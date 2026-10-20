"""R2.0C frozen live outcome study: one disposable CDS data definition (DDLS/DF) on TRL_EN.

Modes
  --build-freeze          write research-package/r2.0/r2_0c/R2_0C_FREEZE_R1.json (deterministic objects + hashes)
  --mock SCENARIO         run the full runner against an in-process mock provider (SYNTHETIC)
  --prewrite-live         READ-ONLY live prewrite validation (fingerprint, baseline ABSENT); no mutation
  --execute --authorization PHRASE   LIVE: exactly one abap_creation-create_object call, then authoritative readback

Hard limits: max 1 mutation, 0 retries, no activation, no compensation, no cleanup. A single-use lock file is
created (O_EXCL) BEFORE the call is sent; if it exists the runner refuses. Raw responses stay outside Git.
"""
import argparse
import hashlib
import json
import os
import sys
import threading
import time
import http.server

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r2_0b_readonly_readback_probe as probe  # noqa: E402  (client, DPAPI, parse helpers)
from mcr_r2_model import GuardError, Mission, chash, eval_predicates, make  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
FREEZE_PATH = os.path.join(ROOT, "research-package", "r2.0", "r2_0c", "R2_0C_FREEZE_R1.json")
DEST, PACKAGE, OBJ_TYPE = "TRL_EN", "ZCLINE", "DDLS/DF"
OBJ_NAME = "ZC_MCR20C_7A3F91D2"                     # fresh identity; never used before this freeze
DESCRIPTION = "MCR R2.0C disposable outcome study"
CREATE_TOOL, READ_TOOL = "abap_creation-create_object", "capella_adt_repository_read_metadata"
CREATE_FINGERPRINT = "CB99759628F2258BFB8E13082ED4675E6B6A8F4A348C0BF30D259D2CFA1A0271"  # name+inputSchema, R2.0B run1
MISSION_ID, TX_ID, MUT_ID = "MCR_R2_0_C_LIVE_OUTCOME_STUDY_R1", "R2_0C_TX_CREATE_DDLS_1", "R2_0C_MUT_CREATE_1"
EXPECTED_TOOL_COUNT = 29
LOCK_DIR = r"D:\MCR\r2.0-evidence\r2_0c"
PREDICATES = [{"field": "exists", "op": "eq", "expected": True},
              {"field": "object_type", "op": "eq", "expected": "DDLS"},
              {"field": "source_hash_integrity", "op": "eq", "expected": True},
              {"field": "source_contains_object_name", "op": "eq", "expected": True}]


def object_content():
    return json.dumps({"description": DESCRIPTION, "name": OBJ_NAME, "packageName": PACKAGE}, sort_keys=True, separators=(",", ":"))


def build_freeze():
    f = {}
    f["intent"] = make("MissionIntent", mission_id=MISSION_ID, objective="create one disposable DDLS and establish its resulting state by authoritative readback",
                       target_system=DEST, expected_outcome_hash="PENDING")
    f["principal"] = make("PrincipalContext", principal_id="OWNER_DELEGATED_SINGLE_RUN", tenant=DEST, roles=["ABAP_DEVELOPER"])
    f["delegation"] = make("DelegationEnvelope", delegation_id="R2_0C_DELEGATION", principal_hash=f["principal"]["object_hash"],
                           scope=[CREATE_TOOL], max_mutations=1, expires_at="SINGLE_RUN")
    f["authority"] = make("ExecutionAuthority", authority_id="R2_0C_AUTHORITY", delegation_hash=f["delegation"]["object_hash"],
                          mission_id=MISSION_ID, scope=[CREATE_TOOL], max_mutations=1, single_use=True)
    f["budget"] = make("MutationBudget", budget_id="R2_0C_BUDGET", authority_hash=f["authority"]["object_hash"], max_mutations=1,
                       retries=0, expansion_allowed=False)
    f["capability"] = make("CapabilityBinding", binding_id="R2_0C_CAP", authority_hash=f["authority"]["object_hash"],
                           capability=CREATE_TOOL, provider_ref="SAP_ADT_MCP::" + CREATE_TOOL)
    f["provider"] = make("ProviderBinding", provider_id="SAP_ADT_MCP", tool_name=CREATE_TOOL, contract_fingerprint=CREATE_FINGERPRINT,
                         identity="SAP_ADT_MCP::" + CREATE_TOOL)
    f["tx"] = make("TransactionEnvelope", transaction_id=TX_ID, mission_id=MISSION_ID, mutation_ids=[MUT_ID], boundary="single-object create, inactive state; no activation")
    f["outcome_contract"] = make("ExpectedOutcomeContract", outcome_contract_id="R2_0C_OUTCOME", mission_id=MISSION_ID, transaction_id=TX_ID,
                                 predicates=PREDICATES, frozen=True)
    f["readback_contract"] = make("AuthoritativeReadbackContract", contract_id="R2_0C_READBACK", source_level_required="AUTHORITATIVE_REPOSITORY",
                                  provider_ref="SAP_ADT_MCP::" + READ_TOOL,
                                  checks=["DDLS endpoint, status 200, found=true -> EXISTS", "DDLS endpoint, status 404, ExceptionResourceNotFound -> ABSENT",
                                          "anything else (isError, transport, other status/type) -> UNKNOWN", "sourceHash recomputed locally from source",
                                          "observation-only: active/inactive version, package (not readable)"])
    f["checkpoint"] = make("PreMutationCheckpoint", checkpoint_id="R2_0C_PREWRITE", transaction_hash=f["tx"]["object_hash"],
                           budget_hash=f["budget"]["object_hash"], outcome_contract_hash=f["outcome_contract"]["object_hash"],
                           readback_contract_hash=f["readback_contract"]["object_hash"], remaining_budget=1)
    return f


def freeze_doc():
    objs = build_freeze()
    body = {"mission": MISSION_ID, "destination": DEST, "package": PACKAGE, "object_name": OBJ_NAME, "object_type": OBJ_TYPE,
            "create_arguments": {"destination": DEST, "objectType": OBJ_TYPE, "objectContent": object_content(), "transportRequestNumber": ""},
            "max_mutations": 1, "retries": 0, "activation": "NOT_PERFORMED", "compensation": "NOT_AUTHORIZED", "cleanup": "NOT_AUTHORIZED",
            "expected_tool_count": EXPECTED_TOOL_COUNT, "objects": objs}
    return dict(body, freeze_sha256=chash(body))


def self_sha():
    return hashlib.sha256(open(os.path.abspath(__file__), "rb").read().replace(b"\r\n", b"\n")).hexdigest().upper()


def auth_phrase(freeze_hash):
    return "AUTHORIZE_R2_0C:%s:%s" % (freeze_hash[:16], self_sha()[:16])


# ------------------------------------------------------------------ authoritative readback
def classify_read(txt, is_err, name, want_status_none=False):
    """Return (existence, observed, detail). Only a DDLS-endpoint 200/found or 404/ResourceNotFound is decisive."""
    if is_err:
        return "UNKNOWN", {}, "isError"
    try:
        d = json.loads(txt)
    except Exception:
        return "UNKNOWN", {}, "unparseable"
    src = d.get("source") or ""
    if d.get("found") is True and d.get("status") == 200 and d.get("sourceType") == "DDLS":
        local = hashlib.sha256(src.encode("utf-8")).hexdigest().upper()
        return "EXISTS", {"exists": True, "object_type": "DDLS", "source_hash_integrity": local == d.get("sourceHash"),
                          "source_contains_object_name": name.upper() in src.upper(), "local_source_sha256": local}, "DDLS 200"
    if d.get("found") is False and d.get("status") == 404 and d.get("sourceType") == "NOT_FOUND_VIA_DDLS_ENDPOINT" \
            and "ExceptionResourceNotFound" in src:
        return "ABSENT", {"exists": False}, "DDLS 404 ResourceNotFound"
    return "UNKNOWN", {}, "other status/type"


def read_state(c, name):
    """Authoritative readback over both versions. EXISTS if either version found; ABSENT only if both ABSENT."""
    res = {}
    for ver in ("inactive", "active"):
        r = c.tool(READ_TOOL, {"destination": DEST, "objectName": name, "version": ver})
        txt, err = probe.text_of(r)
        res[ver] = classify_read(txt, err, name)
    ex = {v: res[v][0] for v in res}
    if "EXISTS" in ex.values():
        base = next(res[v][1] for v in ("inactive", "active") if res[v][0] == "EXISTS")
        existence, observed = "EXISTS", dict(base)
    elif all(x == "ABSENT" for x in ex.values()):
        existence, observed = "ABSENT", {"exists": False}
    else:
        existence, observed = "UNKNOWN", {}
    observed["observation_only"] = {"inactive_read": ex["inactive"], "active_read": ex["active"]}
    return existence, observed


def readback_receipt(f, existence, observed, label):
    activation = "UNKNOWN"      # activation state not claimed: version-discrimination unproven (R2.0B)
    return make("AuthoritativeReadbackReceipt", receipt_id="R2_0C_RB_" + label, transaction_id=TX_ID, mutation_id=MUT_ID,
                contract_hash=f["readback_contract"]["object_hash"], source_level="AUTHORITATIVE_REPOSITORY" if existence != "UNKNOWN" else "INFERRED_OR_REGEX",
                existence=existence, activation=activation, observed=observed)


# ------------------------------------------------------------------ prewrite (read-only)
def prewrite_checks(c, f):
    c.call("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": MISSION_ID, "version": "1"}})
    c.call("notifications/initialized", notify=True)
    tl = probe.parse(c.call("tools/list")[1]).get("result", {}).get("tools", [])
    fps = {t["name"]: probe.sha(json.dumps({"n": t["name"], "s": t.get("inputSchema")}, sort_keys=True)) for t in tl}
    dest_txt, derr = probe.text_of(c.tool("abap_list_destinations", {}))
    ex, obs = read_state(c, OBJ_NAME)
    return {"tool_count": len(tl), "tool_count_ok": len(tl) == EXPECTED_TOOL_COUNT, "create_fingerprint_now": fps.get(CREATE_TOOL),
            "create_fingerprint_ok": fps.get(CREATE_TOOL) == CREATE_FINGERPRINT, "read_tool_present": READ_TOOL in fps,
            "destination_listed": (not derr) and DEST in dest_txt, "baseline_existence": ex, "baseline_observation_only": obs["observation_only"],
            "PREWRITE_OK": len(tl) == EXPECTED_TOOL_COUNT and fps.get(CREATE_TOOL) == CREATE_FINGERPRINT and READ_TOOL in fps
                           and ((not derr) and DEST in dest_txt) and ex == "ABSENT"}, fps


# ------------------------------------------------------------------ the mission
def run_mission(c, doc, lock_dir, live):
    f = doc["objects"]
    m = Mission(MISSION_ID, TX_ID, 1)
    tel = {"governance_ns": 0, "provider_ns": 0}
    out = {"live": live, "events": []}

    def gov(fn, *a):
        t = time.perf_counter_ns(); r = fn(*a); tel["governance_ns"] += time.perf_counter_ns() - t; return r
    gov(m.context_ready, f["intent"], f["principal"])
    gov(m.authorize, f["delegation"], f["authority"], f["budget"])
    gov(m.bind, f["capability"], f["provider"])
    gov(m.prewrite_validate, f["tx"], f["outcome_contract"], f["readback_contract"], f["checkpoint"])
    pre, fps = prewrite_checks(c, f)
    out["prewrite"] = pre
    if not pre["PREWRITE_OK"]:
        gov(m.fail_before_mutation)
        out.update(final_state=m.state, RESULT="NOT_EXECUTED_PREWRITE_FAILED", mutations_sent=0, telemetry=tel)
        return out
    os.makedirs(lock_dir, exist_ok=True)
    lock = os.path.join(lock_dir, "LOCK_%s.json" % doc["freeze_sha256"][:16])
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)            # replay guard persisted before the send
    os.write(fd, json.dumps({"freeze_sha256": doc["freeze_sha256"], "mutation_id": MUT_ID, "state": "ABOUT_TO_SEND"}).encode()); os.close(fd)
    gov(m.begin_execution, MUT_ID, pre["create_fingerprint_now"])
    t = time.perf_counter_ns()
    status, raw = c.call("tools/call", {"name": CREATE_TOOL, "arguments": doc["create_arguments"]}, tool=CREATE_TOOL)
    tel["provider_ns"] += time.perf_counter_ns() - t
    resp = probe.parse(raw)
    if status == 0 or raw.startswith("TRANSPORT_ERROR"):
        cls = "CALL_SENT_NO_RESPONSE"
    elif resp.get("error") or probe.text_of(resp)[1]:
        cls = "PROVIDER_ERROR"
    else:
        cls = "PROVIDER_RESPONSE_SUCCESS"
    er = make("ExecutionReceipt", receipt_id="R2_0C_EXEC", transaction_id=TX_ID, mutation_id=MUT_ID, call_class=cls)
    gov(m.record_execution, er)
    gov(m.request_readback)
    ex, obs = read_state(c, OBJ_NAME)
    rb = readback_receipt(f, ex, obs, "POST")
    gov(m.observe_readback, rb)
    commit = make("CommitObservation", observation_id="R2_0C_COMMIT", transaction_id=TX_ID, mutation_id=MUT_ID, readback_receipt_hash=rb["object_hash"],
                  commit_state={"EXISTS": "COMMITTED", "ABSENT": "ABSENT", "UNKNOWN": "UNKNOWN"}[ex])
    gov(m.decide_commit, commit)
    result = {"COMMIT_STATE_UNKNOWN": "COMMIT_STATE_UNKNOWN", "FAILED_AFTER_POSSIBLE_MUTATION": "NOT_COMMITTED"}.get(m.state)
    if m.state == "COMMITTED":
        res = eval_predicates(PREDICATES, rb["observed"])
        oc = make("OutcomeReceipt", receipt_id="R2_0C_OUTCOME_R", transaction_id=TX_ID, readback_receipt_hash=rb["object_hash"],
                  outcome_contract_hash=f["outcome_contract"]["object_hash"], result=res)
        gov(m.validate_outcome, oc)
        if m.state == "OUTCOME_VALIDATED":
            done = make("CompletionReceipt", receipt_id="R2_0C_DONE", transaction_id=TX_ID, outcome_receipt_hash=oc["object_hash"],
                        commit_observation_hash=commit["object_hash"], execution_receipt_hash=er["object_hash"], authority_hash=f["authority"]["object_hash"])
            gov(m.complete, done)
            result = "COMMITTED_AND_OUTCOME_VALIDATED"
        elif m.state == "COMPENSATION_REQUIRED":
            result = "COMMITTED_BUT_OUTCOME_FAILED"
        else:
            result = "COMMITTED_OUTCOME_UNKNOWN"
    out.update(final_state=m.state, RESULT=result, mutations_sent=m.mutations_sent, execution_call_class=cls, readback_existence=ex,
               readback_observed=obs, chain=[(k, h) for k, h in __import__("mcr_r2_model").chain_hashes(m)], telemetry=tel,
               telemetry_note="governance_ns excludes provider/readback network; single run, descriptive only")
    return out


# ------------------------------------------------------------------ mock provider (tests)
def mock_provider(scenario):
    st = {"created": False}

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a): pass

        def do_POST(self):
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            m, p, i = req["method"], req.get("params", {}), req.get("id")
            if "id" not in req:
                self.send_response(202); self.end_headers(); return
            if m == "initialize":
                res = {"protocolVersion": "2025-06-18"}
            elif m == "tools/list":
                names = ["abap_list_destinations", CREATE_TOOL, READ_TOOL] + ["t%d" % k for k in range(EXPECTED_TOOL_COUNT - 3)]
                res = {"tools": [{"name": n, "inputSchema": {"k": n}} for n in names]}
                H.fp = None
            else:
                n, a = p["name"], p["arguments"]
                if n == "abap_list_destinations":
                    res = {"content": [{"type": "text", "text": "[TRL_EN]"}], "isError": False}
                elif n == CREATE_TOOL:
                    if scenario in ("success", "timeout_persisted", "persisted_error_response", "readback_error", "outcome_fail"):
                        st["created"] = True
                    if scenario == "timeout_persisted":
                        time.sleep(1.5); self.close_connection = True; return      # client times out; object was created
                    res = {"content": [{"type": "text", "text": "boom"}], "isError": True} if scenario in ("error_not_persisted", "persisted_error_response") \
                        else {"content": [{"type": "text", "text": "{}"}], "isError": False}
                else:
                    if scenario == "readback_error" and st["created"]:
                        res = {"content": [{"type": "text", "text": "Unable to initialize the ADT Discovery"}], "isError": True}
                    elif st["created"]:
                        src = "define view entity %s as select from x" % a["objectName"]
                        d = {"found": True, "status": 200, "sourceType": "DDLS", "source": src, "sourceHash": hashlib.sha256(src.encode()).hexdigest().upper()}
                        if scenario == "outcome_fail":
                            d["source"] = "define view entity OTHER"; d["sourceHash"] = hashlib.sha256(d["source"].encode()).hexdigest().upper()
                        res = {"content": [{"type": "text", "text": json.dumps(d)}], "isError": False}
                    else:
                        src = '<exc:exception><type id="ExceptionResourceNotFound"/></exc:exception>'
                        res = {"content": [{"type": "text", "text": json.dumps({"found": False, "status": 404, "sourceType": "NOT_FOUND_VIA_DDLS_ENDPOINT", "source": src, "sourceHash": "0"})}], "isError": False}
            out = ("event: message\ndata: " + json.dumps({"jsonrpc": "2.0", "id": i, "result": res}) + "\n\n").encode()
            self.send_response(200); self.send_header("Content-Length", str(len(out))); self.end_headers(); self.wfile.write(out)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-freeze", action="store_true")
    ap.add_argument("--mock")
    ap.add_argument("--prewrite-live", action="store_true")
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--authorization")
    ap.add_argument("--auth-context", default=r"D:\MCR\ADT_AUTH_CONTEXT_R1.json")
    ap.add_argument("--evidence-dir", default=LOCK_DIR)
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    if a.build_freeze:
        doc = freeze_doc(); os.makedirs(os.path.dirname(FREEZE_PATH), exist_ok=True)
        json.dump(doc, open(FREEZE_PATH, "w", newline="\n"), indent=2, sort_keys=True)
        print("FREEZE_SHA256=%s\nRUNNER_UNSIGNED_SHA256=%s\nAUTH_PHRASE=%s" % (doc["freeze_sha256"], self_sha(), auth_phrase(doc["freeze_sha256"]))); return 0
    doc = json.load(open(FREEZE_PATH, encoding="utf-8"))
    body = {k: v for k, v in doc.items() if k != "freeze_sha256"}
    if chash(body) != doc["freeze_sha256"] or doc != dict(freeze_doc()):
        raise SystemExit("FREEZE_MISMATCH: freeze file does not match code/hash")
    ev = a.evidence_dir
    if a.mock:
        import tempfile
        srv = mock_provider(a.mock)
        c = probe.Client("http://127.0.0.1:%d/mcp" % srv.server_address[1], None, None, timeout=1)
        c.extra_tools = (CREATE_TOOL,)
        # mock tool fingerprints differ from the live one: patch the frozen expectation for MOCK only
        globals()["CREATE_FINGERPRINT"] = probe.sha(json.dumps({"n": CREATE_TOOL, "s": {"k": CREATE_TOOL}}, sort_keys=True))
        doc["objects"]["provider"] = make("ProviderBinding", provider_id="SAP_ADT_MCP", tool_name=CREATE_TOOL, contract_fingerprint=CREATE_FINGERPRINT,
                                          identity="SAP_ADT_MCP::" + CREATE_TOOL)
        out = run_mission(c, doc, tempfile.mkdtemp(prefix="r2c_mock_"), live=False)
        out["mode"] = "MOCK:" + a.mock
    else:
        ep, tok = probe.dpapi_token(a.auth_context)
        os.makedirs(ev, exist_ok=True)
        c = probe.Client(ep, tok, ev)
        c.extra_tools = (CREATE_TOOL,) if a.execute else ()      # prewrite-live stays strictly read-only
        if a.prewrite_live:
            pre, fps = prewrite_checks(c, doc["objects"]); out = {"mode": "LIVE_PREWRITE_READ_ONLY", "prewrite": pre, "mutations_sent": 0}
        elif a.execute:
            if a.authorization != auth_phrase(doc["freeze_sha256"]):
                raise SystemExit("AUTHORIZATION_PHRASE_MISMATCH (bound to freeze hash and runner hash); not executing")
            out = run_mission(c, doc, ev, live=True); out["mode"] = "LIVE_EXECUTE"
        else:
            raise SystemExit("choose --prewrite-live or --execute")
        out["call_log"] = [{k: v for k, v in e.items() if k != "ns"} for e in c.log]
    out.update(freeze_sha256=doc["freeze_sha256"], runner_sha256=self_sha())
    s = json.dumps(out, indent=2, sort_keys=True, default=str)
    if a.out:
        open(a.out, "w", newline="\n").write(s + "\n")
    print(s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
