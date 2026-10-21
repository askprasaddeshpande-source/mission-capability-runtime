"""MCR 3.0 evidence provenance: seven things that are NOT interchangeable.

  1 hash correctness      the event's own integrity digest matches its content
  2 signature validity    a signature over a canonical message verifies under a named key
  3 producer identity     the key belongs to a named signer
  4 provider trust        the signer is a TRUSTED issuer under the verifier's policy (and not revoked)
  5 evidence freshness    the attestation is not older than the policy allows and has not expired
  6 delegated authority   NOT decided here: a verdict from this module never grants, widens or transfers authority
  7 outcome validation    NOT decided here: a signature is not proof that a business outcome occurred

The module produces an evc1 `provenance` record; `evc1.derive_trust` turns it into a trust level. Verification
back-ends are pluggable (`SignatureVerifier`). Back-ends shipped:
  HmacTestVerifier   symmetric, TEST ONLY (cannot prove a producer identity to a third party)
  Ed25519Verifier    public-key, needs the optional `cryptography` package
  SshSigVerifier     `ssh-keygen -Y verify` against an allowed_signers file (the mechanism Claude Mods uses for releases)
No production signing key is created or deployed by this module; tests create throwaway identities in temp folders.
"""
import base64
import hashlib
import hmac
import os
import shutil
import subprocess
import tempfile
import time as _time
import calendar

import evc1

NAMESPACE = "mcr-evidence"
ALGS = ("HMAC-SHA256-TEST", "ED25519", "SSHSIG-ED25519")


def _epoch(ts):
    """RFC 3339 UTC 'YYYY-MM-DDTHH:MM:SS[.fff]Z' -> epoch seconds, or None."""
    if not isinstance(ts, str) or not ts.endswith("Z"):
        return None
    try:
        core = ts[:-1].split(".")[0]
        return calendar.timegm(_time.strptime(core, "%Y-%m-%dT%H:%M:%S"))
    except ValueError:
        return None


def signed_message(event_digest, signed_at, signer, policy_digest=None, authority_digest=None):
    """The bytes that are signed. They bind the event digest, the signing time, the signer, and (when the signer
    wants them bound) the policy and authority digests, so changing any of those invalidates the signature."""
    return evc1.canonical_bytes({"namespace": NAMESPACE, "event_digest": event_digest, "signed_at": signed_at, "signer": signer,
                                 "policy_digest": policy_digest, "authority_digest": authority_digest})


class VerifyResult:
    def __init__(self, valid, signer=None, reason=""):
        self.valid, self.signer, self.reason = bool(valid), signer, reason


class SignatureVerifier:
    alg = None

    def verify(self, message, attestation):               # pragma: no cover (interface)
        raise NotImplementedError


class HmacTestVerifier(SignatureVerifier):
    """TEST ONLY. A shared-secret MAC proves nothing about identity to anyone who also holds the secret."""
    alg = "HMAC-SHA256-TEST"
    TEST_ONLY = True

    def __init__(self, keys):
        self.keys = dict(keys)

    def sign(self, signer, message):
        return base64.b64encode(hmac.new(self.keys[signer], message, hashlib.sha256).digest()).decode()

    def verify(self, message, attestation):
        signer = attestation.get("signer")
        if attestation.get("alg") != self.alg or signer not in self.keys:
            return VerifyResult(False, signer, "unknown signer or algorithm")
        try:
            want = hmac.new(self.keys[signer], message, hashlib.sha256).digest()
            got = base64.b64decode(attestation.get("sig", ""), validate=True)
        except Exception:
            return VerifyResult(False, signer, "malformed signature")
        return VerifyResult(hmac.compare_digest(want, got), signer, "" if hmac.compare_digest(want, got) else "signature mismatch")


class Ed25519Verifier(SignatureVerifier):
    alg = "ED25519"

    def __init__(self, public_keys):
        """public_keys: signer -> 32 raw public-key bytes."""
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        self._keys = {s: Ed25519PublicKey.from_public_bytes(k) for s, k in public_keys.items()}

    def verify(self, message, attestation):
        from cryptography.exceptions import InvalidSignature
        signer = attestation.get("signer")
        if attestation.get("alg") != self.alg or signer not in self._keys:
            return VerifyResult(False, signer, "unknown signer or algorithm")
        try:
            self._keys[signer].verify(base64.b64decode(attestation.get("sig", ""), validate=True), message)
            return VerifyResult(True, signer)
        except (InvalidSignature, ValueError, TypeError):
            return VerifyResult(False, signer, "signature mismatch")


class SshSigVerifier(SignatureVerifier):
    """Verifies an SSH signature (`ssh-keygen -Y verify`) against an allowed_signers file. The signature in the
    attestation is the armoured SSHSIG text."""
    alg = "SSHSIG-ED25519"

    def __init__(self, allowed_signers_path, ssh_keygen=None):
        self.allowed = allowed_signers_path
        self.tool = ssh_keygen or shutil.which("ssh-keygen")
        if not self.tool:
            raise RuntimeError("ssh-keygen not available")

    def verify(self, message, attestation):
        signer = attestation.get("signer")
        if attestation.get("alg") != self.alg or not isinstance(attestation.get("sig"), str):
            return VerifyResult(False, signer, "unknown algorithm")
        d = tempfile.mkdtemp(prefix="m3sig_")
        try:
            sigp = os.path.join(d, "m.sig")
            with open(sigp, "w", newline="\n") as fh:
                fh.write(attestation["sig"])
            r = subprocess.run([self.tool, "-Y", "verify", "-f", self.allowed, "-I", str(signer), "-n", NAMESPACE, "-s", sigp],
                               input=message, capture_output=True, timeout=30)
            return VerifyResult(r.returncode == 0, signer, "" if r.returncode == 0 else "signature mismatch")
        except (OSError, subprocess.SubprocessError):
            return VerifyResult(False, signer, "verifier unavailable")
        finally:
            shutil.rmtree(d, ignore_errors=True)


def ssh_sign(private_key_path, message, ssh_keygen=None):
    """Test helper: sign with a throwaway key using ssh-keygen -Y sign. Returns the armoured signature text."""
    tool = ssh_keygen or shutil.which("ssh-keygen")
    d = tempfile.mkdtemp(prefix="m3sign_")
    try:
        mp = os.path.join(d, "m")
        with open(mp, "wb") as fh:
            fh.write(message)
        r = subprocess.run([tool, "-Y", "sign", "-f", private_key_path, "-n", NAMESPACE, mp], capture_output=True, timeout=30)
        if r.returncode != 0:
            raise RuntimeError("signing failed")
        return open(mp + ".sig", "r", encoding="ascii").read()
    finally:
        shutil.rmtree(d, ignore_errors=True)


class ReplayCache:
    """Remembers (signer, event digest, signed_at) triples that were accepted once. In-memory; a deployment that needs
    replay protection across restarts must supply a durable cache with the same interface."""
    def __init__(self):
        self._seen = set()

    def seen(self, key):
        return key in self._seen

    def add(self, key):
        self._seen.add(key)


class TrustPolicy:
    """issuers: signer -> {"status": "TRUSTED"|"UNTRUSTED", "not_before": epoch|None, "not_after": epoch|None}.
    revoked: signers whose evidence loses trusted status regardless of the issuer table. max_age_seconds bounds how
    old an attestation may be. A signer absent from the table is UNKNOWN (not trusted)."""
    def __init__(self, issuers=None, revoked=(), max_age_seconds=3600, clock=None, expected_policy_digest=None, expected_authority_digest=None):
        self.issuers = dict(issuers or {})
        self.revoked = set(revoked)
        self.max_age = max_age_seconds
        self.clock = clock or _time.time
        self.expected_policy_digest = expected_policy_digest
        self.expected_authority_digest = expected_authority_digest

    def issuer_trust(self, signer, at):
        if signer in self.revoked:
            return "REVOKED"
        rec = self.issuers.get(signer)
        if rec is None:
            return "UNKNOWN"
        if rec.get("status") != "TRUSTED":
            return "UNTRUSTED"
        if (rec.get("not_before") is not None and at < rec["not_before"]) or (rec.get("not_after") is not None and at > rec["not_after"]):
            return "UNTRUSTED"
        return "TRUSTED"


def make_attestation(event, signer, signer_backend, *, signed_at, policy_digest=None, authority_digest=None, alg=None):
    """Produce an attestation over the event's integrity digest. signer_backend needs .sign(signer, message)
    (HmacTestVerifier) or, for SSH, pass `sig` explicitly via make_attestation_with_signature."""
    digest = evc1.content_digest(event)
    msg = signed_message(digest, signed_at, signer, policy_digest, authority_digest)
    return {"signer": signer, "alg": alg or signer_backend.alg, "sig": signer_backend.sign(signer, msg), "signed_at": signed_at,
            "event_digest": digest, "policy_digest": policy_digest, "authority_digest": authority_digest}


def make_attestation_with_signature(event, signer, alg, sig, signed_at, policy_digest=None, authority_digest=None):
    return {"signer": signer, "alg": alg, "sig": sig, "signed_at": signed_at, "event_digest": evc1.content_digest(event),
            "policy_digest": policy_digest, "authority_digest": authority_digest}


def assess(event, attestation, verifier, policy, replay_cache=None, record_replay=True):
    """Return an evc1 provenance record for `event`. Never raises for hostile input; a failure is a weaker record.
    The record says nothing about authority or about whether the business outcome occurred."""
    try:
        return _assess(event, attestation, verifier, policy, replay_cache, record_replay)
    except Exception:
        weak = evc1.unsigned_provenance()
        weak["hash_consistent"] = False
        return weak


def _assess(event, attestation, verifier, policy, replay_cache, record_replay):
    prov = evc1.unsigned_provenance()
    body = {k: v for k, v in event.items() if k != "integrity"}
    try:
        prov["hash_consistent"] = event.get("integrity", {}).get("event_digest") == evc1.digest_of(body)
    except ValueError:
        prov["hash_consistent"] = False
    if not isinstance(attestation, dict):
        return prov
    signer = attestation.get("signer") if isinstance(attestation.get("signer"), str) else None
    prov["signer"], prov["verified_by"] = signer, type(verifier).__name__
    signed_at = attestation.get("signed_at")
    at = _epoch(signed_at)
    try:
        content = evc1.content_digest(event)
    except (KeyError, TypeError, ValueError):
        content = None
    msg_ok = prov["hash_consistent"] and content is not None and attestation.get("event_digest") == content and at is not None
    if msg_ok:
        # the signed message binds the policy and authority digests the signer claims; the verifier policy may pin them
        pd, ad = attestation.get("policy_digest"), attestation.get("authority_digest")
        if policy.expected_policy_digest is not None and pd != policy.expected_policy_digest:
            msg_ok = False
        if policy.expected_authority_digest is not None and ad != policy.expected_authority_digest:
            msg_ok = False
    if not msg_ok:
        prov["signature"] = "INVALID"
        return prov
    res = verifier.verify(signed_message(attestation["event_digest"], signed_at, signer, attestation.get("policy_digest"), attestation.get("authority_digest")), attestation)
    prov["signature"] = "VALID" if res.valid else "INVALID"
    if not res.valid:
        return prov
    prov["issuer_trust"] = policy.issuer_trust(signer, at)
    now = policy.clock()
    prov["freshness"] = "FRESH" if 0 <= now - at <= policy.max_age else "EXPIRED"
    if replay_cache is not None:
        key = (signer, attestation["event_digest"], signed_at)   # content digest: re-sealing with a verdict does not hide a replay
        if replay_cache.seen(key):
            prov["replay"] = "REPLAYED"
        else:
            prov["replay"] = "NOT_SEEN"
            if record_replay and prov["issuer_trust"] == "TRUSTED" and prov["freshness"] == "FRESH":
                replay_cache.add(key)
    return prov


def attach(event, provenance):
    """Return a re-sealed copy of the event carrying the provenance and the trust derived from it."""
    e = {k: v for k, v in event.items() if k != "integrity"}
    e["evidence"] = dict(e["evidence"], provenance=provenance, trust=evc1.derive_trust(provenance))
    return evc1.seal(e)
