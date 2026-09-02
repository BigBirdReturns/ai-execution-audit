#requires -Version 5.1
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('W01', 'L01')]
    [string]$HostRole,
    [string]$BootstrapArchive = (Join-Path $PSScriptRoot 'AXM-Issue-105-Physical-Flight-Bootstrap-03.zip'),
    [string]$ReceiptPath = (Join-Path $PSScriptRoot 'HOST-PREPARATION-RECEIPT.json')
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$ExpectedArchiveName = 'AXM-Issue-105-Physical-Flight-Bootstrap-03.zip'
$ExpectedArchiveBytes = 33026569L
$ExpectedArchiveSha256 = '435a44defad35aa3abd7b67c281f543aae7225efc0351bae05f5d7ae378b98c0'
$ExpectedBootstrapId = 'axmswarmllmflightbootstrap_ed0110be1bac6030490751a098b37e83ce2edf7b460c9efb77eb83c194d6ca7b'
$ExpectedReleaseId = 'axmswarmllmexactcustodyrelease_6948e34bcdd927819b21b5ffaed97c4c287dff23d30dc5a10b12162d9e4e6f7b'
$ExpectedWorkspaceId = 'axmswarmllmvenueobserverworkspace_ed63f5fe5425e19f3f83287da7df60444d76f1089b4d2b8cf42aa24cda277994'
$ExpectedCustodyPlanId = 'axmswarmllmcustodyplan_17c7d340d72ed5d8b707aca3ba6efe91a89564938f310bf76c7ba2f77610c162'
$ExpectedTransactionId = 'axmbrowserphysicalrun_39c742fdf6f8108d750adc3d4e0629b53acb9749e27f7d217679c0fa84553474'
$MinimumFreeBytes = 23622320128L

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

function Test-ReparseCoordinate([string]$Path) {
    $cursor = [System.IO.Path]::GetFullPath($Path)
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            $item = Get-Item -LiteralPath $cursor -Force
            if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                return $true
            }
        }
        $parent = Split-Path -Parent $cursor
        if (-not $parent -or $parent -eq $cursor) {
            break
        }
        $cursor = $parent
    }
    return $false
}

function Write-Receipt([hashtable]$Receipt) {
    $Receipt | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $ReceiptPath -Encoding UTF8
}

function Resolve-Python311 {
    $candidates = @(
        @{ File = 'python'; Prefix = @() },
        @{ File = 'python3'; Prefix = @() },
        @{ File = 'py'; Prefix = @('-3') }
    )
    foreach ($candidate in $candidates) {
        try {
            $null = & $candidate.File @($candidate.Prefix) -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 2)" 2>$null
            if ($LASTEXITCODE -eq 0) {
                return $candidate
            }
        }
        catch {
            continue
        }
    }
    throw 'PYTHON_311_NOT_FOUND'
}

function Invoke-BootstrapJson {
    param(
        [hashtable]$Python,
        [string]$Script,
        [string[]]$Arguments
    )
    $lines = & $Python.File @($Python.Prefix) $Script @Arguments 2>&1
    $code = $LASTEXITCODE
    $text = ($lines -join "`n")
    if ($code -ne 0) {
        throw "BOOTSTRAP_COMMAND_REFUSED:$code"
    }
    return $text | ConvertFrom-Json
}

function Assert-ZeroAuthority($Value, [string]$Label) {
    if ($Value.physicalExecutionObserved -ne $false -or
        $Value.actualSupplierQualified -ne $false -or
        $Value.physicalEstateQualified -ne $false -or
        $Value.missionAuthority -ne 'none' -or
        $Value.commandAuthority -ne 'none') {
        throw "${Label}_AUTHORITY_BOUNDARY_INVALID"
    }
}

$machineGuid = 'unavailable'
try {
    $machineGuid = (Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Cryptography' -Name MachineGuid).MachineGuid
}
catch {
    $machineGuid = 'unavailable'
}
$hostRef = Get-TextSha256 ("{0}|{1}|{2}" -f $env:COMPUTERNAME, $env:PROCESSOR_ARCHITECTURE, $machineGuid)

$receipt = [ordered]@{
    schema = 'axm-private/issue105-final-host-preparation@1'
    status = 'HOLD'
    terminal = 'HOLD'
    reasonCode = 'NOT_STARTED'
    observedAtUtc = [DateTime]::UtcNow.ToString('o')
    requestedHostRole = $HostRole
    hostRef = $hostRef
    bootstrapId = $ExpectedBootstrapId
    releaseId = $ExpectedReleaseId
    workspaceId = $ExpectedWorkspaceId
    custodyPlanId = $ExpectedCustodyPlanId
    transactionId = $ExpectedTransactionId
    archiveBytes = $ExpectedArchiveBytes
    archiveSha256 = 'sha256:' + $ExpectedArchiveSha256
    persistentRootRef = $null
    preparedRoles = @()
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
    $archive = [System.IO.Path]::GetFullPath($BootstrapArchive)
    if (Test-ReparseCoordinate $archive) {
        throw 'BOOTSTRAP_ARCHIVE_COORDINATE_LINKED'
    }
    if (-not (Test-Path -LiteralPath $archive -PathType Leaf)) {
        throw 'BOOTSTRAP_ARCHIVE_MISSING'
    }
    $archiveItem = Get-Item -LiteralPath $archive -Force
    if ($archiveItem.Name -ne $ExpectedArchiveName -or $archiveItem.Length -ne $ExpectedArchiveBytes) {
        throw 'BOOTSTRAP_ARCHIVE_DENOMINATOR_INVALID'
    }
    $archiveDigest = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($archiveDigest -ne $ExpectedArchiveSha256) {
        throw 'BOOTSTRAP_ARCHIVE_SHA256_INVALID'
    }

    $selectedDrive = $null
    foreach ($driveName in @('D', 'E', 'C')) {
        $drive = Get-PSDrive -Name $driveName -PSProvider FileSystem -ErrorAction SilentlyContinue
        if ($drive -and [int64]$drive.Free -ge $MinimumFreeBytes) {
            $selectedDrive = $drive
            break
        }
    }
    if (-not $selectedDrive) {
        throw 'NO_PERSISTENT_VOLUME_WITH_22GIB_FREE'
    }

    $baseRoot = if ($selectedDrive.Name -eq 'C') {
        Join-Path $env:ProgramData 'AXM\Issue-105'
    }
    else {
        Join-Path $selectedDrive.Root 'AXM\Issue-105'
    }
    if (Test-ReparseCoordinate $baseRoot) {
        throw 'PERSISTENT_ROOT_LINKED'
    }
    $receipt.persistentRootRef = Get-TextSha256 $baseRoot
    New-Item -ItemType Directory -Path $baseRoot -Force | Out-Null

    $sourceRoot = Join-Path $baseRoot 'bootstrap-03-source'
    if (Test-ReparseCoordinate $sourceRoot) {
        throw 'BOOTSTRAP_SOURCE_COORDINATE_LINKED'
    }
    if (-not (Test-Path -LiteralPath $sourceRoot -PathType Container)) {
        $staging = "$sourceRoot.staging-$([Guid]::NewGuid().ToString('N'))"
        Expand-Archive -LiteralPath $archive -DestinationPath $staging -Force
        Move-Item -LiteralPath $staging -Destination $sourceRoot
    }

    $bootstrapJsonPath = Join-Path $sourceRoot 'BOOTSTRAP.json'
    $script = Join-Path $sourceRoot 'flight_bootstrap.py'
    if (-not (Test-Path -LiteralPath $bootstrapJsonPath -PathType Leaf) -or
        -not (Test-Path -LiteralPath $script -PathType Leaf)) {
        throw 'BOOTSTRAP_SOURCE_INCOMPLETE'
    }

    $bootstrapJson = Get-Content -LiteralPath $bootstrapJsonPath -Raw | ConvertFrom-Json
    if ($bootstrapJson.bootstrapId -ne $ExpectedBootstrapId -or
        $bootstrapJson.releaseId -ne $ExpectedReleaseId -or
        $bootstrapJson.workspaceId -ne $ExpectedWorkspaceId -or
        $bootstrapJson.custodyPlanId -ne $ExpectedCustodyPlanId -or
        $bootstrapJson.transactionId -ne $ExpectedTransactionId) {
        throw 'BOOTSTRAP_SOURCE_IDENTITY_INVALID'
    }

    $python = Resolve-Python311
    $verified = Invoke-BootstrapJson -Python $python -Script $script -Arguments @('verify-bundle')
    if ($verified.status -ne 'PASS' -or $verified.bootstrapId -ne $ExpectedBootstrapId) {
        throw 'BOOTSTRAP_VERIFICATION_RESULT_INVALID'
    }
    Assert-ZeroAuthority $verified 'BOOTSTRAP_VERIFICATION'

    $roles = if ($HostRole -eq 'W01') { @('controller', 'seat-02') } else { @('seat-01') }
    $preparedRoles = @()
    foreach ($role in $roles) {
        $destination = Join-Path $baseRoot $role
        if (Test-ReparseCoordinate $destination) {
            throw "ROLE_COORDINATE_LINKED:$role"
        }
        if (Test-Path -LiteralPath $destination) {
            $status = Invoke-BootstrapJson -Python $python -Script $script -Arguments @('status', $destination)
            if ($status.workspaceId -ne $ExpectedWorkspaceId -or
                $status.custodyPlanId -ne $ExpectedCustodyPlanId -or
                $status.transactionId -ne $ExpectedTransactionId -or
                $status.routeTerminalProduced -ne $false) {
                throw "ROLE_PREEXISTING_STATUS_MISMATCH:$role"
            }
            Assert-ZeroAuthority $status "ROLE_PREEXISTING_$role"
            $preparedRoles += [ordered]@{ role = $role; state = 'REUSED_EXACT'; destinationRef = Get-TextSha256 $destination }
            continue
        }
        $prepared = Invoke-BootstrapJson -Python $python -Script $script -Arguments @('prepare-role', $role, $destination)
        if ($prepared.status -ne 'PASS' -or
            $prepared.bootstrapId -ne $ExpectedBootstrapId -or
            $prepared.releaseId -ne $ExpectedReleaseId -or
            $prepared.workspaceId -ne $ExpectedWorkspaceId -or
            $prepared.role -ne $role -or
            $prepared.qwen38Status -ne 'PREPARED_FOR_EXACT_RANGE_CUSTODY') {
            throw "ROLE_PREPARATION_RESULT_INVALID:$role"
        }
        Assert-ZeroAuthority $prepared "ROLE_PREPARATION_$role"
        $preparedRoles += [ordered]@{ role = $role; state = 'PREPARED'; destinationRef = Get-TextSha256 $destination }
    }

    $receipt.preparedRoles = $preparedRoles
    $receipt.status = 'PASS'
    $receipt.terminal = if ($HostRole -eq 'W01') { 'W01_CONTROLLER_AND_SEAT02_PREPARED' } else { 'L01_SEAT01_PREPARED' }
    $receipt.reasonCode = $null
    Write-Receipt $receipt
    $receipt | ConvertTo-Json -Depth 30
    exit 0
}
catch {
    $receipt.status = 'HOLD'
    $receipt.terminal = 'HOLD'
    $receipt.reasonCode = ([string]$_.Exception.Message).Split(':')[0]
    Write-Receipt $receipt
    $receipt | ConvertTo-Json -Depth 30
    exit 2
}
