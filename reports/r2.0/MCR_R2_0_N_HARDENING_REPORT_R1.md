# MCR R2.0N Hardening Report R1 (final bounded hardening after independent review 6)

Baseline: `212804f` (review 6 verdict GO_WITH_DOCUMENTED_GAPS). Scope: the five findings of review 6 and the reporting corrections it asked for; no architecture change. SAP writes 0, live runs 0, no credential touched, no PR, no merge.

**This report does not claim an independent verdict on the R2.0N changes.** A targeted review of the R2.0N diff follows this commit.

## Finding-by-finding response
| # | Finding | Status | What changed | Evidence |
|---|---|---|---|---|
| N1 | the in-memory ledger lock fix had no effective regression guard (removing the lock left the validator passing) | FIXED | deterministic rendezvous tests (a first thread is held inside the key set until a second thread reaches it) plus a spy-set stress test; named mutants: lock body removed, lock decorator removed from `has`, `for_authority`, `consume` | all four mutants are detected by an assertion, three repeated probes; a negative-control test proves the detector itself fires |
| N2 | NUL and `CON` ledger paths leaked `ValueError` | FIXED | NUL characters and Windows device names in any path component raise GuardError on every platform; `_io_guard` also converts `ValueError` and `TypeError`; look-alike names (`console.txt`, `CONFIG`) stay legal | 7 refusal tests, one acceptance test, one conversion test, one mutant |
| N3 | scanner missed the `github_pat_` shape the contract claimed | FIXED, limits documented | added `github_pat_`, `npm_`, `AIza`, Stripe `sk_live_`/`rk_live_`, Azure `AccountKey=`; contract R7 section 4 lists the patterns intentionally not detected | synthetic payload checks in the test matrix (flagged and documented-unsupported cases are separate) |
| N4 | R51 is a literal prefix test | DOCUMENTED | contract R7 section 2: empty tail and empty provider id accepted by design | test `r51_accepts_an_empty_tail_after_the_separator` |
| N5 | failed compensating call | DOCUMENTED, reviewer wording corrected | the review said the failure was terminal. It is not: the failed report is refused and nothing changes, but a later success report is accepted, and the model does not gate a second provider call (contract R7 section 3) | 4 tests |

## Corrections and notes
- The reviewer's N5 statement ("no retry path") was imprecise; the behaviour was checked by probe before it was documented.
- The two `ledger_consume_file_not_thread_locked` and `ledger_sync_not_thread_locked` mutants were tried and removed: both methods run under the OS file lock behind a locked caller, so their detection depended on timing and would have made the mutation result non-reproducible. Contract R7 section 5 states that these two decorators have no mutant and no test.
- The mutation harness gave two mutants on one line the same name, which made the per-kind crash count one too low. Names are now unique (`#2` suffix); the counts below reconcile (assertion + crash + hang + survivors = total).

## Results (actual; `evidence/r2.0/MCR_R2_0_N_TEST_MATRIX_R1.json`)
- Model validator: **510 checks** in 18 groups, 0 failed (R1 74, G 96, H 133, I 283, J 391, L 466, M 486, N 510).
- Mutation check (`MCR_R2_0_N_MUTATION_CHECK_R7.json`): 619 generated mutants (422 syntax-tree, 119 guard, 50 relation, 28 special): 305 detected by an assertion, 307 because the validator's own fixtures could no longer run, 1 by hang, 6 survivors that are justified equivalents, 0 unexplained, 0 inconclusive.
- Local D/E scenarios: all PASS (`MCR_R2_0_DE_LOCAL_SCENARIOS_RESULT_R7.json`). Frozen R2.0C runner vs mock provider: 6/6 reproduce the frozen outcomes; the runner file is unchanged.

## Remaining gaps (not closed)
0. **A13a to A13f full-verifier attack scenarios are UNVERIFIED**: the run was stopped twice by low system memory and is not repeated without owner authorization. The scanner payload checks in the matrix cover the same behaviours directly.
1. Receipt and lease provenance (no signatures): owner declined.
2. **ADT bearer token rotation: owner declined; this is an accepted risk.** The token was pasted in an earlier chat message. The leftover test CDS view `ZC_MCR20C_7A3F91D2` was also left in place at the owner's decision.
3. The frozen runner's readback weaknesses; activation and package unproven.
4. The ledger: deletion without a pinned id, restore of an older copy, one local filesystem, POSIX locking untested, power-loss durability untested. The `_consume_file` and `_sync` thread-lock decorators have no mutant and no test (contract R7 section 5).
5. One live run; link 14 never observed live; raw live evidence outside Git; unenforced fields (`expires_at`, `roles`, `tenant`, `intent.expected_outcome_hash`, `readback.activation`, `readback_contract.checks`).
6. The verifier is self-attestation unless run with an external `--expect-sums-sha256`.
7. About half of the mutant detections are validator-crash rather than assertion; the survivors are justified by argument.
8. A second provider call after a failed compensating call is not limited by the model (contract R7 section 3).
9. The scanner is a heuristic with documented unsupported patterns (contract R7 section 4).

## Recommendation
Targeted independent review of the R2.0N diff, then owner review for the single consolidated PR. Do not open the PR without separate owner authorization.
