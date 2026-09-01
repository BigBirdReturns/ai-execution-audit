from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()

EXPECTED_BLOBS = {
    ".github/workflows/axm-head-browser-audition-operation-plan-01.yml": "14f6a17543016a7cad0a76fc851a9a82bf6e9ab5",
    "mating_surface/anchor_node/AXM-HEAD-BROWSER-AUDITION-OPERATION-PLAN-01.md": "9a5c03cf60ada225eefd882c87c4bd0dc02db460",
    "mating_surface/anchor_node/axm_head_browser_audition_operation_plan_01.py": "cb4ddafb4f55db7cc8f268bb3e0291a98690bee2",
    "mating_surface/anchor_node/browser_audition_operation_plan_panel.js": "3aa03eaf48d72e2c0daf34aebba132a0a53c5f01",
    "mating_surface/anchor_node/conformance/test_axm_head_browser_audition_operation_plan_01.py": "1956069416d864c7813f3d95eee7ece7ecfcd693",
    "mating_surface/anchor_node/verify_axm_head_browser_audition_operation_plan_01.py": "bab42efed9f604afc4015d785cc7c6a284110761",
}


def git_blob(relative: str) -> str:
    return subprocess.check_output(["git", "hash-object", relative], cwd=ROOT, text=True).strip()


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def write(relative: str, text: str) -> None:
    if "\r" in text:
        raise SystemExit(f"refusing CR-bearing replacement: {relative}")
    with (ROOT / relative).open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def replace_exact(relative: str, old: str, new: str, count: int = 1) -> None:
    text = read(relative)
    observed = text.count(old)
    if observed != count:
        raise SystemExit(
            f"replacement denominator differs for {relative}: expected={count} observed={observed}"
        )
    write(relative, text.replace(old, new))


for path, wanted in EXPECTED_BLOBS.items():
    observed = git_blob(path)
    if observed != wanted:
        raise SystemExit(f"predecessor blob differs: {path}: {observed} != {wanted}")

panel = "mating_surface/anchor_node/browser_audition_operation_plan_panel.js"
replace_exact(
    panel,
    '''function discardSessionState(reason) {
  for (const pending of state.pending.values()) {
    clearTimeout(pending.timer);
    pending.reject(new Error(reason));
  }
  state.pending.clear();
  state.sessionId = null;
  state.tabId = null;
}
function connectPort() {''',
    '''function discardSessionState(reason) {
  for (const pending of state.pending.values()) {
    clearTimeout(pending.timer);
    pending.reject(new Error(reason));
  }
  state.pending.clear();
  state.sessionId = null;
  state.tabId = null;
}
function disconnectCurrentPort() {
  const port = state.port;
  if (!port) return;
  state.port = null;
  try { port.disconnect(); } catch { /* the browser owns final port disposal */ }
}
async function releaseFailedOpenSession(response) {
  let closed = false;
  if (response && typeof response.sessionId === "string" && Number.isInteger(response.tabId)) {
    state.sessionId = response.sessionId;
    state.tabId = response.tabId;
    try {
      await sessionMessage("close-session");
      closed = true;
    } catch {
      // Disconnecting the owning port is the authoritative worker-session fallback.
    }
  }
  if (!closed) disconnectCurrentPort();
  discardSessionState("session open failed");
  return closed;
}
function connectPort() {''',
)
replace_exact(
    panel,
    '''async function sessionMessage(kind, extra = {}) {
  if (!state.sessionId || !Number.isInteger(state.tabId)) throw new Error("document session is not open");
  return send({ protocol: OPERATOR.PROTOCOL, kind, tabId: state.tabId, sessionId: state.sessionId, ...extra });
}
async function readJsonFile(input, label) {''',
    '''async function sessionMessage(kind, extra = {}) {
  if (!state.sessionId || !Number.isInteger(state.tabId)) throw new Error("document session is not open");
  return send({ protocol: OPERATOR.PROTOCOL, kind, tabId: state.tabId, sessionId: state.sessionId, ...extra });
}
async function requirePostInvocationInspection() {
  const response = await sessionMessage("status");
  return requireHealthyInspection(response.inspection);
}
async function readJsonFile(input, label) {''',
)
replace_exact(
    panel,
    '''async function openSession() {
  try {
    const tabId = await activeTabId();
    const response = await send({ protocol: OPERATOR.PROTOCOL, kind: "open-session", tabId });
    requireHealthyInspection(response.inspection);
    state.sessionId = response.sessionId;
    state.tabId = response.tabId;
    state.terminal = "SESSION_OPEN";
    log("PASS", "exact active document bound to a fresh console session");
  } catch (error) {
    discardSessionState("session open failed");
    log("REFUSED", `${error.code || "OPEN_FAILED"}: ${error.message}`);
  }
  refreshControls();
}''',
    '''async function openSession() {
  let response = null;
  try {
    const tabId = await activeTabId();
    response = await send({ protocol: OPERATOR.PROTOCOL, kind: "open-session", tabId });
    state.sessionId = response.sessionId;
    state.tabId = response.tabId;
    requireHealthyInspection(response.inspection);
    state.terminal = "SESSION_OPEN";
    log("PASS", "exact active document bound to a fresh console session");
  } catch (error) {
    await releaseFailedOpenSession(response);
    settleSessionLoss(state.plan && state.bindings ? "LOADED" : "IDLE");
    log("REFUSED", `${error.code || "OPEN_FAILED"}: ${error.message}`);
  }
  refreshControls();
}''',
)
replace_exact(
    panel,
    '''        const response = await sessionMessage("invoke", { method: current.method, args });
        requireHealthyInspection(response.inspection);
        if (current.method === "exportCapture" && current.captureUse === "preflight") {''',
    '''        const response = await sessionMessage("invoke", { method: current.method, args });
        requireHealthyInspection(response.inspection);
        await requirePostInvocationInspection();
        if (current.method === "exportCapture" && current.captureUse === "preflight") {''',
)

workflow = ".github/workflows/axm-head-browser-audition-operation-plan-01.yml"
replace_exact(workflow, '  WITNESS_DENOMINATOR: "72"', '  WITNESS_DENOMINATOR: "78"')

primary = "mating_surface/anchor_node/axm_head_browser_audition_operation_plan_01.py"
replace_exact(
    primary,
    '''        'settleSessionLoss',
        'requireHealthyInspection',
        'PROBE_REFUSAL_STATE_ABSENT',
        'PROBE_CAPTURE_REFUSED',
        'serializeCaptureForDownload',''',
    '''        'settleSessionLoss',
        'requireHealthyInspection',
        'requirePostInvocationInspection',
        'releaseFailedOpenSession',
        'disconnectCurrentPort',
        'PROBE_REFUSAL_STATE_ABSENT',
        'PROBE_CAPTURE_REFUSED',
        'serializeCaptureForDownload',''',
)
replace_exact(
    primary,
    '''    if panel_source.count('requireHealthyInspection(response.inspection)') != 4:
        refuse("PANEL_CONTROL_COUNT_INVALID", "healthy inspection call denominator")
    if "JSON.stringify(capture, null, 2)" in panel_source:''',
    '''    if panel_source.count('requireHealthyInspection(response.inspection)') != 5:
        refuse("PANEL_CONTROL_COUNT_INVALID", "healthy inspection call denominator")
    invoke_marker = 'const response = await sessionMessage("invoke", { method: current.method, args });'
    post_marker = 'await requirePostInvocationInspection();'
    invoke_index = panel_source.find(invoke_marker)
    post_index = panel_source.find(post_marker, invoke_index + 1)
    save_index = panel_source.find('state.resultRefs.set(current.saveResultAs, response.result);', post_index + 1)
    download_index = panel_source.find('downloadCapture(response.result)', post_index + 1)
    cursor_index = panel_source.find('state.nextIndex += 1;', post_index + 1)
    if min(invoke_index, post_index, save_index, download_index, cursor_index) < 0 or not (
        invoke_index < post_index < save_index < cursor_index and post_index < download_index < cursor_index
    ):
        refuse("PANEL_CONTROL_ORDER_INVALID", "post-invocation inspection")
    open_index = panel_source.find('async function openSession()')
    open_send_index = panel_source.find('response = await send({ protocol: OPERATOR.PROTOCOL, kind: "open-session", tabId });', open_index)
    session_index = panel_source.find('state.sessionId = response.sessionId;', open_send_index)
    open_inspection_index = panel_source.find('requireHealthyInspection(response.inspection);', session_index)
    release_index = panel_source.find('await releaseFailedOpenSession(response);', open_inspection_index)
    if min(open_index, open_send_index, session_index, open_inspection_index, release_index) < 0 or not (
        open_index < open_send_index < session_index < open_inspection_index < release_index
    ):
        refuse("PANEL_CONTROL_ORDER_INVALID", "failed-open session release")
    release_start = panel_source.find('async function releaseFailedOpenSession(response)')
    release_end = panel_source.find('function connectPort()', release_start)
    release_block = panel_source[release_start:release_end]
    for marker in ('sessionMessage("close-session")', 'disconnectCurrentPort()', 'discardSessionState("session open failed")'):
        if marker not in release_block:
            refuse("PANEL_CONTROL_MISSING", marker)
    if "JSON.stringify(capture, null, 2)" in panel_source:''',
)
replace_exact(
    primary,
    '''            "mutation-uncertainty-stop",
            "probe-refusal-state-stop",
            "exact-download-byte-binding",''',
    '''            "mutation-uncertainty-stop",
            "probe-refusal-state-stop",
            "post-invocation-inspection-stop",
            "failed-open-session-release",
            "exact-download-byte-binding",''',
)

verifier = "mating_surface/anchor_node/verify_axm_head_browser_audition_operation_plan_01.py"
replace_exact(
    verifier,
    '''        "settleSessionLoss",
        "requireHealthyInspection",
        "PROBE_REFUSAL_STATE_ABSENT",
        "PROBE_CAPTURE_REFUSED",
        "serializeCaptureForDownload",''',
    '''        "settleSessionLoss",
        "requireHealthyInspection",
        "requirePostInvocationInspection",
        "releaseFailedOpenSession",
        "disconnectCurrentPort",
        "PROBE_REFUSAL_STATE_ABSENT",
        "PROBE_CAPTURE_REFUSED",
        "serializeCaptureForDownload",''',
)
replace_exact(
    verifier,
    '''    if panel_source.count('requireHealthyInspection(response.inspection)') != 4:
        fail("PANEL_CONTROL_COUNT_INVALID", "healthy inspection call denominator")
    if "JSON.stringify(capture, null, 2)" in panel_source:''',
    '''    if panel_source.count('requireHealthyInspection(response.inspection)') != 5:
        fail("PANEL_CONTROL_COUNT_INVALID", "healthy inspection call denominator")
    invoke_marker = 'const response = await sessionMessage("invoke", { method: current.method, args });'
    post_marker = 'await requirePostInvocationInspection();'
    invoke_index = panel_source.find(invoke_marker)
    post_index = panel_source.find(post_marker, invoke_index + 1)
    save_index = panel_source.find('state.resultRefs.set(current.saveResultAs, response.result);', post_index + 1)
    download_index = panel_source.find('downloadCapture(response.result)', post_index + 1)
    cursor_index = panel_source.find('state.nextIndex += 1;', post_index + 1)
    if min(invoke_index, post_index, save_index, download_index, cursor_index) < 0 or not (
        invoke_index < post_index < save_index < cursor_index and post_index < download_index < cursor_index
    ):
        fail("PANEL_CONTROL_ORDER_INVALID", "post-invocation inspection")
    open_index = panel_source.find('async function openSession()')
    open_send_index = panel_source.find('response = await send({ protocol: OPERATOR.PROTOCOL, kind: "open-session", tabId });', open_index)
    session_index = panel_source.find('state.sessionId = response.sessionId;', open_send_index)
    open_inspection_index = panel_source.find('requireHealthyInspection(response.inspection);', session_index)
    release_index = panel_source.find('await releaseFailedOpenSession(response);', open_inspection_index)
    if min(open_index, open_send_index, session_index, open_inspection_index, release_index) < 0 or not (
        open_index < open_send_index < session_index < open_inspection_index < release_index
    ):
        fail("PANEL_CONTROL_ORDER_INVALID", "failed-open session release")
    release_start = panel_source.find('async function releaseFailedOpenSession(response)')
    release_end = panel_source.find('function connectPort()', release_start)
    release_block = panel_source[release_start:release_end]
    for marker in ('sessionMessage("close-session")', 'disconnectCurrentPort()', 'discardSessionState("session open failed")'):
        if marker not in release_block:
            fail("PANEL_CONTROL_MISSING", marker)
    if "JSON.stringify(capture, null, 2)" in panel_source:''',
)
replace_exact(
    verifier,
    '''"pristine-ledger-preflight", "mutation-uncertainty-stop", "probe-refusal-state-stop", "exact-download-byte-binding"''',
    '''"pristine-ledger-preflight", "mutation-uncertainty-stop", "probe-refusal-state-stop", "post-invocation-inspection-stop", "failed-open-session-release", "exact-download-byte-binding"''',
)

tests = "mating_surface/anchor_node/conformance/test_axm_head_browser_audition_operation_plan_01.py"
replace_exact(
    tests,
    '''        postMessage() { throw new Error('unconfigured port'); },
        __messageListeners: messageListeners,''',
    '''        postMessage() { throw new Error('unconfigured port'); },
        disconnect() { disconnectListeners.forEach((fn) => fn()); },
        __messageListeners: messageListeners,''',
)
replace_exact(
    tests,
    '''const panelSource = fs.readFileSync({json.dumps(str(panel_path))}, 'utf8') + `\n;globalThis.__AXM_PANEL_TEST__={{state,el,refreshControls,resetExecutionProgress,settleSessionLoss,discardSessionState,connectPort,requireHealthyInspection,requirePristineCapture,serializeCaptureForDownload,downloadCapture,runPlan,acknowledgeBarrier,closeSession}};`;''',
    '''const panelSource = fs.readFileSync({json.dumps(str(panel_path))}, 'utf8') + `\n;globalThis.__AXM_PANEL_TEST__={{state,el,refreshControls,resetExecutionProgress,settleSessionLoss,discardSessionState,disconnectCurrentPort,releaseFailedOpenSession,connectPort,openSession,requireHealthyInspection,requirePostInvocationInspection,requirePristineCapture,serializeCaptureForDownload,downloadCapture,runPlan,acknowledgeBarrier,closeSession}};`;''',
)
replace_exact(
    tests,
    '''        self.assertLessEqual(plan["probeInvocationCount"] + 4, tool.MAX_SESSION_REQUESTS)''',
    '''        self.assertLessEqual(plan["probeInvocationCount"] * 2 + 4, tool.MAX_SESSION_REQUESTS)''',
)
replace_exact(
    tests,
    '''    if(message.kind==='invoke') {
      invocations.push(message.method);
      response.result=null;
      response.inspection={status:'PASS',probeVersion:'1',installedBeforeApplication:true,probeRefused:invocations.length===2?{code:'EVENT_LIMIT_EXCEEDED'}:null,observedEventCount:invocations.length};
    }
    if(message.kind==='close-session') response.kind='session-closed';''',
    '''    if(message.kind==='invoke') {
      invocations.push(message.method);
      response.result=null;
      response.inspection={status:'PASS',probeVersion:'1',installedBeforeApplication:true,probeRefused:invocations.length===2?{code:'EVENT_LIMIT_EXCEEDED'}:null,observedEventCount:invocations.length};
    }
    if(message.kind==='status') response.inspection={status:'PASS',probeVersion:'1',installedBeforeApplication:true,probeRefused:null,observedEventCount:invocations.length};
    if(message.kind==='close-session') response.kind='session-closed';''',
)
new_tests = r'''
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
'''
replace_exact(
    tests,
    "\n\ndef add_fixture_witnesses() -> None:\n",
    "\n" + new_tests + "\n\ndef add_fixture_witnesses() -> None:\n",
)

document = "mating_surface/anchor_node/AXM-HEAD-BROWSER-AUDITION-OPERATION-PLAN-01.md"
replace_exact(
    document,
    '''The panel loads one plan and one binding file into memory, recomputes both content identities, reconstructs the compiler output, and requires byte-equivalent semantics before opening a document session. It uses the admitted extension port and service worker. It cannot issue an operation outside the admitted fourteen-method denominator.''',
    '''The panel loads one plan and one binding file into memory, recomputes both content identities, reconstructs the compiler output, and requires byte-equivalent semantics before opening a document session. It uses the admitted extension port and service worker. It cannot issue an operation outside the admitted fourteen-method denominator. Because the admitted worker returns an invocation inspection captured before the invoked method runs, the panel performs a separate fresh `status` inspection after every probe invocation and before accepting a result, saving an alias, downloading a capture, logging completion, or advancing the cursor.''',
)
replace_exact(
    document,
    '''The second barrier requires a separate acknowledgement after the physical observation and before local private capture export. Every nominally successful console response must carry an explicit `probeRefused: null` inspection. A missing refusal state or any non-null refusal object stops execution before the cursor can advance. A refusal, document change, service-worker disconnect, channel failure, timeout, invalid opaque member result, or premature close after a mutating invocation may have begun terminates `HALTED_PARTIAL_CAPTURE`.''',
    '''The second barrier requires a separate acknowledgement after the physical observation and before local private capture export. Every nominally successful console response must carry an explicit `probeRefused: null` inspection. A missing refusal state or any non-null refusal object stops execution before the cursor can advance. An open-session inspection failure retains the returned session identifiers long enough to request closure; if closure cannot be confirmed, the panel disconnects the owning port so the worker deletes the session before a later open attempt. A refusal, document change, service-worker disconnect, channel failure, timeout, invalid opaque member result, or premature close after a mutating invocation may have begun terminates `HALTED_PARTIAL_CAPTURE`.''',
)

changed = sorted(subprocess.check_output(["git", "diff", "--name-only"], cwd=ROOT, text=True).splitlines())
expected = sorted(EXPECTED_BLOBS)
if changed != expected:
    raise SystemExit(f"patch denominator differs: observed={changed} expected={expected}")
for relative in changed:
    data = (ROOT / relative).read_bytes()
    if not data or b"\r" in data:
        raise SystemExit(f"invalid patched bytes: {relative}")
    data.decode("utf-8")
print("patched post-call inspection and failed-open release across six exact source members")
