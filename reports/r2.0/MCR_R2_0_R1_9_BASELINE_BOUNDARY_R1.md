# MCR R2.0 — R1.9 Baseline Boundary R1

R2.0 starts from `origin/main` (8128ef5) with release tag `v1.9.0` -> commit 9c5105f unchanged.

## Frozen R1.9 facts (carried verbatim, not re-litigated)
| Item | Value |
|---|---|
| MCR_R1_9 | BOUNDED_CLOSURE_WITH_UNRESOLVED_CREATE_COMMIT_STATE |
| R1_9B_CREATE_REACHED_PROVIDER | TRUE (ADT MCP provider; SAP back-end reach NOT_ESTABLISHED) |
| R1_9B_ACTIVATE_REACHED_PROVIDER | FALSE |
| R1_9B_CREATE_COMMIT_STATE | UNKNOWN |
| AUTHORITATIVE_REPOSITORY_READBACK | FALSE |
| HF06_REPLAY_AUTHORIZED | FALSE |
| OLD_AUTHORIZATION_REUSE_AUTHORIZED | FALSE |

## What R2.0 inherits as lessons (not as evidence)
- The R1.9B retained validation response was an error (`isError: true`, "Unable to initialize the ADT Discovery"); an error response carries no information about object state. R2.0 readback must therefore return UNKNOWN on provider errors, never ABSENT.
- Absence of an existence signal is not ABSENT.
- R1.9 outcome contract used ATC identity/package match as the validator; R2.0 must show an ATC result is not by itself a repository readback of source/activation state.

## Prohibitions
No HF06 rerun, no HF07, no reuse of old authorization, no new experiment aimed at resolving the R1.9 UNKNOWN, no change to R1.9 evidence, no new use of object `ZCL_MCR19B_9533C4D8`. Any R2.0 object gets a fresh identity.
