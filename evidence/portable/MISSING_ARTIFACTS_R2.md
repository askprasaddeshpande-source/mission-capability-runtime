# MCR Missing / Unresolved Portability Artifacts R2

## A. Frozen scientific manuscript: bytes absent everywhere searched

- **R1_6_FROZEN_SCIENTIFIC_MANUSCRIPT** — expected SHA-256 `E589393C6EEA0BA92E4EC521D1577A6F561F9ADFA38FF9EEE97A94695C666D90` (`HISTORICALLY_FROZEN`).
- Searched: this repository (all files and nested ZIPs); `D:\MCP` (4,290 files hashed including nested ZIPs); name search of `D:`; two additional candidates hashed (`E5F1E5EC...`, `141907...`) and rejected.
- Not recreated, not substituted. The hash is cited by the recovered R1.6.1 PDF and by the RC1 package manifest, so the **citation chain is verifiable but the document is not**.
- Effect: the MCWS 5/48, 17/48, 30/48 figures can be audited only as reported in the R1.6.1 PDF, not recomputed from the frozen manuscript or raw experiment data.

## B. Six signed scripts: original bytes unavailable (normalized reading copies only)

| Artifact | Frozen source SHA-256 | Mandatory |
|---|---|---|
| R1_8_WATCHDOG_R2 | `3178680E...` | yes |
| HF05_SESSION_PROTOCOL_FORENSIC | `3DAAA382...` | no |
| HF06_FINAL_QUALIFIED_RUNNER | `DE183ABC47B8F025ED60CFE5CFEA4527585FB20154C949628BDE95E42A0D3C88` | yes |
| HF06_CREATE_COMMIT_FORENSIC | `698968B9...` | yes |
| HF06_PREFLIGHT_RECONCILIATION | `50411974...` | yes |
| HF06_ADJUDICATION_R2_SCRIPT | `2A463A785F383B88ABFE2FFF331CAE854C9F2FBB7353247D7433BC4E8B7D4C03` | yes |

The copies in `evidence/portable/` are LF-normalized by the R1 commit. Their hashes and Authenticode signatures do **not** match the frozen originals. They are readable for audit of logic only. Do not execute them and do not cite their repo hash as the frozen hash. Recovery requires the original signed files from the original workstation.

The independently recovered R1.9B prewrite ZIP and HF06 outputs still support the central R1.9B result (`CREATE_FILEPATH_MISSING` at the CREATE response; lock present; output text preserved).

## C. Deliberately hash-only

- **HF06_ATTEMPT2_AUTHORIZATION** — `CC06B59F341E9B70844F7BEE48F6917303C094206431C228575F91E4500B9E09`. Authority material, excluded by design, not reusable.

## D. Resolved in R2

- R1_6_1_ORIGINAL_PAPER: `AD45F741...` (matches RC1 frozen manifest)
- R1_6_ADVERSARIAL_REVIEW: source recovered, hash newly recorded `14EE73D3...`
- R1_9B_MISSION_ENVELOPE, R1_9B_EXPECTED_OUTCOME, R1_9B_PREWRITE_CHECKPOINT: extracted from the prewrite ZIP
