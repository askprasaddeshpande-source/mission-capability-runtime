[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# ============================================================
# MCR R1.9B
# HF05 FAILURE FORENSIC + ADT MCP SESSION HANDSHAKE QUALIFICATION
#
# READ/PROTOCOL ONLY
# NO tools/call
# NO SAP READ
# NO SAP WRITE
# NO AUTHORIZATION CREATION
# NO HF05 RERUN
# ============================================================

$Root = 'D:\MCP'

$HF05 = Join-Path $Root 'Run-MCR-R1.9B-Live-Governed-Mutation-And-Outcome-R1-HF05.ps1'
$HF05Auth = Join-Path $Root 'MCR_R1_9_B_LIVE_WRITE_AUTHORIZATION_HF05.json'
$StateRoot = Join-Path $Root 'MCR_R1_9_B_LIVE_GOVERNED_MUTATION_AND_OUTCOME_R1_HF05_STATE'
$AuthContextPath = Join-Path $Root 'MCR_R2E_P8_C1A_ADT_AUTH_BINDING_PROBE_R1\ADT_AUTH_CONTEXT_R1.json'
$EvidenceRoot = Join-Path $Root 'MCR_R1_9_B_HF05_SESSION_PROTOCOL_FORENSIC_R1'

$ExpectedHF05Hash = 'E9FC41C4995B8C11C594F3253BEF4AA6EA8F0A2D37714B8D17ADC1717497E17D'
$ExpectedHF05AuthHash = 'C176422D76BCE82084403CFE8460ACA15125DBD4852C3BF1D9562BB2C44350A9'
$ExpectedAuthContextHash = '155D6B0DA47E1DDD85C1F9A1F08786192BA76ED103759A8E53D88712A2D89863'
$ExpectedTokenHash = 'F0DFD22C22C18E40913147DC39E674E29F3170D40C298C1A417827A44891B0EE'
$SignerThumbprint = '9E8E489FF6F727188EBA3EFECA1381A42A9938C6'

$ProtocolVersion = '2025-06-18'
$EndpointExpected = 'http://127.0.0.1:2236/mcp'

$ProviderCalls = 0
$ToolCalls = 0
$SapReads = 0
$SapWrites = 0
$SessionId = $null
$Token = $null
$Plain = $null
$Protected = $null

New-Item -ItemType Directory -Path $EvidenceRoot -Force | Out-Null

function Get-FileSha256 {
    param([Parameter(Mandatory=$true)][string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}

function Get-TextSha256 {
    param([Parameter(Mandatory=$true)][string]$Text)
    $Sha = [Security.Cryptography.SHA256]::Create()
    try {
        return [BitConverter]::ToString(
            $Sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($Text))
        ).Replace('-','')
    }
    finally {
        $Sha.Dispose()
    }
}

function Convert-McpContent {
    param([AllowNull()][string]$Content)

    if ([string]::IsNullOrWhiteSpace($Content)) {
        return $null
    }

    $Trimmed = $Content.Trim()

    if ($Trimmed.StartsWith('{') -or $Trimmed.StartsWith('[')) {
        return ($Trimmed | ConvertFrom-Json)
    }

    foreach ($Line in ($Content -split "`r?`n")) {
        $Candidate = $Line.Trim()

        if ($Candidate.StartsWith('data:', [StringComparison]::OrdinalIgnoreCase)) {
            $Json = $Candidate.Substring(5).Trim()

            if (-not [string]::IsNullOrWhiteSpace($Json) -and $Json -ne '[DONE]') {
                try {
                    return ($Json | ConvertFrom-Json)
                }
                catch {
                }
            }
        }
    }

    throw 'MCP_RESPONSE_NOT_JSON_OR_SSE'
}

function Invoke-ProtocolRequest {
    param(
        [Parameter(Mandatory=$true)][hashtable]$Body,
        [Parameter(Mandatory=$true)][string]$Label,
        [switch]$AllowEmpty
    )

    $script:ProviderCalls++

    $Headers = @{
        Authorization = "Bearer $script:Token"
        Accept = 'application/json, text/event-stream'
        'MCP-Protocol-Version' = $script:ProtocolVersion
    }

    if (-not [string]::IsNullOrWhiteSpace($script:SessionId)) {
        $Headers['Mcp-Session-Id'] = $script:SessionId
    }

    $JsonBody = $Body | ConvertTo-Json -Depth 100 -Compress

    $Response = Invoke-WebRequest `
        -Uri $script:EndpointExpected `
        -Method Post `
        -Headers $Headers `
        -ContentType 'application/json' `
        -Body $JsonBody `
        -TimeoutSec 30

    if ($Response.Headers.ContainsKey('Mcp-Session-Id')) {
        $Sid = [string]$Response.Headers['Mcp-Session-Id']

        if (-not [string]::IsNullOrWhiteSpace($Sid)) {
            $script:SessionId = $Sid
        }
    }

    $EvidencePath = Join-Path $script:EvidenceRoot ("{0}_{1}.txt" -f $script:ProviderCalls,$Label)

    @(
        "LABEL=$Label"
        "HTTP_STATUS=$([int]$Response.StatusCode)"
        "MCP_SESSION_ID_PRESENT=$(-not [string]::IsNullOrWhiteSpace($script:SessionId))"
        "CONTENT_TYPE=$([string]$Response.Headers['Content-Type'])"
        ''
        [string]$Response.Content
    ) | Set-Content -LiteralPath $EvidencePath -Encoding UTF8

    if ([string]::IsNullOrWhiteSpace([string]$Response.Content)) {
        if ($AllowEmpty) {
            return $null
        }

        throw "EMPTY_MCP_RESPONSE=$Label"
    }

    $Parsed = Convert-McpContent -Content ([string]$Response.Content)

    if ($null -ne $Parsed -and $null -ne $Parsed.PSObject.Properties['error']) {
        throw ("MCP_JSONRPC_ERROR:{0}:{1}" -f $Label,($Parsed.error | ConvertTo-Json -Compress))
    }

    return $Parsed
}

Write-Host '=== HISTORICAL_HF05_VERIFICATION ==='

if (-not (Test-Path -LiteralPath $HF05 -PathType Leaf)) {
    throw 'HF05_SOURCE_NOT_FOUND'
}

if (-not (Test-Path -LiteralPath $HF05Auth -PathType Leaf)) {
    throw 'HF05_AUTHORIZATION_NOT_FOUND'
}

$HF05Hash = Get-FileSha256 $HF05
$HF05Sig = Get-AuthenticodeSignature -FilePath $HF05
$HF05AuthHash = Get-FileSha256 $HF05Auth

Write-Host "HF05_SOURCE_SHA256=$HF05Hash"
Write-Host "HF05_SIGNATURE_STATUS=$($HF05Sig.Status)"
Write-Host "HF05_AUTHORIZATION_SHA256=$HF05AuthHash"

if ($HF05Hash -ne $ExpectedHF05Hash) {
    throw 'HF05_SOURCE_HASH_MISMATCH'
}

if ($HF05Sig.Status -ne 'Valid') {
    throw 'HF05_SIGNATURE_INVALID'
}

if ($HF05Sig.SignerCertificate.Thumbprint -ne $SignerThumbprint) {
    throw 'HF05_SIGNER_MISMATCH'
}

if ($HF05AuthHash -ne $ExpectedHF05AuthHash) {
    throw 'HF05_AUTHORIZATION_HASH_MISMATCH'
}

$ConsumedMarker = Join-Path $StateRoot 'AUTHORIZATION_CONSUMED_HF05.json'
$CreateReceipt = Join-Path $StateRoot '20_EXECUTION_RECEIPT_CREATE_HF05.json'
$ActivateReceipt = Join-Path $StateRoot '21_EXECUTION_RECEIPT_ACTIVATE_HF05.json'
$OutcomeReceipt = Join-Path $StateRoot '30_OUTCOME_RECEIPT_HF05.json'
$FinalReceipt = Join-Path $StateRoot '99_LIVE_FINAL_RECEIPT_HF05.json'

Write-Host "HF05_CREATE_RECEIPT_EXISTS=$(Test-Path -LiteralPath $CreateReceipt -PathType Leaf)"
Write-Host "HF05_ACTIVATE_RECEIPT_EXISTS=$(Test-Path -LiteralPath $ActivateReceipt -PathType Leaf)"
Write-Host "HF05_OUTCOME_RECEIPT_EXISTS=$(Test-Path -LiteralPath $OutcomeReceipt -PathType Leaf)"
Write-Host "HF05_FINAL_RECEIPT_EXISTS=$(Test-Path -LiteralPath $FinalReceipt -PathType Leaf)"
Write-Host "HF05_AUTHORIZATION_CONSUMED_EXISTS=$(Test-Path -LiteralPath $ConsumedMarker -PathType Leaf)"

if (Test-Path -LiteralPath $CreateReceipt -PathType Leaf) {
    throw 'UNEXPECTED_CREATE_RECEIPT_PRESENT_REVIEW_REQUIRED'
}

if (Test-Path -LiteralPath $ActivateReceipt -PathType Leaf) {
    throw 'UNEXPECTED_ACTIVATE_RECEIPT_PRESENT_REVIEW_REQUIRED'
}

if (Test-Path -LiteralPath $OutcomeReceipt -PathType Leaf) {
    throw 'UNEXPECTED_OUTCOME_RECEIPT_PRESENT_REVIEW_REQUIRED'
}

if (Test-Path -LiteralPath $FinalReceipt -PathType Leaf) {
    throw 'UNEXPECTED_FINAL_RECEIPT_PRESENT_REVIEW_REQUIRED'
}

if (Test-Path -LiteralPath $ConsumedMarker -PathType Leaf) {
    throw 'UNEXPECTED_AUTHORIZATION_CONSUMED_MARKER_PRESENT_REVIEW_REQUIRED'
}

Write-Host 'HF05_HISTORICAL_LIVE_ATTEMPT_MUTATION_REACH=FALSE'
Write-Host 'HF05_DO_NOT_RERUN=TRUE'

Write-Host '=== SESSION_PROTOCOL_FORENSIC ==='

$HF05Text = Get-Content -LiteralPath $HF05 -Raw

$CapturesSession = (
    $HF05Text -match 'Mcp-Session-Id' -and
    $HF05Text -match 'Response\.Headers'
)

$SendsInitializedNotification = (
    $HF05Text -match 'notifications/initialized'
)

Write-Host "HF05_CAPTURES_SESSION_ID=$CapturesSession"
Write-Host "HF05_SENDS_INITIALIZED_NOTIFICATION=$SendsInitializedNotification"

if ($CapturesSession) {
    throw 'HF05_SESSION_CAPTURE_UNEXPECTEDLY_PRESENT_REVIEW_REQUIRED'
}

if ($SendsInitializedNotification) {
    throw 'HF05_INITIALIZED_NOTIFICATION_UNEXPECTEDLY_PRESENT_REVIEW_REQUIRED'
}

Write-Host 'ROOT_CAUSE_1=HF05_DID_NOT_CAPTURE_AND_PROPAGATE_MCP_SESSION_ID'
Write-Host 'ROOT_CAUSE_2=HF05_DID_NOT_SEND_NOTIFICATIONS_INITIALIZED'

Write-Host '=== AUTH_CONTEXT_VERIFICATION ==='

if (-not (Test-Path -LiteralPath $AuthContextPath -PathType Leaf)) {
    throw 'ADT_AUTH_CONTEXT_NOT_FOUND'
}

$AuthContextHash = Get-FileSha256 $AuthContextPath
Write-Host "AUTH_CONTEXT_SHA256=$AuthContextHash"

if ($AuthContextHash -ne $ExpectedAuthContextHash) {
    throw 'AUTH_CONTEXT_HASH_MISMATCH'
}

$Context = Get-Content -LiteralPath $AuthContextPath -Raw | ConvertFrom-Json

if ($null -eq $Context.PSObject.Properties['endpoint']) {
    throw 'AUTH_CONTEXT_ENDPOINT_MISSING'
}

$Endpoint = [string]$Context.endpoint
Write-Host "ADT_MCP_ENDPOINT=$Endpoint"

if ($Endpoint -ne $EndpointExpected) {
    throw "ADT_MCP_ENDPOINT_UNEXPECTED=$Endpoint"
}

if ([string]$Context.protection -ne 'WINDOWS_DPAPI_CURRENT_USER') {
    throw 'AUTH_CONTEXT_PROTECTION_MISMATCH'
}

try {
    $Protected = [Convert]::FromBase64String([string]$Context.protected_token_b64)

    $Plain = [Security.Cryptography.ProtectedData]::Unprotect(
        $Protected,
        $null,
        [Security.Cryptography.DataProtectionScope]::CurrentUser
    )

    $Token = [Text.Encoding]::UTF8.GetString($Plain)

    if ((Get-TextSha256 $Token) -ne $ExpectedTokenHash) {
        throw 'ADT_TOKEN_HASH_MISMATCH'
    }

    Write-Host 'ADT_TOKEN_UNPROTECT=PASS'
    Write-Host 'ADT_TOKEN_HASH_MATCH=PASS'

    Write-Host '=== LIVE_SESSION_HANDSHAKE_QUALIFICATION ==='
    Write-Host 'MODE=PROTOCOL_ONLY_NO_TOOLS_CALL'
    Write-Host 'SAP_WRITES_AUTHORIZED=FALSE'
    Write-Host 'HF05_WRITE_AUTHORIZATION_REUSABLE=FALSE'

    $Initialize = @{
        jsonrpc = '2.0'
        id = 1
        method = 'initialize'
        params = @{
            protocolVersion = $ProtocolVersion
            capabilities = @{}
            clientInfo = @{
                name = 'mcr-r1.9b-session-handshake-forensic-r1'
                version = '1.0.0'
            }
        }
    }

    $Init = Invoke-ProtocolRequest -Body $Initialize -Label 'INITIALIZE'

    if ($null -eq $Init.result) {
        throw 'INITIALIZE_RESULT_MISSING'
    }

    if ($null -ne $Init.result.protocolVersion) {
        $ProtocolVersion = [string]$Init.result.protocolVersion
    }

    Write-Host "INITIALIZE_PROTOCOL_VERSION=$ProtocolVersion"
    Write-Host "MCP_SESSION_ID_CAPTURED=$(-not [string]::IsNullOrWhiteSpace($SessionId))"

    if ([string]::IsNullOrWhiteSpace($SessionId)) {
        throw 'MCP_SESSION_ID_NOT_RETURNED_BY_INITIALIZE'
    }

    $InitializedNotification = @{
        jsonrpc = '2.0'
        method = 'notifications/initialized'
        params = @{}
    }

    $null = Invoke-ProtocolRequest `
        -Body $InitializedNotification `
        -Label 'INITIALIZED_NOTIFICATION' `
        -AllowEmpty

    Write-Host 'INITIALIZED_NOTIFICATION=PASS'

    $ToolsListRequest = @{
        jsonrpc = '2.0'
        id = 2
        method = 'tools/list'
        params = @{}
    }

    $ToolsList = Invoke-ProtocolRequest -Body $ToolsListRequest -Label 'TOOLS_LIST'

    if ($null -eq $ToolsList.result -or $null -eq $ToolsList.result.tools) {
        throw 'TOOLS_LIST_RESULT_MISSING'
    }

    $Tools = @($ToolsList.result.tools)
    $ToolNames = @($Tools | ForEach-Object { [string]$_.name })

    Write-Host "ADT_MCP_TOOL_COUNT=$($Tools.Count)"

    if ($Tools.Count -ne 20) {
        throw "ADT_MCP_TOOL_COUNT_DRIFT=$($Tools.Count)"
    }

    foreach ($Required in @(
        'abap_creation-create_object',
        'abap_activate_objects',
        'abap_atc_run',
        'abap_atc_get_result'
    )) {
        if ($ToolNames -notcontains $Required) {
            throw "REQUIRED_TOOL_MISSING=$Required"
        }
    }

    Write-Host 'REQUIRED_HF05_TOOLS_PRESENT=TRUE'
}
finally {
    if ($null -ne $Plain) {
        [Array]::Clear($Plain,0,$Plain.Length)
    }

    if ($null -ne $Protected) {
        [Array]::Clear($Protected,0,$Protected.Length)
    }

    $Token = $null
}

$Result = [ordered]@{
    mission = 'MCR_R1_9_B_HF05_SESSION_PROTOCOL_FORENSIC_R1'
    historical_hf05 = [ordered]@{
        source_sha256 = $HF05Hash
        authorization_sha256 = $HF05AuthHash
        authorization_consumed = $false
        mutation_reach = $false
        do_not_rerun = $true
    }
    root_causes = @(
        'HF05_DID_NOT_CAPTURE_AND_PROPAGATE_MCP_SESSION_ID',
        'HF05_DID_NOT_SEND_NOTIFICATIONS_INITIALIZED'
    )
    live_protocol_qualification = [ordered]@{
        initialize = 'PASS'
        session_id_captured = $true
        initialized_notification = 'PASS'
        tools_list = 'PASS'
        tool_count = 20
        required_tools_present = $true
        provider_calls = $ProviderCalls
        tools_call_requests = $ToolCalls
        sap_reads = $SapReads
        sap_writes = $SapWrites
    }
    next_state = 'HF06_SESSION_AWARE_RUNNER_REPAIR_REQUIRED'
}

$ResultPath = Join-Path $EvidenceRoot '01_HF05_SESSION_PROTOCOL_FORENSIC_R1.json'
$Result | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $ResultPath -Encoding UTF8

Write-Host '=== FINAL ==='
Write-Host 'MCR_R1_9_B_HF05_SESSION_PROTOCOL_FORENSIC=PASS'
Write-Host 'ROOT_CAUSE_1=HF05_DID_NOT_CAPTURE_AND_PROPAGATE_MCP_SESSION_ID'
Write-Host 'ROOT_CAUSE_2=HF05_DID_NOT_SEND_NOTIFICATIONS_INITIALIZED'
Write-Host 'INITIALIZE=PASS'
Write-Host 'MCP_SESSION_ID_CAPTURED=TRUE'
Write-Host 'INITIALIZED_NOTIFICATION=PASS'
Write-Host 'TOOLS_LIST=PASS'
Write-Host 'ADT_MCP_TOOL_COUNT=20'
Write-Host 'REQUIRED_HF05_TOOLS_PRESENT=TRUE'
Write-Host "MCP_PROTOCOL_PROVIDER_CALLS=$ProviderCalls"
Write-Host 'MCP_TOOLS_CALL_REQUESTS=0'
Write-Host 'SAP_READS=0'
Write-Host 'SAP_WRITES=0'
Write-Host 'OBJECT_CREATED=FALSE'
Write-Host 'HF05_WRITE_AUTHORIZATION_REUSABLE=FALSE'
Write-Host 'LIVE_SAP_WRITE_AUTHORIZED=FALSE'
Write-Host 'FINAL_STATE=HF06_SESSION_AWARE_RUNNER_REPAIR_REQUIRED'

# SIG # Begin signature block
# MIIHMAYJKoZIhvcNAQcCoIIHITCCBx0CAQExDzANBglghkgBZQMEAgEFADB5Bgor
# BgEEAYI3AgEEoGswaTA0BgorBgEEAYI3AgEeMCYCAwEAAAQQH8w7YFlLCE63JNLG
# KX7zUQIBAAIBAAIBAAIBAAIBADAxMA0GCWCGSAFlAwQCAQUABCABxJ4sJu64QN7P
# 03jfbLtzR0713G5HoCeapjIS8eZMvKCCBBwwggQYMIICgKADAgECAhApojSr80YY
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
# MC8GCSqGSIb3DQEJBDEiBCBTunm4Hflf7Xp/AmKyglROilrta/HHMj5jJcgAMa+m
# dDANBgkqhkiG9w0BAQEFAASCAYAC478xTlmK7AYh/AzfFoiFTx9w13PI/48g2DHW
# IXFG4eia7jirufztIW/rNVGexbkVBzl/rP7mjQgjpiAFSmMRLgIbWeNanKoZKgd2
# /aQ1H23pfu/raZqe3vMOVSrapza16rDadsHZrVlg/y6BWc1TbMJpdL1IjYBZN8LJ
# TkXj4OYWT2EeSDyE4oOvVRDEMoaZtgbA5StiKLgOCmkbsWeFG2d0s3o/8ptRvZAe
# WMNLILKseMEsiQoIj7ff78hd+aep5Pkf2kwtJZ5VBYjPq+FkYMYrwevvSXgdnn61
# GWaK4F/0vFyGKpNDMzubF48Ag5xG4VkAVI5CdOEFDiP6oNA2AbLjm55AywJJ/sqk
# tlpG0LByc8UpoCFzjxtTbVGN0Gw8pKSIEUEynahqLDxKnYAkFA+lkWQqJCX3sqEA
# e/vVsil4uJDJ9SwYVt0RGDDWYN6oqq7ZNK8oIQup+3MtdU6IUaoB8HZsqroknioW
# GzH3xG9yMv8CWtLsmtAs3gqDuZs=
# SIG # End signature block
