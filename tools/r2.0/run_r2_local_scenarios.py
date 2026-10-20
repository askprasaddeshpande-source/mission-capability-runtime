"""R2.0D (replay/continuation), R2.0E (compensation) and R2.0F (governance overhead) - LOCAL/SYNTHETIC.

No enterprise or network access. The provider is absent: provider/business latency is NOT modeled,
so the timings below are governance-only and descriptive, never an enterprise-overhead claim.
Usage: python tools/r2.0/run_r2_local_scenarios.py [--out PATH] [--timing-out PATH] [--n 2000]
"""
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcr_r2_model import GuardError, Mission, chash, eval_predicates, make  # noqa: E402
from validate_r2_outcome_model import (FP, GOOD_OBS, commit_obs, exec_receipt, fixture, outcome,  # noqa: E402
                                       rb_receipt, to_prewrite)

STEPS = ["prewrite", "begin_execution", "record_execution", "request_readback", "observe_readback",
         "decide_commit", "validate_outcome", "complete"]


def run_step(m, f, step, **kw):
    if step == "prewrite":
        to_prewrite(m, f)
    elif step == "begin_execution":
        m.begin_execution("MUT-1", FP)
    elif step == "record_execution":
        m.record_execution(exec_receipt(f, kw.get("call_class", "PROVIDER_RESPONSE_SUCCESS")))
    elif step == "request_readback":
        m.request_readback()
    elif step == "observe_readback":
        m.observe_readback(kw.get("rb") or rb_receipt(f))
    elif step == "decide_commit":
        rb = m.ev["readback"]
        m.decide_commit(commit_obs(rb, {"EXISTS": "COMMITTED", "ABSENT": "ABSENT"}.get(rb["existence"], "UNKNOWN")))
    elif step == "validate_outcome":
        rb = m.ev["readback"]
        m.validate_outcome(outcome(f, rb, eval_predicates(f["oc"]["predicates"], rb["observed"])))
    elif step == "complete":
        m.complete(make("CompletionReceipt", receipt_id="done", transaction_id="TX-SYN-1",
                        outcome_receipt_hash=m.ev["outcome"]["object_hash"], commit_observation_hash=m.ev["commit"]["object_hash"],
                        execution_receipt_hash=m.ev["execution_receipt"]["object_hash"], authority_hash=m.ev["authority"]["object_hash"]))


def evidence_of(m):
    e = {k: m.ev[k] for k in ("tx", "budget", "outcome_contract", "readback_contract", "authority")}
    if "execution_receipt" in m.ev:
        e["execution_receipt"] = m.ev["execution_receipt"]
    return e


def replay_blocked(m):
    """True if the (already consumed) mutation cannot be sent again from this mission object."""
    saved = m.state
    try:
        m.state = "PREWRITE_VALIDATED"
        m.begin_execution("MUT-1", FP)
        return False
    except GuardError:
        return True
    finally:
        m.state = saved


def crash_matrix():
    """Crash (persist a lease) after each step from 'prewrite' on, resume, and check invariants."""
    rows = []
    for k in range(1, len(STEPS)):          # after 'complete' there is nothing to resume
        m, f = fixture()
        for s in STEPS[:k]:
            run_step(m, f, s)
        lease = m.checkpoint_lease()
        r = Mission.resume(lease, f["cp"], f["bu"], "M-SYN-1", evidence=evidence_of(m))
        rows.append({"crash_after": STEPS[k - 1], "resumed_state": r.state,
                     "mutations_sent_before_crash": m.mutations_sent, "mutations_known_after_resume": r.mutations_sent,
                     "replay_blocked_on_resume": replay_blocked(r) if m.mutations_sent else None,
                     "remaining_budget_after_resume": r.remaining})
    return rows


def recover_after_send_crash():
    """Crash right after EXECUTION_STARTED: resume -> UNKNOWN -> readback -> COMPLETE with exactly one mutation."""
    m, f = fixture()
    run_step(m, f, "prewrite"); run_step(m, f, "begin_execution")
    r = Mission.resume(m.checkpoint_lease(), f["cp"], f["bu"], "M-SYN-1", evidence=evidence_of(m))
    out = {"resumed_state": r.state, "replay_blocked": replay_blocked(r)}
    for s in ("request_readback", "observe_readback", "decide_commit", "validate_outcome", "complete"):
        run_step(r, f, s)
    out.update(final_state=r.state, total_mutations_sent=r.mutations_sent, remaining_budget=r.remaining)
    return out


def tampered_resume_cases():
    m, f = fixture()
    run_step(m, f, "prewrite")
    lease = m.checkpoint_lease()
    res = {}
    evil = make("ExpectedOutcomeContract", outcome_contract_id="oc-evil", mission_id="M-SYN-1", transaction_id="TX-SYN-1",
                predicates=[{"field": "exists", "op": "eq", "expected": True}], frozen=True)
    ev = evidence_of(m)
    ev["outcome_contract"] = evil
    for name, fn in (("swapped_outcome_contract_rejected", lambda: Mission.resume(lease, f["cp"], f["bu"], "M-SYN-1", evidence=ev)),
                     ("budget_inflation_rejected", lambda: Mission.resume(dict(lease, remaining_budget=3), f["cp"], f["bu"], "M-SYN-1")),
                     ("foreign_checkpoint_rejected", lambda: Mission.resume(lease, dict(f["cp"], object_hash="0" * 64), f["bu"], "M-SYN-1"))):
        try:
            fn(); res[name] = False
        except GuardError:
            res[name] = True
    return res


def fault_injection():
    res = {}
    cases = (("provider_error_then_readback_unknown", "PROVIDER_ERROR", "AUTHORITATIVE_REPOSITORY", "UNKNOWN"),
             ("success_but_readback_via_logs_only", "PROVIDER_RESPONSE_SUCCESS", "PROVIDER_LOG", "EXISTS"),
             ("no_response_then_authoritative_absent", "CALL_SENT_NO_RESPONSE", "AUTHORITATIVE_REPOSITORY", "ABSENT"),
             ("success_and_authoritative_exists", "PROVIDER_RESPONSE_SUCCESS", "AUTHORITATIVE_REPOSITORY", "EXISTS"))
    for name, call_class, level, existence in cases:
        m, f = fixture()
        run_step(m, f, "prewrite"); run_step(m, f, "begin_execution"); run_step(m, f, "record_execution", call_class=call_class)
        run_step(m, f, "request_readback")
        obs = GOOD_OBS if existence == "EXISTS" else {"exists": False} if existence == "ABSENT" else {}
        run_step(m, f, "observe_readback", rb=rb_receipt(f, existence, level, obs=obs))
        run_step(m, f, "decide_commit")
        res[name] = {"state": m.state, "complete": m.state == "COMPLETE", "second_send_blocked": replay_blocked(m)}
    return res


def compensation_semantics():
    m, f = fixture()
    for s in ("prewrite", "begin_execution", "record_execution", "request_readback"):
        run_step(m, f, s)
    run_step(m, f, "observe_readback", rb=rb_receipt(f, obs=dict(GOOD_OBS, package="WRONG")))
    run_step(m, f, "decide_commit"); run_step(m, f, "validate_outcome")
    r = {"state_after_outcome_fail": m.state, "forward_budget_remaining": m.remaining}
    grant = make("CompensationGrant", grant_id="g", target="SYN_SYS", capability="delete_object", max_mutations=1,
                 preconditions=["object exists"], outcome_predicates=[{"field": "exists", "op": "eq", "expected": False}],
                 inherits_forward_authority=False, issued_by="OWNER-COMP")
    m.authorize_compensation(grant)
    r["compensation_budget_independent_of_forward"] = grant["max_mutations"] == 1 and m.remaining == 0
    post = rb_receipt(f, "ABSENT", obs={"exists": False})
    m.record_compensation(make("CompensationReceipt", receipt_id="c", grant_hash=grant["object_hash"],
                               readback_receipt_hash=post["object_hash"], result="PASS"), post)
    r["final_state"] = m.state
    r["original_mission_reached_complete"] = False
    return r


def overhead(n):
    names = ["context_compile", "authority_validation", "contract_fingerprint", "binding", "checkpoint",
             "receipt_generation", "readback_validation", "outcome_predicate"]
    gov = {k: [] for k in names}
    for _ in range(n):
        t = time.perf_counter_ns(); m, f = fixture(); gov["context_compile"].append(time.perf_counter_ns() - t)
        t = time.perf_counter_ns(); m.context_ready(f["intent"], f["pr"]); m.authorize(f["dl"], f["au"], f["bu"]); gov["authority_validation"].append(time.perf_counter_ns() - t)
        t = time.perf_counter_ns(); chash({"fp": FP, "tool": "x"}); gov["contract_fingerprint"].append(time.perf_counter_ns() - t)
        t = time.perf_counter_ns(); m.bind(f["cb"], f["pb"]); gov["binding"].append(time.perf_counter_ns() - t)
        t = time.perf_counter_ns(); m.prewrite_validate(f["tx"], f["oc"], f["rc"], f["cp"]); gov["checkpoint"].append(time.perf_counter_ns() - t)
        t = time.perf_counter_ns(); m.begin_execution("MUT-1", FP); m.record_execution(exec_receipt(f)); gov["receipt_generation"].append(time.perf_counter_ns() - t)
        t = time.perf_counter_ns(); m.request_readback(); rb = rb_receipt(f); m.observe_readback(rb); m.decide_commit(commit_obs(rb, "COMMITTED")); gov["readback_validation"].append(time.perf_counter_ns() - t)
        t = time.perf_counter_ns(); m.validate_outcome(outcome(f, rb, "PASS")); gov["outcome_predicate"].append(time.perf_counter_ns() - t)

    def q(xs, p):
        return sorted(xs)[min(len(xs) - 1, int(len(xs) * p))]
    stats = {k: {"median_us": round(statistics.median(v) / 1e3, 1), "p95_us": round(q(v, .95) / 1e3, 1)} for k, v in gov.items()}
    total = [sum(gov[k][i] for k in names) for i in range(n)]
    stats["total_governance"] = {"median_us": round(statistics.median(total) / 1e3, 1), "p95_us": round(q(total, .95) / 1e3, 1)}
    return {"n": n, "unit": "microseconds", "provider_latency_modeled": False, "steps": stats,
            "note": "single machine, in-process, no provider; descriptive only; no productivity or enterprise-overhead claim"}


def main(argv):
    n = int(argv[argv.index("--n") + 1]) if "--n" in argv else 2000
    d = {"crash_matrix": crash_matrix(), "recover_after_send_crash": recover_after_send_crash(), "tampered_resume": tampered_resume_cases()}
    det = {"R2_0_D_continuation": d, "fault_injection": fault_injection(), "R2_0_E_compensation": compensation_semantics()}
    fi = det["fault_injection"]
    checks = {
        "recovery_blocks_replay": d["recover_after_send_crash"]["replay_blocked"] is True,
        "recovery_reaches_complete_with_one_mutation": d["recover_after_send_crash"]["final_state"] == "COMPLETE" and d["recover_after_send_crash"]["total_mutations_sent"] == 1,
        "every_post_send_crash_blocks_replay": all(r["replay_blocked_on_resume"] is True for r in d["crash_matrix"] if r["mutations_sent_before_crash"]),
        "no_crash_point_restores_budget": all(r["mutations_known_after_resume"] == r["mutations_sent_before_crash"] for r in d["crash_matrix"]),
        "pre_send_crash_keeps_full_budget": all(r["remaining_budget_after_resume"] == 1 for r in d["crash_matrix"] if not r["mutations_sent_before_crash"]),
        "tampering_rejected": all(d["tampered_resume"].values()),
        "unknown_or_nonauthoritative_never_complete": not fi["provider_error_then_readback_unknown"]["complete"] and not fi["success_but_readback_via_logs_only"]["complete"]
        and fi["provider_error_then_readback_unknown"]["state"] == "COMMIT_STATE_UNKNOWN" and fi["success_but_readback_via_logs_only"]["state"] == "COMMIT_STATE_UNKNOWN",
        "absent_is_fail_closed": fi["no_response_then_authoritative_absent"]["state"] == "FAILED_AFTER_POSSIBLE_MUTATION",
        "every_fault_case_blocks_second_send": all(v["second_send_blocked"] for v in fi.values()),
        "compensation_separate_and_not_completion": det["R2_0_E_compensation"]["final_state"] == "COMPENSATED" and det["R2_0_E_compensation"]["compensation_budget_independent_of_forward"],
    }
    det.update(checks=checks, evidence_class="SYNTHETIC/LOCAL", enterprise_writes=0, network_calls=0,
               local_scenarios="PASS" if all(checks.values()) else "FAIL")
    det["digest"] = chash(det)
    out = json.dumps(det, indent=2, sort_keys=True)
    if "--out" in argv:
        with open(argv[argv.index("--out") + 1], "w", newline="\n") as fh:
            fh.write(out + "\n")
    if "--timing-out" in argv:
        with open(argv[argv.index("--timing-out") + 1], "w", newline="\n") as fh:
            fh.write(json.dumps({"evidence_class": "LOCAL", "governance_overhead": overhead(n)}, indent=2, sort_keys=True) + "\n")
    print(out)
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
