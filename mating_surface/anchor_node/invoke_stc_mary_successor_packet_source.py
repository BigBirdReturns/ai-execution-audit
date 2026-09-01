"""Execute successor operations only from one complete measured source tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping

AUTHORITY = "none"
PROFILE_PACKET_PATH = "anchor_node/stc-mary-successor-packet-flight-01-profile-01.json"
SOURCE_ADMISSION_PACKET_PATH = "lineage/SOURCE-ADMISSION.json"
SOURCE_SET_PACKET_PATH = "lineage/SUCCESSOR-SOURCE-SET.json"
PACKET_MARKER_PATH = "PACKET-ROOT.json"
MAX_MEMBER_BYTES = 8 * 1024 * 1024
MAX_JSON_BYTES = 64 * 1024 * 1024
CLAIM_BOUNDARY = (
    "Measured execution custody for one closed successor operation. It proves which admitted "
    "packet-carried or exact-Git module ran from one complete isolated source tree and records "
    "the process terminal. It grants no authority."
)


class ExecutionCustodyError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def fail(code: str, message: str) -> None:
    raise ExecutionCustodyError(code, message)


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        fail(code, message)


def canonical_json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        fail("NON_CANONICAL_JSON", str(exc))
        raise


def canonical_json_bytes(value: Any) -> bytes:
    return (canonical_json(value) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def content_id(prefix: str, value: Any) -> str:
    return f"{prefix}_{sha256_bytes(canonical_json(value).encode('utf-8'))}"


def body_without(value: Mapping[str, Any], key: str) -> dict[str, Any]:
    body = dict(value)
    body.pop(key, None)
    return body


def exact_keys(value: Any, expected: Iterable[str], code: str, label: str) -> Mapping[str, Any]:
    require(isinstance(value, Mapping), code, f"{label} must be an object")
    require(set(value) == set(expected), code, f"{label} field denominator differs")
    return value


def assert_identity(value: Mapping[str, Any], key: str, prefix: str, code: str, label: str) -> str:
    observed = value.get(key)
    require(isinstance(observed, str) and observed == content_id(prefix, body_without(value, key)), code, f"{label} identity differs")
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


def safe_relative(value: Any, *, code: str, label: str) -> str:
    require(isinstance(value, str) and value and "\\" not in value, code, f"{label} is invalid")
    parts = Path(value).parts
    require(all(part not in ("", ".", "..") for part in parts), code, f"{label} escapes the source root")
    return value


def git(repository: Path, arguments: list[str], *, code: str, label: str) -> bytes:
    completed = subprocess.run(["git", "-C", str(repository), *arguments], check=False, capture_output=True)
    require(completed.returncode == 0, code, f"{label} is unavailable from the Git object database")
    return completed.stdout


def git_text(repository: Path, arguments: list[str], *, code: str, label: str) -> str:
    try:
        return git(repository, arguments, code=code, label=label).decode("ascii").strip()
    except UnicodeDecodeError:
        fail(code, f"{label} is not ASCII Git metadata")
        raise


def validate_profile_and_receipt(
    profile: Mapping[str, Any], receipt: Mapping[str, Any]
) -> tuple[str, Mapping[str, Any], Mapping[str, Any]]:
    admission_law = profile["sourceAdmission"]
    custody_law = profile["executionCustody"]
    exact_keys(receipt, admission_law["receiptKeys"], "SOURCE_ADMISSION_RECEIPT_INVALID", "source-admission receipt")
    admission_id = assert_identity(
        receipt, admission_law["idKey"], admission_law["idPrefix"],
        "SOURCE_ADMISSION_IDENTITY_INVALID", "source-admission receipt",
    )
    require(
        receipt["schema"] == admission_law["schema"]
        and receipt["status"] == "PASS"
        and receipt["bootstrapAuthenticated"] is True
        and receipt["workingTreeBytesTrusted"] is False
        and receipt["authority"] == AUTHORITY,
        "SOURCE_ADMISSION_RECEIPT_INVALID",
        "source admission is not a bootstrap-authenticated no-working-tree receipt",
    )
    require(
        receipt["profileCanonicalSha256"] == sha256_bytes(canonical_json_bytes(profile)),
        "SOURCE_PROFILE_MISMATCH", "source admission names another successor profile",
    )
    return admission_id, admission_law, custody_law


def measure_set(profile: Mapping[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
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
    return {**body, lineage["sourceSetIdKey"]: content_id(lineage["sourceSetIdPrefix"], body)}


def compile_source(
    *, repository: Path, receipt_path: Path, destination: Path
) -> tuple[Mapping[str, Any], Mapping[str, Any], dict[str, Any]]:
    receipt = read_json(receipt_path, code="SOURCE_ADMISSION_RECEIPT_INVALID", label="source-admission receipt", canonical=True)
    commit = receipt.get("sourceCommit")
    require(isinstance(commit, str), "SOURCE_COMMIT_INVALID", "source admission carries no commit")
    profile_path = receipt.get("profilePath")
    require(isinstance(profile_path, str), "SOURCE_PROFILE_PATH_INVALID", "source admission carries no profile path")
    profile_bytes = git(repository, ["cat-file", "blob", f"{commit}:{profile_path}"], code="SOURCE_PROFILE_ABSENT", label="source profile")
    try:
        profile = json.loads(profile_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail("SOURCE_PROFILE_INVALID", str(exc))
        raise
    require(isinstance(profile, Mapping), "SOURCE_PROFILE_INVALID", "source profile is not an object")
    validate_profile_and_receipt(profile, receipt)
    tree = git_text(repository, ["show", "-s", "--format=%T", commit], code="SOURCE_TREE_INVALID", label="source tree")
    require(tree == receipt["sourceTree"], "SOURCE_TREE_MISMATCH", "source receipt tree differs from the commit")
    expected = sorted(profile["successorSourceMembers"].items())
    observed = [(row.get("repositoryPath"), row.get("packetPath")) for row in receipt["members"]]
    require(observed == expected, "SOURCE_MEMBER_SUBSTITUTED", "source receipt mapping differs from the profile")
    measured_rows: list[dict[str, Any]] = []
    for row in receipt["members"]:
        repository_path = safe_relative(row["repositoryPath"], code="SOURCE_MEMBER_PATH_INVALID", label="repository path")
        packet_path = safe_relative(row["packetPath"], code="SOURCE_MEMBER_PATH_INVALID", label="packet path")
        blob = git_text(repository, ["rev-parse", "--verify", f"{commit}:{repository_path}"], code="SOURCE_MEMBER_ABSENT", label=repository_path)
        data = git(repository, ["cat-file", "blob", f"{commit}:{repository_path}"], code="SOURCE_MEMBER_ABSENT", label=repository_path)
        require(blob == row["gitBlob"], "SOURCE_BLOB_IDENTITY_MISMATCH", f"Git blob differs: {repository_path}")
        require(sha256_bytes(data) == row["sha256"] and len(data) == row["bytes"], "SOURCE_MEMBER_DRIFT", f"Git blob bytes differ: {repository_path}")
        target = destination / packet_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        measured_rows.append({"relativePath": packet_path, "sha256": row["sha256"], "bytes": row["bytes"]})
    measured = measure_set(profile, measured_rows)
    require(measured[profile["lineage"]["sourceSetIdKey"]] == receipt["successorSourceSetId"], "SOURCE_SET_MISMATCH", "Git blobs do not reproduce the admitted source set")
    return profile, receipt, measured


def packet_source(
    *, packet: Path, destination: Path
) -> tuple[Mapping[str, Any], Mapping[str, Any], dict[str, Any]]:
    source_root = packet / "lineage" / "successor-source"
    profile = read_json(source_root / PROFILE_PACKET_PATH, code="PACKET_SOURCE_PROFILE_INVALID", label="packet source profile")
    receipt = read_json(packet / SOURCE_ADMISSION_PACKET_PATH, code="SOURCE_ADMISSION_RECEIPT_INVALID", label="packet source admission", canonical=True)
    admission_id, admission_law, _ = validate_profile_and_receipt(profile, receipt)
    stored_set = read_json(packet / SOURCE_SET_PACKET_PATH, code="PACKET_SOURCE_SET_INVALID", label="packet source set", canonical=True)
    lineage = profile["lineage"]
    assert_identity(stored_set, lineage["sourceSetIdKey"], lineage["sourceSetIdPrefix"], "PACKET_SOURCE_SET_INVALID", "packet source set")
    expected_mapping = sorted(profile["successorSourceMembers"].items())
    observed_mapping = [(row.get("repositoryPath"), row.get("packetPath")) for row in receipt["members"]]
    require(observed_mapping == expected_mapping, "SOURCE_MEMBER_SUBSTITUTED", "packet source admission mapping differs")
    stored_by_path = {row.get("relativePath"): row for row in stored_set.get("members", []) if isinstance(row, Mapping)}
    require(set(stored_by_path) == set(profile["successorSourceMembers"].values()), "PACKET_SOURCE_MEMBER_DENOMINATOR_INVALID", "packet source set is incomplete")
    measured_rows: list[dict[str, Any]] = []
    present = {path.relative_to(source_root).as_posix() for path in source_root.rglob("*") if path.is_file()}
    require(present == set(stored_by_path), "PACKET_SOURCE_MEMBER_DENOMINATOR_INVALID", "packet source tree has missing or unexpected members")
    for row in receipt["members"]:
        packet_path = safe_relative(row["packetPath"], code="PACKET_SOURCE_PATH_INVALID", label="packet source path")
        data = read_bytes(source_root / packet_path, MAX_MEMBER_BYTES, code="PACKET_SOURCE_MEMBER_INVALID", label=packet_path)
        stored = stored_by_path.get(packet_path)
        require(
            stored is not None
            and sha256_bytes(data) == row["sha256"] == stored.get("sha256")
            and len(data) == row["bytes"] == stored.get("bytes"),
            "PACKET_SOURCE_MEMBER_DRIFT", f"packet source member differs: {packet_path}",
        )
        target = destination / packet_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        measured_rows.append({"relativePath": packet_path, "sha256": row["sha256"], "bytes": row["bytes"]})
    measured = measure_set(profile, measured_rows)
    require(dict(stored_set) == measured, "PACKET_SOURCE_SET_MISMATCH", "packet source set does not reproduce")
    require(measured[lineage["sourceSetIdKey"]] == receipt["successorSourceSetId"], "SOURCE_ADMISSION_SOURCE_SET_MISMATCH", "packet source differs from Git admission")
    return profile, receipt, measured


def execution_receipt(
    *, profile: Mapping[str, Any], receipt: Mapping[str, Any], measured: Mapping[str, Any],
    role: str, module_path: str, module_sha256: str, packet_id: str | None,
    exit_code: int, stdout: bytes, stderr: bytes, temporary_deleted: bool,
) -> dict[str, Any]:
    custody = profile["executionCustody"]
    body = {
        "schema": custody["schema"], "status": "PASS" if exit_code == 0 else "REFUSED",
        "packetId": packet_id, "sourceAdmissionId": receipt[profile["sourceAdmission"]["idKey"]],
        "sourceCommit": receipt["sourceCommit"], "sourceTree": receipt["sourceTree"],
        "successorSourceSetId": measured[profile["lineage"]["sourceSetIdKey"]],
        "completeMeasuredSourceSetIdentity": measured[profile["lineage"]["sourceSetIdKey"]],
        "measuredSourceMemberCount": measured["memberCount"], "measuredSourceTotalBytes": measured["totalBytes"],
        "moduleRole": role, "modulePath": module_path, "moduleSha256": module_sha256,
        "processExitCode": exit_code, "processTerminal": "PASS" if exit_code == 0 else "REFUSED",
        "stdoutSha256": sha256_bytes(stdout), "stderrSha256": sha256_bytes(stderr),
        "temporarySourceTreeDeleted": temporary_deleted, "authority": AUTHORITY,
        "claimBoundary": custody["claimBoundary"],
    }
    result = {**body, custody["idKey"]: content_id(custody["idPrefix"], body)}
    exact_keys(result, custody["receiptKeys"], "EXECUTION_CUSTODY_RECEIPT_INVALID", "execution-custody receipt")
    return result


def execute(
    *, role: str, execution_receipt_path: Path, module_args: list[str], packet: Path | None = None,
    repository: Path | None = None, source_admission_receipt: Path | None = None,
) -> dict[str, Any]:
    require(not execution_receipt_path.exists(), "EXECUTION_RECEIPT_EXISTS", "execution-custody receipt output exists")
    temporary_path: Path | None = None
    with tempfile.TemporaryDirectory(prefix="stc-mary-successor-execution-") as temporary:
        temporary_path = Path(temporary)
        if role == "compile":
            require(repository is not None and source_admission_receipt is not None, "COMPILE_SOURCE_CUSTODY_INCOMPLETE", "compile requires repository and source admission")
            profile, receipt, measured = compile_source(repository=repository, receipt_path=source_admission_receipt, destination=temporary_path)
            packet_id = None
        else:
            require(packet is not None, "PACKET_REQUIRED", "post-compilation execution requires the packet")
            profile, receipt, measured = packet_source(packet=packet, destination=temporary_path)
            marker = read_json(packet / PACKET_MARKER_PATH, code="PACKET_MARKER_INVALID", label="packet marker")
            packet_id = marker.get("packetId") if isinstance(marker.get("packetId"), str) else None
        custody = profile["executionCustody"]
        roles = custody["roles"]
        require(role in roles, "MODULE_ROLE_UNADMITTED", "requested module role is not admitted")
        module_path = roles[role]
        require(module_path in profile["successorSourceMembers"].values(), "MODULE_ROLE_UNADMITTED", "module role does not name a source member")
        module = temporary_path / module_path
        module_data = read_bytes(module, MAX_MEMBER_BYTES, code="MEASURED_MODULE_ABSENT", label="measured module")
        replaced_args = [str(temporary_path / PROFILE_PACKET_PATH) if value == "@profile" else value for value in module_args]
        environment = {key: value for key, value in os.environ.items() if key.upper() not in ("PYTHONPATH", "PYTHONHOME")}
        environment["PYTHONNOUSERSITE"] = "1"
        completed = subprocess.run(
            [sys.executable, "-I", "-B", str(module), *replaced_args], cwd=temporary_path,
            env=environment, check=False, capture_output=True,
        )
    temporary_deleted = temporary_path is not None and not temporary_path.exists()
    result = execution_receipt(
        profile=profile, receipt=receipt, measured=measured, role=role, module_path=module_path,
        module_sha256=sha256_bytes(module_data), packet_id=packet_id, exit_code=completed.returncode,
        stdout=completed.stdout, stderr=completed.stderr, temporary_deleted=temporary_deleted,
    )
    execution_receipt_path.parent.mkdir(parents=True, exist_ok=True)
    execution_receipt_path.write_bytes(canonical_json_bytes(result))
    sys.stdout.buffer.write(completed.stdout)
    sys.stderr.buffer.write(completed.stderr)
    require(completed.returncode == 0, "MEASURED_PROCESS_REFUSED", f"measured {role} process refused")
    require(temporary_deleted, "TEMPORARY_SOURCE_TREE_RETAINED", "temporary execution source tree was not deleted")
    return result


def refusal(code: str, message: str) -> dict[str, Any]:
    return {"schema": "stc-mary/successor-execution-custody/1", "status": "REFUSED", "code": code,
            "message": message, "authority": AUTHORITY}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one closed successor role from measured source custody")
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
        execute(
            role=args.role, execution_receipt_path=args.execution_receipt,
            module_args=module_args, packet=args.packet, repository=args.repository_root,
            source_admission_receipt=args.source_admission_receipt,
        )
        return 0
    except ExecutionCustodyError as exc:
        sys.stdout.buffer.write(canonical_json_bytes(refusal(exc.code, str(exc))))
        return 1
    except (OSError, ValueError) as exc:
        sys.stdout.buffer.write(canonical_json_bytes(refusal("EXECUTION_CUSTODY_FILESYSTEM_ERROR", str(exc))))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
