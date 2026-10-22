# MCR 3.0 Qualification Report R1

Release line 3.0.0, an **offline engineering release candidate**. Baseline `main` at `fd865c67c053431dc33297a0df2a3c9a02fd51fe` (MCR R2.0, PR #4). Everything here is SYNTHETIC/LOCAL evidence. No SAP write, no live run, no network call, no production signing key, no capability promoted to production trust.

## 0. Which commit each result belongs to
- The final mutation run (section 3) was executed on commit `25577dd`.
- The verifier attack run (section 6) was executed on commit `6188d3d`; the files it exercises (`verify_mcr3.py`, `mcr3_scan.py`, the attack script) are unchanged since.
- The full test run, the fresh-clone verification with the external sums anchor and the targeted re-review refer to the final commit named in the pull request. Between those commits the only code changes are an adapter-registry simplification (`rollback` now just calls `mode()`), test additions and the mutation harness's explanation list; the rest is evidence, sums and these reports.
- Independent review 8 examined commit `dab77be`; its fixes are listed in section 9.

## 1. What was built
See `architecture/mcr3/MCR_3_0_ARCHITECTURE_AND_DECISION_RECORD_R1.md` (decision and module map), `MCR_3_0_SECURITY_AND_AUTHORITY_CONTRACT_R1.md`, `contracts/evidence-v1/README.md`, `CLAUDE_MODS_CHANGE_PACKET_R1.md` and `reports/mcr3/MCR_3_0_GAP_CLOSURE_MATRIX_R1.md`.

## 2. Test results (reproduce with `python tools/mcr3/run_mcr3_tests.py`)
**1,603 checks in 9 suites, 0 failed** (tens of seconds sequentially, about 30 to 50 s on the qualifying machine, peak 38 MB in any one suite; raw records in `evidence/mcr3/MCR3_RESULT_*_R1.json`, resource record `MCR3_RESOURCE_USE_R1.json`).
| Suite | Checks | What it holds |
|---|---|---|
| inherited_r2 | 519 | the R2.0 validator re-run against the 3.0 model, with documented expectation changes |
| hardening | 140 | ledger path forms, expiry, binding fields, activation, compensation attempts, ledger anchor, outcome classification |
| evidence_contract | 207 | schema, examples, negative fixtures, exhaustive trust derivation (216 provenance combinations), canonical form, compatibility, migration, mini-validator, a 1,500-case hostile-input fuzz |
| provenance_authority | 115 | hash / signature / issuer / freshness / replay as separate findings with HMAC (test only), Ed25519 and SSHSIG back-ends; capability and adapter governance |
| adapters_interop | 99 | frozen-R2.0 adapter, native adapter, equivalence between them, lineage, the ten Claude Mods scenarios, `pe-event` mapping |
| evidence_chain | 54 | mission-level inconsistent-chain detection |
| readback | 34 | portable readback rules and the offline SAP-style provider |
| scanner | 109 | 27 credential shapes, encodings, false positives, documented unsupported patterns, tracked-tree scan |
| mutation_gap_tests | 296 | tests written for specific surviving mutants |
Not verified on the qualifying machine: nothing optional was missing (the `cryptography` package and `ssh-keygen` were present, so the Ed25519 and SSHSIG back-ends ran). On a machine without them those checks are recorded NOT_VERIFIED by the suites themselves.

## 3. Mutation qualification (reproduce with `python tools/mcr3/run_mcr3_mutation_check.py --jobs 3`, about 25 minutes; `evidence/mcr3/MCR3_MUTATION_CHECK_R1.json`)
**1,580 mutants generated from the source of 11 modules** (1,358 syntax-tree clause/operator, 141 guard, 53 chain relation, 28 targeted). Every mutant applied. Classification kept separate:
- **890 detected by an assertion** (a validator ran to completion and named failed checks);
- **653 detected by validator crash** (a validator died with a traceback because the mutant broke a flow its own fixtures need): weaker evidence, counted but reported as such (42% of detections; 353 of the 765 runtime-model detections);
- **1 detected by hang** (removing the lock-wait timeout);
- **36 survivors, each an explained equivalent mutant** with a stated reason in the harness (for example a clause made redundant by an earlier check, or a default that cannot differ); **0 unexplained; 0 inconclusive**.
How this went: the first full run of the new code left 190 survivors (184 unexplained); 212 targeted tests and three real defects found by them (scanner crash on a missing folder, migration silently dropping unrecognized fields, bare drive path accepted) brought it to 56, then 36, then 0 unexplained. Survivors are justified by argument, not proven equivalent. Per-module counts are in the JSON (`by_module`).
A hazard found on the way: a mutant that lets a device name through created real `NUL`/`COM3.log` files in the working folder; the harness now runs validators in a scratch directory and the strays were removed.

## 4. Other qualification evidence
- **Self-fuzzing:** 30,000+ hostile-input cases across `parse`, `migrate`, the `pe-event` mapping, the lineage store and `assess()` found four non-contract exceptions (fixed); a permanent 1,500-case fuzz is part of the suite.
- **Frozen history:** `git diff` against the baseline shows only additions under `tools/mcr3`, `architecture/mcr3`, `evidence/mcr3`, `reports/mcr3`; R1.9 tag `v1.9.0` unchanged; the archived R2.0 live result is byte-identical to the baseline (a test checks it).
- **Verifier** (`tools/mcr3/verify_mcr3.py`): sums cover every tracked file, frozen history untouched, no credential-shaped content in the tracked tree, no machine-specific paths in code, validators reproduce the archived results; `--expect-sums-sha256` pins the sums file to a value held outside the repository (without it the verifier is self-attesting).
- **Verifier attacks** (`tools/mcr3/run_mcr3_verifier_attacks.py`, sequential, throwaway clones, `--fast`): see section 6.
- **Overhead** (descriptive, one machine, `evidence/mcr3/MCR3_OVERHEAD_BENCH_R1.json`): a complete mission through the 3.0 model about 0.36 ms against 0.31 ms through the frozen R2.0 model (fixture build included); converting a complete mission to 7 events about 0.57 ms; parsing one event about 0.17 ms; assessing provenance for one event about 0.09 ms. No inference beyond this machine.

## 5. Scientific disposition
MCR 3.0 is an independently qualified **offline capability release candidate / bounded research runtime**. It does not show production behaviour for SAP or any provider. R2.0's single live observation is unchanged, its link 14 was never emitted live, its readback did not establish activation or package membership, and its evidence was not cryptographically authenticated; the 3.0 R2.0 adapter labels it HISTORICAL, unsigned and INCOMPLETE and invents nothing. No hypothesis H41 to H48 is promoted. The portable readback rules and the SAP-style provider are NOT verified live; a new SAP activation, package, independent-readback or failure-path study needs a separate live-study authorization.

## 6. Verifier attack run
22 scenarios, strictly one at a time, each in a throwaway clone of the committed HEAD, `--fast` profile (`evidence/mcr3/MCR3_VERIFIER_ATTACKS_R1.json`). **All 22 were detected for the intended reason** (the named check failed), except S07, which behaves as documented: a new unlisted file with regenerated sums passes without an external anchor and fails with one. The suite covers the six scanner attacks the R2.0 release could not finish (A13a NUL-prefixed UTF-16, A13b UTF-32, A13c `secret_key` assignment, A13d a secret outside the 3.0 folders, A13e a hex value under a secret name, A13f a secret inside a zip member), nine integrity attacks (edited file, unlisted file, edited and deleted frozen R2.0 files, a file outside the 3.0 folders, a moved `v1.9.0` tag, the documented self-attestation limit, a machine-specific path, tracked bytecode) and seven further token shapes. Resource use: one verifier process at a time, peak working set about 31 MB, 20 to 27 s per scenario. **The first run of this suite found two real scanner gaps** (A13b and A13c: letters-only values of 16 or more characters under a strong secret name were not flagged). They were fixed in `mcr3_scan.py` with regression tests, the scanner module was re-mutated, and the whole suite was re-run against the fixed commit (all 22 detected). The frozen R2.0 verifier's own A13a-f suite remains unrun (NOT_VERIFIED); this suite replaces it for the 3.0 verifier.

## 7. Independent review
**Review 8** (isolated agent, fresh clone of commit `dab77be`, own adversarial scripts, `run_mcr3_tests` three times, the fresh-clone verifier with the external anchor, the full attack suite once, two modules re-mutated): **GO_WITH_DOCUMENTED_GAPS, no blocker, no critical authority, replay or evidence-integrity defect.** It reproduced the test, anchor, frozen-history, mutation (for the modules it re-ran) and attack results. It also found new defects, all of which were fixed afterwards with tests (section 9): top-level `disposition`/`outcome_class` accepted on any event type; schema patterns accepting a trailing newline and impossible calendar dates; `parse_expiry` reading `...+05:00Z` as UTC; one mutation survivor wrongly called equivalent (a broken integrity block could poison the replay cache); supersession without a trust rule and a store holding the caller's dict; an adapter mode not capped by a recorded restriction; an approval reference reported without a scope; fractional-second ordering by string; a readback identity test that was a substring match; id limits looser than the `pe-event/1` envelope; undocumented scanner gaps; and a documentation count that was stale. **The fixes are verified by new tests (1,573 checks now), a fresh full mutation run, the re-run attack suite and the fresh-clone verification, but they were not independently re-reviewed in full**: a targeted re-review of the fix diff is recorded below if it was run.

**Review 9** (targeted, isolated agent, fresh clone of commit `26f84dc`, the diff `dab77be..26f84dc`): **GO_WITH_DOCUMENTED_GAPS**, no blocker, no regression. All 13 Review 8 findings and the scanner items were checked with the reviewer's own adversarial scripts (every event type against both summary fields, all 49 trust pairs for supersession, ids of 95/96/97 characters, ASCII and Unicode line separators on every pattern-constrained field, offsets in every position of `expires_at`, replay-cache poisoning variants, deep events to 100,000 levels) and found fixed. It reproduced 1,573 checks, the fresh-clone verification with the external anchor, the frozen-history checks and the chain-module mutation counts (119 mutants, 2 explained survivors), and confirmed that the frozen R2.0 evidence still converts and ingests (7 of 7 events) and that the 11 example events still parse. Its five new findings are low or informational and are recorded in section 10; none touches authority, replay, provenance or evidence integrity. The release candidate as a whole may go to the owner as a draft pull request.

## 8. Remaining gaps (not hidden)
1. No production signing key, trust root or key-custody decision exists (owner decision); signatures are tested with throwaway identities only.
2. The HMAC back-end is TEST ONLY; Ed25519 needs the optional `cryptography` package; SSHSIG needs `ssh-keygen`.
3. Ledger guarantees were exercised on Windows/NTFS only; POSIX locking, network filesystems and power-loss durability are untested. A restored older ledger or rewritten history is detected only if an anchor is held somewhere the ledger's host cannot rewrite; local tests do not establish exactly-once enterprise execution.
4. The model verifies the consistency of presented evidence, not who produced it; identity assurance is SELF_REPORTED unless SIGNED_TRUSTED evidence supports more; `tenant` has no authoritative offline source.
5. 42% of mutant detections are validator crashes rather than targeted assertions; the 36 survivors are justified by argument.
6. The Claude Mods side is exercised only through mocks: the live Governor, approval records, collector store and signing keys were not read; ingestion needs the change packet applied there.
7. The scanner is a heuristic with documented unsupported patterns.
8. R2.0 carry-overs that stay open: one live run, token rotation declined (owner-accepted risk), the leftover test CDS view `ZC_MCR20C_7A3F91D2`, the frozen R2.0 verifier's A13a-f suite never run to completion (the 3.0 verifier's equivalent suite is in section 6).
9. External specification texts (CloudEvents, in-toto, MCP authorization, OWASP) were not re-read during this work; the pins record what the contract cites.

## 9. Fixes made after independent review 8 (each has tests; all are in the final commit)
| Review finding | Fix |
|---|---|
| 1 top-level `disposition`/`outcome_class` accepted on any type (layer separation hole; copied into the `pe-event` mapping) | allowed only on `mcr.mission.disposition`; the mapping reads them from the claim |
| 2 schema `pattern` and date-time too loose | `$` means end of string only (ECMA); date-time must be a real calendar date and time |
| 3 `parse_expiry` accepted `...+05:00Z` as UTC | any offset before the `Z` is refused |
| 4 survivor "equivalent" was not (replay-cache pollution by a broken integrity block) | test added; the explanation removed from the harness |
| 5, 6 supersession without a trust rule; store kept the caller's dict | an event may not supersede a more trusted one; the store keeps and returns copies |
| 7 `mode()` ignored a recorded restriction | the mode of every version is capped by it; `rollback` simplified to `mode()` |
| 8 `view()` without a scope reported an approval reference | no scope, no reference |
| 9 default `Mission` ledger is volatile | documented as a deployment requirement (security contract section 3); `resume()` still enforces a durable ledger |
| 10 times compared as strings; calendar-invalid times | compared by value (to microsecond precision); calendar validity enforced by the schema validator |
| 11 readback identity was a substring match | whole-name match (`ZCL_FOO` is not found in `ZCL_FOOBAR`); comments and namespace-style prefixes can still match (see section 10) |
| 12 ids longer than the `pe-event/1` envelope; mock collector looser than the real one | ids limited to 96 characters; the mock uses the alphanumeric-first 96-character safe-string rule; consumers MUST re-run provenance assessment because a trust label in an event is self-asserted (security contract 3b) |
| 13 recursion on absurdly deep events | a contract error |
| scanner gaps and names | `passphrase`, `pwd`, `credential(s)`, `access_key` and the `:=` and `=>` operators covered; remaining gaps documented |
| stale counts and a placeholder in the reports | corrected |

## 10. Low findings of Review 9 left open (disclosed, no code change made)
1. The date-time check uses a Unicode-aware digit class, so non-ASCII digits (for example Arabic-Indic) pass as an event `time`; a strict ECMA validator would refuse them. No authority impact. Repair: `[0-9]` and an ASCII check.
2. `parse_expiry` accepts ISO forms Python 3.13's `fromisoformat` allows beyond its docstring (basic format, week dates, a space separator); all resolve to the correct UTC instant.
3. Mission-chain time ordering truncates fractions to microseconds; a decrease below that scale is not flagged.
4. Readback identity is a whole-name match, not a structural one: a name in a comment, or after a `/` or `-`, still counts as the object (a comment mention was always true).
5. `evc1.seal` and `digest_of` raise a raw `RecursionError` for a hostile, absurdly deep producer-side object (the consumer paths `parse`, `migrate` and the store return a contract error); the schema validator's `$` rewrite would break a future pattern containing `[$]` (none exists).
Also noted: EXPIRED and UNTRUSTED_RESEARCH share a trust rank, so they can supersede each other.

## 11. PR #5 adapter-governance gate (correction after commit 45f43cb)
**Defect.** `AdapterRegistry.promote()` accepted any dict with a non-empty `approval_id` and `source == "EXTERNAL_GOVERNOR"`. A fabricated reference promoted an adapter to SHADOW or ACTIVE, contradicting the rule that approval is external, verified and scoped. Reports up to section 10 described promotion as needing an "external approval reference"; that wording understated how weak the check was.
**Fix (commits b932d2c, 1a74700; code only in `mcr3_authority.py`).** `AdapterRegistry` now takes an `ApprovalVerifier` (default: deny everything) and an injectable clock. `promote(..., approval_record, expected_scope)` requires: a complete record; the caller's expected scope (owner, capability, provider, target, operation, environment, policy digest) matched exactly; a capability the adapter supports (`*` = any); binding to this adapter id, version, target mode and qualification digest; an unexpired `expires_at` (the instant of expiry is expired); and `verify(record) is True` from the external approver (an exception or any other answer denies). `mode()` re-checks the stored approval on every read, so an expired or revoked approval returns the adapter to OBSERVATION_ONLY. Re-registering drops the approval. `DEFAULT_AUTHORITY` stays NONE and qualification still never approves.
**Tests.** 30 new checks (suite total 1,603, 0 failed): forged (bare and complete-looking), default-deny registry, wrong scope for each of the seven fields, unsupported capability, wrong adapter / version / mode / qualification binding, expired, expiring-exactly-now, malformed expiry, missing scope or bound fields, non-string or empty fields, raising and loosely-answering verifiers, revoked approval (drops an existing promotion and blocks a new one), expiry lapse over time, approval reuse for another adapter, tampered declared mode, wildcard adapter.
**Mutation (this module only, commit 1a74700, `MCR3_MUTATION_CHECK_AUTHORITY_GATE_R1.json`).** 143 mutants: 59 assertion, 75 validator crash, 0 hang, 9 explained survivors, 0 unexplained, 0 inconclusive. The first run (b932d2c) left 10 unexplained survivors; 8 were closed with boundary tests and 2 were explained as equivalent (the fail-closed default verifier; empty scope fields are refused by the scope or bound checks). The 1,580-mutant file for the other modules is unchanged and still refers to its own earlier commit. The verifier attack suite and the interop package were not re-run (no change to them).
**Not changed / not claimed.** The only verifiers are test doubles; no live Governor was contacted and no production key exists. A real Governor-backed `ApprovalVerifier` remains the owner's next step.

**Independent targeted review of the gate (isolated agent, fresh clone of `a9b942f`): GO_WITH_DOCUMENTED_GAPS.** No way found to promote or hold SHADOW/ACTIVE without a verifier-approved record through the public calls (about 25 adversarial cases; 1,603 checks and the anchor reproduced; the mutation file was read, not re-run). Findings and dispositions:
1. (medium-low) `mode()` did not cap the declared mode to the approved `to_mode`, so editing `declaration["MODE"]` from SHADOW to ACTIVE after a SHADOW approval returned ACTIVE. **Fixed**: mode is capped to the approved mode; an unknown declared mode is OBSERVATION_ONLY; tests added.
2. (low) A verifier must authenticate the whole record (expiry, scope, binding), not only the id; the mock checks only the id. **Documented** in the `ApprovalVerifier` docstring; the shipped verifiers are test doubles.
3. (low) After an approval lapses, `declaration["MODE"]` and `APPROVAL_STATUS` still show the old values, and renewing at the same mode is refused ("promotion must raise the mode"), so a lapsed adapter cannot be renewed except by re-registering. **Open, fail-closed**; consumers must call `mode()`, not read the declaration.
4. (low) A raising, None or NaN clock. **Fixed** for `mode()` and `promote()` (they lapse or refuse); tests added.
5. (info) dict subclasses were accepted as records. **Fixed** (`type(record) is dict`).
The fixes to findings 1, 4 and 5 were verified by new tests and a re-run mutation of this module (below) but not re-reviewed by the isolated reviewer.
