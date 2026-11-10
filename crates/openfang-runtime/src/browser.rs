//! Native browser automation via Chrome DevTools Protocol (CDP).
//!
//! Three engines speak CDP and are tried in order (config `engines`):
//! Lightpanda (light, no rendering), Obscura (renders, screenshots,
//! optional stealth fingerprint) and Chromium. Lightpanda and Obscura run
//! as a local CDP server per session; Chromium as before. A page that looks
//! blocked, an empty page from Lightpanda, a screenshot Lightpanda can't
//! take, or an engine that stops answering moves the session to the next
//! engine and the command is tried once more there.
//!
//! # Security
//! - SSRF check runs in Rust before navigate commands
//! - All page content wrapped with `wrap_external_content()` markers
//! - Session limits: max concurrent, idle timeout, 1 per agent
//! - No subprocess bridge, no env leakage, no Python code execution

use dashmap::DashMap;
use futures::stream::{SplitSink, SplitStream};
use futures::{SinkExt, StreamExt};
use openfang_types::config::BrowserConfig;
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::io::AsyncBufReadExt;
use tokio::sync::{oneshot, Mutex};
use tokio_tungstenite::tungstenite::Message as WsMessage;
use tracing::{debug, info, warn};

type WsStream =
    tokio_tungstenite::WebSocketStream<tokio_tungstenite::MaybeTlsStream<tokio::net::TcpStream>>;

// ── Constants ──────────────────────────────────────────────────────────────

const CDP_CONNECT_TIMEOUT_SECS: u64 = 15;
const CDP_COMMAND_TIMEOUT_SECS: u64 = 30;
const PAGE_LOAD_POLL_INTERVAL_MS: u64 = 200;
const PAGE_LOAD_MAX_POLLS: u32 = 150; // 30 seconds
#[allow(dead_code)]
const MAX_CONTENT_CHARS: usize = 50_000;

// ── Public types ───────────────────────────────────────────────────────────

/// Command sent to the browser.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "action")]
pub enum BrowserCommand {
    Navigate { url: String },
    Click { selector: String },
    Type { selector: String, text: String },
    Screenshot,
    ReadPage,
    Close,
    Scroll { direction: String, amount: i32 },
    Wait { selector: String, timeout_ms: u64 },
    RunJs { expression: String },
    Back,
}

/// Response from a browser command.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BrowserResponse {
    pub success: bool,
    pub data: Option<serde_json::Value>,
    pub error: Option<String>,
}

impl BrowserResponse {
    fn ok(data: serde_json::Value) -> Self {
        Self {
            success: true,
            data: Some(data),
            error: None,
        }
    }
    fn err(msg: impl Into<String>) -> Self {
        Self {
            success: false,
            data: None,
            error: Some(msg.into()),
        }
    }
}

// ── CDP connection ─────────────────────────────────────────────────────────

/// Low-level Chrome DevTools Protocol connection over WebSocket.
struct CdpConnection {
    /// Target session (flattened `Target.attachToTarget`); page commands
    /// carry it. None = commands go to the endpoint itself (Chromium page
    /// socket, or browser-level calls before attaching).
    session_id: Option<String>,
    write: Arc<Mutex<SplitSink<WsStream, WsMessage>>>,
    pending: Arc<DashMap<u64, oneshot::Sender<Result<serde_json::Value, String>>>>,
    next_id: AtomicU64,
    _reader_handle: tokio::task::JoinHandle<()>,
}

impl CdpConnection {
    /// Connect to a CDP WebSocket endpoint.
    async fn connect(ws_url: &str) -> Result<Self, String> {
        let (stream, _) = tokio::time::timeout(
            Duration::from_secs(CDP_CONNECT_TIMEOUT_SECS),
            tokio_tungstenite::connect_async(ws_url),
        )
        .await
        .map_err(|_| format!("CDP WebSocket connect timed out: {ws_url}"))?
        .map_err(|e| format!("CDP WebSocket connect failed: {e}"))?;

        let (write, read) = stream.split();
        let write = Arc::new(Mutex::new(write));
        let pending: Arc<DashMap<u64, oneshot::Sender<Result<serde_json::Value, String>>>> =
            Arc::new(DashMap::new());

        let reader_pending = Arc::clone(&pending);
        let reader_handle = tokio::spawn(Self::reader_loop(read, reader_pending));

        Ok(Self {
            session_id: None,
            write,
            pending,
            next_id: AtomicU64::new(1),
            _reader_handle: reader_handle,
        })
    }

    /// Background task: read WebSocket messages and route responses.
    async fn reader_loop(
        mut read: SplitStream<WsStream>,
        pending: Arc<DashMap<u64, oneshot::Sender<Result<serde_json::Value, String>>>>,
    ) {
        while let Some(msg) = read.next().await {
            let text = match msg {
                Ok(WsMessage::Text(t)) => t.to_string(),
                Ok(WsMessage::Close(_)) => break,
                Err(e) => {
                    debug!("CDP WebSocket read error: {e}");
                    break;
                }
                _ => continue,
            };

            let json: serde_json::Value = match serde_json::from_str(&text) {
                Ok(v) => v,
                Err(_) => continue,
            };

            // Route response to waiting caller by id
            if let Some(id) = json.get("id").and_then(|v| v.as_u64()) {
                if let Some((_, sender)) = pending.remove(&id) {
                    if let Some(error) = json.get("error") {
                        let msg = error["message"].as_str().unwrap_or("CDP error").to_string();
                        let _ = sender.send(Err(msg));
                    } else {
                        let result = json
                            .get("result")
                            .cloned()
                            .unwrap_or(serde_json::Value::Null);
                        let _ = sender.send(Ok(result));
                    }
                }
            }
            // Events (method field, no id) are ignored for now.
            // Future: handle Fetch.requestPaused for CDP-level SSRF.
        }
    }

    /// Send a CDP command and wait for the response.
    async fn send(
        &self,
        method: &str,
        params: serde_json::Value,
    ) -> Result<serde_json::Value, String> {
        let id = self.next_id.fetch_add(1, Ordering::Relaxed);
        let (tx, rx) = oneshot::channel();
        self.pending.insert(id, tx);

        let mut msg = serde_json::json!({ "id": id, "method": method, "params": params });
        if let Some(sid) = &self.session_id {
            msg["sessionId"] = serde_json::Value::String(sid.clone());
        }
        self.write
            .lock()
            .await
            .send(WsMessage::Text(msg.to_string()))
            .await
            .map_err(|e| format!("CDP send failed: {e}"))?;

        match tokio::time::timeout(Duration::from_secs(CDP_COMMAND_TIMEOUT_SECS), rx).await {
            Ok(Ok(result)) => result,
            Ok(Err(_)) => Err("CDP response channel closed".to_string()),
            Err(_) => {
                self.pending.remove(&id);
                Err("CDP command timed out".to_string())
            }
        }
    }

    /// Evaluate JavaScript in the browser page and return the value.
    async fn run_js(&self, expression: &str) -> Result<serde_json::Value, String> {
        let result = self
            .send(
                "Runtime.evaluate",
                serde_json::json!({
                    "expression": expression,
                    "returnByValue": true,
                    "awaitPromise": true,
                }),
            )
            .await?;

        // Check for JS exceptions
        if let Some(desc) = result
            .get("exceptionDetails")
            .and_then(|e| e.get("text"))
            .and_then(|t| t.as_str())
        {
            return Err(format!("JS error: {desc}"));
        }

        Ok(result
            .get("result")
            .and_then(|r| r.get("value"))
            .cloned()
            .unwrap_or(serde_json::Value::Null))
    }
}

impl Drop for CdpConnection {
    fn drop(&mut self) {
        self._reader_handle.abort();
    }
}

// ── Browser session ────────────────────────────────────────────────────────

/// A live browser session: one Chromium process + one CDP connection per agent.
struct BrowserSession {
    process: tokio::process::Child,
    cdp: CdpConnection,
    #[allow(dead_code)]
    last_active: Instant,
    engine: Engine,
    /// Last page address the session showed, so another engine can pick up
    /// where this one left off.
    last_url: Option<String>,
}

impl BrowserSession {
    /// Start the first engine (in configured order, minus `skip`) that comes
    /// up. Errors from every engine tried are reported together.
    async fn launch_any(config: &BrowserConfig, skip: &[Engine]) -> Result<Self, String> {
        let mut tried: Vec<String> = Vec::new();
        for engine in engine_order(config) {
            if skip.contains(&engine) {
                continue;
            }
            match Self::launch_engine(config, engine).await {
                Ok(s) => return Ok(s),
                Err(e) => {
                    debug!(engine = engine.label(), error = %e, "Browser engine did not start");
                    tried.push(format!("{}: {e}", engine.label()));
                }
            }
        }
        if tried.is_empty() {
            return Err("No other browser engine is left to try.".to_string());
        }
        Err(format!(
            "No browser engine could start. {}",
            tried.join(" | ")
        ))
    }

    async fn launch_engine(config: &BrowserConfig, engine: Engine) -> Result<Self, String> {
        match engine {
            Engine::Chromium => Self::launch(config).await,
            Engine::Lightpanda | Engine::Obscura => Self::launch_server(config, engine).await,
        }
    }

    /// Start Lightpanda or Obscura as a local CDP server on a free port,
    /// connect, and open one page target to drive.
    async fn launch_server(config: &BrowserConfig, engine: Engine) -> Result<Self, String> {
        let bin = find_engine_binary(config, engine)?;
        let port = std::net::TcpListener::bind("127.0.0.1:0")
            .and_then(|l| l.local_addr())
            .map(|a| a.port())
            .map_err(|e| format!("No free local port: {e}"))?;
        let args = server_args(config, engine, port);
        let mut cmd = tokio::process::Command::new(&bin);
        cmd.args(&args);
        cmd.stdout(std::process::Stdio::null());
        cmd.stderr(std::process::Stdio::null());
        cmd.stdin(std::process::Stdio::null());
        cmd.kill_on_drop(true);
        // SECURITY: clear environment, pass only essentials
        cmd.env_clear();
        for key in &[
            "PATH",
            "HOME",
            "TMPDIR",
            "TEMP",
            "TMP",
            "XDG_CACHE_HOME",
            "XDG_CONFIG_HOME",
        ] {
            if let Ok(val) = std::env::var(key) {
                cmd.env(key, val);
            }
        }
        // Lightpanda reports usage by default; a studio's browsing stays here.
        cmd.env("LIGHTPANDA_DISABLE_TELEMETRY", "true");
        let mut child = cmd
            .spawn()
            .map_err(|e| format!("could not start {}: {e}", bin.display()))?;

        // Wait for the server to accept connections (or exit early).
        let deadline = Instant::now() + Duration::from_secs(CDP_CONNECT_TIMEOUT_SECS);
        loop {
            if let Ok(Some(status)) = child.try_wait() {
                return Err(format!("exited before it was ready ({status})"));
            }
            if tokio::net::TcpStream::connect(("127.0.0.1", port))
                .await
                .is_ok()
            {
                break;
            }
            if Instant::now() >= deadline {
                let _ = child.start_kill();
                return Err("did not start listening in time".to_string());
            }
            tokio::time::sleep(Duration::from_millis(150)).await;
        }

        let mut cdp = match connect_browser_endpoint(port).await {
            Ok(c) => c,
            Err(e) => {
                let _ = child.start_kill();
                return Err(e);
            }
        };
        if let Err(e) = attach_page(&mut cdp).await {
            let _ = child.start_kill();
            return Err(e);
        }
        let _ = cdp.send("Page.enable", serde_json::json!({})).await;
        let _ = cdp.send("Runtime.enable", serde_json::json!({})).await;
        info!(engine = engine.label(), port, "Browser engine started");
        Ok(Self {
            process: child,
            cdp,
            last_active: Instant::now(),
            engine,
            last_url: None,
        })
    }

    /// Launch Chromium and establish a CDP connection.
    async fn launch(config: &BrowserConfig) -> Result<Self, String> {
        let chrome_path = find_chromium(config)?;
        debug!(path = %chrome_path.display(), "Launching Chromium");

        let mut args = vec![
            "--remote-debugging-port=0".to_string(),
            "--no-first-run".to_string(),
            "--no-default-browser-check".to_string(),
            "--disable-extensions".to_string(),
            "--disable-background-networking".to_string(),
            "--disable-sync".to_string(),
            "--disable-translate".to_string(),
            "--disable-features=TranslateUI".to_string(),
            "--metrics-recording-only".to_string(),
            format!(
                "--window-size={},{}",
                config.viewport_width, config.viewport_height
            ),
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36".to_string(),
            "about:blank".to_string(),
        ];
        if config.headless {
            args.insert(0, "--headless=new".to_string());
            args.push("--disable-gpu".to_string());
        }
        // Chromium refuses to run as root without --no-sandbox. Detect this
        // without adding a libc dependency by reading the effective UID from
        // /proc/self/status (Linux) or falling back to the HOME env var.
        if is_running_as_root() {
            args.push("--no-sandbox".to_string());
        }

        let mut cmd = tokio::process::Command::new(&chrome_path);
        cmd.args(&args);
        cmd.stderr(std::process::Stdio::piped());
        cmd.stdout(std::process::Stdio::null());
        cmd.stdin(std::process::Stdio::null());

        // SECURITY: clear environment, pass only essentials
        cmd.env_clear();
        for key in &[
            "PATH",
            "HOME",
            "USERPROFILE",
            "SYSTEMROOT",
            "TEMP",
            "TMP",
            "TMPDIR",
            "APPDATA",
            "LOCALAPPDATA",
            "XDG_CONFIG_HOME",
            "XDG_CACHE_HOME",
            "DISPLAY",
            "WAYLAND_DISPLAY",
        ] {
            if let Ok(val) = std::env::var(key) {
                cmd.env(key, val);
            }
        }

        let mut child = cmd.spawn().map_err(|e| {
            format!(
                "Failed to launch Chromium at {}: {e}",
                chrome_path.display()
            )
        })?;

        // Parse stderr for the DevTools WebSocket URL
        let stderr = child.stderr.take().ok_or("No stderr from Chromium")?;
        let ws_url = Self::read_devtools_url(stderr).await?;
        debug!(ws_url = %ws_url, "Got CDP WebSocket URL");

        // GET /json/list to find the page target
        let port = ws_url
            .split("://")
            .nth(1)
            .and_then(|s| s.split(':').nth(1))
            .and_then(|s| s.split('/').next())
            .ok_or("Cannot parse port from CDP URL")?;
        let list_url = format!("http://127.0.0.1:{port}/json/list");

        let page_ws = Self::find_page_ws(&list_url).await?;
        debug!(page_ws = %page_ws, "Connecting to page");

        let cdp = CdpConnection::connect(&page_ws).await?;

        // Enable required domains
        let _ = cdp.send("Page.enable", serde_json::json!({})).await;
        let _ = cdp.send("Runtime.enable", serde_json::json!({})).await;

        Ok(Self {
            process: child,
            cdp,
            last_active: Instant::now(),
            engine: Engine::Chromium,
            last_url: None,
        })
    }

    /// Read stderr until we find "DevTools listening on ws://...".
    async fn read_devtools_url(stderr: tokio::process::ChildStderr) -> Result<String, String> {
        let reader = tokio::io::BufReader::new(stderr);
        let mut lines = reader.lines();
        let deadline = tokio::time::Instant::now() + Duration::from_secs(CDP_CONNECT_TIMEOUT_SECS);

        loop {
            let line = tokio::time::timeout_at(deadline, lines.next_line())
                .await
                .map_err(|_| {
                    "Timed out waiting for Chromium to start. Is Chrome/Chromium installed?"
                        .to_string()
                })?
                .map_err(|e| format!("Failed to read Chromium stderr: {e}"))?;

            match line {
                Some(l) if l.contains("DevTools listening on") => {
                    let url = l
                        .split("DevTools listening on ")
                        .nth(1)
                        .ok_or("Malformed DevTools URL line")?
                        .trim()
                        .to_string();
                    return Ok(url);
                }
                Some(_) => continue,
                None => {
                    return Err(
                        "Chromium exited before printing DevTools URL. Is Chrome installed?"
                            .to_string(),
                    );
                }
            }
        }
    }

    /// Fetch /json/list and find the page WebSocket URL.
    async fn find_page_ws(list_url: &str) -> Result<String, String> {
        for attempt in 0..10 {
            if attempt > 0 {
                tokio::time::sleep(Duration::from_millis(300)).await;
            }
            let resp = match reqwest::get(list_url).await {
                Ok(r) => r,
                Err(_) => continue,
            };
            let targets: Vec<serde_json::Value> = match resp.json().await {
                Ok(t) => t,
                Err(_) => continue,
            };
            for target in &targets {
                if target["type"].as_str() == Some("page") {
                    if let Some(ws) = target["webSocketDebuggerUrl"].as_str() {
                        return Ok(ws.to_string());
                    }
                }
            }
        }
        Err("No page target found in Chromium".to_string())
    }

    /// Execute a browser command via CDP.
    async fn execute(&mut self, cmd: BrowserCommand) -> BrowserResponse {
        self.last_active = Instant::now();
        let resp = self.execute_inner(cmd).await;
        if resp.success {
            if let Some(u) = resp
                .data
                .as_ref()
                .and_then(|d| d["url"].as_str())
                .filter(|u| u.starts_with("http"))
            {
                self.last_url = Some(u.to_string());
            }
        }
        resp
    }

    async fn execute_inner(&mut self, cmd: BrowserCommand) -> BrowserResponse {
        match cmd {
            BrowserCommand::Navigate { url } => self.cmd_navigate(&url).await,
            BrowserCommand::Click { selector } => self.cmd_click(&selector).await,
            BrowserCommand::Type { selector, text } => self.cmd_type(&selector, &text).await,
            BrowserCommand::Screenshot => self.cmd_screenshot().await,
            BrowserCommand::ReadPage => self.cmd_read_page().await,
            BrowserCommand::Close => BrowserResponse::ok(serde_json::json!({"closed": true})),
            BrowserCommand::Scroll { direction, amount } => {
                self.cmd_scroll(&direction, amount).await
            }
            BrowserCommand::Wait {
                selector,
                timeout_ms,
            } => self.cmd_wait(&selector, timeout_ms).await,
            BrowserCommand::RunJs { expression } => self.cmd_run_js(&expression).await,
            BrowserCommand::Back => self.cmd_back().await,
        }
    }

    // ── Command implementations ────────────────────────────────────────

    async fn cmd_navigate(&self, url: &str) -> BrowserResponse {
        let result = self
            .cdp
            .send("Page.navigate", serde_json::json!({ "url": url }))
            .await;

        if let Err(e) = result {
            return BrowserResponse::err(format!("Navigate failed: {e}"));
        }

        // Wait for page load
        self.wait_for_load().await;

        match self.page_info().await {
            Ok(info) => BrowserResponse::ok(info),
            Err(e) => BrowserResponse::err(format!("Navigate succeeded but page info failed: {e}")),
        }
    }

    async fn cmd_click(&self, selector: &str) -> BrowserResponse {
        let sel_json = serde_json::to_string(selector).unwrap_or_default();
        let js = format!(
            r#"(() => {{
    let sel = {sel_json};
    let el = document.querySelector(sel);
    if (!el) {{
        const all = document.querySelectorAll('a, button, [role="button"], input[type="submit"], [onclick]');
        const lower = sel.toLowerCase();
        for (const e of all) {{
            if (e.textContent.trim().toLowerCase().includes(lower)) {{ el = e; break; }}
        }}
    }}
    if (!el) return JSON.stringify({{success: false, error: 'Element not found: ' + sel}});
    el.scrollIntoView({{block: 'center'}});
    el.click();
    return JSON.stringify({{success: true, tag: el.tagName, text: el.textContent.substring(0, 100).trim()}});
}})()"#
        );

        match self.cdp.run_js(&js).await {
            Ok(val) => {
                let parsed: serde_json::Value = val
                    .as_str()
                    .and_then(|s| serde_json::from_str(s).ok())
                    .unwrap_or(val);
                if parsed["success"].as_bool() == Some(false) {
                    return BrowserResponse::err(
                        parsed["error"]
                            .as_str()
                            .unwrap_or("Click failed")
                            .to_string(),
                    );
                }
                // Wait briefly for any navigation triggered by click
                tokio::time::sleep(Duration::from_millis(500)).await;
                self.wait_for_load().await;
                match self.page_info().await {
                    Ok(info) => BrowserResponse::ok(info),
                    Err(_) => BrowserResponse::ok(parsed),
                }
            }
            Err(e) => BrowserResponse::err(format!("Click failed: {e}")),
        }
    }

    async fn cmd_type(&self, selector: &str, text: &str) -> BrowserResponse {
        let sel_json = serde_json::to_string(selector).unwrap_or_default();
        let text_json = serde_json::to_string(text).unwrap_or_default();
        let js = format!(
            r#"(() => {{
    let sel = {sel_json};
    let txt = {text_json};
    let el = document.querySelector(sel);
    if (!el) return JSON.stringify({{success: false, error: 'Input not found: ' + sel}});
    el.focus();
    el.value = txt;
    el.dispatchEvent(new Event('input', {{bubbles: true}}));
    el.dispatchEvent(new Event('change', {{bubbles: true}}));
    return JSON.stringify({{success: true, selector: sel, typed: txt.length + ' chars'}});
}})()"#
        );

        match self.cdp.run_js(&js).await {
            Ok(val) => {
                let parsed: serde_json::Value = val
                    .as_str()
                    .and_then(|s| serde_json::from_str(s).ok())
                    .unwrap_or(val);
                if parsed["success"].as_bool() == Some(false) {
                    BrowserResponse::err(parsed["error"].as_str().unwrap_or("Type failed"))
                } else {
                    BrowserResponse::ok(parsed)
                }
            }
            Err(e) => BrowserResponse::err(format!("Type failed: {e}")),
        }
    }

    async fn cmd_screenshot(&self) -> BrowserResponse {
        match self
            .cdp
            .send(
                "Page.captureScreenshot",
                serde_json::json!({ "format": "png" }),
            )
            .await
        {
            Ok(result) => {
                let b64 = result["data"].as_str().unwrap_or("");
                let url = self
                    .cdp
                    .run_js("location.href")
                    .await
                    .ok()
                    .and_then(|v| v.as_str().map(String::from))
                    .unwrap_or_default();
                BrowserResponse::ok(
                    serde_json::json!({"image_base64": b64, "url": url, "format": "png"}),
                )
            }
            Err(e) => BrowserResponse::err(format!("Screenshot failed: {e}")),
        }
    }

    async fn cmd_read_page(&self) -> BrowserResponse {
        match self.cdp.run_js(EXTRACT_CONTENT_JS).await {
            Ok(val) => {
                let parsed: serde_json::Value = val
                    .as_str()
                    .and_then(|s| serde_json::from_str(s).ok())
                    .unwrap_or(val);
                BrowserResponse::ok(parsed)
            }
            Err(e) => BrowserResponse::err(format!("ReadPage failed: {e}")),
        }
    }

    async fn cmd_scroll(&self, direction: &str, amount: i32) -> BrowserResponse {
        let (dx, dy) = match direction {
            "up" => (0, -amount),
            "down" => (0, amount),
            "left" => (-amount, 0),
            "right" => (amount, 0),
            _ => (0, amount),
        };
        let js = format!("window.scrollBy({dx}, {dy}); JSON.stringify({{scrollX: window.scrollX, scrollY: window.scrollY}})");
        match self.cdp.run_js(&js).await {
            Ok(val) => {
                let parsed: serde_json::Value = val
                    .as_str()
                    .and_then(|s| serde_json::from_str(s).ok())
                    .unwrap_or(val);
                BrowserResponse::ok(parsed)
            }
            Err(e) => BrowserResponse::err(format!("Scroll failed: {e}")),
        }
    }

    async fn cmd_wait(&self, selector: &str, timeout_ms: u64) -> BrowserResponse {
        let sel_json = serde_json::to_string(selector).unwrap_or_default();
        let max_ms = timeout_ms.min(30_000);
        let polls = (max_ms / PAGE_LOAD_POLL_INTERVAL_MS).max(1);

        for _ in 0..polls {
            let js = format!("document.querySelector({sel_json}) ? 'found' : null");
            if let Ok(val) = self.cdp.run_js(&js).await {
                if val.as_str() == Some("found") {
                    return BrowserResponse::ok(
                        serde_json::json!({"found": true, "selector": selector}),
                    );
                }
            }
            tokio::time::sleep(Duration::from_millis(PAGE_LOAD_POLL_INTERVAL_MS)).await;
        }

        BrowserResponse::err(format!(
            "Timed out waiting for selector: {selector} ({max_ms}ms)"
        ))
    }

    async fn cmd_run_js(&self, expression: &str) -> BrowserResponse {
        match self.cdp.run_js(expression).await {
            Ok(val) => BrowserResponse::ok(serde_json::json!({"result": val})),
            Err(e) => BrowserResponse::err(format!("JS execution failed: {e}")),
        }
    }

    async fn cmd_back(&self) -> BrowserResponse {
        match self.cdp.run_js("history.back(); 'ok'").await {
            Ok(_) => {
                tokio::time::sleep(Duration::from_millis(500)).await;
                self.wait_for_load().await;
                match self.page_info().await {
                    Ok(info) => BrowserResponse::ok(info),
                    Err(e) => {
                        BrowserResponse::err(format!("Back succeeded but page info failed: {e}"))
                    }
                }
            }
            Err(e) => BrowserResponse::err(format!("Back failed: {e}")),
        }
    }

    // ── Helpers ────────────────────────────────────────────────────────

    /// Poll until document.readyState is 'complete' or 'interactive'.
    async fn wait_for_load(&self) {
        for _ in 0..PAGE_LOAD_MAX_POLLS {
            if let Ok(val) = self.cdp.run_js("document.readyState").await {
                let state = val.as_str().unwrap_or("");
                if state == "complete" || state == "interactive" {
                    return;
                }
            }
            tokio::time::sleep(Duration::from_millis(PAGE_LOAD_POLL_INTERVAL_MS)).await;
        }
    }

    /// Get current page title, URL, and readable content.
    async fn page_info(&self) -> Result<serde_json::Value, String> {
        let info = self
            .cdp
            .run_js("JSON.stringify({title: document.title, url: location.href})")
            .await?;
        let parsed: serde_json::Value = info
            .as_str()
            .and_then(|s| serde_json::from_str(s).ok())
            .unwrap_or(info);

        let content_val = self
            .cdp
            .run_js(EXTRACT_CONTENT_JS)
            .await
            .unwrap_or_default();
        let content_obj: serde_json::Value = content_val
            .as_str()
            .and_then(|s| serde_json::from_str(s).ok())
            .unwrap_or(content_val);
        let content_text = content_obj["content"].as_str().unwrap_or("");

        Ok(serde_json::json!({
            "title": parsed["title"],
            "url": parsed["url"],
            "content": content_text,
        }))
    }
}

impl Drop for BrowserSession {
    fn drop(&mut self) {
        let _ = self.process.start_kill();
    }
}

// ── Engines ────────────────────────────────────────────────────────────────

/// A CDP browser engine.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Engine {
    /// Lightpanda: small and fast, runs page scripts, draws nothing.
    Lightpanda,
    /// Obscura: renders and screenshots; optional stealth fingerprint.
    Obscura,
    /// Chromium/Chrome: the full browser, last resort.
    Chromium,
}

impl Engine {
    pub fn parse(name: &str) -> Option<Self> {
        match name.trim().to_ascii_lowercase().as_str() {
            "lightpanda" => Some(Self::Lightpanda),
            "obscura" => Some(Self::Obscura),
            "chromium" | "chrome" => Some(Self::Chromium),
            _ => None,
        }
    }

    pub fn label(self) -> &'static str {
        match self {
            Self::Lightpanda => "Lightpanda",
            Self::Obscura => "Obscura",
            Self::Chromium => "Chromium",
        }
    }

    fn binary_name(self) -> &'static str {
        match self {
            Self::Lightpanda => "lightpanda",
            Self::Obscura => "obscura",
            Self::Chromium => "chromium",
        }
    }
}

/// The engines to try, in order, without repeats. Unknown names are
/// skipped; nothing usable configured means all three in the default order.
pub fn engine_order(config: &BrowserConfig) -> Vec<Engine> {
    let mut out: Vec<Engine> = Vec::new();
    for e in config.engines.iter().filter_map(|n| Engine::parse(n)) {
        if !out.contains(&e) {
            out.push(e);
        }
    }
    if out.is_empty() {
        out = vec![Engine::Lightpanda, Engine::Obscura, Engine::Chromium];
    }
    out
}

/// Command-line arguments for a server engine listening on `port`.
fn server_args(config: &BrowserConfig, engine: Engine, port: u16) -> Vec<String> {
    let mut a = vec!["serve".to_string()];
    match engine {
        Engine::Lightpanda => {
            a.extend([
                "--host".to_string(),
                "127.0.0.1".to_string(),
                "--port".to_string(),
                port.to_string(),
            ]);
            if config.obey_robots {
                a.push("--obey-robots".to_string());
            }
        }
        Engine::Obscura => {
            a.extend(["--port".to_string(), port.to_string()]);
            if config.obscura_stealth {
                a.push("--stealth".to_string());
            }
        }
        Engine::Chromium => {}
    }
    a
}

/// Where a server engine's program is: the configured path, then
/// $LIGHTPANDA_PATH / $OBSCURA_PATH, then <openfang home>/bin/<name>,
/// then PATH.
fn find_engine_binary(config: &BrowserConfig, engine: Engine) -> Result<PathBuf, String> {
    let configured = match engine {
        Engine::Lightpanda => config.lightpanda_path.clone(),
        Engine::Obscura => config.obscura_path.clone(),
        Engine::Chromium => config.chromium_path.clone(),
    };
    if let Some(p) = configured.filter(|p| !p.trim().is_empty()) {
        let p = PathBuf::from(p);
        return if p.is_file() {
            Ok(p)
        } else {
            Err(format!("not found at configured path {}", p.display()))
        };
    }
    let env_key = match engine {
        Engine::Lightpanda => "LIGHTPANDA_PATH",
        Engine::Obscura => "OBSCURA_PATH",
        Engine::Chromium => "CHROME_PATH",
    };
    if let Ok(p) = std::env::var(env_key) {
        let p = PathBuf::from(p);
        if p.is_file() {
            return Ok(p);
        }
    }
    let home = std::env::var("OPENFANG_HOME")
        .map(PathBuf::from)
        .ok()
        .or_else(|| {
            std::env::var("HOME")
                .ok()
                .map(|h| PathBuf::from(h).join(".openfang"))
        });
    if let Some(h) = home {
        let p = h.join("bin").join(engine.binary_name());
        if p.is_file() {
            return Ok(p);
        }
    }
    if let Ok(out) = std::process::Command::new("which")
        .arg(engine.binary_name())
        .output()
    {
        let found = String::from_utf8_lossy(&out.stdout).trim().to_string();
        if out.status.success() && !found.is_empty() {
            return Ok(PathBuf::from(found));
        }
    }
    Err(format!(
        "not installed (looked for {} in the config, ${env_key}, <home>/bin and PATH)",
        engine.binary_name()
    ))
}

/// Connect to a CDP server's browser endpoint on `port`. Tries the address
/// /json/version announces, then the bare socket, then /devtools/browser,
/// and keeps the first one that answers a command.
async fn connect_browser_endpoint(port: u16) -> Result<CdpConnection, String> {
    let mut candidates: Vec<String> = Vec::new();
    if let Ok(resp) = reqwest::Client::new()
        .get(format!("http://127.0.0.1:{port}/json/version"))
        .timeout(Duration::from_secs(3))
        .send()
        .await
    {
        if let Ok(v) = resp.json::<serde_json::Value>().await {
            if let Some(ws) = v["webSocketDebuggerUrl"].as_str() {
                candidates.push(ws.to_string());
            }
        }
    }
    candidates.push(format!("ws://127.0.0.1:{port}"));
    candidates.push(format!("ws://127.0.0.1:{port}/devtools/browser"));
    let mut last = String::new();
    for ws in candidates {
        match CdpConnection::connect(&ws).await {
            Ok(c) => {
                let probe = tokio::time::timeout(
                    Duration::from_secs(5),
                    c.send("Target.getTargets", serde_json::json!({})),
                )
                .await;
                match probe {
                    Ok(Ok(_)) => return Ok(c),
                    Ok(Err(e)) => last = format!("{ws}: {e}"),
                    Err(_) => last = format!("{ws}: no answer"),
                }
            }
            Err(e) => last = e,
        }
    }
    Err(format!("could not talk to it over CDP ({last})"))
}

/// Open a fresh page and attach to it (flattened session): every page
/// command afterwards carries its session id.
async fn attach_page(cdp: &mut CdpConnection) -> Result<(), String> {
    let created = cdp
        .send(
            "Target.createTarget",
            serde_json::json!({ "url": "about:blank" }),
        )
        .await
        .map_err(|e| format!("could not open a page: {e}"))?;
    let target = created["targetId"]
        .as_str()
        .ok_or("could not open a page: no target id")?
        .to_string();
    let attached = cdp
        .send(
            "Target.attachToTarget",
            serde_json::json!({ "targetId": target, "flatten": true }),
        )
        .await
        .map_err(|e| format!("could not attach to the page: {e}"))?;
    let sid = attached["sessionId"]
        .as_str()
        .ok_or("could not attach to the page: no session id")?;
    cdp.session_id = Some(sid.to_string());
    Ok(())
}

/// Phrases a page shows when a site turned the browser away. Checked in
/// the title always, and in the text only for short pages (a real page that
/// merely mentions "captcha" in its footer is long).
const BLOCK_PHRASES: &[&str] = &[
    "just a moment",
    "checking your browser",
    "attention required",
    "verify you are human",
    "verify you are a human",
    "are you a robot",
    "are you human",
    "access denied",
    "request blocked",
    "you have been blocked",
    "pardon our interruption",
    "unusual traffic",
    "enable javascript and cookies to continue",
    "please enable cookies",
    "security check",
    "bot detection",
    "403 forbidden",
    "error 1020",
    "captcha-delivery",
    "px-captcha",
];

/// Short pages (block walls are short) get their text checked too.
const BLOCK_TEXT_MAX_CHARS: usize = 4000;

/// Why a loaded page looks like a block wall instead of the site, or None.
pub fn looks_blocked(title: &str, content: &str) -> Option<&'static str> {
    let t = title.to_lowercase();
    if let Some(p) = BLOCK_PHRASES.iter().find(|p| t.contains(*p)) {
        return Some(p);
    }
    if content.chars().count() < BLOCK_TEXT_MAX_CHARS {
        let c = content.to_lowercase();
        if let Some(p) = BLOCK_PHRASES.iter().find(|p| c.contains(*p)) {
            return Some(p);
        }
    }
    None
}

/// Whether a command's result should move the session to the next engine,
/// and why (in words for the owner and the agent).
fn fallback_reason(cmd: &BrowserCommand, resp: &BrowserResponse, engine: Engine) -> Option<String> {
    if !resp.success {
        let err = resp.error.as_deref().unwrap_or("");
        let lost = [
            "CDP send failed",
            "channel closed",
            "CDP command timed out",
            "WebSocket",
        ]
        .iter()
        .any(|m| err.contains(m));
        if lost {
            return Some(format!("{} stopped responding", engine.label()));
        }
        if matches!(cmd, BrowserCommand::Screenshot) && engine == Engine::Lightpanda {
            return Some("Lightpanda can't take screenshots".to_string());
        }
        return None;
    }
    if !matches!(cmd, BrowserCommand::Navigate { .. }) {
        return None;
    }
    let data = resp.data.clone().unwrap_or_default();
    let title = data["title"].as_str().unwrap_or("");
    let content = data["content"].as_str().unwrap_or("");
    if let Some(p) = looks_blocked(title, content) {
        return Some(format!(
            "the page looked blocked (\"{p}\") in {}",
            engine.label()
        ));
    }
    if engine == Engine::Lightpanda && content.trim().chars().count() < 20 {
        return Some("the page came back empty in Lightpanda".to_string());
    }
    None
}

// ── Chromium discovery ─────────────────────────────────────────────────────

/// Find a Chromium-based browser binary on this system.
fn find_chromium(config: &BrowserConfig) -> Result<PathBuf, String> {
    // 1. User-configured path
    if let Some(ref path) = config.chromium_path {
        if !path.is_empty() {
            let p = PathBuf::from(path);
            if p.exists() {
                return Ok(p);
            }
            return Err(format!("Configured chromium_path not found: {path}"));
        }
    }

    // 2. CHROME_PATH env var
    if let Ok(path) = std::env::var("CHROME_PATH") {
        let p = PathBuf::from(&path);
        if p.exists() {
            return Ok(p);
        }
    }

    // 3. Platform-specific search
    let candidates = chromium_candidates();
    for candidate in &candidates {
        let p = PathBuf::from(candidate);
        if p.exists() {
            return Ok(p);
        }
    }

    // 4. Try PATH lookup
    for name in &[
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
        "chrome",
    ] {
        if let Ok(output) = std::process::Command::new("which").arg(name).output() {
            if output.status.success() {
                let path = String::from_utf8_lossy(&output.stdout).trim().to_string();
                if !path.is_empty() {
                    return Ok(PathBuf::from(path));
                }
            }
        }
        // Windows: use where.exe
        #[cfg(windows)]
        if let Ok(output) = std::process::Command::new("where.exe").arg(name).output() {
            if output.status.success() {
                let path = String::from_utf8_lossy(&output.stdout)
                    .lines()
                    .next()
                    .unwrap_or("")
                    .trim()
                    .to_string();
                if !path.is_empty() {
                    return Ok(PathBuf::from(path));
                }
            }
        }
    }

    Err(
        "Chromium/Chrome not found. Install Chrome or set CHROME_PATH. \
         Checked: Chrome, Chromium, Edge, Brave in standard locations."
            .to_string(),
    )
}

/// Platform-specific candidate paths for Chromium-based browsers.
fn chromium_candidates() -> Vec<String> {
    let mut paths = Vec::new();

    #[cfg(windows)]
    {
        let program_files = std::env::var("ProgramFiles").unwrap_or_default();
        let program_files_x86 = std::env::var("ProgramFiles(x86)").unwrap_or_default();
        let local_app = std::env::var("LOCALAPPDATA").unwrap_or_default();

        for pf in &[&program_files, &program_files_x86] {
            if pf.is_empty() {
                continue;
            }
            paths.push(format!("{pf}\\Google\\Chrome\\Application\\chrome.exe"));
            paths.push(format!("{pf}\\Microsoft\\Edge\\Application\\msedge.exe"));
            paths.push(format!(
                "{pf}\\BraveSoftware\\Brave-Browser\\Application\\brave.exe"
            ));
        }
        if !local_app.is_empty() {
            paths.push(format!(
                "{local_app}\\Google\\Chrome\\Application\\chrome.exe"
            ));
            paths.push(format!(
                "{local_app}\\Microsoft\\Edge\\Application\\msedge.exe"
            ));
        }
    }

    #[cfg(target_os = "macos")]
    {
        paths.push("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome".into());
        paths.push("/Applications/Chromium.app/Contents/MacOS/Chromium".into());
        paths.push("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge".into());
        paths.push("/Applications/Brave Browser.app/Contents/MacOS/Brave Browser".into());
    }

    #[cfg(target_os = "linux")]
    {
        paths.push("/usr/bin/google-chrome".into());
        paths.push("/usr/bin/google-chrome-stable".into());
        paths.push("/usr/bin/chromium".into());
        paths.push("/usr/bin/chromium-browser".into());
        paths.push("/snap/bin/chromium".into());
        paths.push("/usr/bin/microsoft-edge".into());
        paths.push("/usr/bin/brave-browser".into());
    }

    paths
}

// ── Browser manager ────────────────────────────────────────────────────────

/// Manages browser sessions for all agents.
pub struct BrowserManager {
    sessions: DashMap<String, Arc<Mutex<BrowserSession>>>,
    config: BrowserConfig,
}

impl BrowserManager {
    /// Create a new BrowserManager with the given configuration.
    pub fn new(config: BrowserConfig) -> Self {
        Self {
            sessions: DashMap::new(),
            config,
        }
    }

    /// Check whether an agent has an active browser session.
    pub fn has_session(&self, agent_id: &str) -> bool {
        self.sessions.contains_key(agent_id)
    }

    /// Send a command to an agent's browser session (creating one if needed).
    ///
    /// When the result says this engine can't do it (the page looked
    /// blocked, came back empty in Lightpanda, the engine stopped answering,
    /// or Lightpanda was asked for a screenshot), the session moves to the
    /// next engine and the command is tried there: navigation as given;
    /// reading and screenshots after reopening the last page.
    pub async fn send_command(
        &self,
        agent_id: &str,
        cmd: BrowserCommand,
    ) -> Result<BrowserResponse, String> {
        let session = self.get_or_create(agent_id).await?;
        let mut guard = session.lock().await;
        let mut resp = guard.execute(cmd.clone()).await;
        let mut tried = vec![guard.engine];
        let mut notes: Vec<String> = Vec::new();
        while let Some(why) = fallback_reason(&cmd, &resp, guard.engine) {
            let replay = match &cmd {
                BrowserCommand::Navigate { .. } => true,
                BrowserCommand::ReadPage | BrowserCommand::Screenshot => guard.last_url.is_some(),
                _ => false,
            };
            let resume = guard.last_url.clone();
            let next = match BrowserSession::launch_any(&self.config, &tried).await {
                Ok(n) => n,
                Err(e) => {
                    debug!(agent_id, error = %e, "No other browser engine to fall back to");
                    break;
                }
            };
            info!(
                agent_id,
                from = guard.engine.label(),
                to = next.engine.label(),
                reason = %why,
                "Browser switching engine"
            );
            notes.push(format!("{why} — switched to {}", next.engine.label()));
            tried.push(next.engine);
            *guard = next;
            if !replay {
                resp = BrowserResponse::err(format!(
                    "{why}; the browser moved to {}. Open the page again with browser_navigate, then retry.",
                    guard.engine.label()
                ));
                break;
            }
            if !matches!(cmd, BrowserCommand::Navigate { .. }) {
                if let Some(u) = resume {
                    let _ = guard.execute(BrowserCommand::Navigate { url: u }).await;
                }
            }
            resp = guard.execute(cmd.clone()).await;
        }
        if resp.success {
            if let Some(d) = resp.data.as_mut().filter(|d| d.is_object()) {
                d["engine"] = serde_json::Value::String(guard.engine.label().to_string());
                if !notes.is_empty() {
                    d["switched"] = serde_json::Value::String(notes.join("; "));
                }
            }
        } else if let Some(ref err) = resp.error {
            warn!(agent_id, engine = guard.engine.label(), error = %err, "Browser command failed");
        }
        Ok(resp)
    }

    /// Which engine an agent's browser session is running on, if any.
    pub async fn engine_of(&self, agent_id: &str) -> Option<Engine> {
        let s = self.sessions.get(agent_id).map(|e| Arc::clone(e.value()))?;
        let g = s.lock().await;
        Some(g.engine)
    }

    /// Close an agent's browser session.
    pub async fn close_session(&self, agent_id: &str) {
        if let Some((_, session)) = self.sessions.remove(agent_id) {
            drop(session);
            info!(agent_id, "Browser session closed");
        }
    }

    /// Clean up an agent's browser session (called after agent loop ends).
    pub async fn cleanup_agent(&self, agent_id: &str) {
        self.close_session(agent_id).await;
    }

    /// Get existing session or create a new one.
    async fn get_or_create(&self, agent_id: &str) -> Result<Arc<Mutex<BrowserSession>>, String> {
        if let Some(entry) = self.sessions.get(agent_id) {
            return Ok(Arc::clone(entry.value()));
        }

        if self.sessions.len() >= self.config.max_sessions {
            return Err(format!(
                "Maximum browser sessions reached ({}). Close an existing session first.",
                self.config.max_sessions
            ));
        }

        let session = BrowserSession::launch_any(&self.config, &[]).await?;
        let engine = session.engine.label();
        let arc = Arc::new(Mutex::new(session));
        self.sessions.insert(agent_id.to_string(), Arc::clone(&arc));
        info!(agent_id, engine, "Browser session created (native CDP)");
        Ok(arc)
    }
}

// ── Tool handler functions ─────────────────────────────────────────────────

/// browser_navigate: Navigate to a URL. SSRF-checked before sending.
pub async fn tool_browser_navigate(
    input: &serde_json::Value,
    mgr: &BrowserManager,
    agent_id: &str,
) -> Result<String, String> {
    let url = input["url"].as_str().ok_or("Missing 'url' parameter")?;
    crate::web_fetch::check_ssrf(url, &[])?;

    let resp = mgr
        .send_command(
            agent_id,
            BrowserCommand::Navigate {
                url: url.to_string(),
            },
        )
        .await?;
    if !resp.success {
        return Err(resp.error.unwrap_or_else(|| "Navigate failed".to_string()));
    }

    let data = resp.data.unwrap_or_default();
    let title = data["title"].as_str().unwrap_or("(no title)");
    let page_url = data["url"].as_str().unwrap_or(url);
    let content = data["content"].as_str().unwrap_or("");
    let wrapped = crate::web_content::wrap_external_content(page_url, content);
    let engine = data["engine"].as_str().unwrap_or("");
    let switched = data["switched"]
        .as_str()
        .map(|s| format!("Browser note: {s}\n"))
        .unwrap_or_default();
    let blocked = looks_blocked(title, content)
        .map(|p| format!("Browser note: this page still looks like a block wall (\"{p}\") — no engine got past it. Try web_fetch, another source, or tell the owner.\n"))
        .unwrap_or_default();
    Ok(format!(
        "Navigated to: {page_url}\nTitle: {title}\nBrowser: {engine}\n{switched}{blocked}\n{wrapped}"
    ))
}

/// browser_click: Click an element by CSS selector or visible text.
pub async fn tool_browser_click(
    input: &serde_json::Value,
    mgr: &BrowserManager,
    agent_id: &str,
) -> Result<String, String> {
    let selector = input["selector"]
        .as_str()
        .ok_or("Missing 'selector' parameter")?;

    let resp = mgr
        .send_command(
            agent_id,
            BrowserCommand::Click {
                selector: selector.to_string(),
            },
        )
        .await?;
    if !resp.success {
        return Err(resp.error.unwrap_or_else(|| "Click failed".to_string()));
    }

    let data = resp.data.unwrap_or_default();
    let title = data["title"].as_str().unwrap_or("(no title)");
    let url = data["url"].as_str().unwrap_or("");
    Ok(format!("Clicked: {selector}\nPage: {title}\nURL: {url}"))
}

/// browser_type: Type text into an input field.
pub async fn tool_browser_type(
    input: &serde_json::Value,
    mgr: &BrowserManager,
    agent_id: &str,
) -> Result<String, String> {
    let selector = input["selector"]
        .as_str()
        .ok_or("Missing 'selector' parameter")?;
    let text = input["text"].as_str().ok_or("Missing 'text' parameter")?;

    let resp = mgr
        .send_command(
            agent_id,
            BrowserCommand::Type {
                selector: selector.to_string(),
                text: text.to_string(),
            },
        )
        .await?;
    if !resp.success {
        return Err(resp.error.unwrap_or_else(|| "Type failed".to_string()));
    }
    Ok(format!("Typed into {selector}: {text}"))
}

/// browser_screenshot: Take a screenshot of the current page.
pub async fn tool_browser_screenshot(
    _input: &serde_json::Value,
    mgr: &BrowserManager,
    agent_id: &str,
) -> Result<String, String> {
    let resp = mgr
        .send_command(agent_id, BrowserCommand::Screenshot)
        .await?;
    if !resp.success {
        return Err(resp
            .error
            .unwrap_or_else(|| "Screenshot failed".to_string()));
    }

    let data = resp.data.unwrap_or_default();
    let b64 = data["image_base64"].as_str().unwrap_or("");
    let url = data["url"].as_str().unwrap_or("");

    let mut image_urls: Vec<String> = Vec::new();
    if !b64.is_empty() {
        use base64::Engine;
        let upload_dir = openfang_types::uploads::ensure_dir()
            .unwrap_or_else(|_| openfang_types::uploads::dir());
        let file_id = uuid::Uuid::new_v4().to_string();
        if let Ok(decoded) = base64::engine::general_purpose::STANDARD.decode(b64) {
            let path = upload_dir.join(&file_id);
            if std::fs::write(&path, &decoded).is_ok() {
                image_urls.push(format!("/api/uploads/{file_id}"));
            }
        }
    }

    Ok(serde_json::json!({
        "screenshot": true,
        "url": url,
        "image_urls": image_urls,
    })
    .to_string())
}

/// browser_read_page: Read current page content as markdown.
pub async fn tool_browser_read_page(
    _input: &serde_json::Value,
    mgr: &BrowserManager,
    agent_id: &str,
) -> Result<String, String> {
    let resp = mgr.send_command(agent_id, BrowserCommand::ReadPage).await?;
    if !resp.success {
        return Err(resp.error.unwrap_or_else(|| "ReadPage failed".to_string()));
    }

    let data = resp.data.unwrap_or_default();
    let title = data["title"].as_str().unwrap_or("(no title)");
    let url = data["url"].as_str().unwrap_or("");
    let content = data["content"].as_str().unwrap_or("");
    let wrapped = crate::web_content::wrap_external_content(url, content);

    Ok(format!("Page: {title}\nURL: {url}\n\n{wrapped}"))
}

/// browser_close: Close the browser session.
pub async fn tool_browser_close(
    _input: &serde_json::Value,
    mgr: &BrowserManager,
    agent_id: &str,
) -> Result<String, String> {
    mgr.close_session(agent_id).await;
    Ok("Browser session closed.".to_string())
}

/// browser_scroll: Scroll the page in a direction.
pub async fn tool_browser_scroll(
    input: &serde_json::Value,
    mgr: &BrowserManager,
    agent_id: &str,
) -> Result<String, String> {
    let direction = input["direction"].as_str().unwrap_or("down").to_string();
    let amount = input["amount"].as_i64().unwrap_or(600) as i32;

    let resp = mgr
        .send_command(agent_id, BrowserCommand::Scroll { direction, amount })
        .await?;
    if !resp.success {
        return Err(resp.error.unwrap_or_else(|| "Scroll failed".to_string()));
    }
    let data = resp.data.unwrap_or_default();
    Ok(format!(
        "Scrolled. Position: scrollX={}, scrollY={}",
        data["scrollX"], data["scrollY"]
    ))
}

/// browser_wait: Wait for a CSS selector to appear on the page.
pub async fn tool_browser_wait(
    input: &serde_json::Value,
    mgr: &BrowserManager,
    agent_id: &str,
) -> Result<String, String> {
    let selector = input["selector"]
        .as_str()
        .ok_or("Missing 'selector' parameter")?;
    let timeout_ms = input["timeout_ms"].as_u64().unwrap_or(5000);

    let resp = mgr
        .send_command(
            agent_id,
            BrowserCommand::Wait {
                selector: selector.to_string(),
                timeout_ms,
            },
        )
        .await?;
    if !resp.success {
        return Err(resp.error.unwrap_or_else(|| "Wait timed out".to_string()));
    }
    Ok(format!("Element found: {selector}"))
}

/// browser_run_js: Run JavaScript on the current page.
pub async fn tool_browser_run_js(
    input: &serde_json::Value,
    mgr: &BrowserManager,
    agent_id: &str,
) -> Result<String, String> {
    let expression = input["expression"]
        .as_str()
        .ok_or("Missing 'expression' parameter")?;

    let resp = mgr
        .send_command(
            agent_id,
            BrowserCommand::RunJs {
                expression: expression.to_string(),
            },
        )
        .await?;
    if !resp.success {
        return Err(resp
            .error
            .unwrap_or_else(|| "JS execution failed".to_string()));
    }
    let data = resp.data.unwrap_or_default();
    Ok(serde_json::to_string_pretty(&data["result"]).unwrap_or_else(|_| "null".to_string()))
}

/// browser_back: Go back in browser history.
pub async fn tool_browser_back(
    _input: &serde_json::Value,
    mgr: &BrowserManager,
    agent_id: &str,
) -> Result<String, String> {
    let resp = mgr.send_command(agent_id, BrowserCommand::Back).await?;
    if !resp.success {
        return Err(resp.error.unwrap_or_else(|| "Back failed".to_string()));
    }
    let data = resp.data.unwrap_or_default();
    let title = data["title"].as_str().unwrap_or("(no title)");
    let url = data["url"].as_str().unwrap_or("");
    Ok(format!("Went back.\nPage: {title}\nURL: {url}"))
}

// ── Embedded JavaScript ────────────────────────────────────────────────────

/// JavaScript to extract readable page content as markdown.
const EXTRACT_CONTENT_JS: &str = r#"(() => {
    const title = document.title || '';
    const url = location.href || '';
    const body = document.body;
    if (!body) return JSON.stringify({title, url, content: ''});

    const clone = body.cloneNode(true);
    const remove = ['script','style','nav','footer','header','aside','iframe','noscript','svg','canvas'];
    remove.forEach(tag => clone.querySelectorAll(tag).forEach(el => el.remove()));

    let root = clone.querySelector('main, article, [role="main"], .content, #content');
    if (!root) root = clone;

    const lines = [];
    function walk(node) {
        if (node.nodeType === 3) {
            const t = node.textContent.trim();
            if (t) lines.push(t);
            return;
        }
        if (node.nodeType !== 1) return;
        const tag = node.tagName.toLowerCase();
        if (['h1','h2','h3','h4','h5','h6'].includes(tag)) {
            const level = '#'.repeat(parseInt(tag[1]));
            lines.push('\n' + level + ' ' + node.textContent.trim());
            return;
        }
        if (tag === 'a' && node.href && node.textContent.trim()) {
            lines.push('[' + node.textContent.trim() + '](' + node.href + ')');
            return;
        }
        if (tag === 'li') {
            lines.push('- ' + node.textContent.trim());
            return;
        }
        if (tag === 'br') { lines.push(''); return; }
        if (['p','div','section','tr'].includes(tag)) lines.push('');
        for (const child of node.childNodes) walk(child);
        if (['p','div','section','tr'].includes(tag)) lines.push('');
    }
    walk(root);

    let content = lines.join('\n').replace(/\n{3,}/g, '\n\n').trim();
    if (content.length > 50000) content = content.substring(0, 50000) + '\n... (truncated)';
    return JSON.stringify({title, url, content});
})()"#;

// ── Root detection ─────────────────────────────────────────────────────────

/// Returns true if the current process is running as root (UID 0).
///
/// On Linux, reads `/proc/self/status` to get the effective UID without
/// requiring a `libc` dependency. Falls back to checking the `HOME` env var
/// on systems where `/proc` is not available.
fn is_running_as_root() -> bool {
    #[cfg(unix)]
    {
        // Primary: read effective UID from /proc/self/status (Linux)
        if let Ok(status) = std::fs::read_to_string("/proc/self/status") {
            for line in status.lines() {
                if let Some(rest) = line.strip_prefix("Uid:") {
                    // Format: "Uid:	<real> <effective> <saved> <fs>"
                    if let Some(euid_str) = rest.split_whitespace().nth(1) {
                        return euid_str == "0";
                    }
                }
            }
        }
        // Fallback: HOME=/root is a reliable indicator on most Unix systems
        std::env::var("HOME").map(|h| h == "/root").unwrap_or(false)
    }
    #[cfg(not(unix))]
    {
        false
    }
}

// ── Tests ──────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn engines_default_order_and_parsing() {
        let c = BrowserConfig::default();
        assert_eq!(
            engine_order(&c),
            vec![Engine::Lightpanda, Engine::Obscura, Engine::Chromium]
        );
        let c = BrowserConfig {
            engines: vec![
                "Obscura".into(),
                "nope".into(),
                "obscura".into(),
                "chrome".into(),
            ],
            ..BrowserConfig::default()
        };
        assert_eq!(engine_order(&c), vec![Engine::Obscura, Engine::Chromium]);
        let c = BrowserConfig {
            engines: vec!["nothing".into()],
            ..BrowserConfig::default()
        };
        assert_eq!(engine_order(&c).len(), 3, "nothing usable = all three");
    }

    #[test]
    fn server_engines_start_on_loopback_with_their_options() {
        let c = BrowserConfig::default();
        let lp = server_args(&c, Engine::Lightpanda, 9333);
        assert_eq!(lp, vec!["serve", "--host", "127.0.0.1", "--port", "9333"]);
        let ob = server_args(&c, Engine::Obscura, 9334);
        assert_eq!(ob, vec!["serve", "--port", "9334", "--stealth"]);
        let c = BrowserConfig {
            obscura_stealth: false,
            obey_robots: true,
            ..BrowserConfig::default()
        };
        assert!(server_args(&c, Engine::Lightpanda, 1).contains(&"--obey-robots".to_string()));
        assert!(!server_args(&c, Engine::Obscura, 1).contains(&"--stealth".to_string()));
    }

    #[test]
    fn missing_configured_engine_says_where_it_looked() {
        let c = BrowserConfig {
            obscura_path: Some("/nonexistent/obscura".into()),
            ..BrowserConfig::default()
        };
        let e = find_engine_binary(&c, Engine::Obscura).unwrap_err();
        assert!(e.contains("/nonexistent/obscura"), "{e}");
    }

    #[test]
    fn block_walls_are_recognised_and_real_pages_are_not() {
        assert!(looks_blocked("Just a moment...", "").is_some());
        assert!(looks_blocked("Attention Required! | Cloudflare", "").is_some());
        assert!(looks_blocked("", "Access Denied. You don't have permission.").is_some());
        assert!(looks_blocked("Studio", "Please verify you are a human to continue").is_some());
        assert_eq!(
            looks_blocked("Fargo Tattoo", "Black and grey realism in Fargo."),
            None
        );
        // A real page that mentions reCAPTCHA in its footer is not a wall.
        let long = format!(
            "{} This site is protected by reCAPTCHA. access denied",
            "Portfolio. ".repeat(500)
        );
        assert_eq!(looks_blocked("Fargo Tattoo — Portfolio", &long), None);
    }

    #[test]
    fn engine_switch_rules() {
        let nav = BrowserCommand::Navigate {
            url: "https://x.example".into(),
        };
        let page = |t: &str, c: &str| {
            BrowserResponse::ok(
                serde_json::json!({"title": t, "url": "https://x.example", "content": c}),
            )
        };
        assert!(fallback_reason(&nav, &page("Just a moment...", ""), Engine::Lightpanda).is_some());
        assert!(fallback_reason(&nav, &page("Just a moment...", ""), Engine::Obscura).is_some());
        assert!(fallback_reason(&nav, &page("Home", ""), Engine::Lightpanda)
            .unwrap()
            .contains("empty"));
        assert_eq!(
            fallback_reason(&nav, &page("Home", ""), Engine::Obscura),
            None,
            "only Lightpanda's empty pages move on"
        );
        assert_eq!(
            fallback_reason(
                &nav,
                &page("Home", "A real page with words."),
                Engine::Lightpanda
            ),
            None
        );
        let lost = BrowserResponse::err("Navigate failed: CDP command timed out");
        assert!(fallback_reason(&nav, &lost, Engine::Obscura)
            .unwrap()
            .contains("stopped responding"));
        let shot = BrowserCommand::Screenshot;
        assert!(fallback_reason(
            &shot,
            &BrowserResponse::err("Screenshot failed: x"),
            Engine::Lightpanda
        )
        .is_some());
        assert_eq!(
            fallback_reason(
                &shot,
                &BrowserResponse::err("Screenshot failed: x"),
                Engine::Chromium
            ),
            None
        );
        let click = BrowserCommand::Click {
            selector: "#go".into(),
        };
        assert_eq!(
            fallback_reason(
                &click,
                &BrowserResponse::err("Element not found: #go"),
                Engine::Lightpanda
            ),
            None,
            "a missing button is not the engine's fault"
        );
    }

    /// End to end with stand-in engines: two wrappers around a local Chrome
    /// that start like Lightpanda/Obscura (`serve ... --port N`). A test site
    /// turns the first away with a bot wall and lets the second through.
    /// Runs only when BROWSER_ENGINE_TEST_CHROME points at a Chrome binary.
    #[tokio::test]
    async fn falls_back_to_the_next_engine_when_a_site_blocks() {
        let Ok(chrome) = std::env::var("BROWSER_ENGINE_TEST_CHROME") else {
            return;
        };
        let dir = std::env::temp_dir().join(format!("engines-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let wrapper = |name: &str, ua: &str| {
            let p = dir.join(name);
            std::fs::write(
                &p,
                format!(
                    "#!/bin/sh\nPORT=\nwhile [ $# -gt 0 ]; do [ \"$1\" = --port ] && PORT=$2; shift; done\nexec {chrome} --headless=new --no-sandbox --disable-gpu --user-data-dir={dir}/profile-{name} --remote-debugging-port=$PORT --user-agent='{ua}' about:blank\n",
                    dir = dir.display(),
                ),
            )
            .unwrap();
            use std::os::unix::fs::PermissionsExt;
            std::fs::set_permissions(&p, std::fs::Permissions::from_mode(0o755)).unwrap();
            p
        };
        let lp = wrapper("lightpanda", "TestEngine/plain");
        let ob = wrapper("obscura", "TestEngine/stealth");

        // The site: a bot wall for the plain engine, the studio for the other.
        let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        std::thread::spawn(move || {
            use std::io::{Read, Write};
            for stream in listener.incoming().flatten() {
                let mut stream = stream;
                let mut buf = [0u8; 4096];
                let n = stream.read(&mut buf).unwrap_or(0);
                let req = String::from_utf8_lossy(&buf[..n]).to_string();
                let body = if req.contains("TestEngine/stealth") {
                    "<html><head><title>Fargo Tattoo</title></head><body><main><h1>Fargo Tattoo</h1><p>Black and grey realism, portraits and cover-ups in Fargo.</p></main></body></html>"
                } else {
                    "<html><head><title>Just a moment...</title></head><body>Checking your browser before accessing the site.</body></html>"
                };
                let _ = write!(stream, "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}", body.len());
            }
        });

        let config = BrowserConfig {
            lightpanda_path: Some(lp.display().to_string()),
            obscura_path: Some(ob.display().to_string()),
            engines: vec!["lightpanda".into(), "obscura".into()],
            ..BrowserConfig::default()
        };
        let mgr = BrowserManager::new(config);
        let url = format!("http://127.0.0.1:{port}/");
        let resp = mgr
            .send_command("agent-1", BrowserCommand::Navigate { url: url.clone() })
            .await
            .unwrap();
        assert!(resp.success, "{:?}", resp.error);
        let d = resp.data.unwrap();
        assert_eq!(d["title"], "Fargo Tattoo", "{d}");
        assert_eq!(d["engine"], "Obscura");
        // Normally "looked blocked"; on a heavily loaded machine the first
        // stand-in can be too slow to answer, which is also a reason to move
        // on. Recognising block walls is pinned by its own unit test.
        let switched = d["switched"].as_str().unwrap();
        assert!(
            switched.contains("switched to Obscura")
                && (switched.contains("looked blocked") || switched.contains("stopped responding")),
            "{d}"
        );
        assert_eq!(mgr.engine_of("agent-1").await, Some(Engine::Obscura));
        // The session stays on the engine that got through.
        let read = mgr
            .send_command("agent-1", BrowserCommand::ReadPage)
            .await
            .unwrap();
        assert!(read.data.unwrap()["content"]
            .as_str()
            .unwrap()
            .contains("cover-ups"));

        mgr.close_session("agent-1").await;
        tokio::time::sleep(Duration::from_millis(500)).await;

        // An engine that isn't installed is skipped at start.
        let config = BrowserConfig {
            lightpanda_path: Some("/nonexistent/lightpanda".into()),
            obscura_path: Some(ob.display().to_string()),
            engines: vec!["lightpanda".into(), "obscura".into()],
            ..BrowserConfig::default()
        };
        let mgr2 = BrowserManager::new(config);
        let resp = mgr2
            .send_command("agent-2", BrowserCommand::Navigate { url })
            .await
            .unwrap();
        assert_eq!(resp.data.unwrap()["engine"], "Obscura");
        mgr2.close_session("agent-2").await;
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_browser_config_defaults() {
        let config = BrowserConfig::default();
        assert!(config.headless);
        assert_eq!(config.viewport_width, 1280);
        assert_eq!(config.viewport_height, 720);
        assert_eq!(config.timeout_secs, 30);
        assert_eq!(config.idle_timeout_secs, 300);
        assert_eq!(config.max_sessions, 5);
        assert!(config.chromium_path.is_none());
    }

    #[test]
    fn test_browser_command_serialize_navigate() {
        let cmd = BrowserCommand::Navigate {
            url: "https://example.com".to_string(),
        };
        let json = serde_json::to_string(&cmd).unwrap();
        assert!(json.contains("\"action\":\"Navigate\""));
        assert!(json.contains("\"url\":\"https://example.com\""));
    }

    #[test]
    fn test_browser_command_serialize_click() {
        let cmd = BrowserCommand::Click {
            selector: "#submit-btn".to_string(),
        };
        let json = serde_json::to_string(&cmd).unwrap();
        assert!(json.contains("\"action\":\"Click\""));
        assert!(json.contains("\"selector\":\"#submit-btn\""));
    }

    #[test]
    fn test_browser_command_serialize_type() {
        let cmd = BrowserCommand::Type {
            selector: "input[name='email']".to_string(),
            text: "test@example.com".to_string(),
        };
        let json = serde_json::to_string(&cmd).unwrap();
        assert!(json.contains("\"action\":\"Type\""));
        assert!(json.contains("test@example.com"));
    }

    #[test]
    fn test_browser_command_serialize_screenshot() {
        let cmd = BrowserCommand::Screenshot;
        let json = serde_json::to_string(&cmd).unwrap();
        assert!(json.contains("\"action\":\"Screenshot\""));
    }

    #[test]
    fn test_browser_command_serialize_read_page() {
        let cmd = BrowserCommand::ReadPage;
        let json = serde_json::to_string(&cmd).unwrap();
        assert!(json.contains("\"action\":\"ReadPage\""));
    }

    #[test]
    fn test_browser_command_serialize_close() {
        let cmd = BrowserCommand::Close;
        let json = serde_json::to_string(&cmd).unwrap();
        assert!(json.contains("\"action\":\"Close\""));
    }

    #[test]
    fn test_browser_command_serialize_scroll() {
        let cmd = BrowserCommand::Scroll {
            direction: "down".to_string(),
            amount: 500,
        };
        let json = serde_json::to_string(&cmd).unwrap();
        assert!(json.contains("\"action\":\"Scroll\""));
        assert!(json.contains("\"amount\":500"));
    }

    #[test]
    fn test_browser_command_serialize_run_js() {
        let cmd = BrowserCommand::RunJs {
            expression: "document.title".to_string(),
        };
        let json = serde_json::to_string(&cmd).unwrap();
        assert!(json.contains("\"action\":\"RunJs\""));
    }

    #[test]
    fn test_browser_command_serialize_back() {
        let cmd = BrowserCommand::Back;
        let json = serde_json::to_string(&cmd).unwrap();
        assert!(json.contains("\"action\":\"Back\""));
    }

    #[test]
    fn test_browser_command_serialize_wait() {
        let cmd = BrowserCommand::Wait {
            selector: "#loaded".to_string(),
            timeout_ms: 3000,
        };
        let json = serde_json::to_string(&cmd).unwrap();
        assert!(json.contains("\"action\":\"Wait\""));
        assert!(json.contains("\"timeout_ms\":3000"));
    }

    #[test]
    fn test_browser_response_deserialize() {
        let json =
            r#"{"success": true, "data": {"title": "Example", "url": "https://example.com"}}"#;
        let resp: BrowserResponse = serde_json::from_str(json).unwrap();
        assert!(resp.success);
        assert!(resp.data.is_some());
        assert!(resp.error.is_none());
        let data = resp.data.unwrap();
        assert_eq!(data["title"], "Example");
    }

    #[test]
    fn test_browser_response_error_deserialize() {
        let json = r#"{"success": false, "error": "Element not found"}"#;
        let resp: BrowserResponse = serde_json::from_str(json).unwrap();
        assert!(!resp.success);
        assert!(resp.data.is_none());
        assert_eq!(resp.error.unwrap(), "Element not found");
    }

    #[test]
    fn test_browser_manager_new() {
        let config = BrowserConfig::default();
        let mgr = BrowserManager::new(config);
        assert!(mgr.sessions.is_empty());
    }

    #[test]
    fn test_is_running_as_root_returns_bool() {
        // Just verify it doesn't panic and returns a bool.
        let _ = is_running_as_root();
    }

    #[test]
    fn test_chromium_candidates_not_empty() {
        let paths = chromium_candidates();
        assert!(
            !paths.is_empty(),
            "Should have platform-specific candidates"
        );
    }

    #[test]
    fn test_response_helpers() {
        let ok = BrowserResponse::ok(serde_json::json!({"a": 1}));
        assert!(ok.success);
        assert!(ok.error.is_none());

        let err = BrowserResponse::err("bad");
        assert!(!err.success);
        assert_eq!(err.error.unwrap(), "bad");
    }
}
