"""Mutation check for the R2.0 model: remove one guard at a time in a temp copy and require the validator to fail.

Local/synthetic. Usage: python tools/r2.0/run_r2_mutation_check.py [--out PATH]
Exit 0 only if every mutant is detected (validator exit != 0 or reports failed tests) and every mutation applied.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
MUTANTS = [
    ("readback_source_level_ignored", 'return rb["source_level"] == "AUTHORITATIVE_REPOSITORY"', "return True"),
    ("replay_guard_disabled", "if key in self.consumed:", "if False:"),
    ("compensation_inheritance_allowed", 'if grant["inherits_forward_authority"]:', "if False:"),
    ("outcome_recomputation_skipped", 'if outcome["result"] != recomputed:', "if False:"),
    ("completion_not_persisted", '        self.ev["completion"] = completion', "        pass"),
    ("completion_hash_unchecked", "if not verify_hash(completion):", "if False:"),
    ("missing_upstream_links_allowed", '        if missing:\n            raise GuardError("incomplete evidence chain',
     '        if False:\n            raise GuardError("incomplete evidence chain'),
    ("upstream_tamper_unchecked", "if not verify_hash(self.ev[slot]):", "if False:"),
    ("completion_link_dropped_from_chain", '               ("completion", "COMPLETION_RECEIPT")]', "               ]"),
    ("completion_correlation_unchecked", "        self._corr(completion)\n", "        pass\n"),
    ("completion_link_hash_unchecked", 'if completion.get(field) != self.ev[slot]["object_hash"]:', "if False:"),
    ("budget_not_consumed_before_send", "        self.remaining -= 1\n", "        pass\n"),
    ("point_of_use_drift_unchecked", 'if contract_fingerprint_now != self._need("provider")["contract_fingerprint"]:', "if False:"),
    ("compensation_post_readback_not_authoritative", 'if post_readback["source_level"] != "AUTHORITATIVE_REPOSITORY":', "if False:"),
    ("continuation_budget_inflation_allowed", 'if lease["remaining_budget"] > checkpoint["remaining_budget"]:', "if False:"),
]


def main(argv):
    src = open(os.path.join(HERE, "mcr_r2_model.py"), encoding="utf-8").read()
    results = []
    for name, old, new in MUTANTS:
        applied = src.count(old) == 1
        detected = None
        if applied:
            tmp = tempfile.mkdtemp(prefix="r2mut_")
            try:
                open(os.path.join(tmp, "mcr_r2_model.py"), "w", encoding="utf-8", newline="\n").write(src.replace(old, new))
                shutil.copy(os.path.join(HERE, "validate_r2_outcome_model.py"), tmp)
                r = subprocess.run([sys.executable, "validate_r2_outcome_model.py"], cwd=tmp, capture_output=True, text=True)
                detected = r.returncode != 0
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
        results.append({"mutant": name, "applied": applied, "detected": detected})
    ok = all(r["applied"] and r["detected"] for r in results)
    out = {"evidence_class": "SYNTHETIC/LOCAL", "mutants": len(results), "all_applied": all(r["applied"] for r in results),
           "all_detected": all(r["detected"] for r in results if r["applied"]), "results": results,
           "MUTATION_CHECK": "PASS" if ok else "FAIL"}
    s = json.dumps(out, indent=2, sort_keys=True)
    if "--out" in argv:
        open(argv[argv.index("--out") + 1], "w", newline="\n").write(s + "\n")
    print(s)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
