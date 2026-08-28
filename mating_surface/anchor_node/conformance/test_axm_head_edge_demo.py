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
        mod.build_volume(
            profile_path=PROFILE,
            catalog_path=FIXTURES,
            case_id=case_id,
            out=out,
            verifier_source_path=VERIFIER,
        )
        return out

    def standalone(self, volume: Path, cwd: Path | None = None) -> tuple[int, dict]:
        foreign = cwd or (self.root / "foreign")
        foreign.mkdir(exist_ok=True)
        result = subprocess.run(
            [sys.executable, str(volume / "RECOVERY" / "verify_volume.py"), str(volume)],
            cwd=foreign,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.stderr, "")
        return result.returncode, json.loads(result.stdout)

    @staticmethod
    def rebind_manifest_files(volume: Path, relatives: list[str]) -> dict:
        manifest_path = volume / "MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        rows = {row["path"]: row for row in manifest["files"]}
        for relative in relatives:
            member = volume.joinpath(*relative.split("/"))
            if relative not in rows:
                raise AssertionError(relative)
            data = member.read_bytes()
            rows[relative]["bytes"] = len(data)
            rows[relative]["sha256"] = mod.sha256_bytes(data)
        body = dict(manifest)
        body.pop("volumeId")
        manifest["volumeId"] = mod.content_id("axmheadvolume1", body)
        manifest_path.write_bytes(mod.pretty_json_bytes(manifest))
        return manifest

    @staticmethod
    def rebind_manifest_file(volume: Path, relative: str) -> None:
        AxmHeadEdgeDemoTests.rebind_manifest_files(volume, [relative])

    def test_profile_binds_exact_three_supplier_coordinates(self) -> None:
        self.assertEqual(self.profile["sourceCoordinates"]["auditRuntime"]["commit"], "772ce582e1b19b7a2060c50be8ebf40c1f8723b2")
        self.assertEqual(self.profile["sourceCoordinates"]["physicalFlightFloor"]["status"], "admitted_not_executed")
        self.assertEqual(self.profile["sourceCoordinates"]["maryMetabolism"]["status"], "qualified_draft_not_admitted")
        self.assertEqual(self.profile["supplierBindings"], mod.EXPECTED_SUPPLIER_BINDINGS)
        self.assertEqual(len(self.profile["objectSchemas"]), 10)
        self.assertEqual(self.profile["terminalStates"], list(mod.TERMINALS))

    def test_fixture_catalog_closes_all_three_terminal_classes(self) -> None:
        decisions = {case["caseId"]: mod.decide_case(case, self.profile) for case in self.catalog["cases"]}
        self.assertEqual(decisions["qualified-gpu-with-resident-fallback"]["terminal"], "QUALIFIED_ASSEMBLY")
        self.assertEqual(decisions["qualification-plan-missing-adapter"]["terminal"], "QUALIFICATION_PLAN")
        self.assertEqual(decisions["hold-undeclared-mutation-interface"]["terminal"], "HOLD")

    def test_qualified_assembly_selects_optional_3090_without_losing_resident_floor(self) -> None:
        decision = mod.decide_case(self.case("qualified-gpu-with-resident-fallback"), self.profile)
        self.assertEqual(decision["selectedRouteId"], "route:halo3-3090@fixture")
        self.assertTrue(decision["optionalOrganSelected"])
        self.assertTrue(decision["residentFloorAvailable"])
        self.assertEqual(decision["eligibleRouteIds"], ["route:halo3-3090@fixture", "route:resident-cpu@fixture"])
        self.assertEqual(len(decision["routeEvaluations"]), 2)

    def test_optional_organ_removal_reselects_resident_floor_without_changing_mission(self) -> None:
        case = self.case("qualified-gpu-with-resident-fallback")
        original_mission = copy.deepcopy(case["mission"])
        case["routes"] = [route for route in case["routes"] if not route["optionalOrgan"]]
        decision = mod.decide_case(case, self.profile)
        self.assertEqual(decision["terminal"], "QUALIFIED_ASSEMBLY")
        self.assertEqual(decision["selectedRouteId"], "route:resident-cpu@fixture")
        self.assertFalse(decision["optionalOrganSelected"])
        self.assertEqual(case["mission"], original_mission)

    def test_memory_is_evaluated_per_route_and_never_pooled(self) -> None:
        decision = mod.decide_case(self.case("qualification-plan-no-memory-pooling"), self.profile)
        self.assertEqual(decision["terminal"], "QUALIFICATION_PLAN")
        self.assertEqual(decision["eligibleRouteIds"], [])
        for row in decision["routeEvaluations"]:
            self.assertIn("INDIVIDUAL_ROUTE_MEMORY_INSUFFICIENT", row["exclusions"])

    def test_missing_adapter_produces_exact_qualification_plan(self) -> None:
        decision = mod.decide_case(self.case("qualification-plan-missing-adapter"), self.profile)
        self.assertEqual(decision["terminal"], "QUALIFICATION_PLAN")
        self.assertEqual(decision["reasonCodes"], ["ADAPTER_UNAVAILABLE"])
        self.assertEqual(decision["missingProperties"], ["adapter:file-drop@fixture"])
        self.assertFalse(decision["executionOccurred"])

    def test_undeclared_mutation_interface_holds_before_route_selection(self) -> None:
        decision = mod.decide_case(self.case("hold-undeclared-mutation-interface"), self.profile)
        self.assertEqual(decision["terminal"], "HOLD")
        self.assertEqual(
            decision["reasonCodes"],
            ["AUTHORITY_CLASS_WITHHELD", "INTERFACE_UNDECLARED", "PROBE_NOT_READ_ONLY"],
        )
        self.assertIsNone(decision["selectedRouteId"])

    def test_stale_equipment_observation_holds(self) -> None:
        case = self.case("qualified-gpu-with-resident-fallback")
        case["equipment"]["observationTimeUnixNs"] = case["equipment"]["freshUntilUnixNs"] + 1
        decision = mod.decide_case(case, self.profile)
        self.assertEqual(decision["terminal"], "HOLD")
        self.assertIn("EQUIPMENT_OBSERVATION_STALE", decision["reasonCodes"])

    def test_unknown_fixture_field_is_refused(self) -> None:
        case = self.case("qualified-gpu-with-resident-fallback")
        case["inventedAuthority"] = True
        with self.assertRaises(mod.DemoError) as context:
            mod.decide_case(case, self.profile)
        self.assertEqual(context.exception.code, "OBJECT_KEYS_INVALID")

    def test_removable_volume_is_byte_deterministic(self) -> None:
        first = self.build("qualified-gpu-with-resident-fallback", "first")
        second = self.build("qualified-gpu-with-resident-fallback", "second")
        first_files = sorted(path.relative_to(first).as_posix() for path in first.rglob("*") if path.is_file())
        second_files = sorted(path.relative_to(second).as_posix() for path in second.rglob("*") if path.is_file())
        self.assertEqual(first_files, second_files)
        for relative in first_files:
            self.assertEqual((first / relative).read_bytes(), (second / relative).read_bytes(), relative)

    def test_volume_identity_is_stable_across_lf_and_crlf_source_checkouts(self) -> None:
        first = self.build("qualified-gpu-with-resident-fallback", "lf-volume")
        crlf_profile = self.root / "profile-crlf.json"
        crlf_fixtures = self.root / "fixtures-crlf.json"
        for source, target in ((PROFILE, crlf_profile), (FIXTURES, crlf_fixtures)):
            text = source.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
            target.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
        second = self.root / "crlf-volume"
        mod.build_volume(
            profile_path=crlf_profile,
            catalog_path=crlf_fixtures,
            case_id="qualified-gpu-with-resident-fallback",
            out=second,
            verifier_source_path=VERIFIER,
        )
        first_files = sorted(path.relative_to(first).as_posix() for path in first.rglob("*") if path.is_file())
        second_files = sorted(path.relative_to(second).as_posix() for path in second.rglob("*") if path.is_file())
        self.assertEqual(first_files, second_files)
        for relative in first_files:
            self.assertEqual((first / relative).read_bytes(), (second / relative).read_bytes(), relative)

    def test_standalone_verifier_passes_from_foreign_working_directory(self) -> None:
        volume = self.build("qualified-gpu-with-resident-fallback")
        code, verdict = self.standalone(volume)
        self.assertEqual(code, 0)
        self.assertEqual(verdict["status"], "PASS")
        self.assertEqual(verdict["terminal"], "QUALIFIED_ASSEMBLY")
        self.assertFalse(verdict["executionOccurred"])
        self.assertEqual(verdict["systemAuthority"], "none")

    def test_plan_and_hold_volumes_are_portable_and_truthful(self) -> None:
        for index, (case_id, terminal) in enumerate((
            ("qualification-plan-missing-adapter", "QUALIFICATION_PLAN"),
            ("hold-undeclared-mutation-interface", "HOLD"),
        )):
            volume = self.build(case_id, f"volume-{index}")
            code, verdict = self.standalone(volume, self.root / f"foreign-{index}")
            self.assertEqual(code, 0)
            self.assertEqual(verdict["terminal"], terminal)
            public = json.loads((volume / "PUBLIC/status.json").read_text(encoding="utf-8"))
            self.assertFalse(public["executionOccurred"])
            self.assertFalse(public["physicalEstateQualified"])

    def test_volume_carries_complete_work_unit_and_route_denominator(self) -> None:
        volume = self.build("qualified-gpu-with-resident-fallback")
        case = self.case("qualified-gpu-with-resident-fallback")
        work_unit = json.loads((volume / "CARTRIDGE/work-unit.json").read_text(encoding="utf-8"))
        denominator = json.loads((volume / "ROUTES/candidate-routes.json").read_text(encoding="utf-8"))
        decision = json.loads((volume / "ROUTES/intake-decision.json").read_text(encoding="utf-8"))
        manifest = json.loads((volume / "MANIFEST.json").read_text(encoding="utf-8"))
        self.assertEqual(work_unit["task"], case["task"])
        self.assertEqual(work_unit["supplierSchema"], "invitation-home/work-unit@v0alpha1")
        self.assertEqual(denominator["routes"], sorted(case["routes"], key=lambda row: row["routeId"]))
        self.assertEqual(denominator["routeCount"], 2)
        self.assertEqual(decision["routeDenominatorId"], denominator["routeDenominatorId"])
        self.assertEqual(manifest["routeDenominator"]["routeCount"], 2)
        code, verdict = self.standalone(volume)
        self.assertEqual(code, 0)
        self.assertEqual(verdict["fileCount"], 10)
        self.assertEqual(verdict["routeCount"], 2)

    def test_route_denominator_change_is_refused_after_complete_resigning(self) -> None:
        volume = self.build("qualified-gpu-with-resident-fallback")
        denominator_path = volume / "ROUTES/candidate-routes.json"
        denominator = json.loads(denominator_path.read_text(encoding="utf-8"))
        for route in denominator["routes"]:
            if route["routeId"] == "route:halo3-3090@fixture":
                route["preferenceRank"] = 30
        denominator_body = dict(denominator)
        denominator_body.pop("routeDenominatorId")
        denominator["routeDenominatorId"] = mod.content_id("axmheadroutes1", denominator_body)
        denominator_path.write_bytes(mod.pretty_json_bytes(denominator))

        decision_path = volume / "ROUTES/intake-decision.json"
        decision = json.loads(decision_path.read_text(encoding="utf-8"))
        decision["routeDenominatorId"] = denominator["routeDenominatorId"]
        decision_body = dict(decision)
        decision_body.pop("decisionId")
        decision["decisionId"] = mod.content_id("axmheaddecision1", decision_body)
        decision_path.write_bytes(mod.pretty_json_bytes(decision))

        save_path = volume / "SAVE/state.json"
        save = json.loads(save_path.read_text(encoding="utf-8"))
        save["lastDecisionId"] = decision["decisionId"]
        save_path.write_bytes(mod.pretty_json_bytes(save))

        ledger_path = volume / "SAVE/ledger.jsonl"
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        ledger["routeDenominatorId"] = denominator["routeDenominatorId"]
        ledger["decisionId"] = decision["decisionId"]
        ledger_body = dict(ledger)
        ledger_body.pop("eventId")
        ledger["eventId"] = mod.content_id("axmheadledger1", ledger_body)
        ledger_path.write_bytes(mod.canonical_json_bytes(ledger))

        recovery_path = volume / "RECOVERY/cold-successor.json"
        recovery = json.loads(recovery_path.read_text(encoding="utf-8"))
        recovery["bindings"]["routeDenominatorId"] = denominator["routeDenominatorId"]
        recovery["bindings"]["decisionId"] = decision["decisionId"]
        recovery_path.write_bytes(mod.pretty_json_bytes(recovery))

        manifest_path = volume / "MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["routeDenominator"]["routeDenominatorId"] = denominator["routeDenominatorId"]
        manifest_path.write_bytes(mod.pretty_json_bytes(manifest))
        self.rebind_manifest_files(
            volume,
            [
                "ROUTES/candidate-routes.json",
                "ROUTES/intake-decision.json",
                "SAVE/state.json",
                "SAVE/ledger.jsonl",
                "RECOVERY/cold-successor.json",
            ],
        )
        code, verdict = self.standalone(volume)
        self.assertEqual(code, 2)
        self.assertEqual(verdict["code"], "DECISION_RECOMPUTATION_MISMATCH")

    def test_cache_bytes_do_not_change_volume_identity_or_verdict(self) -> None:
        volume = self.build("qualified-gpu-with-resident-fallback")
        manifest_before = json.loads((volume / "MANIFEST.json").read_text(encoding="utf-8"))
        (volume / "CACHE" / "host-specific.bin").write_bytes(b"replaceable cache bytes")
        code, verdict = self.standalone(volume)
        self.assertEqual(code, 0)
        self.assertEqual(verdict["volumeId"], manifest_before["volumeId"])
        self.assertTrue(verdict["cacheNonAuthoritative"])

    def test_unmanifested_non_cache_file_is_refused(self) -> None:
        volume = self.build("qualified-gpu-with-resident-fallback")
        (volume / "SAVE" / "secret-extra.json").write_text("{}\n", encoding="utf-8")
        code, verdict = self.standalone(volume)
        self.assertEqual(code, 2)
        self.assertEqual(verdict["status"], "REFUSED")
        self.assertEqual(verdict["code"], "UNMANIFESTED_FILE")

    def test_cartridge_tamper_is_refused(self) -> None:
        volume = self.build("qualified-gpu-with-resident-fallback")
        path = volume / "CARTRIDGE" / "mission.json"
        data = bytearray(path.read_bytes())
        data[-2] = ord(" ")
        path.write_bytes(bytes(data))
        code, verdict = self.standalone(volume)
        self.assertEqual(code, 2)
        self.assertEqual(verdict["code"], "FILE_DIGEST_MISMATCH")

    def test_semantic_cartridge_save_mismatch_is_refused_after_rebinding_bytes(self) -> None:
        volume = self.build("qualified-gpu-with-resident-fallback")
        save_path = volume / "SAVE" / "state.json"
        save = json.loads(save_path.read_text(encoding="utf-8"))
        save["cartridgeId"] = "cartridge:wrong@fixture"
        save_path.write_bytes(mod.pretty_json_bytes(save))
        self.rebind_manifest_file(volume, "SAVE/state.json")
        code, verdict = self.standalone(volume)
        self.assertEqual(code, 2)
        self.assertIn(verdict["code"], {"CARTRIDGE_SAVE_BINDING_INVALID", "MANIFEST_SAVE_BINDING_INVALID"})

    def test_decision_self_identity_is_independently_recomputed(self) -> None:
        volume = self.build("qualified-gpu-with-resident-fallback")
        decision_path = volume / "ROUTES" / "intake-decision.json"
        decision = json.loads(decision_path.read_text(encoding="utf-8"))
        decision["optionalOrganSelected"] = False
        decision_path.write_bytes(mod.pretty_json_bytes(decision))
        self.rebind_manifest_file(volume, "ROUTES/intake-decision.json")
        code, verdict = self.standalone(volume)
        self.assertEqual(code, 2)
        self.assertEqual(verdict["code"], "DECISION_ID_INVALID")

    def test_public_projection_contains_no_private_host_path_or_promoted_claim(self) -> None:
        volume = self.build("qualified-gpu-with-resident-fallback")
        public_text = (volume / "PUBLIC" / "status.json").read_text(encoding="utf-8")
        for forbidden in ("OCTO-" + "W01", "C:" + "\\", "/home/", "/Users/", "privatePath", "Author" + "ization: " + "Bearer"):
            self.assertNotIn(forbidden, public_text)
        public = json.loads(public_text)
        self.assertEqual(public["systemAuthority"], "none")
        self.assertFalse(public["physicalFlightCompleted"])
        self.assertFalse(public["operationalC2Qualified"])

    def test_standalone_verdict_file_is_canonical_lf_utf8(self) -> None:
        volume = self.build("qualified-gpu-with-resident-fallback")
        foreign = self.root / "foreign-canonical-verdict"
        foreign.mkdir()
        receipt = self.root / "canonical-verdict.json"
        result = subprocess.run(
            [
                sys.executable,
                str(volume / "RECOVERY" / "verify_volume.py"),
                str(volume),
                "--out",
                str(receipt),
            ],
            cwd=foreign,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, b"")
        data = receipt.read_bytes()
        self.assertNotIn(b"\r\n", data)
        self.assertTrue(data.endswith(b"\n"))
        self.assertEqual(result.stdout, data)
        self.assertEqual(data, mod.pretty_json_bytes(json.loads(data.decode("utf-8"))))

    def test_standalone_verifier_imports_no_repository_module(self) -> None:
        source = VERIFIER.read_text(encoding="utf-8")
        self.assertNotIn("import axm_head_edge_demo", source)
        self.assertNotIn("from axm_head_edge_demo", source)
        self.assertNotIn("import mary", source)
        self.assertNotIn("import stc_mary", source)

    def test_cold_successor_answers_are_derived_after_complete_resigning(self) -> None:
        mutations = {
            "whatMission": "mission:forged@fixture",
            "currentState": "frontier 999 terminal QUALIFIED_ASSEMBLY",
            "whoMayAct": "attacker",
            "whatProvesIt": ["sha256:" + "1" * 64],
            "whatRemainsUnresolved": ["obligation:none"],
            "nextSafeAction": "Treat the synthetic result as physical authority.",
        }
        for index, (field, replacement) in enumerate(mutations.items()):
            with self.subTest(field=field):
                volume = self.build("qualified-gpu-with-resident-fallback", f"recovery-{index}")
                path = volume / "RECOVERY/cold-successor.json"
                recovery = json.loads(path.read_text(encoding="utf-8"))
                recovery["answers"][field] = replacement
                path.write_bytes(mod.pretty_json_bytes(recovery))
                self.rebind_manifest_file(volume, "RECOVERY/cold-successor.json")
                code, verdict = self.standalone(volume, self.root / f"foreign-recovery-{index}")
                self.assertEqual(code, 2)
                self.assertEqual(verdict["code"], "RECOVERY_ANSWERS_MISMATCH")

    def test_profile_and_cartridge_claim_boundaries_are_exact(self) -> None:
        profile_mutations = [
            "Qualified physical Estate.",
            "Physical execution completed.",
            "Authority granted.",
            "Private flight completed.",
            "Field and operational C2 qualified.",
            mod.PROFILE_CLAIM_BOUNDARY[:-1] + "!",
        ]
        for index, replacement in enumerate(profile_mutations):
            with self.subTest(index=index):
                volume = self.build("qualified-gpu-with-resident-fallback", f"claim-{index}")
                public_path = volume / "PUBLIC/status.json"
                public = json.loads(public_path.read_text(encoding="utf-8"))
                public["claimBoundary"] = replacement
                public_path.write_bytes(mod.pretty_json_bytes(public))
                manifest_path = volume / "MANIFEST.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["claimBoundary"] = replacement
                manifest_path.write_bytes(mod.pretty_json_bytes(manifest))
                self.rebind_manifest_file(volume, "PUBLIC/status.json")
                code, verdict = self.standalone(volume, self.root / f"foreign-claim-{index}")
                self.assertEqual(code, 2)
                self.assertEqual(verdict["code"], "CLAIM_BOUNDARY_INVALID")

        volume = self.build("qualified-gpu-with-resident-fallback", "cartridge-claim")
        path = volume / "CARTRIDGE/mission.json"
        cartridge = json.loads(path.read_text(encoding="utf-8"))
        cartridge["claimBoundary"] = "Mission authority granted."
        path.write_bytes(mod.pretty_json_bytes(cartridge))
        self.rebind_manifest_file(volume, "CARTRIDGE/mission.json")
        code, verdict = self.standalone(volume, self.root / "foreign-cartridge-claim")
        self.assertEqual(code, 2)
        self.assertEqual(verdict["code"], "CARTRIDGE_CLAIM_BOUNDARY_INVALID")

    def test_source_coordinate_mutations_refuse_after_complete_resigning(self) -> None:
        replacements = {
            "repository": "BigBirdReturns/forged",
            "commit": "1" * 40,
            "tree": "2" * 40,
            "status": "admitted",
        }
        index = 0
        for supplier in ("auditRuntime", "physicalFlightFloor", "maryMetabolism"):
            for field, replacement in replacements.items():
                with self.subTest(supplier=supplier, field=field):
                    volume = self.build("qualified-gpu-with-resident-fallback", f"source-{index}")
                    index += 1
                    manifest_path = volume / "MANIFEST.json"
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    current = manifest["sourceCoordinates"][supplier][field]
                    manifest["sourceCoordinates"][supplier][field] = replacement if replacement != current else "forged_status"
                    body = dict(manifest)
                    body.pop("volumeId")
                    manifest["volumeId"] = mod.content_id("axmheadvolume1", body)
                    manifest_path.write_bytes(mod.pretty_json_bytes(manifest))
                    code, verdict = self.standalone(volume, self.root / f"foreign-source-{index}")
                    self.assertEqual(code, 2)
                    self.assertEqual(verdict["code"], "SOURCE_COORDINATES_INVALID")

    def test_profile_catalog_and_case_denominator_provenance_refuse(self) -> None:
        mutations = [
            ("profileCanonicalSha256", "1" * 64),
            ("fixtureCatalogCanonicalSha256", "2" * 64),
            ("fixtureCatalogSchema", "axm-head-edge-demo-fixture-catalog/forged"),
            ("qualifiedCaseIds", [*mod.EXPECTED_CASE_IDS, "silently-added-fifth-case"]),
            ("qualifiedCaseIds", list(mod.EXPECTED_CASE_IDS[:-1])),
            ("qualifiedCaseIds", ["renamed-case", *mod.EXPECTED_CASE_IDS[1:]]),
            ("qualifiedCaseIds", [*mod.EXPECTED_CASE_IDS, "unexercised-case"]),
            ("caseId", "selected-case-not-in-denominator"),
        ]
        expected_codes = {
            "profileCanonicalSha256": "PROFILE_PROVENANCE_INVALID",
            "fixtureCatalogCanonicalSha256": "FIXTURE_PROVENANCE_INVALID",
            "fixtureCatalogSchema": "FIXTURE_PROVENANCE_INVALID",
            "qualifiedCaseIds": "CASE_DENOMINATOR_INVALID",
            "caseId": "CASE_DENOMINATOR_INVALID",
        }
        for index, (field, replacement) in enumerate(mutations):
            with self.subTest(field=field, index=index):
                volume = self.build("qualified-gpu-with-resident-fallback", f"provenance-{index}")
                manifest_path = volume / "MANIFEST.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest[field] = replacement
                body = dict(manifest)
                body.pop("volumeId")
                manifest["volumeId"] = mod.content_id("axmheadvolume1", body)
                manifest_path.write_bytes(mod.pretty_json_bytes(manifest))
                code, verdict = self.standalone(volume, self.root / f"foreign-provenance-{index}")
                self.assertEqual(code, 2)
                self.assertEqual(verdict["code"], expected_codes[field])

    def test_builder_rejects_changed_profile_and_catalog_bytes(self) -> None:
        changed_profile = copy.deepcopy(self.profile)
        changed_profile["claimBoundary"] = "Stronger claim."
        profile_path = self.root / "changed-profile.json"
        profile_path.write_bytes(mod.pretty_json_bytes(changed_profile))
        with self.assertRaises(mod.DemoError) as context:
            mod.validate_profile(profile_path)
        self.assertIn(context.exception.code, {"CLAIM_BOUNDARY_INVALID", "PROFILE_PROVENANCE_INVALID"})

        for index, mutation in enumerate(("add", "remove", "rename")):
            catalog = copy.deepcopy(self.catalog)
            if mutation == "add":
                extra = copy.deepcopy(catalog["cases"][0])
                extra["caseId"] = "fifth-unexercised-case"
                catalog["cases"].append(extra)
            elif mutation == "remove":
                catalog["cases"].pop()
            else:
                catalog["cases"][0]["caseId"] = "renamed-case"
            path = self.root / f"changed-catalog-{index}.json"
            path.write_bytes(mod.pretty_json_bytes(catalog))
            with self.assertRaises(mod.DemoError) as catalog_context:
                mod.validate_fixture_catalog(path, self.profile)
            self.assertIn(catalog_context.exception.code, {"CASE_DENOMINATOR_INVALID", "FIXTURE_PROVENANCE_INVALID"})

    def test_verifier_identity_is_refused_before_substituted_code_runs(self) -> None:
        malicious = self.root / "verify_volume.py"
        marker = self.root / "MALICIOUS-RAN"
        malicious.write_text(
            f"from pathlib import Path\nPath({str(marker)!r}).write_text('ran')\nprint('{{\"status\":\"PASS\"}}')\n",
            encoding="utf-8",
        )
        with self.assertRaises(mod.DemoError) as context:
            mod.assert_trusted_verifier(malicious)
        self.assertEqual(context.exception.code, "VERIFIER_IDENTITY_INVALID")
        self.assertFalse(marker.exists())

        malicious_volume = self.build("qualified-gpu-with-resident-fallback", "malicious-verifier-volume")
        embedded = malicious_volume / "RECOVERY/verify_volume.py"
        embedded.write_bytes(malicious.read_bytes())
        manifest_path = malicious_volume / "MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["verifierSha256"] = mod.sha256_bytes(embedded.read_bytes())
        manifest_path.write_bytes(mod.pretty_json_bytes(manifest))
        self.rebind_manifest_file(malicious_volume, "RECOVERY/verify_volume.py")
        with self.assertRaises(mod.DemoError) as embedded_context:
            mod.assert_trusted_verifier(embedded)
        self.assertEqual(embedded_context.exception.code, "VERIFIER_IDENTITY_INVALID")
        self.assertFalse(marker.exists())

        for index, body in enumerate((
            VERIFIER.read_bytes() + b"\n",
            b"print('{\"status\":\"PASS\"}')\n",
        )):
            alternate = self.root / f"alternate-{index}.py"
            alternate.write_bytes(body)
            with self.assertRaises(mod.DemoError):
                mod.assert_trusted_verifier(alternate)

        alternate_path = self.root / "exact-verifier-copy.py"
        alternate_path.write_bytes(VERIFIER.read_bytes())
        self.assertEqual(mod.sha256_bytes(mod.assert_trusted_verifier(alternate_path)), mod.EXPECTED_VERIFIER_SHA256)
        with self.assertRaises(mod.DemoError) as path_context:
            mod.build_volume(
                profile_path=PROFILE,
                catalog_path=FIXTURES,
                case_id="qualified-gpu-with-resident-fallback",
                out=self.root / "path-substitution-volume",
                verifier_source_path=alternate_path,
            )
        self.assertEqual(path_context.exception.code, "VERIFIER_PATH_INVALID")

        volume = self.build("qualified-gpu-with-resident-fallback", "verifier-digest")
        manifest_path = volume / "MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["verifierSha256"] = "3" * 64
        body = dict(manifest)
        body.pop("volumeId")
        manifest["volumeId"] = mod.content_id("axmheadvolume1", body)
        manifest_path.write_bytes(mod.pretty_json_bytes(manifest))
        code, verdict = self.standalone(volume, self.root / "foreign-verifier-digest")
        self.assertEqual(code, 2)
        self.assertEqual(verdict["code"], "VERIFIER_IDENTITY_INVALID")

    def test_existing_output_root_is_refused(self) -> None:
        out = self.root / "volume"
        out.mkdir()
        with self.assertRaises(mod.DemoError) as context:
            mod.build_volume(profile_path=PROFILE, catalog_path=FIXTURES, case_id="qualified-gpu-with-resident-fallback", out=out, verifier_source_path=VERIFIER)
        self.assertEqual(context.exception.code, "OUTPUT_EXISTS")


if __name__ == "__main__":
    unittest.main(verbosity=2)
