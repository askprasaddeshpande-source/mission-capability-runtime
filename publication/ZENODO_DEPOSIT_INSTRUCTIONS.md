# Zenodo deposit for release v1.9.0

Status: **not yet deposited.** A Zenodo account login is required; none was available to the automated release process. No DOI exists or is recorded anywhere in this repository.

Deposit (web UI, new upload):

1. Files, from the GitHub release `v1.9.0` (hashes in `RELEASE_ASSETS_SHA256.txt`):
   - `MCR_R1.9_From_Tools_to_Missions_R3.pdf`
   - `MCR-PUBLIC-REPRODUCIBILITY-v1.9.0.zip`
   - `SHA256SUMS.txt`
2. Metadata: copy from `publication/ZENODO_DEPOSIT_METADATA_v1.9.0.json` (matches the conventions of the sibling ACLA and EAF records: related identifier to the GitHub release, CC BY 4.0).
3. Publish, then record the real DOI in `CITATION.cff` (`doi:`), `README.md` and the release notes in one follow-up commit. `python tools/verify_fresh_clone.py` validates the DOI format.

Do not describe the record as proof of end-to-end live mutation; keep the R1.9B bounded result in the description.
