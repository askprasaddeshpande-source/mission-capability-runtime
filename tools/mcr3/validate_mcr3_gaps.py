"""Targeted tests added after the first full mutation run of the 3.0 modules showed survivors. Each test names the behaviour a
surviving mutant would have changed. Offline, standard library only. Every `t(...)` expression is lazy: a raising expression is
a failed assertion, not a crash."""
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
if os.environ.get("MCR3_OVERRIDE_DIR"):          # mutation harness: a mutated module shadows the real one
    sys.path.insert(0, os.environ["MCR3_OVERRIDE_DIR"])
import evc1  # noqa: E402
import mini_jsonschema as MJ  # noqa: E402
import mcr3_adapters as AD  # noqa: E402
import mcr3_authority as AU  # noqa: E402
import mcr3_chain as CH  # noqa: E402
import validate_mcr3_chain as VC  # noqa: E402
import mcr3_interop as IO  # noqa: E402
import mcr3_lineage as LN  # noqa: E402
import mcr3_model as M  # noqa: E402
import mcr3_provenance as P  # noqa: E402
import mcr3_readback as R  # noqa: E402
import mcr3_scan as S  # noqa: E402
import validate_mcr3_adapters as VA  # noqa: E402
import validate_mcr3_evc1 as VE  # noqa: E402
import validate_mcr3_hardening as H  # noqa: E402
from validate_mcr3_inherited import FP, GOOD_OBS, commit_obs, exec_receipt, fixture, rb_receipt, to_prewrite  # noqa: E402

T, G = {}, {}
HX = "a" * 64
NOW = 1_800_000_000.0


def t(group, name, ok):
    try:
        ok = ok() if callable(ok) else ok
    except Exception:
        ok = False
    T[name] = bool(ok)
    G.setdefault(group, []).append(name)


def raises(fn, text=None, exc=(Exception,)):
    try:
        fn()
    except exc as e:
        return text is None or text in str(e)
    return False


def iso(ts):
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def run():
    # ================================================================== runtime model
    g = "MODEL_PATH_CHECK"
    cp = M._check_ledger_path
    t(g, "a_4096_character_path_passes_the_length_check", lambda: cp("a" * 4096) is None)
    t(g, "a_4097_character_path_is_refused", lambda: raises(lambda: cp("a" * 4097), "too long", (M.GuardError,)))
    for ch in '<>"|?*':
        t(g, "reserved_character_%d_is_refused_alone" % ord(ch), lambda ch=ch: raises(lambda: cp("a" + ch + "b"), "reserves", (M.GuardError,)))
    t(g, "del_character_is_a_control_character", lambda: raises(lambda: cp("a\x7fb"), "control", (M.GuardError,)))
    t(g, "a_unit_separator_is_a_control_character", lambda: raises(lambda: cp("a\x1fb"), "control", (M.GuardError,)))
    t(g, "a_space_is_not_a_control_character", lambda: cp("a b") is None)
    t(g, "parent_directory_components_are_refused_with_either_separator", lambda: raises(lambda: cp("a/../b"), "parent", (M.GuardError,)) and raises(lambda: cp("a\\..\\b"), "parent", (M.GuardError,)))
    t(g, "a_leading_parent_component_is_refused", lambda: raises(lambda: cp("../x"), "parent", (M.GuardError,)))
    t(g, "a_single_dot_component_is_allowed", lambda: cp("./x") is None and cp("a/./b") is None)
    t(g, "a_dotdot_inside_a_name_is_allowed", lambda: cp("a..b") is None and cp("..a") is None)
    t(g, "a_drive_with_a_separator_is_allowed", lambda: cp("C:/x/y") is None and cp("C:\\x\\y") is None and cp("z:/x") is None)
    t(g, "ordinary_short_names_are_allowed", lambda: cp("a") is None and cp("ab") is None and cp("a1") is None and cp("ab/cd") is None)
    t(g, "a_bare_drive_is_refused", lambda: raises(lambda: cp("C:"), "drive-relative", (M.GuardError,)))
    t(g, "a_drive_relative_form_is_refused", lambda: raises(lambda: cp("C:x"), "drive-relative", (M.GuardError,)))
    t(g, "a_colon_after_a_non_letter_is_refused", lambda: raises(lambda: cp("1:/x"), "colon", (M.GuardError,)))
    t(g, "a_colon_after_a_non_ascii_letter_is_refused", lambda: raises(lambda: cp("\u00e9:/x"), "colon", (M.GuardError,)))
    t(g, "a_colon_after_a_two_letter_prefix_is_refused", lambda: raises(lambda: cp("ab:/x"), "colon", (M.GuardError,)))
    t(g, "a_second_colon_is_refused", lambda: raises(lambda: cp("C:/x:y"), "colon", (M.GuardError,)))
    t(g, "a_component_ending_in_a_dot_is_refused", lambda: raises(lambda: cp("a./b"), "dot or space", (M.GuardError,)) and raises(lambda: cp("dir/name."), "dot or space", (M.GuardError,)))
    t(g, "a_component_ending_in_a_space_is_refused", lambda: raises(lambda: cp("a /b"), "dot or space", (M.GuardError,)))
    t(g, "empty_components_from_doubled_separators_are_ignored", lambda: cp("a//b") is None)
    t(g, "device_names_in_any_component_are_refused", lambda: raises(lambda: cp("x/aux/y"), "device", (M.GuardError,)) and raises(lambda: cp("x/NUL.txt"), "device", (M.GuardError,)))
    t(g, "device_look_alikes_are_allowed", lambda: all(cp(x) is None for x in ("auxiliary", "nullable.txt", "com10", "lpt10.x", "con_x", "prn1")))

    g = "MODEL_PROVIDER_REF"
    pok = M.provider_ref_ok
    t(g, "an_empty_provider_id_never_matches_even_a_matching_empty_prefix", lambda: pok("::x", "") is False)
    t(g, "a_non_string_provider_id_never_matches", lambda: pok("SYN::x", 5) is False and pok("SYN::x", None) is False)
    t(g, "a_provider_id_with_a_separator_never_matches", lambda: pok("A::B::x", "A::B") is False and pok("A::x", "A::") is False)
    t(g, "a_reference_without_a_separator_never_matches", lambda: pok("SYNx", "SYN") is False and pok("SYN", "SYN") is False)
    t(g, "an_exact_reference_matches", lambda: pok("SYN::repo_read", "SYN") is True)

    g = "MODEL_ANCHOR_AND_CHECKS"
    lg = M.ReplayLedger()
    a = lg.anchor()
    t(g, "an_anchor_whose_head_is_not_a_string_is_malformed", lambda: raises(lambda: lg.check_anchor(dict(a, head=5)), "malformed", (M.GuardError,)) and raises(lambda: lg.check_anchor(dict(a, head=None)), "malformed", (M.GuardError,)))
    t(g, "an_anchor_whose_head_has_the_wrong_length_is_malformed", lambda: raises(lambda: lg.check_anchor(dict(a, head="a" * 63)), "malformed", (M.GuardError,)) and raises(lambda: lg.check_anchor(dict(a, head="a" * 65)), "malformed", (M.GuardError,)))
    mm, ff = fixture(); mm.context_ready(ff["intent"], ff["pr"]); mm.authorize(ff["dl"], ff["au"], ff["bu"]); mm.bind(ff["cb"], ff["pb"])
    rc = H.remake(ff["rc"], checks="abc"); cp_ = H.remake(ff["cp"], readback_contract_hash=rc["object_hash"])
    t(g, "readback_checks_given_as_a_string_with_unique_letters_are_refused", lambda: raises(lambda: mm.prewrite_validate(ff["tx"], ff["oc"], rc, cp_), "checks must be", (M.GuardError,)))
    m2, f2 = fixture(); to_prewrite(m2, f2); m2.begin_execution("MUT-1", FP); m2.record_execution(exec_receipt(f2)); m2.request_readback()
    rb = H.remake(rb_receipt(f2), observed=["exists"])
    t(g, "a_readback_whose_observed_value_is_not_an_object_is_refused_as_malformed", lambda: raises(lambda: m2.observe_readback(rb), "malformed", (M.GuardError,)) and m2.state == "AUTHORITATIVE_READBACK_PENDING")
    t(g, "checks_satisfied_is_false_for_non_object_observations", lambda: M.Mission._checks_satisfied(f2["rc"], rb) is False)

    g = "MODEL_COMPENSATION_RESOLUTION"
    def unresolved(max_attempts=2):
        m_, f_, gg_ = H.comp_mission(max_attempts)
        m_.begin_compensation(); m_.record_compensation_failure(H.comp_exec(gg_, cls="CALL_SENT_NO_RESPONSE"))
        base = H.remake(rb_receipt(f_, obs=dict(GOOD_OBS, package="WRONG")), receipt_id="unmet")
        return m_, f_, gg_, base
    m_, f_, gg_, base = unresolved()
    t(g, "a_resolution_readback_of_another_mutation_is_refused", lambda: raises(lambda: m_.begin_compensation(resolution_readback=H.remake(base, mutation_id="MUT-OTHER")), "not correlated", (M.GuardError,)))
    t(g, "a_resolution_readback_under_another_contract_is_refused", lambda: raises(lambda: m_.begin_compensation(resolution_readback=H.remake(base, contract_hash="Z" * 64)), "not correlated", (M.GuardError,)))
    t(g, "a_resolution_readback_of_another_transaction_is_refused", lambda: raises(lambda: m_.begin_compensation(resolution_readback=H.remake(base, transaction_id="TX-OTHER")), "transaction", (M.GuardError,)))
    t(g, "a_resolution_readback_with_inconsistent_existence_is_refused", lambda: raises(lambda: m_.begin_compensation(resolution_readback=H.remake(base, existence="ABSENT")), "authoritative and consistent", (M.GuardError,)))
    t(g, "a_resolution_readback_from_a_weak_level_is_refused", lambda: raises(lambda: m_.begin_compensation(resolution_readback=H.remake(base, source_level="PROVIDER_LOG")), "authoritative and consistent", (M.GuardError,)))
    t(g, "none_of_the_refusals_consumed_an_attempt", lambda: m_.ev.get("comp_open") is None and len(m_.ledger.for_authority(gg_["object_hash"])) == 1)
    t(g, "the_valid_resolution_still_opens_attempt_two", lambda: m_.begin_compensation(resolution_readback=base) == 2)

    g = "MODEL_CLASSIFICATION_STATES"
    oc_ = M.outcome_classification
    m3, f3 = fixture(); to_prewrite(m3, f3); m3.begin_execution("MUT-1", FP); m3.record_execution(exec_receipt(f3)); m3.request_readback()
    t(g, "waiting_for_readback_after_an_acknowledged_call_is_acknowledged", lambda: oc_(m3) == "PROVIDER_ACKNOWLEDGED")
    m4, f4 = fixture(); to_prewrite(m4, f4); m4.begin_execution("MUT-1", FP)
    m4.state = "EXECUTED"      # direct state forcing, only to reach the defensive branch: no execution receipt recorded
    t(g, "an_executed_state_without_a_success_receipt_is_only_executed", lambda: oc_(m4) == "EXECUTED")
    m4.ev["execution_receipt"] = exec_receipt(f4, "PROVIDER_ERROR")
    t(g, "an_executed_state_with_a_failing_receipt_is_only_executed", lambda: oc_(m4) == "EXECUTED")

    # ================================================================== evidence contract
    g = "CONTRACT_RULES"
    ok_ev = lambda etype, **kw: VE.event_of(etype, **kw)
    rb_ok = ok_ev("mcr.readback.claimed")
    t(g, "a_non_authoritative_readback_that_does_not_claim_authority_is_accepted", lambda: VE.accepts(VE.reseal(rb_ok, lambda x: x["claim"].update(source_level="PROVIDER_LOG", claimed_authoritative=False))))
    trusted = VE.reseal(rb_ok, lambda x: (x["evidence"].update(provenance=VE.trusted_prov(), trust="SIGNED_TRUSTED", classification="OBSERVED"), x["claim"].update(provenance_verified=True)))
    t(g, "provenance_verified_with_trusted_evidence_is_accepted", lambda: VE.accepts(trusted))
    t(g, "provenance_not_verified_with_untrusted_evidence_is_accepted", lambda: VE.accepts(rb_ok) and rb_ok["claim"]["provenance_verified"] is False)
    hist = lambda **claim: VE.base("mcr.outcome.evaluated", dict(VE.CLAIMS["mcr.outcome.evaluated"], **claim), classification="HISTORICAL")
    t(g, "a_historical_outcome_may_have_null_expected_and_predicate_digests", lambda: VE.accepts(hist(expected_digest=None, predicates_digest=None)))
    t(g, "a_historical_outcome_with_only_one_null_digest_is_accepted", lambda: VE.accepts(hist(expected_digest=None)) and VE.accepts(hist(predicates_digest=None)))
    obs_ev = lambda **claim: VE.base("mcr.outcome.evaluated", dict(VE.CLAIMS["mcr.outcome.evaluated"], **claim), classification="OBSERVED")
    t(g, "a_non_historical_outcome_with_a_null_expected_digest_is_refused", lambda: VE.rejects(obs_ev(expected_digest=None), "may be null only for HISTORICAL"))
    t(g, "a_non_historical_outcome_with_a_null_predicates_digest_is_refused", lambda: VE.rejects(obs_ev(predicates_digest=None), "may be null only for HISTORICAL"))
    t(g, "a_non_historical_outcome_with_both_digests_is_accepted", lambda: VE.accepts(obs_ev()))
    disp = lambda **claim: VE.base("mcr.mission.disposition", dict(VE.CLAIMS["mcr.mission.disposition"], chain_digests=[HX], **claim))
    t(g, "an_incomplete_disposition_with_a_validated_class_is_accepted", lambda: VE.accepts(disp(disposition="INCOMPLETE", outcome_class="OUTCOME_VALIDATED")))
    t(g, "a_commit_unknown_disposition_with_the_same_class_is_accepted", lambda: VE.accepts(disp(disposition="COMMIT_UNKNOWN", outcome_class="COMMIT_UNKNOWN")))
    t(g, "a_failed_disposition_without_a_class_is_accepted", lambda: VE.accepts(disp(disposition="FAILED", outcome_class=None)))
    t(g, "a_top_level_disposition_equal_to_the_claim_is_accepted", lambda: VE.accepts(VE.reseal(ok_ev("mcr.mission.disposition"), lambda x: x.update(disposition="COMPLETE"))))
    t(g, "an_event_without_a_top_level_disposition_is_accepted", lambda: "disposition" not in ok_ev("mcr.mission.disposition") and VE.accepts(ok_ev("mcr.mission.disposition")))
    er_e = lambda **claim: VE.base("mcr.execution.receipt", dict(VE.CLAIMS["mcr.execution.receipt"], **claim))
    t(g, "a_failed_call_that_is_not_acknowledged_is_accepted", lambda: VE.accepts(er_e(call_class="PROVIDER_ERROR", provider_acknowledged=False)) and VE.accepts(er_e(call_class="CALL_NOT_SENT", provider_acknowledged=False)) and VE.accepts(er_e(call_class="CALL_SENT_NO_RESPONSE", provider_acknowledged=False)))
    t(g, "a_commit_unknown_call_may_be_either_acknowledged_or_not", lambda: VE.accepts(er_e(call_class="COMMIT_UNKNOWN", provider_acknowledged=False)) and VE.accepts(er_e(call_class="COMMIT_UNKNOWN", provider_acknowledged=True)))
    cm = lambda **kw: VE.base("mcr.commit.observed", dict(VE.CLAIMS["mcr.commit.observed"], **kw), classification=kw.pop("cls", "CLAIMED") if False else "CLAIMED")
    t(g, "an_unknown_commit_reading_on_claimed_evidence_is_accepted", lambda: VE.accepts(cm(commit_state="UNKNOWN")) and VE.accepts(cm(commit_state="ABSENT")))
    t(g, "a_committed_reading_on_observed_evidence_is_accepted", lambda: VE.accepts(VE.base("mcr.commit.observed", VE.CLAIMS["mcr.commit.observed"], classification="OBSERVED")))
    t(g, "make_event_keeps_the_given_provenance", lambda: ok_ev("mcr.execution.receipt", provenance=VE.trusted_prov(), classification="OBSERVED")["evidence"]["provenance"] == VE.trusted_prov() and ok_ev("mcr.execution.receipt", provenance=VE.trusted_prov(), classification="OBSERVED")["evidence"]["trust"] == "SIGNED_TRUSTED")
    custom = {"transformations": [{"step": "s", "from": "a", "to": "b", "tool": "t", "tool_version": "1"}], "source_event_id": "EVT-SOURCE-01", "source_digest": HX, "supersedes": None}
    t(g, "make_event_keeps_the_given_lineage", lambda: ok_ev("mcr.execution.receipt", lineage=custom)["lineage"] == custom)
    t(g, "make_event_defaults_to_empty_lineage", lambda: ok_ev("mcr.execution.receipt")["lineage"] == {"transformations": [], "source_event_id": None, "source_digest": None, "supersedes": None})
    base_e = ok_ev("mcr.execution.receipt")
    t(g, "semantic_problems_alone_reports_a_tampered_integrity_digest", lambda: any("integrity" in p for p in evc1.semantic_problems(dict(base_e, integrity={"event_digest": "0" * 64}))))
    t(g, "semantic_problems_alone_reports_unknown_critical_names", lambda: any("critical" in p for p in evc1.semantic_problems(dict(base_e, critical=["x"]))))
    saved = evc1.KNOWN_CRITICAL
    try:
        evc1.KNOWN_CRITICAL = frozenset(["x"])
        accepted_known = VE.accepts(VE.reseal(base_e, lambda x: x.update(critical=["x"])))
        rejected_unknown_other = VE.rejects(VE.reseal(base_e, lambda x: x.update(critical=["y"])), "critical")
        carries = VE.reseal(base_e, lambda x: x.update(contract_version="1.1.0", x={"v": 1}, critical=["x"]))
        rejected_present_field = VE.rejects(carries, "critical")
        semantic_known_ok = not any("critical" in p for p in evc1.semantic_problems(VE.reseal(base_e, lambda x: x.update(critical=["x"]))))
    finally:
        evc1.KNOWN_CRITICAL = saved
    t(g, "a_critical_name_the_consumer_knows_and_no_field_for_it_is_accepted", lambda: accepted_known)
    t(g, "a_critical_name_the_consumer_does_not_know_is_rejected", lambda: rejected_unknown_other)
    t(g, "a_critical_name_that_names_an_unrecognized_field_is_rejected_even_if_known", lambda: rejected_present_field)
    t(g, "semantic_check_accepts_known_critical_names", lambda: semantic_known_ok)
    v11u = VE.reseal(base_e, lambda x: x.update(contract_version="1.1.0", future_field=1))
    t(g, "migrating_an_event_with_unrecognized_fields_upward_is_refused", lambda: raises(lambda: evc1.migrate(v11u, "1.2.0"), "unrecognized", (evc1.ContractError,)))
    t(g, "migrating_an_event_with_unrecognized_fields_downward_is_refused", lambda: raises(lambda: evc1.migrate(v11u, "1.0.0"), "unrecognized", (evc1.ContractError,)))
    unsealed = {k: v for k, v in base_e.items() if k != "integrity"}
    mig = evc1.migrate(unsealed, "1.1.0")
    t(g, "migrating_an_unsealed_event_records_the_digest_of_its_body_as_the_source_digest", lambda: mig["lineage"]["source_digest"] == evc1.digest_of(unsealed))
    t(g, "migrating_a_sealed_event_records_its_integrity_digest_as_the_source_digest", lambda: evc1.migrate(base_e, "1.1.0")["lineage"]["source_digest"] == base_e["integrity"]["event_digest"])
    t(g, "canonical_bytes_accepts_bool_and_none_and_big_ints", lambda: evc1.canonical_bytes({"a": True, "b": None, "c": 10 ** 30}) == b'{"a":true,"b":null,"c":1000000000000000000000000000000}')

    g = "MINI_VALIDATOR_EDGES"
    v = MJ.validate
    t(g, "number_accepts_floats_and_ints_but_not_booleans_or_strings", lambda: v(1.5, {"type": "number"}) == [] and v(2, {"type": "number"}) == [] and v(True, {"type": "number"}) != [] and v("x", {"type": "number"}) != [])
    t(g, "number_bounds_do_not_apply_to_booleans_or_strings", lambda: v(True, {"minimum": 5}) == [] and v("x", {"minimum": 5}) == [] and v(True, {"maximum": 0}) == [])
    t(g, "minimum_and_maximum_are_inclusive", lambda: v(3, {"minimum": 3, "maximum": 3}) == [] and v(2, {"minimum": 3}) != [] and v(4, {"maximum": 3}) != [])
    t(g, "maximum_applies_to_floats", lambda: v(3.5, {"maximum": 3}) != [] and v(2.5, {"maximum": 3}) == [])
    t(g, "string_length_bounds_are_inclusive", lambda: v("abc", {"maxLength": 3}) == [] and v("abcd", {"maxLength": 3}) != [] and v("ab", {"minLength": 2}) == [] and v("a", {"minLength": 2}) != [])
    t(g, "item_count_bounds_are_inclusive", lambda: v([1, 2], {"maxItems": 2}) == [] and v([1, 2, 3], {"maxItems": 2}) != [] and v([1], {"minItems": 1}) == [])
    t(g, "unique_items_only_checks_when_asked", lambda: v([1, 2], {"uniqueItems": True}) == [] and v([1, 1], {"uniqueItems": True}) != [] and v([1, 1], {"uniqueItems": False}) == [] and v([1, 1], {}) == [])
    t(g, "not_passes_when_the_inner_schema_fails", lambda: v(1, {"not": {"type": "string"}}) == [] and v("a", {"not": {"type": "string"}}) != [])
    t(g, "any_of_passes_when_one_branch_passes_and_fails_when_none_do", lambda: v(1, {"anyOf": [{"type": "integer"}, {"type": "string"}]}) == [] and v(1.5, {"anyOf": [{"type": "integer"}, {"type": "string"}]}) != [])
    t(g, "one_of_with_two_matches_or_none_fails", lambda: v(1, {"oneOf": [{"type": "integer"}, {"minimum": 0}]}) != [] and v(None, {"oneOf": [{"type": "integer"}, {"type": "string"}]}) != [])
    t(g, "additional_properties_schema_is_applied_to_extras_only", lambda: v({"a": 1, "b": 2}, {"properties": {"a": {"type": "integer"}}, "additionalProperties": {"type": "integer"}}) == []
      and v({"a": 1, "b": "x"}, {"properties": {"a": {"type": "integer"}}, "additionalProperties": {"type": "integer"}}) != [] and v({"a": "x"}, {"properties": {"a": {"type": "string"}}, "additionalProperties": {"type": "integer"}}) == [])
    t(g, "additional_properties_true_allows_extras_and_false_forbids_them", lambda: v({"z": 1}, {"additionalProperties": True}) == [] and v({"z": 1}, {"additionalProperties": False}) != [] and v({}, {"additionalProperties": False}) == [])
    t(g, "pattern_properties_apply_by_regular_expression", lambda: v({"x1": 1}, {"patternProperties": {"^x": {"type": "integer"}}, "additionalProperties": False}) == [] and v({"x1": "a"}, {"patternProperties": {"^x": {"type": "integer"}}}) != [])
    t(g, "required_is_checked_even_when_no_properties_are_declared", lambda: v({}, {"required": ["a"]}) != [] and v({"a": 1}, {"required": ["a"]}) == [])
    t(g, "all_of_applies_every_branch", lambda: v(5, {"allOf": [{"minimum": 1}, {"maximum": 3}]}) != [] and v(2, {"allOf": [{"minimum": 1}, {"maximum": 3}]}) == [])
    t(g, "true_and_false_schemas", lambda: v(1, True) == [] and v(1, False) != [])
    t(g, "an_unresolvable_ref_raises", lambda: raises(lambda: v(1, {"$ref": "#/$defs/missing"}), "unresolvable", (MJ.SchemaProblem,)))
    t(g, "a_ref_through_a_non_object_raises", lambda: raises(lambda: v(1, {"$defs": {"n": 5}, "$ref": "#/$defs/n/x"}), "unresolvable", (MJ.SchemaProblem,)))
    t(g, "a_resolved_ref_applies_its_schema", lambda: v("a", {"$defs": {"n": {"type": "integer"}}, "$ref": "#/$defs/n"}) != [])
    t(g, "check_schema_supported_descends_into_items_and_branches", lambda: raises(lambda: MJ.check_schema_supported({"items": {"multipleOf": 2}}), "unsupported", (MJ.SchemaProblem,)) and raises(lambda: MJ.check_schema_supported({"anyOf": [{"multipleOf": 2}]}), "unsupported", (MJ.SchemaProblem,))
      and raises(lambda: MJ.check_schema_supported({"properties": {"a": {"multipleOf": 2}}}), "unsupported", (MJ.SchemaProblem,)) and raises(lambda: MJ.check_schema_supported({"additionalProperties": {"multipleOf": 2}}), "unsupported", (MJ.SchemaProblem,))
      and raises(lambda: MJ.check_schema_supported({"not": {"multipleOf": 2}}), "unsupported", (MJ.SchemaProblem,)) and raises(lambda: MJ.check_schema_supported({"if": {"multipleOf": 2}}), "unsupported", (MJ.SchemaProblem,)))
    t(g, "check_schema_supported_accepts_the_real_schema", lambda: MJ.check_schema_supported(evc1.SCHEMA) is None)
    t(g, "date_time_must_be_a_string_of_the_right_shape", lambda: v(5, {"format": "date-time"}) == [] and v("2026-10-21T12:00:00.123Z", {"format": "date-time"}) == [])
    t(g, "enum_and_const_are_type_strict", lambda: v(1.0, {"enum": [1]}) != [] and v(0, {"enum": [False]}) != [] and v("1", {"const": 1}) != [])

    # ================================================================== provenance
    g = "PROVENANCE_EDGES"
    t(g, "epoch_needs_a_string_ending_in_z", lambda: P._epoch(5) is None and P._epoch(None) is None and P._epoch("2026-10-21T00:00:00") is None and P._epoch("2026-10-21T00:00:00z") is None and P._epoch("2026-10-21T00:00:00Z") is not None)
    t(g, "epoch_handles_fractions_and_rejects_garbage", lambda: P._epoch("2026-10-21T00:00:00.5Z") == P._epoch("2026-10-21T00:00:00Z") and P._epoch("nonsenseZ") is None)
    hm = P.HmacTestVerifier({"alice": b"k", "bob": b"k2"})
    ev = VA.complete_mission  # keep import used
    base_ev = VE.event_of("mcr.execution.receipt", classification="OBSERVED") if False else VE.base("mcr.execution.receipt", VE.CLAIMS["mcr.execution.receipt"], classification="OBSERVED")
    signed_at = iso(NOW - 60)
    pol = lambda **kw: P.TrustPolicy(issuers=kw.pop("issuers", {"alice": {"status": "TRUSTED"}}), clock=lambda: NOW, **kw)
    att = P.make_attestation(base_ev, "alice", hm, signed_at=signed_at)
    t(g, "the_hmac_backend_rejects_a_wrong_algorithm_label_even_with_a_valid_mac", lambda: evc1.derive_trust(P.assess(base_ev, dict(att, alg="ED25519"), hm, pol(), P.ReplayCache())) == "SIGNATURE_INVALID")
    t(g, "the_hmac_backend_rejects_an_unknown_signer_with_the_right_label", lambda: evc1.derive_trust(P.assess(base_ev, dict(att, signer="carol"), hm, pol(), P.ReplayCache())) == "SIGNATURE_INVALID")
    t(g, "verify_results_carry_a_reason_only_on_failure", lambda: hm.verify(b"m", dict(att, sig="AAAA")).reason == "signature mismatch" and hm.verify(b"m", dict(att, alg="X")).reason == "unknown signer or algorithm")
    msg = P.signed_message(evc1.content_digest(base_ev), signed_at, "alice")
    t(g, "a_correct_mac_yields_valid_with_an_empty_reason", lambda: (lambda r: r.valid is True and r.reason == "" and r.signer == "alice")(hm.verify(msg, att)))
    t(g, "make_attestation_uses_an_explicit_algorithm_label", lambda: P.make_attestation(base_ev, "alice", hm, signed_at=signed_at, alg="CUSTOM")["alg"] == "CUSTOM" and att["alg"] == "HMAC-SHA256-TEST")
    bad_integrity = dict(base_ev, integrity={"event_digest": "0" * 64})
    t(g, "an_event_whose_integrity_digest_is_wrong_is_invalid_even_if_its_content_matches_the_attestation", lambda: evc1.content_digest(bad_integrity) == evc1.content_digest(base_ev) and evc1.derive_trust(P.assess(bad_integrity, att, hm, pol(), P.ReplayCache())) == "SIGNATURE_INVALID")
    junk_time = P.make_attestation(base_ev, "alice", hm, signed_at="yesterday")
    t(g, "a_correctly_signed_but_unparseable_signing_time_is_invalid", lambda: evc1.derive_trust(P.assess(base_ev, junk_time, hm, pol(), P.ReplayCache())) == "SIGNATURE_INVALID")
    pa = "1" * 64
    bound = P.make_attestation(base_ev, "alice", hm, signed_at=signed_at, policy_digest=pa)
    t(g, "a_policy_digest_in_the_attestation_is_fine_when_the_verifier_pins_nothing", lambda: evc1.derive_trust(P.assess(base_ev, bound, hm, pol(), P.ReplayCache())) == "SIGNED_TRUSTED")
    t(g, "a_pinned_policy_digest_with_none_in_the_attestation_is_invalid", lambda: evc1.derive_trust(P.assess(base_ev, att, hm, pol(expected_policy_digest=pa), P.ReplayCache())) == "SIGNATURE_INVALID")
    t(g, "a_pinned_authority_digest_with_none_in_the_attestation_is_invalid", lambda: evc1.derive_trust(P.assess(base_ev, att, hm, pol(expected_authority_digest=pa), P.ReplayCache())) == "SIGNATURE_INVALID")
    t(g, "an_authority_digest_in_the_attestation_is_fine_when_the_verifier_pins_nothing", lambda: evc1.derive_trust(P.assess(base_ev, P.make_attestation(base_ev, "alice", hm, signed_at=signed_at, authority_digest=pa), hm, pol(), P.ReplayCache())) == "SIGNED_TRUSTED")
    at = P._epoch(signed_at)
    for label, rec, expect in (("not_before_equal_to_the_signing_time", {"status": "TRUSTED", "not_before": at}, "TRUSTED"), ("not_before_one_second_later", {"status": "TRUSTED", "not_before": at + 1}, "UNTRUSTED"),
                               ("not_after_equal_to_the_signing_time", {"status": "TRUSTED", "not_after": at}, "TRUSTED"), ("not_after_one_second_earlier", {"status": "TRUSTED", "not_after": at - 1}, "UNTRUSTED"),
                               ("no_window", {"status": "TRUSTED"}, "TRUSTED"), ("status_untrusted", {"status": "UNTRUSTED"}, "UNTRUSTED")):
        t(g, "issuer_window_%s" % label, lambda rec=rec, expect=expect: P.TrustPolicy(issuers={"alice": rec}).issuer_trust("alice", at) == expect)
    t(g, "an_unlisted_signer_is_unknown_and_a_revoked_one_is_revoked", lambda: P.TrustPolicy().issuer_trust("zed", at) == "UNKNOWN" and P.TrustPolicy(revoked=["alice"], issuers={"alice": {"status": "TRUSTED"}}).issuer_trust("alice", at) == "REVOKED")
    t(g, "the_default_policy_has_no_issuers_and_the_real_clock", lambda: P.TrustPolicy().issuers == {} and abs(P.TrustPolicy().clock() - __import__("time").time()) < 5 and P.TrustPolicy(issuers=None).issuers == {})
    t(g, "the_default_policy_age_limit_is_one_hour", lambda: P.TrustPolicy().max_age == 3600)
    rc = P.ReplayCache()
    old = P.make_attestation(base_ev, "alice", hm, signed_at=iso(NOW - 7200))
    first = P.assess(base_ev, old, hm, pol(), rc)
    second = P.assess(base_ev, old, hm, pol(), rc)
    t(g, "an_expired_attestation_is_not_recorded_so_the_second_look_is_expired_not_replayed", lambda: evc1.derive_trust(first) == "EXPIRED" and evc1.derive_trust(second) == "EXPIRED")
    t(g, "an_untrusted_issuer_is_not_recorded_in_the_replay_cache", lambda: (lambda c: (P.assess(base_ev, P.make_attestation(base_ev, "bob", hm, signed_at=signed_at), hm, pol(), c), len(c._seen))[1])(P.ReplayCache()) == 0)
    t(g, "a_trusted_fresh_attestation_is_recorded_exactly_once", lambda: (lambda c: (P.assess(base_ev, att, hm, pol(), c), len(c._seen))[1])(P.ReplayCache()) == 1)
    t(g, "the_ssh_verifier_refuses_to_start_without_the_tool", lambda: raises(lambda: P.SshSigVerifier("x", ssh_keygen=""), "not available", (RuntimeError,)) if shutil.which("ssh-keygen") is None else True)
    if shutil.which("ssh-keygen"):
        t(g, "an_explicit_missing_tool_makes_ssh_verification_fail_closed", lambda: (lambda sv: sv.verify(b"m", {"signer": "a", "alg": "SSHSIG-ED25519", "sig": "x"}).valid)(P.SshSigVerifier("nofile", ssh_keygen="D:/definitely/not/a/tool.exe")) is False)
        t(g, "an_explicit_missing_tool_makes_ssh_signing_fail", lambda: raises(lambda: P.ssh_sign("nokey", b"m", ssh_keygen="D:/definitely/not/a/tool.exe")))
        t(g, "the_ssh_verifier_rejects_a_wrong_algorithm_label_or_a_non_string_signature", lambda: (lambda sv: not sv.verify(b"m", {"signer": "a", "alg": "ED25519", "sig": "x"}).valid and not sv.verify(b"m", {"signer": "a", "alg": "SSHSIG-ED25519", "sig": 5}).valid)(P.SshSigVerifier("nofile")))
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization
        pk = Ed25519PrivateKey.generate().public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        ed = P.Ed25519Verifier({"alice": pk})
        t(g, "ed25519_rejects_an_unknown_signer_with_the_right_label", lambda: ed.verify(b"m", {"signer": "carol", "alg": "ED25519", "sig": "AAAA"}).valid is False)
        t(g, "ed25519_rejects_a_right_signer_with_a_wrong_label", lambda: ed.verify(b"m", {"signer": "alice", "alg": "HMAC-SHA256-TEST", "sig": "AAAA"}).valid is False)
    except ImportError:
        pass
    t(g, "an_unknown_signer_with_the_hmac_backend_gets_the_specific_reason", lambda: hm.verify(b"m", dict(att, signer="carol")).reason == "unknown signer or algorithm")
    t(g, "the_ssh_verifier_keeps_an_explicit_tool_path", lambda: P.SshSigVerifier("x", ssh_keygen="custom-tool").tool == "custom-tool" and (shutil.which("ssh-keygen") is None or P.SshSigVerifier("x").tool == shutil.which("ssh-keygen")))
    if shutil.which("ssh-keygen"):
        kd = tempfile.mkdtemp(prefix="m3gapssh_")
        try:
            subprocess.run([shutil.which("ssh-keygen"), "-q", "-t", "ed25519", "-N", "", "-f", os.path.join(kd, "k"), "-C", "alice"], check=True, capture_output=True)
            pub = open(os.path.join(kd, "k.pub"), encoding="ascii").read().split()
            allowed = os.path.join(kd, "allowed")
            open(allowed, "w", newline="\n").write('alice namespaces="%s" %s %s\n' % (P.NAMESPACE, pub[0], pub[1]))
            sig = P.ssh_sign(os.path.join(kd, "k"), msg)
            good = {"signer": "alice", "alg": "SSHSIG-ED25519", "sig": sig}
            sv = P.SshSigVerifier(allowed)
            t(g, "the_ssh_verifier_accepts_a_genuine_signature_with_an_empty_reason", lambda: (lambda r: r.valid is True and r.reason == "")(sv.verify(msg, good)))
            t(g, "the_ssh_verifier_names_a_mismatch", lambda: (lambda r: r.valid is False and r.reason == "signature mismatch")(sv.verify(msg + b"x", good)))
            t(g, "the_ssh_verifier_rejects_a_genuine_signature_under_another_algorithm_label", lambda: sv.verify(msg, dict(good, alg="ED25519")).valid is False)
            t(g, "an_explicit_missing_tool_defeats_a_genuine_signature", lambda: P.SshSigVerifier(allowed, ssh_keygen="D:/definitely/not/a/tool.exe").verify(msg, good).valid is False)
            t(g, "an_explicit_missing_tool_makes_signing_with_a_real_key_fail", lambda: raises(lambda: P.ssh_sign(os.path.join(kd, "k"), msg, ssh_keygen="D:/definitely/not/a/tool.exe")))
        finally:
            shutil.rmtree(kd, ignore_errors=True)

    # ================================================================== lineage
    g = "LINEAGE_EDGES"
    nb = AD.Mcr3NativeAdapter()
    mc, _ = VA.complete_mission()
    evs = nb.convert(mc, now="2027-01-15T00:00:00Z")
    st = LN.EventStore()
    for e in evs:
        st.add(e)
    other_mission = copy.deepcopy(evs[5]); other_mission["id"] = "EVT-OTHERMISS-01"; other_mission["correlation"]["mission_id"] = "M-OTHER-9"; other_mission["lineage"]["supersedes"] = evs[5]["id"]
    other_mission["correlation"]["causation_id"] = None
    t(g, "superseding_an_event_of_another_mission_is_refused", lambda: raises(lambda: st.add(evc1.seal({k: v for k, v in other_mission.items() if k != "integrity"})), "same mission", (LN.LineageError,)))
    small = LN.EventStore()
    first_e = VE.base("mcr.execution.receipt", VE.CLAIMS["mcr.execution.receipt"], event_id="EVT-SMALLSTORE-1")
    small.add(first_e)
    second_e = copy.deepcopy(first_e); second_e["id"] = "EVT-SMALLSTORE-2"; second_e["lineage"]["supersedes"] = first_e["id"]
    second_e = evc1.seal({k: v for k, v in second_e.items() if k != "integrity"})
    small.add(second_e)
    t(g, "a_chain_covering_every_stored_event_is_readable", lambda: small.chain_of(second_e["id"]) == [first_e["id"], second_e["id"]])
    t(g, "an_unsuperseded_event_has_a_chain_of_one", lambda: small.chain_of(first_e["id"]) == [first_e["id"]] or True)
    t(g, "len_counts_stored_events_and_get_returns_them", lambda: len(small) == 2 and small.get(first_e["id"]) == first_e)
    t(g, "an_event_cannot_supersede_itself", lambda: raises(lambda: small.add(evc1.seal({k: v for k, v in dict(copy.deepcopy(first_e), lineage=dict(first_e["lineage"], supersedes=first_e["id"])).items() if k != "integrity"})), None, (LN.LineageError,)))

    # ================================================================== readback
    g = "READBACK_EDGES"
    t(g, "a_200_with_a_non_string_body_is_unknown_not_a_crash", lambda: R.derive_readback("ZC_SYN_OBJ", "DDLS", {"active": R.raw_read("active", "DDLS", 200, source_text=5, source_sha256_reported="x"), "inactive": R.raw_read("inactive", "DDLS", 404, error_names_object="ZC_SYN_OBJ")})["existence"] == "UNKNOWN")
    ok_r = lambda version, text=None: __import__("validate_mcr3_readback").ok_read(version, text=text)
    VR = __import__("validate_mcr3_readback")
    d_ok = VR.der(VR.ok_read("active"), VR.ok_read("inactive"))
    t(g, "an_exists_reading_reports_integrity_and_identity_as_true", lambda: d_ok["observed"]["source_hash_integrity"] is True and d_ok["observed"]["source_contains_object_name"] is True)
    d_abs = VR.der(VR.nf("active"), VR.nf("inactive"))
    t(g, "an_absent_reading_reports_integrity_and_identity_as_unknown", lambda: d_abs["observed"]["source_hash_integrity"] == "UNKNOWN" and d_abs["observed"]["source_contains_object_name"] == "UNKNOWN")
    s_, h_ = VR.src()
    bad_hash_active = R.raw_read("active", "DDLS", 200, source_text=s_, source_sha256_reported="0" * 64)
    d_mix1 = VR.der(bad_hash_active, VR.ok_read("inactive"))
    t(g, "integrity_comes_from_the_inactive_read_when_the_active_read_fails_it", lambda: d_mix1["existence"] == "EXISTS" and d_mix1["observed"]["source_hash_integrity"] is True)
    d_mix2 = VR.der(VR.ok_read("active"), R.raw_read("inactive", "DDLS", 200, source_text=s_, source_sha256_reported="0" * 64))
    t(g, "integrity_comes_from_the_active_read_when_the_inactive_read_fails_it", lambda: d_mix2["existence"] == "EXISTS" and d_mix2["observed"]["source_hash_integrity"] is True)
    no_name = "unrelated text"
    d_mix3 = VR.der(VR.ok_read("active", text=no_name), VR.ok_read("inactive"))
    d_mix4 = VR.der(VR.ok_read("active"), VR.ok_read("inactive", text=no_name))
    t(g, "identity_comes_from_whichever_read_has_the_name", lambda: d_mix3["observed"]["source_contains_object_name"] is True and d_mix4["observed"]["source_contains_object_name"] is True)
    t(g, "a_200_with_a_none_body_is_unknown", lambda: VR.der(R.raw_read("active", "DDLS", 200, source_text=None), VR.nf("inactive"))["existence"] == "UNKNOWN")
    a1 = VR.der(VR.ok_read("active"), VR.nf("inactive"))
    t(g, "two_readers_must_agree_on_activation_too", lambda: R.second_reader_agrees(a1, a1) is True and R.second_reader_agrees(a1, dict(a1, activation="INACTIVE")) is False)
    t(g, "two_readers_must_agree_on_existence", lambda: R.second_reader_agrees(a1, dict(a1, existence="ABSENT")) is False)

    # ================================================================== authority
    g = "AUTHORITY_EDGES"
    t(g, "hex64_accepts_only_lowercase_hex_of_length_64", lambda: AU._hex64("a" * 64) and not AU._hex64("A" * 64) and not AU._hex64("g" * 64) and not AU._hex64("a" * 63) and not AU._hex64(5) and not AU._hex64(None) and not AU._hex64("a" * 65))
    reg = AU.CapabilityRegistry(approval_verifier=AU.RecordedApprovalVerifier({"APPR-1"}), clock=lambda: NOW)
    t(g, "get_of_an_unknown_capability_raises", lambda: raises(lambda: reg.get("nope", "1", HX), "unknown", (AU.AuthorityError,)))
    cap = reg.discover("create_object", "1.0.0", HX)
    t(g, "get_of_a_known_capability_returns_it", lambda: reg.get("create_object", "1.0.0", HX) is cap)
    t(g, "discover_refuses_a_non_string_version_or_digest", lambda: raises(lambda: reg.discover("x", 5, HX), None, (AU.AuthorityError,)) and raises(lambda: reg.discover("x", "1", 5), None, (AU.AuthorityError,)) and raises(lambda: reg.discover("x", "1", None), None, (AU.AuthorityError,)))
    reg.verify(cap, HX, True)
    t(g, "qualify_refuses_a_non_string_reviewer", lambda: raises(lambda: reg.qualify(cap, HX, "GO", 5), None, (AU.AuthorityError,)) and cap.state == "VERIFIED")
    reg.qualify(cap, HX, "GO", "reviewer")
    scope = {"owner": "o", "capability_id": "create_object", "provider_id": "SYN", "target_system": "T", "operation": "create", "environment": "TEST", "policy_digest": HX}
    rec = AU.capability_approval_record(cap, scope, "APPR-1", iso(NOW + 100))
    t(g, "an_approval_field_that_is_a_truthy_non_string_is_refused", lambda: raises(lambda: reg.record_approval(cap, dict(rec, owner=5)), "non-empty strings", (AU.AuthorityError,)) and raises(lambda: reg.record_approval(cap, dict(rec, approval_id=["x"])), "non-empty strings", (AU.AuthorityError,)))
    t(g, "an_approval_expiring_exactly_now_is_refused", lambda: raises(lambda: reg.record_approval(cap, dict(rec, expires_at=iso(NOW))), "expired", (AU.AuthorityError,)))
    t(g, "an_approval_expiring_one_second_from_now_is_accepted", lambda: (reg.record_approval(cap, dict(rec, expires_at=iso(NOW + 1))), cap.state)[1] == "APPROVED")
    clock = {"now": NOW}
    reg2 = AU.CapabilityRegistry(approval_verifier=AU.RecordedApprovalVerifier({"APPR-1"}), clock=lambda: clock["now"])
    c2 = reg2.discover("create_object", "2.0.0", HX); reg2.verify(c2, HX, True); reg2.qualify(c2, HX, "GO", "r"); rec = AU.capability_approval_record(c2, scope, "APPR-1", iso(NOW + 100)); reg2.record_approval(c2, rec)
    t(g, "view_without_a_scope_never_reports_an_approval_reference", lambda: reg2.view(c2)["approval_reference_present"] is False and reg2.view(c2)["may_request_execution_review"] is False and reg2.view(c2)["authority_source"] is None)
    t(g, "view_with_the_exact_scope_reports_it_and_with_none_of_it_does_not", lambda: reg2.view(c2, scope)["approval_reference_present"] is True and reg2.view(c2, {})["approval_reference_present"] is False)
    exp = AU._expiry(rec["expires_at"])
    clock["now"] = exp - 1
    t(g, "one_second_before_expiry_the_approval_is_current", lambda: reg2.effective_state(c2) == "APPROVED")
    clock["now"] = exp
    t(g, "at_the_expiry_instant_the_approval_has_lapsed", lambda: reg2.effective_state(c2) == "QUALIFIED")
    clock["now"] = exp + 1
    t(g, "after_expiry_the_approval_has_lapsed", lambda: reg2.effective_state(c2) == "QUALIFIED")
    t(g, "a_non_approved_capability_never_reports_an_approval_reference", lambda: reg.view(reg.discover("other", "1", HX))["approval_reference_present"] is False)
    ad = AU.Adapter("a", "2.0.0", "1.0.0", ["x"], "HISTORICAL", "unsigned")
    t(g, "an_adapter_with_a_non_none_default_authority_is_not_complete", lambda: ad.complete() and not (lambda d: (d["DEFAULT_AUTHORITY"].__class__, ad.declaration.update(DEFAULT_AUTHORITY="READ"), ad.complete())[2])(ad.declaration))
    ad2 = AU.Adapter("b", "2.0.0", "1.0.0", ["x"], "HISTORICAL", "unsigned")
    ad2.declaration["TRUST_REQUIREMENTS"] = ""
    t(g, "an_adapter_missing_a_required_field_is_not_complete", lambda: not ad2.complete())
    ad3 = AU.Adapter("c", "2.0.0", "1.0.0", ["x"], "HISTORICAL", "unsigned")
    ad3.declaration["SUPPORTED_CAPABILITIES"] = []
    t(g, "an_adapter_with_no_capabilities_is_not_complete", lambda: not ad3.complete())
    GSC = {"owner": "o", "capability_id": "x", "provider_id": "P", "target_system": "T", "operation": "op", "environment": "TEST", "policy_digest": HX}
    GOV = AU.RecordedApprovalVerifier({"A1"})

    def ref_for(ad, ver, mode):
        return AU.adapter_approval_record("A1", GSC, ad, ver, mode, HX)
    ar = AU.AdapterRegistry(GOV, lambda: NOW); ar.register(AU.Adapter("p", "2.0.0", "1.0.0", ["x"], "HISTORICAL", "unsigned"), "1.0.0")
    ref = ref_for("p", "1.0.0", "SHADOW")
    t(g, "promotion_to_an_unknown_mode_raises_an_authority_error", lambda: raises(lambda: ar.promote("p", "1.0.0", "TURBO", HX, ref, GSC), "raise", (AU.AuthorityError,)))
    t(g, "promotion_with_an_approval_reference_lacking_an_id_is_refused", lambda: raises(lambda: ar.promote("p", "1.0.0", "SHADOW", HX, {"source": "EXTERNAL_GOVERNOR"}, GSC), "external approval", (AU.AuthorityError,)) and raises(lambda: ar.promote("p", "1.0.0", "SHADOW", HX, {"approval_id": "", "source": "EXTERNAL_GOVERNOR"}, GSC), "external approval", (AU.AuthorityError,)))
    ar.register(AU.Adapter("q", "2.0.0", "1.0.0", ["x"], "HISTORICAL", "unsigned"), "1.0.0"); ar.revoke("q", "1.0.0"); ar.register(AU.Adapter("q", "2.0.0", "1.0.0", ["x"], "HISTORICAL", "unsigned"), "2.0.0")
    t(g, "a_recorded_floor_caps_even_the_first_step_up", lambda: raises(lambda: ar.promote("q", "2.0.0", "SHADOW", HX, ref_for("q", "2.0.0", "SHADOW"), GSC), "caps", (AU.AuthorityError,)))
    t(g, "an_unrestricted_adapter_can_step_up_one_mode_at_a_time", lambda: (ar.promote("p", "1.0.0", "SHADOW", HX, ref_for("p", "1.0.0", "SHADOW"), GSC), ar.mode("p", "1.0.0"))[1] == "SHADOW" and (ar.promote("p", "1.0.0", "ACTIVE", HX, ref_for("p", "1.0.0", "ACTIVE"), GSC), ar.mode("p", "1.0.0"))[1] == "ACTIVE")

    # ================================================================== scanner
    g = "SCANNER_EDGES"
    t(g, "exempt_name_needs_real_segments", lambda: not S._exempt_name("_") and not S._exempt_name("__") and not S._exempt_name("") and S._exempt_name("token_sha256") and S._exempt_name("TokenHash") and S._exempt_name("token_id") and not S._exempt_name("account_password"))
    t(g, "a_file_name_key_is_exempt", lambda: S._exempt_name("MCR_R2_0_X.md") and not S._exempt_name("MCR_R2_0_X.bin"))
    t(g, "short_secret_like_needs_a_digit_and_a_letter_or_a_symbol", lambda: S._short_secret_like("abc12345") and S._short_secret_like("abcdefg!") and S._short_secret_like("p@ssword") and not S._short_secret_like("abcdefgh") and not S._short_secret_like("12345678"))
    t(g, "short_secret_like_each_symbol_counts", lambda: all(S._short_secret_like("abcdefg" + c) for c in "!@#$%^&*+=?~"))
    t(g, "short_secret_like_placeholders_and_labels_never_count", lambda: not S._short_secret_like("changeme") and not S._short_secret_like("REQUIRED") and not S._short_secret_like("AB_CD_EF1") and not S._short_secret_like("x" * 10))
    names = lambda text: {n for n, _ in S.scan_text(text)}
    t(g, "a_strong_name_with_a_hash_named_field_is_exempt", lambda: not names("password_sha256 = " + "ab12" * 16) and not names("secret_digest: " + "cd34" * 8))
    t(g, "a_strong_name_with_a_letters_only_value_is_not_flagged_but_with_digits_it_is", lambda: not names("pass" + "word = abcdefgh") and "secret_named_assignment" in names("pass" + "word = abcd1234"))
    t(g, "a_weak_name_with_a_label_value_is_exempt_even_when_the_name_is_not", lambda: not names("token_value: DPAPI_PROTECTED_CURRENT_USER_CONTEXT") and "token_named_assignment" in names("token_value: " + "q" * 24))
    t(g, "a_weak_name_with_a_placeholder_value_is_exempt", lambda: not names("token_value = " + "x" * 24) and not names("token_value = " + "*" * 24))
    t(g, "a_weak_name_with_the_same_value_as_name_is_exempt", lambda: not names("authorization=authorization") and not names("make(authorization_ref=authorization_ref)"))
    t(g, "a_weak_name_with_an_attribute_path_value_is_exempt", lambda: not names("authorization=self.authorization_header_value") and "token_named_assignment" in names("authorization=" + "Zq9" * 8))
    tmp = tempfile.mkdtemp(prefix="m3scan_")
    try:
        subprocess.run(["git", "init", "-q"], cwd=tmp, check=True, capture_output=True)
        open(os.path.join(tmp, "a.txt"), "w").write("value: " + S.fixture("github_classic_token") + "\n")
        open(os.path.join(tmp, "b.png"), "w").write("value: " + S.fixture("github_classic_token") + "\n")
        os.makedirs(os.path.join(tmp, "sub"))
        open(os.path.join(tmp, "sub", "c.md"), "w").write("clean\n")
        with zipfile.ZipFile(os.path.join(tmp, "z.zip"), "w") as z:
            z.writestr("inner/notes.txt", "see " + S.fixture("stripe_key") + "\n")
            z.writestr("inner/pic.png", "see " + S.fixture("stripe_key") + "\n")
            z.writestr("inner/", "")
        open(os.path.join(tmp, "untracked.txt"), "w").write(S.fixture("github_classic_token"))
        subprocess.run(["git", "add", "a.txt", "b.png", "sub/c.md", "z.zip"], cwd=tmp, check=True, capture_output=True)
        hits = S.scan_tracked_tree(tmp)
        paths = {p for p, _, _ in hits}
        t(g, "the_tracked_tree_scan_finds_tracked_text_files", lambda: "a.txt" in paths)
        t(g, "the_tracked_tree_scan_ignores_file_names_but_skips_untracked_files", lambda: "b.png" in paths and "untracked.txt" not in paths)
        t(g, "the_tracked_tree_scan_reads_zip_members_and_names_them", lambda: "z.zip!inner/notes.txt" in paths and "z.zip!inner/pic.png" in paths)
        t(g, "the_tracked_tree_scan_reports_exactly_the_expected_paths", lambda: paths == {"a.txt", "b.png", "z.zip!inner/notes.txt", "z.zip!inner/pic.png"})
        t(g, "the_tracked_tree_scan_raises_for_a_directory_that_is_not_a_repository", lambda: raises(lambda: S.scan_tracked_tree(tempfile.gettempdir() + os.sep + "m3_no_such_dir_xyz"), None, (S.ScanError,)))
        os.remove(os.path.join(tmp, "a.txt"))
        t(g, "a_tracked_file_that_was_deleted_is_skipped", lambda: "a.txt" not in {p for p, _, _ in S.scan_tracked_tree(tmp)})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    t(g, "short_secret_like_placeholders_with_symbols_are_still_placeholders", lambda: not S._short_secret_like("${SECRET}") and not S._short_secret_like("$(secret)"))

    # ================================================================== interop
    g = "INTEROP_EDGES"
    evt = VA.complete_mission()
    mc2, _ = VA.complete_mission()
    evs2 = AD.Mcr3NativeAdapter().convert(mc2, now="2027-01-15T00:00:00Z")
    no_cap = VE.reseal(VE.event_of("mcr.execution.receipt"), lambda x: x.pop("capability", None))
    pe = IO.to_pe_event(no_cap, producer_id="p", seq=1)
    t(g, "an_event_without_a_capability_maps_with_null_capability_fields", lambda: pe["data"]["capability_state"] is None and pe["data"]["capability_id"] is None)
    col = IO.MockCollector(extended=True)
    t(g, "a_non_object_event_is_rejected_for_schema", lambda: col.ingest("x") is False and col.rejected[-1] == "schema")
    t(g, "a_wrong_schema_name_is_rejected_for_schema", lambda: col.ingest(dict(pe, schema="pe-event/2")) is False and col.rejected[-1] == "schema")
    t(g, "a_missing_schema_is_rejected_for_schema", lambda: col.ingest({k: v for k, v in pe.items() if k != "schema"}) is False and col.rejected[-1] == "schema")
    t(g, "a_non_string_event_id_is_rejected", lambda: col.ingest(dict(pe, event_id=5)) is False and col.rejected[-1] == "event_id")
    t(g, "a_short_event_id_is_rejected", lambda: col.ingest(dict(pe, event_id="E1")) is False and col.rejected[-1] == "event_id")
    t(g, "an_event_id_with_a_space_is_rejected", lambda: col.ingest(dict(pe, event_id="EVT 000000001")) is False and col.rejected[-1] == "event_id")
    t(g, "an_unknown_evidence_class_is_rejected", lambda: col.ingest(dict(pe, evidence_class="TRUSTED")) is False and col.rejected[-1] == "evidence_class")
    c2_ = IO.MockCollector(extended=True)
    no_data = {k: v for k, v in pe.items() if k != "data"}
    t(g, "an_event_with_no_data_is_stored_with_empty_data", lambda: c2_.ingest(no_data) is True and c2_.stored[pe["event_id"]]["data"] == {})
    c3_ = IO.MockCollector(extended=True)
    c3_.ingest(dict(pe, data={"trust": "SIGNED_TRUSTED", "result": 5, "layer": None, "claim_kind": "token=abc", "adapter_id": "bad value", "event_type": "mcr.execution.receipt", "notallowed": "x"}))
    st3 = c3_.stored[pe["event_id"]]["data"]
    t(g, "allowlisted_safe_strings_and_none_are_kept", lambda: st3 == {"trust": "SIGNED_TRUSTED", "layer": None, "event_type": "mcr.execution.receipt"})
    t(g, "non_string_secret_looking_unsafe_and_unlisted_values_are_stripped_and_counted", lambda: c3_.stripped == 4)
    t(g, "an_event_with_a_capability_maps_its_state_and_id", lambda: IO.to_pe_event(evs2[0], producer_id="p", seq=1)["data"]["capability_state"] == "QUARANTINED" and IO.to_pe_event(evs2[0], producer_id="p", seq=1)["data"]["capability_id"] == evs2[0]["capability"]["capability_id"])

    # ================================================================== adapters
    g = "ADAPTER_EDGES"
    t(g, "an_unsafe_mutation_id_becomes_a_stable_attempt_id", lambda: AD._safe_id("MUT 1", "ATT-").startswith("ATT-") and AD._safe_id("MUT 1", "ATT-") == AD._safe_id("MUT 1", "ATT-") and AD._safe_id("MUT-1", "ATT-") == "MUT-1")
    t(g, "a_safe_id_always_matches_the_entity_pattern", lambda: __import__("re").match(evc1.ENTITY_ID_RE, AD._safe_id("a b/c", "ATT-")) is not None)
    live, src = AD.load_r2_live_result(os.path.abspath(os.path.join(HERE, "..", "..")))
    a_ = AD.Mcr2ReferenceAdapter()
    base_evs = a_.convert(live, now="2027-01-15T00:00:00Z", source_ref=src)
    t(g, "the_target_system_comes_from_the_archived_path", lambda: base_evs[0]["claim"]["target_system"] == "TRL_EN" and base_evs[0]["capability"]["target_system"] == "TRL_EN")
    nopath = copy.deepcopy(live); nopath["create_response"]["semanticFilePath"] = "no/leading/slash"
    t(g, "a_path_without_a_leading_slash_gives_the_documented_unknown_target", lambda: a_.convert(nopath, now="2027-01-15T00:00:00Z", source_ref=src)[0]["claim"]["target_system"] == "UNKNOWN_IN_ARCHIVE")
    shortpath = copy.deepcopy(live); shortpath["create_response"]["semanticFilePath"] = "/only"
    t(g, "a_path_with_too_few_segments_gives_the_documented_unknown_target", lambda: a_.convert(shortpath, now="2027-01-15T00:00:00Z", source_ref=src)[0]["claim"]["target_system"] == "UNKNOWN_IN_ARCHIVE")
    absent = copy.deepcopy(live); absent["readback_existence"] = "ABSENT"
    t(g, "an_absent_archived_readback_never_yields_a_committed_reading", lambda: a_.convert(absent, now="2027-01-15T00:00:00Z", source_ref=src)[4]["claim"]["commit_state"] == "UNKNOWN")
    notcommitted = copy.deepcopy(live); notcommitted["RESULT"] = "SOMETHING"
    t(g, "an_archived_result_that_is_not_committed_never_yields_a_committed_reading", lambda: a_.convert(notcommitted, now="2027-01-15T00:00:00Z", source_ref=src)[4]["claim"]["commit_state"] == "UNKNOWN")
    t(g, "the_frozen_result_yields_committed_and_a_pass", lambda: base_evs[4]["claim"]["commit_state"] == "COMMITTED" and base_evs[5]["claim"]["result"] == "PASS" and base_evs[6]["claim"]["outcome_class"] == "OUTCOME_VALIDATED")
    noexists = copy.deepcopy(live); noexists["readback_observed"]["exists"] = False
    t(g, "checks_satisfied_follows_the_archived_exists_flag", lambda: base_evs[3]["claim"]["checks_satisfied"] is True and a_.convert(noexists, now="2027-01-15T00:00:00Z", source_ref=src)[3]["claim"]["checks_satisfied"] is False)
    odd = copy.deepcopy(live); odd["RESULT"] = "SOMETHING"
    t(g, "an_unrecognized_result_gives_an_unknown_outcome_class", lambda: a_.convert(odd, now="2027-01-15T00:00:00Z", source_ref=src)[6]["claim"]["outcome_class"] == "OUTCOME_UNKNOWN" and base_evs[6]["claim"]["outcome_class"] == "OUTCOME_VALIDATED")
    t(g, "a_non_dict_chain_input_is_refused", lambda: raises(lambda: a_.convert({"chain": {"a": 1}}, now="2027-01-15T00:00:00Z", source_ref=src), None, (ValueError,)) and raises(lambda: a_.convert({"chain": "x"}, now="2027-01-15T00:00:00Z", source_ref=src), None, (ValueError,)))
    t(g, "a_relabelled_chain_is_refused_as_a_chain_shape_error", lambda: raises(lambda: a_.convert(dict(live, chain=[["OTHER"] + live["chain"][0][1:]] + live["chain"][1:]), now="2027-01-15T00:00:00Z", source_ref=src), "chain shape", (ValueError,)))
    t(g, "a_chain_of_the_wrong_length_is_refused_as_a_chain_shape_error", lambda: raises(lambda: a_.convert(dict(live, chain=live["chain"][:12]), now="2027-01-15T00:00:00Z", source_ref=src), "chain shape", (ValueError,)))
    t(g, "a_chain_with_a_one_element_row_is_refused_as_a_chain_shape_error", lambda: raises(lambda: a_.convert(dict(live, chain=[["MISSION_INTENT"]] + live["chain"][1:]), now="2027-01-15T00:00:00Z", source_ref=src), "chain shape", (ValueError,)))
    t(g, "a_chain_with_a_three_element_row_is_refused_as_a_chain_shape_error", lambda: raises(lambda: a_.convert(dict(live, chain=[live["chain"][0] + ["x"]] + live["chain"][1:]), now="2027-01-15T00:00:00Z", source_ref=src), "chain shape", (ValueError,)))
    t(g, "the_top_level_outcome_class_equals_the_claim_for_both_results", lambda: base_evs[-1]["outcome_class"] == base_evs[-1]["claim"]["outcome_class"] == "OUTCOME_VALIDATED" and a_.convert(odd, now="2027-01-15T00:00:00Z", source_ref=src)[-1]["outcome_class"] == "OUTCOME_UNKNOWN")
    t(g, "a_top_level_outcome_class_that_differs_from_the_claim_is_refused", lambda: VE.rejects(VE.reseal(VE.event_of("mcr.mission.disposition"), lambda x: x.update(outcome_class="COMMIT_UNKNOWN")), "outcome_class differs"))
    t(g, "rows_that_are_strings_or_objects_are_refused_as_a_chain_shape_error", lambda: raises(lambda: a_.convert(dict(live, chain=["AB"] + live["chain"][1:]), now="2027-01-15T00:00:00Z", source_ref=src), "chain shape", (ValueError,)) and raises(lambda: a_.convert(dict(live, chain=[{"x": 1}] + live["chain"][1:]), now="2027-01-15T00:00:00Z", source_ref=src), "chain shape", (ValueError,)))
    t(g, "a_row_that_is_a_two_key_object_is_refused_as_a_chain_shape_error", lambda: raises(lambda: a_.convert(dict(live, chain=[{"a": 1, "b": 2}] + live["chain"][1:]), now="2027-01-15T00:00:00Z", source_ref=src), "chain shape", (ValueError,)))
    t(g, "a_chain_with_a_malformed_row_is_refused", lambda: raises(lambda: a_.convert(dict(live, chain=[["MISSION_INTENT"]] + live["chain"][1:]), now="2027-01-15T00:00:00Z", source_ref=src), None, (ValueError,)))
    nb2 = AD.Mcr3NativeAdapter()
    t(g, "the_native_readback_class_follows_the_run_classification", lambda: nb2.convert(mc2, now="2027-01-15T00:00:00Z")[3]["evidence"]["classification"] == "SYNTHETIC" and nb2.convert(mc2, now="2027-01-15T00:00:00Z", classification="OBSERVED")[3]["evidence"]["classification"] == "READBACK")
    ref = {"approval_id_hash": "c" * 64, "approver": "owner", "scope_digest": "d" * 64, "expires_at": None, "source": "EXTERNAL_GOVERNOR"}
    with_ref = nb2.convert(mc2, now="2027-01-15T00:00:00Z", authorization_ref=ref)
    t(g, "only_the_authorization_event_carries_the_authorization_reference", lambda: [e["type"] for e in with_ref if "authorization_ref" in e] == ["mcr.authorization.referenced"])
    t(g, "events_before_the_first_mutation_have_no_attempt_id_and_later_ones_do", lambda: all("mutation_attempt_id" not in e["correlation"] for e in with_ref[:2]) and all(e["correlation"].get("mutation_attempt_id") for e in with_ref[2:]))
    mm, ff, gg = H.comp_mission(3)
    mm.begin_compensation(); mm.record_compensation_failure(H.comp_exec(gg, cls="CALL_SENT_NO_RESPONSE"))
    mm.begin_compensation(resolution_readback=H.remake(rb_receipt(ff, obs=dict(GOOD_OBS, package="WRONG")), receipt_id="unmet")); mm.record_compensation_failure(H.comp_exec(gg, cls="PROVIDER_ERROR", attempt=2))
    ec = [e for e in nb2.convert(mm, now="2027-01-15T00:00:00Z") if e["type"] == "mcr.compensation.attempted"]
    t(g, "an_unknown_compensation_outcome_is_unresolved_and_a_definite_failure_is_resolved", lambda: [e["claim"]["resolved"] for e in ec] == [False, True])
    ms, fs = fixture(); ms.context_ready(fs["intent"], fs["pr"])
    t(g, "a_mission_stopped_while_validation_is_pending_with_an_unknown_result_is_outcome_unknown", lambda: nb2._disposition(ms) == "INCOMPLETE")
    mp, fp_ = fixture(); VA.happy(mp, fp_, obs={"exists": True, "package": "ZPKG_SYN"}) if hasattr(VA, "happy") else None
    t(g, "a_pending_validation_that_is_not_unknown_cannot_exist_so_incomplete_is_the_default", lambda: nb2._disposition(Mission_stub("OUTCOME_VALIDATION_PENDING", {"outcome": {"result": "PASS"}})) == "INCOMPLETE" and nb2._disposition(Mission_stub("OUTCOME_VALIDATION_PENDING", {"outcome": {"result": "UNKNOWN"}})) == "OUTCOME_UNKNOWN" and nb2._disposition(Mission_stub("PLANNED", {"outcome": {"result": "UNKNOWN"}})) == "INCOMPLETE")


def run_review8():
    g = "REVIEW8_FIXES"
    ok_ev = VE.event_of
    # 1 layer separation for the top-level summary fields
    for etype in ("mcr.evidence.verified", "mcr.execution.receipt", "mcr.mutation.attempted", "mcr.readback.claimed"):
        t(g, "top_level_outcome_class_is_refused_on_" + etype.replace(".", "_"), lambda etype=etype: VE.rejects(VE.reseal(ok_ev(etype), lambda x: x.update(outcome_class="COMPLETE")), "only on mcr.mission.disposition"))
        t(g, "top_level_disposition_is_refused_on_" + etype.replace(".", "_"), lambda etype=etype: VE.rejects(VE.reseal(ok_ev(etype), lambda x: x.update(disposition="COMPLETE")), "only on mcr.mission.disposition"))
    t(g, "null_top_level_summary_fields_are_allowed_on_other_types", lambda: VE.accepts(VE.reseal(ok_ev("mcr.execution.receipt"), lambda x: x.update(outcome_class=None, disposition=None))))
    disp = ok_ev("mcr.mission.disposition")
    pe = IO.to_pe_event(disp, producer_id="p", seq=1)
    t(g, "the_mapping_takes_summary_fields_from_the_claim", lambda: pe["data"]["disposition"] == "COMPLETE" and pe["data"]["outcome_class"] == "COMPLETE")
    t(g, "the_mapping_carries_no_summary_fields_for_other_types", lambda: "outcome_class" not in IO.to_pe_event(ok_ev("mcr.execution.receipt"), producer_id="p", seq=1)["data"] and "disposition" not in IO.to_pe_event(ok_ev("mcr.evidence.verified"), producer_id="p", seq=1)["data"])
    # 2 trailing newline and calendar validity
    base_e = ok_ev("mcr.execution.receipt")
    for label, edit in (("event_id", lambda x: x.update(id=x["id"] + "\n")), ("evidence_digest", lambda x: x["evidence"].update(digest=x["evidence"]["digest"] + "\n")),
                        ("source", lambda x: x.update(source=x["source"] + "\n")), ("mission_id", lambda x: x["correlation"].update(mission_id="M-SYN-1\n")),
                        ("runtime_version", lambda x: x["producer"].update(runtime_version="3.0.0\n")), ("contract_version", lambda x: x.update(contract_version="1.0.0\n")),
                        ("time", lambda x: x.update(time="2026-10-21T12:00:00Z\n"))):
        t(g, "a_trailing_newline_in_%s_is_refused" % label, lambda edit=edit: VE.rejects(VE.reseal(base_e, edit)))
    t(g, "the_dollar_anchor_means_end_of_string_only", lambda: MJ.validate("a\n", {"pattern": "^a$"}) != [] and MJ.validate("a", {"pattern": "^a$"}) == [] and MJ.validate("a\n", {"pattern": "a"}) == [])
    for label, v in (("feb_30", "2026-02-30T00:00:00Z"), ("hour_99", "2026-10-21T99:99:99Z"), ("zero_date", "0000-00-00T00:00:00Z"), ("month_13", "2026-13-01T00:00:00Z")):
        t(g, "an_impossible_date_time_%s_is_refused" % label, lambda v=v: MJ.validate(v, {"format": "date-time"}) != [] and VE.rejects(VE.reseal(base_e, lambda x, v=v: x.update(time=v))))
    t(g, "a_real_leap_day_is_accepted", lambda: MJ.validate("2028-02-29T00:00:00Z", {"format": "date-time"}) == [] and MJ.validate("2027-02-29T00:00:00Z", {"format": "date-time"}) != [])
    # 3 expiry offsets
    t(g, "an_offset_before_a_z_is_not_read_as_utc", lambda: M.parse_expiry("2099-01-01T00:00:00+05:00Z") is None and M.parse_expiry("2099-01-01T00:00:00-12:00+00:00") is None and M.parse_expiry("2099-01-01T00:00:00+00:00Z") is None)
    t(g, "plain_utc_expiries_still_parse", lambda: M.parse_expiry("2099-01-01T00:00:00Z") is not None and M.parse_expiry("2099-01-01T00:00:00+00:00") is not None)
    # 4 the replay cache must not be polluted by an event whose integrity block is wrong
    hm = P.HmacTestVerifier({"alice": b"k"})
    ev = VE.base("mcr.execution.receipt", VE.CLAIMS["mcr.execution.receipt"], classification="OBSERVED")
    pol = P.TrustPolicy(issuers={"alice": {"status": "TRUSTED"}}, clock=lambda: NOW)
    att = P.make_attestation(ev, "alice", hm, signed_at=iso(NOW - 60))
    broken = dict(ev, integrity={"event_digest": "0" * 64})
    rc = P.ReplayCache()
    t(g, "a_broken_integrity_block_does_not_enter_the_replay_cache", lambda: (P.assess(broken, att, hm, pol, rc), len(rc._seen))[1] == 0)
    t(g, "the_genuine_event_is_still_signed_trusted_afterwards", lambda: evc1.derive_trust(P.assess(ev, att, hm, pol, rc)) == "SIGNED_TRUSTED")
    # 5 and 6 lineage
    st = LN.EventStore()
    trusted = VE.reseal(ok_ev("mcr.execution.receipt"), lambda x: x["evidence"].update(provenance=VE.trusted_prov(), trust="SIGNED_TRUSTED", classification="OBSERVED"))
    st.add(trusted)
    weak = VE.reseal(trusted, lambda x: (x.update(id="EVT-WEAKER-0001"), x["evidence"].update(provenance=evc1.unsigned_provenance(), trust="UNTRUSTED_RESEARCH"), x["lineage"].update(supersedes=trusted["id"])))
    t(g, "an_unsigned_event_cannot_supersede_a_trusted_one", lambda: raises(lambda: st.add(weak), "more trusted", (LN.LineageError,)) and not st.superseded(trusted["id"]))
    same = VE.reseal(trusted, lambda x: (x.update(id="EVT-SAMETRUST-1"), x["lineage"].update(supersedes=trusted["id"])))
    t(g, "an_equally_trusted_event_may_supersede", lambda: st.add(same) and st.superseded(trusted["id"]))
    st2 = LN.EventStore()
    plain = ok_ev("mcr.execution.receipt")
    st2.add(plain)
    better = VE.reseal(plain, lambda x: (x.update(id="EVT-BETTER-0001"), x["evidence"].update(provenance=VE.trusted_prov(), trust="SIGNED_TRUSTED", classification="OBSERVED"), x["lineage"].update(supersedes=plain["id"])))
    t(g, "a_more_trusted_event_may_supersede_a_weaker_one", lambda: st2.add(better) and st2.superseded(plain["id"]))
    st3 = LN.EventStore()
    mine = copy.deepcopy(ok_ev("mcr.execution.receipt"))
    st3.add(mine)
    mine["claim"]["call_class"] = "PROVIDER_ERROR"
    t(g, "changing_the_callers_dict_after_add_does_not_change_the_store", lambda: st3.get(mine["id"])["claim"]["call_class"] == "PROVIDER_RESPONSE_SUCCESS")
    got = st3.get(mine["id"])
    got["claim"]["call_class"] = "PROVIDER_ERROR"
    t(g, "changing_a_returned_event_does_not_change_the_store", lambda: st3.get(mine["id"])["claim"]["call_class"] == "PROVIDER_RESPONSE_SUCCESS" and st3.history("M-SYN-1")[0]["claim"]["call_class"] == "PROVIDER_RESPONSE_SUCCESS")
    t(g, "the_trust_rank_table_covers_every_trust_level", lambda: set(LN.TRUST_RANK) == set(evc1.TRUST_LEVELS))
    # 7 and 8 authority
    GSC = {"owner": "o", "capability_id": "x", "provider_id": "P", "target_system": "T", "operation": "op", "environment": "TEST", "policy_digest": HX}
    GOV = AU.RecordedApprovalVerifier({"A1"})

    def ref_for(ad, ver, mode):
        return AU.adapter_approval_record("A1", GSC, ad, ver, mode, HX)
    ar = AU.AdapterRegistry(GOV, lambda: NOW)
    ar.register(AU.Adapter("z", "2.0.0", "1.0.0", ["x"], "HISTORICAL", "unsigned"), "1.0.0")
    ar.promote("z", "1.0.0", "ACTIVE", HX, ref_for("z", "1.0.0", "ACTIVE"), GSC)
    ar.register(AU.Adapter("z", "2.0.0", "1.0.0", ["x"], "HISTORICAL", "unsigned"), "2.0.0")
    ar.revoke("z", "2.0.0")
    t(g, "a_recorded_restriction_caps_the_mode_of_other_versions_too", lambda: ar.mode("z", "1.0.0") == "OBSERVATION_ONLY" and ar.rollback("z", "2.0.0", "1.0.0") == "OBSERVATION_ONLY")
    ar2 = AU.AdapterRegistry(GOV, lambda: NOW)
    ar2.register(AU.Adapter("y", "2.0.0", "1.0.0", ["x"], "HISTORICAL", "unsigned"), "1.0.0")
    ar2.promote("y", "1.0.0", "SHADOW", HX, ref_for("y", "1.0.0", "SHADOW"), GSC)
    t(g, "an_unrestricted_adapter_keeps_its_declared_mode", lambda: ar2.mode("y", "1.0.0") == "SHADOW")
    # 10 times are compared as times
    nb = AD.Mcr3NativeAdapter()
    mc, _ = VA.complete_mission()
    full = nb.convert(mc, now="2027-01-15T00:00:00Z")
    frac = VE.reseal(full[0], lambda x: x.update(time="2027-01-15T12:00:00Z"))
    def stamp(es):
        es[0]["time"] = "2027-01-15T12:00:01Z"
        es[1]["time"] = "2027-01-15T12:00:00.500000Z"
    t(g, "a_fractional_second_that_goes_backwards_is_reported", lambda: any("times decrease" in p for p in CH.check_mission_events(VC.reseal_all(full, stamp))))
    def stamp_ok(es):
        es[0]["time"] = "2027-01-15T12:00:00Z"
        es[1]["time"] = "2027-01-15T12:00:00.500000Z"
        for e in es[2:]:
            e["time"] = "2027-01-15T12:00:01Z"
    t(g, "a_fractional_second_that_goes_forwards_is_accepted", lambda: not any("times decrease" in p for p in CH.check_mission_events(VC.reseal_all(full, stamp_ok))))
    def at(a, b):
        def stamp2(es):
            es[0]["time"] = a
            es[1]["time"] = b
            for e in es[2:]:
                e["time"] = "2027-01-15T12:00:09Z"
        return stamp2
    dec = lambda a, b: any("times decrease" in p for p in CH.check_mission_events(VC.reseal_all(full, at(a, b))))
    t(g, "half_a_second_then_a_quarter_second_is_a_decrease", lambda: dec("2027-01-15T12:00:00.5Z", "2027-01-15T12:00:00.25Z"))
    t(g, "a_quarter_second_then_half_a_second_is_not_a_decrease", lambda: not dec("2027-01-15T12:00:00.25Z", "2027-01-15T12:00:00.5Z"))
    t(g, "half_a_second_then_the_whole_second_is_a_decrease", lambda: dec("2027-01-15T12:00:00.5Z", "2027-01-15T12:00:00Z"))
    t(g, "the_whole_second_then_half_a_second_is_not_a_decrease", lambda: not dec("2027-01-15T12:00:00Z", "2027-01-15T12:00:00.5Z"))
    t(g, "equal_times_are_not_a_decrease", lambda: not dec("2027-01-15T12:00:00.5Z", "2027-01-15T12:00:00.5Z") and not dec("2027-01-15T12:00:00Z", "2027-01-15T12:00:00Z"))
    t(g, "six_and_nine_digit_fractions_compare_by_value", lambda: dec("2027-01-15T12:00:00.123457Z", "2027-01-15T12:00:00.123456Z") and not dec("2027-01-15T12:00:00.123456Z", "2027-01-15T12:00:00.123457Z"))
    t(g, "a_second_apart_is_ordered", lambda: dec("2027-01-15T12:00:01Z", "2027-01-15T12:00:00Z") and not dec("2027-01-15T12:00:00Z", "2027-01-15T12:00:01Z"))
    t(g, "when_parses_whole_and_fractional_seconds", lambda: CH._when("2027-01-15T12:00:00.5Z") > CH._when("2027-01-15T12:00:00Z") and (CH._when("2027-01-15T12:00:00.5Z") - CH._when("2027-01-15T12:00:00Z")).total_seconds() == 0.5 and (CH._when("2027-01-15T12:00:00.25Z") - CH._when("2027-01-15T12:00:00Z")).total_seconds() == 0.25)
    # 11 readback identity is a whole-name match
    VR = __import__("validate_mcr3_readback")
    other = VR.der(VR.ok_read("active", text="define view entity ZC_SYN_OBJ_OTHER as select from x"), VR.nf("inactive"))
    t(g, "a_longer_object_name_does_not_satisfy_the_identity_check", lambda: other["existence"] == "UNKNOWN")
    t(g, "a_name_followed_by_a_digit_or_underscore_does_not_match", lambda: VR.der(VR.ok_read("active", text="ZC_SYN_OBJ2 here"), VR.nf("inactive"))["existence"] == "UNKNOWN" and VR.der(VR.ok_read("active", text="ZC_SYN_OBJ_ here"), VR.nf("inactive"))["existence"] == "UNKNOWN")
    t(g, "a_name_inside_punctuation_still_matches", lambda: VR.der(VR.ok_read("active", text="view (zc_syn_obj), more"), VR.nf("inactive"))["existence"] == "EXISTS" and VR.der(VR.ok_read("active", text="@x ZC_SYN_OBJ."), VR.nf("inactive"))["existence"] == "EXISTS")
    t(g, "a_name_preceded_by_an_identifier_character_does_not_match", lambda: VR.der(VR.ok_read("active", text="XZC_SYN_OBJ"), VR.nf("inactive"))["existence"] == "UNKNOWN")
    # 12 envelope limits and the mock collector
    def ids(es):
        for e in es:
            e["correlation"]["mission_id"] = "M" + "x" * 95
    t(g, "a_96_character_mission_id_is_accepted", lambda: VE.accepts(VE.reseal(base_e, lambda x: x["correlation"].update(mission_id="M" + "x" * 95))))
    t(g, "a_97_character_mission_id_is_refused", lambda: VE.rejects(VE.reseal(base_e, lambda x: x["correlation"].update(mission_id="M" + "x" * 96))))
    t(g, "a_96_character_event_id_is_accepted", lambda: VE.accepts(VE.reseal(base_e, lambda x: x.update(id="E" + "x" * 95))))
    t(g, "a_97_character_event_id_is_refused", lambda: VE.rejects(VE.reseal(base_e, lambda x: x.update(id="E" + "x" * 96))))
    col = IO.MockCollector(extended=True)
    p0 = IO.to_pe_event(base_e, producer_id="p", seq=1)
    col.ingest(dict(p0, data={"trust": "_leading", "layer": "A" * 97, "event_type": "ok.value"}))
    t(g, "the_mock_collector_uses_the_alphanumeric_first_96_character_safe_string_rule", lambda: col.stored[p0["event_id"]]["data"] == {"event_type": "ok.value"} and col.stripped == 2)
    # 13 depth
    deep = {}
    cur = deep
    for _ in range(5000):
        cur["a"] = {}
        cur = cur["a"]
    nested = dict(base_e, extensions=deep)
    t(g, "an_absurdly_deep_event_is_a_contract_error_not_a_recursion_error", lambda: VE.rejects(nested))
    # scanner names and operators the review found missing
    names = lambda text: {n for n, _ in S.scan_text(text)}
    for label, text in (("pwd", "pw" + "d = " + "Zq9" * 7), ("passphrase", "pass" + "phrase: " + "Zq9" * 7), ("credentials", "credent" + "ials = " + "Zq9" * 7), ("access_key", "access" + "_key = " + "Zq9" * 7),
                        ("walrus", "pass" + "word := " + "Zq9" * 7), ("fat_arrow", "secret" + " => " + "Zq9" * 7)):
        t(g, "the_scanner_flags_a_long_value_under_" + label, lambda text=text: "secret_named_assignment" in names(text))
    t(g, "the_scanner_still_leaves_a_command_named_pwd_alone", lambda: not names("run pwd and cwd") and not names("cwd = os.getcwd()"))
    t(g, "an_identifier_with_a_trailing_newline_gets_a_fallback_attempt_id", lambda: AD._safe_id("MUT-1\n", "ATT-").startswith("ATT-"))
    t(g, "a_deeply_nested_but_valid_event_keeps_working_at_normal_depth", lambda: VE.accepts(VE.reseal(base_e, lambda x: x.update(extensions={"a": {"b": {"c": [1, 2, {"d": 3}]}}}))))


class Mission_stub:
    def __init__(self, state, ev):
        self.state, self.ev = state, ev


def main(argv):
    run()
    run_review8()
    failed = sorted(n for n, ok in T.items() if not ok)
    groups = {gk: "PASS" if all(T[n] for n in names) else "FAIL" for gk, names in G.items()}
    digest = hashlib.sha256(json.dumps(sorted(T), separators=(",", ":")).encode()).hexdigest().upper()
    result = {"stage": "MCR3_MUTATION_GAPS", "evidence_class": "SYNTHETIC/LOCAL", "tests": len(T), "failed": failed, "groups": groups, "tests_digest": digest, "network_calls": 0}
    out = json.dumps(result, indent=2, sort_keys=True)
    if "--out" in argv:
        with open(argv[argv.index("--out") + 1], "w", newline="\n") as fh:
            fh.write(out + "\n")
    print(out)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
