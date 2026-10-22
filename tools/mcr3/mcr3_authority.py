"""MCR 3.0 capability and adapter governance: states, transitions, and the rule that qualification never approves.

  DISCOVERED -> QUARANTINED -> VERIFIED -> QUALIFIED -> APPROVED ;  any state -> SUSPENDED, REVOKED (REVOKED is final)

MCR does NOT own approval. An approval is a record issued elsewhere (the Claude Mods Governor, in the intended
deployment); this module only checks that a presented approval record is complete, verified by a pluggable
`ApprovalVerifier`, and scoped to exactly the owner, capability, provider, target, operation, environment, policy
digest and expiry it is being used for. Nothing here executes anything. `view()` reports what MCR knows; the
authority to execute stays with the external approver ("INTEROPERABILITY_DOES_NOT_IMPLY_AUTHORITY").
"""
import copy

import evc1

STATES = evc1.CAPABILITY_STATES
FORWARD = {
    "DISCOVERED": {"QUARANTINED"},
    "QUARANTINED": {"VERIFIED"},
    "VERIFIED": {"QUALIFIED"},
    "QUALIFIED": {"APPROVED"},
    "APPROVED": set(),
    "SUSPENDED": {"VERIFIED"},          # re-verification is required before anything above it can return
    "REVOKED": set(),
}
SCOPE_FIELDS = ("owner", "capability_id", "provider_id", "target_system", "operation", "environment", "policy_digest")
ADAPTER_MODES = ("OBSERVATION_ONLY", "SHADOW", "ACTIVE")


class AuthorityError(ValueError):
    pass


class ApprovalVerifier:
    """Interface to the EXTERNAL approver. verify(record) -> True only if the approval is genuine."""
    def verify(self, record):             # pragma: no cover (interface)
        raise NotImplementedError


class DenyAllApprovalVerifier(ApprovalVerifier):
    """The default: nothing is approved because no external approver is connected."""
    def verify(self, record):
        return False


class RecordedApprovalVerifier(ApprovalVerifier):
    """TEST/MOCK: accepts a record whose approval_id is in a set the mock Governor issued."""
    def __init__(self, issued):
        self.issued = set(issued)

    def revoke(self, approval_id):
        self.issued.discard(approval_id)

    def verify(self, record):
        return record.get("approval_id") in self.issued


class Capability:
    def __init__(self, capability_id, version, digest):
        self.capability_id, self.version, self.digest = capability_id, version, digest
        self.state = "DISCOVERED"
        self.history = [("DISCOVERED", None)]
        self.qualification = None
        self.approval = None
        self.suspended_from = None

    def key(self):
        return (self.capability_id, self.version, self.digest)


class CapabilityRegistry:
    def __init__(self, approval_verifier=None, clock=None):
        import time
        self.approval_verifier = approval_verifier or DenyAllApprovalVerifier()
        self.clock = clock or time.time
        self._caps = {}
        self.policy_epoch = 0

    # ---- discovery: anything unknown is quarantined, never trusted
    def discover(self, capability_id, version, digest):
        if not (isinstance(capability_id, str) and capability_id and isinstance(version, str) and version and isinstance(digest, str) and len(digest) == 64):
            raise AuthorityError("capability identity needs an id, a version and a 64-hex content digest")
        key = (capability_id, version, digest)
        if key not in self._caps:
            self._caps[key] = Capability(*key)
        c = self._caps[key]
        if c.state == "DISCOVERED":
            self._move(c, "QUARANTINED", "unknown capability quarantined on discovery")
        return c

    def get(self, capability_id, version, digest):
        c = self._caps.get((capability_id, version, digest))
        if c is None:
            raise AuthorityError("unknown capability")
        return c

    def _move(self, c, to, why):
        if c.state == "REVOKED":
            raise AuthorityError("revoked capabilities are final")
        if to not in FORWARD[c.state]:
            raise AuthorityError("illegal capability transition %s -> %s" % (c.state, to))
        c.history.append((to, why))
        c.state = to

    # ---- verification and qualification: evidence in, never approval out
    def verify(self, c, verification_digest, passed):
        if c.state != "QUARANTINED" and not (c.state == "SUSPENDED"):
            raise AuthorityError("only a quarantined or suspended capability is verified")
        if not passed or not _hex64(verification_digest):
            raise AuthorityError("verification did not pass or carries no evidence digest")
        c.suspended_from = None
        self._move(c, "VERIFIED", "verified")

    def qualify(self, c, qualification_digest, reviewer_verdict, reviewer):
        if reviewer_verdict not in ("GO", "GO_WITH_DOCUMENTED_GAPS"):
            raise AuthorityError("qualification needs an independent GO or GO_WITH_DOCUMENTED_GAPS verdict, not %r" % (reviewer_verdict,))
        if not _hex64(qualification_digest) or not isinstance(reviewer, str) or not reviewer:
            raise AuthorityError("qualification needs an evidence digest and a named reviewer")
        self._move(c, "QUALIFIED", "qualified by %s: %s" % (reviewer, reviewer_verdict))
        c.qualification = {"digest": qualification_digest, "verdict": reviewer_verdict, "reviewer": reviewer}
        # NOTE: qualification stops here. There is deliberately no code path from QUALIFIED to APPROVED except record_approval.

    # ---- approval: an external record, verified and scope-matched
    def record_approval(self, c, record):
        if c.state != "QUALIFIED":
            raise AuthorityError("only a QUALIFIED capability can receive an approval record (state %s)" % c.state)
        self._check_record(c, record, require_unexpired=True)
        if not self.approval_verifier.verify(record):
            raise AuthorityError("approval record was not verified by the external approver")
        self._move(c, "APPROVED", "approval %s referenced" % record["approval_id"])
        c.approval = copy.deepcopy(record)

    def _check_record(self, c, record, require_unexpired):
        if not isinstance(record, dict):
            raise AuthorityError("approval record must be an object")
        need = ("approval_id",) + SCOPE_FIELDS + ("expires_at",)
        missing = [k for k in need if k not in record]
        if missing:
            raise AuthorityError("approval record is missing %s" % missing)
        if not all(isinstance(record[k], str) and record[k] for k in ("approval_id",) + SCOPE_FIELDS):
            raise AuthorityError("approval record fields must be non-empty strings")
        if record["capability_id"] != c.capability_id:
            raise AuthorityError("approval is for another capability")
        exp = _expiry(record["expires_at"])
        if exp is None:
            raise AuthorityError("approval expires_at is not a valid UTC time")
        if require_unexpired and self.clock() >= exp:
            raise AuthorityError("approval already expired")

    def _approval_scope_matches(self, c, scope):
        a = c.approval
        return a is not None and all(a[k] == scope.get(k) for k in SCOPE_FIELDS)

    # ---- suspension and revocation
    def suspend(self, c, why):
        if c.state == "REVOKED":
            raise AuthorityError("revoked capabilities are final")
        if c.state == "SUSPENDED":
            return
        c.suspended_from = c.state
        c.history.append(("SUSPENDED", why))
        c.state = "SUSPENDED"
        c.approval = None                          # an approval does not survive suspension

    def revoke(self, c, why):
        c.history.append(("REVOKED", why))
        c.state = "REVOKED"
        c.approval = None

    def raise_policy_epoch(self):
        """A stricter policy: every existing approval stops counting until it is presented again under the new epoch."""
        self.policy_epoch += 1
        for c in self._caps.values():
            if c.state == "APPROVED":
                c.history.append(("QUALIFIED", "policy epoch %d: approval no longer current" % self.policy_epoch))
                c.state = "QUALIFIED"
                c.approval = None

    # ---- what MCR knows (never an authority grant)
    def effective_state(self, c):
        if c.state == "APPROVED" and c.approval is not None:
            exp = _expiry(c.approval["expires_at"])
            if exp is None or self.clock() >= exp:
                return "QUALIFIED"                  # an expired approval silently lapses to QUALIFIED
        return c.state

    def view(self, c, scope=None):
        st = self.effective_state(c)
        scoped = st == "APPROVED" and scope is not None and self._approval_scope_matches(c, scope)      # review 8: no scope given, no reference
        return {"capability_id": c.capability_id, "state": st, "approval_reference_present": bool(scoped),
                "authority_source": "EXTERNAL_GOVERNOR" if scoped else None, "mcr_grants_authority": False,
                "may_request_execution_review": bool(scoped)}


class Adapter:
    """Declaration every adapter must publish. DEFAULT_AUTHORITY is always NONE; a new adapter starts OBSERVATION_ONLY."""
    def __init__(self, adapter_id, source_runtime_version, target_contract_version, supported_capabilities, evidence_classification,
                 trust_requirements, qualification_evidence=None, approval_status="NOT_APPROVED", revocation_status="NOT_REVOKED",
                 mode="OBSERVATION_ONLY", limitations=()):
        if mode not in ADAPTER_MODES:
            raise AuthorityError("unknown adapter mode")
        self.declaration = {
            "ADAPTER_ID": adapter_id, "SOURCE_RUNTIME_VERSION": source_runtime_version, "TARGET_CONTRACT_VERSION": target_contract_version,
            "SUPPORTED_CAPABILITIES": sorted(supported_capabilities), "EVIDENCE_CLASSIFICATION": evidence_classification,
            "TRUST_REQUIREMENTS": trust_requirements, "QUALIFICATION_EVIDENCE": qualification_evidence, "APPROVAL_STATUS": approval_status,
            "REVOCATION_STATUS": revocation_status, "DEFAULT_AUTHORITY": "NONE", "MODE": mode, "LIMITATIONS": list(limitations),
        }

    def complete(self):
        d = self.declaration
        return all(d[k] not in (None, "", []) for k in ("ADAPTER_ID", "SOURCE_RUNTIME_VERSION", "TARGET_CONTRACT_VERSION", "SUPPORTED_CAPABILITIES",
                                                        "EVIDENCE_CLASSIFICATION", "TRUST_REQUIREMENTS")) and d["DEFAULT_AUTHORITY"] == "NONE"


class AdapterRegistry:
    """Tracks adapters by (id, version). Promotion beyond OBSERVATION_ONLY needs qualification evidence AND an approval record
    that the EXTERNAL approver verifies (fail closed: default verifier denies everything), that is complete, unexpired, scoped
    to the exact owner, capability, provider, target, operation, environment and policy digest the caller expects, and bound to
    this adapter, version, target mode and qualification digest. The approval is re-checked every time the mode is read, so an
    expired or revoked approval drops the adapter back to OBSERVATION_ONLY. A downgrade or rollback can never re-grant a mode a
    revoked or newer-restricted record withdrew."""
    BOUND_FIELDS = ("adapter_id", "adapter_version", "to_mode", "qualification_digest")

    def __init__(self, approval_verifier=None, clock=None):
        import time
        self.approval_verifier = approval_verifier or DenyAllApprovalVerifier()
        self.clock = clock or time.time
        self._a = {}
        self._approval = {}                      # (adapter_id, version) -> the verified approval record behind the current mode
        self.floor = {}                          # adapter_id -> most restrictive mode ever imposed by a revocation or suspension

    def register(self, adapter, version):
        key = (adapter.declaration["ADAPTER_ID"], version)
        if not adapter.complete():
            raise AuthorityError("adapter declaration incomplete or default authority is not NONE")
        if adapter.declaration["MODE"] != "OBSERVATION_ONLY":
            raise AuthorityError("a new adapter registers in OBSERVATION_ONLY mode")
        self._a[key] = adapter
        self._approval.pop(key, None)
        return adapter

    def _approval_current(self, key, record):
        """True only if the record is unexpired now and the external approver still verifies it (fail closed on any error)."""
        exp = _expiry(record.get("expires_at"))
        if exp is None or self.clock() >= exp:
            return False
        try:
            return self.approval_verifier.verify(copy.deepcopy(record)) is True
        except Exception:
            return False

    def mode(self, adapter_id, version):
        a = self._a.get((adapter_id, version))
        if a is None:
            return "OBSERVATION_ONLY"                    # unknown adapters get the lowest mode
        if a.declaration["REVOCATION_STATUS"] != "NOT_REVOKED":
            return "OBSERVATION_ONLY"
        declared = a.declaration["MODE"]
        if declared != "OBSERVATION_ONLY":
            rec = self._approval.get((adapter_id, version))
            if rec is None or not self._approval_current((adapter_id, version), rec):
                return "OBSERVATION_ONLY"                # no current verified approval behind the mode: it lapses
        order = {m: i for i, m in enumerate(ADAPTER_MODES)}
        cap = self.floor.get(adapter_id)                 # review 8: a recorded restriction caps every version of the adapter
        return declared if cap is None or order[declared] <= order[cap] else cap

    def _check_promotion_approval(self, a, adapter_id, version, to_mode, qualification_digest, record, expected_scope):
        if not isinstance(record, dict) or not record.get("approval_id") or record.get("source") != "EXTERNAL_GOVERNOR":
            raise AuthorityError("promotion needs an external approval reference")
        if not isinstance(expected_scope, dict) or not all(isinstance(expected_scope.get(k), str) and expected_scope.get(k) for k in SCOPE_FIELDS):
            raise AuthorityError("promotion needs the expected approval scope (%s)" % ", ".join(SCOPE_FIELDS))
        need = ("approval_id",) + SCOPE_FIELDS + self.BOUND_FIELDS + ("expires_at",)
        missing = [k for k in need if k not in record]
        if missing:
            raise AuthorityError("approval record is missing %s" % missing)
        if not all(isinstance(record[k], str) and record[k] for k in ("approval_id",) + SCOPE_FIELDS + self.BOUND_FIELDS):
            raise AuthorityError("approval record fields must be non-empty strings")
        if any(record[k] != expected_scope[k] for k in SCOPE_FIELDS):
            raise AuthorityError("approval scope does not match the expected scope")
        supported = a.declaration["SUPPORTED_CAPABILITIES"]
        if "*" not in supported and record["capability_id"] not in supported:
            raise AuthorityError("approval capability is not one this adapter supports")
        if (record["adapter_id"], record["adapter_version"], record["to_mode"], record["qualification_digest"]) != (adapter_id, version, to_mode, qualification_digest):
            raise AuthorityError("approval is bound to another adapter, version, mode or qualification")
        exp = _expiry(record["expires_at"])
        if exp is None:
            raise AuthorityError("approval expires_at is not a valid UTC time")
        if self.clock() >= exp:
            raise AuthorityError("approval already expired")
        try:
            ok = self.approval_verifier.verify(copy.deepcopy(record)) is True
        except Exception:
            ok = False
        if not ok:
            raise AuthorityError("approval record was not verified by the external approver")

    def promote(self, adapter_id, version, to_mode, qualification_digest, approval_record, expected_scope=None):
        a = self._a.get((adapter_id, version))
        if a is None:
            raise AuthorityError("unknown adapter")
        if a.declaration["REVOCATION_STATUS"] != "NOT_REVOKED":
            raise AuthorityError("revoked adapters cannot be promoted")
        order = {m: i for i, m in enumerate(ADAPTER_MODES)}
        if to_mode not in order or order[to_mode] <= order[a.declaration["MODE"]]:
            raise AuthorityError("promotion must raise the mode")
        if not _hex64(qualification_digest):
            raise AuthorityError("promotion needs qualification evidence")
        self._check_promotion_approval(a, adapter_id, version, to_mode, qualification_digest, approval_record, expected_scope)
        if order[to_mode] > order.get(self.floor.get(adapter_id, "ACTIVE"), 2):
            raise AuthorityError("a restriction recorded for this adapter caps its mode")
        a.declaration["QUALIFICATION_EVIDENCE"] = qualification_digest
        a.declaration["APPROVAL_STATUS"] = "APPROVAL_REFERENCED:" + approval_record["approval_id"]
        a.declaration["MODE"] = to_mode
        self._approval[(adapter_id, version)] = copy.deepcopy(approval_record)

    def revoke(self, adapter_id, version):
        a = self._a.get((adapter_id, version))
        if a is None:
            raise AuthorityError("unknown adapter")
        a.declaration["REVOCATION_STATUS"] = "REVOKED"
        a.declaration["MODE"] = "OBSERVATION_ONLY"
        self.floor[adapter_id] = "OBSERVATION_ONLY"

    def rollback(self, adapter_id, from_version, to_version):
        """Selecting an older version never lifts a restriction: the older record's own mode and revocation apply,
        and a recorded floor for the adapter still caps it."""
        if (adapter_id, to_version) not in self._a:
            raise AuthorityError("unknown rollback target")
        return self.mode(adapter_id, to_version)          # mode() already applies any recorded restriction


def adapter_approval_record(approval_id, scope, adapter_id, adapter_version, to_mode, qualification_digest, expires_at="2099-01-01"):
    """Builds the SHAPE of an adapter-promotion approval (what an external approver would issue). It is not an approval:
    only the registry's ApprovalVerifier decides whether a record is genuine."""
    r = dict(scope)
    r.update(approval_id=approval_id, source="EXTERNAL_GOVERNOR", adapter_id=adapter_id, adapter_version=adapter_version,
             to_mode=to_mode, qualification_digest=qualification_digest, expires_at=expires_at)
    return r


def _hex64(s):
    return isinstance(s, str) and len(s) == 64 and all(c in "0123456789abcdef" for c in s)


def _expiry(v):
    import mcr3_model
    return mcr3_model.parse_expiry(v)
