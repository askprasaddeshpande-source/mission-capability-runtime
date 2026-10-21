"""Portable readback and outcome-validation interfaces, with an offline SAP/ADT-style reference provider.

The canonical contract and the runtime know nothing about SAP. This module defines:
  ReadbackProvider        interface: given a target and a readback contract, return raw reads
  derive_readback()       provider-neutral rules that turn raw per-version reads into existence / activation / observed
  SapAdtReference         an OFFLINE reference provider whose raw-read shapes are ASSUMPTIONS modelled on the archived R2.0 study
                          (status codes, a 404 that does or does not name the object, a wrong-endpoint 404, source text with a
                          reported hash). Nothing here has been run against a live system; every rule is NOT_VERIFIED live.
Rules that close R2.0 readback weaknesses on paper (and are unit-tested offline, not live):
  * ABSENT needs a 404 that NAMES the requested object; an unnamed or wrong-endpoint 404 is UNKNOWN;
  * active and inactive versions are read separately; EXISTS in either is existence, but ACTIVE needs the active read;
  * a read from an endpoint that serves another object type is UNKNOWN, never ABSENT;
  * the source text must contain the requested object name (identity) and match its reported hash (integrity of one
    response only; it does not prove the provider told the truth);
  * the "authoritative" level is the provider's claim; `independent_source` is False until a second, independent reader agrees.
"""
import hashlib

import mcr3_model as M


class ReadbackProvider:
    """Interface. read(object_name, object_type, version) -> RawRead dict."""
    def read(self, object_name, object_type, version):      # pragma: no cover (interface)
        raise NotImplementedError


def raw_read(version, endpoint, status, error_names_object=None, source_text=None, source_sha256_reported=None):
    return {"version": version, "endpoint": endpoint, "status": status, "error_names_object": error_names_object,
            "source_text": source_text, "source_sha256_reported": source_sha256_reported}


def _classify(r, name, otype):
    """-> ("EXISTS"|"ABSENT"|"UNKNOWN", integrity_ok, identity_ok)"""
    if not isinstance(r, dict) or r.get("endpoint") != otype:
        return "UNKNOWN", False, False                          # wrong endpoint or malformed: never ABSENT
    st = r.get("status")
    if st == 200:
        src = r.get("source_text")
        if not isinstance(src, str) or not src:
            return "UNKNOWN", False, False
        integrity = r.get("source_sha256_reported") == hashlib.sha256(src.encode("utf-8")).hexdigest()
        identity = name.lower() in src.lower()
        return ("EXISTS" if integrity and identity else "UNKNOWN"), integrity, identity
    if st == 404:
        return ("ABSENT" if r.get("error_names_object") == name else "UNKNOWN"), False, False
    return "UNKNOWN", False, False


def derive_readback(object_name, object_type, reads):
    """reads: {"active": RawRead, "inactive": RawRead}. Returns dict(existence, activation, observed, source_level, independent_source)."""
    act, ina = _classify(reads.get("active"), object_name, object_type), _classify(reads.get("inactive"), object_name, object_type)
    if act[0] == "EXISTS" or ina[0] == "EXISTS":
        existence = "EXISTS"
    elif act[0] == "ABSENT" and ina[0] == "ABSENT":
        existence = "ABSENT"
    else:
        existence = "UNKNOWN"
    if act[0] == "EXISTS":
        activation = "ACTIVE"
    elif ina[0] == "EXISTS" and act[0] == "ABSENT":
        activation = "INACTIVE"
    else:
        activation = "UNKNOWN"
    any_definitive = any(x[0] in ("EXISTS", "ABSENT") for x in (act, ina))
    observed = {"exists": True if existence == "EXISTS" else False if existence == "ABSENT" else "UNKNOWN", "object_type": object_type,
                "active_read": act[0], "inactive_read": ina[0],
                "source_hash_integrity": (act[1] or ina[1]) if existence == "EXISTS" else "UNKNOWN",
                "source_contains_object_name": (act[2] or ina[2]) if existence == "EXISTS" else "UNKNOWN"}
    return {"existence": existence, "activation": activation, "observed": observed,
            "source_level": "AUTHORITATIVE_REPOSITORY" if any_definitive else "INFERRED_OR_REGEX", "independent_source": False}


def to_receipt(derived, *, receipt_id, transaction_id, mutation_id, contract_hash):
    return M.make("AuthoritativeReadbackReceipt", receipt_id=receipt_id, transaction_id=transaction_id, mutation_id=mutation_id, contract_hash=contract_hash,
                  source_level=derived["source_level"], existence=derived["existence"], activation=derived["activation"], observed=derived["observed"])


class SapAdtReference(ReadbackProvider):
    """Offline stand-in: serves responses from a dict {(name, type, version): RawRead}. Missing -> no response (status None)."""
    NOT_VERIFIED_LIVE = True

    def __init__(self, store):
        self.store = dict(store)

    def read(self, object_name, object_type, version):
        return self.store.get((object_name, object_type, version), raw_read(version, object_type, None))

    def readback(self, object_name, object_type):
        return derive_readback(object_name, object_type, {v: self.read(object_name, object_type, v) for v in ("active", "inactive")})


def second_reader_agrees(first, second):
    """A second, INDEPENDENT reader agrees if both derived the same existence and activation from definitive reads. Only then may a
    deployment claim `independent_source`; two readers behind the same transport or tool are not independent (the caller must say)."""
    return first["existence"] == second["existence"] != "UNKNOWN" and first["activation"] == second["activation"]
