from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

PROFILE_ID = "stc-mary/offline-cell-successor-carrier/0.1"
PROFILE_SCHEMA = "stc-mary-offline-carrier-profile/1"
PREDECESSOR_COMMIT = "c7f95de862e47307e6f6a0f07fcd7aa456e9a88f"
ATTESTATION_MODES = {"synthetic_simulation", "private_local_attested"}
COMMANDS = (
    "template-inputs",
    "build-cell-pair",
    "verify-cell",
    "reconcile-cells",
    "build-successor",
    "verify-successor",
    "validate-profile",
)
BUNDLE_TYPES = ("cell", "successor")
ABSENT_DEPENDENCIES = (
    "WAN",
    "AWS",
    "Lattice",
    "remote_model_provider",
    "original_host",
    "repository_history",
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CONTENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*_[0-9a-f]{64}$")
PRIVATE_ROOT_RE = re.compile(
    r"^stc-mary-(?:offline|reunion|successor)-[a-z0-9][a-z0-9._-]*$",
    re.IGNORECASE,
)
MAX_FILES = 250_000
MAX_BYTES = 8 * 1024**4
MAX_STRING = 8192
MAX_ACTION_BYTES = 64 * 1024


class OfflineCarrierError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise OfflineCarrierError(code, message)


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def content_id(prefix: str, value: Any) -> str:
    return f"{prefix}_{sha256_bytes(canonical_json(value).encode('utf-8'))}"


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise OfflineCarrierError("JSON_READ_INVALID", f"cannot read JSON {path}: {error}") from error


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def stable_keys(value: Any, expected: Iterable[str], code: str, label: str) -> None:
    require(isinstance(value, Mapping), code, f"{label} must be an object")
    require(set(value.keys()) == set(expected), code, f"{label} fields differ")


def bounded_string(
    value: Any,
    code: str,
    label: str,
    maximum: int = MAX_STRING,
) -> str:
    require(isinstance(value, str), code, f"{label} must be a string")
    normalized = value.strip()
    require(0 < len(normalized) <= maximum, code, f"{label} is empty or unbounded")
    return normalized


def safe_int(value: Any, minimum: int, maximum: int, code: str, label: str) -> int:
    require(
        isinstance(value, int)
        and not isinstance(value, bool)
        and minimum <= value <= maximum,
        code,
        f"{label} is outside {minimum}..{maximum}",
    )
    return value


def assert_sha256(value: Any, code: str, label: str) -> str:
    require(
        isinstance(value, str) and SHA256_RE.fullmatch(value) is not None,
        code,
        f"{label} is not a lowercase SHA-256 digest",
    )
    return value


def assert_content_id(value: Any, code: str, label: str) -> str:
    require(
        isinstance(value, str) and CONTENT_ID_RE.fullmatch(value) is not None,
        code,
        f"{label} is not a content identity",
    )
    return value


def body_without(value: Mapping[str, Any], key: str) -> dict[str, Any]:
    body = dict(value)
    body.pop(key, None)
    return body


def assert_identity(
    value: Mapping[str, Any],
    id_key: str,
    prefix: str,
    code: str,
) -> None:
    require(
        value.get(id_key) == content_id(prefix, body_without(value, id_key)),
        code,
        f"{id_key} differs from content identity",
    )


def is_inside(ancestor: Path, target: Path) -> bool:
    try:
        target.relative_to(ancestor)
        return True
    except ValueError:
        return False


def validate_repository(path: str | Path) -> Path:
    root = Path(path).expanduser().resolve()
    require(root.is_dir(), "REPOSITORY_ROOT_INVALID", "repository root is absent")
    require((root / ".git").exists(), "REPOSITORY_ROOT_INVALID", "repository root has no .git boundary")
    return root


def validate_new_private_root(
    path: str | Path,
    repository: str | Path | None = None,
) -> Path:
    output = Path(path).expanduser().resolve()
    repository_root = Path(repository).expanduser().resolve() if repository is not None else None
    require(
        PRIVATE_ROOT_RE.fullmatch(output.name) is not None,
        "PRIVATE_ROOT_NAME_INVALID",
        "private root name must begin with stc-mary-offline-, stc-mary-reunion-, or stc-mary-successor-",
    )
    require(output.parent.is_dir(), "PRIVATE_ROOT_PARENT_MISSING", "private root parent is absent")
    require(not output.exists(), "PRIVATE_ROOT_EXISTS", "private root already exists")
    require(output != Path(output.anchor), "PRIVATE_ROOT_UNSAFE", "private root may not be a filesystem root")
    require(output != Path.home().resolve(), "PRIVATE_ROOT_UNSAFE", "private root may not be the user home")
    require(output != Path.cwd().resolve(), "PRIVATE_ROOT_UNSAFE", "private root may not be the current directory")
    if repository_root is not None:
        require(
            not is_inside(repository_root, output),
            "PRIVATE_ROOT_IN_REPOSITORY",
            "private root must remain outside the public repository",
        )
        require(
            not is_inside(output, repository_root),
            "PRIVATE_ROOT_UNSAFE",
            "private root may not contain the repository",
        )
    return output


def validate_new_receipt_path(
    path: str | Path,
    repository: str | Path | None = None,
) -> Path:
    output = Path(path).expanduser().resolve()
    repository_root = Path(repository).expanduser().resolve() if repository is not None else None
    require(output.parent.is_dir(), "RECEIPT_PARENT_MISSING", "receipt parent is absent")
    require(not output.exists(), "RECEIPT_EXISTS", "receipt already exists")
    if repository_root is not None:
        require(
            not is_inside(repository_root, output),
            "RECEIPT_IN_REPOSITORY",
            "private receipt must remain outside the public repository",
        )
        require(
            not is_inside(output, repository_root),
            "RECEIPT_PATH_UNSAFE",
            "receipt path may not contain the repository",
        )
    return output


def validate_relative_path(value: Any, code: str = "MANIFEST_PATH_INVALID") -> str:
    require(isinstance(value, str), code, "manifest path must be a string")
    require("\\" not in value, code, "manifest path must use forward slashes")
    path = Path(value)
    require(not path.is_absolute(), code, "manifest path may not be absolute")
    require(value not in {"", "."}, code, "manifest path is empty")
    require(".." not in path.parts, code, "manifest path traverses its root")
    require(all(part not in {"", "."} for part in path.parts), code, "manifest path contains an empty component")
    return path.as_posix()


def stream_sha256(path: Path) -> tuple[str, int]:
    require(path.exists(), "SOURCE_MISSING", f"source is absent: {path}")
    require(not path.is_symlink(), "SYMLINK_REFUSED", f"symlink is refused: {path}")
    require(path.is_file(), "SOURCE_NOT_FILE", f"source is not a regular file: {path}")
    metadata = path.stat()
    require(0 < metadata.st_size <= MAX_BYTES, "SOURCE_SIZE_INVALID", f"source is empty or unbounded: {path}")
    digest = hashlib.sha256()
    count = 0
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
            count += len(chunk)
    require(count == metadata.st_size, "SOURCE_CHANGED_DURING_HASH", f"source changed while hashing: {path}")
    return digest.hexdigest(), count


def iter_regular_files(root: Path) -> list[Path]:
    require(root.exists(), "SOURCE_MISSING", f"source is absent: {root}")
    require(not root.is_symlink(), "SYMLINK_REFUSED", f"symlink is refused: {root}")
    if root.is_file():
        return [root]
    require(root.is_dir(), "SOURCE_TYPE_INVALID", f"source is neither a file nor directory: {root}")
    files: list[Path] = []
    total = 0
    seen_casefold: set[str] = set()
    for candidate in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold()):
        require(not candidate.is_symlink(), "SYMLINK_REFUSED", f"source tree contains symlink: {candidate}")
        if not candidate.is_file():
            continue
        require(len(files) < MAX_FILES, "FILE_DENOMINATOR_UNBOUNDED", "source tree exceeds file denominator")
        relative = candidate.relative_to(root).as_posix()
        validate_relative_path(relative)
        folded = relative.casefold()
        require(folded not in seen_casefold, "PATH_COLLISION_REFUSED", f"case-folded path collision: {relative}")
        seen_casefold.add(folded)
        size = candidate.stat().st_size
        total += size
        require(total <= MAX_BYTES, "SOURCE_SIZE_INVALID", "source tree exceeds byte denominator")
        files.append(candidate)
    require(files, "SOURCE_TREE_EMPTY", f"source tree contains no regular files: {root}")
    return files


def describe_source(source: str | Path, label: str) -> dict[str, Any]:
    source_path = Path(source).expanduser().resolve()
    files = iter_regular_files(source_path)
    rows: list[dict[str, Any]] = []
    total = 0
    if source_path.is_file():
        relative_rows = [(source_path, source_path.name)]
        kind = "file"
    else:
        relative_rows = [(path, path.relative_to(source_path).as_posix()) for path in files]
        kind = "directory"
    for path, relative in relative_rows:
        digest, size = stream_sha256(path)
        rows.append({"relativePath": validate_relative_path(relative), "sha256": digest, "bytes": size})
        total += size
    body = {
        "schema": "stc-mary-offline-component-manifest/1",
        "label": bounded_string(label, "COMPONENT_LABEL_INVALID", "component label", 128),
        "kind": kind,
        "files": rows,
        "fileCount": len(rows),
        "totalBytes": total,
        "authority": "none",
        "claimBoundary": "Content identity for one private local component. Source paths and bodies remain outside public Git.",
    }
    return {**body, "componentId": content_id("stcmaryofflinecomponent1", body)}


def validate_component_manifest(value: Any) -> Mapping[str, Any]:
    stable_keys(
        value,
        [
            "schema",
            "componentId",
            "label",
            "kind",
            "files",
            "fileCount",
            "totalBytes",
            "authority",
            "claimBoundary",
        ],
        "COMPONENT_MANIFEST_INVALID",
        "component manifest",
    )
    require(value["schema"] == "stc-mary-offline-component-manifest/1", "COMPONENT_SCHEMA_INVALID", "component schema differs")
    bounded_string(value["label"], "COMPONENT_MANIFEST_INVALID", "component label", 128)
    require(value["kind"] in {"file", "directory"}, "COMPONENT_MANIFEST_INVALID", "component kind differs")
    require(isinstance(value["files"], list) and value["files"], "COMPONENT_MANIFEST_INVALID", "component files are empty")
    safe_int(value["fileCount"], 1, MAX_FILES, "COMPONENT_MANIFEST_INVALID", "component file count")
    safe_int(value["totalBytes"], 1, MAX_BYTES, "COMPONENT_MANIFEST_INVALID", "component byte count")
    require(value["fileCount"] == len(value["files"]), "COMPONENT_MANIFEST_INVALID", "component file denominator differs")
    paths: set[str] = set()
    folded: set[str] = set()
    total = 0
    for row in value["files"]:
        stable_keys(row, ["relativePath", "sha256", "bytes"], "COMPONENT_MANIFEST_INVALID", "component file")
        relative = validate_relative_path(row["relativePath"])
        require(relative not in paths and relative.casefold() not in folded, "COMPONENT_MANIFEST_INVALID", "component paths duplicate or collide")
        paths.add(relative)
        folded.add(relative.casefold())
        assert_sha256(row["sha256"], "COMPONENT_MANIFEST_INVALID", "component file digest")
        total += safe_int(row["bytes"], 1, MAX_BYTES, "COMPONENT_MANIFEST_INVALID", "component file bytes")
    require(total == value["totalBytes"], "COMPONENT_MANIFEST_INVALID", "component byte denominator differs")
    require(value["authority"] == "none", "COMPONENT_CLAIM_INVALID", "component grants authority")
    bounded_string(value["claimBoundary"], "COMPONENT_MANIFEST_INVALID", "component claim boundary")
    assert_identity(value, "componentId", "stcmaryofflinecomponent1", "COMPONENT_ID_INVALID")
    return value


def copy_source(source: str | Path, destination: Path, label: str) -> dict[str, Any]:
    source_path = Path(source).expanduser().resolve()
    destination = destination.expanduser().resolve()
    require(
        not is_inside(source_path, destination) and not is_inside(destination, source_path),
        "SOURCE_DESTINATION_OVERLAP",
        "source and destination overlap",
    )
    descriptor = describe_source(source_path, label)
    require(not destination.exists(), "DESTINATION_EXISTS", f"destination exists: {destination}")
    destination.mkdir(parents=True)
    if source_path.is_file():
        shutil.copyfile(source_path, destination / source_path.name)
    else:
        for candidate in iter_regular_files(source_path):
            relative = candidate.relative_to(source_path)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(candidate, target)
    verify_component_at(destination, descriptor)
    return descriptor


def verify_component_at(root: Path, descriptor: Mapping[str, Any]) -> None:
    validate_component_manifest(descriptor)
    require(root.is_dir() and not root.is_symlink(), "COMPONENT_ROOT_INVALID", f"component root is invalid: {root}")
    actual: list[str] = []
    for candidate in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold()):
        require(not candidate.is_symlink(), "SYMLINK_REFUSED", f"component contains symlink: {candidate}")
        if candidate.is_file():
            actual.append(candidate.relative_to(root).as_posix())
    expected = [row["relativePath"] for row in descriptor["files"]]
    require(actual == expected, "COMPONENT_DENOMINATOR_INVALID", "component file denominator differs")
    for row in descriptor["files"]:
        digest, size = stream_sha256(root / row["relativePath"])
        require(digest == row["sha256"] and size == row["bytes"], "COMPONENT_DIGEST_INVALID", f"component file differs: {row['relativePath']}")


def record_cell_delta(
    side: str,
    observation: Mapping[str, Any],
    evidence_sha256: str,
    *,
    sequence: int = 1,
) -> dict[str, Any]:
    require(side in {"left", "right"}, "CELL_DELTA_INVALID", "cell side differs")
    require(isinstance(observation, Mapping) and observation, "CELL_DELTA_INVALID", "cell observation must be a non-empty object")
    safe_int(sequence, 1, 1_000_000, "CELL_DELTA_INVALID", "cell delta sequence")
    assert_sha256(evidence_sha256, "CELL_DELTA_INVALID", "cell evidence digest")
    body = {
        "schema": "stc-mary-offline-cell-delta/1",
        "side": side,
        "sequence": sequence,
        "observation": dict(observation),
        "evidenceSha256": evidence_sha256,
        "authority": "none",
        "claimBoundary": "One attributed local cell delta. It records evidence and state change without widening authority.",
    }
    return {**body, "deltaId": content_id("stcmaryofflinecelldelta1", body)}


def validate_cell_delta(value: Any, expected_side: str | None = None) -> Mapping[str, Any]:
    stable_keys(
        value,
        [
            "schema",
            "deltaId",
            "side",
            "sequence",
            "observation",
            "evidenceSha256",
            "authority",
            "claimBoundary",
        ],
        "CELL_DELTA_INVALID",
        "cell delta",
    )
    require(value["schema"] == "stc-mary-offline-cell-delta/1", "CELL_DELTA_SCHEMA_INVALID", "cell delta schema differs")
    require(value["side"] in {"left", "right"}, "CELL_DELTA_INVALID", "cell side differs")
    if expected_side is not None:
        require(value["side"] == expected_side, "CELL_DELTA_BINDING_INVALID", "cell delta belongs to another side")
    safe_int(value["sequence"], 1, 1_000_000, "CELL_DELTA_INVALID", "cell delta sequence")
    require(isinstance(value["observation"], Mapping) and value["observation"], "CELL_DELTA_INVALID", "cell observation is empty")
    assert_sha256(value["evidenceSha256"], "CELL_DELTA_INVALID", "cell evidence digest")
    require(value["authority"] == "none", "CELL_DELTA_CLAIM_INVALID", "cell delta grants authority")
    bounded_string(value["claimBoundary"], "CELL_DELTA_INVALID", "cell delta claim boundary")
    assert_identity(value, "deltaId", "stcmaryofflinecelldelta1", "CELL_DELTA_ID_INVALID")
    return value


def create_authority_boundary() -> dict[str, Any]:
    body = {
        "schema": "stc-mary-offline-authority-boundary/1",
        "authoritySource": "named_human_bind",
        "namedHumanRequired": True,
        "machineAuthority": "none",
        "automaticMergeAllowed": False,
        "authority": "none",
        "claimBoundary": "Named-human authority boundary. Hardware, software, transport, verifier, and scheduler receipts cannot authorize action.",
    }
    return {**body, "authorityId": content_id("stcmaryofflineauthority1", body)}


def validate_authority_boundary(value: Any) -> Mapping[str, Any]:
    stable_keys(
        value,
        [
            "schema",
            "authorityId",
            "authoritySource",
            "namedHumanRequired",
            "machineAuthority",
            "automaticMergeAllowed",
            "authority",
            "claimBoundary",
        ],
        "AUTHORITY_BOUNDARY_INVALID",
        "authority boundary",
    )
    require(value["schema"] == "stc-mary-offline-authority-boundary/1", "AUTHORITY_SCHEMA_INVALID", "authority schema differs")
    require(
        value["authoritySource"] == "named_human_bind"
        and value["namedHumanRequired"] is True
        and value["machineAuthority"] == "none"
        and value["automaticMergeAllowed"] is False
        and value["authority"] == "none",
        "AUTHORITY_CLAIM_INVALID",
        "authority boundary widens machine authority",
    )
    bounded_string(value["claimBoundary"], "AUTHORITY_BOUNDARY_INVALID", "authority claim boundary")
    assert_identity(value, "authorityId", "stcmaryofflineauthority1", "AUTHORITY_ID_INVALID")
    return value


def build_common_state(source: str | Path) -> dict[str, Any]:
    descriptor = describe_source(source, "canonical_common_state")
    body = {
        "schema": "stc-mary-offline-common-state/1",
        "component": descriptor,
        "authority": "none",
        "claimBoundary": "One common canonical-state identity shared by both offline cells.",
    }
    return {**body, "commonStateId": content_id("stcmaryofflinecommonstate1", body)}


def validate_common_state(value: Any) -> Mapping[str, Any]:
    stable_keys(value, ["schema", "commonStateId", "component", "authority", "claimBoundary"], "COMMON_STATE_INVALID", "common state")
    require(value["schema"] == "stc-mary-offline-common-state/1", "COMMON_STATE_SCHEMA_INVALID", "common state schema differs")
    validate_component_manifest(value["component"])
    require(value["authority"] == "none", "COMMON_STATE_CLAIM_INVALID", "common state grants authority")
    bounded_string(value["claimBoundary"], "COMMON_STATE_INVALID", "common state claim boundary")
    assert_identity(value, "commonStateId", "stcmaryofflinecommonstate1", "COMMON_STATE_ID_INVALID")
    return value


def create_cell_record(
    *,
    pair_id: str,
    side: str,
    campaign_label: str,
    common_state_id: str,
    delta_id: str,
    authority_id: str,
) -> dict[str, Any]:
    assert_content_id(pair_id, "CELL_RECORD_INVALID", "pair ID")
    assert_content_id(common_state_id, "CELL_RECORD_INVALID", "common state ID")
    assert_content_id(delta_id, "CELL_RECORD_INVALID", "delta ID")
    assert_content_id(authority_id, "CELL_RECORD_INVALID", "authority ID")
    body = {
        "schema": "stc-mary-offline-cell/1",
        "pairId": pair_id,
        "side": side,
        "campaignLabel": campaign_label,
        "parentStateId": common_state_id,
        "deltaId": delta_id,
        "childStateId": content_id(
            "stcmaryofflinechildstate1",
            {
                "pairId": pair_id,
                "side": side,
                "parentStateId": common_state_id,
                "deltaId": delta_id,
            },
        ),
        "authorityId": authority_id,
        "automaticMergeAllowed": False,
        "networkRequired": False,
        "repositoryHistoryRequired": False,
        "authority": "none",
        "claimBoundary": "One independently verifiable offline cell. Link loss does not widen authority.",
    }
    return {**body, "cellId": content_id("stcmaryofflinecell1", body)}


def validate_cell_record(value: Any) -> Mapping[str, Any]:
    stable_keys(
        value,
        [
            "schema",
            "cellId",
            "pairId",
            "side",
            "campaignLabel",
            "parentStateId",
            "deltaId",
            "childStateId",
            "authorityId",
            "automaticMergeAllowed",
            "networkRequired",
            "repositoryHistoryRequired",
            "authority",
            "claimBoundary",
        ],
        "CELL_RECORD_INVALID",
        "cell record",
    )
    require(value["schema"] == "stc-mary-offline-cell/1", "CELL_RECORD_SCHEMA_INVALID", "cell record schema differs")
    require(value["side"] in {"left", "right"}, "CELL_RECORD_INVALID", "cell side differs")
    bounded_string(value["campaignLabel"], "CELL_RECORD_INVALID", "campaign label", 256)
    for key in ("pairId", "parentStateId", "deltaId", "childStateId", "authorityId"):
        assert_content_id(value[key], "CELL_RECORD_INVALID", key)
    expected_child = content_id(
        "stcmaryofflinechildstate1",
        {
            "pairId": value["pairId"],
            "side": value["side"],
            "parentStateId": value["parentStateId"],
            "deltaId": value["deltaId"],
        },
    )
    require(value["childStateId"] == expected_child, "CELL_CHILD_STATE_INVALID", "cell child state differs")
    require(
        value["automaticMergeAllowed"] is False
        and value["networkRequired"] is False
        and value["repositoryHistoryRequired"] is False
        and value["authority"] == "none",
        "CELL_RECORD_CLAIM_INVALID",
        "cell record widens dependency or authority",
    )
    bounded_string(value["claimBoundary"], "CELL_RECORD_INVALID", "cell claim boundary")
    assert_identity(value, "cellId", "stcmaryofflinecell1", "CELL_ID_INVALID")
    return value


STANDALONE_VERIFIER = r'''from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

CONTENT_ID_RE = __import__("re").compile(r"^[a-z0-9][a-z0-9_-]*_[0-9a-f]{64}$")


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def content_id(prefix, value):
    return f"{prefix}_{hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()}"


def identity_matches(value, key, prefix):
    if not isinstance(value, dict):
        return False
    body = dict(value)
    identifier = body.pop(key, None)
    return (
        isinstance(identifier, str)
        and CONTENT_ID_RE.fullmatch(identifier) is not None
        and identifier == content_id(prefix, body)
    )


def verify_component(root, descriptor):
    expected_keys = {
        "schema", "componentId", "label", "kind", "files",
        "fileCount", "totalBytes", "authority", "claimBoundary",
    }
    if not isinstance(descriptor, dict) or set(descriptor) != expected_keys:
        return "component fields differ"
    if descriptor["schema"] != "stc-mary-offline-component-manifest/1":
        return "component schema differs"
    if descriptor["authority"] != "none" or not identity_matches(
        descriptor, "componentId", "stcmaryofflinecomponent1"
    ):
        return "component identity or authority differs"
    expected_paths = []
    total = 0
    for row in descriptor["files"]:
        if set(row) != {"relativePath", "sha256", "bytes"}:
            return "component file fields differ"
        relative = row["relativePath"]
        path = Path(relative)
        if not isinstance(relative, str) or "\\" in relative or path.is_absolute() or ".." in path.parts:
            return "component path differs"
        target = root / path
        if not target.is_file() or target.is_symlink():
            return f"component file is absent or unsafe: {relative}"
        data = target.read_bytes()
        if len(data) != row["bytes"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
            return f"component file differs: {relative}"
        expected_paths.append(relative)
        total += len(data)
    actual_paths = [
        candidate.relative_to(root).as_posix()
        for candidate in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold())
        if candidate.is_file()
    ]
    if actual_paths != expected_paths:
        return "component denominator differs"
    if descriptor["fileCount"] != len(expected_paths) or descriptor["totalBytes"] != total:
        return "component counts differ"
    return None


def fail(message):
    print(json.dumps({"status": "REFUSED", "reason": message, "authority": "none"}, indent=2))
    return 1


def main(argv):
    if len(argv) != 2:
        return fail("usage: verify_bundle.py BUNDLE")
    root = Path(argv[1]).resolve()
    if not root.is_dir() or root.is_symlink():
        return fail("bundle root is invalid")
    manifest_path = root / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as error:
        return fail(f"manifest read failed: {error}")
    expected_keys = {
        "schema", "manifestId", "bundleType", "bundleId", "files",
        "fileCount", "totalBytes", "authority", "claimBoundary",
    }
    if set(manifest) != expected_keys:
        return fail("manifest fields differ")
    if manifest["schema"] != "stc-mary-offline-bundle-manifest/1":
        return fail("manifest schema differs")
    if manifest["bundleType"] not in {"cell", "successor"}:
        return fail("bundle type differs")
    if manifest["authority"] != "none":
        return fail("manifest grants authority")
    body = dict(manifest)
    actual_id = body.pop("manifestId", None)
    if actual_id != content_id("stcmaryofflinebundlemanifest1", body):
        return fail("manifest identity differs")
    expected_paths = []
    total = 0
    seen = set()
    folded = set()
    for row in manifest["files"]:
        if set(row) != {"path", "sha256", "bytes"}:
            return fail("manifest file fields differ")
        relative = row["path"]
        if not isinstance(relative, str) or "\\" in relative:
            return fail("manifest path differs")
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or relative in {"", "."}:
            return fail("manifest path escapes root")
        if relative in seen or relative.casefold() in folded:
            return fail("manifest path duplicates or collides")
        seen.add(relative)
        folded.add(relative.casefold())
        target = root / path
        if not target.is_file() or target.is_symlink():
            return fail(f"manifest file is absent or unsafe: {relative}")
        data = target.read_bytes()
        if len(data) != row["bytes"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
            return fail(f"manifest file differs: {relative}")
        total += len(data)
        expected_paths.append(relative)
    actual_paths = []
    for candidate in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if candidate.is_symlink():
            return fail(f"bundle contains symlink: {candidate}")
        if candidate.is_file() and candidate != manifest_path:
            actual_paths.append(candidate.relative_to(root).as_posix())
    if actual_paths != expected_paths:
        return fail("bundle file denominator differs")
    if manifest["fileCount"] != len(expected_paths) or manifest["totalBytes"] != total:
        return fail("bundle counts differ")
    record_name = "cell.json" if manifest["bundleType"] == "cell" else "successor.json"
    record = json.loads((root / record_name).read_text(encoding="utf-8"))
    id_key = "cellId" if manifest["bundleType"] == "cell" else "successorId"
    prefix = "stcmaryofflinecell1" if manifest["bundleType"] == "cell" else "stcmaryofflinesuccessor1"
    record_body = dict(record)
    record_id = record_body.pop(id_key, None)
    if not isinstance(record_id, str) or not CONTENT_ID_RE.fullmatch(record_id):
        return fail(f"{id_key} is invalid")
    if record_id != content_id(prefix, record_body):
        return fail(f"{id_key} differs from content identity")
    if record_id != manifest["bundleId"]:
        return fail("manifest belongs to another bundle")

    absent_dependencies = [
        "WAN", "AWS", "Lattice", "remote_model_provider",
        "original_host", "repository_history",
    ]
    if manifest["bundleType"] == "cell":
        expected_cell_keys = {
            "schema", "cellId", "pairId", "side", "campaignLabel",
            "parentStateId", "deltaId", "childStateId", "authorityId",
            "automaticMergeAllowed", "networkRequired",
            "repositoryHistoryRequired", "authority", "claimBoundary",
        }
        if set(record) != expected_cell_keys:
            return fail("cell fields differ")
        if (
            record["schema"] != "stc-mary-offline-cell/1"
            or record["side"] not in {"left", "right"}
            or record["automaticMergeAllowed"] is not False
            or record["networkRequired"] is not False
            or record["repositoryHistoryRequired"] is not False
            or record["authority"] != "none"
        ):
            return fail("cell claim boundary differs")
        expected_child = content_id("stcmaryofflinechildstate1", {
            "pairId": record["pairId"],
            "side": record["side"],
            "parentStateId": record["parentStateId"],
            "deltaId": record["deltaId"],
        })
        if record["childStateId"] != expected_child:
            return fail("cell child state differs")
        common = json.loads((root / "common-state.json").read_text(encoding="utf-8"))
        delta = json.loads((root / "delta.json").read_text(encoding="utf-8"))
        authority = json.loads((root / "authority.json").read_text(encoding="utf-8"))
        if not identity_matches(common, "commonStateId", "stcmaryofflinecommonstate1"):
            return fail("common-state identity differs")
        component_error = verify_component(root / "common", common.get("component"))
        if component_error:
            return fail(component_error)
        if not identity_matches(delta, "deltaId", "stcmaryofflinecelldelta1"):
            return fail("cell delta identity differs")
        if (
            delta.get("side") != record["side"]
            or delta.get("deltaId") != record["deltaId"]
            or delta.get("authority") != "none"
        ):
            return fail("cell delta binding differs")
        if not identity_matches(authority, "authorityId", "stcmaryofflineauthority1"):
            return fail("authority identity differs")
        if (
            authority.get("authoritySource") != "named_human_bind"
            or authority.get("namedHumanRequired") is not True
            or authority.get("machineAuthority") != "none"
            or authority.get("automaticMergeAllowed") is not False
            or authority.get("authority") != "none"
        ):
            return fail("authority boundary differs")
        if (
            common.get("commonStateId") != record["parentStateId"]
            or authority.get("authorityId") != record["authorityId"]
        ):
            return fail("cell source binding differs")
    else:
        expected_successor_keys = {
            "schema", "successorId", "componentIds", "answerId",
            "authorityId", "openObligationIds", "absentDependencies",
            "networkRequired", "repositoryHistoryRequired",
            "originalHostRequired", "authority", "claimBoundary",
        }
        if set(record) != expected_successor_keys:
            return fail("successor fields differ")
        if (
            record["schema"] != "stc-mary-offline-successor/1"
            or record["absentDependencies"] != absent_dependencies
            or record["networkRequired"] is not False
            or record["repositoryHistoryRequired"] is not False
            or record["originalHostRequired"] is not False
            or record["authority"] != "none"
        ):
            return fail("successor claim boundary differs")
        component_set = json.loads((root / "component-manifests.json").read_text(encoding="utf-8"))
        if (
            set(component_set) != {"schema", "components", "authority"}
            or component_set["schema"] != "stc-mary-offline-component-set/1"
            or component_set["authority"] != "none"
            or not isinstance(component_set["components"], list)
            or len(component_set["components"]) != 5
        ):
            return fail("successor component set differs")
        labels = {
            "cartridge", "canonical_state", "authority_boundary",
            "obligations", "evidence_envelope",
        }
        if {row.get("label") for row in component_set["components"]} != labels:
            return fail("successor component labels differ")
        for descriptor in component_set["components"]:
            component_error = verify_component(
                root / "components" / descriptor["label"], descriptor
            )
            if component_error:
                return fail(component_error)
        component_ids = {
            row["label"]: row["componentId"]
            for row in component_set["components"]
        }
        if component_ids != record["componentIds"]:
            return fail("successor component identities differ")
        answer = json.loads((root / "six-question-answer.json").read_text(encoding="utf-8"))
        if not identity_matches(answer, "answerId", "stcmarycoldsuccessoranswer1"):
            return fail("six-question answer identity differs")
        if (
            answer.get("whoMayAct") != "named_human_bind_only"
            or answer.get("whichDependenciesAreAbsent") != absent_dependencies
            or answer.get("authority") != "none"
            or answer.get("answerId") != record["answerId"]
        ):
            return fail("six-question answer claim boundary differs")
        component_id_list = [
            row["componentId"] for row in component_set["components"]
        ]
        if answer.get("whatExists", {}).get("componentIds") != component_id_list:
            return fail("six-question component denominator differs")
        next_text = (root / "next-safe-action.txt").read_text(encoding="utf-8").strip()
        safe_next = answer.get("whatIsSafeNext", {})
        if (
            safe_next.get("text") != next_text
            or safe_next.get("sha256") != hashlib.sha256(next_text.encode("utf-8")).hexdigest()
        ):
            return fail("six-question safe-next answer differs")
        authority_descriptor = next(
            row for row in component_set["components"]
            if row["label"] == "authority_boundary"
        )
        obligations_descriptor = next(
            row for row in component_set["components"]
            if row["label"] == "obligations"
        )
        if (
            authority_descriptor["kind"] != "file"
            or authority_descriptor["fileCount"] != 1
            or obligations_descriptor["kind"] != "file"
            or obligations_descriptor["fileCount"] != 1
        ):
            return fail("successor semantic component shape differs")
        authority_file = (
            root / "components" / "authority_boundary"
            / authority_descriptor["files"][0]["relativePath"]
        )
        obligations_file = (
            root / "components" / "obligations"
            / obligations_descriptor["files"][0]["relativePath"]
        )
        authority = json.loads(authority_file.read_text(encoding="utf-8"))
        obligations = json.loads(obligations_file.read_text(encoding="utf-8"))
        if not identity_matches(authority, "authorityId", "stcmaryofflineauthority1"):
            return fail("successor authority identity differs")
        if (
            authority.get("authoritySource") != "named_human_bind"
            or authority.get("machineAuthority") != "none"
            or authority.get("authority") != "none"
            or authority.get("authorityId") != record["authorityId"]
        ):
            return fail("successor authority boundary differs")
        obligation_ids = [
            row.get("obligationId")
            for row in obligations.get("obligations", [])
        ]
        if (
            obligations.get("schema") != "stc-mary-open-obligations/1"
            or obligations.get("authority") != "none"
            or any(row.get("status") != "open" for row in obligations.get("obligations", []))
            or obligation_ids != record["openObligationIds"]
            or answer.get("whatRemainsUnresolved", {}).get("obligationIds") != obligation_ids
        ):
            return fail("successor obligations differ")
    print(json.dumps({
        "status": "PASS",
        "bundleType": manifest["bundleType"],
        "bundleId": manifest["bundleId"],
        "manifestId": manifest["manifestId"],
        "fileCount": manifest["fileCount"],
        "totalBytes": manifest["totalBytes"],
        "networkRequired": False,
        "repositoryHistoryRequired": False,
        "authority": "none",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
'''


def build_bundle_manifest(root: Path, bundle_type: str, bundle_id: str) -> dict[str, Any]:
    require(bundle_type in BUNDLE_TYPES, "BUNDLE_TYPE_INVALID", "bundle type differs")
    assert_content_id(bundle_id, "BUNDLE_ID_INVALID", "bundle ID")
    manifest_path = root / "manifest.json"
    require(not manifest_path.exists(), "MANIFEST_EXISTS", "manifest already exists")
    rows: list[dict[str, Any]] = []
    total = 0
    seen: set[str] = set()
    folded: set[str] = set()
    for candidate in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold()):
        require(not candidate.is_symlink(), "SYMLINK_REFUSED", f"bundle contains symlink: {candidate}")
        if not candidate.is_file():
            continue
        relative = candidate.relative_to(root).as_posix()
        validate_relative_path(relative)
        require(relative not in seen and relative.casefold() not in folded, "BUNDLE_PATH_COLLISION", f"bundle path duplicates or collides: {relative}")
        seen.add(relative)
        folded.add(relative.casefold())
        digest, size = stream_sha256(candidate)
        rows.append({"path": relative, "sha256": digest, "bytes": size})
        total += size
        require(len(rows) <= MAX_FILES and total <= MAX_BYTES, "BUNDLE_DENOMINATOR_UNBOUNDED", "bundle denominator is unbounded")
    require(rows, "BUNDLE_EMPTY", "bundle contains no files")
    body = {
        "schema": "stc-mary-offline-bundle-manifest/1",
        "bundleType": bundle_type,
        "bundleId": bundle_id,
        "files": rows,
        "fileCount": len(rows),
        "totalBytes": total,
        "authority": "none",
        "claimBoundary": "Complete content-addressed bundle denominator. The manifest grants no authority.",
    }
    manifest = {**body, "manifestId": content_id("stcmaryofflinebundlemanifest1", body)}
    write_json(manifest_path, manifest)
    return manifest


def validate_bundle_manifest(value: Any) -> Mapping[str, Any]:
    stable_keys(
        value,
        [
            "schema",
            "manifestId",
            "bundleType",
            "bundleId",
            "files",
            "fileCount",
            "totalBytes",
            "authority",
            "claimBoundary",
        ],
        "BUNDLE_MANIFEST_INVALID",
        "bundle manifest",
    )
    require(value["schema"] == "stc-mary-offline-bundle-manifest/1", "BUNDLE_MANIFEST_SCHEMA_INVALID", "bundle manifest schema differs")
    require(value["bundleType"] in BUNDLE_TYPES, "BUNDLE_MANIFEST_INVALID", "bundle type differs")
    assert_content_id(value["bundleId"], "BUNDLE_MANIFEST_INVALID", "bundle ID")
    require(isinstance(value["files"], list) and value["files"], "BUNDLE_MANIFEST_INVALID", "bundle file list is empty")
    safe_int(value["fileCount"], 1, MAX_FILES, "BUNDLE_MANIFEST_INVALID", "bundle file count")
    safe_int(value["totalBytes"], 1, MAX_BYTES, "BUNDLE_MANIFEST_INVALID", "bundle total bytes")
    require(value["fileCount"] == len(value["files"]), "BUNDLE_MANIFEST_INVALID", "bundle file denominator differs")
    paths: set[str] = set()
    folded: set[str] = set()
    total = 0
    for row in value["files"]:
        stable_keys(row, ["path", "sha256", "bytes"], "BUNDLE_MANIFEST_INVALID", "bundle file")
        relative = validate_relative_path(row["path"])
        require(relative not in paths and relative.casefold() not in folded, "BUNDLE_MANIFEST_INVALID", "bundle paths duplicate or collide")
        paths.add(relative)
        folded.add(relative.casefold())
        assert_sha256(row["sha256"], "BUNDLE_MANIFEST_INVALID", "bundle file digest")
        total += safe_int(row["bytes"], 1, MAX_BYTES, "BUNDLE_MANIFEST_INVALID", "bundle file bytes")
    require(total == value["totalBytes"], "BUNDLE_MANIFEST_INVALID", "bundle byte denominator differs")
    require(value["authority"] == "none", "BUNDLE_MANIFEST_CLAIM_INVALID", "bundle manifest grants authority")
    bounded_string(value["claimBoundary"], "BUNDLE_MANIFEST_INVALID", "bundle claim boundary")
    assert_identity(value, "manifestId", "stcmaryofflinebundlemanifest1", "BUNDLE_MANIFEST_ID_INVALID")
    return value


def verify_bundle_manifest(root: Path, expected_type: str | None = None) -> Mapping[str, Any]:
    root = root.expanduser().resolve()
    require(root.is_dir() and not root.is_symlink(), "BUNDLE_ROOT_INVALID", "bundle root is absent or unsafe")
    manifest = read_json(root / "manifest.json")
    validate_bundle_manifest(manifest)
    if expected_type is not None:
        require(manifest["bundleType"] == expected_type, "BUNDLE_TYPE_INVALID", "bundle has another type")
    expected_paths = [row["path"] for row in manifest["files"]]
    actual_paths: list[str] = []
    for candidate in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold()):
        require(not candidate.is_symlink(), "SYMLINK_REFUSED", f"bundle contains symlink: {candidate}")
        if candidate.is_file() and candidate != root / "manifest.json":
            actual_paths.append(candidate.relative_to(root).as_posix())
    require(actual_paths == expected_paths, "BUNDLE_DENOMINATOR_INVALID", "bundle file denominator differs")
    for row in manifest["files"]:
        digest, size = stream_sha256(root / row["path"])
        require(digest == row["sha256"] and size == row["bytes"], "BUNDLE_DIGEST_INVALID", f"bundle file differs: {row['path']}")
    return manifest


def create_pair_seed(
    *,
    campaign_label: str,
    common_state_id: str,
    authority_id: str,
    left_delta_id: str,
    right_delta_id: str,
) -> dict[str, Any]:
    body = {
        "campaignLabel": bounded_string(campaign_label, "PAIR_INVALID", "campaign label", 256),
        "commonStateId": common_state_id,
        "authorityId": authority_id,
        "leftDeltaId": left_delta_id,
        "rightDeltaId": right_delta_id,
        "automaticMergeAllowed": False,
        "authority": "none",
    }
    for key in ("commonStateId", "authorityId", "leftDeltaId", "rightDeltaId"):
        assert_content_id(body[key], "PAIR_INVALID", key)
    return {**body, "pairId": content_id("stcmaryofflinepair1", body)}


def build_cell_bundle(
    *,
    destination: Path,
    side: str,
    source_common: Path,
    common_state: Mapping[str, Any],
    delta: Mapping[str, Any],
    authority: Mapping[str, Any],
    pair_id: str,
    campaign_label: str,
) -> dict[str, Any]:
    require(side in {"left", "right"}, "CELL_SIDE_INVALID", "cell side differs")
    destination.mkdir(parents=True)
    common_descriptor = copy_source(source_common, destination / "common", "canonical_common_state")
    require(
        common_descriptor["componentId"] == common_state["component"]["componentId"],
        "COMMON_STATE_COPY_DRIFT",
        "copied common state differs",
    )
    write_json(destination / "common-state.json", common_state)
    write_json(destination / "delta.json", delta)
    write_json(destination / "authority.json", authority)
    cell = create_cell_record(
        pair_id=pair_id,
        side=side,
        campaign_label=campaign_label,
        common_state_id=common_state["commonStateId"],
        delta_id=delta["deltaId"],
        authority_id=authority["authorityId"],
    )
    write_json(destination / "cell.json", cell)
    (destination / "verify_bundle.py").write_text(STANDALONE_VERIFIER, encoding="utf-8", newline="\n")
    manifest = build_bundle_manifest(destination, "cell", cell["cellId"])
    verify_cell_bundle(destination)
    return {"cell": cell, "manifest": manifest}


def build_cell_pair(
    *,
    common_state_path: str | Path,
    left_delta_path: str | Path,
    right_delta_path: str | Path,
    authority_path: str | Path,
    campaign_label: str,
    out: str | Path,
    repository: str | Path,
) -> dict[str, Any]:
    repository_root = validate_repository(repository)
    output = validate_new_private_root(out, repository_root)
    common_source = Path(common_state_path).expanduser().resolve()
    require(
        not is_inside(common_source, output) and not is_inside(output, common_source),
        "SOURCE_DESTINATION_OVERLAP",
        "common-state source and pair output overlap",
    )
    common_state = build_common_state(common_source)
    left_delta = read_json(Path(left_delta_path))
    right_delta = read_json(Path(right_delta_path))
    authority = read_json(Path(authority_path))
    validate_cell_delta(left_delta, "left")
    validate_cell_delta(right_delta, "right")
    validate_authority_boundary(authority)
    require(left_delta["deltaId"] != right_delta["deltaId"], "CELL_DELTAS_IDENTICAL", "left and right deltas are identical")
    left_effect = {
        "sequence": left_delta["sequence"],
        "observation": left_delta["observation"],
        "evidenceSha256": left_delta["evidenceSha256"],
    }
    right_effect = {
        "sequence": right_delta["sequence"],
        "observation": right_delta["observation"],
        "evidenceSha256": right_delta["evidenceSha256"],
    }
    require(
        canonical_json(left_effect) != canonical_json(right_effect),
        "CELL_DELTAS_IDENTICAL",
        "left and right deltas carry the same observed effect",
    )
    pair_seed = create_pair_seed(
        campaign_label=campaign_label,
        common_state_id=common_state["commonStateId"],
        authority_id=authority["authorityId"],
        left_delta_id=left_delta["deltaId"],
        right_delta_id=right_delta["deltaId"],
    )
    output.mkdir()
    left = build_cell_bundle(
        destination=output / "left",
        side="left",
        source_common=common_source,
        common_state=common_state,
        delta=left_delta,
        authority=authority,
        pair_id=pair_seed["pairId"],
        campaign_label=pair_seed["campaignLabel"],
    )
    right = build_cell_bundle(
        destination=output / "right",
        side="right",
        source_common=common_source,
        common_state=common_state,
        delta=right_delta,
        authority=authority,
        pair_id=pair_seed["pairId"],
        campaign_label=pair_seed["campaignLabel"],
    )
    require(left["cell"]["childStateId"] != right["cell"]["childStateId"], "CELL_CHILDREN_IDENTICAL", "partition did not produce divergent child states")
    pair = {
        "schema": "stc-mary-offline-cell-pair/1",
        **pair_seed,
        "leftCellId": left["cell"]["cellId"],
        "rightCellId": right["cell"]["cellId"],
        "leftChildStateId": left["cell"]["childStateId"],
        "rightChildStateId": right["cell"]["childStateId"],
        "networkRequired": False,
        "repositoryHistoryRequired": False,
        "authority": "none",
        "claimBoundary": "Two independently verifiable offline cells derived from one exact parent. Neither branch is privileged.",
    }
    write_json(output / "pair.json", pair)
    return {
        "status": "PASS",
        "output": str(output),
        "pairId": pair["pairId"],
        "leftCellId": pair["leftCellId"],
        "rightCellId": pair["rightCellId"],
        "authority": "none",
    }


def verify_cell_bundle(bundle: str | Path) -> dict[str, Any]:
    root = Path(bundle).expanduser().resolve()
    manifest = verify_bundle_manifest(root, "cell")
    common_state = read_json(root / "common-state.json")
    delta = read_json(root / "delta.json")
    authority = read_json(root / "authority.json")
    cell = read_json(root / "cell.json")
    validate_common_state(common_state)
    validate_cell_delta(delta)
    validate_authority_boundary(authority)
    validate_cell_record(cell)
    require(manifest["bundleId"] == cell["cellId"], "CELL_MANIFEST_BINDING_INVALID", "manifest belongs to another cell")
    require(delta["side"] == cell["side"], "CELL_DELTA_BINDING_INVALID", "delta belongs to another cell")
    require(delta["deltaId"] == cell["deltaId"], "CELL_DELTA_BINDING_INVALID", "cell delta identity differs")
    require(common_state["commonStateId"] == cell["parentStateId"], "CELL_PARENT_BINDING_INVALID", "cell parent differs")
    require(authority["authorityId"] == cell["authorityId"], "CELL_AUTHORITY_BINDING_INVALID", "cell authority differs")
    verify_component_at(root / "common", common_state["component"])
    verifier_digest, _ = stream_sha256(root / "verify_bundle.py")
    return {
        "root": root,
        "manifest": manifest,
        "cell": cell,
        "commonState": common_state,
        "delta": delta,
        "authorityBoundary": authority,
        "standaloneVerifierSha256": verifier_digest,
    }


def host_class_digest() -> str:
    body = {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "node": platform.node(),
        "pythonImplementation": platform.python_implementation(),
        "pythonVersion": platform.python_version(),
        "hardwareNode": f"{uuid.getnode():012x}",
        "computerName": os.environ.get("COMPUTERNAME", ""),
    }
    return sha256_bytes(canonical_json(body).encode("utf-8"))


def create_cell_verification(
    verified: Mapping[str, Any],
    mode: str,
    *,
    host_digest: str | None = None,
) -> dict[str, Any]:
    require(mode in ATTESTATION_MODES, "CELL_VERIFICATION_MODE_INVALID", "cell verification mode differs")
    cell = verified["cell"]
    manifest = verified["manifest"]
    if mode == "private_local_attested":
        digest = host_digest if host_digest is not None else host_class_digest()
    else:
        digest = sha256_bytes(f"synthetic:{cell['cellId']}".encode("utf-8"))
    assert_sha256(digest, "CELL_VERIFICATION_INVALID", "host class digest")
    body = {
        "schema": "stc-mary-offline-cell-verification/1",
        "mode": mode,
        "cellId": cell["cellId"],
        "pairId": cell["pairId"],
        "side": cell["side"],
        "parentStateId": cell["parentStateId"],
        "childStateId": cell["childStateId"],
        "manifestId": manifest["manifestId"],
        "hostClassDigest": digest,
        "bundleVerified": True,
        "standaloneVerifierSha256": verified["standaloneVerifierSha256"],
        "networkRequired": False,
        "repositoryHistoryRequired": False,
        "externalServiceCalls": 0,
        "operationalCredentials": 0,
        "authority": "none",
        "claimBoundary": "Digest-only verification of one complete offline cell bundle. Host identity remains private and the receipt grants no authority.",
    }
    return {**body, "verificationId": content_id("stcmaryofflinecellverification1", body)}


def validate_cell_verification(value: Any) -> Mapping[str, Any]:
    stable_keys(
        value,
        [
            "schema",
            "verificationId",
            "mode",
            "cellId",
            "pairId",
            "side",
            "parentStateId",
            "childStateId",
            "manifestId",
            "hostClassDigest",
            "bundleVerified",
            "standaloneVerifierSha256",
            "networkRequired",
            "repositoryHistoryRequired",
            "externalServiceCalls",
            "operationalCredentials",
            "authority",
            "claimBoundary",
        ],
        "CELL_VERIFICATION_INVALID",
        "cell verification",
    )
    require(value["schema"] == "stc-mary-offline-cell-verification/1", "CELL_VERIFICATION_SCHEMA_INVALID", "cell verification schema differs")
    require(value["mode"] in ATTESTATION_MODES, "CELL_VERIFICATION_MODE_INVALID", "cell verification mode differs")
    require(value["side"] in {"left", "right"}, "CELL_VERIFICATION_INVALID", "cell verification side differs")
    for key in ("cellId", "pairId", "parentStateId", "childStateId", "manifestId"):
        assert_content_id(value[key], "CELL_VERIFICATION_INVALID", key)
    for key in ("hostClassDigest", "standaloneVerifierSha256"):
        assert_sha256(value[key], "CELL_VERIFICATION_INVALID", key)
    require(
        value["bundleVerified"] is True
        and value["networkRequired"] is False
        and value["repositoryHistoryRequired"] is False
        and value["externalServiceCalls"] == 0
        and value["operationalCredentials"] == 0
        and value["authority"] == "none",
        "CELL_VERIFICATION_CLAIM_INVALID",
        "cell verification widens dependency, execution, or authority",
    )
    bounded_string(value["claimBoundary"], "CELL_VERIFICATION_INVALID", "cell verification claim boundary")
    assert_identity(value, "verificationId", "stcmaryofflinecellverification1", "CELL_VERIFICATION_ID_INVALID")
    return value


def verify_cell(
    *,
    bundle: str | Path,
    mode: str,
    out: str | Path,
    repository: str | Path | None = None,
) -> dict[str, Any]:
    bundle_root = Path(bundle).expanduser().resolve()
    verified = verify_cell_bundle(bundle_root)
    receipt = create_cell_verification(verified, mode)
    output = validate_new_receipt_path(out, repository)
    require(
        not is_inside(bundle_root, output),
        "RECEIPT_MUTATES_BUNDLE",
        "verification receipt may not be written inside the verified bundle",
    )
    write_json(output, receipt)
    return {
        "status": "PASS",
        "verificationId": receipt["verificationId"],
        "cellId": receipt["cellId"],
        "mode": receipt["mode"],
        "output": str(output),
        "authority": "none",
    }


def create_reconciliation_obligation(
    *,
    pair_id: str,
    left_cell_id: str,
    right_cell_id: str,
    left_child_state_id: str,
    right_child_state_id: str,
) -> dict[str, Any]:
    body = {
        "schema": "stc-mary-offline-reconciliation-obligation/1",
        "kind": "divergent_offline_cells",
        "pairId": pair_id,
        "leftCellId": left_cell_id,
        "rightCellId": right_cell_id,
        "leftChildStateId": left_child_state_id,
        "rightChildStateId": right_child_state_id,
        "requiredDisposition": "human_required",
        "resolved": False,
        "authority": "none",
        "claimBoundary": "Unresolved obligation retaining both divergent branches until a named human supplies a disposition.",
    }
    return {**body, "obligationId": content_id("stcmaryofflinereconciliationobligation1", body)}


def create_two_cell_verification(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    obligation: Mapping[str, Any],
) -> dict[str, Any]:
    body = {
        "schema": "stc-mary-offline-two-cell-verification/1",
        "mode": left["mode"],
        "pairId": left["pairId"],
        "leftCellId": left["cellId"],
        "rightCellId": right["cellId"],
        "commonParentStateId": left["parentStateId"],
        "leftChildStateId": left["childStateId"],
        "rightChildStateId": right["childStateId"],
        "leftHostClassDigest": left["hostClassDigest"],
        "rightHostClassDigest": right["hostClassDigest"],
        "distinctHostClasses": left["hostClassDigest"] != right["hostClassDigest"],
        "reunionTerminal": "HUMAN_REQUIRED",
        "automaticMergeAllowed": False,
        "branchesRetained": 2,
        "unresolvedObligationId": obligation["obligationId"],
        "bundleVerificationIds": [left["verificationId"], right["verificationId"]],
        "networkRequired": False,
        "repositoryHistoryRequired": False,
        "externalServiceCalls": 0,
        "operationalCredentials": 0,
        "authority": "none",
        "claimBoundary": "Digest-only proof of two divergent offline cells and one human-required reunion. No branch is selected.",
    }
    return {**body, "verificationId": content_id("stcmaryofflinetwocellverification1", body)}


def validate_two_cell_verification(value: Any) -> Mapping[str, Any]:
    stable_keys(
        value,
        [
            "schema",
            "verificationId",
            "mode",
            "pairId",
            "leftCellId",
            "rightCellId",
            "commonParentStateId",
            "leftChildStateId",
            "rightChildStateId",
            "leftHostClassDigest",
            "rightHostClassDigest",
            "distinctHostClasses",
            "reunionTerminal",
            "automaticMergeAllowed",
            "branchesRetained",
            "unresolvedObligationId",
            "bundleVerificationIds",
            "networkRequired",
            "repositoryHistoryRequired",
            "externalServiceCalls",
            "operationalCredentials",
            "authority",
            "claimBoundary",
        ],
        "TWO_CELL_VERIFICATION_INVALID",
        "two-cell verification",
    )
    require(value["schema"] == "stc-mary-offline-two-cell-verification/1", "TWO_CELL_VERIFICATION_SCHEMA_INVALID", "two-cell verification schema differs")
    require(value["mode"] in ATTESTATION_MODES, "TWO_CELL_VERIFICATION_MODE_INVALID", "two-cell verification mode differs")
    for key in (
        "pairId",
        "leftCellId",
        "rightCellId",
        "commonParentStateId",
        "leftChildStateId",
        "rightChildStateId",
        "unresolvedObligationId",
    ):
        assert_content_id(value[key], "TWO_CELL_VERIFICATION_INVALID", key)
    require(value["leftCellId"] != value["rightCellId"], "TWO_CELL_VERIFICATION_INVALID", "cell identities are equal")
    require(value["leftChildStateId"] != value["rightChildStateId"], "TWO_CELL_VERIFICATION_INVALID", "child states are equal")
    for key in ("leftHostClassDigest", "rightHostClassDigest"):
        assert_sha256(value[key], "TWO_CELL_VERIFICATION_INVALID", key)
    require(
        value["leftHostClassDigest"] != value["rightHostClassDigest"]
        and value["distinctHostClasses"] is True,
        "TWO_CELL_HOST_CLASS_INVALID",
        "two-cell verification does not prove distinct host classes",
    )
    require(
        value["reunionTerminal"] == "HUMAN_REQUIRED"
        and value["automaticMergeAllowed"] is False
        and value["branchesRetained"] == 2,
        "TWO_CELL_REUNION_INVALID",
        "two-cell reunion discards a branch or auto-merges",
    )
    require(
        isinstance(value["bundleVerificationIds"], list)
        and len(value["bundleVerificationIds"]) == 2
        and len(set(value["bundleVerificationIds"])) == 2,
        "TWO_CELL_VERIFICATION_INVALID",
        "bundle verification denominator differs",
    )
    for identifier in value["bundleVerificationIds"]:
        assert_content_id(identifier, "TWO_CELL_VERIFICATION_INVALID", "bundle verification ID")
    require(
        value["networkRequired"] is False
        and value["repositoryHistoryRequired"] is False
        and value["externalServiceCalls"] == 0
        and value["operationalCredentials"] == 0
        and value["authority"] == "none",
        "TWO_CELL_CLAIM_INVALID",
        "two-cell verification widens dependency or authority",
    )
    bounded_string(value["claimBoundary"], "TWO_CELL_VERIFICATION_INVALID", "two-cell claim boundary")
    assert_identity(value, "verificationId", "stcmaryofflinetwocellverification1", "TWO_CELL_VERIFICATION_ID_INVALID")
    return value


def reunite_cells(
    *,
    left_bundle: str | Path,
    right_bundle: str | Path,
    left_verification: str | Path | Mapping[str, Any],
    right_verification: str | Path | Mapping[str, Any],
    out: str | Path,
    repository: str | Path | None = None,
) -> dict[str, Any]:
    repository_root = validate_repository(repository) if repository is not None else None
    output = validate_new_private_root(out, repository_root)
    left_root = Path(left_bundle).expanduser().resolve()
    right_root = Path(right_bundle).expanduser().resolve()
    require(
        not is_inside(left_root, output)
        and not is_inside(right_root, output)
        and not is_inside(output, left_root)
        and not is_inside(output, right_root),
        "SOURCE_DESTINATION_OVERLAP",
        "reunion output overlaps a cell bundle",
    )
    left_bundle_state = verify_cell_bundle(left_root)
    right_bundle_state = verify_cell_bundle(right_root)
    left_receipt = read_json(Path(left_verification)) if not isinstance(left_verification, Mapping) else dict(left_verification)
    right_receipt = read_json(Path(right_verification)) if not isinstance(right_verification, Mapping) else dict(right_verification)
    validate_cell_verification(left_receipt)
    validate_cell_verification(right_receipt)
    require(left_receipt["side"] == "left" and right_receipt["side"] == "right", "REUNION_SIDE_INVALID", "reunion receipts are not left and right")
    require(left_receipt["cellId"] == left_bundle_state["cell"]["cellId"], "REUNION_BINDING_INVALID", "left receipt belongs to another bundle")
    require(right_receipt["cellId"] == right_bundle_state["cell"]["cellId"], "REUNION_BINDING_INVALID", "right receipt belongs to another bundle")
    require(left_receipt["pairId"] == right_receipt["pairId"], "REUNION_PAIR_INVALID", "cells belong to different pairs")
    require(left_receipt["parentStateId"] == right_receipt["parentStateId"], "REUNION_PARENT_INVALID", "cells do not share one parent")
    require(left_receipt["childStateId"] != right_receipt["childStateId"], "REUNION_DIVERGENCE_INVALID", "cells did not diverge")
    require(left_receipt["mode"] == right_receipt["mode"], "REUNION_MODE_INVALID", "cell verification modes differ")
    require(left_receipt["hostClassDigest"] != right_receipt["hostClassDigest"], "REUNION_HOST_INVALID", "cell receipts do not prove distinct host classes")
    obligation = create_reconciliation_obligation(
        pair_id=left_receipt["pairId"],
        left_cell_id=left_receipt["cellId"],
        right_cell_id=right_receipt["cellId"],
        left_child_state_id=left_receipt["childStateId"],
        right_child_state_id=right_receipt["childStateId"],
    )
    verification = create_two_cell_verification(left_receipt, right_receipt, obligation)
    validate_two_cell_verification(verification)
    reunion_body = {
        "schema": "stc-mary-offline-cell-reunion/1",
        "verificationId": verification["verificationId"],
        "terminal": "HUMAN_REQUIRED",
        "selectedWinner": None,
        "automaticMergeAllowed": False,
        "retainedCellIds": [left_receipt["cellId"], right_receipt["cellId"]],
        "unresolvedObligationId": obligation["obligationId"],
        "authority": "none",
        "claimBoundary": "Private reunion record retaining both divergent cells and requiring named-human disposition.",
    }
    reunion = {**reunion_body, "reunionId": content_id("stcmaryofflinereunion1", reunion_body)}
    output.mkdir()
    write_json(output / "left-cell-verification.json", left_receipt)
    write_json(output / "right-cell-verification.json", right_receipt)
    write_json(output / "unresolved-reconciliation-obligation.json", obligation)
    write_json(output / "two-cell-verification.json", verification)
    write_json(output / "reunion.json", reunion)
    return {
        "status": "HUMAN_REQUIRED",
        "output": str(output),
        "verificationId": verification["verificationId"],
        "obligationId": obligation["obligationId"],
        "authority": "none",
    }


def validate_open_obligations(value: Any) -> Mapping[str, Any]:
    stable_keys(
        value,
        ["schema", "obligations", "authority", "claimBoundary"],
        "OBLIGATIONS_INVALID",
        "open obligations",
    )
    require(value["schema"] == "stc-mary-open-obligations/1", "OBLIGATIONS_SCHEMA_INVALID", "obligations schema differs")
    require(isinstance(value["obligations"], list), "OBLIGATIONS_INVALID", "obligations must be an array")
    seen: set[str] = set()
    for row in value["obligations"]:
        stable_keys(row, ["obligationId", "kind", "status", "description"], "OBLIGATIONS_INVALID", "obligation")
        identifier = assert_content_id(row["obligationId"], "OBLIGATIONS_INVALID", "obligation ID")
        require(identifier not in seen, "OBLIGATIONS_INVALID", "obligations contain duplicates")
        seen.add(identifier)
        bounded_string(row["kind"], "OBLIGATIONS_INVALID", "obligation kind", 128)
        require(row["status"] == "open", "OBLIGATIONS_INVALID", "obligation is not open")
        bounded_string(row["description"], "OBLIGATIONS_INVALID", "obligation description")
    require(value["authority"] == "none", "OBLIGATIONS_CLAIM_INVALID", "obligations grant authority")
    bounded_string(value["claimBoundary"], "OBLIGATIONS_INVALID", "obligations claim boundary")
    return value


def create_open_obligation(kind: str, description: str) -> dict[str, Any]:
    body = {
        "kind": bounded_string(kind, "OBLIGATION_INVALID", "obligation kind", 128),
        "status": "open",
        "description": bounded_string(description, "OBLIGATION_INVALID", "obligation description"),
    }
    return {**body, "obligationId": content_id("stcmaryopenobligation1", body)}


def build_successor_answer(
    *,
    component_manifests: Sequence[Mapping[str, Any]],
    obligations: Mapping[str, Any],
    next_safe_action: str,
) -> dict[str, Any]:
    component_ids = [row["componentId"] for row in component_manifests]
    obligation_ids = [row["obligationId"] for row in obligations["obligations"]]
    body = {
        "schema": "stc-mary-cold-successor-six-question-answer/1",
        "whatExists": {
            "bundleType": "successor",
            "componentIds": component_ids,
            "componentCount": len(component_ids),
        },
        "whatProvesIt": {
            "componentManifestsVerified": True,
            "standaloneVerifierPresent": True,
        },
        "whoMayAct": "named_human_bind_only",
        "whatRemainsUnresolved": {
            "obligationIds": obligation_ids,
            "openObligationCount": len(obligation_ids),
        },
        "whatIsSafeNext": {
            "text": next_safe_action,
            "sha256": sha256_bytes(next_safe_action.encode("utf-8")),
        },
        "whichDependenciesAreAbsent": list(ABSENT_DEPENDENCIES),
        "authority": "none",
        "claimBoundary": "Six-question cold-successor answer reconstructed from bundled bytes. It grants no authority.",
    }
    return {**body, "answerId": content_id("stcmarycoldsuccessoranswer1", body)}


def validate_successor_answer(value: Any) -> Mapping[str, Any]:
    stable_keys(
        value,
        [
            "schema",
            "answerId",
            "whatExists",
            "whatProvesIt",
            "whoMayAct",
            "whatRemainsUnresolved",
            "whatIsSafeNext",
            "whichDependenciesAreAbsent",
            "authority",
            "claimBoundary",
        ],
        "SUCCESSOR_ANSWER_INVALID",
        "successor answer",
    )
    require(value["schema"] == "stc-mary-cold-successor-six-question-answer/1", "SUCCESSOR_ANSWER_SCHEMA_INVALID", "successor answer schema differs")
    stable_keys(value["whatExists"], ["bundleType", "componentIds", "componentCount"], "SUCCESSOR_ANSWER_INVALID", "what exists")
    require(value["whatExists"]["bundleType"] == "successor", "SUCCESSOR_ANSWER_INVALID", "successor answer bundle type differs")
    require(
        isinstance(value["whatExists"]["componentIds"], list)
        and value["whatExists"]["componentIds"]
        and value["whatExists"]["componentCount"] == len(value["whatExists"]["componentIds"]),
        "SUCCESSOR_ANSWER_INVALID",
        "successor component denominator differs",
    )
    for identifier in value["whatExists"]["componentIds"]:
        assert_content_id(identifier, "SUCCESSOR_ANSWER_INVALID", "component ID")
    stable_keys(value["whatProvesIt"], ["componentManifestsVerified", "standaloneVerifierPresent"], "SUCCESSOR_ANSWER_INVALID", "what proves it")
    require(
        value["whatProvesIt"]["componentManifestsVerified"] is True
        and value["whatProvesIt"]["standaloneVerifierPresent"] is True,
        "SUCCESSOR_ANSWER_INVALID",
        "successor proof answer differs",
    )
    require(value["whoMayAct"] == "named_human_bind_only", "SUCCESSOR_ANSWER_CLAIM_INVALID", "successor answer widens acting authority")
    stable_keys(
        value["whatRemainsUnresolved"],
        ["obligationIds", "openObligationCount"],
        "SUCCESSOR_ANSWER_INVALID",
        "unresolved answer",
    )
    require(
        isinstance(value["whatRemainsUnresolved"]["obligationIds"], list)
        and value["whatRemainsUnresolved"]["openObligationCount"] == len(value["whatRemainsUnresolved"]["obligationIds"]),
        "SUCCESSOR_ANSWER_INVALID",
        "obligation denominator differs",
    )
    for identifier in value["whatRemainsUnresolved"]["obligationIds"]:
        assert_content_id(identifier, "SUCCESSOR_ANSWER_INVALID", "obligation ID")
    stable_keys(value["whatIsSafeNext"], ["text", "sha256"], "SUCCESSOR_ANSWER_INVALID", "safe next answer")
    text = bounded_string(value["whatIsSafeNext"]["text"], "SUCCESSOR_ANSWER_INVALID", "safe next text", MAX_ACTION_BYTES)
    require(
        value["whatIsSafeNext"]["sha256"] == sha256_bytes(text.encode("utf-8")),
        "SUCCESSOR_ANSWER_INVALID",
        "safe next digest differs",
    )
    require(
        value["whichDependenciesAreAbsent"] == list(ABSENT_DEPENDENCIES),
        "SUCCESSOR_ANSWER_INVALID",
        "absent dependency denominator differs",
    )
    require(value["authority"] == "none", "SUCCESSOR_ANSWER_CLAIM_INVALID", "successor answer grants authority")
    bounded_string(value["claimBoundary"], "SUCCESSOR_ANSWER_INVALID", "successor answer claim boundary")
    assert_identity(value, "answerId", "stcmarycoldsuccessoranswer1", "SUCCESSOR_ANSWER_ID_INVALID")
    return value


def create_successor_record(
    component_manifests: Sequence[Mapping[str, Any]],
    answer: Mapping[str, Any],
    authority: Mapping[str, Any],
    obligations: Mapping[str, Any],
) -> dict[str, Any]:
    components = {row["label"]: row["componentId"] for row in component_manifests}
    required = {"cartridge", "canonical_state", "authority_boundary", "obligations", "evidence_envelope"}
    require(set(components) == required, "SUCCESSOR_COMPONENT_DENOMINATOR_INVALID", "successor component denominator differs")
    body = {
        "schema": "stc-mary-offline-successor/1",
        "componentIds": components,
        "answerId": answer["answerId"],
        "authorityId": authority["authorityId"],
        "openObligationIds": [row["obligationId"] for row in obligations["obligations"]],
        "absentDependencies": list(ABSENT_DEPENDENCIES),
        "networkRequired": False,
        "repositoryHistoryRequired": False,
        "originalHostRequired": False,
        "authority": "none",
        "claimBoundary": "Cold-successor bundle reconstructable without repository history, original host, external services, or machine authority.",
    }
    return {**body, "successorId": content_id("stcmaryofflinesuccessor1", body)}


def validate_successor_record(value: Any) -> Mapping[str, Any]:
    stable_keys(
        value,
        [
            "schema",
            "successorId",
            "componentIds",
            "answerId",
            "authorityId",
            "openObligationIds",
            "absentDependencies",
            "networkRequired",
            "repositoryHistoryRequired",
            "originalHostRequired",
            "authority",
            "claimBoundary",
        ],
        "SUCCESSOR_RECORD_INVALID",
        "successor record",
    )
    require(value["schema"] == "stc-mary-offline-successor/1", "SUCCESSOR_RECORD_SCHEMA_INVALID", "successor record schema differs")
    require(
        isinstance(value["componentIds"], Mapping)
        and set(value["componentIds"]) == {"cartridge", "canonical_state", "authority_boundary", "obligations", "evidence_envelope"},
        "SUCCESSOR_COMPONENT_DENOMINATOR_INVALID",
        "successor component denominator differs",
    )
    for identifier in value["componentIds"].values():
        assert_content_id(identifier, "SUCCESSOR_RECORD_INVALID", "component ID")
    assert_content_id(value["answerId"], "SUCCESSOR_RECORD_INVALID", "answer ID")
    assert_content_id(value["authorityId"], "SUCCESSOR_RECORD_INVALID", "authority ID")
    require(isinstance(value["openObligationIds"], list), "SUCCESSOR_RECORD_INVALID", "open obligations must be an array")
    require(
        len(value["openObligationIds"]) == len(set(value["openObligationIds"])),
        "SUCCESSOR_RECORD_INVALID",
        "open obligation identities duplicate",
    )
    for identifier in value["openObligationIds"]:
        assert_content_id(identifier, "SUCCESSOR_RECORD_INVALID", "open obligation ID")
    require(value["absentDependencies"] == list(ABSENT_DEPENDENCIES), "SUCCESSOR_DEPENDENCY_INVALID", "successor absent dependencies differ")
    require(
        value["networkRequired"] is False
        and value["repositoryHistoryRequired"] is False
        and value["originalHostRequired"] is False
        and value["authority"] == "none",
        "SUCCESSOR_RECORD_CLAIM_INVALID",
        "successor record widens dependency or authority",
    )
    bounded_string(value["claimBoundary"], "SUCCESSOR_RECORD_INVALID", "successor claim boundary")
    assert_identity(value, "successorId", "stcmaryofflinesuccessor1", "SUCCESSOR_ID_INVALID")
    return value


def build_successor_bundle(
    *,
    cartridge: str | Path,
    canonical_state: str | Path,
    authority: str | Path,
    obligations: str | Path,
    evidence: str | Path,
    next_safe_action: str | Path,
    out: str | Path,
    repository: str | Path,
) -> dict[str, Any]:
    repository_root = validate_repository(repository)
    output = validate_new_private_root(out, repository_root)
    source_paths = [
        Path(cartridge).expanduser().resolve(),
        Path(canonical_state).expanduser().resolve(),
        Path(authority).expanduser().resolve(),
        Path(obligations).expanduser().resolve(),
        Path(evidence).expanduser().resolve(),
        Path(next_safe_action).expanduser().resolve(),
    ]
    for source_path in source_paths:
        require(
            not is_inside(source_path, output) and not is_inside(output, source_path),
            "SOURCE_DESTINATION_OVERLAP",
            "successor source and output overlap",
        )
    authority_value = read_json(Path(authority))
    obligations_value = read_json(Path(obligations))
    validate_authority_boundary(authority_value)
    validate_open_obligations(obligations_value)
    try:
        action_bytes = Path(next_safe_action).read_bytes()
        action_text = action_bytes.decode("utf-8").strip()
    except (OSError, UnicodeDecodeError) as error:
        raise OfflineCarrierError("NEXT_SAFE_ACTION_INVALID", f"cannot read next-safe-action text: {error}") from error
    bounded_string(action_text, "NEXT_SAFE_ACTION_INVALID", "next safe action", MAX_ACTION_BYTES)
    require("REPLACE_WITH_" not in action_text, "NEXT_SAFE_ACTION_INCOMPLETE", "next safe action remains a placeholder")
    output.mkdir()
    components_root = output / "components"
    components_root.mkdir()
    component_specs = [
        ("cartridge", cartridge),
        ("canonical_state", canonical_state),
        ("authority_boundary", authority),
        ("obligations", obligations),
        ("evidence_envelope", evidence),
    ]
    manifests: list[dict[str, Any]] = []
    for label, source in component_specs:
        manifests.append(copy_source(source, components_root / label, label))
    write_json(output / "component-manifests.json", {"schema": "stc-mary-offline-component-set/1", "components": manifests, "authority": "none"})
    (output / "next-safe-action.txt").write_text(action_text + "\n", encoding="utf-8", newline="\n")
    answer = build_successor_answer(
        component_manifests=manifests,
        obligations=obligations_value,
        next_safe_action=action_text,
    )
    write_json(output / "six-question-answer.json", answer)
    successor = create_successor_record(manifests, answer, authority_value, obligations_value)
    write_json(output / "successor.json", successor)
    (output / "verify_bundle.py").write_text(STANDALONE_VERIFIER, encoding="utf-8", newline="\n")
    manifest = build_bundle_manifest(output, "successor", successor["successorId"])
    verify_successor_bundle(output)
    return {
        "status": "PASS",
        "output": str(output),
        "successorId": successor["successorId"],
        "manifestId": manifest["manifestId"],
        "authority": "none",
    }


def verify_successor_bundle(bundle: str | Path) -> dict[str, Any]:
    root = Path(bundle).expanduser().resolve()
    manifest = verify_bundle_manifest(root, "successor")
    component_set = read_json(root / "component-manifests.json")
    stable_keys(component_set, ["schema", "components", "authority"], "SUCCESSOR_COMPONENT_SET_INVALID", "component set")
    require(component_set["schema"] == "stc-mary-offline-component-set/1", "SUCCESSOR_COMPONENT_SET_INVALID", "component-set schema differs")
    require(isinstance(component_set["components"], list) and len(component_set["components"]) == 5, "SUCCESSOR_COMPONENT_SET_INVALID", "component-set denominator differs")
    require(component_set["authority"] == "none", "SUCCESSOR_COMPONENT_SET_INVALID", "component set grants authority")
    components: list[Mapping[str, Any]] = []
    labels: set[str] = set()
    for descriptor in component_set["components"]:
        validate_component_manifest(descriptor)
        label = descriptor["label"]
        require(label not in labels, "SUCCESSOR_COMPONENT_SET_INVALID", "component labels duplicate")
        labels.add(label)
        verify_component_at(root / "components" / label, descriptor)
        components.append(descriptor)
    require(labels == {"cartridge", "canonical_state", "authority_boundary", "obligations", "evidence_envelope"}, "SUCCESSOR_COMPONENT_SET_INVALID", "component labels differ")
    authority_descriptor = next(row for row in components if row["label"] == "authority_boundary")
    obligations_descriptor = next(row for row in components if row["label"] == "obligations")
    require(
        authority_descriptor["kind"] == "file"
        and authority_descriptor["fileCount"] == 1
        and obligations_descriptor["kind"] == "file"
        and obligations_descriptor["fileCount"] == 1,
        "SUCCESSOR_SEMANTIC_COMPONENT_INVALID",
        "authority and obligations components must each be one JSON file",
    )
    authority_file = root / "components" / "authority_boundary" / authority_descriptor["files"][0]["relativePath"]
    obligations_file = root / "components" / "obligations" / obligations_descriptor["files"][0]["relativePath"]
    authority_value = read_json(authority_file)
    obligations_value = read_json(obligations_file)
    validate_authority_boundary(authority_value)
    validate_open_obligations(obligations_value)
    answer = read_json(root / "six-question-answer.json")
    successor = read_json(root / "successor.json")
    validate_successor_answer(answer)
    validate_successor_record(successor)
    require(manifest["bundleId"] == successor["successorId"], "SUCCESSOR_MANIFEST_BINDING_INVALID", "manifest belongs to another successor")
    require(successor["answerId"] == answer["answerId"], "SUCCESSOR_ANSWER_BINDING_INVALID", "successor answer identity differs")
    require(
        answer["whatExists"]["componentIds"] == [row["componentId"] for row in components],
        "SUCCESSOR_ANSWER_BINDING_INVALID",
        "successor answer component identities differ",
    )
    require(
        answer["whatRemainsUnresolved"]["obligationIds"]
        == [row["obligationId"] for row in obligations_value["obligations"]],
        "SUCCESSOR_ANSWER_BINDING_INVALID",
        "successor answer obligations differ",
    )
    expected_components = {row["label"]: row["componentId"] for row in components}
    require(successor["componentIds"] == expected_components, "SUCCESSOR_COMPONENT_BINDING_INVALID", "successor component identities differ")
    require(successor["authorityId"] == authority_value["authorityId"], "SUCCESSOR_AUTHORITY_BINDING_INVALID", "successor authority identity differs")
    require(
        successor["openObligationIds"] == [row["obligationId"] for row in obligations_value["obligations"]],
        "SUCCESSOR_OBLIGATION_BINDING_INVALID",
        "successor obligations differ",
    )
    next_text = (root / "next-safe-action.txt").read_text(encoding="utf-8").strip()
    require(answer["whatIsSafeNext"]["text"] == next_text, "SUCCESSOR_ACTION_BINDING_INVALID", "successor safe action differs")
    verifier_digest, _ = stream_sha256(root / "verify_bundle.py")
    return {
        "root": root,
        "manifest": manifest,
        "components": components,
        "authorityBoundary": authority_value,
        "obligations": obligations_value,
        "answer": answer,
        "successor": successor,
        "standaloneVerifierSha256": verifier_digest,
    }


def create_successor_verification(
    verified: Mapping[str, Any],
    mode: str,
    original_host_class_digest: str,
    *,
    current_host_digest: str | None = None,
) -> dict[str, Any]:
    require(mode in ATTESTATION_MODES, "SUCCESSOR_VERIFICATION_MODE_INVALID", "successor verification mode differs")
    assert_sha256(original_host_class_digest, "SUCCESSOR_VERIFICATION_INVALID", "original host class digest")
    if mode == "private_local_attested":
        current = current_host_digest if current_host_digest is not None else host_class_digest()
    else:
        current = sha256_bytes(f"synthetic-successor:{verified['successor']['successorId']}".encode("utf-8"))
    assert_sha256(current, "SUCCESSOR_VERIFICATION_INVALID", "current host class digest")
    require(current != original_host_class_digest, "SUCCESSOR_HOST_CLASS_INVALID", "successor host class equals original host class")
    body = {
        "schema": "stc-mary-offline-successor-verification/1",
        "mode": mode,
        "successorId": verified["successor"]["successorId"],
        "manifestId": verified["manifest"]["manifestId"],
        "originalHostClassDigest": original_host_class_digest,
        "currentHostClassDigest": current,
        "hostClassChanged": True,
        "bundleVerified": True,
        "sixQuestionAnswerVerified": True,
        "absentDependenciesVerified": True,
        "absentDependencies": list(ABSENT_DEPENDENCIES),
        "standaloneVerifierSha256": verified["standaloneVerifierSha256"],
        "networkRequired": False,
        "repositoryHistoryRequired": False,
        "externalServiceCalls": 0,
        "operationalCredentials": 0,
        "authority": "none",
        "claimBoundary": "Digest-only cold-successor verification on a distinct host class. It grants no authority.",
    }
    return {**body, "verificationId": content_id("stcmaryofflinesuccessorverification1", body)}


def validate_successor_verification(value: Any) -> Mapping[str, Any]:
    stable_keys(
        value,
        [
            "schema",
            "verificationId",
            "mode",
            "successorId",
            "manifestId",
            "originalHostClassDigest",
            "currentHostClassDigest",
            "hostClassChanged",
            "bundleVerified",
            "sixQuestionAnswerVerified",
            "absentDependenciesVerified",
            "absentDependencies",
            "standaloneVerifierSha256",
            "networkRequired",
            "repositoryHistoryRequired",
            "externalServiceCalls",
            "operationalCredentials",
            "authority",
            "claimBoundary",
        ],
        "SUCCESSOR_VERIFICATION_INVALID",
        "successor verification",
    )
    require(value["schema"] == "stc-mary-offline-successor-verification/1", "SUCCESSOR_VERIFICATION_SCHEMA_INVALID", "successor verification schema differs")
    require(value["mode"] in ATTESTATION_MODES, "SUCCESSOR_VERIFICATION_MODE_INVALID", "successor verification mode differs")
    assert_content_id(value["successorId"], "SUCCESSOR_VERIFICATION_INVALID", "successor ID")
    assert_content_id(value["manifestId"], "SUCCESSOR_VERIFICATION_INVALID", "manifest ID")
    for key in ("originalHostClassDigest", "currentHostClassDigest", "standaloneVerifierSha256"):
        assert_sha256(value[key], "SUCCESSOR_VERIFICATION_INVALID", key)
    require(
        value["originalHostClassDigest"] != value["currentHostClassDigest"]
        and value["hostClassChanged"] is True,
        "SUCCESSOR_HOST_CLASS_INVALID",
        "successor host class did not change",
    )
    require(
        value["bundleVerified"] is True
        and value["sixQuestionAnswerVerified"] is True
        and value["absentDependenciesVerified"] is True
        and value["absentDependencies"] == list(ABSENT_DEPENDENCIES),
        "SUCCESSOR_VERIFICATION_INVALID",
        "successor verification does not close reconstruction",
    )
    require(
        value["networkRequired"] is False
        and value["repositoryHistoryRequired"] is False
        and value["externalServiceCalls"] == 0
        and value["operationalCredentials"] == 0
        and value["authority"] == "none",
        "SUCCESSOR_VERIFICATION_CLAIM_INVALID",
        "successor verification widens dependency or authority",
    )
    bounded_string(value["claimBoundary"], "SUCCESSOR_VERIFICATION_INVALID", "successor verification claim boundary")
    assert_identity(value, "verificationId", "stcmaryofflinesuccessorverification1", "SUCCESSOR_VERIFICATION_ID_INVALID")
    return value


def verify_successor(
    *,
    bundle: str | Path,
    mode: str,
    original_host_class_digest: str,
    out: str | Path,
    repository: str | Path | None = None,
) -> dict[str, Any]:
    bundle_root = Path(bundle).expanduser().resolve()
    verified = verify_successor_bundle(bundle_root)
    receipt = create_successor_verification(verified, mode, original_host_class_digest)
    output = validate_new_receipt_path(out, repository)
    require(
        not is_inside(bundle_root, output),
        "RECEIPT_MUTATES_BUNDLE",
        "verification receipt may not be written inside the verified successor bundle",
    )
    write_json(output, receipt)
    return {
        "status": "PASS",
        "verificationId": receipt["verificationId"],
        "successorId": receipt["successorId"],
        "mode": receipt["mode"],
        "output": str(output),
        "authority": "none",
    }


def load_profile(path: str | Path) -> Mapping[str, Any]:
    profile = read_json(Path(path))
    stable_keys(
        profile,
        [
            "schema",
            "profileId",
            "status",
            "predecessorCommit",
            "commands",
            "bundleTypes",
            "modes",
            "claimBoundary",
        ],
        "PROFILE_INVALID",
        "offline carrier profile",
    )
    require(profile["schema"] == PROFILE_SCHEMA, "PROFILE_SCHEMA_INVALID", "offline carrier profile schema differs")
    require(profile["profileId"] == PROFILE_ID, "PROFILE_ID_INVALID", "offline carrier profile ID differs")
    require(profile["status"] == "candidate_design_only", "PROFILE_STATUS_INVALID", "offline carrier profile status differs")
    require(profile["predecessorCommit"] == PREDECESSOR_COMMIT, "PROFILE_PREDECESSOR_INVALID", "offline carrier predecessor differs")
    require(profile["commands"] == list(COMMANDS), "PROFILE_COMMAND_DENOMINATOR_INVALID", "offline carrier command denominator differs")
    require(profile["bundleTypes"] == list(BUNDLE_TYPES), "PROFILE_BUNDLE_DENOMINATOR_INVALID", "offline carrier bundle denominator differs")
    require(profile["modes"] == ["synthetic_simulation", "private_local_attested"], "PROFILE_MODE_DENOMINATOR_INVALID", "offline carrier mode denominator differs")
    bounded_string(profile["claimBoundary"], "PROFILE_INVALID", "offline carrier claim boundary")
    return profile


def template_inputs(*, out: str | Path, repository: str | Path) -> dict[str, Any]:
    repository_root = validate_repository(repository)
    output = validate_new_private_root(out, repository_root)
    output.mkdir()
    common = {
        "schema": "stc-mary-private-common-state-template/1",
        "state": {"replaceWithPrivateCanonicalState": True},
        "authority": "none",
    }
    write_json(output / "common-state.json", common)
    left = record_cell_delta("left", {"replaceWithPrivateLeftObservation": True}, "1" * 64)
    right = record_cell_delta("right", {"replaceWithPrivateRightObservation": True}, "2" * 64)
    write_json(output / "left-delta.json", left)
    write_json(output / "right-delta.json", right)
    authority = create_authority_boundary()
    write_json(output / "authority.json", authority)
    obligations = {
        "schema": "stc-mary-open-obligations/1",
        "obligations": [
            create_open_obligation(
                "replace_with_private_open_obligation",
                "Replace this template obligation with the actual unresolved private obligation set.",
            )
        ],
        "authority": "none",
        "claimBoundary": "Template open-obligation set. Replace before a physical campaign.",
    }
    write_json(output / "obligations.json", obligations)
    write_json(
        output / "evidence-envelope.json",
        {
            "schema": "stc-mary-private-evidence-envelope-template/1",
            "replaceWithPrivateEvidenceEnvelope": True,
            "authority": "none",
        },
    )
    (output / "next-safe-action.txt").write_text(
        "REPLACE_WITH_PRIVATE_NEXT_SAFE_ACTION\n",
        encoding="utf-8",
        newline="\n",
    )
    return {"status": "PASS", "output": str(output), "authority": "none"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Provider-free offline two-cell and cold-successor carrier for STC MARY."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    template = subparsers.add_parser("template-inputs")
    template.add_argument("--out", required=True)
    template.add_argument("--repository", required=True)

    pair = subparsers.add_parser("build-cell-pair")
    pair.add_argument("--common-state", required=True)
    pair.add_argument("--left-delta", required=True)
    pair.add_argument("--right-delta", required=True)
    pair.add_argument("--authority", required=True)
    pair.add_argument("--campaign-label", required=True)
    pair.add_argument("--out", required=True)
    pair.add_argument("--repository", required=True)

    verify_cell_parser = subparsers.add_parser("verify-cell")
    verify_cell_parser.add_argument("--bundle", required=True)
    verify_cell_parser.add_argument("--mode", required=True, choices=sorted(ATTESTATION_MODES))
    verify_cell_parser.add_argument("--out", required=True)
    verify_cell_parser.add_argument("--repository")

    reconcile = subparsers.add_parser("reconcile-cells")
    reconcile.add_argument("--left-bundle", required=True)
    reconcile.add_argument("--right-bundle", required=True)
    reconcile.add_argument("--left-verification", required=True)
    reconcile.add_argument("--right-verification", required=True)
    reconcile.add_argument("--out", required=True)
    reconcile.add_argument("--repository")

    successor = subparsers.add_parser("build-successor")
    successor.add_argument("--cartridge", required=True)
    successor.add_argument("--canonical-state", required=True)
    successor.add_argument("--authority", required=True)
    successor.add_argument("--obligations", required=True)
    successor.add_argument("--evidence", required=True)
    successor.add_argument("--next-safe-action", required=True)
    successor.add_argument("--out", required=True)
    successor.add_argument("--repository", required=True)

    verify_successor_parser = subparsers.add_parser("verify-successor")
    verify_successor_parser.add_argument("--bundle", required=True)
    verify_successor_parser.add_argument("--mode", required=True, choices=sorted(ATTESTATION_MODES))
    verify_successor_parser.add_argument("--original-host-class-digest", required=True)
    verify_successor_parser.add_argument("--out", required=True)
    verify_successor_parser.add_argument("--repository")

    profile = subparsers.add_parser("validate-profile")
    profile.add_argument("path")
    return parser


def dispatch(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "template-inputs":
        return template_inputs(out=args.out, repository=args.repository)
    if args.command == "build-cell-pair":
        return build_cell_pair(
            common_state_path=args.common_state,
            left_delta_path=args.left_delta,
            right_delta_path=args.right_delta,
            authority_path=args.authority,
            campaign_label=args.campaign_label,
            out=args.out,
            repository=args.repository,
        )
    if args.command == "verify-cell":
        return verify_cell(
            bundle=args.bundle,
            mode=args.mode,
            out=args.out,
            repository=args.repository,
        )
    if args.command == "reconcile-cells":
        return reunite_cells(
            left_bundle=args.left_bundle,
            right_bundle=args.right_bundle,
            left_verification=args.left_verification,
            right_verification=args.right_verification,
            out=args.out,
            repository=args.repository,
        )
    if args.command == "build-successor":
        return build_successor_bundle(
            cartridge=args.cartridge,
            canonical_state=args.canonical_state,
            authority=args.authority,
            obligations=args.obligations,
            evidence=args.evidence,
            next_safe_action=args.next_safe_action,
            out=args.out,
            repository=args.repository,
        )
    if args.command == "verify-successor":
        return verify_successor(
            bundle=args.bundle,
            mode=args.mode,
            original_host_class_digest=args.original_host_class_digest,
            out=args.out,
            repository=args.repository,
        )
    if args.command == "validate-profile":
        profile = load_profile(args.path)
        return {"status": "PASS", "profileId": profile["profileId"], "authority": "none"}
    raise OfflineCarrierError("COMMAND_INVALID", f"unknown command: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        print(json.dumps(dispatch(args), indent=2, ensure_ascii=False))
        return 0
    except OfflineCarrierError as error:
        print(f"{error.code}: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("INTERRUPTED: operator interrupted the offline carrier", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
