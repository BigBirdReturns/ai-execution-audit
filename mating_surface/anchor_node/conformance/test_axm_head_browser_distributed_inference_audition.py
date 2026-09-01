from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPOSITORY_ROOT = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
import axm_head_browser_distributed_inference_audition as mod

PROFILE = ROOT / "axm-head-browser-distributed-inference-audition-profile-01.json"
FIXTURES = ROOT / "fixtures" / "axm-head-browser-distributed-inference-audition-cases-01.json"
TOOL = ROOT / "axm_head_browser_distributed_inference_audition.py"
PROBE = ROOT / "browser_distributed_inference_probe.js"
VERIFIER = ROOT / "verify_axm_head_browser_distributed_inference_audition.py"
BOOTSTRAP = ROOT / "verify_axm_head_browser_distributed_inference_audition_bootstrap.py"
WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "axm-head-browser-distributed-inference-audition-01.yml"


class BrowserAuditionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="browser-distributed-audition-")
        self.work = Path(self.temp.name)
        self.profile = mod.validate_profile(PROFILE)
        self.fixtures = mod.validate_fixture_catalog(FIXTURES, self.profile)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def case(self, case_id: str) -> dict:
        return mod.find_case(self.fixtures, case_id)

    def decision(self, case_id: str) -> dict:
        row = self.case(case_id)
        return mod.assess_capture(row["capture"], self.profile, case_id=case_id)

    def write(self, name: str, value: dict) -> Path:
        path = self.work / name
        path.write_bytes(mod.pretty_bytes(value))
        return path

    def raw_control(self, prefix: str = "materialization") -> tuple[Path, Path]:
        fixture = self.fixtures["materializationFixture"]
        return (
            self.write(f"{prefix}-raw.json", fixture["raw"]),
            self.write(f"{prefix}-control.json", fixture["control"]),
        )

    def verifier_command(self, profile: Path, capture: Path, decision: Path, *, bootstrap: bool = False, prefix: str = "verify") -> list[str]:
        raw, control = self.raw_control(prefix)
        command = [sys.executable]
        if bootstrap:
            command.extend([str(BOOTSTRAP), str(VERIFIER)])
        else:
            command.append(str(VERIFIER))
        command.extend([str(profile), str(capture), str(decision), "--raw", str(raw), "--control", str(control)])
        return command

    def test_01_profile_pins_issue_floor_and_commodity_interface(self) -> None:
        self.assertEqual(self.profile["issueRef"], mod.ISSUE_REF)
        binding = self.profile["commodityBinding"]
        self.assertEqual(binding["admissionCommit"], mod.SOURCE_FLOOR_COMMIT)
        self.assertEqual(binding["admissionTree"], mod.SOURCE_FLOOR_TREE)
        self.assertEqual(binding["interface"], mod.INTERFACE)
        self.assertEqual(len(binding["productMembers"]), 7)

    def test_02_profile_closes_source_case_receipt_and_terminal_denominators(self) -> None:
        self.assertEqual(len(self.profile["sourceMembers"]), 10)
        self.assertEqual(tuple(self.profile["fixtureCaseIds"]), mod.CASE_IDS)
        self.assertEqual(tuple(self.profile["terminalStates"]), mod.TERMINALS)
        self.assertEqual(tuple(self.profile["observationReceiptKinds"]), mod.OBSERVATION_RECEIPT_KINDS)

    def test_03_campaign_has_one_prepared_one_observed_and_thirteen_holds(self) -> None:
        result = mod.campaign(self.profile, self.fixtures)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["caseCount"], 15)
        self.assertEqual(
            result["terminalCounts"],
            {
                "PREPARED_FOR_PHYSICAL_AUDITION": 1,
                "OBSERVED_ROUTE_CANDIDATE": 1,
                "HOLD": 13,
            },
        )
        self.assertFalse(result["actualSupplierQualified"])
        self.assertFalse(result["executionOccurred"])

    def test_04_complete_synthetic_capture_reaches_only_route_candidate(self) -> None:
        decision = self.decision(mod.CASE_IDS[0])
        self.assertEqual(decision["terminal"], "OBSERVED_ROUTE_CANDIDATE")
        self.assertEqual(decision["reasonCodes"], [])
        self.assertTrue(decision["syntheticConformanceOnly"])
        self.assertFalse(decision["actualSupplierQualified"])
        self.assertFalse(decision["supplierAdmissionReceiptPresent"])
        self.assertFalse(decision["executionOccurred"])

    def test_05_public_observation_remains_prepared_not_qualified(self) -> None:
        decision = self.decision(mod.CASE_IDS[1])
        self.assertEqual(decision["terminal"], "PREPARED_FOR_PHYSICAL_AUDITION")
        self.assertEqual(decision["reasonCodes"], ["PHYSICAL_AUDITION_NOT_EXECUTED"])
        self.assertFalse(decision["syntheticConformanceOnly"])
        self.assertFalse(decision["actualSupplierQualified"])

    def test_06_each_hostile_fixture_reaches_exact_hold_reason(self) -> None:
        for row in self.fixtures["cases"][2:]:
            with self.subTest(case_id=row["caseId"]):
                decision = mod.assess_capture(copy.deepcopy(row["capture"]), self.profile, case_id=row["caseId"])
                self.assertEqual(decision["terminal"], "HOLD")
                self.assertEqual(decision["reasonCodes"], row["expectedReasonCodes"])

    def test_07_late_instrumentation_refuses_even_with_complete_route(self) -> None:
        self.assertEqual(self.decision(mod.CASE_IDS[2])["reasonCodes"], ["INSTRUMENTATION_LATE"])

    def test_08_ui_memory_is_not_a_capacity_receipt(self) -> None:
        reasons = self.decision(mod.CASE_IDS[3])["reasonCodes"]
        self.assertIn("UI_ONLY_CAPACITY", reasons)
        self.assertIn("ARTIFACT_BINDING_MISSING", reasons)

    def test_09_duplicate_member_cannot_manufacture_capacity(self) -> None:
        self.assertEqual(self.decision(mod.CASE_IDS[4])["reasonCodes"], ["FORMATION_MEMBER_DUPLICATE"])

    def test_10_selected_candidate_pair_is_required(self) -> None:
        self.assertEqual(self.decision(mod.CASE_IDS[5])["reasonCodes"], ["SELECTED_CANDIDATE_PAIR_MISSING"])

    def test_11_activation_channel_must_be_ordered_and_reliable(self) -> None:
        self.assertEqual(self.decision(mod.CASE_IDS[6])["reasonCodes"], ["ACTIVATION_CHANNEL_NOT_ORDERED_RELIABLE"])

    def test_12_model_label_cannot_replace_artifact_identity(self) -> None:
        self.assertEqual(self.decision(mod.CASE_IDS[7])["reasonCodes"], ["MODEL_IDENTITY_MISMATCH"])

    def test_13_performance_requires_prompt_output_and_each_token_mark(self) -> None:
        self.assertEqual(self.decision(mod.CASE_IDS[8])["reasonCodes"], ["PERFORMANCE_DENOMINATOR_INCOMPLETE"])

    def test_14_member_drop_requires_control_and_terminal_observation(self) -> None:
        self.assertEqual(self.decision(mod.CASE_IDS[9])["reasonCodes"], ["DROP_TERMINAL_MISSING"])

    def test_15_public_projection_rejects_body_and_network_identity(self) -> None:
        self.assertEqual(self.decision(mod.CASE_IDS[10])["reasonCodes"], ["PUBLIC_PROJECTION_LEAK"])
        self.assertTrue(mod.public_leak({"nested": {"candidateAddress": "192.168.1.9"}}))
        self.assertTrue(mod.public_leak({"endpoint": "https://example.invalid/model"}))

    def test_16_observer_silence_cannot_prove_end_to_end_privacy(self) -> None:
        self.assertEqual(self.decision(mod.CASE_IDS[11])["reasonCodes"], ["PRIVACY_CLAIM_EXCEEDS_OBSERVER"])

    def test_17_work_unit_names_interface_and_never_supplier(self) -> None:
        complete = self.case(mod.CASE_IDS[0])["capture"]
        self.assertEqual(complete["workUnit"]["requiredInterface"], mod.INTERFACE)
        self.assertIsNone(complete["workUnit"]["supplierRef"])
        self.assertEqual(self.decision(mod.CASE_IDS[12])["reasonCodes"], ["TASK_SUPPLIER_PINNED"])

    def test_18_capture_limits_are_enforced_before_semantic_promotion(self) -> None:
        self.assertEqual(self.decision(mod.CASE_IDS[13])["reasonCodes"], ["CAPTURE_EVENT_CEILING_EXCEEDED"])

    def test_19_stored_receipt_is_rebuilt_not_trusted(self) -> None:
        self.assertEqual(self.decision(mod.CASE_IDS[14])["reasonCodes"], ["STORED_RECEIPT_MISMATCH"])
        complete = self.case(mod.CASE_IDS[0])["capture"]
        self.assertEqual(complete["storedReceiptDigest"], mod.observation_receipt_digest(complete))

    def test_20_capture_identity_excludes_only_stored_receipt_digest(self) -> None:
        complete = self.case(mod.CASE_IDS[0])["capture"]
        changed = copy.deepcopy(complete)
        changed["storedReceiptDigest"] = "sha256:" + "0" * 64
        self.assertEqual(mod.capture_digest(complete), mod.capture_digest(changed))
        changed["performance"]["lastTokenMonotonicMs"] += 1
        self.assertNotEqual(mod.capture_digest(complete), mod.capture_digest(changed))

    def test_21_generated_public_projection_is_body_free_and_closed(self) -> None:
        public = self.decision(mod.CASE_IDS[0])["publicProjection"]
        self.assertEqual(set(public), set(self.profile["publicProjectionAllowedKeys"]))
        self.assertFalse(mod.public_leak(public))
        self.assertFalse(public["actualSupplierQualified"])
        self.assertFalse(public["executionOccurred"])
        self.assertEqual((public["missionAuthority"], public["commandAuthority"]), ("none", "none"))

    def test_22_observer_core_and_probe_are_supplier_neutral(self) -> None:
        for path in (TOOL, PROBE, PROFILE):
            with self.subTest(path=path.name):
                self.assertNotIn("swarmllm", path.read_text(encoding="utf-8").lower())

    def test_23_probe_has_real_webgpu_webrtc_fetch_and_timing_instrumentation(self) -> None:
        source = PROBE.read_text(encoding="utf-8")
        for token in (
            "requestAdapter",
            "requestDevice",
            "RTCPeerConnection",
            "createDataChannel",
            "getStats",
            "WebSocket",
            "EventSource",
            "Cache",
            "indexedDB",
            "markModelArtifact",
            "markToken",
            "markDrop",
            "markEquivalence",
            "exportCapture",
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)
        self.assertNotIn("response.text(", source)
        self.assertNotIn("candidate.address", source)
        self.assertNotIn("localDescription.sdp", source)
        self.assertNotIn("remoteDescription.sdp", source)

    def test_24_probe_is_valid_javascript(self) -> None:
        result = subprocess.run(["node", "--check", str(PROBE)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"", b""))

    def test_25_cli_profile_fixture_campaign_assess_and_probe_digest(self) -> None:
        complete_path = self.write("capture.json", self.case(mod.CASE_IDS[0])["capture"])
        commands = (
            ["validate-profile", str(PROFILE)],
            ["validate-fixtures", str(PROFILE), str(FIXTURES)],
            ["campaign", str(PROFILE), str(FIXTURES)],
            ["assess", str(PROFILE), str(complete_path), "--case-id", mod.CASE_IDS[0]],
            ["probe-digest", str(PROBE)],
        )
        for args in commands:
            with self.subTest(command=args[0]):
                result = subprocess.run([sys.executable, str(TOOL), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
                self.assertEqual((result.returncode, result.stderr), (0, b""))
                self.assertIsInstance(json.loads(result.stdout.decode("utf-8")), dict)

    def test_26_independent_direct_verifier_reconstructs_complete_decision(self) -> None:
        row = self.case(mod.CASE_IDS[0])
        capture = self.write("capture.json", row["capture"])
        decision = self.write("decision.json", mod.assess_capture(row["capture"], self.profile, case_id=row["caseId"]))
        result = subprocess.run(
            self.verifier_command(PROFILE, capture, decision, prefix="direct"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual((result.returncode, result.stderr), (0, b""))
        verdict = json.loads(result.stdout.decode("utf-8"))
        self.assertEqual(verdict["status"], "PASS")
        self.assertFalse(verdict["bootstrapAuthenticated"])
        self.assertTrue(verdict["storedReceiptReconstructed"])
        self.assertTrue(verdict["publicProjectionReconstructed"])
        self.assertTrue(verdict["rawEvidenceReconstructed"])

    def test_27_bootstrap_executes_measured_verifier_from_foreign_directory(self) -> None:
        row = self.case(mod.CASE_IDS[0])
        capture = self.write("capture.json", row["capture"])
        decision = self.write("decision.json", mod.assess_capture(row["capture"], self.profile, case_id=row["caseId"]))
        foreign = self.work / "foreign"
        foreign.mkdir()
        result = subprocess.run(
            self.verifier_command(PROFILE, capture, decision, bootstrap=True, prefix="bootstrap"),
            cwd=foreign,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual((result.returncode, result.stderr), (0, b""))
        verdict = json.loads(result.stdout.decode("utf-8"))
        self.assertEqual(verdict["status"], "PASS")
        self.assertTrue(verdict["bootstrapAuthenticated"])
        self.assertTrue(verdict["storedVerifierMemberBound"])
        self.assertTrue(verdict["rawEvidenceReconstructed"])
        self.assertFalse(verdict["actualSupplierQualified"])

    def test_28_independent_verifier_rejects_stored_terminal_forgery(self) -> None:
        row = self.case(mod.CASE_IDS[0])
        capture = self.write("capture.json", row["capture"])
        decision_body = mod.assess_capture(row["capture"], self.profile, case_id=row["caseId"])
        decision_body["terminal"] = "PREPARED_FOR_PHYSICAL_AUDITION"
        decision = self.write("decision-forged.json", decision_body)
        result = subprocess.run(
            self.verifier_command(PROFILE, capture, decision, prefix="forgery"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout.decode("utf-8"))["code"], "TERMINAL_MISMATCH")

    def test_29_profile_mutation_and_fixture_expansion_are_refused(self) -> None:
        altered = copy.deepcopy(self.profile)
        altered["commodityBinding"]["admissionCommit"] = "0" * 40
        with self.assertRaises(mod.AuditionError) as context:
            mod.validate_profile(self.write("profile-mutated.json", altered))
        self.assertEqual(context.exception.code, "COMMODITY_BINDING_INVALID")
        fixtures = mod.load_object(FIXTURES)
        fixtures["cases"].append(copy.deepcopy(fixtures["cases"][0]))
        with self.assertRaises(mod.AuditionError) as context:
            mod.validate_fixture_catalog(self.write("fixtures-expanded.json", fixtures), self.profile)
        self.assertEqual(context.exception.code, "CASE_DENOMINATOR_INVALID")

    def test_30_source_set_measures_exact_ten_members(self) -> None:
        measured = mod.source_set(self.profile, REPOSITORY_ROOT)
        self.assertEqual(len(measured["members"]), 10)
        self.assertEqual([row["path"] for row in measured["members"]], self.profile["sourceMembers"])
        self.assertTrue(measured["sourceSetId"].startswith("axmauditionsource1_"))


    def test_31_profile_freezes_exact_predecessor_source_and_public_denominators(self) -> None:
        altered = copy.deepcopy(self.profile)
        altered["commodityBinding"]["productMembers"][0]["sha"] = "0" * 40
        with self.assertRaises(mod.AuditionError) as context:
            mod.validate_profile(self.write("profile-member-forged.json", altered))
        self.assertEqual(context.exception.code, "COMMODITY_MEMBER_DENOMINATOR_INVALID")

        altered = copy.deepcopy(self.profile)
        altered["sourceMembers"][0] = "invented/source.py"
        with self.assertRaises(mod.AuditionError) as context:
            mod.validate_profile(self.write("profile-source-denominator-forged.json", altered))
        self.assertEqual(context.exception.code, "SOURCE_MEMBER_DENOMINATOR_INVALID")

        altered = copy.deepcopy(self.profile)
        altered["publicProjectionAllowedKeys"].append("rawUrl")
        with self.assertRaises(mod.AuditionError) as context:
            mod.validate_profile(self.write("profile-public-denominator-forged.json", altered))
        self.assertEqual(context.exception.code, "PUBLIC_KEY_DENOMINATOR_INVALID")

    def test_32_exact_probe_bytes_are_required_independently_of_early_installation(self) -> None:
        capture = copy.deepcopy(self.case(mod.CASE_IDS[0])["capture"])
        capture["instrumentation"]["probeSha256"] = "sha256:" + "0" * 64
        capture["storedReceiptDigest"] = mod.observation_receipt_digest(capture)
        decision = mod.assess_capture(capture, self.profile)
        self.assertEqual(decision["terminal"], "HOLD")
        self.assertEqual(decision["reasonCodes"], ["PROBE_ARTIFACT_MISMATCH"])
        self.assertEqual(
            "sha256:" + __import__("hashlib").sha256(PROBE.read_bytes()).hexdigest(),
            mod.PROBE_SHA256_REF,
        )

    def test_33_model_artifact_total_must_equal_composite_route_capacity(self) -> None:
        capture = copy.deepcopy(self.case(mod.CASE_IDS[0])["capture"])
        capture["formation"]["modelCapacityBytes"] += 1
        capture["storedReceiptDigest"] = mod.observation_receipt_digest(capture)
        decision = mod.assess_capture(capture, self.profile)
        self.assertEqual(decision["terminal"], "HOLD")
        self.assertEqual(decision["reasonCodes"], ["MODEL_IDENTITY_MISMATCH"])

    def test_34_activation_channel_must_carry_observed_bytes(self) -> None:
        capture = copy.deepcopy(self.case(mod.CASE_IDS[0])["capture"])
        channel = capture["transport"]["activationChannels"][0]
        channel["bytesSent"] = 0
        channel["bytesReceived"] = 0
        capture["storedReceiptDigest"] = mod.observation_receipt_digest(capture)
        decision = mod.assess_capture(capture, self.profile)
        self.assertEqual(decision["terminal"], "HOLD")
        self.assertEqual(decision["reasonCodes"], ["ACTIVATION_CHANNEL_NOT_ORDERED_RELIABLE"])

    def test_35_negative_capture_limits_are_structurally_refused(self) -> None:
        capture = copy.deepcopy(self.case(mod.CASE_IDS[0])["capture"])
        capture["limits"]["events"] = -1
        with self.assertRaises(mod.AuditionError) as context:
            mod.assess_capture(capture, self.profile)
        self.assertEqual(context.exception.code, "CAPTURE_LIMIT_INVALID")

    def test_36_independent_verifier_freezes_profile_and_structures_malformed_input(self) -> None:
        row = self.case(mod.CASE_IDS[0])
        capture = self.write("capture-verifier-profile.json", row["capture"])
        decision = self.write("decision-verifier-profile.json", mod.assess_capture(row["capture"], self.profile, case_id=row["caseId"]))
        altered = copy.deepcopy(self.profile)
        altered["commodityBinding"]["productMembers"][0]["sha"] = "0" * 40
        altered_profile = self.write("profile-verifier-forged.json", altered)
        result = subprocess.run(
            self.verifier_command(altered_profile, capture, decision, prefix="profile-forged"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual((result.returncode, result.stderr), (2, b""))
        self.assertEqual(json.loads(result.stdout.decode("utf-8"))["code"], "COMMODITY_MEMBER_DENOMINATOR_INVALID")

        malformed = copy.deepcopy(row["capture"])
        malformed.pop("transport")
        malformed_path = self.write("capture-malformed.json", malformed)
        result = subprocess.run(
            self.verifier_command(PROFILE, malformed_path, decision, prefix="malformed"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual((result.returncode, result.stderr), (2, b""))
        self.assertEqual(json.loads(result.stdout.decode("utf-8"))["code"], "RAW_MATERIALIZATION_MISMATCH")


    def test_37_raw_probe_and_control_materialize_exact_complete_capture(self) -> None:
        fixture = self.fixtures["materializationFixture"]
        capture, receipt = mod.materialize_probe_capture(
            copy.deepcopy(fixture["raw"]),
            copy.deepcopy(fixture["control"]),
            self.profile,
        )
        self.assertEqual(capture, self.case(mod.CASE_IDS[0])["capture"])
        self.assertEqual(receipt, fixture["expectedReceipt"])
        self.assertEqual(capture["rawEvidenceRef"], mod.sha256_ref(fixture["raw"]))
        self.assertEqual(capture["controlEvidenceRef"], mod.sha256_ref(fixture["control"]))

    def test_38_raw_summaries_cannot_disagree_with_event_ledger(self) -> None:
        fixture = copy.deepcopy(self.fixtures["materializationFixture"])
        fixture["raw"]["summaries"]["memberCount"] += 1
        with self.assertRaises(mod.AuditionError) as context:
            mod.materialize_probe_capture(fixture["raw"], fixture["control"], self.profile)
        self.assertEqual(context.exception.code, "RAW_SUMMARY_COUNT_MISMATCH")

    def test_39_normalized_capture_cannot_escape_raw_event_mutation(self) -> None:
        row = self.case(mod.CASE_IDS[0])
        capture = self.write("capture-raw-mutation.json", row["capture"])
        decision = self.write("decision-raw-mutation.json", mod.assess_capture(row["capture"], self.profile, case_id=row["caseId"]))
        fixture = copy.deepcopy(self.fixtures["materializationFixture"])
        for event in fixture["raw"]["events"]:
            if event["type"] == "rtc-data-channel-send":
                event["bytes"] += 1
                break
        fixture["raw"]["summaries"] = copy.deepcopy(self.fixtures["materializationFixture"]["raw"]["summaries"])
        # The send event is not represented in summaries, so the raw object remains structurally valid.
        raw = self.write("raw-mutated.json", fixture["raw"])
        control = self.write("control-raw-mutation.json", fixture["control"])
        result = subprocess.run(
            [sys.executable, str(VERIFIER), str(PROFILE), str(capture), str(decision), "--raw", str(raw), "--control", str(control)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual((result.returncode, result.stderr), (2, b""))
        self.assertEqual(json.loads(result.stdout.decode("utf-8"))["code"], "RAW_MATERIALIZATION_MISMATCH")

    def test_40_raw_probe_capture_rejects_body_and_network_identity(self) -> None:
        fixture = copy.deepcopy(self.fixtures["materializationFixture"])
        fixture["raw"]["events"][0]["promptText"] = "private"
        with self.assertRaises(mod.AuditionError) as context:
            mod.materialize_probe_capture(fixture["raw"], fixture["control"], self.profile)
        self.assertEqual(context.exception.code, "RAW_CAPTURE_BODY_OR_NETWORK_IDENTITY_LEAK")

    def test_41_probe_exposes_complete_controller_marks_and_random_opaque_ids(self) -> None:
        source = PROBE.read_text(encoding="utf-8")
        for token in (
            "crypto.getRandomValues",
            "markAvailability",
            "markAdapterArtifact",
            "markFormation",
            "markModelManifest",
            "markPerformanceStart",
            "markObservationReceipt",
        ):
            self.assertIn(token, source)
        self.assertNotIn("0x811c9dc5", source)

    def test_42_cli_materialization_and_raw_authenticated_bootstrap(self) -> None:
        raw, control = self.raw_control("cli-materialize")
        capture = self.work / "cli-materialized-capture.json"
        receipt = self.work / "cli-materialization-receipt.json"
        result = subprocess.run(
            [sys.executable, str(TOOL), "materialize", str(PROFILE), str(raw), str(control), "--out", str(capture), "--receipt-out", str(receipt)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual((result.returncode, result.stderr), (0, b""))
        self.assertEqual(capture.read_bytes(), result.stdout)
        materialized = json.loads(capture.read_text(encoding="utf-8"))
        decision = self.write("cli-materialized-decision.json", mod.assess_capture(materialized, self.profile))
        result = subprocess.run(
            [sys.executable, str(BOOTSTRAP), str(VERIFIER), str(PROFILE), str(capture), str(decision), "--raw", str(raw), "--control", str(control)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual((result.returncode, result.stderr), (0, b""))
        verdict = json.loads(result.stdout.decode("utf-8"))
        self.assertTrue(verdict["bootstrapAuthenticated"])
        self.assertTrue(verdict["rawEvidenceReconstructed"])
        self.assertEqual(json.loads(receipt.read_text(encoding="utf-8"))["status"], "PASS")


    def test_43_raw_encoded_byte_count_is_independently_reconstructed(self) -> None:
        fixture = copy.deepcopy(self.fixtures["materializationFixture"])
        fixture["raw"]["observed"]["encodedBytes"] -= 1
        with self.assertRaises(mod.AuditionError) as context:
            mod.materialize_probe_capture(fixture["raw"], fixture["control"], self.profile)
        self.assertEqual(context.exception.code, "RAW_ENCODED_BYTES_MISMATCH")

    def test_44_unknown_raw_event_type_is_refused(self) -> None:
        fixture = copy.deepcopy(self.fixtures["materializationFixture"])
        row = copy.deepcopy(fixture["raw"]["events"][-1])
        row["type"] = "supplier-private-magic"
        row["monotonicMs"] += 1
        fixture["raw"]["events"].append(row)
        fixture["raw"]["observed"]["eventCount"] += 1
        fixture["raw"]["observed"]["encodedBytes"] += len(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        )
        with self.assertRaises(mod.AuditionError) as context:
            mod.materialize_probe_capture(fixture["raw"], fixture["control"], self.profile)
        self.assertEqual(context.exception.code, "RAW_EVENT_TYPE_UNKNOWN")



    def test_45_public_capture_shape_is_independently_refused(self) -> None:
        row = self.case(mod.CASE_IDS[1])
        malformed = copy.deepcopy(row["capture"])
        malformed["supplierAdmissionReceipt"] = "supplier-self-assertion"
        capture = self.write("public-capture-shape-invalid.json", malformed)
        forged = copy.deepcopy(mod.assess_capture(row["capture"], self.profile, case_id=row["caseId"]))
        forged["captureDigest"] = mod.capture_digest(malformed)
        forged["observationReceiptDigest"] = mod.observation_receipt_digest(malformed)
        forged["publicProjection"]["captureDigest"] = forged["captureDigest"]
        forged["publicProjection"]["observationReceiptDigest"] = forged["observationReceiptDigest"]
        decision = self.write("public-capture-shape-invalid-decision.json", forged)
        result = subprocess.run(
            [sys.executable, str(VERIFIER), str(PROFILE), str(capture), str(decision)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual((result.returncode, result.stderr), (2, b""))
        self.assertEqual(json.loads(result.stdout.decode("utf-8"))["code"], "SUPPLIER_ADMISSION_RECEIPT_INVALID")



    def test_46_workflow_has_explicit_os_coordinate_matrix_and_no_empty_loop(self) -> None:
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("ubuntu-latest", source)
        self.assertIn("windows-latest", source)
        self.assertIn("coordinate: ${{ fromJSON(github.event_name == 'pull_request'", source)
        self.assertIn('["head","merge"]', source)
        self.assertNotIn("while IFS=", source)
        self.assertNotIn("while read", source)
        self.assertIn('grep -F "Ran 54 tests"', source)
        self.assertIn('grep -Fx "OK"', source)

    def test_47_workflow_materializes_exact_source_and_predecessor_git_blobs(self) -> None:
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('profile["sourceMembers"]', source)
        self.assertIn('["git", "cat-file", "blob", f"{ref}:{relative}"]', source)
        self.assertIn('["git", "rev-parse", f"{commit}:{member[\'path\']}"]', source)
        self.assertIn("seven-member commodity predecessor is exact", source)
        for relative in self.profile["sourceMembers"]:
            self.assertGreaterEqual(source.count(relative), 2, relative)

    def test_48_workflow_executes_campaign_materialization_and_both_verifiers(self) -> None:
        source = WORKFLOW.read_text(encoding="utf-8")
        for token in (
            'campaign "$PROFILE" "$FIXTURES"',
            'materialize "$PROFILE"',
            "verify_axm_head_browser_distributed_inference_audition.py",
            "verify_axm_head_browser_distributed_inference_audition_bootstrap.py",
            'receipt.get("rawEvidenceReconstructed") is not True',
            '"PREPARED_FOR_PHYSICAL_AUDITION": 1',
            '"OBSERVED_ROUTE_CANDIDATE": 1',
            '"HOLD": 13',
        ):
            self.assertIn(token, source)

    def test_49_workflow_compare_is_event_truthful_and_requires_all_receipt_sets(self) -> None:
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("expected_sets = 4 if is_pull_request else 2", source)
        self.assertIn('"coordinateByteIdentity": True', source)
        self.assertIn('"headMergeByteIdentity": True if is_pull_request else None', source)
        self.assertIn('"source-set.json"', source)
        self.assertIn('"complete-bootstrap-verdict.json"', source)
        self.assertIn("needs: qualify", source)

    def test_50_workflow_is_read_only_additive_and_never_launches_a_browser(self) -> None:
        source = WORKFLOW.read_text(encoding="utf-8")
        lowered = source.lower()
        self.assertIn("permissions:\n  contents: read", source)
        self.assertNotIn("contents: write", lowered)
        self.assertNotIn("git push", lowered)
        self.assertIn('if not status.startswith("A\\t")', source)
        for token in ("playwright", "selenium", "chromedriver", "msedge.exe", "chrome.exe", "firefox.exe"):
            self.assertNotIn(token, lowered)

    def test_52_job_environment_does_not_use_runner_context_before_assignment(self) -> None:
        source = WORKFLOW.read_text(encoding="utf-8")
        job_env = source.split("    env:\n", 1)[1].split("\n\n    steps:\n", 1)[0]
        self.assertIn('PYTHONDWRITEBYTECODE: "1"', job_env)
        self.assertNotIn("$" + "{{ runner.", job_env)
        self.assertNotIn("PYTHONPYCACHEPREFIX", job_env)

    def test_53_runner_paths_enter_python_as_arguments_not_source_literals(self) -> None:
        source = WORKFLOW.read_text(encoding="utf-8")
        expression_open = "$" + "{{"
        self.assertIn(
            "RECEIPT_ROOT: " + expression_open + " runner.temp }}/axm-browser-audition", source
        )
        self.assertIn('python - "$RECEIPT_ROOT/campaign.json" <<\'PY\'', source)
        self.assertIn(
            'campaign = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))', source
        )
        self.assertNotIn('Path("' + expression_open + " runner.temp }}", source)

    def test_54_source_coordinate_accepts_exact_members_and_refuses_external_drift(self) -> None:
        source = WORKFLOW.read_text(encoding="utf-8")
        for token in (
            'f"{expected_sha}:{profile_relative}"',
            'source_members = tuple(profile["sourceMembers"])',
            'f"{expected_sha}:{relative}"',
            '*[f":(exclude){relative}" for relative in source_members]',
            '"sourceMembersExact": source_members_exact',
            '"outsideSourceMembersClean": outside_source_members_clean',
            'if body["status"] != "PASS":',
        ):
            self.assertIn(token, source)
        self.assertNotIn('"clean": subprocess.check_output(["git", "status"', source)
        self.assertNotIn('body["clean"] is not True', source)

        source_members = tuple(self.profile["sourceMembers"])
        for relative in source_members:
            expected = subprocess.check_output(
                ["git", "cat-file", "blob", f"HEAD:{relative}"], cwd=REPOSITORY_ROOT
            )
            self.assertEqual((REPOSITORY_ROOT / relative).read_bytes(), expected)

        status_command = [
            "git",
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            ".",
            *[f":(exclude){relative}" for relative in source_members],
        ]
        self.assertEqual(
            subprocess.check_output(status_command, cwd=REPOSITORY_ROOT, text=True), ""
        )
        drift = REPOSITORY_ROOT / f"AXM_BROWSER_AUDITION_OUTSIDE_DRIFT_{os.getpid()}"
        try:
            drift.write_text("external drift\n", encoding="utf-8", newline="\n")
            observed = subprocess.check_output(
                status_command, cwd=REPOSITORY_ROOT, text=True
            )
            self.assertIn(drift.name, observed)
        finally:
            drift.unlink(missing_ok=True)
        self.assertEqual(
            subprocess.check_output(status_command, cwd=REPOSITORY_ROOT, text=True), ""
        )


    def test_51_bootstrap_resolves_relative_coordinates_before_foreign_execution(self) -> None:
        raw, control = self.raw_control("relative-bootstrap")
        row = self.case(mod.CASE_IDS[0])
        capture = self.write("relative-bootstrap-capture.json", row["capture"])
        decision = self.write(
            "relative-bootstrap-decision.json",
            mod.assess_capture(row["capture"], self.profile, case_id=row["caseId"]),
        )
        foreign = tempfile.TemporaryDirectory(
            prefix="browser-relative-caller-", dir=REPOSITORY_ROOT.parent
        )
        self.addCleanup(foreign.cleanup)
        foreign_root = Path(foreign.name)
        material = foreign_root / "material"
        material.mkdir()
        caller = foreign_root / "caller"
        caller.mkdir()

        def stage(path: Path) -> Path:
            staged = material / path.name
            staged.write_bytes(path.read_bytes())
            return staged

        raw = stage(raw)
        control = stage(control)
        capture = stage(capture)
        decision = stage(decision)

        def relative(path: Path) -> str:
            return os.path.relpath(path, caller)

        output = caller / "relative-verdict.json"
        result = subprocess.run(
            [
                sys.executable,
                str(BOOTSTRAP),
                relative(VERIFIER),
                relative(PROFILE),
                relative(capture),
                relative(decision),
                "--raw",
                relative(raw),
                "--control",
                relative(control),
                "--out",
                output.name,
            ],
            cwd=caller,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual((result.returncode, result.stderr), (0, b""))
        self.assertTrue(output.is_file())
        self.assertEqual(output.read_bytes(), result.stdout)
        verdict = json.loads(result.stdout.decode("utf-8"))
        self.assertEqual(verdict["status"], "PASS")
        self.assertTrue(verdict["bootstrapAuthenticated"])
        self.assertTrue(verdict["rawEvidenceReconstructed"])


if __name__ == "__main__":
    unittest.main()
