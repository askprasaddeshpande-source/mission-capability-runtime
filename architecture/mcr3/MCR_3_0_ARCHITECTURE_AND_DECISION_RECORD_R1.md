# MCR 3.0 Architecture and Decision Record R1

Release line 3.0.0 (offline engineering release candidate). Baseline: `main` at `fd865c67c053431dc33297a0df2a3c9a02fd51fe` (MCR R2.0, PR #4). Branch: `work/mcr3-consolidated-evidence-outcome-runtime-r1`.

## 1. Decision (immutable for this release)
**ARCHITECTURE_DECISION = VERSION_INDEPENDENT_EVIDENCE_CONTRACT.**
- **MCR 2.0** stays the frozen reference model, historical test oracle and scientific baseline. It is not upgraded in place. The 3.0 runtime is a fork (`tools/mcr3/mcr3_model.py`) with its own version and its own qualification; the R2.0 validator is carried over as an inherited regression suite.
- **MCR 3.0** adds capabilities, a canonical evidence contract, provenance verification, capability/adapter governance, adapters and qualification rules.
- **Claude Mods** keeps its observability, ACLA/EAF governance, Evidence Center and owner-approval controls. It consumes MCR evidence through the canonical contract and a one-way mapping; it never imports MCR internals, and MCR never imports Claude Mods code.
- **Invariant: INTEROPERABILITY_DOES_NOT_IMPLY_AUTHORITY.** An adapter, a runtime version, a signature or an evidence event cannot become production authority by existing. Verification, qualification, approval and execution authorization are four separate things.

## 2. Layers and what each can say
| Layer | Can say | Cannot say |
|---|---|---|
| OCCURRENCE | something happened (an attempt, a state change) | that it succeeded |
| RECEIPT | a party reported something (provider call result, readback, commit reading) | that the report is true |
| VERIFIED_FACT | an independent check of another event's hash, signature, producer, trust or freshness | that the business outcome occurred |
| BUSINESS_OUTCOME | expected versus observed outcome evaluated; a mission disposition | that the evidence was authentic (that is provenance) |
| AUTHORIZATION_REFERENCE | an approval exists elsewhere, with this scope | any authority (MCR grants none) |
Outcome classes (derived, never input): EXECUTED, PROVIDER_ACKNOWLEDGED, COMMIT_OBSERVED, OUTCOME_OBSERVED, OUTCOME_VALIDATED, COMPLETE, COMMIT_UNKNOWN, OUTCOME_UNKNOWN, COMPENSATION_REQUIRED, UNRECOVERABLE. A provider success message is not a commit observation; a commit observation is not a validated outcome; a signature is not proof that an outcome happened.

## 3. Module map (all under `tools/mcr3/`, standard library only)
| Module | Role |
|---|---|
| `mcr3_model.py` | 3.0 runtime: state machine, hash-addressed objects, guards, replay ledger (+ anchor), leases, bounded compensation attempts, outcome classification |
| `evc1.py`, `mini_jsonschema.py` | Evidence Contract v1: schema, canonical form, trust derivation, compatibility and migration; dependency-free schema validator |
| `mcr3_provenance.py` | hash / signature / issuer trust / freshness / replay as separate findings; HMAC (test only), Ed25519, SSHSIG back-ends |
| `mcr3_authority.py` | capability states DISCOVERED to REVOKED; adapter declarations and modes; qualification never approves |
| `mcr3_adapters.py` | Adapter A (frozen R2.0 evidence) and Adapter B (native 3.0) |
| `mcr3_lineage.py` | append-only store with supersession |
| `mcr3_readback.py` | provider-neutral readback rules; offline SAP/ADT-style reference provider (not verified live) |
| `mcr3_interop.py` | one-way mapping to the `pe-event/1` scalar envelope; mock collector and Evidence Center |
| `mcr3_scan.py` | credential-shape scanner with synthetic fixtures |
| `verify_mcr3.py`, `run_mcr3_tests.py`, `run_mcr3_mutation_check.py`, `run_mcr3_verifier_attacks.py`, `bench_mcr3_overhead.py` | qualification tooling |

## 4. Reuse decision (from source, see Phase 0)
No existing implementation covers MCR outcome evidence. Reused: the `pe-event/1` conventions (idempotent event id, append-only, nullable-unknown, evidence class) and the 8 identity names reserved by the Claude Mods `pe-event-ext-2` proposal. Created: an MCR-side Evidence Contract v1 and the mapping. The Claude Mods collector's closed enums and scalar-only allowlist mean ingestion needs a change in that project; see `CLAUDE_MODS_CHANGE_PACKET_R1.md` (a packet, not a change).

## 5. External vocabulary (borrowed, not imported; pinned)
CloudEvents 1.0.2, in-toto Attestation Framework v1, OpenTelemetry semantic-convention naming, MCP authorization 2025-06-18, OWASP agentic-AI guidance. The pins record what the contract cites; the specifications' texts were not re-read during this work and no network access was used (their exact wording is UNKNOWN to this record).

## 6. What 3.0 does not claim
Offline qualification does not prove enterprise production behaviour. R2.0's single live observation is unchanged; its link 14 was never emitted live, its readback did not establish activation or package membership, and its evidence was not cryptographically authenticated. Nothing in 3.0 promotes a hypothesis. A new SAP activation, package, independent readback or failure-path study needs a separate live-study authorization.
