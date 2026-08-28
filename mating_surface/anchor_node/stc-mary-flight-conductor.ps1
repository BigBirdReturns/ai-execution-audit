[CmdletBinding(PositionalBinding = $false)]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $ConductorArguments
)

$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Core = Join-Path $Here 'stc_mary_flight_conductor.py'

if (-not (Test-Path -LiteralPath $Core -PathType Leaf)) {
    throw "STC MARY flight-conductor core is absent: $Core"
}

$Python = $env:STC_MARY_PYTHON
if ([string]::IsNullOrWhiteSpace($Python)) {
    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $PythonCommand) {
        $PythonCommand = Get-Command py -ErrorAction SilentlyContinue
        if ($null -eq $PythonCommand) {
            throw 'Python 3.11 or later is required. Set STC_MARY_PYTHON to the exact interpreter path.'
        }
        $Python = $PythonCommand.Source
        & $Python '-3' $Core @ConductorArguments
        exit $LASTEXITCODE
    }
    $Python = $PythonCommand.Source
}

& $Python $Core @ConductorArguments
exit $LASTEXITCODE
