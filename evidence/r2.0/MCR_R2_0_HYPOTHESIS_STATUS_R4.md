# MCR R2.0 Hypothesis Status R4

Date: 2026-10-20. **Supersedes the status columns of** `MCR_R2_0_HYPOTHESIS_REGISTER_R1.md`, `MCR_R2_0_HYPOTHESIS_STATUS_R2.md` and `MCR_R2_0_HYPOTHESIS_STATUS_R3.md` (all retained as history and not edited; where they disagree with this file, this file and `reports/r2.0/MCR_R2_0_C_REPORT_ERRATUM_R1.md` govern). Inputs since R3: independent review verdict HOLD (`reports/r2.0/MCR_R2_0_INDEPENDENT_QUALIFICATION_R1_FINDINGS.md`) and the R2.0H hardening (`reports/r2.0/MCR_R2_0_H_HARDENING_REPORT_R1.md`). **No live evidence was added; no hypothesis was promoted; none is PROVEN.** The independent re-review of the hardened model has not happened yet.

| ID | Status | Change vs R3 | Wording constraint now in force |
|---|---|---|---|
| H41 Authoritative Commit Observation | OBSERVED (scoped) | wording qualified | One DDLS on TRL_EN: a baseline ABSENT, one create, then EXISTS from the DDLS endpoint of the owner's ADT-session read tool. "Authoritative" is the runner's own label for that source, not independently attested; EXISTS was taken if either version was found; ABSENT did not check the exception named the object; the source-integrity check compares hashes inside one response. A third-party creation between prewrite and readback would not have been distinguished |
| H42 Outcome-Authoritative Completion | OBSERVED (scoped) | wording qualified | Four predicates passed on that readback; predicates exclude package and activation; the name predicate is a substring test |
| H43 Transaction Correlation | PARTIAL | none | ids and hashes across receipts; fresh name; no provider correlation token |
| H44 Replay-Safe Continuation | SYNTHETIC | strengthened synthetically | after R2.0H, a forged or inflated lease, a forged lease state and downstream evidence are rejected, and every post-send resume restarts in COMMIT_STATE_UNKNOWN; lease authenticity (signature) is not provided; no live interruption |
| H45 Compensation Authority Separation | SYNTHETIC | none | model only |
| H46 Contract-Drift Fail-Closed | PARTIAL | none | live drift 20 to 29 tools observed; gate passed live; fail-closed synthetic |
| H47 Evidence-Complete Mission Closure | PARTIAL | none | live run emitted 13 of 14 links; the model now validates all 14 links relationally and rejects forged or recomputed chains in synthetic tests; link 14 never observed live; receipt provenance is not authenticated |
| H48 Bounded Governance Overhead | PARTIAL (descriptive) | none | single run plus synthetic; no inference |

## Model qualification status (not a hypothesis)
Repository model: 133 checks and 35 guard mutants all detected by assertion, offline. Independent verdict on the previous commit was HOLD; the HIGH defects it found are fixed and tested here but **unreviewed**. The model verifies the consistency of presented evidence, not who produced it (no signatures or attestation).
