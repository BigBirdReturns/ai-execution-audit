[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('template-inputs', 'build-cell-pair', 'verify-cell', 'reconcile-cells', 'build-successor', 'verify-successor', 'validate-profile')]
    [string]$Command,

    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArguments
)

$ErrorActionPreference = 'Stop'
$Script = Join-Path $PSScriptRoot 'stc_mary_offline_carrier.py'
if (-not (Test-Path -LiteralPath $Script -PathType Leaf)) {
    throw "Offline carrier script is absent: $Script"
}

function Test-PythonCandidate {
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [string[]]$Prefix = @()
    )

    try {
        $versionText = & $Executable @Prefix -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $versionText) { return $null }
        $parts = $versionText.Trim().Split('.')
        if ($parts.Count -lt 2) { return $null }
        $major = [int]$parts[0]
        $minor = [int]$parts[1]
        if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 11)) { return $null }
        return [pscustomobject]@{ Executable = $Executable; Prefix = $Prefix; Version = $versionText.Trim() }
    }
    catch {
        return $null
    }
}

$candidates = @()
if ($env:STC_MARY_PYTHON) {
    $resolved = Resolve-Path -LiteralPath $env:STC_MARY_PYTHON -ErrorAction Stop
    $candidates += ,@($resolved.Path, @())
}
if (Get-Command py -ErrorAction SilentlyContinue) {
    $candidates += ,@('py', @('-3.13'))
    $candidates += ,@('py', @('-3.12'))
    $candidates += ,@('py', @('-3.11'))
}
if (Get-Command python -ErrorAction SilentlyContinue) {
    $candidates += ,@('python', @())
}

$selected = $null
foreach ($candidate in $candidates) {
    $selected = Test-PythonCandidate -Executable $candidate[0] -Prefix $candidate[1]
    if ($selected) { break }
}

if (-not $selected) {
    throw 'No Python 3.11 or later interpreter is available. Set STC_MARY_PYTHON to an exact interpreter path.'
}

& $selected.Executable @($selected.Prefix) $Script $Command @RemainingArguments
exit $LASTEXITCODE
