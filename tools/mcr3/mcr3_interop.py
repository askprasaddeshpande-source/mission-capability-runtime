"""Claude Mods interoperability at the CONTRACT boundary (no import of Claude Mods code, no change to it).

What is here, all MCR-side and offline:
  * `to_pe_event` : a one-way, lossy mapping of an mcr-evidence/1 event to the scalar `pe-event/1`-style envelope that the
                    Claude Mods collector accepts (idempotent event_id, seq, evidence_class, ids{...}, data of scalar safe strings).
                    It uses a PROPOSED source (`MCR_EVIDENCE`) and kind (`mcr.evidence`) that the current closed enums do not contain;
                    ingestion therefore needs the bounded change packet (architecture/mcr3/CLAUDE_MODS_CHANGE_PACKET_R1.md).
  * `MockCollector` : behaves like the documented collector rules (closed enums unless extended, per-kind field allowlist,
                    scalar safe strings only, strip-and-count) so contract fixtures can be tested without the real service.
  * `MockEvidenceCenter` : keeps the ORIGINAL canonical event and the normalized pe-event side by side, and evaluates a session
                    without overstating correctness.
The mapping never creates authority: `authority_effect` travels as data and the mock approval boundary is unchanged.
"""
import re

import evc1

PE_SCHEMA = "pe-event/1"
CURRENT_SOURCES = ("CLAUDE_NATIVE_OTEL", "MOD_CONTEXT_GUARD", "MOD_TWIN_BRIDGE", "MOD_GUARDIAN", "MOD_OBSERVER", "ACLA_CONTEXT", "EAF_ASSURANCE", "OWNER_OUTCOME", "HARNESS")
CURRENT_KINDS = ("native.metric", "native.log", "mod.segment", "mod.mark", "mod.decision", "acla.context_decision", "eaf.authorization", "eaf.outcome_assurance", "owner.outcome", "system.heartbeat")
PROPOSED_SOURCE, PROPOSED_KIND = "MCR_EVIDENCE", "mcr.evidence"
PE_EVIDENCE_CLASSES = ("OBSERVED", "READBACK", "ESTIMATE", "CLAIMED", "SYNTHETIC", "UNKNOWN")
# MCR evidence class -> pe evidence class (lossy: the original is preserved in data.mcr_class)
CLASS_MAP = {"OBSERVED": "OBSERVED", "READBACK": "READBACK", "CORROBORATED": "READBACK", "CLAIMED": "CLAIMED", "INFERRED": "ESTIMATE",
             "HISTORICAL": "CLAIMED", "SYNTHETIC": "SYNTHETIC", "UNKNOWN": "UNKNOWN"}
DATA_ALLOWED = ("contract_version", "event_type", "layer", "claim_kind", "adapter_id", "adapter_version", "source_runtime_version", "trust", "mcr_class",
                "authority_effect", "evidence_digest", "content_digest", "outcome_class", "disposition", "result", "call_class", "commit_state", "source_level",
                "existence", "activation", "claimed_authoritative", "provenance_verified", "attempt_number", "capability_state", "capability_id")
_SAFE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:+=-]{0,95}")          # as the Claude Mods safe string: alphanumeric first, at most 96 characters
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}")
_SECRETISH = re.compile(r"(?i)(bearer\s|password|secret|apikey|api_key|token=)")


def _scalar(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    return v


def to_pe_event(event, *, producer_id, seq):
    """Map a parsed mcr-evidence/1 event. Raises ValueError if it cannot be mapped faithfully."""
    known, _ = evc1.parse(event)
    claim = known["claim"]
    cap = known.get("capability") or {}
    data = {
        "contract_version": known["contract_version"], "event_type": known["type"], "layer": claim["layer"], "claim_kind": claim["kind"],
        "adapter_id": known["producer"]["adapter_id"], "adapter_version": known["producer"]["adapter_version"],
        "source_runtime_version": known["producer"]["source_runtime_version"], "trust": known["evidence"]["trust"],
        "mcr_class": known["evidence"]["classification"], "authority_effect": known["authority_effect"],
        "evidence_digest": known["evidence"]["digest"], "content_digest": evc1.content_digest(known),
        "capability_state": cap.get("qualification_status"), "capability_id": cap.get("capability_id"),
    }
    for k in ("outcome_class", "disposition"):          # read from the claim, never from the top-level summary fields
        if claim.get(k) is not None:
            data[k] = claim[k]
    for k in ("result", "call_class", "commit_state", "source_level", "existence", "activation", "claimed_authoritative", "provenance_verified", "attempt_number"):
        if k in claim:
            data[k] = _scalar(claim[k])
    c = known["correlation"]
    for label, val in (("event_id", known["id"]), ("mission_id", c["mission_id"]), ("transaction_id", c["transaction_id"]), ("correlation_id", c["correlation_id"])):
        if val is not None and len(val) > 96:
            raise ValueError("%s is longer than the 96 characters the pe-event/1 envelope accepts" % label)
    pe = {
        "schema": PE_SCHEMA, "event_id": known["id"], "source": PROPOSED_SOURCE, "kind": PROPOSED_KIND, "ts": known["time"],
        "producer_id": producer_id, "seq": seq, "evidence_class": CLASS_MAP[known["evidence"]["classification"]],
        "ids": {"mission_id": c["mission_id"], "session_id": None, "task_id": None, "context_compile_id": None, "outcome_id": c["transaction_id"],
                "run_id": c["correlation_id"], "case_id": None},
        "component": "mcr", "component_version": known["producer"]["runtime_version"], "data": data,
    }
    return pe


class MockCollector:
    """Models the documented collector rules. `extended=False` is today's closed enum behaviour."""
    def __init__(self, extended=False):
        self.extended = extended
        self.stored = {}
        self.stripped = 0
        self.rejected = []
        self.heartbeat = 0

    def ingest(self, pe):
        sources = CURRENT_SOURCES + ((PROPOSED_SOURCE,) if self.extended else ())
        kinds = CURRENT_KINDS + ((PROPOSED_KIND,) if self.extended else ())
        why = None
        if not isinstance(pe, dict) or pe.get("schema") != PE_SCHEMA:
            why = "schema"
        elif pe.get("source") not in sources:
            why = "source not in the closed list"
        elif pe.get("kind") not in kinds:
            why = "kind not in the closed list"
        elif not isinstance(pe.get("event_id"), str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{7,95}", pe["event_id"]):
            why = "event_id"
        elif pe.get("evidence_class") not in PE_EVIDENCE_CLASSES:
            why = "evidence_class"
        if why:
            self.rejected.append(why)
            return False
        if pe["event_id"] in self.stored:                       # idempotent: same id is stored once
            return False
        data = {}
        for k, v in (pe.get("data") or {}).items():
            if k in DATA_ALLOWED and (v is None or (isinstance(v, str) and _SAFE.fullmatch(v) and not _SECRETISH.search(v))):
                data[k] = v
            else:
                self.stripped += 1
        self.stored[pe["event_id"]] = dict(pe, data=data)
        return True


class MockEvidenceCenter:
    """Holds the original and the normalized form of every event and evaluates a mission without overstating correctness."""
    def __init__(self, collector):
        self.collector = collector
        self.originals = {}

    def record(self, event, normalized_ok):
        self.originals[event["id"]] = event
        return normalized_ok

    def provenance_of(self, eid):
        o = self.originals[eid]
        n = self.collector.stored.get(eid)
        return {"original_digest": o["integrity"]["event_digest"], "original_content_digest": evc1.content_digest(o), "normalized_present": n is not None,
                "normalized_content_digest": n["data"]["content_digest"] if n else None, "adapter": o["producer"]["adapter_id"],
                "source_runtime_version": o["producer"]["source_runtime_version"]}

    def evaluate(self, mission_id):
        evs = [e for e in self.originals.values() if e["correlation"]["mission_id"] == mission_id]
        disp = [e for e in evs if e["type"] == "mcr.mission.disposition"]
        out = {"mission_id": mission_id, "events": len(evs), "disposition": None, "outcome_class": None, "trust_floor": None, "correctness": "NOT_ESTABLISHED",
               "authority_granted": False, "reasons": []}
        if not evs:
            out["reasons"].append("no events")
            return out
        order = evc1.TRUST_LEVELS
        rank = {"SIGNED_TRUSTED": 0, "SIGNED_UNTRUSTED": 1, "UNTRUSTED_RESEARCH": 2, "EXPIRED": 3, "SIGNATURE_INVALID": 4, "REPLAYED": 5, "REVOKED": 6}
        out["trust_floor"] = max((e["evidence"]["trust"] for e in evs), key=lambda x: rank[x])
        if disp:
            c = disp[-1]["claim"]
            out["disposition"], out["outcome_class"] = c["disposition"], c["outcome_class"]
        classes = {e["evidence"]["classification"] for e in evs}
        if out["disposition"] != "COMPLETE":
            out["reasons"].append("mission is not COMPLETE")
        if classes & {"SYNTHETIC", "HISTORICAL", "CLAIMED", "INFERRED", "UNKNOWN"}:
            out["reasons"].append("evidence includes non-independent classes %s" % sorted(classes & {"SYNTHETIC", "HISTORICAL", "CLAIMED", "INFERRED", "UNKNOWN"}))
        if out["trust_floor"] != "SIGNED_TRUSTED":
            out["reasons"].append("not every event is SIGNED_TRUSTED (floor %s)" % out["trust_floor"])
        # even the best case is only "evidence supports the outcome": never "the task was correct"
        if not out["reasons"]:
            out["correctness"] = "EVIDENCE_SUPPORTS_RECORDED_OUTCOME"
        return out
