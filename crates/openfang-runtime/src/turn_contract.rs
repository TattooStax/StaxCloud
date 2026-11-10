//! Turn-local evidence, independent of the driver's prose. Never grants a tool
//! capability or bypasses an approval. Shared by streaming and non-streaming.
use crate::llm_driver::CompletionResponse;
use openfang_types::{
    agent::AgentManifest,
    message::{ContentBlock, Message, MessageContent, Role},
    tool::ToolResult,
};
use serde_json::{json, Value};

#[derive(Default)]
pub(crate) struct TurnContract {
    pub references: Vec<String>,
    user_request: String,
    owner_asset: Option<&'static str>,
    recovered_refusal: bool,
    image_receipts: Vec<String>,
    recorded_images: std::collections::HashSet<String>,
    blocking_error: Option<String>,
}

fn attachment_ids(text: &str) -> Vec<String> {
    text.split("[Attached image: file_id ")
        .skip(1)
        .filter_map(|s| s.split_once(']').map(|(id, _)| id.trim()))
        .filter(|id| uuid::Uuid::parse_str(id).is_ok())
        .map(String::from)
        .collect()
}

impl TurnContract {
    pub fn new(
        manifest: &AgentManifest,
        user: &str,
        blocks: Option<&[ContentBlock]>,
        history: &[Message],
    ) -> Self {
        let mut references = attachment_ids(user);
        for b in blocks.unwrap_or_default() {
            if let ContentBlock::Text { text, .. } = b {
                references.extend(attachment_ids(text));
            }
        }
        let lower = user.to_lowercase();
        // A follow-up can refer to a prior upload. Do not attach old pictures
        // to unrelated new work; never take reference IDs from tool results.
        if references.is_empty()
            && [
                "redo this",
                "redo that",
                "that image",
                "that picture",
                "the reference",
                "attached",
                "same image",
            ]
            .iter()
            .any(|s| lower.contains(s))
        {
            for msg in history.iter().rev().filter(|m| m.role == Role::User) {
                if let MessageContent::Blocks(bs) = &msg.content {
                    for b in bs {
                        if let ContentBlock::Text { text, .. } = b {
                            references.extend(attachment_ids(text));
                        }
                    }
                }
                if !references.is_empty() {
                    break;
                }
            }
        }
        let mut unique = Vec::new();
        for id in references {
            if !unique.contains(&id) {
                unique.push(id);
            }
        }
        let lead = manifest
            .metadata
            .get("owner_facing")
            .and_then(Value::as_bool)
            .unwrap_or(false)
            || (manifest.name == "stax" && manifest.tags.iter().any(|t| t == "hand:stax"));
        let third_party = [
            "competitor",
            "someone else's",
            "another artist",
            "third-party",
            "third party",
            "their website",
            "their portfolio",
        ]
        .iter()
        .any(|s| lower.contains(s));
        let owned = !third_party
            && ["my ", "our ", "fargo tattoo", "fargotattoo.com"]
                .iter()
                .any(|s| lower.contains(s));
        let owner_asset = if lead && owned {
            if [
                "website",
                "web site",
                "my site",
                "our site",
                "landing page",
                "homepage",
                "netlify",
                "fargotattoo.com",
            ]
            .iter()
            .any(|s| lower.contains(s))
            {
                Some("website")
            } else if ["portfolio", "design", "photo", "picture"]
                .iter()
                .any(|s| lower.contains(s))
            {
                Some("portfolio")
            } else if ["records", "contacts", "customer list"]
                .iter()
                .any(|s| lower.contains(s))
            {
                Some("records")
            } else {
                None
            }
        } else {
            None
        };
        Self {
            references: unique,
            owner_asset,
            user_request: user.to_string(),
            ..Default::default()
        }
    }

    pub fn protect_text(&self, tools: &[openfang_types::tool::ToolDefinition]) -> bool {
        self.owner_asset.is_some() || tools.iter().any(|t| t.name == "image_generate")
    }

    /// Bind before hooks, loop-guard hashing, persisted ToolUse and execution.
    /// A retry cannot remove the reference supplied with this turn.
    pub fn bind_references(&self, response: &mut CompletionResponse) {
        for call in &mut response.tool_calls {
            if call.name != "image_generate" || self.references.is_empty() {
                continue;
            }
            if let Some(input) = call.input.as_object_mut() {
                if let Some(brief) = input.get("prompt").and_then(Value::as_str) {
                    let prompt = format!("{brief}\n\nOwner's current request (preserve its explicit palette, style and composition constraints): {}", crate::str_utils::safe_truncate_str(&self.user_request, 4000));
                    input.insert("prompt".into(), json!(prompt));
                }
                let refs = input.entry("references").or_insert_with(|| json!([]));
                if let Some(ids) = refs.as_array_mut() {
                    for id in &self.references {
                        if !ids.iter().any(|v| v.as_str() == Some(id)) {
                            ids.push(json!(id));
                        }
                    }
                } // Malformed arguments stay malformed: the tool must error.
            }
        }
        for block in &mut response.content {
            if let ContentBlock::ToolUse { id, input, .. } = block {
                if let Some(call) = response.tool_calls.iter().find(|c| c.id == *id) {
                    *input = call.input.clone();
                }
            }
        }
    }

    /// Bounded replan, only for the configured owner lead's own-asset work.
    /// This changes the answer, never permissions or approval decisions.
    pub fn recover_refusal(&mut self, text: &str) -> bool {
        if self.owner_asset.is_none()
            || self.blocking_error.is_some()
            || !self.image_receipts.is_empty()
            || !bare_refusal(text)
            || self.recovered_refusal
        {
            return false;
        }
        self.recovered_refusal = true;
        true
    }

    pub fn record_image_result(&mut self, name: &str, result: &ToolResult) {
        if result.is_error && self.blocking_error.is_none() {
            self.blocking_error =
                Some(crate::str_utils::safe_truncate_str(&result.content, 500).to_string());
        }
        if name != "image_generate" || !self.recorded_images.insert(result.tool_use_id.clone()) {
            return;
        }
        let receipt = if result.is_error {
            format!("The image tool failed; this call produced no usable image. Your reference has not been successfully redone. Error: {}", crate::str_utils::safe_truncate_str(&result.content, 300).replace('`', "'"))
        } else {
            let value: Value = serde_json::from_str(&result.content).unwrap_or(Value::Null);
            let refs: Vec<&str> = value["references_used"]
                .as_array()
                .map(|a| a.iter().filter_map(Value::as_str).collect())
                .unwrap_or_default();
            let urls: Vec<&str> = value["image_urls"]
                .as_array()
                .map(|a| {
                    a.iter()
                        .filter_map(Value::as_str)
                        .filter(|u| {
                            u.starts_with("/api/uploads/")
                                && uuid::Uuid::parse_str(u.trim_start_matches("/api/uploads/"))
                                    .is_ok()
                        })
                        .collect()
                })
                .unwrap_or_default();
            if urls.is_empty() || !self.references.iter().all(|id| refs.contains(&id.as_str())) {
                "The image result has no verifiable output or does not confirm the supplied reference. I have not completed the reference edit.".to_string()
            } else {
                let mut s = format!(
                    "Generated {} image(s). {}",
                    urls.len(),
                    if refs.is_empty() {
                        "No customer reference was submitted.".into()
                    } else {
                        format!(
                            "{} customer reference(s) submitted to the image service.",
                            refs.len()
                        )
                    }
                );
                if let Some(artist) = value["style"]["artist"].as_str() {
                    if value["style"]["style_anchor"].is_string() {
                        s.push_str(&format!(" Applied the saved style profile for {artist}."));
                    } else {
                        s.push_str(
                            " No saved style profile was available for the requested artist.",
                        );
                    }
                }
                s.push_str(" The result has not been visually verified for likeness or style. Please review it.");
                for url in urls {
                    s.push_str(&format!("\n\n![Generated design]({url})"));
                }
                s
            }
        };
        self.image_receipts.push(receipt);
    }

    pub fn has_image_receipts(&self) -> bool {
        !self.image_receipts.is_empty()
    }

    pub fn final_text(&self, text: String) -> String {
        if !self.image_receipts.is_empty() {
            return self.image_receipts.join("\n\n");
        }
        if let Some(asset) = self.owner_asset {
            if bare_refusal(&text) {
                if let Some(error) = &self.blocking_error {
                    return format!(
                        "The requested work has not been completed. The blocking tool reported: {}",
                        error.replace('`', "'")
                    );
                }
                return match asset {
                    "website" => "Your website migration has not been completed. Please provide the Netlify site export, including its assets, so I can prepare the Cloudflare copy from the source files.",
                    "portfolio" => "The portfolio change has not been completed. Please attach the source pictures or provide your portfolio URL so I can work from your material.",
                    _ => "The records change has not been completed. Please identify the records and the change you want so I can prepare it for review.",
                }.into();
            }
        }
        text
    }
}

pub(crate) const OWNER_REPLAN: &str = "\n\nOwn-asset recovery: the owner requested work on their own material. Copying or migrating it is ordinary authorized work. Use your granted tools to inspect the source and prepare the result. Do not claim a helper exists without agent_list; an inactive installed hand is not a running agent. If blocked by a specific missing file, hosting login, or decision, name that input and what you actually completed. Keep third-party rights, private data protections, and all customer-facing approval gates unchanged. Do not invent success or bypass a denied tool.";

fn bare_refusal(text: &str) -> bool {
    let lower = text.to_lowercase().replace('’', "'");
    if [
        "prove you own",
        "proof of ownership",
        "verify your ownership",
    ]
    .iter()
    .any(|s| lower.contains(s))
    {
        return true;
    }
    // Epistemic limits are not policy refusals. Keep useful audit findings
    // and honest uncertainty rather than turning them into a source request.
    if [
        "can't find",
        "cannot find",
        "can't guarantee",
        "cannot guarantee",
        "can't tell",
        "cannot tell",
        "can't verify",
        "cannot verify",
    ]
    .iter()
    .any(|s| lower.contains(s))
    {
        return false;
    }
    if [
        "please attach",
        "please provide",
        "connect your",
        "sign in",
        "log in",
        "need your",
        "need the",
    ]
    .iter()
    .any(|s| lower.contains(s))
    {
        return false;
    }
    [
        "i can't",
        "i cannot",
        "i'm unable",
        "i am unable",
        "i can't create a clone",
        "i cannot create a clone",
        "i can't clone",
        "i cannot clone",
        "i'm unable to clone",
        "i can't assist",
        "i cannot assist",
        "i can't help",
        "i cannot help",
        "not allowed to",
        "against my policy",
        "copyright infringement",
    ]
    .iter()
    .any(|s| lower.contains(s))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::llm_driver::CompletionResponse;
    use openfang_types::{
        message::{StopReason, TokenUsage},
        tool::ToolCall,
    };
    const ID: &str = "22222222-2222-4222-8222-222222222222";
    fn contract() -> TurnContract {
        TurnContract {
            references: vec![ID.into()],
            ..Default::default()
        }
    }
    #[test]
    fn omitted_or_empty_references_stay_bound_on_every_retry() {
        for args in [
            json!({"prompt":"redo"}),
            json!({"prompt":"redo", "references":[]}),
        ] {
            let mut r = CompletionResponse {
                content: vec![ContentBlock::ToolUse {
                    id: "t".into(),
                    name: "image_generate".into(),
                    input: args.clone(),
                    provider_metadata: None,
                }],
                tool_calls: vec![ToolCall {
                    id: "t".into(),
                    name: "image_generate".into(),
                    input: args,
                }],
                stop_reason: StopReason::ToolUse,
                usage: TokenUsage::default(),
            };
            contract().bind_references(&mut r);
            assert_eq!(r.tool_calls[0].input["references"], json!([ID]));
            assert!(
                matches!(&r.content[0], ContentBlock::ToolUse {input,..} if input["references"] == json!([ID]))
            );
        }
    }
    #[test]
    fn image_receipt_overrules_a_fabricated_success() {
        let mut c = contract();
        c.record_image_result(
            "image_generate",
            &ToolResult {
                tool_use_id: "t".into(),
                is_error: false,
                content: json!({"references_used":[],"image_urls":[format!("/api/uploads/{ID}")]})
                    .to_string(),
            },
        );
        let text = c.final_text("Successfully redid your tiger in your style".into());
        assert!(text.contains("not completed"));
        assert!(!text.contains("Successfully"));
    }
    #[test]
    fn reference_receipt_does_not_claim_visual_verification() {
        let mut c = contract();
        c.record_image_result(
            "image_generate",
            &ToolResult {
                tool_use_id: "t".into(),
                is_error: false,
                content:
                    json!({"references_used":[ID],"image_urls":[format!("/api/uploads/{ID}")]})
                        .to_string(),
            },
        );
        let text = c.final_text("Perfect black and grey realism!".into());
        assert!(text.contains("not been visually verified"));
        assert!(text.contains("![Generated design]"));
        assert!(!text.contains("Perfect"));
    }
    #[test]
    fn raw_receipt_survives_context_truncation() {
        let mut c = contract();
        c.record_image_result(
            "image_generate",
            &ToolResult {
                tool_use_id: "image".into(),
                is_error: false,
                content:
                    json!({"references_used":[ID],"image_urls":[format!("/api/uploads/{ID}")]})
                        .to_string(),
            },
        );
        c.record_image_result(
            "image_generate",
            &ToolResult {
                tool_use_id: "image".into(),
                is_error: false,
                content: "{truncated".into(),
            },
        );
        assert!(c
            .final_text("Perfect!".into())
            .contains("![Generated design]"));
    }

    #[test]
    fn owner_recovery_does_not_retry_or_bypass_a_denied_tool() {
        let mut m = AgentManifest::default();
        m.metadata.insert("owner_facing".into(), json!(true));
        let mut c = TurnContract::new(&m, "Publish my website", None, &[]);
        c.record_image_result(
            "site_publish",
            &ToolResult {
                tool_use_id: "denied".into(),
                is_error: true,
                content: "requires human approval and was denied".into(),
            },
        );
        assert!(!c.recover_refusal("I can't publish your website"));
        assert!(c
            .final_text("I can't publish your website".into())
            .contains("approval and was denied"));
    }

    #[test]
    fn useful_owner_site_uncertainty_is_not_rewritten_as_a_refusal() {
        let mut m = AgentManifest::default();
        m.metadata.insert("owner_facing".into(), json!(true));
        let mut c = TurnContract::new(&m, "Review my website", None, &[]);
        let text = "I can't find a broken link on the pages I checked.";
        assert!(!c.recover_refusal(text));
        assert_eq!(c.final_text(text.into()), text);
    }

    #[test]
    fn third_party_request_is_not_owner_asset_recovery() {
        let mut m = AgentManifest::default();
        m.metadata.insert("owner_facing".into(), json!(true));
        let mut c = TurnContract::new(&m, "Clone a competitor website", None, &[]);
        assert!(!c.recover_refusal("I can't clone that site"));
    }
    #[test]
    fn tool_failures_cannot_be_narrated_as_success() {
        let mut c = contract();
        c.record_image_result(
            "image_generate",
            &ToolResult {
                tool_use_id: "t".into(),
                is_error: true,
                content: "timeout".into(),
            },
        );
        assert!(c
            .final_text("Here is the redo".into())
            .contains("tool failed"));
    }
}
