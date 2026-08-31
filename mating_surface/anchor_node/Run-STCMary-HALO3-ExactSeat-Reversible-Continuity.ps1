#requires -Version 5.1
<#
STC MARY guided HALO3 continuity gate.

What this does:
  1. Resolves the exact-seat successor campaign and immutable Thunderbolt HALO3 Seat.
  2. Shows the operator the exact local GPU and the effect of the gate.
  3. Refuses if the GPU is driving an active Windows display or has an active CUDA process.
  4. Disables that exact Windows PnP device, proving it absent/inaccessible.
  5. Runs only the resident post-HALO3 continuity result, verification, and comparison.
  6. Refreshes and verifies the conductor, then stops at two_cell_partition / HOLD.
  7. Re-enables the exact GPU and verifies that the same UUID returns.

It does not ask the operator to unplug a cable or guess which enclosure is HALO3.
It does not execute any Cell, successor, plan, packet, or sealing action.
#>

[CmdletBinding(PositionalBinding = $false)]
param(
    [string] $PrivateParent = 'D:\Private\AXM-CAIRN-smoke',

    [string] $CampaignId =
        'stcmaryflightconductorcampaign1_a79891b50290096069501ccfb25412ba05677e020cd2217ceca54aaed6c3f1ed',

    [string] $ExpectedHalo3ResultId =
        'stcmaryapertureworkloadresult1_4c4dcfa384b82892eee0b3f65c21bda773acfed9aba2664f172b1ffa3b5f56d0',

    [string] $ExpectedHalo3VerificationId =
        'stcmaryapertureworkloadverification1_4442ce6aaf5d1d4a121e2d62c62b6e6a7f6d7a25d78348f12f761a91d3a5041d',

    [string] $RuntimePython =
        'D:\Private\AXM-CAIRN-smoke\runtimes\stc-mary-py312-cu128-01\Scripts\python.exe',

    [string] $ExpectedRuntimePythonSha256 =
        '0b471133e110cfb53a061cad528ce8e517d7b9ac41a0a396c39ad795a487fc14',

    [int] $DeviceDisappearTimeoutSeconds = 90,

    [int] $DeviceRestoreTimeoutSeconds = 150,

    [switch] $DrainAuthorizedBraveGpuHelpers,

    [switch] $NonInteractive
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

if (Test-Path variable:PSNativeCommandUseErrorActionPreference) {
    $PSNativeCommandUseErrorActionPreference = $false
}

function Stop-Gate {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Code,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    throw [System.InvalidOperationException]::new("$Code|$Message")
}

function Read-JsonFile {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $Label
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        Stop-Gate -Code "${Label}_ABSENT" -Message "$Label is absent."
    }

    try {
        return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 |
            ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        Stop-Gate -Code "${Label}_INVALID" -Message "$Label is not valid JSON."
    }
}

function Assert-RegularFile {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $Code,

        [Parameter(Mandatory = $true)]
        [string] $Label
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        Stop-Gate -Code $Code -Message "$Label is absent."
    }

    $Item = Get-Item -LiteralPath $Path -Force
    if (($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        Stop-Gate -Code $Code -Message "$Label is a reparse point."
    }
}

function Assert-RegularDirectory {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $Code,

        [Parameter(Mandatory = $true)]
        [string] $Label
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        Stop-Gate -Code $Code -Message "$Label is absent."
    }

    $Item = Get-Item -LiteralPath $Path -Force
    if (($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        Stop-Gate -Code $Code -Message "$Label is a reparse point."
    }
}

function Get-Sha256 {
    param([Parameter(Mandatory = $true)][string] $Path)

    return (
        Get-FileHash -LiteralPath $Path -Algorithm SHA256
    ).Hash.ToLowerInvariant()
}

function Get-StableErrorCode {
    param([object[]] $Output)

    $Text = ($Output | ForEach-Object { $_.ToString() }) -join "`n"
    $Match = [regex]::Match(
        $Text,
        '(?m)(?:^|\r?\n)([A-Z][A-Z0-9_]{2,}):'
    )

    if ($Match.Success) {
        return $Match.Groups[1].Value
    }

    return 'BOUND_TOOL_REFUSED'
}

function Invoke-BoundPowerShellTool {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Script,

        [Parameter(Mandatory = $true)]
        [string[]] $Arguments
    )

    $PriorPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $global:LASTEXITCODE = 0

    try {
        $Output = @(
            & $Script @Arguments 2>&1
        )
        $ExitCode = $LASTEXITCODE
        if ($null -eq $ExitCode) {
            $ExitCode = 0
        }
    }
    catch {
        $Output = @($_)
        $ExitCode = 1
    }
    finally {
        $ErrorActionPreference = $PriorPreference
    }

    return [pscustomobject]@{
        ExitCode = [int] $ExitCode
        Output = $Output
    }
}

function Invoke-ConductorJson {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Conductor,

        [Parameter(Mandatory = $true)]
        [string] $Command,

        [Parameter(Mandatory = $true)]
        [string] $Workstation
    )

    $Invocation = Invoke-BoundPowerShellTool `
        -Script $Conductor `
        -Arguments @($Command, '--workstation', $Workstation)

    if ($Invocation.ExitCode -ne 0) {
        $Code = Get-StableErrorCode -Output $Invocation.Output
        Stop-Gate -Code $Code -Message "Conductor $Command refused."
    }

    $Text = (
        $Invocation.Output |
        ForEach-Object { $_.ToString() }
    ) -join [Environment]::NewLine

    try {
        return $Text | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        Stop-Gate `
            -Code 'CONDUCTOR_NON_JSON_RESPONSE' `
            -Message "Conductor $Command did not return one JSON object."
    }
}

function Get-PhaseState {
    param(
        [Parameter(Mandatory = $true)]
        [object] $Status,

        [Parameter(Mandatory = $true)]
        [string] $Phase
    )

    $Rows = @(
        $Status.phases |
        Where-Object { $_.phase -eq $Phase }
    )

    if ($Rows.Count -ne 1) {
        Stop-Gate `
            -Code 'PHASE_DENOMINATOR_INVALID' `
            -Message "Phase denominator differs for $Phase."
    }

    return [string] $Rows[0].state
}

function Test-IsAdministrator {
    $Identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $Principal = [Security.Principal.WindowsPrincipal]::new($Identity)
    return $Principal.IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator
    )
}

function Get-NvidiaInventory {
    $PriorPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $global:LASTEXITCODE = 0

    try {
        $Raw = @(
            & nvidia-smi `
                --query-gpu=index,name,uuid,pci.bus_id `
                --format=csv,noheader,nounits 2>$null
        )
        $ExitCode = $LASTEXITCODE
        if ($null -eq $ExitCode) {
            $ExitCode = 0
        }
    }
    catch {
        $Raw = @()
        $ExitCode = 1
    }
    finally {
        $ErrorActionPreference = $PriorPreference
    }

    $Rows = @()
    if ($ExitCode -eq 0) {
        foreach ($Line in $Raw) {
            $Parts = @(
                $Line.ToString().Split(',') |
                ForEach-Object { $_.Trim() }
            )

            if ($Parts.Count -ne 4) {
                continue
            }

            $Rows += [pscustomobject]@{
                Index = [int] $Parts[0]
                Name = [string] $Parts[1]
                Uuid = [string] $Parts[2]
                PciBusId = [string] $Parts[3]
            }
        }
    }

    return [pscustomobject]@{
        Success = ($ExitCode -eq 0)
        ExitCode = [int] $ExitCode
        Rows = @($Rows)
    }
}

function Get-NvidiaComputeProcesses {
    param([Parameter(Mandatory = $true)][string] $GpuUuid)

    $PriorPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $global:LASTEXITCODE = 0

    try {
        $Raw = @(
            & nvidia-smi `
                --query-compute-apps=gpu_uuid,pid,process_name `
                --format=csv,noheader,nounits 2>$null
        )
        $ExitCode = $LASTEXITCODE
    }
    catch {
        $Raw = @()
        $ExitCode = 1
    }
    finally {
        $ErrorActionPreference = $PriorPreference
    }

    if ($ExitCode -ne 0) {
        return @()
    }

    $Rows = @()
    foreach ($Line in $Raw) {
        $Parts = @($Line.ToString().Split(',') | ForEach-Object { $_.Trim() })
        if ($Parts.Count -lt 3 -or $Parts[0] -ne $GpuUuid) {
            continue
        }

        $Rows += [pscustomobject]@{
            GpuUuid = [string] $Parts[0]
            Pid = [int] $Parts[1]
            ProcessName = [string] ($Parts[2..($Parts.Count - 1)] -join ',')
        }
    }

function Get-AuthorizedBraveGpuHelper {
    param([Parameter(Mandatory = $true)][int] $ProcessId)

    try {
        $Process = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction Stop
    }
    catch {
        return $null
    }

    $CommandLine = [string] $Process.CommandLine
    $Executable = [string] $Process.ExecutablePath
    $GpuRole = $CommandLine.Contains('--type=gpu-process')
    $VideoRole = $CommandLine.Contains('--utility-sub-type=video_capture.mojom.VideoCaptureService')

    if (
        $Executable -eq 'C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe' -and
        ($GpuRole -or $VideoRole)
    ) {
        return [pscustomobject]@{
            ProcessId = $ProcessId
            Role = if ($GpuRole) { 'gpu-process' } else { 'video-capture-service' }
        }
    }

    return $null
}

    return @($Rows)
}

function Convert-PciBusId {
    param([Parameter(Mandatory = $true)][string] $PciBusId)

    $Match = [regex]::Match(
        $PciBusId,
        '^(?:[0-9A-Fa-f]{8}:)?([0-9A-Fa-f]{2}):([0-9A-Fa-f]{2})\.([0-7])$'
    )

    if (-not $Match.Success) {
        Stop-Gate `
            -Code 'HALO3_PCI_BUS_ID_INVALID' `
            -Message 'HALO3 PCI bus identity does not match the admitted form.'
    }

    return [pscustomobject]@{
        Bus = [Convert]::ToInt32($Match.Groups[1].Value, 16)
        Device = [Convert]::ToInt32($Match.Groups[2].Value, 16)
        Function = [Convert]::ToInt32($Match.Groups[3].Value, 16)
    }
}

function Get-PropertyData {
    param(
        [Parameter(Mandatory = $true)]
        [string] $InstanceId,

        [Parameter(Mandatory = $true)]
        [string] $KeyName
    )

    try {
        $Property = Get-PnpDeviceProperty `
            -InstanceId $InstanceId `
            -KeyName $KeyName `
            -ErrorAction Stop

        return $Property.Data
    }
    catch {
        return $null
    }
}

function Resolve-ExactPnpGpu {
    param(
        [Parameter(Mandatory = $true)]
        [string] $PciBusId
    )

    $Coordinate = Convert-PciBusId -PciBusId $PciBusId
    $Matches = @()

    foreach ($Device in @(
        Get-PnpDevice -Class Display -PresentOnly -ErrorAction Stop
    )) {
        $BusNumber = Get-PropertyData `
            -InstanceId $Device.InstanceId `
            -KeyName 'DEVPKEY_Device_BusNumber'

        $Address = Get-PropertyData `
            -InstanceId $Device.InstanceId `
            -KeyName 'DEVPKEY_Device_Address'

        $Location = Get-PropertyData `
            -InstanceId $Device.InstanceId `
            -KeyName 'DEVPKEY_Device_LocationInfo'

        $AddressDevice = $null
        $AddressFunction = $null

        if ($null -ne $Address) {
            $AddressValue = [uint32] $Address
            $AddressDevice = [int] (($AddressValue -shr 16) -band 0xffff)
            $AddressFunction = [int] ($AddressValue -band 0xffff)
        }

        $MatchesByNumericProperty = (
            $null -ne $BusNumber -and
            [int] $BusNumber -eq $Coordinate.Bus -and
            $null -ne $AddressDevice -and
            $AddressDevice -eq $Coordinate.Device -and
            $AddressFunction -eq $Coordinate.Function
        )

        $ExpectedLocation = (
            'PCI bus {0}, device {1}, function {2}' -f
            $Coordinate.Bus,
            $Coordinate.Device,
            $Coordinate.Function
        )

        $MatchesByLocation = (
            $null -ne $Location -and
            $Location.ToString().IndexOf(
                $ExpectedLocation,
                [StringComparison]::OrdinalIgnoreCase
            ) -ge 0
        )

        if ($MatchesByNumericProperty -or $MatchesByLocation) {
            $Matches += [pscustomobject]@{
                InstanceId = [string] $Device.InstanceId
                FriendlyName = [string] $Device.FriendlyName
                Status = [string] $Device.Status
                Location = [string] $Location
            }
        }
    }

    if ($Matches.Count -ne 1) {
        Stop-Gate `
            -Code 'HALO3_PNP_DEVICE_NOT_UNIQUE' `
            -Message "Expected one Windows display device at the HALO3 PCI coordinate; observed $($Matches.Count)."
    }

    return $Matches[0]
}

function Test-ActiveWindowsDisplay {
    param([Parameter(Mandatory = $true)][string] $InstanceId)

    $Rows = @(
        Get-CimInstance Win32_VideoController -ErrorAction Stop |
        Where-Object {
            $_.PNPDeviceID -and
            $_.PNPDeviceID.Equals(
                $InstanceId,
                [StringComparison]::OrdinalIgnoreCase
            )
        }
    )

    if ($Rows.Count -ne 1) {
        Stop-Gate `
            -Code 'HALO3_VIDEO_CONTROLLER_NOT_UNIQUE' `
            -Message "Expected one Win32 video-controller row; observed $($Rows.Count)."
    }

    $Row = $Rows[0]
    return (
        $null -ne $Row.CurrentHorizontalResolution -or
        $null -ne $Row.CurrentVerticalResolution -or
        $null -ne $Row.CurrentBitsPerPixel
    )
}

function Wait-Until {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock] $Predicate,

        [Parameter(Mandatory = $true)]
        [int] $TimeoutSeconds
    )

    $Deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)

    while ([DateTime]::UtcNow -lt $Deadline) {
        if (& $Predicate) {
            return $true
        }

        Start-Sleep -Milliseconds 750
    }

    return $false
}

function Write-PrivateReceipt {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [System.Collections.IDictionary] $Body
    )

    $Directory = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $Directory -PathType Container)) {
        New-Item -ItemType Directory -Path $Directory | Out-Null
    }

    if (Test-Path -LiteralPath $Path) {
        Stop-Gate `
            -Code 'INTERRUPTION_RECEIPT_EXISTS' `
            -Message 'The private interruption receipt already exists.'
    }

    $Utf8NoBom = [System.Text.UTF8Encoding]::new($false)
    [IO.File]::WriteAllText(
        $Path,
        (($Body | ConvertTo-Json -Depth 12) + "`n"),
        $Utf8NoBom
    )
}

$TerminalPacket = $null
$Workstation = $null
$WorkstationProjection = $null
$Conductor = $null
$PathMap = $null
$PnpGpu = $null
$SelectedGpu = $null
$WasDisabled = $false
$BecameInaccessible = $false
$RestoreSucceeded = $false
$GateStartedUtc = $null
$GateEndedUtc = $null
$InterruptionReceiptPath = $null
$InterruptionReceiptSha256 = $null
$ContinuityResultId = $null
$ContinuityVerificationId = $null
$ComparisonId = $null
$RefusalCode = $null

try {
    Assert-RegularDirectory `
        -Path $PrivateParent `
        -Code 'PRIVATE_PARENT_ABSENT' `
        -Label 'Private campaign parent'

    $Matches = @()

    foreach ($Directory in @(
        Get-ChildItem -LiteralPath $PrivateParent -Directory -Force
    )) {
        $ConfigPath = Join-Path $Directory.FullName 'campaign-config.private.json'
        if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
            continue
        }

        try {
            $CandidateConfig = Get-Content `
                -LiteralPath $ConfigPath `
                -Raw `
                -Encoding UTF8 |
                ConvertFrom-Json -ErrorAction Stop
        }
        catch {
            continue
        }

        if ([string] $CandidateConfig.campaignId -eq $CampaignId) {
            $Matches += $Directory.FullName
        }
    }

    if ($Matches.Count -ne 1) {
        Stop-Gate `
            -Code 'ACTUATOR_NOT_RESOLVED' `
            -Message "Expected one workstation for the campaign; observed $($Matches.Count)."
    }

    $Workstation = [string] $Matches[0]
    $ConfigPath = Join-Path $Workstation 'campaign-config.private.json'
    $PathMapPath = Join-Path $Workstation 'path-map.private.json'
    $OperatorPath = Join-Path $Workstation 'operator-flight.ps1'
    $WorkstationProjection = Join-Path $Workstation 'workstation-public-projection.json'

    $Config = Read-JsonFile -Path $ConfigPath -Label 'CAMPAIGN_CONFIG'
    $PathMap = Read-JsonFile -Path $PathMapPath -Label 'PATH_MAP'

    if ([string] $Config.campaignId -ne $CampaignId) {
        Stop-Gate `
            -Code 'CAMPAIGN_ID_MISMATCH' `
            -Message 'Campaign identity differs.'
    }

    if ([string] $Config.authority -ne 'none') {
        Stop-Gate `
            -Code 'AUTHORITY_WIDENED' `
            -Message 'Campaign configuration authority differs.'
    }

    Assert-RegularFile `
        -Path $OperatorPath `
        -Code 'OPERATOR_SCRIPT_ABSENT' `
        -Label 'Bound operator script'

    $OperatorText = Get-Content -LiteralPath $OperatorPath -Raw -Encoding UTF8
    $ConductorMatch = [regex]::Match(
        $OperatorText,
        "(?m)^\`$Conductor\s*=\s*'((?:''|[^'])*)'\s*$"
    )

    if (-not $ConductorMatch.Success) {
        Stop-Gate `
            -Code 'BOUND_CONDUCTOR_NOT_RESOLVED' `
            -Message 'The generated operator does not expose one bound conductor path.'
    }

    $Conductor = $ConductorMatch.Groups[1].Value.Replace("''", "'")
    Assert-RegularFile `
        -Path $Conductor `
        -Code 'BOUND_CONDUCTOR_ABSENT' `
        -Label 'Bound conductor'

    $ExecutionRepository = [string] $Config.executionSource.repositoryPath
    Assert-RegularDirectory `
        -Path $ExecutionRepository `
        -Code 'EXECUTION_CHECKOUT_ABSENT' `
        -Label 'Bound execution checkout'

    $Tool = Join-Path `
        $ExecutionRepository `
        'mating_surface\anchor_node\stc-mary-local-toolchain.ps1'

    Assert-RegularFile `
        -Path $Tool `
        -Code 'BOUND_TOOLCHAIN_ABSENT' `
        -Label 'Bound local toolchain'

    Assert-RegularFile `
        -Path $RuntimePython `
        -Code 'RUNTIME_PYTHON_ABSENT' `
        -Label 'Qualified runtime interpreter'

    if ((Get-Sha256 -Path $RuntimePython) -ne $ExpectedRuntimePythonSha256) {
        Stop-Gate `
            -Code 'RUNTIME_PYTHON_DRIFT' `
            -Message 'Qualified runtime interpreter digest differs.'
    }

    $env:STC_MARY_PYTHON = (Resolve-Path -LiteralPath $RuntimePython).Path

    $Status = Invoke-ConductorJson `
        -Conductor $Conductor `
        -Command 'status' `
        -Workstation $Workstation

    if ((Get-PhaseState -Status $Status -Phase 'personal_floor') -ne 'CLOSED') {
        Stop-Gate `
            -Code 'PERSONAL_FLOOR_NOT_CLOSED' `
            -Message 'Personal floor is not closed.'
    }

    if ((Get-PhaseState -Status $Status -Phase 'halo3') -ne 'CLOSED') {
        Stop-Gate `
            -Code 'HALO3_NOT_CLOSED' `
            -Message 'HALO3 is not closed.'
    }

    if (
        [string] $Status.currentPhase -ne 'post_halo3_continuity' -or
        [string] $Status.currentPhaseState -ne 'HOLD' -or
        [int] $Status.closedPhaseCount -ne 6 -or
        [int] $Status.heldPhaseCount -ne 6 -or
        [int] $Status.refusedPhaseCount -ne 0
    ) {
        Stop-Gate `
            -Code 'POST_HALO3_START_STATE_INVALID' `
            -Message 'Campaign is not at the admitted post-HALO3 physical gate.'
    }

    $Halo3Result = [string] $PathMap.paths.accelerated
    $Halo3Verification = [string] $PathMap.paths.acceleratedVerification
    $ReadinessPath = [string] $PathMap.paths.readiness
    $Feed = [string] $PathMap.paths.feed
    $Baseline = [string] $PathMap.paths.baseline
    $Continuity = [string] $PathMap.paths.continuity
    $ContinuityVerification = [string] $PathMap.paths.continuityVerification
    $Comparison = [string] $PathMap.paths.comparison

    Assert-RegularFile `
        -Path $Halo3Result `
        -Code 'HALO3_RESULT_ABSENT' `
        -Label 'Accepted HALO3 result'

    Assert-RegularFile `
        -Path $Halo3Verification `
        -Code 'HALO3_VERIFICATION_ABSENT' `
        -Label 'Accepted HALO3 verification'

    $Halo3ResultJson = Read-JsonFile -Path $Halo3Result -Label 'HALO3_RESULT'
    $Halo3VerificationJson = Read-JsonFile `
        -Path $Halo3Verification `
        -Label 'HALO3_VERIFICATION'

    if ([string] $Halo3ResultJson.resultId -ne $ExpectedHalo3ResultId) {
        Stop-Gate `
            -Code 'HALO3_RESULT_ID_MISMATCH' `
            -Message 'HALO3 result identity differs.'
    }

    if (
        [string] $Halo3VerificationJson.verificationId -ne
        $ExpectedHalo3VerificationId
    ) {
        Stop-Gate `
            -Code 'HALO3_VERIFICATION_ID_MISMATCH' `
            -Message 'HALO3 verification identity differs.'
    }
    if (
        [string] $Halo3ResultJson.halo3SeatId -ne [string] $Config.halo3Seat.seatId -or
        [string] $Halo3VerificationJson.halo3SeatId -ne [string] $Config.halo3Seat.seatId
    ) {
        Stop-Gate `
            -Code 'HALO3_RECEIPT_SEAT_MISMATCH' `
            -Message 'Accepted HALO3 result pair names another Seat.'
    }



    $ContinuityExists =
        Test-Path -LiteralPath $Continuity -PathType Leaf
    $ContinuityVerificationExists =
        Test-Path -LiteralPath $ContinuityVerification -PathType Leaf
    $ComparisonExists =
        Test-Path -LiteralPath $Comparison -PathType Leaf

    if ($ContinuityVerificationExists -and -not $ContinuityExists) {
        Stop-Gate `
            -Code 'CONTINUITY_VERIFICATION_WITHOUT_RESULT' `
            -Message 'A continuity verification exists without its result.'
    }

    if (
        $ComparisonExists -and
        (-not $ContinuityExists -or -not $ContinuityVerificationExists)
    ) {
        Stop-Gate `
            -Code 'CONTINUITY_COMPARISON_WITHOUT_COMPLETE_PAIR' `
            -Message 'A comparison exists without a complete continuity pair.'
    }

    $NeedContinuityResult = -not $ContinuityExists
    $NeedContinuityVerification =
        ($ContinuityExists -and -not $ContinuityVerificationExists)
    $NeedComparison =
        ($ContinuityExists -and $ContinuityVerificationExists -and
         -not $ComparisonExists)

    if (-not $NeedContinuityResult) {
        $RestoreSucceeded = $true

        $ExistingReceiptDirectory =
            Join-Path $Workstation 'physical-gate-receipts'

        if (
            Test-Path `
                -LiteralPath $ExistingReceiptDirectory `
                -PathType Container
        ) {
            foreach ($ReceiptFile in @(
                Get-ChildItem `
                    -LiteralPath $ExistingReceiptDirectory `
                    -Filter 'halo3-reversible-interruption-*.private.json' `
                    -File |
                Sort-Object LastWriteTimeUtc -Descending
            )) {
                try {
                    $ExistingReceipt = Read-JsonFile `
                        -Path $ReceiptFile.FullName `
                        -Label 'EXISTING_INTERRUPTION_RECEIPT'

                    if (
                        [string] $ExistingReceipt.campaignId -eq $CampaignId -and
                        [string] $ExistingReceipt.continuityResultId -eq
                            [string] (
                                Read-JsonFile `
                                    -Path $Continuity `
                                    -Label 'CONTINUITY_RESULT'
                            ).resultId
                    ) {
                        $InterruptionReceiptSha256 =
                            Get-Sha256 -Path $ReceiptFile.FullName
                        break
                    }
                }
                catch {
                    continue
                }
            }
        }
    }

    if ($NeedContinuityResult) {
        if (-not (Test-IsAdministrator)) {
            Stop-Gate `
                -Code 'ELEVATION_REQUIRED' `
                -Message 'Run this script from Windows PowerShell opened as Administrator.'
        }

        if (-not (Get-Command Get-PnpDevice -ErrorAction SilentlyContinue)) {
            Stop-Gate `
                -Code 'PNP_DEVICE_MODULE_ABSENT' `
                -Message 'The Windows PnpDevice module is unavailable.'
        }

        if (-not (Get-Command Disable-PnpDevice -ErrorAction SilentlyContinue)) {
            Stop-Gate `
                -Code 'PNP_DISABLE_SURFACE_ABSENT' `
                -Message 'Disable-PnpDevice is unavailable.'
        }

        if (-not (Get-Command Enable-PnpDevice -ErrorAction SilentlyContinue)) {
            Stop-Gate `
                -Code 'PNP_ENABLE_SURFACE_ABSENT' `
                -Message 'Enable-PnpDevice is unavailable.'
        }

        $Readiness = Read-JsonFile -Path $ReadinessPath -Label 'READINESS_RECEIPT'
        $Halo3Seat = $Config.halo3Seat

        if (
            $null -eq $Halo3Seat -or
            [string] $Halo3Seat.role -ne 'HALO3' -or
            [string] $Halo3Seat.transportClass -ne 'thunderbolt_egpu'
        ) {
            Stop-Gate `
                -Code 'HALO3_EXACT_SEAT_CONFIG_INVALID' `
                -Message 'Campaign configuration does not bind one Thunderbolt HALO3 Seat.'
        }

        if (
            $null -eq $Readiness.halo3Seat -or
            [string] $Readiness.halo3Seat.seatId -ne [string] $Halo3Seat.seatId
        ) {
            Stop-Gate `
                -Code 'HALO3_READINESS_SEAT_MISMATCH' `
                -Message 'Readiness names another HALO3 Seat.'
        }

        $SelectedCudaIndex = [int] $Readiness.halo3SeatObservation.currentCudaDeviceIndex

        $ReadinessGpuRows = @(
            $Readiness.nvidiaGpus |
            Where-Object {
                [string] $_.uuid -eq [string] $Halo3Seat.gpuUuid -and
                [string] $_.'pci.bus_id' -eq [string] $Halo3Seat.pciBusId -and
                [string] $_.name -eq [string] $Halo3Seat.productName
            }
        )

        if ($ReadinessGpuRows.Count -ne 1) {
            Stop-Gate `
                -Code 'HALO3_READINESS_GPU_NOT_UNIQUE' `
                -Message "Expected the exact HALO3 UUID/PCI/product once; observed $($ReadinessGpuRows.Count)."
        }

        $SelectedGpu = $ReadinessGpuRows[0]
        $GpuUuid = [string] $Halo3Seat.gpuUuid
        $GpuPciBusId = [string] $Halo3Seat.pciBusId
        $GpuName = [string] $Halo3Seat.productName

        if (
            [string]::IsNullOrWhiteSpace($GpuUuid) -or
            [string]::IsNullOrWhiteSpace($GpuPciBusId) -or
            [string]::IsNullOrWhiteSpace($GpuName)
        ) {
            Stop-Gate `
                -Code 'HALO3_READINESS_GPU_IDENTITY_INCOMPLETE' `
                -Message 'Readiness did not retain the exact HALO3 GPU identity.'
        }

        $CurrentInventory = Get-NvidiaInventory

        if (-not $CurrentInventory.Success) {
            Stop-Gate `
                -Code 'NVIDIA_INVENTORY_UNAVAILABLE' `
                -Message 'NVIDIA inventory could not be read before the gate.'
        }

        $CurrentGpuRows = @(
            $CurrentInventory.Rows |
            Where-Object {
                $_.Uuid -eq $GpuUuid -and
                $_.PciBusId.Equals(
                    $GpuPciBusId,
                    [StringComparison]::OrdinalIgnoreCase
                )
            }
        )

        if ($CurrentGpuRows.Count -ne 1) {
            Stop-Gate `
                -Code 'HALO3_GPU_NOT_CURRENTLY_VISIBLE' `
                -Message 'The exact readiness-bound HALO3 GPU is not currently visible.'
        }

        $PnpGpu = Resolve-ExactPnpGpu -PciBusId $GpuPciBusId

        if (-not ([string] $PnpGpu.InstanceId).Equals(
            [string] $Halo3Seat.pnpInstanceId,
            [StringComparison]::OrdinalIgnoreCase
        )) {
            Stop-Gate `
                -Code 'HALO3_PNP_INSTANCE_MISMATCH' `
                -Message 'Resolved PCI device is not the immutable HALO3 PnP instance.'
        }

        $TransportAnchor = [string] $Halo3Seat.transportAnchorPnpInstanceId
        if ([string]::IsNullOrWhiteSpace($TransportAnchor)) {
            Stop-Gate `
                -Code 'HALO3_TRANSPORT_ANCHOR_ABSENT' `
                -Message 'The immutable Thunderbolt transport anchor is absent.'
        }

        $Ancestors = @()
        $Cursor = [string] $PnpGpu.InstanceId
        for ($Depth = 0; $Depth -lt 16; $Depth++) {
            $Parent = [string] (Get-PropertyData `
                -InstanceId $Cursor `
                -KeyName 'DEVPKEY_Device_Parent'
            )
            if ([string]::IsNullOrWhiteSpace($Parent)) { break }
            $Ancestors += $Parent
            $Cursor = $Parent
        }

        if ($Ancestors -notcontains $TransportAnchor) {
            Stop-Gate `
                -Code 'HALO3_TRANSPORT_TOPOLOGY_MISMATCH' `
                -Message 'The exact HALO3 PnP device is no longer under its admitted Thunderbolt anchor.'
        }

        if (Test-ActiveWindowsDisplay -InstanceId $PnpGpu.InstanceId) {
            Stop-Gate `
                -Code 'HALO3_ACTIVE_DISPLAY_REFUSED' `
                -Message 'Windows reports an active display on the exact HALO3 Seat; no device was changed.'
        }

        $ComputeProcesses = @(
            Get-NvidiaComputeProcesses -GpuUuid $GpuUuid
        )
        $AuthorizedBraveHelpers = @()

        foreach ($ComputeProcess in $ComputeProcesses) {
            $Helper = Get-AuthorizedBraveGpuHelper -ProcessId ([int] $ComputeProcess.Pid)
            if ($null -eq $Helper) {
                Stop-Gate `
                    -Code 'HALO3_ACTIVE_COMPUTE_PROCESS_REFUSED' `
                    -Message "The exact HALO3 GPU has a non-authorized active process PID $($ComputeProcess.Pid)."
            }
            $AuthorizedBraveHelpers += $Helper
        }

        if ($AuthorizedBraveHelpers.Count -ne 0 -and -not $DrainAuthorizedBraveGpuHelpers) {
            Stop-Gate `
                -Code 'HALO3_AUTHORIZED_BRAVE_HELPERS_NOT_DRAINED' `
                -Message "The exact HALO3 GPU has $($AuthorizedBraveHelpers.Count) validated Brave helper process(es)."
        }

        Write-Host ''
        Write-Host 'STC MARY HALO3 CONTINUITY GATE' -ForegroundColor Cyan
        Write-Host ''
        Write-Host 'What this proves:'
        Write-Host '  The accepted resident CPU result still reproduces after the exact'
        Write-Host '  optional accelerator becomes unavailable.'
        Write-Host ''
        Write-Host 'What the script will do:'
        Write-Host '  1. Disable one exact Windows PnP GPU device.'

        Write-Host '  2. Confirm that its admitted UUID disappears from NVIDIA visibility.'
        Write-Host '  3. Run the resident continuity workload, independent verification,'
        Write-Host '     and three-way comparison.'
        Write-Host '  4. Stop at two_cell_partition / HOLD.'
        Write-Host '  5. Re-enable the exact same device and confirm the UUID returns.'
        Write-Host ''
        Write-Host 'What you are NOT doing:'
        Write-Host '  You are not guessing which cable to pull.'
        Write-Host '  You are not turning off the host.'
        Write-Host '  You are not deleting the accepted HALO3 result.'
        Write-Host '  You are not starting the Cell or successor phases.'
        Write-Host ''
        Write-Host 'Exact local device:' -ForegroundColor Yellow
        Write-Host ("  GPU:       {0}" -f $GpuName)
        Write-Host ("  Seat ID:   {0}" -f $Halo3Seat.seatId)
        Write-Host ("  Torch index:{0}" -f $SelectedCudaIndex)
        Write-Host ("  NVIDIA index:{0}" -f $SelectedGpu.index)
        Write-Host ("  PCI bus:   {0}" -f $GpuPciBusId)
        Write-Host ("  PnP name:  {0}" -f $PnpGpu.FriendlyName)
        Write-Host ("  Location:  {0}" -f $PnpGpu.Location)
        Write-Host ''
        Write-Host 'Safety checks already passed:'
        Write-Host '  Windows does not report an active display on this GPU.'
        if ($AuthorizedBraveHelpers.Count -eq 0) {
            Write-Host '  NVIDIA reports no active process on this GPU.'
        }
        else {
            Write-Host ("  {0} authorized Brave GPU/video helper(s) will be drained immediately before disable." -f $AuthorizedBraveHelpers.Count)
        }
        Write-Host ''

        if (-not $NonInteractive) {
            $Confirmation = Read-Host `
                'Type DISABLE EXACT HALO3 to perform the reversible gate'

            if ($Confirmation -cne 'DISABLE EXACT HALO3') {
                Stop-Gate `
                    -Code 'OPERATOR_DID_NOT_CONFIRM' `
                    -Message 'The exact operator confirmation was not supplied.'
            }
        }
        else {
            Stop-Gate `
                -Code 'NONINTERACTIVE_PHYSICAL_GATE_REFUSED' `
                -Message 'This physical gate requires one informed local confirmation.'
        }
        foreach ($Helper in $AuthorizedBraveHelpers) {
            $CurrentHelper = Get-AuthorizedBraveGpuHelper -ProcessId ([int] $Helper.ProcessId)
            if ($null -eq $CurrentHelper -or [string] $CurrentHelper.Role -ne [string] $Helper.Role) {
                Stop-Gate `
                    -Code 'HALO3_BRAVE_HELPER_IDENTITY_CHANGED' `
                    -Message "Authorized Brave helper PID $($Helper.ProcessId) changed before the gate."
            }
            Stop-Process -Id ([int] $Helper.ProcessId) -ErrorAction Stop
        }

        $GateStartedUtc = [DateTime]::UtcNow.ToString('o')

        Disable-PnpDevice `
            -InstanceId $PnpGpu.InstanceId `
            -Confirm:$false `
            -ErrorAction Stop

        $WasDisabled = $true

        $Disappeared = Wait-Until `
            -TimeoutSeconds $DeviceDisappearTimeoutSeconds `
            -Predicate {
                $Inventory = Get-NvidiaInventory
                if (-not $Inventory.Success) {
                    return $false
                }

                $Visible = @(
                    $Inventory.Rows |
                    Where-Object { $_.Uuid -eq $GpuUuid }
                )
                return $Visible.Count -eq 0
            }

        if (-not $Disappeared) {
            Stop-Gate `
                -Code 'HALO3_DID_NOT_BECOME_INACCESSIBLE' `
                -Message 'The exact HALO3 UUID remained visible after PnP disable.'
        }

        $BecameInaccessible = $true
    }

    if ($NeedContinuityResult) {
        $ContinuityInvocation = Invoke-BoundPowerShellTool `
            -Script $Tool `
            -Arguments @(
                'run-workload',
                '--feed', $Feed,
                '--backend', 'python',
                '--out', $Continuity
            )

        if ($ContinuityInvocation.ExitCode -ne 0) {
            $Code = Get-StableErrorCode -Output $ContinuityInvocation.Output
            Stop-Gate `
                -Code $Code `
                -Message 'Post-HALO3 resident workload refused.'
        }
    }

    Assert-RegularFile `
        -Path $Continuity `
        -Code 'CONTINUITY_RESULT_NOT_COMMITTED' `
        -Label 'Post-HALO3 resident result'

    $ContinuityJson = Read-JsonFile `
        -Path $Continuity `
        -Label 'CONTINUITY_RESULT'

    $ContinuityResultId = [string] $ContinuityJson.resultId

    if (-not (Test-Path -LiteralPath $ContinuityVerification)) {
        $ContinuityVerificationInvocation = Invoke-BoundPowerShellTool `
            -Script $Tool `
            -Arguments @(
                'verify-workload',
                '--feed', $Feed,
                '--result', $Continuity,
                '--out', $ContinuityVerification
            )

        if ($ContinuityVerificationInvocation.ExitCode -ne 0) {
            $Code = Get-StableErrorCode `
                -Output $ContinuityVerificationInvocation.Output
            Stop-Gate `
                -Code $Code `
                -Message 'Post-HALO3 independent verification refused.'
        }
    }

    Assert-RegularFile `
        -Path $ContinuityVerification `
        -Code 'CONTINUITY_VERIFICATION_NOT_COMMITTED' `
        -Label 'Post-HALO3 independent verification'

    $ContinuityVerificationJson = Read-JsonFile `
        -Path $ContinuityVerification `
        -Label 'CONTINUITY_VERIFICATION'

    $ContinuityVerificationId =
        [string] $ContinuityVerificationJson.verificationId

    if (-not (Test-Path -LiteralPath $Comparison)) {
        $ComparisonInvocation = Invoke-BoundPowerShellTool `
            -Script $Tool `
            -Arguments @(
                'compare-workloads',
                '--baseline', $Baseline,
                '--accelerated', $Halo3Result,
                '--continuity', $Continuity,
                '--out', $Comparison
            )

        if ($ComparisonInvocation.ExitCode -ne 0) {
            $Code = Get-StableErrorCode -Output $ComparisonInvocation.Output
            Stop-Gate `
                -Code $Code `
                -Message 'Three-way continuity comparison refused.'
        }
    }

    Assert-RegularFile `
        -Path $Comparison `
        -Code 'CONTINUITY_COMPARISON_NOT_COMMITTED' `
        -Label 'Three-way continuity comparison'

    $ComparisonJson = Read-JsonFile `
        -Path $Comparison `
        -Label 'CONTINUITY_COMPARISON'

    $ComparisonId = [string] $ComparisonJson.comparisonId

    $Status = Invoke-ConductorJson `
        -Conductor $Conductor `
        -Command 'status' `
        -Workstation $Workstation

    [void] (
        Invoke-ConductorJson `
            -Conductor $Conductor `
            -Command 'render' `
            -Workstation $Workstation
    )

    [void] (
        Invoke-ConductorJson `
            -Conductor $Conductor `
            -Command 'public-projection' `
            -Workstation $Workstation
    )

    [void] (
        Invoke-ConductorJson `
            -Conductor $Conductor `
            -Command 'verify' `
            -Workstation $Workstation
    )

    $Status = Invoke-ConductorJson `
        -Conductor $Conductor `
        -Command 'status' `
        -Workstation $Workstation

    if ((Get-PhaseState -Status $Status -Phase 'post_halo3_continuity') -ne 'CLOSED') {
        Stop-Gate `
            -Code 'POST_HALO3_CONTINUITY_NOT_CLOSED' `
            -Message 'Post-HALO3 continuity did not reconstruct as closed.'
    }

    if (
        [string] $Status.currentPhase -ne 'two_cell_partition' -or
        [string] $Status.currentPhaseState -ne 'HOLD' -or
        [int] $Status.closedPhaseCount -ne 7 -or
        [int] $Status.heldPhaseCount -ne 5 -or
        [int] $Status.refusedPhaseCount -ne 0
    ) {
        Stop-Gate `
            -Code 'TWO_CELL_STOP_WALL_MISSED' `
            -Message 'Campaign did not stop at two_cell_partition / HOLD.'
    }

    if ([string] $Status.authority -ne 'none') {
        Stop-Gate `
            -Code 'AUTHORITY_WIDENED' `
            -Message 'Conductor authority differs.'
    }

    if ($Status.privateFlightCompleted -ne $false) {
        Stop-Gate `
            -Code 'PRIVATE_FLIGHT_COMPLETION_WIDENED' `
            -Message 'Private flight is incorrectly marked complete.'
    }

    Assert-RegularFile `
        -Path $WorkstationProjection `
        -Code 'CANONICAL_PROJECTION_ABSENT' `
        -Label 'Canonical workstation public projection'
}
catch {
    $Raw = $_.Exception.Message
    $Parts = $Raw -split '\|', 2

    if ($Parts.Count -ge 1 -and $Parts[0]) {
        $RefusalCode = $Parts[0]
    }
    else {
        $RefusalCode = 'HALO3_CONTINUITY_GATE_REFUSED'
    }
}
finally {
    if ($WasDisabled -and $null -ne $PnpGpu) {
        try {
            Enable-PnpDevice `
                -InstanceId $PnpGpu.InstanceId `
                -Confirm:$false `
                -ErrorAction Stop

            $RestoreSucceeded = Wait-Until `
                -TimeoutSeconds $DeviceRestoreTimeoutSeconds `
                -Predicate {
                    $Inventory = Get-NvidiaInventory
                    if (-not $Inventory.Success) {
                        return $false
                    }

                    $Visible = @(
                        $Inventory.Rows |
                        Where-Object { $_.Uuid -eq $GpuUuid }
                    )
                    return $Visible.Count -eq 1
                }
        }
        catch {
            $RestoreSucceeded = $false
            if ($null -eq $RefusalCode) {
                $RefusalCode = 'HALO3_RESTORE_REFUSED'
            }
        }
    }

    $GateEndedUtc = [DateTime]::UtcNow.ToString('o')

    if ($null -ne $Workstation -and $null -ne $SelectedGpu) {
        try {
            $ReceiptDirectory = Join-Path $Workstation 'physical-gate-receipts'
            $ReceiptName = (
                'halo3-reversible-interruption-{0}.private.json' -f
                ([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ'))
            )
            $InterruptionReceiptPath = Join-Path $ReceiptDirectory $ReceiptName

            $Receipt = [ordered]@{
                schema =
                    'stc-mary-halo3-reversible-interruption-private/1'
                campaignId = $CampaignId
                method = 'windows_pnp_disable_exact_device'
                halo3SeatId = [string] $Config.halo3Seat.seatId
                initialCudaDeviceIndex = [int] $Config.halo3Seat.initialCudaDeviceIndex
                observedTorchCudaDeviceIndex = [int] $SelectedCudaIndex
                observedNvidiaIndex = [int] $SelectedGpu.index
                transportAnchorPnpInstanceId = [string] $Config.halo3Seat.transportAnchorPnpInstanceId
                gpu = [ordered]@{
                    name = [string] $SelectedGpu.name
                    uuid = [string] $SelectedGpu.uuid
                    pciBusId = [string] $SelectedGpu.'pci.bus_id'
                    pnpInstanceId = if ($null -ne $PnpGpu) {
                        [string] $PnpGpu.InstanceId
                    }
                    else {
                        $null
                    }
                }
                startedAtUtc = $GateStartedUtc
                endedAtUtc = $GateEndedUtc
                becameInaccessible = [bool] $BecameInaccessible
                continuityResultId = $ContinuityResultId
                continuityVerificationId = $ContinuityVerificationId
                comparisonId = $ComparisonId
                restored = [bool] $RestoreSucceeded
                refusalCode = $RefusalCode
                authority = 'none'
                claimBoundary =
                    'Private receipt for one reversible exact-device interruption and resident continuity proof. It grants no physical-Estate, mission, command, targeting, engagement, effector, or weapons authority.'
            }

            Write-PrivateReceipt `
                -Path $InterruptionReceiptPath `
                -Body $Receipt

            $InterruptionReceiptSha256 =
                Get-Sha256 -Path $InterruptionReceiptPath
        }
        catch {
            if ($null -eq $RefusalCode) {
                $RefusalCode = 'INTERRUPTION_RECEIPT_WRITE_REFUSED'
            }
        }
    }
}

$ProjectionHash = $null
if (
    $null -ne $WorkstationProjection -and
    (Test-Path -LiteralPath $WorkstationProjection -PathType Leaf)
) {
    $ProjectionHash = Get-Sha256 -Path $WorkstationProjection
}

if ($null -eq $RefusalCode) {
    if (-not $RestoreSucceeded) {
        $TerminalPacket = [ordered]@{
            status = 'REFUSED'
            terminal_code =
                'POST_HALO3_CONTINUITY_ACCEPTED_HALO3_RESTORE_HELD'
            campaignId = $CampaignId
            interruption_method =
                'windows_pnp_disable_exact_device'
            interruption_receipt_sha256 =
                $InterruptionReceiptSha256
            continuity_receipt_identity =
                $ContinuityResultId
            continuity_verification_identity =
                $ContinuityVerificationId
            comparison_identity =
                $ComparisonId
            canonical_workstation_public_projection_sha256 =
                $ProjectionHash
            body_free_phase_summary = [ordered]@{
                post_halo3_continuity = 'CLOSED'
                current_phase = 'two_cell_partition'
                current_phase_state = 'HOLD'
                closed_phases = 7
                held_phases = 5
                refused_phases = 0
                private_flight_complete = $false
            }
            halo3_restored = $false
            refusal_code = 'HALO3_RESTORE_REFUSED'
            authority = 'none'
        }
    }
    else {
        $TerminalPacket = [ordered]@{
            status = 'PASS'
            terminal_code =
                'POST_HALO3_CONTINUITY_ACCEPTED'
            campaignId = $CampaignId
            interruption_method =
                'windows_pnp_disable_exact_device'
            interruption_receipt_sha256 =
                $InterruptionReceiptSha256
            continuity_receipt_identity =
                $ContinuityResultId
            continuity_verification_identity =
                $ContinuityVerificationId
            comparison_identity =
                $ComparisonId
            canonical_workstation_public_projection_sha256 =
                $ProjectionHash
            body_free_phase_summary = [ordered]@{
                post_halo3_continuity = 'CLOSED'
                current_phase = 'two_cell_partition'
                current_phase_state = 'HOLD'
                closed_phases = 7
                held_phases = 5
                refused_phases = 0
                private_flight_complete = $false
            }
            halo3_restored = $true
            refusal_code = $null
            authority = 'none'
        }
    }
}
else {
    $TerminalPacket = [ordered]@{
        status = 'REFUSED'
        terminal_code = 'HALO3_REVERSIBLE_CONTINUITY_GATE_REFUSED'
        campaignId = $CampaignId
        interruption_method =
            'windows_pnp_disable_exact_device'
        interruption_receipt_sha256 =
            $InterruptionReceiptSha256
        continuity_receipt_identity =
            $ContinuityResultId
        continuity_verification_identity =
            $ContinuityVerificationId
        comparison_identity =
            $ComparisonId
        canonical_workstation_public_projection_sha256 =
            $ProjectionHash
        body_free_phase_summary = [ordered]@{
            current_phase =
                'post_halo3_continuity'
            private_flight_complete = $false
        }
        halo3_restored = [bool] $RestoreSucceeded
        refusal_code = $RefusalCode
        authority = 'none'
    }
}

$TerminalPacket | ConvertTo-Json -Depth 10
