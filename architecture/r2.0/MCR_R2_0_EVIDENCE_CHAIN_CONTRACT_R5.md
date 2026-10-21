# MCR R2.0 Evidence Chain Contract R5

Supersedes R4 (retained). Source of truth: `tools/r2.0/mcr_r2_model.py`. Added after independent review 4 of `f6e79a4` (verdict HOLD). R4 sections 1 (resume re-runs the real guards), 3 (compensation), 4 (types) and 5 to 8 remain in force with the changes below; R3's relation table gains R50.

## 1. Concurrency
Every guard method takes a per-Mission re-entrant lock for the whole call (snapshot, work, commit or rollback), so two threads on one Mission cannot interleave and one thread's rollback cannot erase another's successful send. `checkpoint_lease` takes the same lock. **Scope:** thread safety of a single Mission object only. Several Mission objects, processes or machines are protected by the replay ledger, not by this lock. `fail_before_mutation` refuses when either the Mission's own counter or the ledger shows a send.

## 2. Types
Presented objects are checked at acceptance: every `*_id` and `*_hash` field must be a string (`None` is refused); `capability`, `tool_name`, `identity`, `provider_ref`, `provider_id`, `target_system` and `objective` must be strings; `scope` must be a list of non-empty strings (a string scope is refused, closing the substring attack). `retries` must be exactly the integer 0 (not `0.0`, `-0.0`, `False`).

## 3. Compensation (additions to R4 section 3)
A grant whose goal predicates already hold on the forward readback is refused (a tautological or already-satisfied goal); a cosmetic clone of the forward readback therefore cannot complete a compensation. `COMPENSATED` additionally requires the compensating call's execution receipt to report `PROVIDER_RESPONSE_SUCCESS` (a no-response, error, unknown or not-sent class leaves the mission in COMPENSATION_AUTHORIZED); the authoritative post readback still decides the goal.

## 4. The replay ledger (replaces R4 section 2)
`ReplayLedger(path, expected_id=None)` is an append-only file: a **header line** with a random ledger id and CRC, then one JSON line per consumed (authority hash, mutation id) with a CRC. Locking, re-read on every operation, per-authority send limit, torn-tail handling, fail-closed on corruption and fsync are as in R4. Additions:
- **Identity.** The header id is copied into every lease. `resume()` refuses a lease whose `ledger_id` differs from the ledger's. A ledger object notices if its file is replaced while open. With `expected_id` pinned (for example recorded in the authorization), a missing, empty or replaced file raises, for fresh missions too.
- **Leases must be backed.** A lease that claims consumed sends the ledger does not record is refused (a forged lease against an empty or recreated ledger cannot resume).
- **Errors.** File problems, malformed keys (strings, bytes, wrong arity, control characters, text that cannot be encoded), invalid `limit` (must be a non-negative integer or `None`) and malformed resume arguments raise `GuardError`.
**Does NOT guarantee:** detection of deletion or replacement when no id is pinned and no lease is involved (a fresh mission against a recreated ledger will send; tested and recorded as a documented limit); restore of an OLDER copy of the same file (same id, fewer entries); callers using different ledger files; a volatile ledger across processes; network filesystems without working locks; power-loss durability; POSIX locking (`fcntl` path inspected, not run). The frozen R2.0C runner uses its own lock file, not this ledger.

## 5. A resumed mission trusts its lease and ledger
`COMPLETE` on a resumed mission rests on a hash-valid lease that is consistent with the ledger and on a **fresh** authoritative readback, outcome and completion. It does not re-prove that the original send happened beyond the ledger entry; the synthetic execution receipt of a resumed mission has call class COMMIT_UNKNOWN and appears in the chain as link 10.

## 6. Fields COMPLETE does not constrain (disclosed)
`readback.activation`, `readback_contract.checks` and `provider_ref`, `intent.objective` and `target_system` (the last is used only for compensation targeting), plus the R3/R4 list: `expires_at`, `roles`, `tenant`, `intent.expected_outcome_hash` (the frozen R2.0C intent carries the placeholder "PENDING"), predicate tautologies in the forward outcome contract, and the model hash inside an authorization phrase (requirement for the next freeze).

## 7. Defined but unused; single-send; trust boundary
Unchanged from R4 sections 5, 6 and 8: the unused schemas, one send per mission, and the trust boundary (consistency, not provenance; no signatures, an accepted gap).
