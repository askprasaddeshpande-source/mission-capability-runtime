"""Tests for evidence provenance verification and capability/adapter authority governance. Offline; throwaway test
identities only (generated in temp folders and deleted). Optional back-ends are exercised when available and recorded
as NOT_VERIFIED otherwise."""
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
if os.environ.get("MCR3_OVERRIDE_DIR"):          # mutation harness: a mutated module shadows the real one
    sys.path.insert(0, os.environ["MCR3_OVERRIDE_DIR"])
import evc1  # noqa: E402
import mcr3_authority as A  # noqa: E402
import mcr3_provenance as P  # noqa: E402

T, G = {}, {}
NOT_VERIFIED = []
H = "a" * 64
NOW = 1_800_000_000.0                    # fixed test clock (2027-01-15)


def iso(ts):
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def t(group, name, ok):
    try:
        ok = ok() if callable(ok) else ok
    except Exception:
        ok = False
    T[name] = bool(ok)
    G.setdefault(group, []).append(name)


def raises(fn, text=None):
    try:
        fn()
    except (A.AuthorityError, evc1.ContractError, ValueError, RuntimeError) as exc:
        return text is None or text in str(exc)
    return False


def make_ev(classification="OBSERVED", **kw):
    args = dict(event_id="EVT-AUTH-0001", source="mcr://auth/test", time="2027-01-15T00:00:00Z", runtime_version="3.0.0", adapter_id="t-adapter",
                adapter_version="1.0.0", source_runtime_version="3.0.0",
                correlation={"mission_id": "M-SYN-1", "transaction_id": "TX-SYN-1", "correlation_id": "CORR-SYN-1", "causation_id": None},
                evidence_digest=H, classification=classification)
    args.update(kw)
    return evc1.make_event("mcr.execution.receipt", {"call_class": "PROVIDER_RESPONSE_SUCCESS", "provider_acknowledged": True, "implies_commit": False}, **args)


def run():
    hm = P.HmacTestVerifier({"alice": b"k-alice", "bob": b"k-bob", "mallory": b"k-mallory"})
    policy = lambda **kw: P.TrustPolicy(issuers={"alice": {"status": "TRUSTED", "not_before": None, "not_after": None}, "bob": {"status": "UNTRUSTED"}},
                                        revoked=kw.pop("revoked", ()), max_age_seconds=kw.pop("max_age", 3600), clock=lambda: NOW, **kw)
    ev = make_ev()
    signed_at = iso(NOW - 60)

    # ---------------------------------------------------------------- provenance: the seven things are separate
    g = "PROVENANCE"
    att = P.make_attestation(ev, "alice", hm, signed_at=signed_at)
    p_ok = P.assess(ev, att, hm, policy(), P.ReplayCache())
    t(g, "a_valid_trusted_fresh_unseen_attestation_is_signed_trusted", lambda: (evc1.derive_trust(p_ok) == "SIGNED_TRUSTED" and p_ok["signature"] == "VALID"))
    t(g, "missing_attestation_is_research_only", lambda: (evc1.derive_trust(P.assess(ev, None, hm, policy())) == "UNTRUSTED_RESEARCH"))
    t(g, "non_dict_attestations_never_raise_and_are_research_only", lambda: (all(evc1.derive_trust(P.assess(ev, x, hm, policy())) == "UNTRUSTED_RESEARCH" for x in ("sig", 5, [], b"x"))))
    bad = dict(att, sig=att["sig"][:-4] + ("AAAA" if att["sig"][-4:] != "AAAA" else "BBBB"))
    t(g, "an_invalid_signature_is_signature_invalid", lambda: (evc1.derive_trust(P.assess(ev, bad, hm, policy())) == "SIGNATURE_INVALID"))
    t(g, "a_malformed_signature_is_signature_invalid", lambda: (evc1.derive_trust(P.assess(ev, dict(att, sig="!!not base64!!"), hm, policy())) == "SIGNATURE_INVALID"))
    t(g, "a_signature_by_another_signer_claiming_alice_is_invalid", lambda: (evc1.derive_trust(P.assess(ev, dict(P.make_attestation(ev, "mallory", hm, signed_at=signed_at), signer="alice"), hm, policy())) == "SIGNATURE_INVALID"))
    t(g, "an_unknown_signer_is_invalid", lambda: (evc1.derive_trust(P.assess(ev, dict(att, signer="eve"), hm, policy())) == "SIGNATURE_INVALID"))
    t(g, "a_valid_signature_by_an_untrusted_issuer_is_signed_untrusted", lambda: (evc1.derive_trust(P.assess(ev, P.make_attestation(ev, "bob", hm, signed_at=signed_at), hm, policy(), P.ReplayCache())) == "SIGNED_UNTRUSTED"))
    t(g, "a_valid_signature_by_an_unlisted_issuer_is_signed_untrusted", lambda: (evc1.derive_trust(P.assess(ev, P.make_attestation(ev, "mallory", hm, signed_at=signed_at), hm, policy(), P.ReplayCache())) == "SIGNED_UNTRUSTED"))
    t(g, "a_revoked_producer_loses_trusted_status", lambda: (evc1.derive_trust(P.assess(ev, att, hm, policy(revoked=["alice"]), P.ReplayCache())) == "REVOKED"))
    old = P.make_attestation(ev, "alice", hm, signed_at=iso(NOW - 7200))
    t(g, "an_old_attestation_is_expired", lambda: (evc1.derive_trust(P.assess(ev, old, hm, policy(), P.ReplayCache())) == "EXPIRED"))
    fut = P.make_attestation(ev, "alice", hm, signed_at=iso(NOW + 600))
    t(g, "a_future_dated_attestation_is_not_fresh", lambda: (evc1.derive_trust(P.assess(ev, fut, hm, policy(), P.ReplayCache())) == "EXPIRED"))
    t(g, "the_age_limit_is_inclusive", lambda: (evc1.derive_trust(P.assess(ev, P.make_attestation(ev, "alice", hm, signed_at=iso(NOW - 3600)), hm, policy(), P.ReplayCache())) == "SIGNED_TRUSTED"))
    t(g, "one_second_past_the_age_limit_is_expired", lambda: (evc1.derive_trust(P.assess(ev, P.make_attestation(ev, "alice", hm, signed_at=iso(NOW - 3601)), hm, policy(), P.ReplayCache())) == "EXPIRED"))
    rc = P.ReplayCache()
    first = P.assess(ev, att, hm, policy(), rc)
    second = P.assess(ev, att, hm, policy(), rc)
    t(g, "the_same_attestation_presented_twice_is_replayed", lambda: (evc1.derive_trust(first) == "SIGNED_TRUSTED" and evc1.derive_trust(second) == "REPLAYED"))
    rc2 = P.ReplayCache()
    P.assess(ev, att, hm, policy(), rc2, record_replay=False)
    t(g, "a_dry_run_does_not_consume_the_replay_slot", lambda: (evc1.derive_trust(P.assess(ev, att, hm, policy(), rc2)) == "SIGNED_TRUSTED"))
    rc3 = P.ReplayCache()
    P.assess(ev, P.make_attestation(ev, "bob", hm, signed_at=signed_at), hm, policy(), rc3)
    t(g, "an_untrusted_signer_does_not_poison_the_replay_cache", lambda: (evc1.derive_trust(P.assess(ev, P.make_attestation(ev, "bob", hm, signed_at=signed_at), hm, policy(), rc3)) == "SIGNED_UNTRUSTED"))
    # changed payload
    changed = evc1.seal(dict({k: v for k, v in ev.items() if k != "integrity"}, time="2027-01-15T00:00:01Z"))
    t(g, "a_changed_but_resealed_payload_invalidates_the_signature", lambda: (evc1.derive_trust(P.assess(changed, att, hm, policy(), P.ReplayCache())) == "SIGNATURE_INVALID"))
    torn = dict(ev, time="2027-01-15T00:00:01Z")
    pt = P.assess(torn, att, hm, policy(), P.ReplayCache())
    t(g, "a_changed_payload_without_reseal_fails_hash_consistency", lambda: (pt["hash_consistent"] is False and evc1.derive_trust(pt) == "SIGNATURE_INVALID"))
    # policy and authority digests are bound by the signature
    pol_a, pol_b, auth_a, auth_b = "1" * 64, "2" * 64, "3" * 64, "4" * 64
    bound = P.make_attestation(ev, "alice", hm, signed_at=signed_at, policy_digest=pol_a, authority_digest=auth_a)
    t(g, "matching_policy_and_authority_digests_verify", lambda: (evc1.derive_trust(P.assess(ev, bound, hm, policy(expected_policy_digest=pol_a, expected_authority_digest=auth_a), P.ReplayCache())) == "SIGNED_TRUSTED"))
    t(g, "a_policy_digest_the_verifier_does_not_expect_is_invalid", lambda: (evc1.derive_trust(P.assess(ev, bound, hm, policy(expected_policy_digest=pol_b), P.ReplayCache())) == "SIGNATURE_INVALID"))
    t(g, "an_authority_digest_the_verifier_does_not_expect_is_invalid", lambda: (evc1.derive_trust(P.assess(ev, bound, hm, policy(expected_authority_digest=auth_b), P.ReplayCache())) == "SIGNATURE_INVALID"))
    t(g, "editing_the_policy_digest_in_the_attestation_breaks_the_signature", lambda: (evc1.derive_trust(P.assess(ev, dict(bound, policy_digest=pol_b), hm, policy(), P.ReplayCache())) == "SIGNATURE_INVALID"))
    t(g, "editing_the_authority_digest_in_the_attestation_breaks_the_signature", lambda: (evc1.derive_trust(P.assess(ev, dict(bound, authority_digest=auth_b), hm, policy(), P.ReplayCache())) == "SIGNATURE_INVALID"))
    t(g, "editing_the_signing_time_breaks_the_signature", lambda: (evc1.derive_trust(P.assess(ev, dict(att, signed_at=iso(NOW - 30)), hm, policy(), P.ReplayCache())) == "SIGNATURE_INVALID"))
    t(g, "a_malformed_signing_time_is_invalid", lambda: (evc1.derive_trust(P.assess(ev, dict(att, signed_at="yesterday"), hm, policy(), P.ReplayCache())) == "SIGNATURE_INVALID"))
    t(g, "an_attestation_for_another_event_is_invalid", lambda: (evc1.derive_trust(P.assess(make_ev(event_id="EVT-OTHER-0002"), att, hm, policy(), P.ReplayCache())) == "SIGNATURE_INVALID"))
    t(g, "issuer_validity_window_is_enforced", lambda: (evc1.derive_trust(P.assess(ev, att, hm, P.TrustPolicy(issuers={"alice": {"status": "TRUSTED", "not_before": NOW + 10, "not_after": None}}, clock=lambda: NOW), P.ReplayCache())) == "SIGNED_UNTRUSTED"))
    # attaching a verdict keeps the producer's signature valid and grants nothing
    attached = P.attach(ev, p_ok)
    t(g, "attaching_the_verdict_yields_an_accepted_event", lambda: (bool(evc1.parse(attached)) and attached["evidence"]["trust"] == "SIGNED_TRUSTED"))
    t(g, "attaching_the_verdict_keeps_authority_effect_none", lambda: (attached["authority_effect"] == "NONE"))
    t(g, "the_producer_signature_still_verifies_on_the_attached_event", lambda: (evc1.derive_trust(P.assess(attached, att, hm, policy(), P.ReplayCache())) == "SIGNED_TRUSTED"))
    t(g, "content_digest_ignores_provenance_but_not_content", lambda: (evc1.content_digest(ev) == evc1.content_digest(attached) and evc1.content_digest(ev) != evc1.content_digest(changed)))
    t(g, "a_signed_trusted_event_does_not_change_its_outcome_claim", lambda: (attached["claim"] == ev["claim"] and attached["claim"]["layer"] == "RECEIPT"))
    t(g, "a_forged_trust_label_without_provenance_is_rejected_by_the_contract", lambda: (raises(lambda: evc1.parse(evc1.seal(dict({k: v for k, v in ev.items() if k != "integrity"}, evidence=dict(ev["evidence"], trust="SIGNED_TRUSTED")))))))

    # ---------------------------------------------------------------- back-ends
    g = "BACKENDS"
    t(g, "hmac_backend_is_marked_test_only", lambda: (getattr(P.HmacTestVerifier, "TEST_ONLY", False) is True))
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization
        sk = Ed25519PrivateKey.generate()
        pk = sk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        sk2 = Ed25519PrivateKey.generate()
        ed = P.Ed25519Verifier({"alice": pk})
        import base64
        msg = P.signed_message(evc1.content_digest(ev), signed_at, "alice")
        ed_att = P.make_attestation_with_signature(ev, "alice", "ED25519", base64.b64encode(sk.sign(msg)).decode(), signed_at)
        t(g, "ed25519_valid_signature_verifies_and_is_trusted", lambda: (evc1.derive_trust(P.assess(ev, ed_att, ed, policy(), P.ReplayCache())) == "SIGNED_TRUSTED"))
        wrong = P.make_attestation_with_signature(ev, "alice", "ED25519", base64.b64encode(sk2.sign(msg)).decode(), signed_at)
        t(g, "ed25519_signature_by_another_key_is_invalid", lambda: (evc1.derive_trust(P.assess(ev, wrong, ed, policy(), P.ReplayCache())) == "SIGNATURE_INVALID"))
        t(g, "ed25519_wrong_algorithm_label_is_invalid", lambda: (evc1.derive_trust(P.assess(ev, dict(ed_att, alg="HMAC-SHA256-TEST"), ed, policy(), P.ReplayCache())) == "SIGNATURE_INVALID"))
        t(g, "ed25519_truncated_signature_is_invalid", lambda: (evc1.derive_trust(P.assess(ev, dict(ed_att, sig=ed_att["sig"][:20]), ed, policy(), P.ReplayCache())) == "SIGNATURE_INVALID"))
    except ImportError:
        NOT_VERIFIED.append("Ed25519 back-end (cryptography package not installed)")
    tool = shutil.which("ssh-keygen")
    if tool:
        d = tempfile.mkdtemp(prefix="m3ssh_")
        try:
            subprocess.run([tool, "-q", "-t", "ed25519", "-N", "", "-f", os.path.join(d, "alice"), "-C", "alice"], check=True, capture_output=True)
            subprocess.run([tool, "-q", "-t", "ed25519", "-N", "", "-f", os.path.join(d, "mallory"), "-C", "mallory"], check=True, capture_output=True)
            pub = open(os.path.join(d, "alice.pub"), encoding="ascii").read().strip().split()
            allowed = os.path.join(d, "allowed_signers")
            with open(allowed, "w", newline="\n") as fh:
                fh.write("alice namespaces=\"%s\" %s %s\n" % (P.NAMESPACE, pub[0], pub[1]))
            sv = P.SshSigVerifier(allowed)
            msg = P.signed_message(evc1.content_digest(ev), signed_at, "alice")
            good = P.make_attestation_with_signature(ev, "alice", "SSHSIG-ED25519", P.ssh_sign(os.path.join(d, "alice"), msg), signed_at)
            t(g, "sshsig_valid_signature_verifies_and_is_trusted", lambda: (evc1.derive_trust(P.assess(ev, good, sv, policy(), P.ReplayCache())) == "SIGNED_TRUSTED"))
            evil = P.make_attestation_with_signature(ev, "alice", "SSHSIG-ED25519", P.ssh_sign(os.path.join(d, "mallory"), msg), signed_at)
            t(g, "sshsig_signature_by_a_key_not_in_allowed_signers_is_invalid", lambda: (evc1.derive_trust(P.assess(ev, evil, sv, policy(), P.ReplayCache())) == "SIGNATURE_INVALID"))
            msg2 = P.signed_message(evc1.content_digest(ev), iso(NOW - 10), "alice")
            moved = P.make_attestation_with_signature(ev, "alice", "SSHSIG-ED25519", P.ssh_sign(os.path.join(d, "alice"), msg), iso(NOW - 10))
            t(g, "sshsig_signature_over_other_content_is_invalid", lambda: (evc1.derive_trust(P.assess(ev, moved, sv, policy(), P.ReplayCache())) == "SIGNATURE_INVALID"))
            t(g, "sshsig_revoked_signer_loses_trusted_status", lambda: (evc1.derive_trust(P.assess(ev, good, sv, policy(revoked=["alice"]), P.ReplayCache())) == "REVOKED"))
            t(g, "sshsig_garbage_signature_is_invalid_not_a_crash", lambda: (evc1.derive_trust(P.assess(ev, dict(good, sig="not a signature"), sv, policy(), P.ReplayCache())) == "SIGNATURE_INVALID"))
            t(g, "sshsig_wrong_signer_name_is_invalid", lambda: (evc1.derive_trust(P.assess(ev, dict(good, signer="bob"), sv, policy(), P.ReplayCache())) == "SIGNATURE_INVALID"))
        finally:
            shutil.rmtree(d, ignore_errors=True)
    else:
        NOT_VERIFIED.append("SSH-signature back-end (ssh-keygen not available)")

    # ---------------------------------------------------------------- authority
    g = "CAPABILITY_STATES"
    clock = {"now": NOW}
    verifier = A.RecordedApprovalVerifier({"APPR-1"})
    reg = A.CapabilityRegistry(approval_verifier=verifier, clock=lambda: clock["now"])
    cap = reg.discover("create_object", "1.0.0", H)
    t(g, "an_unknown_capability_is_quarantined_on_discovery", lambda: (cap.state == "QUARANTINED"))
    t(g, "discovering_again_returns_the_same_capability", lambda: (reg.discover("create_object", "1.0.0", H) is cap))
    t(g, "a_changed_digest_is_a_different_unknown_capability", lambda: (reg.discover("create_object", "1.0.0", "b" * 64).state == "QUARANTINED" and reg.discover("create_object", "1.0.0", "b" * 64) is not cap))
    t(g, "capability_identity_needs_id_version_and_digest", lambda: (all(raises(lambda a=a: reg.discover(*a)) for a in (("", "1", H), ("x", "", H), ("x", "1", "short"), (5, "1", H)))))
    t(g, "a_quarantined_capability_cannot_be_qualified_directly", lambda: (raises(lambda: reg.qualify(cap, H, "GO", "reviewer"), "illegal capability transition")))
    t(g, "a_quarantined_capability_cannot_be_approved", lambda: (raises(lambda: reg.record_approval(cap, {}), "QUALIFIED")))
    t(g, "verification_needs_a_pass_and_evidence", lambda: (raises(lambda: reg.verify(cap, H, False)) and raises(lambda: reg.verify(cap, "short", True))))
    reg.verify(cap, H, True)
    t(g, "verification_moves_to_verified", lambda: (cap.state == "VERIFIED"))
    t(g, "a_hold_verdict_does_not_qualify", lambda: (raises(lambda: reg.qualify(cap, H, "HOLD", "reviewer"), "GO") and cap.state == "VERIFIED"))
    t(g, "an_unnamed_reviewer_does_not_qualify", lambda: (raises(lambda: reg.qualify(cap, H, "GO", "")) and cap.state == "VERIFIED"))
    t(g, "a_missing_evidence_digest_does_not_qualify", lambda: (raises(lambda: reg.qualify(cap, "x", "GO", "r")) and cap.state == "VERIFIED"))
    t(g, "a_verified_capability_cannot_be_approved", lambda: (raises(lambda: reg.record_approval(cap, {}), "QUALIFIED")))
    reg.qualify(cap, H, "GO_WITH_DOCUMENTED_GAPS", "reviewer-1")
    t(g, "go_with_documented_gaps_qualifies", lambda: (cap.state == "QUALIFIED" and cap.qualification["reviewer"] == "reviewer-1"))
    t(g, "qualification_does_not_approve", lambda: (reg.effective_state(cap) == "QUALIFIED" and reg.view(cap)["may_request_execution_review"] is False))
    t(g, "mcr_never_reports_that_it_grants_authority", lambda: (reg.view(cap)["mcr_grants_authority"] is False))
    scope = {"owner": "owner-1", "capability_id": "create_object", "provider_id": "SYN", "target_system": "SYN_SYS", "operation": "create", "environment": "TEST", "policy_digest": H}
    rec = dict(scope, approval_id="APPR-1", expires_at="2099-01-01")
    t(g, "the_default_registry_refuses_every_approval", lambda: (raises(lambda: A.CapabilityRegistry().record_approval(_qualified(A.CapabilityRegistry()), rec), "external approver")))
    for field in A.SCOPE_FIELDS + ("approval_id", "expires_at"):
        t(g, "approval_record_missing_%s_is_refused" % field, raises(lambda f=field: reg.record_approval(cap, {k: v for k, v in rec.items() if k != f}), "missing"))
    t(g, "approval_for_another_capability_is_refused", lambda: (raises(lambda: reg.record_approval(cap, dict(rec, capability_id="delete_object")), "another capability")))
    t(g, "an_already_expired_approval_is_refused", lambda: (raises(lambda: reg.record_approval(cap, dict(rec, expires_at="2020-01-01")), "expired")))
    t(g, "a_malformed_expiry_is_refused", lambda: (raises(lambda: reg.record_approval(cap, dict(rec, expires_at="soon")), "valid UTC")))
    t(g, "an_approval_the_external_approver_did_not_issue_is_refused", lambda: (raises(lambda: reg.record_approval(cap, dict(rec, approval_id="APPR-FORGED")), "not verified") and cap.state == "QUALIFIED"))
    t(g, "empty_scope_values_are_refused", lambda: (raises(lambda: reg.record_approval(cap, dict(rec, owner="")))))
    reg.record_approval(cap, rec)
    t(g, "a_verified_scoped_approval_reference_moves_to_approved", lambda: (cap.state == "APPROVED" and reg.effective_state(cap) == "APPROVED"))
    t(g, "the_view_shows_the_external_source_and_no_mcr_grant", lambda: (reg.view(cap, scope)["authority_source"] == "EXTERNAL_GOVERNOR" and reg.view(cap, scope)["mcr_grants_authority"] is False))
    for field in A.SCOPE_FIELDS:
        t(g, "scope_mismatch_in_%s_removes_the_approval_reference" % field, reg.view(cap, dict(scope, **{field: "other"}))["approval_reference_present"] is False)
    clock["now"] = A._expiry("2099-01-01") + 1
    t(g, "an_expired_approval_lapses_to_qualified", lambda: (reg.effective_state(cap) == "QUALIFIED" and reg.view(cap, scope)["may_request_execution_review"] is False))
    clock["now"] = NOW
    t(g, "approval_is_current_again_only_if_the_clock_says_so", lambda: (reg.effective_state(cap) == "APPROVED"))
    reg.suspend(cap, "incident")
    t(g, "suspension_clears_the_approval", lambda: (cap.state == "SUSPENDED" and cap.approval is None and reg.effective_state(cap) == "SUSPENDED"))
    t(g, "a_suspended_capability_cannot_be_approved_directly", lambda: (raises(lambda: reg.record_approval(cap, rec), "QUALIFIED")))
    t(g, "a_suspended_capability_cannot_be_qualified_directly", lambda: (raises(lambda: reg.qualify(cap, H, "GO", "r"), "illegal capability transition")))
    reg.verify(cap, H, True)
    t(g, "re_verification_returns_a_suspended_capability_to_verified_only", lambda: (cap.state == "VERIFIED"))
    reg.qualify(cap, H, "GO", "reviewer-2"); reg.record_approval(cap, rec)
    t(g, "after_requalification_a_new_approval_record_is_needed_and_works", lambda: (cap.state == "APPROVED"))
    reg.raise_policy_epoch()
    t(g, "a_stricter_policy_epoch_withdraws_every_approval", lambda: (cap.state == "QUALIFIED" and cap.approval is None and reg.view(cap, scope)["may_request_execution_review"] is False))
    reg.record_approval(cap, rec)
    reg.revoke(cap, "compromised")
    t(g, "revocation_is_final", lambda: (cap.state == "REVOKED" and raises(lambda: reg.verify(cap, H, True)) and raises(lambda: reg.suspend(cap, "x"), "final")))
    t(g, "a_revoked_capability_has_no_authority_view", lambda: (reg.view(cap, scope)["may_request_execution_review"] is False and reg.view(cap, scope)["state"] == "REVOKED"))
    t(g, "the_registry_has_no_approve_method_that_skips_the_record", lambda: (not any(n in dir(reg) for n in ("approve", "grant", "promote", "auto_approve", "set_state"))))
    t(g, "every_state_in_the_contract_exists_in_the_registry", lambda: (set(A.STATES) == set(evc1.CAPABILITY_STATES) == set(A.FORWARD)))
    t(g, "qualified_has_only_approved_as_a_forward_move", lambda: (A.FORWARD["QUALIFIED"] == {"APPROVED"} and A.FORWARD["REVOKED"] == set()))

    g = "ADAPTERS"
    def adapter(**kw):
        d = dict(adapter_id="mcr2-reference", source_runtime_version="2.0.0", target_contract_version="1.0.0", supported_capabilities=["create_object"],
                 evidence_classification="HISTORICAL", trust_requirements="unsigned; research only")
        d.update(kw)
        return A.Adapter(**d)
    ascope = {"owner": "owner-1", "capability_id": "create_object", "provider_id": "SYN", "target_system": "SYN_SYS", "operation": "create", "environment": "TEST", "policy_digest": H}
    aclock = {"now": NOW}
    gov = A.RecordedApprovalVerifier({"A1", "A2", "A3", "A9"})

    def aref(aid, ad, ver, mode, qd=H, **kw):
        r = A.adapter_approval_record(aid, ascope, ad, ver, mode, qd)
        r.update(kw)
        return r

    class Exploding(A.ApprovalVerifier):
        def verify(self, record):
            raise RuntimeError("governor unreachable")

    class Truthy(A.ApprovalVerifier):
        def verify(self, record):
            return "yes"

    def failing(verifier):
        r = A.AdapterRegistry(verifier, lambda: aclock["now"])
        r.register(adapter(adapter_id="e"), "1.0.0")
        return raises(lambda: r.promote("e", "1.0.0", "SHADOW", H, aref("A1", "e", "1.0.0", "SHADOW"), ascope), "not verified") and r.mode("e", "1.0.0") == "OBSERVATION_ONLY"

    def dflt():
        r = A.AdapterRegistry()
        r.register(adapter(adapter_id="dd"), "1.0.0")
        return raises(lambda: r.promote("dd", "1.0.0", "SHADOW", H, aref("A1", "dd", "1.0.0", "SHADOW"), ascope), "not verified") and r.mode("dd", "1.0.0") == "OBSERVATION_ONLY"
    ar = A.AdapterRegistry(approval_verifier=gov, clock=lambda: aclock["now"])
    a1 = adapter()
    t(g, "the_declaration_has_every_required_field", {"ADAPTER_ID", "SOURCE_RUNTIME_VERSION", "TARGET_CONTRACT_VERSION", "SUPPORTED_CAPABILITIES", "EVIDENCE_CLASSIFICATION", "TRUST_REQUIREMENTS",
                                                       "QUALIFICATION_EVIDENCE", "APPROVAL_STATUS", "REVOCATION_STATUS", "DEFAULT_AUTHORITY"} <= set(a1.declaration))
    t(g, "default_authority_is_none", lambda: (a1.declaration["DEFAULT_AUTHORITY"] == "NONE"))
    t(g, "a_new_adapter_starts_in_observation_only_mode", lambda: (a1.declaration["MODE"] == "OBSERVATION_ONLY" and ar.register(a1, "1.0.0") is a1))
    t(g, "registering_straight_into_active_mode_is_refused", lambda: (raises(lambda: ar.register(adapter(adapter_id="x", mode="ACTIVE"), "1.0.0"), "OBSERVATION_ONLY")))
    t(g, "an_incomplete_declaration_is_refused", lambda: (raises(lambda: ar.register(adapter(adapter_id="y", trust_requirements=""), "1.0.0"), "incomplete")))
    t(g, "an_unknown_mode_is_refused", lambda: (raises(lambda: adapter(mode="TURBO"))))
    t(g, "an_unknown_adapter_gets_the_lowest_mode", lambda: (ar.mode("nobody", "9.9.9") == "OBSERVATION_ONLY"))
    t(g, "an_unqualified_adapter_cannot_be_promoted", lambda: (raises(lambda: ar.promote("mcr2-reference", "1.0.0", "SHADOW", "x", aref("A1", "mcr2-reference", "1.0.0", "SHADOW"), ascope), "qualification evidence")))
    t(g, "promotion_without_an_external_approval_reference_is_refused", lambda: (raises(lambda: ar.promote("mcr2-reference", "1.0.0", "SHADOW", H, None, ascope), "external approval") and raises(lambda: ar.promote("mcr2-reference", "1.0.0", "SHADOW", H, aref("A1", "mcr2-reference", "1.0.0", "SHADOW", source="SELF"), ascope), "external approval")))
    t(g, "promotion_must_raise_the_mode", lambda: (raises(lambda: ar.promote("mcr2-reference", "1.0.0", "OBSERVATION_ONLY", H, aref("A1", "mcr2-reference", "1.0.0", "OBSERVATION_ONLY"), ascope), "raise")))
    t(g, "a_fabricated_external_approval_reference_cannot_promote", lambda: (raises(lambda: ar.promote("mcr2-reference", "1.0.0", "SHADOW", H, {"approval_id": "FORGED", "source": "EXTERNAL_GOVERNOR"}, ascope), "missing") and ar.mode("mcr2-reference", "1.0.0") == "OBSERVATION_ONLY"))
    t(g, "a_complete_looking_forged_approval_is_refused_by_the_governor", lambda: (raises(lambda: ar.promote("mcr2-reference", "1.0.0", "SHADOW", H, aref("FORGED", "mcr2-reference", "1.0.0", "SHADOW"), ascope), "not verified") and ar.mode("mcr2-reference", "1.0.0") == "OBSERVATION_ONLY" and ar._a[("mcr2-reference", "1.0.0")].declaration["APPROVAL_STATUS"] == "NOT_APPROVED"))
    t(g, "the_default_adapter_registry_denies_every_promotion", lambda: dflt())
    t(g, "an_approval_with_the_wrong_scope_is_refused", lambda: all(raises(lambda f=f: ar.promote("mcr2-reference", "1.0.0", "SHADOW", H, aref("A1", "mcr2-reference", "1.0.0", "SHADOW", **{f: "other"}), ascope), "scope") for f in A.SCOPE_FIELDS))
    t(g, "an_approval_for_a_capability_the_adapter_does_not_support_is_refused", lambda: raises(lambda: ar.promote("mcr2-reference", "1.0.0", "SHADOW", H, aref("A1", "mcr2-reference", "1.0.0", "SHADOW", capability_id="delete_object"), dict(ascope, capability_id="delete_object")), "supports"))
    t(g, "an_approval_bound_to_another_adapter_is_refused", lambda: raises(lambda: ar.promote("mcr2-reference", "1.0.0", "SHADOW", H, aref("A1", "other-adapter", "1.0.0", "SHADOW"), ascope), "bound"))
    t(g, "an_approval_bound_to_another_version_is_refused", lambda: raises(lambda: ar.promote("mcr2-reference", "1.0.0", "SHADOW", H, aref("A1", "mcr2-reference", "9.9.9", "SHADOW"), ascope), "bound"))
    t(g, "an_approval_bound_to_another_mode_is_refused", lambda: raises(lambda: ar.promote("mcr2-reference", "1.0.0", "SHADOW", H, aref("A1", "mcr2-reference", "1.0.0", "ACTIVE"), ascope), "bound"))
    t(g, "an_approval_bound_to_another_qualification_is_refused", lambda: raises(lambda: ar.promote("mcr2-reference", "1.0.0", "SHADOW", H, aref("A1", "mcr2-reference", "1.0.0", "SHADOW", qd="b" * 64), ascope), "bound"))
    t(g, "an_expired_approval_is_refused", lambda: raises(lambda: ar.promote("mcr2-reference", "1.0.0", "SHADOW", H, aref("A1", "mcr2-reference", "1.0.0", "SHADOW", expires_at="2020-01-01"), ascope), "expired"))
    t(g, "a_malformed_expiry_is_refused", lambda: raises(lambda: ar.promote("mcr2-reference", "1.0.0", "SHADOW", H, aref("A1", "mcr2-reference", "1.0.0", "SHADOW", expires_at="soon"), ascope), "valid UTC"))
    t(g, "promotion_without_an_expected_scope_is_refused", lambda: (raises(lambda: ar.promote("mcr2-reference", "1.0.0", "SHADOW", H, aref("A1", "mcr2-reference", "1.0.0", "SHADOW")), "expected approval scope") and raises(lambda: ar.promote("mcr2-reference", "1.0.0", "SHADOW", H, aref("A1", "mcr2-reference", "1.0.0", "SHADOW"), {}), "expected approval scope")))
    t(g, "a_missing_scope_or_bound_field_is_refused", lambda: all(raises(lambda f=f: ar.promote("mcr2-reference", "1.0.0", "SHADOW", H, {k: v for k, v in aref("A1", "mcr2-reference", "1.0.0", "SHADOW").items() if k != f}, ascope)) for f in A.SCOPE_FIELDS + A.AdapterRegistry.BOUND_FIELDS + ("approval_id", "expires_at")))
    t(g, "a_non_string_scope_field_is_refused", lambda: raises(lambda: ar.promote("mcr2-reference", "1.0.0", "SHADOW", H, aref("A1", "mcr2-reference", "1.0.0", "SHADOW", owner=5), ascope), "non-empty"))
    t(g, "a_verifier_that_fails_denies", lambda: failing(Exploding()))
    t(g, "a_verifier_that_answers_loosely_denies", lambda: failing(Truthy()))
    t(g, "no_refused_promotion_changed_the_adapter", lambda: (ar.mode("mcr2-reference", "1.0.0") == "OBSERVATION_ONLY" and a1.declaration["QUALIFICATION_EVIDENCE"] is None and a1.declaration["APPROVAL_STATUS"] == "NOT_APPROVED"))
    ar.promote("mcr2-reference", "1.0.0", "SHADOW", H, aref("A1", "mcr2-reference", "1.0.0", "SHADOW"), ascope)
    t(g, "a_qualified_and_approved_adapter_can_move_to_shadow", lambda: (ar.mode("mcr2-reference", "1.0.0") == "SHADOW" and a1.declaration["APPROVAL_STATUS"].startswith("APPROVAL_REFERENCED")))
    t(g, "default_authority_stays_none_after_promotion", lambda: (a1.declaration["DEFAULT_AUTHORITY"] == "NONE"))
    ar.register(adapter(adapter_id="mcr2-reference"), "1.1.0")
    t(g, "a_newer_version_starts_again_in_observation_only", lambda: (ar.mode("mcr2-reference", "1.1.0") == "OBSERVATION_ONLY"))
    ar.revoke("mcr2-reference", "1.1.0")
    t(g, "revocation_forces_observation_only_and_blocks_promotion", lambda: (ar.mode("mcr2-reference", "1.1.0") == "OBSERVATION_ONLY" and raises(lambda: ar.promote("mcr2-reference", "1.1.0", "SHADOW", H, aref("A2", "mcr2-reference", "1.1.0", "SHADOW"), ascope), "revoked")))
    t(g, "rollback_after_a_revocation_cannot_lift_the_restriction", lambda: (ar.rollback("mcr2-reference", "1.1.0", "1.0.0") == "OBSERVATION_ONLY"))
    t(g, "rollback_to_an_unknown_version_is_refused", lambda: (raises(lambda: ar.rollback("mcr2-reference", "1.1.0", "0.0.1"), "unknown rollback")))
    t(g, "a_floor_caps_later_promotion_of_the_same_adapter", lambda: (raises(lambda: ar.promote("mcr2-reference", "1.0.0", "ACTIVE", H, aref("A3", "mcr2-reference", "1.0.0", "ACTIVE"), ascope), "caps")))
    ar2 = A.AdapterRegistry(approval_verifier=gov, clock=lambda: aclock["now"]); a2 = adapter(adapter_id="clean"); ar2.register(a2, "1.0.0"); ar2.register(adapter(adapter_id="clean"), "1.1.0")
    ar2.promote("clean", "1.1.0", "SHADOW", H, aref("A9", "clean", "1.1.0", "SHADOW"), ascope)
    t(g, "rollback_without_any_restriction_returns_the_older_versions_own_mode", lambda: (ar2.rollback("clean", "1.1.0", "1.0.0") == "OBSERVATION_ONLY" and ar2.mode("clean", "1.1.0") == "SHADOW"))
    ar3 = A.AdapterRegistry(approval_verifier=gov, clock=lambda: aclock["now"])
    ar3.register(adapter(adapter_id="life"), "1.0.0")
    ar3.promote("life", "1.0.0", "SHADOW", H, aref("A9", "life", "1.0.0", "SHADOW", expires_at="2027-01-16"), ascope)
    t(g, "a_promoted_adapter_is_shadow_while_the_approval_is_current", lambda: ar3.mode("life", "1.0.0") == "SHADOW")
    aclock["now"] = NOW + 2 * 86400
    t(g, "an_expired_approval_drops_the_adapter_back_to_observation_only", lambda: (ar3.mode("life", "1.0.0") == "OBSERVATION_ONLY" and ar3._a[("life", "1.0.0")].declaration["DEFAULT_AUTHORITY"] == "NONE"))
    aclock["now"] = NOW
    t(g, "a_current_approval_keeps_the_mode", lambda: ar3.mode("life", "1.0.0") == "SHADOW")
    gov.revoke("A9")
    t(g, "a_revoked_approval_drops_the_adapter_back_to_observation_only", lambda: ar3.mode("life", "1.0.0") == "OBSERVATION_ONLY")
    ar3.register(adapter(adapter_id="life2"), "1.0.0")
    t(g, "a_revoked_approval_cannot_promote_another_adapter", lambda: raises(lambda: ar3.promote("life2", "1.0.0", "SHADOW", H, aref("A9", "life2", "1.0.0", "SHADOW"), ascope), "not verified"))
    ar2.register(adapter(adapter_id="third"), "1.0.0")
    t(g, "a_used_approval_does_not_transfer_to_another_adapter", lambda: raises(lambda: ar2.promote("third", "1.0.0", "SHADOW", H, aref("A9", "clean", "1.1.0", "SHADOW"), ascope), "bound") and ar2.mode("third", "1.0.0") == "OBSERVATION_ONLY")
    t(g, "reregistering_an_adapter_drops_its_stored_approval", lambda: (ar3.register(adapter(adapter_id="life"), "1.0.0"), ar3._approval.get(("life", "1.0.0")) is None and ar3.mode("life", "1.0.0") == "OBSERVATION_ONLY")[1])


def _qualified(reg):
    c = reg.discover("create_object", "1.0.0", H)
    reg.verify(c, H, True)
    reg.qualify(c, H, "GO", "r")
    return c


def main(argv):
    run()
    failed = sorted(n for n, ok in T.items() if not ok)
    groups = {gk: "PASS" if all(T[n] for n in names) else "FAIL" for gk, names in G.items()}
    digest = hashlib.sha256(json.dumps(sorted(T), separators=(",", ":")).encode()).hexdigest().upper()
    result = {"stage": "MCR3_PROVENANCE_AUTHORITY", "evidence_class": "SYNTHETIC/LOCAL", "tests": len(T), "failed": failed, "groups": groups, "tests_digest": digest,
              "not_verified": NOT_VERIFIED, "network_calls": 0}
    out = json.dumps(result, indent=2, sort_keys=True)
    if "--out" in argv:
        with open(argv[argv.index("--out") + 1], "w", newline="\n") as fh:
            fh.write(out + "\n")
    print(out)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
