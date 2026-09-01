from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path
from typing import Any

PROFILE_ID = "axm-head/browser-physical-audition-operator-console/0.1"
PROFILE_SCHEMA = "axm-head/browser-physical-audition-operator-console-profile@1"
PROTOCOL = "axm-head/browser-physical-audition-operator-console@1"
INTERFACE = "axm/distributed-model-inference@1"
ADMITTED_PACKET_COMMIT = "ac60f1196635d73e614a09123772efccd4649bd0"
ADMITTED_PACKET_TREE = "b6a705c988f0997a63c8ff19dd3f1f67e1d146b6"
PROBE_SHA256 = "sha256:b1ded0348ffc0ec4246e9d18a08451216c89f98d6369e483808062430088565e"
EXPECTED_EXTENSION_MEMBERS = {
    "manifest.json",
    "browser_distributed_inference_probe.js",
    "browser_physical_audition_operator_contract.js",
    "browser_physical_audition_operator_service_worker.js",
    "browser_physical_audition_operator_panel.html",
    "browser_physical_audition_operator_panel.js",
    "browser_physical_audition_operator_panel.css",
    "build-manifest.json",
}
EXPECTED_METHODS = (
    "markAvailability",
    "markAdapterArtifact",
    "markFormation",
    "markMember",
    "markModelManifest",
    "markModelArtifact",
    "markPerformanceStart",
    "markToken",
    "markDrop",
    "markEquivalence",
    "markPrivacyDeclaration",
    "markObservationReceipt",
    "samplePeerStats",
    "exportCapture",
)


class VerificationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def fail(code: str, message: str) -> None:
    raise VerificationError(code, message)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def pretty_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def identity(prefix: str, value: Any) -> str:
    return f"{prefix}_{hashlib.sha256(canonical_bytes(value)).hexdigest()}"


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
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        fail("MEMBER_NOT_REGULAR", str(path))
    attributes = getattr(info, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if attributes & reparse:
        fail("MEMBER_NOT_REGULAR", str(path))
    return path.read_bytes()


def inspect_root(root: Path) -> Path:
    absolute = Path(os.path.abspath(root))
    current = Path(absolute.parts[0])
    for part in absolute.parts[1:]:
        current = current / part
        if not current.exists() and not current.is_symlink():
            continue
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode):
            fail("LINKED_PATH_REFUSED", str(current))
        attributes = getattr(info, "st_file_attributes", 0)
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if attributes & reparse:
            fail("LINKED_PATH_REFUSED", str(current))
    if not absolute.is_dir():
        fail("DIRECTORY_REQUIRED", str(absolute))
    return absolute.resolve(strict=True)


def expected_manifest() -> dict[str, Any]:
    return {
        "action": {"default_title": "Open AXM physical-audition console"},
        "background": {"service_worker": "browser_physical_audition_operator_service_worker.js"},
        "content_scripts": [
            {
                "all_frames": False,
                "js": ["browser_distributed_inference_probe.js"],
                "matches": ["<all_urls>"],
                "run_at": "document_start",
                "world": "MAIN",
            }
        ],
        "content_security_policy": {"extension_pages": "script-src 'self'; object-src 'none'"},
        "manifest_version": 3,
        "minimum_chrome_version": "116",
        "name": "AXM Browser Physical-Audition Operator Console",
        "permissions": ["activeTab", "scripting", "sidePanel"],
        "side_panel": {"default_path": "browser_physical_audition_operator_panel.html"},
        "version": "0.1.0",
    }


def static_source_checks(extension: Path) -> list[str]:
    checks = []
    console_names = [
        "browser_physical_audition_operator_contract.js",
        "browser_physical_audition_operator_service_worker.js",
        "browser_physical_audition_operator_panel.js",
        "browser_physical_audition_operator_panel.html",
    ]
    source = {name: regular(extension / name).decode("utf-8") for name in console_names}
    joined = "\n".join(source.values()).lower()
    for token in ("swarm" + "llm", "neha" + "nth"):
        if token in joined:
            fail("SUPPLIER_IDENTITY_ESCAPED_CONSOLE", token)
    checks.append("supplier-neutral-console-source")

    executable = "\n".join(value for name, value in source.items() if name.endswith((".js", ".html")))
    forbidden_network = (
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
        "import('http",
        'import("http',
    )
    lowered = executable.lower()
    for token in forbidden_network:
        if token in lowered:
            fail("CONSOLE_EXTERNAL_SURFACE_FORBIDDEN", token)
    if re.search(r"\bfetch\s*\(", lowered):
        fail("CONSOLE_EXTERNAL_SURFACE_FORBIDDEN", "fetch")
    checks.append("no-network-remote-code-or-persistent-storage")

    worker = source["browser_physical_audition_operator_service_worker.js"]
    required_worker = (
        'chrome.runtime.onConnect.addListener',
        'chrome.scripting.executeScript',
        'world: "MAIN"',
        'chrome.sidePanel',
        'port.onDisconnect.addListener',
    )
    for token in required_worker:
        if token not in worker:
            fail("SERVICE_WORKER_MECHANISM_MISSING", token)
    if "chrome.runtime.onMessage" in worker or "window.postMessage" in worker or "CustomEvent" in worker:
        fail("PAGE_SPOOFABLE_BRIDGE_FORBIDDEN", "message bridge")
    checks.append("extension-port-to-main-world-execution")

    contract = source["browser_physical_audition_operator_contract.js"]
    for method in EXPECTED_METHODS:
        if f'"{method}"' not in contract:
            fail("METHOD_DENOMINATOR_INVALID", method)
    checks.append("closed-method-denominator")

    panel = source["browser_physical_audition_operator_panel.html"]
    if re.search(r"\son[a-z]+\s*=", panel, re.I) or "<script>" in panel.lower():
        fail("INLINE_EXTENSION_CODE_FORBIDDEN", "panel")
    checks.append("extension-csp-compatible-panel")
    return checks


def reconstruct_source_binding(profile: dict[str, Any], repository_root: Path) -> tuple[str, list[dict[str, Any]]]:
    rows = []
    for relative in profile["sourceMembers"]:
        data = regular(repository_root / relative)
        rows.append({"path": relative, "bytes": len(data), "sha256": digest(data)})
    body = {"profileId": profile["profileId"], "members": rows}
    return identity("axmoperatorconsolesource", body), rows


def verify_extension(profile_path: Path, repository_root: Path, extension_root: Path) -> dict[str, Any]:
    repo = inspect_root(repository_root)
    extension = inspect_root(extension_root)
    profile_bytes = regular(profile_path)
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
    if profile.get("schema") != PROFILE_SCHEMA or profile.get("profileId") != PROFILE_ID:
        fail("PROFILE_IDENTITY_INVALID", str(profile_path))
    if profile.get("protocol") != PROTOCOL or profile.get("interface") != INTERFACE:
        fail("PROFILE_INTERFACE_INVALID", str(profile_path))
    if profile.get("admittedPacket") != {
        "commit": ADMITTED_PACKET_COMMIT,
        "tree": ADMITTED_PACKET_TREE,
        "profileId": "axm-head/browser-physical-audition-packet/0.1",
    }:
        fail("ADMITTED_PACKET_BINDING_INVALID", str(profile_path))
    if tuple(profile.get("methods", ())) != EXPECTED_METHODS:
        fail("METHOD_DENOMINATOR_INVALID", str(profile_path))
    observed_names = {path.name for path in extension.iterdir()}
    if observed_names != EXPECTED_EXTENSION_MEMBERS:
        fail(
            "EXTENSION_MEMBER_DENOMINATOR_INVALID",
            f"missing={sorted(EXPECTED_EXTENSION_MEMBERS-observed_names)} extra={sorted(observed_names-EXPECTED_EXTENSION_MEMBERS)}",
        )
    if any(path.is_dir() for path in extension.iterdir()):
        fail("EXTENSION_SUBDIRECTORY_FORBIDDEN", str(extension))

    manifest = load(extension / "manifest.json")
    if manifest != expected_manifest() or manifest != profile.get("manifestContract"):
        fail("MANIFEST_INVALID", str(extension / "manifest.json"))
    probe = regular(extension / "browser_distributed_inference_probe.js")
    if digest(probe) != PROBE_SHA256:
        fail("PROBE_BYTES_INVALID", digest(probe))

    build = load(extension / "build-manifest.json")
    required_build_keys = {
        "schema",
        "status",
        "profileId",
        "protocol",
        "interface",
        "admittedPacket",
        "sourceBindingId",
        "extensionId",
        "memberCount",
        "members",
        "dependencies",
        "claimBoundary",
    }
    if set(build) != required_build_keys:
        fail("BUILD_MANIFEST_KEYS_INVALID", str(extension))
    if build["schema"] != "axm-head/browser-physical-audition-operator-console-build@1" or build["status"] != "PASS":
        fail("BUILD_MANIFEST_IDENTITY_INVALID", str(extension))
    if build["profileId"] != PROFILE_ID or build["protocol"] != PROTOCOL or build["interface"] != INTERFACE:
        fail("BUILD_MANIFEST_BINDING_INVALID", str(extension))
    if build["admittedPacket"] != profile["admittedPacket"] or build["claimBoundary"] != profile["claimBoundary"]:
        fail("BUILD_MANIFEST_BINDING_INVALID", str(extension))

    source_binding, source_rows = reconstruct_source_binding(profile, repo)
    if build["sourceBindingId"] != source_binding:
        fail("SOURCE_BINDING_INVALID", str(extension))
    expected_payload = {
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
    expected_id = identity(
        "axmoperatorconsoleextension",
        {"profileId": PROFILE_ID, "sourceBindingId": source_binding, "members": payload_rows},
    )
    if build["extensionId"] != expected_id:
        fail("EXTENSION_ID_INVALID", str(extension))

    dependency_rows = []
    for expected in profile["dependencies"]:
        data = regular(repo / expected["path"])
        row = {"path": expected["path"], "bytes": len(data), "sha256": digest(data), "gitBlobSha": expected["gitBlobSha"]}
        if row["bytes"] != expected["bytes"] or row["sha256"] != expected["sha256"]:
            fail("DEPENDENCY_BYTES_INVALID", expected["path"])
        dependency_rows.append(row)
    if build["dependencies"] != dependency_rows:
        fail("DEPENDENCY_BINDING_INVALID", str(extension))

    checks = [
        "canonical-profile-byte-binding",
        "payload-source-byte-binding",
        *static_source_checks(extension),
        "stored-verifier-byte-binding",
    ]
    return {
        "schema": "axm-head/browser-physical-audition-operator-console-verdict@1",
        "status": "PASS",
        "profileId": PROFILE_ID,
        "sourceBindingId": source_binding,
        "sourceMemberCount": len(source_rows),
        "extensionId": expected_id,
        "extensionMemberCount": len(EXPECTED_EXTENSION_MEMBERS),
        "checks": checks,
        "bootstrapAuthenticated": False,
        "storedVerifierMemberBound": False,
        "operatorConsoleSourceConstructed": True,
        "operatorConsoleSourceAdmitted": False,
        "browserLaunched": False,
        "supplierEndpointContacted": False,
        "modelDownloaded": False,
        "peerConnectionFormed": False,
        "inferenceExecuted": False,
        "physicalAuditionCompleted": False,
        "namedHumanConfirmationSupplied": False,
        "actualSupplierQualified": False,
        "physicalEstateQualified": False,
        "missionAuthority": "none",
        "commandAuthority": "none",
    }


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        sys.stdout.buffer.write(pretty_bytes({"status": "REFUSED", "code": "ARGUMENT_DENOMINATOR_INVALID"}))
        return 2
    try:
        verdict = verify_extension(Path(argv[0]), Path(argv[1]), Path(argv[2]))
        sys.stdout.buffer.write(pretty_bytes(verdict))
        return 0
    except VerificationError as exc:
        sys.stdout.buffer.write(pretty_bytes({"schema": "axm-head/browser-physical-audition-operator-console-verdict@1", "status": "REFUSED", "code": exc.code, "message": str(exc), "bootstrapAuthenticated": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
