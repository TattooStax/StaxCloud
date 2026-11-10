//! Where uploaded and generated files live on disk.
//!
//! Upstream kept uploads in the OS temp folder (`<tmp>/openfang_uploads`).
//! Many systems clear that folder on reboot (Fedora mounts /tmp as tmpfs),
//! so client photos, reference images and generated designs vanished on
//! every restart. Uploads now live under the daemon's data folder
//! (`<data_dir>/uploads`, default `~/.openfang/data/uploads`).
//!
//! The daemon calls [`init`] once at startup with its configured data
//! folder. Code that runs without that call (tests, the CLI) falls back
//! to `$OPENFANG_HOME/data/uploads` or `~/.openfang/data/uploads`.
//!
//! Files written before this change are still found: [`resolve`] checks
//! the legacy temp folder when a file is missing from the new one, and
//! [`migrate_legacy`] copies any legacy files over at startup.

use std::path::{Path, PathBuf};
use std::sync::OnceLock;

static UPLOAD_DIR: OnceLock<PathBuf> = OnceLock::new();

/// Set the uploads folder from the daemon's data folder. First call wins.
/// Returns the folder in use.
pub fn init(data_dir: &Path) -> PathBuf {
    UPLOAD_DIR.get_or_init(|| data_dir.join("uploads")).clone()
}

/// The persistent uploads folder (not created by this call).
pub fn dir() -> PathBuf {
    UPLOAD_DIR.get().cloned().unwrap_or_else(default_dir)
}

/// The persistent uploads folder, created if missing.
pub fn ensure_dir() -> std::io::Result<PathBuf> {
    let d = dir();
    std::fs::create_dir_all(&d)?;
    Ok(d)
}

/// The pre-fork temp-folder location, kept only for reading old files.
pub fn legacy_dir() -> PathBuf {
    std::env::temp_dir().join("openfang_uploads")
}

/// Path for a file id: the persistent copy if it exists, otherwise the
/// legacy temp copy if that exists, otherwise the persistent path (so a
/// caller that writes gets the right place). Callers must validate the
/// id (UUID) before calling — this does not guard against traversal.
pub fn resolve(file_id: &str) -> PathBuf {
    let primary = dir().join(file_id);
    if primary.exists() {
        return primary;
    }
    let legacy = legacy_dir().join(file_id);
    if legacy.exists() {
        return legacy;
    }
    primary
}

/// Copy every file from the legacy temp folder into the persistent folder
/// that isn't there yet. Never deletes the legacy copies. Returns how many
/// files were copied.
pub fn migrate_legacy() -> std::io::Result<usize> {
    migrate_between(&legacy_dir(), &ensure_dir()?)
}

fn migrate_between(from: &Path, to: &Path) -> std::io::Result<usize> {
    if from == to || !from.is_dir() {
        return Ok(0);
    }
    std::fs::create_dir_all(to)?;
    let mut copied = 0;
    for entry in std::fs::read_dir(from)? {
        let entry = entry?;
        if !entry.file_type()?.is_file() {
            continue;
        }
        let target = to.join(entry.file_name());
        if target.exists() {
            continue;
        }
        std::fs::copy(entry.path(), &target)?;
        copied += 1;
    }
    Ok(copied)
}

/// Image type from the file's first bytes (PNG, JPEG, WebP, GIF), or None.
pub fn sniff_image_mime(bytes: &[u8]) -> Option<&'static str> {
    if bytes.starts_with(&[0x89, b'P', b'N', b'G']) {
        Some("image/png")
    } else if bytes.starts_with(&[0xFF, 0xD8, 0xFF]) {
        Some("image/jpeg")
    } else if bytes.len() >= 12 && &bytes[0..4] == b"RIFF" && &bytes[8..12] == b"WEBP" {
        Some("image/webp")
    } else if bytes.starts_with(b"GIF8") {
        Some("image/gif")
    } else {
        None
    }
}

/// Write bytes as a new upload. Returns the new file id (a UUID).
pub fn save_new(bytes: &[u8]) -> std::io::Result<String> {
    let id = uuid::Uuid::new_v4().to_string();
    std::fs::write(ensure_dir()?.join(&id), bytes)?;
    Ok(id)
}

/// Delete an upload by id — the stored copy and any legacy temp copy.
/// Refuses anything that is not a UUID. Ok(true) when something was
/// removed, Ok(false) when there was no such file.
pub fn remove(file_id: &str) -> std::io::Result<bool> {
    if uuid::Uuid::parse_str(file_id).is_err() {
        return Err(std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            format!("'{file_id}' is not an upload id"),
        ));
    }
    let mut removed = false;
    for p in [dir().join(file_id), legacy_dir().join(file_id)] {
        match std::fs::remove_file(&p) {
            Ok(()) => removed = true,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
            Err(e) => return Err(e),
        }
    }
    Ok(removed)
}

/// Read an upload by id. Refuses anything that is not a UUID (no paths).
pub fn read(file_id: &str) -> std::io::Result<Vec<u8>> {
    if uuid::Uuid::parse_str(file_id).is_err() {
        return Err(std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            format!("'{file_id}' is not an upload id"),
        ));
    }
    std::fs::read(resolve(file_id))
}

fn default_dir() -> PathBuf {
    let home = std::env::var("OPENFANG_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| {
            dirs::home_dir()
                .unwrap_or_else(std::env::temp_dir)
                .join(".openfang")
        });
    home.join("data").join("uploads")
}

#[cfg(test)]
mod tests {
    use super::*;

    fn scratch(name: &str) -> PathBuf {
        let d = std::env::temp_dir().join(format!(
            "openfang-uploads-test-{name}-{}",
            uuid::Uuid::new_v4()
        ));
        std::fs::create_dir_all(&d).unwrap();
        d
    }

    #[test]
    fn migrate_copies_new_files_and_keeps_existing() {
        let from = scratch("from");
        let to = scratch("to");
        std::fs::write(from.join("a"), b"old-a").unwrap();
        std::fs::write(from.join("b"), b"old-b").unwrap();
        std::fs::write(to.join("b"), b"kept-b").unwrap();

        let n = migrate_between(&from, &to).unwrap();
        assert_eq!(n, 1);
        assert_eq!(std::fs::read(to.join("a")).unwrap(), b"old-a");
        assert_eq!(std::fs::read(to.join("b")).unwrap(), b"kept-b");
        // legacy copies are never removed
        assert!(from.join("a").exists());

        // running again copies nothing
        assert_eq!(migrate_between(&from, &to).unwrap(), 0);
    }

    #[test]
    fn migrate_missing_source_is_a_no_op() {
        let to = scratch("to2");
        let missing = to.join("does-not-exist");
        assert_eq!(migrate_between(&missing, &to).unwrap(), 0);
    }

    #[test]
    fn default_dir_is_not_temp() {
        assert!(!default_dir().starts_with(std::env::temp_dir().join("openfang_uploads")));
        assert!(default_dir().ends_with(Path::new("data").join("uploads")));
    }

    #[test]
    fn remove_refuses_paths_and_reports_missing() {
        assert!(remove("../config.toml").is_err());
        assert!(remove("a/b").is_err());
        let id = uuid::Uuid::new_v4().to_string();
        assert!(!remove(&id).unwrap(), "nothing there yet");
        let id = save_new(b"test bytes").unwrap();
        assert!(resolve(&id).exists());
        assert!(remove(&id).unwrap());
        assert!(!resolve(&id).exists());
        assert!(!remove(&id).unwrap());
    }
}
