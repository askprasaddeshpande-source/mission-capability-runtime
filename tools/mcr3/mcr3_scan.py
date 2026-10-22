"""MCR 3.0 credential-shape scanner (heuristic; never proof of absence).

Detects well-known token SHAPES, private-key blocks, URL user-info, and secret-named assignments, in every plausible
text reading of a byte string (UTF-8, UTF-16/32 at every byte offset, Latin-1). Reports only the shape name and a
short non-reversible fingerprint, never the matched text, so a finding cannot itself leak a credential.

Synthetic fixtures for every shape are produced by `fixture(name)` at run time from fragments, so this file and the
repository hold no secret-shaped literal. Intentionally NOT detected (documented in the contract):
  * obfuscated or transformed secrets (zero-width characters, homoglyphs, base64/URL-encoded wrappers, values split
    across lines or strings);
  * a short value (under 16 characters) under a `token` / `authorization` name (too many identifiers);
  * a secret that matches none of the shapes below.
"""
import hashlib
import re
import subprocess

SHAPES = [
    # (name, regex)
    ("anthropic_api_key", r"(?<![A-Za-z0-9])sk-ant-(?:api|admin|sid)\d{2}-[A-Za-z0-9_-]{20,}"),
    ("openai_project_key", r"(?<![A-Za-z0-9])sk-(?:proj|svcacct|admin)-[A-Za-z0-9_-]{20,}"),
    ("openai_legacy_key", r"(?<![A-Za-z0-9-])sk-[A-Za-z0-9]{32,}"),
    ("github_classic_token", r"(?<![A-Za-z0-9])gh[pousr]_[A-Za-z0-9]{36,}"),
    ("github_fine_grained_pat", r"(?<![A-Za-z0-9])github_pat_[A-Za-z0-9_]{22,}"),
    ("gitlab_token", r"(?<![A-Za-z0-9])gl(?:pat|ptt|rt|dt|oas|soat|cbt|imt|agent)-[A-Za-z0-9_-]{20,}"),
    ("google_api_key", r"(?<![A-Za-z0-9])AIza[0-9A-Za-z_-]{35}"),
    ("google_oauth_access_token", r"(?<![A-Za-z0-9])ya29\.[0-9A-Za-z_-]{20,}"),
    ("gcp_service_account_key", r'"private_key"\s*:\s*"-----BEGIN [A-Z ]*PRIVATE KEY'),
    ("sendgrid_api_key", r"(?<![A-Za-z0-9])SG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}"),
    ("stripe_key", r"(?<![A-Za-z0-9])[sr]k_(?:live|test)_[A-Za-z0-9]{16,}"),
    ("stripe_webhook_secret", r"(?<![A-Za-z0-9])whsec_[A-Za-z0-9]{24,}"),
    ("aws_access_key_id", r"(?<![A-Za-z0-9])(?:AKIA|ASIA|AGPA|AIDA|AROA|ANPA)[0-9A-Z]{16}(?![A-Za-z0-9])"),
    ("aws_secret_access_key", r"(?i)aws_?secret_?access_?key[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9/+=]{40}"),
    ("azure_storage_account_key", r"AccountKey=[A-Za-z0-9+/=]{40,}"),
    ("azure_sas_signature", r"[?&]sig=[A-Za-z0-9%+/=]{30,}"),
    ("slack_token", r"(?<![A-Za-z0-9])xox[baprs]-[A-Za-z0-9-]{10,}"),
    ("twilio_api_key", r"(?<![A-Za-z0-9])SK[0-9a-f]{32}(?![A-Za-z0-9])"),
    ("npm_token", r"(?<![A-Za-z0-9])npm_[A-Za-z0-9]{36}(?![A-Za-z0-9])"),
    ("pypi_token", r"(?<![A-Za-z0-9])pypi-[A-Za-z0-9_-]{50,}"),
    ("huggingface_token", r"(?<![A-Za-z0-9])hf_[A-Za-z0-9]{30,}"),
    ("jwt", r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{5,}"),
    ("private_key_block", r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED |PGP )?PRIVATE KEY"),
    ("bearer_header", r"(?i)\bBearer\s+[A-Za-z0-9+/=_.-]{20,}"),
    ("basic_header", r"(?i)\bBasic\s+[A-Za-z0-9+/=]{20,}"),
    ("slack_webhook_url", r"hooks\.slack\.com/services/T[A-Z0-9]{6,}/B[A-Z0-9]{6,}/[A-Za-z0-9]{16,}"),
    ("telegram_bot_token", r"(?<![A-Za-z0-9])\d{8,10}:[A-Za-z0-9_-]{35}(?![A-Za-z0-9_-])"),
    ("command_line_secret_flag", r"(?i)(?<![A-Za-z0-9-])--(?:password|passwd|pass|token|secret|api-?key|access-?key)(?:\s+|=)['\"]?[^\s'\"-][^\s'\"]{7,}"),
    ("curl_user_password", r"(?<![A-Za-z0-9-])(?:-u|--user)\s+['\"]?[^\s:'\"]{1,64}:[^\s'\"]{4,}"),
    ("url_userinfo", r"://[^/\s:@]{1,64}:[^/\s@]{3,}@"),
]
COMPILED = [(n, re.compile(rx)) for n, rx in SHAPES]

# secret-named assignment, found from the KEYWORD outwards (linear time: a regex with an unbounded name prefix backtracks
# quadratically on a long alphanumeric run). The name is the run of name characters around the keyword (at most
# _NAME_SPAN either side); the value tail must follow the name. Strong names flag an 8+ character value, weak names
# (token/authorization) need 16+.
_NAME_SPAN = 256
_NAMECH = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-")
_KW_STRONG = re.compile(r"(?i)password|passwd|passphrase|pwd|credentials?|secret|api[_-]?key|access[_-]?key|private[_-]?key|auth[_-]?key|(?<=[_.-])pass(?![A-Za-z0-9_.-])")
_KW_WEAK = re.compile(r"(?i)token|authorization")
_KW_QUOTED = re.compile(r"(?i)password|passwd|passphrase|pwd|secret|api[_-]?key|private[_-]?key")
_TAIL_STRONG = re.compile(r"[\"']?\s*(?::=|=>|[:=])\s*[\"']?(?P<v>[^\s\"']{8,})")
_TAIL_WEAK = re.compile(r"[\"']?\s*[:=]\s*[\"']?(?P<v>[A-Za-z0-9+/=_.-]{16,}+)(?!\()")
_TAIL_QUOTED = re.compile(r"[\"']?\s*[:=]\s*(?P<q>[\"'])(?P<v>[^\"'\r\n]{12,200})(?P=q)")


class _Named:
    def __init__(self, whole, n, v):
        self._d = {0: whole, "n": n, "v": v}

    def group(self, k):
        return self._d[k]


def _named(kw, tail, txt, ends_with_keyword=False):
    """Matches of <name containing a keyword><tail> with .group(0) (whole), .group("n") (name), .group("v") (value)."""
    last_hi = -1
    for m in kw.finditer(txt):
        a, b = m.start(), m.end()
        if a < last_hi:                                   # another keyword inside a name already examined
            continue
        lo, hi = a, b
        while lo > 0 and a - lo < _NAME_SPAN and txt[lo - 1] in _NAMECH:
            lo -= 1
        while hi < len(txt) and hi - b < _NAME_SPAN and txt[hi] in _NAMECH:
            hi += 1
        last_hi = hi
        if ends_with_keyword and not any(mm.end() == hi - lo for mm in kw.finditer(txt[lo:hi])):
            continue                                      # e.g. a prose key such as SECRETISH_NOTE is not a secret name
        t = tail.match(txt, hi)
        if t:
            yield _Named(txt[lo:t.end()], txt[lo:hi], t.group("v"))


_HASHY = {"hash", "sha", "sha1", "sha224", "sha256", "sha384", "sha512", "digest", "checksum", "fingerprint"}
_COUNTY = {"count", "len", "length", "id", "ids", "size", "name", "type", "source", "kind", "path", "file"}
_LABEL = re.compile(r"(?:[A-Z]+[0-9]?|[0-9]+)(?:_(?:[A-Z]+[0-9]?|[0-9]+))+")
_ATTR_PATH = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+")      # self.some_attribute (code, not a secret)
_PLACEHOLDER = re.compile(r"(?i)^(changeme|redacted|example|placeholder|password|secret|required|optional|none|null|true|false|x{4,}|\*{3,}|<.*>|\$\{.*|\$\(.*|%.*%|\{\{.*)$")


_FILENAME = re.compile(r"(?i)\.(md|json|py|txt|ps1|zip|yaml|yml)$")        # a key that is itself a file name (pin tables)


def _exempt_name(n):
    if _FILENAME.search(n):
        return True
    seg = [x.lower() for x in re.split(r"[_.\-]+|(?<=[a-z0-9])(?=[A-Z])", n) if x]
    return bool(seg) and (any(x in _HASHY for x in seg) or seg[-1] in _COUNTY)


def _short_secret_like(v):
    if _PLACEHOLDER.match(v) or _LABEL.fullmatch(v):
        return False
    return (any(c.isdigit() for c in v) and any(c.isalpha() for c in v)) or any(c in "!@#$%^&*+=?~" for c in v)


def text_variants(b):
    """Every plausible text reading of the bytes (wide encodings at every byte offset, tolerant decoding)."""
    out = [b.decode("utf-8-sig", errors="replace")]
    for enc, width in (("utf-16-le", 2), ("utf-16-be", 2), ("utf-32-le", 4), ("utf-32-be", 4)):
        for offset in range(width):
            out.append(b[offset:].decode(enc, errors="ignore"))
    out.append(b.decode("latin-1"))
    return out


def _fp(s):
    return hashlib.sha256(s.encode("utf-8", "replace")).hexdigest()[:8]


def scan_text(txt):
    """Findings as (shape name, fingerprint) tuples; the matched text itself is never returned."""
    hits = []
    for name, rx in COMPILED:
        for m in rx.finditer(txt):
            hits.append((name, _fp(m.group(0))))
    for m in _named(_KW_STRONG, _TAIL_STRONG, txt):
        v = m.group("v").rstrip("),;]}")                 # trailing code punctuation is not part of a value
        if len(v) < 8 or _exempt_name(m.group("n")) or _PLACEHOLDER.match(v) or _LABEL.fullmatch(v) or _ATTR_PATH.fullmatch(v):
            continue
        # a value of 16 or more characters under a strong secret name is flagged whatever it looks like (found by the A13b/A13c
        # attacks: letters-only values slipped through); 8 to 15 characters need a digit with a letter, or a symbol
        if len(v) >= 16 or _short_secret_like(v):
            hits.append(("secret_named_assignment", _fp(m.group(0))))
    for m in _named(_KW_QUOTED, _TAIL_QUOTED, txt, ends_with_keyword=True):
        v = m.group("v")
        if not (_exempt_name(m.group("n")) or _PLACEHOLDER.match(v) or _ATTR_PATH.fullmatch(v) or _LABEL.fullmatch(v)):
            hits.append(("secret_named_assignment", _fp(m.group(0))))
    for m in _named(_KW_WEAK, _TAIL_WEAK, txt):
        v = m.group("v")
        if not (_exempt_name(m.group("n")) or _LABEL.fullmatch(v) or _PLACEHOLDER.match(v) or v == m.group("n") or _ATTR_PATH.fullmatch(v)):
            hits.append(("token_named_assignment", _fp(m.group(0))))
    return hits


def scan_bytes(b):
    seen, out = set(), []
    for v in text_variants(b):
        for h in scan_text(v):
            if h not in seen:
                seen.add(h)
                out.append(h)
    return out


MAX_SCAN = 8 * 1024 * 1024
MAX_ZIP_TOTAL = 64 * 1024 * 1024


class ScanError(RuntimeError):
    """The scan could not be performed (not a Git repository, git missing or failing). A scan that did not run is never a pass."""


def _git(root, *args, **kw):
    try:
        r = subprocess.run(["git"] + list(args), cwd=root, capture_output=True, **kw)
    except OSError as exc:
        raise ScanError("git could not be run in %r: %s" % (root, type(exc).__name__)) from exc
    if r.returncode != 0:
        raise ScanError("git %s failed in %r (not a Git repository?)" % (args[0], root))
    return r


def _require_toplevel(root):
    """root must be the top of a Git work tree itself (a sub-folder, or a folder that merely sits inside some other
    repository, would be scanned as if it were the whole project)."""
    import os
    top = _git(root, "rev-parse", "--show-toplevel", text=True).stdout.strip()
    if os.path.normcase(os.path.realpath(top)) != os.path.normcase(os.path.realpath(root)):
        raise ScanError("%r is not the top of a Git repository" % (root,))


def scan_blob(label, data):
    """Scan one object's bytes whatever its file name (a text file named .png is still text). A ZIP (by content) is
    opened and its members scanned; content beyond MAX_SCAN is reported ('unscanned_oversize'), never silently skipped.
    Returns [(label, shape, fingerprint)]."""
    import io
    import zipfile
    if len(data) > MAX_SCAN and not data.startswith(b"PK\x03\x04"):
        return [(label, "unscanned_oversize", "%08x" % (len(data) & 0xFFFFFFFF))]
    if data.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                infos = z.infolist()
                if sum(i.file_size for i in infos) > MAX_ZIP_TOTAL:
                    return [(label, "unscanned_oversize", "zip")]
                out = []
                for i in infos:
                    if i.is_dir():
                        continue
                    member = z.read(i)
                    if len(member) > MAX_SCAN:
                        out.append((label + "!" + i.filename, "unscanned_oversize", "%08x" % (len(member) & 0xFFFFFFFF)))
                    else:
                        out += [(label + "!" + i.filename, n, f) for n, f in scan_bytes(member)]
                return out
        except (zipfile.BadZipFile, NotImplementedError, RuntimeError, OSError):
            pass                                                       # not a readable ZIP: scan the raw bytes
    return [(label, n, f) for n, f in scan_bytes(data)]


def scan_tracked_tree(root):
    """Scan every tracked file (and ZIP members) whatever its extension. Returns [(path, shape, fingerprint)].
    Raises ScanError if the folder is not a Git repository: a scan that did not run is not a clean scan."""
    import os
    _require_toplevel(root)
    tr = _git(root, "ls-files", "-z")
    names = [x.decode("utf-8", "replace") for x in tr.stdout.split(b"\0") if x]
    found = []
    for p in names:
        fp = os.path.join(root, p)
        if not os.path.isfile(fp):
            continue
        try:
            with open(fp, "rb") as fh:
                data = fh.read(MAX_SCAN + 1) if not p.lower().endswith(".zip") else fh.read()
        except OSError:
            continue
        found += scan_blob(p, data)
    return found


def scan_history(root):
    """Scan every distinct blob, commit message and tag message reachable from any ref (all of Git history, including
    deleted files). Returns [(oid, path, shape, fingerprint)] (never the matched text). Unreachable objects and anything
    outside Git are not scanned. Raises ScanError if the folder is not a usable Git repository."""
    import os
    import tempfile
    _require_toplevel(root)
    r = _git(root, "rev-list", "--objects", "--all", text=True)
    paths = {}
    for line in r.stdout.split("\n"):
        if line:
            oid, _, name = line.partition(" ")
            paths.setdefault(oid, name)
    fd, lst = tempfile.mkstemp(prefix="m3hist_")
    try:
        with os.fdopen(fd, "w", newline="\n") as fh:
            fh.write("\n".join(paths) + "\n")
        with open(lst, "rb") as fin:
            try:
                c = subprocess.run(["git", "cat-file", "--batch"], cwd=root, stdin=fin, capture_output=True)
            except OSError as exc:
                raise ScanError("git cat-file could not be run") from exc
    finally:
        os.remove(lst)
    if c.returncode != 0:
        raise ScanError("git cat-file failed")
    data, pos, found = c.stdout, 0, []
    while pos < len(data):
        nl = data.find(b"\n", pos)
        if nl < 0:
            break
        head = data[pos:nl].split()
        if len(head) != 3:                                   # "<oid> missing"
            pos = nl + 1
            continue
        oid, typ, size = head[0].decode(), head[1], int(head[2])
        body = data[nl + 1:nl + 1 + size]
        pos = nl + 1 + size + 1
        if typ in (b"blob", b"commit", b"tag"):
            label = paths.get(oid, "") if typ == b"blob" else "<%s message>" % typ.decode()
            found += [(oid, lab, n, f) for lab, n, f in scan_blob(label, body)]
    return found


# ---------------------------------------------------------------- synthetic fixtures (assembled at run time)
def _a(n, ch="A"):
    return ch * n


def fixture(name):
    """A synthetic example of the shape, built from fragments. It is NOT a real credential."""
    f = {
        "anthropic_api_key": lambda: "sk" + "-ant-" + "api03-" + _a(40, "x"),
        "openai_project_key": lambda: "sk" + "-proj-" + _a(40, "x"),
        "openai_legacy_key": lambda: "sk" + "-" + _a(40),
        "github_classic_token": lambda: "gh" + "p_" + _a(36),
        "github_fine_grained_pat": lambda: "github" + "_pat_" + _a(30),
        "gitlab_token": lambda: "gl" + "pat-" + _a(24),
        "google_api_key": lambda: "AI" + "za" + _a(35),
        "google_oauth_access_token": lambda: "ya" + "29." + _a(30),
        "gcp_service_account_key": lambda: '"private' + '_key": "-----BEGIN ' + 'PRIVATE KEY-----"',
        "sendgrid_api_key": lambda: "SG" + "." + _a(22) + "." + _a(43),
        "stripe_key": lambda: "sk" + "_live_" + _a(24),
        "stripe_webhook_secret": lambda: "whsec" + "_" + _a(32),
        "aws_access_key_id": lambda: "AK" + "IA" + "ABCDEFGHIJKLMNOP",
        "aws_secret_access_key": lambda: "aws_secret" + "_access_key = " + _a(40, "a"),
        "azure_storage_account_key": lambda: "Account" + "Key=" + _a(44) + "==",
        "azure_sas_signature": lambda: "?sv=2020&" + "sig=" + _a(40),
        "slack_token": lambda: "xo" + "xb-" + "1234567890-abcdefghij",
        "twilio_api_key": lambda: "S" + "K" + "0123456789abcdef" * 2,
        "npm_token": lambda: "np" + "m_" + _a(36),
        "pypi_token": lambda: "py" + "pi-" + _a(60),
        "huggingface_token": lambda: "h" + "f_" + _a(34),
        "jwt": lambda: ".".join(["ey" + "J" + _a(20), _a(20), _a(10)]),
        "private_key_block": lambda: "-----BEGIN " + "RSA PRIVATE " + "KEY-----",
        "bearer_header": lambda: "Bear" + "er " + _a(30),
        "basic_header": lambda: "Bas" + "ic " + _a(30),
        "url_userinfo": lambda: "https://user:" + "hunter22" + "@example.org/x",
        "slack_webhook_url": lambda: "hooks.slack" + ".com/services/T" + "ABCDEFGH" + "/B" + "ABCDEFGH" + "/" + _a(24, "x"),
        "telegram_bot_token": lambda: "1234567" + "890:" + _a(35, "x"),
        "command_line_secret_flag": lambda: "--pass" + "word " + "hunter2hunter2",
        "curl_user_password": lambda: "curl " + "-u " + "admin:" + "hunter22",
        "secret_named_assignment": lambda: "pass" + "word = " + "p@ss!w0rd",
        "token_named_assignment": lambda: "to" + "ken: " + _a(24, "q"),
    }
    return f[name]()


def fixture_names():
    return [n for n, _ in SHAPES] + ["secret_named_assignment", "token_named_assignment"]
