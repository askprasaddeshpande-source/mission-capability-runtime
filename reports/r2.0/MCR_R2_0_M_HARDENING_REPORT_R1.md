# MCR R2.0M Hardening Report R1 (cleanup after independent review 5)

Baseline: `681f77a` (review 5 verdict PASS_WITH_GAPS, release gate GO_WITH_DOCUMENTED_GAPS). Scope: offline model, test, harness and verifier changes only. SAP writes 0, live executions 0, no credential touched, no PR. The owner chose to clean up the findings (F1 to F7) and the missing tests, re-verify, and request a short re-review before any PR decision.

**This report does not claim an independent verdict.** A short re-review of the resulting commit is still required.

## Finding-by-finding response
| # | Finding | Status | What changed | Evidence |
|---|---|---|---|---|
| F1 | in-memory `ReplayLedger` shared by several Mission objects was not thread-safe (double send; `Set changed size during iteration`) | FIXED | every ledger operation (`has`, `for_authority`, `consume`, file sync) runs under a per-ledger re-entrant lock | 60 rounds x 8 threads on the same key, per-authority limit, writer/reader race, eight Missions on one volatile ledger send exactly once |
| F2 | ledger path `""` looked durable but behaved as volatile; `expected_id` accepted without a file | FIXED | path must be a non-empty string or `None`; `expected_id` needs a file-backed ledger | tests for `""`, int, bytes, list, float, bool, and `expected_id` with no file |
| F3 | compensation wording overstated the goal-already-holds check | FIXED (wording) | contract R6 section 3 states the residual no-provenance case | document |
| F4 | readback contract not tied to the bound provider | FIXED | `provider_ref` must start with `<provider_id>::` at prewrite (so also on resume) and as relation R51 at COMPLETE | refusals for another provider, missing separator, prefix-only id; resume refusal; matching prefix accepted; R51 recipe and mutant |
| F5 | mutation wording "all detected" next to 6 survivors | FIXED | status R8 and summary state assertion / crash / hang / explained-equivalent counts separately | status R8 |
| F6 | mutation JSON labels and classification | FIXED | a crash needs a Python traceback; a kill or timeout without one is `inconclusive`, retried once and never counted as detection; the same mutant timing out twice is classed `hang` (detected, listed separately); explained survivors keyed by code fragment | harness; one mutant (removing the lock-wait timeout) is detected by hang |
| F7 | scanner false negatives (short values, hex values, key blocks, token shapes, URL user-info) and false positives | FIXED with residual limits | see contract R6 section 5 | 23 payload checks all as expected; 0 hits over the tracked tree |
| T | missing tests named by the reviewer | ADDED | history unchanged after a refused call, one entry after success, late-failure rollback restores history, default lock timeout outlasts contention, resume audit entry, resume first-sorted-key fallback | HARDENING_R2_0M group |

## Results (actual; `evidence/r2.0/MCR_R2_0_M_TEST_MATRIX_R1.json`)
- Model validator: **486 checks** in 17 groups, 0 failed (R1 74, G 96, H 133, I 283, J 391, L 466, M 486).
- Mutation check (`MCR_R2_0_M_MUTATION_CHECK_R6.json`): **607 mutants** generated from source (417 syntax-tree, 117 guard, 50 relation, 23 special), all applied. **298 detected by an assertion; 302 detected because the validator could not run to completion; 1 detected by hang; 6 survivors, all justified equivalents; 0 unexplained; 0 inconclusive.**
- Local D/E scenarios: all PASS (`MCR_R2_0_DE_LOCAL_SCENARIOS_RESULT_R6.json`). Frozen R2.0C runner vs mock provider: 6/6 reproduce the frozen outcomes; the runner file is unchanged.
- Chain relations: 50 named plus the predicate check.

## Remaining gaps (not closed)
0. The 6 verifier attack scenarios A13a to A13f have no archived full-verifier run: the run was stopped twice by low system memory; restart only on the owner's request. The scanner payload checks in the matrix cover the same behaviours directly.
1. Receipt and lease provenance (no signatures): owner declined.
2. The frozen runner's readback weaknesses; activation and package unproven.
3. The ledger: deletion without a pinned id, restore of an older copy, one local filesystem, POSIX locking untested, power-loss durability untested.
4. One live run; link 14 never observed live; raw live evidence outside Git; unenforced fields (`expires_at`, `roles`, `tenant`, `intent.expected_outcome_hash`, `readback.activation`, `readback_contract.checks`).
5. The verifier is self-attestation unless run with an external `--expect-sums-sha256`.
6. 302 of 607 mutant detections are validator-crash, weaker than an assertion; the 6 survivors are justified by argument.
7. Token rotation and the leftover test view `ZC_MCR20C_7A3F91D2` were declined by the owner (accepted risks).

## Recommendation
Request a short independent re-review of the resulting commit. Do not open the consolidated PR without that and without separate owner authorization.
