#requires -Version 5.1
param(
    [string]$ReceiptRoot = (Join-Path $env:RUNNER_TEMP 'issue105-w01-range-custody-03')
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$ExpectedArchiveName = 'AXM-Issue-105-Range-Custody-Transaction-03.zip'
$ExpectedArchiveBytes = 10673635L
$ExpectedArchiveSha256 = '3d098e96f68b7a080faca888d5c5d11d755bfe5024239fb9faa3381cbc3dbfa4'
$ExpectedTransactionId = 'axmissue105rangecustodytransaction_d04361beed3870611380cfb9a8141e82077c1f95d759a89cadf3ea2aef5877d9'
$ExpectedPackageId = 'axmissue105onerunnertwohostpackage_0f05332460544ddfc40499aa83825da0a5235621d9227a259abb543e992e0101'
$ExpectedRangeSourceSha256 = 'a1c4ed9316811275ebf09f9766cd9ab86bb63fa0a2b5b367edb6c7ec388bd0dc'
$ExpectedHostedRun = 33688952874L
$ExpectedPayloadBytes = 15780284416L
$MinimumFreeBytes = 32212254720L

function Get-TextSha256([string]$Value) {
    $Bytes = [Text.Encoding]::UTF8.GetBytes($Value)
    $Sha = [Security.Cryptography.SHA256]::Create()
    try {
        return 'sha256:' + (($Sha.ComputeHash($Bytes) | ForEach-Object { $_.ToString('x2') }) -join '')
    }
    finally {
        $Sha.Dispose()
    }
}

function Get-FileSha256([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Test-ReparseCoordinate([string]$Path) {
    $Cursor = [IO.Path]::GetFullPath($Path)
    while ($Cursor) {
        if (Test-Path -LiteralPath $Cursor) {
            $Item = Get-Item -LiteralPath $Cursor -Force
            if (($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                return $true
            }
        }
        $Parent = Split-Path -Parent $Cursor
        if (-not $Parent -or $Parent -eq $Cursor) {
            break
        }
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
            if ($LASTEXITCODE -eq 0) {
                return $Candidate
            }
        }
        catch {
        }
    }
    throw 'PYTHON_311_NOT_FOUND'
}

function Write-Json([string]$Path, $Value) {
    $Value | ConvertTo-Json -Depth 60 | Set-Content -LiteralPath $Path -Encoding UTF8
}

function Add-MaskedValue([string]$Value) {
    if (-not [string]::IsNullOrWhiteSpace($Value)) {
        Write-Output "::add-mask::$Value"
    }
}

function Add-CandidatePath($Set, [string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) {
        return
    }
    try {
        $null = $Set.Add([IO.Path]::GetFullPath($Path))
    }
    catch {
    }
}

function Update-SummaryFromOperation($Summary, $Operation) {
    foreach ($Name in @(
        'hostPreparationAttempted',
        'w01RangeDownloadAttempted',
        'l01RangeDownloadAttempted',
        'remoteHelperTransferred',
        'remoteCommandExecuted',
        'remoteReceiptRetrieved',
        'remoteCleanupCompleted',
        'remoteStageRetainedForRetry',
        'modelArtifactEndpointContactConfirmed',
        'modelDownloaded',
        'physicalExecutionObserved',
        'browserLaunched',
        'supplierEndpointContacted',
        'peerConnectionFormed',
        'inferenceExecuted',
        'namedHumanConfirmationSupplied',
        'routeTerminalProduced',
        'actualSupplierQualified',
        'physicalEstateQualified'
    )) {
        if ($null -ne $Operation.PSObject.Properties[$Name]) {
            $Summary[$Name] = $Operation.$Name
        }
    }
    foreach ($Name in @('rangeShardsDownloaded', 'rangePayloadBytes', 'physicalMemberEvidenceAccepted', 'rawCapturesAccepted')) {
        if ($null -ne $Operation.PSObject.Properties[$Name]) {
            $Summary[$Name] = [int64]$Operation.$Name
        }
    }
    foreach ($Name in @(
        'hostPreparationReceiptRef',
        'w01RangeReceiptRef',
        'l01RangeReceiptRef',
        'w01LaunchCommandReceiptRef',
        'l01LaunchCommandReceiptRef',
        'finalRangeJoinReceiptRef'
    )) {
        if ($null -ne $Operation.PSObject.Properties[$Name]) {
            $Summary[$Name] = [string]$Operation.$Name
        }
    }
    if ($null -ne $Operation.PSObject.Properties['missionAuthority']) {
        $Summary.missionAuthority = [string]$Operation.missionAuthority
    }
    if ($null -ne $Operation.PSObject.Properties['commandAuthority']) {
        $Summary.commandAuthority = [string]$Operation.commandAuthority
    }
}

if (Test-Path -LiteralPath $ReceiptRoot) {
    Remove-Item -LiteralPath $ReceiptRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $ReceiptRoot -Force | Out-Null
$SummaryPath = Join-Path $ReceiptRoot 'PUBLIC-SUMMARY.json'

$SourcePath = [string]$MyInvocation.MyCommand.Path
$Summary = [ordered]@{
    schema = 'axm-private/issue105-w01-range-custody-summary@3'
    status = 'HOLD'
    terminal = 'HOLD'
    reasonCode = 'NOT_STARTED'
    observedAtUtc = [DateTime]::UtcNow.ToString('o')
    expectedArchiveName = $ExpectedArchiveName
    expectedArchiveBytes = $ExpectedArchiveBytes
    expectedArchiveSha256 = 'sha256:' + $ExpectedArchiveSha256
    transactionId = $ExpectedTransactionId
    packageId = $ExpectedPackageId
    rangeSourceSha256 = 'sha256:' + $ExpectedRangeSourceSha256
    hostedQualificationRun = $ExpectedHostedRun
    sourceRef = if (Test-Path -LiteralPath $SourcePath -PathType Leaf) { 'sha256:' + (Get-FileSha256 $SourcePath) } else { $null }
    exactCandidateCount = 0
    namedMismatchCount = 0
    unreadableCandidateCount = 0
    ingressUsed = $false
    ingressSourceRef = $null
    serviceArchiveRef = $null
    workspaceRef = $null
    operationRootRef = $null
    transactionVerified = $false
    operationReceiptRef = $null
    hostPreparationAttempted = $false
    w01RangeDownloadAttempted = $false
    l01RangeDownloadAttempted = $false
    remoteHelperTransferred = $false
    remoteCommandExecuted = $false
    remoteReceiptRetrieved = $false
    remoteCleanupCompleted = $false
    remoteStageRetainedForRetry = $false
    hostPreparationReceiptRef = $null
    w01RangeReceiptRef = $null
    l01RangeReceiptRef = $null
    w01LaunchCommandReceiptRef = $null
    l01LaunchCommandReceiptRef = $null
    finalRangeJoinReceiptRef = $null
    modelArtifactEndpointContactConfirmed = $false
    modelDownloaded = $false
    rangeShardsDownloaded = 0
    rangePayloadBytes = 0
    physicalExecutionObserved = $false
    browserLaunched = $false
    supplierEndpointContacted = $false
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

$OperationReceiptPath = $null
try {
    $Candidates = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    $ProfileRoots = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)

    try {
        foreach ($Profile in @(Get-CimInstance Win32_UserProfile -ErrorAction Stop)) {
            if (-not $Profile.Special -and -not [string]::IsNullOrWhiteSpace([string]$Profile.LocalPath)) {
                $null = $ProfileRoots.Add([IO.Path]::GetFullPath([string]$Profile.LocalPath))
            }
        }
    }
    catch {
    }

    $UsersRoot = Join-Path ([IO.Path]::GetPathRoot($env:SystemRoot)) 'Users'
    if (Test-Path -LiteralPath $UsersRoot -PathType Container) {
        foreach ($Directory in @(Get-ChildItem -LiteralPath $UsersRoot -Directory -Force -ErrorAction SilentlyContinue)) {
            if ($Directory.Name -notin @('All Users', 'Default', 'Default User', 'Public')) {
                $null = $ProfileRoots.Add($Directory.FullName)
            }
        }
    }

    $RelativeCandidates = @(
        $ExpectedArchiveName,
        (Join-Path 'Downloads' $ExpectedArchiveName),
        (Join-Path 'Desktop' $ExpectedArchiveName),
        (Join-Path 'Documents' $ExpectedArchiveName),
        (Join-Path 'My Drive' $ExpectedArchiveName),
        (Join-Path 'Google Drive' $ExpectedArchiveName),
        (Join-Path 'Google Drive\My Drive' $ExpectedArchiveName),
        (Join-Path 'Drive' $ExpectedArchiveName)
    )
    foreach ($Root in $ProfileRoots) {
        foreach ($Relative in $RelativeCandidates) {
            Add-CandidatePath $Candidates (Join-Path $Root $Relative)
        }
    }
    foreach ($Drive in @(Get-PSDrive -PSProvider FileSystem -ErrorAction SilentlyContinue)) {
        foreach ($Relative in @(
            $ExpectedArchiveName,
            (Join-Path 'My Drive' $ExpectedArchiveName),
            (Join-Path 'Google Drive' $ExpectedArchiveName),
            (Join-Path 'Google Drive\My Drive' $ExpectedArchiveName),
            (Join-Path 'AXM\Issue-105' $ExpectedArchiveName)
        )) {
            Add-CandidatePath $Candidates (Join-Path $Drive.Root $Relative)
        }
    }

    $ExactCopies = @()
    $CandidateIndex = 0
    foreach ($Candidate in @($Candidates | Sort-Object)) {
        if (-not (Test-Path -LiteralPath $Candidate -PathType Leaf)) {
            continue
        }
        Add-MaskedValue $Candidate
        $CandidateIndex += 1
        $Summary.ingressUsed = $true
        $Materialized = Join-Path $ReceiptRoot ("candidate-{0:D3}.zip" -f $CandidateIndex)
        try {
            Copy-Item -LiteralPath $Candidate -Destination $Materialized -Force
        }
        catch {
            $Summary.unreadableCandidateCount = [int]$Summary.unreadableCandidateCount + 1
            continue
        }
        $Item = Get-Item -LiteralPath $Materialized -Force
        $Digest = Get-FileSha256 $Materialized
        if ($Item.Length -eq $ExpectedArchiveBytes -and $Digest -eq $ExpectedArchiveSha256) {
            $ExactCopies += [ordered]@{
                Source = $Candidate
                Materialized = $Materialized
            }
        }
        else {
            $Summary.namedMismatchCount = [int]$Summary.namedMismatchCount + 1
            Remove-Item -LiteralPath $Materialized -Force -ErrorAction SilentlyContinue
        }
    }

    $Summary.exactCandidateCount = $ExactCopies.Count
    if ($ExactCopies.Count -eq 0) {
        $Summary.reasonCode = if ([int]$Summary.namedMismatchCount -gt 0) { 'PRIVATE_TRANSACTION_IDENTITY_MISMATCH' } else { 'PRIVATE_TRANSACTION_NOT_SYNCED' }
        Write-Json $SummaryPath $Summary
        exit 0
    }

    $SelectedCopy = $ExactCopies | Select-Object -First 1
    $Summary.ingressSourceRef = Get-TextSha256 ([string]$SelectedCopy.Source)
    foreach ($Copy in $ExactCopies | Select-Object -Skip 1) {
        Remove-Item -LiteralPath ([string]$Copy.Materialized) -Force -ErrorAction SilentlyContinue
    }

    $SelectedDrive = $null
    foreach ($DriveName in @('D', 'E', 'C')) {
        $Drive = Get-PSDrive -Name $DriveName -PSProvider FileSystem -ErrorAction SilentlyContinue
        if ($Drive -and [int64]$Drive.Free -ge $MinimumFreeBytes) {
            $SelectedDrive = $Drive
            break
        }
    }
    if (-not $SelectedDrive) {
        $Summary.reasonCode = 'NO_PERSISTENT_VOLUME_WITH_30GIB_FREE'
        Write-Json $SummaryPath $Summary
        exit 0
    }

    $ServiceRoot = if ($SelectedDrive.Name -eq 'C') {
        Join-Path $env:ProgramData 'AXM\Issue-105\range-custody-03'
    }
    else {
        Join-Path $SelectedDrive.Root 'AXM\Issue-105\range-custody-03'
    }
    if (Test-ReparseCoordinate $ServiceRoot) {
        throw 'SERVICE_ROOT_LINKED'
    }
    New-Item -ItemType Directory -Path $ServiceRoot -Force | Out-Null

    $ServiceArchive = Join-Path $ServiceRoot $ExpectedArchiveName
    Add-MaskedValue $ServiceArchive
    if (Test-ReparseCoordinate $ServiceArchive) {
        throw 'SERVICE_ARCHIVE_COORDINATE_LINKED'
    }
    if (Test-Path -LiteralPath $ServiceArchive -PathType Leaf) {
        $Item = Get-Item -LiteralPath $ServiceArchive -Force
        $Digest = Get-FileSha256 $ServiceArchive
        if ($Item.Length -ne $ExpectedArchiveBytes -or $Digest -ne $ExpectedArchiveSha256) {
            throw 'SERVICE_ARCHIVE_COLLISION'
        }
    }
    else {
        $TemporaryArchive = "$ServiceArchive.part-$([Guid]::NewGuid().ToString('N'))"
        Copy-Item -LiteralPath ([string]$SelectedCopy.Materialized) -Destination $TemporaryArchive -Force
        $Item = Get-Item -LiteralPath $TemporaryArchive -Force
        $Digest = Get-FileSha256 $TemporaryArchive
        if ($Item.Length -ne $ExpectedArchiveBytes -or $Digest -ne $ExpectedArchiveSha256) {
            Remove-Item -LiteralPath $TemporaryArchive -Force -ErrorAction SilentlyContinue
            throw 'SERVICE_ARCHIVE_COPY_IDENTITY_INVALID'
        }
        Move-Item -LiteralPath $TemporaryArchive -Destination $ServiceArchive
    }
    $Summary.serviceArchiveRef = 'sha256:' + (Get-FileSha256 $ServiceArchive)

    $RunId = if ([string]::IsNullOrWhiteSpace($env:GITHUB_RUN_ID)) { [Guid]::NewGuid().ToString('N') } else { $env:GITHUB_RUN_ID }
    $RunAttempt = if ([string]::IsNullOrWhiteSpace($env:GITHUB_RUN_ATTEMPT)) { '0' } else { $env:GITHUB_RUN_ATTEMPT }
    $RunRoot = Join-Path $ServiceRoot (Join-Path 'runs' ("$RunId-$RunAttempt"))
    if (Test-ReparseCoordinate $RunRoot) {
        throw 'RUN_ROOT_LINKED'
    }
    if (Test-Path -LiteralPath $RunRoot) {
        Remove-Item -LiteralPath $RunRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Path $RunRoot -Force | Out-Null
    Add-MaskedValue $RunRoot

    $WorkspaceStaging = Join-Path $RunRoot 'workspace.staging'
    $Workspace = Join-Path $RunRoot 'workspace'
    Expand-Archive -LiteralPath $ServiceArchive -DestinationPath $WorkspaceStaging -Force
    Move-Item -LiteralPath $WorkspaceStaging -Destination $Workspace
    $Summary.workspaceRef = Get-TextSha256 $Workspace

    $Python = Resolve-Python311
    $Verifier = Join-Path $Workspace 'verify_issue105_range_custody_transaction_03.py'
    if (-not (Test-Path -LiteralPath $Verifier -PathType Leaf)) {
        throw 'TRANSACTION_VERIFIER_MISSING'
    }
    $VerifyLines = & $Python.File @($Python.Prefix) $Verifier $Workspace 2>&1
    $VerifyExit = [int]$LASTEXITCODE
    try {
        $Verify = (($VerifyLines | ForEach-Object { [string]$_ }) -join "`n") | ConvertFrom-Json
    }
    catch {
        throw 'TRANSACTION_VERIFICATION_OUTPUT_INVALID'
    }
    if ($VerifyExit -ne 0 -or
        $Verify.status -ne 'PASS' -or
        $Verify.transactionId -ne $ExpectedTransactionId -or
        $Verify.packageId -ne $ExpectedPackageId -or
        $Verify.modelDownloaded -ne $false -or
        [int]$Verify.rangeShardsDownloaded -ne 0 -or
        $Verify.physicalExecutionObserved -ne $false -or
        $Verify.browserLaunched -ne $false -or
        $Verify.supplierEndpointContacted -ne $false -or
        $Verify.peerConnectionFormed -ne $false -or
        $Verify.inferenceExecuted -ne $false -or
        $Verify.routeTerminalProduced -ne $false -or
        $Verify.actualSupplierQualified -ne $false -or
        $Verify.physicalEstateQualified -ne $false -or
        $Verify.missionAuthority -ne 'none' -or
        $Verify.commandAuthority -ne 'none') {
        throw 'TRANSACTION_VERIFICATION_RESULT_INVALID'
    }
    $Summary.transactionVerified = $true

    $OperationRoot = Join-Path $RunRoot 'receipts'
    New-Item -ItemType Directory -Path $OperationRoot -Force | Out-Null
    $Summary.operationRootRef = Get-TextSha256 $OperationRoot
    $OperationReceiptPath = Join-Path $OperationRoot 'ACQUIRE-BOTH-SEAT-RANGES-RECEIPT.json'
    $Acquire = Join-Path $Workspace 'Acquire-Both-Seat-Ranges.ps1'
    if (-not (Test-Path -LiteralPath $Acquire -PathType Leaf)) {
        throw 'RANGE_ACQUISITION_ENTRYPOINT_MISSING'
    }

    $PrivateLog = Join-Path $RunRoot 'operation-private.log'
    $OperationLines = & powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $Acquire -OutputRoot $OperationRoot 2>&1
    $OperationExit = [int]$LASTEXITCODE
    @($OperationLines | ForEach-Object { [string]$_ }) | Set-Content -LiteralPath $PrivateLog -Encoding UTF8

    if (-not (Test-Path -LiteralPath $OperationReceiptPath -PathType Leaf)) {
        throw 'OPERATION_RECEIPT_MISSING'
    }
    $Operation = Get-Content -LiteralPath $OperationReceiptPath -Raw | ConvertFrom-Json
    $Summary.operationReceiptRef = 'sha256:' + (Get-FileSha256 $OperationReceiptPath)
    Update-SummaryFromOperation $Summary $Operation

    if ($Summary.physicalExecutionObserved -ne $false -or
        $Summary.browserLaunched -ne $false -or
        $Summary.supplierEndpointContacted -ne $false -or
        $Summary.peerConnectionFormed -ne $false -or
        $Summary.inferenceExecuted -ne $false -or
        $Summary.routeTerminalProduced -ne $false -or
        $Summary.actualSupplierQualified -ne $false -or
        $Summary.physicalEstateQualified -ne $false -or
        $Summary.missionAuthority -ne 'none' -or
        $Summary.commandAuthority -ne 'none') {
        throw 'OPERATION_AUTHORITY_BOUNDARY_INVALID'
    }

    if ($Operation.status -eq 'PASS') {
        if ($OperationExit -ne 0 -or
            $Operation.terminal -ne 'READY_FOR_PHYSICAL_SEAT_OPERATION' -or
            $Summary.modelArtifactEndpointContactConfirmed -ne $true -or
            $Summary.modelDownloaded -ne $true -or
            [int]$Summary.rangeShardsDownloaded -ne 2 -or
            [int64]$Summary.rangePayloadBytes -ne $ExpectedPayloadBytes) {
            throw 'OPERATION_PASS_TERMINAL_INVALID'
        }
        $Summary.status = 'PASS'
        $Summary.terminal = 'READY_FOR_PHYSICAL_SEAT_OPERATION'
        $Summary.reasonCode = $null
    }
    elseif ($Operation.status -eq 'HOLD') {
        $Summary.status = 'HOLD'
        $Summary.terminal = 'HOLD'
        $Reason = [string]$Operation.reasonCode
        $Summary.reasonCode = if ($Reason -match '^[A-Z0-9_]+$') { $Reason } else { 'OPERATION_HOLD_UNCLASSIFIED' }
    }
    else {
        throw 'OPERATION_STATUS_INVALID'
    }

    Write-Json $SummaryPath $Summary
    exit 0
}
catch {
    if ($OperationReceiptPath -and (Test-Path -LiteralPath $OperationReceiptPath -PathType Leaf)) {
        try {
            $Operation = Get-Content -LiteralPath $OperationReceiptPath -Raw | ConvertFrom-Json
            $Summary.operationReceiptRef = 'sha256:' + (Get-FileSha256 $OperationReceiptPath)
            Update-SummaryFromOperation $Summary $Operation
        }
        catch {
        }
    }
    $Summary.status = 'REFUSED'
    $Summary.terminal = 'REFUSED'
    $Summary.reasonCode = ([string]$_.Exception.Message).Split(':')[0]
    Write-Json $SummaryPath $Summary
    exit 2
}
