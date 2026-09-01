<#
.SYNOPSIS
    Operator entrypoint for the STC MARY successor packet flight 01 source set.

.DESCRIPTION
    Drives the admitted legal order for one stc-mary/private-flight-packet/0.2 successor
    packet, in the only sequence the source set admits:

        compile -> verify -> (admit, outside this script) -> materialize -> record
                -> close-pre-seal -> seal -> verify-detached -> close-post-seal

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
    One of: compile, verify, materialize, record, close-pre-seal, seal, verify-detached,
    close-post-seal, qualify.

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
    [ValidateSet('compile', 'verify', 'materialize', 'record', 'close-pre-seal', 'seal', 'verify-detached', 'close-post-seal', 'qualify')]
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
    & $Python $script @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Module refused with exit code $LASTEXITCODE"
    }
}

switch ($Command) {
    'compile' {
        Assert-Supplied -Name 'Workstation' -Value $Workstation
        Assert-Supplied -Name 'Predecessor' -Value $Predecessor
        Assert-Supplied -Name 'Packet' -Value $Packet
        $arguments = @(
            'compile',
            '--workstation', $Workstation,
            '--predecessor', $Predecessor,
            '--successor', $Packet,
            '--repository-root', $repositoryRoot
        )
        if ($Out) { $arguments += @('--out', $Out) }
        Invoke-Surface -Module 'stc_mary_successor_packet_compiler.py' -Arguments $arguments
    }

    'verify' {
        # Always through the bootstrap. The verifier cannot authenticate itself, and a
        # direct run reports bootstrapAuthenticated: false by design.
        Assert-Supplied -Name 'Packet' -Value $Packet
        $arguments = @(
            '--packet', $Packet,
            '--profile', $profilePath,
            '--repository-root', $repositoryRoot
        )
        if ($Out) { $arguments += @('--out', $Out) }
        Invoke-Surface -Module 'verify_stc_mary_successor_packet_bootstrap.py' -Arguments $arguments
    }

    'materialize' {
        # The bridge between the admitted evidence denominator and the packet. It writes
        # nothing into the packet and records nothing; it only says which admitted body
        # belongs at which packet coordinate under which admitted role.
        Assert-Supplied -Name 'Packet' -Value $Packet
        Assert-Supplied -Name 'AdmissionReceipt' -Value $AdmissionReceipt
        Assert-Supplied -Name 'Candidates' -Value $Candidates
        $arguments = @(
            '--packet', $Packet,
            '--admission-receipt', $AdmissionReceipt,
            '--candidates', $Candidates,
            '--profile', $profilePath,
            '--repository-root', $repositoryRoot
        )
        if ($Out) { $arguments += @('--out', $Out) }
        Invoke-Surface -Module 'verify_stc_mary_successor_evidence_materialization.py' -Arguments $arguments
    }

    'record' {
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
            '--repository-root', $repositoryRoot
        )
        if ($Out) { $arguments += @('--out', $Out) }
        Invoke-Surface -Module 'stc_mary_successor_packet_orchestrator.py' -Arguments $arguments
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
            '--profile', $profilePath,
            '--repository-root', $repositoryRoot
        )
        if ($Out) { $arguments += @('--out', $Out) }
        Invoke-Surface -Module 'verify_stc_mary_successor_pre_seal_closure.py' -Arguments $arguments
    }

    'seal' {
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
        if ($Out) { $arguments += @('--out', $Out) }
        Invoke-Surface -Module 'stc_mary_successor_seal_adapter.py' -Arguments $arguments
    }

    'verify-detached' {
        Assert-Supplied -Name 'Sealed' -Value $Sealed
        $arguments = @(
            'verify-detached',
            '--sealed', $Sealed,
            '--repository-root', $repositoryRoot
        )
        if ($Out) { $arguments += @('--out', $Out) }
        Invoke-Surface -Module 'stc_mary_successor_seal_adapter.py' -Arguments $arguments
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
            '--profile', $profilePath,
            '--repository-root', $repositoryRoot
        )
        if ($Out) { $arguments += @('--out', $Out) }
        Invoke-Surface -Module 'verify_stc_mary_successor_post_seal_closure.py' -Arguments $arguments
    }

    'qualify' {
        # The full hostile witness denominator, including the one executable traversal
        # that begins at a configured predecessor at zero of sixteen.
        $conformance = Join-Path $anchor 'conformance'
        Push-Location $conformance
        try {
            & $Python -m unittest discover -s . -p 'test_stc_mary_successor_packet_flight_01.py' -v
            if ($LASTEXITCODE -ne 0) {
                throw "the successor flight witness denominator refused with exit code $LASTEXITCODE"
            }
        }
        finally {
            Pop-Location
        }
    }
}
