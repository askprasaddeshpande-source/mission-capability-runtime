# MCR R2.0 Evidence Chain Contract R3

Supersedes R2 of this contract (retained). Source of truth: `tools/r2.0/mcr_r2_model.py` (`CHAIN_SLOTS`, `SLOT_KINDS`, `RELATIONS`, `Mission`, `ReplayLedger`). Added after independent review 2 of `b5cca1f` (verdict HOLD).

The 14-link order and emission rules are unchanged (see R1). What changed is where evidence is verified and how replay is remembered.

## 1. Every presented object is verified at the gate that consumes it
Each guard method (`context_ready`, `authorize`, `bind`, `prewrite_validate`, `record_execution`, `observe_readback`, `decide_commit`, `validate_outcome`, `complete`, `authorize_compensation`, `record_compensation`) first checks that every object it is given is a dict of the expected `kind` with a valid `object_hash`, and stores a private deep copy. Consequences: nothing irreversible (the send) can happen on a tampered or wrong-kind object; COMMITTED, OUTCOME_VALIDATED and COMPENSATED cannot be reached on hand-built dictionaries; a caller who keeps an alias and rewrites and re-hashes it afterwards does not change the recorded evidence.

Gate-level relations (checked before the state moves): delegation issued to the principal; authority derived from the delegation, in this mission, attenuated, no larger than the delegation, single use; budget derived from the authority, no larger, no retries or expansion, equal to the mission limit; capability from this authority, inside its scope, matching the provider tool and identity; transaction and outcome contract in this mission; mutation ids a non-empty list of strings; checkpoint pins transaction, budget, outcome contract and readback contract, and its budget equals the budget limit; execution receipt, readback and commit observation correlated to the transaction and mutation; outcome bound to readback and contract and equal to a recomputation.

## 2. Replay is remembered outside the lease
`ReplayLedger` is an append-only set of `(authority hash, mutation id)` pairs. `begin_execution` consults it, records the send in it (flushed and fsynced when file-backed) before the state moves, and it is never rolled back by a failed call. `resume()` requires the ledger and uses the UNION of the lease and the ledger, so a stale lease (taken before a send that was never persisted) cannot re-open that send. A post-send resume always restarts in COMMIT_STATE_UNKNOWN. Deployments must pass one durable ledger to every Mission and to every resume; a process-local ledger protects only that process.

## 3. COMPLETE re-verifies the whole chain
In order: the completion receipt is verified; the state is OUTCOME_VALIDATED; all 15 required slots are present, of the right kind and hash-valid; then the relations below, each with an id; then the completion receipt's four hash links and transaction. A malformed object yields GuardError. Every relation has its own violation recipe in the validator and an automatically generated mutant in the mutation harness.

| Id | Relation checked by COMPLETE |
|---|---|
| R01 | delegation not issued to this principal |
| R02 | authority not derived from delegation |
| R03 | authority mission mismatch |
| R04 | intent mission mismatch |
| R05 | authority scope exceeds delegation |
| R06 | authority mutation count exceeds delegation |
| R07 | budget not derived from authority |
| R08 | budget exceeds authority |
| R09 | budget allows retries or expansion |
| R10 | budget differs from mission limit |
| R11 | authority is not single use |
| R12 | capability binding not from this authority |
| R13 | capability outside authority scope |
| R14 | capability does not match provider tool |
| R15 | capability provider_ref differs from provider identity |
| R16 | transaction identity mismatch |
| R17 | transaction mission mismatch |
| R18 | mutation not in transaction |
| R19 | mutation authority was never consumed |
| R20 | outcome contract not frozen or not correlated |
| R22 | readback contract not authoritative |
| R23 | checkpoint does not pin the transaction |
| R24 | checkpoint does not pin the budget |
| R25 | checkpoint does not pin the outcome contract |
| R26 | checkpoint does not pin the readback contract |
| R27 | checkpoint budget differs from budget limit |
| R28 | execution receipt transaction mismatch |
| R29 | execution receipt mutation mismatch |
| R30 | execution receipt call class invalid |
| R31 | readback transaction mismatch |
| R32 | readback mutation mismatch |
| R33 | readback not produced under the frozen contract |
| R34 | readback is not from an authoritative source |
| R35 | readback is not EXISTS |
| R36 | commit observation transaction mismatch |
| R37 | commit observation mutation mismatch |
| R38 | commit observation not bound to readback |
| R39 | commit state is not COMMITTED |
| R40 | outcome receipt transaction mismatch |
| R41 | outcome receipt not bound to readback |
| R42 | outcome receipt not bound to outcome contract |
| R43 | outcome result is not PASS |
| R44 | predicates do not pass on the readback |
| R45 | completion authority hash mismatch |
| R46 | completion execution receipt hash mismatch |
| R47 | completion commit observation hash mismatch |
| R48 | completion outcome receipt hash mismatch |
| R49 | completion transaction mismatch |

(R21 is the predicate-validity check, `check_predicates`, which raises its own GuardError.)

## 4. Compensation is gated like the forward path
The grant, receipt and post-compensation readback are verified; the grant must not inherit or derive from forward authority, must name a capability outside the forward scope, must carry predicate preconditions that PASS against the forward readback (so there is something to compensate), and its goal predicates; the post readback must be correlated to this transaction, mutation and readback contract, authoritative, and satisfy the goal predicates.

## 5. Fields that are NOT enforced (stated, not hidden)
`DelegationEnvelope.expires_at` (the model is deterministic and has no clock), `PrincipalContext.roles` and `tenant`, `MissionIntent.expected_outcome_hash` (the frozen R2.0C intent carries the placeholder "PENDING"; a future freeze should bind it to the outcome contract hash), and predicate tautologies (predicates are authored and frozen before the mutation; a tautological predicate is an authoring error this model cannot detect).

## 6. Trust boundary
Guards defend against malformed, forged or inconsistent evidence and logic errors. They do not defend against hostile code in the same process (it can mutate objects or reuse the internal token). They verify consistency, not provenance: object hashes are not signatures, so a fully self-consistent forged chain that labels its readback authoritative is accepted. Lease authenticity has the same limit. Signing was declined by the owner and is an accepted, disclosed gap.
