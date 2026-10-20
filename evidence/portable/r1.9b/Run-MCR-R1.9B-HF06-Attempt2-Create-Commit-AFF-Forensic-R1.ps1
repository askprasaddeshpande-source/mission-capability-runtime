[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# ============================================================
# MCR R1.9B
# HF06 ATTEMPT-2 CREATE-COMMIT / AFF-PATH FORENSIC R1
#
# READ-ONLY FORENSIC.
#
# Performs:
#   1. exact HF06 / authorization / single-use-lock verification
#   2. exact failed-output verification
#   3. static call-order verification
#   4. bounded recent VS Code log search for the returned AFF filePath
#   5. one read-only Eclipse bridge GET of the exact class source
#
# DOES NOT:
#   - call ADT MCP tools
#   - create/activate/delete/update any SAP object
#   - modify/reuse authorization
#   - rerun HF06
# ============================================================

$Root = 'D:\MCP'

$HF06 = Join-Path $Root 'Run-MCR-R1.9B-Live-Governed-Mutation-And-Outcome-R1-HF06.ps1'
$HF06Auth = Join-Path $Root 'MCR_R1_9_B_LIVE_WRITE_AUTHORIZATION_HF06.json'
$HF06StateRoot = Join-Path $Root 'MCR_R1_9_B_LIVE_GOVERNED_MUTATION_AND_OUTCOME_R1_HF06_STATE'

$Attempt2Root = Join-Path $Root 'MCR_R1_9_B_HF06_AUTHORIZED_LIVE_EXECUTION_R2'
$Attempt2Output = Join-Path $Attempt2Root '02_HF06_LIVE_EXECUTION_OUTPUT_R2.txt'

$EvidenceRoot = Join-Path $Root 'MCR_R1_9_B_HF06_ATTEMPT2_CREATE_COMMIT_AFF_FORENSIC_R1'

$ExpectedHF06Hash = 'DE183ABC47B8F025ED60CFE5CFEA4527585FB20154C949628BDE95E42A0D3C88'
$ExpectedHF06AuthHash = 'CC06B59F341E9B70844F7BEE48F6917303C094206431C228575F91E4500B9E09'
$ExpectedLockHash = 'DFE129A6D66656B4477B1693D5073CD17B40918516DCF725A6193C019B7BB275'
$SignerThumbprint = '9E8E489FF6F727188EBA3EFECA1381A42A9938C6'

$ObjectName = 'ZCL_MCR19B_9533C4D8'
$Destination = 'TRL_EN'

$BridgeBase = 'http://127.0.0.1:8765'
$BridgeHealth = "$BridgeBase/health"
$BridgeProxy = "$BridgeBase/proxy"
$ClassSourcePath = "/sap/bc/adt/oo/classes/$ObjectName/source/main"

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
        ($Object | ConvertTo-Json -Depth 40),
        $Utf8NoBom
    )
}

function Redact-ForensicText {
    param([Parameter(Mandatory=$true)][string]$Text)

    $Value = $Text

    $Value = [regex]::Replace(
        $Value,
        '(?i)(Bearer\s+)[A-Za-z0-9\-._~+/]+=*',
        '$1<REDACTED>'
    )

    $Value = [regex]::Replace(
        $Value,
        '(?i)("Authorization"\s*:\s*")[^"]+(")',
        '$1<REDACTED>$2'
    )

    $Value = [regex]::Replace(
        $Value,
        '(?i)("protected_token_b64"\s*:\s*")[^"]+(")',
        '$1<REDACTED>$2'
    )

    return $Value
}

Write-Host '=== EXACT_INPUT_VERIFICATION ==='

if (-not (Test-Path -LiteralPath $HF06 -PathType Leaf)) {
    throw 'HF06_SOURCE_NOT_FOUND'
}

if (-not (Test-Path -LiteralPath $HF06Auth -PathType Leaf)) {
    throw 'HF06_ATTEMPT2_AUTHORIZATION_NOT_FOUND'
}

if (-not (Test-Path -LiteralPath $Attempt2Output -PathType Leaf)) {
    throw 'HF06_ATTEMPT2_OUTPUT_NOT_FOUND'
}

$HF06Hash = Get-FileSha256Local $HF06
$HF06Sig = Get-AuthenticodeSignature -FilePath $HF06
$AuthHash = Get-FileSha256Local $HF06Auth
$OutputHash = Get-FileSha256Local $Attempt2Output

Write-Host "HF06_SOURCE_SHA256=$HF06Hash"
Write-Host "HF06_SIGNATURE_STATUS=$($HF06Sig.Status)"
Write-Host "HF06_AUTHORIZATION_SHA256=$AuthHash"
Write-Host "HF06_ATTEMPT2_OUTPUT_SHA256=$OutputHash"

if ($HF06Hash -ne $ExpectedHF06Hash) {
    throw 'HF06_SOURCE_HASH_MISMATCH'
}

if ($HF06Sig.Status -ne 'Valid') {
    throw 'HF06_SIGNATURE_INVALID'
}

if ($HF06Sig.SignerCertificate.Thumbprint -ne $SignerThumbprint) {
    throw 'HF06_SIGNER_MISMATCH'
}

if ($AuthHash -ne $ExpectedHF06AuthHash) {
    throw 'HF06_ATTEMPT2_AUTHORIZATION_HASH_MISMATCH'
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

Write-Host "HF06_SINGLE_USE_LOCK_COUNT=$($Locks.Count)"

if ($Locks.Count -ne 1) {
    throw "HF06_SINGLE_USE_LOCK_COUNT_INVALID=$($Locks.Count)"
}

$LockHash = Get-FileSha256Local $Locks[0].FullName

Write-Host "HF06_SINGLE_USE_LOCK_SHA256=$LockHash"

if ($LockHash -ne $ExpectedLockHash) {
    throw 'HF06_SINGLE_USE_LOCK_HASH_MISMATCH'
}

$ReceiptNames = @(
    '20_EXECUTION_RECEIPT_CREATE_HF06.json',
    '21_EXECUTION_RECEIPT_ACTIVATE_HF06.json',
    '30_OUTCOME_RECEIPT_HF06.json',
    '99_LIVE_FINAL_RECEIPT_HF06.json',
    'AUTHORIZATION_CONSUMED_HF06.json'
)

$ExistingReceiptCount = 0

foreach ($Name in $ReceiptNames) {
    $Path = Join-Path $HF06StateRoot $Name
    $Exists = Test-Path -LiteralPath $Path -PathType Leaf

    Write-Host "$Name=$Exists"

    if ($Exists) {
        $ExistingReceiptCount++
    }
}

if ($ExistingReceiptCount -ne 0) {
    throw "UNEXPECTED_HF06_RECEIPTS_PRESENT=$ExistingReceiptCount"
}

Write-Host 'HF06_ATTEMPT2_REPLAY_BLOCKED_BY_SINGLE_USE_LOCK=TRUE'
Write-Host 'HF06_DO_NOT_RERUN=TRUE'


# ============================================================
# FAILED OUTPUT + STATIC CALL ORDER
# ============================================================

Write-Host '=== CREATE_REACH_STATIC_FORENSIC ==='

$AttemptOutputText = Get-Content -LiteralPath $Attempt2Output -Raw

if ($AttemptOutputText -notmatch 'CREATE_FILEPATH_MISSING') {
    throw 'EXPECTED_CREATE_FILEPATH_MISSING_NOT_FOUND_IN_ATTEMPT2_OUTPUT'
}

$HF06Text = Get-Content -LiteralPath $HF06 -Raw

$CreateCallPosition = $HF06Text.IndexOf('$create=Send-Hf06LiveRequest')
$FilePathPosition = $HF06Text.IndexOf('$createdPath=')
$FilePathGuardPosition = $HF06Text.IndexOf('CREATE_FILEPATH_MISSING')
$ActivateCallPosition = $HF06Text.IndexOf('$activate=Send-Hf06LiveRequest')

Write-Host "CREATE_CALL_POSITION=$CreateCallPosition"
Write-Host "FILEPATH_EXTRACTION_POSITION=$FilePathPosition"
Write-Host "FILEPATH_GUARD_POSITION=$FilePathGuardPosition"
Write-Host "ACTIVATE_CALL_POSITION=$ActivateCallPosition"

if (
    $CreateCallPosition -lt 0 -or
    $FilePathPosition -lt 0 -or
    $FilePathGuardPosition -lt 0 -or
    $ActivateCallPosition -lt 0
) {
    throw 'HF06_EXPECTED_LIVE_SEQUENCE_ELEMENT_MISSING'
}

if (-not (
    $CreateCallPosition -lt $FilePathPosition -and
    $FilePathPosition -lt $FilePathGuardPosition -and
    $FilePathGuardPosition -lt $ActivateCallPosition
)) {
    throw 'HF06_CREATE_FILEPATH_ACTIVATE_ORDER_INVALID'
}

Write-Host 'CREATE_TOOL_CALL_REACHED_PROVIDER=TRUE'
Write-Host 'ACTIVATE_TOOL_CALL_REACHED_PROVIDER=FALSE'
Write-Host 'CREATE_COMMIT_STATE=UNKNOWN_PENDING_READBACK'


# ============================================================
# BOUNDED RECENT VS CODE LOG SEARCH FOR AFF FILEPATH
# ============================================================

Write-Host '=== BOUNDED_VSCODE_AFF_PATH_FORENSIC ==='

$VsCodeLogRoot = Join-Path $env:APPDATA 'Code\logs'
$CutoffUtc = [DateTime]::UtcNow.AddHours(-6)

$MatchingLines = New-Object System.Collections.Generic.List[string]

if (Test-Path -LiteralPath $VsCodeLogRoot -PathType Container) {
    $RecentLogFiles = @(
        Get-ChildItem `
            -LiteralPath $VsCodeLogRoot `
            -File `
            -Recurse `
            -ErrorAction SilentlyContinue |
        Where-Object {
            $_.LastWriteTimeUtc -ge $CutoffUtc
        } |
        Select-Object -First 1000
    )

    Write-Host "RECENT_VSCODE_LOG_FILES_SCANNED=$($RecentLogFiles.Count)"

    foreach ($File in $RecentLogFiles) {
        try {
            foreach ($Match in @(
                Select-String `
                    -LiteralPath $File.FullName `
                    -SimpleMatch `
                    -Pattern $ObjectName `
                    -ErrorAction SilentlyContinue
            )) {
                if ($MatchingLines.Count -ge 100) {
                    break
                }

                $Safe = Redact-ForensicText (
                    '{0}:{1}:{2}' -f
                    $File.FullName,
                    $Match.LineNumber,
                    $Match.Line
                )

                $MatchingLines.Add($Safe)
            }
        }
        catch {
        }

        if ($MatchingLines.Count -ge 100) {
            break
        }
    }
}
else {
    Write-Host 'VSCODE_LOG_ROOT_PRESENT=FALSE'
}

$LogEvidencePath = Join-Path $EvidenceRoot '01_VSCODE_OBJECT_MATCHES_REDACTED.txt'

[System.IO.File]::WriteAllLines(
    $LogEvidencePath,
    @($MatchingLines),
    $Utf8NoBom
)

Write-Host "VSCODE_OBJECT_MATCH_LINE_COUNT=$($MatchingLines.Count)"

$CandidateUris = New-Object System.Collections.Generic.HashSet[string](
    [StringComparer]::OrdinalIgnoreCase
)

foreach ($Line in $MatchingLines) {
    foreach ($Match in [regex]::Matches(
        $Line,
        '(?i)abap:/repotree-v1/[^\s"''\\]+'
    )) {
        $Candidate = $Match.Value.TrimEnd('}',']',',')
        if ($Candidate -match '(?i)zcl_mcr19b_9533c4d8') {
            $null = $CandidateUris.Add($Candidate)
        }
    }

    foreach ($Match in [regex]::Matches(
        $Line,
        '(?i)file:/+[^\s"''\\]+'
    )) {
        $Candidate = $Match.Value.TrimEnd('}',']',',')
        if ($Candidate -match '(?i)zcl_mcr19b_9533c4d8') {
            $null = $CandidateUris.Add($Candidate)
        }
    }
}

$AffCandidates = @($CandidateUris | Sort-Object)

Write-Host "AFF_FILEPATH_CANDIDATE_COUNT=$($AffCandidates.Count)"

foreach ($Candidate in $AffCandidates) {
    Write-Host "AFF_FILEPATH_CANDIDATE=$Candidate"
}

$AffEvidencePath = Join-Path $EvidenceRoot '02_AFF_FILEPATH_CANDIDATES.json'

Write-JsonEvidence `
    -Path $AffEvidencePath `
    -Object ([ordered]@{
        object_name = $ObjectName
        candidates = $AffCandidates
        candidate_count = $AffCandidates.Count
    })


# ============================================================
# EXACT READ-ONLY SAP OBJECT EXISTENCE PROBE VIA PROVEN BRIDGE
# ============================================================

Write-Host '=== READ_ONLY_CLASS_EXISTENCE_PROBE ==='
Write-Host 'PROBE_METHOD=GET'
Write-Host "PROBE_PATH=$ClassSourcePath"
Write-Host 'SAP_WRITES_AUTHORIZED=FALSE'

$BridgeAvailable = $false
$SapReadPerformed = $false
$SapStatus = $null
$ObjectExists = $null
$SourceHash = $null
$SourceSize = 0
$BridgeError = $null

try {
    $Health = Invoke-RestMethod `
        -Uri $BridgeHealth `
        -Method Get `
        -TimeoutSec 5

    $BridgeAvailable = $true
    Write-Host 'ECLIPSE_BRIDGE_HEALTH=PASS'
}
catch {
    $BridgeError = "BRIDGE_HEALTH_FAILED:$($_.Exception.Message)"
    Write-Host 'ECLIPSE_BRIDGE_HEALTH=UNAVAILABLE'
}

if ($BridgeAvailable) {
    try {
        $Response = Invoke-RestMethod `
            -Uri $BridgeProxy `
            -Method Post `
            -Headers @{
                'X-Proxy-Method' = 'GET'
                'X-Proxy-Path' = $ClassSourcePath
                'X-Proxy-Destination' = $Destination
                'X-Proxy-Accept' = 'text/plain'
            } `
            -Body ([byte[]]@()) `
            -TimeoutSec 30

        $SapReadPerformed = $true
        $SapStatus = [int]$Response.status

        Write-Host "SAP_READ_STATUS=$SapStatus"

        if ($SapStatus -eq 200) {
            $ObjectExists = $true
            $Body = [string]$Response.body
            $SourceSize = [Text.Encoding]::UTF8.GetByteCount($Body)
            $SourceHash = Get-TextSha256Local $Body

            Write-Host 'OBJECT_EXISTS_READBACK=TRUE'
            Write-Host "READBACK_SOURCE_SIZE_BYTES=$SourceSize"
            Write-Host "READBACK_SOURCE_SHA256=$SourceHash"
        }
        elseif ($SapStatus -eq 404) {
            $ObjectExists = $false
            Write-Host 'OBJECT_EXISTS_READBACK=FALSE'
        }
        else {
            $ObjectExists = $null
            Write-Host 'OBJECT_EXISTS_READBACK=UNKNOWN'
        }
    }
    catch {
        $BridgeError = "BRIDGE_READ_FAILED:$($_.Exception.Message)"
        Write-Host 'SAP_READ_STATUS=UNAVAILABLE'
        Write-Host 'OBJECT_EXISTS_READBACK=UNKNOWN'
    }
}

$SapReads = if ($SapReadPerformed) { 1 } else { 0 }

if ($ObjectExists -eq $true) {
    $CreateCommitState = 'CREATE_COMMIT_OBSERVED_BY_READBACK'
    $MinimumSapWritesObserved = 1
}
elseif ($ObjectExists -eq $false) {
    $CreateCommitState = 'CREATE_COMMIT_NOT_OBSERVED_OBJECT_ABSENT'
    $MinimumSapWritesObserved = 0
}
else {
    $CreateCommitState = 'CREATE_COMMIT_UNKNOWN'
    $MinimumSapWritesObserved = 0
}

Write-Host "CREATE_COMMIT_STATE=$CreateCommitState"
Write-Host "MINIMUM_SAP_WRITES_OBSERVED=$MinimumSapWritesObserved"


# ============================================================
# RESULT
# ============================================================

$Result = [ordered]@{
    mission = 'MCR_R1_9_B_HF06_ATTEMPT2_CREATE_COMMIT_AFF_FORENSIC_R1'

    frozen_identity = [ordered]@{
        hf06_source_sha256 = $HF06Hash
        hf06_authorization_sha256 = $AuthHash
        hf06_single_use_lock_sha256 = $LockHash
        object_name = $ObjectName
        destination = $Destination
    }

    execution_forensic = [ordered]@{
        failure = 'CREATE_FILEPATH_MISSING'
        create_tool_call_reached_provider = $true
        activate_tool_call_reached_provider = $false
        replay_blocked_by_single_use_lock = $true
        do_not_rerun_hf06 = $true
        create_commit_state = $CreateCommitState
        minimum_sap_writes_observed = $MinimumSapWritesObserved
    }

    aff_path_forensic = [ordered]@{
        recent_vscode_match_lines = $MatchingLines.Count
        candidate_count = $AffCandidates.Count
        candidates = $AffCandidates
    }

    read_only_reconciliation = [ordered]@{
        bridge_available = $BridgeAvailable
        sap_read_performed = $SapReadPerformed
        sap_status = $SapStatus
        object_exists = $ObjectExists
        source_sha256 = $SourceHash
        source_size_bytes = $SourceSize
        bridge_error = $BridgeError
        sap_reads = $SapReads
        sap_writes = 0
    }

    authority = [ordered]@{
        historical_hf06_authorization_reusable = $false
        live_sap_write_authorized = $false
        compensation_authorized = $false
        cleanup_delete_authorized = $false
    }
}

if ($ObjectExists -eq $true -and $AffCandidates.Count -eq 1) {
    $NextState = 'CREATE_CONFIRMED_AFF_PATH_RECOVERED_CONTINUATION_DESIGN_REQUIRED'
}
elseif ($ObjectExists -eq $true) {
    $NextState = 'CREATE_CONFIRMED_AFF_PATH_RESOLUTION_REQUIRED'
}
elseif ($ObjectExists -eq $false) {
    $NextState = 'CREATE_NOT_COMMITTED_NEW_AUTHORITY_DESIGN_REQUIRED_NO_REPLAY'
}
else {
    $NextState = 'CREATE_COMMIT_UNKNOWN_ADDITIONAL_READ_ONLY_RECONCILIATION_REQUIRED'
}

$Result.next_state = $NextState

$ResultPath = Join-Path $EvidenceRoot '03_RESULT_R1.json'

Write-JsonEvidence `
    -Path $ResultPath `
    -Object $Result

Write-Host '=== FINAL ==='
Write-Host 'MCR_R1_9_B_HF06_ATTEMPT2_CREATE_COMMIT_AFF_FORENSIC=PASS'
Write-Host 'HF06_DO_NOT_RERUN=TRUE'
Write-Host 'HF06_REPLAY_BLOCKED_BY_SINGLE_USE_LOCK=TRUE'
Write-Host 'CREATE_TOOL_CALL_REACHED_PROVIDER=TRUE'
Write-Host 'ACTIVATE_TOOL_CALL_REACHED_PROVIDER=FALSE'
Write-Host "CREATE_COMMIT_STATE=$CreateCommitState"
Write-Host "AFF_FILEPATH_CANDIDATE_COUNT=$($AffCandidates.Count)"
Write-Host "SAP_READS=$SapReads"
Write-Host 'SAP_WRITES_AUTHORIZED=FALSE'
Write-Host 'SAP_WRITES_PERFORMED_BY_FORENSIC=0'
Write-Host "MINIMUM_PRIOR_SAP_WRITES_OBSERVED=$MinimumSapWritesObserved"
Write-Host "OBJECT_CREATED=$ObjectExists"
Write-Host 'HF06_AUTHORIZATION_REUSE_AUTHORIZED=FALSE'
Write-Host 'LIVE_SAP_WRITE_AUTHORIZED=FALSE'
Write-Host "FINAL_STATE=$NextState"

# SIG # Begin signature block
# MIIHMAYJKoZIhvcNAQcCoIIHITCCBx0CAQExDzANBglghkgBZQMEAgEFADB5Bgor
# BgEEAYI3AgEEoGswaTA0BgorBgEEAYI3AgEeMCYCAwEAAAQQH8w7YFlLCE63JNLG
# KX7zUQIBAAIBAAIBAAIBAAIBADAxMA0GCWCGSAFlAwQCAQUABCAhMdCQEESzWv81
# 2HI3/1VtlOH1n4E5Fyv5xJFXd2YtyaCCBBwwggQYMIICgKADAgECAhApojSr80YY
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
# MC8GCSqGSIb3DQEJBDEiBCDaiwdE2puWIbpfA4rzbNDQ4dw6qQBKX+xaMPDTQtfs
# rDANBgkqhkiG9w0BAQEFAASCAYCK6+3PS54wveT7u1+eAav46fae5VDYoqVur0F+
# 7sVX6vCSJhB2enT/aOrz4jxhhir0w5/KQljl5eBVPSQU3qAfkRSeK++QC/gRxibR
# Nwzp6H7VUURydwaa3pyfhnsADf1ho98oJnNRoEwG8GQOEkLEZaJ4tIkDf33DN0sX
# zw8T5B3MQkcMxJkKhZqlC0QfW9BACpE9xrrB55yL7f4vqVa4SxnXF47XbDgB2VCv
# eIph98wWhhRzTaI+r6IfvFxldNeu94rAvWUsWBzT8GUv27rWSkfbOjH0TzOR0va+
# n/qSg+g2dZkFnh/YHe01mTrInZLTh6/YzgORIUUrqQGutuWIRjAi5nOB/v0YwyPZ
# VwcZWeNZxmm4MVgg037ggzYakGATqzeT4EkRrrVPAgdvXtNDvdIbMkgE1Y7ffY/8
# 5jBHcuPLH9o2GWWeCebs4dcMeV9TxC/xMXZUH9JDb9+SvDwDmFi2XM7j1fhjPbYo
# hee8Gl7+ZTWRBjubYV4dJRXONWM=
# SIG # End signature block
