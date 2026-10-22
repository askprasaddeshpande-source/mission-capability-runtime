"""Phase 1 tests: typed principal, revocation of principal / delegation / authority, fail-closed revocation source (offline fixtures only)."""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
if os.environ.get("MCR3_OVERRIDE_DIR"):          # mutation harness: a mutated module shadows the real one
    sys.path.insert(0, os.environ["MCR3_OVERRIDE_DIR"])
import mcr3_model as M  # noqa: E402
from mcr3_model import GuardError, Mission, RevocationList, make  # noqa: E402
import validate_mcr3_hardening as H  # noqa: E402
from validate_mcr3_inherited import FP, fixture, happy, to_prewrite  # noqa: E402

T, G = {}, {}


def t(group, name, ok):
    try:
        ok = ok() if callable(ok) else ok
    except Exception:
        ok = False
    T[name] = bool(ok)
    G.setdefault(group, []).append(name)


def raises(fn, text=None):
    try:
        fn()
    except GuardError as e:
        return text is None or text in str(e)
    except Exception:
        return False
    return False


def mission(rev, **kw):
    m, f = fixture()
    m2 = Mission("M-SYN-1", "TX-SYN-1", 1, revocation_check=rev, **kw)
    return m2, f


def upto_authorize(m, f):
    m.context_ready(f["intent"], f["pr"])
    m.authorize(f["dl"], f["au"], f["bu"])


def run():
    g = "PRINCIPAL_TYPING"
    for name, kw in (("empty_tenant", dict(tenant="")), ("empty_principal", dict(principal_id="")), ("roles_not_a_list", dict(roles="dev")),
                     ("duplicate_roles", dict(roles=["dev", "dev"])), ("empty_role_name", dict(roles=["dev", ""])), ("non_string_role", dict(roles=["dev", 5])),
                     ("non_string_tenant", dict(tenant=7))):
        def attempt(kw=kw):
            m, f = fixture()
            body = dict(principal_id="p1", tenant="t", roles=["dev"])
            body.update(kw)
            try:
                pr = make("PrincipalContext", **body)
            except Exception:
                return True            # refused already by the schema layer
            return raises(lambda: m.context_ready(f["intent"], pr), "principal needs")
        t(g, "a_principal_with_%s_is_refused" % name, attempt)
    t(g, "a_well_formed_principal_is_accepted", lambda: (lambda mf: (mf[0].context_ready(mf[1]["intent"], mf[1]["pr"]), mf[0].state)[1] == "CONTEXT_READY")(fixture()))

    g = "REVOCATION"
    # no source: nothing is checked (documented)
    m, f = mission(None)
    upto_authorize(m, f)
    t(g, "without_a_revocation_source_authorization_proceeds", lambda: m.state == "AUTHORIZED")
    t(g, "a_non_callable_revocation_source_is_refused", lambda: raises(lambda: Mission("M", "T", 1, revocation_check="x"), "callable"))
    # clean list: whole workflow completes
    m, f = mission(RevocationList())
    happy(m, f)
    t(g, "an_empty_revocation_list_lets_the_workflow_reach_outcome_validated", lambda: m.state == "OUTCOME_VALIDATED")
    for kind, key in (("principal", "pr"), ("delegation", "dl"), ("authority", "au")):
        rl = RevocationList()
        m, f = mission(rl)
        rl.revoke(f[key]["object_hash"])
        m.context_ready(f["intent"], f["pr"])
        t(g, "a_revoked_%s_is_refused_at_authorization" % kind, lambda m=m, f=f: raises(lambda: m.authorize(f["dl"], f["au"], f["bu"]), "revoked") and m.state == "CONTEXT_READY" and "authority" not in m.ev and "delegation" not in m.ev and "budget" not in m.ev)
    # revoked between authorization and sending
    rl = RevocationList()
    m, f = mission(rl)
    to_prewrite(m, f)
    rl.revoke(f["au"]["object_hash"])
    before = (m.remaining, len(m.ledger.for_authority(f["au"]["object_hash"])))
    t(g, "revocation_after_authorization_blocks_the_send", lambda: raises(lambda: m.begin_execution("MUT-1", FP), "revoked"))
    t(g, "a_blocked_send_consumes_no_budget_and_no_ledger_entry", lambda: (m.remaining, len(m.ledger.for_authority(f["au"]["object_hash"]))) == before and m.mutations_sent == 0)
    rl.revoked.clear()
    t(g, "lifting_the_revocation_lets_the_send_proceed", lambda: (m.begin_execution("MUT-1", FP), m.state)[1] == "EXECUTION_STARTED")
    # delegation revoked mid-flight
    rl = RevocationList()
    m, f = mission(rl)
    to_prewrite(m, f)
    rl.revoke(f["dl"]["object_hash"])
    t(g, "a_revoked_delegation_blocks_the_send", lambda: raises(lambda: m.begin_execution("MUT-1", FP), "delegation revoked"))
    rl = RevocationList()
    m, f = mission(rl)
    to_prewrite(m, f)
    rl.revoke(f["pr"]["object_hash"])
    t(g, "a_revoked_principal_blocks_the_send", lambda: raises(lambda: m.begin_execution("MUT-1", FP), "principal revoked"))
    # fail closed on a bad source
    def bad_source(answer):
        def src(kind, h):
            if answer == "raise":
                raise RuntimeError("revocation service down")
            return answer
        return src
    for label, ans in (("raising", "raise"), ("none", None), ("true", True), ("zero", 0), ("string", "no"), ("empty_list", [])):
        m, f = mission(bad_source(ans))
        m.context_ready(f["intent"], f["pr"])
        t(g, "a_%s_revocation_source_denies_authorization" % label, lambda m=m, f=f: raises(lambda: m.authorize(f["dl"], f["au"], f["bu"]), "revoked or revocation status unknown") and m.state == "CONTEXT_READY")
    # revocation source asked about the right objects
    asked = []
    def spy(kind, h):
        asked.append((kind, h))
        return False
    m, f = mission(spy)
    to_prewrite(m, f)
    t(g, "the_source_is_asked_about_principal_delegation_and_authority", lambda: {k for k, _ in asked} == {"principal", "delegation", "authority"} and {h for _, h in asked} == {f["pr"]["object_hash"], f["dl"]["object_hash"], f["au"]["object_hash"]})
    # compensation
    rl = RevocationList()
    mm, ff, gg = H.comp_mission(1)
    mm._revoked = rl
    rl.revoke(mm.ev["authority"]["object_hash"])
    t(g, "a_revoked_authority_blocks_a_compensating_send", lambda: raises(lambda: mm.begin_compensation(), "revoked") and len(mm.ledger.for_authority(gg["object_hash"])) == 0)
    rl.revoked.clear()
    t(g, "compensation_proceeds_when_not_revoked", lambda: mm.begin_compensation() == 1)
    # resume carries the source
    t(g, "resume_accepts_a_revocation_source", lambda: "revocation_check" in M.Mission._resume.__code__.co_varnames)


def main(argv):
    run()
    failed = sorted(n for n, ok in T.items() if not ok)
    groups = {gk: "PASS" if all(T[n] for n in names) else "FAIL" for gk, names in G.items()}
    digest = hashlib.sha256(json.dumps(sorted(T), separators=(",", ":")).encode()).hexdigest().upper()
    result = {"stage": "MCR3_PHASE1_AUTHORITY", "evidence_class": "SYNTHETIC/LOCAL", "tests": len(T), "failed": failed, "groups": groups, "tests_digest": digest, "network_calls": 0}
    out = json.dumps(result, indent=2, sort_keys=True)
    if "--out" in argv:
        with open(argv[argv.index("--out") + 1], "w", newline="\n") as fh:
            fh.write(out + "\n")
    print(out)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
