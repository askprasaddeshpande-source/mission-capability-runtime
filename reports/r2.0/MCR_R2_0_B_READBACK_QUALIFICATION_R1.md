# MCR R2.0B Read-Only Readback Qualification R1

Stage: `R2_0_B_AUTHORITATIVE_READBACK_QUALIFICATION`. SAP writes: 0. Provider calls this session: 0.

**R2_0_B_AUTHORITATIVE_READBACK_QUALIFICATION = PARTIAL** (offline contract analysis only; live read-only qualification NOT executed: BLOCKER_B).

## Why no live qualification
- ADT MCP provider (Eclipse-hosted, loopback port 2236 in the retained R1.8 record): port not listening, no Eclipse/Java process running (checked this session).
- The retained ADT auth context used by R1.8/R1.9 (`ADT_AUTH_CONTEXT_R1.json`, DPAPI-protected, outside Git) is not present on this machine.
- Other providers (Fiori, UI5, CAP) are local-workspace providers and cannot read an SAP repository. The configured `sap-fullstack-qualifier` MCP is a static application-contract analyzer, not a repository readback. A filename search also surfaced DPAPI files belonging to unrelated projects; they were neither opened nor used.

## What the retained evidence establishes (offline, historical)
| Item | Classification | Basis |
|---|---|---|
| READBACK_TARGET_IDENTITY | PARTIAL | destination `TRL_EN`, package `ZCLINE` recorded in R1.7/R1.9 evidence; not re-observed |
| READBACK_PROVIDER | OBSERVED (historical) | `SAP_ADT_MCP`, "ADT MCP Server" 1.0.0, streamable HTTP, protocol 2025-06-18, 20 tools (R1.8 HF04) |
| READBACK_CAPABILITY | PARTIAL | no dedicated read-object, get-source or search tool among the 20; `abap_atc_run` + `abap_atc_get_result` are the only post-write observation path |
| READBACK_AUTHORITY_LEVEL | PARTIAL | ATC is backend-computed analysis (model level `PROVIDER_VALIDATION`) until negative-control discrimination is shown |
| OBJECT_EXISTENCE_READBACK | PARTIAL | one documented ATC result listing name, CLAS, ZCLINE, findings=[] for an existing object (R1.7 P6-D1); ABSENT behavior untested |
| ACTIVATION_STATE_READBACK | NOT_ESTABLISHED | no tool returns active/inactive state; `abap_activate_objects` is a mutation |
| SOURCE_HASH_READBACK | NOT_ESTABLISHED | only `abap_transport-unifiedDifference`, which needs a transport (creating one is a mutation) |
| PACKAGE_READBACK | PARTIAL | package appears in the single documented ATC listing |
| ATC_RESULT_READBACK | PARTIAL | result tool returns checked-object count and findings by priority; the run can be unfinished; the first call timed out at 30 s in R1.7 |
| CONTRACT_FINGERPRINT | OBSERVED (historical) | normalized live equals reference `52B73C57...7E166` in R1.8 (tool names match, 20 tools) |
| SESSION_PROTOCOL | OBSERVED (historical) | initialize, then `notifications/initialized`, then `tools/list`; SSE framing and session id (R1.9 raw) |
| FILE_URI_REQUIREMENTS | PARTIAL | `abap_activate_objects` takes `uris` from the `create_object` `filePath`; format not re-observed |

## Lesson carried from R1.9
A retained `abap_creation-run_validation` response was `isError: true` ("Unable to initialize the ADT Discovery"). Any readback that errors must map to `UNKNOWN`, never `ABSENT`. The probe encodes this: silence and any error that is not an explicit "not found" map to UNKNOWN.

## Sufficiency for H41/H42
- **H41 (commit observation):** only possible for existence, type and package, and only through ATC. Reaching `AUTHORITATIVE_REPOSITORY` for that scope needs a live positive/negative control showing ATC distinguishes EXISTS, ABSENT and UNKNOWN. NOT_ESTABLISHED today.
- **H42 (outcome-authoritative completion):** an outcome contract with `active` or `source_sha256` predicates cannot be evaluated with this provider; those stay UNKNOWN and COMPLETE would be unreachable. Either the contract is restricted to what is readable, or another authoritative route is needed (for example a direct ADT REST repository read against the SAP system, which needs SAP system credentials not available to this session; its endpoints are not verified here).

## Redesign decision
R2.0C is **not frozen**. The frozen outcome contract must be derived from the B result:
1. If live controls show ATC discriminates, restrict the contract to {exists, type, package, findings}. Record activation and source hash as NOT_ESTABLISHED scope limits, not silently dropped.
2. If ATC does not discriminate, R2.0C cannot establish COMMITTED. No live mutation until an authoritative route exists.

## Prepared for the owner (read-only)
`tools/r2.0/r2_0b_readonly_readback_probe.py`:
- allowlist-only client (initialize, tools/list, `abap_list_destinations`, `abap_atc_run`, `abap_atc_get_result`); mutation tools are refused in code before any network I/O (tested);
- loopback endpoint only; token read from the DPAPI context and never printed; raw responses written outside Git;
- positive control (existing R1.7 object, not the R1.9 object) plus a fresh random negative-control name;
- the verdict is only a proposal and `ADJUDICATION_REQUIRED` is always true.

Tested only against an in-process mock, which says nothing about the real provider. Not executed live.

**Blocker (BLOCKER_B):** needs the ADT MCP provider running (Eclipse with ADT MCP, loopback) and a valid ADT auth context.
