# ACLA -> EAF -> MCR relationship

The research program separates context lifecycle, assurance and execution.

| Layer | Question | Ownership |
|---|---|---|
| ACLA | What should the model know for this mission? | Persistent context, authority/temporal/provenance-aware context compilation, Mission Working Set |
| EAF | Is the agent sufficiently informed and authorized to act, and was the outcome validated? | Authority control, evidence sufficiency, pre-action assurance, outcome assurance |
| MCR | Which capability/provider/tool should satisfy the authorized mission, under which deterministic execution controls? | Capability working set, deterministic admissibility, binding, mutation/transaction state, execution |
| Evidence / P4 | What happened and what can be audited? | Correlated events, receipts, hashes, readback and reporting |

Recommended closed loop:

```text
Claude Mods
    |
    v
ACLA Context Compiler
    |
    v
Mission Working Set
    |
    v
EAF pre-action assurance
    |
    v
MissionExecutionEnvelope
    |
    v
MCR / MCWS
    |
    v
LLM semantic proposal
    |
    v
MCR deterministic binding/execution
    |
    v
ExecutionReceipt
    |
    v
EAF authoritative outcome observation
    |
    v
OutcomeReceipt
    |
    +--> audit/reporting
    +--> ACLA persistent evidence
```

These are three distinct research programs. MCR does not replace ACLA or EAF, and ACLA and EAF do not replace MCR.

Boundary rule:

- ACLA does not grant execution authority.
- EAF does not need to become the provider/tool runtime.
- MCR does not decide enterprise truth from tool return text alone.
- Reporting does not become execution authority.
