[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $Arguments
)

$ErrorActionPreference = 'Stop'
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Tool = Join-Path $ScriptRoot 'stc_mary_flight_01_cartridge.py'

if ($env:STC_MARY_PYTHON) {
    $Python = $env:STC_MARY_PYTHON
} else {
    $Python = 'python'
}

& $Python $Tool @Arguments
exit $LASTEXITCODE
