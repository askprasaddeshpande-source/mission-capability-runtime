# MCR R2.0 Evidence Chain Contract R2

Supersedes R1 of this contract (retained). Source of truth: `tools/r2.0/mcr_r2_model.py` (`CHAIN_SLOTS`, `SLOT_KINDS`, `Mission._verify_chain`). Added after the independent review of `8a383b6`.

The 14-link order and emission rules are unchanged from R1. What changed is how COMPLETE validates the chain.

## COMPLETE guards (`Mission.complete`), in order
Any failure changes nothing (all guard methods are atomic).
1. The receipt is a `CompletionReceipt` and its own hash verifies.
2. The state is OUTCOME_VALIDATED.
3. All 15 required slots are present (the 13 upstream links plus the outcome and readback contracts), each of the expected kind and hash-valid.
4. Relational checks: delegation was issued to the principal; authority derives from the delegation, belongs to this mission and is attenuated; budget is bounded with no retries or expansion; the capability binding comes from this authority and is in its scope; transaction identity and mutation membership; the (authority, mutation) pair is in the replay set; outcome contract frozen and correlated; readback contract demands an authoritative source; checkpoint pins match the chain; execution receipt correlated with a post-send call class; readback correlated and produced under the frozen contract, source level AUTHORITATIVE_REPOSITORY, existence EXISTS; commit observation bound to that readback and COMMITTED; outcome receipt bound to the readback and the outcome contract with result PASS; predicates recomputed on the readback are PASS.
5. The completion receipt's authority, execution, commit and outcome hashes equal the mission's records, and its transaction id matches.
Malformed evidence yields a GuardError, never a partial state change.

## Continuation (`Mission.resume`)
Lease and checkpoint must be hash-valid, of the right kind and consistent with the consumed set; only pre-observation evidence may be re-presented; after any possible send the mission restarts in COMMIT_STATE_UNKNOWN and must obtain a fresh readback; a lease can never restore consumed authority or enlarge the budget.

## Trust boundary
Guards defend against malformed, forged or inconsistent evidence and logic errors. They do not defend against hostile code in the same process, and they verify **consistency, not provenance**: object hashes are not signatures, so a fully self-consistent forged chain that labels its readback authoritative is accepted. Authenticity requires signatures or an independent attested source (owner key decision, not part of this model).
