"""Admit successor source exclusively from one exact Git commit.

Until this law, the identity of the successor source set was measured over working-tree
bytes. A working tree is whatever the checkout machinery last wrote: the same commit
yields different bytes under different line-ending configuration, and an edited file
changes the measured identity without any recorded transaction naming the change. An
identity that moves when nobody committed anything is not a custody claim.

This verifier derives the admitted source identity from Git objects and from nothing
else:

    the source commit, named by its full object identifier; abbreviation is refused
    the commit's exact tree
    the successor profile blob inside that tree, re-identified by blob and by
        canonical digest
    every source member the profile declares, read through ``git cat-file blob``
        at its exact commit-scoped path

Working-tree bytes never reach the receipt. A mutated checkout, a CRLF smudge, or a
staged-but-uncommitted edit changes nothing this verifier measures, and the same
commit produces the same ``successorSourceSetId`` on every platform.

Like the other verifiers in this source set, it imports nothing from the shared
construction law. It cannot authenticate itself: run directly it reports
``bootstrapAuthenticated: false``, and only its own bootstrap -- which retrieves this
verifier's bytes from the exact source commit and executes them isolated -- may flip
that field.

It writes nothing, records nothing, seals nothing, and grants no authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

AUTHORITY = "none"
MINIMUM_PYTHON = (3, 12)
# One full object identifier per admitted object format. A shorter spelling may resolve
# today and resolve to something else after one more object lands, so abbreviation is a
# refusal, never a convenience.
OBJECT_ID_LENGTH = {"sha1": 40, "sha256": 64}
RELATIVE_MEMBER_RE = re.compile(r"^[A-Za-z0-9.][A-Za-z0-9._/-]{0,255}$")
MAX_MEMBER_BYTES = 8 * 1024 * 1024
PROFILE_SCHEMA = "stc-mary/successor-packet-flight-profile/1"
PROFILE_ID = "stc-mary/successor-packet-flight-01@1"
PROFILE_PATH = "mating_surface/anchor_node/stc-mary-successor-packet-flight-01-profile-01.json"
RECEIPT_SCHEMA = "stc-mary/successor-source-admission/1"
RECEIPT_ID_KEY = "sourceAdmissionId"
RECEIPT_ID_PREFIX = "stcmarysuccessorsourceadmission1"
CLAIM_BOUNDARY = (
    "Exact Git-object admission of one successor source set. It identifies source bytes "
    "and their commit and tree ancestry, trusts no working-tree byte, establishes no merge "
    "or approval state, and grants no authority."
)


class SourceAdmissionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def fail(code: str, message: str) -> None:
    raise SourceAdmissionError(code, message)


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        fail(code, message)


def require_git_object_id(value: Any, object_format: str, *, code: str, label: str) -> str:
    """Require one full lowercase object ID under the repository's declared format."""
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


def sign(body: Mapping[str, Any], id_key: str, prefix: str) -> dict[str, Any]:
    require(id_key not in body, "OBJECT_ALREADY_SIGNED", f"body already carries {id_key}")
    return {**body, id_key: content_id(prefix, body)}


def exact_keys(value: Any, expected: Iterable[str], code: str, label: str) -> Mapping[str, Any]:
    require(isinstance(value, Mapping), code, f"{label} must be an object")
    require(set(value) == set(expected), code, f"{label} field denominator differs")
    return value


def git(repository: Path, arguments: list[str], *, code: str, label: str) -> bytes:
    try:
        completed = subprocess.run(
            ["git", "-c", f"safe.directory={repository}", "-C", str(repository), *arguments],
            check=False,
            capture_output=True,
        )
    except OSError as exc:
        fail(code, f"{label} could not invoke Git: {exc}")
        raise
    require(completed.returncode == 0, code, f"{label} is unavailable from the repository object database")
    return completed.stdout


def git_text(repository: Path, arguments: list[str], *, code: str, label: str) -> str:
    raw = git(repository, arguments, code=code, label=label)
    try:
        return raw.decode("ascii").strip()
    except UnicodeDecodeError:
        fail(code, f"{label} is not ASCII Git metadata")
        raise


def require_repository_root(repository: Path) -> Path:
    try:
        repository = Path(os.path.abspath(os.fspath(repository)))
    except (OSError, ValueError) as exc:
        fail("SOURCE_REPOSITORY_INVALID", f"repository coordinate is invalid: {exc}")
        raise
    top = git_text(repository, ["rev-parse", "--show-toplevel"], code="SOURCE_REPOSITORY_INVALID", label="repository")
    top_path = Path(os.path.abspath(top))
    try:
        same_root = os.path.samefile(top_path, repository)
    except OSError:
        same_root = False
    require(
        same_root,
        "SOURCE_REPOSITORY_SUBSTITUTED",
        "the supplied coordinate is not the object database's exact worktree root",
    )
    return repository


def require_relative(path: Any, *, code: str, label: str) -> str:
    require(
        isinstance(path, str)
        and "\\" not in path
        and all(part not in ("", ".", "..") for part in Path(path).parts)
        and RELATIVE_MEMBER_RE.fullmatch(path) is not None,
        code,
        f"{label} is not an admitted relative path",
    )
    return path


def object_type(repository: Path, object_id: str, *, code: str, label: str) -> str:
    return git_text(repository, ["cat-file", "-t", object_id], code=code, label=label)


def blob_at(
    repository: Path, commit: str, relative: str, *, object_format: str, label: str
) -> tuple[str, bytes]:
    require_relative(relative, code="SOURCE_MEMBER_PATH_INVALID", label=label)
    spec = f"{commit}:{relative}"
    blob_id = git_text(repository, ["rev-parse", "--verify", spec], code="SOURCE_MEMBER_ABSENT", label=label)
    require_git_object_id(
        blob_id, object_format, code="SOURCE_BLOB_IDENTITY_INVALID", label=f"{label} blob identity"
    )
    require(
        object_type(repository, blob_id, code="SOURCE_OBJECT_TYPE_INVALID", label=label) == "blob",
        "SOURCE_OBJECT_TYPE_INVALID",
        f"{label} is not a Git blob",
    )
    data = git(repository, ["cat-file", "blob", spec], code="SOURCE_MEMBER_ABSENT", label=label)
    require(len(data) <= MAX_MEMBER_BYTES, "SOURCE_MEMBER_TOO_LARGE", f"{label} exceeds the bounded allocation")
    return blob_id, data


def source_set(profile: Mapping[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    lineage = profile["lineage"]
    body = {
        "schema": lineage["sourceSetSchema"],
        "profileId": profile["packet"]["packetProfileId"],
        "members": [
            {"relativePath": row["packetPath"], "sha256": row["sha256"], "bytes": row["bytes"]}
            for row in sorted(rows, key=lambda entry: entry["packetPath"])
        ],
        "memberCount": len(rows),
        "totalBytes": sum(row["bytes"] for row in rows),
        "authority": AUTHORITY,
        "claimBoundary": lineage["sourceSetClaimBoundary"],
    }
    return sign(body, lineage["sourceSetIdKey"], lineage["sourceSetIdPrefix"])


def object_format(repository: Path) -> str:
    """Read the repository's Git object format; the receipt binds it explicitly."""
    observed = git_text(
        repository,
        ["rev-parse", "--show-object-format"],
        code="SOURCE_OBJECT_FORMAT_INVALID",
        label="repository object format",
    )
    require(
        observed in OBJECT_ID_LENGTH,
        "SOURCE_OBJECT_FORMAT_INVALID",
        "the repository object format is not an admitted Git object format",
    )
    return observed


def admit_source(*, repository: Path, source_commit: str) -> dict[str, Any]:
    require(sys.version_info[:2] >= MINIMUM_PYTHON, "PYTHON_RUNTIME_UNSUPPORTED", "Python 3.12 or newer is required")
    repository = require_repository_root(repository)
    git_object_format = object_format(repository)
    require_git_object_id(
        source_commit,
        git_object_format,
        code="SOURCE_COMMIT_NOT_FULL",
        label="source commit",
    )
    require(
        object_type(repository, source_commit, code="SOURCE_COMMIT_UNKNOWN", label="source commit") == "commit",
        "SOURCE_COMMIT_OBJECT_TYPE_INVALID",
        "source commit is not a commit object",
    )
    source_tree = git_text(repository, ["show", "-s", "--format=%T", source_commit], code="SOURCE_TREE_INVALID", label="source tree")
    require_git_object_id(
        source_tree, git_object_format, code="SOURCE_TREE_INVALID", label="source tree identity"
    )
    require(
        object_type(repository, source_tree, code="SOURCE_TREE_INVALID", label="source tree") == "tree",
        "SOURCE_TREE_OBJECT_TYPE_INVALID",
        "source tree is not a tree object",
    )

    profile_blob, profile_bytes = blob_at(
        repository, source_commit, PROFILE_PATH,
        object_format=git_object_format, label="successor profile",
    )
    try:
        profile = json.loads(profile_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail("SOURCE_PROFILE_INVALID", f"successor profile is not UTF-8 JSON: {exc}")
        raise
    require(isinstance(profile, Mapping), "SOURCE_PROFILE_INVALID", "successor profile must be an object")
    require(
        profile.get("schema") == PROFILE_SCHEMA and profile.get("profileId") == PROFILE_ID,
        "SOURCE_PROFILE_INVALID",
        "successor profile identity differs",
    )
    require(profile.get("authority") == AUTHORITY, "AUTHORITY_WIDENED", "successor profile grants authority")
    admission_law = profile.get("sourceAdmission")
    require(isinstance(admission_law, Mapping), "SOURCE_ADMISSION_LAW_INVALID", "source-admission law is absent")
    require(
        admission_law.get("schema") == RECEIPT_SCHEMA
        and admission_law.get("idKey") == RECEIPT_ID_KEY
        and admission_law.get("idPrefix") == RECEIPT_ID_PREFIX
        and admission_law.get("profilePath") == PROFILE_PATH,
        "SOURCE_ADMISSION_LAW_INVALID",
        "source-admission law differs",
    )
    require(
        admission_law.get("gitObjectIdLengths") == OBJECT_ID_LENGTH,
        "SOURCE_ADMISSION_LAW_INVALID",
        "source-admission object-format law differs",
    )
    members = profile.get("successorSourceMembers")
    denominator = profile.get("successorSourceMemberDenominator")
    require(isinstance(members, Mapping) and members, "SOURCE_MEMBER_DENOMINATOR_INVALID", "source member mapping is absent")
    require(len(members) == denominator, "SOURCE_MEMBER_DENOMINATOR_INVALID", "declared source member denominator differs")
    require(len(set(members.values())) == len(members), "SOURCE_PACKET_PATH_SUBSTITUTED", "two members name one packet path")

    rows: list[dict[str, Any]] = []
    for repository_path, packet_path in sorted(members.items()):
        repository_path = require_relative(repository_path, code="SOURCE_REPOSITORY_PATH_SUBSTITUTED", label="repository source path")
        packet_path = require_relative(packet_path, code="SOURCE_PACKET_PATH_SUBSTITUTED", label="packet source path")
        blob_id, data = blob_at(
            repository, source_commit, repository_path,
            object_format=git_object_format, label=f"source member {repository_path}",
        )
        rows.append(
            {
                "repositoryPath": repository_path,
                "packetPath": packet_path,
                "gitBlob": blob_id,
                "sha256": sha256_bytes(data),
                "bytes": len(data),
            }
        )
    measured_set = source_set(profile, rows)
    body = {
        "schema": RECEIPT_SCHEMA,
        "status": "PASS",
        "gitObjectFormat": git_object_format,
        "sourceCommit": source_commit,
        "sourceTree": source_tree,
        "profilePath": PROFILE_PATH,
        "profileGitBlob": profile_blob,
        "profileCanonicalSha256": sha256_bytes(canonical_json_bytes(profile)),
        "declaredSourceMemberDenominator": denominator,
        "members": rows,
        "memberCount": len(rows),
        "totalBytes": sum(row["bytes"] for row in rows),
        "successorSourceSetId": measured_set[profile["lineage"]["sourceSetIdKey"]],
        "workingTreeBytesTrusted": False,
        "bootstrapAuthenticated": False,
        "bootstrapVerifierSha256": None,
        "authority": AUTHORITY,
        "claimBoundary": CLAIM_BOUNDARY,
    }
    receipt = sign(body, RECEIPT_ID_KEY, RECEIPT_ID_PREFIX)
    exact_keys(receipt, admission_law["receiptKeys"], "SOURCE_ADMISSION_RECEIPT_INVALID", "source-admission receipt")
    return receipt


def refusal(code: str, message: str) -> dict[str, Any]:
    return {"schema": RECEIPT_SCHEMA, "status": "REFUSED", "code": code, "message": message,
            "bootstrapAuthenticated": False, "workingTreeBytesTrusted": False, "authority": AUTHORITY}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Admit STC-MARY successor source from one exact Git commit")
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--out", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        receipt = admit_source(repository=args.repository_root, source_commit=args.source_commit)
        data = canonical_json_bytes(receipt)
        if args.out is None:
            sys.stdout.buffer.write(data)
        else:
            require(not args.out.exists(), "SOURCE_ADMISSION_OUTPUT_EXISTS", "source-admission output must not exist")
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_bytes(data)
        return 0
    except SourceAdmissionError as exc:
        sys.stdout.buffer.write(canonical_json_bytes(refusal(exc.code, str(exc))))
        return 1
    except (OSError, ValueError) as exc:
        sys.stdout.buffer.write(canonical_json_bytes(refusal("SOURCE_ADMISSION_FILESYSTEM_ERROR", str(exc))))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
