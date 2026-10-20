# MCR R2.0 Claim–Evidence Register R1

| Claim | Class | Evidence | SHA-256 | Limits |
|---|---|---|---|---|
| The R2.0 state machine rejects every skipped-evidence path tested (74 checks, 11 acceptance groups) | SYNTHETIC | `evidence/r2.0/MCR_R2_0_A_VALIDATION_RESULT_R1.json` via `tools/r2.0/validate_r2_outcome_model.py` | 8456E2D3B9148CC949086E3BB30E46F41DA78BE0D526890E04F6FB990A1EC126 | Tests the model against itself; 4 guard mutations were detected in a manual mutation check (not archived). No enterprise behavior is shown |
| R1.9 remains frozen: tag v1.9.0 -> 9c5105f | LOCAL | `git rev-list -n1 v1.9.0` at 2026-10-20 | n/a | Tag could be re-pointed by a repo admin; commit id recorded here |
| SAP writes performed by R2.0 so far = 0 | LOCAL | no write tool exists in the model; no provider call made in this lineage | n/a | Self-reported by the executing agent |
| Continuation after a crash at every step never restores consumed mutation authority; recovery after a post-send crash reaches COMPLETE with exactly one mutation; tampered resume inputs are rejected | SYNTHETIC | `evidence/r2.0/MCR_R2_0_DE_LOCAL_SCENARIOS_RESULT_R1.json` via `tools/r2.0/run_r2_local_scenarios.py` | 4BF0B24C9032F6254258ECAC9088F1B78BE431EAE2829850FED9F3632E7ABD5E | In-process fake world; the "world" answers readback as scripted |
| Compensation requires a separate grant, never inherits forward authority and is not completion of the original mission | SYNTHETIC | same file | 4BF0B24C9032F6254258ECAC9088F1B78BE431EAE2829850FED9F3632E7ABD5E | Semantics only; no live compensation |
| Local governance overhead for the synthetic path is ~0.1 ms median (n=500, single machine, no provider) | LOCAL | timing kept outside Git (workspace evidence folder); summary in the R2.0A report | n/a | Descriptive only; provider/SAP/network latency not modeled; no productivity claim |
| The retained ADT MCP contract (20 tools, R1.8) contains no dedicated object-read/get-source/search tool | OBSERVED (historical) | R1.8 package `P8_C1A_HF04` live_tools list, read offline | see B report | Not re-observed in this session: provider unreachable |
| ATC result can expose object name, type and package for an existing object (one documented instance, R1.7 P6-D1) | PARTIAL | R1.8 external review manuscript text | see B report | Single instance; absence behavior untested; no activation or source-hash content |
| (reserved) COMMITTED can be established by authoritative readback | NOT_ESTABLISHED | pending R2.0B/C | | |
