"""Independently verify one compiled stc-mary/private-flight-packet/0.2 successor packet.

This verifier deliberately imports nothing from the source set that produced the packet.
Every primitive it needs -- canonical JSON, content identity, bounded reads, source-set
measurement -- is re-implemented here, so a defect in the shared construction law cannot
authenticate the objects that law produced.

It answers one question: is this packet a truthful successor, before any evidence has
been offered for it?

    the marker, the state and the successor contract name one 0.2 succession
    the packet identity recomputes from the succession it declares
    the predecessor packet, the handoff and the source set exist and re-identify
    every declared source member byte reproduces the source-set identity
    the packet is configured, unrecorded, unsealed, and carries no stage record
    nothing anywhere grants authority

It writes nothing to the packet and records no stage.
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

RECEIPT_SCHEMA = "stc-mary/successor-packet-verification/1"
RECEIPT_ID_KEY = "verificationId"
RECEIPT_ID_PREFIX = "stcmarysuccessorpacketverification1"

PROFILE_SCHEMA = "stc-mary/successor-packet-flight-profile/1"
PROFILE_ID = "stc-mary/successor-packet-flight-01@1"
ADMISSION_PROFILE_SCHEMA = "stc-mary/packet-evidence-admission-profile/1"

AUTHORITY = "none"
MINIMUM_PYTHON = (3, 12)

CONTENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*_[0-9a-f]{64}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
RELATIVE_MEMBER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,255}$")

MAX_JSON_BYTES = 64 * 1024 * 1024
MAX_MEMBER_BYTES = 8 * 1024 * 1024
MAX_TEXT_FIELD = 8192

PRIVATE_VALUE_FRAGMENTS = ("password", "secret", "token", "credential", "api_key", "apikey")
WINDOWS_PATH_RE = re.compile(r"[A-Za-z]:[\\/]")
UNC_PATH_RE = re.compile(r"^\\\\")
POSIX_PATH_RE = re.compile(r"(?:^|\s)/(?:home|root|mnt|media|var|etc|opt|Users)/")

CLAIM_BOUNDARY = (
    "Independent verification of one compiled successor packet before any evidence is offered "
    "for it. It confirms lineage, succession agreement, measured source custody and an "
    "unrecorded, unsealed pre-record state. It records no stage, seals nothing, admits no "
    "evidence, authenticates no human principal, qualifies no physical estate, representative "
    "operator, field network, operational C2 or production Lattice, and grants no mission, "
    "command, targeting, engagement, effector or weapons authority."
)


class SuccessorPacketError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def fail(code: str, message: str) -> None:
    raise SuccessorPacketError(code, message)


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


def require_supported_python() -> None:
    require(
        sys.version_info[:2] >= MINIMUM_PYTHON,
        "PYTHON_RUNTIME_UNSUPPORTED",
        f"this verifier requires Python {MINIMUM_PYTHON[0]}.{MINIMUM_PYTHON[1]} or newer",
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


def assert_bounded_text(value: Any, code: str, label: str, maximum: int = MAX_TEXT_FIELD) -> str:
    require(isinstance(value, str) and 0 < len(value) <= maximum, code, f"{label} is not bounded text")
    return value


def coordinate_component_is_link(path: Path, *, code: str, label: str) -> bool:
    try:
        if path.is_symlink():
            return True
        if os.name == "nt" and path.exists():
            try:
                return bool(path.lstat().st_file_attributes & 0x400)
            except (OSError, AttributeError):
                return False
        return False
    except OSError as exc:
        fail(code, f"{label} could not be inspected: {exc}")
        raise


def validate_lexical_coordinate(path: Path, *, label: str, code: str) -> Path:
    require_supported_python()
    if any(part == os.pardir for part in path.parts):
        fail(code, f"{label} may not contain a parent-directory segment")
    try:
        absolute = Path(os.path.abspath(os.fspath(path.expanduser())))
    except (OSError, ValueError, RuntimeError) as exc:
        fail(code, f"{label} could not be made absolute: {exc}")
        raise
    parts = absolute.parts
    require(bool(parts), code, f"{label} is empty")
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
    require(path.is_file(), code, f"{label} is not a regular file")
    require(stat.st_size <= maximum, code, f"{label} exceeds the bounded read allocation")
    try:
        with path.open("rb") as handle:
            data = handle.read(maximum + 1)
    except OSError as exc:
        fail(code, f"{label} could not be read: {exc}")
        raise
    require(len(data) <= maximum, code, f"{label} changed during the bounded read")
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
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key)
            yield from iter_string_values(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from iter_string_values(item)


def assert_no_private_material(value: Any, *, code: str, label: str) -> None:
    for text in iter_string_values(value):
        lowered = text.lower()
        for fragment in PRIVATE_VALUE_FRAGMENTS:
            require(fragment not in lowered, code, f"{label} carries a private-looking value")
        require(WINDOWS_PATH_RE.search(text) is None, code, f"{label} carries a local filesystem coordinate")
        require(UNC_PATH_RE.search(text) is None, code, f"{label} carries a UNC coordinate")
        require(POSIX_PATH_RE.search(text) is None, code, f"{label} carries a local filesystem coordinate")


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
        require(
            RELATIVE_MEMBER_RE.fullmatch(relative) is not None,
            code,
            f"{label} member path is not an admitted relative member",
        )
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


# --------------------------------------------------------------------------------
# profiles
# --------------------------------------------------------------------------------


def load_profiles(profile_path: Path, repository: Path) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    profile = read_json_file(profile_path, code="PROFILE_UNREADABLE", label="successor flight profile")
    require(profile.get("schema") == PROFILE_SCHEMA, "PROFILE_INVALID", "successor flight profile schema differs")
    require(profile.get("profileId") == PROFILE_ID, "PROFILE_INVALID", "successor flight profile identity differs")
    require(profile.get("authority") == AUTHORITY, "AUTHORITY_WIDENED", "successor flight profile grants authority")

    law = profile["admissionProfile"]
    admission = read_json_file(
        repository / law["relativePath"], code="ADMISSION_PROFILE_UNREADABLE", label="admission profile"
    )
    require(
        admission.get("schema") == ADMISSION_PROFILE_SCHEMA,
        "ADMISSION_PROFILE_INVALID",
        "admission profile schema differs",
    )
    require(
        admission.get("profileId") == law["profileId"],
        "ADMISSION_PROFILE_INVALID",
        "admission profile identity is not the admitted profile this source is bound to",
    )
    require(
        sha256_bytes(canonical_json_bytes(admission)) == law["canonicalSha256"],
        "ADMISSION_PROFILE_CANONICAL_DIGEST_INVALID",
        "admission profile canonical digest differs from the pinned admitted digest",
    )
    return profile, admission


# --------------------------------------------------------------------------------
# verification
# --------------------------------------------------------------------------------


def verify_successor_packet(
    *, packet: Path, profile_path: Path, repository: Path, measured_verifier_bytes: bytes | None = None
) -> dict[str, Any]:
    require_supported_python()
    packet = validate_lexical_coordinate(packet, label="packet root", code="PACKET_ROOT_INVALID")
    profile_path = validate_lexical_coordinate(
        profile_path, label="successor flight profile", code="PROFILE_UNREADABLE"
    )
    repository = validate_lexical_coordinate(repository, label="repository root", code="SOURCE_ROOT_INVALID")
    require(
        packet.is_dir()
        and not coordinate_component_is_link(packet, code="PACKET_ROOT_INVALID", label="packet root"),
        "PACKET_ROOT_INVALID",
        "packet root is not a regular non-linked directory",
    )
    require(
        not is_within(packet, repository),
        "PACKET_INSIDE_REPOSITORY",
        "the successor packet may not live inside the public repository",
    )

    profile, admission = load_profiles(profile_path, repository)
    packet_law = profile["packet"]
    lineage_law = profile["lineage"]
    files = packet_law["files"]
    stages = list(admission["stageSequence"])

    # ---- marker -------------------------------------------------------------------
    marker = read_json_file(packet / files["marker"], code="PACKET_MARKER_INVALID", label="packet marker")
    exact_keys(marker, packet_law["markerKeys"], "PACKET_MARKER_INVALID", "packet marker")
    require(
        marker["schema"] == packet_law["markerSchema"], "PACKET_MARKER_INVALID", "packet marker schema differs"
    )
    marker_id = assert_identity(
        marker, packet_law["markerIdKey"], packet_law["markerIdPrefix"], "PACKET_MARKER_INVALID", "packet marker"
    )
    require(marker["authority"] == AUTHORITY, "AUTHORITY_WIDENED", "packet marker grants authority")
    campaign_label = assert_bounded_text(marker["campaignLabel"], "PACKET_MARKER_INVALID", "campaign label", 256)
    packet_id = assert_content_id(marker["packetId"], "PACKET_MARKER_INVALID", "packet identity")
    # The frozen refusal is checked first, on purpose. Behind the generic
    # successor-profile check it would be unreachable decoration: a 0.1 packet would
    # already have refused for the wrong reason, and the boundary this source set exists
    # to hold would never be the one that fired.
    require(
        marker["packetProfileId"] != packet_law["predecessorPacketProfileId"],
        "DIRECT_FROZEN_PACKET_APPLICATION_FORBIDDEN",
        "this verifier does not govern the frozen predecessor packet",
    )
    require(
        marker["packetProfileId"] == packet_law["packetProfileId"],
        "SUCCESSOR_PROFILE_INVALID",
        "the packet marker does not carry the 0.2 successor packet profile",
    )
    require(
        marker["physicalProfileId"] == packet_law["physicalProfileId"],
        "PACKET_MARKER_INVALID",
        "the packet marker names another physical-flight profile",
    )
    # The identity is derived, not asserted: a packet cannot claim a succession its own
    # identity does not encode.
    require(
        packet_id
        == content_id(
            packet_law["packetIdPrefix"],
            {
                "packetProfileId": packet_law["packetProfileId"],
                "physicalProfileId": packet_law["physicalProfileId"],
                "campaignLabel": campaign_label,
                "stageSequence": stages,
            },
        ),
        "PACKET_IDENTITY_NOT_DERIVED",
        "the packet identity does not recompute from the succession the marker declares",
    )

    # ---- state --------------------------------------------------------------------
    state = read_json_file(packet / files["state"], code="PACKET_STATE_INVALID", label="packet state")
    exact_keys(state, packet_law["stateKeys"], "PACKET_STATE_INVALID", "packet state")
    require(state["schema"] == packet_law["stateSchema"], "PACKET_STATE_INVALID", "packet state schema differs")
    state_id = assert_identity(
        state, packet_law["stateIdKey"], packet_law["stateIdPrefix"], "PACKET_STATE_INVALID", "packet state"
    )
    require(state["authority"] == AUTHORITY, "AUTHORITY_WIDENED", "packet state grants authority")
    for field in ("packetProfileId", "physicalProfileId"):
        require(
            state[field] == marker[field],
            "PACKET_PROFILE_SUCCESSION_SPLIT",
            f"packet marker and packet state name different {field} values",
        )
    require(
        state["packetId"] == packet_id and state["campaignLabel"] == campaign_label,
        "PACKET_CAMPAIGN_BINDING_INVALID",
        "packet state and packet marker name different packets or campaigns",
    )
    require(
        state["configurationState"] == packet_law["requiredConfigurationState"],
        "PACKET_NOT_CONFIGURED",
        "the packet is not in the configured pre-record state",
    )
    require(
        state["sealed"] is False and state["sealedDispositionId"] is None,
        "PACKET_ALREADY_SEALED",
        "the packet is already sealed",
    )
    require(
        list(state["stageDenominator"]) == stages,
        "PACKET_STAGE_DENOMINATOR_INVALID",
        "the packet stage denominator differs from the admitted sixteen-stage denominator",
    )
    rows = state["stages"]
    require(
        isinstance(rows, list) and len(rows) == len(stages),
        "PACKET_STAGE_DENOMINATOR_INVALID",
        "the packet stage state denominator differs",
    )
    for index, row in enumerate(rows):
        exact_keys(row, packet_law["stateRowKeys"], "PACKET_STATE_INVALID", "packet stage state row")
        require(
            row["stage"] == stages[index] and row["sequence"] == index + 1,
            "PACKET_STAGE_DENOMINATOR_INVALID",
            "the packet stage state order differs",
        )
        require(
            row["status"] == "unrecorded" and row["recordDigest"] is None and row["evidenceCount"] == 0,
            "PACKET_STAGES_ALREADY_RECORDED",
            f"stage {row['stage']} already carries a recorded stage record",
        )
        record_path = packet / Path(row["draftPath"]).parent / packet_law["stageRecord"]["fileName"]
        require(
            not record_path.exists(),
            "PACKET_STAGES_ALREADY_RECORDED",
            f"stage {row['stage']} already carries a stage record file",
        )
    require(
        state["completedStageCount"] == 0 and state["nextStage"] == stages[0],
        "PACKET_STAGES_ALREADY_RECORDED",
        "the packet does not begin at zero of sixteen",
    )

    # ---- configuration --------------------------------------------------------------
    config = read_json_file(packet / files["config"], code="PACKET_CONFIG_INVALID", label="packet configuration")
    exact_keys(config, packet_law["configKeys"], "PACKET_CONFIG_INVALID", "packet configuration")
    require(
        config["schema"] == packet_law["configSchema"],
        "PACKET_CONFIG_INVALID",
        "packet configuration schema differs",
    )
    require(
        config["campaignLabel"] == campaign_label,
        "PACKET_CAMPAIGN_BINDING_INVALID",
        "the packet configuration names another campaign",
    )
    require(config["authority"] == AUTHORITY, "AUTHORITY_WIDENED", "packet configuration grants authority")
    canonical = assert_sha256(
        config["canonicalMissionStateDigest"], "PACKET_CONFIG_INVALID", "canonical mission state digest"
    )

    # ---- successor contract ----------------------------------------------------------
    contract = read_json_file(
        packet / files["successorContract"], code="SUCCESSOR_CONTRACT_INVALID", label="successor contract"
    )
    exact_keys(contract, lineage_law["successorContractKeys"], "SUCCESSOR_CONTRACT_INVALID", "successor contract")
    require(
        contract["schema"] == lineage_law["successorContractSchema"],
        "SUCCESSOR_CONTRACT_INVALID",
        "successor contract schema differs",
    )
    contract_id = assert_identity(
        contract,
        lineage_law["successorContractIdKey"],
        lineage_law["successorContractIdPrefix"],
        "SUCCESSOR_CONTRACT_INVALID",
        "successor contract",
    )
    require(contract["authority"] == AUTHORITY, "AUTHORITY_WIDENED", "successor contract grants authority")
    campaign_id = assert_content_id(contract["campaignId"], "SUCCESSOR_CONTRACT_INVALID", "campaign identity")
    require(
        contract["successorPacketId"] == packet_id
        and contract["successorPacketProfileId"] == packet_law["packetProfileId"]
        and contract["predecessorPacketProfileId"] == packet_law["predecessorPacketProfileId"]
        and contract["campaignLabel"] == campaign_label
        and contract["canonicalMissionStateDigest"] == canonical
        and contract["admissionProfileId"] == profile["admissionProfile"]["profileId"],
        "SUCCESSOR_CONTRACT_BINDING_INVALID",
        "the successor contract does not bind this packet, campaign, canonical state and admitted profile",
    )
    predecessor_packet_id = assert_content_id(
        contract["predecessorPacketId"], "SUCCESSOR_CONTRACT_INVALID", "predecessor packet identity"
    )
    require(
        predecessor_packet_id != packet_id,
        "SUCCESSOR_CONTRACT_BINDING_INVALID",
        "the successor contract names itself as its own predecessor",
    )

    # ---- lineage referents, measured -------------------------------------------------
    predecessor_marker = read_json_file(
        packet / lineage_law["predecessorMarkerFile"],
        code="SUCCESSOR_LINEAGE_REFERENT_INVALID",
        label="predecessor packet marker",
    )
    exact_keys(
        predecessor_marker,
        packet_law["markerKeys"],
        "SUCCESSOR_LINEAGE_REFERENT_INVALID",
        "predecessor packet marker",
    )
    predecessor_marker_id = assert_identity(
        predecessor_marker,
        packet_law["markerIdKey"],
        packet_law["markerIdPrefix"],
        "SUCCESSOR_LINEAGE_REFERENT_INVALID",
        "predecessor packet marker",
    )
    require(
        predecessor_marker["packetId"] == predecessor_packet_id
        and predecessor_marker["packetProfileId"] == packet_law["predecessorPacketProfileId"]
        and predecessor_marker["physicalProfileId"] == packet_law["physicalProfileId"]
        and predecessor_marker["campaignLabel"] == campaign_label,
        "SUCCESSOR_LINEAGE_BINDING_INVALID",
        "the measured predecessor packet is not the predecessor this contract names",
    )
    require(
        predecessor_marker["authority"] == AUTHORITY,
        "AUTHORITY_WIDENED",
        "predecessor packet marker grants authority",
    )
    predecessor_state = read_json_file(
        packet / lineage_law["predecessorStateFile"],
        code="SUCCESSOR_LINEAGE_REFERENT_INVALID",
        label="predecessor packet state",
    )
    exact_keys(
        predecessor_state, packet_law["stateKeys"], "SUCCESSOR_LINEAGE_REFERENT_INVALID", "predecessor packet state"
    )
    predecessor_state_id = assert_identity(
        predecessor_state,
        packet_law["stateIdKey"],
        packet_law["stateIdPrefix"],
        "SUCCESSOR_LINEAGE_REFERENT_INVALID",
        "predecessor packet state",
    )
    require(
        predecessor_state["packetId"] == predecessor_packet_id
        and predecessor_state["campaignLabel"] == campaign_label,
        "SUCCESSOR_LINEAGE_BINDING_INVALID",
        "the measured predecessor state names another packet or campaign than its marker",
    )
    for field in ("packetProfileId", "physicalProfileId"):
        require(
            predecessor_state[field] == predecessor_marker[field],
            "PACKET_PROFILE_SUCCESSION_SPLIT",
            f"predecessor marker and state name different {field} values",
        )
    require(
        list(predecessor_state["stageDenominator"]) == stages,
        "SUCCESSOR_LINEAGE_BINDING_INVALID",
        "the measured predecessor carries another stage denominator",
    )

    handoff = read_json_file(
        packet / lineage_law["handoffFile"],
        code="SUCCESSOR_LINEAGE_REFERENT_INVALID",
        label="packet handoff receipt",
    )
    exact_keys(
        handoff, lineage_law["handoffKeys"], "SUCCESSOR_LINEAGE_REFERENT_INVALID", "packet handoff receipt"
    )
    require(
        handoff["schema"] == lineage_law["handoffSchema"],
        "SUCCESSOR_LINEAGE_REFERENT_INVALID",
        "packet handoff receipt schema differs",
    )
    handoff_id = assert_identity(
        handoff,
        lineage_law["handoffIdKey"],
        lineage_law["handoffIdPrefix"],
        "SUCCESSOR_LINEAGE_REFERENT_INVALID",
        "packet handoff receipt",
    )
    require(handoff["authority"] == AUTHORITY, "AUTHORITY_WIDENED", "packet handoff receipt grants authority")
    require(
        handoff_id == contract["packetHandoffId"],
        "SUCCESSOR_LINEAGE_BINDING_INVALID",
        "the measured handoff is not the handoff the successor contract names",
    )
    require(
        handoff["campaignId"] == campaign_id
        and handoff["campaignLabel"] == campaign_label
        and handoff["predecessorPacketId"] == predecessor_packet_id
        and handoff["successorPacketId"] == packet_id
        and handoff["predecessorPacketProfileId"] == packet_law["predecessorPacketProfileId"]
        and handoff["successorPacketProfileId"] == packet_law["packetProfileId"]
        and handoff["canonicalMissionStateDigest"] == canonical,
        "SUCCESSOR_LINEAGE_BINDING_INVALID",
        "the measured handoff does not bind this predecessor, successor, campaign and canonical state",
    )

    stored_source = read_json_file(
        packet / lineage_law["sourceSetFile"],
        code="SUCCESSOR_LINEAGE_REFERENT_INVALID",
        label="successor source set",
    )
    require(
        stored_source.get("schema") == lineage_law["sourceSetSchema"],
        "SUCCESSOR_LINEAGE_REFERENT_INVALID",
        "successor source set schema differs",
    )
    declared = stored_source.get("members")
    require(
        isinstance(declared, list) and declared,
        "SUCCESSOR_LINEAGE_REFERENT_INVALID",
        "the successor source set declares no measured members",
    )
    relative_members = []
    for row in declared:
        require(
            isinstance(row, Mapping) and isinstance(row.get("relativePath"), str),
            "SUCCESSOR_LINEAGE_REFERENT_INVALID",
            "successor source set member row is not a measured member",
        )
        relative_members.append(row["relativePath"])
    require(
        len(set(relative_members)) == len(relative_members),
        "SUCCESSOR_LINEAGE_REFERENT_INVALID",
        "the successor source set repeats a member path",
    )
    # Every member this transaction declares must actually be carried by the packet.
    require(
        sorted(relative_members) == sorted(profile["successorSourceMembers"].values()),
        "SUCCESSOR_SOURCE_MEMBER_DENOMINATOR_INVALID",
        "the packet's source set is not the declared successor source member denominator",
    )
    require(
        len(relative_members) == profile["successorSourceMemberDenominator"],
        "SUCCESSOR_SOURCE_MEMBER_DENOMINATOR_INVALID",
        "the packet's source member count differs from the declared denominator",
    )
    measured_source = measure_source_set(
        packet / lineage_law["sourceRoot"],
        relative_members,
        schema=lineage_law["sourceSetSchema"],
        profile_id=packet_law["packetProfileId"],
        claim_boundary=lineage_law["sourceSetClaimBoundary"],
        id_key=lineage_law["sourceSetIdKey"],
        id_prefix=lineage_law["sourceSetIdPrefix"],
        code="SUCCESSOR_LINEAGE_REFERENT_INVALID",
        label="successor source set",
    )
    require(
        dict(stored_source) == measured_source,
        "SUCCESSOR_LINEAGE_BINDING_INVALID",
        "the stored successor source set does not reproduce from its measured member bytes",
    )
    require(
        measured_source[lineage_law["sourceSetIdKey"]] == contract["successorSourceSetId"],
        "SUCCESSOR_LINEAGE_BINDING_INVALID",
        "the measured successor source set is not the source set the successor contract names",
    )

    source_admission_law = profile["sourceAdmission"]
    source_admission = read_json_file(
        packet / lineage_law["sourceAdmissionFile"],
        code="SOURCE_ADMISSION_RECEIPT_INVALID",
        label="packet-carried source-admission receipt",
    )
    exact_keys(
        source_admission,
        source_admission_law["receiptKeys"],
        "SOURCE_ADMISSION_RECEIPT_INVALID",
        "packet-carried source-admission receipt",
    )
    source_admission_id = assert_identity(
        source_admission,
        source_admission_law["idKey"],
        source_admission_law["idPrefix"],
        "SOURCE_ADMISSION_IDENTITY_INVALID",
        "packet-carried source-admission receipt",
    )
    require(
        source_admission["schema"] == source_admission_law["schema"]
        and source_admission["status"] == "PASS"
        and source_admission["bootstrapAuthenticated"] is True
        and source_admission["workingTreeBytesTrusted"] is False
        and source_admission["authority"] == AUTHORITY,
        "SOURCE_ADMISSION_RECEIPT_INVALID",
        "packet-carried source admission is not a bootstrap-authenticated no-working-tree receipt",
    )
    object_format = source_admission.get("gitObjectFormat")
    object_id_lengths = source_admission_law["gitObjectIdLengths"]
    require_git_object_id(
        source_admission.get("sourceCommit"), object_format, object_id_lengths,
        code="SOURCE_COMMIT_INVALID", label="source admission commit",
    )
    require_git_object_id(
        source_admission.get("sourceTree"), object_format, object_id_lengths,
        code="SOURCE_TREE_INVALID", label="source admission tree",
    )
    require_git_object_id(
        source_admission.get("profileGitBlob"), object_format, object_id_lengths,
        code="SOURCE_PROFILE_BLOB_INVALID", label="source admission profile blob",
    )
    source_rows = source_admission["members"]
    require(
        isinstance(source_rows, list)
        and len(source_rows) == source_admission["memberCount"] == profile["successorSourceMemberDenominator"],
        "SOURCE_ADMISSION_MEMBER_DENOMINATOR_INVALID",
        "packet-carried source admission member denominator differs",
    )
    expected_mapping = sorted(profile["successorSourceMembers"].items())
    observed_mapping = [(row.get("repositoryPath"), row.get("packetPath")) for row in source_rows]
    require(observed_mapping == expected_mapping, "SOURCE_ADMISSION_MEMBER_SUBSTITUTED", "packet-carried source admission mapping differs")
    measured_by_packet_path = {row["relativePath"]: row for row in measured_source["members"]}
    for row in source_rows:
        exact_keys(row, source_admission_law["memberKeys"], "SOURCE_ADMISSION_RECEIPT_INVALID", "source-admission member row")
        require_git_object_id(
            row.get("gitBlob"), object_format, object_id_lengths,
            code="SOURCE_BLOB_IDENTITY_INVALID", label="source admission member blob",
        )
        measured_row = measured_by_packet_path.get(row["packetPath"])
        require(
            measured_row is not None
            and measured_row["sha256"] == row["sha256"]
            and measured_row["bytes"] == row["bytes"],
            "SOURCE_ADMISSION_MEMBER_BINDING_INVALID",
            f"packet source member differs from admitted Git blob: {row['packetPath']}",
        )
    require(
        source_admission["successorSourceSetId"] == measured_source[lineage_law["sourceSetIdKey"]],
        "SOURCE_ADMISSION_SOURCE_SET_MISMATCH",
        "packet-carried source admission names another successor source set",
    )

    # ---- the source set never claims the frozen runtime ------------------------------
    require(
        set(profile["frozenRuntimeMembers"]).isdisjoint(set(profile["successorSourceMembers"])),
        "SOURCE_CLAIMS_FROZEN_RUNTIME",
        "the successor source set claims a frozen packet-runtime member as its own",
    )

    checks = [
        "successor-packet-marker-identity",
        "successor-packet-state-identity",
        "packet-identity-derived-from-succession",
        "marker-state-profile-agreement",
        "frozen-predecessor-packet-refused",
        "packet-configured-and-unrecorded",
        "no-stage-record-file-present",
        "successor-contract-identity",
        "successor-contract-binding-exact",
        "predecessor-packet-referent-measured",
        "packet-handoff-referent-measured",
        "successor-source-set-members-measured",
        "successor-source-member-denominator-exact",
        "source-admission-receipt-identity",
        "source-admission-git-blob-members-bound",
        "frozen-packet-runtime-unclaimed",
        "admitted-profile-canonical-digest-pinned",
        "authority-none",
    ]
    measured_verifier_sha256 = None
    if measured_verifier_bytes is not None:
        measured_verifier_sha256 = sha256_bytes(measured_verifier_bytes)
        stored = next(
            (
                row
                for row in measured_source["members"]
                if row["relativePath"].endswith("verify_stc_mary_successor_packet.py")
            ),
            None,
        )
        require(
            stored is not None and stored["sha256"] == measured_verifier_sha256,
            "MEASURED_VERIFIER_MEMBER_BINDING_INVALID",
            "the executing verifier bytes are not the source member this packet carries",
        )
        checks.append("measured-verifier-member-binding")

    body = {
        "schema": RECEIPT_SCHEMA,
        "status": "PASS",
        "profileId": PROFILE_ID,
        "admissionProfileId": profile["admissionProfile"]["profileId"],
        "admissionProfileCanonicalSha256": profile["admissionProfile"]["canonicalSha256"],
        "campaignId": campaign_id,
        "campaignLabel": campaign_label,
        "canonicalMissionStateDigest": canonical,
        "packetId": packet_id,
        "packetProfileId": packet_law["packetProfileId"],
        "packetMarkerId": marker_id,
        "packetStateId": state_id,
        "packetMarkerProfileId": marker["packetProfileId"],
        "packetStateProfileId": state["packetProfileId"],
        "predecessorPacketId": predecessor_packet_id,
        "predecessorPacketProfileId": packet_law["predecessorPacketProfileId"],
        "predecessorPacketMarkerId": predecessor_marker_id,
        "predecessorPacketStateId": predecessor_state_id,
        "successorContractId": contract_id,
        "packetHandoffId": handoff_id,
        "sourceAdmissionId": source_admission_id,
        "sourceCommit": source_admission["sourceCommit"],
        "sourceTree": source_admission["sourceTree"],
        "successorSourceSetId": measured_source[lineage_law["sourceSetIdKey"]],
        "successorSourceMemberCount": measured_source["memberCount"],
        "stageDenominator": len(stages),
        "completedStageCount": 0,
        "sealed": False,
        "stageRecordsPresent": 0,
        "packetMutated": False,
        "stagesRecordedByThisVerifier": 0,
        "evidenceAdmitted": 0,
        "humanPrincipalsAuthenticated": 0,
        "physicalEstateQualified": False,
        "representativeOperatorQualified": False,
        "fieldNetworkQualified": False,
        "operationalC2Qualified": False,
        "productionLatticeQualified": False,
        "missionAuthorityGranted": False,
        "commandAuthorityGranted": False,
        "checks": checks,
        "measuredVerifierSha256": measured_verifier_sha256,
        "bootstrapAuthenticated": False,
        "authority": AUTHORITY,
        "claimBoundary": CLAIM_BOUNDARY,
    }
    receipt = {**body, RECEIPT_ID_KEY: content_id(RECEIPT_ID_PREFIX, body)}
    assert_no_private_material(receipt, code="VERIFICATION_PRIVATE_MATERIAL", label="successor packet verification")
    return receipt


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def refusal_document(code: str, message: str) -> dict[str, Any]:
    return {
        "schema": RECEIPT_SCHEMA,
        "status": "REFUSED",
        "code": code,
        "message": message,
        "packetMutated": False,
        "stagesRecordedByThisVerifier": 0,
        "bootstrapAuthenticated": False,
        "authority": AUTHORITY,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Independently verify one compiled 0.2 successor packet")
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        output = None
        if args.out is not None:
            output = validate_lexical_coordinate(args.out, label="receipt output", code="RECEIPT_PATH_INVALID")
            if is_within(output, Path(os.path.abspath(os.fspath(args.packet)))):
                fail("RECEIPT_INSIDE_MEASURED_SURFACE", "the verification may not be written inside the packet")
            if output.exists():
                fail("RECEIPT_OUTPUT_EXISTS", "verification output must not already exist")
        receipt = verify_successor_packet(
            packet=args.packet,
            profile_path=args.profile,
            repository=args.repository_root,
            measured_verifier_bytes=globals().get("_STC_MARY_SUCCESSOR_MEASURED_VERIFIER_BYTES"),
        )
        data = canonical_json_bytes(receipt)
        if output is None:
            sys.stdout.buffer.write(data)
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(data)
        return 0
    except SuccessorPacketError as exc:
        sys.stdout.buffer.write(canonical_json_bytes(refusal_document(exc.code, str(exc))))
        return 1
    except (OSError, ValueError) as exc:
        sys.stdout.buffer.write(canonical_json_bytes(refusal_document("VERIFIER_FILESYSTEM_ERROR", str(exc))))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
