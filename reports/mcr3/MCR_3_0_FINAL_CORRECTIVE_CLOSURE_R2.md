# MCR 3.0 Final Corrective Closure R2

Classification: **OFFLINE_QUALIFIED_BOUNDED_RESEARCH_RUNTIME** (not live-observed, not enterprise-proven, not production-qualified). No hypothesis promoted. SAP writes 0.

Supersedes the gate table in `MCR_3_0_FINAL_QUALIFICATION_GATE_R1.md` (written at `6828101`). That report's attack evidence was taken at the candidate `297a51f`; the evidence here is for the code commit `311d566`.

## Release gate: HOLD (single remaining blocker: external checksum anchor)
| Gate | Result | Basis |
|---|---|---|
| Offline suites | PASS | 1,777 checks in 11 suites, 0 failed (local), reproduced by `mcr3-offline` CI on ubuntu and windows, push and pull_request |
| Mutation, all 11 targets (incl. `mcr3_model.py`, `mcr3_scan.py`, `mcr3_authority.py`) | PASS | CI run 39767965983 on `311d566`; 1,743 mutants: 973 assertion detections, 725 validator-crash detections, 1 hang (a detection), 44 explained survivors (equivalent mutants with reasons), **0 unexplained, 0 inconclusive, 0 not applied** |
| Verifier attacks | PASS | 25 scenarios, `all_passed` true, attacked `311d566`; A13a-A13f included; N1-N3 (verdict honesty) added |
| External checksum anchor | **BLOCKED** | repository variable `MCR3_SUMS_ANCHOR` is not set; the gate's `anchor` job fails with `BLOCKED_EXTERNAL_ANCHOR`, so the `release gate` check is red. Not claimed as a pass. |
| Heavy gate enforced | PASS (mechanism) | `mcr3-release-gate.yml` runs on every push to `work/mcr3*`; the `release gate` job fails unless mutation, attacks and anchor jobs each report `success` (skipped is a failure) and `check_release_gate.py` accepts the artifacts for exactly the commit; branch protection is NOT configured (owner action: require the check `release gate`) |
| Frozen R1.9 / R2.0 | PASS | v1.9.0 unchanged (9c5105f); additions-only diff against the R2.0 baseline; `verify_mcr3.py` full run `PASS_WITHOUT_EXTERNAL_ANCHOR` |
| Independent review | PARTIAL | two isolated reviewers of the SAME model lineage as the implementer (not independent); ruff and mypy were the only independent tools (bandit, semgrep, pyflakes absent) |

## Verified defects repaired (each with a regression test; the corrective tests that could run on the pre-repair code failed there, 29 of 34, the rest being controls)
- **B1** `Mission.resume` dropped revocation: the lease now records `revocation_required`; resume without a callable source is refused when the lease requires it or does not say. Residual: the flag is hash-checked, not authenticated (a forged re-sealed lease can claim `False`).
- **B2** compensation did not check grant revocation or delegation expiry: both are now checked before any ledger entry.
- **B3** NaN/inf/negative/non-numeric/raising/huge-integer clocks and huge expiry values are refused consistently in `Mission`, `CapabilityRegistry` and `AdapterRegistry` (`valid_time`).
- **B4** `CapabilityRegistry` approvals bind capability version, digest, qualification digest and target state; one approval can no longer approve another version.
- **B5** scanner: secret-name detection is keyword-anchored and linear (256 KB adversarial input about 1 s, previously minutes); values bounded to 256; new shapes (lowercase Basic, Slack webhook, Telegram bot token, `--password` flags, `curl -u`, `MY_PASS=`, quoted phrases); no file-name based skipping; ZIPs opened by content with unreadable members reported; commit and tag messages scanned; oversize content reported (`unscanned_oversize`).
- **B6** a non-Git directory, a sub-folder, a shallow clone or a clone with a missing object can no longer give a successful scan (`ScanError`, CLI exit 2).
- **B7** `verify_mcr3.py`: any mandatory `NOT_CHECKED` prevents PASS; no anchor gives `BLOCKED_EXTERNAL_ANCHOR` (or `PASS_WITHOUT_EXTERNAL_ANCHOR` only with `--allow-no-anchor`); a missing or malformed `--expect-sums-sha256` value fails; `--require-clean` demands a clean tree.
- **B8** ledger rollback on resume: resume on a durable ledger needs `trusted_anchor` (an anchor recorded after the last send in a store the ledger host cannot rewrite), or an explicit `allow_unanchored_ledger=True` accepting the replay risk. Verified: a restored ledger is caught by the trusted anchor.

## Reviewer findings from the second review (counterexamples executed by the reviewer)
Fixed: F1 scanner still quadratic (high), F2 unreadable ZIP member discarded other findings, F5 shallow clone passed, F9 truthy string accepted as opt-out, F11/F12 AdapterRegistry clock and huge-integer clock, F14 gate had no floor on mutation evidence, F6 gate used `--fast` (it now runs the validators and a full verification).
Documented, not fixed: F3/F4 scanner misses (nested or prefixed ZIP, gzip, XML `<password>`, `.netrc`, `DBPASS=`, `mysql -p`, short quoted values, `Authorization: Basic` with a short token); F7 `--require-clean` is opt-in; F8 forged lease can claim `revocation_required=False`; F10 a caller can pass the lease's own anchor as `trusted_anchor` (the policy is advisory unless the anchor really comes from outside); F13 approvals carry no policy-epoch binding; gate workflow is push-only on `work/mcr3*`, the mutation runner has no unmutated baseline run.

## Ledger replay status
Prevented: a second send from the same ledger within a process or across processes (tested earlier, including concurrent writers), a truncated or rewritten ledger **when an independent anchor is supplied**. NOT prevented: restoring an older ledger copy and resuming with an honest pre-send lease, unless `trusted_anchor` really comes from a store the ledger host cannot rewrite. Configurations that cannot supply one are blocked by default and can only proceed with an explicit opt-out.

## Not covered
- `verify_mcr3.py`, the two workflows and `check_release_gate.py` are not mutation-tested; the verifier is covered by the attack suite only.
- 42% of detections are validator crashes (725 of 1,698), not targeted assertions.
- POSIX ledger behaviour is tested only on a hosted runner's local disk; network filesystems and power loss are untested.
- Principal identity is self-reported; revocation is enforced only when a source is connected; no real revocation service, signing authority or Governor exists; Claude Mods, ACLA, EAF only through mocks; SAP-style readback rules not verified live.
- The previously disclosed ADT bearer token remains exposed until the owner rotates it; nothing authenticated was attempted.

## Owner actions needed
1. Set repository variable `MCR3_SUMS_ANCHOR` to the SHA-256 of `evidence/mcr3/SHA256SUMS_MCR3.txt` as held outside the repository (value printed in the PR description) and re-run the gate; configure branch protection to require `release gate`.
2. Obtain a review from a human or a different tool lineage.
3. Rotate the exposed ADT token before any live work; decide on a live study separately.
4. PR #5 remains DRAFT; promotion, merge or release only by separate owner approval.

Heavy-gate artifacts for `311d566`: `evidence/mcr3/heavy_311d566/`. Run: https://github.com/askprasaddeshpande-source/mission-capability-runtime/actions/runs/39767965983
