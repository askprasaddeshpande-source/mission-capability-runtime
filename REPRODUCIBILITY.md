# Reproducibility

## Current repository status

This repository is a **draft closure workspace**, not yet the frozen MCR public reproducibility release.

The original R1.6.1 MCWS scientific experiment is frozen and must not be rerun merely to improve presentation.

R1.7/R1.8/R1.9 evidence must likewise be treated as historical/frozen evidence where explicitly closed.

## No implicit authority

Nothing in this repository grants permission to:

- call an enterprise mutation capability;
- reuse a historical authorization;
- rerun HF06;
- delete or clean up `ZCL_MCR19B_9533C4D8`;
- activate the object;
- compensate a prior action; or
- substitute target/package/provider.

Historical PowerShell files are research evidence, not standing authority.

## HF06 replay boundary

HF06 attempt 2 created a single-use lock before the CREATE call.

Current rule:

`HF06_DO_NOT_RERUN=TRUE`

`HF06_AUTHORIZATION_REUSE_AUTHORIZED=FALSE`

## Current outcome uncertainty

Observed:

- CREATE provider call reached.
- ACTIVATE provider call did not reach.
- authoritative repository readback was unavailable.
- secondary read/validation reconciliation remained inconclusive.

Therefore:

`CREATE_COMMIT_STATE=UNKNOWN`

A reproducibility package must preserve this unknown state.

## Release construction

Before a public reproducibility ZIP is built:

1. collect only approved evidence copies;
2. verify every frozen anchor;
3. remove authentication material and private paths;
4. run a secret scan;
5. run a private-path scan;
6. preserve Authenticode/signature evidence only where safe to publish;
7. generate `SHA256SUMS.txt`;
8. freeze `PUBLICATION_MANIFEST.json`;
9. generate the reviewed PDF from the final manuscript;
10. build the release ZIP without rerunning experiments or enterprise mutations.

## Frozen anchor policy

`FROZEN_EVIDENCE_ANCHORS.json` is the expected hash index.

Files that cannot be safely redistributed should remain hash-referenced rather than copied into the public package.

## Scientific separation

Keep these evidence classes distinct:

- original frozen MCWS experiment;
- separate engineering POCs;
- R1.7/R1.8 runtime/provider studies;
- R1.9A local deterministic foundation;
- R1.9B bounded live mutation attempt;
- publication-layer exposition.

A publication build must not convert architecture synthesis into empirical proof.
