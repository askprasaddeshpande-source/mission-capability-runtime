"""Release-gate decision for MCR 3.0 from the artifacts of the heavy tier. Offline; reads files only.

Usage: python tools/mcr3/check_release_gate.py --dir DIR --sha SHA [--out FILE]
DIR holds mutation-<module>.json (one per mutation target) and attacks.json. The gate passes only if, for EXACTLY the
candidate commit SHA: every mutation target has a result file, each says PASS with no inconclusive, no unexplained survivor
and no mutant that failed to apply; the verifier attack suite attacked that SHA and every scenario passed. A missing file
is a failure (a skipped job is not a pass). The external checksum anchor is checked by the workflow, not here."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def targets():
    import run_mcr3_mutation_check as R
    return [t for t, _ in R.TARGETS]


def load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def decide(directory, sha, required=None):
    required = required if required is not None else targets()
    problems, modules = [], {}
    for mod in required:
        d = load(os.path.join(directory, "mutation-%s.json" % mod))
        if d is None:
            problems.append("%s: no result file (job skipped, failed or not run)" % mod)
            continue
        bm = (d.get("by_module") or {}).get(mod)
        if d.get("MUTATION_CHECK") != "PASS" or not bm or not d.get("mutants"):
            problems.append("%s: mutation check is not PASS" % mod)
        if d.get("inconclusive") or d.get("unexplained_survivors") or d.get("not_applied") or d.get("detected_by_hang"):
            problems.append("%s: inconclusive, unexplained, hanging or unapplied mutants" % mod)
        modules[mod] = {"mutants": d.get("mutants"), "assertion": (bm or {}).get("assertion"), "validator_crash": (bm or {}).get("crash"),
                        "hang": (bm or {}).get("hang"), "survivors": (bm or {}).get("survivors"), "explained_survivors": len(d.get("explained_survivors") or {}),
                        "unexplained_survivors": len(d.get("unexplained_survivors") or []), "inconclusive": len(d.get("inconclusive") or [])}
    a = load(os.path.join(directory, "attacks.json"))
    if a is None:
        problems.append("attacks: no result file")
        attacks = None
    else:
        attacks = {"scenarios": a.get("scenarios"), "all_passed": a.get("all_passed"), "head_attacked": a.get("head_attacked")}
        if a.get("all_passed") is not True or not a.get("scenarios"):
            problems.append("attacks: not all scenarios passed")
        if a.get("head_attacked") != sha:
            problems.append("attacks: attacked %r, not the candidate %r" % (a.get("head_attacked"), sha))
        names = " ".join((a.get("results") or {}).keys())
        for need in ("A13a", "A13b", "A13c", "A13d", "A13e", "A13f", "N1_", "N2_", "N3_"):
            if need not in names:
                problems.append("attacks: scenario %s missing" % need)
    return {"candidate_sha": sha, "mutation": modules, "attacks": attacks, "problems": problems,
            "RELEASE_GATE_HEAVY": "PASS" if not problems else "FAIL"}


def main(argv):
    if "--dir" not in argv or "--sha" not in argv:
        print("usage: check_release_gate.py --dir DIR --sha SHA [--out FILE]")
        return 2
    res = decide(argv[argv.index("--dir") + 1], argv[argv.index("--sha") + 1])
    s = json.dumps(res, indent=2, sort_keys=True)
    if "--out" in argv:
        with open(argv[argv.index("--out") + 1], "w", newline="\n") as fh:
            fh.write(s + "\n")
    print(s)
    return 0 if res["RELEASE_GATE_HEAVY"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
