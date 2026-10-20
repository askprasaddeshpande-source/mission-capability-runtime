"""R2.0A deterministic validator. Synthetic/local only; makes no enterprise or network call.

Usage: python tools/r2.0/validate_r2_outcome_model.py [--out PATH] [--emit-schemas DIR]
Exit 0 only if every acceptance group passes. Output is deterministic (no timestamps/timings).
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mcr_r2_model as MODEL  # noqa: E402
from mcr_r2_model import (CALL_CLASSES, CHAIN_SLOTS, EXPECTED_CHAIN, SCHEMAS, STATES, TRANSITIONS, GuardError, Mission, SchemaError,  # noqa: E402
                          chain_hashes, chash, eval_predicates, make, verify_hash)

FP = "FP-" + "A" * 61
PREDS = [{"field": "exists", "op": "eq", "expected": True},
         {"field": "package", "op": "eq", "expected": "ZPKG_SYN"},
         {"field": "active", "op": "eq", "expected": True},
         {"field": "source_sha256", "op": "eq", "expected": "S" * 8}]
GOOD_OBS = {"exists": True, "package": "ZPKG_SYN", "active": True, "source_sha256": "S" * 8}


def fixture(max_mut=1, scope=("create_object",), deleg_scope=("create_object", "read_object")):
    mid, tid = "M-SYN-1", "TX-SYN-1"
    intent = make("MissionIntent", mission_id=mid, objective="synthetic", target_system="SYN_SYS", expected_outcome_hash="x")
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
    oc = make("ExpectedOutcomeContract", outcome_contract_id="oc1", mission_id=mid, transaction_id=tid, predicates=PREDS, frozen=True)
    rc = make("AuthoritativeReadbackContract", contract_id="rc1", source_level_required="AUTHORITATIVE_REPOSITORY",
              provider_ref="SYN::repo_read", checks=["existence", "activation", "package", "source_sha256"])
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
                activation="ACTIVE" if existence == "EXISTS" else "UNKNOWN", observed=obs if obs is not None else GOOD_OBS)


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
                          evidence if evidence is not None else ev_upstream(mm), ledger if ledger is not None else mm.ledger)


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
    other_dl = make("DelegationEnvelope", delegation_id="d2", principal_hash=f["pr"]["object_hash"], scope=["create_object"], max_mutations=2, expires_at="x")
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
        gg = gr(); mm.authorize_compensation(gg)
        return mm, ff, gg
    m, f, grant = comp_authorized()
    t(g, "valid_separate_grant_accepted", m.state == "COMPENSATION_AUTHORIZED")
    post_bad = rb_receipt(f, "EXISTS", obs={"exists": True})
    cr_bad = make("CompensationReceipt", receipt_id="cr", grant_hash=grant["object_hash"], readback_receipt_hash=post_bad["object_hash"], result="PASS")
    t(g, "compensation_without_predicate_pass_rejected", raises(lambda: m.record_compensation(cr_bad, post_bad), "predicate") and m.state == "COMPENSATION_AUTHORIZED")
    m, f, grant = comp_authorized()
    post_weak = rb_receipt(f, "ABSENT", level="PROVIDER_LOG", obs={"exists": False})
    cr_w = make("CompensationReceipt", receipt_id="cr", grant_hash=grant["object_hash"], readback_receipt_hash=post_weak["object_hash"], result="PASS")
    t(g, "post_compensation_readback_must_be_authoritative", raises(lambda: m.record_compensation(cr_w, post_weak), "authoritative") and m.state == "COMPENSATION_AUTHORIZED")
    m, f, grant = comp_authorized()
    post_ok = rb_receipt(f, "ABSENT", obs={"exists": False})
    cr_ok = make("CompensationReceipt", receipt_id="cr", grant_hash=grant["object_hash"], readback_receipt_hash=post_ok["object_hash"], result="PASS")
    m.record_compensation(cr_ok, post_ok)
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
        mm, ff = comp_ready(); gg = grant_of(); mm.authorize_compensation(gg)
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
        t(g, name, raises(lambda mm=mm, gg=gg, post=post: mm.record_compensation(comp_receipt_for(gg, post), post), text) and mm.state == "COMPENSATION_AUTHORIZED")
    mm, ff, gg = comp_authorized2(); post = rb_receipt(ff, "ABSENT", obs={"exists": False})
    t(g, "compensation_rejects_tampered_receipt_and_foreign_grant", raises(lambda: mm.record_compensation(stale(comp_receipt_for(gg, post), result="PASS", receipt_id="x"), post), "hash invalid")
      and raises(lambda: mm.record_compensation(make("CompensationReceipt", receipt_id="cr", grant_hash=Z, readback_receipt_hash=post["object_hash"], result="PASS"), post), "not bound to its grant")
      and raises(lambda: mm.record_compensation(make("CompensationReceipt", receipt_id="cr", grant_hash=gg["object_hash"], readback_receipt_hash=Z, result="PASS"), post), "not bound to post readback")
      and raises(lambda: mm.record_compensation(comp_receipt_for(gg, post, "FAIL"), post), "predicate not satisfied") and mm.state == "COMPENSATION_AUTHORIZED")
    mm, ff, gg = comp_authorized2(); post = rb_receipt(ff, "ABSENT", obs={"exists": False}); mm.record_compensation(comp_receipt_for(gg, post), post)
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
    bad_ledger = MODEL.ReplayLedger(os.path.join(ldir, "missing_dir", "x.txt"))   # parent missing: the write fails
    mm, ff = fixture(); mm.ledger = bad_ledger; to_prewrite(mm, ff)
    t(g, "failed_ledger_write_blocks_the_send_and_changes_nothing", not safe(lambda: mm.begin_execution("MUT-1", FP)) and mm.state == "PREWRITE_VALIDATED" and mm.mutations_sent == 0 and mm.remaining == 1)
    m, f, lease = sent_mission()
    t(g, "resume_requires_ledger_and_evidence", raises(lambda: Mission.resume(lease, f["cp"], f["bu"], "M-SYN-1", ev_upstream(m), None), "ReplayLedger")
      and raises(lambda: Mission.resume(lease, f["cp"], f["bu"], "M-SYN-1", None, m.ledger), "re-presented evidence")
      and raises(lambda: Mission.resume(lease, f["cp"], f["bu"], "M-SYN-1", {k: v for k, v in ev_upstream(m).items() if k != "tx"}, m.ledger), "missing tx"))
    t(g, "resume_rejects_foreign_mission_id", raises(lambda: rsm(lease, f, m, mission_id="OTHER-MISSION"), "another mission"))
    other_budget = make("MutationBudget", budget_id="bx", authority_hash=f["au"]["object_hash"], max_mutations=1, retries=0, expansion_allowed=False)
    t(g, "resume_rejects_original_budget_not_matching_evidence", raises(lambda: Mission.resume(lease, f["cp"], other_budget, "M-SYN-1", ev_upstream(m), m.ledger), "original budget does not match")
      and raises(lambda: Mission.resume(lease, f["cp"], stale(f["bu"], max_mutations=9), "M-SYN-1", ev_upstream(m), m.ledger), "hash invalid"))
    t(g, "resume_rejects_invalid_remaining_budget_values", all(raises(lambda v=v: rsm(remake(lease, remaining_budget=v), f, m), "remaining_budget invalid") for v in (-1, True, 1.5, "1")))
    t(g, "resume_rejects_malformed_consumed_ids", raises(lambda: rsm(remake(lease, consumed_authority_ids=["noseparator"]), f, m), "consumed ids invalid")
      and raises(lambda: rsm(remake(lease, consumed_authority_ids=["%s:MUT-1" % f["au"]["object_hash"]] * 2), f, m), "consumed ids invalid")
      and raises(lambda: rsm(remake(lease, consumed_authority_ids="x:y"), f, m), "consumed ids invalid"))
    t(g, "resume_rejects_lease_for_foreign_transaction", raises(lambda: rsm(remake(lease, transaction_id="TX-OTHER"), f, m), "does not match lease"))
    t(g, "resume_rejects_execution_receipt_not_matching_lease", raises(lambda: rsm(lease, f, m, evidence=dict(ev_upstream(m), execution_receipt=exec_receipt(f))), "does not match lease"))
    t(g, "resume_rejects_evidence_not_pinned_by_checkpoint", raises(lambda: rsm(lease, f, m, evidence=dict(ev_upstream(m), tx=remake(f["tx"], boundary="other"))), "checkpoint pin")
      and raises(lambda: rsm(lease, f, m, evidence=dict(ev_upstream(m), budget=remake(f["bu"], budget_id="other"))), "checkpoint pin"))
    t(g, "resume_rejects_inconsistent_delegation_capability_and_authority", raises(lambda: rsm(lease, f, m, evidence=dict(ev_upstream(m), delegation=remake(f["dl"], delegation_id="z"))), "does not match authority")
      and raises(lambda: rsm(lease, f, m, evidence=dict(ev_upstream(m), capability=remake(f["cb"], authority_hash=Z))), "does not match authority")
      and raises(lambda: rsm(lease, f, m, evidence=dict(ev_upstream(m), authority=remake(f["au"], authority_id="z"))), "does not match budget"))
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
    src_ids = set(re.findall(r'self\._rel\("(R\d+)"', open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcr_r2_model.py"), encoding="utf-8").read()))
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

    # ---- NO_ENTERPRISE_WRITES (structural)
    g = "NO_ENTERPRISE_WRITES"
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcr_r2_model.py")).read()
    t(g, "model_has_no_network_or_process_imports", not any(k in src for k in ("import socket", "import requests", "urllib", "subprocess", "http.client")))


def _exec_only_complete():
    m, f = fixture(); to_prewrite(m, f); m.begin_execution("MUT-1", FP); m.record_execution(exec_receipt(f))
    m._go("COMPLETE")


ACCEPT = ["STATE_MACHINE_VALID", "SCHEMA_VALIDATION", "AUTHORITY_INVARIANTS", "MUTATION_BUDGET_INVARIANTS",
          "REPLAY_GUARD_INVARIANTS", "CONTINUATION_INVARIANTS", "COMPENSATION_AUTHORITY_INVARIANTS",
          "OUTCOME_PREDICATE_MODEL", "COMMIT_UNKNOWN_HANDLING", "COMPLETION_EVIDENCE", "HARDENING_R2_0H", "HARDENING_R2_0I", "TELEMETRY_MODEL", "NO_ENTERPRISE_WRITES"]


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
