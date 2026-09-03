from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import stat
import sys
from pathlib import Path
from typing import Any, Iterable

PROFILE_SCHEMA = "axm-head/browser-physical-audition-operator-console-profile@1"
PROFILE_ID = "axm-head/browser-physical-audition-operator-console/0.1"
ISSUE_REF = "BigBirdReturns/ai-execution-audit#103"
PROTOCOL = "axm-head/browser-physical-audition-operator-console@1"
INTERFACE = "axm/distributed-model-inference@1"
ADMITTED_PACKET_COMMIT = "0df3795b47a58903adc86c68db2b1168de543ab7"
ADMITTED_PACKET_TREE = "d05b33f066ee1b9aea731a1027de4c87f61b074b"
ADMITTED_PACKET_SOURCE_BINDING_ID = "axmbrowserphysicalpacketsource_47826c4d84036ce65ce7e2e222086d0cce422f5a5448b7e54909963bda556107"
ADMITTED_PACKET_KIT_ID = "axmbrowserphysicalkit_3da8f2aa59666d990653e46036ea060f0fd56591e11eed15131789554d630aac"
PROBE_SHA256 = "sha256:b1ded0348ffc0ec4246e9d18a08451216c89f98d6369e483808062430088565e"
PROBE_BYTES = 22384
PROBE_BLOB = "f8489140c119b8513a7569ff95c3900dc1672496"
PACKET_PROFILE_SHA256 = "sha256:785ecb62e6093ff613298e503d7eb078250063d4ee2cfae3b92446e68c215e78"
PACKET_PROFILE_BYTES = 8275
PACKET_PROFILE_BLOB = "322414803ab0620d66d20e3ba0a9ed0ec8ac9697"
MAX_COMMAND_BYTES = 65536
MAX_CAPTURE_BYTES = 1048576
MAX_SESSION_REQUESTS = 512
SESSION_MAX_AGE_MS = 7200000

METHODS = (
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
RECEIPT_KINDS = (
    "current-availability-observation",
    "executable-adapter-artifact",
    "formation-capacity-receipt",
    "formation-topology-receipt",
    "member-drop-behavior-receipt",
    "model-output-equivalence-receipt",
    "performance-receipt",
    "network-exposure-observation",
    "privacy-declaration",
)
SOURCE_MEMBERS = (
    ".github/workflows/axm-head-browser-physical-audition-operator-console-01.yml",
    "mating_surface/anchor_node/AXM-HEAD-BROWSER-PHYSICAL-AUDITION-OPERATOR-CONSOLE-01.md",
    "mating_surface/anchor_node/axm-head-browser-physical-audition-operator-console-profile-01.json",
    "mating_surface/anchor_node/axm-head-browser-physical-audition-operator-console-01.ps1",
    "mating_surface/anchor_node/axm_head_browser_physical_audition_operator_console_01.py",
    "mating_surface/anchor_node/browser_physical_audition_operator_contract.js",
    "mating_surface/anchor_node/browser_physical_audition_operator_service_worker.js",
    "mating_surface/anchor_node/browser_physical_audition_operator_panel.html",
    "mating_surface/anchor_node/browser_physical_audition_operator_panel.js",
    "mating_surface/anchor_node/browser_physical_audition_operator_panel.css",
    "mating_surface/anchor_node/verify_axm_head_browser_physical_audition_operator_console_01.py",
    "mating_surface/anchor_node/verify_axm_head_browser_physical_audition_operator_console_01_bootstrap.py",
    "mating_surface/anchor_node/conformance/test_axm_head_browser_physical_audition_operator_console_01.py",
    "mating_surface/anchor_node/fixtures/axm-head-browser-physical-audition-operator-console-cases-01.json",
)
EXTENSION_SOURCE_MEMBERS = (
    "mating_surface/anchor_node/browser_physical_audition_operator_contract.js",
    "mating_surface/anchor_node/browser_physical_audition_operator_service_worker.js",
    "mating_surface/anchor_node/browser_physical_audition_operator_panel.html",
    "mating_surface/anchor_node/browser_physical_audition_operator_panel.js",
    "mating_surface/anchor_node/browser_physical_audition_operator_panel.css",
)
DEPENDENCIES = (
    {
        "path": "mating_surface/anchor_node/browser_distributed_inference_probe.js",
        "bytes": PROBE_BYTES,
        "sha256": PROBE_SHA256,
        "gitBlobSha": PROBE_BLOB,
    },
    {
        "path": "mating_surface/anchor_node/axm-head-browser-physical-audition-packet-profile-01.json",
        "bytes": PACKET_PROFILE_BYTES,
        "sha256": PACKET_PROFILE_SHA256,
        "gitBlobSha": PACKET_PROFILE_BLOB,
    },
)
EXTENSION_PAYLOAD_MEMBERS = (
    "manifest.json",
    "browser_distributed_inference_probe.js",
    "browser_physical_audition_operator_contract.js",
    "browser_physical_audition_operator_service_worker.js",
    "browser_physical_audition_operator_panel.html",
    "browser_physical_audition_operator_panel.js",
    "browser_physical_audition_operator_panel.css",
)
EXTENSION_MEMBERS = (*EXTENSION_PAYLOAD_MEMBERS, "build-manifest.json")
COMMANDS = (
    "validate-profile",
    "validate-fixtures",
    "campaign",
    "validate-command",
    "build-extension",
    "verify-extension",
    "source-set",
)

SHA_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
LOCAL_LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@+/\-]{0,127}$")
MODEL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@+/\-]{0,191}$")
OPAQUE_RE = re.compile(r"^opaque:[0-9a-f]{32}$")
RAW_SCHEME_RE = re.compile(r"^(?:https?|wss?|file):", re.I)
IP_RE = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?$")
FORBIDDEN_KEYS = frozenset(
    {
        "prompt",
        "promptText",
        "completion",
        "completionText",
        "tokenText",
        "sdp",
        "iceAddress",
        "candidateAddress",
        "credential",
        "credentials",
        "password",
        "secret",
        "responseBody",
        "hostname",
        "localPath",
        "rawUrl",
        "url",
        "supplier",
        "supplierRef",
        "supplierAdmissionReceipt",
        "supplierAdmissionReceiptPresent",
        "terminal",
        "authority",
        "missionAuthority",
        "commandAuthority",
        "targetingAuthority",
        "engagementAuthority",
        "effectorAuthority",
        "weaponsAuthority",
        "namedHumanConfirmation",
    }
)


class ConsoleError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def refuse(code: str, message: str) -> None:
    raise ConsoleError(code, message)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def pretty_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def identity(prefix: str, value: Any) -> str:
    return f"{prefix}_{hashlib.sha256(canonical_bytes(value)).hexdigest()}"


def load_object(path: str | os.PathLike[str]) -> dict[str, Any]:
    candidate = Path(path)
    try:
        body = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        refuse("JSON_INVALID", f"{candidate}: {exc}")
    if not isinstance(body, dict):
        refuse("OBJECT_REQUIRED", str(candidate))
    return body


def exact_keys(value: Any, required: Iterable[str], optional: Iterable[str] = ()) -> dict[str, Any]:
    if not isinstance(value, dict):
        refuse("OBJECT_REQUIRED", "a JSON object is required")
    required_set = set(required)
    allowed = required_set | set(optional)
    missing = sorted(required_set - value.keys())
    extra = sorted(value.keys() - allowed)
    if missing or extra:
        refuse("KEY_DENOMINATOR_INVALID", f"missing={missing} extra={extra}")
    return value


def regular_file(path: Path) -> bytes:
    try:
        info = path.lstat()
    except OSError as exc:
        refuse("SOURCE_MEMBER_UNAVAILABLE", f"{path}: {exc}")
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        refuse("SOURCE_MEMBER_NOT_REGULAR", str(path))
    return path.read_bytes()


def safe_relative(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        refuse("PATH_INVALID", str(value))
    path = Path(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        refuse("PATH_INVALID", value)
    return path.as_posix()


def inspect_lexical_path(path: Path) -> None:
    absolute = Path(os.path.abspath(path))
    parts = absolute.parts
    current = Path(parts[0])
    for part in parts[1:]:
        current = current / part
        if not current.exists() and not current.is_symlink():
            continue
        try:
            info = current.lstat()
        except OSError as exc:
            refuse("PATH_INSPECTION_FAILED", f"{current}: {exc}")
        if stat.S_ISLNK(info.st_mode):
            refuse("LINKED_PATH_REFUSED", str(current))
        attributes = getattr(info, "st_file_attributes", 0)
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if attributes & reparse:
            refuse("LINKED_PATH_REFUSED", str(current))


def ensure_external_output(repository_root: Path, output_root: Path) -> tuple[Path, Path]:
    inspect_lexical_path(repository_root)
    inspect_lexical_path(output_root.parent)
    repo = repository_root.resolve(strict=True)
    output = Path(os.path.abspath(output_root))
    try:
        output.relative_to(repo)
    except ValueError:
        pass
    else:
        refuse("REPOSITORY_LOCAL_OUTPUT_REFUSED", str(output))
    if output.exists() or output.is_symlink():
        refuse("OUTPUT_ALREADY_EXISTS", str(output))
    return repo, output


def validate_profile(path: str | os.PathLike[str]) -> dict[str, Any]:
    profile = load_object(path)
    exact_keys(
        profile,
        (
            "schema",
            "profileId",
            "issueRef",
            "status",
            "protocol",
            "interface",
            "admittedPacket",
            "dependencies",
            "sourceMembers",
            "extensionSourceMembers",
            "extensionPayloadMembers",
            "extensionMembers",
            "methods",
            "receiptKinds",
            "limits",
            "manifestContract",
            "fixtureCaseIds",
            "fixtureCounts",
            "commands",
            "claimBoundary",
        ),
    )
    if profile["schema"] != PROFILE_SCHEMA or profile["profileId"] != PROFILE_ID:
        refuse("PROFILE_IDENTITY_INVALID", str(path))
    if profile["issueRef"] != ISSUE_REF or profile["status"] != "candidate_source_only":
        refuse("PROFILE_STATE_INVALID", str(path))
    if profile["protocol"] != PROTOCOL or profile["interface"] != INTERFACE:
        refuse("INTERFACE_BINDING_INVALID", str(path))
    exact_keys(profile["admittedPacket"], ("commit", "tree", "profileId", "sourceBindingId", "kitId"))
    if profile["admittedPacket"] != {
        "commit": ADMITTED_PACKET_COMMIT,
        "tree": ADMITTED_PACKET_TREE,
        "profileId": "axm-head/browser-physical-audition-packet/0.1",
        "sourceBindingId": ADMITTED_PACKET_SOURCE_BINDING_ID,
        "kitId": ADMITTED_PACKET_KIT_ID,
    }:
        refuse("ADMITTED_PACKET_BINDING_INVALID", str(path))
    if tuple(profile["dependencies"]) != DEPENDENCIES:
        refuse("DEPENDENCY_DENOMINATOR_INVALID", str(path))
    for group, expected in (
        (profile["sourceMembers"], SOURCE_MEMBERS),
        (profile["extensionSourceMembers"], EXTENSION_SOURCE_MEMBERS),
        (profile["extensionPayloadMembers"], EXTENSION_PAYLOAD_MEMBERS),
        (profile["extensionMembers"], EXTENSION_MEMBERS),
        (profile["methods"], METHODS),
        (profile["receiptKinds"], RECEIPT_KINDS),
        (profile["commands"], COMMANDS),
    ):
        if tuple(group) != tuple(expected):
            refuse("PROFILE_DENOMINATOR_INVALID", str(path))
    for relative in (*profile["sourceMembers"], *(row["path"] for row in profile["dependencies"])):
        safe_relative(relative)
    if profile["limits"] != {
        "maximumCaptureBytes": MAX_CAPTURE_BYTES,
        "maximumCommandBytes": MAX_COMMAND_BYTES,
        "maximumSessionAgeMs": SESSION_MAX_AGE_MS,
        "maximumSessionRequests": MAX_SESSION_REQUESTS,
    }:
        refuse("LIMITS_INVALID", str(path))
    expected_manifest = extension_manifest(profile)
    if profile["manifestContract"] != expected_manifest:
        refuse("MANIFEST_CONTRACT_INVALID", str(path))
    exact_keys(
        profile["claimBoundary"],
        (
            "operatorConsoleSourceConstructed",
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
            "missionAuthority",
            "commandAuthority",
        ),
    )
    expected_claim = {
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
    if profile["claimBoundary"] != expected_claim:
        refuse("CLAIM_BOUNDARY_INVALID", str(path))
    lowered = canonical_bytes(profile).lower()
    for token in (b"swarm" + b"llm", b"neha" + b"nth"):
        if token in lowered:
            refuse("SUPPLIER_IDENTITY_ESCAPED_PROFILE", token.decode())
    return profile


def extension_manifest(profile: dict[str, Any] | None = None) -> dict[str, Any]:
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


def assert_no_forbidden_keys(value: Any, path: str = "$") -> None:
    if isinstance(value, list):
        if len(value) > 1024:
            refuse("ARRAY_LIMIT_EXCEEDED", path)
        for index, item in enumerate(value):
            assert_no_forbidden_keys(item, f"{path}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            if key in FORBIDDEN_KEYS:
                refuse("FORBIDDEN_FIELD", f"{path}.{key}")
            assert_no_forbidden_keys(item, f"{path}.{key}")


def string_value(
    value: Any,
    name: str,
    *,
    pattern: re.Pattern[str] | None = None,
    maximum: int = 256,
    enum_values: Iterable[str] | None = None,
) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= maximum or any(ch in value for ch in "\r\n\x00"):
        refuse("STRING_INVALID", name)
    if pattern and not pattern.fullmatch(value):
        refuse("STRING_PATTERN_INVALID", name)
    if enum_values is not None and value not in tuple(enum_values):
        refuse("ENUM_INVALID", name)
    if RAW_SCHEME_RE.match(value) or re.match(r"^[A-Za-z]:[\\/]", value) or value.startswith("\\\\"):
        refuse("RAW_COORDINATE_FORBIDDEN", name)
    if IP_RE.match(value):
        refuse("RAW_NETWORK_IDENTITY_FORBIDDEN", name)
    return value


def sha256_value(value: Any, name: str) -> str:
    return string_value(value, name, pattern=SHA_RE, maximum=71)


def bool_value(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        refuse("BOOLEAN_INVALID", name)
    return value


def number_value(
    value: Any,
    name: str,
    *,
    integer: bool = False,
    minimum: float = 0,
    maximum: float = float(2**53 - 1),
) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        refuse("NUMBER_INVALID", name)
    if integer and not isinstance(value, int):
        refuse("INTEGER_REQUIRED", name)
    if value < minimum or value > maximum:
        refuse("NUMBER_RANGE_INVALID", name)
    return value


def validate_args(method: str, args: Any) -> dict[str, Any]:
    if method not in METHODS:
        refuse("METHOD_NOT_ALLOWED", str(method))
    if not isinstance(args, dict):
        refuse("OBJECT_REQUIRED", "args")
    assert_no_forbidden_keys(args)
    if len(canonical_bytes(args)) > MAX_COMMAND_BYTES:
        refuse("COMMAND_BYTE_LIMIT_EXCEEDED", method)

    if method == "markAvailability":
        exact_keys(args, ("observedAtUnixMs", "evidenceRef", "observed"))
        return {
            "observedAtUnixMs": number_value(args["observedAtUnixMs"], "observedAtUnixMs", integer=True, minimum=946684800000, maximum=4102444800000),
            "evidenceRef": sha256_value(args["evidenceRef"], "evidenceRef"),
            "observed": bool_value(args["observed"], "observed"),
        }
    if method == "markAdapterArtifact":
        exact_keys(args, ("artifactBytes", "artifactDigest", "evidenceRef", "executableObserved"))
        return {
            "artifactBytes": number_value(args["artifactBytes"], "artifactBytes", integer=True, minimum=1),
            "artifactDigest": sha256_value(args["artifactDigest"], "artifactDigest"),
            "evidenceRef": sha256_value(args["evidenceRef"], "evidenceRef"),
            "executableObserved": bool_value(args["executableObserved"], "executableObserved"),
        }
    if method == "markFormation":
        exact_keys(args, ("artifactBound", "capacityBasis", "capacityReceiptRef", "modelCapacityBytes", "partitionMode", "topologyReceiptRef"))
        return {
            "artifactBound": bool_value(args["artifactBound"], "artifactBound"),
            "capacityBasis": string_value(args["capacityBasis"], "capacityBasis", enum_values=("artifact-bound-shards",)),
            "capacityReceiptRef": sha256_value(args["capacityReceiptRef"], "capacityReceiptRef"),
            "modelCapacityBytes": number_value(args["modelCapacityBytes"], "modelCapacityBytes", integer=True, minimum=1),
            "partitionMode": string_value(args["partitionMode"], "partitionMode", enum_values=("pipeline-layer",)),
            "topologyReceiptRef": sha256_value(args["topologyReceiptRef"], "topologyReceiptRef"),
        }
    if method == "markMember":
        exact_keys(args, ("memberId", "role", "pledgedBytes"))
        return {
            "memberId": string_value(args["memberId"], "memberId", pattern=LOCAL_LABEL_RE, maximum=128),
            "role": string_value(args["role"], "role", enum_values=("pipeline-input", "pipeline-output", "pipeline-stage", "coordinator")),
            "pledgedBytes": number_value(args["pledgedBytes"], "pledgedBytes", integer=True, minimum=1),
        }
    if method == "markModelManifest":
        exact_keys(args, ("claimedId", "boundModelId", "observedManifestDigest"))
        return {
            "claimedId": string_value(args["claimedId"], "claimedId", pattern=MODEL_ID_RE, maximum=192),
            "boundModelId": string_value(args["boundModelId"], "boundModelId", pattern=MODEL_ID_RE, maximum=192),
            "observedManifestDigest": sha256_value(args["observedManifestDigest"], "observedManifestDigest"),
        }
    if method == "markModelArtifact":
        exact_keys(args, ("artifactId", "bytes", "digest", "layerStart", "layerEnd", "memberIdHash"))
        start = number_value(args["layerStart"], "layerStart", integer=True, minimum=0, maximum=1048575)
        end = number_value(args["layerEnd"], "layerEnd", integer=True, minimum=0, maximum=1048575)
        if end < start:
            refuse("LAYER_RANGE_INVALID", "layerEnd precedes layerStart")
        return {
            "artifactId": string_value(args["artifactId"], "artifactId", pattern=LOCAL_LABEL_RE, maximum=128),
            "bytes": number_value(args["bytes"], "bytes", integer=True, minimum=1),
            "digest": sha256_value(args["digest"], "digest"),
            "layerStart": start,
            "layerEnd": end,
            "memberIdHash": string_value(args["memberIdHash"], "memberIdHash", pattern=OPAQUE_RE, maximum=39),
        }
    if method in {"markPerformanceStart", "markToken"}:
        if method == "markPerformanceStart":
            exact_keys(args, ("promptTokenCount",), ("startMonotonicMs",))
            result = {"promptTokenCount": number_value(args["promptTokenCount"], "promptTokenCount", integer=True, minimum=1, maximum=1048576)}
            optional_name = "startMonotonicMs"
        else:
            exact_keys(args, ("index",), ("monotonicMs",))
            result = {"index": number_value(args["index"], "index", integer=True, minimum=0, maximum=1048575)}
            optional_name = "monotonicMs"
        if optional_name in args and args[optional_name] not in (None, ""):
            result[optional_name] = number_value(args[optional_name], optional_name, minimum=0)
        return result
    if method == "markDrop":
        exact_keys(args, ("memberIdHash", "observedTerminal", "recovered", "evidenceRef", "controlled"))
        return {
            "memberIdHash": string_value(args["memberIdHash"], "memberIdHash", pattern=OPAQUE_RE, maximum=39),
            "observedTerminal": string_value(args["observedTerminal"], "observedTerminal", enum_values=("HALTED", "DEGRADED", "RECOVERED")),
            "recovered": bool_value(args["recovered"], "recovered"),
            "evidenceRef": sha256_value(args["evidenceRef"], "evidenceRef"),
            "controlled": bool_value(args["controlled"], "controlled"),
        }
    if method == "markEquivalence":
        exact_keys(args, ("referenceDigest", "candidateDigest", "promptTokenCount", "outputTokenCount", "evidenceRef"))
        return {
            "referenceDigest": sha256_value(args["referenceDigest"], "referenceDigest"),
            "candidateDigest": sha256_value(args["candidateDigest"], "candidateDigest"),
            "promptTokenCount": number_value(args["promptTokenCount"], "promptTokenCount", integer=True, minimum=1, maximum=1048576),
            "outputTokenCount": number_value(args["outputTokenCount"], "outputTokenCount", integer=True, minimum=1, maximum=1048576),
            "evidenceRef": sha256_value(args["evidenceRef"], "evidenceRef"),
        }
    if method == "markPrivacyDeclaration":
        exact_keys(args, ("scope", "evidenceRef", "claimsEndToEndConfidentiality"))
        return {
            "scope": string_value(args["scope"], "scope", enum_values=("browser-observed-network-surface-only",)),
            "evidenceRef": sha256_value(args["evidenceRef"], "evidenceRef"),
            "claimsEndToEndConfidentiality": bool_value(args["claimsEndToEndConfidentiality"], "claimsEndToEndConfidentiality"),
        }
    if method == "markObservationReceipt":
        exact_keys(args, ("kind", "evidenceRef"))
        return {
            "kind": string_value(args["kind"], "kind", enum_values=RECEIPT_KINDS),
            "evidenceRef": sha256_value(args["evidenceRef"], "evidenceRef"),
        }
    exact_keys(args, ())
    return {}


def validate_fixture_catalog(path: str | os.PathLike[str], profile: dict[str, Any]) -> dict[str, Any]:
    fixtures = load_object(path)
    exact_keys(fixtures, ("schema", "positiveCases", "hostileCases", "envelopeCases"))
    if fixtures["schema"] != "axm-head/browser-physical-audition-operator-console-fixtures@1":
        refuse("FIXTURE_SCHEMA_INVALID", str(path))
    rows = [*fixtures["positiveCases"], *fixtures["hostileCases"], *fixtures["envelopeCases"]]
    ids: list[str] = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("caseId"), str):
            refuse("FIXTURE_CASE_INVALID", str(row))
        ids.append(row["caseId"])
    if len(ids) != len(set(ids)) or ids != profile["fixtureCaseIds"]:
        refuse("FIXTURE_CASE_DENOMINATOR_INVALID", str(path))
    expected_counts = {
        "positive": len(fixtures["positiveCases"]),
        "hostile": len(fixtures["hostileCases"]),
        "envelope": len(fixtures["envelopeCases"]),
        "total": len(rows),
    }
    if profile["fixtureCounts"] != expected_counts:
        refuse("FIXTURE_COUNT_INVALID", str(path))
    return fixtures


def validate_envelope(envelope: Any) -> dict[str, Any]:
    if not isinstance(envelope, dict):
        refuse("OBJECT_REQUIRED", "envelope")
    exact_keys(envelope, ("protocol", "kind", "requestId", "tabId"), ("sessionId", "method", "args"))
    if envelope["protocol"] != PROTOCOL:
        refuse("PROTOCOL_INVALID", str(envelope["protocol"]))
    string_value(envelope["requestId"], "requestId", pattern=re.compile(r"^request:[0-9a-f]{32}$"), maximum=40)
    number_value(envelope["tabId"], "tabId", integer=True, minimum=0, maximum=2147483647)
    kind = envelope["kind"]
    if kind not in {"open-session", "invoke", "close-session", "status"}:
        refuse("MESSAGE_KIND_INVALID", str(kind))
    if kind == "open-session":
        exact_keys(envelope, ("protocol", "kind", "requestId", "tabId"))
        return dict(envelope)
    string_value(envelope.get("sessionId"), "sessionId", pattern=re.compile(r"^session:[0-9a-f]{32}$"), maximum=40)
    if kind == "invoke":
        exact_keys(envelope, ("protocol", "kind", "requestId", "tabId", "sessionId", "method", "args"))
        result = dict(envelope)
        result["args"] = validate_args(envelope["method"], envelope["args"])
        return result
    exact_keys(envelope, ("protocol", "kind", "requestId", "tabId", "sessionId"))
    return dict(envelope)


def campaign(profile: dict[str, Any], fixtures: dict[str, Any]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for row in fixtures["positiveCases"]:
        try:
            normalized = validate_args(row["method"], row["args"])
            outcome = "PASS"
            code = None
        except ConsoleError as exc:
            normalized = None
            outcome = "REFUSED"
            code = exc.code
        expected = row["expected"]
        results.append({"caseId": row["caseId"], "outcome": outcome, "code": code, "normalized": normalized})
        if outcome != expected:
            refuse("CAMPAIGN_MISMATCH", row["caseId"])
    for row in fixtures["hostileCases"]:
        try:
            validate_args(row["method"], row["args"])
            outcome, code = "PASS", None
        except ConsoleError as exc:
            outcome, code = "REFUSED", exc.code
        results.append({"caseId": row["caseId"], "outcome": outcome, "code": code})
        if outcome != "REFUSED" or code != row["expectedCode"]:
            refuse("CAMPAIGN_MISMATCH", row["caseId"])
    for row in fixtures["envelopeCases"]:
        try:
            validate_envelope(row["envelope"])
            outcome, code = "PASS", None
        except ConsoleError as exc:
            outcome, code = "REFUSED", exc.code
        results.append({"caseId": row["caseId"], "outcome": outcome, "code": code})
        if outcome != row["expected"] or code != row.get("expectedCode"):
            refuse("CAMPAIGN_MISMATCH", row["caseId"])
    counts = {
        "PASS": sum(row["outcome"] == "PASS" for row in results),
        "REFUSED": sum(row["outcome"] == "REFUSED" for row in results),
    }
    return {
        "schema": "axm-head/browser-physical-audition-operator-console-campaign@1",
        "status": "PASS",
        "profileId": profile["profileId"],
        "caseCount": len(results),
        "outcomeCounts": counts,
        "operatorConsoleSourceConstructed": True,
        "operatorConsoleSourceAdmitted": False,
        "browserLaunched": False,
        "actualSupplierQualified": False,
        "physicalEstateQualified": False,
        "missionAuthority": "none",
        "commandAuthority": "none",
        "results": results,
    }


def source_set(profile: dict[str, Any], repository_root: str | os.PathLike[str]) -> dict[str, Any]:
    root = Path(repository_root).resolve(strict=True)
    rows = []
    for relative in profile["sourceMembers"]:
        data = regular_file(root / relative)
        rows.append({"path": relative, "bytes": len(data), "sha256": digest_bytes(data)})
    body = {"profileId": profile["profileId"], "members": rows}
    return {
        "schema": "axm-head/browser-physical-audition-operator-console-source-set@1",
        "status": "PASS",
        "sourceMemberCount": len(rows),
        "sourceBindingId": identity("axmoperatorconsolesource", body),
        "members": rows,
    }


def verify_dependencies(profile: dict[str, Any], repository_root: Path) -> list[dict[str, Any]]:
    rows = []
    for expected in profile["dependencies"]:
        data = regular_file(repository_root / expected["path"])
        observed = {"path": expected["path"], "bytes": len(data), "sha256": digest_bytes(data), "gitBlobSha": expected["gitBlobSha"]}
        if observed["bytes"] != expected["bytes"] or observed["sha256"] != expected["sha256"]:
            refuse("DEPENDENCY_BYTES_INVALID", expected["path"])
        rows.append(observed)
    return rows


def build_extension(
    profile_path: str | os.PathLike[str], repository_root: str | os.PathLike[str], output_root: str | os.PathLike[str]
) -> dict[str, Any]:
    profile = validate_profile(profile_path)
    repo, output = ensure_external_output(Path(repository_root), Path(output_root))
    dependencies = verify_dependencies(profile, repo)
    source = source_set(profile, repo)
    output.mkdir(parents=True, exist_ok=False)
    try:
        manifest = extension_manifest(profile)
        (output / "manifest.json").write_bytes(pretty_bytes(manifest))
        probe_data = regular_file(repo / profile["dependencies"][0]["path"])
        (output / "browser_distributed_inference_probe.js").write_bytes(probe_data)
        for relative in profile["extensionSourceMembers"]:
            data = regular_file(repo / relative)
            (output / Path(relative).name).write_bytes(data)
        payload_rows = []
        for name in profile["extensionPayloadMembers"]:
            data = regular_file(output / name)
            payload_rows.append({"path": name, "bytes": len(data), "sha256": digest_bytes(data)})
        extension_id = identity(
            "axmoperatorconsoleextension",
            {"profileId": profile["profileId"], "sourceBindingId": source["sourceBindingId"], "members": payload_rows},
        )
        build_manifest = {
            "schema": "axm-head/browser-physical-audition-operator-console-build@1",
            "status": "PASS",
            "profileId": profile["profileId"],
            "protocol": profile["protocol"],
            "interface": profile["interface"],
            "admittedPacket": profile["admittedPacket"],
            "sourceBindingId": source["sourceBindingId"],
            "extensionId": extension_id,
            "memberCount": len(payload_rows),
            "members": payload_rows,
            "dependencies": dependencies,
            "claimBoundary": profile["claimBoundary"],
        }
        (output / "build-manifest.json").write_bytes(pretty_bytes(build_manifest))
        return build_manifest
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise


def cli() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("validate-profile")
    one.add_argument("profile")
    two = sub.add_parser("validate-fixtures")
    two.add_argument("profile")
    two.add_argument("fixtures")
    three = sub.add_parser("campaign")
    three.add_argument("profile")
    three.add_argument("fixtures")
    four = sub.add_parser("validate-command")
    four.add_argument("method")
    four.add_argument("args_json")
    five = sub.add_parser("build-extension")
    five.add_argument("profile")
    five.add_argument("repository_root")
    five.add_argument("output_root")
    six = sub.add_parser("verify-extension")
    six.add_argument("profile")
    six.add_argument("repository_root")
    six.add_argument("extension_root")
    seven = sub.add_parser("source-set")
    seven.add_argument("profile")
    seven.add_argument("repository_root")
    args = parser.parse_args()
    try:
        if args.command == "validate-profile":
            result = {"schema": "axm-head/browser-physical-audition-operator-console-profile-validation@1", "status": "PASS", "profileId": validate_profile(args.profile)["profileId"]}
        elif args.command == "validate-fixtures":
            profile = validate_profile(args.profile)
            fixtures = validate_fixture_catalog(args.fixtures, profile)
            result = {"schema": "axm-head/browser-physical-audition-operator-console-fixture-validation@1", "status": "PASS", "caseCount": sum(len(fixtures[key]) for key in ("positiveCases", "hostileCases", "envelopeCases"))}
        elif args.command == "campaign":
            profile = validate_profile(args.profile)
            result = campaign(profile, validate_fixture_catalog(args.fixtures, profile))
        elif args.command == "validate-command":
            result = {"schema": "axm-head/browser-physical-audition-operator-console-command-validation@1", "status": "PASS", "method": args.method, "args": validate_args(args.method, json.loads(args.args_json))}
        elif args.command == "build-extension":
            result = build_extension(args.profile, args.repository_root, args.output_root)
        elif args.command == "verify-extension":
            import verify_axm_head_browser_physical_audition_operator_console_01 as verifier

            result = verifier.verify_extension(Path(args.profile), Path(args.repository_root), Path(args.extension_root))
        else:
            result = source_set(validate_profile(args.profile), args.repository_root)
        sys.stdout.buffer.write(pretty_bytes(result))
        return 0
    except (ConsoleError, json.JSONDecodeError) as exc:
        code = exc.code if isinstance(exc, ConsoleError) else "JSON_INVALID"
        sys.stdout.buffer.write(pretty_bytes({"schema": "axm-head/browser-physical-audition-operator-console-error@1", "status": "REFUSED", "code": code, "message": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(cli())
