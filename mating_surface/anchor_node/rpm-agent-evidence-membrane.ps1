[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Upstream,

    [string]$OutputDirectory = (Join-Path ([System.IO.Path]::GetTempPath()) "rpm-agent-evidence-membrane"),

    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$Anchor = Split-Path -Parent $MyInvocation.MyCommand.Path
$EstateRoot = Split-Path -Parent (Split-Path -Parent $Anchor)
$Profile = Join-Path $Anchor "rpm-agent-evidence-membrane-profile-01.json"
$Bootstrap = Join-Path $Anchor "verify_rpm_agent_estate_bootstrap.py"
$Verifier = Join-Path $Anchor "verify_rpm_agent_estate_receipt.py"
$ResolvedUpstream = (Resolve-Path $Upstream).Path

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$Receipt = Join-Path $OutputDirectory "qualification-receipt.json"
$Verification = Join-Path $OutputDirectory "verification-receipt.json"

& $Python $Bootstrap `
    --upstream $ResolvedUpstream `
    --profile $Profile `
    --estate-root $EstateRoot `
    --out $Receipt `
    --enforce-profile-expectation
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& $Python $Verifier `
    --profile $Profile `
    --receipt $Receipt `
    --out $Verification
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Output "qualification_receipt=$Receipt"
Write-Output "verification_receipt=$Verification"
