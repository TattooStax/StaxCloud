//! Stateless session token authentication for the dashboard.
//! Tokens are HMAC-SHA256 signed and contain username + expiry.

use hmac::{Hmac, Mac};
use sha2::Sha256;

type HmacSha256 = Hmac<Sha256>;

/// Create a session token: base64(username:expiry_unix:hmac_hex)
pub fn create_session_token(username: &str, secret: &str, ttl_hours: u64) -> String {
    use base64::Engine;
    let expiry = chrono::Utc::now().timestamp() + (ttl_hours as i64 * 3600);
    let payload = format!("{username}:{expiry}");
    let mut mac = HmacSha256::new_from_slice(secret.as_bytes()).expect("HMAC key");
    mac.update(payload.as_bytes());
    let signature = hex::encode(mac.finalize().into_bytes());
    base64::engine::general_purpose::STANDARD.encode(format!("{payload}:{signature}"))
}

/// Load the daemon's session-signing secret, creating it on first use.
///
/// The secret is independent of every other credential by design: it
/// is NOT the API key and NOT derived from the dashboard password
/// hash. Approval provenance stamps `owner_session` only for requests
/// carrying a cookie signed with this secret, and the carriers that
/// legitimately hold the API token (they read it from config) must
/// never be able to construct such a cookie. The secret persists in
/// the daemon's data dir (0600) so owner sessions survive restarts;
/// if it cannot be persisted, an ephemeral secret is used — sessions
/// then die with the process, which is degraded but never unsafe.
pub fn load_or_create_session_secret(data_dir: &std::path::Path) -> String {
    let path = data_dir.join("session_secret");
    if let Ok(existing) = std::fs::read_to_string(&path) {
        let existing = existing.trim().to_string();
        if !existing.is_empty() {
            return existing;
        }
    }
    let mut buf = [0u8; 32];
    rand::RngCore::fill_bytes(&mut rand::rng(), &mut buf);
    let secret = hex::encode(buf);
    let write = (|| -> std::io::Result<()> {
        std::fs::create_dir_all(data_dir)?;
        let mut opts = std::fs::OpenOptions::new();
        opts.write(true).create_new(true);
        #[cfg(unix)]
        {
            use std::os::unix::fs::OpenOptionsExt;
            opts.mode(0o600);
        }
        let mut f = opts.open(&path)?;
        use std::io::Write;
        f.write_all(secret.as_bytes())?;
        f.sync_all()
    })();
    match write {
        Ok(()) => secret,
        Err(e) => {
            tracing::warn!(error = %e, path = %path.display(),
                "session secret could not be persisted; sessions will not survive restart");
            secret
        }
    }
}

/// Extract the `openfang_session` cookie value from a `Cookie` header string.
///
/// Returns `None` if the header is absent or the cookie is not present.
/// Used by both the HTTP auth middleware and the WebSocket upgrade handler so
/// that browser sessions established via `sessionLogin()` are honored on both
/// surfaces (issue #1085).
pub fn extract_session_cookie(headers: &axum::http::HeaderMap) -> Option<String> {
    headers
        .get("cookie")
        .and_then(|v| v.to_str().ok())
        .and_then(|cookies| {
            cookies.split(';').find_map(|c| {
                c.trim()
                    .strip_prefix("openfang_session=")
                    .map(|v| v.to_string())
            })
        })
}

/// Verify a session token. Returns the username if valid and not expired.
pub fn verify_session_token(token: &str, secret: &str) -> Option<String> {
    use base64::Engine;
    let decoded = base64::engine::general_purpose::STANDARD
        .decode(token)
        .ok()?;
    let decoded_str = String::from_utf8(decoded).ok()?;
    let parts: Vec<&str> = decoded_str.splitn(3, ':').collect();
    if parts.len() != 3 {
        return None;
    }
    let (username, expiry_str, provided_sig) = (parts[0], parts[1], parts[2]);

    let expiry: i64 = expiry_str.parse().ok()?;
    if chrono::Utc::now().timestamp() > expiry {
        return None;
    }

    let payload = format!("{username}:{expiry_str}");
    let mut mac = HmacSha256::new_from_slice(secret.as_bytes()).ok()?;
    mac.update(payload.as_bytes());
    let expected_sig = hex::encode(mac.finalize().into_bytes());

    use subtle::ConstantTimeEq;
    if provided_sig.len() != expected_sig.len() {
        return None;
    }
    if provided_sig
        .as_bytes()
        .ct_eq(expected_sig.as_bytes())
        .into()
    {
        Some(username.to_string())
    } else {
        None
    }
}

/// Hash a password with Argon2id for config storage.
///
/// Returns a PHC-format string (e.g. `$argon2id$v=19$m=19456,t=2,p=1$...`).
pub fn hash_password(password: &str) -> String {
    use argon2::{password_hash::SaltString, Argon2, PasswordHasher};
    let salt = SaltString::generate(&mut rand::thread_rng());
    Argon2::default()
        .hash_password(password.as_bytes(), &salt)
        .expect("Argon2 hashing should not fail with valid inputs")
        .to_string()
}

/// Verify a password against a stored Argon2id hash (PHC string format).
pub fn verify_password(password: &str, stored_hash: &str) -> bool {
    use argon2::{password_hash::PasswordHash, Argon2, PasswordVerifier};
    let Ok(parsed) = PasswordHash::new(stored_hash) else {
        return false;
    };
    Argon2::default()
        .verify_password(password.as_bytes(), &parsed)
        .is_ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_hash_and_verify_password() {
        let hash = hash_password("secret123");
        assert!(
            hash.starts_with("$argon2id$"),
            "should produce Argon2id PHC string"
        );
        assert!(verify_password("secret123", &hash));
        assert!(!verify_password("wrong", &hash));
    }

    #[test]
    fn test_hash_produces_unique_salts() {
        let h1 = hash_password("same");
        let h2 = hash_password("same");
        assert_ne!(h1, h2, "each hash should use a unique salt");
        assert!(verify_password("same", &h1));
        assert!(verify_password("same", &h2));
    }

    #[test]
    fn test_rejects_non_argon2_hash() {
        // A plain SHA256 hex string should no longer be accepted.
        use sha2::Digest;
        let sha256_hash = hex::encode(sha2::Sha256::digest(b"password"));
        assert!(!verify_password("password", &sha256_hash));
    }

    #[test]
    fn test_create_and_verify_token() {
        let token = create_session_token("admin", "my-secret", 1);
        let user = verify_session_token(&token, "my-secret");
        assert_eq!(user, Some("admin".to_string()));
    }

    #[test]
    fn test_token_wrong_secret() {
        let token = create_session_token("admin", "my-secret", 1);
        let user = verify_session_token(&token, "wrong-secret");
        assert_eq!(user, None);
    }

    #[test]
    fn test_session_secret_is_independent_and_persistent() {
        // Review finding (PR #1): the signing secret must not be the
        // API key (or derivable from it) — a token holder forging a
        // cookie with the API key as the HMAC secret must fail.
        let dir = std::env::temp_dir().join(format!(
            "openfang-session-secret-{}",
            std::process::id()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        let secret = load_or_create_session_secret(&dir);
        assert!(!secret.is_empty());
        // Stable across calls (persisted), so sessions survive restarts.
        assert_eq!(secret, load_or_create_session_secret(&dir));
        // A cookie signed with some other credential (the stand-in
        // API key) does not verify against the real secret.
        let forged = create_session_token("admin", "the-api-key", 1);
        assert_eq!(verify_session_token(&forged, &secret), None);
        let real = create_session_token("admin", &secret, 1);
        assert_eq!(
            verify_session_token(&real, &secret),
            Some("admin".to_string())
        );
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn test_token_invalid_base64() {
        let user = verify_session_token("not-valid-base64!!!", "secret");
        assert_eq!(user, None);
    }

    #[test]
    fn test_rejects_garbage_input() {
        assert!(!verify_password("x", "short"));
        assert!(!verify_password("x", ""));
    }

    #[test]
    fn test_verify_malformed_argon2_hash() {
        // Starts with $argon2 but is not a valid PHC string.
        assert!(!verify_password("x", "$argon2id$garbage"));
    }

    #[test]
    fn test_extract_session_cookie_present() {
        let mut h = axum::http::HeaderMap::new();
        h.insert(
            "cookie",
            "foo=bar; openfang_session=abc.def.ghi; baz=qux"
                .parse()
                .unwrap(),
        );
        assert_eq!(extract_session_cookie(&h).as_deref(), Some("abc.def.ghi"));
    }

    #[test]
    fn test_extract_session_cookie_absent() {
        let mut h = axum::http::HeaderMap::new();
        h.insert("cookie", "foo=bar; baz=qux".parse().unwrap());
        assert_eq!(extract_session_cookie(&h), None);
    }

    #[test]
    fn test_extract_session_cookie_no_header() {
        let h = axum::http::HeaderMap::new();
        assert_eq!(extract_session_cookie(&h), None);
    }

    #[test]
    fn test_extract_session_cookie_only_value() {
        let mut h = axum::http::HeaderMap::new();
        h.insert("cookie", "openfang_session=lonely".parse().unwrap());
        assert_eq!(extract_session_cookie(&h).as_deref(), Some("lonely"));
    }
}
