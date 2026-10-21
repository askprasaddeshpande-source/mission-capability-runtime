# MCR R2.0A Foundation Qualification R1

Stage: `R2_0_A_OUTCOME_MODEL_FOUNDATION`. Evidence class: **SYNTHETIC/LOCAL**. No enterprise write, no provider call, no network I/O.

**R2_0_A_FOUNDATION = PASS** (74 checks, 11 acceptance groups; `evidence/r2.0/MCR_R2_0_A_VALIDATION_RESULT_R1.json`).

| Acceptance criterion | Result | What backs it |
|---|---|---|
| STATE_MACHINE_VALID | PASS | 20 states, all reachable, terminal states exit-free, no direct path EXECUTED/COMMITTED/READBACK to a later state, no FAILED_BEFORE_MUTATION after send |
| SCHEMA_VALIDATION | PASS | 25 object kinds, required-field and enum checks, key-order-independent SHA-256 addressing, tamper detection; JSON Schemas in `architecture/r2.0/schemas/` |
| AUTHORITY_INVARIANTS | PASS | delegation derivation, scope attenuation, capability inside scope, frozen outcome contract, authoritative readback contract required before prewrite, point-of-use drift fails closed before budget use |
| MUTATION_BUDGET_INVARIANTS | PASS | budget <= authority <= delegation, no retries, no expansion, consumed before send, mutation must belong to the transaction |
| REPLAY_GUARD_INVARIANTS | PASS | (authority, mutation) key consumed once even with budget left; no-response does not unlock retry |
| CONTINUATION_INVARIANTS | PASS | lease bound to checkpoint; cannot enlarge budget; consumed set inherited; re-presented evidence must match checkpoint hash pins |
| COMPENSATION_AUTHORITY_INVARIANTS | PASS | separate grant, no inheritance, not issued from forward authority, preconditions and predicates required, authoritative post-compensation readback, ends COMPENSATED not COMPLETE |
| OUTCOME_PREDICATE_MODEL | PASS | tri-state PASS/FAIL/UNKNOWN; missing field is UNKNOWN; forged receipt result rejected by recomputation; UNKNOWN stays pending |
| COMMIT_UNKNOWN_HANDLING | PASS | five non-authoritative source levels and UNKNOWN readback give COMMIT_STATE_UNKNOWN; authoritative ABSENT fails closed; provider error after send is UNKNOWN, never ABSENT |
| NO_ENTERPRISE_WRITES | PASS | model imports no network/process modules (structural check); runs recorded `enterprise_writes: 0` |

## Extended local scenarios (R2.0D/E/F, SYNTHETIC/LOCAL)
`tools/r2.0/run_r2_local_scenarios.py` writes `evidence/r2.0/MCR_R2_0_DE_LOCAL_SCENARIOS_RESULT_R1.json`.
- Crash injected after each step: a post-send crash resumes as COMMIT_STATE_UNKNOWN, reconciles through readback and reaches COMPLETE with exactly one mutation.
- Swapped outcome contract, inflated budget and foreign checkpoint are rejected on resume.
- Four fault-injection cases never reach COMPLETE without authoritative EXISTS plus passing predicates.
- Compensation runs under its own grant and ends COMPENSATED, not COMPLETE.

This is design-level support for H44/H45, **not** live evidence.

## Governance overhead (descriptive, LOCAL)
n=500, one machine, in-process, no provider. Median whole-path governance cost 105.8 us (p95 123.0 us). The largest component is building and hashing the fixture objects (median 65.8 us). Provider, SAP, network and business latency are not modeled, so this says nothing about enterprise overhead and supports no productivity claim. Raw timing is kept outside Git.

## Limits and known gaps
- The model is tested against its own assertions. A manual mutation check (4 guard removals) was detected, but is not archived.
- The model has no `OUTCOME_UNKNOWN` state: an UNKNOWN predicate leaves the mission in OUTCOME_VALIDATION_PENDING. Revisit if R2.0C needs it.
- `COMMIT_STATE_UNKNOWN -> AUTHORITATIVE_READBACK_PENDING` is the only forward path from unknown; no automatic retry exists by design.
- Readback "authority level" is a declared attribute of a receipt; R2.0B decides which real sources may carry `AUTHORITATIVE_REPOSITORY`.
