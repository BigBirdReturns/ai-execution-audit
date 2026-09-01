from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()

EXPECTED_BLOBS = {
    ".github/workflows/axm-head-browser-audition-operation-plan-01.yml": "644e4349fff27e1441ee6c06a5dca767e73db2da",
    "mating_surface/anchor_node/AXM-HEAD-BROWSER-AUDITION-OPERATION-PLAN-01.md": "1cdd2111241f9b6081c5d6bcce9d6988332a01e1",
    "mating_surface/anchor_node/axm_head_browser_audition_operation_plan_01.py": "82b8f56834fc51c67b2d5ba1580802ce15ae8411",
    "mating_surface/anchor_node/browser_audition_operation_plan_panel.js": "24e94dd9a3da9208209f88efc9d9768ffe68adc9",
    "mating_surface/anchor_node/conformance/test_axm_head_browser_audition_operation_plan_01.py": "41baf610a37da0cfd6b781c5a5bd73f290c70e30",
    "mating_surface/anchor_node/verify_axm_head_browser_audition_operation_plan_01.py": "de684b129521268696337508b48adf4280de8bf6",
}


def git_blob(relative: str) -> str:
    return subprocess.check_output(
        ["git", "hash-object", relative], cwd=ROOT, text=True
    ).strip()


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
    '''function updateInspection(inspection) {
  if (!inspection) return;
  el.probeState.textContent = inspection.status === "PASS" ? `version ${inspection.probeVersion}` : inspection.code || "refused";
  el.probeEarly.textContent = inspection.installedBeforeApplication === true ? "yes" : "no";
  el.probeEvents.textContent = String(inspection.observedEventCount ?? 0);
}
function refreshControls() {''',
    '''function updateInspection(inspection) {
  if (!inspection) return;
  el.probeState.textContent = inspection.status === "PASS" ? `version ${inspection.probeVersion}` : inspection.code || "refused";
  el.probeEarly.textContent = inspection.installedBeforeApplication === true ? "yes" : "no";
  el.probeEvents.textContent = String(inspection.observedEventCount ?? 0);
}
function requireHealthyInspection(inspection) {
  updateInspection(inspection);
  if (!inspection || inspection.status !== "PASS") {
    throw Object.assign(new Error(inspection?.code || "probe inspection refused"), {
      code: inspection?.code || "PROBE_INSPECTION_REFUSED",
    });
  }
  if (!Object.prototype.hasOwnProperty.call(inspection, "probeRefused")) {
    throw Object.assign(new Error("probe refusal state is absent"), {
      code: "PROBE_REFUSAL_STATE_ABSENT",
    });
  }
  if (inspection.probeRefused !== null) {
    throw Object.assign(new Error("probe reported a capture refusal"), {
      code: "PROBE_CAPTURE_REFUSED",
    });
  }
  return inspection;
}
function refreshControls() {''',
)
replace_exact(
    panel,
    '''    const response = await send({ protocol: OPERATOR.PROTOCOL, kind: "open-session", tabId });
    state.sessionId = response.sessionId;
    state.tabId = response.tabId;
    state.terminal = "SESSION_OPEN";
    updateInspection(response.inspection);
    log("PASS", "exact active document bound to a fresh console session");''',
    '''    const response = await send({ protocol: OPERATOR.PROTOCOL, kind: "open-session", tabId });
    requireHealthyInspection(response.inspection);
    state.sessionId = response.sessionId;
    state.tabId = response.tabId;
    state.terminal = "SESSION_OPEN";
    log("PASS", "exact active document bound to a fresh console session");''',
)
replace_exact(
    panel,
    "    updateInspection(response.inspection);",
    "    requireHealthyInspection(response.inspection);",
    count=3,
)

workflow = ".github/workflows/axm-head-browser-audition-operation-plan-01.yml"
replace_exact(workflow, '  WITNESS_DENOMINATOR: "68"', '  WITNESS_DENOMINATOR: "72"')

primary = "mating_surface/anchor_node/axm_head_browser_audition_operation_plan_01.py"
replace_exact(
    primary,
    "        'settleSessionLoss',\n        'serializeCaptureForDownload',",
    "        'settleSessionLoss',\n        'requireHealthyInspection',\n        'PROBE_REFUSAL_STATE_ABSENT',\n        'PROBE_CAPTURE_REFUSED',\n        'serializeCaptureForDownload',",
)
replace_exact(
    primary,
    '''    for marker in required_panel_controls:
        if marker not in panel_source:
            refuse("PANEL_CONTROL_MISSING", marker)
    if "JSON.stringify(capture, null, 2)" in panel_source:''',
    '''    for marker in required_panel_controls:
        if marker not in panel_source:
            refuse("PANEL_CONTROL_MISSING", marker)
    if panel_source.count('requireHealthyInspection(response.inspection)') != 4:
        refuse("PANEL_CONTROL_COUNT_INVALID", "healthy inspection call denominator")
    if "JSON.stringify(capture, null, 2)" in panel_source:''',
)
replace_exact(
    primary,
    '            "mutation-uncertainty-stop",\n            "exact-download-byte-binding",',
    '            "mutation-uncertainty-stop",\n            "probe-refusal-state-stop",\n            "exact-download-byte-binding",',
)

verifier = "mating_surface/anchor_node/verify_axm_head_browser_audition_operation_plan_01.py"
replace_exact(
    verifier,
    '''        "settleSessionLoss",
        "serializeCaptureForDownload",''',
    '''        "settleSessionLoss",
        "requireHealthyInspection",
        "PROBE_REFUSAL_STATE_ABSENT",
        "PROBE_CAPTURE_REFUSED",
        "serializeCaptureForDownload",''',
)
replace_exact(
    verifier,
    '''    for marker in (
        "HALTED_PARTIAL_CAPTURE",''',
    '''    for marker in (
        "HALTED_PARTIAL_CAPTURE",''',
)
replace_exact(
    verifier,
    '''    ):
        if marker not in panel_source:
            fail("PANEL_CONTROL_MISSING", marker)
    if "JSON.stringify(capture, null, 2)" in panel_source:''',
    '''    ):
        if marker not in panel_source:
            fail("PANEL_CONTROL_MISSING", marker)
    if panel_source.count('requireHealthyInspection(response.inspection)') != 4:
        fail("PANEL_CONTROL_COUNT_INVALID", "healthy inspection call denominator")
    if "JSON.stringify(capture, null, 2)" in panel_source:''',
)
replace_exact(
    verifier,
    '"pristine-ledger-preflight", "mutation-uncertainty-stop", "exact-download-byte-binding"',
    '"pristine-ledger-preflight", "mutation-uncertainty-stop", "probe-refusal-state-stop", "exact-download-byte-binding"',
)

tests = "mating_surface/anchor_node/conformance/test_axm_head_browser_audition_operation_plan_01.py"
replace_exact(
    tests,
    '''connectPort,requirePristineCapture,serializeCaptureForDownload''',
    '''connectPort,requireHealthyInspection,requirePristineCapture,serializeCaptureForDownload''',
)
replace_exact(
    tests,
    '''inspection:{status:'PASS',probeVersion:'1',installedBeforeApplication:true,observedEventCount:1}''',
    '''inspection:{status:'PASS',probeVersion:'1',installedBeforeApplication:true,probeRefused:null,observedEventCount:1}''',
)
new_tests = r'''
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
        result = run_panel_harness(r"""
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
    if(message.kind==='close-session') response.kind='session-closed';
    queueMicrotask(()=>messageListeners.forEach(fn=>fn(response)));
  },
}));
test.connectPort();
test.state.plan={steps:[
  {stepId:'step:first-mark',kind:'probe-call',method:'markAvailability',literalArgs:{}},
  {stepId:'step:second-mark',kind:'probe-call',method:'markAdapterArtifact',literalArgs:{}},
  {stepId:'step:must-not-run',kind:'probe-call',method:'markFormation',literalArgs:{}},
]};
test.state.bindings={};
test.state.sessionId='session:'+'1'.repeat(32);
test.state.tabId=7;
test.state.terminal='SESSION_OPEN';
await test.runPlan();
console.log(JSON.stringify({terminal:test.state.terminal,nextIndex:test.state.nextIndex,mutation:test.state.probeMutationPossible,sessionId:test.state.sessionId,loadDisabled:test.el.load.disabled,openDisabled:test.el.open.disabled,invocations}));
""")
        self.assertEqual(result, {
            "terminal": "HALTED_PARTIAL_CAPTURE",
            "nextIndex": 1,
            "mutation": True,
            "sessionId": None,
            "loadDisabled": True,
            "openDisabled": True,
            "invocations": ["markAvailability", "markAdapterArtifact"],
        })
'''
replace_exact(
    tests,
    "\n\ndef add_fixture_witnesses() -> None:\n",
    "\n" + new_tests + "\n\ndef add_fixture_witnesses() -> None:\n",
)

document = "mating_surface/anchor_node/AXM-HEAD-BROWSER-AUDITION-OPERATION-PLAN-01.md"
replace_exact(
    document,
    '''The second barrier requires a separate acknowledgement after the physical observation and before local private capture export. A refusal, document change, service-worker disconnect, channel failure, timeout, invalid opaque member result, or premature close after a mutating invocation may have begun terminates `HALTED_PARTIAL_CAPTURE`.''',
    '''The second barrier requires a separate acknowledgement after the physical observation and before local private capture export. Every nominally successful console response must carry an explicit `probeRefused: null` inspection. A missing refusal state or any non-null refusal object stops execution before the cursor can advance. A refusal, document change, service-worker disconnect, channel failure, timeout, invalid opaque member result, or premature close after a mutating invocation may have begun terminates `HALTED_PARTIAL_CAPTURE`.''',
)

changed = sorted(
    subprocess.check_output(
        ["git", "diff", "--name-only"], cwd=ROOT, text=True
    ).splitlines()
)
expected = sorted(EXPECTED_BLOBS)
if changed != expected:
    raise SystemExit(f"patch denominator differs: observed={changed} expected={expected}")

for relative in changed:
    data = (ROOT / relative).read_bytes()
    if not data or b"\r" in data:
        raise SystemExit(f"invalid patched bytes: {relative}")
    data.decode("utf-8")

print("patched probe-refusal controls across six exact source members")
