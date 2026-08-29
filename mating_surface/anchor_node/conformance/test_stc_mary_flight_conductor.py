from __future__ import annotations

import argparse
import copy
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ANCHOR = Path(__file__).resolve().parents[1]
if str(ANCHOR) not in sys.path:
    sys.path.insert(0, str(ANCHOR))

import stc_mary_flight_conductor as conductor
from stc_mary_local.common import hash_artifact


class StcMaryFlightConductorWitnesses(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.repository = self.root / "execution-repository"
        self.repository.mkdir()
        self.private_parent = self.root / "private-evidence"
        self.private_parent.mkdir()
        self.artifact_parent = self.root / "declared-artifacts"
        self.artifact_parent.mkdir()
        self.artifacts: dict[str, Path] = {}
        for label in conductor.ARTIFACT_LABELS:
            path = self.artifact_parent / f"{label}.bin"
            path.write_bytes(f"{label}-identity\n".encode("utf-8"))
            self.artifacts[label] = path

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def assert_code(self, code: str, callable_object, *args, **kwargs) -> conductor.ConductorError:
        with self.assertRaises(conductor.ConductorError) as caught:
            callable_object(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def source_receipt(self, **overrides) -> dict:
        body = {
            "schema": "stc-mary-flight-conductor-source-receipt/1",
            "repositoryRoot": str(self.repository),
            "head": conductor.REQUIRED_COMMIT,
            "tree": conductor.REQUIRED_TREE,
            "clean": True,
            "detached": True,
            "statusSha256": conductor.sha256_bytes(b""),
            "authority": "none",
            "claimBoundary": "Exact test source receipt. It grants no authority.",
        }
        body.update(overrides)
        return {**body, "sourceReceiptId": conductor.content_id("stcmaryflightconductorsourcereceipt1", body)}

    def artifact_arguments(self) -> list[str]:
        return [f"{label}={self.artifacts[label]}" for label in conductor.ARTIFACT_LABELS]

    def init_arguments(self, *, campaign_label: str = "PRIVATE-STC-MARY-FLIGHT-01", out: Path | None = None, artifacts: list[str] | None = None, private_parent: Path | None = None) -> argparse.Namespace:
        return argparse.Namespace(
            repository=str(self.repository),
            private_parent=str(private_parent or self.private_parent),
            out=str(out or (self.private_parent / "stc-mary-flight-conductor-test-01")),
            campaign_label=campaign_label,
            cuda_device_index=0,
            artifact=artifacts if artifacts is not None else self.artifact_arguments(),
            profile=str(conductor.DEFAULT_PROFILE),
        )

    def initialize(self, **kwargs) -> Path:
        arguments = self.init_arguments(**kwargs)
        ledger = {"currentPhase": "admitted_checkout"}
        with (
            patch.object(conductor, "git_snapshot", return_value=self.source_receipt()),
            patch.object(conductor, "derive_status", return_value=ledger),
            patch.object(conductor, "write_public_projection", return_value={}),
        ):
            conductor.initialize_workstation(arguments)
        return Path(arguments.out).resolve()

    def load_initialized(self) -> conductor.Workstation:
        return conductor.load_workstation(self.initialize())

    @staticmethod
    def git(command: list[str], cwd: Path) -> None:
        completed = subprocess.run(["git", *command], cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if completed.returncode != 0:
            raise AssertionError(completed.stderr.decode("utf-8", errors="replace"))

    def initialize_git_repository(self) -> Path:
        repository = self.root / "git-probe"
        repository.mkdir()
        self.git(["init"], repository)
        self.git(["config", "user.email", "qualification@example.invalid"], repository)
        self.git(["config", "user.name", "Qualification Witness"], repository)
        (repository / "tracked.txt").write_text("tracked\n", encoding="utf-8", newline="\n")
        self.git(["add", "tracked.txt"], repository)
        self.git(["commit", "-m", "qualification fixture"], repository)
        return repository

    def closed_prior(self, through: str) -> dict[str, conductor.PhaseResult]:
        rows: dict[str, conductor.PhaseResult] = {}
        for phase in conductor.PHASE_SEQUENCE:
            rows[phase] = conductor.closed(phase, [])
            if phase == through:
                break
        return rows

    def build_all_ready_plan(self, ws: conductor.Workstation) -> tuple[dict, dict, dict[str, conductor.PhaseResult]]:
        ids = {
            "readinessId": conductor.content_id("readiness", {"campaign": ws.marker["campaignId"]}),
            "feedId": conductor.content_id("feed", {"campaign": ws.marker["campaignId"]}),
            "baselineResultId": conductor.content_id("baseline", {"campaign": ws.marker["campaignId"]}),
            "acceleratedResultId": conductor.content_id("accelerated", {"campaign": ws.marker["campaignId"]}),
            "continuityResultId": conductor.content_id("continuity", {"campaign": ws.marker["campaignId"]}),
            "twoCellVerificationId": conductor.content_id("twocell", {"campaign": ws.marker["campaignId"]}),
            "successorVerificationId": conductor.content_id("successor", {"campaign": ws.marker["campaignId"]}),
        }
        for key, identifier in (
            ("baseline", ids["baselineResultId"]),
            ("accelerated", ids["acceleratedResultId"]),
            ("continuity", ids["continuityResultId"]),
        ):
            ws.path(key).parent.mkdir(parents=True, exist_ok=True)
            conductor.write_json(ws.path(key), {"resultId": identifier})
        ws.path("twoCellVerification").parent.mkdir(parents=True, exist_ok=True)
        conductor.write_json(ws.path("twoCellVerification"), {"verificationId": ids["twoCellVerificationId"]})
        conductor.write_json(ws.path("successorVerification"), {"verificationId": ids["successorVerificationId"]})
        gates = []
        for name in ("admitted_checkout", "personal_floor", "halo3", "post_halo3_continuity", "lattice_absence", "two_cell_partition", "successor_head", "private_evidence_root"):
            gate_body = {"name": name, "status": "READY", "evidence": [], "wakeCondition": None}
            gates.append({**gate_body, "gateId": conductor.content_id("stcmarylocalflightgate1", gate_body)})
        plan_body = {
            "schema": "stc-mary-local-flight-plan/1",
            "profileId": conductor.TOOLCHAIN_PROFILE_ID,
            "campaignLabel": ws.config["campaignLabel"],
            "requiredCommit": conductor.REQUIRED_COMMIT,
            **ids,
            "gates": gates,
            "stagePlan": [{"sequence": index + 1} for index in range(16)],
            "readyGateCount": 8,
            "holdGateCount": 0,
            "refuseGateCount": 0,
            "flightExecuted": False,
            "physicalEstateQualified": False,
            "representativeOperatorQualified": False,
            "fieldNetworkQualified": False,
            "operationalC2Qualified": False,
            "productionLatticeQualified": False,
            "externalServiceCalls": 0,
            "operationalCredentials": 0,
            "authority": "none",
            "claimBoundary": "All-ready qualification fixture. It claims no execution or authority.",
        }
        plan = {**plan_body, "planId": conductor.content_id("stcmarylocalflightplan1", plan_body)}
        flight_config = {
            "schema": "stc-mary-private-flight-packet-config/1",
            "campaignLabel": ws.config["campaignLabel"],
            "sourceObjectDigests": ["1" * 64, "2" * 64],
            "identityClasses": {
                "personalFloor": "private_resident_cpu_execution_seat",
                "halo3": "private_optional_24gib_cuda_accelerator",
                "initialHead": "private_initial_windows_head",
                "successorHead": "private_verified_successor_head",
                "graceBind": "named_human_operator_grace",
                "lattice": "private_optional_interoperability_membrane",
                "leftCell": "private_verified_left_cell",
                "rightCell": "private_verified_right_cell",
            },
            "canonicalMissionStateDigest": "3" * 64,
            "authority": "none",
            "claimBoundary": "Packet configuration fixture. It grants no authority.",
        }
        ws.path("flightPlan").parent.mkdir(parents=True, exist_ok=True)
        conductor.write_json(ws.path("flightPlan"), plan)
        conductor.write_json(ws.path("flightConfig"), flight_config)
        prior = self.closed_prior("successor_head")
        prior["readiness"] = conductor.closed("readiness", [ids["readinessId"]], {"readinessId": ids["readinessId"]})
        prior["feed"] = conductor.closed("feed", [ids["feedId"]], {"feedId": ids["feedId"]})
        return plan, flight_config, prior

    def all_closed_ledger(self, ws: conductor.Workstation) -> dict:
        evaluators = {
            phase: (lambda _ws, _prior, _validators, phase=phase: conductor.closed(phase, [conductor.content_id("witness", {"phase": phase})]))
            for phase in conductor.PHASE_SEQUENCE
        }
        with (
            patch.dict(conductor.PHASE_EVALUATORS, evaluators, clear=True),
            patch.object(conductor, "import_admitted_validators", return_value={"available": lambda *_: None}),
        ):
            return conductor.derive_status(ws.root, persist=False)


    def powershell_executable(self) -> str:
        candidate = shutil.which("pwsh") or shutil.which("powershell")
        if candidate is None:
            if os.name == "nt":
                self.fail("Windows qualification requires a PowerShell executable")
            self.skipTest("PowerShell is unavailable on this runner")
        return candidate

    def operator_fixture(self, *, phase: str = "readiness", fail_command: str | None = None) -> tuple[Path, dict[str, str], Path]:
        stub_anchor = self.root / "operator-conductor"
        stub_anchor.mkdir(exist_ok=True)
        conductor_stub = stub_anchor / "stc-mary-flight-conductor.ps1"
        conductor_stub.write_text(
            """[CmdletBinding(PositionalBinding = $false)]
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
$ErrorActionPreference = 'Stop'
if ($env:STC_MARY_STUB_LOG) {
    Add-Content -LiteralPath $env:STC_MARY_STUB_LOG -Value ('conductor:' + ($Arguments -join ' '))
}
if ($env:STC_MARY_STUB_CONDUCTOR_FAIL) { exit 19 }
@{
    currentPhase = $env:STC_MARY_STUB_PHASE
    refusedPhaseCount = 0
    authority = 'none'
} | ConvertTo-Json -Compress
exit 0
""",
            encoding="utf-8",
            newline="\n",
        )

        tool_anchor = self.repository / "mating_surface" / "anchor_node"
        tool_anchor.mkdir(parents=True, exist_ok=True)
        generic_stub = """[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)][string]$Command,
    [Parameter(Position = 1, ValueFromRemainingArguments = $true)][string[]]$RemainingArguments
)
$ErrorActionPreference = 'Stop'
Add-Content -LiteralPath $env:STC_MARY_STUB_LOG -Value ($env:STC_MARY_STUB_KIND + ':' + $Command)
if ($env:STC_MARY_STUB_FAIL_COMMAND -eq $Command) { exit 23 }
exit 0
"""
        for name, kind in (
            ("stc-mary-local-toolchain.ps1", "tool"),
            ("stc-mary-offline-carrier.ps1", "carrier"),
            ("stc-mary-private-flight.ps1", "packet"),
        ):
            path = tool_anchor / name
            path.write_text(generic_stub.replace("$env:STC_MARY_STUB_KIND", f"'{kind}'"), encoding="utf-8", newline="\n")

        if os.name == "nt":
            python_proxy = self.root / "python-proxy.cmd"
            python_proxy.write_text(
                "@echo off\r\n"
                "if \"%~1\"==\"-c\" (\r\n"
                "  echo {\"cudaAvailable\":true,\"deviceCount\":1,\"devices\":[0],\"version\":[3,12]}\r\n"
                "  exit /b 0\r\n"
                ")\r\n"
                f"\"{sys.executable}\" %*\r\n"
                "exit /b %ERRORLEVEL%\r\n",
                encoding="utf-8",
                newline="",
            )
        else:
            python_proxy = self.root / "python-proxy.sh"
            python_proxy.write_text(
                "#!/usr/bin/env sh\n"
                "if [ \"$1\" = \"-c\" ]; then\n"
                "  printf '%s\\n' '{\"cudaAvailable\":true,\"deviceCount\":1,\"devices\":[0],\"version\":[3,12]}'\n"
                "  exit 0\n"
                "fi\n"
                f"exec {shlex.quote(sys.executable)} \"$@\"\n",
                encoding="utf-8",
                newline="\n",
            )
            python_proxy.chmod(0o755)

        arguments = self.init_arguments(out=self.private_parent / f"stc-mary-flight-conductor-operator-{phase.replace('_', '-')}")
        ledger = {"currentPhase": "admitted_checkout"}
        with (
            patch.object(conductor, "HERE", stub_anchor),
            patch.object(conductor, "git_snapshot", return_value=self.source_receipt()),
            patch.object(conductor, "derive_status", return_value=ledger),
            patch.object(conductor, "write_public_projection", return_value={}),
        ):
            conductor.initialize_workstation(arguments)

        log = self.root / f"operator-{phase}.log"
        env = os.environ.copy()
        env.update(
            {
                "STC_MARY_STUB_LOG": str(log),
                "STC_MARY_STUB_PHASE": phase,
                "STC_MARY_PYTHON": str(python_proxy),
            }
        )
        if fail_command is not None:
            env["STC_MARY_STUB_FAIL_COMMAND"] = fail_command
        return Path(arguments.out).resolve(), env, log

    def run_operator(self, script: Path, arguments: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[bytes]:
        shell = self.powershell_executable()
        command = [shell, "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(script), *arguments]
        return subprocess.run(
            command,
            cwd=self.root,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_01_frozen_profile_validates(self) -> None:
        profile = conductor.load_profile()
        self.assertEqual(profile["profileId"], conductor.PROFILE_ID)
        self.assertEqual(profile["phaseSequence"], list(conductor.PHASE_SEQUENCE))

    def test_02_profile_byte_mutation_is_refused(self) -> None:
        mutated = self.root / "mutated-profile.json"
        mutated.write_bytes(conductor.DEFAULT_PROFILE.read_bytes() + b"\n")
        self.assert_code("CONDUCTOR_PROFILE_FROZEN_BYTES_MISMATCH", conductor.load_profile, mutated)

    def test_03_profile_phase_order_mutation_is_refused(self) -> None:
        profile = json.loads(conductor.DEFAULT_PROFILE.read_text(encoding="utf-8"))
        profile["phaseSequence"] = list(reversed(profile["phaseSequence"]))
        self.assert_code("CONDUCTOR_PROFILE_INVALID", conductor.validate_profile_structure, profile)

    def test_04_content_identity_is_canonical_and_deterministic(self) -> None:
        left = conductor.content_id("fixture", {"alpha": 1, "beta": 2})
        right = conductor.content_id("fixture", {"beta": 2, "alpha": 1})
        self.assertEqual(left, right)
        self.assertRegex(left, conductor.CONTENT_ID_RE)

    def test_05_source_set_has_exact_six_member_denominator(self) -> None:
        receipt = conductor.source_set_receipt()
        conductor.validate_source_set(receipt)
        self.assertEqual(receipt["memberCount"], 6)
        self.assertEqual([row["relativePath"] for row in receipt["members"]], list(conductor.SOURCE_MEMBERS))

    def test_06_git_snapshot_detects_moving_branch(self) -> None:
        repository = self.initialize_git_repository()
        snapshot = conductor.git_snapshot(repository)
        self.assertFalse(snapshot["detached"])
        self.assertTrue(snapshot["clean"])

    def test_07_git_snapshot_detects_dirty_untracked_state(self) -> None:
        repository = self.initialize_git_repository()
        (repository / "untracked.txt").write_text("untracked\n", encoding="utf-8", newline="\n")
        snapshot = conductor.git_snapshot(repository)
        self.assertFalse(snapshot["clean"])
        self.assertNotEqual(snapshot["statusSha256"], conductor.sha256_bytes(b""))

    def test_08_wrong_source_commit_is_refused(self) -> None:
        receipt = self.source_receipt(head="0" * 40)
        self.assert_code("SOURCE_COMMIT_INVALID", conductor.validate_source_snapshot, receipt, self.repository)

    def test_09_placeholder_campaign_label_is_refused(self) -> None:
        arguments = self.init_arguments(campaign_label="REPLACE_WITH_CAMPAIGN")
        with patch.object(conductor, "git_snapshot", return_value=self.source_receipt()):
            self.assert_code("CAMPAIGN_LABEL_INVALID", conductor.initialize_workstation, arguments)

    def test_10_duplicate_artifact_label_is_refused(self) -> None:
        artifacts = self.artifact_arguments()
        artifacts[-1] = f"cartridge={self.artifacts['storage']}"
        arguments = self.init_arguments(artifacts=artifacts)
        with patch.object(conductor, "git_snapshot", return_value=self.source_receipt()):
            self.assert_code("ARTIFACT_LABEL_DUPLICATE", conductor.initialize_workstation, arguments)

    def test_11_missing_artifact_label_is_refused(self) -> None:
        arguments = self.init_arguments(artifacts=self.artifact_arguments()[:-1])
        with patch.object(conductor, "git_snapshot", return_value=self.source_receipt()):
            self.assert_code("ARTIFACT_DENOMINATOR_INVALID", conductor.initialize_workstation, arguments)

    def test_12_unknown_artifact_label_is_refused(self) -> None:
        artifacts = self.artifact_arguments()
        artifacts[-1] = f"unknown={self.artifacts['storage']}"
        arguments = self.init_arguments(artifacts=artifacts)
        with patch.object(conductor, "git_snapshot", return_value=self.source_receipt()):
            self.assert_code("ARTIFACT_LABEL_UNKNOWN", conductor.initialize_workstation, arguments)

    def test_13_repository_private_parent_overlap_is_refused(self) -> None:
        private_parent = self.repository / "private"
        private_parent.mkdir()
        arguments = self.init_arguments(private_parent=private_parent, out=private_parent / "stc-mary-flight-conductor-test-01")
        with patch.object(conductor, "git_snapshot", return_value=self.source_receipt()):
            self.assert_code("PRIVATE_PARENT_REPOSITORY_OVERLAP", conductor.initialize_workstation, arguments)

    def test_14_existing_workstation_root_is_refused(self) -> None:
        output = self.private_parent / "stc-mary-flight-conductor-existing-01"
        output.mkdir()
        arguments = self.init_arguments(out=output)
        with patch.object(conductor, "git_snapshot", return_value=self.source_receipt()):
            self.assert_code("WORKSTATION_EXISTS", conductor.initialize_workstation, arguments)

    def test_15_overlapping_artifact_coordinates_are_refused(self) -> None:
        artifacts = self.artifact_arguments()
        artifacts[1] = f"model={self.artifacts['cartridge']}"
        arguments = self.init_arguments(artifacts=artifacts)
        with patch.object(conductor, "git_snapshot", return_value=self.source_receipt()):
            self.assert_code("ARTIFACT_COORDINATE_OVERLAP", conductor.initialize_workstation, arguments)

    def test_16_doctor_shaped_readiness_closes_and_file_presence_alone_does_not(self) -> None:
        ws = self.load_initialized()
        ws.path("readiness").parent.mkdir(parents=True, exist_ok=True)
        artifacts = [
            hash_artifact(row["label"], Path(row["privatePath"]))
            for row in ws.config["artifacts"]
        ]
        body = {
            "schema": "stc-mary-local-readiness-private/1",
            "profileId": conductor.TOOLCHAIN_PROFILE_ID,
            "capturedAtUnixNs": ws.config["createdAtUnixNs"] + 1,
            "host": {},
            "repository": {
                "head": conductor.REQUIRED_COMMIT,
                "branch": None,
                "root": ws.config["executionSource"]["repositoryPath"],
                "clean": True,
                "statusSha256": conductor.sha256_bytes(b""),
                "commandReceipts": {},
                "privateStatus": {},
            },
            "commands": {},
            "pythonModules": {},
            "torch": {
                "cudaAvailable": True,
                "devices": [{"index": ws.config["selectedCudaDeviceIndex"]}],
            },
            "nvidiaQuery": {},
            "nvidiaGpus": [],
            "windows": {},
            "artifacts": artifacts,
            "externalServiceCalls": 0,
            "operationalCredentials": 0,
            "authority": "none",
            "claimBoundary": "Doctor-shaped readiness fixture. It grants no authority.",
        }
        receipt = {
            **body,
            "readinessId": conductor.content_id("stcmarylocalreadiness1", body),
        }
        conductor.write_json(ws.path("readiness"), receipt)
        prior = {
            "admitted_checkout": conductor.closed("admitted_checkout", []),
            "artifact_coordinates": conductor.closed("artifact_coordinates", []),
        }
        result = conductor.phase_readiness(ws, prior, {})
        self.assertEqual(result.state, "CLOSED")
        self.assertEqual(result.evidence, [receipt["readinessId"]])

        conductor.write_json(
            ws.path("readiness"),
            {"schema": "present-but-not-a-receipt"},
            replace=True,
        )
        result = conductor.phase_readiness(ws, prior, {})
        self.assertEqual(result.state, "REFUSED")
        self.assertEqual(result.reason_code, "READINESS_RECEIPT_INVALID")

    def test_17_altered_workstation_marker_is_refused(self) -> None:
        root = self.initialize()
        marker_path = root / conductor.MARKER_FILE
        marker = conductor.read_json(marker_path)
        marker["campaignLabel"] = "PRIVATE-STC-MARY-FLIGHT-ALTERED"
        conductor.write_json(marker_path, marker, replace=True)
        self.assert_code("WORKSTATION_MARKER_ID_INVALID", conductor.load_workstation, root)

    def test_18_readiness_from_another_commit_is_refused(self) -> None:
        ws = self.load_initialized()
        body = {
            "schema": "stc-mary-local-readiness-private/1",
            "profileId": conductor.TOOLCHAIN_PROFILE_ID,
            "capturedAtUnixNs": ws.config["createdAtUnixNs"] + 1,
            "host": {},
            "repository": {
                "head": "0" * 40,
                "branch": None,
                "root": ws.config["executionSource"]["repositoryPath"],
                "clean": True,
                "statusSha256": conductor.sha256_bytes(b""),
                "commandReceipts": {},
                "privateStatus": {},
            },
            "commands": {},
            "pythonModules": {},
            "torch": {},
            "nvidiaQuery": {},
            "nvidiaGpus": [],
            "windows": {},
            "artifacts": [],
            "externalServiceCalls": 0,
            "operationalCredentials": 0,
            "authority": "none",
            "claimBoundary": "Wrong-source readiness fixture.",
        }
        receipt = {**body, "readinessId": conductor.content_id("stcmarylocalreadiness1", body)}
        self.assert_code("READINESS_SOURCE_MISMATCH", conductor.validate_readiness_receipt, receipt, ws)

    def test_19_synthetic_two_cell_receipt_remains_held(self) -> None:
        ws = self.load_initialized()
        ws.path("twoCellVerification").parent.mkdir(parents=True, exist_ok=True)
        body = {"mode": "synthetic_simulation"}
        value = {**body, "verificationId": conductor.content_id("synthetictwocell", body)}
        conductor.write_json(ws.path("twoCellVerification"), value)
        prior = {"post_halo3_continuity": conductor.closed("post_halo3_continuity", [])}
        result = conductor.phase_two_cell(ws, prior, {"two_cell": lambda _value: _value})
        self.assertEqual(result.state, "HOLD")
        self.assertEqual(result.reason_code, "TWO_CELL_SYNTHETIC_HELD")

    def test_20_held_plan_blocks_packet_handoff(self) -> None:
        ws = self.load_initialized()
        self.assert_code("PACKET_HANDOFF_HELD", conductor.packet_handoff_record, ws, {"packetHandoffReady": False})

    def test_21_all_ready_plan_closes_and_enables_handoff(self) -> None:
        ws = self.load_initialized()
        plan, _config, prior = self.build_all_ready_plan(ws)
        result = conductor.phase_flight_plan(ws, prior, {})
        self.assertEqual(result.state, "CLOSED")
        handoff = conductor.packet_handoff_record(ws, {"packetHandoffReady": True})
        self.assertEqual(handoff["planId"], plan["planId"])
        self.assertEqual(handoff["authority"], "none")

    def test_22_every_phase_has_one_wake_condition_and_control_question(self) -> None:
        ws = self.load_initialized()
        for phase in conductor.PHASE_SEQUENCE:
            result = conductor.held(phase, code="TEST_HOLD", reason="qualification fixture")
            _action, wake, control = conductor.next_action_for(ws, result)
            self.assertEqual(wake, ws.profile["phases"][phase]["wakeCondition"])
            self.assertEqual(control, ws.profile["phases"][phase]["controlQuestion"])
            self.assertTrue(wake.strip())
            self.assertTrue(control.strip())

    def test_23_restart_reconstruction_preserves_campaign_and_ledger_identity(self) -> None:
        ws = self.load_initialized()
        first = self.all_closed_ledger(ws)
        reloaded = conductor.load_workstation(ws.root)
        second = self.all_closed_ledger(reloaded)
        self.assertEqual(first["campaignId"], second["campaignId"])
        self.assertEqual(first["ledgerId"], second["ledgerId"])
        self.assertEqual(first["phaseDenominator"], second["phaseDenominator"])

    def test_24_public_projection_contains_no_private_path_host_or_body(self) -> None:
        ws = self.load_initialized()
        ledger = self.all_closed_ledger(ws)
        projection = conductor.public_projection(ws, ledger)
        serialized = conductor.canonical_json(projection)
        for secret in (str(ws.root), ws.config["privateParent"], ws.config["executionSource"]["repositoryPath"], *[row["privatePath"] for row in ws.config["artifacts"]]):
            self.assertNotIn(secret, serialized)
        self.assertNotIn("evidenceBody", serialized)
        self.assertNotIn("hostname", serialized)

    def test_25_ledgers_and_public_projection_never_widen_qualification_or_authority(self) -> None:
        ws = self.load_initialized()
        ledger = self.all_closed_ledger(ws)
        projection = conductor.public_projection(ws, ledger)
        for value in (ledger, projection):
            self.assertEqual(value["authority"], "none")
            self.assertEqual(value["missionAuthority"], "none")
            self.assertEqual(value["commandAuthority"], "none")
            for key in ("physicalEstateQualified", "representativeOperatorQualified", "fieldNetworkQualified", "operationalC2Qualified", "productionLatticeQualified", "targetingEngagementEffectorWeaponsCapability", "networkRequired"):
                self.assertFalse(value[key])
            self.assertEqual(value["externalServiceCalls"], 0)
            self.assertEqual(value["operationalCredentials"], 0)
            self.assertEqual(value["privateEvidenceBodiesCommittedToPublicGit"], 0)


    def test_26_operator_action_vocabulary_is_closed_and_preflight_aligned(self) -> None:
        self.assertEqual(
            conductor.OPERATOR_ACTIONS,
            (
                "readiness",
                "feed",
                "personal-floor",
                "halo3",
                "post-halo3-continuity",
                "two-cell",
                "successor-head",
                "compile-plan",
                "seal",
            ),
        )
        self.assertEqual(set(conductor.OPERATOR_ACTION_PHASES), set(conductor.OPERATOR_ACTIONS))
        self.assertEqual(conductor.OPERATOR_ACTION_PHASES["seal"], "sealed_flight")

    def test_27_missing_unknown_and_additional_actions_refuse_before_tool_invocation(self) -> None:
        for index, arguments in enumerate(([], ["unknown-action"], ["readiness", "extra"]), start=1):
            with self.subTest(arguments=arguments):
                root, env, log = self.operator_fixture(phase=f"readiness_{index}")
                result = self.run_operator(root / conductor.OPERATOR_SCRIPT_FILE, arguments, env)
                self.assertNotEqual(result.returncode, 0)
                if log.exists():
                    lines = log.read_text(encoding="utf-8").splitlines()
                    self.assertFalse(any(line.startswith(("tool:", "carrier:", "packet:")) for line in lines))

    def test_28_readiness_action_invokes_only_doctor(self) -> None:
        root, env, log = self.operator_fixture(phase="readiness")
        result = self.run_operator(root / conductor.OPERATOR_SCRIPT_FILE, ["readiness"], env)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))
        lines = log.read_text(encoding="utf-8").splitlines()
        self.assertEqual([line for line in lines if line.startswith(("tool:", "carrier:", "packet:"))], ["tool:doctor"])
        ws_paths = conductor.read_json(root / conductor.PATH_MAP_FILE)["paths"]
        for key in (
            "feed",
            "baseline",
            "baselineVerification",
            "accelerated",
            "acceleratedVerification",
            "continuity",
            "continuityVerification",
            "comparison",
            "cellPair",
            "reunion",
            "successor",
            "plan",
            "packet",
            "sealed",
        ):
            self.assertFalse(Path(ws_paths[key]).exists(), key)

    def test_29_tool_refusal_stops_without_crossing_action_boundary(self) -> None:
        root, env, log = self.operator_fixture(phase="readiness", fail_command="doctor")
        result = self.run_operator(root / conductor.OPERATOR_SCRIPT_FILE, ["readiness"], env)
        self.assertNotEqual(result.returncode, 0)
        lines = log.read_text(encoding="utf-8").splitlines()
        self.assertEqual([line for line in lines if line.startswith(("tool:", "carrier:", "packet:"))], ["tool:doctor"])

    def test_30_wrong_phase_refuses_before_execution_floor_tool_invocation(self) -> None:
        root, env, log = self.operator_fixture(phase="readiness")
        result = self.run_operator(root / conductor.OPERATOR_SCRIPT_FILE, ["feed"], env)
        self.assertNotEqual(result.returncode, 0)
        lines = log.read_text(encoding="utf-8").splitlines()
        self.assertFalse(any(line.startswith(("tool:", "carrier:", "packet:")) for line in lines))

    def test_31_two_cell_action_advances_only_one_local_subtransaction(self) -> None:
        root, env, log = self.operator_fixture(phase="two_cell_partition")
        result = self.run_operator(root / conductor.OPERATOR_SCRIPT_FILE, ["two-cell"], env)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))
        lines = log.read_text(encoding="utf-8").splitlines()
        self.assertEqual([line for line in lines if line.startswith(("tool:", "carrier:", "packet:"))], ["carrier:template-inputs"])

    def test_32_successor_action_builds_only_and_never_attests_replacement_host(self) -> None:
        root, env, log = self.operator_fixture(phase="successor_head")
        paths = conductor.read_json(root / conductor.PATH_MAP_FILE)["paths"]
        inputs = Path(paths["offlineInputs"])
        inputs.mkdir(parents=True)
        for name in ("common-state.json", "authority.json", "obligations.json", "evidence-envelope.json", "next-safe-action.txt"):
            (inputs / name).write_text("{}\n" if name.endswith(".json") else "continue\n", encoding="utf-8", newline="\n")
        result = self.run_operator(root / conductor.OPERATOR_SCRIPT_FILE, ["successor-head"], env)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))
        lines = log.read_text(encoding="utf-8").splitlines()
        tool_lines = [line for line in lines if line.startswith(("tool:", "carrier:", "packet:"))]
        self.assertEqual(tool_lines, ["carrier:build-successor"])
        self.assertFalse(any("verify-successor" in line for line in lines))



if __name__ == "__main__":
    unittest.main()
