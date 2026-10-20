# MCR R1.9 Claim / Evidence Matrix R1

Status vocabulary:

- **PROVEN / OBSERVED** — directly supported by frozen/live evidence.
- **PARTIAL** — some live behavior observed; end state not fully established.
- **SYNTHETIC / LOCAL** — deterministic local/mock evidence only.
- **NOT ESTABLISHED** — evidence is insufficient.
- **DEFERRED** — intentionally outside R1.9 closure.

| ID | Claim | Status | Evidence basis | Boundary |
|---|---|---|---|---|
| C01 | Stage-scoped MCWS outperformed Broad and Static in the frozen primary benchmark | PROVEN | R1.6 frozen experiment | Bounded authored benchmark only |
| C02 | MCWS itself provides provider abstraction | REJECTED | Adversarial review / architecture boundary | Provider abstraction belongs to MCR binding |
| C03 | LLM semantic proposal is separated from deterministic execution authority | PROVEN / ARCHITECTURE+LIVE | R1.7-R1.9 controls | Does not prove production security |
| C04 | Discoverable capability is not automatically authorized | PROVEN | R1.7 authority tests | Bounded tested rules |
| C05 | Trusted-to-describe is distinct from authorized-to-execute | PROVEN | R1.7 federated authority tests | Bounded tested rules |
| C06 | Delegated authority cannot amplify | PROVEN locally; live multi-hop NOT ESTABLISHED | R1.7/R1.9A | Full live delegated write chain absent |
| C07 | Provider version equality implies contract equality | REJECTED | R1.8 Fiori drift | Opposite observed |
| C08 | Point-of-use contract mismatch can fail closed and require requalification | PROVEN | R1.8 C2 | Specific provider set |
| C09 | Four local provider surfaces can be mission-scoped under canonical `PROVIDER::TOOL_NAME` identity | PROVEN | R1.8 | ADT/Fiori/UI5/CAP bounded set |
| C10 | MCR autonomously self-heals an ADT provider | NOT ESTABLISHED / CONTRARY OBSERVATION | R1.7 process-loss study | Explicit recovery was required |
| C11 | Mutation authority can be bounded to an exact count and exact capabilities | PROVEN as control | R1.9B contract / authorization | Full mission did not complete |
| C12 | Single-use authorization prevents replay after first side-effect boundary | PROVEN | HF06 lock | Does not resolve whether CREATE committed |
| C13 | MCP session semantics are part of valid runtime state | PROVEN | HF05 failure + HF06 qualification | ADT MCP implementation studied |
| C14 | `notifications/initialized` ordering matters in the studied ADT MCP path | PROVEN | protocol forensic / HF06 | Provider-specific protocol evidence |
| C15 | Execution receipt is equivalent to validated outcome | REJECTED | R1.7 outcome model + R1.9B partial execution | They are explicitly different states |
| C16 | R1.9B completed CREATE+ACTIVATE+ATC | NOT ESTABLISHED / FALSE for ACTIVATE | HF06 attempt 2 | ACTIVATE was not reached |
| C17 | HF06 CREATE definitely committed in SAP | NOT ESTABLISHED | failed readback / inconclusive reconciliation | `CREATE_COMMIT_STATE=UNKNOWN` |
| C18 | HF06 CREATE definitely did not commit | NOT ESTABLISHED | same | Unknown means neither success nor absence can be claimed |
| C19 | R1.9B demonstrated compensation correctness | NOT ESTABLISHED | compensation authority was false | No compensation executed |
| C20 | R1.9A provides checkpoint/continuation objects | SYNTHETIC / LOCAL | foundation package | Live ambiguous-side-effect continuation not demonstrated |
| C21 | Governance requires an LLM call per action | REJECTED by design/foundation | R1.9A | Deterministic fast path |
| C22 | Full live mutation-to-authoritative-outcome correctness is established | NOT ESTABLISHED | R1.9B | Closure must remain partial/bounded |
| C23 | Multi-ERP federation is established | DEFERRED | roadmap | Future research |
| C24 | Cyber-physical safety is established | DEFERRED / NOT ESTABLISHED | original long-horizon roadmap | Requires separate deterministic safety evidence |

## Recommended closure claim

If no authoritative readback becomes available:

`MCR_R1_9=BOUNDED_CLOSURE_WITH_UNRESOLVED_CREATE_COMMIT_STATE`

If authoritative readback confirms persistent CREATE but ACTIVATE remained unexecuted:

`MCR_R1_9=BOUNDED_CLOSURE_WITH_PARTIAL_LIVE_MUTATION_RESULT`
