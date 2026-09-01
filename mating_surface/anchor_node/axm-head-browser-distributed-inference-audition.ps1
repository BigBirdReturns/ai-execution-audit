[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('validate-profile', 'validate-fixtures', 'campaign', 'assess', 'materialize', 'probe-digest', 'source-set', 'verify', 'bootstrap-verify')]
    [string]$Command,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
)

$ErrorActionPreference = 'Stop'
$Python = if ($env:AXM_PYTHON) { $env:AXM_PYTHON } else { 'python' }
$Root = $PSScriptRoot
$Tool = Join-Path $Root 'axm_head_browser_distributed_inference_audition.py'
$Verifier = Join-Path $Root 'verify_axm_head_browser_distributed_inference_audition.py'
$Bootstrap = Join-Path $Root 'verify_axm_head_browser_distributed_inference_audition_bootstrap.py'

switch ($Command) {
    'verify' {
        & $Python $Verifier @Arguments
    }
    'bootstrap-verify' {
        & $Python $Bootstrap $Verifier @Arguments
    }
    default {
        & $Python $Tool $Command @Arguments
    }
}

exit $LASTEXITCODE
