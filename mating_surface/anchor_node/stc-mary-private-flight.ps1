[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $PacketArguments
)

$ErrorActionPreference = 'Stop'
$runtime = Join-Path $PSScriptRoot 'stc_mary_private_flight_packet.mjs'

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw 'Node.js 24 or later is required to run the STC MARY private-flight packet.'
}

& node $runtime @PacketArguments
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    exit $exitCode
}
