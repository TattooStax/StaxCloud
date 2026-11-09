//! Studio export and import — take a studio's records with you.
//!
//! The studio's records (contacts, forms, submissions, leads, designs,
//! setup, boards, and everything the hands store with `memory_store`) all
//! live in the shared memory namespace. This module bundles that namespace,
//! plus the uploaded files it points at, into one JSON file, and loads such
//! a file back in.
//!
//! What a bundle does NOT carry: chat sessions, agent and hand
//! configuration, the knowledge graph, the approvals ledger, and secrets.
//! It is the studio's business records, not a full machine image.
//!
//! - `GET  /api/studio/export` — the bundle. `?uploads=false` leaves files out.
//! - `POST /api/studio/import` — load a bundle. Existing records and files are
//!   kept unless `?overwrite=true`. Returns what was added, replaced and skipped.

use crate::routes::AppState;
use axum::extract::{Query, State};
use axum::http::{header, StatusCode};
use axum::response::IntoResponse;
use axum::Json;
use base64::Engine;
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::path::Path;
use std::sync::Arc;

/// Format tag written into every bundle and checked on import.
pub const BUNDLE_FORMAT: &str = "staxcloud-studio";
/// Bundle layout version. Bump when the shape changes.
pub const BUNDLE_VERSION: u32 = 1;
/// Keys the kernel keeps for its own bookkeeping (migration flags and the
/// like). They describe this machine, not the studio, so they never leave
/// in an export and are never written by an import.
pub const INTERNAL_KEY_PREFIX: &str = "__openfang_";

/// Largest bundle the import route accepts (uploads ride along as base64).
pub const MAX_IMPORT_BYTES: usize = 512 * 1024 * 1024;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct BundleRecord {
    pub key: String,
    pub value: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct BundleUpload {
    /// The upload's id (a UUID) — the same id records use in `/api/uploads/<id>`.
    pub file_id: String,
    pub data_base64: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct StudioBundle {
    pub format: String,
    pub version: u32,
    pub exported_at: String,
    pub records: Vec<BundleRecord>,
    #[serde(default)]
    pub uploads: Vec<BundleUpload>,
}

#[derive(Debug, Default, Clone, Serialize, PartialEq)]
pub struct ImportCounts {
    pub added: usize,
    pub replaced: usize,
    pub skipped: usize,
}

#[derive(Debug, Default, Clone, Serialize, PartialEq)]
pub struct ImportReport {
    pub records: ImportCounts,
    pub uploads: ImportCounts,
    /// Upload entries rejected because their id was not a UUID or their
    /// data was not valid base64. Named so nothing is dropped silently.
    pub rejected_uploads: Vec<String>,
}

/// Build a bundle from the shared namespace's records and, when given, every
/// UUID-named file in the uploads folder. Records come out sorted by key so
/// two exports of the same studio are identical.
pub fn build_bundle(
    mut records: Vec<(String, serde_json::Value)>,
    upload_dir: Option<&Path>,
) -> std::io::Result<StudioBundle> {
    records.retain(|(k, _)| !k.starts_with(INTERNAL_KEY_PREFIX));
    records.sort_by(|a, b| a.0.cmp(&b.0));
    let mut uploads = Vec::new();
    if let Some(dir) = upload_dir {
        if dir.is_dir() {
            let mut names: Vec<String> = std::fs::read_dir(dir)?
                .filter_map(|e| e.ok())
                .filter(|e| e.file_type().map(|t| t.is_file()).unwrap_or(false))
                .filter_map(|e| e.file_name().into_string().ok())
                .filter(|n| uuid::Uuid::parse_str(n).is_ok())
                .collect();
            names.sort();
            for name in names {
                let bytes = std::fs::read(dir.join(&name))?;
                uploads.push(BundleUpload {
                    file_id: name,
                    data_base64: base64::engine::general_purpose::STANDARD.encode(bytes),
                });
            }
        }
    }
    Ok(StudioBundle {
        format: BUNDLE_FORMAT.to_string(),
        version: BUNDLE_VERSION,
        exported_at: chrono::Utc::now().to_rfc3339(),
        records: records
            .into_iter()
            .map(|(key, value)| BundleRecord { key, value })
            .collect(),
        uploads,
    })
}

/// Refuse a bundle that isn't ours or is from a newer layout.
pub fn check_bundle(bundle: &StudioBundle) -> Result<(), String> {
    if bundle.format != BUNDLE_FORMAT {
        return Err(format!(
            "This file is not a studio export (format '{}').",
            bundle.format
        ));
    }
    if bundle.version > BUNDLE_VERSION {
        return Err(format!(
            "This export was made by a newer version (layout {}); update this box first.",
            bundle.version
        ));
    }
    Ok(())
}

/// Decide which records to write. Returns the records to write and the counts.
pub fn plan_records<'a>(
    bundle: &'a StudioBundle,
    existing: &HashSet<String>,
    overwrite: bool,
) -> (Vec<&'a BundleRecord>, ImportCounts) {
    let mut counts = ImportCounts::default();
    let mut write = Vec::new();
    for rec in &bundle.records {
        if rec.key.starts_with(INTERNAL_KEY_PREFIX) {
            counts.skipped += 1;
            continue;
        }
        if existing.contains(&rec.key) {
            if overwrite {
                counts.replaced += 1;
                write.push(rec);
            } else {
                counts.skipped += 1;
            }
        } else {
            counts.added += 1;
            write.push(rec);
        }
    }
    (write, counts)
}

/// Write the bundle's files into `dir`. Bad entries are named, not dropped.
pub fn write_uploads(
    bundle: &StudioBundle,
    dir: &Path,
    overwrite: bool,
) -> std::io::Result<(ImportCounts, Vec<String>)> {
    let mut counts = ImportCounts::default();
    let mut rejected = Vec::new();
    if bundle.uploads.is_empty() {
        return Ok((counts, rejected));
    }
    std::fs::create_dir_all(dir)?;
    for up in &bundle.uploads {
        if uuid::Uuid::parse_str(&up.file_id).is_err() {
            rejected.push(up.file_id.clone());
            continue;
        }
        let bytes = match base64::engine::general_purpose::STANDARD.decode(&up.data_base64) {
            Ok(b) => b,
            Err(_) => {
                rejected.push(up.file_id.clone());
                continue;
            }
        };
        let path = dir.join(&up.file_id);
        let exists = path.exists();
        if exists && !overwrite {
            counts.skipped += 1;
            continue;
        }
        std::fs::write(&path, bytes)?;
        if exists {
            counts.replaced += 1;
        } else {
            counts.added += 1;
        }
    }
    Ok((counts, rejected))
}

fn flag(params: &HashMap<String, String>, name: &str, default: bool) -> bool {
    match params.get(name).map(|s| s.to_ascii_lowercase()) {
        Some(v) if v == "true" || v == "1" || v == "yes" => true,
        Some(v) if v == "false" || v == "0" || v == "no" => false,
        _ => default,
    }
}

fn error(status: StatusCode, msg: impl Into<String>) -> axum::response::Response {
    (status, Json(serde_json::json!({ "error": msg.into() }))).into_response()
}

/// GET /api/studio/export
pub async fn export_studio(
    State(state): State<Arc<AppState>>,
    Query(params): Query<HashMap<String, String>>,
) -> axum::response::Response {
    let include_uploads = flag(&params, "uploads", true);
    let shared = openfang_kernel::kernel::shared_memory_agent_id();
    let records = match state.kernel.memory.list_kv(shared) {
        Ok(r) => r,
        Err(e) => {
            tracing::warn!("Studio export: list_kv failed: {e}");
            return error(
                StatusCode::INTERNAL_SERVER_ERROR,
                "Could not read the studio records",
            );
        }
    };
    let dir = openfang_types::uploads::dir();
    let bundle = match build_bundle(records, include_uploads.then_some(dir.as_path())) {
        Ok(b) => b,
        Err(e) => {
            tracing::warn!("Studio export: reading uploads failed: {e}");
            return error(
                StatusCode::INTERNAL_SERVER_ERROR,
                "Could not read the studio's files",
            );
        }
    };
    let filename = format!(
        "studio-export-{}.json",
        chrono::Utc::now().format("%Y-%m-%d")
    );
    (
        StatusCode::OK,
        [(
            header::CONTENT_DISPOSITION,
            format!("attachment; filename=\"{filename}\""),
        )],
        Json(bundle),
    )
        .into_response()
}

/// POST /api/studio/import
pub async fn import_studio(
    State(state): State<Arc<AppState>>,
    Query(params): Query<HashMap<String, String>>,
    Json(bundle): Json<StudioBundle>,
) -> axum::response::Response {
    if let Err(msg) = check_bundle(&bundle) {
        return error(StatusCode::BAD_REQUEST, msg);
    }
    let overwrite = flag(&params, "overwrite", false);
    let shared = openfang_kernel::kernel::shared_memory_agent_id();

    let existing: HashSet<String> = match state.kernel.memory.list_kv(shared) {
        Ok(r) => r.into_iter().map(|(k, _)| k).collect(),
        Err(e) => {
            tracing::warn!("Studio import: list_kv failed: {e}");
            return error(
                StatusCode::INTERNAL_SERVER_ERROR,
                "Could not read the studio records",
            );
        }
    };

    // Files first: a record that points at a file should never land before it.
    let (upload_counts, rejected) = match openfang_types::uploads::ensure_dir()
        .and_then(|dir| write_uploads(&bundle, &dir, overwrite))
    {
        Ok(r) => r,
        Err(e) => {
            tracing::warn!("Studio import: writing uploads failed: {e}");
            return error(
                StatusCode::INTERNAL_SERVER_ERROR,
                "Could not save the studio's files",
            );
        }
    };

    let (to_write, record_counts) = plan_records(&bundle, &existing, overwrite);
    for (written, rec) in to_write.into_iter().enumerate() {
        if let Err(e) = state
            .kernel
            .memory
            .structured_set(shared, &rec.key, rec.value.clone())
        {
            tracing::warn!("Studio import: writing '{}' failed: {e}", rec.key);
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(serde_json::json!({
                    "error": format!("Stopped at record '{}'; {written} records were written before it.", rec.key),
                    "uploads": upload_counts,
                })),
            )
                .into_response();
        }
    }

    (
        StatusCode::OK,
        Json(ImportReport {
            records: record_counts,
            uploads: upload_counts,
            rejected_uploads: rejected,
        }),
    )
        .into_response()
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn scratch() -> std::path::PathBuf {
        let d = std::env::temp_dir().join(format!("studio-test-{}", uuid::Uuid::new_v4()));
        std::fs::create_dir_all(&d).unwrap();
        d
    }

    #[test]
    fn export_sorts_records_and_only_takes_uuid_files() {
        let dir = scratch();
        let id = uuid::Uuid::new_v4().to_string();
        std::fs::write(dir.join(&id), b"photo").unwrap();
        std::fs::write(dir.join("not-a-uuid.txt"), b"junk").unwrap();

        let b = build_bundle(
            vec![
                ("contact/b".into(), json!({"name": "B"})),
                ("contact/a".into(), json!({"name": "A"})),
            ],
            Some(&dir),
        )
        .unwrap();

        assert_eq!(b.format, BUNDLE_FORMAT);
        assert_eq!(b.records[0].key, "contact/a");
        assert_eq!(b.uploads.len(), 1);
        assert_eq!(b.uploads[0].file_id, id);
    }

    #[test]
    fn internal_kernel_keys_never_travel() {
        let b = build_bundle(
            vec![
                ("__openfang_schedules_migrated_v1".into(), json!(true)),
                ("contact/a".into(), json!(1)),
            ],
            None,
        )
        .unwrap();
        assert_eq!(b.records.len(), 1);

        let mut b = b;
        b.records.push(BundleRecord {
            key: "__openfang_x".into(),
            value: json!(1),
        });
        let (w, c) = plan_records(&b, &HashSet::new(), true);
        assert_eq!(w.len(), 1);
        assert_eq!(c.skipped, 1);
    }

    #[test]
    fn export_without_uploads_has_none() {
        let b = build_bundle(vec![("k".into(), json!(1))], None).unwrap();
        assert!(b.uploads.is_empty());
    }

    #[test]
    fn import_keeps_existing_records_unless_overwrite() {
        let b = build_bundle(
            vec![
                ("contact/a".into(), json!(1)),
                ("contact/b".into(), json!(2)),
            ],
            None,
        )
        .unwrap();
        let existing: HashSet<String> = ["contact/a".to_string()].into_iter().collect();

        let (w, c) = plan_records(&b, &existing, false);
        assert_eq!(w.len(), 1);
        assert_eq!(
            c,
            ImportCounts {
                added: 1,
                replaced: 0,
                skipped: 1
            }
        );

        let (w, c) = plan_records(&b, &existing, true);
        assert_eq!(w.len(), 2);
        assert_eq!(
            c,
            ImportCounts {
                added: 1,
                replaced: 1,
                skipped: 0
            }
        );
    }

    #[test]
    fn round_trip_restores_files_byte_for_byte() {
        let src = scratch();
        let id = uuid::Uuid::new_v4().to_string();
        std::fs::write(src.join(&id), [0u8, 159, 255, 1]).unwrap();
        let b = build_bundle(vec![], Some(&src)).unwrap();

        // through JSON, as the routes do
        let text = serde_json::to_string(&b).unwrap();
        let b: StudioBundle = serde_json::from_str(&text).unwrap();

        let dst = scratch();
        let (c, rejected) = write_uploads(&b, &dst, false).unwrap();
        assert_eq!(c.added, 1);
        assert!(rejected.is_empty());
        assert_eq!(
            std::fs::read(dst.join(&id)).unwrap(),
            vec![0u8, 159, 255, 1]
        );

        // second import skips, overwrite replaces
        assert_eq!(write_uploads(&b, &dst, false).unwrap().0.skipped, 1);
        assert_eq!(write_uploads(&b, &dst, true).unwrap().0.replaced, 1);
    }

    #[test]
    fn import_names_bad_upload_entries() {
        let mut b = build_bundle(vec![], None).unwrap();
        b.uploads.push(BundleUpload {
            file_id: "../etc/passwd".into(),
            data_base64: "aGk=".into(),
        });
        b.uploads.push(BundleUpload {
            file_id: uuid::Uuid::new_v4().to_string(),
            data_base64: "%%% not base64".into(),
        });
        let dst = scratch();
        let (c, rejected) = write_uploads(&b, &dst, false).unwrap();
        assert_eq!(c.added, 0);
        assert_eq!(rejected.len(), 2);
        assert_eq!(rejected[0], "../etc/passwd");
        assert_eq!(std::fs::read_dir(&dst).unwrap().count(), 0);
    }

    #[test]
    fn rejects_foreign_or_newer_bundles() {
        let mut b = build_bundle(vec![], None).unwrap();
        assert!(check_bundle(&b).is_ok());
        b.version = BUNDLE_VERSION + 1;
        assert!(check_bundle(&b).is_err());
        b.version = BUNDLE_VERSION;
        b.format = "something-else".into();
        assert!(check_bundle(&b).is_err());
    }
}
