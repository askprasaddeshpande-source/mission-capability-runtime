[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$Root = 'D:\MCP'
$EvidenceRoot = Join-Path $Root 'MCR_R1_9_B_HF06_ATTEMPT2_CREATE_STATE_PREFLIGHT_RECONCILIATION_R1'
$HF06 = Join-Path $Root 'Run-MCR-R1.9B-Live-Governed-Mutation-And-Outcome-R1-HF06.ps1'
$HF06Auth = Join-Path $Root 'MCR_R1_9_B_LIVE_WRITE_AUTHORIZATION_HF06.json'
$HF06StateRoot = Join-Path $Root 'MCR_R1_9_B_LIVE_GOVERNED_MUTATION_AND_OUTCOME_R1_HF06_STATE'
$BrokenScript = Join-Path $Root 'Run-MCR-R1.9B-HF06-Attempt2-Create-State-Preflight-Reconciliation-R1.ps1'
$ValidationRawPath = Join-Path $EvidenceRoot '05_RUN_VALIDATION_RAW_RESPONSE.txt'
$DetailsRawPath = Join-Path $EvidenceRoot '04_GET_OBJECT_TYPE_DETAILS_RAW_RESPONSE.txt'

$ExpectedHF06Hash = 'DE183ABC47B8F025ED60CFE5CFEA4527585FB20154C949628BDE95E42A0D3C88'
$ExpectedAuthHash = 'CC06B59F341E9B70844F7BEE48F6917303C094206431C228575F91E4500B9E09'
$ExpectedLockHash = 'DFE129A6D66656B4477B1693D5073CD17B40918516DCF725A6193C019B7BB275'
$ExpectedBrokenScriptHash = '504119748D25232EA47063642A9A6F73681986005B35735D51EC4333DF10A4FD'
$SignerThumbprint = '9E8E489FF6F727188EBA3EFECA1381A42A9938C6'
$Utf8NoBom = [System.Text.UTF8Encoding]::new($false)

function Get-Sha([string]$Path) {
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}

function Convert-McpContent([string]$Content) {
    if ([string]::IsNullOrWhiteSpace($Content)) { throw 'RAW_MCP_RESPONSE_EMPTY' }
    $t = $Content.Trim()
    if ($t.StartsWith('{') -or $t.StartsWith('[')) {
        return ($t | ConvertFrom-Json -Depth 100)
    }
    foreach ($line in ($Content -split "`r?`n")) {
        $c = $line.Trim()
        if ($c.StartsWith('data:', [StringComparison]::OrdinalIgnoreCase)) {
            $j = $c.Substring(5).Trim()
            if ($j -and $j -ne '[DONE]') {
                try { return ($j | ConvertFrom-Json -Depth 100) } catch {}
            }
        }
    }
    throw 'RAW_MCP_RESPONSE_NOT_JSON_OR_SSE'
}

function Collect-Text($Node) {
    $out = New-Object System.Collections.Generic.List[string]
    function Visit($x) {
        if ($null -eq $x) { return }
        if ($x -is [string]) { return }
        if ($x -is [System.Collections.IDictionary]) {
            foreach ($k in $x.Keys) {
                $v = $x[$k]
                if (@('message','error','text') -contains ([string]$k).ToLowerInvariant()) {
                    if ($null -ne $v) { $out.Add([string]$v) }
                }
                Visit $v
            }
            return
        }
        if ($x -is [System.Collections.IEnumerable] -and -not ($x -is [string])) {
            foreach ($i in $x) { Visit $i }
            return
        }
        foreach ($p in $x.PSObject.Properties) {
            $v = $p.Value
            if (@('message','error','text') -contains ([string]$p.Name).ToLowerInvariant()) {
                if ($null -ne $v) { $out.Add([string]$v) }
            }
            Visit $v
        }
    }
    Visit $Node
    return @($out | Select-Object -Unique)
}

Write-Host '=== INPUT_VERIFICATION ==='

foreach ($p in @($HF06,$HF06Auth,$BrokenScript,$ValidationRawPath,$DetailsRawPath)) {
    if (-not (Test-Path -LiteralPath $p -PathType Leaf)) { throw "REQUIRED_EVIDENCE_MISSING=$p" }
}

$hf06Hash = Get-Sha $HF06
$hf06Sig = Get-AuthenticodeSignature -FilePath $HF06
$authHash = Get-Sha $HF06Auth
$brokenHash = Get-Sha $BrokenScript
$validationRawHash = Get-Sha $ValidationRawPath
$detailsRawHash = Get-Sha $DetailsRawPath

Write-Host "HF06_SOURCE_SHA256=$hf06Hash"
Write-Host "HF06_SIGNATURE_STATUS=$($hf06Sig.Status)"
Write-Host "HF06_AUTHORIZATION_SHA256=$authHash"
Write-Host "BROKEN_RECONCILIATION_SIGNED_SHA256=$brokenHash"
Write-Host "VALIDATION_RAW_SHA256=$validationRawHash"
Write-Host "DETAILS_RAW_SHA256=$detailsRawHash"

if ($hf06Hash -ne $ExpectedHF06Hash) { throw 'HF06_SOURCE_HASH_MISMATCH' }
if ($hf06Sig.Status -ne 'Valid') { throw 'HF06_SIGNATURE_INVALID' }
if ($hf06Sig.SignerCertificate.Thumbprint -ne $SignerThumbprint) { throw 'HF06_SIGNER_MISMATCH' }
if ($authHash -ne $ExpectedAuthHash) { throw 'HF06_AUTHORIZATION_HASH_MISMATCH' }
if ($brokenHash -ne $ExpectedBrokenScriptHash) { throw 'BROKEN_RECONCILIATION_SCRIPT_HASH_MISMATCH' }

$locks = @()
if (Test-Path -LiteralPath $HF06StateRoot -PathType Container) {
    $locks = @(Get-ChildItem -LiteralPath $HF06StateRoot -File -Filter 'PRE_MUTATION_SINGLE_USE_LOCK_HF06_*.json' -ErrorAction SilentlyContinue)
}
if ($locks.Count -ne 1) { throw "HF06_SINGLE_USE_LOCK_COUNT_INVALID=$($locks.Count)" }
$lockHash = Get-Sha $locks[0].FullName
Write-Host "HF06_SINGLE_USE_LOCK_SHA256=$lockHash"
if ($lockHash -ne $ExpectedLockHash) { throw 'HF06_SINGLE_USE_LOCK_HASH_MISMATCH' }

foreach ($n in @(
    '20_EXECUTION_RECEIPT_CREATE_HF06.json',
    '21_EXECUTION_RECEIPT_ACTIVATE_HF06.json',
    '30_OUTCOME_RECEIPT_HF06.json',
    '99_LIVE_FINAL_RECEIPT_HF06.json',
    'AUTHORIZATION_CONSUMED_HF06.json'
)) {
    if (Test-Path -LiteralPath (Join-Path $HF06StateRoot $n) -PathType Leaf) {
        throw "UNEXPECTED_HF06_RECEIPT_PRESENT=$n"
    }
}

Write-Host 'HF06_REPLAY_BLOCKED=TRUE'
Write-Host 'HF06_DO_NOT_RERUN=TRUE'
Write-Host 'HF06_AUTHORIZATION_REUSE_AUTHORIZED=FALSE'

Write-Host '=== LOCAL_RAW_RESPONSE_ADJUDICATION ==='

$validation = Convert-McpContent (Get-Content -LiteralPath $ValidationRawPath -Raw)
$details = Convert-McpContent (Get-Content -LiteralPath $DetailsRawPath -Raw)

if ($validation.PSObject.Properties['error'] -and $null -ne $validation.error) {
    throw "VALIDATION_JSONRPC_ERROR=$($validation.error | ConvertTo-Json -Compress)"
}
if ($details.PSObject.Properties['error'] -and $null -ne $details.error) {
    throw "DETAILS_JSONRPC_ERROR=$($details.error | ConvertTo-Json -Compress)"
}

$detailsTexts = @(Collect-Text $details)
$validationTexts = @(Collect-Text $validation)

Write-Host "DETAILS_TEXT_COUNT=$($detailsTexts.Count)"
Write-Host "VALIDATION_TEXT_COUNT=$($validationTexts.Count)"

$validationText = ($validationTexts -join ' | ').Trim()
if ([string]::IsNullOrWhiteSpace($validationText)) {
    $validationText = ($validation | ConvertTo-Json -Depth 100 -Compress)
}

$norm = $validationText
if ($norm.Length -gt 4000) { $norm = $norm.Substring(0,4000) }
[System.IO.File]::WriteAllText(
    (Join-Path $EvidenceRoot '08_NORMALIZED_VALIDATION_TEXT_R2.txt'),
    $norm,
    $Utf8NoBom
)

$lower = $validationText.ToLowerInvariant()
$existsPattern = 'already\s+exists|already\s+exist|exists\s+already|object.{0,80}exists|name.{0,80}exists|duplicate|collision|is\s+already\s+used'
$successPattern = 'validation.{0,40}(successful|success|passed)|(successful|successfully).{0,40}validat|no\s+(validation\s+)?errors|input.{0,40}valid'

$errorValues = @(
    @(Collect-Text $validation) |
    Where-Object { $_ -match '(?i)error|invalid|failed|failure' }
)

$existenceConflict = [regex]::IsMatch($lower,$existsPattern,[Text.RegularExpressions.RegexOptions]::IgnoreCase)
$positiveValidation = [regex]::IsMatch($lower,$successPattern,[Text.RegularExpressions.RegexOptions]::IgnoreCase)

if ($existenceConflict) {
    $reconciliation = 'CREATE_COMMIT_SUPPORTED_BY_CREATION_COLLISION_SIGNAL'
    $inference = 'LIKELY_EXISTS'
}
elseif ($positiveValidation -and $errorValues.Count -eq 0) {
    $reconciliation = 'CREATE_COMMIT_NOT_SUPPORTED_BY_PREFLIGHT_VALIDATION'
    $inference = 'LIKELY_ABSENT_OR_CREATE_STILL_ADMISSIBLE'
}
else {
    $reconciliation = 'CREATE_COMMIT_REMAINS_UNKNOWN'
    $inference = 'UNKNOWN'
}

Write-Host "VALIDATION_ERROR_SIGNAL_COUNT=$($errorValues.Count)"
Write-Host "EXISTENCE_CONFLICT_SIGNAL=$existenceConflict"
Write-Host "POSITIVE_VALIDATION_SIGNAL=$positiveValidation"
Write-Host "CREATE_STATE_RECONCILIATION=$reconciliation"
Write-Host "OBJECT_STATE_INFERENCE=$inference"

if ($reconciliation -eq 'CREATE_COMMIT_SUPPORTED_BY_CREATION_COLLISION_SIGNAL') {
    $next = 'CREATE_LIKELY_COMMITTED_READBACK_OR_CONTINUATION_DESIGN_REQUIRED'
}
elseif ($reconciliation -eq 'CREATE_COMMIT_NOT_SUPPORTED_BY_PREFLIGHT_VALIDATION') {
    $next = 'CREATE_LIKELY_NOT_COMMITTED_NEW_GOVERNED_EXECUTION_DESIGN_REQUIRED'
}
else {
    $next = 'CREATE_COMMIT_UNKNOWN_FURTHER_READ_ONLY_RECONCILIATION_REQUIRED'
}

$result = [ordered]@{
    mission = 'MCR_R1_9_B_HF06_ATTEMPT2_CREATE_STATE_PREFLIGHT_RECONCILIATION_ADJUDICATION_R2'
    source_run = [ordered]@{
        broken_reconciliation_script_sha256 = $brokenHash
        validation_raw_sha256 = $validationRawHash
        details_raw_sha256 = $detailsRawHash
        prior_provider_protocol_calls = 5
        prior_tools_call_requests = 2
        prior_sap_remote_read_calls = 1
        prior_sap_remote_validation_calls = 1
        prior_sap_writes = 0
    }
    adjudication = [ordered]@{
        method = 'LOCAL_PARSE_OF_ALREADY_CAPTURED_MCP_RESPONSES'
        existence_conflict_signal = $existenceConflict
        positive_validation_signal = $positiveValidation
        error_signal_count = $errorValues.Count
        create_commit_state = $reconciliation
        object_state_inference = $inference
        authoritative_repository_readback = $false
    }
    local_execution = [ordered]@{
        mcp_provider_calls = 0
        mcp_tools_call_requests = 0
        sap_reads = 0
        sap_writes = 0
    }
    authority = [ordered]@{
        hf06_authorization_reuse_authorized = $false
        live_sap_write_authorized = $false
    }
    final_state = $next
}

$resultPath = Join-Path $EvidenceRoot '09_ADJUDICATION_RESULT_R2.json'
[System.IO.File]::WriteAllText(
    $resultPath,
    ($result | ConvertTo-Json -Depth 30),
    $Utf8NoBom
)

Write-Host '=== FINAL ==='
Write-Host 'MCR_R1_9_B_HF06_ATTEMPT2_CREATE_STATE_PREFLIGHT_RECONCILIATION_ADJUDICATION_R2=PASS'
Write-Host 'SOURCE_FAILURE=POWERSHELL_SCALAR_COUNT_BUG'
Write-Host 'SOURCE_LIVE_CALLS_REPEATED=FALSE'
Write-Host 'MCP_PROVIDER_CALLS=0'
Write-Host 'MCP_TOOLS_CALL_REQUESTS=0'
Write-Host 'SAP_READS=0'
Write-Host 'SAP_WRITES=0'
Write-Host 'HF06_DO_NOT_RERUN=TRUE'
Write-Host 'HF06_AUTHORIZATION_REUSE_AUTHORIZED=FALSE'
Write-Host "CREATE_STATE_RECONCILIATION=$reconciliation"
Write-Host "OBJECT_STATE_INFERENCE=$inference"
Write-Host 'AUTHORITATIVE_REPOSITORY_READBACK=FALSE'
Write-Host 'LIVE_SAP_WRITE_AUTHORIZED=FALSE'
Write-Host "FINAL_STATE=$next"

# SIG # Begin signature block
# MIIHMAYJKoZIhvcNAQcCoIIHITCCBx0CAQExDzANBglghkgBZQMEAgEFADB5Bgor
# BgEEAYI3AgEEoGswaTA0BgorBgEEAYI3AgEeMCYCAwEAAAQQH8w7YFlLCE63JNLG
# KX7zUQIBAAIBAAIBAAIBAAIBADAxMA0GCWCGSAFlAwQCAQUABCDxEOttWWVx7UQx
# WbryXO+7EkOUjXSP3N/BQB1qLk1g2KCCBBwwggQYMIICgKADAgECAhApojSr80YY
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
# MC8GCSqGSIb3DQEJBDEiBCAR6bqd2D65Qq9ElvJ8z4tFGKzxu/EJ4n+50OFGiAmY
# XDANBgkqhkiG9w0BAQEFAASCAYD2298sz88g53W31Rqfp5/5A9Z6piBCyCT+f2YT
# W+c9F+9IUFFTuOaG5lBGNNNpN+5y5GXLivQd8a3gS+eJK+DpMbXeqOboEysWO3l8
# pyr7bsgJ8jCx87gsfBOv6R4nH/7+m+ZpKJfUKohz8ffjfFRMmrPY5NU+R2aAgGm3
# W7ZN6bar8Kp9BUNyxfxT4TP+uhsebSswPwD0uVbaYtXPEIdjrxc8zO4p59VpbuzC
# zyYORD+B2ubsxw3SbvZn6on6EYOptG+m4XCCuZ5l8Et7A1JxpxvF2G4VZV9LMlV+
# Ewbqw6j7JQ/5YhucwOi+m+q7lfVTn6SnHwpVvIYojesgtwOvqpp8kQoFUMeZQtRx
# 1sWYpcNce2u+ID55UxSDhhZKonOxCzAxpX05zcJ4dxo+o+P1CTCKQulWkktDW+oP
# E2jHXrhNwgJ9woo6GsFeG17iU5BLB9+9t/Pp9ZcV+hFyAUhPvxkBMPel6eIyfIzk
# l2t40y+qHzAvX6YWmCsEAeOyLeM=
# SIG # End signature block
