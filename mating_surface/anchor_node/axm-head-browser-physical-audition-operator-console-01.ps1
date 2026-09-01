[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('validate-profile', 'validate-fixtures', 'campaign', 'validate-command', 'build-extension', 'verify-extension', 'source-set')]
    [string]$Command,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArguments
)

$ErrorActionPreference = 'Stop'
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Tool = Join-Path $ScriptRoot 'axm_head_browser_physical_audition_operator_console_01.py'
if (-not (Test-Path -LiteralPath $Tool -PathType Leaf)) {
    Write-Error "Operator console tool unavailable: $Tool"
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
