//! Execution approval manager — gates dangerous operations behind human approval.

use chrono::Utc;
use dashmap::DashMap;
use openfang_types::approval::{
    ApprovalDecision, ApprovalPolicy, ApprovalRequest, ApprovalResponse, RiskLevel,
};
use std::collections::VecDeque;
use tracing::{debug, info, warn};
use uuid::Uuid;

/// Max pending requests per agent.
const MAX_PENDING_PER_AGENT: usize = 5;
/// Max queued (non-blocking) holds per agent. A sidecar carries every
/// hold of its class under one agent id, so the tool-gate cap above
/// would refuse most of a real queue; this cap is sized for that use
/// and exists to bound memory, not to shape the queue.
const MAX_QUEUED_PER_AGENT: usize = 100;
/// Max recent approval records to retain for history and UI visibility.
const MAX_RECENT_APPROVALS: usize = 100;

/// Manages approval requests with oneshot channels for blocking resolution.
pub struct ApprovalManager {
    pending: DashMap<Uuid, PendingRequest>,
    recent: std::sync::Mutex<VecDeque<ApprovalRecord>>,
    policy: std::sync::RwLock<ApprovalPolicy>,
}

struct PendingRequest {
    request: ApprovalRequest,
    sender: tokio::sync::oneshot::Sender<ApprovalDecision>,
}

#[derive(Debug, Clone)]
pub struct ApprovalRecord {
    pub request: ApprovalRequest,
    pub decision: ApprovalDecision,
    pub decided_at: chrono::DateTime<Utc>,
    pub decided_by: Option<String>,
}

/// One read of the store by id: a queued/tool request still waiting,
/// a request that already carries a decision, or no such request.
#[derive(Debug, Clone)]
pub enum ApprovalLookup {
    Pending(ApprovalRequest),
    Decided(ApprovalRecord),
    Missing,
}

impl ApprovalManager {
    pub fn new(policy: ApprovalPolicy) -> Self {
        Self {
            pending: DashMap::new(),
            recent: std::sync::Mutex::new(VecDeque::new()),
            policy: std::sync::RwLock::new(policy),
        }
    }

    /// Check if a tool requires approval based on current policy.
    pub fn requires_approval(&self, tool_name: &str) -> bool {
        let policy = self.policy.read().unwrap_or_else(|e| e.into_inner());
        policy.require_approval.iter().any(|t| t == tool_name)
    }

    /// Submit an approval request. Returns a future that resolves when approved/denied/timed out.
    pub async fn request_approval(&self, req: ApprovalRequest) -> ApprovalDecision {
        // Check per-agent pending limit
        let agent_pending = self
            .pending
            .iter()
            .filter(|r| r.value().request.agent_id == req.agent_id)
            .count();
        if agent_pending >= MAX_PENDING_PER_AGENT {
            warn!(agent_id = %req.agent_id, "Approval request rejected: too many pending");
            return ApprovalDecision::Denied;
        }

        let timeout = std::time::Duration::from_secs(req.timeout_secs);
        let id = req.id;
        let req_for_timeout = req.clone();

        let (tx, rx) = tokio::sync::oneshot::channel();
        self.pending.insert(
            id,
            PendingRequest {
                request: req,
                sender: tx,
            },
        );

        info!(request_id = %id, "Approval request submitted, waiting for resolution");

        match tokio::time::timeout(timeout, rx).await {
            Ok(Ok(decision)) => {
                debug!(request_id = %id, ?decision, "Approval resolved");
                decision
            }
            _ => {
                let request = self
                    .pending
                    .remove(&id)
                    .map(|(_, pending)| pending.request)
                    .unwrap_or(req_for_timeout);
                self.push_recent(request, ApprovalDecision::TimedOut, None, Utc::now());
                warn!(request_id = %id, "Approval request timed out");
                ApprovalDecision::TimedOut
            }
        }
    }

    /// Submit a queued hold for a human decision (the external/API path).
    ///
    /// Unlike `request_approval`, nothing waits on this request and no
    /// timer runs against it: a hold is a queue entry a person decides
    /// on human time, and the consumers that poll for the decision work
    /// on a multi-minute cadence the tool-gate timeout (max 300s) cannot
    /// outlive. The record is inserted before this returns, so an id the
    /// caller is handed always names a record that exists; refusing a
    /// submission (per-agent queue cap) is an error here, never an id
    /// that was never stored.
    pub fn submit_queued(&self, req: ApprovalRequest) -> Result<Uuid, String> {
        let agent_pending = self
            .pending
            .iter()
            .filter(|r| r.value().request.agent_id == req.agent_id)
            .count();
        if agent_pending >= MAX_QUEUED_PER_AGENT {
            warn!(agent_id = %req.agent_id, "Queued approval rejected: too many pending");
            return Err(format!(
                "Too many pending approvals for agent {} (max {MAX_QUEUED_PER_AGENT})",
                req.agent_id
            ));
        }
        let id = req.id;
        // No waiter exists for a queued hold; the sender is kept so
        // `resolve` treats both paths identically, and its send simply
        // finds no receiver.
        let (tx, _rx) = tokio::sync::oneshot::channel();
        self.pending.insert(
            id,
            PendingRequest {
                request: req,
                sender: tx,
            },
        );
        info!(request_id = %id, "Queued approval submitted");
        Ok(id)
    }

    /// Look up one request by id across the pending map and the
    /// decided history, so a caller holding an id reads the same fact
    /// the list views are built from.
    pub fn lookup(&self, request_id: Uuid) -> ApprovalLookup {
        if let Some(entry) = self.pending.get(&request_id) {
            return ApprovalLookup::Pending(entry.value().request.clone());
        }
        let recent = self.recent.lock().unwrap_or_else(|e| e.into_inner());
        match recent.iter().find(|r| r.request.id == request_id) {
            Some(record) => ApprovalLookup::Decided(record.clone()),
            None => ApprovalLookup::Missing,
        }
    }

    /// Resolve a pending request (called by API/UI).
    ///
    /// Deciding an already-decided id returns the stored decision
    /// unchanged: a decision is a fact about the record, and a repeated
    /// decide (a second tap, a retried caller) must never produce a
    /// second effect. A timed-out request is refused as timed out —
    /// its waiter already received that outcome.
    pub fn resolve(
        &self,
        request_id: Uuid,
        decision: ApprovalDecision,
        decided_by: Option<String>,
    ) -> Result<ApprovalResponse, String> {
        match self.pending.remove(&request_id) {
            Some((_, pending)) => {
                let response = ApprovalResponse {
                    request_id,
                    decision,
                    decided_at: Utc::now(),
                    decided_by,
                };
                self.push_recent(
                    pending.request.clone(),
                    decision,
                    response.decided_by.clone(),
                    response.decided_at,
                );
                // Send decision to waiting agent (ignore error if receiver dropped)
                let _ = pending.sender.send(decision);
                info!(request_id = %request_id, ?decision, "Approval request resolved");
                Ok(response)
            }
            None => match self.lookup(request_id) {
                ApprovalLookup::Decided(record) => match record.decision {
                    ApprovalDecision::Approved | ApprovalDecision::Denied => {
                        Ok(ApprovalResponse {
                            request_id,
                            decision: record.decision,
                            decided_at: record.decided_at,
                            decided_by: record.decided_by,
                        })
                    }
                    ApprovalDecision::TimedOut => Err(format!(
                        "Approval request {request_id} already timed out"
                    )),
                },
                _ => Err(format!("No pending approval request with id {request_id}")),
            },
        }
    }

    /// List all pending requests (for API/dashboard display).
    pub fn list_pending(&self) -> Vec<ApprovalRequest> {
        self.pending
            .iter()
            .map(|r| r.value().request.clone())
            .collect()
    }

    /// List recent non-pending approvals, newest first.
    pub fn list_recent(&self, limit: usize) -> Vec<ApprovalRecord> {
        let recent = self.recent.lock().unwrap_or_else(|e| e.into_inner());
        recent.iter().take(limit).cloned().collect()
    }

    /// Number of pending requests.
    pub fn pending_count(&self) -> usize {
        self.pending.len()
    }

    /// Update the approval policy (for hot-reload).
    pub fn update_policy(&self, policy: ApprovalPolicy) {
        *self.policy.write().unwrap_or_else(|e| e.into_inner()) = policy;
    }

    /// Get a copy of the current policy.
    pub fn policy(&self) -> ApprovalPolicy {
        self.policy
            .read()
            .unwrap_or_else(|e| e.into_inner())
            .clone()
    }

    /// Classify the risk level of a tool invocation.
    pub fn classify_risk(tool_name: &str) -> RiskLevel {
        match tool_name {
            "shell_exec" => RiskLevel::Critical,
            "file_write" | "file_delete" => RiskLevel::High,
            "web_fetch" | "browser_navigate" => RiskLevel::Medium,
            _ => RiskLevel::Low,
        }
    }

    fn push_recent(
        &self,
        request: ApprovalRequest,
        decision: ApprovalDecision,
        decided_by: Option<String>,
        decided_at: chrono::DateTime<Utc>,
    ) {
        let mut recent = self.recent.lock().unwrap_or_else(|e| e.into_inner());
        recent.push_front(ApprovalRecord {
            request,
            decision,
            decided_at,
            decided_by,
        });
        while recent.len() > MAX_RECENT_APPROVALS {
            recent.pop_back();
        }
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use openfang_types::approval::ApprovalPolicy;
    use std::sync::Arc;

    fn default_manager() -> ApprovalManager {
        ApprovalManager::new(ApprovalPolicy::default())
    }

    fn make_request(agent_id: &str, tool_name: &str, timeout_secs: u64) -> ApprovalRequest {
        ApprovalRequest {
            id: Uuid::new_v4(),
            agent_id: agent_id.to_string(),
            tool_name: tool_name.to_string(),
            description: "test operation".to_string(),
            action_summary: "test action".to_string(),
            risk_level: RiskLevel::High,
            requested_at: Utc::now(),
            timeout_secs,
        }
    }

    // -----------------------------------------------------------------------
    // requires_approval
    // -----------------------------------------------------------------------

    #[test]
    fn test_requires_approval_default() {
        let mgr = default_manager();
        assert!(mgr.requires_approval("shell_exec"));
        assert!(!mgr.requires_approval("file_read"));
    }

    #[test]
    fn test_requires_approval_custom_policy() {
        let policy = ApprovalPolicy {
            require_approval: vec!["file_write".to_string(), "file_delete".to_string()],
            timeout_secs: 30,
            auto_approve_autonomous: false,
            auto_approve: false,
        };
        let mgr = ApprovalManager::new(policy);
        assert!(mgr.requires_approval("file_write"));
        assert!(mgr.requires_approval("file_delete"));
        assert!(!mgr.requires_approval("shell_exec"));
        assert!(!mgr.requires_approval("file_read"));
    }

    // -----------------------------------------------------------------------
    // classify_risk
    // -----------------------------------------------------------------------

    #[test]
    fn test_classify_risk() {
        assert_eq!(
            ApprovalManager::classify_risk("shell_exec"),
            RiskLevel::Critical
        );
        assert_eq!(
            ApprovalManager::classify_risk("file_write"),
            RiskLevel::High
        );
        assert_eq!(
            ApprovalManager::classify_risk("file_delete"),
            RiskLevel::High
        );
        assert_eq!(
            ApprovalManager::classify_risk("web_fetch"),
            RiskLevel::Medium
        );
        assert_eq!(
            ApprovalManager::classify_risk("browser_navigate"),
            RiskLevel::Medium
        );
        assert_eq!(ApprovalManager::classify_risk("file_read"), RiskLevel::Low);
        assert_eq!(
            ApprovalManager::classify_risk("unknown_tool"),
            RiskLevel::Low
        );
    }

    // -----------------------------------------------------------------------
    // resolve nonexistent
    // -----------------------------------------------------------------------

    #[test]
    fn test_resolve_nonexistent() {
        let mgr = default_manager();
        let result = mgr.resolve(Uuid::new_v4(), ApprovalDecision::Approved, None);
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("No pending approval request"));
    }

    // -----------------------------------------------------------------------
    // submit_queued — the queue path
    // -----------------------------------------------------------------------

    #[test]
    fn test_submit_queued_visible_immediately() {
        let mgr = default_manager();
        let req = make_request("agent-1", "design_approval", 60);
        let id = req.id;
        let returned = mgr.submit_queued(req).unwrap();
        assert_eq!(returned, id);
        // The record exists before the caller is answered: readable by
        // id, present in the pending list, counted.
        match mgr.lookup(id) {
            ApprovalLookup::Pending(found) => assert_eq!(found.id, id),
            other => panic!("expected Pending, got {other:?}"),
        }
        assert!(mgr.list_pending().iter().any(|r| r.id == id));
        assert_eq!(mgr.pending_count(), 1);
    }

    #[test]
    fn test_submit_queued_cap_refuses_without_phantom() {
        let mgr = default_manager();
        for _ in 0..MAX_QUEUED_PER_AGENT {
            let req = make_request("agent-1", "design_approval", 60);
            mgr.submit_queued(req).unwrap();
        }
        assert_eq!(mgr.pending_count(), MAX_QUEUED_PER_AGENT);
        // The next submission for the same agent is refused as an
        // error, and its id names nothing in the store.
        let refused = make_request("agent-1", "design_approval", 60);
        let refused_id = refused.id;
        assert!(mgr.submit_queued(refused).is_err());
        assert!(matches!(mgr.lookup(refused_id), ApprovalLookup::Missing));
        assert_eq!(mgr.pending_count(), MAX_QUEUED_PER_AGENT);
        // A different agent is unaffected.
        let other = make_request("agent-2", "design_approval", 60);
        assert!(mgr.submit_queued(other).is_ok());
    }

    #[test]
    fn test_queued_resolve_is_idempotent() {
        let mgr = default_manager();
        let req = make_request("agent-1", "design_approval", 60);
        let id = req.id;
        mgr.submit_queued(req).unwrap();

        let first = mgr
            .resolve(id, ApprovalDecision::Approved, Some("api".to_string()))
            .unwrap();
        assert_eq!(first.decision, ApprovalDecision::Approved);
        match mgr.lookup(id) {
            ApprovalLookup::Decided(record) => {
                assert_eq!(record.decision, ApprovalDecision::Approved)
            }
            other => panic!("expected Decided, got {other:?}"),
        }

        // A repeated decide — even one asking for the opposite outcome —
        // returns the stored decision and changes nothing.
        let second = mgr
            .resolve(id, ApprovalDecision::Denied, Some("api".to_string()))
            .unwrap();
        assert_eq!(second.decision, ApprovalDecision::Approved);
        assert_eq!(second.decided_at, first.decided_at);
        assert_eq!(mgr.list_recent(10).len(), 1);
        assert_eq!(mgr.pending_count(), 0);
    }

    #[test]
    fn test_lookup_missing() {
        let mgr = default_manager();
        assert!(matches!(
            mgr.lookup(Uuid::new_v4()),
            ApprovalLookup::Missing
        ));
    }

    // -----------------------------------------------------------------------
    // list_pending empty
    // -----------------------------------------------------------------------

    #[test]
    fn test_list_pending_empty() {
        let mgr = default_manager();
        assert!(mgr.list_pending().is_empty());
        assert!(mgr.list_recent(10).is_empty());
    }

    // -----------------------------------------------------------------------
    // update_policy
    // -----------------------------------------------------------------------

    #[test]
    fn test_update_policy() {
        let mgr = default_manager();
        assert!(mgr.requires_approval("shell_exec"));
        assert!(!mgr.requires_approval("file_write"));

        let new_policy = ApprovalPolicy {
            require_approval: vec!["file_write".to_string()],
            timeout_secs: 120,
            auto_approve_autonomous: true,
            auto_approve: false,
        };
        mgr.update_policy(new_policy);

        assert!(!mgr.requires_approval("shell_exec"));
        assert!(mgr.requires_approval("file_write"));

        let policy = mgr.policy();
        assert_eq!(policy.timeout_secs, 120);
        assert!(policy.auto_approve_autonomous);
    }

    // -----------------------------------------------------------------------
    // pending_count
    // -----------------------------------------------------------------------

    #[test]
    fn test_pending_count() {
        let mgr = default_manager();
        assert_eq!(mgr.pending_count(), 0);
    }

    // -----------------------------------------------------------------------
    // request_approval — timeout
    // -----------------------------------------------------------------------

    #[tokio::test]
    async fn test_request_approval_timeout() {
        let mgr = Arc::new(default_manager());
        let req = make_request("agent-1", "shell_exec", 10);
        let decision = mgr.request_approval(req).await;
        assert_eq!(decision, ApprovalDecision::TimedOut);
        // After timeout, pending map should be cleaned up
        assert_eq!(mgr.pending_count(), 0);
        let recent = mgr.list_recent(10);
        assert_eq!(recent.len(), 1);
        assert_eq!(recent[0].decision, ApprovalDecision::TimedOut);
        assert_eq!(recent[0].request.tool_name, "shell_exec");
    }

    // -----------------------------------------------------------------------
    // request_approval — approve
    // -----------------------------------------------------------------------

    #[tokio::test]
    async fn test_request_approval_approve() {
        let mgr = Arc::new(default_manager());
        let req = make_request("agent-1", "shell_exec", 60);
        let request_id = req.id;

        let mgr2 = Arc::clone(&mgr);
        tokio::spawn(async move {
            // Small delay to let the request register
            tokio::time::sleep(std::time::Duration::from_millis(10)).await;
            let result = mgr2.resolve(
                request_id,
                ApprovalDecision::Approved,
                Some("admin".to_string()),
            );
            assert!(result.is_ok());
            let resp = result.unwrap();
            assert_eq!(resp.decision, ApprovalDecision::Approved);
            assert_eq!(resp.decided_by, Some("admin".to_string()));
        });

        let decision = mgr.request_approval(req).await;
        assert_eq!(decision, ApprovalDecision::Approved);
        let recent = mgr.list_recent(10);
        assert_eq!(recent.len(), 1);
        assert_eq!(recent[0].decision, ApprovalDecision::Approved);
        assert_eq!(recent[0].decided_by.as_deref(), Some("admin"));
    }

    // -----------------------------------------------------------------------
    // request_approval — deny
    // -----------------------------------------------------------------------

    #[tokio::test]
    async fn test_request_approval_deny() {
        let mgr = Arc::new(default_manager());
        let req = make_request("agent-1", "shell_exec", 60);
        let request_id = req.id;

        let mgr2 = Arc::clone(&mgr);
        tokio::spawn(async move {
            tokio::time::sleep(std::time::Duration::from_millis(10)).await;
            let result = mgr2.resolve(request_id, ApprovalDecision::Denied, None);
            assert!(result.is_ok());
        });

        let decision = mgr.request_approval(req).await;
        assert_eq!(decision, ApprovalDecision::Denied);
        let recent = mgr.list_recent(10);
        assert_eq!(recent.len(), 1);
        assert_eq!(recent[0].decision, ApprovalDecision::Denied);
    }

    // -----------------------------------------------------------------------
    // max pending per agent
    // -----------------------------------------------------------------------

    #[tokio::test]
    async fn test_max_pending_per_agent() {
        let mgr = Arc::new(default_manager());

        // Fill up 5 pending requests for agent-1 (they will all be waiting)
        let mut ids = Vec::new();
        for _ in 0..MAX_PENDING_PER_AGENT {
            let req = make_request("agent-1", "shell_exec", 300);
            ids.push(req.id);
            let mgr_clone = Arc::clone(&mgr);
            tokio::spawn(async move {
                mgr_clone.request_approval(req).await;
            });
        }

        // Give spawned tasks time to register
        tokio::time::sleep(std::time::Duration::from_millis(50)).await;
        assert_eq!(mgr.pending_count(), MAX_PENDING_PER_AGENT);

        // 6th request for the same agent should be immediately denied
        let req6 = make_request("agent-1", "shell_exec", 300);
        let decision = mgr.request_approval(req6).await;
        assert_eq!(decision, ApprovalDecision::Denied);

        // A different agent should still be able to submit
        let req_other = make_request("agent-2", "shell_exec", 300);
        let other_id = req_other.id;
        let mgr2 = Arc::clone(&mgr);
        tokio::spawn(async move {
            mgr2.request_approval(req_other).await;
        });
        tokio::time::sleep(std::time::Duration::from_millis(20)).await;
        assert_eq!(mgr.pending_count(), MAX_PENDING_PER_AGENT + 1);

        // Cleanup: resolve all pending to avoid hanging tasks
        for id in &ids {
            let _ = mgr.resolve(*id, ApprovalDecision::Denied, None);
        }
        let _ = mgr.resolve(other_id, ApprovalDecision::Denied, None);
    }

    // -----------------------------------------------------------------------
    // policy defaults
    // -----------------------------------------------------------------------

    #[test]
    fn test_policy_defaults() {
        let mgr = default_manager();
        let policy = mgr.policy();
        assert_eq!(policy.require_approval, vec!["shell_exec".to_string()]);
        assert_eq!(policy.timeout_secs, 60);
        assert!(!policy.auto_approve_autonomous);
    }
}
