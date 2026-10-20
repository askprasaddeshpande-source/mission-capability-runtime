# MCR paper

**Title:** From Tools to Missions: A Mission-Capability Runtime for Enterprise AI

**Original subtitle:** Credible Lineage, Measurable Post-LLM Capability Scoping, Engineering Proof, and a Prerequisite-Conditioned Long-Horizon Roadmap

**Author:** Prasad Deshpande  
**ORCID:** 0009-0008-1344-6585

This folder preserves the original MCR research-paper lineage and hosts the R1.9 closure draft.

## Source of record

Original adversarially hardened candidate:

- Version: `R1.6.1`
- Date: `31 August 2026`
- Frozen scientific manuscript SHA-256: `E589393C6EEA0BA92E4EC521D1577A6F561F9ADFA38FF9EEE97A94695C666D90`

See [`ORIGINAL_R1.6.1_SOURCE_OF_RECORD.md`](ORIGINAL_R1.6.1_SOURCE_OF_RECORD.md).

## Current manuscript

- [`MCR_Manuscript_R1.9_EXTERNAL_REVIEW_CANDIDATE_R3.md`](MCR_Manuscript_R1.9_EXTERNAL_REVIEW_CANDIDATE_R3.md) — final manuscript for release 1.9.0 (original title, subtitle and section progression preserved)
- [`MCR_Manuscript_R1.9_EXTERNAL_REVIEW_CANDIDATE_R2.md`](MCR_Manuscript_R1.9_EXTERNAL_REVIEW_CANDIDATE_R2.md) — earlier candidate, retained
- [`MCR_Manuscript_R1.9_CLOSURE_DRAFT_R1.md`](MCR_Manuscript_R1.9_CLOSURE_DRAFT_R1.md) — earlier closure draft, retained unchanged

The original R1.6.1 PDF is held byte-exact at `../evidence/portable/r1.6/`.

## Scientific status

The original MCWS benchmark remains frozen and unchanged.

R1.7/R1.8 add separately frozen runtime/provider engineering evidence.

R1.9A adds a deterministic governed-execution foundation.

R1.9B is a **partial live mutation result**, not a completed success. CREATE reached the ADT provider; ACTIVATE did not. Persistent SAP state after the CREATE response (which lacked the expected file path) remains unresolved; `MCR_R1_9=BOUNDED_CLOSURE_WITH_UNRESOLVED_CREATE_COMMIT_STATE`.

## Publication principle

> **The LLM proposes semantics; the runtime binds authority.**

> **Execution receipt != validated outcome. EXECUTED != COMPLETE.**

## Public-release rule

Do not tag, publish a release, mint a DOI, or describe R1.9 as closed until:

1. the closure classification is frozen;
2. the final evidence bundle is hashed;
3. claim/evidence review is complete;
4. private-path and secret scans pass; and
5. the final manuscript preserves the unresolved/negative result without strengthening it.
