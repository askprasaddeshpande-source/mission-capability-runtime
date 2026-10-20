# MCR R1.9 Repository Consistency Audit R3

Supersedes R2 (retained). Re-run after the R3 manuscript, audits, PDF, tooling and documentation updates; the R2 findings table is carried forward with current status.

Scope: README, paper/, architecture/, evidence/, reports/, research-package/, REPRODUCIBILITY.md, PORTABILITY.md, FROZEN_EVIDENCE_ANCHORS.json, PUBLICATION_MANIFEST.json, SHA256SUMS.txt, CITATION.cff, LICENSE_POLICY.md, publication/.

Method: programmatic hash comparison (anchors vs recomputed bytes, register vs anchors, SHA256SUMS vs files), text sweeps for contradiction patterns, and manual reading.

## Result

**REPOSITORY_CONSISTENCY=PASS_WITH_GAPS**

Mechanical confirmation: `python tools/verify_fresh_clone.py` returns no FAIL (`OVERALL=PASS_WITH_DOCUMENTED_GAPS`).

All contradictions about the scientific state were resolved or confirmed absent. Remaining gaps are evidence-availability gaps, not inconsistencies in what is claimed.

## Contradiction checks

| Check | Result |
|---|---|
| CREATE "committed" vs UNKNOWN | PASS. Every occurrence in tracked prose is a negation or "may have"; no file asserts CREATE committed or did not commit |
| `SAP_WRITES=0` asserted for HF06 attempt 2 | PASS. Appears nowhere as a claim. The adjudication file's `prior_sap_writes: 0` is reconciliation-run accounting and is explicitly annotated in the manuscript and audits |
| Autonomous self-healing | PASS. All occurrences are denials (matrix, checklist, manuscript, closure report) |
| "R1.9 complete" vs bounded closure | PASS. "Complete and frozen" refers to R1.9A only; R1.9 closure is stated as `BOUNDED_CLOSURE_WITH_UNRESOLVED_CREATE_COMMIT_STATE` |
| MCWS metrics (5/48, 17/48, 30/48; p-values; held-out) | PASS. Identical in README, source-of-record note, closure draft, R2 manuscript, and the R1.6.1 PDF; arithmetic verified |
| Provider counts | PASS. 41 contracts / 30 zero-write (23 READ + 7 ANALYSIS) / ADT 20, Fiori 9, UI5 10, CAP 2 consistent with the C1D closure |
| Frozen hashes | PASS with one defect. All 64-hex register hashes equal anchor hashes (and vice versa); see F5 |
| Invented DOI / release metadata | PASS. `github_release`, Zenodo DOIs null; CITATION.cff has no DOI or release date |
| GitHub path | PASS. `askprasaddeshpande-source/mission-capability-runtime` throughout |
| Frozen anchors vs bytes | PASS for the 10 anchors with bytes in Git (recomputed equal); 5 anchors have no bytes (documented) |

## Findings

| ID | Finding | Severity | Status |
|---|---|---|---|
| F1 | MCWS expanded inconsistently: R1.6.1 source of record says **Minimum** Capability Working Set; README, architecture doc and closure draft said "Mission-Capability Working Set" | Medium | FIXED in README, architecture, R2 manuscript. Earlier closure draft R1 retained unchanged as history |
| F2 | R1 portability commit stored line-ending-normalized evidence; 19 of 28 "exact" copies did not match their recorded hashes (`HASH_MISMATCH=0` was wrong) | High | FIXED for 13 files (restored, hash-verified) with `-text` guard; 6 unrecoverable (documented). R1 records retained |
| F3 | `PORTABILITY.md` had corrupted paths (`vidence/portable/...`) | Low | FIXED (rewritten for R2) |
| F4 | `SHA256SUMS.txt` stale for `.gitattributes`, R1 portability manifest/summary, `PORTABILITY.md` and six scripts | Medium | FIXED (regenerated for all tracked files) |
| F5 | Register entry `MCR-R1.7-P7` has a 54-character (invalid) hash; not in anchors; no bytes | Medium | OPEN (documented). Erratum appended to the register; classified archival (the underlying negative result is anchored elsewhere) |
| F6 | R1 claim matrix rows C11, C12, C13, C14 overstate (see audit R2: C11 PARTIAL, C13 OBSERVED/indirect, C14 PARTIAL). `PROVEN` for replay prevention rests on a lock's existence, not a tested refusal | Medium | NARROWED in claim audit R2; erratum appended to R1 matrix (R1 table unchanged) |
| F7 | Closure draft R1 said a provider "can execute CREATE while the client fails to interpret the response" and attributed the stop to "response-shape handling". Retained evidence cannot distinguish an error payload from an alternate success layout | Medium | FIXED in R2 manuscript (C20 NOT_ESTABLISHED) |
| F8 | Closure draft R1 said "four distinct evidence classes" above a five-row table | Low | FIXED in R2 |
| F9 | `PUBLICATION_MANIFEST.json`, `CITATION.cff`, README, REPRODUCIBILITY still said "DRAFT / CLOSURE WORKSPACE" and version `1.9.0-draft-r1` | Low | FIXED (R3: version `1.9.0` in manifest and CITATION.cff; validator checks they agree; no DOI recorded) |
| F10 | R1.7 matrix lists "SAP write safety" and "P6-D completed" as NOT CLAIMED, while P6-D1 later passed | Info | Not a conflict: sequential records; R2 manuscript labels P6-D1 as a separate bounded result and not general write safety |
| F11 | R1.9A microbenchmark reports identical p50/p95/p99 | Low | Disclosed in manuscript, hypothesis matrix (H38) and claim C25 |
| F12 | `paper/README.md` public-release rule says R1.9 must not be described as closed until the classification is frozen | Info | Consistent: classification is selected; owner freeze pending |
| F13 | Expected local path `D:\MCP\research-paper\mission-capability-runtime` did not exist on this machine | Info | Environmental; work performed in a fresh clone at `D:\MCR\mission-capability-runtime` |
| F14 | The six scripts' `SHA256SUMS` entries (R1) record the frozen original hashes while the stored bytes differ | Medium | Documented in manifest R2 (`HASH_MISMATCH`, cause = normalization); SHA256SUMS now describes the stored bytes |

## R3 additions

| ID | Finding | Severity | Status |
|---|---|---|---|
| F15 | R2 manuscript stronger than its own claim audit on replay/budget ("demonstrated"), and silent on MCWS causal limits, provider-vs-back-end reach, reconciliation error content | High | FIXED in manuscript R3; see `reports/MCR_R1_9_EXTERNAL_ADVERSARIAL_REVIEW_R3.md` AR-01 to AR-08 |
| F16 | Claim audit R2 stated "provider" reach without the back-end qualification; 3 claims added, 3 narrowed in R3 (33 claims) | Medium | FIXED |
| F17 | Inclusion plan R2 left 10 items as NEEDS_OWNER_REVIEW | Low | FIXED: decided in R3 plan (content reviewed) |
| F18 | Closure report R2 recommended `EXTERNAL_REVIEW_CANDIDATE_READY_WITH_GAPS` and later release state would have contradicted it | Low | FIXED: closure R3 and manifest use `RELEASE_WITH_DOCUMENTED_GAPS`; the release state is recorded in release notes |
| F19 | Version-label consistency | Info | PASS: manifest, CITATION.cff and README agree on 1.9.0; R1/R2 candidate files retain their own labels as history |
| F20 | Hypothesis numbering (`H31` vs `R2-H31`) | Low | FIXED (manuscript Appendix E note) |

## Residual gaps (not inconsistencies)

- Frozen scientific manuscript bytes absent; six signed originals absent; R1.8 reviewer PDF package and P7 closure ZIP absent.
- HF06 raw CREATE response, HF01-HF05 chronology and HF05 transcript not retained.
- 41 of 48 references are time-sensitive or emerging and unverified.
- Claim audit, adversarial review and consistency audit are self-reviews.
- PDF visually checked on 3 of 23 pages.

PASS_WITH_GAPS is the correct verdict: nothing in the repository now contradicts the evidence, but the evidence set is not complete.
