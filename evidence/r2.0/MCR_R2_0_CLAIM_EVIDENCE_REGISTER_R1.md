# MCR R2.0 Claim–Evidence Register R1

| Claim | Class | Evidence | SHA-256 | Limits |
|---|---|---|---|---|
| The R2.0 state machine rejects every skipped-evidence path tested (74 checks, 11 acceptance groups) | SYNTHETIC | `evidence/r2.0/MCR_R2_0_A_VALIDATION_RESULT_R1.json` via `tools/r2.0/validate_r2_outcome_model.py` | 8456E2D3B9148CC949086E3BB30E46F41DA78BE0D526890E04F6FB990A1EC126 | Tests the model against itself; 4 guard mutations were detected in a manual mutation check (not archived). No enterprise behavior is shown |
| R1.9 remains frozen: tag v1.9.0 -> 9c5105f | LOCAL | `git rev-list -n1 v1.9.0` at 2026-10-20 | n/a | Tag could be re-pointed by a repo admin; commit id recorded here |
| SAP writes performed by R2.0 so far = 0 | LOCAL | no write tool exists in the model; no provider call made in this lineage | n/a | Self-reported by the executing agent |
| (reserved) COMMITTED can be established by authoritative readback | NOT_ESTABLISHED | pending R2.0B/C | | |
