"""Mutation check for the R2.0 model: remove one guard at a time in a temp copy and require the validator to fail.

Local/synthetic. Usage: python tools/r2.0/run_r2_mutation_check.py [--out PATH]
For every mutant the harness records HOW it was detected:
  assertion = the validator ran to completion and reported failed test names;
  crash     = the validator died with an exception (still detected, but weaker evidence).
Exit 0 only if every mutation applied (exactly one match) and every mutant was detected.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
MUTANTS = [
    # --- R2.0A-G mutants
    ("readback_source_level_ignored", 'return rb["source_level"] == "AUTHORITATIVE_REPOSITORY"', "return True"),
    ("replay_guard_disabled", "if key in self.consumed:", "if False:"),
    ("compensation_inheritance_allowed", 'if grant["inherits_forward_authority"]:', "if False:"),
    ("outcome_recomputation_skipped", 'if outcome["result"] != recomputed:', "if False:"),
    ("completion_not_persisted", '        self.ev["completion"] = completion', "        pass"),
    ("completion_hash_unchecked", "if not verify_hash(completion):", "if False:"),
    ("missing_upstream_links_allowed", '        if missing:\n            raise GuardError("incomplete evidence chain', '        if False:\n            raise GuardError("incomplete evidence chain'),
    ("upstream_tamper_unchecked", "            if not verify_hash(o):\n                raise GuardError(\"evidence %s hash invalid", "            if False:\n                raise GuardError(\"evidence %s hash invalid"),
    ("completion_link_dropped_from_chain", '               ("completion", "COMPLETION_RECEIPT")]', "               ]"),
    ("completion_correlation_unchecked", "        self._corr(completion)\n", "        pass\n"),
    ("completion_link_hash_unchecked", 'if completion.get(field) != h(slot):', "if False:"),
    ("budget_not_consumed_before_send", "        self.remaining -= 1\n", "        pass\n"),
    ("point_of_use_drift_unchecked", 'if contract_fingerprint_now != self._need("provider")["contract_fingerprint"]:', "if False:"),
    ("compensation_post_readback_not_authoritative", 'if post_readback["source_level"] != "AUTHORITATIVE_REPOSITORY":', "if False:"),
    ("continuation_budget_inflation_allowed", 'if lease["remaining_budget"] + len(consumed) > checkpoint["remaining_budget"]:', "if False:"),
    # --- R2.0H mutants (independent-review findings)
    ("direct_state_change_allowed", "if _tok is not _TOKEN:", "if False:"),
    ("atomic_rollback_removed", "            self.state, self.history, self.ev, self.remaining, self.consumed, self.mutations_sent = snap\n            raise", "            raise"),
    ("lease_hash_unchecked", 'if not isinstance(o, dict) or o.get("kind") != kind or not verify_hash(o):', "if False:"),
    ("resume_inherits_lease_state", '        m.state = "COMMIT_STATE_UNKNOWN"\n        m.history.append(("RESUMED_AS_COMMIT_STATE_UNKNOWN"', '        m.state = st\n        m.history.append(("RESUMED_AS_COMMIT_STATE_UNKNOWN"'),
    ("resume_accepts_downstream_evidence", "        if extra:", "        if False:"),
    ("resume_lease_state_consistency_unchecked", 'if consumed and st in ("PREWRITE_VALIDATED", "PLANNED") or (not consumed and st not in ("PREWRITE_VALIDATED",)):', "if False:"),
    ("resume_consumed_authority_unchecked", 'if any(k[0] != evidence["authority"]["object_hash"] for k in consumed):', "if False:"),
    ("chain_kind_unchecked", 'if not isinstance(o, dict) or o.get("kind") != SLOT_KINDS[slot]:', "if False:"),
    ("chain_relations_skipped", "        for ok, msg in chk:", "        for ok, msg in []:"),
    ("chain_readback_authority_unchecked", 'e["readback"]["source_level"] == "AUTHORITATIVE_REPOSITORY" and e["readback"]["existence"] == "EXISTS"', "True"),
    ("chain_replay_record_unchecked", '(h("authority"), mid) in self.consumed', "True"),
    ("empty_predicates_allowed", "if not isinstance(predicates, (list, tuple)) or not predicates:", "if not isinstance(predicates, (list, tuple)):"),
    ("unknown_predicate_op_allowed", 'if p["op"] not in PRED_OPS:', "if False:"),
    ("authority_consumed_check_disabled", 'if any((k[0] if isinstance(k, tuple) else k) == authority["object_hash"] for k in self.consumed):', "if False:"),
    ("commit_readback_binding_unchecked", 'if observation["readback_receipt_hash"] != rb["object_hash"]:', "if False:"),
    ("readback_contract_binding_unchecked", 'if rb["contract_hash"] != contract["object_hash"]:', "if False:"),
    ("commit_understatement_allowed", 'if observation["commit_state"] != "COMMITTED":', "if False:"),
    ("execution_receipt_mutation_binding_unchecked", 'if receipt.get("mutation_id") != self.ev.get("mutation_id"):', "if False:"),
    ("outcome_binding_unchecked", 'if outcome["outcome_contract_hash"] != oc["object_hash"] or outcome["readback_receipt_hash"] != rb["object_hash"]:', "if False:"),
    ("prewrite_predicates_unchecked", '        check_predicates(outcome_contract["predicates"])', "        pass"),
]


def classify(r):
    try:
        d = json.loads(r.stdout)
    except Exception:
        return "crash" if r.returncode != 0 else None
    if d.get("failed"):
        return "assertion"
    return "crash" if r.returncode != 0 else None


def main(argv):
    src = open(os.path.join(HERE, "mcr_r2_model.py"), encoding="utf-8").read().replace("\r\n", "\n")
    results = []
    for name, old, new in MUTANTS:
        applied = src.count(old) == 1
        kind = None
        if applied:
            tmp = tempfile.mkdtemp(prefix="r2mut_")
            try:
                open(os.path.join(tmp, "mcr_r2_model.py"), "w", encoding="utf-8", newline="\n").write(src.replace(old, new))
                shutil.copy(os.path.join(HERE, "validate_r2_outcome_model.py"), tmp)
                kind = classify(subprocess.run([sys.executable, "validate_r2_outcome_model.py"], cwd=tmp, capture_output=True, text=True))
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
        results.append({"mutant": name, "applied": applied, "detected": kind is not None if applied else None, "detected_by": kind})
    ok = all(r["applied"] and r["detected"] for r in results)
    out = {"evidence_class": "SYNTHETIC/LOCAL", "mutants": len(results), "all_applied": all(r["applied"] for r in results),
           "all_detected": all(r["detected"] for r in results if r["applied"]),
           "detected_by_assertion": sum(1 for r in results if r["detected_by"] == "assertion"),
           "detected_by_crash_only": [r["mutant"] for r in results if r["detected_by"] == "crash"],
           "results": results, "MUTATION_CHECK": "PASS" if ok else "FAIL"}
    s = json.dumps(out, indent=2, sort_keys=True)
    if "--out" in argv:
        with open(argv[argv.index("--out") + 1], "w", newline="\n") as fh:
            fh.write(s + "\n")
    print(s)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
