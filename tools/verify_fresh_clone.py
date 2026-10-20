#!/usr/bin/env python3
"""Fresh-clone qualification for the MCR research repository.

Pure standard library. Reads files only: no network, SAP, MCP or model access, and it never executes any
repository script. Exit code 0 = no FAIL (PASS_WITH_DOCUMENTED_GAPS is still success), 1 = at least one FAIL.

Usage:  python tools/verify_fresh_clone.py [--tag vX.Y.Z]
"""
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(ROOT)
H = lambda b: hashlib.sha256(b).hexdigest().upper()
results = []


def rec(name, status, detail=""):
    results.append((name, status, detail))
    print(f"{name}={status}" + (f"  # {detail}" if detail else ""))


def rd(p):
    return open(p, encoding="utf-8-sig").read()


def tracked_files():
    try:
        out = subprocess.run(["git", "ls-files", "-z"], capture_output=True, check=True).stdout.decode()
        return [f for f in out.split("\0") if f]
    except Exception:
        fl = []
        for d, _, fs in os.walk("."):
            if ".git" in d.split(os.sep):
                continue
            for f in fs:
                fl.append(os.path.relpath(os.path.join(d, f), ".").replace(os.sep, "/"))
        return fl


files = tracked_files()

# 1. portability: every included_exact artifact is byte-exact
m = json.load(open("evidence/portable/PORTABILITY_MANIFEST_R2.json", encoding="utf-8"))
bad = [a["artifact_id"] for a in m["artifacts"] if a["included_exact"] and H(open(a["repo_path"], "rb").read()) != a["sha256"].upper()]
gaps = [a["artifact_id"] for a in m["artifacts"] if a["missing"]]
exact = sum(1 for a in m["artifacts"] if a["included_exact"])
rec("PORTABILITY_EXACT_ARTIFACTS", "PASS" if not bad else "FAIL", f"{exact} verified" if not bad else f"mismatch: {bad}")
rec("PORTABILITY", "PASS_WITH_DOCUMENTED_HISTORICAL_GAPS" if gaps and not bad else ("PASS" if not bad else "FAIL"), f"{len(gaps)} documented gaps: {', '.join(gaps)}")

# 2. SHA256SUMS
sums = [l.rstrip("\n").split("  ", 1) for l in open("SHA256SUMS.txt", encoding="utf-8") if l.strip()]
badsum = [p for h, p in sums if not os.path.exists(p) or hashlib.sha256(open(p, "rb").read()).hexdigest().lower() != h.lower()]
uncovered = [f for f in files if f != "SHA256SUMS.txt" and f not in {p for _, p in sums}]
rec("SHA256SUMS", "PASS" if not badsum and not uncovered else "FAIL", f"{len(sums)} entries" if not badsum and not uncovered else f"bad={badsum[:3]} uncovered={uncovered[:3]}")

# 3. frozen evidence anchors
anchors = json.load(open("FROZEN_EVIDENCE_ANCHORS.json", encoding="utf-8-sig"))
byhash = {a["sha256"].upper(): a for a in m["artifacts"] if a["included_exact"]}
anc_bad, anc_gap = [], []
for a in anchors:
    s = a["sha256"].upper()
    if a.get("bytes_in_git"):
        if s not in byhash:
            anc_bad.append(a["id"])
    else:
        anc_gap.append(a["id"])
rec("FROZEN_EVIDENCE_ANCHORS", ("PASS_WITH_DOCUMENTED_GAPS" if anc_gap else "PASS") if not anc_bad else "FAIL", f"{len(anchors)} anchors; bytes-absent (documented): {len(anc_gap)}" if not anc_bad else f"unresolved: {anc_bad}")

# 4. claim/evidence linkage (claim audit R3)
ca = rd("reports/MCR_R1_9_FINAL_CLAIM_EVIDENCE_AUDIT_R3.md")
link_bad, n_claims, n_checked = [], 0, 0
for blk in re.split(r"\n## (?=C\d+)", ca)[1:]:
    n_claims += 1
    cid = blk.split()[0]
    arts = re.search(r"- \*\*supporting_artifact:\*\* (.+)", blk).group(1)
    shas = re.search(r"- \*\*artifact_sha:\*\* (.+)", blk).group(1)
    paths = re.findall(r"`([^`]+)`", arts) or []
    hs = re.findall(r"`([0-9A-F]{64})`", shas)
    for p, h in zip(paths, hs):
        if p.startswith("(") or not os.path.exists(p):
            continue
        n_checked += 1
        if H(open(p, "rb").read()) != h:
            link_bad.append((cid, p))
for p in re.findall(r"\(frozen manuscript, bytes absent\)", ca):
    pass
rec("CLAIM_EVIDENCE_LINKAGE", "PASS" if not link_bad and n_claims >= 30 else "FAIL", f"{n_claims} claims, {n_checked} artifact links hash-verified" if not link_bad else f"{link_bad[:3]}")

# 5. secret / reusable-authority scan (including decompressed ZIPs)
pat = {
    "private_key": re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "bearer": re.compile(rb"(?i)bearer\s+[A-Za-z0-9\-_\.=]{20,}"),
    "jwt": re.compile(rb"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
    "gh_token": re.compile(rb"gh[pousr]_[A-Za-z0-9]{30,}"),
    "aws_key": re.compile(rb"AKIA[0-9A-Z]{16}"),
    "zenodo_token_like": re.compile(rb"(?i)zenodo[_-]?(access[_-]?)?token\s*[:=]\s*[A-Za-z0-9]{20,}"),
    "pw_assign": re.compile(rb"(?i)\b(password|passwd|client_secret|api[_-]?key)\b\s*[:=]\s*[\"']?[^\s\"',;<>{}\[\]]{8,}"),
}
auth_true = re.compile(rb"(?i)live_sap_write_authorized\"?\s*:\s*true")
sec_hits, auth_hits = [], []


def scan(label, b):
    for k, p in pat.items():
        if p.search(b):
            sec_hits.append((label, k))
    if auth_true.search(b):
        auth_hits.append(label)


def walk(z, label, depth=0):
    for i in z.infolist():
        if i.filename.endswith("/"):
            continue
        b = z.read(i)
        scan(label + "::" + i.filename, b)
        if i.filename.lower().endswith(".zip") and depth < 4:
            try:
                walk(zipfile.ZipFile(io.BytesIO(b)), label + "::" + i.filename, depth + 1)
            except Exception:
                pass


for f in files:
    b = open(f, "rb").read()
    scan(f, b)
    if f.lower().endswith(".zip"):
        walk(zipfile.ZipFile(f), f)
name_hits = [f for f in files if re.search(r"(?i)(LIVE_WRITE_AUTHORIZATION|auth[-_]?context|\.pfx$|\.pem$|\.key$)", f)]
rec("SECRET_SCAN", "PASS" if not sec_hits else "FAIL", "no secret patterns in tracked files or nested ZIPs" if not sec_hits else f"{sec_hits[:3]}")
rec("REUSABLE_LIVE_AUTHORITY_IN_GIT", "0" if not auth_hits and not name_hits else "FAIL", "" if not auth_hits and not name_hits else f"{auth_hits[:2]} {name_hits[:2]}")

# 6. publication asset map: every backticked repo path exists
amap = rd("publication/PUBLICATION_ASSET_MAP.md")
paths = {p for p in re.findall(r"`([A-Za-z0-9_./-]+\.[A-Za-z0-9]+)`", amap) if "/" in p or p.endswith((".md", ".json", ".pdf"))}
missing = [p for p in paths if not os.path.exists(p)]
rec("PUBLICATION_ASSET_MAP", "PASS" if not missing else "FAIL", f"{len(paths)} referenced paths exist" if not missing else f"missing: {missing}")

# 7. citation metadata
cff = rd("CITATION.cff")
pm = json.load(open("PUBLICATION_MANIFEST.json", encoding="utf-8-sig"))
ver_cff = re.search(r'^version:\s*"?([^"\n]+)"?', cff, re.M).group(1).strip()
doi_cff = re.search(r'^doi:\s*"?([^"\n]+)"?', cff, re.M)
ok = ver_cff == pm.get("version") and re.search(r"orcid.org/0009-0008-1344-6585", cff) is not None
if doi_cff:
    ok = ok and re.fullmatch(r"10\.5281/zenodo\.\d+", doi_cff.group(1).strip()) is not None
rec("CITATION_METADATA", "PASS" if ok else "FAIL", f"version {ver_cff}; DOI {'present' if doi_cff else 'none (not yet issued)'}")

# 8. reproducibility doc documents gaps and no-rerun rule
rp = rd("REPRODUCIBILITY.md")
ok = all(s in rp for s in ("HF06_DO_NOT_RERUN=TRUE", "CREATE_COMMIT_STATE=UNKNOWN", "MISSING_ARTIFACTS_R2"))
rec("REPRODUCIBILITY_DOC", "PASS" if ok else "FAIL")

# 9. frozen MCWS result in the final manuscript
ms = rd(pm["manuscript"])
need = ["| Broad | 5/48 | 10.4% |", "| Static | 17/48 | 35.4% |", "| MCWS | 30/48 | 62.5% |", "0.00293", "0.03125", "0.2266", "E589393C6EEA0BA92E4EC521D1577A6F561F9ADFA38FF9EEE97A94695C666D90", "0/12", "2/12", "7/12"]
rec("FROZEN_MCWS_RESULT", "PASS" if all(s in ms for s in need) else "FAIL")
bound = all(s in ms for s in ("CREATE reached", "ACTIVATE did not", "UNKNOWN", "REQUESTED != AUTHORIZED != BOUND != EXECUTED != COMMITTED != VALIDATED_COMPLETE"))
rec("R1_9B_BOUNDARY_IN_MANUSCRIPT", "PASS" if bound else "FAIL")

# 10. optional tag / commit check
if "--tag" in sys.argv:
    tag = sys.argv[sys.argv.index("--tag") + 1]
    try:
        tc = subprocess.run(["git", "rev-parse", tag + "^{commit}"], capture_output=True, text=True, check=True).stdout.strip()
        head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        rec("TAG_RESOLVES", "PASS", f"{tag} -> {tc[:12]}")
        rec("RELEASE_COMMIT_MATCH", "PASS" if tc == head else "FAIL", f"HEAD {head[:12]}")
    except Exception as e:
        rec("TAG_RESOLVES", "FAIL", str(e))

fails = [r for r in results if r[1] == "FAIL"]
print("OVERALL=" + ("FAIL" if fails else "PASS_WITH_DOCUMENTED_GAPS" if any("GAPS" in r[1] or "GAPS" in r[2] for r in results) or gaps else "PASS"))
sys.exit(1 if fails else 0)
