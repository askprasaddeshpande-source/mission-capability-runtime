# MCR R2.0 Research Summary R1: Validated Enterprise Outcome Runtime

Status: DRAFT for the consolidated R2.0 pull request. Date: 2026-10-20. This summary states only what the evidence in this repository supports. It is an independent practitioner research record, not a peer-reviewed result, and no hypothesis is PROVEN.

## Question
Can an enterprise-agent runtime prove that an authorized mission caused the intended enterprise state transition, and keep "the tool returned" distinct from "the state was committed" and from "the intended outcome holds"? REQUESTED, AUTHORIZED, BOUND, EXECUTED, COMMITTED, AUTHORITATIVELY OBSERVED, OUTCOME VALIDATED and COMPLETE are modelled as separate states, each entered only through a guard that demands its own evidence object.

## What was built
- A deterministic model (`tools/r2.0/mcr_r2_model.py`): a 20-state machine, 25 hash-addressed object kinds (JSON Schemas in `architecture/r2.0/schemas/`), tri-state outcome predicates, a replay guard consumed before the call is sent, continuation leases, separate compensation grants, and a 14-link evidence chain validated relationally before COMPLETE.
- A read-only qualification probe and a frozen, single-use live study runner (`tools/r2.0/r2_0b_*.py`, `r2_0c_study.py`).
- Tests and tooling: 486-check validator, 607 generated mutants (guards, the 50 chain relations, clause-level operators and targeted ones; 298 detected by an assertion, 302 because the validator's own fixtures could no longer run, 1 because the mutant makes the validator hang, 6 survivors each justified as an equivalent mutant), local crash/compensation scenarios, a fresh-clone verifier that pins 82 historical files, checks reviewed-revision pins, supports an external sums anchor and was itself attacked in 25 archived scenarios (6 more written, not yet run, because the machine ran short of memory).

## What was observed live (one run, OBSERVED, not proven)
- A read-only probe of the ADT MCP provider on TRL_EN (0 writes): the provider contract had drifted from 20 to 29 tools since R1.8; a CDS (DDLS) readback tool distinguished an existing object (HTTP 200, source hash recomputed locally equal) from absent names (HTTP 404, resource-not-found); the same tool returned a wrong-endpoint 404 for an existing class, so a 404 is only meaningful from the endpoint that serves that object type.
- One owner-authorized mutation: a single `abap_creation-create_object` for a fresh CDS data definition (`ZC_MCR20C_7A3F91D2`, package ZCLINE, TRL_EN). Baseline readback ABSENT, provider success message, post-write readback EXISTS from the DDLS endpoint, four frozen predicates passed, mission state COMPLETE. The run emitted 13 of the 14 specified chain links; the completion receipt was not persisted by the model at the time (erratum filed, model repaired, not re-observed live).

## What this does and does not show
Shows: in this one case the runtime could separate the provider's success message from an independently read commit state and tie both to one transaction by identifiers and hashes, and the model rejects the failure patterns it was tested against (offline).
Does not show: activation state (both version reads returned the same payload), package membership, atomicity, behaviour under real failure or interruption, live compensation, drift between prewrite and call, or any generalization beyond one object on one provider. The readback source is the owner's ADT session read tool; "authoritative" is the runner's own label for it and no second independent source was used. The model verifies the consistency of presented evidence, not who produced it (no signatures; an owner decision, recorded as an accepted gap).

## Independent review
Five independent, read-only reviews were commissioned. Reviews 1 to 4 returned HOLD, each finding smaller defects than the last; review 5 returned PASS_WITH_GAPS / GO_WITH_DOCUMENTED_GAPS. Review 1 (`8a383b6`): forged-lease resume, non-atomic guards, absent relational chain checks, vacuous predicates, weak verifier. Review 2 (`b5cca1f`): send-time gates that did not verify evidence, stale-lease replay, ungated terminal states, 46 surviving mutants. Review 3 (`a381a22`): `resume()` skipping the gate checks, two processes sharing the replay ledger both sending, compensation completing with no compensating action, scanner and mutation-granularity gaps. Review 4 (`f6e79a4`): no thread safety on one Mission object, unchecked `scope` types, weak compensation goal checks, undisclosed ledger deletion, scanner evasions and four test gaps; all addressed in R2.0L. Review 5 (`681f77a`): a thread-unsafe in-memory ledger, unvalidated ledger paths, overstated compensation wording, a readback contract not tied to the bound provider, mutation-report wording and scanner false negatives; all addressed offline in R2.0M (`reports/r2.0/MCR_R2_0_M_HARDENING_REPORT_R1.md`). The R2.0M commit has not been re-reviewed.

## Hypotheses (see `evidence/r2.0/MCR_R2_0_HYPOTHESIS_STATUS_R8.md`)
H41 and H42 OBSERVED (scoped to one object, one run); H43, H46, H47, H48 PARTIAL; H44, H45 SYNTHETIC. None PROVEN.

## Next required proof
A second frozen live study (fresh owner authorization) that: binds the model hash into the authorization; proves per-version readback on an object with a pending inactive version; requires ABSENT to name the requested object; adds an independent second readback source or renames the authority level; emits and persists the completion receipt (link 14); and exercises at least one non-success branch live.

## Constraints on use
Do not describe R2.0 as a validated enterprise runtime, as qualified for SAP generally, or as proof of end-to-end correctness. The supportable statement is: a bounded proof of concept with one scoped live observation and an offline-tested evidence model, with the gaps listed above.
