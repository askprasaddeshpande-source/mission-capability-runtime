# MCR R1.9 Final Architecture Figure Specification R2

Specification only; no figure is rendered here. Intended for one landscape publication figure (SVG/TikZ source to be derived later, consistent with the R1.6.1 figure style).

## Evidence-status encoding (mandatory, redundant: color + border + label)

| Status | Meaning | Border | Fill | Text tag |
|---|---|---|---|---|
| CURRENT / PROVEN | Frozen result or verified property within stated scope | solid, thick | solid | `[PROVEN]` |
| PARTIAL / OBSERVED | Seen in bounded live runs; end state incomplete | solid, thin | hatched | `[OBSERVED]` / `[PARTIAL]` |
| SYNTHETIC / FOUNDATION | Deterministic or local conformance only | dashed | light tint | `[SYNTHETIC]` |
| FUTURE / DEFERRED | Not established | dotted, no fill | none | `[DEFERRED]` |

Color must never be the only encoding (grayscale and color-blind safe). Any element whose evidence is unresolved must use dotted or dashed styling, never solid.

## Layout (left to right, top to bottom)

### Row 1: inputs
- **MISSION PLANE** (mission state, stage, policy/evidence) `[OBSERVED]` (R1.8 mission-scoped runs)
- **CONTEXT / ASSURANCE INPUT**: ACLA Mission Working Set `[DEFERRED]` (separate research program; integration not evidenced here); EAF MissionExecutionEnvelope `[SYNTHETIC]` (R1.9A schema)

### Row 2: selection
- **CAPABILITY PLANE**: capability requirement -> MCWS (Minimum Capability Working Set) `[PROVEN]` for stage-scoped selection in the frozen benchmark only

### Boundary
- **PROBABILISTIC BOUNDARY** (heavy vertical rule): *LLM semantic proposal only*. Label on the rule: "The LLM proposes semantics". Nothing right of the rule accepts a model output as authority.

### Row 3: DETERMINISTIC MCR (single container, label "the runtime binds authority")
Sub-boxes in order:
1. admissibility `[PROVEN]` (bounded R1.7 rule families)
2. authority intersection `[SYNTHETIC]` (live multi-hop absent)
3. contract lease / fingerprint `[OBSERVED]` (R1.8 point-of-use revalidation)
4. provider ranking `[OBSERVED]` (directional equivalence, bounded)
5. parameter / target checks `[OBSERVED]` (R1.9B exact target frozen)
6. mutation budget `[PARTIAL]` (frozen; consumed 2/2 only in P6-D1)
7. transaction envelope `[SYNTHETIC]`

### Row 4: provider and execution
- **PROVIDER PLANE**: ADT, Fiori, UI5, CAP `[OBSERVED]`; other providers `[DEFERRED]`
- **EXECUTION PLANE**: request -> provider response -> side effect. Render as three separate stacked states with a visible gap between "provider response" and "side effect committed" (this gap is the R1.9B finding). **ExecutionReceipt** `[SYNTHETIC]` (R1.9A); annotate "none written in HF06".

### Row 5: outcome
- **OUTCOME ASSURANCE**: authoritative observation -> **OutcomeReceipt**. Authoritative observation `[OBSERVED]` in P6-D1 only; `[PARTIAL]` for R1.9B (readback unavailable, commit UNKNOWN). OutcomeReceipt `[SYNTHETIC]`.

### Row 6: mission transition
Five exits: **complete** `[OBSERVED]` (P6-D1), **blocked** `[OBSERVED]` (fail-closed cases), **partial** `[PARTIAL]` (R1.9B), **recompose** `[OBSERVED]` (requalification, bounded), **continuation-required** `[SYNTHETIC]` (MissionCheckpoint/ContinuationLease; live `[DEFERRED]`).

## Required annotations

- Central formula banner under the whole figure: `REQUESTED != AUTHORIZED != BOUND != EXECUTED != COMMITTED != VALIDATED_COMPLETE`
- Authority banner: `The LLM proposes semantics; the runtime binds authority; enterprise state decides completion.`
- Callout on the execution plane: `R1.9B: CREATE reached provider. ACTIVATE did not. CREATE commit UNKNOWN.` (dotted callout)
- Footer: frozen MCWS result applies only to the capability plane; later layers are not experimental rows of that study.

## Positioning strip (small, top-right)

`Claude Mods -> ACLA -> EAF pre-action -> MCR -> EAF post-action -> ACLA / evidence`, with the three programs in three distinct, equally weighted boxes. ACLA asks "what should the model know?"; EAF asks "is the agent authorized and sufficiently informed, and was the outcome validated?"; MCR asks "which capability/provider/tool should satisfy the authorized mission under which deterministic controls?". Do not draw MCR enclosing or replacing ACLA or EAF.

## Prohibited in the figure

Solid styling on any SYNTHETIC/DEFERRED element; a single arrow from "request" to "complete"; any element implying autonomous self-healing, atomic transactions, compensation correctness, multi-ERP federation or cyber-physical safety as present capabilities.
