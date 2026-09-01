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

The second is where a stage's evidence comes from and what its evidence-admission root
means. This runtime does not hash whatever files happen to sit in a stage's evidence
directory, and it does not copy the root the admission receipt published. It is handed the
exact admitted role rows of an evidence-materialization receipt, requires the stage
directory to hold exactly those coordinates and nothing else, recomputes every body's own
content identity from the bytes in the packet, and then *reconstructs* the stage
evidence-admission root from those rows. A stage is recordable only when the reconstructed
root equals the authorized one, so the root in a stage record is a measurement of the
bodies beside it rather than a value inherited from elsewhere.

The Stage 16 observation contract is not restated here either. Every stage observation is
validated against the admitted packet-evidence-admission@2 profile, read through the
successor profile's canonical-digest pin, so this runtime cannot record a Stage 16
observation the admission gate would not admit.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

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
    "confirmation that must authorize it. It describes no evidence body, carries no evidence "
    "class or media type, grants no authority and records nothing."
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
    code = "STAGE_DRAFT_INVALID"
    label = f"{stage} stage draft"
    law.exact_keys(draft, draft_law["keys"], code, label)
    # The frozen recorder's self-declared operator Boolean has no coordinate in this
    # schema, so a draft cannot even offer one without failing the exact key denominator.
    law.require(
        "operatorConfirmed" not in draft,
        "STAGE_DRAFT_SELF_CONFIRMED",
        f"{label} carries a self-declared operator confirmation",
    )
    # Nor may a draft describe the evidence beside it. One draft-wide evidenceClass cannot
    # truthfully describe a stage that combines an accepted predecessor receipt with a
    # named-human statement, and a draft-authored class would be a second self-declaration
    # in a schema built to remove the first. Class, media type and provenance are carried
    # per admitted body by the evidence-materialization receipt.
    law.require(
        "evidenceClass" not in draft and "mediaType" not in draft,
        "STAGE_DRAFT_DESCRIBES_ITS_OWN_EVIDENCE",
        f"{label} describes its own evidence class or media type",
    )
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
        isinstance(draft["notes"], str) and len(draft["notes"]) <= 16384,
        code,
        f"{label} notes are invalid or unbounded",
    )
    law.require(draft["authority"] == law.AUTHORITY, "AUTHORITY_WIDENED", f"{label} grants authority")
    return draft


# --------------------------------------------------------------------------------
# recording
# --------------------------------------------------------------------------------


def recompute_body_identity(
    *, admission: Mapping[str, Any], role_row: Mapping[str, Any], data: bytes, label: str
) -> str:
    """Recompute one admitted body's own content identity from the bytes in the packet.

    This is the step that makes the reconstructed stage root a measurement. Without it the
    runtime would be re-hashing files it was merely told about, and a body could be
    replaced by another body of the same length and digest lineage without the identity
    that entered the gate's root ever being checked against the packet.
    """
    provenance = role_row["provenanceClass"]
    if role_row["opaqueInstrumentClass"] is None:
        schema_law = admission["bodySchemas"][provenance]
        body = law.read_json_bytes(data, code="STAGE_EVIDENCE_INVALID", label=label)
        law.exact_keys(body, schema_law["keys"], "STAGE_EVIDENCE_INVALID", label)
        return law.assert_identity(
            body, schema_law["idKey"], schema_law["idPrefix"], "STAGE_EVIDENCE_IDENTITY_INVALID", label
        )
    opaque_law = admission["opaqueInstrument"]
    instrument = law.read_json_bytes(data, code="STAGE_EVIDENCE_INVALID", label=label)
    law.exact_keys(instrument, opaque_law["receiptKeys"], "STAGE_EVIDENCE_INVALID", label)
    return law.assert_identity(
        instrument,
        opaque_law["receiptIdKey"],
        opaque_law["receiptIdPrefix"],
        "STAGE_EVIDENCE_IDENTITY_INVALID",
        label,
    )


def evidence_rows(
    *,
    profile: Mapping[str, Any],
    admission: Mapping[str, Any],
    packet: Path,
    stage: str,
    evidence_directory: str,
    role_rows: Sequence[Mapping[str, Any]],
    maximum: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Measure exactly the materialized admitted bodies, and nothing else.

    Returns the stage record's evidence rows and the role rows the stage evidence-admission
    root is reconstructed from. The two differ: an opaque instrument body and its separately
    admitted instrument receipt are two physical bodies but one evidence role.
    """
    record_law = profile["packet"]["stageRecord"]
    directory = packet / evidence_directory
    law.require(directory.is_dir(), "STAGE_EVIDENCE_INVALID", "stage evidence directory is absent")

    expected: dict[str, tuple[Mapping[str, Any], bool]] = {}
    for role_row in role_rows:
        expected[role_row["packetDestination"]] = (role_row, False)
        if role_row["instrumentReceiptDestination"] is not None:
            expected[role_row["instrumentReceiptDestination"]] = (role_row, True)
    present = {
        f"{evidence_directory}/{entry.name}" for entry in directory.iterdir()
    }
    # An unadmitted file in a stage's evidence directory is the exact defect this runtime
    # exists to refuse: it would be hashed into the manifest, counted as private evidence,
    # and sealed beside a root that never covered it.
    law.require(
        present == set(expected),
        "PACKET_EVIDENCE_UNMATERIALIZED",
        f"{stage} evidence directory does not hold exactly the admitted materialized bodies",
    )
    law.require(
        0 < len(expected) <= maximum,
        "STAGE_EVIDENCE_INVALID",
        "stage evidence file denominator is empty or unbounded",
    )

    rows: list[dict[str, Any]] = []
    root_rows: list[dict[str, Any]] = []
    for relative in sorted(expected):
        role_row, is_instrument_receipt = expected[relative]
        label = f"{stage} evidence role {role_row['evidenceRoleKey']}"
        path = directory / Path(relative).name
        law.require(path.is_file(), "STAGE_EVIDENCE_INVALID", f"stage evidence entry is not a regular file: {relative}")
        data = law.read_bounded_bytes(
            path, law.MAX_EVIDENCE_BYTES, code="STAGE_EVIDENCE_INVALID", label=f"stage evidence {relative}"
        )
        law.require(len(data) > 0, "STAGE_EVIDENCE_INVALID", f"stage evidence body is empty: {relative}")
        measured = law.sha256_bytes(data)
        if is_instrument_receipt:
            law.require(
                measured == role_row["instrumentReceiptSha256"] and len(data) == role_row["instrumentReceiptBytes"],
                "STAGE_EVIDENCE_SUBSTITUTED",
                f"{label} instrument receipt in the packet is not the admitted receipt",
            )
            body_content_id = role_row["instrumentReceiptId"]
            media_type = "application/json"
        else:
            law.require(
                measured == role_row["bodySha256"] and len(data) == role_row["bodyBytes"],
                "STAGE_EVIDENCE_SUBSTITUTED",
                f"{label} body in the packet is not the admitted body",
            )
            body_content_id = recompute_body_identity(
                admission=admission, role_row=role_row, data=data, label=label
            )
            law.require(
                body_content_id == role_row["bodyContentId"],
                "STAGE_EVIDENCE_IDENTITY_INVALID",
                f"{label} body identity recomputed from the packet differs from the admitted identity",
            )
            media_type = role_row["mediaType"]
            root_rows.append(
                {
                    "evidenceRole": role_row["evidenceRole"],
                    "provenanceClass": role_row["provenanceClass"],
                    "evidenceClass": role_row["evidenceClass"],
                    "bodyContentId": body_content_id,
                    "bodySha256": measured,
                    "bodyBytes": len(data),
                }
            )
        law.require(
            role_row["evidenceClass"] in profile["packet"]["evidenceClasses"],
            "STAGE_EVIDENCE_INVALID",
            f"{label} evidence class is not an admitted private evidence class",
        )
        row = {
            "relativePath": relative,
            "sha256": measured,
            "bytes": len(data),
            "mediaType": media_type,
            "evidenceClass": role_row["evidenceClass"],
            "evidenceRole": role_row["evidenceRole"],
            "provenanceClass": role_row["provenanceClass"],
            "bodyContentId": body_content_id,
        }
        law.exact_keys(row, record_law["evidenceRowKeys"], "STAGE_EVIDENCE_INVALID", f"{stage} stage evidence row")
        rows.append(row)
    return rows, root_rows


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
    role_rows: Sequence[Mapping[str, Any]],
    phase_hook: Callable[[str, Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]], None] | None = None,
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

    law.require(
        bool(role_rows) and all(entry["stage"] == stage and entry["sequence"] == sequence for entry in role_rows),
        "STAGE_EVIDENCE_ROLE_BINDING_INVALID",
        f"{stage} was handed materialized evidence roles belonging to another stage",
    )
    rows, root_rows = evidence_rows(
        profile=profile,
        admission=admission,
        packet=packet,
        stage=stage,
        evidence_directory=row["evidenceDirectory"],
        role_rows=role_rows,
        maximum=packet_law["maxEvidenceFilesPerStage"],
    )
    law.require(
        len(root_rows) == admission["stages"][stage]["evidenceRoleDenominator"],
        "STAGE_EVIDENCE_ROLE_DENOMINATOR_INVALID",
        f"{stage} does not carry its admitted evidence-role denominator",
    )
    # The recorded root is reconstructed from the bodies in the packet, never copied from
    # the authorization. Equality with the authorized root is what admits the stage.
    reconstructed_root = law.stage_evidence_root(
        admission, scope=law.ALL_ROLES_SCOPE, sequence=sequence, stage=stage, rows=root_rows
    )
    law.require(
        reconstructed_root == authorization["evidenceAdmissionRoot"],
        "STAGE_EVIDENCE_ROOT_MISMATCH",
        f"{stage} evidence-admission root reconstructed from the packet differs from the authorized root",
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
        "evidenceAdmissionRoot": reconstructed_root,
        "admissionId": authorization["admissionId"],
        "stageConfirmationId": authorization["stageConfirmationId"],
        "authority": law.AUTHORITY,
        "claimBoundary": RECORD_CLAIM,
    }
    record = law.sign(body, record_law["idKey"], record_law["idPrefix"])
    law.exact_keys(record, record_law["keys"], "STAGE_RECORD_INVALID", f"{stage} stage record")
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
    if phase_hook is not None:
        phase_hook("prepared", record, state, next_state)
    law.write_canonical_json(packet / Path(row["draftPath"]).parent / record_law["fileName"], record)
    if phase_hook is not None:
        phase_hook("record-promoted", record, state, next_state)
    law.write_canonical_json(packet / packet_law["files"]["state"], next_state)
    if phase_hook is not None:
        phase_hook("state-promoted", record, state, next_state)
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
