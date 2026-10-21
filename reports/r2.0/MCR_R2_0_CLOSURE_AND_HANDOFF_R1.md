# MCR R2.0 Closure and Handoff R1

Date: 2026-10-21. Branch `work/r2.0-validated-enterprise-outcome-runtime-r1`. Last reviewed code: `73a2646` (R2.0N). This file closes the R2.0 research line as a **bounded proof of concept**. It adds no code and no new evidence; it is the entry point to everything else under `architecture/r2.0/`, `reports/r2.0/`, `evidence/r2.0/` and `tools/r2.0/`.

## 1. What R2.0 is, and what it is not
**Question:** can an enterprise-agent runtime show that an authorized mission caused the intended enterprise state transition, keeping "the tool returned" distinct from "the state was committed" and from "the intended outcome holds"?

**Is:** an offline-tested evidence model (a library, not a service) with a 20-state machine, 25 hash-addressed object kinds, tri-state outcome predicates, a replay ledger, continuation leases, separate compensation grants and a 14-link evidence chain validated through 50 named relations before COMPLETE; a read-only readback probe; a frozen single-use live study runner; and one scoped live observation (one CDS data definition on one provider).

**Is not:** a validated enterprise runtime, qualified for SAP generally, a proof of end-to-end correctness, or production-ready. The model verifies the **consistency of presented evidence**, not **who produced it** (no signatures). It is a single-send-per-mission library; thread safety is per Mission object and per ledger object.

## 2. Where things are
| Need | Start here |
|---|---|
| The question, scope and charter | `reports/r2.0/MCR_R2_0_RESEARCH_CHARTER_R1.md`, `MCR_R2_0_RESEARCH_SUMMARY_R1.md` |
| Architecture and state machine | `architecture/r2.0/MCR_R2_0_VALIDATED_OUTCOME_ARCHITECTURE_R1.md`, `MCR_R2_0_STATE_MACHINE_R1.md` |
| Current contract (each file amends the previous) | `architecture/r2.0/MCR_R2_0_EVIDENCE_CHAIN_CONTRACT_R7.md` (R1 to R7 retained as history) |
| JSON Schemas | `architecture/r2.0/schemas/` |
| Current claims and wording limits | `evidence/r2.0/MCR_R2_0_HYPOTHESIS_STATUS_R9.md` |
| The model | `tools/r2.0/mcr_r2_model.py` |
| Tests, mutation check, local scenarios | `tools/r2.0/validate_r2_outcome_model.py`, `run_r2_mutation_check.py`, `run_r2_local_scenarios.py` |
| Verification | `tools/r2.0/verify_r2_fresh_clone.py` |
| Live study (frozen) | `tools/r2.0/r2_0c_study.py`, `reports/r2.0/MCR_R2_0_C_LIVE_OUTCOME_STUDY_REPORT_R1.md`, `MCR_R2_0_C_REPORT_ERRATUM_R1.md` |
| R1.9 boundary | `reports/r2.0/MCR_R2_0_R1_9_BASELINE_BOUNDARY_R1.md` (tag `v1.9.0` unchanged) |
| Hardening history | `reports/r2.0/MCR_R2_0_{G,H,I,J,L,M,N}_HARDENING_REPORT_R1.md` (G is `G_QUALIFICATION_SUMMARY`) |
| Independent review history | section 4 below; review 1 to 4 findings in `reports/r2.0/MCR_R2_0_INDEPENDENT_QUALIFICATION_R*_FINDINGS.md` |

## 3. How to verify
```
python tools/r2.0/validate_r2_outcome_model.py                         # 510 checks
python tools/r2.0/run_r2_local_scenarios.py
python tools/r2.0/verify_r2_fresh_clone.py --quick                     # fast, no mutation rerun
python tools/r2.0/verify_r2_fresh_clone.py --clone --expect-sums-sha256 <anchor from outside the repository>
python tools/r2.0/run_r2_mutation_check.py --jobs 2                    # about 25 minutes; keep jobs low on small machines
```
The verifier is self-attestation unless run with `--expect-sums-sha256` supplied from a source outside the repository. The anchor for a commit is the SHA-256 of `evidence/r2.0/SHA256SUMS_R2_0.txt` quoted in that commit's message. No command here touches SAP or the network.

## 4. Independent review history
| Review | Commit | Verdict | Main finding classes |
|---|---|---|---|
| 1 | `8a383b6` | HOLD | forged-lease resume, non-atomic guards, no relational chain checks, vacuous predicates, weak verifier |
| 2 | `b5cca1f` | HOLD | send-time gates that did not verify evidence, stale-lease replay, ungated terminal states, 46 surviving mutants |
| 3 | `a381a22` | HOLD | `resume()` skipping gates, two processes sharing a ledger both sending, compensation with no compensating action, scanner and mutation-granularity gaps |
| 4 | `f6e79a4` | HOLD | no thread safety on one Mission, unchecked `scope` types, weak compensation goal checks, undisclosed ledger deletion, scanner evasions |
| 5 | `681f77a` | PASS_WITH_GAPS | thread-unsafe in-memory ledger, unvalidated ledger paths, overstated compensation wording, readback contract not tied to the bound provider, mutation-report wording, scanner false negatives |
| 6 | `212804f` | GO_WITH_DOCUMENTED_GAPS | no effective regression guard for the ledger lock, NUL and device-name paths leaking `ValueError`, scanner missing `github_pat_`, two undocumented behaviours (R51 empty tail, failed compensating call) |
| 7 (targeted, R2.0N diff) | `73a2646` | GO_WITH_DOCUMENTED_GAPS | no HOLD-level defect; low-severity items listed in section 5 |

Each review was read-only, run by a fresh agent in a clean clone with no access to owner credentials or private workspace files. Findings fixed in a round are listed in that round's hardening report.

## 5. Qualification numbers (R2.0N, reproduced by review 7)
- Validator: 510 checks, 18 groups, 0 failed.
- Mutation check: 619 mutants generated from the source (422 syntax-tree, 119 guard, 50 relation, 28 special). 305 detected by an assertion; 307 because the validator's own fixtures could no longer run (weaker evidence); 1 by hang; 6 survivors, each justified as an equivalent mutant; 0 unexplained; 0 inconclusive.
- Frozen R2.0C runner against the mock provider: 6/6 scenarios reproduce the frozen outcomes; the runner file is unchanged.
- Full fresh-clone verification with the external sums anchor: PASS.

## 6. Accepted and known gaps
Accepted by the owner: no provenance signatures; ADT bearer token rotation declined (the token was pasted in an earlier chat message; a risk accepted); the leftover test CDS view `ZC_MCR20C_7A3F91D2` was not removed.
Disclosed and unclosed:
- The six verifier attack scenarios A13a to A13f were never run to completion (stopped twice for low memory). The scanner payload checks in the test matrix cover the same behaviours directly.
- One live run; completion link 14 never observed live; raw live evidence is outside Git.
- The frozen runner's readback weaknesses: "authoritative" is its own label, either-version EXISTS, ABSENT without object identity, intra-response integrity, substring predicate; activation and package unproven.
- Unenforced fields: `expires_at`, `roles`, `tenant`, `intent.expected_outcome_hash`, `readback.activation`, `readback_contract.checks`.
- Ledger limits: deletion without a pinned id, restore of an older copy, one local filesystem, POSIX locking untested, power-loss durability untested. The `_consume_file` and `_sync` thread-lock decorators have no reliable test.
- A second provider call after a failed compensating call is not counted by the model (contract R7 section 3).
- Review 7 low-severity items, not fixed: `NUL:stream`, a superscript-digit device name such as `com¹.txt` and `file:aux` pass the ledger-path device-name check (each still ends as a `GuardError` or a working ledger); the scanner does not detect `sk-ant-`, `sk-proj-`, `glpat-`, `ya29.`, `SG.` or `sk_test_` shapes. Suggested fix: reject `:` in any path component and extend the reserved and token lists.
- The scanner is a heuristic, and about half of the mutant detections are validator crashes rather than targeted assertions.
- Hypotheses H41 and H42 are OBSERVED (scoped to one object, one run); H43, H46, H47, H48 PARTIAL; H44, H45 SYNTHETIC. None is PROVEN.

## 7. Using R2.0 downstream
Treat the model, schemas and contract as a **reference design and test oracle**, not as code to ship. Any later use must keep the standing rules: no SAP mutation without a fresh, hash-bound owner authorization; no credentials, tokens or auth contexts in the repository; R1.9 stays frozen.

## 8. Next required proof (unchanged from the research summary)
A second frozen live study, under a fresh owner authorization, that: binds the model hash into the authorization; proves per-version readback on an object with a pending inactive version; requires ABSENT to name the requested object; adds an independent second readback source or renames the authority level; emits and persists the completion receipt (link 14); exercises at least one non-success branch live; and counts compensating-call attempts in the ledger before any live compensation.
