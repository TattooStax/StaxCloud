"""Slice S3 — customer-facing design flow (PLAN-v2 §5; LOOP-OVERNIGHT S3).

One intake contract for every customer channel (sms | email | widget),
one offer rule, one lifecycle, one estimate guard. This module owns
the CONVERSATION STATE around generation — it never generates pixels
itself (the model call stays in the agent's chat image path, PLAN §6)
and it never relaxes a gate:

- GATE 1 (opt-in): the design offer exists ONLY for an artist whose
  `allow_customer_designs` is on. Routing runs first (descriptors pick
  the best fit); the offer is then checked against that artist's flag.
  An ambiguous fit returns a customer-facing CHOICE between the
  fitting artists — filtered to those who opted in — never a silent
  default. No fit, or no fitting artist opted in, means NO offer and
  the reason is returned, not hidden.
- GATE 2 (artist approval is absolute): a request moves
  received -> routed -> planned -> awaiting_artist -> artist_approved
  before anything is sent to the customer, and the customer-visible
  design record (the one `ProfileStore.customer_view` reads) is only
  created AT artist approval. A rejected request is terminal: it can
  never reach sent_to_customer, and its customer view stays empty.
- GATE 3 (estimates): any outbound customer message carrying a
  price/hours figure is refused unless the text is estimate-framed
  (the word "estimate" AND the every-person-is-different framing)
  AND the artist has been alerted (`artist_alerted` on the request).
  A bare price promise is refused outright — see `check_outbound`.

Lifecycle (exactly the LOOP-OVERNIGHT S3 chain):

    received -> routed -> planned -> awaiting_artist
             -> artist_approved | artist_rejected
    artist_approved -> sent_to_customer
    sent_to_customer -> revision_requested -> planned   (new round,
                        same artist, same style anchor, round + 1)
    sent_to_customer -> customer_approved -> stencil_ready

Entering stencil_ready saves the design under the artist (their
profile's generated_history) and attaches the stencil reference to
the customer record.
"""

from __future__ import annotations

import copy
import re

from .generate import plan_versions, route_request
from .profiles import ProfileStore

CHANNELS = ("sms", "email", "widget")

# The lifecycle states, in chain order (artist_rejected branches off
# awaiting_artist; revision_requested loops back to planned).
STATES = (
    "received", "routed", "planned", "awaiting_artist",
    "artist_approved", "artist_rejected", "sent_to_customer",
    "revision_requested", "customer_approved", "stencil_ready",
)

_ALLOWED: dict[str, tuple[str, ...]] = {
    "received": ("routed",),
    "routed": ("planned",),
    "planned": ("awaiting_artist",),
    "awaiting_artist": ("artist_approved", "artist_rejected"),
    "artist_approved": ("sent_to_customer",),
    "artist_rejected": (),
    "sent_to_customer": ("revision_requested", "customer_approved"),
    "revision_requested": ("planned",),
    "customer_approved": ("stencil_ready",),
    "stencil_ready": (),
}


class InvalidTransition(Exception):
    """A lifecycle move the state machine does not allow."""


# ---------------------------------------------------------------------
# Intake — one contract for sms | email | widget (PLAN §5)
# ---------------------------------------------------------------------

INTAKE_FIELDS = ("request_id", "channel", "customer_id", "prompt_text",
                 "placement", "size_mm", "reference_ref", "ts")


def make_intake(request_id: str, channel: str, customer_id: str,
                prompt_text: str, placement=None, size_mm=None,
                reference_ref=None, ts=None) -> dict:
    """The single intake record every channel produces. No channel
    gets its own shape — sms, email and the widget differ only in the
    `channel` value carried here."""
    if channel not in CHANNELS:
        raise ValueError(f"unknown channel {channel!r} (expected one of {CHANNELS})")
    if not customer_id:
        raise ValueError("intake requires a customer_id")
    if not prompt_text or not str(prompt_text).strip():
        raise ValueError("intake requires prompt_text")
    if isinstance(size_mm, tuple):
        size_mm = list(size_mm)
    return {
        "request_id": request_id,
        "channel": channel,
        "customer_id": customer_id,
        "prompt_text": prompt_text,
        "placement": placement,
        "size_mm": size_mm,
        "reference_ref": reference_ref,
        "ts": ts,
    }


# ---------------------------------------------------------------------
# Offer logic — Gate 1 (route first, opt-in decides)
# ---------------------------------------------------------------------


def evaluate_offer(prompt_text: str, store: ProfileStore) -> dict:
    """Decide whether a design offer exists for this prompt.

    Returns one of:
      {offer: True, artist_id, routing, reason}
          — a single best-fit artist, opted in.
      {offer: False, choice_required: True, choice: [artist_id, ...],
       routing, reason}
          — ambiguous fit; the customer is asked to pick between the
          fitting artists who opted in (two or more of them).
      {offer: True, artist_id, routing, reason}  (narrowed choice)
          — ambiguous fit, but exactly ONE fitting artist opted in,
          so the choice has narrowed to that artist.
      {offer: False, reason, routing}
          — no fit at all, or the fitting artist(s) have not opted
          in. No offer is made; the reason says why.
    """
    routing = route_request(prompt_text, store)
    if routing is None:
        return {"offer": False, "routing": None,
                "reason": "no artist profile fits this request — no offer"}
    if "ambiguous" in routing:
        fitting = list(routing["ambiguous"])
        opted = [a for a in fitting if store.can_offer_customer_designs(a)]
        if not opted:
            return {"offer": False, "routing": routing,
                    "reason": "fitting artists "
                              f"({', '.join(fitting)}) have not opted in to "
                              "customer designs — no offer"}
        if len(opted) == 1:
            return {"offer": True, "artist_id": opted[0], "routing": routing,
                    "reason": f"ambiguous fit narrowed: only {opted[0]} of the "
                              f"fitting artists ({', '.join(fitting)}) has "
                              "opted in to customer designs"}
        return {"offer": False, "choice_required": True, "choice": opted,
                "routing": routing,
                "reason": "equal fit between opted-in artists "
                          f"{', '.join(opted)} — ask the customer to choose"}
    artist_id = routing["artist_id"]
    if not store.can_offer_customer_designs(artist_id):
        return {"offer": False, "routing": routing,
                "reason": f"best-fit artist {artist_id} has not opted in to "
                          "customer designs — no offer"}
    return {"offer": True, "artist_id": artist_id, "routing": routing,
            "reason": f"offer available: {routing['reason']}; "
                      f"{artist_id} has opted in to customer designs"}


# ---------------------------------------------------------------------
# Estimate guard — Gate 3 (PLAN §5; standing pricing rule)
# ---------------------------------------------------------------------

_FIGURE_PATTERNS = (
    re.compile(r"\$\s?\d"),                                            # $300
    re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:hours?|hrs?)\b", re.IGNORECASE),  # 2 hours
    re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:dollars|bucks)\b", re.IGNORECASE),
)


def _has_price_or_hours_figure(text: str) -> bool:
    return any(p.search(text or "") for p in _FIGURE_PATTERNS)


def _is_estimate_framed(text: str) -> tuple[bool, str]:
    low = re.sub(r"\s+", " ", (text or "").lower().replace("-", " "))
    if "estimate" not in low:
        return False, "the text carries a price/hours figure but is not " \
                      "framed as an estimate (the word 'estimate' is missing)"
    if "every person is different" not in low:
        return False, "the text says 'estimate' but is missing the " \
                      "every-person-is-different framing (no definite " \
                      "time can be given)"
    return True, ""


def _alerted_flag(request) -> bool:
    if request is None:
        return False
    if isinstance(request, dict):
        return bool(request.get("artist_alerted", False))
    return bool(getattr(request, "artist_alerted", False))


def check_outbound(request, text: str) -> tuple[bool, str]:
    """Gate an outbound customer message. Returns (ok, reason):
    (True, "ok") when the message may go out, (False, <refusal
    reason>) when the flow must refuse it.

    A message with NO price/hours figure needs no estimate framing.
    A message WITH one is refused unless BOTH hold: it is
    estimate-framed (word 'estimate' + every-person-is-different)
    and the artist was alerted first (`artist_alerted` on the
    request). Bare price promises fail the first test outright."""
    if not _has_price_or_hours_figure(text):
        return True, "ok"
    framed, why = _is_estimate_framed(text)
    if not framed:
        return False, f"refused: {why} — a price is never promised, " \
                      "estimates only"
    if not _alerted_flag(request):
        return False, "refused: estimate is framed, but the artist has " \
                      "not been alerted yet — alert the artist before " \
                      "any estimate is sent"
    return True, "ok"


# ---------------------------------------------------------------------
# The request + flow
# ---------------------------------------------------------------------


class DesignRequest:
    """One customer's design request and its lifecycle state."""

    def __init__(self, intake: dict):
        self.intake = dict(intake)
        self.request_id = intake["request_id"]
        self.channel = intake["channel"]
        self.customer_id = intake["customer_id"]
        self.prompt_text = intake["prompt_text"]
        self.placement = intake.get("placement")
        self.size_mm = intake.get("size_mm")
        self.reference_ref = intake.get("reference_ref")
        self.ts = intake.get("ts")

        self.status = "received"
        self.history: list[str] = ["received"]
        self.routing: dict | None = None
        self.offer: dict | None = None
        self.pending_choice: list[str] | None = None
        self.artist_id: str | None = None
        self.round = 0                       # planning rounds (1-based once planned)
        self.versions: list[dict] = []       # current round's plan
        self.plans: list[dict] = []          # every round's plan, in order
        self.style_anchor_prompt: str | None = None  # first round's anchor carrier
        self.feedback: list[str] = []
        self.artist_alerted = False
        self.design_id: str | None = None
        self.stencil_ref: str | None = None

    # -- state machine ---------------------------------------------------
    def _transition(self, new_state: str) -> None:
        if new_state not in _ALLOWED[self.status]:
            raise InvalidTransition(
                f"{self.request_id}: {self.status} -> {new_state} is not "
                f"allowed (from {self.status} only: "
                f"{', '.join(_ALLOWED[self.status]) or 'nothing — terminal'})")
        self.status = new_state
        self.history.append(new_state)

    def to_dict(self) -> dict:
        return {
            "intake": dict(self.intake),
            "status": self.status,
            "history": list(self.history),
            "artist_id": self.artist_id,
            "routing": copy.deepcopy(self.routing),
            "round": self.round,
            "versions": copy.deepcopy(self.versions),
            "feedback": list(self.feedback),
            "artist_alerted": self.artist_alerted,
            "design_id": self.design_id,
            "stencil_ref": self.stencil_ref,
        }


class CustomerFlow:
    """Owns design requests against a ProfileStore.

    `designs` is the customer-record list `ProfileStore.customer_view`
    reads ({id, customer_id, artist_id, approved, preview_ref, ...});
    an entry is created ONLY at artist approval (Gate 2), so the
    customer view is empty for received/routed/planned/awaiting and
    for rejected requests — by construction, not by filtering here.
    """

    def __init__(self, store: ProfileStore):
        self.store = store
        self.requests: dict[str, DesignRequest] = {}
        self.designs: list[dict] = []
        self._counter = 0

    # -- intake ------------------------------------------------------------
    def intake(self, channel: str, customer_id: str, prompt_text: str,
               placement=None, size_mm=None, reference_ref=None,
               ts=None, request_id: str | None = None) -> DesignRequest:
        if request_id is None:
            self._counter += 1
            request_id = f"req-{self._counter}"
        if request_id in self.requests:
            raise ValueError(f"duplicate request_id {request_id!r}")
        record = make_intake(request_id, channel, customer_id, prompt_text,
                             placement=placement, size_mm=size_mm,
                             reference_ref=reference_ref, ts=ts)
        req = DesignRequest(record)
        self.requests[request_id] = req
        return req

    def get(self, request_id: str) -> DesignRequest:
        try:
            return self.requests[request_id]
        except KeyError:
            raise KeyError(f"no design request {request_id!r}") from None

    # -- offer + routing -----------------------------------------------------
    def evaluate(self, request_id: str) -> dict:
        """The offer decision for a received request (no state change)."""
        return evaluate_offer(self.get(request_id).prompt_text, self.store)

    def route(self, request_id: str, chosen_artist_id: str | None = None) -> dict:
        """received -> routed, under Gate 1.

        Without a fitting opted-in artist the request stays in
        `received` and the result explains why (no offer / a pending
        customer choice). With `chosen_artist_id` (the customer's
        answer to a choice) the pick is validated against the fitting
        opted-in artists — never accepted blind."""
        req = self.get(request_id)
        if req.status != "received":
            raise InvalidTransition(
                f"{request_id}: route() needs status 'received', is {req.status!r}")
        if chosen_artist_id is not None:
            decision = evaluate_offer(req.prompt_text, self.store)
            allowed = []
            if decision.get("offer"):
                allowed = [decision["artist_id"]]
            if decision.get("choice"):
                allowed = list(decision["choice"])
            if chosen_artist_id not in allowed:
                return {"routed": False, "offer": decision,
                        "reason": f"chosen artist {chosen_artist_id!r} is not "
                                  f"among the fitting opted-in artists {allowed}"}
            req.routing = decision.get("routing")
            req.offer = decision
            req.pending_choice = None
            req.artist_id = chosen_artist_id
            req._transition("routed")
            return {"routed": True, "artist_id": chosen_artist_id,
                    "offer": decision,
                    "reason": f"customer chose {chosen_artist_id} from the "
                              "fitting opted-in artists"}

        decision = evaluate_offer(req.prompt_text, self.store)
        req.offer = decision
        req.routing = decision.get("routing")
        if decision.get("choice_required"):
            req.pending_choice = list(decision["choice"])
            return {"routed": False, "choice_required": True,
                    "choice": list(decision["choice"]), "offer": decision,
                    "reason": decision["reason"]}
        if not decision.get("offer"):
            return {"routed": False, "offer": decision,
                    "reason": decision["reason"]}
        req.artist_id = decision["artist_id"]
        req._transition("routed")
        return {"routed": True, "artist_id": req.artist_id,
                "offer": decision, "reason": decision["reason"]}

    # -- planning -------------------------------------------------------------
    def _plan_round(self, req: DesignRequest, feedback: str | None = None) -> list[dict]:
        plan = plan_versions(
            {"subject": req.prompt_text, "placement": req.placement or "",
             "size_mm": req.size_mm, "artist_id": req.artist_id},
            self.store)
        versions = copy.deepcopy(plan["versions"])
        for v in versions:
            refs = list(v.get("reference_ids", []))
            if req.reference_ref and req.reference_ref not in refs:
                refs.append(req.reference_ref)
            v["reference_ids"] = refs
            if feedback:
                v["seed"] = int(v["seed"]) + req.round * 10000
                v["prompt"] = (f"{v['prompt']} Revision round {req.round} — "
                               f"fold this feedback into the SAME style, do "
                               f"not add detail: {feedback}")
        if req.style_anchor_prompt is None and versions:
            req.style_anchor_prompt = versions[0]["prompt"]
        req.versions = versions
        req.plans.append({"round": req.round, "versions": copy.deepcopy(versions),
                          "feedback": feedback})
        return versions

    def plan(self, request_id: str) -> list[dict]:
        """routed -> planned. Version count comes from the routed
        artist's `versions_per_request` (via plan_versions)."""
        req = self.get(request_id)
        if req.status != "routed":
            raise InvalidTransition(
                f"{request_id}: plan() needs status 'routed', is {req.status!r}")
        req.round = 1
        versions = self._plan_round(req)
        req._transition("planned")
        return versions

    def submit_to_artist(self, request_id: str) -> None:
        """planned -> awaiting_artist."""
        self.get(request_id)._transition("awaiting_artist")

    # -- artist decision (Gate 2) ----------------------------------------------
    def _design_record(self, req: DesignRequest) -> dict:
        for d in self.designs:
            if d["id"] == req.design_id:
                return d
        raise KeyError(req.design_id)  # pragma: no cover - guarded by callers

    def artist_approve(self, request_id: str) -> dict:
        """awaiting_artist -> artist_approved. THE moment a
        customer-visible design record comes into existence."""
        req = self.get(request_id)
        req._transition("artist_approved")
        preview_ref = f"preview/{req.request_id}/r{req.round}"
        if req.design_id is None:
            req.design_id = f"design-{req.request_id}"
            self.designs.append({
                "id": req.design_id,
                "customer_id": req.customer_id,
                "artist_id": req.artist_id,
                "approved": True,
                "preview_ref": preview_ref,
                "approved_round": req.round,
            })
        else:
            record = self._design_record(req)
            record["preview_ref"] = preview_ref
            record["approved_round"] = req.round
            record["approved"] = True
        return self._design_record(req)

    def artist_reject(self, request_id: str) -> None:
        """awaiting_artist -> artist_rejected (terminal). No design
        record is created, so the customer view stays empty."""
        self.get(request_id)._transition("artist_rejected")

    # -- sending ------------------------------------------------------------------
    def alert_artist(self, request_id: str) -> None:
        """Record that the artist was alerted (Gate 3's second half:
        required before any estimate leaves the building)."""
        self.get(request_id).artist_alerted = True

    def send_to_customer(self, request_id: str, text: str | None = None) -> None:
        """artist_approved -> sent_to_customer. If an outbound text is
        given it is estimate-gated first; a refusal raises and the
        request does NOT advance."""
        req = self.get(request_id)
        if text is not None:
            ok, reason = check_outbound(req, text)
            if not ok:
                raise PermissionError(reason)
        req._transition("sent_to_customer")

    # -- revision loop ---------------------------------------------------------
    def request_revision(self, request_id: str, feedback: str) -> list[dict]:
        """sent_to_customer -> revision_requested -> planned (new round).

        The customer's feedback creates a NEW planned round under the
        SAME artist and the SAME style anchor: routing is not re-run,
        the plan is re-issued for the already-routed artist with the
        feedback folded into every version's prompt (in the same
        style — the prompt says so), and the round increments. The
        new round is NOT customer-visible until the artist approves
        it and it is sent again — it re-enters at planned."""
        req = self.get(request_id)
        if not feedback or not str(feedback).strip():
            raise ValueError("a revision needs the customer's feedback text")
        req._transition("revision_requested")
        req.feedback.append(feedback)
        req.round += 1
        versions = self._plan_round(req, feedback=feedback)
        req._transition("planned")
        return versions

    # -- customer decision + stencil --------------------------------------------
    def customer_approve(self, request_id: str) -> None:
        """sent_to_customer -> customer_approved."""
        self.get(request_id)._transition("customer_approved")

    def mark_stencil_ready(self, request_id: str) -> dict:
        """customer_approved -> stencil_ready (and ONLY from there).

        Saves the design under the artist (their profile's
        generated_history) and attaches the stencil reference to the
        customer record."""
        req = self.get(request_id)
        req._transition("stencil_ready")
        req.stencil_ref = f"stencil/{req.request_id}"
        record = self._design_record(req)
        record["stencil_ref"] = req.stencil_ref
        record["status"] = "stencil_ready"
        profile = self.store.get(req.artist_id)
        entry = {"request_id": req.request_id, "design_id": req.design_id,
                 "customer_id": req.customer_id, "channel": req.channel,
                 "rounds": req.round, "stencil_ref": req.stencil_ref}
        if entry not in profile["generated_history"]:
            profile["generated_history"].append(entry)
        return record

    # -- customer view ---------------------------------------------------------
    def customer_designs(self, customer_id: str) -> list[dict]:
        """What a customer can see — delegated to the profile store's
        customer_view, so this flow and the UI scoping can never
        disagree about Gate 2."""
        return ProfileStore.customer_view(customer_id, self.designs)
