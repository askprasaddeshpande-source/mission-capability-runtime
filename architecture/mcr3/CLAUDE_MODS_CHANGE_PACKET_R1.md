# Claude Mods Change Packet R1 (a packet, NOT a change)

Nothing in the Claude Mods repositories was modified by MCR 3.0. This packet lists what the Claude Mods side would have to change so that MCR evidence can be ingested, and what MCR 3.0 already provides. Source facts come from the read-only inspection of `claude-mods-v3-corrections-work` (branch `work/v3-v5-integration-r1`, HEAD `834694d`): `contracts/pe-event.schema.v1.json`, `telemetry/backend/normalize.mjs` behaviour as documented in `docs/ACLA_EAF_MCR_EVENT_CONTRACT_R1.md`, and `docs/MCR_CONTRACT_COMPATIBILITY_MATRIX.md`. The live Governor logic, owner approval records, signing keys and the live collector store were NOT read (UNKNOWN).

## 1. What MCR 3.0 provides (tested against mocks)
- `mcr-evidence/1` events, version-independent, with `authority_effect = NONE`.
- A one-way mapping `mcr3_interop.to_pe_event()` to a `pe-event/1`-shaped envelope with scalar safe-string `data` only, using a proposed source `MCR_EVIDENCE` and kind `mcr.evidence`.
- A mock collector that enforces the documented rules (closed enums, per-kind allowlist, strip-and-count, idempotent event id) and a mock Evidence Center that keeps the original canonical event next to the normalized form.
- Ten interoperability scenarios and the consumer compatibility matrix as executable fixtures (`tools/mcr3/validate_mcr3_adapters.py`, `validate_mcr3_evc1.py`).

## 2. Changes needed on the Claude Mods side (proposed, in dependency order)
| # | Change | Why | Risk if skipped |
|---|---|---|---|
| 1 | Add source `MCR_EVIDENCE` and kind `mcr.evidence` in a NEW additive contract version (the current enums are closed) | today's collector rejects both (scenario 8) | MCR events are rejected; nothing else breaks |
| 2 | Add to `x-kind-data` for `mcr.evidence` exactly these keys: contract_version, event_type, layer, claim_kind, adapter_id, adapter_version, source_runtime_version, trust, mcr_class, authority_effect, evidence_digest, content_digest, outcome_class, disposition, result, call_class, commit_state, source_level, existence, activation, claimed_authoritative, provenance_verified, attempt_number, capability_state, capability_id | the collector strips unlisted fields silently | fields lost without error |
| 3 | Confirm the collector's secret-like-value filter accepts 64-hex digests under `*_digest` names (their `evidence_hash` already carries one) | digest values must survive normalization | `content_digest` stripped; original-vs-normalized linkage lost |
| 4 | Evidence Center `mcr` view: show adapter id/version, trust floor, disposition and outcome class; never display "correct"; reuse the rule in `MockEvidenceCenter.evaluate` (best case: "evidence supports the recorded outcome") | the current view reports `runtime NOT_CONNECTED / adapter NOT_IMPLEMENTED` | overstating correctness |
| 5 | Implement an `ApprovalVerifier` against the Governor's real approval record, outside MCR | MCR ships a deny-all default; approval format is UNKNOWN to this work | no capability can reach APPROVED (fail closed) |
| 6 | If MCR adapters are ever signed, reuse the existing SSH `allowed_signers` trust root and revocation list (MCR's `SshSigVerifier` uses `ssh-keygen -Y verify`, namespace `mcr-evidence`) | one trust root, no competing one | two trust roots |

## 3. Field correspondence with the reserved `pe-event-ext-2` identities
| Reserved name | MCR 3.0 field | Status |
|---|---|---|
| transaction_id | `correlation.transaction_id` (mapped to `ids.outcome_id`) | present |
| principal_context_hash | `principal.principal_ref` | present (assurance SELF_REPORTED unless SIGNED_TRUSTED) |
| outcome_contract_hash | `claim.expected_digest` of `mcr.outcome.evaluated` | present (null for HISTORICAL R2.0 evidence) |
| execution_envelope_id, envelope_hash, authority_graph_hash, mission_version, lease_hash | none in contract 1.0 | MISSING: candidates for optional fields in a 1.x minor version; they must not be invented from other hashes (the Claude Mods rule: `authorization_hash` is never an envelope hash) |

## 4. Not done, not authorized
No change to any Claude Mods repository, collector, plugin, schema or signed release; no connector, no live ingestion; no production signing key; no approval was issued or verified; the Governor was not contacted. Integration infrastructure was not built.

## 5. Acceptance check once the change is made (on the Claude Mods side)
Replay the 11 example events in `architecture/mcr3/contracts/evidence-v1/examples/` through `to_pe_event` and the real collector: all stored once (idempotent re-send), none stripped except documented lossy fields, existing native events unchanged, `authority_effect` always `NONE`, no MCR event changes any Governor decision.
