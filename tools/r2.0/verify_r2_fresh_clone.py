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
# Historical (R2.0A-C, baseline commit 6f992c6) files that must stay byte-identical; superseding work is added as new versions.
FROZEN_HISTORICAL = {
    "evidence/r2.0/MCR_R2_0_A_VALIDATION_RESULT_R1.json": "8456E2D3B9148CC949086E3BB30E46F41DA78BE0D526890E04F6FB990A1EC126",
    "evidence/r2.0/MCR_R2_0_B_DDLS_CONTROL_SUMMARY_R1.json": "1BE52855011E6A49D28BF5D4C2842D74FB44A2DDA2E42AE4F53D25286D314C17",
    "evidence/r2.0/MCR_R2_0_B_LIVE_READONLY_PROBE_SUMMARY_R1.json": "1EE963DC90B8DE986CC83329851AB0E9A4782088AB46AF66B7A3EA6C8E2D9D40",
    "evidence/r2.0/MCR_R2_0_C_LIVE_EXECUTION_RESULT_R1.json": "FA2B7518F7815C08EAD1658C912524CDC3EAAD0F0F82DF90B0B32A2806160A02",
    "evidence/r2.0/MCR_R2_0_C_MOCK_SCENARIOS_R1.json": "4213C0CDAD3A58B10A2DE752010B82EFE51DD52E096E5202C61BFB72C84C58A7",
    "evidence/r2.0/MCR_R2_0_C_PREWRITE_LIVE_READONLY_R1.json": "7E0750A1BD50196FC17C5E023F7AAE7A24F202B31DDB278DE45E38FCB25FCD66",
    "evidence/r2.0/MCR_R2_0_DE_LOCAL_SCENARIOS_RESULT_R1.json": "4BF0B24C9032F6254258ECAC9088F1B78BE431EAE2829850FED9F3632E7ABD5E",
    "evidence/r2.0/MCR_R2_0_HYPOTHESIS_STATUS_R2.md": "120499A8E39C34E7079838BCEDF279F1AAB57F52007D6B0B1C92F4175F2BA347",
    "reports/r2.0/MCR_R2_0_C_LIVE_OUTCOME_STUDY_REPORT_R1.md": "B1635033CFAE49D01728B6DC19C33F5B083387E16A20AAA45C187A5B23FB1B9A",
    "research-package/r2.0/r2_0c/MCR_R2_0_C_AUTHORIZATION_PACKET_R1.md": "751C6BD6507C4127CAFB35334F350A2CEF1518309935D0B31B27E75EA29D34D8",
    "research-package/r2.0/r2_0c/R2_0C_FREEZE_R1.json": "43A775C21EC2AE1D640DE5A2955762D57E4877BCE828BA828EDBBBA01C67E833",
    "tools/r2.0/r2_0c_study.py": "A73F4647E0AC9B672284A4A4D4A87AE031CBC6AFB7707362C9050ED632C3DDC9"
}
ROOTS = ["tools/r2.0", "architecture/r2.0", "evidence/r2.0", "reports/r2.0", "research-package/r2.0"]
SKIP = {SUMS, "__pycache__", "tools/r2.0/make_adt_auth_context.py"}   # local credential helper, git-ignored
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
    res["validator_result_reproduces"] = open(os.path.join(t, "a.json"), "rb").read() == open(os.path.join(root, "evidence/r2.0/MCR_R2_0_A_VALIDATION_RESULT_R2.json"), "rb").read().replace(b"\r\n", b"\n")
    sch = sorted(os.listdir(os.path.join(t, "schemas")))
    res["schemas_reproduce"] = sch == sorted(os.listdir(os.path.join(root, "architecture/r2.0/schemas"))) and all(
        open(os.path.join(t, "schemas", s), "rb").read() == open(os.path.join(root, "architecture/r2.0/schemas", s), "rb").read().replace(b"\r\n", b"\n") for s in sch)
    d = run(root, "tools/r2.0/run_r2_local_scenarios.py", "--out", os.path.join(t, "d.json"))
    res["scenarios_pass"] = d.returncode == 0
    res["scenarios_result_reproduces"] = open(os.path.join(t, "d.json"), "rb").read() == open(os.path.join(root, "evidence/r2.0/MCR_R2_0_DE_LOCAL_SCENARIOS_RESULT_R1.json"), "rb").read().replace(b"\r\n", b"\n")
    res["frozen_historical_unchanged"] = all(os.path.exists(os.path.join(root, p)) and sha(os.path.join(root, p)) == h for p, h in FROZEN_HISTORICAL.items())
    m = run(root, "tools/r2.0/run_r2_mutation_check.py", "--out", os.path.join(t, "m.json"))
    res["mutation_check_passes"] = m.returncode == 0
    res["mutation_result_reproduces"] = open(os.path.join(t, "m.json"), "rb").read() == open(os.path.join(root, "evidence/r2.0/MCR_R2_0_G_MUTATION_CHECK_R1.json"), "rb").read().replace(b"\r\n", b"\n")
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
