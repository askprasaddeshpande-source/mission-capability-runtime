# MCR R2.0 Independent Qualification R2: Reviewer Findings (as received)

Target commit `b5cca1f092dcbf3e1bda54b93b53f5b067c3efe1` (R2.0H). Reviewer: a fresh agent instance, separate from the implementing session and from review 1, working read-only in a new clean clone, offline and `--mock` only, no credential or live-evidence access. This file records its final reply condensed, without changing any finding or the verdict. Its full report and scratch scripts stay in the owner workspace (not published).

**INDEPENDENT_REVIEW_VERDICT = HOLD**

## What held
`Mission.complete()` was much stronger than at `8a383b6`: every missing, wrong-kind and stale-hash case on all 15 slots and the 8 malformed or tampered completion-receipt forms tried were rejected. Atomicity held (all 17 mutating methods; injected exceptions rolled back). The 14-link order matched. The live 13/14 result, frozen evidence (all 53 baseline files compared; the 5 changed ones legitimate), the runner equivalence (6 mock scenarios) and the secret scan (no token in the tree or any ref) all held.

## What failed (public API, evidence built with `make()` only)
1. **HIGH N1:** send-time gates (`authorize`, `bind`, `prewrite_validate`, `begin_execution`) never verified evidence kind or hash. A delegation with widened scope and a stale hash reached EXECUTION_STARTED with a send; a transaction envelope with an injected mutation id let a send happen. `complete()` rejected both, but only after the send.
2. **HIGH N2:** a genuine but stale lease (taken at PREWRITE_VALIDATED, then the send, then `resume(old_lease)`) allowed a second send of the same mutation; there was no durable replay ledger; `resume(post-send lease, None)` returned PLANNED.
3. **MEDIUM-HIGH N3/N3b:** COMPENSATED, COMMITTED and OUTCOME_VALIDATED were reachable on hand-built unhashed dictionaries, including a readback from a foreign transaction; a tampered grant was accepted; preconditions were never evaluated.
4. **MEDIUM N4:** several relations unbound: `expires_at`, `single_use`, `roles`, `tenant`, `preconditions`, `intent.expected_outcome_hash`, provider against `capability.provider_ref`; budget/count relations not rechecked at completion or on resume; rehashed `intent`, `capability`, `provider` or `checkpoint` accepted by `complete()`.
5. **MEDIUM N5:** non-empty tautological predicates reach OUTCOME_VALIDATED; predicate `ne` and `in` untested.
6. **LOW-MEDIUM N6:** the model kept caller evidence by reference (alias rewrite and re-hash before `complete()`).
7. **LOW N7/N8:** rollback replaces container objects; non-integer `remaining_budget` raised TypeError; the Mission budget argument was unbound to the MutationBudget evidence; mutation-id membership was a substring test if `mutation_ids` was a string.
8. **MEDIUM-LOW N9:** verifier gaps: forward-slash drive paths and raw JWT/`sk-` tokens pass; the credential helper file is skipped by sums and scan; a new unpinned R2.0 file plus regenerated sums passes; the model, validator, harness and verifier are not pinned (replace two relations with `True`, regenerate sums: PASS).
9. **LOW N10:** the authorization phrase is not revoked in code.

## Mutation result
Repo harness: 35/35 detected by assertion, reproduced. Reviewer's own set: 123 mutants (every `if ... raise GuardError` guard removed, each of the 18 relations replaced by `True`, 25 hand-written): 64 killed by assertion, 13 by crash only, **46 survived** (12 of the 18 relations, the checkpoint-pin checks in `prewrite_validate`, the `authorize` mission and count guards, the `bind` authority check, the budget-exhausted check, about eight `resume` guards, predicate `ne`/`in`).

## Other
- Prior findings: 1 PARTIAL, 2 FIXED, 3 FIXED for COMPLETE (PARTIAL on relation completeness and other terminal states), 4 PARTIAL, 5 DEFERRED-ACCEPTED, 6 PARTIAL, 7 PARTIAL, 8 FIXED, 9 PARTIAL.
- Hypothesis wording: no promotion, but H47 ("validates all 14 links relationally and rejects forged or recomputed chains") and H44 ("forged or inflated lease rejected") overreached, and status R4 said the HIGH defects were fixed.
- Report honesty: two R2.0G claims in the hardening report could not be reproduced ("4 crash-only", "one mutant initially survived").
- Security: no bearer token, JWT, private key, DPAPI blob prefix or cloud key in the tree or in any ref (searched added lines in 11 and 16 refs, 534 files and nested zip members; patterns only; a bare opaque token of unknown format would go undetected). One 64-hex constant assigned to a variable named `token` in a pre-v1.9.0 script inside a nested R1.8 zip recurs in 4 other published places and looks like a public hash, but the reviewer asked the owner to confirm what it is. Owner-controlled rotation of the pasted token is still recommended (owner declined; see status).
- Portability: only Windows with Python 3.13 tested.
- Release readiness: not ready; "a bounded offline research prototype with one scoped live observation, whose COMPLETE gate is hardened and whose other terminal states, send-time gates and replay are not".

## Reviewer's next required proof
1. Verify kind and hash of every object at the gate that consumes it, before any irreversible step. 2. Bind compensation to transaction, mutation and grant target; evaluate preconditions. 3. Add a persisted replay ledger or epoch outside the lease, with a stale-lease and crash-before-persist test. 4. Bind or explicitly drop the unenforced fields; add a killing test for each of the 18 relations, the `resume`, `authorize`, `bind` and prewrite-pin guards, and `ne`/`in`. 5. Pin or sign the model, validator, harness and verifier; fix the verifier regexes and filename skip. 6. Correct the R4 wording, then run a fresh independent re-review.
