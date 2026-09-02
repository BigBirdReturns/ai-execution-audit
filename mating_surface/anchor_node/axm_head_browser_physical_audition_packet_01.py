from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import types
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable

PROFILE_SCHEMA = "axm-head/browser-physical-audition-packet-profile@1"
FIXTURE_SCHEMA = "axm-head/browser-physical-audition-packet-fixtures@1"
CONTROLLER_TEMPLATE_SCHEMA = "axm-head/browser-physical-audition-controller-template@1"
PACKET_DECISION_SCHEMA = "axm-head/browser-physical-audition-packet-decision@1"
PACKET_PUBLIC_SCHEMA = "axm-head/browser-physical-audition-packet-public@1"
PACKET_VERDICT_SCHEMA = "axm-head/browser-physical-audition-packet-verdict@1"
CONFIRMATION_SCHEMA = "axm-head/browser-physical-audition-named-human-confirmation@1"
KIT_SOURCE_BINDING_SCHEMA = "axm-head/browser-physical-audition-kit-source-binding@1"
KIT_MANIFEST_SCHEMA = "axm-head/browser-physical-audition-kit-manifest@1"
SOURCE_SET_SCHEMA = "axm-head/browser-physical-audition-packet-source-set@1"
CAMPAIGN_SCHEMA = "axm-head/browser-physical-audition-packet-campaign@1"
CLI_REFUSAL_SCHEMA = "axm-head/browser-physical-audition-packet-cli-refusal@1"

PROFILE_ID = "axm-head/browser-physical-audition-packet/0.1"
ISSUE_REF = "BigBirdReturns/ai-execution-audit#98"
INTERFACE = "axm/distributed-model-inference@1"
ADMITTED_COMMIT = "e32cf641cddd00ab1c97d7d6af1708c84ea491b6"
ADMITTED_TREE = "271956e4a5068c0d71f5223b032cd2e19d4a7c8d"
ADMITTED_CANDIDATE_COMMIT = "351f1f1e54e4d454137b69ad64e571590db134dd"
ADMITTED_AUDITION_PROFILE_ID = "axm-head/browser-distributed-inference-audition/0.1"
PROBE_SHA256_REF = "sha256:b1ded0348ffc0ec4246e9d18a08451216c89f98d6369e483808062430088565e"
SEAT_IDS = ("seat-01", "seat-02")
TERMINALS = (
    "PREPARED_NOT_EXECUTED",
    "READY_FOR_NAMED_HUMAN",
    "OBSERVED_ROUTE_CANDIDATE",
    "HOLD",
    "REFUSED",
)
COMMANDS = (
    "validate-profile",
    "validate-fixtures",
    "campaign",
    "build-kit",
    "assemble",
    "verify",
    "public-projection",
    "source-set",
)
SOURCE_MEMBERS = (
    ".github/workflows/axm-head-browser-physical-audition-packet-01.yml",
    "mating_surface/anchor_node/AXM-HEAD-BROWSER-PHYSICAL-AUDITION-PACKET-01.md",
    "mating_surface/anchor_node/axm-head-browser-physical-audition-packet-profile-01.json",
    "mating_surface/anchor_node/axm-head-browser-physical-audition-controller-template-01.json",
    "mating_surface/anchor_node/axm-head-browser-physical-audition-packet-01.ps1",
    "mating_surface/anchor_node/axm_head_browser_physical_audition_packet_01.py",
    "mating_surface/anchor_node/verify_axm_head_browser_physical_audition_packet_01.py",
    "mating_surface/anchor_node/verify_axm_head_browser_physical_audition_packet_01_bootstrap.py",
    "mating_surface/anchor_node/conformance/test_axm_head_browser_physical_audition_packet_01.py",
    "mating_surface/anchor_node/fixtures/axm-head-browser-physical-audition-packet-cases-01.json",
)
ADMITTED_SOURCE_MEMBERS = (
    (".github/workflows/axm-head-browser-distributed-inference-audition-01.yml", "bda298075ce2516eb138f818479a2be102cb6916"),
    ("mating_surface/anchor_node/AXM-HEAD-BROWSER-DISTRIBUTED-INFERENCE-AUDITION-01.md", "3c3b2664eb5c31aa29427fffc13b6b8a17ac6f98"),
    ("mating_surface/anchor_node/axm-head-browser-distributed-inference-audition-profile-01.json", "b78eb859fa49bfa3bd7d993e4788af0cb225e667"),
    ("mating_surface/anchor_node/axm-head-browser-distributed-inference-audition.ps1", "c1007897f73a4a41a3be47635d040d8745bb578e"),
    ("mating_surface/anchor_node/axm_head_browser_distributed_inference_audition.py", "93afd1fd2ac0af290287d4a5aba622835bcf2e28"),
    ("mating_surface/anchor_node/browser_distributed_inference_probe.js", "f8489140c119b8513a7569ff95c3900dc1672496"),
    ("mating_surface/anchor_node/verify_axm_head_browser_distributed_inference_audition.py", "01d55294bff5200b44e58c5489dd61220f3230ce"),
    ("mating_surface/anchor_node/verify_axm_head_browser_distributed_inference_audition_bootstrap.py", "3199e60a885c416d49d8af5607a27f8bbb243333"),
    ("mating_surface/anchor_node/conformance/test_axm_head_browser_distributed_inference_audition.py", "f836be0df843615553b512e6e29103e94f5d016a"),
    ("mating_surface/anchor_node/fixtures/axm-head-browser-distributed-inference-audition-cases-01.json", "eb72bc18745c6808188a04531f5e2ae977dbb94c"),
)
KIT_DEPENDENCIES = (
    "axm-head-browser-distributed-inference-audition-profile-01.json",
    "axm_head_browser_distributed_inference_audition.py",
    "browser_distributed_inference_probe.js",
    "verify_axm_head_browser_distributed_inference_audition.py",
    "verify_axm_head_browser_distributed_inference_audition_bootstrap.py",
)
PUBLIC_KEYS = (
    "actualSupplierQualified",
    "commandAuthority",
    "effectorAuthority",
    "engagementAuthority",
    "missionAuthority",
    "namedHumanConfirmed",
    "packetEvidenceRoot",
    "physicalEstateQualified",
    "physicalExecutionObserved",
    "reasonCodes",
    "schema",
    "seatCount",
    "sourceBindingId",
    "supplierAdmissionReceiptPresent",
    "syntheticConformanceOnly",
    "targetingAuthority",
    "terminal",
    "weaponsAuthority",
)
CLAIM_BOUNDARY = (
    "Supplier-neutral source-qualified preparation for one private two-seat browser audition. "
    "Synthetic fixtures qualify only the packet compiler, generated extension, and independent reconstruction law. "
    "They do not establish a browser launch, endpoint contact, model download, peer connection, inference, physical execution, "
    "supplier qualification, physical Estate qualification, or any mission, command, targeting, engagement, effector, or weapons authority."
)
REASON_ORDER = (
    "ONE_SEAT_SUBSTITUTION",
    "SEAT_REPLAYED",
    "SEAT_CAPTURE_HELD",
    "NONPHYSICAL_SOURCE_KIND",
    "MIXED_SOURCE_KIND",
    "DUPLICATE_PHYSICAL_MEMBER_EVIDENCE",
    "CROSS_SEAT_MEMBER_SET_DISAGREEMENT",
    "PROBE_BINDING_DISAGREEMENT",
    "INTERFACE_BINDING_DISAGREEMENT",
    "MODEL_DENOMINATOR_DISAGREEMENT",
    "TOPOLOGY_DISAGREEMENT",
    "ACTIVATION_TRANSPORT_DISAGREEMENT",
    "PERFORMANCE_DENOMINATOR_DISAGREEMENT",
    "OUTPUT_DISAGREEMENT",
    "PRIVACY_DECLARATION_DISAGREEMENT",
    "NAMED_HUMAN_CONFIRMATION_MISSING",
)
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
CONTENT_ID_RE = re.compile(r"^[a-z0-9]+_[0-9a-f]{64}$")
WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")
MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_SOURCE_BYTES = 4 * 1024 * 1024
PRIVATE_ADDRESS_RE = re.compile(
    r"(?:^|[^0-9])(?:10\.(?:\d{1,3}\.){2}\d{1,3}|192\.168\.(?:\d{1,3}\.)\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.(?:\d{1,3}\.)\d{1,3})(?:$|[^0-9])"
)
FORBIDDEN_PUBLIC_KEYS = {
    "prompt",
    "prompttext",
    "completion",
    "completiontext",
    "tokentext",
    "sdp",
    "iceaddress",
    "candidateaddress",
    "devicelabel",
    "rawurl",
    "modelurl",
    "authorization",
    "password",
    "credential",
    "hostname",
    "operatoridentity",
    "privatepath",
    "evidencebody",
    "evidencefilename",
    "endpoint",
}


class PacketError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise PacketError(code, message)


def exact_keys(value: dict[str, Any], expected: set[str], code: str) -> None:
    observed = set(value) if isinstance(value, dict) else set()
    require(observed == expected, code, f"expected={sorted(expected)} observed={sorted(observed)}")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def pretty_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_ref(value: Any) -> str:
    data = value if isinstance(value, bytes) else canonical_bytes(value)
    return "sha256:" + sha256_bytes(data)


def content_id(prefix: str, value: Any) -> str:
    return prefix + "_" + sha256_bytes(canonical_bytes(value))


def is_sha256_ref(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None



def lexical_absolute(path: str | Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def is_linkish(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        junction = getattr(path, "is_junction", None)
        if callable(junction) and junction():
            return True
        metadata = path.lstat()
    except (FileNotFoundError, OSError, ValueError):
        return False
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(reparse and getattr(metadata, "st_file_attributes", 0) & reparse)


def assert_unlinked_coordinate(path: str | Path, code: str = "UNSAFE_LINK") -> Path:
    absolute = lexical_absolute(path)
    for candidate in reversed((absolute, *absolute.parents)):
        if candidate.exists() or candidate.is_symlink():
            require(not is_linkish(candidate), code, str(candidate))
    return absolute


def secure_read_bytes(
    path: str | Path,
    *,
    maximum_bytes: int = MAX_JSON_BYTES,
    expected_bytes: int | None = None,
    expected_sha256: str | None = None,
    code: str = "FILE_READ_REFUSED",
) -> bytes:
    absolute = assert_unlinked_coordinate(path)
    try:
        before = absolute.lstat()
    except OSError as exc:
        raise PacketError("REQUIRED_FILE_MISSING", f"{absolute}: {exc}") from exc
    require(stat.S_ISREG(before.st_mode), "REGULAR_FILE_REQUIRED", str(absolute))
    limit = expected_bytes if expected_bytes is not None else maximum_bytes
    require(isinstance(limit, int) and 0 <= limit <= maximum_bytes, "FILE_SIZE_INVALID", f"{absolute}: {limit}")
    if expected_bytes is not None:
        require(before.st_size == expected_bytes, "FILE_SIZE_MISMATCH", f"{absolute}: expected={expected_bytes} observed={before.st_size}")
    else:
        require(before.st_size <= maximum_bytes, "FILE_TOO_LARGE", f"{absolute}: {before.st_size}")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(absolute, flags)
    except OSError as exc:
        raise PacketError(code, f"{absolute}: {exc}") from exc
    try:
        opened = os.fstat(descriptor)
        require(stat.S_ISREG(opened.st_mode), "REGULAR_FILE_REQUIRED", str(absolute))
        chunks: list[bytes] = []
        remaining = limit + 1
        while remaining > 0:
            chunk = os.read(descriptor, min(65536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
        after_open = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    require(len(data) <= limit, "FILE_TOO_LARGE", f"{absolute}: {len(data)}")
    require(opened.st_size == after_open.st_size == len(data), "FILE_CHANGED_DURING_READ", str(absolute))
    try:
        after_path = absolute.lstat()
    except OSError as exc:
        raise PacketError("FILE_CHANGED_DURING_READ", f"{absolute}: {exc}") from exc
    require(
        before.st_size == after_path.st_size == len(data)
        and getattr(before, "st_mtime_ns", None) == getattr(after_path, "st_mtime_ns", None),
        "FILE_CHANGED_DURING_READ",
        str(absolute),
    )
    assert_unlinked_coordinate(absolute)
    if expected_sha256 is not None:
        require(sha256_ref(data) == expected_sha256, "SOURCE_BINDING_MISMATCH", f"{absolute}: expected={expected_sha256} observed={sha256_ref(data)}")
    return data


def load_object(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(secure_read_bytes(path).decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PacketError("JSON_UNAVAILABLE", f"{path}: {exc}") from exc
    require(isinstance(value, dict), "JSON_OBJECT_REQUIRED", str(path))
    return value




def ensure_unlinked_parent(path: Path) -> None:
    parent = lexical_absolute(path).parent
    assert_unlinked_coordinate(parent)
    parent.mkdir(parents=True, exist_ok=True)
    assert_unlinked_coordinate(parent)
    require(parent.is_dir(), "OUTPUT_PARENT_INVALID", str(parent))


def write_new(path: Path, data: bytes) -> None:
    absolute = lexical_absolute(path)
    ensure_unlinked_parent(absolute)
    if absolute.exists() or absolute.is_symlink():
        require(not is_linkish(absolute), "OUTPUT_COLLISION", str(absolute))
        existing = secure_read_bytes(absolute, maximum_bytes=max(MAX_SOURCE_BYTES, len(data)), expected_bytes=len(data))
        require(existing == data, "OUTPUT_COLLISION", str(absolute))
        return
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(absolute, flags, 0o600)
    except FileExistsError:
        existing = secure_read_bytes(absolute, maximum_bytes=max(MAX_SOURCE_BYTES, len(data)), expected_bytes=len(data))
        require(existing == data, "OUTPUT_COLLISION", str(absolute))
        return
    except OSError as exc:
        raise PacketError("OUTPUT_WRITE_REFUSED", f"{absolute}: {exc}") from exc
    try:
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            require(written > 0, "OUTPUT_WRITE_REFUSED", str(absolute))
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    assert_unlinked_coordinate(absolute)
    require(secure_read_bytes(absolute, maximum_bytes=max(MAX_SOURCE_BYTES, len(data)), expected_bytes=len(data)) == data, "OUTPUT_WRITE_MISMATCH", str(absolute))



def write_derived(path: Path, data: bytes) -> None:
    absolute = lexical_absolute(path)
    ensure_unlinked_parent(absolute)
    if absolute.exists() or absolute.is_symlink():
        require(not is_linkish(absolute), "DERIVED_OUTPUT_LINKED", str(absolute))
        require(absolute.is_file(), "DERIVED_OUTPUT_INVALID", str(absolute))
    temporary = absolute.with_name(f".{absolute.name}.tmp-{os.getpid()}-{hashlib.sha256(data).hexdigest()[:12]}")
    require(not temporary.exists() and not temporary.is_symlink(), "DERIVED_OUTPUT_COLLISION", str(temporary))
    write_new(temporary, data)
    try:
        os.replace(temporary, absolute)
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise PacketError("DERIVED_OUTPUT_REPLACE_REFUSED", f"{absolute}: {exc}") from exc
    require(secure_read_bytes(absolute, maximum_bytes=max(MAX_SOURCE_BYTES, len(data)), expected_bytes=len(data)) == data, "DERIVED_OUTPUT_MISMATCH", str(absolute))


def normalized_key(value: Any) -> str:
    return str(value).replace("_", "").replace("-", "").lower()


def public_leak(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if normalized_key(key) in FORBIDDEN_PUBLIC_KEYS or public_leak(child):
                return True
        return False
    if isinstance(value, list):
        return any(public_leak(child) for child in value)
    if isinstance(value, str):
        lowered = value.lower()
        return (
            "://" in value
            or "bearer " in lowered
            or "begin private key" in lowered
            or PRIVATE_ADDRESS_RE.search(value) is not None
            or value.startswith("/")
            or value.startswith("\\\\")
            or WINDOWS_ABSOLUTE_RE.match(value) is not None
        )
    return False


def relative_safe(value: str) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    pure = Path(value)
    return not pure.is_absolute() and all(part not in {"", ".", ".."} for part in pure.parts)



def resolve_inside(root: Path, relative: str) -> Path:
    require(relative_safe(relative), "UNSAFE_PATH", relative)
    lexical_root = assert_unlinked_coordinate(root)
    path = lexical_absolute(lexical_root.joinpath(*relative.split("/")))
    require(path_is_within(path, lexical_root), "UNSAFE_PATH", relative)
    assert_unlinked_coordinate(path)
    return path




def path_is_within(path: Path, root: Path) -> bool:
    absolute_path = lexical_absolute(path)
    absolute_root = lexical_absolute(root)
    try:
        common = os.path.commonpath((str(absolute_path), str(absolute_root)))
    except ValueError:
        return False
    return os.path.normcase(common) == os.path.normcase(str(absolute_root))




def assert_regular_no_symlink(path: Path, code: str = "UNSAFE_LINK") -> None:
    absolute = assert_unlinked_coordinate(path, code)
    require(absolute.exists(), "REQUIRED_FILE_MISSING", str(absolute))
    try:
        metadata = absolute.lstat()
    except OSError as exc:
        raise PacketError("REQUIRED_FILE_MISSING", f"{absolute}: {exc}") from exc
    require(stat.S_ISREG(metadata.st_mode), "REGULAR_FILE_REQUIRED", str(absolute))




def load_module_from_bytes(path: Path, name: str, source: bytes) -> Any:
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = ""
    previous = sys.modules.get(name)
    sys.modules[name] = module
    try:
        exec(compile(source, str(path), "exec"), module.__dict__)
    except Exception:
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous
        raise
    return module




def source_binding_id(profile: dict[str, Any]) -> str:
    binding = {
        "profileId": profile["profileId"],
        "admittedAudition": copy.deepcopy(profile["admittedAudition"]),
        "commands": copy.deepcopy(profile["commands"]),
        "terminalStates": copy.deepcopy(profile["terminalStates"]),
        "seatCount": profile["seatCount"],
        "physicalMemberEvidenceCount": profile["physicalMemberEvidenceCount"],
        "publicProjectionAllowedKeys": copy.deepcopy(profile["publicProjectionAllowedKeys"]),
        "extensionContract": copy.deepcopy(profile["extensionContract"]),
        "confirmationPolicy": copy.deepcopy(profile["confirmationPolicy"]),
        "kitSourceBindings": copy.deepcopy(profile["kitSourceBindings"]),
        "packetSourceBindings": copy.deepcopy(profile["packetSourceBindings"]),
        "claimBoundary": profile["claimBoundary"],
    }
    return content_id("axmbrowserphysicalpacketsource", binding)



def validate_profile(path: str | Path) -> dict[str, Any]:
    profile = load_object(path)
    exact_keys(
        profile,
        {
            "admittedAudition",
            "claimBoundary",
            "commands",
            "confirmationPolicy",
            "extensionContract",
            "fixtureCaseIds",
            "fixtureTerminalCounts",
            "issueRef",
            "kitSourceBindings",
            "packetSourceBindings",
            "physicalMemberEvidenceCount",
            "profileId",
            "publicProjectionAllowedKeys",
            "schema",
            "seatCount",
            "sourceMembers",
            "status",
            "terminalStates",
        },
        "PROFILE_KEYS_INVALID",
    )
    require(profile["schema"] == PROFILE_SCHEMA, "PROFILE_SCHEMA_INVALID", str(profile["schema"]))
    require(profile["profileId"] == PROFILE_ID, "PROFILE_ID_INVALID", str(profile["profileId"]))
    require(profile["issueRef"] == ISSUE_REF, "ISSUE_REF_INVALID", str(profile["issueRef"]))
    require(profile["status"] == "candidate_source_only", "PROFILE_STATUS_INVALID", str(profile["status"]))
    require(tuple(profile["commands"]) == COMMANDS, "COMMAND_DENOMINATOR_INVALID", str(profile["commands"]))
    require(tuple(profile["terminalStates"]) == TERMINALS, "TERMINAL_DENOMINATOR_INVALID", str(profile["terminalStates"]))
    require(profile["seatCount"] == 2, "SEAT_DENOMINATOR_INVALID", str(profile["seatCount"]))
    require(profile["physicalMemberEvidenceCount"] == 2, "PHYSICAL_MEMBER_DENOMINATOR_INVALID", str(profile["physicalMemberEvidenceCount"]))
    require(tuple(profile["sourceMembers"]) == SOURCE_MEMBERS, "SOURCE_MEMBER_DENOMINATOR_INVALID", str(profile["sourceMembers"]))
    require(tuple(profile["publicProjectionAllowedKeys"]) == PUBLIC_KEYS, "PUBLIC_KEY_DENOMINATOR_INVALID", str(profile["publicProjectionAllowedKeys"]))
    require(profile["claimBoundary"] == CLAIM_BOUNDARY, "CLAIM_BOUNDARY_INVALID", str(profile["claimBoundary"]))

    binding = profile["admittedAudition"]
    exact_keys(
        binding,
        {
            "admissionCommit",
            "admissionTree",
            "candidateCommit",
            "interface",
            "probeSha256",
            "profileId",
            "sourceMembers",
        },
        "ADMITTED_BINDING_KEYS_INVALID",
    )
    require(
        (
            binding["admissionCommit"],
            binding["admissionTree"],
            binding["candidateCommit"],
            binding["interface"],
            binding["probeSha256"],
            binding["profileId"],
        )
        == (
            ADMITTED_COMMIT,
            ADMITTED_TREE,
            ADMITTED_CANDIDATE_COMMIT,
            INTERFACE,
            PROBE_SHA256_REF,
            ADMITTED_AUDITION_PROFILE_ID,
        ),
        "ADMITTED_SOURCE_FLOOR_DRIFT",
        "admitted browser-audition source binding drifted",
    )
    observed_members = tuple((row.get("path"), row.get("gitBlobSha")) for row in binding["sourceMembers"] if isinstance(row, dict))
    require(observed_members == ADMITTED_SOURCE_MEMBERS, "ADMITTED_SOURCE_MEMBER_DRIFT", str(observed_members))
    for row in binding["sourceMembers"]:
        exact_keys(row, {"gitBlobSha", "path"}, "ADMITTED_SOURCE_MEMBER_KEYS_INVALID")
        require(relative_safe(row["path"]) and re.fullmatch(r"[0-9a-f]{40}", row["gitBlobSha"]) is not None, "ADMITTED_SOURCE_MEMBER_INVALID", str(row))

    extension = profile["extensionContract"]
    require(
        extension
        == {
            "manifestVersion": 3,
            "runAt": "document_start",
            "script": "browser_distributed_inference_probe.js",
            "world": "MAIN",
        },
        "EXTENSION_CONTRACT_INVALID",
        str(extension),
    )
    confirmation = profile["confirmationPolicy"]
    require(
        confirmation
        == {
            "actorClass": "named-human",
            "actorEvidenceRequired": True,
            "decision": "CONFIRM_OBSERVED_ROUTE_CANDIDATE",
            "futureSkewMs": 300000,
            "maximumValidityMs": 86400000,
        },
        "CONFIRMATION_POLICY_INVALID",
        str(confirmation),
    )
    for key in ("kitSourceBindings", "packetSourceBindings"):
        rows = profile[key]
        require(isinstance(rows, list) and rows, "SOURCE_BINDING_DENOMINATOR_INVALID", key)
        seen: set[str] = set()
        for row in rows:
            exact_keys(row, {"bytes", "path", "sha256"}, "SOURCE_BINDING_KEYS_INVALID")
            require(
                relative_safe(row["path"])
                and isinstance(row["bytes"], int)
                and 0 < row["bytes"] <= MAX_SOURCE_BYTES
                and is_sha256_ref(row["sha256"]),
                "SOURCE_BINDING_INVALID",
                str(row),
            )
            require(row["path"] not in seen, "SOURCE_BINDING_DUPLICATE", row["path"])
            seen.add(row["path"])
    require(
        tuple(Path(row["path"]).name for row in profile["kitSourceBindings"]) == KIT_DEPENDENCIES,
        "KIT_SOURCE_BINDING_DENOMINATOR_INVALID",
        str(profile["kitSourceBindings"]),
    )
    require(
        tuple(Path(row["path"]).name for row in profile["packetSourceBindings"])
        == (
            "axm-head-browser-physical-audition-controller-template-01.json",
            "axm-head-browser-physical-audition-packet-01.ps1",
            "axm_head_browser_physical_audition_packet_01.py",
            "verify_axm_head_browser_physical_audition_packet_01.py",
            "verify_axm_head_browser_physical_audition_packet_01_bootstrap.py",
        ),
        "PACKET_SOURCE_BINDING_DENOMINATOR_INVALID",
        str(profile["packetSourceBindings"]),
    )
    require(isinstance(profile["fixtureCaseIds"], list) and profile["fixtureCaseIds"], "FIXTURE_CASE_DENOMINATOR_INVALID", "fixtureCaseIds")
    require(len(profile["fixtureCaseIds"]) == len(set(profile["fixtureCaseIds"])), "FIXTURE_CASE_DENOMINATOR_INVALID", str(profile["fixtureCaseIds"]))
    counts = profile["fixtureTerminalCounts"]
    exact_keys(counts, set(TERMINALS), "FIXTURE_TERMINAL_COUNT_KEYS_INVALID")
    require(sum(counts.values()) == len(profile["fixtureCaseIds"]), "FIXTURE_TERMINAL_COUNTS_INVALID", str(counts))
    return profile



def verify_bound_sources(profile: dict[str, Any], root: Path, key: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for binding in profile[key]:
        path = resolve_inside(root, binding["path"])
        data = secure_read_bytes(
            path,
            maximum_bytes=MAX_SOURCE_BYTES,
            expected_bytes=binding["bytes"],
            expected_sha256=binding["sha256"],
        )
        rows.append({"path": binding["path"], "bytes": len(data), "sha256": sha256_ref(data)})
    return rows



def dependency_paths(base: Path | None = None) -> dict[str, Path]:
    root = assert_unlinked_coordinate(base or Path(__file__).parent)
    return {name: root / name for name in KIT_DEPENDENCIES}



def load_admitted_runtime(profile: dict[str, Any], base: Path | None = None) -> tuple[Any, Any, Path]:
    paths = dependency_paths(base)
    bindings = {Path(row["path"]).name: row for row in profile["kitSourceBindings"]}
    measured: dict[str, bytes] = {}
    for name, path in paths.items():
        binding = bindings.get(name)
        require(binding is not None, "SOURCE_BINDING_MISSING", name)
        measured[name] = secure_read_bytes(
            path,
            maximum_bytes=MAX_SOURCE_BYTES,
            expected_bytes=binding["bytes"],
            expected_sha256=binding["sha256"],
        )
    core = load_module_from_bytes(paths["axm_head_browser_distributed_inference_audition.py"], "axm_admitted_audition_core", measured["axm_head_browser_distributed_inference_audition.py"])
    verifier = load_module_from_bytes(paths["verify_axm_head_browser_distributed_inference_audition.py"], "axm_admitted_audition_verifier", measured["verify_axm_head_browser_distributed_inference_audition.py"])
    audition_profile_path = paths["axm-head-browser-distributed-inference-audition-profile-01.json"]
    admitted_profile = core.validate_profile(audition_profile_path)
    require(admitted_profile["profileId"] == ADMITTED_AUDITION_PROFILE_ID, "ADMITTED_PROFILE_INVALID", admitted_profile["profileId"])
    for name, path in paths.items():
        binding = bindings[name]
        secure_read_bytes(path, maximum_bytes=MAX_SOURCE_BYTES, expected_bytes=binding["bytes"], expected_sha256=binding["sha256"])
    return core, verifier, audition_profile_path



def control_member_refs(control: dict[str, Any]) -> tuple[dict[str, str], list[str]]:
    assertions = control.get("memberUniquenessAssertions")
    require(isinstance(assertions, list) and len(assertions) == 2, "PHYSICAL_MEMBER_DENOMINATOR_INVALID", str(assertions))
    mapping: dict[str, str] = {}
    refs: list[str] = []
    for row in assertions:
        require(isinstance(row, dict), "PHYSICAL_MEMBER_ASSERTION_INVALID", str(row))
        exact_keys(row, {"evidenceRef", "physicallyUnique", "probeMemberId"}, "PHYSICAL_MEMBER_ASSERTION_KEYS_INVALID")
        require(isinstance(row["probeMemberId"], str) and row["probeMemberId"].startswith("opaque:") and len(row["probeMemberId"]) > 15, "PHYSICAL_MEMBER_ID_INVALID", str(row["probeMemberId"]))
        require(row["physicallyUnique"] is True, "PHYSICAL_MEMBER_UNIQUENESS_UNPROVED", str(row))
        require(is_sha256_ref(row["evidenceRef"]), "PHYSICAL_MEMBER_EVIDENCE_INVALID", str(row["evidenceRef"]))
        require(row["probeMemberId"] not in mapping, "PHYSICAL_MEMBER_ID_DUPLICATE", row["probeMemberId"])
        mapping[row["probeMemberId"]] = row["evidenceRef"]
        refs.append(row["evidenceRef"])
    return mapping, sorted(refs)


def hashed_member_id(probe_id: str) -> str:
    return sha256_ref({"probeOpaqueId": probe_id})


def seat_private_projection(capture: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    opaque_map, physical_refs = control_member_refs(control)
    hashed_map = {hashed_member_id(probe): ref for probe, ref in opaque_map.items()}
    members: list[dict[str, Any]] = []
    for row in capture["formation"]["members"]:
        ref = hashed_map.get(row["memberIdHash"])
        require(ref is not None, "CROSS_SEAT_MEMBER_BINDING_INVALID", str(row["memberIdHash"]))
        members.append({"evidenceRef": ref, "pledgedBytes": row["pledgedBytes"], "role": row["role"]})
    layers: list[dict[str, Any]] = []
    for row in capture["model"]["layers"]:
        ref = hashed_map.get(row["memberIdHash"])
        require(ref is not None, "CROSS_SEAT_MODEL_BINDING_INVALID", str(row["memberIdHash"]))
        layers.append(
            {
                "artifactBytes": row["artifactBytes"],
                "artifactDigest": row["artifactDigest"],
                "evidenceRef": ref,
                "layerEnd": row["layerEnd"],
                "layerStart": row["layerStart"],
            }
        )
    channels = capture["transport"]["activationChannels"]
    return {
        "physicalMemberEvidenceRefs": physical_refs,
        "probeSha256": capture["instrumentation"]["probeSha256"],
        "interface": capture["workUnit"]["requiredInterface"],
        "model": {
            "artifactTotalBytes": capture["model"]["artifactTotalBytes"],
            "boundModelId": capture["model"]["boundModelId"],
            "claimedId": capture["model"]["claimedId"],
            "layers": sorted(layers, key=lambda row: (row["layerStart"], row["evidenceRef"])),
            "members": sorted(members, key=lambda row: row["evidenceRef"]),
            "modelCapacityBytes": capture["formation"]["modelCapacityBytes"],
            "observedManifestDigest": capture["model"]["observedManifestDigest"],
            "partitionMode": capture["formation"]["partitionMode"],
        },
        "topology": {
            "activationChannelCount": len(channels),
            "allOrdered": all(row["ordered"] is True for row in channels),
            "allReliable": all(row["maxRetransmits"] is None and row["maxPacketLifeTime"] is None for row in channels),
            "allTransferredBytes": all((row["bytesSent"] + row["bytesReceived"]) > 0 for row in channels),
            "peerConnectionCount": capture["transport"]["peerConnectionCount"],
            "selectedCandidatePairClass": capture["transport"]["selectedCandidatePairClass"],
            "selectedCandidatePairObserved": capture["transport"]["selectedCandidatePairObserved"],
        },
        "performance": {
            "outputTokenCount": capture["performance"]["outputTokenCount"],
            "promptTokenCount": capture["performance"]["promptTokenCount"],
            "tokenMarkCount": len(capture["performance"]["tokenMarks"]),
        },
        "equivalence": copy.deepcopy(capture["equivalence"]),
        "privacy": copy.deepcopy(capture["privacy"]),
    }


def verify_seat(raw: dict[str, Any], control: dict[str, Any], profile: dict[str, Any], *, base: Path | None = None) -> dict[str, Any]:
    require(
        isinstance(control, dict) and control.get("sourceKind") in {"synthetic-live-capture", "physical-private-local"},
        "NONPHYSICAL_SOURCE_KIND",
        str(control.get("sourceKind") if isinstance(control, dict) else type(control)),
    )
    core, verifier, audition_profile_path = load_admitted_runtime(profile, base)
    try:
        admitted_profile = core.validate_profile(audition_profile_path)
        capture, materialization = core.materialize_probe_capture(copy.deepcopy(raw), copy.deepcopy(control), admitted_profile)
        decision = core.assess_capture(copy.deepcopy(capture), admitted_profile)
        verdict = verifier.verify(admitted_profile, capture, decision, raw=raw, control=control)
    except Exception as exc:
        code = getattr(exc, "code", "ADMITTED_CAPTURE_REFUSED")
        message = getattr(exc, "message", str(exc))
        raise PacketError(str(code), str(message)) from exc
    require(verdict.get("status") == "PASS", "ADMITTED_VERIFIER_REFUSED", str(verdict))
    return {
        "raw": copy.deepcopy(raw),
        "control": copy.deepcopy(control),
        "capture": capture,
        "materialization": materialization,
        "decision": decision,
        "verdict": verdict,
        "projection": seat_private_projection(capture, control),
    }


def confirmation_id(value: dict[str, Any]) -> str:
    normalized = copy.deepcopy(value)
    normalized["confirmationId"] = None
    return content_id("axmbrowserhumanconfirmation", normalized)


def validate_confirmation(
    confirmation: dict[str, Any],
    profile: dict[str, Any],
    *,
    evidence_root: str,
    seat_capture_digests: list[str],
    physical_refs: list[str],
    now_ms: int,
) -> dict[str, Any]:
    exact_keys(
        confirmation,
        {
            "actorClass",
            "actorEvidenceRef",
            "authority",
            "confirmationId",
            "decision",
            "evidenceRoot",
            "expiresAtUnixMs",
            "issuedAtUnixMs",
            "physicalMemberEvidenceRefs",
            "schema",
            "seatCaptureDigests",
        },
        "CONFIRMATION_KEYS_INVALID",
    )
    policy = profile["confirmationPolicy"]
    require(confirmation["schema"] == CONFIRMATION_SCHEMA, "CONFIRMATION_SCHEMA_INVALID", str(confirmation["schema"]))
    require(confirmation["actorClass"] == policy["actorClass"], "CONFIRMATION_ACTOR_INVALID", str(confirmation["actorClass"]))
    require(policy["actorEvidenceRequired"] is True and is_sha256_ref(confirmation["actorEvidenceRef"]), "CONFIRMATION_ACTOR_EVIDENCE_INVALID", str(confirmation["actorEvidenceRef"]))
    require(confirmation["actorEvidenceRef"] not in set(seat_capture_digests) | set(physical_refs), "CONFIRMATION_ACTOR_EVIDENCE_REUSED", str(confirmation["actorEvidenceRef"]))
    require(confirmation["decision"] == policy["decision"], "CONFIRMATION_DECISION_INVALID", str(confirmation["decision"]))
    require(confirmation["authority"] == "none", "AUTHORITY_PROMOTED", str(confirmation["authority"]))
    require(confirmation["evidenceRoot"] == evidence_root, "CONFIRMATION_EVIDENCE_ROOT_MISMATCH", str(confirmation["evidenceRoot"]))
    require(confirmation["seatCaptureDigests"] == seat_capture_digests, "CONFIRMATION_SEAT_BINDING_MISMATCH", str(confirmation["seatCaptureDigests"]))
    require(confirmation["physicalMemberEvidenceRefs"] == physical_refs, "CONFIRMATION_MEMBER_BINDING_MISMATCH", str(confirmation["physicalMemberEvidenceRefs"]))
    issued = confirmation["issuedAtUnixMs"]
    expires = confirmation["expiresAtUnixMs"]
    require(isinstance(issued, int) and isinstance(expires, int), "CONFIRMATION_TIME_INVALID", f"issued={issued} expires={expires}")
    require(issued <= now_ms + policy["futureSkewMs"], "CONFIRMATION_NOT_CURRENT", f"issued={issued} now={now_ms}")
    require(now_ms <= expires, "CONFIRMATION_EXPIRED", f"expires={expires} now={now_ms}")
    require(0 < expires - issued <= policy["maximumValidityMs"], "CONFIRMATION_VALIDITY_INVALID", f"issued={issued} expires={expires}")
    require(isinstance(confirmation["confirmationId"], str) and CONTENT_ID_RE.fullmatch(confirmation["confirmationId"]) is not None, "CONFIRMATION_ID_INVALID", str(confirmation["confirmationId"]))
    require(confirmation["confirmationId"] == confirmation_id(confirmation), "CONFIRMATION_ID_MISMATCH", str(confirmation["confirmationId"]))
    return confirmation


def generated_public(decision: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    value = {
        "schema": PACKET_PUBLIC_SCHEMA,
        "terminal": decision["terminal"],
        "reasonCodes": decision["reasonCodes"],
        "sourceBindingId": decision["sourceBindingId"],
        "packetEvidenceRoot": decision["packetEvidenceRoot"],
        "seatCount": decision["seatCount"],
        "namedHumanConfirmed": decision["namedHumanConfirmed"],
        "syntheticConformanceOnly": decision["syntheticConformanceOnly"],
        "physicalExecutionObserved": decision["physicalExecutionObserved"],
        "actualSupplierQualified": False,
        "supplierAdmissionReceiptPresent": False,
        "physicalEstateQualified": False,
        "missionAuthority": "none",
        "commandAuthority": "none",
        "targetingAuthority": "none",
        "engagementAuthority": "none",
        "effectorAuthority": "none",
        "weaponsAuthority": "none",
    }
    require(set(value) == set(profile["publicProjectionAllowedKeys"]), "PUBLIC_PROJECTION_DENOMINATOR_INVALID", str(sorted(value)))
    require(not public_leak(value), "PUBLIC_PROJECTION_LEAK", "generated projection contains private material")
    return value


def reconstruct_packet(
    profile: dict[str, Any],
    seats: list[dict[str, Any]],
    confirmation: dict[str, Any] | None,
    *,
    now_ms: int,
    base: Path | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    require(isinstance(seats, list), "SEAT_SET_INVALID", str(type(seats)))
    verified: list[dict[str, Any]] = []
    if len(seats) == 0:
        require(confirmation is None, "CONFIRMATION_NOT_APPLICABLE", "named-human confirmation is not accepted before any seat evidence exists")
        evidence = {
            "sourceBindingId": source_binding_id(profile),
            "seatReceipts": [],
            "physicalMemberEvidenceRefs": [],
            "modelDenominatorDigest": None,
            "topologyDigest": None,
            "performanceDenominatorDigest": None,
            "outputDigest": None,
            "privacyDigest": None,
        }
        root = sha256_ref(evidence)
        body = {
            "schema": PACKET_DECISION_SCHEMA,
            "terminal": "PREPARED_NOT_EXECUTED",
            "reasonCodes": [],
            "sourceBindingId": source_binding_id(profile),
            "packetEvidenceRoot": root,
            "seatCount": 0,
            "seatReceipts": [],
            "physicalMemberEvidenceRefs": [],
            "modelDenominatorDigest": None,
            "topologyDigest": None,
            "performanceDenominatorDigest": None,
            "outputDigest": None,
            "privacyDigest": None,
            "namedHumanConfirmationId": None,
            "namedHumanActorEvidenceRef": None,
            "namedHumanConfirmed": False,
            "syntheticConformanceOnly": False,
            "physicalExecutionObserved": False,
            "actualSupplierQualified": False,
            "supplierAdmissionReceiptPresent": False,
            "physicalEstateQualified": False,
            "missionAuthority": "none",
            "commandAuthority": "none",
            "targetingAuthority": "none",
            "engagementAuthority": "none",
            "effectorAuthority": "none",
            "weaponsAuthority": "none",
            "publicProjection": None,
            "packetDecisionId": None,
        }
        body["publicProjection"] = generated_public(body, profile)
        body["packetDecisionId"] = content_id("axmbrowserpacketdecision", {**body, "packetDecisionId": None})
        return body, verified

    violations: set[str] = set()
    if len(seats) != profile["seatCount"]:
        violations.add("ONE_SEAT_SUBSTITUTION")
    require(len(seats) <= profile["seatCount"], "SEAT_DENOMINATOR_EXCEEDED", str(len(seats)))

    for index, seat in enumerate(seats):
        require(isinstance(seat, dict), "SEAT_RECORD_INVALID", str(index))
        exact_keys(seat, {"control", "raw", "seatId"}, "SEAT_RECORD_KEYS_INVALID")
        require(seat["seatId"] == SEAT_IDS[index], "SEAT_ORDER_INVALID", str(seat["seatId"]))
        verified.append(verify_seat(seat["raw"], seat["control"], profile, base=base))

    seat_receipts: list[dict[str, Any]] = []
    for seat_id, row in zip(SEAT_IDS, verified):
        decision = row["decision"]
        if decision["terminal"] != "OBSERVED_ROUTE_CANDIDATE" or decision["reasonCodes"]:
            violations.add("SEAT_CAPTURE_HELD")
        seat_receipts.append(
            {
                "seatId": seat_id,
                "rawEvidenceRef": row["capture"]["rawEvidenceRef"],
                "controlEvidenceRef": row["capture"]["controlEvidenceRef"],
                "captureDigest": decision["captureDigest"],
                "observationReceiptDigest": decision["observationReceiptDigest"],
                "admittedVerifierDecisionDigest": row["verdict"]["decisionDigest"],
            }
        )

    source_kinds = [row["capture"]["sourceKind"] for row in verified]
    if len(set(source_kinds)) > 1:
        violations.add("MIXED_SOURCE_KIND")
    synthetic = bool(source_kinds) and all(kind == "synthetic-live-capture" for kind in source_kinds)
    physical = bool(source_kinds) and all(kind == "physical-private-local" for kind in source_kinds)
    if not (synthetic or physical):
        violations.add("NONPHYSICAL_SOURCE_KIND")
    if synthetic and any(row["capture"]["syntheticConformanceOnly"] is not True for row in verified):
        violations.add("NONPHYSICAL_SOURCE_KIND")
    if physical and any(row["capture"]["syntheticConformanceOnly"] is not False for row in verified):
        violations.add("NONPHYSICAL_SOURCE_KIND")

    if len(verified) == 2:
        if (
            verified[0]["capture"]["rawEvidenceRef"] == verified[1]["capture"]["rawEvidenceRef"]
            or verified[0]["capture"]["controlEvidenceRef"] == verified[1]["capture"]["controlEvidenceRef"]
            or seat_receipts[0]["captureDigest"] == seat_receipts[1]["captureDigest"]
        ):
            violations.add("SEAT_REPLAYED")

        projections = [row["projection"] for row in verified]
        refs_a = projections[0]["physicalMemberEvidenceRefs"]
        refs_b = projections[1]["physicalMemberEvidenceRefs"]
        if len(refs_a) != 2 or len(set(refs_a)) != 2 or len(refs_b) != 2 or len(set(refs_b)) != 2:
            violations.add("DUPLICATE_PHYSICAL_MEMBER_EVIDENCE")
        if refs_a != refs_b:
            violations.add("CROSS_SEAT_MEMBER_SET_DISAGREEMENT")
        if projections[0]["probeSha256"] != PROBE_SHA256_REF or projections[1]["probeSha256"] != PROBE_SHA256_REF:
            violations.add("PROBE_BINDING_DISAGREEMENT")
        if projections[0]["interface"] != INTERFACE or projections[1]["interface"] != INTERFACE:
            violations.add("INTERFACE_BINDING_DISAGREEMENT")
        if projections[0]["model"] != projections[1]["model"]:
            violations.add("MODEL_DENOMINATOR_DISAGREEMENT")
        topology_a, topology_b = projections[0]["topology"], projections[1]["topology"]
        if (
            topology_a["selectedCandidatePairObserved"] is not True
            or topology_b["selectedCandidatePairObserved"] is not True
            or topology_a["selectedCandidatePairClass"] != topology_b["selectedCandidatePairClass"]
            or topology_a["peerConnectionCount"] != topology_b["peerConnectionCount"]
        ):
            violations.add("TOPOLOGY_DISAGREEMENT")
        if (
            topology_a["activationChannelCount"] != topology_b["activationChannelCount"]
            or not topology_a["allOrdered"]
            or not topology_b["allOrdered"]
            or not topology_a["allReliable"]
            or not topology_b["allReliable"]
            or not topology_a["allTransferredBytes"]
            or not topology_b["allTransferredBytes"]
        ):
            violations.add("ACTIVATION_TRANSPORT_DISAGREEMENT")
        if projections[0]["performance"] != projections[1]["performance"]:
            violations.add("PERFORMANCE_DENOMINATOR_DISAGREEMENT")
        eq_a, eq_b = projections[0]["equivalence"], projections[1]["equivalence"]
        if (
            eq_a["match"] is not True
            or eq_b["match"] is not True
            or eq_a["referenceDigest"] != eq_a["candidateDigest"]
            or eq_b["referenceDigest"] != eq_b["candidateDigest"]
            or eq_a["referenceDigest"] != eq_b["referenceDigest"]
            or eq_a["promptTokenCount"] != eq_b["promptTokenCount"]
            or eq_a["outputTokenCount"] != eq_b["outputTokenCount"]
        ):
            violations.add("OUTPUT_DISAGREEMENT")
        privacy_a, privacy_b = projections[0]["privacy"], projections[1]["privacy"]
        if (
            privacy_a["declarationPresent"] is not True
            or privacy_b["declarationPresent"] is not True
            or privacy_a["claimsEndToEndConfidentiality"] is not False
            or privacy_b["claimsEndToEndConfidentiality"] is not False
            or privacy_a["scope"] != "browser-observed-network-surface-only"
            or privacy_b["scope"] != "browser-observed-network-surface-only"
        ):
            violations.add("PRIVACY_DECLARATION_DISAGREEMENT")

    physical_refs = verified[0]["projection"]["physicalMemberEvidenceRefs"] if verified else []
    model_digest = sha256_ref(verified[0]["projection"]["model"]) if verified else None
    topology_digest = sha256_ref(verified[0]["projection"]["topology"]) if verified else None
    performance_digest = sha256_ref(verified[0]["projection"]["performance"]) if verified else None
    output_digest = sha256_ref(verified[0]["projection"]["equivalence"]) if verified else None
    privacy_digest = sha256_ref(verified[0]["projection"]["privacy"]) if verified else None
    evidence = {
        "sourceBindingId": source_binding_id(profile),
        "seatReceipts": seat_receipts,
        "physicalMemberEvidenceRefs": physical_refs,
        "modelDenominatorDigest": model_digest,
        "topologyDigest": topology_digest,
        "performanceDenominatorDigest": performance_digest,
        "outputDigest": output_digest,
        "privacyDigest": privacy_digest,
    }
    evidence_root = sha256_ref(evidence)

    named_human_confirmed = False
    confirmation_id_value: str | None = None
    confirmation_actor_evidence_ref: str | None = None
    if physical and len(verified) == 2 and not violations:
        if confirmation is None:
            violations.add("NAMED_HUMAN_CONFIRMATION_MISSING")
        else:
            validate_confirmation(
                confirmation,
                profile,
                evidence_root=evidence_root,
                seat_capture_digests=[row["captureDigest"] for row in seat_receipts],
                physical_refs=physical_refs,
                now_ms=now_ms,
            )
            named_human_confirmed = True
            confirmation_id_value = confirmation["confirmationId"]
            confirmation_actor_evidence_ref = confirmation["actorEvidenceRef"]
    elif confirmation is not None:
        raise PacketError("CONFIRMATION_NOT_APPLICABLE", "named-human confirmation is accepted only for a complete physical-private-local packet")

    ordered_reasons = [code for code in REASON_ORDER if code in violations]
    if synthetic and len(verified) == 2 and not violations:
        terminal = "OBSERVED_ROUTE_CANDIDATE"
    elif physical and len(verified) == 2 and named_human_confirmed and not violations:
        terminal = "OBSERVED_ROUTE_CANDIDATE"
    elif physical and len(verified) == 2 and violations == {"NAMED_HUMAN_CONFIRMATION_MISSING"}:
        terminal = "READY_FOR_NAMED_HUMAN"
        ordered_reasons = ["NAMED_HUMAN_CONFIRMATION_MISSING"]
    elif violations:
        terminal = "HOLD"
    else:
        terminal = "HOLD"

    body = {
        "schema": PACKET_DECISION_SCHEMA,
        "terminal": terminal,
        "reasonCodes": ordered_reasons,
        "sourceBindingId": source_binding_id(profile),
        "packetEvidenceRoot": evidence_root,
        "seatCount": len(verified),
        "seatReceipts": seat_receipts,
        "physicalMemberEvidenceRefs": physical_refs,
        "modelDenominatorDigest": model_digest,
        "topologyDigest": topology_digest,
        "performanceDenominatorDigest": performance_digest,
        "outputDigest": output_digest,
        "privacyDigest": privacy_digest,
        "namedHumanConfirmationId": confirmation_id_value,
        "namedHumanActorEvidenceRef": confirmation_actor_evidence_ref,
        "namedHumanConfirmed": named_human_confirmed,
        "syntheticConformanceOnly": synthetic,
        "physicalExecutionObserved": bool(physical and named_human_confirmed and terminal == "OBSERVED_ROUTE_CANDIDATE"),
        "actualSupplierQualified": False,
        "supplierAdmissionReceiptPresent": False,
        "physicalEstateQualified": False,
        "missionAuthority": "none",
        "commandAuthority": "none",
        "targetingAuthority": "none",
        "engagementAuthority": "none",
        "effectorAuthority": "none",
        "weaponsAuthority": "none",
        "publicProjection": None,
        "packetDecisionId": None,
    }
    body["publicProjection"] = generated_public(body, profile)
    body["packetDecisionId"] = content_id("axmbrowserpacketdecision", {**body, "packetDecisionId": None})
    return body, verified


def apply_mutations(value: Any, mutations: list[dict[str, Any]]) -> Any:
    result = copy.deepcopy(value)
    for mutation in mutations:
        require(isinstance(mutation, dict), "FIXTURE_MUTATION_INVALID", str(mutation))
        exact_keys(mutation, {"path", "value"}, "FIXTURE_MUTATION_KEYS_INVALID")
        parts = mutation["path"]
        require(isinstance(parts, list) and parts, "FIXTURE_MUTATION_PATH_INVALID", str(parts))
        cursor = result
        for part in parts[:-1]:
            try:
                cursor = cursor[part]
            except (KeyError, IndexError, TypeError) as exc:
                raise PacketError("FIXTURE_MUTATION_PATH_INVALID", str(parts)) from exc
        try:
            cursor[parts[-1]] = copy.deepcopy(mutation["value"])
        except (KeyError, IndexError, TypeError) as exc:
            raise PacketError("FIXTURE_MUTATION_PATH_INVALID", str(parts)) from exc
    return result


def validate_fixture_catalog(path: str | Path, profile: dict[str, Any], *, base: Path | None = None) -> dict[str, Any]:
    catalog = load_object(path)
    exact_keys(catalog, {"bases", "cases", "schema"}, "FIXTURE_KEYS_INVALID")
    require(catalog["schema"] == FIXTURE_SCHEMA, "FIXTURE_SCHEMA_INVALID", str(catalog["schema"]))
    require(isinstance(catalog["bases"], dict) and catalog["bases"], "FIXTURE_BASES_INVALID", "bases")
    require(isinstance(catalog["cases"], list), "FIXTURE_CASES_INVALID", "cases")
    ids: list[str] = []
    counts = {terminal: 0 for terminal in TERMINALS}
    expanded: list[dict[str, Any]] = []
    for row in catalog["cases"]:
        exact_keys(row, {"base", "caseId", "expectedReasonCodes", "expectedTerminal", "mutations"}, "FIXTURE_CASE_KEYS_INVALID")
        require(row["base"] in catalog["bases"], "FIXTURE_BASE_REF_INVALID", str(row["base"]))
        packet = apply_mutations(catalog["bases"][row["base"]], row["mutations"])
        try:
            decision, _ = reconstruct_packet(
                profile,
                packet["seats"],
                packet.get("confirmation"),
                now_ms=packet.get("nowMs", 2000000000000),
                base=base,
            )
            terminal = decision["terminal"]
            reasons = decision["reasonCodes"]
        except PacketError as exc:
            terminal = "REFUSED"
            reasons = [exc.code]
        require(terminal == row["expectedTerminal"], "FIXTURE_TERMINAL_MISMATCH", f"{row['caseId']}: expected={row['expectedTerminal']} observed={terminal}")
        require(reasons == row["expectedReasonCodes"], "FIXTURE_REASON_MISMATCH", f"{row['caseId']}: expected={row['expectedReasonCodes']} observed={reasons}")
        ids.append(row["caseId"])
        counts[terminal] += 1
        expanded.append({"caseId": row["caseId"], "packet": packet, "terminal": terminal, "reasonCodes": reasons})
    require(ids == profile["fixtureCaseIds"] and len(ids) == len(set(ids)), "FIXTURE_CASE_DENOMINATOR_INVALID", str(ids))
    require(counts == profile["fixtureTerminalCounts"], "FIXTURE_TERMINAL_COUNTS_INVALID", str(counts))
    return {"schema": catalog["schema"], "bases": copy.deepcopy(catalog["bases"]), "cases": expanded, "terminalCounts": counts}


def campaign(profile: dict[str, Any], fixtures: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": CAMPAIGN_SCHEMA,
        "status": "PASS" if fixtures["terminalCounts"] == profile["fixtureTerminalCounts"] else "REFUSED",
        "caseCount": len(fixtures["cases"]),
        "terminalCounts": fixtures["terminalCounts"],
        "cases": [
            {"caseId": row["caseId"], "terminal": row["terminal"], "reasonCodes": row["reasonCodes"]}
            for row in fixtures["cases"]
        ],
        "physicalExecutionObserved": False,
        "actualSupplierQualified": False,
        "supplierAdmissionReceiptPresent": False,
        "physicalEstateQualified": False,
        "missionAuthority": "none",
        "commandAuthority": "none",
        "targetingAuthority": "none",
        "engagementAuthority": "none",
        "effectorAuthority": "none",
        "weaponsAuthority": "none",
    }


def controller_template_for_seat(template: dict[str, Any], seat_id: str) -> dict[str, Any]:
    value = copy.deepcopy(template)
    value["seatId"] = seat_id
    return value


def extension_manifest(profile: dict[str, Any]) -> dict[str, Any]:
    contract = profile["extensionContract"]
    return {
        "manifest_version": contract["manifestVersion"],
        "name": "AXM Browser Distributed-Inference Observation Probe",
        "version": "0.1.0",
        "content_scripts": [
            {
                "matches": ["<all_urls>"],
                "js": [contract["script"]],
                "run_at": contract["runAt"],
                "world": contract["world"],
                "all_frames": False,
            }
        ],
    }


def runbook_text() -> str:
    return """# AXM Browser Physical Audition Run Kit\n\nThis kit prepares one private two-seat observation transaction for the admitted `axm/distributed-model-inference@1` interface. It does not select or qualify a supplier.\n\nKeep the entire run root outside every source repository. Load `extension/` as an unpacked Chromium-family extension on each independently operated physical seat. The extension installs the exact admitted probe at `document_start` in the page MAIN world. The same exact probe bytes are retained at `source/browser_distributed_inference_probe.js` because the packet runtime resolves its admitted dependencies relative to `source/`. Kit verification requires both copies to match the admitted SHA-256 binding and one another. Confirm the extension manifest and `kit-manifest.json` before opening the target application.\n\nFor each seat, copy the matching controller template to `private/seat-01/control.json` or `private/seat-02/control.json`. Replace every placeholder using body-free evidence references and controller observations. Retain the probe export as `private/<seat>/raw.json`. Do not place prompts, completions, token text, SDP, ICE addresses, device labels, URLs, credentials, response bodies, hostnames, local paths, or private evidence bodies in either file.\n\nRun `python source/axm_head_browser_physical_audition_packet_01.py assemble source/axm-head-browser-physical-audition-packet-profile-01.json <packet-root>`. A complete physical pair without human confirmation stops at `READY_FOR_NAMED_HUMAN`. The compiler does not create a valid confirmation. The named human must separately bind the exact packet evidence root, both seat capture digests, both physical-member evidence references, a body-free SHA-256 actor-evidence reference, current issuance and expiry times, decision code, and authority `none`. The actor-evidence reference identifies an external private provenance receipt; its syntax and content binding do not independently prove the human identity or role.\n\nAfter placing that separately supplied record at `private/named-human-confirmation.json`, rerun `assemble`, then run `verify`. Only an independently reconstructed pair with a valid current confirmation can reach `OBSERVED_ROUTE_CANDIDATE`. That terminal admits the observed route only. It does not admit a supplier, a physical Estate, or any mission, command, targeting, engagement, effector, or weapons authority.\n"""


def kit_member_sources(profile: dict[str, Any], repository_root: Path) -> dict[str, bytes]:
    anchor = repository_root / "mating_surface" / "anchor_node"
    template_path = anchor / "axm-head-browser-physical-audition-controller-template-01.json"
    template = load_object(template_path)
    manifest = extension_manifest(profile)
    source_binding_body = {
        "schema": KIT_SOURCE_BINDING_SCHEMA,
        "admissionCommit": ADMITTED_COMMIT,
        "admissionTree": ADMITTED_TREE,
        "candidateCommit": ADMITTED_CANDIDATE_COMMIT,
        "interface": INTERFACE,
        "profileId": ADMITTED_AUDITION_PROFILE_ID,
        "probeSha256": PROBE_SHA256_REF,
        "sourceBindingId": source_binding_id(profile),
        "copiedMembers": verify_bound_sources(profile, anchor, "kitSourceBindings"),
        "actualSupplierQualified": False,
        "physicalExecutionObserved": False,
        "authority": "none",
    }
    files: dict[str, bytes] = {
        "RUNBOOK.md": runbook_text().encode("utf-8"),
        "extension/manifest.json": pretty_bytes(manifest),
        "extension/browser_distributed_inference_probe.js": (anchor / "browser_distributed_inference_probe.js").read_bytes(),
        "source-binding.json": pretty_bytes(source_binding_body),
        "templates/seat-01-controller.json": pretty_bytes(controller_template_for_seat(template, "seat-01")),
        "templates/seat-02-controller.json": pretty_bytes(controller_template_for_seat(template, "seat-02")),
        "templates/named-human-confirmation.json": pretty_bytes(
            {
                "schema": CONFIRMATION_SCHEMA,
                "actorClass": "named-human",
                "actorEvidenceRef": "REPLACE_WITH_SHA256_NAMED_HUMAN_ACTOR_EVIDENCE_REF",
                "decision": "REPLACE_WITH_NAMED_HUMAN_DECISION",
                "evidenceRoot": "REPLACE_WITH_PACKET_EVIDENCE_ROOT",
                "seatCaptureDigests": [],
                "physicalMemberEvidenceRefs": [],
                "issuedAtUnixMs": 0,
                "expiresAtUnixMs": 0,
                "authority": "none",
                "confirmationId": None,
            }
        ),
    }
    copy_names = {
        "axm-head-browser-distributed-inference-audition-profile-01.json",
        "axm_head_browser_distributed_inference_audition.py",
        "browser_distributed_inference_probe.js",
        "verify_axm_head_browser_distributed_inference_audition.py",
        "verify_axm_head_browser_distributed_inference_audition_bootstrap.py",
        "axm-head-browser-physical-audition-packet-profile-01.json",
        "axm-head-browser-physical-audition-controller-template-01.json",
        "axm-head-browser-physical-audition-packet-01.ps1",
        "axm_head_browser_physical_audition_packet_01.py",
        "verify_axm_head_browser_physical_audition_packet_01.py",
        "verify_axm_head_browser_physical_audition_packet_01_bootstrap.py",
    }
    for name in sorted(copy_names):
        source_path = anchor / name
        assert_regular_no_symlink(source_path)
        files[f"source/{name}"] = source_path.read_bytes()
    wrapper = anchor / "axm-head-browser-physical-audition-packet-01.ps1"
    assert_regular_no_symlink(wrapper)
    files["Invoke-AXMBrowserPhysicalAudition.ps1"] = wrapper.read_bytes()
    return files


def kit_manifest_for(files: dict[str, bytes], source_binding: str) -> dict[str, Any]:
    rows = [
        {"path": path, "bytes": len(data), "sha256": sha256_ref(data)}
        for path, data in sorted(files.items())
    ]
    body = {
        "schema": KIT_MANIFEST_SCHEMA,
        "sourceBindingId": source_binding,
        "members": rows,
        "browserLaunched": False,
        "externalEndpointContacted": False,
        "modelDownloaded": False,
        "peerConnectionFormed": False,
        "inferenceExecuted": False,
        "physicalExecutionObserved": False,
        "actualSupplierQualified": False,
        "authority": "none",
    }
    return {**body, "kitId": content_id("axmbrowserphysicalkit", body)}


def verify_kit(profile: dict[str, Any], kit_root: Path) -> dict[str, Any]:
    kit_root = assert_unlinked_coordinate(kit_root)
    require(kit_root.is_dir(), "KIT_ROOT_INVALID", str(kit_root))
    assert_regular_no_symlink(kit_root / "kit-manifest.json")
    manifest = load_object(kit_root / "kit-manifest.json")
    exact_keys(
        manifest,
        {
            "actualSupplierQualified",
            "authority",
            "browserLaunched",
            "externalEndpointContacted",
            "inferenceExecuted",
            "kitId",
            "members",
            "modelDownloaded",
            "peerConnectionFormed",
            "physicalExecutionObserved",
            "schema",
            "sourceBindingId",
        },
        "KIT_MANIFEST_KEYS_INVALID",
    )
    require(manifest["schema"] == KIT_MANIFEST_SCHEMA, "KIT_MANIFEST_SCHEMA_INVALID", str(manifest["schema"]))
    require(manifest["sourceBindingId"] == source_binding_id(profile), "KIT_SOURCE_BINDING_MISMATCH", str(manifest["sourceBindingId"]))
    for flag in ("browserLaunched", "externalEndpointContacted", "modelDownloaded", "peerConnectionFormed", "inferenceExecuted", "physicalExecutionObserved", "actualSupplierQualified"):
        require(manifest[flag] is False, "KIT_CLAIM_PROMOTED", flag)
    require(manifest["authority"] == "none", "AUTHORITY_PROMOTED", str(manifest["authority"]))
    member_paths: list[str] = []
    for row in manifest["members"]:
        exact_keys(row, {"bytes", "path", "sha256"}, "KIT_MEMBER_KEYS_INVALID")
        require(relative_safe(row["path"]), "UNSAFE_PATH", str(row["path"]))
        path = resolve_inside(kit_root, row["path"])
        assert_regular_no_symlink(path)
        data = path.read_bytes()
        require(len(data) == row["bytes"] and sha256_ref(data) == row["sha256"], "KIT_MEMBER_MISMATCH", row["path"])
        member_paths.append(row["path"])
    require(len(member_paths) == len(set(member_paths)), "KIT_MEMBER_DUPLICATE", str(member_paths))
    observed_files = sorted(
        path.relative_to(kit_root).as_posix()
        for path in kit_root.rglob("*")
        if path.is_file() and path.name != "kit-manifest.json"
    )
    require(observed_files == sorted(member_paths), "KIT_MEMBER_DENOMINATOR_INVALID", f"expected={sorted(member_paths)} observed={observed_files}")
    expected_id = content_id("axmbrowserphysicalkit", {key: value for key, value in manifest.items() if key != "kitId"})
    require(manifest["kitId"] == expected_id, "KIT_ID_MISMATCH", str(manifest["kitId"]))
    extension = load_object(kit_root / "extension" / "manifest.json")
    require(extension == extension_manifest(profile), "EXTENSION_CONTRACT_DRIFT", str(extension))
    extension_probe = kit_root / "extension" / "browser_distributed_inference_probe.js"
    extension_probe_bytes = secure_read_bytes(
        extension_probe,
        maximum_bytes=MAX_SOURCE_BYTES,
        expected_sha256=PROBE_SHA256_REF,
    )
    runtime_source = kit_root / "source"
    verify_bound_sources(profile, runtime_source, "kitSourceBindings")
    runtime_probe = runtime_source / "browser_distributed_inference_probe.js"
    runtime_binding = next(
        row for row in profile["kitSourceBindings"] if Path(row["path"]).name == runtime_probe.name
    )
    runtime_probe_bytes = secure_read_bytes(
        runtime_probe,
        maximum_bytes=MAX_SOURCE_BYTES,
        expected_bytes=runtime_binding["bytes"],
        expected_sha256=runtime_binding["sha256"],
    )
    require(runtime_probe_bytes == extension_probe_bytes, "PROBE_COPY_DIVERGENCE", "extension and runtime probe bytes differ")
    verify_bound_sources(profile, runtime_source, "packetSourceBindings")
    return {"schema": KIT_MANIFEST_SCHEMA, "status": "PASS", "kitId": manifest["kitId"], "sourceBindingId": manifest["sourceBindingId"], "memberCount": len(member_paths)}


def build_kit(profile: dict[str, Any], repository_root: str | Path, output_root: str | Path) -> dict[str, Any]:
    repository_root = assert_unlinked_coordinate(repository_root)
    require(repository_root.is_dir(), "REPOSITORY_ROOT_INVALID", str(repository_root))
    output_root = lexical_absolute(output_root)
    assert_unlinked_coordinate(output_root)
    require(not path_is_within(output_root, repository_root), "REPOSITORY_LOCAL_OUTPUT", str(output_root))
    require(not output_root.exists(), "OUTPUT_ALREADY_EXISTS", str(output_root))
    verify_bound_sources(profile, repository_root / "mating_surface" / "anchor_node", "kitSourceBindings")
    verify_bound_sources(profile, repository_root / "mating_surface" / "anchor_node", "packetSourceBindings")
    files = kit_member_sources(profile, repository_root)
    manifest = kit_manifest_for(files, source_binding_id(profile))
    assert_unlinked_coordinate(output_root.parent)
    output_root.parent.mkdir(parents=True, exist_ok=True)
    assert_unlinked_coordinate(output_root.parent)
    with tempfile.TemporaryDirectory(prefix="axm-browser-physical-kit-", dir=output_root.parent) as temporary:
        staging = Path(temporary) / "kit"
        staging.mkdir()
        for relative, data in files.items():
            path = resolve_inside(staging, relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        (staging / "kit-manifest.json").write_bytes(pretty_bytes(manifest))
        verify_kit(profile, staging)
        staging.rename(output_root)
    return verify_kit(profile, output_root)



def allowed_packet_members(seat_ids: Iterable[str], confirmation_present: bool) -> set[str]:
    allowed = {"private/packet-decision.json", "public/status.json"}
    for seat_id in seat_ids:
        allowed.update(
            {
                f"private/{seat_id}/raw.json",
                f"private/{seat_id}/control.json",
                f"private/{seat_id}/capture.json",
                f"private/{seat_id}/materialization.json",
                f"private/{seat_id}/decision.json",
                f"private/{seat_id}/admitted-verdict.json",
            }
        )
    if confirmation_present:
        allowed.add("private/named-human-confirmation.json")
    return allowed


def inspect_packet_tree(packet_root: Path, *, permit_missing_generated: bool) -> None:
    root = assert_unlinked_coordinate(packet_root)
    if not root.exists():
        return
    require(root.is_dir(), "PACKET_ROOT_INVALID", str(root))
    observed: set[str] = set()
    for path in root.rglob("*"):
        assert_unlinked_coordinate(path)
        if path.is_file():
            observed.add(path.relative_to(root).as_posix())
        else:
            require(path.is_dir(), "PACKET_MEMBER_INVALID", str(path))
    seat_ids = sorted(
        path.name for path in (root / "private").glob("seat-*") if path.is_dir()
    ) if (root / "private").is_dir() else []
    require(all(name in SEAT_IDS for name in seat_ids), "EXTRA_SEAT_PRESENT", str(seat_ids))
    confirmation_present = (root / "private" / "named-human-confirmation.json").exists()
    allowed = allowed_packet_members(seat_ids, confirmation_present)
    if permit_missing_generated:
        allowed.update({"private/packet-decision.json", "public/status.json"})
    extra = sorted(observed - allowed)
    require(not extra, "EXTRA_PACKET_MEMBER", str(extra))


def packet_input_records(packet_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    packet_root = assert_unlinked_coordinate(packet_root)
    inspect_packet_tree(packet_root, permit_missing_generated=True)
    private = packet_root / "private"
    observed_seats = sorted(path.name for path in private.glob("seat-*") if path.is_dir()) if private.is_dir() else []
    require(all(name in SEAT_IDS for name in observed_seats), "EXTRA_SEAT_PRESENT", str(observed_seats))
    records: list[dict[str, Any]] = []
    for seat_id in SEAT_IDS:
        seat = private / seat_id
        raw = seat / "raw.json"
        control = seat / "control.json"
        if not raw.exists() and not control.exists():
            continue
        require(raw.exists() and control.exists(), "RAW_CONTROL_PAIR_INCOMPLETE", seat_id)
        records.append({"seatId": seat_id, "raw": load_object(raw), "control": load_object(control)})
    confirmation_path = private / "named-human-confirmation.json"
    confirmation = load_object(confirmation_path) if confirmation_path.exists() else None
    return records, confirmation




def assemble_packet(profile: dict[str, Any], packet_root: str | Path, *, now_ms: int, base: Path | None = None) -> dict[str, Any]:
    root = assert_unlinked_coordinate(packet_root)
    source_root = assert_unlinked_coordinate(base or Path(__file__).parent)
    require(not path_is_within(root, source_root), "SOURCE_LOCAL_PACKET_ROOT", str(root))
    root.mkdir(parents=True, exist_ok=True)
    assert_unlinked_coordinate(root)
    records, confirmation = packet_input_records(root)
    decision, verified = reconstruct_packet(profile, records, confirmation, now_ms=now_ms, base=base)
    private = root / "private"
    public = root / "public"
    private.mkdir(parents=True, exist_ok=True)
    public.mkdir(parents=True, exist_ok=True)
    assert_unlinked_coordinate(private)
    assert_unlinked_coordinate(public)
    for seat_id, row in zip(SEAT_IDS, verified):
        seat = private / seat_id
        write_derived(seat / "capture.json", pretty_bytes(row["capture"]))
        write_derived(seat / "materialization.json", pretty_bytes(row["materialization"]))
        write_derived(seat / "decision.json", pretty_bytes(row["decision"]))
        write_derived(seat / "admitted-verdict.json", pretty_bytes(row["verdict"]))
    write_derived(private / "packet-decision.json", pretty_bytes(decision))
    write_derived(public / "status.json", pretty_bytes(decision["publicProjection"]))
    inspect_packet_tree(root, permit_missing_generated=False)
    return decision



def locate_packet_verifier(base: Path | None = None) -> tuple[Path, Path]:
    root = assert_unlinked_coordinate(base or Path(__file__).parent)
    require(root.is_dir(), "SOURCE_ROOT_INVALID", str(root))
    return (
        root / "verify_axm_head_browser_physical_audition_packet_01.py",
        root / "verify_axm_head_browser_physical_audition_packet_01_bootstrap.py",
    )



def run_packet_verification(profile_path: Path, packet_root: Path, *, now_ms: int, output: Path | None = None, base: Path | None = None) -> dict[str, Any]:
    profile = validate_profile(profile_path)
    source_root = assert_unlinked_coordinate(base or Path(__file__).parent)
    profile_path = assert_unlinked_coordinate(profile_path)
    packet_root = assert_unlinked_coordinate(packet_root)
    verifier, bootstrap = locate_packet_verifier(base)
    packet_bindings = {Path(row["path"]).name: row for row in profile["packetSourceBindings"]}
    for executable in (verifier, bootstrap):
        binding = packet_bindings.get(executable.name)
        require(binding is not None, "SOURCE_BINDING_MISSING", executable.name)
        secure_read_bytes(
            executable,
            maximum_bytes=MAX_SOURCE_BYTES,
            expected_bytes=binding["bytes"],
            expected_sha256=binding["sha256"],
        )
    if output is not None:
        output = lexical_absolute(output)
        assert_unlinked_coordinate(output)
        require(not path_is_within(output, packet_root), "OUTPUT_INSIDE_PACKET", str(output))
        require(not path_is_within(output, source_root), "OUTPUT_INSIDE_SOURCE", str(output))
    command = [
        sys.executable,
        str(bootstrap),
        str(verifier),
        str(profile_path),
        str(packet_root),
        str(packet_root / "private" / "packet-decision.json"),
        "--now-ms",
        str(now_ms),
    ]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=120)
    require(result.stderr == b"", "PACKET_BOOTSTRAP_STDERR", result.stderr.decode("utf-8", errors="replace"))
    try:
        value = json.loads(result.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PacketError("PACKET_BOOTSTRAP_INVALID", str(exc)) from exc
    require(result.returncode == 0 and value.get("status") == "PASS" and value.get("bootstrapAuthenticated") is True, "PACKET_BOOTSTRAP_REFUSED", str(value))
    require(isinstance(value.get("publicProjection"), dict) and not public_leak(value["publicProjection"]), "PUBLIC_PROJECTION_INVALID", str(value.get("publicProjection")))
    if output is not None:
        write_new(output, pretty_bytes(value))
    return value



def source_set(profile: dict[str, Any], repository_root: str | Path) -> dict[str, Any]:
    root = assert_unlinked_coordinate(repository_root)
    require(root.is_dir(), "REPOSITORY_ROOT_INVALID", str(root))
    rows: list[dict[str, Any]] = []
    for relative in profile["sourceMembers"]:
        path = resolve_inside(root, relative)
        assert_regular_no_symlink(path)
        data = path.read_bytes()
        rows.append({"path": relative, "bytes": len(data), "sha256": sha256_ref(data)})
    body = {"schema": SOURCE_SET_SCHEMA, "profileId": profile["profileId"], "members": rows}
    return {**body, "sourceSetId": content_id("axmbrowserphysicalpacketsource", body)}


def write_fixture_packet(case: dict[str, Any], root: Path) -> None:
    packet = case["packet"]
    private = root / "private"
    private.mkdir(parents=True, exist_ok=True)
    for seat in packet["seats"]:
        seat_root = private / seat["seatId"]
        seat_root.mkdir(parents=True, exist_ok=True)
        (seat_root / "raw.json").write_bytes(pretty_bytes(seat["raw"]))
        (seat_root / "control.json").write_bytes(pretty_bytes(seat["control"]))
    if packet.get("confirmation") is not None:
        (private / "named-human-confirmation.json").write_bytes(pretty_bytes(packet["confirmation"]))


def emit(value: Any) -> None:
    sys.stdout.buffer.write(pretty_bytes(value))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    command = sub.add_parser("validate-profile")
    command.add_argument("profile")

    command = sub.add_parser("validate-fixtures")
    command.add_argument("profile")
    command.add_argument("fixtures")

    command = sub.add_parser("campaign")
    command.add_argument("profile")
    command.add_argument("fixtures")

    command = sub.add_parser("build-kit")
    command.add_argument("profile")
    command.add_argument("repository_root")
    command.add_argument("output_root")

    command = sub.add_parser("assemble")
    command.add_argument("profile")
    command.add_argument("packet_root")
    command.add_argument("--now-ms", type=int, default=None)

    command = sub.add_parser("verify")
    command.add_argument("profile")
    command.add_argument("packet_root")
    command.add_argument("--now-ms", type=int, default=None)
    command.add_argument("--out")

    command = sub.add_parser("public-projection")
    command.add_argument("profile")
    command.add_argument("packet_root")
    command.add_argument("--now-ms", type=int, default=None)
    command.add_argument("--out")

    command = sub.add_parser("source-set")
    command.add_argument("profile")
    command.add_argument("repository_root")

    args = parser.parse_args(argv)
    try:
        profile_path = assert_unlinked_coordinate(args.profile)
        profile = validate_profile(profile_path)
        if args.command == "validate-profile":
            emit({"schema": PROFILE_SCHEMA, "status": "PASS", "profileId": profile["profileId"], "sourceBindingId": source_binding_id(profile)})
            return 0
        if args.command == "validate-fixtures":
            fixtures = validate_fixture_catalog(args.fixtures, profile)
            emit({"schema": FIXTURE_SCHEMA, "status": "PASS", "caseCount": len(fixtures["cases"]), "terminalCounts": fixtures["terminalCounts"]})
            return 0
        if args.command == "campaign":
            fixtures = validate_fixture_catalog(args.fixtures, profile)
            emit(campaign(profile, fixtures))
            return 0
        if args.command == "build-kit":
            emit(build_kit(profile, args.repository_root, args.output_root))
            return 0
        now_ms = args.now_ms if getattr(args, "now_ms", None) is not None else int(__import__("time").time() * 1000)
        if args.command == "assemble":
            decision = assemble_packet(profile, args.packet_root, now_ms=now_ms)
            emit(decision)
            return 0
        if args.command == "verify":
            value = run_packet_verification(profile_path, Path(args.packet_root), now_ms=now_ms, output=Path(args.out) if args.out else None)
            emit(value)
            return 0
        if args.command == "public-projection":
            packet_root = assert_unlinked_coordinate(args.packet_root)
            verdict = run_packet_verification(profile_path, packet_root, now_ms=now_ms)
            require(verdict["status"] == "PASS", "PACKET_VERIFICATION_REQUIRED", str(verdict))
            public = verdict["publicProjection"]
            require(not public_leak(public), "PUBLIC_PROJECTION_LEAK", "authenticated projection leaks")
            data = pretty_bytes(public)
            if args.out:
                output = lexical_absolute(args.out)
                require(not path_is_within(output, packet_root), "OUTPUT_INSIDE_PACKET", str(output))
                require(not path_is_within(output, profile_path.parent), "OUTPUT_INSIDE_SOURCE", str(output))
                write_new(output, data)
            sys.stdout.buffer.write(data)
            return 0
        if args.command == "source-set":
            emit(source_set(profile, args.repository_root))
            return 0
        raise PacketError("COMMAND_INVALID", args.command)
    except (PacketError, KeyError, TypeError, ValueError, OSError) as exc:
        code = exc.code if isinstance(exc, PacketError) else "STRUCTURE_INVALID"
        message = exc.message if isinstance(exc, PacketError) else str(exc)
        emit(
            {
                "schema": CLI_REFUSAL_SCHEMA,
                "status": "REFUSED",
                "code": code,
                "message": message,
                "actualSupplierQualified": False,
                "physicalExecutionObserved": False,
                "authority": "none",
            }
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
