"""Tests for the portable readback rules and the offline SAP/ADT-style reference provider (NOT verified against a live system)."""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
if os.environ.get("MCR3_OVERRIDE_DIR"):          # mutation harness: a mutated module shadows the real one
    sys.path.insert(0, os.environ["MCR3_OVERRIDE_DIR"])
import mcr3_model as M  # noqa: E402
import mcr3_readback as R  # noqa: E402
from validate_mcr3_inherited import FP, commit_obs, exec_receipt, fixture, outcome, to_prewrite  # noqa: E402

T, G = {}, {}
NAME = "ZC_SYN_OBJ"


def t(group, name, ok):
    try:
        ok = ok() if callable(ok) else ok
    except Exception:
        ok = False
    T[name] = bool(ok)
    G.setdefault(group, []).append(name)


def src(text=None):
    text = text or ("define view entity %s as select from x" % NAME)
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()


def ok_read(version, endpoint="DDLS", text=None):
    s, h = src(text)
    return R.raw_read(version, endpoint, 200, source_text=s, source_sha256_reported=h)


def nf(version, endpoint="DDLS", names=NAME):
    return R.raw_read(version, endpoint, 404, error_names_object=names)


def der(active, inactive):
    return R.derive_readback(NAME, "DDLS", {"active": active, "inactive": inactive})


def run():
    g = "EXISTENCE"
    d = der(ok_read("active"), ok_read("inactive"))
    t(g, "both_versions_found_is_exists_and_active", lambda: (d["existence"] == "EXISTS" and d["activation"] == "ACTIVE"))
    d = der(nf("active"), ok_read("inactive"))
    t(g, "only_the_inactive_version_is_exists_but_inactive", lambda: (d["existence"] == "EXISTS" and d["activation"] == "INACTIVE"))
    d = der(ok_read("active"), nf("inactive"))
    t(g, "only_the_active_version_is_exists_and_active", lambda: (d["existence"] == "EXISTS" and d["activation"] == "ACTIVE"))
    d = der(nf("active"), nf("inactive"))
    t(g, "both_versions_named_absent_is_absent", lambda: (d["existence"] == "ABSENT" and d["activation"] == "UNKNOWN" and d["observed"]["exists"] is False))
    d = der(nf("active", names=None), nf("inactive", names=None))
    t(g, "an_unnamed_404_is_unknown_not_absent", lambda: (d["existence"] == "UNKNOWN" and d["observed"]["exists"] == "UNKNOWN"))
    d = der(nf("active", names="OTHER_OBJECT"), nf("inactive", names="OTHER_OBJECT"))
    t(g, "a_404_naming_another_object_is_unknown_not_absent", lambda: (d["existence"] == "UNKNOWN"))
    d = der(nf("active"), nf("inactive", names=None))
    t(g, "one_named_and_one_unnamed_absent_is_unknown", lambda: (d["existence"] == "UNKNOWN"))
    d = der(nf("active", endpoint="CLAS"), nf("inactive", endpoint="CLAS"))
    t(g, "a_wrong_endpoint_404_is_unknown_never_absent", lambda: (d["existence"] == "UNKNOWN" and d["source_level"] == "INFERRED_OR_REGEX"))
    d = der(ok_read("active", endpoint="CLAS"), ok_read("inactive", endpoint="CLAS"))
    t(g, "a_wrong_endpoint_200_is_unknown_never_exists", lambda: (d["existence"] == "UNKNOWN"))
    d = der(R.raw_read("active", "DDLS", None), R.raw_read("inactive", "DDLS", None))
    t(g, "no_response_is_unknown", lambda: (d["existence"] == "UNKNOWN" and d["source_level"] == "INFERRED_OR_REGEX"))
    d = der(R.raw_read("active", "DDLS", 500), R.raw_read("inactive", "DDLS", 503))
    t(g, "server_errors_are_unknown", lambda: (d["existence"] == "UNKNOWN"))
    s, h = src()
    d = der(R.raw_read("active", "DDLS", 200, source_text=s, source_sha256_reported="0" * 64), nf("inactive"))
    t(g, "a_200_whose_source_hash_does_not_match_is_unknown", lambda: (d["existence"] == "UNKNOWN"))
    d = der(ok_read("active", text="unrelated source text"), nf("inactive"))
    t(g, "a_200_whose_source_lacks_the_object_name_is_unknown", lambda: (d["existence"] == "UNKNOWN"))
    d = der(R.raw_read("active", "DDLS", 200, source_text="", source_sha256_reported=""), nf("inactive"))
    t(g, "an_empty_200_body_is_unknown", lambda: (d["existence"] == "UNKNOWN"))
    t(g, "malformed_reads_are_unknown_not_a_crash", lambda: (R.derive_readback(NAME, "DDLS", {"active": "x", "inactive": None})["existence"] == "UNKNOWN" and R.derive_readback(NAME, "DDLS", {})["existence"] == "UNKNOWN"))
    t(g, "object_name_matching_is_case_insensitive_for_identity", lambda: (der(ok_read("active", text="DEFINE VIEW ENTITY zc_syn_obj"), nf("inactive"))["existence"] == "EXISTS"))

    g = "ACTIVATION"
    t(g, "inactive_exists_with_unknown_active_read_is_unknown_activation", lambda: (der(R.raw_read("active", "DDLS", 500), ok_read("inactive"))["activation"] == "UNKNOWN"))
    t(g, "activation_is_never_active_without_the_active_read", lambda: (all(der(a, i)["activation"] != "ACTIVE" for a, i in ((nf("active"), ok_read("inactive")), (R.raw_read("active", "DDLS", None), ok_read("inactive"))))))
    t(g, "the_activation_value_is_a_member_of_the_declared_set", lambda: (all(der(a, i)["activation"] in M.READBACK_ACTIVATION for a in (ok_read("active"), nf("active")) for i in (ok_read("inactive"), nf("inactive")))))

    g = "AUTHORITY_LABEL"
    d = der(ok_read("active"), ok_read("inactive"))
    t(g, "the_authoritative_level_is_a_claim_and_independence_is_false", lambda: (d["source_level"] == "AUTHORITATIVE_REPOSITORY" and d["independent_source"] is False))
    t(g, "the_reference_provider_declares_it_is_not_verified_live", lambda: (R.SapAdtReference.NOT_VERIFIED_LIVE is True))
    a, b = der(ok_read("active"), nf("inactive")), der(ok_read("active"), nf("inactive"))
    t(g, "a_second_reader_agreeing_is_required_before_independence_may_be_claimed", lambda: (R.second_reader_agrees(a, b) is True and R.second_reader_agrees(a, der(nf("active"), nf("inactive"))) is False))
    t(g, "two_unknowns_never_agree", lambda: (R.second_reader_agrees(der(R.raw_read("active", "DDLS", None), R.raw_read("inactive", "DDLS", None)), der(R.raw_read("active", "DDLS", None), R.raw_read("inactive", "DDLS", None))) is False))

    g = "PROVIDER"
    store = {(NAME, "DDLS", "active"): ok_read("active"), (NAME, "DDLS", "inactive"): ok_read("inactive")}
    prov = R.SapAdtReference(store)
    t(g, "the_reference_provider_serves_recorded_responses", lambda: (prov.readback(NAME, "DDLS")["existence"] == "EXISTS"))
    t(g, "an_object_the_provider_has_no_record_of_has_no_response_and_is_unknown", lambda: (prov.readback("ZC_OTHER", "DDLS")["existence"] == "UNKNOWN"))
    t(g, "the_provider_is_an_interface_implementation", lambda: (isinstance(prov, R.ReadbackProvider)))
    t(g, "the_base_interface_cannot_be_used_directly", lambda: ((lambda: not _ok(lambda: R.ReadbackProvider().read(NAME, "DDLS", "active")))()))

    g = "RUNTIME_INTEGRATION"
    m, f = fixture(); to_prewrite(m, f); m.begin_execution("MUT-1", FP); m.record_execution(exec_receipt(f)); m.request_readback()
    der_ok = prov.readback(NAME, "DDLS")
    obs_pred = [{"field": "exists", "op": "eq", "expected": True}]
    rb = R.to_receipt(der_ok, receipt_id="rb-prov", transaction_id="TX-SYN-1", mutation_id="MUT-1", contract_hash=f["rc"]["object_hash"])
    m.observe_readback(rb)
    t(g, "a_derived_receipt_is_accepted_by_the_runtime", lambda: (m.state == "AUTHORITATIVE_READBACK_OBSERVED" and M.verify_hash(rb)))
    t(g, "the_exists_check_is_satisfied_by_the_derived_observation", lambda: (M.Mission._checks_satisfied(f["rc"], rb)))
    t(g, "commit_is_decided_from_the_derived_receipt", lambda: (m.decide_commit(commit_obs(rb, "COMMITTED")) == "COMMITTED"))
    m2, f2 = fixture(); to_prewrite(m2, f2); m2.begin_execution("MUT-1", FP); m2.record_execution(exec_receipt(f2)); m2.request_readback()
    unk = R.SapAdtReference({}).readback(NAME, "DDLS")
    rb2 = R.to_receipt(unk, receipt_id="rb-unk", transaction_id="TX-SYN-1", mutation_id="MUT-1", contract_hash=f2["rc"]["object_hash"])
    m2.observe_readback(rb2)
    t(g, "an_unknown_derived_readback_leaves_the_commit_unknown", lambda: (m2.decide_commit(commit_obs(rb2, "UNKNOWN")) == "COMMIT_STATE_UNKNOWN"))
    m3, f3 = fixture(); to_prewrite(m3, f3); m3.begin_execution("MUT-1", FP); m3.record_execution(exec_receipt(f3)); m3.request_readback()
    ab = R.SapAdtReference({(NAME, "DDLS", "active"): nf("active"), (NAME, "DDLS", "inactive"): nf("inactive")}).readback(NAME, "DDLS")
    rb3 = R.to_receipt(ab, receipt_id="rb-abs", transaction_id="TX-SYN-1", mutation_id="MUT-1", contract_hash=f3["rc"]["object_hash"])
    m3.observe_readback(rb3)
    t(g, "a_named_absent_readback_fails_after_a_possible_mutation", lambda: (m3.decide_commit(commit_obs(rb3, "ABSENT")) == "FAILED_AFTER_POSSIBLE_MUTATION"))
    t(g, "the_canonical_contract_has_no_sap_vocabulary", lambda: (not any(w in open(os.path.join(HERE, "evc1.py"), encoding="utf-8").read().lower() for w in ("adt", "ddls", "sap_", "abap"))))
    t(g, "the_runtime_model_has_no_sap_vocabulary_in_its_logic", lambda: (not any(w in open(os.path.join(HERE, "mcr3_model.py"), encoding="utf-8").read().lower() for w in ("ddls", "abap", "/sap/bc/"))))


def _ok(fn):
    try:
        fn()
        return True
    except Exception:
        return False


def main(argv):
    run()
    failed = sorted(n for n, ok in T.items() if not ok)
    groups = {gk: "PASS" if all(T[n] for n in names) else "FAIL" for gk, names in G.items()}
    digest = hashlib.sha256(json.dumps(sorted(T), separators=(",", ":")).encode()).hexdigest().upper()
    result = {"stage": "MCR3_READBACK", "evidence_class": "SYNTHETIC/LOCAL", "tests": len(T), "failed": failed, "groups": groups, "tests_digest": digest, "network_calls": 0}
    out = json.dumps(result, indent=2, sort_keys=True)
    if "--out" in argv:
        with open(argv[argv.index("--out") + 1], "w", newline="\n") as fh:
            fh.write(out + "\n")
    print(out)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
