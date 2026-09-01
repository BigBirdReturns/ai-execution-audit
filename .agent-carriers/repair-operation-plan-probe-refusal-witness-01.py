from __future__ import annotations

import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
path = root / "mating_surface/anchor_node/conformance/test_axm_head_browser_audition_operation_plan_01.py"
text = path.read_text(encoding="utf-8")
start_marker = "    def test_048_nominal_pass_probe_refusal_halts_mutated_plan(self):\n"
end_marker = "\n\ndef add_fixture_witnesses() -> None:\n"
if text.count(start_marker) != 1 or text.count(end_marker) != 1:
    raise SystemExit("test_048 replacement denominator differs")
start = text.index(start_marker)
end = text.index(end_marker, start)
replacement = r'''    def test_048_nominal_pass_probe_refusal_halts_mutated_plan(self):
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
'''
updated = text[:start] + replacement + text[end:]
if updated.count("def test_048_nominal_pass_probe_refusal_halts_mutated_plan") != 1:
    raise SystemExit("test_048 successor denominator differs")
if "literalArgs:{}" in updated[start : start + len(replacement)]:
    raise SystemExit("invalid literal witness survived")
with path.open("w", encoding="utf-8", newline="\n") as handle:
    handle.write(updated)
print("repaired test_048 to use admitted fixture arguments")
