"""Tests for mission-level evidence-chain consistency (inconsistent chains are found; consistent chains from both adapters pass)."""
import copy
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
if os.environ.get("MCR3_OVERRIDE_DIR"):          # mutation harness: a mutated module shadows the real one
    sys.path.insert(0, os.environ["MCR3_OVERRIDE_DIR"])
import evc1  # noqa: E402
import mcr3_adapters as AD  # noqa: E402
import mcr3_chain as CH  # noqa: E402
import validate_mcr3_adapters as VA  # noqa: E402
import validate_mcr3_evc1 as VE  # noqa: E402
import validate_mcr3_hardening as H  # noqa: E402
from validate_mcr3_inherited import FP, exec_receipt, fixture, to_prewrite  # noqa: E402

T, G = {}, {}
NOW = "2027-01-15T00:00:00Z"


def t(group, name, ok):
    try:
        ok = ok() if callable(ok) else ok
    except Exception:
        ok = False
    T[name] = bool(ok)
    G.setdefault(group, []).append(name)


def reseal_all(events, edit):
    """Apply edit(list_of_dicts) and re-seal every event in place order (keeps each event internally valid)."""
    es = copy.deepcopy(events)
    edit(es)
    return [evc1.seal({k: v for k, v in e.items() if k != "integrity"}) for e in es]


def relink(es):
    for i, e in enumerate(es):
        e["correlation"]["causation_id"] = es[i - 1]["id"] if i else None
    return es


def rl(events, edit):
    """Edit, relink the causation path, then seal: keeps every event valid so only the intended rule is violated."""
    return reseal_all(events, lambda es: (edit(es), relink(es)))


def has(probs, text):
    return any(text in p for p in probs)


def run():
    nb = AD.Mcr3NativeAdapter()
    mc, _ = VA.complete_mission()
    full = nb.convert(mc, now=NOW)
    live, src = AD.load_r2_live_result(ROOT)
    hist = AD.Mcr2ReferenceAdapter().convert(live, now=NOW, source_ref=src)
    mv, _ = VA.validated_mission()
    part = nb.convert(mv, now=NOW)

    g = "CONSISTENT_CHAINS"
    t(g, "a_complete_native_chain_is_consistent", CH.check_mission_events(full) == [])
    t(g, "the_frozen_r2_chain_converted_by_adapter_a_is_consistent", CH.check_mission_events(hist) == [])
    t(g, "a_validated_but_uncompleted_chain_is_consistent", CH.check_mission_events(part) == [])
    m1, f1 = fixture(); to_prewrite(m1, f1); m1.begin_execution("MUT-1", FP); m1.record_execution(exec_receipt(f1))
    t(g, "a_provider_acknowledged_only_chain_is_consistent", CH.check_mission_events(nb.convert(m1, now=NOW)) == [])
    mm, ff, gg = H.comp_mission(2)
    mm.begin_compensation(); mm.record_compensation_failure(H.comp_exec(gg, cls="PROVIDER_ERROR")); mm.begin_compensation(); post = H.post_receipt(ff)
    mm.record_compensation(H.comp_receipt(gg, post), post, H.comp_exec(gg, attempt=2))
    t(g, "a_compensated_chain_is_consistent", CH.check_mission_events(nb.convert(mm, now=NOW)) == [])
    mu, fu, gu = H.comp_mission(1); mu.begin_compensation(); mu.record_compensation_failure(H.comp_exec(gu, cls="PROVIDER_ERROR"))
    t(g, "an_unrecoverable_chain_is_consistent", CH.check_mission_events(nb.convert(mu, now=NOW)) == [])
    m2, f2 = fixture(); m2.context_ready(f2["intent"], f2["pr"])
    t(g, "a_start_only_chain_is_consistent", CH.check_mission_events(nb.convert(m2, now=NOW)) == [])

    g = "INCONSISTENT_CHAINS"
    t(g, "empty_and_non_list_inputs_are_problems", CH.check_mission_events([]) == ["no events"] and CH.check_mission_events("x") == ["no events"] and CH.check_mission_events(None) == ["no events"])
    t(g, "an_invalid_event_is_reported_not_raised", has(CH.check_mission_events([{"x": 1}]), "not a valid"))
    bad = copy.deepcopy(full); bad[3]["claim"]["provider_acknowledged"] = False
    t(g, "an_unsealed_edit_is_reported", has(CH.check_mission_events(bad), "not a valid"))
    t(g, "a_duplicate_event_is_reported", has(CH.check_mission_events(full + [full[2]]), "duplicate"))
    t(g, "a_swapped_pair_is_reported_as_out_of_order_or_broken_causation", (lambda p: has(p, "out of order") or has(p, "predecessor"))(CH.check_mission_events([full[0], full[2], full[1]] + full[3:])))
    t(g, "a_dropped_middle_event_breaks_the_causal_path", has(CH.check_mission_events(full[:3] + full[4:]), "predecessor"))
    t(g, "events_of_two_missions_are_reported", has(CH.check_mission_events(reseal_all(full, lambda es: es[3]["correlation"].update(mission_id="M-OTHER-1"))), "missions"))
    t(g, "events_of_two_transactions_are_reported", has(CH.check_mission_events(reseal_all(full, lambda es: es[3]["correlation"].update(transaction_id="TX-OTHER-1"))), "transaction"))
    t(g, "two_starts_are_reported", has(CH.check_mission_events(rl(full, lambda es: es.insert(1, copy.deepcopy(es[0])))), "exactly one"))
    t(g, "a_start_that_is_not_first_is_reported", has(CH.check_mission_events(rl(full, lambda es: es.append(es.pop(0)))), "exactly one"))
    t(g, "a_disposition_that_is_not_last_is_reported", has(CH.check_mission_events(rl(full, lambda es: es.insert(2, es.pop()))), "come last"))
    t(g, "a_broken_causation_is_reported", has(CH.check_mission_events(reseal_all(full, lambda es: es[4]["correlation"].update(causation_id=es[1]["id"]))), "predecessor"))
    t(g, "a_first_event_with_a_cause_is_reported", has(CH.check_mission_events(reseal_all(full, lambda es: es[0]["correlation"].update(causation_id=es[3]["id"]))), "first event"))
    t(g, "decreasing_times_are_reported", has(CH.check_mission_events(reseal_all(full, lambda es: es[3].update(time="2026-01-01T00:00:00Z"))), "times decrease"))
    t(g, "a_gap_in_compensation_numbers_is_reported", has(CH.check_mission_events(reseal_all(nb.convert(mm, now=NOW), lambda es: [e["claim"].update(attempt_number=3) for e in es if e["type"] == "mcr.compensation.attempted"][:1])), "compensation attempt numbers"))
    t(g, "a_mutation_attempt_number_of_two_is_reported", has(CH.check_mission_events(reseal_all(full, lambda es: es[1]["claim"].update(attempt_number=2))), "mutation attempt numbers"))
    t(g, "a_commit_naming_another_readback_is_reported", has(CH.check_mission_events(reseal_all(full, lambda es: es[4]["claim"].update(readback_digest="9" * 64))), "commit observation names"))
    t(g, "an_outcome_naming_another_readback_is_reported", has(CH.check_mission_events(reseal_all(full, lambda es: es[5]["claim"].update(readback_digest="9" * 64))), "outcome evaluation names"))
    t(g, "a_commit_without_a_readback_is_reported", has(CH.check_mission_events(rl(full, lambda es: es.pop(3))), "readback"))
    t(g, "a_committed_state_over_an_absent_readback_is_reported", has(CH.check_mission_events(reseal_all(full, lambda es: es[3]["claim"].update(existence="ABSENT"))), "EXISTS readback"))
    t(g, "a_commit_without_an_execution_receipt_is_reported", has(CH.check_mission_events(rl(full, lambda es: es.pop(2))), "execution receipt"))
    t(g, "a_pass_outcome_without_commit_is_reported", has(CH.check_mission_events(rl(full, lambda es: es.pop(4))), "committed observation") or has(CH.check_mission_events(rl(full, lambda es: es.pop(4))), "names a readback"))
    t(g, "a_disposition_missing_a_chain_digest_is_reported", has(CH.check_mission_events(reseal_all(full, lambda es: es[-1]["claim"].update(chain_digests=es[-1]["claim"]["chain_digests"][1:]))), "lack the evidence digest"))
    t(g, "complete_with_a_short_chain_is_reported", has(CH.check_mission_events(reseal_all(full, lambda es: es[-1]["claim"].update(chain_digests=es[-1]["claim"]["chain_digests"][:13]))), "14-digest") or has(CH.check_mission_events(reseal_all(full, lambda es: es[-1]["claim"].update(chain_digests=es[-1]["claim"]["chain_digests"][:13]))), "lack the evidence"))
    t(g, "complete_without_a_pass_outcome_is_reported", has(CH.check_mission_events(reseal_all(full, lambda es: es[5]["claim"].update(result="UNKNOWN"))), "COMPLETE needs a PASS"))
    t(g, "validated_class_without_a_pass_outcome_is_reported", has(CH.check_mission_events(reseal_all(part, lambda es: es[5]["claim"].update(result="UNKNOWN"))), "OUTCOME_VALIDATED needs"))
    t(g, "acknowledged_class_over_an_unacknowledged_receipt_is_reported", has(CH.check_mission_events(reseal_all(nb.convert(m1, now=NOW), lambda es: (es[2]["claim"].update(call_class="PROVIDER_ERROR", provider_acknowledged=False)))), "PROVIDER_ACKNOWLEDGED needs"))
    t(g, "commit_observed_class_without_a_commit_event_is_reported", has(CH.check_mission_events(rl(part, lambda es: [es.pop(4) for _ in (0,)])), "commit"))
    t(g, "compensated_without_attempts_is_reported", has(CH.check_mission_events(rl(nb.convert(mm, now=NOW), lambda es: [es.remove(e) for e in [x for x in es if x["type"] == "mcr.compensation.attempted"]])), "COMPENSATED needs"))
    t(g, "unrecoverable_disposition_needs_the_unrecoverable_class", has(CH.check_mission_events(reseal_all(nb.convert(mu, now=NOW), lambda es: (es[-1]["claim"].update(outcome_class="COMMIT_UNKNOWN"), es[-1].update(outcome_class="COMMIT_UNKNOWN")))), "UNRECOVERABLE disposition"))
    t(g, "an_authoritative_claim_from_a_weak_level_is_stopped_by_the_event_contract_first", has(CH.check_mission_events(reseal_all(full, lambda es: es[3]["claim"].update(source_level="PROVIDER_LOG"))), "not a valid"))
    # --- targeted tests added after the first full mutation run
    m_none = VE.base("mcr.mission.started", VE.CLAIMS["mcr.mission.started"], correlation={"mission_id": None, "transaction_id": None, "correlation_id": "CORR-SYN-1", "causation_id": None})
    t(g, "a_chain_whose_only_event_has_no_mission_id_is_reported", has(CH.check_mission_events([m_none]), "missions"))
    no_tx = reseal_all(full, lambda es: [e["correlation"].update(transaction_id=None) for e in es[1:]])
    t(g, "events_without_a_transaction_id_are_reported", has(CH.check_mission_events(no_tx), "transaction"))
    commit_unknown_hist = reseal_all(hist, lambda es: es[4]["claim"].update(commit_state="UNKNOWN"))
    t(g, "a_commit_reading_of_unknown_needs_no_exists_readback", not has(CH.check_mission_events(commit_unknown_hist), "COMMITTED needs"))
    t(g, "a_pass_outcome_over_an_unknown_commit_is_reported", has(CH.check_mission_events(commit_unknown_hist), "PASS outcome needs a committed"))
    t(g, "a_committed_reading_after_a_failed_call_is_reported", has(CH.check_mission_events(reseal_all(full, lambda es: es[2]["claim"].update(call_class="PROVIDER_ERROR", provider_acknowledged=False))), "execution receipt before it"))
    t(g, "a_committed_reading_after_a_commit_unknown_call_is_not_reported_for_the_receipt", not has(CH.check_mission_events(reseal_all(full, lambda es: es[2]["claim"].update(call_class="COMMIT_UNKNOWN", provider_acknowledged=False))), "execution receipt before it"))
    dup14 = reseal_all(full, lambda es: es[-1]["claim"].update(chain_digests=es[-1]["claim"]["chain_digests"][:13] + [es[-1]["claim"]["chain_digests"][0]]))
    t(g, "fourteen_digests_with_a_repeat_are_not_a_full_chain", has(CH.check_mission_events(dup14), "14-digest"))
    fifteen = reseal_all(full, lambda es: es[-1]["claim"].update(chain_digests=es[-1]["claim"]["chain_digests"] + [es[-1]["claim"]["chain_digests"][0]]))
    t(g, "fifteen_digests_are_not_a_full_chain", has(CH.check_mission_events(fifteen), "14-digest"))
    t(g, "complete_without_an_outcome_event_is_reported", has(CH.check_mission_events(rl(full, lambda es: es.pop(5))), "COMPLETE needs a PASS"))
    t(g, "complete_without_a_commit_event_is_reported", has(CH.check_mission_events(rl(full, lambda es: es.pop(4))), "COMPLETE needs a PASS"))
    t(g, "validated_class_without_an_outcome_event_is_reported", has(CH.check_mission_events(rl(part, lambda es: es.pop(5))), "OUTCOME_VALIDATED needs"))
    ack = nb.convert(m1, now=NOW)
    t(g, "acknowledged_class_without_an_execution_receipt_is_reported", has(CH.check_mission_events(rl(ack, lambda es: es.pop(2))), "PROVIDER_ACKNOWLEDGED needs"))
    def unknown_commit_chain(es):
        es[3]["claim"].update(existence="ABSENT")
        es[4]["claim"].update(commit_state="UNKNOWN")
        es[5]["claim"].update(result="UNKNOWN")
        es[6]["claim"].update(disposition="INCOMPLETE", outcome_class="OUTCOME_UNKNOWN")
        es[6].update(disposition="INCOMPLETE", outcome_class="OUTCOME_UNKNOWN")
    ucc = reseal_all(hist, unknown_commit_chain)
    t(g, "a_consistent_chain_with_an_absent_readback_an_unknown_commit_and_an_unknown_outcome_has_no_problems", CH.check_mission_events(ucc) == [])
    t(g, "complete_with_an_unknown_commit_reading_is_reported", has(CH.check_mission_events(reseal_all(full, lambda es: es[4]["claim"].update(commit_state="UNKNOWN"))), "COMPLETE needs a PASS outcome and a COMMITTED"))
    t(g, "every_problem_message_is_a_string", all(isinstance(p, str) for p in CH.check_mission_events(full[:1] + full[2:3])))
    t(g, "a_hostile_list_never_raises", all(isinstance(CH.check_mission_events(x), list) for x in ([None], [1], ["a"], [[]], [{}], [full[0], None], [{"contract": "mcr-evidence/1"}])))


def main(argv):
    run()
    failed = sorted(n for n, ok in T.items() if not ok)
    groups = {gk: "PASS" if all(T[n] for n in names) else "FAIL" for gk, names in G.items()}
    digest = hashlib.sha256(json.dumps(sorted(T), separators=(",", ":")).encode()).hexdigest().upper()
    result = {"stage": "MCR3_EVIDENCE_CHAIN", "evidence_class": "SYNTHETIC/LOCAL", "tests": len(T), "failed": failed, "groups": groups, "tests_digest": digest, "network_calls": 0}
    out = json.dumps(result, indent=2, sort_keys=True)
    if "--out" in argv:
        with open(argv[argv.index("--out") + 1], "w", newline="\n") as fh:
            fh.write(out + "\n")
    print(out)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
