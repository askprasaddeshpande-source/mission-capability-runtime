# From Tools to Missions: A Mission-Capability Runtime for Enterprise AI

## Credible Lineage, Measurable Post-LLM Capability Scoping, Governed Runtime Evidence, and a Bounded Live-Mutation Closure

**Prasad Deshpande**  
Independent Researcher — Agentic AI Systems and Enterprise Architecture  
ORCID: 0009-0008-1344-6585  
Email: er.prasad.deshpande@gmail.com  
Research & Architecture: https://prasaddeshpande.com/

**MCR R1.9 Closure Draft R1 — 20 October 2026**

*Publication-layer provenance.* This draft extends the original adversarially hardened MCR R1.6.1 whitepaper without changing the frozen MCWS experiment. The original scientific manuscript is anchored by SHA-256 `E589393C6EEA0BA92E4EC521D1577A6F561F9ADFA38FF9EEE97A94695C666D90`. R1.7, R1.8 and R1.9 contribute separately frozen runtime and enterprise-engineering evidence. No historical failure is rewritten as success. In particular, the R1.9B live SAP mutation study did not reach validated completion: CREATE reached the provider, ACTIVATE did not, and the authoritative repository state after CREATE remains unresolved at this draft.

---

## Abstract

Goal-driven service discovery, semantic capability descriptions, durable workflow state, compensation and dynamic provider binding have substantial ancestry in Semantic Web Services, SOA/BPM and durable-workflow systems. LLM-era tool-retrieval work likewise predates MCR and already recognizes the model-visible tool set as part of the reasoning surface. The narrower problem addressed by the Mission-Capability Runtime (MCR) is how an enterprise runtime can make executable capability exposure mission-stage-specific while keeping authorization, final provider ranking, mutation authority and binding outside probabilistic model control.

The frozen MCWS scientific result from R1.6.1 is unchanged: MCWS achieved 30/48 primary mission successes (62.5%), Static 17/48 (35.4%) and Broad 5/48 (10.4%). Holm-adjusted case-cluster tests were `p = 0.00293` for Broad–MCWS, `p = 0.03125` for Static–MCWS and `p = 0.2266` for Broad–Static. These results evaluate capability-exposure behavior in the frozen benchmark; they do not establish general enterprise safety, universal orchestration superiority, production cost savings or transaction correctness.

R1.7 and R1.8 then moved the research program from architecture synthesis toward bounded runtime evidence. They exercised deterministic authority boundaries, provider contracts, multi-provider capability surfaces, point-of-use contract revalidation, mission-scoped capability identities, fail-closed drift detection and bounded multi-mission execution. R1.9A formalized governed execution using PrincipalContext, DelegationEnvelope, MissionExecutionEnvelope, MutationBudget, TransactionEnvelope, ExecutionReceipt, OutcomeReceipt, CompensationGrant, ContractLease, MissionCheckpoint and ContinuationLease, while keeping the authorization fast path deterministic and off the LLM critical path.

R1.9B prospectively froze one live SAP mutation mission: target `TRL_EN`, object `ZCL_MCR19B_9533C4D8`, package `ZCLINE`, provider ADT, exactly two authorized mutations (CREATE and ACTIVATE), two outcome-validation operations, zero retries and no compensation or cleanup authority. Successive fail-closed iterations exposed real implementation defects in authorization binding, state-root handling, evidence persistence and MCP session semantics. The final qualified HF06 runner reached the CREATE provider call but stopped on `CREATE_FILEPATH_MISSING` before ACTIVATE. A single-use lock prevents replay. Subsequent read-only/validation-only reconciliation could not establish whether CREATE persisted in SAP, so `CREATE_COMMIT_STATE=UNKNOWN` remains the bounded closure state.

The R1.9 result is therefore deliberately partial. It supports deterministic control-plane properties such as source-bound authorization, session-aware MCP execution, single-use replay blocking, mutation-budget enforcement and fail-closed behavior. It does **not** establish successful end-to-end live mutation, successful activation, authoritative outcome completion, autonomous self-healing, general transaction atomicity or production enterprise safety. The negative/partial result strengthens rather than weakens the central runtime distinction: **tool invocation, mutation commit, execution receipt and authoritative outcome are different states.**

**Keywords:** agentic AI; enterprise agents; Mission-Capability Runtime; Mission-Capability Working Set; MCP; tool retrieval; capability scoping; deterministic authority; mutation budgets; execution receipts; outcome validation; SAP; enterprise architecture

---

# 1 Executive summary

The original MCR whitepaper argued for a narrow layer above provider protocols and enterprise gateways: durable mission state should produce a current capability requirement; only a bounded stage working set should become model-visible; the LLM may propose semantic intent; deterministic runtime logic must own admissibility, provider ranking, binding integrity and execution authority; and authoritative enterprise observation should determine whether the mission actually progressed.

R1.9 preserves that thesis but changes the evidence balance. The program now contains four distinct evidence classes:

| Contribution level | R1.9 position | Evidence class | Explicit boundary |
|---|---|---|---|
| Scientific | Stage-scoped MCWS Broad/Static/MCWS benchmark | Frozen experiment | Does not establish universal MCR superiority or production safety |
| Engineering | SAP/MCP/Capella/BAS plus R1.7/R1.8 provider/runtime proofs | Separate frozen POCs | Components were exercised separately; not one monolithic production runtime |
| Runtime-control research | R1.9A deterministic governed-execution foundation; R1.9B bounded live mutation attempt | Synthetic/local + bounded live evidence | Full mutation-to-authoritative-outcome completion not established |
| Architecture synthesis | Mission -> MCWS -> deterministic admissibility/binding -> execution -> authoritative outcome | Practitioner pattern | Components have prior-art ancestry; combination and control discipline are the contribution |
| Long-horizon agenda | portable missions, trust federation, economics, cyber-physical execution | Hypothesis / scenario | Prerequisite-conditioned and non-empirical |

The practical MCR rule remains:

> **The LLM proposes semantics; the runtime binds authority.**

The R1.9 outcome rule becomes equally important:

> **REQUESTED != AUTHORIZED != BOUND != EXECUTED != COMMITTED != VALIDATED_COMPLETE**

A runtime that collapses those states cannot safely reason about partial failure.

## 1.1 Decision rule

Prefer a static/compiled execution path where provider identity, mission requirements and authority are stable. Introduce MCR where one or more of the following are material:

- provider substitution or failover;
- changing mission requirements;
- heterogeneous capability surfaces;
- delegated authority;
- long-running state;
- consequential mutations;
- contract/schema drift;
- point-of-use policy changes; or
- authoritative outcome verification.

## 1.2 Claim boundary

R1.9 is not a claim that MCR has become a production transaction coordinator. It is a bounded research program that progressively tests the control structures required before such a claim could be credible.

---

# 2 What we have already built: engineering proof at a glance

The evidence program remains split into independent streams.

## 2.1 Original scientific stream

The frozen Broad/Static/MCWS benchmark remains unchanged.

Corrected primary mission success:

| Architecture | Success | Rate |
|---|---:|---:|
| Broad | 5/48 | 10.4% |
| Static | 17/48 | 35.4% |
| MCWS | 30/48 | 62.5% |

The result supports bounded stage-scoped capability exposure in the evaluated benchmark. It does not independently establish attack-surface reduction, monetary savings, zero-trust isolation or general security.

## 2.2 R1.7 governed-runtime stream

R1.7 added bounded live runtime evidence:

- read-only provider binding and dry-run paths;
- bounded live SAP reads;
- actual provider-loss fail-closed behavior;
- explicit evidence that autonomous ADT resurrection was **not observed**;
- federated authority distinctions;
- outcome-authoritative state handling; and
- one bounded SAP write experiment with exactly authorized CREATE + ACTIVATE and no extra writes.

The surviving invariants include:

- `DISCOVERABLE != AUTHORIZED`
- `TRUSTED_TO_DESCRIBE != AUTHORIZED_TO_EXECUTE`
- delegated authority cannot amplify;
- provider equivalence is directional rather than universal;
- `EXECUTED != COMPLETE`.

## 2.3 R1.8 multi-provider / multi-mission stream

R1.8 qualified a four-provider local capability set across ADT, Fiori, UI5 and CAP and formalized provider-qualified capability identities using:

`PROVIDER::TOOL_NAME`

The local qualified set contained 41 tool contracts, with 30 classified as zero-write READ/ANALYSIS capabilities and the remainder separated into local or enterprise mutation classes.

R1.8 live work demonstrated:

- one read-only call per provider in the C1 bounded qualification;
- mission-aware capability identities;
- fail-closed contract mismatch detection;
- Fiori contract drift despite unchanged nominal package/server version;
- explicit requalification before continuation;
- bounded multi-mission continuation after governed repair; and
- no automatic replay of failed business calls.

The observed Fiori drift supports a central contract lesson:

> **VERSION_EQUALITY_DOES_NOT_IMPLY_CONTRACT_EQUALITY**

## 2.4 R1.9A governed-execution foundation

R1.9A is complete and frozen.

It defines:

- `PrincipalContext`
- `DelegationEnvelope`
- `MissionExecutionEnvelope`
- `MutationBudget`
- `TransactionEnvelope`
- `ExecutionReceipt`
- `OutcomeReceipt`
- `CompensationGrant`
- `ContractLease`
- mission-relevant contract hash/change classification
- `MissionCheckpoint`
- `ContinuationLease`

The deterministic fast path is designed so that:

- LLM authorization calls are not required;
- a remote governance network hop is not mandatory per invocation;
- authority amplification is refused;
- unauthorized compensation is refused;
- point-of-use checks remain deterministic.

---

# 3 Independent-review alignment: what changed

The original adversarial review narrowed three important areas:

1. provider abstraction belongs to the deterministic MCR binding layer, not MCWS;
2. the MCWS benchmark measures selection/task-success behavior, not end-to-end security; and
3. composite substitution under Saga-style compensation remained incompletely specified.

R1.7–R1.9 do not reverse those concessions.

Instead, the program tests the runtime boundary directly and exposes new failure classes:

- authorization artifact can be semantically correct but bound to the wrong signed source;
- a runner may qualify local request construction yet fail on the real authorization path;
- evidence persistence code can fail after a real mutation unless pre-mutation replay controls exist;
- MCP initialize success does not imply subsequent requests are valid unless session semantics are preserved;
- localized DateTime conversion can invalidate otherwise correct signed authority;
- a provider can execute CREATE while the client fails to interpret the response contract;
- after that boundary, replay is unsafe because the side effect may already have committed.

These are not paper-cleanup details. They are exactly the runtime states a mission system must distinguish.

---

# 4 Where the runtime fits

## 4.1 Protocol, control plane and mission runtime are different layers

MCR does not replace:

- MCP;
- A2A;
- API gateways;
- registries;
- OAuth/workload identity;
- enterprise authorization;
- SAP business authorization;
- observability; or
- systems of record.

It consumes those layers.

A useful separation is:

`Mission semantics -> MCR -> enterprise control plane -> protocol adapters -> systems of record`

## 4.2 Mission state, not provider identity

The core indirection remains:

`Mission -> Capability -> Provider -> Tool`

The mission should remain stable when a provider changes, but provider change is not automatically safe. Substitutability must be directional, stage-relative, policy-compatible and authority-preserving.

## 4.3 Relationship to ACLA and EAF

The broader research program separates three questions:

- **ACLA:** what should the model know?
- **EAF:** is the action sufficiently supported and authorized, and was the outcome validated?
- **MCR:** which capability/provider/tool should execute the authorized mission under deterministic runtime constraints?

MCR consumes context and authority; it should not silently become the owner of all context lifecycle or all enterprise assurance.

---

# 5 The measurable post-LLM problem: capability catalogs become reasoning input

The original post-LLM observation remains unchanged.

Classical registries are external deterministic data structures until queried. In LLM systems, tool/capability descriptions can be serialized directly into the active model context. A broader executable catalog can therefore alter:

- prompt length;
- semantic collisions;
- model tool selection;
- exposure to malicious descriptions;
- audit clarity; and
- reasoning ambiguity.

MCWS addresses the model-visible capability surface.

MCR addresses deterministic admissibility and execution after the model proposes semantic intent.

The two mechanisms must not be conflated.

---

# 6 Practical implementation profile

## 6.1 Effective execution authority

R1.8/R1.9 formalize effective authority as an intersection rather than an inherited model privilege:

`EffectiveExecutionAuthority = ProviderAuthority ∩ UserAuthority ∩ AgentAuthority ∩ MissionAuthority ∩ TemporalAuthority ∩ CapabilityAuthority ∩ TargetAuthority ∩ TransactionAuthority`

Any empty term blocks execution.

## 6.2 Mission-Capability Working Set

MCWS is the model-visible capability projection for the active mission stage.

Its job is to bound the reasoning surface. It is not final permission.

## 6.3 Deterministic binding

A model proposal is an untrusted semantic candidate.

Before execution, MCR should revalidate at least:

- mission stage;
- capability class;
- provider identity;
- contract fingerprint;
- target;
- parameter digest;
- authority chain;
- transaction state;
- mutation budget;
- temporal validity; and
- current policy.

## 6.4 Runtime records

The research lineage uses runtime records rather than proposing a new industry standard.

R1.9 operational objects include:

- MissionExecutionEnvelope
- Runtime Binding Record or equivalent binding receipt
- MutationBudget
- TransactionEnvelope
- ExecutionReceipt
- OutcomeReceipt
- ContractLease
- MissionCheckpoint / ContinuationLease
- CompensationGrant

The important property is explicit state, not the exact serialization vocabulary.

## 6.5 Contract leases and drift

A nominal version string is insufficient.

MCR maintains:

- full provider contract identity; and
- mission-relevant contract identity.

Point-of-use drift may therefore invalidate only the affected mission path rather than globally declaring a provider unusable.

## 6.6 Outcome verification

For consequential operations:

`tool returned success != enterprise outcome validated`

An execution receipt records invocation/execution evidence.

An outcome receipt requires authoritative observation against the intended state/delta.

---

# 7 SAP S/4HANA worked example and R1.9B live study

The original R1.6.1 paper used SAP as a worked enterprise example while keeping that example separate from the frozen MCWS benchmark.

R1.9B moves one narrow SAP mutation into live bounded research.

## 7.1 Frozen live mission

The prospective live contract fixed:

- Target: `TRL_EN`
- Object: `ZCL_MCR19B_9533C4D8`
- Package: `ZCLINE`
- Provider: ADT
- Mutation budget: exactly `2`
- Mutation 1: `abap_creation-create_object`
- Mutation 2: `abap_activate_objects`
- Validation 1: `abap_atc_run`
- Validation 2: `abap_atc_get_result`
- Automatic retries: `0`
- Compensation authority: `FALSE`
- Cleanup/delete authority: `FALSE`
- Substitution: `FALSE`

The object, target, package, provider and budget were not allowed to change to rescue the study.

## 7.2 Qualification chronology

The live runner lineage intentionally preserves failed attempts as evidence.

Historical defects included:

- initial artifact/source-map mismatch;
- auth-context property mismatch;
- qualification guard blocking live execution;
- undefined StateRoot;
- stale historical authorization binding;
- undefined evidence writer;
- missing pre-mutation single-use lock;
- missing MCP session ID propagation;
- missing `notifications/initialized`;
- launcher-only DateTimeOffset parsing defect.

No failed historical runner is reusable.

## 7.3 HF06 qualified state

HF06 became the first runner to pass the full pre-write control set:

- source/signature binding;
- unchanged authorization validator;
- frozen scientific contract;
- HF06-only authorization path;
- session ID capture/propagation;
- `notifications/initialized`;
- tools/list before mutation lock;
- single-use lock before CREATE;
- signed mock E2E;
- pre-provider construction checks;
- exact signed session-protocol qualification.

Frozen HF06 source:

`DE183ABC47B8F025ED60CFE5CFEA4527585FB20154C949628BDE95E42A0D3C88`

## 7.4 HF06 live attempt 2

The final live attempt reached:

`CREATE -> response -> filePath extraction -> CREATE_FILEPATH_MISSING -> STOP`

Observed:

- CREATE provider call reached;
- ACTIVATE provider call did not reach;
- one single-use lock persisted;
- no CREATE execution receipt was written;
- no ACTIVATE execution receipt was written;
- no outcome receipt was written;
- no final receipt was written;
- authorization-consumed receipt was not written;
- automatic retry remained zero.

The single-use lock prevents replay of the same authority.

## 7.5 Unresolved commit state

The central unresolved question is whether the CREATE side effect committed before client-side response interpretation failed.

A direct authoritative repository readback was attempted through a previously used Eclipse bridge, but the bridge was unavailable.

A secondary creation-preflight reconciliation used bounded read/validation MCP operations and captured responses, but local adjudication did not yield a reliable existence-collision signal or reliable positive-validation signal.

Current state:

`CREATE_COMMIT_STATE=UNKNOWN`

`OBJECT_STATE_INFERENCE=UNKNOWN`

`AUTHORITATIVE_REPOSITORY_READBACK=FALSE`

This state must not be rewritten as either success or absence without stronger evidence.

---

# 8 Adoption roadmap: from broad exposure to governed mission execution

The original incremental roadmap remains useful, with R1.9 evidence added:

1. **Broad exposure** — inventory tools and establish baseline.
2. **Governed catalog** — registry/gateway/identity/policy.
3. **Capability normalization** — provider-neutral capability IDs.
4. **Stage MCWS** — expose only current mission capability set.
5. **Runtime recomposition** — directional provider qualification and point-of-use revalidation.
6. **Consequential execution** — delegated authority, mutation budgets, transaction state and replay protection.
7. **Authoritative outcome** — independent readback and outcome receipt.

R1.9B demonstrates why stages 6 and 7 cannot be collapsed.

---

# 9 Identity and policy: how much control is enough?

MCR treats business authorization as external authoritative input, not a model inference.

Relevant runtime principles:

- discoverability does not grant authority;
- trusted capability descriptions do not grant execution authority;
- delegated authority cannot exceed parent authority;
- stale authority must fail closed;
- mutation budgets are explicit;
- compensation authority is separate;
- authorization must bind exact mission/source/target semantics; and
- point-of-use revalidation is required where material state can change.

---

# 10 Engineering failure modes observed in practice

The MCR program now contains an unusually useful failure register.

| Failure class | Observed form | Runtime lesson |
|---|---|---|
| Provider loss | ADT process loss in earlier bounded study | Current provider health is mission state; autonomous self-healing was not observed |
| Contract drift | Fiori normalized contract changed under nominally unchanged package/server version | Version equality does not prove contract equality |
| Authorization binding | Correct authorization data pointed at stale runner identity | Authority must bind exact executable source |
| Evidence persistence | Undefined evidence writer discovered in live-path audit | Post-mutation evidence failure must not permit replay |
| Single-use semantics | Missing pre-mutation lock in HF04 | Acquire replay barrier before first side effect |
| MCP session semantics | initialize succeeded but later request lacked session ID | Protocol session state is part of execution state |
| Initialization lifecycle | `notifications/initialized` omitted | MCP lifecycle sequence must be explicit |
| Time parsing | ISO expiry converted through localized DateTime string | Authority time must use unambiguous round-trip representation |
| Response contract mismatch | CREATE returned but expected filePath could not be extracted | Provider success and client interpretation are different states |
| Outcome uncertainty | CREATE may have committed; ACTIVATE not reached; readback unavailable | Partial execution must remain explicit until authoritative reconciliation |

None of these should be collapsed into a generic "agent failed" state.

---

# 11 Future-proofing MCWS as context windows grow

The original R1.6.1 boundary remains appropriate.

MCWS should not be defended only as token reduction.

Its defensible runtime role is bounded capability exposure where smaller stage-specific sets improve operational clarity or selection behavior.

Provider independence, deterministic ranking, execution authority, mutation budgets and outcome validation belong to MCR, not MCWS.

If future models reason perfectly over arbitrarily large tool catalogs without selection/security cost, MCWS may become less important. The deterministic mission/binding/outcome architecture can remain useful independently.

---

# 12 What the experiment actually supports

The original benchmark supports the following bounded claim:

> In the evaluated authored benchmark, stage-scoped MCWS achieved higher primary mission success than Broad and Static exposure.

It does not establish:

- universal MCWS superiority;
- production latency savings;
- monetary savings;
- prompt-injection immunity;
- multi-tenant isolation;
- transaction correctness; or
- outcome correctness.

R1.7–R1.9 add runtime evidence, but they are not retroactively added as rows to the frozen MCWS experiment.

---

# 13 When to choose Static versus MCR

Prefer **Static / compiled** when:

- one provider is stable;
- requirements are repetitive;
- operations are low-risk/read-only;
- execution is short-lived;
- deterministic throughput and simplicity dominate.

Prefer **MCR** when:

- provider availability/eligibility changes;
- requirements evolve mid-mission;
- tool estates overlap;
- delegated authority is material;
- consequential writes require bounded mutation authority;
- mission duration outlives one model session;
- point-of-use contract/policy changes are plausible; or
- authoritative outcome must be reconciled.

---

# 14 Platform map

The detailed vendor/platform map in R1.6.1 was a dated architecture map, not a vendor ranking.

This R1.9 closure draft does not refresh that market table. A publication release should either:

1. re-verify every time-sensitive platform claim immediately before publication; or
2. retain the R1.6.1 map explicitly as a dated 31 August 2026 snapshot.

No current-market claim should silently inherit freshness from the older whitepaper.

---

# 15 Build, buy and compose

The original practical rule still holds:

> **Buy the plumbing. Compose the providers. Build only the mission-semantic layer the enterprise uniquely needs.**

Buy/reuse:

- gateway;
- registry;
- OAuth/workload identity;
- API lifecycle;
- deterministic policy;
- observability.

Build narrowly:

- mission semantics;
- capability normalization;
- stage MCWS;
- mission-relative substitutability;
- deterministic binding state;
- transaction/mutation state;
- enterprise-specific outcome interpretation.

Compose:

- qualified MCP/API/event/enterprise providers.

---

# 16 Historical architecture ancestry: what is not new

MCR does not claim invention of:

- goal/capability mediation;
- semantic service descriptions;
- dynamic service binding;
- durable workflow state;
- Saga compensation;
- event-driven workflows; or
- tool retrieval.

The residual research question is how these ideas should be recomposed for probabilistic agent reasoning when executable capability descriptions themselves become model input and when authority/outcome truth must remain deterministic.

---

# 17 Closest prior art and residual contribution

The residual contribution remains a differentiated combination rather than a claim of a wholly new computational primitive:

1. durable mission state independent of model/provider session;
2. mission-stage capability demand;
3. stage-scoped MCWS reasoning boundary;
4. semantic proposal separated from deterministic admissibility/binding;
5. point-of-use contract and authority revalidation;
6. explicit mutation/transaction state;
7. execution receipt separated from authoritative outcome;
8. replay/continuation semantics that do not assume side effects are absent after client failure.

R1.9's strongest new evidence is not a clean success path. It is the explicit handling of ambiguous post-side-effect state.

---

# 18 Executive migration checklist

Before production adoption, require affirmative evidence for:

1. capability ownership/version traceability;
2. read/write/destructive semantics;
3. deterministic business authorization;
4. explainable provider eligibility;
5. directional substitutability;
6. correct resume identity/policy;
7. mutation budget;
8. replay barrier before first side effect;
9. contract drift handling;
10. authoritative readback independent of client success interpretation;
11. explicit partial-execution state; and
12. separate compensation authority.

---

# 19 Long-horizon thesis: from tool access to portable missions

The long-horizon architecture remains prerequisite-conditioned.

## 19.1 Directional substitution

R1.8 adds real contract-drift/requalification evidence but does not establish universal cross-provider equivalence.

## 19.2 Delegated authority

R1.9A formalizes delegation envelopes and attenuation rules. Full live multi-hop delegated mutation remains unestablished.

## 19.3 Transaction boundaries

R1.9B demonstrates why invocation state and commit state must be distinct. Full multi-provider atomicity is not established.

## 19.4 Compensation

Compensation remained unauthorized in the frozen R1.9B live mission. No compensation-correctness claim is made.

## 19.5 Checkpointed continuation

MissionCheckpoint and ContinuationLease exist in the R1.9A foundation. Live continuation after an ambiguous committed side effect remains future work.

## 19.6 Contract evolution

R1.8 provides direct evidence that nominal provider version equality can coexist with contract fingerprint drift.

## 19.7 Autonomous self-healing

Not established.

Earlier live process-loss work observed fail-closed behavior and required explicit recovery. MCR must not claim autonomous ADT resurrection.

## 19.8 Multi-ERP federation

Deferred.

Federation, cross-organization trust, liability and economic routing remain beyond the R1.9 closure.

---

# 20 A buildable research program after R1.9

The next program should begin only after R1.9 closure is frozen.

Suggested independent POCs:

| POC | Question | Evidence gate |
|---|---|---|
| N1 | Can authoritative readback be independent of the mutation provider? | Side effect reconciled without trusting mutation response |
| N2 | Can provider responses be normalized without losing contract identity? | Stable canonical outcome across qualified provider schemas |
| N3 | Can a mission resume after a confirmed partial mutation without replay? | Checkpoint continuity + no duplicate side effect |
| N4 | Can separately authorized compensation operate without authority amplification? | Explicit grant + bounded compensation evidence |
| N5 | What is pure governance overhead under successful live mutation? | Separate business time, validation time and governance-only time |
| N6 | Can delegated authority survive long-running resume/rebind? | No amplification; revocation observed |
| N7 | Can multi-ERP mission state remain portable? | Bounded cross-system mission with independent outcome evidence |

Each POC should receive its own prospective contract, authority boundary, freeze and evidence manifest.

---

# 21 Limitations and future work

The R1.9 program has several important limitations.

First, the original MCWS benchmark remains small and authored: 48 primary missions, four mission families and one local-model configuration. It does not establish population-level enterprise performance.

Second, R1.7/R1.8 provider/runtime evidence is bounded engineering evidence rather than a full production deployment.

Third, R1.9A is primarily deterministic/local foundation evidence.

Fourth, R1.9B did not reach validated live completion. CREATE reached the provider; ACTIVATE did not. The client then failed on response-shape handling, and authoritative SAP repository state could not be established before this draft. `CREATE_COMMIT_STATE=UNKNOWN` is therefore a scientific result, not a temporary wording inconvenience.

Fifth, no compensation was authorized or executed.

Sixth, full checkpointed continuation after a possibly committed side effect was not demonstrated.

Seventh, no autonomous self-healing claim is supported.

Eighth, multi-ERP federation, economic routing and cyber-physical execution remain long-horizon research.

The immediate publication task is therefore closure discipline, not another live write.

---

# 22 Conclusion

MCR began with a narrow post-LLM observation: when executable capability descriptions are placed inside model-active context, the tool catalog becomes part of probabilistic reasoning. The frozen MCWS benchmark supports stage-scoped capability exposure within its evaluated conditions, with MCWS achieving 30/48 primary mission successes compared with 17/48 for Static and 5/48 for Broad.

The broader Mission-Capability Runtime was originally presented as a practitioner pattern layered above protocols, gateways and systems of record. R1.7 and R1.8 added bounded engineering evidence for authority separation, provider contracts, point-of-use drift detection, multi-provider capability identity and governed continuation. R1.9A then formalized deterministic execution envelopes, mutation budgets, transaction state, contract leases, receipts and continuation objects.

R1.9B deliberately attempted the harder boundary: a prospectively frozen consequential SAP mutation. The program did not produce a clean end-to-end success. Instead, it exposed a sequence of fail-closed defects and ultimately reached the first mutation before failing on provider-response interpretation. Because the CREATE call may have produced a side effect, replay was correctly blocked. Because ACTIVATE was not reached and authoritative repository readback remained unavailable, completion could not be claimed.

That result sharpens MCR's central thesis.

A robust enterprise-agent runtime must distinguish what the model proposed, what authority permitted, what runtime bound, what provider executed, what side effect committed and what enterprise state was later validated. These are not interchangeable milestones.

The strongest defensible R1.9 closure is therefore bounded:

> **The LLM proposes semantics; the runtime binds authority; enterprise state decides completion.**

MCR R1.9 should close with the partial/unknown live result preserved, rather than extending the experiment until a cleaner demo appears.

---

## Appendix A — R1.9 closure labels

If authoritative readback proves the object exists:

`MCR_R1_9=BOUNDED_CLOSURE_WITH_PARTIAL_LIVE_MUTATION_RESULT`

If authoritative readback remains unavailable:

`MCR_R1_9=BOUNDED_CLOSURE_WITH_UNRESOLVED_CREATE_COMMIT_STATE`

## Appendix B — claims explicitly not made

This manuscript does not claim:

- autonomous self-healing;
- universal safe enterprise mutation;
- universal transaction atomicity;
- successful R1.9B end-to-end live completion;
- successful activation of `ZCL_MCR19B_9533C4D8`;
- proof that CREATE committed without authoritative readback;
- universal provider failover;
- general multi-ERP safety;
- compensation correctness; or
- production certification.

## Appendix C — publication work still pending

- authoritative read-only reconciliation if technically available;
- final closure evidence bundle;
- final claim/evidence audit;
- refreshed references for time-sensitive platform statements;
- final figures;
- reviewed PDF;
- release ZIP;
- GitHub release;
- Zenodo archival DOI.
