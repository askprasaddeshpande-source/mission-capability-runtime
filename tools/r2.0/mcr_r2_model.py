"""MCR R2.0A outcome model: state machine, hash-addressed objects, guards.

Deterministic, dependency-free, no network, no enterprise access.
Evidence class of everything produced by this module: SYNTHETIC/LOCAL.
Design rule: a state is entered only through a guard that demands the specific
evidence object for that state. No state is inferred from an earlier one.
"""
import functools
import hashlib
import json

# ---------------------------------------------------------------- hashing
def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def chash(obj):
    return hashlib.sha256(canon(obj).encode("ascii")).hexdigest().upper()


# ---------------------------------------------------------------- states
STATES = [
    "PLANNED", "CONTEXT_READY", "AUTHORIZED", "BOUND", "PREWRITE_VALIDATED",
    "EXECUTION_STARTED", "EXECUTED", "COMMIT_STATE_UNKNOWN", "COMMITTED",
    "AUTHORITATIVE_READBACK_PENDING", "AUTHORITATIVE_READBACK_OBSERVED",
    "OUTCOME_VALIDATION_PENDING", "OUTCOME_VALIDATED", "COMPLETE",
    "FAILED_BEFORE_MUTATION", "FAILED_AFTER_POSSIBLE_MUTATION",
    "COMPENSATION_REQUIRED", "COMPENSATION_AUTHORIZED", "COMPENSATED",
    "UNRECOVERABLE",
]
TERMINAL = {"COMPLETE", "COMPENSATED", "UNRECOVERABLE", "FAILED_BEFORE_MUTATION"}

TRANSITIONS = {
    "PLANNED": {"CONTEXT_READY", "FAILED_BEFORE_MUTATION"},
    "CONTEXT_READY": {"AUTHORIZED", "FAILED_BEFORE_MUTATION"},
    "AUTHORIZED": {"BOUND", "FAILED_BEFORE_MUTATION"},
    "BOUND": {"PREWRITE_VALIDATED", "FAILED_BEFORE_MUTATION"},
    "PREWRITE_VALIDATED": {"EXECUTION_STARTED", "FAILED_BEFORE_MUTATION"},
    # once EXECUTION_STARTED the call may have left the client: no FAILED_BEFORE_MUTATION
    "EXECUTION_STARTED": {"EXECUTED", "COMMIT_STATE_UNKNOWN", "FAILED_AFTER_POSSIBLE_MUTATION"},
    "EXECUTED": {"AUTHORITATIVE_READBACK_PENDING", "COMMIT_STATE_UNKNOWN"},
    "COMMIT_STATE_UNKNOWN": {"AUTHORITATIVE_READBACK_PENDING", "FAILED_AFTER_POSSIBLE_MUTATION"},
    "AUTHORITATIVE_READBACK_PENDING": {
        "AUTHORITATIVE_READBACK_OBSERVED", "COMMIT_STATE_UNKNOWN"},
    # observed readback decides COMMITTED (EXISTS) or not-committed (ABSENT) or stays unknown
    "AUTHORITATIVE_READBACK_OBSERVED": {
        "COMMITTED", "COMMIT_STATE_UNKNOWN", "FAILED_AFTER_POSSIBLE_MUTATION"},
    "COMMITTED": {"OUTCOME_VALIDATION_PENDING"},
    "OUTCOME_VALIDATION_PENDING": {
        "OUTCOME_VALIDATED", "COMPENSATION_REQUIRED"},
    "OUTCOME_VALIDATED": {"COMPLETE"},
    "FAILED_AFTER_POSSIBLE_MUTATION": {
        "AUTHORITATIVE_READBACK_PENDING", "COMPENSATION_REQUIRED", "UNRECOVERABLE"},
    "COMPENSATION_REQUIRED": {"COMPENSATION_AUTHORIZED", "UNRECOVERABLE"},
    "COMPENSATION_AUTHORIZED": {"COMPENSATED", "UNRECOVERABLE"},
    "COMPLETE": set(), "COMPENSATED": set(), "UNRECOVERABLE": set(),
    "FAILED_BEFORE_MUTATION": set(),
}

# ---------------------------------------------------------------- enums
READBACK_EXISTENCE = ("EXISTS", "ABSENT", "UNKNOWN")
READBACK_ACTIVATION = ("ACTIVE", "INACTIVE", "UNKNOWN")
# Only the first level can establish enterprise state.
SOURCE_LEVELS = ("AUTHORITATIVE_REPOSITORY", "PROVIDER_VALIDATION", "PROVIDER_LOG",
                 "TRANSPORT_SUCCESS", "CACHED_OUTPUT", "LOCAL_RUNNER_STATE", "INFERRED_OR_REGEX")
CALL_CLASSES = ("CALL_NOT_SENT", "CALL_SENT_NO_RESPONSE", "PROVIDER_ERROR",
                "PROVIDER_RESPONSE_SUCCESS", "COMMIT_UNKNOWN", "COMMIT_CONFIRMED",
                "OUTCOME_FAILED", "OUTCOME_VALIDATED")
TRI = ("PASS", "FAIL", "UNKNOWN")

# ---------------------------------------------------------------- schemas
# name -> (required fields, enum constraints)
SCHEMAS = {
    "MissionIntent": (["mission_id", "objective", "target_system", "expected_outcome_hash"], {}),
    "PrincipalContext": (["principal_id", "tenant", "roles"], {}),
    "DelegationEnvelope": (["delegation_id", "principal_hash", "scope", "max_mutations", "expires_at"], {}),
    "ExecutionAuthority": (["authority_id", "delegation_hash", "mission_id", "scope", "max_mutations", "single_use"], {}),
    "CapabilityBinding": (["binding_id", "authority_hash", "capability", "provider_ref"], {}),
    "ProviderBinding": (["provider_id", "tool_name", "contract_fingerprint", "identity"], {}),
    "MutationBudget": (["budget_id", "authority_hash", "max_mutations", "retries", "expansion_allowed"], {}),
    "TransactionEnvelope": (["transaction_id", "mission_id", "mutation_ids", "boundary"], {}),
    "PreMutationCheckpoint": (["checkpoint_id", "transaction_hash", "budget_hash", "outcome_contract_hash",
                               "readback_contract_hash", "remaining_budget"], {}),
    "ExecutionReceipt": (["receipt_id", "transaction_id", "mutation_id", "call_class"], {"call_class": CALL_CLASSES}),
    "CommitObservation": (["observation_id", "transaction_id", "mutation_id", "readback_receipt_hash", "commit_state"],
                          {"commit_state": ("COMMITTED", "ABSENT", "UNKNOWN")}),
    "AuthoritativeReadbackContract": (["contract_id", "source_level_required", "provider_ref", "checks"],
                                      {"source_level_required": SOURCE_LEVELS}),
    "AuthoritativeReadbackReceipt": (["receipt_id", "transaction_id", "mutation_id", "contract_hash",
                                      "source_level", "existence", "activation", "observed"],
                                     {"source_level": SOURCE_LEVELS, "existence": READBACK_EXISTENCE,
                                      "activation": READBACK_ACTIVATION}),
    "ExpectedOutcomeContract": (["outcome_contract_id", "mission_id", "transaction_id", "predicates", "frozen"], {}),
    "OutcomePredicate": (["field", "op", "expected"], {"op": ("eq", "ne", "in")}),
    "OutcomeReceipt": (["receipt_id", "transaction_id", "readback_receipt_hash", "outcome_contract_hash", "result"],
                       {"result": TRI}),
    "CompletionReceipt": (["receipt_id", "transaction_id", "outcome_receipt_hash", "commit_observation_hash",
                           "execution_receipt_hash", "authority_hash"], {}),
    "ContinuationLease": (["lease_id", "checkpoint_hash", "transaction_id", "remaining_budget", "consumed_authority_ids"], {}),
    "ReplayGuard": (["guard_id", "consumed"], {}),
    "CompensationGrant": (["grant_id", "target", "capability", "max_mutations", "preconditions",
                           "outcome_predicates", "inherits_forward_authority", "issued_by"], {}),
    "CompensationReceipt": (["receipt_id", "grant_hash", "readback_receipt_hash", "result"], {"result": TRI}),
    "ContractLease": (["lease_id", "provider_ref", "contract_fingerprint", "mission_relevant_fields"], {}),
    "ContractFingerprint": (["provider_ref", "tool_name", "schema_hash", "description_hash"], {}),
    "GovernanceTelemetry": (["mission_id", "governance_ns", "provider_ns"], {}),
    "EvidenceEnvelope": (["envelope_id", "mission_id", "transaction_id", "chain", "evidence_class"],
                         {"evidence_class": ("PROVEN", "OBSERVED", "PARTIAL", "SYNTHETIC", "LOCAL",
                                             "NOT_ESTABLISHED", "DEFERRED", "REJECTED")}),
}


class SchemaError(ValueError):
    pass


def make(kind, **fields):
    """Build a hash-addressed object. Hash covers the whole body (incl. refs)."""
    req, enums = SCHEMAS[kind]
    missing = [f for f in req if f not in fields]
    if missing:
        raise SchemaError("%s missing %s" % (kind, missing))
    for f, allowed in enums.items():
        if fields[f] not in allowed:
            raise SchemaError("%s.%s=%r not in %s" % (kind, f, fields[f], allowed))
    body = {"kind": kind, **fields}
    return {**body, "object_hash": chash(body)}


def verify_hash(obj):
    body = {k: v for k, v in obj.items() if k != "object_hash"}
    return obj.get("object_hash") == chash(body)


# ---------------------------------------------------------------- outcome predicates
class GuardError(Exception):
    pass


PRED_OPS = ("eq", "ne", "in")


def check_predicates(predicates):
    """A usable predicate list is non-empty and well-formed. Empty lists are vacuous and refused."""
    if not isinstance(predicates, (list, tuple)) or not predicates:
        raise GuardError("empty predicate list is vacuous")
    for p in predicates:
        if not isinstance(p, dict) or not {"field", "op", "expected"} <= set(p):
            raise GuardError("malformed predicate")
        if p["op"] not in PRED_OPS:
            raise GuardError("unknown predicate op %r" % (p["op"],))
        if p["op"] == "in" and not isinstance(p["expected"], (list, tuple, set, frozenset)):
            raise GuardError("op 'in' needs a collection")


def eval_predicates(predicates, observed):
    """Tri-state. A missing observed field is UNKNOWN, never FAIL or PASS. Empty/unknown-op predicates raise."""
    check_predicates(predicates)
    result = "PASS"
    for p in predicates:
        if p["field"] not in observed or observed[p["field"]] in (None, "UNKNOWN"):
            result = "UNKNOWN" if result != "FAIL" else result
            continue
        v, e, op = observed[p["field"]], p["expected"], p["op"]
        ok = (v == e) if op == "eq" else (v != e) if op == "ne" else (v in e)
        if not ok:
            return "FAIL"
    return result


# ---------------------------------------------------------------- authority checks
def attenuated(child_scope, parent_scope):
    return set(child_scope) <= set(parent_scope)


# Library trust boundary: guards protect against logic errors and malformed/forged EVIDENCE presented to a
# Mission. They do not defend against hostile code running in the same process (which can mutate objects).
# Direct state changes are refused unless they come through a guard method (token below).
_TOKEN = object()

SLOT_KINDS = {"intent": "MissionIntent", "principal": "PrincipalContext", "delegation": "DelegationEnvelope",
              "authority": "ExecutionAuthority", "capability": "CapabilityBinding", "provider": "ProviderBinding",
              "budget": "MutationBudget", "tx": "TransactionEnvelope", "checkpoint": "PreMutationCheckpoint",
              "execution_receipt": "ExecutionReceipt", "commit": "CommitObservation",
              "readback": "AuthoritativeReadbackReceipt", "outcome": "OutcomeReceipt",
              "outcome_contract": "ExpectedOutcomeContract", "readback_contract": "AuthoritativeReadbackContract",
              "completion": "CompletionReceipt"}
POST_SEND_CLASSES = ("PROVIDER_RESPONSE_SUCCESS", "CALL_SENT_NO_RESPONSE", "PROVIDER_ERROR", "COMMIT_UNKNOWN")
# Evidence a resumed mission may be given: pre-observation only. Readback, commit, outcome and completion must
# be produced fresh by the guard methods after resume.
RESUME_SLOTS = ("intent", "principal", "delegation", "capability", "provider", "tx", "budget", "outcome_contract",
                "readback_contract", "authority", "execution_receipt")


def atomic(fn):
    """A guard method either fully succeeds or changes nothing (state, evidence, budget, replay set)."""
    @functools.wraps(fn)
    def wrapper(self, *a, **k):
        snap = (self.state, list(self.history), dict(self.ev), self.remaining, set(self.consumed), self.mutations_sent)
        try:
            return fn(self, *a, **k)
        except BaseException:
            self.state, self.history, self.ev, self.remaining, self.consumed, self.mutations_sent = snap
            raise
    return wrapper


class Mission:
    """Evidence-gated state machine. Every advance() names the evidence it relies on."""

    def __init__(self, mission_id, transaction_id, max_mutations):
        self.mission_id = mission_id
        self.transaction_id = transaction_id
        self.state = "PLANNED"
        self.history = [("PLANNED", None)]
        self.ev = {}                     # evidence slot -> object
        self.remaining = max_mutations
        self.consumed = set()            # ReplayGuard: (authority hash, mutation id) already consumed
        self.mutations_sent = 0
        self.max_mutations = max_mutations
        self.sap_writes_by_model = 0

    # -- helpers
    def _go(self, to, ref=None, _tok=None):
        if _tok is not _TOKEN:
            raise GuardError("direct state change refused: %s must be entered through its guard method" % to)
        if to not in TRANSITIONS[self.state]:
            raise GuardError("illegal transition %s -> %s" % (self.state, to))
        self.state = to
        self.history.append((to, ref))

    def _need(self, slot):
        if slot not in self.ev:
            raise GuardError("missing evidence %s" % slot)
        return self.ev[slot]

    def _corr(self, obj):
        if obj.get("transaction_id") != self.transaction_id:
            raise GuardError("transaction correlation mismatch on %s" % obj.get("kind"))

    # -- forward path
    @atomic
    def context_ready(self, intent, principal):
        self.ev["intent"], self.ev["principal"] = intent, principal
        self._go("CONTEXT_READY", intent["object_hash"], _tok=_TOKEN)

    @atomic
    def authorize(self, delegation, authority, budget):
        if authority["delegation_hash"] != delegation["object_hash"]:
            raise GuardError("authority not derived from delegation")
        if authority["mission_id"] != self.mission_id:
            raise GuardError("authority mission mismatch")
        if not attenuated(authority["scope"], delegation["scope"]):
            raise GuardError("authority exceeds delegation (no attenuation)")
        if authority["max_mutations"] > delegation["max_mutations"]:
            raise GuardError("authority mutation count exceeds delegation")
        if budget["authority_hash"] != authority["object_hash"] or budget["max_mutations"] > authority["max_mutations"]:
            raise GuardError("budget not bounded by authority")
        if budget["expansion_allowed"] or budget["retries"] != 0:
            raise GuardError("budget must forbid expansion and retries")
        if any((k[0] if isinstance(k, tuple) else k) == authority["object_hash"] for k in self.consumed):
            raise GuardError("authority already consumed")
        self.ev.update(delegation=delegation, authority=authority, budget=budget)
        self._go("AUTHORIZED", authority["object_hash"], _tok=_TOKEN)

    @atomic
    def bind(self, capability_binding, provider_binding):
        a = self._need("authority")
        if capability_binding["authority_hash"] != a["object_hash"]:
            raise GuardError("capability binding not from this authority")
        if capability_binding["capability"] not in a["scope"]:
            raise GuardError("capability outside authority scope")
        self.ev.update(capability=capability_binding, provider=provider_binding)
        self._go("BOUND", provider_binding["contract_fingerprint"], _tok=_TOKEN)

    @atomic
    def prewrite_validate(self, tx, outcome_contract, readback_contract, checkpoint):
        self._corr(tx)
        self._corr(outcome_contract)
        if not outcome_contract["frozen"]:
            raise GuardError("outcome contract not frozen before mutation")
        check_predicates(outcome_contract["predicates"])
        if checkpoint["outcome_contract_hash"] != outcome_contract["object_hash"]:
            raise GuardError("checkpoint does not pin outcome contract")
        if checkpoint["readback_contract_hash"] != readback_contract["object_hash"]:
            raise GuardError("checkpoint does not pin readback contract")
        if checkpoint["budget_hash"] != self._need("budget")["object_hash"]:
            raise GuardError("checkpoint does not pin budget")
        if checkpoint["transaction_hash"] != tx["object_hash"]:
            raise GuardError("checkpoint does not pin transaction")
        if readback_contract["source_level_required"] != "AUTHORITATIVE_REPOSITORY":
            raise GuardError("readback contract is not authoritative")
        self.ev.update(tx=tx, outcome_contract=outcome_contract,
                       readback_contract=readback_contract, checkpoint=checkpoint)
        self._go("PREWRITE_VALIDATED", checkpoint["object_hash"], _tok=_TOKEN)

    @atomic
    def begin_execution(self, mutation_id, contract_fingerprint_now):
        """Budget + replay guard are consumed BEFORE the call leaves the client (and only if the step is legal)."""
        if contract_fingerprint_now != self._need("provider")["contract_fingerprint"]:
            raise GuardError("contract drift at point of use: revalidate (fail closed)")
        if mutation_id not in self._need("tx")["mutation_ids"]:
            raise GuardError("mutation not in transaction")
        key = (self.ev["authority"]["object_hash"], mutation_id)
        if key in self.consumed:
            raise GuardError("replay: mutation authority already consumed")
        if self.remaining <= 0:
            raise GuardError("mutation budget exhausted")
        if "EXECUTION_STARTED" not in TRANSITIONS[self.state]:
            raise GuardError("illegal transition %s -> EXECUTION_STARTED" % self.state)
        self.consumed.add(key)
        self.remaining -= 1
        self.mutations_sent += 1
        self.ev["mutation_id"] = mutation_id
        self._go("EXECUTION_STARTED", mutation_id, _tok=_TOKEN)

    @atomic
    def record_execution(self, receipt):
        """Execution receipt classifies the call; it never implies commit."""
        self._corr(receipt)
        if receipt.get("mutation_id") != self.ev.get("mutation_id"):
            raise GuardError("execution receipt not correlated to mutation")
        c = receipt["call_class"]
        if c not in POST_SEND_CLASSES:
            raise GuardError("call_class %s not valid after execution started" % c)
        self.ev["execution_receipt"] = receipt
        if c == "PROVIDER_RESPONSE_SUCCESS":
            self._go("EXECUTED", receipt["object_hash"], _tok=_TOKEN)
        else:
            self._go("COMMIT_STATE_UNKNOWN", receipt["object_hash"], _tok=_TOKEN)

    @atomic
    def request_readback(self):
        self._go("AUTHORITATIVE_READBACK_PENDING", _tok=_TOKEN)

    @atomic
    def observe_readback(self, rb):
        """rb: AuthoritativeReadbackReceipt. Non-authoritative sources and errors are UNKNOWN."""
        self._corr(rb)
        contract = self._need("readback_contract")
        if rb["contract_hash"] != contract["object_hash"]:
            raise GuardError("readback not produced under frozen contract")
        if rb["mutation_id"] != self.ev["mutation_id"]:
            raise GuardError("readback not correlated to mutation")
        self.ev["readback"] = rb
        self._go("AUTHORITATIVE_READBACK_OBSERVED", rb["object_hash"], _tok=_TOKEN)

    def _readback_authoritative(self, rb):
        return rb["source_level"] == "AUTHORITATIVE_REPOSITORY"

    @atomic
    def decide_commit(self, observation):
        rb = self._need("readback")
        if observation["readback_receipt_hash"] != rb["object_hash"]:
            raise GuardError("commit observation not bound to readback")
        self._corr(observation)
        if not self._readback_authoritative(rb) or rb["existence"] == "UNKNOWN":
            self._go("COMMIT_STATE_UNKNOWN", observation["object_hash"], _tok=_TOKEN)
            return self.state
        if rb["existence"] == "ABSENT":
            # Not committed. Remains fail-closed: no retry without a new authorization lineage.
            self._go("FAILED_AFTER_POSSIBLE_MUTATION", observation["object_hash"], _tok=_TOKEN)
            return self.state
        if observation["commit_state"] != "COMMITTED":
            raise GuardError("commit observation contradicts authoritative EXISTS readback")
        self.ev["commit"] = observation
        self._go("COMMITTED", observation["object_hash"], _tok=_TOKEN)
        return self.state

    @atomic
    def validate_outcome(self, outcome):
        self._need("commit")
        oc, rb = self._need("outcome_contract"), self._need("readback")
        if outcome["outcome_contract_hash"] != oc["object_hash"] or outcome["readback_receipt_hash"] != rb["object_hash"]:
            raise GuardError("outcome receipt not bound to contract+readback")
        self._corr(outcome)
        recomputed = eval_predicates(oc["predicates"], rb["observed"])
        if outcome["result"] != recomputed:
            raise GuardError("outcome receipt result disagrees with recomputation")
        self._go("OUTCOME_VALIDATION_PENDING", _tok=_TOKEN)
        self.ev["outcome"] = outcome
        if recomputed == "PASS":
            self._go("OUTCOME_VALIDATED", outcome["object_hash"], _tok=_TOKEN)
        elif recomputed == "FAIL":
            self._go("COMPENSATION_REQUIRED", outcome["object_hash"], _tok=_TOKEN)
        # UNKNOWN predicate: stay in OUTCOME_VALIDATION_PENDING (COMPLETE=FALSE); never PASS/FAIL.
        return self.state

    def _verify_chain(self, completion):
        """Relational validation of the whole evidence chain (hash validity alone is not authentication)."""
        required = [s for s, _ in CHAIN_SLOTS[:-1]] + ["outcome_contract", "readback_contract"]
        missing = [s for s in required if s not in self.ev]
        if missing:
            raise GuardError("incomplete evidence chain: missing %s" % missing)
        e = self.ev
        for slot in required:
            o = e[slot]
            if not isinstance(o, dict) or o.get("kind") != SLOT_KINDS[slot]:
                raise GuardError("evidence %s has wrong kind" % slot)
            if not verify_hash(o):
                raise GuardError("evidence %s hash invalid (tampered)" % slot)
        h = lambda s: e[s]["object_hash"]
        mid = e.get("mutation_id")
        chk = [
            (e["delegation"]["principal_hash"] == h("principal"), "delegation not issued to this principal"),
            (e["authority"]["delegation_hash"] == h("delegation"), "authority not derived from delegation"),
            (e["authority"]["mission_id"] == self.mission_id and e["intent"]["mission_id"] == self.mission_id, "mission id mismatch"),
            (attenuated(e["authority"]["scope"], e["delegation"]["scope"]), "authority exceeds delegation"),
            (e["budget"]["authority_hash"] == h("authority") and e["budget"]["retries"] == 0 and not e["budget"]["expansion_allowed"], "budget not bounded by authority"),
            (e["capability"]["authority_hash"] == h("authority") and e["capability"]["capability"] in e["authority"]["scope"], "capability binding outside authority"),
            (e["tx"]["transaction_id"] == self.transaction_id and e["tx"]["mission_id"] == self.mission_id, "transaction identity mismatch"),
            (mid is not None and mid in e["tx"]["mutation_ids"], "mutation not in transaction"),
            ((h("authority"), mid) in self.consumed, "mutation authority was never consumed"),
            (e["outcome_contract"]["frozen"] and e["outcome_contract"]["transaction_id"] == self.transaction_id, "outcome contract not frozen/correlated"),
            (e["readback_contract"]["source_level_required"] == "AUTHORITATIVE_REPOSITORY", "readback contract not authoritative"),
            (e["checkpoint"]["transaction_hash"] == h("tx") and e["checkpoint"]["budget_hash"] == h("budget")
             and e["checkpoint"]["outcome_contract_hash"] == h("outcome_contract") and e["checkpoint"]["readback_contract_hash"] == h("readback_contract"), "checkpoint pins do not match chain"),
            (e["execution_receipt"]["transaction_id"] == self.transaction_id and e["execution_receipt"]["mutation_id"] == mid
             and e["execution_receipt"]["call_class"] in POST_SEND_CLASSES, "execution receipt invalid"),
            (e["readback"]["transaction_id"] == self.transaction_id and e["readback"]["mutation_id"] == mid
             and e["readback"]["contract_hash"] == h("readback_contract"), "readback not correlated/under contract"),
            (e["readback"]["source_level"] == "AUTHORITATIVE_REPOSITORY" and e["readback"]["existence"] == "EXISTS", "readback is not an authoritative EXISTS"),
            (e["commit"]["transaction_id"] == self.transaction_id and e["commit"]["mutation_id"] == mid
             and e["commit"]["readback_receipt_hash"] == h("readback") and e["commit"]["commit_state"] == "COMMITTED", "commit observation not bound to readback"),
            (e["outcome"]["transaction_id"] == self.transaction_id and e["outcome"]["readback_receipt_hash"] == h("readback")
             and e["outcome"]["outcome_contract_hash"] == h("outcome_contract") and e["outcome"]["result"] == "PASS", "outcome receipt not bound/PASS"),
            (eval_predicates(e["outcome_contract"]["predicates"], e["readback"]["observed"]) == "PASS", "predicates do not pass on the readback"),
        ]
        for ok, msg in chk:
            if not ok:
                raise GuardError("evidence chain inconsistent: " + msg)
        need = {"authority": "authority_hash", "execution_receipt": "execution_receipt_hash",
                "commit": "commit_observation_hash", "outcome": "outcome_receipt_hash"}
        for slot, field in need.items():
            if completion.get(field) != h(slot):
                raise GuardError("completion chain broken at %s" % slot)

    @atomic
    def complete(self, completion):
        """COMPLETE needs the whole chain present, hash-valid AND relationally consistent, a hash-valid
        CompletionReceipt linking it, and state OUTCOME_VALIDATED. Persisted only after every guard passes."""
        if not isinstance(completion, dict) or completion.get("kind") != "CompletionReceipt":
            raise GuardError("completion receipt absent or wrong kind")
        if not verify_hash(completion):
            raise GuardError("completion receipt hash invalid (tampered)")
        if self.state != "OUTCOME_VALIDATED":
            raise GuardError("COMPLETE requires OUTCOME_VALIDATED")
        try:
            self._verify_chain(completion)
        except (KeyError, TypeError, AttributeError, IndexError) as exc:
            raise GuardError("evidence chain malformed: %s" % type(exc).__name__)
        self._corr(completion)
        self._go("COMPLETE", completion["object_hash"], _tok=_TOKEN)
        self.ev["completion"] = completion

    # -- failure / compensation
    @atomic
    def fail_before_mutation(self):
        if self.mutations_sent:
            raise GuardError("mutation possibly sent; use FAILED_AFTER_POSSIBLE_MUTATION")
        self._go("FAILED_BEFORE_MUTATION", _tok=_TOKEN)

    @atomic
    def fail_after_possible_mutation(self):
        self._go("FAILED_AFTER_POSSIBLE_MUTATION", _tok=_TOKEN)

    @atomic
    def require_compensation(self):
        self._go("COMPENSATION_REQUIRED", _tok=_TOKEN)

    @atomic
    def authorize_compensation(self, grant):
        a = self._need("authority")
        if grant["inherits_forward_authority"]:
            raise GuardError("compensation may not inherit forward authority")
        if grant["issued_by"] == a["object_hash"]:
            raise GuardError("compensation grant must not be issued from forward authority")
        if grant["max_mutations"] < 1 or not grant["preconditions"] or not grant["outcome_predicates"]:
            raise GuardError("compensation grant incomplete")
        check_predicates(grant["outcome_predicates"])
        if grant["target"] not in (self.ev["intent"]["target_system"], self._need("tx")["transaction_id"]):
            raise GuardError("compensation target not tied to mission")
        self.ev["comp_grant"] = grant
        self._go("COMPENSATION_AUTHORIZED", grant["object_hash"], _tok=_TOKEN)

    @atomic
    def record_compensation(self, comp_receipt, post_readback):
        g = self._need("comp_grant")
        if comp_receipt["grant_hash"] != g["object_hash"]:
            raise GuardError("compensation receipt not bound to its grant")
        if post_readback["source_level"] != "AUTHORITATIVE_REPOSITORY":
            raise GuardError("post-compensation readback must be authoritative")
        if comp_receipt["readback_receipt_hash"] != post_readback["object_hash"]:
            raise GuardError("compensation receipt not bound to post readback")
        if eval_predicates(g["outcome_predicates"], post_readback["observed"]) != "PASS" or comp_receipt["result"] != "PASS":
            raise GuardError("compensation outcome predicate not satisfied")
        self._go("COMPENSATED", comp_receipt["object_hash"], _tok=_TOKEN)

    @atomic
    def declare_unrecoverable(self):
        self._go("UNRECOVERABLE", _tok=_TOKEN)

    # -- continuation
    def checkpoint_lease(self):
        cp = self._need("checkpoint")
        er = self.ev.get("execution_receipt")
        return make("ContinuationLease", lease_id="LEASE-" + chash([cp["object_hash"], sorted(map(str, self.consumed)), self.state])[:12],
                    checkpoint_hash=cp["object_hash"], transaction_id=self.transaction_id,
                    remaining_budget=self.remaining, state_at_checkpoint=self.state,
                    mutation_id=self.ev.get("mutation_id"),
                    execution_receipt_hash=er["object_hash"] if er else None,
                    consumed_authority_ids=sorted(("%s:%s" % k) for k in self.consumed))

    @classmethod
    def resume(cls, lease, checkpoint, original_budget, mission_id, evidence=None):
        """Rebuild a mission from a lease. The lease and checkpoint must be hash-valid and mutually consistent;
        re-presented evidence is limited to RESUME_SLOTS and must match the checkpoint's pins. A resumed mission
        never regains consumed authority and never inherits a post-send state: after any possible send it
        restarts in COMMIT_STATE_UNKNOWN and must obtain a fresh readback. Lease integrity (hash) is checked;
        lease authenticity (a signature) is NOT provided by this library."""
        for o, kind in ((lease, "ContinuationLease"), (checkpoint, "PreMutationCheckpoint")):
            if not isinstance(o, dict) or o.get("kind") != kind or not verify_hash(o):
                raise GuardError("%s absent, wrong kind or hash invalid" % kind)
        if lease["checkpoint_hash"] != checkpoint["object_hash"]:
            raise GuardError("lease not bound to checkpoint")
        consumed = {tuple(s.split(":", 1)) for s in lease["consumed_authority_ids"]}
        if lease["remaining_budget"] + len(consumed) > checkpoint["remaining_budget"]:
            raise GuardError("continuation may not enlarge budget")
        if lease["remaining_budget"] + len(consumed) > original_budget["max_mutations"]:
            raise GuardError("continuation exceeds original budget")
        st = lease["state_at_checkpoint"]
        if consumed and st in ("PREWRITE_VALIDATED", "PLANNED") or (not consumed and st not in ("PREWRITE_VALIDATED",)):
            raise GuardError("lease state inconsistent with consumed set")
        m = cls(mission_id, lease["transaction_id"], lease["remaining_budget"])
        m.consumed = consumed
        if evidence is None:
            return m
        extra = sorted(set(evidence) - set(RESUME_SLOTS))
        if extra:
            raise GuardError("resume accepts no downstream evidence: %s" % extra)
        for slot in ("tx", "budget", "outcome_contract", "readback_contract", "authority"):
            if slot not in evidence:
                raise GuardError("resume evidence missing %s" % slot)
        for slot, o in evidence.items():
            if not isinstance(o, dict) or o.get("kind") != SLOT_KINDS[slot] or not verify_hash(o):
                raise GuardError("re-presented %s wrong kind or hash invalid" % slot)
        pins = {"tx": "transaction_hash", "budget": "budget_hash",
                "outcome_contract": "outcome_contract_hash", "readback_contract": "readback_contract_hash"}
        for slot, field in pins.items():
            if evidence[slot]["object_hash"] != checkpoint[field]:
                raise GuardError("re-presented %s does not match checkpoint pin" % slot)
        if evidence["tx"]["transaction_id"] != lease["transaction_id"]:
            raise GuardError("re-presented transaction does not match lease")
        if evidence["budget"]["authority_hash"] != evidence["authority"]["object_hash"]:
            raise GuardError("re-presented authority does not match budget")
        if "delegation" in evidence and evidence["authority"]["delegation_hash"] != evidence["delegation"]["object_hash"]:
            raise GuardError("re-presented delegation does not match authority")
        if "capability" in evidence and evidence["capability"]["authority_hash"] != evidence["authority"]["object_hash"]:
            raise GuardError("re-presented capability binding does not match authority")
        if any(k[0] != evidence["authority"]["object_hash"] for k in consumed):
            raise GuardError("consumed set does not belong to the re-presented authority")
        m.ev.update(evidence)
        m.ev["checkpoint"] = checkpoint
        m.mutations_sent = len(consumed)
        if not consumed:
            m.state = "PREWRITE_VALIDATED"
            return m
        # a send may have happened: never silently restart or trust carried post-send state; reconcile
        mut = lease["mutation_id"]
        if mut is None or mut not in evidence["tx"]["mutation_ids"] or (evidence["authority"]["object_hash"], mut) not in consumed:
            raise GuardError("lease mutation id inconsistent")
        m.ev["mutation_id"] = mut
        er = evidence.get("execution_receipt")
        if er is not None:
            if er["object_hash"] != lease["execution_receipt_hash"] or er.get("mutation_id") != mut or er.get("transaction_id") != lease["transaction_id"]:
                raise GuardError("execution receipt does not match lease")
        else:
            er = make("ExecutionReceipt", receipt_id="resume-" + lease["lease_id"], transaction_id=lease["transaction_id"],
                      mutation_id=mut, call_class="COMMIT_UNKNOWN")
        m.ev["execution_receipt"] = er
        m.state = "COMMIT_STATE_UNKNOWN"
        m.history.append(("RESUMED_AS_COMMIT_STATE_UNKNOWN", lease["object_hash"]))
        return m


# Architecture contract (spec section 19): 14 links, fixed order. Slot name -> chain label.
CHAIN_SLOTS = [("intent", "MISSION_INTENT"), ("principal", "PRINCIPAL_CONTEXT"), ("delegation", "DELEGATION"),
               ("authority", "AUTHORITY"), ("capability", "CAPABILITY_BINDING"), ("provider", "PROVIDER_CONTRACT"),
               ("budget", "MUTATION_BUDGET"), ("tx", "TRANSACTION"), ("checkpoint", "PREWRITE_CHECKPOINT"),
               ("execution_receipt", "EXECUTION_RECEIPT"), ("commit", "COMMIT_OBSERVATION"),
               ("readback", "AUTHORITATIVE_READBACK_RECEIPT"), ("outcome", "OUTCOME_RECEIPT"),
               ("completion", "COMPLETION_RECEIPT")]
EXPECTED_CHAIN = [label for _, label in CHAIN_SLOTS]


def chain_hashes(m):
    """Emit the links that exist, in contract order. A COMPLETE mission emits all 14, the last being the
    CompletionReceipt; a non-complete mission never emits a completion link."""
    return [(label, m.ev[slot]["object_hash"]) for slot, label in CHAIN_SLOTS if slot in m.ev]
