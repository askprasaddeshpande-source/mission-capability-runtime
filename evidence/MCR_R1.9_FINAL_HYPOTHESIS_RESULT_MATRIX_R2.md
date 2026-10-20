# MCR R1.9 Final Hypothesis Result Matrix R2

States used: PROVEN, OBSERVED, PARTIAL, SYNTHETIC, NOT_ESTABLISHED, DEFERRED. No binary PASS/FAIL is forced.

Naming note: the R1.8 companion paper numbers these as `R2-H31 ... R2-H38`; the R1.9A register carries H33-H38 with its own wording. This matrix follows the R1.9A wording for H33-H38 and the R1.8 wording for H31, H32 and H36, and states where they differ.

| H | Hypothesis | Final state | Decisive evidence | What is NOT shown |
|---|---|---|---|---|
| H31 | Multi-MCP mission-scoped composition | **OBSERVED** (bounded) | C1D: one mission composed 4 heterogeneous providers, 4/4 valid outcomes, 0 writes. C2C: 3 missions, 8 calls, governed recovery and continuation | Comparative reduction of invalid exposure vs host-wide exposure (R2-H31 as stated was prospective, not tested); uninterrupted multi-mission replication (`NOT_OBSERVED_IN_C2`) |
| H32 | Gateway + MCR temporal mission control reduces stale/revoked/duplicate executor reach without excess false denial | **NOT_ESTABLISHED** | R1.8: R2-H32 "remains prospective and receives no empirical promotion". R1.7 P7 offline/bounded temporal tests show zero executor reach for stale/revoked/drift cases, but with no gateway-plus-MCR vs gateway-only comparison | Any controlled gateway-only vs gateway+MCR comparison. Architectural fit with gateways is design reasoning, not evidence |
| H33 | User -> Agent -> Mission delegated authority is an intersection and cannot amplify | **SYNTHETIC** | R1.9A delegation adversarial results and attenuation tests (PASS); C2C `R2_H33_SUPPORT=SYNTHETIC_CONFORMANCE_ONLY`, `C2_UPGRADE=false` | A live multi-hop delegated mutation chain; R1.9B did not upgrade this |
| H34 | Explicit transaction/outcome semantics give stronger completion guarantees than treating tool receipts as completion | **PARTIAL** | Receipt schemas and conformance (synthetic). P6-D1 (historical, other object): initial ATC timeout, no replay, completion only after independent ATC observation. R1.9B: provider reach, commit and completion visibly diverge | A comparison against a receipt-as-completion baseline ("stronger guarantees" is comparative); an R1.9B run that produced receipts and an outcome receipt (none were written) |
| H35 | Mutation budgets constrain state change; compensation needs separately authorized authority | **PARTIAL**: budget. **NOT_ESTABLISHED**: compensation | Budget: frozen 2-mutation budget (R1.9B); P6-D1 consumed exactly 2/2 with 0 unauthorized; R1.9A budget-exhaustion tests. Compensation: separation tested synthetically only | Live budget exhaustion in R1.9B (at most the first request was issued); any compensation execution or correctness |
| H36 | Contract evolution can be detected, classified by mission relevance and governed through requalification | **OBSERVED** (detection, point-of-use revalidation, fail-closed, requalification). **SYNTHETIC** (mission-relevance change classification) | C1D: 4/4 contracts fingerprint-revalidated before live calls. C2C: Fiori drift vs C1 freeze caught, failed closed, requalified, continued. `VERSION_EQUALITY_DOES_NOT_IMPLY_CONTRACT_EQUALITY=OBSERVED`. R1.9A classification policy tests (synthetic) | Raw historical C2B Fiori contract (not captured; earlier-drift attribution unproven); live mission-relevant partial-drift acceptance; universal drift detection |
| H37 | A mission resumes from validated checkpoint without replay when identity, authority, contracts and budget are revalidated | **SYNTHETIC**; live **NOT_ESTABLISHED** | R1.9A checkpoint integrity and continuation-exclusion tests (PASS). R1.8 governed continuation after requalification is adjacent evidence, not checkpoint/lease evidence | Live interruption and continuation after a confirmed or ambiguous side effect. Deferred to R1.9C, which is not initiated |
| H38 | Governance enforces controls with bounded incremental overhead | **SYNTHETIC** (local microbenchmark only) | R1.9A: 5,000 iterations, ~0.28 ms simulated governed admission vs ~0.0012 ms simulated direct dispatch; 0 network, MCP, business, model calls | Overhead under real provider latency or a successful live mutation; a latency distribution (p50=p95=p99 identical, i.e., one aggregate value) |

## Summary

- OBSERVED: H31 (bounded), H36 (detection/revalidation/requalification)
- PARTIAL: H34, H35 (budget)
- SYNTHETIC: H33, H37, H38, H36 (classification only)
- NOT_ESTABLISHED: H32, H35 (compensation)
- PROVEN: none of H31-H38 reaches PROVEN under the R1.9 evidence
- DEFERRED: live parts of H37, H38, and live delegation under H33 (R1.9C, not initiated)

## Effect of the R1.9B live attempt on the matrix

R1.9B changed no hypothesis state upward. It supports the *need* for the H34 distinction and the H35 budget/replay design, and it exposed that H37-style continuation would have to operate from an unknown, not a known, commit state. The `UNKNOWN` is retained; it is not converted into support or into refutation.
