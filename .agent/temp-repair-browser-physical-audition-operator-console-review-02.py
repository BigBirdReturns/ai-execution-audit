from pathlib import Path
import textwrap

ROOT = Path("mating_surface/anchor_node")


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"replacement target differs: {path}: {old[:80]!r}: {count}")
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


verifier = ROOT / "verify_axm_head_browser_physical_audition_operator_console_01.py"
replace_once(
    verifier,
    '    profile = load(profile_path)\n',
    '''    profile_bytes = regular(profile_path)
    canonical_profile_bytes = regular(
        repo / "mating_surface/anchor_node/axm-head-browser-physical-audition-operator-console-profile-01.json"
    )
    if profile_bytes != canonical_profile_bytes:
        fail("PROFILE_BYTES_INVALID", str(profile_path))
    try:
        profile = json.loads(profile_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        fail("JSON_INVALID", f"{profile_path}: {exc}")
    if not isinstance(profile, dict):
        fail("OBJECT_REQUIRED", str(profile_path))

    executed_verifier_bytes = globals().get("__AXM_MEASURED_VERIFIER_BYTES__")
    if executed_verifier_bytes is None:
        executed_verifier_bytes = regular(Path(__file__))
    if not isinstance(executed_verifier_bytes, (bytes, bytearray)):
        fail("EXECUTED_VERIFIER_BYTES_INVALID", str(type(executed_verifier_bytes)))
    stored_verifier_bytes = regular(
        repo / "mating_surface/anchor_node/verify_axm_head_browser_physical_audition_operator_console_01.py"
    )
    if bytes(executed_verifier_bytes) != stored_verifier_bytes:
        fail("STORED_VERIFIER_MEMBER_MISMATCH", str(profile_path))
''',
)
replace_once(
    verifier,
    '''    payload_rows = []
    for name in profile["extensionPayloadMembers"]:
        data = regular(extension / name)
        payload_rows.append({"path": name, "bytes": len(data), "sha256": digest(data)})
    if build["members"] != payload_rows or build["memberCount"] != len(payload_rows):
        fail("PAYLOAD_BINDING_INVALID", str(extension))
''',
    '''    expected_payload = {
        "manifest.json": pretty_bytes(expected_manifest()),
        "browser_distributed_inference_probe.js": regular(repo / profile["dependencies"][0]["path"]),
    }
    for relative in profile["extensionSourceMembers"]:
        expected_payload[Path(relative).name] = regular(repo / relative)
    if set(expected_payload) != set(profile["extensionPayloadMembers"]):
        fail("PAYLOAD_SOURCE_DENOMINATOR_INVALID", str(extension))

    payload_rows = []
    for name in profile["extensionPayloadMembers"]:
        data = regular(extension / name)
        if data != expected_payload[name]:
            fail("PAYLOAD_SOURCE_BYTES_INVALID", name)
        payload_rows.append({"path": name, "bytes": len(data), "sha256": digest(data)})
    if build["members"] != payload_rows or build["memberCount"] != len(payload_rows):
        fail("PAYLOAD_BINDING_INVALID", str(extension))
''',
)
replace_once(
    verifier,
    '    checks = static_source_checks(extension)\n',
    '''    checks = [
        "canonical-profile-byte-binding",
        "payload-source-byte-binding",
        *static_source_checks(extension),
        "stored-verifier-byte-binding",
    ]
''',
)

bootstrap = ROOT / "verify_axm_head_browser_physical_audition_operator_console_01_bootstrap.py"
replace_once(
    bootstrap,
    '''    launcher = (
        "import sys; data=sys.stdin.buffer.read(); "
        "namespace={'__name__':'__main__','__file__':'<measured-verifier>'}; "
        "exec(compile(data,'<measured-verifier>','exec'),namespace,namespace)"
    )
''',
    '''    launcher = (
        "import sys; data=sys.stdin.buffer.read(); "
        "namespace={'__name__':'__main__','__file__':'<measured-verifier>',"
        "'__AXM_MEASURED_VERIFIER_BYTES__':data}; "
        "exec(compile(data,'<measured-verifier>','exec'),namespace,namespace)"
    )
''',
)

worker = ROOT / "browser_physical_audition_operator_service_worker.js"
replace_once(
    worker,
    '''async function executeInMain(tabId, func, args) {
  const rows = await chrome.scripting.executeScript({
    target: { tabId, frameIds: [0] },
    world: "MAIN",
    func,
    args,
  });
  if (!Array.isArray(rows) || rows.length !== 1 || !rows[0] || !("result" in rows[0])) {
    throw Object.assign(new Error("MAIN-world result denominator differs"), {
      code: "MAIN_WORLD_RESULT_INVALID",
    });
  }
  return rows[0].result;
}
''',
    '''async function executeInMain(tabId, func, args, expectedDocumentId = null) {
  const rows = await chrome.scripting.executeScript({
    target: { tabId, frameIds: [0] },
    world: "MAIN",
    func,
    args,
  });
  if (!Array.isArray(rows) || rows.length !== 1 || !rows[0] || !("result" in rows[0])) {
    throw Object.assign(new Error("MAIN-world result denominator differs"), {
      code: "MAIN_WORLD_RESULT_INVALID",
    });
  }
  const row = rows[0];
  if (typeof row.documentId !== "string" || row.documentId.length < 1) {
    throw Object.assign(new Error("MAIN-world document identity is absent"), {
      code: "MAIN_WORLD_DOCUMENT_ID_INVALID",
    });
  }
  if (expectedDocumentId !== null && row.documentId !== expectedDocumentId) {
    throw Object.assign(new Error("the target document changed during the session"), {
      code: "SESSION_DOCUMENT_MISMATCH",
    });
  }
  return { documentId: row.documentId, result: row.result };
}
''',
)
replace_once(
    worker,
    '''      const inspection = await executeInMain(message.tabId, inspectProbeInPage, [
        CONTRACT.METHODS,
        CONTRACT.MAX_CAPTURE_BYTES,
      ]);
''',
    '''      const execution = await executeInMain(message.tabId, inspectProbeInPage, [
        CONTRACT.METHODS,
        CONTRACT.MAX_CAPTURE_BYTES,
      ]);
      const inspection = execution.result;
''',
)
replace_once(
    worker,
    '''        tabId: message.tabId,
        createdAtUnixMs: Date.now(),
''',
    '''        tabId: message.tabId,
        documentId: execution.documentId,
        createdAtUnixMs: Date.now(),
''',
)
replace_once(
    worker,
    '''      const inspection = await executeInMain(message.tabId, inspectProbeInPage, [
        CONTRACT.METHODS,
        CONTRACT.MAX_CAPTURE_BYTES,
      ]);
      return CONTRACT.response("PASS", message.requestId, {
''',
    '''      const execution = await executeInMain(
        message.tabId,
        inspectProbeInPage,
        [CONTRACT.METHODS, CONTRACT.MAX_CAPTURE_BYTES],
        session.documentId
      );
      const inspection = execution.result;
      return CONTRACT.response("PASS", message.requestId, {
''',
)
replace_once(
    worker,
    '''    const invocation = await executeInMain(message.tabId, invokeProbeInPage, [
      message.method,
      message.args,
      CONTRACT.METHODS,
      CONTRACT.MAX_CAPTURE_BYTES,
    ]);
''',
    '''    const execution = await executeInMain(
      message.tabId,
      invokeProbeInPage,
      [message.method, message.args, CONTRACT.METHODS, CONTRACT.MAX_CAPTURE_BYTES],
      session.documentId
    );
    const invocation = execution.result;
''',
)
replace_once(
    worker,
    '''  } catch (error) {
    return refusal(message?.requestId || rawMessage?.requestId, error);
  }
}
''',
    '''  } catch (error) {
    if (error?.code === "SESSION_DOCUMENT_MISMATCH") {
      sessions.delete(port);
    }
    return refusal(message?.requestId || rawMessage?.requestId, error);
  }
}
''',
)

panel = ROOT / "browser_physical_audition_operator_panel.js"
replace_once(
    panel,
    '''const state = {
  port: chrome.runtime.connect({ name: PORT_NAME }),
  sessionId: null,
''',
    '''const state = {
  port: null,
  sessionId: null,
''',
)
replace_once(
    panel,
    '''function send(message) {
  return new Promise((resolve, reject) => {
    const requestId = message.requestId || randomRequestId();
    const timeout = setTimeout(() => {
      state.pending.delete(requestId);
      reject(new Error("console response timeout"));
    }, 15000);
    state.pending.set(requestId, { resolve, reject, timeout });
    state.port.postMessage({ ...message, requestId });
  });
}

state.port.onMessage.addListener((message) => {
  const pending = state.pending.get(message.requestId);
  if (!pending) return;
  clearTimeout(pending.timeout);
  state.pending.delete(message.requestId);
  if (message.status === "PASS") pending.resolve(message);
  else pending.reject(Object.assign(new Error(message.message || message.code), { code: message.code }));
});

state.port.onDisconnect.addListener(() => {
  for (const pending of state.pending.values()) {
    clearTimeout(pending.timeout);
    pending.reject(new Error("operator console disconnected"));
  }
  state.pending.clear();
  state.sessionId = null;
  state.tabId = null;
  setSessionOpen(false);
  appendLog("REFUSED", "extension service worker disconnected");
});
''',
    '''function settleResponse(message) {
  const pending = state.pending.get(message.requestId);
  if (!pending) return;
  clearTimeout(pending.timeout);
  state.pending.delete(message.requestId);
  if (message.status === "PASS") pending.resolve(message);
  else pending.reject(Object.assign(new Error(message.message || message.code), { code: message.code }));
}

function connectPort() {
  const port = chrome.runtime.connect({ name: PORT_NAME });
  state.port = port;
  port.onMessage.addListener(settleResponse);
  port.onDisconnect.addListener(() => {
    if (state.port !== port) return;
    for (const pending of state.pending.values()) {
      clearTimeout(pending.timeout);
      pending.reject(new Error("operator console disconnected"));
    }
    state.pending.clear();
    state.port = null;
    state.sessionId = null;
    state.tabId = null;
    state.memberHashes.clear();
    elements.memberData.replaceChildren();
    elements.memberList.replaceChildren();
    try {
      connectPort();
    } catch {
      // send() performs the same bounded reconnection before the next request.
    }
    setSessionOpen(false);
    appendLog("REFUSED", "extension service worker disconnected; command session was discarded");
  });
  return port;
}

function ensurePort() {
  return state.port || connectPort();
}

function send(message) {
  return new Promise((resolve, reject) => {
    const requestId = message.requestId || randomRequestId();
    const timeout = setTimeout(() => {
      state.pending.delete(requestId);
      reject(new Error("console response timeout"));
    }, 15000);
    state.pending.set(requestId, { resolve, reject, timeout });
    const port = ensurePort();
    try {
      port.postMessage({ ...message, requestId });
    } catch (error) {
      clearTimeout(timeout);
      state.pending.delete(requestId);
      if (state.port === port) state.port = null;
      reject(error);
    }
  });
}
''',
)
replace_once(
    panel,
    '''    if (field.type === "integer") args[field.name] = Number.parseInt(raw, 10);
    else if (field.type === "number") args[field.name] = Number(raw);
    else args[field.name] = raw;
''',
    '''    if (field.type === "integer") {
      const value = Number(raw);
      if (!Number.isFinite(value) || !Number.isInteger(value)) {
        input.classList.add("invalid");
        throw new Error(`${field.label} must be a complete integer`);
      }
      args[field.name] = value;
    } else if (field.type === "number") {
      const value = Number(raw);
      if (!Number.isFinite(value)) {
        input.classList.add("invalid");
        throw new Error(`${field.label} must be a finite number`);
      }
      args[field.name] = value;
    } else args[field.name] = raw;
''',
)
replace_once(panel, 'renderOperation();\nsetSessionOpen(false);\n', 'connectPort();\nrenderOperation();\nsetSessionOpen(false);\n')

tests = ROOT / "conformance/test_axm_head_browser_physical_audition_operator_console_01.py"
replace_once(tests, 'WITNESS_DENOMINATOR: "76"', 'WITNESS_DENOMINATOR: "81"')
replace_once(
    tests,
    "const root = process.argv[1]; const listeners = []; let activeTabId = 7; const events = []; const members = new Map();",
    "const root = process.argv[1]; const listeners = []; let activeTabId = 7; let documentId = 'document-a'; const events = []; const members = new Map();",
)
replace_once(
    tests,
    "scripting:{async executeScript({func,args}){return [{result:await func(...args)}];}},sidePanel",
    "scripting:{async executeScript({func,args}){return [{documentId,result:await func(...args)}];}},sidePanel",
)
extra_tests = textwrap.dedent(r'''
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
''')
replace_once(tests, '\n\ndef _fixture_test(row: dict, group: str):\n', extra_tests + '\n\ndef _fixture_test(row: dict, group: str):\n')

workflow = Path(".github/workflows/axm-head-browser-physical-audition-operator-console-01.yml")
replace_once(workflow, 'WITNESS_DENOMINATOR: "76"', 'WITNESS_DENOMINATOR: "81"')
replace_once(
    workflow,
    '''          for name in ("direct-verdict.json", "bootstrap-verdict.json"):
              body = json.loads((root / name).read_text(encoding="utf-8"))
              if body.get("status") != "PASS" or body.get("actualSupplierQualified") is not False:
                  raise SystemExit(body)
          bootstrap = json.loads((root / "bootstrap-verdict.json").read_text(encoding="utf-8"))
          if bootstrap.get("bootstrapAuthenticated") is not True:
              raise SystemExit(bootstrap)
''',
    '''          required_checks = {
              "canonical-profile-byte-binding",
              "payload-source-byte-binding",
              "stored-verifier-byte-binding",
          }
          for name in ("direct-verdict.json", "bootstrap-verdict.json"):
              body = json.loads((root / name).read_text(encoding="utf-8"))
              if body.get("status") != "PASS" or body.get("actualSupplierQualified") is not False:
                  raise SystemExit(body)
              if not required_checks.issubset(set(body.get("checks", []))):
                  raise SystemExit(f"repaired custody checks absent: {name}: {body.get('checks')}")
          bootstrap = json.loads((root / "bootstrap-verdict.json").read_text(encoding="utf-8"))
          if bootstrap.get("bootstrapAuthenticated") is not True:
              raise SystemExit(bootstrap)
''',
)

documentation = ROOT / "AXM-HEAD-BROWSER-PHYSICAL-AUDITION-OPERATOR-CONSOLE-01.md"
replace_once(
    documentation,
    'The target page never receives the extension port, session ledger, or service-worker return path. The service worker retains no private capture after responding. Closing the side panel destroys the in-memory session and request ledger.\n',
    'The target page never receives the extension port, session ledger, or service-worker return path. The service worker binds each session to the exact MAIN-world document identity returned by Chromium, invalidates the session after navigation or reload, and retains no private capture after responding. A disconnected Manifest V3 worker port is replaced before the panel permits a new session request. Closing the side panel destroys the in-memory session and request ledger.\n',
)
replace_once(
    documentation,
    'The command contract applies exact-key validation before any page execution. It refuses unknown methods, missing or extra fields, arrays above the closed ceiling, commands above 65,536 encoded bytes, nonfinite numbers, wrong integer types, negative or excessive values, malformed SHA-256 references, invalid layer ranges, unknown partition modes, unknown pipeline roles, unknown receipt classes, raw URL or file coordinates, raw IPv4 identities, and malformed opaque member identifiers.\n',
    'The command contract applies exact-key validation before any page execution. The panel parses complete numeric values and refuses a fractional integer instead of truncating the operator input. The contract refuses unknown methods, missing or extra fields, arrays above the closed ceiling, commands above 65,536 encoded bytes, nonfinite numbers, wrong integer types, negative or excessive values, malformed SHA-256 references, invalid layer ranges, unknown partition modes, unknown pipeline roles, unknown receipt classes, raw URL or file coordinates, raw IPv4 identities, and malformed opaque member identifiers.\n',
)
replace_once(
    documentation,
    'The direct verifier ignores the stored extension identity until it has independently reconstructed the source set, dependencies, manifest, probe digest, payload members, extension identity, static no-network law, closed method denominator, service-worker mechanism, and extension-page content-security posture. The external bootstrap measures the verifier once, executes only the measured byte string under an isolated interpreter, binds the stored verifier member back to those bytes, and only then marks the verdict bootstrap-authenticated.\n',
    'The direct verifier ignores the stored extension identity until it has independently reconstructed the source set, dependencies, manifest, probe digest, payload members, extension identity, static no-network law, closed method denominator, service-worker mechanism, and extension-page content-security posture. It now requires the supplied profile bytes to equal the canonical repository member, every generated payload byte to equal its deterministic manifest, admitted dependency, or source member, and the executing verifier bytes to equal the stored source member. The external bootstrap measures the verifier once, injects those measured bytes into the isolated verifier namespace, binds the stored verifier member back to them, and only then marks the verdict bootstrap-authenticated.\n',
)
replace_once(
    documentation,
    'The source campaign contains fifty-two command and envelope cases. The permanent hostile suite retains the contract in both Python and JavaScript, executes a complete synthetic side-panel-to-service-worker-to-frozen-probe sequence, and proves deterministic extension construction and independent verification.\n',
    'The source campaign contains fifty-two command and envelope cases. The permanent eighty-one-witness hostile suite retains the contract in both Python and JavaScript, executes a complete synthetic side-panel-to-service-worker-to-frozen-probe sequence, and proves deterministic extension construction, payload-to-source custody, canonical profile and verifier binding, worker-port recovery, navigation-bound session invalidation, complete integer parsing, and independent verification.\n',
)
