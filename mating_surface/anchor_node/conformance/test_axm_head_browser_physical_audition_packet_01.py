from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPOSITORY_ROOT = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

import axm_head_browser_physical_audition_packet_01 as mod
import verify_axm_head_browser_physical_audition_packet_01 as verifier

PROFILE = ROOT / "axm-head-browser-physical-audition-packet-profile-01.json"
CONTROLLER_TEMPLATE = ROOT / "axm-head-browser-physical-audition-controller-template-01.json"
POWERSHELL = ROOT / "axm-head-browser-physical-audition-packet-01.ps1"
TOOL = ROOT / "axm_head_browser_physical_audition_packet_01.py"
DIRECT = ROOT / "verify_axm_head_browser_physical_audition_packet_01.py"
BOOTSTRAP = ROOT / "verify_axm_head_browser_physical_audition_packet_01_bootstrap.py"
FIXTURES = ROOT / "fixtures" / "axm-head-browser-physical-audition-packet-cases-01.json"
WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "axm-head-browser-physical-audition-packet-01.yml"
DOCUMENTATION = ROOT / "AXM-HEAD-BROWSER-PHYSICAL-AUDITION-PACKET-01.md"
NOW_MS = 2_000_000_000_000


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def make_directory_link(link: Path, target: Path) -> None:
    if os.name == "nt":
        result = subprocess.run(
            ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            raise OSError(result.stderr.decode("utf-8", errors="replace") or result.stdout.decode("utf-8", errors="replace"))
    else:
        link.symlink_to(target, target_is_directory=True)


def rewrite_kit_manifest(kit: Path, profile: dict) -> None:
    files = {
        path.relative_to(kit).as_posix(): path.read_bytes()
        for path in kit.rglob("*")
        if path.is_file() and path.name != "kit-manifest.json"
    }
    manifest = mod.kit_manifest_for(files, mod.source_binding_id(profile))
    (kit / "kit-manifest.json").write_bytes(mod.pretty_bytes(manifest))


class BrowserPhysicalAuditionPacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile = mod.validate_profile(PROFILE)
        cls.catalog = mod.load_object(FIXTURES)
        cls.fixtures = mod.validate_fixture_catalog(FIXTURES, cls.profile)

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(
            prefix="axm-browser-physical-packet-test-",
            dir=REPOSITORY_ROOT.parent,
        )
        self.work = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def case(self, case_id: str) -> dict:
        return next(row for row in self.fixtures["cases"] if row["caseId"] == case_id)

    def base(self, name: str) -> dict:
        return copy.deepcopy(self.catalog["bases"][name])

    def write_packet(self, case_id: str, name: str = "packet") -> Path:
        packet = self.work / name
        mod.write_fixture_packet(self.case(case_id), packet)
        return packet

    def assemble(self, case_id: str, name: str = "packet") -> tuple[Path, dict]:
        packet = self.write_packet(case_id, name)
        decision = mod.assemble_packet(self.profile, packet, now_ms=NOW_MS, base=ROOT)
        return packet, decision

    def confirmation_for(self, packet_decision: dict, **changes: object) -> dict:
        value = {
            "schema": mod.CONFIRMATION_SCHEMA,
            "actorClass": "named-human",
            "actorEvidenceRef": "sha256:" + "c" * 64,
            "decision": "CONFIRM_OBSERVED_ROUTE_CANDIDATE",
            "evidenceRoot": packet_decision["packetEvidenceRoot"],
            "seatCaptureDigests": [row["captureDigest"] for row in packet_decision["seatReceipts"]],
            "physicalMemberEvidenceRefs": packet_decision["physicalMemberEvidenceRefs"],
            "issuedAtUnixMs": NOW_MS - 1_000,
            "expiresAtUnixMs": NOW_MS + 60_000,
            "authority": "none",
            "confirmationId": None,
        }
        value.update(changes)
        value["confirmationId"] = mod.confirmation_id(value)
        return value

    def assert_claim_boundary(self, value: dict) -> None:
        self.assertFalse(value["actualSupplierQualified"])
        self.assertFalse(value["supplierAdmissionReceiptPresent"])
        self.assertFalse(value["physicalEstateQualified"])
        for key in (
            "missionAuthority",
            "commandAuthority",
            "targetingAuthority",
            "engagementAuthority",
            "effectorAuthority",
            "weaponsAuthority",
        ):
            self.assertEqual(value[key], "none")

    def test_01_profile_pins_issue_floor_interface_and_exact_source_denominator(self) -> None:
        self.assertEqual(self.profile["issueRef"], mod.ISSUE_REF)
        binding = self.profile["admittedAudition"]
        self.assertEqual(binding["admissionCommit"], mod.ADMITTED_COMMIT)
        self.assertEqual(binding["admissionTree"], mod.ADMITTED_TREE)
        self.assertEqual(binding["candidateCommit"], mod.ADMITTED_CANDIDATE_COMMIT)
        self.assertEqual(binding["interface"], mod.INTERFACE)
        self.assertEqual(binding["probeSha256"], mod.PROBE_SHA256_REF)
        self.assertEqual(tuple(self.profile["sourceMembers"]), mod.SOURCE_MEMBERS)
        self.assertEqual(len(self.profile["sourceMembers"]), 10)

    def test_02_profile_closes_commands_terminals_seats_and_public_keys(self) -> None:
        self.assertEqual(tuple(self.profile["commands"]), mod.COMMANDS)
        self.assertEqual(tuple(self.profile["terminalStates"]), mod.TERMINALS)
        self.assertEqual(self.profile["seatCount"], 2)
        self.assertEqual(self.profile["physicalMemberEvidenceCount"], 2)
        self.assertEqual(tuple(self.profile["publicProjectionAllowedKeys"]), mod.PUBLIC_KEYS)

    def test_03_source_bindings_are_length_and_digest_bound_with_closed_names(self) -> None:
        self.assertEqual(
            tuple(Path(row["path"]).name for row in self.profile["kitSourceBindings"]),
            mod.KIT_DEPENDENCIES,
        )
        self.assertEqual(
            tuple(Path(row["path"]).name for row in self.profile["packetSourceBindings"]),
            (
                "axm-head-browser-physical-audition-controller-template-01.json",
                "axm-head-browser-physical-audition-packet-01.ps1",
                "axm_head_browser_physical_audition_packet_01.py",
                "verify_axm_head_browser_physical_audition_packet_01.py",
                "verify_axm_head_browser_physical_audition_packet_01_bootstrap.py",
            ),
        )
        for key in ("kitSourceBindings", "packetSourceBindings"):
            for row in self.profile[key]:
                data = (ROOT / row["path"]).read_bytes()
                self.assertEqual(row["bytes"], len(data))
                self.assertEqual(row["sha256"], mod.sha256_ref(data))

    def test_04_source_binding_identity_covers_packet_runtime_bytes(self) -> None:
        original = mod.source_binding_id(self.profile)
        altered = copy.deepcopy(self.profile)
        altered["packetSourceBindings"][0]["sha256"] = "sha256:" + "0" * 64
        self.assertNotEqual(original, mod.source_binding_id(altered))
        self.assertTrue(original.startswith("axmbrowserphysicalpacketsource_"))

    def test_05_fixture_denominator_and_terminal_counts_are_closed(self) -> None:
        self.assertEqual(len(self.fixtures["cases"]), 23)
        self.assertEqual(self.fixtures["terminalCounts"], self.profile["fixtureTerminalCounts"])
        self.assertEqual(
            self.fixtures["terminalCounts"],
            {
                "PREPARED_NOT_EXECUTED": 1,
                "READY_FOR_NAMED_HUMAN": 1,
                "OBSERVED_ROUTE_CANDIDATE": 1,
                "HOLD": 15,
                "REFUSED": 5,
            },
        )

    def test_06_campaign_is_source_only_and_promotes_no_execution_or_authority(self) -> None:
        result = mod.campaign(self.profile, self.fixtures)
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["physicalExecutionObserved"])
        self.assert_claim_boundary(result)

    def test_07_synthetic_route_candidate_cannot_claim_physical_execution(self) -> None:
        row = self.case("synthetic-complete-route")
        self.assertEqual(row["terminal"], "OBSERVED_ROUTE_CANDIDATE")
        decision, _ = mod.reconstruct_packet(
            self.profile,
            row["packet"]["seats"],
            None,
            now_ms=NOW_MS,
            base=ROOT,
        )
        self.assertTrue(decision["syntheticConformanceOnly"])
        self.assertFalse(decision["physicalExecutionObserved"])
        self.assertFalse(decision["namedHumanConfirmed"])
        self.assert_claim_boundary(decision)

    def test_08_empty_packet_is_prepared_not_executed(self) -> None:
        decision, rows = mod.reconstruct_packet(self.profile, [], None, now_ms=NOW_MS, base=ROOT)
        self.assertEqual(decision["terminal"], "PREPARED_NOT_EXECUTED")
        self.assertEqual(decision["seatCount"], 0)
        self.assertEqual(rows, [])
        self.assertFalse(decision["physicalExecutionObserved"])

    def test_09_complete_physical_pair_stops_for_named_human(self) -> None:
        packet = self.base("physicalComplete")
        decision, _ = mod.reconstruct_packet(
            self.profile,
            packet["seats"],
            None,
            now_ms=NOW_MS,
            base=ROOT,
        )
        self.assertEqual(decision["terminal"], "READY_FOR_NAMED_HUMAN")
        self.assertEqual(decision["reasonCodes"], ["NAMED_HUMAN_CONFIRMATION_MISSING"])
        self.assertFalse(decision["physicalExecutionObserved"])
        self.assertFalse(decision["namedHumanConfirmed"])

    def test_10_separately_supplied_valid_confirmation_opens_only_route_terminal(self) -> None:
        packet = self.base("physicalComplete")
        ready, _ = mod.reconstruct_packet(self.profile, packet["seats"], None, now_ms=NOW_MS, base=ROOT)
        confirmation = self.confirmation_for(ready)
        decision, _ = mod.reconstruct_packet(
            self.profile,
            packet["seats"],
            confirmation,
            now_ms=NOW_MS,
            base=ROOT,
        )
        self.assertEqual(decision["terminal"], "OBSERVED_ROUTE_CANDIDATE")
        self.assertEqual(decision["reasonCodes"], [])
        self.assertTrue(decision["namedHumanConfirmed"])
        self.assertTrue(decision["physicalExecutionObserved"])
        self.assertFalse(decision["syntheticConformanceOnly"])
        self.assertEqual(decision["namedHumanActorEvidenceRef"], confirmation["actorEvidenceRef"])
        self.assert_claim_boundary(decision)

    def test_11_confirmation_content_id_forgery_is_refused(self) -> None:
        packet = self.base("physicalComplete")
        ready, _ = mod.reconstruct_packet(self.profile, packet["seats"], None, now_ms=NOW_MS, base=ROOT)
        confirmation = self.confirmation_for(ready)
        confirmation["confirmationId"] = "axmbrowserhumanconfirmation_" + "0" * 64
        with self.assertRaises(mod.PacketError) as context:
            mod.reconstruct_packet(self.profile, packet["seats"], confirmation, now_ms=NOW_MS, base=ROOT)
        self.assertEqual(context.exception.code, "CONFIRMATION_ID_MISMATCH")

    def test_12_named_human_actor_evidence_is_required_and_cannot_reuse_packet_receipts(self) -> None:
        packet = self.base("physicalComplete")
        ready, _ = mod.reconstruct_packet(self.profile, packet["seats"], None, now_ms=NOW_MS, base=ROOT)
        confirmation = self.confirmation_for(ready, actorEvidenceRef="not-a-digest")
        with self.assertRaises(mod.PacketError) as context:
            mod.reconstruct_packet(self.profile, packet["seats"], confirmation, now_ms=NOW_MS, base=ROOT)
        self.assertEqual(context.exception.code, "CONFIRMATION_ACTOR_EVIDENCE_INVALID")
        confirmation = self.confirmation_for(ready, actorEvidenceRef=ready["physicalMemberEvidenceRefs"][0])
        with self.assertRaises(mod.PacketError) as context:
            mod.reconstruct_packet(self.profile, packet["seats"], confirmation, now_ms=NOW_MS, base=ROOT)
        self.assertEqual(context.exception.code, "CONFIRMATION_ACTOR_EVIDENCE_REUSED")

    def test_13_confirmation_must_bind_exact_packet_evidence_root(self) -> None:
        packet = self.base("physicalComplete")
        ready, _ = mod.reconstruct_packet(self.profile, packet["seats"], None, now_ms=NOW_MS, base=ROOT)
        confirmation = self.confirmation_for(ready, evidenceRoot="sha256:" + "0" * 64)
        with self.assertRaises(mod.PacketError) as context:
            mod.reconstruct_packet(self.profile, packet["seats"], confirmation, now_ms=NOW_MS, base=ROOT)
        self.assertEqual(context.exception.code, "CONFIRMATION_EVIDENCE_ROOT_MISMATCH")

    def test_14_confirmation_must_bind_both_exact_seat_capture_digests(self) -> None:
        packet = self.base("physicalComplete")
        ready, _ = mod.reconstruct_packet(self.profile, packet["seats"], None, now_ms=NOW_MS, base=ROOT)
        digests = list(row["captureDigest"] for row in ready["seatReceipts"])
        digests[1] = "sha256:" + "0" * 64
        confirmation = self.confirmation_for(ready, seatCaptureDigests=digests)
        with self.assertRaises(mod.PacketError) as context:
            mod.reconstruct_packet(self.profile, packet["seats"], confirmation, now_ms=NOW_MS, base=ROOT)
        self.assertEqual(context.exception.code, "CONFIRMATION_SEAT_BINDING_MISMATCH")

    def test_15_confirmation_must_bind_the_same_two_physical_member_evidence_refs(self) -> None:
        packet = self.base("physicalComplete")
        ready, _ = mod.reconstruct_packet(self.profile, packet["seats"], None, now_ms=NOW_MS, base=ROOT)
        confirmation = self.confirmation_for(ready, physicalMemberEvidenceRefs=["sha256:" + "d" * 64, "sha256:" + "e" * 64])
        with self.assertRaises(mod.PacketError) as context:
            mod.reconstruct_packet(self.profile, packet["seats"], confirmation, now_ms=NOW_MS, base=ROOT)
        self.assertEqual(context.exception.code, "CONFIRMATION_MEMBER_BINDING_MISMATCH")

    def test_16_confirmation_time_window_is_current_bounded_and_fail_closed(self) -> None:
        packet = self.base("physicalComplete")
        ready, _ = mod.reconstruct_packet(self.profile, packet["seats"], None, now_ms=NOW_MS, base=ROOT)
        rows = (
            (self.confirmation_for(ready, issuedAtUnixMs=NOW_MS + 300_001), "CONFIRMATION_NOT_CURRENT"),
            (self.confirmation_for(ready, expiresAtUnixMs=NOW_MS - 1), "CONFIRMATION_EXPIRED"),
            (self.confirmation_for(ready, issuedAtUnixMs=NOW_MS - 1, expiresAtUnixMs=NOW_MS + 86_400_001), "CONFIRMATION_VALIDITY_INVALID"),
        )
        for confirmation, code in rows:
            with self.subTest(code=code), self.assertRaises(mod.PacketError) as context:
                mod.reconstruct_packet(self.profile, packet["seats"], confirmation, now_ms=NOW_MS, base=ROOT)
            self.assertEqual(context.exception.code, code)

    def test_17_confirmation_actor_decision_and_authority_are_closed(self) -> None:
        packet = self.base("physicalComplete")
        ready, _ = mod.reconstruct_packet(self.profile, packet["seats"], None, now_ms=NOW_MS, base=ROOT)
        rows = (
            (self.confirmation_for(ready, actorClass="machine"), "CONFIRMATION_ACTOR_INVALID"),
            (self.confirmation_for(ready, decision="QUALIFY_SUPPLIER"), "CONFIRMATION_DECISION_INVALID"),
            (self.confirmation_for(ready, authority="command"), "AUTHORITY_PROMOTED"),
        )
        for confirmation, code in rows:
            with self.subTest(code=code), self.assertRaises(mod.PacketError) as context:
                mod.reconstruct_packet(self.profile, packet["seats"], confirmation, now_ms=NOW_MS, base=ROOT)
            self.assertEqual(context.exception.code, code)

    def test_18_confirmation_is_refused_before_evidence_or_for_synthetic_packet(self) -> None:
        with self.assertRaises(mod.PacketError) as context:
            mod.reconstruct_packet(self.profile, [], {"schema": "forged"}, now_ms=NOW_MS, base=ROOT)
        self.assertEqual(context.exception.code, "CONFIRMATION_NOT_APPLICABLE")
        packet = self.base("syntheticComplete")
        with self.assertRaises(mod.PacketError) as context:
            mod.reconstruct_packet(self.profile, packet["seats"], {"schema": "forged"}, now_ms=NOW_MS, base=ROOT)
        self.assertEqual(context.exception.code, "CONFIRMATION_NOT_APPLICABLE")

    def test_19_every_hostile_fixture_reaches_its_exact_terminal_and_reason_order(self) -> None:
        for expected in self.catalog["cases"]:
            observed = self.case(expected["caseId"])
            with self.subTest(case=expected["caseId"]):
                self.assertEqual(observed["terminal"], expected["expectedTerminal"])
                self.assertEqual(observed["reasonCodes"], expected["expectedReasonCodes"])

    def test_20_one_seat_substitution_holds(self) -> None:
        self.assertEqual(self.case("hold-one-seat-substitution")["reasonCodes"], ["ONE_SEAT_SUBSTITUTION"])

    def test_21_seat_replay_holds(self) -> None:
        self.assertEqual(self.case("hold-seat-replay")["reasonCodes"], ["SEAT_REPLAYED"])

    def test_22_duplicate_physical_member_evidence_cannot_manufacture_capacity(self) -> None:
        self.assertEqual(self.case("hold-duplicate-physical-member-evidence")["reasonCodes"], ["DUPLICATE_PHYSICAL_MEMBER_EVIDENCE"])

    def test_23_cross_seat_member_set_disagreement_holds(self) -> None:
        self.assertIn("CROSS_SEAT_MEMBER_SET_DISAGREEMENT", self.case("hold-cross-seat-member-set-disagreement")["reasonCodes"])

    def test_24_late_instrumentation_holds_the_seat(self) -> None:
        self.assertEqual(self.case("hold-late-instrumentation")["reasonCodes"], ["SEAT_CAPTURE_HELD"])

    def test_25_supplier_pinned_work_unit_holds_the_seat(self) -> None:
        self.assertEqual(self.case("hold-supplier-pinned-work-unit")["reasonCodes"], ["SEAT_CAPTURE_HELD"])

    def test_26_cross_seat_model_denominator_disagreement_holds(self) -> None:
        self.assertEqual(self.case("hold-model-denominator-disagreement")["reasonCodes"], ["MODEL_DENOMINATOR_DISAGREEMENT"])

    def test_27_output_disagreement_holds(self) -> None:
        self.assertEqual(self.case("hold-output-disagreement")["reasonCodes"], ["OUTPUT_DISAGREEMENT"])

    def test_28_missing_selected_topology_holds(self) -> None:
        self.assertIn("TOPOLOGY_DISAGREEMENT", self.case("hold-selected-topology-missing")["reasonCodes"])

    def test_29_unordered_or_unreliable_activation_channel_holds(self) -> None:
        self.assertIn("ACTIVATION_TRANSPORT_DISAGREEMENT", self.case("hold-unreliable-activation-channel")["reasonCodes"])

    def test_30_incomplete_performance_denominator_holds(self) -> None:
        self.assertIn("PERFORMANCE_DENOMINATOR_DISAGREEMENT", self.case("hold-performance-denominator-incomplete")["reasonCodes"])

    def test_31_incomplete_controlled_drop_holds_the_seat(self) -> None:
        self.assertEqual(self.case("hold-controlled-drop-incomplete")["reasonCodes"], ["SEAT_CAPTURE_HELD"])

    def test_32_privacy_overclaim_holds_and_cannot_be_inferred_from_observer_silence(self) -> None:
        self.assertIn("PRIVACY_DECLARATION_DISAGREEMENT", self.case("hold-privacy-overclaim")["reasonCodes"])

    def test_33_private_projection_leak_holds_the_seat(self) -> None:
        self.assertEqual(self.case("hold-private-projection-leak")["reasonCodes"], ["SEAT_CAPTURE_HELD"])
        self.assertTrue(mod.public_leak({"endpoint": "https://private.invalid"}))
        self.assertTrue(mod.public_leak({"candidateAddress": "192.168.1.4"}))

    def test_34_nonphysical_and_mixed_source_kinds_fail_closed(self) -> None:
        self.assertEqual(self.case("refused-nonphysical-source-kind")["terminal"], "REFUSED")
        self.assertEqual(self.case("hold-mixed-source-kind")["terminal"], "HOLD")

    def test_35_unknown_raw_event_and_probe_byte_drift_are_refused(self) -> None:
        self.assertEqual(self.case("refused-unknown-raw-event")["reasonCodes"], ["RAW_EVENT_TYPE_UNKNOWN"])
        self.assertEqual(self.case("refused-probe-byte-drift")["reasonCodes"], ["PROBE_ARTIFACT_MISMATCH"])

    def test_36_per_seat_opaque_ids_may_differ_but_physical_refs_must_converge(self) -> None:
        packet = self.base("physicalComplete")
        ids = [
            [row["probeMemberId"] for row in seat["control"]["memberUniquenessAssertions"]]
            for seat in packet["seats"]
        ]
        self.assertNotEqual(ids[0], ids[1])
        decision, _ = mod.reconstruct_packet(self.profile, packet["seats"], None, now_ms=NOW_MS, base=ROOT)
        self.assertEqual(decision["terminal"], "READY_FOR_NAMED_HUMAN")
        self.assertEqual(decision["physicalMemberEvidenceRefs"], ["sha256:" + "a" * 64, "sha256:" + "b" * 64])

    def test_37_generated_public_projection_is_closed_body_free_and_authority_free(self) -> None:
        decision, _ = mod.reconstruct_packet(self.profile, self.base("syntheticComplete")["seats"], None, now_ms=NOW_MS, base=ROOT)
        public = decision["publicProjection"]
        self.assertEqual(tuple(sorted(public)), mod.PUBLIC_KEYS)
        self.assertFalse(mod.public_leak(public))
        self.assert_claim_boundary(public)

    def test_38_controller_template_requires_operator_replacement_and_never_pins_supplier(self) -> None:
        template = load_json(CONTROLLER_TEMPLATE)
        self.assertFalse(template["instructions"]["unchangedTemplateIsValid"])
        control = template["control"]
        self.assertEqual(control["sourceKind"], "physical-private-local")
        self.assertFalse(control["syntheticConformanceOnly"])
        self.assertIsNone(control["workUnit"]["supplierRef"])
        self.assertIsNone(control["supplierAdmissionReceipt"])
        self.assertEqual(control["workUnit"]["requiredInterface"], mod.INTERFACE)

    def test_39_extension_manifest_installs_exact_probe_at_document_start_in_main_world(self) -> None:
        manifest = mod.extension_manifest(self.profile)
        self.assertEqual(manifest["manifest_version"], 3)
        self.assertEqual(len(manifest["content_scripts"]), 1)
        row = manifest["content_scripts"][0]
        self.assertEqual(row["matches"], ["<all_urls>"])
        self.assertEqual(row["js"], ["browser_distributed_inference_probe.js"])
        self.assertEqual(row["run_at"], "document_start")
        self.assertEqual(row["world"], "MAIN")
        self.assertFalse(row["all_frames"])
        self.assertNotIn("permissions", manifest)

    def test_40_build_kit_is_external_complete_and_independently_verified(self) -> None:
        kit = self.work / "kit"
        result = mod.build_kit(self.profile, REPOSITORY_ROOT, kit)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["memberCount"], 19)
        self.assertTrue((kit / "extension" / "manifest.json").is_file())
        self.assertTrue((kit / "source" / "browser_distributed_inference_probe.js").is_file())
        self.assertTrue((kit / "source" / DIRECT.name).is_file())
        self.assertTrue((kit / "templates" / "named-human-confirmation.json").is_file())
        self.assertEqual(mod.sha256_ref((kit / "extension" / "browser_distributed_inference_probe.js").read_bytes()), mod.PROBE_SHA256_REF)

    def test_41_repository_local_and_linked_kit_outputs_are_refused_before_creation(self) -> None:
        output = REPOSITORY_ROOT / "forbidden-kit-output"
        with self.assertRaises(mod.PacketError) as context:
            mod.build_kit(self.profile, REPOSITORY_ROOT, output)
        self.assertEqual(context.exception.code, "REPOSITORY_LOCAL_OUTPUT")
        self.assertFalse(output.exists())

        target = self.work / "linked-kit-target"
        target.mkdir()
        linked = self.work / "linked-kit-output"
        make_directory_link(linked, target)
        with self.assertRaises(mod.PacketError) as context:
            mod.build_kit(self.profile, REPOSITORY_ROOT, linked)
        self.assertEqual(context.exception.code, "UNSAFE_LINK")
        self.assertEqual(list(target.iterdir()), [])

    def test_42_kit_probe_tamper_is_refused(self) -> None:
        kit = self.work / "kit"
        mod.build_kit(self.profile, REPOSITORY_ROOT, kit)
        probe = kit / "extension" / "browser_distributed_inference_probe.js"
        probe.write_bytes(probe.read_bytes() + b"\n")
        with self.assertRaises(mod.PacketError) as context:
            mod.verify_kit(self.profile, kit)
        self.assertIn(context.exception.code, {"KIT_MEMBER_MISMATCH", "PROBE_BYTE_DRIFT"})

    def test_43_extra_kit_member_is_refused(self) -> None:
        kit = self.work / "kit"
        mod.build_kit(self.profile, REPOSITORY_ROOT, kit)
        (kit / "extra.txt").write_text("extra", encoding="utf-8")
        with self.assertRaises(mod.PacketError) as context:
            mod.verify_kit(self.profile, kit)
        self.assertEqual(context.exception.code, "KIT_MEMBER_DENOMINATOR_INVALID")

    def test_44_unsafe_kit_manifest_path_is_refused_before_identity_check(self) -> None:
        kit = self.work / "kit"
        mod.build_kit(self.profile, REPOSITORY_ROOT, kit)
        manifest_path = kit / "kit-manifest.json"
        manifest = load_json(manifest_path)
        manifest["members"][0]["path"] = "../escape"
        manifest_path.write_bytes(mod.pretty_bytes(manifest))
        with self.assertRaises(mod.PacketError) as context:
            mod.verify_kit(self.profile, kit)
        self.assertEqual(context.exception.code, "UNSAFE_PATH")

    def test_45_build_kit_refuses_preexisting_output_coordinate(self) -> None:
        kit = self.work / "kit"
        kit.mkdir()
        with self.assertRaises(mod.PacketError) as context:
            mod.build_kit(self.profile, REPOSITORY_ROOT, kit)
        self.assertEqual(context.exception.code, "OUTPUT_ALREADY_EXISTS")

    def test_46_kit_manifest_records_zero_execution_and_zero_authority(self) -> None:
        kit = self.work / "kit"
        mod.build_kit(self.profile, REPOSITORY_ROOT, kit)
        manifest = load_json(kit / "kit-manifest.json")
        for key in (
            "browserLaunched",
            "externalEndpointContacted",
            "modelDownloaded",
            "peerConnectionFormed",
            "inferenceExecuted",
            "physicalExecutionObserved",
            "actualSupplierQualified",
        ):
            self.assertFalse(manifest[key])
        self.assertEqual(manifest["authority"], "none")

    def test_47_assemble_empty_packet_materializes_only_private_decision_and_public_status(self) -> None:
        packet = self.work / "prepared-packet"
        decision = mod.assemble_packet(self.profile, packet, now_ms=NOW_MS, base=ROOT)
        self.assertEqual(decision["terminal"], "PREPARED_NOT_EXECUTED")
        observed = sorted(path.relative_to(packet).as_posix() for path in packet.rglob("*") if path.is_file())
        self.assertEqual(observed, ["private/packet-decision.json", "public/status.json"])

    def test_48_assemble_synthetic_packet_materializes_both_complete_seat_receipt_sets(self) -> None:
        packet, decision = self.assemble("synthetic-complete-route")
        self.assertEqual(decision["terminal"], "OBSERVED_ROUTE_CANDIDATE")
        for seat_id in mod.SEAT_IDS:
            for name in ("raw.json", "control.json", "capture.json", "materialization.json", "decision.json", "admitted-verdict.json"):
                self.assertTrue((packet / "private" / seat_id / name).is_file(), f"{seat_id}/{name}")

    def test_49_assemble_can_advance_ready_packet_after_separate_confirmation_without_mutating_inputs(self) -> None:
        packet, ready = self.assemble("physical-ready-for-named-human")
        raw_before = [(packet / "private" / seat / "raw.json").read_bytes() for seat in mod.SEAT_IDS]
        confirmation = self.confirmation_for(ready)
        (packet / "private" / "named-human-confirmation.json").write_bytes(mod.pretty_bytes(confirmation))
        confirmed = mod.assemble_packet(self.profile, packet, now_ms=NOW_MS, base=ROOT)
        self.assertEqual(confirmed["terminal"], "OBSERVED_ROUTE_CANDIDATE")
        self.assertTrue(confirmed["physicalExecutionObserved"])
        self.assertEqual(raw_before, [(packet / "private" / seat / "raw.json").read_bytes() for seat in mod.SEAT_IDS])

    def test_50_direct_verifier_reconstructs_packet_seats_decision_and_public_status(self) -> None:
        packet, decision = self.assemble("synthetic-complete-route")
        verdict = verifier.verify(self.profile, ROOT, packet, decision, NOW_MS)
        self.assertEqual(verdict["status"], "PASS")
        self.assertEqual(verdict["seatCapturesIndependentlyReconstructed"], 2)
        self.assertTrue(verdict["rawEvidenceReconstructed"])
        self.assertTrue(verdict["storedDecisionReconstructed"])
        self.assertTrue(verdict["publicProjectionReconstructed"])
        self.assertFalse(verdict["bootstrapAuthenticated"])

    def test_51_bootstrap_executes_only_measured_packet_verifier_bytes(self) -> None:
        packet, _ = self.assemble("synthetic-complete-route")
        verdict = mod.run_packet_verification(PROFILE, packet, now_ms=NOW_MS, base=ROOT)
        self.assertEqual(verdict["status"], "PASS")
        self.assertTrue(verdict["bootstrapAuthenticated"])
        self.assertTrue(verdict["storedVerifierMemberBound"])
        self.assertEqual(verdict["embeddedVerifierSha256"], next(row["sha256"] for row in self.profile["packetSourceBindings"] if Path(row["path"]).name == DIRECT.name))

    def test_52_public_projection_is_returned_by_authenticated_verdict_without_second_decision_read(self) -> None:
        packet, decision = self.assemble("synthetic-complete-route")
        verdict = mod.run_packet_verification(PROFILE, packet, now_ms=NOW_MS, base=ROOT)
        self.assertEqual(verdict["publicProjection"], decision["publicProjection"])
        self.assertEqual(verdict["publicProjectionDigest"], mod.sha256_ref(decision["publicProjection"]))
        self.assertFalse(mod.public_leak(verdict["publicProjection"]))

    def test_53_stored_packet_decision_forgery_is_refused(self) -> None:
        packet, _ = self.assemble("synthetic-complete-route")
        path = packet / "private" / "packet-decision.json"
        body = load_json(path)
        body["terminal"] = "PREPARED_NOT_EXECUTED"
        path.write_bytes(mod.pretty_bytes(body))
        with self.assertRaises(mod.PacketError) as context:
            mod.run_packet_verification(PROFILE, packet, now_ms=NOW_MS, base=ROOT)
        self.assertEqual(context.exception.code, "PACKET_BOOTSTRAP_REFUSED")

    def test_54_stored_public_status_forgery_is_refused(self) -> None:
        packet, _ = self.assemble("synthetic-complete-route")
        path = packet / "public" / "status.json"
        body = load_json(path)
        body["actualSupplierQualified"] = True
        path.write_bytes(mod.pretty_bytes(body))
        with self.assertRaises(mod.PacketError):
            mod.run_packet_verification(PROFILE, packet, now_ms=NOW_MS, base=ROOT)

    def test_55_stored_seat_capture_forgery_is_refused(self) -> None:
        packet, _ = self.assemble("synthetic-complete-route")
        path = packet / "private" / "seat-01" / "capture.json"
        body = load_json(path)
        body["performance"]["lastTokenMonotonicMs"] += 1
        path.write_bytes(mod.pretty_bytes(body))
        with self.assertRaises(mod.PacketError):
            mod.run_packet_verification(PROFILE, packet, now_ms=NOW_MS, base=ROOT)

    def test_56_stored_materialization_receipt_forgery_is_refused(self) -> None:
        packet, _ = self.assemble("synthetic-complete-route")
        path = packet / "private" / "seat-01" / "materialization.json"
        body = load_json(path)
        body["rawEventsReconstructed"] = False
        path.write_bytes(mod.pretty_bytes(body))
        with self.assertRaises(mod.PacketError):
            mod.run_packet_verification(PROFILE, packet, now_ms=NOW_MS, base=ROOT)

    def test_57_stored_admitted_verdict_forgery_is_refused(self) -> None:
        packet, _ = self.assemble("synthetic-complete-route")
        path = packet / "private" / "seat-01" / "admitted-verdict.json"
        body = load_json(path)
        body["actualSupplierQualified"] = True
        path.write_bytes(mod.pretty_bytes(body))
        with self.assertRaises(mod.PacketError):
            mod.run_packet_verification(PROFILE, packet, now_ms=NOW_MS, base=ROOT)

    def test_58_extra_private_packet_member_is_refused(self) -> None:
        packet, _ = self.assemble("synthetic-complete-route")
        (packet / "private" / "secret.txt").write_text("not admitted", encoding="utf-8")
        with self.assertRaises(mod.PacketError):
            mod.run_packet_verification(PROFILE, packet, now_ms=NOW_MS, base=ROOT)

    def test_59_linked_packet_root_is_refused_before_read_or_write(self) -> None:
        target = self.work / "target"
        target.mkdir()
        linked = self.work / "linked"
        make_directory_link(linked, target)
        with self.assertRaises(mod.PacketError) as context:
            mod.assemble_packet(self.profile, linked, now_ms=NOW_MS, base=ROOT)
        self.assertEqual(context.exception.code, "UNSAFE_LINK")
        self.assertEqual(list(target.iterdir()), [])

    def test_60_linked_source_dependency_root_is_refused(self) -> None:
        copied = self.work / "source"
        copied.mkdir()
        for row in self.profile["kitSourceBindings"]:
            shutil.copy2(ROOT / row["path"], copied / row["path"])
        linked = self.work / "linked-source"
        make_directory_link(linked, copied)
        with self.assertRaises(mod.PacketError) as context:
            mod.verify_bound_sources(self.profile, linked, "kitSourceBindings")
        self.assertEqual(context.exception.code, "UNSAFE_LINK")

    def test_61_packet_verifier_substitution_is_refused_before_execution(self) -> None:
        packet, _ = self.assemble("synthetic-complete-route")
        copied = self.work / "source"
        shutil.copytree(ROOT, copied)
        target = copied / DIRECT.name
        altered = bytearray(target.read_bytes())
        altered[0] = ord("x") if altered[0] != ord("x") else ord("y")
        target.write_bytes(altered)
        with self.assertRaises(mod.PacketError) as context:
            mod.run_packet_verification(copied / PROFILE.name, packet, now_ms=NOW_MS, base=copied)
        self.assertEqual(context.exception.code, "SOURCE_BINDING_MISMATCH")

    def test_62_packet_bootstrap_substitution_is_refused_before_execution(self) -> None:
        packet, _ = self.assemble("synthetic-complete-route")
        copied = self.work / "source"
        shutil.copytree(ROOT, copied)
        target = copied / BOOTSTRAP.name
        altered = bytearray(target.read_bytes())
        altered[0] = ord("x") if altered[0] != ord("x") else ord("y")
        target.write_bytes(altered)
        with self.assertRaises(mod.PacketError) as context:
            mod.run_packet_verification(copied / PROFILE.name, packet, now_ms=NOW_MS, base=copied)
        self.assertEqual(context.exception.code, "SOURCE_BINDING_MISMATCH")

    def test_63_admitted_source_floor_or_member_drift_is_refused(self) -> None:
        altered = copy.deepcopy(self.profile)
        altered["admittedAudition"]["admissionCommit"] = "0" * 40
        path = self.work / "profile.json"
        path.write_bytes(mod.pretty_bytes(altered))
        with self.assertRaises(mod.PacketError) as context:
            mod.validate_profile(path)
        self.assertEqual(context.exception.code, "ADMITTED_SOURCE_FLOOR_DRIFT")

    def test_64_verification_output_cannot_modify_measured_packet_source_or_link_target(self) -> None:
        packet, _ = self.assemble("synthetic-complete-route")
        for output, code in (
            (packet / "verdict.json", "OUTPUT_INSIDE_PACKET"),
            (ROOT / "verdict.json", "OUTPUT_INSIDE_SOURCE"),
        ):
            with self.subTest(code=code), self.assertRaises(mod.PacketError) as context:
                mod.run_packet_verification(PROFILE, packet, now_ms=NOW_MS, output=output, base=ROOT)
            self.assertEqual(context.exception.code, code)

        target = self.work / "verdict-target"
        target.mkdir()
        linked_parent = self.work / "linked-verdict-parent"
        make_directory_link(linked_parent, target)
        with self.assertRaises(mod.PacketError) as context:
            mod.run_packet_verification(
                PROFILE,
                packet,
                now_ms=NOW_MS,
                output=linked_parent / "verdict.json",
                base=ROOT,
            )
        self.assertEqual(context.exception.code, "UNSAFE_LINK")
        self.assertEqual(list(target.iterdir()), [])

    def test_65_relative_coordinates_work_from_a_foreign_directory_on_the_same_volume(self) -> None:
        packet, _ = self.assemble("synthetic-complete-route")
        caller = self.work / "caller"
        caller.mkdir()
        relative_profile = os.path.relpath(PROFILE, caller)
        relative_packet = os.path.relpath(packet, caller)
        result = subprocess.run(
            [sys.executable, str(TOOL), "verify", relative_profile, relative_packet, "--now-ms", str(NOW_MS)],
            cwd=caller,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual((result.returncode, result.stderr), (0, b""))
        self.assertTrue(json.loads(result.stdout)["bootstrapAuthenticated"])

    def test_66_source_set_measures_exact_ten_lf_only_members(self) -> None:
        result = mod.source_set(self.profile, REPOSITORY_ROOT)
        self.assertEqual(len(result["members"]), 10)
        self.assertEqual(tuple(row["path"] for row in result["members"]), mod.SOURCE_MEMBERS)
        for row in result["members"]:
            data = (REPOSITORY_ROOT / row["path"]).read_bytes()
            self.assertNotIn(b"\r", data)
            self.assertEqual(row["bytes"], len(data))
            self.assertEqual(row["sha256"], mod.sha256_ref(data))

    def test_67_cli_validation_campaign_and_refusal_are_machine_readable(self) -> None:
        commands = (
            ["validate-profile", str(PROFILE)],
            ["validate-fixtures", str(PROFILE), str(FIXTURES)],
            ["campaign", str(PROFILE), str(FIXTURES)],
            ["source-set", str(PROFILE), str(REPOSITORY_ROOT)],
        )
        for command in commands:
            with self.subTest(command=command[0]):
                result = subprocess.run([sys.executable, str(TOOL), *command], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
                self.assertEqual((result.returncode, result.stderr), (0, b""))
                self.assertIsInstance(json.loads(result.stdout), dict)
        bad = subprocess.run([sys.executable, str(TOOL), "validate-profile", str(self.work / "missing.json")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        self.assertEqual(bad.returncode, 2)
        self.assertEqual(json.loads(bad.stdout)["status"], "REFUSED")

    def test_68_powershell_entrypoint_exposes_only_the_closed_command_surface(self) -> None:
        source = POWERSHELL.read_text(encoding="utf-8")
        for command in mod.COMMANDS:
            self.assertIn(f"'{command}'", source)
        self.assertIn("Python 3.11 or later is required", source)
        self.assertNotIn("Invoke-WebRequest", source)
        self.assertNotIn("Start-Process", source)

    def test_69_source_data_contains_no_bound_supplier_identity(self) -> None:
        supplier_binding_keys = {"supplierref", "supplierobservationref", "supplieradmissionreceipt"}

        def assert_unbound(value: object, coordinate: str = "root") -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    normalized = key.replace("_", "").replace("-", "").lower()
                    if normalized in supplier_binding_keys:
                        self.assertIsNone(child, f"supplier binding at {coordinate}/{key}")
                    assert_unbound(child, f"{coordinate}/{key}")
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    assert_unbound(child, f"{coordinate}/{index}")

        assert_unbound(mod.load_object(CONTROLLER_TEMPLATE), "controller-template")
        assert_unbound(mod.load_object(FIXTURES), "fixture-catalog")
        self.assertNotIn("supplierIdentity", self.profile)
        self.assertNotIn("supplierSelection", self.profile)

    def test_70_workflow_has_explicit_os_coordinate_matrix_and_exact_git_blob_materialization(self) -> None:
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("ubuntu-latest", source)
        self.assertIn("windows-latest", source)
        self.assertIn('["head","merge"]', source)
        self.assertIn("git", source)
        self.assertIn("cat-file", source)
        self.assertIn('f"{commit}^{{tree}}"', source)
        self.assertNotIn('f"{commit}^{tree}"', source)
        self.assertIn("sourceMembers", source)
        self.assertIn("Require the exact bounded source-change denominator", source)
        self.assertIn("changed.issubset(allowed)", source)
        self.assertIn("status.startswith(\"M\\t\")", source)

    def test_71_workflow_qualifies_tests_campaign_kit_packet_verifiers_and_powershell(self) -> None:
        source = WORKFLOW.read_text(encoding="utf-8")
        for token in (
            "Ran 82 tests",
            "validate-profile",
            "validate-fixtures",
            "campaign",
            "build-kit",
            "assemble",
            "verify",
            "public-projection",
            "source-set",
            "pwsh",
            "actions/upload-artifact@v4",
        ):
            self.assertIn(token, source)

    def test_72_workflow_is_read_only_and_launches_no_browser_or_network_client(self) -> None:
        source = WORKFLOW.read_text(encoding="utf-8")
        lowered = source.lower()
        self.assertIn("permissions:\n  contents: read", source)
        self.assertNotIn("contents: write", lowered)
        self.assertNotIn("git push", lowered)
        for token in ("playwright", "selenium", "chromedriver", "msedge.exe", "chrome.exe", "firefox.exe", "curl ", "wget ", "invoke-webrequest"):
            self.assertNotIn(token, lowered)

    def test_73_workflow_comparison_requires_all_four_pull_request_receipt_sets(self) -> None:
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("expected_sets = 4 if is_pull_request else 2", source)
        self.assertIn("platformByteIdentity", source)
        self.assertIn("coordinateByteIdentity", source)
        self.assertIn("headMergeByteIdentity", source)

    def test_74_documentation_classifies_object_actors_mechanism_receipts_limits_and_control_question(self) -> None:
        source = DOCUMENTATION.read_text(encoding="utf-8")
        for token in (
            "two-seat browser physical-audition packet",
            "publicly observed actor",
            "replaceable `OBSERVED_CANDIDATE` implementation",
            "axm/distributed-model-inference@1",
            "PREPARED_NOT_EXECUTED",
            "READY_FOR_NAMED_HUMAN",
            "OBSERVED_ROUTE_CANDIDATE",
            "HOLD",
            "REFUSED",
            "Evidence ledger and claim boundary",
            "Control question",
        ):
            self.assertIn(token, source)
        self.assertIn(mod.ADMITTED_COMMIT, source)
        self.assertIn(mod.ADMITTED_TREE, source)

    def test_75_permanent_source_tree_contains_no_private_packet_or_temporary_carrier(self) -> None:
        expected = {REPOSITORY_ROOT / relative for relative in mod.SOURCE_MEMBERS}
        self.assertTrue(all(path.is_file() for path in expected))
        for path in expected:
            relative = path.relative_to(REPOSITORY_ROOT).as_posix().lower()
            self.assertNotIn("temp-repair", relative)
            self.assertNotIn("private/", relative)
            self.assertNotIn("packet-decision.json", relative)
        for path in ROOT.rglob("__pycache__"):
            self.fail(f"bytecode cache retained in source tree: {path}")

    def test_76_workflow_distinguishes_exact_admitted_dependency_materialization_from_unrelated_drift(self) -> None:
        source = WORKFLOW.read_text(encoding="utf-8")
        for token in (
            'profile["kitSourceBindings"]',
            'profile["admittedAudition"]["admissionCommit"]',
            "materialized_members = source_members + dependency_members",
            'admittedDependencyCount',
            'admittedDependenciesExact',
            'admittedDependencyDifferences',
            'outsideMaterializedMembersClean',
            '*[f":(exclude){relative}" for relative in materialized_members]',
        ):
            self.assertIn(token, source)
        self.assertNotIn(
            '*[f":(exclude){relative}" for relative in source_members]],',
            source,
        )

    def test_77_kit_contains_byte_identical_extension_and_runtime_probe_copies(self) -> None:
        kit = self.work / "kit"
        result = mod.build_kit(self.profile, REPOSITORY_ROOT, kit)
        extension_probe = kit / "extension" / "browser_distributed_inference_probe.js"
        runtime_probe = kit / "source" / "browser_distributed_inference_probe.js"
        self.assertEqual(result["memberCount"], 19)
        self.assertTrue(extension_probe.is_file())
        self.assertTrue(runtime_probe.is_file())
        self.assertEqual(extension_probe.read_bytes(), runtime_probe.read_bytes())
        self.assertEqual(mod.sha256_ref(runtime_probe.read_bytes()), mod.PROBE_SHA256_REF)

    def test_78_documented_source_assemble_command_executes_from_fresh_kit(self) -> None:
        kit = self.work / "kit"
        mod.build_kit(self.profile, REPOSITORY_ROOT, kit)
        packet = self.work / "documented-command-packet"
        foreign = self.work / "foreign-cwd"
        foreign.mkdir()
        completed = subprocess.run(
            [
                sys.executable,
                str(kit / "source" / TOOL.name),
                "assemble",
                str(kit / "source" / PROFILE.name),
                str(packet),
                "--now-ms",
                str(NOW_MS),
            ],
            cwd=foreign,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["terminal"], "PREPARED_NOT_EXECUTED")
        self.assertTrue((packet / "private" / "packet-decision.json").is_file())
        self.assertTrue((packet / "public" / "status.json").is_file())

    def test_79_missing_runtime_probe_is_refused(self) -> None:
        kit = self.work / "kit"
        mod.build_kit(self.profile, REPOSITORY_ROOT, kit)
        (kit / "source" / "browser_distributed_inference_probe.js").unlink()
        with self.assertRaises(mod.PacketError) as context:
            mod.verify_kit(self.profile, kit)
        self.assertEqual(context.exception.code, "REQUIRED_FILE_MISSING")

    def test_80_runtime_probe_drift_from_profile_binding_is_refused(self) -> None:
        kit = self.work / "kit"
        mod.build_kit(self.profile, REPOSITORY_ROOT, kit)
        runtime_probe = kit / "source" / "browser_distributed_inference_probe.js"
        data = runtime_probe.read_bytes()
        runtime_probe.write_bytes(bytes([data[0] ^ 1]) + data[1:])
        rewrite_kit_manifest(kit, self.profile)
        with self.assertRaises(mod.PacketError) as context:
            mod.verify_kit(self.profile, kit)
        self.assertEqual(context.exception.code, "SOURCE_BINDING_MISMATCH")

    def test_81_rebound_runtime_probe_cannot_diverge_from_extension_probe(self) -> None:
        kit = self.work / "kit"
        mod.build_kit(self.profile, REPOSITORY_ROOT, kit)
        runtime_probe = kit / "source" / "browser_distributed_inference_probe.js"
        data = runtime_probe.read_bytes()
        mutated = bytes([data[0] ^ 1]) + data[1:]
        runtime_probe.write_bytes(mutated)
        altered = copy.deepcopy(self.profile)
        binding = next(row for row in altered["kitSourceBindings"] if Path(row["path"]).name == runtime_probe.name)
        binding["bytes"] = len(mutated)
        binding["sha256"] = mod.sha256_ref(mutated)
        rewrite_kit_manifest(kit, altered)
        with self.assertRaises(mod.PacketError) as context:
            mod.verify_kit(altered, kit)
        self.assertEqual(context.exception.code, "PROBE_COPY_DIVERGENCE")

    def test_82_workflow_executes_documented_kit_runtime_on_every_matrix_platform(self) -> None:
        source = WORKFLOW.read_text(encoding="utf-8")
        for token in (
            'DOCUMENTED_PACKET_ROOT',
            '$KIT_ROOT/source/axm_head_browser_physical_audition_packet_01.py',
            '$KIT_ROOT/source/axm-head-browser-physical-audition-packet-profile-01.json',
            'documented-command-decision.json',
            'PREPARED_NOT_EXECUTED',
            'Invoke-AXMBrowserPhysicalAudition.ps1',
            'pwsh-documented-packet',
        ):
            self.assertIn(token, source)


if __name__ == "__main__":
    unittest.main()
