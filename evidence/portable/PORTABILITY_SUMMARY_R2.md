# MCR Git Portability Summary R2

Supersedes `PORTABILITY_SUMMARY_R1.md` (R1 records are preserved unchanged).

## Scientific boundary (unchanged)

- CREATE reached provider: TRUE
- ACTIVATE reached provider: FALSE
- CREATE commit state: UNKNOWN
- Object state inference: UNKNOWN
- Authoritative repository readback: FALSE
- HF06 replay authorized: FALSE
- Historical authorization reuse authorized: FALSE

## What changed from R1

R1 reported `INCLUDED_EXACT=28`, `HASH_MISMATCH=0`. That was **wrong for 19 of the 28 files**: the R1 commit was written under `.gitattributes` `* text=auto eol=lf`, so Git normalized line endings and the stored bytes no longer equalled the recorded source hashes (including the HF06 signed runner and the single-use lock).

R2 actions:

1. `.gitattributes`: added `evidence/portable/** -text` so evidence bytes can never be normalized again.
2. Restored byte-exact, each verified against the recorded SHA-256 before writing:
   - 10 files extracted from ZIPs already in Git (by hash match);
   - 3 files restored by deterministic LF to CRLF conversion (hash-verified).
3. Resolved the three R1.9B gaps from the prewrite-freeze ZIP (ZIP SHA `3DFE6756...` verified; entry hashes equal the ZIP's own `17_PACKAGE_MANIFEST_R1.json`).
4. Recovered two R1.6 artifacts from owner-local files on this machine; the third is still absent.

## Counts (catalog = 36 artifacts)

| Measure | R1 | R2 |
|---|---:|---:|
| Catalog | 35 | 36 (+RC1 package) |
| Included, byte-exact, hash-verified | 28 (19 actually not exact) | 28 |
| Hash-only (sensitive) | 1 | 1 |
| Absent everywhere | 6 | 1 |
| Normalized copy only, original bytes unavailable (HASH_MISMATCH) | 0 reported | 6 |
| Mandatory unresolved | 6 | 6 (different composition) |

## Gate

- MANDATORY_UNRESOLVED=6
- HASH_MISMATCH=6 (normalization artifacts of signed scripts; cause documented, not content change)
- SECRETS_IN_GIT=0
- REUSABLE_LIVE_AUTHORITY_IN_GIT=0

FRESH_CLONE_CAN_AUDIT_AVAILABLE_EVIDENCE=TRUE

FRESH_CLONE_CAN_VERIFY_FULL_HISTORICAL_SOURCE_LINEAGE=FALSE

PORTABILITY_STATE=PORTABLE_RESEARCH_BASELINE_READY_WITH_DOCUMENTED_HISTORICAL_GAPS

See `MISSING_ARTIFACTS_R2.md`.
