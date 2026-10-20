# MCR Repository Portability

Portable evidence is indexed under:

- `evidence/portable/PORTABILITY_MANIFEST_R2.json` (current; supersedes R1)
- `evidence/portable/PORTABILITY_SUMMARY_R2.md`
- `evidence/portable/MISSING_ARTIFACTS_R2.md`
- `reports/MCR_PORTABILITY_FINAL_GAP_RECOVERY_R1.md`

R1 records (`*_R1.*`) are retained unchanged as history. Note: the R1 summary's `HASH_MISMATCH=0` was incorrect; see the recovery report.

## Rules

- `evidence/portable/**` is marked `-text` in `.gitattributes`. Hash-bound evidence must never be line-ending or BOM normalized.
- Historical live authorizations and authentication context are not portable execution authority and are intentionally excluded from exact Git storage.
- Nothing in this repository grants authority to run any historical script. Six scripts are normalized reading copies only and must not be executed.

## Verify a fresh clone

```
git clone https://github.com/askprasaddeshpande-source/mission-capability-runtime.git
cd mission-capability-runtime
git checkout <candidate-branch>
python -c "import json,hashlib; m=json.load(open('evidence/portable/PORTABILITY_MANIFEST_R2.json')); bad=[a['artifact_id'] for a in m['artifacts'] if a['included_exact'] and hashlib.sha256(open(a['repo_path'],'rb').read()).hexdigest().upper()!=a['sha256']]; print('mismatches:',bad)"
```

The fresh clone is scientifically complete for available evidence. Full historical source lineage is not verifiable until the frozen manuscript and the six signed originals are supplied (see `MISSING_ARTIFACTS_R2.md`).
