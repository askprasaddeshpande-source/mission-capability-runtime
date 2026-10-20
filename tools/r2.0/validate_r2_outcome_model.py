"""R2.0A deterministic validator. Synthetic/local only; makes no enterprise or network call.

Usage: python tools/r2.0/validate_r2_outcome_model.py [--out PATH] [--emit-schemas DIR]
Exit 0 only if every acceptance group passes. Output is deterministic (no timestamps/timings).
"""
import json
import os
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
    try:
        fn()
    except (GuardError, SchemaError) as e:
        return text is None or text in str(e)
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
        r = Mission.resume(lease, f["cp"], f["bu"], "M-SYN-1")
    except GuardError:
        r = None
    t(g, "resume_preserves_transaction_identity", r is not None and r.transaction_id == m.transaction_id)
    t(g, "resume_inherits_consumed_set", r is not None and r.consumed == m.consumed and r.remaining == 1)
    t(g, "resume_cannot_exceed_remaining", r is not None and r.remaining <= f["cp"]["remaining_budget"] - 1)
    inflated = make("ContinuationLease", **{k: v for k, v in lease.items() if k not in ("kind", "object_hash")} | {"remaining_budget": 9})
    t(g, "inflated_lease_rejected", raises(lambda: Mission.resume(inflated, f["cp"], f["bu"], "M-SYN-1"), "enlarge"))
    other_cp = make("PreMutationCheckpoint", checkpoint_id="cpZ", transaction_hash="h", budget_hash="h", outcome_contract_hash="h", readback_contract_hash="h", remaining_budget=2)
    t(g, "lease_bound_to_checkpoint", raises(lambda: Mission.resume(lease, other_cp, f["bu"], "M-SYN-1"), "not bound"))
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
                          preconditions=["object exists"], outcome_predicates=[{"field": "exists", "op": "eq", "expected": False}],
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
    t(g, "completion_receipt_persisted_in_mission", m.ev.get("completion") is cr and verify_hash(m.ev["completion"]))
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
    t(g, "wrong_transaction_completion_rejected", raises(lambda: m.complete(done(transaction_id="TX-OTHER")), "correlation") and "completion" not in m.ev)
    ok = True
    for fld in ("outcome_receipt_hash", "commit_observation_hash", "execution_receipt_hash", "authority_hash"):
        ok = ok and raises(lambda fld=fld: m.complete(done(**{fld: "0" * 64})), "chain broken") and "completion" not in m.ev and m.state == "OUTCOME_VALIDATED"
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

    def ev_upstream(mm):
        return {k: mm.ev[k] for k in ("intent", "principal", "delegation", "capability", "provider", "tx", "budget", "outcome_contract",
                                      "readback_contract", "authority")}
    m, f, lease = sent_mission()
    bad_state = dict(lease, state_at_checkpoint="OUTCOME_VALIDATED")
    t(g, "lease_with_invalid_hash_rejected", raises(lambda: Mission.resume(bad_state, f["cp"], f["bu"], "M-SYN-1", evidence=ev_upstream(m)), "hash invalid"))
    forged = remake(lease, state_at_checkpoint="OUTCOME_VALIDATED")
    try:
        r = Mission.resume(forged, f["cp"], f["bu"], "M-SYN-1", evidence=ev_upstream(m))
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
        ok = ok and raises(lambda ev=ev: Mission.resume(lease, f["cp"], f["bu"], "M-SYN-1", evidence=ev), "no downstream")
    t(g, "resume_refuses_downstream_evidence_slots", ok)
    t(g, "lease_state_inconsistent_with_consumed_rejected",
      raises(lambda: Mission.resume(remake(lease, consumed_authority_ids=[]), f["cp"], f["bu"], "M-SYN-1", evidence=ev_upstream(m)), "inconsistent")
      and raises(lambda: Mission.resume(remake(lease, state_at_checkpoint="PREWRITE_VALIDATED"), f["cp"], f["bu"], "M-SYN-1", evidence=ev_upstream(m)), "inconsistent"))
    t(g, "lease_consumed_for_other_authority_rejected",
      raises(lambda: Mission.resume(remake(lease, consumed_authority_ids=["OTHERHASH:MUT-1"]), f["cp"], f["bu"], "M-SYN-1", evidence=ev_upstream(m)), "does not belong"))
    t(g, "lease_unknown_mutation_rejected",
      raises(lambda: Mission.resume(remake(lease, mutation_id="MUT-X"), f["cp"], f["bu"], "M-SYN-1", evidence=ev_upstream(m)), "inconsistent"))
    t(g, "resume_wrong_kind_evidence_rejected",
      raises(lambda: Mission.resume(lease, f["cp"], f["bu"], "M-SYN-1", evidence=dict(ev_upstream(m), intent=f["pr"])), "wrong kind"))

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
        ok = ok and raises(lambda mm=mm, cr_=cr_: mm.complete(cr_), "authoritative EXISTS") and mm.state == "OUTCOME_VALIDATED" and "completion" not in mm.ev
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
    t(g, "rehashed_checkpoint_with_other_pins_blocked", blocked("checkpoint", remake(mm0.ev["checkpoint"], budget_hash="0" * 64), "pins"))
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

    # ---- NO_ENTERPRISE_WRITES (structural)
    g = "NO_ENTERPRISE_WRITES"
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcr_r2_model.py")).read()
    t(g, "model_has_no_network_or_process_imports", not any(k in src for k in ("import socket", "import requests", "urllib", "subprocess", "http.client")))


def _exec_only_complete():
    m, f = fixture(); to_prewrite(m, f); m.begin_execution("MUT-1", FP); m.record_execution(exec_receipt(f))
    m._go("COMPLETE")


ACCEPT = ["STATE_MACHINE_VALID", "SCHEMA_VALIDATION", "AUTHORITY_INVARIANTS", "MUTATION_BUDGET_INVARIANTS",
          "REPLAY_GUARD_INVARIANTS", "CONTINUATION_INVARIANTS", "COMPENSATION_AUTHORITY_INVARIANTS",
          "OUTCOME_PREDICATE_MODEL", "COMMIT_UNKNOWN_HANDLING", "COMPLETION_EVIDENCE", "HARDENING_R2_0H", "TELEMETRY_MODEL", "NO_ENTERPRISE_WRITES"]


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
