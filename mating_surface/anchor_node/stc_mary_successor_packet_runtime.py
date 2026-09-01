"""The stc-mary/private-flight-packet/0.2 successor packet runtime.

This is an independent implementation of the packet recorder, not a patched copy of the
frozen 0.1 runtime. It never imports the frozen module.

The one substantive difference from the frozen recorder is where recording consent comes
from. The frozen recorder admits a stage when the operator-authored draft carries
``operatorConfirmed: true`` -- a Boolean the operator process writes about itself. The
0.2 draft schema has no such field at all. A stage is recordable here only when the draft
names a ``stageConfirmationId`` and the caller supplies the matching authenticated
recording authorization derived from an admission receipt. There is no path by which this
module can record a stage from a self-declared flag.

The Stage 16 observation contract is not restated here either. Every stage observation is
validated against the admitted packet-evidence-admission@2 profile, read through the
successor profile's canonical-digest pin, so this runtime cannot record a Stage 16
observation the admission gate would not admit.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import stc_mary_successor_flight_law as law  # noqa: E402

PROFILE_PATH = HERE / "stc-mary-successor-packet-flight-01-profile-01.json"

RECORD_CLAIM = (
    "Local stage record with relative evidence references. It names the admission receipt and "
    "the named-human stage confirmation that authorized it, remains outside the public "
    "repository, and grants no physical, mission, command, targeting, engagement, effector, or "
    "weapons authority."
)
STATE_CLAIM = (
    "Local packet state. It records preparation and receipt custody only and grants no physical, "
    "mission, command, targeting, engagement, effector, or weapons authority."
)
DRAFT_CLAIM = (
    "Local stage draft. It proposes one stage observation and names the named-human stage "
    "confirmation that must authorize it. It grants no authority and records nothing."
)

AUTHORIZATION_KEYS = (
    "admissionId",
    "controlQuestion",
    "evidenceAdmissionRoot",
    "observationDigest",
    "requiredTerminal",
    "stage",
    "stageConfirmationId",
)


# --------------------------------------------------------------------------------
# stage observation, validated against the admitted contract
# --------------------------------------------------------------------------------


def validate_observation(stage: str, contract: Mapping[str, Any], observation: Any) -> None:
    code = "STAGE_OBSERVATION_INVALID"
    label = f"{stage} observation"
    law.exact_keys(observation, contract["keys"], code, label)
    for key, expected in contract.get("requiredValues", {}).items():
        law.require(
            observation[key] == expected and type(observation[key]) is type(expected),
            code,
            f"{label} field {key} is not the exact value the stage requires",
        )
    for key in contract.get("contentIdFields", []):
        law.assert_content_id(observation[key], code, f"{label} {key}")
    for key in contract.get("sha256Fields", []):
        law.assert_sha256(observation[key], code, f"{label} {key}")
    for key in contract.get("boundedStringFields", []):
        law.assert_bounded_text(observation[key], code, f"{label} {key}", 256)
    for key, bounds in contract.get("integerFields", {}).items():
        value = observation[key]
        law.require(
            isinstance(value, int) and not isinstance(value, bool) and bounds[0] <= value <= bounds[1],
            code,
            f"{label} {key} is outside {bounds[0]}..{bounds[1]}",
        )
    for key, allowed in contract.get("enumFields", {}).items():
        law.require(observation[key] in allowed, code, f"{label} {key} is not an admitted value")
    for key, count in contract.get("uniqueStringArrayFields", {}).items():
        value = observation[key]
        law.require(isinstance(value, list) and len(value) == count, code, f"{label} {key} denominator differs")
        for row in value:
            law.assert_bounded_text(row, code, f"{label} {key} member", 256)
        law.require(len(set(value)) == count, code, f"{label} {key} contains duplicates")
    for key, allowed in contract.get("exactStringArrayFields", {}).items():
        law.require(observation[key] == list(allowed), code, f"{label} {key} denominator differs")
    for left, right in contract.get("distinctFieldPairs", []):
        law.require(observation[left] != observation[right], code, f"{label} {left} and {right} are not distinct")


def observation_digest(admission: Mapping[str, Any], *, sequence: int, stage: str, observation: Any) -> str:
    return law.content_id(
        admission["digests"]["observationDigestPrefix"],
        {"sequence": sequence, "stage": stage, "observation": observation},
    )


# --------------------------------------------------------------------------------
# stage drafts
# --------------------------------------------------------------------------------


def build_stage_draft(
    *,
    profile: Mapping[str, Any],
    admission: Mapping[str, Any],
    sequence: int,
    stage: str,
    observation: Mapping[str, Any],
    canonical_mission_state_digest: str,
    stage_confirmation_id: str,
    evidence_class: str,
    media_type: str,
    notes: str = "",
) -> dict[str, Any]:
    draft_law = profile["packet"]["stageDraft"]
    stage_law = admission["stages"][stage]
    draft = {
        "schema": draft_law["schema"],
        "sequence": sequence,
        "stage": stage,
        "terminalState": stage_law["requiredTerminal"],
        "canonicalMissionStateIdBefore": canonical_mission_state_digest,
        "canonicalMissionStateIdAfter": canonical_mission_state_digest,
        "observation": dict(observation),
        "stageConfirmationId": stage_confirmation_id,
        "evidenceClass": evidence_class,
        "mediaType": media_type,
        "notes": notes,
        "authority": law.AUTHORITY,
        "claimBoundary": DRAFT_CLAIM,
    }
    law.exact_keys(draft, draft_law["keys"], "STAGE_DRAFT_INVALID", f"{stage} stage draft")
    return draft


def validate_stage_draft(
    *,
    profile: Mapping[str, Any],
    admission: Mapping[str, Any],
    draft: Mapping[str, Any],
    stage: str,
    sequence: int,
    canonical_mission_state_digest: str,
) -> Mapping[str, Any]:
    draft_law = profile["packet"]["stageDraft"]
    packet_law = profile["packet"]
    code = "STAGE_DRAFT_INVALID"
    label = f"{stage} stage draft"
    law.exact_keys(draft, draft_law["keys"], code, label)
    # The frozen recorder's self-declared operator Boolean has no coordinate in this
    # schema, so a draft cannot even offer one without failing the exact key denominator.
    law.require("operatorConfirmed" not in draft, "STAGE_DRAFT_SELF_CONFIRMED", f"{label} carries a self-declared operator confirmation")
    law.require(draft["schema"] == draft_law["schema"], code, f"{label} schema differs")
    law.require(
        draft["stage"] == stage and draft["sequence"] == sequence,
        "STAGE_OUT_OF_ORDER",
        f"{label} identity or order differs",
    )
    law.require(
        draft["terminalState"] == admission["stages"][stage]["requiredTerminal"],
        "STAGE_TERMINAL_INVALID",
        f"{label} names a terminal the stage does not require",
    )
    law.require(
        draft["canonicalMissionStateIdBefore"] == canonical_mission_state_digest
        and draft["canonicalMissionStateIdAfter"] == canonical_mission_state_digest,
        "CANONICAL_MISSION_STATE_CHANGED",
        f"{label} canonical mission state differs from the configured packet",
    )
    validate_observation(stage, admission["stages"][stage]["observation"], draft["observation"])
    law.assert_content_id(draft["stageConfirmationId"], code, f"{label} stage confirmation identity")
    law.require(
        draft["evidenceClass"] in packet_law["evidenceClasses"],
        code,
        f"{label} evidence class is not an admitted private evidence class",
    )
    law.assert_bounded_text(draft["mediaType"], code, f"{label} media type", 256)
    law.require(
        isinstance(draft["notes"], str) and len(draft["notes"]) <= 16384,
        code,
        f"{label} notes are invalid or unbounded",
    )
    law.require(draft["authority"] == law.AUTHORITY, "AUTHORITY_WIDENED", f"{label} grants authority")
    return draft


# --------------------------------------------------------------------------------
# recording
# --------------------------------------------------------------------------------


def evidence_rows(*, packet: Path, evidence_directory: str, draft: Mapping[str, Any], maximum: int) -> list[dict[str, Any]]:
    directory = packet / evidence_directory
    law.require(directory.is_dir(), "STAGE_EVIDENCE_INVALID", "stage evidence directory is absent")
    names = sorted(entry.name for entry in directory.iterdir())
    law.require(
        0 < len(names) <= maximum,
        "STAGE_EVIDENCE_INVALID",
        "stage evidence file denominator is empty or unbounded",
    )
    rows: list[dict[str, Any]] = []
    for name in names:
        path = directory / name
        law.require(path.is_file(), "STAGE_EVIDENCE_INVALID", f"stage evidence entry is not a regular file: {name}")
        data = law.read_bounded_bytes(
            path, law.MAX_EVIDENCE_BYTES, code="STAGE_EVIDENCE_INVALID", label=f"stage evidence {name}"
        )
        law.require(len(data) > 0, "STAGE_EVIDENCE_INVALID", f"stage evidence body is empty: {name}")
        rows.append(
            {
                "relativePath": path.relative_to(packet).as_posix(),
                "sha256": law.sha256_bytes(data),
                "bytes": len(data),
                "mediaType": draft["mediaType"],
                "evidenceClass": draft["evidenceClass"],
            }
        )
    return rows


def validate_authorization(authorization: Mapping[str, Any], *, stage: str) -> Mapping[str, Any]:
    """The only channel through which a stage becomes recordable."""
    code = "RECORDING_AUTHORIZATION_INVALID"
    law.exact_keys(authorization, AUTHORIZATION_KEYS, code, f"{stage} recording authorization")
    law.require(authorization["stage"] == stage, code, f"{stage} recording authorization names another stage")
    law.assert_content_id(authorization["admissionId"], code, f"{stage} admission identity")
    law.assert_content_id(authorization["stageConfirmationId"], code, f"{stage} stage confirmation identity")
    law.assert_content_id(authorization["evidenceAdmissionRoot"], code, f"{stage} evidence admission root")
    law.assert_content_id(authorization["observationDigest"], code, f"{stage} observation digest")
    law.assert_bounded_text(authorization["controlQuestion"], code, f"{stage} control question")
    law.require(
        authorization["requiredTerminal"] in ("PASS", "HUMAN_REQUIRED"),
        code,
        f"{stage} recording authorization names an unknown terminal",
    )
    return authorization


def record_stage(
    *,
    profile: Mapping[str, Any],
    admission: Mapping[str, Any],
    packet: Path,
    stage: str,
    authorization: Mapping[str, Any],
) -> dict[str, Any]:
    """Record exactly one stage, in order, under one authenticated authorization."""
    law.require_supported_python()
    validate_authorization(authorization, stage=stage)
    packet_law = profile["packet"]
    record_law = packet_law["stageRecord"]
    loaded = law.load_packet(profile, packet)
    marker, state, config = loaded["marker"], loaded["state"], loaded["config"]

    law.require(
        state["configurationState"] == packet_law["requiredConfigurationState"],
        "PACKET_NOT_CONFIGURED",
        "the packet must be configured before a stage is recorded",
    )
    law.require(state["sealed"] is False, "PACKET_ALREADY_SEALED", "a sealed packet cannot record another stage")
    stages = law.stage_sequence(admission)
    law.require(stage in stages, "STAGE_INVALID", "stage is not in the closed sixteen-stage denominator")
    law.require(
        state["nextStage"] == stage,
        "STAGE_OUT_OF_ORDER",
        f"the next recordable stage is {state['nextStage']}",
    )
    row = next(entry for entry in state["stages"] if entry["stage"] == stage)
    sequence = row["sequence"]
    canonical = config["canonicalMissionStateDigest"]

    draft = law.read_json_file(
        packet / row["draftPath"], code="STAGE_DRAFT_INVALID", label=f"{stage} stage draft"
    )
    validate_stage_draft(
        profile=profile,
        admission=admission,
        draft=draft,
        stage=stage,
        sequence=sequence,
        canonical_mission_state_digest=canonical,
    )
    # Recording consent comes from the authenticated confirmation the authorization
    # names, and the draft may only agree with it. It may not supply it.
    law.require(
        draft["stageConfirmationId"] == authorization["stageConfirmationId"],
        "STAGE_CONFIRMATION_BINDING_INVALID",
        f"{stage} draft names another stage confirmation than the authenticated authorization",
    )
    law.require(
        draft["terminalState"] == authorization["requiredTerminal"],
        "STAGE_TERMINAL_INVALID",
        f"{stage} draft terminal differs from the authorized terminal",
    )
    measured_observation_digest = observation_digest(
        admission, sequence=sequence, stage=stage, observation=draft["observation"]
    )
    law.require(
        measured_observation_digest == authorization["observationDigest"],
        "STAGE_OBSERVATION_BINDING_INVALID",
        f"{stage} draft observation is not the observation the named human decided over",
    )

    rows = evidence_rows(
        packet=packet,
        evidence_directory=row["evidenceDirectory"],
        draft=draft,
        maximum=packet_law["maxEvidenceFilesPerStage"],
    )
    for evidence in rows:
        law.exact_keys(
            evidence, record_law["evidenceRowKeys"], "STAGE_EVIDENCE_INVALID", f"{stage} stage evidence row"
        )

    body = {
        "schema": record_law["schema"],
        "packetId": marker["packetId"],
        "sequence": sequence,
        "stage": stage,
        "terminalState": draft["terminalState"],
        "canonicalMissionStateIdBefore": canonical,
        "canonicalMissionStateIdAfter": canonical,
        "observation": dict(draft["observation"]),
        "observationDigest": measured_observation_digest,
        "evidenceFiles": rows,
        "evidenceAdmissionRoot": authorization["evidenceAdmissionRoot"],
        "admissionId": authorization["admissionId"],
        "stageConfirmationId": authorization["stageConfirmationId"],
        "authority": law.AUTHORITY,
        "claimBoundary": RECORD_CLAIM,
    }
    record = law.sign(body, record_law["idKey"], record_law["idPrefix"])
    law.exact_keys(record, record_law["keys"], "STAGE_RECORD_INVALID", f"{stage} stage record")
    law.write_canonical_json(packet / Path(row["draftPath"]).parent / record_law["fileName"], record)

    updated = [
        {**entry, "status": "recorded", "evidenceCount": len(rows), "recordDigest": record[record_law["idKey"]]}
        if entry["stage"] == stage
        else dict(entry)
        for entry in state["stages"]
    ]
    next_state = law.build_packet_state(
        profile=profile,
        marker=marker,
        stages=stages,
        rows=updated,
        configuration_state="configured",
        sealed=False,
        sealed_disposition_id=None,
        claim_boundary=STATE_CLAIM,
    )
    law.write_canonical_json(packet / packet_law["files"]["state"], next_state)
    return {"record": record, "state": next_state}


def read_stage_records(
    *, profile: Mapping[str, Any], packet: Path, state: Mapping[str, Any]
) -> list[Mapping[str, Any]]:
    """Read every recorded stage record, in sequence order, re-identifying each."""
    record_law = profile["packet"]["stageRecord"]
    records: list[Mapping[str, Any]] = []
    for row in state["stages"]:
        law.require(
            row["status"] == "recorded",
            "PACKET_INCOMPLETE",
            f"stage {row['stage']} is not recorded",
        )
        path = packet / Path(row["draftPath"]).parent / record_law["fileName"]
        record = law.read_json_file(path, code="STAGE_RECORD_INVALID", label=f"{row['stage']} stage record")
        law.exact_keys(record, record_law["keys"], "STAGE_RECORD_INVALID", f"{row['stage']} stage record")
        law.assert_identity(
            record, record_law["idKey"], record_law["idPrefix"], "STAGE_RECORD_INVALID", f"{row['stage']} stage record"
        )
        law.require(
            record[record_law["idKey"]] == row["recordDigest"],
            "STAGE_RECORD_BINDING_INVALID",
            f"{row['stage']} stage record identity differs from the packet state",
        )
        law.require(
            record["stage"] == row["stage"] and record["sequence"] == row["sequence"],
            "STAGE_RECORD_BINDING_INVALID",
            f"{row['stage']} stage record order differs from the packet state",
        )
        records.append(record)
    return records


def verify_evidence_custody(*, packet: Path, records: Sequence[Mapping[str, Any]]) -> int:
    """Re-hash every recorded evidence body and refuse any drift since recording."""
    bodies = 0
    for record in records:
        for evidence in record["evidenceFiles"]:
            relative = evidence["relativePath"]
            law.require(
                law.RELATIVE_MEMBER_RE.fullmatch(relative) is not None and "\\" not in relative,
                "STAGE_EVIDENCE_INVALID",
                f"recorded evidence path is not an admitted relative member: {relative}",
            )
            path = law.validate_lexical_coordinate(
                packet / relative, label="recorded evidence body", code="STAGE_EVIDENCE_INVALID"
            )
            law.require(
                law.is_within(path, packet),
                "STAGE_EVIDENCE_ESCAPES_PACKET",
                f"recorded evidence escapes the packet: {relative}",
            )
            data = law.read_bounded_bytes(
                path, law.MAX_EVIDENCE_BYTES, code="STAGE_EVIDENCE_INVALID", label=f"recorded evidence {relative}"
            )
            law.require(
                law.sha256_bytes(data) == evidence["sha256"] and len(data) == evidence["bytes"],
                "STAGE_EVIDENCE_DRIFT",
                f"recorded evidence changed after recording: {relative}",
            )
            bodies += 1
    return bodies


def packet_status(profile: Mapping[str, Any], packet: Path) -> dict[str, Any]:
    loaded = law.load_packet(profile, packet)
    state = loaded["state"]
    return {
        "schema": "stc-mary/successor-flight-packet-status/1",
        "packetId": state["packetId"],
        "packetProfileId": state["packetProfileId"],
        "campaignLabel": state["campaignLabel"],
        "configurationState": state["configurationState"],
        "completedStageCount": state["completedStageCount"],
        "stageCount": len(state["stageDenominator"]),
        "nextStage": state["nextStage"],
        "sealed": state["sealed"],
        "sealedDispositionId": state["sealedDispositionId"],
        "authority": law.AUTHORITY,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect one stc-mary/private-flight-packet/0.2 successor packet")
    sub = parser.add_subparsers(dest="command", required=True)
    status = sub.add_parser("status", help="report the packet's recording state")
    status.add_argument("--packet", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        profile = law.load_profile(PROFILE_PATH)
        packet = law.validate_lexical_coordinate(args.packet, label="packet root", code="PACKET_ROOT_INVALID")
        sys.stdout.buffer.write(law.canonical_json_bytes(packet_status(profile, packet)))
        return 0
    except law.SuccessorFlightError as exc:
        sys.stdout.buffer.write(
            law.canonical_json_bytes(
                {
                    "schema": "stc-mary/successor-flight-packet-status/1",
                    "status": "REFUSED",
                    "code": exc.code,
                    "message": str(exc),
                    "authority": law.AUTHORITY,
                }
            )
        )
        return 1
    except (OSError, ValueError) as exc:
        sys.stdout.buffer.write(
            law.canonical_json_bytes(
                {
                    "schema": "stc-mary/successor-flight-packet-status/1",
                    "status": "REFUSED",
                    "code": "RUNTIME_FILESYSTEM_ERROR",
                    "message": str(exc),
                    "authority": law.AUTHORITY,
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
