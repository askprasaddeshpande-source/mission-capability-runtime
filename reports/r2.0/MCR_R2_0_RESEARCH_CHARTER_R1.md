# MCR R2.0 Research Charter R1 — Validated Enterprise Outcome Runtime

Mission: `MCR_R2_0_VALIDATED_ENTERPRISE_OUTCOME_RUNTIME_R1`
Lineage: new experimental lineage. R1.9 (tag `v1.9.0`) is frozen and is not modified by this work.

## Primary question
Can an enterprise-agent runtime prove that an authorized mission caused the intended enterprise state transition, and distinguish that state from mere tool/provider execution?

## Thesis under test
REQUESTED != AUTHORIZED != BOUND != EXECUTED != COMMITTED != AUTHORITATIVELY_OBSERVED != OUTCOME_VALIDATED != COMPLETE.
No later state is ever inferred from an earlier one. `COMPLETE = AUTHORIZED_EXECUTION AND COMMIT_ESTABLISHED AND AUTHORITATIVE_READBACK AND EXPECTED_OUTCOME_PREDICATE_PASS`. Any required UNKNOWN means `COMPLETE=FALSE`.

## Secondary questions
1. COMMITTED from an authoritative readback. 2. Readback bound to the exact mutation/transaction. 3. Execution receipt vs outcome receipt. 4. COMPLETE only against a frozen outcome predicate. 5. Replay prevention across failure and continuation. 6. Attenuated authority during continuation. 7. Compensation under independently scoped authority. 8. Outcome validation under provider-contract drift. 9. Governance overhead measured separately from business latency.

## Hypotheses (unclassified until evidence exists)
H41 Authoritative Commit Observation; H42 Outcome-Authoritative Completion; H43 Transaction Correlation; H44 Replay-Safe Continuation; H45 Compensation Authority Separation; H46 Contract-Drift Fail-Closed Outcome Validation; H47 Evidence-Complete Mission Closure; H48 Bounded Governance Overhead. See `evidence/r2.0/MCR_R2_0_HYPOTHESIS_REGISTER_R1.md`.

## Phases
R2.0A outcome model foundation (no SAP write) -> R2.0B read-only enterprise qualification (no write) -> R2.0C frozen live outcome study (needs fresh owner authorization) -> R2.0D replay/continuation -> R2.0E compensation -> R2.0F governance overhead.

## Boundaries
- Research-program authorization is not live-write authorization. SAP writes performed to date: 0.
- Never: rerun HF06, create HF07, reuse R1.9 authorizations, repair the R1.9 UNKNOWN with a new experiment, alter R1.9 evidence, rewrite history. Object `ZCL_MCR19B_9533C4D8` is not reused.
- Evidence classes: PROVEN, OBSERVED, PARTIAL, SYNTHETIC, LOCAL, NOT_ESTABLISHED, DEFERRED, REJECTED. No automatic promotion (synthetic -> observed, observed -> proven).
- Raw/unsafe evidence stays outside Git until sanitized. No secrets, tokens, authorization material or private keys are committed.

## Owner blockers (only these)
A fresh live enterprise write required; B credential/session unavailable; C new owner signing action; D unresolved evidence conflict; E unauthorized destructive action.
