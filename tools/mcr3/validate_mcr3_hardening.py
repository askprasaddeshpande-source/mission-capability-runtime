"""MCR 3.0 hardening validator: tests for behaviour that is NEW in the 3.0 model (ledger path forms, expiry,
outcome-hash and readback-check enforcement, activation predicates, bounded compensation attempts, outcome
classification, structural lock invariant). Stdlib only, offline. Output: JSON on stdout (same shape as the
inherited validator): {"tests": n, "failed": [...], "groups": {...}}.
"""
import ast
import hashlib
import json
import os
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
if os.environ.get("MCR3_OVERRIDE_DIR"):          # mutation harness: a mutated module shadows the real one
    sys.path.insert(0, os.environ["MCR3_OVERRIDE_DIR"])
import mcr3_model as MODEL  # noqa: E402
from mcr3_model import GuardError, Mission, make, eval_predicates  # noqa: E402
import validate_mcr3_inherited as INH  # noqa: E402
from validate_mcr3_inherited import (FP, GOOD_OBS, PREDS, comp_exec, commit_obs, exec_receipt, fixture, happy,  # noqa: E402
                                     outcome, raises, rb_receipt, safe, to_prewrite)

T, G = {}, {}
Z = "Z" * 64


def t(group, name, ok):
    try:
        ok = ok() if callable(ok) else ok
    except Exception:
        ok = False
    T[name] = bool(ok)
    G.setdefault(group, []).append(name)


def remake(obj, **chg):
    body = {k: v for k, v in obj.items() if k not in ("kind", "object_hash")}
    body.update(chg)
    return make(obj["kind"], **body)


def fixed_clock(value):
    box = {"now": value}
    return (lambda: box["now"]), box


def mission_with(f, clock=None, max_mut=1):
    m = Mission("M-SYN-1", "TX-SYN-1", max_mut, clock=clock)
    return m


PRE = [{"field": "exists", "op": "eq", "expected": True}]
GOAL = [{"field": "exists", "op": "eq", "expected": False}]


def grant_of(**k):
    return make("CompensationGrant", **dict(dict(grant_id="g1", target="SYN_SYS", capability="delete_object", max_mutations=1,
                                                 preconditions=PRE, outcome_predicates=GOAL, inherits_forward_authority=False,
                                                 issued_by="OWNER2"), **k))


def comp_ready(max_mut_for_forward=1):
    """A mission whose outcome validation failed (COMPENSATION_REQUIRED) on an authoritative forward readback."""
    mm, ff = fixture()
    to_prewrite(mm, ff); mm.begin_execution("MUT-1", FP); mm.record_execution(exec_receipt(ff)); mm.request_readback()
    obs = dict(GOOD_OBS, package="WRONG")
    rbo = rb_receipt(ff, obs=obs); mm.observe_readback(rbo); mm.decide_commit(commit_obs(rbo, "COMMITTED"))
    mm.validate_outcome(outcome(ff, rbo, eval_predicates(PREDS, obs)))
    return mm, ff


def comp_mission(max_attempts, ledger=None):
    mm, ff = comp_ready()
    if ledger is not None:
        mm.ledger = ledger
    gg = grant_of(max_mutations=max_attempts)
    mm.authorize_compensation(gg)
    return mm, ff, gg


def post_receipt(ff, existence="ABSENT", obs=None, rid="post"):
    r = rb_receipt(ff, existence, obs=obs if obs is not None else {"exists": False})
    return remake(r, receipt_id=rid)


def comp_receipt(gg, post, res="PASS"):
    return make("CompensationReceipt", receipt_id="cr1", grant_hash=gg["object_hash"], readback_receipt_hash=post["object_hash"], result=res)


def run():
    # ---------------------------------------------------------------- ledger path forms (G01)
    g = "LEDGER_PATH_FORMS"
    d = tempfile.mkdtemp(prefix="m3path_")
    bad = [("nul_char", "led\x00ger.txt"), ("control_char", "led\x01ger.txt"), ("tab", "a\tb"), ("bare_con", "CON"), ("con_ext", "con.txt"),
           ("con_colon", "CON:"), ("conin", "CONIN$"), ("conout_ext", "CONOUT$.log"), ("nul_stream", "NUL:stream"),
           ("file_stream", "ledger.txt:aux"), ("stream_in_dir", os.path.join(d, "x.txt:s")), ("drive_relative", "C:ledger.txt"),
           ("com0", "COM0"), ("com9_ext", "COM9.x"), ("lpt1_dir", d + "/LPT1/x"), ("superscript_com", "com\u00b9.txt"),
           ("superscript_lpt", "LPT\u00b2"), ("fullwidth_con", "\uff23\uff2f\uff2e"), ("trailing_space", "CON "), ("trailing_dot_name", "ledger."),
           ("trailing_space_name", "ledger.txt "), ("parent_dir", d + "/../x.txt"), ("question_mark", "\\\\?\\C:\\x"), ("star", "a*b"),
           ("pipe", "a|b"), ("angle", "a<b"), ("quote", 'a"b'), ("too_long", "a" * 5000), ("empty", ""), ("int", 5), ("bytes", b"x"), ("bool", False)]
    for label, path in bad:
        t(g, "ledger_path_" + label + "_is_a_guard_error", raises(lambda p=path: MODEL.ReplayLedger(p)))
    good = ["console.txt", "CONFIG", "aux_ledger.txt", "com10.txt", "LPT10.log", "my.ledger.txt", "a b.txt", os.path.join(d, "ok.txt"), d.replace("\\", "/") + "/ok2.txt"]
    for gi, p in enumerate(good):
        t(g, "legal_ledger_path_accepted_%d" % gi, safe(lambda p=p: MODEL.ReplayLedger(os.path.join(d, os.path.basename(p)) if not os.path.isabs(p) else p) is not None))
    t(g, "no_stray_file_was_created_by_a_refused_path", lambda: (not [n for n in os.listdir(os.getcwd()) + os.listdir(d) if n.upper().split(".")[0] in ("CON", "NUL", "PRN", "AUX", "CONIN$", "CONOUT$", "COM0", "COM9", "LPT1") or ":" in n or n in ("ledger.", "x.txt:s")]))
    t(g, "io_guard_turns_value_and_type_errors_into_guard_errors",
      raises(lambda: MODEL._io_guard(lambda: (_ for _ in ()).throw(ValueError("embedded null byte")))(), "ledger I/O error: ValueError")
      and raises(lambda: MODEL._io_guard(lambda: (_ for _ in ()).throw(TypeError("x")))(), "ledger I/O error: TypeError"))
    t(g, "io_guard_leaves_guard_errors_alone", lambda: (raises(lambda: MODEL._io_guard(lambda: (_ for _ in ()).throw(GuardError("keep me")))(), "keep me")))

    # structural lock invariant (G04): the private file methods are only reached from locked methods or the constructor
    src = open(os.path.join(HERE, "mcr3_model.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    led = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ReplayLedger")
    def decorated_locked(fn):
        return any(isinstance(x, ast.Name) and x.id == "_tlocked" for x in fn.decorator_list)
    callers = {}
    for fn in [n for n in led.body if isinstance(n, ast.FunctionDef)]:
        for c in ast.walk(fn):
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr in ("_sync", "_consume_file", "_load", "_admit"):
                callers.setdefault(c.func.attr, set()).add((fn.name, decorated_locked(fn)))
    allowed = {"__init__", "_consume_file", "_sync", "_load"}
    ok = all(locked or name in allowed for ws in callers.values() for name, locked in ws)
    t(g, "private_ledger_methods_are_called_only_under_the_in_process_lock", lambda: (ok and callers))
    t(g, "private_file_methods_are_not_separately_decorated", lambda: (not any(decorated_locked(fn) for fn in led.body if isinstance(fn, ast.FunctionDef) and fn.name in ("_sync", "_consume_file"))))

    # ---------------------------------------------------------------- expiry (G06)
    g = "EXPIRY"
    pe = MODEL.parse_expiry
    t(g, "parse_expiry_accepts_date_datetime_z_and_utc_offset_and_numbers",
      all(pe(x) is not None for x in ("2099-01-01", "2099-01-01T00:00:00Z", "2099-01-01T00:00:00+00:00", "2099-01-01T00:00:00.250Z", 4102444800, 4102444800.5, 0)))
    t(g, "parse_expiry_refuses_junk", lambda: (all(pe(x) is None for x in ("x", "", "2099-13-01", "2099-01-01T00:00:00", "2099-01-01T00:00:00+02:00", True, False, None, [], float("nan"), float("inf"), -1, "99-01-01", b"2099-01-01"))))
    t(g, "parse_expiry_values_agree", lambda: (pe("2099-01-01") == pe("2099-01-01T00:00:00Z") == pe("2099-01-01T00:00:00+00:00")))
    clock, box = fixed_clock(pe("2099-01-01") - 100)
    mm, ff = fixture()
    mm = Mission("M-SYN-1", "TX-SYN-1", 1, clock=clock)
    mm.context_ready(ff["intent"], ff["pr"])
    t(g, "authorize_accepts_an_unexpired_delegation", lambda: (safe(lambda: (mm.authorize(ff["dl"], ff["au"], ff["bu"]), mm.state)[1] == "AUTHORIZED")))
    mm.bind(ff["cb"], ff["pb"]); mm.prewrite_validate(ff["tx"], ff["oc"], ff["rc"], ff["cp"])
    box["now"] = pe("2099-01-01") + 1
    t(g, "send_is_refused_when_the_delegation_expired_after_authorization", lambda: (raises(lambda: mm.begin_execution("MUT-1", FP), "delegation expired") and mm.state == "PREWRITE_VALIDATED" and not mm.ledger.for_authority(ff["au"]["object_hash"])))
    box["now"] = pe("2099-01-01")
    t(g, "expiry_instant_itself_counts_as_expired", lambda: (raises(lambda: mm.begin_execution("MUT-1", FP), "delegation expired")))
    mm2, ff2 = fixture(); mm2 = Mission("M-SYN-1", "TX-SYN-1", 1, clock=lambda: pe("2099-01-01") + 5)
    mm2.context_ready(ff2["intent"], ff2["pr"])
    t(g, "authorize_refuses_an_expired_delegation", lambda: (raises(lambda: mm2.authorize(ff2["dl"], ff2["au"], ff2["bu"]), "delegation expired") and mm2.state == "CONTEXT_READY"))
    for label, val in (("junk_string", "x"), ("bool", True), ("naive_datetime", "2099-01-01T00:00:00"), ("offset", "2099-01-01T00:00:00+02:00"), ("negative", -5), ("nan", float("nan"))):
        mm3, ff3 = fixture(); dl3 = remake(ff3["dl"], expires_at=val)
        au3 = remake(ff3["au"], delegation_hash=dl3["object_hash"]); bu3 = remake(ff3["bu"], authority_hash=au3["object_hash"])
        mm3.context_ready(ff3["intent"], ff3["pr"])
        t(g, "authorize_refuses_expires_at_" + label, raises(lambda mm3=mm3, dl3=dl3, au3=au3, bu3=bu3: mm3.authorize(dl3, au3, bu3), "not a valid UTC time"))
    t(g, "a_non_callable_clock_is_refused", lambda: (raises(lambda: Mission("M", "T", 1, clock=5), "clock must be callable")))
    ok_epoch = remake(ff["dl"], expires_at=4102444800)
    au4 = remake(ff["au"], delegation_hash=ok_epoch["object_hash"]); bu4 = remake(ff["bu"], authority_hash=au4["object_hash"])
    mm4 = Mission("M-SYN-1", "TX-SYN-1", 1); mm4.context_ready(ff["intent"], ff["pr"])
    t(g, "epoch_number_expiry_is_accepted", lambda: (safe(lambda: (mm4.authorize(ok_epoch, au4, bu4), mm4.state)[1] == "AUTHORIZED")))

    # ---------------------------------------------------------------- outcome hash / readback checks / activation (G06)
    g = "BINDING_FIELDS"
    mm, ff = fixture()
    mm.context_ready(remake(ff["intent"], expected_outcome_hash=Z), ff["pr"]); mm.authorize(ff["dl"], ff["au"], ff["bu"]); mm.bind(ff["cb"], ff["pb"])
    t(g, "prewrite_refuses_an_intent_that_names_another_outcome_contract", lambda: (raises(lambda: mm.prewrite_validate(ff["tx"], ff["oc"], ff["rc"], ff["cp"]), "expected_outcome_hash") and mm.state == "BOUND"))
    for label, chk in (("empty", []), ("duplicates", ["exists", "exists"]), ("non_string", ["exists", 3]), ("empty_name", [""]), ("string", "exists"), ("none", None)):
        mm, ff = fixture(); mm.context_ready(ff["intent"], ff["pr"]); mm.authorize(ff["dl"], ff["au"], ff["bu"]); mm.bind(ff["cb"], ff["pb"])
        rc = remake(ff["rc"], checks=chk); cp = remake(ff["cp"], readback_contract_hash=rc["object_hash"])
        t(g, "prewrite_refuses_readback_checks_" + label, raises(lambda mm=mm, ff=ff, rc=rc, cp=cp: mm.prewrite_validate(ff["tx"], ff["oc"], rc, cp), "checks must be"))

    def committed_with(checks, obs):
        mm, ff = fixture(); mm.context_ready(ff["intent"], ff["pr"]); mm.authorize(ff["dl"], ff["au"], ff["bu"]); mm.bind(ff["cb"], ff["pb"])
        rc = remake(ff["rc"], checks=checks); cp = remake(ff["cp"], readback_contract_hash=rc["object_hash"]); ff2 = dict(ff, rc=rc, cp=cp)
        mm.prewrite_validate(ff["tx"], ff["oc"], rc, cp); mm.begin_execution("MUT-1", FP); mm.record_execution(exec_receipt(ff2)); mm.request_readback()
        rb = rb_receipt(ff2, obs=obs); mm.observe_readback(rb)
        return mm, ff2, rb
    mm, ff2, rb = committed_with(["exists", "package"], GOOD_OBS)
    t(g, "a_readback_with_every_required_check_can_commit", lambda: (mm.decide_commit(commit_obs(rb, "COMMITTED")) == "COMMITTED"))
    mm, ff2, rb = committed_with(["exists", "package", "owner"], GOOD_OBS)
    t(g, "a_missing_required_check_leaves_the_commit_unknown", lambda: (mm.decide_commit(commit_obs(rb, "COMMITTED")) == "COMMIT_STATE_UNKNOWN" and "commit" not in mm.ev))
    mm, ff2, rb = committed_with(["exists", "package"], dict(GOOD_OBS, package="UNKNOWN"))
    t(g, "a_required_check_with_an_unknown_value_leaves_the_commit_unknown", lambda: (mm.decide_commit(commit_obs(rb, "COMMITTED")) == "COMMIT_STATE_UNKNOWN"))
    mm, ff2, rb = committed_with(["exists", "package"], dict(GOOD_OBS, package=None))
    t(g, "a_required_check_with_a_null_value_leaves_the_commit_unknown", lambda: (mm.decide_commit(commit_obs(rb, "COMMITTED")) == "COMMIT_STATE_UNKNOWN"))
    mm2, ffx = fixture(); mm2.context_ready(ffx["intent"], ffx["pr"]); mm2.authorize(ffx["dl"], ffx["au"], ffx["bu"]); mm2.bind(ffx["cb"], ffx["pb"])
    rcx = remake(ffx["rc"], checks=["exists", "package"]); cpx = remake(ffx["cp"], readback_contract_hash=rcx["object_hash"]); ffx2 = dict(ffx, rc=rcx, cp=cpx)
    mm2.prewrite_validate(ffx["tx"], ffx["oc"], rcx, cpx); mm2.begin_execution("MUT-1", FP); mm2.record_execution(exec_receipt(ffx2)); mm2.request_readback()
    rba = rb_receipt(ffx2, "ABSENT", obs={"exists": False}); mm2.observe_readback(rba)
    t(g, "an_authoritative_absent_readback_is_not_blocked_by_missing_checks", lambda: (mm2.decide_commit(commit_obs(rba, "ABSENT")) == "FAILED_AFTER_POSSIBLE_MUTATION"))

    # activation pseudo-field
    act_preds = [{"field": "exists", "op": "eq", "expected": True}, {"field": "$activation", "op": "eq", "expected": "ACTIVE"}]
    def outcome_for(activation, preds=act_preds):
        mm, ff = fixture()
        oc = make("ExpectedOutcomeContract", outcome_contract_id="oc-act", mission_id="M-SYN-1", transaction_id="TX-SYN-1", predicates=preds, frozen=True)
        intent = remake(ff["intent"], expected_outcome_hash=oc["object_hash"])
        cp = remake(ff["cp"], outcome_contract_hash=oc["object_hash"])
        ff = dict(ff, oc=oc, intent=intent, cp=cp)
        to_prewrite(mm, ff); mm.begin_execution("MUT-1", FP); mm.record_execution(exec_receipt(ff)); mm.request_readback()
        rb = remake(rb_receipt(ff, obs=GOOD_OBS), activation=activation)
        mm.observe_readback(rb); mm.decide_commit(commit_obs(rb, "COMMITTED"))
        res = eval_predicates(preds, MODEL.observed_view(rb))
        mm.validate_outcome(make("OutcomeReceipt", receipt_id="or-act", transaction_id="TX-SYN-1", readback_receipt_hash=rb["object_hash"], outcome_contract_hash=oc["object_hash"], result=res))
        return mm, res
    mm, res = outcome_for("ACTIVE"); t(g, "an_active_readback_satisfies_an_activation_predicate", res == "PASS" and mm.state == "OUTCOME_VALIDATED")
    mm, res = outcome_for("INACTIVE"); t(g, "an_inactive_readback_fails_an_activation_predicate", res == "FAIL" and mm.state == "COMPENSATION_REQUIRED")
    mm, res = outcome_for("UNKNOWN"); t(g, "an_unknown_activation_never_passes_an_activation_predicate", res == "UNKNOWN" and mm.state == "OUTCOME_VALIDATION_PENDING")
    t(g, "observed_view_does_not_let_observed_data_spoof_the_activation_field",
      MODEL.observed_view(make("AuthoritativeReadbackReceipt", receipt_id="s", transaction_id="T", mutation_id="M", contract_hash=Z, source_level="AUTHORITATIVE_REPOSITORY", existence="EXISTS", activation="INACTIVE", observed={"$activation": "ACTIVE"}))["$activation"] == "INACTIVE")

    # ---------------------------------------------------------------- compensation attempts (G03)
    g = "COMPENSATION_ATTEMPTS"
    mm, ff, gg = comp_mission(3)
    t(g, "first_attempt_is_numbered_one_and_consumes_a_ledger_entry", lambda: (mm.begin_compensation() == 1 and mm.ledger.has((gg["object_hash"], "COMPENSATION-ATTEMPT-1"))))
    t(g, "a_second_attempt_cannot_open_while_the_first_is_open", lambda: (raises(lambda: mm.begin_compensation(), "attempt is already open")))
    t(g, "a_receipt_for_another_attempt_number_is_refused", lambda: (raises(lambda: mm.record_compensation_failure(comp_exec(gg, cls="PROVIDER_ERROR", attempt=2)), "not bound to the grant")))
    t(g, "a_failure_cannot_be_recorded_as_a_success", lambda: (raises(lambda: mm.record_compensation_failure(comp_exec(gg)), "record_compensation")))
    t(g, "a_success_receipt_with_a_failing_call_class_is_refused_by_record_compensation",
      raises(lambda: mm.record_compensation(comp_receipt(gg, post_receipt(ff)), post_receipt(ff), comp_exec(gg, cls="PROVIDER_ERROR")), "must report success"))
    t(g, "an_invalid_failure_class_is_refused", lambda: (raises(lambda: mm.record_compensation_failure(comp_exec(gg, cls="OUTCOME_VALIDATED")), "not valid for a compensating call")))
    t(g, "a_definite_failure_keeps_the_mission_open_when_budget_remains", lambda: (mm.record_compensation_failure(comp_exec(gg, cls="PROVIDER_ERROR")) == "COMPENSATION_AUTHORIZED" and mm.ev["comp_open"] is None))
    t(g, "after_a_definite_failure_the_next_attempt_is_number_two", lambda: (mm.begin_compensation() == 2 and mm.ledger.has((gg["object_hash"], "COMPENSATION-ATTEMPT-2"))))
    t(g, "attempt_two_must_name_attempt_two", lambda: (raises(lambda: mm.record_compensation_failure(comp_exec(gg, cls="PROVIDER_ERROR", attempt=1)), "not bound to the grant")))
    t(g, "a_not_sent_failure_is_still_counted", lambda: (mm.record_compensation_failure(comp_exec(gg, cls="CALL_NOT_SENT", attempt=2)) == "COMPENSATION_AUTHORIZED" and len(mm.ev["comp_log"]) == 2))
    t(g, "the_third_attempt_succeeds_with_a_distinct_authoritative_readback", lambda: (mm.begin_compensation() == 3 and safe(lambda: (mm.record_compensation(comp_receipt(gg, post_receipt(ff)), post_receipt(ff), comp_exec(gg, attempt=3)), mm.state)[1] == "COMPENSATED")))
    t(g, "the_compensation_evidence_is_persisted_after_success", lambda: (all(k in mm.ev for k in ("comp_receipt", "comp_readback", "comp_execution")) and mm.ev["comp_receipt"]["grant_hash"] == gg["object_hash"]))
    t(g, "three_ledger_entries_exist_for_the_grant", lambda: (len(mm.ledger.for_authority(gg["object_hash"])) == 3))
    t(g, "comp_log_records_each_failed_attempt", lambda: ([e["attempt"] for e in mm.ev["comp_log"]] == [1, 2] and [e["call_class"] for e in mm.ev["comp_log"]] == ["PROVIDER_ERROR", "CALL_NOT_SENT"]))

    mm, ff, gg = comp_mission(2)
    mm.begin_compensation(); mm.record_compensation_failure(comp_exec(gg, cls="PROVIDER_ERROR")); mm.begin_compensation()
    t(g, "the_last_failed_attempt_makes_the_mission_unrecoverable", lambda: (mm.record_compensation_failure(comp_exec(gg, cls="PROVIDER_ERROR", attempt=2)) == "UNRECOVERABLE" and mm.state == "UNRECOVERABLE"))
    t(g, "no_attempt_is_possible_after_unrecoverable", lambda: (raises(lambda: mm.begin_compensation(), "illegal transition")))

    mm, ff, gg = comp_mission(2)
    mm.begin_compensation(); mm.record_compensation_failure(comp_exec(gg, cls="CALL_SENT_NO_RESPONSE"))
    t(g, "an_unknown_outcome_blocks_the_next_attempt_without_a_readback", lambda: (raises(lambda: mm.begin_compensation(), "outcome is unknown") and mm.ev["comp_open"] is None))
    met = post_receipt(ff, "ABSENT", {"exists": False}, rid="met")
    t(g, "a_readback_showing_the_goal_met_cannot_resolve_it_as_unmet", lambda: (raises(lambda: mm.begin_compensation(resolution_readback=met), "does not show the compensation goal unmet")))
    weak = remake(rb_receipt(ff, obs={"exists": True, "package": "WRONG"}, level="PROVIDER_LOG"), receipt_id="weak")
    t(g, "a_non_authoritative_resolution_readback_is_refused", lambda: (raises(lambda: mm.begin_compensation(resolution_readback=weak), "authoritative")))
    unmet = remake(rb_receipt(ff, obs=dict(GOOD_OBS, package="WRONG")), receipt_id="unmet")
    t(g, "an_authoritative_readback_showing_the_goal_unmet_resolves_it", lambda: (mm.begin_compensation(resolution_readback=unmet) == 2 and mm.ev["comp_unresolved"] is False and mm.ev["comp_resolutions"] == [unmet["object_hash"]]))

    mm, ff, gg = comp_mission(1)
    t(g, "resume_cannot_widen_the_attempt_budget_a_used_ledger_entry_blocks_it", lambda: (safe(lambda: mm.ledger.consume((gg["object_hash"], "COMPENSATION-ATTEMPT-1"), limit=1) is None) and raises(lambda: mm.begin_compensation(), "budget exhausted") and mm.ev.get("comp_open") is None))

    # concurrency: several Mission objects sharing one ledger cannot exceed the grant budget
    shared = MODEL.ReplayLedger()
    ms = []
    for _ in range(6):
        m_, f_, g_ = comp_mission(2, ledger=shared)
        ms.append((m_, g_))
    grant_hash = ms[0][1]["object_hash"]
    ms = [(m_, g_) for m_, g_ in ms if g_["object_hash"] == grant_hash]
    wins, errs = [], []
    barrier = threading.Barrier(len(ms))
    def go(m_):
        barrier.wait()
        try:
            wins.append(m_.begin_compensation())
        except GuardError:
            pass
        except Exception as exc:
            errs.append(type(exc).__name__)
    ths = [threading.Thread(target=go, args=(m_,)) for m_, _ in ms]
    [x.start() for x in ths]; [x.join() for x in ths]
    t(g, "six_missions_sharing_a_ledger_open_at_most_the_grant_budget_of_attempts", lambda: (len(wins) == 2 and not errs and len(shared.for_authority(grant_hash)) == 2))
    t(g, "the_winning_attempt_numbers_are_unique_in_the_ledger", lambda: (len({k[1] for k in shared._keys if k[0] == grant_hash}) == 2))

    # grants: unchanged checks still hold
    mm, ff = comp_ready()
    t(g, "a_grant_with_zero_attempts_is_refused", lambda: (raises(lambda: mm.authorize_compensation(grant_of(max_mutations=0)), "incomplete")))

    # ---------------------------------------------------------------- ledger anchor (G08)
    g = "LEDGER_ANCHOR"
    import shutil
    d_ = tempfile.mkdtemp(prefix="m3anchor_")
    lp = os.path.join(d_, "ledger.txt")
    lg = MODEL.ReplayLedger(lp)
    a0 = lg.anchor()
    t(g, "an_empty_ledger_has_a_count_of_zero_and_a_head", a0["count"] == 0 and len(a0["head"]) == 64 and a0["ledger_id"] == lg.ledger_id)
    lg.consume(("A" * 64, "M-1"))
    a1 = lg.anchor()
    shutil.copyfile(lp, lp + ".copy1")
    lg.consume(("A" * 64, "M-2"))
    a2 = lg.anchor()
    t(g, "each_consume_changes_the_head_and_raises_the_count", a1["count"] == 1 and a2["count"] == 2 and len({a0["head"], a1["head"], a2["head"]}) == 3)
    t(g, "the_anchor_is_deterministic_for_the_same_content", MODEL.ReplayLedger(lp).anchor() == a2)
    t(g, "an_anchor_of_a_prefix_is_still_valid_after_more_entries", lg.check_anchor(a1) is True and lg.check_anchor(a0) is True and lg.check_anchor(a2) is True)
    shutil.copyfile(lp, lp + ".latest")
    shutil.copyfile(lp + ".copy1", lp)                         # an attacker restores the older copy of the same file
    older = MODEL.ReplayLedger(lp)
    t(g, "a_restored_older_copy_is_detected_by_the_latest_anchor", raises(lambda: older.check_anchor(a2), "fewer entries"))
    t(g, "a_restored_older_copy_still_satisfies_the_older_anchor", older.check_anchor(a1) is True)
    lg_hist = MODEL.ReplayLedger(os.path.join(d_, "ledger2.txt"))
    lg_hist.consume(("B" * 64, "M-1")); lg_hist.consume(("B" * 64, "M-2"))
    ah = lg_hist.anchor()
    other = MODEL.ReplayLedger(os.path.join(d_, "ledger3.txt"))
    other.consume(("B" * 64, "M-1")); other.consume(("B" * 64, "M-X"))
    t(g, "a_ledger_with_the_same_count_but_other_history_is_detected", raises(lambda: other.check_anchor(dict(ah, ledger_id=other.ledger_id)), "history differs"))
    t(g, "an_anchor_from_another_ledger_is_detected", raises(lambda: other.check_anchor(ah), "identity differs"))
    for label, bad in (("not_a_dict", "x"), ("missing_count", {"ledger_id": "a", "head": "0" * 64}), ("bool_count", dict(ah, count=True)), ("negative_count", dict(ah, count=-1)),
                       ("short_head", dict(ah, head="abc")), ("int_id", dict(ah, ledger_id=5)), ("none", None)):
        t(g, "malformed_anchor_%s_is_refused" % label, raises(lambda b=bad: lg_hist.check_anchor(b), "malformed"))
    vol = MODEL.ReplayLedger()
    va = vol.anchor()
    vol.consume(("C" * 64, "M-1"))
    t(g, "a_volatile_ledger_anchors_within_the_process", va["ledger_id"] == "VOLATILE" and vol.check_anchor(va) is True and vol.anchor()["count"] == 1)
    t(g, "a_volatile_ledger_cannot_vouch_for_a_durable_one", raises(lambda: vol.check_anchor(ah), "identity differs"))
    mm, ff = fixture(); to_prewrite(mm, ff); mm.begin_execution("MUT-1", FP)
    lease = mm.checkpoint_lease()
    t(g, "a_lease_carries_the_ledger_anchor", isinstance(lease.get("ledger_anchor"), dict) and lease["ledger_anchor"]["count"] == 1)
    ev_up = {k: mm.ev[k] for k in ("intent", "principal", "delegation", "capability", "provider", "tx", "budget", "outcome_contract", "readback_contract", "authority")}
    rs = Mission.resume(lease, ff["cp"], ff["bu"], "M-SYN-1", ev_up, mm.ledger, allow_volatile_ledger=True)
    t(g, "resume_with_the_matching_ledger_and_anchor_works", rs.state == "COMMIT_STATE_UNKNOWN")
    no_anchor = make("ContinuationLease", **{k: v for k, v in lease.items() if k not in ("kind", "object_hash", "ledger_anchor")})
    t(g, "a_lease_without_an_anchor_is_refused", raises(lambda: Mission.resume(no_anchor, ff["cp"], ff["bu"], "M-SYN-1", ev_up, mm.ledger, allow_volatile_ledger=True), "no ledger anchor"))
    bad_anchor = remake(lease, ledger_anchor=dict(lease["ledger_anchor"], head="f" * 64))
    t(g, "a_lease_whose_anchor_head_is_wrong_is_refused", raises(lambda: Mission.resume(bad_anchor, ff["cp"], ff["bu"], "M-SYN-1", ev_up, mm.ledger, allow_volatile_ledger=True), "history differs"))
    fresh_led = MODEL.ReplayLedger(os.path.join(d_, "restore.txt"))
    mr, fr = fixture(); mr.ledger = fresh_led; to_prewrite(mr, fr); mr.begin_execution("MUT-1", FP)
    shutil.copyfile(fresh_led.path, fresh_led.path + ".keep")
    lease_r = mr.checkpoint_lease()
    open(fresh_led.path, "wb").write(open(fresh_led.path + ".keep", "rb").read()[:0] + open(fresh_led.path + ".keep", "rb").read())   # same bytes: control
    ev_r = {k: mr.ev[k] for k in ev_up}
    t(g, "resume_control_with_an_untouched_ledger_works", Mission.resume(lease_r, fr["cp"], fr["bu"], "M-SYN-1", ev_r, MODEL.ReplayLedger(fresh_led.path), allow_unanchored_ledger=True).state == "COMMIT_STATE_UNKNOWN")
    header_only = open(fresh_led.path, "rb").read().split(b"\n")[0] + b"\n"
    open(fresh_led.path, "wb").write(header_only)               # the send record is removed from the file, header (id) kept
    t(g, "removing_the_send_record_from_a_durable_ledger_is_caught_on_resume", raises(lambda: Mission.resume(lease_r, fr["cp"], fr["bu"], "M-SYN-1", ev_r, MODEL.ReplayLedger(fresh_led.path), allow_unanchored_ledger=True), "does not record"))
    shutil.rmtree(d_, ignore_errors=True)

    # ---------------------------------------------------------------- outcome classification (the 3.0 distinction)
    g = "OUTCOME_CLASSIFICATION"
    oc_ = MODEL.outcome_classification
    mm, ff = fixture()
    t(g, "nothing_sent_has_no_classification", lambda: (oc_(mm) is None))
    to_prewrite(mm, ff)
    t(g, "prewrite_validated_has_no_classification", lambda: (oc_(mm) is None))
    mm.begin_execution("MUT-1", FP)
    t(g, "execution_started_is_only_executed", lambda: (oc_(mm) == "EXECUTED"))
    mm.record_execution(exec_receipt(ff, "CALL_SENT_NO_RESPONSE"))
    t(g, "a_no_response_call_is_commit_unknown", lambda: (oc_(mm) == "COMMIT_UNKNOWN"))
    mm, ff = fixture(); to_prewrite(mm, ff); mm.begin_execution("MUT-1", FP); mm.record_execution(exec_receipt(ff))
    t(g, "a_provider_success_is_acknowledged_not_committed", lambda: (oc_(mm) == "PROVIDER_ACKNOWLEDGED"))
    mm.request_readback()
    t(g, "waiting_for_readback_is_still_only_acknowledged", lambda: (oc_(mm) == "PROVIDER_ACKNOWLEDGED"))
    rb = rb_receipt(ff); mm.observe_readback(rb)
    t(g, "an_observed_readback_is_still_not_a_commit_decision", lambda: (oc_(mm) == "PROVIDER_ACKNOWLEDGED"))
    mm.decide_commit(commit_obs(rb, "COMMITTED"))
    t(g, "a_decided_commit_is_commit_observed_not_validated", lambda: (oc_(mm) == "COMMIT_OBSERVED"))
    mm.validate_outcome(outcome(ff, rb, eval_predicates(PREDS, rb["observed"])))
    t(g, "a_passing_outcome_is_validated_not_complete", lambda: (oc_(mm) == "OUTCOME_VALIDATED"))
    mm.complete(make("CompletionReceipt", receipt_id="done", transaction_id="TX-SYN-1", outcome_receipt_hash=mm.ev["outcome"]["object_hash"],
                     commit_observation_hash=mm.ev["commit"]["object_hash"], execution_receipt_hash=mm.ev["execution_receipt"]["object_hash"], authority_hash=ff["au"]["object_hash"]))
    t(g, "only_the_completion_receipt_makes_it_complete", lambda: (oc_(mm) == "COMPLETE"))
    mm, ff = fixture(); er, rb = happy(mm, ff, obs={"exists": True, "package": "ZPKG_SYN"})
    t(g, "an_unknown_predicate_result_is_outcome_unknown", lambda: (oc_(mm) == "OUTCOME_UNKNOWN"))
    mm, ff = comp_ready()
    t(g, "a_failed_outcome_requires_compensation", lambda: (oc_(mm) == "COMPENSATION_REQUIRED"))
    mm, ff, gg = comp_mission(1); mm.begin_compensation(); mm.record_compensation_failure(comp_exec(gg, cls="PROVIDER_ERROR"))
    t(g, "an_exhausted_compensation_is_unrecoverable", lambda: (oc_(mm) == "UNRECOVERABLE"))
    mm, ff = fixture(); to_prewrite(mm, ff); mm.begin_execution("MUT-1", FP); mm.record_execution(exec_receipt(ff)); mm.request_readback()
    rb = rb_receipt(ff, "UNKNOWN"); mm.observe_readback(rb); mm.decide_commit(commit_obs(rb, "UNKNOWN"))
    t(g, "an_unknown_readback_is_commit_unknown", lambda: (oc_(mm) == "COMMIT_UNKNOWN"))
    t(g, "classification_values_are_from_the_declared_set", lambda: (all(v in MODEL.OUTCOME_CLASSES for v in ("EXECUTED", "COMPLETE")) and set(MODEL.OUTCOME_CLASSES) >= {"PROVIDER_ACKNOWLEDGED", "COMMIT_OBSERVED", "OUTCOME_OBSERVED", "OUTCOME_VALIDATED", "OUTCOME_UNKNOWN", "COMMIT_UNKNOWN"}))
    t(g, "a_provider_success_never_maps_beyond_acknowledged_without_a_commit", lambda: (all(oc_(m_) in (None, "EXECUTED", "PROVIDER_ACKNOWLEDGED", "COMMIT_UNKNOWN") for m_ in [Mission("M", "T", 1)])))


def main(argv):
    run()
    failed = sorted(n for n, ok in T.items() if not ok)
    groups = {gk: "PASS" if all(T[n] for n in names) else "FAIL" for gk, names in G.items()}
    digest = hashlib.sha256(json.dumps(sorted(T), separators=(",", ":")).encode()).hexdigest().upper()
    result = {"stage": "MCR3_HARDENING", "evidence_class": "SYNTHETIC/LOCAL", "tests": len(T), "failed": failed, "groups": groups, "tests_digest": digest, "network_calls": 0}
    out = json.dumps(result, indent=2, sort_keys=True)
    if "--out" in argv:
        with open(argv[argv.index("--out") + 1], "w", newline="\n") as fh:
            fh.write(out + "\n")
    print(out)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
