$ErrorActionPreference = 'Stop'

# Delegate only to the authenticated Python bootstrap; this wrapper creates no worker or listener.
$Python = if ($env:AXM_HEAD_PYTHON) { $env:AXM_HEAD_PYTHON } elseif ($env:STC_MARY_PYTHON) { $env:STC_MARY_PYTHON } else { 'python' }
$Tool = Join-Path $PSScriptRoot 'axm_head_physical_long_haul_join.py'

& $Python $Tool @args
exit $LASTEXITCODE