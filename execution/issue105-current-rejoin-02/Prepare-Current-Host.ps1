#requires -Version 5.1
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('W01', 'L01')]
    [string]$HostRole,
    [string]$PacketRoot = $PSScriptRoot,
    [string]$OutputRoot = '',
    [string]$ReceiptPath = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$ExpectedMainCommit = '3c11dbca48ae777137675bb9bf485f0c42daf7a4'
$ExpectedReleaseName = 'AXM-Issue-105-Browser-Physical-Audition-Flight-Package-03-Release.zip'
$ExpectedReleaseBytes = 3438484L
$ExpectedReleaseSha256 = '884630ee32a75545373bc88b725c976cc1e61bffd240315a14afea81c20e6d09'
$ExpectedReleaseId = 'axmbrowserphysicalflightrelease_48bded1a98f703e2a044765bcd786b82eb9c097c26a43bc420945f97f074e566'
$ExpectedPackageId = 'axmbrowserphysicalflightpackage_812d83141a0f339f0ada89339a5ba98f375c788a3aafdbd91aaa2bb450929a19'
$ExpectedTransactionId = 'axmbrowserphysicalrun_b90f76feb0a7324dac7fbd8780a7079a8123c85cdf4a06233467e675803722dc'
$ExpectedPreparedName = 'axm-head-browser-physical-audition-flight-105-prepared-003.zip'
$ExpectedPreparedBytes = 158969L
$ExpectedPreparedSha256 = '5d95d479c4834eccf2c3b9d0ffc365f94584a5989360f335f0725149d4fa360c'
$Seat = if ($HostRole -eq 'W01') {
    [ordered]@{
        Id = 'seat-02'
        CapsuleId = 'axmbrowserphysicalseatcapsule_d9898cb5ff6df1c9312d80bed0851985c634fb395e6ec63cc1469ab9851c6df6'
        Bytes = 36335L
        Sha256 = '0f6211976f03260d2c645c613e8ba690de83e72fbac9e7d4a5320f6952cdf491'
        Terminal = 'W01_CURRENT_CONTROLLER_AND_SEAT02_PREPARED'
    }
} else {
    [ordered]@{
        Id = 'seat-01'
        CapsuleId = 'axmbrowserphysicalseatcapsule_5dc5e85984afb654dfc353731f2e3822807db98884d88cfb2a3cb5b3bf18b024'
        Bytes = 36337L
        Sha256 = '5e06e8d9f5b3ec69dd1e9db1f68b0630042cd58dea730aa56aba6ec4c23670bb'
        Terminal = 'L01_CURRENT_SEAT01_PREPARED'
    }
}

function Get-TextSha256([string]$Value) {
    $Bytes = [Text.Encoding]::UTF8.GetBytes($Value)
    $Sha = [Security.Cryptography.SHA256]::Create()
    try { return 'sha256:' + (($Sha.ComputeHash($Bytes) | ForEach-Object { $_.ToString('x2') }) -join '') }
    finally { $Sha.Dispose() }
}

function Get-FileSha256([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Test-ReparseCoordinate([string]$Path) {
    $Cursor = [IO.Path]::GetFullPath($Path)
    while ($Cursor) {
        if (Test-Path -LiteralPath $Cursor) {
            $Item = Get-Item -LiteralPath $Cursor -Force
            if (($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { return $true }
        }
        $Parent = Split-Path -Parent $Cursor
        if (-not $Parent -or $Parent -eq $Cursor) { break }
        $Cursor = $Parent
    }
    return $false
}

function Resolve-Python311 {
    foreach ($Candidate in @(
        @{ File = 'python'; Prefix = @() },
        @{ File = 'python3'; Prefix = @() },
        @{ File = 'py'; Prefix = @('-3') }
    )) {
        try {
            & $Candidate.File @($Candidate.Prefix) -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 2)" 2>$null
            if ($LASTEXITCODE -eq 0) { return $Candidate }
        } catch { }
    }
    throw 'PYTHON_311_NOT_FOUND'
}

function Assert-ExactFile([string]$Path, [int64]$Bytes, [string]$Sha256, [string]$Code) {
    if (Test-ReparseCoordinate $Path) { throw "${Code}_COORDINATE_LINKED" }
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "${Code}_MISSING" }
    $Item = Get-Item -LiteralPath $Path -Force
    if ($Item.Length -ne $Bytes -or (Get-FileSha256 $Path) -ne $Sha256) { throw "${Code}_IDENTITY_INVALID" }
}

function Write-Receipt($Value) {
    $Parent = Split-Path -Parent $ReceiptPath
    if ($Parent) { New-Item -ItemType Directory -Path $Parent -Force | Out-Null }
    $Value | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath $ReceiptPath -Encoding UTF8
}

$PacketRoot = [IO.Path]::GetFullPath($PacketRoot)
if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $Selected = $null
    foreach ($Name in @('D', 'E', 'C')) {
        $Drive = Get-PSDrive -Name $Name -PSProvider FileSystem -ErrorAction SilentlyContinue
        if ($Drive -and [int64]$Drive.Free -ge 1073741824L) { $Selected = $Drive; break }
    }
    if (-not $Selected) { throw 'NO_PERSISTENT_VOLUME_WITH_1GIB_FREE' }
    $OutputRoot = if ($Selected.Name -eq 'C') {
        Join-Path $env:ProgramData "AXM\Issue-105\current-rejoin-02\$HostRole"
    } else {
        Join-Path $Selected.Root "AXM\Issue-105\current-rejoin-02\$HostRole"
    }
}
$OutputRoot = [IO.Path]::GetFullPath($OutputRoot)
if ([string]::IsNullOrWhiteSpace($ReceiptPath)) {
    $ReceiptPath = Join-Path $OutputRoot "ISSUE105-$HostRole-PREPARATION-RECEIPT.json"
}
$ReceiptPath = [IO.Path]::GetFullPath($ReceiptPath)

$IdentityPath = Join-Path $PacketRoot 'ISSUE105-CURRENT-IDENTITY-JOIN.json'
$PackagePath = Join-Path $PacketRoot 'PACKAGE.json'
$ReleasePath = Join-Path $PacketRoot $ExpectedReleaseName
$VerifierPath = Join-Path $PacketRoot 'verify_current_rejoin_packet.py'
$PreparerPath = Join-Path $PacketRoot 'Prepare-Current-Host.ps1'

$MachineGuid = 'unavailable'
try { $MachineGuid = (Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Cryptography' -Name MachineGuid).MachineGuid }
catch { }
$HostRef = Get-TextSha256 ("{0}|{1}|{2}" -f $env:COMPUTERNAME, $env:PROCESSOR_ARCHITECTURE, $MachineGuid)
$Receipt = [ordered]@{
    schema = 'axm-private/issue105-current-host-preparation@1'
    status = 'HOLD'
    terminal = 'HOLD'
    reasonCode = 'NOT_STARTED'
    observedAtUtc = [DateTime]::UtcNow.ToString('o')
    requestedHostRole = $HostRole
    hostRef = $HostRef
    hardwareClassMatched = $false
    preparerSha256 = 'sha256:' + (Get-FileSha256 $PreparerPath)
    identityJoinId = $null
    rejoinPacketId = $null
    repositoryMainCommit = $ExpectedMainCommit
    releaseId = $ExpectedReleaseId
    packageId = $ExpectedPackageId
    transactionId = $ExpectedTransactionId
    seatId = $Seat.Id
    capsuleId = $Seat.CapsuleId
    capsuleArchiveSha256 = 'sha256:' + $Seat.Sha256
    persistentRootRef = Get-TextSha256 $OutputRoot
    persistenceScope = 'HOST_LOCAL_OUTSIDE_TRANSPORT_STAGE'
    persistentMaterialVerifiedAfterPrepare = $false
    preparedRoles = @()
    browserSeatsPhysicallyOperated = 0
    browserLaunched = $false
    supplierEndpointContacted = $false
    modelDownloadedByThisTransaction = $false
    rangeShardsDownloaded = 0
    peerConnectionFormed = $false
    inferenceExecuted = $false
    physicalMemberEvidenceAccepted = 0
    rawCapturesAccepted = 0
    namedHumanConfirmationSupplied = $false
    routeTerminalProduced = $false
    actualSupplierQualified = $false
    physicalEstateQualified = $false
    physicalUniquenessProved = $false
    missionAuthority = 'none'
    commandAuthority = 'none'
}

try {
    if ((Test-ReparseCoordinate $PacketRoot) -or (Test-ReparseCoordinate $OutputRoot)) { throw 'ROOT_COORDINATE_LINKED' }
    foreach ($Path in @($IdentityPath, $PackagePath, $VerifierPath, $PreparerPath)) {
        if (-not (Test-Path -LiteralPath $Path -PathType Leaf) -or (Test-ReparseCoordinate $Path)) { throw 'PACKET_SOURCE_INCOMPLETE' }
    }
    Assert-ExactFile $ReleasePath $ExpectedReleaseBytes $ExpectedReleaseSha256 'CURRENT_RELEASE'
    $Python = Resolve-Python311
    $VerifyText = & $Python.File @($Python.Prefix) $VerifierPath $PacketRoot 2>&1
    if ($LASTEXITCODE -ne 0) { throw 'CURRENT_REJOIN_PACKET_REFUSED' }
    $Verify = ($VerifyText -join "`n") | ConvertFrom-Json
    if ($Verify.status -ne 'PASS') { throw 'CURRENT_REJOIN_VERDICT_INVALID' }
    $Identity = Get-Content -LiteralPath $IdentityPath -Raw | ConvertFrom-Json
    $Package = Get-Content -LiteralPath $PackagePath -Raw | ConvertFrom-Json
    if ($Identity.status -ne 'PASS' -or
        $Identity.identityBody.repository.mainCommit -ne $ExpectedMainCommit -or
        $Identity.identityBody.privateCarrier.releaseId -ne $ExpectedReleaseId -or
        $Identity.identityBody.privateCarrier.preparedTransactionId -ne $ExpectedTransactionId -or
        $Package.identityJoinId -ne $Identity.identityJoinId -or
        $Package.packetId -ne $Verify.packetId) {
        throw 'CURRENT_IDENTITY_JOIN_INVALID'
    }
    $Receipt.identityJoinId = [string]$Identity.identityJoinId
    $Receipt.rejoinPacketId = [string]$Package.packetId

    $GpuNames = @()
    try { $GpuNames = @(Get-CimInstance Win32_VideoController | ForEach-Object { [string]$_.Name }) } catch { }
    $Receipt.hardwareClassMatched = if ($HostRole -eq 'W01') {
        @($GpuNames | Where-Object { $_ -match 'RTX\s*4060' }).Count -gt 0
    } else {
        @($GpuNames | Where-Object { $_ -match 'RTX\s*3090' }).Count -gt 0
    }
    if (-not $Receipt.hardwareClassMatched) { throw "HOST_NOT_$($HostRole)_HARDWARE_CLASS" }

    New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null
    $Temporary = Join-Path $OutputRoot ('.staging-' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $Temporary | Out-Null
    try {
        Expand-Archive -LiteralPath $ReleasePath -DestinationPath $Temporary -Force
        $ReleaseRoots = @(Get-ChildItem -LiteralPath $Temporary -Directory -Force)
        if ($ReleaseRoots.Count -ne 1) { throw 'CURRENT_RELEASE_ROOT_DENOMINATOR_INVALID' }
        $ReleaseRoot = $ReleaseRoots[0].FullName
        $InnerVerify = Join-Path $ReleaseRoot 'verification\verify_release.py'
        $InnerText = & $Python.File @($Python.Prefix) $InnerVerify $ReleaseRoot 2>&1
        if ($LASTEXITCODE -ne 0) { throw 'CURRENT_RELEASE_VERIFIER_REFUSED' }
        $Inner = ($InnerText -join "`n") | ConvertFrom-Json
        if ($Inner.status -ne 'PASS' -or $Inner.releaseId -ne $ExpectedReleaseId -or $Inner.transactionId -ne $ExpectedTransactionId) {
            throw 'CURRENT_RELEASE_VERDICT_INVALID'
        }
        $PreparedPath = Join-Path $ReleaseRoot "artifacts\$ExpectedPreparedName"
        Assert-ExactFile $PreparedPath $ExpectedPreparedBytes $ExpectedPreparedSha256 'PREPARED_TRANSACTION'
        $PreparedStage = Join-Path $Temporary 'prepared'
        Expand-Archive -LiteralPath $PreparedPath -DestinationPath $PreparedStage -Force
        $PreparedRoots = @(Get-ChildItem -LiteralPath $PreparedStage -Directory -Force)
        if ($PreparedRoots.Count -ne 1) { throw 'PREPARED_ROOT_DENOMINATOR_INVALID' }
        $CapsulePath = Join-Path $PreparedRoots[0].FullName "flight-private\seat-capsules\$($Seat.Id).zip"
        Assert-ExactFile $CapsulePath $Seat.Bytes $Seat.Sha256 'SEAT_CAPSULE'

        $PreparedRoles = @()
        if ($HostRole -eq 'W01') {
            $ControllerRoot = Join-Path $OutputRoot 'controller'
            New-Item -ItemType Directory -Path $ControllerRoot -Force | Out-Null
            $ControllerRelease = Join-Path $ControllerRoot $ExpectedReleaseName
            if (Test-Path -LiteralPath $ControllerRelease) {
                Assert-ExactFile $ControllerRelease $ExpectedReleaseBytes $ExpectedReleaseSha256 'EXISTING_CONTROLLER_RELEASE'
                $ControllerState = 'REUSED_EXACT'
            } else {
                Copy-Item -LiteralPath $ReleasePath -Destination $ControllerRelease
                Assert-ExactFile $ControllerRelease $ExpectedReleaseBytes $ExpectedReleaseSha256 'STAGED_CONTROLLER_RELEASE'
                $ControllerState = 'PREPARED'
            }
            Copy-Item -LiteralPath $IdentityPath -Destination (Join-Path $ControllerRoot 'ISSUE105-CURRENT-IDENTITY-JOIN.json') -Force
            $PreparedRoles += [ordered]@{ role = 'controller'; state = $ControllerState; destinationRef = Get-TextSha256 $ControllerRoot }
        }
        $SeatRoot = Join-Path $OutputRoot $Seat.Id
        New-Item -ItemType Directory -Path $SeatRoot -Force | Out-Null
        $SeatDestination = Join-Path $SeatRoot "$($Seat.Id).zip"
        if (Test-Path -LiteralPath $SeatDestination) {
            Assert-ExactFile $SeatDestination $Seat.Bytes $Seat.Sha256 'EXISTING_SEAT_CAPSULE'
            $SeatState = 'REUSED_EXACT'
        } else {
            Copy-Item -LiteralPath $CapsulePath -Destination $SeatDestination
            Assert-ExactFile $SeatDestination $Seat.Bytes $Seat.Sha256 'STAGED_SEAT_CAPSULE'
            $SeatState = 'PREPARED'
        }
        $PreparedRoles += [ordered]@{ role = $Seat.Id; state = $SeatState; destinationRef = Get-TextSha256 $SeatRoot }
        $Receipt.preparedRoles = $PreparedRoles
    } finally {
        if (Test-Path -LiteralPath $Temporary) { Remove-Item -LiteralPath $Temporary -Recurse -Force }
    }
    if ($HostRole -eq 'W01') {
        Assert-ExactFile $ControllerRelease $ExpectedReleaseBytes $ExpectedReleaseSha256 'PERSISTENT_CONTROLLER_RELEASE'
    }
    Assert-ExactFile $SeatDestination $Seat.Bytes $Seat.Sha256 'PERSISTENT_SEAT_CAPSULE'
    $Receipt.persistentMaterialVerifiedAfterPrepare = $true
    $Receipt.status = 'PASS'
    $Receipt.terminal = $Seat.Terminal
    $Receipt.reasonCode = $null
    Write-Receipt $Receipt
    $Receipt | ConvertTo-Json -Depth 40
    exit 0
} catch {
    $Receipt.status = 'HOLD'
    $Receipt.terminal = 'HOLD'
    $Receipt.reasonCode = ([string]$_.Exception.Message).Split(':')[0]
    Write-Receipt $Receipt
    $Receipt | ConvertTo-Json -Depth 40
    exit 2
}
