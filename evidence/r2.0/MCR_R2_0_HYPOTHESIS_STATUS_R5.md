# MCR R2.0 Hypothesis Status R5

Date: 2026-10-20. **Supersedes** `MCR_R2_0_HYPOTHESIS_REGISTER_R1.md` and status R2, R3 and R4 (all retained as history, not edited). Where they disagree with this file and with `reports/r2.0/MCR_R2_0_C_REPORT_ERRATUM_R1.md`, those govern. **No live evidence was added since R4; no hypothesis was promoted; none is PROVEN.** Two independent reviews of the repository returned HOLD (`b5cca1f` and `8a383b6`); the defects review 2 found are addressed offline in R2.0I (`reports/r2.0/MCR_R2_0_I_HARDENING_REPORT_R1.md`) but have **not yet been re-reviewed**.

## Corrections to R4 wording
- R4 said the HIGH defects were fixed. It was true only for review 1's defects; review 2 found send-time gates that did not verify evidence, a stale-lease replay path and ungated terminal states. R2.0I addresses them; status stays HOLD until re-review.
- R4/R3 H47 said the model "validates all 14 links relationally and rejects forged or recomputed chains". At R2.0H that was false for rehashed intent, capability, provider and checkpoint. R2.0I adds the missing relations and tests; the sentence below replaces it.
- R4 H44 said forged or inflated leases are rejected; it omitted stale-lease replay. Replaced below.

| ID | Status | Wording constraint now in force |
|---|---|---|
| H41 Authoritative Commit Observation | OBSERVED (scoped) | One DDLS on TRL_EN: baseline ABSENT, one create, then EXISTS from the DDLS endpoint of the owner's ADT-session read tool. "Authoritative" is the runner's own label for that source, not independently attested; EXISTS was taken if either version was found; ABSENT did not check that the exception named the object; the source-integrity check compares hashes inside one response; a third-party creation between prewrite and readback would not have been distinguished |
| H42 Outcome-Authoritative Completion | OBSERVED (scoped) | Four predicates passed on that readback; predicates exclude package and activation; the name predicate is a substring test |
| H43 Transaction Correlation | PARTIAL | ids and hashes across receipts; fresh name; no provider correlation token |
| H44 Replay-Safe Continuation | SYNTHETIC | offline: lease and checkpoint integrity, a post-send resume always restarts in COMMIT_STATE_UNKNOWN, a stale lease cannot re-open a send recorded in the replay ledger (demonstrated with a file-backed ledger surviving a simulated restart). Protection requires deployment to pass one durable ledger to every mission and resume; lease authenticity (signature) is not provided; no live interruption |
| H45 Compensation Authority Separation | SYNTHETIC | offline: separate grant, no inheritance, capability outside the forward scope, preconditions evaluated, verified post-compensation readback correlated to the mission; no live compensation |
| H46 Contract-Drift Fail-Closed | PARTIAL | live drift 20 to 29 tools observed; point-of-use fingerprint gate passed live and fails closed in synthetic tests |
| H47 Evidence-Complete Mission Closure | PARTIAL | the live run emitted 13 of the 14 specified links; offline, COMPLETE re-verifies kind, hash and 48 named relations plus the predicate check over the whole chain and rejects the forgeries tested (including consistent forgeries where an attacker recomputed hashes), but provenance is not authenticated: a self-consistent forged chain labelled authoritative is accepted; link 14 never observed live |
| H48 Bounded Governance Overhead | PARTIAL (descriptive) | single live run plus synthetic; no inference |

## Model qualification status (not a hypothesis)
Repository model: 283 checks, 159 generated guard, relation and special mutants all detected (0 survivors; 3 detected only because test fixtures break), frozen-runner mock regression 6/6. Independent verdict on the last reviewed commit was HOLD; fixes are unreviewed. The model verifies the consistency of presented evidence, not who produced it.
