param(
    [ValidateSet(
        "Start",
        "Run",
        "Status",
        "Stop"
    )]
    [string]$Mode = "Start"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedSigner =
    "9E8E489FF6F727188EBA3EFECA1381A42A9938C6"

$Workspace =
    "D:\MCP\MCR_R2E_P8_MULTI_MCP_PROVIDER_SET_R1"

$StateRoot =
    "D:\MCP\MCR_R2E_P8_MCP_WATCHDOG_R2"

$StatePath =
    Join-Path $StateRoot "WATCHDOG_STATE_R2.json"

$LogPath =
    Join-Path $StateRoot "WATCHDOG_R2.log"

$StopSignal =
    Join-Path $StateRoot "STOP.REQUESTED"

$AdtPort =
    2236

$AdtExe =
    "C:\Users\Admin\.vscode\extensions\sapse.adt-vscode-1.1.2-win32-x64\adt-ls\win32\win32\x86_64\adt-lsc.exe"

$ExpectedAdtExeHash =
    "9794FA26F74FE5E04435F7111A853A415FD97476C85FE24B1DA3AD65CAE955E8"

$ExpectedFioriHash =
    "31DF0A573FEBDC49B462E5B0268B164ECE034D470818AA33D5C577732BB403A1"

$ExpectedUi5Hash =
    "ABB1F7107F7AEF4F001F030353AA8285FCFD23652053A3CF22A1AD6BECDEC55C"

$ExpectedCapHash =
    "50E1C4792B539F3228FDCA86740D97ED132334FEB76DA4AEA5681E6940B609BB"

function Assert-SelfSignature {

    $sig =
        Get-AuthenticodeSignature $PSCommandPath

    if ($sig.Status -ne "Valid") {
        throw "WATCHDOG_SIGNATURE_INVALID"
    }

    if ($sig.SignerCertificate.Thumbprint -ne $ExpectedSigner) {
        throw "WATCHDOG_SIGNER_MISMATCH"
    }
}

function Write-Log {

    param(
        [Parameter(Mandatory=$true)]
        [string]$Message
    )

    if (-not (Test-Path $StateRoot)) {

        New-Item `
            -ItemType Directory `
            -Path $StateRoot `
            -Force |
            Out-Null
    }

    Add-Content `
        -Path $LogPath `
        -Value (
            "{0} {1}" -f
            [DateTime]::UtcNow.ToString("o"),
            $Message
        ) `
        -Encoding utf8
}

function Test-Port {

    param(
        [Parameter(Mandatory=$true)]
        [int]$Port
    )

    $client =
        [System.Net.Sockets.TcpClient]::new()

    try {

        $task =
            $client.ConnectAsync(
                "127.0.0.1",
                $Port
            )

        if (-not $task.Wait(1000)) {
            return $false
        }

        return $client.Connected
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

function Test-Pid {

    param(
        [int]$ProcessId
    )

    if ($ProcessId -le 0) {
        return $false
    }

    try {

        Get-Process `
            -Id $ProcessId `
            -ErrorAction Stop |
            Out-Null

        return $true
    }
    catch {
        return $false
    }
}

function Assert-Hash {

    param(
        [string]$Path,
        [string]$Expected,
        [string]$Label
    )

    if (-not (Test-Path $Path)) {
        throw ("{0}_NOT_FOUND={1}" -f $Label,$Path)
    }

    $actual =
        (Get-FileHash `
            $Path `
            -Algorithm SHA256
        ).Hash.ToUpperInvariant()

    if ($actual -ne $Expected) {

        throw (
            "{0}_HASH_DRIFT={1}" -f
            $Label,
            $actual
        )
    }

    return $actual
}

function Resolve-ProviderBinaries {

    $npmRoot =
        (& npm root -g).Trim()

    if ([string]::IsNullOrWhiteSpace($npmRoot)) {
        throw "NPM_ROOT_NOT_RESOLVED"
    }

    $fiori =
        Join-Path `
            $npmRoot `
            "@sap-ux\fiori-mcp-server\dist\index.js"

    $ui5 =
        Join-Path `
            $npmRoot `
            "@ui5\mcp-server\bin\ui5mcp.js"

    $cap =
        Join-Path `
            $npmRoot `
            "@cap-js\mcp-server\index.js"

    Assert-Hash `
        $fiori `
        $ExpectedFioriHash `
        "FIORI" |
        Out-Null

    Assert-Hash `
        $ui5 `
        $ExpectedUi5Hash `
        "UI5" |
        Out-Null

    Assert-Hash `
        $cap `
        $ExpectedCapHash `
        "CAP" |
        Out-Null

    Assert-Hash `
        $AdtExe `
        $ExpectedAdtExeHash `
        "ADT_EXE" |
        Out-Null

    return [ordered]@{
        Fiori = $fiori
        UI5   = $ui5
        CAP   = $cap
    }
}

function Write-State {

    param(
        [bool]$AdtLive,
        [bool]$VsCodeRunning,
        [bool]$ExplicitRecoveryRequired,
        [hashtable]$ProviderPaths
    )

    $state =
        [ordered]@{

            watchdog_id =
                "MCR_R2E_P8_MCP_WATCHDOG_R2"

            timestamp_utc =
                [DateTime]::UtcNow.ToString("o")

            watchdog_pid =
                $PID

            architecture =
                "PERSISTENT_ADT_PLUS_BOUNDED_STDIO_SESSIONS"

            adt =
                [ordered]@{

                    owner =
                        "VS_CODE_SAP_ADT"

                    endpoint =
                        "http://127.0.0.1:2236/mcp"

                    live =
                        $AdtLive

                    vscode_running =
                        $VsCodeRunning

                    autonomous_self_healing =
                        $false

                    explicit_recovery_required =
                        $ExplicitRecoveryRequired
                }

            stdio_providers =
                @(

                    [ordered]@{
                        provider = "SAP_FIORI_MCP"
                        state = "READY_FOR_BOUNDED_SESSION"
                        persistent_process_expected = $false
                        binary = $ProviderPaths.Fiori
                    },

                    [ordered]@{
                        provider = "SAP_UI5_MCP"
                        state = "READY_FOR_BOUNDED_SESSION"
                        persistent_process_expected = $false
                        binary = $ProviderPaths.UI5
                    },

                    [ordered]@{
                        provider = "SAP_CAP_MCP"
                        state = "READY_FOR_BOUNDED_SESSION"
                        persistent_process_expected = $false
                        binary = $ProviderPaths.CAP
                    }
                )

            btp_administration =
                "DEFERRED"

            counters =
                [ordered]@{

                    model_calls = 0
                    mcp_calls = 0
                    sap_calls = 0
                    sap_writes = 0
                    btp_calls = 0
                    btp_writes = 0
                }
        }

    $utf8 =
        New-Object System.Text.UTF8Encoding($true)

    [System.IO.File]::WriteAllText(
        $StatePath,
        ($state | ConvertTo-Json -Depth 30),
        $utf8
    )
}

function Show-Status {

    $providers =
        Resolve-ProviderBinaries

    $adtLive =
        Test-Port -Port $AdtPort

    $vscode =
        @(
            Get-Process `
                -Name "Code" `
                -ErrorAction SilentlyContinue
        )

    $vscodeRunning =
        ($vscode.Count -gt 0)

    Write-Host "=== MCP_WATCHDOG_STATUS ==="

    Write-Host "WATCHDOG_VERSION=R2"
    Write-Host "ARCHITECTURE=PERSISTENT_ADT_PLUS_BOUNDED_STDIO_SESSIONS"

    Write-Host "ADT_PORT_2236_LIVE=$adtLive"
    Write-Host "ADT_OWNER=VS_CODE_SAP_ADT"
    Write-Host "ADT_AUTONOMOUS_SELF_HEALING=FALSE"

    Write-Host "VSCODE_RUNNING=$vscodeRunning"

    Write-Host "FIORI=READY_FOR_BOUNDED_STDIO_SESSION"
    Write-Host "UI5=READY_FOR_BOUNDED_STDIO_SESSION"
    Write-Host "CAP=READY_FOR_BOUNDED_STDIO_SESSION"

    Write-Host "FIORI_PERSISTENT_PROCESS_EXPECTED=FALSE"
    Write-Host "UI5_PERSISTENT_PROCESS_EXPECTED=FALSE"
    Write-Host "CAP_PERSISTENT_PROCESS_EXPECTED=FALSE"

    Write-Host "SAP_BTP_ADMINISTRATION_MCP=DEFERRED"

    Write-Host "WATCHDOG_MODEL_CALLS=0"
    Write-Host "WATCHDOG_MCP_CALLS=0"
    Write-Host "WATCHDOG_SAP_CALLS=0"
    Write-Host "WATCHDOG_SAP_WRITES=0"
    Write-Host "WATCHDOG_BTP_CALLS=0"
    Write-Host "WATCHDOG_BTP_WRITES=0"

    Write-Host "=== END_MCP_WATCHDOG_STATUS ==="
}

function Invoke-Run {

    Assert-SelfSignature

    $providers =
        Resolve-ProviderBinaries

    if (-not (Test-Path $StateRoot)) {

        New-Item `
            -ItemType Directory `
            -Path $StateRoot `
            -Force |
            Out-Null
    }

    if (Test-Path $StopSignal) {
        Remove-Item $StopSignal -Force
    }

    $adtDownSince =
        $null

    $vsCodeBringupAttempted =
        $false

    while ($true) {

        if (Test-Path $StopSignal) {
            break
        }

        $adtLive =
            Test-Port -Port $AdtPort

        $vscode =
            @(
                Get-Process `
                    -Name "Code" `
                    -ErrorAction SilentlyContinue
            )

        $vscodeRunning =
            ($vscode.Count -gt 0)

        if ($adtLive) {

            $adtDownSince =
                $null
        }
        else {

            if ($null -eq $adtDownSince) {
                $adtDownSince = [DateTime]::UtcNow
            }

            if (
                -not $vscodeRunning -and
                -not $vsCodeBringupAttempted
            ) {

                try {

                    $code =
                        (Get-Command code -ErrorAction Stop).Source

                    Start-Process `
                        -FilePath $code `
                        -ArgumentList @(
                            "--reuse-window",
                            $Workspace
                        ) |
                        Out-Null

                    $vsCodeBringupAttempted =
                        $true

                    Write-Log "VSCODE_BRINGUP_REQUESTED"
                }
                catch {

                    Write-Log (
                        "VSCODE_BRINGUP_FAILED error={0}" -f
                        $_.Exception.Message
                    )
                }
            }
        }

        $recoveryRequired =
            $false

        if ($null -ne $adtDownSince) {

            $seconds =
                (
                    [DateTime]::UtcNow -
                    $adtDownSince
                ).TotalSeconds

            if ($seconds -ge 30) {
                $recoveryRequired = $true
            }
        }

        Write-State `
            -AdtLive $adtLive `
            -VsCodeRunning $vscodeRunning `
            -ExplicitRecoveryRequired $recoveryRequired `
            -ProviderPaths $providers

        Start-Sleep -Seconds 5
    }
}

function Start-Watchdog {

    Assert-SelfSignature

    if (-not (Test-Path $StateRoot)) {

        New-Item `
            -ItemType Directory `
            -Path $StateRoot `
            -Force |
            Out-Null
    }

    if (Test-Path $StatePath) {

        try {

            $existing =
                Get-Content $StatePath -Raw |
                ConvertFrom-Json

            if (
                Test-Pid `
                    -ProcessId ([int]$existing.watchdog_pid)
            ) {

                Write-Host "P8_MCP_WATCHDOG_R2_START=ALREADY_RUNNING"
                Show-Status
                return
            }
        }
        catch {
        }
    }

    if (Test-Path $StopSignal) {
        Remove-Item $StopSignal -Force
    }

    $pwsh =
        (Get-Command pwsh -ErrorAction Stop).Source

    $psi =
        [System.Diagnostics.ProcessStartInfo]::new()

    $psi.FileName = $pwsh

    $psi.ArgumentList.Add("-NoProfile")
    $psi.ArgumentList.Add("-ExecutionPolicy")
    $psi.ArgumentList.Add("Bypass")
    $psi.ArgumentList.Add("-File")
    $psi.ArgumentList.Add($PSCommandPath)
    $psi.ArgumentList.Add("-Mode")
    $psi.ArgumentList.Add("Run")

    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true

    $proc =
        [System.Diagnostics.Process]::Start($psi)

    if ($null -eq $proc) {
        throw "WATCHDOG_R2_START_FAILED"
    }

    $ready = $false

    for ($i = 0; $i -lt 30; $i++) {

        Start-Sleep -Milliseconds 500

        if (Test-Path $StatePath) {

            try {

                $state =
                    Get-Content $StatePath -Raw |
                    ConvertFrom-Json

                if (
                    [int]$state.watchdog_pid -eq
                    $proc.Id
                ) {

                    $ready = $true
                    break
                }
            }
            catch {
            }
        }

        if ($proc.HasExited) {

            throw (
                "WATCHDOG_R2_EXITED={0}" -f
                $proc.ExitCode
            )
        }
    }

    if (-not $ready) {
        throw "WATCHDOG_R2_START_TIMEOUT"
    }

    Write-Host "P8_MCP_WATCHDOG_R2_START=PASS"
    Write-Host "WATCHDOG_PID=$($proc.Id)"

    Show-Status
}

function Stop-Watchdog {

    if (-not (Test-Path $StateRoot)) {

        Write-Host "P8_MCP_WATCHDOG_R2_STOP=NOT_RUNNING"
        return
    }

    New-Item `
        -ItemType File `
        -Path $StopSignal `
        -Force |
        Out-Null

    if (Test-Path $StatePath) {

        try {

            $state =
                Get-Content $StatePath -Raw |
                ConvertFrom-Json

            $watchdogPid =
                [int]$state.watchdog_pid

            if (
                $watchdogPid -ne $PID -and
                (
                    Test-Pid `
                        -ProcessId $watchdogPid
                )
            ) {

                Start-Sleep -Seconds 1

                if (
                    Test-Pid `
                        -ProcessId $watchdogPid
                ) {

                    Stop-Process `
                        -Id $watchdogPid `
                        -Force
                }
            }
        }
        catch {
        }
    }

    Write-Host "P8_MCP_WATCHDOG_R2_STOP=PASS"
}

Assert-SelfSignature

switch ($Mode) {

    "Start" {
        Start-Watchdog
    }

    "Run" {
        Invoke-Run
    }

    "Status" {
        Show-Status
    }

    "Stop" {
        Stop-Watchdog
    }
}
# SIG # Begin signature block
# MIIHMAYJKoZIhvcNAQcCoIIHITCCBx0CAQExDzANBglghkgBZQMEAgEFADB5Bgor
# BgEEAYI3AgEEoGswaTA0BgorBgEEAYI3AgEeMCYCAwEAAAQQH8w7YFlLCE63JNLG
# KX7zUQIBAAIBAAIBAAIBAAIBADAxMA0GCWCGSAFlAwQCAQUABCCqLpNrK0J3Vy7P
# KYZXfpxyBIkFGlSZYm1GvKEWmkKX7KCCBBwwggQYMIICgKADAgECAhApojSr80YY
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
# MC8GCSqGSIb3DQEJBDEiBCDeOIt0KPSfmtNJXNf2UB64SaYd1wr5NtoKjbKP4CCy
# LzANBgkqhkiG9w0BAQEFAASCAYBFuSzr6ZKzEafn0cbm3ml062bMY92Ul03d84eH
# ipKoT9aYrUwQJxcJPCFUszcJdfftRhrVbyvv6zrsrVq20HI2jxVwOhRkGiB0WonM
# Z4vCpIS1H8+pvlXrK2nylz2r7fW921umi/jMO8rBu/F7j4gELnSCjp80zF5qa1+q
# roTtju7iN/IdOSzlVO8PKKwuqwkupMmUllFOE8t0iaAMYmL2cigxFgp1cZgY0AYS
# q90B4kKRCvDLxydbGg0C8MFcxJKf8WShwaohxp2kkFU179IF0lK1lp6+XSuTK2Yi
# xQMP8dAZ/nU3OtcA0IbY2fIeqbpL9zayywFGVDngdvPrs+DdCkyfV5FJ5D7NxG1Q
# yII9j7BXG8IDb5Ubcn9Oq8CdcFqa4awkftZcWPfHK+/8SczaiMt73KxKE/wdJx8f
# jUNaSyyQSXYD60KWr4Es5zi/UrJD3RDdaBqhvk2xKc/bNQpuudmcxWqs2vPLLQHt
# FVDeA2fsIZ3piqoqwFSDrCvI2K8=
# SIG # End signature block
