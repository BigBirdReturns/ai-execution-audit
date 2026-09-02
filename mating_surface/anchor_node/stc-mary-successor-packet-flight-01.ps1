<#
.SYNOPSIS
    Operator entrypoint for the STC MARY successor packet flight 01 source set.

.DESCRIPTION
    Drives the admitted legal order for one stc-mary/private-flight-packet/0.2 successor
    packet, in the only sequence the source set admits:

        compile -> verify-packet -> (admit, outside this script)
                -> verify-evidence-materialization -> materialize-or-resume
                -> record-or-resume -> close-pre-seal -> seal-or-resume
                -> verify-detached -> close-post-seal -> status

    This script orchestrates nothing on its own authority. Every step shells out to the
    measured Python surface that owns it, and every step writes its receipt outside the
    packet and outside the sealed directory.

    The admission step is deliberately NOT a command here. Evidence admission belongs to
    the separately admitted packet-evidence-admission@2 gate and its own bootstrap, which
    live in production and are not part of this source set. Run that gate yourself and
    pass its bootstrap-authenticated receipt to -AdmissionReceipt.

    The materialize step is the bridge between that receipt and the packet. The admitted
    gate publishes forty-three evidence roles but places no body anywhere, so materialize
    replays the admitted candidate-body mapping and issues the receipt record consumes.
    Without it a packet could carry any bodies at all beside a forty-three-role root, and
    record refuses rather than let that happen.

.PARAMETER Command
    One of the exact ten operation roles, plus admit-source and qualify.

.NOTES
    Campaign application is held. Every fixture this source set can build is synthetic and
    every campaign label it will accept carries the SYNTHETIC- prefix. Real Campaign A
    application stays held until issue #94 admits a named-human authentication mechanism.

    Authority: none. This script records no stage on its own behalf, signs no human
    statement, issues no stage confirmation, and grants no physical, mission, command,
    targeting, engagement, effector or weapons authority.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('admit-source', 'compile', 'verify-packet', 'verify-evidence-materialization', 'materialize-or-resume', 'record-or-resume', 'close-pre-seal', 'seal-or-resume', 'verify-detached', 'close-post-seal', 'status', 'qualify')]
    [string] $Command,

    [string] $Workstation,
    [string] $Predecessor,
    [string] $Packet,
    [string] $Sealed,
    [string] $AdmissionReceipt,
    [string] $MaterializationReceipt,
    [string] $AuthenticationReceipt,
    [string] $Candidates,
    [string] $PreSealClosure,
    [string] $DetachedVerification,
    [string] $SourceAdmissionReceipt,
    [string] $SourceCommit,
    [string] $ExecutionReceipt,
    [string] $TransactionWorkspace,
    [string] $SealTransactionReceipt,
    [string] $Out,
    [string] $Python = 'python'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$anchor = Split-Path -Parent $MyInvocation.MyCommand.Path
$repositoryRoot = Split-Path -Parent (Split-Path -Parent $anchor)
$profilePath = Join-Path $anchor 'stc-mary-successor-packet-flight-01-profile-01.json'

function Assert-Supplied {
    param([string] $Name, [string] $Value)
    if ([string]::IsNullOrWhiteSpace($Value)) {
        throw "$Command requires -$Name"
    }
}

function Invoke-Surface {
    param([string] $Module, [string[]] $Arguments)
    $script = Join-Path $anchor $Module
    if (-not (Test-Path -LiteralPath $script)) {
        throw "measured surface is absent: $Module"
    }
    & $Python -I -S -B $script @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Module refused with exit code $LASTEXITCODE"
    }
}

function Invoke-MeasuredSurface {
    param([string] $Role, [string[]] $Arguments, [switch] $CompileMode)
    $launcher = Join-Path $anchor 'invoke_stc_mary_successor_packet_source_bootstrap.py'
    if (-not (Test-Path -LiteralPath $launcher)) {
        throw 'measured execution launcher is absent'
    }
    $custodyOut = $ExecutionReceipt
    if ([string]::IsNullOrWhiteSpace($custodyOut)) {
        if ([string]::IsNullOrWhiteSpace($Out)) {
            throw "$Command requires -ExecutionReceipt when -Out is absent"
        }
        $custodyOut = "$Out.execution-receipt.json"
    }
    $launcherArguments = @('--role', $Role, '--execution-receipt', $custodyOut)
    if ($CompileMode) {
        $launcherArguments += @(
            '--repository-root', $repositoryRoot,
            '--source-admission-receipt', $SourceAdmissionReceipt
        )
    }
    else {
        Assert-Supplied -Name 'Packet' -Value $Packet
        $launcherArguments += @('--packet', $Packet)
    }
    $launcherArguments += '--'
    $launcherArguments += $Arguments
    & $Python -I -S -B $launcher @launcherArguments
    if ($LASTEXITCODE -ne 0) {
        throw "measured $Role execution refused with exit code $LASTEXITCODE"
    }
}

switch ($Command) {
    'admit-source' {
        Assert-Supplied -Name 'SourceCommit' -Value $SourceCommit
        $arguments = @(
            '--repository-root', $repositoryRoot,
            '--source-commit', $SourceCommit
        )
        if ($Out) { $arguments += @('--out', $Out) }
        Invoke-Surface -Module 'verify_stc_mary_successor_source_admission_bootstrap.py' -Arguments $arguments
    }

    'compile' {
        Assert-Supplied -Name 'Workstation' -Value $Workstation
        Assert-Supplied -Name 'Predecessor' -Value $Predecessor
        Assert-Supplied -Name 'Packet' -Value $Packet
        Assert-Supplied -Name 'SourceAdmissionReceipt' -Value $SourceAdmissionReceipt
        $arguments = @(
            'compile',
            '--workstation', $Workstation,
            '--predecessor', $Predecessor,
            '--successor', $Packet,
            '--repository-root', $repositoryRoot,
            '--source-admission-receipt', $SourceAdmissionReceipt
        )
        if ($Out) { $arguments += @('--out', $Out) }
        Invoke-MeasuredSurface -Role 'compile' -Arguments $arguments -CompileMode
    }

    'verify-packet' {
        # Always through the bootstrap. The verifier cannot authenticate itself, and a
        # direct run reports bootstrapAuthenticated: false by design.
        Assert-Supplied -Name 'Packet' -Value $Packet
        $arguments = @(
            '--packet', $Packet,
            '--profile', '@profile',
            '--repository-root', $repositoryRoot
        )
        if ($Out) { $arguments += @('--out', $Out) }
        Invoke-MeasuredSurface -Role 'verify-packet' -Arguments $arguments
    }

    'verify-evidence-materialization' {
        Assert-Supplied -Name 'Packet' -Value $Packet
        Assert-Supplied -Name 'AdmissionReceipt' -Value $AdmissionReceipt
        Assert-Supplied -Name 'Candidates' -Value $Candidates
        $arguments = @(
            '--packet', $Packet,
            '--admission-receipt', $AdmissionReceipt,
            '--candidates', $Candidates,
            '--profile', '@profile',
            '--repository-root', $repositoryRoot
        )
        if ($Out) { $arguments += @('--out', $Out) }
        Invoke-MeasuredSurface -Role 'verify-evidence-materialization' -Arguments $arguments
    }

    'materialize-or-resume' {
        # The bridge verifies the complete evidence denominator, promotes an exact
        # recoverable prefix, and emits completion only at 43 / 43. It records no stage.
        Assert-Supplied -Name 'Packet' -Value $Packet
        Assert-Supplied -Name 'AdmissionReceipt' -Value $AdmissionReceipt
        Assert-Supplied -Name 'Candidates' -Value $Candidates
        Assert-Supplied -Name 'Out' -Value $Out
        $materializationTransactions = $TransactionWorkspace
        if ([string]::IsNullOrWhiteSpace($materializationTransactions)) {
            $materializationTransactions = "$Out.materialization-transaction"
        }
        $arguments = @(
            '--packet', $Packet,
            '--admission-receipt', $AdmissionReceipt,
            '--candidates', $Candidates,
            '--profile', '@profile',
            '--repository-root', $repositoryRoot,
            '--transaction-workspace', $materializationTransactions
        )
        if ($Out) { $arguments += @('--out', $Out) }
        Invoke-MeasuredSurface -Role 'materialize-or-resume' -Arguments $arguments
    }

    'record-or-resume' {
        Assert-Supplied -Name 'Packet' -Value $Packet
        Assert-Supplied -Name 'AdmissionReceipt' -Value $AdmissionReceipt
        Assert-Supplied -Name 'MaterializationReceipt' -Value $MaterializationReceipt
        Assert-Supplied -Name 'AuthenticationReceipt' -Value $AuthenticationReceipt
        Assert-Supplied -Name 'Candidates' -Value $Candidates
        Assert-Supplied -Name 'Out' -Value $Out
        $recordingTransactions = $TransactionWorkspace
        if ([string]::IsNullOrWhiteSpace($recordingTransactions)) {
            $recordingTransactions = "$Out.recording-transactions"
        }
        $arguments = @(
            '--packet', $Packet,
            '--admission-receipt', $AdmissionReceipt,
            '--materialization-receipt', $MaterializationReceipt,
            '--authentication-receipt', $AuthenticationReceipt,
            '--candidates', $Candidates,
            '--repository-root', $repositoryRoot,
            '--transaction-workspace', $recordingTransactions
        )
        if ($Out) { $arguments += @('--out', $Out) }
        Invoke-MeasuredSurface -Role 'record-or-resume' -Arguments $arguments
    }

    'close-pre-seal' {
        Assert-Supplied -Name 'Packet' -Value $Packet
        Assert-Supplied -Name 'AdmissionReceipt' -Value $AdmissionReceipt
        Assert-Supplied -Name 'MaterializationReceipt' -Value $MaterializationReceipt
        Assert-Supplied -Name 'AuthenticationReceipt' -Value $AuthenticationReceipt
        Assert-Supplied -Name 'Candidates' -Value $Candidates
        $arguments = @(
            '--packet', $Packet,
            '--admission-receipt', $AdmissionReceipt,
            '--materialization-receipt', $MaterializationReceipt,
            '--authentication-receipt', $AuthenticationReceipt,
            '--candidates', $Candidates,
            '--profile', '@profile',
            '--repository-root', $repositoryRoot
        )
        if ($Out) { $arguments += @('--out', $Out) }
        Invoke-MeasuredSurface -Role 'close-pre-seal' -Arguments $arguments
    }

    'seal-or-resume' {
        Assert-Supplied -Name 'Packet' -Value $Packet
        Assert-Supplied -Name 'Sealed' -Value $Sealed
        Assert-Supplied -Name 'PreSealClosure' -Value $PreSealClosure
        $arguments = @(
            'seal',
            '--packet', $Packet,
            '--sealed', $Sealed,
            '--pre-seal-closure', $PreSealClosure,
            '--repository-root', $repositoryRoot
        )
        if ($SealTransactionReceipt) { $arguments += @('--transaction-receipt', $SealTransactionReceipt) }
        if ($Out) { $arguments += @('--out', $Out) }
        Invoke-MeasuredSurface -Role 'seal-or-resume' -Arguments $arguments
    }

    'verify-detached' {
        Assert-Supplied -Name 'Packet' -Value $Packet
        Assert-Supplied -Name 'Sealed' -Value $Sealed
        $arguments = @(
            'verify-detached',
            '--sealed', $Sealed,
            '--repository-root', $repositoryRoot
        )
        if ($Out) { $arguments += @('--out', $Out) }
        Invoke-MeasuredSurface -Role 'verify-detached' -Arguments $arguments
    }

    'close-post-seal' {
        Assert-Supplied -Name 'Packet' -Value $Packet
        Assert-Supplied -Name 'Sealed' -Value $Sealed
        Assert-Supplied -Name 'PreSealClosure' -Value $PreSealClosure
        Assert-Supplied -Name 'DetachedVerification' -Value $DetachedVerification
        $arguments = @(
            '--packet', $Packet,
            '--sealed', $Sealed,
            '--pre-seal-closure', $PreSealClosure,
            '--detached-verification', $DetachedVerification,
            '--profile', '@profile',
            '--repository-root', $repositoryRoot
        )
        if ($SealTransactionReceipt) { $arguments += @('--seal-transaction-receipt', $SealTransactionReceipt) }
        if ($Out) { $arguments += @('--out', $Out) }
        Invoke-MeasuredSurface -Role 'close-post-seal' -Arguments $arguments
    }

    'status' {
        Assert-Supplied -Name 'Packet' -Value $Packet
        $arguments = @('status', '--packet', $Packet)
        Invoke-MeasuredSurface -Role 'status' -Arguments $arguments
    }

    'qualify' {
        # The full hostile witness denominator, including the one executable traversal
        # that begins at a configured predecessor at zero of sixteen.
        $conformance = Join-Path $anchor 'conformance'
        Push-Location $conformance
        try {
            & $Python -I -S -B -m unittest discover -s . -p 'test_stc_mary_successor_packet_flight_01.py' -v
            if ($LASTEXITCODE -ne 0) {
                throw "the successor flight witness denominator refused with exit code $LASTEXITCODE"
            }
        }
        finally {
            Pop-Location
        }
    }
}
