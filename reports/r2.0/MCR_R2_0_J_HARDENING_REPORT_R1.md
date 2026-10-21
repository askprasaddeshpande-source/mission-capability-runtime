# MCR R2.0J Hardening Report R1 (response to independent review 3)

Baseline for this work: `a381a22` (reviewed, verdict HOLD). Inputs: `reports/r2.0/MCR_R2_0_INDEPENDENT_QUALIFICATION_R3_FINDINGS.md`. Scope: offline model, test, harness and verifier changes. SAP writes 0, live executions 0, no credential touched, no PR. The three HIGH/MEDIUM findings were reproduced by the implementer before any change (a budget with `retries=1` reached EXECUTION_STARTED through `resume()`; two real processes sharing one ledger file both "sent" the same mutation; COMPENSATED was reached by re-presenting the forward readback).

**This report does not claim the HOLD is lifted.** A fresh independent re-review of the resulting commit is required.

## Finding-by-finding response
| # | Finding | Status | What changed | Evidence |
|---|---|---|---|---|
| F1 | `resume()` skipped the gates | FIXED | `resume()` now re-runs the real `context_ready`, `authorize`, `bind` and `prewrite_validate` on re-presented evidence (all ten upstream objects are required), so a resumed mission is refused exactly where a fresh one is; the explicit duplicate checks were removed; a durable ledger is required unless explicitly waived for tests | 17 gate-by-gate resume tests, 5 missing-slot tests, kind/id/mutation-id/receipt tests; reproduction no longer succeeds |
| F2 | ledger unsafe across processes and per authority | FIXED within stated limits | OS file lock plus re-read on every operation; per-authority send limit enforced at the ledger; JSON lines with CRC (colons, unicode and escaped characters safe, control characters rejected); torn tail ignored and truncated, corrupt or non-UTF-8 content fails closed; flush and fsync before returning; unusable path fails at construction | four real processes race: exactly one wins; two ledger objects, two missions on one authority, torn/corrupt/CRC/UTF-8 files, fsync and append mode, lock timeout and lock wait: 22 tests. **Limits documented in contract R4 section 2** (different files, volatile ledger, network filesystems, power loss, POSIX path untested) |
| F3 | COMPENSATED without any compensating action | FIXED | `begin_compensation` (ledger entry bound to the grant, once only), an execution receipt bound to the grant, a post readback that is authoritative, correlated, internally consistent and distinct from the forward readback in hash and observed state; authoritative forward readback required for preconditions | 36 compensation tests (across R2.0I and R2.0J) |
| F4 | gate weaker than COMPLETE for truthy `frozen`, NaN or bool counts | FIXED | counts must be real non-negative ints; `frozen`, `single_use` exactly True; `expansion_allowed` exactly False; relations R09 strict | tests and mutants |
| F5 | readback existence vs `observed.exists`; TypeError leaks | FIXED | existence must agree with `observed.exists` (gate and new relation R50); guard methods turn malformed-argument exceptions into GuardError with state unchanged | tests |
| F6 | verifier gaps | FIXED / PARTIAL | secret patterns now cover JSON-quoted keys, yaml and extension-less files (all files in the roots are scanned), base64 Bearer, Basic, unquoted `password=`, `x-api-key`, UTF-16; UNC share paths and profile environment-variable paths-style paths; tracked `*.pyc` or `__pycache__` fails even with the anchor; empty or malformed `--expect-sums-sha256` fails; tracked files must equal the sums list; reviewed-revision and I-era pins; `--quick` (skips only the mutation re-run and says so) for fast checks. **Limit:** a verifier in the repository it checks is self-attestation; only the external anchor helps | 8 R2.0I attacks plus 13 new attack scenarios (`run_r2_verifier_attacks.py`), see test matrix |
| F7 | mutation granularity | FIXED / PARTIAL | the harness now also generates clause-level and operator mutants from the syntax tree (comparison flips, clause drops, `not` removal, `+`/`-` swaps) for the whole model, plus the guard, relation and special mutants | see Results; every survivor listed with a reason |

## Results (actual; `evidence/r2.0/MCR_R2_0_J_TEST_MATRIX_R1.json`)
- Model validator: **391 checks** in 15 groups, 0 failed (R1 74, R2.0G 96, R2.0H 133, R2.0I 283, now 391; the new HARDENING_R2_0J group has 105).
- Mutation check: **513 mutants** generated from the source (342 syntax-tree clause/operator, 101 guard, 49 relation, 21 special), all applied. **267 detected by an assertion; 240 detected because the validator could not run to completion** (the mutant broke a legitimate flow its own fixtures depend on: strong evidence the behaviour matters, but not a targeted assertion). **6 survivors, all equivalent mutants with a stated reason** (identical object hash implies identical content; a tuple is guaranteed before the key check; `None` is never in a list of strings; a CRC of a non-string raises and is caught; `>` versus `>=` on a float clock). 0 unexplained survivors. Earlier counts ("0 survivors" at 159 mutants) were true only at whole-condition granularity.
- Local D/E scenarios: all checks PASS, including the stale-lease and forged-lease scenarios and the new compensation flow.
- Frozen R2.0C runner vs mock provider: 6/6 scenarios reproduce the frozen outcomes under the stricter model; the runner file is byte-identical to baseline. The model-dependent equivalence remains: "runner unchanged" means source bytes only.

## Remaining gaps (not closed)
1. Receipt and lease provenance (no signatures): owner declined; a self-consistent forged chain labelled authoritative is accepted.
2. The frozen runner's readback weaknesses (label "authoritative", either-version EXISTS, ABSENT without object identity, intra-response integrity, substring predicate, third-party race), activation and package unproven.
3. The ledger guarantees stop at one local filesystem with working locks; the POSIX locking path is untested; the frozen runner uses its own lock file.
4. One live run; link 14 never observed live; raw live evidence outside Git; unenforced fields (`expires_at`, `roles`, `tenant`, `intent.expected_outcome_hash`); the model hash is not yet bound into authorization phrases (requirement for the next freeze).
5. The verifier is self-attestation unless run with an external `--expect-sums-sha256`.
6. Mutation evidence: 240 of 513 detections are validator-crash rather than assertion; 6 equivalent survivors are justified by argument, not by proof.
7. A 64-hex constant in a pre-v1.9.0 script (reported by reviews 2 and 3) is unexplained here; it lives in frozen R1.x evidence.

## Recommendation
Request a fresh independent re-review of the resulting commit. Until it returns, the verdict remains HOLD. Do not open the consolidated PR yet.
