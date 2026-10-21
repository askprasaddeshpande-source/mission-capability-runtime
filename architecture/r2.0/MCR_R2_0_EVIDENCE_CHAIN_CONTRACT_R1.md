# MCR R2.0 Evidence Chain Contract R1

Source of truth: `CHAIN_SLOTS` / `EXPECTED_CHAIN` in `tools/r2.0/mcr_r2_model.py`; derived from the live-mission chain in the R2.0 mission specification (section 19). Added by R2.0G; it clarifies the contract and does not change the R2.0A architecture.

## The chain has 14 links, in this order
1 MISSION_INTENT, 2 PRINCIPAL_CONTEXT, 3 DELEGATION, 4 AUTHORITY, 5 CAPABILITY_BINDING, 6 PROVIDER_CONTRACT, 7 MUTATION_BUDGET, 8 TRANSACTION, 9 PREWRITE_CHECKPOINT, 10 EXECUTION_RECEIPT, 11 COMMIT_OBSERVATION, 12 AUTHORITATIVE_READBACK_RECEIPT, 13 OUTCOME_RECEIPT, **14 COMPLETION_RECEIPT**.

Links 1-13 are the "upstream" chain; link 14 is created only at COMPLETE.

## Emission rules
- `chain_hashes()` emits only links that exist, in contract order. A non-complete mission never emits link 14. A COMPLETE mission emits all 14 and the last is the CompletionReceipt hash.
- A mission that stops earlier emits fewer links (examples observed in the synthetic scenarios: 11 after an ABSENT or UNKNOWN readback, 13 after a failed outcome predicate).

## COMPLETE guards (`Mission.complete`)
Evaluated in this order; any failure leaves the state unchanged and persists nothing:
1. the receipt is a `CompletionReceipt` and its own hash verifies;
2. all 13 upstream links are present;
3. every upstream link's hash verifies (tamper check);
4. the receipt's authority, execution, commit and outcome hashes equal the mission's recorded objects;
5. the state is OUTCOME_VALIDATED (so commit, authoritative readback and predicate PASS were already established);
6. the receipt's `transaction_id` equals the mission's transaction.
Only then the state moves to COMPLETE and the receipt is stored as link 14.

## Correlation
Every receipt carries `transaction_id` (and mutation id where relevant); downstream receipts carry the hash of the upstream object they rely on. Correlation is by identifier and hash, not by time. The schemas are unchanged by R2.0G; `CompletionReceipt` has no separate `mission_id` field and is tied to the mission through its transaction id and the upstream hashes (a documented limit).

## Historical note
The R2.0C live run (2026-10-20) was executed with the model revision before this contract was enforced; it emitted links 1-13 and did not emit link 14. That record is frozen. See `reports/r2.0/MCR_R2_0_C_REPORT_ERRATUM_R1.md`.
