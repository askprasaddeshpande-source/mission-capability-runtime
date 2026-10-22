"""Corrective-closure regression tests (B1 resume keeps revocation, B2 compensation guards, B3 clock and expiry validation,
B4 capability approval binding, B8 ledger rollback on resume). Offline fixtures only. Each test was written to FAIL on the
code before the repair (see reports/mcr3/MCR_3_0_FINAL_CORRECTIVE_CLOSURE_R2.md); B5/B6 are in validate_mcr3_scan.py and B7 in
run_mcr3_verifier_attacks.py."""
import hashlib
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
if os.environ.get("MCR3_OVERRIDE_DIR"):          # mutation harness: a mutated module shadows the real one
    sys.path.insert(0, os.environ["MCR3_OVERRIDE_DIR"])
import mcr3_model as M  # noqa: E402
import mcr3_authority as A  # noqa: E402
from mcr3_model import GuardError, Mission, RevocationList, make  # noqa: E402
import validate_mcr3_hardening as H  # noqa: E402
from validate_mcr3_inherited import FP, fixture, to_prewrite  # noqa: E402

T, G = {}, {}
UP = ("intent", "principal", "delegation", "capability", "provider", "tx", "budget", "outcome_contract", "readback_contract", "authority")
HX = "a" * 64


def t(group, name, ok):
    try:
        ok = ok() if callable(ok) else ok
    except Exception:
        ok = False
    T[name] = bool(ok)
    G.setdefault(group, []).append(name)


def raises(fn, text=None, exc=(GuardError,)):
    try:
        fn()
    except exc as e:
        return text is None or text in str(e)
    except Exception:
        return False
    return False


def governed(rev, **kw):
    f = fixture()[1]
    m = Mission("M-SYN-1", "TX-SYN-1", 1, revocation_check=rev, **kw)
    return m, f


def resume(lease, f, m, **kw):
    return Mission.resume(lease, f["cp"], f["bu"], "M-SYN-1", {k: m.ev[k] for k in UP}, m.ledger, allow_volatile_ledger=True, **kw)


def run():
    # ------------------------------------------------------------------ B1 resume keeps mandatory revocation
    g = "B1_RESUME_REVOCATION"
    rl = RevocationList()
    m, f = governed(rl)
    to_prewrite(m, f)
    lease = m.checkpoint_lease()
    t(g, "a_lease_records_that_a_revocation_source_governed_the_mission", lambda: lease.get("revocation_required") is True)
    rl.revoke(f["au"]["object_hash"])
    t(g, "resume_without_the_revocation_source_is_refused", lambda: raises(lambda: resume(lease, f, m), "revocation_check"))
    t(g, "resume_with_a_source_that_reports_the_authority_revoked_is_refused", lambda: raises(lambda: resume(lease, f, m, revocation_check=rl), "revoked"))
    t(g, "resume_with_a_clean_source_works", lambda: resume(lease, f, m, revocation_check=RevocationList()).state == "PREWRITE_VALIDATED")
    t(g, "resume_with_a_non_callable_source_is_refused", lambda: raises(lambda: resume(lease, f, m, revocation_check="yes"), "callable"))
    t(g, "a_resumed_mission_asks_the_source_again_before_sending", lambda: raises(lambda: _send_after(resume(lease, f, m, revocation_check=_Flip()), "MUT-1"), "revoked"))
    old = make("ContinuationLease", **{k: v for k, v in lease.items() if k not in ("kind", "object_hash", "revocation_required")})
    t(g, "a_lease_that_does_not_say_it_was_ungoverned_is_treated_as_governed", lambda: raises(lambda: resume(old, f, m), "revocation_check"))
    m0, f0 = governed(None)
    to_prewrite(m0, f0)
    lease0 = m0.checkpoint_lease()
    t(g, "a_lease_from_an_ungoverned_mission_resumes_without_a_source", lambda: lease0.get("revocation_required") is False and resume(lease0, f0, m0).state == "PREWRITE_VALIDATED")

    # ------------------------------------------------------------------ B2 compensation grant revocation and delegation expiry
    g = "B2_COMPENSATION_GUARDS"
    rl = RevocationList()
    mm, ff, gg = H.comp_mission(1)
    mm._revoked = rl
    rl.revoke(gg["object_hash"])
    t(g, "a_revoked_compensation_grant_blocks_the_compensating_send", lambda: raises(lambda: mm.begin_compensation(), "comp_grant revoked") and len(mm.ledger.for_authority(gg["object_hash"])) == 0)
    rl.revoked.clear()
    asked = []
    mm._revoked = lambda kind, h: (asked.append(kind), False)[1]
    t(g, "the_source_is_asked_about_the_grant_too", lambda: mm.begin_compensation() == 1 and "comp_grant" in asked)
    mm, ff, gg = H.comp_mission(1)
    mm._clock = lambda: 1e11                                  # far beyond the delegation's expires_at
    t(g, "an_expired_delegation_blocks_the_compensating_send", lambda: raises(lambda: mm.begin_compensation(), "expired") and len(mm.ledger.for_authority(gg["object_hash"])) == 0)
    mm, ff, gg = H.comp_mission(1)
    t(g, "compensation_with_a_valid_delegation_and_clock_proceeds", lambda: mm.begin_compensation() == 1)

    # ------------------------------------------------------------------ B3 clocks and expiry values
    g = "B3_CLOCK_AND_EXPIRY"
    nan, inf = float("nan"), float("inf")

    def boom():
        raise RuntimeError("clock down")
    for label, clk in (("nan", lambda: nan), ("infinity", lambda: inf), ("negative", lambda: -1.0), ("string", lambda: "2020"), ("none", lambda: None),
                       ("bool", lambda: True), ("raising", boom)):
        m, f = governed(None, clock=clk)
        m.context_ready(f["intent"], f["pr"])
        t(g, "a_%s_clock_cannot_authorize" % label, lambda m=m, f=f: raises(lambda: m.authorize(f["dl"], f["au"], f["bu"]), "clock") and m.state == "CONTEXT_READY")
    m, f = governed(None)
    to_prewrite(m, f)
    m._clock = lambda: nan
    t(g, "a_nan_clock_cannot_send", lambda: raises(lambda: m.begin_execution("MUT-1", FP), "clock") and m.mutations_sent == 0)
    t(g, "a_huge_integer_expiry_is_refused_not_an_overflow", lambda: M.parse_expiry(10 ** 400) is None and M.parse_expiry(float("nan")) is None and M.parse_expiry(inf) is None)
    for label, clk in (("nan", lambda: nan), ("infinity", lambda: inf), ("string", lambda: "x"), ("raising", boom)):
        reg, cap, rec = _approvable(clk)
        t(g, "capability_registry_with_a_%s_clock_refuses_an_approval" % label, lambda reg=reg, cap=cap, rec=rec: raises(lambda: reg.record_approval(cap, rec), "clock", (A.AuthorityError,)) and cap.state == "QUALIFIED")
    st = {"now": 1.0}
    reg, cap, rec = _approvable(lambda: st["now"])
    reg.record_approval(cap, rec)
    st["now"] = nan
    t(g, "an_approval_lapses_when_the_clock_becomes_unusable", lambda: reg.effective_state(cap) == "QUALIFIED")

    huge = 10 ** 400
    m, f = governed(None, clock=lambda: huge)
    m.context_ready(f["intent"], f["pr"])
    t(g, "a_huge_integer_clock_is_refused_with_a_guard_error_not_an_overflow", lambda: raises(lambda: m.authorize(f["dl"], f["au"], f["bu"]), "clock") and m.state == "CONTEXT_READY")
    reg, cap, rec = _approvable(lambda: huge)
    t(g, "a_huge_integer_clock_refuses_a_capability_approval_with_the_right_error", lambda: raises(lambda: reg.record_approval(cap, rec), "clock", (A.AuthorityError,)))
    st2 = {"now": 1.0}
    reg, cap, rec = _approvable(lambda: st2["now"])
    reg.record_approval(cap, rec)
    st2["now"] = huge
    t(g, "view_lapses_instead_of_crashing_when_the_clock_becomes_a_huge_integer", lambda: reg.effective_state(cap) == "QUALIFIED" and reg.view(cap, _scope())["may_request_execution_review"] is False)
    AR = A.AdapterRegistry
    for label, clk in (("minus_infinity", lambda: -inf), ("negative", lambda: -1.0), ("bool", lambda: True), ("string", lambda: "x"), ("huge", lambda: huge), ("nan", lambda: nan), ("raising", boom)):
        t(g, "adapter_promotion_with_a_%s_clock_is_refused" % label, lambda clk=clk: _adapter_promotion_refused(clk))

    # ------------------------------------------------------------------ B4 capability approval binding
    g = "B4_APPROVAL_BINDING"
    reg, cap, rec = _approvable(lambda: 1.0)
    for field in ("capability_version", "capability_digest", "qualification_digest", "to_state"):
        t(g, "an_approval_without_%s_is_refused" % field, lambda f=field: raises(lambda: reg.record_approval(cap, {k: v for k, v in rec.items() if k != f}), "not bound", (A.AuthorityError,)) and cap.state == "QUALIFIED")
    t(g, "an_approval_for_another_version_is_refused", lambda: raises(lambda: reg.record_approval(cap, dict(rec, capability_version="9.9.9")), "capability_version", (A.AuthorityError,)))
    t(g, "an_approval_for_another_digest_is_refused", lambda: raises(lambda: reg.record_approval(cap, dict(rec, capability_digest="f" * 64)), "capability_digest", (A.AuthorityError,)))
    t(g, "an_approval_bound_to_another_qualification_is_refused", lambda: raises(lambda: reg.record_approval(cap, dict(rec, qualification_digest="e" * 64)), "qualification_digest", (A.AuthorityError,)))
    t(g, "an_approval_for_another_target_state_is_refused", lambda: raises(lambda: reg.record_approval(cap, dict(rec, to_state="ACTIVE")), "to_state", (A.AuthorityError,)))
    reg.record_approval(cap, rec)
    other = reg.discover("create_object", "2.0.0-malicious", "f" * 64)
    reg.verify(other, HX, True)
    reg.qualify(other, HX, "GO", "r")
    t(g, "one_approval_cannot_be_replayed_onto_another_capability_version", lambda: raises(lambda: reg.record_approval(other, rec), "not bound", (A.AuthorityError,)) and other.state == "QUALIFIED")
    t(g, "the_other_version_is_not_reported_as_approved", lambda: reg.view(other, _scope())["may_request_execution_review"] is False and reg.view(cap, _scope())["may_request_execution_review"] is True)

    # ------------------------------------------------------------------ B8 ledger rollback on resume
    g = "B8_LEDGER_ROLLBACK"
    d = tempfile.mkdtemp(prefix="m3corr_")
    try:
        path = os.path.join(d, "ledger.txt")
        m, f = fixture()
        m.ledger = M.ReplayLedger(path)
        to_prewrite(m, f)
        pre_lease = m.checkpoint_lease()                      # cut BEFORE the send
        shutil.copyfile(path, path + ".old")
        m.begin_execution("MUT-1", FP)
        post_lease = m.checkpoint_lease()
        anchor_after = m.ledger.anchor()                      # held outside the ledger host
        shutil.copyfile(path + ".old", path)                  # the ledger is restored to its pre-send state
        ev = {k: m.ev[k] for k in UP}

        def rs(lease, **kw):
            return Mission.resume(lease, f["cp"], f["bu"], "M-SYN-1", ev, M.ReplayLedger(path), **kw)
        t(g, "a_restored_ledger_is_caught_by_the_trusted_anchor", lambda: raises(lambda: rs(pre_lease, trusted_anchor=anchor_after), "fewer entries"))
        t(g, "resume_on_a_durable_ledger_without_an_anchor_is_refused_by_default", lambda: raises(lambda: rs(pre_lease), "trusted_anchor"))
        t(g, "an_explicitly_unanchored_resume_is_the_documented_residual_replay_risk", lambda: rs(pre_lease, allow_unanchored_ledger=True).state == "PREWRITE_VALIDATED")
        shutil.copyfile(path + ".old", path)
        t(g, "a_malformed_trusted_anchor_is_refused", lambda: raises(lambda: rs(pre_lease, trusted_anchor={"count": 1}), "malformed"))
        # honest ledger: rebuild the post-send ledger from scratch with the same mission steps is not possible, so check the honest path in-process
        m2, f2 = fixture()
        m2.ledger = M.ReplayLedger(os.path.join(d, "honest.txt"))
        to_prewrite(m2, f2)
        m2.begin_execution("MUT-1", FP)
        lease2 = m2.checkpoint_lease()
        anchor2 = m2.ledger.anchor()
        ev2 = {k: m2.ev[k] for k in UP}
        t(g, "an_honest_resume_with_the_current_anchor_works", lambda: Mission.resume(lease2, f2["cp"], f2["bu"], "M-SYN-1", ev2, M.ReplayLedger(os.path.join(d, "honest.txt")), trusted_anchor=anchor2).state == "COMMIT_STATE_UNKNOWN")
        t(g, "an_anchor_from_a_different_ledger_is_refused", lambda: raises(lambda: Mission.resume(lease2, f2["cp"], f2["bu"], "M-SYN-1", ev2, M.ReplayLedger(os.path.join(d, "honest.txt")), trusted_anchor=anchor_after), "differs"))
        t(g, "a_truthy_string_is_not_an_explicit_acceptance_of_the_replay_risk", lambda: raises(lambda: rs(pre_lease, allow_unanchored_ledger="no"), "trusted_anchor"))
        t(g, "a_volatile_ledger_resume_needs_no_anchor", lambda: Mission.resume(pre_lease_volatile(), *_vol_args(), allow_volatile_ledger=True).state == "PREWRITE_VALIDATED")
        t(g, "post_send_lease_is_unaffected_by_the_policy_when_anchored", lambda: post_lease.get("ledger_anchor") is not None)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _adapter_promotion_refused(clk):
    ar = A.AdapterRegistry(approval_verifier=A.RecordedApprovalVerifier({"A1"}), clock=clk)
    ad = A.Adapter(adapter_id="e", source_runtime_version="2.0.0", target_contract_version="1.0.0", supported_capabilities=["create_object"],
                   evidence_classification="HISTORICAL", trust_requirements="unsigned; research only")
    ar.register(ad, "1.0.0")
    rec = A.adapter_approval_record("A1", _scope(), "e", "1.0.0", "SHADOW", HX, expires_at="2020-01-01")
    try:
        ar.promote("e", "1.0.0", "SHADOW", HX, rec, _scope())
        return False
    except A.AuthorityError:
        pass
    return ar.mode("e", "1.0.0") == "OBSERVATION_ONLY"


def _gate_dirs():
    import check_release_gate as C
    d = tempfile.mkdtemp(prefix="m3gate_")
    good = {"MUTATION_CHECK": "PASS", "mutants": 50, "by_module": {}, "inconclusive": [], "unexplained_survivors": [], "not_applied": [], "detected_by_hang": [], "explained_survivors": {}}
    for mod in C.targets():
        j = dict(good, by_module={mod: {"mutants": 50, "assertion": 20, "crash": 29, "hang": 0, "survivors": 1}})
        open(os.path.join(d, "mutation-%s.json" % mod), "w").write(json.dumps(j))
    att = {"all_passed": True, "scenarios": 31, "head_attacked": "S" * 40, "results": {k: {} for k in ("A13a", "A13b", "A13c", "A13d", "A13e", "A13f", "N1_x", "N2_x", "N3_x")}}
    open(os.path.join(d, "attacks.json"), "w").write(json.dumps(att))
    return C, d


def gate_checks():
    g = "RELEASE_GATE_CHECKER"
    C, d = _gate_dirs()
    try:
        t(g, "complete_artifacts_for_the_candidate_sha_pass", lambda: C.decide(d, "S" * 40)["RELEASE_GATE_HEAVY"] == "PASS")
        t(g, "artifacts_for_another_sha_fail", lambda: C.decide(d, "T" * 40)["RELEASE_GATE_HEAVY"] == "FAIL")
        first = C.targets()[0]
        path = os.path.join(d, "mutation-%s.json" % first)
        saved = open(path).read()
        os.remove(path)
        t(g, "a_missing_module_result_fails", lambda: C.decide(d, "S" * 40)["RELEASE_GATE_HEAVY"] == "FAIL")
        tiny = json.loads(saved)
        tiny["by_module"][first] = {"mutants": 1, "assertion": 0, "crash": 1, "hang": 0, "survivors": 0}
        tiny["mutants"] = 1
        open(path, "w").write(json.dumps(tiny))
        t(g, "a_one_mutant_crash_only_result_fails", lambda: C.decide(d, "S" * 40)["RELEASE_GATE_HEAVY"] == "FAIL")
        bad = json.loads(saved)
        bad["unexplained_survivors"] = ["x"]
        open(path, "w").write(json.dumps(bad))
        t(g, "an_unexplained_survivor_fails", lambda: C.decide(d, "S" * 40)["RELEASE_GATE_HEAVY"] == "FAIL")
        open(path, "w").write(saved)
        os.remove(os.path.join(d, "attacks.json"))
        t(g, "missing_attack_results_fail", lambda: C.decide(d, "S" * 40)["RELEASE_GATE_HEAVY"] == "FAIL")
    finally:
        shutil.rmtree(d, ignore_errors=True)


class _Flip:
    """Revocation source that is clean at resume time and reports everything revoked afterwards."""
    def __init__(self):
        self.calls = 0

    def __call__(self, kind, h):
        self.calls += 1
        return self.calls > 3                                  # principal, delegation, authority are checked at resume; the next check denies


def _send_after(m, mid):
    m.begin_execution(mid, FP)


def _scope():
    return {"owner": "o", "capability_id": "create_object", "provider_id": "SYN", "target_system": "T", "operation": "create", "environment": "TEST", "policy_digest": HX}


def _approvable(clock):
    reg = A.CapabilityRegistry(approval_verifier=A.RecordedApprovalVerifier({"APPR-1"}), clock=clock)
    cap = reg.discover("create_object", "1.0.0", HX)
    reg.verify(cap, HX, True)
    reg.qualify(cap, HX, "GO", "r")
    return reg, cap, A.capability_approval_record(cap, _scope(), "APPR-1", "2099-01-01")


_VOL = {}


def pre_lease_volatile():
    m, f = fixture()
    to_prewrite(m, f)
    _VOL["a"] = (f["cp"], f["bu"], "M-SYN-1", {k: m.ev[k] for k in UP}, m.ledger)
    return m.checkpoint_lease()


def _vol_args():
    return _VOL["a"]


def main(argv):
    run()
    gate_checks()
    failed = sorted(n for n, ok in T.items() if not ok)
    groups = {gk: "PASS" if all(T[n] for n in names) else "FAIL" for gk, names in G.items()}
    digest = hashlib.sha256(json.dumps(sorted(T), separators=(",", ":")).encode()).hexdigest().upper()
    result = {"stage": "MCR3_CORRECTIVE_CLOSURE", "evidence_class": "SYNTHETIC/LOCAL", "tests": len(T), "failed": failed, "groups": groups, "tests_digest": digest, "network_calls": 0}
    out = json.dumps(result, indent=2, sort_keys=True)
    if "--out" in argv:
        with open(argv[argv.index("--out") + 1], "w", newline="\n") as fh:
            fh.write(out + "\n")
    print(out)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
