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
    ("basic_header", r"\bBasic\s+[A-Za-z0-9+/=]{20,}"),
    ("url_userinfo", r"://[^/\s:@]{1,64}:[^/\s@]{3,}@"),
]
COMPILED = [(n, re.compile(rx)) for n, rx in SHAPES]

# secret-named assignment: strong names flag a 8+ character value, weak names (token/authorization) need 16+
_STRONG = re.compile(r"(?P<n>[A-Za-z0-9_.-]*(?i:password|passwd|passphrase|pwd|credentials?|secret|api[_-]?key|access[_-]?key|private[_-]?key)[A-Za-z0-9_.-]*)[\"']?\s*(?::=|=>|[:=])\s*[\"']?(?P<v>[^\s\"']{8,})")
_WEAK = re.compile(r"(?P<n>[A-Za-z0-9_.-]*(?i:token|authorization)[A-Za-z0-9_.-]*)[\"']?\s*[:=]\s*[\"']?(?P<v>[A-Za-z0-9+/=_.-]{16,}+)(?!\()")
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
    for m in _STRONG.finditer(txt):
        v = m.group("v").rstrip("),;]}")                 # trailing code punctuation is not part of a value
        if len(v) < 8 or _exempt_name(m.group("n")) or _PLACEHOLDER.match(v) or _LABEL.fullmatch(v) or _ATTR_PATH.fullmatch(v):
            continue
        # a value of 16 or more characters under a strong secret name is flagged whatever it looks like (found by the A13b/A13c
        # attacks: letters-only values slipped through); 8 to 15 characters need a digit with a letter, or a symbol
        if len(v) >= 16 or _short_secret_like(v):
            hits.append(("secret_named_assignment", _fp(m.group(0))))
    for m in _WEAK.finditer(txt):
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


BINARY_EXT = (".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".woff", ".woff2", ".ttf", ".pyc", ".pyo")
MAX_SCAN = 8 * 1024 * 1024


def scan_tracked_tree(root):
    """Scan every tracked file and the text members of zip archives. Returns [(path, shape, fingerprint)]."""
    import zipfile
    try:
        tr = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True)
    except OSError:                                    # missing folder or no git: nothing to scan
        return []
    names = [x for x in tr.stdout.split("\n") if x] if tr.returncode == 0 else []
    found = []
    import os
    for p in names:
        fp = os.path.join(root, p)
        if not os.path.isfile(fp) or p.lower().endswith(BINARY_EXT):
            continue
        try:
            if p.lower().endswith(".zip"):
                with zipfile.ZipFile(fp) as z:
                    for mem in z.namelist():
                        if mem.lower().endswith(BINARY_EXT) or mem.endswith("/"):
                            continue
                        data = z.read(mem)[:MAX_SCAN]
                        found += [(p + "!" + mem, n, f) for n, f in scan_bytes(data)]
                continue
            data = open(fp, "rb").read(MAX_SCAN)
        except (OSError, zipfile.BadZipFile):
            continue
        found += [(p, n, f) for n, f in scan_bytes(data)]
    return found


def scan_history(root):
    """Scan every distinct blob reachable from any ref (all of Git history, including deleted files).
    Returns [(oid, path, shape, fingerprint)] (never the matched text). A blob removed from the tree but still
    reachable from history IS scanned. Unreachable objects and anything outside Git are not."""
    import os
    import tempfile
    try:
        r = subprocess.run(["git", "rev-list", "--objects", "--all"], cwd=root, capture_output=True, text=True)
    except OSError:
        return []
    if r.returncode != 0:
        return []
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
            c = subprocess.run(["git", "cat-file", "--batch"], cwd=root, stdin=fin, capture_output=True)
    finally:
        os.remove(lst)
    if c.returncode != 0:
        return []
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
        name = paths.get(oid, "")
        if typ == b"blob" and not name.lower().endswith(BINARY_EXT):
            found += [(oid, name, n, f) for n, f in scan_bytes(body[:MAX_SCAN])]
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
        "secret_named_assignment": lambda: "pass" + "word = " + "p@ss!w0rd",
        "token_named_assignment": lambda: "to" + "ken: " + _a(24, "q"),
    }
    return f[name]()


def fixture_names():
    return [n for n, _ in SHAPES] + ["secret_named_assignment", "token_named_assignment"]
