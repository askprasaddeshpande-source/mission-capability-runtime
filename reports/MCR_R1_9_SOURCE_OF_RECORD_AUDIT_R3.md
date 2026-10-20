# MCR R1.9 Source-of-Record Audit R3

Classification vocabulary: **MATCHED** (bytes in Git hash-equal to the recorded value), **PARTIAL**, **MISSING**, **CONFLICT**, **UNVERIFIABLE** (cited, but no bytes available to check).

No evidence was edited to resolve any finding below.

## 1. Original R1.6.1 scientific identity

| Item | Status | Basis |
|---|---|---|
| Title, subtitle, author, version, date (Adversarially Hardened Whitepaper Candidate R1.6.1, 31 August 2026) | MATCHED | `evidence/portable/r1.6/From_Tools_to_Missions_Mission_Capability_Runtime_R1_6_1.pdf`, SHA-256 `AD45F74150D9FEB188C7CA78E427DB960443069EE4A3C1B2B65AF3C53DE0140A` equals `canonical_pdf_sha256` in the RC1 package manifest |
| Frozen scientific manuscript `E589393C6EEA0BA9...` | **MISSING** (hash cited, bytes absent) | Cited by the PDF and RC1 manifest; searched Git, `D:\MCP` (4,290 files incl. nested ZIPs) and by name across `D:`; not found. Not recreated |
| Earlier R1.6.1 PDF `A1E76C87...` | MISSING | Cited by RC1 manifest as text/render-equivalent, not byte-identical; bytes not found |

## 2. Frozen MCWS metrics

Checked against the R1.6.1 PDF text (publication layer) and by arithmetic. The frozen manuscript itself is unavailable, so these are verified as *reported*, not recomputed from raw data.

| Item | Status |
|---|---|
| Broad 5/48 (10.4%) | MATCHED (as reported in R1.6.1 PDF) |
| Static 17/48 (35.4%) | MATCHED (as reported in R1.6.1 PDF) |
| MCWS 30/48 (62.5%) | MATCHED (as reported in R1.6.1 PDF) |
| p Broad-MCWS 0.00293 | MATCHED (as reported in R1.6.1 PDF) |
| p Static-MCWS 0.03125 | MATCHED (as reported in R1.6.1 PDF) |
| p Broad-Static 0.2266 | MATCHED (as reported in R1.6.1 PDF) |
| Held-out Broad 0/12, Static 2/12, MCWS 7/12 | MATCHED (as reported in R1.6.1 PDF) |
| Title/subtitle/R1.6.1/31 August 2026 | MATCHED (as reported in R1.6.1 PDF) |
| Cites frozen manuscript hash | MATCHED (as reported in R1.6.1 PDF) |
| Arithmetic 5/48, 17/48, 30/48 -> 10.4%, 35.4%, 62.5% | MATCHED |
| Repository file `README.md` carries the same metrics and p-values | MATCHED |
| Repository file `paper/ORIGINAL_R1.6.1_SOURCE_OF_RECORD.md` carries the same metrics and p-values | MATCHED |
| Repository file `paper/MCR_Manuscript_R1.9_CLOSURE_DRAFT_R1.md` carries the same metrics and p-values | MATCHED |
| Repository file `paper/MCR_Manuscript_R1.9_EXTERNAL_REVIEW_CANDIDATE_R3.md` carries the same metrics and p-values | MATCHED |
| Raw experiment data / frozen manuscript recomputation | UNVERIFIABLE |

## 3. R1.7 evidence (companion R2-E P3-P7 and P6-D1)

| Item | Status | Artifact / hash |
|---|---|---|
| R1.7 publication final freeze | MATCHED | `evidence/portable/r1.7/MCR_R1_7_PUBLICATION_FINAL_FREEZE_R1.zip` `48FA1C707002314752245434F5BDC09F96C5DEAB6CC27BC05F0483908457F1F3` |
| P6-D1 bounded SAP write closure | MATCHED | `evidence/portable/r1.7/MCR_R2E_P6_D1_SCIENTIFIC_CLOSURE_R1.zip` `D6ECA3A411DC1E224DCE677C404575A530C04BFB625852734802D61848AE953C` |
| R1.7 P7 closure ZIP (register ID MCR-R1.7-P7) | **CONFLICT** | Register value `082CC73D...6B44F6B...` is 54 hex characters (malformed); not in anchors; no bytes. Cannot be verified or repaired without the original |
| Content check: P6-D1 closure states `FINAL_STATE=VALIDATED_COMPLETE`, 2/2 mutations, `WRITE_REPLAY_AFTER_TIMEOUT=FALSE`, object `ZCL_MCR_P6D_DFC3F677` (not the R1.9B object) | MATCHED | inside the P6-D1 ZIP |
| Content check: R1.7 claim matrix lists 'SAP write safety proven' NOT CLAIMED and 'P6-D completed' NOT CLAIMED | PARTIAL | True at R1.7-freeze time; superseded for P6-D1 only by the later P6-D1 closure. Not a conflict when read in sequence |

## 4. R1.8 evidence

| Item | Status | Artifact / hash |
|---|---|---|
| External review refresh | MATCHED | `evidence/portable/r1.8/MCR_R1_8_EXTERNAL_REVIEW_PACKAGE_REFRESH_R1.zip` `28DA3688FCECA431B5272659B4C4C09F83D851AF598604CC3E83AD3215434DDC` |
| C1D four-provider closure | MATCHED | `evidence/portable/r1.8/MCR_R2E_P8_C1D_LIVE_FOUR_PROVIDER_SCIENTIFIC_CLOSURE_R1.zip` `296961C6CB47C876B35CB107DC6EDB3D8A4803A5611105A78102C440A2731B14` |
| C2C multi-mission closure | MATCHED | `evidence/portable/r1.8/MCR_R2E_P8_C2C_MULTI_MISSION_OUTCOME_AND_SCIENTIFIC_CLOSURE_R1.zip` `F347FC825D9E444E9E0FAE61D806304C8B2CA540A4D6EA037AB5412D8AEEA61D` |
| R1.8 reviewer PDF package (`A6685F62...`) | UNVERIFIABLE | Hash anchored; no bytes in Git |
| C1D content: 41 tools = ADT 20 + Fiori 9 + UI5 10 + CAP 2; READ 23 + ANALYSIS 7 = 30 zero-write | MATCHED | inside C1D ZIP |
| C2C content: 3 missions, 8 calls, 0 retries, 0 replay, 0 writes; historical C2B raw Fiori contract not captured | MATCHED | inside C2C ZIP |

## 5. R1.9A evidence

| Item | Status | Artifact / hash |
|---|---|---|
| Foundation package | MATCHED | `evidence/portable/r1.9a/MCR_R1_9_A_GOVERNED_EXECUTION_FOUNDATION_R1.zip` `4F018E2F1EBE86AEF78E94989685B02A2E41BFFB73238A21F63AC12C8190E1F2` |
| Foundation runner | MATCHED | `evidence/portable/r1.9a/Run-MCR-R1.9A-Governed-Execution-Foundation-R1.ps1` `C42E09CA4A00DB88B011CD2B693851CC6EDAC1664C0A44CB7DDDDB97D6959237` (restored byte-exact from the ZIP in R2; the R1 commit copy was normalized) |
| Test report: schema, hashing, attenuation, budget, lease, checkpoint, compensation separation, fast path all PASS; determinism drift 0 | MATCHED | `21_TEST_REPORT_R1.json` in package |
| Microbenchmark | PARTIAL | Local synthetic; p50=p95=p99 identical (aggregate, not a distribution) |

## 6. R1.9B evidence

| Item | Status | Artifact / hash |
|---|---|---|
| Prewrite freeze ZIP | MATCHED | `evidence/portable/r1.9b/MCR_R1_9_B_LIVE_GOVERNED_MUTATION_AND_OUTCOME_R1_PREWRITE_FREEZE.zip` `3DFE6756695A67EF28BBF54F5C7B61746A819B4161923B0319FEC26683C3ECF9` |
| Mission execution envelope | MATCHED | `evidence/portable/r1.9b/04_V1_9_B_MISSION_EXECUTION_ENVELOPE_R1.json` `C037A481BACE9F4812E1401526BE399534861E4E72B9776470ECCCDD8967A221` |
| Expected outcome contract | MATCHED | `evidence/portable/r1.9b/08_V1_9_B_EXPECTED_OUTCOME_CONTRACT_R1.json` `A21568B904F226AEB94FB17EF26E9820DDFF3F6EF1F2432AD9905B95AC10AEB1` |
| Pre-write checkpoint | MATCHED | `evidence/portable/r1.9b/11_V1_9_B_PRE_WRITE_CHECKPOINT_R1.json` `B0A19C2879A7A8AC9EFE06DCEF9B33F38071CB0B7E0C83FEB0AE583E1F0095B8` |
| Live mission contract | MATCHED | `evidence/portable/r1.9b/01_V1_9_B_LIVE_MISSION_CONTRACT_R1.json` `49F6B88CE4361993A0F3337B8446172B25CD7DBF71D523E7DA8F34F60476A0F8` |
| Attempt-2 single-use lock | MATCHED | `evidence/portable/r1.9b/PRE_MUTATION_SINGLE_USE_LOCK_HF06_CC06B59F341E9B70844F7BEE48F6917303C094206431C228575F91E4500B9E09.json` `DFE129A6D66656B4477B1693D5073CD17B40918516DCF725A6193C019B7BB275` |
| Attempt-2 execution output | MATCHED | `evidence/portable/r1.9b/02_HF06_LIVE_EXECUTION_OUTPUT_R2.txt` `227DF3A15E55AB7E380ACD990F62D511CD933BF3A8254282D0A4AEC8264FEA49` |
| Validation raw response | MATCHED | `evidence/portable/r1.9b/05_RUN_VALIDATION_RAW_RESPONSE.txt` `79E493808385BCAB300B757882FACF8B3BCDC6B04117F926DC1736FC3DE50182` |
| Object-type-details raw response | MATCHED | `evidence/portable/r1.9b/04_GET_OBJECT_TYPE_DETAILS_RAW_RESPONSE.txt` `09F2E8AA655844DBF72C279465C7DB3C3B60B61EB9C786B16CBB1933F26DCB72` |
| Reconciliation adjudication result | MATCHED | `evidence/portable/r1.9b/09_ADJUDICATION_RESULT_R2.json` `4BEAD2D1FFC060476E2ACB2D5A7DFAB0D28950518325A417BC691E9A81A60D02` |
| HF06 signed runner `DE183ABC...` | UNVERIFIABLE | Frozen hash confirmed by lock (`script_sha256`) and SHA256SUMS; original bytes absent. Repo copy is a normalized reading copy (`6446AB83A3AF6539...`) |
| HF06 attempt-2 authorization `CC06B59F...` | UNVERIFIABLE (hash-only by design) | Hash corroborated by the lock's `authorization_sha256` |
| Validation raw response content | PARTIAL | `isError: true`: Unable to initialize the ADT Discovery; carries no information about the object |
| Raw CREATE response | **MISSING** | Never persisted; the runner stopped before writing a receipt. This is why the cause of the absent `filePath` is undetermined |
| Authoritative repository readback | MISSING | Eclipse bridge unavailable; none captured |
| Adjudication `prior_sap_writes: 0` | PARTIAL | Describes the reconciliation run only; must not be read as HF06 attempt-2 write accounting |

## 7. Exact unresolved state

- CREATE tool call reached provider: TRUE (evidence is indirect: runner output + code path; raw response not preserved)
- ACTIVATE tool call reached provider: FALSE (code path: ACTIVATE request is constructed only after the file-path check)
- CREATE commit state: UNKNOWN; object state inference: UNKNOWN; authoritative repository readback: FALSE
- Execution receipts / outcome receipt / final receipt / authorization-consumed receipt: none written
- HF06 replay authorized: FALSE; authorization reuse authorized: FALSE

## 8. All cited SHA-256 anchors

| Anchor | Status | Local artifact |
|---|---|---|
| `MCR_R1_6_FROZEN_SCIENTIFIC_MANUSCRIPT` `E589393C6EEA...` | MISSING (cited by verified PDF) | - |
| `MCR_R1_7_PUBLICATION_FREEZE` `48FA1C707002...` | MATCHED | `evidence/portable/r1.7/MCR_R1_7_PUBLICATION_FINAL_FREEZE_R1.zip` |
| `MCR_P6D_BOUNDED_WRITE_CLOSURE` `D6ECA3A411DC...` | MATCHED | `evidence/portable/r1.7/MCR_R2E_P6_D1_SCIENTIFIC_CLOSURE_R1.zip` |
| `MCR_R1_8_EXTERNAL_REVIEW_REFRESH` `28DA3688FCEC...` | MATCHED | `evidence/portable/r1.8/MCR_R1_8_EXTERNAL_REVIEW_PACKAGE_REFRESH_R1.zip` |
| `MCR_R1_8_REVIEWER_PDF_PACKAGE` `A6685F627636...` | UNVERIFIABLE | no bytes in Git |
| `MCR_R1_8_C1D_CLOSURE` `296961C6CB47...` | MATCHED | `evidence/portable/r1.8/MCR_R2E_P8_C1D_LIVE_FOUR_PROVIDER_SCIENTIFIC_CLOSURE_R1.zip` |
| `MCR_R1_8_C2C_CLOSURE` `F347FC825D9E...` | MATCHED | `evidence/portable/r1.8/MCR_R2E_P8_C2C_MULTI_MISSION_OUTCOME_AND_SCIENTIFIC_CLOSURE_R1.zip` |
| `MCR_R1_9_A_FOUNDATION` `4F018E2F1EBE...` | MATCHED | `evidence/portable/r1.9a/MCR_R1_9_A_GOVERNED_EXECUTION_FOUNDATION_R1.zip` |
| `MCR_R1_9_B_PREWRITE_FREEZE` `3DFE6756695A...` | MATCHED | `evidence/portable/r1.9b/MCR_R1_9_B_LIVE_GOVERNED_MUTATION_AND_OUTCOME_R1_PREWRITE_FREEZE.zip` |
| `HF06_SIGNED_SOURCE` `DE183ABC47B8...` | UNVERIFIABLE | no bytes in Git |
| `HF06_ATTEMPT2_AUTHORIZATION` `CC06B59F341E...` | UNVERIFIABLE | no bytes in Git |
| `HF06_ATTEMPT2_SINGLE_USE_LOCK` `DFE129A6D666...` | MATCHED | `evidence/portable/r1.9b/PRE_MUTATION_SINGLE_USE_LOCK_HF06_CC06B59F341E9B70844F7BEE48F6917303C094206431C228575F91E4500B9E09.json` |
| `HF06_VALIDATION_RAW` `79E493808385...` | MATCHED | `evidence/portable/r1.9b/05_RUN_VALIDATION_RAW_RESPONSE.txt` |
| `HF06_DETAILS_RAW` `09F2E8AA6558...` | MATCHED | `evidence/portable/r1.9b/04_GET_OBJECT_TYPE_DETAILS_RAW_RESPONSE.txt` |
| `HF06_ADJUDICATION_R2_SIGNED_SCRIPT` `2A463A785F38...` | UNVERIFIABLE | no bytes in Git |
| `MCR_R1_6_1_ORIGINAL_PDF` `AD45F74150D9...` | MATCHED | `evidence/portable/r1.6/From_Tools_to_Missions_Mission_Capability_Runtime_R1_6_1.pdf` |
| `MCR_R1_6_ADVERSARIAL_REVIEW_MD` `14EE73D372D9...` | MATCHED | `evidence/portable/r1.6/MCR_R1_6_ADVERSARIAL_REVIEW.md` |
| `MCR_R1_6_1_TARGETED_REVIEW_RC1` `F54F677A1737...` | MATCHED | `evidence/portable/r1.6/MCR_R1_6_1_TARGETED_REVIEW_RC1.zip` |
| Register `MCR-R1.7-P7` (54 hex chars) | CONFLICT (malformed) | - |

Totals: anchors in `FROZEN_EVIDENCE_ANCHORS.json` = 15; MATCHED = 13; remaining are bytes-absent or hash-only. One additional register entry is malformed.
