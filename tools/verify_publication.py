#!/usr/bin/env python3
"""Fail-closed, standard-library MCR4 v1.0.2 PUBLICATION verifier, not production qualification."""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROOT_COMMIT = "c82d8ce128e1ddd8ab52bd5066f4e74ff770bae4"
HASHES = {
    "paper/MCR4_Preprint_PublicReview_v1.0.2.pdf": "05468984528309e926b0563908fb7c0baa4f633987ad92d55c07d7b1747fe545",
    "paper/MCR4_Preprint_PublicReview_v1.0.2.tex": "5a045f1edca33533a5ec4ff56fc6b807e75b27b9b085dd350325078783bf434b",
    "evidence/MCR4_PUBLIC_SAFE_EVIDENCE_SUMMARY_R3.md": "593024e598313bb92667904233a51d4292be0398832ddb7ca721720fb06dc00d",
}
ALLOWED = {
    ".gitattributes", ".github/workflows/mcr4-publication.yml",
    "README.md", "RELEASE_NOTES.md", "SHA256SUMS.txt", "tools/verify_publication.py",
    *HASHES.keys(),
    "metadata/MCR4_PREPRINT_CITATION_PROPOSAL_R4.cff",
    "metadata/MCR4_LICENSE_AND_ATTRIBUTION_PROPOSAL_R4.md",
    "metadata/ZENODO_DRAFT_METADATA_R4.json",
    "metadata/OWNER_PUBLICATION_AUTHORIZATION_R5.md",
}
errors = []
def require(ok, msg):
    if not ok: errors.append(msg)
def digest(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda: f.read(1024*1024), b""): h.update(block)
    return h.hexdigest()
def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT).decode("utf-8").strip()
try:
    roots = git("rev-list", "--max-parents=0", "HEAD").splitlines()
    require(roots == [ROOT_COMMIT], "independent/orphan history root not confirmed")
    tracked = set(git("ls-files", "-z").split("\x00")) - {""}
    require(tracked == ALLOWED, "tracked publication-file allowlist mismatch: " + str(sorted(tracked ^ ALLOWED)))
    for name in sorted(tracked):
        p = ROOT / name
        require(p.is_file() and not p.is_symlink(), "missing/symlink file: " + name)
        require(p.suffix.lower() not in {".zip", ".pt", ".pem", ".key", ".pfx", ".p12"}, "excluded extension: " + name)
    for name, expected in HASHES.items():
        p = ROOT / name
        require(p.is_file() and digest(p) == expected, "approved SHA256 mismatch or missing: " + name)
    manifest = {}
    for line in (ROOT / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        parts = line.split(maxsplit=1)
        require(len(parts) == 2, "invalid manifest line")
        if len(parts) == 2:
            require(parts[1] not in manifest, "duplicate manifest entry")
            manifest[parts[1]] = parts[0].lower()
    require(manifest == HASHES, "manifest does not match approved PDF/TeX/R3 hashes")
    if (ROOT / "paper/MCR4_Preprint_PublicReview_v1.0.2.pdf").is_file():
        with (ROOT / "paper/MCR4_Preprint_PublicReview_v1.0.2.pdf").open("rb") as f:
            require(f.read(5) == b"%PDF-", "PDF header invalid")
    for name in ["RELEASE_NOTES.md", "evidence/MCR4_PUBLIC_SAFE_EVIDENCE_SUMMARY_R3.md"]:
        t = (ROOT / name).read_text(encoding="utf-8")
        for claim in ["MCR_R4_0_P1_CLOSED_BOUNDED_SYNTHETIC_RESEARCH", "38/40", "40/40"]:
            require(claim in t, "missing historic/scoped research claim: " + name + " " + claim)
    path_pat = re.compile(r"(?i)[a-z]:\\(?:users|mcr|sap)")
    token_pat = re.compile(r"(?i)(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{40,})")
    for name in tracked:
        p = ROOT / name
        if p.suffix.lower() in {".md", ".tex", ".yml", ".json", ".cff", ".txt"} and p.is_file():
            content = p.read_text(encoding="utf-8", errors="replace")
            require(not path_pat.search(content), "local private path: " + name)
            require(not token_pat.search(content), "token-shaped string: " + name)
    meta = json.loads((ROOT / "metadata/ZENODO_DRAFT_METADATA_R4.json").read_text(encoding="utf-8"))
    require(meta.get("doi") == "NOT_ASSIGNED", "fabricated or stale Zenodo DOI")
except Exception as exc:
    errors.append("verifier exception: " + repr(exc))
for msg in errors: print("HOLD_PUBLICATION:", msg, file=sys.stderr)
if errors:
    print("MCR4_PUBLICATION_CI=FAIL")
    sys.exit(1)
print("MCR4_PUBLICATION_CI=PASS")
print("SCOPE=CLASS_A_BOUNDED_SYNTHETIC_RESEARCH_ONLY")
