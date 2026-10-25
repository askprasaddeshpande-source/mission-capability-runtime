# MCR 3.0 Release Handoff R1

Entry point for MCR 3.0.0 (offline engineering release candidate). Baseline: `main` at `fd865c67c053431dc33297a0df2a3c9a02fd51fe` (MCR R2.0, PR #4). Branch: `work/mcr3-consolidated-evidence-outcome-runtime-r1`. One consolidated PR is prepared; **it is not merged, not tagged, and no release exists until the owner approves**.

## What this release is and is not
**Is:** a new, independently versioned runtime lineage (`tools/mcr3/`), qualified offline (tests, mutation, attacks, fresh clone) and reviewed by an independent agent (verdict in the qualification report) that carries the R2.0 reference model forward with the R2.0 engineering gaps closed or dispositioned; a version-independent Evidence Contract v1 (`mcr-evidence/1`); provenance verification with the hash/signature/producer/trust/freshness/replay findings kept separate; capability and adapter governance in which qualification never approves; two reference adapters (frozen R2.0 evidence, native 3.0); portable readback rules; and a Claude Mods interoperability package at the contract boundary (mock consumers and a change packet).
**Is not:** production-qualified, live-verified, signed with a production key, connected to Claude Mods, or evidence that any enterprise outcome is correct. INTEROPERABILITY_DOES_NOT_IMPLY_AUTHORITY holds everywhere: every event carries `authority_effect = NONE`.

## Where things are
| Need | Start here |
|---|---|
| Decision, layers, module map | `architecture/mcr3/MCR_3_0_ARCHITECTURE_AND_DECISION_RECORD_R1.md` |
| Phase 0 baseline, gap register G01 to G13, Claude Mods source facts | `architecture/mcr3/MCR_3_0_PHASE0_BASELINE_AND_SCOPE_FREEZE_R1.md` |
| Security, provenance, authority, ledger guarantees by platform, scanner limits | `architecture/mcr3/MCR_3_0_SECURITY_AND_AUTHORITY_CONTRACT_R1.md` |
| Evidence contract, compatibility rules, examples, schema | `architecture/mcr3/contracts/evidence-v1/` |
| What Claude Mods would have to change (not changed) | `architecture/mcr3/CLAUDE_MODS_CHANGE_PACKET_R1.md` |
| Gap-by-gap dispositions | `reports/mcr3/MCR_3_0_GAP_CLOSURE_MATRIX_R1.md` |
| Test, mutation, attack, review results | `reports/mcr3/MCR_3_0_QUALIFICATION_REPORT_R1.md`, `evidence/mcr3/` |
| Code and tools | `tools/mcr3/` |

## How to verify (offline, no SAP, no network)
```
python tools/mcr3/run_mcr3_tests.py                                   # 1,644 checks in 10 suites, tens of seconds
python tools/mcr3/verify_mcr3.py --fast --expect-sums-sha256 <anchor taken from outside the repository>
python tools/mcr3/verify_mcr3.py --clone --expect-sums-sha256 <anchor>   # fresh clone, runs every validator and checks they reproduce the archived results
python tools/mcr3/run_mcr3_mutation_check.py --jobs 3                  # about 25 minutes
python tools/mcr3/run_mcr3_verifier_attacks.py                         # sequential, throwaway clones
```
The anchor for a commit is the SHA-256 of `evidence/mcr3/SHA256SUMS_MCR3.txt` quoted in the final commit message.

## Owner decisions still needed
1. Approve, change or reject the single consolidated PR. Nothing is merged or tagged without that.
2. Production signing: whether to create a trust root, who holds the keys, how revocation works (the SSH `allowed_signers` mechanism that Claude Mods already uses is supported by the SSHSIG back-end). No key was created.
3. Whether the Claude Mods change packet should be applied in that project, and by whom (this work did not modify it).
4. Whether to authorize a separate live study for SAP activation, package membership, an independent second readback and a failure path (the portable readback rules are written and unit-tested, NOT verified live).
5. Standing R2.0 decisions: ADT token rotation (declined, accepted risk) and the leftover test view `ZC_MCR20C_7A3F91D2`.

## Next phase (recommended, not started)
A frozen live study with the model hash bound into the authorization; a Governor-backed `ApprovalVerifier`; a durable replay cache and, if wanted, a second readback source; POSIX and network-filesystem tests of the ledger.
