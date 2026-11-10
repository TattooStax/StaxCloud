//! Hosted forms — the studio's published forms, served by the daemon itself.
//!
//! A form definition lives in the shared records at `form/<slug>`. When its
//! `published` flag is on, anyone with the link can open and send it:
//!
//! - `GET  /f/<slug>`         the form page
//! - `GET  /f/<slug>/def`     the form's fields (published forms only)
//! - `POST /f/<slug>/upload`  one picture (a reference photo or a drawn signature)
//! - `POST /f/<slug>`         the filled-in form
//!
//! A submission is stored at `formsub/<slug>/<uuid>` — the same record the
//! Forms surface, Contacts and the Forms helper already read — and the sender
//! is matched to (or added as) a contact right here, deterministically, so a
//! form always lands on the right person's card without waiting on a model.
//! The Forms helper is then woken with the exact key to draft a reply for the
//! owner's OK.
//!
//! These routes are public by design, so every input is bounded: only
//! published forms answer, only keys the form owns are kept, values are size
//! capped, uploads must be real pictures, and sends are rate limited per
//! sender and overall.

use crate::routes::AppState;
use axum::body::Bytes;
use axum::extract::{ConnectInfo, Path, State};
use axum::http::{header, HeaderMap, StatusCode};
use axum::response::IntoResponse;
use axum::Json;
use openfang_runtime::kernel_handle::KernelHandle;
use serde_json::{json, Value};
use std::collections::{HashMap, VecDeque};
use std::net::SocketAddr;
use std::sync::{Arc, Mutex, OnceLock};
use std::time::{Duration, Instant};

const FORMS_JS: &str = include_str!("../static/js/pages/forms.js");
const PAGE_HTML: &str = include_str!("../static/form_public.html");

/// Largest submission body accepted.
pub const MAX_SUBMIT_BYTES: usize = 256 * 1024;
/// Largest picture accepted by the upload route.
pub const MAX_UPLOAD_BYTES: usize = 8 * 1024 * 1024;
const MAX_KEYS: usize = 400;
const MAX_TEXT_CHARS: usize = 20_000;
const MAX_LIST_ITEMS: usize = 100;

const SENDS_PER_SENDER: usize = 8;
const UPLOADS_PER_SENDER: usize = 40;
const SENDS_OVERALL: usize = 240;
const WINDOW: Duration = Duration::from_secs(600);
const OVERALL_WINDOW: Duration = Duration::from_secs(3600);

// ---------------------------------------------------------------------------
// Pure helpers
// ---------------------------------------------------------------------------

/// The field helpers the dashboard's Forms preview uses, shared with the
/// hosted page so both render and validate a form the same way.
pub fn shared_helpers() -> &'static str {
    static CELL: OnceLock<String> = OnceLock::new();
    CELL.get_or_init(|| {
        let start = FORMS_JS.find("/*PURE-BEGIN pvforms*/").unwrap_or(0);
        let end = FORMS_JS
            .find("/*PURE-END pvforms*/")
            .unwrap_or(FORMS_JS.len());
        FORMS_JS[start..end].to_string()
    })
}

/// A form slug: lowercase letters, digits and dashes, 1–64 long.
pub fn valid_slug(slug: &str) -> bool {
    !slug.is_empty()
        && slug.len() <= 64
        && slug
            .chars()
            .all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == '-' || c == '_')
}

/// The form's field keys.
pub fn field_keys(def: &Value) -> Vec<String> {
    def["fields"]
        .as_array()
        .map(|fs| {
            fs.iter()
                .filter_map(|f| f["key"].as_str())
                .filter(|k| !k.is_empty())
                .map(String::from)
                .collect()
        })
        .unwrap_or_default()
}

/// Whether an answer key belongs to one of the form's fields: the field's
/// own key, or a sub-answer `<key>_<suffix>`.
pub fn key_owned(key: &str, fields: &[String]) -> bool {
    fields.iter().any(|f| {
        key == f
            || (key.len() > f.len() + 1
                && key.starts_with(f.as_str())
                && key.as_bytes()[f.len()] == b'_')
    })
}

fn upload_ref_ok(v: &Value) -> bool {
    // {"signature": true, "file_id": "<uuid>"} or {"url": "/api/uploads/<uuid>", "name": "..."}
    let Some(o) = v.as_object() else { return false };
    if o.get("signature") == Some(&Value::Bool(true)) {
        return o.len() == 2
            && o.get("file_id")
                .and_then(|x| x.as_str())
                .is_some_and(|id| uuid::Uuid::parse_str(id).is_ok());
    }
    let url_ok = o
        .get("url")
        .and_then(|x| x.as_str())
        .and_then(|u| u.strip_prefix("/api/uploads/"))
        .is_some_and(|id| uuid::Uuid::parse_str(id).is_ok());
    let name_ok = o
        .get("name")
        .is_none_or(|n| n.as_str().is_some_and(|s| s.chars().count() <= 200));
    url_ok && name_ok && o.len() <= 2
}

fn value_ok(v: &Value) -> bool {
    match v {
        Value::Null | Value::Bool(_) | Value::Number(_) => true,
        Value::String(s) => s.chars().count() <= MAX_TEXT_CHARS,
        Value::Array(items) => {
            items.len() <= MAX_LIST_ITEMS
                && items.iter().all(|it| match it {
                    Value::String(s) => s.chars().count() <= 1000,
                    Value::Object(_) => upload_ref_ok(it),
                    _ => false,
                })
        }
        Value::Object(_) => upload_ref_ok(v),
    }
}

/// Keep only answers the form owns, refusing shapes a form never sends.
/// Returns the cleaned answers, or a plain reason.
pub fn clean_answers(data: &Value, def: &Value) -> Result<serde_json::Map<String, Value>, String> {
    let obj = data.as_object().ok_or("The form's answers were missing.")?;
    if obj.len() > MAX_KEYS {
        return Err("That form has too many answers.".into());
    }
    let fields = field_keys(def);
    let mut out = serde_json::Map::new();
    for (k, v) in obj {
        if !key_owned(k, &fields) {
            continue; // not this form's field: dropped, never stored
        }
        if !value_ok(v) {
            return Err("One of the answers is too long or not in a shape this form sends.".into());
        }
        out.insert(k.clone(), v.clone());
    }
    let has_content = out.values().any(|v| match v {
        Value::String(s) => !s.trim().is_empty(),
        Value::Array(a) => !a.is_empty(),
        Value::Bool(b) => *b,
        Value::Null => false,
        _ => true,
    });
    if !has_content {
        return Err("The form was empty.".into());
    }
    Ok(out)
}

/// Phone digits the way the contact index keys them: digits only, US
/// country code dropped.
pub fn phone_digits(raw: &str) -> String {
    let mut d: String = raw.chars().filter(|c| c.is_ascii_digit()).collect();
    if d.len() == 11 && d.starts_with('1') {
        d.remove(0);
    }
    d
}

fn looks_like_email(s: &str) -> bool {
    let s = s.trim();
    let Some((local, domain)) = s.split_once('@') else {
        return false;
    };
    !local.is_empty()
        && domain.contains('.')
        && !domain.starts_with('.')
        && !domain.ends_with('.')
        && s.len() <= 254
        && !s.chars().any(|c| c.is_whitespace() || c == '/')
}

/// Who sent a form, read from its answers.
#[derive(Debug, Default, Clone, PartialEq)]
pub struct Sender {
    pub name: String,
    pub email: String,
    pub phone: String,
}

/// Find the sender's name, email and phone in a submission, going by the
/// form's own fields first (a Name/Email/Phone block, or the client-info and
/// booking blocks' sub-answers), then by answer keys that plainly say so.
/// Emergency-contact, parent and minor answers are never the sender.
pub fn find_sender(def: &Value, data: &serde_json::Map<String, Value>) -> Sender {
    let text = |k: &str| {
        data.get(k)
            .and_then(|v| v.as_str())
            .map(|s| s.trim().to_string())
            .filter(|s| !s.is_empty())
    };
    let mut s = Sender::default();
    let set = |slot: &mut String, v: Option<String>| {
        if slot.is_empty() {
            if let Some(v) = v {
                *slot = v;
            }
        }
    };
    for f in def["fields"]
        .as_array()
        .map(|a| a.as_slice())
        .unwrap_or(&[])
    {
        let (Some(key), stype, ftype) = (
            f["key"].as_str(),
            f["stype"].as_str().unwrap_or(""),
            f["type"].as_str().unwrap_or(""),
        ) else {
            continue;
        };
        match stype {
            "field-email" => set(&mut s.email, text(key)),
            "field-phone" => set(&mut s.phone, text(key)),
            "field-name" => set(&mut s.name, text(key)),
            "consent-client-info" | "booking-form" | "booking-gate" => {
                set(&mut s.name, text(&format!("{key}_name")));
                set(&mut s.email, text(&format!("{key}_email")));
                set(&mut s.phone, text(&format!("{key}_phone")));
            }
            _ => match ftype {
                "email" => set(&mut s.email, text(key)),
                "phone" => set(&mut s.phone, text(key)),
                _ if key == "name" => set(&mut s.name, text(key)),
                _ => {}
            },
        }
    }
    let other_person = |k: &str| {
        let k = k.to_lowercase();
        ["emergency", "parent", "minor", "guardian", "typed"]
            .iter()
            .any(|w| k.contains(w))
    };
    for (k, v) in data {
        let Some(v) = v.as_str().map(str::trim).filter(|v| !v.is_empty()) else {
            continue;
        };
        if other_person(k) {
            continue;
        }
        let kl = k.to_lowercase();
        if s.email.is_empty() && kl.ends_with("email") {
            s.email = v.to_string();
        } else if s.phone.is_empty() && kl.ends_with("phone") {
            s.phone = v.to_string();
        } else if s.name.is_empty() && (kl == "name" || kl.ends_with("_name")) {
            s.name = v.to_string();
        }
    }
    if !looks_like_email(&s.email) {
        s.email.clear();
    } else {
        s.email = s.email.to_lowercase();
    }
    if phone_digits(&s.phone).len() < 7 {
        s.phone.clear();
    }
    s
}

/// The contact index keys a sender can live under, best first.
pub fn contact_keys(s: &Sender) -> Vec<String> {
    let mut keys = Vec::new();
    if !s.email.is_empty() {
        keys.push(format!("contact/{}", s.email));
    }
    let d = phone_digits(&s.phone);
    if !d.is_empty() {
        keys.push(format!("contact/{d}"));
    }
    keys
}

/// The contact record after this submission: a returning person keeps every
/// field they had (notes, kind, stage, artist…) and gains a visit; a new
/// person gets the index record the Forms helper has always written.
pub fn contact_after(existing: Option<&Value>, s: &Sender, slug: &str, ts: &str) -> Value {
    match existing.and_then(|v| v.as_object()) {
        Some(old) => {
            let mut rec = old.clone();
            let visits = rec.get("visits").and_then(|v| v.as_u64()).unwrap_or(0) + 1;
            rec.insert("visits".into(), json!(visits));
            rec.insert("last_seen".into(), json!(ts));
            for (field, val) in [("name", &s.name), ("email", &s.email), ("phone", &s.phone)] {
                let empty = rec
                    .get(field)
                    .and_then(|v| v.as_str())
                    .is_none_or(|v| v.trim().is_empty());
                if empty && !val.is_empty() {
                    rec.insert(field.into(), json!(val));
                }
            }
            Value::Object(rec)
        }
        None => json!({
            "name": s.name,
            "email": s.email,
            "phone": s.phone,
            "source_form": slug,
            "first_seen": ts,
            "last_seen": ts,
            "visits": 1,
            "notes": [],
        }),
    }
}

// ---------------------------------------------------------------------------
// Rate limiting
// ---------------------------------------------------------------------------

#[derive(Default)]
struct Limiter {
    per_sender: HashMap<String, VecDeque<Instant>>,
    overall: VecDeque<Instant>,
}

fn limiter() -> &'static Mutex<Limiter> {
    static L: OnceLock<Mutex<Limiter>> = OnceLock::new();
    L.get_or_init(|| Mutex::new(Limiter::default()))
}

/// Count one action for `who` and say whether it is within `cap` per window.
fn allow(who: &str, bucket: &str, cap: usize, count_overall: bool) -> bool {
    let now = Instant::now();
    let mut l = limiter().lock().unwrap_or_else(|e| e.into_inner());
    if l.per_sender.len() > 10_000 {
        l.per_sender
            .retain(|_, q| q.back().is_some_and(|t| now.duration_since(*t) < WINDOW));
    }
    if count_overall {
        while l
            .overall
            .front()
            .is_some_and(|t| now.duration_since(*t) >= OVERALL_WINDOW)
        {
            l.overall.pop_front();
        }
        if l.overall.len() >= SENDS_OVERALL {
            return false;
        }
    }
    let q = l.per_sender.entry(format!("{bucket}:{who}")).or_default();
    while q.front().is_some_and(|t| now.duration_since(*t) >= WINDOW) {
        q.pop_front();
    }
    if q.len() >= cap {
        return false;
    }
    q.push_back(now);
    if count_overall {
        l.overall.push_back(now);
    }
    true
}

/// The sender's address: the socket peer, or — when the peer is this machine
/// (a tunnel or reverse proxy in front) — the address the proxy reports.
fn sender_addr(peer: SocketAddr, headers: &HeaderMap) -> String {
    if peer.ip().is_loopback() {
        for name in ["cf-connecting-ip", "x-real-ip", "x-forwarded-for"] {
            if let Some(v) = headers.get(name).and_then(|v| v.to_str().ok()) {
                let first = v.split(',').next().unwrap_or("").trim();
                if !first.is_empty() && first.len() <= 64 {
                    return first.to_string();
                }
            }
        }
    }
    peer.ip().to_string()
}

// ---------------------------------------------------------------------------
// Routes
// ---------------------------------------------------------------------------

fn shared() -> openfang_types::agent::AgentId {
    openfang_kernel::kernel::shared_memory_agent_id()
}

fn record(state: &AppState, key: &str) -> Option<Value> {
    let v = state.kernel.memory.structured_get(shared(), key).ok()??;
    // Records written by a model can arrive as a JSON string.
    match v {
        Value::String(s) => serde_json::from_str(&s).ok(),
        other => Some(other),
    }
}

/// The published form at `slug`, or None (missing, a draft, or removed).
fn published_form(state: &AppState, slug: &str) -> Option<Value> {
    if !valid_slug(slug) {
        return None;
    }
    let def = record(state, &format!("form/{slug}"))?;
    let live =
        def["published"].as_bool().unwrap_or(false) && !def["deleted"].as_bool().unwrap_or(false);
    live.then_some(def)
}

fn plain(status: StatusCode, msg: &str) -> axum::response::Response {
    (status, Json(json!({"error": msg}))).into_response()
}

/// GET /f/:slug — the form page. The page itself is the same for every
/// form; it loads the fields from `/f/:slug/def`.
pub async fn page(Path(_slug): Path<String>) -> impl IntoResponse {
    let nonce = uuid::Uuid::new_v4().to_string();
    let html = PAGE_HTML
        .replace("__HELPERS__", shared_helpers())
        .replace("__NONCE__", &nonce);
    let csp = format!(
        "default-src 'none'; script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; style-src-attr 'unsafe-inline'; \
         img-src 'self' data: blob:; connect-src 'self'; form-action 'self'; \
         base-uri 'none'; frame-ancestors 'none'"
    );
    (
        [
            (header::CONTENT_TYPE, "text/html; charset=utf-8".to_string()),
            (
                header::HeaderName::from_static("content-security-policy"),
                csp,
            ),
            (header::CACHE_CONTROL, "no-store".to_string()),
        ],
        html,
    )
}

/// GET /f/:slug/def — title, fields and the artist names a published form
/// needs to draw itself. Nothing else about the studio is exposed.
pub async fn definition(
    State(state): State<Arc<AppState>>,
    Path(slug): Path<String>,
) -> axum::response::Response {
    let Some(def) = published_form(&state, &slug) else {
        return plain(StatusCode::NOT_FOUND, "This form isn't available.");
    };
    let mut artists = Vec::new();
    if let Ok(pairs) = state.kernel.memory.list_kv(shared()) {
        let mut names: HashMap<String, String> = HashMap::new();
        let mut order: Vec<String> = Vec::new();
        for (k, v) in pairs {
            if k == "artist/index" {
                if let Some(list) = v["artists"].as_array() {
                    order = list
                        .iter()
                        .filter_map(|x| x.as_str().map(String::from))
                        .collect();
                }
            } else if let Some(id) = k.strip_prefix("artist/") {
                let name = v["display_name"]
                    .as_str()
                    .or_else(|| v["name"].as_str())
                    .unwrap_or(id);
                names.insert(id.to_string(), name.to_string());
            }
        }
        if order.is_empty() {
            order = names.keys().cloned().collect();
            order.sort();
        }
        for id in order {
            if let Some(name) = names.get(&id) {
                artists.push(json!({"id": id, "name": name}));
            }
        }
    }
    let studio = record(&state, "setup/profile")
        .and_then(|p| {
            p["studio"]
                .as_str()
                .or_else(|| p["studio_name"].as_str())
                .or_else(|| p["name"].as_str())
                .map(String::from)
        })
        .unwrap_or_default();
    Json(json!({
        "title": def["title"].as_str().unwrap_or(&slug),
        "fields": def["fields"].as_array().cloned().unwrap_or_default(),
        "artists": artists,
        "studio": studio,
    }))
    .into_response()
}

/// POST /f/:slug/upload — one picture for a published form (a reference
/// photo, or a drawn signature). The body is the picture itself.
pub async fn upload(
    State(state): State<Arc<AppState>>,
    Path(slug): Path<String>,
    ConnectInfo(peer): ConnectInfo<SocketAddr>,
    headers: HeaderMap,
    body: Bytes,
) -> axum::response::Response {
    if published_form(&state, &slug).is_none() {
        return plain(StatusCode::NOT_FOUND, "This form isn't available.");
    }
    if !allow(
        &sender_addr(peer, &headers),
        "upload",
        UPLOADS_PER_SENDER,
        false,
    ) {
        return plain(
            StatusCode::TOO_MANY_REQUESTS,
            "That's a lot of uploads — give it a few minutes and try again.",
        );
    }
    if body.is_empty() || body.len() > MAX_UPLOAD_BYTES {
        return plain(StatusCode::PAYLOAD_TOO_LARGE, "Pictures can be up to 8 MB.");
    }
    let Some(mime) = openfang_types::uploads::sniff_image_mime(&body) else {
        return plain(
            StatusCode::UNSUPPORTED_MEDIA_TYPE,
            "Only PNG, JPEG or WebP pictures can be added.",
        );
    };
    if mime == "image/gif" {
        return plain(
            StatusCode::UNSUPPORTED_MEDIA_TYPE,
            "Only PNG, JPEG or WebP pictures can be added.",
        );
    }
    match openfang_types::uploads::save_new(&body) {
        Ok(id) => Json(json!({"file_id": id, "url": format!("/api/uploads/{id}"), "type": mime}))
            .into_response(),
        Err(e) => {
            tracing::warn!("Form upload could not be saved: {e}");
            plain(
                StatusCode::INTERNAL_SERVER_ERROR,
                "That picture didn't save. Please try again.",
            )
        }
    }
}

/// POST /f/:slug — a filled-in form.
pub async fn submit(
    State(state): State<Arc<AppState>>,
    Path(slug): Path<String>,
    ConnectInfo(peer): ConnectInfo<SocketAddr>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> axum::response::Response {
    let Some(def) = published_form(&state, &slug) else {
        return plain(StatusCode::NOT_FOUND, "This form isn't available.");
    };
    // The hidden "leave this empty" box: a filled one is a bot. It is told
    // the form went through and nothing is stored.
    if body["hp"].as_str().is_some_and(|s| !s.is_empty()) {
        return Json(json!({"ok": true})).into_response();
    }
    if !allow(&sender_addr(peer, &headers), "send", SENDS_PER_SENDER, true) {
        return plain(
            StatusCode::TOO_MANY_REQUESTS,
            "This form has been sent a lot in the last few minutes. Please try again shortly.",
        );
    }
    let data = match clean_answers(&body["data"], &def) {
        Ok(d) => d,
        Err(msg) => return plain(StatusCode::BAD_REQUEST, &msg),
    };

    let ts = chrono::Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true);
    let uuid = uuid::Uuid::new_v4().to_string();
    let memory = &state.kernel.memory;

    // Match the sender to a contact, or add them — before the submission is
    // written, so the record names its person from the first moment.
    let sender = find_sender(&def, &data);
    let keys = contact_keys(&sender);
    let mut contact_key = String::new();
    if !keys.is_empty() {
        let found = keys
            .iter()
            .find_map(|k| record(&state, k).map(|v| (k.clone(), v)));
        let (key, existing) = match found {
            Some((k, v)) => (k, Some(v)),
            None => (keys[0].clone(), None),
        };
        let rec = contact_after(existing.as_ref(), &sender, &slug, &ts);
        match memory.structured_set(shared(), &key, rec) {
            Ok(()) => contact_key = key,
            Err(e) => tracing::warn!("Form contact could not be saved: {e}"),
        }
    }

    let sub_key = format!("formsub/{slug}/{uuid}");
    let sub = json!({
        "form": slug,
        "uuid": uuid,
        "ts": ts,
        "source": "web",
        "data": Value::Object(data),
        "processed": false,
        "contact": contact_key,
    });
    if let Err(e) = memory.structured_set(shared(), &sub_key, sub) {
        tracing::warn!("Form submission could not be saved: {e}");
        return plain(
            StatusCode::INTERNAL_SERVER_ERROR,
            "That didn't save on our side. Please try again.",
        );
    }
    tracing::info!(form = %slug, key = %sub_key, "Hosted form submission stored");

    // Wake the Forms helper with the exact key (it cannot search), the same
    // way the pull-sync does for the older Worker-hosted forms.
    if let Some(forms) = state.kernel.registry.find_by_name("forms") {
        let kernel = state.kernel.clone();
        let note = if contact_key.is_empty() {
            String::new()
        } else {
            format!(
                " Its sender is already matched to the contact record at {contact_key} (the submission's \"contact\" field): do not create or update a contact for it."
            )
        };
        let msg = format!(
            "New form submission(s) just landed in shared memory at these exact keys: {sub_key}.{note} Recall each key exactly and process it per your playbook (hold the reply draft, mark it processed)."
        );
        tokio::spawn(async move {
            let handle: Arc<dyn KernelHandle> = kernel.clone() as Arc<dyn KernelHandle>;
            if let Err(e) = kernel
                .send_message_with_handle(forms.id, &msg, Some(handle), None, None)
                .await
            {
                tracing::warn!("Forms helper could not be woken for {sub_key}: {e}");
            }
        });
    }

    Json(json!({"ok": true})).into_response()
}

/// Whether a request path is one of the hosted-form routes (all public).
pub fn is_public_form_path(path: &str, method: &axum::http::Method) -> bool {
    let Some(rest) = path.strip_prefix("/f/") else {
        return false;
    };
    let mut parts = rest.split('/');
    let (Some(slug), tail, None) = (parts.next(), parts.next(), parts.next()) else {
        return false;
    };
    if !valid_slug(slug) {
        return false;
    }
    matches!(
        (tail, method),
        (None, &axum::http::Method::GET)
            | (None, &axum::http::Method::POST)
            | (Some("def"), &axum::http::Method::GET)
            | (Some("upload"), &axum::http::Method::POST)
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    fn consent_def() -> Value {
        json!({"title": "Consent", "published": true, "fields": [
            {"key": "client", "label": "Your details", "type": "text", "stype": "consent-client-info"},
            {"key": "terms", "label": "Terms", "stype": "consent-legal", "required": true},
            {"key": "sig", "label": "Signature", "stype": "consent-signature"},
            {"key": "refs", "label": "Photos", "stype": "studio-ref-images"}
        ]})
    }

    #[test]
    fn helpers_block_is_extracted() {
        let h = shared_helpers();
        assert!(h.contains("function pvKind("));
        assert!(h.contains("function pvCompose("));
        assert!(
            !h.contains("function formsPage("),
            "only the pure block ships to the public page"
        );
    }

    #[test]
    fn slugs() {
        assert!(valid_slug("tattoo-consent"));
        assert!(valid_slug("form_2"));
        for bad in ["", "Has Caps", "a/b", "../x", &"x".repeat(65)] {
            assert!(!valid_slug(bad), "{bad}");
        }
    }

    #[test]
    fn only_the_forms_own_keys_are_kept() {
        let id = uuid::Uuid::new_v4().to_string();
        let data = json!({
            "client_name": "Jane Ink", "client_email": "Jane@Example.com", "client_phone": "(701) 555-0101",
            "terms": "agreed",
            "sig": {"signature": true, "file_id": id},
            "refs": [{"url": format!("/api/uploads/{id}"), "name": "rose.jpg"}],
            "clientx": "not a field", "processed": true, "__proto__": "x"
        });
        let out = clean_answers(&data, &consent_def()).unwrap();
        assert_eq!(out.len(), 6);
        assert!(!out.contains_key("clientx") && !out.contains_key("processed"));
    }

    #[test]
    fn odd_shapes_are_refused() {
        let def = consent_def();
        for bad in [
            json!({"terms": {"anything": 1}}),
            json!({"sig": {"signature": true, "file_id": "../../etc/passwd"}}),
            json!({"refs": [{"url": "https://evil.example/x.png"}]}),
            json!({"refs": [[1, 2]]}),
            json!({"terms": "x".repeat(MAX_TEXT_CHARS + 1)}),
        ] {
            assert!(clean_answers(&bad, &def).is_err(), "{bad}");
        }
        assert!(
            clean_answers(&json!({"terms": ""}), &def).is_err(),
            "empty form"
        );
        assert!(clean_answers(&json!("nope"), &def).is_err());
    }

    #[test]
    fn sender_comes_from_the_forms_fields() {
        let def = consent_def();
        let data = json!({
            "client_name": "Jane Ink", "client_email": "Jane@Example.com", "client_phone": "+1 (701) 555-0101",
            "client_emergency_name": "Bob Ink", "client_emergency_phone": "7015550199", "sig_typed": "Jane Ink"
        });
        let s = find_sender(&def, data.as_object().unwrap());
        assert_eq!(
            s,
            Sender {
                name: "Jane Ink".into(),
                email: "jane@example.com".into(),
                phone: "+1 (701) 555-0101".into()
            }
        );
        assert_eq!(
            contact_keys(&s),
            vec!["contact/jane@example.com", "contact/7015550101"]
        );

        let flat = json!({"fields": [
            {"key": "name", "type": "text"}, {"key": "email", "type": "email"}, {"key": "phone", "type": "phone"}]});
        let s = find_sender(
            &flat,
            json!({"name": "Sam", "email": "not-an-email", "phone": "555"})
                .as_object()
                .unwrap(),
        );
        assert_eq!(
            s,
            Sender {
                name: "Sam".into(),
                ..Default::default()
            },
            "bad email and short phone are dropped"
        );
        assert!(contact_keys(&s).is_empty());
    }

    #[test]
    fn emergency_contact_is_never_the_sender() {
        let def = json!({"fields": [{"key": "q", "type": "text"}]});
        let data = json!({"q_emergency_phone": "7015550199", "q_parent_email": "mom@example.com", "q_minor_name": "Kid"});
        assert_eq!(
            find_sender(&def, data.as_object().unwrap()),
            Sender::default()
        );
    }

    #[test]
    fn returning_contact_keeps_everything_and_gains_a_visit() {
        let s = Sender {
            name: "Jane Ink".into(),
            email: "jane@example.com".into(),
            phone: "7015550101".into(),
        };
        let old = json!({"name": "Jane I.", "email": "jane@example.com", "phone": "", "visits": 2,
            "notes": [{"text": "prefers Leni"}], "kind": "Client", "first_seen": "2026-01-01"});
        let rec = contact_after(Some(&old), &s, "consent", "2026-11-09T12:00:00Z");
        assert_eq!(rec["visits"], 3);
        assert_eq!(
            rec["name"], "Jane I.",
            "an existing name is not overwritten"
        );
        assert_eq!(rec["phone"], "7015550101", "a missing phone is filled in");
        assert_eq!(rec["notes"][0]["text"], "prefers Leni");
        assert_eq!(rec["kind"], "Client");
        assert_eq!(rec["first_seen"], "2026-01-01");

        let new = contact_after(None, &s, "consent", "2026-11-09T12:00:00Z");
        assert_eq!(new["visits"], 1);
        assert_eq!(new["source_form"], "consent");
        assert!(new["notes"].as_array().unwrap().is_empty());
    }

    #[test]
    fn public_paths() {
        use axum::http::Method;
        assert!(is_public_form_path("/f/consent", &Method::GET));
        assert!(is_public_form_path("/f/consent", &Method::POST));
        assert!(is_public_form_path("/f/consent/def", &Method::GET));
        assert!(is_public_form_path("/f/consent/upload", &Method::POST));
        assert!(!is_public_form_path("/f/consent/def", &Method::POST));
        assert!(!is_public_form_path("/f/consent/upload", &Method::GET));
        assert!(!is_public_form_path("/f/consent/def/more", &Method::GET));
        assert!(!is_public_form_path("/f/Bad Slug", &Method::GET));
        assert!(!is_public_form_path("/api/approvals", &Method::GET));
    }

    #[test]
    fn sender_limit_holds() {
        let who = format!("test-{}", uuid::Uuid::new_v4());
        for _ in 0..3 {
            assert!(allow(&who, "t", 3, false));
        }
        assert!(!allow(&who, "t", 3, false));
        assert!(allow(&format!("{who}-other"), "t", 3, false));
    }
}
