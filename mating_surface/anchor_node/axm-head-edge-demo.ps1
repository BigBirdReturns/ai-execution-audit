$ErrorActionPreference = 'Stop'

$Python = if ($env:AXM_HEAD_PYTHON) { $env:AXM_HEAD_PYTHON } elseif ($env:STC_MARY_PYTHON) { $env:STC_MARY_PYTHON } else { 'python' }
$Tool = Join-Path $PSScriptRoot 'axm_head_edge_demo.py'
$Bootstrap = Join-Path $PSScriptRoot 'verify_axm_head_bootstrap.py'

if ($args.Length -gt 0 -and $args[0] -eq 'verify-volume') {
    $Remaining = @()
    if ($args.Length -gt 1) {
        $Remaining = $args[1..($args.Length - 1)]
    }
    & $Python $Bootstrap @Remaining
} else {
    & $Python $Tool @args
}
exit $LASTEXITCODE
