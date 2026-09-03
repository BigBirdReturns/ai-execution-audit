from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path
from typing import Any

PROFILE_ID = "axm-head/browser-audition-operation-plan/0.1"
PROFILE_SCHEMA = "axm-head/browser-audition-operation-plan-profile@1"
BUILD_SCHEMA = "axm-head/browser-audition-operation-plan-build@1"
VERDICT_SCHEMA = "axm-head/browser-audition-operation-plan-verdict@1"
ADMITTED_COMMIT = "d083ae55a20c730c56b69863c172b43d2a6f7651"
ADMITTED_TREE = "e7631a37778595c5367237a4fe52afec78120149"
ADMITTED_SOURCE = "axmoperatorconsolesource_d213e280c45cf2c81d84edf8d7af4ea077c77632472117d8f6708277ce4fe7a3"
ADMITTED_EXTENSION = "axmoperatorconsoleextension_63b6140baf423457b83af8da3c1dc4f3493c43933b4e6d712f53bfe6df363d01"
EXPECTED_EXTENSION = {
    "manifest.json",
    "browser_distributed_inference_probe.js",
    "browser_physical_audition_operator_contract.js",
    "browser_physical_audition_operator_service_worker.js",
    "browser_audition_operation_plan_contract.js",
    "browser_audition_operation_plan_panel.html",
    "browser_audition_operation_plan_panel.js",
    "browser_audition_operation_plan_panel.css",
    "build-manifest.json",
}


class VerifyError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def fail(code: str, message: str) -> None:
    raise VerifyError(code, message)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def pretty(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def identity(prefix: str, value: Any) -> str:
    return f"{prefix}_{hashlib.sha256(canonical(value)).hexdigest()}"


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail("JSON_INVALID", f"{path}: {exc}")
    if not isinstance(value, dict):
        fail("OBJECT_REQUIRED", str(path))
    return value


def regular(path: Path) -> bytes:
    try:
        info = path.lstat()
    except OSError as exc:
        fail("MEMBER_UNAVAILABLE", f"{path}: {exc}")
    attrs = getattr(info, "st_file_attributes", 0)
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
        fail("MEMBER_NOT_REGULAR", str(path))
    return path.read_bytes()


def inspect_root(root: Path) -> Path:
    absolute = Path(os.path.abspath(root))
    current = Path(absolute.parts[0])
    for part in absolute.parts[1:]:
        current /= part
        if not current.exists() and not current.is_symlink():
            continue
        info = current.lstat()
        attrs = getattr(info, "st_file_attributes", 0)
        if stat.S_ISLNK(info.st_mode) or attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
            fail("LINKED_PATH_REFUSED", str(current))
    if not absolute.is_dir():
        fail("DIRECTORY_REQUIRED", str(absolute))
    return absolute.resolve(strict=True)


def expected_manifest() -> dict[str, Any]:
    return {
        "action": {"default_title": "Open AXM audition operation plan"},
        "background": {"service_worker": "browser_physical_audition_operator_service_worker.js"},
        "content_scripts": [{"all_frames": False, "js": ["browser_distributed_inference_probe.js"], "matches": ["<all_urls>"], "run_at": "document_start", "world": "MAIN"}],
        "content_security_policy": {"extension_pages": "script-src 'self'; object-src 'none'"},
        "manifest_version": 3,
        "minimum_chrome_version": "116",
        "name": "AXM Browser Audition Operation Plan",
        "permissions": ["activeTab", "scripting", "sidePanel"],
        "side_panel": {"default_path": "browser_audition_operation_plan_panel.html"},
        "version": "0.1.0",
    }


def verify(profile_path: Path, repository_root: Path, extension_root: Path) -> dict[str, Any]:
    repo = inspect_root(repository_root)
    extension = inspect_root(extension_root)
    profile = load(profile_path)
    if profile.get("schema") != PROFILE_SCHEMA or profile.get("profileId") != PROFILE_ID:
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
    if admitted != {"commit": ADMITTED_COMMIT, "tree": ADMITTED_TREE, "profileId": "axm-head/browser-physical-audition-operator-console/0.1", "sourceBindingId": ADMITTED_SOURCE, "extensionId": ADMITTED_EXTENSION}:
        fail("ADMITTED_CONSOLE_BINDING_INVALID", str(profile_path))

    names = {path.name for path in extension.iterdir()}
    if names != EXPECTED_EXTENSION or any(path.is_dir() for path in extension.iterdir()):
        fail("EXTENSION_MEMBER_DENOMINATOR_INVALID", f"missing={sorted(EXPECTED_EXTENSION-names)} extra={sorted(names-EXPECTED_EXTENSION)}")
    if load(extension / "manifest.json") != expected_manifest() or profile.get("manifestContract") != expected_manifest():
        fail("MANIFEST_INVALID", str(extension))

    dependencies = []
    dep_by_path = {row["path"]: row for row in profile["dependencies"]}
    for relative, expected in dep_by_path.items():
        data = regular(repo / relative)
        observed = {"path": relative, "bytes": len(data), "sha256": digest(data), "gitBlobSha": expected["gitBlobSha"]}
        if observed != expected:
            fail("DEPENDENCY_BYTES_INVALID", relative)
        dependencies.append(observed)
    for relative in profile["extensionDependencyMembers"]:
        if regular(extension / Path(relative).name) != regular(repo / relative):
            fail("DEPENDENCY_COPY_INVALID", relative)
    for relative in profile["extensionSourceMembers"]:
        if regular(extension / Path(relative).name) != regular(repo / relative):
            fail("SOURCE_COPY_INVALID", relative)

    source_rows = []
    for relative in profile["sourceMembers"]:
        data = regular(repo / relative)
        source_rows.append({"path": relative, "bytes": len(data), "sha256": digest(data)})
    source_id = identity("axmoperationplansource", {"profileId": PROFILE_ID, "members": source_rows})
    payload_rows = []
    for name in profile["extensionPayloadMembers"]:
        data = regular(extension / name)
        payload_rows.append({"path": name, "bytes": len(data), "sha256": digest(data)})
    extension_id = identity("axmoperationplanextension", {"profileId": PROFILE_ID, "sourceBindingId": source_id, "members": payload_rows})

    build = load(extension / "build-manifest.json")
    required = {"schema", "status", "profileId", "protocol", "operatorProtocol", "interface", "admittedConsole", "sourceBindingId", "extensionId", "memberCount", "members", "dependencies", "claimBoundary"}
    if set(build) != required or build["schema"] != BUILD_SCHEMA or build["status"] != "PASS":
        fail("BUILD_MANIFEST_INVALID", str(extension))
    if build["admittedConsole"] != admitted or build["sourceBindingId"] != source_id or build["extensionId"] != extension_id:
        fail("BUILD_BINDING_INVALID", str(extension))
    if build["members"] != payload_rows or build["memberCount"] != len(payload_rows) or build["dependencies"] != dependencies:
        fail("BUILD_DENOMINATOR_INVALID", str(extension))

    source_names = [
        "browser_physical_audition_operator_contract.js",
        "browser_physical_audition_operator_service_worker.js",
        "browser_audition_operation_plan_contract.js",
        "browser_audition_operation_plan_panel.html",
        "browser_audition_operation_plan_panel.js",
    ]
    text = {name: regular(extension / name).decode("utf-8") for name in source_names}
    lowered = "\n".join(text.values()).lower()
    for token in ("swarm" + "llm", "neha" + "nth"):
        if token in lowered:
            fail("SUPPLIER_IDENTITY_ESCAPED_EXTENSION", token)
    for token in ("xmlhttprequest", "new websocket", "indexeddb", "localstorage", "sessionstorage", "chrome.storage", "eval(", "new function("):
        if token in lowered:
            fail("EXTERNAL_SURFACE_FORBIDDEN", token)
    if re.search(r"\bfetch\s*\(", lowered):
        fail("EXTERNAL_SURFACE_FORBIDDEN", "fetch")
    panel = text["browser_audition_operation_plan_panel.html"]
    order = [panel.find("browser_physical_audition_operator_contract.js"), panel.find("browser_audition_operation_plan_contract.js"), panel.find("browser_audition_operation_plan_panel.js")]
    if min(order) < 0 or order != sorted(order):
        fail("PANEL_SCRIPT_ORDER_INVALID", str(order))
    plan_source = text["browser_audition_operation_plan_contract.js"]
    for marker in (
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
    for marker in (
        "HALTED_PARTIAL_CAPTURE",
        "Acknowledge",
        "discardSessionState",
        "Discard this page ledger",
        'captureUse === "preflight"',
        "PROBE_LEDGER_ALREADY_MARKED",
        "PROBE_INSTALLATION_LATE",
        "MUTATING_METHODS.has(current.method)",
        "probeMutationPossible",
        "settleSessionLoss",
        "requireHealthyInspection",
        "requirePostInvocationInspection",
        "releaseFailedOpenSession",
        "disconnectCurrentPort",
        "PROBE_REFUSAL_STATE_ABSENT",
        "PROBE_CAPTURE_REFUSED",
        "serializeCaptureForDownload",
        "new Blob([serialized]",
    ):
        if marker not in panel_source:
            fail("PANEL_CONTROL_MISSING", marker)
    if panel_source.count('requireHealthyInspection(response.inspection)') != 5:
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
    if "JSON.stringify(capture, null, 2)" in panel_source:
        fail("CAPTURE_SERIALIZATION_DIVERGENCE", "pretty capture serialization")

    claim = profile["claimBoundary"]
    if build["claimBoundary"] != claim:
        fail("CLAIM_BOUNDARY_INVALID", str(extension))
    return {
        "schema": VERDICT_SCHEMA,
        "status": "PASS",
        "profileId": PROFILE_ID,
        "sourceBindingId": source_id,
        "extensionId": extension_id,
        "sourceMemberCount": len(source_rows),
        "extensionMemberCount": len(EXPECTED_EXTENSION),
        "checks": ["exact-admitted-console-binding", "independent-source-reconstruction", "payload-source-byte-binding", "deterministic-plan-controls", "pristine-ledger-preflight", "mutation-uncertainty-stop", "probe-refusal-state-stop", "post-invocation-inspection-stop", "post-invocation-session-budget", "failed-open-session-release", "exact-download-byte-binding", "closed-local-extension-surface", "supplier-neutral-executable-surface"],
        "bootstrapAuthenticated": False,
        "storedVerifierMemberBound": False,
        **claim,
    }


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        sys.stdout.buffer.write(pretty({"schema": VERDICT_SCHEMA, "status": "REFUSED", "code": "ARGUMENT_DENOMINATOR_INVALID"}))
        return 2
    try:
        result = verify(Path(argv[0]), Path(argv[1]), Path(argv[2]))
        sys.stdout.buffer.write(pretty(result))
        return 0
    except VerifyError as exc:
        sys.stdout.buffer.write(pretty({"schema": VERDICT_SCHEMA, "status": "REFUSED", "code": exc.code, "message": str(exc), "bootstrapAuthenticated": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
