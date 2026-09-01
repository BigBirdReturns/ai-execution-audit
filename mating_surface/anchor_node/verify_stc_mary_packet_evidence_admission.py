"""Source-authenticated pre-record packet evidence admission gate.

This object decides whether a set of proposed private stage-evidence bodies may be
placed before the named human principal, and, once that human has separately and
exactly decided, whether those bodies constitute an admissible packet denominator.

It is NOT the packet recorder and never becomes one. It does not import, execute, or
shell out to the frozen recorder module. It never writes into the packet,
never sets ``operatorConfirmed``, never records a stage, and never signs, generates, or
completes a named-human statement or a stage confirmation. It reads only, and it emits
one body-free admission receipt.

The gate exists because the frozen packet recorder authenticates the operator's own
Boolean, not the evidence. The recorder requires ``operatorConfirmed: true``, an
allowlisted evidence-class string, a bounded media type, and one to sixty-four
non-empty regular files. It then hashes those bytes. Content addressing proves the
bytes did not change after recording; it proves nothing about what the bytes are.
An untouched envelope template satisfies every mechanical check.

This gate closes that hole ahead of the recorder, without patching it:

* every proposed body is independently read, measured, and hashed here;
* every recognized body is parsed, exact-key validated, and its content identity is
  recomputed from its own body rather than trusted;
* every body is bound to the exact campaign, packet, stage, sequence, evidence role,
  canonical mission state, and provenance class the admission profile requires;
* every body must carry the exact semantic predicate denominator that role owes the
  stage observation it is offered to support;
* reused predecessor receipts are admitted only as ``reused_pre_stage_receipt``, only
  from the campaign's accepted predecessor graph, and only when they predate the
  current observation transaction;
* current observations must fall inside the declared observation transaction window
  and may not claim an uncaptured historical transition;
* named-human statements and stage confirmations are never produced here, and every
  machine, model, scheduler, verifier, tool, agent, automation, and packet-runner
  actor class is structurally incapable of satisfying the named-human actor class.

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

PROFILE_SCHEMA = "stc-mary/packet-evidence-admission-profile/1"
PROFILE_ID = "stc-mary/packet-evidence-admission@2"
PROFILE_CANONICAL_SHA256 = "0296e23f4ac15deb933420c5ff7121be3904add565b39bdc91808e0d8ded1f6d"
RECEIPT_SCHEMA = "stc-mary/packet-evidence-admission-receipt/1"
RECEIPT_ID_KEY = "admissionId"
RECEIPT_ID_PREFIX = "stcmarypacketevidenceadmission1"
SOURCE_SET_SCHEMA = "stc-mary/packet-evidence-admission-source-set/1"
SOURCE_SET_ID_PREFIX = "stcmarypacketevidenceadmissionsourceset1"
SOURCE_SET_CLAIM_BOUNDARY = (
    "Exact packet-evidence-admission source set. It identifies source bytes and grants no authority."
)

READY = "READY_FOR_NAMED_HUMAN_DECISION"
ADMISSIBLE = "ADMISSIBLE_FOR_PACKET_RECORDING"
HOLD = "HOLD"
REFUSED = "REFUSED"

AUTHORITY = "none"
MINIMUM_PYTHON = (3, 12)

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CONTENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*_[0-9a-f]{64}$")
RELATIVE_MEMBER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,255}$")

MAX_JSON_BYTES = 64 * 1024 * 1024
MAX_MEMBER_BYTES = 8 * 1024 * 1024
MAX_BODY_BYTES = 64 * 1024 * 1024
MAX_EVIDENCE_FILES_PER_STAGE = 64
MAX_ACCEPTED_PREDECESSOR_ROWS = 256
MAX_TEXT_FIELD = 8192
MAX_UNIX_NS = 4_102_444_800_000_000_000  # 2100-01-01, a bounded clock domain

# Scanned over string VALUES only, never over keys.
#
# The closed schemas this gate consumes are exact-key validated against their own
# admitted denominators, so a leaking key cannot survive that gate and a key-name scan
# buys nothing. A key-name scan is also actively wrong here: this product's own
# denominator carries keys such as `privateEvidenceBodiesCommittedToGit` and
# `evidenceAdmissionRoot`, whose lowercase forms contain `evidencebody` fragments.
# Scanning values keeps the real protection without that false refusal.
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
    "Body-free pre-record admission receipt for one configured, unrecorded private flight packet. "
    "It reports which proposed evidence bodies were independently measured, parsed, identity-checked, "
    "campaign-bound, stage-bound, and semantically sufficient, and it places the outstanding named-human "
    "statement forms and the exact stage decision records before the human principal. It records no "
    "packet stage, sets no operator confirmation, calls no packet recorder, signs no human statement, "
    "issues no stage confirmation, mutates no packet byte, and grants no physical-Estate, "
    "representative-operator, field-network, operational-C2, production-Lattice, mission, command, "
    "targeting, engagement, effector, or weapons qualification or authority."
)


class AdmissionError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def fail(code: str, message: str) -> None:
    raise AdmissionError(code, message)


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


def assert_bounded_text(value: Any, code: str, label: str, maximum: int = MAX_TEXT_FIELD) -> str:
    require(isinstance(value, str), code, f"{label} must be a string")
    stripped = value.strip()
    require(stripped != "" and len(value) <= maximum, code, f"{label} is empty or unbounded")
    return value


def assert_unix_ns(value: Any, code: str, label: str) -> int:
    require(
        isinstance(value, int) and not isinstance(value, bool) and 0 < value <= MAX_UNIX_NS,
        code,
        f"{label} is not a bounded Unix nanosecond coordinate",
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


def parse_json_bytes(data: bytes, *, code: str, label: str) -> Mapping[str, Any]:
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


def file_fence(path: Path, prefix: str, *, code: str, label: str) -> str:
    data = read_bounded_bytes(path, MAX_JSON_BYTES, code=code, label=label)
    return content_id(prefix, {"bytes": len(data), "sha256": sha256_bytes(data)})


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
    raw = read_bounded_bytes(path, MAX_MEMBER_BYTES, code="PROFILE_UNREADABLE", label="admission profile")
    try:
        profile = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail("PROFILE_INVALID", f"admission profile is not valid UTF-8 JSON: {exc}")
        raise
    require(isinstance(profile, Mapping), "PROFILE_INVALID", "admission profile must be an object")
    require(profile.get("schema") == PROFILE_SCHEMA, "PROFILE_INVALID", "admission profile schema differs")
    require(profile.get("profileId") == PROFILE_ID, "PROFILE_INVALID", "admission profile identity differs")
    require(
        sha256_bytes(canonical_json_bytes(profile)) == PROFILE_CANONICAL_SHA256,
        "PROFILE_CANONICAL_DIGEST_INVALID",
        "admission profile canonical digest differs from the admitted profile",
    )
    return profile


# --------------------------------------------------------------------------------
# stage observation contract
# --------------------------------------------------------------------------------


def validate_observation(stage: str, contract: Mapping[str, Any], observation: Any) -> None:
    code = "STAGE_OBSERVATION_INVALID"
    label = f"{stage} observation"
    exact_keys(observation, contract["keys"], code, label)
    for key, expected in contract.get("requiredValues", {}).items():
        require(
            observation[key] == expected and type(observation[key]) is type(expected),
            code,
            f"{label} field {key} is not the exact value the stage requires",
        )
    for key in contract.get("contentIdFields", []):
        assert_content_id(observation[key], code, f"{label} {key}")
    for key in contract.get("sha256Fields", []):
        assert_sha256(observation[key], code, f"{label} {key}")
    for key in contract.get("boundedStringFields", []):
        assert_bounded_text(observation[key], code, f"{label} {key}", 256)
    for key, bounds in contract.get("integerFields", {}).items():
        value = observation[key]
        require(
            isinstance(value, int) and not isinstance(value, bool) and bounds[0] <= value <= bounds[1],
            code,
            f"{label} {key} is outside {bounds[0]}..{bounds[1]}",
        )
    for key, allowed in contract.get("enumFields", {}).items():
        require(observation[key] in allowed, code, f"{label} {key} is not an admitted value")
    for key, count in contract.get("uniqueStringArrayFields", {}).items():
        value = observation[key]
        require(isinstance(value, list) and len(value) == count, code, f"{label} {key} denominator differs")
        for row in value:
            assert_bounded_text(row, code, f"{label} {key} member", 256)
        require(len(set(value)) == count, code, f"{label} {key} contains duplicates")
    for key, allowed in contract.get("exactStringArrayFields", {}).items():
        require(observation[key] == list(allowed), code, f"{label} {key} denominator differs")
    for left, right in contract.get("distinctFieldPairs", []):
        require(observation[left] != observation[right], code, f"{label} {left} and {right} are not distinct")


# --------------------------------------------------------------------------------
# frozen packet surface, read only
# --------------------------------------------------------------------------------


def read_frozen_surface(
    *, workstation: Path, packet: Path, profile: Mapping[str, Any]
) -> dict[str, Any]:
    ws_law = profile["workstation"]
    packet_law = profile["packet"]

    require(
        workstation.is_dir()
        and not coordinate_component_is_link(workstation, code="WORKSTATION_ROOT_INVALID", label="workstation"),
        "WORKSTATION_ROOT_INVALID",
        "workstation root is not a regular non-linked directory",
    )
    require(
        packet.is_dir() and not coordinate_component_is_link(packet, code="PACKET_ROOT_INVALID", label="packet root"),
        "PACKET_ROOT_INVALID",
        "packet root is not a regular non-linked directory",
    )

    marker = read_json_file(
        workstation / ws_law["markerFile"], code="WORKSTATION_MARKER_INVALID", label="workstation marker"
    )
    exact_keys(marker, ws_law["markerKeys"], "WORKSTATION_MARKER_INVALID", "workstation marker")
    require(
        marker["schema"] == ws_law["markerSchema"],
        "WORKSTATION_MARKER_INVALID",
        "workstation marker schema differs",
    )
    require(
        marker["profileId"] == ws_law["conductorProfileId"],
        "WORKSTATION_MARKER_INVALID",
        "workstation marker names another conductor profile",
    )
    require(marker["authority"] == AUTHORITY, "AUTHORITY_WIDENED", "workstation marker grants authority")
    assert_identity(
        marker, ws_law["markerIdKey"], ws_law["markerIdPrefix"], "WORKSTATION_MARKER_ID_INVALID", "workstation marker"
    )
    campaign_id = assert_content_id(marker["campaignId"], "WORKSTATION_MARKER_INVALID", "campaign identity")
    campaign_label = assert_bounded_text(
        marker["campaignLabel"], "WORKSTATION_MARKER_INVALID", "campaign label", 256
    )

    packet_marker = read_json_file(
        packet / packet_law["markerFile"], code="PACKET_MARKER_INVALID", label="packet marker"
    )
    exact_keys(packet_marker, packet_law["markerKeys"], "PACKET_MARKER_INVALID", "packet marker")
    require(
        packet_marker["schema"] == packet_law["markerSchema"], "PACKET_MARKER_INVALID", "packet marker schema differs"
    )
    require(packet_marker["authority"] == AUTHORITY, "AUTHORITY_WIDENED", "packet marker grants authority")
    assert_identity(
        packet_marker,
        packet_law["markerIdKey"],
        packet_law["markerIdPrefix"],
        "PACKET_MARKER_ID_INVALID",
        "packet marker",
    )
    require(
        packet_marker["campaignLabel"] == campaign_label,
        "PACKET_CAMPAIGN_BINDING_INVALID",
        "packet marker belongs to another campaign than the frozen workstation",
    )
    # The successor boundary is runtime law, not profile prose. The frozen predecessor
    # packet cannot satisfy stage 16 truthfully, so this gate refuses to govern it at all
    # rather than returning a positive terminal for a packet it has declared out of scope.
    succession = profile["sourceSuccession"]
    require(
        succession["directFrozenPacketApplication"] is False,
        "PROFILE_INVALID",
        "admission profile claims direct applicability to the frozen predecessor packet",
    )
    require(
        packet_marker["packetProfileId"] != profile["predecessorPacketProfileId"],
        succession["frozenPacketRefusalCode"],
        "this gate may not govern the frozen predecessor packet; its stage-16 observation "
        "contract cannot be satisfied truthfully before sealing",
    )
    require(
        packet_marker["packetProfileId"] == profile["successorPacketProfileId"]
        and packet_marker["physicalProfileId"] == profile["predecessorPhysicalProfileId"],
        "PACKET_MARKER_INVALID",
        "packet marker names another packet or physical-flight profile",
    )
    packet_id = assert_content_id(packet_marker["packetId"], "PACKET_MARKER_INVALID", "packet identity")

    state_path = packet / packet_law["stateFile"]
    state = read_json_file(state_path, code="PACKET_STATE_INVALID", label="packet state")
    exact_keys(state, packet_law["stateKeys"], "PACKET_STATE_INVALID", "packet state")
    require(state["schema"] == packet_law["stateSchema"], "PACKET_STATE_INVALID", "packet state schema differs")
    require(state["authority"] == AUTHORITY, "AUTHORITY_WIDENED", "packet state grants authority")
    assert_identity(
        state, packet_law["stateIdKey"], packet_law["stateIdPrefix"], "PACKET_STATE_ID_INVALID", "packet state"
    )
    require(
        state["packetId"] == packet_id and state["campaignLabel"] == campaign_label,
        "PACKET_CAMPAIGN_BINDING_INVALID",
        "packet state and packet marker name different packets or campaigns",
    )
    # The successor boundary has to hold at every object layer that carries a profile
    # identity. A root marker that declares the successor while the state still declares
    # the frozen predecessor is a decorated boundary, not a successor packet.
    agreement = profile["packetProfileAgreement"]
    require(
        agreement["requiredPacketProfileId"] == profile["successorPacketProfileId"]
        and agreement["requiredPhysicalProfileId"] == profile["predecessorPhysicalProfileId"]
        and succession["successorPacketProfileId"] == profile["successorPacketProfileId"]
        and succession["predecessorPacketProfileId"] == profile["predecessorPacketProfileId"],
        "PROFILE_INVALID",
        "admission profile does not name one single packet-profile succession",
    )
    require(
        state["packetProfileId"] != profile["predecessorPacketProfileId"],
        agreement["frozenPredecessorInStateRefusalCode"],
        "the packet state still declares the frozen predecessor packet profile; this gate may "
        "not govern the frozen predecessor packet at any object layer",
    )
    for field in agreement["agreedFields"]:
        require(
            state[field] == packet_marker[field],
            agreement["splitRefusalCode"],
            f"packet marker and packet state name different {field} values",
        )
    require(
        state["packetProfileId"] == agreement["requiredPacketProfileId"]
        and state["physicalProfileId"] == agreement["requiredPhysicalProfileId"],
        agreement["splitRefusalCode"],
        "packet state names another packet or physical-flight profile than the admitted succession",
    )
    require(
        state["configurationState"] == packet_law["requiredConfigurationState"],
        "PACKET_NOT_CONFIGURED",
        "packet is not in the configured pre-record state this gate admits",
    )
    require(
        state["sealed"] is packet_law["requiredSealed"] and state["sealedDispositionId"] is None,
        "PACKET_ALREADY_SEALED",
        "packet is already sealed and is no longer a pre-record surface",
    )
    require(
        state["completedStageCount"] == packet_law["requiredCompletedStageCount"],
        "PACKET_STAGES_ALREADY_RECORDED",
        "packet already carries recorded stages; this gate is a pre-record surface only",
    )
    require(
        list(state["stageDenominator"]) == list(profile["stageSequence"]),
        "PACKET_STAGE_DENOMINATOR_INVALID",
        "packet stage denominator differs from the admitted sixteen-stage denominator",
    )
    rows = state["stages"]
    require(
        isinstance(rows, list) and len(rows) == profile["denominator"]["stageDenominator"],
        "PACKET_STAGE_DENOMINATOR_INVALID",
        "packet stage state denominator differs",
    )
    for index, row in enumerate(rows):
        require(isinstance(row, Mapping), "PACKET_STATE_INVALID", "packet stage state row must be an object")
        require(
            row.get("stage") == profile["stageSequence"][index] and row.get("sequence") == index + 1,
            "PACKET_STAGE_DENOMINATOR_INVALID",
            "packet stage state order differs",
        )
        require(
            row.get("status") == "unrecorded"
            and row.get("recordDigest") is None
            and row.get("evidenceCount") == 0,
            "PACKET_STAGES_ALREADY_RECORDED",
            f"packet stage {row.get('stage')} already carries a recorded stage record",
        )

    config = read_json_file(
        packet / packet_law["configFile"], code="PACKET_CONFIG_INVALID", label="packet configuration"
    )
    exact_keys(config, packet_law["configKeys"], "PACKET_CONFIG_INVALID", "packet configuration")
    require(
        config["schema"] == packet_law["configSchema"], "PACKET_CONFIG_INVALID", "packet configuration schema differs"
    )
    require(
        config["campaignLabel"] == campaign_label,
        "PACKET_CAMPAIGN_BINDING_INVALID",
        "packet configuration names another campaign",
    )
    require(config["authority"] == AUTHORITY, "AUTHORITY_WIDENED", "packet configuration grants authority")
    canonical_mission_state_digest = assert_sha256(
        config["canonicalMissionStateDigest"], "PACKET_CONFIG_INVALID", "canonical mission state digest"
    )

    # ---- successor lineage, separately authenticated ------------------------
    contract_law = profile["successorContract"]
    contract = read_json_file(
        packet / contract_law["file"], code="SUCCESSOR_CONTRACT_INVALID", label="successor contract"
    )
    exact_keys(contract, contract_law["keys"], "SUCCESSOR_CONTRACT_INVALID", "successor contract")
    require(
        contract["schema"] == contract_law["schema"],
        "SUCCESSOR_CONTRACT_INVALID",
        "successor contract schema differs",
    )
    require(contract["authority"] == AUTHORITY, "AUTHORITY_WIDENED", "successor contract grants authority")
    successor_contract_id = assert_identity(
        contract,
        contract_law["idKey"],
        contract_law["idPrefix"],
        "SUCCESSOR_CONTRACT_ID_INVALID",
        "successor contract",
    )
    require(
        contract["admissionProfileId"] == PROFILE_ID,
        "SUCCESSOR_CONTRACT_INVALID",
        "successor contract names another admission profile",
    )
    require(
        contract["successorPacketId"] == packet_id
        and contract["successorPacketProfileId"] == profile["successorPacketProfileId"],
        "SUCCESSOR_CONTRACT_BINDING_INVALID",
        "successor contract does not bind this packet",
    )
    require(
        contract["predecessorPacketProfileId"] == profile["predecessorPacketProfileId"],
        "SUCCESSOR_CONTRACT_BINDING_INVALID",
        "successor contract names another predecessor packet profile",
    )
    predecessor_packet_id = assert_content_id(
        contract["predecessorPacketId"], "SUCCESSOR_CONTRACT_INVALID", "predecessor packet identity"
    )
    require(
        predecessor_packet_id != packet_id,
        "SUCCESSOR_CONTRACT_BINDING_INVALID",
        "successor contract names itself as its own predecessor",
    )
    require(
        contract["campaignId"] == campaign_id and contract["campaignLabel"] == campaign_label,
        "SUCCESSOR_CONTRACT_BINDING_INVALID",
        "successor contract belongs to another campaign",
    )
    require(
        contract["canonicalMissionStateDigest"] == canonical_mission_state_digest,
        "CANONICAL_MISSION_STATE_CHANGED",
        "successor contract names another canonical mission state than the configured packet",
    )
    packet_handoff_id = assert_content_id(
        contract["packetHandoffId"], "SUCCESSOR_CONTRACT_INVALID", "packet handoff identity"
    )
    successor_source_set_id = assert_content_id(
        contract["successorSourceSetId"], "SUCCESSOR_CONTRACT_INVALID", "successor source set identity"
    )
    assert_bounded_text(
        contract["claimBoundary"], "SUCCESSOR_CONTRACT_INVALID", "successor contract claim boundary"
    )
    require(
        contract["successorPacketProfileId"] == state["packetProfileId"]
        and contract["predecessorPacketProfileId"] == profile["predecessorPacketProfileId"],
        agreement["splitRefusalCode"],
        "successor contract and packet state do not name the same packet-profile succession",
    )

    # ---- lineage referents, measured rather than asserted --------------------
    # A content-addressed contract proves that its own bytes are self-consistent. It
    # proves nothing about the predecessor packet, the handoff, or the source set it
    # names. Each named coordinate is therefore supplied as an object, re-identified from
    # its own bytes, and bound to this campaign and this packet.
    lineage_law = contract_law["lineage"]
    referent_code = lineage_law["referentRefusalCode"]
    binding_code = lineage_law["bindingRefusalCode"]

    predecessor_law = lineage_law["predecessorPacket"]
    # The predecessor is read and never written. This gate has no write path at all, and
    # both predecessor objects join the before-and-after packet fence below.
    require(
        predecessor_law["mutationAllowed"] is False
        and succession["predecessorPacketMutationAllowed"] is False,
        "PROFILE_INVALID",
        "admission profile permits predecessor packet mutation",
    )
    predecessor_marker_path = packet / predecessor_law["markerFile"]
    predecessor_marker = read_json_file(
        predecessor_marker_path, code=referent_code, label="predecessor packet marker"
    )
    exact_keys(predecessor_marker, packet_law["markerKeys"], referent_code, "predecessor packet marker")
    require(
        predecessor_marker["schema"] == packet_law["markerSchema"],
        referent_code,
        "predecessor packet marker schema differs",
    )
    require(
        predecessor_marker["authority"] == AUTHORITY,
        "AUTHORITY_WIDENED",
        "predecessor packet marker grants authority",
    )
    predecessor_marker_id = assert_identity(
        predecessor_marker,
        packet_law["markerIdKey"],
        packet_law["markerIdPrefix"],
        referent_code,
        "predecessor packet marker",
    )
    require(
        predecessor_marker["packetId"] == predecessor_packet_id,
        binding_code,
        "the measured predecessor packet marker is not the predecessor the successor contract names",
    )
    require(
        predecessor_marker["packetProfileId"] == profile["predecessorPacketProfileId"]
        and predecessor_marker["physicalProfileId"] == profile["predecessorPhysicalProfileId"],
        binding_code,
        "the measured predecessor packet does not carry the frozen predecessor packet profile",
    )
    require(
        predecessor_marker["campaignLabel"] == campaign_label,
        binding_code,
        "the measured predecessor packet belongs to another campaign",
    )

    predecessor_state_path = packet / predecessor_law["stateFile"]
    predecessor_state = read_json_file(
        predecessor_state_path, code=referent_code, label="predecessor packet state"
    )
    exact_keys(predecessor_state, packet_law["stateKeys"], referent_code, "predecessor packet state")
    require(
        predecessor_state["schema"] == packet_law["stateSchema"],
        referent_code,
        "predecessor packet state schema differs",
    )
    require(
        predecessor_state["authority"] == AUTHORITY,
        "AUTHORITY_WIDENED",
        "predecessor packet state grants authority",
    )
    predecessor_state_id = assert_identity(
        predecessor_state,
        packet_law["stateIdKey"],
        packet_law["stateIdPrefix"],
        referent_code,
        "predecessor packet state",
    )
    require(
        predecessor_state["packetId"] == predecessor_packet_id
        and predecessor_state["campaignLabel"] == campaign_label,
        binding_code,
        "the measured predecessor packet state names another packet or campaign than its marker",
    )
    for field in agreement["agreedFields"]:
        require(
            predecessor_state[field] == predecessor_marker[field],
            agreement["splitRefusalCode"],
            f"predecessor packet marker and state name different {field} values",
        )
    require(
        list(predecessor_state["stageDenominator"]) == list(profile["stageSequence"]),
        binding_code,
        "the measured predecessor packet carries another stage denominator",
    )

    handoff_law = lineage_law["handoff"]
    handoff_path = packet / handoff_law["file"]
    handoff = read_json_file(handoff_path, code=referent_code, label="packet handoff receipt")
    exact_keys(handoff, handoff_law["keys"], referent_code, "packet handoff receipt")
    require(
        handoff["schema"] == handoff_law["schema"], referent_code, "packet handoff receipt schema differs"
    )
    require(
        handoff["authority"] == AUTHORITY, "AUTHORITY_WIDENED", "packet handoff receipt grants authority"
    )
    measured_handoff_id = assert_identity(
        handoff, handoff_law["idKey"], handoff_law["idPrefix"], referent_code, "packet handoff receipt"
    )
    require(
        measured_handoff_id == packet_handoff_id,
        binding_code,
        "the measured packet handoff receipt is not the handoff the successor contract names",
    )
    require(
        handoff["campaignId"] == campaign_id and handoff["campaignLabel"] == campaign_label,
        binding_code,
        "the measured packet handoff receipt belongs to another campaign",
    )
    require(
        handoff["predecessorPacketId"] == predecessor_packet_id
        and handoff["successorPacketId"] == packet_id
        and handoff["predecessorPacketProfileId"] == profile["predecessorPacketProfileId"]
        and handoff["successorPacketProfileId"] == profile["successorPacketProfileId"],
        binding_code,
        "the measured packet handoff receipt does not bind this predecessor and this successor packet",
    )
    require(
        handoff["canonicalMissionStateDigest"] == canonical_mission_state_digest,
        "CANONICAL_MISSION_STATE_CHANGED",
        "the measured packet handoff receipt names another canonical mission state",
    )
    assert_bounded_text(handoff["claimBoundary"], referent_code, "packet handoff claim boundary")

    source_law = lineage_law["successorSourceSet"]
    source_set_path = packet / source_law["file"]
    stored_source = read_json_file(source_set_path, code=referent_code, label="successor source set")
    require(
        stored_source.get("schema") == source_law["schema"],
        referent_code,
        "successor source set schema differs",
    )
    declared_members = stored_source.get("members")
    require(
        isinstance(declared_members, list) and len(declared_members) >= source_law["minimumMemberCount"],
        referent_code,
        "successor source set declares no measured members",
    )
    relative_members: list[str] = []
    for row in declared_members:
        require(
            isinstance(row, Mapping) and isinstance(row.get("relativePath"), str),
            referent_code,
            "successor source set member row is not a measured member",
        )
        relative_members.append(row["relativePath"])
    require(
        len(set(relative_members)) == len(relative_members),
        referent_code,
        "successor source set repeats a member path",
    )
    measured_successor_source = measure_source_set(
        packet / source_law["root"],
        relative_members,
        schema=source_law["schema"],
        profile_id=profile["successorPacketProfileId"],
        claim_boundary=source_law["claimBoundary"],
        id_key=source_law["idKey"],
        id_prefix=source_law["idPrefix"],
        code=referent_code,
        label="successor source set",
    )
    require(
        dict(stored_source) == measured_successor_source,
        binding_code,
        "the stored successor source set does not reproduce from its measured member bytes",
    )
    require(
        measured_successor_source[source_law["idKey"]] == successor_source_set_id,
        binding_code,
        "the measured successor source set is not the source set the successor contract names",
    )

    return {
        "campaignId": campaign_id,
        "campaignLabel": campaign_label,
        "packetId": packet_id,
        "successorContractId": successor_contract_id,
        "predecessorPacketId": predecessor_packet_id,
        "packetHandoffId": packet_handoff_id,
        "successorSourceSetId": successor_source_set_id,
        "successorSourceSetMemberCount": measured_successor_source["memberCount"],
        "predecessorPacketMarkerId": predecessor_marker_id,
        "predecessorPacketStateId": predecessor_state_id,
        "packetMarkerProfileId": packet_marker["packetProfileId"],
        "packetStateProfileId": state["packetProfileId"],
        "canonicalMissionStateDigest": canonical_mission_state_digest,
        # Every packet-side object this gate read, fenced before and after admission.
        "fencedPaths": [
            (packet / packet_law["markerFile"], "PACKET_MARKER_INVALID", "packet marker"),
            (packet / contract_law["file"], "SUCCESSOR_CONTRACT_INVALID", "successor contract"),
            (state_path, "PACKET_STATE_INVALID", "packet state"),
            (packet / packet_law["configFile"], "PACKET_CONFIG_INVALID", "packet configuration"),
            (predecessor_marker_path, referent_code, "predecessor packet marker"),
            (predecessor_state_path, referent_code, "predecessor packet state"),
            (handoff_path, referent_code, "packet handoff receipt"),
            (source_set_path, referent_code, "successor source set"),
            *(
                (packet / source_law["root"] / relative, referent_code, f"successor source member {relative}")
                for relative in relative_members
            ),
            (workstation / ws_law["markerFile"], "WORKSTATION_MARKER_INVALID", "workstation marker"),
        ],
    }


# --------------------------------------------------------------------------------
# admission request
# --------------------------------------------------------------------------------


def load_request(candidates: Path, profile: Mapping[str, Any]) -> Mapping[str, Any]:
    request_law = profile["request"]
    request = read_json_file(
        candidates / request_law["fileName"], code="ADMISSION_REQUEST_INVALID", label="admission request"
    )
    exact_keys(request, request_law["keys"], "ADMISSION_REQUEST_INVALID", "admission request")
    require(
        request["schema"] == request_law["schema"], "ADMISSION_REQUEST_INVALID", "admission request schema differs"
    )
    require(request["authority"] == AUTHORITY, "AUTHORITY_WIDENED", "admission request grants authority")
    assert_bounded_text(request["claimBoundary"], "ADMISSION_REQUEST_INVALID", "admission request claim boundary")
    assert_identity(
        request,
        request_law["idKey"],
        request_law["idPrefix"],
        "ADMISSION_REQUEST_ID_INVALID",
        "admission request",
    )
    return request


def validate_observation_transaction(request: Mapping[str, Any], profile: Mapping[str, Any]) -> dict[str, int]:
    law = profile["observationTransaction"]
    transaction = request["observationTransaction"]
    exact_keys(transaction, law["keys"], "OBSERVATION_TRANSACTION_INVALID", "observation transaction")
    require(
        transaction["schema"] == law["schema"],
        "OBSERVATION_TRANSACTION_INVALID",
        "observation transaction schema differs",
    )
    started = assert_unix_ns(
        transaction["startedAtUnixNs"], "OBSERVATION_TRANSACTION_INVALID", "observation transaction start"
    )
    ended = assert_unix_ns(
        transaction["endedAtUnixNs"], "OBSERVATION_TRANSACTION_INVALID", "observation transaction end"
    )
    require(
        started < ended,
        "OBSERVATION_TRANSACTION_INVALID",
        "observation transaction window does not advance",
    )
    require(
        ended - started <= law["maxWindowNs"],
        "OBSERVATION_TRANSACTION_UNBOUNDED",
        "observation transaction window exceeds the admitted bound",
    )
    transaction_id = assert_identity(
        transaction,
        law["idKey"],
        law["idPrefix"],
        "OBSERVATION_TRANSACTION_ID_INVALID",
        "observation transaction",
    )
    return {"transactionId": transaction_id, "startedAtUnixNs": started, "endedAtUnixNs": ended}


def validate_accepted_predecessor_graph(
    request: Mapping[str, Any], profile: Mapping[str, Any]
) -> dict[str, set[str]]:
    law = profile["request"]
    rows = request["acceptedPredecessorGraph"]
    code = "ACCEPTED_PREDECESSOR_GRAPH_INVALID"
    require(isinstance(rows, list), code, "accepted predecessor graph must be a list")
    require(
        len(rows) <= MAX_ACCEPTED_PREDECESSOR_ROWS,
        code,
        "accepted predecessor graph exceeds the admitted bound",
    )
    graph: dict[str, set[str]] = {}
    for row in rows:
        exact_keys(row, law["acceptedPredecessorKeys"], code, "accepted predecessor row")
        coordinate = assert_content_id(row["acceptedPredecessorCoordinate"], code, "accepted predecessor coordinate")
        require(
            row["campaignId"] == request["campaignId"],
            "PREDECESSOR_CAMPAIGN_BINDING_INVALID",
            "accepted predecessor coordinate belongs to another campaign",
        )
        receipts = row["sourceReceiptIds"]
        require(isinstance(receipts, list) and receipts, code, "accepted predecessor row carries no receipt identity")
        for receipt in receipts:
            assert_content_id(receipt, code, "accepted predecessor receipt identity")
        require(len(set(receipts)) == len(receipts), code, "accepted predecessor row repeats a receipt identity")
        require(coordinate not in graph, code, "accepted predecessor graph repeats a coordinate")
        graph[coordinate] = set(receipts)
    return graph


# --------------------------------------------------------------------------------
# one evidence body
# --------------------------------------------------------------------------------


def admit_evidence_body(
    *,
    descriptor: Mapping[str, Any],
    stage: str,
    sequence: int,
    role_law: Mapping[str, Any],
    profile: Mapping[str, Any],
    candidates: Path,
    packet: Path,
    frozen: Mapping[str, Any],
    request: Mapping[str, Any],
    transaction: Mapping[str, Any],
    graph: Mapping[str, set[str]],
) -> dict[str, Any]:
    code = "EVIDENCE_DESCRIPTOR_INVALID"
    role = role_law["evidenceRole"]
    label = f"{stage} evidence role {role_law['evidenceRoleKey']}"
    provenance = role_law["provenanceClass"]

    exact_keys(descriptor, profile["descriptorKeys"], code, f"{label} descriptor")
    require(descriptor["authority"] == AUTHORITY, "AUTHORITY_WIDENED", f"{label} descriptor grants authority")
    assert_bounded_text(descriptor["claimBoundary"], code, f"{label} descriptor claim boundary")
    require(
        descriptor["provenanceClass"] == provenance,
        "EVIDENCE_PROVENANCE_INVALID",
        f"{label} descriptor names a provenance class the stage role does not admit",
    )
    require(
        descriptor["evidenceClass"] in profile["evidenceClassByProvenance"][provenance],
        "EVIDENCE_CLASS_INCONSISTENT",
        f"{label} evidence class is inconsistent with its provenance class",
    )

    relative = descriptor["bodyPath"]
    require(
        isinstance(relative, str) and RELATIVE_MEMBER_RE.fullmatch(relative) is not None and "\\" not in relative,
        "EVIDENCE_BODY_PATH_INVALID",
        f"{label} body path is not a bounded POSIX-relative coordinate",
    )
    body_path = validate_lexical_coordinate(
        candidates / relative, label=f"{label} body", code="EVIDENCE_BODY_PATH_INVALID"
    )
    require(
        is_within(body_path, candidates),
        "EVIDENCE_BODY_PATH_INVALID",
        f"{label} body escapes the admission workspace",
    )
    require(
        not is_within(body_path, packet),
        "EVIDENCE_BODY_INSIDE_PACKET",
        f"{label} body is staged inside the packet; the gate admits nothing into the packet",
    )

    data = read_bounded_bytes(body_path, MAX_BODY_BYTES, code="EVIDENCE_BODY_UNREADABLE", label=f"{label} body")
    require(len(data) > 0, "EVIDENCE_BODY_EMPTY", f"{label} body is empty")
    measured_sha256 = sha256_bytes(data)
    require(
        descriptor["bodySha256"] == measured_sha256 and descriptor["bodyBytes"] == len(data),
        "EVIDENCE_BODY_MEASUREMENT_MISMATCH",
        f"{label} descriptor digest or byte count differs from the measured body",
    )
    assert_sha256(descriptor["bodySha256"], code, f"{label} body digest")

    opaque_law = profile["opaqueInstrument"]
    opaque_class = descriptor["opaqueInstrumentClass"]
    if opaque_class is not None:
        require(
            provenance == opaque_law["provenanceClass"],
            "OPAQUE_INSTRUMENT_PROVENANCE_INVALID",
            f"{label} offers an opaque instrument body for a provenance class that does not admit one",
        )
        require(
            opaque_class in opaque_law["admittedInstrumentClasses"],
            "OPAQUE_INSTRUMENT_CLASS_INVALID",
            f"{label} names an instrument class outside the admitted denominator",
        )
        require(
            descriptor["mediaType"] in opaque_law["mediaTypes"],
            "EVIDENCE_MEDIA_TYPE_INCONSISTENT",
            f"{label} opaque media type is not admitted",
        )
        require(
            descriptor["bodySchema"] is None and descriptor["bodyContentId"] is None,
            code,
            f"{label} opaque body may not claim a parsed schema or content identity",
        )
        receipt_relative = descriptor["instrumentReceiptPath"]
        require(
            isinstance(receipt_relative, str)
            and RELATIVE_MEMBER_RE.fullmatch(receipt_relative) is not None
            and "\\" not in receipt_relative,
            "OPAQUE_INSTRUMENT_RECEIPT_ABSENT",
            f"{label} opaque body carries no admitted instrument receipt",
        )
        receipt_path = validate_lexical_coordinate(
            candidates / receipt_relative, label=f"{label} instrument receipt", code="OPAQUE_INSTRUMENT_RECEIPT_ABSENT"
        )
        require(
            is_within(receipt_path, candidates),
            "OPAQUE_INSTRUMENT_RECEIPT_ABSENT",
            f"{label} instrument receipt escapes the admission workspace",
        )
        receipt_bytes = read_bounded_bytes(
            receipt_path, MAX_JSON_BYTES, code="OPAQUE_INSTRUMENT_RECEIPT_INVALID", label=f"{label} instrument receipt"
        )
        receipt = parse_json_bytes(
            receipt_bytes, code="OPAQUE_INSTRUMENT_RECEIPT_INVALID", label=f"{label} instrument receipt"
        )
        exact_keys(
            receipt, opaque_law["receiptKeys"], "OPAQUE_INSTRUMENT_RECEIPT_INVALID", f"{label} instrument receipt"
        )
        require(
            receipt["schema"] == opaque_law["receiptSchema"],
            "OPAQUE_INSTRUMENT_RECEIPT_INVALID",
            f"{label} instrument receipt schema differs",
        )
        body_content_id = assert_identity(
            receipt,
            opaque_law["receiptIdKey"],
            opaque_law["receiptIdPrefix"],
            "OPAQUE_INSTRUMENT_RECEIPT_ID_INVALID",
            f"{label} instrument receipt",
        )
        require(
            receipt["instrumentClass"] == opaque_class,
            "OPAQUE_INSTRUMENT_CLASS_INVALID",
            f"{label} instrument receipt names another instrument class",
        )
        require(
            receipt["opaqueBodySha256"] == measured_sha256 and receipt["opaqueBodyBytes"] == len(data),
            "OPAQUE_INSTRUMENT_BINDING_INVALID",
            f"{label} instrument receipt does not bind the measured opaque body",
        )
        require(
            receipt["observationTransactionId"] == transaction["transactionId"],
            "OPAQUE_INSTRUMENT_BINDING_INVALID",
            f"{label} instrument receipt names another observation transaction",
        )
        captured = assert_unix_ns(
            receipt["capturedAtUnixNs"], "OPAQUE_INSTRUMENT_RECEIPT_INVALID", f"{label} instrument capture coordinate"
        )
        require(
            transaction["startedAtUnixNs"] <= captured <= transaction["endedAtUnixNs"],
            "CURRENT_OBSERVATION_STALE",
            f"{label} instrument capture falls outside the declared observation transaction window",
        )
        body = receipt
    else:
        schema_law = profile["bodySchemas"][provenance]
        require(
            descriptor["bodySchema"] == schema_law["schema"],
            "EVIDENCE_SCHEMA_INVALID",
            f"{label} descriptor names an unknown or absent body schema",
        )
        require(
            descriptor["instrumentReceiptPath"] is None,
            code,
            f"{label} parsed body may not carry an instrument receipt path",
        )
        require(
            descriptor["mediaType"] in profile["mediaTypeByProvenance"][provenance],
            "EVIDENCE_MEDIA_TYPE_INCONSISTENT",
            f"{label} media type is inconsistent with the admitted body schema",
        )
        body = parse_json_bytes(data, code="EVIDENCE_SCHEMA_INVALID", label=f"{label} body")
        exact_keys(body, schema_law["keys"], "EVIDENCE_SCHEMA_INVALID", f"{label} body")
        require(
            body["schema"] == schema_law["schema"],
            "EVIDENCE_SCHEMA_INVALID",
            f"{label} body schema differs from the descriptor",
        )
        body_content_id = assert_identity(
            body, schema_law["idKey"], schema_law["idPrefix"], "EVIDENCE_CONTENT_ID_FORGED", f"{label} body"
        )
        require(
            descriptor["bodyContentId"] == body_content_id,
            "EVIDENCE_CONTENT_ID_FORGED",
            f"{label} descriptor content identity differs from the recomputed body identity",
        )

    # ---- bindings every admitted body owes, opaque or parsed ------------------
    require(body["authority"] == AUTHORITY, "AUTHORITY_WIDENED", f"{label} body grants authority")
    require(
        body["campaignId"] == request["campaignId"] == frozen["campaignId"],
        "EVIDENCE_CAMPAIGN_BINDING_INVALID",
        f"{label} body names another campaign",
    )
    require(
        body["packetId"] == request["packetId"] == frozen["packetId"],
        "EVIDENCE_PACKET_BINDING_INVALID",
        f"{label} body names another packet",
    )
    require(
        body["stage"] == stage and body["sequence"] == sequence,
        "EVIDENCE_STAGE_BINDING_INVALID",
        f"{label} body was authenticated for another stage",
    )
    require(
        body["evidenceRole"] == role,
        "EVIDENCE_ROLE_BINDING_INVALID",
        f"{label} body was authenticated for another evidence role",
    )
    require(
        body["canonicalMissionStateDigest"] == frozen["canonicalMissionStateDigest"],
        "CANONICAL_MISSION_STATE_CHANGED",
        f"{label} body names another canonical mission state than the configured packet",
    )
    require(
        body["provenanceClass"] == provenance,
        "EVIDENCE_PROVENANCE_INVALID",
        f"{label} body provenance class differs from the descriptor",
    )
    assert_bounded_text(body["claimBoundary"], code, f"{label} body claim boundary")

    predicates = body["semanticPredicates"]
    require(isinstance(predicates, Mapping), "EVIDENCE_SEMANTICS_INSUFFICIENT", f"{label} semantic predicates missing")
    required = role_law["requiredPredicates"]
    require(
        set(predicates.keys()) == set(required.keys()),
        "EVIDENCE_SEMANTICS_INSUFFICIENT",
        f"{label} semantic predicate denominator differs from the stage role contract",
    )
    for key, expected in required.items():
        require(
            predicates[key] == expected and type(predicates[key]) is type(expected),
            "EVIDENCE_SEMANTICS_INSUFFICIENT",
            f"{label} does not prove the predicate {key} the stage requires",
        )

    # ---- provenance-specific law ---------------------------------------------
    if provenance == "accepted_predecessor_receipt":
        schema_law = profile["bodySchemas"][provenance]
        require(
            body["reuseClass"] == schema_law["requiredReuseClass"],
            "PREDECESSOR_REUSE_CLASS_INVALID",
            f"{label} reused receipt is not marked as a reused pre-stage receipt",
        )
        coordinate = assert_content_id(
            body["acceptedPredecessorCoordinate"], code, f"{label} accepted predecessor coordinate"
        )
        require(
            body["sourceCampaignId"] == frozen["campaignId"],
            "PREDECESSOR_CAMPAIGN_BINDING_INVALID",
            f"{label} reused receipt belongs to another campaign",
        )
        require(
            coordinate in graph,
            "PREDECESSOR_OUTSIDE_ACCEPTED_GRAPH",
            f"{label} reused receipt names a coordinate outside the accepted predecessor graph",
        )
        source_receipt_id = assert_content_id(body["sourceReceiptId"], code, f"{label} source receipt identity")
        require(
            source_receipt_id in graph[coordinate],
            "PREDECESSOR_OUTSIDE_ACCEPTED_GRAPH",
            f"{label} reused receipt is not part of the accepted coordinate it names",
        )
        captured = assert_unix_ns(body["capturedAtUnixNs"], code, f"{label} capture coordinate")
        require(
            captured < transaction["startedAtUnixNs"],
            "PREDECESSOR_RECEIPT_MISREPRESENTED_AS_FRESH",
            f"{label} reused receipt claims capture inside the current observation transaction",
        )
    elif provenance == "current_local_observation" and opaque_class is None:
        require(
            body["observationTransactionId"] == transaction["transactionId"],
            "CURRENT_OBSERVATION_TRANSACTION_INVALID",
            f"{label} current observation names another observation transaction",
        )
        assert_content_id(body["sourceObservationId"], code, f"{label} source observation identity")
        captured = assert_unix_ns(body["capturedAtUnixNs"], code, f"{label} capture coordinate")
        require(
            transaction["startedAtUnixNs"] <= captured <= transaction["endedAtUnixNs"],
            "CURRENT_OBSERVATION_STALE",
            f"{label} current observation was not captured inside the declared transaction window",
        )
        require(
            body["claimsHistoricalTransition"] is False,
            "CURRENT_OBSERVATION_CLAIMS_HISTORY",
            f"{label} current observation claims an uncaptured historical transition",
        )
    elif provenance == "named_human_statement":
        schema_law = profile["bodySchemas"][provenance]
        actor = body["actorClass"]
        require(
            isinstance(actor, str) and actor.lower() not in set(schema_law["forbiddenActorClasses"]),
            "HUMAN_STATEMENT_ACTOR_INVALID",
            f"{label} statement carries a machine actor class",
        )
        require(
            actor == schema_law["requiredActorClass"],
            "HUMAN_STATEMENT_ACTOR_INVALID",
            f"{label} statement was not issued by the named-human actor class",
        )
        assert_bounded_text(body["statementScope"], code, f"{label} statement scope")
        assert_bounded_text(body["authenticationBinding"], code, f"{label} statement authentication binding")
        assert_unix_ns(body["issuedAtUnixNs"], code, f"{label} statement issue coordinate")
        accepted = body["acceptedEvidenceIds"]
        require(isinstance(accepted, list), code, f"{label} accepted evidence identities must be a list")
        for row in accepted:
            assert_content_id(row, code, f"{label} accepted evidence identity")
        require(len(set(accepted)) == len(accepted), code, f"{label} repeats an accepted evidence identity")
        binding_law = schema_law["evidenceAdmissionBinding"]
        bound_root = assert_content_id(
            body[binding_law["rootKey"]],
            binding_law["rootRefusalCode"],
            f"{label} non-human evidence admission root",
        )
        require(
            bound_root.startswith(f"{binding_law['rootPrefix']}_"),
            binding_law["rootRefusalCode"],
            f"{label} does not bind a stage evidence-admission root",
        )

    return {
        "evidenceRole": role,
        "evidenceRoleKey": role_law["evidenceRoleKey"],
        "provenanceClass": provenance,
        "evidenceClass": descriptor["evidenceClass"],
        "mediaType": descriptor["mediaType"],
        "bodySha256": measured_sha256,
        "bodyBytes": len(data),
        "bodyContentId": body_content_id,
        "opaqueInstrumentClass": opaque_class,
        "body": body,
    }


# --------------------------------------------------------------------------------
# named-human statement semantics that the stage itself imposes
# --------------------------------------------------------------------------------


def validate_human_statement_for_stage(
    *, stage: str, admitted: Mapping[str, Any], stage_law: Mapping[str, Any], profile: Mapping[str, Any]
) -> None:
    schema_law = profile["bodySchemas"]["named_human_statement"]
    body = admitted["body"]
    label = f"{stage} named-human statement"
    require(
        body["terminalOrRetainedObligation"] == stage_law["requiredTerminal"],
        "HUMAN_STATEMENT_TERMINAL_INVALID",
        f"{label} names a terminal the stage does not require",
    )
    if stage == schema_law["conflictStage"]:
        requirements = schema_law["conflictRequirements"]
        branches = body["retainedBranches"]
        require(
            isinstance(branches, list) and len(branches) == requirements["retainedBranchCount"],
            "CONFLICT_STATEMENT_BRANCHES_LOST",
            f"{label} does not retain both divergent branches",
        )
        for row in branches:
            assert_sha256(row, "CONFLICT_STATEMENT_BRANCHES_LOST", f"{label} retained branch digest")
        require(
            len(set(branches)) == len(branches),
            "CONFLICT_STATEMENT_BRANCHES_LOST",
            f"{label} retained branches are not distinct",
        )
        require(
            body["selectedWinner"] is None,
            "CONFLICT_STATEMENT_SELECTS_WINNER",
            f"{label} selects a conflict winner; disposition is deferred to the named human",
        )
        require(
            body["automaticMerge"] is requirements["automaticMerge"],
            "CONFLICT_STATEMENT_AUTOMATIC_MERGE",
            f"{label} permits an automatic merge",
        )
    else:
        require(
            body["selectedWinner"] is None and body["retainedBranches"] == [] and body["automaticMerge"] is None,
            "HUMAN_STATEMENT_SCOPE_INVALID",
            f"{label} carries conflict-resolution fields outside the retained-conflict stage",
        )


# --------------------------------------------------------------------------------
# stage confirmations
# --------------------------------------------------------------------------------


def validate_stage_confirmations(
    *,
    request: Mapping[str, Any],
    profile: Mapping[str, Any],
    frozen: Mapping[str, Any],
    stage_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    law = profile["confirmation"]
    code = "STAGE_CONFIRMATION_INVALID"
    supplied = request["stageConfirmations"]
    require(isinstance(supplied, list), code, "stage confirmations must be a list")
    denominator = profile["denominator"]["stageConfirmationDenominator"]
    require(
        len(supplied) in (0, denominator),
        "STAGE_CONFIRMATION_DENOMINATOR_INVALID",
        "a partial stage-confirmation set is not an admitted decision denominator",
    )
    if not supplied:
        return []

    by_stage = {row["stage"]: row for row in stage_rows}
    seen_ids: set[str] = set()
    seen_stages: set[str] = set()
    decisions: list[dict[str, Any]] = []
    for confirmation in supplied:
        exact_keys(confirmation, law["keys"], code, "stage confirmation")
        require(confirmation["schema"] == law["schema"], code, "stage confirmation schema differs")
        require(confirmation["authority"] == AUTHORITY, "AUTHORITY_WIDENED", "stage confirmation grants authority")
        actor = confirmation["actorClass"]
        require(
            isinstance(actor, str) and actor.lower() not in set(law["forbiddenActorClasses"]),
            "STAGE_CONFIRMATION_ACTOR_INVALID",
            "stage confirmation carries a machine actor class",
        )
        require(
            actor == law["requiredActorClass"],
            "STAGE_CONFIRMATION_ACTOR_INVALID",
            "stage confirmation was not issued by the named-human actor class",
        )
        confirmation_id = assert_identity(
            confirmation, law["idKey"], law["idPrefix"], "STAGE_CONFIRMATION_ID_INVALID", "stage confirmation"
        )
        require(
            confirmation_id not in seen_ids,
            "STAGE_CONFIRMATION_REPLAYED",
            "the same stage confirmation identity was supplied more than once",
        )
        seen_ids.add(confirmation_id)
        stage = confirmation["stage"]
        require(stage in by_stage, "STAGE_CONFIRMATION_STAGE_MISMATCH", "stage confirmation names an unknown stage")
        require(
            stage not in seen_stages,
            "STAGE_CONFIRMATION_REPLAYED",
            f"stage {stage} carries more than one confirmation",
        )
        seen_stages.add(stage)
        row = by_stage[stage]
        require(
            confirmation["sequence"] == row["sequence"],
            "STAGE_CONFIRMATION_STAGE_MISMATCH",
            f"stage confirmation for {stage} names another sequence",
        )
        require(
            confirmation["campaignId"] == frozen["campaignId"] and confirmation["packetId"] == frozen["packetId"],
            "STAGE_CONFIRMATION_CAMPAIGN_BINDING_INVALID",
            f"stage confirmation for {stage} names another campaign or packet",
        )
        require(
            confirmation["requiredTerminal"] == row["requiredTerminal"],
            "STAGE_CONFIRMATION_TERMINAL_INVALID",
            f"stage confirmation for {stage} names another required terminal",
        )
        require(
            confirmation["evidenceAdmissionRoot"] == row["evidenceAdmissionRoot"],
            "STAGE_CONFIRMATION_ROOT_MISMATCH",
            f"stage confirmation for {stage} is bound to another evidence admission root",
        )
        require(
            confirmation["observationDigest"] == row["observationDigest"],
            "STAGE_CONFIRMATION_ROOT_MISMATCH",
            f"stage confirmation for {stage} is bound to another observation digest",
        )
        require(
            confirmation["decisionCode"] in law["decisionCodes"],
            code,
            f"stage confirmation for {stage} carries an unbounded decision",
        )
        assert_bounded_text(
            confirmation["controlQuestionResponse"], code, f"stage {stage} control-question response"
        )
        assert_bounded_text(confirmation["authenticationBinding"], code, f"stage {stage} authentication binding")
        assert_unix_ns(confirmation["issuedAtUnixNs"], code, f"stage {stage} confirmation issue coordinate")
        decisions.append(
            {
                "sequence": row["sequence"],
                "stage": stage,
                "decisionCode": confirmation["decisionCode"],
                "stageConfirmationId": confirmation_id,
                "evidenceAdmissionRoot": row["evidenceAdmissionRoot"],
                "observationDigest": row["observationDigest"],
                "requiredTerminal": row["requiredTerminal"],
                "controlQuestionResponse": confirmation["controlQuestionResponse"],
            }
        )

    require(
        seen_stages == {row["stage"] for row in stage_rows},
        "STAGE_CONFIRMATION_DENOMINATOR_INVALID",
        "the stage-confirmation set does not exact-enumerate the sixteen-stage denominator",
    )
    decisions.sort(key=lambda row: row["sequence"])
    return decisions


def validate_batch_confirmation(
    *,
    request: Mapping[str, Any],
    profile: Mapping[str, Any],
    frozen: Mapping[str, Any],
    decisions: Sequence[Mapping[str, Any]],
) -> str | None:
    batch = request["batchConfirmation"]
    if batch is None:
        return None
    law = profile["batchConfirmation"]
    code = "BATCH_CONFIRMATION_INVALID"
    require(
        bool(decisions),
        "BATCH_CONFIRMATION_UNBOUNDED",
        "a batch confirmation may not stand in for the exact per-stage decision denominator",
    )
    exact_keys(batch, law["keys"], code, "batch confirmation")
    require(batch["schema"] == law["schema"], code, "batch confirmation schema differs")
    require(batch["authority"] == AUTHORITY, "AUTHORITY_WIDENED", "batch confirmation grants authority")
    require(
        batch["actorClass"] == profile["confirmation"]["requiredActorClass"],
        "STAGE_CONFIRMATION_ACTOR_INVALID",
        "batch confirmation was not issued by the named-human actor class",
    )
    require(
        batch["campaignId"] == frozen["campaignId"] and batch["packetId"] == frozen["packetId"],
        "STAGE_CONFIRMATION_CAMPAIGN_BINDING_INVALID",
        "batch confirmation names another campaign or packet",
    )
    assert_bounded_text(batch["authenticationBinding"], code, "batch confirmation authentication binding")
    assert_unix_ns(batch["issuedAtUnixNs"], code, "batch confirmation issue coordinate")
    rows = batch["stages"]
    require(
        isinstance(rows, list) and batch["stageCount"] == law["requiredStageCount"] == len(rows),
        "BATCH_CONFIRMATION_UNBOUNDED",
        "batch confirmation does not exact-enumerate every stage",
    )
    for row, decision in zip(rows, decisions, strict=True):
        exact_keys(row, law["stageKeys"], code, "batch confirmation stage row")
        require(
            row["stage"] == decision["stage"] and row["sequence"] == decision["sequence"],
            "BATCH_CONFIRMATION_UNBOUNDED",
            "batch confirmation stage order differs from the stage denominator",
        )
        require(
            row["evidenceAdmissionRoot"] == decision["evidenceAdmissionRoot"]
            and row["observationDigest"] == decision["observationDigest"]
            and row["requiredTerminal"] == decision["requiredTerminal"],
            "BATCH_CONFIRMATION_ROOT_MISMATCH",
            f"batch confirmation for {decision['stage']} is bound to another evidence root",
        )
        require(
            row["decisionCode"] == decision["decisionCode"],
            "BATCH_CONFIRMATION_ROOT_MISMATCH",
            f"batch confirmation for {decision['stage']} disagrees with the exact stage decision",
        )
        assert_bounded_text(row["controlQuestionResponse"], code, "batch confirmation control-question response")
    return assert_identity(
        batch, law["idKey"], law["idPrefix"], "BATCH_CONFIRMATION_ID_INVALID", "batch confirmation"
    )


# --------------------------------------------------------------------------------
# the gate
# --------------------------------------------------------------------------------


def verify_packet_evidence_admission(
    *,
    workstation: Path,
    packet: Path,
    candidates: Path,
    profile_path: Path,
    admission_source_root: Path,
    measured_verifier_bytes: bytes | None = None,
) -> dict[str, Any]:
    require_supported_python()

    workstation = validate_lexical_coordinate(
        workstation, label="workstation coordinate", code="WORKSTATION_ROOT_INVALID"
    )
    packet = validate_lexical_coordinate(packet, label="packet root", code="PACKET_ROOT_INVALID")
    candidates = validate_lexical_coordinate(
        candidates, label="admission workspace", code="ADMISSION_WORKSPACE_INVALID"
    )
    profile_path = validate_lexical_coordinate(profile_path, label="admission profile", code="PROFILE_UNREADABLE")
    admission_source_root = validate_lexical_coordinate(
        admission_source_root, label="admission source root", code="ADMISSION_SOURCE_SET_INVALID"
    )

    profile = load_profile(profile_path)
    denominator = profile["denominator"]

    require(
        not is_within(candidates, packet),
        "ADMISSION_WORKSPACE_INSIDE_PACKET",
        "the admission workspace is inside the packet; admission is a separate surface",
    )
    require(
        not is_within(packet, candidates),
        "ADMISSION_WORKSPACE_INSIDE_PACKET",
        "the packet is inside the admission workspace",
    )
    require(
        not is_within(candidates, admission_source_root),
        "ADMISSION_WORKSPACE_INSIDE_SOURCE",
        "the admission workspace is inside the public source root",
    )
    require(
        candidates.is_dir()
        and not coordinate_component_is_link(candidates, code="ADMISSION_WORKSPACE_INVALID", label="admission workspace"),
        "ADMISSION_WORKSPACE_INVALID",
        "admission workspace is not a regular non-linked directory",
    )

    frozen = read_frozen_surface(workstation=workstation, packet=packet, profile=profile)
    fence_prefix = profile["digests"]["fencePrefix"]
    packet_fence_before = [
        file_fence(path, fence_prefix, code=code, label=label) for path, code, label in frozen["fencedPaths"]
    ]

    request = load_request(candidates, profile)
    require(
        request["campaignId"] == frozen["campaignId"],
        "REQUEST_CAMPAIGN_BINDING_INVALID",
        "admission request names another campaign than the frozen workstation",
    )
    require(
        request["packetId"] == frozen["packetId"],
        "REQUEST_PACKET_BINDING_INVALID",
        "admission request names another packet than the configured packet",
    )
    require(
        request["canonicalMissionStateDigest"] == frozen["canonicalMissionStateDigest"],
        "CANONICAL_MISSION_STATE_CHANGED",
        "admission request names another canonical mission state than the configured packet",
    )

    transaction = validate_observation_transaction(request, profile)
    graph = validate_accepted_predecessor_graph(request, profile)

    stage_requests = request["stages"]
    require(
        isinstance(stage_requests, list) and len(stage_requests) == denominator["stageDenominator"],
        "STAGE_DENOMINATOR_INVALID",
        "admission request does not carry the exact sixteen-stage denominator",
    )

    stage_rows: list[dict[str, Any]] = []
    seen_body_identities: set[str] = set()
    seen_body_digests: set[str] = set()
    admitted_role_count = 0
    admitted_human_statements = 0
    reused_predecessor_receipts = 0
    current_observations = 0
    missing_roles: list[dict[str, str]] = []
    human_statement_requirements: list[dict[str, Any]] = []
    current_observation_requirements: list[dict[str, Any]] = []

    for index, stage_request in enumerate(stage_requests):
        stage = profile["stageSequence"][index]
        sequence = index + 1
        stage_law = profile["stages"][stage]
        exact_keys(stage_request, profile["request"]["stageKeys"], "STAGE_REQUEST_INVALID", f"{stage} stage request")
        require(
            stage_request["stage"] == stage and stage_request["sequence"] == sequence,
            "STAGE_DENOMINATOR_INVALID",
            "admission request stage order differs from the admitted stage denominator",
        )
        require(
            stage_request["availabilityClass"] == stage_law["availabilityClass"],
            "STAGE_AVAILABILITY_CLASS_INVALID",
            f"{stage} availability class differs from the admitted evidence matrix",
        )
        validate_observation(stage, stage_law["observation"], stage_request["observation"])
        observation_digest = content_id(
            profile["digests"]["observationDigestPrefix"],
            {"sequence": sequence, "stage": stage, "observation": stage_request["observation"]},
        )

        descriptors = stage_request["evidence"]
        require(isinstance(descriptors, list), "STAGE_REQUEST_INVALID", f"{stage} evidence must be a list")
        require(
            len(descriptors) <= MAX_EVIDENCE_FILES_PER_STAGE,
            "STAGE_REQUEST_INVALID",
            f"{stage} evidence denominator exceeds the admitted bound",
        )
        by_role = {row["evidenceRole"]: row for row in stage_law["evidenceRoles"]}
        offered: dict[str, Mapping[str, Any]] = {}
        for descriptor in descriptors:
            require(isinstance(descriptor, Mapping), "EVIDENCE_DESCRIPTOR_INVALID", f"{stage} descriptor must be an object")
            role = descriptor.get("evidenceRole")
            require(
                role in by_role,
                "EVIDENCE_ROLE_UNKNOWN",
                f"{stage} carries an evidence role outside the admitted stage denominator",
            )
            require(
                role not in offered,
                "EVIDENCE_ROLE_DUPLICATED",
                f"{stage} carries more than one body for evidence role {role}",
            )
            offered[role] = descriptor

        admitted_rows: list[dict[str, Any]] = []
        for role_law in stage_law["evidenceRoles"]:
            role = role_law["evidenceRole"]
            descriptor = offered.get(role)
            if descriptor is None:
                missing_roles.append(
                    {
                        "stage": stage,
                        "evidenceRole": role,
                        "evidenceRoleKey": role_law["evidenceRoleKey"],
                        "provenanceClass": role_law["provenanceClass"],
                    }
                )
                continue
            admitted = admit_evidence_body(
                descriptor=descriptor,
                stage=stage,
                sequence=sequence,
                role_law=role_law,
                profile=profile,
                candidates=candidates,
                packet=packet,
                frozen=frozen,
                request=request,
                transaction=transaction,
                graph=graph,
            )
            require(
                admitted["bodyContentId"] not in seen_body_identities,
                "DUPLICATE_EVIDENCE_IDENTITY",
                "the same evidence identity is offered for more than one evidence role",
            )
            require(
                admitted["bodySha256"] not in seen_body_digests,
                "DUPLICATE_EVIDENCE_IDENTITY",
                "the same evidence body bytes are offered for more than one evidence role",
            )
            seen_body_identities.add(admitted["bodyContentId"])
            seen_body_digests.add(admitted["bodySha256"])
            if role_law["provenanceClass"] == "named_human_statement":
                validate_human_statement_for_stage(
                    stage=stage, admitted=admitted, stage_law=stage_law, profile=profile
                )
                admitted_human_statements += 1
            elif role_law["provenanceClass"] == "accepted_predecessor_receipt":
                reused_predecessor_receipts += 1
            else:
                current_observations += 1
            admitted_role_count += 1
            admitted_rows.append(admitted)

        # A named-human statement may only accept evidence identities admitted for its
        # own stage. This is checked after the stage is complete so the statement cannot
        # bind an identity the gate never measured.
        stage_identities = {row["bodyContentId"] for row in admitted_rows}
        for row in admitted_rows:
            if row["provenanceClass"] != "named_human_statement":
                continue
            for accepted in row["body"]["acceptedEvidenceIds"]:
                require(
                    accepted in stage_identities,
                    "HUMAN_STATEMENT_SCOPE_INVALID",
                    f"{stage} named-human statement accepts an evidence identity this gate did not admit for the stage",
                )

        def stage_root(rows: Sequence[Mapping[str, Any]], scope: str) -> str:
            return content_id(
                profile["digests"]["stageEvidenceRootPrefix"],
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

        evidence_admission_root = stage_root(admitted_rows, "all-admitted-evidence-roles")
        # The non-human root is stable across the two passes this gate is designed for:
        # it does not move when the outstanding named-human statement is later supplied,
        # so a human statement can bind it without chasing its own effect on the root.
        non_human_root = stage_root(
            [row for row in admitted_rows if row["provenanceClass"] != "named_human_statement"],
            "non-human-evidence-roles",
        )
        # A named-human statement authorizes on the complete non-human evidence of its own
        # stage. Accepting a subset -- or none at all -- would let a seal authorization
        # exist beside evidence its signer never accepted, so the set is exact and the
        # root is recomputed from exactly that set.
        statement_binding = profile["bodySchemas"]["named_human_statement"]["evidenceAdmissionBinding"]
        require(
            statement_binding["requiresCompleteNonHumanAdmissionSet"] is True
            and statement_binding["rootKey"] == profile["sealAuthorization"]["statementRootKey"],
            "PROFILE_INVALID",
            "admission profile does not bind statements to the complete non-human stage root",
        )
        non_human_identities = {
            row["bodyContentId"] for row in admitted_rows if row["provenanceClass"] != "named_human_statement"
        }
        for row in admitted_rows:
            if row["provenanceClass"] != "named_human_statement":
                continue
            require(
                set(row["body"][statement_binding["acceptedIdentitiesKey"]]) == non_human_identities,
                statement_binding["setRefusalCode"],
                f"{stage} named-human statement does not accept the exact complete non-human "
                "evidence set this gate admitted for the stage",
            )
            require(
                row["body"][statement_binding["rootKey"]] == non_human_root,
                statement_binding["rootRefusalCode"],
                f"{stage} named-human statement binds another non-human evidence-admission root "
                "than the one this gate computed for the stage",
            )

        stage_roles_outstanding = sum(
            1 for row in missing_roles if row["stage"] == stage
        )

        for role_law in stage_law["evidenceRoles"]:
            if role_law["provenanceClass"] == "named_human_statement":
                human_statement_requirements.append(
                    {
                        "sequence": sequence,
                        "stage": stage,
                        "evidenceRole": role_law["evidenceRole"],
                        "requiredSchema": profile["bodySchemas"]["named_human_statement"]["schema"],
                        "requiredActorClass": profile["bodySchemas"]["named_human_statement"]["requiredActorClass"],
                        "requiredTerminalOrRetainedObligation": stage_law["requiredTerminal"],
                        "requiredPredicates": role_law["requiredPredicates"],
                        "nonHumanEvidenceAdmissionRoot": non_human_root,
                        "observationDigest": observation_digest,
                        "supplied": role_law["evidenceRole"] in offered,
                    }
                )
            elif role_law["provenanceClass"] == "current_local_observation":
                current_observation_requirements.append(
                    {
                        "sequence": sequence,
                        "stage": stage,
                        "evidenceRole": role_law["evidenceRole"],
                        "requiredSchema": profile["bodySchemas"]["current_local_observation"]["schema"],
                        "requiredPredicates": role_law["requiredPredicates"],
                        "observationTransactionId": transaction["transactionId"],
                        "supplied": role_law["evidenceRole"] in offered,
                    }
                )

        stage_rows.append(
            {
                "sequence": sequence,
                "stage": stage,
                "availabilityClass": stage_law["availabilityClass"],
                "requiredTerminal": stage_law["requiredTerminal"],
                "controlQuestion": stage_law["controlQuestion"],
                "evidenceRoleDenominator": stage_law["evidenceRoleDenominator"],
                "admittedEvidenceRoleCount": len(admitted_rows),
                "admittedEvidenceIdentities": [row["bodyContentId"] for row in admitted_rows],
                "reusedPredecessorReceiptCount": sum(
                    1 for row in admitted_rows if row["provenanceClass"] == "accepted_predecessor_receipt"
                ),
                "currentObservationCount": sum(
                    1 for row in admitted_rows if row["provenanceClass"] == "current_local_observation"
                ),
                "namedHumanStatementCount": sum(
                    1 for row in admitted_rows if row["provenanceClass"] == "named_human_statement"
                ),
                "evidenceAdmissionRoot": evidence_admission_root,
                "nonHumanEvidenceAdmissionRoot": non_human_root,
                "observationDigest": observation_digest,
                "outstandingEvidenceRoleCount": stage_roles_outstanding,
                "evidenceAdmissionRootFinal": stage_roles_outstanding == 0,
            }
        )

    require(
        admitted_human_statements in (0, denominator["humanStatementRoleCount"]),
        "HUMAN_STATEMENT_DENOMINATOR_INVALID",
        "a partial named-human statement set is not an admitted denominator",
    )

    # The sixteen decision records become invitable only once every stage root is final:
    # both named-human statements landed and all sixteen final roots exist. Until then a
    # confirmation would bind a root that has not settled, and would go stale the moment
    # a statement-bearing stage root moved. This is the published form of a rule the gate
    # already enforces through STAGE_CONFIRMATION_ON_INCOMPLETE_EVIDENCE.
    confirmation_invitable = not missing_roles
    for row in stage_rows:
        row["confirmationInvitable"] = confirmation_invitable

    missing_non_human = [row for row in missing_roles if row["provenanceClass"] != "named_human_statement"]
    decisions = validate_stage_confirmations(
        request=request, profile=profile, frozen=frozen, stage_rows=stage_rows
    )
    batch_confirmation_id = validate_batch_confirmation(
        request=request, profile=profile, frozen=frozen, decisions=decisions
    )

    if decisions:
        require(
            not missing_non_human,
            "STAGE_CONFIRMATION_ON_INCOMPLETE_EVIDENCE",
            "stage confirmations were supplied against an incomplete evidence denominator",
        )
        require(
            admitted_human_statements == denominator["humanStatementRoleCount"],
            "STAGE_CONFIRMATION_ON_INCOMPLETE_EVIDENCE",
            "stage confirmations were supplied before both named-human statements",
        )
    refusing = [row for row in decisions if row["decisionCode"] == "REFUSE_STAGE"]
    require(
        not refusing,
        "STAGE_DECISION_REFUSED",
        f"the named human refused {len(refusing)} stage decision(s); no packet denominator is admissible",
    )
    holding = [row for row in decisions if row["decisionCode"] == profile["confirmation"]["holdingDecisionCode"]]

    if missing_non_human:
        terminal = HOLD
        hold_reason = "non-human evidence roles outstanding"
    elif admitted_human_statements == 0 and not decisions:
        terminal = READY
        hold_reason = None
    elif admitted_role_count == denominator["evidenceRoleDenominator"] and holding:
        terminal = HOLD
        hold_reason = "named human held one or more stage decisions"
    elif admitted_role_count == denominator["evidenceRoleDenominator"] and len(decisions) == denominator[
        "stageConfirmationDenominator"
    ]:
        terminal = ADMISSIBLE
        hold_reason = None
    else:
        terminal = HOLD
        hold_reason = "named-human statements supplied; sixteen exact stage decisions outstanding"

    admission_root = content_id(
        profile["digests"]["admissionRootPrefix"],
        [
            {
                "sequence": row["sequence"],
                "stage": row["stage"],
                "evidenceAdmissionRoot": row["evidenceAdmissionRoot"],
                "observationDigest": row["observationDigest"],
            }
            for row in stage_rows
        ],
    )

    # ---- admission source, separately identified ----------------------------
    measured_source = measure_source_set(
        admission_source_root,
        profile["admissionSourceMembers"],
        schema=SOURCE_SET_SCHEMA,
        profile_id=PROFILE_ID,
        claim_boundary=SOURCE_SET_CLAIM_BOUNDARY,
        id_key="sourceSetId",
        id_prefix=SOURCE_SET_ID_PREFIX,
        code="ADMISSION_SOURCE_SET_INVALID",
        label="admission source set",
    )
    require(
        set(profile["admissionSourceMembers"]).isdisjoint(set(profile["frozenRuntimeMembers"])),
        "ADMISSION_SOURCE_CLAIMS_FROZEN_RUNTIME",
        "the admission source set claims a frozen packet-runtime member as its own",
    )

    measured_verifier_sha256 = None
    if measured_verifier_bytes is not None:
        measured_verifier_sha256 = sha256_bytes(measured_verifier_bytes)
        stored = next(
            (
                row
                for row in measured_source["members"]
                if row["relativePath"].endswith("verify_stc_mary_packet_evidence_admission.py")
            ),
            None,
        )
        require(
            stored is not None and stored["sha256"] == measured_verifier_sha256,
            "MEASURED_VERIFIER_MEMBER_BINDING_INVALID",
            "the executing verifier bytes are not the stored admission source member",
        )

    # ---- nothing moved while we read ----------------------------------------
    packet_fence_after = [
        file_fence(path, fence_prefix, code=code, label=label) for path, code, label in frozen["fencedPaths"]
    ]
    require(
        packet_fence_after == packet_fence_before,
        "PACKET_MUTATED_DURING_ADMISSION",
        "the configured packet changed while its evidence was being admitted",
    )

    checks = [
        "workstation-marker-identity",
        "packet-marker-identity",
        "packet-state-identity",
        "packet-campaign-binding-exact",
        "packet-configured-and-unrecorded",
        "successor-packet-identity-required",
        "frozen-predecessor-packet-refused",
        "packet-marker-and-state-profile-agreement",
        "successor-contract-identity",
        "successor-contract-lineage-binding",
        "predecessor-packet-referent-measured",
        "packet-handoff-referent-measured",
        "successor-source-set-members-measured",
        "packet-canonical-mission-state-bound",
        "admission-request-identity",
        "admission-request-campaign-and-packet-binding",
        "observation-transaction-bounded",
        "accepted-predecessor-graph-closed",
        "stage-denominator-exact",
        "stage-availability-class-exact",
        "stage-observation-contract-exact",
        "evidence-role-denominator-closed",
        "evidence-body-independently-measured",
        "evidence-body-schema-parsed",
        "evidence-content-identity-recomputed",
        "evidence-campaign-packet-stage-role-binding",
        "evidence-class-and-media-type-consistent-with-body",
        "evidence-semantic-predicates-exact",
        "reused-predecessor-receipt-marked-and-graph-bound",
        "reused-predecessor-receipt-predates-observation-transaction",
        "current-observation-inside-transaction-window",
        "current-observation-claims-no-history",
        "opaque-instrument-receipt-bound",
        "duplicate-evidence-identity-refused",
        "named-human-statement-actor-class-exact",
        "named-human-statement-scope-bound",
        "named-human-statement-accepts-complete-non-human-set",
        "named-human-statement-non-human-root-bound",
        "conflict-statement-retains-both-branches",
        "stage-confirmation-denominator-closed",
        "stage-confirmation-root-and-observation-binding",
        "stage-confirmation-replay-refused",
        "batch-confirmation-exact-enumeration",
        "admission-source-separately-identified",
        "frozen-packet-runtime-unclaimed",
        "packet-unmutated-fence",
        "authority-none",
    ]
    if measured_verifier_sha256 is not None:
        checks.append("measured-verifier-member-binding")

    body = {
        "schema": RECEIPT_SCHEMA,
        "status": "PASS",
        "terminal": terminal,
        "holdReason": hold_reason,
        "profileId": PROFILE_ID,
        "campaignId": frozen["campaignId"],
        "packetId": frozen["packetId"],
        "requestId": request[profile["request"]["idKey"]],
        "observationTransactionId": transaction["transactionId"],
        "canonicalMissionStateDigest": frozen["canonicalMissionStateDigest"],
        "successorContractId": frozen["successorContractId"],
        "predecessorPacketId": frozen["predecessorPacketId"],
        "predecessorPacketMarkerId": frozen["predecessorPacketMarkerId"],
        "predecessorPacketStateId": frozen["predecessorPacketStateId"],
        "packetHandoffId": frozen["packetHandoffId"],
        "successorSourceSetId": frozen["successorSourceSetId"],
        "successorSourceSetMemberCount": frozen["successorSourceSetMemberCount"],
        "successorPacketProfileId": profile["successorPacketProfileId"],
        "predecessorPacketProfileId": profile["predecessorPacketProfileId"],
        "packetMarkerProfileId": frozen["packetMarkerProfileId"],
        "packetStateProfileId": frozen["packetStateProfileId"],
        "directFrozenPacketApplication": False,
        "stageDenominator": denominator["stageDenominator"],
        "evidenceRoleDenominator": denominator["evidenceRoleDenominator"],
        "nonHumanEvidenceRoleDenominator": denominator["nonHumanEvidenceRoleCount"],
        "humanStatementRoleDenominator": denominator["humanStatementRoleCount"],
        "stageConfirmationDenominator": denominator["stageConfirmationDenominator"],
        "admittedEvidenceRoleCount": admitted_role_count,
        "admittedNonHumanEvidenceRoleCount": admitted_role_count - admitted_human_statements,
        "admittedHumanStatementCount": admitted_human_statements,
        "reusedPredecessorReceiptCount": reused_predecessor_receipts,
        "currentObservationCount": current_observations,
        "missingEvidenceRoles": missing_roles,
        "missingEvidenceRoleCount": len(missing_roles),
        "stages": stage_rows,
        "humanStatementRequirements": human_statement_requirements,
        "currentObservationRequirements": current_observation_requirements,
        "stageConfirmationRequirements": [
            {
                "sequence": row["sequence"],
                "stage": row["stage"],
                "requiredTerminal": row["requiredTerminal"],
                "controlQuestion": row["controlQuestion"],
                "evidenceAdmissionRoot": row["evidenceAdmissionRoot"],
                "evidenceAdmissionRootFinal": row["evidenceAdmissionRootFinal"],
                "confirmationInvitable": row["confirmationInvitable"],
                "observationDigest": row["observationDigest"],
                "requiredSchema": profile["confirmation"]["schema"],
                "requiredActorClass": profile["confirmation"]["requiredActorClass"],
                "decisionCodes": profile["confirmation"]["decisionCodes"],
            }
            for row in stage_rows
        ],
        "confirmationDenominatorInvitable": confirmation_invitable,
        "suppliedStageConfirmationCount": len(decisions),
        "stageDecisions": decisions,
        "batchConfirmationId": batch_confirmation_id,
        "evidenceAdmissionDigestRoot": admission_root,
        "admissionSourceSetId": measured_source["sourceSetId"],
        "admissionSourceMemberCount": measured_source["memberCount"],
        "packetStagesRecorded": 0,
        "operatorConfirmedFlagsSet": 0,
        "packetRecorderInvoked": False,
        "packetMutated": False,
        "humanStatementsGeneratedByThisGate": 0,
        "stageConfirmationsIssuedByThisGate": 0,
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
    assert_no_private_material(receipt, code="ADMISSION_RECEIPT_PRIVATE_MATERIAL", label="admission receipt")
    return receipt


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Admit proposed private stage evidence for one configured, unrecorded STC MARY private flight packet"
    )
    parser.add_argument("--workstation", type=Path, required=True)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--admission-source-root", type=Path)
    parser.add_argument("--out", type=Path)
    return parser.parse_args(argv)


def refusal_document(code: str, message: str) -> dict[str, Any]:
    return {
        "schema": RECEIPT_SCHEMA,
        "status": "REFUSED",
        "code": code,
        "message": message,
        "terminal": REFUSED,
        "bootstrapAuthenticated": False,
        "packetStagesRecorded": 0,
        "operatorConfirmedFlagsSet": 0,
        "packetRecorderInvoked": False,
        "packetMutated": False,
        "humanStatementsGeneratedByThisGate": 0,
        "stageConfirmationsIssuedByThisGate": 0,
        "authority": AUTHORITY,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        profile_path = args.profile
        admission_source_root = args.admission_source_root
        if admission_source_root is None:
            admission_source_root = profile_path.resolve(strict=False).parent.parent.parent
        output = None
        if args.out is not None:
            output = validate_lexical_coordinate(
                args.out, label="receipt output coordinate", code="RECEIPT_PATH_INVALID"
            )
            for forbidden, label in ((args.packet, "packet"), (args.candidates, "admission workspace")):
                if is_within(output, Path(os.path.abspath(os.fspath(forbidden)))):
                    fail("RECEIPT_INSIDE_MEASURED_SURFACE", f"the admission receipt may not be written inside the {label}")
            if output.exists():
                fail("RECEIPT_OUTPUT_EXISTS", "admission receipt output must not already exist")
        receipt = verify_packet_evidence_admission(
            workstation=args.workstation,
            packet=args.packet,
            candidates=args.candidates,
            profile_path=profile_path,
            admission_source_root=admission_source_root,
            measured_verifier_bytes=globals().get("_STC_MARY_BOOTSTRAP_MEASURED_VERIFIER_BYTES"),
        )
        data = canonical_json_bytes(receipt)
        if output is None:
            sys.stdout.buffer.write(data)
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(data)
        return 0
    except AdmissionError as exc:
        sys.stdout.buffer.write(canonical_json_bytes(refusal_document(exc.code, str(exc))))
        return 1
    except (OSError, ValueError) as exc:
        sys.stdout.buffer.write(canonical_json_bytes(refusal_document("ADMISSION_FILESYSTEM_ERROR", str(exc))))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
