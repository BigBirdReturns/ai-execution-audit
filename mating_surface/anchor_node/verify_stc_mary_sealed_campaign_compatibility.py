"""Source-authenticated sealed-campaign compatibility verifier.

This verifier authenticates one already sealed, already detached-verified private
campaign package against the exact frozen predecessor conductor that refused it.

It is NOT the predecessor conductor and never claims to be. It does not execute the
predecessor, does not rewrite the predecessor ledger, does not reseal or mutate the
sealed package, and does not replay packet stages. It reads only, and it emits one
body-free compatibility receipt that separately identifies the predecessor source set
and this repair source.

The verifier is deliberately self-contained and standard-library only so that the
external bootstrap can measure its bytes and execute the measured copy in isolation
from a foreign working directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

PROFILE_SCHEMA = "stc-mary/sealed-campaign-compatibility-profile/1"
PROFILE_ID = "stc-mary/sealed-campaign-compatibility@1"
PROFILE_CANONICAL_SHA256 = "82611206d11eecc047355f10c346ad6609524420e49dd563b4200a4d05947f43"
RECEIPT_SCHEMA = "stc-mary/sealed-campaign-compatibility-receipt/1"
RECEIPT_ID_KEY = "compatibilityId"
RECEIPT_ID_PREFIX = "stcmarysealedcampaigncompatibility1"
REPAIR_SOURCE_SET_SCHEMA = "stc-mary/sealed-campaign-compatibility-source-set/1"
REPAIR_SOURCE_SET_ID_PREFIX = "stcmarysealedcampaigncompatibilitysourceset1"
REPAIR_SOURCE_SET_CLAIM_BOUNDARY = (
    "Exact repair verifier source set. It identifies source bytes and grants no authority."
)
TERMINAL = "SEALED_CAMPAIGN_COMPATIBLE"
AUTHORITY = "none"
MINIMUM_PYTHON = (3, 12)

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CONTENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*_[0-9a-f]{64}$")

MAX_JSON_BYTES = 64 * 1024 * 1024
MAX_MEMBER_BYTES = 8 * 1024 * 1024
MAX_SEALED_MEMBER_BYTES = 64 * 1024 * 1024

# Scanned over string VALUES only, never over keys.
#
# The closed schemas this verifier consumes are exact-key validated against their own
# admitted denominators, so a leaking key cannot survive that gate and a key-name scan
# buys nothing. A key-name scan is also actively wrong here: the admitted disposition
# carries the key `privatePhysicalEvidenceBodyCount`, whose lowercase form contains the
# substring `evidencebody`. Any verifier that scans keys for that fragment refuses every
# valid disposition. Scanning values keeps the real protection without that false refusal.
PRIVATE_VALUE_FRAGMENTS = (
    "password",
    "credential",
    "secret",
    "api_key",
    "apikey",
    "bearer ",
    "stdout",
    "stderr",
)
WINDOWS_PATH_RE = re.compile(r"[A-Za-z]:[\\/]")
UNC_PATH_RE = re.compile(r"^\\\\")
POSIX_PATH_RE = re.compile(r"(?:^|\s)/(?:home|root|mnt|media|var|etc|opt|Users)/")

CLAIM_BOUNDARY = (
    "Body-free compatibility receipt for one unchanged sealed private campaign package. "
    "It separately identifies the frozen predecessor conductor source set, that predecessor's "
    "retained refusal, and this repair verifier source. It replays no packet stage, mutates no "
    "sealed byte, rewrites no predecessor ledger, and grants no physical-Estate, "
    "representative-operator, field-network, operational-C2, production-Lattice, mission, command, "
    "targeting, engagement, effector, or weapons qualification or authority."
)


class CompatibilityError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def fail(code: str, message: str) -> None:
    raise CompatibilityError(code, message)


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        fail(code, message)


def require_supported_python() -> None:
    if sys.version_info < MINIMUM_PYTHON:
        fail(
            "PYTHON_VERSION_UNSUPPORTED",
            f"Python {MINIMUM_PYTHON[0]}.{MINIMUM_PYTHON[1]} or newer is required for junction-safe custody",
        )


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
    result = dict(value)
    result.pop(key, None)
    return result


def assert_identity(value: Mapping[str, Any], id_key: str, prefix: str, code: str, label: str) -> str:
    observed = value.get(id_key)
    require(isinstance(observed, str), code, f"{label} {id_key} is missing")
    require(
        observed == content_id(prefix, body_without(value, id_key)),
        code,
        f"{label} {id_key} differs from its content identity",
    )
    return observed


def exact_keys(value: Any, expected: Iterable[str], code: str, label: str) -> Mapping[str, Any]:
    require(isinstance(value, Mapping), code, f"{label} must be an object")
    require(set(value.keys()) == set(expected), code, f"{label} field denominator differs")
    return value


def assert_content_id(value: Any, code: str, label: str) -> str:
    require(
        isinstance(value, str) and CONTENT_ID_RE.fullmatch(value) is not None,
        code,
        f"{label} is not a content identity",
    )
    return value


def assert_sha256(value: Any, code: str, label: str) -> str:
    require(
        isinstance(value, str) and SHA256_RE.fullmatch(value) is not None,
        code,
        f"{label} is not a lowercase SHA-256 digest",
    )
    return value


def coordinate_component_is_link(path: Path, *, code: str, label: str) -> bool:
    require_supported_python()
    try:
        return path.is_symlink() or path.is_junction()
    except OSError as exc:
        fail(code, f"{label} component could not be inspected: {exc}")
        raise


def validate_lexical_coordinate(path: Path, *, label: str, code: str) -> Path:
    require_supported_python()
    if any(part == os.pardir for part in path.parts):
        fail(code, f"{label} may not contain a parent-directory segment")
    try:
        supplied = path.expanduser()
    except RuntimeError as exc:
        fail(code, f"{label} user expansion failed: {exc}")
        raise
    if any(part == os.pardir for part in supplied.parts):
        fail(code, f"{label} may not contain a parent-directory segment")
    try:
        absolute = Path(os.path.abspath(os.fspath(supplied)))
    except (OSError, ValueError) as exc:
        fail(code, f"{label} could not be made absolute: {exc}")
        raise
    parts = absolute.parts
    if not parts:
        fail(code, f"{label} is empty")
    current = Path(parts[0])
    if coordinate_component_is_link(current, code=code, label=label):
        fail(code, f"{label} contains a symlink or junction component")
    for part in parts[1:]:
        current = current / part
        if coordinate_component_is_link(current, code=code, label=label):
            fail(code, f"{label} contains a symlink or junction component")
    return absolute


def read_bounded_bytes(path: Path, maximum: int, *, code: str, label: str) -> bytes:
    if coordinate_component_is_link(path, code=code, label=label):
        fail(code, f"{label} is a symlink or junction")
    try:
        stat = path.stat()
    except OSError as exc:
        fail(code, f"{label} could not be inspected: {exc}")
        raise
    if not path.is_file():
        fail(code, f"{label} is not a regular file")
    if stat.st_size > maximum:
        fail(code, f"{label} exceeds the bounded read allocation")
    try:
        with path.open("rb") as handle:
            data = handle.read(maximum + 1)
    except OSError as exc:
        fail(code, f"{label} could not be read: {exc}")
        raise
    if len(data) > maximum:
        fail(code, f"{label} changed during the bounded read")
    return data


def read_json_file(path: Path, *, code: str, label: str) -> Mapping[str, Any]:
    data = read_bounded_bytes(path, MAX_JSON_BYTES, code=code, label=label)
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(code, f"{label} is not valid UTF-8 JSON: {exc}")
        raise
    require(isinstance(value, Mapping), code, f"{label} must be a JSON object")
    return value


def iter_string_values(value: Any) -> Iterable[str]:
    if isinstance(value, Mapping):
        for nested in value.values():
            yield from iter_string_values(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from iter_string_values(nested)
    elif isinstance(value, str):
        yield value


def assert_no_private_material(value: Any, *, code: str, label: str) -> None:
    for text in iter_string_values(value):
        lowered = text.lower()
        for fragment in PRIVATE_VALUE_FRAGMENTS:
            require(fragment not in lowered, code, f"{label} exposes forbidden surface: {fragment}")
        require(WINDOWS_PATH_RE.search(text) is None, code, f"{label} exposes a Windows filesystem coordinate")
        require(UNC_PATH_RE.search(text) is None, code, f"{label} exposes a UNC coordinate")
        require(POSIX_PATH_RE.search(text) is None, code, f"{label} exposes a POSIX filesystem coordinate")


def directory_file_names(root: Path, *, code: str, label: str) -> list[str]:
    if coordinate_component_is_link(root, code=code, label=label) or not root.is_dir():
        fail(code, f"{label} is not a regular non-linked directory")
    try:
        entries = sorted(entry.name for entry in root.iterdir())
    except OSError as exc:
        fail(code, f"{label} could not be enumerated: {exc}")
        raise
    return entries


def directory_fence(root: Path, names: Sequence[str], *, code: str, label: str) -> str:
    rows = []
    for name in sorted(names):
        data = read_bounded_bytes(root / name, MAX_SEALED_MEMBER_BYTES, code=code, label=f"{label} member {name}")
        rows.append({"name": name, "bytes": len(data), "sha256": sha256_bytes(data)})
    return content_id("stcmarysealedcampaigncompatibilityfence1", rows)


def file_fence(path: Path, *, code: str, label: str) -> str:
    data = read_bounded_bytes(path, MAX_JSON_BYTES, code=code, label=label)
    return content_id("stcmarysealedcampaigncompatibilityfence1", {"bytes": len(data), "sha256": sha256_bytes(data)})


def measure_source_set(
    root: Path,
    members: Sequence[str],
    *,
    schema: str,
    profile_id: str,
    claim_boundary: str,
    id_key: str,
    id_prefix: str,
    code: str,
    label: str,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for relative in members:
        require("\\" not in relative, code, f"{label} member path is not POSIX-relative")
        member = validate_lexical_coordinate(root / relative, label=f"{label} member", code=code)
        try:
            member.resolve(strict=False).relative_to(root.resolve(strict=False))
        except ValueError:
            fail(code, f"{label} member escapes the source root: {relative}")
        raw = read_bounded_bytes(member, MAX_MEMBER_BYTES, code=code, label=f"{label} member {relative}")
        rows.append({"relativePath": relative, "sha256": sha256_bytes(raw), "bytes": len(raw)})
    body = {
        "schema": schema,
        "profileId": profile_id,
        "members": rows,
        "memberCount": len(rows),
        "totalBytes": sum(row["bytes"] for row in rows),
        "authority": AUTHORITY,
        "claimBoundary": claim_boundary,
    }
    return {**body, id_key: content_id(id_prefix, body)}


def load_profile(path: Path) -> Mapping[str, Any]:
    raw = read_bounded_bytes(path, MAX_MEMBER_BYTES, code="PROFILE_UNREADABLE", label="compatibility profile")
    try:
        profile = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail("PROFILE_INVALID", f"compatibility profile is not valid UTF-8 JSON: {exc}")
        raise
    require(isinstance(profile, Mapping), "PROFILE_INVALID", "compatibility profile must be an object")
    require(profile.get("schema") == PROFILE_SCHEMA, "PROFILE_INVALID", "compatibility profile schema differs")
    require(profile.get("profileId") == PROFILE_ID, "PROFILE_INVALID", "compatibility profile identity differs")
    require(
        sha256_bytes(canonical_json_bytes(profile)) == PROFILE_CANONICAL_SHA256,
        "PROFILE_CANONICAL_DIGEST_INVALID",
        "compatibility profile canonical digest differs from the admitted profile",
    )
    return profile


def verify_sealed_campaign_compatibility(
    *,
    workstation: Path,
    conductor_checkout: Path,
    profile_path: Path,
    repair_source_root: Path,
    measured_verifier_bytes: bytes | None = None,
) -> dict[str, Any]:
    require_supported_python()

    workstation = validate_lexical_coordinate(workstation, label="workstation coordinate", code="WORKSTATION_ROOT_INVALID")
    conductor_checkout = validate_lexical_coordinate(
        conductor_checkout, label="predecessor conductor checkout", code="PREDECESSOR_CHECKOUT_INVALID"
    )
    profile_path = validate_lexical_coordinate(profile_path, label="compatibility profile", code="PROFILE_UNREADABLE")
    repair_source_root = validate_lexical_coordinate(
        repair_source_root, label="repair source root", code="REPAIR_SOURCE_SET_INVALID"
    )

    profile = load_profile(profile_path)
    denominator = profile["campaignDenominator"]
    predecessor_law = profile["predecessor"]
    packet_law = profile["packet"]
    sealed_law = profile["sealedPackage"]
    workstation_law = profile["workstation"]

    require(
        workstation.is_dir() and not coordinate_component_is_link(workstation, code="WORKSTATION_ROOT_INVALID", label="workstation"),
        "WORKSTATION_ROOT_INVALID",
        "workstation root is not a regular non-linked directory",
    )
    require(
        conductor_checkout.is_dir(),
        "PREDECESSOR_CHECKOUT_INVALID",
        "predecessor conductor checkout is not a regular directory",
    )

    # ---- frozen workstation -------------------------------------------------
    marker = read_json_file(
        workstation / workstation_law["markerFile"], code="WORKSTATION_MARKER_INVALID", label="workstation marker"
    )
    exact_keys(marker, predecessor_law["markerKeys"], "WORKSTATION_MARKER_INVALID", "workstation marker")
    require(
        marker["schema"] == predecessor_law["markerSchema"],
        "WORKSTATION_MARKER_INVALID",
        "workstation marker schema differs",
    )
    require(
        marker["profileId"] == predecessor_law["conductorProfileId"],
        "WORKSTATION_MARKER_INVALID",
        "workstation marker names another conductor profile",
    )
    require(marker["authority"] == AUTHORITY, "WORKSTATION_MARKER_INVALID", "workstation marker grants authority")
    assert_identity(
        marker,
        predecessor_law["markerIdKey"],
        predecessor_law["markerIdPrefix"],
        "WORKSTATION_MARKER_ID_INVALID",
        "workstation marker",
    )
    campaign_id = assert_content_id(marker["campaignId"], "WORKSTATION_MARKER_INVALID", "campaign identity")
    campaign_label = marker["campaignLabel"]
    require(
        isinstance(campaign_label, str) and campaign_label.strip() != "",
        "WORKSTATION_MARKER_INVALID",
        "campaign label is empty",
    )

    config = read_json_file(
        workstation / workstation_law["configFile"], code="CAMPAIGN_CONFIG_INVALID", label="campaign configuration"
    )
    require(config.get("schema") == predecessor_law["configSchema"], "CAMPAIGN_CONFIG_INVALID", "campaign configuration schema differs")
    assert_identity(
        config,
        predecessor_law["configIdKey"],
        predecessor_law["configIdPrefix"],
        "CAMPAIGN_CONFIG_ID_INVALID",
        "campaign configuration",
    )
    require(config.get("configId") == marker["configId"], "CAMPAIGN_CONFIG_INVALID", "campaign configuration is not the one the marker names")
    require(config.get("campaignId") == campaign_id, "CAMPAIGN_CONFIG_INVALID", "campaign configuration names another campaign")
    require(config.get("campaignLabel") == campaign_label, "CAMPAIGN_CONFIG_INVALID", "campaign configuration names another campaign label")
    require(config.get("pathMapId") == marker["pathMapId"], "CAMPAIGN_CONFIG_INVALID", "campaign configuration names another path map")
    require(config.get("authority") == AUTHORITY, "CAMPAIGN_CONFIG_INVALID", "campaign configuration grants authority")
    require(
        config.get("conductorSourceSetId") == marker["sourceSetId"],
        "CAMPAIGN_SOURCE_SET_BINDING_INVALID",
        "campaign configuration and marker name different conductor source sets",
    )

    path_map = read_json_file(
        workstation / workstation_law["pathMapFile"], code="PATH_MAP_INVALID", label="workstation path map"
    )
    require(path_map.get("schema") == predecessor_law["pathMapSchema"], "PATH_MAP_INVALID", "path map schema differs")
    require(path_map.get("campaignId") == campaign_id, "PATH_MAP_INVALID", "path map names another campaign")
    require(path_map.get("authority") == AUTHORITY, "PATH_MAP_INVALID", "path map grants authority")
    assert_identity(
        path_map, predecessor_law["pathMapIdKey"], predecessor_law["pathMapIdPrefix"], "PATH_MAP_ID_INVALID", "path map"
    )
    require(path_map.get("pathMapId") == marker["pathMapId"], "PATH_MAP_INVALID", "path map is not the one the marker names")
    paths = path_map.get("paths")
    require(isinstance(paths, Mapping), "PATH_MAP_INVALID", "path map paths must be an object")
    for label in ("packet", "packetState", "sealed"):
        require(
            isinstance(paths.get(label), str) and paths[label].strip() != "",
            "PATH_MAP_INVALID",
            f"path map does not name a {label} coordinate",
        )

    # ---- predecessor conductor source set -----------------------------------
    measured_predecessor = measure_source_set(
        conductor_checkout,
        predecessor_law["sourceMembers"],
        schema=predecessor_law["sourceSetSchema"],
        profile_id=predecessor_law["conductorProfileId"],
        claim_boundary=predecessor_law["sourceSetClaimBoundary"],
        id_key=predecessor_law["sourceSetIdKey"],
        id_prefix=predecessor_law["sourceSetIdPrefix"],
        code="PREDECESSOR_SOURCE_SET_INVALID",
        label="predecessor conductor source set",
    )
    predecessor_source_set_id = measured_predecessor[predecessor_law["sourceSetIdKey"]]
    require(
        predecessor_source_set_id == marker["sourceSetId"],
        "PREDECESSOR_SOURCE_SET_DRIFT",
        "predecessor conductor checkout bytes differ from the source set the frozen campaign recorded",
    )

    # ---- the impossible predicate, read out of the measured predecessor -----
    predicate_law = predecessor_law["impossiblePredicate"]
    predicate_relative = predicate_law["relativePath"]
    predicate_member = next(
        (row for row in measured_predecessor["members"] if row["relativePath"] == predicate_relative), None
    )
    require(
        predicate_member is not None,
        "PREDECESSOR_PREDICATE_UNBOUND",
        "the predicate source member is not part of the measured predecessor source set",
    )
    predicate_bytes = read_bounded_bytes(
        conductor_checkout / predicate_relative,
        MAX_MEMBER_BYTES,
        code="PREDECESSOR_PREDICATE_UNBOUND",
        label="predecessor predicate source",
    )
    require(
        sha256_bytes(predicate_bytes) == predicate_member["sha256"],
        "PREDECESSOR_PREDICATE_UNBOUND",
        "predecessor predicate source changed during measurement",
    )
    predicate_text = predicate_bytes.decode("utf-8", errors="replace")
    require(
        predicate_law["expression"] in " ".join(predicate_text.split()),
        "PREDECESSOR_PREDICATE_ABSENT",
        "the measured predecessor source does not contain the recorded impossible predicate",
    )

    # ---- predecessor refusal, retained not rewritten -------------------------
    ledger = read_json_file(
        workstation / workstation_law["ledgerFile"], code="PREDECESSOR_LEDGER_INVALID", label="predecessor ledger"
    )
    require(ledger.get("schema") == predecessor_law["ledgerSchema"], "PREDECESSOR_LEDGER_INVALID", "predecessor ledger schema differs")
    require(ledger.get("campaignId") == campaign_id, "PREDECESSOR_LEDGER_INVALID", "predecessor ledger names another campaign")
    require(ledger.get("profileId") == predecessor_law["conductorProfileId"], "PREDECESSOR_LEDGER_INVALID", "predecessor ledger names another conductor profile")
    require(ledger.get("authority") == AUTHORITY, "PREDECESSOR_LEDGER_INVALID", "predecessor ledger grants authority")
    assert_identity(
        ledger,
        predecessor_law["ledgerIdKey"],
        predecessor_law["ledgerIdPrefix"],
        "PREDECESSOR_LEDGER_ID_INVALID",
        "predecessor ledger",
    )
    phases = ledger.get("phases")
    require(isinstance(phases, list), "PREDECESSOR_LEDGER_INVALID", "predecessor ledger phases must be a list")
    refused_row = next(
        (row for row in phases if isinstance(row, Mapping) and row.get("phase") == predecessor_law["refusedPhase"]), None
    )
    require(refused_row is not None, "PREDECESSOR_REFUSAL_ABSENT", "the predecessor ledger has no sealed-flight row")
    require(
        refused_row.get("state") == "REFUSED",
        "PREDECESSOR_REFUSAL_ABSENT",
        "the predecessor sealed-flight row is not the retained refusal",
    )
    require(
        refused_row.get("reasonCode") == predecessor_law["refusalCode"],
        "PREDECESSOR_REFUSAL_MISMATCH",
        "the predecessor sealed-flight refusal names another reason code",
    )

    # ---- configured packet ---------------------------------------------------
    packet_root = validate_lexical_coordinate(Path(str(paths.get("packet"))), label="packet root", code="PACKET_ROOT_INVALID")
    packet_state_path = validate_lexical_coordinate(
        Path(str(paths.get("packetState"))), label="packet state", code="PACKET_STATE_INVALID"
    )
    packet_marker = read_json_file(
        packet_root / packet_law["markerFile"], code="PACKET_MARKER_INVALID", label="packet marker"
    )
    exact_keys(packet_marker, packet_law["markerKeys"], "PACKET_MARKER_INVALID", "packet marker")
    require(packet_marker["schema"] == packet_law["markerSchema"], "PACKET_MARKER_INVALID", "packet marker schema differs")
    require(packet_marker["authority"] == AUTHORITY, "PACKET_MARKER_INVALID", "packet marker grants authority")
    assert_identity(
        packet_marker, packet_law["markerIdKey"], packet_law["markerIdPrefix"], "PACKET_MARKER_ID_INVALID", "packet marker"
    )
    require(
        packet_marker["campaignLabel"] == campaign_label,
        "PACKET_CAMPAIGN_BINDING_INVALID",
        "packet marker belongs to another campaign",
    )
    packet_id = assert_content_id(packet_marker["packetId"], "PACKET_MARKER_INVALID", "packet identity")

    packet_state_fence_before = file_fence(packet_state_path, code="PACKET_STATE_INVALID", label="packet state")
    packet_state = read_json_file(packet_state_path, code="PACKET_STATE_INVALID", label="packet state")
    exact_keys(packet_state, packet_law["stateKeys"], "PACKET_STATE_INVALID", "packet state")
    require(packet_state["schema"] == packet_law["stateSchema"], "PACKET_STATE_INVALID", "packet state schema differs")
    require(packet_state["authority"] == AUTHORITY, "PACKET_STATE_INVALID", "packet state grants authority")
    assert_identity(
        packet_state, packet_law["stateIdKey"], packet_law["stateIdPrefix"], "PACKET_STATE_ID_INVALID", "packet state"
    )
    require(
        packet_state["campaignLabel"] == campaign_label,
        "PACKET_CAMPAIGN_BINDING_INVALID",
        "packet state belongs to another campaign",
    )
    require(
        packet_state["packetId"] == packet_id,
        "PACKET_CAMPAIGN_BINDING_INVALID",
        "packet state and packet marker name different packets",
    )
    require(packet_state["sealed"] is True, "PACKET_NOT_SEALED", "packet state is not sealed")
    require(
        packet_state["stageDenominator"] == denominator["stageDenominator"]
        and packet_state["completedStageCount"] == denominator["stageDenominator"]
        and packet_state["nextStage"] is None,
        "PACKET_STAGE_DENOMINATOR_INVALID",
        "packet stage denominator is not the complete admitted denominator",
    )
    sealed_disposition_id = assert_content_id(
        packet_state["sealedDispositionId"], "PACKET_STATE_INVALID", "packet sealed disposition identity"
    )

    # ---- unchanged sealed package -------------------------------------------
    sealed_root = validate_lexical_coordinate(Path(str(paths.get("sealed"))), label="sealed root", code="SEALED_ROOT_INVALID")
    observed_files = directory_file_names(sealed_root, code="SEALED_ROOT_INVALID", label="sealed root")
    require(
        observed_files == sorted(sealed_law["sealedRootFiles"]),
        "SEALED_ROOT_DENOMINATOR_INVALID",
        "sealed root file denominator differs from the admitted sealed package",
    )
    require(
        len(observed_files) == denominator["sealedRootFileCount"],
        "SEALED_ROOT_DENOMINATOR_INVALID",
        "sealed root file count differs",
    )
    sealed_fence_before = directory_fence(
        sealed_root, observed_files, code="SEALED_ROOT_INVALID", label="sealed root"
    )

    sealed_marker = read_json_file(
        sealed_root / sealed_law["markerFile"], code="SEALED_MARKER_INVALID", label="sealed marker"
    )
    require(sealed_marker.get("schema") == sealed_law["markerSchema"], "SEALED_MARKER_INVALID", "sealed marker schema differs")
    require(
        sealed_marker.get("flightMode") == sealed_law["requiredFlightMode"],
        "SEALED_MARKER_INVALID",
        "sealed marker flight mode differs",
    )
    require(
        sealed_marker.get("publicEvidenceBodyCount") == denominator["publicEvidenceBodyCount"]
        and sealed_marker.get("authority") == AUTHORITY,
        "SEALED_MARKER_INVALID",
        "sealed marker widens evidence or authority",
    )
    marker_id = assert_identity(
        sealed_marker, sealed_law["markerIdKey"], sealed_law["markerIdPrefix"], "SEALED_MARKER_ID_INVALID", "sealed marker"
    )
    run_id = assert_content_id(sealed_marker.get("runId"), "SEALED_MARKER_INVALID", "sealed marker run identity")
    disposition_id = assert_content_id(
        sealed_marker.get("dispositionId"), "SEALED_MARKER_INVALID", "sealed marker disposition identity"
    )

    manifest = read_json_file(
        sealed_root / sealed_law["manifestFile"], code="SEALED_MANIFEST_INVALID", label="sealed manifest"
    )
    require(manifest.get("schema") == sealed_law["manifestSchema"], "SEALED_MANIFEST_INVALID", "sealed manifest schema differs")
    require(manifest.get("authority") == AUTHORITY, "SEALED_MANIFEST_INVALID", "sealed manifest grants authority")
    require(
        manifest.get("publicEvidenceBodyCount") == denominator["publicEvidenceBodyCount"],
        "SEALED_MANIFEST_INVALID",
        "sealed manifest widens public evidence",
    )
    manifest_id = assert_identity(
        manifest, sealed_law["manifestIdKey"], sealed_law["manifestIdPrefix"], "SEALED_MANIFEST_ID_INVALID", "sealed manifest"
    )
    require(
        manifest.get("runId") == run_id and manifest.get("dispositionId") == disposition_id,
        "SEALED_MANIFEST_BINDING_INVALID",
        "sealed manifest names another run or disposition",
    )
    manifest_files = manifest.get("files")
    require(isinstance(manifest_files, list), "SEALED_MANIFEST_INVALID", "sealed manifest files must be a list")
    require(
        manifest.get("fileCount") == len(manifest_files) == denominator["manifestFileCount"],
        "SEALED_MANIFEST_INVALID",
        "sealed manifest file denominator differs",
    )
    require(
        sorted(str(row.get("path")) for row in manifest_files if isinstance(row, Mapping))
        == sorted(sealed_law["manifestMemberFiles"]),
        "SEALED_MANIFEST_INVALID",
        "sealed manifest member denominator differs",
    )
    for row in manifest_files:
        exact_keys(row, ["path", "bytes", "sha256"], "SEALED_MANIFEST_INVALID", "sealed manifest file row")
        relative = str(row["path"])
        require("\\" not in relative and ".." not in Path(relative).parts, "SEALED_MANIFEST_INVALID", "sealed manifest path is unsafe")
        assert_sha256(row["sha256"], "SEALED_MANIFEST_INVALID", f"sealed manifest digest for {relative}")
        data = read_bounded_bytes(
            sealed_root / relative,
            MAX_SEALED_MEMBER_BYTES,
            code="SEALED_PACKAGE_FILE_MISMATCH",
            label=f"sealed member {relative}",
        )
        require(
            len(data) == row["bytes"] and sha256_bytes(data) == row["sha256"],
            "SEALED_PACKAGE_FILE_MISMATCH",
            f"sealed member bytes differ from the manifest: {relative}",
        )

    run = read_json_file(sealed_root / sealed_law["runFile"], code="SEALED_RUN_INVALID", label="sealed run")
    require(run.get("runId") == run_id, "SEALED_RUN_BINDING_INVALID", "sealed run is not the run the marker names")

    disposition = read_json_file(
        sealed_root / sealed_law["publicDispositionFile"], code="PUBLIC_DISPOSITION_INVALID", label="public disposition"
    )
    exact_keys(
        disposition, sealed_law["publicDispositionKeys"], "PUBLIC_DISPOSITION_SCHEMA_INVALID", "public disposition"
    )
    require(
        predicate_law["absentDispositionField"] not in disposition,
        "PUBLIC_DISPOSITION_SCHEMA_INVALID",
        "public disposition carries the field the closed sealer schema cannot emit",
    )
    require(
        disposition["schema"] == sealed_law["publicDispositionSchema"],
        "PUBLIC_DISPOSITION_SCHEMA_INVALID",
        "public disposition schema differs",
    )
    assert_identity(
        disposition,
        sealed_law["publicDispositionIdKey"],
        sealed_law["publicDispositionIdPrefix"],
        "PUBLIC_DISPOSITION_ID_INVALID",
        "public disposition",
    )
    require(
        disposition["dispositionId"] == disposition_id and disposition["runId"] == run_id,
        "PUBLIC_DISPOSITION_BINDING_INVALID",
        "public disposition names another run or disposition",
    )
    require(
        disposition["flightMode"] == sealed_law["requiredFlightMode"] and disposition["selfAttestationOnly"] is True,
        "PUBLIC_DISPOSITION_CLAIM_INVALID",
        "public disposition flight mode or self-attestation boundary differs",
    )
    require(
        disposition["stageCount"] == denominator["stageDenominator"]
        and disposition["successfulStageCount"] == denominator["successfulStageCount"]
        and disposition["humanRequiredStageCount"] == denominator["humanRequiredStageCount"],
        "PUBLIC_DISPOSITION_DENOMINATOR_INVALID",
        "public disposition terminal denominator differs",
    )
    require(
        disposition["successfulStageCount"] + disposition["humanRequiredStageCount"] == disposition["stageCount"],
        "PUBLIC_DISPOSITION_DENOMINATOR_INVALID",
        "public disposition terminal denominator does not close over the stage denominator",
    )
    require(
        disposition["humanRequiredStageCount"] > 0,
        "UNRESOLVED_OBLIGATION_DISCHARGED",
        "public disposition no longer retains an unresolved human obligation",
    )
    require(
        isinstance(disposition["stageReceiptIds"], list)
        and len(disposition["stageReceiptIds"]) == denominator["stageDenominator"]
        and len(set(disposition["stageReceiptIds"])) == denominator["stageDenominator"],
        "PUBLIC_DISPOSITION_DENOMINATOR_INVALID",
        "public disposition stage receipt denominator differs",
    )
    require(
        disposition["privatePhysicalEvidenceBodyCount"] == denominator["privateEvidenceBodyCount"],
        "PRIVATE_EVIDENCE_DENOMINATOR_INVALID",
        "private evidence body denominator differs from the admitted campaign",
    )
    require(
        disposition["publicEvidenceBodyCount"] == denominator["publicEvidenceBodyCount"],
        "PUBLIC_EVIDENCE_WIDENED",
        "public evidence body denominator differs",
    )
    require(
        disposition["privatePhysicalFlightCompleted"] is True,
        "PRIVATE_FLIGHT_INCOMPLETE",
        "public disposition does not record a complete private physical flight",
    )
    require(disposition["authority"] == AUTHORITY, "AUTHORITY_WIDENED", "public disposition grants authority")
    for key in sealed_law["strongerQualificationKeys"]:
        require(disposition[key] is False, "QUALIFICATION_WIDENED", f"public disposition widens {key}")
    assert_no_private_material(disposition, code="PUBLIC_DISPOSITION_PRIVATE_MATERIAL", label="public disposition")

    verification = read_json_file(
        sealed_root / sealed_law["verificationFile"], code="SEALED_VERIFICATION_INVALID", label="sealed verification"
    )
    detached = read_json_file(
        sealed_root / sealed_law["detachedVerificationFile"],
        code="DETACHED_VERIFICATION_INVALID",
        label="detached verification",
    )
    require(
        canonical_json(detached) == canonical_json(verification),
        "DETACHED_VERIFICATION_DRIFT",
        "detached verification differs from the sealed verification it must reproduce",
    )
    require(
        verification.get("schema") == sealed_law["verificationSchema"],
        "SEALED_VERIFICATION_INVALID",
        "sealed verification schema differs",
    )
    require(verification.get("status") == "PASS", "DETACHED_VERIFICATION_NOT_PASS", "detached verification did not pass")
    verification_id = assert_identity(
        verification,
        sealed_law["verificationIdKey"],
        sealed_law["verificationIdPrefix"],
        "SEALED_VERIFICATION_ID_INVALID",
        "sealed verification",
    )
    require(
        verification.get("runId") == run_id and verification.get("dispositionId") == disposition_id,
        "DETACHED_VERIFICATION_BINDING_INVALID",
        "detached verification names another run or disposition",
    )
    require(
        verification.get("deterministicReceiptReplay") is True,
        "DETERMINISTIC_REPLAY_ABSENT",
        "detached verification does not record deterministic receipt replay",
    )
    require(
        verification.get("bodyFreePublicDisposition") is True,
        "BODY_FREE_DISPOSITION_ABSENT",
        "detached verification does not record a body-free public disposition",
    )
    require(
        verification.get("privatePhysicalEvidenceBodyCount") == denominator["privateEvidenceBodyCount"]
        and verification.get("publicEvidenceBodyCount") == denominator["publicEvidenceBodyCount"],
        "PRIVATE_EVIDENCE_DENOMINATOR_INVALID",
        "detached verification evidence denominator differs",
    )
    require(
        verification.get("fileCount") == denominator["manifestFileCount"],
        "SEALED_MANIFEST_INVALID",
        "detached verification file denominator differs from the manifest",
    )
    require(verification.get("authority") == AUTHORITY, "AUTHORITY_WIDENED", "detached verification grants authority")
    for key in sealed_law["strongerQualificationKeys"]:
        require(verification.get(key) is False, "QUALIFICATION_WIDENED", f"detached verification widens {key}")

    # ---- the binding the predecessor could not express ----------------------
    require(
        sealed_disposition_id == disposition_id,
        "PACKET_SEALED_DISPOSITION_MISMATCH",
        "packet state names a different sealed disposition than the sealed package",
    )

    # ---- repair source, separately identified -------------------------------
    measured_repair = measure_source_set(
        repair_source_root,
        profile["repairSourceMembers"],
        schema=REPAIR_SOURCE_SET_SCHEMA,
        profile_id=PROFILE_ID,
        claim_boundary=REPAIR_SOURCE_SET_CLAIM_BOUNDARY,
        id_key="sourceSetId",
        id_prefix=REPAIR_SOURCE_SET_ID_PREFIX,
        code="REPAIR_SOURCE_SET_INVALID",
        label="repair verifier source set",
    )
    repair_source_set_id = measured_repair["sourceSetId"]
    require(
        repair_source_set_id != predecessor_source_set_id,
        "REPAIR_SOURCE_IMPERSONATES_PREDECESSOR",
        "the repair verifier source set is not separately identified from the predecessor",
    )
    predecessor_member_paths = {row["relativePath"] for row in measured_predecessor["members"]}
    repair_member_paths = {row["relativePath"] for row in measured_repair["members"]}
    require(
        predecessor_member_paths.isdisjoint(repair_member_paths),
        "REPAIR_SOURCE_IMPERSONATES_PREDECESSOR",
        "the repair verifier claims a predecessor conductor source member as its own",
    )

    measured_verifier_sha256 = None
    if measured_verifier_bytes is not None:
        measured_verifier_sha256 = sha256_bytes(measured_verifier_bytes)
        stored = next(
            (
                row
                for row in measured_repair["members"]
                if row["relativePath"].endswith("verify_stc_mary_sealed_campaign_compatibility.py")
            ),
            None,
        )
        require(
            stored is not None and stored["sha256"] == measured_verifier_sha256,
            "MEASURED_VERIFIER_MEMBER_BINDING_INVALID",
            "the executing verifier bytes are not the stored repair source member",
        )

    # ---- nothing moved while we read ----------------------------------------
    sealed_fence_after = directory_fence(sealed_root, observed_files, code="SEALED_ROOT_INVALID", label="sealed root")
    packet_state_fence_after = file_fence(packet_state_path, code="PACKET_STATE_INVALID", label="packet state")
    require(
        sealed_fence_after == sealed_fence_before,
        "SEALED_PACKAGE_MUTATED",
        "the sealed package changed while it was being authenticated",
    )
    require(
        packet_state_fence_after == packet_state_fence_before,
        "PACKET_STAGES_REPLAYED",
        "the packet state changed while it was being authenticated",
    )

    checks = [
        "workstation-marker-identity",
        "workstation-config-binding",
        "workstation-path-map-identity",
        "predecessor-source-set-exact",
        "predecessor-impossible-predicate-bound",
        "predecessor-refusal-retained",
        "packet-marker-identity",
        "packet-state-identity",
        "packet-campaign-binding-exact",
        "packet-sealed-disposition-binding-exact",
        "packet-stage-denominator-complete",
        "sealed-root-file-denominator",
        "sealed-marker-identity",
        "sealed-manifest-identity",
        "sealed-manifest-member-byte-identities",
        "sealed-run-binding",
        "public-disposition-closed-schema",
        "public-disposition-identity",
        "public-disposition-run-and-disposition-binding",
        "public-disposition-terminal-denominator",
        "unresolved-obligation-retained",
        "detached-verification-identity",
        "detached-verification-binding",
        "detached-verification-pass",
        "deterministic-receipt-replay",
        "body-free-public-disposition",
        "private-evidence-denominator",
        "public-evidence-none",
        "stronger-qualifications-false",
        "authority-none",
        "repair-source-separately-identified",
        "sealed-package-unmutated-fence",
        "packet-stages-not-replayed-fence",
    ]
    if measured_verifier_sha256 is not None:
        checks.append("measured-verifier-member-binding")

    body = {
        "schema": RECEIPT_SCHEMA,
        "status": "PASS",
        "terminal": TERMINAL,
        "profileId": PROFILE_ID,
        "campaignId": campaign_id,
        "packetId": packet_id,
        "runId": run_id,
        "dispositionId": disposition_id,
        "markerId": marker_id,
        "manifestId": manifest_id,
        "verificationId": verification_id,
        "predecessorSourceSetId": predecessor_source_set_id,
        "predecessorConductorProfileId": predecessor_law["conductorProfileId"],
        "predecessorRefusedPhase": predecessor_law["refusedPhase"],
        "predecessorRefusal": predecessor_law["refusalCode"],
        "predecessorImpossibleField": predicate_law["absentDispositionField"],
        "predecessorLedgerId": ledger[predecessor_law["ledgerIdKey"]],
        "repairSourceSetId": repair_source_set_id,
        "repairSourceMemberCount": measured_repair["memberCount"],
        "predecessorSourceMemberCount": measured_predecessor["memberCount"],
        "stageDenominator": denominator["stageDenominator"],
        "successfulStageCount": disposition["successfulStageCount"],
        "humanRequiredStageCount": disposition["humanRequiredStageCount"],
        "refusedStageCount": denominator["refusedStageCount"],
        "unresolvedObligationRetained": True,
        "manifestFileCount": manifest["fileCount"],
        "sealedRootFileCount": len(observed_files),
        "manifestedFileBytesUnchanged": True,
        "detachedVerificationStatus": "PASS",
        "deterministicReceiptReplay": True,
        "bodyFreePublicDisposition": True,
        "privateEvidenceBodies": disposition["privatePhysicalEvidenceBodyCount"],
        "publicEvidenceBodies": disposition["publicEvidenceBodyCount"],
        "privatePhysicalFlightCompleted": True,
        "packageMutated": False,
        "packetStagesReplayed": False,
        "predecessorLedgerRewritten": False,
        "predecessorConductorExecuted": False,
        "physicalEstateQualified": False,
        "representativeOperatorQualified": False,
        "fieldNetworkQualified": False,
        "operationalC2Qualified": False,
        "productionLatticeQualified": False,
        "missionAuthorityGranted": False,
        "commandAuthorityGranted": False,
        "networkRequired": False,
        "externalServiceCalls": 0,
        "operationalCredentials": 0,
        "checks": checks,
        "measuredVerifierSha256": measured_verifier_sha256,
        "bootstrapAuthenticated": False,
        "authority": AUTHORITY,
        "claimBoundary": CLAIM_BOUNDARY,
    }
    receipt = {**body, RECEIPT_ID_KEY: content_id(RECEIPT_ID_PREFIX, body)}
    assert_no_private_material(receipt, code="COMPATIBILITY_RECEIPT_PRIVATE_MATERIAL", label="compatibility receipt")
    return receipt


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Authenticate one unchanged sealed private campaign package against its exact frozen predecessor conductor"
    )
    parser.add_argument("--workstation", type=Path, required=True)
    parser.add_argument("--conductor-checkout", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--repair-source-root", type=Path)
    parser.add_argument("--out", type=Path)
    return parser.parse_args(argv)


def refusal_document(code: str, message: str) -> dict[str, Any]:
    return {
        "schema": RECEIPT_SCHEMA,
        "status": "REFUSED",
        "code": code,
        "message": message,
        "terminal": None,
        "bootstrapAuthenticated": False,
        "packageMutated": False,
        "packetStagesReplayed": False,
        "predecessorLedgerRewritten": False,
        "predecessorConductorExecuted": False,
        "authority": AUTHORITY,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        profile_path = args.profile
        repair_source_root = args.repair_source_root
        if repair_source_root is None:
            repair_source_root = profile_path.resolve(strict=False).parent.parent.parent
        output = None
        if args.out is not None:
            output = validate_lexical_coordinate(args.out, label="receipt output coordinate", code="RECEIPT_PATH_INVALID")
            if output.exists():
                fail("RECEIPT_OUTPUT_EXISTS", "compatibility receipt output must not already exist")
        receipt = verify_sealed_campaign_compatibility(
            workstation=args.workstation,
            conductor_checkout=args.conductor_checkout,
            profile_path=profile_path,
            repair_source_root=repair_source_root,
            measured_verifier_bytes=globals().get("_STC_MARY_BOOTSTRAP_MEASURED_VERIFIER_BYTES"),
        )
        data = canonical_json_bytes(receipt)
        if output is None:
            sys.stdout.buffer.write(data)
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(data)
        return 0
    except CompatibilityError as exc:
        sys.stdout.buffer.write(canonical_json_bytes(refusal_document(exc.code, str(exc))))
        return 1
    except (OSError, ValueError) as exc:
        sys.stdout.buffer.write(canonical_json_bytes(refusal_document("COMPATIBILITY_FILESYSTEM_ERROR", str(exc))))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
