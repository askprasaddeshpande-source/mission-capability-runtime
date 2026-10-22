# MCR 3.0 Acceptance Matrix, Migration Guide and Claim Ledger R1

Status vocabulary: IMPLEMENTED (code exists), TESTED (offline tests pass), EXTERNALLY_VERIFIED (a reviewer other than the implementing agent reproduced it), LIVE_OBSERVED (seen on a real system), PRODUCTION_QUALIFIED. Nothing in 3.0 is LIVE_OBSERVED or PRODUCTION_QUALIFIED. "Independent" reviews so far were isolated agents of the same model lineage: **not fully independent**.

## 1. Requirement to code, tests and evidence
| Mission item | Code | Tests (suite) | Status | Residual |
|---|---|---|---|---|
| P1 delegation expiry, point-of-use | `Mission._expiry_guard`, `parse_expiry` | inherited, gaps, hardening | TESTED, EXTERNALLY_VERIFIED (reviews 8, 9) | microsecond precision; lenient ISO forms (N06) |
| P1 typed principal, tenant, roles | `Mission.context_ready` | phase1_authority (`PRINCIPAL_TYPING`) | TESTED | still SELF_REPORTED, not verified identity |
| P1 revocation of principal / delegation / authority | `RevocationList`, `Mission._revocation_guard` (authorize, send, compensating send; fail closed on raise or any non-False answer) | phase1_authority (`REVOCATION`) | TESTED | no source connected means nothing is checked; no real revocation service; credential-expiry is covered only through delegation `expires_at` |
| P1 capability promotion, attenuation, single use | `attenuated`, single_use guard, `mcr3_authority` registry, `AdapterRegistry.promote` (verified, scoped, bound, unexpired approval) | inherited, authority | TESTED, EXTERNALLY_VERIFIED (gate review) | verifiers are test doubles; no Governor connected |
| P1 no permission from available tools | provider/capability binding R51, DenyAll default verifier | inherited, authority | TESTED | binds provider system, not tool/object |
| P2 shared replay ledger, cross-process, threads | `ReplayLedger` (OS byte-range lock + RLock, CRC lines) | hardening, inherited | TESTED on Windows/NTFS | POSIX, network FS, power loss NOT_VERIFIED |
| P2 identity, generation, rollback, deletion detection | ledger id, `anchor()/check_anchor()`, lease carries anchor | hardening `LEDGER_ANCHOR` | TESTED | detects only if the anchor is held elsewhere |
| P2 budget before send, compensation consumes authority | `begin_execution`, `begin_compensation` | inherited, hardening | TESTED | model records a send; it cannot stop a caller calling the provider |
| P2 stale leases, forged checkpoints | `resume()` re-runs real guards, ledger union | inherited, hardening | TESTED, attacks A2/A5 refused (independent R2.0 re-check on fd865c6) | lease integrity is a hash, not a signature |
| P3 provenance and trust model | `mcr3_provenance`, `evc1.derive_trust` | authority, evc1 | TESTED (216 combinations) | no production key; HMAC test-only |
| P3 correlation, expected_outcome_hash, readback contract, 14 links, relations R01-R54 | `Mission.complete`, `chain_hashes`, `mcr3_chain` | inherited, chain | TESTED | |
| P3 per-version readback, ABSENT tied to object, active/inactive | `mcr3_readback.py` | readback | TESTED offline | SAP-style rules NOT verified live |
| P3 optional offline signatures | Ed25519 / SSHSIG / HMAC verifiers, disposable keys | authority | TESTED (backends skip with NOT_VERIFIED when tool absent) | no production signing authority created; historical observations not signed |
| P4 event adapter (ACLA, EAF, Claude Mods, MCR receipts) | `evc1`, `mcr3_adapters`, `mcr3_interop` (contract boundary, mocks) | evc1, adapters | TESTED against mocks | ACLA/EAF/Claude Mods repositories not read live or modified; change packet only |
| P5 CI gates | `.github/workflows/mcr3-offline.yml` | CI | see CI status in the PR; never inferred | heavy tier manual |
| P5 exact-byte vs canonical checksums | `verify_mcr3.py` sums are exact bytes; `.gitattributes` keeps evidence bytes | verify | TESTED | R2.0 sums are CRLF-insensitive (independent R2.0 review note) |
| P5 external anchor | `--expect-sums-sha256`; CI variable `MCR3_SUMS_ANCHOR` | verify | TESTED (attack suite) | without an anchor the verifier is self-attesting |
| P5 secret scanning tree + history | `scan_tracked_tree`, `scan_history`, `scan_history_mcr3.py` + reviewed false-positive list | scan (`HISTORY`) | TESTED; history scan of this repo: 2 reviewed false positives, 0 unreviewed | heuristic; documented unsupported formats |
| P5 reserved names, traversal, ADS | `_check_ledger_path` | hardening | TESTED | |
| P5 token | exposed ADT token treated as exposed; never read or used | n/a | BLOCKED_SECURITY_DEPENDENCY for any authenticated live work | owner must rotate |
| P5 unsigned historical scripts | not modified; MCR 3.0 adds no PowerShell | n/a | ACCEPTED_RISK | |
| P6 mutation, A13a-f | `run_mcr3_mutation_check.py`, `run_mcr3_verifier_attacks.py` | see qualification report | 1,580 mutants (0 unexplained) + authority-gate module re-run; 22/22 attacks | 42% of detections are validator crashes |
| P7 live-study package | `architecture/mcr3/MCR_3_0_LIVE_STUDY_PACKAGE_R1.md` | n/a | PREPARED, NOT EXECUTED | |

## 2. Migration R2.0 to R3.0
- R2.0 code and evidence are untouched; 3.0 is a forked lineage under `tools/mcr3` (module `mcr3_model`, version 3.0.0). R2.0 is not upgraded in place.
- Leases: 3.0 leases carry a ledger anchor; R2.0 leases are not accepted.
- `Mission.resume` needs a `ReplayLedger` and re-presented evidence (also in R2.0 main); `revocation_check` is optional.
- New enforced fields: `expires_at` (UTC), `intent.expected_outcome_hash` must equal the frozen outcome contract hash, readback `checks`, exact `provider_ref`.
- Historical R2.0 evidence converts only as HISTORICAL, unsigned, INCOMPLETE (13 of 14 links) via `Mcr2ReferenceAdapter`; it is never relabelled.
- Adapters start OBSERVATION_ONLY; promotion needs an externally verified approval.

## 3. Hypothesis and claim ledger
| Claim | Class | Basis | Status |
|---|---|---|---|
| H41, H42 (R2.0C) | LIVE_OBSERVED (scoped, historical, single run) | frozen R2.0C evidence | unchanged, not replicated, not promoted |
| H43, H46, H47, H48 | PARTIAL (R2.0) | frozen evidence + erratum (13 of 14 links) | unchanged |
| H44, H45 | SYNTHETIC | offline models | 3.0 strengthens the offline tests only |
| MCR 3.0 runtime guards (authority, replay, evidence chain, revocation) | TESTED offline | this repository | not LIVE_OBSERVED |
| Evidence Contract v1 | IMPLEMENTED + TESTED; consumers only mocks | | |
| SAP/ADT-style readback rules | TESTED against an offline provider | | live: NOT_ESTABLISHED |
| Production correctness, exactly-once enterprise execution | | | NOT_ESTABLISHED |
