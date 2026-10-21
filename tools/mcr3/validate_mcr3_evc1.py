"""Conformance, negative-fixture, compatibility and migration tests for the MCR Evidence Contract v1. Offline, stdlib only
(the optional `jsonschema` library is used as a cross-check when importable; otherwise that check is NOT_VERIFIED)."""
import copy
import hashlib
import itertools
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
if os.environ.get("MCR3_OVERRIDE_DIR"):          # mutation harness: a mutated module shadows the real one
    sys.path.insert(0, os.environ["MCR3_OVERRIDE_DIR"])
import evc1  # noqa: E402
import mini_jsonschema as MJ  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SCHEMA_FILE = os.path.join(ROOT, "architecture", "mcr3", "contracts", "evidence-v1", "mcr-evidence-1.schema.json")
EXAMPLES_DIR = os.path.join(ROOT, "architecture", "mcr3", "contracts", "evidence-v1", "examples")
T, G = {}, {}
NOT_VERIFIED = []
H = "a" * 64


def t(group, name, ok):
    try:
        ok = ok() if callable(ok) else ok
    except Exception:
        ok = False
    T[name] = bool(ok)
    G.setdefault(group, []).append(name)


def rejects(e, text=None, **kw):
    try:
        evc1.parse(e, **kw)
    except evc1.ContractError as exc:
        return text is None or text in str(exc)
    except Exception:
        return False
    return False


def accepts(e, **kw):
    try:
        evc1.parse(e, **kw)
        return True
    except Exception:
        return False


def base(etype, claim, **kw):
    args = dict(event_id="EVT-%s" % hashlib.sha1(etype.encode()).hexdigest()[:10], source="mcr://conformance/fixture", time="2026-10-21T12:00:00Z",
                runtime_version="3.0.0", adapter_id="fixture-adapter", adapter_version="1.0.0", source_runtime_version="3.0.0",
                correlation={"mission_id": "M-SYN-1", "transaction_id": "TX-SYN-1", "correlation_id": "CORR-SYN-1", "causation_id": None, "mutation_attempt_id": "ATT-SYN-1"},
                evidence_digest=H, classification="SYNTHETIC")
    args.update(kw)
    return evc1.make_event(etype, claim, **args)


CLAIMS = {
    "mcr.mission.started": {"intent_digest": H, "target_system": "SYN_SYS"},
    "mcr.authorization.referenced": {"referenced": True},
    "mcr.capability.state_changed": {"from_state": "QUALIFIED", "to_state": "APPROVED", "reason": "owner approval referenced", "approval_required": True},
    "mcr.mutation.attempted": {"attempt_id": "ATT-SYN-1", "attempt_number": 1, "budget_remaining_after": 0, "budget_kind": "FORWARD"},
    "mcr.execution.receipt": {"call_class": "PROVIDER_RESPONSE_SUCCESS", "provider_acknowledged": True, "implies_commit": False},
    "mcr.commit.observed": {"commit_state": "COMMITTED", "readback_digest": H, "implies_outcome": False},
    "mcr.readback.claimed": {"source_level": "AUTHORITATIVE_REPOSITORY", "claimed_authoritative": True, "existence": "EXISTS", "activation": "UNKNOWN",
                             "checks_satisfied": True, "provenance_verified": False},
    "mcr.outcome.evaluated": {"expected_digest": H, "observed_digest": H, "readback_digest": H, "predicates_digest": H, "result": "PASS"},
    "mcr.compensation.attempted": {"attempt_number": 1, "call_class": "PROVIDER_ERROR", "resolved": False},
    "mcr.mission.disposition": {"disposition": "COMPLETE", "outcome_class": "COMPLETE", "chain_digests": [H]},
    "mcr.evidence.verified": {"subject_digest": H, "scope": "HASH", "result": "PASS", "verifier": "mcr3-test", "claims_business_outcome": False},
}


def event_of(etype, **kw):
    return base(etype, copy.deepcopy(CLAIMS[etype]), **kw)


def reseal(e, mutate):
    x = copy.deepcopy(e)
    mutate(x)
    x.pop("integrity", None)
    return evc1.seal(x)          # keeps the event internally consistent, so only the intended rule is violated


def trusted_prov():
    return {"hash_consistent": True, "signature": "VALID", "signer": "test-signer", "issuer_trust": "TRUSTED", "freshness": "FRESH", "replay": "NOT_SEEN", "verified_by": "mcr3-test"}


def run():
    # ---------------------------------------------------------------- schema and examples
    g = "SCHEMA"
    gen = json.dumps(evc1.build_schema(), indent=2, sort_keys=True) + "\n"
    t(g, "schema_uses_only_keywords_the_validator_checks", lambda: (safe(lambda: MJ.check_schema_supported(evc1.SCHEMA) is None)))
    t(g, "checked_in_schema_equals_the_generated_schema", lambda: (os.path.exists(SCHEMA_FILE) and open(SCHEMA_FILE, encoding="utf-8", newline="").read().replace("\r\n", "\n") == gen))
    t(g, "schema_digest_is_stable_and_pinned_in_events", lambda: (evc1.SCHEMA_DIGEST == evc1.digest_of(evc1.build_schema())))
    t(g, "type_table_covers_every_claim_kind_once", lambda: (len({k for k, _ in evc1.TYPE_TABLE.values()}) == len(evc1.TYPE_TABLE) == len(evc1.SCHEMA["properties"]["claim"]["oneOf"]) == 11))
    t(g, "every_type_belongs_to_exactly_one_known_layer", lambda: (all(l in evc1.LAYERS for _, l in evc1.TYPE_TABLE.values())))
    t(g, "all_five_layers_are_used", lambda: ({l for _, l in evc1.TYPE_TABLE.values()} == set(evc1.LAYERS)))
    t(g, "authority_effect_is_the_constant_none", lambda: (evc1.SCHEMA["properties"]["authority_effect"] == {"const": "NONE"}))
    t(g, "spec_pins_are_recorded", lambda: ({"cloudevents", "in-toto-attestation", "mcp-authorization", "opentelemetry-semantic-conventions", "owasp"} <= set(evc1.SPEC_PINS)))
    try:
        import jsonschema
        have_js = True
    except Exception:
        have_js = False
        NOT_VERIFIED.append("jsonschema cross-check (library not installed)")

    g = "EXAMPLES"
    for etype in sorted(evc1.TYPE_TABLE):
        e = event_of(etype)
        t(g, "example_%s_is_accepted" % etype, accepts(e))
        t(g, "example_%s_has_authority_effect_none" % etype, e["authority_effect"] == "NONE")
        t(g, "example_%s_digests_are_consistent" % etype, e["digests"]["payload"] == evc1.digest_of(e["claim"]) and e["integrity"]["event_digest"] == evc1.digest_of({k: v for k, v in e.items() if k != "integrity"}))
        if have_js:
            t(g, "example_%s_agrees_with_the_jsonschema_library" % etype, not list(jsonschema.Draft202012Validator(evc1.SCHEMA).iter_errors(e)))
    if os.path.isdir(EXAMPLES_DIR):
        files = sorted(os.listdir(EXAMPLES_DIR))
        t(g, "checked_in_examples_are_all_accepted_and_cover_every_type", lambda: (len(files) == len(evc1.TYPE_TABLE) and all(accepts(json.load(open(os.path.join(EXAMPLES_DIR, f), encoding="utf-8"))) for f in files)))

    # ---------------------------------------------------------------- negative fixtures
    g = "NEGATIVE"
    ok_e = event_of("mcr.execution.receipt")
    for field in evc1.SCHEMA["required"]:
        e = copy.deepcopy(ok_e); e.pop(field)
        t(g, "missing_required_%s_is_rejected" % field, rejects(e))
    t(g, "wrong_contract_name_rejected", lambda: (rejects(dict(ok_e, contract="other/1"), "not an")))
    t(g, "major_two_rejected", lambda: (rejects(dict(ok_e, contract_version="2.0.0"), "major")))
    t(g, "major_zero_rejected", lambda: (rejects(dict(ok_e, contract_version="0.9.0"), "major")))
    t(g, "malformed_version_rejected", lambda: (rejects(dict(ok_e, contract_version="1.0"), "contract_version")))
    t(g, "non_object_rejected", lambda: (rejects([ok_e]) and rejects("x") and rejects(None)))
    t(g, "unknown_type_rejected", lambda: (rejects(dict(ok_e, type="mcr.mission.exploded"))))
    t(g, "claim_kind_that_does_not_match_the_type_rejected", lambda: (rejects(reseal(ok_e, lambda x: x.update(type="mcr.commit.observed")), "kind/layer")))
    t(g, "claim_layer_that_does_not_match_the_type_rejected", lambda: (rejects(reseal(ok_e, lambda x: x["claim"].update(layer="VERIFIED_FACT")))))
    t(g, "payload_tamper_rejected", lambda: (rejects(dict(copy.deepcopy(ok_e), claim=dict(ok_e["claim"], provider_acknowledged=False)), "payload")))
    e = copy.deepcopy(ok_e); e["time"] = "2026-10-21T13:00:00Z"
    t(g, "event_tamper_without_reseal_rejected", lambda: (rejects(e, "integrity")))
    t(g, "wrong_schema_digest_rejected", lambda: (rejects(dict(ok_e, digests=dict(ok_e["digests"], schema="b" * 64)))))
    t(g, "authority_effect_other_than_none_rejected", lambda: (rejects(reseal(ok_e, lambda x: x.update(authority_effect="GRANT")))))
    t(g, "extra_top_level_grant_field_rejected", lambda: (rejects(reseal(ok_e, lambda x: x.update(grants=["delete"])), "unknown top-level")))
    t(g, "extra_nested_field_in_claim_rejected", lambda: (rejects(reseal(ok_e, lambda x: x["claim"].update(extra=1)))))
    t(g, "extra_nested_field_in_evidence_rejected", lambda: (rejects(reseal(ok_e, lambda x: x["evidence"].update(extra=1)))))
    t(g, "implies_commit_true_rejected", lambda: (rejects(reseal(ok_e, lambda x: x["claim"].update(implies_commit=True)))))
    c = event_of("mcr.commit.observed")
    t(g, "implies_outcome_true_rejected", lambda: (rejects(reseal(c, lambda x: x["claim"].update(implies_outcome=True)))))
    v = event_of("mcr.evidence.verified")
    t(g, "a_verification_claiming_a_business_outcome_rejected", lambda: (rejects(reseal(v, lambda x: x["claim"].update(claims_business_outcome=True)))))
    t(g, "a_verification_scope_of_business_outcome_rejected", lambda: (rejects(reseal(v, lambda x: x["claim"].update(scope="BUSINESS_OUTCOME")))))
    t(g, "a_signature_verification_does_not_become_an_outcome", lambda: (accepts(reseal(v, lambda x: x["claim"].update(scope="SIGNATURE"))) and v["claim"]["layer"] == "VERIFIED_FACT"))
    rb = event_of("mcr.readback.claimed")
    t(g, "authoritative_claim_from_provider_log_rejected", lambda: (rejects(reseal(rb, lambda x: x["claim"].update(source_level="PROVIDER_LOG")), "authoritative")))
    t(g, "provenance_verified_without_trust_rejected", lambda: (rejects(reseal(rb, lambda x: x["claim"].update(provenance_verified=True)), "provenance_verified")))
    t(g, "authoritative_claim_is_distinct_from_verified_provenance", lambda: (accepts(rb) and rb["claim"]["claimed_authoritative"] and not rb["claim"]["provenance_verified"]))
    oc = event_of("mcr.outcome.evaluated", classification="CLAIMED")
    t(g, "pass_outcome_on_claimed_evidence_rejected", lambda: (rejects(oc, "PASS outcome needs")))
    t(g, "pass_outcome_on_readback_evidence_accepted", lambda: (accepts(event_of("mcr.outcome.evaluated", classification="READBACK"))))
    t(g, "unknown_outcome_on_claimed_evidence_accepted", lambda: (accepts(base("mcr.outcome.evaluated", dict(CLAIMS["mcr.outcome.evaluated"], result="UNKNOWN"), classification="CLAIMED"))))
    t(g, "commit_observed_on_claimed_evidence_rejected", lambda: (rejects(base("mcr.commit.observed", CLAIMS["mcr.commit.observed"], classification="CLAIMED"), "COMMITTED observation")))
    dp = event_of("mcr.mission.disposition")
    t(g, "complete_disposition_with_another_outcome_class_rejected", lambda: (rejects(reseal(dp, lambda x: x["claim"].update(outcome_class="OUTCOME_VALIDATED")), "needs outcome_class COMPLETE")))
    t(g, "complete_outcome_class_with_another_disposition_rejected", lambda: (rejects(reseal(dp, lambda x: x["claim"].update(disposition="INCOMPLETE")), "needs disposition COMPLETE")))
    t(g, "top_level_disposition_must_match_the_claim", lambda: (rejects(reseal(dp, lambda x: x.update(disposition="FAILED")), "differs from the claim")))
    t(g, "empty_chain_digests_rejected", lambda: (rejects(reseal(dp, lambda x: x["claim"].update(chain_digests=[])))))
    er = event_of("mcr.execution.receipt")
    t(g, "success_response_without_acknowledgement_rejected", lambda: (rejects(reseal(er, lambda x: x["claim"].update(provider_acknowledged=False)), "acknowledgement")))
    t(g, "a_failed_call_that_is_acknowledged_rejected", lambda: (rejects(reseal(er, lambda x: x["claim"].update(call_class="PROVIDER_ERROR")), "cannot be an acknowledgement")))
    ev0 = event_of("mcr.mutation.attempted")
    t(g, "attempt_event_without_attempt_id_rejected", lambda: (rejects(reseal(ev0, lambda x: x["correlation"].update(mutation_attempt_id=None)), "mutation_attempt_id")))
    t(g, "non_start_event_without_mission_id_rejected", lambda: (rejects(reseal(er, lambda x: x["correlation"].update(mission_id=None)), "mission_id")))
    t(g, "mission_start_without_mission_id_is_allowed", lambda: (accepts(base("mcr.mission.started", CLAIMS["mcr.mission.started"], correlation={"mission_id": None, "transaction_id": None, "correlation_id": "CORR-SYN-1", "causation_id": None}))))
    for label, bad in (("date_only", "2026-10-21"), ("offset", "2026-10-21T12:00:00+05:30"), ("lowercase_z", "2026-10-21T12:00:00z"), ("empty", ""), ("not_a_time", "yesterday")):
        t(g, "time_%s_rejected" % label, rejects(reseal(er, lambda x, b=bad: x.update(time=b))))
    t(g, "short_event_id_rejected", lambda: (rejects(reseal(er, lambda x: x.update(id="E1")))))
    t(g, "event_id_with_a_space_rejected", lambda: (rejects(reseal(er, lambda x: x.update(id="EVT 0000001")))))
    t(g, "source_with_whitespace_rejected", lambda: (rejects(reseal(er, lambda x: x.update(source="mcr://a b")))))
    t(g, "uppercase_hash_rejected", lambda: (rejects(reseal(er, lambda x: x["evidence"].update(digest="A" * 64)))))
    t(g, "short_hash_rejected", lambda: (rejects(reseal(er, lambda x: x["evidence"].update(digest="a" * 63)))))
    t(g, "null_where_a_hash_is_required_rejected", lambda: (rejects(reseal(er, lambda x: x["evidence"].update(digest=None)))))
    t(g, "bool_where_an_int_is_required_rejected", lambda: (rejects(reseal(ev0, lambda x: x["claim"].update(attempt_number=True)))))
    t(g, "zero_attempt_number_rejected", lambda: (rejects(reseal(ev0, lambda x: x["claim"].update(attempt_number=0)))))
    t(g, "negative_budget_rejected", lambda: (rejects(reseal(ev0, lambda x: x["claim"].update(budget_remaining_after=-1)))))
    t(g, "runtime_other_than_mcr_rejected", lambda: (rejects(reseal(er, lambda x: x["producer"].update(runtime="other")))))
    t(g, "bad_runtime_version_rejected", lambda: (rejects(reseal(er, lambda x: x["producer"].update(runtime_version="3.0")))))
    t(g, "unknown_call_class_rejected", lambda: (rejects(reseal(er, lambda x: x["claim"].update(call_class="FINE")))))
    t(g, "unknown_evidence_class_rejected", lambda: (rejects(reseal(er, lambda x: x["evidence"].update(classification="TRUSTED_BY_ME")))))
    t(g, "unknown_trust_value_rejected", lambda: (rejects(reseal(er, lambda x: x["evidence"].update(trust="SUPER_TRUSTED")))))
    t(g, "unknown_capability_state_rejected", lambda: (rejects(reseal(event_of("mcr.capability.state_changed"), lambda x: x["claim"].update(to_state="PROMOTED")))))
    t(g, "unknown_disposition_rejected", lambda: (rejects(reseal(dp, lambda x: x["claim"].update(disposition="DONE")))))
    t(g, "unknown_outcome_class_rejected", lambda: (rejects(reseal(dp, lambda x: x["claim"].update(outcome_class="DONE")))))
    t(g, "two_claims_at_once_rejected", lambda: (rejects(reseal(er, lambda x: x["claim"].update(commit_state="COMMITTED")))))
    t(g, "authorization_ref_with_a_foreign_source_rejected", lambda: (rejects(reseal(er, lambda x: x.update(authorization_ref={"approval_id_hash": H, "approver": "me", "scope_digest": H, "expires_at": None, "source": "SELF"})))))
    t(g, "authorization_ref_from_the_external_governor_is_a_reference_only", lambda: (accepts(reseal(er, lambda x: x.update(authorization_ref={"approval_id_hash": H, "approver": "owner", "scope_digest": H, "expires_at": None, "source": "EXTERNAL_GOVERNOR"}))) and er["authority_effect"] == "NONE"))
    t(g, "authorization_ref_without_scope_rejected", lambda: (rejects(reseal(er, lambda x: x.update(authorization_ref={"approval_id_hash": H, "approver": "owner", "expires_at": None, "source": "EXTERNAL_GOVERNOR"})))))
    t(g, "synthetic_evidence_cannot_be_signed_trusted", lambda: (rejects(reseal(er, lambda x: x["evidence"].update(provenance=trusted_prov(), trust="SIGNED_TRUSTED")), "synthetic")))
    good_trusted = reseal(er, lambda x: x["evidence"].update(provenance=trusted_prov(), trust="SIGNED_TRUSTED", classification="OBSERVED"))
    t(g, "observed_evidence_with_complete_trusted_provenance_is_accepted", lambda: (accepts(good_trusted) and good_trusted["evidence"]["trust"] == "SIGNED_TRUSTED"))
    t(g, "signed_trusted_never_changes_authority_effect", lambda: (good_trusted["authority_effect"] == "NONE"))
    t(g, "principal_verified_without_trusted_evidence_rejected", lambda: (rejects(reseal(er, lambda x: x.update(principal={"principal_ref": H, "assurance": "VERIFIED", "delegation_ref": None})), "VERIFIED")))
    t(g, "principal_verified_with_trusted_evidence_accepted", lambda: (accepts(reseal(good_trusted, lambda x: x.update(principal={"principal_ref": H, "assurance": "VERIFIED", "delegation_ref": None})))))
    t(g, "principal_self_reported_is_accepted_and_labelled", lambda: (accepts(reseal(er, lambda x: x.update(principal={"principal_ref": H, "assurance": "SELF_REPORTED", "delegation_ref": None})))))
    t(g, "trust_overclaim_rejected", lambda: (rejects(reseal(er, lambda x: x["evidence"].update(trust="SIGNED_TRUSTED")), "provenance record supports")))

    # ---------------------------------------------------------------- derive_trust exhaustively
    g = "TRUST_DERIVATION"
    combos = list(itertools.product((True, False), evc1.SIGNATURE_STATES, evc1.ISSUER_TRUST, evc1.FRESHNESS, evc1.REPLAY))
    trusted_ok = True
    never_trusted_wrong = True
    revoked_ok = True
    absent_ok = True
    for h_, sig, iss, fr, rp in combos:
        prov = {"hash_consistent": h_, "signature": sig, "signer": None, "issuer_trust": iss, "freshness": fr, "replay": rp, "verified_by": None}
        tr = evc1.derive_trust(prov)
        full = h_ and sig == "VALID" and iss == "TRUSTED" and fr == "FRESH" and rp == "NOT_SEEN"
        trusted_ok &= (tr == "SIGNED_TRUSTED") == full
        if rp == "REPLAYED":
            never_trusted_wrong &= tr == "REPLAYED"
        elif iss == "REVOKED":
            revoked_ok &= tr == "REVOKED"
        elif sig == "ABSENT":
            absent_ok &= tr == "UNTRUSTED_RESEARCH"
    t(g, "all_216_provenance_combinations_were_tried", lambda: (len(combos) == 2 * 3 * 4 * 3 * 3))
    t(g, "signed_trusted_only_for_the_one_complete_combination", lambda: (trusted_ok))
    t(g, "a_replay_always_wins", lambda: (never_trusted_wrong))
    t(g, "a_revoked_issuer_always_beats_everything_but_replay", lambda: (revoked_ok))
    t(g, "an_absent_signature_is_never_more_than_research", lambda: (absent_ok))
    t(g, "every_derived_value_is_a_declared_trust_level", lambda: (all(evc1.derive_trust({"hash_consistent": a, "signature": b, "signer": None, "issuer_trust": c, "freshness": d, "replay": e_, "verified_by": None}) in evc1.TRUST_LEVELS for a, b, c, d, e_ in combos)))
    full_prov = trusted_prov()
    for field, bad in (("hash_consistent", False), ("signature", "INVALID"), ("signature", "ABSENT"), ("issuer_trust", "UNTRUSTED"), ("issuer_trust", "REVOKED"), ("freshness", "EXPIRED"), ("freshness", "UNKNOWN"), ("replay", "REPLAYED"), ("replay", "UNKNOWN")):
        t(g, "single_weakness_%s_%s_loses_trusted_status" % (field, bad), evc1.derive_trust(dict(full_prov, **{field: bad})) != "SIGNED_TRUSTED")

    # ---------------------------------------------------------------- canonical serialization
    g = "CANONICAL"
    t(g, "key_order_does_not_change_the_digest", lambda: (evc1.digest_of({"a": 1, "b": [1, 2]}) == evc1.digest_of({"b": [1, 2], "a": 1})))
    t(g, "list_order_does_change_the_digest", lambda: (evc1.digest_of([1, 2]) != evc1.digest_of([2, 1])))
    t(g, "bool_and_int_digest_differently", lambda: (evc1.digest_of({"x": True}) != evc1.digest_of({"x": 1})))
    t(g, "null_and_missing_digest_differently", lambda: (evc1.digest_of({"x": None}) != evc1.digest_of({})))
    t(g, "floats_are_refused", lambda: (all(_raises(lambda v=v: evc1.canonical_bytes({"x": v})) for v in (1.5, 1.0, float("nan"), float("inf")))))
    t(g, "non_string_keys_are_refused", lambda: (_raises(lambda: evc1.canonical_bytes({1: "a"}))))
    t(g, "unsupported_types_are_refused", lambda: (_raises(lambda: evc1.canonical_bytes({"x": {1, 2}})) and _raises(lambda: evc1.canonical_bytes({"x": b"y"}))))
    t(g, "unicode_is_kept_and_stable", lambda: (evc1.canonical_bytes({"x": "é"}) == '{"x":"é"}'.encode("utf-8")))
    t(g, "no_whitespace_in_canonical_form", lambda: (b" " not in evc1.canonical_bytes({"a": [1, 2, {"b": None}]})))
    t(g, "sha256_of_empty_object_matches_the_known_value", lambda: (evc1.digest_of({}) == hashlib.sha256(b"{}").hexdigest()))

    # ---------------------------------------------------------------- compatibility rules and consumer matrix
    g = "COMPATIBILITY"
    v10 = event_of("mcr.execution.receipt")
    v11_unknown = reseal(v10, lambda x: x.update(contract_version="1.1.0", future_field={"a": 1}))
    v11_plain = reseal(v10, lambda x: x.update(contract_version="1.1.0"))
    v11_crit = reseal(v10, lambda x: x.update(contract_version="1.1.0", future_field=1, critical=["future_field"]))
    v10_unknown = reseal(v10, lambda x: x.update(future_field=1))
    v2 = dict(v10, contract_version="2.0.0")
    ext = reseal(v10, lambda x: x.update(extensions={"vendor.note": "kept"}))
    t(g, "a_newer_minor_with_no_new_fields_is_accepted_by_an_older_consumer", lambda: (accepts(v11_plain)))
    k, u = evc1.parse(v11_unknown)
    t(g, "a_newer_minor_unknown_field_is_retained_not_interpreted", lambda: (u == {"future_field": {"a": 1}} and "future_field" not in k))
    t(g, "an_unknown_field_in_the_same_minor_is_rejected", lambda: (rejects(v10_unknown, "unknown top-level")))
    t(g, "an_unknown_critical_field_from_a_newer_minor_is_rejected", lambda: (rejects(v11_crit, "critical")))
    t(g, "a_critical_name_with_no_matching_field_is_still_rejected", lambda: (rejects(reseal(v10, lambda x: x.update(critical=["something"])), "critical")))
    t(g, "critical_must_be_a_list", lambda: (rejects(dict(v10, critical="x"))))
    t(g, "another_major_is_rejected_even_if_otherwise_identical", lambda: (rejects(v2, "major")))
    t(g, "a_consumer_that_supports_minor_one_rejects_unknown_fields_of_minor_one", lambda: (rejects(v11_unknown, "unknown top-level", supported_minor=1)))
    t(g, "extensions_are_retained_in_known_events", lambda: (accepts(ext) and evc1.parse(ext)[0]["extensions"] == {"vendor.note": "kept"}))
    t(g, "extensions_do_not_change_authority_effect", lambda: (ext["authority_effect"] == "NONE"))
    matrix = {}
    for cname, kw in (("consumer_v1_0", {"supported_minor": 0}), ("consumer_v1_1", {"supported_minor": 1})):
        for ename, ev in (("v1_0_event", v10), ("v1_1_plain", v11_plain), ("v1_1_unknown_noncritical", v11_unknown), ("v1_1_unknown_critical", v11_crit), ("v1_0_unknown_field", v10_unknown), ("v2_0_event", v2)):
            try:
                _, unk = evc1.parse(ev, **kw)
                res = "ACCEPTED" if not unk else "ACCEPTED_WITH_UNRECOGNIZED_RETAINED"
            except evc1.ContractError as exc:
                res = "REJECTED"
            matrix.setdefault(cname, {})[ename] = res
    t(g, "consumer_matrix_v1_0", matrix["consumer_v1_0"] == {"v1_0_event": "ACCEPTED", "v1_1_plain": "ACCEPTED", "v1_1_unknown_noncritical": "ACCEPTED_WITH_UNRECOGNIZED_RETAINED",
                                                              "v1_1_unknown_critical": "REJECTED", "v1_0_unknown_field": "REJECTED", "v2_0_event": "REJECTED"})
    t(g, "consumer_matrix_v1_1", lambda: (matrix["consumer_v1_1"]["v1_1_unknown_noncritical"] == "REJECTED" and matrix["consumer_v1_1"]["v2_0_event"] == "REJECTED" and matrix["consumer_v1_1"]["v1_0_event"] == "ACCEPTED"))
    G["COMPATIBILITY"].append("consumer_matrix_recorded")
    T["consumer_matrix_recorded"] = True

    g = "MIGRATION"
    m = evc1.migrate(v10, "1.1.0")
    t(g, "migration_relabels_within_the_same_major", lambda: (m["contract_version"] == "1.1.0" and accepts(m)))
    t(g, "migration_keeps_the_claim_and_its_payload_digest", lambda: (m["claim"] == v10["claim"] and m["digests"]["payload"] == v10["digests"]["payload"]))
    t(g, "migration_records_lineage_and_source_digest", lambda: (m["lineage"]["source_event_id"] == v10["id"] and m["lineage"]["source_digest"] == v10["integrity"]["event_digest"] and m["lineage"]["transformations"][-1]["step"] == "migrate"))
    t(g, "migration_gives_a_new_event_id_and_a_new_integrity_digest", lambda: (m["id"] != v10["id"] and m["integrity"]["event_digest"] != v10["integrity"]["event_digest"]))
    t(g, "migration_never_changes_evidence_or_trust", lambda: (m["evidence"] == v10["evidence"] and m["authority_effect"] == "NONE"))
    m2 = evc1.migrate(m, "1.2.0")
    t(g, "two_migrations_keep_two_lineage_steps", lambda: (len(m2["lineage"]["transformations"]) == 2 and m2["lineage"]["source_event_id"] == m["id"]))
    t(g, "cross_major_migration_is_refused", lambda: (_raises(lambda: evc1.migrate(v10, "2.0.0"))))
    t(g, "a_downgrade_that_would_drop_unrecognized_fields_is_refused", lambda: (_raises(lambda: evc1.migrate(v11_unknown, "1.0.0"))))
    t(g, "a_downgrade_of_a_clean_event_is_allowed", lambda: (accepts(evc1.migrate(v11_plain, "1.0.0"))))
    t(g, "migrating_a_tampered_event_is_refused", lambda: (_raises(lambda: evc1.migrate(dict(v10, time="2026-10-21T13:00:00Z")))))
    t(g, "migration_is_deterministic", lambda: (evc1.migrate(v10, "1.1.0") == evc1.migrate(v10, "1.1.0")))

    # ---------------------------------------------------------------- cross-check with the optional library
    g = "LIBRARY_CROSS_CHECK"
    if have_js:
        import jsonschema
        corpus = [ok_e, v11_plain, dp, rb, ev0, oc, v]
        bad_corpus = [dict(ok_e, type="x"), {k: v_ for k, v_ in ok_e.items() if k != "claim"}, dict(ok_e, authority_effect="GRANT"), reseal(ok_e, lambda x: x["claim"].update(extra=1))]
        t(g, "library_and_mini_validator_agree_on_valid_events", lambda: (all((not MJ.validate(e, evc1.SCHEMA)) == (not list(jsonschema.Draft202012Validator(evc1.SCHEMA).iter_errors(e))) for e in corpus)))
        t(g, "library_and_mini_validator_agree_on_invalid_events", lambda: (all((not MJ.validate(e, evc1.SCHEMA)) == (not list(jsonschema.Draft202012Validator(evc1.SCHEMA).iter_errors(e))) for e in bad_corpus)))
        t(g, "library_check_schema_accepts_the_schema", lambda: (safe(lambda: jsonschema.Draft202012Validator.check_schema(evc1.SCHEMA) is None)))
    # mini validator unit tests (it guards the contract)
    g = "MINI_VALIDATOR"
    sc = {"type": "object", "properties": {"a": {"type": "integer", "minimum": 1}, "b": {"enum": ["x", "y"]}}, "required": ["a"], "additionalProperties": False}
    t(g, "mini_accepts_a_valid_object", lambda: (MJ.validate({"a": 1, "b": "x"}, sc) == []))
    t(g, "mini_rejects_bool_as_integer", lambda: (MJ.validate({"a": True}, sc) != []))
    t(g, "mini_rejects_below_minimum", lambda: (MJ.validate({"a": 0}, sc) != []))
    t(g, "mini_rejects_missing_required", lambda: (MJ.validate({}, sc) != []))
    t(g, "mini_rejects_extra_property", lambda: (MJ.validate({"a": 1, "z": 1}, sc) != []))
    t(g, "mini_rejects_bad_enum", lambda: (MJ.validate({"a": 1, "b": "q"}, sc) != []))
    t(g, "mini_enum_is_type_strict", lambda: (MJ.validate({"a": 1, "b": 1}, {"properties": {"b": {"enum": [True]}}}) != [] and MJ.validate(1, {"enum": [True]}) != []))
    t(g, "mini_const_is_type_strict", lambda: (MJ.validate(1, {"const": True}) != [] and MJ.validate(True, {"const": True}) == []))
    t(g, "mini_oneof_requires_exactly_one", lambda: (MJ.validate(1, {"oneOf": [{"type": "integer"}, {"type": "number"}]}) != [] and MJ.validate(1.5, {"oneOf": [{"type": "integer"}, {"type": "number"}]}) == []))
    t(g, "mini_unsupported_keyword_fails_closed", lambda: (_raises(lambda: MJ.validate(1, {"multipleOf": 2}))))
    t(g, "mini_ref_resolves_locally_and_rejects_remote", lambda: (MJ.validate(1, {"$defs": {"n": {"type": "integer"}}, "$ref": "#/$defs/n"}) == [] and _raises(lambda: MJ.validate(1, {"$ref": "http://x/y"}))))
    t(g, "mini_date_time_shape", lambda: (MJ.validate("2026-10-21T12:00:00Z", {"format": "date-time"}) == [] and MJ.validate("2026-10-21 12:00:00", {"format": "date-time"}) != []))
    t(g, "mini_array_rules", lambda: (MJ.validate([1, 1], {"uniqueItems": True}) != [] and MJ.validate([], {"minItems": 1}) != [] and MJ.validate([1, "a"], {"items": {"type": "integer"}}) != []))
    t(g, "mini_not_and_if_then_else", lambda: (MJ.validate(1, {"not": {"type": "integer"}}) != [] and MJ.validate(1, {"if": {"type": "integer"}, "then": {"minimum": 5}}) != [] and MJ.validate("a", {"if": {"type": "integer"}, "then": {"minimum": 5}, "else": {"minLength": 3}}) != []))


def safe(fn):
    try:
        return bool(fn())
    except Exception:
        return False


def _raises(fn):
    try:
        fn()
    except Exception:
        return True
    return False


def write_artifacts():
    os.makedirs(os.path.dirname(SCHEMA_FILE), exist_ok=True)
    with open(SCHEMA_FILE, "w", newline="\n") as fh:
        fh.write(json.dumps(evc1.build_schema(), indent=2, sort_keys=True) + "\n")
    os.makedirs(EXAMPLES_DIR, exist_ok=True)
    for etype in sorted(evc1.TYPE_TABLE):
        with open(os.path.join(EXAMPLES_DIR, etype.replace("mcr.", "").replace(".", "_") + ".json"), "w", newline="\n") as fh:
            fh.write(json.dumps(event_of(etype), indent=2, sort_keys=True) + "\n")


def main(argv):
    if "--write-artifacts" in argv:
        write_artifacts()
    run()
    failed = sorted(n for n, ok in T.items() if not ok)
    groups = {gk: "PASS" if all(T[n] for n in names) else "FAIL" for gk, names in G.items()}
    digest = hashlib.sha256(json.dumps(sorted(T), separators=(",", ":")).encode()).hexdigest().upper()
    result = {"stage": "MCR3_EVIDENCE_CONTRACT_V1", "evidence_class": "SYNTHETIC/LOCAL", "tests": len(T), "failed": failed, "groups": groups, "tests_digest": digest,
              "not_verified": NOT_VERIFIED, "network_calls": 0}
    out = json.dumps(result, indent=2, sort_keys=True)
    if "--out" in argv:
        with open(argv[argv.index("--out") + 1], "w", newline="\n") as fh:
            fh.write(out + "\n")
    print(out)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
