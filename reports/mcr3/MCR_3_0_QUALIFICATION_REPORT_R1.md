# MCR 3.0 Qualification Report R1

Release line 3.0.0, an **offline engineering release candidate**. Baseline `main` at `fd865c67c053431dc33297a0df2a3c9a02fd51fe` (MCR R2.0, PR #4). Everything here is SYNTHETIC/LOCAL evidence. No SAP write, no live run, no network call, no production signing key, no capability promoted to production trust.

## 0. Which commit each result belongs to
The mutation run (section 3) and the verifier attack run (section 6) were executed on commit `bec9a3a`. The only code change after it is one test name made deterministic in `tools/mcr3/validate_mcr3_hardening.py` (a temporary-path hash made that suite's result differ between runs); the other later changes are evidence files, sums and these reports. The full test run, the fresh-clone verification with the external sums anchor and the independent review refer to the final commit named in the pull request.

## 1. What was built
See `architecture/mcr3/MCR_3_0_ARCHITECTURE_AND_DECISION_RECORD_R1.md` (decision and module map), `MCR_3_0_SECURITY_AND_AUTHORITY_CONTRACT_R1.md`, `contracts/evidence-v1/README.md`, `CLAUDE_MODS_CHANGE_PACKET_R1.md` and `reports/mcr3/MCR_3_0_GAP_CLOSURE_MATRIX_R1.md`.

## 2. Test results (reproduce with `python tools/mcr3/run_mcr3_tests.py`)
**1,498 checks in 9 suites, 0 failed** (about 31 s sequentially, peak 38 MB in any one suite; raw records in `evidence/mcr3/MCR3_RESULT_*_R1.json`, resource record `MCR3_RESOURCE_USE_R1.json`).
| Suite | Checks | What it holds |
|---|---|---|
| inherited_r2 | 519 | the R2.0 validator re-run against the 3.0 model, with documented expectation changes |
| hardening | 140 | ledger path forms, expiry, binding fields, activation, compensation attempts, ledger anchor, outcome classification |
| evidence_contract | 207 | schema, examples, negative fixtures, exhaustive trust derivation (216 provenance combinations), canonical form, compatibility, migration, mini-validator, a 1,500-case hostile-input fuzz |
| provenance_authority | 115 | hash / signature / issuer / freshness / replay as separate findings with HMAC (test only), Ed25519 and SSHSIG back-ends; capability and adapter governance |
| adapters_interop | 99 | frozen-R2.0 adapter, native adapter, equivalence between them, lineage, the ten Claude Mods scenarios, `pe-event` mapping |
| evidence_chain | 54 | mission-level inconsistent-chain detection |
| readback | 34 | portable readback rules and the offline SAP-style provider |
| scanner | 99 | 27 credential shapes, encodings, false positives, documented unsupported patterns, tracked-tree scan |
| mutation_gap_tests | 231 | tests written for specific surviving mutants |
Not verified on the qualifying machine: nothing optional was missing (the `cryptography` package and `ssh-keygen` were present, so the Ed25519 and SSHSIG back-ends ran). On a machine without them those checks are recorded NOT_VERIFIED by the suites themselves.

## 3. Mutation qualification (reproduce with `python tools/mcr3/run_mcr3_mutation_check.py --jobs 3`, about 25 minutes; `evidence/mcr3/MCR3_MUTATION_CHECK_R1.json`)
**1,564 mutants generated from the source of 11 modules** (1342 syntax-tree clause/operator, 141 guard, 53 chain relation, 28 targeted). Every mutant applied. Classification kept separate:
- **885 detected by an assertion** (a validator ran to completion and named failed checks);
- **646 detected by validator crash** (a validator died with a traceback because the mutant broke a flow its own fixtures need): weaker evidence, counted but reported as such (42% of detections; 353 of the 765 runtime-model detections);
- **1 detected by hang** (removing the lock-wait timeout);
- **32 survivors, each an explained equivalent mutant** with a stated reason in the harness (for example a clause made redundant by an earlier check, or a default that cannot differ); **0 unexplained; 0 inconclusive**.
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
{{REVIEW_SUMMARY}}

## 8. Remaining gaps (not hidden)
1. No production signing key, trust root or key-custody decision exists (owner decision); signatures are tested with throwaway identities only.
2. The HMAC back-end is TEST ONLY; Ed25519 needs the optional `cryptography` package; SSHSIG needs `ssh-keygen`.
3. Ledger guarantees were exercised on Windows/NTFS only; POSIX locking, network filesystems and power-loss durability are untested. A restored older ledger or rewritten history is detected only if an anchor is held somewhere the ledger's host cannot rewrite; local tests do not establish exactly-once enterprise execution.
4. The model verifies the consistency of presented evidence, not who produced it; identity assurance is SELF_REPORTED unless SIGNED_TRUSTED evidence supports more; `tenant` has no authoritative offline source.
5. 42% of mutant detections are validator crashes rather than targeted assertions; the 32 survivors are justified by argument.
6. The Claude Mods side is exercised only through mocks: the live Governor, approval records, collector store and signing keys were not read; ingestion needs the change packet applied there.
7. The scanner is a heuristic with documented unsupported patterns.
8. R2.0 carry-overs that stay open: one live run, token rotation declined (owner-accepted risk), the leftover test CDS view `ZC_MCR20C_7A3F91D2`, the frozen R2.0 verifier's A13a-f suite never run to completion (the 3.0 verifier's equivalent suite is in section 6).
9. External specification texts (CloudEvents, in-toto, MCP authorization, OWASP) were not re-read during this work; the pins record what the contract cites.
