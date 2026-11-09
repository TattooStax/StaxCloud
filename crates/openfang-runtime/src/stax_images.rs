//! StaxCloud image work through OpenRouter: make a picture (optionally from
//! reference pictures), describe a picture with a vision model, and fetch a
//! picture from the web into the uploads folder.
//!
//! Models come from the environment so a pin is a config change:
//! `STAX_IMAGE_MODEL` (falls back to `DESIGNER_GEN_MODEL`, which the designer
//! sidecar already uses) and `STAX_VISION_MODEL`. The API key is
//! `OPENROUTER_API_KEY`; `OPENROUTER_BASE_URL` overrides the endpoint (tests,
//! proxies).

use base64::Engine;
use openfang_types::uploads;
use std::time::Duration;

/// Image model used until a benchmark winner is pinned (what Canvas used).
pub const DEFAULT_IMAGE_MODEL: &str = "google/gemini-2.5-flash-image";
/// Vision model used until a benchmark winner is pinned (what the designer used).
pub const DEFAULT_VISION_MODEL: &str = "google/gemini-2.5-flash";
/// Largest picture accepted from the web or sent as a reference.
pub const MAX_IMAGE_BYTES: usize = 10 * 1024 * 1024;
/// Most reference pictures sent with one generation.
pub const MAX_REFERENCES: usize = 6;

const DEFAULT_BASE_URL: &str = "https://openrouter.ai/api/v1";
const MAX_REDIRECTS: usize = 3;

fn env_nonempty(name: &str) -> Option<String> {
    std::env::var(name)
        .ok()
        .map(|v| v.trim().to_string())
        .filter(|v| !v.is_empty())
}

/// The image model in use.
pub fn image_model() -> String {
    env_nonempty("STAX_IMAGE_MODEL")
        .or_else(|| env_nonempty("DESIGNER_GEN_MODEL"))
        .unwrap_or_else(|| DEFAULT_IMAGE_MODEL.to_string())
}

/// The vision model in use.
pub fn vision_model() -> String {
    env_nonempty("STAX_VISION_MODEL").unwrap_or_else(|| DEFAULT_VISION_MODEL.to_string())
}

/// Whether OpenRouter image work is configured (an API key is present).
pub fn available() -> bool {
    env_nonempty("OPENROUTER_API_KEY").is_some()
}

fn api_key() -> Result<String, String> {
    env_nonempty("OPENROUTER_API_KEY")
        .ok_or_else(|| "Image work needs OPENROUTER_API_KEY, which is not set.".to_string())
}

fn base_url() -> String {
    env_nonempty("OPENROUTER_BASE_URL")
        .unwrap_or_else(|| DEFAULT_BASE_URL.to_string())
        .trim_end_matches('/')
        .to_string()
}

fn chat_url() -> String {
    format!("{}/chat/completions", base_url())
}

fn images_url() -> String {
    format!("{}/images", base_url())
}

/// A picture to send to a model.
#[derive(Debug, Clone)]
pub struct Picture {
    pub mime: String,
    pub bytes: Vec<u8>,
}

impl Picture {
    /// Load an upload by id; refuses non-images and oversize files.
    pub fn from_upload(file_id: &str) -> Result<Self, String> {
        let bytes =
            uploads::read(file_id).map_err(|e| format!("Upload '{file_id}' unreadable: {e}"))?;
        Self::from_bytes(bytes).map_err(|e| format!("Upload '{file_id}': {e}"))
    }

    pub fn from_bytes(bytes: Vec<u8>) -> Result<Self, String> {
        if bytes.len() > MAX_IMAGE_BYTES {
            return Err(format!(
                "picture is {} MB; the limit is {} MB",
                bytes.len() / (1024 * 1024),
                MAX_IMAGE_BYTES / (1024 * 1024)
            ));
        }
        let mime = uploads::sniff_image_mime(&bytes)
            .ok_or("not a PNG, JPEG, WebP or GIF picture")?
            .to_string();
        Ok(Self { mime, bytes })
    }

    fn data_url(&self) -> String {
        format!(
            "data:{};base64,{}",
            self.mime,
            base64::engine::general_purpose::STANDARD.encode(&self.bytes)
        )
    }
}

/// What a generation returned.
#[derive(Debug, Clone)]
pub struct Generated {
    pub pictures: Vec<Picture>,
    /// Text the model returned alongside the pictures, if any.
    pub note: String,
    /// What OpenRouter billed, when it reported it.
    pub cost_usd: Option<f64>,
    pub model: String,
}

fn client(timeout_secs: u64) -> Result<reqwest::Client, String> {
    reqwest::Client::builder()
        .timeout(Duration::from_secs(timeout_secs))
        .redirect(reqwest::redirect::Policy::none())
        .build()
        .map_err(|e| format!("HTTP client: {e}"))
}

/// An HTTP status from the image service, kept so the caller can choose a
/// fallback route.
struct ServiceError {
    status: u16,
    message: String,
}

async fn post_json(
    url: String,
    body: serde_json::Value,
    timeout_secs: u64,
) -> Result<serde_json::Value, ServiceError> {
    let fail = |status: u16, message: String| ServiceError { status, message };
    let key = api_key().map_err(|m| fail(0, m))?;
    let resp = client(timeout_secs)
        .map_err(|m| fail(0, m))?
        .post(url)
        .bearer_auth(key)
        .header("X-Title", "StaxCloud")
        .json(&body)
        .send()
        .await
        .map_err(|e| fail(0, format!("Request to the image service failed: {e}")))?;
    let status = resp.status();
    let text = resp.text().await.unwrap_or_default();
    if !status.is_success() {
        return Err(fail(
            status.as_u16(),
            format!(
                "Image service returned HTTP {}: {}",
                status.as_u16(),
                crate::str_utils::safe_truncate_str(&text, 400)
            ),
        ));
    }
    serde_json::from_str(&text)
        .map_err(|e| fail(0, format!("Image service sent unreadable JSON: {e}")))
}

async fn post_chat(
    body: serde_json::Value,
    timeout_secs: u64,
) -> Result<serde_json::Value, String> {
    post_json(chat_url(), body, timeout_secs)
        .await
        .map_err(|e| e.message)
}

fn decode_data_url(url: &str) -> Option<Vec<u8>> {
    let (head, data) = url.split_once(',')?;
    if !head.starts_with("data:") || !head.contains(";base64") {
        return None;
    }
    base64::engine::general_purpose::STANDARD.decode(data).ok()
}

/// Pull pictures out of a chat-completions reply. OpenRouter puts them in
/// `message.images[]`; some providers put them in `message.content[]` parts.
pub fn pictures_in_reply(reply: &serde_json::Value) -> (Vec<Picture>, String) {
    let msg = &reply["choices"][0]["message"];
    let mut urls: Vec<String> = Vec::new();
    if let Some(imgs) = msg["images"].as_array() {
        for im in imgs {
            if let Some(u) = im["image_url"]["url"].as_str() {
                urls.push(u.to_string());
            }
        }
    }
    let mut note = String::new();
    match &msg["content"] {
        serde_json::Value::String(s) => note.push_str(s),
        serde_json::Value::Array(parts) => {
            for p in parts {
                if let Some(u) = p["image_url"]["url"].as_str() {
                    urls.push(u.to_string());
                } else if let Some(t) = p["text"].as_str() {
                    note.push_str(t);
                }
            }
        }
        _ => {}
    }
    let pictures = urls
        .iter()
        .filter_map(|u| decode_data_url(u))
        .filter_map(|b| Picture::from_bytes(b).ok())
        .collect();
    (pictures, note.trim().to_string())
}

fn billed(reply: &serde_json::Value) -> Option<f64> {
    reply["usage"]["cost"].as_f64()
}

/// Pictures from the dedicated images endpoint's reply (`data[].b64_json`).
pub fn pictures_in_images_reply(reply: &serde_json::Value) -> Vec<Picture> {
    reply["data"]
        .as_array()
        .map(|items| {
            items
                .iter()
                .filter_map(|it| it["b64_json"].as_str())
                .filter_map(|b| base64::engine::general_purpose::STANDARD.decode(b).ok())
                .filter_map(|b| Picture::from_bytes(b).ok())
                .collect()
        })
        .unwrap_or_default()
}

/// Make pictures from a prompt and optional reference pictures.
///
/// OpenRouter serves image models on two routes: the dedicated
/// `/images` endpoint (GPT-Image, FLUX, Seedream, Qwen-Image, … — reference
/// pictures go in `input_references`) and chat completions with
/// `modalities: ["image","text"]` (Gemini image models and some others only
/// generate there). The images endpoint is tried first; a 400/404/405/422
/// from it means the model wants the chat route, which is tried next.
pub async fn generate(
    prompt: &str,
    references: &[Picture],
    model: &str,
) -> Result<Generated, String> {
    let refs: Vec<serde_json::Value> = references
        .iter()
        .take(MAX_REFERENCES)
        .map(|r| serde_json::json!({"type": "image_url", "image_url": {"url": r.data_url()}}))
        .collect();

    let mut body = serde_json::json!({"model": model, "prompt": prompt, "n": 1});
    if !refs.is_empty() {
        body["input_references"] = serde_json::json!(refs);
    }
    let images_err = match post_json(images_url(), body, 300).await {
        Ok(reply) => {
            let pictures = pictures_in_images_reply(&reply);
            if !pictures.is_empty() {
                return Ok(Generated {
                    pictures,
                    note: String::new(),
                    cost_usd: billed(&reply),
                    model: model.to_string(),
                });
            }
            format!("{model} returned no picture on the images route")
        }
        Err(e) if matches!(e.status, 400 | 404 | 405 | 422) => e.message,
        Err(e) => return Err(e.message),
    };

    let mut content = vec![serde_json::json!({"type": "text", "text": prompt})];
    content.extend(refs);
    let body = serde_json::json!({
        "model": model,
        "modalities": ["image", "text"],
        "messages": [{"role": "user", "content": content}],
        "usage": {"include": true},
    });
    let reply = post_chat(body, 300).await.map_err(|chat_err| {
        format!(
            "{model} could not make a picture. Images route: {images_err}. Chat route: {chat_err}"
        )
    })?;
    let (pictures, note) = pictures_in_reply(&reply);
    if pictures.is_empty() {
        return Err(if note.is_empty() {
            format!("{model} returned no picture.")
        } else {
            format!(
                "{model} returned no picture. It said: {}",
                crate::str_utils::safe_truncate_str(&note, 300)
            )
        });
    }
    Ok(Generated {
        pictures,
        note,
        cost_usd: billed(&reply),
        model: model.to_string(),
    })
}

/// Ask a vision model about a picture. Returns (answer, billed cost).
pub async fn describe(
    picture: &Picture,
    prompt: &str,
    model: &str,
) -> Result<(String, Option<f64>), String> {
    let body = serde_json::json!({
        "model": model,
        // Room for reasoning models to think and still finish the answer.
        "max_tokens": 2000,
        "temperature": 0.1,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": picture.data_url()}},
        ]}],
        "usage": {"include": true},
    });
    let reply = post_chat(body, 120).await?;
    let text = reply["choices"][0]["message"]["content"]
        .as_str()
        .unwrap_or("")
        .trim()
        .to_string();
    if text.is_empty() {
        return Err(format!("{model} gave no description."));
    }
    Ok((text, billed(&reply)))
}

/// GET a public web address: private and internal addresses refused (same
/// rule as web_fetch), redirects re-checked hop by hop, body capped at
/// `max_bytes`. Returns (body, final address).
async fn fetch_public(url: &str, max_bytes: usize) -> Result<(Vec<u8>, reqwest::Url), String> {
    let http = client(30)?;
    let mut current = url.to_string();
    for _ in 0..=MAX_REDIRECTS {
        crate::web_fetch::check_ssrf(&current, &[])?;
        let resp = http
            .get(&current)
            .header("User-Agent", "StaxCloud/1.0 (portfolio reader)")
            .send()
            .await
            .map_err(|e| format!("Could not fetch {current}: {e}"))?;
        if resp.status().is_redirection() {
            let next = resp
                .headers()
                .get(reqwest::header::LOCATION)
                .and_then(|v| v.to_str().ok())
                .ok_or_else(|| format!("{current} redirected without a location"))?;
            current = resp
                .url()
                .join(next)
                .map_err(|e| format!("Bad redirect from {current}: {e}"))?
                .to_string();
            continue;
        }
        if !resp.status().is_success() {
            return Err(format!(
                "{current} returned HTTP {}",
                resp.status().as_u16()
            ));
        }
        if resp
            .content_length()
            .is_some_and(|len| len as usize > max_bytes)
        {
            return Err(format!("{current} is larger than the limit"));
        }
        let final_url = resp.url().clone();
        let bytes = resp
            .bytes()
            .await
            .map_err(|e| format!("Download of {current} broke off: {e}"))?;
        if bytes.len() > max_bytes {
            return Err(format!("{current} is larger than the limit"));
        }
        return Ok((bytes.to_vec(), final_url));
    }
    Err(format!("{url} redirected too many times"))
}

/// Download a picture from a public web address. Anything that is not an
/// image or is over the size limit is refused.
pub async fn fetch(url: &str) -> Result<Picture, String> {
    let (bytes, final_url) = fetch_public(url, MAX_IMAGE_BYTES).await?;
    Picture::from_bytes(bytes).map_err(|e| format!("{final_url}: {e}"))
}

/// A picture found on a web page.
#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct PageImage {
    pub url: String,
    pub alt: String,
}

/// Most pictures listed from one page.
pub const MAX_PAGE_IMAGES: usize = 150;
const MAX_PAGE_BYTES: usize = 5 * 1024 * 1024;

fn attr(tag: &str, name: &str) -> Option<String> {
    let re = regex_lite::Regex::new(&format!(
        r#"(?i)\s{}\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))"#,
        regex_lite::escape(name)
    ))
    .ok()?;
    let c = re.captures(tag)?;
    c.get(1)
        .or_else(|| c.get(2))
        .or_else(|| c.get(3))
        .map(|m| m.as_str().replace("&amp;", "&").trim().to_string())
        .filter(|v| !v.is_empty())
}

/// The widest candidate in a srcset ("a.jpg 400w, b.jpg 1200w" -> b.jpg).
fn widest_in_srcset(srcset: &str) -> Option<String> {
    srcset
        .split(',')
        .filter_map(|part| {
            let mut it = part.split_whitespace();
            let url = it.next()?.to_string();
            let w = it
                .next()
                .and_then(|d| d.trim_end_matches(['w', 'x']).parse::<f64>().ok())
                .unwrap_or(0.0);
            Some((url, w))
        })
        .max_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal))
        .map(|(u, _)| u)
}

/// Pictures referenced by an HTML page: <img> (src, lazy-load attributes,
/// widest srcset), <picture><source srcset>, and og:image. Relative
/// addresses are resolved against `base`; icons, SVGs, data: URIs and
/// duplicates are skipped.
pub fn images_in_html(html: &str, base: &reqwest::Url) -> Vec<PageImage> {
    let mut found: Vec<PageImage> = Vec::new();
    let mut seen: std::collections::HashMap<String, usize> = std::collections::HashMap::new();
    let mut push = |raw: &str, alt: String, found: &mut Vec<PageImage>| {
        let raw = raw.trim();
        if raw.is_empty() || raw.starts_with("data:") {
            return;
        }
        let Ok(u) = base.join(raw) else { return };
        if u.scheme() != "http" && u.scheme() != "https" {
            return;
        }
        let path = u.path().to_lowercase();
        let name = path.rsplit('/').next().unwrap_or("");
        if name.ends_with(".svg")
            || ["favicon", "sprite", "pixel", "spacer", "apple-touch-icon"]
                .iter()
                .any(|n| name.contains(n))
        {
            return;
        }
        // One picture often ships as several files (WebP + JPEG, sized
        // copies like "-720"): same folder + same name stem = same picture.
        // The first file found is kept; alt text fills in from a twin.
        let folder = path.rsplit_once('/').map(|(d, _)| d).unwrap_or("");
        let stem = name.rsplit_once('.').map(|(s, _)| s).unwrap_or(name);
        let stem = match stem.rsplit_once('-') {
            Some((head, tail))
                if !head.is_empty()
                    && tail.len() <= 4
                    && tail.chars().all(|c| c.is_ascii_digit()) =>
            {
                head
            }
            _ => stem,
        };
        let key = format!("{}{}/{}", u.host_str().unwrap_or(""), folder, stem);
        if let Some(&i) = seen.get(&key) {
            let existing: &mut PageImage = &mut found[i];
            if existing.alt.is_empty() && !alt.is_empty() {
                existing.alt = alt;
            }
            return;
        }
        if found.len() < MAX_PAGE_IMAGES {
            seen.insert(key, found.len());
            found.push(PageImage {
                url: u.to_string(),
                alt,
            });
        }
    };

    if let Ok(meta) = regex_lite::Regex::new(r#"(?is)<meta\b[^>]*>"#) {
        for m in meta.find_iter(html) {
            let tag = m.as_str();
            let prop = attr(tag, "property")
                .or_else(|| attr(tag, "name"))
                .unwrap_or_default();
            if prop.eq_ignore_ascii_case("og:image") {
                if let Some(c) = attr(tag, "content") {
                    push(&c, "page preview image".into(), &mut found);
                }
            }
        }
    }
    if let Ok(img) = regex_lite::Regex::new(r#"(?is)<(?:img|source)\b[^>]*>"#) {
        for m in img.find_iter(html) {
            let tag = m.as_str();
            let alt = attr(tag, "alt").unwrap_or_default();
            let src = attr(tag, "srcset")
                .or_else(|| attr(tag, "data-srcset"))
                .and_then(|s| widest_in_srcset(&s))
                .or_else(|| attr(tag, "data-src"))
                .or_else(|| attr(tag, "data-lazy-src"))
                .or_else(|| attr(tag, "data-image"))
                .or_else(|| attr(tag, "src"));
            if let Some(src) = src {
                push(&src, alt, &mut found);
            }
        }
    }
    found
}

/// List the pictures on a public web page.
pub async fn page_images(url: &str) -> Result<Vec<PageImage>, String> {
    let (bytes, final_url) = fetch_public(url, MAX_PAGE_BYTES).await?;
    let html = String::from_utf8_lossy(&bytes);
    Ok(images_in_html(&html, &final_url))
}

#[cfg(test)]
mod tests {
    use super::*;

    const PNG: &[u8] = &[0x89, b'P', b'N', b'G', 0x0D, 0x0A, 0x1A, 0x0A, 1, 2, 3];

    #[test]
    fn picture_rejects_non_images() {
        assert!(Picture::from_bytes(b"<html>".to_vec()).is_err());
        let p = Picture::from_bytes(PNG.to_vec()).unwrap();
        assert_eq!(p.mime, "image/png");
        assert!(p.data_url().starts_with("data:image/png;base64,"));
    }

    #[test]
    fn reads_pictures_from_both_reply_shapes() {
        let b64 = base64::engine::general_purpose::STANDARD.encode(PNG);
        let url = format!("data:image/png;base64,{b64}");
        let a = serde_json::json!({"choices": [{"message": {
            "content": "Here you go", "images": [{"type": "image_url", "image_url": {"url": url}}]}}]});
        let (pics, note) = pictures_in_reply(&a);
        assert_eq!(pics.len(), 1);
        assert_eq!(note, "Here you go");
        let b = serde_json::json!({"choices": [{"message": {"content": [
            {"type": "text", "text": "done"}, {"type": "image_url", "image_url": {"url": url}}]}}]});
        let (pics, note) = pictures_in_reply(&b);
        assert_eq!(pics.len(), 1);
        assert_eq!(note, "done");
        let none = serde_json::json!({"choices": [{"message": {"content": "I can't draw that"}}]});
        assert!(pictures_in_reply(&none).0.is_empty());
    }

    #[test]
    fn finds_pictures_in_html() {
        let base = reqwest::Url::parse("https://studio.example/artists/shawn/").unwrap();
        let html = r#"
          <meta property="og:image" content="https://cdn.example/og.jpg">
          <img src="/img/logo.svg" alt="logo">
          <img src="data:image/gif;base64,R0lG" alt="pixel">
          <img class="lazy" data-src="work/rose.jpg?w=300" alt="Black and grey rose">
          <img srcset="p/dog-400.jpg 400w, p/dog-1600.jpg 1600w" src="p/dog-400.jpg" alt='Dog portrait'>
          <picture><source srcset="https://cdn.example/lion.webp"><img src="https://cdn.example/lion.jpg" alt="Lion"></picture>
          <img src="/work/rose.jpg?w=1200" alt="duplicate rose">
          <img src="/favicon-32.png">
        "#;
        let got = images_in_html(html, &base);
        let urls: Vec<&str> = got.iter().map(|i| i.url.as_str()).collect();
        assert_eq!(
            urls,
            vec![
                "https://cdn.example/og.jpg",
                "https://studio.example/artists/shawn/work/rose.jpg?w=300",
                "https://studio.example/artists/shawn/p/dog-1600.jpg",
                "https://cdn.example/lion.webp",
                "https://studio.example/work/rose.jpg?w=1200",
            ]
        );
        assert_eq!(got[1].alt, "Black and grey rose");
        assert_eq!(got[2].alt, "Dog portrait");
        assert_eq!(got[3].alt, "Lion", "alt text fills in from the JPEG twin");
    }

    #[test]
    fn reads_pictures_from_the_images_endpoint() {
        let b64 = base64::engine::general_purpose::STANDARD.encode(PNG);
        let r = serde_json::json!({"data": [{"b64_json": b64, "media_type": "image/png"}, {"b64_json": "not base64!"}], "usage": {"cost": 0.04}});
        assert_eq!(pictures_in_images_reply(&r).len(), 1);
        assert_eq!(billed(&r), Some(0.04));
        assert!(pictures_in_images_reply(&serde_json::json!({"error": {"code": 400}})).is_empty());
    }

    #[tokio::test]
    async fn page_images_refuses_private_addresses() {
        assert!(page_images("http://10.0.0.5/").await.is_err());
    }

    #[tokio::test]
    async fn fetch_refuses_private_addresses() {
        for u in [
            "http://127.0.0.1/x.png",
            "http://localhost/x.png",
            "http://169.254.169.254/latest",
            "file:///etc/passwd",
        ] {
            assert!(fetch(u).await.is_err(), "{u}");
        }
    }
}
