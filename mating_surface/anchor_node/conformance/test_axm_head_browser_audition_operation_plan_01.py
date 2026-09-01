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


def bindings_with_probe_invocations(probe_invocation_count: int) -> dict:
    bindings = fixture_bindings()
    base_count = sum(row["kind"] == "probe-call" for row in tool.expected_steps(bindings))
    if probe_invocation_count < base_count:
        raise ValueError(f"probe invocation target {probe_invocation_count} is below base {base_count}")
    token_count = len(bindings["values"]["tokenMarks"]) + probe_invocation_count - base_count
    if token_count > tool.MAX_TOKEN_MARKS:
        raise ValueError(f"token target {token_count} exceeds {tool.MAX_TOKEN_MARKS}")
    bindings["values"]["tokenMarks"] = [
        {"index": index, "monotonicMs": 1010 + index * 10}
        for index in range(token_count)
    ]
    bindings["values"]["equivalence"]["outputTokenCount"] = token_count
    bindings["bindingsId"] = tool.content_identity(
        "axmoperationbindings",
        tool.normalized_bindings_body(bindings),
    )
    return bindings


def run_contract_compile(bindings: dict) -> dict:
    with tempfile.TemporaryDirectory(prefix="axm-operation-plan-contract-") as temp:
        binding_path = pathlib.Path(temp) / "bindings.json"
        binding_path.write_text(json.dumps(bindings), encoding="utf-8")
        script = f"""
const fs=require('fs'),vm=require('vm'),crypto=require('crypto');
global.crypto=crypto.webcrypto;
vm.runInThisContext(fs.readFileSync({json.dumps(str(ANCHOR / 'browser_physical_audition_operator_contract.js'))},'utf8'));
vm.runInThisContext(fs.readFileSync({json.dumps(str(ANCHOR / 'browser_audition_operation_plan_contract.js'))},'utf8'));
(async()=>{{
  const bindings=JSON.parse(fs.readFileSync({json.dumps(str(binding_path))},'utf8'));
  try {{
    const plan=await AXMOperationPlanContract.compilePlan(bindings);
    const requests=plan.probeInvocationCount * AXMOperationPlanContract.SESSION_REQUESTS_PER_PROBE_INVOCATION + AXMOperationPlanContract.SESSION_REQUEST_RESERVE;
    console.log(JSON.stringify({{status:'PASS',probeInvocationCount:plan.probeInvocationCount,sessionRequestCount:requests}}));
  }} catch (error) {{
    console.log(JSON.stringify({{status:'REFUSED',code:error.code || 'ERROR'}}));
  }}
}})().catch((error)=>{{console.error(error.stack || error);process.exit(2);}});
"""
        completed = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        if completed.returncode != 0:
            raise AssertionError(completed.stdout + completed.stderr)
        return json.loads(completed.stdout)


def run_panel_harness(body: str) -> dict:
    panel_path = ANCHOR / "browser_audition_operation_plan_panel.js"
    operator_path = ANCHOR / "browser_physical_audition_operator_contract.js"
    plan_path = ANCHOR / "browser_audition_operation_plan_contract.js"
    script = f"""
const fs = require('fs');
const vm = require('vm');
const cryptoModule = require('crypto');
global.crypto = cryptoModule.webcrypto;
class Element {{
  constructor(id = '') {{ this.id=id; this.disabled=false; this.hidden=false; this.textContent=''; this.className=''; this.children=[]; this.files=[]; this.listeners={{}}; this.clicked=false; }}
  addEventListener(kind, fn) {{ this.listeners[kind]=fn; }}
  prepend(row) {{ this.children.unshift(row); }}
  get lastElementChild() {{ return this.children.length ? this.children[this.children.length - 1] : null; }}
  remove() {{ this.removed=true; }}
  click() {{ this.clicked=true; }}
}}
const elements = new Map();
global.document = {{
  querySelector(selector) {{ if (!elements.has(selector)) elements.set(selector, new Element(selector)); return elements.get(selector); }},
  createElement(tag) {{ return new Element(tag); }},
}};
const ports = [];
let portFactory = null;
global.chrome = {{
  runtime: {{
    connect(options) {{
      if (portFactory) return portFactory(options);
      const messageListeners=[]; const disconnectListeners=[];
      const port={{
        name: options.name,
        onMessage: {{ addListener(fn) {{ messageListeners.push(fn); }} }},
        onDisconnect: {{ addListener(fn) {{ disconnectListeners.push(fn); }} }},
        postMessage() {{ throw new Error('unconfigured port'); }},
        disconnect() {{ disconnectListeners.forEach((fn) => fn()); }},
        __messageListeners: messageListeners,
        __disconnectListeners: disconnectListeners,
      }};
      ports.push(port);
      return port;
    }},
  }},
  tabs: {{ query: async () => [{{id: 7}}] }},
}};
let lastBlob = null;
const NativeBlob = global.Blob;
global.Blob = class extends NativeBlob {{ constructor(parts, options) {{ super(parts, options); lastBlob=this; }} }};
const nativeURL = global.URL;
global.URL = {{ createObjectURL() {{ return 'blob:test'; }}, revokeObjectURL() {{}}, }};
vm.runInThisContext(fs.readFileSync({json.dumps(str(operator_path))}, 'utf8'));
vm.runInThisContext(fs.readFileSync({json.dumps(str(plan_path))}, 'utf8'));
const panelSource = fs.readFileSync({json.dumps(str(panel_path))}, 'utf8') + `\n;globalThis.__AXM_PANEL_TEST__={{state,el,refreshControls,resetExecutionProgress,settleSessionLoss,discardSessionState,disconnectCurrentPort,releaseFailedOpenSession,connectPort,openSession,requireHealthyInspection,requirePostInvocationInspection,requirePristineCapture,serializeCaptureForDownload,downloadCapture,runPlan,acknowledgeBarrier,closeSession}};`;
vm.runInThisContext(panelSource);
(async () => {{
  const test = globalThis.__AXM_PANEL_TEST__;
  const setPortFactory = (value) => {{ portFactory = value; }};
  {body}
}})().catch((error) => {{ console.error(error.stack || error); process.exit(2); }}).finally(() => {{ global.URL = nativeURL; }});
"""
    completed = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    if completed.returncode != 0:
        raise AssertionError(completed.stdout + completed.stderr)
    return json.loads(completed.stdout)


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
        self.assertEqual(first["planId"], "axmoperationplan_4efbcaacc84ecf1e5cd3be5a3c1415ad504a8319e2b162d77daf0b7b0fb6c7d0")

    def test_006_plan_validates(self):
        bindings = tool.validate_bindings(fixture_bindings(), self.operator)
        plan = tool.compile_plan(bindings)
        self.assertEqual(tool.validate_plan(plan, bindings), plan)

    def test_007_fixed_first_barrier_precedes_probe_marks(self):
        plan = tool.compile_plan(tool.validate_bindings(fixture_bindings(), self.operator))
        self.assertEqual(plan["steps"][0]["kind"], "console-status")
        self.assertEqual(plan["steps"][1], {
            "stepId": "step:capture-preflight",
            "kind": "probe-call",
            "method": "exportCapture",
            "literalArgs": {},
            "captureUse": "preflight",
        })
        self.assertEqual(plan["steps"][2]["code"], "BEFORE_PLAN_EXECUTION")
        self.assertEqual(plan["steps"][3]["method"], "markAvailability")

    def test_008_export_barrier_precedes_capture(self):
        plan = tool.compile_plan(tool.validate_bindings(fixture_bindings(), self.operator))
        self.assertEqual(plan["steps"][-2]["code"], "BEFORE_CAPTURE_EXPORT")
        self.assertEqual(plan["steps"][-1]["method"], "exportCapture")
        self.assertEqual(plan["steps"][-1]["captureUse"], "download")

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
        self.assertLessEqual(plan["probeInvocationCount"] * 2 + 4, tool.MAX_SESSION_REQUESTS)

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

    def test_033_pristine_capture_accepts_passive_observations(self):
        result = run_panel_harness(r"""
const capture={schema:'axm-head/browser-probe-private-capture@1',installedBeforeApplication:true,refused:null,events:[{type:'probe-installed'},{type:'fetch-observation'}]};
test.requirePristineCapture(capture);
console.log(JSON.stringify({status:'PASS'}));
""")
        self.assertEqual(result, {"status": "PASS"})

    def test_034_pristine_capture_refuses_prior_plan_mark(self):
        result = run_panel_harness(r"""
let code=null;
try { test.requirePristineCapture({schema:'axm-head/browser-probe-private-capture@1',installedBeforeApplication:true,refused:null,events:[{type:'probe-installed'},{type:'availability-observation'}]}); }
catch (error) { code=error.code; }
console.log(JSON.stringify({code}));
""")
        self.assertEqual(result, {"code": "PROBE_LEDGER_ALREADY_MARKED"})

    def test_035_pristine_capture_refuses_late_installation(self):
        result = run_panel_harness(r"""
let code=null;
try { test.requirePristineCapture({schema:'axm-head/browser-probe-private-capture@1',installedBeforeApplication:false,refused:null,events:[{type:'probe-installed'}]}); }
catch (error) { code=error.code; }
console.log(JSON.stringify({code}));
""")
        self.assertEqual(result, {"code": "PROBE_INSTALLATION_LATE"})

    def test_036_download_checks_the_exact_written_representation(self):
        result = run_panel_harness(r"""
const capture={rows:Array(430000).fill(0)};
const compact=test.serializeCaptureForDownload(capture);
const compactBytes=new TextEncoder().encode(compact).byteLength;
const prettyBytes=new TextEncoder().encode(JSON.stringify(capture,null,2)+'\n').byteLength;
test.downloadCapture(capture);
console.log(JSON.stringify({compactBytes,prettyBytes,blobBytes:lastBlob.size,limit:AXMOperatorContract.MAX_CAPTURE_BYTES}));
""")
        self.assertLessEqual(result["compactBytes"], result["limit"])
        self.assertGreater(result["prettyBytes"], result["limit"])
        self.assertEqual(result["blobBytes"], result["compactBytes"])

    def test_037_download_refuses_actual_bytes_above_ceiling(self):
        result = run_panel_harness(r"""
let code=null;
try { test.serializeCaptureForDownload({rows:Array(530000).fill(0)}); }
catch (error) { code=error.code; }
console.log(JSON.stringify({code}));
""")
        self.assertEqual(result, {"code": "CAPTURE_DOWNLOAD_LIMIT_EXCEEDED"})

    def test_038_pre_mutation_session_loss_resets_execution_cursor(self):
        result = run_panel_harness(r"""
test.state.plan={steps:[{stepId:'a'}]}; test.state.bindings={}; test.state.nextIndex=3; test.state.resultRefs.set('member:a','opaque:'+'1'.repeat(32)); test.state.barrierCode='BEFORE_PLAN_EXECUTION'; test.state.barrierAcknowledged=true; test.state.probeMutationPossible=false; test.state.terminal='AWAITING_OPERATOR_BARRIER';
test.settleSessionLoss('LOADED');
console.log(JSON.stringify({terminal:test.state.terminal,nextIndex:test.state.nextIndex,results:test.state.resultRefs.size,barrier:test.state.barrierCode,mutation:test.state.probeMutationPossible}));
""")
        self.assertEqual(result, {"terminal": "LOADED", "nextIndex": 0, "results": 0, "barrier": None, "mutation": False})

    def test_039_post_mutation_session_loss_seals_partial_capture(self):
        result = run_panel_harness(r"""
test.state.plan={steps:[{stepId:'a'}]}; test.state.bindings={}; test.state.nextIndex=4; test.state.probeMutationPossible=true; test.state.terminal='RUNNING';
test.settleSessionLoss('LOADED'); test.refreshControls();
console.log(JSON.stringify({terminal:test.state.terminal,nextIndex:test.state.nextIndex,loadDisabled:test.el.load.disabled,openDisabled:test.el.open.disabled}));
""")
        self.assertEqual(result, {"terminal": "HALTED_PARTIAL_CAPTURE", "nextIndex": 4, "loadDisabled": True, "openDisabled": True})

    def test_040_full_panel_sequence_preflights_before_mutation_and_halts_after_mark(self):
        bindings = fixture_bindings()
        body = r"""
const bindings=JSON.parse(BINDINGS_JSON);
const plan={steps:[
  {stepId:'step:status-preflight',kind:'console-status'},
  {stepId:'step:capture-preflight',kind:'probe-call',method:'exportCapture',literalArgs:{},captureUse:'preflight'},
  {stepId:'step:barrier-before-execution',kind:'operator-barrier',code:'BEFORE_PLAN_EXECUTION',statement:'review'},
  {stepId:'step:availability',kind:'probe-call',method:'markAvailability',argsRef:'values.availability'},
  {stepId:'step:barrier-before-export',kind:'operator-barrier',code:'BEFORE_CAPTURE_EXPORT',statement:'export'},
]};
const messageListeners=[]; const disconnectListeners=[];
setPortFactory(() => ({
  onMessage:{addListener(fn){messageListeners.push(fn);}},
  onDisconnect:{addListener(fn){disconnectListeners.push(fn);}},
  postMessage(message){
    let response={protocol:AXMOperatorContract.PROTOCOL,status:'PASS',requestId:message.requestId,inspection:{status:'PASS',probeVersion:'1',installedBeforeApplication:true,probeRefused:null,observedEventCount:1}};
    if(message.kind==='invoke' && message.method==='exportCapture') response.result={schema:'axm-head/browser-probe-private-capture@1',installedBeforeApplication:true,refused:null,events:[{type:'probe-installed'}]};
    if(message.kind==='invoke' && message.method==='markAvailability') response.result=null;
    queueMicrotask(()=>messageListeners.forEach(fn=>fn(response)));
  },
}));
test.connectPort(); test.state.plan=plan; test.state.bindings=bindings; test.state.sessionId='session:'+'1'.repeat(32); test.state.tabId=7; test.state.terminal='SESSION_OPEN';
await test.runPlan();
const first={terminal:test.state.terminal,nextIndex:test.state.nextIndex,mutation:test.state.probeMutationPossible};
test.acknowledgeBarrier(); await test.runPlan();
const second={terminal:test.state.terminal,nextIndex:test.state.nextIndex,mutation:test.state.probeMutationPossible};
await test.closeSession();
const third={terminal:test.state.terminal,nextIndex:test.state.nextIndex,mutation:test.state.probeMutationPossible};
console.log(JSON.stringify({first,second,third}));
""".replace("BINDINGS_JSON", json.dumps(json.dumps(bindings)))
        result = run_panel_harness(body)
        self.assertEqual(result["first"], {"terminal": "AWAITING_OPERATOR_BARRIER", "nextIndex": 2, "mutation": False})
        self.assertEqual(result["second"], {"terminal": "AWAITING_OPERATOR_BARRIER", "nextIndex": 4, "mutation": True})
        self.assertEqual(result["third"], {"terminal": "HALTED_PARTIAL_CAPTURE", "nextIndex": 4, "mutation": True})

    def test_041_profile_contains_no_supplier_identity(self):
        data = PROFILE_PATH.read_bytes().lower()
        self.assertNotIn(b"swarm" + b"llm", data)
        self.assertNotIn(b"neha" + b"nth", data)

    def test_042_primary_verifier_requires_pristine_ledger_control(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = clone_minimal(pathlib.Path(temp) / "repo")
            panel = repo / "mating_surface/anchor_node/browser_audition_operation_plan_panel.js"
            panel.write_text(panel.read_text(encoding="utf-8").replace("PROBE_LEDGER_ALREADY_MARKED", "REMOVED_LEDGER_CONTROL"), encoding="utf-8")
            output = pathlib.Path(temp) / "extension"
            tool.build_extension(repo / self.profile["sourceMembers"][2], repo, output)
            with self.assertRaises(tool.PlanError) as caught:
                tool.verify_extension(repo / self.profile["sourceMembers"][2], repo, output)
            self.assertEqual(caught.exception.code, "PANEL_CONTROL_MISSING")

    def test_043_independent_verifier_requires_exact_download_binding(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = clone_minimal(pathlib.Path(temp) / "repo")
            panel = repo / "mating_surface/anchor_node/browser_audition_operation_plan_panel.js"
            panel.write_text(panel.read_text(encoding="utf-8").replace("new Blob([serialized]", "new Blob([serialized + '\\n']"), encoding="utf-8")
            output = pathlib.Path(temp) / "extension"
            tool.build_extension(repo / self.profile["sourceMembers"][2], repo, output)
            completed = subprocess.run(
                [sys.executable, str(VERIFIER_PATH), str(repo / self.profile["sourceMembers"][2]), str(repo), str(output)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 2, completed.stdout + completed.stderr)
            self.assertEqual(json.loads(completed.stdout)["code"], "PANEL_CONTROL_MISSING")

    def test_044_javascript_and_python_fixture_campaigns_agree(self):
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


    def test_045_healthy_inspection_accepts_explicit_null_refusal(self):
        result = run_panel_harness(r"""
const inspection={status:'PASS',probeVersion:'1',installedBeforeApplication:true,probeRefused:null,observedEventCount:2};
const observed=test.requireHealthyInspection(inspection);
console.log(JSON.stringify({same:observed===inspection,probeState:test.el.probeState.textContent,events:test.el.probeEvents.textContent}));
""")
        self.assertEqual(result, {"same": True, "probeState": "version 1", "events": "2"})

    def test_046_healthy_inspection_refuses_absent_refusal_state(self):
        result = run_panel_harness(r"""
let code=null;
try { test.requireHealthyInspection({status:'PASS',probeVersion:'1',installedBeforeApplication:true,observedEventCount:1}); }
catch (error) { code=error.code; }
console.log(JSON.stringify({code}));
""")
        self.assertEqual(result, {"code": "PROBE_REFUSAL_STATE_ABSENT"})

    def test_047_healthy_inspection_refuses_non_null_refusal_state(self):
        result = run_panel_harness(r"""
let code=null;
try { test.requireHealthyInspection({status:'PASS',probeVersion:'1',installedBeforeApplication:true,probeRefused:{code:'EVENT_LIMIT_EXCEEDED'},observedEventCount:1}); }
catch (error) { code=error.code; }
console.log(JSON.stringify({code}));
""")
        self.assertEqual(result, {"code": "PROBE_CAPTURE_REFUSED"})

    def test_048_nominal_pass_probe_refusal_halts_mutated_plan(self):
        bindings = fixture_bindings()
        body = r"""
const bindings=JSON.parse(BINDINGS_JSON);
const messageListeners=[]; const disconnectListeners=[]; const invocations=[];
setPortFactory(() => ({
  onMessage:{addListener(fn){messageListeners.push(fn);}},
  onDisconnect:{addListener(fn){disconnectListeners.push(fn);}},
  postMessage(message){
    let response={protocol:AXMOperatorContract.PROTOCOL,status:'PASS',requestId:message.requestId};
    if(message.kind==='invoke') {
      invocations.push(message.method);
      response.result=null;
      response.inspection={status:'PASS',probeVersion:'1',installedBeforeApplication:true,probeRefused:invocations.length===2?{code:'EVENT_LIMIT_EXCEEDED'}:null,observedEventCount:invocations.length};
    }
    if(message.kind==='status') response.inspection={status:'PASS',probeVersion:'1',installedBeforeApplication:true,probeRefused:null,observedEventCount:invocations.length};
    if(message.kind==='close-session') response.kind='session-closed';
    queueMicrotask(()=>messageListeners.forEach(fn=>fn(response)));
  },
}));
test.connectPort();
test.state.plan={steps:[
  {stepId:'step:first-mark',kind:'probe-call',method:'markAvailability',argsRef:'values.availability'},
  {stepId:'step:second-mark',kind:'probe-call',method:'markAdapterArtifact',argsRef:'values.adapterArtifact'},
  {stepId:'step:must-not-run',kind:'probe-call',method:'markFormation',argsRef:'values.formation'},
]};
test.state.bindings=bindings;
test.state.sessionId='session:'+'1'.repeat(32);
test.state.tabId=7;
test.state.terminal='SESSION_OPEN';
await test.runPlan();
console.log(JSON.stringify({terminal:test.state.terminal,nextIndex:test.state.nextIndex,mutation:test.state.probeMutationPossible,sessionId:test.state.sessionId,loadDisabled:test.el.load.disabled,openDisabled:test.el.open.disabled,invocations}));
""".replace("BINDINGS_JSON", json.dumps(json.dumps(bindings)))
        result = run_panel_harness(body)
        self.assertEqual(result, {
            "terminal": "HALTED_PARTIAL_CAPTURE",
            "nextIndex": 1,
            "mutation": True,
            "sessionId": None,
            "loadDisabled": True,
            "openDisabled": True,
            "invocations": ["markAvailability", "markAdapterArtifact"],
        })


    def test_049_post_call_status_catches_the_first_refusing_invocation(self):
        bindings = fixture_bindings()
        body = r"""
const bindings=JSON.parse(BINDINGS_JSON);
const messageListeners=[]; const disconnectListeners=[]; const invocations=[]; let statusRequests=0;
setPortFactory(() => ({
  onMessage:{addListener(fn){messageListeners.push(fn);}},
  onDisconnect:{addListener(fn){disconnectListeners.push(fn);}},
  disconnect(){disconnectListeners.forEach(fn=>fn());},
  postMessage(message){
    let response={protocol:AXMOperatorContract.PROTOCOL,status:'PASS',requestId:message.requestId};
    if(message.kind==='invoke') {
      invocations.push(message.method);
      response.result=null;
      response.inspection={status:'PASS',probeVersion:'1',installedBeforeApplication:true,probeRefused:null,observedEventCount:invocations.length-1};
    }
    if(message.kind==='status') {
      statusRequests += 1;
      response.inspection={status:'PASS',probeVersion:'1',installedBeforeApplication:true,probeRefused:statusRequests===1?{code:'EVENT_LIMIT_EXCEEDED'}:null,observedEventCount:invocations.length};
    }
    if(message.kind==='close-session') response.kind='session-closed';
    queueMicrotask(()=>messageListeners.forEach(fn=>fn(response)));
  },
}));
test.connectPort();
test.state.plan={steps:[
  {stepId:'step:first-mark',kind:'probe-call',method:'markAvailability',argsRef:'values.availability'},
  {stepId:'step:must-not-run',kind:'probe-call',method:'markAdapterArtifact',argsRef:'values.adapterArtifact'},
]};
test.state.bindings=bindings;
test.state.sessionId='session:'+'1'.repeat(32);
test.state.tabId=7;
test.state.terminal='SESSION_OPEN';
await test.runPlan();
console.log(JSON.stringify({terminal:test.state.terminal,nextIndex:test.state.nextIndex,mutation:test.state.probeMutationPossible,sessionId:test.state.sessionId,loadDisabled:test.el.load.disabled,openDisabled:test.el.open.disabled,invocations,statusRequests}));
""".replace("BINDINGS_JSON", json.dumps(json.dumps(bindings)))
        result = run_panel_harness(body)
        self.assertEqual(result, {
            "terminal": "HALTED_PARTIAL_CAPTURE",
            "nextIndex": 0,
            "mutation": True,
            "sessionId": None,
            "loadDisabled": True,
            "openDisabled": True,
            "invocations": ["markAvailability"],
            "statusRequests": 1,
        })

    def test_050_healthy_post_call_status_precedes_cursor_advance(self):
        bindings = fixture_bindings()
        body = r"""
const bindings=JSON.parse(BINDINGS_JSON);
const messageListeners=[]; const disconnectListeners=[]; const messages=[];
setPortFactory(() => ({
  onMessage:{addListener(fn){messageListeners.push(fn);}},
  onDisconnect:{addListener(fn){disconnectListeners.push(fn);}},
  disconnect(){disconnectListeners.forEach(fn=>fn());},
  postMessage(message){
    messages.push(message.kind);
    const response={protocol:AXMOperatorContract.PROTOCOL,status:'PASS',requestId:message.requestId,result:null,inspection:{status:'PASS',probeVersion:'1',installedBeforeApplication:true,probeRefused:null,observedEventCount:1}};
    queueMicrotask(()=>messageListeners.forEach(fn=>fn(response)));
  },
}));
test.connectPort();
test.state.plan={steps:[
  {stepId:'step:first-mark',kind:'probe-call',method:'markAvailability',argsRef:'values.availability'},
  {stepId:'step:barrier',kind:'operator-barrier',code:'BEFORE_CAPTURE_EXPORT',statement:'review'},
]};
test.state.bindings=bindings;
test.state.sessionId='session:'+'1'.repeat(32);
test.state.tabId=7;
test.state.terminal='SESSION_OPEN';
await test.runPlan();
console.log(JSON.stringify({terminal:test.state.terminal,nextIndex:test.state.nextIndex,messages}));
""".replace("BINDINGS_JSON", json.dumps(json.dumps(bindings)))
        result = run_panel_harness(body)
        self.assertEqual(result, {
            "terminal": "AWAITING_OPERATOR_BARRIER",
            "nextIndex": 1,
            "messages": ["invoke", "status"],
        })

    def test_051_failed_open_inspection_closes_the_returned_worker_session(self):
        result = run_panel_harness(r"""
const messageListeners=[]; const disconnectListeners=[]; const messages=[]; let disconnected=false;
setPortFactory(() => ({
  onMessage:{addListener(fn){messageListeners.push(fn);}},
  onDisconnect:{addListener(fn){disconnectListeners.push(fn);}},
  disconnect(){disconnected=true; disconnectListeners.forEach(fn=>fn());},
  postMessage(message){
    messages.push(message.kind);
    let response={protocol:AXMOperatorContract.PROTOCOL,status:'PASS',requestId:message.requestId};
    if(message.kind==='open-session') Object.assign(response,{sessionId:'session:'+'1'.repeat(32),tabId:7,inspection:{status:'PASS',probeVersion:'1',installedBeforeApplication:true,probeRefused:{code:'EVENT_LIMIT_EXCEEDED'},observedEventCount:1}});
    if(message.kind==='close-session') response.kind='session-closed';
    queueMicrotask(()=>messageListeners.forEach(fn=>fn(response)));
  },
}));
test.state.plan={steps:[]}; test.state.bindings={}; test.state.terminal='LOADED';
await test.openSession();
console.log(JSON.stringify({messages,disconnected,terminal:test.state.terminal,sessionId:test.state.sessionId,portConnected:Boolean(test.state.port)}));
""")
        self.assertEqual(result, {
            "messages": ["open-session", "close-session"],
            "disconnected": False,
            "terminal": "LOADED",
            "sessionId": None,
            "portConnected": True,
        })

    def test_052_failed_open_close_refusal_disconnects_and_allows_a_fresh_port(self):
        result = run_panel_harness(r"""
let generation=0; let disconnects=0; const messages=[];
setPortFactory(() => {
  generation += 1;
  const own=generation; const messageListeners=[]; const disconnectListeners=[];
  return {
    onMessage:{addListener(fn){messageListeners.push(fn);}},
    onDisconnect:{addListener(fn){disconnectListeners.push(fn);}},
    disconnect(){disconnects += 1; messages.push(`${own}:disconnect`); disconnectListeners.forEach(fn=>fn());},
    postMessage(message){
      messages.push(`${own}:${message.kind}`);
      let response={protocol:AXMOperatorContract.PROTOCOL,status:'PASS',requestId:message.requestId};
      if(message.kind==='open-session') Object.assign(response,{sessionId:'session:'+String(own).repeat(32),tabId:7,inspection:{status:'PASS',probeVersion:'1',installedBeforeApplication:true,probeRefused:own===1?{code:'EVENT_LIMIT_EXCEEDED'}:null,observedEventCount:1}});
      if(message.kind==='close-session' && own===1) Object.assign(response,{status:'REFUSED',code:'CLOSE_FAILED',message:'close refused'});
      queueMicrotask(()=>messageListeners.forEach(fn=>fn(response)));
    },
  };
});
test.state.plan={steps:[]}; test.state.bindings={}; test.state.terminal='LOADED';
await test.openSession();
const first={terminal:test.state.terminal,sessionId:test.state.sessionId,portConnected:Boolean(test.state.port)};
await test.openSession();
const second={terminal:test.state.terminal,sessionId:test.state.sessionId,portConnected:Boolean(test.state.port)};
console.log(JSON.stringify({generation,disconnects,messages,first,second}));
""")
        self.assertEqual(result, {
            "generation": 2,
            "disconnects": 1,
            "messages": ["1:open-session", "1:close-session", "1:disconnect", "2:open-session"],
            "first": {"terminal": "LOADED", "sessionId": None, "portConnected": False},
            "second": {"terminal": "SESSION_OPEN", "sessionId": "session:" + "2" * 32, "portConnected": True},
        })

    def test_053_primary_verifier_requires_post_invocation_inspection(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = clone_minimal(pathlib.Path(temp) / "repo")
            panel = repo / "mating_surface/anchor_node/browser_audition_operation_plan_panel.js"
            panel.write_text(panel.read_text(encoding="utf-8").replace("await requirePostInvocationInspection();", "/* post-call inspection removed */"), encoding="utf-8")
            output = pathlib.Path(temp) / "extension"
            tool.build_extension(repo / self.profile["sourceMembers"][2], repo, output)
            with self.assertRaises(tool.PlanError) as caught:
                tool.verify_extension(repo / self.profile["sourceMembers"][2], repo, output)
            self.assertIn(caught.exception.code, {"PANEL_CONTROL_MISSING", "PANEL_CONTROL_ORDER_INVALID"})

    def test_054_independent_verifier_requires_failed_open_session_release(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = clone_minimal(pathlib.Path(temp) / "repo")
            panel = repo / "mating_surface/anchor_node/browser_audition_operation_plan_panel.js"
            panel.write_text(panel.read_text(encoding="utf-8").replace("await releaseFailedOpenSession(response);", "discardSessionState(\"session open failed\");"), encoding="utf-8")
            output = pathlib.Path(temp) / "extension"
            tool.build_extension(repo / self.profile["sourceMembers"][2], repo, output)
            completed = subprocess.run(
                [sys.executable, str(VERIFIER_PATH), str(repo / self.profile["sourceMembers"][2]), str(repo), str(output)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 2, completed.stdout + completed.stderr)
            self.assertIn(json.loads(completed.stdout)["code"], {"PANEL_CONTROL_MISSING", "PANEL_CONTROL_ORDER_INVALID"})


    def test_055_python_compiler_accepts_exact_session_request_boundary(self):
        bindings = tool.validate_bindings(bindings_with_probe_invocations(254), self.operator)
        plan = tool.compile_plan(bindings)
        self.assertEqual(plan["probeInvocationCount"], 254)
        self.assertEqual(tool.required_session_requests(plan["probeInvocationCount"]), tool.MAX_SESSION_REQUESTS)

    def test_056_python_compiler_refuses_first_session_request_overrun(self):
        bindings = tool.validate_bindings(bindings_with_probe_invocations(255), self.operator)
        with self.assertRaises(tool.PlanError) as caught:
            tool.compile_plan(bindings)
        self.assertEqual(caught.exception.code, "PLAN_LIMIT_EXCEEDED")
        self.assertIn("sessionRequests=514", str(caught.exception))

    def test_057_javascript_compiler_accepts_exact_session_request_boundary(self):
        result = run_contract_compile(bindings_with_probe_invocations(254))
        self.assertEqual(result, {"status": "PASS", "probeInvocationCount": 254, "sessionRequestCount": 512})

    def test_058_javascript_compiler_refuses_first_session_request_overrun(self):
        result = run_contract_compile(bindings_with_probe_invocations(255))
        self.assertEqual(result, {"status": "REFUSED", "code": "PLAN_LIMIT_EXCEEDED"})

    def test_059_independent_verifier_requires_post_invocation_session_budget(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = clone_minimal(pathlib.Path(temp) / "repo")
            contract = repo / "mating_surface/anchor_node/browser_audition_operation_plan_contract.js"
            expression = "probeInvocationCount * SESSION_REQUESTS_PER_PROBE_INVOCATION + SESSION_REQUEST_RESERVE"
            source = contract.read_text(encoding="utf-8")
            self.assertEqual(source.count(expression), 1)
            contract.write_text(source.replace(expression, "probeInvocationCount + SESSION_REQUEST_RESERVE"), encoding="utf-8")
            output = pathlib.Path(temp) / "extension"
            tool.build_extension(repo / self.profile["sourceMembers"][2], repo, output)
            completed = subprocess.run(
                [sys.executable, str(VERIFIER_PATH), str(repo / self.profile["sourceMembers"][2]), str(repo), str(output)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 2, completed.stdout + completed.stderr)
            self.assertEqual(json.loads(completed.stdout)["code"], "PLAN_SESSION_BUDGET_INVALID")


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
