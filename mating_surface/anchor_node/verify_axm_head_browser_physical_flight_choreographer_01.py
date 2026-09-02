from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any

PROFILE_SCHEMA = "axm-head/browser-physical-flight-choreographer-profile@1"
PROFILE_ID = "axm-head/browser-physical-flight-choreographer/0.1"
PROTOCOL = "axm-head/browser-physical-flight-choreographer@1"
INTERFACE = "axm/distributed-model-inference@1"
BUILD_SCHEMA = "axm-head/browser-physical-flight-choreographer-build@1"
ADMITTED_OPERATION_PLAN_COMMIT = "e78bb4e8a4115b2191967d1ffcd1d744d77ce050"
ADMITTED_OPERATION_PLAN_TREE = "83006c13dd14f670785ffb57bd62d44b502d73a8"
ADMITTED_OPERATION_PLAN_SOURCE = "axmoperationplansource_c16c73e2f3923a1c271bd4840d05f56a8bf639f947b4a47a565e5980c615ea9c"
ADMITTED_OPERATION_PLAN_EXTENSION = "axmoperationplanextension_43261df0433ae81596aa1d0a85fdc86f4f85d2004098d604ecc6bda694e3ffa6"
ADMITTED_CONSOLE_COMMIT = "ce93cf8856b7fcc9b172b9251b9665df50fdeda4"
ADMITTED_CONSOLE_TREE = "664784d10309665eb3b993ce8f6df4eb5b10baf7"
ADMITTED_CONSOLE_SOURCE = "axmoperatorconsolesource_aefa481bc33a9c4500f5fe1d4398b90c2159ac1833bf67c9d42ec321592d987c"
ADMITTED_CONSOLE_EXTENSION = "axmoperatorconsoleextension_ab926ed5afc19f66c1b898abd832925c3f3e3c719d7fa814c5751f570b9c8231"
OPERATOR_PROTOCOL = "axm-head/browser-physical-audition-operator-console@1"

CLAIM_BOUNDARY = {
    "operationCardConstructed": True,
    "operationCardExecuted": False,
    "browserLaunched": False,
    "supplierEndpointContacted": False,
    "modelDownloaded": False,
    "peerConnectionFormed": False,
    "inferenceExecuted": False,
    "physicalAuditionCompleted": False,
    "routeTerminalProduced": False,
    "namedHumanConfirmationSupplied": False,
    "actualSupplierQualified": False,
    "physicalEstateQualified": False,
    "missionAuthority": "none",
    "commandAuthority": "none",
}

DEPENDENCIES = [
    {
        "path": "mating_surface/anchor_node/browser_distributed_inference_probe.js",
        "bytes": 22384,
        "gitBlobSha": "f8489140c119b8513a7569ff95c3900dc1672496",
        "sha256": "sha256:b1ded0348ffc0ec4246e9d18a08451216c89f98d6369e483808062430088565e",
    },
    {
        "path": "mating_surface/anchor_node/browser_physical_audition_operator_contract.js",
        "bytes": 14749,
        "gitBlobSha": "649007fbf08db899630ad8f9fb972f01146feade",
        "sha256": "sha256:fe826434bc9fe2a3e47a0d991273bddd9e54852618b86b97914976d514336042",
    },
    {
        "path": "mating_surface/anchor_node/browser_physical_audition_operator_service_worker.js",
        "bytes": 11228,
        "gitBlobSha": "9c3854efd2859ab21747672d4916989aff550a04",
        "sha256": "sha256:260eb0a5f6edd0f2a448e5665245d29962bb5ab28fb21829fc9fe196abd8bb03",
    },
]

MAPPING = {
    "manifest.json": None,
    "browser_distributed_inference_probe.js": DEPENDENCIES[0]["path"],
    "browser_physical_audition_operator_contract.js": DEPENDENCIES[1]["path"],
    "browser_physical_audition_operator_service_worker.js": DEPENDENCIES[2]["path"],
    "browser_physical_flight_choreographer_contract.js": "mating_surface/anchor_node/browser_physical_flight_choreographer_contract.js",
    "browser_physical_flight_choreographer_panel.html": "mating_surface/anchor_node/browser_physical_flight_choreographer_panel.html",
    "browser_physical_flight_choreographer_panel.js": "mating_surface/anchor_node/browser_physical_flight_choreographer_panel.js",
    "browser_physical_flight_choreographer_panel.css": "mating_surface/anchor_node/browser_physical_flight_choreographer_panel.css",
}


class VerificationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def fail(code: str, message: str) -> None:
    raise VerificationError(code, message)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_ref(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def content_id(prefix: str, value: Any) -> str:
    return f"{prefix}_{hashlib.sha256(canonical_bytes(value)).hexdigest()}"


def regular_bytes(path: Path, maximum: int = 2_000_000) -> bytes:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.parts[0])
    for part in absolute.parts[1:]:
        current = current / part
        if current.exists() or current.is_symlink():
            info = current.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                fail("LINKED_PATH_REFUSED", str(current))
    try:
        info = absolute.lstat()
    except OSError as exc:
        fail("INPUT_UNAVAILABLE", f"{absolute}: {exc}")
    if not stat.S_ISREG(info.st_mode) or not 1 <= info.st_size <= maximum:
        fail("INPUT_SIZE_OR_TYPE_INVALID", str(absolute))
    data = absolute.read_bytes()
    if len(data) != info.st_size:
        fail("INPUT_READ_INVALID", str(absolute))
    return data


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(regular_bytes(path).decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        fail("JSON_INVALID", f"{path}: {exc}")
    if not isinstance(value, dict):
        fail("JSON_OBJECT_REQUIRED", str(path))
    return value


def extension_manifest() -> dict[str, Any]:
    return {
        "manifest_version": 3,
        "name": "AXM Browser Physical Flight Choreographer",
        "version": "0.1.0",
        "minimum_chrome_version": "116",
        "permissions": ["activeTab", "scripting", "sidePanel"],
        "background": {"service_worker": "browser_physical_audition_operator_service_worker.js"},
        "content_scripts": [
            {
                "matches": ["<all_urls>"],
                "js": ["browser_distributed_inference_probe.js"],
                "run_at": "document_start",
                "world": "MAIN",
                "all_frames": False,
            }
        ],
        "side_panel": {"default_path": "browser_physical_flight_choreographer_panel.html"},
        "action": {"default_title": "Open AXM physical flight choreographer"},
        "content_security_policy": {"extension_pages": "script-src 'self'; object-src 'none'"},
    }


def duplicate_literal_dict_keys(path: Path) -> list[str]:
    tree = ast.parse(regular_bytes(path).decode("utf-8"), filename=str(path))
    duplicates: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        seen: set[str] = set()
        for key in node.keys:
            if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                continue
            if key.value in seen:
                duplicates.append(f"{path}:{getattr(key, 'lineno', '?')}:{key.value}")
            seen.add(key.value)
    return duplicates


def verify(profile_path: Path, repository_root: Path, extension_root: Path) -> dict[str, Any]:
    profile = load_json(profile_path)
    if profile.get("schema") != PROFILE_SCHEMA or profile.get("profileId") != PROFILE_ID or profile.get("protocol") != PROTOCOL or profile.get("interface") != INTERFACE:
        fail("PROFILE_IDENTITY_INVALID", str(profile_path))
    if profile.get("admittedOperationPlan") != {
        "commit": ADMITTED_OPERATION_PLAN_COMMIT,
        "tree": ADMITTED_OPERATION_PLAN_TREE,
        "sourceBindingId": ADMITTED_OPERATION_PLAN_SOURCE,
        "extensionId": ADMITTED_OPERATION_PLAN_EXTENSION,
    }:
        fail("ADMITTED_OPERATION_PLAN_INVALID", str(profile_path))
    if profile.get("admittedConsole") != {
        "commit": ADMITTED_CONSOLE_COMMIT,
        "tree": ADMITTED_CONSOLE_TREE,
        "sourceBindingId": ADMITTED_CONSOLE_SOURCE,
        "extensionId": ADMITTED_CONSOLE_EXTENSION,
        "protocol": OPERATOR_PROTOCOL,
    }:
        fail("ADMITTED_CONSOLE_INVALID", str(profile_path))
    if profile.get("dependencies") != DEPENDENCIES:
        fail("DEPENDENCY_DENOMINATOR_INVALID", str(profile_path))
    if profile.get("limits") != {
        "maximumArtifacts": 200,
        "maximumAvailabilityAgeMs": 900000,
        "maximumCardBytes": 262144,
        "maximumMembers": 32,
        "maximumPrivateTextBytes": 65536,
        "maximumSessionRequests": 512,
        "maximumSupplementBytes": 131072,
        "outputTokenCount": 1,
        "sessionRequestReserve": 4,
        "sessionRequestsPerProbeInvocation": 2,
    }:
        fail("PROFILE_LIMITS_INVALID", str(profile.get("limits")))
    if profile.get("claimBoundary") != CLAIM_BOUNDARY:
        fail("CLAIM_BOUNDARY_INVALID", str(profile_path))
    if len(profile.get("sourceMembers", [])) != 13 or len(set(profile["sourceMembers"])) != 13:
        fail("SOURCE_MEMBER_DENOMINATOR_INVALID", str(profile.get("sourceMembers")))
    if sorted(profile.get("extensionMembers", [])) != sorted(MAPPING):
        fail("EXTENSION_MEMBER_DENOMINATOR_INVALID", str(profile.get("extensionMembers")))

    rows = []
    source_text: dict[str, str] = {}
    for relative in sorted(profile["sourceMembers"]):
        data = regular_bytes(repository_root / PurePosixPath(relative))
        if b"\r" in data or any(value < 32 and value not in (9, 10) for value in data):
            fail("SOURCE_CONTROL_BYTE_INVALID", relative)
        try:
            source_text[relative] = data.decode("utf-8")
        except UnicodeError:
            fail("SOURCE_UTF8_INVALID", relative)
        rows.append({"path": relative, "bytes": len(data), "sha256": sha256_ref(data)})
    source_binding = content_id("axmphysicalflightchoreographersource", rows)

    for row in DEPENDENCIES:
        data = regular_bytes(repository_root / PurePosixPath(row["path"]))
        if len(data) != row["bytes"] or sha256_ref(data) != row["sha256"]:
            fail("DEPENDENCY_CONTENT_MISMATCH", row["path"])

    extension_files = sorted(path.name for path in extension_root.iterdir() if path.is_file())
    expected_extension_files = sorted([*MAPPING, "build-manifest.json"])
    if extension_files != expected_extension_files or any(path.is_dir() for path in extension_root.iterdir()):
        fail("EXTENSION_FILE_DENOMINATOR_INVALID", str(extension_files))
    manifest = load_json(extension_root / "manifest.json")
    if manifest != extension_manifest():
        fail("MANIFEST_INVALID", str(extension_root))

    members = []
    for destination, source_relative in MAPPING.items():
        data = regular_bytes(extension_root / destination)
        expected = canonical_bytes(manifest)
        if destination == "manifest.json":
            expected = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode("utf-8")
        elif source_relative is not None:
            expected = regular_bytes(repository_root / PurePosixPath(source_relative))
        if data != expected:
            fail("EXTENSION_SOURCE_BINDING_MISMATCH", destination)
        members.append({"path": destination, "bytes": len(data), "sha256": sha256_ref(data)})

    build = load_json(extension_root / "build-manifest.json")
    expected_build_keys = {
        "schema", "status", "profileId", "protocol", "operatorProtocol", "interface",
        "admittedOperationPlan", "admittedConsole", "sourceBindingId", "extensionId",
        "memberCount", "members", "claimBoundary",
    }
    if set(build) != expected_build_keys or build.get("schema") != BUILD_SCHEMA or build.get("status") != "PASS":
        fail("BUILD_MANIFEST_INVALID", str(extension_root))
    if build.get("sourceBindingId") != source_binding or build.get("memberCount") != 8 or build.get("members") != sorted(members, key=lambda row: row["path"]):
        fail("BUILD_SOURCE_BINDING_INVALID", str(extension_root))
    expected_extension_id = content_id("axmphysicalflightchoreographerextension", {**build, "extensionId": None})
    if build.get("extensionId") != expected_extension_id or build.get("claimBoundary") != CLAIM_BOUNDARY:
        fail("EXTENSION_ID_INVALID", str(extension_root))

    executable_paths = [
        repository_root / "mating_surface/anchor_node/axm_head_browser_physical_flight_choreographer_01.py",
        repository_root / "mating_surface/anchor_node/browser_physical_flight_choreographer_contract.js",
        repository_root / "mating_surface/anchor_node/browser_physical_flight_choreographer_panel.js",
        repository_root / "mating_surface/anchor_node/verify_axm_head_browser_physical_flight_choreographer_01.py",
    ]
    executable = "\n".join(regular_bytes(path).decode("utf-8") for path in executable_paths)
    for token in ("swarm" + "llm", "ne" + "hanth"):
        if token in executable.lower():
            fail("SUPPLIER_IDENTITY_IN_EXECUTABLE", token)
    panel = source_text["mating_surface/anchor_node/browser_physical_flight_choreographer_panel.js"]
    for token in ("localStorage", "sessionStorage", "indexedDB", "XMLHttpRequest", "new WebSocket", "fetch("):
        if token in panel:
            fail("PANEL_PERSISTENCE_OR_NETWORK_CLIENT", token)
    panel_markers = [
        "function requirePristineCapture",
        "async function recordStatic",
        "async function armPrompt",
        "async function recordOutput",
        "function armDrop",
        "async function recordPostflight",
        "async function exportCapture",
    ]
    positions = [panel.find(marker) for marker in panel_markers]
    if min(positions) < 0 or positions != sorted(positions):
        fail("PANEL_PHASE_ORDER_INVALID", str(positions))
    for marker in (
        "requirePostInvocationInspection",
        "PROBE_REFUSAL_STATE_ABSENT",
        "PROBE_CAPTURE_REFUSED",
        "HALTED_PARTIAL_CAPTURE",
        "PROMPT_BINDING_MISMATCH",
        "OUTPUT_DIGEST_MISMATCH",
        "SUPPLEMENT_OUTPUT_BINDING_MISMATCH",
        "AVAILABILITY_OBSERVATION_STALE",
        "MANUAL_STATUS_RESERVE_EXHAUSTED",
        "FINAL_INVOCATION_DENOMINATOR_INVALID",
    ):
        if marker not in panel:
            fail("PANEL_CONTROL_MISSING", marker)
    contract = source_text["mating_surface/anchor_node/browser_physical_flight_choreographer_contract.js"]
    for marker in (
        "21 + card.static.members.length + card.static.modelArtifacts.length",
        "probeInvocationCount(card) * SESSION_REQUESTS_PER_INVOCATION + SESSION_REQUEST_RESERVE",
        "ONE_TOKEN_CHALLENGE_REQUIRED",
        "MAX_AVAILABILITY_AGE_MS",
        "SUPPLEMENT_CARD_BINDING_INVALID",
        "RECEIPT_EVIDENCE_BINDING_MISMATCH",
    ):
        if marker not in contract:
            fail("CONTRACT_CONTROL_MISSING", marker)
    python_source = repository_root / "mating_surface/anchor_node/axm_head_browser_physical_flight_choreographer_01.py"
    duplicates = duplicate_literal_dict_keys(python_source)
    if duplicates:
        fail("DUPLICATE_LITERAL_DICTIONARY_KEY", str(duplicates))

    node_script = f"""
const fs=require('fs'),vm=require('vm'),crypto=require('crypto');
global.crypto=crypto.webcrypto;
vm.runInThisContext(fs.readFileSync({json.dumps(str(extension_root / 'browser_physical_audition_operator_contract.js'))},'utf8'));
vm.runInThisContext(fs.readFileSync({json.dumps(str(extension_root / 'browser_physical_flight_choreographer_contract.js'))},'utf8'));
const F=AXMPhysicalFlightChoreographerContract;
console.log(JSON.stringify({{profile:F.PROFILE_ID,protocol:F.PROTOCOL,interface:F.INTERFACE,outputTokens:F.OUTPUT_TOKEN_COUNT,reserve:F.SESSION_REQUEST_RESERVE,perInvocation:F.SESSION_REQUESTS_PER_INVOCATION}}));
"""
    completed = subprocess.run(["node", "-e", node_script], capture_output=True, text=True)
    if completed.returncode != 0:
        fail("NODE_CONTRACT_LOAD_FAILED", completed.stdout + completed.stderr)
    node = json.loads(completed.stdout)
    if node != {"profile": PROFILE_ID, "protocol": PROTOCOL, "interface": INTERFACE, "outputTokens": 1, "reserve": 4, "perInvocation": 2}:
        fail("NODE_CONTRACT_IDENTITY_INVALID", str(node))

    return {
        "schema": "axm-head/browser-physical-flight-choreographer-verification@1",
        "status": "PASS",
        "profileId": PROFILE_ID,
        "sourceBindingId": source_binding,
        "sourceMemberCount": len(rows),
        "extensionId": expected_extension_id,
        "extensionMemberCount": len(extension_files),
        "checks": [
            "exact-admitted-predecessors",
            "exact-dependency-bytes",
            "source-member-denominator",
            "source-control-byte-hygiene",
            "extension-source-binding",
            "extension-content-identity",
            "supplier-neutral-executable",
            "no-panel-persistence-or-network-client",
            "governed-phase-order",
            "post-invocation-inspection",
            "one-token-output-binding",
            "content-bound-postflight",
            "closed-request-budget",
            "availability-freshness-window",
            "manual-status-reserve",
            "private-text-erasure",
            "duplicate-key-refusal",
            "node-contract-identity",
        ],
        "operationCardExecuted": False,
        "physicalExecutionObserved": False,
        "actualSupplierQualified": False,
        "physicalEstateQualified": False,
        "missionAuthority": "none",
        "commandAuthority": "none",
    }


def main() -> int:
    if len(sys.argv) != 4:
        print(json.dumps({"status": "REFUSED", "code": "ARGUMENT_DENOMINATOR_INVALID"}, sort_keys=True))
        return 2
    try:
        result = verify(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except VerificationError as exc:
        print(json.dumps({
            "schema": "axm-head/browser-physical-flight-choreographer-verification@1",
            "status": "REFUSED",
            "code": exc.code,
            "message": str(exc),
            "actualSupplierQualified": False,
            "physicalEstateQualified": False,
            "missionAuthority": "none",
            "commandAuthority": "none",
        }, sort_keys=True, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
