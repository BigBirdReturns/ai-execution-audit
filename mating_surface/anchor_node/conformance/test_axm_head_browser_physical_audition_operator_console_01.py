from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPOSITORY_ROOT = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
import axm_head_browser_physical_audition_operator_console_01 as mod
import verify_axm_head_browser_physical_audition_operator_console_01 as verifier

PROFILE = ROOT / "axm-head-browser-physical-audition-operator-console-profile-01.json"
FIXTURES = ROOT / "fixtures" / "axm-head-browser-physical-audition-operator-console-cases-01.json"
TOOL = ROOT / "axm_head_browser_physical_audition_operator_console_01.py"
VERIFY = ROOT / "verify_axm_head_browser_physical_audition_operator_console_01.py"
BOOTSTRAP = ROOT / "verify_axm_head_browser_physical_audition_operator_console_01_bootstrap.py"
CONTRACT = ROOT / "browser_physical_audition_operator_contract.js"
WORKER = ROOT / "browser_physical_audition_operator_service_worker.js"
PANEL_HTML = ROOT / "browser_physical_audition_operator_panel.html"
PANEL_JS = ROOT / "browser_physical_audition_operator_panel.js"
PANEL_CSS = ROOT / "browser_physical_audition_operator_panel.css"
WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "axm-head-browser-physical-audition-operator-console-01.yml"
WRAPPER = ROOT / "axm-head-browser-physical-audition-operator-console-01.ps1"
PROBE = ROOT / "browser_distributed_inference_probe.js"
PACKET_PROFILE = ROOT / "axm-head-browser-physical-audition-packet-profile-01.json"


class OperatorConsoleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = mod.validate_profile(PROFILE)
        self.fixtures = mod.validate_fixture_catalog(FIXTURES, self.profile)
        self.temp = tempfile.TemporaryDirectory(prefix="axm-operator-console-test-")
        self.work = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def build(self, name: str = "extension") -> Path:
        output = self.work / name
        mod.build_extension(PROFILE, REPOSITORY_ROOT, output)
        return output

    def test_01_profile_identity_and_admitted_floor_are_exact(self) -> None:
        self.assertEqual(self.profile["profileId"], mod.PROFILE_ID)
        self.assertEqual(self.profile["issueRef"], mod.ISSUE_REF)
        self.assertEqual(self.profile["protocol"], mod.PROTOCOL)
        self.assertEqual(self.profile["interface"], mod.INTERFACE)
        self.assertEqual(self.profile["admittedPacket"]["commit"], mod.ADMITTED_PACKET_COMMIT)
        self.assertEqual(self.profile["admittedPacket"]["tree"], mod.ADMITTED_PACKET_TREE)
        self.assertEqual(self.profile["admittedPacket"]["sourceBindingId"], mod.ADMITTED_PACKET_SOURCE_BINDING_ID)
        self.assertEqual(self.profile["admittedPacket"]["kitId"], mod.ADMITTED_PACKET_KIT_ID)

    def test_02_profile_closes_source_extension_method_and_command_denominators(self) -> None:
        self.assertEqual(tuple(self.profile["sourceMembers"]), mod.SOURCE_MEMBERS)
        self.assertEqual(tuple(self.profile["extensionSourceMembers"]), mod.EXTENSION_SOURCE_MEMBERS)
        self.assertEqual(tuple(self.profile["extensionPayloadMembers"]), mod.EXTENSION_PAYLOAD_MEMBERS)
        self.assertEqual(tuple(self.profile["extensionMembers"]), mod.EXTENSION_MEMBERS)
        self.assertEqual(tuple(self.profile["methods"]), mod.METHODS)
        self.assertEqual(tuple(self.profile["commands"]), mod.COMMANDS)

    def test_03_admitted_dependency_files_are_exact(self) -> None:
        expected = {row["path"]: row for row in self.profile["dependencies"]}
        for relative, row in expected.items():
            data = (REPOSITORY_ROOT / relative).read_bytes()
            self.assertEqual(len(data), row["bytes"])
            self.assertEqual(mod.digest_bytes(data), row["sha256"])
        self.assertEqual(hashlib.sha1(f"blob {PROBE.stat().st_size}\0".encode() + PROBE.read_bytes()).hexdigest(), mod.PROBE_BLOB)
        self.assertEqual(hashlib.sha1(f"blob {PACKET_PROFILE.stat().st_size}\0".encode() + PACKET_PROFILE.read_bytes()).hexdigest(), mod.PACKET_PROFILE_BLOB)

    def test_04_manifest_contract_keeps_probe_early_and_console_out_of_page_channel(self) -> None:
        manifest = mod.extension_manifest(self.profile)
        self.assertEqual(manifest, self.profile["manifestContract"])
        self.assertEqual(manifest["content_scripts"][0]["js"], ["browser_distributed_inference_probe.js"])
        self.assertEqual(manifest["content_scripts"][0]["run_at"], "document_start")
        self.assertEqual(manifest["content_scripts"][0]["world"], "MAIN")
        self.assertEqual(manifest["permissions"], ["activeTab", "scripting", "sidePanel"])
        self.assertNotIn("host_permissions", manifest)

    def test_05_claim_boundary_is_closed(self) -> None:
        claim = self.profile["claimBoundary"]
        self.assertTrue(claim["operatorConsoleSourceConstructed"])
        for key in (
            "operatorConsoleSourceAdmitted",
            "browserLaunched",
            "supplierEndpointContacted",
            "modelDownloaded",
            "peerConnectionFormed",
            "inferenceExecuted",
            "physicalAuditionCompleted",
            "namedHumanConfirmationSupplied",
            "actualSupplierQualified",
            "physicalEstateQualified",
        ):
            self.assertFalse(claim[key])
        self.assertEqual((claim["missionAuthority"], claim["commandAuthority"]), ("none", "none"))

    def test_06_executable_profile_and_console_sources_are_supplier_neutral(self) -> None:
        for path in (PROFILE, CONTRACT, WORKER, PANEL_HTML, PANEL_JS, PANEL_CSS, TOOL, VERIFY, BOOTSTRAP):
            lowered = path.read_text(encoding="utf-8").lower()
            self.assertNotIn("swarmllm", lowered, path.name)
            self.assertNotIn("nehanth", lowered, path.name)

    def test_07_all_javascript_sources_parse(self) -> None:
        for path in (CONTRACT, WORKER, PANEL_JS):
            result = subprocess.run(["node", "--check", str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"", b""), path.name)

    def test_08_panel_contains_no_inline_script_or_event_handler(self) -> None:
        source = PANEL_HTML.read_text(encoding="utf-8")
        self.assertNotIn("<script>", source.lower())
        self.assertNotRegex(source.lower(), r"\son[a-z]+\s*=")
        self.assertIn('src="browser_physical_audition_operator_panel.js"', source)
        self.assertIn('href="browser_physical_audition_operator_panel.css"', source)

    def test_09_service_worker_uses_extension_port_and_secure_main_world_execution(self) -> None:
        source = WORKER.read_text(encoding="utf-8")
        for token in (
            "chrome.runtime.onConnect.addListener",
            "chrome.scripting.executeScript",
            'world: "MAIN"',
            "chrome.sidePanel",
            "port.onDisconnect.addListener",
            "Object.getOwnPropertyDescriptor(globalThis, \"__AXM_AUDITION__\")",
        ):
            self.assertIn(token, source)
        for token in ("chrome.runtime.onMessage", "window.postMessage", "CustomEvent"):
            self.assertNotIn(token, source)

    def test_10_console_uses_no_network_remote_code_or_persistent_storage(self) -> None:
        joined = "\n".join(path.read_text(encoding="utf-8") for path in (CONTRACT, WORKER, PANEL_JS, PANEL_HTML)).lower()
        for token in (
            "xmlhttprequest",
            "new websocket",
            "new eventsource",
            "sendbeacon",
            "chrome.storage",
            "localstorage",
            "sessionstorage",
            "indexeddb",
            "eval(",
            "new function(",
        ):
            self.assertNotIn(token, joined)
        self.assertNotRegex(joined, r"\bfetch\s*\(")

    def test_11_python_and_javascript_fixture_contracts_agree(self) -> None:
        script = textwrap.dedent(
            """
            const fs = require('fs');
            const vm = require('vm');
            vm.runInThisContext(fs.readFileSync(process.argv[1], 'utf8'));
            const fixtures = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
            const rows = [];
            for (const row of fixtures.positiveCases) {
              try { AXMOperatorContract.validateArgs(row.method, row.args); rows.push([row.caseId, 'PASS', null]); }
              catch (error) { rows.push([row.caseId, 'REFUSED', error.code || 'UNKNOWN']); }
            }
            for (const row of fixtures.hostileCases) {
              try { AXMOperatorContract.validateArgs(row.method, row.args); rows.push([row.caseId, 'PASS', null]); }
              catch (error) { rows.push([row.caseId, 'REFUSED', error.code || 'UNKNOWN']); }
            }
            for (const row of fixtures.envelopeCases) {
              try { AXMOperatorContract.validateEnvelope(row.envelope); rows.push([row.caseId, 'PASS', null]); }
              catch (error) { rows.push([row.caseId, 'REFUSED', error.code || 'UNKNOWN']); }
            }
            process.stdout.write(JSON.stringify(rows));
            """
        )
        result = subprocess.run(["node", "-e", script, str(CONTRACT), str(FIXTURES)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        self.assertEqual((result.returncode, result.stderr), (0, b""))
        js_rows = {case_id: (outcome, code) for case_id, outcome, code in json.loads(result.stdout)}
        py = mod.campaign(self.profile, self.fixtures)
        py_rows = {row["caseId"]: (row["outcome"], row["code"]) for row in py["results"]}
        self.assertEqual(js_rows, py_rows)

    def test_12_extension_build_is_deterministic(self) -> None:
        one = self.build("one")
        two = self.build("two")
        self.assertEqual(sorted(path.name for path in one.iterdir()), sorted(path.name for path in two.iterdir()))
        for path in one.iterdir():
            self.assertEqual(path.read_bytes(), (two / path.name).read_bytes(), path.name)

    def test_13_extension_has_exact_members_and_exact_probe(self) -> None:
        extension = self.build()
        self.assertEqual({path.name for path in extension.iterdir()}, set(mod.EXTENSION_MEMBERS))
        self.assertEqual(mod.digest_bytes((extension / "browser_distributed_inference_probe.js").read_bytes()), mod.PROBE_SHA256)
        build = json.loads((extension / "build-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(build["memberCount"], 7)
        self.assertFalse(build["claimBoundary"]["actualSupplierQualified"])

    def test_14_direct_verifier_reconstructs_extension(self) -> None:
        extension = self.build()
        verdict = verifier.verify_extension(PROFILE, REPOSITORY_ROOT, extension)
        self.assertEqual(verdict["status"], "PASS")
        self.assertFalse(verdict["bootstrapAuthenticated"])
        self.assertFalse(verdict["actualSupplierQualified"])
        self.assertEqual((verdict["missionAuthority"], verdict["commandAuthority"]), ("none", "none"))

    def test_15_bootstrap_executes_measured_verifier(self) -> None:
        extension = self.build()
        result = subprocess.run(
            [sys.executable, str(BOOTSTRAP), str(VERIFY), str(PROFILE), str(REPOSITORY_ROOT), str(extension)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual((result.returncode, result.stderr), (0, b""))
        verdict = json.loads(result.stdout.decode("utf-8"))
        self.assertEqual(verdict["status"], "PASS")
        self.assertTrue(verdict["bootstrapAuthenticated"])
        self.assertTrue(verdict["storedVerifierMemberBound"])

    def test_16_probe_tampering_is_refused(self) -> None:
        extension = self.build()
        probe = extension / "browser_distributed_inference_probe.js"
        probe.write_bytes(probe.read_bytes() + b"\n")
        with self.assertRaises(verifier.VerificationError) as context:
            verifier.verify_extension(PROFILE, REPOSITORY_ROOT, extension)
        self.assertEqual(context.exception.code, "PROBE_BYTES_INVALID")

    def test_17_extra_extension_member_is_refused(self) -> None:
        extension = self.build()
        (extension / "extra.txt").write_text("extra\n", encoding="utf-8")
        with self.assertRaises(verifier.VerificationError) as context:
            verifier.verify_extension(PROFILE, REPOSITORY_ROOT, extension)
        self.assertEqual(context.exception.code, "EXTENSION_MEMBER_DENOMINATOR_INVALID")

    def test_18_repository_local_build_output_is_refused(self) -> None:
        output = REPOSITORY_ROOT / ".operator-console-test-output"
        with self.assertRaises(mod.ConsoleError) as context:
            mod.build_extension(PROFILE, REPOSITORY_ROOT, output)
        self.assertEqual(context.exception.code, "REPOSITORY_LOCAL_OUTPUT_REFUSED")
        self.assertFalse(output.exists())

    def test_19_linked_output_ancestor_is_refused(self) -> None:
        target = self.work / "target"
        target.mkdir()
        link = self.work / "linked"
        if os.name == "nt":
            result = subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            link.symlink_to(target, target_is_directory=True)
        with self.assertRaises(mod.ConsoleError) as context:
            mod.build_extension(PROFILE, REPOSITORY_ROOT, link / "extension")
        self.assertEqual(context.exception.code, "LINKED_PATH_REFUSED")
        if os.name == "nt" and link.exists():
            os.rmdir(link)

    def test_20_source_set_measures_exact_fourteen_members(self) -> None:
        source = mod.source_set(self.profile, REPOSITORY_ROOT)
        self.assertEqual(source["status"], "PASS")
        self.assertEqual(source["sourceMemberCount"], 14)
        self.assertEqual([row["path"] for row in source["members"]], list(mod.SOURCE_MEMBERS))
        self.assertTrue(source["sourceBindingId"].startswith("axmoperatorconsolesource_"))

    def test_21_full_service_worker_sequence_reaches_capture_only(self) -> None:
        script = textwrap.dedent(
            r"""
            const fs = require('fs'); const vm = require('vm'); const path = require('path');
            const root = process.argv[1]; const listeners = []; let activeTabId = 7; let documentId = 'document-a'; const events = []; const members = new Map();
            function opaque(label){ if(!members.has(label)) members.set(label, 'opaque:' + String(members.size + 1).repeat(32).slice(0,32)); return members.get(label); }
            const api = Object.freeze({version:'1',
              markAvailability(a){events.push(['markAvailability',a]);}, markAdapterArtifact(a){events.push(['markAdapterArtifact',a]);},
              markFormation(a){events.push(['markFormation',a]);}, markMember(a){const id=opaque(a.memberId);events.push(['markMember',a]);return id;},
              markModelManifest(a){events.push(['markModelManifest',a]);}, markModelArtifact(a){events.push(['markModelArtifact',a]);},
              markPerformanceStart(a){events.push(['markPerformanceStart',a]);}, markToken(a){events.push(['markToken',a]);},
              markDrop(a){events.push(['markDrop',a]);}, markEquivalence(a){events.push(['markEquivalence',a]);},
              markPrivacyDeclaration(a){events.push(['markPrivacyDeclaration',a]);}, markObservationReceipt(a){events.push(['markObservationReceipt',a]);},
              samplePeerStats(){events.push(['samplePeerStats',{}]);return [];},
              exportCapture(){return {schema:'axm-head/browser-probe-private-capture@1',installedBeforeApplication:true,refused:null,observed:{eventCount:events.length,encodedBytes:JSON.stringify(events).length},events:[...events],summaries:{}};}
            });
            Object.defineProperty(globalThis,'__AXM_AUDITION__',{value:api,enumerable:false,writable:false,configurable:false});
            global.importScripts=(...names)=>{for(const name of names)vm.runInThisContext(fs.readFileSync(path.join(root,name),'utf8'),{filename:name});};
            global.chrome={runtime:{id:'test-extension',onConnect:{addListener(fn){listeners.push(fn);}}},tabs:{async query(){return [{id:activeTabId}];}},
              scripting:{async executeScript({func,args}){return [{documentId,result:await func(...args)}];}},sidePanel:{setPanelBehavior(){return Promise.resolve();}}};
            vm.runInThisContext(fs.readFileSync(path.join(root,'browser_physical_audition_operator_service_worker.js'),'utf8'));
            function port(){const ml=[],dl=[],responses=[];return{name:'axm-browser-physical-audition-operator-console-v1',sender:{id:'test-extension'},onMessage:{addListener(f){ml.push(f);}},onDisconnect:{addListener(f){dl.push(f);}},postMessage(v){responses.push(v);},disconnect(){dl.forEach(f=>f());},send(v){ml.forEach(f=>f(v));},responses};}
            const p=port(); listeners[0](p); let seq=1; const rid=()=>`request:${String(seq++).padStart(32,'0')}`;
            async function send(m){const n=p.responses.length;p.send({...m,requestId:m.requestId||rid()});for(let i=0;i<200;i++){if(p.responses.length>n)return p.responses.at(-1);await new Promise(r=>setTimeout(r,2));}throw new Error('timeout');}
            (async()=>{const base={protocol:'axm-head/browser-physical-audition-operator-console@1',tabId:7};const sha=c=>'sha256:'+c.repeat(64);
              const open=await send({...base,kind:'open-session'});const sessionId=open.sessionId;const invoke=(method,args)=>send({...base,kind:'invoke',sessionId,method,args});
              const m1=await invoke('markMember',{memberId:'member-a',role:'pipeline-input',pledgedBytes:8});const m2=await invoke('markMember',{memberId:'member-b',role:'pipeline-output',pledgedBytes:8});
              await invoke('markAvailability',{observedAtUnixMs:1788246000000,evidenceRef:sha('1'),observed:true});await invoke('markAdapterArtifact',{artifactBytes:10,artifactDigest:sha('2'),evidenceRef:sha('3'),executableObserved:true});
              await invoke('markFormation',{artifactBound:true,capacityBasis:'artifact-bound-shards',capacityReceiptRef:sha('4'),modelCapacityBytes:16,partitionMode:'pipeline-layer',topologyReceiptRef:sha('5')});
              await invoke('markModelManifest',{claimedId:'model:qwen',boundModelId:'model:qwen',observedManifestDigest:sha('6')});await invoke('markModelArtifact',{artifactId:'a',bytes:8,digest:sha('7'),layerStart:0,layerEnd:1,memberIdHash:m1.result});
              await invoke('markPerformanceStart',{promptTokenCount:1});await invoke('markToken',{index:0});await invoke('markDrop',{memberIdHash:m2.result,observedTerminal:'HALTED',recovered:false,evidenceRef:sha('8'),controlled:true});
              await invoke('markEquivalence',{referenceDigest:sha('9'),candidateDigest:sha('9'),promptTokenCount:1,outputTokenCount:1,evidenceRef:sha('a')});await invoke('markPrivacyDeclaration',{scope:'browser-observed-network-surface-only',evidenceRef:sha('b'),claimsEndToEndConfidentiality:false});
              await invoke('markObservationReceipt',{kind:'performance-receipt',evidenceRef:sha('c')});await invoke('samplePeerStats',{});const capture=await invoke('exportCapture',{});
              const replayId=rid();const first=await send({...base,kind:'status',sessionId,requestId:replayId});const replay=await send({...base,kind:'status',sessionId,requestId:replayId});activeTabId=8;const wrongTab=await send({...base,kind:'status',sessionId});const close=await send({...base,kind:'close-session',sessionId});
              process.stdout.write(JSON.stringify({open,m1,m2,capture,first,replay,wrongTab,close,eventCount:events.length}));
            })().catch(e=>{console.error(e);process.exit(2);});
            """
        )
        result = subprocess.run(["node", "-e", script, str(ROOT)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        self.assertEqual((result.returncode, result.stderr), (0, b""))
        body = json.loads(result.stdout)
        self.assertEqual(body["open"]["status"], "PASS")
        self.assertEqual(body["capture"]["result"]["schema"], "axm-head/browser-probe-private-capture@1")
        self.assertEqual(body["eventCount"], 14)
        self.assertEqual(body["replay"]["code"], "REQUEST_REPLAY")
        self.assertEqual(body["wrongTab"]["code"], "ACTIVE_TAB_MISMATCH")
        self.assertEqual(body["close"]["status"], "PASS")
        for row in (body["open"], body["capture"]):
            self.assertFalse(row["actualSupplierQualified"])
            self.assertEqual((row["missionAuthority"], row["commandAuthority"]), ("none", "none"))
        self.assertNotIn("terminal", body["capture"])

    def test_22_powershell_wrapper_has_only_closed_commands(self) -> None:
        source = WRAPPER.read_text(encoding="utf-8")
        for command in mod.COMMANDS:
            self.assertIn(f"'{command}'", source)
        self.assertNotIn("Invoke-WebRequest", source)
        self.assertNotIn("Start-Process", source)
        self.assertNotIn("chrome.exe", source.lower())

    def test_23_workflow_has_four_pr_coordinates_and_no_physical_execution(self) -> None:
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("ubuntu-latest", source)
        self.assertIn("windows-latest", source)
        self.assertIn("'[\"head\",\"merge\"]'", source)
        self.assertIn('WITNESS_DENOMINATOR: "83"', source)
        self.assertIn("build-extension", source)
        self.assertIn("bootstrap-verdict.json", source)
        self.assertIn("Require platform and coordinate byte identity", source)
        self.assertIn("Require the exact bounded successor source-change denominator", source)
        self.assertIn("changed != required", source)
        for token in ("playwright", "selenium", "chromedriver", "chrome.exe", "msedge.exe", "curl ", "wget "):
            self.assertNotIn(token, source.lower())

    def test_24_cli_commands_emit_structured_receipts(self) -> None:
        commands = (
            ["validate-profile", str(PROFILE)],
            ["validate-fixtures", str(PROFILE), str(FIXTURES)],
            ["campaign", str(PROFILE), str(FIXTURES)],
            ["source-set", str(PROFILE), str(REPOSITORY_ROOT)],
        )
        for args in commands:
            result = subprocess.run([sys.executable, str(TOOL), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            self.assertEqual((result.returncode, result.stderr), (0, b""), args[0])
            body = json.loads(result.stdout.decode("utf-8"))
            self.assertEqual(body["status"], "PASS")

    def test_25_payload_mutation_cannot_recompute_itself_into_a_pass(self) -> None:
        extension = self.build()
        panel = extension / "browser_physical_audition_operator_panel.js"
        panel.write_bytes(panel.read_bytes() + b"\n// hostile payload mutation\n")
        build = json.loads((extension / "build-manifest.json").read_text(encoding="utf-8"))
        rows = []
        for name in self.profile["extensionPayloadMembers"]:
            data = (extension / name).read_bytes()
            rows.append({"path": name, "bytes": len(data), "sha256": verifier.digest(data)})
        build["members"] = rows
        build["memberCount"] = len(rows)
        build["extensionId"] = verifier.identity(
            "axmoperatorconsoleextension",
            {"profileId": self.profile["profileId"], "sourceBindingId": build["sourceBindingId"], "members": rows},
        )
        (extension / "build-manifest.json").write_bytes(verifier.pretty_bytes(build))
        with self.assertRaises(verifier.VerificationError) as context:
            verifier.verify_extension(PROFILE, REPOSITORY_ROOT, extension)
        self.assertEqual(context.exception.code, "PAYLOAD_SOURCE_BYTES_INVALID")

    def test_26_profile_and_executed_verifier_bytes_are_repository_bound(self) -> None:
        extension = self.build()
        copied_profile = self.work / "profile-copy.json"
        copied_profile.write_bytes(PROFILE.read_bytes() + b"\n")
        with self.assertRaises(verifier.VerificationError) as context:
            verifier.verify_extension(copied_profile, REPOSITORY_ROOT, extension)
        self.assertEqual(context.exception.code, "PROFILE_BYTES_INVALID")

        copied_verifier = self.work / "verifier-copy.py"
        copied_verifier.write_bytes(VERIFY.read_bytes() + b"\n# hostile verifier substitution\n")
        result = subprocess.run(
            [sys.executable, str(copied_verifier), str(PROFILE), str(REPOSITORY_ROOT), str(extension)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual((result.returncode, result.stderr), (2, b""))
        self.assertEqual(json.loads(result.stdout.decode("utf-8"))["code"], "STORED_VERIFIER_MEMBER_MISMATCH")

    def test_27_panel_reconnects_a_fresh_port_before_session_reopening(self) -> None:
        source = PANEL_JS.read_text(encoding="utf-8")
        self.assertIn("function connectPort()", source)
        self.assertIn("function ensurePort()", source)
        self.assertIn("state.port = null;", source)
        self.assertIn("const port = ensurePort();", source)
        self.assertIn("try {\n      connectPort();", source)
        self.assertNotIn("port: chrome.runtime.connect", source)

    def test_28_panel_parses_complete_integer_values_without_truncation(self) -> None:
        source = PANEL_JS.read_text(encoding="utf-8")
        self.assertNotIn("Number.parseInt", source)
        self.assertIn("const value = Number(raw);", source)
        self.assertIn("Number.isInteger(value)", source)
        self.assertIn("must be a complete integer", source)

    def test_29_service_worker_invalidates_a_session_when_document_identity_changes(self) -> None:
        script = textwrap.dedent(
            r"""
            const fs = require('fs'); const vm = require('vm'); const path = require('path');
            const root = process.argv[1]; const listeners = []; let documentId = 'document-a';
            global.importScripts=(...names)=>{for(const name of names)vm.runInThisContext(fs.readFileSync(path.join(root,name),'utf8'),{filename:name});};
            global.chrome={runtime:{id:'test-extension',onConnect:{addListener(fn){listeners.push(fn);}}},tabs:{async query(){return [{id:7}];}},
              scripting:{async executeScript({func,args}){return [{documentId,result:await func(...args)}];}},sidePanel:{setPanelBehavior(){return Promise.resolve();}}};
            vm.runInThisContext(fs.readFileSync(path.join(root,'browser_physical_audition_operator_service_worker.js'),'utf8'));
            const methods=global.AXMOperatorContract.METHODS;const api={version:'1'};
            for(const method of methods)api[method]=()=>null;
            api.exportCapture=()=>({schema:'axm-head/browser-probe-private-capture@1',installedBeforeApplication:true,refused:null,observed:{eventCount:0,encodedBytes:0},events:[],summaries:{}});
            Object.freeze(api);Object.defineProperty(globalThis,'__AXM_AUDITION__',{value:api,enumerable:false,writable:false,configurable:false});
            function port(){const ml=[],dl=[],responses=[];return{name:'axm-browser-physical-audition-operator-console-v1',sender:{id:'test-extension'},onMessage:{addListener(f){ml.push(f);}},onDisconnect:{addListener(f){dl.push(f);}},postMessage(v){responses.push(v);},disconnect(){dl.forEach(f=>f());},send(v){ml.forEach(f=>f(v));},responses};}
            const p=port();listeners[0](p);let seq=1;const rid=()=>`request:${String(seq++).padStart(32,'0')}`;
            async function send(m){const n=p.responses.length;p.send({...m,requestId:rid()});for(let i=0;i<200;i++){if(p.responses.length>n)return p.responses.at(-1);await new Promise(r=>setTimeout(r,2));}throw new Error('timeout');}
            (async()=>{const base={protocol:'axm-head/browser-physical-audition-operator-console@1',tabId:7};const open=await send({...base,kind:'open-session'});documentId='document-b';const changed=await send({...base,kind:'status',sessionId:open.sessionId});const stale=await send({...base,kind:'status',sessionId:open.sessionId});process.stdout.write(JSON.stringify({open,changed,stale}));})().catch(e=>{console.error(e);process.exit(2);});
            """
        )
        result = subprocess.run(["node", "-e", script, str(ROOT)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        self.assertEqual((result.returncode, result.stderr), (0, b""))
        body = json.loads(result.stdout)
        self.assertEqual(body["open"]["status"], "PASS")
        self.assertEqual(body["changed"]["code"], "SESSION_DOCUMENT_MISMATCH")
        self.assertEqual(body["stale"]["code"], "SESSION_INVALID")


    def test_30_packet_source_binding_substitution_is_refused(self) -> None:
        hostile = json.loads(json.dumps(self.profile))
        hostile["admittedPacket"]["sourceBindingId"] = "axmbrowserphysicalpacketsource_" + "0" * 64
        path = self.work / "hostile-source-binding-profile.json"
        path.write_bytes(mod.pretty_bytes(hostile))
        with self.assertRaises(mod.ConsoleError) as context:
            mod.validate_profile(path)
        self.assertEqual(context.exception.code, "ADMITTED_PACKET_BINDING_INVALID")

    def test_31_packet_kit_substitution_is_refused(self) -> None:
        hostile = json.loads(json.dumps(self.profile))
        hostile["admittedPacket"]["kitId"] = "axmbrowserphysicalkit_" + "0" * 64
        path = self.work / "hostile-kit-profile.json"
        path.write_bytes(mod.pretty_bytes(hostile))
        with self.assertRaises(mod.ConsoleError) as context:
            mod.validate_profile(path)
        self.assertEqual(context.exception.code, "ADMITTED_PACKET_BINDING_INVALID")

def _fixture_test(row: dict, group: str):
    def run(self: OperatorConsoleTests) -> None:
        if group == "positive":
            normalized = mod.validate_args(row["method"], row["args"])
            self.assertIsInstance(normalized, dict)
            return
        if group == "hostile":
            with self.assertRaises(mod.ConsoleError) as context:
                mod.validate_args(row["method"], row["args"])
            self.assertEqual(context.exception.code, row["expectedCode"])
            return
        expected = row["expected"]
        if expected == "PASS":
            self.assertIsInstance(mod.validate_envelope(row["envelope"]), dict)
        else:
            with self.assertRaises(mod.ConsoleError) as context:
                mod.validate_envelope(row["envelope"])
            self.assertEqual(context.exception.code, row["expectedCode"])
    return run


_catalog = json.loads(FIXTURES.read_text(encoding="utf-8"))
for _group_name, _key in (("positive", "positiveCases"), ("hostile", "hostileCases"), ("envelope", "envelopeCases")):
    for _row in _catalog[_key]:
        _name = "test_fixture_" + _row["caseId"].replace("-", "_")
        setattr(OperatorConsoleTests, _name, _fixture_test(_row, _group_name))


if __name__ == "__main__":
    unittest.main()
