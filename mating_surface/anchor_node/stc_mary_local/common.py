from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

TOOLCHAIN_SCHEMA = "stc-mary-local-toolchain/1"
TOOLCHAIN_PROFILE_ID = "stc-mary/local-toolchain/0.1"
ADMITTED_PACKET_COMMIT = "66fa5a477752d07b0fff5ab4553e50505a42d2f7"
PRIVATE_ROOT_PATTERN = re.compile(r"^stc-mary-local-(?:prep|feed|plan)-[a-z0-9][a-z0-9._-]*$", re.I)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CONTENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*_[0-9a-f]{64}$")
MAX_COMMAND_BYTES = 4 * 1024 * 1024
MAX_HASH_FILES = 250_000
MAX_HASH_BYTES = 8 * 1024**4
MAX_FEED_BYTES = 16 * 1024**3
FEATURE_MAGIC = b"STCMARY1"
FEATURE_HEADER = struct.Struct("<8sIIIIQ")
BACKENDS = ("python", "numpy", "torch-cpu", "torch-cuda")
STAGES = (
    "VERIFY_INPUTS",
    "MOUNT_PERSONAL_FLOOR",
    "BIND_GRACE",
    "RUN_PERSONAL_FLOOR_BASELINE",
    "ATTACH_HALO3",
    "RUN_HALO3_ACCELERATED",
    "REMOVE_HALO3",
    "VERIFY_PERSONAL_FLOOR_CONTINUITY",
    "REMOVE_LATTICE",
    "VERIFY_LOCAL_CONTINUITY",
    "PARTITION_TWO_CELLS",
    "RESTORE_LINK_HOLD_CONFLICT",
    "REPLACE_HEAD",
    "REBUILD_PROJECTIONS",
    "COLD_SUCCESSOR_VERIFY",
    "SEAL_PRIVATE_EVIDENCE",
)


class ToolchainError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise ToolchainError(code, message)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def content_id(prefix: str, value: Any) -> str:
    return f"{prefix}_{hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()}"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ToolchainError("JSON_READ_INVALID", f"cannot read JSON {path}: {error}") from error


def assert_sha256(value: Any, code: str, label: str) -> str:
    require(isinstance(value, str) and SHA256_RE.fullmatch(value) is not None, code, f"{label} is not a lowercase SHA-256 digest")
    return value


def assert_content_id(value: Any, code: str, label: str) -> str:
    require(isinstance(value, str) and CONTENT_ID_RE.fullmatch(value) is not None, code, f"{label} is not a content identity")
    return value


def stable_keys(value: Mapping[str, Any], expected: Sequence[str], code: str, label: str) -> None:
    require(isinstance(value, Mapping), code, f"{label} must be an object")
    require(set(value.keys()) == set(expected), code, f"{label} fields differ")


def bounded_string(value: Any, code: str, label: str, max_length: int = 8192) -> str:
    require(isinstance(value, str), code, f"{label} must be a string")
    normalized = value.strip()
    require(0 < len(normalized) <= max_length, code, f"{label} is empty or unbounded")
    return normalized


def safe_int(value: Any, minimum: int, maximum: int, code: str, label: str) -> int:
    require(isinstance(value, int) and not isinstance(value, bool) and minimum <= value <= maximum, code, f"{label} is outside {minimum}..{maximum}")
    return value


def stream_sha256(path: Path) -> tuple[str, int]:
    metadata = path.stat()
    require(path.is_file(), "ARTIFACT_NOT_FILE", f"artifact is not a regular file: {path}")
    require(0 < metadata.st_size <= MAX_HASH_BYTES, "ARTIFACT_SIZE_INVALID", f"artifact is empty or unbounded: {path}")
    digest = hashlib.sha256()
    count = 0
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            count += len(chunk)
            digest.update(chunk)
    require(count == metadata.st_size, "ARTIFACT_CHANGED_DURING_HASH", f"artifact changed while hashing: {path}")
    return digest.hexdigest(), count


def is_inside(ancestor: Path, target: Path) -> bool:
    try:
        target.relative_to(ancestor)
        return True
    except ValueError:
        return False


def validate_new_private_root(path: Path, *, repository_root: Path | None = None) -> Path:
    resolved = path.expanduser().resolve()
    require(PRIVATE_ROOT_PATTERN.fullmatch(resolved.name) is not None, "PRIVATE_ROOT_NAME_INVALID", "private root must use stc-mary-local-prep-*, stc-mary-local-feed-*, or stc-mary-local-plan-*")
    require(resolved != Path(resolved.anchor), "PRIVATE_ROOT_UNSAFE", "private root may not be a filesystem root")
    require(resolved != Path.home().resolve(), "PRIVATE_ROOT_UNSAFE", "private root may not be the user home")
    require(resolved != Path.cwd().resolve(), "PRIVATE_ROOT_UNSAFE", "private root may not be the current working directory")
    if repository_root is not None:
        repository_root = repository_root.expanduser().resolve()
        require(not is_inside(repository_root, resolved), "PRIVATE_ROOT_IN_REPOSITORY", "private root must remain outside the public repository")
        require(not is_inside(resolved, repository_root), "PRIVATE_ROOT_UNSAFE", "private root may not contain the public repository")
    require(resolved.parent.is_dir(), "PRIVATE_ROOT_PARENT_MISSING", "private root parent must already exist")
    require(not resolved.exists(), "PRIVATE_ROOT_EXISTS", "private root already exists")
    return resolved


def executable(name: str) -> str | None:
    return shutil.which(name)


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    available: bool
    returncode: int | None
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool

    def private_record(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "available": self.available,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "durationSeconds": round(self.duration_seconds, 6),
            "timedOut": self.timed_out,
        }

    def public_record(self) -> dict[str, Any]:
        body = self.private_record()
        raw = canonical_json(body).encode("utf-8")
        return {
            "available": self.available,
            "returncode": self.returncode,
            "durationSeconds": round(self.duration_seconds, 6),
            "timedOut": self.timed_out,
            "receiptSha256": sha256_bytes(raw),
            "receiptBytes": len(raw),
        }


def run_command(command: Sequence[str], *, timeout: float = 20.0, cwd: Path | None = None) -> CommandResult:
    command = [str(item) for item in command]
    program = executable(command[0]) if not Path(command[0]).is_absolute() else command[0]
    if not program:
        return CommandResult(command, False, None, "", "", 0.0, False)
    actual = [program, *command[1:]]
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            actual,
            cwd=str(cwd) if cwd else None,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
            text=False,
            env=os.environ.copy(),
        )
        duration = time.perf_counter() - started
        return CommandResult(
            command,
            True,
            completed.returncode,
            completed.stdout[:MAX_COMMAND_BYTES].decode("utf-8", errors="replace"),
            completed.stderr[:MAX_COMMAND_BYTES].decode("utf-8", errors="replace"),
            duration,
            False,
        )
    except subprocess.TimeoutExpired as error:
        duration = time.perf_counter() - started
        stdout = (error.stdout or b"")[:MAX_COMMAND_BYTES].decode("utf-8", errors="replace") if isinstance(error.stdout, (bytes, bytearray)) else str(error.stdout or "")[:MAX_COMMAND_BYTES]
        stderr = (error.stderr or b"")[:MAX_COMMAND_BYTES].decode("utf-8", errors="replace") if isinstance(error.stderr, (bytes, bytearray)) else str(error.stderr or "")[:MAX_COMMAND_BYTES]
        return CommandResult(command, True, None, stdout, stderr, duration, True)


def powershell_executable() -> str | None:
    return executable("pwsh") or executable("powershell")


def run_powershell(script: str, *, timeout: float = 30.0) -> CommandResult:
    shell = powershell_executable()
    if not shell:
        return CommandResult(["powershell", "-NoProfile", "-Command", script], False, None, "", "", 0.0, False)
    return run_command([shell, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", script], timeout=timeout)


def parse_json_output(result: CommandResult) -> Any:
    if not result.available or result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def hash_artifact(label: str, path: Path) -> dict[str, Any]:
    label = bounded_string(label, "ARTIFACT_LABEL_INVALID", "artifact label", 128)
    resolved = path.expanduser().resolve()
    require(resolved.exists(), "ARTIFACT_MISSING", f"artifact is absent: {resolved}")
    require(not resolved.is_symlink(), "ARTIFACT_SYMLINK_REFUSED", f"artifact symlink is refused: {resolved}")
    if resolved.is_file():
        sha, size = stream_sha256(resolved)
        body = {
            "schema": "stc-mary-local-artifact-manifest/1",
            "label": label,
            "kind": "file",
            "files": [{"relativePath": resolved.name, "sha256": sha, "bytes": size}],
            "fileCount": 1,
            "totalBytes": size,
            "authority": "none",
            "claimBoundary": "Private local artifact identity. The path and body remain outside public Git.",
        }
        return {**body, "artifactId": content_id("stcmarylocalartifact1", body), "privatePath": str(resolved)}
    require(resolved.is_dir(), "ARTIFACT_TYPE_INVALID", f"artifact is neither file nor directory: {resolved}")
    files: list[dict[str, Any]] = []
    total = 0
    for candidate in sorted(resolved.rglob("*"), key=lambda row: row.as_posix().lower()):
        require(not candidate.is_symlink(), "ARTIFACT_SYMLINK_REFUSED", f"artifact tree contains symlink: {candidate}")
        if not candidate.is_file():
            continue
        require(len(files) < MAX_HASH_FILES, "ARTIFACT_FILE_DENOMINATOR_UNBOUNDED", "artifact tree exceeds file denominator")
        sha, size = stream_sha256(candidate)
        total += size
        require(total <= MAX_HASH_BYTES, "ARTIFACT_SIZE_INVALID", "artifact tree exceeds byte denominator")
        files.append({"relativePath": candidate.relative_to(resolved).as_posix(), "sha256": sha, "bytes": size})
    require(files, "ARTIFACT_TREE_EMPTY", f"artifact tree contains no regular files: {resolved}")
    body = {
        "schema": "stc-mary-local-artifact-manifest/1",
        "label": label,
        "kind": "directory",
        "files": files,
        "fileCount": len(files),
        "totalBytes": total,
        "authority": "none",
        "claimBoundary": "Private local artifact-tree identity. Paths and bodies remain outside public Git.",
    }
    return {**body, "artifactId": content_id("stcmarylocalartifact1", body), "privatePath": str(resolved)}


def artifact_public_projection(artifact: Mapping[str, Any]) -> dict[str, Any]:
    body = {key: value for key, value in artifact.items() if key != "privatePath"}
    return {
        "artifactId": artifact["artifactId"],
        "label": artifact["label"],
        "kind": artifact["kind"],
        "fileCount": artifact["fileCount"],
        "totalBytes": artifact["totalBytes"],
        "manifestSha256": sha256_bytes(canonical_json(body).encode("utf-8")),
    }


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]
