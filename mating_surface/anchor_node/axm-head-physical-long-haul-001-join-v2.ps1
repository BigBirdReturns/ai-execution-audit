$ErrorActionPreference = 'Stop'

$Python = $env:AXM_HEAD_JOIN_V2_PYTHON
if ([string]::IsNullOrWhiteSpace($Python)) {
    $Python = 'python'
}

$Script = Join-Path $PSScriptRoot 'axm_head_physical_long_haul_001_join_v2.py'
& $Python $Script @args
exit $LASTEXITCODE
