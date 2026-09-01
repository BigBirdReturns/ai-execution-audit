from __future__ import annotations

from pathlib import Path


def replace_exact(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"replacement denominator differs for {path}: {count}")
    target.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


python_path = "mating_surface/anchor_node/axm_head_browser_audition_operation_plan_01.py"
replace_exact(
    python_path,
    "MAX_RECEIPT_COUNT = 9\nMAX_SESSION_REQUESTS = 512\n",
    "MAX_RECEIPT_COUNT = 9\nMAX_SESSION_REQUESTS = 512\nSESSION_REQUESTS_PER_PROBE_INVOCATION = 2\nSESSION_REQUEST_RESERVE = 4\n",
)
replace_exact(
    python_path,
    "        \"maximumReceiptCount\": MAX_RECEIPT_COUNT,\n        \"operatorMaximumSessionRequests\": MAX_SESSION_REQUESTS,\n",
    "        \"maximumReceiptCount\": MAX_RECEIPT_COUNT,\n        \"operatorMaximumSessionRequests\": MAX_SESSION_REQUESTS,\n        \"sessionRequestReserve\": SESSION_REQUEST_RESERVE,\n        \"sessionRequestsPerProbeInvocation\": SESSION_REQUESTS_PER_PROBE_INVOCATION,\n",
)
replace_exact(
    python_path,
    '''def normalized_plan_body(plan: dict[str, Any]) -> dict[str, Any]:
    body = json.loads(json.dumps(plan))
    body["planId"] = None
    return body


def compile_plan(bindings: dict[str, Any]) -> dict[str, Any]:
    steps = expected_steps(bindings)
    invocation_count = sum(row["kind"] == "probe-call" for row in steps)
    if len(steps) > MAX_PLAN_STEPS or invocation_count > MAX_PROBE_INVOCATIONS or invocation_count + 4 > MAX_SESSION_REQUESTS:
        refuse("PLAN_LIMIT_EXCEEDED", f"steps={len(steps)} invocations={invocation_count}")
''',
    '''def normalized_plan_body(plan: dict[str, Any]) -> dict[str, Any]:
    body = json.loads(json.dumps(plan))
    body["planId"] = None
    return body


def required_session_requests(probe_invocation_count: int) -> int:
    return probe_invocation_count * SESSION_REQUESTS_PER_PROBE_INVOCATION + SESSION_REQUEST_RESERVE


def compile_plan(bindings: dict[str, Any]) -> dict[str, Any]:
    steps = expected_steps(bindings)
    invocation_count = sum(row["kind"] == "probe-call" for row in steps)
    session_request_count = required_session_requests(invocation_count)
    if len(steps) > MAX_PLAN_STEPS or invocation_count > MAX_PROBE_INVOCATIONS or session_request_count > MAX_SESSION_REQUESTS:
        refuse(
            "PLAN_LIMIT_EXCEEDED",
            f"steps={len(steps)} invocations={invocation_count} sessionRequests={session_request_count}",
        )
''',
)

contract_path = "mating_surface/anchor_node/browser_audition_operation_plan_contract.js"
replace_exact(
    contract_path,
    "  const MAX_ARTIFACT_COUNT = 256;\n  const RECEIPT_KINDS = Object.freeze([\n",
    "  const MAX_ARTIFACT_COUNT = 256;\n  const SESSION_REQUESTS_PER_PROBE_INVOCATION = 2;\n  const SESSION_REQUEST_RESERVE = 4;\n  const RECEIPT_KINDS = Object.freeze([\n",
)
replace_exact(
    contract_path,
    '''    const probeInvocationCount = steps.filter((row) => row.kind === "probe-call").length;
    if (steps.length > MAX_PLAN_STEPS || probeInvocationCount > MAX_PROBE_INVOCATIONS || probeInvocationCount + 4 > OPERATOR.MAX_SESSION_REQUESTS) fail("PLAN_LIMIT_EXCEEDED", `${steps.length}/${probeInvocationCount}`);
''',
    '''    const probeInvocationCount = steps.filter((row) => row.kind === "probe-call").length;
    const requiredSessionRequests = probeInvocationCount * SESSION_REQUESTS_PER_PROBE_INVOCATION + SESSION_REQUEST_RESERVE;
    if (steps.length > MAX_PLAN_STEPS || probeInvocationCount > MAX_PROBE_INVOCATIONS || requiredSessionRequests > OPERATOR.MAX_SESSION_REQUESTS) fail("PLAN_LIMIT_EXCEEDED", `${steps.length}/${probeInvocationCount}/${requiredSessionRequests}`);
''',
)
replace_exact(
    contract_path,
    '''    CLAIM_BOUNDARY, RECEIPT_KINDS, MAX_PLAN_BYTES, MAX_BINDINGS_BYTES, MAX_PLAN_STEPS,
    PlanContractError, encodedBytes, validateBindings, validatePlan, validateBundle,
''',
    '''    CLAIM_BOUNDARY, RECEIPT_KINDS, MAX_PLAN_BYTES, MAX_BINDINGS_BYTES, MAX_PLAN_STEPS,
    SESSION_REQUESTS_PER_PROBE_INVOCATION, SESSION_REQUEST_RESERVE,
    PlanContractError, encodedBytes, validateBindings, validatePlan, validateBundle,
''',
)

profile_path = "mating_surface/anchor_node/axm-head-browser-audition-operation-plan-profile-01.json"
replace_exact(
    profile_path,
    '    "operatorMaximumSessionRequests": 512\n',
    '    "operatorMaximumSessionRequests": 512,\n    "sessionRequestReserve": 4,\n    "sessionRequestsPerProbeInvocation": 2\n',
)

verifier_path = "mating_surface/anchor_node/verify_axm_head_browser_audition_operation_plan_01.py"
replace_exact(
    verifier_path,
    '''    if profile.get("schema") != PROFILE_SCHEMA or profile.get("profileId") != PROFILE_ID:
        fail("PROFILE_IDENTITY_INVALID", str(profile_path))
    admitted = profile.get("admittedConsole")
''',
    '''    if profile.get("schema") != PROFILE_SCHEMA or profile.get("profileId") != PROFILE_ID:
        fail("PROFILE_IDENTITY_INVALID", str(profile_path))
    limits = profile.get("limits")
    if not isinstance(limits, dict) or {
        "operatorMaximumSessionRequests": limits.get("operatorMaximumSessionRequests"),
        "sessionRequestReserve": limits.get("sessionRequestReserve"),
        "sessionRequestsPerProbeInvocation": limits.get("sessionRequestsPerProbeInvocation"),
    } != {
        "operatorMaximumSessionRequests": 512,
        "sessionRequestReserve": 4,
        "sessionRequestsPerProbeInvocation": 2,
    }:
        fail("PLAN_SESSION_BUDGET_INVALID", "profile limits")
    admitted = profile.get("admittedConsole")
''',
)
replace_exact(
    verifier_path,
    '''    for marker in ("BEFORE_PLAN_EXECUTION", "BEFORE_CAPTURE_EXPORT", "validateBundle", "resolveStepArgs", "PLAN_NOT_DETERMINISTIC", "RESULT_REFERENCE_UNRESOLVED"):
        if marker not in plan_source:
            fail("PLAN_CONTROL_MISSING", marker)
    panel_source = text["browser_audition_operation_plan_panel.js"]
''',
    '''    for marker in (
        "BEFORE_PLAN_EXECUTION",
        "BEFORE_CAPTURE_EXPORT",
        "validateBundle",
        "resolveStepArgs",
        "PLAN_NOT_DETERMINISTIC",
        "RESULT_REFERENCE_UNRESOLVED",
        "SESSION_REQUESTS_PER_PROBE_INVOCATION",
        "SESSION_REQUEST_RESERVE",
        "requiredSessionRequests",
    ):
        if marker not in plan_source:
            fail("PLAN_CONTROL_MISSING", marker)
    javascript_budget = "probeInvocationCount * SESSION_REQUESTS_PER_PROBE_INVOCATION + SESSION_REQUEST_RESERVE"
    if plan_source.count(javascript_budget) != 1:
        fail("PLAN_SESSION_BUDGET_INVALID", "JavaScript compiler")
    python_plan_source = regular(repo / "mating_surface/anchor_node/axm_head_browser_audition_operation_plan_01.py").decode("utf-8")
    python_budget = "probe_invocation_count * SESSION_REQUESTS_PER_PROBE_INVOCATION + SESSION_REQUEST_RESERVE"
    if python_plan_source.count(python_budget) != 1:
        fail("PLAN_SESSION_BUDGET_INVALID", "Python compiler")
    panel_source = text["browser_audition_operation_plan_panel.js"]
''',
)
replace_exact(
    verifier_path,
    '"probe-refusal-state-stop", "post-invocation-inspection-stop", "failed-open-session-release", "exact-download-byte-binding"',
    '"probe-refusal-state-stop", "post-invocation-inspection-stop", "post-invocation-session-budget", "failed-open-session-release", "exact-download-byte-binding"',
)

tests_path = "mating_surface/anchor_node/conformance/test_axm_head_browser_audition_operation_plan_01.py"
replace_exact(
    tests_path,
    '''def run_panel_harness(body: str) -> dict:
''',
    '''def bindings_with_probe_invocations(probe_invocation_count: int) -> dict:
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
''',
)
replace_exact(
    tests_path,
    '''

def add_fixture_witnesses() -> None:
''',
    '''

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
''',
)

documentation_path = "mating_surface/anchor_node/AXM-HEAD-BROWSER-AUDITION-OPERATION-PLAN-01.md"
replace_exact(
    documentation_path,
    '''Because the admitted worker returns an invocation inspection captured before the invoked method runs, the panel performs a separate fresh `status` inspection after every probe invocation and before accepting a result, saving an alias, downloading a capture, logging completion, or advancing the cursor.
''',
    '''Because the admitted worker returns an invocation inspection captured before the invoked method runs, the panel performs a separate fresh `status` inspection after every probe invocation and before accepting a result, saving an alias, downloading a capture, logging completion, or advancing the cursor. The compiler therefore budgets two counted worker-session requests for every probe invocation, one invocation and one post-call status inspection, plus the fixed four-request operational reserve carried by the plan contract. It refuses any plan for which `2 * probeInvocationCount + 4` exceeds the admitted 512-request ceiling. Under the current ceiling, 254 probe invocations are admissible and 255 are refused before a document session can open.
''',
)

workflow_path = ".github/workflows/axm-head-browser-audition-operation-plan-01.yml"
replace_exact(workflow_path, '  WITNESS_DENOMINATOR: "78"\n', '  WITNESS_DENOMINATOR: "83"\n')

print("applied exact post-invocation session-budget repair")
