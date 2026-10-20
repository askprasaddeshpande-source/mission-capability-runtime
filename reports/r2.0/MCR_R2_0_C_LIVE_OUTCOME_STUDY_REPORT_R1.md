# MCR R2.0C Live Outcome Study Report R1

Run: 2026-10-20, owner-authorized with the frozen phrase `AUTHORIZE_R2_0C:8CCC5B949245638B:A73F4647E0AC9B67` (freeze `8CCC5B94...DAE951`, runner `A73F4647...3DDC9`). Evidence: `evidence/r2.0/MCR_R2_0_C_LIVE_EXECUTION_RESULT_R1.json` (sanitized; raw provider responses and the lock file stay outside Git, their SHA-256 are in the result file).

**RESULT = COMMITTED_AND_OUTCOME_VALIDATED** (mission state COMPLETE). One run; evidence class **OBSERVED**, never PROVEN from a single mutation.

## What happened (call sequence, 9 calls)
initialize, notifications/initialized, tools/list (29 tools; create-tool fingerprint equal to frozen), `abap_list_destinations` (TRL_EN), baseline readback of `ZC_MCR20C_7A3F91D2` (inactive and active: both ABSENT) -> lock file created -> **one** `abap_creation-create_object` (DDLS/DF, ZCLINE): `isError:false`, "Data Definition created successfully", `semanticFilePath=/TRL_EN/.adt/ddic/ddlsources/zc_mcr20c_7a3f91d2/zc_mcr20c_7a3f91d2.asddls` -> authoritative readback (inactive and active): found, HTTP 200, type DDLS.

Mutations sent 1 of 1; retries 0; activation not performed; compensation and cleanup not used; SAP writes by the study = 1 (the frozen create).

## Distinct states, each with its own evidence
| State | Evidence |
|---|---|
| EXECUTED | ExecutionReceipt `PROVIDER_RESPONSE_SUCCESS` (provider message only) |
| COMMITTED | CommitObservation bound to a post-write DDLS-endpoint readback: EXISTS (200, found) |
| OUTCOME_VALIDATED | all 4 frozen predicates PASS on that readback: exists, type DDLS, source-hash integrity (local SHA-256 `544F9D19...85AF0` equals tool `sourceHash`), source contains object name |
| COMPLETE | completion receipt linking authority, execution receipt, commit observation, outcome receipt |

The baseline-ABSENT to post-write-EXISTS transition on the same name, obtained through a read path separate from the create call, is what distinguishes commit from the provider's success message here.

## Hypotheses (single run, scoped to one DDLS on TRL_EN; see `evidence/r2.0/MCR_R2_0_HYPOTHESIS_STATUS_R2.md`)
- H41 OBSERVED (scoped): COMMITTED established from a type-correct authoritative readback with ABSENT baseline. Not shown: the ABSENT/UNKNOWN branches live.
- H42 OBSERVED (scoped): COMPLETE reached only after predicate PASS on authoritative state. Predicates exclude package and activation.
- H43 PARTIAL: transaction and mutation ids and hashes link every receipt, and the object name appears in the create path, baseline and readback. The provider returned no transaction-correlating token; correlation of the effect to this mission rests on the fresh name, ABSENT baseline and a single mutation.
- H47 PARTIAL: 12 of the 13 specified links were emitted. The completion receipt was created and the state reached COMPLETE, but the model does not store it, so its hash is not in the emitted chain or persisted (gap; fix in a later model revision, the frozen runner is unchanged).
- H48: descriptive single observation only: governance step time 69.3 us versus provider/readback time 3.68 s in this run (excludes SSE/network inside governance). No bounded-overhead claim.
- H44, H45, H46 receive no live evidence from this run (no interruption, no compensation, no drift between prewrite and call).

## Not established by this run
- **Activation state:** the active and inactive reads returned identical payloads for the new object (and earlier for an existing one). The tool may fall back between versions; "active" cannot be asserted. The created source is the generated placeholder template (`select from DATA_SOURCE_NAME`) and is not expected to activate.
- **Package membership:** not readable through the tool; the create argument named ZCLINE but this is not verified by readback.
- **Atomicity, replay on a real failure, compensation, contract drift handling in flight.**
- **Independent second source:** no non-provider repository check. Optional owner check: refresh ZCLINE in Eclipse and look for `ZC_MCR20C_7A3F91D2` under Core Data Services.

## Residue
One disposable inactive-or-unactivated CDS data definition `ZC_MCR20C_7A3F91D2` exists in ZCLINE on TRL_EN. Deletion is not authorized or performed by this study.

## Process notes
- R1.9 untouched; the R1.9 object and its UNKNOWN state were not addressed.
- The owner pasted a bearer token into chat during R2.0B. It was never written to the repository; rotation is recommended.
