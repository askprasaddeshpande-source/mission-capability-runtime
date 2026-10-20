"""Verify the R2.0 lineage from a repository checkout; needs no owner workspace.

Usage:
  python tools/r2.0/verify_r2_fresh_clone.py            # verify the checkout this file lives in
  python tools/r2.0/verify_r2_fresh_clone.py --clone    # git clone the checkout into a temp dir first
  python tools/r2.0/verify_r2_fresh_clone.py --write-sums   # (maintainers) regenerate SHA256SUMS_R2_0.txt

Checks: file hashes match SHA256SUMS_R2_0.txt (CRLF-insensitive for text); validator and scenario results
regenerate byte-identically; schemas regenerate identically; no absolute workstation paths or secret-like
strings in published R2.0 artifacts; if tag v1.9.0 exists it still points at the recorded commit.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

R1_9_TAG, R1_9_COMMIT = "v1.9.0", "9c5105fe5b35dadf7b1384f54d4bea4c490d3ae0"
SUMS = "evidence/r2.0/SHA256SUMS_R2_0.txt"
ROOTS = ["tools/r2.0", "architecture/r2.0", "evidence/r2.0", "reports/r2.0", "research-package/r2.0"]
SKIP = {SUMS, "__pycache__"}
TEXT = (".py", ".md", ".json", ".txt")
LOCAL_EXEC_DOCS = {"research-package/r2.0/r2_0c/MCR_R2_0_C_AUTHORIZATION_PACKET_R1.md"}   # owner-workspace commands by design
ABS = re.compile(r"[A-Za-z]:\\|/Users/|/home/[a-z]")
SECRET = re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}|protected_token_b64\"\s*:\s*\"[A-Za-z0-9+/=]{20,}|BEGIN (RSA |EC )?PRIVATE KEY")


def files(root):
    out = []
    for r in ROOTS:
        for d, dn, fn in os.walk(os.path.join(root, r)):
            dn[:] = [x for x in dn if x != "__pycache__"]
            for f in fn:
                p = os.path.relpath(os.path.join(d, f), root).replace("\\", "/")
                if p not in SKIP and not f.endswith(".pyc"):
                    out.append(p)
    return sorted(out)


def sha(path):
    b = open(path, "rb").read()
    if path.endswith(TEXT):
        b = b.replace(b"\r\n", b"\n")
    return hashlib.sha256(b).hexdigest().upper()


def run(root, *args):
    return subprocess.run([sys.executable, *args], cwd=root, capture_output=True, text=True)


def main(argv):
    root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    tmp = None
    if "--clone" in argv:
        tmp = tempfile.mkdtemp(prefix="r2verify_")
        subprocess.run(["git", "clone", "-q", root, tmp], check=True)
        root = tmp
    if "--write-sums" in argv:
        with open(os.path.join(root, SUMS), "w", newline="\n") as fh:
            for p in files(root):
                fh.write("%s  %s\n" % (sha(os.path.join(root, p)), p))
        print("wrote", SUMS)
        return 0
    res = {}
    listed = {}
    for line in open(os.path.join(root, SUMS), encoding="utf-8"):
        h, p = line.rstrip("\n").split("  ", 1)
        listed[p] = h
    cur = files(root)
    res["sums_cover_all_files"] = sorted(listed) == cur
    res["hashes_match"] = all(os.path.exists(os.path.join(root, p)) and sha(os.path.join(root, p)) == h for p, h in listed.items())
    t = tempfile.mkdtemp(prefix="r2out_")
    a = run(root, "tools/r2.0/validate_r2_outcome_model.py", "--out", os.path.join(t, "a.json"), "--emit-schemas", os.path.join(t, "schemas"))
    res["validator_passes"] = a.returncode == 0
    res["validator_result_reproduces"] = open(os.path.join(t, "a.json"), "rb").read() == open(os.path.join(root, "evidence/r2.0/MCR_R2_0_A_VALIDATION_RESULT_R1.json"), "rb").read().replace(b"\r\n", b"\n")
    sch = sorted(os.listdir(os.path.join(t, "schemas")))
    res["schemas_reproduce"] = sch == sorted(os.listdir(os.path.join(root, "architecture/r2.0/schemas"))) and all(
        open(os.path.join(t, "schemas", s), "rb").read() == open(os.path.join(root, "architecture/r2.0/schemas", s), "rb").read().replace(b"\r\n", b"\n") for s in sch)
    d = run(root, "tools/r2.0/run_r2_local_scenarios.py", "--out", os.path.join(t, "d.json"))
    res["scenarios_pass"] = d.returncode == 0
    res["scenarios_result_reproduces"] = open(os.path.join(t, "d.json"), "rb").read() == open(os.path.join(root, "evidence/r2.0/MCR_R2_0_DE_LOCAL_SCENARIOS_RESULT_R1.json"), "rb").read().replace(b"\r\n", b"\n")
    bad_abs, bad_sec = [], []
    for p in cur:
        if p.endswith(TEXT):
            txt = open(os.path.join(root, p), encoding="utf-8", errors="replace").read()
            if p.startswith("tools/") is False and p not in LOCAL_EXEC_DOCS and ABS.search(txt):
                bad_abs.append(p)
            if SECRET.search(txt):
                bad_sec.append(p)
    res["no_absolute_paths_in_docs"] = not bad_abs
    res["no_secret_like_strings"] = not bad_sec
    g = subprocess.run(["git", "rev-parse", "-q", "--verify", R1_9_TAG + "^{commit}"], cwd=root, capture_output=True, text=True)
    res["r1_9_tag"] = ("UNCHANGED" if g.stdout.strip() == R1_9_COMMIT else "CHANGED") if g.returncode == 0 else "NOT_PRESENT_IN_CHECKOUT"
    ok = all(v is True for k, v in res.items() if k != "r1_9_tag") and res["r1_9_tag"] != "CHANGED"
    print(json.dumps(dict(res, details={"absolute_path_files": bad_abs, "secret_like_files": bad_sec}, R2_FRESH_CLONE_VERIFY="PASS" if ok else "FAIL"), indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
