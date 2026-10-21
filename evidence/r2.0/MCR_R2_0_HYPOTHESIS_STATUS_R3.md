# MCR R2.0 Hypothesis Status R3

Supersedes status R2 (kept as history; see also `reports/r2.0/MCR_R2_0_C_REPORT_ERRATUM_R1.md`). Date: 2026-10-20. New evidence since R2: offline repair and re-qualification only (96-test model validator, 15-mutant guard check, frozen-runner mock regression). **No new live evidence; no hypothesis is PROVEN; no hypothesis was promoted.**

| ID | Status | Change vs R2 | Basis | Limits |
|---|---|---|---|---|
| H41 Authoritative Commit Observation | OBSERVED (scoped) | none | live run 2026-10-20: ABSENT baseline -> one create -> readback EXISTS (DDLS endpoint) | one object, one run; live ABSENT/UNKNOWN branches only synthetic |
| H42 Outcome-Authoritative Completion | OBSERVED (scoped) | none | COMPLETE after 4 predicates passed on authoritative readback | predicates exclude package and activation |
| H43 Transaction Correlation | PARTIAL | none | ids and hashes across receipts; fresh name, ABSENT baseline, single mutation | provider returned no correlation token; CompletionReceipt has no mission_id field |
| H44 Replay-Safe Continuation | SYNTHETIC | none (re-run: crash matrix byte-identical after repair) | crash-injection matrix; lock existence observed live | no live interruption; lock refusal live not exercised |
| H45 Compensation Authority Separation | SYNTHETIC | none (compensation guards still detected by mutants) | model semantics | no live compensation |
| H46 Contract-Drift Fail-Closed | PARTIAL | none | live drift 20 -> 29 tools observed; point-of-use gate passed live; fail-closed synthetic (mutant detected) | no live drift between prewrite and call |
| H47 Evidence-Complete Mission Closure | PARTIAL | **qualifier corrected**: live run emitted 13 of 14 links (R2 said 12 of 13); repaired model emits 14 of 14 on synthetic COMPLETE missions | frozen live chain links 1-13; synthetic 14/14 plus tamper, missing-link and mismatch rejection | link 14 never observed live; historical run not backfilled |
| H48 Bounded Governance Overhead | PARTIAL (descriptive) | none | synthetic median ~0.1 ms; one live run 69.3 us vs 3.68 s | single machine/run; no inference |

Promotion conditions (not met): H47 needs a live run emitting link 14; H41/H42 need replication across objects/runs and at least one live non-success branch; H44-H46 need live interruption, compensation and drift cases, each under a fresh frozen authorization.
