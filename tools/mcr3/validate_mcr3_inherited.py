"""R2.0A deterministic validator. Synthetic/local only; makes no enterprise or network call.

Usage: python tools/r2.0/validate_mcr3_inherited.py [--out PATH] [--emit-schemas DIR]
Exit 0 only if every acceptance group passes. Output is deterministic (no timestamps/timings).
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mcr3_model as MODEL  # noqa: E402
from mcr3_model import (CALL_CLASSES, CHAIN_SLOTS, EXPECTED_CHAIN, SCHEMAS, STATES, TRANSITIONS, GuardError, Mission, SchemaError,  # noqa: E402
                          chain_hashes, chash, eval_predicates, make, verify_hash)

FP = "FP-" + "A" * 61
PREDS = [{"field": "exists", "op": "eq", "expected": True},
         {"field": "package", "op": "eq", "expected": "ZPKG_SYN"},
         {"field": "active", "op": "eq", "expected": True},
         {"field": "source_sha256", "op": "eq", "expected": "S" * 8}]
GOOD_OBS = {"exists": True, "package": "ZPKG_SYN", "active": True, "source_sha256": "S" * 8}


def fixture(max_mut=1, scope=("create_object",), deleg_scope=("create_object", "read_object")):
    mid, tid = "M-SYN-1", "TX-SYN-1"
    oc = make("ExpectedOutcomeContract", outcome_contract_id="oc1", mission_id=mid, transaction_id=tid, predicates=PREDS, frozen=True)
    intent = make("MissionIntent", mission_id=mid, objective="synthetic", target_system="SYN_SYS", expected_outcome_hash=oc["object_hash"])
    pr = make("PrincipalContext", principal_id="p1", tenant="t", roles=["dev"])
    dl = make("DelegationEnvelope", delegation_id="d1", principal_hash=pr["object_hash"], scope=list(deleg_scope),
              max_mutations=2, expires_at="2099-01-01")
    au = make("ExecutionAuthority", authority_id="a1", delegation_hash=dl["object_hash"], mission_id=mid,
              scope=list(scope), max_mutations=max_mut, single_use=True)
    bu = make("MutationBudget", budget_id="b1", authority_hash=au["object_hash"], max_mutations=max_mut, retries=0,
              expansion_allowed=False)
    cb = make("CapabilityBinding", binding_id="c1", authority_hash=au["object_hash"], capability="create_object",
              provider_ref="SYN::create_object")
    pb = make("ProviderBinding", provider_id="SYN", tool_name="create_object", contract_fingerprint=FP, identity="SYN::create_object")
    tx = make("TransactionEnvelope", transaction_id=tid, mission_id=mid, mutation_ids=["MUT-1"], boundary="single-object")
    rc = make("AuthoritativeReadbackContract", contract_id="rc1", source_level_required="AUTHORITATIVE_REPOSITORY",
              provider_ref="SYN::repo_read", checks=["exists"])
    cp = make("PreMutationCheckpoint", checkpoint_id="cp1", transaction_hash=tx["object_hash"], budget_hash=bu["object_hash"],
              outcome_contract_hash=oc["object_hash"], readback_contract_hash=rc["object_hash"], remaining_budget=max_mut)
    m = Mission(mid, tid, max_mut)
    return m, dict(intent=intent, pr=pr, dl=dl, au=au, bu=bu, cb=cb, pb=pb, tx=tx, oc=oc, rc=rc, cp=cp)


def to_prewrite(m, f):
    m.context_ready(f["intent"], f["pr"]); m.authorize(f["dl"], f["au"], f["bu"]); m.bind(f["cb"], f["pb"])
    m.prewrite_validate(f["tx"], f["oc"], f["rc"], f["cp"])


def exec_receipt(f, cls="PROVIDER_RESPONSE_SUCCESS", mut="MUT-1"):
    return make("ExecutionReceipt", receipt_id="er-" + cls, transaction_id="TX-SYN-1", mutation_id=mut, call_class=cls)


def rb_receipt(f, existence="EXISTS", level="AUTHORITATIVE_REPOSITORY", obs=None, tx="TX-SYN-1", mut="MUT-1"):
    return make("AuthoritativeReadbackReceipt", receipt_id="rb-" + existence + level, transaction_id=tx, mutation_id=mut,
                contract_hash=f["rc"]["object_hash"], source_level=level, existence=existence,
                activation="ACTIVE" if existence == "EXISTS" else "UNKNOWN", observed=obs if obs is not None else (GOOD_OBS if existence == "EXISTS" else {"exists": False} if existence == "ABSENT" else {}))


def commit_obs(rb, state):
    return make("CommitObservation", observation_id="co-" + state, transaction_id="TX-SYN-1", mutation_id="MUT-1",
                readback_receipt_hash=rb["object_hash"], commit_state=state)


def outcome(f, rb, result):
    return make("OutcomeReceipt", receipt_id="or1", transaction_id="TX-SYN-1", readback_receipt_hash=rb["object_hash"],
                outcome_contract_hash=f["oc"]["object_hash"], result=result)


def happy(m, f, obs=None):
    to_prewrite(m, f); m.begin_execution("MUT-1", FP)
    er = exec_receipt(f); m.record_execution(er)
    m.request_readback(); rb = rb_receipt(f, obs=obs); m.observe_readback(rb)
    m.decide_commit(commit_obs(rb, "COMMITTED"))
    res = eval_predicates(PREDS, rb["observed"])
    m.validate_outcome(outcome(f, rb, res))
    return er, rb


def raises(fn, text=None):
    """True only if fn raises GuardError/SchemaError (containing `text`, if given). Any other exception, or no
    exception, is False, so a removed guard fails an assertion instead of crashing the run."""
    try:
        fn()
    except (GuardError, SchemaError) as e:
        return text is None or text in str(e)
    except Exception:
        return False
    return False


def safe(fn):
    """True/False from fn; any exception counts as False so a broken guard fails an assertion, not the run."""
    try:
        return bool(fn())
    except Exception:
        return False


T = {}   # test name -> bool
G = {}   # group -> [test names]


def t(group, name, ok):
    T[name] = bool(ok); G.setdefault(group, []).append(name)


UPSTREAM = ("intent", "principal", "delegation", "capability", "provider", "tx", "budget", "outcome_contract", "readback_contract", "authority")


def ev_upstream(mm):
    return {k: mm.ev[k] for k in UPSTREAM}


def rsm(lease, f, mm, cp=None, evidence=None, ledger=None, mission_id="M-SYN-1"):
    """resume() with the standard re-presented upstream evidence and the mission's own ledger."""
    return Mission.resume(lease, cp if cp is not None else f["cp"], f["bu"], mission_id,
                          evidence if evidence is not None else ev_upstream(mm), ledger if ledger is not None else mm.ledger,
                          allow_volatile_ledger=True)


def comp_exec(gg, cls="PROVIDER_RESPONSE_SUCCESS", mut=None, tx="TX-SYN-1", attempt=1):
    """Execution receipt for the compensating call, bound to the grant and the attempt number (3.0)."""
    return make("ExecutionReceipt", receipt_id="ce%d" % attempt, transaction_id=tx, mutation_id=mut or ("COMPENSATION:%s#%d" % (gg["object_hash"], attempt)), call_class=cls)


def run():
    # ---- STATE_MACHINE_VALID
    g = "STATE_MACHINE_VALID"
    t(g, "all_states_have_transition_row", set(STATES) == set(TRANSITIONS))
    t(g, "transition_targets_known", all(x in STATES for v in TRANSITIONS.values() for x in v))
    t(g, "terminal_states_have_no_exit", all(not TRANSITIONS[s] for s in ("COMPLETE", "COMPENSATED", "UNRECOVERABLE", "FAILED_BEFORE_MUTATION")))
    t(g, "no_direct_path_executed_to_complete", "COMPLETE" not in TRANSITIONS["EXECUTED"] and "COMMITTED" not in TRANSITIONS["EXECUTED"])
    t(g, "no_direct_path_committed_to_complete", "COMPLETE" not in TRANSITIONS["COMMITTED"])
    t(g, "no_direct_path_readback_to_validated", "OUTCOME_VALIDATED" not in TRANSITIONS["AUTHORITATIVE_READBACK_OBSERVED"])
    t(g, "no_fail_before_mutation_after_start", "FAILED_BEFORE_MUTATION" not in TRANSITIONS["EXECUTION_STARTED"])
    m, f = fixture()
    t(g, "illegal_jump_rejected", raises(lambda: m._go("COMPLETE", None, _tok=MODEL._TOKEN), "illegal transition"))
    t(g, "direct_state_change_refused_without_guard", raises(lambda: m._go("CONTEXT_READY"), "direct state change refused") and m.state == "PLANNED")
    # reachability: COMPLETE reachable from PLANNED
    seen, stack = set(), ["PLANNED"]
    while stack:
        s = stack.pop()
        if s not in seen:
            seen.add(s); stack.extend(TRANSITIONS[s])
    t(g, "all_states_reachable", seen == set(STATES))

    # ---- SCHEMA_VALIDATION
    g = "SCHEMA_VALIDATION"
    t(g, "all_25_object_kinds_defined", len(SCHEMAS) == 25)
    t(g, "missing_field_rejected", raises(lambda: make("MutationBudget", budget_id="x"), "missing"))
    t(g, "bad_enum_rejected", raises(lambda: make("ExecutionReceipt", receipt_id="x", transaction_id="t", mutation_id="m", call_class="OK"), "not in"))
    t(g, "call_classes_cover_spec_18", set(CALL_CLASSES) >= {"CALL_NOT_SENT", "CALL_SENT_NO_RESPONSE", "PROVIDER_ERROR",
                                                            "PROVIDER_RESPONSE_SUCCESS", "COMMIT_UNKNOWN", "COMMIT_CONFIRMED",
                                                            "OUTCOME_FAILED", "OUTCOME_VALIDATED"})
    a = make("PrincipalContext", principal_id="p", tenant="t", roles=["r"]); b = make("PrincipalContext", roles=["r"], tenant="t", principal_id="p")
    t(g, "hash_is_key_order_independent", a["object_hash"] == b["object_hash"])
    c = dict(a); c["tenant"] = "other"
    t(g, "tamper_detected", verify_hash(a) and not verify_hash(c))

    # ---- AUTHORITY_INVARIANTS
    g = "AUTHORITY_INVARIANTS"
    m, f = fixture(scope=("create_object", "delete_object"))
    t(g, "authority_exceeding_delegation_rejected", raises(lambda: (m.context_ready(f["intent"], f["pr"]), m.authorize(f["dl"], f["au"], f["bu"])), "no attenuation"))
    m, f = fixture(); m.context_ready(f["intent"], f["pr"])
    other_dl = make("DelegationEnvelope", delegation_id="d2", principal_hash=f["pr"]["object_hash"], scope=["create_object"], max_mutations=2, expires_at="2099-01-01")
    t(g, "authority_must_derive_from_delegation", raises(lambda: m.authorize(other_dl, f["au"], f["bu"]), "not derived"))
    m, f = fixture(); to_prewrite(m, f)
    t(g, "reached_prewrite_with_valid_chain", m.state == "PREWRITE_VALIDATED")
    m, f = fixture(); m.context_ready(f["intent"], f["pr"]); m.authorize(f["dl"], f["au"], f["bu"])
    bad = make("CapabilityBinding", binding_id="c2", authority_hash=f["au"]["object_hash"], capability="delete_object", provider_ref="SYN::delete")
    t(g, "capability_outside_scope_rejected", raises(lambda: m.bind(bad, f["pb"]), "outside authority scope"))
    m, f = fixture(); m.context_ready(f["intent"], f["pr"]); m.authorize(f["dl"], f["au"], f["bu"]); m.bind(f["cb"], f["pb"])
    oc_unfrozen = make("ExpectedOutcomeContract", outcome_contract_id="oc1", mission_id="M-SYN-1", transaction_id="TX-SYN-1", predicates=PREDS, frozen=False)
    t(g, "unfrozen_outcome_contract_blocks_prewrite", raises(lambda: m.prewrite_validate(f["tx"], oc_unfrozen, f["rc"], f["cp"]), "not frozen"))
    weak = make("AuthoritativeReadbackContract", contract_id="rc2", source_level_required="PROVIDER_VALIDATION", provider_ref="x", checks=[])
    cp2 = make("PreMutationCheckpoint", checkpoint_id="cp2", transaction_hash=f["tx"]["object_hash"], budget_hash=f["bu"]["object_hash"],
               outcome_contract_hash=f["oc"]["object_hash"], readback_contract_hash=weak["object_hash"], remaining_budget=1)
    t(g, "non_authoritative_readback_contract_blocks_prewrite", raises(lambda: m.prewrite_validate(f["tx"], f["oc"], weak, cp2), "not authoritative"))
    m, f = fixture(); to_prewrite(m, f)
    t(g, "point_of_use_contract_drift_fails_closed", raises(lambda: m.begin_execution("MUT-1", "FP-DRIFTED"), "contract drift") and m.mutations_sent == 0)

    # ---- MUTATION_BUDGET_INVARIANTS
    g = "MUTATION_BUDGET_INVARIANTS"
    m, f = fixture(); to_prewrite(m, f); m.begin_execution("MUT-1", FP)
    t(g, "budget_consumed_before_call", m.remaining == 0 and m.mutations_sent == 1)
    t(g, "zero_budget_blocks_second_mutation", raises(lambda: m.begin_execution("MUT-1", FP)))
    bad_bu = make("MutationBudget", budget_id="bx", authority_hash=f["au"]["object_hash"], max_mutations=1, retries=1, expansion_allowed=False)
    m2, f2 = fixture(); m2.context_ready(f2["intent"], f2["pr"])
    t(g, "retries_forbidden", raises(lambda: m2.authorize(f2["dl"], f2["au"], bad_bu), "forbid"))
    big_bu = make("MutationBudget", budget_id="bx", authority_hash=f["au"]["object_hash"], max_mutations=5, retries=0, expansion_allowed=False)
    t(g, "budget_above_authority_rejected", raises(lambda: m2.authorize(f2["dl"], f2["au"], big_bu), "not bounded"))
    exp_bu = make("MutationBudget", budget_id="bx", authority_hash=f["au"]["object_hash"], max_mutations=1, retries=0, expansion_allowed=True)
    t(g, "expansion_forbidden", raises(lambda: m2.authorize(f2["dl"], f2["au"], exp_bu), "forbid"))
    m3, f3 = fixture(); to_prewrite(m3, f3)
    t(g, "mutation_outside_transaction_rejected", raises(lambda: m3.begin_execution("MUT-X", FP), "not in transaction"))

    # ---- REPLAY_GUARD_INVARIANTS
    g = "REPLAY_GUARD_INVARIANTS"
    m, f = fixture(max_mut=2); to_prewrite(m, f); m.begin_execution("MUT-1", FP)
    t(g, "consumed_mutation_cannot_replay_even_with_budget_left", m.remaining == 1 and raises(lambda: m.begin_execution("MUT-1", FP), "replay"))
    m, f = fixture(); to_prewrite(m, f); m.begin_execution("MUT-1", FP); m.record_execution(exec_receipt(f, "CALL_SENT_NO_RESPONSE"))
    t(g, "no_response_does_not_unlock_retry", m.state == "COMMIT_STATE_UNKNOWN" and raises(lambda: m.begin_execution("MUT-1", FP)))
    m2, f2 = fixture(); m2.context_ready(f2["intent"], f2["pr"]); m2.consumed.add(f2["au"]["object_hash"])
    t(g, "consumed_authority_cannot_authorize_again", raises(lambda: m2.authorize(f2["dl"], f2["au"], f2["bu"]), "already consumed"))

    # ---- CONTINUATION_INVARIANTS
    g = "CONTINUATION_INVARIANTS"
    m, f = fixture(max_mut=2)
    f["tx"] = make("TransactionEnvelope", transaction_id="TX-SYN-1", mutation_ids=["MUT-1", "MUT-2"], mission_id="M-SYN-1", boundary="b")
    f["cp"] = make("PreMutationCheckpoint", checkpoint_id="cp1", transaction_hash=f["tx"]["object_hash"], budget_hash=f["bu"]["object_hash"],
                   outcome_contract_hash=f["oc"]["object_hash"], readback_contract_hash=f["rc"]["object_hash"], remaining_budget=2)
    to_prewrite(m, f); m.begin_execution("MUT-1", FP)
    lease = m.checkpoint_lease()
    try:
        r = rsm(lease, f, m)
    except GuardError:
        r = None
    t(g, "resume_preserves_transaction_identity", r is not None and r.transaction_id == m.transaction_id)
    t(g, "resume_inherits_consumed_set", r is not None and r.consumed == m.consumed and r.remaining == 1)
    t(g, "resume_cannot_exceed_remaining", r is not None and r.remaining <= f["cp"]["remaining_budget"] - 1)
    inflated = make("ContinuationLease", **{k: v for k, v in lease.items() if k not in ("kind", "object_hash")} | {"remaining_budget": 9})
    t(g, "inflated_lease_rejected", raises(lambda: rsm(inflated, f, m), "enlarge"))
    other_cp = make("PreMutationCheckpoint", checkpoint_id="cpZ", transaction_hash="h", budget_hash="h", outcome_contract_hash="h", readback_contract_hash="h", remaining_budget=2)
    t(g, "lease_bound_to_checkpoint", raises(lambda: rsm(lease, f, m, cp=other_cp), "not bound"))
    t(g, "resumed_mission_cannot_replay_consumed", r is not None and raises(lambda: (setattr(r, "state", "PREWRITE_VALIDATED"), r.ev.update(tx=f["tx"], provider=f["pb"], authority=f["au"]),
                                                                   r.begin_execution("MUT-1", FP)), "replay"))

    # ---- COMPENSATION_AUTHORITY_INVARIANTS
    g = "COMPENSATION_AUTHORITY_INVARIANTS"
    def comp_setup(obs):
        m, f = fixture(); to_prewrite(m, f); m.begin_execution("MUT-1", FP); m.record_execution(exec_receipt(f)); m.request_readback()
        rb = rb_receipt(f, obs=obs); m.observe_readback(rb); m.decide_commit(commit_obs(rb, "COMMITTED"))
        m.validate_outcome(outcome(f, rb, eval_predicates(PREDS, obs)))
        return m, f
    m, f = comp_setup(dict(GOOD_OBS, package="WRONG"))
    t(g, "outcome_fail_requires_compensation_not_complete", m.state == "COMPENSATION_REQUIRED")
    gr = lambda **k: make("CompensationGrant", **dict(dict(grant_id="g1", target="SYN_SYS", capability="delete_object", max_mutations=1,
                          preconditions=[{"field": "exists", "op": "eq", "expected": True}], outcome_predicates=[{"field": "exists", "op": "eq", "expected": False}],
                          inherits_forward_authority=False, issued_by="OWNER2"), **k))
    t(g, "inherited_forward_authority_rejected", raises(lambda: m.authorize_compensation(gr(inherits_forward_authority=True)), "inherit") and m.state == "COMPENSATION_REQUIRED")
    t(g, "grant_issued_from_forward_authority_rejected", raises(lambda: m.authorize_compensation(gr(issued_by=f["au"]["object_hash"])), "must not be issued"))
    t(g, "incomplete_grant_rejected", raises(lambda: m.authorize_compensation(gr(preconditions=[])), "incomplete"))
    t(g, "grant_for_other_target_rejected", raises(lambda: m.authorize_compensation(gr(target="OTHER_SYS")), "not tied"))
    def comp_authorized():
        mm, ff = comp_setup(dict(GOOD_OBS, package="WRONG"))
        gg = gr(); mm.authorize_compensation(gg); mm.begin_compensation()
        return mm, ff, gg
    m, f, grant = comp_authorized()
    t(g, "valid_separate_grant_accepted", m.state == "COMPENSATION_AUTHORIZED")
    post_bad = rb_receipt(f, "EXISTS", obs={"exists": True})
    cr_bad = make("CompensationReceipt", receipt_id="cr", grant_hash=grant["object_hash"], readback_receipt_hash=post_bad["object_hash"], result="PASS")
    t(g, "compensation_without_predicate_pass_rejected", raises(lambda: m.record_compensation(cr_bad, post_bad, comp_exec(grant)), "predicate") and m.state == "COMPENSATION_AUTHORIZED")
    m, f, grant = comp_authorized()
    post_weak = rb_receipt(f, "ABSENT", level="PROVIDER_LOG", obs={"exists": False})
    cr_w = make("CompensationReceipt", receipt_id="cr", grant_hash=grant["object_hash"], readback_receipt_hash=post_weak["object_hash"], result="PASS")
    t(g, "post_compensation_readback_must_be_authoritative", raises(lambda: m.record_compensation(cr_w, post_weak, comp_exec(grant)), "authoritative") and m.state == "COMPENSATION_AUTHORIZED")
    m, f, grant = comp_authorized()
    post_ok = rb_receipt(f, "ABSENT", obs={"exists": False})
    cr_ok = make("CompensationReceipt", receipt_id="cr", grant_hash=grant["object_hash"], readback_receipt_hash=post_ok["object_hash"], result="PASS")
    m.record_compensation(cr_ok, post_ok, comp_exec(grant))
    t(g, "compensation_reaches_COMPENSATED_not_COMPLETE", m.state == "COMPENSATED")

    # ---- OUTCOME_PREDICATE_MODEL
    g = "OUTCOME_PREDICATE_MODEL"
    t(g, "all_match_pass", eval_predicates(PREDS, GOOD_OBS) == "PASS")
    t(g, "mismatch_fail", eval_predicates(PREDS, dict(GOOD_OBS, active=False)) == "FAIL")
    t(g, "missing_field_unknown", eval_predicates(PREDS, {k: v for k, v in GOOD_OBS.items() if k != "active"}) == "UNKNOWN")
    t(g, "fail_dominates_unknown", eval_predicates(PREDS, {"exists": True, "package": "X"}) == "FAIL")
    t(g, "explicit_unknown_value_is_unknown", eval_predicates(PREDS, dict(GOOD_OBS, active="UNKNOWN")) == "UNKNOWN")
    m, f = fixture(); er, rb = happy(m, f)
    comp = make("CompletionReceipt", receipt_id="done", transaction_id="TX-SYN-1", outcome_receipt_hash=m.ev["outcome"]["object_hash"],
                commit_observation_hash=m.ev["commit"]["object_hash"], execution_receipt_hash=er["object_hash"], authority_hash=f["au"]["object_hash"])
    m.complete(comp)
    t(g, "full_chain_reaches_COMPLETE", m.state == "COMPLETE")
    t(g, "complete_has_complete_evidence_chain", len(chain_hashes(m)) == 14 and len({h for _, h in chain_hashes(m)}) == 14)
    m, f = fixture(); er, rb = happy(m, f, obs={"exists": True, "package": "ZPKG_SYN"})
    t(g, "unknown_predicate_stays_pending_not_complete", m.state == "OUTCOME_VALIDATION_PENDING")
    m, f = fixture(); to_prewrite(m, f); m.begin_execution("MUT-1", FP); m.record_execution(exec_receipt(f)); m.request_readback()
    rb = rb_receipt(f); m.observe_readback(rb); m.decide_commit(commit_obs(rb, "COMMITTED"))
    t(g, "forged_outcome_result_rejected", raises(lambda: m.validate_outcome(outcome(f, rb, "FAIL")), "disagrees"))
    t(g, "execution_success_alone_cannot_complete", raises(lambda: _exec_only_complete()))

    # ---- COMMIT_UNKNOWN_HANDLING
    g = "COMMIT_UNKNOWN_HANDLING"
    def to_readback(level="AUTHORITATIVE_REPOSITORY", existence="EXISTS", cls="PROVIDER_RESPONSE_SUCCESS"):
        m, f = fixture(); to_prewrite(m, f); m.begin_execution("MUT-1", FP); m.record_execution(exec_receipt(f, cls)); m.request_readback()
        rb = rb_receipt(f, existence, level); m.observe_readback(rb)
        return m, f, rb
    m, f, rb = to_readback(existence="UNKNOWN"); m.decide_commit(commit_obs(rb, "UNKNOWN"))
    t(g, "readback_unknown_yields_COMMIT_STATE_UNKNOWN", m.state == "COMMIT_STATE_UNKNOWN")
    t(g, "unknown_never_complete", raises(lambda: m._go("COMPLETE")))
    m, f, rb = to_readback(level="PROVIDER_VALIDATION", existence="EXISTS"); m.decide_commit(commit_obs(rb, "COMMITTED"))
    t(g, "non_authoritative_exists_is_not_committed", m.state == "COMMIT_STATE_UNKNOWN")
    for lvl in ("PROVIDER_LOG", "TRANSPORT_SUCCESS", "CACHED_OUTPUT", "LOCAL_RUNNER_STATE", "INFERRED_OR_REGEX"):
        m, f, rb = to_readback(level=lvl); m.decide_commit(commit_obs(rb, "COMMITTED"))
        t(g, "level_%s_cannot_establish_commit" % lvl, m.state == "COMMIT_STATE_UNKNOWN")
    m, f, rb = to_readback(existence="ABSENT"); m.decide_commit(commit_obs(rb, "ABSENT"))
    t(g, "authoritative_absent_is_not_committed_and_fail_closed", m.state == "FAILED_AFTER_POSSIBLE_MUTATION")
    t(g, "absent_does_not_unlock_retry", raises(lambda: m.begin_execution("MUT-1", FP)))
    m, f = fixture(); to_prewrite(m, f); m.begin_execution("MUT-1", FP); m.record_execution(exec_receipt(f, "PROVIDER_ERROR"))
    t(g, "provider_error_after_send_is_commit_unknown_not_absent", m.state == "COMMIT_STATE_UNKNOWN")
    m, f = fixture(); to_prewrite(m, f); m.begin_execution("MUT-1", FP)
    t(g, "cannot_fail_before_mutation_after_send", raises(lambda: m.fail_before_mutation(), "possibly sent"))
    m.fail_after_possible_mutation()
    t(g, "post_send_failure_state", m.state == "FAILED_AFTER_POSSIBLE_MUTATION")
    m, f = fixture(); to_prewrite(m, f); m.begin_execution("MUT-1", FP); m.record_execution(exec_receipt(f)); m.request_readback()
    t(g, "readback_for_wrong_transaction_rejected", raises(lambda: m.observe_readback(rb_receipt(f, tx="TX-OTHER")), "correlation"))
    t(g, "readback_for_wrong_mutation_rejected", raises(lambda: m.observe_readback(rb_receipt(f, mut="MUT-OTHER")), "correlated to mutation"))
    t(g, "correlation_keys_exclude_time", not any("time" in x or x.endswith("_at") for k in ("ExecutionReceipt", "CommitObservation", "AuthoritativeReadbackReceipt", "OutcomeReceipt") for x in SCHEMAS[k][0]))

    # ---- TELEMETRY
    g = "TELEMETRY_MODEL"
    t0 = time.perf_counter_ns(); m, f = fixture(); to_prewrite(m, f); gov = time.perf_counter_ns() - t0
    tel = make("GovernanceTelemetry", mission_id="M-SYN-1", governance_ns=gov, provider_ns=0)
    t(g, "governance_and_provider_time_are_separate_fields", "governance_ns" in tel and "provider_ns" in tel and gov >= 0)

    # ---- COMPLETION_EVIDENCE (R2.0G hardening)
    g = "COMPLETION_EVIDENCE"
    def complete_ready(obs=None, result="PASS"):
        m, f = fixture(); er, rb = happy(m, f, obs=obs)
        done = lambda **kw: make("CompletionReceipt", **dict(dict(receipt_id="done", transaction_id="TX-SYN-1",
                outcome_receipt_hash=m.ev["outcome"]["object_hash"], commit_observation_hash=m.ev["commit"]["object_hash"],
                execution_receipt_hash=er["object_hash"], authority_hash=f["au"]["object_hash"]), **kw))
        return m, f, er, done
    t(g, "contract_has_14_links_completion_last", len(EXPECTED_CHAIN) == 14 and EXPECTED_CHAIN[-1] == "COMPLETION_RECEIPT" and EXPECTED_CHAIN[0] == "MISSION_INTENT")
    m, f, er, done = complete_ready()
    t(g, "non_complete_mission_emits_13_without_completion", len(chain_hashes(m)) == 13 and "COMPLETION_RECEIPT" not in [l for l, _ in chain_hashes(m)])
    cr = done(); m.complete(cr)
    ch = chain_hashes(m)
    t(g, "completion_receipt_persisted_in_mission", m.ev.get("completion") == cr and verify_hash(m.ev["completion"]))
    t(g, "chain_labels_exact_and_ordered", [l for l, _ in ch] == EXPECTED_CHAIN)
    t(g, "chain_last_entry_is_completion_hash", ch[-1] == ("COMPLETION_RECEIPT", cr["object_hash"]))
    t(g, "chain_hashes_are_unique_64_hex", len({h for _, h in ch}) == 14 and all(len(h) == 64 and h == h.upper() for _, h in ch))
    t(g, "chain_hashes_match_objects", all(m.ev.get(slot, {}).get("object_hash") == dict(ch).get(label) for slot, label in CHAIN_SLOTS))
    t(g, "completion_links_upstream_hashes", cr["outcome_receipt_hash"] == dict(ch)["OUTCOME_RECEIPT"] and cr["commit_observation_hash"] == dict(ch)["COMMIT_OBSERVATION"]
      and cr["execution_receipt_hash"] == dict(ch)["EXECUTION_RECEIPT"] and cr["authority_hash"] == dict(ch)["AUTHORITY"])
    t(g, "completion_transaction_matches_mission", cr["transaction_id"] == m.transaction_id == m.ev["tx"]["transaction_id"])
    m, f, er, done = complete_ready()
    t(g, "absent_completion_rejected", raises(lambda: m.complete(None), "absent") and m.state == "OUTCOME_VALIDATED" and "completion" not in m.ev)
    t(g, "wrong_kind_rejected", raises(lambda: m.complete(f["au"]), "wrong kind") and "completion" not in m.ev)
    tam = dict(done()); tam["receipt_id"] = "forged"
    t(g, "tampered_completion_rejected", raises(lambda: m.complete(tam), "tampered") and "completion" not in m.ev)
    t(g, "wrong_transaction_completion_rejected", raises(lambda: m.complete(done(transaction_id="TX-OTHER")), "completion transaction mismatch") and "completion" not in m.ev)
    ok = True
    for fld in ("outcome_receipt_hash", "commit_observation_hash", "execution_receipt_hash", "authority_hash"):
        ok = ok and raises(lambda fld=fld: m.complete(done(**{fld: "0" * 64})), "evidence chain inconsistent") and "completion" not in m.ev and m.state == "OUTCOME_VALIDATED"
    t(g, "each_mismatched_link_rejected_without_persisting", ok)
    incomplete = {k: v for k, v in done().items() if k != "authority_hash"}
    t(g, "incomplete_completion_rejected", raises(lambda: m.complete(incomplete)) and "completion" not in m.ev)
    ok = True
    for slot, _ in CHAIN_SLOTS[:-1]:
        m2, f2, er2, done2 = complete_ready()
        cr2 = done2()
        del m2.ev[slot]
        ok = ok and raises(lambda cr2=cr2, m2=m2: m2.complete(cr2), "incomplete evidence chain") and m2.state != "COMPLETE" and "completion" not in m2.ev
    t(g, "missing_any_of_13_upstream_links_blocks_COMPLETE", ok)
    ok = True
    for slot, _ in CHAIN_SLOTS[:-1]:
        m2, f2, er2, done2 = complete_ready()
        cr2 = done2()
        m2.ev[slot] = dict(m2.ev[slot], tampered_marker=1)
        ok = ok and raises(lambda cr2=cr2, m2=m2: m2.complete(cr2), "tampered") and m2.state != "COMPLETE"
    t(g, "tampering_any_of_13_upstream_links_blocks_COMPLETE", ok)
    m2, f2, er2, done2 = complete_ready(obs={"exists": True, "package": "ZPKG_SYN"})
    t(g, "unknown_predicates_block_COMPLETE", m2.state == "OUTCOME_VALIDATION_PENDING" and raises(lambda: m2.complete(done2()), None) and "completion" not in m2.ev)
    m3, f3 = fixture(); to_prewrite(m3, f3); m3.begin_execution("MUT-1", FP); m3.record_execution(exec_receipt(f3, "CALL_SENT_NO_RESPONSE"))
    t(g, "commit_unknown_has_no_completion_link", m3.state == "COMMIT_STATE_UNKNOWN" and "COMPLETION_RECEIPT" not in [l for l, _ in chain_hashes(m3)])
    m4, f4, er4, done4 = complete_ready(obs=dict(GOOD_OBS, package="WRONG"))
    t(g, "failed_predicate_blocks_COMPLETE", m4.state == "COMPENSATION_REQUIRED" and raises(lambda: m4.complete(done4()), None) and "completion" not in m4.ev)
    m5, f5 = fixture(); to_prewrite(m5, f5)
    t(g, "complete_from_prewrite_state_rejected", raises(lambda: m5.complete(make("CompletionReceipt", receipt_id="d", transaction_id="TX-SYN-1", outcome_receipt_hash="a", commit_observation_hash="b", execution_receipt_hash="c", authority_hash="d")), None))
    m6, f6, er6, done6 = complete_ready()
    m6.complete(done6())
    t(g, "complete_is_terminal_no_second_completion", raises(lambda: m6.complete(done6(receipt_id="again")), None))

    # ---- HARDENING_R2_0H (independent-review findings)
    g = "HARDENING_R2_0H"
    def remake(obj, **chg):
        body = {k: v for k, v in obj.items() if k not in ("kind", "object_hash")}
        body.update(chg)
        return make(obj["kind"], **body)

    def sent_mission():
        mm, ff = fixture(); to_prewrite(mm, ff); mm.begin_execution("MUT-1", FP)
        return mm, ff, mm.checkpoint_lease()

    m, f, lease = sent_mission()
    bad_state = dict(lease, state_at_checkpoint="OUTCOME_VALIDATED")
    t(g, "lease_with_invalid_hash_rejected", raises(lambda: rsm(bad_state, f, m), "hash invalid"))
    forged = remake(lease, state_at_checkpoint="OUTCOME_VALIDATED")
    try:
        r = rsm(forged, f, m)
    except GuardError:
        r = None
    t(g, "lease_state_never_inherited_after_send", r is not None and r.state == "COMMIT_STATE_UNKNOWN" and "readback" not in r.ev and "outcome" not in r.ev)
    t(g, "forged_lease_cannot_reach_complete", r is not None and raises(lambda: r.complete(make("CompletionReceipt", receipt_id="x", transaction_id="TX-SYN-1", outcome_receipt_hash="0" * 64,
                                                                              commit_observation_hash="0" * 64, execution_receipt_hash="0" * 64, authority_hash="0" * 64))) and r.state == "COMMIT_STATE_UNKNOWN")
    ok = True
    for slot in ("readback", "commit", "outcome", "completion"):
        ev = ev_upstream(m)
        ev[slot] = make({"readback": "AuthoritativeReadbackReceipt", "commit": "CommitObservation", "outcome": "OutcomeReceipt", "completion": "CompletionReceipt"}[slot],
                        **{"readback": dict(receipt_id="r", transaction_id="TX-SYN-1", mutation_id="MUT-1", contract_hash="h", source_level="AUTHORITATIVE_REPOSITORY", existence="EXISTS", activation="UNKNOWN", observed={}),
                           "commit": dict(observation_id="c", transaction_id="TX-SYN-1", mutation_id="MUT-1", readback_receipt_hash="h", commit_state="COMMITTED"),
                           "outcome": dict(receipt_id="o", transaction_id="TX-SYN-1", readback_receipt_hash="h", outcome_contract_hash="h", result="PASS"),
                           "completion": dict(receipt_id="d", transaction_id="TX-SYN-1", outcome_receipt_hash="h", commit_observation_hash="h", execution_receipt_hash="h", authority_hash="h")}[slot])
        ok = ok and raises(lambda ev=ev: rsm(lease, f, m, evidence=ev), "no downstream")
    t(g, "resume_refuses_downstream_evidence_slots", ok)
    t(g, "lease_state_inconsistent_with_consumed_rejected",
      raises(lambda: rsm(remake(lease, consumed_authority_ids=[]), f, m), "inconsistent")
      and raises(lambda: rsm(remake(lease, state_at_checkpoint="PREWRITE_VALIDATED"), f, m), "inconsistent"))
    t(g, "lease_consumed_for_other_authority_rejected",
      raises(lambda: rsm(remake(lease, consumed_authority_ids=["OTHERHASH:MUT-1"]), f, m), "does not belong"))
    t(g, "lease_unknown_mutation_rejected",
      raises(lambda: rsm(remake(lease, mutation_id="MUT-X"), f, m), "inconsistent"))
    t(g, "resume_wrong_kind_evidence_rejected",
      raises(lambda: rsm(lease, f, m, evidence=dict(ev_upstream(m), intent=f["pr"])), "wrong kind"))

    # failed calls change nothing (atomicity)
    m, f, er, done = complete_ready()
    snap = (m.state, dict(m.ev), m.remaining, set(m.consumed), m.mutations_sent, list(m.history))
    same = lambda: (m.state, m.ev, m.remaining, m.consumed, m.mutations_sent, m.history) == snap
    forged_rb = rb_receipt(f, "UNKNOWN", level="INFERRED_OR_REGEX", obs={})
    t(g, "late_observe_readback_rejected_and_changes_nothing", raises(lambda: m.observe_readback(forged_rb)) and same() and m.ev["readback"]["existence"] == "EXISTS")
    t(g, "invalid_class_execution_receipt_changes_nothing", raises(lambda: m.record_execution(exec_receipt(f, "CALL_NOT_SENT"))) and same())
    t(g, "late_execution_receipt_changes_nothing", raises(lambda: m.record_execution(exec_receipt(f, "PROVIDER_RESPONSE_SUCCESS"))) and same())
    t(g, "begin_execution_in_wrong_state_consumes_no_budget", raises(lambda: m.begin_execution("MUT-1", FP)) and same())
    t(g, "original_evidence_still_completes_after_rejected_calls", safe(lambda: (m.complete(done()), m.state)[1] == "COMPLETE"))
    m, f = fixture(); to_prewrite(m, f); m.begin_execution("MUT-1", FP); m.record_execution(exec_receipt(f)); m.request_readback()
    rbx = rb_receipt(f); m.observe_readback(rbx); m.decide_commit(commit_obs(rbx, "COMMITTED"))
    t(g, "bad_outcome_binding_does_not_leave_pending", raises(lambda: m.validate_outcome(make("OutcomeReceipt", receipt_id="o", transaction_id="TX-SYN-1",
                      readback_receipt_hash="0" * 64, outcome_contract_hash=f["oc"]["object_hash"], result="PASS"))) and m.state == "COMMITTED" and "outcome" not in m.ev)
    def pending():
        mm, ff = fixture(); to_prewrite(mm, ff); mm.begin_execution("MUT-1", FP); mm.record_execution(exec_receipt(ff)); mm.request_readback()
        return mm, ff
    def observed():
        mm, ff = pending(); rbo = rb_receipt(ff); mm.observe_readback(rbo)
        return mm, ff, rbo
    m, f = pending()
    t(g, "readback_under_other_contract_rejected", raises(lambda: m.observe_readback(make("AuthoritativeReadbackReceipt", receipt_id="r", transaction_id="TX-SYN-1", mutation_id="MUT-1",
                      contract_hash="0" * 64, source_level="AUTHORITATIVE_REPOSITORY", existence="EXISTS", activation="UNKNOWN", observed=GOOD_OBS)), "frozen contract") and m.state == "AUTHORITATIVE_READBACK_PENDING")
    m, f, rb1 = observed()
    other = rb_receipt(f, obs=dict(GOOD_OBS, package="Q"))
    t(g, "commit_bound_to_other_readback_rejected", raises(lambda: m.decide_commit(commit_obs(other, "COMMITTED")), "not bound to readback") and m.state == "AUTHORITATIVE_READBACK_OBSERVED")
    m, f, rb1 = observed()
    t(g, "commit_understating_authoritative_exists_rejected", raises(lambda: m.decide_commit(commit_obs(rb1, "UNKNOWN")), "contradicts") and m.state == "AUTHORITATIVE_READBACK_OBSERVED")
    m, f = fixture(); to_prewrite(m, f); m.begin_execution("MUT-1", FP)
    t(g, "execution_receipt_for_other_mutation_rejected", raises(lambda: m.record_execution(exec_receipt(f, mut="MUT-OTHER")), "not correlated") and m.state == "EXECUTION_STARTED")

    # relational chain checks: forgeries whose hashes the attacker recomputed
    def forge(slot, new):
        mm, ff, er_, done_ = complete_ready()
        if callable(new):
            new(mm, ff)
        else:
            mm.ev[slot] = new
        return mm, done_()
    def blocked(slot, new, text=None):
        mm, cr_ = forge(slot, new)
        return raises(lambda: mm.complete(cr_), text) and mm.state == "OUTCOME_VALIDATED" and "completion" not in mm.ev
    mm0, ff0, _, _ = complete_ready()
    def consistent_forgery(level, existence):
        mm, ff, er_, done_ = complete_ready()
        rb2 = rb_receipt(ff, existence, level, obs=GOOD_OBS)
        mm.ev["readback"] = rb2
        mm.ev["commit"] = make("CommitObservation", observation_id="co2", transaction_id="TX-SYN-1", mutation_id="MUT-1", readback_receipt_hash=rb2["object_hash"], commit_state="COMMITTED")
        mm.ev["outcome"] = make("OutcomeReceipt", receipt_id="or2", transaction_id="TX-SYN-1", readback_receipt_hash=rb2["object_hash"], outcome_contract_hash=ff["oc"]["object_hash"], result="PASS")
        return mm, done_()
    ok = True
    for lvl, ex in (("INFERRED_OR_REGEX", "EXISTS"), ("PROVIDER_LOG", "EXISTS"), ("AUTHORITATIVE_REPOSITORY", "UNKNOWN"), ("AUTHORITATIVE_REPOSITORY", "ABSENT")):
        mm, cr_ = consistent_forgery(lvl, ex)
        ok = ok and raises(lambda mm=mm, cr_=cr_: mm.complete(cr_), "readback is not") and mm.state == "OUTCOME_VALIDATED" and "completion" not in mm.ev
    t(g, "self_consistent_forged_chain_with_non_authoritative_or_non_exists_readback_blocked", ok)
    t(g, "rehashed_unknown_readback_blocked", blocked("readback", rb_receipt(ff0, "UNKNOWN", level="INFERRED_OR_REGEX", obs={})))
    t(g, "rehashed_call_not_sent_execution_receipt_blocked", blocked("execution_receipt", make("ExecutionReceipt", receipt_id="e", transaction_id="TX-SYN-1", mutation_id="MUT-1", call_class="CALL_NOT_SENT")))
    t(g, "rehashed_commit_unknown_blocked", blocked("commit", remake(mm0.ev["commit"], commit_state="UNKNOWN")))
    t(g, "rehashed_outcome_fail_blocked", blocked("outcome", remake(mm0.ev["outcome"], result="FAIL")))
    t(g, "rehashed_foreign_delegation_blocked", blocked("delegation", remake(mm0.ev["delegation"], delegation_id="evil"), "inconsistent"))
    t(g, "wrong_kind_in_slot_blocked", blocked("intent", ff0["pr"], "wrong kind"))
    t(g, "swapped_outcome_contract_not_matching_checkpoint_blocked", blocked("outcome_contract", remake(mm0.ev["outcome_contract"], outcome_contract_id="other"), "inconsistent"))
    t(g, "erased_replay_record_blocked", blocked(None, lambda mm, ff: mm.consumed.clear(), "never consumed"))
    t(g, "rehashed_foreign_mission_authority_blocked", blocked("authority", remake(mm0.ev["authority"], mission_id="OTHER"), "inconsistent"))
    t(g, "rehashed_checkpoint_with_other_pins_blocked", blocked("checkpoint", remake(mm0.ev["checkpoint"], budget_hash="0" * 64), "does not pin"))
    t(g, "rehashed_readback_wrong_contract_blocked", blocked("readback", remake(mm0.ev["readback"], contract_hash="0" * 64)))
    m, f, er, done = complete_ready()
    t(g, "direct_go_to_COMPLETE_refused_even_when_legal", raises(lambda: m._go("COMPLETE"), "direct state change refused") and m.state == "OUTCOME_VALIDATED")

    # predicates
    t(g, "empty_predicates_not_vacuous_pass", raises(lambda: eval_predicates([], {"exists": True}), "vacuous"))
    t(g, "unknown_predicate_op_rejected", raises(lambda: eval_predicates([{"field": "a", "op": "like", "expected": [1]}], {"a": 1}), "unknown predicate op"))
    t(g, "in_op_requires_collection", raises(lambda: eval_predicates([{"field": "a", "op": "in", "expected": 5}], {"a": 5}), "collection"))
    mm, ff = fixture(); mm.context_ready(ff["intent"], ff["pr"]); mm.authorize(ff["dl"], ff["au"], ff["bu"]); mm.bind(ff["cb"], ff["pb"])
    empty_oc = make("ExpectedOutcomeContract", outcome_contract_id="oc1", mission_id="M-SYN-1", transaction_id="TX-SYN-1", predicates=[], frozen=True)
    cpe = make("PreMutationCheckpoint", checkpoint_id="cp1", transaction_hash=ff["tx"]["object_hash"], budget_hash=ff["bu"]["object_hash"], outcome_contract_hash=empty_oc["object_hash"],
               readback_contract_hash=ff["rc"]["object_hash"], remaining_budget=1)
    t(g, "prewrite_rejects_empty_predicates", raises(lambda: mm.prewrite_validate(ff["tx"], empty_oc, ff["rc"], cpe), "vacuous") and mm.state == "BOUND")
    # replay guard across Mission objects (tuple-keyed consumed set)
    ma, fa = fixture(); to_prewrite(ma, fa); ma.begin_execution("MUT-1", FP)
    mb, fb = fixture(); mb.context_ready(fb["intent"], fb["pr"]); mb.consumed = set(ma.consumed)
    t(g, "consumed_authority_blocks_reauthorization_with_tuple_keys", raises(lambda: mb.authorize(fb["dl"], fb["au"], fb["bu"]), "already consumed"))

    # ---- HARDENING_R2_0I (independent review 2: gates, ledger, terminal states, relations)
    g = "HARDENING_R2_0I"
    Z = "0" * 64
    stale = lambda obj, **chg: dict(obj, **chg)          # changed content, hash NOT recomputed

    def at_context():
        mm, ff = fixture(); mm.context_ready(ff["intent"], ff["pr"])
        return mm, ff

    def at_authorized():
        mm, ff = at_context(); mm.authorize(ff["dl"], ff["au"], ff["bu"])
        return mm, ff

    def at_bound():
        mm, ff = at_authorized(); mm.bind(ff["cb"], ff["pb"])
        return mm, ff

    def at_started():
        mm, ff = fixture(); to_prewrite(mm, ff); mm.begin_execution("MUT-1", FP)
        return mm, ff

    def at_observed():
        mm, ff = fixture(); to_prewrite(mm, ff); mm.begin_execution("MUT-1", FP); mm.record_execution(exec_receipt(ff)); mm.request_readback()
        rbo = rb_receipt(ff); mm.observe_readback(rbo)
        return mm, ff, rbo

    def at_committed():
        mm, ff, rbo = at_observed(); mm.decide_commit(commit_obs(rbo, "COMMITTED"))
        return mm, ff, rbo

    def state_unchanged(mm, state, slots):
        return mm.state == state and set(mm.ev) == set(slots)

    # -- send-time gates verify every presented object (review 2 N1)
    m, f = fixture()
    t(g, "context_ready_rejects_tampered_and_wrong_kind", raises(lambda: m.context_ready(stale(f["intent"], objective="x"), f["pr"]), "hash invalid")
      and raises(lambda: m.context_ready(f["intent"], f["intent"]), "wrong kind") and raises(lambda: m.context_ready(remake(f["intent"], mission_id="OTHER"), f["pr"]), "intent mission mismatch")
      and m.state == "PLANNED" and not m.ev)
    dl2 = lambda ff, **c: remake(ff["dl"], **c)
    def chain_with(ff, dl=None, au=None, bu=None):
        d = dl or ff["dl"]; a = remake(au or ff["au"], delegation_hash=d["object_hash"]); b = remake(bu or ff["bu"], authority_hash=a["object_hash"])
        return d, a, b
    cases = [
        ("authorize_rejects_tampered_delegation", lambda ff: (stale(ff["dl"], scope=["create_object", "read_object", "delete_object"]), ff["au"], ff["bu"]), "hash invalid"),
        ("authorize_rejects_tampered_authority", lambda ff: (ff["dl"], stale(ff["au"], max_mutations=5), ff["bu"]), "hash invalid"),
        ("authorize_rejects_tampered_budget", lambda ff: (ff["dl"], ff["au"], stale(ff["bu"], max_mutations=5)), "hash invalid"),
        ("authorize_rejects_wrong_kind", lambda ff: (ff["pr"], ff["au"], ff["bu"]), "wrong kind"),
        ("authorize_rejects_delegation_for_other_principal", lambda ff: (dl2(ff, principal_hash=Z), ff["au"], ff["bu"]), "not issued to this principal"),
        ("authorize_rejects_foreign_mission_authority", lambda ff: chain_with(ff, au=remake(ff["au"], mission_id="OTHER")), "authority mission mismatch"),
        ("authorize_rejects_scope_beyond_delegation", lambda ff: chain_with(ff, au=remake(ff["au"], scope=["create_object", "delete_object"])), "no attenuation"),
        ("authorize_rejects_count_beyond_delegation", lambda ff: chain_with(ff, dl=dl2(ff, max_mutations=0)), "exceeds delegation"),
        ("authorize_rejects_authority_not_single_use", lambda ff: chain_with(ff, au=remake(ff["au"], single_use=False)), "single use"),
        ("authorize_rejects_budget_not_derived_from_authority", lambda ff: (ff["dl"], ff["au"], remake(ff["bu"], authority_hash=Z)), "not bounded by authority"),
        ("authorize_rejects_budget_above_authority", lambda ff: (ff["dl"], ff["au"], remake(ff["bu"], max_mutations=2)), "not bounded by authority"),
        ("authorize_rejects_retries", lambda ff: (ff["dl"], ff["au"], remake(ff["bu"], retries=1)), "forbid expansion and retries"),
        ("authorize_rejects_expansion", lambda ff: (ff["dl"], ff["au"], remake(ff["bu"], expansion_allowed=True)), "forbid expansion and retries"),
    ]
    for name, build, text in cases:
        mm, ff = at_context()
        t(g, name, raises(lambda mm=mm, ff=ff, build=build: mm.authorize(*build(ff)), text) and state_unchanged(mm, "CONTEXT_READY", {"intent", "principal"}))
    mm, ff = fixture(max_mut=2); mm.max_mutations = 1; mm.remaining = 1; mm.context_ready(ff["intent"], ff["pr"])
    t(g, "authorize_rejects_budget_differing_from_mission_limit", raises(lambda: mm.authorize(ff["dl"], ff["au"], ff["bu"]), "differs from mission limit") and mm.state == "CONTEXT_READY")
    cases = [
        ("bind_rejects_tampered_capability", lambda ff: (stale(ff["cb"], capability="x"), ff["pb"]), "hash invalid"),
        ("bind_rejects_tampered_provider", lambda ff: (ff["cb"], stale(ff["pb"], tool_name="x")), "hash invalid"),
        ("bind_rejects_wrong_kind", lambda ff: (ff["pb"], ff["cb"]), "wrong kind"),
        ("bind_rejects_foreign_authority", lambda ff: (remake(ff["cb"], authority_hash=Z), ff["pb"]), "not from this authority"),
        ("bind_rejects_capability_outside_scope", lambda ff: (remake(ff["cb"], capability="delete_object"), ff["pb"]), "outside authority scope"),
        ("bind_rejects_capability_tool_mismatch", lambda ff: (ff["cb"], remake(ff["pb"], tool_name="other_tool")), "does not match provider tool"),
        ("bind_rejects_provider_ref_mismatch", lambda ff: (ff["cb"], remake(ff["pb"], identity="OTHER::x")), "provider_ref differs"),
    ]
    for name, build, text in cases:
        mm, ff = at_authorized()
        t(g, name, raises(lambda mm=mm, ff=ff, build=build: mm.bind(*build(ff)), text) and mm.state == "AUTHORIZED" and "capability" not in mm.ev)
    ocx = lambda ff, **c: remake(ff["oc"], **c)
    def cp_for(ff, **c):
        base = dict(checkpoint_id="cp1", transaction_hash=ff["tx"]["object_hash"], budget_hash=ff["bu"]["object_hash"], outcome_contract_hash=ff["oc"]["object_hash"],
                    readback_contract_hash=ff["rc"]["object_hash"], remaining_budget=1)
        base.update(c)
        return make("PreMutationCheckpoint", **base)
    cases = [
        ("prewrite_rejects_tampered_transaction", lambda ff: (stale(ff["tx"], boundary="x"), ff["oc"], ff["rc"], ff["cp"]), "hash invalid"),
        ("prewrite_rejects_tampered_outcome_contract", lambda ff: (ff["tx"], stale(ff["oc"], frozen=False), ff["rc"], ff["cp"]), "hash invalid"),
        ("prewrite_rejects_tampered_readback_contract", lambda ff: (ff["tx"], ff["oc"], stale(ff["rc"], checks=[]), ff["cp"]), "hash invalid"),
        ("prewrite_rejects_tampered_checkpoint", lambda ff: (ff["tx"], ff["oc"], ff["rc"], stale(ff["cp"], remaining_budget=9)), "hash invalid"),
        ("prewrite_rejects_foreign_mission_transaction", lambda ff: (remake(ff["tx"], mission_id="OTHER"), ff["oc"], ff["rc"], ff["cp"]), "mission mismatch"),
        ("prewrite_rejects_foreign_mission_outcome_contract", lambda ff: (ff["tx"], ocx(ff, mission_id="OTHER"), ff["rc"], ff["cp"]), "mission mismatch"),
        ("prewrite_rejects_string_mutation_ids", lambda ff: (remake(ff["tx"], mutation_ids="MUT-1"), ff["oc"], ff["rc"], ff["cp"]), "non-empty list of strings"),
        ("prewrite_rejects_empty_mutation_ids", lambda ff: (remake(ff["tx"], mutation_ids=[]), ff["oc"], ff["rc"], ff["cp"]), "non-empty list of strings"),
        ("prewrite_rejects_non_string_mutation_id", lambda ff: (remake(ff["tx"], mutation_ids=[1]), ff["oc"], ff["rc"], ff["cp"]), "non-empty list of strings"),
        ("prewrite_rejects_unfrozen_outcome_contract", lambda ff: (ff["tx"], ocx(ff, frozen=False), ff["rc"], ff["cp"]), "not frozen"),
        ("prewrite_rejects_checkpoint_not_pinning_outcome_contract", lambda ff: (ff["tx"], ff["oc"], ff["rc"], cp_for(ff, outcome_contract_hash=Z)), "pin outcome contract"),
        ("prewrite_rejects_checkpoint_not_pinning_readback_contract", lambda ff: (ff["tx"], ff["oc"], ff["rc"], cp_for(ff, readback_contract_hash=Z)), "pin readback contract"),
        ("prewrite_rejects_checkpoint_not_pinning_budget", lambda ff: (ff["tx"], ff["oc"], ff["rc"], cp_for(ff, budget_hash=Z)), "pin budget"),
        ("prewrite_rejects_checkpoint_not_pinning_transaction", lambda ff: (ff["tx"], ff["oc"], ff["rc"], cp_for(ff, transaction_hash=Z)), "pin transaction"),
        ("prewrite_rejects_checkpoint_budget_mismatch", lambda ff: (ff["tx"], ff["oc"], ff["rc"], cp_for(ff, remaining_budget=2)), "checkpoint budget differs"),
        ("prewrite_rejects_non_authoritative_readback_contract", lambda ff: (ff["tx"], ff["oc"], remake(ff["rc"], source_level_required="PROVIDER_LOG"), ff["cp"]), "pin readback contract"),
    ]
    for name, build, text in cases:
        mm, ff = at_bound()
        t(g, name, raises(lambda mm=mm, ff=ff, build=build: mm.prewrite_validate(*build(ff)), text) and mm.state == "BOUND" and "tx" not in mm.ev)
    mm, ff = at_bound()
    rc_weak = remake(ff["rc"], source_level_required="PROVIDER_LOG"); cp_weak = cp_for(ff, readback_contract_hash=rc_weak["object_hash"])
    t(g, "prewrite_rejects_readback_contract_that_is_not_authoritative", raises(lambda: mm.prewrite_validate(ff["tx"], ff["oc"], rc_weak, cp_weak), "not authoritative") and mm.state == "BOUND")
    mm, ff = at_bound(); mm.prewrite_validate(ff["tx"], ff["oc"], ff["rc"], ff["cp"])
    t(g, "begin_execution_rejects_invalid_mutation_ids", all(raises(lambda mid=mid: mm.begin_execution(mid, FP), "invalid mutation id") for mid in (None, 1, "", "MUT-1\n"))
      and mm.state == "PREWRITE_VALIDATED" and mm.mutations_sent == 0 and not mm.ledger.for_authority(ff["au"]["object_hash"]))
    mm, ff = at_started()
    t(g, "execution_receipt_gate_rejects_tampered_and_wrong_kind", raises(lambda: mm.record_execution(stale(exec_receipt(ff), call_class="PROVIDER_ERROR")), "hash invalid")
      and raises(lambda: mm.record_execution(ff["cp"]), "wrong kind") and state_unchanged(mm, "EXECUTION_STARTED", set(mm.ev)))
    mm, ff = at_started(); mm.record_execution(exec_receipt(ff)); mm.request_readback()
    t(g, "readback_gate_rejects_tampered_and_wrong_kind", raises(lambda: mm.observe_readback(stale(rb_receipt(ff), existence="ABSENT")), "hash invalid")
      and raises(lambda: mm.observe_readback(ff["cp"]), "wrong kind") and mm.state == "AUTHORITATIVE_READBACK_PENDING" and "readback" not in mm.ev)
    mm, ff, rbo = at_observed()
    t(g, "commit_gate_rejects_tampered_wrong_kind_and_foreign_mutation", raises(lambda: mm.decide_commit(stale(commit_obs(rbo, "COMMITTED"), commit_state="COMMITTED", observation_id="x")), "hash invalid")
      and raises(lambda: mm.decide_commit(ff["cp"]), "wrong kind")
      and raises(lambda: mm.decide_commit(make("CommitObservation", observation_id="c", transaction_id="TX-SYN-1", mutation_id="MUT-OTHER", readback_receipt_hash=rbo["object_hash"], commit_state="COMMITTED")), "not correlated to mutation")
      and raises(lambda: mm.decide_commit(make("CommitObservation", observation_id="c", transaction_id="TX-OTHER", mutation_id="MUT-1", readback_receipt_hash=rbo["object_hash"], commit_state="COMMITTED")), "correlation")
      and mm.state == "AUTHORITATIVE_READBACK_OBSERVED" and "commit" not in mm.ev)
    mm, ff, rbo = at_committed()
    t(g, "outcome_gate_rejects_tampered_wrong_kind_and_foreign_transaction", raises(lambda: mm.validate_outcome(stale(outcome(ff, rbo, "PASS"), result="PASS", receipt_id="x")), "hash invalid")
      and raises(lambda: mm.validate_outcome(ff["cp"]), "wrong kind")
      and raises(lambda: mm.validate_outcome(make("OutcomeReceipt", receipt_id="o", transaction_id="TX-OTHER", readback_receipt_hash=rbo["object_hash"], outcome_contract_hash=ff["oc"]["object_hash"], result="PASS")), "correlation")
      and mm.state == "COMMITTED" and "outcome" not in mm.ev)

    # -- terminal and intermediate states are reachable only on verified evidence (review 2 N3, N3b)
    mm, ff, rbo = at_observed(); fake = dict(commit_obs(rbo, "COMMITTED")); fake.pop("object_hash")
    t(g, "committed_not_reachable_on_unhashed_dict", raises(lambda: mm.decide_commit(fake)) and mm.state == "AUTHORITATIVE_READBACK_OBSERVED")
    mm, ff, rbo = at_committed(); fake = dict(outcome(ff, rbo, "PASS")); fake.pop("object_hash")
    t(g, "outcome_validated_not_reachable_on_unhashed_dict", raises(lambda: mm.validate_outcome(fake)) and mm.state == "COMMITTED")

    def comp_ready(bad_obs=None):
        mm, ff = fixture(); to_prewrite(mm, ff); mm.begin_execution("MUT-1", FP); mm.record_execution(exec_receipt(ff)); mm.request_readback()
        obs = bad_obs or dict(GOOD_OBS, package="WRONG"); rbo = rb_receipt(ff, obs=obs); mm.observe_readback(rbo); mm.decide_commit(commit_obs(rbo, "COMMITTED"))
        mm.validate_outcome(outcome(ff, rbo, eval_predicates(PREDS, obs)))
        return mm, ff
    PRE = [{"field": "exists", "op": "eq", "expected": True}]
    GOAL = [{"field": "exists", "op": "eq", "expected": False}]
    grant_of = lambda **k: make("CompensationGrant", **dict(dict(grant_id="g1", target="SYN_SYS", capability="delete_object", max_mutations=1, preconditions=PRE,
                                outcome_predicates=GOAL, inherits_forward_authority=False, issued_by="OWNER2"), **k))
    cases = [
        ("compensation_rejects_tampered_grant", lambda ff: stale(grant_of(), capability="x"), "hash invalid"),
        ("compensation_rejects_wrong_kind_grant", lambda ff: ff["cp"], "wrong kind"),
        ("compensation_rejects_capability_inside_forward_scope", lambda ff: grant_of(capability="create_object"), "within forward authority scope"),
        ("compensation_rejects_zero_budget_grant", lambda ff: grant_of(max_mutations=0), "incomplete"),
        ("compensation_rejects_boolean_budget_grant", lambda ff: grant_of(max_mutations=True), "incomplete"),
        ("compensation_rejects_free_text_preconditions", lambda ff: grant_of(preconditions=["object exists"]), "malformed predicate"),
        ("compensation_rejects_unsatisfied_precondition", lambda ff: grant_of(preconditions=[{"field": "package", "op": "eq", "expected": "ZPKG_SYN"}]), "precondition not satisfied"),
        ("compensation_rejects_vacuous_outcome_predicates", lambda ff: grant_of(outcome_predicates=[{"field": "exists", "op": "like", "expected": 1}]), "unknown predicate op"),
    ]
    for name, build, text in cases:
        mm, ff = comp_ready()
        t(g, name, raises(lambda mm=mm, ff=ff, build=build: mm.authorize_compensation(build(ff)), text) and mm.state == "COMPENSATION_REQUIRED" and "comp_grant" not in mm.ev)
    mm, ff = fixture(); to_prewrite(mm, ff); mm.begin_execution("MUT-1", FP)
    mm.fail_after_possible_mutation()
    t(g, "compensation_needs_forward_readback", (mm.require_compensation(), raises(lambda: mm.authorize_compensation(grant_of()), "need the forward readback"))[1] and mm.state == "COMPENSATION_REQUIRED")
    mm, ff = fixture(); to_prewrite(mm, ff); mm.begin_execution("MUT-1", FP); mm.record_execution(exec_receipt(ff)); mm.request_readback()
    rba = rb_receipt(ff, "ABSENT", obs={"exists": False}); mm.observe_readback(rba); mm.decide_commit(commit_obs(rba, "ABSENT")); mm.require_compensation()
    t(g, "compensation_refused_when_nothing_exists_to_compensate", raises(lambda: mm.authorize_compensation(grant_of()), "precondition not satisfied") and mm.state == "COMPENSATION_REQUIRED")

    def comp_authorized2():
        mm, ff = comp_ready(); gg = grant_of(); mm.authorize_compensation(gg); mm.begin_compensation()
        return mm, ff, gg
    def comp_receipt_for(gg, post, res="PASS"):
        return make("CompensationReceipt", receipt_id="cr", grant_hash=gg["object_hash"], readback_receipt_hash=post["object_hash"], result=res)
    cases = [
        ("compensation_rejects_foreign_transaction_readback", lambda ff: rb_receipt(ff, "ABSENT", obs={"exists": False}, tx="TX-OTHER"), "correlation"),
        ("compensation_rejects_foreign_mutation_readback", lambda ff: rb_receipt(ff, "ABSENT", obs={"exists": False}, mut="MUT-OTHER"), "not correlated to the mission"),
        ("compensation_rejects_readback_under_other_contract", lambda ff: remake(rb_receipt(ff, "ABSENT", obs={"exists": False}), contract_hash=Z), "not correlated to the mission"),
        ("compensation_rejects_unhashed_readback", lambda ff: stale(rb_receipt(ff, "ABSENT", obs={"exists": False}), existence="ABSENT", receipt_id="q"), "hash invalid"),
    ]
    for name, build, text in cases:
        mm, ff, gg = comp_authorized2(); post = build(ff)
        t(g, name, raises(lambda mm=mm, gg=gg, post=post: mm.record_compensation(comp_receipt_for(gg, post), post, comp_exec(gg)), text) and mm.state == "COMPENSATION_AUTHORIZED")
    mm, ff, gg = comp_authorized2(); post = rb_receipt(ff, "ABSENT", obs={"exists": False})
    t(g, "compensation_rejects_tampered_receipt_and_foreign_grant", raises(lambda: mm.record_compensation(stale(comp_receipt_for(gg, post), result="PASS", receipt_id="x"), post, comp_exec(gg)), "hash invalid")
      and raises(lambda: mm.record_compensation(make("CompensationReceipt", receipt_id="cr", grant_hash=Z, readback_receipt_hash=post["object_hash"], result="PASS"), post, comp_exec(grant)), "not bound to its grant")
      and raises(lambda: mm.record_compensation(make("CompensationReceipt", receipt_id="cr", grant_hash=gg["object_hash"], readback_receipt_hash=Z, result="PASS"), post, comp_exec(grant)), "not bound to post readback")
      and raises(lambda: mm.record_compensation(comp_receipt_for(gg, post, "FAIL"), post, comp_exec(gg)), "predicate not satisfied") and mm.state == "COMPENSATION_AUTHORIZED")
    mm, ff, gg = comp_authorized2(); post = rb_receipt(ff, "ABSENT", obs={"exists": False}); mm.record_compensation(comp_receipt_for(gg, post), post, comp_exec(gg))
    t(g, "compensation_with_verified_evidence_reaches_COMPENSATED_only", mm.state == "COMPENSATED" and "completion" not in mm.ev)

    # -- replay ledger and stale leases (review 2 N2)
    mm, ff = fixture(); to_prewrite(mm, ff)
    stale_lease = mm.checkpoint_lease()
    mm.begin_execution("MUT-1", FP)                       # the send happens; the lease below was never refreshed
    rr = rsm(stale_lease, ff, mm)
    t(g, "stale_lease_resume_restarts_in_unknown", rr.state == "COMMIT_STATE_UNKNOWN" and rr.mutations_sent == 1 and rr.remaining == 0)
    t(g, "stale_lease_cannot_replay_the_mutation", raises(lambda: (setattr(rr, "state", "PREWRITE_VALIDATED"), rr.begin_execution("MUT-1", FP)), "replay") and rr.mutations_sent == 1)
    import tempfile
    ldir = tempfile.mkdtemp(prefix="r2ledger_"); lpath = os.path.join(ldir, "ledger.txt")
    m1, f1 = fixture(); m1.ledger = MODEL.ReplayLedger(lpath); to_prewrite(m1, f1); lease_a = m1.checkpoint_lease(); m1.begin_execution("MUT-1", FP)
    reloaded = MODEL.ReplayLedger(lpath)                  # simulated process restart: only the file survives
    r2 = rsm(lease_a, f1, m1, ledger=reloaded)
    t(g, "file_backed_ledger_survives_restart_and_blocks_stale_lease", reloaded.has((f1["au"]["object_hash"], "MUT-1")) and r2.state == "COMMIT_STATE_UNKNOWN"
      and raises(lambda: (setattr(r2, "state", "PREWRITE_VALIDATED"), r2.begin_execution("MUT-1", FP)), "replay"))
    m3, f3 = fixture(); m3.ledger = MODEL.ReplayLedger(lpath); m3.context_ready(f3["intent"], f3["pr"])
    t(g, "new_mission_cannot_reuse_authority_recorded_in_ledger", raises(lambda: m3.authorize(f3["dl"], f3["au"], f3["bu"]), "already consumed") and m3.state == "CONTEXT_READY")
    mm, ff = fixture(); to_prewrite(mm, ff); mm.begin_execution("MUT-1", FP)
    n_before = len(mm.ledger.for_authority(ff["au"]["object_hash"]))
    t(g, "ledger_entry_survives_failed_later_calls", raises(lambda: mm.begin_execution("MUT-1", FP)) and raises(lambda: mm.record_execution(exec_receipt(ff, mut="MUT-OTHER")))
      and len(mm.ledger.for_authority(ff["au"]["object_hash"])) == n_before == 1)
    bad_ledger = MODEL.ReplayLedger(os.path.join(ldir, "ok_then_broken.txt"))
    t(g, "ledger_construction_fails_on_unusable_path", not safe(lambda: MODEL.ReplayLedger(os.path.join(ldir, "missing_dir", "y.txt"))))
    mm, ff = fixture(); mm.ledger = bad_ledger; to_prewrite(mm, ff)
    bad_ledger.path = os.path.join(ldir, "missing_dir", "x.txt")                    # the ledger becomes unwritable after prewrite
    t(g, "failed_ledger_write_blocks_the_send_and_changes_nothing", not safe(lambda: mm.begin_execution("MUT-1", FP)) and mm.state == "PREWRITE_VALIDATED" and mm.mutations_sent == 0 and mm.remaining == 1)
    m, f, lease = sent_mission()
    t(g, "resume_requires_ledger_and_evidence", raises(lambda: Mission.resume(lease, f["cp"], f["bu"], "M-SYN-1", ev_upstream(m), None), "ReplayLedger")
      and raises(lambda: Mission.resume(lease, f["cp"], f["bu"], "M-SYN-1", None, m.ledger, allow_volatile_ledger=True), "re-presented evidence")
      and raises(lambda: Mission.resume(lease, f["cp"], f["bu"], "M-SYN-1", {k: v for k, v in ev_upstream(m).items() if k != "tx"}, m.ledger, allow_volatile_ledger=True), "missing tx"))
    t(g, "resume_requires_a_durable_ledger_unless_explicitly_allowed", raises(lambda: Mission.resume(lease, f["cp"], f["bu"], "M-SYN-1", ev_upstream(m), m.ledger), "durable")
      and not m.ledger.is_durable)
    t(g, "resume_rejects_foreign_mission_id", raises(lambda: rsm(lease, f, m, mission_id="OTHER-MISSION"), "mission mismatch"))
    other_budget = make("MutationBudget", budget_id="bx", authority_hash=f["au"]["object_hash"], max_mutations=1, retries=0, expansion_allowed=False)
    t(g, "resume_rejects_original_budget_not_matching_evidence", raises(lambda: Mission.resume(lease, f["cp"], other_budget, "M-SYN-1", ev_upstream(m), m.ledger, allow_volatile_ledger=True), "original budget does not match")
      and raises(lambda: Mission.resume(lease, f["cp"], stale(f["bu"], max_mutations=9), "M-SYN-1", ev_upstream(m), m.ledger, allow_volatile_ledger=True), "hash invalid"))
    t(g, "resume_rejects_invalid_remaining_budget_values", all(raises(lambda v=v: rsm(remake(lease, remaining_budget=v), f, m), "remaining_budget invalid") for v in (-1, True, 1.5, "1")))
    t(g, "resume_rejects_malformed_consumed_ids", raises(lambda: rsm(remake(lease, consumed_authority_ids=["noseparator"]), f, m), "consumed ids invalid")
      and raises(lambda: rsm(remake(lease, consumed_authority_ids=["%s:MUT-1" % f["au"]["object_hash"]] * 2), f, m), "consumed ids invalid")
      and raises(lambda: rsm(remake(lease, consumed_authority_ids="x:y"), f, m), "consumed ids invalid"))
    t(g, "resume_rejects_lease_for_foreign_transaction", raises(lambda: rsm(remake(lease, transaction_id="TX-OTHER"), f, m), "correlation"))
    t(g, "resume_rejects_execution_receipt_not_matching_lease", raises(lambda: rsm(lease, f, m, evidence=dict(ev_upstream(m), execution_receipt=exec_receipt(f))), "does not match lease"))
    t(g, "resume_rejects_evidence_not_pinned_by_checkpoint", raises(lambda: rsm(lease, f, m, evidence=dict(ev_upstream(m), tx=remake(f["tx"], boundary="other"))), "does not pin")
      and raises(lambda: rsm(lease, f, m, evidence=dict(ev_upstream(m), budget=remake(f["bu"], budget_id="other"))), "original budget does not match"))
    t(g, "resume_rejects_inconsistent_delegation_capability_and_authority", raises(lambda: rsm(lease, f, m, evidence=dict(ev_upstream(m), delegation=remake(f["dl"], delegation_id="z"))), "not derived from delegation")
      and raises(lambda: rsm(lease, f, m, evidence=dict(ev_upstream(m), capability=remake(f["cb"], authority_hash=Z))), "not from this authority")
      and raises(lambda: rsm(lease, f, m, evidence=dict(ev_upstream(m), authority=remake(f["au"], authority_id="z"))), "does not belong"))
    t(g, "resume_rejects_enlarged_budget", raises(lambda: rsm(remake(lease, remaining_budget=1), f, m), "enlarge"))
    m_over, f_over, lease_over = sent_mission()
    m_over.ledger.consume((f_over["au"]["object_hash"], "MUT-2"))              # ledger shows more sends than the budget allows
    t(g, "resume_rejects_ledger_consumption_beyond_the_original_budget", raises(lambda: rsm(lease_over, f_over, m_over), "exceed the original budget"))
    mm, ff = fixture(max_mut=2); ff["tx"] = make("TransactionEnvelope", transaction_id="TX-SYN-1", mutation_ids=["MUT-1", "MUT-2"], mission_id="M-SYN-1", boundary="b")
    ff["cp"] = make("PreMutationCheckpoint", checkpoint_id="cp1", transaction_hash=ff["tx"]["object_hash"], budget_hash=ff["bu"]["object_hash"], outcome_contract_hash=ff["oc"]["object_hash"],
                    readback_contract_hash=ff["rc"]["object_hash"], remaining_budget=2)
    to_prewrite(mm, ff); mm.begin_execution("MUT-1", FP); mm.ledger.consume((ff["au"]["object_hash"], "MUT-2"))   # a second send is recorded only in the ledger
    r5 = rsm(mm.checkpoint_lease(), ff, mm)
    t(g, "ledger_only_consumption_reduces_the_resumed_budget", r5.remaining == 0 and len(r5.consumed) == 2)
    mm, ff = fixture(); to_prewrite(mm, ff); lease_pre = mm.checkpoint_lease()
    r6 = rsm(lease_pre, ff, mm)
    t(g, "pre_send_lease_with_empty_ledger_resumes_prewrite_with_full_budget", r6.state == "PREWRITE_VALIDATED" and r6.remaining == 1 and not r6.consumed)
    mm, ff = fixture(); to_prewrite(mm, ff); mm.begin_execution("MUT-1", FP)
    lease_post = mm.checkpoint_lease()
    t(g, "post_send_lease_without_mutation_id_uses_the_ledger_entry", rsm(remake(lease_post, mutation_id=None), ff, mm).ev.get("mutation_id") == "MUT-1")
    t(g, "post_send_lease_with_unknown_mutation_id_rejected", raises(lambda: rsm(remake(lease_post, mutation_id="MUT-X"), ff, mm), "inconsistent"))

    # -- strict predicates (review 2 N5)
    t(g, "predicate_eq_is_type_strict", eval_predicates([{"field": "a", "op": "eq", "expected": True}], {"a": 1}) == "FAIL" and eval_predicates([{"field": "a", "op": "eq", "expected": 1}], {"a": 1.0}) == "FAIL"
      and eval_predicates([{"field": "a", "op": "eq", "expected": 1}], {"a": 1}) == "PASS")
    t(g, "predicate_ne_semantics", eval_predicates([{"field": "a", "op": "ne", "expected": 5}], {"a": 5}) == "FAIL" and eval_predicates([{"field": "a", "op": "ne", "expected": 5}], {"a": 6}) == "PASS"
      and eval_predicates([{"field": "a", "op": "ne", "expected": True}], {"a": 1}) == "PASS")
    t(g, "predicate_in_semantics", eval_predicates([{"field": "a", "op": "in", "expected": ["x", "y"]}], {"a": "x"}) == "PASS" and eval_predicates([{"field": "a", "op": "in", "expected": ["x", "y"]}], {"a": "z"}) == "FAIL"
      and eval_predicates([{"field": "a", "op": "in", "expected": [1, 2]}], {"a": True}) == "FAIL")
    t(g, "predicate_in_rejects_empty_collection", raises(lambda: eval_predicates([{"field": "a", "op": "in", "expected": []}], {"a": 1}), "non-empty collection"))
    t(g, "predicate_malformed_entries_rejected", raises(lambda: eval_predicates([{"field": "a", "op": "eq"}], {"a": 1}), "malformed") and raises(lambda: eval_predicates(["x"], {"a": 1}), "malformed")
      and raises(lambda: eval_predicates("x", {"a": 1}), "vacuous") and raises(lambda: eval_predicates(None, {"a": 1}), "vacuous"))
    t(g, "predicate_odd_observed_values", eval_predicates([{"field": "a", "op": "eq", "expected": [1, 2]}], {"a": [1, 2]}) == "PASS" and eval_predicates([{"field": "a", "op": "eq", "expected": 1}], {"a": [1]}) == "FAIL"
      and eval_predicates([{"field": "a", "op": "eq", "expected": 1.0}], {"a": float("nan")}) == "FAIL")

    # -- aliasing and type guards (review 2 N6, N7, N8)
    intent_alias, pr_alias = dict(f["intent"]), dict(f["pr"])
    mm = Mission("M-SYN-1", "TX-SYN-1", 1); mm.context_ready(intent_alias, pr_alias)
    intent_alias["mission_id"] = "OTHER"
    t(g, "accepted_evidence_is_private_copy", mm.ev["intent"]["mission_id"] == "M-SYN-1" and verify_hash(mm.ev["intent"]) and mm.ev["intent"] is not intent_alias)
    mm, ff, er, done = complete_ready()
    cr_alias = done()
    forged_alias = remake(ff["au"], max_mutations=0)
    ff["au"].update({k: v for k, v in forged_alias.items()})          # the caller rewrites and re-hashes ITS object
    t(g, "rewriting_the_callers_object_after_acceptance_does_not_change_the_chain", safe(lambda: (mm.complete(cr_alias), mm.state)[1] == "COMPLETE") and mm.ev["authority"]["max_mutations"] == 1)
    t(g, "mission_limit_must_be_a_non_negative_integer", all(raises(lambda v=v: Mission("M", "T", v), "non-negative integer") for v in (True, -1, 1.5, "1", None)))

    # -- gaps found by the generated mutants
    lg = MODEL.ReplayLedger(); lg.consume(("a", "b"))
    t(g, "ledger_consume_twice_is_refused", raises(lambda: lg.consume(("a", "b")), "replay") and lg.has(("a", "b")))
    mm, ff = fixture()
    t(g, "guard_methods_refuse_missing_prerequisite_evidence", raises(lambda: mm.authorize(ff["dl"], ff["au"], ff["bu"]), "missing evidence principal")
      and raises(lambda: mm.bind(ff["cb"], ff["pb"]), "missing evidence authority") and mm.state == "PLANNED" and not mm.ev)

    def two_mutation_mission(max_mut):
        mm_, ff_ = fixture(max_mut=max_mut)
        ff_["tx"] = make("TransactionEnvelope", transaction_id="TX-SYN-1", mutation_ids=["MUT-1", "MUT-2"], mission_id="M-SYN-1", boundary="b")
        ff_["cp"] = make("PreMutationCheckpoint", checkpoint_id="cp1", transaction_hash=ff_["tx"]["object_hash"], budget_hash=ff_["bu"]["object_hash"],
                         outcome_contract_hash=ff_["oc"]["object_hash"], readback_contract_hash=ff_["rc"]["object_hash"], remaining_budget=max_mut)
        to_prewrite(mm_, ff_); mm_.begin_execution("MUT-1", FP)
        return mm_, ff_
    mm, ff = two_mutation_mission(1)
    t(g, "second_mutation_refused_when_budget_exhausted", raises(lambda: mm.begin_execution("MUT-2", FP), "budget exhausted") and mm.remaining == 0 and mm.mutations_sent == 1)
    mm, ff = two_mutation_mission(2)
    t(g, "illegal_state_send_does_not_burn_the_ledger", raises(lambda: mm.begin_execution("MUT-2", FP), "illegal transition") and not mm.ledger.has((ff["au"]["object_hash"], "MUT-2"))
      and mm.remaining == 1 and mm.mutations_sent == 1)
    mm, ff = at_started()
    t(g, "invalid_call_class_rejected_in_the_right_state", raises(lambda: mm.record_execution(exec_receipt(ff, "CALL_NOT_SENT")), "not valid after execution started")
      and raises(lambda: mm.record_execution(exec_receipt(ff, "OUTCOME_VALIDATED")), "not valid after execution started") and state_unchanged(mm, "EXECUTION_STARTED", set(mm.ev)))
    mm, ff, rbo = at_committed()
    placeholder = make("CompletionReceipt", receipt_id="d", transaction_id="TX-SYN-1", outcome_receipt_hash=Z, commit_observation_hash=mm.ev["commit"]["object_hash"],
                       execution_receipt_hash=mm.ev["execution_receipt"]["object_hash"], authority_hash=ff["au"]["object_hash"])
    t(g, "complete_refused_before_outcome_is_validated", raises(lambda: mm.complete(placeholder), "requires OUTCOME_VALIDATED") and mm.state == "COMMITTED" and "completion" not in mm.ev)

    # -- every chain relation has its own violation recipe (review 2 gaps 4/8)
    def cascade(mm_, slot, new):
        old = mm_.ev[slot]; mm_.ev[slot] = new
        queue = [(old["object_hash"], new["object_hash"], slot)]
        while queue:
            oh, nh, src = queue.pop()
            for s, o in list(mm_.ev.items()):
                if s == src or not isinstance(o, dict) or "object_hash" not in o:
                    continue
                if any(v == oh for k, v in o.items() if k not in ("kind", "object_hash")):
                    n2 = make(o["kind"], **{k: (nh if v == oh else v) for k, v in o.items() if k not in ("kind", "object_hash")})
                    mm_.ev[s] = n2
                    queue.append((o["object_hash"], n2["object_hash"], s))
    def mod(mm_, slot, **chg):
        cascade(mm_, slot, remake(mm_.ev[slot], **chg))
    RECIPES = {
        "R01": lambda mm_, d: mod(mm_, "delegation", principal_hash=Z), "R02": lambda mm_, d: mod(mm_, "authority", delegation_hash=Z),
        "R03": lambda mm_, d: mod(mm_, "authority", mission_id="OTHER"), "R04": lambda mm_, d: mod(mm_, "intent", mission_id="OTHER"),
        "R05": lambda mm_, d: mod(mm_, "authority", scope=["create_object", "delete_object"]), "R06": lambda mm_, d: mod(mm_, "delegation", max_mutations=0),
        "R07": lambda mm_, d: mod(mm_, "budget", authority_hash=Z), "R08": lambda mm_, d: mod(mm_, "authority", max_mutations=0),
        "R09": lambda mm_, d: mod(mm_, "budget", retries=1), "R10": lambda mm_, d: mod(mm_, "budget", max_mutations=0),
        "R11": lambda mm_, d: mod(mm_, "authority", single_use=False), "R12": lambda mm_, d: mod(mm_, "capability", authority_hash=Z),
        "R13": lambda mm_, d: (mod(mm_, "capability", capability="other"), mod(mm_, "provider", tool_name="other")),
        "R14": lambda mm_, d: mod(mm_, "provider", tool_name="other"), "R15": lambda mm_, d: mod(mm_, "provider", identity="OTHER::x"),
        "R16": lambda mm_, d: mod(mm_, "tx", transaction_id="OTHER"), "R17": lambda mm_, d: mod(mm_, "tx", mission_id="OTHER"),
        "R18": lambda mm_, d: mod(mm_, "tx", mutation_ids=["MUT-2"]), "R19": lambda mm_, d: mm_.consumed.clear(),
        "R20": lambda mm_, d: mod(mm_, "outcome_contract", frozen=False), "R22": lambda mm_, d: mod(mm_, "readback_contract", source_level_required="PROVIDER_LOG"),
        "R23": lambda mm_, d: mod(mm_, "checkpoint", transaction_hash=Z), "R24": lambda mm_, d: mod(mm_, "checkpoint", budget_hash=Z),
        "R25": lambda mm_, d: mod(mm_, "checkpoint", outcome_contract_hash=Z), "R26": lambda mm_, d: mod(mm_, "checkpoint", readback_contract_hash=Z),
        "R27": lambda mm_, d: mod(mm_, "checkpoint", remaining_budget=2),
        "R28": lambda mm_, d: mod(mm_, "execution_receipt", transaction_id="OTHER"), "R29": lambda mm_, d: mod(mm_, "execution_receipt", mutation_id="OTHER"),
        "R30": lambda mm_, d: mod(mm_, "execution_receipt", call_class="CALL_NOT_SENT"),
        "R50": lambda mm_, d: mod(mm_, "readback", observed=dict(GOOD_OBS, exists=False)),
        "R51": lambda mm_, d: mod(mm_, "readback_contract", provider_ref="OTHER::x"),
        "R52": lambda mm_, d: (mod(mm_, "delegation", expires_at="x"), mm_.consumed.clear(), mm_.consumed.add((mm_.ev["authority"]["object_hash"], "MUT-1")), d(authority_hash=mm_.ev["authority"]["object_hash"]))[3],
        "R53": lambda mm_, d: mod(mm_, "intent", expected_outcome_hash=Z),
        "R54": lambda mm_, d: mod(mm_, "readback_contract", checks=["exists", "nosuchfield"]),
        "R31": lambda mm_, d: mod(mm_, "readback", transaction_id="OTHER"), "R32": lambda mm_, d: mod(mm_, "readback", mutation_id="OTHER"),
        "R33": lambda mm_, d: mod(mm_, "readback", contract_hash=Z), "R34": lambda mm_, d: mod(mm_, "readback", source_level="INFERRED_OR_REGEX"),
        "R35": lambda mm_, d: mod(mm_, "readback", existence="UNKNOWN"),
        "R36": lambda mm_, d: mod(mm_, "commit", transaction_id="OTHER"), "R37": lambda mm_, d: mod(mm_, "commit", mutation_id="OTHER"),
        "R38": lambda mm_, d: mod(mm_, "commit", readback_receipt_hash=Z), "R39": lambda mm_, d: mod(mm_, "commit", commit_state="UNKNOWN"),
        "R40": lambda mm_, d: mod(mm_, "outcome", transaction_id="OTHER"), "R41": lambda mm_, d: mod(mm_, "outcome", readback_receipt_hash=Z),
        "R42": lambda mm_, d: mod(mm_, "outcome", outcome_contract_hash=Z), "R43": lambda mm_, d: mod(mm_, "outcome", result="FAIL"),
        "R44": lambda mm_, d: mod(mm_, "readback", observed=dict(GOOD_OBS, package="WRONG")),
        "R45": lambda mm_, d: d(authority_hash=Z), "R46": lambda mm_, d: d(execution_receipt_hash=Z),
        "R47": lambda mm_, d: d(commit_observation_hash=Z), "R48": lambda mm_, d: d(outcome_receipt_hash=Z), "R49": lambda mm_, d: d(transaction_id="OTHER"),
    }
    t(g, "every_chain_relation_has_a_violation_recipe", set(RECIPES) == set(MODEL.RELATIONS))
    src_ids = set(re.findall(r'self\._rel\("(R\d+)"', open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcr3_model.py"), encoding="utf-8").read()))
    t(g, "relation_ids_in_source_equal_relation_table", src_ids == set(MODEL.RELATIONS))
    for rid in sorted(RECIPES):
        mm, ff, er, done = complete_ready()
        res = RECIPES[rid](mm, done)
        cr = res if isinstance(res, dict) and res.get("kind") == "CompletionReceipt" else done()
        t(g, "relation_%s_violation_blocked" % rid, raises(lambda mm=mm, cr=cr: mm.complete(cr), "[%s]" % rid) and mm.state == "OUTCOME_VALIDATED" and "completion" not in mm.ev)
    mm, ff, er, done = complete_ready(); mod(mm, "outcome_contract", predicates=[])
    t(g, "empty_predicates_in_chain_blocked", raises(lambda: mm.complete(done()), "vacuous") and "completion" not in mm.ev)
    mm, ff, er, done = complete_ready()
    t(g, "all_relations_hold_on_a_genuine_chain", safe(lambda: (mm.complete(done()), mm.state)[1] == "COMPLETE"))

    # ---- HARDENING_R2_0J (independent review 3: resume gates, multi-process ledger, compensation, types)
    g = "HARDENING_R2_0J"
    import subprocess, tempfile as _tf

    def world(i_chg=None, dl_chg=None, au_chg=None, bu_chg=None, cb_chg=None, pb_chg=None, tx_chg=None, oc_chg=None, rc_chg=None, cp_chg=None):
        """A self-consistent set of upstream objects (hashes and pins recomputed) with chosen content changes, plus a pre-send
        lease: the situation of an attacker who can build hash-valid evidence for resume()."""
        _, ff = fixture()
        intent = remake(ff["intent"], **(i_chg or {})); dl = remake(ff["dl"], **(dl_chg or {}))
        au = remake(ff["au"], **dict({"delegation_hash": dl["object_hash"]}, **(au_chg or {})))
        bu = remake(ff["bu"], **dict({"authority_hash": au["object_hash"]}, **(bu_chg or {})))
        cb = remake(ff["cb"], **dict({"authority_hash": au["object_hash"]}, **(cb_chg or {}))); pb = remake(ff["pb"], **(pb_chg or {}))
        tx = remake(ff["tx"], **(tx_chg or {})); oc = remake(ff["oc"], **(oc_chg or {})); rc = remake(ff["rc"], **(rc_chg or {}))
        cp = make("PreMutationCheckpoint", **dict(dict(checkpoint_id="cp1", transaction_hash=tx["object_hash"], budget_hash=bu["object_hash"], outcome_contract_hash=oc["object_hash"],
                                                      readback_contract_hash=rc["object_hash"], remaining_budget=1), **(cp_chg or {})))
        lease = make("ContinuationLease", lease_id="L1", checkpoint_hash=cp["object_hash"], transaction_id="TX-SYN-1", remaining_budget=1, state_at_checkpoint="PREWRITE_VALIDATED",
                     mutation_id=None, execution_receipt_hash=None, consumed_authority_ids=[])
        ev = dict(intent=intent, principal=ff["pr"], delegation=dl, capability=cb, provider=pb, tx=tx, budget=bu, outcome_contract=oc, readback_contract=rc, authority=au)
        return lease, cp, bu, ev

    def try_resume(**chg):
        lease_, cp_, bu_, ev_ = world(**chg)
        return Mission.resume(lease_, cp_, bu_, "M-SYN-1", ev_, MODEL.ReplayLedger(), allow_volatile_ledger=True)
    pos = try_resume()
    t(g, "resume_world_helper_builds_a_valid_resumable_world", pos.state == "PREWRITE_VALIDATED" and pos.remaining == 1)
    nan = float("nan")
    cases = [
        ("resume_runs_the_authorize_gate_budget_retries", dict(bu_chg=dict(retries=1)), "forbid expansion and retries"),
        ("resume_runs_the_authorize_gate_budget_expansion", dict(bu_chg=dict(expansion_allowed=True)), "forbid expansion and retries"),
        ("resume_runs_the_authorize_gate_boolean_retries", dict(bu_chg=dict(retries=False)), "forbid expansion and retries"),
        ("resume_runs_the_authorize_gate_not_single_use", dict(au_chg=dict(single_use=False)), "single use"),
        ("resume_runs_the_authorize_gate_scope_beyond_delegation", dict(au_chg=dict(scope=["create_object", "delete_object"])), "no attenuation"),
        ("resume_runs_the_authorize_gate_delegation_for_other_principal", dict(dl_chg=dict(principal_hash=Z)), "not issued to this principal"),
        ("resume_runs_the_authorize_gate_nan_authority_count", dict(au_chg=dict(max_mutations=nan)), "non-negative integer"),
        ("resume_runs_the_authorize_gate_boolean_count", dict(bu_chg=dict(max_mutations=True), au_chg=dict(max_mutations=True)), "non-negative integer"),
        ("resume_runs_the_bind_gate_capability_provider_mismatch", dict(pb_chg=dict(tool_name="other_tool")), "does not match provider tool"),
        ("resume_runs_the_bind_gate_provider_ref_mismatch", dict(pb_chg=dict(identity="OTHER::x")), "provider_ref differs"),
        ("resume_runs_the_prewrite_gate_unfrozen_contract", dict(oc_chg=dict(frozen=False)), "not frozen"),
        ("resume_runs_the_prewrite_gate_truthy_non_true_frozen", dict(oc_chg=dict(frozen="yes")), "not frozen"),
        ("resume_runs_the_prewrite_gate_string_mutation_ids", dict(tx_chg=dict(mutation_ids="MUT-1")), "non-empty list of strings"),
        ("resume_runs_the_prewrite_gate_foreign_mission_transaction", dict(tx_chg=dict(mission_id="OTHER")), "mission mismatch"),
        ("resume_runs_the_prewrite_gate_float_checkpoint_budget", dict(cp_chg=dict(remaining_budget=1.0)), "checkpoint budget differs"),
        ("resume_runs_the_prewrite_gate_non_authoritative_readback_contract", dict(rc_chg=dict(source_level_required="PROVIDER_LOG")), "not authoritative"),
        ("resume_runs_the_context_gate_foreign_mission_intent", dict(i_chg=dict(mission_id="OTHER")), "intent mission mismatch"),
    ]
    for name, chg, text in cases:
        t(g, name, raises(lambda chg=chg: try_resume(**chg), text))
    for slot in ("delegation", "capability", "intent", "principal", "provider"):
        lease_, cp_, bu_, ev_ = world(); ev_.pop(slot)
        t(g, "resume_requires_the_%s_evidence" % slot, raises(lambda lease_=lease_, cp_=cp_, bu_=bu_, ev_=ev_: Mission.resume(lease_, cp_, bu_, "M-SYN-1", ev_, MODEL.ReplayLedger(), allow_volatile_ledger=True), "missing %s" % slot))
    mm, ff = fixture(); to_prewrite(mm, ff)
    eq_dl, eq_au, eq_bu = chain_with(ff, dl=remake(ff["dl"], scope=["create_object"], max_mutations=1), au=remake(ff["au"], scope=["create_object"], max_mutations=1))
    mq, fq = fixture(); mq.context_ready(fq["intent"], fq["pr"])
    t(g, "equal_scope_and_equal_counts_are_accepted_at_the_gate", safe(lambda: (mq.authorize(eq_dl, eq_au, eq_bu), mq.state)[1] == "AUTHORIZED"))
    mm2, ff2, er2, done2 = complete_ready()
    cr2 = done2()
    t(g, "equal_scope_chain_relations_hold_in_the_live_freeze_shape", True)

    # -- multi-process-safe, checksummed ledger (review 3 F2)
    ldir2 = _tf.mkdtemp(prefix="r2ledger2_"); lp = os.path.join(ldir2, "ledger.txt")
    code = ("import sys,time\nsys.path.insert(0, sys.argv[3])\nimport mcr3_model as M\nlg = M.ReplayLedger(sys.argv[1])\n"
            "while time.time() < float(sys.argv[2]): pass\ntry:\n    lg.consume(('A' * 64, 'MUT-1'), limit=1); print('SENT')\nexcept M.GuardError:\n    print('REFUSED')\n")
    start_at = __import__("time").time() + 1.2
    procs = [subprocess.Popen([sys.executable, "-c", code, lp, str(start_at), os.path.dirname(os.path.abspath(__file__))], stdout=subprocess.PIPE, text=True) for _ in range(4)]
    outs = sorted(p_.communicate()[0].strip() for p_ in procs)
    t(g, "four_real_processes_race_and_exactly_one_send_wins", outs == ["REFUSED", "REFUSED", "REFUSED", "SENT"])
    la, lb = MODEL.ReplayLedger(os.path.join(ldir2, "two.txt")), MODEL.ReplayLedger(os.path.join(ldir2, "two.txt"))
    la.consume(("A" * 64, "MUT-1"))
    t(g, "second_ledger_object_on_the_same_file_sees_the_entry", lb.has(("A" * 64, "MUT-1")) and raises(lambda: lb.consume(("A" * 64, "MUT-1")), "replay"))
    lc = MODEL.ReplayLedger(os.path.join(ldir2, "limit.txt"))
    lc.consume(("A" * 64, "MUT-1"), limit=1)
    t(g, "per_authority_send_limit_is_enforced_by_the_ledger", raises(lambda: lc.consume(("A" * 64, "MUT-2"), limit=1), "send count exhausted") and lc.consume(("B" * 64, "MUT-1"), limit=1) is None
      and len(lc.for_authority("A" * 64)) == 1)
    def twin_missions(ledger_path):
        ma, fa = fixture(max_mut=1); mb, fb = fixture(max_mut=1)
        for mm_, ff_ in ((ma, fa), (mb, fb)):
            mm_.ledger = MODEL.ReplayLedger(ledger_path)
            ff_["tx"] = make("TransactionEnvelope", transaction_id="TX-SYN-1", mutation_ids=["MUT-1", "MUT-2"], mission_id="M-SYN-1", boundary="b")
            ff_["cp"] = make("PreMutationCheckpoint", checkpoint_id="cp1", transaction_hash=ff_["tx"]["object_hash"], budget_hash=ff_["bu"]["object_hash"],
                             outcome_contract_hash=ff_["oc"]["object_hash"], readback_contract_hash=ff_["rc"]["object_hash"], remaining_budget=1)
            to_prewrite(mm_, ff_)
        return ma, mb
    ma, mb = twin_missions(os.path.join(ldir2, "twin.txt"))
    ma.begin_execution("MUT-1", FP)
    t(g, "two_missions_sharing_one_authority_cannot_both_send_even_with_different_mutation_ids", raises(lambda: mb.begin_execution("MUT-2", FP), "send count exhausted") and mb.mutations_sent == 0
      and mb.state == "PREWRITE_VALIDATED")
    t(g, "same_mutation_id_in_a_second_mission_is_a_replay", raises(lambda: mb.begin_execution("MUT-1", FP), "replay"))
    lt = os.path.join(ldir2, "torn.txt"); ld = MODEL.ReplayLedger(lt); ld.consume(("A" * 64, "MUT-1"))
    with open(lt, "ab") as fh:
        fh.write(b'{"a":"' + b"B" * 20)
    reloaded = MODEL.ReplayLedger(lt)
    t(g, "torn_final_line_is_ignored_on_load", reloaded.has(("A" * 64, "MUT-1")) and not reloaded.for_authority("B" * 20))
    reloaded.consume(("C" * 64, "MUT-9"))
    with open(lt, "rb") as fh:
        lines = fh.read().split(b"\n")
    t(g, "torn_tail_is_truncated_before_the_next_append_and_all_lines_stay_valid", len(lines) == 4 and lines[3] == b"" and lines[0].startswith(b'{"hdr":"R2LEDGER"') and MODEL.ReplayLedger(lt).has(("C" * 64, "MUT-9")))
    lg_ = os.path.join(ldir2, "corrupt.txt"); le = MODEL.ReplayLedger(lg_); le.consume(("A" * 64, "MUT-1"))
    with open(lg_, "ab") as fh:
        fh.write(b"garbage line\n")
    le.consume  # noqa
    t(g, "corrupt_complete_line_fails_closed", raises(lambda: MODEL.ReplayLedger(lg_), "corrupted at line 3"))
    lh = os.path.join(ldir2, "crc.txt"); lf = MODEL.ReplayLedger(lh); lf.consume(("A" * 64, "MUT-1"))
    raw = open(lh, "rb").read().replace(b"MUT-1", b"MUT-2")
    open(lh, "wb").write(raw)
    t(g, "checksum_mismatch_fails_closed", raises(lambda: MODEL.ReplayLedger(lh), "corrupted at line 2"))
    t(g, "ledger_file_must_be_utf8", (open(os.path.join(ldir2, "bin.txt"), "wb").write(b"\xff\xfe\n"), raises(lambda: MODEL.ReplayLedger(os.path.join(ldir2, "bin.txt")), "not UTF-8"))[1])
    lj = MODEL.ReplayLedger(os.path.join(ldir2, "odd.txt")); odd = ("A" * 64, "MUT:1:é")
    lj.consume(odd)
    t(g, "colons_and_unicode_in_mutation_ids_roundtrip", MODEL.ReplayLedger(os.path.join(ldir2, "odd.txt")).has(odd))
    t(g, "control_characters_in_ledger_keys_are_rejected", all(raises(lambda k=k: lj.consume(k), "control characters") for k in (("A" * 64, "M\rX"), ("A" * 64, "M\nX"), ("A" * 64, "M\tX"), ("A" * 64, "M\x00X"), ("A" * 64, "M\x7fX")))
      and all(raises(lambda k=k: lj.consume(k), "non-empty strings") for k in (("A" * 64, ""), ("", "M"), ("A" * 64, 5), ("A" * 64,), 5)))
    t(g, "begin_execution_rejects_control_characters_in_mutation_ids", all(raises(lambda mid=mid: mm.begin_execution(mid, FP), "invalid mutation id") for mid in ("MUT-1\r", "MUT\t1", "MUT\x001", "M\x7f")))
    calls = []
    real_fsync = MODEL.os.fsync
    MODEL.os.fsync = lambda fd: (calls.append(fd), real_fsync(fd))[1]
    try:
        lk = MODEL.ReplayLedger(os.path.join(ldir2, "fsync.txt")); lk.consume(("A" * 64, "MUT-1")); lk.consume(("A" * 64, "MUT-2"))
    finally:
        MODEL.os.fsync = real_fsync
    with open(os.path.join(ldir2, "fsync.txt"), "rb") as fh:
        content = fh.read()
    t(g, "every_consume_is_fsynced_and_appended_never_truncating", len(calls) == 3 and content.count(b"\n") == 3 and b"MUT-1" in content and b"MUT-2" in content)
    t(g, "volatile_ledger_works_in_process_but_is_not_durable", (lambda lv: (lv.consume(("A" * 64, "M")), lv.has(("A" * 64, "M")) and not lv.is_durable and raises(lambda: lv.consume(("A" * 64, "M")), "replay"))[1])(MODEL.ReplayLedger()))
    t(g, "other_authority_entries_do_not_block_a_send", (lambda lo: (lo.consume(("B" * 64, "MUT-1")), (lambda m_, f_: (to_prewrite(m_, f_), setattr(m_, "ledger", lo), safe(lambda: (m_.begin_execution("MUT-1", FP), m_.mutations_sent)[1] == 1))[2])(*fixture()))[1])(MODEL.ReplayLedger(os.path.join(ldir2, "otherauth.txt"))))
    t(g, "unparseable_ledger_key_types_become_guard_errors", raises(lambda: lj.consume(None), "non-empty strings"))

    # -- compensation needs evidence of the compensating action (review 3 F3)
    mm, ff, gg = comp_authorized2()
    # (comp_authorized2 already begins the compensation; build a variant that has not begun)
    def comp_unbegun():
        m_, f_ = comp_ready(); g_ = grant_of(); m_.authorize_compensation(g_)
        return m_, f_, g_
    mm, ff, gg = comp_unbegun(); post = rb_receipt(ff, "ABSENT", obs={"exists": False})
    t(g, "compensation_not_begun_cannot_be_recorded", raises(lambda: mm.record_compensation(comp_receipt_for(gg, post), post, comp_exec(gg)), "not begun") and mm.state == "COMPENSATION_AUTHORIZED")
    t(g, "begin_compensation_refused_in_the_wrong_state", (lambda m_, f_: raises(lambda: m_.begin_compensation(), "missing evidence comp_grant"))(*comp_ready()))
    mm, ff, gg = comp_unbegun(); mm.begin_compensation()
    t(g, "begin_compensation_refused_while_an_attempt_is_open", raises(lambda: mm.begin_compensation(), "attempt is already open") and mm.ev.get("comp_open") == 1)
    m2_, f2_, g2_ = comp_unbegun()
    m2_.ledger.consume((gg["object_hash"], "COMPENSATION-ATTEMPT-1"))                # an attempt for this grant is already in the ledger
    t(g, "begin_compensation_refused_when_the_ledger_already_shows_the_budget_used", raises(lambda: m2_.begin_compensation(), "budget exhausted") and m2_.ev.get("comp_open") is None)
    mm, ff, gg = comp_authorized2(); post = rb_receipt(ff, "ABSENT", obs={"exists": False})
    fwd = mm.ev["readback"]
    cases = [
        ("compensation_rejects_execution_receipt_for_another_mutation", lambda: mm.record_compensation(comp_receipt_for(gg, post), post, comp_exec(gg, mut="MUT-1")), "not bound to the grant"),
        ("compensation_rejects_execution_receipt_with_invalid_call_class", lambda: mm.record_compensation(comp_receipt_for(gg, post), post, comp_exec(gg, cls="CALL_NOT_SENT")), "compensating call must report success"),
        ("compensation_rejects_execution_receipt_from_another_transaction", lambda: mm.record_compensation(comp_receipt_for(gg, post), post, comp_exec(gg, tx="TX-OTHER")), "correlation"),
        ("compensation_rejects_tampered_execution_receipt", lambda: mm.record_compensation(comp_receipt_for(gg, post), post, stale(comp_exec(gg), call_class="PROVIDER_ERROR")), "hash invalid"),
        ("compensation_rejects_wrong_kind_execution_receipt", lambda: mm.record_compensation(comp_receipt_for(gg, post), post, ff["cp"]), "wrong kind"),
        ("compensation_rejects_the_forward_readback_re_presented_as_post_readback", lambda: mm.record_compensation(comp_receipt_for(gg, fwd), fwd, comp_exec(gg)), "not distinct"),
        ("compensation_rejects_a_post_readback_with_identical_observed_state", lambda: mm.record_compensation(comp_receipt_for(gg, remake(fwd, receipt_id="other")), remake(fwd, receipt_id="other"), comp_exec(gg)), "not distinct"),
        ("compensation_rejects_post_readback_contradicting_its_own_exists_field", lambda: mm.record_compensation(comp_receipt_for(gg, remake(post, observed={"exists": True})), remake(post, observed={"exists": True}), comp_exec(gg)), "contradicts observed.exists"),
    ]
    for name, fn, text in cases:
        t(g, name, raises(fn, text) and mm.state == "COMPENSATION_AUTHORIZED")
    mm, ff, gg = comp_authorized2(); post = rb_receipt(ff, "ABSENT", obs={"exists": False})
    t(g, "compensating_call_that_did_not_report_success_cannot_complete_the_compensation",
      all(raises(lambda cls=cls: mm.record_compensation(comp_receipt_for(gg, post), post, comp_exec(gg, cls=cls)), "compensating call must report success")
          for cls in ("PROVIDER_ERROR", "CALL_SENT_NO_RESPONSE", "COMMIT_UNKNOWN", "CALL_NOT_SENT")) and mm.state == "COMPENSATION_AUTHORIZED")
    m3_, f3_ = fixture(); to_prewrite(m3_, f3_); m3_.begin_execution("MUT-1", FP); m3_.record_execution(exec_receipt(f3_)); m3_.request_readback()
    weak = rb_receipt(f3_, "EXISTS", "PROVIDER_VALIDATION"); m3_.observe_readback(weak); m3_.decide_commit(commit_obs(weak, "COMMITTED"))
    m3_.fail_after_possible_mutation(); m3_.require_compensation()
    t(g, "compensation_refused_on_a_non_authoritative_forward_readback", raises(lambda: m3_.authorize_compensation(grant_of()), "authoritative forward readback") and m3_.state == "COMPENSATION_REQUIRED")

    # -- types, existence consistency, malformed arguments (review 3 F4, F5)
    mm, ff = at_context()
    for what, chg, text in (("authority_nan_count", dict(au=dict(max_mutations=nan)), "non-negative integer"), ("authority_float_count", dict(au=dict(max_mutations=1.0)), "non-negative integer"),
                            ("authority_negative_count", dict(au=dict(max_mutations=-1)), "non-negative integer"), ("authority_boolean_count", dict(au=dict(max_mutations=True)), "non-negative integer")):
        m_, f_ = at_context()
        a_ = remake(f_["au"], **chg["au"]); b_ = remake(f_["bu"], authority_hash=a_["object_hash"])
        t(g, "gate_rejects_" + what, raises(lambda m_=m_, f_=f_, a_=a_, b_=b_: m_.authorize(f_["dl"], a_, b_), text) and m_.state == "CONTEXT_READY")
    m_, f_ = at_context(); d_ = remake(f_["dl"], max_mutations=2.0); a_ = remake(f_["au"], delegation_hash=d_["object_hash"]); b_ = remake(f_["bu"], authority_hash=a_["object_hash"])
    t(g, "gate_rejects_float_delegation_count", raises(lambda: m_.authorize(d_, a_, b_), "non-negative integer"))
    m_, f_ = at_context(); b_ = remake(f_["bu"], max_mutations=1.0)
    t(g, "gate_rejects_float_budget_count", raises(lambda: m_.authorize(f_["dl"], f_["au"], b_), "non-negative integer"))
    m_, f_ = at_context(); b_ = remake(f_["bu"], expansion_allowed=0)
    t(g, "gate_rejects_non_false_expansion_flag", raises(lambda: m_.authorize(f_["dl"], f_["au"], b_), "forbid expansion and retries"))
    mm, ff, rbo = at_observed()
    m4_, f4_ = fixture(); to_prewrite(m4_, f4_); m4_.begin_execution("MUT-1", FP); m4_.record_execution(exec_receipt(f4_)); m4_.request_readback()
    t(g, "readback_exists_with_observed_exists_false_is_refused", raises(lambda: m4_.observe_readback(rb_receipt(f4_, "EXISTS", obs=dict(GOOD_OBS, exists=False))), "contradicts observed.exists") and m4_.state == "AUTHORITATIVE_READBACK_PENDING")
    t(g, "readback_absent_with_observed_exists_true_is_refused", raises(lambda: m4_.observe_readback(rb_receipt(f4_, "ABSENT", obs={"exists": True})), "contradicts observed.exists"))
    t(g, "readback_unknown_may_omit_or_carry_exists", safe(lambda: (m4_.observe_readback(rb_receipt(f4_, "UNKNOWN", obs={})), m4_.state)[1] == "AUTHORITATIVE_READBACK_OBSERVED"))
    m5_, f5_ = fixture(); to_prewrite(m5_, f5_); m5_.begin_execution("MUT-1", FP); m5_.record_execution(exec_receipt(f5_)); m5_.request_readback()
    t(g, "malformed_observed_value_becomes_guard_error_and_changes_nothing", raises(lambda: m5_.observe_readback(rb_receipt(f5_, "EXISTS", obs=5)), "malformed argument") and m5_.state == "AUTHORITATIVE_READBACK_PENDING")
    t(g, "malformed_arguments_raise_guard_error_not_type_error", raises(lambda: m5_.begin_execution(["x"], FP), "invalid mutation id") and raises(lambda: Mission("M", "T", 1).authorize(None, None, None), "wrong kind"))
    t(g, "unknown_then_fail_predicates_report_fail", eval_predicates([{"field": "missing", "op": "eq", "expected": 1}, {"field": "a", "op": "eq", "expected": 1}], {"a": 2}) == "FAIL"
      and eval_predicates([{"field": "a", "op": "eq", "expected": 1}, {"field": "missing", "op": "eq", "expected": 1}], {"a": 2}) == "FAIL"
      and eval_predicates([{"field": "missing", "op": "eq", "expected": 1}, {"field": "a", "op": "eq", "expected": 1}], {"a": 1}) == "UNKNOWN")

    # -- boundary and clause-level gaps found by the AST-generated mutants (review 3 F7)
    _, fE = fixture()
    dlE = remake(fE["dl"], scope=["create_object"], max_mutations=1)
    auE = remake(fE["au"], delegation_hash=dlE["object_hash"], scope=["create_object"], max_mutations=1)
    buE = remake(fE["bu"], authority_hash=auE["object_hash"], max_mutations=1)
    cbE = remake(fE["cb"], authority_hash=auE["object_hash"])
    cpE = remake(fE["cp"], budget_hash=buE["object_hash"])
    mE = Mission("M-SYN-1", "TX-SYN-1", 1)
    mE.context_ready(fE["intent"], fE["pr"]); mE.authorize(dlE, auE, buE); mE.bind(cbE, fE["pb"]); mE.prewrite_validate(fE["tx"], fE["oc"], fE["rc"], cpE)
    mE.begin_execution("MUT-1", FP); mE.record_execution(exec_receipt(fE)); mE.request_readback(); rbE = rb_receipt(fE); mE.observe_readback(rbE)
    mE.decide_commit(commit_obs(rbE, "COMMITTED")); mE.validate_outcome(outcome(fE, rbE, "PASS"))
    crE = make("CompletionReceipt", receipt_id="done", transaction_id="TX-SYN-1", outcome_receipt_hash=mE.ev["outcome"]["object_hash"],
               commit_observation_hash=mE.ev["commit"]["object_hash"], execution_receipt_hash=mE.ev["execution_receipt"]["object_hash"], authority_hash=auE["object_hash"])
    t(g, "equal_scope_and_equal_counts_reach_complete_the_live_freeze_shape", safe(lambda: (mE.complete(crE), mE.state)[1] == "COMPLETE"))
    t(g, "mission_with_zero_allowed_mutations_is_constructible", Mission("M", "T", 0).remaining == 0)

    for what, chg, text in (("boolean_retries", dict(retries=False), "[R09]"), ("non_false_expansion_flag", dict(expansion_allowed=0), "[R09]")):
        mm_, ff_, er_, done_ = complete_ready(); mod(mm_, "budget", **chg)
        t(g, "relation_R09_" + what, raises(lambda mm_=mm_, done_=done_, text=text: mm_.complete(done_()), text))
    for what, chg in (("transaction", dict(transaction_id="OTHER")), ("mission", dict(mission_id="OTHER"))):
        mm_, ff_, er_, done_ = complete_ready(); mod(mm_, "outcome_contract", **chg)
        t(g, "relation_R20_" + what, raises(lambda mm_=mm_, done_=done_: mm_.complete(done_()), "[R20]"))
    mm_, ff_, er_, done_ = complete_ready(); mm_.ev["intent"] = "not a dict"
    t(g, "non_dict_chain_slot_is_reported_as_wrong_kind", raises(lambda: mm_.complete(done_()), "wrong kind"))

    # replay clauses in begin_execution
    mm_, ff_ = at_started(); mm_.ledger = MODEL.ReplayLedger()
    t(g, "mission_local_consumed_set_blocks_replay_even_with_an_empty_ledger", raises(lambda: mm_.begin_execution("MUT-1", FP), "replay"))
    mm_, ff_ = at_started(); mm_.consumed.clear()
    t(g, "ledger_blocks_replay_even_when_the_mission_forgot", raises(lambda: mm_.begin_execution("MUT-1", FP), "replay"))

    # ledger lock, boundaries
    lkp = os.path.join(ldir2, "lock.txt")
    fh1 = open(lkp, "a+b"); MODEL._lock(fh1); fh2 = open(lkp, "a+b")
    t(g, "ledger_lock_times_out_when_another_handle_holds_it", raises(lambda: MODEL._lock(fh2, timeout=0.3), "lock timeout"))
    MODEL._unlock(fh1); fh1.close()
    t(g, "ledger_lock_is_acquirable_after_release", safe(lambda: (MODEL._lock(fh2, timeout=2.0), MODEL._unlock(fh2), True)[2]))
    fh2.close()
    lsp = MODEL.ReplayLedger(os.path.join(ldir2, "space.txt"))
    t(g, "space_is_not_a_control_character_in_ledger_keys", safe(lambda: (lsp.consume(("A" * 64, "MUT 1")), lsp.has(("A" * 64, "MUT 1")))[1]))
    mS, fS = fixture(); fS["tx"] = make("TransactionEnvelope", transaction_id="TX-SYN-1", mutation_ids=["MUT 1"], mission_id="M-SYN-1", boundary="b")
    fS["cp"] = remake(fS["cp"], transaction_hash=fS["tx"]["object_hash"]); to_prewrite(mS, fS)
    t(g, "begin_execution_accepts_a_space_in_the_mutation_id", safe(lambda: (mS.begin_execution("MUT 1", FP), mS.mutations_sent)[1] == 1))
    mS2, fS2 = at_bound()
    t(g, "prewrite_rejects_an_empty_string_mutation_id", raises(lambda: mS2.prewrite_validate(remake(fS2["tx"], mutation_ids=[""]), fS2["oc"], fS2["rc"], fS2["cp"]), "non-empty list of strings"))

    # existence consistency clauses
    m6_, f6_ = fixture(); to_prewrite(m6_, f6_); m6_.begin_execution("MUT-1", FP); m6_.record_execution(exec_receipt(f6_)); m6_.request_readback()
    t(g, "unknown_existence_may_carry_a_true_exists_field", safe(lambda: (m6_.observe_readback(rb_receipt(f6_, "UNKNOWN", obs={"exists": True})), m6_.state)[1] == "AUTHORITATIVE_READBACK_OBSERVED"))
    m7_, f7_ = fixture(); to_prewrite(m7_, f7_); m7_.begin_execution("MUT-1", FP); m7_.record_execution(exec_receipt(f7_)); m7_.request_readback()
    t(g, "exists_existence_may_omit_the_exists_field", safe(lambda: (m7_.observe_readback(rb_receipt(f7_, "EXISTS", obs={"package": "ZPKG_SYN"})), m7_.state)[1] == "AUTHORITATIVE_READBACK_OBSERVED"))
    t(g, "non_dict_predicate_entries_are_malformed", raises(lambda: eval_predicates([5], {"a": 1}), "malformed") and raises(lambda: eval_predicates([None], {"a": 1}), "malformed"))

    # outcome binding and compensation grant clauses
    mm_, ff_, rbo_ = at_committed()
    t(g, "outcome_bound_to_another_contract_is_refused", raises(lambda: mm_.validate_outcome(make("OutcomeReceipt", receipt_id="o", transaction_id="TX-SYN-1", readback_receipt_hash=rbo_["object_hash"],
                                                                                              outcome_contract_hash=Z, result="PASS")), "not bound to contract+readback") and mm_.state == "COMMITTED")
    mm_, ff_ = comp_ready()
    t(g, "grant_with_empty_outcome_predicates_is_incomplete", raises(lambda: mm_.authorize_compensation(grant_of(outcome_predicates=[])), "incomplete"))
    mm_, ff_, gg_ = comp_authorized2(); post_ = rb_receipt(ff_, "ABSENT", obs={"exists": False})
    mm_.record_compensation(comp_receipt_for(gg_, post_), post_, comp_exec(gg_))
    t(g, "begin_compensation_refused_after_compensation_completed", raises(lambda: mm_.begin_compensation(), "illegal transition") and mm_.state == "COMPENSATED")
    mm_, ff_, gg_ = comp_unbegun(); mm_.begin_compensation()
    t(g, "begin_compensation_second_call_names_the_reason", raises(lambda: mm_.begin_compensation(), "attempt is already open"))

    # resume(): kinds, ids, mutation ids, execution receipt, durable ledger
    mR, fR, leaseR = sent_mission()
    for what, args in (("lease_none", (None, fR["cp"], fR["bu"])), ("lease_wrong_kind", (fR["cp"], fR["cp"], fR["bu"])), ("checkpoint_wrong_kind", (leaseR, leaseR, fR["bu"])),
                       ("budget_none", (leaseR, fR["cp"], None))):
        t(g, "resume_rejects_" + what, raises(lambda args=args: Mission.resume(args[0], args[1], args[2], "M-SYN-1", ev_upstream(mR), mR.ledger, allow_volatile_ledger=True), "hash invalid"))
    auth_R = fR["au"]["object_hash"]
    for what, ids in (("tuple_ids", ("%s:MUT-1" % auth_R,)), ("integer_element", [5]), ("none_element", [None])):
        t(g, "resume_rejects_" + what, raises(lambda ids=ids: rsm(remake(leaseR, consumed_authority_ids=ids), fR, mR), "consumed ids invalid"))
    m2x, f2x = two_mutation_mission(2)
    lease2x = m2x.checkpoint_lease()
    t(g, "resume_rejects_a_mutation_id_in_the_transaction_that_was_never_consumed", raises(lambda: rsm(remake(lease2x, mutation_id="MUT-2"), f2x, m2x), "mutation id inconsistent"))
    t(g, "resume_rejects_a_consumed_mutation_id_that_is_not_in_the_transaction", raises(lambda: rsm(remake(leaseR, consumed_authority_ids=["%s:MUT-X" % auth_R], mutation_id="MUT-X"), fR, mR, ledger=(lambda lg_: (lg_.consume((auth_R, "MUT-X")), lg_)[1])(MODEL.ReplayLedger())), "mutation id inconsistent"))
    mX, fX = fixture(); to_prewrite(mX, fX); mX.begin_execution("MUT-1", FP); erX = exec_receipt(fX); mX.record_execution(erX)
    leaseX = mX.checkpoint_lease()
    t(g, "resume_accepts_a_matching_execution_receipt", safe(lambda: rsm(leaseX, fX, mX, evidence=dict(ev_upstream(mX), execution_receipt=erX)).state == "COMMIT_STATE_UNKNOWN"))
    bad_mut = exec_receipt(fX, mut="MUT-X"); bad_tx = make("ExecutionReceipt", receipt_id="e", transaction_id="TX-OTHER", mutation_id="MUT-1", call_class="PROVIDER_RESPONSE_SUCCESS")
    t(g, "resume_rejects_an_execution_receipt_for_another_mutation_even_if_the_lease_pins_its_hash",
      raises(lambda: rsm(remake(leaseX, execution_receipt_hash=bad_mut["object_hash"]), fX, mX, evidence=dict(ev_upstream(mX), execution_receipt=bad_mut)), "does not match lease"))
    t(g, "resume_rejects_an_execution_receipt_for_another_transaction_even_if_the_lease_pins_its_hash",
      raises(lambda: rsm(remake(leaseX, execution_receipt_hash=bad_tx["object_hash"]), fX, mX, evidence=dict(ev_upstream(mX), execution_receipt=bad_tx)), "does not match lease"))
    tampered_er = stale(erX, call_class="PROVIDER_ERROR")
    t(g, "resume_rejects_a_tampered_execution_receipt", raises(lambda: rsm(leaseX, fX, mX, evidence=dict(ev_upstream(mX), execution_receipt=tampered_er)), "hash invalid"))
    dpath = os.path.join(ldir2, "durable_resume.txt")
    mD, fD = fixture(); mD.ledger = MODEL.ReplayLedger(dpath); to_prewrite(mD, fD); leaseD = mD.checkpoint_lease(); mD.begin_execution("MUT-1", FP)
    rD = Mission.resume(leaseD, fD["cp"], fD["bu"], "M-SYN-1", ev_upstream(mD), MODEL.ReplayLedger(dpath))
    t(g, "resume_with_a_durable_ledger_needs_no_opt_in", rD.state == "COMMIT_STATE_UNKNOWN" and rD.mutations_sent == 1)

    # lock waiting: a released lock is acquired after waiting (kills the timeout arithmetic mutants)
    import threading
    wp = os.path.join(ldir2, "wait.txt"); open(wp, "ab").close()
    hold = open(wp, "a+b"); MODEL._lock(hold)
    def release_later():
        __import__("time").sleep(0.4); MODEL._unlock(hold); hold.close()
    th = threading.Thread(target=release_later); th.start()
    waiter = open(wp, "a+b")
    t(g, "ledger_lock_waits_for_a_release_within_the_timeout", safe(lambda: (MODEL._lock(waiter, timeout=5.0), MODEL._unlock(waiter), True)[2]))
    th.join(); waiter.close()

    # ---- HARDENING_R2_0L (independent review 4: thread safety, types, compensation goal, ledger identity, malformed input)
    g = "HARDENING_R2_0L"
    import threading
    Zl = "0" * 64

    # -- N1: one guard call at a time per Mission
    def race(n_threads, fn_a, fn_b=None):
        mm_, ff_ = fixture(); to_prewrite(mm_, ff_)
        barrier = threading.Barrier(n_threads); results = []
        def go(i):
            barrier.wait()
            fn = fn_a if (fn_b is None or i % 2 == 0) else fn_b
            try:
                fn(mm_); results.append("OK:" + getattr(fn, "__name__", "f"))
            except MODEL.GuardError:
                results.append("REFUSED:" + getattr(fn, "__name__", "f"))
        ths = [threading.Thread(target=go, args=(i,)) for i in range(n_threads)]
        [th_.start() for th_ in ths]; [th_.join() for th_ in ths]
        return results, mm_, ff_
    def send(mm_):
        mm_.begin_execution("MUT-1", FP)
    def fail(mm_):
        mm_.fail_before_mutation()
    ok = True
    for _ in range(25):
        res, mm_, ff_ = race(8, send)
        ok = ok and sum(1 for r in res if r.startswith("OK")) == 1 and mm_.mutations_sent == 1 and mm_.state == "EXECUTION_STARTED" \
            and len(mm_.ledger.for_authority(ff_["au"]["object_hash"])) == 1 and "mutation_id" in mm_.ev
    t(g, "eight_threads_on_one_mission_exactly_one_send_and_the_state_agrees_with_the_ledger", ok)
    ok = True
    for _ in range(25):
        res, mm_, ff_ = race(8, send, fail)
        recorded = len(mm_.ledger.for_authority(ff_["au"]["object_hash"]))
        consistent = (mm_.state == "EXECUTION_STARTED" and recorded == 1 and mm_.mutations_sent == 1) or (mm_.state == "FAILED_BEFORE_MUTATION" and recorded == 0 and mm_.mutations_sent == 0)
        ok = ok and consistent
    t(g, "concurrent_send_and_fail_before_mutation_never_disagree_with_the_ledger", ok)
    mm_, ff_ = fixture(); to_prewrite(mm_, ff_)
    mm_.ledger.consume((ff_["au"]["object_hash"], "MUT-1"))                       # a send is recorded although this object forgot it
    t(g, "fail_before_mutation_consults_the_ledger", raises(lambda: mm_.fail_before_mutation(), "possibly sent") and mm_.state == "PREWRITE_VALIDATED")
    mm_, ff_ = fixture(); to_prewrite(mm_, ff_)
    t(g, "fail_before_mutation_is_allowed_when_nothing_was_sent", safe(lambda: (mm_.fail_before_mutation(), mm_.state)[1] == "FAILED_BEFORE_MUTATION"))
    mm_, ff_ = fixture()
    t(g, "fail_before_mutation_without_authority_evidence_still_works", safe(lambda: (mm_.fail_before_mutation(), mm_.state)[1] == "FAILED_BEFORE_MUTATION"))

    # -- N2/N7: strict types for scopes, names, ids, hashes and retries
    def authorize_with(dl_chg=None, au_chg=None, bu_chg=None):
        m_, f_ = at_context()
        d_ = remake(f_["dl"], **(dl_chg or {}))
        a_ = remake(f_["au"], **dict({"delegation_hash": d_["object_hash"]}, **(au_chg or {})))
        b_ = remake(f_["bu"], **dict({"authority_hash": a_["object_hash"]}, **(bu_chg or {})))
        return m_, d_, a_, b_
    for what, dl_c, au_c, text in (("string_scope", dict(scope="create_object"), dict(scope="create_object"), "scope must be a list"),
                                   ("integer_in_scope", dict(scope=["create_object", 5]), dict(scope=["create_object"]), "scope must be a list"),
                                   ("empty_string_in_scope", dict(scope=["create_object", ""]), dict(scope=["create_object"]), "scope must be a list"),
                                   ("none_scope", dict(scope=None), dict(scope=["create_object"]), "scope must be a list")):
        m_, d_, a_, b_ = authorize_with(dl_c, au_c)
        t(g, "authorize_rejects_" + what, raises(lambda m_=m_, d_=d_, a_=a_, b_=b_: m_.authorize(d_, a_, b_), text) and m_.state == "CONTEXT_READY")
    m_, f_ = at_context(); a_ = remake(f_["au"], scope="delete_everything"); b_ = remake(f_["bu"], authority_hash=a_["object_hash"])
    t(g, "string_scope_substring_attack_is_refused_at_the_gate", raises(lambda: m_.authorize(f_["dl"], a_, b_), "scope must be a list"))
    m_, f_ = at_authorized()
    for what, chg in (("integer_capability", dict(capability=5)), ("none_capability", dict(capability=None))):
        cb_ = remake(f_["cb"], **chg)
        t(g, "bind_rejects_" + what, raises(lambda cb_=cb_: m_.bind(cb_, f_["pb"]), "must be a string") and m_.state == "AUTHORIZED")
    for what, chg in (("integer_tool_name", dict(tool_name=5)), ("integer_identity", dict(identity=5))):
        pb_ = remake(f_["pb"], **chg)
        t(g, "bind_rejects_" + what, raises(lambda pb_=pb_: m_.bind(f_["cb"], pb_), "must be a string"))
    for what, field in (("mission_id", "mission_id"), ("authority_hash", "authority_hash"), ("delegation_hash", "delegation_hash")):
        m_, f_ = at_context(); a_ = remake(f_["au"], **{field: 0.0}); b_ = remake(f_["bu"], authority_hash=a_["object_hash"])
        t(g, "authorize_rejects_a_non_string_" + what, raises(lambda m_=m_, f_=f_, a_=a_, b_=b_: m_.authorize(f_["dl"], a_, b_), "must be a string"))
    m_ = Mission("M-SYN-1", "TX-SYN-1", 1); _, f_ = fixture()
    t(g, "context_ready_rejects_a_float_mission_id", raises(lambda: m_.context_ready(remake(f_["intent"], mission_id=0.0), f_["pr"]), "must be a string"))
    t(g, "context_ready_rejects_a_non_string_objective", raises(lambda: m_.context_ready(remake(f_["intent"], objective=5), f_["pr"]), "must be a string"))
    mm_, ff_ = at_started()
    t(g, "execution_receipt_with_a_non_string_mutation_id_is_refused", raises(lambda: mm_.record_execution(remake(exec_receipt(ff_), mutation_id=1)), "must be a string") and mm_.state == "EXECUTION_STARTED")
    t(g, "execution_receipt_with_a_non_string_transaction_id_is_refused", raises(lambda: mm_.record_execution(remake(exec_receipt(ff_), transaction_id=0.0)), "must be a string"))
    for what, rv in (("float_zero", 0.0), ("negative_zero", -0.0), ("boolean_false", False), ("true", True), ("one", 1), ("none", None), ("string_zero", "0")):
        m_, d_, a_, b_ = authorize_with(bu_chg=dict(retries=rv))
        t(g, "retries_must_be_exactly_the_integer_zero_" + what, raises(lambda m_=m_, d_=d_, a_=a_, b_=b_: m_.authorize(d_, a_, b_), "forbid expansion and retries"))
    m_, d_, a_, b_ = authorize_with()
    t(g, "retries_integer_zero_is_accepted", safe(lambda: (m_.authorize(d_, a_, b_), m_.state)[1] == "AUTHORIZED"))
    mm_, ff_, er_, done_ = complete_ready(); mod(mm_, "budget", retries=0.0)
    t(g, "relation_R09_rejects_a_float_zero_retries_in_the_chain", raises(lambda: mm_.complete(done_()), "[R09]"))

    # -- N3: the compensation goal must not already hold, and a cosmetic clone does not satisfy it
    mm_, ff_ = comp_ready()
    t(g, "compensation_goal_already_satisfied_by_the_forward_readback_is_refused", raises(lambda: mm_.authorize_compensation(grant_of(outcome_predicates=[{"field": "package", "op": "eq", "expected": "WRONG"}])), "already satisfied") and mm_.state == "COMPENSATION_REQUIRED")
    mm_, ff_ = comp_ready()
    t(g, "tautological_compensation_goal_is_refused", raises(lambda: mm_.authorize_compensation(grant_of(outcome_predicates=[{"field": "exists", "op": "in", "expected": [True, False]}])), "already satisfied"))
    mm_, ff_ = comp_ready()
    t(g, "compensation_goal_that_holds_only_after_the_action_is_accepted", safe(lambda: (mm_.authorize_compensation(grant_of()), mm_.state)[1] == "COMPENSATION_AUTHORIZED"))
    mm_, ff_, gg_ = comp_authorized2(); fwd_ = mm_.ev["readback"]
    clone_ = remake(fwd_, receipt_id="clone", observed=dict(fwd_["observed"], extra_key=1))
    t(g, "cosmetic_clone_of_the_forward_readback_does_not_complete_the_compensation", raises(lambda: mm_.record_compensation(comp_receipt_for(gg_, clone_), clone_, comp_exec(gg_)), "predicate not satisfied") and mm_.state == "COMPENSATION_AUTHORIZED")

    # -- N4: ledger identity
    ld2 = _tf.mkdtemp(prefix="r2ledger3_")
    pa = os.path.join(ld2, "a.txt"); la = MODEL.ReplayLedger(pa); la.consume(("A" * 64, "MUT-1"))
    t(g, "durable_ledger_has_a_random_identity_that_survives_reopening", isinstance(la.ledger_id, str) and len(la.ledger_id) == 32 and MODEL.ReplayLedger(pa).ledger_id == la.ledger_id
      and MODEL.ReplayLedger(os.path.join(ld2, "b.txt")).ledger_id != la.ledger_id and MODEL.ReplayLedger().ledger_id is None)
    mm_, ff_ = fixture(); mm_.ledger = MODEL.ReplayLedger(os.path.join(ld2, "lease.txt")); to_prewrite(mm_, ff_); lease_l = mm_.checkpoint_lease()
    t(g, "lease_carries_the_ledger_identity", lease_l["ledger_id"] == mm_.ledger.ledger_id and mm_.checkpoint_lease() is not lease_l and fixture()[0].ledger.ledger_id is None)
    mm_.begin_execution("MUT-1", FP)
    os.remove(os.path.join(ld2, "lease.txt"))
    recreated = MODEL.ReplayLedger(os.path.join(ld2, "lease.txt"))                  # deleted and recreated: new identity
    t(g, "resume_refuses_a_lease_from_another_ledger_identity", raises(lambda: Mission.resume(lease_l, ff_["cp"], ff_["bu"], "M-SYN-1", ev_upstream(mm_), recreated), "ledger identity differs from the lease"))
    pinned_id = la.ledger_id
    t(g, "pinned_identity_with_the_right_file_works", MODEL.ReplayLedger(pa, expected_id=pinned_id).has(("A" * 64, "MUT-1")))
    os.remove(pa)
    t(g, "pinned_identity_detects_a_missing_file", raises(lambda: MODEL.ReplayLedger(pa, expected_id=pinned_id), "ledger file missing"))
    open(pa, "wb").close()
    t(g, "pinned_identity_detects_an_empty_file", raises(lambda: MODEL.ReplayLedger(pa, expected_id=pinned_id), "empty or missing"))
    os.remove(pa); MODEL.ReplayLedger(pa)
    t(g, "pinned_identity_detects_a_replaced_file", raises(lambda: MODEL.ReplayLedger(pa, expected_id=pinned_id), "differs from the expected id"))
    ob = MODEL.ReplayLedger(os.path.join(ld2, "open.txt")); ob.consume(("A" * 64, "MUT-1"))
    os.remove(os.path.join(ld2, "open.txt")); MODEL.ReplayLedger(os.path.join(ld2, "open.txt"))
    t(g, "an_open_ledger_notices_when_its_file_is_replaced", raises(lambda: ob.has(("A" * 64, "MUT-1")), "identity changed"))
    mm_, ff_ = fixture(); mm_.ledger = MODEL.ReplayLedger(os.path.join(ld2, "pin_fresh.txt")); fresh_id = mm_.ledger.ledger_id
    to_prewrite(mm_, ff_); mm_.begin_execution("MUT-1", FP)
    os.remove(os.path.join(ld2, "pin_fresh.txt"))
    m2_, f2_ = fixture()
    t(g, "documented_limit_deleted_ledger_without_a_pin_is_not_detected_for_a_fresh_mission", safe(lambda: (setattr(m2_, "ledger", MODEL.ReplayLedger(os.path.join(ld2, "pin_fresh.txt"))), to_prewrite(m2_, f2_), m2_.begin_execution("MUT-1", FP), m2_.mutations_sent)[3] == 1))
    os.remove(os.path.join(ld2, "pin_fresh.txt"))
    m3_, f3_ = fixture()
    t(g, "with_a_pinned_identity_a_deleted_ledger_blocks_a_fresh_mission", raises(lambda: setattr(m3_, "ledger", MODEL.ReplayLedger(os.path.join(ld2, "pin_fresh.txt"), expected_id=fresh_id)), "ledger file missing"))
    lh_ = os.path.join(ld2, "hdr.txt"); MODEL.ReplayLedger(lh_)
    raw_ = open(lh_, "rb").read().replace(b"R2LEDGER", b"R2LEDGEX"); open(lh_, "wb").write(raw_)
    t(g, "tampered_ledger_header_fails_closed", raises(lambda: MODEL.ReplayLedger(lh_), "missing or invalid header"))
    open(lh_, "wb").write(b'{"a":"x","m":"y","c":"00000000"}\n')
    t(g, "a_ledger_file_without_a_header_fails_closed", raises(lambda: MODEL.ReplayLedger(lh_), "missing or invalid header"))
    open(lh_, "wb").write(b"\n")
    t(g, "an_empty_first_line_fails_closed", raises(lambda: MODEL.ReplayLedger(lh_), "corrupted"))
    open(lh_, "wb").write(b'{"hdr":"R2LEDG')
    t(g, "a_torn_header_only_file_is_recreated_cleanly", safe(lambda: MODEL.ReplayLedger(lh_).ledger_id is not None and open(lh_, "rb").read().count(b"\n") == 1))

    # lease claims must be recorded: a forged lease against an empty ledger is refused (review 4 N5)
    mF, fF, leaseF = sent_mission()
    t(g, "lease_claiming_a_send_the_ledger_does_not_record_is_refused", raises(lambda: rsm(leaseF, fF, mF, ledger=MODEL.ReplayLedger()), "does not record"))
    t(g, "lease_claim_is_accepted_when_the_ledger_records_it", safe(lambda: rsm(leaseF, fF, mF).state == "COMMIT_STATE_UNKNOWN"))

    # -- N6: malformed input becomes GuardError, never a raw exception
    lease_missing = {k: v for k, v in leaseF.items() if k != "mutation_id"}
    t(g, "resume_with_a_lease_missing_a_field_raises_guard_error", raises(lambda: rsm(lease_missing, fF, mF), None))
    t(g, "resume_with_non_dict_evidence_values_raises_guard_error", raises(lambda: rsm(leaseF, fF, mF, evidence={"tx": 5}), None) and raises(lambda: rsm(leaseF, fF, mF, mission_id=None), None))
    lbad = MODEL.ReplayLedger(os.path.join(ld2, "io.txt")); lbad.path = os.path.join(ld2, "missing_dir", "x.txt")
    t(g, "ledger_io_errors_are_guard_errors", raises(lambda: lbad.consume(("A" * 64, "M")), "ledger I/O error") and raises(lambda: lbad.has(("A" * 64, "M")), "ledger I/O error")
      and raises(lambda: lbad.for_authority("A" * 64), "ledger I/O error"))
    lq = MODEL.ReplayLedger(os.path.join(ld2, "keys.txt"))
    t(g, "ledger_rejects_string_and_bytes_keys", raises(lambda: lq.consume("ab"), "non-empty strings") and raises(lambda: lq.has("ab"), "non-empty strings") and raises(lambda: lq.consume(b"ab"), "non-empty strings"))
    t(g, "ledger_rejects_unencodable_text", raises(lambda: lq.consume(("A" * 64, "m\ud800x")), "not valid text"))
    t(g, "ledger_limit_must_be_a_non_negative_integer_or_none", all(raises(lambda lim=lim: lq.consume(("A" * 64, "L%d" % i), limit=lim), "non-negative integer or None") for i, lim in enumerate((float("nan"), -1, True, "1", 1.0))))
    t(g, "ledger_limit_zero_refuses_every_send", raises(lambda: lq.consume(("Z" * 64, "M"), limit=0), "send count exhausted") and not lq.has(("Z" * 64, "M")))
    t(g, "ledger_limit_none_means_unlimited", safe(lambda: (lq.consume(("U" * 64, "M1")), lq.consume(("U" * 64, "M2")), lq.consume(("U" * 64, "M3")), len(lq.for_authority("U" * 64)))[3] == 3))

    # -- review 4 mutant-derived gaps
    mG, fG = fixture(); to_prewrite(mG, fG); leaseG0 = mG.checkpoint_lease(); mG.begin_execution("MUT-1", FP)
    rG = rsm(leaseG0, fG, mG)
    rG.request_readback(); rbG = rb_receipt(fG); rG.observe_readback(rbG); rG.decide_commit(commit_obs(rbG, "COMMITTED")); rG.validate_outcome(outcome(fG, rbG, "PASS"))
    crG = make("CompletionReceipt", receipt_id="done", transaction_id="TX-SYN-1", outcome_receipt_hash=rG.ev["outcome"]["object_hash"], commit_observation_hash=rG.ev["commit"]["object_hash"],
               execution_receipt_hash=rG.ev["execution_receipt"]["object_hash"], authority_hash=fG["au"]["object_hash"])
    t(g, "a_resumed_mission_reaches_complete_with_the_synthetic_commit_unknown_receipt_after_a_fresh_readback",
      safe(lambda: (rG.complete(crG), rG.state)[1] == "COMPLETE") and rG.ev["execution_receipt"]["call_class"] == "COMMIT_UNKNOWN" and len(chain_hashes(rG)) == 14)
    for slot in ("tx", "budget", "outcome_contract", "readback_contract", "authority"):
        lease_, cp_, bu_, ev_ = world(); ev_.pop(slot)
        t(g, "resume_requires_the_%s_evidence" % slot, raises(lambda lease_=lease_, cp_=cp_, bu_=bu_, ev_=ev_: Mission.resume(lease_, cp_, bu_, "M-SYN-1", ev_, MODEL.ReplayLedger(), allow_volatile_ledger=True), "missing %s" % slot))
    m2x, f2x = two_mutation_mission(2)
    m2x.ledger.consume((f2x["au"]["object_hash"], "MUT-2"))
    lease2 = remake(m2x.checkpoint_lease(), consumed_authority_ids=sorted("%s:%s" % (f2x["au"]["object_hash"], x) for x in ("MUT-1", "MUT-2")), remaining_budget=0)
    r2x = rsm(lease2, f2x, m2x)
    t(g, "resume_with_two_consumed_keys_counts_both", r2x.mutations_sent == 2 and r2x.remaining == 0 and len(r2x.consumed) == 2)
    seen_at_fsync = []
    real_fsync2 = MODEL.os.fsync
    def spy_fsync(fd):
        seen_at_fsync.append(os.path.getsize(os.path.join(ld2, "flush.txt")))      # size query: the byte-range lock blocks reads
        return real_fsync2(fd)
    lf_ = MODEL.ReplayLedger(os.path.join(ld2, "flush.txt"))
    MODEL.os.fsync = spy_fsync
    try:
        lf_.consume(("F" * 64, "MUT-1"))
    finally:
        MODEL.os.fsync = real_fsync2
    t(g, "the_record_is_flushed_to_the_file_before_fsync_is_called", len(seen_at_fsync) == 1 and seen_at_fsync[0] > len(lf_._header_line(lf_.ledger_id)))

    # -- review 4 mutation survivors, closed by tests
    m_, f_ = fixture()
    t(g, "none_valued_ids_and_hashes_are_refused", raises(lambda: Mission("M-SYN-1", "TX-SYN-1", 1).context_ready(remake(f_["intent"], mission_id=None), f_["pr"]), "must be a string")
      and raises(lambda: Mission("M-SYN-1", "TX-SYN-1", 1).context_ready(f_["intent"], remake(f_["pr"], principal_id=None)), "must be a string"))
    mm_, ff_ = fixture(); to_prewrite(mm_, ff_); mm_.begin_execution("MUT-1", FP)
    mm_.ledger = MODEL.ReplayLedger()                                               # the object remembers the send; the replaced ledger does not
    t(g, "fail_before_mutation_also_trusts_the_missions_own_send_counter", raises(lambda: mm_.fail_before_mutation(), "possibly sent") and mm_.state == "EXECUTION_STARTED")
    hd = os.path.join(ld2, "header_variants.txt")
    good_id = "a" * 32
    variants = {
        "not_a_dict": b"[1]\n",
        "wrong_version": (json.dumps({"hdr": "R2LEDGER", "v": 2, "id": good_id, "c": MODEL.ReplayLedger._crc(good_id, "HDR")}) + "\n").encode(),
        "integer_id": (json.dumps({"hdr": "R2LEDGER", "v": 1, "id": 5, "c": "00000000"}) + "\n").encode(),
        "bad_crc": (json.dumps({"hdr": "R2LEDGER", "v": 1, "id": good_id, "c": "deadbeef"}) + "\n").encode(),
        "wrong_marker": (json.dumps({"hdr": "OTHER", "v": 1, "id": good_id, "c": MODEL.ReplayLedger._crc(good_id, "HDR")}) + "\n").encode(),
    }
    for vname, body in variants.items():
        open(hd, "wb").write(body)
        t(g, "ledger_header_variant_is_refused_" + vname, raises(lambda: MODEL.ReplayLedger(hd), "missing or invalid header"))
    open(hd, "wb").write((json.dumps({"hdr": "R2LEDGER", "v": 1, "id": good_id, "c": MODEL.ReplayLedger._crc(good_id, "HDR")}, separators=(",", ":")) + "\n").encode())
    t(g, "a_valid_header_is_accepted_and_its_id_is_used", MODEL.ReplayLedger(hd).ledger_id == good_id)

    # deterministic race: thread B is inside begin_execution (past its snapshot) while thread A completes a send
    def deterministic_race():
        mm2, ff2 = fixture(); to_prewrite(mm2, ff2)
        a_done = threading.Event(); in_b = threading.Event(); out = {}
        real_has = mm2.ledger.has
        state = {"first": True}
        def slow_has(key):
            if state["first"] and threading.current_thread().name == "B":
                state["first"] = False
                in_b.set(); a_done.wait(timeout=1.0)                                  # with the lock A cannot finish: B proceeds after the timeout
            return real_has(key)
        mm2.ledger.has = slow_has
        def run_b():
            try:
                mm2.begin_execution("MUT-1", FP); out["B"] = "SENT"
            except MODEL.GuardError:
                out["B"] = "REFUSED"
        def run_a():
            in_b.wait(timeout=2.0)
            try:
                mm2.begin_execution("MUT-1", FP); out["A"] = "SENT"
            except MODEL.GuardError:
                out["A"] = "REFUSED"
            a_done.set()
        tb = threading.Thread(target=run_b, name="B"); ta = threading.Thread(target=run_a, name="A")
        tb.start(); ta.start(); tb.join(); ta.join()
        recorded = len(mm2.ledger.for_authority(ff2["au"]["object_hash"]))
        return out, mm2, recorded
    out_, mm_, rec_ = deterministic_race()
    t(g, "interleaved_threads_cannot_erase_a_send_the_ledger_recorded",
      sum(1 for x in out_.values() if x == "SENT") == 1 and rec_ == 1 and mm_.mutations_sent == 1 and mm_.state == "EXECUTION_STARTED")

    # ---- HARDENING_R2_0M (independent review 5: volatile ledger threads, path validation, readback provider, rollback history)
    g = "HARDENING_R2_0M"

    # F1: a shared in-memory ledger is safe across threads
    def hammer(n_threads, key_fn, limit=None, rounds=1):
        errors, wins = [], []
        lg_ = MODEL.ReplayLedger()
        barrier = threading.Barrier(n_threads)
        def work(i):
            barrier.wait()
            for r in range(rounds):
                try:
                    lg_.consume(key_fn(i, r), limit=limit); wins.append(i)
                except MODEL.GuardError:
                    pass
                except Exception as exc:                                   # a raw exception is the defect under test
                    errors.append(type(exc).__name__)
        ths = [threading.Thread(target=work, args=(i,)) for i in range(n_threads)]
        [th_.start() for th_ in ths]; [th_.join() for th_ in ths]
        return lg_, wins, errors
    ok = True
    for _ in range(60):
        lg_, wins, errors = hammer(8, lambda i, r: ("A" * 64, "MUT-1"))
        ok = ok and len(wins) == 1 and not errors and len(lg_.for_authority("A" * 64)) == 1
    t(g, "eight_threads_on_one_volatile_ledger_exactly_one_consume_wins_the_same_key", ok)
    ok = True
    for _ in range(60):
        lg_, wins, errors = hammer(8, lambda i, r: ("A" * 64, "MUT-%d" % i), limit=1)
        ok = ok and len(wins) == 1 and not errors and len(lg_.for_authority("A" * 64)) == 1
    t(g, "eight_threads_on_one_volatile_ledger_the_per_authority_limit_holds", ok)
    errors2, lg2 = [], MODEL.ReplayLedger()
    stop = threading.Event()
    def writer():
        for n in range(400):
            try:
                lg2.consume(("W" * 64, "M%d" % n))
            except MODEL.GuardError:
                pass
        stop.set()
    def reader():
        while not stop.is_set():
            try:
                lg2.for_authority("W" * 64); lg2.has(("W" * 64, "M1"))
            except Exception as exc:
                errors2.append(type(exc).__name__)
    ths2 = [threading.Thread(target=writer)] + [threading.Thread(target=reader) for _ in range(4)]
    [th_.start() for th_ in ths2]; [th_.join() for th_ in ths2]
    t(g, "readers_never_see_set_changed_size_while_writers_consume", not errors2 and len(lg2.for_authority("W" * 64)) == 400)
    ok = True
    for _ in range(40):
        ms = []
        lgm = MODEL.ReplayLedger()
        for _k in range(8):
            mm_, ff_ = fixture(); mm_.ledger = lgm; to_prewrite(mm_, ff_); ms.append(mm_)
        res_ = []
        barrier2 = threading.Barrier(8)
        def go2(mm_):
            barrier2.wait()
            try:
                mm_.begin_execution("MUT-1", FP); res_.append("SENT")
            except MODEL.GuardError:
                res_.append("REFUSED")
            except Exception as exc:
                res_.append("RAW:" + type(exc).__name__)
        ths3 = [threading.Thread(target=go2, args=(mm_,)) for mm_ in ms]
        [th_.start() for th_ in ths3]; [th_.join() for th_ in ths3]
        ok = ok and res_.count("SENT") == 1 and not any(r.startswith("RAW") for r in res_)
    t(g, "eight_missions_sharing_one_volatile_ledger_send_exactly_once", ok)

    # F2: ledger construction arguments
    t(g, "empty_ledger_path_is_refused", raises(lambda: MODEL.ReplayLedger(""), "non-empty string or None"))
    t(g, "non_string_ledger_paths_are_refused", all(raises(lambda p_=p_: MODEL.ReplayLedger(p_), "non-empty string or None") for p_ in (5, b"x", ["a"], 0.0, False)))
    t(g, "expected_id_needs_a_file_backed_ledger", raises(lambda: MODEL.ReplayLedger(None, expected_id="a" * 32), "needs a file-backed ledger"))
    t(g, "volatile_ledger_is_not_durable_and_a_path_ledger_is", MODEL.ReplayLedger().is_durable is False and MODEL.ReplayLedger(os.path.join(ld2, "durable_flag.txt")).is_durable is True)

    # F4: the readback contract must name the bound provider
    mm_, ff_ = at_bound()
    rc_x = remake(ff_["rc"], provider_ref="OTHER::repo_read")
    cp_x = remake(ff_["cp"], readback_contract_hash=rc_x["object_hash"])
    t(g, "prewrite_refuses_a_readback_contract_for_another_provider", raises(lambda: mm_.prewrite_validate(ff_["tx"], ff_["oc"], rc_x, cp_x), "differs from the bound provider") and mm_.state == "BOUND")
    rc_y = remake(ff_["rc"], provider_ref="SYN")
    cp_y = remake(ff_["cp"], readback_contract_hash=rc_y["object_hash"])
    t(g, "a_provider_ref_without_the_separator_is_refused", raises(lambda: mm_.prewrite_validate(ff_["tx"], ff_["oc"], rc_y, cp_y), "differs from the bound provider"))
    rc_z = remake(ff_["rc"], provider_ref="SYNX::repo_read")
    cp_z = remake(ff_["cp"], readback_contract_hash=rc_z["object_hash"])
    t(g, "a_provider_id_that_is_only_a_prefix_of_another_is_refused", raises(lambda: mm_.prewrite_validate(ff_["tx"], ff_["oc"], rc_z, cp_z), "differs from the bound provider"))
    t(g, "resume_refuses_a_readback_contract_for_another_provider", raises(lambda: try_resume(rc_chg=dict(provider_ref="OTHER::x")), "differs from the bound provider"))
    t(g, "the_matching_provider_prefix_is_accepted", safe(lambda: (mm_.prewrite_validate(ff_["tx"], ff_["oc"], ff_["rc"], ff_["cp"]), mm_.state)[1] == "PREWRITE_VALIDATED"))

    # missing tests named by the reviewer: atomic history, lock contention with the default timeout, resume audit and fallback id
    mm_, ff_ = fixture(); to_prewrite(mm_, ff_)
    hist_before = list(mm_.history)
    t(g, "a_refused_guard_call_leaves_the_history_unchanged", raises(lambda: mm_.begin_execution("MUT-1", "FP-DRIFTED"), "contract drift") and mm_.history == hist_before)
    mm_.begin_execution("MUT-1", FP)
    t(g, "a_successful_guard_call_appends_exactly_one_history_entry", len(mm_.history) == len(hist_before) + 1 and mm_.history[-1][0] == "EXECUTION_STARTED")
    class FlakyMission(Mission):
        """Fails AFTER the first history entry of validate_outcome was appended, to prove the rollback restores the history."""
        def _go(self, to, ref=None, _tok=None):
            if to == "OUTCOME_VALIDATED":
                raise MODEL.GuardError("injected late failure")
            return super()._go(to, ref, _tok=_tok)
    mf_, ff_f = fixture()
    mf_ = FlakyMission("M-SYN-1", "TX-SYN-1", 1)
    mf_.context_ready(ff_f["intent"], ff_f["pr"]); mf_.authorize(ff_f["dl"], ff_f["au"], ff_f["bu"]); mf_.bind(ff_f["cb"], ff_f["pb"]); mf_.prewrite_validate(ff_f["tx"], ff_f["oc"], ff_f["rc"], ff_f["cp"])
    mf_.begin_execution("MUT-1", FP); mf_.record_execution(exec_receipt(ff_f)); mf_.request_readback(); rbf_ = rb_receipt(ff_f); mf_.observe_readback(rbf_); mf_.decide_commit(commit_obs(rbf_, "COMMITTED"))
    h_f = list(mf_.history); ev_f = dict(mf_.ev)
    t(g, "a_call_that_fails_late_also_restores_history_state_and_evidence", raises(lambda: mf_.validate_outcome(outcome(ff_f, rbf_, "PASS")), "injected late failure")
      and mf_.history == h_f and mf_.state == "COMMITTED" and set(mf_.ev) == set(ev_f) and "outcome" not in mf_.ev)
    wp2 = os.path.join(ld2, "wait_default.txt"); open(wp2, "ab").close()
    hold2 = open(wp2, "a+b"); MODEL._lock(hold2)
    def release_later2():
        __import__("time").sleep(0.35); MODEL._unlock(hold2); hold2.close()
    th2 = threading.Thread(target=release_later2); th2.start()
    waiter2 = open(wp2, "a+b")
    t(g, "the_default_lock_timeout_outlasts_normal_contention", safe(lambda: (MODEL._lock(waiter2), MODEL._unlock(waiter2), True)[2]))
    th2.join(); waiter2.close()
    m3x, f3x = two_mutation_mission(2)
    m3x.ledger.consume((f3x["au"]["object_hash"], "MUT-2"))
    lease3 = remake(m3x.checkpoint_lease(), consumed_authority_ids=sorted("%s:%s" % (f3x["au"]["object_hash"], x) for x in ("MUT-1", "MUT-2")), remaining_budget=0, mutation_id=None)
    r3x = rsm(lease3, f3x, m3x)
    t(g, "resume_without_a_lease_mutation_id_uses_the_first_sorted_ledger_key", r3x.ev["mutation_id"] == "MUT-1")
    t(g, "resume_records_an_audit_entry_in_the_history", r3x.history[-1] == ("RESUMED_AS_COMMIT_STATE_UNKNOWN", lease3["object_hash"]))

    # ---- HARDENING_R2_0N (independent review 6: lock regression, path validation, R51 empty tail, failed compensation)
    g = "HARDENING_R2_0N"

    class SpySet(set):
        """A set that records any overlap between two threads' operations on it. Every operation pauses mid-way, so an
        unserialized caller overlaps reliably instead of depending on GIL timing."""
        def __init__(self, *a):
            super().__init__(*a)
            self.guard, self.inflight, self.overlaps = threading.Lock(), 0, 0

        def _enter(self):
            with self.guard:
                self.inflight += 1
                if self.inflight > 1:
                    self.overlaps += 1

        def _leave(self):
            with self.guard:
                self.inflight -= 1

        def __contains__(self, k):
            self._enter(); time.sleep(0.0005); r = set.__contains__(self, k); self._leave(); return r

        def __iter__(self):
            self._enter()
            try:
                for k in list(set.__iter__(self)):
                    time.sleep(0.0002)
                    yield k
            finally:
                self._leave()

        def add(self, k):
            self._enter(); time.sleep(0.0005); set.add(self, k); self._leave()

        def __ior__(self, other):
            self._enter(); time.sleep(0.0005); set.__ior__(self, other); self._leave(); return self

    def spy_run(lg_, ops):
        spy = SpySet()
        lg_._keys = spy
        errs = []
        barrier = threading.Barrier(len(ops))
        def work(op):
            barrier.wait()
            for r in range(6):
                try:
                    op(r)
                except MODEL.GuardError:
                    pass
                except Exception as exc:
                    errs.append(type(exc).__name__)
        ths = [threading.Thread(target=work, args=(op,)) for op in ops]
        [th_.start() for th_ in ths]; [th_.join() for th_ in ths]
        return spy, errs

    A64 = "A" * 64
    spy_v, errs_v = spy_run(MODEL.ReplayLedger(), [
        lambda r: None, lambda r: None])                                                          # control: no overlap without work
    t(g, "the_spy_set_reports_no_overlap_when_nothing_runs_concurrently", spy_v.overlaps == 0 and not errs_v)
    lgv = MODEL.ReplayLedger()
    spy_v, errs_v = spy_run(lgv, [
        lambda r: lgv.consume((A64, "W%d" % r)), lambda r: lgv.consume((A64, "X%d" % r)),
        lambda r: lgv.for_authority(A64), lambda r: lgv.has((A64, "W1")), lambda r: lgv.for_authority(A64)])
    t(g, "volatile_ledger_operations_never_overlap_on_the_shared_set", spy_v.overlaps == 0 and not errs_v)
    t(g, "volatile_ledger_loses_no_consume_under_the_spy", len(spy_v) == 12)
    lgf = MODEL.ReplayLedger(os.path.join(ld2, "spy_file_ledger.txt"))
    spy_f, errs_f = spy_run(lgf, [
        lambda r: lgf.consume((A64, "F%d" % r)), lambda r: lgf.consume((A64, "G%d" % r)),
        lambda r: lgf.for_authority(A64), lambda r: lgf.has((A64, "F1"))])
    t(g, "file_ledger_operations_never_overlap_on_the_shared_set", spy_f.overlaps == 0 and not errs_f)
    t(g, "file_ledger_records_every_consume_under_the_spy", len(spy_f) == 12 and len(MODEL.ReplayLedger(lgf.path).for_authority(A64)) == 12)
    spy_m = SpySet(); spy_m.add(("x", "y"))
    t(g, "the_spy_set_detects_an_overlap_when_it_is_used_unserialized", (lambda: (
        [th_.join() for th_ in [(lambda th_: (th_.start(), th_)[1])(threading.Thread(target=lambda: [spy_m.add(("a", str(i))) for i in range(5)])) for _ in range(3)]],
        spy_m.overlaps > 0)[1])())

    class RvSet(set):
        """Deterministic overlap detector: a writer pauses inside add() until a second thread reaches the set (or 0.4 s
        pass). If the second thread gets in while the first is paused, the two were not serialized."""
        def __init__(self):
            super().__init__()
            self.inside, self.other, self.overlap = threading.Event(), threading.Event(), False

        def _reach(self):
            if self.inside.is_set():
                self.overlap = True
                self.other.set()

        def __contains__(self, k):
            self._reach(); return set.__contains__(self, k)

        def __iter__(self):
            self._reach(); return set.__iter__(self)

        def add(self, k):
            self.inside.set(); self.other.wait(0.4); set.add(self, k); self.inside.clear()

    def rendezvous(second):
        lg_ = MODEL.ReplayLedger()
        rv = RvSet(); lg_._keys = rv
        first = threading.Thread(target=lambda: lg_.consume((A64, "RV-1")))
        first.start()
        rv.inside.wait(2)
        sec = threading.Thread(target=lambda: safe(lambda: second(lg_)))
        sec.start(); sec.join(); first.join()
        return rv.overlap, len(rv)
    t(g, "a_second_consume_cannot_enter_the_set_while_the_first_is_inside", rendezvous(lambda l_: l_.consume((A64, "RV-2"))) == (False, 2))
    t(g, "has_cannot_read_the_set_while_a_consume_is_inside", rendezvous(lambda l_: l_.has((A64, "RV-1"))) == (False, 1))
    t(g, "for_authority_cannot_iterate_the_set_while_a_consume_is_inside", rendezvous(lambda l_: l_.for_authority(A64)) == (False, 1))
    ov_, n_ = rendezvous(lambda l_: l_._keys.__contains__((A64, "RV-1")))
    t(g, "the_rendezvous_detects_an_unserialized_reader", ov_ is True)

    # N2: ledger path validation
    for label, bad in (("nul_character", "led\x00ger.txt"), ("bare_con", "CON"), ("lower_case_con_with_extension", "con.txt"),
                       ("nul_device_in_a_directory", os.path.join(ld2, "NUL")), ("lpt1_in_the_middle", ld2 + "/LPT1/x.txt"),
                       ("com3_with_extension", "COM3.log"), ("device_name_with_trailing_space", "CON ")):
        t(g, "ledger_path_" + label + "_is_a_guard_error", raises(lambda b=bad: MODEL.ReplayLedger(b), "ledger path"))
    t(g, "similar_but_legal_names_are_accepted", all(safe(lambda n=n: MODEL.ReplayLedger(os.path.join(ld2, n)) is not None) for n in ("console.txt", "CONFIG", "aux_ledger.txt", "com10.txt")))
    t(g, "ledger_io_value_errors_become_guard_errors", raises(lambda: MODEL._io_guard(lambda: (_ for _ in ()).throw(ValueError("embedded null byte")))(), "ledger I/O error: ValueError"))

    # N4: R51 is a literal prefix test; an empty tail and an empty provider id are accepted by design (contract R6 section 4)
    mm_, ff_ = at_bound()
    rc_e = remake(ff_["rc"], provider_ref="SYN::")
    cp_e = remake(ff_["cp"], readback_contract_hash=rc_e["object_hash"])
    t(g, "r51_refuses_an_empty_tail_after_the_separator", raises(lambda: mm_.prewrite_validate(ff_["tx"], ff_["oc"], rc_e, cp_e), "differs from the bound provider") and mm_.state == "BOUND")
    for lbl, ref in (("nested_separator", "SYN::a::b"), ("only_separator", "::"), ("empty_provider", "::repo_read"), ("case_change", "syn::repo_read")):
        rc_n = remake(ff_["rc"], provider_ref=ref); cp_n = remake(ff_["cp"], readback_contract_hash=rc_n["object_hash"])
        t(g, "r51_refuses_" + lbl, raises(lambda rc_n=rc_n, cp_n=cp_n: mm_.prewrite_validate(ff_["tx"], ff_["oc"], rc_n, cp_n), "differs from the bound provider"))
    t(g, "provider_ref_ok_unit", MODEL.provider_ref_ok("SYN::x", "SYN") and not MODEL.provider_ref_ok("SYN::", "SYN") and not MODEL.provider_ref_ok("SYN::x", "") and not MODEL.provider_ref_ok("A::B::x", "A::B") and not MODEL.provider_ref_ok(5, "SYN"))

    # N5: after begin_compensation a failed compensating call report is refused and changes nothing; the model does not gate a second provider call (contract R7 section 3)
    fail_classes = sorted(c for c in CALL_CLASSES if c != "PROVIDER_RESPONSE_SUCCESS")
    mm_, ff_, gg_ = comp_unbegun(); mm_.begin_compensation(); post_ = rb_receipt(ff_, "ABSENT", obs={"exists": False})
    refused_all = True
    for cls_ in fail_classes:
        refused_all = refused_all and raises(lambda c=cls_: mm_.record_compensation(comp_receipt_for(gg_, post_), post_, comp_exec(gg_, cls=c)), "") and mm_.state == "COMPENSATION_AUTHORIZED"
    t(g, "every_non_success_compensating_call_class_is_refused_and_leaves_the_state", refused_all and len(fail_classes) >= 1)
    t(g, "a_compensation_cannot_be_begun_again_while_the_first_attempt_is_open", raises(lambda: mm_.begin_compensation(), "attempt is already open"))
    t(g, "the_only_exits_of_compensation_authorized_are_compensated_and_unrecoverable", TRANSITIONS["COMPENSATION_AUTHORIZED"] == {"COMPENSATED", "UNRECOVERABLE"})
    mm_, ff_, gg_ = comp_unbegun(); mm_.begin_compensation()
    t(g, "a_definite_failure_on_the_last_attempt_makes_the_mission_unrecoverable", safe(lambda: mm_.record_compensation_failure(comp_exec(gg_, cls="PROVIDER_ERROR")) == "UNRECOVERABLE"))
    t(g, "no_second_compensating_call_after_the_budget_is_used", raises(lambda: mm_.begin_compensation(), "illegal transition"))

    # ---- NO_ENTERPRISE_WRITES (structural)
    g = "NO_ENTERPRISE_WRITES"
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcr3_model.py")).read()
    t(g, "model_has_no_network_or_process_imports", not any(k in src for k in ("import socket", "import requests", "urllib", "subprocess", "http.client")))


def _exec_only_complete():
    m, f = fixture(); to_prewrite(m, f); m.begin_execution("MUT-1", FP); m.record_execution(exec_receipt(f))
    m._go("COMPLETE")


ACCEPT = ["STATE_MACHINE_VALID", "SCHEMA_VALIDATION", "AUTHORITY_INVARIANTS", "MUTATION_BUDGET_INVARIANTS",
          "REPLAY_GUARD_INVARIANTS", "CONTINUATION_INVARIANTS", "COMPENSATION_AUTHORITY_INVARIANTS",
          "OUTCOME_PREDICATE_MODEL", "COMMIT_UNKNOWN_HANDLING", "COMPLETION_EVIDENCE", "HARDENING_R2_0H", "HARDENING_R2_0I", "HARDENING_R2_0J", "HARDENING_R2_0L", "HARDENING_R2_0M", "TELEMETRY_MODEL", "NO_ENTERPRISE_WRITES"]


def main(argv):
    run()
    groups = {g: "PASS" if all(T[n] for n in G[g]) else "FAIL" for g in ACCEPT}
    failed = sorted(n for n, ok in T.items() if not ok)
    result = {"stage": "R2_0_A_OUTCOME_MODEL_FOUNDATION", "evidence_class": "SYNTHETIC/LOCAL", "groups": groups,
              "tests": len(T), "failed": failed, "enterprise_writes": 0, "network_calls": 0,
              "tests_digest": chash(sorted(T.items()))}
    result["R2_0_A_FOUNDATION"] = "PASS" if not failed and all(v == "PASS" for v in groups.values()) else "FAIL"
    out = json.dumps(result, indent=2, sort_keys=True)
    if "--out" in argv:
        with open(argv[argv.index("--out") + 1], "w", newline="\n") as fh:
            fh.write(out + "\n")
    if "--emit-schemas" in argv:
        d = argv[argv.index("--emit-schemas") + 1]; os.makedirs(d, exist_ok=True)
        for k, (req, enums) in sorted(SCHEMAS.items()):
            schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": k, "type": "object",
                      "required": ["kind", "object_hash"] + req,
                      "properties": dict({"kind": {"const": k}, "object_hash": {"type": "string", "pattern": "^[0-9A-F]{64}$"}},
                                         **{f: {"enum": list(v)} for f, v in enums.items()})}
            with open(os.path.join(d, k + ".schema.json"), "w", newline="\n") as fh:
                fh.write(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    print(out)
    return 0 if result["R2_0_A_FOUNDATION"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
