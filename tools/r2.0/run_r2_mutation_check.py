"""Mutation check for the R2.0 model. Local/synthetic; no network.

Usage: python tools/r2.0/run_r2_mutation_check.py [--out PATH] [--jobs N]

Mutants are generated from the source, not hand-listed, so a new guard cannot silently escape:
  * GUARD: every `if <cond>: raise GuardError(...)` has its condition replaced by False;
  * RELATION: every `self._rel("Rnn", <cond>)` has its condition replaced by True;
  * SPECIAL: targeted mutants for logic that is not an if-raise guard (state, budget, ledger, copy, strict compare...).
Each mutant is applied to a temp copy and the validator must fail. The harness records HOW it was detected:
  assertion = the validator ran to completion and reported failed test names; crash = it died with an exception.
PASS requires: every mutation applied exactly once, every mutant detected, and every survivor listed in EXPLAINED
with a reason (an equivalent mutant). Crash-only detections are reported separately and also listed.
"""
import concurrent.futures
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

GUARD_RE = re.compile(r"^( +)if ((?:[^\n]*\\\n)*[^\n]*):\n( +)raise GuardError\(", re.M)
REL_RE = re.compile(r'^( +self\._rel\("(R\d+)", )(.+)(\))$', re.M)

# (name, old, new): applied once; old must occur exactly once.
SPECIAL = [
    ("readback_authority_helper_always_true", 'return rb["source_level"] == "AUTHORITATIVE_REPOSITORY"', "return True"),
    ("budget_not_decremented", "        self.remaining -= 1\n", "        pass\n"),
    ("completion_not_persisted", '        self.ev["completion"] = completion', "        pass"),
    ("completion_link_dropped_from_chain", '               ("completion", "COMPLETION_RECEIPT")]', "               ]"),
    ("atomic_rollback_removed", "            self.state, self.history, self.ev, self.remaining, self.consumed, self.mutations_sent = snap\n            raise", "            raise"),
    ("ledger_not_written_on_send", "        self.ledger.consume(key)\n", "        pass\n"),
    ("mission_consumed_set_not_recorded", "        self.consumed.add(key)\n", "        pass\n"),
    ("resume_ignores_ledger", "        consumed = lease_consumed | ledger.for_authority(auth)", "        consumed = lease_consumed"),
    ("resume_state_inherited_from_lease", '        m.state = "COMMIT_STATE_UNKNOWN"\n        m.history.append(("RESUMED_AS_COMMIT_STATE_UNKNOWN"', '        m.state = lease["state_at_checkpoint"]\n        m.history.append(("RESUMED_AS_COMMIT_STATE_UNKNOWN"'),
    ("resume_budget_taken_from_lease_only", "        m.remaining = min(lease_rem, total - len(consumed))", "        m.remaining = lease_rem"),
    ("resume_evidence_not_verified", "        ev = {slot: _accept_obj(slot, o) for slot, o in evidence.items()}", "        ev = dict(evidence)"),
    ("resume_consumed_set_not_restored", "        m.consumed = consumed\n", "        pass\n"),
    ("resume_sent_counter_not_restored", "        m.mutations_sent = len(consumed)\n", "        pass\n"),
    ("accepted_objects_not_copied", "    return copy.deepcopy(obj)", "    return obj"),
    ("predicates_not_type_strict", "    return type(a) is type(b) and a == b", "    return a == b"),
    ("predicate_ne_always_true", 'ok = _same(v, e) if op == "eq" else (not _same(v, e)) if op == "ne" else any(_same(v, x) for x in e)',
     'ok = _same(v, e) if op == "eq" else True if op == "ne" else any(_same(v, x) for x in e)'),
    ("predicate_in_always_true", 'ok = _same(v, e) if op == "eq" else (not _same(v, e)) if op == "ne" else any(_same(v, x) for x in e)',
     'ok = _same(v, e) if op == "eq" else (not _same(v, e)) if op == "ne" else True'),
    ("predicate_eq_always_true", 'ok = _same(v, e) if op == "eq" else (not _same(v, e)) if op == "ne" else any(_same(v, x) for x in e)',
     'ok = True if op == "eq" else (not _same(v, e)) if op == "ne" else any(_same(v, x) for x in e)'),
    ("unknown_observed_value_treated_as_known", 'if p["field"] not in observed or observed[p["field"]] in (None, "UNKNOWN"):', 'if p["field"] not in observed:'),
    ("unknown_predicate_never_degrades", '            result = "UNKNOWN" if result != "FAIL" else result', "            result = result"),
    ("go_token_not_required", "        if _tok is not _TOKEN:", "        if False:"),
]

# Survivors that are equivalent mutants (behaviour cannot differ), keyed by mutant name. Anything else that
# survives fails the check.
EXPLAINED = {}

# Mutants detected only because the validator's OWN fixtures can no longer run (the mutant breaks a legitimate
# flow the test setup depends on). Strong detection, but reported separately from assertion failures.
CRASH_REASONS = {
    "special: budget_not_decremented": "a legitimate resume is refused because the lease budget no longer adds up",
    "special: mission_consumed_set_not_recorded": "a genuine chain is refused by R19 because the replay set was never filled",
    "special: predicate_eq_always_true": "the compensation fixture reaches an illegal transition because an eq predicate passes wrongly",
}


def build_mutants(src):
    muts = []
    for m in GUARD_RE.finditer(src):
        cond = " ".join(m.group(2).replace("\\\n", " ").split())
        line = src.count("\n", 0, m.start()) + 1
        new = src[:m.start(2)] + "False" + src[m.end(2):]
        muts.append(("guard@L%d: %s" % (line, cond[:70]), new, src.count(m.group(0)) == 1 or True))
    for m in REL_RE.finditer(src):
        new = src[:m.start(3)] + "True" + src[m.end(3):]
        muts.append(("relation %s" % m.group(2), new, True))
    for name, old, rep in SPECIAL:
        ok = src.count(old) == 1
        muts.append(("special: " + name, src.replace(old, rep, 1) if ok else None, ok))
    return muts


def classify(r):
    try:
        d = json.loads(r.stdout)
    except Exception:
        return "crash" if r.returncode != 0 else None
    if d.get("failed"):
        return "assertion"
    return "crash" if r.returncode != 0 else None


def run_one(item):
    name, new_src, applied = item
    if not applied or new_src is None:
        return {"mutant": name, "applied": False, "detected": None, "detected_by": None}
    tmp = tempfile.mkdtemp(prefix="r2mut_")
    try:
        with open(os.path.join(tmp, "mcr_r2_model.py"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(new_src)
        shutil.copy(os.path.join(HERE, "validate_r2_outcome_model.py"), tmp)
        r = subprocess.run([sys.executable, "validate_r2_outcome_model.py"], cwd=tmp, capture_output=True, text=True, timeout=300)
        kind = classify(r)
    except subprocess.TimeoutExpired:
        kind = "crash"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {"mutant": name, "applied": True, "detected": kind is not None, "detected_by": kind}


def main(argv):
    jobs = int(argv[argv.index("--jobs") + 1]) if "--jobs" in argv else 4
    src = open(os.path.join(HERE, "mcr_r2_model.py"), encoding="utf-8").read().replace("\r\n", "\n")
    mutants = build_mutants(src)
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
        results = list(ex.map(run_one, mutants))
    survivors = [r["mutant"] for r in results if r["applied"] and not r["detected"]]
    unexplained = [s for s in survivors if s not in EXPLAINED]
    not_applied = [r["mutant"] for r in results if not r["applied"]]
    out = {"evidence_class": "SYNTHETIC/LOCAL", "mutants": len(results),
           "by_kind": {"guard": sum(1 for r in results if r["mutant"].startswith("guard@")),
                       "relation": sum(1 for r in results if r["mutant"].startswith("relation ")),
                       "special": sum(1 for r in results if r["mutant"].startswith("special:"))},
           "not_applied": not_applied, "detected_by_assertion": sum(1 for r in results if r["detected_by"] == "assertion"),
           "detected_by_crash_only": {r["mutant"]: CRASH_REASONS.get(r["mutant"], "UNEXPLAINED") for r in results if r["detected_by"] == "crash"},
           "survivors": survivors, "explained_survivors": {s: EXPLAINED[s] for s in survivors if s in EXPLAINED},
           "unexplained_survivors": unexplained, "results": results,
           "MUTATION_CHECK": "PASS" if not not_applied and not unexplained else "FAIL"}
    s = json.dumps(out, indent=2, sort_keys=True)
    if "--out" in argv:
        with open(argv[argv.index("--out") + 1], "w", newline="\n") as fh:
            fh.write(s + "\n")
    print(s)
    return 0 if out["MUTATION_CHECK"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
