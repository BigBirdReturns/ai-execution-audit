from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

HERE = Path(__file__).resolve().parent
SOURCE_ROOT = HERE.parent.parent
DEFAULT_PROFILE = HERE / "stc-mary-flight-conductor-profile-01.json"
PROFILE_FILE_SHA256 = "ca1fa71c7168dbcca9ff3e77930d06621350f5509ca922968eb3b40e709cadeb"
PROFILE_ID = "stc-mary/private-flight-conductor/0.1"
PROFILE_SCHEMA = "stc-mary-flight-conductor-profile/1"
REQUIRED_REPOSITORY = "BigBirdReturns/ai-execution-audit"
REQUIRED_COMMIT = "d31e59f5fd30e57b1917c00832b189ee2ea3e12f"
REQUIRED_TREE = "2a6a155e9615eb847781f87566bac32d4c9dc126"
TOOLCHAIN_PROFILE_ID = "stc-mary/local-toolchain/0.1"
PHASE_SEQUENCE = (
    "admitted_checkout",
    "artifact_coordinates",
    "readiness",
    "feed",
    "personal_floor",
    "halo3",
    "post_halo3_continuity",
    "two_cell_partition",
    "successor_head",
    "flight_plan",
    "private_packet",
    "sealed_flight",
)
ARTIFACT_LABELS = ("cartridge", "model", "verifier", "storage")
OPERATOR_ACTIONS = (
    "readiness",
    "feed",
    "personal-floor",
    "halo3",
    "post-halo3-continuity",
    "two-cell",
    "successor-head",
    "compile-plan",
    "seal",
)
OPERATOR_ACTION_PHASES = {
    "readiness": "readiness",
    "feed": "feed",
    "personal-floor": "personal_floor",
    "halo3": "halo3",
    "post-halo3-continuity": "post_halo3_continuity",
    "two-cell": "two_cell_partition",
    "successor-head": "successor_head",
    "compile-plan": "flight_plan",
    "seal": "sealed_flight",
}
SOURCE_MEMBERS = (
    ".github/workflows/stc-mary-flight-conductor-01.yml",
    "mating_surface/anchor_node/STC-MARY-FLIGHT-CONDUCTOR-RUNBOOK.md",
    "mating_surface/anchor_node/conformance/test_stc_mary_flight_conductor.py",
    "mating_surface/anchor_node/stc-mary-flight-conductor-profile-01.json",
    "mating_surface/anchor_node/stc-mary-flight-conductor.ps1",
    "mating_surface/anchor_node/stc_mary_flight_conductor.py",
)
WORKSPACE_PATTERN = re.compile(r"^stc-mary-flight-conductor-[a-z0-9][a-z0-9._-]*$", re.I)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CONTENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*_[0-9a-f]{64}$")
CAMPAIGN_LABEL_RE = re.compile(r"^[A-Z0-9][A-Z0-9._-]{2,255}$")
PHASE_STATES = {"CLOSED", "HOLD", "REFUSED"}
MAX_JSON_BYTES = 64 * 1024 * 1024
MAX_ARTIFACTS = 16
MAX_PATH_CHARS = 32768

MARKER_FILE = "CONDUCTOR-ROOT.json"
CONFIG_FILE = "campaign-config.private.json"
PATH_MAP_FILE = "path-map.private.json"
OPERATOR_SCRIPT_FILE = "operator-flight.ps1"
LEDGER_FILE = "progress-ledger.json"
NEXT_ACTION_FILE = "NEXT-SAFE-ACTION.md"
HANDOFF_FILE = "packet-handoff.private.json"
HANDOFF_SCRIPT_FILE = "packet-handoff.ps1"
PUBLIC_PROJECTION_FILE = "workstation-public-projection.json"

CLAIM_BOUNDARY = (
    "Receipt-derived status for one source-pinned private campaign workstation. "
    "It performs no physical action, invents no evidence, and grants no hardware, model, verifier, "
    "scheduler, transport, physical-Estate, representative-operator, field-network, operational-C2, "
    "production-Lattice, mission, command, targeting, engagement, effector, or weapons qualification or authority."
)


class ConductorError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise ConductorError(code, message)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def content_id(prefix: str, value: Any) -> str:
    return f"{prefix}_{sha256_bytes(canonical_json(value).encode('utf-8'))}"


def body_without(value: Mapping[str, Any], key: str) -> dict[str, Any]:
    result = dict(value)
    result.pop(key, None)
    return result


def assert_identity(value: Mapping[str, Any], id_key: str, prefix: str, code: str) -> None:
    require(value.get(id_key) == content_id(prefix, body_without(value, id_key)), code, f"{id_key} differs from content identity")


def exact_keys(value: Any, expected: Iterable[str], code: str, label: str) -> Mapping[str, Any]:
    require(isinstance(value, Mapping), code, f"{label} must be an object")
    require(set(value.keys()) == set(expected), code, f"{label} fields differ")
    return value


def bounded_string(value: Any, code: str, label: str, maximum: int = 8192) -> str:
    require(isinstance(value, str), code, f"{label} must be a string")
    normalized = value.strip()
    require(0 < len(normalized) <= maximum, code, f"{label} is empty or unbounded")
    return normalized


def assert_sha256(value: Any, code: str, label: str) -> str:
    require(isinstance(value, str) and SHA256_RE.fullmatch(value) is not None, code, f"{label} is not a lowercase SHA-256 digest")
    return value


def assert_content_id(value: Any, code: str, label: str) -> str:
    require(isinstance(value, str) and CONTENT_ID_RE.fullmatch(value) is not None, code, f"{label} is not a content identity")
    return value


def safe_int(value: Any, minimum: int, maximum: int, code: str, label: str) -> int:
    require(isinstance(value, int) and not isinstance(value, bool) and minimum <= value <= maximum, code, f"{label} is outside {minimum}..{maximum}")
    return value


def read_bytes(path: Path) -> bytes:
    try:
        metadata = path.stat()
    except OSError as error:
        raise ConductorError("FILE_READ_INVALID", f"cannot stat {path}: {error}") from error
    require(path.is_file() and not path.is_symlink(), "FILE_TYPE_INVALID", f"required regular file is absent or symlinked: {path}")
    require(0 < metadata.st_size <= MAX_JSON_BYTES, "FILE_SIZE_INVALID", f"file is empty or unbounded: {path}")
    try:
        return path.read_bytes()
    except OSError as error:
        raise ConductorError("FILE_READ_INVALID", f"cannot read {path}: {error}") from error


def read_json(path: Path) -> Any:
    raw = read_bytes(path)
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ConductorError("JSON_READ_INVALID", f"cannot parse JSON {path}: {error}") from error


def write_json(path: Path, value: Any, *, replace: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    require(replace or not path.exists(), "OUTPUT_EXISTS", f"output already exists: {path}")
    encoded = (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    require(not temporary.exists(), "TEMPORARY_OUTPUT_EXISTS", f"temporary output exists: {temporary}")
    with temporary.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def write_text(path: Path, value: str, *, replace: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    require(replace or not path.exists(), "OUTPUT_EXISTS", f"output already exists: {path}")
    encoded = value.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    require(not temporary.exists(), "TEMPORARY_OUTPUT_EXISTS", f"temporary output exists: {temporary}")
    with temporary.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def is_inside(ancestor: Path, target: Path) -> bool:
    try:
        target.relative_to(ancestor)
        return True
    except ValueError:
        return False


def paths_overlap(left: Path, right: Path) -> bool:
    return is_inside(left, right) or is_inside(right, left)


def resolved_path(value: str | Path) -> Path:
    text = bounded_string(str(value), "PATH_INVALID", "path", MAX_PATH_CHARS)
    return Path(text).expanduser().resolve()


def run_command(command: Sequence[str], *, cwd: Path | None = None, timeout: float = 30.0) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            [str(item) for item in command],
            cwd=str(cwd) if cwd else None,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ConductorError("COMMAND_EXECUTION_FAILED", f"cannot execute {command[0]}: {type(error).__name__}") from error


def command_text(result: subprocess.CompletedProcess[bytes], code: str, label: str) -> str:
    require(result.returncode == 0, code, f"{label} failed with exit {result.returncode}")
    try:
        return result.stdout.decode("utf-8").strip()
    except UnicodeDecodeError as error:
        raise ConductorError(code, f"{label} output is not UTF-8") from error


def git_snapshot(repository: Path) -> dict[str, Any]:
    repository = repository.expanduser().resolve()
    require(repository.is_dir(), "REPOSITORY_MISSING", f"repository is absent: {repository}")
    root = command_text(run_command(["git", "rev-parse", "--show-toplevel"], cwd=repository), "REPOSITORY_GIT_INVALID", "git root probe")
    head = command_text(run_command(["git", "rev-parse", "HEAD"], cwd=repository), "REPOSITORY_GIT_INVALID", "git HEAD probe")
    tree = command_text(run_command(["git", "rev-parse", "HEAD^{tree}"], cwd=repository), "REPOSITORY_GIT_INVALID", "git tree probe")
    status_result = run_command(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=repository)
    status = command_text(status_result, "REPOSITORY_GIT_INVALID", "git status probe")
    branch_result = run_command(["git", "symbolic-ref", "-q", "--short", "HEAD"], cwd=repository)
    require(branch_result.returncode in {0, 1}, "REPOSITORY_GIT_INVALID", "git symbolic-ref probe failed")
    branch = branch_result.stdout.decode("utf-8", errors="replace").strip() if branch_result.returncode == 0 else None
    body = {
        "schema": "stc-mary-flight-conductor-source-receipt/1",
        "repositoryRoot": str(Path(root).resolve()),
        "head": head,
        "tree": tree,
        "clean": status == "",
        "detached": branch is None,
        "statusSha256": sha256_bytes(status_result.stdout),
        "authority": "none",
        "claimBoundary": "Exact local Git coordinate observation. It grants no execution or command authority.",
    }
    return {**body, "sourceReceiptId": content_id("stcmaryflightconductorsourcereceipt1", body)}


def validate_source_snapshot(snapshot: Mapping[str, Any], repository: Path) -> None:
    exact_keys(snapshot, [
        "schema", "sourceReceiptId", "repositoryRoot", "head", "tree", "clean", "detached",
        "statusSha256", "authority", "claimBoundary",
    ], "SOURCE_RECEIPT_INVALID", "source receipt")
    require(snapshot["schema"] == "stc-mary-flight-conductor-source-receipt/1", "SOURCE_RECEIPT_INVALID", "source receipt schema differs")
    require(Path(snapshot["repositoryRoot"]).resolve() == repository.resolve(), "SOURCE_RECEIPT_INVALID", "source receipt names another repository")
    require(snapshot["head"] == REQUIRED_COMMIT, "SOURCE_COMMIT_INVALID", f"repository HEAD must equal {REQUIRED_COMMIT}")
    require(snapshot["tree"] == REQUIRED_TREE, "SOURCE_TREE_INVALID", f"repository tree must equal {REQUIRED_TREE}")
    require(snapshot["clean"] is True, "SOURCE_WORKTREE_DIRTY", "repository contains tracked or untracked change")
    require(snapshot["detached"] is True, "SOURCE_MOVING_BRANCH_REFUSED", "repository must be detached from every moving branch")
    assert_sha256(snapshot["statusSha256"], "SOURCE_RECEIPT_INVALID", "status digest")
    require(snapshot["authority"] == "none", "SOURCE_AUTHORITY_INVALID", "source receipt grants authority")
    assert_identity(snapshot, "sourceReceiptId", "stcmaryflightconductorsourcereceipt1", "SOURCE_RECEIPT_ID_INVALID")


def source_set_receipt() -> dict[str, Any]:
    members: list[dict[str, Any]] = []
    for relative in SOURCE_MEMBERS:
        path = (SOURCE_ROOT / relative).resolve()
        require(is_inside(SOURCE_ROOT.resolve(), path), "SOURCE_SET_PATH_INVALID", "source member escapes source root")
        raw = read_bytes(path)
        members.append({"relativePath": relative, "sha256": sha256_bytes(raw), "bytes": len(raw)})
    body = {
        "schema": "stc-mary-flight-conductor-source-set/1",
        "profileId": PROFILE_ID,
        "members": members,
        "memberCount": len(members),
        "totalBytes": sum(row["bytes"] for row in members),
        "authority": "none",
        "claimBoundary": "Exact six-member conductor source set. It identifies source bytes and grants no authority.",
    }
    return {**body, "sourceSetId": content_id("stcmaryflightconductorsourceset1", body)}


def validate_profile_structure(profile: Any) -> Mapping[str, Any]:
    exact_keys(profile, [
        "schema", "profileId", "status", "repository", "requiredCommit", "requiredTree", "queueIssue",
        "workItemIssue", "workspaceDirectoryPattern", "repositoryOutputAllowed", "networkRequired",
        "externalServiceCalls", "operationalCredentials", "artifactLabels", "selectedCudaIndexRange", "feed",
        "phaseSequence", "phases", "authority", "claimBoundary",
    ], "CONDUCTOR_PROFILE_INVALID", "conductor profile")
    require(profile["schema"] == PROFILE_SCHEMA and profile["profileId"] == PROFILE_ID, "CONDUCTOR_PROFILE_INVALID", "profile identity differs")
    require(profile["status"] == "candidate_design_only", "CONDUCTOR_PROFILE_INVALID", "profile status differs")
    require(profile["repository"] == REQUIRED_REPOSITORY, "CONDUCTOR_PROFILE_INVALID", "profile repository differs")
    require(profile["requiredCommit"] == REQUIRED_COMMIT and profile["requiredTree"] == REQUIRED_TREE, "CONDUCTOR_PROFILE_INVALID", "profile predecessor differs")
    require(profile["queueIssue"] == 37 and profile["workItemIssue"] == 44, "CONDUCTOR_PROFILE_INVALID", "profile issue binding differs")
    require(profile["workspaceDirectoryPattern"] == WORKSPACE_PATTERN.pattern, "CONDUCTOR_PROFILE_INVALID", "workspace pattern differs")
    require(profile["repositoryOutputAllowed"] is False and profile["networkRequired"] is False, "CONDUCTOR_PROFILE_INVALID", "profile widens repository or network surface")
    require(profile["externalServiceCalls"] == 0 and profile["operationalCredentials"] == 0 and profile["authority"] == "none", "CONDUCTOR_PROFILE_INVALID", "profile widens service, credential, or authority surface")
    require(profile["artifactLabels"] == list(ARTIFACT_LABELS), "CONDUCTOR_PROFILE_INVALID", "artifact denominator differs")
    require(profile["selectedCudaIndexRange"] == [0, 31], "CONDUCTOR_PROFILE_INVALID", "CUDA index range differs")
    require(profile["feed"] == {"records": 262144, "features": 32, "classes": 8, "seed": 20260827}, "CONDUCTOR_PROFILE_INVALID", "feed coordinate differs")
    require(profile["phaseSequence"] == list(PHASE_SEQUENCE), "CONDUCTOR_PROFILE_INVALID", "phase sequence differs")
    exact_keys(profile["phases"], PHASE_SEQUENCE, "CONDUCTOR_PROFILE_INVALID", "phase definitions")
    for phase in PHASE_SEQUENCE:
        row = exact_keys(profile["phases"][phase], [
            "receiptClasses", "operatorAction", "nextSafeAction", "wakeCondition", "repairAction", "controlQuestion",
        ], "CONDUCTOR_PROFILE_INVALID", f"phase {phase}")
        require(isinstance(row["receiptClasses"], list) and row["receiptClasses"], "CONDUCTOR_PROFILE_INVALID", f"phase {phase} receipt classes differ")
        require(len(set(row["receiptClasses"])) == len(row["receiptClasses"]), "CONDUCTOR_PROFILE_INVALID", f"phase {phase} receipt classes duplicate")
        for key in ("operatorAction", "nextSafeAction", "wakeCondition", "repairAction", "controlQuestion"):
            bounded_string(row[key], "CONDUCTOR_PROFILE_INVALID", f"phase {phase} {key}", 4096)
    bounded_string(profile["claimBoundary"], "CONDUCTOR_PROFILE_INVALID", "profile claim boundary", 8192)
    return profile


def load_profile(path: Path = DEFAULT_PROFILE) -> Mapping[str, Any]:
    raw = read_bytes(path)
    require(sha256_bytes(raw) == PROFILE_FILE_SHA256, "CONDUCTOR_PROFILE_FROZEN_BYTES_MISMATCH", "conductor profile bytes differ from the frozen profile")
    try:
        profile = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ConductorError("CONDUCTOR_PROFILE_INVALID", f"cannot parse conductor profile: {error}") from error
    return validate_profile_structure(profile)


def validate_private_parent(parent: Path, repository: Path) -> Path:
    parent = parent.expanduser().resolve()
    require(parent.is_dir() and not parent.is_symlink(), "PRIVATE_PARENT_INVALID", "private parent must be an existing non-symlink directory")
    require(parent != Path(parent.anchor), "PRIVATE_PARENT_UNSAFE", "private parent may not be a filesystem root")
    require(parent != Path.home().resolve(), "PRIVATE_PARENT_UNSAFE", "private parent may not be the user home")
    require(parent != Path.cwd().resolve(), "PRIVATE_PARENT_UNSAFE", "private parent may not be the current working directory")
    require(not paths_overlap(parent, repository.resolve()), "PRIVATE_PARENT_REPOSITORY_OVERLAP", "private parent and repository overlap")
    return parent


def parse_artifacts(items: Sequence[str], repository: Path, private_parent: Path, workspace: Path) -> list[dict[str, Any]]:
    require(0 < len(items) <= MAX_ARTIFACTS, "ARTIFACT_ARGUMENT_INVALID", "artifact arguments are empty or unbounded")
    coordinates: list[dict[str, Any]] = []
    labels: set[str] = set()
    paths: list[Path] = []
    for item in items:
        require(isinstance(item, str) and "=" in item, "ARTIFACT_ARGUMENT_INVALID", "artifact must use LABEL=PATH")
        label, raw_path = item.split("=", 1)
        label = label.strip()
        require(label in ARTIFACT_LABELS, "ARTIFACT_LABEL_UNKNOWN", f"unknown artifact label: {label}")
        require(label not in labels, "ARTIFACT_LABEL_DUPLICATE", f"duplicate artifact label: {label}")
        path = resolved_path(raw_path)
        require(path.exists() and not path.is_symlink(), "ARTIFACT_COORDINATE_MISSING", f"artifact coordinate is absent or symlinked: {label}")
        require(path.is_file() or path.is_dir(), "ARTIFACT_COORDINATE_TYPE_INVALID", f"artifact coordinate has unsupported type: {label}")
        require(not paths_overlap(path, repository.resolve()), "ARTIFACT_REPOSITORY_OVERLAP", f"artifact overlaps repository: {label}")
        require(not paths_overlap(path, workspace), "ARTIFACT_WORKSPACE_OVERLAP", f"artifact overlaps workstation: {label}")
        for other in paths:
            require(not paths_overlap(path, other), "ARTIFACT_COORDINATE_OVERLAP", "artifact coordinates overlap")
        body = {"label": label, "privatePath": str(path), "kind": "file" if path.is_file() else "directory"}
        coordinates.append({**body, "coordinateId": content_id("stcmaryflightconductorartifactcoordinate1", body)})
        labels.add(label)
        paths.append(path)
    require(labels == set(ARTIFACT_LABELS), "ARTIFACT_DENOMINATOR_INVALID", "exactly cartridge, model, verifier, and storage coordinates are required")
    return sorted(coordinates, key=lambda row: ARTIFACT_LABELS.index(row["label"]))


def generated_paths(workstation: Path) -> dict[str, str]:
    root = workstation.resolve()
    products = root / "products"
    sealed = products / "stc-mary-private-flight-sealed-local-01"
    return {
        "workstation": str(root),
        "products": str(products),
        "prep": str(products / "stc-mary-local-prep-flight-01"),
        "readiness": str(products / "stc-mary-local-prep-flight-01" / "readiness-private.json"),
        "feed": str(products / "stc-mary-local-feed-flight-01"),
        "feedManifest": str(products / "stc-mary-local-feed-flight-01" / "feed-manifest.json"),
        "baseline": str(products / "personal-floor-baseline.json"),
        "baselineVerification": str(products / "personal-floor-baseline-verification.json"),
        "accelerated": str(products / "halo3-accelerated.json"),
        "acceleratedVerification": str(products / "halo3-accelerated-verification.json"),
        "continuity": str(products / "personal-floor-after-halo3-removal.json"),
        "continuityVerification": str(products / "personal-floor-after-halo3-removal-verification.json"),
        "comparison": str(products / "personal-floor-halo3-comparison.json"),
        "offlineInputs": str(products / "stc-mary-offline-inputs-flight-01"),
        "cellPair": str(products / "stc-mary-offline-pair-flight-01"),
        "leftCellVerification": str(products / "left-cell-verification.private.json"),
        "rightCellVerification": str(products / "right-cell-verification.private.json"),
        "reunion": str(products / "stc-mary-reunion-flight-01"),
        "twoCellVerification": str(products / "stc-mary-reunion-flight-01" / "two-cell-verification.json"),
        "successor": str(products / "stc-mary-successor-flight-01"),
        "successorVerification": str(products / "successor-verification.private.json"),
        "plan": str(products / "stc-mary-local-plan-flight-01"),
        "flightPlan": str(products / "stc-mary-local-plan-flight-01" / "local-flight-plan.json"),
        "flightConfig": str(products / "stc-mary-local-plan-flight-01" / "flight-config.generated.json"),
        "packet": str(products / "stc-mary-private-flight-local-01"),
        "packetState": str(products / "stc-mary-private-flight-local-01" / "packet-state.json"),
        "sealed": str(sealed),
        "detachedVerification": str(sealed / "detached-verification.json"),
        "publicDisposition": str(sealed / "public-disposition.json"),
    }


def path_map_record(campaign_id: str, workstation: Path) -> dict[str, Any]:
    body = {
        "schema": "stc-mary-flight-conductor-path-map/1",
        "campaignId": campaign_id,
        "paths": generated_paths(workstation),
        "authority": "none",
        "claimBoundary": "Private generated path map for one campaign root. It grants no authority and is not suitable for public projection.",
    }
    return {**body, "pathMapId": content_id("stcmaryflightconductorpathmap1", body)}


def campaign_coordinate_id(*, campaign_label: str, repository: Path, private_parent: Path, selected_cuda: int, artifacts: Sequence[Mapping[str, Any]], source_set_id: str) -> str:
    body = {
        "profileId": PROFILE_ID,
        "campaignLabel": campaign_label,
        "requiredRepository": REQUIRED_REPOSITORY,
        "requiredCommit": REQUIRED_COMMIT,
        "requiredTree": REQUIRED_TREE,
        "repositoryPath": str(repository.resolve()),
        "privateParent": str(private_parent.resolve()),
        "selectedCudaDeviceIndex": selected_cuda,
        "artifactCoordinateIds": [row["coordinateId"] for row in artifacts],
        "sourceSetId": source_set_id,
    }
    return content_id("stcmaryflightconductorcampaign1", body)


def config_record(*, campaign_id: str, campaign_label: str, created_at: int, repository: Path, private_parent: Path, selected_cuda: int, artifacts: Sequence[Mapping[str, Any]], source_receipt: Mapping[str, Any], source_set: Mapping[str, Any], path_map_id: str) -> dict[str, Any]:
    body = {
        "schema": "stc-mary-flight-conductor-config/1",
        "profileId": PROFILE_ID,
        "campaignId": campaign_id,
        "campaignLabel": campaign_label,
        "createdAtUnixNs": created_at,
        "executionSource": {
            "repository": REQUIRED_REPOSITORY,
            "requiredCommit": REQUIRED_COMMIT,
            "requiredTree": REQUIRED_TREE,
            "repositoryPath": str(repository.resolve()),
            "sourceReceiptId": source_receipt["sourceReceiptId"],
        },
        "conductorSourceSetId": source_set["sourceSetId"],
        "privateParent": str(private_parent.resolve()),
        "selectedCudaDeviceIndex": selected_cuda,
        "artifacts": list(artifacts),
        "pathMapId": path_map_id,
        "authority": "none",
        "claimBoundary": "Immutable private campaign configuration. Paths remain private and no coordinate grants authority.",
    }
    return {**body, "configId": content_id("stcmaryflightconductorconfig1", body)}


def marker_record(*, campaign_id: str, campaign_label: str, created_at: int, config_id: str, path_map_id: str, source_set_id: str) -> dict[str, Any]:
    body = {
        "schema": "stc-mary-flight-conductor-root/1",
        "profileId": PROFILE_ID,
        "campaignId": campaign_id,
        "campaignLabel": campaign_label,
        "createdAtUnixNs": created_at,
        "configId": config_id,
        "pathMapId": path_map_id,
        "sourceSetId": source_set_id,
        "authority": "none",
        "claimBoundary": "Marker for one immutable private flight-conductor workstation outside public Git.",
    }
    return {**body, "markerId": content_id("stcmaryflightconductorroot1", body)}


def ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def render_operator_script(config: Mapping[str, Any], paths: Mapping[str, str]) -> str:
    artifacts = {row["label"]: row["privatePath"] for row in config["artifacts"]}
    repo = config["executionSource"]["repositoryPath"]
    conductor = str((HERE / "stc-mary-flight-conductor.ps1").resolve())
    action_set = ", ".join(ps_quote(action) for action in OPERATOR_ACTIONS)
    lines = [
        "[CmdletBinding(PositionalBinding = $false)]",
        "param(",
        "    [Parameter(Mandatory = $true, Position = 0)]",
        f"    [ValidateSet({action_set})]",
        "    [string]$Action",
        ")",
        "",
        "$ErrorActionPreference = 'Stop'",
        "$ProgressPreference = 'SilentlyContinue'",
        "",
        "if ($args.Count -ne 0) {",
        "    throw 'operator-flight.ps1 accepts exactly one closed action name and no additional arguments.'",
        "}",
        "",
        f"$Conductor = {ps_quote(conductor)}",
        "$Workstation = $PSScriptRoot",
        f"$Repo = {ps_quote(repo)}",
        f"$Campaign = {ps_quote(config['campaignLabel'])}",
        f"$Tool = Join-Path $Repo {ps_quote('mating_surface\\anchor_node\\stc-mary-local-toolchain.ps1')}",
        f"$Carrier = Join-Path $Repo {ps_quote('mating_surface\\anchor_node\\stc-mary-offline-carrier.ps1')}",
        f"$PacketRunner = Join-Path $Repo {ps_quote('mating_surface\\anchor_node\\stc-mary-private-flight.ps1')}",
        f"$Prep = {ps_quote(paths['prep'])}",
        f"$Feed = {ps_quote(paths['feed'])}",
        f"$Baseline = {ps_quote(paths['baseline'])}",
        f"$BaselineVerification = {ps_quote(paths['baselineVerification'])}",
        f"$Accelerated = {ps_quote(paths['accelerated'])}",
        f"$AcceleratedVerification = {ps_quote(paths['acceleratedVerification'])}",
        f"$Continuity = {ps_quote(paths['continuity'])}",
        f"$ContinuityVerification = {ps_quote(paths['continuityVerification'])}",
        f"$Comparison = {ps_quote(paths['comparison'])}",
        f"$Inputs = {ps_quote(paths['offlineInputs'])}",
        f"$Pair = {ps_quote(paths['cellPair'])}",
        f"$LeftVerification = {ps_quote(paths['leftCellVerification'])}",
        f"$RightVerification = {ps_quote(paths['rightCellVerification'])}",
        f"$Reunion = {ps_quote(paths['reunion'])}",
        f"$Successor = {ps_quote(paths['successor'])}",
        f"$SuccessorVerification = {ps_quote(paths['successorVerification'])}",
        f"$Plan = {ps_quote(paths['plan'])}",
        f"$Packet = {ps_quote(paths['packet'])}",
        f"$Sealed = {ps_quote(paths['sealed'])}",
        f"$CudaDeviceIndex = {config['selectedCudaDeviceIndex']}",
        "",
        "function Invoke-Checked {",
        "    param(",
        "        [Parameter(Mandatory = $true)][string]$Label,",
        "        [Parameter(Mandatory = $true)][scriptblock]$Operation",
        "    )",
        "    $global:LASTEXITCODE = 0",
        "    & $Operation",
        "    $exitCode = $LASTEXITCODE",
        "    if ($null -eq $exitCode) { $exitCode = 0 }",
        "    if ($exitCode -ne 0) {",
        "        throw \"$Label refused with exit $exitCode.\"",
        "    }",
        "}",
        "",
        "function Get-ConductorStatus {",
        "    $global:LASTEXITCODE = 0",
        "    $raw = & $Conductor status --workstation $Workstation 2>&1",
        "    $exitCode = $LASTEXITCODE",
        "    if ($exitCode -ne 0) {",
        "        throw \"Conductor status refused with exit $exitCode.\"",
        "    }",
        "    try {",
        "        return (($raw -join [Environment]::NewLine) | ConvertFrom-Json -ErrorAction Stop)",
        "    }",
        "    catch {",
        "        throw 'Conductor status did not return one JSON object.'",
        "    }",
        "}",
        "",
        "function Assert-CurrentPhase {",
        "    param([Parameter(Mandatory = $true)][string]$ExpectedPhase)",
        "    $status = Get-ConductorStatus",
        "    if ($status.refusedPhaseCount -ne 0) {",
        "        throw 'The workstation contains a refused phase and cannot execute an operator action.'",
        "    }",
        "    if ($status.currentPhase -ne $ExpectedPhase) {",
        "        throw \"Action '$Action' requires current phase '$ExpectedPhase'; observed '$($status.currentPhase)'.\"",
        "    }",
        "}",
        "",
        "function Assert-RegularFile {",
        "    param(",
        "        [Parameter(Mandatory = $true)][string]$Path,",
        "        [Parameter(Mandatory = $true)][string]$Label",
        "    )",
        "    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {",
        "        throw \"$Label is absent: $Path\"",
        "    }",
        "    $item = Get-Item -LiteralPath $Path -Force",
        "    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {",
        "        throw \"$Label is a reparse point: $Path\"",
        "    }",
        "}",
        "",
        "function Assert-RegularDirectory {",
        "    param(",
        "        [Parameter(Mandatory = $true)][string]$Path,",
        "        [Parameter(Mandatory = $true)][string]$Label",
        "    )",
        "    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {",
        "        throw \"$Label is absent: $Path\"",
        "    }",
        "    $item = Get-Item -LiteralPath $Path -Force",
        "    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {",
        "        throw \"$Label is a reparse point: $Path\"",
        "    }",
        "}",
        "",
        "function Assert-ReadinessPython {",
        "    if ([string]::IsNullOrWhiteSpace($env:STC_MARY_PYTHON)) {",
        "        throw 'Set STC_MARY_PYTHON to one exact Python 3.11-or-later interpreter before readiness.'",
        "    }",
        "    $resolved = Resolve-Path -LiteralPath $env:STC_MARY_PYTHON -ErrorAction Stop",
        "    if (-not (Test-Path -LiteralPath $resolved.Path -PathType Leaf)) {",
        "        throw 'STC_MARY_PYTHON does not resolve to a regular file.'",
        "    }",
        "    $probeProgram = \"import json,sys,torch; print(json.dumps({'version':[sys.version_info.major,sys.version_info.minor],'cudaAvailable':bool(torch.cuda.is_available()),'deviceCount':int(torch.cuda.device_count()),'devices':list(range(torch.cuda.device_count()))},sort_keys=True,separators=(',',':')))\"",
        "    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()",
        "    $startInfo.FileName = $resolved.Path",
        "    $startInfo.UseShellExecute = $false",
        "    $startInfo.RedirectStandardOutput = $true",
        "    $startInfo.RedirectStandardError = $true",
        "    $startInfo.CreateNoWindow = $true",
        "    if ($startInfo.PSObject.Properties.Name -contains 'ArgumentList') {",
        "        [void]$startInfo.ArgumentList.Add('-c')",
        "        [void]$startInfo.ArgumentList.Add($probeProgram)",
        "    }",
        "    else {",
        """    $startInfo.Arguments = '-c "' + $probeProgram + '"'""",
        "    }",
        "    $process = [System.Diagnostics.Process]::new()",
        "    $process.StartInfo = $startInfo",
        "    $stdoutCapture = [System.IO.MemoryStream]::new()",
        "    $stderrCapture = [System.IO.MemoryStream]::new()",
        "    $stdoutBuffer = [byte[]]::new(4096)",
        "    $stderrBuffer = [byte[]]::new(4096)",
        "    $streamLimit = 65536",
        "    $probeTimeoutMilliseconds = 60000",
        "    $probeFailure = $null",
        "    $processStarted = $false",
        "    try {",
        "        if (-not $process.Start()) {",
        "            $probeFailure = 'The selected readiness interpreter could not be started.'",
        "        }",
        "        else {",
        "            $processStarted = $true",
        "        }",
        "        if ($null -eq $probeFailure) {",
        "            $stdoutStream = $process.StandardOutput.BaseStream",
        "            $stderrStream = $process.StandardError.BaseStream",
        "            $stdoutTask = $stdoutStream.ReadAsync($stdoutBuffer, 0, $stdoutBuffer.Length)",
        "            $stderrTask = $stderrStream.ReadAsync($stderrBuffer, 0, $stderrBuffer.Length)",
        "            $stdoutDone = $false",
        "            $stderrDone = $false",
        "            $timer = [System.Diagnostics.Stopwatch]::StartNew()",
        "            while (-not ($process.HasExited -and $stdoutDone -and $stderrDone)) {",
        "                if ($timer.ElapsedMilliseconds -gt $probeTimeoutMilliseconds) {",
        "                    $probeFailure = 'The selected readiness interpreter exceeded the Torch probe time limit.'",
        "                    break",
        "                }",
        "                if (-not $stdoutDone -and $stdoutTask.IsCompleted) {",
        "                    $read = $stdoutTask.GetAwaiter().GetResult()",
        "                    if ($read -eq 0) {",
        "                        $stdoutDone = $true",
        "                    }",
        "                    elseif ($stdoutCapture.Length + $read -gt $streamLimit) {",
        "                        $probeFailure = 'The selected readiness interpreter returned an oversized Torch probe.'",
        "                        break",
        "                    }",
        "                    else {",
        "                        $stdoutCapture.Write($stdoutBuffer, 0, $read)",
        "                        $stdoutTask = $stdoutStream.ReadAsync($stdoutBuffer, 0, $stdoutBuffer.Length)",
        "                    }",
        "                }",
        "                if (-not $stderrDone -and $stderrTask.IsCompleted) {",
        "                    $read = $stderrTask.GetAwaiter().GetResult()",
        "                    if ($read -eq 0) {",
        "                        $stderrDone = $true",
        "                    }",
        "                    elseif ($stderrCapture.Length + $read -gt $streamLimit) {",
        "                        $probeFailure = 'The selected readiness interpreter returned oversized diagnostic output.'",
        "                        break",
        "                    }",
        "                    else {",
        "                        $stderrCapture.Write($stderrBuffer, 0, $read)",
        "                        $stderrTask = $stderrStream.ReadAsync($stderrBuffer, 0, $stderrBuffer.Length)",
        "                    }",
        "                }",
        "                if ($null -eq $probeFailure -and -not ($process.HasExited -and $stdoutDone -and $stderrDone)) {",
        "                    [System.Threading.Thread]::Sleep(10)",
        "                }",
        "            }",
        "            $timer.Stop()",
        "        }",
        "        if ($null -eq $probeFailure) {",
        "            $process.WaitForExit()",
        "            $exitCode = $process.ExitCode",
        "            $probeStdout = [System.Text.Encoding]::UTF8.GetString($stdoutCapture.ToArray())",
        "            $probeStderr = [System.Text.Encoding]::UTF8.GetString($stderrCapture.ToArray())",
        "        }",
        "    }",
        "    catch {",
        "        if ($null -eq $probeFailure) {",
        "            $probeFailure = 'The selected readiness interpreter could not be started or observed.'",
        "        }",
        "    }",
        "    finally {",
        "        if ($processStarted -and $null -ne $probeFailure) {",
        "            try {",
        "                if (-not $process.HasExited) { $process.Kill() }",
        "            }",
        "            catch { }",
        "            try { [void]$process.WaitForExit(5000) } catch { }",
        "        }",
        "        $stdoutCapture.Dispose()",
        "        $stderrCapture.Dispose()",
        "        $process.Dispose()",
        "    }",
        "    if ($null -ne $probeFailure) {",
        "        throw $probeFailure",
        "    }",
        "    if ($exitCode -ne 0) {",
        "        throw \"The selected readiness interpreter cannot import and probe Torch; exit $exitCode.\"",
        "    }",
        "    if ([string]::IsNullOrWhiteSpace($probeStdout)) {",
        "        throw 'The selected readiness interpreter returned an empty Torch probe.'",
        "    }",
        "    try {",
        "        $probe = ($probeStdout | ConvertFrom-Json -ErrorAction Stop)",
        "    }",
        "    catch {",
        "        throw 'The selected readiness interpreter returned an invalid Torch probe.'",
        "    }",
        "    if ($probe.version.Count -ne 2 -or $probe.version[0] -lt 3 -or ($probe.version[0] -eq 3 -and $probe.version[1] -lt 11)) {",
        "        throw 'The selected readiness interpreter is older than Python 3.11.'",
        "    }",
        "    if ($probe.cudaAvailable -ne $true) {",
        "        throw 'The selected readiness interpreter does not expose torch.cuda.'",
        "    }",
        "    if ($CudaDeviceIndex -lt 0 -or $CudaDeviceIndex -ge $probe.deviceCount -or $probe.devices -notcontains $CudaDeviceIndex) {",
        "        throw \"The selected readiness interpreter does not expose CUDA device index $CudaDeviceIndex.\"",
        "    }",
        "    $env:STC_MARY_PYTHON = $resolved.Path",
        "}",
        "",
        "switch ($Action) {",
        "    'readiness' {",
        "        Assert-CurrentPhase 'readiness'",
        "        Assert-ReadinessPython",
        "        Invoke-Checked 'readiness doctor' {",
        "            & $Tool doctor --repository $Repo --out $Prep `",
        f"              --artifact {ps_quote('cartridge=' + artifacts['cartridge'])} `",
        f"              --artifact {ps_quote('model=' + artifacts['model'])} `",
        f"              --artifact {ps_quote('verifier=' + artifacts['verifier'])} `",
        f"              --artifact {ps_quote('storage=' + artifacts['storage'])}",
        "        }",
        "        exit 0",
        "    }",
        "    'feed' {",
        "        Assert-CurrentPhase 'feed'",
        "        Invoke-Checked 'deterministic feed generation' {",
        "            & $Tool generate-feed --out $Feed --records 262144 --features 32 --classes 8 --seed 20260827",
        "        }",
        "        exit 0",
        "    }",
        "    'personal-floor' {",
        "        Assert-CurrentPhase 'personal_floor'",
        "        Invoke-Checked 'resident-floor workload' {",
        "            & $Tool run-workload --feed $Feed --backend python --out $Baseline",
        "        }",
        "        Invoke-Checked 'resident-floor verification' {",
        "            & $Tool verify-workload --feed $Feed --result $Baseline --out $BaselineVerification",
        "        }",
        "        exit 0",
        "    }",
        "    'halo3' {",
        "        Assert-CurrentPhase 'halo3'",
        "        Invoke-Checked 'HALO3 workload' {",
        "            & $Tool run-workload --feed $Feed --backend torch-cuda --device-index $CudaDeviceIndex --out $Accelerated",
        "        }",
        "        Invoke-Checked 'HALO3 verification' {",
        "            & $Tool verify-workload --feed $Feed --result $Accelerated --out $AcceleratedVerification",
        "        }",
        "        exit 0",
        "    }",
        "    'post-halo3-continuity' {",
        "        Assert-CurrentPhase 'post_halo3_continuity'",
        "        Invoke-Checked 'post-HALO3 resident workload' {",
        "            & $Tool run-workload --feed $Feed --backend python --out $Continuity",
        "        }",
        "        Invoke-Checked 'post-HALO3 resident verification' {",
        "            & $Tool verify-workload --feed $Feed --result $Continuity --out $ContinuityVerification",
        "        }",
        "        Invoke-Checked 'three-way continuity comparison' {",
        "            & $Tool compare-workloads --baseline $Baseline --accelerated $Accelerated --continuity $Continuity --out $Comparison",
        "        }",
        "        exit 0",
        "    }",
        "    'two-cell' {",
        "        Assert-CurrentPhase 'two_cell_partition'",
        "        if (-not (Test-Path -LiteralPath $Inputs)) {",
        "            Invoke-Checked 'two-cell private input template' {",
        "                & $Carrier template-inputs --out $Inputs --repository $Repo",
        "            }",
        "            exit 0",
        "        }",
        "        Assert-RegularDirectory $Inputs 'two-cell private input root'",
        "        if (-not (Test-Path -LiteralPath $Pair)) {",
        "            foreach ($requiredInput in @('common-state.json', 'left-delta.json', 'right-delta.json', 'authority.json')) {",
        "                Assert-RegularFile (Join-Path $Inputs $requiredInput) \"two-cell input $requiredInput\"",
        "            }",
        "            Invoke-Checked 'two-cell pair construction' {",
        "                & $Carrier build-cell-pair --common-state (Join-Path $Inputs 'common-state.json') --left-delta (Join-Path $Inputs 'left-delta.json') --right-delta (Join-Path $Inputs 'right-delta.json') --authority (Join-Path $Inputs 'authority.json') --campaign-label $Campaign --out $Pair --repository $Repo",
        "            }",
        "            exit 0",
        "        }",
        "        Assert-RegularDirectory $Pair 'two-cell pair root'",
        "        if (-not (Test-Path -LiteralPath $Reunion)) {",
        "            Assert-RegularFile $LeftVerification 'left private host verification'",
        "            Assert-RegularFile $RightVerification 'right private host verification'",
        "            Invoke-Checked 'two-cell HUMAN_REQUIRED reunion' {",
        "                & $Carrier reconcile-cells --left-bundle (Join-Path $Pair 'left') --right-bundle (Join-Path $Pair 'right') --left-verification $LeftVerification --right-verification $RightVerification --out $Reunion --repository $Repo",
        "            }",
        "            exit 0",
        "        }",
        "        throw 'No locally executable two-cell subtransaction remains. Preserve the existing products and return to conductor status.'",
        "    }",
        "    'successor-head' {",
        "        Assert-CurrentPhase 'successor_head'",
        "        if (Test-Path -LiteralPath $Successor) {",
        "            throw 'The successor bundle already exists. Replacement-host attestation remains a separate human-controlled transaction.'",
        "        }",
        "        foreach ($requiredInput in @('common-state.json', 'authority.json', 'obligations.json', 'evidence-envelope.json', 'next-safe-action.txt')) {",
        "            Assert-RegularFile (Join-Path $Inputs $requiredInput) \"successor input $requiredInput\"",
        "        }",
        "        Invoke-Checked 'cold-successor bundle construction' {",
        f"            & $Carrier build-successor --cartridge {ps_quote(artifacts['cartridge'])} --canonical-state (Join-Path $Inputs 'common-state.json') --authority (Join-Path $Inputs 'authority.json') --obligations (Join-Path $Inputs 'obligations.json') --evidence (Join-Path $Inputs 'evidence-envelope.json') --next-safe-action (Join-Path $Inputs 'next-safe-action.txt') --out $Successor --repository $Repo",
        "        }",
        "        exit 0",
        "    }",
        "    'compile-plan' {",
        "        Assert-CurrentPhase 'flight_plan'",
        "        Invoke-Checked 'eight-gate flight-plan compilation' {",
        "            & $Tool compile-plan --repository $Repo --readiness (Join-Path $Prep 'readiness-private.json') --feed $Feed --baseline $Baseline --accelerated $Accelerated --continuity $Continuity --cell-verification (Join-Path $Reunion 'two-cell-verification.json') --successor-verification $SuccessorVerification --campaign-label $Campaign --required-commit " + REQUIRED_COMMIT + " --out $Plan",
        "        }",
        "        exit 0",
        "    }",
        "    'seal' {",
        "        Assert-CurrentPhase 'sealed_flight'",
        "        Assert-RegularDirectory $Packet 'completed private packet root'",
        "        if (Test-Path -LiteralPath $Sealed) {",
        "            throw 'The sealed output already exists.'",
        "        }",
        "        Invoke-Checked 'private packet sealing' {",
        "            & $PacketRunner seal $Packet $Sealed",
        "        }",
        "        Invoke-Checked 'detached sealed-package verification' {",
        "            & $PacketRunner verify-sealed $Sealed (Join-Path $Sealed 'detached-verification.json')",
        "        }",
        "        exit 0",
        "    }",
        "}",
        "",
    ]
    return "\n".join(lines)


def initialize_workstation(args: argparse.Namespace) -> dict[str, Any]:
    profile = load_profile(Path(args.profile))
    repository = resolved_path(args.repository)
    source_receipt = git_snapshot(repository)
    validate_source_snapshot(source_receipt, repository)
    private_parent = validate_private_parent(resolved_path(args.private_parent), repository)
    workstation = resolved_path(args.out)
    require(workstation.parent == private_parent, "WORKSTATION_PARENT_INVALID", "workstation must be a direct child of the declared private parent")
    require(WORKSPACE_PATTERN.fullmatch(workstation.name) is not None, "WORKSTATION_NAME_INVALID", "workstation name differs from the dedicated pattern")
    require(not workstation.exists(), "WORKSTATION_EXISTS", "workstation root already exists")
    require(not paths_overlap(workstation, repository), "WORKSTATION_REPOSITORY_OVERLAP", "workstation and repository overlap")
    campaign_label = bounded_string(args.campaign_label, "CAMPAIGN_LABEL_INVALID", "campaign label", 256)
    require(CAMPAIGN_LABEL_RE.fullmatch(campaign_label) is not None and not campaign_label.startswith("REPLACE_WITH_"), "CAMPAIGN_LABEL_INVALID", "campaign label is a placeholder or differs from the closed form")
    selected_cuda = safe_int(args.cuda_device_index, profile["selectedCudaIndexRange"][0], profile["selectedCudaIndexRange"][1], "CUDA_DEVICE_INDEX_INVALID", "CUDA device index")
    artifacts = parse_artifacts(args.artifact, repository, private_parent, workstation)
    source_set = source_set_receipt()
    campaign_id = campaign_coordinate_id(
        campaign_label=campaign_label,
        repository=repository,
        private_parent=private_parent,
        selected_cuda=selected_cuda,
        artifacts=artifacts,
        source_set_id=source_set["sourceSetId"],
    )
    path_map = path_map_record(campaign_id, workstation)
    created_at = time.time_ns()
    config = config_record(
        campaign_id=campaign_id,
        campaign_label=campaign_label,
        created_at=created_at,
        repository=repository,
        private_parent=private_parent,
        selected_cuda=selected_cuda,
        artifacts=artifacts,
        source_receipt=source_receipt,
        source_set=source_set,
        path_map_id=path_map["pathMapId"],
    )
    marker = marker_record(
        campaign_id=campaign_id,
        campaign_label=campaign_label,
        created_at=created_at,
        config_id=config["configId"],
        path_map_id=path_map["pathMapId"],
        source_set_id=source_set["sourceSetId"],
    )
    workstation.mkdir()
    (workstation / "products").mkdir()
    write_json(workstation / MARKER_FILE, marker)
    write_json(workstation / CONFIG_FILE, config)
    write_json(workstation / PATH_MAP_FILE, path_map)
    write_json(workstation / "conductor-source-set.json", source_set)
    write_text(workstation / OPERATOR_SCRIPT_FILE, render_operator_script(config, path_map["paths"]))
    result = derive_status(workstation, persist=True)
    write_public_projection(workstation, result, workstation / PUBLIC_PROJECTION_FILE, replace=False)
    return {
        "status": "INITIALIZED",
        "campaignId": campaign_id,
        "markerId": marker["markerId"],
        "configId": config["configId"],
        "pathMapId": path_map["pathMapId"],
        "sourceSetId": source_set["sourceSetId"],
        "currentPhase": result["currentPhase"],
        "authority": "none",
    }


@dataclass(frozen=True)
class Workstation:
    root: Path
    profile: Mapping[str, Any]
    marker: Mapping[str, Any]
    config: Mapping[str, Any]
    path_map: Mapping[str, Any]
    source_set: Mapping[str, Any]

    @property
    def paths(self) -> Mapping[str, str]:
        return self.path_map["paths"]

    def path(self, key: str) -> Path:
        return Path(self.paths[key]).resolve()


def validate_artifact_coordinate(value: Any) -> Mapping[str, Any]:
    exact_keys(value, ["label", "privatePath", "kind", "coordinateId"], "ARTIFACT_COORDINATE_INVALID", "artifact coordinate")
    require(value["label"] in ARTIFACT_LABELS, "ARTIFACT_COORDINATE_INVALID", "artifact coordinate label differs")
    require(value["kind"] in {"file", "directory"}, "ARTIFACT_COORDINATE_INVALID", "artifact coordinate kind differs")
    bounded_string(value["privatePath"], "ARTIFACT_COORDINATE_INVALID", "artifact private path", MAX_PATH_CHARS)
    assert_identity(value, "coordinateId", "stcmaryflightconductorartifactcoordinate1", "ARTIFACT_COORDINATE_ID_INVALID")
    return value


def load_workstation(root: str | Path) -> Workstation:
    profile = load_profile(DEFAULT_PROFILE)
    root = resolved_path(root)
    require(root.is_dir() and not root.is_symlink(), "WORKSTATION_ROOT_INVALID", "workstation root is absent or symlinked")
    require(WORKSPACE_PATTERN.fullmatch(root.name) is not None, "WORKSTATION_ROOT_INVALID", "workstation root name differs")
    marker = read_json(root / MARKER_FILE)
    config = read_json(root / CONFIG_FILE)
    path_map = read_json(root / PATH_MAP_FILE)
    source_set = read_json(root / "conductor-source-set.json")
    exact_keys(marker, [
        "schema", "markerId", "profileId", "campaignId", "campaignLabel", "createdAtUnixNs", "configId",
        "pathMapId", "sourceSetId", "authority", "claimBoundary",
    ], "WORKSTATION_MARKER_INVALID", "workstation marker")
    require(marker["schema"] == "stc-mary-flight-conductor-root/1" and marker["profileId"] == PROFILE_ID and marker["authority"] == "none", "WORKSTATION_MARKER_INVALID", "workstation marker identity or authority differs")
    assert_content_id(marker["campaignId"], "WORKSTATION_MARKER_INVALID", "campaign ID")
    assert_identity(marker, "markerId", "stcmaryflightconductorroot1", "WORKSTATION_MARKER_ID_INVALID")
    exact_keys(config, [
        "schema", "configId", "profileId", "campaignId", "campaignLabel", "createdAtUnixNs", "executionSource",
        "conductorSourceSetId", "privateParent", "selectedCudaDeviceIndex", "artifacts", "pathMapId", "authority", "claimBoundary",
    ], "WORKSTATION_CONFIG_INVALID", "workstation config")
    require(config["schema"] == "stc-mary-flight-conductor-config/1" and config["profileId"] == PROFILE_ID and config["authority"] == "none", "WORKSTATION_CONFIG_INVALID", "workstation config identity or authority differs")
    exact_keys(config["executionSource"], ["repository", "requiredCommit", "requiredTree", "repositoryPath", "sourceReceiptId"], "WORKSTATION_CONFIG_INVALID", "execution source")
    require(config["executionSource"]["repository"] == REQUIRED_REPOSITORY and config["executionSource"]["requiredCommit"] == REQUIRED_COMMIT and config["executionSource"]["requiredTree"] == REQUIRED_TREE, "WORKSTATION_CONFIG_INVALID", "execution source coordinate differs")
    assert_content_id(config["executionSource"]["sourceReceiptId"], "WORKSTATION_CONFIG_INVALID", "source receipt ID")
    require(isinstance(config["artifacts"], list) and len(config["artifacts"]) == len(ARTIFACT_LABELS), "WORKSTATION_CONFIG_INVALID", "artifact coordinate denominator differs")
    for row in config["artifacts"]:
        validate_artifact_coordinate(row)
    require([row["label"] for row in config["artifacts"]] == list(ARTIFACT_LABELS), "WORKSTATION_CONFIG_INVALID", "artifact coordinate order differs")
    safe_int(config["selectedCudaDeviceIndex"], 0, 31, "WORKSTATION_CONFIG_INVALID", "CUDA device index")
    assert_identity(config, "configId", "stcmaryflightconductorconfig1", "WORKSTATION_CONFIG_ID_INVALID")
    exact_keys(path_map, ["schema", "pathMapId", "campaignId", "paths", "authority", "claimBoundary"], "WORKSTATION_PATH_MAP_INVALID", "path map")
    require(path_map["schema"] == "stc-mary-flight-conductor-path-map/1" and path_map["authority"] == "none", "WORKSTATION_PATH_MAP_INVALID", "path map identity or authority differs")
    require(path_map["paths"] == generated_paths(root), "WORKSTATION_PATH_MAP_INVALID", "path map differs from deterministic campaign map")
    assert_identity(path_map, "pathMapId", "stcmaryflightconductorpathmap1", "WORKSTATION_PATH_MAP_ID_INVALID")
    validate_source_set(source_set)
    require(marker["campaignId"] == config["campaignId"] == path_map["campaignId"], "WORKSTATION_BINDING_INVALID", "campaign identities differ")
    require(marker["campaignLabel"] == config["campaignLabel"], "WORKSTATION_BINDING_INVALID", "campaign labels differ")
    require(marker["createdAtUnixNs"] == config["createdAtUnixNs"], "WORKSTATION_BINDING_INVALID", "creation times differ")
    require(marker["configId"] == config["configId"] and marker["pathMapId"] == config["pathMapId"] == path_map["pathMapId"], "WORKSTATION_BINDING_INVALID", "marker, config, and path map differ")
    require(marker["sourceSetId"] == config["conductorSourceSetId"] == source_set["sourceSetId"], "WORKSTATION_BINDING_INVALID", "source set binding differs")
    private_parent = Path(config["privateParent"]).resolve()
    require(root.parent == private_parent, "WORKSTATION_BINDING_INVALID", "workstation is no longer a direct child of the private parent")
    require(Path(config["executionSource"]["repositoryPath"]).resolve() != root, "WORKSTATION_BINDING_INVALID", "repository and workstation coincide")
    expected_campaign = campaign_coordinate_id(
        campaign_label=config["campaignLabel"],
        repository=Path(config["executionSource"]["repositoryPath"]),
        private_parent=private_parent,
        selected_cuda=config["selectedCudaDeviceIndex"],
        artifacts=config["artifacts"],
        source_set_id=source_set["sourceSetId"],
    )
    require(expected_campaign == marker["campaignId"], "WORKSTATION_CAMPAIGN_ID_INVALID", "campaign coordinate differs")
    expected_script = render_operator_script(config, path_map["paths"]).encode("utf-8")
    require(read_bytes(root / OPERATOR_SCRIPT_FILE) == expected_script, "WORKSTATION_OPERATOR_SCRIPT_DRIFT", "operator script differs from immutable campaign coordinates")
    return Workstation(root, profile, marker, config, path_map, source_set)


def validate_source_set(value: Any) -> Mapping[str, Any]:
    exact_keys(value, ["schema", "sourceSetId", "profileId", "members", "memberCount", "totalBytes", "authority", "claimBoundary"], "SOURCE_SET_INVALID", "source set")
    require(value["schema"] == "stc-mary-flight-conductor-source-set/1" and value["profileId"] == PROFILE_ID and value["authority"] == "none", "SOURCE_SET_INVALID", "source set identity or authority differs")
    require(isinstance(value["members"], list) and value["memberCount"] == len(SOURCE_MEMBERS) == len(value["members"]), "SOURCE_SET_INVALID", "source set denominator differs")
    require([row.get("relativePath") for row in value["members"]] == list(SOURCE_MEMBERS), "SOURCE_SET_INVALID", "source member order differs")
    total = 0
    for row in value["members"]:
        exact_keys(row, ["relativePath", "sha256", "bytes"], "SOURCE_SET_INVALID", "source member")
        assert_sha256(row["sha256"], "SOURCE_SET_INVALID", "source member digest")
        total += safe_int(row["bytes"], 1, MAX_JSON_BYTES, "SOURCE_SET_INVALID", "source member bytes")
    require(total == value["totalBytes"], "SOURCE_SET_INVALID", "source set byte denominator differs")
    assert_identity(value, "sourceSetId", "stcmaryflightconductorsourceset1", "SOURCE_SET_ID_INVALID")
    return value


@dataclass
class PhaseResult:
    phase: str
    state: str
    evidence: list[str]
    reason_code: str | None = None
    reason: str | None = None
    detail: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        require(self.phase in PHASE_SEQUENCE, "PHASE_RESULT_INVALID", "phase result names an unknown phase")
        require(self.state in PHASE_STATES, "PHASE_RESULT_INVALID", "phase result state differs")
        require(len(self.evidence) == len(set(self.evidence)), "PHASE_RESULT_INVALID", "phase evidence identities duplicate")
        for identity in self.evidence:
            require(isinstance(identity, str) and (CONTENT_ID_RE.fullmatch(identity) or SHA256_RE.fullmatch(identity)), "PHASE_RESULT_INVALID", "phase evidence identity is malformed")


def closed(phase: str, evidence: Sequence[str], detail: Mapping[str, Any] | None = None) -> PhaseResult:
    return PhaseResult(phase, "CLOSED", list(evidence), detail=dict(detail or {}))


def held(phase: str, evidence: Sequence[str] = (), code: str | None = None, reason: str | None = None, detail: Mapping[str, Any] | None = None) -> PhaseResult:
    return PhaseResult(phase, "HOLD", list(evidence), code, reason, dict(detail or {}))


def refused(phase: str, error: Exception, evidence: Sequence[str] = ()) -> PhaseResult:
    code = error.code if isinstance(error, ConductorError) else type(error).__name__
    return PhaseResult(phase, "REFUSED", list(evidence), code, str(error), {})


def optional_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    require(path.is_file() and not path.is_symlink(), "RECEIPT_PATH_INVALID", f"receipt path is not a regular file: {path}")
    return read_json(path)


def import_admitted_validators(repository: Path) -> dict[str, Callable[..., Any]]:
    anchor = repository / "mating_surface" / "anchor_node"
    require(anchor.is_dir(), "ADMITTED_VALIDATOR_SURFACE_MISSING", "admitted anchor-node validator surface is absent")
    inserted = False
    if str(anchor) not in sys.path:
        sys.path.insert(0, str(anchor))
        inserted = True
    try:
        from stc_mary_local.workload_feed import validate_feed_manifest  # type: ignore
        from stc_mary_local.workload_compute import validate_workload_result  # type: ignore
        from stc_mary_offline_carrier import validate_successor_verification, validate_two_cell_verification  # type: ignore
        return {
            "feed": validate_feed_manifest,
            "workload": validate_workload_result,
            "two_cell": validate_two_cell_verification,
            "successor": validate_successor_verification,
        }
    except Exception as error:
        raise ConductorError("ADMITTED_VALIDATOR_IMPORT_FAILED", f"cannot import admitted validators: {type(error).__name__}: {error}") from error
    finally:
        if inserted and sys.path and sys.path[0] == str(anchor):
            sys.path.pop(0)


def validate_readiness_receipt(value: Any, ws: Workstation) -> Mapping[str, Any]:
    exact_keys(value, [
        "schema", "readinessId", "profileId", "capturedAtUnixNs", "host", "repository", "commands", "pythonModules", "torch",
        "nvidiaQuery", "nvidiaGpus", "windows", "artifacts", "externalServiceCalls", "operationalCredentials", "authority", "claimBoundary",
    ], "READINESS_RECEIPT_INVALID", "readiness receipt")
    require(value["schema"] == "stc-mary-local-readiness-private/1" and value["profileId"] == TOOLCHAIN_PROFILE_ID, "READINESS_RECEIPT_INVALID", "readiness schema or profile differs")
    require(value["externalServiceCalls"] == 0 and value["operationalCredentials"] == 0 and value["authority"] == "none", "READINESS_RECEIPT_INVALID", "readiness widens service, credential, or authority surface")
    require(isinstance(value["capturedAtUnixNs"], int) and value["capturedAtUnixNs"] >= ws.config["createdAtUnixNs"], "READINESS_RECEIPT_STALE", "readiness predates campaign initialization")
    repository = exact_keys(value["repository"], ["head", "branch", "root", "clean", "statusSha256", "commandReceipts", "privateStatus"], "READINESS_RECEIPT_INVALID", "readiness repository")
    require(repository["head"] == REQUIRED_COMMIT and repository["clean"] is True, "READINESS_SOURCE_MISMATCH", "readiness names another or dirty source checkout")
    require(repository["branch"] in {None, ""}, "READINESS_MOVING_BRANCH_REFUSED", "readiness was captured from a moving branch")
    require(Path(repository["root"]).resolve() == Path(ws.config["executionSource"]["repositoryPath"]).resolve(), "READINESS_SOURCE_MISMATCH", "readiness names another repository path")
    assert_sha256(repository["statusSha256"], "READINESS_RECEIPT_INVALID", "readiness status digest")
    require(isinstance(value["artifacts"], list) and len(value["artifacts"]) == len(ARTIFACT_LABELS), "READINESS_ARTIFACT_DENOMINATOR_INVALID", "readiness artifact denominator differs")
    expected = {row["label"]: row for row in ws.config["artifacts"]}
    seen: set[str] = set()
    for artifact in value["artifacts"]:
        exact_keys(artifact, ["schema", "artifactId", "label", "kind", "files", "fileCount", "totalBytes", "authority", "claimBoundary", "privatePath"], "READINESS_ARTIFACT_INVALID", "readiness artifact")
        label = artifact["label"]
        require(label in expected and label not in seen, "READINESS_ARTIFACT_INVALID", "readiness artifact label differs or duplicates")
        require(Path(artifact["privatePath"]).resolve() == Path(expected[label]["privatePath"]).resolve(), "READINESS_ARTIFACT_COORDINATE_MISMATCH", f"readiness artifact coordinate differs: {label}")
        require(artifact["kind"] == expected[label]["kind"], "READINESS_ARTIFACT_COORDINATE_MISMATCH", f"readiness artifact kind differs: {label}")
        require(artifact["schema"] == "stc-mary-local-artifact-manifest/1" and artifact["authority"] == "none", "READINESS_ARTIFACT_INVALID", "readiness artifact schema or authority differs")
        require(isinstance(artifact["files"], list) and artifact["fileCount"] == len(artifact["files"]) and artifact["fileCount"] > 0, "READINESS_ARTIFACT_INVALID", "readiness artifact file denominator differs")
        total = 0
        for row in artifact["files"]:
            exact_keys(row, ["relativePath", "sha256", "bytes"], "READINESS_ARTIFACT_INVALID", "readiness artifact file")
            bounded_string(row["relativePath"], "READINESS_ARTIFACT_INVALID", "artifact relative path", MAX_PATH_CHARS)
            assert_sha256(row["sha256"], "READINESS_ARTIFACT_INVALID", "artifact file digest")
            total += safe_int(row["bytes"], 1, 8 * 1024**4, "READINESS_ARTIFACT_INVALID", "artifact file bytes")
        require(total == artifact["totalBytes"], "READINESS_ARTIFACT_INVALID", "readiness artifact byte denominator differs")
        artifact_identity = {key: item for key, item in artifact.items() if key != "privatePath"}
        assert_identity(artifact_identity, "artifactId", "stcmarylocalartifact1", "READINESS_ARTIFACT_ID_INVALID")
        seen.add(label)
    require(seen == set(ARTIFACT_LABELS), "READINESS_ARTIFACT_DENOMINATOR_INVALID", "readiness artifact labels differ")
    assert_identity(value, "readinessId", "stcmarylocalreadiness1", "READINESS_RECEIPT_ID_INVALID")
    return value


def cuda_device_observed(readiness: Mapping[str, Any], index: int) -> bool:
    torch = readiness.get("torch")
    if not isinstance(torch, Mapping) or torch.get("cudaAvailable") is not True:
        return False
    devices = torch.get("devices")
    return isinstance(devices, list) and any(isinstance(row, Mapping) and row.get("index") == index for row in devices)


def validate_workload_verification(value: Any, result: Mapping[str, Any], feed_id: str) -> Mapping[str, Any]:
    exact_keys(value, [
        "schema", "verificationId", "feedId", "resultId", "status", "verifier", "recordDenominatorVerified",
        "featureDigestVerified", "classificationDigestVerified", "semanticOutputVerified", "classCountsVerified",
        "verificationElapsedSeconds", "externalServiceCalls", "operationalCredentials", "authority", "claimBoundary",
    ], "WORKLOAD_VERIFICATION_INVALID", "workload verification")
    require(value["schema"] == "stc-mary-aperture-workload-verification/1" and value["status"] == "PASS", "WORKLOAD_VERIFICATION_INVALID", "workload verification schema or status differs")
    require(value["feedId"] == feed_id and value["resultId"] == result["resultId"], "WORKLOAD_VERIFICATION_BINDING_INVALID", "workload verification names another feed or result")
    require(value["verifier"] == "python-stdlib-independent/1", "WORKLOAD_VERIFICATION_INVALID", "workload verifier differs")
    for key in ("recordDenominatorVerified", "featureDigestVerified", "classificationDigestVerified", "semanticOutputVerified", "classCountsVerified"):
        require(value[key] is True, "WORKLOAD_VERIFICATION_INVALID", f"{key} is not true")
    require(isinstance(value["verificationElapsedSeconds"], (int, float)) and value["verificationElapsedSeconds"] > 0, "WORKLOAD_VERIFICATION_INVALID", "verification elapsed time differs")
    require(value["externalServiceCalls"] == 0 and value["operationalCredentials"] == 0 and value["authority"] == "none", "WORKLOAD_VERIFICATION_INVALID", "verification widens service, credential, or authority surface")
    assert_identity(value, "verificationId", "stcmaryapertureworkloadverification1", "WORKLOAD_VERIFICATION_ID_INVALID")
    return value


def validate_comparison(value: Any, baseline: Mapping[str, Any], accelerated: Mapping[str, Any], continuity: Mapping[str, Any]) -> Mapping[str, Any]:
    exact_keys(value, [
        "schema", "comparisonId", "feedId", "baselineResultId", "acceleratedResultId", "continuityResultId",
        "semanticOutputSha256", "sameAcceptedOutput", "halo3AccelerationFactor", "personalFloorContinuity",
        "halo3RequiredForContinuity", "externalServiceCalls", "operationalCredentials", "authority", "claimBoundary",
    ], "WORKLOAD_COMPARISON_INVALID", "workload comparison")
    require(value["schema"] == "stc-mary-aperture-workload-comparison/1", "WORKLOAD_COMPARISON_INVALID", "comparison schema differs")
    require(value["feedId"] == baseline["feedId"] == accelerated["feedId"] == continuity["feedId"], "WORKLOAD_COMPARISON_BINDING_INVALID", "comparison feed binding differs")
    require(value["baselineResultId"] == baseline["resultId"] and value["acceleratedResultId"] == accelerated["resultId"] and value["continuityResultId"] == continuity["resultId"], "WORKLOAD_COMPARISON_BINDING_INVALID", "comparison result binding differs")
    require(value["semanticOutputSha256"] == baseline["semanticOutputSha256"] == accelerated["semanticOutputSha256"] == continuity["semanticOutputSha256"], "WORKLOAD_COMPARISON_OUTPUT_INVALID", "comparison semantic identity differs")
    require(value["sameAcceptedOutput"] is True and value["personalFloorContinuity"] is True and value["halo3RequiredForContinuity"] is False, "WORKLOAD_COMPARISON_INVALID", "comparison continuity claims differ")
    require(isinstance(value["halo3AccelerationFactor"], (int, float)) and value["halo3AccelerationFactor"] > 1.0, "WORKLOAD_COMPARISON_INVALID", "comparison does not prove acceleration")
    require(value["externalServiceCalls"] == 0 and value["operationalCredentials"] == 0 and value["authority"] == "none", "WORKLOAD_COMPARISON_INVALID", "comparison widens service, credential, or authority surface")
    assert_identity(value, "comparisonId", "stcmaryapertureworkloadcomparison1", "WORKLOAD_COMPARISON_ID_INVALID")
    return value


def validate_plan_gate(value: Any) -> Mapping[str, Any]:
    exact_keys(value, ["name", "status", "evidence", "wakeCondition", "gateId"], "FLIGHT_PLAN_GATE_INVALID", "flight plan gate")
    require(value["name"] in {"admitted_checkout", "personal_floor", "halo3", "post_halo3_continuity", "lattice_absence", "two_cell_partition", "successor_head", "private_evidence_root"}, "FLIGHT_PLAN_GATE_INVALID", "flight plan gate name differs")
    require(value["status"] in {"READY", "HOLD", "REFUSE"}, "FLIGHT_PLAN_GATE_INVALID", "flight plan gate status differs")
    require(isinstance(value["evidence"], list) and len(value["evidence"]) == len(set(value["evidence"])), "FLIGHT_PLAN_GATE_INVALID", "flight plan gate evidence differs")
    for identity in value["evidence"]:
        assert_content_id(identity, "FLIGHT_PLAN_GATE_INVALID", "flight plan gate evidence identity")
    require(value["wakeCondition"] is None or isinstance(value["wakeCondition"], str), "FLIGHT_PLAN_GATE_INVALID", "flight plan gate wake condition differs")
    assert_identity(value, "gateId", "stcmarylocalflightgate1", "FLIGHT_PLAN_GATE_ID_INVALID")
    return value


def validate_flight_plan(value: Any, bindings: Mapping[str, str], campaign_label: str) -> Mapping[str, Any]:
    exact_keys(value, [
        "schema", "planId", "profileId", "campaignLabel", "requiredCommit", "readinessId", "feedId",
        "baselineResultId", "acceleratedResultId", "continuityResultId", "twoCellVerificationId",
        "successorVerificationId", "gates", "stagePlan", "readyGateCount", "holdGateCount", "refuseGateCount",
        "flightExecuted", "physicalEstateQualified", "representativeOperatorQualified", "fieldNetworkQualified",
        "operationalC2Qualified", "productionLatticeQualified", "externalServiceCalls", "operationalCredentials",
        "authority", "claimBoundary",
    ], "FLIGHT_PLAN_INVALID", "flight plan")
    require(value["schema"] == "stc-mary-local-flight-plan/1" and value["profileId"] == TOOLCHAIN_PROFILE_ID, "FLIGHT_PLAN_INVALID", "flight plan schema or profile differs")
    require(value["campaignLabel"] == campaign_label and value["requiredCommit"] == REQUIRED_COMMIT, "FLIGHT_PLAN_BINDING_INVALID", "flight plan campaign or commit differs")
    for key in ("readinessId", "feedId", "baselineResultId", "acceleratedResultId", "continuityResultId", "twoCellVerificationId", "successorVerificationId"):
        require(value[key] == bindings[key], "FLIGHT_PLAN_BINDING_INVALID", f"flight plan {key} differs")
    require(isinstance(value["gates"], list) and len(value["gates"]) == 8, "FLIGHT_PLAN_INVALID", "flight plan gate denominator differs")
    gates = [validate_plan_gate(row) for row in value["gates"]]
    expected_names = ["admitted_checkout", "personal_floor", "halo3", "post_halo3_continuity", "lattice_absence", "two_cell_partition", "successor_head", "private_evidence_root"]
    require([row["name"] for row in gates] == expected_names, "FLIGHT_PLAN_INVALID", "flight plan gate order differs")
    ready = sum(1 for row in gates if row["status"] == "READY")
    hold = sum(1 for row in gates if row["status"] == "HOLD")
    refuse_count = sum(1 for row in gates if row["status"] == "REFUSE")
    require((value["readyGateCount"], value["holdGateCount"], value["refuseGateCount"]) == (ready, hold, refuse_count), "FLIGHT_PLAN_INVALID", "flight plan gate counts differ")
    require(isinstance(value["stagePlan"], list) and len(value["stagePlan"]) == 16, "FLIGHT_PLAN_INVALID", "flight plan stage denominator differs")
    require(value["flightExecuted"] is False, "FLIGHT_PLAN_CLAIM_INVALID", "flight plan claims execution")
    for key in ("physicalEstateQualified", "representativeOperatorQualified", "fieldNetworkQualified", "operationalC2Qualified", "productionLatticeQualified"):
        require(value[key] is False, "FLIGHT_PLAN_CLAIM_INVALID", f"flight plan widens {key}")
    require(value["externalServiceCalls"] == 0 and value["operationalCredentials"] == 0 and value["authority"] == "none", "FLIGHT_PLAN_CLAIM_INVALID", "flight plan widens service, credential, or authority surface")
    assert_identity(value, "planId", "stcmarylocalflightplan1", "FLIGHT_PLAN_ID_INVALID")
    return value


def validate_flight_config(value: Any, campaign_label: str) -> Mapping[str, Any]:
    exact_keys(value, ["schema", "campaignLabel", "sourceObjectDigests", "identityClasses", "canonicalMissionStateDigest", "authority", "claimBoundary"], "FLIGHT_CONFIG_INVALID", "flight configuration")
    require(value["schema"] == "stc-mary-private-flight-packet-config/1" and value["campaignLabel"] == campaign_label, "FLIGHT_CONFIG_INVALID", "flight configuration schema or campaign differs")
    require(isinstance(value["sourceObjectDigests"], list) and value["sourceObjectDigests"] and len(value["sourceObjectDigests"]) == len(set(value["sourceObjectDigests"])), "FLIGHT_CONFIG_INVALID", "source object digest denominator differs")
    for digest in value["sourceObjectDigests"]:
        assert_sha256(digest, "FLIGHT_CONFIG_INVALID", "source object digest")
    exact_keys(value["identityClasses"], ["personalFloor", "halo3", "initialHead", "successorHead", "graceBind", "lattice", "leftCell", "rightCell"], "FLIGHT_CONFIG_INVALID", "identity classes")
    for label, identity in value["identityClasses"].items():
        bounded_string(identity, "FLIGHT_CONFIG_INVALID", f"identity class {label}", 256)
        require(not identity.startswith("REPLACE_WITH_"), "FLIGHT_CONFIG_PLACEHOLDER_HELD", f"identity class {label} remains a placeholder")
    assert_sha256(value["canonicalMissionStateDigest"], "FLIGHT_CONFIG_INVALID", "canonical mission-state digest")
    require(value["authority"] == "none", "FLIGHT_CONFIG_INVALID", "flight configuration grants authority")
    return value


def node_packet_status(ws: Workstation) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    packet = ws.path("packet")
    script = Path(ws.config["executionSource"]["repositoryPath"]) / "mating_surface" / "anchor_node" / "stc_mary_private_flight_packet.mjs"
    require(script.is_file() and not script.is_symlink(), "PACKET_RUNTIME_MISSING", "admitted packet runtime is absent")
    result = run_command(["node", str(script), "status", str(packet)], cwd=script.parent, timeout=60.0)
    require(result.returncode == 0, "PACKET_STATUS_REFUSED", f"admitted packet status refused with exit {result.returncode}: {result.stderr.decode('utf-8', errors='replace')[:512]}")
    try:
        status = json.loads(result.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ConductorError("PACKET_STATUS_INVALID", f"packet status is not valid JSON: {error}") from error
    state = read_json(ws.path("packetState"))
    exact_keys(status, ["schema", "packetId", "campaignLabel", "configurationState", "completedStageCount", "stageCount", "nextStage", "sealed", "sealedDispositionId", "authority"], "PACKET_STATUS_INVALID", "packet status")
    require(status["schema"] == "stc-mary-private-flight-packet-status/1" and status["campaignLabel"] == ws.config["campaignLabel"], "PACKET_STATUS_INVALID", "packet status schema or campaign differs")
    require(status["authority"] == "none", "PACKET_STATUS_INVALID", "packet status grants authority")
    exact_keys(state, [
        "schema", "stateId", "packetId", "campaignLabel", "packetProfileId", "physicalProfileId", "configurationState",
        "stageDenominator", "stages", "completedStageCount", "nextStage", "sealed", "sealedDispositionId", "authority", "claimBoundary",
    ], "PACKET_STATE_INVALID", "packet state")
    require(state["schema"] == "stc-mary-private-flight-packet-state/1" and state["campaignLabel"] == ws.config["campaignLabel"], "PACKET_STATE_INVALID", "packet state schema or campaign differs")
    require(state["packetId"] == status["packetId"] and state["configurationState"] == status["configurationState"] and state["completedStageCount"] == status["completedStageCount"] and state["nextStage"] == status["nextStage"] and state["sealed"] == status["sealed"], "PACKET_STATE_INVALID", "packet status and state differ")
    require(state["authority"] == "none", "PACKET_STATE_INVALID", "packet state grants authority")
    assert_identity(state, "stateId", "stcmaryprivateflightpacketstate1", "PACKET_STATE_ID_INVALID")
    return status, state


def node_verify_sealed(ws: Workstation) -> Mapping[str, Any]:
    sealed = ws.path("sealed")
    script = Path(ws.config["executionSource"]["repositoryPath"]) / "mating_surface" / "anchor_node" / "stc_mary_private_flight_packet.mjs"
    require(script.is_file() and not script.is_symlink(), "PACKET_RUNTIME_MISSING", "admitted packet runtime is absent")
    result = run_command(["node", str(script), "verify-sealed", str(sealed)], cwd=script.parent, timeout=120.0)
    require(result.returncode == 0, "SEALED_VERIFICATION_REFUSED", f"admitted sealed-package verifier refused with exit {result.returncode}: {result.stderr.decode('utf-8', errors='replace')[:512]}")
    try:
        verification = json.loads(result.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ConductorError("SEALED_VERIFICATION_INVALID", f"sealed verification is not valid JSON: {error}") from error
    require(isinstance(verification, Mapping), "SEALED_VERIFICATION_INVALID", "sealed verification must be an object")
    require(verification.get("schema") == "stc-mary-private-flight-sealed-verification/1" and verification.get("status") == "PASS", "SEALED_VERIFICATION_INVALID", "sealed verification schema or status differs")
    require(verification.get("authority") == "none", "SEALED_VERIFICATION_INVALID", "sealed verification grants authority")
    assert_content_id(verification.get("verificationId"), "SEALED_VERIFICATION_INVALID", "sealed verification ID")
    return verification


def validate_public_disposition(value: Any, campaign_label: str) -> Mapping[str, Any]:
    require(isinstance(value, Mapping), "PUBLIC_DISPOSITION_INVALID", "public disposition must be an object")
    require(value.get("campaignLabel") == campaign_label, "PUBLIC_DISPOSITION_BINDING_INVALID", "public disposition names another campaign")
    require(value.get("authority") == "none", "PUBLIC_DISPOSITION_INVALID", "public disposition grants authority")
    require(value.get("externalServiceCalls") == 0 and value.get("operationalCredentials") == 0, "PUBLIC_DISPOSITION_INVALID", "public disposition widens service or credential surface")
    for key in (
        "physicalEstateQualified", "representativeOperatorQualified", "fieldNetworkQualified", "operationalC2Qualified",
        "productionLatticeQualified", "missionAuthorityGranted", "commandAuthorityGranted",
    ):
        if key in value:
            require(value[key] is False, "PUBLIC_DISPOSITION_CLAIM_WIDENED", f"public disposition widens {key}")
    disposition_id = value.get("dispositionId")
    assert_content_id(disposition_id, "PUBLIC_DISPOSITION_INVALID", "public disposition ID")
    serialized = canonical_json(value)
    forbidden = ["privatePath", "hostname", "endpoint", "credential", "stdout", "stderr", "evidenceFilename", "evidenceBody"]
    for token in forbidden:
        require(token.lower() not in serialized.lower(), "PUBLIC_DISPOSITION_PRIVATE_MATERIAL", f"public disposition contains forbidden surface: {token}")
    return value


def phase_admitted_checkout(ws: Workstation, _: Mapping[str, PhaseResult], __: Mapping[str, Callable[..., Any]]) -> PhaseResult:
    try:
        repository = Path(ws.config["executionSource"]["repositoryPath"]).resolve()
        snapshot = git_snapshot(repository)
        validate_source_snapshot(snapshot, repository)
        actual_source_set = source_set_receipt()
        require(actual_source_set["sourceSetId"] == ws.source_set["sourceSetId"], "CONDUCTOR_SOURCE_SET_DRIFT", "conductor source bytes differ from campaign initialization")
        return closed("admitted_checkout", [snapshot["sourceReceiptId"], actual_source_set["sourceSetId"]])
    except Exception as error:
        return refused("admitted_checkout", error)


def phase_artifact_coordinates(ws: Workstation, _: Mapping[str, PhaseResult], __: Mapping[str, Callable[..., Any]]) -> PhaseResult:
    evidence: list[str] = []
    try:
        paths: list[Path] = []
        for row in ws.config["artifacts"]:
            validate_artifact_coordinate(row)
            path = Path(row["privatePath"]).resolve()
            require(path.exists() and not path.is_symlink(), "ARTIFACT_COORDINATE_MISSING", f"artifact coordinate is absent or symlinked: {row['label']}")
            require((row["kind"] == "file" and path.is_file()) or (row["kind"] == "directory" and path.is_dir()), "ARTIFACT_COORDINATE_TYPE_DRIFT", f"artifact coordinate type changed: {row['label']}")
            for other in paths:
                require(not paths_overlap(path, other), "ARTIFACT_COORDINATE_OVERLAP", "artifact coordinates overlap")
            require(not paths_overlap(path, ws.root), "ARTIFACT_WORKSPACE_OVERLAP", f"artifact overlaps workstation: {row['label']}")
            paths.append(path)
            evidence.append(row["coordinateId"])
        return closed("artifact_coordinates", evidence)
    except Exception as error:
        return refused("artifact_coordinates", error, evidence)


def phase_readiness(ws: Workstation, prior: Mapping[str, PhaseResult], __: Mapping[str, Callable[..., Any]]) -> PhaseResult:
    path = ws.path("readiness")
    try:
        value = optional_json(path)
        if value is None:
            return held("readiness", code="READINESS_RECEIPT_ABSENT", reason="readiness-private receipt is absent")
        receipt = validate_readiness_receipt(value, ws)
        evidence = [receipt["readinessId"]]
        if prior["admitted_checkout"].state != "CLOSED" or prior["artifact_coordinates"].state != "CLOSED":
            return held("readiness", evidence, "PREDECESSOR_HELD", "source checkout or artifact coordinates are not closed")
        if not cuda_device_observed(receipt, ws.config["selectedCudaDeviceIndex"]):
            return held("readiness", evidence, "SELECTED_CUDA_DEVICE_NOT_OBSERVED", "readiness did not observe the selected CUDA device index")
        return closed("readiness", evidence)
    except Exception as error:
        return refused("readiness", error)


def phase_feed(ws: Workstation, prior: Mapping[str, PhaseResult], validators: Mapping[str, Callable[..., Any]]) -> PhaseResult:
    path = ws.path("feedManifest")
    try:
        value = optional_json(path)
        if value is None:
            return held("feed", code="FEED_RECEIPT_ABSENT", reason="feed manifest is absent")
        validators["feed"](value, ws.path("feed"))
        require(value["seed"] == 20260827 and value["recordCount"] == 262144 and value["featureCount"] == 32 and value["classCount"] == 8, "FEED_COORDINATE_MISMATCH", "feed dimensions or seed differ from the frozen campaign")
        evidence = [value["feedId"]]
        if prior["readiness"].state != "CLOSED":
            return held("feed", evidence, "PREDECESSOR_HELD", "readiness phase is not closed")
        return closed("feed", evidence, {"feedId": value["feedId"]})
    except Exception as error:
        return refused("feed", error)


def load_workload_pair(ws: Workstation, result_key: str, verification_key: str, validators: Mapping[str, Callable[..., Any]]) -> tuple[Mapping[str, Any], Mapping[str, Any]] | None:
    result_value = optional_json(ws.path(result_key))
    verification_value = optional_json(ws.path(verification_key))
    if result_value is None and verification_value is None:
        return None
    require(result_value is not None and verification_value is not None, "WORKLOAD_PAIR_INCOMPLETE", "workload result and verification must both be present")
    validators["workload"](result_value)
    feed_manifest = read_json(ws.path("feedManifest"))
    validate_workload_verification(verification_value, result_value, feed_manifest["feedId"])
    require(result_value["feedId"] == feed_manifest["feedId"], "WORKLOAD_FEED_BINDING_INVALID", "workload result belongs to another feed")
    return result_value, verification_value


def phase_personal_floor(ws: Workstation, prior: Mapping[str, PhaseResult], validators: Mapping[str, Callable[..., Any]]) -> PhaseResult:
    try:
        pair = load_workload_pair(ws, "baseline", "baselineVerification", validators)
        if pair is None:
            return held("personal_floor", code="PERSONAL_FLOOR_RECEIPTS_ABSENT", reason="baseline result and verification are absent")
        result, verification = pair
        require(result["backend"] != "torch-cuda" and result["deviceClass"].startswith("resident_cpu"), "PERSONAL_FLOOR_BACKEND_INVALID", "baseline is not a resident CPU result")
        evidence = [result["resultId"], verification["verificationId"]]
        if prior["feed"].state != "CLOSED":
            return held("personal_floor", evidence, "PREDECESSOR_HELD", "feed phase is not closed")
        return closed("personal_floor", evidence, {"resultId": result["resultId"], "verificationId": verification["verificationId"], "semanticOutputSha256": result["semanticOutputSha256"], "classificationStreamSha256": result["classificationStreamSha256"], "throughput": result["throughputRecordsPerSecond"]})
    except Exception as error:
        return refused("personal_floor", error)


def phase_halo3(ws: Workstation, prior: Mapping[str, PhaseResult], validators: Mapping[str, Callable[..., Any]]) -> PhaseResult:
    try:
        pair = load_workload_pair(ws, "accelerated", "acceleratedVerification", validators)
        if pair is None:
            return held("halo3", code="HALO3_RECEIPTS_ABSENT", reason="HALO3 result and verification are absent")
        result, verification = pair
        baseline = read_json(ws.path("baseline"))
        require(result["backend"] == "torch-cuda" and result["deviceClass"] == f"cuda_accelerator:{ws.config['selectedCudaDeviceIndex']}", "HALO3_DEVICE_INVALID", "HALO3 result names another backend or device")
        require(result["semanticOutputSha256"] == baseline["semanticOutputSha256"] and result["classificationStreamSha256"] == baseline["classificationStreamSha256"], "HALO3_OUTPUT_MISMATCH", "HALO3 changed the accepted output")
        require(result["throughputRecordsPerSecond"] > baseline["throughputRecordsPerSecond"], "HALO3_ACCELERATION_NOT_PROVEN", "HALO3 did not exceed baseline throughput")
        evidence = [result["resultId"], verification["verificationId"]]
        if prior["personal_floor"].state != "CLOSED":
            return held("halo3", evidence, "PREDECESSOR_HELD", "personal-floor phase is not closed")
        return closed("halo3", evidence, {"resultId": result["resultId"], "verificationId": verification["verificationId"], "throughput": result["throughputRecordsPerSecond"]})
    except Exception as error:
        return refused("halo3", error)


def phase_post_halo3(ws: Workstation, prior: Mapping[str, PhaseResult], validators: Mapping[str, Callable[..., Any]]) -> PhaseResult:
    try:
        pair = load_workload_pair(ws, "continuity", "continuityVerification", validators)
        comparison = optional_json(ws.path("comparison"))
        if pair is None and comparison is None:
            return held("post_halo3_continuity", code="CONTINUITY_RECEIPTS_ABSENT", reason="continuity result, verification, and comparison are absent")
        require(pair is not None and comparison is not None, "CONTINUITY_CHAIN_INCOMPLETE", "continuity result, verification, and comparison must all be present")
        continuity, verification = pair
        baseline = read_json(ws.path("baseline"))
        accelerated = read_json(ws.path("accelerated"))
        require(continuity["backend"] != "torch-cuda" and continuity["deviceClass"].startswith("resident_cpu"), "CONTINUITY_BACKEND_INVALID", "continuity result is not resident CPU work")
        require(continuity["semanticOutputSha256"] == baseline["semanticOutputSha256"] and continuity["classificationStreamSha256"] == baseline["classificationStreamSha256"], "CONTINUITY_OUTPUT_MISMATCH", "continuity changed the accepted output")
        validate_comparison(comparison, baseline, accelerated, continuity)
        evidence = [continuity["resultId"], verification["verificationId"], comparison["comparisonId"]]
        if prior["halo3"].state != "CLOSED":
            return held("post_halo3_continuity", evidence, "PREDECESSOR_HELD", "HALO3 phase is not closed")
        return closed("post_halo3_continuity", evidence, {"resultId": continuity["resultId"], "verificationId": verification["verificationId"], "comparisonId": comparison["comparisonId"]})
    except Exception as error:
        return refused("post_halo3_continuity", error)


def phase_two_cell(ws: Workstation, prior: Mapping[str, PhaseResult], validators: Mapping[str, Callable[..., Any]]) -> PhaseResult:
    try:
        value = optional_json(ws.path("twoCellVerification"))
        if value is None:
            return held("two_cell_partition", code="TWO_CELL_RECEIPT_ABSENT", reason="two-cell verification is absent")
        validators["two_cell"](value)
        evidence = [value["verificationId"]]
        if value["mode"] != "private_local_attested":
            return held("two_cell_partition", evidence, "TWO_CELL_SYNTHETIC_HELD", "synthetic two-cell verification cannot close a physical gate")
        require(value.get("reunionTerminal") == "HUMAN_REQUIRED" and value.get("automaticMergeAllowed") is False and value.get("branchesRetained") == 2 and value.get("distinctHostClasses") is True, "TWO_CELL_PHYSICAL_BOUNDARY_INVALID", "two-cell receipt does not preserve the required physical reunion boundary")
        if prior["post_halo3_continuity"].state != "CLOSED":
            return held("two_cell_partition", evidence, "PREDECESSOR_HELD", "post-HALO3 continuity phase is not closed")
        return closed("two_cell_partition", evidence, {"verificationId": value["verificationId"], "leftCellId": value["leftCellId"], "rightCellId": value["rightCellId"]})
    except Exception as error:
        return refused("two_cell_partition", error)


def phase_successor(ws: Workstation, prior: Mapping[str, PhaseResult], validators: Mapping[str, Callable[..., Any]]) -> PhaseResult:
    try:
        value = optional_json(ws.path("successorVerification"))
        if value is None:
            return held("successor_head", code="SUCCESSOR_RECEIPT_ABSENT", reason="successor verification is absent")
        validators["successor"](value)
        evidence = [value["verificationId"]]
        if value["mode"] != "private_local_attested":
            return held("successor_head", evidence, "SUCCESSOR_SYNTHETIC_HELD", "synthetic successor verification cannot close a physical gate")
        if prior["two_cell_partition"].state != "CLOSED":
            return held("successor_head", evidence, "PREDECESSOR_HELD", "two-cell partition phase is not closed")
        return closed("successor_head", evidence, {"verificationId": value["verificationId"], "successorId": value["successorId"]})
    except Exception as error:
        return refused("successor_head", error)


def phase_flight_plan(ws: Workstation, prior: Mapping[str, PhaseResult], _: Mapping[str, Callable[..., Any]]) -> PhaseResult:
    try:
        plan = optional_json(ws.path("flightPlan"))
        config = optional_json(ws.path("flightConfig"))
        if plan is None and config is None:
            return held("flight_plan", code="FLIGHT_PLAN_RECEIPTS_ABSENT", reason="flight plan and generated packet configuration are absent")
        require(plan is not None and config is not None, "FLIGHT_PLAN_CHAIN_INCOMPLETE", "flight plan and generated packet configuration must both be present")
        bindings = {
            "readinessId": prior["readiness"].detail.get("readinessId") if prior["readiness"].detail else read_json(ws.path("readiness"))["readinessId"],
            "feedId": prior["feed"].detail.get("feedId") if prior["feed"].detail else read_json(ws.path("feedManifest"))["feedId"],
            "baselineResultId": read_json(ws.path("baseline"))["resultId"],
            "acceleratedResultId": read_json(ws.path("accelerated"))["resultId"],
            "continuityResultId": read_json(ws.path("continuity"))["resultId"],
            "twoCellVerificationId": read_json(ws.path("twoCellVerification"))["verificationId"],
            "successorVerificationId": read_json(ws.path("successorVerification"))["verificationId"],
        }
        validate_flight_plan(plan, bindings, ws.config["campaignLabel"])
        validate_flight_config(config, ws.config["campaignLabel"])
        evidence = [plan["planId"], sha256_bytes(canonical_json(config).encode("utf-8"))]
        held_gates = [row for row in plan["gates"] if row["status"] == "HOLD"]
        refused_gates = [row for row in plan["gates"] if row["status"] == "REFUSE"]
        if refused_gates:
            raise ConductorError("FLIGHT_PLAN_GATE_REFUSED", f"flight plan gate refused: {refused_gates[0]['name']}")
        if held_gates:
            return held("flight_plan", evidence, "FLIGHT_PLAN_GATE_HELD", f"flight plan gate held: {held_gates[0]['name']}", {"gateWakeCondition": held_gates[0]["wakeCondition"]})
        require(plan["readyGateCount"] == 8 and plan["holdGateCount"] == 0 and plan["refuseGateCount"] == 0, "FLIGHT_PLAN_GATE_COUNTS_INVALID", "all eight gates are not ready")
        if prior["successor_head"].state != "CLOSED":
            return held("flight_plan", evidence, "PREDECESSOR_HELD", "successor phase is not closed")
        return closed("flight_plan", evidence, {"planId": plan["planId"], "configSha256": evidence[1]})
    except Exception as error:
        return refused("flight_plan", error)


def phase_private_packet(ws: Workstation, prior: Mapping[str, PhaseResult], _: Mapping[str, Callable[..., Any]]) -> PhaseResult:
    packet = ws.path("packet")
    if not packet.exists():
        return held("private_packet", code="PRIVATE_PACKET_ABSENT", reason="private packet root is absent", detail={"substate": "not_initialized"})
    try:
        require(packet.is_dir() and not packet.is_symlink(), "PRIVATE_PACKET_PATH_INVALID", "private packet root is not a regular directory")
        status, state = node_packet_status(ws)
        evidence = [status["packetId"], state["stateId"]]
        for row in state["stages"]:
            if row["status"] == "recorded":
                evidence.append(row["recordDigest"])
        if prior["flight_plan"].state != "CLOSED":
            return held("private_packet", evidence, "PACKET_HANDOFF_NOT_READY", "flight plan is not closed", {"substate": status["configurationState"], "nextStage": status["nextStage"], "completedStageCount": status["completedStageCount"]})
        if status["configurationState"] != "configured":
            return held("private_packet", evidence, "PRIVATE_PACKET_UNCONFIGURED", "private packet is initialized but not configured", {"substate": "unconfigured", "nextStage": status["nextStage"], "completedStageCount": status["completedStageCount"]})
        if status["nextStage"] is not None:
            return held("private_packet", evidence, "PRIVATE_PACKET_STAGE_PENDING", f"next admitted packet stage is {status['nextStage']}", {"substate": "recording", "nextStage": status["nextStage"], "completedStageCount": status["completedStageCount"]})
        require(status["completedStageCount"] == status["stageCount"] == 16, "PRIVATE_PACKET_DENOMINATOR_INVALID", "private packet stage denominator differs")
        return closed("private_packet", evidence, {"packetId": status["packetId"], "stateId": state["stateId"], "sealed": status["sealed"]})
    except Exception as error:
        return refused("private_packet", error)


def phase_sealed_flight(ws: Workstation, prior: Mapping[str, PhaseResult], _: Mapping[str, Callable[..., Any]]) -> PhaseResult:
    sealed = ws.path("sealed")
    if not sealed.exists():
        return held("sealed_flight", code="SEALED_PACKAGE_ABSENT", reason="sealed package is absent")
    try:
        require(sealed.is_dir() and not sealed.is_symlink(), "SEALED_PACKAGE_PATH_INVALID", "sealed package root is not a regular directory")
        verification = node_verify_sealed(ws)
        disposition = validate_public_disposition(read_json(ws.path("publicDisposition")), ws.config["campaignLabel"])
        require(verification["dispositionId"] == disposition["dispositionId"], "SEALED_DISPOSITION_BINDING_INVALID", "sealed verification names another public disposition")
        detached = optional_json(ws.path("detachedVerification"))
        if detached is not None:
            require(canonical_json(detached) == canonical_json(verification), "DETACHED_VERIFICATION_DRIFT", "stored detached verification differs from replay")
        evidence = [verification["verificationId"], disposition["dispositionId"]]
        if prior["private_packet"].state != "CLOSED":
            return held("sealed_flight", evidence, "PREDECESSOR_HELD", "private packet is not complete")
        return closed("sealed_flight", evidence, {"verificationId": verification["verificationId"], "dispositionId": disposition["dispositionId"]})
    except Exception as error:
        return refused("sealed_flight", error)


PHASE_EVALUATORS: Mapping[str, Callable[[Workstation, Mapping[str, PhaseResult], Mapping[str, Callable[..., Any]]], PhaseResult]] = {
    "admitted_checkout": phase_admitted_checkout,
    "artifact_coordinates": phase_artifact_coordinates,
    "readiness": phase_readiness,
    "feed": phase_feed,
    "personal_floor": phase_personal_floor,
    "halo3": phase_halo3,
    "post_halo3_continuity": phase_post_halo3,
    "two_cell_partition": phase_two_cell,
    "successor_head": phase_successor,
    "flight_plan": phase_flight_plan,
    "private_packet": phase_private_packet,
    "sealed_flight": phase_sealed_flight,
}


def phase_public_row(sequence: int, result: PhaseResult) -> dict[str, Any]:
    return {
        "sequence": sequence,
        "phase": result.phase,
        "state": result.state,
        "evidenceIdentities": result.evidence,
        "reasonCode": result.reason_code,
    }


def next_action_for(ws: Workstation, result: PhaseResult) -> tuple[str, str | None, str]:
    profile_row = ws.profile["phases"][result.phase]
    if result.state == "REFUSED":
        action = profile_row["repairAction"]
        wake = None
    elif result.state == "HOLD":
        action = profile_row["nextSafeAction"]
        wake = result.detail.get("gateWakeCondition") if result.detail and result.detail.get("gateWakeCondition") else profile_row["wakeCondition"]
    else:
        action = "Submit the body-free public disposition for a separate evidence-tier review; do not change any qualification claim automatically."
        wake = None
    control = profile_row["controlQuestion"]
    if result.phase == "private_packet" and result.state == "HOLD" and result.detail:
        next_stage = result.detail.get("nextStage")
        if next_stage:
            action = f"Perform the admitted packet instruction for {next_stage}, supply local evidence, answer its control question, and record only that stage."
            packet_profile_path = Path(ws.config["executionSource"]["repositoryPath"]) / "mating_surface" / "anchor_node" / "stc-mary-private-flight-packet-profile-01.json"
            try:
                packet_profile = read_json(packet_profile_path)
                if isinstance(packet_profile.get("stages"), Mapping) and next_stage in packet_profile["stages"]:
                    control = packet_profile["stages"][next_stage]["controlQuestion"]
            except ConductorError:
                pass
    return action, wake, control


def derive_status(root: str | Path, *, persist: bool = True) -> dict[str, Any]:
    ws = load_workstation(root)
    repository = Path(ws.config["executionSource"]["repositoryPath"]).resolve()
    try:
        validators = import_admitted_validators(repository)
    except ConductorError:
        validators = {}
    results: dict[str, PhaseResult] = {}
    for phase in PHASE_SEQUENCE:
        evaluator = PHASE_EVALUATORS[phase]
        if phase in {"feed", "personal_floor", "halo3", "post_halo3_continuity", "two_cell_partition", "successor_head"} and not validators:
            result = refused(phase, ConductorError("ADMITTED_VALIDATOR_IMPORT_FAILED", "admitted validators are unavailable from the exact execution checkout"))
        else:
            result = evaluator(ws, results, validators)
        results[phase] = result
    current = next((results[name] for name in PHASE_SEQUENCE if results[name].state != "CLOSED"), results["sealed_flight"])
    action, wake, control = next_action_for(ws, current)
    rows = [phase_public_row(index, results[phase]) for index, phase in enumerate(PHASE_SEQUENCE, start=1)]
    closed_count = sum(1 for row in results.values() if row.state == "CLOSED")
    held_count = sum(1 for row in results.values() if row.state == "HOLD")
    refused_count = sum(1 for row in results.values() if row.state == "REFUSED")
    body = {
        "schema": "stc-mary-flight-conductor-ledger/1",
        "profileId": PROFILE_ID,
        "campaignId": ws.marker["campaignId"],
        "sourceCommit": REQUIRED_COMMIT,
        "sourceTree": REQUIRED_TREE,
        "currentPhase": current.phase,
        "currentPhaseState": current.state,
        "closedPhaseCount": closed_count,
        "heldPhaseCount": held_count,
        "refusedPhaseCount": refused_count,
        "phaseDenominator": list(PHASE_SEQUENCE),
        "phases": rows,
        "supportingReceiptIdentities": current.evidence,
        "nextSafeAction": action,
        "wakeCondition": wake,
        "operatorControlQuestion": control,
        "packetHandoffReady": results["flight_plan"].state == "CLOSED",
        "privateFlightCompleted": results["sealed_flight"].state == "CLOSED",
        "physicalEstateQualified": False,
        "representativeOperatorQualified": False,
        "fieldNetworkQualified": False,
        "operationalC2Qualified": False,
        "productionLatticeQualified": False,
        "missionAuthority": "none",
        "commandAuthority": "none",
        "targetingEngagementEffectorWeaponsCapability": False,
        "networkRequired": False,
        "externalServiceCalls": 0,
        "operationalCredentials": 0,
        "privateEvidenceBodiesCommittedToPublicGit": 0,
        "authority": "none",
        "claimBoundary": CLAIM_BOUNDARY,
    }
    ledger = {**body, "ledgerId": content_id("stcmaryflightconductorledger1", body)}
    if persist:
        write_json(ws.root / LEDGER_FILE, ledger, replace=(ws.root / LEDGER_FILE).exists())
    return ledger


def packet_handoff_record(ws: Workstation, ledger: Mapping[str, Any]) -> dict[str, Any]:
    require(ledger["packetHandoffReady"] is True, "PACKET_HANDOFF_HELD", "packet handoff remains held while any plan gate is not ready")
    plan = read_json(ws.path("flightPlan"))
    config_bytes = read_bytes(ws.path("flightConfig"))
    body = {
        "schema": "stc-mary-flight-conductor-packet-handoff/1",
        "campaignId": ws.marker["campaignId"],
        "planId": plan["planId"],
        "flightConfigSha256": sha256_bytes(config_bytes),
        "packetRoot": str(ws.path("packet")),
        "packetRunner": str(Path(ws.config["executionSource"]["repositoryPath"]) / "mating_surface" / "anchor_node" / "stc-mary-private-flight.ps1"),
        "campaignLabel": ws.config["campaignLabel"],
        "namedHumanReviewRequired": True,
        "automaticStageRecordingAllowed": False,
        "authority": "none",
        "claimBoundary": "Private packet handoff coordinate. It authorizes no stage, evidence claim, physical action, or command decision.",
    }
    return {**body, "handoffId": content_id("stcmaryflightconductorpackethandoff1", body)}


def render_handoff_script(handoff: Mapping[str, Any], flight_config: Path) -> str:
    return "\n".join([
        "$ErrorActionPreference = 'Stop'",
        f"$PacketRunner = {ps_quote(handoff['packetRunner'])}",
        f"$Packet = {ps_quote(handoff['packetRoot'])}",
        f"$Campaign = {ps_quote(handoff['campaignLabel'])}",
        f"$FlightConfig = {ps_quote(str(flight_config))}",
        "",
        "# Named-human control: review every identity class and confirm that no REPLACE_WITH_ value remains.",
        "& $PacketRunner init $Packet $Campaign",
        "& $PacketRunner configure $Packet $FlightConfig",
        "& $PacketRunner status $Packet",
        "",
        "# Continue one admitted stage at a time. This handoff does not record any stage.",
        "",
    ])


def render_workstation(root: str | Path) -> dict[str, Any]:
    ws = load_workstation(root)
    ledger = derive_status(ws.root, persist=True)
    lines = [
        "# STC MARY private flight conductor",
        "",
        f"Campaign identity: `{ledger['campaignId']}`",
        f"Current phase: `{ledger['currentPhase']}`",
        f"State: `{ledger['currentPhaseState']}`",
        f"Closed / held / refused: `{ledger['closedPhaseCount']} / {ledger['heldPhaseCount']} / {ledger['refusedPhaseCount']}`",
        "",
        "## Supporting receipt identities",
        "",
    ]
    if ledger["supportingReceiptIdentities"]:
        lines.extend(f"- `{identity}`" for identity in ledger["supportingReceiptIdentities"])
    else:
        lines.append("- none")
    lines.extend([
        "",
        "## One next safe action",
        "",
        ledger["nextSafeAction"],
        "",
    ])
    if ledger["wakeCondition"] is not None:
        lines.extend(["## Wake condition", "", ledger["wakeCondition"], ""])
    lines.extend(["## Operator control question", "", ledger["operatorControlQuestion"], "", "Authority: `none`", "", CLAIM_BOUNDARY, ""])
    write_text(ws.root / NEXT_ACTION_FILE, "\n".join(lines), replace=(ws.root / NEXT_ACTION_FILE).exists())
    handoff_id = None
    if ledger["packetHandoffReady"]:
        handoff = packet_handoff_record(ws, ledger)
        handoff_path = ws.root / HANDOFF_FILE
        if handoff_path.exists():
            require(canonical_json(read_json(handoff_path)) == canonical_json(handoff), "PACKET_HANDOFF_DRIFT", "existing packet handoff differs from receipt-derived handoff")
        else:
            write_json(handoff_path, handoff)
        script = render_handoff_script(handoff, ws.path("flightConfig"))
        write_text(ws.root / HANDOFF_SCRIPT_FILE, script, replace=(ws.root / HANDOFF_SCRIPT_FILE).exists())
        handoff_id = handoff["handoffId"]
    return {"status": "RENDERED", "ledgerId": ledger["ledgerId"], "currentPhase": ledger["currentPhase"], "handoffId": handoff_id, "authority": "none"}


def public_projection(ws: Workstation, ledger: Mapping[str, Any]) -> dict[str, Any]:
    sealed_row = next(row for row in ledger["phases"] if row["phase"] == "sealed_flight")
    body = {
        "schema": "stc-mary-flight-conductor-public-projection/1",
        "profileId": PROFILE_ID,
        "campaignId": ledger["campaignId"],
        "sourceCommit": ledger["sourceCommit"],
        "sourceTree": ledger["sourceTree"],
        "currentPhase": ledger["currentPhase"],
        "currentPhaseState": ledger["currentPhaseState"],
        "closedPhaseCount": ledger["closedPhaseCount"],
        "heldPhaseCount": ledger["heldPhaseCount"],
        "refusedPhaseCount": ledger["refusedPhaseCount"],
        "phaseStates": [{"phase": row["phase"], "state": row["state"], "evidenceIdentities": row["evidenceIdentities"]} for row in ledger["phases"]],
        "sealedEvidenceIdentities": sealed_row["evidenceIdentities"],
        "privateFlightCompleted": ledger["privateFlightCompleted"],
        "publicEvidenceBodyCount": 0,
        "physicalEstateQualified": False,
        "representativeOperatorQualified": False,
        "fieldNetworkQualified": False,
        "operationalC2Qualified": False,
        "productionLatticeQualified": False,
        "missionAuthority": "none",
        "commandAuthority": "none",
        "targetingEngagementEffectorWeaponsCapability": False,
        "networkRequired": False,
        "externalServiceCalls": 0,
        "operationalCredentials": 0,
        "privateEvidenceBodiesCommittedToPublicGit": 0,
        "authority": "none",
        "claimBoundary": "Body-free conductor projection. It reports content identities, phase states, and claim boundaries only and grants no qualification or authority.",
    }
    projection = {**body, "projectionId": content_id("stcmaryflightconductorpublicprojection1", body)}
    validate_public_projection(projection, ws)
    return projection


def validate_public_projection(value: Any, ws: Workstation) -> Mapping[str, Any]:
    exact_keys(value, [
        "schema", "projectionId", "profileId", "campaignId", "sourceCommit", "sourceTree", "currentPhase",
        "currentPhaseState", "closedPhaseCount", "heldPhaseCount", "refusedPhaseCount", "phaseStates",
        "sealedEvidenceIdentities", "privateFlightCompleted", "publicEvidenceBodyCount", "physicalEstateQualified",
        "representativeOperatorQualified", "fieldNetworkQualified", "operationalC2Qualified", "productionLatticeQualified",
        "missionAuthority", "commandAuthority", "targetingEngagementEffectorWeaponsCapability", "networkRequired",
        "externalServiceCalls", "operationalCredentials", "privateEvidenceBodiesCommittedToPublicGit", "authority", "claimBoundary",
    ], "PUBLIC_PROJECTION_INVALID", "public projection")
    require(value["schema"] == "stc-mary-flight-conductor-public-projection/1" and value["profileId"] == PROFILE_ID and value["campaignId"] == ws.marker["campaignId"], "PUBLIC_PROJECTION_INVALID", "public projection identity differs")
    require(value["authority"] == "none" and value["missionAuthority"] == "none" and value["commandAuthority"] == "none", "PUBLIC_PROJECTION_INVALID", "public projection grants authority")
    for key in ("physicalEstateQualified", "representativeOperatorQualified", "fieldNetworkQualified", "operationalC2Qualified", "productionLatticeQualified", "targetingEngagementEffectorWeaponsCapability", "networkRequired"):
        require(value[key] is False, "PUBLIC_PROJECTION_INVALID", f"public projection widens {key}")
    require(value["externalServiceCalls"] == 0 and value["operationalCredentials"] == 0 and value["publicEvidenceBodyCount"] == 0 and value["privateEvidenceBodiesCommittedToPublicGit"] == 0, "PUBLIC_PROJECTION_INVALID", "public projection widens service, credential, or body surface")
    assert_identity(value, "projectionId", "stcmaryflightconductorpublicprojection1", "PUBLIC_PROJECTION_ID_INVALID")
    serialized = canonical_json(value)
    secrets = [
        ws.config["executionSource"]["repositoryPath"],
        ws.config["privateParent"],
        str(ws.root),
        *[row["privatePath"] for row in ws.config["artifacts"]],
    ]
    for secret in secrets:
        require(secret not in serialized and secret.replace("\\", "/") not in serialized, "PUBLIC_PROJECTION_PRIVATE_PATH", "public projection contains a private path")
    forbidden_keys = {"path", "privatePath", "repositoryPath", "host", "hostname", "endpoint", "credential", "credentials", "environment", "stdout", "stderr", "command", "commands", "evidenceBody", "evidenceBodies", "evidenceFilename"}
    def walk(node: Any) -> None:
        if isinstance(node, Mapping):
            for key, child in node.items():
                require(key not in forbidden_keys, "PUBLIC_PROJECTION_FORBIDDEN_FIELD", f"public projection contains forbidden field: {key}")
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)
        elif isinstance(node, str):
            require(re.search(r"(?:[A-Za-z]:[\\/]|\\\\[^\\]+\\|/(?:home|Users|mnt|tmp|var|opt|srv|root)/)", node) is None, "PUBLIC_PROJECTION_PATH_SHAPE", "public projection contains an absolute path shape")
            require("://" not in node, "PUBLIC_PROJECTION_ENDPOINT_SHAPE", "public projection contains an endpoint shape")
    walk(value)
    return value


def write_public_projection(root: str | Path, ledger: Mapping[str, Any] | None = None, output: Path | None = None, *, replace: bool = True) -> dict[str, Any]:
    ws = load_workstation(root)
    ledger = ledger or derive_status(ws.root, persist=True)
    projection = public_projection(ws, ledger)
    destination = output or ws.root / PUBLIC_PROJECTION_FILE
    write_json(destination, projection, replace=replace and destination.exists())
    return projection


def verify_workstation(root: str | Path) -> dict[str, Any]:
    ws = load_workstation(root)
    recomputed = derive_status(ws.root, persist=False)
    ledger_path = ws.root / LEDGER_FILE
    if ledger_path.exists():
        require(canonical_json(read_json(ledger_path)) == canonical_json(recomputed), "PROGRESS_LEDGER_DRIFT", "persisted progress ledger differs from receipt-derived reconstruction")
    projection_path = ws.root / PUBLIC_PROJECTION_FILE
    if projection_path.exists():
        expected_projection = public_projection(ws, recomputed)
        require(canonical_json(read_json(projection_path)) == canonical_json(expected_projection), "PUBLIC_PROJECTION_DRIFT", "persisted public projection differs from receipt-derived projection")
    handoff_path = ws.root / HANDOFF_FILE
    if handoff_path.exists():
        require(recomputed["packetHandoffReady"] is True, "PACKET_HANDOFF_PREMATURE", "packet handoff exists while a plan gate is held")
        require(canonical_json(read_json(handoff_path)) == canonical_json(packet_handoff_record(ws, recomputed)), "PACKET_HANDOFF_DRIFT", "packet handoff differs from receipt-derived handoff")
    require(recomputed["authority"] == "none" and recomputed["missionAuthority"] == "none" and recomputed["commandAuthority"] == "none", "WORKSTATION_AUTHORITY_WIDENED", "workstation grants authority")
    require(recomputed["refusedPhaseCount"] == 0, "WORKSTATION_PHASE_REFUSED", f"workstation contains {recomputed['refusedPhaseCount']} refused phase(s)")
    return {"status": "PASS", "campaignId": ws.marker["campaignId"], "ledgerId": recomputed["ledgerId"], "currentPhase": recomputed["currentPhase"], "closedPhases": recomputed["closedPhaseCount"], "heldPhases": recomputed["heldPhaseCount"], "authority": "none"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="STC MARY source-pinned private flight conductor")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate-profile", help="validate the frozen conductor profile")
    validate.add_argument("profile", nargs="?", default=str(DEFAULT_PROFILE))
    init = sub.add_parser("init", help="initialize one immutable private campaign workstation")
    init.add_argument("--repository", required=True)
    init.add_argument("--private-parent", required=True)
    init.add_argument("--out", required=True)
    init.add_argument("--campaign-label", required=True)
    init.add_argument("--cuda-device-index", type=int, required=True)
    init.add_argument("--artifact", action="append", default=[], required=True)
    init.add_argument("--profile", default=str(DEFAULT_PROFILE))
    for name in ("status", "render", "verify", "public-projection"):
        command = sub.add_parser(name)
        command.add_argument("--workstation", required=True)
        if name == "public-projection":
            command.add_argument("--out")
    return parser


def run_cli(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate-profile":
            profile = load_profile(Path(args.profile))
            output = {"status": "PASS", "profileId": profile["profileId"], "requiredCommit": profile["requiredCommit"], "requiredTree": profile["requiredTree"], "phaseCount": len(profile["phaseSequence"]), "authority": "none"}
        elif args.command == "init":
            output = initialize_workstation(args)
        elif args.command == "status":
            output = derive_status(args.workstation, persist=True)
        elif args.command == "render":
            output = render_workstation(args.workstation)
        elif args.command == "verify":
            output = verify_workstation(args.workstation)
        elif args.command == "public-projection":
            destination = Path(args.out).expanduser().resolve() if args.out else None
            output = write_public_projection(args.workstation, output=destination, replace=True)
        else:
            raise ConductorError("COMMAND_INVALID", "command differs")
        sys.stdout.write(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
        return 0
    except ConductorError as error:
        sys.stderr.write(json.dumps({"status": "REFUSED", "code": error.code, "message": str(error), "authority": "none"}, indent=2) + "\n")
        return 2
    except Exception as error:
        sys.stderr.write(json.dumps({"status": "REFUSED", "code": type(error).__name__, "message": str(error), "authority": "none"}, indent=2) + "\n")
        return 3


if __name__ == "__main__":
    raise SystemExit(run_cli())
