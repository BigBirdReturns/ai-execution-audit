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

ISOLATED_MODULE_LAUNCHER = r"""
import pathlib
import sys
module_path = pathlib.Path(sys.argv[1])
module_args = sys.argv[2:]
source = sys.stdin.buffer.read()
if not (sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.flags.dont_write_bytecode == 1):
    raise SystemExit("isolated child flags differ")
sys.path[:] = [str(module_path.parent), *[entry for entry in sys.path if entry and entry != str(module_path.parent)]]
sys.argv = [str(module_path), *module_args]
namespace = {"__name__": "__main__", "__file__": str(module_path)}
exec(compile(source, str(module_path), "exec"), namespace)
"""

MUTATING_ROLES = {"materialize-or-resume", "record-or-resume", "seal-or-resume"}


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
    completed = subprocess.run(
        ["git", "-c", f"safe.directory={repository}", "-C", str(repository), *arguments],
        check=False,
        capture_output=True,
        env=scrubbed_environment(),
    )
    require(completed.returncode == 0, code, f"{label} is unavailable from the Git object database")
    return completed.stdout


def git_text(repository: Path, arguments: list[str], *, code: str, label: str) -> str:
    try:
        return git(repository, arguments, code=code, label=label).decode("ascii").strip()
    except UnicodeDecodeError:
        fail(code, f"{label} is not ASCII Git metadata")
        raise


def scrubbed_environment() -> dict[str, str]:
    """Retain only process-launch essentials; Python and user import inputs are absent."""
    admitted = {
        "COMSPEC", "LANG", "LC_ALL", "PATH", "PATHEXT", "SYSTEMDRIVE", "SYSTEMROOT",
        "TEMP", "TMP", "TMPDIR", "WINDIR",
    }
    return {key: value for key, value in os.environ.items() if key.upper() in admitted}


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
    role: str, repository_module_path: str, packet_module_path: str,
    module_git_blob_id: str, module_sha256: str, packet_id: str | None,
) -> dict[str, Any]:
    custody = profile["executionCustody"]
    body = {
        "schema": custody["schema"], "status": "PASS",
        "packetId": packet_id, "sourceAdmissionId": receipt[profile["sourceAdmission"]["idKey"]],
        "sourceCommit": receipt["sourceCommit"], "sourceTree": receipt["sourceTree"],
        "gitObjectFormat": receipt["gitObjectFormat"],
        "successorSourceSetId": measured[profile["lineage"]["sourceSetIdKey"]],
        "completeMeasuredSourceSetId": measured[profile["lineage"]["sourceSetIdKey"]],
        "operationRole": role,
        "repositoryRelativeModulePath": repository_module_path,
        "packetRelativeModulePath": packet_module_path,
        "moduleGitBlobId": module_git_blob_id,
        "moduleSha256": module_sha256,
        "processTerminal": "PASS",
        "isolated": 1,
        "noSite": 1,
        "dontWriteBytecode": 1,
        "ambientRepositorySourceTrusted": False,
        "authority": AUTHORITY,
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
    source_path: Path | None = None
    foreign_path: Path | None = None
    with tempfile.TemporaryDirectory(prefix="stc-mary-successor-source-") as source_temporary, tempfile.TemporaryDirectory(prefix="stc-mary-successor-foreign-") as foreign_temporary:
        source_path = Path(source_temporary)
        foreign_path = Path(foreign_temporary)
        if role == "compile":
            require(repository is not None and source_admission_receipt is not None, "COMPILE_SOURCE_CUSTODY_INCOMPLETE", "compile requires repository and source admission")
            profile, receipt, measured = compile_source(repository=repository, receipt_path=source_admission_receipt, destination=source_path)
            packet_id = None
        else:
            require(packet is not None, "PACKET_REQUIRED", "post-compilation execution requires the packet")
            profile, receipt, measured = packet_source(packet=packet, destination=source_path)
            marker = read_json(packet / PACKET_MARKER_PATH, code="PACKET_MARKER_INVALID", label="packet marker")
            packet_id = marker.get("packetId") if isinstance(marker.get("packetId"), str) else None
        custody = profile["executionCustody"]
        roles = custody["roles"]
        require(set(roles) == set(custody["roleDenominator"]) and len(roles) == 10, "MODULE_ROLE_MAP_INVALID", "the final role map is not the exact ten-role denominator")
        require(role in roles, "MODULE_ROLE_UNADMITTED", "requested module role is not admitted")
        role_mapping = roles[role]
        repository_module_path = role_mapping["repositoryPath"]
        packet_module_path = role_mapping["packetPath"]
        require(
            profile["successorSourceMembers"].get(repository_module_path) == packet_module_path,
            "MODULE_ROLE_UNADMITTED",
            "module role does not name one exact source member",
        )
        module = source_path / packet_module_path
        module_data = read_bytes(module, MAX_MEMBER_BYTES, code="MEASURED_MODULE_ABSENT", label="measured module")
        matching_rows = [
            row for row in receipt["members"]
            if row.get("repositoryPath") == repository_module_path and row.get("packetPath") == packet_module_path
        ]
        require(len(matching_rows) == 1, "MEASURED_MODULE_MEMBER_INVALID", "module does not resolve to exactly one admitted member row")
        module_row = matching_rows[0]
        require(
            module_row["sha256"] == sha256_bytes(module_data),
            "MEASURED_MODULE_MEMBER_INVALID",
            "measured module bytes differ from the admitted member row",
        )
        result = execution_receipt(
            profile=profile,
            receipt=receipt,
            measured=measured,
            role=role,
            repository_module_path=repository_module_path,
            packet_module_path=packet_module_path,
            module_git_blob_id=module_row["gitBlob"],
            module_sha256=sha256_bytes(module_data),
            packet_id=packet_id,
        )
        provisional = foreign_path / "execution-receipt.json"
        provisional.write_bytes(canonical_json_bytes(result))
        replaced_args = [str(source_path / PROFILE_PACKET_PATH) if value == "@profile" else value for value in module_args]
        if role in MUTATING_ROLES:
            require("--source-execution-receipt" not in replaced_args, "SOURCE_EXECUTION_RECEIPT_DUPLICATED", "launcher owns the source execution receipt argument")
            replaced_args.extend(["--source-execution-receipt", str(provisional)])
        completed = subprocess.run(
            [sys.executable, "-I", "-S", "-B", "-c", ISOLATED_MODULE_LAUNCHER, str(module), *replaced_args],
            cwd=foreign_path,
            input=module_data,
            env=scrubbed_environment(),
            check=False,
            capture_output=True,
        )
    sys.stdout.buffer.write(completed.stdout)
    sys.stderr.buffer.write(completed.stderr)
    require(completed.returncode == 0, "MEASURED_PROCESS_REFUSED", f"measured {role} process refused")
    require(source_path is not None and not source_path.exists(), "TEMPORARY_SOURCE_TREE_RETAINED", "temporary execution source tree was not deleted")
    require(foreign_path is not None and not foreign_path.exists(), "FOREIGN_EXECUTION_DIRECTORY_RETAINED", "foreign execution directory was not deleted")
    execution_receipt_path.parent.mkdir(parents=True, exist_ok=True)
    execution_receipt_path.write_bytes(canonical_json_bytes(result))
    return result


def refusal(code: str, message: str) -> dict[str, Any]:
    return {"schema": "stc-mary/successor-execution-receipt/1", "status": "REFUSED", "code": code,
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
