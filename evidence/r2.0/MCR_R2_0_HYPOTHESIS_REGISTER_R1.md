# MCR R2.0 Hypothesis Register R1

No hypothesis is classified before evidence exists. "Model support" below is SYNTHETIC/LOCAL design coverage, not a classification.

| ID | Hypothesis | Classification | Model support (R2.0A, synthetic) | Evidence still required |
|---|---|---|---|---|
| H41 | Authoritative Commit Observation: a live mutation is distinguishable as COMMITTED / ABSENT / UNKNOWN via a frozen authoritative readback contract | NOT_CLASSIFIED | guards for EXISTS/ABSENT/UNKNOWN, non-authoritative levels -> UNKNOWN | live readback qualification (R2.0B) and live study (R2.0C) |
| H42 | Outcome-Authoritative Completion: COMPLETE only when authoritative state satisfies frozen contract | NOT_CLASSIFIED | tri-state predicates, forged-result rejection, UNKNOWN stays pending | live study |
| H43 | Transaction Correlation without reliance on temporal proximity | NOT_CLASSIFIED | id+hash correlation, mismatch rejection | live study; provider must return a correlatable identity |
| H44 | Replay-Safe Continuation from a checkpoint | NOT_CLASSIFIED | consumed-set inheritance, lease bound to checkpoint, no budget growth | R2.0D (local first) |
| H45 | Compensation Authority Separation | NOT_CLASSIFIED | separate grant, no inheritance, authoritative post-readback | R2.0E (local first) |
| H46 | Contract-Drift Fail-Closed Outcome Validation | NOT_CLASSIFIED | point-of-use fingerprint check before budget consumption | readback-side drift handling and live fingerprints |
| H47 | Evidence-Complete Mission Closure | NOT_CLASSIFIED | 13-link hash chain on synthetic mission | live chain |
| H48 | Bounded Governance Overhead | NOT_CLASSIFIED | telemetry fields only | R2.0F measurements |

Classes allowed later: PROVEN, OBSERVED, PARTIAL, SYNTHETIC, LOCAL, NOT_ESTABLISHED, DEFERRED, REJECTED. No automatic promotion.
