# MCR R2.0 Evidence Plan R1

Evidence classes: PROVEN, OBSERVED, PARTIAL, SYNTHETIC, LOCAL, NOT_ESTABLISHED, DEFERRED, REJECTED. No automatic promotion. Every material claim links to an artifact and a SHA-256 in `evidence/r2.0/MCR_R2_0_CLAIM_EVIDENCE_REGISTER_R1.md`.

| Phase | Hypotheses | Evidence produced | Class ceiling | Status |
|---|---|---|---|---|
| R2.0A model foundation | model support for H41-H48 | `MCR_R2_0_A_VALIDATION_RESULT_R1.json`, schemas | SYNTHETIC | done (PASS) |
| R2.0B read-only qualification | H41, H42 prerequisites | offline contract analysis; live probe prepared | PARTIAL until live controls run | PARTIAL; blocked on provider + auth context (BLOCKER_B) |
| R2.0C frozen live outcome study | H41, H42, H43, H47 | raw provider + readback responses, receipts, hash chain | OBSERVED (one run); never PROVEN from a single mutation | not frozen; needs B result, then one fresh owner authorization |
| R2.0D replay/continuation | H44 | local crash-injection matrix (done); live only if scientifically necessary | SYNTHETIC / LOCAL | local part done |
| R2.0E compensation | H45 | local semantics (done); live needs a separate grant and packet | SYNTHETIC / LOCAL | local part done |
| R2.0F governance overhead | H48 | descriptive timing, governance separated from provider latency | LOCAL (no provider); OBSERVED only with a live run | local baseline done |
| Drift | H46 | point-of-use drift test (done, synthetic); readback-side drift and live fingerprints pending | SYNTHETIC | partial |

## Rules
- Raw, unsafe or transient evidence stays outside Git (owner workspace evidence folder) until sanitized: no tokens, auth contexts, DPAPI blobs, customer content.
- Hash-bound files are not line-ending normalized (`.gitattributes`).
- Publication artifacts use relative repository paths. `tools/r2.0/verify_r2_fresh_clone.py` verifies the lineage without the owner workspace.
- The R1.9 record (tag `v1.9.0`) is read-only for this lineage.

## Result vocabulary for the live study (R2.0C)
COMMITTED_AND_OUTCOME_VALIDATED, COMMITTED_BUT_OUTCOME_FAILED, NOT_COMMITTED, COMMIT_STATE_UNKNOWN. UNKNOWN is a valid research result and is never collapsed into PASS or FAIL.

## Live-write gate (unchanged)
No live mutation without: frozen mission, runner and hashes; prewrite validation; the complete authorization packet; one explicit fresh owner authorization. No wildcard, no reuse, no budget expansion after authorization.
