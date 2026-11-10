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

// ---------------------------------------------------------------------------
// Daily backups
// ---------------------------------------------------------------------------

/// Backups kept unless `STAX_BACKUP_KEEP` says otherwise.
pub const BACKUP_KEEP_DEFAULT: usize = 14;

/// Where the box keeps its own backups: `<home>/backups`.
pub fn backups_dir(home: &Path) -> std::path::PathBuf {
    home.join("backups")
}

/// Whether daily backups run (on unless `STAX_BACKUPS=0`).
pub fn backups_enabled() -> bool {
    !matches!(
        std::env::var("STAX_BACKUPS").as_deref().map(str::trim),
        Ok("0") | Ok("off") | Ok("false") | Ok("no")
    )
}

/// How many daily backups to keep.
pub fn backups_keep() -> usize {
    std::env::var("STAX_BACKUP_KEEP")
        .ok()
        .and_then(|v| v.trim().parse::<usize>().ok())
        .filter(|n| *n >= 1)
        .unwrap_or(BACKUP_KEEP_DEFAULT)
}

fn is_backup_name(name: &str) -> bool {
    name.len() == "studio-YYYY-MM-DD.json".len()
        && name.starts_with("studio-")
        && name.ends_with(".json")
        && chrono::NaiveDate::parse_from_str(&name[7..17], "%Y-%m-%d").is_ok()
}

/// The backups in `dir`, newest first: (file name, size in bytes).
pub fn list_backups(dir: &Path) -> Vec<(String, u64)> {
    let mut out: Vec<(String, u64)> = std::fs::read_dir(dir)
        .map(|it| {
            it.filter_map(|e| e.ok())
                .filter_map(|e| {
                    let name = e.file_name().into_string().ok()?;
                    let size = e.metadata().ok()?.len();
                    is_backup_name(&name).then_some((name, size))
                })
                .collect()
        })
        .unwrap_or_default();
    out.sort_by(|a, b| b.0.cmp(&a.0));
    out
}

/// Write the studio (records + uploads) to `<dir>/studio-<date>.json`,
/// replacing that day's file if there is one. Written to a temporary file
/// first, so a backup is either whole or absent.
pub fn write_backup(
    records: Vec<(String, serde_json::Value)>,
    upload_dir: &Path,
    dir: &Path,
    date: &str,
) -> std::io::Result<std::path::PathBuf> {
    std::fs::create_dir_all(dir)?;
    let bundle = build_bundle(records, Some(upload_dir))?;
    let path = dir.join(format!("studio-{date}.json"));
    let tmp = dir.join(format!(".studio-{date}.json.tmp"));
    {
        let file = std::fs::File::create(&tmp)?;
        let mut w = std::io::BufWriter::new(file);
        serde_json::to_writer(&mut w, &bundle).map_err(std::io::Error::other)?;
        use std::io::Write;
        w.flush()?;
        w.get_ref().sync_all()?;
    }
    std::fs::rename(&tmp, &path)?;
    Ok(path)
}

/// Delete all but the newest `keep` backups. Returns how many were removed.
pub fn prune_backups(dir: &Path, keep: usize) -> std::io::Result<usize> {
    let mut removed = 0;
    for (name, _) in list_backups(dir).into_iter().skip(keep) {
        std::fs::remove_file(dir.join(name))?;
        removed += 1;
    }
    Ok(removed)
}

/// Write today's backup unless it already exists (`force` writes it again),
/// then prune. Returns the path written, or None when today's was there.
pub fn run_backup(
    kernel: &openfang_kernel::OpenFangKernel,
    force: bool,
) -> std::io::Result<Option<std::path::PathBuf>> {
    let dir = backups_dir(&kernel.config.home_dir);
    let date = chrono::Local::now().format("%Y-%m-%d").to_string();
    if !force && dir.join(format!("studio-{date}.json")).exists() {
        return Ok(None);
    }
    let shared = openfang_kernel::kernel::shared_memory_agent_id();
    let records = kernel
        .memory
        .list_kv(shared)
        .map_err(|e| std::io::Error::other(e.to_string()))?;
    let path = write_backup(records, &openfang_types::uploads::dir(), &dir, &date)?;
    let removed = prune_backups(&dir, backups_keep())?;
    tracing::info!(path = %path.display(), removed, "Studio backup written");
    Ok(Some(path))
}

fn backups_report(state: &AppState) -> serde_json::Value {
    let dir = backups_dir(&state.kernel.config.home_dir);
    let list: Vec<serde_json::Value> = list_backups(&dir)
        .into_iter()
        .map(|(name, size)| {
            let modified = std::fs::metadata(dir.join(&name))
                .and_then(|m| m.modified())
                .ok()
                .map(|t| chrono::DateTime::<chrono::Utc>::from(t).to_rfc3339());
            serde_json::json!({"name": name, "bytes": size, "written_at": modified})
        })
        .collect();
    serde_json::json!({
        "enabled": backups_enabled(),
        "keep": backups_keep(),
        "folder": dir.display().to_string(),
        "backups": list,
    })
}

/// GET /api/studio/backups — the box's own backups, newest first.
pub async fn list_backups_route(State(state): State<Arc<AppState>>) -> axum::response::Response {
    Json(backups_report(&state)).into_response()
}

/// POST /api/studio/backups — back up now (replaces today's file).
pub async fn backup_now(State(state): State<Arc<AppState>>) -> axum::response::Response {
    let kernel = state.kernel.clone();
    match tokio::task::spawn_blocking(move || run_backup(&kernel, true)).await {
        Ok(Ok(_)) => Json(backups_report(&state)).into_response(),
        Ok(Err(e)) => {
            tracing::warn!("Backup failed: {e}");
            error(
                StatusCode::INTERNAL_SERVER_ERROR,
                "The backup could not be written",
            )
        }
        Err(e) => {
            tracing::warn!("Backup task failed: {e}");
            error(
                StatusCode::INTERNAL_SERVER_ERROR,
                "The backup could not be written",
            )
        }
    }
}

#[cfg(test)]
mod tests {
    #[test]
    fn backups_are_dated_whole_and_pruned() {
        let root = std::env::temp_dir().join(format!("stax-backup-test-{}", uuid::Uuid::new_v4()));
        let uploads = root.join("uploads");
        let dir = root.join("backups");
        std::fs::create_dir_all(&uploads).unwrap();
        let fid = uuid::Uuid::new_v4().to_string();
        std::fs::write(uploads.join(&fid), b"picture").unwrap();
        let recs = vec![
            ("contact/1".to_string(), serde_json::json!({"name": "Jane"})),
            ("__openfang_internal".to_string(), serde_json::json!(1)),
        ];
        for d in ["2026-11-01", "2026-11-02", "2026-11-03", "2026-11-04"] {
            write_backup(recs.clone(), &uploads, &dir, d).unwrap();
        }
        std::fs::write(dir.join("notes.txt"), b"not a backup").unwrap();
        let names: Vec<String> = list_backups(&dir).into_iter().map(|b| b.0).collect();
        assert_eq!(names[0], "studio-2026-11-04.json", "newest first");
        assert_eq!(names.len(), 4, "other files are not backups");
        assert_eq!(prune_backups(&dir, 2).unwrap(), 2);
        let names: Vec<String> = list_backups(&dir).into_iter().map(|b| b.0).collect();
        assert_eq!(
            names,
            vec!["studio-2026-11-04.json", "studio-2026-11-03.json"]
        );
        assert!(
            dir.join("notes.txt").exists(),
            "pruning never touches other files"
        );
        // A backup is a bundle import accepts.
        let b: StudioBundle =
            serde_json::from_slice(&std::fs::read(dir.join("studio-2026-11-04.json")).unwrap())
                .unwrap();
        check_bundle(&b).unwrap();
        assert_eq!(b.records.len(), 1, "internal keys never travel");
        assert_eq!(b.uploads[0].file_id, fid);
        assert!(std::fs::read_dir(&dir).unwrap().all(|e| !e
            .unwrap()
            .file_name()
            .to_string_lossy()
            .ends_with(".tmp")));
        std::fs::remove_dir_all(root).unwrap();
    }

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
