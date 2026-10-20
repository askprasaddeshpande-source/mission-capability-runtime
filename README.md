# Mission-Capability Runtime (MCR)

**From Tools to Missions: A Mission-Capability Runtime for Enterprise AI**

Research repository for the Mission-Capability Runtime (MCR) and Minimum Capability Working Set (MCWS) program.

**Author:** Prasad Deshpande — Independent Researcher  
**ORCID:** 0009-0008-1344-6585  
**Research & Architecture:** https://prasaddeshpande.com/

> **Repository status: release `v1.9.0` with documented evidence gaps.**  
> This is an independent research repository. It is not a peer-reviewed journal or conference publication. The bounded R1.9B live-mutation result is partial (see below); it is not a proof of successful end-to-end live mutation.

## Research lineage

The repository preserves the original MCR research framing rather than replacing it with a new paper structure.

The source-of-record lineage begins with:

**From Tools to Missions: A Mission-Capability Runtime for Enterprise AI**  
*Credible Lineage, Measurable Post-LLM Capability Scoping, Engineering Proof, and a Prerequisite-Conditioned Long-Horizon Roadmap*

Original adversarially hardened whitepaper candidate: **R1.6.1 — 31 August 2026**

Frozen scientific manuscript SHA-256:

`E589393C6EEA0BA92E4EC521D1577A6F561F9ADFA38FF9EEE97A94695C666D90`

R1.7, R1.8 and R1.9 extend the engineering and runtime-control evidence while preserving the original MCWS experiment as a separate frozen scientific stream.

## Core thesis

MCR addresses a post-LLM enterprise-runtime problem:

1. represent mission semantics independently of provider/tool identity;
2. resolve the capability requirement for the current mission stage;
3. expose only the stage-relevant Minimum Capability Working Set (MCWS) to probabilistic reasoning;
4. keep admissibility, provider ranking, authority, parameter enforcement and binding deterministic;
5. treat execution receipts and authoritative enterprise outcomes as different states; and
6. re-resolve when mission state, provider state, policy, authority or outcome evidence changes.

Core authority rule:

> **The LLM proposes semantics; the runtime binds authority.**

Core outcome rule:

> **EXECUTED != COMPLETE**

## Frozen MCWS scientific anchor

The corrected R1.6.1 primary result remains the scientific anchor:

| Architecture | Success | Rate |
|---|---:|---:|
| Broad | 5/48 | 10.4% |
| Static | 17/48 | 35.4% |
| MCWS | 30/48 | 62.5% |

Holm-adjusted case-cluster tests reported in R1.6.1:

- Broad–MCWS: `p = 0.00293`
- Static–MCWS: `p = 0.03125`
- Broad–Static: `p = 0.2266`

These results apply to the frozen bounded benchmark. They do not establish universal orchestration superiority, general enterprise safety, production cost savings, or full runtime correctness.

## Current R1.9 closure boundary

R1.9A deterministic governed-execution foundation is complete and frozen.

R1.9B attempted a bounded live SAP mutation under:

- Target: `TRL_EN`
- Object: `ZCL_MCR19B_9533C4D8`
- Package: `ZCLINE`
- Provider: ADT
- Authorized mutations: exactly two
  - `abap_creation-create_object`
  - `abap_activate_objects`
- Outcome validation:
  - `abap_atc_run`
  - `abap_atc_get_result`
- Retries: `0`
- Compensation authority: `FALSE`
- Cleanup/delete authority: `FALSE`

The final HF06 live attempt reached the CREATE provider call and then failed while extracting the returned file path. ACTIVATE was not reached. A single-use lock blocks replay.

At current closure:

`CREATE_COMMIT_STATE=UNKNOWN`

`AUTHORITATIVE_REPOSITORY_READBACK=FALSE`

Therefore R1.9B must **not** be described as a successful end-to-end live mutation.

**Closure classification:** `MCR_R1_9=BOUNDED_CLOSURE_WITH_UNRESOLVED_CREATE_COMMIT_STATE`. Control-plane behavior is supported; complete live mutation/outcome correctness is not. HF06 must not be rerun and its authorization must not be reused. See [`reports/MCR_R1_9_FINAL_SCIENTIFIC_CLOSURE_R3.md`](reports/MCR_R1_9_FINAL_SCIENTIFIC_CLOSURE_R3.md), the [evidence-sufficiency gate](reports/MCR_R1_9_PUBLICATION_EVIDENCE_GATE_R3.md) and the [adversarial review](reports/MCR_R1_9_EXTERNAL_ADVERSARIAL_REVIEW_R3.md).

Publication manuscript: [`paper/MCR_Manuscript_R1.9_EXTERNAL_REVIEW_CANDIDATE_R3.md`](paper/MCR_Manuscript_R1.9_EXTERNAL_REVIEW_CANDIDATE_R3.md) and PDF [`publication/MCR_R1.9_From_Tools_to_Missions_R3.pdf`](publication/MCR_R1.9_From_Tools_to_Missions_R3.pdf).

**Central distinction:** `REQUESTED != AUTHORIZED != BOUND != EXECUTED != COMMITTED != VALIDATED_COMPLETE`.

**Evidence portability:** a fresh clone verifies 28 evidence artifacts byte-exact. The frozen scientific manuscript (`E589393C...`) and the original signed bytes of six historical scripts are not in the repository; they are documented gaps (`evidence/portable/MISSING_ARTIFACTS_R2.md`).

## Repository layout

- [`paper/`](paper/) — manuscript and source-of-record lineage (final: `MCR_Manuscript_R1.9_EXTERNAL_REVIEW_CANDIDATE_R3.md`)
- [`tools/`](tools/) — `verify_fresh_clone.py` (fresh-clone qualification) and `build_pdf.py`
- [`reports/`](reports/) — source-of-record, claim/evidence, consistency and closure audits
- [`evidence/portable/`](evidence/portable/) — byte-exact portable evidence and portability manifests (`-text`: never line-ending normalized)
- [`architecture/`](architecture/) — MCR/MCWS architecture and ACLA/EAF relationship
- [`evidence/`](evidence/) — evidence register and claim/evidence matrix
- [`frozen-evidence-anchors/`](frozen-evidence-anchors/) — release anchor index
- [`research-package/`](research-package/) — eventual sanitized reproducibility package boundary
- [`publication/`](publication/) — asset map and release checklist
- [`social/`](social/) — publication communications only after scientific closure
- [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md) — frozen evidence and rerun rules
- [`FROZEN_EVIDENCE_ANCHORS.json`](FROZEN_EVIDENCE_ANCHORS.json) — hash-bound evidence index
- [`PUBLICATION_MANIFEST.json`](PUBLICATION_MANIFEST.json) — draft publication state
- [`CITATION.cff`](CITATION.cff) — citation metadata
- [`LICENSE_POLICY.md`](LICENSE_POLICY.md) — dual-license policy

## Relationship to ACLA and EAF

The research program intentionally separates three concerns:

- **ACLA** — what should the model know for this mission?
- **EAF** — is the agent authorized and sufficiently informed to act, and was the outcome validated?
- **MCR** — which capability/provider/tool should execute the authorized mission, and under what deterministic runtime controls?

They are complementary layers, not one product.

Recommended closed loop:

`Claude Mods -> ACLA -> EAF pre-action -> MCR -> EAF post-action -> ACLA / evidence`

## Verify this repository

```
python tools/verify_fresh_clone.py
```

This checks evidence hashes, `SHA256SUMS.txt`, frozen anchors, claim-to-artifact linkage, a secret scan and citation metadata. It reads files only and executes nothing from the repository.

## Publication state

GitHub release `v1.9.0`. This tagged snapshot records no DOI; if an archival DOI is later issued it is recorded in `CITATION.cff` on the default branch, not here. Known gaps (frozen manuscript bytes, six signed originals, unverified time-sensitive references) are listed in `evidence/portable/MISSING_ARTIFACTS_R2.md` and the manuscript limitations.

The release preserves negative, partial and unresolved results exactly as observed.

## Licensing

The intended publication policy mirrors the original research repositories:

- **Software / executable research utilities:** Apache License 2.0
- **Original research prose / diagrams / documentation:** CC BY 4.0
- **Third-party material:** remains under its original terms

See [`LICENSE_POLICY.md`](LICENSE_POLICY.md).
