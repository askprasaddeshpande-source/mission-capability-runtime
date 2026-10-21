# MCR R2.0 Evidence Chain Contract R6

Supersedes R5 (retained). Source of truth: `tools/r2.0/mcr_r2_model.py`. Added after independent review 5 of `681f77a` (verdict PASS_WITH_GAPS, release gate GO_WITH_DOCUMENTED_GAPS). R5 stays in force except where this file changes it; R3's relation table gains R50 (R5) and R51 (this file), so there are 50 named relations (R01 to R51 without R21) plus the predicate-validity check.

## 1. Concurrency and the ledger (replaces R5 section 1)
- **One Mission object:** every guard method holds a per-Mission re-entrant lock for the whole call, so one thread's rollback cannot erase another thread's send.
- **The replay ledger, volatile or file-backed:** every operation on one `ReplayLedger` object (`has`, `for_authority`, `consume`, the file sync) is serialized by an in-process lock. Before this round the in-memory ledger did a check-then-add on a plain set and could double-send under threads (11 of 300 trials with 8 Mission objects) and leak `Set changed size during iteration`; both are fixed and tested (many eight-thread rounds, and writer/reader races).
- **Several Mission objects over one authority** are protected by the ledger they share: a file-backed ledger across threads and processes, an in-memory ledger across threads of one process only.
- `fail_before_mutation` refuses when the Mission's counter or the ledger shows a send.

## 2. Ledger construction (new)
A ledger path must be a non-empty string or `None`; `""`, non-strings and other falsy values raise `GuardError` (an empty path used to look durable while behaving as volatile). `expected_id` requires a file-backed ledger. `is_durable` is true only for a path-backed ledger; `resume()` refuses a volatile ledger unless explicitly waived.

## 3. Compensation: corrected wording (replaces the sentence in R5 section 3)
A grant whose goal predicates already hold on the forward readback is refused. This blocks a tautological goal and a clone that adds nothing relevant to the goal. It does **not** stop a post readback that equals the forward observed state plus a new field when the grant's goal is expressed on that new field (a field absent from the forward readback): there the goal is "not yet satisfied" before and "satisfied" after, so the compensation is accepted. This is the no-provenance class: the model verifies consistency of presented evidence, not that the compensation really happened.

## 4. Readback provider relation (new, R51)
The readback contract's `provider_ref` must start with the bound provider's `provider_id` followed by `::`. Checked at prewrite (so also on resume) and again by COMPLETE as relation R51. It ties the readback to the same provider system as the mutation; it does not tie it to the same tool (the frozen R2.0C study creates through one ADT tool and reads back through another).

## 5. Verifier scanner (describes the tool, not the model)
The secret scan covers every tracked file and zip member at every byte offset of the plausible encodings. It flags long and short secret values under secret-like names, private key blocks (including encrypted and PGP), GitHub, AWS and Slack token shapes and URL user-info. Exemptions are narrow: names that contain a whole hash/digest word or end in a count/identifier word (so `account_password` and `client_secret_silent` are NOT exempt), upper-snake enumeration labels, code calls, file-name keys and a short placeholder list. **Residual limits:** it cannot find a secret that looks like none of these shapes (for example a short value under an innocuous name); an UPPER_SNAKE value or a value followed by an opening parenthesis is treated as non-secret; it is a heuristic, not proof of absence.

## 6. Everything else
Sections 2 to 8 of R4 and sections 4 to 7 of R5 (ledger identity and limits, resume trusts lease plus ledger, unenforced fields including `readback.activation`, `readback_contract.checks`, `intent.objective`, defined-but-unused schemas, single-send missions, trust boundary and no signatures) are unchanged.
