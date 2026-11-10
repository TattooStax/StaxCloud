//! Production middleware for the OpenFang API server.
//!
//! Provides:
//! - Request ID generation and propagation
//! - Per-endpoint structured request logging
//! - In-memory rate limiting (per IP)

use axum::body::Body;
use axum::http::{Request, Response, StatusCode};
use axum::middleware::Next;
use std::time::Instant;
use tracing::info;

/// Request ID header name (standard).
pub const REQUEST_ID_HEADER: &str = "x-request-id";

/// Middleware: inject a unique request ID and log the request/response.
pub async fn request_logging(request: Request<Body>, next: Next) -> Response<Body> {
    let request_id = uuid::Uuid::new_v4().to_string();
    let method = request.method().clone();
    let uri = request.uri().path().to_string();
    let start = Instant::now();

    let mut response = next.run(request).await;

    let elapsed = start.elapsed();
    let status = response.status().as_u16();

    info!(
        request_id = %request_id,
        method = %method,
        path = %uri,
        status = status,
        latency_ms = elapsed.as_millis() as u64,
        "API request"
    );

    // Inject the request ID into the response
    if let Ok(header_val) = request_id.parse() {
        response.headers_mut().insert(REQUEST_ID_HEADER, header_val);
    }

    response
}

/// Authentication state passed to the auth middleware.
#[derive(Clone)]
pub struct AuthState {
    pub api_key: String,
    pub auth_enabled: bool,
    pub session_secret: String,
    /// Set from `OPENFANG_ALLOW_NO_AUTH=1` to permit running without an api_key
    /// on a non-loopback bind. Off by default so empty keys fail closed.
    pub allow_no_auth: bool,
    /// Set from `OPENFANG_LEGACY_PUBLIC_READS=1` to restore upstream's
    /// unauthenticated dashboard reads (approvals, sessions, logs, config…).
    /// Off by default: on an internet-facing box those reads expose
    /// customer data to anyone with the address.
    pub legacy_public_reads: bool,
}

/// Paths anyone may reach without signing in: the login page and its
/// assets, the login endpoints themselves, liveness, A2A discovery, and
/// uploaded files (served by unguessable UUID).
pub fn is_always_public(path: &str, is_get: bool) -> bool {
    path == "/"
        || path == "/logo.png"
        || path == "/favicon.ico"
        || path == "/manifest.json"
        || path == "/sw.js"
        || (path == "/.well-known/agent.json" && is_get)
        || (path.starts_with("/a2a/") && is_get)
        || path == "/api/health"
        || path == "/api/version"
        || (path.starts_with("/api/uploads/") && is_get)
        || path.starts_with("/api/providers/github-copilot/oauth/")
        || path == "/api/auth/login"
        || path == "/api/auth/logout"
        || (path == "/api/auth/check" && is_get)
}

/// Upstream's unauthenticated dashboard reads, so its SPA could render
/// before a key was entered. Only public when `legacy_public_reads` is on.
pub fn is_legacy_dashboard_read(path: &str, is_get: bool) -> bool {
    path == "/api/health/detail"
        || path == "/api/status"
        || (path == "/api/agents" && is_get)
        || (path == "/api/profiles" && is_get)
        || (path == "/api/config" && is_get)
        || (path == "/api/config/schema" && is_get)
        || (path == "/api/models" && is_get)
        || (path == "/api/models/aliases" && is_get)
        || (path == "/api/providers" && is_get)
        || (path == "/api/budget" && is_get)
        || (path == "/api/budget/agents" && is_get)
        || (path.starts_with("/api/budget/agents/") && is_get)
        || (path == "/api/network/status" && is_get)
        || (path == "/api/a2a/agents" && is_get)
        || (path == "/api/approvals" && is_get)
        || (path.starts_with("/api/approvals/") && is_get)
        || (path == "/api/channels" && is_get)
        || (path == "/api/hands" && is_get)
        || (path == "/api/hands/active" && is_get)
        || (path.starts_with("/api/hands/") && is_get)
        || (path == "/api/skills" && is_get)
        || (path.starts_with("/api/skills/") && path.ends_with("/config") && is_get)
        || (path == "/api/sessions" && is_get)
        || (path == "/api/integrations" && is_get)
        || (path == "/api/integrations/available" && is_get)
        || (path == "/api/integrations/health" && is_get)
        || (path == "/api/workflows" && is_get)
        || path == "/api/logs/stream"
        || (path.starts_with("/api/cron/") && is_get)
}

/// The authenticated principal class of a request, stamped by the
/// auth middleware from *how the request authenticated* — never from
/// anything the caller asserts (Work build §3, Consult 12 Q3).
/// Decision handlers read it from the request extensions to stamp
/// `decided_via` on approval records; grant creation and the send
/// gate honor `OwnerSession` decisions only.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum AuthClass {
    /// The dashboard's password-login session (HMAC session cookie),
    /// carrying the session's username.
    OwnerSession(String),
    /// The shared API key (Bearer, X-API-Key, or ?token=) — carriers,
    /// sidecars, and external callers.
    ApiToken,
    /// No credential class: public reads, loopback pass-through, or
    /// an explicitly unauthenticated local setup.
    System,
}

/// Bearer token authentication middleware.
///
/// When `api_key` is non-empty (after trimming), requests to non-public
/// endpoints must include `Authorization: Bearer <api_key>`.
///
/// When `api_key` is empty (no key configured) the server defaults to
/// fail-closed for any request that does NOT originate from loopback.
/// Loopback traffic (127.0.0.1 / ::1) is always allowed through with no
/// key so single-user local setups keep zero-config UX. To explicitly
/// run a no-auth server on a LAN/WAN address, set
/// `OPENFANG_ALLOW_NO_AUTH=1`; this opts out of fail-closed and is
/// reported loudly at startup.
///
/// When dashboard auth is enabled, session cookies are also accepted.
pub async fn auth(
    axum::extract::State(auth_state): axum::extract::State<AuthState>,
    mut request: Request<Body>,
    next: Next,
) -> Response<Body> {
    // SECURITY: Capture method early for method-aware public endpoint checks.
    let method = request.method().clone();

    let is_loopback = request
        .extensions()
        .get::<axum::extract::ConnectInfo<std::net::SocketAddr>>()
        .map(|ci| ci.0.ip().is_loopback())
        .unwrap_or(false); // SECURITY: default-deny; unknown origin is NOT loopback

    // Shutdown is loopback-only (CLI on same machine). Skip token auth only
    // when the request is from loopback.
    let path = request.uri().path();
    if path == "/api/shutdown" && is_loopback {
        request.extensions_mut().insert(AuthClass::System);
        return next.run(request).await;
    }

    // Public endpoints that don't require auth. POST/PUT/DELETE to any
    // other endpoint ALWAYS requires auth. Upstream also left most dashboard
    // reads open (approvals, sessions, logs, config…); on a box reachable
    // from the internet that publishes customer data, so those are behind
    // sign-in unless OPENFANG_LEGACY_PUBLIC_READS=1.
    let is_get = method == axum::http::Method::GET;
    let is_public = is_always_public(path, is_get)
        || crate::stax_forms::is_public_form_path(path, &method)
        || (auth_state.legacy_public_reads && is_legacy_dashboard_read(path, is_get));

    if is_public {
        request.extensions_mut().insert(AuthClass::System);
        return next.run(request).await;
    }

    // If no API key configured and no dashboard login is active, fail closed
    // for anything that did not come from loopback. Opting out of this
    // behavior requires setting `OPENFANG_ALLOW_NO_AUTH=1`, which is logged
    // loudly at startup.
    //
    // See issue #1034 (B1/B2): empty api_key previously bypassed auth for
    // all origins, exposing agent config, channel tokens, and LLM keys on
    // any LAN-reachable bind.
    let api_key_trimmed = auth_state.api_key.trim().to_string();
    if api_key_trimmed.is_empty() && !auth_state.auth_enabled {
        if is_loopback || auth_state.allow_no_auth {
            request.extensions_mut().insert(AuthClass::System);
            return next.run(request).await;
        }
        return Response::builder()
            .status(StatusCode::UNAUTHORIZED)
            .header("www-authenticate", "Bearer")
            .body(Body::from(
                serde_json::json!({
                    "error": "API key required for non-loopback requests. Set OPENFANG_API_KEY or bind to 127.0.0.1."
                })
                .to_string(),
            ))
            .unwrap_or_default();
    }
    let api_key = api_key_trimmed.as_str();

    // Check Authorization: Bearer <token> header, then fallback to X-API-Key
    let bearer_token = request
        .headers()
        .get("authorization")
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "));

    let api_token = bearer_token.or_else(|| {
        request
            .headers()
            .get("x-api-key")
            .and_then(|v| v.to_str().ok())
    });

    // SECURITY: Use constant-time comparison to prevent timing attacks.
    let header_auth = api_token.map(|token| {
        use subtle::ConstantTimeEq;
        if token.len() != api_key.len() {
            return false;
        }
        token.as_bytes().ct_eq(api_key.as_bytes()).into()
    });

    // Also check ?token= query parameter (for EventSource/SSE clients that
    // cannot set custom headers, same approach as WebSocket auth).
    let query_token_decoded = request
        .uri()
        .query()
        .and_then(|q| q.split('&').find_map(|pair| pair.strip_prefix("token=")))
        .map(crate::percent_decode);

    // SECURITY: Use constant-time comparison to prevent timing attacks.
    let query_auth = query_token_decoded.as_deref().map(|token| {
        use subtle::ConstantTimeEq;
        if token.len() != api_key.len() {
            return false;
        }
        token.as_bytes().ct_eq(api_key.as_bytes()).into()
    });

    // Session cookie (dashboard login) is checked FIRST for class
    // attribution: a valid session token is HMAC-signed and issued
    // only by the password login, so a request carrying one is the
    // owner's dashboard session even if the browser also presents a
    // saved API key. Either credential alone still suffices to pass;
    // the cookie merely decides the class when both are present.
    if auth_state.auth_enabled {
        if let Some(token) = crate::session_auth::extract_session_cookie(request.headers()) {
            if let Some(username) =
                crate::session_auth::verify_session_token(&token, &auth_state.session_secret)
            {
                request
                    .extensions_mut()
                    .insert(AuthClass::OwnerSession(username));
                return next.run(request).await;
            }
        }
    }

    // Accept if either API-key method matches
    if header_auth == Some(true) || query_auth == Some(true) {
        request.extensions_mut().insert(AuthClass::ApiToken);
        return next.run(request).await;
    }

    // Determine error message: was a credential provided but wrong, or missing entirely?
    let credential_provided = header_auth.is_some() || query_auth.is_some();
    let error_msg = if credential_provided {
        "Invalid API key"
    } else {
        "Missing Authorization: Bearer <api_key> header"
    };

    Response::builder()
        .status(StatusCode::UNAUTHORIZED)
        .header("www-authenticate", "Bearer")
        .body(Body::from(
            serde_json::json!({"error": error_msg}).to_string(),
        ))
        .unwrap_or_default()
}

/// Security headers middleware — applied to ALL API responses.
pub async fn security_headers(request: Request<Body>, next: Next) -> Response<Body> {
    let mut response = next.run(request).await;
    let headers = response.headers_mut();
    headers.insert("x-content-type-options", "nosniff".parse().unwrap());
    headers.insert("x-frame-options", "DENY".parse().unwrap());
    headers.insert("x-xss-protection", "1; mode=block".parse().unwrap());
    // The dashboard handler (webchat_page) sets its own nonce-based CSP.
    // For all other responses (API endpoints), apply a strict default.
    if !headers.contains_key("content-security-policy") {
        headers.insert(
            "content-security-policy",
            "default-src 'none'; frame-ancestors 'none'"
                .parse()
                .unwrap(),
        );
    }
    headers.insert(
        "referrer-policy",
        "strict-origin-when-cross-origin".parse().unwrap(),
    );
    headers.insert(
        "cache-control",
        "no-store, no-cache, must-revalidate".parse().unwrap(),
    );
    headers.insert(
        "strict-transport-security",
        "max-age=63072000; includeSubDomains".parse().unwrap(),
    );
    response
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::body::Body;
    use axum::extract::ConnectInfo;
    use axum::http::{Method, Request};
    use axum::routing::get;
    use axum::Router;
    use std::net::SocketAddr;
    use tower::ServiceExt;

    #[test]
    fn test_request_id_header_constant() {
        assert_eq!(REQUEST_ID_HEADER, "x-request-id");
    }

    fn auth_state_empty() -> AuthState {
        AuthState {
            api_key: String::new(),
            auth_enabled: false,
            session_secret: String::new(),
            allow_no_auth: false,
            legacy_public_reads: false,
        }
    }

    fn auth_state_with_key(key: &str) -> AuthState {
        AuthState {
            api_key: key.to_string(),
            auth_enabled: false,
            session_secret: key.to_string(),
            allow_no_auth: false,
            legacy_public_reads: false,
        }
    }

    async fn ok_handler() -> &'static str {
        "ok"
    }

    fn router(state: AuthState) -> Router {
        Router::new()
            .route("/api/agents/1", get(ok_handler))
            .route_layer(axum::middleware::from_fn_with_state(state, auth))
    }

    fn req_from(ip: &str) -> Request<Body> {
        let addr: SocketAddr = format!("{ip}:40000").parse().unwrap();
        let mut req = Request::builder()
            .method(Method::GET)
            .uri("/api/agents/1")
            .body(Body::empty())
            .unwrap();
        req.extensions_mut().insert(ConnectInfo(addr));
        req
    }

    fn get_from(ip: &str, path: &str) -> Request<Body> {
        let addr: SocketAddr = format!("{ip}:40000").parse().unwrap();
        let mut req = Request::builder()
            .method(Method::GET)
            .uri(path)
            .body(Body::empty())
            .unwrap();
        req.extensions_mut().insert(ConnectInfo(addr));
        req
    }

    fn dashboard_router(state: AuthState) -> Router {
        let mut r = Router::new();
        for p in [
            "/api/approvals",
            "/api/sessions",
            "/api/logs/stream",
            "/api/budget",
            "/api/config",
            "/api/health",
            "/api/auth/check",
        ] {
            r = r.route(p, get(ok_handler));
        }
        r.route_layer(axum::middleware::from_fn_with_state(state, auth))
    }

    #[tokio::test]
    async fn customer_data_reads_need_sign_in() {
        for path in [
            "/api/approvals",
            "/api/sessions",
            "/api/logs/stream",
            "/api/budget",
            "/api/config",
        ] {
            let app = dashboard_router(auth_state_with_key("k"));
            let resp = app.oneshot(get_from("203.0.113.5", path)).await.unwrap();
            assert_eq!(resp.status(), StatusCode::UNAUTHORIZED, "{path}");
        }
    }

    #[tokio::test]
    async fn login_and_health_stay_public() {
        for path in ["/api/health", "/api/auth/check"] {
            let app = dashboard_router(auth_state_with_key("k"));
            let resp = app.oneshot(get_from("203.0.113.5", path)).await.unwrap();
            assert_eq!(resp.status(), StatusCode::OK, "{path}");
        }
    }

    #[tokio::test]
    async fn legacy_switch_restores_dashboard_reads() {
        let mut s = auth_state_with_key("k");
        s.legacy_public_reads = true;
        let app = dashboard_router(s);
        let resp = app
            .oneshot(get_from("203.0.113.5", "/api/approvals"))
            .await
            .unwrap();
        assert_eq!(resp.status(), StatusCode::OK);
    }

    #[test]
    fn public_lists_do_not_overlap_on_customer_data() {
        for p in [
            "/api/approvals",
            "/api/sessions",
            "/api/logs/stream",
            "/api/config",
        ] {
            assert!(!is_always_public(p, true), "{p}");
            assert!(is_legacy_dashboard_read(p, true), "{p}");
        }
    }

    #[tokio::test]
    async fn empty_key_allows_loopback() {
        let app = router(auth_state_empty());
        let resp = app.oneshot(req_from("127.0.0.1")).await.unwrap();
        assert_eq!(resp.status(), StatusCode::OK);
    }

    #[tokio::test]
    async fn empty_key_blocks_lan_origin() {
        // Issue #1034 B1: previously 192.168/10/... could hit every non-public
        // endpoint when api_key was unset. Must now be 401.
        let app = router(auth_state_empty());
        let resp = app.oneshot(req_from("192.168.1.50")).await.unwrap();
        assert_eq!(resp.status(), StatusCode::UNAUTHORIZED);
    }

    #[tokio::test]
    async fn empty_key_blocks_public_origin() {
        let app = router(auth_state_empty());
        let resp = app.oneshot(req_from("203.0.113.5")).await.unwrap();
        assert_eq!(resp.status(), StatusCode::UNAUTHORIZED);
    }

    #[tokio::test]
    async fn empty_key_blocks_unknown_connect_info() {
        // Paranoia: if ConnectInfo is missing for any reason, we must fail
        // closed, not open.
        let app = router(auth_state_empty());
        let req = Request::builder()
            .method(Method::GET)
            .uri("/api/agents/1")
            .body(Body::empty())
            .unwrap();
        let resp = app.oneshot(req).await.unwrap();
        assert_eq!(resp.status(), StatusCode::UNAUTHORIZED);
    }

    #[tokio::test]
    async fn empty_key_with_allow_no_auth_opens_everything() {
        let mut s = auth_state_empty();
        s.allow_no_auth = true;
        let app = router(s);
        let resp = app.oneshot(req_from("10.0.0.9")).await.unwrap();
        assert_eq!(resp.status(), StatusCode::OK);
    }

    #[tokio::test]
    async fn configured_key_rejects_missing_token_from_loopback() {
        let app = router(auth_state_with_key("secret"));
        let resp = app.oneshot(req_from("127.0.0.1")).await.unwrap();
        assert_eq!(resp.status(), StatusCode::UNAUTHORIZED);
    }

    #[tokio::test]
    async fn configured_key_accepts_bearer() {
        let app = router(auth_state_with_key("secret"));
        let addr: SocketAddr = "127.0.0.1:40000".parse().unwrap();
        let mut req = Request::builder()
            .method(Method::GET)
            .uri("/api/agents/1")
            .header("authorization", "Bearer secret")
            .body(Body::empty())
            .unwrap();
        req.extensions_mut().insert(ConnectInfo(addr));
        let resp = app.oneshot(req).await.unwrap();
        assert_eq!(resp.status(), StatusCode::OK);
    }
}
