"""R2.0B read-only readback qualification probe for the SAP ADT MCP provider.

READ-ONLY BY CONSTRUCTION: only the methods/tools in ALLOWED are ever sent; anything else raises
before any network I/O. abap_atc_run starts an ATC analysis (server-side worklist, no repository
object change; R1.8 taxonomy READ_OR_ANALYSIS_CAPABLE) and therefore needs --confirm-analysis-run.

Controls: a positive control (an existing object whose ATC observation is documented in R1.7) and a
negative control (a fresh never-created name). The probe records raw responses OUTSIDE Git (--evidence-dir)
and emits an auto-classification that is only a proposal: ADJUDICATION_REQUIRED is always true.

Modes: --mock (spawns an in-process localhost mock, for tests) or --auth-context PATH (DPAPI, Windows).
Never prints or stores the bearer token.
"""
import argparse
import base64
import hashlib
import http.server
import json
import os
import re
import secrets
import sys
import threading
import time
import urllib.request

ALLOWED_METHODS = {"initialize", "notifications/initialized", "tools/list"}
ALLOWED_TOOLS = {"abap_list_destinations", "abap_atc_run", "abap_atc_get_result"}
EXPECTED_ADT_TOOL_COUNT = 20      # R1.8 retained contract (SAP_ADT_MCP, 20 tools)
KEYS = {"name": "name", "objectname": "name", "type": "type", "objecttype": "type", "package": "package",
        "packagename": "package", "findings": "findings", "worklistid": "worklistId"}
NOT_FOUND = re.compile(r"not found|does not exist|no such|unknown object|nicht gefunden|not exist", re.I)


class ReadOnlyViolation(Exception):
    pass


def guard(method, tool=None):
    if method == "tools/call":
        if tool not in ALLOWED_TOOLS:
            raise ReadOnlyViolation("tool %r is not on the read-only allowlist" % tool)
    elif method not in ALLOWED_METHODS:
        raise ReadOnlyViolation("method %r is not on the read-only allowlist" % method)


def sha(b):
    return hashlib.sha256(b if isinstance(b, bytes) else b.encode()).hexdigest().upper()


def dpapi_token(ctx_path):
    """Unprotect protected_token_b64 (Windows DPAPI, current user). The token is never printed."""
    import ctypes
    from ctypes import wintypes
    ctx = json.load(open(ctx_path, encoding="utf-8-sig"))
    if ctx.get("protection") != "WINDOWS_DPAPI_CURRENT_USER":
        raise SystemExit("PROTECTION_MISMATCH")
    raw = base64.b64decode(ctx["protected_token_b64"])

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]
    buf = ctypes.create_string_buffer(raw, len(raw))
    src, dst = Blob(len(raw), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), Blob()
    if not ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(src), None, None, None, None, 0, ctypes.byref(dst)):
        raise SystemExit("DPAPI_UNPROTECT_FAILED")
    tok = ctypes.string_at(dst.pbData, dst.cbData).decode("utf-8")
    ctypes.windll.kernel32.LocalFree(dst.pbData)
    return ctx["endpoint"], tok


class Client:
    def __init__(self, endpoint, token, evdir, timeout=45):
        self.endpoint, self.token, self.evdir, self.timeout = endpoint, token, evdir, timeout
        self.session, self.n, self.log = None, 0, []

    def call(self, method, params=None, tool=None, notify=False):
        guard(method, tool)                                  # BEFORE any I/O
        self.n += 1
        body = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        if not notify:
            body["id"] = self.n
        hdr = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.token:
            hdr["Authorization"] = "Bearer " + self.token
        if self.session:
            hdr["Mcp-Session-Id"] = self.session
        data = json.dumps(body).encode()
        t0 = time.perf_counter_ns()
        try:
            with urllib.request.urlopen(urllib.request.Request(self.endpoint, data, hdr), timeout=self.timeout) as r:
                raw, status = r.read().decode("utf-8", "replace"), r.status
                self.session = r.headers.get("Mcp-Session-Id") or self.session
        except Exception as e:                                 # transport failure: outcome unknown to caller
            raw, status = "TRANSPORT_ERROR:" + type(e).__name__, 0
        dt = time.perf_counter_ns() - t0
        label = "%02d_%s%s" % (self.n, method.replace("/", "_"), "_" + tool if tool else "")
        if self.evdir:
            open(os.path.join(self.evdir, label + ".raw.txt"), "w", encoding="utf-8", newline="\n").write(raw)
        self.log.append({"label": label, "status": status, "sha256": sha(raw), "bytes": len(raw), "ns": dt})
        return status, raw

    def tool(self, name, args):
        return parse(self.call("tools/call", {"name": name, "arguments": args}, tool=name)[1])


def parse(raw):
    """Extract the JSON-RPC object from plain JSON or an SSE 'data:' frame."""
    for line in raw.splitlines():
        if line.startswith("data:"):
            raw = line[5:].strip()
            break
    try:
        return json.loads(raw)
    except Exception:
        return {"unparseable": raw[:200]}


def collect(o, out=None):
    out = out if out is not None else {}
    if isinstance(o, dict):
        for k, v in o.items():
            kk = KEYS.get(k.lower())
            if kk and not isinstance(v, (dict,)):
                out.setdefault(kk, []).append(v)
            collect(v, out)
    elif isinstance(o, list):
        for x in o:
            collect(x, out)
    elif isinstance(o, str) and o[:1] in "{[":
        try:
            collect(json.loads(o), out)
        except Exception:
            pass
    return out


def text_of(resp):
    res = resp.get("result", {})
    return " ".join(c.get("text", "") for c in res.get("content", []) if isinstance(c, dict)), bool(res.get("isError"))


def atc_observe(c, dest, name, otype, polls=6, gap=5):
    r = c.tool("abap_atc_run", {"destination": dest, "objects": [{"name": name, "type": otype}]})
    txt, err = text_of(r)
    wl = (collect(r).get("worklistId") or [None])[0]
    out = {"run_is_error": err, "run_text_sha256": sha(txt), "worklistId_present": bool(wl)}
    if err or not wl:
        out["run_error_text"] = txt[:300]
        out["signal"] = "ABSENT_SIGNAL" if err and NOT_FOUND.search(txt) else "UNKNOWN"
        return out
    for _ in range(polls):
        g = c.tool("abap_atc_get_result", {"destination": dest, "worklistId": wl})
        gt, gerr = text_of(g)
        if gerr or "running" not in gt.lower():
            break
        time.sleep(gap)
    f = collect(g)
    out.update(get_is_error=gerr, get_text_sha256=sha(gt), fields={k: v[:3] for k, v in f.items()},
               name_in_result=name.upper() in gt.upper())
    if gerr:
        out["signal"] = "ABSENT_SIGNAL" if NOT_FOUND.search(gt) else "UNKNOWN"
    elif out["name_in_result"]:
        out["signal"] = "EXISTS_SIGNAL"
    else:
        out["signal"] = "UNKNOWN"          # silence is never ABSENT
    return out


def run(c, dest, pos, neg, otype):
    rep = {"read_only_allowlist": sorted(ALLOWED_TOOLS | ALLOWED_METHODS), "provider_calls": 0}
    st, raw = c.call("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "MCR_R2_0_B", "version": "1"}})
    rep["initialize_ok"] = st == 200 and "result" in parse(raw)
    if not rep["initialize_ok"]:
        rep["verdict_proposal"] = "NOT_ESTABLISHED_PROVIDER_UNREACHABLE"
        return rep
    c.call("notifications/initialized", notify=True)
    tl = parse(c.call("tools/list")[1]).get("result", {}).get("tools", [])
    rep["tool_count"] = len(tl)
    rep["tool_names"] = sorted(t["name"] for t in tl)
    rep["tool_fingerprints"] = {t["name"]: sha(json.dumps({"n": t["name"], "s": t.get("inputSchema")}, sort_keys=True)) for t in tl}
    rep["tool_count_matches_r1_8"] = len(tl) == EXPECTED_ADT_TOOL_COUNT
    rep["has_dedicated_object_read_tool"] = any(re.search(r"get_(object|source)|read_(object|source)|search", t["name"]) for t in tl)
    dtxt, derr = text_of(c.tool("abap_list_destinations", {}))
    rep["destination_listed"] = (not derr) and dest in dtxt
    rep["positive_control"] = atc_observe(c, dest, pos, otype)
    rep["negative_control"] = atc_observe(c, dest, neg, otype)
    p, n = rep["positive_control"]["signal"], rep["negative_control"]["signal"]
    if p == "EXISTS_SIGNAL" and n == "ABSENT_SIGNAL":
        rep["verdict_proposal"] = "EXISTENCE_DISCRIMINATING_VIA_ATC_PARTIAL"   # still no activation/source readback
    elif p == "EXISTS_SIGNAL":
        rep["verdict_proposal"] = "EXISTS_ONLY_ABSENT_INDISTINGUISHABLE_FROM_UNKNOWN"
    else:
        rep["verdict_proposal"] = "NOT_ESTABLISHED"
    rep["activation_readback"] = "NOT_ESTABLISHED" if not rep["has_dedicated_object_read_tool"] else "UNTESTED"
    rep["source_hash_readback"] = "NOT_ESTABLISHED" if not rep["has_dedicated_object_read_tool"] else "UNTESTED"
    rep["provider_calls"] = len(c.log)
    rep["ADJUDICATION_REQUIRED"] = True
    return rep


# ------------------------------------------------------------------ in-process mock (tests only)
def mock_server(known):
    class H(http.server.BaseHTTPRequestHandler):
        wl = {}

        def log_message(self, *a):
            pass

        def do_POST(self):
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            m, p, i = req["method"], req.get("params", {}), req.get("id")
            if "id" not in req:
                self.send_response(202); self.end_headers(); return
            if m == "initialize":
                res = {"protocolVersion": "2025-06-18"}
            elif m == "tools/list":
                names = ["abap_list_destinations", "abap_atc_run", "abap_atc_get_result", "abap_creation-create_object", "abap_activate_objects"] + ["t%d" % k for k in range(15)]
                res = {"tools": [{"name": n, "inputSchema": {}} for n in names]}
            else:
                a = p["arguments"]
                if p["name"] == "abap_list_destinations":
                    res = {"content": [{"type": "text", "text": "TRL_EN"}], "isError": False}
                elif p["name"] == "abap_atc_run":
                    nm = a["objects"][0]["name"]
                    if nm in known:
                        H.wl["W1"] = nm; res = {"content": [{"type": "text", "text": json.dumps({"worklistId": "W1"})}], "isError": False}
                    else:
                        res = {"content": [{"type": "text", "text": "Object %s does not exist" % nm}], "isError": True}
                else:
                    res = {"content": [{"type": "text", "text": json.dumps({"objects": [{"name": H.wl["W1"], "type": "CLAS", "packageName": "ZCLINE", "findings": []}]})}], "isError": False}
            out = ("id: x\nevent: message\ndata: " + json.dumps({"jsonrpc": "2.0", "id": i, "result": res}) + "\n\n").encode()
            self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.send_header("Content-Length", str(len(out)))
            self.send_header("Mcp-Session-Id", "S1"); self.end_headers(); self.wfile.write(out)
    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--auth-context")
    ap.add_argument("--confirm-analysis-run", action="store_true")
    ap.add_argument("--destination", default="TRL_EN")
    ap.add_argument("--positive-control", default="ZCL_MCR_P6D_DFC3F677")
    ap.add_argument("--object-type", default="CLAS")
    ap.add_argument("--evidence-dir", help="outside-Git directory for raw responses")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    if not a.confirm_analysis_run:
        raise SystemExit("refusing: pass --confirm-analysis-run (abap_atc_run starts a server-side ATC analysis)")
    if a.evidence_dir:
        os.makedirs(a.evidence_dir, exist_ok=True)
    neg = "ZCL_MCR20B_NEG_" + secrets.token_hex(4).upper()
    if a.mock:
        srv = mock_server({a.positive_control})
        c = Client("http://127.0.0.1:%d/mcp" % srv.server_address[1], None, a.evidence_dir, timeout=5)
    else:
        if not a.auth_context or not os.path.exists(a.auth_context):
            raise SystemExit("BLOCKER_B: auth context not available")
        ep, tok = dpapi_token(a.auth_context)
        if not ep.startswith("http://127.0.0.1:"):
            raise SystemExit("endpoint must be loopback")
        c = Client(ep, tok, a.evidence_dir)
    rep = run(c, a.destination, a.positive_control, neg, a.object_type)
    rep.update(mode="MOCK" if a.mock else "LIVE_READ_ONLY", negative_control_name=neg, sap_writes=0,
               call_log=[{k: v for k, v in e.items() if k != "ns"} for e in c.log])
    out = json.dumps(rep, indent=2, sort_keys=True)
    if a.out:
        open(a.out, "w", newline="\n").write(out + "\n")
    print(out)


if __name__ == "__main__":
    main()
