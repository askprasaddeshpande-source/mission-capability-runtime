# MCR Portability Final Gap Recovery R1

Stage: `MCR_PORTABILITY_FINAL_GAP_RECOVERY_R1`
Branch: `work/r1.9-portability-final-gap-recovery-r1` (from `09e84287725f18a8ecf013619b98f57aaab28af1`)
Operations performed: local hashing, ZIP enumeration, file copy. No SAP, MCP, model or historical-runner execution.

## 1. Preflight

Repository `askprasaddeshpande-source/mission-capability-runtime`, visibility PRIVATE, active `gh` identity `askprasaddeshpande-source`, portability commit and branch present, worktree clean. Working copy: `D:\MCR\mission-capability-runtime` (fresh clone; the expected `D:\MCP\research-paper\...` clone did not exist).

## 2. R1 gap hypothesis, verified

The six R1 gaps were real. A seventh problem, larger than any of them, was found while verifying (section 3).

## 3. New finding: R1 "exact" copies were not exact

`.gitattributes` contains `* text=auto eol=lf` and `*.ps1 text eol=crlf`. The R1 commit therefore stored LF-normalized bytes. Recomputing every catalog entry from the Git index showed 19 of 28 `INCLUDED_EXACT` entries did not equal their recorded source SHA-256, including the HF06 signed runner (`DE183ABC...`), the single-use lock and the HF06 output. R1's `HASH_MISMATCH=0` was incorrect.

Fix: `evidence/portable/** -text` appended to `.gitattributes`; history not rewritten.

## 4. Recovery results

| Method | Count | Files |
|---|---:|---|
| Extracted from ZIP in Git by hash match | 10 | R1.9A runner, R1.8 taxonomy JSON, R1.9B contract, principal, delegation, budget, transaction, lease, compensation, package manifest |
| LF to CRLF restoration, hash-verified | 3 | HF06 single-use lock, HF06 output, adjudication result R2 |
| R1.9B previously missing, extracted from prewrite ZIP | 3 | mission execution envelope (04), expected outcome (08), pre-write checkpoint (11) |
| R1.6, copied from owner-local files | 3 | original R1.6.1 PDF, adversarial review, RC1 package (supporting) |
| Unrecoverable (normalized copy only) | 6 | Watchdog R2, HF05 forensic, HF06 runner, HF06 forensic, HF06 preflight, HF06 adjudication script |
| Absent everywhere | 1 | frozen scientific manuscript `E589...` |

Prewrite ZIP: SHA-256 `3DFE6756695A67EF28BBF54F5C7B61746A819B4161923B0319FEC26683C3ECF9` verified. Artifact identity resolved by semantics and cross-checked against the ZIP's own `17_PACKAGE_MANIFEST_R1.json`; filenames from prior prompts were not trusted.

R1.6 status: the PDF is `MATCHED_TO_FROZEN` (hash equals `canonical_pdf_sha256` in the RC1 manifest; content verified: title, subtitle, "Adversarially Hardened Whitepaper Candidate R1.6.1 - 31 August 2026", cites `E589...`). The review is `NEWLY_RECORDED`. The frozen manuscript is `HISTORICALLY_FROZEN` but missing; nothing was synthesized.

## 5. Secret and authority scan

Tracked files and decompressed ZIP contents (nested to depth 4) were scanned. No private keys, bearer/JWT tokens, cloud keys or credential assignments. Hits reviewed: `DPAPI` and `protected_token` are provenance labels; `token_sha256` is a hash only; one script references a local `C:\Users\Admin\...` extension path (private-path note). The only authorization-like files are the single-use lock (barrier) and an authorization **request** template with `live_sap_write_authorized: false`.

SECRETS_IN_GIT=0, REUSABLE_LIVE_AUTHORITY_IN_GIT=0.

## 6. Gate

PORTABILITY_GATE=PASS_WITH_DOCUMENTED_GAPS
PORTABILITY_STATE=PORTABLE_RESEARCH_BASELINE_READY_WITH_DOCUMENTED_HISTORICAL_GAPS
FRESH_CLONE_CAN_AUDIT_AVAILABLE_EVIDENCE=TRUE
FRESH_CLONE_CAN_VERIFY_FULL_HISTORICAL_SOURCE_LINEAGE=FALSE

## 7. Owner action to close remaining gaps

Supply from the original workstation, byte-unmodified: the frozen scientific manuscript (`E589...`) and the six original signed scripts. Verify each hash before import. If never retrievable, keep as documented gaps.
