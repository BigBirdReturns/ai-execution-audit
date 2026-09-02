#requires -Version 5.1
param(
    [string]$ReceiptRoot = (Join-Path $env:RUNNER_TEMP 'issue105-w01-private-transfer-probe-03'),
    [string]$ProbeScript = (Join-Path $PSScriptRoot 'issue105-w01-private-transfer-probe-01.ps1')
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

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

function Add-MaskedValue([string]$Value) {
    if (-not [string]::IsNullOrWhiteSpace($Value)) {
        Write-Output "::add-mask::$Value"
    }
}

function Read-ProbeReceipt([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw 'PROBE_RECEIPT_MISSING'
    }
    return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
}

function Invoke-Probe {
    if (-not (Test-Path -LiteralPath $ProbeScript -PathType Leaf)) {
        throw 'PROBE_SCRIPT_MISSING'
    }
    & $ProbeScript -ReceiptRoot $ReceiptRoot
    if ($LASTEXITCODE -ne 0) {
        throw "PROBE_SCRIPT_REFUSED:$LASTEXITCODE"
    }
    return Read-ProbeReceipt (Join-Path $ReceiptRoot 'receipt.json')
}

function Write-AugmentedReceipt($Receipt, [bool]$IngressUsed, [string]$IngressPathRef, [string]$IngressSourceRef) {
    $Receipt | Add-Member -NotePropertyName interactiveProfileIngressUsed -NotePropertyValue $IngressUsed -Force
    $Receipt | Add-Member -NotePropertyName ingressPathRef -NotePropertyValue $IngressPathRef -Force
    $Receipt | Add-Member -NotePropertyName ingressSourceRef -NotePropertyValue $IngressSourceRef -Force
    $Receipt | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath (Join-Path $ReceiptRoot 'receipt.json') -Encoding UTF8
}

function Assert-ZeroAuthority($Receipt) {
    if ($Receipt.physicalExecutionObserved -ne $false -or
        $Receipt.browserLaunched -ne $false -or
        $Receipt.supplierEndpointContacted -ne $false -or
        $Receipt.modelDownloaded -ne $false -or
        [int]$Receipt.rangeShardsDownloaded -ne 0 -or
        $Receipt.peerConnectionFormed -ne $false -or
        $Receipt.inferenceExecuted -ne $false -or
        $Receipt.routeTerminalProduced -ne $false -or
        $Receipt.actualSupplierQualified -ne $false -or
        $Receipt.physicalEstateQualified -ne $false -or
        $Receipt.missionAuthority -ne 'none' -or
        $Receipt.commandAuthority -ne 'none') {
        throw 'PROBE_AUTHORITY_BOUNDARY_INVALID'
    }
}

if ([string]::IsNullOrWhiteSpace($env:EXPECTED_ARCHIVE_NAME) -or
    [string]::IsNullOrWhiteSpace($env:EXPECTED_ARCHIVE_BYTES) -or
    [string]::IsNullOrWhiteSpace($env:EXPECTED_ARCHIVE_SHA256)) {
    throw 'EXPECTED_TRANSFER_IDENTITY_MISSING'
}

$expectedName = $env:EXPECTED_ARCHIVE_NAME
$expectedBytes = [int64]$env:EXPECTED_ARCHIVE_BYTES
$expectedSha = $env:EXPECTED_ARCHIVE_SHA256.ToLowerInvariant()

$first = Invoke-Probe
Assert-ZeroAuthority $first
if ($first.status -eq 'PASS' -or $first.reasonCode -ne 'PRIVATE_TRANSFER_NOT_SYNCED') {
    Write-AugmentedReceipt -Receipt $first -IngressUsed $false -IngressPathRef $null -IngressSourceRef $null
    exit 0
}

$candidateSet = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
function Add-Candidate([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) {
        return
    }
    try {
        $full = [System.IO.Path]::GetFullPath($Path)
        $null = $candidateSet.Add($full)
    }
    catch {
    }
}

$profileRoots = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
try {
    foreach ($profile in @(Get-CimInstance Win32_UserProfile -ErrorAction Stop)) {
        if (-not $profile.Special -and -not [string]::IsNullOrWhiteSpace([string]$profile.LocalPath)) {
            $null = $profileRoots.Add([System.IO.Path]::GetFullPath([string]$profile.LocalPath))
        }
    }
}
catch {
}

$usersRoot = Join-Path ([System.IO.Path]::GetPathRoot($env:SystemRoot)) 'Users'
if (Test-Path -LiteralPath $usersRoot -PathType Container) {
    foreach ($directory in @(Get-ChildItem -LiteralPath $usersRoot -Directory -Force -ErrorAction SilentlyContinue)) {
        if ($directory.Name -notin @('All Users', 'Default', 'Default User', 'Public')) {
            $null = $profileRoots.Add($directory.FullName)
        }
    }
}

foreach ($root in $profileRoots) {
    foreach ($relative in @(
        $expectedName,
        (Join-Path 'Downloads' $expectedName),
        (Join-Path 'Desktop' $expectedName),
        (Join-Path 'My Drive' $expectedName),
        (Join-Path 'Google Drive' $expectedName),
        (Join-Path 'Google Drive\My Drive' $expectedName),
        (Join-Path 'Drive' $expectedName),
        (Join-Path 'Documents' $expectedName)
    )) {
        Add-Candidate (Join-Path $root $relative)
    }
}

foreach ($root in @($env:AXM_PRIVATE_TRANSFER_ROOTS -split ';')) {
    if (-not [string]::IsNullOrWhiteSpace($root)) {
        Add-Candidate (Join-Path $root $expectedName)
    }
}

$exact = @()
$named = @()
foreach ($candidate in ($candidateSet | Sort-Object)) {
    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
        continue
    }
    if (Test-ReparseCoordinate $candidate) {
        continue
    }
    $item = Get-Item -LiteralPath $candidate -Force
    if ($item.Name -ne $expectedName) {
        continue
    }
    $named += $candidate
    if ($item.Length -ne $expectedBytes) {
        continue
    }
    $digest = (Get-FileHash -LiteralPath $candidate -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($digest -eq $expectedSha) {
        $exact += $candidate
    }
}

if ($exact.Count -eq 0) {
    $first.reasonCode = if ($named.Count -gt 0) { 'INTERACTIVE_TRANSFER_DIGEST_MISMATCH' } else { 'PRIVATE_TRANSFER_NOT_SYNCED' }
    Write-AugmentedReceipt -Receipt $first -IngressUsed $false -IngressPathRef $null -IngressSourceRef $null
    exit 0
}
if ($exact.Count -gt 1) {
    $first.reasonCode = 'MULTIPLE_EXACT_INTERACTIVE_TRANSFERS_PRESENT'
    Write-AugmentedReceipt -Receipt $first -IngressUsed $false -IngressPathRef $null -IngressSourceRef $null
    exit 0
}

$source = $exact[0]
Add-MaskedValue $source
$sourceRef = Get-TextSha256 $source

$selectedDrive = $null
foreach ($driveName in @('D', 'E', 'C')) {
    $drive = Get-PSDrive -Name $driveName -PSProvider FileSystem -ErrorAction SilentlyContinue
    if ($drive -and [int64]$drive.Free -ge ($expectedBytes + 1073741824)) {
        $selectedDrive = $drive
        break
    }
}
if (-not $selectedDrive) {
    $first.reasonCode = 'NO_SERVICE_VISIBLE_INGRESS_VOLUME'
    Write-AugmentedReceipt -Receipt $first -IngressUsed $false -IngressPathRef $null -IngressSourceRef $sourceRef
    exit 0
}

$staged = Join-Path $selectedDrive.Root $expectedName
Add-MaskedValue $staged
if (Test-ReparseCoordinate $staged) {
    throw 'INGRESS_COORDINATE_LINKED'
}

$stagedCreated = $false
if (Test-Path -LiteralPath $staged -PathType Leaf) {
    $existing = Get-Item -LiteralPath $staged -Force
    $existingDigest = if ($existing.Length -eq $expectedBytes) {
        (Get-FileHash -LiteralPath $staged -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    else {
        ''
    }
    if ($existingDigest -ne $expectedSha) {
        $first.reasonCode = 'SERVICE_VISIBLE_INGRESS_COLLISION'
        Write-AugmentedReceipt -Receipt $first -IngressUsed $false -IngressPathRef (Get-TextSha256 $staged) -IngressSourceRef $sourceRef
        exit 0
    }
}
else {
    $temporary = "$staged.part-$([Guid]::NewGuid().ToString('N'))"
    Add-MaskedValue $temporary
    Copy-Item -LiteralPath $source -Destination $temporary -Force
    $temporaryItem = Get-Item -LiteralPath $temporary -Force
    $temporaryDigest = (Get-FileHash -LiteralPath $temporary -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($temporaryItem.Length -ne $expectedBytes -or $temporaryDigest -ne $expectedSha) {
        Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue
        throw 'INGRESS_COPY_IDENTITY_MISMATCH'
    }
    Move-Item -LiteralPath $temporary -Destination $staged
    $stagedCreated = $true
}

$second = Invoke-Probe
Assert-ZeroAuthority $second
if ($second.status -ne 'PASS' -and $stagedCreated) {
    $second | Add-Member -NotePropertyName ingressRetainedForRetry -NotePropertyValue $true -Force
}
Write-AugmentedReceipt -Receipt $second -IngressUsed $true -IngressPathRef (Get-TextSha256 $staged) -IngressSourceRef $sourceRef
exit 0
