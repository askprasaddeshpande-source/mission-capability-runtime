# MCR R1.9 External-Style Adversarial Review R3

Reviewer stance: skeptical peer reviewer applied to `MCR_Manuscript_R1.9_EXTERNAL_REVIEW_CANDIDATE_R2.md`, with the claim audit, hypothesis matrix and evidence in Git. **Honesty note:** this review was produced by the same agent that drafted the manuscript. It used mechanical pattern sweeps and a re-read of primary evidence to reduce shared-blind-spot risk, but it is not independent and does not replace an external reviewer.

## Verdict

The manuscript is bounded and its denials are consistent. Eight findings were scientifically valid and have been remediated in R3; two are open as documented gaps. No finding required new experimental evidence.

## Findings

| ID | Search target | Finding | Severity | Disposition |
|---|---|---|---|---|
| AR-01 | Inflated causality; confusing engineering proof with science | The MCWS section reported the benchmark result but omitted three limits that the R1.6.1 audit itself records: stage-relevance as the cause is unresolved (no size-matched selection-logic control); Broad also changes the planning mechanism; Static outputs were regraded against the frozen post-change target (M003) without reruns. A reader could infer a causal mechanism the study does not isolate | High | FIXED (section 12 bullets) |
| AR-02 | Ambiguous HF06 language | "CREATE reached the provider" is true for the ADT MCP provider, but reach of the SAP back end is not established. The retained reconciliation response shows the provider could not initialize ADT discovery, so back-end availability around the run is itself uncertain | High | FIXED (abstract, section 1.2, 7.5; claim C15 narrowed) |
| AR-03 | Unsupported "demonstrated" wording | The closure sentence said R1.9 "demonstrated ... mutation budgets, single-use execution control and fail-closed replay protection". The audit classifies replay refusal as untested and the budget as not consumed to completion, so the sentence contradicted the manuscript's own claim audit (C11, C14) | High | FIXED: "exercised"; limits stated in abstract and Appendix A; claims C11 and C14 text aligned |
| AR-04 | Accidental absence inference | "No existence signal" could be read as evidence the object is absent. The validation response was `isError: true` (ADT discovery not initialized) and the details response was generic field metadata; neither concerns the object | High | FIXED (section 7.5; claim C17 narrowed) |
| AR-05 | Evidence not retained but stated as established | The HF01-HF05 defect chronology and the HF06 pre-write qualification steps (signed mock E2E, session-protocol qualification) have no retained transcripts. They were written as findings | Medium | FIXED: labeled owner-reported with provenance notes; claims C31, C32 added |
| AR-06 | Unsupported universality | Section 13 gives Static-vs-MCR selection rules with no crossover measurement and read like evidence-derived guidance | Medium | FIXED: labeled practitioner heuristic (stream G) |
| AR-07 | Incomplete prior-art concessions | Section 16 listed concepts conceded but not the named works; section 17 named none | Medium | FIXED: OWL-S, WSMO, SOA/BPM, Saga, Temporal, tool-retrieval literature, capability-contract and mission-bound-authorization work named, with R1.6.1 reference numbers |
| AR-08 | Loose causal verbs | "the client failed while interpreting the CREATE response"; "R1.9B demonstrates why..." (x2) | Low | FIXED ("stopped when ... lacked"; "illustrates") |
| AR-09 | Inconsistent hashes | Register entry `MCR-R1.7-P7` is a 54-character value | Medium | OPEN, documented (register erratum; source-of-record audit) |
| AR-10 | Unresolved evidence anchors | Frozen manuscript, six signed originals, R1.8 reviewer PDF package, P7 ZIP not in Git | Medium | OPEN, documented (gate report: archival, none claim-critical) |
| AR-11 | Dual hypothesis numbering (`R2-H31` vs `H31`) | Could mislead a reader comparing with the R1.8 paper | Low | FIXED (Appendix E note) |

## Checks that found nothing

| Search target | Result |
|---|---|
| Accidental CREATE-commit assertion | None; the only occurrence is a "not claimed" bullet |
| Accidental zero-write assertion | None; `prior_sap_writes: 0` is explicitly scoped to the reconciliation run |
| Autonomous recovery overstatement | None; all eight mentions are denials; the process-loss result is stated as a negative |
| Compensation overstatement | None; compensation authority FALSE, never executed |
| Transaction atomicity overstatement | None; "not established" in all three mentions |
| Provider-equivalence / failover overstatement | None; "directional", "universal ... not established" |
| Multi-ERP / cyber-physical overstatement | None; deferred / long-horizon only |
| Stale platform claims | The R1.9 body contains no vendor product statements (0 hits for the platform names); the R1.6.1 platform map is referenced as a dated snapshot only |
| Inconsistent frozen metrics | None; 5/48, 17/48, 30/48, p-values and held-out values identical across README, source-of-record note and manuscripts, and equal to the R1.6.1 PDF |
| Hypothesis inflation | No H31-H38 reaches PROVEN; H31 and H36 OBSERVED match the R1.8 closure wording ("LIVE_BOUNDED_SUPPORT_OBSERVED") |

## Residual risks (not fixable here)

1. Self-review: an external reviewer may find issues this review shares a blind spot with.
2. The MCWS result rests on a publication layer; the frozen manuscript is not in the repository.
3. The R1.9B inference "CREATE reached the provider" depends on the retained error output plus a normalized copy of the runner whose line 195 matches the quoted line.
4. Time-sensitive references are unverified.
