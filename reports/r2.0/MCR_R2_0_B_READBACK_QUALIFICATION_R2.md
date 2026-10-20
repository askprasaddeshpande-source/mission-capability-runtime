# MCR R2.0B Read-Only Readback Qualification R2

Supersedes R1 (retained, offline-only). Adds a live read-only probe of the ADT MCP provider. SAP writes: 0. Raw provider responses are kept outside Git; this report and `evidence/r2.0/MCR_R2_0_B_LIVE_READONLY_PROBE_SUMMARY_R1.json` carry hashes and classifications only. The bearer token was supplied by the owner in chat, used once to build a DPAPI-protected context outside Git, and appears in no repository file.

**R2_0_B_AUTHORITATIVE_READBACK_QUALIFICATION = PARTIAL** (live; existence/active/source readback for the intended object type is still NOT_ESTABLISHED)

## Live observations (OBSERVED, destination TRL_EN, 18 read calls, 0 writes)
| Observation | Result |
|---|---|
| Provider reachable at loopback 2234, session protocol initialize -> notifications/initialized -> tools/list | OBSERVED |
| Destination `TRL_EN` listed by `abap_list_destinations` | OBSERVED |
| **Contract drift since R1.8**: 29 tools (R1.8: 20). 9 `capella_adt_*` tools added; `abap_atc_run`, `abap_activate_objects`, `abap_run_unit_tests` changed input schema; `abap_atc_run` description changed | OBSERVED (H46-relevant: drift detected by comparison; not yet handled by a runtime gate) |
| `abap_activate_objects` URI semantics changed: URIs must now be relative to the Eclipse project (`/ProjectName/path/...`) | OBSERVED (relevant to the R1.9 URI/`filePath` gap; consequence for any R2.0C activation) |
| `abap_atc_run` positive and negative control both returned `isError` with the identical text "Error executing tool: null" | OBSERVED; classification UNKNOWN. ATC did not discriminate; cause (argument shape vs changed schema, or object state) not diagnosed |
| `capella_adt_repository_read_metadata` for the existing class control and for a random name returned identical-shape `found:false`, HTTP 404, "Data definition ... does not exist", `isError:false` | OBSERVED. The tool queries the **DDLS endpoint only** (`NOT_FOUND_VIA_DDLS_ENDPOINT`); for a class this 404 is wrong-endpoint, **not absence**. Mapping it to ABSENT would be a false negative |
| `capella_adt_class_read_source` on `TRL_EN` | refused by provider scope gate "destination outside DF-P1 class scope"; not circumvented |

## Updated classification
| Item | R1 | R2 | Basis |
|---|---|---|---|
| READBACK_PROVIDER / session / fingerprint | OBSERVED (historical) | OBSERVED (live) | above; fingerprint **differs** from R1.8 |
| Class existence / active / source readback on TRL_EN | PARTIAL | NOT_ESTABLISHED | ATC UNKNOWN; DDLS tool wrong type; class-source tool gated |
| DDLS (CDS view) existence, active/inactive, source hash, elements | NOT_ESTABLISHED | PARTIAL: tool exists and returns a structured not-found for a non-existent DDLS name format, but **no positive control run** | no existing DDLS name supplied yet |
| Activation state readback | NOT_ESTABLISHED | PARTIAL for DDLS (`version` active/inactive parameter), NOT_ESTABLISHED for classes | tool schema only |
| Source hash readback | NOT_ESTABLISHED | PARTIAL for DDLS (tool returns `sourceHash`; must be recomputed locally from source, since for errors it hashes the error body) | tool output only |
| ATC readback | PARTIAL | UNKNOWN (did not run) | above |

## Consequence for R2.0C
- A **class**-based study cannot establish COMMITTED on TRL_EN with the current provider: no working authoritative readback. Do not freeze it.
- A **DDLS-based** study is the candidate: the provider exposes active/inactive read, source, hash and elements for DDLS, and a structured not-found for absent objects. This remains a hypothesis until a positive control confirms `found:true`, `sourceType` DDLS and a source whose locally computed SHA-256 matches the tool's `sourceHash`, and until active vs inactive behaviour is shown on an existing object.
- Whatever the object type, the model rule stands: only a type-correct endpoint result may produce ABSENT. A `found:false` is ABSENT only when `sourceType` and the HTTP/exception identity (`ExceptionResourceNotFound`) belong to the endpoint that serves that object type. Otherwise UNKNOWN.
- The provider's own write tools (`capella_adt_*_save_inactive`) carry a plan-hash/expected-source-hash gate and state "activation is not performed". They belong to a separate owner project, are not part of the retained R1.8 contract, and are not used or evaluated for write here. Any R2.0C mutation tool must be chosen and frozen explicitly with its own fingerprint.

## Next read-only step (needs one owner input)
Supply the name of **one existing DDLS in package ZCLINE on TRL_EN** (Project Explorer: ZCLINE > Core Data Services). The probe then reads it as `active` and `inactive`, hashes the returned source locally, and compares with the tool's `sourceHash`.

## Blockers
None for read-only work. BLOCKER_A (fresh live write) is not yet reached; the packet cannot be frozen before the DDLS control above and a decision on the mutation tool and outcome contract.
