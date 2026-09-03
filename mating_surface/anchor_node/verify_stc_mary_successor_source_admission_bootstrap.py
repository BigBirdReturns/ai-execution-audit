"""Measure and execute the source-admission verifier from one exact Git commit.

The source-admission verifier cannot authenticate itself, and unlike the packet
verifier it may not even be trusted from the working tree it sits in: the whole point
of the law it enforces is that checkout bytes are not custody. This bootstrap therefore
retrieves the verifier's bytes from the exact source commit through Git object
plumbing, digests them, pipes exactly those bytes into a fresh isolated interpreter
with a foreign working directory, and only then compares three things:

    the bytes it executed
    the Git blob the source commit carries at the verifier's path
    the member row the measured receipt declares for that path

Only when all three are one object does it annotate the receipt as
bootstrap-authenticated. A receipt whose inner verifier claimed authentication for
itself, or whose declared verifier row differs from the executed bytes, is refused.

It admits nothing on its own behalf and grants no authority.
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
MINIMUM_PYTHON = (3, 12)
OBJECT_ID_LENGTH = {"sha1": 40, "sha256": 64}
VERIFIER_PATH = "mating_surface/anchor_node/verify_stc_mary_successor_source_admission.py"
RECEIPT_SCHEMA = "stc-mary/successor-source-admission/1"
RECEIPT_ID_KEY = "sourceAdmissionId"
RECEIPT_ID_PREFIX = "stcmarysuccessorsourceadmission1"
BOOTSTRAP_SCHEMA = "stc-mary/successor-source-admission-bootstrap/1"

ISOLATED_LAUNCHER = r"""
import sys
source = sys.stdin.buffer.read()
namespace = {
    "__name__": "__main__",
    "__file__": "<measured-stc-mary-successor-source-admission>",
    "_STC_MARY_MEASURED_SOURCE_ADMISSION_VERIFIER_BYTES": source,
}
exec(compile(source, namespace["__file__"], "exec"), namespace)
"""


class BootstrapError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def fail(code: str, message: str) -> None:
    raise BootstrapError(code, message)


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        fail(code, message)


def require_git_object_id(value: Any, object_format: str, *, code: str, label: str) -> str:
    require(
        object_format in OBJECT_ID_LENGTH,
        "SOURCE_OBJECT_FORMAT_INVALID",
        "the repository object format is not admitted",
    )
    require(
        isinstance(value, str)
        and len(value) == OBJECT_ID_LENGTH[object_format]
        and all(character in "0123456789abcdef" for character in value),
        code,
        f"{label} is not one exact full {object_format} object identifier",
    )
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def canonical_json_bytes(value: Any) -> bytes:
    return (canonical_json(value) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def content_id(prefix: str, value: Any) -> str:
    return f"{prefix}_{sha256_bytes(canonical_json(value).encode('utf-8'))}"


def scrubbed_environment() -> dict[str, str]:
    admitted = {
        "COMSPEC", "LANG", "LC_ALL", "PATH", "PATHEXT", "SYSTEMDRIVE", "SYSTEMROOT",
        "TEMP", "TMP", "TMPDIR", "WINDIR",
    }
    return {key: value for key, value in os.environ.items() if key.upper() in admitted}


def git(repository: Path, arguments: list[str], *, code: str) -> bytes:
    completed = subprocess.run(
        ["git", "-c", f"safe.directory={repository}", "-C", str(repository), *arguments],
        check=False,
        capture_output=True,
        env=scrubbed_environment(),
    )
    require(completed.returncode == 0, code, "the requested verifier blob is unavailable")
    return completed.stdout


def verifier_blob(repository: Path, source_commit: str) -> tuple[str, bytes]:
    """Retrieve the verifier from the exact source commit, never from a checkout path."""
    object_format = git(
        repository, ["rev-parse", "--show-object-format"], code="SOURCE_OBJECT_FORMAT_INVALID"
    ).decode("ascii").strip()
    require_git_object_id(
        source_commit, object_format, code="SOURCE_COMMIT_NOT_FULL", label="source commit"
    )
    kind = git(repository, ["cat-file", "-t", source_commit], code="SOURCE_COMMIT_UNKNOWN").decode("ascii").strip()
    require(kind == "commit", "SOURCE_COMMIT_OBJECT_TYPE_INVALID", "source commit is not a commit object")
    blob_id = (
        git(repository, ["rev-parse", "--verify", f"{source_commit}:{VERIFIER_PATH}"],
            code="SOURCE_ADMISSION_VERIFIER_ABSENT")
        .decode("ascii")
        .strip()
    )
    require_git_object_id(
        blob_id, object_format,
        code="SOURCE_ADMISSION_VERIFIER_BLOB_INVALID", label="source-admission verifier blob",
    )
    data = git(
        repository, ["cat-file", "blob", f"{source_commit}:{VERIFIER_PATH}"],
        code="SOURCE_ADMISSION_VERIFIER_ABSENT",
    )
    return blob_id, data


def annotate_authenticated(
    receipt: Mapping[str, Any], *, source_commit: str, executed_sha256: str,
    executed_bytes_count: int, executed_blob_id: str,
) -> dict[str, Any]:
    """Admit one measured receipt as bootstrap-authenticated, or refuse.

    This is the gate the isolated execution's output must pass: the receipt must be the
    inner verifier's own (self-authentication refused), it must name the exact commit
    this bootstrap executed from, and its declared member row for the verifier path must
    be the Git blob and the bytes this process actually ran.
    """
    require(isinstance(receipt, Mapping), "SOURCE_ADMISSION_RECEIPT_INVALID", "receipt is not an object")
    require(receipt.get("schema") == RECEIPT_SCHEMA, "SOURCE_ADMISSION_RECEIPT_INVALID", "receipt schema differs")
    require(receipt.get("sourceCommit") == source_commit, "SOURCE_ADMISSION_COMMIT_MISMATCH", "receipt names another commit")
    object_format = receipt.get("gitObjectFormat")
    require(isinstance(object_format, str), "SOURCE_OBJECT_FORMAT_INVALID", "receipt carries no object format")
    require_git_object_id(
        source_commit, object_format, code="SOURCE_COMMIT_NOT_FULL", label="source commit"
    )
    require_git_object_id(
        receipt.get("sourceTree"), object_format,
        code="SOURCE_TREE_INVALID", label="source-admission tree",
    )
    require_git_object_id(
        receipt.get("profileGitBlob"), object_format,
        code="SOURCE_PROFILE_BLOB_INVALID", label="source-admission profile blob",
    )
    rows = receipt.get("members")
    require(isinstance(rows, list), "SOURCE_ADMISSION_RECEIPT_INVALID", "member rows are absent")
    for row in rows:
        require(isinstance(row, Mapping), "SOURCE_ADMISSION_RECEIPT_INVALID", "member row is not an object")
        require_git_object_id(
            row.get("gitBlob"), object_format,
            code="SOURCE_BLOB_IDENTITY_INVALID", label="source-admission member blob",
        )
    require_git_object_id(
        executed_blob_id, object_format,
        code="SOURCE_ADMISSION_VERIFIER_BLOB_INVALID", label="executed verifier blob",
    )
    require(receipt.get("bootstrapAuthenticated") is False, "SOURCE_ADMISSION_SELF_AUTHENTICATED", "inner verifier self-authenticated")
    require(receipt.get("bootstrapVerifierSha256") is None, "SOURCE_ADMISSION_SELF_AUTHENTICATED", "inner verifier supplied an external digest")
    verifier_rows = [row for row in rows if isinstance(row, Mapping) and row.get("repositoryPath") == VERIFIER_PATH]
    require(len(verifier_rows) == 1, "SOURCE_ADMISSION_VERIFIER_MEMBER_INVALID", "receipt does not declare one verifier member")
    require(
        verifier_rows[0].get("sha256") == executed_sha256
        and verifier_rows[0].get("bytes") == executed_bytes_count
        and verifier_rows[0].get("gitBlob") == executed_blob_id,
        "EXECUTED_VERIFIER_BYTES_DIFFER",
        "executed verifier bytes differ from the admitted verifier Git blob and member row",
    )
    body = dict(receipt)
    body.pop(RECEIPT_ID_KEY, None)
    body["bootstrapAuthenticated"] = True
    body["bootstrapVerifierSha256"] = executed_sha256
    return {**body, RECEIPT_ID_KEY: content_id(RECEIPT_ID_PREFIX, body)}


def authenticate(*, repository: Path, source_commit: str) -> dict[str, Any]:
    require(sys.version_info[:2] >= MINIMUM_PYTHON, "PYTHON_RUNTIME_UNSUPPORTED", "Python 3.12 or newer is required")
    repository = Path(os.path.abspath(os.fspath(repository)))
    executed_blob_id, measured = verifier_blob(repository, source_commit)
    observed = sha256_bytes(measured)
    with tempfile.TemporaryDirectory(prefix="stc-mary-source-admission-bootstrap-") as foreign:
        completed = subprocess.run(
            [sys.executable, "-I", "-S", "-B", "-c", ISOLATED_LAUNCHER, "--repository-root", str(repository),
             "--source-commit", source_commit],
            input=measured,
            cwd=foreign,
            check=False,
            capture_output=True,
            env=scrubbed_environment(),
        )
    require(
        completed.returncode == 0,
        "MEASURED_SOURCE_ADMISSION_VERIFIER_REFUSED",
        completed.stdout.decode("utf-8", "replace"),
    )
    try:
        receipt = json.loads(completed.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail("SOURCE_ADMISSION_RECEIPT_INVALID", f"measured verifier emitted invalid JSON: {exc}")
        raise
    return annotate_authenticated(
        receipt,
        source_commit=source_commit,
        executed_sha256=observed,
        executed_bytes_count=len(measured),
        executed_blob_id=executed_blob_id,
    )


def refusal(code: str, message: str) -> dict[str, Any]:
    return {"schema": BOOTSTRAP_SCHEMA, "status": "REFUSED", "code": code, "message": message,
            "bootstrapAuthenticated": False, "authority": AUTHORITY}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap-authenticate exact Git-blob successor source admission")
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--out", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        receipt = authenticate(repository=args.repository_root, source_commit=args.source_commit)
        data = canonical_json_bytes(receipt)
        if args.out is None:
            sys.stdout.buffer.write(data)
        else:
            require(not args.out.exists(), "SOURCE_ADMISSION_OUTPUT_EXISTS", "source-admission output must not exist")
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_bytes(data)
        return 0
    except BootstrapError as exc:
        sys.stdout.buffer.write(canonical_json_bytes(refusal(exc.code, str(exc))))
        return 1
    except (OSError, ValueError) as exc:
        sys.stdout.buffer.write(canonical_json_bytes(refusal("SOURCE_ADMISSION_BOOTSTRAP_ERROR", str(exc))))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
