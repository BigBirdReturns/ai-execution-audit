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
import axm_head_distributed_inference_commodity as mod

PROFILE = ROOT / "axm-head-distributed-inference-commodity-profile-01.json"
SUPPLIERS = ROOT / "fixtures" / "axm-head-distributed-inference-suppliers-01.json"
FIXTURES = ROOT / "fixtures" / "axm-head-distributed-inference-commodity-cases-01.json"
TOOL = ROOT / "axm_head_distributed_inference_commodity.py"
REPO = ROOT.parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "axm-head-distributed-inference-commodity-01.yml"
DOCUMENT = ROOT / "AXM-HEAD-DISTRIBUTED-INFERENCE-COMMODITY-01.md"
PRODUCT_PATHS = (
    ".github/workflows/axm-head-distributed-inference-commodity-01.yml",
    "mating_surface/anchor_node/AXM-HEAD-DISTRIBUTED-INFERENCE-COMMODITY-01.md",
    "mating_surface/anchor_node/axm-head-distributed-inference-commodity-profile-01.json",
    "mating_surface/anchor_node/axm_head_distributed_inference_commodity.py",
    "mating_surface/anchor_node/conformance/test_axm_head_distributed_inference_commodity.py",
    "mating_surface/anchor_node/fixtures/axm-head-distributed-inference-commodity-cases-01.json",
    "mating_surface/anchor_node/fixtures/axm-head-distributed-inference-suppliers-01.json",
)


class CommodityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="distributed-inference-")
        self.root = Path(self.temp.name)
        self.profile = mod.validate_profile(PROFILE)
        self.suppliers = mod.validate_supplier_catalog(SUPPLIERS, self.profile)
        self.fixtures = mod.validate_fixture_catalog(FIXTURES, self.profile, self.suppliers)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def decision(self, case_id: str) -> dict:
        return mod.decide_case(mod.find_case(self.fixtures, case_id), self.profile, self.suppliers)

    def write(self, name: str, value: dict) -> Path:
        path = self.root / name
        path.write_bytes(mod.pretty_bytes(value))
        return path

    def test_profile_supplier_and_denominators(self) -> None:
        self.assertEqual(self.profile["sourceFloor"], mod.SOURCE_FLOOR)
        self.assertEqual(self.profile["commodityInterface"], mod.INTERFACE)
        self.assertEqual(tuple(self.profile["terminalStates"]), mod.TERMINALS)
        self.assertEqual(tuple(self.profile["fixtureCaseIds"]), mod.CASE_IDS)
        self.assertIn("memory is never summed", self.profile["noMemoryPoolingLaw"])
        self.assertIn("does not name SwarmLLM", self.profile["supplierNeutralityLaw"])
        row = self.suppliers["suppliers"][0]
        self.assertEqual(
            (row["supplierId"], row["actor"], row["product"]),
            (mod.PUBLIC_SUPPLIER_ID, "Nehanth Narendrula", "SwarmLLM"),
        )
        self.assertEqual(row["status"], "OBSERVED_CANDIDATE")
        self.assertEqual((len(row["evidence"]), len(row["missingProperties"])), (3, 9))
        self.assertEqual([case["caseId"] for case in self.fixtures["cases"]], list(mod.CASE_IDS))

    def test_campaign_and_public_claim_boundary(self) -> None:
        result = mod.campaign(self.profile, self.suppliers, self.fixtures)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["caseCount"], 12)
        self.assertEqual(
            result["terminalCounts"],
            {"QUALIFIED_ASSEMBLY": 5, "QUALIFICATION_PLAN": 3, "HOLD": 4},
        )
        self.assertFalse(result["publicSwarmLLMQualified"])
        self.assertFalse(result["actualSupplierQualified"])
        self.assertFalse(result["executionOccurred"])
        public = self.decision(mod.PUBLIC_CASE_ID)
        self.assertEqual(public["terminal"], "QUALIFICATION_PLAN")
        self.assertIsNone(public["selectedRouteId"])

    def test_closed_route_outcomes(self) -> None:
        for case_id in mod.CASE_IDS:
            terminal, route_id, reasons = mod.OUTCOMES[case_id]
            with self.subTest(case_id=case_id):
                decision = self.decision(case_id)
                self.assertEqual(decision["terminal"], terminal)
                self.assertEqual(decision["selectedRouteId"], route_id)
                self.assertEqual(decision["reasonCodes"], list(reasons))
                self.assertFalse(decision["actualSupplierQualified"])
                self.assertFalse(decision["publicSwarmLLMQualified"])
                self.assertFalse(decision["executionOccurred"])

    def test_synthetic_neutrality_and_local_fallback(self) -> None:
        synthetic = self.decision(mod.CASE_IDS[0])
        substitute = self.decision(mod.CASE_IDS[6])
        self.assertTrue(synthetic["syntheticConformanceOnly"])
        self.assertTrue(substitute["supplierNeutral"])
        self.assertEqual(self.decision(mod.CASE_IDS[10])["selectedRouteId"], "route:local-fast@fixture")
        self.assertEqual(self.decision(mod.CASE_IDS[11])["selectedRouteId"], "route:local-fallback@fixture")

    def test_floor_projection_puts_nehanth_on_floor_truthfully(self) -> None:
        floor = mod.floor_projection(self.profile, self.suppliers, self.fixtures)
        self.assertEqual(floor["supplierCount"], 1)
        row = floor["suppliers"][0]
        self.assertEqual((row["actor"], row["product"]), ("Nehanth Narendrula", "SwarmLLM"))
        self.assertEqual(
            (row["catalogStatus"], row["status"]),
            ("OBSERVED_CANDIDATE", "QUALIFICATION_PLAN"),
        )
        self.assertFalse(row["actualSupplierQualified"])
        self.assertFalse(floor["executionOccurred"])
        self.assertFalse(floor["physicalEstateQualified"])
        self.assertEqual(floor["missionAuthority"], "none")

    def test_cli_campaign_and_floor(self) -> None:
        for command in ("campaign", "floor"):
            with self.subTest(command=command):
                result = subprocess.run(
                    [sys.executable, str(TOOL), command, str(PROFILE), str(SUPPLIERS), str(FIXTURES)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertEqual((result.returncode, result.stderr), (0, b""))
                body = json.loads(result.stdout.decode("utf-8"))
                self.assertFalse(body["executionOccurred"])

    def test_profile_and_supplier_mutations_are_refused(self) -> None:
        profile = copy.deepcopy(self.profile)
        profile["sourceFloor"]["commit"] = "0" * 40
        with self.assertRaises(mod.CommodityError) as context:
            mod.validate_profile(self.write("profile.json", profile))
        self.assertEqual(context.exception.code, "SOURCE_FLOOR_INVALID")
        suppliers = copy.deepcopy(self.suppliers)
        suppliers["suppliers"].append(copy.deepcopy(suppliers["suppliers"][0]))
        with self.assertRaises(mod.CommodityError) as context:
            mod.validate_supplier_catalog(self.write("suppliers.json", suppliers), self.profile)
        self.assertEqual(context.exception.code, "SUPPLIER_DENOMINATOR_INVALID")

    def test_case_denominator_expansion_is_refused(self) -> None:
        fixtures = copy.deepcopy(self.fixtures)
        fixtures["cases"].append(copy.deepcopy(fixtures["cases"][0]))
        with self.assertRaises(mod.CommodityError) as context:
            mod.validate_fixture_catalog(
                self.write("fixtures.json", fixtures),
                self.profile,
                self.suppliers,
            )
        self.assertEqual(context.exception.code, "CASE_DENOMINATOR_INVALID")


class WorkflowQualificationTests(unittest.TestCase):
    @staticmethod
    def workflow() -> str:
        return WORKFLOW.read_text(encoding="utf-8")

    def test_workflow_uses_explicit_coordinate_matrix_without_stdin_loop(self) -> None:
        workflow = self.workflow()
        self.assertIn(
            "coordinate: ${{ fromJSON(github.event_name == 'pull_request' && '[\"head\",\"merge\"]' || '[\"source\"]') }}",
            workflow,
        )
        self.assertIn("matrix.coordinate", workflow)
        self.assertNotIn("while IFS=", workflow)
        self.assertNotIn("COORDINATES=", workflow)
        self.assertNotIn("done <", workflow)

    def test_workflow_materializes_all_seven_members_from_exact_git_blobs(self) -> None:
        workflow = self.workflow()
        self.assertIn('subprocess.check_output(["git", "cat-file", "blob"', workflow)
        self.assertIn("materialized {len(product_paths)} exact product members", workflow)
        for relative in PRODUCT_PATHS:
            with self.subTest(relative=relative):
                self.assertGreaterEqual(workflow.count(f'"{relative}"'), 3)

    def test_workflow_cannot_report_pass_without_executed_coordinate_verdict(self) -> None:
        workflow = self.workflow()
        self.assertIn('"qualificationExecuted": True', workflow)
        self.assertIn('row.get("qualificationExecuted") is not True', workflow)
        self.assertIn("a coordinate reported PASS without executed qualification", workflow)
        self.assertIn("coordinate-verdict.json", workflow)
        self.assertIn("source-identity.json", workflow)

    def test_workflow_uploads_every_job_and_requires_cross_coordinate_comparison(self) -> None:
        workflow = self.workflow()
        self.assertIn("compare:\n    needs: qualify", workflow)
        self.assertIn("actions/upload-artifact@v4", workflow)
        self.assertIn("actions/download-artifact@v4", workflow)
        self.assertIn("expected_jobs = 2 * len(expected_coordinates)", workflow)
        self.assertIn('("head", "merge") if os.environ["EVENT_NAME"] == "pull_request" else ("source",)', workflow)
        self.assertIn("qualificationExecutedEverywhere", workflow)
        self.assertIn("cross-coordinate-verdict.json", workflow)

    def test_workflow_hygiene_is_read_only_and_detectors_do_not_match_themselves(self) -> None:
        workflow = self.workflow()
        self.assertIn("permissions:\n  contents: read\n", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("git push origin", workflow)
        self.assertNotIn("pull_request_target", workflow)
        self.assertNotIn(r"\b(?:requests|urllib3|aiohttp|httpx)\b", workflow)
        self.assertIn('"requ" + "ests"', workflow)
        self.assertIn('"contents" + ": write"', workflow)
        self.assertIn('"pull_request" + "_target"', workflow)

    def test_workflow_freezes_closed_witness_and_campaign_denominators(self) -> None:
        workflow = self.workflow()
        self.assertIn('grep -F "Ran 15 tests"', workflow)
        self.assertIn('int(match.group(1)) != 15', workflow)
        self.assertIn('"unitWitnesses": 15', workflow)
        self.assertIn('"campaignCases": 12', workflow)
        self.assertIn('"HOLD": 4', workflow)
        self.assertIn('"QUALIFICATION_PLAN": 3', workflow)
        self.assertIn('"QUALIFIED_ASSEMBLY": 5', workflow)

    def test_document_records_the_noop_repair_without_promoting_swarmllm(self) -> None:
        document = DOCUMENT.read_text(encoding="utf-8")
        self.assertIn("PR #91", document)
        self.assertIn("8d18d2c4b6df505751574f219c8c8dd69877a6df", document)
        self.assertIn("the loop read no coordinate rows", document)
        self.assertIn("hosted qualification claim is withdrawn", document)
        self.assertIn("actual qualification: false", document)
        self.assertIn("public SwarmLLM row remains", document)


if __name__ == "__main__":
    unittest.main()
