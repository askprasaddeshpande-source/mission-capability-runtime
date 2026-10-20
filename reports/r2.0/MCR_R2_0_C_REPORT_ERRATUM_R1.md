# MCR R2.0C Report Erratum R1

Applies to `reports/r2.0/MCR_R2_0_C_LIVE_OUTCOME_STUDY_REPORT_R1.md`, `evidence/r2.0/MCR_R2_0_HYPOTHESIS_STATUS_R2.md` and `evidence/r2.0/MCR_R2_0_HYPOTHESIS_REGISTER_R1.md`. Those files are frozen and are **not edited**; this erratum supersedes the statements below. Added in R2.0G (2026-10-20), baseline commit `6f992c6`.

## What was wrong
The R2.0C report and hypothesis status R2 said "12 of the 13 specified links were emitted". That was a miscount.
- The specified chain (mission specification section 19) has **14** links, ending with COMPLETION_RECEIPT.
- The frozen live result (`evidence/r2.0/MCR_R2_0_C_LIVE_EXECUTION_RESULT_R1.json`) contains **13** emitted entries: MISSION_INTENT through OUTCOME_RECEIPT. All 13 are present, correctly ordered and hash-linked.
- The missing entry is link 14, COMPLETION_RECEIPT.

Correct statement: **13 of 14 links were emitted; the completion receipt hash was not emitted.**

The same omission was baked into two earlier artifacts: a synthetic test asserting a COMPLETE mission has 13 links (`MCR_R2_0_A_VALIDATION_RESULT_R1.json`, 74 tests) and the "13-link hash chain" wording in the hypothesis register R1 (H47 row). They are kept as history; the repaired model and the 96-test result `MCR_R2_0_A_VALIDATION_RESULT_R2.json` supersede them.

## What is unchanged
- The live outcome, `COMMITTED_AND_OUTCOME_VALIDATED`, mission state COMPLETE, and every receipt hash in the frozen file. Nothing was re-run and nothing is backfilled.
- The original claim that a completion receipt object was created in the run's memory and the mission state reached COMPLETE. What was lacking was storing the receipt in the mission record and emitting its hash. The old run therefore has **no hash evidence of a completion receipt**. In principle its fields could be re-derived from the four upstream hashes and fixed identifiers, but that value was not emitted, is not computed here, and is not asserted as evidence.
- H41 and H42: they rest on links 10-13 (execution, commit observation, authoritative readback, outcome receipt), all emitted. Status stays OBSERVED (scoped).
- H43 stays PARTIAL. H47 stays PARTIAL with the corrected qualifier (13/14 links emitted live).

## Cause and repair
`Mission.complete()` validated the completion receipt but did not store it, and `chain_hashes()` had no completion slot. R2.0G stores the receipt after all guards pass, adds link 14, enforces the full 14-link order (`architecture/r2.0/MCR_R2_0_EVIDENCE_CHAIN_CONTRACT_R1.md`), and tests absent, tampered, mismatched and incomplete evidence. The repair is validated offline and against the frozen runner's mock provider; it has **not** been observed in a live run.

## Reproducibility note
The live run used the model as of commit `6f992c6`. That revision is recoverable from Git. The frozen runner (`tools/r2.0/r2_0c_study.py`, SHA-256 `A73F4647...3DDC9`) is unchanged.
