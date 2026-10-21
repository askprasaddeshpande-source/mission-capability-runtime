"""MCR Evidence Contract v1 ("mcr-evidence/1"): a canonical, version-independent evidence envelope.

The contract is versioned separately from every MCR runtime release. Vocabulary is borrowed, not imported:
CloudEvents 1.0.2 (id, type, source, time, subject-like digests), in-toto Attestation Framework v1 (subject digests,
typed predicate), OpenTelemetry attribute naming (snake_case, nullable-unknown), MCP authorization 2025-06-18 (scope
and resource vocabulary), OWASP agentic-AI threat guidance (checked as a test list, not a dependency). No library
beyond the standard library is required.

Five layers are kept apart and a type belongs to exactly one:
  OCCURRENCE               something happened (an attempt was made, a state changed)
  RECEIPT                  a party reported something (a provider call result, a readback, a commit reading)
  VERIFIED_FACT            an independent check of ANOTHER event's integrity/provenance (never a business outcome)
  BUSINESS_OUTCOME         an evaluation of expected against observed outcome, or a mission disposition
  AUTHORIZATION_REFERENCE  a pointer to an approval made elsewhere; carries no authority
`authority_effect` is the constant "NONE": no evidence event grants, widens or transfers authority.
"""
import copy
import hashlib
import json
import re

CONTRACT = "mcr-evidence/1"
SUPPORTED_MAJOR = 1
CURRENT_MINOR = 0
CURRENT_VERSION = "1.0.0"
SPEC_PINS = {"cloudevents": "1.0.2", "in-toto-attestation": "v1", "mcp-authorization": "2025-06-18",
             "opentelemetry-semantic-conventions": "attribute naming only (no SDK)", "owasp": "Top 10 for Agentic Applications / Agentic AI Threats and Mitigations (checklist, not a dependency)"}

LAYERS = ("OCCURRENCE", "RECEIPT", "VERIFIED_FACT", "BUSINESS_OUTCOME", "AUTHORIZATION_REFERENCE")
EVIDENCE_CLASSES = ("OBSERVED", "READBACK", "CORROBORATED", "CLAIMED", "INFERRED", "HISTORICAL", "SYNTHETIC", "UNKNOWN")
TRUST_LEVELS = ("UNTRUSTED_RESEARCH", "SIGNATURE_INVALID", "SIGNED_UNTRUSTED", "SIGNED_TRUSTED", "REVOKED", "EXPIRED", "REPLAYED")
SIGNATURE_STATES = ("ABSENT", "INVALID", "VALID")
ISSUER_TRUST = ("UNKNOWN", "UNTRUSTED", "TRUSTED", "REVOKED")
FRESHNESS = ("UNKNOWN", "FRESH", "EXPIRED")
REPLAY = ("UNKNOWN", "NOT_SEEN", "REPLAYED")
CAPABILITY_STATES = ("DISCOVERED", "QUARANTINED", "VERIFIED", "QUALIFIED", "APPROVED", "SUSPENDED", "REVOKED")
CALL_CLASSES = ("CALL_NOT_SENT", "CALL_SENT_NO_RESPONSE", "PROVIDER_ERROR", "PROVIDER_RESPONSE_SUCCESS", "COMMIT_UNKNOWN",
                "COMMIT_CONFIRMED", "OUTCOME_FAILED", "OUTCOME_VALIDATED")
SOURCE_LEVELS = ("AUTHORITATIVE_REPOSITORY", "PROVIDER_VALIDATION", "PROVIDER_LOG", "TRANSPORT_SUCCESS", "CACHED_OUTPUT",
                 "LOCAL_RUNNER_STATE", "INFERRED_OR_REGEX")
OUTCOME_CLASSES = ("EXECUTED", "PROVIDER_ACKNOWLEDGED", "COMMIT_OBSERVED", "OUTCOME_OBSERVED", "OUTCOME_VALIDATED", "COMPLETE",
                   "COMMIT_UNKNOWN", "OUTCOME_UNKNOWN", "COMPENSATION_REQUIRED", "UNRECOVERABLE")
DISPOSITIONS = ("COMPLETE", "INCOMPLETE", "COMMIT_UNKNOWN", "OUTCOME_UNKNOWN", "FAILED", "COMPENSATED", "COMPENSATION_REQUIRED",
                "UNRECOVERABLE", "NOT_APPLICABLE")
VERIFY_SCOPES = ("HASH", "SIGNATURE", "PRODUCER_IDENTITY", "PROVIDER_TRUST", "FRESHNESS")
TRI = ("PASS", "FAIL", "UNKNOWN")

# type -> (claim kind, layer)
TYPE_TABLE = {
    "mcr.mission.started": ("MISSION_STARTED", "OCCURRENCE"),
    "mcr.authorization.referenced": ("AUTHORIZATION_REFERENCE", "AUTHORIZATION_REFERENCE"),
    "mcr.capability.state_changed": ("CAPABILITY_STATE_CHANGED", "OCCURRENCE"),
    "mcr.mutation.attempted": ("MUTATION_ATTEMPTED", "OCCURRENCE"),
    "mcr.execution.receipt": ("EXECUTION_RECEIPT", "RECEIPT"),
    "mcr.commit.observed": ("COMMIT_OBSERVATION", "RECEIPT"),
    "mcr.readback.claimed": ("READBACK_CLAIM", "RECEIPT"),
    "mcr.outcome.evaluated": ("OUTCOME_EVALUATION", "BUSINESS_OUTCOME"),
    "mcr.compensation.attempted": ("COMPENSATION_ATTEMPT", "OCCURRENCE"),
    "mcr.mission.disposition": ("MISSION_DISPOSITION", "BUSINESS_OUTCOME"),
    "mcr.evidence.verified": ("EVIDENCE_VERIFICATION", "VERIFIED_FACT"),
}
KNOWN_CRITICAL = frozenset()          # extension names this consumer understands; v1.0 defines none
ID_RE = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{7,127}$"          # event ids (idempotency keys): 8 to 128 characters
ENTITY_ID_RE = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$"  # mission, transaction, correlation, attempt ids
HASH_RE = r"^[0-9a-f]{64}$"
VERSION_RE = r"^[0-9]+\.[0-9]+\.[0-9]+$"
_HASH = {"type": "string", "pattern": HASH_RE}
_NHASH = {"type": ["string", "null"], "pattern": HASH_RE}
_NSTR = {"type": ["string", "null"], "minLength": 1, "maxLength": 256}
_STR = {"type": "string", "minLength": 1, "maxLength": 256}
_NID = {"type": ["string", "null"], "pattern": ENTITY_ID_RE}
_COUNT = {"type": "integer", "minimum": 0}


def _obj(props, required=None, extra=False):
    return {"type": "object", "properties": props, "required": list(props) if required is None else required, "additionalProperties": extra}


def _claim(kind, layer, props, required=None):
    p = {"kind": {"const": kind}, "layer": {"const": layer}}
    p.update(props)
    return _obj(p, required)


def build_schema():
    """The JSON Schema (2020-12 subset) for contract 1.x. Single source of truth; the checked-in file is generated."""
    claims = [
        _claim("MISSION_STARTED", "OCCURRENCE", {"intent_digest": _HASH, "target_system": _STR}),
        _claim("AUTHORIZATION_REFERENCE", "AUTHORIZATION_REFERENCE", {"referenced": {"type": "boolean"}}),
        _claim("CAPABILITY_STATE_CHANGED", "OCCURRENCE", {"from_state": {"enum": list(CAPABILITY_STATES)}, "to_state": {"enum": list(CAPABILITY_STATES)},
                                                           "reason": _STR, "approval_required": {"type": "boolean"}}),
        _claim("MUTATION_ATTEMPTED", "OCCURRENCE", {"attempt_id": {"type": "string", "pattern": ENTITY_ID_RE}, "attempt_number": {"type": "integer", "minimum": 1},
                                                    "budget_remaining_after": _COUNT, "budget_kind": {"enum": ["FORWARD", "COMPENSATION"]}}),
        _claim("EXECUTION_RECEIPT", "RECEIPT", {"call_class": {"enum": list(CALL_CLASSES)}, "provider_acknowledged": {"type": "boolean"},
                                                "implies_commit": {"const": False}}),
        _claim("COMMIT_OBSERVATION", "RECEIPT", {"commit_state": {"enum": ["COMMITTED", "ABSENT", "UNKNOWN"]}, "readback_digest": _HASH,
                                                 "implies_outcome": {"const": False}}),
        _claim("READBACK_CLAIM", "RECEIPT", {"source_level": {"enum": list(SOURCE_LEVELS)}, "claimed_authoritative": {"type": "boolean"},
                                             "existence": {"enum": ["EXISTS", "ABSENT", "UNKNOWN"]}, "activation": {"enum": ["ACTIVE", "INACTIVE", "UNKNOWN"]},
                                             "checks_satisfied": {"type": "boolean"}, "provenance_verified": {"type": "boolean"}}),
        _claim("OUTCOME_EVALUATION", "BUSINESS_OUTCOME", {"expected_digest": _NHASH, "observed_digest": _HASH, "readback_digest": _HASH,
                                                          "predicates_digest": _NHASH, "result": {"enum": list(TRI)}}),
        _claim("COMPENSATION_ATTEMPT", "OCCURRENCE", {"attempt_number": {"type": "integer", "minimum": 1}, "call_class": {"enum": list(CALL_CLASSES)},
                                                      "resolved": {"type": "boolean"}}),
        _claim("MISSION_DISPOSITION", "BUSINESS_OUTCOME", {"disposition": {"enum": list(DISPOSITIONS)}, "outcome_class": {"enum": list(OUTCOME_CLASSES) + [None]},
                                                           "chain_digests": {"type": "array", "items": _HASH, "minItems": 1}}),
        _claim("EVIDENCE_VERIFICATION", "VERIFIED_FACT", {"subject_digest": _HASH, "scope": {"enum": list(VERIFY_SCOPES)}, "result": {"enum": list(TRI)},
                                                          "verifier": _STR, "claims_business_outcome": {"const": False}}),
    ]
    provenance = _obj({"hash_consistent": {"type": "boolean"}, "signature": {"enum": list(SIGNATURE_STATES)}, "signer": _NSTR,
                       "issuer_trust": {"enum": list(ISSUER_TRUST)}, "freshness": {"enum": list(FRESHNESS)}, "replay": {"enum": list(REPLAY)},
                       "verified_by": _NSTR})
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "mcr-evidence/1",
        "title": "MCR Evidence Contract v1 (version-independent canonical evidence envelope)",
        "type": "object",
        "additionalProperties": False,
        "required": ["contract", "contract_version", "id", "type", "source", "time", "producer", "correlation", "claim", "evidence",
                     "authority_effect", "digests", "lineage"],
        "properties": {
            "contract": {"const": CONTRACT},
            "contract_version": {"type": "string", "pattern": r"^1\.[0-9]+\.[0-9]+$"},
            "id": {"type": "string", "pattern": ID_RE},
            "type": {"enum": sorted(TYPE_TABLE)},
            "source": {"type": "string", "minLength": 1, "maxLength": 256, "pattern": r"^[^\s]+$"},
            "time": {"type": "string", "format": "date-time"},
            "producer": _obj({"runtime": {"const": "mcr"}, "runtime_version": {"type": "string", "pattern": VERSION_RE}, "adapter_id": _STR,
                              "adapter_version": {"type": "string", "pattern": VERSION_RE}, "source_runtime_version": {"type": "string", "pattern": VERSION_RE}}),
            "correlation": _obj({"mission_id": _NID, "transaction_id": _NID, "correlation_id": _NID, "causation_id": _NID, "mutation_attempt_id": _NID},
                                ["mission_id", "transaction_id", "correlation_id", "causation_id"]),
            "principal": _obj({"principal_ref": _NHASH, "assurance": {"enum": ["SELF_REPORTED", "UNKNOWN", "VERIFIED"]}, "delegation_ref": _NHASH}),
            "capability": _obj({"capability_id": _STR, "qualification_status": {"enum": list(CAPABILITY_STATES)}, "provider_id": _NSTR,
                                "target_system": _NSTR, "operation": _NSTR}, ["capability_id", "qualification_status"]),
            "budget": _obj({"mutation_budget": _COUNT, "attempt_number": {"type": ["integer", "null"], "minimum": 1},
                            "attempts_remaining": {"type": ["integer", "null"], "minimum": 0}, "kind": {"enum": ["FORWARD", "COMPENSATION"]}}),
            "claim": {"oneOf": claims},
            "evidence": _obj({"digest": _HASH, "ref": _NSTR, "classification": {"enum": list(EVIDENCE_CLASSES)}, "trust": {"enum": list(TRUST_LEVELS)},
                              "provenance": provenance}),
            "authority_effect": {"const": "NONE"},
            "authorization_ref": {"type": ["object", "null"], "properties": {"approval_id_hash": _HASH, "approver": _STR, "scope_digest": _HASH,
                                                                             "expires_at": {"type": ["string", "null"], "format": "date-time"},
                                                                             "source": {"const": "EXTERNAL_GOVERNOR"}},
                                  "required": ["approval_id_hash", "approver", "scope_digest", "expires_at", "source"], "additionalProperties": False},
            "disposition": {"enum": list(DISPOSITIONS) + [None]},
            "outcome_class": {"enum": list(OUTCOME_CLASSES) + [None]},
            "digests": _obj({"schema": _HASH, "policy": _NHASH, "payload": _HASH}),
            "lineage": _obj({"transformations": {"type": "array", "items": _obj({"step": _STR, "from": _STR, "to": _STR, "tool": _STR, "tool_version": _STR})},
                             "source_event_id": _NSTR, "source_digest": _NHASH, "supersedes": _NSTR}),
            "extensions": {"type": "object"},
            "critical": {"type": "array", "items": _STR, "uniqueItems": True},
            "integrity": _obj({"event_digest": _HASH}),
        },
    }
    return schema


def canonical_bytes(obj):
    """Deterministic UTF-8 JSON: sorted keys, no whitespace, no floats (a float would digest differently across
    producers), only str/int/bool/None/list/dict-with-str-keys."""
    def check(v):
        if isinstance(v, bool) or v is None or isinstance(v, (str, int)):
            return
        if isinstance(v, float):
            raise ValueError("floats are not allowed in digested evidence")
        if isinstance(v, (list, tuple)):
            for x in v:
                check(x)
            return
        if isinstance(v, dict):
            for k, x in v.items():
                if not isinstance(k, str):
                    raise ValueError("object keys must be strings")
                check(x)
            return
        raise ValueError("unsupported type %s" % type(v).__name__)
    check(obj)
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(b):
    return hashlib.sha256(b).hexdigest()


def digest_of(obj):
    return sha256_hex(canonical_bytes(obj))


SCHEMA = build_schema()
SCHEMA_DIGEST = digest_of(SCHEMA)


def derive_trust(prov):
    """Trust is a pure function of the provenance record; an event cannot assert more than its provenance supports."""
    if prov["replay"] == "REPLAYED":
        return "REPLAYED"
    if prov["issuer_trust"] == "REVOKED":
        return "REVOKED"
    if prov["signature"] == "ABSENT":
        return "UNTRUSTED_RESEARCH"
    if prov["signature"] == "INVALID" or not prov["hash_consistent"]:
        return "SIGNATURE_INVALID"
    if prov["freshness"] == "EXPIRED":
        return "EXPIRED"
    if prov["issuer_trust"] == "TRUSTED" and prov["freshness"] == "FRESH" and prov["replay"] == "NOT_SEEN":
        return "SIGNED_TRUSTED"
    return "SIGNED_UNTRUSTED"


def unsigned_provenance():
    return {"hash_consistent": True, "signature": "ABSENT", "signer": None, "issuer_trust": "UNKNOWN", "freshness": "UNKNOWN", "replay": "UNKNOWN", "verified_by": None}


def content_digest(event):
    """Digest of what the PRODUCER asserted: the event without its integrity block and with the verifier-controlled
    provenance/trust reset. Signatures bind this value, so a verifier can attach its provenance verdict without
    invalidating the producer's signature."""
    e = copy.deepcopy(event)
    e.pop("integrity", None)
    e["evidence"]["provenance"] = unsigned_provenance()
    e["evidence"]["trust"] = "UNTRUSTED_RESEARCH"
    return digest_of(e)


def seal(event):
    """Set digests.payload and integrity.event_digest. Returns a new event."""
    e = copy.deepcopy(event)
    e["digests"]["payload"] = digest_of(e["claim"])
    e["digests"]["schema"] = SCHEMA_DIGEST
    e.pop("integrity", None)
    e["integrity"] = {"event_digest": digest_of(e)}
    return e


def make_event(etype, claim, *, event_id, source, time, runtime_version, adapter_id, adapter_version, source_runtime_version,
               correlation, evidence_digest, evidence_ref=None, classification="UNKNOWN", provenance=None, capability=None, principal=None,
               budget=None, authorization_ref=None, disposition=None, outcome_class=None, policy_digest=None, lineage=None, extensions=None):
    kind, layer = TYPE_TABLE[etype]
    prov = provenance or unsigned_provenance()
    e = {
        "contract": CONTRACT, "contract_version": CURRENT_VERSION, "id": event_id, "type": etype, "source": source, "time": time,
        "producer": {"runtime": "mcr", "runtime_version": runtime_version, "adapter_id": adapter_id, "adapter_version": adapter_version,
                     "source_runtime_version": source_runtime_version},
        "correlation": {"mission_id": None, "transaction_id": None, "correlation_id": None, "causation_id": None, **correlation},
        "claim": dict({"kind": kind, "layer": layer}, **claim),
        "evidence": {"digest": evidence_digest, "ref": evidence_ref, "classification": classification, "trust": derive_trust(prov), "provenance": prov},
        "authority_effect": "NONE",
        "digests": {"schema": SCHEMA_DIGEST, "policy": policy_digest, "payload": "0" * 64},
        "lineage": lineage or {"transformations": [], "source_event_id": None, "source_digest": None, "supersedes": None},
    }
    for k, v in (("capability", capability), ("principal", principal), ("budget", budget), ("authorization_ref", authorization_ref),
                 ("disposition", disposition), ("outcome_class", outcome_class), ("extensions", extensions)):
        if v is not None:
            e[k] = v
    return seal(e)


# ---------------------------------------------------------------- validation
class ContractError(ValueError):
    """Raised by parse() for an event a consumer must not accept."""


def _split_version(v):
    a, b, c = v.split(".")
    return int(a), int(b), int(c)


def semantic_problems(e, full=None):
    """Rules a schema cannot express. e is already schema-valid. `full` is the event including unrecognized top-level
    fields: the integrity digest covers them, so they cannot be altered without detection."""
    p = []
    kind, layer = TYPE_TABLE[e["type"]]
    if e["claim"]["kind"] != kind or e["claim"]["layer"] != layer:
        p.append("claim kind/layer does not belong to type %s" % e["type"])
    if e["digests"]["payload"] != digest_of(e["claim"]):
        p.append("digests.payload does not match the claim")
    if e["digests"]["schema"] != SCHEMA_DIGEST:
        p.append("digests.schema does not match this contract's schema digest")
    if "integrity" in e:
        body = {k: v for k, v in (full or e).items() if k != "integrity"}
        if e["integrity"]["event_digest"] != digest_of(body):
            p.append("integrity.event_digest does not match the event")
    ev = e["evidence"]
    if ev["trust"] != derive_trust(ev["provenance"]):
        p.append("evidence.trust is not what the provenance record supports (%s)" % derive_trust(ev["provenance"]))
    if ev["trust"] == "SIGNED_TRUSTED" and ev["classification"] in ("SYNTHETIC",):
        p.append("synthetic evidence cannot be SIGNED_TRUSTED")
    pr = e.get("principal")
    if pr and pr["assurance"] == "VERIFIED" and ev["trust"] != "SIGNED_TRUSTED":
        p.append("principal assurance VERIFIED needs SIGNED_TRUSTED evidence")
    if e["type"] != "mcr.mission.started" and e["correlation"]["mission_id"] is None:
        p.append("correlation.mission_id is required for %s" % e["type"])
    if e["type"] in ("mcr.mutation.attempted", "mcr.compensation.attempted") and e["correlation"].get("mutation_attempt_id") is None:
        p.append("mutation_attempt_id is required for an attempt event")
    for name in e.get("critical", []):
        if name not in KNOWN_CRITICAL:
            p.append("unknown critical semantics %r (fail closed)" % name)
    cl = e["claim"]
    if cl["kind"] == "READBACK_CLAIM" and cl["claimed_authoritative"] and cl["source_level"] != "AUTHORITATIVE_REPOSITORY":
        p.append("a readback cannot claim to be authoritative from a non-authoritative source level")
    if cl["kind"] == "READBACK_CLAIM" and cl["provenance_verified"] and ev["trust"] != "SIGNED_TRUSTED":
        p.append("provenance_verified needs SIGNED_TRUSTED evidence")
    if cl["kind"] == "OUTCOME_EVALUATION" and cl["result"] == "PASS" and ev["classification"] not in ("READBACK", "OBSERVED", "CORROBORATED", "SYNTHETIC", "HISTORICAL"):
        p.append("a PASS outcome needs readback/observed evidence, not %s" % ev["classification"])
    if cl["kind"] == "OUTCOME_EVALUATION" and ev["classification"] != "HISTORICAL" and (cl["expected_digest"] is None or cl["predicates_digest"] is None):
        p.append("expected_digest and predicates_digest may be null only for HISTORICAL evidence (nothing is back-filled)")
    if cl["kind"] == "MISSION_DISPOSITION":
        if cl["disposition"] == "COMPLETE" and cl["outcome_class"] != "COMPLETE":
            p.append("disposition COMPLETE needs outcome_class COMPLETE")
        if cl["outcome_class"] == "COMPLETE" and cl["disposition"] != "COMPLETE":
            p.append("outcome_class COMPLETE needs disposition COMPLETE")
        if "disposition" in e and e["disposition"] != cl["disposition"]:
            p.append("top-level disposition differs from the claim")
    if cl["kind"] == "EXECUTION_RECEIPT" and cl["call_class"] == "PROVIDER_RESPONSE_SUCCESS" and not cl["provider_acknowledged"]:
        p.append("a successful provider response is an acknowledgement")
    if cl["kind"] == "EXECUTION_RECEIPT" and cl["call_class"] in ("CALL_NOT_SENT", "CALL_SENT_NO_RESPONSE", "PROVIDER_ERROR") and cl["provider_acknowledged"]:
        p.append("a failed or unanswered call cannot be an acknowledgement")
    if cl["kind"] == "COMMIT_OBSERVATION" and cl["commit_state"] == "COMMITTED" and ev["classification"] not in ("READBACK", "OBSERVED", "CORROBORATED", "SYNTHETIC", "HISTORICAL"):
        p.append("a COMMITTED observation needs readback/observed evidence")
    return p


def parse(event, *, supported_major=SUPPORTED_MAJOR, supported_minor=CURRENT_MINOR):
    """Validate for a consumer. Returns (known_event, unrecognized). Raises ContractError (fail closed) on:
    wrong contract, other major, schema or semantic violation, unknown type/enum, unknown critical semantics.
    Unknown top-level fields from a NEWER minor version are retained in `unrecognized` and never interpreted."""
    from mini_jsonschema import validate
    if not isinstance(event, dict):
        raise ContractError("event must be an object")
    if event.get("contract") != CONTRACT:
        raise ContractError("not an %s event" % CONTRACT)
    ver = event.get("contract_version")
    if not isinstance(ver, str) or not re.match(VERSION_RE, ver):
        raise ContractError("contract_version missing or malformed")
    major, minor, _ = _split_version(ver)
    if major != supported_major:
        raise ContractError("unsupported major version %d (this consumer supports %d)" % (major, supported_major))
    crit = event.get("critical", [])
    if not isinstance(crit, list) or not all(isinstance(x, str) for x in crit):
        raise ContractError("critical must be a list of strings")
    top_known = set(SCHEMA["properties"])
    unknown = {k: v for k, v in event.items() if k not in top_known}
    if unknown and minor <= supported_minor:
        raise ContractError("unknown top-level field(s) %s in version %s" % (sorted(unknown), ver))
    for name in crit:
        if name in unknown or name not in KNOWN_CRITICAL:
            raise ContractError("unknown critical semantics %r (fail closed)" % (name,))
    known = {k: v for k, v in event.items() if k in top_known}
    # the version pattern allows any 1.x; a newer minor is accepted only through the unknown-field rule above
    probs = validate(known, SCHEMA)
    if probs:
        raise ContractError("schema violation: " + "; ".join(probs[:6]))
    try:
        sem = semantic_problems(known, event)
    except (ValueError, TypeError, KeyError, AttributeError) as exc:       # hostile content that the schema cannot describe (for example non-string keys)
        raise ContractError("semantic violation: unusable content (%s)" % type(exc).__name__) from exc
    if sem:
        raise ContractError("semantic violation: " + "; ".join(sem[:6]))
    return known, unknown


def migrate(event, target_version, *, tool="evc1.migrate", tool_version="3.0.0"):
    """Re-label an event within the same major version, recording the transformation in lineage and keeping the source
    digest. Refuses a downgrade that would drop an unrecognized field, and any change of major."""
    known, unknown = parse(event)
    smaj, smin, _ = _split_version(known["contract_version"])
    tmaj, tmin, _ = _split_version(target_version)
    if tmaj != smaj:
        raise ContractError("migration across major versions needs a new contract, not a relabel")
    if tmin < smin and unknown:
        raise ContractError("downgrade would drop unrecognized fields")
    out = copy.deepcopy(known)
    out["contract_version"] = target_version
    out["lineage"]["transformations"].append({"step": "migrate", "from": known["contract_version"], "to": target_version, "tool": tool, "tool_version": tool_version})
    out["lineage"]["source_event_id"] = known["id"]
    out["lineage"]["source_digest"] = known.get("integrity", {}).get("event_digest") or digest_of({k: v for k, v in known.items() if k != "integrity"})
    out["id"] = known["id"] + ".m" + target_version.replace(".", "")
    return seal(out)
