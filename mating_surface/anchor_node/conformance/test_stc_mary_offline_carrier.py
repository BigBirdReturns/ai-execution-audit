from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ANCHOR = HERE.parent if HERE.name == "conformance" else HERE
sys.path.insert(0, str(ANCHOR))
import stc_mary_offline_carrier as mod

try:
    import stc_mary_local as local_mod
except ImportError:
    local_mod = None


PROFILE = {
    "schema": "stc-mary-offline-carrier-profile/1",
    "profileId": "stc-mary/offline-cell-successor-carrier/0.1",
    "status": "candidate_design_only",
    "predecessorCommit": "c7f95de862e47307e6f6a0f07fcd7aa456e9a88f",
    "commands": [
        "template-inputs",
        "build-cell-pair",
        "verify-cell",
        "reconcile-cells",
        "build-successor",
        "verify-successor",
        "validate-profile",
    ],
    "bundleTypes": ["cell", "successor"],
    "modes": ["synthetic_simulation", "private_local_attested"],
    "claimBoundary": "Provider-free offline two-cell and cold-successor carrier candidate.",
}


class OfflineCarrierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="stc-mary-offline-test-")
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        (self.repo / ".git").mkdir()
        self.private = self.root / "private"
        self.private.mkdir()

        self.profile = self.root / "profile.json"
        self.profile.write_text(json.dumps(PROFILE), encoding="utf-8")

        self.common = self.root / "common-state.json"
        self.common.write_text(json.dumps({"state": "common", "sequence": 7}), encoding="utf-8")
        self.left_delta = self.root / "left-delta.json"
        self.right_delta = self.root / "right-delta.json"
        mod.write_json(
            self.left_delta,
            mod.record_cell_delta("left", {"observation": "left"}, "1" * 64),
        )
        mod.write_json(
            self.right_delta,
            mod.record_cell_delta("right", {"observation": "right"}, "2" * 64),
        )
        self.authority = self.root / "authority.json"
        mod.write_json(self.authority, mod.create_authority_boundary())

        self.obligations = self.root / "obligations.json"
        mod.write_json(
            self.obligations,
            {
                "schema": "stc-mary-open-obligations/1",
                "obligations": [
                    mod.create_open_obligation(
                        "reconcile_partition",
                        "A named human must reconcile the retained divergent branches.",
                    )
                ],
                "authority": "none",
                "claimBoundary": "Private open obligations.",
            },
        )
        self.cartridge = self.root / "cartridge"
        self.cartridge.mkdir()
        (self.cartridge / "mission.json").write_text('{"mission":"fixture"}\n', encoding="utf-8")
        (self.cartridge / "verifier.bin").write_bytes(b"fixture-verifier")
        self.evidence = self.root / "evidence"
        self.evidence.mkdir()
        (self.evidence / "receipt.json").write_text('{"evidence":"fixture"}\n', encoding="utf-8")
        self.next_action = self.root / "next-safe-action.txt"
        self.next_action.write_text(
            "Present the verified bundle and open obligations to the named human operator.",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def pair(self, suffix: str = "a") -> Path:
        output = self.private / f"stc-mary-offline-pair-{suffix}"
        result = mod.build_cell_pair(
            common_state_path=self.common,
            left_delta_path=self.left_delta,
            right_delta_path=self.right_delta,
            authority_path=self.authority,
            campaign_label="PRIVATE-STC-MARY-FLIGHT-TEST",
            out=output,
            repository=self.repo,
        )
        self.assertEqual(result["status"], "PASS")
        return output

    def successor(self, suffix: str = "a") -> Path:
        output = self.private / f"stc-mary-successor-{suffix}"
        result = mod.build_successor_bundle(
            cartridge=self.cartridge,
            canonical_state=self.common,
            authority=self.authority,
            obligations=self.obligations,
            evidence=self.evidence,
            next_safe_action=self.next_action,
            out=output,
            repository=self.repo,
        )
        self.assertEqual(result["status"], "PASS")
        return output

    def test_profile_is_closed(self):
        profile = mod.load_profile(self.profile)
        self.assertEqual(profile["profileId"], mod.PROFILE_ID)
        self.assertEqual(profile["commands"], list(mod.COMMANDS))

    def test_profile_refuses_reordered_command_denominator(self):
        altered = copy.deepcopy(PROFILE)
        altered["commands"][0], altered["commands"][1] = altered["commands"][1], altered["commands"][0]
        path = self.root / "bad-profile.json"
        path.write_text(json.dumps(altered), encoding="utf-8")
        with self.assertRaises(mod.OfflineCarrierError) as context:
            mod.load_profile(path)
        self.assertEqual(context.exception.code, "PROFILE_COMMAND_DENOMINATOR_INVALID")

    def test_delta_identity_is_deterministic_and_side_bound(self):
        first = mod.record_cell_delta("left", {"x": 1}, "a" * 64)
        second = mod.record_cell_delta("left", {"x": 1}, "a" * 64)
        right = mod.record_cell_delta("right", {"x": 1}, "a" * 64)
        self.assertEqual(first, second)
        self.assertNotEqual(first["deltaId"], right["deltaId"])
        mod.validate_cell_delta(first, "left")
        with self.assertRaises(mod.OfflineCarrierError):
            mod.validate_cell_delta(first, "right")

    def test_cell_pair_refuses_same_observed_effect_on_both_sides(self):
        left = mod.record_cell_delta("left", {"observation": "same"}, "a" * 64)
        right = mod.record_cell_delta("right", {"observation": "same"}, "a" * 64)
        mod.write_json(self.left_delta, left)
        mod.write_json(self.right_delta, right)
        with self.assertRaises(mod.OfflineCarrierError) as context:
            mod.build_cell_pair(
                common_state_path=self.common,
                left_delta_path=self.left_delta,
                right_delta_path=self.right_delta,
                authority_path=self.authority,
                campaign_label="PRIVATE-STC-MARY-FLIGHT-TEST",
                out=self.private / "stc-mary-offline-pair-same-effect",
                repository=self.repo,
            )
        self.assertEqual(context.exception.code, "CELL_DELTAS_IDENTICAL")

    def test_cell_pair_binds_one_parent_and_two_children(self):
        pair = self.pair()
        left = mod.verify_cell_bundle(pair / "left")
        right = mod.verify_cell_bundle(pair / "right")
        self.assertEqual(left["cell"]["parentStateId"], right["cell"]["parentStateId"])
        self.assertEqual(left["cell"]["pairId"], right["cell"]["pairId"])
        self.assertNotEqual(left["cell"]["childStateId"], right["cell"]["childStateId"])
        self.assertFalse(left["cell"]["automaticMergeAllowed"])
        self.assertEqual(left["cell"]["authority"], "none")

    def test_pair_builds_deterministically_across_output_roots(self):
        first = self.pair("one")
        second = self.pair("two")
        first_pair = json.loads((first / "pair.json").read_text())
        second_pair = json.loads((second / "pair.json").read_text())
        self.assertEqual(first_pair, second_pair)
        self.assertEqual(
            (first / "left" / "manifest.json").read_bytes(),
            (second / "left" / "manifest.json").read_bytes(),
        )

    def test_standalone_cell_verifier_runs_without_repository_history(self):
        pair = self.pair()
        completed = subprocess.run(
            [sys.executable, str(pair / "left" / "verify_bundle.py"), str(pair / "left")],
            cwd=self.root,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
        receipt = json.loads(completed.stdout)
        self.assertEqual(receipt["status"], "PASS")
        self.assertFalse(receipt["repositoryHistoryRequired"])

    def test_cell_tampering_is_refused(self):
        pair = self.pair()
        path = pair / "left" / "common" / self.common.name
        path.write_bytes(path.read_bytes() + b"x")
        with self.assertRaises(mod.OfflineCarrierError) as context:
            mod.verify_cell_bundle(pair / "left")
        self.assertEqual(context.exception.code, "BUNDLE_DIGEST_INVALID")

    def test_cell_extra_file_is_refused(self):
        pair = self.pair()
        (pair / "left" / "extra.txt").write_text("extra", encoding="utf-8")
        with self.assertRaises(mod.OfflineCarrierError) as context:
            mod.verify_cell_bundle(pair / "left")
        self.assertEqual(context.exception.code, "BUNDLE_DENOMINATOR_INVALID")

    def test_cell_missing_file_is_refused(self):
        pair = self.pair()
        (pair / "left" / "delta.json").unlink()
        with self.assertRaises(mod.OfflineCarrierError):
            mod.verify_cell_bundle(pair / "left")

    def test_manifest_unknown_field_is_refused(self):
        pair = self.pair()
        path = pair / "left" / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["invented"] = True
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(mod.OfflineCarrierError) as context:
            mod.verify_cell_bundle(pair / "left")
        self.assertEqual(context.exception.code, "BUNDLE_MANIFEST_INVALID")

    def test_synthetic_cell_receipts_are_valid_but_self_identified(self):
        pair = self.pair()
        left = mod.create_cell_verification(
            mod.verify_cell_bundle(pair / "left"),
            "synthetic_simulation",
        )
        right = mod.create_cell_verification(
            mod.verify_cell_bundle(pair / "right"),
            "synthetic_simulation",
        )
        mod.validate_cell_verification(left)
        mod.validate_cell_verification(right)
        self.assertNotEqual(left["hostClassDigest"], right["hostClassDigest"])
        self.assertEqual(left["mode"], "synthetic_simulation")

    def test_reunion_retains_both_branches_and_ends_human_required(self):
        pair = self.pair()
        left = mod.create_cell_verification(mod.verify_cell_bundle(pair / "left"), "synthetic_simulation")
        right = mod.create_cell_verification(mod.verify_cell_bundle(pair / "right"), "synthetic_simulation")
        output = self.private / "stc-mary-reunion-synthetic"
        result = mod.reunite_cells(
            left_bundle=pair / "left",
            right_bundle=pair / "right",
            left_verification=left,
            right_verification=right,
            out=output,
            repository=self.repo,
        )
        self.assertEqual(result["status"], "HUMAN_REQUIRED")
        verification = json.loads((output / "two-cell-verification.json").read_text())
        self.assertEqual(verification["branchesRetained"], 2)
        self.assertFalse(verification["automaticMergeAllowed"])
        self.assertEqual(verification["reunionTerminal"], "HUMAN_REQUIRED")

    def test_reunion_refuses_same_host_class(self):
        pair = self.pair()
        shared = "f" * 64
        left = mod.create_cell_verification(
            mod.verify_cell_bundle(pair / "left"),
            "private_local_attested",
            host_digest=shared,
        )
        right = mod.create_cell_verification(
            mod.verify_cell_bundle(pair / "right"),
            "private_local_attested",
            host_digest=shared,
        )
        with self.assertRaises(mod.OfflineCarrierError) as context:
            mod.reunite_cells(
                left_bundle=pair / "left",
                right_bundle=pair / "right",
                left_verification=left,
                right_verification=right,
                out=self.private / "stc-mary-reunion-same-host",
                repository=self.repo,
            )
        self.assertEqual(context.exception.code, "REUNION_HOST_INVALID")

    def test_reunion_refuses_mixed_attestation_modes(self):
        pair = self.pair()
        left = mod.create_cell_verification(mod.verify_cell_bundle(pair / "left"), "synthetic_simulation")
        right = mod.create_cell_verification(
            mod.verify_cell_bundle(pair / "right"),
            "private_local_attested",
            host_digest="e" * 64,
        )
        with self.assertRaises(mod.OfflineCarrierError) as context:
            mod.reunite_cells(
                left_bundle=pair / "left",
                right_bundle=pair / "right",
                left_verification=left,
                right_verification=right,
                out=self.private / "stc-mary-reunion-mixed",
                repository=self.repo,
            )
        self.assertEqual(context.exception.code, "REUNION_MODE_INVALID")

    def test_two_cell_verification_identity_refuses_tampering(self):
        pair = self.pair()
        left = mod.create_cell_verification(mod.verify_cell_bundle(pair / "left"), "synthetic_simulation")
        right = mod.create_cell_verification(mod.verify_cell_bundle(pair / "right"), "synthetic_simulation")
        obligation = mod.create_reconciliation_obligation(
            pair_id=left["pairId"],
            left_cell_id=left["cellId"],
            right_cell_id=right["cellId"],
            left_child_state_id=left["childStateId"],
            right_child_state_id=right["childStateId"],
        )
        receipt = mod.create_two_cell_verification(left, right, obligation)
        receipt["automaticMergeAllowed"] = True
        with self.assertRaises(mod.OfflineCarrierError):
            mod.validate_two_cell_verification(receipt)

    def test_successor_bundle_closes_six_question_answer(self):
        successor = self.successor()
        verified = mod.verify_successor_bundle(successor)
        answer = verified["answer"]
        self.assertEqual(answer["whatExists"]["componentCount"], 5)
        self.assertEqual(answer["whoMayAct"], "named_human_bind_only")
        self.assertEqual(
            answer["whichDependenciesAreAbsent"],
            list(mod.ABSENT_DEPENDENCIES),
        )
        self.assertEqual(answer["whatRemainsUnresolved"]["openObligationCount"], 1)

    def test_standalone_successor_verifier_runs(self):
        successor = self.successor()
        completed = subprocess.run(
            [sys.executable, str(successor / "verify_bundle.py"), str(successor)],
            cwd=self.root,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
        self.assertEqual(json.loads(completed.stdout)["bundleType"], "successor")

    def test_successor_tampering_is_refused(self):
        successor = self.successor()
        path = successor / "components" / "cartridge" / "mission.json"
        path.write_text('{"mission":"tampered"}\n', encoding="utf-8")
        with self.assertRaises(mod.OfflineCarrierError) as context:
            mod.verify_successor_bundle(successor)
        self.assertEqual(context.exception.code, "BUNDLE_DIGEST_INVALID")

    def test_successor_answer_dependency_denominator_is_closed(self):
        successor = self.successor()
        path = successor / "six-question-answer.json"
        answer = json.loads(path.read_text())
        answer["whichDependenciesAreAbsent"] = answer["whichDependenciesAreAbsent"][:-1]
        path.write_text(json.dumps(answer), encoding="utf-8")
        with self.assertRaises(mod.OfflineCarrierError):
            mod.verify_successor_bundle(successor)

    def test_successor_verification_proves_changed_host_class(self):
        successor = self.successor()
        verified = mod.verify_successor_bundle(successor)
        original = "1" * 64
        receipt = mod.create_successor_verification(
            verified,
            "private_local_attested",
            original,
            current_host_digest="2" * 64,
        )
        mod.validate_successor_verification(receipt)
        self.assertTrue(receipt["hostClassChanged"])
        self.assertFalse(receipt["repositoryHistoryRequired"])

    def test_successor_verification_refuses_original_host(self):
        successor = self.successor()
        verified = mod.verify_successor_bundle(successor)
        with self.assertRaises(mod.OfflineCarrierError) as context:
            mod.create_successor_verification(
                verified,
                "private_local_attested",
                "3" * 64,
                current_host_digest="3" * 64,
            )
        self.assertEqual(context.exception.code, "SUCCESSOR_HOST_CLASS_INVALID")

    def test_successor_receipt_identity_refuses_tampering(self):
        successor = self.successor()
        verified = mod.verify_successor_bundle(successor)
        receipt = mod.create_successor_verification(
            verified,
            "synthetic_simulation",
            "4" * 64,
        )
        receipt["repositoryHistoryRequired"] = True
        with self.assertRaises(mod.OfflineCarrierError):
            mod.validate_successor_verification(receipt)

    def test_private_root_inside_repository_is_refused(self):
        output = self.repo / "stc-mary-offline-forbidden"
        with self.assertRaises(mod.OfflineCarrierError) as context:
            mod.validate_new_private_root(output, self.repo)
        self.assertEqual(context.exception.code, "PRIVATE_ROOT_IN_REPOSITORY")

    @unittest.skipIf(os.name == "nt", "symlink creation may require elevated Windows privileges")
    def test_source_symlink_is_refused(self):
        source = self.root / "source-tree"
        source.mkdir()
        target = self.root / "target.txt"
        target.write_text("target", encoding="utf-8")
        (source / "link.txt").symlink_to(target)
        with self.assertRaises(mod.OfflineCarrierError) as context:
            mod.describe_source(source, "fixture")
        self.assertEqual(context.exception.code, "SYMLINK_REFUSED")

    def test_templates_are_valid_and_deliberately_incomplete(self):
        output = self.private / "stc-mary-offline-inputs-template"
        result = mod.template_inputs(out=output, repository=self.repo)
        self.assertEqual(result["status"], "PASS")
        mod.validate_cell_delta(json.loads((output / "left-delta.json").read_text()), "left")
        mod.validate_authority_boundary(json.loads((output / "authority.json").read_text()))
        self.assertIn("REPLACE_WITH_", (output / "next-safe-action.txt").read_text())

    def test_parser_exposes_exact_profile_commands(self):
        parser = mod.build_parser()
        for command in mod.COMMANDS:
            if command == "validate-profile":
                args = parser.parse_args([command, str(self.profile)])
            elif command == "template-inputs":
                args = parser.parse_args([command, "--out", "x", "--repository", "y"])
            else:
                continue
            self.assertEqual(args.command, command)
        with self.assertRaises(SystemExit):
            parser.parse_args(["invent-authority"])

    def test_builds_do_not_mutate_source_inputs(self):
        before = {
            path: path.read_bytes()
            for path in (
                self.common,
                self.left_delta,
                self.right_delta,
                self.authority,
                self.obligations,
                self.next_action,
            )
        }
        self.pair()
        self.successor()
        after = {path: path.read_bytes() for path in before}
        self.assertEqual(before, after)

    def test_authority_boundary_cannot_self_promote(self):
        value = mod.create_authority_boundary()
        value["machineAuthority"] = "scheduler"
        with self.assertRaises(mod.OfflineCarrierError) as context:
            mod.validate_authority_boundary(value)
        self.assertEqual(context.exception.code, "AUTHORITY_CLAIM_INVALID")


    @unittest.skipIf(local_mod is None, "local toolchain package is unavailable")
    def test_plan_gates_accept_only_private_local_carrier_receipts(self):
        required_commit = "a" * 40
        plan_repo = self.root / "plan-repo"
        plan_repo.mkdir()

        readiness_body = {
            "schema": "stc-mary-local-readiness-private/1",
            "profileId": local_mod.TOOLCHAIN_PROFILE_ID,
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
            "torch": {
                "available": True,
                "version": "fixture",
                "cudaAvailable": True,
                "deviceCount": 1,
                "devices": [],
            },
            "nvidiaQuery": {},
            "nvidiaGpus": [{"memory.total": 24576}],
            "windows": {
                "applicable": True,
                "raw": {},
                "parsed": {
                    "latticeProcesses": [],
                    "latticeServices": [],
                    "listeners": [],
                },
            },
            "artifacts": [{
                "schema": "stc-mary-local-artifact-manifest/1",
                "label": "cartridge",
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
        readiness = {
            **readiness_body,
            "readinessId": local_mod.content_id(
                "stcmarylocalreadiness1",
                readiness_body,
            ),
        }
        readiness_path = self.root / "readiness.json"
        readiness_path.write_text(json.dumps(readiness), encoding="utf-8")

        feed = self.root / "stc-mary-local-feed-plan"
        local_mod.generate_feed(argparse.Namespace(
            out=str(feed),
            records=128,
            features=8,
            classes=4,
            seed=20260827,
        ))
        baseline_path = self.root / "baseline.json"
        local_mod.run_workload(argparse.Namespace(
            feed=str(feed),
            backend="python",
            device_index=0,
            out=str(baseline_path),
        ))

        pair = self.pair("plan")
        left_verified = mod.verify_cell_bundle(pair / "left")
        right_verified = mod.verify_cell_bundle(pair / "right")
        successor = self.successor("plan")
        successor_verified = mod.verify_successor_bundle(successor)

        synthetic_left = mod.create_cell_verification(
            left_verified,
            "synthetic_simulation",
        )
        synthetic_right = mod.create_cell_verification(
            right_verified,
            "synthetic_simulation",
        )
        synthetic_obligation = mod.create_reconciliation_obligation(
            pair_id=synthetic_left["pairId"],
            left_cell_id=synthetic_left["cellId"],
            right_cell_id=synthetic_right["cellId"],
            left_child_state_id=synthetic_left["childStateId"],
            right_child_state_id=synthetic_right["childStateId"],
        )
        synthetic_cells = mod.create_two_cell_verification(
            synthetic_left,
            synthetic_right,
            synthetic_obligation,
        )
        synthetic_successor = mod.create_successor_verification(
            successor_verified,
            "synthetic_simulation",
            "5" * 64,
        )
        synthetic_cells_path = self.root / "synthetic-cells.json"
        synthetic_successor_path = self.root / "synthetic-successor.json"
        synthetic_cells_path.write_text(json.dumps(synthetic_cells), encoding="utf-8")
        synthetic_successor_path.write_text(json.dumps(synthetic_successor), encoding="utf-8")

        synthetic_output = self.root / "stc-mary-local-plan-synthetic"
        local_mod.compile_plan(argparse.Namespace(
            repository=str(plan_repo),
            readiness=str(readiness_path),
            feed=str(feed),
            baseline=str(baseline_path),
            accelerated=None,
            continuity=None,
            cell_verification=str(synthetic_cells_path),
            successor_verification=str(synthetic_successor_path),
            campaign_label="PRIVATE-STC-MARY-PLAN-SYNTHETIC",
            required_commit=required_commit,
            out=str(synthetic_output),
        ))
        synthetic_plan = json.loads(
            (synthetic_output / "local-flight-plan.json").read_text()
        )
        synthetic_gates = {
            row["name"]: row["status"] for row in synthetic_plan["gates"]
        }
        self.assertEqual(synthetic_gates["two_cell_partition"], "HOLD")
        self.assertEqual(synthetic_gates["successor_head"], "HOLD")

        private_left = mod.create_cell_verification(
            left_verified,
            "private_local_attested",
            host_digest="6" * 64,
        )
        private_right = mod.create_cell_verification(
            right_verified,
            "private_local_attested",
            host_digest="7" * 64,
        )
        private_obligation = mod.create_reconciliation_obligation(
            pair_id=private_left["pairId"],
            left_cell_id=private_left["cellId"],
            right_cell_id=private_right["cellId"],
            left_child_state_id=private_left["childStateId"],
            right_child_state_id=private_right["childStateId"],
        )
        private_cells = mod.create_two_cell_verification(
            private_left,
            private_right,
            private_obligation,
        )
        private_successor = mod.create_successor_verification(
            successor_verified,
            "private_local_attested",
            "8" * 64,
            current_host_digest="9" * 64,
        )
        private_cells_path = self.root / "private-cells.json"
        private_successor_path = self.root / "private-successor.json"
        private_cells_path.write_text(json.dumps(private_cells), encoding="utf-8")
        private_successor_path.write_text(json.dumps(private_successor), encoding="utf-8")

        private_output = self.root / "stc-mary-local-plan-private"
        local_mod.compile_plan(argparse.Namespace(
            repository=str(plan_repo),
            readiness=str(readiness_path),
            feed=str(feed),
            baseline=str(baseline_path),
            accelerated=None,
            continuity=None,
            cell_verification=str(private_cells_path),
            successor_verification=str(private_successor_path),
            campaign_label="PRIVATE-STC-MARY-PLAN-ATTESTED",
            required_commit=required_commit,
            out=str(private_output),
        ))
        private_plan = json.loads(
            (private_output / "local-flight-plan.json").read_text()
        )
        private_gates = {
            row["name"]: row["status"] for row in private_plan["gates"]
        }
        self.assertEqual(private_gates["two_cell_partition"], "READY")
        self.assertEqual(private_gates["successor_head"], "READY")
        config = json.loads(
            (private_output / "flight-config.generated.json").read_text()
        )
        self.assertFalse(
            config["identityClasses"]["leftCell"].startswith("REPLACE_WITH_")
        )
        self.assertFalse(
            config["identityClasses"]["successorHead"].startswith("REPLACE_WITH_")
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
