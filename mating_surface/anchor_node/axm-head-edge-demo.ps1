$ErrorActionPreference = 'Stop'

$Python = if ($env:AXM_HEAD_PYTHON) { $env:AXM_HEAD_PYTHON } elseif ($env:STC_MARY_PYTHON) { $env:STC_MARY_PYTHON } else { 'python' }
$Tool = Join-Path $PSScriptRoot 'axm_head_edge_demo.py'

& $Python $Tool @args
exit $LASTEXITCODE
