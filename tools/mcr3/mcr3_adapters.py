"""Reference adapters from MCR evidence to the Evidence Contract v1 (mcr-evidence/1).

Adapter A (`Mcr2ReferenceAdapter`) reads FROZEN MCR R2.0 evidence (the archived live-run result) and converts only what that
file states. It never back-fills: the 14th chain link was not emitted by the live run, the predicates digest and the
expected-outcome digest are not in the archived result, the readback's "authoritative" label is the runner's own, and
activation and package membership were not established. Everything it emits is HISTORICAL, unsigned
(UNTRUSTED_RESEARCH), and carries `time_semantics: CONVERSION_TIME_NOT_OCCURRENCE_TIME`.

Adapter B (`Mcr3NativeAdapter`) converts a 3.0 `Mission` (its evidence slots and outcome classification) with the same
externally defined semantics.

Both start in OBSERVATION_ONLY mode with DEFAULT_AUTHORITY=NONE (see mcr3_authority.Adapter). Neither signs, approves or
executes anything.
"""
import hashlib
import json
import os
import re

import evc1
import mcr3_authority as A
import mcr3_model as M

ADAPTER_VERSION = "1.0.0"
RUNTIME_VERSION = "3.0.0"
_ENTITY = re.compile(evc1.ENTITY_ID_RE)


def low(h):
    return h.lower() if isinstance(h, str) else h


def _id(*parts):
    return "EVT-" + hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:24]


def _safe_id(value, fallback_prefix):
    v = str(value)
    return v if _ENTITY.fullmatch(v) else fallback_prefix + hashlib.sha256(v.encode("utf-8")).hexdigest()[:16]


def corr_id(mission_id, transaction_id):
    return "CORR-" + hashlib.sha256(("%s|%s" % (mission_id, transaction_id)).encode("utf-8")).hexdigest()[:16]


class _Builder:
    """Chains events: each event's causation_id is its direct predecessor."""
    def __init__(self, *, adapter_id, adapter_version, source_runtime_version, now, mission_id, transaction_id, classification,
                 capability, principal=None, authorization_ref=None, source_prefix, lineage_note=None, extensions=None, provenance=None):
        self.kw = dict(adapter_id=adapter_id, adapter_version=adapter_version, source_runtime_version=source_runtime_version, runtime_version=RUNTIME_VERSION)
        self.now, self.mission_id, self.transaction_id, self.classification = now, mission_id, transaction_id, classification
        self.capability, self.principal, self.authorization_ref = capability, principal, authorization_ref
        self.source_prefix, self.lineage_note, self.extensions, self.provenance = source_prefix, lineage_note, extensions, provenance
        self.events = []
        self.last_id = None
        self.attempt_id = None

    def add(self, etype, claim, evidence_digest, evidence_ref, *, classification=None, disposition=None, outcome_class=None, budget=None, attempt=False, key=""):
        eid = _id(self.mission_id, self.transaction_id, etype, evidence_digest, key)
        corr = {"mission_id": self.mission_id, "transaction_id": self.transaction_id,
                "correlation_id": corr_id(self.mission_id, self.transaction_id), "causation_id": self.last_id}
        if attempt or self.attempt_id:
            corr["mutation_attempt_id"] = self.attempt_id
        e = evc1.make_event(etype, claim, event_id=eid, source="%s/%s" % (self.source_prefix, etype.split(".", 1)[1].replace(".", "/")), time=self.now,
                            correlation=corr, evidence_digest=low(evidence_digest), evidence_ref=evidence_ref,
                            classification=classification or self.classification, capability=self.capability, principal=self.principal,
                            budget=budget, authorization_ref=self.authorization_ref if etype == "mcr.authorization.referenced" else None,
                            disposition=disposition, outcome_class=outcome_class, provenance=self.provenance,
                            lineage=({"transformations": [self.lineage_note], "source_event_id": None, "source_digest": None, "supersedes": None} if self.lineage_note else None),
                            extensions=self.extensions, **self.kw)
        self.events.append(e)
        self.last_id = eid
        return e


def _capability(capability_id, status, provider_id, target, operation):
    return {"capability_id": capability_id, "qualification_status": status, "provider_id": provider_id, "target_system": target, "operation": operation}


# ---------------------------------------------------------------- Adapter B: MCR 3.0 native
class Mcr3NativeAdapter:
    ADAPTER_ID = "mcr3-native"

    @staticmethod
    def declaration():
        return A.Adapter(Mcr3NativeAdapter.ADAPTER_ID, RUNTIME_VERSION, evc1.CURRENT_VERSION, ["*"], "OBSERVED|READBACK|SYNTHETIC (per run)",
                         "unsigned unless a verifier attaches provenance; authority_effect NONE", mode="OBSERVATION_ONLY",
                         limitations=["Mission cannot verify provenance", "identity assurance is SELF_REPORTED", "no approval is known to the model"])

    def convert(self, mission, *, now, classification="SYNTHETIC", capability_status="QUARANTINED", authorization_ref=None, provenance=None, source_prefix="mcr://runtime/3.0"):
        ev = mission.ev
        if "intent" not in ev:
            return []
        cb, pv = ev.get("capability"), ev.get("provider")
        cap = _capability(cb["capability"] if cb else "UNBOUND", capability_status, pv["provider_id"] if pv else None, ev["intent"]["target_system"], cb["capability"] if cb else None)
        pr = ev.get("principal")
        principal = {"principal_ref": low(pr["object_hash"]), "assurance": "SELF_REPORTED", "delegation_ref": low(ev["delegation"]["object_hash"]) if "delegation" in ev else None} if pr else None
        b = _Builder(adapter_id=self.ADAPTER_ID, adapter_version=ADAPTER_VERSION, source_runtime_version=RUNTIME_VERSION, now=now, mission_id=mission.mission_id,
                     transaction_id=mission.transaction_id, classification=classification, capability=cap, principal=principal, authorization_ref=authorization_ref,
                     source_prefix=source_prefix, provenance=provenance)
        b.add("mcr.mission.started", {"intent_digest": low(ev["intent"]["object_hash"]), "target_system": ev["intent"]["target_system"]}, ev["intent"]["object_hash"], "mission:intent")
        if authorization_ref is not None:
            b.add("mcr.authorization.referenced", {"referenced": True}, authorization_ref["approval_id_hash"], "approval:external")
        if "mutation_id" in ev:
            b.attempt_id = _safe_id(ev["mutation_id"], "ATT-")
            budget = {"mutation_budget": mission.max_mutations, "attempt_number": mission.mutations_sent or 1, "attempts_remaining": mission.remaining, "kind": "FORWARD"}
            b.add("mcr.mutation.attempted", {"attempt_id": b.attempt_id, "attempt_number": mission.mutations_sent or 1, "budget_remaining_after": mission.remaining, "budget_kind": "FORWARD"},
                  ev["checkpoint"]["object_hash"], "mission:checkpoint", budget=budget, attempt=True)
        er = ev.get("execution_receipt")
        if er:
            b.add("mcr.execution.receipt", {"call_class": er["call_class"], "provider_acknowledged": er["call_class"] == "PROVIDER_RESPONSE_SUCCESS", "implies_commit": False},
                  er["object_hash"], "mission:execution_receipt")
        rb = ev.get("readback")
        if rb:
            rc = ev["readback_contract"]
            b.add("mcr.readback.claimed", {"source_level": rb["source_level"], "claimed_authoritative": rb["source_level"] == "AUTHORITATIVE_REPOSITORY",
                                           "existence": rb["existence"], "activation": rb["activation"], "checks_satisfied": bool(M.Mission._checks_satisfied(rc, rb)),
                                           "provenance_verified": False}, rb["object_hash"], "mission:readback",
                  classification="READBACK" if classification != "SYNTHETIC" else "SYNTHETIC")
        co = ev.get("commit")
        if co:
            b.add("mcr.commit.observed", {"commit_state": co["commit_state"], "readback_digest": low(rb["object_hash"]), "implies_outcome": False}, co["object_hash"], "mission:commit")
        oo = ev.get("outcome")
        if oo:
            oc = ev["outcome_contract"]
            b.add("mcr.outcome.evaluated", {"expected_digest": low(oc["object_hash"]), "observed_digest": evc1.digest_of(rb["observed"]), "readback_digest": low(rb["object_hash"]),
                                            "predicates_digest": evc1.digest_of(oc["predicates"]), "result": oo["result"]}, oo["object_hash"], "mission:outcome")
        for entry in ev.get("comp_log", []):
            b.add("mcr.compensation.attempted", {"attempt_number": entry["attempt"], "call_class": entry["call_class"],
                                                 "resolved": entry["call_class"] not in M.COMP_UNKNOWN_CLASSES}, entry["receipt_hash"], "mission:comp_log", key=str(entry["attempt"]))
        if mission.state == "COMPENSATED" and "comp_receipt" in ev:
            n = ev.get("comp_attempts", 1)
            b.add("mcr.compensation.attempted", {"attempt_number": n, "call_class": "PROVIDER_RESPONSE_SUCCESS", "resolved": True}, ev["comp_receipt"]["object_hash"], "mission:comp_receipt", key="ok")
        chain = M.chain_hashes(mission)
        if chain:
            disp = self._disposition(mission)
            b.add("mcr.mission.disposition", {"disposition": disp, "outcome_class": M.outcome_classification(mission), "chain_digests": [low(h) for _, h in chain]},
                  chain[-1][1], "mission:chain", disposition=disp, outcome_class=M.outcome_classification(mission), key=mission.state)
        return b.events

    @staticmethod
    def _disposition(m):
        st = m.state
        if st == "COMPLETE":
            return "COMPLETE"
        if st == "COMPENSATED":
            return "COMPENSATED"
        if st == "UNRECOVERABLE":
            return "UNRECOVERABLE"
        if st == "FAILED_BEFORE_MUTATION":
            return "FAILED"
        if st in ("COMMIT_STATE_UNKNOWN", "FAILED_AFTER_POSSIBLE_MUTATION"):
            return "COMMIT_UNKNOWN"
        if st in ("COMPENSATION_REQUIRED", "COMPENSATION_AUTHORIZED"):
            return "COMPENSATION_REQUIRED"
        if st == "OUTCOME_VALIDATION_PENDING" and m.ev.get("outcome", {}).get("result") == "UNKNOWN":
            return "OUTCOME_UNKNOWN"
        return "INCOMPLETE"


# ---------------------------------------------------------------- Adapter A: MCR 2.0 reference (frozen evidence)
R2_LABELS = ["MISSION_INTENT", "PRINCIPAL_CONTEXT", "DELEGATION", "AUTHORITY", "CAPABILITY_BINDING", "PROVIDER_CONTRACT", "MUTATION_BUDGET", "TRANSACTION",
             "PREWRITE_CHECKPOINT", "EXECUTION_RECEIPT", "COMMIT_OBSERVATION", "AUTHORITATIVE_READBACK_RECEIPT", "OUTCOME_RECEIPT"]


class Mcr2ReferenceAdapter:
    ADAPTER_ID = "mcr2-reference"

    @staticmethod
    def declaration():
        return A.Adapter(Mcr2ReferenceAdapter.ADAPTER_ID, "2.0.0", evc1.CURRENT_VERSION, ["abap_creation-create_object"], "HISTORICAL",
                         "unsigned frozen evidence; research use only", mode="OBSERVATION_ONLY",
                         limitations=["one live observation", "completion receipt (link 14) not emitted by the live run", "expected-outcome and predicate digests absent from the archive",
                                      "the readback's 'authoritative' label is the runner's own", "activation and package membership not established",
                                      "times are conversion times, not occurrence times"])

    def convert(self, result, *, now, source_ref, mission_id="M-R2-0C-LIVE", transaction_id="TX-R2-0C-LIVE"):
        """result: the parsed archived live-execution result. Raises ValueError if it does not have the frozen shape."""
        chain = result.get("chain") if isinstance(result, dict) else None
        if not isinstance(chain, list) or [c[0] for c in chain if isinstance(c, list) and len(c) == 2] != R2_LABELS:
            raise ValueError("not a frozen R2.0 live-run result (chain shape)")
        h = {label: low(hh) for label, hh in chain}
        if not all(re.fullmatch(evc1.HASH_RE, v) for v in h.values()):
            raise ValueError("chain hashes are not 64-hex digests")
        ro = result.get("readback_observed", {})
        path = result.get("create_response", {}).get("semanticFilePath", "")
        target = path.split("/")[1] if path.startswith("/") and len(path.split("/")) > 2 else None
        cap = _capability("abap_creation-create_object", "QUARANTINED", None, target, "create_object")
        ext = {"time_semantics": "CONVERSION_TIME_NOT_OCCURRENCE_TIME", "source_file": source_ref, "source_runner_sha256": result.get("runner_sha256"),
               "source_reported_final_state": result.get("final_state"), "completion_receipt_link": "NOT_EMITTED_BY_THE_HISTORICAL_RUN",
               "live": bool(result.get("live")), "single_observation": True}
        note = {"step": "convert", "from": "mcr2.0/live-result", "to": evc1.CONTRACT, "tool": "mcr2-reference", "tool_version": ADAPTER_VERSION}
        b = _Builder(adapter_id=self.ADAPTER_ID, adapter_version=ADAPTER_VERSION, source_runtime_version="2.0.0", now=now, mission_id=mission_id,
                     transaction_id=transaction_id, classification="HISTORICAL", capability=cap, principal=None, source_prefix="mcr://runtime/2.0",
                     lineage_note=note, extensions=ext)
        ref = lambda i: "%s#chain[%d]" % (source_ref, i)
        b.add("mcr.mission.started", {"intent_digest": h["MISSION_INTENT"], "target_system": target or "UNKNOWN_IN_ARCHIVE"}, h["MISSION_INTENT"], ref(0))
        b.attempt_id = "ATT-R2-0C-LIVE-1"
        b.add("mcr.mutation.attempted", {"attempt_id": b.attempt_id, "attempt_number": 1, "budget_remaining_after": 0, "budget_kind": "FORWARD"},
              h["PREWRITE_CHECKPOINT"], ref(8), budget={"mutation_budget": 1, "attempt_number": 1, "attempts_remaining": 0, "kind": "FORWARD"}, attempt=True)
        cc = result.get("execution_call_class")
        b.add("mcr.execution.receipt", {"call_class": cc, "provider_acknowledged": cc == "PROVIDER_RESPONSE_SUCCESS", "implies_commit": False}, h["EXECUTION_RECEIPT"], ref(9))
        ex = result.get("readback_existence", "UNKNOWN")
        b.add("mcr.readback.claimed", {"source_level": "AUTHORITATIVE_REPOSITORY", "claimed_authoritative": True, "existence": ex,
                                       "activation": "UNKNOWN", "checks_satisfied": bool(ro.get("exists") is True), "provenance_verified": False},
              h["AUTHORITATIVE_READBACK_RECEIPT"], ref(11))
        cs = "COMMITTED" if ex == "EXISTS" and result.get("RESULT", "").startswith("COMMITTED") else "UNKNOWN"
        b.add("mcr.commit.observed", {"commit_state": cs, "readback_digest": h["AUTHORITATIVE_READBACK_RECEIPT"], "implies_outcome": False}, h["COMMIT_OBSERVATION"], ref(10))
        res = "PASS" if result.get("RESULT") == "COMMITTED_AND_OUTCOME_VALIDATED" else "UNKNOWN"
        b.add("mcr.outcome.evaluated", {"expected_digest": None, "observed_digest": evc1.digest_of(ro), "readback_digest": h["AUTHORITATIVE_READBACK_RECEIPT"],
                                        "predicates_digest": None, "result": res}, h["OUTCOME_RECEIPT"], ref(12))
        # 13 links only: the disposition is INCOMPLETE however the source labelled its final state
        b.add("mcr.mission.disposition", {"disposition": "INCOMPLETE", "outcome_class": "OUTCOME_VALIDATED" if res == "PASS" else "OUTCOME_UNKNOWN",
                                          "chain_digests": [h[l] for l in R2_LABELS]}, h["OUTCOME_RECEIPT"], source_ref + "#chain", disposition="INCOMPLETE",
              outcome_class="OUTCOME_VALIDATED" if res == "PASS" else "OUTCOME_UNKNOWN")
        return b.events


def load_r2_live_result(repo_root):
    p = os.path.join(repo_root, "evidence", "r2.0", "MCR_R2_0_C_LIVE_EXECUTION_RESULT_R1.json")
    return json.load(open(p, encoding="utf-8")), "evidence/r2.0/MCR_R2_0_C_LIVE_EXECUTION_RESULT_R1.json"
