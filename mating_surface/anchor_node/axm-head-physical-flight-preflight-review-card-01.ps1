$ErrorActionPreference = 'Stop'

$Python = $env:AXM_HEAD_PREFLIGHT_REVIEW_CARD_01_PYTHON
if ([string]::IsNullOrWhiteSpace($Python)) {
    $Python = 'python'
}

$Script = Join-Path $PSScriptRoot 'axm_head_physical_flight_preflight_review_card_01.py'
& $Python $Script @args
exit $LASTEXITCODE
