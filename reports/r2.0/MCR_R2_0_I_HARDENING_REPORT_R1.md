# MCR R2.0I Hardening Report R1 (response to independent review 2)

Baseline for this work: `b5cca1f` (reviewed, verdict HOLD). Inputs: `reports/r2.0/MCR_R2_0_INDEPENDENT_QUALIFICATION_R2_FINDINGS.md`. Scope: offline model, test, harness and verifier changes. SAP writes 0, live executions 0, no credential touched, no PR. Both HIGH findings were reproduced by the implementer before any change (a tampered delegation reached EXECUTION_STARTED; a stale lease allowed a second send).

**This report does not claim the HOLD is lifted.** An independent re-review of the resulting commit is required.

## Finding-by-finding response
| # | Finding | Status | What changed | Evidence |
|---|---|---|---|---|
| N1 | send-time gates do not verify evidence | FIXED | every guard method verifies kind and hash of each presented object and stores a deep copy; gate-level relations added (delegation to principal, single-use authority, budget equals mission limit, capability matches provider tool and identity, mission and mutation-id shape on transaction and contract, checkpoint pins and budget) | 44 gate tests; the generated guard mutants for each check are detected |
| N2 | stale lease replays the send | FIXED (within the ledger contract) | `ReplayLedger` (append-only, file-backed with fsync, never rolled back) records each send before the state moves; `resume()` takes the UNION of lease and ledger, requires the ledger and re-presented evidence, binds the mission id and the original budget, validates integer budget fields and consumed ids; post-send resume always restarts in COMMIT_STATE_UNKNOWN | stale-lease scenario (local D/E result R3), file-backed restart test, 23 resume/ledger tests. **Limit:** protection exists only if a durable ledger is passed to every Mission and resume; a process-local ledger protects that process only |
| N3, N3b | terminal states reachable on unverified evidence; compensation ungated | FIXED | COMMITTED, OUTCOME_VALIDATED and COMPENSATED are entered only on verified objects; compensation verifies grant, receipt and post readback, correlates the readback to the mission, forbids a capability inside the forward scope, requires predicate preconditions that PASS against the forward readback | 18 tests (16 compensation, 2 terminal-state) |
| N4 | unbound relations, 12 of 18 relations untested | FIXED / DOCUMENTED | 48 named relations (R01-R49) plus the predicate check, each with its own violation recipe (a consistent forgery that breaks only that relation) and an automatic mutant; added: single-use, provider/capability, budget limits at completion, checkpoint budget. **Not enforced, now stated:** `expires_at`, `roles`, `tenant`, `intent.expected_outcome_hash` (the frozen runner sets the placeholder "PENDING") | `chain contract R3` section 5; 48 recipe tests |
| N5 | tautological predicates; `ne`/`in` untested | PARTIAL | equality is type-strict (True is not 1), `in` needs a non-empty collection, precondition and goal predicates are validated, `ne`/`in`/`eq` have tests and mutants. **Not fixable here:** a tautological predicate is an authoring error; predicates are frozen by the author before the mutation | tests; documented |
| N6 | caller aliasing | FIXED | deep copy at acceptance | test |
| N7, N8 | rollback aliasing; non-integer budget; unbound mission limit; substring mutation ids | FIXED (rollback aliasing is a stated low-risk property) | integer checks; mission limit bound to the budget at authorize and chain (R10); mutation ids must be a non-empty list of strings | tests |
| N9 | verifier gaps | FIXED / PARTIAL | forward-slash drive paths, JWT, `sk-` and quoted secret patterns; the credential helper is scanned when present; 55 plus 9 historical files pinned; reviewed-revision pins for the model-side files; `--expect-sums-sha256` lets a reviewer check the sums file against a value recorded outside the repository. **Limit:** a verifier that lives in the repository it checks is self-attestation; only the external anchor helps | verifier negative tests (see test matrix) |
| N10 | authorization phrase not revoked in code | DOCUMENTED | consumed notice already filed; the lock file and the ledger are the code-level guards for a rerun | n/a |

## Corrections to earlier statements (honesty items)
- The R2.0H report said four mutants were "crash-only" in R2.0G and that one mutant "initially survived". The repository does not contain the run that produced those numbers; treat them as development observations, not reproducible evidence.
- Status R4 said the HIGH defects found by review 1 were fixed. That was true for those defects but review 2 found others; status R5 supersedes it.
- Status R4 said H47 means the model "validates all 14 links relationally and rejects forged or recomputed chains". That was too strong at the time and is corrected in status R5.

## Results (actual; machine-readable `evidence/r2.0/MCR_R2_0_I_TEST_MATRIX_R1.json`)
- Model validator: 283 checks in 14 groups, 0 failed (R1 74, R2.0G 96, R2.0H 133, now 283).
- Mutation check: 159 mutants generated from the source (90 guards, 48 relations, 21 special), all applied, all detected, 0 survivors. 156 detected by assertion. 3 are detected only because the validator's own fixtures can no longer run (each listed with a reason in the result). 6 mutants survived the first generated run; each exposed a real test gap and was closed by a new test, not by an exemption.
- Local D/E scenarios: all checks PASS, including a new stale-lease scenario.
- Frozen R2.0C runner vs mock provider: 6/6 scenarios reproduce the frozen outcomes under the stricter model; the runner file is byte-identical to baseline.

## Remaining gaps (not closed)
1. Receipt and lease provenance (no signatures): owner declined; a self-consistent forged chain labelled authoritative is accepted.
2. The frozen runner's readback weaknesses (label "authoritative", either-version EXISTS, ABSENT without object identity, intra-response integrity, substring predicate, third-party race), activation and package unproven.
3. Ledger protection depends on deployment passing one durable ledger; the frozen R2.0C runner uses its own lock file, not this ledger.
4. One live run; link 14 never observed live; raw live evidence outside Git; unenforced fields listed above.
5. Verifier is self-attestation unless run with an external `--expect-sums-sha256`.
6. A 64-hex constant in a pre-v1.9.0 script (reported by review 2 for owner confirmation) is unexplained here; it appears in R1.x frozen evidence which this lineage does not touch.

## Recommendation
Request a fresh independent re-review of the resulting commit. Until it returns, the verdict remains HOLD. Do not open the consolidated PR yet.
