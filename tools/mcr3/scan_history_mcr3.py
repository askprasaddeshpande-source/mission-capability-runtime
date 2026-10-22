"""Scan all of Git history for credential-shaped content. Usage: python tools/mcr3/scan_history_mcr3.py [--root DIR]
Exit 0 only if every finding is in history_scan_reviewed.json (reviewed false positives). Heuristic; never proof of absence."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mcr3_scan as S  # noqa: E402


def main(argv):
    root = argv[argv.index("--root") + 1] if "--root" in argv else os.path.abspath(os.path.join(HERE, "..", ".."))
    reviewed = json.load(open(os.path.join(HERE, "history_scan_reviewed.json"), encoding="utf-8"))["reviewed_false_positives"]
    ok = {(r["path"], r["shape"], r["fingerprint"]) for r in reviewed}
    found = S.scan_history(root)
    new = [f for f in found if (f[1], f[2], f[3]) not in ok]
    print(json.dumps({"history_findings": len(found), "reviewed_false_positives": len(found) - len(new),
                      "unreviewed": [{"oid": o, "path": p, "shape": n, "fingerprint": fp} for o, p, n, fp in new],
                      "HISTORY_SCAN": "PASS" if not new else "FAIL"}, indent=2, sort_keys=True))
    return 0 if not new else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
