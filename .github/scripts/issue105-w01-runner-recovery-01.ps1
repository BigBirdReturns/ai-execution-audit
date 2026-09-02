#requires -Version 5.1
param(
    [string]$ReceiptPath = (Join-Path $PSScriptRoot 'RUNNER-RECOVERY-RECEIPT.json')
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$ExpectedQueuedRunId = 33612249992L
$ExpectedWorkflow = 'TEMP Issue 105 W01 Private Transfer Probe 04'

function Get-TextSha256([string]$Value) {
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Value)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        return 'sha256:' + (($sha.ComputeHash($bytes) | ForEach-Object { $_.ToString('x2') }) -join '')
    }
    finally {
        $sha.Dispose()
    }
}

function Write-Receipt([hashtable]$Receipt) {
    $Receipt | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $ReceiptPath -Encoding UTF8
}

$receipt = [ordered]@{
    schema = 'axm-private/issue105-w01-runner-recovery@1'
    status = 'HOLD'
    terminal = 'HOLD'
    reasonCode = 'NOT_STARTED'
    observedAtUtc = [DateTime]::UtcNow.ToString('o')
    expectedQueuedRunId = $ExpectedQueuedRunId
    expectedWorkflow = $ExpectedWorkflow
    matchingServiceCount = 0
    serviceNameRef = $null
    serviceImageRef = $null
    initialServiceState = $null
    finalServiceState = $null
    startMode = $null
    serviceStartAttempted = $false
    serviceConfigurationChanged = $false
    flightStateChanged = $false
    physicalExecutionObserved = $false
    browserLaunched = $false
    supplierEndpointContacted = $false
    modelDownloaded = $false
    rangeShardsDownloaded = 0
    peerConnectionFormed = $false
    inferenceExecuted = $false
    physicalMemberEvidenceAccepted = 0
    rawCapturesAccepted = 0
    namedHumanConfirmationSupplied = $false
    routeTerminalProduced = $false
    actualSupplierQualified = $false
    physicalEstateQualified = $false
    missionAuthority = 'none'
    commandAuthority = 'none'
}

try {
    $services = @(Get-CimInstance Win32_Service -ErrorAction Stop | Where-Object {
        $_.Name -like 'actions.runner.*' -or
        $_.DisplayName -like 'GitHub Actions Runner*' -or
        ([string]$_.PathName).Contains('RunnerService.exe')
    })
    $receipt.matchingServiceCount = $services.Count
    if ($services.Count -eq 0) {
        throw 'RUNNER_SERVICE_NOT_FOUND'
    }
    if ($services.Count -ne 1) {
        throw 'MULTIPLE_RUNNER_SERVICES_FOUND'
    }

    $service = $services[0]
    $receipt.serviceNameRef = Get-TextSha256 ([string]$service.Name)
    $receipt.serviceImageRef = Get-TextSha256 ([string]$service.PathName)
    $receipt.initialServiceState = [string]$service.State
    $receipt.finalServiceState = [string]$service.State
    $receipt.startMode = [string]$service.StartMode

    if ([string]$service.State -eq 'Running') {
        $receipt.status = 'PASS'
        $receipt.terminal = 'RUNNER_ALREADY_RUNNING'
        $receipt.reasonCode = $null
        Write-Receipt $receipt
        $receipt | ConvertTo-Json -Depth 20
        exit 0
    }
    if ([string]$service.StartMode -eq 'Disabled') {
        throw 'RUNNER_SERVICE_DISABLED'
    }

    $receipt.serviceStartAttempted = $true
    Start-Service -Name ([string]$service.Name) -ErrorAction Stop
    $deadline = [DateTime]::UtcNow.AddSeconds(30)
    do {
        Start-Sleep -Milliseconds 250
        $state = (Get-Service -Name ([string]$service.Name) -ErrorAction Stop).Status.ToString()
        $receipt.finalServiceState = $state
        if ($state -eq 'Running') {
            break
        }
    } while ([DateTime]::UtcNow -lt $deadline)

    if ($receipt.finalServiceState -ne 'Running') {
        throw 'RUNNER_SERVICE_START_TIMEOUT'
    }

    $receipt.status = 'PASS'
    $receipt.terminal = 'RUNNER_STARTED'
    $receipt.reasonCode = $null
    Write-Receipt $receipt
    $receipt | ConvertTo-Json -Depth 20
    exit 0
}
catch {
    $receipt.status = 'HOLD'
    $receipt.terminal = 'HOLD'
    $receipt.reasonCode = ([string]$_.Exception.Message).Split(':')[0]
    Write-Receipt $receipt
    $receipt | ConvertTo-Json -Depth 20
    exit 2
}
