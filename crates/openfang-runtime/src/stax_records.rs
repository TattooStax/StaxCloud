//! Deterministic record tools for the lead (Stax): find everything about one
//! customer in one call, draft an email reply, draft a form from the
//! builder's own blocks. The model proposes; this code checks, writes in the
//! exact shapes the rest of the system reads, and reads back.

use crate::kernel_handle::KernelHandle;
use serde_json::{json, Value};
use std::collections::BTreeSet;
use std::sync::Arc;

fn as_record(v: &Value) -> Value {
    if let Value::String(s) = v {
        if let Ok(j) = serde_json::from_str::<Value>(s) {
            if j.is_object() {
                return j;
            }
        }
    }
    v.clone()
}

/// Phone digits as contact keys use them (US leading 1 dropped).
pub fn phone_digits(raw: &str) -> String {
    let mut d: String = raw.chars().filter(|c| c.is_ascii_digit()).collect();
    if d.len() == 11 && d.starts_with('1') {
        d.remove(0);
    }
    d
}

fn cut(s: &str, n: usize) -> String {
    let t = s.split_whitespace().collect::<Vec<_>>().join(" ");
    if t.chars().count() <= n {
        t
    } else {
        format!("{}…", t.chars().take(n).collect::<String>())
    }
}

fn strings_in(v: &Value, out: &mut Vec<String>) {
    match v {
        Value::String(s) => out.push(s.clone()),
        Value::Array(a) => a.iter().for_each(|x| strings_in(x, out)),
        Value::Object(o) => o.values().for_each(|x| strings_in(x, out)),
        _ => {}
    }
}

/// One person as the records know them.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Person {
    pub name: String,
    pub emails: BTreeSet<String>,
    pub phones: BTreeSet<String>,
    pub contact_keys: Vec<String>,
}

impl Person {
    fn mentions(&self, text: &str) -> bool {
        let t = text.to_lowercase();
        self.emails.iter().any(|e| t.contains(e.as_str()))
            || self
                .phones
                .iter()
                .any(|p| p.len() >= 7 && phone_digits(&t).contains(p.as_str()))
    }
}

/// People from contact records, merged when they share an email or phone.
pub fn people(records: &[(String, Value)]) -> Vec<Person> {
    let mut out: Vec<Person> = Vec::new();
    for (k, v) in records.iter().filter(|(k, _)| k.starts_with("contact/")) {
        let r = as_record(v);
        let mut p = Person {
            name: r["name"].as_str().unwrap_or("").trim().to_string(),
            contact_keys: vec![k.clone()],
            ..Default::default()
        };
        let id = &k["contact/".len()..];
        if id.contains('@') {
            p.emails.insert(id.to_lowercase());
        } else if phone_digits(id).len() >= 7 {
            p.phones.insert(phone_digits(id));
        }
        for f in ["email", "emails"] {
            let mut s = Vec::new();
            strings_in(&r[f], &mut s);
            for e in s.into_iter().filter(|e| e.contains('@')) {
                p.emails.insert(e.trim().to_lowercase());
            }
        }
        for f in ["phone", "phones"] {
            let mut s = Vec::new();
            strings_in(&r[f], &mut s);
            for x in s {
                let d = phone_digits(&x);
                if d.len() >= 7 {
                    p.phones.insert(d);
                }
            }
        }
        if let Some(same) = out.iter_mut().find(|q| {
            q.emails.intersection(&p.emails).next().is_some()
                || q.phones.intersection(&p.phones).next().is_some()
        }) {
            same.emails.extend(p.emails);
            same.phones.extend(p.phones);
            same.contact_keys.extend(p.contact_keys);
            if same.name.is_empty() {
                same.name = p.name;
            }
        } else {
            out.push(p);
        }
    }
    out
}

/// Which people a query (name words, an email, or a phone number) means.
pub fn matching<'a>(all: &'a [Person], query: &str) -> Vec<&'a Person> {
    let q = query.trim().to_lowercase();
    let digits = phone_digits(&q);
    if q.contains('@') {
        return all.iter().filter(|p| p.emails.contains(&q)).collect();
    }
    if digits.len() >= 7 && digits.len() * 2 >= q.chars().filter(|c| !c.is_whitespace()).count() {
        return all
            .iter()
            .filter(|p| {
                p.phones
                    .iter()
                    .any(|ph| ph.ends_with(&digits) || digits.ends_with(ph.as_str()))
            })
            .collect();
    }
    let words: Vec<&str> = q.split_whitespace().collect();
    if words.is_empty() {
        return Vec::new();
    }
    all.iter()
        .filter(|p| {
            let n = p.name.to_lowercase();
            words
                .iter()
                .all(|w| n.split_whitespace().any(|part| part.starts_with(w)))
        })
        .collect()
}

/// Everything the records hold about one customer, newest first per kind.
pub fn customer_lookup(kh: &Arc<dyn KernelHandle>, query: &str) -> Result<String, String> {
    if query.trim().is_empty() {
        return Err("Say who: a name, an email, or a phone number.".into());
    }
    let records = kh.memory_list("")?;
    let all = people(&records);
    let mut hits = matching(&all, query);
    // Someone with no contact record yet: a text thread, a form or an email
    // may still be theirs.
    let stranger;
    if hits.is_empty() {
        let q = query.trim().to_lowercase();
        let d = phone_digits(&q);
        let mut p = Person::default();
        if q.contains('@') {
            p.emails.insert(q.clone());
        } else if d.len() >= 7 {
            p.phones.insert(d);
        } else {
            return Ok(format!(
                "No contact matches \"{}\". Try a phone number or email, or memory_list with contains.",
                query.trim()
            ));
        }
        p.name = query.trim().to_string();
        stranger = p;
        hits.push(&stranger);
    }
    if hits.len() > 1 {
        let list: Vec<String> = hits
            .iter()
            .take(8)
            .map(|p| {
                let mut id: Vec<String> = p.emails.iter().cloned().collect();
                id.extend(p.phones.iter().cloned());
                format!(
                    "{} ({})",
                    if p.name.is_empty() {
                        "no name"
                    } else {
                        &p.name
                    },
                    id.join(", ")
                )
            })
            .collect();
        return Ok(format!(
            "{} people match \"{}\" — say which: {}",
            hits.len(),
            query.trim(),
            list.join("; ")
        ));
    }
    let p = hits[0];
    let mut out = String::new();
    let ids: Vec<String> = p.emails.iter().chain(p.phones.iter()).cloned().collect();
    out.push_str(&format!(
        "{} — {}\n",
        if p.name.is_empty() {
            "(no name on record)"
        } else {
            &p.name
        },
        ids.join(", ")
    ));

    // Contact details and notes.
    for k in &p.contact_keys {
        if let Some((_, v)) = records.iter().find(|(rk, _)| rk == k) {
            let r = as_record(v);
            let mut facts = Vec::new();
            for f in [
                "kind",
                "stage",
                "artist",
                "temperature",
                "visits",
                "last_seen",
            ] {
                if let Some(x) = r.get(f).filter(|x| !x.is_null() && x.as_str() != Some("")) {
                    facts.push(format!(
                        "{f}: {}",
                        x.as_str()
                            .map(String::from)
                            .unwrap_or_else(|| x.to_string())
                    ));
                }
            }
            out.push_str(&format!(
                "Contact {k}: {}\n",
                if facts.is_empty() {
                    "no details".into()
                } else {
                    facts.join(", ")
                }
            ));
            if let Some(notes) = r["notes"].as_array() {
                for n in notes.iter().rev().take(5) {
                    out.push_str(&format!(
                        "  note {}: {}\n",
                        n["ts"].as_str().unwrap_or(""),
                        cut(n["text"].as_str().unwrap_or(""), 140)
                    ));
                }
            }
        }
    }

    // Text threads.
    for d in &p.phones {
        for key in [format!("sms/{d}"), format!("sms/1{d}")] {
            if let Some((_, v)) = records.iter().find(|(k, _)| *k == key) {
                let msgs = as_record(v)["messages"]
                    .as_array()
                    .cloned()
                    .unwrap_or_default();
                out.push_str(&format!(
                    "Texts {key} ({} messages, latest last):\n",
                    msgs.len()
                ));
                for m in msgs.iter().rev().take(6).rev() {
                    let who = if m["dir"].as_str() == Some("out") {
                        "studio"
                    } else {
                        "them"
                    };
                    out.push_str(&format!(
                        "  {} {}: {}\n",
                        m["ts"].as_str().unwrap_or(""),
                        who,
                        cut(m["body"].as_str().unwrap_or(""), 160)
                    ));
                }
            }
        }
    }

    // Form submissions, emails, drafts, waiting memory facts.
    let mut forms: Vec<(String, String, String)> = Vec::new();
    let mut mails: Vec<(String, String)> = Vec::new();
    let mut drafts: Vec<String> = Vec::new();
    let mut facts: Vec<String> = Vec::new();
    for (k, v) in &records {
        let r = as_record(v);
        if k.starts_with("formsub/") && k.matches('/').count() >= 2 {
            let mut s = Vec::new();
            strings_in(&r["data"], &mut s);
            if s.iter().any(|x| p.mentions(x)) {
                let answers: Vec<String> = r["data"]
                    .as_object()
                    .map(|o| {
                        o.iter()
                            .filter_map(|(ak, av)| {
                                av.as_str()
                                    .filter(|x| !x.trim().is_empty())
                                    .map(|x| format!("{ak}: {}", cut(x, 80)))
                            })
                            .take(6)
                            .collect()
                    })
                    .unwrap_or_default();
                forms.push((
                    r["ts"].as_str().unwrap_or("").to_string(),
                    k.clone(),
                    answers.join("; "),
                ));
            }
        } else if k.starts_with("mail/") {
            let from = r["from"].as_str().unwrap_or("").to_lowercase();
            if p.emails.contains(&from) {
                mails.push((
                    r["ts"].as_str().unwrap_or("").to_string(),
                    format!(
                        "  {} {k} from them: \"{}\" — {}",
                        r["ts"].as_str().unwrap_or(""),
                        cut(r["subject"].as_str().unwrap_or(""), 80),
                        cut(
                            r["snippet"].as_str().or(r["text"].as_str()).unwrap_or(""),
                            140
                        )
                    ),
                ));
            }
        } else if k.starts_with("emailout/") {
            if p.emails
                .contains(&r["to"].as_str().unwrap_or("").to_lowercase())
            {
                mails.push((
                    r["ts"].as_str().unwrap_or("").to_string(),
                    format!(
                        "  {} {k} to them: \"{}\" ({})",
                        r["ts"].as_str().unwrap_or(""),
                        cut(r["subject"].as_str().unwrap_or(""), 80),
                        r["status"].as_str().unwrap_or("")
                    ),
                ));
            }
        } else if k.starts_with("draft/") {
            let mut s = Vec::new();
            for f in [
                "to",
                "to_name",
                "thread",
                "sub",
                "source_key",
                "contact_key",
            ] {
                strings_in(&r[f], &mut s);
            }
            if s.iter().any(|x| p.mentions(x)) || p.contact_keys.iter().any(|ck| s.contains(ck)) {
                drafts.push(format!(
                    "  {k} ({}, {}): {}",
                    r["kind"].as_str().unwrap_or("reply"),
                    r["status"].as_str().unwrap_or("held"),
                    cut(r["text"].as_str().or(r["body"].as_str()).unwrap_or(""), 120)
                ));
            }
        } else if k.starts_with("memcand/") {
            let ck = r["contact_key"].as_str().unwrap_or("");
            if p.contact_keys.iter().any(|x| x == ck) && r["status"].as_str() != Some("promoted") {
                facts.push(format!(
                    "  {}: {} (waiting for approval)",
                    r["field"].as_str().unwrap_or("fact"),
                    cut(r["value"].as_str().unwrap_or(""), 100)
                ));
            }
        }
    }
    if !forms.is_empty() {
        forms.sort_by(|a, b| b.0.cmp(&a.0));
        out.push_str("Form submissions (newest first):\n");
        for (ts, k, a) in forms.iter().take(5) {
            out.push_str(&format!("  {ts} {k}: {a}\n"));
        }
    }
    if !mails.is_empty() {
        mails.sort_by(|a, b| b.0.cmp(&a.0));
        out.push_str("Email (newest first):\n");
        for (_, line) in mails.iter().take(6) {
            out.push_str(line);
            out.push('\n');
        }
    }
    if !drafts.is_empty() {
        out.push_str("Drafts:\n");
        for d in drafts.iter().take(6) {
            out.push_str(d);
            out.push('\n');
        }
    }
    if !facts.is_empty() {
        out.push_str("Remembered facts waiting:\n");
        for f in &facts {
            out.push_str(f);
            out.push('\n');
        }
    }
    if p.contact_keys.is_empty() && forms.is_empty() && mails.is_empty() && !out.contains("Texts ")
    {
        return Ok(format!("Nothing on record for \"{}\".", query.trim()));
    }
    out.push_str("memory_recall any key above for the full record.");
    Ok(out)
}

/// The template blanks a customer must never see ("[Your Name]", "{date}").
fn blank_in(text: &str) -> Option<String> {
    let re = regex_lite::Regex::new(r"(?i)[\[{<]{1,2}\s*(your|their|my|insert|client|customer|studio|shop|business|artist|first|last|full|recipient|date|time|phone|email|link|name|price|address)[^\]}>\n]{0,40}[\]}>]{1,2}").expect("valid regex");
    re.find(text).map(|m| m.as_str().to_string())
}

/// A held email reply, in the shape the mail carrier sends after approval.
pub fn email_draft(kh: &Arc<dyn KernelHandle>, input: &Value) -> Result<String, String> {
    let body = input["body"].as_str().unwrap_or("").trim().to_string();
    if body.is_empty() {
        return Err("Write the email's text in body.".into());
    }
    if let Some(b) = blank_in(&body) {
        return Err(format!("Not saved: the email still has a blank to fill in: {b}. Use the person's name from the record and sign as the studio, or leave that part out."));
    }
    let mut to = input["to"].as_str().unwrap_or("").trim().to_lowercase();
    let mut subject = input["subject"].as_str().unwrap_or("").trim().to_string();
    let (mut in_reply_to, mut references, mut to_name, mut source) =
        (String::new(), String::new(), String::new(), String::new());
    if let Some(k) = input["reply_to"]
        .as_str()
        .map(str::trim)
        .filter(|k| !k.is_empty())
    {
        let key = if k.starts_with("mail/") {
            k.to_string()
        } else {
            format!("mail/{k}")
        };
        let Some(m) = kh.memory_recall(&key)? else {
            return Err(format!(
                "No email at {key}. Use customer_lookup or memory_list prefix 'mail/' to find it."
            ));
        };
        let m = as_record(&m);
        if to.is_empty() {
            to = m["from"].as_str().unwrap_or("").to_lowercase();
        }
        to_name = m["from_name"].as_str().unwrap_or("").to_string();
        if subject.is_empty() {
            let s = m["subject"].as_str().unwrap_or("");
            subject = if s.to_lowercase().starts_with("re:") {
                s.to_string()
            } else {
                format!("Re: {s}")
            };
        }
        let mid = m["message_id"].as_str().unwrap_or("");
        if !mid.is_empty() {
            in_reply_to = mid.to_string();
            let refs = m["references"].as_str().unwrap_or("").trim();
            references = if refs.is_empty() {
                format!("<{mid}>")
            } else {
                format!("{refs} <{mid}>")
            };
        }
        source = key;
    }
    let ok_addr = to.split_once('@').is_some_and(|(a, d)| {
        !a.is_empty() && d.contains('.') && !to.contains(char::is_whitespace)
    });
    if !ok_addr {
        return Err(
            "Say who it goes to: reply_to an email on record, or a valid to address.".into(),
        );
    }
    if subject.is_empty() {
        return Err("Give the email a subject.".into());
    }
    let id = uuid::Uuid::new_v4().to_string();
    let key = format!("draft/{id}");
    let rec = json!({
        "kind": "email_send", "to": to, "to_name": to_name, "subject": subject, "body": body,
        "in_reply_to": in_reply_to, "references": references, "source_key": source,
        "status": "held", "drafted_by": "stax",
        "ts": chrono::Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true),
    });
    kh.memory_store(&key, rec)?;
    match kh.memory_recall(&key)? {
        Some(back) if as_record(&back)["body"].as_str() == Some(body.as_str()) => Ok(format!(
            "Email to {to} (\"{subject}\") is saved and waiting in Needs you for the owner's OK. Nothing is sent until they approve it."
        )),
        _ => Err("The email draft did not save. Nothing was changed — try again.".into()),
    }
}

/// The builder's own blocks, generated from forms.js (see
/// stax/tests/form_blocks_sync.test.js).
const FORM_BLOCKS: &str = include_str!("form_blocks.json");

fn palette() -> Vec<(String, Value)> {
    let v: Value = serde_json::from_str(FORM_BLOCKS).expect("form_blocks.json is valid");
    v["blocks"]
        .as_array()
        .map(|a| {
            a.iter()
                .map(|b| {
                    (
                        b["name"].as_str().unwrap_or("").to_string(),
                        b["block"].clone(),
                    )
                })
                .collect()
        })
        .unwrap_or_default()
}

/// The names of the blocks a form can use, by group.
pub fn block_names() -> String {
    let v: Value = serde_json::from_str(FORM_BLOCKS).expect("form_blocks.json is valid");
    let mut groups: Vec<(String, Vec<String>)> = Vec::new();
    for b in v["blocks"].as_array().cloned().unwrap_or_default() {
        let g = b["group"].as_str().unwrap_or("").to_string();
        let n = b["name"].as_str().unwrap_or("").to_string();
        match groups.iter_mut().find(|(x, _)| *x == g) {
            Some((_, l)) => l.push(n),
            None => groups.push((g, vec![n])),
        }
    }
    groups
        .iter()
        .map(|(g, l)| format!("{g}: {}", l.join(", ")))
        .collect::<Vec<_>>()
        .join(". ")
}

/// fbSlug: lowercase, runs of other characters become "-", 48 at most.
pub fn fb_slug(text: &str) -> String {
    let mut out = String::new();
    for ch in text.to_lowercase().chars() {
        if ch.is_ascii_lowercase() || ch.is_ascii_digit() {
            out.push(ch);
        } else if !out.ends_with('-') {
            out.push('-');
        }
    }
    out.trim_matches('-')
        .chars()
        .take(48)
        .collect::<String>()
        .trim_end_matches('-')
        .to_string()
}

/// fbUniqueKey: a key no other field uses, nor is a "<key>_" prefix of one.
pub fn fb_unique_key(base: &str, taken: &[String]) -> String {
    let stem = {
        let s = fb_slug(base).replace('-', "_");
        if s.is_empty() {
            "field".to_string()
        } else {
            s
        }
    };
    let clash = |k: &str| {
        taken
            .iter()
            .any(|t| t == k || t.starts_with(&format!("{k}_")) || k.starts_with(&format!("{t}_")))
    };
    if !clash(&stem) {
        return stem;
    }
    (2..500)
        .map(|n| format!("{stem}{n}"))
        .find(|k| !clash(k))
        .unwrap_or_else(|| format!("{stem}{}", chrono::Utc::now().timestamp()))
}

fn find_block(want: &str) -> Option<Value> {
    let w = want.trim().to_lowercase();
    let pal = palette();
    pal.iter()
        .find(|(n, b)| n.to_lowercase() == w || b["stype"].as_str() == Some(w.as_str()))
        .or_else(|| {
            pal.iter()
                .find(|(_, b)| b["label"].as_str().is_some_and(|l| l.to_lowercase() == w))
        })
        .map(|(_, b)| b.clone())
}

/// A form draft built from the builder's blocks, saved unpublished for the
/// owner to review in Forms. Same record shape the builder writes.
pub fn form_draft(kh: &Arc<dyn KernelHandle>, input: &Value) -> Result<String, String> {
    let title = input["title"].as_str().unwrap_or("").trim().to_string();
    if title.is_empty() {
        return Err("Give the form a name (title).".into());
    }
    let wanted = input["blocks"].as_array().cloned().unwrap_or_default();
    if wanted.is_empty() {
        return Err(format!(
            "Add at least one block. Blocks: {}.",
            block_names()
        ));
    }
    let mut fields: Vec<Value> = Vec::new();
    let mut keys: Vec<String> = Vec::new();
    for (i, w) in wanted.iter().enumerate() {
        let name = w["block"].as_str().or(w.as_str()).unwrap_or("");
        let Some(mut f) = find_block(name) else {
            return Err(format!(
                "Block {} (\"{name}\") is not one the builder has. Use one of: {}.",
                i + 1,
                block_names()
            ));
        };
        if let Some(l) = w["label"].as_str().map(str::trim).filter(|l| !l.is_empty()) {
            f["label"] = json!(l);
        }
        if let Some(r) = w["required"].as_bool() {
            f["required"] = json!(r);
        }
        let stype = f["stype"].as_str().unwrap_or("").to_string();
        if let Some(opts) = w["options"].as_array() {
            let opts: Vec<String> = opts
                .iter()
                .filter_map(|o| o.as_str())
                .map(|o| o.trim().to_string())
                .filter(|o| !o.is_empty())
                .collect();
            if !opts.is_empty() {
                f["config"]["options"] = json!(opts);
            }
        }
        if let Some(t) = w["text"].as_str().map(str::trim).filter(|t| !t.is_empty()) {
            f["config"]["text"] = json!(t);
        }
        if matches!(stype.as_str(), "field-dropdown" | "field-choice") {
            let n = f["config"]["options"]
                .as_array()
                .map(|a| a.len())
                .unwrap_or(0);
            let placeholder = f["config"]["options"].as_array().is_some_and(|a| {
                a.iter()
                    .any(|o| o.as_str().is_some_and(|s| s.starts_with("Option ")))
            });
            if n == 0 || placeholder {
                return Err(format!(
                    "\"{}\" needs its real choices in options.",
                    f["label"].as_str().unwrap_or(name)
                ));
            }
        }
        if stype != "field-paragraph" && f["label"].as_str().unwrap_or("").trim().is_empty() {
            return Err(format!(
                "Block {} needs a question or heading (label).",
                i + 1
            ));
        }
        let key = fb_unique_key(f["label"].as_str().unwrap_or(name), &keys);
        keys.push(key.clone());
        let mut keyed = serde_json::Map::new();
        keyed.insert("key".into(), json!(key));
        if let Some(o) = f.as_object() {
            for (k, v) in o {
                keyed.insert(k.clone(), v.clone());
            }
        }
        fields.push(Value::Object(keyed));
    }
    let taken: BTreeSet<String> = kh
        .memory_list("form/")?
        .into_iter()
        .filter(|(_, v)| !as_record(v)["deleted"].as_bool().unwrap_or(false))
        .map(|(k, _)| k["form/".len()..].to_string())
        .collect();
    let stem = {
        let s = fb_slug(input["slug"].as_str().unwrap_or(&title));
        if s.is_empty() {
            "form".to_string()
        } else {
            s
        }
    };
    let slug = if !taken.contains(&stem) {
        stem.clone()
    } else {
        (2..500)
            .map(|n| format!("{stem}-{n}"))
            .find(|s| !taken.contains(s))
            .unwrap_or_else(|| format!("{stem}-{}", chrono::Utc::now().timestamp()))
    };
    let now = chrono::Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Millis, true);
    let rec = json!({"title": title, "fields": fields, "published": false, "drafted_by": "stax", "created": now, "updated": now});
    let key = format!("form/{slug}");
    kh.memory_store(&key, rec)?;
    let back = kh.memory_recall(&key)?.map(|v| as_record(&v));
    let ok = back.is_some_and(|b| {
        b["title"].as_str() == Some(title.as_str())
            && b["fields"].as_array().map(|a| a.len()) == Some(fields.len())
    });
    if !ok {
        return Err("The form did not save. Nothing was changed — try again.".into());
    }
    let list: Vec<String> = fields
        .iter()
        .map(|f| f["label"].as_str().unwrap_or("").to_string())
        .collect();
    Ok(format!(
        "Drafted \"{title}\" with {} blocks: {}. It is saved in Forms as a draft, not published — the owner opens it there to review, change and publish it.",
        fields.len(),
        list.join(", ")
    ))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn slugs_and_keys_match_the_builder() {
        assert_eq!(fb_slug("Tattoo Consent — 2026!"), "tattoo-consent-2026");
        assert_eq!(fb_slug("  "), "");
        let taken = vec!["client_details".to_string(), "name".to_string()];
        assert_eq!(fb_unique_key("Name", &taken), "name2");
        assert_eq!(fb_unique_key("Client", &taken), "client2");
        assert_eq!(fb_unique_key("Signature", &taken), "signature");
        assert_eq!(fb_unique_key("!!!", &taken), "field");
    }

    #[test]
    fn palette_has_the_builder_blocks() {
        let names = block_names();
        for n in [
            "Heading",
            "Email",
            "Medical disclosure",
            "Signature",
            "Artist",
            "Reference photos",
        ] {
            assert!(names.contains(n), "{n} missing: {names}");
        }
        assert!(find_block("consent-signature").is_some());
        assert!(find_block("signature").is_some());
        assert!(find_block("Your name").is_some(), "by label too");
        assert!(find_block("hologram").is_none());
    }

    #[test]
    fn people_merge_and_match() {
        let recs = vec![
            (
                "contact/7015550101".to_string(),
                json!({"name": "Jane Ink", "phone": "+1 (701) 555-0101", "email": "jane@ink.test"}),
            ),
            (
                "contact/jane@ink.test".to_string(),
                json!({"name": "Jane Ink"}),
            ),
            (
                "contact/sam@example.com".to_string(),
                json!({"name": "Sam Rivera"}),
            ),
            (
                "contact/7015550199".to_string(),
                json!({"name": "Janet Moss"}),
            ),
        ];
        let all = people(&recs);
        assert_eq!(all.len(), 3, "Jane's two records are one person");
        assert_eq!(matching(&all, "jane ink").len(), 1);
        assert_eq!(matching(&all, "jan").len(), 2, "Jane and Janet");
        assert_eq!(matching(&all, "(701) 555-0101")[0].name, "Jane Ink");
        assert_eq!(matching(&all, "JANE@ink.test")[0].name, "Jane Ink");
        assert!(matching(&all, "nobody").is_empty());
    }
}
