from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import stc_mary_local as mod
from stc_mary_local.halo3_seat import halo3_seat_record
PROFILE_PATH = HERE.parent / "stc-mary-local-toolchain-profile-01.json"


class LocalToolchainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="stc-mary-local-toolchain-")
        self.root = Path(self.temp.name)
        self.halo3_seat = halo3_seat_record(
            product_name="NVIDIA GeForce RTX 3090",
            gpu_uuid="GPU-0b31e56a-34eb-e8ef-e888-a6d6f044097b",
            pci_bus_id="00000000:25:00.0",
            pnp_instance_id=r"PCI\VEN_10DE&DEV_2204&SUBSYS_38801028\FIXTURE",
            transport_class="thunderbolt_egpu",
            transport_anchor_pnp_instance_id=r"PCI\VEN_8086&DEV_15DA&SUBSYS_00011A58\FIXTURE",
            initial_cuda_device_index=1,
        )
        self.halo3_observation = {
            "schema": "stc-mary-halo3-seat-observation/1",
            "seatId": self.halo3_seat["seatId"],
            "role": "HALO3",
            "currentCudaDeviceIndex": 1,
            "gpuUuid": self.halo3_seat["gpuUuid"],
            "pciBusId": self.halo3_seat["pciBusId"],
            "pnpInstanceId": self.halo3_seat["pnpInstanceId"],
            "transportClass": self.halo3_seat["transportClass"],
            "transportAnchorObserved": True,
            "authority": "none",
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def feed(self, name: str = "stc-mary-local-feed-a", records: int = 512) -> Path:
        path = self.root / name
        result = mod.generate_feed(argparse.Namespace(
            out=str(path), records=records, features=16, classes=4, seed=12345,
        ))
        self.assertEqual(result["status"], "PASS")
        return path

    def workload(self, feed: Path, name: str, backend: str = "python") -> dict:
        path = self.root / name
        mod.run_workload(argparse.Namespace(feed=str(feed), backend=backend, device_index=0, out=str(path)))
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def rewrite_result(result: dict, **changes) -> dict:
        body = dict(result)
        body.pop("resultId")
        body.update(changes)
        return {**body, "resultId": mod.content_id("stcmaryapertureworkloadresult1", body)}

    def synthetic_readiness(self, required_commit: str, *, lattice_absent: bool = True) -> dict:
        windows = {
            "applicable": True,
            "raw": {},
            "parsed": {
                "latticeProcesses": [] if lattice_absent else [{"ProcessName": "lattice"}],
                "latticeServices": [],
                "listeners": [],
            },
        }
        body = {
            "schema": "stc-mary-local-readiness-private/1",
            "profileId": mod.TOOLCHAIN_PROFILE_ID,
            "capturedAtUnixNs": 1,
            "host": {},
            "repository": {
                "head": required_commit,
                "branch": "main",
                "root": "private",
                "clean": True,
                "statusSha256": "0" * 64,
                "commandReceipts": {},
                "privateStatus": {},
            },
            "commands": {},
            "pythonModules": {
                "numpy": {"available": False, "version": None},
                "torch": {"available": True, "version": "fixture"},
                "onnxruntime": {"available": False, "version": None},
            },
            "torch": {"available": True, "version": "fixture", "cudaAvailable": True, "deviceCount": 1, "devices": []},
            "nvidiaQuery": {},
            "nvidiaGpus": [{"memory.total": 24576}],
            "windows": windows,
            "artifacts": [{
                "schema": "stc-mary-local-artifact-manifest/1",
                "label": "cartridge",
            "halo3Seat": self.halo3_seat,
            "halo3SeatObservation": self.halo3_observation,
                "kind": "file",
                "files": [{"relativePath": "cartridge.bin", "sha256": "1" * 64, "bytes": 1}],
                "fileCount": 1,
                "totalBytes": 1,
                "authority": "none",
                "claimBoundary": "private",
                "artifactId": "stcmarylocalartifact1_" + "2" * 64,
                "privatePath": "private",
            }],
            "externalServiceCalls": 0,
            "operationalCredentials": 0,
            "authority": "none",
            "claimBoundary": "private readiness",
        }
        return {**body, "readinessId": mod.content_id("stcmarylocalreadiness1", body)}

    def test_profile_is_closed_and_valid(self):
        profile = mod.validate_profile(PROFILE_PATH)
        self.assertEqual(profile["profileId"], mod.TOOLCHAIN_PROFILE_ID)
        self.assertEqual(profile["predecessorCommit"], mod.ADMITTED_PACKET_COMMIT)

    def test_feed_generation_is_byte_deterministic(self):
        first = self.feed("stc-mary-local-feed-first")
        second = self.feed("stc-mary-local-feed-second")
        self.assertEqual((first / "features.bin").read_bytes(), (second / "features.bin").read_bytes())
        self.assertEqual((first / "feed-manifest.json").read_bytes(), (second / "feed-manifest.json").read_bytes())

    def test_python_workload_and_independent_verifier_close(self):
        feed = self.feed()
        result_path = self.root / "result.json"
        verification_path = self.root / "verification.json"
        result = mod.run_workload(argparse.Namespace(feed=str(feed), backend="python", device_index=0, out=str(result_path)))
        verification = mod.verify_workload(argparse.Namespace(feed=str(feed), result=str(result_path), out=str(verification_path)))
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(verification["status"], "PASS")
        self.assertEqual(json.loads(verification_path.read_text())["semanticOutputVerified"], True)

    def test_workload_repeats_same_semantic_output(self):
        feed = self.feed()
        first = self.workload(feed, "first.json")
        second = self.workload(feed, "second.json")
        self.assertEqual(first["semanticOutputSha256"], second["semanticOutputSha256"])
        self.assertEqual(first["classificationStreamSha256"], second["classificationStreamSha256"])
        self.assertNotEqual(first["resultId"], second["resultId"])

    def test_tampered_feed_is_refused_before_execution(self):
        feed = self.feed()
        path = feed / "features.bin"
        data = bytearray(path.read_bytes())
        data[-1] ^= 1
        path.write_bytes(data)
        with self.assertRaisesRegex(mod.ToolchainError, "feature file digest or size differs"):
            mod.run_workload(argparse.Namespace(feed=str(feed), backend="python", device_index=0, out=str(self.root / "bad.json")))

    def test_tampered_result_is_refused_by_verifier(self):
        feed = self.feed()
        result_path = self.root / "result.json"
        mod.run_workload(argparse.Namespace(feed=str(feed), backend="python", device_index=0, out=str(result_path)))
        result = json.loads(result_path.read_text())
        result["semanticOutputSha256"] = "0" * 64
        result_path.write_text(json.dumps(result), encoding="utf-8")
        with self.assertRaises(mod.ToolchainError) as context:
            mod.verify_workload(argparse.Namespace(feed=str(feed), result=str(result_path), out=str(self.root / "verification.json")))
        self.assertIn(context.exception.code, {"WORKLOAD_RESULT_ID_INVALID", "WORKLOAD_SEMANTIC_MISMATCH"})

    def test_private_root_inside_repository_is_refused(self):
        repository = self.root / "repo"
        repository.mkdir()
        with self.assertRaises(mod.ToolchainError) as context:
            mod.validate_new_private_root(repository / "stc-mary-local-prep-x", repository_root=repository)
        self.assertEqual(context.exception.code, "PRIVATE_ROOT_IN_REPOSITORY")

    def test_public_projection_drops_private_path_and_host(self):
        required = "a" * 40
        readiness = self.synthetic_readiness(required)
        readiness["host"] = {"node": "SECRET-HOST", "user": "SECRET-USER"}
        readiness["commands"] = {"gitVersion": mod.CommandResult(["git"], True, 0, "git version", "", 0.1, False).private_record()}
        projection = mod.public_readiness_projection(readiness)
        encoded = mod.canonical_json(projection)
        self.assertNotIn("SECRET-HOST", encoded)
        self.assertNotIn("SECRET-USER", encoded)
        self.assertNotIn("privatePath", encoded)
        self.assertEqual(projection["publicPrivatePaths"], 0)

    def test_torch_cuda_workload_resolves_exact_seat_in_torch_index_space(self):
        feed = self.feed(records=16)
        config = self.root / "campaign.json"
        config.write_text(json.dumps({"halo3Seat": self.halo3_seat}), encoding="utf-8")
        torch_devices = [{
            "index": 0,
            "name": self.halo3_seat["productName"],
            "uuid": self.halo3_seat["gpuUuid"],
            "pciBusId": self.halo3_seat["pciBusId"],
        }]
        observation = {**self.halo3_observation, "currentCudaDeviceIndex": 0}

        workload_module = importlib.import_module("stc_mary_local.workload")
        classified = (bytes([0]) * 16, [16, 0, 0, 0], 1.0, "fixture", 0.5, "cuda_accelerator:0")
        with patch.object(workload_module, "torch_probe", return_value={
            "available": True, "cudaAvailable": True, "devices": torch_devices,
        }), patch.object(
            workload_module, "resolve_halo3_seat", return_value=observation,
        ) as resolve, patch.object(
            workload_module, "classify_torch", return_value=classified,
        ) as classify:
            result = workload_module.run_workload(argparse.Namespace(
                feed=str(feed), backend="torch-cuda", device_index=0,
                halo3_seat_config=str(config), out=str(self.root / "cuda.json"),
            ))

        resolve.assert_called_once_with(self.halo3_seat, torch_devices=torch_devices)
        self.assertEqual(classify.call_args.kwargs["device_index"], 0)
        committed = json.loads((self.root / "cuda.json").read_text(encoding="utf-8"))
        self.assertEqual(committed["observedCudaDeviceIndex"], 0)
        self.assertEqual(committed["halo3SeatId"], self.halo3_seat["seatId"])

    def test_comparison_requires_same_output_and_proves_acceleration(self):
        feed = self.feed()
        baseline = self.workload(feed, "baseline.json")
        accelerated = self.rewrite_result(
            baseline,
            backend="torch-cuda",
            backendVersion="fixture",
            deviceClass="cuda_accelerator",
            halo3SeatId=self.halo3_seat["seatId"],
            observedCudaDeviceIndex=1,
            elapsedSeconds=baseline["elapsedSeconds"] / 4,
            computeSeconds=baseline["computeSeconds"] / 4,
            throughputRecordsPerSecond=baseline["throughputRecordsPerSecond"] * 4,
        )
        continuity = self.rewrite_result(
            baseline,
            elapsedSeconds=baseline["elapsedSeconds"] * 1.1,
            computeSeconds=baseline["computeSeconds"] * 1.1,
            throughputRecordsPerSecond=baseline["throughputRecordsPerSecond"] / 1.1,
        )
        accelerated_path = self.root / "accelerated.json"
        continuity_path = self.root / "continuity.json"
        accelerated_path.write_text(json.dumps(accelerated), encoding="utf-8")
        continuity_path.write_text(json.dumps(continuity), encoding="utf-8")
        output = self.root / "comparison.json"
        receipt = mod.compare_workloads(argparse.Namespace(
            baseline=str(self.root / "baseline.json"),
            accelerated=str(accelerated_path),
            continuity=str(continuity_path),
            out=str(output),
        ))
        self.assertEqual(receipt["status"], "PASS")
        self.assertGreater(json.loads(output.read_text())["halo3AccelerationFactor"], 1)

    def test_compile_plan_admits_only_measured_ready_gates(self):
        required = "a" * 40
        readiness = self.synthetic_readiness(required, lattice_absent=True)
        readiness_path = self.root / "readiness.json"
        readiness_path.write_text(json.dumps(readiness), encoding="utf-8")
        feed = self.feed()
        baseline = self.workload(feed, "baseline.json")
        accelerated = self.rewrite_result(
            baseline,
            backend="torch-cuda",
            backendVersion="fixture",
            deviceClass="cuda_accelerator",
            halo3SeatId=self.halo3_seat["seatId"],
            observedCudaDeviceIndex=1,
            elapsedSeconds=baseline["elapsedSeconds"] / 3,
            computeSeconds=baseline["computeSeconds"] / 3,
            throughputRecordsPerSecond=baseline["throughputRecordsPerSecond"] * 3,
        )
        continuity = self.rewrite_result(
            baseline,
            elapsedSeconds=baseline["elapsedSeconds"] * 1.05,
            computeSeconds=baseline["computeSeconds"] * 1.05,
            throughputRecordsPerSecond=baseline["throughputRecordsPerSecond"] / 1.05,
        )
        (self.root / "accelerated.json").write_text(json.dumps(accelerated), encoding="utf-8")
        (self.root / "continuity.json").write_text(json.dumps(continuity), encoding="utf-8")
        repository = self.root / "repo"
        repository.mkdir()
        output = self.root / "stc-mary-local-plan-a"
        result = mod.compile_plan(argparse.Namespace(
            repository=str(repository), readiness=str(readiness_path), feed=str(feed), baseline=str(self.root / "baseline.json"),
            accelerated=str(self.root / "accelerated.json"), continuity=str(self.root / "continuity.json"),
            campaign_label="PRIVATE-STC-MARY-FLIGHT-TEST-01", required_commit=required, out=str(output),
        ))
        self.assertEqual(result["status"], "PASS")
        plan = json.loads((output / "local-flight-plan.json").read_text())
        gates = {row["name"]: row["status"] for row in plan["gates"]}
        self.assertEqual(gates["admitted_checkout"], "READY")
        self.assertEqual(gates["personal_floor"], "READY")
        self.assertEqual(gates["halo3"], "READY")
        self.assertEqual(gates["post_halo3_continuity"], "READY")
        self.assertEqual(gates["lattice_absence"], "READY")
        self.assertEqual(gates["two_cell_partition"], "HOLD")
        self.assertEqual(gates["successor_head"], "HOLD")
        config = json.loads((output / "flight-config.generated.json").read_text())
        self.assertTrue(config["identityClasses"]["successorHead"].startswith("REPLACE_WITH_"))
        self.assertTrue(config["identityClasses"]["leftCell"].startswith("REPLACE_WITH_"))

    def test_non_cuda_acceleration_does_not_admit_halo3(self):
        required = "b" * 40
        readiness = self.synthetic_readiness(required)
        readiness_path = self.root / "readiness.json"
        readiness_path.write_text(json.dumps(readiness), encoding="utf-8")
        feed = self.feed()
        baseline = self.workload(feed, "baseline.json")
        faster_cpu = self.rewrite_result(
            baseline,
            backend="numpy",
            backendVersion="fixture",
            deviceClass="resident_cpu",
            throughputRecordsPerSecond=baseline["throughputRecordsPerSecond"] * 10,
            elapsedSeconds=baseline["elapsedSeconds"] / 10,
            computeSeconds=baseline["computeSeconds"] / 10,
        )
        (self.root / "faster.json").write_text(json.dumps(faster_cpu), encoding="utf-8")
        repository = self.root / "repo"
        repository.mkdir()
        output = self.root / "stc-mary-local-plan-hold"
        mod.compile_plan(argparse.Namespace(
            repository=str(repository), readiness=str(readiness_path), feed=str(feed), baseline=str(self.root / "baseline.json"),
            accelerated=str(self.root / "faster.json"), continuity=None,
            campaign_label="PRIVATE-STC-MARY-FLIGHT-TEST-02", required_commit=required, out=str(output),
        ))
        plan = json.loads((output / "local-flight-plan.json").read_text())
        gates = {row["name"]: row["status"] for row in plan["gates"]}
        self.assertEqual(gates["halo3"], "HOLD")

    def test_directory_artifact_manifest_is_deterministic(self):
        tree = self.root / "artifact"
        tree.mkdir()
        (tree / "b.txt").write_text("b", encoding="utf-8")
        (tree / "a.txt").write_text("a", encoding="utf-8")
        first = mod.hash_artifact("tree", tree)
        second = mod.hash_artifact("tree", tree)
        self.assertEqual(first["artifactId"], second["artifactId"])
        self.assertEqual([row["relativePath"] for row in first["files"]], ["a.txt", "b.txt"])

    def test_doctor_writes_private_and_body_free_public_receipts(self):
        repository = self.root / "repo"
        repository.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repository, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repository, check=True)
        artifact = repository / "artifact.bin"
        artifact.write_bytes(b"artifact")
        subprocess.run(["git", "add", "artifact.bin"], cwd=repository, check=True)
        subprocess.run(["git", "commit", "-qm", "init"], cwd=repository, check=True)
        output = self.root / "stc-mary-local-prep-doctor"
        campaign_config = self.root / "campaign-config.json"
        campaign_config.write_text(json.dumps({"halo3Seat": self.halo3_seat}), encoding="utf-8")
        with patch("stc_mary_local.readiness.resolve_halo3_seat", return_value=self.halo3_observation):
            receipt = mod.doctor_command(argparse.Namespace(
                repository=str(repository), out=str(output), artifact=[f"artifact={artifact}"],
                halo3_seat_config=str(campaign_config),
            ))
        self.assertEqual(receipt["status"], "PASS")
        private = json.loads((output / "readiness-private.json").read_text())
        public = json.loads((output / "readiness-public-projection.json").read_text())
        self.assertIn("privatePath", json.dumps(private))
        self.assertNotIn(str(artifact), json.dumps(public))
        self.assertEqual(public["physicalEstateQualified"], False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
