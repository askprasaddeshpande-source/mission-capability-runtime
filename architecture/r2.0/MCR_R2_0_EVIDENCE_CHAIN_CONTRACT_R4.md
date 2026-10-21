# MCR R2.0 Evidence Chain Contract R4

Supersedes R3 (retained). Source of truth: `tools/r2.0/mcr_r2_model.py`. Added after independent review 3 of `a381a22` (verdict HOLD). R3 sections 1 (per-gate verification), 3 (COMPLETE re-verifies the chain) and the relation table remain in force, with the additions below (relation R50 and stricter types).

## 1. A resumed mission is held to exactly the checks a fresh one gets
`Mission.resume()` no longer rebuilds state by copying evidence into place. It verifies the lease, checkpoint and original budget (kind, hash, mutual consistency), accepts only pre-observation evidence and requires ALL of intent, principal, delegation, capability, provider, transaction, budget, outcome contract, readback contract and authority, then **re-runs the real guard methods** `context_ready`, `authorize`, `bind` and `prewrite_validate` on them. The only relaxation is that `authorize` does not refuse an authority that the ledger already shows as consumed (that is the point of resuming). Anything the normal path refuses (unfrozen contract, retries or expansion, a non-single-use authority, a wider scope, a mismatched capability, a missing delegation, a foreign mission, a float checkpoint budget...) is refused on resume with the same message. Consumption is then the union of the lease and the ledger; after any possible send the mission restarts in COMMIT_STATE_UNKNOWN and needs a fresh readback. `resume()` requires a durable (file-backed) ledger unless `allow_volatile_ledger=True` (tests only).

## 2. The replay ledger: what it guarantees and what it does not
`ReplayLedger(path)` is an append-only file of JSON lines `{"a": authority hash, "m": mutation id, "c": crc}`.
**Guarantees (one local filesystem with working file locks):**
- every `consume`, `has` and `for_authority` takes an OS file lock and re-reads the file, so entries written by other processes or other ledger objects on the same file are seen; two processes racing to consume the same key: exactly one wins (tested with four real processes);
- `consume(key, limit)` refuses a send once `limit` sends are recorded for the authority, across missions and processes (the limit is the budget's `max_mutations`), so two missions sharing one single-use authority cannot both send, even with different mutation ids;
- the record is flushed and fsynced before `consume` returns, and the send happens only after; a failed write blocks the send and changes no mission state;
- ids may contain colons and unicode; control characters (including CR, LF, tab, NUL, DEL) are rejected; JSON escaping and the CRC keep the format intact;
- a torn final line (crash mid-write) is ignored and truncated before the next append (no send followed it); a corrupt or checksum-failing complete line, or non-UTF-8 content, **fails closed** with a GuardError;
- the ledger is not rolled back by a failed guard call: a recorded send stays recorded.
**Does not guarantee:** protection when callers use different ledger files; a volatile (`path=None`) ledger across processes; network filesystems without working locks; durability across power loss on hardware that ignores fsync (not tested); POSIX behaviour (tested only on Windows with `msvcrt`; the `fcntl` path is untested). The frozen R2.0C runner uses its own lock file, not this ledger. A deployment must pass one durable ledger to every Mission and every resume.

## 3. Compensation is gated like the forward path and is itself a send
`authorize_compensation` needs: verified grant; no inheritance and not issued from forward authority; a capability outside the forward scope; predicate preconditions and goals that are valid; a forward readback that is present **and authoritative**; preconditions that PASS against it (so there is something to compensate). `begin_compensation` consumes a ledger entry bound to the grant (limit: the grant's budget) before the compensating call, once only. `record_compensation(receipt, post_readback, execution_receipt)` needs: a begun compensation; an execution receipt bound to the grant (`COMPENSATION:<grant hash>`, post-send call class, same transaction); a receipt bound to the grant; a post readback that is authoritative, correlated to the mission and readback contract, internally consistent, **distinct from the forward readback in hash and observed state**, and that satisfies the goal. A resumed mission cannot continue a compensation (it restarts in COMMIT_STATE_UNKNOWN).

## 4. Types and consistency
Counts (delegation, authority, budget, checkpoint budget, lease budget) must be real non-negative integers (no bool, float, NaN); `single_use` and `frozen` must be exactly `True`; `expansion_allowed` exactly `False`; `retries` the integer 0. A readback's `existence` must agree with `observed.exists` when that field is present and the existence is not UNKNOWN (gate check and relation R50). Malformed arguments of the wrong type become GuardError and leave the mission unchanged.

## 5. Single-send missions
The state machine allows one EXECUTION_STARTED per mission. A budget above 1 does not enable multiple sends; multi-mutation missions need a state-machine extension that this lineage has not made.

## 6. Defined but unused
`ReplayGuard`, `ContractLease`, `GovernanceTelemetry`, `EvidenceEnvelope` and `OutcomePredicate` exist as object schemas for the architecture and the telemetry test but are not consumed by `Mission`.

## 7. Not enforced (unchanged from R3, plus one)
`expires_at`, `roles`, `tenant`, `intent.expected_outcome_hash` (the frozen R2.0C intent carries the placeholder "PENDING"), predicate tautologies, and the model hash inside an authorization phrase (requirement for the next freeze).

## 8. Trust boundary (unchanged)
Guards defend against malformed, forged or inconsistent evidence and logic errors, not against hostile code in the same process. They verify consistency, not provenance: a fully self-consistent forged chain that labels its readback authoritative is accepted. Lease authenticity has the same limit. Signing was declined by the owner and is an accepted, disclosed gap.
