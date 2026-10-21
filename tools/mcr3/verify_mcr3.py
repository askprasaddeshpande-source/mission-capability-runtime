"""Verify an MCR 3.0 checkout. Offline; needs no owner workspace; no network; no SAP.

Usage:
  python tools/mcr3/verify_mcr3.py                       # verify the checkout this file lives in (full: runs every validator)
  python tools/mcr3/verify_mcr3.py --fast                # sums, frozen-history check, secret scan only (no validator run)
  python tools/mcr3/verify_mcr3.py --clone               # git clone the checkout to a temp folder first, verify the clone
  python tools/mcr3/verify_mcr3.py --expect-sums-sha256 H   # anchor: SHA-256 of the sums file, taken from OUTSIDE the repository
  python tools/mcr3/verify_mcr3.py --write-sums          # (re)write evidence/mcr3/SHA256SUMS_MCR3.txt
  python tools/mcr3/verify_mcr3.py --no-git              # skip the checks that need git history (reported as NOT_CHECKED)
Checks: sums cover every tracked file of the MCR 3.0 folders and match; the frozen R1.9/R2.0 history is untouched since the
baseline commit (no modified, deleted or renamed path outside the 3.0 folders, tag v1.9.0 unchanged); no credential-shaped
content anywhere in the tracked tree; no machine-specific absolute path in 3.0 code; the validators pass and reproduce the
archived results. Without --expect-sums-sha256 the verifier is SELF-ATTESTING: an attacker who edits files and the sums file
together passes.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mcr3_scan  # noqa: E402

BASELINE = "fd865c67c053431dc33297a0df2a3c9a02fd51fe"
R1_9_TAG, R1_9_COMMIT = "v1.9.0", "9c5105fe5b35dadf7b1384f54d4bea4c490d3ae0"
NEW_DIRS = ("tools/mcr3/", "architecture/mcr3/", "evidence/mcr3/", "reports/mcr3/")
SUMS = "evidence/mcr3/SHA256SUMS_MCR3.txt"
ABS = re.compile(r"(?i)(?<![A-Za-z0-9])[A-Za-z]:[\\/](?!/)|\\\\[A-Za-z0-9_.-]+\\|/(?:home|Users)/[A-Za-z0-9_.-]+")
ABS_ALLOWED_FILES = {"tools/mcr3/verify_mcr3.py", "tools/mcr3/run_mcr3_verifier_attacks.py"}


def sh(path):
    b = open(path, "rb").read().replace(b"\r\n", b"\n")
    return hashlib.sha256(b).hexdigest().upper()


def git(root, *args):
    return subprocess.run(["git"] + list(args), cwd=root, capture_output=True, text=True)


def tracked_new(root):
    r = git(root, "ls-files")
    return sorted(p for p in r.stdout.split("\n") if p and p.startswith(NEW_DIRS) and p != SUMS and "__pycache__" not in p and not p.endswith((".pyc", ".pyo")))


def write_sums(root):
    files = tracked_new(root) if git(root, "rev-parse", "--git-dir").returncode == 0 else sorted(
        os.path.relpath(os.path.join(d, f), root).replace("\\", "/") for t in NEW_DIRS for d, _, fs in os.walk(os.path.join(root, t)) for f in fs if "__pycache__" not in d)
    files = [f for f in files if f != SUMS]
    with open(os.path.join(root, SUMS), "w", newline="\n") as fh:
        for f in files:
            fh.write("%s  %s\n" % (sh(os.path.join(root, f)), f))
    print("wrote", SUMS, len(files), "files")


def verify(root, argv):
    res = {}
    use_git = "--no-git" not in argv and git(root, "rev-parse", "--git-dir").returncode == 0
    listed = {}
    try:
        for line in open(os.path.join(root, SUMS), encoding="utf-8"):
            h, p = line.rstrip("\n").split("  ", 1)
            listed[p] = h
    except OSError:
        listed = None
    res["sums_file_present"] = listed is not None
    listed = listed or {}
    if use_git:
        res["sums_cover_every_tracked_file"] = sorted(listed) == tracked_new(root)
    else:
        res["sums_cover_every_tracked_file"] = "NOT_CHECKED (--no-git or no repository)"
    res["sums_hashes_match"] = bool(listed) and all(os.path.exists(os.path.join(root, p)) and sh(os.path.join(root, p)) == h for p, h in listed.items())
    sums_sha = sh(os.path.join(root, SUMS)) if listed else None
    res["sums_sha256"] = sums_sha
    if "--expect-sums-sha256" in argv:
        res["sums_anchor_matches"] = sums_sha == argv[argv.index("--expect-sums-sha256") + 1].upper()
    else:
        res["sums_anchor_matches"] = "NOT_CHECKED (pass --expect-sums-sha256 from a source outside the repository)"

    if use_git:
        have_base = git(root, "cat-file", "-e", BASELINE + "^{commit}").returncode == 0
        if have_base:
            diff = git(root, "diff", "--name-status", "-M", BASELINE, "HEAD").stdout.splitlines()
            bad = []
            for line in diff:
                parts = line.split("\t")
                st, paths = parts[0], parts[1:]
                if st.startswith("A") and all(p.startswith(NEW_DIRS) for p in paths):
                    continue
                bad.append(line)
            res["frozen_history_untouched"] = not bad
            res["frozen_history_violations"] = bad[:10]
            dirty = git(root, "status", "--porcelain").stdout.splitlines()
            res["working_tree_clean"] = not dirty
        else:
            res["frozen_history_untouched"] = "NOT_CHECKED (baseline commit not in this checkout)"
        tag = git(root, "rev-parse", R1_9_TAG + "^{commit}")
        res["r1_9_tag"] = "UNCHANGED" if tag.stdout.strip() == R1_9_COMMIT else "CHANGED_OR_MISSING"
        res["no_tracked_bytecode"] = not any("__pycache__" in x or x.endswith((".pyc", ".pyo")) for x in git(root, "ls-files").stdout.split("\n"))
    else:
        res["frozen_history_untouched"] = res["r1_9_tag"] = res["no_tracked_bytecode"] = "NOT_CHECKED (--no-git or no repository)"

    hits = mcr3_scan.scan_tracked_tree(root) if use_git else []
    res["no_credential_shaped_content"] = (not hits) if use_git else "NOT_CHECKED (--no-git)"
    res["credential_hits"] = [(p, n) for p, n, _ in hits][:10]
    bad_abs = []
    for p in tracked_new(root) if use_git else listed:
        if p.startswith("tools/mcr3/") and p.endswith(".py") and p not in ABS_ALLOWED_FILES:
            if ABS.search(open(os.path.join(root, p), encoding="utf-8", errors="replace").read()):
                bad_abs.append(p)
    res["no_machine_specific_paths_in_code"] = not bad_abs
    res["absolute_path_files"] = bad_abs

    if "--fast" in argv:
        res["validators"] = "SKIPPED (--fast)"
    else:
        out = os.path.join(root, "evidence", "mcr3")
        r = subprocess.run([sys.executable, os.path.join(root, "tools", "mcr3", "run_mcr3_tests.py"), "--check-dir", out], capture_output=True, text=True, cwd=root, timeout=3600)
        try:
            d = json.loads(r.stdout)
        except Exception:
            d = {}
        res["validators_pass"] = r.returncode == 0 and d.get("MCR3_TESTS") == "PASS"
        res["validator_results_reproduce"] = d.get("reproduces_archived_results") is True
        res["tests"] = d.get("tests")
        res["not_verified"] = d.get("not_verified")
    bools = [v for k, v in res.items() if isinstance(v, bool) and k not in ("working_tree_clean",)]
    strict = all(bools) and res.get("r1_9_tag") in ("UNCHANGED", "NOT_CHECKED (--no-git or no repository)")
    res["MCR3_VERIFY"] = "PASS" if strict else "FAIL"
    return res


def main(argv):
    root = os.path.abspath(os.path.join(HERE, "..", ".."))
    if "--write-sums" in argv:
        write_sums(root)
        return 0
    if "--clone" in argv:
        t = tempfile.mkdtemp(prefix="mcr3_clone_")
        c = subprocess.run(["git", "clone", "-q", "--no-hardlinks", root, os.path.join(t, "c")], capture_output=True, text=True)
        if c.returncode != 0:
            print(json.dumps({"MCR3_VERIFY": "FAIL", "error": "clone failed", "detail": c.stderr[-400:]}))
            return 1
        g = git(root, "rev-parse", "HEAD").stdout.strip()
        git(os.path.join(t, "c"), "checkout", "-q", g)
        root = os.path.join(t, "c")
        argv = [a for a in argv if a != "--clone"]
        try:
            res = verify(root, argv)
        finally:
            shutil.rmtree(t, ignore_errors=True)
    else:
        res = verify(root, argv)
    print(json.dumps(res, indent=2, sort_keys=True))
    return 0 if res["MCR3_VERIFY"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
