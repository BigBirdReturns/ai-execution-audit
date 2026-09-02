[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('validate-profile', 'validate-fixtures', 'campaign', 'build-kit', 'assemble', 'verify', 'public-projection', 'source-set')]
    [string]$Command,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArguments
)

$ErrorActionPreference = 'Stop'
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ToolCandidates = @(
    (Join-Path $ScriptRoot 'axm_head_browser_physical_audition_packet_01.py'),
    (Join-Path (Join-Path $ScriptRoot 'source') 'axm_head_browser_physical_audition_packet_01.py')
)
$Tool = $null
foreach ($CandidateTool in $ToolCandidates) {
    if (Test-Path -LiteralPath $CandidateTool -PathType Leaf) {
        $Tool = $CandidateTool
        break
    }
}
if ($null -eq $Tool) {
    Write-Error "Packet compiler unavailable at repository or generated-kit coordinate: $($ToolCandidates -join ', ')"
    exit 2
}

$Candidates = @(
    @{ File = 'python'; Prefix = @() },
    @{ File = 'python3'; Prefix = @() },
    @{ File = 'py'; Prefix = @('-3') }
)

foreach ($Candidate in $Candidates) {
    $CommandInfo = Get-Command $Candidate.File -ErrorAction SilentlyContinue
    if ($null -eq $CommandInfo) { continue }
    & $Candidate.File @($Candidate.Prefix) -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 2)" 2>$null
    if ($LASTEXITCODE -ne 0) { continue }
    & $Candidate.File @($Candidate.Prefix) $Tool $Command @RemainingArguments
    exit $LASTEXITCODE
}

Write-Error 'Python 3.11 or later is required.'
exit 2
