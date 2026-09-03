from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import stat
import sys
from pathlib import Path
from typing import Any, Iterable

PROFILE_SCHEMA = "axm-head/browser-audition-operation-plan-profile@1"
PROFILE_ID = "axm-head/browser-audition-operation-plan/0.1"
PLAN_SCHEMA = "axm-head/browser-audition-operation-plan@1"
BINDINGS_SCHEMA = "axm-head/browser-audition-operation-bindings@1"
BUILD_SCHEMA = "axm-head/browser-audition-operation-plan-build@1"
VERDICT_SCHEMA = "axm-head/browser-audition-operation-plan-verdict@1"
CAMPAIGN_SCHEMA = "axm-head/browser-audition-operation-plan-campaign@1"
FIXTURE_SCHEMA = "axm-head/browser-audition-operation-plan-fixtures@1"
INTERFACE = "axm/distributed-model-inference@1"
ISSUE_REF = "BigBirdReturns/ai-execution-audit#105"
ADMITTED_CONSOLE_COMMIT = "d083ae55a20c730c56b69863c172b43d2a6f7651"
ADMITTED_CONSOLE_TREE = "e7631a37778595c5367237a4fe52afec78120149"
ADMITTED_CONSOLE_PROFILE_ID = "axm-head/browser-physical-audition-operator-console/0.1"
ADMITTED_CONSOLE_SOURCE_BINDING = "axmoperatorconsolesource_d213e280c45cf2c81d84edf8d7af4ea077c77632472117d8f6708277ce4fe7a3"
ADMITTED_CONSOLE_EXTENSION_ID = "axmoperatorconsoleextension_63b6140baf423457b83af8da3c1dc4f3493c43933b4e6d712f53bfe6df363d01"
OPERATOR_PROTOCOL = "axm-head/browser-physical-audition-operator-console@1"
PLAN_PROTOCOL = "axm-head/browser-audition-operation-plan@1"

MAX_PLAN_BYTES = 262144
MAX_BINDINGS_BYTES = 262144
MAX_PLAN_STEPS = 480
MAX_PROBE_INVOCATIONS = 500
MAX_TOKEN_MARKS = 400
MIN_MEMBER_COUNT = 2
MAX_MEMBER_COUNT = 32
MAX_ARTIFACT_COUNT = 256
MAX_RECEIPT_COUNT = 9
MAX_SESSION_REQUESTS = 512
SESSION_REQUESTS_PER_PROBE_INVOCATION = 2
SESSION_REQUEST_RESERVE = 4

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

DEPENDENCIES = (
    {
        "path": "mating_surface/anchor_node/axm-head-browser-physical-audition-operator-console-profile-01.json",
        "bytes": 8096,
        "sha256": "sha256:f9e3b76e66b683f54a2066ba8a301b9d50e367d783d8f88e4179bd46faf15d9a",
        "gitBlobSha": "f7bfd37873c693512f8c8e190abd3520ccc7ee45",
    },
    {
        "path": "mating_surface/anchor_node/axm_head_browser_physical_audition_operator_console_01.py",
        "bytes": 34926,
        "sha256": "sha256:df4b5d8e6c0db86c144a86bd4edc10b2a32e401f79e7c1495a7262392d5cf267",
        "gitBlobSha": "0746bd163acc8fe70b292fdba6e5388164cd13c9",
    },
    {
        "path": "mating_surface/anchor_node/browser_distributed_inference_probe.js",
        "bytes": 22384,
        "sha256": "sha256:b1ded0348ffc0ec4246e9d18a08451216c89f98d6369e483808062430088565e",
        "gitBlobSha": "f8489140c119b8513a7569ff95c3900dc1672496",
    },
    {
        "path": "mating_surface/anchor_node/browser_physical_audition_operator_contract.js",
        "bytes": 14749,
        "sha256": "sha256:fe826434bc9fe2a3e47a0d991273bddd9e54852618b86b97914976d514336042",
        "gitBlobSha": "649007fbf08db899630ad8f9fb972f01146feade",
    },
    {
        "path": "mating_surface/anchor_node/browser_physical_audition_operator_service_worker.js",
        "bytes": 11228,
        "sha256": "sha256:260eb0a5f6edd0f2a448e5665245d29962bb5ab28fb21829fc9fe196abd8bb03",
        "gitBlobSha": "9c3854efd2859ab21747672d4916989aff550a04",
    },
    {
        "path": "mating_surface/anchor_node/verify_axm_head_browser_physical_audition_operator_console_01.py",
        "bytes": 15638,
        "sha256": "sha256:ca1e30c46d07883b48968d1fc18ef3c31b3f4245175f6867ba18eb5d492300ea",
        "gitBlobSha": "9c590ff86d53907a7583769a9b16555f067ce677",
    },
)

SOURCE_MEMBERS = (
    ".github/workflows/axm-head-browser-audition-operation-plan-01.yml",
    "mating_surface/anchor_node/AXM-HEAD-BROWSER-AUDITION-OPERATION-PLAN-01.md",
    "mating_surface/anchor_node/axm-head-browser-audition-operation-plan-profile-01.json",
    "mating_surface/anchor_node/axm-head-browser-audition-operation-plan-01.ps1",
    "mating_surface/anchor_node/axm_head_browser_audition_operation_plan_01.py",
    "mating_surface/anchor_node/browser_audition_operation_plan_contract.js",
    "mating_surface/anchor_node/browser_audition_operation_plan_panel.html",
    "mating_surface/anchor_node/browser_audition_operation_plan_panel.js",
    "mating_surface/anchor_node/browser_audition_operation_plan_panel.css",
    "mating_surface/anchor_node/verify_axm_head_browser_audition_operation_plan_01.py",
    "mating_surface/anchor_node/verify_axm_head_browser_audition_operation_plan_01_bootstrap.py",
    "mating_surface/anchor_node/conformance/test_axm_head_browser_audition_operation_plan_01.py",
    "mating_surface/anchor_node/fixtures/axm-head-browser-audition-operation-plan-cases-01.json",
)

EXTENSION_SOURCE_MEMBERS = (
    "mating_surface/anchor_node/browser_audition_operation_plan_contract.js",
    "mating_surface/anchor_node/browser_audition_operation_plan_panel.html",
    "mating_surface/anchor_node/browser_audition_operation_plan_panel.js",
    "mating_surface/anchor_node/browser_audition_operation_plan_panel.css",
)

EXTENSION_DEPENDENCY_MEMBERS = (
    "mating_surface/anchor_node/browser_distributed_inference_probe.js",
    "mating_surface/anchor_node/browser_physical_audition_operator_contract.js",
    "mating_surface/anchor_node/browser_physical_audition_operator_service_worker.js",
)

EXTENSION_PAYLOAD_MEMBERS = (
    "manifest.json",
    "browser_distributed_inference_probe.js",
    "browser_physical_audition_operator_contract.js",
    "browser_physical_audition_operator_service_worker.js",
    "browser_audition_operation_plan_contract.js",
    "browser_audition_operation_plan_panel.html",
    "browser_audition_operation_plan_panel.js",
    "browser_audition_operation_plan_panel.css",
)
EXTENSION_MEMBERS = (*EXTENSION_PAYLOAD_MEMBERS, "build-manifest.json")

COMMANDS = (
    "validate-profile",
    "validate-bindings",
    "compile-plan",
    "validate-plan",
    "validate-fixtures",
    "campaign",
    "source-set",
    "build-extension",
    "verify-extension",
)

SHA_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
ALIAS_RE = re.compile(r"^member:[a-z0-9][a-z0-9._-]{0,63}$")
STEP_RE = re.compile(r"^step:[a-z0-9][a-z0-9._-]{0,95}$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._:/+-]{0,191}$")
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

CLAIM_BOUNDARY = {
    "operationPlanSourceConstructed": True,
    "operationPlanSourceAdmitted": False,
    "operationPlanExecuted": False,
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


class PlanError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def refuse(code: str, message: str) -> None:
    raise PlanError(code, message)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def pretty_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def content_identity(prefix: str, value: Any) -> str:
    return f"{prefix}_{hashlib.sha256(canonical_bytes(value)).hexdigest()}"


def load_object(path: str | os.PathLike[str]) -> dict[str, Any]:
    candidate = Path(path)
    try:
        value = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        refuse("JSON_INVALID", f"{candidate}: {exc}")
    if not isinstance(value, dict):
        refuse("OBJECT_REQUIRED", str(candidate))
    return value


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


def string_value(value: Any, name: str, *, pattern: re.Pattern[str] | None = None, maximum: int = 256) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= maximum:
        refuse("STRING_INVALID", name)
    if any(ord(ch) < 0x20 for ch in value) or "\x7f" in value:
        refuse("STRING_CONTROL_INVALID", name)
    if pattern and not pattern.fullmatch(value):
        refuse("STRING_PATTERN_INVALID", name)
    if re.match(r"^(?:https?|wss?|file):", value, re.I) or re.match(r"^[A-Za-z]:[\\/]", value) or value.startswith("\\\\"):
        refuse("RAW_COORDINATE_FORBIDDEN", name)
    return value


def sha256_value(value: Any, name: str) -> str:
    return string_value(value, name, pattern=SHA_RE, maximum=71)


def integer_value(value: Any, name: str, *, minimum: int = 0, maximum: int = 2**53 - 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        refuse("INTEGER_REQUIRED", name)
    if not minimum <= value <= maximum:
        refuse("INTEGER_RANGE_INVALID", name)
    return value


def number_value(value: Any, name: str, *, minimum: float = 0) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < minimum:
        refuse("NUMBER_INVALID", name)
    return value


def assert_no_forbidden_keys(value: Any, path: str = "$") -> None:
    if isinstance(value, list):
        if len(value) > 2048:
            refuse("ARRAY_LIMIT_EXCEEDED", path)
        for index, item in enumerate(value):
            assert_no_forbidden_keys(item, f"{path}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            if key in FORBIDDEN_KEYS:
                refuse("FORBIDDEN_FIELD", f"{path}.{key}")
            assert_no_forbidden_keys(item, f"{path}.{key}")
    elif isinstance(value, str):
        if any(ord(ch) < 0x20 and ch not in "\t" for ch in value) or "\x7f" in value:
            refuse("STRING_CONTROL_INVALID", path)


def regular_file(path: Path) -> bytes:
    try:
        info = path.lstat()
    except OSError as exc:
        refuse("SOURCE_MEMBER_UNAVAILABLE", f"{path}: {exc}")
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        refuse("SOURCE_MEMBER_NOT_REGULAR", str(path))
    attributes = getattr(info, "st_file_attributes", 0)
    if attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
        refuse("SOURCE_MEMBER_NOT_REGULAR", str(path))
    return path.read_bytes()


def inspect_lexical_path(path: Path) -> None:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.parts[0])
    for part in absolute.parts[1:]:
        current = current / part
        if not current.exists() and not current.is_symlink():
            continue
        info = current.lstat()
        attributes = getattr(info, "st_file_attributes", 0)
        if stat.S_ISLNK(info.st_mode) or attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
            refuse("LINKED_PATH_REFUSED", str(current))


def safe_relative(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        refuse("PATH_INVALID", str(value))
    path = Path(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        refuse("PATH_INVALID", value)
    return path.as_posix()


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


def dependency_map() -> dict[str, dict[str, Any]]:
    return {row["path"]: dict(row) for row in DEPENDENCIES}


def load_operator_module(repository_root: Path):
    path = repository_root / DEPENDENCIES[1]["path"]
    data = regular_file(path)
    expected = DEPENDENCIES[1]
    if len(data) != expected["bytes"] or digest_bytes(data) != expected["sha256"]:
        refuse("OPERATOR_TOOL_BYTES_INVALID", str(path))
    spec = importlib.util.spec_from_file_location("axm_admitted_operator_console", path)
    if spec is None or spec.loader is None:
        refuse("OPERATOR_TOOL_IMPORT_INVALID", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def extension_manifest() -> dict[str, Any]:
    return {
        "action": {"default_title": "Open AXM audition operation plan"},
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
        "name": "AXM Browser Audition Operation Plan",
        "permissions": ["activeTab", "scripting", "sidePanel"],
        "side_panel": {"default_path": "browser_audition_operation_plan_panel.html"},
        "version": "0.1.0",
    }


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
            "operatorProtocol",
            "interface",
            "admittedConsole",
            "dependencies",
            "sourceMembers",
            "extensionSourceMembers",
            "extensionDependencyMembers",
            "extensionPayloadMembers",
            "extensionMembers",
            "receiptKinds",
            "limits",
            "manifestContract",
            "commands",
            "fixtureCaseIds",
            "fixtureCounts",
            "claimBoundary",
        ),
    )
    if profile["schema"] != PROFILE_SCHEMA or profile["profileId"] != PROFILE_ID:
        refuse("PROFILE_IDENTITY_INVALID", str(path))
    if profile["issueRef"] != ISSUE_REF or profile["status"] != "candidate_source_only":
        refuse("PROFILE_STATE_INVALID", str(path))
    if profile["protocol"] != PLAN_PROTOCOL or profile["operatorProtocol"] != OPERATOR_PROTOCOL or profile["interface"] != INTERFACE:
        refuse("PROFILE_INTERFACE_INVALID", str(path))
    if profile["admittedConsole"] != {
        "commit": ADMITTED_CONSOLE_COMMIT,
        "tree": ADMITTED_CONSOLE_TREE,
        "profileId": ADMITTED_CONSOLE_PROFILE_ID,
        "sourceBindingId": ADMITTED_CONSOLE_SOURCE_BINDING,
        "extensionId": ADMITTED_CONSOLE_EXTENSION_ID,
    }:
        refuse("ADMITTED_CONSOLE_BINDING_INVALID", str(path))
    for observed, expected in (
        (profile["dependencies"], DEPENDENCIES),
        (profile["sourceMembers"], SOURCE_MEMBERS),
        (profile["extensionSourceMembers"], EXTENSION_SOURCE_MEMBERS),
        (profile["extensionDependencyMembers"], EXTENSION_DEPENDENCY_MEMBERS),
        (profile["extensionPayloadMembers"], EXTENSION_PAYLOAD_MEMBERS),
        (profile["extensionMembers"], EXTENSION_MEMBERS),
        (profile["receiptKinds"], RECEIPT_KINDS),
        (profile["commands"], COMMANDS),
    ):
        if tuple(observed) != tuple(expected):
            refuse("PROFILE_DENOMINATOR_INVALID", str(path))
    for relative in (*SOURCE_MEMBERS, *(row["path"] for row in DEPENDENCIES)):
        safe_relative(relative)
    if profile["limits"] != {
        "maximumPlanBytes": MAX_PLAN_BYTES,
        "maximumBindingsBytes": MAX_BINDINGS_BYTES,
        "maximumPlanSteps": MAX_PLAN_STEPS,
        "maximumProbeInvocations": MAX_PROBE_INVOCATIONS,
        "maximumTokenMarks": MAX_TOKEN_MARKS,
        "minimumMemberCount": MIN_MEMBER_COUNT,
        "maximumMemberCount": MAX_MEMBER_COUNT,
        "maximumArtifactCount": MAX_ARTIFACT_COUNT,
        "maximumReceiptCount": MAX_RECEIPT_COUNT,
        "operatorMaximumSessionRequests": MAX_SESSION_REQUESTS,
        "sessionRequestReserve": SESSION_REQUEST_RESERVE,
        "sessionRequestsPerProbeInvocation": SESSION_REQUESTS_PER_PROBE_INVOCATION,
    }:
        refuse("PROFILE_LIMITS_INVALID", str(path))
    if profile["manifestContract"] != extension_manifest():
        refuse("MANIFEST_CONTRACT_INVALID", str(path))
    if profile["claimBoundary"] != CLAIM_BOUNDARY:
        refuse("CLAIM_BOUNDARY_INVALID", str(path))
    lowered = canonical_bytes(profile).lower()
    for token in (b"swarm" + b"llm", b"neha" + b"nth"):
        if token in lowered:
            refuse("SUPPLIER_IDENTITY_ESCAPED_PROFILE", token.decode())
    return profile


def normalized_bindings_body(bindings: dict[str, Any]) -> dict[str, Any]:
    body = json.loads(json.dumps(bindings))
    body["bindingsId"] = None
    return body


def validate_bindings(value: dict[str, Any], operator_module: Any) -> dict[str, Any]:
    if len(canonical_bytes(value)) > MAX_BINDINGS_BYTES:
        refuse("BINDINGS_BYTE_LIMIT_EXCEEDED", str(len(canonical_bytes(value))))
    exact_keys(value, ("schema", "bindingsId", "profileId", "protocol", "interface", "transactionRef", "seatRef", "values", "claimBoundary"))
    if value["schema"] != BINDINGS_SCHEMA or value["profileId"] != PROFILE_ID or value["protocol"] != PLAN_PROTOCOL or value["interface"] != INTERFACE:
        refuse("BINDINGS_IDENTITY_INVALID", "bindings")
    expected_id = content_identity("axmoperationbindings", normalized_bindings_body(value))
    if value["bindingsId"] != expected_id:
        refuse("BINDINGS_CONTENT_ID_INVALID", str(value.get("bindingsId")))
    sha256_value(value["transactionRef"], "transactionRef")
    sha256_value(value["seatRef"], "seatRef")
    if value["claimBoundary"] != CLAIM_BOUNDARY:
        refuse("CLAIM_BOUNDARY_INVALID", "bindings")
    assert_no_forbidden_keys(value["values"], "$.values")
    values = exact_keys(
        value["values"],
        (
            "availability",
            "adapterArtifact",
            "formation",
            "members",
            "modelManifest",
            "modelArtifacts",
            "performanceStart",
            "tokenMarks",
            "drop",
            "equivalence",
            "privacy",
            "receipts",
        ),
    )

    direct_methods = (
        ("markAvailability", "availability"),
        ("markAdapterArtifact", "adapterArtifact"),
        ("markFormation", "formation"),
        ("markModelManifest", "modelManifest"),
        ("markPerformanceStart", "performanceStart"),
        ("markEquivalence", "equivalence"),
        ("markPrivacyDeclaration", "privacy"),
    )
    normalized: dict[str, Any] = {}
    for method, key in direct_methods:
        try:
            normalized[key] = operator_module.validate_args(method, values[key])
        except Exception as exc:
            refuse(getattr(exc, "code", "OPERATOR_VALIDATION_FAILED"), f"{key}: {exc}")

    members = values["members"]
    if not isinstance(members, list) or not MIN_MEMBER_COUNT <= len(members) <= MAX_MEMBER_COUNT:
        refuse("MEMBER_COUNT_INVALID", str(len(members) if isinstance(members, list) else "non-list"))
    normalized_members = []
    aliases: set[str] = set()
    member_ids: set[str] = set()
    role_counts = {"pipeline-input": 0, "pipeline-output": 0}
    for index, row in enumerate(members):
        exact_keys(row, ("alias", "args"))
        alias = string_value(row["alias"], f"members[{index}].alias", pattern=ALIAS_RE, maximum=71)
        if alias in aliases:
            refuse("MEMBER_ALIAS_DUPLICATE", alias)
        aliases.add(alias)
        try:
            args = operator_module.validate_args("markMember", row["args"])
        except Exception as exc:
            refuse(getattr(exc, "code", "OPERATOR_VALIDATION_FAILED"), f"members[{index}]: {exc}")
        if args["memberId"] in member_ids:
            refuse("MEMBER_ID_DUPLICATE", args["memberId"])
        member_ids.add(args["memberId"])
        if args["role"] in role_counts:
            role_counts[args["role"]] += 1
        normalized_members.append({"alias": alias, "args": args})
    if role_counts != {"pipeline-input": 1, "pipeline-output": 1}:
        refuse("MEMBER_ROLE_DENOMINATOR_INVALID", str(role_counts))
    normalized["members"] = normalized_members

    artifacts = values["modelArtifacts"]
    if not isinstance(artifacts, list) or not 1 <= len(artifacts) <= MAX_ARTIFACT_COUNT:
        refuse("ARTIFACT_COUNT_INVALID", str(len(artifacts) if isinstance(artifacts, list) else "non-list"))
    normalized_artifacts = []
    artifact_ids: set[str] = set()
    expected_layer = 0
    total_bytes = 0
    for index, row in enumerate(artifacts):
        exact_keys(row, ("memberAlias", "args"))
        alias = string_value(row["memberAlias"], f"modelArtifacts[{index}].memberAlias", pattern=ALIAS_RE, maximum=71)
        if alias not in aliases:
            refuse("MEMBER_ALIAS_UNRESOLVED", alias)
        args = dict(row["args"])
        exact_keys(args, ("artifactId", "bytes", "digest", "layerStart", "layerEnd"))
        if args["artifactId"] in artifact_ids:
            refuse("ARTIFACT_ID_DUPLICATE", str(args["artifactId"]))
        artifact_ids.add(str(args["artifactId"]))
        candidate = {**args, "memberIdHash": "opaque:" + "0" * 32}
        try:
            checked = operator_module.validate_args("markModelArtifact", candidate)
        except Exception as exc:
            refuse(getattr(exc, "code", "OPERATOR_VALIDATION_FAILED"), f"modelArtifacts[{index}]: {exc}")
        if checked["layerStart"] != expected_layer:
            refuse("LAYER_DENOMINATOR_NOT_CONTIGUOUS", f"expected={expected_layer} observed={checked['layerStart']}")
        expected_layer = checked["layerEnd"] + 1
        total_bytes += checked["bytes"]
        checked.pop("memberIdHash")
        normalized_artifacts.append({"memberAlias": alias, "args": checked})
    if total_bytes != normalized["formation"]["modelCapacityBytes"]:
        refuse("FORMATION_CAPACITY_MISMATCH", f"formation={normalized['formation']['modelCapacityBytes']} artifacts={total_bytes}")
    normalized["modelArtifacts"] = normalized_artifacts

    token_marks = values["tokenMarks"]
    if not isinstance(token_marks, list) or not 1 <= len(token_marks) <= MAX_TOKEN_MARKS:
        refuse("TOKEN_COUNT_INVALID", str(len(token_marks) if isinstance(token_marks, list) else "non-list"))
    normalized_tokens = []
    previous_time: float | None = None
    for index, args in enumerate(token_marks):
        try:
            checked = operator_module.validate_args("markToken", args)
        except Exception as exc:
            refuse(getattr(exc, "code", "OPERATOR_VALIDATION_FAILED"), f"tokenMarks[{index}]: {exc}")
        if checked["index"] != index:
            refuse("TOKEN_INDEX_NOT_CONTIGUOUS", f"expected={index} observed={checked['index']}")
        mark = checked.get("monotonicMs")
        if mark is not None and previous_time is not None and mark < previous_time:
            refuse("TOKEN_TIME_REGRESSION", f"index={index}")
        if mark is not None:
            previous_time = mark
        normalized_tokens.append(checked)
    normalized["tokenMarks"] = normalized_tokens

    drop = exact_keys(values["drop"], ("memberAlias", "args"))
    drop_alias = string_value(drop["memberAlias"], "drop.memberAlias", pattern=ALIAS_RE, maximum=71)
    if drop_alias not in aliases:
        refuse("MEMBER_ALIAS_UNRESOLVED", drop_alias)
    drop_candidate = {**drop["args"], "memberIdHash": "opaque:" + "0" * 32}
    try:
        checked_drop = operator_module.validate_args("markDrop", drop_candidate)
    except Exception as exc:
        refuse(getattr(exc, "code", "OPERATOR_VALIDATION_FAILED"), f"drop: {exc}")
    checked_drop.pop("memberIdHash")
    normalized["drop"] = {"memberAlias": drop_alias, "args": checked_drop}

    start_mark = normalized["performanceStart"].get("startMonotonicMs")
    if start_mark is not None and not isinstance(start_mark, int):
        refuse("MONOTONIC_TIME_INTEGER_REQUIRED", "performanceStart.startMonotonicMs")
    for index, token in enumerate(normalized_tokens):
        mark = token.get("monotonicMs")
        if mark is not None and not isinstance(mark, int):
            refuse("MONOTONIC_TIME_INTEGER_REQUIRED", f"tokenMarks[{index}].monotonicMs")
    if normalized["performanceStart"]["promptTokenCount"] != normalized["equivalence"]["promptTokenCount"]:
        refuse("PROMPT_TOKEN_DENOMINATOR_MISMATCH", "performance and equivalence")
    if normalized["equivalence"]["outputTokenCount"] != len(normalized_tokens):
        refuse("OUTPUT_TOKEN_DENOMINATOR_MISMATCH", "equivalence and token marks")

    receipts = values["receipts"]
    if not isinstance(receipts, list) or len(receipts) != MAX_RECEIPT_COUNT:
        refuse("RECEIPT_COUNT_INVALID", str(len(receipts) if isinstance(receipts, list) else "non-list"))
    normalized_receipts = []
    for index, args in enumerate(receipts):
        try:
            checked = operator_module.validate_args("markObservationReceipt", args)
        except Exception as exc:
            refuse(getattr(exc, "code", "OPERATOR_VALIDATION_FAILED"), f"receipts[{index}]: {exc}")
        if checked["kind"] != RECEIPT_KINDS[index]:
            refuse("RECEIPT_DENOMINATOR_INVALID", f"index={index} kind={checked['kind']}")
        normalized_receipts.append(checked)
    normalized["receipts"] = normalized_receipts

    evidence_matches = {
        "current-availability-observation": normalized["availability"]["evidenceRef"],
        "executable-adapter-artifact": normalized["adapterArtifact"]["evidenceRef"],
        "formation-capacity-receipt": normalized["formation"]["capacityReceiptRef"],
        "formation-topology-receipt": normalized["formation"]["topologyReceiptRef"],
        "member-drop-behavior-receipt": normalized["drop"]["args"]["evidenceRef"],
        "model-output-equivalence-receipt": normalized["equivalence"]["evidenceRef"],
        "privacy-declaration": normalized["privacy"]["evidenceRef"],
    }
    for receipt in normalized_receipts:
        expected = evidence_matches.get(receipt["kind"])
        if expected is not None and receipt["evidenceRef"] != expected:
            refuse("RECEIPT_EVIDENCE_BINDING_MISMATCH", receipt["kind"])

    normalized_value = {
        "schema": BINDINGS_SCHEMA,
        "bindingsId": value["bindingsId"],
        "profileId": PROFILE_ID,
        "protocol": PLAN_PROTOCOL,
        "interface": INTERFACE,
        "transactionRef": value["transactionRef"],
        "seatRef": value["seatRef"],
        "values": normalized,
        "claimBoundary": CLAIM_BOUNDARY,
    }
    if normalized_value != value:
        refuse("BINDINGS_NOT_CANONICAL", "input differs from normalized binding object")
    return normalized_value


def step(step_id: str, kind: str, **values: Any) -> dict[str, Any]:
    return {"stepId": step_id, "kind": kind, **values}


def expected_steps(bindings: dict[str, Any]) -> list[dict[str, Any]]:
    values = bindings["values"]
    steps: list[dict[str, Any]] = [
        step("step:status-preflight", "console-status"),
        step(
            "step:capture-preflight",
            "probe-call",
            method="exportCapture",
            literalArgs={},
            captureUse="preflight",
        ),
        step(
            "step:barrier-before-execution",
            "operator-barrier",
            code="BEFORE_PLAN_EXECUTION",
            statement="The operator has reviewed the bound transaction, seat, and complete invocation denominator.",
        ),
        step("step:availability", "probe-call", method="markAvailability", argsRef="values.availability"),
        step("step:adapter-artifact", "probe-call", method="markAdapterArtifact", argsRef="values.adapterArtifact"),
        step("step:formation", "probe-call", method="markFormation", argsRef="values.formation"),
    ]
    for index, member in enumerate(values["members"]):
        steps.append(
            step(
                f"step:member-{index:02d}",
                "probe-call",
                method="markMember",
                argsRef=f"values.members.{index}.args",
                saveResultAs=member["alias"],
            )
        )
    steps.append(step("step:model-manifest", "probe-call", method="markModelManifest", argsRef="values.modelManifest"))
    for index, artifact in enumerate(values["modelArtifacts"]):
        steps.append(
            step(
                f"step:model-artifact-{index:03d}",
                "probe-call",
                method="markModelArtifact",
                argsRef=f"values.modelArtifacts.{index}.args",
                resultRefs={"memberIdHash": artifact["memberAlias"]},
            )
        )
    steps.append(step("step:performance-start", "probe-call", method="markPerformanceStart", argsRef="values.performanceStart"))
    for index, _ in enumerate(values["tokenMarks"]):
        steps.append(step(f"step:token-{index:03d}", "probe-call", method="markToken", argsRef=f"values.tokenMarks.{index}"))
    steps.extend(
        [
            step(
                "step:controlled-drop",
                "probe-call",
                method="markDrop",
                argsRef="values.drop.args",
                resultRefs={"memberIdHash": values["drop"]["memberAlias"]},
            ),
            step("step:equivalence", "probe-call", method="markEquivalence", argsRef="values.equivalence"),
            step("step:privacy", "probe-call", method="markPrivacyDeclaration", argsRef="values.privacy"),
        ]
    )
    for index, receipt in enumerate(values["receipts"]):
        steps.append(
            step(
                f"step:receipt-{index:02d}",
                "probe-call",
                method="markObservationReceipt",
                argsRef=f"values.receipts.{index}",
                receiptKind=receipt["kind"],
            )
        )
    steps.extend(
        [
            step("step:peer-stats", "probe-call", method="samplePeerStats", literalArgs={}),
            step(
                "step:barrier-before-export",
                "operator-barrier",
                code="BEFORE_CAPTURE_EXPORT",
                statement="The operator has completed the physical observation and authorizes local private capture export.",
            ),
            step("step:capture-export", "probe-call", method="exportCapture", literalArgs={}, captureUse="download"),
        ]
    )
    return steps


def normalized_plan_body(plan: dict[str, Any]) -> dict[str, Any]:
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
    plan = {
        "schema": PLAN_SCHEMA,
        "planId": None,
        "profileId": PROFILE_ID,
        "protocol": PLAN_PROTOCOL,
        "operatorProtocol": OPERATOR_PROTOCOL,
        "interface": INTERFACE,
        "bindingsId": bindings["bindingsId"],
        "transactionRef": bindings["transactionRef"],
        "seatRef": bindings["seatRef"],
        "stepCount": len(steps),
        "probeInvocationCount": invocation_count,
        "steps": steps,
        "claimBoundary": CLAIM_BOUNDARY,
    }
    plan["planId"] = content_identity("axmoperationplan", normalized_plan_body(plan))
    return plan


def validate_plan(value: dict[str, Any], bindings: dict[str, Any]) -> dict[str, Any]:
    if len(canonical_bytes(value)) > MAX_PLAN_BYTES:
        refuse("PLAN_BYTE_LIMIT_EXCEEDED", str(len(canonical_bytes(value))))
    exact_keys(
        value,
        (
            "schema",
            "planId",
            "profileId",
            "protocol",
            "operatorProtocol",
            "interface",
            "bindingsId",
            "transactionRef",
            "seatRef",
            "stepCount",
            "probeInvocationCount",
            "steps",
            "claimBoundary",
        ),
    )
    assert_no_forbidden_keys(value["steps"], "$.steps")
    expected = compile_plan(bindings)
    if value != expected:
        refuse("PLAN_NOT_DETERMINISTIC", "plan differs from compiler output")
    if value["planId"] != content_identity("axmoperationplan", normalized_plan_body(value)):
        refuse("PLAN_CONTENT_ID_INVALID", value["planId"])
    return value


def validate_fixture_catalog(path: str | os.PathLike[str], profile: dict[str, Any]) -> dict[str, Any]:
    fixtures = load_object(path)
    exact_keys(fixtures, ("schema", "positiveCases", "hostileCases"))
    if fixtures["schema"] != FIXTURE_SCHEMA:
        refuse("FIXTURE_SCHEMA_INVALID", str(path))
    rows = [*fixtures["positiveCases"], *fixtures["hostileCases"]]
    ids = [row.get("caseId") for row in rows]
    if not all(isinstance(item, str) for item in ids) or len(ids) != len(set(ids)) or ids != profile["fixtureCaseIds"]:
        refuse("FIXTURE_CASE_DENOMINATOR_INVALID", str(path))
    counts = {"positive": len(fixtures["positiveCases"]), "hostile": len(fixtures["hostileCases"]), "total": len(rows)}
    if counts != profile["fixtureCounts"]:
        refuse("FIXTURE_COUNT_INVALID", str(path))
    return fixtures


def campaign(profile: dict[str, Any], fixtures: dict[str, Any], operator_module: Any) -> dict[str, Any]:
    results = []
    for row in fixtures["positiveCases"]:
        try:
            bindings = validate_bindings(row["bindings"], operator_module)
            plan = compile_plan(bindings)
            validate_plan(plan, bindings)
            outcome, code = "PASS", None
        except PlanError as exc:
            outcome, code = "REFUSED", exc.code
        results.append({"caseId": row["caseId"], "outcome": outcome, "code": code})
        if outcome != "PASS":
            refuse("CAMPAIGN_MISMATCH", row["caseId"])
    for row in fixtures["hostileCases"]:
        try:
            bindings = validate_bindings(row["bindings"], operator_module)
            plan = row.get("plan") or compile_plan(bindings)
            validate_plan(plan, bindings)
            outcome, code = "PASS", None
        except PlanError as exc:
            outcome, code = "REFUSED", exc.code
        results.append({"caseId": row["caseId"], "outcome": outcome, "code": code})
        if outcome != "REFUSED" or code != row["expectedCode"]:
            refuse("CAMPAIGN_MISMATCH", row["caseId"])
    return {
        "schema": CAMPAIGN_SCHEMA,
        "status": "PASS",
        "profileId": PROFILE_ID,
        "caseCount": len(results),
        "outcomeCounts": {
            "PASS": sum(row["outcome"] == "PASS" for row in results),
            "REFUSED": sum(row["outcome"] == "REFUSED" for row in results),
        },
        "operationPlanSourceConstructed": True,
        "operationPlanSourceAdmitted": False,
        "operationPlanExecuted": False,
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
    body = {"profileId": PROFILE_ID, "members": rows}
    return {
        "schema": "axm-head/browser-audition-operation-plan-source-set@1",
        "status": "PASS",
        "sourceMemberCount": len(rows),
        "sourceBindingId": content_identity("axmoperationplansource", body),
        "members": rows,
    }


def verify_dependencies(profile: dict[str, Any], repository_root: Path) -> list[dict[str, Any]]:
    rows = []
    for expected in profile["dependencies"]:
        data = regular_file(repository_root / expected["path"])
        observed = {
            "path": expected["path"],
            "bytes": len(data),
            "sha256": digest_bytes(data),
            "gitBlobSha": expected["gitBlobSha"],
        }
        if observed != expected:
            refuse("DEPENDENCY_BYTES_INVALID", expected["path"])
        rows.append(observed)
    return rows


def build_extension(profile_path: str | os.PathLike[str], repository_root: str | os.PathLike[str], output_root: str | os.PathLike[str]) -> dict[str, Any]:
    profile = validate_profile(profile_path)
    repo, output = ensure_external_output(Path(repository_root), Path(output_root))
    dependencies = verify_dependencies(profile, repo)
    source = source_set(profile, repo)
    output.mkdir(parents=True, exist_ok=False)
    try:
        (output / "manifest.json").write_bytes(pretty_bytes(extension_manifest()))
        for relative in profile["extensionDependencyMembers"]:
            (output / Path(relative).name).write_bytes(regular_file(repo / relative))
        for relative in profile["extensionSourceMembers"]:
            (output / Path(relative).name).write_bytes(regular_file(repo / relative))
        members = []
        for name in profile["extensionPayloadMembers"]:
            data = regular_file(output / name)
            members.append({"path": name, "bytes": len(data), "sha256": digest_bytes(data)})
        extension_id = content_identity(
            "axmoperationplanextension",
            {"profileId": PROFILE_ID, "sourceBindingId": source["sourceBindingId"], "members": members},
        )
        build = {
            "schema": BUILD_SCHEMA,
            "status": "PASS",
            "profileId": PROFILE_ID,
            "protocol": PLAN_PROTOCOL,
            "operatorProtocol": OPERATOR_PROTOCOL,
            "interface": INTERFACE,
            "admittedConsole": profile["admittedConsole"],
            "sourceBindingId": source["sourceBindingId"],
            "extensionId": extension_id,
            "memberCount": len(members),
            "members": members,
            "dependencies": dependencies,
            "claimBoundary": CLAIM_BOUNDARY,
        }
        (output / "build-manifest.json").write_bytes(pretty_bytes(build))
        return build
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise


def verify_extension(profile_path: str | os.PathLike[str], repository_root: str | os.PathLike[str], extension_root: str | os.PathLike[str]) -> dict[str, Any]:
    profile = validate_profile(profile_path)
    repo = Path(repository_root).resolve(strict=True)
    extension = Path(extension_root).resolve(strict=True)
    observed_names = {path.name for path in extension.iterdir()}
    if observed_names != set(EXTENSION_MEMBERS) or any(path.is_dir() for path in extension.iterdir()):
        refuse("EXTENSION_MEMBER_DENOMINATOR_INVALID", str(sorted(observed_names)))
    if load_object(extension / "manifest.json") != extension_manifest():
        refuse("EXTENSION_MANIFEST_INVALID", str(extension))
    source = source_set(profile, repo)
    dependencies = verify_dependencies(profile, repo)
    for relative in profile["extensionDependencyMembers"]:
        if regular_file(extension / Path(relative).name) != regular_file(repo / relative):
            refuse("DEPENDENCY_COPY_INVALID", relative)
    for relative in profile["extensionSourceMembers"]:
        if regular_file(extension / Path(relative).name) != regular_file(repo / relative):
            refuse("SOURCE_COPY_INVALID", relative)
    members = []
    for name in profile["extensionPayloadMembers"]:
        data = regular_file(extension / name)
        members.append({"path": name, "bytes": len(data), "sha256": digest_bytes(data)})
    expected_id = content_identity(
        "axmoperationplanextension",
        {"profileId": PROFILE_ID, "sourceBindingId": source["sourceBindingId"], "members": members},
    )
    build = load_object(extension / "build-manifest.json")
    if build != {
        "schema": BUILD_SCHEMA,
        "status": "PASS",
        "profileId": PROFILE_ID,
        "protocol": PLAN_PROTOCOL,
        "operatorProtocol": OPERATOR_PROTOCOL,
        "interface": INTERFACE,
        "admittedConsole": profile["admittedConsole"],
        "sourceBindingId": source["sourceBindingId"],
        "extensionId": expected_id,
        "memberCount": len(members),
        "members": members,
        "dependencies": dependencies,
        "claimBoundary": CLAIM_BOUNDARY,
    }:
        refuse("BUILD_MANIFEST_INVALID", str(extension))
    joined = b"\n".join(regular_file(extension / Path(relative).name).lower() for relative in EXTENSION_SOURCE_MEMBERS)
    for token in (b"swarm" + b"llm", b"neha" + b"nth"):
        if token in joined:
            refuse("SUPPLIER_IDENTITY_ESCAPED_EXTENSION", token.decode())
    for token in (b"fetch(", b"xmlhttprequest", b"websocket", b"indexeddb", b"localstorage", b"sessionstorage", b"chrome.storage"):
        if token in joined:
            refuse("EXTENSION_EXTERNAL_SURFACE_FORBIDDEN", token.decode())
    panel = regular_file(extension / "browser_audition_operation_plan_panel.html").decode("utf-8")
    if "browser_physical_audition_operator_contract.js" not in panel or "browser_audition_operation_plan_contract.js" not in panel:
        refuse("PANEL_CONTRACT_ORDER_INVALID", "panel")
    panel_source = regular_file(extension / "browser_audition_operation_plan_panel.js").decode("utf-8")
    required_panel_controls = (
        'captureUse === "preflight"',
        'PROBE_LEDGER_ALREADY_MARKED',
        'PROBE_INSTALLATION_LATE',
        'MUTATING_METHODS.has(current.method)',
        'probeMutationPossible',
        'settleSessionLoss',
        'requireHealthyInspection',
        'requirePostInvocationInspection',
        'releaseFailedOpenSession',
        'disconnectCurrentPort',
        'PROBE_REFUSAL_STATE_ABSENT',
        'PROBE_CAPTURE_REFUSED',
        'serializeCaptureForDownload',
        'new Blob([serialized]',
    )
    for marker in required_panel_controls:
        if marker not in panel_source:
            refuse("PANEL_CONTROL_MISSING", marker)
    if panel_source.count('requireHealthyInspection(response.inspection)') != 5:
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
    if "JSON.stringify(capture, null, 2)" in panel_source:
        refuse("CAPTURE_SERIALIZATION_DIVERGENCE", "pretty capture serialization")
    return {
        "schema": VERDICT_SCHEMA,
        "status": "PASS",
        "profileId": PROFILE_ID,
        "sourceBindingId": source["sourceBindingId"],
        "extensionId": expected_id,
        "sourceMemberCount": len(SOURCE_MEMBERS),
        "extensionMemberCount": len(EXTENSION_MEMBERS),
        "checks": [
            "exact-admitted-console-binding",
            "deterministic-operation-plan",
            "payload-source-byte-binding",
            "closed-local-extension-surface",
            "supplier-neutral-executable-surface",
            "pristine-ledger-preflight",
            "mutation-uncertainty-stop",
            "probe-refusal-state-stop",
            "post-invocation-inspection-stop",
            "failed-open-session-release",
            "exact-download-byte-binding",
            "operator-barrier-before-execution",
            "operator-barrier-before-export",
        ],
        "bootstrapAuthenticated": False,
        **CLAIM_BOUNDARY,
    }


def cli() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("validate-profile"); p.add_argument("profile")
    p = sub.add_parser("validate-bindings"); p.add_argument("profile"); p.add_argument("repository_root"); p.add_argument("bindings")
    p = sub.add_parser("compile-plan"); p.add_argument("profile"); p.add_argument("repository_root"); p.add_argument("bindings")
    p = sub.add_parser("validate-plan"); p.add_argument("profile"); p.add_argument("repository_root"); p.add_argument("bindings"); p.add_argument("plan")
    p = sub.add_parser("validate-fixtures"); p.add_argument("profile"); p.add_argument("fixtures")
    p = sub.add_parser("campaign"); p.add_argument("profile"); p.add_argument("repository_root"); p.add_argument("fixtures")
    p = sub.add_parser("source-set"); p.add_argument("profile"); p.add_argument("repository_root")
    p = sub.add_parser("build-extension"); p.add_argument("profile"); p.add_argument("repository_root"); p.add_argument("output_root")
    p = sub.add_parser("verify-extension"); p.add_argument("profile"); p.add_argument("repository_root"); p.add_argument("extension_root")
    args = parser.parse_args()
    try:
        profile = validate_profile(args.profile)
        if args.command == "validate-profile": result = {"status": "PASS", "profileId": profile["profileId"]}
        elif args.command == "validate-bindings":
            result = validate_bindings(load_object(args.bindings), load_operator_module(Path(args.repository_root).resolve(strict=True)))
        elif args.command == "compile-plan":
            bindings = validate_bindings(load_object(args.bindings), load_operator_module(Path(args.repository_root).resolve(strict=True)))
            result = compile_plan(bindings)
        elif args.command == "validate-plan":
            bindings = validate_bindings(load_object(args.bindings), load_operator_module(Path(args.repository_root).resolve(strict=True)))
            result = validate_plan(load_object(args.plan), bindings)
        elif args.command == "validate-fixtures": result = validate_fixture_catalog(args.fixtures, profile)
        elif args.command == "campaign":
            root = Path(args.repository_root).resolve(strict=True)
            result = campaign(profile, validate_fixture_catalog(args.fixtures, profile), load_operator_module(root))
        elif args.command == "source-set": result = source_set(profile, args.repository_root)
        elif args.command == "build-extension": result = build_extension(args.profile, args.repository_root, args.output_root)
        elif args.command == "verify-extension": result = verify_extension(args.profile, args.repository_root, args.extension_root)
        else: raise AssertionError(args.command)
        sys.stdout.buffer.write(pretty_bytes(result))
        return 0
    except PlanError as exc:
        sys.stdout.buffer.write(pretty_bytes({"schema": VERDICT_SCHEMA, "status": "REFUSED", "code": exc.code, "message": str(exc), **CLAIM_BOUNDARY}))
        return 2


if __name__ == "__main__":
    raise SystemExit(cli())
