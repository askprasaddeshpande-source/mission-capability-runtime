# MCR R2.0 Hypothesis Status R6

Date: 2026-10-21. **Supersedes** `MCR_R2_0_HYPOTHESIS_REGISTER_R1.md` and status R2, R3, R4 and R5 (all retained as history, not edited). Where they disagree with this file and with `reports/r2.0/MCR_R2_0_C_REPORT_ERRATUM_R1.md`, those govern. **No live evidence was added since R5; no hypothesis was promoted; none is PROVEN.** Three independent reviews of the repository returned HOLD (`8a383b6`, `b5cca1f`, `a381a22`). The defects review 3 found are addressed offline in R2.0J (`reports/r2.0/MCR_R2_0_J_HARDENING_REPORT_R1.md`) and have **not yet been re-reviewed**.

## Corrections to R5 wording
- R5 H44 said a stale lease cannot re-open a send when a durable ledger is passed, and R5 called the ledger "durable". Review 3 showed that two processes sharing one ledger file could both send, that a resumed mission skipped the gate checks, and that the ledger did not count sends per authority. R2.0J fixes those and states the ledger's limits (contract R4, section 2).
- R5 H45 said compensation requires a verified post-compensation readback. Review 3 showed COMPENSATED was reachable with no compensating action. R2.0J requires a begun compensation, an execution receipt and a distinct authoritative post readback.
- R5 and the I hardening report said "0 survivors". That was true at 159 whole-condition mutants; at 513 clause-level mutants 6 survive as justified equivalents.

| ID | Status | Wording constraint now in force |
|---|---|---|
| H41 Authoritative Commit Observation | OBSERVED (scoped) | One DDLS on TRL_EN: baseline ABSENT, one create, then EXISTS from the DDLS endpoint of the owner's ADT-session read tool. "Authoritative" is the runner's own label, not independently attested; EXISTS was taken if either version was found; ABSENT did not check that the exception named the object; the source-integrity check compares hashes inside one response; a third-party creation between prewrite and readback would not have been distinguished |
| H42 Outcome-Authoritative Completion | OBSERVED (scoped) | Four predicates passed on that readback; predicates exclude package and activation; the name predicate is a substring test |
| H43 Transaction Correlation | PARTIAL | ids and hashes across receipts; fresh name; no provider correlation token |
| H44 Replay-Safe Continuation | SYNTHETIC | offline: lease, checkpoint and budget integrity; a resumed mission re-runs the real guards; a post-send resume restarts in COMMIT_STATE_UNKNOWN; a stale lease cannot re-open a send recorded in the ledger. The ledger is a local file with an OS lock: tested with four real processes on Windows; POSIX locking untested; different ledger files, volatile ledgers, network filesystems and power-loss durability are not covered; lease authenticity (signature) is not provided; no live interruption |
| H45 Compensation Authority Separation | SYNTHETIC | offline: separate grant, no inheritance, capability outside the forward scope, preconditions evaluated on an authoritative forward readback, a begun compensation that consumes its own ledger entry, an execution receipt bound to the grant, a distinct authoritative post readback; no live compensation |
| H46 Contract-Drift Fail-Closed | PARTIAL | live drift 20 to 29 tools observed; point-of-use fingerprint gate passed live and fails closed in synthetic tests |
| H47 Evidence-Complete Mission Closure | PARTIAL | the live run emitted 13 of the 14 specified links; offline, COMPLETE re-verifies kind, hash and 49 named relations plus the predicate check over the whole chain and rejects the forgeries tested, but provenance is not authenticated (a self-consistent forged chain labelled authoritative is accepted); link 14 never observed live |
| H48 Bounded Governance Overhead | PARTIAL (descriptive) | single live run plus synthetic; no inference |

## Model qualification status (not a hypothesis)
Repository model: 391 checks; 513 generated mutants all detected (267 by assertion, 240 because the validator's own fixtures could no longer run), 6 equivalent survivors each with a stated reason; frozen-runner mock regression 6/6. Independent verdict on the last reviewed commit was HOLD; fixes are unreviewed. The model verifies the consistency of presented evidence, not who produced it, and is a single-send-per-mission library.
