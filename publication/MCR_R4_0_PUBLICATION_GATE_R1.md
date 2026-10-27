# MCR 4.0 Publication Gate R1 — Draft / Not Released

**26 October 2026** | **MCR 4.0 scope:** Owner-closed Class A synthetic P1 only.

## Authority and immutable research boundaries

- Preserve MCR 1.9 historical release and MCR 3.0 frozen main commit `7326207ed86b258ffa233e37a1e4f611a816aa55`.
- Preserve the six owner-frozen Class A contracts and their original SHA-256 hashes; do not silently rewrite or treat them as Class B.
- Final P1 closure decision: `MCR_R4_0_P1_CLOSED_BOUNDED_SYNTHETIC_RESEARCH`.
- Do not imply live SAP, production, enterprise API or integrated ACLA/EAF provider qualification.

## Evidence available from the owner-supplied R6 execution receipt (not re-verified here)

- 131/131 units; 18/18 synthetic scenarios; 22/22 R2 regressions; 40/40 reconciled reviewer checks.
- Original reviewer suite 38/40 and raw runner exit 1 must remain visible.
- Independent Claude reviewer: reported zero blocking findings; 64 adversarial tests.
- Mutation evaluation: 45 distinct mutants; 39 raw detections + four material survivors killed by supplemental probes + two bounded redundancies.
- R6 package SHA-256 (executor-reported): `cf3f7162d09070ca86840e741f3e81a1baa5ff9350d4dd1a8eac156f7250074c`.
- Complete private archive NOT independently rehashed by this ChatGPT session.

## Public release blocking gates

1. Owner inspects and approves research manuscript PDF and source, including private-path scrub and intellectual-property review.
2. Reconcile exact final manuscript with independently read-back R6 archive and the original reviewer exceptions.
3. Validate secret scanning, licensed third-party content, manifest hashes and public-safe artifact completeness.
4. Attach public-safe paper PDF, source and claim/evidence matrix to a release candidate (not the original private 30,869-entry R6 package).
5. Preserve limits and disclosed `~/.gnupg` reviewer side effect; no silent erasure.
6. Obtain explicit owner approval for a GitHub **release/tag**, which is separate from permission to stage this branch.
7. Obtain explicit owner approval for the Zenodo **Publish** action. Zenodo archival DOI must not be fabricated.
8. After publication, verify release assets, hashes, DOI and `CITATION.cff` updates. Do not rewrite historical tags.

**Current disposition:** `PUBLICATION_CANDIDATE_ONLY` — article and gate can be reviewed on a branch; research PDF/binary release assets and Zenodo DOI remain pending.

**Note on Zenodo:** GitHub-linked software archives and manually deposited research-paper records are distinct archival objects. Avoid creating duplicate DOIs for the same object without metadata cross-links.
