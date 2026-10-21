# MCR R2.0 Hypothesis Status R2

Supersedes the status column of `MCR_R2_0_HYPOTHESIS_REGISTER_R1.md` (kept as history). Date: 2026-10-20. Evidence: R2.0A/D/E synthetic, R2.0B and R2.0C one live run each (`reports/r2.0/MCR_R2_0_C_LIVE_OUTCOME_STUDY_REPORT_R1.md`). No hypothesis is PROVEN.

| ID | Status | Basis | Limits |
|---|---|---|---|
| H41 Authoritative Commit Observation | OBSERVED (scoped) | live baseline ABSENT -> one create -> readback EXISTS from the DDLS endpoint; controls in R2.0B | one object, one run, DDLS endpoint only; live ABSENT/UNKNOWN branches for the new mutation not exercised (mock only) |
| H42 Outcome-Authoritative Completion | OBSERVED (scoped) | COMPLETE after 4 frozen predicates passed on authoritative readback | predicates exclude package and activation; failure branches mock only |
| H43 Transaction Correlation | PARTIAL | ids and hash links across all receipts; fresh name + ABSENT baseline + one mutation | provider returned no correlation token; correlation partly rests on uniqueness of the name |
| H44 Replay-Safe Continuation | SYNTHETIC | crash-injection matrix; persisted single-use lock written before send (lock existence observed live) | no live interruption; lock refusal of a second run not exercised live |
| H45 Compensation Authority Separation | SYNTHETIC | model semantics | no live compensation |
| H46 Contract-Drift Fail-Closed Outcome Validation | PARTIAL | drift 20 -> 29 tools OBSERVED live; point-of-use fingerprint gate passed live (no drift) and fails closed in synthetic tests | no live drift between prewrite and call; readback-contract drift not handled |
| H47 Evidence-Complete Mission Closure | PARTIAL | 12 of 13 chain links emitted and hash-linked | completion receipt not persisted by the model (gap) |
| H48 Bounded Governance Overhead | PARTIAL (descriptive) | synthetic n=500 median ~0.1 ms; one live run 69.3 us governance vs 3.68 s provider | single machine/run; no inference |
