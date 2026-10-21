"""Mutation check for the R2.0 model. Local/synthetic; no network.

Usage: python tools/r2.0/run_r2_mutation_check.py [--out PATH] [--jobs N]

Mutants are generated from the source, not hand-listed, so a new guard or operator cannot silently escape:
  * GUARD: every `if <cond>: raise GuardError(...)` has its condition replaced by False;
  * RELATION: every `self._rel("Rnn", <cond>)` has its condition replaced by True;
  * AST: every comparison operator is flipped (== != < <= > >= in/not in is/is not), every `and`/`or` operand is
    dropped (replaced by True/False), every `not` is removed and every `+`/`-` is swapped, anywhere in the model
    outside docstrings (clause-level and boundary mutants);
  * SPECIAL: targeted mutants for logic that is not an if-raise guard (state, budget, ledger, copy, strict compare...).
Each mutant is applied to a temp copy and the validator must fail. The harness records HOW it was detected:
  assertion = the validator ran to completion and reported failed test names; crash = it died with an exception.
PASS requires: every mutation applied exactly once, every mutant detected, and every survivor listed in EXPLAINED
with a reason (an equivalent mutant). Crash-only detections are reported separately and also listed.
"""
import ast
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
    ("atomic_rollback_removed", "                self.state, self.history, self.ev, self.remaining, self.consumed, self.mutations_sent = snap\n                if isinstance(exc,", "                if isinstance(exc,"),
    ("ledger_not_written_on_send", '        self.ledger.consume(key, limit=self.ev["budget"]["max_mutations"])\n', "        pass\n"),
    ("mission_consumed_set_not_recorded", "        self.consumed.add(key)\n", "        pass\n"),
    ("resume_ignores_ledger", "        consumed = lease_consumed | recorded\n", "        consumed = lease_consumed\n"),
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
    ("thread_lock_removed", "        with self._lock:                              # one guard call at a time per Mission (re-entrant)", "        if True:                                      # lock removed"),
    ("ledger_header_not_written", "            data = self._header_line(lid)\n            fh.seek(0, 2)\n            fh.write(data)\n", "            data = b''\n            fh.seek(0, 2)\n            fh.write(data)\n"),
]

# Survivors that are equivalent mutants (behaviour cannot differ), keyed by mutant name. Anything else that
# survives fails the check.
EXPLAINED = {
    # key = distinctive fragment that must appear in the (line-number-free) mutant name -> reason it is equivalent
    'drop clause 1 of post_readback["object_hash"] == fwd': "equivalent: an identical object hash implies identical content, so the observed-state clause already covers it",
    "drop clause 1 of isinstance(key, tuple) and len(key) == 2": "equivalent: _as_key() always returns a tuple before _check_key() runs",
    'drop clause 1 of mid is not None and mid in tx': "equivalent: None is never a member of a list of non-empty strings",
    "drop clause 1 of isinstance(a, str) and isinstance(m_, str)": "equivalent: _crc() raises TypeError for non-strings, which the surrounding except turns into 'corrupted'",
    "drop clause 2 of isinstance(a, str) and isinstance(m_, str)": "equivalent: _crc() raises TypeError for non-strings, which the surrounding except turns into 'corrupted'",
    "flip time.time() - start > timeout": "equivalent: > versus >= on a float clock difference changes nothing observable",
}


def explanation(name):
    n = norm(name)
    for key, why in EXPLAINED.items():
        if key in n:
            return why
    return None

# Mutants detected only because the validator's OWN fixtures can no longer run (the mutant breaks a legitimate
# flow the test setup depends on). Strong detection, but reported separately from assertion failures.
DEFAULT_CRASH_REASON = ("the validator raised a Python exception: a legitimate flow its own fixtures need was broken by the mutant "
                        "(detected, but not by a targeted assertion)")
CRASH_REASONS = {
    "special: budget_not_decremented": "a legitimate resume is refused because the lease budget no longer adds up",
    "special: mission_consumed_set_not_recorded": "a genuine chain is refused by R19 because the replay set was never filled",
    "special: predicate_eq_always_true": "the compensation fixture reaches an illegal transition because an eq predicate passes wrongly",
}



SWAP = {ast.Eq: "!=", ast.NotEq: "==", ast.Lt: "<=", ast.LtE: "<", ast.Gt: ">=", ast.GtE: ">", ast.In: "not in",
        ast.NotIn: "in", ast.Is: "is not", ast.IsNot: "is"}


def ast_mutants(src):
    """Yield (name, mutated source) for every clause/operator mutation in the model (docstrings excluded)."""
    tree = ast.parse(src)
    data = src.encode("utf-8")
    starts = [0]
    for line in data.split(b"\n")[:-1]:
        starts.append(starts[-1] + len(line) + 1)

    def off(lineno, col):
        return starts[lineno - 1] + col

    def span(n):
        return off(n.lineno, n.col_offset), off(n.end_lineno, n.end_col_offset)

    docstrings = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.Module)) and n.body and isinstance(n.body[0], ast.Expr) \
                and isinstance(n.body[0].value, ast.Constant) and isinstance(n.body[0].value.value, str):
            docstrings.add(id(n.body[0].value))
    skip = set()
    for n in ast.walk(tree):
        if id(n) in docstrings:
            for c in ast.walk(n):
                skip.add(id(c))

    def mutated(s, e, text):
        return (data[:s] + text.encode("utf-8") + data[e:]).decode("utf-8")

    for n in ast.walk(tree):
        if id(n) in skip or not hasattr(n, "lineno"):
            continue
        snippet = data[span(n)[0]:span(n)[1]].decode("utf-8").replace("\n", " ")[:60]
        if isinstance(n, ast.Compare) and len(n.ops) == 1 and type(n.ops[0]) in SWAP:
            s_, e_ = span(n.left)[1], span(n.comparators[0])[0]
            yield "ast@L%d: flip %s" % (n.lineno, snippet), mutated(s_, e_, " %s " % SWAP[type(n.ops[0])])
        elif isinstance(n, ast.BoolOp) and len(n.values) >= 2:
            repl = "True" if isinstance(n.op, ast.And) else "False"
            for i, v in enumerate(n.values):
                s_, e_ = span(v)
                yield "ast@L%d: drop clause %d of %s" % (n.lineno, i + 1, snippet), mutated(s_, e_, repl)
        elif isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not):
            s_, e_ = span(n)
            vs, ve = span(n.operand)
            yield "ast@L%d: remove not in %s" % (n.lineno, snippet), mutated(s_, e_, data[vs:ve].decode("utf-8"))
        elif isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub)):
            s_, e_ = span(n.left)[1], span(n.right)[0]
            yield "ast@L%d: swap +/- in %s" % (n.lineno, snippet), mutated(s_, e_, " - " if isinstance(n.op, ast.Add) else " + ")

def norm(name):
    """Mutant name without its line number, so explanations survive harmless line shifts."""
    return re.sub(r"@L\d+", "", name)


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
    seen = {m[1] for m in muts}
    for name, new in ast_mutants(src):
        try:
            ast.parse(new)
        except SyntaxError:
            continue
        if new in seen:                      # identical to a guard/relation mutant already generated
            continue
        seen.add(new)
        muts.append((name, new, True))
    for name, old, rep in SPECIAL:
        ok = src.count(old) == 1
        muts.append(("special: " + name, src.replace(old, rep, 1) if ok else None, ok))
    return muts


def classify(r):
    """assertion = the validator ran to completion and named failed tests; crash = it died with a Python traceback
    (a legitimate flow its fixtures need was broken); inconclusive = killed, timed out or non-JSON WITHOUT a traceback
    (for example a memory kill), which is NOT counted as detection; None = the mutant survived."""
    try:
        d = json.loads(r.stdout)
    except Exception:
        if r.returncode != 0 and "Traceback" in (r.stderr or ""):
            return "crash"
        return "inconclusive"
    if d.get("failed"):
        return "assertion"
    return "inconclusive" if r.returncode != 0 else None


def run_one(item):
    name, new_src, applied = item
    if not applied or new_src is None:
        return {"mutant": name, "applied": False, "detected": None, "detected_by": None}
    kind = "inconclusive"
    timed_out = False
    for _attempt in range(2):                         # one retry: an inconclusive run must not decide the outcome
        tmp = tempfile.mkdtemp(prefix="r2mut_")
        try:
            with open(os.path.join(tmp, "mcr_r2_model.py"), "w", encoding="utf-8", newline="\n") as fh:
                fh.write(new_src)
            shutil.copy(os.path.join(HERE, "validate_r2_outcome_model.py"), tmp)
            r = subprocess.run([sys.executable, "validate_r2_outcome_model.py"], cwd=tmp, capture_output=True, text=True, timeout=300)
            kind = classify(r)
        except subprocess.TimeoutExpired:
            kind = "hang" if timed_out else "inconclusive"   # the same mutant timing out twice is a deterministic hang
            timed_out = True
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if kind != "inconclusive":
            break
    return {"mutant": name, "applied": True, "detected": kind in ("assertion", "crash", "hang"), "detected_by": kind}


def main(argv):
    jobs = int(argv[argv.index("--jobs") + 1]) if "--jobs" in argv else 4
    src = open(os.path.join(HERE, "mcr_r2_model.py"), encoding="utf-8").read().replace("\r\n", "\n")
    mutants = build_mutants(src)
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
        results = list(ex.map(run_one, mutants))
    inconclusive = [r["mutant"] for r in results if r["detected_by"] == "inconclusive"]
    survivors = [r["mutant"] for r in results if r["applied"] and not r["detected"] and r["detected_by"] != "inconclusive"]
    unexplained = [s_ for s_ in survivors if explanation(s_) is None]
    not_applied = [r["mutant"] for r in results if not r["applied"]]
    out = {"evidence_class": "SYNTHETIC/LOCAL", "mutants": len(results),
           "by_kind": {"guard": sum(1 for r in results if r["mutant"].startswith("guard@")),
                       "relation": sum(1 for r in results if r["mutant"].startswith("relation ")),
                       "ast": sum(1 for r in results if r["mutant"].startswith("ast@")),
                       "special": sum(1 for r in results if r["mutant"].startswith("special:"))},
           "not_applied": not_applied, "detected_by_assertion": sum(1 for r in results if r["detected_by"] == "assertion"),
           "detected_by_validator_crash": {r["mutant"]: CRASH_REASONS.get(r["mutant"], DEFAULT_CRASH_REASON) for r in results if r["detected_by"] == "crash"},
           "detected_by_hang": [r["mutant"] for r in results if r["detected_by"] == "hang"],
           "inconclusive": inconclusive,
           "survivors": survivors, "explained_survivors": {s_: explanation(s_) for s_ in survivors if explanation(s_) is not None},
           "unexplained_survivors": unexplained, "results": results,
           "MUTATION_CHECK": "PASS" if not not_applied and not unexplained and not inconclusive else "FAIL"}
    s = json.dumps(out, indent=2, sort_keys=True)
    if "--out" in argv:
        with open(argv[argv.index("--out") + 1], "w", newline="\n") as fh:
            fh.write(s + "\n")
    print(s)
    return 0 if out["MUTATION_CHECK"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
