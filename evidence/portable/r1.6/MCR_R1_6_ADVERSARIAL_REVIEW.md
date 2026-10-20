# MCR / MCWS Whitepaper R1.6 — Final Independent Adversarial Review

Reviewer stance: skeptical peer reviewer, frozen-science constraint honored. No new experiments requested to strengthen the existing result; findings distinguish evidence class throughout.

---

## 1. EXECUTIVE VERDICT

R1.6 is a well-disciplined *narrowing* of an earlier, more inflated draft. It does the two hardest things a practitioner whitepaper can do: it concedes lineage it cannot win (OWL-S/WSMO/SOA/BPM/Saga/Temporal) instead of relabeling it, and it visually/textually separates CURRENT from EMERGING from HYPOTHESIS from LONG-HORIZON material almost everywhere. That discipline is real and should be credited.

But conceding lineage does not, by itself, earn the residual claim. After the concession, what's left is: (a) one bounded, small-N benchmark (48 primary missions, 4 authored mission families, one local model) showing MCWS beats Static and Broad tool exposure on task success; (b) a coherent but *unvalidated* architecture description (deterministic admissibility, Runtime Binding Record, recomposition loop) that is, at the description level, a competent modern re-statement of registry + policy-gateway + durable-workflow patterns already shipping in 2026 (MuleSoft Agent Fabric, AWS AgentCore/Cedar, Google Agent Registry); and (c) SAP engineering POCs that prove the surrounding plumbing works, not that the mission-capability abstraction itself does.

The paper's own framing — "MCWS is the evidenced mechanism; provider independence and recomposition belong to the broader runtime and are not credited to MCWS" — is the right move and largely holds up under scrutiny. It correctly forecloses Alternative C somewhat (deterministic binding is *not* smuggled in as if it were the tested variable) by explicitly saying the deterministic layer is *not* what was measured either — only capability exposure was. That is honest, but it also means the "operational schema" (four runtime records) and the "deterministic binding" language, which occupy most of the paper's page count, are essentially **unevaluated architecture**, competing directly against products already in market (Table 10) with no comparative evidence of superiority.

The paper is weakest exactly where a hostile reviewer would push: (1) the six claimed value channels of MCWS (selection quality, least-capability exposure, attack-surface reduction, policy clarity, reasoning-boundary auditability, cost/latency) are asserted as a bundle, but the frozen experiment measures only task-success rate — a proxy for selection quality alone. The other five are narrative extrapolations from one causal pathway (fewer tools shown → higher success), not independently measured. (2) The "post-LLM reasoning-boundary" framing is presented as if its closest antecedent is 2004–2010 Semantic Web Services; the far closer, and unaddressed, antecedent is the 2023–2025 LLM tool-retrieval/tool-subset-selection literature (RAG-for-tools, dynamic tool retrieval, context-aware filtering for agents), which made essentially the same "exposed catalog is part of the reasoning surface" observation years earlier and is only thinly represented in the bibliography (ToolScope, CMTF, BiasBusters — all 2026). This is the single most damaging prior-art gap in the manuscript.

The thesis survives, but only in a narrowed form, and only if the paper stops implying that the *combination itself* (MCWS + deterministic binding + recomposition) is validated as a system. What's validated is narrower still: bounded capability exposure improves task success in one small benchmark. Everything else is architecture, not evidence — which the paper mostly, but not perfectly, admits.

---

## 2. BINARY CORE GATE

```text
R1_6_RESIDUAL_CONTRIBUTION_AFTER_PRIOR_ART_CONCESSION=PASS
```

Explanation: a residual contribution survives — the *measured* claim that stage-scoped capability exposure (MCWS) outperforms Broad and Static exposure in this benchmark, plus a disciplined (if unvalidated) operational vocabulary for separating demand/supply/binding/evidence. It passes because the paper does not claim the combination is proven, and the narrow empirical claim is real, statistically supported for two of three pairwise comparisons, and clearly bounded. It is not a strong pass — the differentiation from contemporaneous tool-retrieval/scoped-execution work (Queen-Bee, Tool Forge, and the unaddressed 2023–2025 tool-retrieval literature) is thin, and most of the paper's bulk sits above the evidence line.

---

## 3. PUBLICATION READINESS

```text
READY_AFTER_BOUNDED_PATCHES
```

---

## 4. WHAT ACTUALLY REMAINS DIFFERENTIATED

Stripped of terminology and of everything already covered by OWL-S/WSMO/SOA/Saga/Temporal/ACC/Queen-Bee/Tool Forge/AWS Cedar/MuleSoft Fabric, the smallest defensible residual is:

- A **named, bounded benchmark result**: restricting the LLM-visible capability catalog to a mission-stage working set produced higher task success than showing it the full catalog (Broad) or a fixed compiled path (Static), in one small authored benchmark, on one local model, across four mission families (30/48 vs 17/48 vs 5/48; Broad–MCWS and Static–MCWS significant after Holm correction, Broad–Static not significant).
- A **vocabulary discipline** — four runtime objects (Mission Capability Requirement, Provider Capability Declaration, Runtime Binding Record, Outcome Evidence Receipt) consistently separating demand, supply, binding, and evidence, explicitly framed as a schema rather than a novelty claim.
- A **maturity-labeling practice** (CURRENT/EMERGING/HYPOTHESIS/LONG-HORIZON tagging applied to nearly every architectural element) that is unusually rigorous for a practitioner whitepaper and is itself a legitimate, if modest, contribution to how such papers should be written.

Everything else — deterministic admissibility, provider substitution formalism, TOCTOU binding, recomposition loop, degraded capability, mission portability — is architecture description, not evidence, and the paper substantially (though not completely) says so itself.

---

## 5. STRONGEST ARGUMENT FOR THE PAPER

The paper identifies a real, narrow, and non-obvious operational fact: once capability descriptions are readable by the model doing the selecting, the *catalog itself* becomes an input to a probabilistic process, not merely a lookup table for a deterministic planner. Classical service composition never had this property — the planner in OWL-S/WSMO was not itself a component that could be semantically confused, socially engineered, or biased by catalog ordering. An LLM choosing among tool descriptions can be. That distinction is real and is not fully captured by saying "this is just registry scoping" — a registry that only *filters what a deterministic planner can call* is a different security object from a registry that *filters what a probabilistic reasoner reads before deciding what to call*. The paper's own Figure 3 makes this argument cleanly, and the benchmark result, however small, is at least directionally consistent with it: broader exposure correlated with worse task outcomes in a setting designed to stress exactly that variable.

---

## 6. STRONGEST ARGUMENT AGAINST THE PAPER

The "post-LLM reasoning-boundary" framing is not as fresh as the paper implies, because it omits the literature that already made this exact argument for LLM agents specifically — dynamic/retrieval-based tool selection, context-aware tool filtering, and tool-subset curation for LLM function-calling agents were active research areas well before 2026 (the paper's own citations for adjacent 2026 work — ToolScope, CMTF, BiasBusters — are evidence that "restrict what the model sees to improve tool selection" is now a *crowded*, not novel, space). Once that lineage is added next to OWL-S/WSMO, the paper's residual claim shrinks from "we identified a new post-LLM problem" to "we ran a small benchmark inside an already-recognized problem space, using a slightly different architectural vocabulary than Queen-Bee or Tool Forge." That is a legitimate but modest contribution, not the five-layer, page-count-dominant architecture the paper spends most of its length building on top of it. A hostile reviewer's cleanest line of attack is: *the measured contribution is small and crowded; the unmeasured architecture is large and unvalidated; the paper's structure inverts the emphasis these two facts deserve.*

---

## 7. FALSIFICATION RESULTS

**Alternative A — MCWS is classical scoped service discovery applied to LLM tools.**
```text
PARTIALLY_SUPPORTED
```
Mechanically, MCWS *is* scoped discovery. What differentiates it from "classical" registry scoping is the claim that the consumer of the scoped set is a probabilistic reasoner rather than a deterministic planner, which changes what "scoping" is defending against (semantic collision/prompt-injection surface vs. pure lookup efficiency). The paper does not, however, empirically isolate this distinction from ordinary discovery-scoping benefits (fewer irrelevant options, less noise) — the benchmark cannot tell us how much of the MCWS advantage is "probabilistic-reasoning-specific" versus "any reasoner does better with fewer distractors," which is also true of humans and deterministic planners. Hence partial, not rejected.

**Alternative B — the benefit is context-size reduction, not a distinctive capability architecture.**
```text
UNRESOLVED
```
The paper explicitly anticipates this (Section 11/19.6) and argues token efficiency is secondary to selection/security/auditability rationale — but it never runs a control that holds context size constant while varying *how* the working set is chosen (e.g., a random same-size subset vs. MCWS's stage-relevant subset). Without that control, the benchmark cannot distinguish "MCWS's specific selection logic helps" from "any similarly-sized, non-adversarial subset would help about as much." This is a real, addressable gap the paper does not close.

**Alternative C — the real contribution is deterministic policy/runtime binding, not MCWS.**
```text
REJECTED
```
The paper explicitly and correctly does *not* claim the deterministic binding layer was tested — Table 1 and Section 5 attribute the frozen result to capability exposure alone and explicitly deny provider independence/recomposition credit to MCWS. This alternative is rejected on the paper's own terms because it does not conflate the two; the risk here is not that the paper commits this error but that a *reader skimming the architecture-heavy middle sections* would come away believing the whole stack was validated.

**Alternative D — the architecture is integration of known techniques, not a research contribution.**
```text
STRONGLY_SUPPORTED
```
On the paper's own historical-ancestry section (16–17), essentially every named component (goal/capability separation, semantic matching, dynamic binding, compensation, durable state) has direct 2000s-era prior art, and the 2026-era pieces (registries, gateways, Cedar policy, ACC) are already shipping commercial infrastructure. The paper's defensible claim is explicitly framed as "the combination," not new mechanism — which is consistent with this alternative rather than a rebuttal of it.

**Alternative E — conventional authorization filtering solves this without an MCWS abstraction.**
```text
PARTIALLY_SUPPORTED
```
Authorization filtering (RBAC/ABAC on top of a registry) would remove capabilities the caller isn't *permitted* to use. It would not, by itself, remove capabilities the caller *is* permitted to use but which are irrelevant to the current mission stage — which is the specific reduction MCWS targets. So MCWS is not redundant with authorization filtering. But it is also not shown to outperform simpler heuristics that would achieve similar exposure reduction (e.g., static per-stage allowlists configured by a human, which is close to the paper's own "Static" condition and lost to MCWS by a smaller, non-significant-relative-to-Broad margin at the case-cluster level). The paper does not fully foreclose "a simpler non-dynamic scoping heuristic gets most of the benefit."

---

## 8. CLAIM-EVIDENCE AUDIT

| ID | Claim | Claim Type | Evidence Present | Evidence Strength | Overstatement? | Required Action |
|----|-------|-----------|-------------------|--------------------|-----------------|------------------|
| C1 | MCWS achieves higher primary mission success than Broad and Static (30/48 vs 5/48 vs 17/48) | EMPIRICAL | Frozen 48-mission benchmark, Holm-adjusted cluster tests | LIMITED | No — appropriately hedged with p-values and cluster caveat | Keep narrowed to evaluated benchmark; do not generalize to "production" |
| C2 | Broad–Static difference is directional only | EMPIRICAL | Same benchmark, p=0.2266 | LIMITED | No | None — correctly labeled non-significant |
| C3 | Held-out results (Broad 0/12, Static 2/12, MCWS 7/12) support MCWS | EMPIRICAL | 4 independent held-out cases | ILLUSTRATIVE | Borderline — labeled "directional" but still reported prominently in abstract-adjacent text | State n=4 independent cases explicitly wherever the number is cited, not only in a footnote |
| C4 | The capability catalog becomes part of the model's active reasoning environment (post-LLM problem) | ARCHITECTURAL / DESIGN_CONSTRAINT | Conceptual argument, Figure 3 | MODERATE (as argument) / NONE (as isolated empirical effect) | Yes, mildly — implies more novelty than the 2023–2025 tool-retrieval literature would grant | Add that lineage explicitly (see Section 10 below) |
| C5 | MCWS has six value channels (selection quality, least-capability exposure, attack-surface reduction, policy clarity, auditability, cost/latency) | ARCHITECTURAL | Only selection quality is measured | LIMITED (1 of 6) / NONE (5 of 6) | Yes — bundling five unmeasured claims with one measured one | Explicitly mark 5 of 6 channels as unmeasured design rationale, not evidenced outcomes |
| C6 | Deterministic admissibility function (Sem ∧ Tenant ∧ Auth ∧ Policy ∧ SignedDecl ∧ Trust ∧ Tx ∧ Data ∧ Version) | ARCHITECTURAL | Pseudocode sketch only | NONE | No — labeled illustrative, not tested | None beyond existing labeling |
| C7 | Runtime Binding Record addresses TOCTOU | SECURITY / ARCHITECTURAL | Design description; revalidation-at-execution rule | NONE (implementation) | No — Figure 1 marks outcome/compensation as REFERENCE-DESIGN | State explicitly that TOCTOU mitigation is unimplemented design, not tested control |
| C8 | Directional, stage-relative provider substitutability | ARCHITECTURE HYPOTHESIS (self-labeled) | "Mechanism validation... 4/5 in the prequalified subset" | ILLUSTRATIVE | No — already labeled hypothesis | Report the n=5 sample size inline, not only implied |
| C9 | Multi-tenant isolation (discovery, cache, credentials) | SECURITY | Threat table description only | NONE | No — not claimed as tested | None |
| C10 | Malicious/compromised provider mitigation via deterministic ranking | SECURITY | Threat table description only | NONE | No | None |
| C11 | Mission portability ("historical policy ≠ current authority") | ARCHITECTURE HYPOTHESIS (self-labeled) | Conceptual principle only | NONE | No — labeled hypothesis | None |
| C12 | Protocol independence | DESIGN_CONSTRAINT (self-labeled) | None; explicitly "to be tested" | NOT_APPLICABLE | No — correctly labeled | None |
| C13 | Cyber-physical extension respects deterministic safety boundary | FUTURE (self-labeled LONG_HORIZON) | None | NOT_APPLICABLE | No | None |
| C14 | SAP/Capella/BAS engineering POCs (P1–P7) | ENGINEERING | Frozen implementation identifiers, proof-state legend | MODERATE (for what each POC individually claims) | No — explicitly separated from scientific claim | None; keep separation |
| C15 | Residual differentiation from Queen-Bee/Tool Forge | HISTORICAL | Comparison table (Table 12) | LIMITED | Mild — differentiation reads more like "different benchmark" than "different mechanism" | Sharpen or concede overlap explicitly (see Section 10) |

---

## 9. FINDINGS BY SEVERITY

### FATAL
```text
NONE
```
No finding here invalidates the central, narrowed thesis. The paper's own hedging (evidence-class table, maturity tags, explicit non-crediting of MCWS with provider independence) prevents any single issue from being fatal — the problems below are about proportion and completeness, not about the frozen result being wrong or the architecture being incoherent.

### MAJOR

**M1 — Bundled value-channel claim (Section 5, Table title "MCWS therefore has six value channels").**
The benchmark measures task success only. Five of six claimed value channels (least-capability exposure, attack-surface reduction, policy clarity, reasoning-boundary auditability, cost/latency) are asserted, not measured, yet are presented in the same breath and same evidentiary register as the one channel (selection quality) that the benchmark actually supports.

**M2 — Missing closest prior art: LLM tool-retrieval / dynamic tool-subset-selection literature.**
The manuscript's prior-art treatment is thorough for pre-LLM service composition (OWL-S/WSMO/SOA/Saga/Temporal) and thin for the *directly comparable* body of LLM-era work that scopes/retrieves/filters tool catalogs specifically to manage a model's reasoning surface. Only 2026 contemporaneous work is cited (ToolScope, CMTF, BiasBusters, Queen-Bee, Tool Forge); the 2023–2025 foundational work in this exact space is absent. This is the single strongest weakening omission in the paper (see Section 10).

**M3 — No control isolating "MCWS's selection logic" from "any similarly-sized subset."**
Nothing in the reported design holds catalog size constant while varying selection method, so Alternative B (context-size reduction, not a distinctive mechanism) cannot be ruled out from the data presented.

**M4 — Composite substitution acknowledged as unsolved but still diagrammed as part of the operational architecture.**
Section 19.4 admits atomicity, ordering, compensation and rollback are open problems, yet Figure 2/4 present the runtime as an operational pattern ready for adoption guidance (Table 5, "Stage 4: Runtime recomposition... prequalify directional/degraded provider substitutability"). A practitioner following the adoption roadmap could reasonably believe composite substitution is further along than it is.

**M5 — "H2 stage-exposure reduction is an architectural invariant verified in execution."**
This phrase (Section 12) risks maturity leakage: "verified in execution" reads as evidence of the *causal* claim (exposure reduces collisions/attack surface) when what was actually verified is that the code executes as designed (a tautology about implementation, not about the benefit).

### MINOR

**N1 —** Held-out n=4 independent cases is stated in prose but not repeated wherever the 0/12, 2/12, 7/12 figures are quoted; a skimming reader could treat 12 as the sample size.

**N2 —** "Provider substitution... mechanism validation; independently gated mission success 4/5 in the prequalified subset" (Appendix A) — n=5 should be stated inline in the main text wherever this result is referenced, not only in the appendix table.

**N3 —** Table 12's residual-distinction column for Queen-Bee and Tool Forge reads as a benchmark/scope difference more than a mechanism difference; wording should make explicit that the distinction is empirical-design-scope, not architectural novelty.

**N4 —** The abstract's opening sentence order (lineage concession, then p-values) is good, but the Table 1 "Architecture synthesis" row's claim that the practitioner pattern is "Builds on... ancestry; not claimed as a new computational primitive" could be stated even earlier, before Section 4, to preempt skimming misreadings.

**N5 —** "Post-audit... common-target reanalysis" (correcting an M003 Static grading asymmetry after freeze) is disclosed but the *criterion* for the correction is not stated in the excerpted text — a hostile reviewer will ask whether the correction rule was specified before or after seeing which arm it favored (see Section 17, Q3).

### OPTIONAL

**O1 —** A explicit object-capability-security citation (e.g., capability-based security lineage, not just "capability" as a business-operation label) would strengthen the terminology section, since "capability" already has a distinct, decades-old meaning in the security literature that the paper's usage risks colliding with.

**O2 —** Table 9 (Static vs. runtime decision framework) would benefit from an explicit column noting that the benchmark's own Static condition is the empirical proxy for the left column, so readers see the connection between the decision framework and the study design.

---

## 10. PRIOR-ART GAP ANALYSIS

**Gap 1: LLM-era dynamic tool selection / tool-retrieval literature (pre-2026).**
```text
WHY_IT_MATTERS=This body of work already treats the exposed tool/function catalog as part of the model's active input and already motivates scoping it down for selection accuracy and safety — which is the paper's central "post-LLM" framing. Its absence makes the post-LLM distinction look newer than it is.
WHAT_CLAIM_IT_CHALLENGES=The residual novelty claim in Section 17 ("closest prior art and residual contribution") and the abstract's framing of the post-LLM problem as the paper's differentiator.
SEVERITY=MAJOR
```

**Gap 2: Capability-based security / object-capability model (e.g., the object-capability security tradition).**
```text
WHY_IT_MATTERS=The paper's central noun, "capability," and its admissibility/binding formalism echo decades-old capability-security design (unforgeable references, least authority) more than it echoes OWL-S "capability" (a semantic service description). Conflating the two usages without acknowledgment risks a terminology critique from security reviewers specifically.
WHAT_CLAIM_IT_CHALLENGES=Terminology precision (Section 17 terminology stress test) and the security/authority sections (19.5, threat table).
SEVERITY=MINOR
```

**Gap 3: Existing LLM function-calling security/red-team literature on tool-description prompt injection.**
```text
WHY_IT_MATTERS=The threat table (Table 14) names "registry/declaration poisoning" and "adversarial selection inside admissible set" as threats, which are exactly the failure modes documented in existing tool-use red-teaming work; citing that work would substantiate the threat model rather than presenting it as a first-principles list.
WHAT_CLAIM_IT_CHALLENGES=Section 10 (malicious/compromised providers) and Section 19.5's threat model completeness.
SEVERITY=MINOR
```

No other omission rises above minor — the paper's classical-lineage citation coverage (OWL-S, WSMO, SOA/BPM, Saga, Temporal) is genuinely thorough, and its 2026 commercial/market coverage (MuleSoft, AWS, Google, Microsoft, IBM, SAP) is unusually complete for a whitepaper of this kind.

---

## 11. ARCHITECTURE COHERENCE VERDICT

- **MCWS:** Internally coherent and the only component with empirical support, though that support is narrow (one benchmark, one model, four mission families).
- **Deterministic binding:** Coherent as a specification; entirely untested. The admissibility predicate is a reasonable conjunction of checks but is illustrative pseudocode, not an implemented/verified component.
- **Provider substitution:** Directional formalism is a genuine improvement over naive symmetric equivalence, correctly labeled ARCHITECTURE HYPOTHESIS, but the substitutability relation (⪯) is defined informally (a list of properties it must respect) rather than with any decision procedure — a hostile reviewer will call this "descriptive, not executable," which the paper itself half-concedes.
- **Composite substitution:** Explicitly unresolved (see M4). This is the weakest single piece of the architecture and is honestly flagged as such, but its presence in the adoption roadmap (Table 5, Stage 4) slightly outruns that honesty.
- **Runtime Binding Record:** A sound sketch for TOCTOU mitigation at the design level (digest-binding plus point-of-use revalidation); no implementation evidence.
- **Mission-state transition / recomposition:** Coherent loop diagram; "authoritative observation" is not operationally defined beyond "system-of-record readback," which is reasonable for SAP but under-specified for non-SAP or non-deterministic observation sources (e.g., eventual consistency, conflicting sensor readings) — the paper's own "Limitations" section flags eventual consistency as future work, which is appropriate.
- **Multi-tenancy:** Addressed only at the threat-table level; no implementation or test evidence of tenant isolation in the MCWS construction path specifically.
- **Degraded operation:** A useful third state beyond binary admissible/inadmissible; correctly labeled hypothesis; the paper does not specify whether degraded operation requires the same re-authorization step as ordinary rebind (a plausible gap — Section 19.4 discusses degradation without explicitly cross-referencing the re-authorization rule from Section 19.3).

Overall: the architecture is a competent, internally consistent practitioner pattern. It is not shown to be superior to, or meaningfully different from, the commercial control-plane products the paper itself tables in Section 14 (MuleSoft, AWS, Google, Microsoft, IBM) beyond the specific mission/capability/provider vocabulary layered on top.

---

## 12. SCIENTIFIC EVIDENCE VERDICT

**What the experiment establishes:** In one benchmark of 48 primary missions across four authored mission families, tested against one local model, restricting the LLM-visible capability catalog to a stage-scoped working set (MCWS) produced a higher primary-mission-success rate (62.5%) than either full catalog exposure (Broad, 10.4%) or a fixed compiled path (Static, 35.4%). The MCWS-vs-Broad and MCWS-vs-Static differences remain significant after Holm correction at the case-cluster level; the Broad-vs-Static difference does not.

**What it does not establish:**
- Generalization across models, larger/heterogeneous mission catalogs, real (vs. authored/deterministic) providers, or production-scale tool counts.
- Any of the five non-selection-quality value channels claimed for MCWS (attack-surface reduction, policy clarity, auditability, least-capability exposure as an independent measured quantity, cost/latency benefit).
- That MCWS's specific selection mechanism, rather than any similarly small/relevant subset, drives the benefit (no size-matched control).
- Anything about the deterministic binding layer, provider substitution, recomposition, multi-tenancy, or TOCTOU mitigation — these were not part of the measured variable.
- Production readiness, cost savings, or superiority over existing commercial governed-catalog/gateway products.

Conservative classification: **preliminary/illustrative evidence** for the primary MCWS-vs-Broad/Static claim (not "strong evidence" — sample size, single-model, cluster count of 16, and held-out n=4 all argue against that tier); **hypothesis only** for provider substitution (n=5) and held-out generalization; **engineering evidence, not scientific validation** for the SAP/Capella/BAS POCs, correctly treated as such by the paper.

---

## 13. SECURITY / AUTHORITY VERDICT

The rule "LLM proposes semantics; deterministic runtime binds authority" is **maintained at the level explicitly modeled** — provider ranking, credentials, trust policy, and binding are all placed in the deterministic layer, and the pseudocode explicitly keeps ranking outside model control. This part of the boundary is well-designed and consistently described.

There is one under-addressed indirect path: the **model authors the demand side** (`required_capability`, stage interpretation) that feeds the admissibility computation. If the model mis-specifies, narrows, or broadens the stated requirement — whether through error, ambiguity, or adversarial manipulation of upstream mission input — it can shape *which* providers become eligible for ranking, even though it never ranks them itself. The paper does not name or address this "semantic funneling" risk explicitly; it treats "propose semantics" as a clean, contained action, but semantics-proposal and authority-shaping are not as cleanly separable as the one-sentence rule implies once the demand side is generated by the same probabilistic component the rule is designed to constrain. This is not a fatal flaw (the admissibility filter still runs on tenant/policy/trust regardless of what capability was requested), but it is a boundary condition the "propose semantics / bind authority" slogan glosses over.

The threat model (Table 14) is reasonably complete at the *taxonomy* level (poisoning, confused deputy, TOCTOU, cross-tenant leakage, adversarial selection, result falsification, credential replay, compromised runtime, economic manipulation) but every "required control" column is a design intention, not a tested mitigation — none of these threats were exercised against the implementation. That is honestly implied by the evidence-class labeling elsewhere in the paper but should be stated once, explicitly, in the threat-model section itself rather than left to be inferred from the separate maturity tables.

---

## 14. MATURITY-BOUNDARY AUDIT

```text
MCWS capability-exposure result ............... CURRENT (evaluated, bounded)
Deterministic admissibility/binding pseudocode . ARCHITECTURE HYPOTHESIS (self-labeled correctly)
Runtime Binding Record / TOCTOU mitigation ..... REFERENCE-DESIGN (self-labeled correctly)
Provider substitution (directional) ............ ARCHITECTURE HYPOTHESIS (self-labeled correctly)
Composite substitution .......................... HYPOTHESIS, explicitly unresolved (correctly labeled)
Mission portability ............................. ARCHITECTURE HYPOTHESIS (self-labeled correctly)
Recomposition loop mechanics .................... EMERGING / self-labeled, mostly correct
"Stage-exposure reduction verified in execution" (Sec 12) ... LEAKAGE — phrased as evidence of the causal benefit; actually only evidence the code runs as designed
Six MCWS value channels ......................... 1 CURRENT (selection quality) / 5 presented at CURRENT-adjacent register but actually HYPOTHESIS-tier — LEAKAGE (see M1)
Multi-tenancy isolation .......................... EMERGING, self-labeled, no implementation evidence
Degraded capability .............................. ARCHITECTURE HYPOTHESIS (self-labeled correctly)
Cyber-physical extension ......................... LONG_HORIZON (self-labeled correctly, explicitly rejects premature control authority)
Protocol independence ............................ DESIGN_CONSTRAINT explicitly "to be tested" (self-labeled correctly)
Economic routing .................................. EMERGING/LONG_HORIZON (self-labeled correctly)
```

Two leakage points are worth fixing (M5 and M1 above); everywhere else the paper's own maturity tagging (Table 13, Figure 4, Figure 6) is unusually careful and should be preserved as a model for future editions.

---

## 15. REQUIRED PATCH REGISTER

```text
FINDING_ID=M1
LOCATION=Section 10, "MCWS therefore has six value channels"
CURRENT_PROBLEM=Five of six claimed value channels are presented alongside the one measured channel without a strength distinction.
WHY_IT_MATTERS=A reader can reasonably conclude all six are evidence-backed because they appear in one undifferentiated list immediately following the benchmark numbers.
RECOMMENDED_PATCH=Split the list into "measured (1): selection quality" and "design rationale, not measured (5): least-capability exposure, attack-surface reduction, policy clarity, auditability, cost/latency," with one sentence explaining why each remaining channel is plausible but untested.
SCIENTIFIC_RESULT_CHANGE=NO
NEW_EXPERIMENT_REQUIRED=NO
CLAIM_NARROWING_REQUIRED=YES
```

```text
FINDING_ID=M2
LOCATION=Section 17 ("Closest prior art and residual contribution"), References
CURRENT_PROBLEM=The pre-2026 LLM tool-retrieval/dynamic-tool-selection literature, which already frames the exposed catalog as part of the model's reasoning input, is absent.
WHY_IT_MATTERS=This is the most directly comparable prior art to the paper's central "post-LLM" claim; omitting it inflates the apparent novelty of the framing.
RECOMMENDED_PATCH=Add a paragraph in Section 17 acknowledging this lineage explicitly, positioned between the OWL-S/WSMO paragraph and the Queen-Bee/Tool Forge paragraph, and narrow the "post-LLM problem" framing to "post-LLM-agent-tool-catalog problem, building on retrieval/filtering work, applied here to mission-stage structure specifically."
SCIENTIFIC_RESULT_CHANGE=NO
NEW_EXPERIMENT_REQUIRED=NO
CLAIM_NARROWING_REQUIRED=YES
```

```text
FINDING_ID=M3
LOCATION=Section 12 / Appendix A (methodology)
CURRENT_PROBLEM=No control isolates MCWS's selection logic from a same-size non-adversarial subset.
WHY_IT_MATTERS=Without it, Alternative B (context-size reduction alone) cannot be ruled out from the reported data.
RECOMMENDED_PATCH=Add one sentence in Limitations naming this specific missing control explicitly (not just "future work should test larger models"), so readers know the benchmark cannot separate "smaller" from "smarter-scoped."
SCIENTIFIC_RESULT_CHANGE=NO
NEW_EXPERIMENT_REQUIRED=YES (only for closing the gap, not for republishing R1.6)
CLAIM_NARROWING_REQUIRED=YES
```

```text
FINDING_ID=M4
LOCATION=Table 5 (adoption roadmap, Stage 4) / Section 19.4
CURRENT_PROBLEM=Composite substitution is presented in the adoption roadmap as an achievable stage while Section 19.4 admits it is an unresolved open problem.
WHY_IT_MATTERS=A practitioner following the roadmap could under-scope the engineering effort required for Stage 4.
RECOMMENDED_PATCH=Add a footnote to Table 5, Stage 4, cross-referencing Section 19.4 and stating composite substitution specifically remains unresolved architecture, distinct from single-provider directional substitution.
SCIENTIFIC_RESULT_CHANGE=NO
NEW_EXPERIMENT_REQUIRED=NO
CLAIM_NARROWING_REQUIRED=YES
```

```text
FINDING_ID=M5
LOCATION=Section 12, "H2 stage-exposure reduction is an architectural invariant verified in execution"
CURRENT_PROBLEM=Phrase implies the causal exposure-reduction benefit was verified, when only code execution was verified.
WHY_IT_MATTERS=Maturity leakage — reads as stronger evidence than the frozen study supports.
RECOMMENDED_PATCH=Reword to "H2 stage-exposure reduction was implemented and executed as designed in every trial; this confirms the mechanism ran correctly, not that its downstream security/collision benefits were independently measured."
SCIENTIFIC_RESULT_CHANGE=NO
NEW_EXPERIMENT_REQUIRED=NO
CLAIM_NARROWING_REQUIRED=YES
```

```text
FINDING_ID=N1
LOCATION=Wherever held-out 0/12, 2/12, 7/12 figures are quoted (abstract-adjacent and Section 12)
CURRENT_PROBLEM=Sample size (4 independent cases) is stated once in prose but not repeated at each citation of the 12-based figures.
WHY_IT_MATTERS=Skimming readers may treat n=12 as the effective sample size.
RECOMMENDED_PATCH=Append "(n=4 independent held-out cases)" at every occurrence of the held-out figures, not only the first.
SCIENTIFIC_RESULT_CHANGE=NO
NEW_EXPERIMENT_REQUIRED=NO
CLAIM_NARROWING_REQUIRED=NO
```

```text
FINDING_ID=N2
LOCATION=Appendix A, "Provider substitution" row; Section 19.4
CURRENT_PROBLEM=n=5 for the "4/5 in the prequalified subset" claim is only visible in the appendix.
WHY_IT_MATTERS=The main-text mentions of provider-substitution "mechanism validation" do not carry the sample-size caveat.
RECOMMENDED_PATCH=State "(4 of 5 prequalified cases)" inline wherever provider-substitution validation is referenced in the main text.
SCIENTIFIC_RESULT_CHANGE=NO
NEW_EXPERIMENT_REQUIRED=NO
CLAIM_NARROWING_REQUIRED=NO
```

```text
FINDING_ID=N5
LOCATION=Section 12, "corrected M003 Static grading asymmetry"
CURRENT_PROBLEM=The criterion and timing for the post-freeze correction rule is not stated in the reviewed text.
WHY_IT_MATTERS=A hostile reviewer will ask whether the correction rule was specified independent of which arm it would favor.
RECOMMENDED_PATCH=Add one sentence stating the correction rule explicitly and confirming it was defined by reference to the grading rubric error alone, before results were compared, with a pointer to the frozen manuscript for the exact rule text.
SCIENTIFIC_RESULT_CHANGE=NO
NEW_EXPERIMENT_REQUIRED=NO
CLAIM_NARROWING_REQUIRED=NO
```

---

## 16. CLAIMS THAT SHOULD NOT BE STRENGTHENED

- The MCWS-vs-Broad/Static task-success result must stay bounded to "this benchmark, this model, these four mission families." It should not be generalized to "production," "enterprise-scale," or "any LLM," regardless of future informal replications, until a new frozen study says so.
- Provider substitution mechanism validation (4/5 cases) must remain "illustrative/mechanism validation," never elevated to "proven" or "validated" in future editions without a larger, independently-run study.
- None of the five unmeasured MCWS value channels (attack-surface reduction, policy clarity, auditability, cost/latency, least-capability exposure as an independent metric) should be promoted from design rationale to evidenced benefit without a dedicated measurement design for each.
- The deterministic binding/admissibility layer, Runtime Binding Record, recomposition loop, mission portability, and composite substitution must remain labeled hypothesis/reference-design until implemented and tested — none of this should be described as "proven" in future marketing or abstract language even if the SAP POCs expand.
- Cyber-physical and economic-routing material must remain long-horizon/emerging; no future edition should imply readiness or certification-adjacent language without new evidence from the domains those claims actually require (functional-safety practice, commercial/legal frameworks).

---

## 17. QUESTIONS A HOSTILE PEER REVIEWER WILL ASK

1. If context windows are already 400k–1M tokens (as the paper itself notes in 19.6), why should a reviewer believe capability-count, rather than raw token count, is the operative variable — and where is the control that separates them?
2. The benchmark used a single local model. Which model, and why should its tool-selection failure modes generalize to frontier hosted models with materially different function-calling training?
3. Was the M003 Static grading-asymmetry correction rule fixed before or after the arm-level results were compared? What is the exact rule, and is it available for independent audit?
4. Given that Queen-Bee already reports retrieval beating static routing and Tool Forge already reports 99%+ context reduction with governed catalogs, what specific mechanism in MCWS is not already present in either of those systems — beyond running a different, smaller benchmark?
5. The admissibility predicate lists nine conjunctive checks (semantic match, tenant, authority, policy, signature, attestation, schema version, transaction compatibility, residency, outcome verifiability) — has any of this been implemented and load-tested, or is it entirely a design sketch? If untested, why does Table 6 present it as ready operational guidance for practitioners at multiple risk tiers today?
6. How does the runtime prevent the model from indirectly shaping provider eligibility by how it phrases the `required_capability` it proposes, given that the model — not a human — authors the demand side that feeds the deterministic admissibility filter?
7. Composite (multi-provider) substitution is explicitly unresolved for atomicity, ordering, and compensation. Why does the five-stage adoption roadmap (Table 5) place "runtime recomposition" — which depends on substitutability including composite cases — as an achievable Stage 4 without flagging that limitation at the point of the roadmap itself?
8. What does "authoritative observation" mean operationally outside SAP's synchronous system-of-record readback model — e.g., under eventual consistency, conflicting sensor input, or multi-system disagreement — and how does the recomposition loop avoid oscillation in those cases?
9. Held-out generalization rests on 4 independent cases. What is the paper's basis for describing this as "directional" rather than simply insufficient to draw any conclusion at all?
10. If the deterministic binding, recomposition, and provider-substitution layers are explicitly not credited to the MCWS evidence, why does roughly 70% of the paper's page count and nearly all of its diagrams focus on describing them rather than on the one component that was actually measured?

---

## 18. FINAL THESIS TEST

Thesis under test:

> Stage-scoped capability exposure addresses a specifically post-LLM enterprise problem: executable capability descriptions can become part of a probabilistic model's active reasoning environment, so the exposed catalog itself can change tool-selection behavior, attack surface and auditability. The Mission-Capability Runtime combines this evidence-backed MCWS mechanism with deterministic tenant/policy/trust admissibility and provider binding, while authoritative enterprise observation drives mission-state transition and recomposition. The architecture builds on Semantic Web Services, SOA/BPM, Saga and durable-workflow ancestry rather than claiming to replace them.

```text
THESIS_STATUS=DEFENSIBLE_WITH_NARROWING
```

Why: the first sentence (the post-LLM framing) is defensible only once it is narrowed to acknowledge the pre-2026 LLM tool-retrieval/filtering lineage (M2) — as written it slightly overclaims freshness. The second sentence overstates integration: it says the architecture "combines" the evidence-backed MCWS mechanism *with* deterministic binding, as though the combination itself carries the paper's evidentiary weight — but the paper's own Table 1 says the opposite (binding/recomposition are not credited to the evidenced mechanism). The sentence should read "pairs" or "is designed to be combined with," not "combines," to avoid implying the pairing was tested as a unit. The third sentence (attack surface/auditability as consequences) is architectural rationale, not evidenced outcome, and should be flagged as such inline. The final sentence (historical ancestry, not replacement) is fully defensible and is the strongest, most careful part of the thesis as written.

---

## 19. FINAL MACHINE-READABLE CLOSURE

```text
MCR_R1_6_FINAL_ADVERSARIAL_REVIEW=PASS
RESIDUAL_CONTRIBUTION=PARTIAL
POST_LLM_DISTINCTION=MODERATE
MCWS_EVIDENCE_ALIGNMENT=PARTIAL
DETERMINISTIC_AUTHORITY_BOUNDARY=PARTIAL
PRIOR_ART_POSITIONING=PARTIAL
ENGINEERING_VS_SCIENCE_SEPARATION=PASS
CURRENT_FUTURE_BOUNDARY=PASS
FATAL_FINDINGS=0
MAJOR_FINDINGS=5
MINOR_FINDINGS=5
NEW_EXPERIMENT_REQUIRED_FOR_CURRENT_THESIS=FALSE
FROZEN_SCIENCE_CAN_REMAIN_UNCHANGED=TRUE
PUBLICATION_READINESS=READY_AFTER_BOUNDED_PATCHES
THESIS_STATUS=DEFENSIBLE_WITH_NARROWING
```
