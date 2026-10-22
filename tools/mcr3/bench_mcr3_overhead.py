"""Governance overhead, descriptively: time for a complete mission through the frozen R2.0 model and through the 3.0 model,
and for the 3.0 evidence conversion and verification steps. No threshold is asserted: the numbers describe THIS machine on THIS run.
Usage: python tools/mcr3/bench_mcr3_overhead.py [--n N] [--out PATH]
"""
import importlib
import json
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "r2.0"))
import evc1  # noqa: E402
import mcr3_adapters as AD  # noqa: E402
import mcr3_model as M3  # noqa: E402
import mcr3_provenance as P  # noqa: E402
import validate_mcr3_adapters as VA  # noqa: E402
from validate_mcr3_inherited import fixture, happy  # noqa: E402


def timeit(fn, n):
    xs = []
    for _ in range(n):
        t = time.perf_counter()
        fn()
        xs.append((time.perf_counter() - t) * 1000.0)
    xs.sort()
    return {"n": n, "mean_ms": round(statistics.fmean(xs), 3), "median_ms": round(xs[len(xs) // 2], 3), "p95_ms": round(xs[int(len(xs) * 0.95) - 1], 3), "max_ms": round(xs[-1], 3)}


def main(argv):
    n = int(argv[argv.index("--n") + 1]) if "--n" in argv else 200

    def m3_run():
        m, f = fixture()
        happy(m, f)
    mc, fc = VA.complete_mission()
    nb = AD.Mcr3NativeAdapter()
    evs = nb.convert(mc, now="2027-01-15T00:00:00Z")
    hm = P.HmacTestVerifier({"alice": b"k"})
    pol = P.TrustPolicy(issuers={"alice": {"status": "TRUSTED"}}, clock=lambda: 1_799_971_230.0)
    att = P.make_attestation(evs[2], "alice", hm, signed_at="2027-01-15T00:00:00Z")
    out = {"note": "descriptive; machine-dependent; one process; no inference about production", "python": sys.version.split()[0],
           "platform": sys.platform,
           "mission_end_to_end_3_0_model_incl_fixture_build": timeit(m3_run, n),
           "adapter_convert_complete_mission_7_events": timeit(lambda: nb.convert(mc, now="2027-01-15T00:00:00Z"), n),
           "contract_parse_one_event": timeit(lambda: evc1.parse(evs[2]), n),
           "provenance_assess_one_event": timeit(lambda: P.assess(evs[2], att, hm, pol, P.ReplayCache()), n),
           "seal_one_event": timeit(lambda: evc1.seal({k: v for k, v in evs[2].items() if k != "integrity"}), n)}
    sys.path.insert(0, os.path.join(ROOT, "tools", "r2.0"))
    try:
        r2 = importlib.import_module("validate_r2_outcome_model")
        out["mission_end_to_end_r2_0_model_incl_fixture_build"] = timeit(lambda: (lambda mf: r2.happy(*mf))((lambda: r2.fixture())()), n)
    except Exception as exc:
        out["mission_end_to_end_r2_0_model_incl_fixture_build"] = "NOT_MEASURED (%s)" % type(exc).__name__
    s = json.dumps(out, indent=2, sort_keys=True)
    if "--out" in argv:
        with open(argv[argv.index("--out") + 1], "w", newline="\n") as fh:
            fh.write(s + "\n")
    print(s)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
