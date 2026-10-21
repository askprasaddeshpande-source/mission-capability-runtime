# MCR 3.0 Phase 0: Baseline Inspection and Scope Freeze R1

Date: 2026-10-21. Branch `work/mcr3-consolidated-evidence-outcome-runtime-r1`, created from `main` at `fd865c67c053431dc33297a0df2a3c9a02fd51fe`.

## 1. Baseline verification (all checked on 2026-10-21)
| Item | Result |
|---|---|
| `origin/main` HEAD | `fd865c6` (merge of PR #4) |
| PR #4 | MERGED, merge commit `fd865c67c053431dc33297a0df2a3c9a02fd51fe` |
| Tag `v1.9.0` | present, `2f4b85c613dab47782495242b25f51438a569fcd` (unchanged since R2.0) |
| R2.0 closure handoff | `reports/r2.0/MCR_R2_0_CLOSURE_AND_HANDOFF_R1.md` present on `main` |
| R2.0 qualification | 510 checks; 619 mutants (305 assertion, 307 crash, 1 hang, 6 explained survivors); full fresh-clone verification PASS; review 7 GO_WITH_DOCUMENTED_GAPS |

## 2. Source precedence used
Verified current source outranks historical notes. Private or inaccessible material is UNKNOWN. Classification terms: IMPLEMENTED (code exists), TESTED, INDEPENDENTLY QUALIFIED (reviewed in a clean checkout by a separate reviewer), LIVE-OBSERVED.

## 3. R2.0 capability inventory (what exists, at which level)
| Capability | Where | Level |
|---|---|---|
| 20-state mission machine, guarded transitions, atomic guards, per-Mission lock | `tools/r2.0/mcr_r2_model.py` | IMPLEMENTED, TESTED, INDEPENDENTLY QUALIFIED (offline) |
| 25 hash-addressed object kinds + JSON Schemas | `architecture/r2.0/schemas/` | IMPLEMENTED, TESTED |
| Tri-state typed outcome predicates, readback source levels | model | IMPLEMENTED, TESTED |
| Replay ledger (file-backed, OS lock, CRC, header id, per-authority limit) | model | IMPLEMENTED, TESTED (Windows only), QUALIFIED with documented limits |
| Leases + `resume()` replaying the real guards | model | IMPLEMENTED, TESTED |
| Compensation grant separation | model | IMPLEMENTED, TESTED; attempts not counted (gap) |
| 14-link chain, 50 named relations | model | IMPLEMENTED, TESTED; live run emitted 13 of 14 |
| Mutation harness, validator, verifier with external anchor | `tools/r2.0/` | IMPLEMENTED, QUALIFIED |
| Read-only readback probe + frozen live study runner | `tools/r2.0/r2_0b_*`, `r2_0c_study.py` | LIVE-OBSERVED once (one CDS object, one provider) |
| Provenance (signatures) | none | ABSENT (owner declined in R2.0) |

## 4. Outstanding-gap register carried into 3.0
IDs are stable; each gets a disposition (FIXED, DEFERRED, ACCEPTED_RISK) in the closure matrix delivered with this release.
| ID | Gap | Planned disposition |
|---|---|---|
| G01 | ledger path forms: `:` / alternate data streams, superscript device names, `CONIN$`/`CONOUT$` | FIX in the MCR 3.0 ledger |
| G02 | scanner token shapes (Claude, OpenAI, GitHub, GitLab, Google, SendGrid, Stripe, cloud) | FIX with synthetic fixtures |
| G03 | compensating-call attempts not counted | FIX (bounded separate grant, per-attempt accounting) |
| G04 | `_consume_file` / `_sync` thread-lock decorators untestable | FIX by removing the redundant decorator layer and testing the invariant instead |
| G05 | 307 of 619 R2.0 mutant detections are validator crashes | FIX for the 3.0 code via targeted assertions; carry the R2.0 count as history |
| G06 | unenforced fields (`expires_at`, `roles`, `tenant`, `intent.expected_outcome_hash`, `readback.activation`, `readback_contract.checks`) | FIX where an offline invariant exists; roles are never treated as verified identity |
| G07 | R51 prefix test accepts an empty tail | FIX in the 3.0 contract (new explicit contract version) |
| G08 | ledger restore of an older copy, deletion without a pinned id | PARTIAL: detect when an independently verifiable anchor exists; document otherwise |
| G09 | A13a to A13f verifier attacks never completed | RE-RUN memory-bounded in isolation, or record NOT_VERIFIED |
| G10 | no provenance signatures | FIX: pluggable verification interface, offline test identities; production keys NOT created |
| G11 | single live run, link 14 never live, activation/package unproven, no independent second readback | DEFERRED: needs a separately authorized live study |
| G12 | POSIX locking, network filesystems, power-loss durability untested | DEFERRED / documented guarantees per platform |
| G13 | ADT token rotation declined; CDS view `ZC_MCR20C_7A3F91D2` left | ACCEPTED_RISK (owner) |

## 5. Claude Mods: what the real source shows (read-only)
Source: `D:\PRASAD_AI_ENGINEERING\claude-mods-v3-corrections-work` (branch `work/v3-v5-integration-r1`, HEAD `834694d`). Also seen: `claude-mods` (docs-only repository), and other work trees. Nothing was modified and nothing from it is imported.
| Fact (from source) | Source | Consequence for MCR 3.0 |
|---|---|---|
| An existing shared envelope exists: `pe-event/1` (`contracts/pe-event.schema.v1.json`): fields schema, event_id (idempotency key), source, kind, ts, producer_id, seq, evidence_class, ids{mission_id, session_id, task_id, context_compile_id, outcome_id, run_id, case_id}, arm, cohort, component, component_version, data | contracts/ | REUSE the semantics (idempotent event id, append-only, evidence class, nullable unknowns); do NOT fork it |
| `additionalProperties:false`; `source` and `kind` are closed enums; the collector keeps only per-kind allowlisted scalar safe strings and silently strips the rest | `pe-event.schema.v1.json`, `telemetry/backend/normalize.mjs`, `ACLA_EAF_MCR_EVENT_CONTRACT_R1.md` | An MCR event cannot be ingested without a Claude Mods schema change: deliver a bounded CHANGE PACKET; do not edit Claude Mods |
| Existing kinds `eaf.authorization` and `eaf.outcome_assurance` (file-scope readback) | same | Map MCR facts to scalar fields in a proposed new additive version; never reuse `authorization_hash` as an envelope hash (their own rule) |
| `pe-event-ext-1` correlation fields (`correlation_id`, `causation_id`) and a proposed `pe-event-ext-2` with 8 reserved null-only MCR identities | `docs/ACLA_EAF_MCR_EVENT_CONTRACT_R1.md`, `docs/MCR_CONTRACT_COMPATIBILITY_MATRIX.md` | Align the MCR 3.0 canonical field names with those reservations |
| Compatibility matrix tally against MCR R1.9 envelopes: PRESENT 1, PARTIAL 5, MISSING 12, MCR-OWNED 1 (19 fields); no MCR adapter exists; MCR coupling NONE; P4 authority NONE | `docs/MCR_CONTRACT_COMPATIBILITY_MATRIX.md`, `telemetry/evidence-center/mcr.json` | Evidence Center shows MCR "NOT_CONNECTED / adapter NOT_IMPLEMENTED"; 3.0 supplies the adapter side only |
| Governance: authority matrix is advisory data; later states are never inferred from earlier states; release approval by owner; release/launch verified by detached SSH signatures (`ssh-keygen -Y`) against an owner-pinned `allowed_signers` trust root, with revocation and rollback refusal tested | `contracts/authority-matrix.json`, `security/signing-policy.md`, `security/v5/verify-package.sh` | The 3.0 provenance interface must be able to wrap an SSH-signature verifier; MCR must not create a competing approval system |
| UNKNOWN (not read): the live Governor decision logic, owner approval records, signing keys, the live collector store, Evidence Center writeback | n/a | Treated UNKNOWN; mock consumers are used instead |

## 6. Reuse decision
No existing contract implementation covers MCR outcome evidence (verified: no MCR consumer, producer or event kind). Reuse: the `pe-event/1` idempotency/evidence-class/null-means-unknown conventions and the 8 reserved identity names. Create: an MCR-side, version-independent Evidence Contract v1 and a one-way mapping to `pe-event` scalars. External vocabulary is borrowed, not imported (section 7).

## 7. Frozen scope and acceptance plan
Code lives in new directories only: `tools/mcr3/`, `architecture/mcr3/`, `evidence/mcr3/`, `reports/mcr3/`. R1.9 and R2.0 files are not modified. Standard library only for the runtime; optional libraries (`cryptography`, `jsonschema`) are used only in clearly optional paths and tests, and tests record NOT_VERIFIED when a library is absent.
External specifications pinned (concepts borrowed, version recorded in the contract): CloudEvents 1.0.2 (event envelope attributes), OpenTelemetry semantic conventions as an attribute-naming reference (no SDK dependency), in-toto Attestation Framework v1 Statement/predicate layout (subject digests, predicateType), MCP authorization specification 2025-06-18 (resource/tool scoping vocabulary), OWASP Top 10 for Agentic Applications / Agentic AI Threats and Mitigations (threat checklist). No network access is used to fetch them; the pins record what the contract text cites, and the actual text was not re-read in this session (UNKNOWN until verified by a reader with network access).

| Milestone | Weight | Acceptance evidence |
|---|---|---|
| M0 Baseline, architecture and contract freeze | 10% | this file, architecture decision record, contract skeleton |
| M1 R2.0 gap hardening in the 3.0 lineage | 20% | hardened ledger/compensation/validation/scanner with tests, closure matrix G01-G13 |
| M2 New 3.0 capabilities (Evidence Contract v1, provenance, authority states, outcome runtime) | 30% | schemas, runtime, tests, negative fixtures |
| M3 Adapters and Claude Mods interoperability | 15% | R2.0 reference adapter, 3.0 native adapter, mock consumer, ten mandatory scenarios, change packet |
| M4 Independent qualification | 20% | full test run, mutation classification, fresh clone, isolated reviewer verdict |
| M5 Consolidated PR package | 5% | one draft PR package; no merge, no tag |

## 8. Boundaries restated
SAP writes 0. No production signing credentials created. No capability is promoted to production trust. INTEROPERABILITY_DOES_NOT_IMPLY_AUTHORITY. Merge and release tag need separate owner approval.
