[CmdletBinding(PositionalBinding = $false)]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $Arguments
)

$ErrorActionPreference = 'Stop'
$Tool = Join-Path $PSScriptRoot 'axm_head_browser_physical_flight_choreographer_01.py'
$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) { $Python = Get-Command py -ErrorAction Stop }
& $Python.Source $Tool @Arguments
exit $LASTEXITCODE
