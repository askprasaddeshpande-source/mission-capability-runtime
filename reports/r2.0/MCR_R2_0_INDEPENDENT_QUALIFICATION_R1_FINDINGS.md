# MCR R2.0 Independent Qualification R1: Reviewer Findings (as received)

Mission `MCR_R2_0_INDEPENDENT_QUALIFICATION_R1`, target commit `8a383b6ebe51d22db1676c3e865a676a3ef985a0`, baseline `6f992c6`. Reviewer: a separate agent instance (not the implementing session), working read-only in a clean detached clone, no network/SAP/credential access. This file records its final reply condensed but without changing any finding or verdict. The reviewer's full report stays in the owner workspace (not published).

**INDEPENDENT_REVIEW_VERDICT = HOLD**

## Why HOLD
A mission could reach COMPLETE without the evidence the repository claimed. Two in-process paths were reproduced; the live run and the mock runner never use them.

## Verification table (14 items)
| # | Item | Result |
|---|---|---|
| 1 | Exact commit and fresh-clone reproducibility | PASS |
| 2 | Frozen evidence unchanged | PARTIAL |
| 3 | Completion receipt validated before COMPLETE | PARTIAL |
| 4 | 14 chain links in correct order | PARTIAL |
| 5 | Invalid, absent, tampered or wrong-kind receipts rejected | PASS |
| 6 | Missing or corrupted upstream links rejected | PARTIAL |
| 7 | Unknown commit state cannot reach COMPLETE | FAIL |
| 8 | Failed and unknown predicates cannot complete | PARTIAL |
| 9 | Mutation-test independence and reproducibility | PARTIAL |
| 10 | Frozen-runner behavioral equivalence | PASS |
| 11 | Historical 13/14 result preserved | PASS |
| 12 | No unsupported promotion of H41, H42, H43, H47 | PARTIAL |
| 13 | No credentials or machine paths introduced | PASS |
| 14 | No unsupported activation, package or SAP claims | PASS |

## Findings, ranked
1. **HIGH** `Mission.resume()` trusts the lease and sets state directly: it never checked the lease hash, copied `state_at_checkpoint` into the state, and accepted any evidence slot. A lease with an invalid hash plus fabricated hash-valid receipts reached COMPLETE with an UNKNOWN readback at source level INFERRED_OR_REGEX.
2. **HIGH** Failed calls changed evidence before the transition check (`observe_readback`, `record_execution`, `begin_execution`). After OUTCOME_VALIDATED a rejected late call replaced the readback or execution receipt, and `complete()` then accepted it (one accepted receipt had call class CALL_NOT_SENT).
3. **HIGH** `complete()` checked only per-object hash validity and four pinned hashes: no relational checks (readback existence/source level, execution call class, cross-object bindings); a valid-hash object of the wrong kind in the `intent` slot and attacker-recomputed hashes were accepted; `_go("COMPLETE")` was directly callable.
4. **MEDIUM** An empty predicate list passed vacuously and reached OUTCOME_VALIDATED; an unknown predicate `op` was treated as `in`.
5. **MEDIUM** In the frozen runner "authoritative" is a constant it assigns, not an independent source; `read_state` reports EXISTS if either version is found; ABSENT never checks that the exception names the requested object; the source-integrity predicate compares hashes within one response; the name predicate is a substring test; a third party creating the object between prewrite and readback would be counted as this mission's commit.
6. **MEDIUM** The published authorization phrase is not marked consumed and does not bind the model hash.
7. **MEDIUM** The verifier pinned 12 of 53 baseline files (41 unpinned), passed when the `v1.9.0` tag was missing, and skipped `tools/` in the path check; the reviewer edited an unpinned register and regenerated the sums and the verifier passed.
8. **LOW** `authorize()` consumed check was dead code; a bad outcome receipt left the mission stuck in OUTCOME_VALIDATION_PENDING; `decide_commit` ignored `commit_state`.
9. **LOW** Four mutants were detected only by an uncaught exception.
10. **LOW** The erratum says "hash-linked"; two R1 registers are stale and not marked superseded.

## Other reviewer results
- **Chain:** 14 labels and order match the model and the reviewer's own typed list; `complete()` rejected 15 bad completion receipts without state change; missing upstream links rejected 13/13; stale-hash corruption 13/13; attacker-recomputed hashes accepted 13/13 (object_hash is not authentication).
- **Mutation:** all 15 repo mutants detected and reproducible; of 14 reviewer-added mutants 9 detected, 5 survived (2 real test gaps: readback contract binding, commit bound to readback; 2 equivalent; 1 partly redundant).
- **Frozen evidence:** the 13-file diff touched no historical R2.0A-C evidence, freeze, packet, runner or C report; all 12 pinned hashes match `git show 6f992c6:<path>`; 41 other baseline files were unpinned.
- **Live evidence:** 13/14 confirmed; links 1-9 equal the freeze objects, links 10-13 rebuilt exactly from fixed ids and the published readback. Scope OBSERVED for one DDLS on TRL_EN; active/inactive both EXISTS proves nothing about activation or package, and the reports say so.
- **Security:** no bearer token, JWT, private key or protected-token value in the tree at the target commit or in the 10 commits since `v1.9.0` (pre-`v1.9.0` history not exhaustively searched by the reviewer). The token pasted into chat earlier still needs OWNER-CONTROLLED rotation; nothing was rotated or reused. The credential helper is git-ignored only through case-insensitive matching on this filesystem.
- **Portability:** offline verifier passes in place and with `--clone` (Windows, Python 3.13); other operating systems not tested; live tooling tied to Windows DPAPI and owner-workspace paths.
- **Release readiness:** not ready; do not merge or describe the model as qualified until the HIGH findings are fixed and re-reviewed.

## Reviewer's next required proof
1. Make `complete()` re-verify object relations. 2. Make failed calls change nothing. 3. Verify the lease hash in `resume()` and stop it accepting downstream evidence. 4. Reject empty predicate lists and unknown ops. 5. Add tests and mutants for those, plus the two surviving readback gaps, and record which test failed. 6. Pin the whole baseline tree. 7. Mark the published authorization consumed and bind the model hash in the next freeze. 8. Re-run independent review. 9. In a later frozen study, emit link 14 live and add a second readback source.
