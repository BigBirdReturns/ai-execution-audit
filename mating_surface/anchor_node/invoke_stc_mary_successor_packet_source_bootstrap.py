"""Externally measure the successor launcher, then execute only those bytes.

For compile the launcher and receipt verifier are retrieved from the exact admitted Git
commit.  For every packet operation they are read from the packet only after this
bootstrap independently reproduces the complete packet-carried source set and requires
equality with the authenticated source admission.  Ambient repository source bytes are
never an execution fallback.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

AUTHORITY = "none"
PROFILE_REPOSITORY_PATH = "mating_surface/anchor_node/stc-mary-successor-packet-flight-01-profile-01.json"
PROFILE_PACKET_PATH = "anchor_node/stc-mary-successor-packet-flight-01-profile-01.json"
LAUNCHER_REPOSITORY_PATH = "mating_surface/anchor_node/invoke_stc_mary_successor_packet_source.py"
LAUNCHER_PACKET_PATH = "anchor_node/invoke_stc_mary_successor_packet_source.py"
VERIFIER_REPOSITORY_PATH = "mating_surface/anchor_node/verify_stc_mary_successor_execution_receipt.py"
VERIFIER_PACKET_PATH = "anchor_node/verify_stc_mary_successor_execution_receipt.py"
SOURCE_ADMISSION_PACKET_PATH = "lineage/SOURCE-ADMISSION.json"
SOURCE_SET_PACKET_PATH = "lineage/SUCCESSOR-SOURCE-SET.json"
SOURCE_ROOT = "lineage/successor-source"
MAX_JSON_BYTES = 64 * 1024 * 1024
MAX_MEMBER_BYTES = 8 * 1024 * 1024

MEASURED_SOURCE_LAUNCHER = r"""
import sys
source = sys.stdin.buffer.read()
if not (sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.flags.dont_write_bytecode == 1):
    raise SystemExit("measured bootstrap child flags differ")
namespace = {"__name__": "__main__", "__file__": "<externally-measured-successor-source>"}
exec(compile(source, namespace["__file__"], "exec"), namespace)
"""


class LauncherBootstrapError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def fail(code: str, message: str) -> None:
    raise LauncherBootstrapError(code, message)


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        fail(code, message)


def require_git_object_id(
    value: Any, object_format: Any, lengths: Mapping[str, Any], *, code: str, label: str
) -> str:
    require(
        isinstance(object_format, str)
        and isinstance(lengths, Mapping)
        and object_format in lengths
        and lengths == {"sha1": 40, "sha256": 64},
        code,
        f"{label} object-format law differs",
    )
    require(
        isinstance(value, str)
        and len(value) == lengths[object_format]
        and all(character in "0123456789abcdef" for character in value),
        code,
        f"{label} is not one exact full {object_format} object identifier",
    )
    return value


def require_source_object_ids(profile: Mapping[str, Any], admission: Mapping[str, Any]) -> str:
    source_law = profile["sourceAdmission"]
    lengths = source_law["gitObjectIdLengths"]
    object_format = admission.get("gitObjectFormat")
    require_git_object_id(
        admission.get("sourceCommit"), object_format, lengths,
        code="SOURCE_COMMIT_INVALID", label="source admission commit",
    )
    require_git_object_id(
        admission.get("sourceTree"), object_format, lengths,
        code="SOURCE_TREE_INVALID", label="source admission tree",
    )
    require_git_object_id(
        admission.get("profileGitBlob"), object_format, lengths,
        code="SOURCE_PROFILE_BLOB_INVALID", label="source admission profile blob",
    )
    for row in admission.get("members", []):
        require(isinstance(row, Mapping), "SOURCE_ADMISSION_INVALID", "source member row is invalid")
        require_git_object_id(
            row.get("gitBlob"), object_format, lengths,
            code="SOURCE_BLOB_IDENTITY_INVALID", label="source admission member blob",
        )
    return object_format


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def canonical_json_bytes(value: Any) -> bytes:
    return (canonical_json(value) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def content_id(prefix: str, value: Any) -> str:
    return f"{prefix}_{sha256_bytes(canonical_json(value).encode('utf-8'))}"


def assert_identity(value: Mapping[str, Any], key: str, prefix: str, *, code: str, label: str) -> str:
    body = dict(value)
    observed = body.pop(key, None)
    require(isinstance(observed, str) and observed == content_id(prefix, body), code, f"{label} identity differs")
    return observed


def read_bytes(path: Path, maximum: int, *, code: str, label: str) -> bytes:
    require(not path.is_symlink() and path.is_file(), code, f"{label} is not a regular file")
    data = path.read_bytes()
    require(len(data) <= maximum, code, f"{label} exceeds the bounded allocation")
    return data


def read_json(path: Path, *, code: str, label: str, canonical: bool = False) -> Mapping[str, Any]:
    raw = read_bytes(path, MAX_JSON_BYTES, code=code, label=label)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(code, f"{label} is not UTF-8 JSON: {exc}")
        raise
    require(isinstance(value, Mapping), code, f"{label} must be an object")
    if canonical:
        require(raw == canonical_json_bytes(value), code, f"{label} is not canonical JSON")
    return value


def git(repository: Path, arguments: list[str], *, code: str, label: str) -> bytes:
    completed = subprocess.run(
        ["git", "-c", f"safe.directory={repository}", "-C", str(repository), *arguments],
        check=False,
        capture_output=True,
        env=scrubbed_environment(),
    )
    require(completed.returncode == 0, code, f"{label} is unavailable from the Git object database")
    return completed.stdout


def scrubbed_environment() -> dict[str, str]:
    admitted = {
        "COMSPEC", "LANG", "LC_ALL", "PATH", "PATHEXT", "SYSTEMDRIVE", "SYSTEMROOT",
        "TEMP", "TMP", "TMPDIR", "WINDIR",
    }
    return {key: value for key, value in os.environ.items() if key.upper() in admitted}


def member_row(admission: Mapping[str, Any], repository_path: str, packet_path: str) -> Mapping[str, Any]:
    rows = [
        row for row in admission.get("members", [])
        if isinstance(row, Mapping)
        and row.get("repositoryPath") == repository_path
        and row.get("packetPath") == packet_path
    ]
    require(len(rows) == 1, "MEASURED_SOURCE_MEMBER_INVALID", f"{repository_path} does not resolve to exactly one admitted row")
    return rows[0]


def require_row_bytes(row: Mapping[str, Any], data: bytes, *, label: str) -> None:
    require(
        row.get("sha256") == sha256_bytes(data) and row.get("bytes") == len(data),
        "MEASURED_SOURCE_MEMBER_DRIFT",
        f"{label} bytes differ from the authenticated source-admission row",
    )


def compile_material(
    repository: Path, source_admission_path: Path,
) -> tuple[Mapping[str, Any], Mapping[str, Any], bytes, bytes]:
    admission = read_json(source_admission_path, code="SOURCE_ADMISSION_INVALID", label="source admission", canonical=True)
    require(
        admission.get("status") == "PASS"
        and admission.get("bootstrapAuthenticated") is True
        and admission.get("workingTreeBytesTrusted") is False
        and admission.get("authority") == AUTHORITY,
        "SOURCE_ADMISSION_INVALID",
        "compile requires an externally authenticated exact-Git source admission",
    )
    commit = admission.get("sourceCommit")
    require(isinstance(commit, str), "SOURCE_COMMIT_INVALID", "source admission carries no exact commit")
    profile_bytes = git(repository, ["cat-file", "blob", f"{commit}:{PROFILE_REPOSITORY_PATH}"], code="SOURCE_PROFILE_ABSENT", label="source profile")
    try:
        profile = json.loads(profile_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail("SOURCE_PROFILE_INVALID", str(exc))
        raise
    require(isinstance(profile, Mapping), "SOURCE_PROFILE_INVALID", "source profile is not an object")
    admission_law = profile["sourceAdmission"]
    require(set(admission) == set(admission_law["receiptKeys"]), "SOURCE_ADMISSION_INVALID", "source admission field denominator differs")
    assert_identity(admission, admission_law["idKey"], admission_law["idPrefix"], code="SOURCE_ADMISSION_IDENTITY_INVALID", label="source admission")
    require(admission.get("profileCanonicalSha256") == sha256_bytes(canonical_json_bytes(profile)), "SOURCE_PROFILE_MISMATCH", "source admission names another profile")
    object_format = require_source_object_ids(profile, admission)
    measured_format = git(
        repository, ["rev-parse", "--show-object-format"],
        code="SOURCE_OBJECT_FORMAT_INVALID", label="repository object format",
    ).decode("ascii").strip()
    require(
        measured_format == object_format,
        "SOURCE_OBJECT_FORMAT_MISMATCH",
        "source admission object format differs from the repository",
    )
    profile_blob = git(
        repository, ["rev-parse", "--verify", f"{commit}:{PROFILE_REPOSITORY_PATH}"],
        code="SOURCE_PROFILE_ABSENT", label="source profile blob",
    ).decode("ascii").strip()
    require_git_object_id(
        profile_blob, object_format, admission_law["gitObjectIdLengths"],
        code="SOURCE_PROFILE_BLOB_INVALID", label="measured source profile blob",
    )
    require(
        profile_blob == admission["profileGitBlob"],
        "SOURCE_PROFILE_MISMATCH",
        "source admission profile blob differs from the exact Git object",
    )
    launcher = git(repository, ["cat-file", "blob", f"{commit}:{LAUNCHER_REPOSITORY_PATH}"], code="LAUNCHER_GIT_OBJECT_ABSENT", label="launcher")
    verifier = git(repository, ["cat-file", "blob", f"{commit}:{VERIFIER_REPOSITORY_PATH}"], code="EXECUTION_VERIFIER_GIT_OBJECT_ABSENT", label="execution receipt verifier")
    for repository_path, packet_path, data, label in (
        (LAUNCHER_REPOSITORY_PATH, LAUNCHER_PACKET_PATH, launcher, "launcher"),
        (VERIFIER_REPOSITORY_PATH, VERIFIER_PACKET_PATH, verifier, "execution receipt verifier"),
    ):
        row = member_row(admission, repository_path, packet_path)
        require_row_bytes(row, data, label=label)
        blob = git(repository, ["rev-parse", "--verify", f"{commit}:{repository_path}"], code="SOURCE_MEMBER_ABSENT", label=label).decode("ascii").strip()
        require_git_object_id(
            blob, object_format, admission_law["gitObjectIdLengths"],
            code="SOURCE_BLOB_IDENTITY_INVALID", label=f"measured {label} blob",
        )
        require(blob == row.get("gitBlob"), "MEASURED_SOURCE_GIT_BLOB_MISMATCH", f"{label} Git blob differs")
    return profile, admission, launcher, verifier


def packet_material(packet: Path) -> tuple[Mapping[str, Any], Mapping[str, Any], bytes, bytes]:
    root = packet / SOURCE_ROOT
    profile = read_json(root / PROFILE_PACKET_PATH, code="PACKET_SOURCE_PROFILE_INVALID", label="packet source profile")
    admission = read_json(packet / SOURCE_ADMISSION_PACKET_PATH, code="SOURCE_ADMISSION_INVALID", label="packet source admission", canonical=True)
    stored = read_json(packet / SOURCE_SET_PACKET_PATH, code="PACKET_SOURCE_SET_INVALID", label="packet source set", canonical=True)
    require(
        admission.get("status") == "PASS"
        and admission.get("bootstrapAuthenticated") is True
        and admission.get("workingTreeBytesTrusted") is False,
        "SOURCE_ADMISSION_INVALID",
        "packet source admission is not externally authenticated",
    )
    admission_law = profile["sourceAdmission"]
    require(set(admission) == set(admission_law["receiptKeys"]), "SOURCE_ADMISSION_INVALID", "packet source admission field denominator differs")
    assert_identity(admission, admission_law["idKey"], admission_law["idPrefix"], code="SOURCE_ADMISSION_IDENTITY_INVALID", label="packet source admission")
    require(admission.get("profileCanonicalSha256") == sha256_bytes(canonical_json_bytes(profile)), "PACKET_SOURCE_PROFILE_MISMATCH", "packet source admission names another profile")
    require_source_object_ids(profile, admission)
    mapping = profile.get("successorSourceMembers")
    require(isinstance(mapping, Mapping), "PACKET_SOURCE_PROFILE_INVALID", "source member mapping is absent")
    require(len(mapping) == profile.get("successorSourceMemberDenominator"), "PACKET_SOURCE_MEMBER_DENOMINATOR_INVALID", "declared source denominator differs")
    expected_present = set(mapping.values())
    present = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
    require(present == expected_present, "PACKET_SOURCE_MEMBER_DENOMINATOR_INVALID", "packet source tree is incomplete or has extra members")
    admitted_mapping = [(row.get("repositoryPath"), row.get("packetPath")) for row in admission.get("members", []) if isinstance(row, Mapping)]
    require(admitted_mapping == sorted(mapping.items()), "PACKET_SOURCE_MEMBER_SUBSTITUTED", "packet source mapping differs from source admission")
    rows: list[dict[str, Any]] = []
    for repository_path, packet_path in sorted(mapping.items()):
        row = member_row(admission, repository_path, packet_path)
        data = read_bytes(root / packet_path, MAX_MEMBER_BYTES, code="PACKET_SOURCE_MEMBER_INVALID", label=packet_path)
        require_row_bytes(row, data, label=packet_path)
        rows.append({"relativePath": packet_path, "sha256": sha256_bytes(data), "bytes": len(data)})
    lineage = profile["lineage"]
    body = {
        "schema": lineage["sourceSetSchema"],
        "profileId": profile["packet"]["packetProfileId"],
        "members": sorted(rows, key=lambda row: row["relativePath"]),
        "memberCount": len(rows),
        "totalBytes": sum(row["bytes"] for row in rows),
        "authority": AUTHORITY,
        "claimBoundary": lineage["sourceSetClaimBoundary"],
    }
    measured = {**body, lineage["sourceSetIdKey"]: content_id(lineage["sourceSetIdPrefix"], body)}
    require(dict(stored) == measured, "PACKET_SOURCE_SET_MISMATCH", "packet-carried source set does not reproduce completely")
    require(measured[lineage["sourceSetIdKey"]] == admission.get("successorSourceSetId"), "PACKET_SOURCE_ADMISSION_MISMATCH", "packet source set differs from admitted source receipt")
    launcher = read_bytes(root / LAUNCHER_PACKET_PATH, MAX_MEMBER_BYTES, code="PACKET_LAUNCHER_INVALID", label="packet launcher")
    verifier = read_bytes(root / VERIFIER_PACKET_PATH, MAX_MEMBER_BYTES, code="PACKET_EXECUTION_VERIFIER_INVALID", label="packet execution receipt verifier")
    return profile, admission, launcher, verifier


def run_measured(source: bytes, arguments: list[str], *, foreign: Path) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-c", MEASURED_SOURCE_LAUNCHER, *arguments],
        input=source,
        cwd=foreign,
        env=scrubbed_environment(),
        check=False,
        capture_output=True,
    )


def execute(
    *, role: str, execution_receipt: Path, module_args: list[str], packet: Path | None,
    repository: Path | None, source_admission_receipt: Path | None,
) -> int:
    if role == "compile":
        require(repository is not None and source_admission_receipt is not None, "COMPILE_SOURCE_CUSTODY_INCOMPLETE", "compile requires repository and source admission")
        profile, _admission, launcher, verifier = compile_material(repository, source_admission_receipt)
    else:
        require(packet is not None, "PACKET_REQUIRED", "packet operation requires a packet")
        profile, _admission, launcher, verifier = packet_material(packet)
    require(role in profile["executionCustody"]["roles"], "MODULE_ROLE_UNADMITTED", "requested operation role is not admitted")
    require(sha256_bytes(launcher) != sha256_bytes(Path(__file__).read_bytes()), "LAUNCHER_SELF_AUTHENTICATION", "external bootstrap may not be the measured launcher")

    with tempfile.TemporaryDirectory(prefix="stc-mary-launcher-bootstrap-") as foreign_name:
        foreign = Path(foreign_name)
        profile_path = foreign / "profile.json"
        profile_path.write_bytes(canonical_json_bytes(profile))
        launcher_args = [
            "--role", role,
            "--execution-receipt", str(execution_receipt),
        ]
        if packet is not None:
            launcher_args.extend(["--packet", str(packet)])
        if repository is not None:
            launcher_args.extend(["--repository-root", str(repository)])
        if source_admission_receipt is not None:
            launcher_args.extend(["--source-admission-receipt", str(source_admission_receipt)])
        launcher_args.extend(["--", *module_args])
        launched = run_measured(launcher, launcher_args, foreign=foreign)
        sys.stdout.buffer.write(launched.stdout)
        sys.stderr.buffer.write(launched.stderr)
        require(launched.returncode == 0, "MEASURED_LAUNCHER_REFUSED", "externally measured launcher refused")
        require(execution_receipt.is_file(), "EXECUTION_RECEIPT_ABSENT", "measured launcher emitted no final execution receipt")

        verifier_args = [
            "--execution-receipt", str(execution_receipt),
            "--expected-role", role,
            "--profile", str(profile_path),
        ]
        if packet is not None:
            verifier_args.extend(["--packet", str(packet)])
        else:
            verifier_args.extend(["--source-admission-receipt", str(source_admission_receipt)])
        verified = run_measured(verifier, verifier_args, foreign=foreign)
        require(verified.returncode == 0, "EXECUTION_RECEIPT_VERIFIER_REFUSED", verified.stdout.decode("utf-8", "replace"))
    return 0


def refusal(code: str, message: str) -> dict[str, Any]:
    return {
        "schema": "stc-mary/successor-launcher-bootstrap/1",
        "status": "REFUSED",
        "code": code,
        "message": message,
        "ambientRepositorySourceTrusted": False,
        "authority": AUTHORITY,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Externally measure and execute one successor operation launcher")
    parser.add_argument("--role", required=True)
    parser.add_argument("--execution-receipt", type=Path, required=True)
    parser.add_argument("--packet", type=Path)
    parser.add_argument("--repository-root", type=Path)
    parser.add_argument("--source-admission-receipt", type=Path)
    parser.add_argument("module_args", nargs=argparse.REMAINDER)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    module_args = list(args.module_args)
    if module_args[:1] == ["--"]:
        module_args.pop(0)
    try:
        return execute(
            role=args.role,
            execution_receipt=args.execution_receipt,
            module_args=module_args,
            packet=args.packet,
            repository=args.repository_root,
            source_admission_receipt=args.source_admission_receipt,
        )
    except LauncherBootstrapError as exc:
        sys.stdout.buffer.write(canonical_json_bytes(refusal(exc.code, str(exc))))
        return 1
    except (OSError, ValueError, KeyError) as exc:
        sys.stdout.buffer.write(canonical_json_bytes(refusal("LAUNCHER_BOOTSTRAP_FILESYSTEM_ERROR", str(exc))))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
