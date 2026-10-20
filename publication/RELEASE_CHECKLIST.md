# MCR Release Checklist

## Scientific closure

- [x] Closure classification selected: BOUNDED_CLOSURE_WITH_UNRESOLVED_CREATE_COMMIT_STATE (owner freeze pending)
- [x] Authoritative readback incorporated, or unresolved state explicitly frozen
- [x] No historical runner replayed
- [x] No historical authorization reused
- [x] Claim/evidence audit R2 produced (self-review; independent external review still pending)
- [x] Original MCWS metrics unchanged
- [x] Negative/partial R1.9B result preserved

## Evidence hygiene

- [x] Approved evidence-copy list frozen (`research-package/PUBLIC_EVIDENCE_INCLUSION_PLAN_R3.md`)
- [x] Secret scan PASS
- [x] Private-path scan reviewed (3 generic user-profile path hits in scripts, accepted and documented)
- [x] Authentication material excluded
- [x] Customer/client material excluded
- [x] Every included artifact hashed
- [x] FROZEN_EVIDENCE_ANCHORS verified (10 with bytes verified; 5 bytes-absent, documented)
- [x] SHA256SUMS generated after final file set

## Manuscript

- [x] Time-sensitive vendor/platform claims explicitly dated (not refreshed; see reference register)
- [x] Figures regenerated from approved sources (SVG from the figure specification; rendered and visually checked)
- [ ] PDF reviewed page-by-page (3 of 23 pages visually checked; all pages checked by text extraction, heading order, values and metadata)
- [x] Claim language matches evidence class
- [x] R1.9B not described as completed live mutation
- [x] Autonomous self-healing not claimed

## Archival release

- [x] Version selected (1.9.0)
- [ ] Git tag created
- [ ] GitHub release created
- [ ] Release ZIP attached
- [ ] Release ZIP hash published
- [ ] Zenodo archive minted
- [ ] CITATION.cff updated with DOI/date
- [ ] PUBLICATION_MANIFEST frozen
- [ ] Repository visibility intentionally set for release

## R2 additions

- [x] Evidence bytes verified from a fresh clone (28/28 exact)
- [x] Documented gaps accepted for release (gate: PASS_WITH_DOCUMENTED_GAPS; none claim-critical)
- [x] Raw SAP responses, principal context and author email reviewed and decided (include)
- [ ] Time-sensitive references re-verified or removed (22 + 9 + 1 entries)
- [ ] P7 closure ZIP hash recovered or entry removed from the evidence register
- [x] Figure rendered from the figure specification
- [x] Delegated push and merge performed through pull requests
