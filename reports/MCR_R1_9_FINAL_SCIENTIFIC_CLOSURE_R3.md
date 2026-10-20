# MCR R1.9 Final Scientific Closure R3

Supersedes R2 (retained). R3 adds the publication evidence-sufficiency gate, the adversarial review and the remediations that followed.

**MCR_R1_9 = BOUNDED_CLOSURE_WITH_UNRESOLVED_CREATE_COMMIT_STATE**

Evidence gate: `PASS_WITH_DOCUMENTED_GAPS` (`reports/MCR_R1_9_PUBLICATION_EVIDENCE_GATE_R3.md`): claim-critical evidence missing 0; archival gaps 9; new experiment required for current claims: FALSE. Recommended publication state: `RELEASE_WITH_DOCUMENTED_GAPS`. The final release state is recorded in the release notes, not asserted here.

Performed by this work: SAP writes 0, MCP business calls 0, model experiment calls 0, historical runner executions 0. Local hashing, ZIP reading and document work only.

## 1. What was MCR originally trying to prove?

That in LLM-era enterprise agents, where capability descriptions become model input, the model-visible capability set should be scoped to the current mission stage (MCWS), while authorization, provider ranking, binding and outcome truth stay deterministic and outside probabilistic control. The narrow, measurable claim was about stage-scoped exposure; the broader runtime was always presented as a practitioner architecture with historical ancestry conceded (OWL-S/WSMO/SOA/Saga/durable workflows/tool retrieval).

## 2. What does the original MCWS experiment actually prove?

In one frozen, authored benchmark (48 primary missions, 4 families, one local model): MCWS 30/48 (62.5%), Static 17/48 (35.4%), Broad 5/48 (10.4%); Holm-adjusted case-cluster p = 0.00293 (Broad-MCWS), 0.03125 (Static-MCWS), 0.2266 (Broad-Static); held-out 0/12, 2/12, 7/12 on n=4, descriptive only. It does not prove universal superiority, security, savings, transaction or outcome correctness. These values are preserved unchanged. Caveat: they are verified as reported in the R1.6.1 PDF; the frozen manuscript bytes are not available to recompute from.

## 3. What did R1.7 add?

Separately frozen bounded evidence: deterministic admission over comparators and adversarial families, a bounded live read-only enterprise POC, temporal/fault and federated-authority tests, directional provider equivalence, outcome-authoritative state, a retained negative result (no autonomous ADT process resurrection; explicit recovery required), and one bounded SAP write (P6-D1, a different object) that completed only after independent ATC observation.

## 4. What did R1.8 add?

Four local providers (ADT, Fiori, UI5, CAP; 41 contracts; 30 zero-write) under `PROVIDER::TOOL_NAME` identity, bounded live reads, point-of-use fingerprint revalidation, fail-closed contract mismatch, explicit requalification, governed continuation without automatic replay (3 missions, 8 calls, 0 writes), and the observation that version equality does not imply contract equality. Not shown: uninterrupted replication, autonomous recovery, universal equivalence or failover.

## 5. What did R1.9A add?

A deterministic, local, synthetic foundation: PrincipalContext, DelegationEnvelope, MissionExecutionEnvelope, MutationBudget, TransactionEnvelope, Execution/OutcomeReceipt, CompensationGrant, ContractLease and change classification, MissionCheckpoint, ContinuationLease; conformance tests PASS; fast path with no LLM call or mandatory remote hop. Class: SYNTHETIC/LOCAL. Not live proof of any construct.

## 6. What did R1.9B actually observe?

Under a prospectively frozen contract (TRL_EN, `ZCL_MCR19B_9533C4D8`, CLAS/OC, package ZCLINE, ADT, two authorized mutations, zero retries, no compensation or cleanup authority), a sequence of fail-closed implementation defects was exposed and preserved. The final run (HF06 attempt 2) completed initialize, session capture, `notifications/initialized`, `tools/list`, created the single-use lock, issued CREATE, received a non-empty parseable response from the ADT MCP provider, found no `filePath`, and stopped.

- CREATE reached the ADT MCP provider: TRUE (reach of the SAP back end is not established)
- ACTIVATE reached provider: FALSE
- No execution, outcome, final or authorization-consumed receipt exists
- Reconciliation: first read-only attempt could not reach the Eclipse bridge; a later bounded ADT read/validation produced no existence signal and no positive-validation signal; the retained validation response is itself an error (`isError: true`, "Unable to initialize the ADT Discovery"), so it carries no information about the object

This is a bounded partial execution that exposed ambiguous post-side-effect state. It is not a failed demo and not a success.

## 7. What remains unknown?

- Whether CREATE persisted: **UNKNOWN**. Object state inference: UNKNOWN. Authoritative repository readback: FALSE.
- Why the response lacked `filePath`: error payload vs success in another layout is undeterminable (code path never checks a JSON-RPC `error`; raw response not retained).
- Whether omitting `notifications/initialized` or the session id would have failed again (HF05 transcript not retained).

Neither "CREATE committed" nor "SAP writes = 0" may be asserted for HF06 attempt 2.

## 8. Which hypotheses are supported?

See `evidence/MCR_R1.9_FINAL_HYPOTHESIS_RESULT_MATRIX_R2.md`. OBSERVED: H31 (bounded composition), H36 (detection, revalidation, requalification). PARTIAL: H34, H35 (budget). Nothing reaches PROVEN among H31-H38.

## 9. Which claims remain synthetic?

Delegation attenuation (H33), transaction/receipt model, checkpoint/continuation (H37), governance overhead (H38), mission-relevance change classification, the no-LLM fast path.

## 10. Which claims are not established?

Gateway + MCR temporal control comparison (H32); compensation correctness; live delegated mutation; live continuation after an ambiguous side effect; end-to-end governance overhead; successful R1.9B completion; autonomous self-healing; general transaction atomicity; universal mutation safety or provider failover; multi-ERP federation; cyber-physical safety.

## 11. Why HF06 must not be replayed

The CREATE request left the client and may have committed. A rerun or reused authorization would risk a duplicate or conflicting side effect on a state nobody can read, would consume authority that was single-use by design, and would replace an honest unknown with a different experiment. The runner and authorization are frozen; the lock stands; no mutation authority exists in this work.

## 12. Is any further experiment required for R1.9 closure?

No. The bounded closure is defensible as it stands. Resolving the unknown would require authoritative read-only repository evidence (for example, a readback through a restored bridge) that already-captured data does not contain; if the owner later authorizes a read-only readback, it would refine the state to EXISTS or ABSENT without altering the rest of this record. Anything that mutates SAP is out of scope.

## 13. Recommended final scientific state

`MCR_R1_9=BOUNDED_CLOSURE_WITH_UNRESOLVED_CREATE_COMMIT_STATE`

Around a live enterprise mutation attempt, R1.9 exercised deterministic authority binding, MCP session binding, a frozen two-mutation budget, a single-use lock written before the first side effect, and a fail-closed stop with no retry. The lock's refusal of a replay was not itself exercised and the budget was not consumed to completion. The frozen mission did not reach validated completion. CREATE was invoked against the ADT MCP provider; ACTIVATE was not; authoritative post-failure repository state remained unresolved. This supports bounded control-plane behavior and does not establish complete live mutation/outcome correctness.

## 14. Recommended publication state

`RELEASE_WITH_DOCUMENTED_GAPS`. Not described as complete: the frozen manuscript and six signed originals are absent (archival, not claim-critical), references are unverified, and the claim audit and adversarial review are self-reviews awaiting independent review. Every gap is stated in the manuscript limitations, `REPRODUCIBILITY.md`, the manifests and the release notes.

## 15. What moves to future research

R1.9C (live interruption and continuation, end-to-end overhead under successful live mutation) is deferred and not initiated. Also: authoritative provider-independent readback, response normalization that preserves contract identity, separately authorized compensation, long-running delegation with revocation, multi-ERP mission portability (N1-N7 in the manuscript, Section 20).

## Corrections discovered during this work

1. The first portability commit stored line-ending-normalized evidence; 19 of 28 "exact" copies mismatched their hashes. Fixed for 13 (restored, hash-verified), 6 unrecoverable, `-text` guard added.
2. Claims narrowed: single-use replay prevention (PROVEN -> PARTIAL), session necessity (PROVEN -> OBSERVED with gap), response-cause attribution (removed), `prior_sap_writes: 0` (not HF06 accounting).
3. MCWS expansion aligned to the source of record ("Minimum Capability Working Set").
4. Malformed register hash (`MCR-R1.7-P7`) flagged, not repaired.
5. Adversarial pass (R3) corrected: causal/integrity caveats on the MCWS result (unresolved mechanism, M003 regrading), provider-reach precision (ADT MCP provider vs SAP back end), "demonstrated" replay/budget wording, absence-of-signal read as absence, unretained chronology stated as established, unlabeled practitioner heuristic, and unnamed prior art.

## Remaining optional follow-up

1. Supply the frozen manuscript and the six signed originals from the original workstation, if they exist; import with hash verification.
2. Recover or remove the `MCR-R1.7-P7` register entry.
3. Commission an independent external claim review and fresh verification of time-sensitive references.
4. If ever authorized, an authoritative read-only repository readback of the R1.9B object would refine the commit state.
