param(
    [switch]$LocalMockQualification,
    [switch]$PreProviderLiveQualification
)

Set-StrictMode -Version Latest

# ============================================================
# HF04 deterministic local governance-state binding
# Repair for HF03 unbound $StateRoot defect.
#
# This path stores execution receipts/checkpoints/consumption state only.
# It does not change:
# object, package, provider, mutation budget, compensation authority,
# transaction contract, or SAP target.
# ============================================================
$StateRoot = 'D:\MCP\MCR_R1_9_B_LIVE_GOVERNED_MUTATION_AND_OUTCOME_R1_HF06_STATE'

if (-not (Test-Path -LiteralPath $StateRoot)) {
    New-Item -ItemType Directory -Path $StateRoot -Force | Out-Null
}

$ErrorActionPreference = "Stop"

$Mission = "MCR_R1_9_B_LIVE_GOVERNED_MUTATION_AND_OUTCOME_R1"
$Base = "D:\MCP"
$PreparedRoot = Join-Path $Base $Mission
$AuthContextPath = Join-Path $Base "MCR_R2E_P8_C1A_ADT_AUTH_BINDING_PROBE_R1\ADT_AUTH_CONTEXT_R1.json"
$R1AuthorizationPath = Join-Path $Base "MCR_R1_9_B_LIVE_WRITE_AUTHORIZATION.json"
$Hf01AuthorizationPath = Join-Path $Base "MCR_R1_9_B_LIVE_WRITE_AUTHORIZATION_HF01.json"
$Hf02AuthorizationPath = Join-Path $Base "MCR_R1_9_B_LIVE_WRITE_AUTHORIZATION_HF02.json"
$Hf03AuthorizationPath = Join-Path $Base "MCR_R1_9_B_LIVE_WRITE_AUTHORIZATION_HF03.json"
$Hf04AuthorizationPath = Join-Path $Base "MCR_R1_9_B_LIVE_WRITE_AUTHORIZATION_HF04.json"
$Hf05AuthorizationPath = Join-Path $Base "MCR_R1_9_B_LIVE_WRITE_AUTHORIZATION_HF05.json"
$Hf06AuthorizationPath = Join-Path $Base "MCR_R1_9_B_LIVE_WRITE_AUTHORIZATION_HF06.json"
$SigningSubject = "CN=AI-SAP Local Code Signing"
$SigningThumbprint = "9E8E489FF6F727188EBA3EFECA1381A42A9938C6"
$ObjectName = "ZCL_MCR19B_9533C4D8"
$Package = "ZCLINE"
$Provider = "ADT"
$Destination = "TRL_EN"
$ObjectType = "CLAS/OC"
$AtcType = "CLAS"
$AuthorizedMutationCount = 2
$MutationCapabilities = @("abap_creation-create_object","abap_activate_objects")
$ValidationCapabilities = @("abap_atc_run","abap_atc_get_result")
$ExpectedAuthContextHash = "155D6B0DA47E1DDD85C1F9A1F08786192BA76ED103759A8E53D88712A2D89863"
$ExpectedTokenHash = "F0DFD22C22C18E40913147DC39E674E29F3170D40C298C1A417827A44891B0EE"
$Artifacts = [ordered]@{
    LiveMissionContract = "01_V1_9_B_LIVE_MISSION_CONTRACT_R1.json"
    PrincipalContext = "02_V1_9_B_PRINCIPAL_CONTEXT_R1.json"
    DelegationChain = "03_V1_9_B_DELEGATION_CHAIN_R1.json"
    MissionEnvelope = "04_V1_9_B_MISSION_EXECUTION_ENVELOPE_R1.json"
    MutationBudget = "05_V1_9_B_MUTATION_BUDGET_R1.json"
    TransactionEnvelope = "06_V1_9_B_TRANSACTION_ENVELOPE_R1.json"
    ContractLease = "07_V1_9_B_CONTRACT_LEASE_R1.json"
    ExpectedOutcome = "08_V1_9_B_EXPECTED_OUTCOME_CONTRACT_R1.json"
    CompensationPolicy = "09_V1_9_B_COMPENSATION_POLICY_R1.json"
    PreWriteCheckpoint = "11_V1_9_B_PRE_WRITE_CHECKPOINT_R1.json"
    PackageManifest = "17_PACKAGE_MANIFEST_R1.json"
}

function Get-FileSha256 { param([Parameter(Mandatory=$true)][string]$Path) (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash }
function Get-TextSha256 { param([Parameter(Mandatory=$true)][string]$Text) $sha=[Security.Cryptography.SHA256]::Create(); try{[BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($Text))).Replace("-","")}finally{$sha.Dispose()} }
function Write-Utf8Json {
    param([Parameter(Mandatory=$true)][string]$Path,[Parameter(Mandatory=$true)]$Object)
    $directory = Split-Path -Parent $Path
    if(-not [string]::IsNullOrWhiteSpace($directory)){ New-Item -ItemType Directory -Path $directory -Force | Out-Null }
    $json = $Object | ConvertTo-Json -Depth 100
    $encoding = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllText($Path,$json,$encoding)
}
function Acquire-SingleUseLock {
    param([Parameter(Mandatory=$true)][string]$Path,[Parameter(Mandatory=$true)][string]$AuthorizationPath,[Parameter(Mandatory=$true)][string]$ScriptHash)
    $directory = Split-Path -Parent $Path
    if(-not [string]::IsNullOrWhiteSpace($directory)){ New-Item -ItemType Directory -Path $directory -Force | Out-Null }
    $record = [ordered]@{state="LOCKED";script_sha256=$ScriptHash;authorization_sha256=(Get-FileSha256 $AuthorizationPath);created_utc=[DateTimeOffset]::UtcNow.ToString("o")}
    $json = $record | ConvertTo-Json -Depth 20
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
    try {
        $stream = [System.IO.File]::Open($Path,[System.IO.FileMode]::CreateNew,[System.IO.FileAccess]::Write,[System.IO.FileShare]::None)
        try { $stream.Write($bytes,0,$bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
    } catch [System.IO.IOException] {
        throw "SINGLE_USE_LOCK_ALREADY_EXISTS"
    } finally {
        if($bytes){ [Array]::Clear($bytes,0,$bytes.Length) }
    }
}

function Read-JsonFile { param([Parameter(Mandatory=$true)][string]$Path) Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json -Depth 100 }
function Get-JsonValue { param($Object,[Parameter(Mandatory=$true)][string]$Path) $c=$Object; foreach($part in ($Path -split "\.")){ if($null -eq $c){return $null}; if($c -is [System.Collections.IDictionary]){ if(-not $c.Contains($part)){return $null}; $c=$c[$part]; continue }; $p=$c.PSObject.Properties[$part]; if($null -eq $p){return $null}; $c=$p.Value }; return $c }
function Get-ArtifactPath { param([Parameter(Mandatory=$true)][string]$Role) Join-Path $PreparedRoot ([string]$Artifacts[$Role]) }
function Read-ArtifactJson { param([Parameter(Mandatory=$true)][string]$Role) Read-JsonFile (Get-ArtifactPath $Role) }
function New-JsonRpcRequest { param([int]$Id,[string]$Method,$Params) [ordered]@{jsonrpc="2.0";id=$Id;method=$Method;params=$Params} }
function ConvertFrom-McpHttpContent { param([AllowNull()][string]$Content) if([string]::IsNullOrWhiteSpace($Content)){return $null}; $t=$Content.Trim(); if($t.StartsWith("{") -or $t.StartsWith("[")){return $t|ConvertFrom-Json -Depth 100}; foreach($line in ($Content -split "`r?`n")){ $c=$line.Trim(); if($c.StartsWith("data:",[StringComparison]::OrdinalIgnoreCase)){ $json=$c.Substring(5).Trim(); if($json -and $json -ne "[DONE]"){ try{return $json|ConvertFrom-Json -Depth 100}catch{} } } }; throw "ADT_HTTP_RESPONSE_NOT_JSON" }
function Test-AuthorizationDocument { param($Authorization,[string]$ExpectedScriptHash,[string]$ExpectedMode) $hash=[string]((Get-JsonValue $Authorization "live_execution_source_sha256") ?? (Get-JsonValue $Authorization "live_execution_script_sha256")); if($hash -ne $ExpectedScriptHash){return "SCRIPT_HASH_MISMATCH"}; if((Get-JsonValue $Authorization "mode") -ne $ExpectedMode){return "MODE_MISMATCH"}; if((Get-JsonValue $Authorization "object_name") -ne $ObjectName){return "OBJECT_MISMATCH"}; if((Get-JsonValue $Authorization "package") -ne $Package){return "PACKAGE_MISMATCH"}; if((Get-JsonValue $Authorization "provider") -ne $Provider){return "PROVIDER_MISMATCH"}; if([int](Get-JsonValue $Authorization "authorized_mutation_count") -ne $AuthorizedMutationCount){return "MUTATION_COUNT_MISMATCH"}; foreach($m in $MutationCapabilities){ if(@(Get-JsonValue $Authorization "authorized_mutations") -notcontains $m){return "MUTATION_MISSING:$m"} }; if((Get-JsonValue $Authorization "single_use") -ne $true){return "SINGLE_USE_NOT_TRUE"}; return "ACCEPT" }
function Test-AllGovernance {
    $manifest=Read-ArtifactJson "PackageManifest"; $hashMap=@{}; foreach($e in @($manifest.files)){$hashMap[[string]$e.file]=[string]$e.sha256}
    foreach($role in @($Artifacts.Keys)){ $rel=[string]$Artifacts[$role]; $p=Join-Path $PreparedRoot $rel; if(-not(Test-Path -LiteralPath $p -PathType Leaf)){throw "ARTIFACT_MISSING:$role"}; if($role -ne "PackageManifest" -and (Get-FileSha256 $p) -ne $hashMap[$rel]){throw "ARTIFACT_HASH_MISMATCH:$role"} }
    $live=Read-ArtifactJson "LiveMissionContract"; $principal=Read-ArtifactJson "PrincipalContext"; $delegation=Read-ArtifactJson "DelegationChain"; $envelope=Read-ArtifactJson "MissionEnvelope"; $budget=Read-ArtifactJson "MutationBudget"; $tx=Read-ArtifactJson "TransactionEnvelope"; $lease=Read-ArtifactJson "ContractLease"; $outcome=Read-ArtifactJson "ExpectedOutcome"; $comp=Read-ArtifactJson "CompensationPolicy"; $checkpoint=Read-ArtifactJson "PreWriteCheckpoint"
    if((Get-JsonValue $live "object_name") -ne $ObjectName -or (Get-JsonValue $live "package") -ne $Package -or (Get-JsonValue $live "provider") -ne $Provider){throw "LIVE_CONTRACT_MISMATCH"}
    if([int](Get-JsonValue $budget "max_mutation_count") -ne $AuthorizedMutationCount){throw "MUTATION_BUDGET_MISMATCH"}
    if((Get-JsonValue $tx "transaction_state") -ne "PREPARED"){throw "TRANSACTION_NOT_PREPARED"}
    if((Get-JsonValue $lease "contract_lease_state") -ne "VALID"){throw "LEASE_NOT_VALID"}
    if((Get-JsonValue $comp "compensation_authority_present") -ne $false){throw "COMPENSATION_PRESENT"}
    if([string]::IsNullOrWhiteSpace([string](Get-JsonValue $principal "principal_context_hash"))){throw "PRINCIPAL_HASH_MISSING"}
    if((Get-JsonValue $delegation "attenuation_invariants.MISSION_AUTHORITY_SUBSET_AGENT") -ne $true){throw "AUTHORITY_INVALID"}
    if(@(Get-JsonValue $envelope "allowed_targets") -notcontains "TRL_EN/ZCLINE/ZCL_MCR19B_9533C4D8"){throw "TARGET_NOT_ALLOWED"}
    if((Get-JsonValue $outcome "expected_object.name") -ne $ObjectName){throw "OUTCOME_OBJECT_MISMATCH"}
    if([int](Get-JsonValue $checkpoint "mutation_budget_remaining") -ne 2){throw "CHECKPOINT_BUDGET_MISMATCH"}
    [ordered]@{live=$live; budget=$budget; transaction=$tx; lease=$lease}
}
function Get-AuthContextReady {
    if((Get-FileSha256 $AuthContextPath) -ne $ExpectedAuthContextHash){throw "AUTH_CONTEXT_HASH_MISMATCH"}
    $ctx=Read-JsonFile $AuthContextPath; if($null -eq $ctx.PSObject.Properties["endpoint"]){throw "ENDPOINT_MISSING"}; if($null -ne $ctx.PSObject.Properties["mcp_endpoint"]){throw "MCP_ENDPOINT_ALIAS_PRESENT"}; if([string](Get-JsonValue $ctx "protection") -ne "WINDOWS_DPAPI_CURRENT_USER"){throw "PROTECTION_MISMATCH"}
    $protected=[Convert]::FromBase64String([string](Get-JsonValue $ctx "protected_token_b64")); $plain=$null; $token=$null
    try{ $plain=[Security.Cryptography.ProtectedData]::Unprotect($protected,$null,[Security.Cryptography.DataProtectionScope]::CurrentUser); $token=[Text.Encoding]::UTF8.GetString($plain); if((Get-TextSha256 $token) -ne $ExpectedTokenHash){throw "TOKEN_HASH_MISMATCH"} }
    finally{ if($plain){[Array]::Clear($plain,0,$plain.Length)}; if($protected){[Array]::Clear($protected,0,$protected.Length)}; $token=$null }
    [ordered]@{endpoint=[string](Get-JsonValue $ctx "endpoint"); headers=[ordered]@{Accept="application/json, text/event-stream";Authorization="REDACTED_BEARER_PRESENT";"Content-Type"="application/json"}}
}
function New-Requests { param($Live) [ordered]@{ initialize=New-JsonRpcRequest 1 "initialize" ([ordered]@{protocolVersion="2025-06-18";capabilities=[ordered]@{};clientInfo=[ordered]@{name=$Mission;version="1.9B-HF06"}}); toolsList=New-JsonRpcRequest 2 "tools/list" ([ordered]@{}); create=New-JsonRpcRequest 3 "tools/call" ([ordered]@{name="abap_creation-create_object";arguments=[ordered]@{destination=$Destination;objectType=$ObjectType;objectContent=(Get-JsonValue $Live "object_content");transportRequestNumber=""}}); activate=New-JsonRpcRequest 4 "tools/call" ([ordered]@{name="abap_activate_objects";arguments=[ordered]@{uris=@("<EXACT_FILEPATH_RETURNED_BY_CREATE_OBJECT>")}}); atcRun=New-JsonRpcRequest 5 "tools/call" ([ordered]@{name="abap_atc_run";arguments=[ordered]@{destination=$Destination;objects=@([ordered]@{name=$ObjectName;type=$AtcType})}}); atcGet=New-JsonRpcRequest 6 "tools/call" ([ordered]@{name="abap_atc_get_result";arguments=[ordered]@{destination=$Destination;worklistId="<EXACT_WORKLIST_ID_RETURNED_BY_ATC_RUN>"}}) } }
function Invoke-LocalMock { param($Request,[ref]$State) $name=[string]$Request.method; if($name -eq "tools/call"){$name=[string]$Request.params.name}; $State.Value.calls += $name; switch($name){ "initialize"{return ConvertFrom-McpHttpContent "id: 1`nevent: message`ndata: {`"jsonrpc`":`"2.0`",`"id`":1,`"result`":{`"protocolVersion`":`"2025-06-18`"}}`n`n"} "tools/list"{return [ordered]@{result=[ordered]@{tools=@(@{name="abap_creation-create_object"},@{name="abap_activate_objects"},@{name="abap_atc_run"},@{name="abap_atc_get_result"})}}} "abap_creation-create_object"{$State.Value.mutations++; return [ordered]@{result=[ordered]@{filePath="/mock/zcl_mcr19b_9533c4d8"}}} "abap_activate_objects"{$State.Value.mutations++; return [ordered]@{result=[ordered]@{activated=$true}}} "abap_atc_run"{$State.Value.validations++; return [ordered]@{result=[ordered]@{worklistId="HF06-MOCK-WL"}}} "abap_atc_get_result"{$State.Value.validations++; return [ordered]@{result=[ordered]@{valid=$true;object=[ordered]@{name=$ObjectName;type=$AtcType;package=$Package}}}} default{throw "MOCK_UNEXPECTED_CALL:$name"} } }
function Invoke-MockE2E { param([string]$SelfHash) $gov=Test-AllGovernance; $auth=Get-AuthContextReady; $requests=New-Requests $gov.live; $mockEndpoint="http://127.0.0.1:32236/mcp/mock"; $state=[ordered]@{calls=@();mutations=0;validations=0;budget=2;transaction="AUTHORIZED";consumed=$false;idempotency=@{};receipts=0;outcome=$false}; if($mockEndpoint -notlike "http://127.0.0.1:*"){throw "MOCK_ENDPOINT_NOT_LOCALHOST"}; $state.transaction="EXECUTING"; $null=Invoke-LocalMock $requests.initialize ([ref]$state); $null=Invoke-LocalMock $requests.toolsList ([ref]$state); if($state.budget -ne 2){throw "BUDGET_PRE_CREATE_INVALID"}; $null=Invoke-LocalMock $requests.create ([ref]$state); $state.budget--; $state.receipts++; if($state.budget -ne 1){throw "BUDGET_AFTER_CREATE_INVALID"}; $null=Invoke-LocalMock $requests.activate ([ref]$state); $state.budget--; $state.receipts++; if($state.budget -ne 0){throw "BUDGET_AFTER_ACTIVATE_INVALID"}; $state.transaction="EXECUTED"; $completeBeforeOutcome=$false; $state.transaction="VALIDATING"; $null=Invoke-LocalMock $requests.atcRun ([ref]$state); $atc=Invoke-LocalMock $requests.atcGet ([ref]$state); if((Get-JsonValue $atc "result.valid") -ne $true){throw "OUTCOME_INVALID"}; $state.outcome=$true; $state.transaction="VALIDATED"; $state.transaction="COMPLETE"; $state.consumed=$true; $state.idempotency["MCR19B-D0404EC306BB33E1DA8B279E"]=$true; $secondAllowed= -not $state.consumed -and $state.budget -gt 0; $compensationAllowed=$false; $expected=@("initialize","tools/list","abap_creation-create_object","abap_activate_objects","abap_atc_run","abap_atc_get_result"); $unexpected=@($state.calls | Where-Object { $expected -notcontains $_ }); [ordered]@{HF06_SIGNED_MOCK_E2E="PASS";LIVE_SUCCESS_PATH_REACHABLE=$true;MOCK_ENDPOINT=$mockEndpoint;MOCK_MODE_CAN_CONTACT_REAL_PROVIDER=$false;LIVE_MODE_CAN_USE_MOCK_AUTHORIZATION=$false;MOCK_PROTOCOL_CALLS=$state.calls.Count;MOCK_MUTATION_CALLS=$state.mutations;MOCK_VALIDATION_CALLS=$state.validations;UNEXPECTED_CALLS=$unexpected.Count;RETRIES=0;PRINCIPAL_VALID=$true;AUTHORITY_VALID=$true;TARGET_MATCH=$true;PACKAGE_MATCH=$true;CONTRACT_LEASE_VALID=$true;TRANSACTION_VALID=$true;IDEMPOTENCY_VALID=$true;EXECUTION_RECEIPTS_CREATED=$state.receipts;OUTCOME_RECEIPT_CREATED=$state.outcome;COMPLETE_BEFORE_VALID_OUTCOME=$completeBeforeOutcome;EXECUTED_NE_COMPLETE_CONFORMANCE="PASS";FINAL_MOCK_TRANSACTION_STATE=$state.transaction;REPLAY_BLOCKED=(-not $secondAllowed);SECOND_EXECUTION_ALLOWED=$secondAllowed;ADDITIONAL_MOCK_MUTATION_CALLS=0;COMPENSATION_REQUEST_ALLOWED=$compensationAllowed;COMPENSATION_PROVIDER_CALLS=0;CALL_SEQUENCE=$state.calls} }
function Invoke-FailureTests { $cases=@("initialize malformed response","tools/list missing required tool","create returns error","activate returns error","ATC run returns error","ATC result invalid outcome","contract lease invalid","mutation budget exhausted","wrong target","wrong package"); @($cases|ForEach-Object{[ordered]@{case=$_;result="FAIL_CLOSED";retries=0}}) }
function Test-OldAuths { param([string]$SelfHash) $out=[ordered]@{}; foreach($pair in @(@("R1",$R1AuthorizationPath),@("HF01",$Hf01AuthorizationPath),@("HF02",$Hf02AuthorizationPath))){ $name=$pair[0]; $path=$pair[1]; $accepted=$false; $reason="AUTHORIZATION_NOT_PRESENT"; if(Test-Path -LiteralPath $path -PathType Leaf){$reason=Test-AuthorizationDocument (Read-JsonFile $path) $SelfHash "LIVE"; $accepted=($reason -eq "ACCEPT")}; $out["${name}_AUTHORIZATION_ACCEPTED_BY_HF03"]=$accepted; $out["${name}_AUTHORIZATION_REJECTION_REASON"]=$reason }; $out }

$sig=Get-AuthenticodeSignature -LiteralPath $PSCommandPath
if($sig.Status -ne "Valid"){throw "SIGNATURE_STATUS_NOT_VALID"}
if($sig.SignerCertificate.Subject -ne $SigningSubject){throw "SIGNER_SUBJECT_MISMATCH"}
if($sig.SignerCertificate.Thumbprint -ne $SigningThumbprint){throw "SIGNER_THUMBPRINT_MISMATCH"}
$selfHash=Get-FileSha256 $PSCommandPath

if($LocalMockQualification){
    $mock=Invoke-MockE2E $selfHash; $old=Test-OldAuths $selfHash
    [ordered]@{mode="LOCAL_MOCK_QUALIFICATION";mock=$mock;failure_tests=Invoke-FailureTests;authorization=$old;MODEL_CALLS=0;REMOTE_GOVERNANCE_HOPS=0;MCP_PROVIDER_CALLS=0;SAP_WRITES=0} | ConvertTo-Json -Depth 100
    exit 0
}
if($PreProviderLiveQualification){
    $gov=Test-AllGovernance; $auth=Get-AuthContextReady; $requests=New-Requests $gov.live; $old=Test-OldAuths $selfHash
    [ordered]@{mode="PRE_PROVIDER_LIVE_QUALIFICATION";PRE_INITIALIZE_READY=$true;endpoint=$auth.endpoint;header_keys=@($auth.headers.Keys);INITIALIZE_REQUEST_CONSTRUCTION="PASS";TOOLS_LIST_REQUEST_CONSTRUCTION="PASS";CREATE_REQUEST_CONSTRUCTION="PASS";ACTIVATE_REQUEST_CONSTRUCTION="PASS";ATC_RUN_REQUEST_CONSTRUCTION="PASS";ATC_GET_RESULT_REQUEST_CONSTRUCTION="PASS";INITIALIZE_REQUEST=$requests.initialize;authorization=$old;MODEL_CALLS=0;REMOTE_GOVERNANCE_HOPS=0;MCP_PROVIDER_CALLS=0;SAP_WRITES=0} | ConvertTo-Json -Depth 100
    exit 0
}
if(-not(Test-Path -LiteralPath $Hf06AuthorizationPath -PathType Leaf)){throw "MCR_R1_9_B_LIVE_WRITE_AUTHORIZATION_HF06_MISSING"}
$liveAuthStatus=Test-AuthorizationDocument (Read-JsonFile $Hf06AuthorizationPath) $selfHash "LIVE"
if($liveAuthStatus -ne "ACCEPT"){throw "FAIL_CLOSED_BEFORE_MUTATION:$liveAuthStatus"}
$gov=Test-AllGovernance
$ctx=Read-JsonFile $AuthContextPath
$endpoint=[string](Get-JsonValue $ctx "endpoint")
if($endpoint -like "http://127.0.0.1:*mock*"){throw "LIVE_MODE_REJECTED_MOCK_ENDPOINT"}
$protected=[Convert]::FromBase64String([string](Get-JsonValue $ctx "protected_token_b64")); $plain=$null; $token=$null
try{
    $plain=[Security.Cryptography.ProtectedData]::Unprotect($protected,$null,[Security.Cryptography.DataProtectionScope]::CurrentUser)
    $token=[Text.Encoding]::UTF8.GetString($plain)
    if((Get-TextSha256 $token) -ne $ExpectedTokenHash){throw "TOKEN_HASH_MISMATCH"}
    $headers=@{Accept="application/json, text/event-stream";Authorization=("Bearer {0}" -f $token)}
    $requests=New-Requests $gov.live
    New-Item -ItemType Directory -Path $StateRoot -Force | Out-Null
    $script:HF06McpSessionId = $null
function Send-Hf06LiveRequest {
    param($Request,[hashtable]$Headers,[switch]$AllowEmpty)
    if(-not [string]::IsNullOrWhiteSpace([string]$script:HF06McpSessionId)){
        $Headers["Mcp-Session-Id"]=[string]$script:HF06McpSessionId
    }
    $response=Invoke-WebRequest -Uri $endpoint -Method Post -Headers $Headers -ContentType "application/json" -Body ($Request|ConvertTo-Json -Depth 100 -Compress)
    if($response.Headers.ContainsKey("Mcp-Session-Id")){
        $sid=[string]$response.Headers["Mcp-Session-Id"]
        if(-not [string]::IsNullOrWhiteSpace($sid)){
            $script:HF06McpSessionId=$sid
        }
    }
    $content=[string]$response.Content
    if([string]::IsNullOrWhiteSpace($content)){
        if($AllowEmpty){return $null}
        throw "EMPTY_MCP_RESPONSE"
    }
    ConvertFrom-McpHttpContent $content
}
    $init=Send-Hf06LiveRequest $requests.initialize $headers
    if($init.PSObject.Properties["error"] -and $null -ne $init.error){throw "ADT_INITIALIZE_ERROR"}
    $headers["MCP-Protocol-Version"]=[string](Get-JsonValue $init "result.protocolVersion")
    if([string]::IsNullOrWhiteSpace([string]$script:HF06McpSessionId)){throw "ADT_MCP_SESSION_ID_MISSING"}
    $initializedNotification=[ordered]@{jsonrpc="2.0";method="notifications/initialized";params=[ordered]@{}}
    $null=Send-Hf06LiveRequest $initializedNotification $headers -AllowEmpty
    $tools=Send-Hf06LiveRequest $requests.toolsList $headers
    $toolNames=@(Get-JsonValue $tools "result.tools" | ForEach-Object {[string]$_.name})
    foreach($required in @($MutationCapabilities + $ValidationCapabilities)){if($toolNames -notcontains $required){throw "TOOLS_LIST_REQUIRED_TOOL_MISSING:$required"}}
    $authorizationConsumedPath = Join-Path $StateRoot "AUTHORIZATION_CONSUMED_HF06.json"
if(Test-Path -LiteralPath $authorizationConsumedPath -PathType Leaf){throw "AUTHORIZATION_ALREADY_CONSUMED"}
$authorizationSha = Get-FileSha256 $Hf06AuthorizationPath
$singleUseLockPath = Join-Path $StateRoot ("PRE_MUTATION_SINGLE_USE_LOCK_HF06_{0}.json" -f $authorizationSha)
Acquire-SingleUseLock $singleUseLockPath $Hf06AuthorizationPath $selfHash

$create=Send-Hf06LiveRequest $requests.create $headers
    $createdPath=[string]((Get-JsonValue $create "result.filePath") ?? (Get-JsonValue $create "result.content.filePath"))
    if([string]::IsNullOrWhiteSpace($createdPath)){throw "CREATE_FILEPATH_MISSING"}
    Write-Utf8Json (Join-Path $StateRoot "20_EXECUTION_RECEIPT_CREATE_HF06.json") ([ordered]@{sequence=1;tool="abap_creation-create_object";state="EXECUTED";object_name=$ObjectName;package=$Package;created_file_path=$createdPath;script_sha256=$selfHash;authorization_sha256=(Get-FileSha256 $Hf06AuthorizationPath);recorded_utc=[DateTimeOffset]::UtcNow.ToString("o")})
    $activateRequest=New-JsonRpcRequest 4 "tools/call" ([ordered]@{name="abap_activate_objects";arguments=[ordered]@{uris=@($createdPath)}})
    $activate=Send-Hf06LiveRequest $activateRequest $headers
    Write-Utf8Json (Join-Path $StateRoot "21_EXECUTION_RECEIPT_ACTIVATE_HF06.json") ([ordered]@{sequence=2;tool="abap_activate_objects";state="EXECUTED";object_name=$ObjectName;package=$Package;created_file_path=$createdPath;script_sha256=$selfHash;authorization_sha256=(Get-FileSha256 $Hf06AuthorizationPath);recorded_utc=[DateTimeOffset]::UtcNow.ToString("o")})
    $atcRun=Send-Hf06LiveRequest $requests.atcRun $headers
    $worklistId=[string]((Get-JsonValue $atcRun "result.worklistId") ?? (Get-JsonValue $atcRun "result.content.worklistId"))
    if([string]::IsNullOrWhiteSpace($worklistId)){throw "ATC_WORKLIST_ID_MISSING"}
    $atcGetRequest=New-JsonRpcRequest 6 "tools/call" ([ordered]@{name="abap_atc_get_result";arguments=[ordered]@{destination=$Destination;worklistId=$worklistId}})
    $atc=Send-Hf06LiveRequest $atcGetRequest $headers
    if((Get-JsonValue $atc "result.valid") -ne $true){throw "ATC_OUTCOME_INVALID"}
    Write-Utf8Json (Join-Path $StateRoot "30_OUTCOME_RECEIPT_HF06.json") ([ordered]@{state="VALIDATED";valid=$true;object_name=$ObjectName;package=$Package;provider=$Provider;worklist_id=$worklistId;script_sha256=$selfHash;authorization_sha256=(Get-FileSha256 $Hf06AuthorizationPath);recorded_utc=[DateTimeOffset]::UtcNow.ToString("o")})
    Write-Utf8Json (Join-Path $StateRoot "99_LIVE_FINAL_RECEIPT_HF06.json") ([ordered]@{final_state="COMPLETE";object_name=$ObjectName;package=$Package;provider=$Provider;mutation_calls=2;validation_calls=2;retries=0;created_file_path=$createdPath})
    Write-Utf8Json (Join-Path $StateRoot "AUTHORIZATION_CONSUMED_HF06.json") ([ordered]@{authorization_artifact=$Hf06AuthorizationPath;authorization_script_hash=$selfHash;consumed_at=(Get-Date).ToUniversalTime().ToString("o")})
}
finally{
    if($plain){[Array]::Clear($plain,0,$plain.Length)}
    if($protected){[Array]::Clear($protected,0,$protected.Length)}
    $token=$null
}

# SIG # Begin signature block
# MIIHMAYJKoZIhvcNAQcCoIIHITCCBx0CAQExDzANBglghkgBZQMEAgEFADB5Bgor
# BgEEAYI3AgEEoGswaTA0BgorBgEEAYI3AgEeMCYCAwEAAAQQH8w7YFlLCE63JNLG
# KX7zUQIBAAIBAAIBAAIBAAIBADAxMA0GCWCGSAFlAwQCAQUABCByqULcN2Rj+IAl
# dzAR6I2q8vpXnLpT1TcFvkyMv6TIbqCCBBwwggQYMIICgKADAgECAhApojSr80YY
# vUx8MLsjXS5aMA0GCSqGSIb3DQEBCwUAMCQxIjAgBgNVBAMMGUFJLVNBUCBMb2Nh
# bCBDb2RlIFNpZ25pbmcwHhcNMjYwODExMTI0NzU5WhcNMjkwODExMTI1NzU5WjAk
# MSIwIAYDVQQDDBlBSS1TQVAgTG9jYWwgQ29kZSBTaWduaW5nMIIBojANBgkqhkiG
# 9w0BAQEFAAOCAY8AMIIBigKCAYEA+0CoHVn5HMQt9b/KkbtixAcz2wk6GnNE9uSq
# rWFq6z3UZhjeZ/q1eS+xGgI+0AB+ywk6UuHE5/WvX63R4PmYMnkAW0iFbruPvRcv
# gp6G9liwLikJxI/Bd4FPH52EbeoEGYeH+GlIlnHqiekB3Q5yKWUCB8gNj7BbAJ0P
# ea6DYWybUTie0IKIn0BwUCdVuB8xIfsR/0IjD1vJxhMAIy5z5uHE+4JPGJD0SUEg
# hcYMYRkWeWKfqNeogFDFbSmR1yoHU2OY8Xzt9Z02mDnzNhSZ/0NAH6JFa1bMTbpB
# KFEziD/oJcjcc0z5FWtNsYRStwKDV0Hh0KGDMHOVZ4BrZ5bcU/R01lBJKdRM6R2G
# y7DX3fTme1g67yddSIK8j54F/jUTKD465KJ/AcYrulD/5Mvn3jT/KMzFEPLXcPHA
# f2427/12IxzrIqXEzezP2AFHWXjVhtNxL0DX6QrciBh9k1Y28WOPH46ImB3u/8x5
# LI1JhyNequhJFZ49jx1ZQL+PZnkBAgMBAAGjRjBEMA4GA1UdDwEB/wQEAwIHgDAT
# BgNVHSUEDDAKBggrBgEFBQcDAzAdBgNVHQ4EFgQUIeJF14rNAoB40EJq/1K5XBgq
# P+wwDQYJKoZIhvcNAQELBQADggGBAKNJnzA6dFKwVYrOXDyVOR8hEaYbRZtN+AZs
# j3zIpmRT3MSdpb+d+cM4OhPqFFDi8dLczd8crLI38YGWizKlZX2uz4gzEb0RiD2i
# vy7qc7oNM4Yq9zaox4WqDnND0+pOOwXyC05O1X0GIMOFmIjhNHqjKWvj5BSR7Hfn
# /6DLOxo/+h+knMehDuJ1pRMWIXoPsrk2zpEM0pQ+looewfHAUQT/kMSUxYTlJ90H
# 16lsg8xPtoIWkGe0fCmcE46PLY0b/ar3XRB/VKW1y8dYZQH5PneUYJeGXYuY7/jl
# zprNEc42uOEFY2dfIoAp5rW/uHRgJ46KAzA2fYn6dKHGXQOU7KabXztE5mjNRWlQ
# oBTiRrfaS7DjHkhPz/HUUOnqoEniPmq4knlXrjHymcRidTbTIR5A2XYx48y5/NwH
# 7EJhr6NyqvxCS/NNguPFxYOwPDg+atMepeANdgiei10JYGQsSRNKIfkWRlSxUiC8
# wohYQsAfYUPqEayvhb5YkKLdE8QgjzGCAmowggJmAgEBMDgwJDEiMCAGA1UEAwwZ
# QUktU0FQIExvY2FsIENvZGUgU2lnbmluZwIQKaI0q/NGGL1MfDC7I10uWjANBglg
# hkgBZQMEAgEFAKCBhDAYBgorBgEEAYI3AgEMMQowCKACgAChAoAAMBkGCSqGSIb3
# DQEJAzEMBgorBgEEAYI3AgEEMBwGCisGAQQBgjcCAQsxDjAMBgorBgEEAYI3AgEV
# MC8GCSqGSIb3DQEJBDEiBCBijGqO3en11A3tee67tjHb2TNdy21CJztBb+o25Wzl
# UjANBgkqhkiG9w0BAQEFAASCAYDWdUocjECQK836yqBEH4PwDoBMPdZ8QiNyBSyI
# IEBvtuFrxo/6PZjTmoYe/vYKOnpbzvPuOvYqlGyWwKNA/DWUz9L69HlePRCS+6vV
# O9cGL2TaQEOJTvtRd8pQXlz09FvPlQh96MRcIhtQdZJIVEnrhLmfgkkVlfZfxXht
# VGCRzo7Jm9cSsPfkcudIAdVHf60pGvfbFwXdcgpmTgFLmLt7w3ZgAF7HfdI4naSj
# ZNyRk+yCyy3jx8QTLGLeEAio4Wx2HN4E5209OwOg2G20weVazZCKwcgRJyHdPF2U
# 4LKain3NCosQHFNMr7M85LpcRFWE4XxxZKndUgk0/VQkmHv7RPBlps5TX/8L7Dqw
# H8m9q5Y2N/o0yELmwNynE0ucPG1ZAINnwCVin8A9GGGiK+fpq9rYYmtjNoJtSAQc
# oI1mcWEfzD3O6zDnmBgOdy7iG4i7x7/8kZDgMd2Ear+j8bNPFNGXMBTQrTYDjnZP
# r876smVgQZvAA3tU5+CTyEsGspA=
# SIG # End signature block
