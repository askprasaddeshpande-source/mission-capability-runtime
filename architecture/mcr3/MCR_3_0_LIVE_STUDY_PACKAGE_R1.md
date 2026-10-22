# MCR 3.0 Future Live-Study Package R1 (PREPARED, NOT AUTHORIZED, NOT EXECUTED)

Status: **design and authorization template only.** No SAP write, activation, cleanup of `ZC_MCR20C_7A3F91D2`, deployment or credential use was performed or is authorized by this document. Every live claim below stays **NOT_ESTABLISHED** until an owner-authorized study observes it independently. The existing ADT bearer token is treated as exposed; this study cannot start until the owner rotates it (BLOCKED_SECURITY_DEPENDENCY).

## 1. What a study must add beyond R2.0C (the open evidence)
| Gap | Required observation | Pass criterion |
|---|---|---|
| Link 14 never observed live | emit and persist the CompletionReceipt hash in the run record | 14 of 14 links in the live chain file, hash-verified offline |
| Activation / package not established | readback of the ACTIVE version and package assignment | predicates `$activation == ACTIVE` and `package == <authorized package>` evaluated on an authoritative read |
| Single readback source | second, independently obtained read (a different tool or a human Eclipse/ADT observation recorded as SELF_REPORTED_HUMAN) | two sources agree; a disagreement is UNKNOWN, never PASS |
| Active vs inactive versions | per-version reads (`inactive`, `active`) | each version has its own receipt; ambiguity fails closed |
| ABSENT proof | 404 naming exactly the requested object, per version | portable rules in `mcr3_readback.py` |
| No live non-success branch | at least one controlled failure (for example an object that already exists, or a refused name) with recovery | outcome class COMMIT_UNKNOWN or FAIL reached and handled without a repeat send |
| Compensation untested live | one authorized compensation with attempt accounting | one ledger entry per attempt before the call; goal verified by a distinct authoritative readback |

## 2. Fresh authorization packet (fields the OWNER must fill and sign off; none are pre-filled)
```
STUDY_ID:                    # new id; never reuse the R2.0C authorization
OWNER / APPROVER:            # a person; approval record issued by the external approver (Governor), verified by ApprovalVerifier
TARGET_SYSTEM / CLIENT:      # exact system id and client
PACKAGE:                     # exact package, e.g. a disposable package created for the study
OBJECT_NAMES:                # exact names, fresh, with the study prefix; the ABSENT baseline must show 404 naming each
CAPABILITY / PROVIDER / TOOL # exact capability id and provider_ref "<provider_id>::<tool>"
MUTATION_BUDGET:             # forward sends (default 1 per object), compensation attempts (separate grant, default 1)
WINDOW:                      # expires_at (UTC); the model enforces it at authorization and at the point of sending
FROZEN FINGERPRINTS:         # git commit of MCR, SHA-256 of mcr3_model.py, provider tool-contract fingerprint, outcome-contract hash
CREDENTIAL:                  # a newly issued, least-privilege, short-lived credential; NEVER the exposed ADT token
RECORDING:                   # raw evidence custody location, sanitization rule, reviewer access
```
The approval record must match the study's expected scope exactly (owner, capability, provider, target, operation, environment, policy digest) and be bound to the run; an adapter used in the study stays OBSERVATION_ONLY unless a verified approval promotes it.

## 3. Test plan (ordered; each step has an explicit stop condition)
0. Preconditions: credential rotated by the owner; fingerprints frozen and committed; reviewer named; dry run of the entire flow against the offline reference provider (`mcr3_readback.py`) green.
1. Read-only baseline: ABSENT per object and per version; package exists and is the authorized one; provider contract fingerprint equals the frozen one. **Stop** on any difference.
2. Forward send 1 (create). Ledger entry before the call. Record execution receipt (never implies commit).
3. Commit observation by authoritative readback (existence, version, source hash).
4. Activation: only if the authorization names activation as an operation; separate send and separate budget unit. Read active and inactive versions separately.
5. Outcome validation: bounded predicates, PASS / FAIL / UNKNOWN. Second independent source compared.
6. Completion: all 14 links persisted; offline verifier recomputes every hash.
7. Non-success case (separate authorized object): induce a known refusal; verify the model reaches COMMIT_UNKNOWN or FAIL, performs no second send for the same mutation, and requires a readback before any further action.
8. Compensation case (separate grant): one attempt, ledger entry first, post-compensation authoritative readback showing the goal met.

## 4. Decision boundaries
- **Stop (no further sends, preserve evidence):** fingerprint drift, budget exhausted, authorization expired or revoked, ABSENT baseline not clean, any UNKNOWN commit state, any disagreement between readback sources, any tool error that could have committed.
- **Abort (end the study):** credential problem, unexpected object found in the target package, ledger check_anchor mismatch, a second send being requested for the same mutation id.
- **Rollback (compensation) is allowed only** under a pre-issued separate grant with preconditions satisfied by an authoritative readback; otherwise the object is reported and left for the owner (as with `ZC_MCR20C_7A3F91D2`).
- The study never retries a possibly completed mutation.

## 5. Claims after a successful study (the most that may be said)
Scoped observation of one or a few objects in one system under one tool path. Not: general SAP correctness, production readiness, exactly-once enterprise execution, or independence beyond what the second source actually provides.
