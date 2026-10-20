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

- [ ] Approved evidence-copy list frozen
- [x] Secret scan PASS
- [ ] Private-path scan PASS
- [x] Authentication material excluded
- [ ] Customer/client material excluded
- [ ] Every included artifact hashed
- [ ] FROZEN_EVIDENCE_ANCHORS verified
- [ ] SHA256SUMS generated after final file set

## Manuscript

- [x] Time-sensitive vendor/platform claims explicitly dated (not refreshed; see reference register)
- [ ] Figures regenerated from approved sources
- [ ] PDF reviewed page-by-page
- [x] Claim language matches evidence class
- [x] R1.9B not described as completed live mutation
- [x] Autonomous self-healing not claimed

## Archival release

- [ ] Version selected
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
- [ ] Owner supplies frozen manuscript and six signed originals, or accepts documented gaps
- [ ] Owner reviews raw SAP responses and author email for public inclusion
- [ ] Time-sensitive references re-verified or removed (22 + 9 + 1 entries)
- [ ] P7 closure ZIP hash recovered or entry removed from the evidence register
- [ ] Figure rendered from `architecture/MCR_R1.9_FINAL_ARCHITECTURE_FIGURE_SPEC_R2.md`
- [ ] Owner-authorized push of the candidate branch
