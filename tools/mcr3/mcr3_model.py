"""MCR 3.0 outcome model (forked from the frozen MCR R2.0 reference model; independently versioned).

MCR R2.0 stays frozen. This module is the 3.0 lineage: stricter ledger paths, bounded compensation attempts,
enforced expiry / outcome-hash / readback checks, exact provider binding, outcome classification.
Original R2.0A docstring follows.

MCR R2.0A outcome model: state machine, hash-addressed objects, guards.

Deterministic, dependency-free, no network, no enterprise access.
Evidence class of everything produced by this module: SYNTHETIC/LOCAL.
Design rule: a state is entered only through a guard that demands the specific
evidence object for that state. No state is inferred from an earlier one.
"""
import copy
import functools
import hashlib
import json
import os
import threading
import time
import uuid
import unicodedata
import zlib

try:                                   # OS file locking for the replay ledger
    import msvcrt
except ImportError:                    # pragma: no cover (POSIX)
    msvcrt = None
try:
    import fcntl
except ImportError:                    # pragma: no cover (Windows)
    fcntl = None

MODEL_VERSION = "3.0.0"
MODEL_LINEAGE = "MCR3 (forked from MCR R2.0 reference model)"

# ---------------------------------------------------------------- hashing
def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def chash(obj):
    return hashlib.sha256(canon(obj).encode("ascii")).hexdigest().upper()


# ---------------------------------------------------------------- states
STATES = [
    "PLANNED", "CONTEXT_READY", "AUTHORIZED", "BOUND", "PREWRITE_VALIDATED",
    "EXECUTION_STARTED", "EXECUTED", "COMMIT_STATE_UNKNOWN", "COMMITTED",
    "AUTHORITATIVE_READBACK_PENDING", "AUTHORITATIVE_READBACK_OBSERVED",
    "OUTCOME_VALIDATION_PENDING", "OUTCOME_VALIDATED", "COMPLETE",
    "FAILED_BEFORE_MUTATION", "FAILED_AFTER_POSSIBLE_MUTATION",
    "COMPENSATION_REQUIRED", "COMPENSATION_AUTHORIZED", "COMPENSATED",
    "UNRECOVERABLE",
]
TERMINAL = {"COMPLETE", "COMPENSATED", "UNRECOVERABLE", "FAILED_BEFORE_MUTATION"}

TRANSITIONS = {
    "PLANNED": {"CONTEXT_READY", "FAILED_BEFORE_MUTATION"},
    "CONTEXT_READY": {"AUTHORIZED", "FAILED_BEFORE_MUTATION"},
    "AUTHORIZED": {"BOUND", "FAILED_BEFORE_MUTATION"},
    "BOUND": {"PREWRITE_VALIDATED", "FAILED_BEFORE_MUTATION"},
    "PREWRITE_VALIDATED": {"EXECUTION_STARTED", "FAILED_BEFORE_MUTATION"},
    # once EXECUTION_STARTED the call may have left the client: no FAILED_BEFORE_MUTATION
    "EXECUTION_STARTED": {"EXECUTED", "COMMIT_STATE_UNKNOWN", "FAILED_AFTER_POSSIBLE_MUTATION"},
    "EXECUTED": {"AUTHORITATIVE_READBACK_PENDING", "COMMIT_STATE_UNKNOWN"},
    "COMMIT_STATE_UNKNOWN": {"AUTHORITATIVE_READBACK_PENDING", "FAILED_AFTER_POSSIBLE_MUTATION"},
    "AUTHORITATIVE_READBACK_PENDING": {
        "AUTHORITATIVE_READBACK_OBSERVED", "COMMIT_STATE_UNKNOWN"},
    # observed readback decides COMMITTED (EXISTS) or not-committed (ABSENT) or stays unknown
    "AUTHORITATIVE_READBACK_OBSERVED": {
        "COMMITTED", "COMMIT_STATE_UNKNOWN", "FAILED_AFTER_POSSIBLE_MUTATION"},
    "COMMITTED": {"OUTCOME_VALIDATION_PENDING"},
    "OUTCOME_VALIDATION_PENDING": {
        "OUTCOME_VALIDATED", "COMPENSATION_REQUIRED"},
    "OUTCOME_VALIDATED": {"COMPLETE"},
    "FAILED_AFTER_POSSIBLE_MUTATION": {
        "AUTHORITATIVE_READBACK_PENDING", "COMPENSATION_REQUIRED", "UNRECOVERABLE"},
    "COMPENSATION_REQUIRED": {"COMPENSATION_AUTHORIZED", "UNRECOVERABLE"},
    "COMPENSATION_AUTHORIZED": {"COMPENSATED", "UNRECOVERABLE"},
    "COMPLETE": set(), "COMPENSATED": set(), "UNRECOVERABLE": set(),
    "FAILED_BEFORE_MUTATION": set(),
}

# ---------------------------------------------------------------- enums
READBACK_EXISTENCE = ("EXISTS", "ABSENT", "UNKNOWN")
READBACK_ACTIVATION = ("ACTIVE", "INACTIVE", "UNKNOWN")
# Only the first level can establish enterprise state.
SOURCE_LEVELS = ("AUTHORITATIVE_REPOSITORY", "PROVIDER_VALIDATION", "PROVIDER_LOG",
                 "TRANSPORT_SUCCESS", "CACHED_OUTPUT", "LOCAL_RUNNER_STATE", "INFERRED_OR_REGEX")
CALL_CLASSES = ("CALL_NOT_SENT", "CALL_SENT_NO_RESPONSE", "PROVIDER_ERROR",
                "PROVIDER_RESPONSE_SUCCESS", "COMMIT_UNKNOWN", "COMMIT_CONFIRMED",
                "OUTCOME_FAILED", "OUTCOME_VALIDATED")
TRI = ("PASS", "FAIL", "UNKNOWN")

# ---------------------------------------------------------------- schemas
# name -> (required fields, enum constraints)
SCHEMAS = {
    "MissionIntent": (["mission_id", "objective", "target_system", "expected_outcome_hash"], {}),
    "PrincipalContext": (["principal_id", "tenant", "roles"], {}),
    "DelegationEnvelope": (["delegation_id", "principal_hash", "scope", "max_mutations", "expires_at"], {}),
    "ExecutionAuthority": (["authority_id", "delegation_hash", "mission_id", "scope", "max_mutations", "single_use"], {}),
    "CapabilityBinding": (["binding_id", "authority_hash", "capability", "provider_ref"], {}),
    "ProviderBinding": (["provider_id", "tool_name", "contract_fingerprint", "identity"], {}),
    "MutationBudget": (["budget_id", "authority_hash", "max_mutations", "retries", "expansion_allowed"], {}),
    "TransactionEnvelope": (["transaction_id", "mission_id", "mutation_ids", "boundary"], {}),
    "PreMutationCheckpoint": (["checkpoint_id", "transaction_hash", "budget_hash", "outcome_contract_hash",
                               "readback_contract_hash", "remaining_budget"], {}),
    "ExecutionReceipt": (["receipt_id", "transaction_id", "mutation_id", "call_class"], {"call_class": CALL_CLASSES}),
    "CommitObservation": (["observation_id", "transaction_id", "mutation_id", "readback_receipt_hash", "commit_state"],
                          {"commit_state": ("COMMITTED", "ABSENT", "UNKNOWN")}),
    "AuthoritativeReadbackContract": (["contract_id", "source_level_required", "provider_ref", "checks"],
                                      {"source_level_required": SOURCE_LEVELS}),
    "AuthoritativeReadbackReceipt": (["receipt_id", "transaction_id", "mutation_id", "contract_hash",
                                      "source_level", "existence", "activation", "observed"],
                                     {"source_level": SOURCE_LEVELS, "existence": READBACK_EXISTENCE,
                                      "activation": READBACK_ACTIVATION}),
    "ExpectedOutcomeContract": (["outcome_contract_id", "mission_id", "transaction_id", "predicates", "frozen"], {}),
    "OutcomePredicate": (["field", "op", "expected"], {"op": ("eq", "ne", "in")}),
    "OutcomeReceipt": (["receipt_id", "transaction_id", "readback_receipt_hash", "outcome_contract_hash", "result"],
                       {"result": TRI}),
    "CompletionReceipt": (["receipt_id", "transaction_id", "outcome_receipt_hash", "commit_observation_hash",
                           "execution_receipt_hash", "authority_hash"], {}),
    "ContinuationLease": (["lease_id", "checkpoint_hash", "transaction_id", "remaining_budget", "consumed_authority_ids"], {}),
    "ReplayGuard": (["guard_id", "consumed"], {}),
    "CompensationGrant": (["grant_id", "target", "capability", "max_mutations", "preconditions",
                           "outcome_predicates", "inherits_forward_authority", "issued_by"], {}),
    "CompensationReceipt": (["receipt_id", "grant_hash", "readback_receipt_hash", "result"], {"result": TRI}),
    "ContractLease": (["lease_id", "provider_ref", "contract_fingerprint", "mission_relevant_fields"], {}),
    "ContractFingerprint": (["provider_ref", "tool_name", "schema_hash", "description_hash"], {}),
    "GovernanceTelemetry": (["mission_id", "governance_ns", "provider_ns"], {}),
    "EvidenceEnvelope": (["envelope_id", "mission_id", "transaction_id", "chain", "evidence_class"],
                         {"evidence_class": ("PROVEN", "OBSERVED", "PARTIAL", "SYNTHETIC", "LOCAL",
                                             "NOT_ESTABLISHED", "DEFERRED", "REJECTED")}),
}


class SchemaError(ValueError):
    pass


def make(kind, **fields):
    """Build a hash-addressed object. Hash covers the whole body (incl. refs)."""
    req, enums = SCHEMAS[kind]
    missing = [f for f in req if f not in fields]
    if missing:
        raise SchemaError("%s missing %s" % (kind, missing))
    for f, allowed in enums.items():
        if fields[f] not in allowed:
            raise SchemaError("%s.%s=%r not in %s" % (kind, f, fields[f], allowed))
    body = {"kind": kind, **fields}
    return {**body, "object_hash": chash(body)}


def verify_hash(obj):
    body = {k: v for k, v in obj.items() if k != "object_hash"}
    return obj.get("object_hash") == chash(body)


# ---------------------------------------------------------------- outcome predicates
class GuardError(Exception):
    pass


PRED_OPS = ("eq", "ne", "in")


def _same(a, b):
    """Strict equality: same type and equal (so True != 1 and 1 != 1.0 for predicate purposes)."""
    return type(a) is type(b) and a == b


def check_predicates(predicates):
    """A usable predicate list is non-empty and well-formed. Empty lists are vacuous and refused."""
    if not isinstance(predicates, (list, tuple)) or not predicates:
        raise GuardError("empty predicate list is vacuous")
    for p in predicates:
        if not isinstance(p, dict) or not {"field", "op", "expected"} <= set(p):
            raise GuardError("malformed predicate")
        if p["op"] not in PRED_OPS:
            raise GuardError("unknown predicate op %r" % (p["op"],))
        if p["op"] == "in" and (not isinstance(p["expected"], (list, tuple, set, frozenset)) or not p["expected"]):
            raise GuardError("op 'in' needs a non-empty collection")


def eval_predicates(predicates, observed):
    """Tri-state. A missing observed field is UNKNOWN, never FAIL or PASS. Empty/unknown-op predicates raise.
    Comparison is strict about type. Predicates are authored and frozen before the mutation; a tautological
    predicate is an authoring error this function cannot detect."""
    check_predicates(predicates)
    result = "PASS"
    for p in predicates:
        if p["field"] not in observed or observed[p["field"]] in (None, "UNKNOWN"):
            result = "UNKNOWN" if result != "FAIL" else result
            continue
        v, e, op = observed[p["field"]], p["expected"], p["op"]
        ok = _same(v, e) if op == "eq" else (not _same(v, e)) if op == "ne" else any(_same(v, x) for x in e)
        if not ok:
            return "FAIL"
    return result


# ---------------------------------------------------------------- authority checks
def parse_expiry(value):
    """expires_at as UTC epoch seconds. Accepts a finite number (not bool) or an ISO-8601 string
    YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS[.ffffff](Z|+00:00). Anything else is refused (None)."""
    import datetime
    import math
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) and value >= 0 else None
    if not isinstance(value, str):
        return None
    try:
        if len(value) == 10:
            d = datetime.datetime.strptime(value, "%Y-%m-%d")
        else:
            v = value[:-1] + "+00:00" if value.endswith("Z") else value
            if not v.endswith("+00:00"):
                return None
            d = datetime.datetime.fromisoformat(v[:-6])
            if d.tzinfo is not None:                       # review 8: "...+05:00Z" must not be read as UTC
                return None
        return d.replace(tzinfo=datetime.timezone.utc).timestamp()
    except ValueError:
        return None


def observed_view(rb):
    """Fields a predicate may test: the readback's observed state plus the receipt-level activation as '$activation'."""
    return dict(rb["observed"], **{"$activation": rb["activation"]})


def attenuated(child_scope, parent_scope):
    return set(child_scope) <= set(parent_scope)


def _hash_ok(obj):
    try:
        return verify_hash(obj)
    except Exception:
        return False


_STR_FIELDS = ("capability", "tool_name", "identity", "provider_ref", "provider_id", "target_system", "objective")


def _accept_obj(slot, obj):
    """Gate for every presented object: right kind, valid hash, string-typed ids/hashes/names and list-typed scopes;
    returns a private deep copy."""
    if not isinstance(obj, dict) or obj.get("kind") != SLOT_KINDS[slot]:
        raise GuardError("%s absent, malformed or wrong kind" % slot)
    if not _hash_ok(obj):
        raise GuardError("%s hash invalid (tampered)" % slot)
    for k, v in obj.items():
        if k == "kind":
            continue
        if (k.endswith("_id") or k.endswith("_hash")) and not isinstance(v, str):
            raise GuardError("%s field %s must be a string" % (slot, k))
        if k in _STR_FIELDS and not isinstance(v, str):
            raise GuardError("%s field %s must be a string" % (slot, k))
        if k == "scope" and (not isinstance(v, (list, tuple)) or not all(isinstance(x, str) and x for x in v)):
            raise GuardError("%s scope must be a list of non-empty strings" % slot)
    return copy.deepcopy(obj)


def _lock(fh, timeout=30.0):
    """Exclusive advisory lock on the ledger file (byte 0), shared by every process that uses the file."""
    start = time.time()
    while True:
        try:
            if msvcrt is not None:
                os.lseek(fh.fileno(), 0, os.SEEK_SET)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except OSError:
            if time.time() - start > timeout:
                raise GuardError("ledger lock timeout")
            time.sleep(0.01)


def _unlock(fh):
    try:
        if msvcrt is not None:
            os.lseek(fh.fileno(), 0, os.SEEK_SET)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass


def _tlocked(fn):
    """Serialize every operation on one ReplayLedger object across threads (a plain set is not thread-safe)."""
    @functools.wraps(fn)
    def wrapper(self, *a, **k):
        with self._tlock:
            return fn(self, *a, **k)
    return wrapper


def _io_guard(fn):
    """File problems must block the send as a GuardError, never leak as an OSError."""
    @functools.wraps(fn)
    def wrapper(*a, **k):
        try:
            return fn(*a, **k)
        except GuardError:
            raise
        except (OSError, ValueError, TypeError) as exc:
            raise GuardError("ledger I/O error: %s" % type(exc).__name__) from exc
    return wrapper


_RESERVED_NAMES = frozenset(["CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$", "CLOCK$"]
                            + ["COM%d" % i for i in range(0, 10)] + ["LPT%d" % i for i in range(0, 10)])
_BAD_PATH_CHARS = frozenset('<>"|?*')


def _check_ledger_path(path):
    """Refuse, on every platform, anything that could name a device, an NTFS alternate data stream, a parent
    directory or a name Windows would silently rewrite: control characters (incl. NUL), the characters < > " | ? *,
    a colon anywhere except a leading drive letter, '..' components, components ending in a dot or space, and device
    names (CON, PRN, AUX, NUL, CONIN$, CONOUT$, COM0-9, LPT0-9, also written with superscript digits, with an
    extension or with trailing spaces). Names are compared after Unicode NFKC folding."""
    if len(path) > 4096:
        raise GuardError("ledger path too long")
    if any(ord(c) < 32 or ord(c) == 127 for c in path):
        raise GuardError("ledger path contains a control character")
    if any(c in _BAD_PATH_CHARS for c in path):
        raise GuardError("ledger path contains a character Windows reserves")
    rest = path
    if len(path) >= 2 and path[1] == ":" and path[0].isalpha() and path[0].isascii():
        if len(path) == 2 or path[2] not in "/\\":
            raise GuardError("ledger path has a drive-relative form")
        rest = path[2:]
    if ":" in rest:
        raise GuardError("ledger path contains a colon (alternate data stream or device form)")
    for part in rest.replace("\\", "/").split("/"):
        if part == "":
            continue
        if part == "..":
            raise GuardError("ledger path contains a parent-directory component")
        if part != "." and (part.endswith(".") or part.endswith(" ")):
            raise GuardError("ledger path component ends in a dot or space")
        folded = unicodedata.normalize("NFKC", part).split(".")[0].rstrip(" ").upper()
        if folded in _RESERVED_NAMES:
            raise GuardError("ledger path names a reserved device")


class ReplayLedger:
    """Append-only record of sends, kept OUTSIDE any lease. File format: a header line carrying a random ledger id,
    then one JSON line per consumed (authority hash, mutation id), each with a CRC, so newlines or colons in ids
    cannot corrupt the format.

    With a `path` the ledger is DURABLE and MULTI-PROCESS SAFE on one local filesystem: every operation takes an OS
    file lock, re-reads the file (so entries written by other processes or ledger objects are seen), checks, appends,
    flushes and fsyncs before consume() returns. A torn final line (crash mid-write) is ignored and truncated, because
    consume() had not returned and so no send followed; a corrupt earlier line fails closed. consume(key, limit)
    also refuses a send once `limit` sends are recorded for the authority, across missions and processes.

    IDENTITY: the header id is copied into every lease (`ledger_id`); resume() refuses a lease whose id differs from
    the ledger's, so a deleted-and-recreated or replaced ledger is detected for resumed missions. A deployment that
    pins the id (`expected_id`, e.g. recorded in the authorization) also detects a missing or replaced file for FRESH
    missions: a missing file or a different id then raises.
    NOT guaranteed: deletion or replacement of the file when no id is pinned and no lease is involved; RESTORE of an
    older copy of the same file (same id, fewer entries); callers using different ledger files; a volatile
    (path=None) ledger across processes; network filesystems without working locks; power-loss durability.
    Without a path the ledger is process-local (tests only); resume() refuses it unless explicitly allowed."""

    HEADER = "R2LEDGER"

    def __init__(self, path=None, expected_id=None):
        if path is not None and (not isinstance(path, str) or not path):
            raise GuardError("ledger path must be a non-empty string or None")
        if path is not None:
            _check_ledger_path(path)
        if expected_id is not None and path is None:
            raise GuardError("expected_id needs a file-backed ledger")
        self._tlock = threading.RLock()
        self.path = path
        self.is_durable = path is not None
        self.expected_id = expected_id
        self.ledger_id = None
        self._keys = set()
        self._order = []                              # entries in append order (the anchor chain depends on it)
        if path:
            self._sync()

    @staticmethod
    def _crc(auth, mut):
        return "%08x" % (zlib.crc32((auth + "\x00" + mut).encode("utf-8")) & 0xFFFFFFFF)

    @staticmethod
    def _as_key(key):
        if isinstance(key, (str, bytes)):
            raise GuardError("ledger key must be (authority hash, mutation id) non-empty strings")
        try:
            return tuple(key)
        except TypeError:
            raise GuardError("ledger key must be (authority hash, mutation id) non-empty strings")

    @staticmethod
    def _check_key(key):
        if not (isinstance(key, tuple) and len(key) == 2 and all(isinstance(x, str) and x for x in key)):
            raise GuardError("ledger key must be (authority hash, mutation id) non-empty strings")
        if any(ord(c) < 32 or ord(c) == 127 for c in key[0] + key[1]):
            raise GuardError("ledger key contains control characters")
        try:
            (key[0] + key[1]).encode("utf-8")
        except UnicodeEncodeError:
            raise GuardError("ledger key is not valid text")

    def _header_line(self, lid):
        return (json.dumps({"hdr": self.HEADER, "v": 1, "id": lid, "c": self._crc(lid, "HDR")}, separators=(",", ":")) + "\n").encode("utf-8")

    def _parse(self, data):
        """Return (ledger id or None, keys, entries in file order). None means the file is empty or holds only a torn header."""
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            raise GuardError("ledger corrupted (not UTF-8)")
        complete = text.split("\n")[:-1]               # the last element is the (possibly empty) torn tail
        lid, keys, order = None, set(), []
        for n, line in enumerate(complete, 1):
            try:
                rec = json.loads(line)
            except Exception:
                raise GuardError("ledger corrupted at line %d" % n)
            if n == 1:
                ok = isinstance(rec, dict) and rec.get("hdr") == self.HEADER and rec.get("v") == 1 and isinstance(rec.get("id"), str) \
                    and rec.get("c") == self._crc(rec["id"], "HDR")
                if not ok:
                    raise GuardError("ledger corrupted: missing or invalid header")
                lid = rec["id"]
                continue
            try:
                a, m_, c = rec["a"], rec["m"], rec["c"]
                ok = isinstance(a, str) and isinstance(m_, str) and c == self._crc(a, m_)
            except Exception:
                ok = False
            if not ok:
                raise GuardError("ledger corrupted at line %d" % n)
            keys.add((a, m_))
            order.append((a, m_))
        return lid, keys, order

    def _load(self, fh):
        """Under the lock: read, validate identity, create the header of a new file. Returns the current bytes."""
        fh.seek(0)
        data = fh.read()
        lid, keys, order = self._parse(data)
        if lid is None:
            if self.expected_id is not None:
                raise GuardError("ledger is empty or missing (expected id %s)" % self.expected_id)
            if data:
                fh.truncate(0)
            lid = uuid.uuid4().hex
            data = self._header_line(lid)
            fh.seek(0, 2)
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        if self.ledger_id is not None and lid != self.ledger_id:
            raise GuardError("ledger identity changed (file replaced?)")
        if self.expected_id is not None and lid != self.expected_id:
            raise GuardError("ledger identity differs from the expected id")
        self.ledger_id = lid
        self._keys |= keys
        self._order = order                           # the file is the source of truth for the entry order
        return data

    def _require_present(self):
        if self.expected_id is not None and not os.path.exists(self.path):
            raise GuardError("ledger file missing (expected id %s)" % self.expected_id)

    @_io_guard
    def _sync(self):
        self._require_present()
        with open(self.path, "a+b") as fh:
            _lock(fh)
            try:
                self._load(fh)
            finally:
                _unlock(fh)

    @_tlocked
    def anchor(self):
        """{ledger_id, count, head}: store it SOMEWHERE THE LEDGER'S HOST CANNOT REWRITE (a lease, an authorization record,
        a separate system). check_anchor() then detects a restored older copy or rewritten history; without an
        independently held anchor these cannot be detected."""
        if self.path:
            self._sync()
        lid = self.ledger_id or "VOLATILE"
        return {"ledger_id": lid, "count": len(self._order), "head": _chain(lid, self._order)[-1]}

    @_tlocked
    def check_anchor(self, anchor):
        if not isinstance(anchor, dict) or not isinstance(anchor.get("ledger_id"), str) or not _count(anchor.get("count")) \
                or not isinstance(anchor.get("head"), str) or len(anchor["head"]) != 64:
            raise GuardError("ledger anchor is malformed")
        if self.path:
            self._sync()
        lid = self.ledger_id or "VOLATILE"
        if anchor["ledger_id"] != lid:
            raise GuardError("ledger identity differs from the anchor")
        if len(self._order) < anchor["count"]:
            raise GuardError("ledger has fewer entries than the anchor (an older copy may have been restored)")
        if _chain(lid, self._order)[anchor["count"]] != anchor["head"]:
            raise GuardError("ledger history differs from the anchor")
        return True

    @_tlocked
    def has(self, key):
        key = self._as_key(key)
        if self.path:
            self._sync()
        return key in self._keys

    @_tlocked
    def for_authority(self, authority_hash):
        if self.path:
            self._sync()
        return {k for k in self._keys if k[0] == authority_hash}

    def _admit(self, key, limit):
        if key in self._keys:
            raise GuardError("replay: mutation authority already consumed (ledger)")
        if limit is not None and sum(1 for k in self._keys if k[0] == key[0]) >= limit:
            raise GuardError("authority send count exhausted (ledger)")

    @_tlocked
    def consume(self, key, limit=None):
        key = self._as_key(key)
        self._check_key(key)
        if limit is not None and not _count(limit):
            raise GuardError("ledger limit must be a non-negative integer or None")
        if not self.path:
            self._admit(key, limit)
            self._keys.add(key)
            self._order.append(key)
            return
        self._consume_file(key, limit)

    @_io_guard
    def _consume_file(self, key, limit):
        self._require_present()
        with open(self.path, "a+b") as fh:
            _lock(fh)
            try:
                data = self._load(fh)
                self._admit(key, limit)
                torn = data.split(b"\n")[-1]
                if torn:                                  # discard a torn tail before appending
                    fh.truncate(len(data) - len(torn))
                fh.seek(0, 2)
                fh.write((json.dumps({"a": key[0], "m": key[1], "c": self._crc(*key)}, separators=(",", ":")) + "\n").encode("utf-8"))
                fh.flush()
                os.fsync(fh.fileno())
                self._keys.add(key)
                self._order.append(key)
            finally:
                _unlock(fh)


def _chain(ledger_id, order):
    """Hash chain over the ledger: out[i] is the head after i entries. A copy that is older, shorter or rewritten has a
    different head at the anchored position."""
    h = hashlib.sha256(("MCR3-LEDGER|" + ledger_id).encode("utf-8")).hexdigest()
    out = [h]
    for a, m in order:
        h = hashlib.sha256((h + "|" + a + "\x00" + m).encode("utf-8")).hexdigest()
        out.append(h)
    return out


def _count(x):
    """A usable count: a real int (not bool, not float/NaN), non-negative."""
    return isinstance(x, int) and not isinstance(x, bool) and x >= 0


def provider_ref_ok(ref, provider_id):
    """readback contract provider_ref must be exactly '<provider_id>::<tool>' with a non-empty tail and no further
    '::' (R2.0 used a prefix test that accepted an empty tail and nested separators)."""
    if not isinstance(ref, str) or not isinstance(provider_id, str) or not provider_id or "::" in provider_id:
        return False
    pid, sep, tail = ref.partition("::")
    return sep == "::" and pid == provider_id and tail != "" and "::" not in tail


def _exists_consistent(rb):
    o = rb["observed"]
    if rb["existence"] == "UNKNOWN" or "exists" not in o:
        return True
    return o["exists"] is (rb["existence"] == "EXISTS")


# Library trust boundary: guards protect against logic errors and malformed/forged EVIDENCE presented to a
# Mission. They do not defend against hostile code running in the same process (which can mutate objects).
# They verify CONSISTENCY of evidence, not PROVENANCE (no signatures). Direct state changes are refused
# unless they come through a guard method (token below).
_TOKEN = object()

SLOT_KINDS = {"intent": "MissionIntent", "principal": "PrincipalContext", "delegation": "DelegationEnvelope",
              "authority": "ExecutionAuthority", "capability": "CapabilityBinding", "provider": "ProviderBinding",
              "budget": "MutationBudget", "tx": "TransactionEnvelope", "checkpoint": "PreMutationCheckpoint",
              "execution_receipt": "ExecutionReceipt", "commit": "CommitObservation",
              "readback": "AuthoritativeReadbackReceipt", "outcome": "OutcomeReceipt",
              "outcome_contract": "ExpectedOutcomeContract", "readback_contract": "AuthoritativeReadbackContract",
              "completion": "CompletionReceipt", "comp_grant": "CompensationGrant",
              "comp_receipt": "CompensationReceipt", "comp_readback": "AuthoritativeReadbackReceipt", "comp_resolution": "AuthoritativeReadbackReceipt",
              "comp_execution": "ExecutionReceipt"}
POST_SEND_CLASSES = ("PROVIDER_RESPONSE_SUCCESS", "CALL_SENT_NO_RESPONSE", "PROVIDER_ERROR", "COMMIT_UNKNOWN")
# compensating calls: a failure may also be "never sent"; an unknown outcome needs a readback before another attempt
COMP_FAILURE_CLASSES = ("CALL_NOT_SENT", "CALL_SENT_NO_RESPONSE", "PROVIDER_ERROR", "COMMIT_UNKNOWN")
COMP_UNKNOWN_CLASSES = ("CALL_SENT_NO_RESPONSE", "COMMIT_UNKNOWN")
# Evidence a resumed mission may be given: pre-observation only. Readback, commit, outcome and completion must
# be produced fresh by the guard methods after resume.
RESUME_SLOTS = ("intent", "principal", "delegation", "capability", "provider", "tx", "budget", "outcome_contract",
                "readback_contract", "authority", "execution_receipt")
RESUME_REQUIRED = ("intent", "principal", "delegation", "capability", "provider", "tx", "budget", "outcome_contract",
                   "readback_contract", "authority")

# Relational checks run by COMPLETE. One id per relation; every id has a violation recipe in the validator
# and an automatic mutant in the mutation harness (a new relation without both fails the tests).
RELATIONS = {
    "R01": "delegation not issued to this principal", "R02": "authority not derived from delegation",
    "R03": "authority mission mismatch", "R04": "intent mission mismatch", "R05": "authority scope exceeds delegation",
    "R06": "authority mutation count exceeds delegation", "R07": "budget not derived from authority",
    "R08": "budget exceeds authority", "R09": "budget allows retries or expansion",
    "R10": "budget differs from mission limit", "R11": "authority is not single use",
    "R12": "capability binding not from this authority", "R13": "capability outside authority scope",
    "R14": "capability does not match provider tool", "R15": "capability provider_ref differs from provider identity",
    "R16": "transaction identity mismatch", "R17": "transaction mission mismatch", "R18": "mutation not in transaction",
    "R19": "mutation authority was never consumed", "R20": "outcome contract not frozen or not correlated",
    "R22": "readback contract not authoritative", "R51": "readback contract provider differs from the bound provider",
    "R52": "delegation expires_at is not a valid UTC time", "R53": "intent expected_outcome_hash differs from the frozen outcome contract",
    "R54": "readback lacks a check the readback contract requires", "R23": "checkpoint does not pin the transaction",
    "R24": "checkpoint does not pin the budget", "R25": "checkpoint does not pin the outcome contract",
    "R26": "checkpoint does not pin the readback contract", "R27": "checkpoint budget differs from budget limit",
    "R28": "execution receipt transaction mismatch", "R29": "execution receipt mutation mismatch",
    "R30": "execution receipt call class invalid", "R31": "readback transaction mismatch",
    "R32": "readback mutation mismatch", "R50": "readback existence contradicts observed.exists", "R33": "readback not produced under the frozen contract",
    "R34": "readback is not from an authoritative source", "R35": "readback is not EXISTS",
    "R36": "commit observation transaction mismatch", "R37": "commit observation mutation mismatch",
    "R38": "commit observation not bound to readback", "R39": "commit state is not COMMITTED",
    "R40": "outcome receipt transaction mismatch", "R41": "outcome receipt not bound to readback",
    "R42": "outcome receipt not bound to outcome contract", "R43": "outcome result is not PASS",
    "R44": "predicates do not pass on the readback", "R45": "completion authority hash mismatch",
    "R46": "completion execution receipt hash mismatch", "R47": "completion commit observation hash mismatch",
    "R48": "completion outcome receipt hash mismatch", "R49": "completion transaction mismatch",
}


def atomic(fn):
    """A guard method either fully succeeds or changes nothing (state, evidence, budget, mission replay set).
    The external ReplayLedger is deliberately NOT rolled back: a consumed send stays consumed."""
    @functools.wraps(fn)
    def wrapper(self, *a, **k):
        with self._lock:                              # one guard call at a time per Mission (re-entrant)
            snap = (self.state, list(self.history), dict(self.ev), self.remaining, set(self.consumed), self.mutations_sent)
            try:
                return fn(self, *a, **k)
            except BaseException as exc:
                self.state, self.history, self.ev, self.remaining, self.consumed, self.mutations_sent = snap
                if isinstance(exc, (KeyError, TypeError, AttributeError, ValueError, IndexError)):
                    raise GuardError("malformed argument: %s" % type(exc).__name__) from exc
                raise
    return wrapper


class RevocationList:
    """Offline revocation source for tests and simple deployments: revoked object hashes. Callable as (kind, object_hash)."""
    def __init__(self, revoked=()):
        self.revoked = set(revoked)

    def revoke(self, object_hash):
        self.revoked.add(object_hash)

    def __call__(self, kind, object_hash):
        return object_hash in self.revoked


class Mission:
    """Evidence-gated state machine. Every object a guard method accepts is verified (kind and hash) and
    deep-copied first, so later changes by the caller cannot alter recorded evidence."""

    def __init__(self, mission_id, transaction_id, max_mutations, ledger=None, clock=None, revocation_check=None):
        if clock is not None and not callable(clock):
            raise GuardError("clock must be callable")
        if revocation_check is not None and not callable(revocation_check):
            raise GuardError("revocation_check must be callable")
        self._revoked = revocation_check          # (kind, object_hash) -> exactly False when NOT revoked; anything else denies
        self._clock = clock or time.time
        if not isinstance(max_mutations, int) or isinstance(max_mutations, bool) or max_mutations < 0:
            raise GuardError("max_mutations must be a non-negative integer")
        self.mission_id = mission_id
        self.transaction_id = transaction_id
        self.state = "PLANNED"
        self.history = [("PLANNED", None)]
        self.ev = {}                     # evidence slot -> object
        self.remaining = max_mutations
        self.consumed = set()            # (authority hash, mutation id) consumed by this mission object
        self.ledger = ledger if ledger is not None else ReplayLedger()
        self.mutations_sent = 0
        self.max_mutations = max_mutations
        self._resuming = False
        self._lock = threading.RLock()

    # -- helpers
    def _go(self, to, ref=None, _tok=None):
        if _tok is not _TOKEN:
            raise GuardError("direct state change refused: %s must be entered through its guard method" % to)
        if to not in TRANSITIONS[self.state]:
            raise GuardError("illegal transition %s -> %s" % (self.state, to))
        self.state = to
        self.history.append((to, ref))

    def _need(self, slot):
        if slot not in self.ev:
            raise GuardError("missing evidence %s" % slot)
        return self.ev[slot]

    def _accept(self, slot, obj):
        return _accept_obj(slot, obj)

    def _corr(self, obj):
        if obj.get("transaction_id") != self.transaction_id:
            raise GuardError("transaction correlation mismatch on %s" % obj.get("kind"))

    def _expiry_guard(self, delegation, what):
        exp = parse_expiry(delegation.get("expires_at"))
        if exp is None:
            raise GuardError("delegation expires_at is not a valid UTC time")
        if self._clock() >= exp:
            raise GuardError("delegation expired (%s)" % what)

    def _revocation_guard(self, what):
        """If a revocation source is connected, principal, delegation and authority must each be reported NOT revoked
        (exactly False). A raising source, or any other answer, is treated as revoked (fail closed). With no source
        connected nothing is checked: the model cannot know about revocations it is not told about."""
        if self._revoked is None:
            return
        for kind in ("principal", "delegation", "authority"):
            obj = self.ev.get(kind)
            if obj is None:
                continue
            try:
                ok = self._revoked(kind, obj["object_hash"]) is False
            except Exception:
                ok = False
            if not ok:
                raise GuardError("%s revoked or revocation status unknown (%s)" % (kind, what))

    def _rel(self, rid, ok):
        if not ok:
            raise GuardError("evidence chain inconsistent [%s]: %s" % (rid, RELATIONS[rid]))

    # -- forward path
    @atomic
    def context_ready(self, intent, principal):
        intent, principal = self._accept("intent", intent), self._accept("principal", principal)
        roles = principal["roles"]
        if not (isinstance(principal["principal_id"], str) and principal["principal_id"] and isinstance(principal["tenant"], str) and principal["tenant"]
                and isinstance(roles, list) and all(isinstance(r, str) and r for r in roles) and len(set(roles)) == len(roles)):
            raise GuardError("principal needs a non-empty principal_id and tenant and a list of unique non-empty role names")
        if intent["mission_id"] != self.mission_id:
            raise GuardError("intent mission mismatch")
        self.ev["intent"], self.ev["principal"] = intent, principal
        self._go("CONTEXT_READY", intent["object_hash"], _tok=_TOKEN)

    @atomic
    def authorize(self, delegation, authority, budget):
        delegation, authority, budget = (self._accept("delegation", delegation), self._accept("authority", authority),
                                         self._accept("budget", budget))
        if delegation["principal_hash"] != self._need("principal")["object_hash"]:
            raise GuardError("delegation not issued to this principal")
        self._expiry_guard(delegation, "at authorization")
        if authority["delegation_hash"] != delegation["object_hash"]:
            raise GuardError("authority not derived from delegation")
        if authority["mission_id"] != self.mission_id:
            raise GuardError("authority mission mismatch")
        if not attenuated(authority["scope"], delegation["scope"]):
            raise GuardError("authority exceeds delegation (no attenuation)")
        if authority["max_mutations"] > delegation["max_mutations"]:
            raise GuardError("authority mutation count exceeds delegation")
        for what, val in (("delegation", delegation["max_mutations"]), ("authority", authority["max_mutations"]), ("budget", budget["max_mutations"])):
            if not _count(val):
                raise GuardError("%s mutation count must be a non-negative integer" % what)
        if authority["single_use"] is not True:
            raise GuardError("authority must be single use")
        if budget["authority_hash"] != authority["object_hash"] or budget["max_mutations"] > authority["max_mutations"]:
            raise GuardError("budget not bounded by authority")
        if budget["expansion_allowed"] is not False or type(budget["retries"]) is not int or budget["retries"] != 0:
            raise GuardError("budget must forbid expansion and retries")
        if budget["max_mutations"] != self.max_mutations:
            raise GuardError("budget differs from mission limit")
        if any((k[0] if isinstance(k, tuple) else k) == authority["object_hash"] for k in self.consumed) \
                or (not self._resuming and self.ledger.for_authority(authority["object_hash"])):
            raise GuardError("authority already consumed")
        self.ev.update(delegation=delegation, authority=authority, budget=budget)
        try:
            self._revocation_guard("at authorization")
        except GuardError:
            for k in ("delegation", "authority", "budget"):
                self.ev.pop(k, None)
            raise
        self._go("AUTHORIZED", authority["object_hash"], _tok=_TOKEN)

    @atomic
    def bind(self, capability_binding, provider_binding):
        capability_binding, provider_binding = self._accept("capability", capability_binding), self._accept("provider", provider_binding)
        a = self._need("authority")
        if capability_binding["authority_hash"] != a["object_hash"]:
            raise GuardError("capability binding not from this authority")
        if capability_binding["capability"] not in a["scope"]:
            raise GuardError("capability outside authority scope")
        if capability_binding["capability"] != provider_binding["tool_name"]:
            raise GuardError("capability does not match provider tool")
        if capability_binding["provider_ref"] != provider_binding["identity"]:
            raise GuardError("capability provider_ref differs from provider identity")
        self.ev.update(capability=capability_binding, provider=provider_binding)
        self._go("BOUND", provider_binding["contract_fingerprint"], _tok=_TOKEN)

    @atomic
    def prewrite_validate(self, tx, outcome_contract, readback_contract, checkpoint):
        tx, outcome_contract = self._accept("tx", tx), self._accept("outcome_contract", outcome_contract)
        readback_contract, checkpoint = self._accept("readback_contract", readback_contract), self._accept("checkpoint", checkpoint)
        self._corr(tx)
        self._corr(outcome_contract)
        if tx["mission_id"] != self.mission_id or outcome_contract["mission_id"] != self.mission_id:
            raise GuardError("transaction or outcome contract mission mismatch")
        ids = tx["mutation_ids"]
        if not isinstance(ids, list) or not ids or not all(isinstance(i, str) and i for i in ids):
            raise GuardError("transaction mutation ids must be a non-empty list of strings")
        if outcome_contract["frozen"] is not True:
            raise GuardError("outcome contract not frozen before mutation")
        check_predicates(outcome_contract["predicates"])
        budget = self._need("budget")
        if checkpoint["outcome_contract_hash"] != outcome_contract["object_hash"]:
            raise GuardError("checkpoint does not pin outcome contract")
        if checkpoint["readback_contract_hash"] != readback_contract["object_hash"]:
            raise GuardError("checkpoint does not pin readback contract")
        if checkpoint["budget_hash"] != budget["object_hash"]:
            raise GuardError("checkpoint does not pin budget")
        if checkpoint["transaction_hash"] != tx["object_hash"]:
            raise GuardError("checkpoint does not pin transaction")
        if not _count(checkpoint["remaining_budget"]) or checkpoint["remaining_budget"] != budget["max_mutations"]:
            raise GuardError("checkpoint budget differs from budget limit")
        if self._need("intent")["expected_outcome_hash"] != outcome_contract["object_hash"]:
            raise GuardError("intent expected_outcome_hash differs from the frozen outcome contract")
        if readback_contract["source_level_required"] != "AUTHORITATIVE_REPOSITORY":
            raise GuardError("readback contract is not authoritative")
        chk = readback_contract["checks"]
        if not isinstance(chk, list) or not chk or not all(isinstance(c, str) and c for c in chk) or len(set(chk)) != len(chk):
            raise GuardError("readback contract checks must be a non-empty list of unique strings")
        if not provider_ref_ok(readback_contract["provider_ref"], self._need("provider")["provider_id"]):
            raise GuardError("readback contract provider differs from the bound provider")
        self.ev.update(tx=tx, outcome_contract=outcome_contract,
                       readback_contract=readback_contract, checkpoint=checkpoint)
        self._go("PREWRITE_VALIDATED", checkpoint["object_hash"], _tok=_TOKEN)

    @atomic
    def begin_execution(self, mutation_id, contract_fingerprint_now):
        """Budget + replay guard are consumed BEFORE the call leaves the client (and only if the step is legal)."""
        if not isinstance(mutation_id, str) or not mutation_id or any(ord(c) < 32 or ord(c) == 127 for c in mutation_id):
            raise GuardError("invalid mutation id")
        if contract_fingerprint_now != self._need("provider")["contract_fingerprint"]:
            raise GuardError("contract drift at point of use: revalidate (fail closed)")
        if mutation_id not in self._need("tx")["mutation_ids"]:
            raise GuardError("mutation not in transaction")
        self._expiry_guard(self._need("delegation"), "at the point of sending")
        self._revocation_guard("at the point of sending")
        key = (self.ev["authority"]["object_hash"], mutation_id)
        if key in self.consumed or self.ledger.has(key):
            raise GuardError("replay: mutation authority already consumed")
        if self.remaining <= 0:
            raise GuardError("mutation budget exhausted")
        if "EXECUTION_STARTED" not in TRANSITIONS[self.state]:
            raise GuardError("illegal transition %s -> EXECUTION_STARTED" % self.state)
        self.ledger.consume(key, limit=self.ev["budget"]["max_mutations"])
        self.consumed.add(key)
        self.remaining -= 1
        self.mutations_sent += 1
        self.ev["mutation_id"] = mutation_id
        self._go("EXECUTION_STARTED", mutation_id, _tok=_TOKEN)

    @atomic
    def record_execution(self, receipt):
        """Execution receipt classifies the call; it never implies commit."""
        receipt = self._accept("execution_receipt", receipt)
        self._corr(receipt)
        if receipt.get("mutation_id") != self.ev.get("mutation_id"):
            raise GuardError("execution receipt not correlated to mutation")
        c = receipt["call_class"]
        if c not in POST_SEND_CLASSES:
            raise GuardError("call_class %s not valid after execution started" % c)
        self.ev["execution_receipt"] = receipt
        if c == "PROVIDER_RESPONSE_SUCCESS":
            self._go("EXECUTED", receipt["object_hash"], _tok=_TOKEN)
        else:
            self._go("COMMIT_STATE_UNKNOWN", receipt["object_hash"], _tok=_TOKEN)

    @atomic
    def request_readback(self):
        self._go("AUTHORITATIVE_READBACK_PENDING", _tok=_TOKEN)

    @atomic
    def observe_readback(self, rb):
        """rb: AuthoritativeReadbackReceipt. Non-authoritative sources and errors are UNKNOWN."""
        rb = self._accept("readback", rb)
        self._corr(rb)
        contract = self._need("readback_contract")
        if rb["contract_hash"] != contract["object_hash"]:
            raise GuardError("readback not produced under frozen contract")
        if rb["mutation_id"] != self.ev["mutation_id"]:
            raise GuardError("readback not correlated to mutation")
        if not _exists_consistent(rb):
            raise GuardError("readback existence contradicts observed.exists")
        self.ev["readback"] = rb
        self._go("AUTHORITATIVE_READBACK_OBSERVED", rb["object_hash"], _tok=_TOKEN)

    def _readback_authoritative(self, rb):
        return rb["source_level"] == "AUTHORITATIVE_REPOSITORY"

    @staticmethod
    def _checks_satisfied(contract, rb):
        """Every check the readback contract names must be present in the observation and known."""
        obs = rb.get("observed")
        return isinstance(obs, dict) and all(c in obs and obs[c] not in (None, "UNKNOWN") for c in contract["checks"])

    @atomic
    def decide_commit(self, observation):
        observation = self._accept("commit", observation)
        rb = self._need("readback")
        if observation["readback_receipt_hash"] != rb["object_hash"]:
            raise GuardError("commit observation not bound to readback")
        self._corr(observation)
        if observation["mutation_id"] != self.ev["mutation_id"]:
            raise GuardError("commit observation not correlated to mutation")
        if not self._readback_authoritative(rb) or rb["existence"] == "UNKNOWN"                 or (rb["existence"] == "EXISTS" and not self._checks_satisfied(self._need("readback_contract"), rb)):
            self._go("COMMIT_STATE_UNKNOWN", observation["object_hash"], _tok=_TOKEN)
            return self.state
        if rb["existence"] == "ABSENT":
            # Not committed. Remains fail-closed: no retry without a new authorization lineage.
            self._go("FAILED_AFTER_POSSIBLE_MUTATION", observation["object_hash"], _tok=_TOKEN)
            return self.state
        if observation["commit_state"] != "COMMITTED":
            raise GuardError("commit observation contradicts authoritative EXISTS readback")
        self.ev["commit"] = observation
        self._go("COMMITTED", observation["object_hash"], _tok=_TOKEN)
        return self.state

    @atomic
    def validate_outcome(self, outcome):
        outcome = self._accept("outcome", outcome)
        self._need("commit")
        oc, rb = self._need("outcome_contract"), self._need("readback")
        if outcome["outcome_contract_hash"] != oc["object_hash"] or outcome["readback_receipt_hash"] != rb["object_hash"]:
            raise GuardError("outcome receipt not bound to contract+readback")
        self._corr(outcome)
        recomputed = eval_predicates(oc["predicates"], observed_view(rb))
        if outcome["result"] != recomputed:
            raise GuardError("outcome receipt result disagrees with recomputation")
        self._go("OUTCOME_VALIDATION_PENDING", _tok=_TOKEN)
        self.ev["outcome"] = outcome
        if recomputed == "PASS":
            self._go("OUTCOME_VALIDATED", outcome["object_hash"], _tok=_TOKEN)
        elif recomputed == "FAIL":
            self._go("COMPENSATION_REQUIRED", outcome["object_hash"], _tok=_TOKEN)
        # UNKNOWN predicate: stay in OUTCOME_VALIDATION_PENDING (COMPLETE=FALSE); never PASS/FAIL.
        return self.state

    def _verify_chain(self, completion):
        """Relational validation of the whole evidence chain (hash validity alone is not authentication)."""
        required = [s for s, _ in CHAIN_SLOTS[:-1]] + ["outcome_contract", "readback_contract"]
        missing = [s for s in required if s not in self.ev]
        if missing:
            raise GuardError("incomplete evidence chain: missing %s" % missing)
        e = self.ev
        for slot in required:
            o = e[slot]
            if not isinstance(o, dict) or o.get("kind") != SLOT_KINDS[slot]:
                raise GuardError("evidence %s has wrong kind" % slot)
            if not _hash_ok(o):
                raise GuardError("evidence %s hash invalid (tampered)" % slot)
        h = lambda s: e[s]["object_hash"]
        mid, T = e.get("mutation_id"), self.transaction_id
        dl, au, bu, cb, pv = e["delegation"], e["authority"], e["budget"], e["capability"], e["provider"]
        tx, oc, rc, cp = e["tx"], e["outcome_contract"], e["readback_contract"], e["checkpoint"]
        er, rb, co, oo = e["execution_receipt"], e["readback"], e["commit"], e["outcome"]
        self._rel("R01", dl["principal_hash"] == h("principal"))
        self._rel("R02", au["delegation_hash"] == h("delegation"))
        self._rel("R03", au["mission_id"] == self.mission_id)
        self._rel("R04", e["intent"]["mission_id"] == self.mission_id)
        self._rel("R05", attenuated(au["scope"], dl["scope"]))
        self._rel("R06", au["max_mutations"] <= dl["max_mutations"])
        self._rel("R07", bu["authority_hash"] == h("authority"))
        self._rel("R08", bu["max_mutations"] <= au["max_mutations"])
        self._rel("R09", type(bu["retries"]) is int and bu["retries"] == 0 and bu["expansion_allowed"] is False)
        self._rel("R10", bu["max_mutations"] == self.max_mutations)
        self._rel("R11", au["single_use"] is True)
        self._rel("R12", cb["authority_hash"] == h("authority"))
        self._rel("R13", cb["capability"] in au["scope"])
        self._rel("R14", cb["capability"] == pv["tool_name"])
        self._rel("R15", cb["provider_ref"] == pv["identity"])
        self._rel("R16", tx["transaction_id"] == T)
        self._rel("R17", tx["mission_id"] == self.mission_id)
        self._rel("R18", mid is not None and mid in tx["mutation_ids"])
        self._rel("R19", (h("authority"), mid) in self.consumed)
        self._rel("R20", oc["frozen"] is True and oc["transaction_id"] == T and oc["mission_id"] == self.mission_id)
        check_predicates(oc["predicates"])
        self._rel("R22", rc["source_level_required"] == "AUTHORITATIVE_REPOSITORY")
        self._rel("R51", provider_ref_ok(rc["provider_ref"], pv["provider_id"]))
        self._rel("R23", cp["transaction_hash"] == h("tx"))
        self._rel("R24", cp["budget_hash"] == h("budget"))
        self._rel("R25", cp["outcome_contract_hash"] == h("outcome_contract"))
        self._rel("R26", cp["readback_contract_hash"] == h("readback_contract"))
        self._rel("R27", cp["remaining_budget"] == bu["max_mutations"])
        self._rel("R28", er["transaction_id"] == T)
        self._rel("R29", er["mutation_id"] == mid)
        self._rel("R30", er["call_class"] in POST_SEND_CLASSES)
        self._rel("R31", rb["transaction_id"] == T)
        self._rel("R32", rb["mutation_id"] == mid)
        self._rel("R33", rb["contract_hash"] == h("readback_contract"))
        self._rel("R34", rb["source_level"] == "AUTHORITATIVE_REPOSITORY")
        self._rel("R35", rb["existence"] == "EXISTS")
        self._rel("R50", _exists_consistent(rb))
        self._rel("R36", co["transaction_id"] == T)
        self._rel("R37", co["mutation_id"] == mid)
        self._rel("R38", co["readback_receipt_hash"] == h("readback"))
        self._rel("R39", co["commit_state"] == "COMMITTED")
        self._rel("R40", oo["transaction_id"] == T)
        self._rel("R41", oo["readback_receipt_hash"] == h("readback"))
        self._rel("R42", oo["outcome_contract_hash"] == h("outcome_contract"))
        self._rel("R43", oo["result"] == "PASS")
        self._rel("R44", eval_predicates(oc["predicates"], observed_view(rb)) == "PASS")
        self._rel("R45", completion.get("authority_hash") == h("authority"))
        self._rel("R46", completion.get("execution_receipt_hash") == h("execution_receipt"))
        self._rel("R47", completion.get("commit_observation_hash") == h("commit"))
        self._rel("R48", completion.get("outcome_receipt_hash") == h("outcome"))
        self._rel("R49", completion.get("transaction_id") == T)
        self._rel("R52", parse_expiry(dl["expires_at"]) is not None)
        self._rel("R53", e["intent"]["expected_outcome_hash"] == h("outcome_contract"))
        self._rel("R54", self._checks_satisfied(rc, rb))

    @atomic
    def complete(self, completion):
        """COMPLETE needs the whole chain present, hash-valid AND relationally consistent, a hash-valid
        CompletionReceipt linking it, and state OUTCOME_VALIDATED. Persisted only after every guard passes."""
        completion = self._accept("completion", completion)
        if self.state != "OUTCOME_VALIDATED":
            raise GuardError("COMPLETE requires OUTCOME_VALIDATED")
        try:
            self._verify_chain(completion)
        except (KeyError, TypeError, AttributeError, IndexError) as exc:
            raise GuardError("evidence chain malformed: %s" % type(exc).__name__)
        self._go("COMPLETE", completion["object_hash"], _tok=_TOKEN)
        self.ev["completion"] = completion

    # -- failure / compensation
    @atomic
    def fail_before_mutation(self):
        if self.mutations_sent or ("authority" in self.ev and self.ledger.for_authority(self.ev["authority"]["object_hash"])):
            raise GuardError("mutation possibly sent; use FAILED_AFTER_POSSIBLE_MUTATION")
        self._go("FAILED_BEFORE_MUTATION", _tok=_TOKEN)

    @atomic
    def fail_after_possible_mutation(self):
        self._go("FAILED_AFTER_POSSIBLE_MUTATION", _tok=_TOKEN)

    @atomic
    def require_compensation(self):
        self._go("COMPENSATION_REQUIRED", _tok=_TOKEN)

    @atomic
    def authorize_compensation(self, grant):
        grant = self._accept("comp_grant", grant)
        a = self._need("authority")
        if grant["inherits_forward_authority"]:
            raise GuardError("compensation may not inherit forward authority")
        if grant["issued_by"] == a["object_hash"]:
            raise GuardError("compensation grant must not be issued from forward authority")
        if not _count(grant["max_mutations"]) or grant["max_mutations"] < 1 or not grant["preconditions"] or not grant["outcome_predicates"]:
            raise GuardError("compensation grant incomplete")
        if grant["capability"] in a["scope"]:
            raise GuardError("compensation capability lies within forward authority scope")
        check_predicates(grant["outcome_predicates"])
        check_predicates(grant["preconditions"])
        if grant["target"] not in (self.ev["intent"]["target_system"], self._need("tx")["transaction_id"]):
            raise GuardError("compensation target not tied to mission")
        if "readback" not in self.ev:
            raise GuardError("compensation preconditions need the forward readback")
        if self.ev["readback"]["source_level"] != "AUTHORITATIVE_REPOSITORY":
            raise GuardError("compensation preconditions need an authoritative forward readback")
        if eval_predicates(grant["preconditions"], observed_view(self.ev["readback"])) != "PASS":
            raise GuardError("compensation precondition not satisfied")
        if eval_predicates(grant["outcome_predicates"], observed_view(self.ev["readback"])) == "PASS":
            raise GuardError("compensation goal already satisfied by the forward readback")
        self.ev["comp_grant"] = grant
        self._go("COMPENSATION_AUTHORIZED", grant["object_hash"], _tok=_TOKEN)

    @atomic
    def begin_compensation(self, resolution_readback=None):
        """Every compensating call is a send and is accounted BEFORE it leaves: attempt n consumes the ledger entry
        (grant hash, COMPENSATION-ATTEMPT-n), limited to the grant's own budget (separate from the forward budget).
        Only one attempt may be open. After an attempt whose outcome is unknown (no response, commit unknown) a new
        attempt needs an authoritative readback showing the goal still unmet. Returns the attempt number."""
        grant = self._need("comp_grant")
        if self.state != "COMPENSATION_AUTHORIZED":
            raise GuardError("illegal transition %s -> compensation start" % self.state)
        self._revocation_guard("at the point of a compensating send")
        if self.ev.get("comp_open") is not None:
            raise GuardError("a compensation attempt is already open: record its result first")
        used = max(self.ev.get("comp_attempts", 0), len(self.ledger.for_authority(grant["object_hash"])))
        if used >= grant["max_mutations"]:
            raise GuardError("compensation budget exhausted")
        resolution = None
        if self.ev.get("comp_unresolved"):
            if resolution_readback is None:
                raise GuardError("previous compensation attempt outcome is unknown: an authoritative readback showing the goal unmet is required")
            resolution = self._accept("comp_resolution", resolution_readback)
            self._corr(resolution)
            if resolution["mutation_id"] != self.ev["mutation_id"] or resolution["contract_hash"] != self._need("readback_contract")["object_hash"]:
                raise GuardError("resolution readback not correlated to the mission")
            if resolution["source_level"] != "AUTHORITATIVE_REPOSITORY" or not _exists_consistent(resolution):
                raise GuardError("resolution readback must be authoritative and consistent")
            if eval_predicates(grant["outcome_predicates"], observed_view(resolution)) != "FAIL":
                raise GuardError("resolution readback does not show the compensation goal unmet")
        n = used + 1
        self.ledger.consume((grant["object_hash"], "COMPENSATION-ATTEMPT-%d" % n), limit=grant["max_mutations"])
        self.ev["comp_attempts"], self.ev["comp_open"] = n, n
        if resolution is not None:
            self.ev["comp_unresolved"] = False
            self.ev.setdefault("comp_resolutions", []).append(resolution["object_hash"])
        return n

    def _comp_execution(self, comp_execution):
        g = self._need("comp_grant")
        n = self.ev.get("comp_open")
        if n is None:
            raise GuardError("compensation was not begun")
        ex = self._accept("comp_execution", comp_execution)
        self._corr(ex)
        if ex["mutation_id"] != "COMPENSATION:%s#%d" % (g["object_hash"], n):
            raise GuardError("compensation execution receipt not bound to the grant")
        return g, n, ex

    @atomic
    def record_compensation_failure(self, comp_execution):
        """A compensating call that did not succeed. The attempt stays counted. A definite failure (not sent,
        provider error) allows the next attempt; an unknown outcome blocks it until a readback resolves it. When the
        grant budget is used up the mission becomes UNRECOVERABLE."""
        g, n, ex = self._comp_execution(comp_execution)
        c = ex["call_class"]
        if c == "PROVIDER_RESPONSE_SUCCESS":
            raise GuardError("a successful compensating call is recorded with record_compensation")
        if c not in COMP_FAILURE_CLASSES:
            raise GuardError("call_class %s not valid for a compensating call" % c)
        self.ev.setdefault("comp_log", []).append({"attempt": n, "call_class": c, "receipt_hash": ex["object_hash"]})
        self.ev["comp_open"] = None
        if c in COMP_UNKNOWN_CLASSES:
            self.ev["comp_unresolved"] = True
        if n >= g["max_mutations"]:
            self._go("UNRECOVERABLE", ex["object_hash"], _tok=_TOKEN)
        return self.state

    @atomic
    def record_compensation(self, comp_receipt, post_readback, comp_execution):
        """COMPENSATED needs: an open attempt, a successful execution receipt for it, a receipt bound to the grant, and an
        authoritative post-compensation readback that is distinct from the forward readback and satisfies the goal."""
        comp_receipt, post_readback = self._accept("comp_receipt", comp_receipt), self._accept("comp_readback", post_readback)
        g, n, comp_execution = self._comp_execution(comp_execution)
        if comp_execution["call_class"] != "PROVIDER_RESPONSE_SUCCESS":
            raise GuardError("compensating call must report success")
        if comp_receipt["grant_hash"] != g["object_hash"]:
            raise GuardError("compensation receipt not bound to its grant")
        self._corr(post_readback)
        if post_readback["mutation_id"] != self.ev["mutation_id"] or post_readback["contract_hash"] != self._need("readback_contract")["object_hash"]:
            raise GuardError("post-compensation readback not correlated to the mission")
        if post_readback["source_level"] != "AUTHORITATIVE_REPOSITORY":
            raise GuardError("post-compensation readback must be authoritative")
        if not _exists_consistent(post_readback):
            raise GuardError("readback existence contradicts observed.exists")
        fwd = self._need("readback")
        if post_readback["object_hash"] == fwd["object_hash"] or post_readback["observed"] == fwd["observed"]:
            raise GuardError("post-compensation readback is not distinct from the forward readback")
        if comp_receipt["readback_receipt_hash"] != post_readback["object_hash"]:
            raise GuardError("compensation receipt not bound to post readback")
        if eval_predicates(g["outcome_predicates"], observed_view(post_readback)) != "PASS" or comp_receipt["result"] != "PASS":
            raise GuardError("compensation outcome predicate not satisfied")
        self.ev["comp_open"] = None
        self._go("COMPENSATED", comp_receipt["object_hash"], _tok=_TOKEN)
        self.ev.update(comp_receipt=comp_receipt, comp_readback=post_readback, comp_execution=comp_execution)   # persisted only after every guard passed

    @atomic
    def declare_unrecoverable(self):
        self._go("UNRECOVERABLE", _tok=_TOKEN)

    # -- continuation
    def checkpoint_lease(self):
        with self._lock:
            cp = self._need("checkpoint")
            er = self.ev.get("execution_receipt")
            return make("ContinuationLease", lease_id="LEASE-" + chash([cp["object_hash"], sorted(map(str, self.consumed)), self.state])[:12],
                        checkpoint_hash=cp["object_hash"], transaction_id=self.transaction_id,
                        remaining_budget=self.remaining, state_at_checkpoint=self.state,
                        mutation_id=self.ev.get("mutation_id"),
                        execution_receipt_hash=er["object_hash"] if er else None,
                        ledger_id=self.ledger.ledger_id, ledger_anchor=self.ledger.anchor(),
                        consumed_authority_ids=sorted(("%s:%s" % k) for k in self.consumed))

    @classmethod
    def resume(cls, *args, **kwargs):
        """See _resume. Any malformed argument becomes a GuardError."""
        try:
            return cls._resume(*args, **kwargs)
        except (KeyError, TypeError, AttributeError, ValueError, IndexError) as exc:
            raise GuardError("malformed argument: %s" % type(exc).__name__) from exc

    @classmethod
    def _resume(cls, lease, checkpoint, original_budget, mission_id, evidence, ledger, allow_volatile_ledger=False, clock=None, revocation_check=None):
        """Rebuild a mission by re-running the REAL guard methods on re-presented evidence (so a resumed mission is
        held to exactly the checks a fresh one gets), then applying consumption. Lease, checkpoint and original budget
        must be hash-valid and agree with each other; consumption is the UNION of the lease and the external
        ReplayLedger, so a stale lease cannot re-open a send recorded there; after any possible send the mission
        restarts in COMMIT_STATE_UNKNOWN and needs a fresh readback. Only pre-observation evidence is accepted.
        A durable (file-backed) ledger is required unless allow_volatile_ledger is set (tests). Lease integrity
        (hash) is checked; authenticity (signature) is not provided by this library."""
        if not isinstance(ledger, ReplayLedger):
            raise GuardError("resume requires the ReplayLedger")
        if not ledger.is_durable and not allow_volatile_ledger:
            raise GuardError("resume requires a durable (file-backed) ledger")
        if not isinstance(evidence, dict):
            raise GuardError("resume requires re-presented evidence")
        for o, kind in ((lease, "ContinuationLease"), (checkpoint, "PreMutationCheckpoint"), (original_budget, "MutationBudget")):
            if not isinstance(o, dict) or o.get("kind") != kind or not _hash_ok(o):
                raise GuardError("%s absent, wrong kind or hash invalid" % kind)
        if lease["checkpoint_hash"] != checkpoint["object_hash"]:
            raise GuardError("lease not bound to checkpoint")
        if lease.get("ledger_id") is not None and lease["ledger_id"] != ledger.ledger_id:
            raise GuardError("ledger identity differs from the lease (deleted, replaced or restored ledger?)")
        lease_rem = lease["remaining_budget"]
        if not _count(lease_rem):
            raise GuardError("lease remaining_budget invalid")
        ids = lease["consumed_authority_ids"]
        if not isinstance(ids, list) or not all(isinstance(s_, str) and ":" in s_ for s_ in ids) or len(ids) != len(set(ids)):
            raise GuardError("lease consumed ids invalid")
        lease_consumed = {tuple(s_.split(":", 1)) for s_ in ids}
        pre_send = lease["state_at_checkpoint"] == "PREWRITE_VALIDATED"
        if (lease_consumed and pre_send) or (not lease_consumed and not pre_send):
            raise GuardError("lease state inconsistent with consumed set")
        extra = sorted(set(evidence) - set(RESUME_SLOTS))
        if extra:
            raise GuardError("resume accepts no downstream evidence: %s" % extra)
        for slot in RESUME_REQUIRED:
            if slot not in evidence:
                raise GuardError("resume evidence missing %s" % slot)
        ev = {slot: _accept_obj(slot, o) for slot, o in evidence.items()}
        if original_budget["object_hash"] != ev["budget"]["object_hash"]:
            raise GuardError("original budget does not match the re-presented budget")
        auth = ev["authority"]["object_hash"]
        if any(k[0] != auth for k in lease_consumed):
            raise GuardError("consumed set does not belong to the re-presented authority")
        total = original_budget["max_mutations"]
        if lease_rem + len(lease_consumed) > min(checkpoint["remaining_budget"], total):
            raise GuardError("continuation may not enlarge budget")
        m = cls(mission_id, lease["transaction_id"], total, ledger=ledger, clock=clock, revocation_check=revocation_check)
        m._resuming = True
        try:
            m.context_ready(ev["intent"], ev["principal"])
            m.authorize(ev["delegation"], ev["authority"], ev["budget"])
            m.bind(ev["capability"], ev["provider"])
            m.prewrite_validate(ev["tx"], ev["outcome_contract"], ev["readback_contract"], checkpoint)
        finally:
            m._resuming = False
        recorded = ledger.for_authority(auth)
        if not lease_consumed <= recorded:
            raise GuardError("lease claims a send that the ledger does not record")
        if not isinstance(lease.get("ledger_anchor"), dict):                  # 3.0: every lease carries an anchor of the ledger it was cut from
            raise GuardError("lease carries no ledger anchor")
        ledger.check_anchor(lease["ledger_anchor"])                           # detects a restored older copy or rewritten history
        consumed = lease_consumed | recorded
        m.remaining = min(lease_rem, total - len(consumed))
        if m.remaining < 0:
            raise GuardError("consumed mutations exceed the original budget")
        m.consumed = consumed
        m.mutations_sent = len(consumed)
        if not consumed:
            return m
        # a send may have happened: never silently restart or trust carried post-send state; reconcile
        mut = lease["mutation_id"] if lease["mutation_id"] else sorted(k[1] for k in consumed)[0]
        if mut not in ev["tx"]["mutation_ids"] or (auth, mut) not in consumed:
            raise GuardError("lease mutation id inconsistent")
        m.ev["mutation_id"] = mut
        er = ev.get("execution_receipt")
        if er is not None:
            if er["object_hash"] != lease["execution_receipt_hash"] or er.get("mutation_id") != mut or er.get("transaction_id") != lease["transaction_id"]:
                raise GuardError("execution receipt does not match lease")
        else:
            er = make("ExecutionReceipt", receipt_id="resume-" + lease["lease_id"], transaction_id=lease["transaction_id"],
                      mutation_id=mut, call_class="COMMIT_UNKNOWN")
        m.ev["execution_receipt"] = er
        m.state = "COMMIT_STATE_UNKNOWN"
        m.history.append(("RESUMED_AS_COMMIT_STATE_UNKNOWN", lease["object_hash"]))
        return m


# Architecture contract (spec section 19): 14 links, fixed order. Slot name -> chain label.
CHAIN_SLOTS = [("intent", "MISSION_INTENT"), ("principal", "PRINCIPAL_CONTEXT"), ("delegation", "DELEGATION"),
               ("authority", "AUTHORITY"), ("capability", "CAPABILITY_BINDING"), ("provider", "PROVIDER_CONTRACT"),
               ("budget", "MUTATION_BUDGET"), ("tx", "TRANSACTION"), ("checkpoint", "PREWRITE_CHECKPOINT"),
               ("execution_receipt", "EXECUTION_RECEIPT"), ("commit", "COMMIT_OBSERVATION"),
               ("readback", "AUTHORITATIVE_READBACK_RECEIPT"), ("outcome", "OUTCOME_RECEIPT"),
               ("completion", "COMPLETION_RECEIPT")]
EXPECTED_CHAIN = [label for _, label in CHAIN_SLOTS]


OUTCOME_CLASSES = ("EXECUTED", "PROVIDER_ACKNOWLEDGED", "COMMIT_OBSERVED", "OUTCOME_OBSERVED", "OUTCOME_VALIDATED", "COMPLETE",
                   "COMMIT_UNKNOWN", "OUTCOME_UNKNOWN", "COMPENSATION_REQUIRED", "UNRECOVERABLE")


def outcome_classification(m):
    """Derived classification of what the evidence supports, never an input. A provider acknowledgement is not a
    commit observation; a commit observation is not an observed outcome; an observed outcome is not a validated one.
    None means nothing was sent yet or the mission ended without a send (failed/compensated states are reported by
    their own state)."""
    st, ev = m.state, m.ev
    if st == "COMPLETE":
        return "COMPLETE"
    if st == "UNRECOVERABLE":
        return "UNRECOVERABLE"
    if st in ("COMPENSATION_REQUIRED", "COMPENSATION_AUTHORIZED"):
        return "COMPENSATION_REQUIRED"
    if st in ("COMMIT_STATE_UNKNOWN", "FAILED_AFTER_POSSIBLE_MUTATION"):
        return "COMMIT_UNKNOWN"
    if st == "OUTCOME_VALIDATED":
        return "OUTCOME_VALIDATED"
    if st == "OUTCOME_VALIDATION_PENDING":
        return "OUTCOME_UNKNOWN" if ev.get("outcome", {}).get("result") == "UNKNOWN" else "OUTCOME_OBSERVED"
    if st == "COMMITTED":
        return "COMMIT_OBSERVED"
    if st in ("AUTHORITATIVE_READBACK_PENDING", "AUTHORITATIVE_READBACK_OBSERVED", "EXECUTED"):
        er = ev.get("execution_receipt")
        return "PROVIDER_ACKNOWLEDGED" if er and er["call_class"] == "PROVIDER_RESPONSE_SUCCESS" else "EXECUTED"
    if st == "EXECUTION_STARTED":
        return "EXECUTED"
    return None


def chain_hashes(m):
    """Emit the links that exist, in contract order. A COMPLETE mission emits all 14, the last being the
    CompletionReceipt; a non-complete mission never emits a completion link."""
    return [(label, m.ev[slot]["object_hash"]) for slot, label in CHAIN_SLOTS if slot in m.ev]
