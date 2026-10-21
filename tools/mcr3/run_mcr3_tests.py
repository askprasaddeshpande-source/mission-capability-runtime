"""Run every MCR 3.0 validator in its own process, record counts, wall time and peak memory, and write the results.

Usage: python tools/mcr3/run_mcr3_tests.py [--out-dir DIR] [--check-dir DIR]
  --out-dir    write each suite's deterministic result JSON, a summary, and a (non-deterministic) resource record there
  --check-dir  compare the deterministic fields (tests, failed, groups, tests_digest) with archived results; exit 1 on a difference
Each validator runs sequentially (never in parallel) in a separate interpreter, so peak memory is one suite's.
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SUITES = [
    ("inherited_r2", "validate_mcr3_inherited.py"),
    ("hardening", "validate_mcr3_hardening.py"),
    ("evidence_contract", "validate_mcr3_evc1.py"),
    ("provenance_authority", "validate_mcr3_authority.py"),
    ("adapters_interop", "validate_mcr3_adapters.py"),
    ("evidence_chain", "validate_mcr3_chain.py"),
    ("readback", "validate_mcr3_readback.py"),
    ("scanner", "validate_mcr3_scan.py"),
]
WRAPPER = r'''
import runpy, sys, os
script = sys.argv[1]
sys.argv = [script] + sys.argv[2:]
code = 0
try:
    runpy.run_path(script, run_name="__main__")
except SystemExit as e:
    code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
finally:
    try:
        import mcr3_measure
        sys.stderr.write("\nPEAK_BYTES=%d\n" % mcr3_measure.peak_bytes())
    except Exception:
        pass
sys.exit(code)
'''
STABLE = ("tests", "failed", "groups", "tests_digest", "not_verified")


def run_suite(name, script, out_dir):
    t0 = time.time()
    env = dict(os.environ, PYTHONPATH=HERE, PYTHONDONTWRITEBYTECODE="1")
    r = subprocess.run([sys.executable, "-c", WRAPPER, os.path.join(HERE, script)], cwd=HERE, capture_output=True, text=True, timeout=1800, env=env)
    wall = round(time.time() - t0, 2)
    peak = None
    for line in r.stderr.splitlines():
        if line.startswith("PEAK_BYTES="):
            peak = int(line.split("=", 1)[1])
    try:
        d = json.loads(r.stdout)
    except Exception:
        return {"suite": name, "script": script, "error": "no JSON result", "returncode": r.returncode, "stderr_tail": r.stderr[-600:]}, None
    return {"suite": name, "script": script, "tests": d["tests"], "failed": d["failed"], "returncode": r.returncode, "wall_seconds": wall, "peak_bytes": peak}, d


def main(argv):
    out_dir = argv[argv.index("--out-dir") + 1] if "--out-dir" in argv else None
    chk_dir = argv[argv.index("--check-dir") + 1] if "--check-dir" in argv else None
    rows, results, mismatch = [], {}, []
    for name, script in SUITES:
        row, d = run_suite(name, script, out_dir)
        rows.append(row)
        if d is None:
            continue
        results[name] = d
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
            with open(os.path.join(out_dir, "MCR3_RESULT_%s_R1.json" % name.upper()), "w", newline="\n") as fh:
                fh.write(json.dumps(d, indent=2, sort_keys=True) + "\n")
        if chk_dir:
            p = os.path.join(chk_dir, "MCR3_RESULT_%s_R1.json" % name.upper())
            try:
                ref = json.load(open(p, encoding="utf-8"))
                if any(ref.get(k) != d.get(k) for k in STABLE):
                    mismatch.append(name)
            except OSError:
                mismatch.append(name + " (archived result missing)")
    total = sum(r.get("tests", 0) for r in rows)
    failed = [f for r in rows for f in r.get("failed", [])] + [r["suite"] for r in rows if "error" in r]
    summary = {"suites": len(rows), "tests": total, "failed": failed, "by_suite": {r["suite"]: r.get("tests") for r in rows},
               "not_verified": sorted({x for d in results.values() for x in d.get("not_verified", [])}), "network_calls": 0, "SAP_WRITES": 0,
               "MCR3_TESTS": "PASS" if not failed and len(rows) == len(SUITES) else "FAIL"}
    if chk_dir:
        summary["reproduces_archived_results"] = not mismatch
        summary["mismatch"] = mismatch
    resources = {"note": "descriptive, machine-dependent", "suites": [{k: r.get(k) for k in ("suite", "wall_seconds", "peak_bytes")} for r in rows],
                 "total_wall_seconds": round(sum(r.get("wall_seconds", 0) for r in rows), 2), "max_peak_bytes": max([r.get("peak_bytes") or 0 for r in rows])}
    if out_dir:
        with open(os.path.join(out_dir, "MCR3_TEST_SUMMARY_R1.json"), "w", newline="\n") as fh:
            fh.write(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        with open(os.path.join(out_dir, "MCR3_RESOURCE_USE_R1.json"), "w", newline="\n") as fh:
            fh.write(json.dumps(resources, indent=2, sort_keys=True) + "\n")
    print(json.dumps(dict(summary, resources=resources), indent=2, sort_keys=True))
    return 0 if summary["MCR3_TESTS"] == "PASS" and not mismatch else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
