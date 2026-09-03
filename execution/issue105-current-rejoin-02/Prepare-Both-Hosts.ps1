#requires -Version 5.1
param(
    [string]$OutputRoot = '',
    [string]$PeerAlias = 'OCTO-L01'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$PacketRoot = [IO.Path]::GetFullPath($PSScriptRoot)
$Preparer = Join-Path $PacketRoot 'Prepare-Current-Host.ps1'
$Verifier = Join-Path $PacketRoot 'verify_current_rejoin_packet.py'
$Joiner = Join-Path $PacketRoot 'join_preparation_receipts.py'
$ExpectedRelease = Join-Path $PacketRoot 'AXM-Issue-105-Browser-Physical-Audition-Flight-Package-03-Release.zip'
$ExpectedReleaseBytes = 3438484L
$ExpectedReleaseSha256 = '884630ee32a75545373bc88b725c976cc1e61bffd240315a14afea81c20e6d09'

function Get-TextSha256([string]$Value) {
    $Bytes = [Text.Encoding]::UTF8.GetBytes($Value)
    $Sha = [Security.Cryptography.SHA256]::Create()
    try { return 'sha256:' + (($Sha.ComputeHash($Bytes) | ForEach-Object { $_.ToString('x2') }) -join '') }
    finally { $Sha.Dispose() }
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

function ConvertTo-EncodedPowerShell([string]$Source) {
    return [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($Source))
}

function Invoke-External([string]$FilePath, [string[]]$Arguments) {
    $Lines = & $FilePath @Arguments 2>&1
    return [ordered]@{ exitCode = $LASTEXITCODE; output = ($Lines -join "`n") }
}

if (Test-ReparseCoordinate $PacketRoot) { throw 'PACKET_ROOT_LINKED' }
foreach ($Path in @($Preparer, $Verifier, $Joiner, $ExpectedRelease)) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf) -or (Test-ReparseCoordinate $Path)) { throw 'PACKET_SOURCE_INCOMPLETE' }
}
$ReleaseItem = Get-Item -LiteralPath $ExpectedRelease -Force
if ($ReleaseItem.Length -ne $ExpectedReleaseBytes -or (Get-FileHash -LiteralPath $ExpectedRelease -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ExpectedReleaseSha256) {
    throw 'CURRENT_RELEASE_IDENTITY_INVALID'
}
$Python = Resolve-Python311
$VerifyText = & $Python.File @($Python.Prefix) $Verifier $PacketRoot 2>&1
if ($LASTEXITCODE -ne 0) { throw 'CURRENT_REJOIN_PACKET_REFUSED' }
$Verify = ($VerifyText -join "`n") | ConvertFrom-Json
if ($Verify.status -ne 'PASS') { throw 'CURRENT_REJOIN_VERDICT_INVALID' }

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $Selected = $null
    foreach ($Name in @('D', 'E', 'C')) {
        $Drive = Get-PSDrive -Name $Name -PSProvider FileSystem -ErrorAction SilentlyContinue
        if ($Drive -and [int64]$Drive.Free -ge 1073741824L) { $Selected = $Drive; break }
    }
    if (-not $Selected) { throw 'NO_RECEIPT_VOLUME_WITH_1GIB_FREE' }
    $OutputRoot = if ($Selected.Name -eq 'C') {
        Join-Path $env:ProgramData 'AXM\Issue-105\current-rejoin-02\receipts'
    } else {
        Join-Path $Selected.Root 'AXM\Issue-105\current-rejoin-02\receipts'
    }
}
$OutputRoot = [IO.Path]::GetFullPath($OutputRoot)
if (Test-ReparseCoordinate $OutputRoot) { throw 'OUTPUT_ROOT_LINKED' }
New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null
$W01Receipt = Join-Path $OutputRoot 'ISSUE105-W01-PREPARATION-RECEIPT.json'
$L01Receipt = Join-Path $OutputRoot 'ISSUE105-L01-PREPARATION-RECEIPT.json'
$JoinReceipt = Join-Path $OutputRoot 'ISSUE105-TWO-SEAT-PREPARATION-JOIN.json'

& powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $Preparer `
    -HostRole W01 -PacketRoot $PacketRoot -OutputRoot (Join-Path (Split-Path -Parent $OutputRoot) 'W01') -ReceiptPath $W01Receipt | Out-Null
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $W01Receipt -PathType Leaf)) { throw 'W01_CURRENT_PREPARATION_REFUSED' }

$Ssh = Get-Command ssh.exe -ErrorAction SilentlyContinue
$Scp = Get-Command scp.exe -ErrorAction SilentlyContinue
if (-not $Ssh -or -not $Scp) { throw 'OPENSSH_CLIENT_NOT_AVAILABLE' }
$RunCoordinate = if ([string]::IsNullOrWhiteSpace($env:GITHUB_RUN_ID)) { [Guid]::NewGuid().ToString('N') } else { $env:GITHUB_RUN_ID }
if ($RunCoordinate -notmatch '^[A-Za-z0-9_-]+$') { throw 'RUN_COORDINATE_INVALID' }
$RemoteStage = "issue105-current-rejoin-$RunCoordinate"
$RemoteRootName = Split-Path -Leaf $PacketRoot
$SshOptions = @('-o','BatchMode=yes','-o','ConnectTimeout=8','-o','ConnectionAttempts=1','-o','StrictHostKeyChecking=yes','-o','ForwardAgent=no','-o','ForwardX11=no','-o','ClearAllForwardings=yes')
$ScpOptions = @('-q','-B','-o','BatchMode=yes','-o','ConnectTimeout=8','-o','ConnectionAttempts=1','-o','StrictHostKeyChecking=yes','-o','ForwardAgent=no','-o','ForwardX11=no','-o','ClearAllForwardings=yes')

Write-Output "::add-mask::$PeerAlias"
Write-Output "::add-mask::$RemoteStage"
$SetupSource = @"
`$ErrorActionPreference = 'Stop'
`$Root = Join-Path `$env:USERPROFILE '$RemoteStage'
if (Test-Path -LiteralPath `$Root) { exit 21 }
New-Item -ItemType Directory -Path `$Root -Force | Out-Null
exit 0
"@
$Setup = Invoke-External -FilePath $Ssh.Source -Arguments @($SshOptions + @($PeerAlias, 'powershell.exe', '-NoLogo', '-NoProfile', '-NonInteractive', '-EncodedCommand', (ConvertTo-EncodedPowerShell $SetupSource)))
if ($Setup.exitCode -ne 0) { throw "L01_SSH_SETUP_REFUSED:$($Setup.exitCode)" }

$Copy = Invoke-External -FilePath $Scp.Source -Arguments @(@('-r') + $ScpOptions + @($PacketRoot, "${PeerAlias}:$RemoteStage/"))
if ($Copy.exitCode -ne 0) { throw "L01_PACKET_TRANSFER_REFUSED:$($Copy.exitCode)" }

$RemoteRunSource = @"
`$ErrorActionPreference = 'Stop'
`$Stage = Join-Path `$env:USERPROFILE '$RemoteStage'
`$Packet = Join-Path `$Stage '$RemoteRootName'
`$Output = Join-Path `$Stage 'output'
`$Receipt = Join-Path `$Output 'ISSUE105-L01-PREPARATION-RECEIPT.json'
`$Preparer = Join-Path `$Packet 'Prepare-Current-Host.ps1'
if (-not (Test-Path -LiteralPath `$Preparer -PathType Leaf)) { exit 31 }
`$Selected = `$null
foreach (`$Name in @('D', 'E', 'C')) {
    `$Drive = Get-PSDrive -Name `$Name -PSProvider FileSystem -ErrorAction SilentlyContinue
    if (`$Drive -and [int64]`$Drive.Free -ge 1073741824L) { `$Selected = `$Drive; break }
}
if (-not `$Selected) { exit 33 }
`$Persistent = if (`$Selected.Name -eq 'C') {
    Join-Path `$env:ProgramData 'AXM\Issue-105\current-rejoin-02\L01'
} else {
    Join-Path `$Selected.Root 'AXM\Issue-105\current-rejoin-02\L01'
}
& powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File `$Preparer -HostRole L01 -PacketRoot `$Packet -OutputRoot `$Persistent -ReceiptPath `$Receipt | Out-Null
if (`$LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath `$Receipt -PathType Leaf)) { exit 32 }
`$ReceiptBody = Get-Content -LiteralPath `$Receipt -Raw | ConvertFrom-Json
if (`$ReceiptBody.persistenceScope -ne 'HOST_LOCAL_OUTSIDE_TRANSPORT_STAGE' -or `$ReceiptBody.persistentMaterialVerifiedAfterPrepare -ne `$true) { exit 34 }
exit 0
"@
$RemoteRun = Invoke-External -FilePath $Ssh.Source -Arguments @($SshOptions + @($PeerAlias, 'powershell.exe', '-NoLogo', '-NoProfile', '-NonInteractive', '-EncodedCommand', (ConvertTo-EncodedPowerShell $RemoteRunSource)))
if ($RemoteRun.exitCode -ne 0) { throw "L01_CURRENT_PREPARATION_REFUSED:$($RemoteRun.exitCode)" }

$Download = Invoke-External -FilePath $Scp.Source -Arguments @($ScpOptions + @("${PeerAlias}:$RemoteStage/output/ISSUE105-L01-PREPARATION-RECEIPT.json", $L01Receipt))
if ($Download.exitCode -ne 0 -or -not (Test-Path -LiteralPath $L01Receipt -PathType Leaf)) { throw 'L01_RECEIPT_RETURN_REFUSED' }

& $Python.File @($Python.Prefix) $Joiner `
    --identity (Join-Path $PacketRoot 'ISSUE105-CURRENT-IDENTITY-JOIN.json') `
    --package (Join-Path $PacketRoot 'PACKAGE.json') `
    --w01 $W01Receipt --l01 $L01Receipt --output $JoinReceipt | Out-Null
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $JoinReceipt -PathType Leaf)) { throw 'TWO_SEAT_PREPARATION_JOIN_REFUSED' }
$JoinBody = Get-Content -LiteralPath $JoinReceipt -Raw | ConvertFrom-Json
if ($JoinBody.status -ne 'PASS' -or $JoinBody.terminal -ne 'READY_FOR_EXACT_RANGE_CUSTODY' -or $JoinBody.physicalUniquenessProved -ne $false) {
    throw 'TWO_SEAT_PREPARATION_JOIN_INVALID'
}

$CleanupSource = @"
`$Root = Join-Path `$env:USERPROFILE '$RemoteStage'
if (Test-Path -LiteralPath `$Root) { Remove-Item -LiteralPath `$Root -Recurse -Force }
exit 0
"@
$Cleanup = Invoke-External -FilePath $Ssh.Source -Arguments @($SshOptions + @($PeerAlias, 'powershell.exe', '-NoLogo', '-NoProfile', '-NonInteractive', '-EncodedCommand', (ConvertTo-EncodedPowerShell $CleanupSource)))
if ($Cleanup.exitCode -ne 0) { throw 'L01_REMOTE_STAGE_CLEANUP_REFUSED' }

$JoinBody | ConvertTo-Json -Depth 40
exit 0
