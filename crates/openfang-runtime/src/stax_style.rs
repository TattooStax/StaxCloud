//! The Style helper's bookkeeping, done in code.
//!
//! The model used to find portfolio pictures, check which it had already
//! read, date the records, count categories and rebuild each artist's
//! profile — and it got those wrong (a picture stored twice, invented dates,
//! counts that didn't match, its own schedule deleted). Now one tool call,
//! `style_learn`, does all of it: it finds the pictures, skips the ones
//! already read, has the vision model read each new one with a fixed
//! question, stores one record per picture, and rebuilds the touched
//! artists' profiles from their records. `style_correct` applies an owner's
//! correction and rebuilds both profiles. The model only decides when to
//! call them and tells the owner what happened.
//!
//! Records (shared memory):
//! - `portfolio/<artist-slug>/<picture-id>` — one per tattoo picture read.
//! - `portfolioskip/<picture-id>` — a picture read that is not a tattoo
//!   (logo, shop photo, flyer), so it is never read again.
//! - `style/<artist-slug>` — the artist's profile, rebuilt from records.
//! - `stylequeue` — `{"pending": [picture urls], "checked_at"}`: pictures
//!   found but not read yet. The catch-up schedule only wakes while this
//!   holds something.

use crate::kernel_handle::KernelHandle;
use crate::stax_images::{self, Picture};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, HashSet};
use std::sync::Arc;

/// Style categories, in the words the profiles use.
pub const CATEGORIES: [&str; 13] = [
    "black and grey realism",
    "color realism",
    "portrait",
    "fine line",
    "lettering",
    "traditional",
    "neo-traditional",
    "japanese",
    "blackwork",
    "geometric",
    "illustrative",
    "cover-up",
    "other",
];

/// The one question every portfolio picture is asked.
pub const VISION_PROMPT: &str = "This is from a tattoo studio portfolio. Is it a photo of a tattoo (finished, healed, or a drawn design)? Reply with JSON only: {\"finished_tattoo\": true|false, \"style\": one of [black and grey realism, color realism, portrait, fine line, lettering, traditional, neo-traditional, japanese, blackwork, geometric, illustrative, cover-up, other], \"also\": [other categories that clearly apply], \"subject\": \"<a few words>\", \"placement\": \"<body part or unknown>\", \"linework\": \"<a few words>\", \"shading\": \"<a few words>\"}";

/// Most new pictures read in one call.
pub const DEFAULT_BATCH: usize = 12;
/// Most pages looked at for pictures in one call.
const MAX_PAGES: usize = 10;

/// A picture's identity: the same picture at another size or with a cache
/// query (`photo-300x200.jpg?v=3`) is the same picture.
pub fn picture_id(url: &str) -> String {
    let mut u = url.trim().to_lowercase();
    if let Some(i) = u.find(['?', '#']) {
        u.truncate(i);
    }
    for scheme in ["https://", "http://"] {
        if let Some(rest) = u.strip_prefix(scheme) {
            u = rest.to_string();
        }
    }
    if let Some(rest) = u.strip_prefix("www.") {
        u = rest.to_string();
    }
    // Drop a size suffix and the extension: name-300x200.webp -> name
    let (stem, _) = match u.rfind('.') {
        Some(dot) if dot > u.rfind('/').unwrap_or(0) => (u[..dot].to_string(), &u[dot..]),
        _ => (u.clone(), ""),
    };
    let re =
        regex_lite::Regex::new(r"[-_@](\d{2,5}x\d{2,5}|\d{1,2}x|scaled|thumb|small|medium|large)$")
            .expect("valid regex");
    let stem = re.replace(&stem, "").to_string();
    let d = Sha256::digest(stem.as_bytes());
    hex::encode(&d[..8])
}

/// The category a free-text style answer means.
pub fn normalize_style(s: &str) -> String {
    let t = s.trim().to_lowercase().replace(['_', '-'], " ");
    if t.is_empty() {
        return "other".into();
    }
    for c in CATEGORIES {
        if t == c.replace('-', " ") {
            return c.to_string();
        }
    }
    let rules: [(&str, &str); 16] = [
        ("neo trad", "neo-traditional"),
        ("neotrad", "neo-traditional"),
        ("black and gr", "black and grey realism"),
        ("black & gr", "black and grey realism"),
        ("black and gray", "black and grey realism"),
        ("color real", "color realism"),
        ("colour real", "color realism"),
        ("portrait", "portrait"),
        ("fine line", "fine line"),
        ("fineline", "fine line"),
        ("letter", "lettering"),
        ("script", "lettering"),
        ("japan", "japanese"),
        ("irezumi", "japanese"),
        ("cover", "cover-up"),
        ("geometr", "geometric"),
    ];
    for (needle, cat) in rules {
        if t.contains(needle) {
            return cat.to_string();
        }
    }
    for (needle, cat) in [
        ("traditional", "traditional"),
        ("blackwork", "blackwork"),
        ("illustr", "illustrative"),
        ("realism", "black and grey realism"),
    ] {
        if t.contains(needle) {
            return cat.to_string();
        }
    }
    "other".into()
}

/// What the vision model said about one picture.
#[derive(Debug, Clone, PartialEq, Default)]
pub struct Reading {
    pub finished_tattoo: bool,
    pub style: String,
    pub also: Vec<String>,
    pub subject: String,
    pub placement: String,
    pub linework: String,
    pub shading: String,
}

/// The JSON object in a vision reply (models wrap it in prose or fences).
pub fn parse_reading(text: &str) -> Option<Reading> {
    let start = text.find('{')?;
    let end = text.rfind('}')?;
    if end <= start {
        return None;
    }
    let v: Value = serde_json::from_str(&text[start..=end]).ok()?;
    let s = |k: &str| v[k].as_str().unwrap_or("").trim().to_string();
    let finished = match &v["finished_tattoo"] {
        Value::Bool(b) => *b,
        Value::String(x) => x.eq_ignore_ascii_case("true"),
        _ => false,
    };
    let style = normalize_style(&s("style"));
    let mut also: Vec<String> = v["also"]
        .as_array()
        .map(|a| {
            a.iter()
                .filter_map(|x| x.as_str())
                .map(normalize_style)
                .collect()
        })
        .unwrap_or_default();
    also.retain(|c| c != &style && c != "other");
    also.dedup();
    Some(Reading {
        finished_tattoo: finished,
        style,
        also,
        subject: s("subject"),
        placement: if s("placement").is_empty() {
            "unknown".into()
        } else {
            s("placement")
        },
        linework: s("linework"),
        shading: s("shading"),
    })
}

/// An artist the studio has on record.
#[derive(Debug, Clone, PartialEq)]
pub struct Artist {
    pub slug: String,
    pub name: String,
}

/// Lowercase words joined by "-": "Leni Bee" -> "leni-bee".
pub fn slug(name: &str) -> String {
    let mut out = String::new();
    for ch in name.trim().to_lowercase().chars() {
        if ch.is_ascii_alphanumeric() {
            out.push(ch);
        } else if !out.ends_with('-') && !out.is_empty() {
            out.push('-');
        }
    }
    out.trim_end_matches('-').to_string()
}

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

/// Artists from `artist/<id>` records, plus any already in style profiles.
pub fn artists_from(records: &[(String, Value)]) -> Vec<Artist> {
    let mut out: Vec<Artist> = Vec::new();
    let mut push = |name: &str| {
        let name = name.trim();
        let s = slug(name);
        if !s.is_empty() && s != "unassigned" && !out.iter().any(|a| a.slug == s) {
            out.push(Artist {
                slug: s,
                name: name.to_string(),
            });
        }
    };
    for (k, v) in records {
        let r = as_record(v);
        if k.starts_with("artist/") && k != "artist/index" {
            let name = r["display_name"]
                .as_str()
                .or(r["name"].as_str())
                .unwrap_or(&k[7..])
                .to_string();
            push(&name);
        } else if k.starts_with("style/") && k.matches('/').count() == 1 {
            if let Some(n) = r["artist"].as_str() {
                push(n);
            }
        }
    }
    out
}

/// Whose work a picture is: an artist named in the page address or the
/// picture's alt text (first name or full name, as whole words). A shared
/// gallery that names nobody gives None — the picture stays unassigned.
pub fn artist_for(page_url: &str, alt: &str, artists: &[Artist]) -> Option<Artist> {
    let path = page_url
        .split("://")
        .nth(1)
        .and_then(|r| r.split_once('/').map(|(_, p)| p))
        .unwrap_or("")
        .to_lowercase();
    let path_words: Vec<&str> = path
        .split(|c: char| !c.is_ascii_alphanumeric())
        .filter(|w| !w.is_empty())
        .collect();
    let alt_l = alt.to_lowercase();
    let alt_words: Vec<&str> = alt_l
        .split(|c: char| !c.is_alphanumeric())
        .filter(|w| !w.is_empty())
        .collect();
    let mut hits: Vec<&Artist> = Vec::new();
    for a in artists {
        let words: Vec<String> = a.slug.split('-').map(String::from).collect();
        let first = words.first().cloned().unwrap_or_default();
        if first.len() < 2 {
            continue;
        }
        let in_path = path.contains(&a.slug) || path_words.contains(&first.as_str());
        let in_alt = alt_words.contains(&first.as_str());
        if in_path || in_alt {
            hits.push(a);
        }
    }
    // Two artists named on one page = a shared gallery: nobody's for sure.
    if hits.len() == 1 {
        Some(hits[0].clone())
    } else {
        None
    }
}

/// Same-site links on a page that may hold portfolio pictures: gallery,
/// portfolio, work or artist pages, or a page named after an artist.
pub fn portfolio_links(html: &str, base: &reqwest::Url, artists: &[Artist]) -> Vec<String> {
    let re =
        regex_lite::Regex::new(r#"(?is)<a\b[^>]*\bhref\s*=\s*["']([^"'#]+)["'][^>]*>(.*?)</a>"#)
            .expect("valid regex");
    let tag = regex_lite::Regex::new(r"(?s)<[^>]+>").expect("valid regex");
    let words = [
        "portfolio",
        "gallery",
        "work",
        "artist",
        "tattoos",
        "flash",
        "our-team",
        "team",
    ];
    let mut out: Vec<String> = Vec::new();
    for c in re.captures_iter(html) {
        let href = c.get(1).map(|m| m.as_str()).unwrap_or("");
        let text = tag
            .replace_all(c.get(2).map(|m| m.as_str()).unwrap_or(""), " ")
            .to_lowercase();
        let Ok(url) = base.join(href.trim()) else {
            continue;
        };
        if url.host_str() != base.host_str() || !matches!(url.scheme(), "http" | "https") {
            continue;
        }
        let path = url.path().to_lowercase();
        if path == "/" || path.is_empty() {
            continue;
        }
        let hit = words.iter().any(|w| path.contains(w) || text.contains(w))
            || artists.iter().any(|a| {
                let first = a.slug.split('-').next().unwrap_or("");
                first.len() >= 2
                    && (path.contains(first)
                        || text
                            .split_whitespace()
                            .any(|t| t.trim_matches(|c: char| !c.is_alphanumeric()) == first))
            });
        let mut u = url.clone();
        u.set_fragment(None);
        let s = u.to_string();
        if hit && !out.contains(&s) {
            out.push(s);
        }
    }
    out
}

/// Every web address in a record (the studio profile, an artist record).
pub fn urls_in(v: &Value) -> Vec<String> {
    let re = regex_lite::Regex::new(r#"https?://[^\s"'<>),]+"#).expect("valid regex");
    let mut out = Vec::new();
    fn walk(v: &Value, re: &regex_lite::Regex, out: &mut Vec<String>) {
        match v {
            Value::String(s) => {
                for m in re.find_iter(s) {
                    let u = m.as_str().trim_end_matches(['.', ';']).to_string();
                    if !out.contains(&u) {
                        out.push(u);
                    }
                }
            }
            Value::Array(a) => a.iter().for_each(|x| walk(x, re, out)),
            Value::Object(o) => o.values().for_each(|x| walk(x, re, out)),
            _ => {}
        }
    }
    walk(&as_record(v), &re, &mut out);
    out
}

fn top_words(texts: &[&str], n: usize) -> Vec<String> {
    let mut count: BTreeMap<String, usize> = BTreeMap::new();
    for t in texts {
        let t = t.trim().to_lowercase();
        if t.is_empty() || t == "unknown" {
            continue;
        }
        *count.entry(t).or_default() += 1;
    }
    let mut v: Vec<(String, usize)> = count.into_iter().collect();
    v.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(&b.0)));
    v.into_iter().take(n).map(|(w, _)| w).collect()
}

/// An artist's profile, rebuilt from their portfolio records. Counts,
/// specialties, examples and the date come from the records and the clock;
/// the note is assembled from what the pictures' readings actually said.
/// Fields the owner set by hand (named in the old profile's "owner_set")
/// are kept as they were.
pub fn rebuild_profile(
    artist: &Artist,
    records: &[Value],
    old: Option<&Value>,
    now: &str,
) -> Value {
    let mut cats: BTreeMap<String, u64> = BTreeMap::new();
    for r in records {
        if let Some(s) = r["style"].as_str() {
            *cats.entry(s.to_string()).or_default() += 1;
        }
    }
    let mut ranked: Vec<(String, u64)> = cats.iter().map(|(k, v)| (k.clone(), *v)).collect();
    ranked.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(&b.0)));
    let specialties: Vec<String> = ranked
        .iter()
        .filter(|(c, _)| c != "other")
        .take(4)
        .map(|(c, _)| c.clone())
        .collect();

    let mut exemplars = Vec::new();
    for (cat, _) in ranked.iter().take(3) {
        let mut picked = 0;
        for r in records
            .iter()
            .filter(|r| r["style"].as_str() == Some(cat.as_str()))
        {
            if picked == 3 {
                break;
            }
            if let Some(fid) = r["file_id"].as_str() {
                exemplars.push(json!({"file_id": fid, "category": cat, "subject": r["subject"].as_str().unwrap_or("")}));
                picked += 1;
            }
        }
    }

    let lw: Vec<&str> = records
        .iter()
        .filter_map(|r| r["linework"].as_str())
        .collect();
    let sh: Vec<&str> = records
        .iter()
        .filter_map(|r| r["shading"].as_str())
        .collect();
    let subj: Vec<&str> = records
        .iter()
        .filter_map(|r| r["subject"].as_str())
        .collect();
    let n = records.len();
    let mut note = String::new();
    if let Some((top, c)) = ranked.first() {
        note.push_str(&format!("Mostly {top} ({c} of {n} pieces read)"));
        if specialties.len() > 1 {
            note.push_str(&format!(", also {}", specialties[1..].join(", ")));
        }
        note.push('.');
    }
    let lw = top_words(&lw, 2);
    let sh = top_words(&sh, 2);
    if !lw.is_empty() {
        note.push_str(&format!(" Linework: {}.", lw.join("; ")));
    }
    if !sh.is_empty() {
        note.push_str(&format!(" Shading: {}.", sh.join("; ")));
    }
    let subj = top_words(&subj, 3);
    if !subj.is_empty() {
        note.push_str(&format!(" Subjects include {}.", subj.join(", ")));
    }

    let mut out = json!({
        "artist": artist.name,
        "artist_slug": artist.slug,
        "photo_count": n,
        "categories": cats,
        "specialties": specialties,
        "style_note": note.trim(),
        "exemplars": exemplars,
        "updated": now,
        "learned_from": "portfolio",
    });
    if let Some(old) = old.map(as_record) {
        if let Some(owned) = old["owner_set"].as_array() {
            for f in owned.iter().filter_map(|f| f.as_str()) {
                if let Some(v) = old.get(f) {
                    out[f] = v.clone();
                }
            }
            out["owner_set"] = Value::Array(owned.clone());
        }
    }
    out
}

/// Where pictures come from and how they are read — the real web and
/// vision model in use, a fake in tests.
#[async_trait::async_trait]
pub trait PictureSource: Send + Sync {
    async fn html(&self, url: &str) -> Result<(String, reqwest::Url), String>;
    async fn picture(&self, url: &str) -> Result<Picture, String>;
    /// The vision model's answer to VISION_PROMPT, and its cost.
    async fn read(&self, picture: &Picture) -> Result<(String, Option<f64>), String>;
}

/// The real web and the configured vision model.
pub struct LiveSource;

#[async_trait::async_trait]
impl PictureSource for LiveSource {
    async fn html(&self, url: &str) -> Result<(String, reqwest::Url), String> {
        stax_images::page_html(url).await
    }
    async fn picture(&self, url: &str) -> Result<Picture, String> {
        stax_images::fetch(url).await
    }
    async fn read(&self, picture: &Picture) -> Result<(String, Option<f64>), String> {
        stax_images::describe(picture, VISION_PROMPT, &stax_images::vision_model()).await
    }
}

/// Saves a picture and returns its upload id.
pub type SavePicture<'a> = dyn Fn(&Picture) -> Result<String, String> + Send + Sync + 'a;

fn now_iso() -> String {
    chrono::Local::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, false)
}

/// One sweep: find portfolio pictures, read up to `max` new ones, store
/// them, rebuild touched profiles, and leave the rest in `stylequeue`.
/// `pages` are extra pages to look at, each optionally for a named artist.
pub async fn learn(
    kh: &Arc<dyn KernelHandle>,
    web: &dyn PictureSource,
    save: &SavePicture<'_>,
    pages: &[(String, Option<String>)],
    max: usize,
) -> Result<String, String> {
    let tidied = tidy_old_records(kh)?;
    let records = kh.memory_list("")?;
    let artists = artists_from(&records);
    let profile = records
        .iter()
        .find(|(k, _)| k == "setup/profile")
        .map(|(_, v)| v.clone())
        .unwrap_or(Value::Null);

    // Pages to look at: those given, then known portfolio pages, then the
    // studio's and artists' own addresses and their portfolio links.
    let mut to_visit: Vec<(String, Option<Artist>)> = Vec::new();
    let add = |url: String, who: Option<Artist>, list: &mut Vec<(String, Option<Artist>)>| {
        if !list.iter().any(|(u, _)| u == &url) {
            list.push((url, who));
        }
    };
    for (u, a) in pages {
        let who = a.as_deref().map(|n| {
            artists
                .iter()
                .find(|x| x.slug == slug(n))
                .cloned()
                .unwrap_or(Artist {
                    slug: slug(n),
                    name: n.to_string(),
                })
        });
        add(u.clone(), who, &mut to_visit);
    }
    for (k, v) in &records {
        if k.starts_with("portfolio/") {
            if let Some(p) = as_record(v)["page"].as_str() {
                add(p.to_string(), None, &mut to_visit);
            }
        }
    }
    let mut homes: Vec<(String, Option<Artist>)> =
        urls_in(&profile).into_iter().map(|u| (u, None)).collect();
    for (k, v) in &records {
        if k.starts_with("artist/") && k != "artist/index" {
            let r = as_record(v);
            let name = r["display_name"]
                .as_str()
                .or(r["name"].as_str())
                .unwrap_or("");
            let who = artists.iter().find(|a| a.slug == slug(name)).cloned();
            for u in urls_in(&r) {
                homes.push((u, who.clone()));
            }
        }
    }
    let mut notes: Vec<String> = Vec::new();
    for (home, who) in homes.iter().take(4) {
        add(home.clone(), who.clone(), &mut to_visit);
        if let Ok((html, base)) = web.html(home).await {
            for link in portfolio_links(&html, &base, &artists) {
                add(link, who.clone(), &mut to_visit);
            }
        }
    }
    if to_visit.is_empty() {
        return Ok("No website or portfolio address on record. Ask the owner for the studio's website or a portfolio link, then call style_learn with it in pages.".into());
    }

    // Pictures on those pages, newest page order, minus the ones read.
    let mut known: HashSet<String> = records
        .iter()
        .filter(|(k, _)| k.starts_with("portfolio/") || k.starts_with("portfolioskip/"))
        .filter_map(|(k, _)| k.rsplit('/').next().map(String::from))
        .collect();
    for (k, v) in &records {
        if k.starts_with("portfolio/") || k.starts_with("portfolioskip/") {
            if let Some(u) = as_record(v)["source_url"].as_str() {
                known.insert(picture_id(u));
            }
        }
    }
    let mut found: Vec<(String, String, String, Option<Artist>)> = Vec::new(); // id, url, page, artist
    let mut seen: HashSet<String> = HashSet::new();
    let mut pages_read = 0;
    for (page, who) in to_visit.iter().take(MAX_PAGES) {
        let Ok((html, base)) = web.html(page).await else {
            notes.push(format!("couldn't open {page}"));
            continue;
        };
        pages_read += 1;
        for img in stax_images::images_in_html(&html, &base) {
            let id = picture_id(&img.url);
            if known.contains(&id) || !seen.insert(id.clone()) {
                continue;
            }
            let artist = who.clone().or_else(|| artist_for(page, &img.alt, &artists));
            found.push((id, img.url.clone(), page.clone(), artist));
        }
    }

    let mut learned: BTreeMap<String, usize> = BTreeMap::new();
    let (mut skipped, mut failed, mut unassigned) = (0, 0, 0);
    let mut touched: HashSet<String> = HashSet::new();
    let mut cost = 0.0;
    let now = now_iso();
    for (id, url, page, artist) in found.iter().take(max) {
        let pic = match web.picture(url).await {
            Ok(p) => p,
            Err(_) => {
                failed += 1;
                continue;
            }
        };
        let reading = match web.read(&pic).await {
            Ok((text, c)) => {
                cost += c.unwrap_or(0.0);
                parse_reading(&text)
            }
            Err(_) => None,
        };
        let Some(r) = reading else {
            failed += 1;
            continue;
        };
        if !r.finished_tattoo {
            kh.memory_store(&format!("portfolioskip/{id}"), json!({"source_url": url, "page": page, "reason": "not a tattoo", "checked_at": now}))?;
            skipped += 1;
            continue;
        }
        let file_id = save(&pic)?;
        let (aslug, aname) = match artist {
            Some(a) => (a.slug.clone(), a.name.clone()),
            None => {
                unassigned += 1;
                ("unassigned".to_string(), "unassigned".to_string())
            }
        };
        kh.memory_store(
            &format!("portfolio/{aslug}/{id}"),
            json!({
                "artist": aname, "file_id": file_id, "source_url": url, "page": page,
                "style": r.style, "also": r.also, "subject": r.subject, "placement": r.placement,
                "linework": r.linework, "shading": r.shading, "finished_tattoo": true, "learned_at": now,
            }),
        )?;
        *learned.entry(aname.clone()).or_default() += 1;
        if aslug != "unassigned" {
            touched.insert(aslug);
        }
    }

    touched.extend(tidied.iter().cloned());
    for s in &touched {
        rebuild(kh, s, &now)?;
    }
    let pending: Vec<String> = found
        .iter()
        .skip(max)
        .map(|(_, u, _, _)| u.clone())
        .collect();
    kh.memory_store("stylequeue", json!({"pending": pending, "checked_at": now}))?;

    let mut out = format!(
        "Looked at {pages_read} page(s), found {} new picture(s). Learned {} tattoo picture(s)",
        found.len(),
        learned.values().sum::<usize>()
    );
    if !learned.is_empty() {
        let parts: Vec<String> = learned.iter().map(|(a, n)| format!("{a}: {n}")).collect();
        out.push_str(&format!(" ({})", parts.join(", ")));
    }
    out.push_str(&format!(". Not tattoos: {skipped}. Couldn't read: {failed}. Unassigned: {unassigned}. Still to read: {}.", pending.len()));
    for s in &touched {
        if let Ok(Some(p)) = kh.memory_recall(&format!("style/{s}")) {
            let p = as_record(&p);
            out.push_str(&format!(
                " {}: {} pieces, mostly {}.",
                p["artist"].as_str().unwrap_or(s),
                p["photo_count"],
                p["specialties"]
                    .as_array()
                    .and_then(|a| a.first())
                    .and_then(|x| x.as_str())
                    .unwrap_or("not sure yet")
            ));
        }
    }
    if !tidied.is_empty() {
        out.push_str(" Older records were tidied (duplicates merged, profiles recounted).");
    }
    if cost > 0.0 {
        out.push_str(&format!(" (Reading cost about ${cost:.3}.)"));
    }
    if !notes.is_empty() {
        out.push_str(&format!(" Notes: {}.", notes.join("; ")));
    }
    Ok(out)
}

/// Records written before this code (keyed by upload id, possibly the
/// same picture twice) are re-keyed by picture identity, one per picture
/// per artist. Returns the artists whose records changed.
pub fn tidy_old_records(kh: &Arc<dyn KernelHandle>) -> Result<Vec<String>, String> {
    let mut changed: Vec<String> = Vec::new();
    let all = kh.memory_list("portfolio/")?;
    let mut have: HashSet<String> = all.iter().map(|(k, _)| k.clone()).collect();
    for (key, v) in &all {
        let parts: Vec<&str> = key.splitn(3, '/').collect();
        if parts.len() != 3 {
            continue;
        }
        let rec = as_record(v);
        let Some(url) = rec["source_url"].as_str().filter(|u| !u.is_empty()) else {
            continue;
        };
        let pid = picture_id(url);
        if parts[2] == pid {
            continue;
        }
        let target = format!("portfolio/{}/{pid}", parts[1]);
        if !have.contains(&target) {
            kh.memory_store(&target, rec.clone())?;
            have.insert(target);
        }
        kh.memory_delete(key)?;
        have.remove(key);
        if parts[1] != "unassigned" && !changed.iter().any(|c| c == parts[1]) {
            changed.push(parts[1].to_string());
        }
    }
    Ok(changed)
}

/// Rebuild one artist's profile from their portfolio records.
pub fn rebuild(kh: &Arc<dyn KernelHandle>, artist_slug: &str, now: &str) -> Result<(), String> {
    let recs: Vec<Value> = kh
        .memory_list(&format!("portfolio/{artist_slug}/"))?
        .into_iter()
        .map(|(_, v)| as_record(&v))
        .collect();
    let old = kh.memory_recall(&format!("style/{artist_slug}"))?;
    let name = recs
        .iter()
        .find_map(|r| r["artist"].as_str().map(String::from))
        .or_else(|| {
            old.as_ref()
                .and_then(|o| as_record(o)["artist"].as_str().map(String::from))
        })
        .unwrap_or_else(|| artist_slug.to_string());
    let artist = Artist {
        slug: artist_slug.to_string(),
        name,
    };
    if recs.is_empty() {
        return Ok(());
    }
    kh.memory_store(
        &format!("style/{artist_slug}"),
        rebuild_profile(&artist, &recs, old.as_ref(), now),
    )
}

/// The owner's correction: a picture is another artist's, or another
/// style. Moves or edits the record and rebuilds every profile touched.
pub fn correct(
    kh: &Arc<dyn KernelHandle>,
    picture: &str,
    artist: Option<&str>,
    style: Option<&str>,
) -> Result<String, String> {
    let needle = picture.trim().to_lowercase();
    if needle.is_empty() {
        return Err("Say which picture: its address, its subject words, or its id.".into());
    }
    let id_guess = if needle.starts_with("http") {
        picture_id(&needle)
    } else {
        String::new()
    };
    let all = kh.memory_list("portfolio/")?;
    let hits: Vec<&(String, Value)> = all
        .iter()
        .filter(|(k, v)| {
            let r = as_record(v);
            k.ends_with(&format!("/{needle}"))
                || (!id_guess.is_empty() && k.ends_with(&format!("/{id_guess}")))
                || r["file_id"].as_str() == Some(picture.trim())
                || r["subject"]
                    .as_str()
                    .is_some_and(|s| s.to_lowercase().contains(&needle))
        })
        .collect();
    match hits.len() {
        0 => return Err(format!("No portfolio picture matches \"{picture}\". Use memory_list prefix 'portfolio/' to find it.")),
        1 => {}
        n => {
            let names: Vec<String> = hits.iter().map(|(k, v)| format!("{k} ({})", as_record(v)["subject"].as_str().unwrap_or(""))).collect();
            return Err(format!("{n} pictures match — say which one: {}", names.join("; ")));
        }
    }
    let (key, val) = hits[0];
    let mut rec = as_record(val);
    let old_slug = key.split('/').nth(1).unwrap_or("unassigned").to_string();
    let id = key.rsplit('/').next().unwrap_or("").to_string();
    let now = now_iso();
    if let Some(s) = style {
        rec["style"] = json!(normalize_style(s));
    }
    let mut new_slug = old_slug.clone();
    if let Some(a) = artist {
        let name = a.trim();
        new_slug = if name.eq_ignore_ascii_case("unassigned") {
            "unassigned".into()
        } else {
            slug(name)
        };
        rec["artist"] = json!(if new_slug == "unassigned" {
            "unassigned"
        } else {
            name
        });
    }
    rec["corrected_at"] = json!(now);
    kh.memory_store(&format!("portfolio/{new_slug}/{id}"), rec.clone())?;
    if new_slug != old_slug {
        kh.memory_delete(key)?;
    }
    for s in [&old_slug, &new_slug] {
        if s != "unassigned" {
            rebuild(kh, s, &now)?;
        }
    }
    Ok(format!(
        "Done: \"{}\" is now {}'s, {}. Profiles rebuilt.",
        rec["subject"].as_str().unwrap_or("that picture"),
        rec["artist"].as_str().unwrap_or("unassigned"),
        rec["style"].as_str().unwrap_or("")
    ))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn same_picture_any_size_same_id() {
        let a = picture_id("https://fargotattoo.com/wp-content/uploads/rose-300x200.jpg?v=2");
        let b = picture_id("http://www.fargotattoo.com/wp-content/uploads/rose.webp");
        let c = picture_id("https://fargotattoo.com/wp-content/uploads/rose-1024x683.jpg");
        assert_eq!(a, b);
        assert_eq!(a, c);
        assert_ne!(
            a,
            picture_id("https://fargotattoo.com/wp-content/uploads/lily.jpg")
        );
        assert_eq!(a.len(), 16);
    }

    #[test]
    fn styles_normalize_to_the_categories() {
        assert_eq!(
            normalize_style("Black & Grey Realism"),
            "black and grey realism"
        );
        assert_eq!(normalize_style("neo traditional"), "neo-traditional");
        assert_eq!(normalize_style("Traditional"), "traditional");
        assert_eq!(normalize_style("fineline"), "fine line");
        assert_eq!(normalize_style("script lettering"), "lettering");
        assert_eq!(normalize_style("watercolor"), "other");
        assert_eq!(normalize_style(""), "other");
    }

    #[test]
    fn readings_parse_from_chatty_replies() {
        let r = parse_reading("Sure! ```json\n{\"finished_tattoo\": true, \"style\": \"Black and grey\", \"also\": [\"portrait\", \"black and grey realism\"], \"subject\": \"lion\", \"placement\": \"\", \"linework\": \"fine\", \"shading\": \"smooth\"}\n```").unwrap();
        assert!(r.finished_tattoo);
        assert_eq!(r.style, "black and grey realism");
        assert_eq!(r.also, vec!["portrait"]);
        assert_eq!(r.placement, "unknown");
        assert!(parse_reading("no json here").is_none());
        assert!(
            !parse_reading("{\"finished_tattoo\": \"false\"}")
                .unwrap()
                .finished_tattoo
        );
    }

    fn crew() -> Vec<Artist> {
        vec![
            Artist {
                slug: "shawn-lowe".into(),
                name: "Shawn Lowe".into(),
            },
            Artist {
                slug: "leni-b".into(),
                name: "Leni B.".into(),
            },
        ]
    }

    #[test]
    fn artist_from_page_or_alt_never_a_guess() {
        let a = crew();
        assert_eq!(
            artist_for("https://fargotattoo.com/leni-b/", "", &a)
                .unwrap()
                .slug,
            "leni-b"
        );
        assert_eq!(
            artist_for("https://fargotattoo.com/artists/shawn", "", &a)
                .unwrap()
                .slug,
            "shawn-lowe"
        );
        assert_eq!(
            artist_for("https://fargotattoo.com/gallery", "Rose by Leni", &a)
                .unwrap()
                .slug,
            "leni-b"
        );
        assert!(
            artist_for("https://fargotattoo.com/gallery", "a rose", &a).is_none(),
            "shared gallery stays unassigned"
        );
        assert!(
            artist_for(
                "https://fargotattoo.com/gallery",
                "Shawn and Leni collab",
                &a
            )
            .is_none(),
            "two names = not sure"
        );
        assert!(
            artist_for("https://fargotattoo.com/shawnee-county", "", &a).is_none(),
            "whole words only"
        );
    }

    #[test]
    fn finds_portfolio_links_on_the_same_site() {
        let base = reqwest::Url::parse("https://fargotattoo.com/").unwrap();
        let html = r#"<a href="/gallery/">Gallery</a> <a href="/leni-b">Leni</a> <a href="https://instagram.com/x">IG</a>
            <a href="/aftercare">Aftercare</a> <a href="/">Home</a> <a href="/meet"><span>Shawn</span></a>"#;
        let links = portfolio_links(html, &base, &crew());
        assert_eq!(
            links,
            vec![
                "https://fargotattoo.com/gallery/",
                "https://fargotattoo.com/leni-b",
                "https://fargotattoo.com/meet"
            ]
        );
    }

    #[test]
    fn urls_are_found_in_any_record() {
        let v = json!({"business": "Fargo Tattoo — site https://fargotattoo.com, IG https://instagram.com/fargotattoo.", "brief": ["see https://fargotattoo.com"]});
        assert_eq!(
            urls_in(&v),
            vec![
                "https://fargotattoo.com",
                "https://instagram.com/fargotattoo"
            ]
        );
    }

    #[test]
    fn profile_counts_dates_and_keeps_owner_fields() {
        let a = Artist {
            slug: "leni-b".into(),
            name: "Leni B.".into(),
        };
        let recs = vec![
            json!({"style": "fine line", "subject": "rose", "file_id": "f1", "linework": "fine, delicate", "shading": "light stipple"}),
            json!({"style": "fine line", "subject": "moth", "file_id": "f2", "linework": "fine, delicate", "shading": "minimal"}),
            json!({"style": "illustrative", "subject": "rose", "file_id": "f3", "linework": "bold", "shading": "light stipple"}),
        ];
        let old = json!({"artist": "Leni B.", "style_note": "Owner wrote this.", "owner_set": ["style_note"], "updated": "2024-04-15"});
        let p = rebuild_profile(&a, &recs, Some(&old), "2026-11-10T09:00:00-06:00");
        assert_eq!(p["photo_count"], 3);
        assert_eq!(p["categories"]["fine line"], 2);
        assert_eq!(p["specialties"][0], "fine line");
        assert_eq!(
            p["updated"], "2026-11-10T09:00:00-06:00",
            "the date is the clock's, never invented"
        );
        assert_eq!(p["style_note"], "Owner wrote this.", "owner's note kept");
        assert_eq!(p["exemplars"].as_array().unwrap().len(), 3);
        let fresh = rebuild_profile(&a, &recs, None, "now");
        let note = fresh["style_note"].as_str().unwrap();
        assert!(
            note.starts_with("Mostly fine line (2 of 3 pieces read), also illustrative."),
            "{note}"
        );
        assert!(
            note.contains("Linework: fine, delicate") && note.contains("Subjects include rose"),
            "{note}"
        );
    }
}
