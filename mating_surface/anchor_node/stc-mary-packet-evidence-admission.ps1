[CmdletBinding(PositionalBinding = $false)]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $AdmissionArguments
)

$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Core = Join-Path $Here 'stc_mary_packet_evidence_admission.py'

if (-not (Test-Path -LiteralPath $Core -PathType Leaf)) {
    throw "STC MARY packet evidence admission core is absent: $Core"
}

$Python = $env:STC_MARY_PYTHON
if ([string]::IsNullOrWhiteSpace($Python)) {
    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $PythonCommand) {
        throw 'Python 3.12 or later is required. Set STC_MARY_PYTHON to the exact interpreter path.'
    }
    $Python = $PythonCommand.Source
}

& $Python $Core @AdmissionArguments
exit $LASTEXITCODE
