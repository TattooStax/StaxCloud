//! Execution approval manager — gates dangerous operations behind human approval.

use chrono::Utc;
use dashmap::DashMap;
use openfang_types::approval::{
    ApprovalDecision, ApprovalPolicy, ApprovalRequest, ApprovalResponse, RiskLevel,
};
use std::collections::VecDeque;
use std::io::Write;
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
    /// Durable decision ledger (Work build §5): the daemon-owned,
    /// append-only record of every decision, attached by the kernel
    /// at boot. Without one (unit tests, embedded use) decisions are
    /// in-memory only, exactly as before this build.
    ledger: Option<std::sync::Arc<DecisionLedger>>,
    /// Lineage index for queued holds (Work build §6.4): draft key +
    /// round → the live approval carrying it. Makes queue submission
    /// idempotent on lineage across carriers and races.
    lineage_index: DashMap<(String, Option<u32>), Uuid>,
    /// Serializes decide/supersede so a decision is ledger-first
    /// (§5.2.3): no second decider can observe the gap between the
    /// pending removal and the ledger append.
    decide_lock: std::sync::Mutex<()>,
    /// Serializes lineage check-and-insert in `submit_queued`.
    lineage_lock: std::sync::Mutex<()>,
}

struct PendingRequest {
    request: ApprovalRequest,
    sender: tokio::sync::oneshot::Sender<ApprovalDecision>,
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct ApprovalRecord {
    pub request: ApprovalRequest,
    pub decision: ApprovalDecision,
    pub decided_at: chrono::DateTime<Utc>,
    pub decided_by: Option<String>,
    /// Server-stamped decision provenance (Work build §3): the
    /// authenticated session class that decided, from the daemon's
    /// auth context — `owner_session`, `api_token`, `agent`, or
    /// `system`. Never caller-supplied.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub decided_via: Option<String>,
}

/// Why a queued submission was refused. The queue cap is the only
/// refusal today; it is typed so carriers can count it without
/// parsing prose (Work build §4.5 — the API renders it as
/// `reason: "queue_full"`).
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SubmitQueuedError {
    QueueFull { agent_id: String },
}

impl std::fmt::Display for SubmitQueuedError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            SubmitQueuedError::QueueFull { agent_id } => write!(
                f,
                "Too many pending approvals for agent {agent_id} (max {MAX_QUEUED_PER_AGENT})"
            ),
        }
    }
}

impl std::error::Error for SubmitQueuedError {}

/// Append-only durable decision ledger (Work build §5.2): one JSON
/// record per line in a daemon-owned file under the data dir. A
/// decision is written and synced here before `resolve` reports it,
/// so decided history survives restarts while the pending store
/// stays in-memory by design. Append-only: no eviction, no rewrite.
pub struct DecisionLedger {
    inner: std::sync::Mutex<LedgerInner>,
}

struct LedgerInner {
    file: std::fs::File,
    records: std::collections::HashMap<Uuid, ApprovalRecord>,
    order: Vec<Uuid>,
}

impl DecisionLedger {
    /// Open (creating if needed) the ledger at `path` and load every
    /// record it already holds. A torn final line — the signature of
    /// a crash mid-append, whose decision was never reported — is
    /// skipped with a warning rather than failing the daemon.
    pub fn open(path: &std::path::Path) -> std::io::Result<Self> {
        let mut records = std::collections::HashMap::new();
        let mut order = Vec::new();
        if path.is_file() {
            let text = std::fs::read_to_string(path)?;
            for line in text.lines() {
                let line = line.trim();
                if line.is_empty() {
                    continue;
                }
                match serde_json::from_str::<ApprovalRecord>(line) {
                    Ok(record) => {
                        let id = record.request.id;
                        if records.insert(id, record).is_none() {
                            order.push(id);
                        }
                    }
                    Err(e) => {
                        warn!(path = %path.display(), error = %e,
                              "decision ledger: skipping unreadable line");
                    }
                }
            }
        }
        let file = std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(path)?;
        info!(path = %path.display(), records = order.len(),
              "decision ledger opened");
        Ok(Self {
            inner: std::sync::Mutex::new(LedgerInner {
                file,
                records,
                order,
            }),
        })
    }

    /// Append one decision and sync it to disk before returning.
    pub fn append(&self, record: &ApprovalRecord) -> std::io::Result<()> {
        let line = serde_json::to_string(record)
            .map_err(std::io::Error::from)?;
        let mut inner = self.inner.lock().unwrap_or_else(|e| e.into_inner());
        inner.file.write_all(line.as_bytes())?;
        inner.file.write_all(b"\n")?;
        inner.file.sync_all()?;
        let id = record.request.id;
        if inner.records.insert(id, record.clone()).is_none() {
            inner.order.push(id);
        }
        Ok(())
    }

    pub fn get(&self, id: &Uuid) -> Option<ApprovalRecord> {
        let inner = self.inner.lock().unwrap_or_else(|e| e.into_inner());
        inner.records.get(id).cloned()
    }

    /// All ledger records, newest first.
    pub fn list(&self) -> Vec<ApprovalRecord> {
        let inner = self.inner.lock().unwrap_or_else(|e| e.into_inner());
        inner
            .order
            .iter()
            .rev()
            .filter_map(|id| inner.records.get(id).cloned())
            .collect()
    }

    pub fn len(&self) -> usize {
        let inner = self.inner.lock().unwrap_or_else(|e| e.into_inner());
        inner.order.len()
    }

    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }
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
            ledger: None,
            lineage_index: DashMap::new(),
            decide_lock: std::sync::Mutex::new(()),
            lineage_lock: std::sync::Mutex::new(()),
        }
    }

    /// Attach the durable decision ledger (Work build §5). Called
    /// once by the kernel at boot with a path under its data dir.
    pub fn attach_ledger(&mut self, path: &std::path::Path) -> std::io::Result<()> {
        let ledger = DecisionLedger::open(path)?;
        self.ledger = Some(std::sync::Arc::new(ledger));
        Ok(())
    }

    /// Number of decisions in the durable ledger (0 without one).
    pub fn ledger_len(&self) -> usize {
        self.ledger.as_ref().map(|l| l.len()).unwrap_or(0)
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
                self.push_recent(
                    request,
                    ApprovalDecision::TimedOut,
                    None,
                    Some("system".to_string()),
                    Utc::now(),
                );
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
    pub fn submit_queued(
        &self,
        req: ApprovalRequest,
    ) -> Result<Uuid, SubmitQueuedError> {
        // Lineage idempotency (Work build §6.4): a submission whose
        // draft key + round already has a LIVE approval returns that
        // approval's id — two carriers, or two racing submissions,
        // resolve to one hold. Check-and-insert runs under a lock so
        // simultaneity cannot split it.
        let lineage_key = req
            .lineage
            .as_ref()
            .map(|l| (l.draft_key.clone(), l.round));
        let _lineage_guard = if lineage_key.is_some() {
            Some(self.lineage_lock.lock().unwrap_or_else(|e| e.into_inner()))
        } else {
            None
        };
        if let Some(key) = &lineage_key {
            if let Some(existing) = self.lineage_index.get(key).map(|e| *e.value()) {
                if matches!(self.lookup(existing), ApprovalLookup::Pending(_)) {
                    debug!(request_id = %existing,
                           "Queued submission already carried under this lineage");
                    return Ok(existing);
                }
            }
        }
        let agent_pending = self
            .pending
            .iter()
            .filter(|r| r.value().request.agent_id == req.agent_id)
            .count();
        if agent_pending >= MAX_QUEUED_PER_AGENT {
            warn!(agent_id = %req.agent_id, "Queued approval rejected: too many pending");
            return Err(SubmitQueuedError::QueueFull {
                agent_id: req.agent_id.clone(),
            });
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
        if let Some(key) = lineage_key {
            self.lineage_index.insert(key, id);
        }
        info!(request_id = %id, "Queued approval submitted");
        Ok(id)
    }

    /// Look up one request by id across the pending map and the
    /// decided history, so a caller holding an id reads the same fact
    /// the list views are built from. The durable ledger outranks the
    /// in-memory recent list: decisions win (Work build §5.2.4).
    pub fn lookup(&self, request_id: Uuid) -> ApprovalLookup {
        if let Some(entry) = self.pending.get(&request_id) {
            return ApprovalLookup::Pending(entry.value().request.clone());
        }
        if let Some(ledger) = &self.ledger {
            if let Some(record) = ledger.get(&request_id) {
                return ApprovalLookup::Decided(record);
            }
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
    ///
    /// Ledger-first (Work build §5.2.3): with a ledger attached, the
    /// decision is appended and synced there before it is applied or
    /// reported; if the write fails the approval stays pending and
    /// the decider gets an error — never an in-memory-only decision.
    /// `decided_via` is the daemon-stamped provenance of the deciding
    /// session class (Consult 12 Q3); callers pass the auth context's
    /// class, never a caller-supplied value.
    pub fn resolve(
        &self,
        request_id: Uuid,
        decision: ApprovalDecision,
        decided_by: Option<String>,
        decided_via: Option<String>,
    ) -> Result<ApprovalResponse, String> {
        let _decide_guard = self.decide_lock.lock().unwrap_or_else(|e| e.into_inner());
        match self.pending.remove(&request_id) {
            Some((_, pending)) => {
                let record = ApprovalRecord {
                    request: pending.request.clone(),
                    decision,
                    decided_at: Utc::now(),
                    decided_by: decided_by.clone(),
                    decided_via: decided_via.clone(),
                };
                if let Some(ledger) = &self.ledger {
                    if let Err(e) = ledger.append(&record) {
                        // Not applied: the hold goes back to pending
                        // untouched and the decider sees the failure.
                        self.pending.insert(request_id, pending);
                        return Err(format!(
                            "decision ledger write failed: {e}"
                        ));
                    }
                }
                self.push_recent_record(&record);
                self.clear_lineage(&pending.request);
                // Send decision to waiting agent (ignore error if receiver dropped)
                let _ = pending.sender.send(decision);
                info!(request_id = %request_id, ?decision, "Approval request resolved");
                Ok(ApprovalResponse {
                    request_id,
                    decision,
                    decided_at: record.decided_at,
                    decided_by,
                    decided_via,
                })
            }
            None => match self.lookup(request_id) {
                ApprovalLookup::Decided(record) => match record.decision {
                    ApprovalDecision::Approved
                    | ApprovalDecision::Denied
                    | ApprovalDecision::Superseded => Ok(ApprovalResponse {
                        request_id,
                        decision: record.decision,
                        decided_at: record.decided_at,
                        decided_by: record.decided_by,
                        decided_via: record.decided_via,
                    }),
                    ApprovalDecision::TimedOut => Err(format!(
                        "Approval request {request_id} already timed out"
                    )),
                },
                _ => Err(format!("No pending approval request with id {request_id}")),
            },
        }
    }

    /// Administratively terminalize a pending queued hold as
    /// superseded (Work build §12.2.4): the reconciliation
    /// mechanism's verb, distinct from approve/reject. Writes the
    /// same durable ledger record a decision writes, but fires no
    /// waiter and no consumer effect — consumers reading the record
    /// see a terminal `superseded`, never an outcome they act on.
    /// Idempotent for an already-superseded id; a real human
    /// decision (approved/denied) is never overwritten by it.
    pub fn supersede(
        &self,
        request_id: Uuid,
        decided_by: Option<String>,
        decided_via: Option<String>,
    ) -> Result<ApprovalResponse, String> {
        let _decide_guard = self.decide_lock.lock().unwrap_or_else(|e| e.into_inner());
        if let ApprovalLookup::Decided(record) = self.lookup(request_id) {
            return match record.decision {
                ApprovalDecision::Superseded => Ok(ApprovalResponse {
                    request_id,
                    decision: record.decision,
                    decided_at: record.decided_at,
                    decided_by: record.decided_by,
                    decided_via: record.decided_via,
                }),
                ApprovalDecision::TimedOut => Err(format!(
                    "Approval request {request_id} already timed out"
                )),
                _ => Err(format!(
                    "Approval request {request_id} already decided; supersede cannot override a decision"
                )),
            };
        }
        let Some((_, pending)) = self.pending.remove(&request_id) else {
            return Err(format!("No pending approval request with id {request_id}"));
        };
        let record = ApprovalRecord {
            request: pending.request.clone(),
            decision: ApprovalDecision::Superseded,
            decided_at: Utc::now(),
            decided_by: decided_by.clone(),
            decided_via: decided_via.clone(),
        };
        if let Some(ledger) = &self.ledger {
            if let Err(e) = ledger.append(&record) {
                self.pending.insert(request_id, pending);
                return Err(format!("decision ledger write failed: {e}"));
            }
        }
        self.push_recent_record(&record);
        self.clear_lineage(&pending.request);
        info!(request_id = %request_id, "Approval request superseded");
        Ok(ApprovalResponse {
            request_id,
            decision: ApprovalDecision::Superseded,
            decided_at: record.decided_at,
            decided_by,
            decided_via,
        })
    }

    fn clear_lineage(&self, request: &ApprovalRequest) {
        if let Some(l) = &request.lineage {
            self.lineage_index
                .remove(&(l.draft_key.clone(), l.round));
        }
    }

    fn push_recent_record(&self, record: &ApprovalRecord) {
        let mut recent = self.recent.lock().unwrap_or_else(|e| e.into_inner());
        recent.push_front(record.clone());
        while recent.len() > MAX_RECENT_APPROVALS {
            recent.pop_back();
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

    /// All decided records, newest first — the Finished view's
    /// source (Work build §5.2.4). The durable ledger is the spine;
    /// in-memory recent records the ledger does not hold (decided
    /// before a ledger attached, or timed out) merge in, deduplicated
    /// by id, the ledger's copy winning any conflict. Not truncated
    /// at the recent-list limits: counts of this list are counts of
    /// the ledger.
    pub fn list_decided(&self) -> Vec<ApprovalRecord> {
        let mut seen = std::collections::HashSet::new();
        let mut out: Vec<ApprovalRecord> = Vec::new();
        if let Some(ledger) = &self.ledger {
            for record in ledger.list() {
                if seen.insert(record.request.id) {
                    out.push(record);
                }
            }
        }
        for record in self.list_recent(usize::MAX) {
            if seen.insert(record.request.id) {
                out.push(record);
            }
        }
        out.sort_by(|a, b| b.decided_at.cmp(&a.decided_at));
        out
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
        decided_via: Option<String>,
        decided_at: chrono::DateTime<Utc>,
    ) {
        self.push_recent_record(&ApprovalRecord {
            request,
            decision,
            decided_at,
            decided_by,
            decided_via,
        });
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
            lineage: None,
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
        let result = mgr.resolve(Uuid::new_v4(), ApprovalDecision::Approved, None, None);
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
            .resolve(id, ApprovalDecision::Approved, Some("api".to_string()), Some("api_token".to_string()))
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
            .resolve(id, ApprovalDecision::Denied, Some("api".to_string()), Some("api_token".to_string()))
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
                Some("owner_session".to_string()),
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
            let result = mgr2.resolve(request_id, ApprovalDecision::Denied, None, None);
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
            let _ = mgr.resolve(*id, ApprovalDecision::Denied, None, None);
        }
        let _ = mgr.resolve(other_id, ApprovalDecision::Denied, None, None);
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

    // -----------------------------------------------------------------------
    // Work build §5 — the decision ledger
    // -----------------------------------------------------------------------

    fn manager_with_ledger(path: &std::path::Path) -> ApprovalManager {
        let mut mgr = default_manager();
        mgr.attach_ledger(path).unwrap();
        mgr
    }

    #[test]
    fn test_decisions_survive_a_fresh_manager() {
        let dir = std::env::temp_dir().join(format!(
            "fang-ledger-test-{}",
            std::process::id()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("decisions.jsonl");
        let (id_a, id_b, id_c) = {
            let mgr = manager_with_ledger(&path);
            let a = make_request("agent-1", "design_approval", 60);
            let b = make_request("agent-1", "sms_reply", 60);
            let c = make_request("agent-1", "sms_reply", 60);
            let (ia, ib, ic) = (a.id, b.id, c.id);
            mgr.submit_queued(a).unwrap();
            mgr.submit_queued(b).unwrap();
            mgr.submit_queued(c).unwrap();
            mgr.resolve(ia, ApprovalDecision::Approved,
                        Some("admin".to_string()),
                        Some("owner_session".to_string())).unwrap();
            mgr.resolve(ib, ApprovalDecision::Denied,
                        Some("api".to_string()),
                        Some("api_token".to_string())).unwrap();
            assert_eq!(mgr.ledger_len(), 2);
            (ia, ib, ic)
        };
        // A fresh manager over the same file = a daemon restart.
        let mgr = manager_with_ledger(&path);
        match mgr.lookup(id_a) {
            ApprovalLookup::Decided(r) => {
                assert_eq!(r.decision, ApprovalDecision::Approved);
                assert_eq!(r.decided_by.as_deref(), Some("admin"));
                assert_eq!(r.decided_via.as_deref(), Some("owner_session"));
            }
            other => panic!("expected Decided, got {other:?}"),
        }
        match mgr.lookup(id_b) {
            ApprovalLookup::Decided(r) => {
                assert_eq!(r.decision, ApprovalDecision::Denied);
                assert_eq!(r.decided_via.as_deref(), Some("api_token"));
            }
            other => panic!("expected Decided, got {other:?}"),
        }
        assert!(matches!(mgr.lookup(id_c), ApprovalLookup::Missing));
        assert_eq!(mgr.list_decided().len(), 2);
        // Re-deciding after the restart returns the stored decision,
        // even with the opposite verb — no second ledger record.
        let again = mgr
            .resolve(id_a, ApprovalDecision::Denied, None, None)
            .unwrap();
        assert_eq!(again.decision, ApprovalDecision::Approved);
        assert_eq!(mgr.ledger_len(), 2);
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn test_ledger_write_failure_keeps_the_hold_pending() {
        // /dev/full accepts opens and fails every write (ENOSPC) —
        // the failure-injection stand-in for an unavailable store.
        let mut mgr = default_manager();
        mgr.attach_ledger(std::path::Path::new("/dev/full")).unwrap();
        let req = make_request("agent-1", "design_approval", 60);
        let id = req.id;
        mgr.submit_queued(req).unwrap();
        let result = mgr.resolve(
            id,
            ApprovalDecision::Approved,
            Some("admin".to_string()),
            Some("owner_session".to_string()),
        );
        assert!(result.is_err(), "resolve must fail when the ledger does");
        assert!(result.unwrap_err().contains("decision ledger"));
        // The decision was NOT applied: still pending, still decidable
        // in the store's own view, nothing in the decided list.
        assert!(matches!(mgr.lookup(id), ApprovalLookup::Pending(_)));
        assert_eq!(mgr.pending_count(), 1);
        assert!(mgr.list_decided().is_empty());
    }

    // -----------------------------------------------------------------------
    // Work build §6.4 — lineage-idempotent submission
    // -----------------------------------------------------------------------

    fn lineage_request(agent: &str, draft_key: &str, round: Option<u32>) -> ApprovalRequest {
        let mut req = make_request(agent, "design_approval", 60);
        req.lineage = Some(openfang_types::approval::ApprovalLineage {
            draft_key: draft_key.to_string(),
            request_key: Some("req-1".to_string()),
            round,
        });
        req
    }

    #[test]
    fn test_lineage_submission_is_idempotent() {
        let mgr = default_manager();
        let first = mgr
            .submit_queued(lineage_request("agent-1", "draft/design-req-1", Some(1)))
            .unwrap();
        // A second carrier submitting the same draft + round gets
        // the same approval back — no second mint.
        let second = mgr
            .submit_queued(lineage_request("agent-1", "draft/design-req-1", Some(1)))
            .unwrap();
        assert_eq!(first, second);
        assert_eq!(mgr.pending_count(), 1);
        // A different round is a different hold.
        let third = mgr
            .submit_queued(lineage_request("agent-1", "draft/design-req-1", Some(2)))
            .unwrap();
        assert_ne!(first, third);
        assert_eq!(mgr.pending_count(), 2);
        // Once decided, the lineage frees: a fresh submission mints.
        mgr.resolve(first, ApprovalDecision::Approved, None, None)
            .unwrap();
        let fourth = mgr
            .submit_queued(lineage_request("agent-1", "draft/design-req-1", Some(1)))
            .unwrap();
        assert_ne!(first, fourth);
        assert!(matches!(mgr.lookup(fourth), ApprovalLookup::Pending(_)));
    }

    #[test]
    fn test_cap_error_is_typed_queue_full() {
        let mgr = default_manager();
        for _ in 0..MAX_QUEUED_PER_AGENT {
            mgr.submit_queued(make_request("agent-1", "design_approval", 60))
                .unwrap();
        }
        let err = mgr
            .submit_queued(make_request("agent-1", "design_approval", 60))
            .unwrap_err();
        assert_eq!(
            err,
            SubmitQueuedError::QueueFull {
                agent_id: "agent-1".to_string()
            }
        );
    }

    // -----------------------------------------------------------------------
    // Work build §12 — supersede
    // -----------------------------------------------------------------------

    #[test]
    fn test_supersede_is_terminal_idempotent_and_never_overrides() {
        let dir = std::env::temp_dir().join(format!(
            "fang-supersede-test-{}",
            std::process::id()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        let mgr = manager_with_ledger(&dir.join("decisions.jsonl"));
        let req = lineage_request("agent-1", "draft/sms-1", None);
        let id = req.id;
        mgr.submit_queued(req).unwrap();
        let resp = mgr
            .supersede(id, Some("cleanup".to_string()), Some("api_token".to_string()))
            .unwrap();
        assert_eq!(resp.decision, ApprovalDecision::Superseded);
        assert_eq!(mgr.pending_count(), 0);
        match mgr.lookup(id) {
            ApprovalLookup::Decided(r) => {
                assert_eq!(r.decision, ApprovalDecision::Superseded)
            }
            other => panic!("expected Decided, got {other:?}"),
        }
        // Idempotent: a second supersede returns the stored record.
        let again = mgr.supersede(id, None, None).unwrap();
        assert_eq!(again.decision, ApprovalDecision::Superseded);
        assert_eq!(mgr.ledger_len(), 1);
        // A human decision cannot be superseded after the fact.
        let req2 = make_request("agent-1", "sms_reply", 60);
        let id2 = req2.id;
        mgr.submit_queued(req2).unwrap();
        mgr.resolve(id2, ApprovalDecision::Approved, None, None)
            .unwrap();
        assert!(mgr.supersede(id2, None, None).is_err());
        match mgr.lookup(id2) {
            ApprovalLookup::Decided(r) => {
                assert_eq!(r.decision, ApprovalDecision::Approved)
            }
            other => panic!("expected Decided, got {other:?}"),
        }
        std::fs::remove_dir_all(&dir).ok();
    }
}
