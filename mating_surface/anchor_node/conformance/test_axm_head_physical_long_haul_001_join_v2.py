from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ANCHOR = Path(__file__).resolve().parents[1]
TOOL_PATH = ANCHOR / "axm_head_physical_long_haul_001_join_v2.py"
VERIFIER_PATH = ANCHOR / "verify_axm_head_physical_long_haul_001_join_v2.py"
BOOTSTRAP_PATH = ANCHOR / "verify_axm_head_physical_long_haul_001_join_v2_bootstrap.py"
PROFILE_PATH = ANCHOR / "axm-head-physical-long-haul-001-join-v2-profile.json"
WRAPPER_PATH = ANCHOR / "axm-head-physical-long-haul-001-join-v2.ps1"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TOOL = load_module("join_v2_tool_tests", TOOL_PATH)
VERIFIER = load_module("join_v2_verifier_tests", VERIFIER_PATH)
BOOTSTRAP = load_module("join_v2_bootstrap_tests", BOOTSTRAP_PATH)


class JoinV2Tests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.profile = TOOL.validate_profile(PROFILE_PATH)
        self.checkouts = {
            "conductor": {
                "commit": TOOL.EXPECTED_SOURCE_COORDINATES["admittedConductor"]["commit"],
                "tree": TOOL.EXPECTED_SOURCE_COORDINATES["admittedConductor"]["tree"],
                "detached": True,
                "clean": True,
            },
            "physicalFloor": {
                "commit": TOOL.EXPECTED_SOURCE_COORDINATES["physicalFlightFloor"]["commit"],
                "tree": TOOL.EXPECTED_SOURCE_COORDINATES["physicalFlightFloor"]["tree"],
                "detached": True,
                "clean": True,
            },
        }
        self.headers = [
            {
                "label": label,
                "contentRef": f"sha256:{index + 1:064x}",
                "exists": True,
                "symlinkRoot": False,
                "overlapFree": True,
            }
            for index, label in enumerate(TOOL.ARTIFACT_LABELS)
        ]

    def tearDown(self) -> None:
        self.temp.cleanup()

    def build(self, name: str = "carrier") -> Path:
        target = self.root / name
        manifest = TOOL.build_carrier(profile_path=PROFILE_PATH, out=target)
        self.assertEqual(manifest["terminal"], "PREPARED_NOT_ARMED")
        self.assertFalse(manifest["physicalExecutionStarted"])
        self.assertEqual(manifest["authority"], "none")
        return target

    def full_state(self, *, card: bool = False):
        state = TOOL.make_state(
            self.profile,
            checkout_bindings=self.checkouts,
            private_coordinate_headers=self.headers,
        )
        return TOOL.attach_compiled_card(self.profile, state) if card else state

    def run_tool(self, *args: str):
        return subprocess.run(
            [sys.executable, str(TOOL_PATH), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def resign_manifest_member(self, carrier: Path, relative: str) -> None:
        manifest_path = carrier / "MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        member = carrier / Path(*relative.split("/"))
        data = member.read_bytes()
        for row in manifest["files"]:
            if row["path"] == relative:
                row["bytes"] = len(data)
                row["sha256"] = hashlib.sha256(data).hexdigest()
                break
        else:
            self.fail(f"manifest row missing: {relative}")
        body = dict(manifest)
        body.pop("carrierId")
        manifest["carrierId"] = TOOL.content_id("axmheadjoincarrier2", body)
        manifest_path.write_bytes(TOOL.pretty_json_bytes(manifest))

    def mutate_json_and_resign(self, carrier: Path, relative: str, mutate) -> None:
        path = carrier / Path(*relative.split("/"))
        value = json.loads(path.read_text(encoding="utf-8"))
        mutate(value)
        path.write_bytes(TOOL.pretty_json_bytes(value))
        self.resign_manifest_member(carrier, relative)

    def test_01_profile_exact_coordinate_validates(self):
        self.assertEqual(self.profile["owningProject"], "Estate")
        self.assertEqual(self.profile["owningRepository"], "BigBirdReturns/ai-execution-audit")
        self.assertEqual(self.profile["sourceCoordinates"]["admittedAxmHeadSupplier"]["commit"], "b452bb32e26249deab90db124f157bc62ad0850d")
        self.assertEqual(self.profile["sourceCoordinates"]["admittedAxmHeadSupplier"]["tree"], "c557bddc17ad62f6ad36bac5a6ef57338429a951")

    def test_02_profile_canonical_digest_is_frozen(self):
        self.assertEqual(TOOL.sha256_bytes(TOOL.canonical_json_bytes(self.profile)), TOOL.PROFILE_CANONICAL_SHA256)

    def test_03_profile_coordinate_drift_refuses(self):
        changed = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        changed["sourceCoordinates"]["admittedAxmHeadSupplier"]["tree"] = "0" * 40
        path = self.root / "profile.json"
        path.write_text(json.dumps(changed), encoding="utf-8")
        with self.assertRaisesRegex(TOOL.JoinError, "source coordinates differ"):
            TOOL.validate_profile(path)

    def test_04_issue_37_is_sole_physical_coordinate(self):
        self.assertEqual(self.profile["physicalFlightIssue"], TOOL.EXPECTED_ISSUE)

    def test_05_phase_denominator_is_twelve(self):
        self.assertEqual(tuple(self.profile["phaseSequence"]), TOOL.PHASE_SEQUENCE)
        self.assertEqual(len(self.profile["phasePlans"]), 12)

    def test_06_packet_denominator_is_sixteen(self):
        self.assertEqual(tuple(self.profile["packetStageSequence"]), TOOL.PACKET_STAGE_SEQUENCE)
        self.assertEqual(len(self.profile["packetStageSequence"]), 16)

    def test_07_prepared_state_has_zero_activity(self):
        state = TOOL.prepared_state(self.profile)
        self.assertFalse(state["physicalExecutionStarted"])
        self.assertEqual(state["workersLaunched"], 0)
        self.assertEqual(state["listenersCreated"], 0)
        self.assertFalse(state["authorization"]["granted"])
        self.assertEqual(state["authority"], "none")
        self.assertIsNone(state["executionCard"])

    def test_08_prepared_state_terminates_prepared_not_armed(self):
        decision = TOOL.evaluate_preparation(self.profile, TOOL.prepared_state(self.profile))
        self.assertEqual(decision["terminal"], "PREPARED_NOT_ARMED")
        self.assertFalse(decision["physicalAuthorizationProduced"])

    def test_09_partial_checkout_denominator_holds(self):
        state = TOOL.make_state(self.profile, checkout_bindings={"conductor": self.checkouts["conductor"]})
        decision = TOOL.evaluate_preparation(self.profile, state)
        self.assertEqual(decision["terminal"], "HOLD")
        self.assertIn("EXACT_CHECKOUTS_INCOMPLETE", decision["reasonCodes"])

    def test_10_dirty_checkout_holds(self):
        changed = json.loads(json.dumps(self.checkouts))
        changed["physicalFloor"]["clean"] = False
        state = TOOL.make_state(self.profile, checkout_bindings=changed, private_coordinate_headers=self.headers)
        decision = TOOL.evaluate_preparation(self.profile, state)
        self.assertEqual(decision["terminal"], "HOLD")
        self.assertIn("CHECKOUT_NOT_CLEAN_DETACHED", decision["reasonCodes"])

    def test_11_incomplete_private_header_denominator_holds(self):
        state = TOOL.make_state(self.profile, checkout_bindings=self.checkouts, private_coordinate_headers=self.headers[:3])
        decision = TOOL.evaluate_preparation(self.profile, state)
        self.assertEqual(decision["terminal"], "HOLD")
        self.assertIn("PRIVATE_COORDINATE_DENOMINATOR_INCOMPLETE", decision["reasonCodes"])

    def test_12_unsafe_private_header_holds(self):
        headers = json.loads(json.dumps(self.headers))
        headers[0]["symlinkRoot"] = True
        state = TOOL.make_state(self.profile, checkout_bindings=self.checkouts, private_coordinate_headers=headers)
        decision = TOOL.evaluate_preparation(self.profile, state)
        self.assertEqual(decision["terminal"], "HOLD")
        self.assertIn("PRIVATE_COORDINATE_UNSAFE", decision["reasonCodes"])

    def test_13_complete_prerequisites_without_card_hold(self):
        decision = TOOL.evaluate_preparation(self.profile, self.full_state())
        self.assertEqual(decision["terminal"], "HOLD")
        self.assertEqual(decision["reasonCodes"], ["EXECUTION_CARD_ABSENT"])

    def test_14_compiled_card_reaches_human_review_only(self):
        state = self.full_state(card=True)
        decision = TOOL.evaluate_preparation(self.profile, state)
        self.assertEqual(decision["terminal"], "READY_FOR_HUMAN_REVIEW")
        self.assertIn("SEPARATE_HUMAN_AUTHORIZATION_REQUIRED", decision["reasonCodes"])
        self.assertFalse(decision["physicalAuthorizationProduced"])
        self.assertEqual(decision["authority"], "none")

    def test_15_card_contains_all_twelve_phases(self):
        card = self.full_state(card=True)["executionCard"]
        self.assertEqual(card["actionCount"], 12)
        self.assertEqual([row["phase"] for row in card["actions"]], list(TOOL.PHASE_SEQUENCE))

    def test_16_every_card_action_is_unauthorized(self):
        card = self.full_state(card=True)["executionCard"]
        self.assertTrue(all(row["authorized"] is False for row in card["actions"]))
        self.assertFalse(card["physicalAuthorizationProduced"])
        self.assertFalse(card["physicalExecutionStarted"])
        self.assertEqual(card["authority"], "none")

    def test_17_card_names_receipt_and_stop_denominators(self):
        card = self.full_state(card=True)["executionCard"]
        for action in card["actions"]:
            self.assertTrue(action["receiptClasses"])
            self.assertEqual(action["stopConditions"], self.profile["stopConditions"])
            self.assertTrue(action["commandSurface"])
            self.assertTrue(action["operatorAction"])

    def test_18_card_first_physical_action_is_explicit(self):
        card = self.full_state(card=True)["executionCard"]
        ordinal = card["firstPhysicalActionOrdinal"]
        self.assertIsInstance(ordinal, int)
        self.assertTrue(card["actions"][ordinal - 1]["physicalAction"])
        self.assertTrue(all(not row["physicalAction"] for row in card["actions"][: ordinal - 1]))

    def test_19_card_compilation_refuses_incomplete_preparation(self):
        with self.assertRaisesRegex(TOOL.JoinError, "safe private coordinate headers"):
            TOOL.compile_execution_card(self.profile, TOOL.prepared_state(self.profile))

    def test_20_card_compilation_refuses_started_activity(self):
        state = TOOL.make_state(
            self.profile,
            checkout_bindings=self.checkouts,
            private_coordinate_headers=self.headers,
            physical_execution_started=True,
        )
        with self.assertRaisesRegex(TOOL.JoinError, "after physical activity begins"):
            TOOL.compile_execution_card(self.profile, state)

    def test_21_physical_execution_started_refuses(self):
        state = TOOL.make_state(self.profile, physical_execution_started=True)
        decision = TOOL.evaluate_preparation(self.profile, state)
        self.assertEqual(decision["terminal"], "REFUSED")
        self.assertIn("PHYSICAL_EXECUTION_ALREADY_STARTED", decision["reasonCodes"])

    def test_22_worker_or_listener_activity_refuses(self):
        state = TOOL.make_state(self.profile, workers_launched=1, listeners_created=1)
        decision = TOOL.evaluate_preparation(self.profile, state)
        self.assertEqual(decision["terminal"], "REFUSED")
        self.assertIn("UNEXPECTED_RUNTIME_ACTIVITY", decision["reasonCodes"])

    def test_23_authority_promotion_refuses(self):
        state = TOOL.make_state(
            self.profile,
            authorization={"granted": True, "actorId": "named-human", "transactionId": "authorization-1"},
            authority="human",
        )
        decision = TOOL.evaluate_preparation(self.profile, state)
        self.assertEqual(decision["terminal"], "REFUSED")
        self.assertIn("AUTHORITY_PROMOTION_REFUSED", decision["reasonCodes"])

    def test_24_wrong_checkout_coordinate_refuses_state(self):
        changed = json.loads(json.dumps(self.checkouts))
        changed["conductor"]["commit"] = "0" * 40
        state = TOOL.make_state(self.profile, checkout_bindings=changed)
        decision = TOOL.evaluate_preparation(self.profile, state)
        self.assertEqual(decision["terminal"], "REFUSED")
        self.assertEqual(decision["errorCode"], "CHECKOUT_COORDINATE_INVALID")

    def test_25_private_headers_are_body_free(self):
        state = self.full_state()
        serialized = json.dumps(state)
        self.assertNotIn("privatePath", serialized)
        self.assertNotIn("hostname", serialized.lower())
        self.assertNotIn("credential", serialized.lower())
        self.assertEqual(set(state["privateCoordinateHeaders"][0]), {"label", "contentRef", "exists", "symlinkRoot", "overlapFree"})

    def test_26_duplicate_private_label_refuses(self):
        headers = json.loads(json.dumps(self.headers))
        headers[1]["label"] = headers[0]["label"]
        state = TOOL.make_state(self.profile, private_coordinate_headers=headers)
        decision = TOOL.evaluate_preparation(self.profile, state)
        self.assertEqual(decision["terminal"], "REFUSED")
        self.assertEqual(decision["errorCode"], "PRIVATE_HEADER_DUPLICATE")

    def test_27_invalid_content_reference_refuses(self):
        headers = json.loads(json.dumps(self.headers))
        headers[0]["contentRef"] = "not-a-digest"
        state = TOOL.make_state(self.profile, private_coordinate_headers=headers)
        decision = TOOL.evaluate_preparation(self.profile, state)
        self.assertEqual(decision["terminal"], "REFUSED")
        self.assertEqual(decision["errorCode"], "STRING_PATTERN_INVALID")

    def test_28_caller_supplied_card_forgery_refuses(self):
        state = self.full_state(card=True)
        state["executionCard"]["actions"][0]["authorized"] = True
        body = dict(state)
        body.pop("stateId")
        state["stateId"] = TOOL.content_id("axmheadjoinstate2", body)
        decision = TOOL.evaluate_preparation(self.profile, state)
        self.assertEqual(decision["terminal"], "REFUSED")
        self.assertIn("EXECUTION_CARD_MISMATCH", decision["reasonCodes"])

    def test_29_carrier_build_is_deterministic(self):
        left = self.build("left")
        right = self.build("right")
        left_files = sorted(path.relative_to(left).as_posix() for path in left.rglob("*") if path.is_file())
        right_files = sorted(path.relative_to(right).as_posix() for path in right.rglob("*") if path.is_file())
        self.assertEqual(left_files, right_files)
        for relative in left_files:
            self.assertEqual((left / relative).read_bytes(), (right / relative).read_bytes(), relative)

    def test_30_carrier_has_closed_five_member_denominator(self):
        carrier = self.build()
        manifest = json.loads((carrier / "MANIFEST.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["fileCount"], 5)
        self.assertEqual([row["path"] for row in manifest["files"]], list(TOOL.EXPECTED_RELATIVE_FILES))

    def test_31_direct_verifier_passes_without_self_authentication(self):
        carrier = self.build("forged-auth-environment")
        env = os.environ.copy()
        env["AXM_HEAD_JOIN_V2_BOOTSTRAP_AUTHENTICATED"] = "1"
        env["AXM_HEAD_JOIN_V2_VERIFIER_SHA256"] = TOOL.STANDALONE_VERIFIER_SHA256
        completed = subprocess.run(
            [sys.executable, str(carrier / "RECOVERY/verify_join.py"), str(carrier)],
            stdout=subprocess.PIPE,
            env=env,
            check=False,
        )
        self.assertEqual(completed.returncode, 0)
        verdict = json.loads(completed.stdout)
        self.assertEqual(verdict["status"], "PASS")
        self.assertFalse(verdict["bootstrapAuthenticated"])

    def test_32_bootstrap_authenticates_exact_verifier(self):
        carrier = self.build("bootstrap-custody")
        out = self.root / "authenticated-verdict.json"
        completed = subprocess.run(
            [sys.executable, str(BOOTSTRAP_PATH), str(carrier), "--out", str(out)],
            stdout=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, out.read_bytes())
        verdict = json.loads(completed.stdout)
        self.assertTrue(verdict["bootstrapAuthenticated"])
        self.assertEqual(verdict["standaloneVerifierSha256"], TOOL.STANDALONE_VERIFIER_SHA256)

    def test_33_unmanifested_file_refuses(self):
        carrier = self.build()
        (carrier / "EXTRA.txt").write_text("extra\n", encoding="utf-8")
        with self.assertRaisesRegex(VERIFIER.VerificationError, "file denominator differs"):
            VERIFIER.verify(carrier)

    def test_34_missing_member_refuses(self):
        carrier = self.build()
        (carrier / "PUBLIC/status.json").unlink()
        with self.assertRaisesRegex(VERIFIER.VerificationError, "required regular member"):
            VERIFIER.verify(carrier)

    def test_35_resigned_public_claim_promotion_refuses(self):
        cases = (
            ("PUBLIC/status.json", "physicalExecutionStarted", True, "public status is not reconstructed"),
            ("PUBLIC/status.json", "physicalExecutionStarted", 0, "public status is not reconstructed"),
            ("JOIN/decision.json", "physicalAuthorizationProduced", True, "decision is not reconstructed"),
            ("JOIN/decision.json", "physicalAuthorizationProduced", 0, "decision is not reconstructed"),
        )
        for index, (relative, key, replacement, message) in enumerate(cases):
            with self.subTest(relative=relative, key=key, replacement=replacement):
                carrier = self.build(f"resigned-public-semantics-{index}")
                self.mutate_json_and_resign(
                    carrier,
                    relative,
                    lambda value, k=key, r=replacement: value.__setitem__(k, r),
                )
                with self.assertRaisesRegex(VERIFIER.VerificationError, message):
                    VERIFIER.verify(carrier)

    def test_36_resigned_preparation_activity_refuses(self):
        member_cases = (
            ("workersLaunched", 1),
            ("workersLaunched", False),
        )
        for index, (key, replacement) in enumerate(member_cases):
            with self.subTest(member=key, replacement=replacement):
                carrier = self.build(f"resigned-preparation-{index}")
                self.mutate_json_and_resign(
                    carrier,
                    "JOIN/preparation-state.json",
                    lambda value, k=key, r=replacement: value.__setitem__(k, r),
                )
                with self.assertRaisesRegex(VERIFIER.VerificationError, "prepared state is not reconstructed"):
                    VERIFIER.verify(carrier)

        manifest_cases = (
            ("physicalExecutionStarted", True, "manifest physicalExecutionStarted differs"),
            ("physicalExecutionStarted", 0, "manifest physicalExecutionStarted differs"),
            ("bootstrapRequired", False, "bootstrapRequired must remain true"),
            ("bootstrapRequired", 1, "bootstrapRequired must remain true"),
            ("fileCount", False, "manifest fileCount differs"),
        )
        for index, (key, replacement, message) in enumerate(manifest_cases):
            with self.subTest(manifest=key, replacement=replacement):
                carrier = self.build(f"resigned-manifest-{index}")
                manifest_path = carrier / "MANIFEST.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest[key] = replacement
                body = dict(manifest)
                body.pop("carrierId")
                manifest["carrierId"] = TOOL.content_id("axmheadjoincarrier2", body)
                manifest_path.write_bytes(TOOL.pretty_json_bytes(manifest))
                with self.assertRaisesRegex(VERIFIER.VerificationError, message):
                    VERIFIER.verify(carrier)

    def test_37_rewritten_profile_refuses_after_resigning(self):
        carrier = self.build()
        self.mutate_json_and_resign(carrier, "RECOVERY/profile.json", lambda value: value.__setitem__("status", "admitted"))
        with self.assertRaisesRegex(VERIFIER.VerificationError, "canonical digest differs"):
            VERIFIER.verify(carrier)

    def test_38_malicious_verifier_substitution_refuses_before_execution(self):
        carrier = self.build()
        marker = self.root / "executed.txt"
        verifier = carrier / "RECOVERY/verify_join.py"
        verifier.write_text(
            f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\nprint('{{\"status\":\"PASS\"}}')\n",
            encoding="utf-8",
        )
        self.resign_manifest_member(carrier, "RECOVERY/verify_join.py")
        completed = subprocess.run([sys.executable, str(BOOTSTRAP_PATH), str(carrier)], stdout=subprocess.PIPE, check=False)
        self.assertEqual(completed.returncode, 2)
        refusal = json.loads(completed.stdout)
        self.assertEqual(refusal["code"], "VERIFIER_SUBSTITUTION_REFUSED")
        self.assertFalse(marker.exists())

    def test_39_verdict_inside_carrier_refuses_without_mutation(self):
        carrier = self.build()
        manifest_before = (carrier / "MANIFEST.json").read_bytes()
        out = carrier / "VERDICT.json"
        completed = subprocess.run([sys.executable, str(BOOTSTRAP_PATH), str(carrier), "--out", str(out)], stdout=subprocess.PIPE, check=False)
        self.assertEqual(completed.returncode, 2)
        self.assertFalse(out.exists())
        self.assertEqual((carrier / "MANIFEST.json").read_bytes(), manifest_before)

    def test_40_hardlink_output_alias_refuses(self):
        if not hasattr(os, "link"):
            self.skipTest("hard links unavailable")
        carrier = self.build()
        alias = self.root / "alias.json"
        try:
            os.link(carrier / "MANIFEST.json", alias)
        except OSError as exc:
            self.skipTest(str(exc))
        completed = subprocess.run([sys.executable, str(BOOTSTRAP_PATH), str(carrier), "--out", str(alias)], stdout=subprocess.PIPE, check=False)
        self.assertEqual(completed.returncode, 2)
        refusal = json.loads(completed.stdout)
        self.assertEqual(refusal["code"], "OUTPUT_ALIASES_CARRIER")

    def test_41_symlink_member_refuses(self):
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks unavailable")
        carrier = self.build()
        member = carrier / "PUBLIC/status.json"
        copy = self.root / "status.json"
        shutil.copyfile(member, copy)
        member.unlink()
        try:
            os.symlink(copy, member)
        except OSError as exc:
            self.skipTest(str(exc))
        with self.assertRaisesRegex(VERIFIER.VerificationError, "missing or symlinked"):
            VERIFIER.verify(carrier)

    def test_42_powershell_wrapper_has_no_remote_or_execution_surface(self):
        text = WRAPPER_PATH.read_text(encoding="utf-8").lower()
        for forbidden in ("invoke-webrequest", "start-process", "new-pssession", "ssh ", "winrm", "start-job"):
            self.assertNotIn(forbidden, text)


    def test_43_caller_supplied_card_type_confusion_refuses(self):
        cases = (
            ("action.authorized", lambda card: card["actions"][0].__setitem__("authorized", 0)),
            ("card.physicalAuthorizationProduced", lambda card: card.__setitem__("physicalAuthorizationProduced", 0)),
            ("card.actionCount", lambda card: card.__setitem__("actionCount", 12.0)),
            ("card.firstPhysicalActionOrdinal", lambda card: card.__setitem__("firstPhysicalActionOrdinal", 5.0)),
        )
        for label, mutate in cases:
            with self.subTest(label=label):
                state = self.full_state(card=True)
                mutate(state["executionCard"])
                body = dict(state)
                body.pop("stateId")
                state["stateId"] = TOOL.content_id("axmheadjoinstate2", body)
                decision = TOOL.evaluate_preparation(self.profile, state)
                self.assertEqual(decision["terminal"], "REFUSED")
                self.assertIn("EXECUTION_CARD_MISMATCH", decision["reasonCodes"])

    def test_44_issue_binding_type_confusion_refuses(self):
        state = self.full_state()
        state["physicalFlightIssue"]["issueNumber"] = 37.0
        state["preparationBasisId"] = TOOL.content_id(
            "axmheadjoinbasis2", TOOL.state_basis_body(self.profile, state)
        )
        body = dict(state)
        body.pop("stateId")
        state["stateId"] = TOOL.content_id("axmheadjoinstate2", body)
        decision = TOOL.evaluate_preparation(self.profile, state)
        self.assertEqual(decision["terminal"], "REFUSED")
        self.assertEqual(decision["errorCode"], "STATE_ISSUE_BINDING_INVALID")

    def test_45_direct_refusal_ignores_forged_authentication_environment(self):
        carrier = self.build("forged-auth-refusal")
        (carrier / "EXTRA.txt").write_text("extra\n", encoding="utf-8")
        env = os.environ.copy()
        env["AXM_HEAD_JOIN_V2_BOOTSTRAP_AUTHENTICATED"] = "1"
        env["AXM_HEAD_JOIN_V2_VERIFIER_SHA256"] = TOOL.STANDALONE_VERIFIER_SHA256
        completed = subprocess.run(
            [sys.executable, str(carrier / "RECOVERY/verify_join.py"), str(carrier)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stderr, b"")
        refusal = json.loads(completed.stdout)
        self.assertEqual(refusal["status"], "REFUSED")
        self.assertFalse(refusal["bootstrapAuthenticated"])

    def test_46_repository_output_is_refused_before_writing(self):
        carrier = self.build("external-carrier")
        inside_dir = ANCHOR / ".join-v2-repository-output-refused-test"
        inside_file = ANCHOR / ".join-v2-repository-output-refused-test.json"
        try:
            with self.assertRaisesRegex(TOOL.JoinError, "inside the repository"):
                TOOL.build_carrier(profile_path=PROFILE_PATH, out=inside_dir)
            with self.assertRaisesRegex(TOOL.JoinError, "inside the repository"):
                TOOL.emit({"status": "PASS"}, inside_file)
            with self.assertRaisesRegex(TOOL.JoinError, "inside the repository"):
                TOOL.run_bootstrap(carrier, inside_file)
            self.assertFalse(inside_dir.exists())
            self.assertFalse(inside_file.exists())
        finally:
            if inside_dir.is_dir():
                shutil.rmtree(inside_dir)
            elif inside_dir.exists():
                inside_dir.unlink()
            if inside_file.exists():
                inside_file.unlink()


    def test_47_bootstrap_executes_measured_bytes_not_reopened_path(self):
        carrier = self.build("measured-verifier-race")
        verifier_path = carrier / "RECOVERY/verify_join.py"
        measured_bytes = verifier_path.read_bytes()
        marker = self.root / "malicious-verifier-executed.txt"
        verifier_path.write_text(
            "from pathlib import Path\n"
            f"Path({str(marker)!r}).write_text('executed', encoding='utf-8')\n",
            encoding="utf-8",
        )
        env = os.environ.copy()
        env.pop("AXM_HEAD_JOIN_V2_BOOTSTRAP_AUTHENTICATED", None)
        env.pop("AXM_HEAD_JOIN_V2_VERIFIER_SHA256", None)
        result = BOOTSTRAP.invoke_measured_verifier(measured_bytes, carrier, env)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr, b"")
        self.assertFalse(marker.exists())
        refusal = json.loads(result.stdout)
        self.assertEqual(refusal["status"], "REFUSED")
        self.assertFalse(refusal["bootstrapAuthenticated"])


if __name__ == "__main__":
    unittest.main()
