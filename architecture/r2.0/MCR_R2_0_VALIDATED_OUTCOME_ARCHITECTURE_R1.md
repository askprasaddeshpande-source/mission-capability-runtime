# MCR R2.0 Validated Outcome Architecture R1

ACLA (mission context / lifecycle), EAF (pre- and post-action authority) and MCR (capability selection, binding, execution control, outcome evidence) are distinct components. R2.0 adds the outcome plane to MCR; it does not merge the three.

## Control flow
Mission -> ACLA mission context -> EAF pre-action authority -> MCR capability selection -> provider binding -> point-of-use authority revalidation -> mutation budget -> pre-mutation checkpoint -> enterprise execution -> **execution receipt** -> commit observation -> **authoritative enterprise readback** -> outcome predicate -> **outcome receipt** -> EAF post-action validation -> completion receipt -> evidence / ACLA lifecycle update.

Bold items are the R2.0 additions that separate "the tool returned" from "the enterprise state is as intended".

## Two receipts, never merged
- **ExecutionReceipt**: a classified fact about the call (`CALL_NOT_SENT` ... `PROVIDER_RESPONSE_SUCCESS`). Establishes at most EXECUTED.
- **OutcomeReceipt**: a result (PASS/FAIL/UNKNOWN) of evaluating the frozen ExpectedOutcomeContract against an AuthoritativeReadbackReceipt. Recomputed by the guard; a receipt whose result disagrees with recomputation is rejected.

## Authoritative readback
Source levels, strongest first: `AUTHORITATIVE_REPOSITORY`, `PROVIDER_VALIDATION`, `PROVIDER_LOG`, `TRANSPORT_SUCCESS`, `CACHED_OUTPUT`, `LOCAL_RUNNER_STATE`, `INFERRED_OR_REGEX`. Only the first can establish COMMITTED or ABSENT. A provider error, an empty body or an unreachable bridge yields `UNKNOWN`, never `ABSENT` (R1.9 lesson). Output: existence EXISTS/ABSENT/UNKNOWN; activation ACTIVE/INACTIVE/UNKNOWN; plus observed fields for predicates (type, package, source hash).

## Transaction correlation
Execution receipt, readback receipt, commit observation and outcome receipt each carry `transaction_id` and `mutation_id`, and each downstream object carries the hash of its upstream object. Correlation is by identifier and hash, not temporal proximity. Schemas deliberately contain no timestamp field in any correlation key.

## Replay and continuation
Budget decrement and ReplayGuard insertion (authority hash, mutation id) happen before the call leaves the client. A ContinuationLease is bound to a checkpoint hash and transaction id, carries the consumed set, and cannot enlarge the remaining budget. A no-response or error leaves the mission in COMMIT_STATE_UNKNOWN; the only forward path is readback/reconciliation, not retry.

## Compensation
A CompensationGrant is a separate object: exact target, capability, budget, preconditions, outcome predicates; `inherits_forward_authority=false` and not issued from the forward authority. COMPENSATED requires an authoritative post-compensation readback satisfying the grant's predicates. Compensation is not completion of the original mission.

## Drift
Contract fingerprint is checked at bind time and again at point of use. Mismatch fails closed before the budget is consumed. Mission-relevant drift in the readback contract invalidates the pre-mutation checkpoint (to be exercised in R2.0D/H46).

## Telemetry
GovernanceTelemetry records governance time and provider time as separate fields (R2.0F).

## Objects
25 object kinds, each hash-addressed (SHA-256 over canonical JSON). JSON Schemas generated into `architecture/r2.0/schemas/` by `tools/r2.0/validate_r2_outcome_model.py --emit-schemas`.

## Evidence class
Everything in R2.0A is SYNTHETIC/LOCAL. It shows the model's guards behave as specified; it shows nothing about any enterprise system.
