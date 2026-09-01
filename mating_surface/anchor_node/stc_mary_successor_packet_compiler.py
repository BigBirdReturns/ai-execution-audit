"""Compile one stc-mary/private-flight-packet/0.2 successor from a configured 0.1 predecessor.

The compiler is the only surface in this source set that creates a successor packet. It
reads a configured, unrecorded 0.1 predecessor, materializes a *distinct* 0.2 successor
beside it, and proves the predecessor is byte-identical afterwards.

What the successor carries, and why each is measured rather than asserted:

    lineage/predecessor-packet/PACKET-ROOT.json    the predecessor marker, copied verbatim
    lineage/predecessor-packet/packet-state.json   the predecessor state, copied verbatim
    lineage/PACKET-HANDOFF.json                    binds both packets and both profiles
    lineage/SUCCESSOR-SOURCE-SET.json              measured over the member bytes below
    lineage/successor-source/**                    every successor source member, verbatim
    SUCCESSOR-CONTRACT.json                        names all three coordinates above

The admitted packet-evidence-admission@2 gate re-measures every one of those objects
before it will admit evidence for this packet. The compiler therefore produces them in
exactly the shape that gate re-derives, and never imports that gate to do it.

It records no stage, sets no confirmation, seals nothing, and grants no authority.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import stc_mary_successor_flight_law as law  # noqa: E402

PROFILE_PATH = HERE / "stc-mary-successor-packet-flight-01-profile-01.json"

COMPILE_RECEIPT_SCHEMA = "stc-mary/successor-flight-compile-receipt/1"
COMPILE_RECEIPT_ID_KEY = "compileReceiptId"
COMPILE_RECEIPT_ID_PREFIX = "stcmarysuccessorflightcompilereceipt1"

PREDECESSOR_FENCE_PREFIX = "stcmarysuccessorpredecessorfence1"

MARKER_CLAIM = (
    "Marker for one local private-flight packet outside the public repository. It grants no "
    "deletion, physical, mission, command, targeting, engagement, effector, or weapons authority."
)
STATE_CLAIM = (
    "Local packet state. It records preparation and receipt custody only and grants no physical, "
    "mission, command, targeting, engagement, effector, or weapons authority."
)
CONFIG_CLAIM = (
    "Local packet configuration. It binds source identities and canonical mission state and "
    "grants no physical, mission, command, targeting, engagement, effector, or weapons authority."
)
CONTRACT_CLAIM = (
    "Lineage receipt for one successor packet. It binds the exact predecessor packet and profile, "
    "the campaign, the packet handoff, the canonical mission state, and the successor source set. "
    "It grants no authority and establishes no completion."
)
HANDOFF_CLAIM = (
    "Packet handoff receipt. It binds one predecessor packet and one successor packet under one "
    "campaign and one canonical mission state. It grants no authority and establishes no completion."
)
COMPILE_CLAIM = (
    "Compilation receipt for one synthetic successor packet. It reports what was materialized and "
    "that the predecessor was not mutated. It records no stage, seals nothing, qualifies no "
    "physical estate, operator, field network, operational C2 or production Lattice, and grants "
    "no mission, command, targeting, engagement, effector or weapons authority."
)


# --------------------------------------------------------------------------------
# the frozen predecessor surface, read only
# --------------------------------------------------------------------------------


def fence_directory(root: Path, *, code: str, label: str) -> list[dict[str, Any]]:
    """Digest every regular file under ``root``, deterministically ordered."""
    rows: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda entry: entry.as_posix()):
        if not path.is_file():
            continue
        data = law.read_bounded_bytes(path, law.MAX_MEMBER_BYTES, code=code, label=f"{label} member")
        rows.append(
            {
                "relativePath": path.relative_to(root).as_posix(),
                "sha256": law.sha256_bytes(data),
                "bytes": len(data),
            }
        )
    return rows


def fence_identity(rows: list[dict[str, Any]]) -> str:
    return law.content_id(PREDECESSOR_FENCE_PREFIX, {"members": rows, "memberCount": len(rows)})


def read_workstation(profile: Mapping[str, Any], workstation: Path) -> dict[str, str]:
    """Read the frozen conductor marker for the campaign identity and label."""
    marker = law.read_json_file(
        workstation / "CONDUCTOR-ROOT.json", code="WORKSTATION_MARKER_INVALID", label="workstation marker"
    )
    campaign_id = law.assert_content_id(
        marker.get("campaignId"), "WORKSTATION_MARKER_INVALID", "campaign identity"
    )
    campaign_label = law.assert_bounded_text(
        marker.get("campaignLabel"), "WORKSTATION_MARKER_INVALID", "campaign label", 256
    )
    law.require(
        marker.get("authority") == law.AUTHORITY,
        "AUTHORITY_WIDENED",
        "workstation marker grants authority",
    )
    return {"campaignId": campaign_id, "campaignLabel": campaign_label}


def read_predecessor(profile: Mapping[str, Any], predecessor: Path) -> dict[str, Any]:
    """Read one configured, unrecorded 0.1 predecessor packet without writing to it."""
    packet_law = profile["packet"]
    files = packet_law["files"]
    marker = law.read_json_file(
        predecessor / files["marker"], code="PREDECESSOR_MARKER_INVALID", label="predecessor packet marker"
    )
    law.exact_keys(
        marker, packet_law["markerKeys"], "PREDECESSOR_MARKER_INVALID", "predecessor packet marker"
    )
    law.assert_identity(
        marker,
        packet_law["markerIdKey"],
        packet_law["markerIdPrefix"],
        "PREDECESSOR_MARKER_INVALID",
        "predecessor packet marker",
    )
    law.require(
        marker["packetProfileId"] == packet_law["predecessorPacketProfileId"],
        "PREDECESSOR_PROFILE_INVALID",
        "the named predecessor does not carry the frozen 0.1 packet profile",
    )
    law.require(
        marker["physicalProfileId"] == packet_law["physicalProfileId"],
        "PREDECESSOR_PROFILE_INVALID",
        "the named predecessor carries another physical-flight profile",
    )
    state = law.read_json_file(
        predecessor / files["state"], code="PREDECESSOR_STATE_INVALID", label="predecessor packet state"
    )
    law.exact_keys(state, packet_law["stateKeys"], "PREDECESSOR_STATE_INVALID", "predecessor packet state")
    law.assert_identity(
        state,
        packet_law["stateIdKey"],
        packet_law["stateIdPrefix"],
        "PREDECESSOR_STATE_INVALID",
        "predecessor packet state",
    )
    law.require(
        state["packetId"] == marker["packetId"]
        and state["packetProfileId"] == marker["packetProfileId"]
        and state["physicalProfileId"] == marker["physicalProfileId"]
        and state["campaignLabel"] == marker["campaignLabel"],
        "PREDECESSOR_SUCCESSION_SPLIT",
        "predecessor marker and state do not name one packet",
    )
    law.require(
        state["configurationState"] == packet_law["requiredConfigurationState"],
        "PREDECESSOR_NOT_CONFIGURED",
        "the predecessor must be configured before a successor may be compiled from it",
    )
    law.require(
        state["sealed"] is False and state["sealedDispositionId"] is None,
        "PREDECESSOR_ALREADY_SEALED",
        "a sealed predecessor is no longer a compilation source",
    )
    law.require(
        state["completedStageCount"] == 0,
        "PREDECESSOR_STAGES_ALREADY_RECORDED",
        "the predecessor already carries recorded stages",
    )
    config = law.read_json_file(
        predecessor / files["config"], code="PREDECESSOR_CONFIG_INVALID", label="predecessor configuration"
    )
    law.exact_keys(
        config, packet_law["configKeys"], "PREDECESSOR_CONFIG_INVALID", "predecessor configuration"
    )
    law.require(
        config["campaignLabel"] == marker["campaignLabel"],
        "PREDECESSOR_CONFIG_INVALID",
        "predecessor configuration names another campaign",
    )
    law.assert_sha256(
        config["canonicalMissionStateDigest"],
        "PREDECESSOR_CONFIG_INVALID",
        "predecessor canonical mission state digest",
    )
    for row in (marker, state, config):
        law.require(
            row["authority"] == law.AUTHORITY, "AUTHORITY_WIDENED", "predecessor object grants authority"
        )
    return {"marker": marker, "state": state, "config": config}


# --------------------------------------------------------------------------------
# materialize a synthetic predecessor, for source qualification only
# --------------------------------------------------------------------------------


def materialize_synthetic_predecessor(
    *, profile: Mapping[str, Any], packet: Path, campaign_label: str, canonical_mission_state_digest: str
) -> dict[str, Any]:
    """Build one configured, unrecorded synthetic 0.1 packet at ``packet``.

    This exists so the qualifying witness can begin where the transaction requires it to
    begin -- at a configured predecessor at zero of sixteen -- without touching any live
    campaign. It refuses any campaign label that is not declared synthetic.
    """
    require_synthetic_campaign(profile, campaign_label)
    packet_law = profile["packet"]
    files = packet_law["files"]
    law.require(
        not packet.exists() or not any(packet.iterdir()),
        "PREDECESSOR_OUTPUT_EXISTS",
        "the synthetic predecessor coordinate must be empty",
    )
    admission = law.load_admission_profile(repository_root(), profile)
    stages = law.stage_sequence(admission)
    packet_id = law.packet_id_for(
        packet_profile_id=packet_law["predecessorPacketProfileId"],
        physical_profile_id=packet_law["physicalProfileId"],
        campaign_label=campaign_label,
        stages=stages,
    )
    marker_body = {
        "schema": packet_law["markerSchema"],
        "packetProfileId": packet_law["predecessorPacketProfileId"],
        "physicalProfileId": packet_law["physicalProfileId"],
        "campaignLabel": campaign_label,
        "packetId": packet_id,
        "authority": law.AUTHORITY,
        "claimBoundary": MARKER_CLAIM,
    }
    marker = law.sign(marker_body, packet_law["markerIdKey"], packet_law["markerIdPrefix"])
    rows = law.stage_state_rows(stages)
    state_body = {
        "schema": packet_law["stateSchema"],
        "packetId": packet_id,
        "campaignLabel": campaign_label,
        "packetProfileId": packet_law["predecessorPacketProfileId"],
        "physicalProfileId": packet_law["physicalProfileId"],
        "configurationState": "configured",
        "stageDenominator": list(stages),
        "stages": rows,
        "completedStageCount": 0,
        "nextStage": stages[0],
        "sealed": False,
        "sealedDispositionId": None,
        "authority": law.AUTHORITY,
        "claimBoundary": STATE_CLAIM,
    }
    state = law.sign(state_body, packet_law["stateIdKey"], packet_law["stateIdPrefix"])
    config = {
        "schema": packet_law["configSchema"],
        "campaignLabel": campaign_label,
        "sourceObjectDigests": [law.sha256_bytes(f"synthetic-source-object:{campaign_label}".encode("utf-8"))],
        "identityClasses": {
            "personalFloor": "synthetic-personal-floor",
            "halo3": "synthetic-halo3",
            "initialHead": "synthetic-initial-head",
            "successorHead": "synthetic-successor-head",
            "graceBind": "synthetic-named-human-bind",
            "lattice": "synthetic-lattice",
            "leftCell": "synthetic-left-cell",
            "rightCell": "synthetic-right-cell",
        },
        "canonicalMissionStateDigest": canonical_mission_state_digest,
        "authority": law.AUTHORITY,
        "claimBoundary": CONFIG_CLAIM,
    }
    law.write_canonical_json(packet / files["marker"], marker)
    law.write_canonical_json(packet / files["state"], state)
    law.write_canonical_json(packet / files["config"], config)
    return {"marker": marker, "state": state, "config": config}


def require_synthetic_campaign(profile: Mapping[str, Any], campaign_label: str) -> None:
    prefix = profile["humanAuthentication"]["syntheticCampaignLabelPrefix"]
    law.require(
        isinstance(campaign_label, str) and campaign_label.startswith(prefix),
        "SYNTHETIC_AUTHENTICATION_APPLIED_TO_LIVE_CAMPAIGN",
        "this source set may materialize synthetic campaigns only; live campaign application is held",
    )


def repository_root() -> Path:
    return HERE.parent.parent


# --------------------------------------------------------------------------------
# compilation
# --------------------------------------------------------------------------------


def compile_successor_packet(
    *,
    workstation: Path,
    predecessor: Path,
    successor: Path,
    repository: Path,
    profile_path: Path = PROFILE_PATH,
) -> dict[str, Any]:
    law.require_supported_python()
    workstation = law.validate_lexical_coordinate(
        workstation, label="workstation coordinate", code="WORKSTATION_ROOT_INVALID"
    )
    predecessor = law.validate_lexical_coordinate(
        predecessor, label="predecessor packet", code="PREDECESSOR_ROOT_INVALID"
    )
    successor = law.validate_lexical_coordinate(
        successor, label="successor packet", code="SUCCESSOR_ROOT_INVALID"
    )
    repository = law.validate_lexical_coordinate(
        repository, label="repository root", code="SOURCE_ROOT_INVALID"
    )
    profile = law.load_profile(law.validate_lexical_coordinate(
        profile_path, label="successor flight profile", code="PROFILE_UNREADABLE"
    ))
    admission = law.load_admission_profile(repository, profile)

    law.require(
        not law.is_within(successor, predecessor) and not law.is_within(predecessor, successor),
        "SUCCESSOR_INSIDE_PREDECESSOR",
        "the successor packet may not be nested with its predecessor",
    )
    law.require(
        not law.is_within(successor, repository),
        "SUCCESSOR_INSIDE_REPOSITORY",
        "the successor packet may not be materialized inside the public repository",
    )
    law.require(
        not successor.exists() or not any(successor.iterdir()),
        "SUCCESSOR_OUTPUT_EXISTS",
        "the successor packet coordinate must be empty",
    )

    campaign = read_workstation(profile, workstation)
    predecessor_objects = read_predecessor(profile, predecessor)
    predecessor_marker = predecessor_objects["marker"]
    predecessor_config = predecessor_objects["config"]
    law.require(
        predecessor_marker["campaignLabel"] == campaign["campaignLabel"],
        "PREDECESSOR_CAMPAIGN_BINDING_INVALID",
        "the predecessor belongs to another campaign than the workstation",
    )
    require_synthetic_campaign(profile, campaign["campaignLabel"])

    fence_before = fence_directory(
        predecessor, code="PREDECESSOR_UNREADABLE", label="predecessor packet"
    )

    packet_law = profile["packet"]
    lineage_law = profile["lineage"]
    files = packet_law["files"]
    stages = law.stage_sequence(admission)
    campaign_label = campaign["campaignLabel"]
    canonical_mission_state_digest = predecessor_config["canonicalMissionStateDigest"]

    successor_packet_id = law.packet_id_for(
        packet_profile_id=packet_law["packetProfileId"],
        physical_profile_id=packet_law["physicalProfileId"],
        campaign_label=campaign_label,
        stages=stages,
    )
    law.require(
        successor_packet_id != predecessor_marker["packetId"],
        "SUCCESSOR_NOT_DISTINCT",
        "the compiled successor is not distinct from its predecessor",
    )

    # ---- marker, state and configuration, in one agreed succession ---------------
    marker = law.build_packet_marker(
        profile=profile,
        campaign_label=campaign_label,
        packet_id=successor_packet_id,
        claim_boundary=MARKER_CLAIM,
    )
    state = law.build_packet_state(
        profile=profile,
        marker=marker,
        stages=stages,
        rows=law.stage_state_rows(stages),
        configuration_state="configured",
        sealed=False,
        sealed_disposition_id=None,
        claim_boundary=STATE_CLAIM,
    )
    config = {
        "schema": packet_law["configSchema"],
        "campaignLabel": campaign_label,
        "sourceObjectDigests": list(predecessor_config["sourceObjectDigests"]),
        "identityClasses": dict(predecessor_config["identityClasses"]),
        "canonicalMissionStateDigest": canonical_mission_state_digest,
        "authority": law.AUTHORITY,
        "claimBoundary": CONFIG_CLAIM,
    }

    # ---- lineage referents, materialized so the admission gate can measure them ---
    predecessor_marker_bytes = law.read_bounded_bytes(
        predecessor / files["marker"], law.MAX_JSON_BYTES, code="PREDECESSOR_UNREADABLE", label="predecessor marker"
    )
    predecessor_state_bytes = law.read_bounded_bytes(
        predecessor / files["state"], law.MAX_JSON_BYTES, code="PREDECESSOR_UNREADABLE", label="predecessor state"
    )
    write_bytes(successor / lineage_law["predecessorMarkerFile"], predecessor_marker_bytes)
    write_bytes(successor / lineage_law["predecessorStateFile"], predecessor_state_bytes)

    handoff = law.sign(
        {
            "schema": lineage_law["handoffSchema"],
            "campaignId": campaign["campaignId"],
            "campaignLabel": campaign_label,
            "predecessorPacketId": predecessor_marker["packetId"],
            "predecessorPacketProfileId": packet_law["predecessorPacketProfileId"],
            "successorPacketId": successor_packet_id,
            "successorPacketProfileId": packet_law["packetProfileId"],
            "canonicalMissionStateDigest": canonical_mission_state_digest,
            "authority": law.AUTHORITY,
            "claimBoundary": HANDOFF_CLAIM,
        },
        lineage_law["handoffIdKey"],
        lineage_law["handoffIdPrefix"],
    )

    source_set = copy_successor_source(
        profile=profile, repository=repository, successor=successor, packet_profile_id=packet_law["packetProfileId"]
    )

    contract = law.sign(
        {
            "schema": lineage_law["successorContractSchema"],
            "campaignId": campaign["campaignId"],
            "campaignLabel": campaign_label,
            "predecessorPacketId": predecessor_marker["packetId"],
            "predecessorPacketProfileId": packet_law["predecessorPacketProfileId"],
            "successorPacketId": successor_packet_id,
            "successorPacketProfileId": packet_law["packetProfileId"],
            "packetHandoffId": handoff[lineage_law["handoffIdKey"]],
            "canonicalMissionStateDigest": canonical_mission_state_digest,
            "successorSourceSetId": source_set[lineage_law["sourceSetIdKey"]],
            "admissionProfileId": profile["admissionProfile"]["profileId"],
            "authority": law.AUTHORITY,
            "claimBoundary": CONTRACT_CLAIM,
        },
        lineage_law["successorContractIdKey"],
        lineage_law["successorContractIdPrefix"],
    )

    law.write_canonical_json(successor / lineage_law["handoffFile"], handoff)
    law.write_canonical_json(successor / lineage_law["sourceSetFile"], source_set)
    law.write_canonical_json(successor / files["successorContract"], contract)
    law.write_canonical_json(successor / files["marker"], marker)
    law.write_canonical_json(successor / files["state"], state)
    law.write_canonical_json(successor / files["config"], config)

    # ---- the stage skeleton the runtime will fill, one directory per stage -------
    for index, stage in enumerate(stages):
        directory = successor / law.stage_directory_name(index + 1, stage)
        (directory / "evidence").mkdir(parents=True, exist_ok=True)

    # ---- the predecessor did not move --------------------------------------------
    fence_after = fence_directory(predecessor, code="PREDECESSOR_UNREADABLE", label="predecessor packet")
    law.require(
        fence_after == fence_before,
        "PREDECESSOR_MUTATED_DURING_COMPILATION",
        "the predecessor packet changed while its successor was being compiled",
    )
    law.require(
        lineage_law["predecessorMutationAllowed"] is False
        and profile["sourceBoundary"]["predecessorPacketMutationAllowed"] is False,
        "PROFILE_INVALID",
        "this source declares predecessor mutation permitted",
    )

    body = {
        "schema": COMPILE_RECEIPT_SCHEMA,
        "status": "PASS",
        "profileId": law.PROFILE_ID,
        "admissionProfileId": profile["admissionProfile"]["profileId"],
        "admissionProfileCanonicalSha256": profile["admissionProfile"]["canonicalSha256"],
        "campaignId": campaign["campaignId"],
        "campaignLabel": campaign_label,
        "canonicalMissionStateDigest": canonical_mission_state_digest,
        "predecessorPacketId": predecessor_marker["packetId"],
        "predecessorPacketProfileId": packet_law["predecessorPacketProfileId"],
        "predecessorFenceId": fence_identity(fence_before),
        "predecessorFileCount": len(fence_before),
        "predecessorMutated": False,
        "successorPacketId": successor_packet_id,
        "successorPacketProfileId": packet_law["packetProfileId"],
        "successorMarkerId": marker[packet_law["markerIdKey"]],
        "successorStateId": state[packet_law["stateIdKey"]],
        "successorContractId": contract[lineage_law["successorContractIdKey"]],
        "packetHandoffId": handoff[lineage_law["handoffIdKey"]],
        "successorSourceSetId": source_set[lineage_law["sourceSetIdKey"]],
        "successorSourceMemberCount": source_set["memberCount"],
        "stageDenominator": profile["denominator"]["stageDenominator"],
        "completedStageCount": 0,
        "sealed": False,
        "stagesRecordedByThisSurface": 0,
        "stageConfirmationsIssuedByThisSurface": 0,
        "humanStatementsIssuedByThisSurface": 0,
        "physicalEstateQualified": False,
        "representativeOperatorQualified": False,
        "fieldNetworkQualified": False,
        "operationalC2Qualified": False,
        "productionLatticeQualified": False,
        "missionAuthorityGranted": False,
        "commandAuthorityGranted": False,
        "authority": law.AUTHORITY,
        "claimBoundary": COMPILE_CLAIM,
    }
    return law.sign(body, COMPILE_RECEIPT_ID_KEY, COMPILE_RECEIPT_ID_PREFIX)


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(data)


def copy_successor_source(
    *, profile: Mapping[str, Any], repository: Path, successor: Path, packet_profile_id: str
) -> dict[str, Any]:
    """Copy every successor source member into the packet, then measure what was written.

    The bytes are copied verbatim rather than normalized, so the set the admission gate
    re-measures is exactly what this working tree holds. That makes the measured identity
    a property of the checkout, which is the honest reading: a different checkout is a
    different source set.
    """
    lineage_law = profile["lineage"]
    members = profile["successorSourceMembers"]
    law.require(
        len(members) == profile["successorSourceMemberDenominator"],
        "SOURCE_MEMBER_DENOMINATOR_INVALID",
        "the declared source member denominator differs from the declared members",
    )
    law.require(
        len(set(members.values())) == len(members),
        "SOURCE_MEMBER_DENOMINATOR_INVALID",
        "two source members claim one packet coordinate",
    )
    frozen = set(profile["frozenRuntimeMembers"])
    law.require(
        frozen.isdisjoint(set(members)),
        "SOURCE_CLAIMS_FROZEN_RUNTIME",
        "the successor source set claims a frozen packet-runtime member as its own",
    )
    root = successor / lineage_law["sourceRoot"]
    for repository_relative, member_relative in sorted(members.items()):
        law.require(
            law.RELATIVE_MEMBER_RE.fullmatch(member_relative) is not None and "\\" not in member_relative,
            "SOURCE_MEMBER_COORDINATE_INVALID",
            f"source member coordinate is not an admitted relative member: {member_relative}",
        )
        source = law.validate_lexical_coordinate(
            repository / repository_relative, label="successor source member", code="SOURCE_MEMBER_UNREADABLE"
        )
        data = law.read_bounded_bytes(
            source, law.MAX_MEMBER_BYTES, code="SOURCE_MEMBER_UNREADABLE", label=f"source member {repository_relative}"
        )
        write_bytes(root / member_relative, data)
    return law.measure_source_set(
        root,
        sorted(members.values()),
        schema=lineage_law["sourceSetSchema"],
        profile_id=packet_profile_id,
        claim_boundary=lineage_law["sourceSetClaimBoundary"],
        id_key=lineage_law["sourceSetIdKey"],
        id_prefix=lineage_law["sourceSetIdPrefix"],
        code="SUCCESSOR_SOURCE_SET_INVALID",
        label="successor source set",
    )


# --------------------------------------------------------------------------------
# command line
# --------------------------------------------------------------------------------


def refusal_document(code: str, message: str) -> dict[str, Any]:
    return {
        "schema": COMPILE_RECEIPT_SCHEMA,
        "status": "REFUSED",
        "code": code,
        "message": message,
        "predecessorMutated": False,
        "stagesRecordedByThisSurface": 0,
        "stageConfirmationsIssuedByThisSurface": 0,
        "humanStatementsIssuedByThisSurface": 0,
        "authority": law.AUTHORITY,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compile one stc-mary/private-flight-packet/0.2 successor from a configured 0.1 predecessor"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    synthetic = sub.add_parser(
        "materialize-predecessor", help="materialize one synthetic configured 0.1 predecessor"
    )
    synthetic.add_argument("--packet", type=Path, required=True)
    synthetic.add_argument("--campaign-label", required=True)
    synthetic.add_argument("--canonical-mission-state", required=True)

    build = sub.add_parser("compile", help="compile one 0.2 successor from a 0.1 predecessor")
    build.add_argument("--workstation", type=Path, required=True)
    build.add_argument("--predecessor", type=Path, required=True)
    build.add_argument("--successor", type=Path, required=True)
    build.add_argument("--repository-root", type=Path, default=repository_root())
    build.add_argument("--out", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.command == "materialize-predecessor":
            profile = law.load_profile(PROFILE_PATH)
            result = materialize_synthetic_predecessor(
                profile=profile,
                packet=law.validate_lexical_coordinate(
                    args.packet, label="synthetic predecessor", code="PREDECESSOR_ROOT_INVALID"
                ),
                campaign_label=args.campaign_label,
                canonical_mission_state_digest=law.assert_sha256(
                    args.canonical_mission_state, "PREDECESSOR_CONFIG_INVALID", "canonical mission state digest"
                ),
            )
            sys.stdout.buffer.write(
                law.canonical_json_bytes(
                    {
                        "status": "MATERIALIZED",
                        "packetId": result["marker"]["packetId"],
                        "packetProfileId": result["marker"]["packetProfileId"],
                        "completedStageCount": 0,
                        "authority": law.AUTHORITY,
                    }
                )
            )
            return 0

        receipt = compile_successor_packet(
            workstation=args.workstation,
            predecessor=args.predecessor,
            successor=args.successor,
            repository=args.repository_root,
        )
        data = law.canonical_json_bytes(receipt)
        if args.out is None:
            sys.stdout.buffer.write(data)
        else:
            out = law.validate_lexical_coordinate(
                args.out, label="compile receipt output", code="RECEIPT_PATH_INVALID"
            )
            law.require(not out.exists(), "RECEIPT_OUTPUT_EXISTS", "compile receipt output must not already exist")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
        return 0
    except law.SuccessorFlightError as exc:
        sys.stdout.buffer.write(law.canonical_json_bytes(refusal_document(exc.code, str(exc))))
        return 1
    except (OSError, ValueError) as exc:
        sys.stdout.buffer.write(law.canonical_json_bytes(refusal_document("COMPILER_FILESYSTEM_ERROR", str(exc))))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
