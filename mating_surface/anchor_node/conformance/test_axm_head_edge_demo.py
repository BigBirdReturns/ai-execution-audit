from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import axm_head_edge_demo as mod

PROFILE = ROOT / "axm-head-edge-demo-profile-01.json"
FIXTURES = ROOT / "fixtures" / "axm-head-edge-demo-cases-01.json"
VERIFIER = ROOT / "verify_axm_head_volume.py"
BOOTSTRAP = ROOT / "verify_axm_head_bootstrap.py"


class AxmHeadEdgeDemoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="axm-head-edge-demo-")
        self.root = Path(self.temp.name)
        self.profile = mod.validate_profile(PROFILE)
        self.catalog = mod.validate_fixture_catalog(FIXTURES, self.profile)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def case(self, case_id: str) -> dict:
        return copy.deepcopy(mod.find_case(self.catalog, case_id))

    def build(self, case_id: str, name: str = "volume") -> Path:
        out = self.root / name
        mod.build_volume(profile_path=PROFILE, catalog_path=FIXTURES, case_id=case_id, out=out)
        return out

    def bootstrap(self, volume: Path, cwd: Path | None = None, out: Path | None = None) -> tuple[int, dict, bytes, bytes]:
        foreign = cwd or (self.root / "foreign")
        foreign.mkdir(exist_ok=True)
        command = [sys.executable, str(BOOTSTRAP), str(volume)]
        if out is not None:
            command.extend(["--out", str(out)])
        result = subprocess.run(command, cwd=foreign, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        return result.returncode, json.loads(result.stdout.decode("utf-8")), result.stdout, result.stderr

    def direct(self, volume: Path, cwd: Path | None = None) -> tuple[int, dict]:
        foreign = cwd or (self.root / "foreign-direct")
        foreign.mkdir(exist_ok=True)
        result = subprocess.run(
            [sys.executable, str(volume / "RECOVERY" / "verify_volume.py"), str(volume)],
            cwd=foreign,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.stderr, b"")
        return result.returncode, json.loads(result.stdout.decode("utf-8"))

    @staticmethod
    def rewrite_manifest(volume: Path, *, relatives: list[str] = (), mutations: dict | None = None) -> dict:
        path = volume / "MANIFEST.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if mutations:
            manifest.update(mutations)
        rows = {row["path"]: row for row in manifest["files"]}
        for relative in relatives:
            member = volume.joinpath(*relative.split("/"))
            data = member.read_bytes()
            rows[relative]["bytes"] = len(data)
            rows[relative]["sha256"] = mod.sha256_bytes(data)
        body = dict(manifest)
        body.pop("volumeId")
        manifest["volumeId"] = mod.content_id("axmheadvolume1", body)
        path.write_bytes(mod.pretty_json_bytes(manifest))
        return manifest

    def test_profile_freezes_coordinates_claim_case_denominator_and_digest(self) -> None:
        self.assertEqual(self.profile["sourceCoordinates"], mod.EXPECTED_SOURCE_COORDINATES)
        self.assertEqual(self.profile["claimBoundary"], mod.PUBLIC_CLAIM_BOUNDARY)
        self.assertEqual(self.profile["fixtureCaseIds"], list(mod.CASE_IDS))
        self.assertEqual(mod.sha256_bytes(mod.canonical_json_bytes(self.profile)), mod.PROFILE_CANONICAL_SHA256)
        self.assertEqual(len(self.profile["objectSchemas"]), 10)

    def test_cartridge_digest_is_derived_from_canonical_mission_law(self) -> None:
        for case in self.catalog["cases"]:
            self.assertEqual(case["mission"]["cartridgeSha256"], mod.cartridge_law_sha256(case["mission"]))
        attacks = (
            ("invariant", lambda mission: mission["invariantRefs"].append("invariant:forged@1")),
            ("actor", lambda mission: mission["humanAuthority"].update({"actorId": "autonomous-system"})),
        )
        for label, mutate in attacks:
            with self.subTest(label=label):
                case = self.case(mod.CASE_IDS[0])
                mutate(case["mission"])
                with self.assertRaises(mod.DemoError) as context:
                    mod.decide_case(case, self.profile)
                self.assertEqual(context.exception.code, "CARTRIDGE_LAW_DIGEST_INVALID")

    def test_each_supplier_coordinate_mutation_is_refused_by_builder(self) -> None:
        for name in ("auditRuntime", "physicalFlightFloor", "maryMetabolism"):
            with self.subTest(name=name):
                altered = copy.deepcopy(self.profile)
                altered["sourceCoordinates"][name]["commit"] = "0" * 40
                path = self.root / f"profile-{name}.json"
                path.write_bytes(mod.pretty_json_bytes(altered))
                with self.assertRaises(mod.DemoError) as context:
                    mod.validate_profile(path)
                self.assertEqual(context.exception.code, "SOURCE_COORDINATES_INVALID")

    def test_profile_claim_promotion_is_refused_by_builder(self) -> None:
        altered = copy.deepcopy(self.profile)
        altered["claimBoundary"] = "Physical equipment and operational C2 are qualified."
        path = self.root / "promoted-profile.json"
        path.write_bytes(mod.pretty_json_bytes(altered))
        with self.assertRaises(mod.DemoError) as context:
            mod.validate_profile(path)
        self.assertEqual(context.exception.code, "CLAIM_BOUNDARY_INVALID")

    def test_fixture_catalog_closes_exact_four_cases_and_three_terminals(self) -> None:
        self.assertEqual([case["caseId"] for case in self.catalog["cases"]], list(mod.CASE_IDS))
        decisions = [mod.decide_case(case, self.profile) for case in self.catalog["cases"]]
        self.assertEqual([row["terminal"] for row in decisions], ["QUALIFIED_ASSEMBLY", "QUALIFICATION_PLAN", "HOLD", "QUALIFICATION_PLAN"])
        self.assertEqual(mod.sha256_bytes(mod.canonical_json_bytes(self.catalog)), mod.FIXTURE_CATALOG_CANONICAL_SHA256)

    def test_silently_expanded_fixture_catalog_is_refused(self) -> None:
        altered = copy.deepcopy(self.catalog)
        extra = copy.deepcopy(altered["cases"][0])
        extra["caseId"] = "unqualified-extra-case"
        altered["cases"].append(extra)
        path = self.root / "expanded-catalog.json"
        path.write_bytes(mod.pretty_json_bytes(altered))
        with self.assertRaises(mod.DemoError) as context:
            mod.validate_fixture_catalog(path, self.profile)
        self.assertEqual(context.exception.code, "CASE_DENOMINATOR_INVALID")

    def test_qualified_assembly_selects_optional_3090_without_losing_resident_floor(self) -> None:
        decision = mod.decide_case(self.case(mod.CASE_IDS[0]), self.profile)
        self.assertEqual(decision["selectedRouteId"], "route:halo3-3090@fixture")
        self.assertTrue(decision["optionalOrganSelected"])
        self.assertTrue(decision["residentFloorAvailable"])
        self.assertEqual(decision["eligibleRouteIds"], ["route:halo3-3090@fixture", "route:resident-cpu@fixture"])

    def test_optional_organ_removal_reselects_resident_floor_without_changing_mission(self) -> None:
        case = self.case(mod.CASE_IDS[0])
        original = copy.deepcopy(case["mission"])
        case["routes"] = [route for route in case["routes"] if not route["optionalOrgan"]]
        decision = mod.decide_case(case, self.profile)
        self.assertEqual(decision["terminal"], "QUALIFIED_ASSEMBLY")
        self.assertEqual(decision["selectedRouteId"], "route:resident-cpu@fixture")
        self.assertEqual(case["mission"], original)

    def test_memory_is_evaluated_per_route_and_never_pooled(self) -> None:
        decision = mod.decide_case(self.case(mod.CASE_IDS[3]), self.profile)
        self.assertEqual(decision["terminal"], "QUALIFICATION_PLAN")
        self.assertEqual(decision["eligibleRouteIds"], [])
        for row in decision["routeEvaluations"]:
            self.assertIn("INDIVIDUAL_ROUTE_MEMORY_INSUFFICIENT", row["exclusions"])

    def test_missing_adapter_produces_exact_plan(self) -> None:
        decision = mod.decide_case(self.case(mod.CASE_IDS[1]), self.profile)
        self.assertEqual(decision["reasonCodes"], ["ADAPTER_UNAVAILABLE"])
        self.assertEqual(decision["missingProperties"], ["adapter:file-drop@fixture"])

    def test_undeclared_mutation_interface_holds_before_selection(self) -> None:
        decision = mod.decide_case(self.case(mod.CASE_IDS[2]), self.profile)
        self.assertEqual(decision["terminal"], "HOLD")
        self.assertEqual(decision["reasonCodes"], ["AUTHORITY_CLASS_WITHHELD", "INTERFACE_UNDECLARED", "PROBE_NOT_READ_ONLY"])
        self.assertIsNone(decision["selectedRouteId"])

    def test_stale_equipment_observation_holds(self) -> None:
        case = self.case(mod.CASE_IDS[0])
        case["equipment"]["observationTimeUnixNs"] = case["equipment"]["freshUntilUnixNs"] + 1
        decision = mod.decide_case(case, self.profile)
        self.assertIn("EQUIPMENT_OBSERVATION_STALE", decision["reasonCodes"])

    def test_unknown_fixture_field_is_refused(self) -> None:
        case = self.case(mod.CASE_IDS[0])
        case["inventedAuthority"] = True
        with self.assertRaises(mod.DemoError) as context:
            mod.decide_case(case, self.profile)
        self.assertEqual(context.exception.code, "OBJECT_KEYS_INVALID")

    def test_removable_volume_is_byte_deterministic(self) -> None:
        first = self.build(mod.CASE_IDS[0], "first")
        second = self.build(mod.CASE_IDS[0], "second")
        names = sorted(path.relative_to(first).as_posix() for path in first.rglob("*") if path.is_file())
        self.assertEqual(names, sorted(path.relative_to(second).as_posix() for path in second.rglob("*") if path.is_file()))
        for relative in names:
            self.assertEqual((first / relative).read_bytes(), (second / relative).read_bytes(), relative)

    def test_volume_identity_is_stable_across_lf_and_crlf_profile_catalog(self) -> None:
        first = self.build(mod.CASE_IDS[0], "lf")
        crlf_profile = self.root / "profile-crlf.json"
        crlf_catalog = self.root / "catalog-crlf.json"
        for source, target in ((PROFILE, crlf_profile), (FIXTURES, crlf_catalog)):
            text = source.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
            target.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
        second = self.root / "crlf"
        mod.build_volume(profile_path=crlf_profile, catalog_path=crlf_catalog, case_id=mod.CASE_IDS[0], out=second)
        names = sorted(path.relative_to(first).as_posix() for path in first.rglob("*") if path.is_file())
        for relative in names:
            self.assertEqual((first / relative).read_bytes(), (second / relative).read_bytes(), relative)

    def test_bootstrap_authenticates_and_verifies_from_foreign_directory(self) -> None:
        volume = self.build(mod.CASE_IDS[0])
        code, verdict, _, stderr = self.bootstrap(volume)
        self.assertEqual(code, 0)
        self.assertEqual(stderr, b"")
        self.assertEqual(verdict["status"], "PASS")
        self.assertTrue(verdict["bootstrapAuthenticated"])
        self.assertTrue(verdict["successorAnswersReconstructed"])
        self.assertEqual(verdict["standaloneVerifierSha256"], mod.STANDALONE_VERIFIER_SHA256)

    def test_direct_embedded_verifier_is_truthfully_unauthenticated(self) -> None:
        volume = self.build(mod.CASE_IDS[0])
        code, verdict = self.direct(volume)
        self.assertEqual(code, 0)
        self.assertFalse(verdict["bootstrapAuthenticated"])

    def test_plan_and_hold_volumes_are_portable_and_truthful(self) -> None:
        for index, (case_id, terminal) in enumerate(((mod.CASE_IDS[1], "QUALIFICATION_PLAN"), (mod.CASE_IDS[2], "HOLD"))):
            volume = self.build(case_id, f"volume-{index}")
            code, verdict, _, _ = self.bootstrap(volume, self.root / f"foreign-{index}")
            self.assertEqual(code, 0)
            self.assertEqual(verdict["terminal"], terminal)
            public = json.loads((volume / "PUBLIC/status.json").read_text(encoding="utf-8"))
            self.assertFalse(public["executionOccurred"])
            self.assertFalse(public["physicalEstateQualified"])

    def test_volume_carries_exact_profile_catalog_and_complete_denominators(self) -> None:
        volume = self.build(mod.CASE_IDS[0])
        manifest = json.loads((volume / "MANIFEST.json").read_text(encoding="utf-8"))
        embedded_profile = json.loads((volume / "RECOVERY/profile.json").read_text(encoding="utf-8"))
        embedded_catalog = json.loads((volume / "RECOVERY/fixture-catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(embedded_profile, self.profile)
        self.assertEqual(embedded_catalog, self.catalog)
        self.assertEqual(manifest["profileCanonicalSha256"], mod.PROFILE_CANONICAL_SHA256)
        self.assertEqual(manifest["fixtureCatalogCanonicalSha256"], mod.FIXTURE_CATALOG_CANONICAL_SHA256)
        self.assertEqual(manifest["standaloneVerifierSha256"], mod.STANDALONE_VERIFIER_SHA256)
        self.assertEqual(manifest["fixtureCaseIds"], list(mod.CASE_IDS))
        self.assertTrue(manifest["bootstrapRequired"])
        code, verdict, _, _ = self.bootstrap(volume)
        self.assertEqual(code, 0)
        self.assertEqual(verdict["fileCount"], 12)
        self.assertEqual(verdict["routeCount"], 2)

    def test_profile_provenance_cannot_be_rewritten_and_resigned(self) -> None:
        volume = self.build(mod.CASE_IDS[0])
        path = volume / "RECOVERY/profile.json"
        profile = json.loads(path.read_text(encoding="utf-8"))
        profile["status"] = "admitted"
        path.write_bytes(mod.pretty_json_bytes(profile))
        digest = mod.sha256_bytes(mod.canonical_json_bytes(profile))
        self.rewrite_manifest(volume, relatives=["RECOVERY/profile.json"], mutations={"profileCanonicalSha256": digest})
        code, verdict, _, _ = self.bootstrap(volume)
        self.assertEqual(code, 2)
        self.assertEqual(verdict["code"], "MANIFEST_PROFILE_DIGEST_INVALID")

    def test_catalog_provenance_cannot_be_expanded_and_resigned(self) -> None:
        volume = self.build(mod.CASE_IDS[0])
        path = volume / "RECOVERY/fixture-catalog.json"
        catalog = json.loads(path.read_text(encoding="utf-8"))
        extra = copy.deepcopy(catalog["cases"][0])
        extra["caseId"] = "unqualified-extra-case"
        catalog["cases"].append(extra)
        path.write_bytes(mod.pretty_json_bytes(catalog))
        digest = mod.sha256_bytes(mod.canonical_json_bytes(catalog))
        self.rewrite_manifest(volume, relatives=["RECOVERY/fixture-catalog.json"], mutations={"fixtureCatalogCanonicalSha256": digest, "fixtureCaseIds": [*mod.CASE_IDS, "unqualified-extra-case"]})
        code, verdict, _, _ = self.bootstrap(volume)
        self.assertEqual(code, 2)
        self.assertIn(verdict["code"], {"MANIFEST_CATALOG_DIGEST_INVALID", "MANIFEST_CASE_DENOMINATOR_INVALID"})

    def test_every_successor_answer_forgery_is_refused_after_full_resigning(self) -> None:
        attacks = {
            "whatMission": "mission:forged@fixture",
            "currentState": "field qualified and complete",
            "whoMayAct": "autonomous-system",
            "whatProvesIt": ["sha256:" + "1" * 64],
            "whatRemainsUnresolved": [],
            "nextSafeAction": "Execute without human review.",
        }
        for index, (field, value) in enumerate(attacks.items()):
            with self.subTest(field=field):
                volume = self.build(mod.CASE_IDS[0], f"answer-{index}")
                path = volume / "RECOVERY/cold-successor.json"
                recovery = json.loads(path.read_text(encoding="utf-8"))
                recovery["answers"][field] = value
                path.write_bytes(mod.pretty_json_bytes(recovery))
                self.rewrite_manifest(volume, relatives=["RECOVERY/cold-successor.json"])
                code, verdict, _, _ = self.bootstrap(volume, self.root / f"answer-foreign-{index}")
                self.assertEqual(code, 2)
                self.assertEqual(verdict["code"], "RECOVERY_RECONSTRUCTION_MISMATCH")

    def test_same_id_claim_promotion_across_manifest_and_public_is_refused(self) -> None:
        volume = self.build(mod.CASE_IDS[0])
        promoted = "This volume proves physical equipment, field operation, and operational C2 qualification."
        public_path = volume / "PUBLIC/status.json"
        public = json.loads(public_path.read_text(encoding="utf-8"))
        public["claimBoundary"] = promoted
        public_path.write_bytes(mod.pretty_json_bytes(public))
        self.rewrite_manifest(
            volume,
            relatives=["PUBLIC/status.json"],
            mutations={"claimBoundary": promoted},
        )
        code, verdict, _, _ = self.bootstrap(volume)
        self.assertEqual(code, 2)
        self.assertEqual(verdict["code"], "MANIFEST_CLAIM_BOUNDARY_INVALID")

    def test_resigned_cartridge_law_forgery_is_refused(self) -> None:
        attacks = (
            ("invariant", lambda cartridge: cartridge["invariantRefs"].append("invariant:forged@1")),
            ("actor", lambda cartridge: cartridge["humanAuthority"].update({"actorId": "autonomous-system"})),
        )
        for index, (label, mutate) in enumerate(attacks):
            for mode in ("stale-declared-digest", "rederived-forged-digest"):
                with self.subTest(label=label, mode=mode):
                    volume = self.build(mod.CASE_IDS[0], f"cartridge-law-{index}-{mode}")
                    path = volume / "CARTRIDGE/mission.json"
                    cartridge = json.loads(path.read_text(encoding="utf-8"))
                    mutate(cartridge)
                    manifest_mutations = None
                    expected_code = "CARTRIDGE_LAW_DIGEST_INVALID"
                    if mode == "rederived-forged-digest":
                        cartridge["cartridgeSha256"] = mod.cartridge_law_sha256(cartridge)
                        manifest = json.loads((volume / "MANIFEST.json").read_text(encoding="utf-8"))
                        binding = dict(manifest["cartridgeBinding"])
                        binding["declaredCartridgeSha256"] = cartridge["cartridgeSha256"]
                        manifest_mutations = {"cartridgeBinding": binding}
                        expected_code = "CARTRIDGE_RECONSTRUCTION_MISMATCH"
                    path.write_bytes(mod.pretty_json_bytes(cartridge))
                    self.rewrite_manifest(
                        volume,
                        relatives=["CARTRIDGE/mission.json"],
                        mutations=manifest_mutations,
                    )
                    code, verdict, _, _ = self.bootstrap(
                        volume,
                        self.root / f"cartridge-law-foreign-{index}-{mode}",
                    )
                    self.assertEqual(code, 2)
                    self.assertEqual(verdict["code"], expected_code)

    def test_cartridge_claim_boundary_forgery_is_refused_after_resigning(self) -> None:
        volume = self.build(mod.CASE_IDS[0])
        path = volume / "CARTRIDGE/mission.json"
        cartridge = json.loads(path.read_text(encoding="utf-8"))
        cartridge["claimBoundary"] = "The cartridge grants execution authority."
        path.write_bytes(mod.pretty_json_bytes(cartridge))
        self.rewrite_manifest(volume, relatives=["CARTRIDGE/mission.json"])
        code, verdict, _, _ = self.bootstrap(volume)
        self.assertEqual(code, 2)
        self.assertEqual(verdict["code"], "CARTRIDGE_CLAIM_BOUNDARY_INVALID")

    def test_malicious_verifier_substitution_is_refused_before_execution(self) -> None:
        volume = self.build(mod.CASE_IDS[0])
        marker = self.root / "malicious-verifier-ran"
        malicious = (
            "from pathlib import Path\n"
            f"Path({str(marker)!r}).write_text('executed')\n"
            "print('{\"schema\":\"axm-head/mission-volume-verdict@1\",\"status\":\"PASS\"}')\n"
        )
        path = volume / "RECOVERY/verify_volume.py"
        path.write_text(malicious, encoding="utf-8")
        observed = mod.sha256_bytes(path.read_bytes())
        self.rewrite_manifest(volume, relatives=["RECOVERY/verify_volume.py"], mutations={"standaloneVerifierSha256": observed})
        code, verdict, _, _ = self.bootstrap(volume)
        self.assertEqual(code, 2)
        self.assertEqual(verdict["code"], "VERIFIER_TRUST_MISMATCH")
        self.assertFalse(marker.exists())

    def test_builder_refuses_arbitrary_verifier_source_even_through_internal_api(self) -> None:
        malicious = self.root / "malicious.py"
        malicious.write_text("print('PASS')\n", encoding="utf-8")
        with self.assertRaises(mod.DemoError) as context:
            mod.build_volume(profile_path=PROFILE, catalog_path=FIXTURES, case_id=mod.CASE_IDS[0], out=self.root / "bad", verifier_source_path=malicious)
        self.assertEqual(context.exception.code, "VERIFIER_TRUST_MISMATCH")

    def test_route_denominator_change_is_refused_after_complete_resigning(self) -> None:
        volume = self.build(mod.CASE_IDS[0])
        path = volume / "ROUTES/candidate-routes.json"
        denominator = json.loads(path.read_text(encoding="utf-8"))
        denominator["routes"][0]["preferenceRank"] = 99
        body = dict(denominator)
        body.pop("routeDenominatorId")
        denominator["routeDenominatorId"] = mod.content_id("axmheadroutes1", body)
        path.write_bytes(mod.pretty_json_bytes(denominator))
        self.rewrite_manifest(volume, relatives=["ROUTES/candidate-routes.json"], mutations={"routeDenominator": {**json.loads((volume / "MANIFEST.json").read_text())["routeDenominator"], "routeDenominatorId": denominator["routeDenominatorId"]}})
        code, verdict, _, _ = self.bootstrap(volume)
        self.assertEqual(code, 2)
        self.assertEqual(verdict["code"], "ROUTE_DENOMINATOR_RECONSTRUCTION_MISMATCH")

    def test_cache_bytes_do_not_change_volume_identity_or_verdict(self) -> None:
        volume = self.build(mod.CASE_IDS[0])
        before = json.loads((volume / "MANIFEST.json").read_text(encoding="utf-8"))["volumeId"]
        (volume / "CACHE" / "host-specific.bin").write_bytes(b"replaceable cache bytes")
        code, verdict, _, _ = self.bootstrap(volume)
        self.assertEqual(code, 0)
        self.assertEqual(verdict["volumeId"], before)
        self.assertTrue(verdict["cacheNonAuthoritative"])

    def test_unmanifested_non_cache_file_is_refused(self) -> None:
        volume = self.build(mod.CASE_IDS[0])
        (volume / "SAVE" / "secret-extra.json").write_text("{}\n", encoding="utf-8")
        code, verdict, _, _ = self.bootstrap(volume)
        self.assertEqual(code, 2)
        self.assertEqual(verdict["code"], "UNMANIFESTED_FILE")

    def test_cartridge_byte_tamper_is_refused(self) -> None:
        volume = self.build(mod.CASE_IDS[0])
        path = volume / "CARTRIDGE/mission.json"
        data = bytearray(path.read_bytes())
        data[-2] = ord(" ")
        path.write_bytes(bytes(data))
        code, verdict, _, _ = self.bootstrap(volume)
        self.assertEqual(code, 2)
        self.assertEqual(verdict["code"], "FILE_DIGEST_MISMATCH")

    def test_semantic_save_mismatch_is_refused_after_rebinding(self) -> None:
        volume = self.build(mod.CASE_IDS[0])
        path = volume / "SAVE/state.json"
        save = json.loads(path.read_text(encoding="utf-8"))
        save["cartridgeId"] = "cartridge:wrong@fixture"
        path.write_bytes(mod.pretty_json_bytes(save))
        self.rewrite_manifest(volume, relatives=["SAVE/state.json"])
        code, verdict, _, _ = self.bootstrap(volume)
        self.assertEqual(code, 2)
        self.assertEqual(verdict["code"], "SAVE_RECONSTRUCTION_MISMATCH")

    def test_decision_self_identity_and_semantics_are_reconstructed(self) -> None:
        volume = self.build(mod.CASE_IDS[0])
        path = volume / "ROUTES/intake-decision.json"
        decision = json.loads(path.read_text(encoding="utf-8"))
        decision["optionalOrganSelected"] = False
        body = dict(decision)
        body.pop("decisionId")
        decision["decisionId"] = mod.content_id("axmheaddecision1", body)
        path.write_bytes(mod.pretty_json_bytes(decision))
        self.rewrite_manifest(volume, relatives=["ROUTES/intake-decision.json"])
        code, verdict, _, _ = self.bootstrap(volume)
        self.assertEqual(code, 2)
        self.assertEqual(verdict["code"], "DECISION_RECOMPUTATION_MISMATCH")

    def test_public_projection_contains_no_private_material_or_promoted_claim(self) -> None:
        volume = self.build(mod.CASE_IDS[0])
        text = (volume / "PUBLIC/status.json").read_text(encoding="utf-8")
        for forbidden in ("OCTO-" + "W01", "C:" + "\\", "/home/", "/Users/", "privatePath", "Author" + "ization: " + "Bearer"):
            self.assertNotIn(forbidden, text)
        public = json.loads(text)
        self.assertEqual(public["claimBoundary"], mod.PUBLIC_CLAIM_BOUNDARY)
        self.assertEqual(public["systemAuthority"], "none")
        self.assertFalse(public["physicalFlightCompleted"])

    def test_verdict_output_inside_volume_is_refused_without_mutation(self) -> None:
        for index, entrypoint in enumerate(("bootstrap", "direct")):
            with self.subTest(entrypoint=entrypoint):
                volume = self.build(mod.CASE_IDS[0], f"output-volume-{index}")
                before = {
                    path.relative_to(volume).as_posix(): path.read_bytes()
                    for path in volume.rglob("*")
                    if path.is_file()
                }
                out = volume / "PUBLIC" / f"{entrypoint}-verdict.json"
                if entrypoint == "bootstrap":
                    code, verdict, _, stderr = self.bootstrap(
                        volume,
                        self.root / f"output-foreign-{index}",
                        out,
                    )
                else:
                    foreign = self.root / f"output-foreign-{index}"
                    foreign.mkdir()
                    result = subprocess.run(
                        [
                            sys.executable,
                            str(volume / "RECOVERY" / "verify_volume.py"),
                            str(volume),
                            "--out",
                            str(out),
                        ],
                        cwd=foreign,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=False,
                    )
                    code = result.returncode
                    verdict = json.loads(result.stdout.decode("utf-8"))
                    stderr = result.stderr
                self.assertEqual(code, 2)
                self.assertEqual(stderr, b"")
                self.assertEqual(verdict["code"], "OUTPUT_INSIDE_VOLUME")
                self.assertFalse(out.exists())
                after = {
                    path.relative_to(volume).as_posix(): path.read_bytes()
                    for path in volume.rglob("*")
                    if path.is_file()
                }
                self.assertEqual(after, before)

    def test_bootstrap_verdict_file_is_canonical_lf_utf8(self) -> None:
        volume = self.build(mod.CASE_IDS[0])
        receipt = self.root / "verdict.json"
        code, verdict, stdout, stderr = self.bootstrap(volume, self.root / "foreign-verdict", receipt)
        self.assertEqual(code, 0)
        self.assertEqual(stderr, b"")
        data = receipt.read_bytes()
        self.assertEqual(stdout, data)
        self.assertNotIn(b"\r\n", data)
        self.assertTrue(data.endswith(b"\n"))
        self.assertEqual(data, mod.pretty_json_bytes(verdict))

    def test_standalone_verifier_imports_no_repository_module(self) -> None:
        source = VERIFIER.read_text(encoding="utf-8")
        for forbidden in ("import axm_head_edge_demo", "from axm_head_edge_demo", "import mary", "import stc_mary"):
            self.assertNotIn(forbidden, source)

    def test_existing_output_root_is_refused(self) -> None:
        out = self.root / "volume"
        out.mkdir()
        with self.assertRaises(mod.DemoError) as context:
            mod.build_volume(profile_path=PROFILE, catalog_path=FIXTURES, case_id=mod.CASE_IDS[0], out=out)
        self.assertEqual(context.exception.code, "OUTPUT_EXISTS")


if __name__ == "__main__":
    unittest.main(verbosity=2)
