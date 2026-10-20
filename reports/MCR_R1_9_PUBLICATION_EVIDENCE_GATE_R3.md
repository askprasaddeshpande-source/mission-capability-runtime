# MCR R1.9 Publication Readiness / Evidence Sufficiency Gate R3

Independent adjudication performed on the merged `main` baseline (`299eb18`) plus the R2 closure work. No SAP, MCP or model execution was performed.

## Decision block

```
SCIENTIFIC_CLOSURE_READINESS=READY_TO_CLOSE_AND_PUBLISH_WITH_DOCUMENTED_EVIDENCE_GAPS
PUBLICATION_EVIDENCE_GATE=PASS_WITH_DOCUMENTED_GAPS
CLAIM_CRITICAL_EVIDENCE_MISSING=0
ARCHIVAL_EVIDENCE_GAPS=9
NEW_EXPERIMENT_REQUIRED_FOR_CURRENT_CLAIMS=FALSE
CAN_CLOSE_MCR_R1_9_NOW=TRUE
CAN_MOVE_TO_PUBLICATION_NOW=TRUE
RECOMMENDED_PUBLICATION_STATE=RELEASE_WITH_DOCUMENTED_GAPS
RECOMMENDED_NEXT_ACTION=Apply adversarial-review remediations to manuscript R3, build PDF and package, release with the gaps stated in limitations, reproducibility, manifest and release notes.
```

`ARCHIVAL_EVIDENCE_GAPS=9` counts catalog-level artifacts: frozen manuscript (1), six signed scripts (6), R1.8 reviewer PDF package (1), R1.7 P7 closure ZIP (1). Two further items were never retained (raw HF06 CREATE response; HF05 failure transcript) and are handled as claim limitations, not recoverable artifacts.

## Per-artifact adjudication

| ARTIFACT_ID | STATUS | EVIDENCE_ROLE | AFFECTED_CLAIMS | PUBLICATION_BLOCKER | RATIONALE |
|---|---|---|---|---|---|
| R1_6_1_ORIGINAL_PAPER | RECOVERED | ARCHIVAL | C01, C02 | FALSE | Byte-exact; hash equals the RC1 manifest `canonical_pdf_sha256`; content verified |
| R1_6_FROZEN_SCIENTIFIC_MANUSCRIPT | MISSING | ARCHIVAL | C01, C02 (provenance only) | FALSE | The numbers are independently anchored three ways: PDF Table 16 evidence capsule, the RC1 claim-evidence audit (frozen numerical anchors), and the hash chain. The paper reports a frozen prior result and does not claim to reproduce it. Stated as limitation |
| R1_6_ADVERSARIAL_REVIEW | RECOVERED | ARCHIVAL | claim narrowing history | FALSE | Source recovered; hash newly recorded |
| R1_9B_MISSION_ENVELOPE | RECOVERED | ARCHIVAL | C11 | FALSE | From prewrite ZIP; entry hash equals the ZIP package manifest |
| R1_9B_EXPECTED_OUTCOME | RECOVERED | ARCHIVAL | C17, C27 | FALSE | As above |
| R1_9B_PREWRITE_CHECKPOINT | RECOVERED | ARCHIVAL | C11 | FALSE | As above |
| HF06 runner and 5 other signed scripts (original bytes) | MISSING (normalized copies only) | ARCHIVAL | C13, C15, C16 | FALSE | Frozen hashes corroborated by the lock (`script_sha256`) and SHA256SUMS. The surviving output quotes line 195 verbatim and it equals line 195 of the normalized copy, so the logic used for code-path inference is corroborated. Stated as limitation |
| R1.8 reviewer PDF package | MISSING | NICE_TO_HAVE | none | FALSE | Presentation package; no claim rests on it |
| R1.7 P7 closure ZIP | MISSING (hash malformed in register) | ARCHIVAL | C22 | FALSE | The negative self-healing result is independently recorded in the R1.8 manuscript (section 12.3) and the C2C limitations (`AUTONOMOUS_SELF_HEALING=NOT_CLAIMED`) |

## Required questions

1. **Frozen MCWS result.** Nothing claim-critical is missing. The paper reports the result as frozen and unchanged, anchored by the R1.6.1 PDF, its evidence capsule, and the RC1 audit. The frozen manuscript is an archival gap; recomputation from raw data is explicitly not claimed.
2. **R1.7 conclusions.** No claim-critical gap. The R1.7 publication-freeze ZIP and the P6-D1 closure ZIP are in Git and hash-match. The P7 closure ZIP is absent, but its conclusions are restated in the R1.8 manuscript and C2C limitations, and the paper makes no claim that depends on the P7 ZIP bytes.
3. **R1.8 conclusions.** No gap. C1D and C2C closure ZIPs and the external review refresh are in Git and hash-match. The raw historical C2B Fiori contract was never captured; the paper already limits the drift claim to "relative to the C1 freeze".
4. **R1.9A conclusions.** No gap. The foundation package and runner are byte-exact. Claims are classified SYNTHETIC/LOCAL.
5. **R1.9B bounded partial live execution.** No claim-critical gap. Supported by the frozen prewrite package, the single-use lock, the execution output, and the adjudication. The following limits are stated, not repaired: the raw CREATE response was not retained; reach of the ADT MCP provider does not establish reach of the SAP backend; the retained reconciliation validation response (`isError: true`, "Unable to initialize the ADT Discovery") carries no information about the object.
6. **Honest classification of every material claim.** Yes. 30 claims were classified in R2; R3 adds three and narrows three (C14, C15, C17).
7. **Unresolved claims as PARTIAL / NOT_ESTABLISHED / DEFERRED.** Yes, and that is the treatment used. No new experiment is needed for any current claim.
8. **Would publication misrepresent an unresolved state?** Not after the R3 remediations (see the external adversarial review). Before them, three statements were stronger than the evidence: "demonstrated replay protection", HF06 qualification steps stated as established, and an uncaveated causal reading of the MCWS result.

## R1.9B sufficiency rule check

Supported by retained evidence: CREATE reached the ADT MCP provider; ACTIVATE did not; commit state UNKNOWN; no authoritative readback; HF06 replay barred (lock present, authorization hash-only and not reusable). The manuscript does not claim end-to-end completion, that CREATE did or did not commit, zero SAP writes, activation, outcome validation, autonomous recovery or compensation.

## Conclusion

No claim-critical evidence is missing and no new experiment is required. UNKNOWN is the valid final scientific state. Publication proceeds with the gaps documented in the manuscript limitations, `REPRODUCIBILITY.md`, the portability manifest, the source-of-record audit and the release notes.
