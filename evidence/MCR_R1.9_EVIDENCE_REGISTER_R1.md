# MCR R1.9 Evidence Register R1

This is a publication-preparation index. It does not replace the original local evidence.

## Major frozen / qualified anchors

| ID | Artifact / role | SHA-256 / identity | State |
|---|---|---|---|
| MCR-R1.6-SCI | Frozen scientific manuscript | `E589393C6EEA0BA92E4EC521D1577A6F561F9ADFA38FF9EEE97A94695C666D90` | Frozen |
| MCR-R1.7-PUB | R1.7 publication freeze ZIP | `48FA1C707002314752245434F5BDC09F96C5DEAB6CC27BC05F0483908457F1F3` | Frozen |
| MCR-R1.7-P7 | P7 closure ZIP | `082CC73D151597B0FAF28EA2BFA55171316C3BDB28A544B6682F52` | Frozen; hash as preserved in program record |
| MCR-P6D | Bounded SAP write closure ZIP | `D6ECA3A411DC1E224DCE677C404575A530C04BFB625852734802D61848AE953C` | Frozen |
| MCR-R1.8-EXT | R1.8 external review refresh ZIP | `28DA3688FCECA431B5272659B4C4C09F83D851AF598604CC3E83AD3215434DDC` | Frozen |
| MCR-R1.8-PDF | R1.8 reviewer PDF package ZIP | `A6685F627636A0DFB7C5E824FA430642D0280BFA0E4D691AFA4BAA9AD78B2BCB` | Frozen |
| MCR-R1.8-C1 | C1D scientific closure ZIP | `296961C6CB47C876B35CB107DC6EDB3D8A4803A5611105A78102C440A2731B14` | Frozen |
| MCR-R1.8-C2 | C2C scientific closure ZIP | `F347FC825D9E444E9E0FAE61D806304C8B2CA540A4D6EA037AB5412D8AEEA61D` | Frozen |
| MCR-R1.9A | Governed execution foundation ZIP | `4F018E2F1EBE86AEF78E94989685B02A2E41BFFB73238A21F63AC12C8190E1F2` | Frozen |
| MCR-R1.9B-FREEZE | Prewrite contract freeze ZIP | `3DFE6756695A67EF28BBF54F5C7B61746A819B4161923B0319FEC26683C3ECF9` | Frozen |
| HF06-SOURCE | Signed HF06 runner | `DE183ABC47B8F025ED60CFE5CFEA4527585FB20154C949628BDE95E42A0D3C88` | Frozen / do not rerun |
| HF06-AUTH2 | Live attempt-2 authorization | `CC06B59F341E9B70844F7BEE48F6917303C094206431C228575F91E4500B9E09` | Historical / not reusable |
| HF06-LOCK | Attempt-2 single-use lock | `DFE129A6D66656B4477B1693D5073CD17B40918516DCF725A6193C019B7BB275` | Replay barrier |
| HF06-VALIDATION-RAW | Captured run-validation response | `79E493808385BCAB300B757882FACF8B3BCDC6B04117F926DC1736FC3DE50182` | Read/validation evidence |
| HF06-DETAILS-RAW | Captured object-type-details response | `09F2E8AA655844DBF72C279465C7DB3C3B60B61EB9C786B16CBB1933F26DCB72` | Read evidence |
| HF06-ADJ-R2 | Signed local adjudication script | `2A463A785F383B88ABFE2FFF331CAE854C9F2FBB7353247D7433BC4E8B7D4C03` | Local-only adjudication |

## Current unresolved state

- CREATE reached provider: **YES**
- ACTIVATE reached provider: **NO**
- HF06 replay allowed: **NO**
- HF06 authorization reusable: **NO**
- authoritative repository readback: **NO**
- create commit: **UNKNOWN**
- successful live mission completion: **NO**

## Publication-copy rule

Raw evidence must be copied into the eventual public research package only after:

1. secret scan;
2. private-path scan;
3. license review;
4. byte/hash verification against this register; and
5. final closure approval.

Do not publish local authentication context, tokens, certificates, user paths or private environment metadata.

## R2 erratum (appended; R1 table above is unchanged)

- `MCR-R1.7-P7` lists a 54-character value, which is not a valid SHA-256 and is not in `FROZEN_EVIDENCE_ANCHORS.json`. It is unverified and must be recovered from the original workstation or removed. See `reports/MCR_R1_9_SOURCE_OF_RECORD_AUDIT_R2.md`.
- `HF06-SOURCE`, `HF06-ADJ-R2` and the other signed scripts: original bytes are not in Git (normalized reading copies only). See `evidence/portable/MISSING_ARTIFACTS_R2.md`.
