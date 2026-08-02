[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)]
    [string]$MameRoot,

    [Parameter(Mandatory = $true)]
    [string]$FramePath,

    [switch]$Apply
)

$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'c2simrehearsal'
$target = Join-Path (Resolve-Path $MameRoot) 'plugins\c2simrehearsal'
$resolvedFrame = Resolve-Path $FramePath

foreach ($required in @('init.lua', 'plugin.json')) {
    $path = Join-Path $source $required
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Plugin source is incomplete: $path"
    }
}

if (-not (Test-Path -LiteralPath $resolvedFrame -PathType Leaf)) {
    throw "Semantic host frame is missing: $resolvedFrame"
}

$frame = Get-Content -LiteralPath $resolvedFrame -Raw | ConvertFrom-Json
if ($frame.schema -ne 'standards-semantic-rehearsal-frame/1') {
    throw "Unsupported semantic host frame schema: $($frame.schema)"
}
if ($frame.status -notin @('reconciled', 'attention_required')) {
    throw "Unsupported semantic host frame status: $($frame.status)"
}

$plan = [ordered]@{
    schema = 'c2sim-semantic-rehearsal-mame-install-plan/1'
    mode = if ($Apply) { 'apply' } else { 'dry-run' }
    mame_root = (Resolve-Path $MameRoot).Path
    target = $target
    frame = $resolvedFrame.Path
    frame_id = $frame.frameId
    files = @('init.lua', 'plugin.json', 'semantic-host-frame.json')
    target_host_qualified = $false
    authority = 'none'
}

$plan | ConvertTo-Json -Depth 5

if (-not $Apply) {
    return
}

if ($PSCmdlet.ShouldProcess($target, 'Install read-only C2SIM semantic rehearsal MAME plugin')) {
    New-Item -ItemType Directory -Path $target -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $source 'init.lua') -Destination (Join-Path $target 'init.lua') -Force
    Copy-Item -LiteralPath (Join-Path $source 'plugin.json') -Destination (Join-Path $target 'plugin.json') -Force
    Copy-Item -LiteralPath $resolvedFrame -Destination (Join-Path $target 'semantic-host-frame.json') -Force
}
