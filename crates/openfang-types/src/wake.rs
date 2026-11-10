//! Wake rules for background helpers: decide in code, before any model is
//! called, whether a scheduled wake has new work to do.
//!
//! A helper's HAND.toml may carry a `[wake]` table:
//!
//! ```toml
//! [wake]
//! fresh = true                                   # start each scheduled wake with a clean conversation
//! when = [
//!   { key = "attention/sms", list = "threads" },  # work = the keys this list names
//!   { prefix = "formsub/", unless = "processed" } # work = records under it not yet marked processed
//! ]
//! ```
//!
//! A scheduled wake runs the model only when the watched records hold work
//! AND that work changed since the helper last woke. Otherwise the wake is
//! skipped and costs nothing. The rules are config, never the model's.

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

/// A helper's wake rules (the `[wake]` table of HAND.toml).
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct WakeSpec {
    /// Scheduled wakes start with an empty conversation instead of carrying
    /// the helper's running history along on every step.
    #[serde(default)]
    pub fresh: bool,
    /// What counts as work. Empty = no gate: every scheduled wake runs.
    #[serde(default)]
    pub when: Vec<WakeWatch>,
    /// The helper's standing schedules. The kernel keeps each one in place
    /// (creates it when missing, never twice); the helper itself never
    /// creates or deletes schedules.
    #[serde(default)]
    pub schedules: Vec<WakeSchedule>,
}

/// One standing schedule a helper runs on.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct WakeSchedule {
    pub name: String,
    /// 5-field cron expression, e.g. "*/15 * * * *".
    pub cron: String,
    /// What the helper is told when it fires.
    pub message: String,
    /// false = this schedule always reaches the model (e.g. a weekly
    /// re-check that has to look outside the records to find work).
    #[serde(default = "yes")]
    pub gated: bool,
}

fn yes() -> bool {
    true
}

/// One watched place in the shared records.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct WakeWatch {
    /// One exact record.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub key: Option<String>,
    /// With `key`: the field holding a list. Work = the list's entries (and,
    /// when an entry names another record, that record's contents).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub list: Option<String>,
    /// A family of records, e.g. "formsub/".
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub prefix: Option<String>,
    /// With `prefix`: a record is work only while this field is not true.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub unless: Option<String>,
}

impl WakeSpec {
    pub fn is_gated(&self) -> bool {
        !self.when.is_empty()
    }

    /// Whether the work check applies to the scheduled job with this name.
    pub fn gates_job(&self, job_name: &str) -> bool {
        self.is_gated()
            && !self
                .schedules
                .iter()
                .any(|s| !s.gated && same_job_name(&s.name, job_name))
    }
}

/// Job names compare loosely: the scheduler swaps punctuation for dashes.
pub fn same_job_name(a: &str, b: &str) -> bool {
    let norm = |s: &str| {
        s.trim()
            .to_lowercase()
            .chars()
            .map(|c| if c.is_alphanumeric() { c } else { ' ' })
            .collect::<String>()
            .split_whitespace()
            .collect::<Vec<_>>()
            .join(" ")
    };
    norm(a) == norm(b)
}

/// A stored record as JSON, whether stored as an object or a JSON string.
fn as_json(v: &serde_json::Value) -> serde_json::Value {
    if let serde_json::Value::String(s) = v {
        if let Ok(j) = serde_json::from_str::<serde_json::Value>(s) {
            if j.is_object() || j.is_array() {
                return j;
            }
        }
    }
    v.clone()
}

fn digest(v: &serde_json::Value) -> String {
    let h = Sha256::digest(v.to_string().as_bytes());
    hex::encode(&h[..8])
}

/// The work the watched records hold right now, as (place, content digest)
/// pairs, sorted. Empty = nothing to do. `records` is every shared record.
pub fn work_items(
    spec: &WakeSpec,
    records: &[(String, serde_json::Value)],
) -> Vec<(String, String)> {
    let find = |k: &str| records.iter().find(|(rk, _)| rk == k).map(|(_, v)| v);
    let mut out = Vec::new();
    for w in &spec.when {
        if let Some(key) = &w.key {
            let Some(raw) = find(key) else { continue };
            let rec = as_json(raw);
            match &w.list {
                Some(field) => {
                    let items = rec
                        .get(field)
                        .and_then(|x| x.as_array())
                        .cloned()
                        .unwrap_or_default();
                    for item in items {
                        let name = item
                            .as_str()
                            .map(str::to_string)
                            .unwrap_or_else(|| item.to_string());
                        // An entry naming a record changes when that record does
                        // (a new message in a thread already on the list).
                        let d = find(&name).map(digest).unwrap_or_else(|| digest(&item));
                        out.push((format!("{key}#{name}"), d));
                    }
                }
                None => {
                    let empty = rec.is_null()
                        || rec.as_array().is_some_and(|a| a.is_empty())
                        || rec.as_object().is_some_and(|o| o.is_empty())
                        || rec.as_str().is_some_and(|s| s.trim().is_empty());
                    if !empty {
                        out.push((key.clone(), digest(&rec)));
                    }
                }
            }
        }
        if let Some(prefix) = &w.prefix {
            for (k, raw) in records
                .iter()
                .filter(|(k, _)| k.starts_with(prefix.as_str()))
            {
                let rec = as_json(raw);
                if let Some(field) = &w.unless {
                    if rec.get(field).and_then(|x| x.as_bool()).unwrap_or(false) {
                        continue;
                    }
                }
                out.push((k.clone(), digest(&rec)));
            }
        }
    }
    out.sort();
    out.dedup();
    out
}

/// One string that changes whenever the work changes.
pub fn fingerprint(items: &[(String, String)]) -> String {
    let mut h = Sha256::new();
    for (k, d) in items {
        h.update(k.as_bytes());
        h.update(b"\0");
        h.update(d.as_bytes());
        h.update(b"\n");
    }
    hex::encode(&h.finalize()[..12])
}

/// What a scheduled wake should do.
#[derive(Debug, Clone, PartialEq)]
pub enum WakeDecision {
    /// Run the model: there is work it has not seen.
    Run,
    /// Skip: the watched records hold no work.
    NoWork,
    /// Skip: the same work the helper already handled on its last wake.
    Unchanged,
}

pub fn decide(
    spec: &WakeSpec,
    records: &[(String, serde_json::Value)],
    last_fingerprint: Option<&str>,
) -> (WakeDecision, String) {
    if !spec.is_gated() {
        return (WakeDecision::Run, String::new());
    }
    let items = work_items(spec, records);
    let fp = fingerprint(&items);
    if items.is_empty() {
        return (WakeDecision::NoWork, fp);
    }
    if last_fingerprint == Some(fp.as_str()) {
        return (WakeDecision::Unchanged, fp);
    }
    (WakeDecision::Run, fp)
}

/// The shared record holding a helper's wake receipts.
pub fn receipt_key(agent_name: &str) -> String {
    format!("wake/{agent_name}")
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn sms_spec() -> WakeSpec {
        toml::from_str(
            r#"fresh = true
when = [ { key = "attention/sms", list = "threads" } ]"#,
        )
        .unwrap()
    }

    fn forms_spec() -> WakeSpec {
        toml::from_str(r#"when = [ { prefix = "formsub/", unless = "processed" } ]"#).unwrap()
    }

    #[test]
    fn parses_from_toml() {
        let s = sms_spec();
        assert!(s.fresh && s.is_gated());
        assert_eq!(s.when[0].key.as_deref(), Some("attention/sms"));
        assert!(!WakeSpec::default().is_gated());
    }

    #[test]
    fn texts_wake_only_for_new_or_changed_threads() {
        let spec = sms_spec();
        let empty = vec![("attention/sms".to_string(), json!({"threads": []}))];
        assert_eq!(decide(&spec, &empty, None).0, WakeDecision::NoWork);
        assert_eq!(
            decide(&spec, &[], None).0,
            WakeDecision::NoWork,
            "missing record = no work"
        );

        let mut recs = vec![
            (
                "attention/sms".to_string(),
                json!({"threads": ["sms/7015550101"]}),
            ),
            (
                "sms/7015550101".to_string(),
                json!({"messages": [{"id": "m1", "body": "hi"}]}),
            ),
        ];
        let (d, fp) = decide(&spec, &recs, None);
        assert_eq!(d, WakeDecision::Run);
        // Same waiting thread, nothing new: no second wake.
        assert_eq!(decide(&spec, &recs, Some(&fp)).0, WakeDecision::Unchanged);
        // A new message in that same thread: wake again.
        recs[1].1 =
            json!({"messages": [{"id": "m1", "body": "hi"}, {"id": "m2", "body": "still there?"}]});
        assert_eq!(decide(&spec, &recs, Some(&fp)).0, WakeDecision::Run);
    }

    #[test]
    fn forms_wake_only_for_unprocessed_submissions() {
        let spec = forms_spec();
        let done = vec![("formsub/booking/a".to_string(), json!({"processed": true}))];
        assert_eq!(decide(&spec, &done, None).0, WakeDecision::NoWork);
        let fresh = vec![
            ("formsub/booking/a".to_string(), json!({"processed": true})),
            (
                "formsub/booking/b".to_string(),
                serde_json::Value::String(json!({"data": {}}).to_string()),
            ),
            ("contact/x".to_string(), json!({})),
        ];
        let items = work_items(&spec, &fresh);
        assert_eq!(items.len(), 1);
        assert_eq!(items[0].0, "formsub/booking/b");
    }

    #[test]
    fn schedules_parse_and_an_ungated_one_skips_the_check() {
        let spec: WakeSpec = toml::from_str(
            r#"fresh = true
when = [ { key = "stylequeue", list = "pending" } ]
[[schedules]]
name = "style catch-up"
cron = "*/15 * * * *"
message = "Learn the next portfolio pictures."
[[schedules]]
name = "style weekly"
cron = "0 3 * * 0"
message = "Check the website for new portfolio pictures."
gated = false"#,
        )
        .unwrap();
        assert_eq!(spec.schedules.len(), 2);
        assert!(spec.schedules[0].gated);
        assert!(spec.gates_job("style catch-up"));
        assert!(!spec.gates_job("Style-Weekly"), "names compare loosely");
        assert!(spec.gates_job("anything else"));
    }

    #[test]
    fn ungated_always_runs() {
        assert_eq!(
            decide(&WakeSpec::default(), &[], Some("x")).0,
            WakeDecision::Run
        );
    }
}
