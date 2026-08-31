[CmdletBinding(PositionalBinding = $false)]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $CompatibilityArguments
)

$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Core = Join-Path $Here 'stc_mary_sealed_campaign_compatibility.py'

if (-not (Test-Path -LiteralPath $Core -PathType Leaf)) {
    throw "STC MARY sealed-campaign compatibility core is absent: $Core"
}

$Python = $env:STC_MARY_PYTHON
if ([string]::IsNullOrWhiteSpace($Python)) {
    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $PythonCommand) {
        throw 'Python 3.12 or later is required. Set STC_MARY_PYTHON to the exact interpreter path.'
    }
    $Python = $PythonCommand.Source
}

& $Python $Core @CompatibilityArguments
exit $LASTEXITCODE
