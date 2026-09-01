from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import stat
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

PROFILE_SCHEMA = "axm-head/browser-physical-audition-packet-profile@1"
PACKET_DECISION_SCHEMA = "axm-head/browser-physical-audition-packet-decision@1"
PACKET_PUBLIC_SCHEMA = "axm-head/browser-physical-audition-packet-public@1"
VERDICT_SCHEMA = "axm-head/browser-physical-audition-packet-verdict@1"
CONFIRMATION_SCHEMA = "axm-head/browser-physical-audition-named-human-confirmation@1"
PROFILE_ID = "axm-head/browser-physical-audition-packet/0.1"
ISSUE_REF = "BigBirdReturns/ai-execution-audit#98"
INTERFACE = "axm/distributed-model-inference@1"
ADMITTED_COMMIT = "e32cf641cddd00ab1c97d7d6af1708c84ea491b6"
ADMITTED_TREE = "271956e4a5068c0d71f5223b032cd2e19d4a7c8d"
ADMITTED_CANDIDATE_COMMIT = "351f1f1e54e4d454137b69ad64e571590db134dd"
ADMITTED_AUDITION_PROFILE_ID = "axm-head/browser-distributed-inference-audition/0.1"
PROBE_SHA256_REF = "sha256:b1ded0348ffc0ec4246e9d18a08451216c89f98d6369e483808062430088565e"
MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_SOURCE_BYTES = 4 * 1024 * 1024
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
KIT_DEPENDENCIES = (
    "axm-head-browser-distributed-inference-audition-profile-01.json",
    "axm_head_browser_distributed_inference_audition.py",
    "browser_distributed_inference_probe.js",
    "verify_axm_head_browser_distributed_inference_audition.py",
    "verify_axm_head_browser_distributed_inference_audition_bootstrap.py",
)
PACKET_DEPENDENCIES = (
    "axm-head-browser-physical-audition-controller-template-01.json",
    "axm-head-browser-physical-audition-packet-01.ps1",
    "axm_head_browser_physical_audition_packet_01.py",
    "verify_axm_head_browser_physical_audition_packet_01.py",
    "verify_axm_head_browser_physical_audition_packet_01_bootstrap.py",
)
CLAIM_BOUNDARY = (
    "Supplier-neutral source-qualified preparation for one private two-seat browser audition. "
    "Synthetic fixtures qualify only the packet compiler, generated extension, and independent reconstruction law. "
    "They do not establish a browser launch, endpoint contact, model download, peer connection, inference, physical execution, "
    "supplier qualification, physical Estate qualification, or any mission, command, targeting, engagement, effector, or weapons authority."
)
SEAT_IDS = ("seat-01", "seat-02")
TERMINALS = (
    "PREPARED_NOT_EXECUTED",
    "READY_FOR_NAMED_HUMAN",
    "OBSERVED_ROUTE_CANDIDATE",
    "HOLD",
    "REFUSED",
)
PUBLIC_KEYS = {
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
}
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


class VerifyError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise VerifyError(code, message)


def exact_keys(value: dict[str, Any], expected: set[str], code: str) -> None:
    observed = set(value) if isinstance(value, dict) else set()
    require(observed == expected, code, f"expected={sorted(expected)} observed={sorted(observed)}")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def pretty_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def sha256_ref(value: Any) -> str:
    data = value if isinstance(value, bytes) else canonical_bytes(value)
    return "sha256:" + hashlib.sha256(data).hexdigest()


def content_id(prefix: str, value: Any) -> str:
    return prefix + "_" + hashlib.sha256(canonical_bytes(value)).hexdigest()


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


def path_is_within(path: Path, root: Path) -> bool:
    absolute_path = lexical_absolute(path)
    absolute_root = lexical_absolute(root)
    try:
        common = os.path.commonpath((str(absolute_path), str(absolute_root)))
    except ValueError:
        return False
    return os.path.normcase(common) == os.path.normcase(str(absolute_root))


def secure_read_bytes(
    path: str | Path,
    *,
    maximum_bytes: int = MAX_JSON_BYTES,
    expected_bytes: int | None = None,
    expected_sha256: str | None = None,
) -> bytes:
    absolute = assert_unlinked_coordinate(path)
    try:
        before = absolute.lstat()
    except OSError as exc:
        raise VerifyError("REQUIRED_FILE_MISSING", f"{absolute}: {exc}") from exc
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
        raise VerifyError("FILE_READ_REFUSED", f"{absolute}: {exc}") from exc
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
    after_path = absolute.lstat()
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


def load(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(secure_read_bytes(path).decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise VerifyError("JSON_UNAVAILABLE", f"{path}: {exc}") from exc
    require(isinstance(value, dict), "JSON_OBJECT_REQUIRED", str(path))
    return value


def write_new(path: Path, data: bytes) -> None:
    absolute = lexical_absolute(path)
    assert_unlinked_coordinate(absolute.parent)
    absolute.parent.mkdir(parents=True, exist_ok=True)
    assert_unlinked_coordinate(absolute.parent)
    if absolute.exists() or absolute.is_symlink():
        existing = secure_read_bytes(absolute, maximum_bytes=max(MAX_SOURCE_BYTES, len(data)), expected_bytes=len(data))
        require(existing == data, "OUTPUT_COLLISION", str(absolute))
        return
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(absolute, flags, 0o600)
    except OSError as exc:
        raise VerifyError("OUTPUT_WRITE_REFUSED", f"{absolute}: {exc}") from exc
    try:
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            require(written > 0, "OUTPUT_WRITE_REFUSED", str(absolute))
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    require(secure_read_bytes(absolute, maximum_bytes=max(MAX_SOURCE_BYTES, len(data)), expected_bytes=len(data)) == data, "OUTPUT_WRITE_MISMATCH", str(absolute))



def normalized_key(value: Any) -> str:
    return str(value).replace("_", "").replace("-", "").lower()


def public_leak(value: Any) -> bool:
    if isinstance(value, dict):
        return any(normalized_key(key) in FORBIDDEN_PUBLIC_KEYS or public_leak(child) for key, child in value.items())
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




def validate_profile(profile: dict[str, Any]) -> None:
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
    require(profile["seatCount"] == 2 and profile["physicalMemberEvidenceCount"] == 2, "SEAT_DENOMINATOR_INVALID", str(profile["seatCount"]))
    require(tuple(profile["sourceMembers"]) == SOURCE_MEMBERS, "SOURCE_MEMBER_DENOMINATOR_INVALID", str(profile["sourceMembers"]))
    require(set(profile["publicProjectionAllowedKeys"]) == PUBLIC_KEYS and len(profile["publicProjectionAllowedKeys"]) == len(PUBLIC_KEYS), "PUBLIC_KEY_DENOMINATOR_INVALID", str(profile["publicProjectionAllowedKeys"]))
    require(profile["claimBoundary"] == CLAIM_BOUNDARY, "CLAIM_BOUNDARY_INVALID", str(profile["claimBoundary"]))
    binding = profile["admittedAudition"]
    exact_keys(binding, {"admissionCommit", "admissionTree", "candidateCommit", "interface", "probeSha256", "profileId", "sourceMembers"}, "ADMITTED_BINDING_KEYS_INVALID")
    require(
        (
            binding["admissionCommit"],
            binding["admissionTree"],
            binding["candidateCommit"],
            binding["interface"],
            binding["probeSha256"],
            binding["profileId"],
        )
        == (ADMITTED_COMMIT, ADMITTED_TREE, ADMITTED_CANDIDATE_COMMIT, INTERFACE, PROBE_SHA256_REF, ADMITTED_AUDITION_PROFILE_ID),
        "ADMITTED_SOURCE_FLOOR_DRIFT",
        "admitted source binding drifted",
    )
    observed_members = tuple((row.get("path"), row.get("gitBlobSha")) for row in binding["sourceMembers"] if isinstance(row, dict))
    require(observed_members == ADMITTED_SOURCE_MEMBERS, "ADMITTED_SOURCE_MEMBER_DRIFT", str(observed_members))
    require(
        profile["extensionContract"] == {"manifestVersion": 3, "runAt": "document_start", "script": "browser_distributed_inference_probe.js", "world": "MAIN"},
        "EXTENSION_CONTRACT_INVALID",
        str(profile["extensionContract"]),
    )
    require(
        profile["confirmationPolicy"] == {
            "actorClass": "named-human",
            "actorEvidenceRequired": True,
            "decision": "CONFIRM_OBSERVED_ROUTE_CANDIDATE",
            "futureSkewMs": 300000,
            "maximumValidityMs": 86400000,
        },
        "CONFIRMATION_POLICY_INVALID",
        str(profile["confirmationPolicy"]),
    )
    for key, names in (("kitSourceBindings", KIT_DEPENDENCIES), ("packetSourceBindings", PACKET_DEPENDENCIES)):
        rows = profile[key]
        require(isinstance(rows, list) and tuple(Path(row.get("path", "")).name for row in rows if isinstance(row, dict)) == names, "SOURCE_BINDING_DENOMINATOR_INVALID", key)
        seen: set[str] = set()
        for row in rows:
            exact_keys(row, {"bytes", "path", "sha256"}, "SOURCE_BINDING_KEYS_INVALID")
            require(
                isinstance(row["path"], str)
                and row["path"]
                and "\\" not in row["path"]
                and not Path(row["path"]).is_absolute()
                and all(part not in {"", ".", ".."} for part in Path(row["path"]).parts)
                and isinstance(row["bytes"], int)
                and 0 < row["bytes"] <= MAX_SOURCE_BYTES
                and is_sha256_ref(row["sha256"]),
                "SOURCE_BINDING_INVALID",
                str(row),
            )
            require(row["path"] not in seen, "SOURCE_BINDING_DUPLICATE", row["path"])
            seen.add(row["path"])
    require(isinstance(profile["fixtureCaseIds"], list) and len(profile["fixtureCaseIds"]) == len(set(profile["fixtureCaseIds"])), "FIXTURE_CASE_DENOMINATOR_INVALID", str(profile["fixtureCaseIds"]))
    exact_keys(profile["fixtureTerminalCounts"], set(TERMINALS), "FIXTURE_TERMINAL_COUNT_KEYS_INVALID")
    require(sum(profile["fixtureTerminalCounts"].values()) == len(profile["fixtureCaseIds"]), "FIXTURE_TERMINAL_COUNTS_INVALID", str(profile["fixtureTerminalCounts"]))




def expected_binding(profile: dict[str, Any], basename: str, key: str = "kitSourceBindings") -> dict[str, Any]:
    rows = [row for row in profile[key] if Path(row["path"]).name == basename]
    require(len(rows) == 1, "SOURCE_BINDING_MISSING", basename)
    return rows[0]


def verify_bound_sources(profile: dict[str, Any], source_root: Path, key: str) -> None:
    for row in profile[key]:
        path = assert_unlinked_coordinate(source_root / row["path"])
        secure_read_bytes(path, maximum_bytes=MAX_SOURCE_BYTES, expected_bytes=row["bytes"], expected_sha256=row["sha256"])




def measured_admitted_verify(
    profile: dict[str, Any],
    source_root: Path,
    capture_path: Path,
    decision_path: Path,
    raw_path: Path,
    control_path: Path,
) -> dict[str, Any]:
    source_root = assert_unlinked_coordinate(source_root)
    verifier_path = source_root / "verify_axm_head_browser_distributed_inference_audition.py"
    audition_profile_path = source_root / "axm-head-browser-distributed-inference-audition-profile-01.json"
    verifier_binding = expected_binding(profile, verifier_path.name)
    profile_binding = expected_binding(profile, audition_profile_path.name)
    source = secure_read_bytes(verifier_path, maximum_bytes=MAX_SOURCE_BYTES, expected_bytes=verifier_binding["bytes"], expected_sha256=verifier_binding["sha256"])
    profile_bytes = secure_read_bytes(audition_profile_path, maximum_bytes=MAX_SOURCE_BYTES, expected_bytes=profile_binding["bytes"], expected_sha256=profile_binding["sha256"])
    captured = {
        "capture.json": secure_read_bytes(capture_path),
        "decision.json": secure_read_bytes(decision_path),
        "raw.json": secure_read_bytes(raw_path),
        "control.json": secure_read_bytes(control_path),
        "profile.json": profile_bytes,
    }
    launcher = (
        "import sys; source=sys.stdin.buffer.read(); "
        "sys.argv=['measured-admitted-verifier', *sys.argv[1:]]; "
        "ns={'__name__':'__main__','__file__':'<measured-admitted-verifier>'}; "
        "exec(compile(source,'<measured-admitted-verifier>','exec'),ns)"
    )
    with tempfile.TemporaryDirectory(prefix="axm-admitted-seat-verifier-") as temporary:
        staged = Path(temporary)
        for name, data in captured.items():
            (staged / name).write_bytes(data)
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-S",
                "-c",
                launcher,
                str(staged / "profile.json"),
                str(staged / "capture.json"),
                str(staged / "decision.json"),
                "--raw",
                str(staged / "raw.json"),
                "--control",
                str(staged / "control.json"),
            ],
            input=source,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=staged,
            check=False,
            timeout=60,
        )
    require(result.stderr == b"", "ADMITTED_VERIFIER_STDERR", result.stderr.decode("utf-8", errors="replace"))
    try:
        verdict = json.loads(result.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise VerifyError("ADMITTED_VERIFIER_OUTPUT_INVALID", str(exc)) from exc
    require(result.returncode == 0 and verdict.get("status") == "PASS", "ADMITTED_VERIFIER_REFUSED", str(verdict))
    require(verdict.get("rawEvidenceReconstructed") is True, "RAW_EVIDENCE_NOT_RECONSTRUCTED", str(verdict))
    require(verdict.get("bootstrapAuthenticated") is False, "ADMITTED_VERIFIER_SELF_AUTHENTICATED", str(verdict))
    return verdict



def control_member_refs(control: dict[str, Any]) -> tuple[dict[str, str], list[str]]:
    assertions = control.get("memberUniquenessAssertions")
    require(isinstance(assertions, list) and len(assertions) == 2, "PHYSICAL_MEMBER_DENOMINATOR_INVALID", str(assertions))
    mapping: dict[str, str] = {}
    refs: list[str] = []
    for row in assertions:
        exact_keys(row, {"evidenceRef", "physicallyUnique", "probeMemberId"}, "PHYSICAL_MEMBER_ASSERTION_KEYS_INVALID")
        require(isinstance(row["probeMemberId"], str) and row["probeMemberId"].startswith("opaque:"), "PHYSICAL_MEMBER_ID_INVALID", str(row["probeMemberId"]))
        require(row["physicallyUnique"] is True and is_sha256_ref(row["evidenceRef"]), "PHYSICAL_MEMBER_EVIDENCE_INVALID", str(row))
        require(row["probeMemberId"] not in mapping, "PHYSICAL_MEMBER_ID_DUPLICATE", row["probeMemberId"])
        mapping[row["probeMemberId"]] = row["evidenceRef"]
        refs.append(row["evidenceRef"])
    return mapping, sorted(refs)


def hashed_member_id(probe_id: str) -> str:
    return sha256_ref({"probeOpaqueId": probe_id})


def seat_projection(capture: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    opaque_map, refs = control_member_refs(control)
    hashed_map = {hashed_member_id(key): value for key, value in opaque_map.items()}
    members = []
    for row in capture["formation"]["members"]:
        require(row["memberIdHash"] in hashed_map, "CROSS_SEAT_MEMBER_BINDING_INVALID", row["memberIdHash"])
        members.append({"evidenceRef": hashed_map[row["memberIdHash"]], "pledgedBytes": row["pledgedBytes"], "role": row["role"]})
    layers = []
    for row in capture["model"]["layers"]:
        require(row["memberIdHash"] in hashed_map, "CROSS_SEAT_MODEL_BINDING_INVALID", row["memberIdHash"])
        layers.append(
            {
                "artifactBytes": row["artifactBytes"],
                "artifactDigest": row["artifactDigest"],
                "evidenceRef": hashed_map[row["memberIdHash"]],
                "layerEnd": row["layerEnd"],
                "layerStart": row["layerStart"],
            }
        )
    channels = capture["transport"]["activationChannels"]
    return {
        "physicalMemberEvidenceRefs": refs,
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


def confirmation_id(value: dict[str, Any]) -> str:
    normalized = copy.deepcopy(value)
    normalized["confirmationId"] = None
    return content_id("axmbrowserhumanconfirmation", normalized)


def validate_confirmation(
    confirmation: dict[str, Any],
    profile: dict[str, Any],
    evidence_root: str,
    seat_capture_digests: list[str],
    physical_refs: list[str],
    now_ms: int,
) -> None:
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
    issued, expires = confirmation["issuedAtUnixMs"], confirmation["expiresAtUnixMs"]
    require(isinstance(issued, int) and isinstance(expires, int), "CONFIRMATION_TIME_INVALID", str((issued, expires)))
    require(issued <= now_ms + policy["futureSkewMs"], "CONFIRMATION_NOT_CURRENT", str(issued))
    require(now_ms <= expires, "CONFIRMATION_EXPIRED", str(expires))
    require(0 < expires - issued <= policy["maximumValidityMs"], "CONFIRMATION_VALIDITY_INVALID", str((issued, expires)))
    require(isinstance(confirmation["confirmationId"], str) and CONTENT_ID_RE.fullmatch(confirmation["confirmationId"]) is not None, "CONFIRMATION_ID_INVALID", str(confirmation["confirmationId"]))
    require(confirmation["confirmationId"] == confirmation_id(confirmation), "CONFIRMATION_ID_MISMATCH", str(confirmation["confirmationId"]))


def generated_public(decision: dict[str, Any]) -> dict[str, Any]:
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
    require(set(value) == PUBLIC_KEYS and not public_leak(value), "PUBLIC_PROJECTION_INVALID", str(value))
    return value



def allowed_packet_members(seat_ids: list[str], confirmation_present: bool) -> set[str]:
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


def inspect_packet_tree(packet_root: Path) -> list[str]:
    root = assert_unlinked_coordinate(packet_root)
    require(root.is_dir(), "PACKET_ROOT_INVALID", str(root))
    observed: set[str] = set()
    for path in root.rglob("*"):
        assert_unlinked_coordinate(path)
        if path.is_file():
            observed.add(path.relative_to(root).as_posix())
        else:
            require(path.is_dir(), "PACKET_MEMBER_INVALID", str(path))
    private = root / "private"
    seat_ids = sorted(path.name for path in private.glob("seat-*") if path.is_dir()) if private.is_dir() else []
    require(all(name in SEAT_IDS for name in seat_ids), "EXTRA_SEAT_PRESENT", str(seat_ids))
    confirmation_present = (private / "named-human-confirmation.json").exists()
    allowed = allowed_packet_members(seat_ids, confirmation_present)
    require(observed == allowed, "PACKET_MEMBER_DENOMINATOR_INVALID", f"missing={sorted(allowed-observed)} extra={sorted(observed-allowed)}")
    return seat_ids


def read_packet_inputs(packet_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    root = assert_unlinked_coordinate(packet_root)
    private = root / "private"
    records: list[dict[str, Any]] = []
    observed_seats = sorted(path.name for path in private.glob("seat-*") if path.is_dir()) if private.is_dir() else []
    require(all(name in SEAT_IDS for name in observed_seats), "EXTRA_SEAT_PRESENT", str(observed_seats))
    for seat_id in SEAT_IDS:
        seat = private / seat_id
        raw = seat / "raw.json"
        control = seat / "control.json"
        if not raw.exists() and not control.exists():
            continue
        require(raw.exists() and control.exists(), "RAW_CONTROL_PAIR_INCOMPLETE", seat_id)
        records.append({"seatId": seat_id, "rawPath": raw, "controlPath": control, "raw": load(raw), "control": load(control)})
    confirmation_path = private / "named-human-confirmation.json"
    confirmation = load(confirmation_path) if confirmation_path.exists() else None
    return records, confirmation


def expected_materialization(raw: dict[str, Any], control: dict[str, Any], capture: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "axm-head/browser-distributed-inference-audition-materialization@1",
        "status": "PASS",
        "rawCaptureDigest": sha256_ref(raw),
        "controlDigest": sha256_ref(control),
        "normalizedCaptureDigest": decision["captureDigest"],
        "rawEventCount": len(raw["events"]),
        "rawEventsReconstructed": True,
        "probeSha256": control["probeSha256"],
        "executionOccurred": False,
        "actualSupplierQualified": False,
        "physicalEstateQualified": False,
        "missionAuthority": "none",
        "commandAuthority": "none",
    }



def reconstruct(profile: dict[str, Any], source_root: Path, packet_root: Path, now_ms: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source_root = assert_unlinked_coordinate(source_root)
    packet_root = assert_unlinked_coordinate(packet_root)
    verify_bound_sources(profile, source_root, "kitSourceBindings")
    verify_bound_sources(profile, source_root, "packetSourceBindings")
    records, confirmation = read_packet_inputs(packet_root)
    if len(records) == 0:
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
        body["publicProjection"] = generated_public(body)
        body["packetDecisionId"] = content_id("axmbrowserpacketdecision", {**body, "packetDecisionId": None})
        return body, []

    require(len(records) <= 2, "SEAT_DENOMINATOR_EXCEEDED", str(len(records)))
    verified: list[dict[str, Any]] = []
    violations: set[str] = set()
    if len(records) != 2:
        violations.add("ONE_SEAT_SUBSTITUTION")
    for index, record in enumerate(records):
        require(record["seatId"] == SEAT_IDS[index], "SEAT_ORDER_INVALID", record["seatId"])
        seat_root = packet_root / "private" / record["seatId"]
        capture_path = seat_root / "capture.json"
        materialization_path = seat_root / "materialization.json"
        decision_path = seat_root / "decision.json"
        stored_verdict_path = seat_root / "admitted-verdict.json"
        for generated in (capture_path, materialization_path, decision_path, stored_verdict_path):
            require(generated.exists(), "GENERATED_SEAT_RECEIPT_MISSING", f"{record['seatId']}: {generated.name}")
        capture = load(capture_path)
        materialization = load(materialization_path)
        decision = load(decision_path)
        stored_verdict = load(stored_verdict_path)
        measured = measured_admitted_verify(profile, source_root, capture_path, decision_path, record["rawPath"], record["controlPath"])
        require(measured == stored_verdict, "ADMITTED_VERDICT_MISMATCH", record["seatId"])
        require(materialization == expected_materialization(record["raw"], record["control"], capture, decision), "MATERIALIZATION_RECEIPT_MISMATCH", record["seatId"])
        if measured["terminal"] != "OBSERVED_ROUTE_CANDIDATE" or measured["reasonCodes"]:
            violations.add("SEAT_CAPTURE_HELD")
        verified.append(
            {
                "capture": capture,
                "decision": decision,
                "verdict": measured,
                "control": record["control"],
                "projection": seat_projection(capture, record["control"]),
            }
        )

    seat_receipts = [
        {
            "seatId": seat_id,
            "rawEvidenceRef": row["capture"]["rawEvidenceRef"],
            "controlEvidenceRef": row["capture"]["controlEvidenceRef"],
            "captureDigest": row["decision"]["captureDigest"],
            "observationReceiptDigest": row["decision"]["observationReceiptDigest"],
            "admittedVerifierDecisionDigest": row["verdict"]["decisionDigest"],
        }
        for seat_id, row in zip(SEAT_IDS, verified)
    ]
    source_kinds = [row["capture"]["sourceKind"] for row in verified]
    if len(set(source_kinds)) > 1:
        violations.add("MIXED_SOURCE_KIND")
    synthetic = bool(source_kinds) and all(kind == "synthetic-live-capture" for kind in source_kinds)
    physical = bool(source_kinds) and all(kind == "physical-private-local" for kind in source_kinds)
    if not (synthetic or physical):
        violations.add("NONPHYSICAL_SOURCE_KIND")
    if synthetic and any(row["capture"].get("syntheticConformanceOnly") is not True for row in verified):
        violations.add("NONPHYSICAL_SOURCE_KIND")
    if physical and any(row["capture"].get("syntheticConformanceOnly") is not False for row in verified):
        violations.add("NONPHYSICAL_SOURCE_KIND")

    if len(verified) == 2:
        if (
            verified[0]["capture"]["rawEvidenceRef"] == verified[1]["capture"]["rawEvidenceRef"]
            or verified[0]["capture"]["controlEvidenceRef"] == verified[1]["capture"]["controlEvidenceRef"]
            or seat_receipts[0]["captureDigest"] == seat_receipts[1]["captureDigest"]
        ):
            violations.add("SEAT_REPLAYED")
        a, b = verified[0]["projection"], verified[1]["projection"]
        refs_a, refs_b = a["physicalMemberEvidenceRefs"], b["physicalMemberEvidenceRefs"]
        if len(refs_a) != 2 or len(set(refs_a)) != 2 or len(refs_b) != 2 or len(set(refs_b)) != 2:
            violations.add("DUPLICATE_PHYSICAL_MEMBER_EVIDENCE")
        if refs_a != refs_b:
            violations.add("CROSS_SEAT_MEMBER_SET_DISAGREEMENT")
        if a["probeSha256"] != PROBE_SHA256_REF or b["probeSha256"] != PROBE_SHA256_REF:
            violations.add("PROBE_BINDING_DISAGREEMENT")
        if a["interface"] != INTERFACE or b["interface"] != INTERFACE:
            violations.add("INTERFACE_BINDING_DISAGREEMENT")
        if a["model"] != b["model"]:
            violations.add("MODEL_DENOMINATOR_DISAGREEMENT")
        ta, tb = a["topology"], b["topology"]
        if (
            ta["selectedCandidatePairObserved"] is not True
            or tb["selectedCandidatePairObserved"] is not True
            or ta["selectedCandidatePairClass"] != tb["selectedCandidatePairClass"]
            or ta["peerConnectionCount"] != tb["peerConnectionCount"]
        ):
            violations.add("TOPOLOGY_DISAGREEMENT")
        if (
            ta["activationChannelCount"] != tb["activationChannelCount"]
            or not ta["allOrdered"]
            or not tb["allOrdered"]
            or not ta["allReliable"]
            or not tb["allReliable"]
            or not ta["allTransferredBytes"]
            or not tb["allTransferredBytes"]
        ):
            violations.add("ACTIVATION_TRANSPORT_DISAGREEMENT")
        if a["performance"] != b["performance"]:
            violations.add("PERFORMANCE_DENOMINATOR_DISAGREEMENT")
        ea, eb = a["equivalence"], b["equivalence"]
        if (
            ea["match"] is not True
            or eb["match"] is not True
            or ea["referenceDigest"] != ea["candidateDigest"]
            or eb["referenceDigest"] != eb["candidateDigest"]
            or ea["referenceDigest"] != eb["referenceDigest"]
            or ea["promptTokenCount"] != eb["promptTokenCount"]
            or ea["outputTokenCount"] != eb["outputTokenCount"]
        ):
            violations.add("OUTPUT_DISAGREEMENT")
        pa, pb = a["privacy"], b["privacy"]
        if (
            pa["declarationPresent"] is not True
            or pb["declarationPresent"] is not True
            or pa["claimsEndToEndConfidentiality"] is not False
            or pb["claimsEndToEndConfidentiality"] is not False
            or pa["scope"] != "browser-observed-network-surface-only"
            or pb["scope"] != "browser-observed-network-surface-only"
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
    confirmation_value = None
    confirmation_actor_evidence_ref = None
    if physical and len(verified) == 2 and not violations:
        if confirmation is None:
            violations.add("NAMED_HUMAN_CONFIRMATION_MISSING")
        else:
            validate_confirmation(
                confirmation,
                profile,
                evidence_root,
                [row["captureDigest"] for row in seat_receipts],
                physical_refs,
                now_ms,
            )
            named_human_confirmed = True
            confirmation_value = confirmation["confirmationId"]
            confirmation_actor_evidence_ref = confirmation["actorEvidenceRef"]
    elif confirmation is not None:
        raise VerifyError("CONFIRMATION_NOT_APPLICABLE", "confirmation supplied to nonphysical or incomplete packet")

    reasons = [code for code in REASON_ORDER if code in violations]
    if synthetic and len(verified) == 2 and not violations:
        terminal = "OBSERVED_ROUTE_CANDIDATE"
    elif physical and len(verified) == 2 and named_human_confirmed and not violations:
        terminal = "OBSERVED_ROUTE_CANDIDATE"
    elif physical and len(verified) == 2 and violations == {"NAMED_HUMAN_CONFIRMATION_MISSING"}:
        terminal = "READY_FOR_NAMED_HUMAN"
        reasons = ["NAMED_HUMAN_CONFIRMATION_MISSING"]
    elif violations:
        terminal = "HOLD"
    else:
        terminal = "HOLD"

    body = {
        "schema": PACKET_DECISION_SCHEMA,
        "terminal": terminal,
        "reasonCodes": reasons,
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
        "namedHumanConfirmationId": confirmation_value,
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
    body["publicProjection"] = generated_public(body)
    body["packetDecisionId"] = content_id("axmbrowserpacketdecision", {**body, "packetDecisionId": None})
    return body, verified



def verify(profile: dict[str, Any], source_root: Path, packet_root: Path, stored_decision: dict[str, Any], now_ms: int) -> dict[str, Any]:
    validate_profile(profile)
    source_root = assert_unlinked_coordinate(source_root)
    packet_root = assert_unlinked_coordinate(packet_root)
    inspect_packet_tree(packet_root)
    expected, verified = reconstruct(profile, source_root, packet_root, now_ms)
    require(stored_decision == expected, "PACKET_DECISION_MISMATCH", "stored packet decision differs from independent reconstruction")
    public_path = packet_root / "public" / "status.json"
    stored_public = load(public_path)
    require(stored_public == expected["publicProjection"], "PUBLIC_STATUS_MISMATCH", "stored public status differs from authenticated reconstruction")
    require(stored_decision["actualSupplierQualified"] is False, "SUPPLIER_CLAIM_PROMOTED", "actual supplier qualified")
    require(stored_decision["supplierAdmissionReceiptPresent"] is False, "SUPPLIER_ADMISSION_PROMOTED", "supplier admission present")
    require(stored_decision["physicalEstateQualified"] is False, "ESTATE_CLAIM_PROMOTED", "physical Estate qualified")
    for key in ("missionAuthority", "commandAuthority", "targetingAuthority", "engagementAuthority", "effectorAuthority", "weaponsAuthority"):
        require(stored_decision[key] == "none", "AUTHORITY_PROMOTED", key)
    require(not public_leak(stored_public), "PUBLIC_PROJECTION_LEAK", "stored public projection leaks")
    return {
        "schema": VERDICT_SCHEMA,
        "status": "PASS",
        "terminal": stored_decision["terminal"],
        "reasonCodes": stored_decision["reasonCodes"],
        "packetDecisionId": stored_decision["packetDecisionId"],
        "packetEvidenceRoot": stored_decision["packetEvidenceRoot"],
        "sourceBindingId": stored_decision["sourceBindingId"],
        "seatCount": stored_decision["seatCount"],
        "seatCapturesIndependentlyReconstructed": len(verified),
        "namedHumanConfirmed": stored_decision["namedHumanConfirmed"],
        "syntheticConformanceOnly": stored_decision["syntheticConformanceOnly"],
        "physicalExecutionObserved": stored_decision["physicalExecutionObserved"],
        "rawEvidenceReconstructed": all(row["verdict"]["rawEvidenceReconstructed"] is True for row in verified),
        "storedDecisionReconstructed": True,
        "publicProjectionReconstructed": True,
        "publicProjection": copy.deepcopy(stored_public),
        "publicProjectionDigest": sha256_ref(stored_public),
        "bootstrapAuthenticated": False,
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




def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile")
    parser.add_argument("packet_root")
    parser.add_argument("decision")
    parser.add_argument("--now-ms", type=int, required=True)
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    output: Path | None = None
    try:
        profile_path = assert_unlinked_coordinate(args.profile)
        packet_root = assert_unlinked_coordinate(args.packet_root)
        decision_path = assert_unlinked_coordinate(args.decision)
        source_root = profile_path.parent
        require(decision_path == packet_root / "private" / "packet-decision.json", "DECISION_COORDINATE_INVALID", str(decision_path))
        if args.out:
            output = assert_unlinked_coordinate(args.out)
            require(not path_is_within(output, packet_root), "OUTPUT_INSIDE_PACKET", str(output))
            require(not path_is_within(output, source_root), "OUTPUT_INSIDE_SOURCE", str(output))
        verdict = verify(load(profile_path), source_root, packet_root, load(decision_path), args.now_ms)
        data = pretty_bytes(verdict)
        if output is not None:
            write_new(output, data)
        sys.stdout.buffer.write(data)
        return 0
    except (VerifyError, KeyError, TypeError, ValueError, OSError, subprocess.TimeoutExpired) as exc:
        code = exc.code if isinstance(exc, VerifyError) else "STRUCTURE_INVALID"
        message = exc.message if isinstance(exc, VerifyError) else str(exc)
        body = {
            "schema": VERDICT_SCHEMA,
            "status": "REFUSED",
            "code": code,
            "message": message,
            "bootstrapAuthenticated": False,
            "actualSupplierQualified": False,
            "physicalExecutionObserved": False,
            "authority": "none",
        }
        data = pretty_bytes(body)
        if output is not None:
            try:
                write_new(output, data)
            except Exception:
                pass
        sys.stdout.buffer.write(data)
        return 2



if __name__ == "__main__":
    raise SystemExit(main())
