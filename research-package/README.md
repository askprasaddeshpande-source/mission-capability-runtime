# Research package boundary

This folder is reserved for the sanitized MCR reproducibility package.

It is intentionally not populated with raw local evidence in the draft scaffold.

## Include only after closure review

Candidate release contents:

- frozen mission contracts;
- sanitized provider contract fingerprints;
- MCWS benchmark materials already cleared for publication;
- R1.7/R1.8 closure evidence approved for redistribution;
- R1.9A deterministic foundation artifacts;
- R1.9B prospective contract and sanitized live evidence;
- call accounting;
- claim/evidence audit;
- closure report.

## Never publish directly from local evidence roots

Do not copy:

- bearer tokens;
- DPAPI blobs;
- auth-context files;
- local certificates/private keys;
- machine-specific secrets;
- private source paths where unnecessary;
- customer/client data;
- unreviewed SAP content.

Use hash anchors when redistribution is inappropriate.

## Inclusion plan

See [`PUBLIC_EVIDENCE_INCLUSION_PLAN_R2.md`](PUBLIC_EVIDENCE_INCLUSION_PLAN_R2.md) for the per-artifact INCLUDE / HASH_ONLY / EXCLUDE / NEEDS_OWNER_REVIEW classification. This folder remains unpopulated; nothing is published.
