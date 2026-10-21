# MCR R2.0 State Machine R1

Source of truth: `tools/r2.0/mcr_r2_model.py` (`STATES`, `TRANSITIONS`). The table below is generated from it. Evidence class: SYNTHETIC/LOCAL.

## Rule
A state is entered only through a guard that demands the specific evidence object for that state. No state is inferred from an earlier one:
EXECUTED does not imply COMMITTED; provider success does not imply SAP commit; COMMITTED does not imply the expected business outcome; readback observed does not imply outcome validated; outcome validation does not imply compensation correctness.

## Transitions
| From | To (allowed) |
|---|---|
| `PLANNED` | `CONTEXT_READY`, `FAILED_BEFORE_MUTATION` |
| `CONTEXT_READY` | `AUTHORIZED`, `FAILED_BEFORE_MUTATION` |
| `AUTHORIZED` | `BOUND`, `FAILED_BEFORE_MUTATION` |
| `BOUND` | `FAILED_BEFORE_MUTATION`, `PREWRITE_VALIDATED` |
| `PREWRITE_VALIDATED` | `EXECUTION_STARTED`, `FAILED_BEFORE_MUTATION` |
| `EXECUTION_STARTED` | `COMMIT_STATE_UNKNOWN`, `EXECUTED`, `FAILED_AFTER_POSSIBLE_MUTATION` |
| `EXECUTED` | `AUTHORITATIVE_READBACK_PENDING`, `COMMIT_STATE_UNKNOWN` |
| `COMMIT_STATE_UNKNOWN` | `AUTHORITATIVE_READBACK_PENDING`, `FAILED_AFTER_POSSIBLE_MUTATION` |
| `COMMITTED` | `OUTCOME_VALIDATION_PENDING` |
| `AUTHORITATIVE_READBACK_PENDING` | `AUTHORITATIVE_READBACK_OBSERVED`, `COMMIT_STATE_UNKNOWN` |
| `AUTHORITATIVE_READBACK_OBSERVED` | `COMMITTED`, `COMMIT_STATE_UNKNOWN`, `FAILED_AFTER_POSSIBLE_MUTATION` |
| `OUTCOME_VALIDATION_PENDING` | `COMPENSATION_REQUIRED`, `OUTCOME_VALIDATED` |
| `OUTCOME_VALIDATED` | `COMPLETE` |
| `COMPLETE` | _terminal_ |
| `FAILED_BEFORE_MUTATION` | _terminal_ |
| `FAILED_AFTER_POSSIBLE_MUTATION` | `AUTHORITATIVE_READBACK_PENDING`, `COMPENSATION_REQUIRED`, `UNRECOVERABLE` |
| `COMPENSATION_REQUIRED` | `COMPENSATION_AUTHORIZED`, `UNRECOVERABLE` |
| `COMPENSATION_AUTHORIZED` | `COMPENSATED`, `UNRECOVERABLE` |
| `COMPENSATED` | _terminal_ |
| `UNRECOVERABLE` | _terminal_ |

## Guards (what each entry requires)
| Entry | Required evidence |
|---|---|
| AUTHORIZED | ExecutionAuthority derived from this DelegationEnvelope (hash), scope subset (attenuation), mutation count <= delegation, MutationBudget bounded by authority with retries=0 and no expansion, authority not already consumed |
| BOUND | CapabilityBinding from this authority, capability inside authority scope, ProviderBinding with contract fingerprint |
| PREWRITE_VALIDATED | Transaction + ExpectedOutcomeContract (frozen, same transaction) + AuthoritativeReadbackContract (source level AUTHORITATIVE_REPOSITORY) + PreMutationCheckpoint pinning budget, outcome contract and readback contract by hash |
| EXECUTION_STARTED | Point-of-use contract fingerprint equal to bound fingerprint; mutation in transaction; ReplayGuard key (authority, mutation) unused; budget > 0. Budget and guard are consumed **before** the call is sent |
| EXECUTED | ExecutionReceipt with call_class PROVIDER_RESPONSE_SUCCESS (says nothing about commit) |
| COMMIT_STATE_UNKNOWN | no response, provider error, COMMIT_UNKNOWN receipt, non-authoritative or UNKNOWN readback |
| AUTHORITATIVE_READBACK_OBSERVED | AuthoritativeReadbackReceipt produced under the frozen readback contract, same transaction and mutation id |
| COMMITTED | CommitObservation bound to an AUTHORITATIVE_REPOSITORY readback with existence EXISTS |
| (readback ABSENT) | FAILED_AFTER_POSSIBLE_MUTATION, fail closed; no retry without a new authorization lineage |
| OUTCOME_VALIDATED | OutcomeReceipt bound to outcome contract + readback; result must equal independent recomputation of the predicates (PASS) |
| (predicates FAIL) | COMPENSATION_REQUIRED |
| (predicates UNKNOWN) | remains OUTCOME_VALIDATION_PENDING, COMPLETE=FALSE |
| COMPLETE | CompletionReceipt hash-linking authority, execution receipt, commit observation and outcome receipt, from OUTCOME_VALIDATED |
| COMPENSATION_AUTHORIZED | CompensationGrant that does not inherit forward authority, is not issued from it, has preconditions, predicates, budget >= 1, and targets this mission |
| COMPENSATED | CompensationReceipt bound to the grant and to an authoritative post-compensation readback whose predicates pass |

## Call-class semantics (fail closed)
CALL_NOT_SENT, CALL_SENT_NO_RESPONSE, PROVIDER_ERROR, PROVIDER_RESPONSE_SUCCESS, COMMIT_UNKNOWN, COMMIT_CONFIRMED, OUTCOME_FAILED, OUTCOME_VALIDATED. After a send, FAILED_BEFORE_MUTATION is unreachable. UNKNOWN is never collapsed into PASS or FAIL.
