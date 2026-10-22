# MCR 3.0 Final Qualification and Release Gate R1

Candidate: `297a51f86035f1d3e1c266cd80a018cd483f8c87` (PR #5, DRAFT). Classification: **OFFLINE_QUALIFIED_BOUNDED_RESEARCH_RUNTIME** (not live-observed, not enterprise-proven, not production-qualified).

## Release gate: HOLD (research-candidate review may proceed: GO_WITH_DOCUMENTED_GAPS)
HOLD because three mandatory gates are not satisfied. No code defect caused the HOLD.

| Gate | Result | Basis |
|---|---|---|
| Offline suites | PASS | 1,644 checks, 10 suites, 0 failed (archived, unchanged) |
| Verifier attacks | PASS | 22/22 detected on this head, A13a-f all detected (`MCR3_VERIFIER_ATTACKS_FINAL_GATE_R1.json`) |
| CI matrix | PASS | `mcr3-offline` green on ubuntu and windows, push and pull_request, at the candidate SHA |
| Heavy (manual) tier | NOT RUN | not enforced as a release gate; no traceable result for this SHA |
| Mutation, `mcr3_model.py` (revocation, principal typing, expiry) | NOT COMPLETE | run (`--jobs 1`) stopped by the workstation low-memory guard before results; not restarted; tests-only coverage, no mutation PASS claimed |
| Mutation, `mcr3_scan.py` (history scan) | NOT RUN | |
| External checksum anchor | BLOCKED | repository variable `MCR3_SUMS_ANCHOR` is not set; the digest of SHA256SUMS_MCR3.txt computed from the GitHub-served file and the local checkout agree (BBEF1516...49B4) but no owner-held value exists, so this is not an independent anchor |
| Independent review | PARTIAL | fresh read-only agent, same model lineage (not independent); ruff 0.16.5 as the only independent tool; no critical or high finding |
| Frozen R1.9 / R2.0 | PASS | v1.9.0 still 9c5105f; additions-only diff |

## Review findings (VERIFIED_COUNTEREXAMPLE, executed by the reviewer; none critical or high; none fixed in this gate)
F1 `Mission.resume()` without `revocation_check` drops revocation silently (resumed mission can send). F2 `begin_compensation` does not consult revocation of the compensation grant. F3 `begin_compensation` does not check delegation expiry. F4 a NaN injected clock bypasses expiry in `Mission` and `CapabilityRegistry` (AdapterRegistry is correct). F5 `CapabilityRegistry.record_approval` has no version/digest binding (one approval covers other versions). F6/F7 history scan skips commit/tag messages, zip members, files named like binaries, content after 8 MiB. F8 scanner regex is quadratic (a 16 KB alphanumeric run took ~32 s; availability risk to CI). F9 scanner misses lowercase `Authorization: basic`, `MY_PASS=...`, `--password x`, `curl -u`, Slack webhook, Telegram token, bare AWS secret. F10 `scan_history_mcr3.py` on a non-git directory reports PASS. F11 `verify_mcr3.py --no-git`/shallow clone prints PASS with NOT_CHECKED items. F12 ledger restore plus a pre-send lease permits a second send (documented gap 3). F13 huge `expires_at` raises OverflowError (fails closed). F14 `RecordedApprovalVerifier` is id-only (test double). F15 some intent/provider fields not covered by relations.
Not proven: workflow action-SHA correctness (no network in the review), revocation-source hang/staleness, pip transitive pinning.

## Required before GO
1. Complete mutation on `mcr3_model.py` and `mcr3_scan.py` on a machine with free memory; close or explain survivors.
2. Owner sets `MCR3_SUMS_ANCHOR` (digest held outside the repository) and CI passes with it.
3. Run the heavy tier for the final SHA and make its result a required check.
4. Decide on F1-F5, F8, F10, F11 (recommended before any release claim: F1, F2, F4, F8, F10).
5. Review by a human or a different tool lineage.

Live and production claims remain NOT_ESTABLISHED. SAP writes: 0.
