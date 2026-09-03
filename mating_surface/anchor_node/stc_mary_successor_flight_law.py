"""Shared construction law for the STC MARY successor packet flight 01 source set.

This module is the *producer* side of the transaction. The compiler, the successor
packet runtime, the admission-driven orchestrator and the seal adapter all build objects
through it, so one canonical identity algorithm and one profile reading are used
everywhere a successor object is created.

It is deliberately NOT imported by the three verifiers. ``verify_stc_mary_successor_packet``,
``verify_stc_mary_successor_pre_seal_closure`` and ``verify_stc_mary_successor_post_seal_closure``
re-implement every primitive they need, so a defect in this module cannot silently
authenticate the objects it produced.

It never imports the frozen packet runtime, never records a stage on its own behalf, and
grants no authority.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

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
MAX_EVIDENCE_BYTES = 64 * 1024 * 1024
MAX_TEXT_FIELD = 8192
MAX_UNIX_NS = 4_102_444_800_000_000_000  # 2100-01-01, a bounded clock domain


class SuccessorFlightError(RuntimeError):
    """One coded, bounded refusal. It carries no private coordinate."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def fail(code: str, message: str) -> None:
    raise SuccessorFlightError(code, message)


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        fail(code, message)


def require_supported_python() -> None:
    import sys

    require(
        sys.version_info[:2] >= MINIMUM_PYTHON,
        "PYTHON_RUNTIME_UNSUPPORTED",
        f"this source requires Python {MINIMUM_PYTHON[0]}.{MINIMUM_PYTHON[1]} or newer",
    )


def require_git_object_id(
    value: Any,
    object_format: Any,
    lengths: Mapping[str, Any],
    *,
    code: str,
    label: str,
) -> str:
    """Require one lowercase full Git object ID under the receipt's declared format."""
    require(
        isinstance(object_format, str)
        and isinstance(lengths, Mapping)
        and set(lengths) == {"sha1", "sha256"}
        and lengths.get("sha1") == 40
        and lengths.get("sha256") == 64
        and object_format in lengths,
        code,
        f"{label} object-format law differs",
    )
    expected = lengths[object_format]
    require(
        isinstance(value, str)
        and len(value) == expected
        and all(character in "0123456789abcdef" for character in value),
        code,
        f"{label} is not one exact full {object_format} object identifier",
    )
    return value


# --------------------------------------------------------------------------------
# canonical identity
# --------------------------------------------------------------------------------


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


def sign(body: Mapping[str, Any], id_key: str, prefix: str) -> dict[str, Any]:
    """Return the body plus its own content identity under ``id_key``."""
    require(id_key not in body, "OBJECT_ALREADY_SIGNED", f"body already carries {id_key}")
    return {**body, id_key: content_id(prefix, body)}


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
    require(
        isinstance(value, str) and 0 < len(value) <= maximum,
        code,
        f"{label} is not bounded text",
    )
    return value


def assert_unix_ns(value: Any, code: str, label: str) -> int:
    require(
        isinstance(value, int) and not isinstance(value, bool) and 0 < value <= MAX_UNIX_NS,
        code,
        f"{label} is not a bounded Unix nanosecond coordinate",
    )
    return value


# --------------------------------------------------------------------------------
# bounded filesystem reads and canonical writes
# --------------------------------------------------------------------------------


def coordinate_component_is_link(path: Path, *, code: str, label: str) -> bool:
    try:
        return path.is_symlink() or (os.name == "nt" and path.exists() and _is_reparse_point(path))
    except OSError as exc:
        fail(code, f"{label} could not be inspected: {exc}")
        raise


def _is_reparse_point(path: Path) -> bool:
    try:
        return bool(path.lstat().st_file_attributes & 0x400)  # FILE_ATTRIBUTE_REPARSE_POINT
    except (OSError, AttributeError):
        return False


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


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


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


def read_json_bytes(data: bytes, *, code: str, label: str) -> Mapping[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(code, f"{label} is not valid UTF-8 JSON: {exc}")
        raise
    require(isinstance(value, Mapping), code, f"{label} must be a JSON object")
    return value


def read_json_file(path: Path, *, code: str, label: str) -> Mapping[str, Any]:
    return read_json_bytes(
        read_bounded_bytes(path, MAX_JSON_BYTES, code=code, label=label), code=code, label=label
    )


def write_canonical_json(path: Path, value: Any) -> bytes:
    """Write one object as canonical JSON with LF endings, and return the bytes.

    Every object this source set produces is written this way, so a reader on any
    platform measures the same bytes the writer measured.
    """
    data = canonical_json_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(data)
    return data


# --------------------------------------------------------------------------------
# profiles
# --------------------------------------------------------------------------------


def load_profile(path: Path) -> Mapping[str, Any]:
    profile = read_json_file(path, code="PROFILE_UNREADABLE", label="successor flight profile")
    require(profile.get("schema") == PROFILE_SCHEMA, "PROFILE_INVALID", "successor flight profile schema differs")
    require(profile.get("profileId") == PROFILE_ID, "PROFILE_INVALID", "successor flight profile identity differs")
    require(profile.get("authority") == AUTHORITY, "AUTHORITY_WIDENED", "successor flight profile grants authority")
    return profile


def load_admission_profile(repository_root: Path, profile: Mapping[str, Any]) -> Mapping[str, Any]:
    """Read the admitted packet-evidence-admission profile through this profile's pin.

    The successor contract does not restate the Stage 16 decision surface. It binds the
    admitted profile by canonical digest and reads the surface from it, so a successor
    packet can never carry a Stage 16 contract the admission gate did not admit.
    """
    law = profile["admissionProfile"]
    path = repository_root / law["relativePath"]
    admission = read_json_file(path, code="ADMISSION_PROFILE_UNREADABLE", label="admission profile")
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
    require(
        admission["successorPacketProfileId"] == profile["packet"]["packetProfileId"]
        and admission["predecessorPacketProfileId"] == profile["packet"]["predecessorPacketProfileId"]
        and admission["predecessorPhysicalProfileId"] == profile["packet"]["physicalProfileId"],
        "ADMISSION_PROFILE_BINDING_INVALID",
        "the admitted profile names another packet-profile succession than this source",
    )
    denominator = admission["denominator"]
    ours = profile["denominator"]
    require(
        denominator["stageDenominator"] == ours["stageDenominator"]
        and denominator["evidenceRoleDenominator"] == ours["evidenceRoleDenominator"]
        and denominator["nonHumanEvidenceRoleCount"] == ours["nonHumanEvidenceRoleCount"]
        and denominator["humanStatementRoleCount"] == ours["humanStatementRoleCount"]
        and denominator["stageConfirmationDenominator"] == ours["stageConfirmationDenominator"],
        "ADMISSION_PROFILE_BINDING_INVALID",
        "the admitted denominator differs from the denominator this source declares",
    )
    # The recorded terminal denominator this source declares is not a restatement: it is
    # derived from the admitted per-stage terminals and required to agree. A profile that
    # simply asserted 15 / 1 / 0 could drift away from the stages it describes.
    require(
        dict(ours["recordedTerminalCounts"]) == recorded_terminal_counts(admission),
        "ADMISSION_PROFILE_BINDING_INVALID",
        "the declared recorded-terminal denominator is not the one the admitted stages derive",
    )
    return admission


def stage_sequence(admission: Mapping[str, Any]) -> list[str]:
    return list(admission["stageSequence"])


def required_terminals(admission: Mapping[str, Any]) -> dict[str, str]:
    return {stage: admission["stages"][stage]["requiredTerminal"] for stage in admission["stageSequence"]}


# The scope string the admitted gate computes a stage's complete role root under. The
# non-human scope is the gate's own two-pass concern and never reaches a stage record.
ALL_ROLES_SCOPE = "all-admitted-evidence-roles"


def stage_evidence_root(
    admission: Mapping[str, Any], *, scope: str, sequence: int, stage: str, rows: Sequence[Mapping[str, Any]]
) -> str:
    """Recompute one stage evidence-admission root the way the admitted gate computes it.

    The producer needs this because a stage record may no longer *copy* the root the
    admission receipt published. It must reconstruct the root from the bodies the packet
    actually carries and prove the two agree; a copied root says nothing about the files
    beside it. The six fields, the sort key and the scope string belong to the admitted
    profile, so a change to any of them moves that profile's canonical digest and the pin
    refuses before this function is ever reached.
    """
    return content_id(
        admission["digests"]["stageEvidenceRootPrefix"],
        {
            "scope": scope,
            "sequence": sequence,
            "stage": stage,
            "roles": sorted(
                (
                    {
                        "evidenceRole": row["evidenceRole"],
                        "provenanceClass": row["provenanceClass"],
                        "evidenceClass": row["evidenceClass"],
                        "bodyContentId": row["bodyContentId"],
                        "bodySha256": row["bodySha256"],
                        "bodyBytes": row["bodyBytes"],
                    }
                    for row in rows
                ),
                key=lambda row: row["evidenceRole"],
            ),
        },
    )


def recorded_terminal_counts(admission: Mapping[str, Any]) -> dict[str, int]:
    counts = {"PASS": 0, "HUMAN_REQUIRED": 0, "REFUSED": 0}
    for terminal in required_terminals(admission).values():
        require(terminal in counts, "STAGE_TERMINAL_INVALID", f"unknown stage terminal {terminal}")
        counts[terminal] += 1
    return counts


# --------------------------------------------------------------------------------
# measured source sets
# --------------------------------------------------------------------------------


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
    """Measure one exact source set.

    This reproduces the admitted admission gate's algorithm byte for byte, because the
    set this produces is the object that gate re-measures. It is implemented here rather
    than imported so the producer never depends on the verifier that judges it.
    """
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
# packet coordinates
# --------------------------------------------------------------------------------


def packet_id_for(
    *, packet_profile_id: str, physical_profile_id: str, campaign_label: str, stages: Sequence[str]
) -> str:
    """Derive one packet identity.

    This is the frozen derivation, unchanged. Only ``packetProfileId`` differs between a
    0.1 predecessor and its 0.2 successor, which is exactly why the two identities are
    distinct and why the successor can name its predecessor without ambiguity.
    """
    return content_id(
        "stcmaryprivateflightpacket1",
        {
            "packetProfileId": packet_profile_id,
            "physicalProfileId": physical_profile_id,
            "campaignLabel": campaign_label,
            "stageSequence": list(stages),
        },
    )


def stage_directory_name(sequence: int, stage: str) -> str:
    return f"{sequence:02d}-{stage}"


def stage_state_rows(stages: Sequence[str]) -> list[dict[str, Any]]:
    return [
        {
            "sequence": index + 1,
            "stage": stage,
            "status": "unrecorded",
            "draftPath": f"{stage_directory_name(index + 1, stage)}/stage-attestation.json",
            "evidenceDirectory": f"{stage_directory_name(index + 1, stage)}/evidence",
            "evidenceCount": 0,
            "recordDigest": None,
        }
        for index, stage in enumerate(stages)
    ]


def build_packet_marker(
    *, profile: Mapping[str, Any], campaign_label: str, packet_id: str, claim_boundary: str
) -> dict[str, Any]:
    packet_law = profile["packet"]
    body = {
        "schema": packet_law["markerSchema"],
        "packetProfileId": packet_law["packetProfileId"],
        "physicalProfileId": packet_law["physicalProfileId"],
        "campaignLabel": campaign_label,
        "packetId": packet_id,
        "authority": AUTHORITY,
        "claimBoundary": claim_boundary,
    }
    return sign(body, packet_law["markerIdKey"], packet_law["markerIdPrefix"])


def build_packet_state(
    *,
    profile: Mapping[str, Any],
    marker: Mapping[str, Any],
    stages: Sequence[str],
    rows: Sequence[Mapping[str, Any]],
    configuration_state: str,
    sealed: bool,
    sealed_disposition_id: str | None,
    claim_boundary: str,
) -> dict[str, Any]:
    packet_law = profile["packet"]
    completed = sum(1 for row in rows if row["status"] == "recorded")
    next_stage = next((row["stage"] for row in rows if row["status"] == "unrecorded"), None)
    body = {
        "schema": packet_law["stateSchema"],
        "packetId": marker["packetId"],
        "campaignLabel": marker["campaignLabel"],
        "packetProfileId": marker["packetProfileId"],
        "physicalProfileId": marker["physicalProfileId"],
        "configurationState": configuration_state,
        "stageDenominator": list(stages),
        "stages": [dict(row) for row in rows],
        "completedStageCount": completed,
        "nextStage": next_stage,
        "sealed": sealed,
        "sealedDispositionId": sealed_disposition_id,
        "authority": AUTHORITY,
        "claimBoundary": claim_boundary,
    }
    return sign(body, packet_law["stateIdKey"], packet_law["stateIdPrefix"])


def load_packet(profile: Mapping[str, Any], packet: Path) -> dict[str, Any]:
    """Read one successor packet's marker, state and configuration."""
    packet_law = profile["packet"]
    files = packet_law["files"]
    marker = read_json_file(packet / files["marker"], code="PACKET_MARKER_INVALID", label="packet marker")
    exact_keys(marker, packet_law["markerKeys"], "PACKET_MARKER_INVALID", "packet marker")
    assert_identity(
        marker, packet_law["markerIdKey"], packet_law["markerIdPrefix"], "PACKET_MARKER_INVALID", "packet marker"
    )
    require(
        marker["packetProfileId"] == packet_law["packetProfileId"],
        "PACKET_PROFILE_INVALID",
        "packet marker does not carry the successor packet profile",
    )
    state = read_json_file(packet / files["state"], code="PACKET_STATE_INVALID", label="packet state")
    exact_keys(state, packet_law["stateKeys"], "PACKET_STATE_INVALID", "packet state")
    assert_identity(
        state, packet_law["stateIdKey"], packet_law["stateIdPrefix"], "PACKET_STATE_INVALID", "packet state"
    )
    require(
        state["packetId"] == marker["packetId"]
        and state["packetProfileId"] == marker["packetProfileId"]
        and state["physicalProfileId"] == marker["physicalProfileId"]
        and state["campaignLabel"] == marker["campaignLabel"],
        "PACKET_PROFILE_SUCCESSION_SPLIT",
        "packet state and packet marker do not name one packet",
    )
    config = read_json_file(packet / files["config"], code="PACKET_CONFIG_INVALID", label="packet configuration")
    exact_keys(config, packet_law["configKeys"], "PACKET_CONFIG_INVALID", "packet configuration")
    require(
        config["campaignLabel"] == marker["campaignLabel"],
        "PACKET_CONFIG_INVALID",
        "packet configuration names another campaign",
    )
    assert_sha256(
        config["canonicalMissionStateDigest"], "PACKET_CONFIG_INVALID", "canonical mission state digest"
    )
    for row in (marker, state, config):
        require(row["authority"] == AUTHORITY, "AUTHORITY_WIDENED", "packet object grants authority")
    return {"marker": marker, "state": state, "config": config, "root": packet}
