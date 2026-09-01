from __future__ import annotations

import copy
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve()
ANCHOR = HERE.parents[1]
REPOSITORY = HERE.parents[3]
PROFILE_PATH = ANCHOR / "axm-head-browser-audition-operation-plan-profile-01.json"
FIXTURE_PATH = ANCHOR / "fixtures/axm-head-browser-audition-operation-plan-cases-01.json"
TOOL_PATH = ANCHOR / "axm_head_browser_audition_operation_plan_01.py"
VERIFIER_PATH = ANCHOR / "verify_axm_head_browser_audition_operation_plan_01.py"
BOOTSTRAP_PATH = ANCHOR / "verify_axm_head_browser_audition_operation_plan_01_bootstrap.py"

spec = importlib.util.spec_from_file_location("operation_plan_tool", TOOL_PATH)
tool = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(tool)


def clone_minimal(destination: pathlib.Path) -> pathlib.Path:
    destination.mkdir(parents=True)
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    for relative in [*profile["sourceMembers"], *(row["path"] for row in profile["dependencies"])]:
        source = REPOSITORY / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    return destination


def fixture_bindings(case_id: str = "pass-two-seat-plan") -> dict:
    catalog = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    for row in [*catalog["positiveCases"], *catalog["hostileCases"]]:
        if row["caseId"] == case_id:
            return copy.deepcopy(row["bindings"])
    raise KeyError(case_id)


class OperationPlanWitnesses(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile = tool.validate_profile(PROFILE_PATH)
        cls.fixtures = tool.validate_fixture_catalog(FIXTURE_PATH, cls.profile)
        cls.operator = tool.load_operator_module(REPOSITORY)

    def build(self, repository: pathlib.Path = REPOSITORY) -> tuple[tempfile.TemporaryDirectory, pathlib.Path, dict]:
        temp = tempfile.TemporaryDirectory(prefix="axm-operation-plan-test-")
        output = pathlib.Path(temp.name) / "extension"
        build = tool.build_extension(repository / self.profile["sourceMembers"][2], repository, output)
        return temp, output, build

    def test_001_profile_validates(self):
        self.assertEqual(self.profile["profileId"], tool.PROFILE_ID)

    def test_002_fixture_catalog_validates(self):
        self.assertEqual(self.profile["fixtureCounts"]["total"], 24)

    def test_003_campaign_passes(self):
        result = tool.campaign(self.profile, self.fixtures, self.operator)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["outcomeCounts"], {"PASS": 3, "REFUSED": 21})

    def test_004_bindings_validate(self):
        value = tool.validate_bindings(fixture_bindings(), self.operator)
        self.assertTrue(value["bindingsId"].startswith("axmoperationbindings_"))

    def test_005_plan_compiles_deterministically(self):
        bindings = tool.validate_bindings(fixture_bindings(), self.operator)
        first = tool.compile_plan(bindings)
        second = tool.compile_plan(bindings)
        self.assertEqual(first, second)
        self.assertEqual(first["planId"], "axmoperationplan_998ef5491418acdf16bd811ca9d2ee647b551fc59ae50a934c2aeaf10b3350b9")

    def test_006_plan_validates(self):
        bindings = tool.validate_bindings(fixture_bindings(), self.operator)
        plan = tool.compile_plan(bindings)
        self.assertEqual(tool.validate_plan(plan, bindings), plan)

    def test_007_fixed_first_barrier_precedes_probe_marks(self):
        plan = tool.compile_plan(tool.validate_bindings(fixture_bindings(), self.operator))
        self.assertEqual(plan["steps"][0]["kind"], "console-status")
        self.assertEqual(plan["steps"][1]["code"], "BEFORE_PLAN_EXECUTION")
        self.assertEqual(plan["steps"][2]["method"], "markAvailability")

    def test_008_export_barrier_precedes_capture(self):
        plan = tool.compile_plan(tool.validate_bindings(fixture_bindings(), self.operator))
        self.assertEqual(plan["steps"][-2]["code"], "BEFORE_CAPTURE_EXPORT")
        self.assertEqual(plan["steps"][-1]["method"], "exportCapture")

    def test_009_member_results_are_saved_and_reused(self):
        plan = tool.compile_plan(tool.validate_bindings(fixture_bindings(), self.operator))
        saves = {row.get("saveResultAs") for row in plan["steps"] if row.get("saveResultAs")}
        refs = {alias for row in plan["steps"] for alias in (row.get("resultRefs") or {}).values()}
        self.assertTrue(refs.issubset(saves))

    def test_010_receipt_order_is_exact(self):
        plan = tool.compile_plan(tool.validate_bindings(fixture_bindings(), self.operator))
        observed = [row["receiptKind"] for row in plan["steps"] if "receiptKind" in row]
        self.assertEqual(observed, list(tool.RECEIPT_KINDS))

    def test_011_probe_invocations_fit_operator_session(self):
        plan = tool.compile_plan(tool.validate_bindings(fixture_bindings(), self.operator))
        self.assertLessEqual(plan["probeInvocationCount"] + 4, tool.MAX_SESSION_REQUESTS)

    def test_012_source_set_is_content_bound(self):
        result = tool.source_set(self.profile, REPOSITORY)
        self.assertEqual(result["sourceMemberCount"], len(tool.SOURCE_MEMBERS))
        self.assertTrue(result["sourceBindingId"].startswith("axmoperationplansource_"))

    def test_013_dependencies_are_exact(self):
        rows = tool.verify_dependencies(self.profile, REPOSITORY)
        self.assertEqual(tuple(rows), tool.DEPENDENCIES)

    def test_014_extension_builds(self):
        temp, output, build = self.build()
        self.addCleanup(temp.cleanup)
        self.assertEqual(build["memberCount"], len(tool.EXTENSION_PAYLOAD_MEMBERS))
        self.assertEqual({path.name for path in output.iterdir()}, set(tool.EXTENSION_MEMBERS))

    def test_015_extension_verifies(self):
        temp, output, _ = self.build()
        self.addCleanup(temp.cleanup)
        verdict = tool.verify_extension(PROFILE_PATH, REPOSITORY, output)
        self.assertEqual(verdict["status"], "PASS")

    def test_016_independent_verifier_passes(self):
        temp, output, _ = self.build()
        self.addCleanup(temp.cleanup)
        completed = subprocess.run([sys.executable, str(VERIFIER_PATH), str(PROFILE_PATH), str(REPOSITORY), str(output)], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["status"], "PASS")

    def test_017_bootstrap_verifier_passes(self):
        temp, output, _ = self.build()
        self.addCleanup(temp.cleanup)
        completed = subprocess.run([sys.executable, str(BOOTSTRAP_PATH), str(VERIFIER_PATH), str(PROFILE_PATH), str(REPOSITORY), str(output)], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        verdict = json.loads(completed.stdout)
        self.assertTrue(verdict["bootstrapAuthenticated"])
        self.assertTrue(verdict["storedVerifierMemberBound"])

    def test_018_repository_local_output_refused(self):
        output = REPOSITORY / ".operation-plan-output-must-not-exist"
        if output.exists(): shutil.rmtree(output)
        with self.assertRaises(tool.PlanError) as caught:
            tool.build_extension(PROFILE_PATH, REPOSITORY, output)
        self.assertEqual(caught.exception.code, "REPOSITORY_LOCAL_OUTPUT_REFUSED")

    def test_019_existing_output_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            output = pathlib.Path(temp) / "existing"
            output.mkdir()
            with self.assertRaises(tool.PlanError) as caught:
                tool.build_extension(PROFILE_PATH, REPOSITORY, output)
            self.assertEqual(caught.exception.code, "OUTPUT_ALREADY_EXISTS")

    def test_020_dependency_tamper_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = clone_minimal(pathlib.Path(temp) / "repo")
            target = repo / tool.DEPENDENCIES[2]["path"]
            target.write_bytes(target.read_bytes() + b"\n")
            with self.assertRaises(tool.PlanError) as caught:
                tool.verify_dependencies(self.profile, repo)
            self.assertEqual(caught.exception.code, "DEPENDENCY_BYTES_INVALID")

    def test_021_extension_payload_tamper_refused(self):
        temp, output, _ = self.build()
        self.addCleanup(temp.cleanup)
        target = output / "browser_audition_operation_plan_panel.js"
        target.write_bytes(target.read_bytes() + b"\n")
        with self.assertRaises(tool.PlanError) as caught:
            tool.verify_extension(PROFILE_PATH, REPOSITORY, output)
        self.assertIn(caught.exception.code, {"SOURCE_COPY_INVALID", "BUILD_MANIFEST_INVALID"})

    def test_022_extra_extension_member_refused(self):
        temp, output, _ = self.build()
        self.addCleanup(temp.cleanup)
        (output / "extra.txt").write_text("extra\n")
        with self.assertRaises(tool.PlanError) as caught:
            tool.verify_extension(PROFILE_PATH, REPOSITORY, output)
        self.assertEqual(caught.exception.code, "EXTENSION_MEMBER_DENOMINATOR_INVALID")

    def test_023_missing_extension_member_refused(self):
        temp, output, _ = self.build()
        self.addCleanup(temp.cleanup)
        (output / "browser_audition_operation_plan_panel.css").unlink()
        with self.assertRaises(tool.PlanError) as caught:
            tool.verify_extension(PROFILE_PATH, REPOSITORY, output)
        self.assertEqual(caught.exception.code, "EXTENSION_MEMBER_DENOMINATOR_INVALID")

    def test_024_manifest_tamper_refused(self):
        temp, output, _ = self.build()
        self.addCleanup(temp.cleanup)
        manifest = json.loads((output / "manifest.json").read_text())
        manifest["name"] = "Changed"
        (output / "manifest.json").write_text(json.dumps(manifest))
        with self.assertRaises(tool.PlanError) as caught:
            tool.verify_extension(PROFILE_PATH, REPOSITORY, output)
        self.assertEqual(caught.exception.code, "EXTENSION_MANIFEST_INVALID")

    def test_025_build_manifest_tamper_refused(self):
        temp, output, _ = self.build()
        self.addCleanup(temp.cleanup)
        build = json.loads((output / "build-manifest.json").read_text())
        build["extensionId"] = "axmoperationplanextension_" + "0" * 64
        (output / "build-manifest.json").write_text(json.dumps(build))
        with self.assertRaises(tool.PlanError) as caught:
            tool.verify_extension(PROFILE_PATH, REPOSITORY, output)
        self.assertEqual(caught.exception.code, "BUILD_MANIFEST_INVALID")

    def test_026_supplier_identity_in_extension_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = clone_minimal(pathlib.Path(temp) / "repo")
            target = repo / "mating_surface/anchor_node/browser_audition_operation_plan_panel.js"
            target.write_text(target.read_text() + "\n// " + "swarm" + "llm\n")
            output = pathlib.Path(temp) / "extension"
            build = tool.build_extension(repo / self.profile["sourceMembers"][2], repo, output)
            build_path = output / "build-manifest.json"
            # Builder is content-bound to the modified source; verifier must still reject supplier identity.
            with self.assertRaises(tool.PlanError) as caught:
                tool.verify_extension(repo / self.profile["sourceMembers"][2], repo, output)
            self.assertEqual(caught.exception.code, "SUPPLIER_IDENTITY_ESCAPED_EXTENSION")

    def test_027_network_client_in_extension_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = clone_minimal(pathlib.Path(temp) / "repo")
            target = repo / "mating_surface/anchor_node/browser_audition_operation_plan_panel.js"
            target.write_text(target.read_text() + "\n// fetch(\n")
            output = pathlib.Path(temp) / "extension"
            tool.build_extension(repo / self.profile["sourceMembers"][2], repo, output)
            with self.assertRaises(tool.PlanError) as caught:
                tool.verify_extension(repo / self.profile["sourceMembers"][2], repo, output)
            self.assertEqual(caught.exception.code, "EXTENSION_EXTERNAL_SURFACE_FORBIDDEN")

    def test_028_node_contract_validates_python_plan(self):
        bindings = fixture_bindings()
        plan = tool.compile_plan(tool.validate_bindings(bindings, self.operator))
        with tempfile.TemporaryDirectory() as temp:
            b = pathlib.Path(temp) / "bindings.json"; p = pathlib.Path(temp) / "plan.json"
            b.write_text(json.dumps(bindings)); p.write_text(json.dumps(plan))
            script = f"""
const fs=require('fs'),vm=require('vm'),crypto=require('crypto');
global.crypto=crypto.webcrypto;
vm.runInThisContext(fs.readFileSync({json.dumps(str(ANCHOR / 'browser_physical_audition_operator_contract.js'))},'utf8'));
vm.runInThisContext(fs.readFileSync({json.dumps(str(ANCHOR / 'browser_audition_operation_plan_contract.js'))},'utf8'));
(async()=>{{const b=JSON.parse(fs.readFileSync({json.dumps(str(b))}));const p=JSON.parse(fs.readFileSync({json.dumps(str(p))}));const v=await AXMOperationPlanContract.validateBundle(p,b);console.log(JSON.stringify(v));}})().catch(e=>{{console.error(e.code,e.message);process.exit(2);}});
"""
            completed = subprocess.run(["node", "-e", script], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertEqual(json.loads(completed.stdout)["status"], "PASS")

    def test_029_node_contract_refuses_plan_mutation(self):
        bindings = fixture_bindings()
        plan = tool.compile_plan(tool.validate_bindings(bindings, self.operator))
        plan["steps"][0]["kind"] = "probe-call"
        with tempfile.TemporaryDirectory() as temp:
            b = pathlib.Path(temp) / "b.json"; p = pathlib.Path(temp) / "p.json"
            b.write_text(json.dumps(bindings)); p.write_text(json.dumps(plan))
            script = f"""
const fs=require('fs'),vm=require('vm'),crypto=require('crypto');global.crypto=crypto.webcrypto;
vm.runInThisContext(fs.readFileSync({json.dumps(str(ANCHOR / 'browser_physical_audition_operator_contract.js'))},'utf8'));
vm.runInThisContext(fs.readFileSync({json.dumps(str(ANCHOR / 'browser_audition_operation_plan_contract.js'))},'utf8'));
(async()=>{{try{{await AXMOperationPlanContract.validateBundle(JSON.parse(fs.readFileSync({json.dumps(str(p))})),JSON.parse(fs.readFileSync({json.dumps(str(b))})));process.exit(3);}}catch(e){{console.log(e.code);}}}})();
"""
            completed = subprocess.run(["node", "-e", script], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0)
            self.assertEqual(completed.stdout.strip(), "PLAN_NOT_DETERMINISTIC")

    def test_030_panel_has_no_persistent_storage(self):
        source = (ANCHOR / "browser_audition_operation_plan_panel.js").read_text(encoding="utf-8").lower()
        for token in ("localstorage", "sessionstorage", "indexeddb", "chrome.storage"):
            self.assertNotIn(token, source)

    def test_031_panel_has_partial_capture_stop(self):
        source = (ANCHOR / "browser_audition_operation_plan_panel.js").read_text(encoding="utf-8")
        self.assertIn("HALTED_PARTIAL_CAPTURE", source)
        self.assertIn("Discard this page ledger", source)

    def test_032_panel_requires_two_barriers(self):
        source = (ANCHOR / "browser_audition_operation_plan_panel.js").read_text(encoding="utf-8")
        contract = (ANCHOR / "browser_audition_operation_plan_contract.js").read_text(encoding="utf-8")
        self.assertIn("acknowledgeBarrier", source)
        self.assertIn("BEFORE_PLAN_EXECUTION", contract)
        self.assertIn("BEFORE_CAPTURE_EXPORT", contract)

    def test_033_profile_contains_no_supplier_identity(self):
        data = PROFILE_PATH.read_bytes().lower()
        self.assertNotIn(b"swarm" + b"llm", data)
        self.assertNotIn(b"neha" + b"nth", data)

    def test_034_javascript_and_python_fixture_campaigns_agree(self):
        script = f"""
const fs=require('fs'),vm=require('vm'),crypto=require('crypto');global.crypto=crypto.webcrypto;
vm.runInThisContext(fs.readFileSync({json.dumps(str(ANCHOR / 'browser_physical_audition_operator_contract.js'))},'utf8'));
vm.runInThisContext(fs.readFileSync({json.dumps(str(ANCHOR / 'browser_audition_operation_plan_contract.js'))},'utf8'));
const fixtures=JSON.parse(fs.readFileSync({json.dumps(str(FIXTURE_PATH))},'utf8'));
(async()=>{{
  for (const row of fixtures.positiveCases) {{
    const plan=await AXMOperationPlanContract.compilePlan(row.bindings);
    await AXMOperationPlanContract.validateBundle(plan,row.bindings);
  }}
  for (const row of fixtures.hostileCases) {{
    let code=null;
    try {{
      const plan=row.plan || await AXMOperationPlanContract.compilePlan(row.bindings);
      await AXMOperationPlanContract.validateBundle(plan,row.bindings);
    }} catch (error) {{ code=error.code; }}
    if (code !== row.expectedCode) throw new Error(`${{row.caseId}}:${{code}}:${{row.expectedCode}}`);
  }}
  console.log(JSON.stringify({{status:'PASS',count:fixtures.positiveCases.length+fixtures.hostileCases.length}}));
}})().catch(error=>{{console.error(error.stack||error);process.exit(2);}});
"""
        completed = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(json.loads(completed.stdout), {"status": "PASS", "count": 24})


def add_fixture_witnesses() -> None:
    catalog = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    for row in catalog["positiveCases"]:
        case_id = row["caseId"]
        def positive(self, row=copy.deepcopy(row)):
            bindings = tool.validate_bindings(row["bindings"], self.operator)
            plan = tool.compile_plan(bindings)
            self.assertEqual(tool.validate_plan(plan, bindings)["planId"], plan["planId"])
        setattr(OperationPlanWitnesses, f"test_fixture_positive_{case_id.replace('-', '_')}", positive)
    for row in catalog["hostileCases"]:
        case_id = row["caseId"]
        def hostile(self, row=copy.deepcopy(row)):
            with self.assertRaises(tool.PlanError) as caught:
                bindings = tool.validate_bindings(row["bindings"], self.operator)
                plan = row.get("plan") or tool.compile_plan(bindings)
                tool.validate_plan(plan, bindings)
            self.assertEqual(caught.exception.code, row["expectedCode"])
        setattr(OperationPlanWitnesses, f"test_fixture_hostile_{case_id.replace('-', '_')}", hostile)


add_fixture_witnesses()

if __name__ == "__main__":
    unittest.main()
