# MCR R2.0 Evidence Chain Contract R7

Supersedes R6 (retained). Source of truth: `tools/r2.0/mcr_r2_model.py`. Added after independent review 6 of `212804f` (verdict GO_WITH_DOCUMENTED_GAPS). R6 stays in force except where this file changes or sharpens it. The relation table is unchanged (50 named relations plus the predicate-validity check).

## 1. Ledger path validation (extends R6 section 2)
A ledger path containing a NUL character, or any path component whose base name (the part before the first dot, trailing spaces ignored, case-insensitive) is a Windows device name (`CON`, `PRN`, `AUX`, `NUL`, `COM1`-`COM9`, `LPT1`-`LPT9`), raises `GuardError`. The rule applies on every platform. Names that merely resemble a device name (`console.txt`, `CONFIG`, `com10.txt`) are accepted. `_io_guard` now also turns `ValueError` and `TypeError` raised by file operations into `GuardError`, so no ledger call leaks a raw exception.

## 2. Readback provider relation, exact meaning (sharpens R6 section 4)
R51 is a literal prefix test: `provider_ref` must start with `<provider_id>::`. By design it therefore **accepts** an empty tail (`SYN::`), an empty `provider_id` with a `::` prefix, and a provider id that is itself the prefix of a longer reference (`SYN` matches `SYN::A::x`). It **refuses** `SYNX::...`, a reference without the separator, and a case difference. It binds the readback to the same provider system, not to a particular tool or object.

## 3. Failed compensating call (new wording)
After `begin_compensation`, a compensating call whose execution receipt does not report `PROVIDER_RESPONSE_SUCCESS` is refused by `record_compensation`; the mission stays in `COMPENSATION_AUTHORIZED` and nothing is recorded. `begin_compensation` is once-only, so the ledger permits exactly one recorded start. The model does **not** limit how many times a caller actually invokes the provider afterwards, and a later success report is accepted. The only exits of `COMPENSATION_AUTHORIZED` are `COMPENSATED` and `UNRECOVERABLE`. A second provider call after a failed first one is therefore outside the model's single-send guarantee; a deployment that needs it limited must enforce that itself.

## 4. Verifier scanner: shapes added and intentionally unsupported patterns (extends R6 section 5)
Added token shapes: `github_pat_` fine-grained tokens, `npm_` tokens, `AIza` API keys, Stripe `sk_live_` and `rk_live_` keys, and Azure `AccountKey=` values. Synthetic payloads for each are in the test matrix.
Intentionally **not** detected (documented limits, not claimed as covered):
- a short (under 16 characters) value under a `token` or `authorization` name, because such names are too often identifiers;
- a quoted password containing spaces;
- obfuscated or transformed secrets: zero-width characters, homoglyphs, base64 or URL-encoded wrappers, values split across lines or strings;
- any secret that matches none of the shapes above.
The scan is a heuristic and is not proof that the tree holds no secret.

## 5. Concurrency test method (new)
The ledger's thread safety is checked two ways. A stress run uses a spy key set that pauses inside every operation and records any overlap of threads. Four rendezvous tests are deterministic: a first thread is held inside `add` until a second thread (`consume`, `has` or `for_authority`) reaches the set or 0.4 s pass, so removing the in-process lock gives an assertion failure every time, not a timing-dependent one. Removing the lock body, or the lock decorator from `has`, `for_authority` or `consume`, is a named mutant (all four caught by assertion in three repeated probes). The decorators on `_consume_file` and `_sync` are defence in depth: both run under the OS file lock and behind a locked caller, so their removal is observable only through timing. They have **no mutant and no test**, and that is stated here rather than claimed as covered.

## 6. Everything else
R6 sections 1, 2 (apart from section 1 above), 3, 5 residual limits and everything R6 section 6 carries forward are unchanged.
