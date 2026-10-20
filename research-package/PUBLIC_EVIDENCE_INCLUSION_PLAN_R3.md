# MCR Public Evidence Inclusion Plan R3

Plan only. Nothing here publishes anything; the repository remains PRIVATE. Categories: INCLUDE, HASH_ONLY, EXCLUDE_SECRET, EXCLUDE_PRIVATE_PATH, EXCLUDE_REDUNDANT, EXCLUDE_NONPUBLIC, NEEDS_OWNER_REVIEW.

## 1. Artifacts already in Git (per `PORTABILITY_MANIFEST_R2.json`)

| Artifact | Repo path | Category | Rationale |
|---|---|---|---|
| `R1_6_1_ORIGINAL_PAPER` | `evidence/portable/r1.6/From_Tools_to_Missions_Mission_Capability_Runtime_R1_6_1.pdf` | INCLUDE | Original author material; contains the author's public contact email, already printed in the manuscript |
| `R1_6_FROZEN_SCIENTIFIC_MANUSCRIPT` | `-` | HASH_ONLY | Bytes unavailable; the frozen hash is recorded and cited; nothing is substituted |
| `R1_6_ADVERSARIAL_REVIEW` | `evidence/portable/r1.6/MCR_R1_6_ADVERSARIAL_REVIEW.md` | INCLUDE | Original author material; contains the author's public contact email, already printed in the manuscript |
| `R1_7_PUBLICATION_FREEZE` | `evidence/portable/r1.7/MCR_R1_7_PUBLICATION_FINAL_FREEZE_R1.zip` | INCLUDE | Exact bytes verified; secret/authority scan clean |
| `P6D_BOUNDED_WRITE_CLOSURE` | `evidence/portable/r1.7/MCR_R2E_P6_D1_SCIENTIFIC_CLOSURE_R1.zip` | INCLUDE | Exact bytes verified; secret/authority scan clean |
| `R1_8_EXTERNAL_REVIEW_REFRESH` | `evidence/portable/r1.8/MCR_R1_8_EXTERNAL_REVIEW_PACKAGE_REFRESH_R1.zip` | INCLUDE | Exact bytes verified; secret/authority scan clean |
| `R1_8_C1D_SCIENTIFIC_CLOSURE` | `evidence/portable/r1.8/MCR_R2E_P8_C1D_LIVE_FOUR_PROVIDER_SCIENTIFIC_CLOSURE_R1.zip` | EXCLUDE_REDUNDANT | Byte-identical copy already nested inside the R1.8 external-review refresh ZIP; retained in the repository for direct hash verification, so the public release package may omit the standalone copy |
| `R1_8_C2C_SCIENTIFIC_CLOSURE` | `evidence/portable/r1.8/MCR_R2E_P8_C2C_MULTI_MISSION_OUTCOME_AND_SCIENTIFIC_CLOSURE_R1.zip` | EXCLUDE_REDUNDANT | Byte-identical copy already nested inside the R1.8 external-review refresh ZIP; retained in the repository for direct hash verification, so the public release package may omit the standalone copy |
| `R1_8_WATCHDOG_R2` | `evidence/portable/r1.8/MCR-P8-MCP-Watchdog-R2.ps1` | INCLUDE | DECIDED (delegated review): include as a clearly labeled normalized reading copy; frozen hash recorded in the manifest; original bytes unavailable; do not execute. Contains a generic local user-profile path (C:\Users\Admin\...ADT extension), accepted as non-sensitive.  |
| `R1_8_B1_EXACT_TAXONOMY` | `evidence/portable/r1.8/P8_B1_2_EXACT_NAME_TAXONOMY_CORRECTION_R1.json` | EXCLUDE_REDUNDANT | Byte-identical copy already nested inside the R1.8 external-review refresh ZIP; retained in the repository for direct hash verification, so the public release package may omit the standalone copy |
| `R1_9A_FOUNDATION_PACKAGE` | `evidence/portable/r1.9a/MCR_R1_9_A_GOVERNED_EXECUTION_FOUNDATION_R1.zip` | INCLUDE | Exact bytes verified; secret/authority scan clean |
| `R1_9A_FOUNDATION_RUNNER` | `evidence/portable/r1.9a/Run-MCR-R1.9A-Governed-Execution-Foundation-R1.ps1` | INCLUDE | Exact bytes verified; secret/authority scan clean |
| `R1_9B_PREWRITE_FREEZE` | `evidence/portable/r1.9b/MCR_R1_9_B_LIVE_GOVERNED_MUTATION_AND_OUTCOME_R1_PREWRITE_FREEZE.zip` | INCLUDE | Exact bytes verified; secret/authority scan clean |
| `R1_9B_LIVE_CONTRACT` | `evidence/portable/r1.9b/01_V1_9_B_LIVE_MISSION_CONTRACT_R1.json` | INCLUDE | Exact bytes verified; secret/authority scan clean |
| `R1_9B_PRINCIPAL_CONTEXT` | `evidence/portable/r1.9b/02_V1_9_B_PRINCIPAL_CONTEXT_R1.json` | INCLUDE | DECIDED (delegated review): hashes, target alias and an expired timestamp; no token material |
| `R1_9B_DELEGATION_CHAIN` | `evidence/portable/r1.9b/03_V1_9_B_DELEGATION_CHAIN_R1.json` | INCLUDE | Exact bytes verified; secret/authority scan clean |
| `R1_9B_MISSION_ENVELOPE` | `evidence/portable/r1.9b/04_V1_9_B_MISSION_EXECUTION_ENVELOPE_R1.json` | INCLUDE | Exact bytes verified; secret/authority scan clean |
| `R1_9B_MUTATION_BUDGET` | `evidence/portable/r1.9b/05_V1_9_B_MUTATION_BUDGET_R1.json` | INCLUDE | Exact bytes verified; secret/authority scan clean |
| `R1_9B_TRANSACTION_ENVELOPE` | `evidence/portable/r1.9b/06_V1_9_B_TRANSACTION_ENVELOPE_R1.json` | INCLUDE | Exact bytes verified; secret/authority scan clean |
| `R1_9B_CONTRACT_LEASE` | `evidence/portable/r1.9b/07_V1_9_B_CONTRACT_LEASE_R1.json` | INCLUDE | Exact bytes verified; secret/authority scan clean |
| `R1_9B_EXPECTED_OUTCOME` | `evidence/portable/r1.9b/08_V1_9_B_EXPECTED_OUTCOME_CONTRACT_R1.json` | INCLUDE | Exact bytes verified; secret/authority scan clean |
| `R1_9B_COMPENSATION_POLICY` | `evidence/portable/r1.9b/09_V1_9_B_COMPENSATION_POLICY_R1.json` | INCLUDE | Exact bytes verified; secret/authority scan clean |
| `R1_9B_PREWRITE_CHECKPOINT` | `evidence/portable/r1.9b/11_V1_9_B_PRE_WRITE_CHECKPOINT_R1.json` | INCLUDE | Exact bytes verified; secret/authority scan clean |
| `R1_9B_PACKAGE_MANIFEST` | `evidence/portable/r1.9b/17_PACKAGE_MANIFEST_R1.json` | INCLUDE | Exact bytes verified; secret/authority scan clean |
| `HF05_SESSION_PROTOCOL_FORENSIC` | `evidence/portable/r1.9b/Run-MCR-R1.9B-HF05-Session-Protocol-Forensic-R1.ps1` | INCLUDE | DECIDED (delegated review): include as a clearly labeled normalized reading copy; frozen hash recorded in the manifest; original bytes unavailable; do not execute.  |
| `HF06_FINAL_QUALIFIED_RUNNER` | `evidence/portable/r1.9b/Run-MCR-R1.9B-Live-Governed-Mutation-And-Outcome-R1-HF06.ps1` | INCLUDE | DECIDED (delegated review): include as a clearly labeled normalized reading copy; frozen hash recorded in the manifest; original bytes unavailable; do not execute.  |
| `HF06_ATTEMPT2_AUTHORIZATION` | `-` | HASH_ONLY | Authority material; never copy bytes. Hash corroborated by the single-use lock |
| `HF06_ATTEMPT2_SINGLE_USE_LOCK` | `evidence/portable/r1.9b/PRE_MUTATION_SINGLE_USE_LOCK_HF06_CC06B59F341E9B70844F7BEE48F6917303C094206431C228575F91E4500B9E09.json` | INCLUDE | Exact bytes verified; secret/authority scan clean |
| `HF06_ATTEMPT2_OUTPUT` | `evidence/portable/r1.9b/02_HF06_LIVE_EXECUTION_OUTPUT_R2.txt` | INCLUDE | Exact bytes verified; secret/authority scan clean |
| `HF06_CREATE_COMMIT_FORENSIC` | `evidence/portable/r1.9b/Run-MCR-R1.9B-HF06-Attempt2-Create-Commit-AFF-Forensic-R1.ps1` | INCLUDE | DECIDED (delegated review): include as a clearly labeled normalized reading copy; frozen hash recorded in the manifest; original bytes unavailable; do not execute.  |
| `HF06_PREFLIGHT_RECONCILIATION` | `evidence/portable/r1.9b/Run-MCR-R1.9B-HF06-Attempt2-Create-State-Preflight-Reconciliation-R1.ps1` | INCLUDE | DECIDED (delegated review): include as a clearly labeled normalized reading copy; frozen hash recorded in the manifest; original bytes unavailable; do not execute.  |
| `HF06_DETAILS_RAW_RESPONSE` | `evidence/portable/r1.9b/04_GET_OBJECT_TYPE_DETAILS_RAW_RESPONSE.txt` | INCLUDE | DECIDED (delegated review): content read; generic field metadata, a provider error string and local adjudication JSON; no customer, tenant-business or credential content |
| `HF06_VALIDATION_RAW_RESPONSE` | `evidence/portable/r1.9b/05_RUN_VALIDATION_RAW_RESPONSE.txt` | INCLUDE | DECIDED (delegated review): content read; generic field metadata, a provider error string and local adjudication JSON; no customer, tenant-business or credential content |
| `HF06_ADJUDICATION_R2_SCRIPT` | `evidence/portable/r1.9b/Run-MCR-R1.9B-HF06-Attempt2-Create-State-Preflight-Reconciliation-Adjudication-R2.ps1` | INCLUDE | DECIDED (delegated review): include as a clearly labeled normalized reading copy; frozen hash recorded in the manifest; original bytes unavailable; do not execute.  |
| `HF06_ADJUDICATION_RESULT_R2` | `evidence/portable/r1.9b/09_ADJUDICATION_RESULT_R2.json` | INCLUDE | DECIDED (delegated review): content read; generic field metadata, a provider error string and local adjudication JSON; no customer, tenant-business or credential content |
| `R1_6_1_TARGETED_REVIEW_RC1_PACKAGE` | `evidence/portable/r1.6/MCR_R1_6_1_TARGETED_REVIEW_RC1.zip` | INCLUDE | Original author material; contains the author's public contact email, already printed in the manuscript |

Counts: EXCLUDE_REDUNDANT=3, HASH_ONLY=2, INCLUDE=31.

## 2. Local evidence classes that must never be copied from the workstation

| Class | Examples | Category |
|---|---|---|
| Authentication material | bearer tokens, DPAPI-protected blobs, `auth-context*`, `*AUTH_CONTEXT*`, `*protected_token*` | EXCLUDE_SECRET |
| Certificates and keys | `*.pfx`, `*.pem`, `*.key`, code-signing private material | EXCLUDE_SECRET |
| Live write authorizations | `MCR_R1_9_B_LIVE_WRITE_AUTHORIZATION*.json` | HASH_ONLY |
| Workstation state roots | `..._HF06_STATE`, user-profile and extension paths | EXCLUDE_PRIVATE_PATH |
| Customer/client or tenant SAP content | unreviewed SAP source, system dumps, other landscapes | EXCLUDE_NONPUBLIC |
| Unreviewed historical D:\MCP tree | 4,000+ files incl. DS12 archives, images, unrelated programs | EXCLUDE_NONPUBLIC (not curated for this research) |
| Nested duplicate packages | copies of C1D/C2C inside review ZIPs | EXCLUDE_REDUNDANT |

## 3. Pre-publication gates

1. Re-run the secret and private-path scans over the final file set, including decompressed ZIP contents (R2 scan: no secrets; 3 user-profile path hits, all in scripts).
2. Raw SAP responses, principal context and author email: reviewed and decided above (include).
3. Unrecovered originals: published hash-only or as labeled normalized copies with the documented gap.
4. Keep `evidence/portable/** -text` so published bytes remain exact.
5. Release, tag, visibility and archival actions are performed only after the final gates pass; no DOI is recorded until a real one is issued.
