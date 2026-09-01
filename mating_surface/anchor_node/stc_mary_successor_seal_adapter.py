"""Seal one closed 0.2 successor packet, and verify the sealed result detached from sealing.

Sealing is permitted only when the packet already carries a valid pre-seal closure at
exact sixteen of sixteen. The closure is not produced here; it is produced by
``verify_stc_mary_successor_pre_seal_closure`` and merely consumed, so the surface that
decides a packet is closed is not the surface that benefits from closing it.

Everything the sealed directory publishes is body-free. The run and the public
disposition carry counts, content identities, terminals and claim boundaries. No private
evidence body and no private path leaves the packet.

``verify-detached`` re-reads a sealed directory with nothing carried over from the sealing
run, replays the verification from the sealed run alone, and emits the detached
verification receipt the post-seal closure requires.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import stc_mary_successor_flight_law as law  # noqa: E402
import stc_mary_successor_packet_runtime as runtime  # noqa: E402

PROFILE_PATH = HERE / "stc-mary-successor-packet-flight-01-profile-01.json"

RUN_CLAIM = (
    "Local private flight run for one synthetic successor packet. It carries stage terminals, "
    "content identities and counts only, holds no private evidence body or path, and grants no "
    "physical, mission, command, targeting, engagement, effector, or weapons authority."
)
DISPOSITION_CLAIM = (
    "Public disposition for one local private flight. It contains content identities, counts and "
    "claim boundaries only. It qualifies no physical estate, representative operator, field "
    "network, operational C2 or production Lattice, and grants no mission, command, targeting, "
    "engagement, effector or weapons authority."
)
MARKER_CLAIM = (
    "Marker for one local digest-only sealed flight result. Private evidence bodies remain in the "
    "packet and this directory grants no independent qualification or authority."
)
MANIFEST_CLAIM = (
    "Digest manifest for one local sealed flight result. It contains no private evidence body or "
    "path and grants no independent qualification or authority."
)
VERIFICATION_CLAIM = (
    "Detached verification of one local sealed self-attestation package. It grants no independent "
    "physical, operator, field, operational, mission, command, targeting, engagement, effector, or "
    "weapons qualification or authority."
)
STATE_CLAIM = (
    "Local packet state. It records preparation and receipt custody only and grants no physical, "
    "mission, command, targeting, engagement, effector, or weapons authority."
)


def validate_new_sealed_directory(profile: Mapping[str, Any], sealed: Path, repository: Path) -> Path:
    seal_law = profile["seal"]
    resolved = law.validate_lexical_coordinate(sealed, label="sealed directory", code="SEALED_OUTPUT_UNSAFE")
    law.require(
        re.fullmatch(seal_law["directoryPattern"], resolved.name) is not None,
        "SEALED_OUTPUT_UNSAFE",
        "the sealed directory name is outside the admitted sealed-directory pattern",
    )
    law.require(
        not law.is_within(resolved, repository),
        "SEALED_OUTPUT_UNSAFE",
        "the sealed directory must remain outside the public repository",
    )
    law.require(
        not resolved.exists() or not any(resolved.iterdir()),
        "SEALED_OUTPUT_EXISTS",
        "the sealed directory must not already carry a sealed result",
    )
    return resolved


def load_pre_seal_closure(
    profile: Mapping[str, Any], path: Path, state: Mapping[str, Any]
) -> Mapping[str, Any]:
    closure_law = profile["preSealClosure"]
    law.require(
        path.is_file(),
        "PRE_SEAL_CLOSURE_ABSENT",
        "no pre-seal closure was supplied; sealing is not permitted before the packet is closed",
    )
    closure = law.read_json_file(path, code="PRE_SEAL_CLOSURE_INVALID", label="pre-seal closure")
    law.exact_keys(closure, closure_law["keys"], "PRE_SEAL_CLOSURE_INVALID", "pre-seal closure")
    law.require(
        closure["schema"] == closure_law["schema"], "PRE_SEAL_CLOSURE_INVALID", "pre-seal closure schema differs"
    )
    law.assert_identity(
        closure, closure_law["idKey"], closure_law["idPrefix"], "PRE_SEAL_CLOSURE_INVALID", "pre-seal closure"
    )
    law.require(
        closure["status"] == closure_law["requiredStatus"],
        "PRE_SEAL_CLOSURE_INVALID",
        "the pre-seal closure did not pass",
    )
    law.require(
        closure["packetId"] == state["packetId"],
        "PRE_SEAL_CLOSURE_BINDING_INVALID",
        "the pre-seal closure closes another packet",
    )
    law.require(
        closure["stageRecordIdentityRoot"] is not None and closure["unsealed"] is True,
        "PRE_SEAL_CLOSURE_BINDING_INVALID",
        "the pre-seal closure does not close an unsealed packet",
    )
    law.require(
        closure["authority"] == law.AUTHORITY, "AUTHORITY_WIDENED", "pre-seal closure grants authority"
    )
    return closure


def seal_packet(
    *, packet: Path, sealed: Path, pre_seal_closure: Path, repository: Path, profile_path: Path = PROFILE_PATH
) -> dict[str, Any]:
    law.require_supported_python()
    packet = law.validate_lexical_coordinate(packet, label="packet root", code="PACKET_ROOT_INVALID")
    repository = law.validate_lexical_coordinate(repository, label="repository root", code="SOURCE_ROOT_INVALID")
    profile = law.load_profile(
        law.validate_lexical_coordinate(profile_path, label="successor flight profile", code="PROFILE_UNREADABLE")
    )
    admission = law.load_admission_profile(repository, profile)
    seal_law = profile["seal"]
    files = seal_law["files"]

    loaded = law.load_packet(profile, packet)
    marker, state, config = loaded["marker"], loaded["state"], loaded["config"]
    law.require(state["sealed"] is False, "PACKET_ALREADY_SEALED", "the packet is already sealed")
    law.require(
        state["completedStageCount"] == profile["denominator"]["stageDenominator"]
        and state["nextStage"] is None,
        "PACKET_INCOMPLETE",
        "all sixteen stages must be recorded before sealing",
    )
    closure = load_pre_seal_closure(
        profile,
        law.validate_lexical_coordinate(
            pre_seal_closure, label="pre-seal closure", code="PRE_SEAL_CLOSURE_ABSENT"
        ),
        state,
    )
    resolved = validate_new_sealed_directory(profile, sealed, repository)

    records = runtime.read_stage_records(profile=profile, packet=packet, state=state)
    private_bodies = runtime.verify_evidence_custody(packet=packet, records=records)
    # The sealed body count is measured from the packet, and the deciding closure already
    # measured the same set against the admitted materialization. Requiring the two to
    # agree is what stops a body being added or removed between closing and sealing.
    law.require(
        private_bodies == closure["privateEvidenceBodyCount"],
        "PRE_SEAL_CLOSURE_BINDING_INVALID",
        "the packet carries a different number of private evidence bodies than the closure measured",
    )

    attestations = []
    successful = 0
    human_required = 0
    for record in records:
        terminal = record["terminalState"]
        if terminal == "PASS":
            successful += 1
        elif terminal == "HUMAN_REQUIRED":
            human_required += 1
        else:  # pragma: no cover - the recorded terminal denominator is closed
            law.fail("STAGE_TERMINAL_INVALID", f"unknown recorded terminal {terminal}")
        row = {
            "sequence": record["sequence"],
            "stage": record["stage"],
            "terminalState": terminal,
            "canonicalMissionStateIdBefore": record["canonicalMissionStateIdBefore"],
            "canonicalMissionStateIdAfter": record["canonicalMissionStateIdAfter"],
            "observationDigest": record["observationDigest"],
            "evidenceAdmissionRoot": record["evidenceAdmissionRoot"],
            "recordDigest": record[profile["packet"]["stageRecord"]["idKey"]],
            "privateEvidenceBodyCount": len(record["evidenceFiles"]),
        }
        law.exact_keys(row, seal_law["runStageKeys"], "SEALED_RUN_INVALID", "sealed run stage attestation")
        attestations.append(row)

    expected = profile["denominator"]["recordedTerminalCounts"]
    law.require(
        successful == expected["PASS"] and human_required == expected["HUMAN_REQUIRED"],
        "RECORDED_TERMINAL_DENOMINATOR_INVALID",
        "the recorded terminal denominator differs from the admitted denominator",
    )

    run = law.sign(
        {
            "schema": seal_law["runSchema"],
            "packetId": marker["packetId"],
            "campaignLabel": marker["campaignLabel"],
            "canonicalMissionStateDigest": config["canonicalMissionStateDigest"],
            "preSealClosureId": closure[profile["preSealClosure"]["idKey"]],
            "stageAttestations": attestations,
            "stageCount": len(attestations),
            "successfulStageCount": successful,
            "humanRequiredStageCount": human_required,
            "privatePhysicalEvidenceBodyCount": private_bodies,
            "authority": law.AUTHORITY,
            "claimBoundary": RUN_CLAIM,
        },
        seal_law["runIdKey"],
        seal_law["runIdPrefix"],
    )
    law.exact_keys(run, seal_law["runKeys"], "SEALED_RUN_INVALID", "sealed run")

    disposition = law.sign(
        {
            "schema": seal_law["dispositionSchema"],
            "runId": run[seal_law["runIdKey"]],
            "packetId": marker["packetId"],
            "campaignLabel": marker["campaignLabel"],
            "stageCount": run["stageCount"],
            "successfulStageCount": successful,
            "humanRequiredStageCount": human_required,
            "publicEvidenceBodyCount": 0,
            "privatePhysicalFlightCompleted": True,
            "physicalEstateQualified": False,
            "representativeOperatorQualified": False,
            "fieldNetworkQualified": False,
            "operationalC2Qualified": False,
            "productionLatticeQualified": False,
            "missionAuthorityGranted": False,
            "commandAuthorityGranted": False,
            "authority": law.AUTHORITY,
            "claimBoundary": DISPOSITION_CLAIM,
        },
        seal_law["dispositionIdKey"],
        seal_law["dispositionIdPrefix"],
    )
    law.exact_keys(disposition, seal_law["dispositionKeys"], "SEALED_DISPOSITION_INVALID", "public disposition")

    sealed_marker = law.sign(
        {
            "schema": seal_law["markerSchema"],
            "packetId": marker["packetId"],
            "runId": run[seal_law["runIdKey"]],
            "dispositionId": disposition[seal_law["dispositionIdKey"]],
            "flightMode": seal_law["flightMode"],
            "publicEvidenceBodyCount": 0,
            "authority": law.AUTHORITY,
            "claimBoundary": MARKER_CLAIM,
        },
        seal_law["markerIdKey"],
        seal_law["markerIdPrefix"],
    )
    verification = build_verification(profile=profile, run=run, disposition=disposition, file_count=len(seal_law["manifestFiles"]))

    resolved.mkdir(parents=True, exist_ok=True)
    law.write_canonical_json(resolved / files["marker"], sealed_marker)
    law.write_canonical_json(resolved / files["run"], run)
    law.write_canonical_json(resolved / files["disposition"], disposition)
    law.write_canonical_json(resolved / files["verification"], verification)

    entries = []
    for name in seal_law["manifestFiles"]:
        data = law.read_bounded_bytes(
            resolved / name, law.MAX_JSON_BYTES, code="SEALED_FILE_INVALID", label=f"sealed file {name}"
        )
        row = {"path": name, "bytes": len(data), "sha256": law.sha256_bytes(data)}
        law.exact_keys(row, seal_law["manifestFileKeys"], "SEALED_MANIFEST_INVALID", "sealed manifest file")
        entries.append(row)
    manifest = law.sign(
        {
            "schema": seal_law["manifestSchema"],
            "runId": run[seal_law["runIdKey"]],
            "dispositionId": disposition[seal_law["dispositionIdKey"]],
            "files": entries,
            "fileCount": len(entries),
            "publicEvidenceBodyCount": 0,
            "authority": law.AUTHORITY,
            "claimBoundary": MANIFEST_CLAIM,
        },
        seal_law["manifestIdKey"],
        seal_law["manifestIdPrefix"],
    )
    law.exact_keys(manifest, seal_law["manifestKeys"], "SEALED_MANIFEST_INVALID", "sealed manifest")
    law.require(
        manifest["fileCount"] == profile["denominator"]["sealedManifestFileCount"],
        "SEALED_MANIFEST_INVALID",
        "the sealed manifest file denominator differs from the admitted denominator",
    )
    law.write_canonical_json(resolved / files["manifest"], manifest)

    next_state = law.build_packet_state(
        profile=profile,
        marker=marker,
        stages=law.stage_sequence(admission),
        rows=state["stages"],
        configuration_state="configured",
        sealed=True,
        sealed_disposition_id=disposition[seal_law["dispositionIdKey"]],
        claim_boundary=STATE_CLAIM,
    )
    law.write_canonical_json(packet / profile["packet"]["files"]["state"], next_state)
    return {
        "sealedDirectory": resolved,
        "marker": sealed_marker,
        "run": run,
        "disposition": disposition,
        "verification": verification,
        "manifest": manifest,
        "state": next_state,
    }


def build_verification(
    *, profile: Mapping[str, Any], run: Mapping[str, Any], disposition: Mapping[str, Any], file_count: int
) -> dict[str, Any]:
    """Derive the verification body from the sealed run alone.

    Sealing and detached verification both call this with the same inputs, which is what
    makes the replay comparison meaningful: a sealed directory whose verification was
    hand-written rather than derived will not reproduce.
    """
    seal_law = profile["seal"]
    body = {
        "schema": seal_law["verificationSchema"],
        "status": "PASS",
        "packetId": run["packetId"],
        "runId": run[seal_law["runIdKey"]],
        "dispositionId": disposition[seal_law["dispositionIdKey"]],
        "fileCount": file_count,
        "stageCount": run["stageCount"],
        "privatePhysicalEvidenceBodyCount": run["privatePhysicalEvidenceBodyCount"],
        "publicEvidenceBodyCount": 0,
        "bodyFreePublicDisposition": True,
        "deterministicReceiptReplay": True,
        "physicalEstateQualified": False,
        "representativeOperatorQualified": False,
        "fieldNetworkQualified": False,
        "operationalC2Qualified": False,
        "productionLatticeQualified": False,
        "missionAuthorityGranted": False,
        "commandAuthorityGranted": False,
        "authority": law.AUTHORITY,
        "claimBoundary": VERIFICATION_CLAIM,
    }
    signed = law.sign(body, seal_law["verificationIdKey"], seal_law["verificationIdPrefix"])
    law.exact_keys(signed, seal_law["verificationKeys"], "SEALED_VERIFICATION_INVALID", "sealed verification")
    return signed


# --------------------------------------------------------------------------------
# detached verification
# --------------------------------------------------------------------------------


def verify_detached(*, sealed: Path, repository: Path, profile_path: Path = PROFILE_PATH) -> dict[str, Any]:
    """Re-read one sealed directory carrying nothing over from the sealing run."""
    law.require_supported_python()
    sealed = law.validate_lexical_coordinate(sealed, label="sealed directory", code="SEALED_OUTPUT_UNSAFE")
    repository = law.validate_lexical_coordinate(repository, label="repository root", code="SOURCE_ROOT_INVALID")
    profile = law.load_profile(
        law.validate_lexical_coordinate(profile_path, label="successor flight profile", code="PROFILE_UNREADABLE")
    )
    seal_law = profile["seal"]
    files = seal_law["files"]
    law.require(
        not law.is_within(sealed, repository),
        "SEALED_OUTPUT_UNSAFE",
        "the sealed directory must remain outside the public repository",
    )

    marker = law.read_json_file(sealed / files["marker"], code="SEALED_MARKER_INVALID", label="sealed marker")
    law.exact_keys(marker, seal_law["markerKeys"], "SEALED_MARKER_INVALID", "sealed marker")
    law.assert_identity(
        marker, seal_law["markerIdKey"], seal_law["markerIdPrefix"], "SEALED_MARKER_INVALID", "sealed marker"
    )
    law.require(
        marker["schema"] == seal_law["markerSchema"] and marker["flightMode"] == seal_law["flightMode"],
        "SEALED_MARKER_INVALID",
        "sealed marker schema or flight mode differs",
    )
    law.require(
        marker["publicEvidenceBodyCount"] == 0 and marker["authority"] == law.AUTHORITY,
        "SEALED_MARKER_INVALID",
        "sealed marker widens evidence or authority",
    )

    manifest = law.read_json_file(sealed / files["manifest"], code="SEALED_MANIFEST_INVALID", label="sealed manifest")
    law.exact_keys(manifest, seal_law["manifestKeys"], "SEALED_MANIFEST_INVALID", "sealed manifest")
    law.assert_identity(
        manifest, seal_law["manifestIdKey"], seal_law["manifestIdPrefix"], "SEALED_MANIFEST_INVALID", "sealed manifest"
    )
    law.require(
        manifest["runId"] == marker["runId"] and manifest["dispositionId"] == marker["dispositionId"],
        "SEALED_BINDING_INVALID",
        "the sealed manifest belongs to another marker",
    )
    law.require(
        manifest["fileCount"] == len(manifest["files"])
        and manifest["fileCount"] == profile["denominator"]["sealedManifestFileCount"]
        and [row["path"] for row in manifest["files"]] == list(seal_law["manifestFiles"]),
        "SEALED_MANIFEST_INVALID",
        "the sealed manifest file denominator differs",
    )
    for row in manifest["files"]:
        law.exact_keys(row, seal_law["manifestFileKeys"], "SEALED_MANIFEST_INVALID", "sealed manifest file")
        data = law.read_bounded_bytes(
            sealed / row["path"], law.MAX_JSON_BYTES, code="SEALED_FILE_MISMATCH", label=f"sealed file {row['path']}"
        )
        law.require(
            len(data) == row["bytes"] and law.sha256_bytes(data) == row["sha256"],
            "SEALED_FILE_MISMATCH",
            f"sealed file differs from the manifest: {row['path']}",
        )

    run = law.read_json_file(sealed / files["run"], code="SEALED_RUN_INVALID", label="sealed run")
    law.exact_keys(run, seal_law["runKeys"], "SEALED_RUN_INVALID", "sealed run")
    law.assert_identity(run, seal_law["runIdKey"], seal_law["runIdPrefix"], "SEALED_RUN_INVALID", "sealed run")
    disposition = law.read_json_file(
        sealed / files["disposition"], code="SEALED_DISPOSITION_INVALID", label="public disposition"
    )
    law.exact_keys(disposition, seal_law["dispositionKeys"], "SEALED_DISPOSITION_INVALID", "public disposition")
    law.assert_identity(
        disposition,
        seal_law["dispositionIdKey"],
        seal_law["dispositionIdPrefix"],
        "SEALED_DISPOSITION_INVALID",
        "public disposition",
    )
    law.require(
        marker["runId"] == run[seal_law["runIdKey"]]
        and marker["dispositionId"] == disposition[seal_law["dispositionIdKey"]]
        and disposition["runId"] == run[seal_law["runIdKey"]]
        and marker["packetId"] == run["packetId"] == disposition["packetId"],
        "SEALED_BINDING_INVALID",
        "the sealed marker, run and disposition do not name one flight",
    )

    stored = law.read_json_file(
        sealed / files["verification"], code="SEALED_VERIFICATION_INVALID", label="sealed verification"
    )
    replayed = build_verification(
        profile=profile, run=run, disposition=disposition, file_count=manifest["fileCount"]
    )
    law.require(
        law.canonical_json(stored) == law.canonical_json(replayed),
        "SEALED_VERIFICATION_MISMATCH",
        "the stored verification does not reproduce from the sealed run alone",
    )
    return replayed


def refusal_document(schema: str, code: str, message: str) -> dict[str, Any]:
    return {
        "schema": schema,
        "status": "REFUSED",
        "code": code,
        "message": message,
        "authority": law.AUTHORITY,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seal one closed 0.2 successor packet and verify it detached")
    sub = parser.add_subparsers(dest="command", required=True)
    seal = sub.add_parser("seal", help="seal one packet already closed at sixteen of sixteen")
    seal.add_argument("--packet", type=Path, required=True)
    seal.add_argument("--sealed", type=Path, required=True)
    seal.add_argument("--pre-seal-closure", type=Path, required=True)
    seal.add_argument("--repository-root", type=Path, default=HERE.parent.parent)
    seal.add_argument("--out", type=Path)
    detached = sub.add_parser("verify-detached", help="verify one sealed directory with nothing carried over")
    detached.add_argument("--sealed", type=Path, required=True)
    detached.add_argument("--repository-root", type=Path, default=HERE.parent.parent)
    detached.add_argument("--out", type=Path)
    return parser.parse_args(argv)


def emit(value: Mapping[str, Any], out: Path | None) -> None:
    data = law.canonical_json_bytes(value)
    if out is None:
        sys.stdout.buffer.write(data)
        return
    path = law.validate_lexical_coordinate(out, label="receipt output", code="RECEIPT_PATH_INVALID")
    law.require(not path.exists(), "RECEIPT_OUTPUT_EXISTS", "receipt output must not already exist")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    schema = "stc-mary/successor-flight-sealed-verification/1"
    try:
        if args.command == "seal":
            result = seal_packet(
                packet=args.packet,
                sealed=args.sealed,
                pre_seal_closure=args.pre_seal_closure,
                repository=args.repository_root,
            )
            emit(
                {
                    "schema": "stc-mary/successor-flight-seal-receipt/1",
                    "status": "SEALED",
                    "packetId": result["marker"]["packetId"],
                    "runId": result["marker"]["runId"],
                    "dispositionId": result["marker"]["dispositionId"],
                    "manifestId": result["manifest"]["manifestId"],
                    "authority": law.AUTHORITY,
                },
                args.out,
            )
            return 0
        emit(verify_detached(sealed=args.sealed, repository=args.repository_root), args.out)
        return 0
    except law.SuccessorFlightError as exc:
        sys.stdout.buffer.write(law.canonical_json_bytes(refusal_document(schema, exc.code, str(exc))))
        return 1
    except (OSError, ValueError) as exc:
        sys.stdout.buffer.write(
            law.canonical_json_bytes(refusal_document(schema, "SEAL_ADAPTER_FILESYSTEM_ERROR", str(exc)))
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
