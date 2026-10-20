# MCR R1.9 Architecture

## Purpose

Mission-Capability Runtime (MCR) is the deterministic runtime between probabilistic agent reasoning and executable enterprise capabilities.

It does not replace MCP, gateways, registries, identity systems, enterprise authorization or systems of record.

## Core flow

```text
Mission State
   |
   v
Capability Requirement
   |
   v
Minimum Capability Working Set (MCWS)
   |
   v
LLM semantic proposal
   |
   v
Deterministic MCR admissibility
   |
   v
Provider binding
   |
   v
Point-of-use revalidation
   |
   v
Execution
   |
   +--> ExecutionReceipt
   |
   v
Authoritative observation
   |
   +--> OutcomeReceipt
   |
   v
Mission transition / block / recompose / partial
```

## Authority

```text
EffectiveExecutionAuthority =
    ProviderAuthority
  ∩ UserAuthority
  ∩ AgentAuthority
  ∩ MissionAuthority
  ∩ TemporalAuthority
  ∩ CapabilityAuthority
  ∩ TargetAuthority
  ∩ TransactionAuthority
```

No model output can expand that intersection.

## R1.9 runtime objects

- PrincipalContext
- DelegationEnvelope
- MissionExecutionEnvelope
- MutationBudget
- TransactionEnvelope
- ExecutionReceipt
- OutcomeReceipt
- CompensationGrant
- ContractLease
- MissionCheckpoint
- ContinuationLease

## Invariants

- DISCOVERABLE != AUTHORIZED
- TRUSTED_TO_DESCRIBE != AUTHORIZED_TO_EXECUTE
- LLM_PROPOSAL != EXECUTION_AUTHORITY
- delegated authority cannot amplify
- stale authority fails closed
- VERSION_EQUALITY != CONTRACT_EQUALITY
- EXECUTION_RECEIPT != VALIDATED_OUTCOME
- EXECUTED != COMPLETE
- compensation requires separate authority
- replay after ambiguous side effect is prohibited
- checkpoint state does not imply mutation replay permission

## R1.9B live boundary

```text
Target      TRL_EN
Object      ZCL_MCR19B_9533C4D8
Package     ZCLINE
Provider    ADT
Mutations   CREATE, ACTIVATE
Budget      2
Retries     0
Compensate  FALSE
Cleanup     FALSE
```

Final live attempt:

```text
initialize
-> capture session
-> notifications/initialized
-> tools/list
-> single-use lock
-> CREATE
-> response
-> filePath extraction
-> CREATE_FILEPATH_MISSING
-> STOP
```

ACTIVATE was not reached.

Commit state after CREATE remains unknown at this draft.
