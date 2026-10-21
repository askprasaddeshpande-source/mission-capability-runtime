# MCR R2.0 Independent Qualification R4: Reviewer Findings (as received)

Target commit `f6e79a451975f3c71e3f226e0f98245bf24a4482` (R2.0J). Reviewer: a fresh agent instance, separate from the implementing session and from reviews 1 to 3, read-only in a new clean clone, offline and `--mock` only, no credential or live-evidence access, working under an owner-set release-gate brief (GO / GO_WITH_DOCUMENTED_GAPS / HOLD). This file records its final reply condensed, without changing any finding or the verdict. Its full report stays in the owner workspace (not published).

**INDEPENDENT_REVIEW_VERDICT = HOLD. RELEASE_GATE = HOLD** (do not open the consolidated PR yet; after the repair list and a short re-review, one consolidated PR is reasonable, with separate owner authorization).

## Coverage limits stated by the reviewer
It did not read all 1,191 validator lines or `run_r2_local_scenarios.py` line by line (the scenarios were checked through their byte-identical reproduced result). It was not given the earlier review numbering, so it tested the finding classes instead of mapping N1..N10.

## What held
Source reproduces; the full verifier passed from a clean clone with the external anchor (every field true); validator output byte-identical to the archived result; counts add up (25 schemas, 20 states, 14 links, 49 relations, 513 = 342+101+49+21 and 513 = 267+240+6). Frozen evidence recomputed at five commits: all 73 pins correct, the runner `A73F4647...` unchanged, tag `v1.9.0` at `9c5105f`. On 30,000 random multi-field forgeries with recomputed hashes every COMPLETE reached was explained by a field the model does not enforce; all 49 relation mutants caught by assertion. Concurrency: with 8 and 10 real processes through full `begin_execution`, exactly the budgeted number of sends won; Windows `msvcrt` locking behaved as claimed (empty file, killed holder, timeout raises GuardError, torn tails, bad CRCs, 1 MB ids). F1 fixed. 5,760 junk-argument calls to the guard methods produced zero non-GuardError exceptions and zero state changes. Six mock scenarios and the 13/14 live result preserved; the stricter model cannot change what the frozen runner does against the real provider (volatile ledger, consistent `observed.exists`, its own lock file). No secrets in the tree or any ref (21 commits scanned). Hypothesis classifications supported, none PROVEN.

## What failed
1. **N1 MEDIUM-HIGH:** `@atomic` snapshotted with no lock (`mcr_r2_model.py:415-428`). With two threads on one Mission the loser's rollback erased the winner's EXECUTION_STARTED: the winner was told SENT and the ledger recorded it, but the Mission showed PREWRITE_VALIDATED with `mutations_sent=0`, and `fail_before_mutation` was then accepted. Thread safety was not documented.
2. **N2 MEDIUM:** `scope` not type-checked: with string scopes the capability `"delete"` under scope `"delete_everything"` reached COMPLETE (reproduced independently by the implementer through BOUND).
3. **N3 MEDIUM:** COMPENSATED reached with a tautological grant; with the forward readback plus one extra key in `observed`; with a `CALL_SENT_NO_RESPONSE` compensating receipt. The distinctness check was only syntactic.
4. **N4 MEDIUM:** deleting, truncating or restoring the ledger file let a second send through (reproduced independently for deletion); undisclosed, and the J report marked F2 FIXED.
5. **N5 LOW-MEDIUM:** a hash-valid forged lease resumed against an empty ledger reached COMPLETE with 0 ledger bytes.
6. **N6 LOW:** non-GuardError leaks in `resume()` (lease missing optional fields) and the direct ledger API (OSError, TypeError, UnicodeEncodeError); `limit=nan` accepted as unlimited; `consume("ab")` accepted as a key.
7. **N7 LOW:** `retries=0.0` and `-0.0` accepted although the contract said the integer 0; ids compared with `==`.
8. **N8 LOW:** verifier secret-scan evasions (each verified with a staged file and regenerated sums): a file starting with a NUL byte and of even length; a UTF-32 file; `secret_key =` assignments; any file outside the five R2.0 folders. No secret was actually present.
9. **N9 LOW:** four test gaps from the reviewer's own 32 mutants (16 caught by assertion, 7 by crash only, 9 survived): resume-to-COMPLETE with the synthetic COMMIT_UNKNOWN receipt, `flush()` removal, resume with `readback_contract` missing, resume with more than one consumed key.
10. **N10 LOW:** wording: status R6 said "513 all detected (267+240)" and then listed 6 survivors; the summary said the verifier was attacked in 8 scenarios while the matrix said 26 and pointed to status R4 instead of R6; the J report marked F3 and F4 FIXED although they were partial.

## Mutation assessment
267 by assertion; 240 only because the validator's own fixtures crashed ("honest and acceptable as evidence that behavior changed, but not a targeted test"); 6 survivors, each equivalence argument checked and correct, two resting on current call-graph facts. The harness covers operator and clause classes only.

## Prior-finding status as judged by the reviewer
F1 FIXED (minor residual: KeyError leak on a lease missing optional fields). F2 PARTIAL (absent or truncated ledger undisclosed). F3 PARTIAL. F4 PARTIAL. F5 PARTIAL (guard methods clean; `resume()` and the direct ledger API leaked). F6 PARTIAL (25 of 26 archived attack results reproduce; A7 cannot run in a clone; new evasions). F7 PARTIAL.

## Bounded repair scope (reviewer, ordered)
1. Serialize guard methods per Mission, and make `fail_*` consult the ledger. 2. Validate types for `scope`, `capability` and ids; strict equality for id relations. 3. Require that the compensation goal is not already satisfied by the forward readback; reject no-response compensating receipts for COMPENSATED. 4. Add a ledger creation marker or a lease-recorded ledger digest; at minimum disclose deletion and restore. 5. Convert `resume()` and direct-ledger exceptions to GuardError; require `retries` exactly the integer 0; state that COMPLETE on a resumed mission trusts the lease. 6. Fix the scanner evasions, add the four mutant-derived tests, and correct the R6 and summary wording in new files.

## Security
No bearer token, JWT, private key, protected-token blob, DPAPI header or long labelled secret in the f6e79a4 tree or any added line of the 21 commits. Rotation of the pasted ADT MCP token remains pending (owner declined). Drive paths appear only in the whitelisted frozen runner and probe defaults and the authorization packet; older R1.x evidence has a few drive-letter and profile paths, pre-existing and outside R2.0.
