[CmdletBinding()]
param(
    [Parameter(Position=0, Mandatory=$true)][string]$Command,
    [Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments
)
$ErrorActionPreference = 'Stop'
$script = Join-Path $PSScriptRoot 'axm_head_physical_long_haul_join.py'
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command py -ErrorAction Stop; & $python.Source -3.12 $script $Command @Arguments; exit $LASTEXITCODE }
& $python.Source $script $Command @Arguments
exit $LASTEXITCODE
