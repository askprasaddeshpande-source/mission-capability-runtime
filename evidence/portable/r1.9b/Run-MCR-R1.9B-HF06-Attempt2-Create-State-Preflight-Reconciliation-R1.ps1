[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# ============================================================
# MCR R1.9B
# HF06 ATTEMPT-2 CREATE-STATE RECONCILIATION VIA EXACT
# CREATE-PREFLIGHT VALIDATION R1
#
# BOUNDED LIVE READ/VALIDATION ONLY.
#
# Provider sequence:
#   initialize
#   notifications/initialized
#   tools/list
#   abap_creation-get_object_type_details
#   abap_creation-run_validation
#   STOP
#
# NO create_object
# NO activate_objects
# NO ATC run
# NO compensation
# NO cleanup/delete
# NO authorization reuse
# ============================================================

$Root = 'D:\MCP'
$Mission = 'MCR_R1_9_B_LIVE_GOVERNED_MUTATION_AND_OUTCOME_R1'
$PreparedRoot = Join-Path $Root $Mission

$HF06 = Join-Path $Root 'Run-MCR-R1.9B-Live-Governed-Mutation-And-Outcome-R1-HF06.ps1'
$HF06Auth = Join-Path $Root 'MCR_R1_9_B_LIVE_WRITE_AUTHORIZATION_HF06.json'
$HF06StateRoot = Join-Path $Root 'MCR_R1_9_B_LIVE_GOVERNED_MUTATION_AND_OUTCOME_R1_HF06_STATE'

$AuthContextPath = Join-Path $Root 'MCR_R2E_P8_C1A_ADT_AUTH_BINDING_PROBE_R1\ADT_AUTH_CONTEXT_R1.json'
$ManifestPath = Join-Path $PreparedRoot '17_PACKAGE_MANIFEST_R1.json'
$EvidenceRoot = Join-Path $Root 'MCR_R1_9_B_HF06_ATTEMPT2_CREATE_STATE_PREFLIGHT_RECONCILIATION_R1'

$ExpectedHF06Hash = 'DE183ABC47B8F025ED60CFE5CFEA4527585FB20154C949628BDE95E42A0D3C88'
$ExpectedHF06AuthHash = 'CC06B59F341E9B70844F7BEE48F6917303C094206431C228575F91E4500B9E09'
$ExpectedLockHash = 'DFE129A6D66656B4477B1693D5073CD17B40918516DCF725A6193C019B7BB275'
$ExpectedManifestHash = 'A2D10E3D4A9D467781F604D7DC48A4D60E89D9B9A3B8287DF0E5344DA56190BA'
$ExpectedAuthContextHash = '155D6B0DA47E1DDD85C1F9A1F08786192BA76ED103759A8E53D88712A2D89863'
$ExpectedTokenHash = 'F0DFD22C22C18E40913147DC39E674E29F3170D40C298C1A417827A44891B0EE'
$SignerThumbprint = '9E8E489FF6F727188EBA3EFECA1381A42A9938C6'

$Destination = 'TRL_EN'
$ObjectName = 'ZCL_MCR19B_9533C4D8'
$ObjectType = 'CLAS/OC'
$Package = 'ZCLINE'
$ProtocolVersion = '2025-06-18'
$ExpectedEndpoint = 'http://127.0.0.1:2236/mcp'

$ProviderCalls = 0
$ToolCallRequests = 0
$SapRemoteReadCalls = 0
$SapRemoteValidationCalls = 0
$SapWrites = 0

$SessionId = $null
$Token = $null
$Plain = $null
$Protected = $null
$Utf8NoBom = [System.Text.UTF8Encoding]::new($false)

New-Item -ItemType Directory -Path $EvidenceRoot -Force | Out-Null

function Get-FileSha256Local {
    param([Parameter(Mandatory=$true)][string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}

function Get-TextSha256Local {
    param([Parameter(Mandatory=$true)][string]$Text)

    $Sha = [Security.Cryptography.SHA256]::Create()
    try {
        $Bytes = [Text.Encoding]::UTF8.GetBytes($Text)
        try {
            return [BitConverter]::ToString(
                $Sha.ComputeHash($Bytes)
            ).Replace('-','')
        }
        finally {
            [Array]::Clear($Bytes,0,$Bytes.Length)
        }
    }
    finally {
        $Sha.Dispose()
    }
}

function Write-JsonEvidence {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)]$Object
    )

    [System.IO.File]::WriteAllText(
        $Path,
        ($Object | ConvertTo-Json -Depth 50),
        $Utf8NoBom
    )
}

function Convert-McpContent {
    param([AllowNull()][string]$Content)

    if ([string]::IsNullOrWhiteSpace($Content)) {
        return $null
    }

    $Trimmed = $Content.Trim()

    if ($Trimmed.StartsWith('{') -or $Trimmed.StartsWith('[')) {
        return ($Trimmed | ConvertFrom-Json -Depth 100)
    }

    foreach ($Line in ($Content -split "`r?`n")) {
        $Candidate = $Line.Trim()

        if ($Candidate.StartsWith('data:', [StringComparison]::OrdinalIgnoreCase)) {
            $Json = $Candidate.Substring(5).Trim()

            if (-not [string]::IsNullOrWhiteSpace($Json) -and $Json -ne '[DONE]') {
                try {
                    return ($Json | ConvertFrom-Json -Depth 100)
                }
                catch {
                }
            }
        }
    }

    throw 'MCP_RESPONSE_NOT_JSON_OR_SSE'
}

function Invoke-McpRequest {
    param(
        [Parameter(Mandatory=$true)]$Body,
        [Parameter(Mandatory=$true)][string]$Label,
        [switch]$AllowEmpty,
        [switch]$IsToolCall
    )

    $script:ProviderCalls++

    if ($IsToolCall) {
        $script:ToolCallRequests++
    }

    $Headers = @{
        Authorization = "Bearer $script:Token"
        Accept = 'application/json, text/event-stream'
    }

    if (-not [string]::IsNullOrWhiteSpace($script:ProtocolVersion)) {
        $Headers['MCP-Protocol-Version'] = $script:ProtocolVersion
    }

    if (-not [string]::IsNullOrWhiteSpace($script:SessionId)) {
        $Headers['Mcp-Session-Id'] = $script:SessionId
    }

    $Response = Invoke-WebRequest `
        -Uri $script:ExpectedEndpoint `
        -Method Post `
        -Headers $Headers `
        -ContentType 'application/json' `
        -Body ($Body | ConvertTo-Json -Depth 100 -Compress) `
        -TimeoutSec 30

    if ($Response.Headers.ContainsKey('Mcp-Session-Id')) {
        $Sid = [string]$Response.Headers['Mcp-Session-Id']

        if (-not [string]::IsNullOrWhiteSpace($Sid)) {
            $script:SessionId = $Sid
        }
    }

    $RawPath = Join-Path `
        $script:EvidenceRoot `
        ('{0:D2}_{1}_RAW_RESPONSE.txt' -f $script:ProviderCalls,$Label)

    [System.IO.File]::WriteAllText(
        $RawPath,
        [string]$Response.Content,
        $script:Utf8NoBom
    )

    if ([string]::IsNullOrWhiteSpace([string]$Response.Content)) {
        if ($AllowEmpty) {
            return $null
        }

        throw "EMPTY_MCP_RESPONSE=$Label"
    }

    $Parsed = Convert-McpContent ([string]$Response.Content)

    if (
        $null -ne $Parsed -and
        $null -ne $Parsed.PSObject.Properties['error'] -and
        $null -ne $Parsed.error
    ) {
        throw (
            'MCP_JSONRPC_ERROR:{0}:{1}' -f
            $Label,
            ($Parsed.error | ConvertTo-Json -Depth 20 -Compress)
        )
    }

    return $Parsed
}

function Get-RecursiveNamedValues {
    param(
        [AllowNull()]$Value,
        [Parameter(Mandatory=$true)][string[]]$Names
    )

    $Output = New-Object System.Collections.Generic.List[string]
    $Wanted = @{}

    foreach ($Name in $Names) {
        $Wanted[$Name.ToLowerInvariant()] = $true
    }

    function Visit {
        param($Node)

        if ($null -eq $Node -or $Node -is [string]) {
            return
        }

        if ($Node -is [System.Collections.IDictionary]) {
            foreach ($Key in $Node.Keys) {
                $KeyString = [string]$Key
                $Child = $Node[$Key]

                if ($Wanted.ContainsKey($KeyString.ToLowerInvariant())) {
                    if ($null -ne $Child) {
                        $Output.Add([string]$Child)
                    }
                }

                Visit $Child
            }
            return
        }

        if (
            $Node -is [System.Collections.IEnumerable] -and
            -not ($Node -is [string])
        ) {
            foreach ($Item in $Node) {
                Visit $Item
            }
            return
        }

        foreach ($Property in $Node.PSObject.Properties) {
            $NameString = [string]$Property.Name
            $Child = $Property.Value

            if ($Wanted.ContainsKey($NameString.ToLowerInvariant())) {
                if ($null -ne $Child) {
                    $Output.Add([string]$Child)
                }
            }

            Visit $Child
        }
    }

    Visit $Value
    return @($Output)
}

function Get-ToolTextPayloads {
    param([AllowNull()]$Response)

    $Texts = New-Object System.Collections.Generic.List[string]

    foreach ($Candidate in @(
        Get-RecursiveNamedValues `
            -Value $Response `
            -Names @('message','error','text')
    )) {
        if (-not [string]::IsNullOrWhiteSpace([string]$Candidate)) {
            $Texts.Add([string]$Candidate)

            $Trimmed = ([string]$Candidate).Trim()

            if (
                ($Trimmed.StartsWith('{') -and $Trimmed.EndsWith('}')) -or
                ($Trimmed.StartsWith('[') -and $Trimmed.EndsWith(']'))
            ) {
                try {
                    $Nested = $Trimmed | ConvertFrom-Json -Depth 100

                    foreach ($NestedValue in @(
                        Get-RecursiveNamedValues `
                            -Value $Nested `
                            -Names @('message','error','text')
                    )) {
                        if (-not [string]::IsNullOrWhiteSpace([string]$NestedValue)) {
                            $Texts.Add([string]$NestedValue)
                        }
                    }
                }
                catch {
                }
            }
        }
    }

    return @($Texts | Select-Object -Unique)
}

Write-Host '=== HISTORICAL_HF06_ATTEMPT2_VERIFICATION ==='

foreach ($RequiredPath in @(
    $HF06,
    $HF06Auth,
    $ManifestPath,
    $AuthContextPath
)) {
    if (-not (Test-Path -LiteralPath $RequiredPath -PathType Leaf)) {
        throw "REQUIRED_FILE_MISSING=$RequiredPath"
    }
}

$HF06Hash = Get-FileSha256Local $HF06
$HF06Sig = Get-AuthenticodeSignature -FilePath $HF06
$HF06AuthHash = Get-FileSha256Local $HF06Auth
$ManifestHash = Get-FileSha256Local $ManifestPath
$AuthContextHash = Get-FileSha256Local $AuthContextPath

Write-Host "HF06_SOURCE_SHA256=$HF06Hash"
Write-Host "HF06_SIGNATURE_STATUS=$($HF06Sig.Status)"
Write-Host "HF06_AUTHORIZATION_SHA256=$HF06AuthHash"
Write-Host "PACKAGE_MANIFEST_SHA256=$ManifestHash"
Write-Host "AUTH_CONTEXT_SHA256=$AuthContextHash"

if ($HF06Hash -ne $ExpectedHF06Hash) {
    throw 'HF06_SOURCE_HASH_MISMATCH'
}
if ($HF06Sig.Status -ne 'Valid') {
    throw 'HF06_SIGNATURE_INVALID'
}
if ($HF06Sig.SignerCertificate.Thumbprint -ne $SignerThumbprint) {
    throw 'HF06_SIGNER_MISMATCH'
}
if ($HF06AuthHash -ne $ExpectedHF06AuthHash) {
    throw 'HF06_ATTEMPT2_AUTHORIZATION_HASH_MISMATCH'
}
if ($ManifestHash -ne $ExpectedManifestHash) {
    throw 'PACKAGE_MANIFEST_HASH_MISMATCH'
}
if ($AuthContextHash -ne $ExpectedAuthContextHash) {
    throw 'AUTH_CONTEXT_HASH_MISMATCH'
}

$Locks = @()
if (Test-Path -LiteralPath $HF06StateRoot -PathType Container) {
    $Locks = @(
        Get-ChildItem `
            -LiteralPath $HF06StateRoot `
            -File `
            -Filter 'PRE_MUTATION_SINGLE_USE_LOCK_HF06_*.json' `
            -ErrorAction SilentlyContinue
    )
}

if ($Locks.Count -ne 1) {
    throw "HF06_SINGLE_USE_LOCK_COUNT_INVALID=$($Locks.Count)"
}

$LockHash = Get-FileSha256Local $Locks[0].FullName
Write-Host "HF06_SINGLE_USE_LOCK_SHA256=$LockHash"

if ($LockHash -ne $ExpectedLockHash) {
    throw 'HF06_SINGLE_USE_LOCK_HASH_MISMATCH'
}

foreach ($ReceiptName in @(
    '20_EXECUTION_RECEIPT_CREATE_HF06.json',
    '21_EXECUTION_RECEIPT_ACTIVATE_HF06.json',
    '30_OUTCOME_RECEIPT_HF06.json',
    '99_LIVE_FINAL_RECEIPT_HF06.json',
    'AUTHORIZATION_CONSUMED_HF06.json'
)) {
    if (
        Test-Path `
            -LiteralPath (Join-Path $HF06StateRoot $ReceiptName) `
            -PathType Leaf
    ) {
        throw "UNEXPECTED_HF06_RECEIPT_PRESENT=$ReceiptName"
    }
}

Write-Host 'HF06_REPLAY_BLOCKED=TRUE'
Write-Host 'HF06_DO_NOT_RERUN=TRUE'
Write-Host 'HF06_AUTHORIZATION_REUSE_AUTHORIZED=FALSE'

Write-Host '=== FROZEN_LIVE_CONTRACT_RESOLUTION ==='

$HF06Text = Get-Content -LiteralPath $HF06 -Raw

$LiveRoleMatch = [regex]::Match(
    $HF06Text,
    'LiveMissionContract\s*=\s*"([^"]+)"'
)

if (-not $LiveRoleMatch.Success) {
    throw 'LIVE_MISSION_CONTRACT_ROLE_NOT_FOUND_IN_HF06'
}

$LiveRelativePath = $LiveRoleMatch.Groups[1].Value
$LivePath = Join-Path $PreparedRoot $LiveRelativePath

Write-Host "LIVE_MISSION_CONTRACT_RELATIVE_PATH=$LiveRelativePath"

if (-not (Test-Path -LiteralPath $LivePath -PathType Leaf)) {
    throw 'LIVE_MISSION_CONTRACT_FILE_NOT_FOUND'
}

$Manifest = Get-Content -LiteralPath $ManifestPath -Raw |
    ConvertFrom-Json -Depth 100

$ManifestEntries = @(
    $Manifest.files |
    Where-Object {
        [string]$_.file -eq $LiveRelativePath
    }
)

if ($ManifestEntries.Count -ne 1) {
    throw "LIVE_CONTRACT_MANIFEST_ENTRY_COUNT_INVALID=$($ManifestEntries.Count)"
}

$LiveHash = Get-FileSha256Local $LivePath
$ExpectedLiveHash = [string]$ManifestEntries[0].sha256

Write-Host "LIVE_MISSION_CONTRACT_SHA256=$LiveHash"

if ($LiveHash -ne $ExpectedLiveHash) {
    throw 'LIVE_MISSION_CONTRACT_HASH_MISMATCH'
}

$Live = Get-Content -LiteralPath $LivePath -Raw |
    ConvertFrom-Json -Depth 100

if ([string]$Live.object_name -ne $ObjectName) {
    throw 'LIVE_CONTRACT_OBJECT_MISMATCH'
}
if ([string]$Live.package -ne $Package) {
    throw 'LIVE_CONTRACT_PACKAGE_MISMATCH'
}
if ([string]$Live.provider -ne 'ADT') {
    throw 'LIVE_CONTRACT_PROVIDER_MISMATCH'
}

$ObjectContent = [string]$Live.object_content

if ([string]::IsNullOrWhiteSpace($ObjectContent)) {
    throw 'LIVE_CONTRACT_OBJECT_CONTENT_MISSING'
}

$ObjectContentHash = Get-TextSha256Local $ObjectContent

Write-Host "FROZEN_OBJECT_CONTENT_SHA256=$ObjectContentHash"
Write-Host 'FROZEN_OBJECT_CONTENT_RESOLVED=TRUE'

Write-Host '=== AUTH_CONTEXT_VERIFICATION ==='

$Context = Get-Content -LiteralPath $AuthContextPath -Raw |
    ConvertFrom-Json -Depth 100

if ([string]$Context.endpoint -ne $ExpectedEndpoint) {
    throw "ADT_MCP_ENDPOINT_UNEXPECTED=$($Context.endpoint)"
}
if ([string]$Context.protection -ne 'WINDOWS_DPAPI_CURRENT_USER') {
    throw 'AUTH_CONTEXT_PROTECTION_MISMATCH'
}

try {
    $Protected = [Convert]::FromBase64String(
        [string]$Context.protected_token_b64
    )

    $Plain = [Security.Cryptography.ProtectedData]::Unprotect(
        $Protected,
        $null,
        [Security.Cryptography.DataProtectionScope]::CurrentUser
    )

    $Token = [Text.Encoding]::UTF8.GetString($Plain)

    if ((Get-TextSha256Local $Token) -ne $ExpectedTokenHash) {
        throw 'ADT_TOKEN_HASH_MISMATCH'
    }

    Write-Host 'ADT_TOKEN_UNPROTECT=PASS'
    Write-Host 'ADT_TOKEN_HASH_MATCH=PASS'

    Write-Host '=== LIVE_READ_VALIDATION_RECONCILIATION ==='
    Write-Host 'MODE=BOUNDED_READ_AND_VALIDATION_ONLY'
    Write-Host 'SAP_WRITES_AUTHORIZED=FALSE'
    Write-Host 'CREATE_OBJECT_AUTHORIZED=FALSE'
    Write-Host 'ACTIVATE_OBJECTS_AUTHORIZED=FALSE'
    Write-Host 'HF06_AUTHORIZATION_REUSE_AUTHORIZED=FALSE'

    $Initialize = [ordered]@{
        jsonrpc = '2.0'
        id = 1
        method = 'initialize'
        params = [ordered]@{
            protocolVersion = $ProtocolVersion
            capabilities = [ordered]@{}
            clientInfo = [ordered]@{
                name = 'MCR_R1_9_B_HF06_CREATE_STATE_RECONCILIATION'
                version = '1.0.0'
            }
        }
    }

    $Init = Invoke-McpRequest `
        -Body $Initialize `
        -Label 'INITIALIZE'

    if ($null -eq $Init.result) {
        throw 'INITIALIZE_RESULT_MISSING'
    }

    $NegotiatedProtocol = [string]$Init.result.protocolVersion

    if (-not [string]::IsNullOrWhiteSpace($NegotiatedProtocol)) {
        $ProtocolVersion = $NegotiatedProtocol
    }

    if ([string]::IsNullOrWhiteSpace($SessionId)) {
        throw 'MCP_SESSION_ID_NOT_RETURNED'
    }

    Write-Host "MCP_SESSION_ID_CAPTURED=$(-not [string]::IsNullOrWhiteSpace($SessionId))"
    Write-Host "NEGOTIATED_PROTOCOL_VERSION=$ProtocolVersion"

    $Initialized = [ordered]@{
        jsonrpc = '2.0'
        method = 'notifications/initialized'
        params = [ordered]@{}
    }

    $null = Invoke-McpRequest `
        -Body $Initialized `
        -Label 'INITIALIZED_NOTIFICATION' `
        -AllowEmpty

    Write-Host 'INITIALIZED_NOTIFICATION=PASS'

    $ToolsListRequest = [ordered]@{
        jsonrpc = '2.0'
        id = 2
        method = 'tools/list'
        params = [ordered]@{}
    }

    $ToolsList = Invoke-McpRequest `
        -Body $ToolsListRequest `
        -Label 'TOOLS_LIST'

    $Tools = @($ToolsList.result.tools)
    $ToolNames = @($Tools | ForEach-Object { [string]$_.name })

    Write-Host "ADT_MCP_TOOL_COUNT=$($Tools.Count)"

    if ($Tools.Count -ne 20) {
        throw "ADT_MCP_TOOL_COUNT_DRIFT=$($Tools.Count)"
    }

    foreach ($RequiredTool in @(
        'abap_creation-get_object_type_details',
        'abap_creation-run_validation'
    )) {
        if ($ToolNames -notcontains $RequiredTool) {
            throw "REQUIRED_READ_VALIDATION_TOOL_MISSING=$RequiredTool"
        }
    }

    Write-Host 'REQUIRED_READ_VALIDATION_TOOLS_PRESENT=TRUE'

    $DetailsRequest = [ordered]@{
        jsonrpc = '2.0'
        id = 3
        method = 'tools/call'
        params = [ordered]@{
            name = 'abap_creation-get_object_type_details'
            arguments = [ordered]@{
                destination = $Destination
                objectType = $ObjectType
                name = $ObjectName
                description = 'MCR R1.9B governed mutation probe'
            }
        }
    }

    $SapRemoteReadCalls++

    $Details = Invoke-McpRequest `
        -Body $DetailsRequest `
        -Label 'GET_OBJECT_TYPE_DETAILS' `
        -IsToolCall

    $DetailsTexts = @(Get-ToolTextPayloads $Details)

    Write-Host "OBJECT_TYPE_DETAILS_TEXT_COUNT=$($DetailsTexts.Count)"
    Write-Host 'OBJECT_TYPE_DETAILS_CALL=PASS'

    $ValidationRequest = [ordered]@{
        jsonrpc = '2.0'
        id = 4
        method = 'tools/call'
        params = [ordered]@{
            name = 'abap_creation-run_validation'
            arguments = [ordered]@{
                destination = $Destination
                objectType = $ObjectType
                objectContent = $ObjectContent
            }
        }
    }

    $SapRemoteValidationCalls++

    $Validation = Invoke-McpRequest `
        -Body $ValidationRequest `
        -Label 'RUN_VALIDATION' `
        -IsToolCall

    $ValidationTexts = @(Get-ToolTextPayloads $Validation)
    $ValidationText = ($ValidationTexts -join ' | ').Trim()

    Write-Host "VALIDATION_TEXT_COUNT=$($ValidationTexts.Count)"

    if ([string]::IsNullOrWhiteSpace($ValidationText)) {
        $ValidationText = (
            $Validation | ConvertTo-Json -Depth 100 -Compress
        )
    }

    $EvidenceValidationText = $ValidationText

    if ($EvidenceValidationText.Length -gt 4000) {
        $EvidenceValidationText = $EvidenceValidationText.Substring(0,4000)
    }

    [System.IO.File]::WriteAllText(
        (Join-Path $EvidenceRoot '06_NORMALIZED_VALIDATION_TEXT.txt'),
        $EvidenceValidationText,
        $Utf8NoBom
    )

    $Lower = $ValidationText.ToLowerInvariant()

    $ExistsPattern = (
        'already\s+exists|' +
        'already\s+exist|' +
        'exists\s+already|' +
        'object.{0,80}exists|' +
        'name.{0,80}exists|' +
        'duplicate|' +
        'collision|' +
        'is\s+already\s+used'
    )

    $SuccessPattern = (
        'validation.{0,40}(successful|success|passed)|' +
        '(successful|successfully).{0,40}validat|' +
        'no\s+(validation\s+)?errors|' +
        'input.{0,40}valid'
    )

    $ErrorValues = @(
        Get-RecursiveNamedValues `
            -Value $Validation `
            -Names @('error')
    ) |
        Where-Object {
            -not [string]::IsNullOrWhiteSpace([string]$_)
        }

    $ExistenceConflict = [regex]::IsMatch(
        $Lower,
        $ExistsPattern,
        [Text.RegularExpressions.RegexOptions]::IgnoreCase
    )

    $PositiveValidation = [regex]::IsMatch(
        $Lower,
        $SuccessPattern,
        [Text.RegularExpressions.RegexOptions]::IgnoreCase
    )

    $HasExplicitError = $ErrorValues.Count -gt 0

    if ($ExistenceConflict) {
        $Reconciliation = 'CREATE_COMMIT_SUPPORTED_BY_CREATION_COLLISION_SIGNAL'
        $ObjectStateInference = 'LIKELY_EXISTS'
    }
    elseif ($PositiveValidation -and -not $HasExplicitError) {
        $Reconciliation = 'CREATE_COMMIT_NOT_SUPPORTED_BY_PREFLIGHT_VALIDATION'
        $ObjectStateInference = 'LIKELY_ABSENT_OR_CREATE_STILL_ADMISSIBLE'
    }
    else {
        $Reconciliation = 'CREATE_COMMIT_REMAINS_UNKNOWN'
        $ObjectStateInference = 'UNKNOWN'
    }

    Write-Host "VALIDATION_EXPLICIT_ERROR_COUNT=$($ErrorValues.Count)"
    Write-Host "EXISTENCE_CONFLICT_SIGNAL=$ExistenceConflict"
    Write-Host "POSITIVE_VALIDATION_SIGNAL=$PositiveValidation"
    Write-Host "CREATE_STATE_RECONCILIATION=$Reconciliation"
    Write-Host "OBJECT_STATE_INFERENCE=$ObjectStateInference"
}
finally {
    if ($null -ne $Plain) {
        [Array]::Clear($Plain,0,$Plain.Length)
    }

    if ($null -ne $Protected) {
        [Array]::Clear($Protected,0,$Protected.Length)
    }

    $Token = $null
    $SessionId = $null
}

$Result = [ordered]@{
    mission = 'MCR_R1_9_B_HF06_ATTEMPT2_CREATE_STATE_PREFLIGHT_RECONCILIATION_R1'

    historical_attempt = [ordered]@{
        hf06_source_sha256 = $HF06Hash
        hf06_authorization_sha256 = $HF06AuthHash
        single_use_lock_sha256 = $LockHash
        replay_blocked = $true
        do_not_rerun = $true
    }

    frozen_contract = [ordered]@{
        target = $Destination
        object_name = $ObjectName
        object_type = $ObjectType
        package = $Package
        live_contract_relative_path = $LiveRelativePath
        live_contract_sha256 = $LiveHash
        object_content_sha256 = $ObjectContentHash
    }

    bounded_live_calls = [ordered]@{
        provider_protocol_calls = $ProviderCalls
        tools_call_requests = $ToolCallRequests
        sap_remote_read_calls = $SapRemoteReadCalls
        sap_remote_validation_calls = $SapRemoteValidationCalls
        sap_writes = $SapWrites
    }

    reconciliation = [ordered]@{
        method = 'CREATION_PREFLIGHT_SECONDARY_SIGNAL'
        create_commit_state = $Reconciliation
        object_state_inference = $ObjectStateInference
        existence_conflict_signal = $ExistenceConflict
        positive_validation_signal = $PositiveValidation
        explicit_error_count = $ErrorValues.Count
        authoritative_repository_readback = $false
    }

    authority = [ordered]@{
        historical_hf06_authorization_reusable = $false
        live_sap_write_authorized = $false
        create_authorized = $false
        activation_authorized = $false
        compensation_authorized = $false
        cleanup_delete_authorized = $false
    }
}

$ResultPath = Join-Path $EvidenceRoot '07_RESULT_R1.json'

Write-JsonEvidence `
    -Path $ResultPath `
    -Object $Result

if ($Reconciliation -eq 'CREATE_COMMIT_SUPPORTED_BY_CREATION_COLLISION_SIGNAL') {
    $NextState = 'CREATE_LIKELY_COMMITTED_READBACK_OR_CONTINUATION_DESIGN_REQUIRED'
}
elseif ($Reconciliation -eq 'CREATE_COMMIT_NOT_SUPPORTED_BY_PREFLIGHT_VALIDATION') {
    $NextState = 'CREATE_LIKELY_NOT_COMMITTED_NEW_GOVERNED_EXECUTION_DESIGN_REQUIRED'
}
else {
    $NextState = 'CREATE_COMMIT_UNKNOWN_FURTHER_READ_ONLY_RECONCILIATION_REQUIRED'
}

Write-Host '=== FINAL ==='
Write-Host 'MCR_R1_9_B_HF06_ATTEMPT2_CREATE_STATE_PREFLIGHT_RECONCILIATION=PASS'
Write-Host 'HF06_DO_NOT_RERUN=TRUE'
Write-Host 'HF06_REPLAY_BLOCKED=TRUE'
Write-Host "CREATE_STATE_RECONCILIATION=$Reconciliation"
Write-Host "OBJECT_STATE_INFERENCE=$ObjectStateInference"
Write-Host 'AUTHORITATIVE_REPOSITORY_READBACK=FALSE'
Write-Host "MCP_PROTOCOL_PROVIDER_CALLS=$ProviderCalls"
Write-Host "MCP_TOOLS_CALL_REQUESTS=$ToolCallRequests"
Write-Host "SAP_REMOTE_READ_CALLS=$SapRemoteReadCalls"
Write-Host "SAP_REMOTE_VALIDATION_CALLS=$SapRemoteValidationCalls"
Write-Host 'SAP_WRITES=0'
Write-Host 'HF06_AUTHORIZATION_REUSE_AUTHORIZED=FALSE'
Write-Host 'LIVE_SAP_WRITE_AUTHORIZED=FALSE'
Write-Host "FINAL_STATE=$NextState"

# SIG # Begin signature block
# MIIHMAYJKoZIhvcNAQcCoIIHITCCBx0CAQExDzANBglghkgBZQMEAgEFADB5Bgor
# BgEEAYI3AgEEoGswaTA0BgorBgEEAYI3AgEeMCYCAwEAAAQQH8w7YFlLCE63JNLG
# KX7zUQIBAAIBAAIBAAIBAAIBADAxMA0GCWCGSAFlAwQCAQUABCAvAykkkKCVTqNa
# C9pYWNiwXtQym2W8P0sK7xV84HKTD6CCBBwwggQYMIICgKADAgECAhApojSr80YY
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
# MC8GCSqGSIb3DQEJBDEiBCARfm3SMF2EP/lc1VW0Y2Z/odNevSdTCYizf0eh26pp
# wjANBgkqhkiG9w0BAQEFAASCAYAAezshyzuavxpq4lKIjvwrNylWw2fkNumF2rkF
# CWZZlRgrZZb0/V+Cp6MB2SHiM1tmPQyMsrodlpxwRzhd/hmfQZyoe9off8T5XZXq
# /DWIUxQ4j7wR/m5giVCg7dZ1lkz9ussMk5tTTdCjXpTY/7ZXralGR4rlIobC8/D0
# Z9HLxK2qMRI8PYQjhPCzEkCaHckcJNWykqE87DMCMZ9aGMpRnkVWXoKGOWVl24Pm
# 7ftLizj6nvdHxhI/8e/cVG1aeFWO2f19K0vlm1SHolyLTdamohjyvp08RoDNoPgD
# RjpcKK/rxVeS1YipbPi7wx8AD4F4GhzF0+s+opwC6fjXdHslWbnJml+1Z0GNoscR
# DJcl9UrsHR1+MvLPZ3KsSA035sC2eHLa8rWF2bmvsREU24Vcxd/ynf5MAFleMH02
# yTb3+pL8Mvql3SfGWbiTjRcjp1ja86SZQP/LnLs7Om5z6YRPZQbkIiHAjdg4Cg9k
# Qu9ST2zVCUZr1YczFVrgWKjrYvk=
# SIG # End signature block
