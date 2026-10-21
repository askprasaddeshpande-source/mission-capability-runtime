"""Mutation check for the MCR 3.0 modules. Local/synthetic; no network.

Usage: python tools/mcr3/run_mcr3_mutation_check.py [--out PATH] [--jobs N] [--only MODULE.py]

Targets (module -> the validators that must fail when the module is mutated): see TARGETS. Mutants are generated from the
source: for the runtime model, every `if <cond>: raise GuardError(...)` guard, every chain relation and targeted SPECIAL
mutants; for every module, clause/operator mutants (comparison flips, dropped and/or clauses, removed `not`, +/- swaps).
A mutated module shadows the real one through MCR3_OVERRIDE_DIR; the tree-wide secret scan is skipped (MCR3_SKIP_TREE).
The harness records HOW each mutant was detected:
  assertion    a validator ran to completion and named failed tests
  crash        a validator died with a Python traceback (a legitimate flow its fixtures need was broken) - weaker evidence
  hang         the same mutant timed out twice
  inconclusive killed or timed out without a traceback (for example a memory kill), retried once, never counted as detection
PASS requires: every mutation applied, none inconclusive, every survivor listed in EXPLAINED with a reason.
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

TARGETS = [
    ("mcr3_model.py", ["validate_mcr3_inherited.py", "validate_mcr3_hardening.py", "validate_mcr3_gaps.py"]),
    ("evc1.py", ["validate_mcr3_evc1.py", "validate_mcr3_gaps.py"]),
    ("mini_jsonschema.py", ["validate_mcr3_evc1.py", "validate_mcr3_gaps.py"]),
    ("mcr3_provenance.py", ["validate_mcr3_authority.py", "validate_mcr3_gaps.py"]),
    ("mcr3_authority.py", ["validate_mcr3_authority.py", "validate_mcr3_gaps.py"]),
    ("mcr3_scan.py", ["validate_mcr3_scan.py", "validate_mcr3_gaps.py"]),
    ("mcr3_readback.py", ["validate_mcr3_readback.py", "validate_mcr3_gaps.py"]),
    ("mcr3_adapters.py", ["validate_mcr3_adapters.py", "validate_mcr3_gaps.py"]),
    ("mcr3_lineage.py", ["validate_mcr3_adapters.py", "validate_mcr3_gaps.py"]),
    ("mcr3_interop.py", ["validate_mcr3_adapters.py", "validate_mcr3_gaps.py"]),
    ("mcr3_chain.py", ["validate_mcr3_chain.py"]),
]

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
    ("ledger_thread_lock_body_removed", "        with self._tlock:\n            return fn(self, *a, **k)", "        if True:\n            return fn(self, *a, **k)"),
    ("ledger_has_not_thread_locked", "    @_tlocked\n    def has(self, key):", "    def has(self, key):"),
    ("ledger_for_authority_not_thread_locked", "    @_tlocked\n    def for_authority(self, authority_hash):", "    def for_authority(self, authority_hash):"),
    ("ledger_consume_not_thread_locked", "    @_tlocked\n    def consume(self, key, limit=None):", "    def consume(self, key, limit=None):"),
    ("ledger_io_guard_value_errors_not_caught", "        except (OSError, ValueError, TypeError) as exc:", "        except OSError as exc:"),
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
    # ---- added for the 3.0 modules (each reason was checked against the code; the tests that would kill a NON-equivalent variant are named in the gap closure matrix)
    'mcr3_model.py::ast: drop clause 4 of not isinstance(ref, str)': "equivalent: partition() splits at the first '::', so the part before it can never contain '::' and cannot equal a provider id that does",
    'mcr3_model.py::ast: drop clause 1 of sep == "::"': "equivalent: with no separator the tail is empty and tail != '' refuses the reference",
    'mcr3_readback.py::ast: drop clause 2 of not isinstance(src, str) or not src': "equivalent: an empty body contains no object name, so the read is UNKNOWN either way",
    'mcr3_provenance.py::ast: drop clause 1 of prov["hash_consistent"] and content is not None': "equivalent: a hash-inconsistent event is downgraded to SIGNATURE_INVALID by derive_trust anyway (defence in depth)",
    'mcr3_provenance.py::ast: drop clause 2 of prov["hash_consistent"] and content is not None': "equivalent: content is None only when digesting failed, and an attestation digest can never equal None",
    'evc1.py::ast: drop clause 2 of e["claim"]["kind"] != kind or e["claim"]["layer"] != layer': "equivalent: the schema pins the layer to a constant per claim kind, so a wrong layer fails the schema first",
    'evc1.py::ast: drop clause 1 of known.get("integrity", {}).get("event_digest") or digest_of': "equivalent: for any event that passed parse, integrity.event_digest equals digest_of(body)",
    'evc1.py::ast: drop clause 1 of isinstance(v, bool) or v is None': "equivalent: bool is a subclass of int",
    'evc1.py::ast: drop clause 2 of name in unknown or name not in KNOWN_CRITICAL': "equivalent: semantic_problems rejects the same case, so the event is rejected either way",
    'mcr3_authority.py::ast: drop clause 1 of require_unexpired and self.clock() >= exp': "equivalent: require_unexpired is always True at the only call site",
    'mcr3_authority.py::ast: drop clause 1 of a is not None and all(a[k]': "equivalent: an APPROVED capability always holds its approval record",
    'mcr3_authority.py::ast: drop clause 1 of c.state == "APPROVED" and c.approval is not None': "equivalent: the approval record is set exactly when the state is APPROVED and cleared on every other move",
    'mcr3_authority.py::ast: drop clause 2 of c.state == "APPROVED" and c.approval is not None': "equivalent: the approval record is set exactly when the state is APPROVED and cleared on every other move",
    'mcr3_authority.py::ast: drop clause 1 of exp is None or self.clock() >= exp': "equivalent: the expiry was validated when the approval was recorded, so it is never None here",
    'mcr3_scan.py::ast: drop clause 1 of not os.path.isfile(fp)': "equivalent: a missing or non-file path raises OSError on open, which is caught and skipped",
    'mcr3_scan.py::ast: drop clause 2 of mem.lower().endswith(BINARY_EXT) or mem.endswith("/")': "equivalent: a directory member reads as empty and has no findings",
    'mcr3_adapters.py::ast: drop clause 1 of attempt or self.attempt_id': "equivalent: attempt_id is always set before an attempt event is added",
    'mcr3_adapters.py::ast: drop clause 1 of mission.state == "COMPENSATED" and "comp_receipt" in ev': "equivalent: comp_receipt is persisted exactly when the state is COMPENSATED",
    'mcr3_adapters.py::ast: drop clause 2 of mission.state == "COMPENSATED" and "comp_receipt" in ev': "equivalent: comp_receipt is persisted exactly when the state is COMPENSATED",
    'mcr3_adapters.py::ast: drop clause 1 of not isinstance(chain, list)': "equivalent: a non-list chain yields no labelled rows and fails the label comparison with the same message",
    'mcr3_adapters.py::ast: drop clause 1 of mission.mutations_sent or 1': "equivalent: a mutation event exists only after a send, so mutations_sent is at least 1",
    'mcr3_adapters.py::ast: drop clause 2 of mission.mutations_sent or 1': "equivalent: a mutation event exists only after a send, so mutations_sent is at least 1",
    'mcr3_chain.py::ast: drop clause 1 of len(disp) > 1 or (disp and disp[0] != len(parsed) - 1)': "equivalent: with two dispositions the first can never be the last event",
    'mcr3_chain.py::ast: drop clause 2 of rb and rb["claim"]["claimed_authoritative"]': "equivalent: the event contract rejects an authoritative claim from a weak level before this check runs",
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


def build_mutants(src, is_model=True):
    muts = []
    for m in (GUARD_RE.finditer(src) if is_model else ()):
        cond = " ".join(m.group(2).replace("\\\n", " ").split())
        line = src.count("\n", 0, m.start()) + 1
        new = src[:m.start(2)] + "False" + src[m.end(2):]
        muts.append(("guard@L%d: %s" % (line, cond[:70]), new, src.count(m.group(0)) == 1 or True))
    for m in (REL_RE.finditer(src) if is_model else ()):
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
        taken = sum(1 for m_ in muts if m_[0] == name or m_[0].startswith(name + " #"))
        muts.append((name if not taken else "%s #%d" % (name, taken + 1), new, True))   # names must be unique
    for name, old, rep in (SPECIAL if is_model else ()):
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
    target, validators, name, new_src, applied = item
    full = "%s::%s" % (target, name)
    if not applied or new_src is None:
        return {"mutant": full, "applied": False, "detected": None, "detected_by": None}
    kind = "inconclusive"
    timed_out = False
    for _attempt in range(2):                         # one retry: an inconclusive run must not decide the outcome
        tmp = tempfile.mkdtemp(prefix="m3mut_")
        try:
            with open(os.path.join(tmp, target), "w", encoding="utf-8", newline="\n") as fh:
                fh.write(new_src)
            env = dict(os.environ, MCR3_OVERRIDE_DIR=tmp, MCR3_SKIP_TREE="1", PYTHONDONTWRITEBYTECODE="1")
            kind = None
            for v in validators:
                r = subprocess.run([sys.executable, os.path.join(HERE, v)], cwd=tmp, capture_output=True, text=True, timeout=300, env=env)   # cwd = scratch: a mutant that lets a bad path through must not litter the repository
                kind = classify(r)
                if kind is not None:
                    break
        except subprocess.TimeoutExpired:
            kind = "hang" if timed_out else "inconclusive"   # the same mutant timing out twice is a deterministic hang
            timed_out = True
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if kind != "inconclusive":
            break
    return {"mutant": full, "applied": True, "detected": kind in ("assertion", "crash", "hang"), "detected_by": kind}


def main(argv):
    jobs = int(argv[argv.index("--jobs") + 1]) if "--jobs" in argv else 4
    only = argv[argv.index("--only") + 1] if "--only" in argv else None
    items = []
    for target, validators in TARGETS:
        if only and target != only:
            continue
        src = open(os.path.join(HERE, target), encoding="utf-8").read().replace("\r\n", "\n")
        for name, new_src, applied in build_mutants(src, is_model=(target == "mcr3_model.py")):
            items.append((target, validators, name, new_src, applied))
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
        results = list(ex.map(run_one, items))
    inconclusive = [r["mutant"] for r in results if r["detected_by"] == "inconclusive"]
    survivors = [r["mutant"] for r in results if r["applied"] and not r["detected"] and r["detected_by"] != "inconclusive"]
    unexplained = [s_ for s_ in survivors if explanation(s_) is None]
    not_applied = [r["mutant"] for r in results if not r["applied"]]
    out = {"evidence_class": "SYNTHETIC/LOCAL", "mutants": len(results),
           "by_kind": {"guard": sum(1 for r in results if "::guard@" in r["mutant"]),
                       "relation": sum(1 for r in results if "::relation " in r["mutant"]),
                       "ast": sum(1 for r in results if "::ast@" in r["mutant"]),
                       "special": sum(1 for r in results if "::special:" in r["mutant"])},
           "by_module": {t_: {"mutants": sum(1 for r in results if r["mutant"].startswith(t_ + "::")),
                              "detected": sum(1 for r in results if r["mutant"].startswith(t_ + "::") and r["detected"]),
                              "assertion": sum(1 for r in results if r["mutant"].startswith(t_ + "::") and r["detected_by"] == "assertion"),
                              "crash": sum(1 for r in results if r["mutant"].startswith(t_ + "::") and r["detected_by"] == "crash"),
                              "hang": sum(1 for r in results if r["mutant"].startswith(t_ + "::") and r["detected_by"] == "hang"),
                              "survivors": sum(1 for r in results if r["mutant"].startswith(t_ + "::") and r["applied"] and not r["detected"] and r["detected_by"] != "inconclusive")}
                         for t_, _ in TARGETS if any(r["mutant"].startswith(t_ + "::") for r in results)},
           "not_applied": not_applied, "detected_by_assertion": sum(1 for r in results if r["detected_by"] == "assertion"),
           "detected_by_validator_crash": {r["mutant"]: CRASH_REASONS.get(r["mutant"].split("::", 1)[1], DEFAULT_CRASH_REASON) for r in results if r["detected_by"] == "crash"},
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
