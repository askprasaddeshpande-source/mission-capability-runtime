# MCR R2.0C Live-Write Authorization Packet R1

Status: **FROZEN, NOT AUTHORIZED.** No live write has been performed. SAP writes so far: 0.

```
LIVE_WRITE_STAGE=R2_0_C_FROZEN_LIVE_OUTCOME_STUDY
TARGET=SAP ABAP project destination TRL_EN (client 100), via the ADT MCP provider at loopback :2234 (SAP_ADT_MCP, 29 tools)
OBJECT=ZC_MCR20C_7A3F91D2 (fresh identity; absent in both versions at prewrite: see evidence/r2.0/MCR_R2_0_C_PREWRITE_LIVE_READONLY_R1.json)
OBJECT_TYPE=DDLS/DF (CDS data definition), created inactive, never activated
PACKAGE=ZCLINE, transportRequestNumber="" (if the system requires a transport the call errors and the study records NOT_COMMITTED)
PROVIDER=SAP_ADT_MCP, tool abap_creation-create_object, pinned fingerprint CB99759628F2258BFB8E13082ED4675E6B6A8F4A348C0BF30D259D2CFA1A0271 (sha256 of name + inputSchema; re-checked at point of use)
EXACT_MUTATIONS=1: abap_creation-create_object with {"destination":"TRL_EN","objectType":"DDLS/DF","objectContent":"{\"description\":\"MCR R2.0C disposable outcome study\",\"name\":\"ZC_MCR20C_7A3F91D2\",\"packageName\":\"ZCLINE\"}","transportRequestNumber":""}
VALIDATION_CALLS=read-only only: initialize, notifications/initialized, tools/list, abap_list_destinations, capella_adt_repository_read_metadata (inactive + active, before and after)
MAX_MUTATIONS=1
RETRIES=0
COMPENSATION_ALLOWED=NO (no grant exists; no delete tool is used)
ROLLBACK_POLICY=NONE. Cleanup is not authorized; a successful run leaves one disposable inactive DDLS in ZCLINE for the owner to remove manually if wanted
TRANSACTION_BOUNDARY=single object create, one call, no activation, no transport handling
EXPECTED_OUTCOME=frozen predicates (all must pass against the authoritative readback): exists=true; object_type=DDLS; source_hash_integrity=true (SHA-256 of returned source recomputed locally equals the tool's sourceHash); source_contains_object_name=true
AUTHORITATIVE_READBACK_METHOD=capella_adt_repository_read_metadata on the DDLS endpoint. 200 + found + sourceType DDLS -> EXISTS. 404 + ExceptionResourceNotFound from the DDLS endpoint in both versions -> ABSENT. Anything else (isError, transport failure, other status/type) -> UNKNOWN. Qualified in R2.0B with one positive control (existing DDLS) and negative controls
FAIL_CLOSED_RULES=lock file created (O_EXCL) before the send and refuses any second run; no retry on any failure; call error or timeout never implies NOT_COMMITTED (readback decides); UNKNOWN is never PASS or FAIL; prewrite failure (fingerprint, tool count, destination, baseline not ABSENT) sends nothing; freeze or runner change invalidates the authorization phrase
RUNNER_PATH=tools/r2.0/r2_0c_study.py (Python; the PowerShell signing policy does not apply to it)
RUNNER_UNSIGNED_SHA256=A73F4647E0AC9B672284A4A4D4A87AE031CBC6AFB7707362C9050ED632C3DDC9
CONTRACT_SHA256=8CCC5B949245638BF518776E3694BB8A6FC85A289B7B93BEBCC4D97591DAE951 (research-package/r2.0/r2_0c/R2_0C_FREEZE_R1.json; ExpectedOutcomeContract 7E32CA9CF01720E8E6178B00FE5DDF9BA721B8D5437377EBE3FEBF1D109C743D, readback contract 57715BFED1A182F64A7298DEB75E0759ECB3EABBDFA629E09615FD5B9C5F42B3)
MUTATION_BUDGET_SHA256=183C1554D2BF20038C2651352712ECC7F64D281DE2FF7D12C0AE96DEA2EA6A6E
PREWRITE_CHECKPOINT_SHA256=D4C3415F650957ECAFEBC315CF236DE925C1F93247846CAC6829F63EE9477E79
```

## Possible results (UNKNOWN is a valid research result)
COMMITTED_AND_OUTCOME_VALIDATED; COMMITTED_BUT_OUTCOME_FAILED; NOT_COMMITTED; COMMIT_STATE_UNKNOWN. All four are produced by the runner against an in-process mock (SYNTHETIC; `evidence/r2.0/MCR_R2_0_C_MOCK_SCENARIOS_R1.json`).

## What this study can and cannot show
- Can show (one run, OBSERVED at most): whether the tool response and the authoritative DDLS readback agree; commit observation correlated to one transaction/mutation id; execution receipt distinct from outcome receipt; the hash chain from intent to completion.
- Cannot show: package membership (not readable by the tool, recorded as NOT_ESTABLISHED), activation state (active-vs-inactive discrimination unproven: an existing object returned identical source for both versions; the study records both reads as observation only), transactional atomicity, replay behaviour on a real failure, compensation, or any general claim from a single mutation.
- Provider-contract drift since R1.8 (20 -> 29 tools) is already OBSERVED; this study pins the fingerprint of the one mutation tool only.

## Owner authorization (one explicit action)
Running this command **is** the authorization. The phrase is bound to the freeze hash and the runner hash; changing either invalidates it.

```
python tools\r2.0\r2_0c_study.py --execute --authorization AUTHORIZE_R2_0C:8CCC5B949245638B:A73F4647E0AC9B67 --out D:\MCR\r2.0-evidence\r2_0c\execution_report.json
```

Optional before authorizing: re-run the read-only prewrite check `python tools\r2.0\r2_0c_study.py --prewrite-live --out D:\MCR\r2.0-evidence\r2_0c_prewrite\prewrite_report.json`.

Requires: Eclipse ADT MCP running on :2234 and `D:\MCR\ADT_AUTH_CONTEXT_R1.json`. Raw responses are written to `D:\MCR\r2.0-evidence\r2_0c\` (outside Git).
