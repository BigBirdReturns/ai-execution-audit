[CmdletBinding()]
param(
  [Parameter(Mandatory = $true, Position = 0)]
  [ValidateSet('validate-profile','validate-bindings','compile-plan','validate-plan','validate-fixtures','campaign','source-set','build-extension','verify-extension')]
  [string]$Command,

  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$Arguments
)

$ErrorActionPreference = 'Stop'
$Tool = Join-Path $PSScriptRoot 'axm_head_browser_audition_operation_plan_01.py'
if (-not (Test-Path -LiteralPath $Tool -PathType Leaf)) {
  throw "Operation-plan Python entrypoint is unavailable: $Tool"
}
& python $Tool $Command @Arguments
exit $LASTEXITCODE
