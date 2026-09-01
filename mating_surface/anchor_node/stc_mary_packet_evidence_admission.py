"""Operator front-end for the packet evidence admission gate.

This module owns no admission law. Every predicate lives in
``verify_stc_mary_packet_evidence_admission.py`` so that the bytes an operator runs
here and the bytes the external bootstrap measures and executes are the same bytes.
This front-end only resolves coordinates, selects a lane, and prints.

It cannot record a packet stage, set ``operatorConfirmed``, sign a named-human
statement, or issue a stage confirmation, because none of those operations exist in
the law module it calls.

Lanes
-----
``admit``           run the admitted gate in this process (not bootstrap-authenticated)
``bootstrap-admit`` run the external bootstrap, which measures the gate and executes
                    the measured copy from a foreign temporary directory
``profile-digest``  print the canonical digest of the admitted profile, for pinning
``source-set``      print the admission source set receipt, separately identified
``denominator``     print the closed sixteen-stage, forty-three-role evidence
                    denominator this gate enforces, with no campaign coordinate
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPOSITORY_ROOT = HERE.parent.parent
DEFAULT_PROFILE = HERE / "stc-mary-packet-evidence-admission-profile-01.json"
BOOTSTRAP = HERE / "verify_stc_mary_packet_evidence_admission_bootstrap.py"

sys.path.insert(0, str(HERE))

import verify_stc_mary_packet_evidence_admission as law  # noqa: E402


def emit(value: Any) -> None:
    sys.stdout.buffer.write(law.canonical_json_bytes(value))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Operator front-end for the STC MARY packet evidence admission gate"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("admit", "bootstrap-admit"):
        lane = sub.add_parser(name)
        lane.add_argument("--workstation", type=Path, required=True)
        lane.add_argument("--packet", type=Path, required=True)
        lane.add_argument("--candidates", type=Path, required=True)
        lane.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
        lane.add_argument("--admission-source-root", type=Path, default=REPOSITORY_ROOT)
        lane.add_argument("--out", type=Path)

    digest = sub.add_parser("profile-digest")
    digest.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)

    source = sub.add_parser("source-set")
    source.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    source.add_argument("--admission-source-root", type=Path, default=REPOSITORY_ROOT)

    denominator = sub.add_parser("denominator")
    denominator.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)

    return parser.parse_args(argv)


def denominator_document(profile: Any) -> dict[str, Any]:
    rows = []
    for stage in profile["stageSequence"]:
        stage_law = profile["stages"][stage]
        rows.append(
            {
                "sequence": stage_law["sequence"],
                "stage": stage,
                "availabilityClass": stage_law["availabilityClass"],
                "requiredTerminal": stage_law["requiredTerminal"],
                "evidenceRoleDenominator": stage_law["evidenceRoleDenominator"],
                "evidenceRoles": [
                    {
                        "evidenceRole": row["evidenceRole"],
                        "provenanceClass": row["provenanceClass"],
                        "requiredPredicates": sorted(row["requiredPredicates"]),
                    }
                    for row in stage_law["evidenceRoles"]
                ],
            }
        )
    body = {
        "schema": "stc-mary/packet-evidence-admission-denominator/1",
        "profileId": profile["profileId"],
        "terminalStates": profile["terminalStates"],
        "denominator": profile["denominator"],
        "stages": rows,
        "packetStagesRecorded": 0,
        "operatorConfirmedFlagsSet": 0,
        "authority": law.AUTHORITY,
    }
    return {**body, "denominatorId": law.content_id("stcmarypacketevidenceadmissiondenominator1", body)}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.command == "profile-digest":
            profile = law.load_profile(args.profile)
            emit(
                {
                    "schema": "stc-mary/packet-evidence-admission-profile-digest/1",
                    "profileId": profile["profileId"],
                    "canonicalSha256": law.sha256_bytes(law.canonical_json_bytes(profile)),
                    "authority": law.AUTHORITY,
                }
            )
            return 0

        if args.command == "denominator":
            emit(denominator_document(law.load_profile(args.profile)))
            return 0

        if args.command == "source-set":
            profile = law.load_profile(args.profile)
            emit(
                law.measure_source_set(
                    law.validate_lexical_coordinate(
                        args.admission_source_root,
                        label="admission source root",
                        code="ADMISSION_SOURCE_SET_INVALID",
                    ),
                    profile["admissionSourceMembers"],
                    schema=law.SOURCE_SET_SCHEMA,
                    profile_id=law.PROFILE_ID,
                    claim_boundary=law.SOURCE_SET_CLAIM_BOUNDARY,
                    id_key="sourceSetId",
                    id_prefix=law.SOURCE_SET_ID_PREFIX,
                    code="ADMISSION_SOURCE_SET_INVALID",
                    label="admission source set",
                )
            )
            return 0

        if args.command == "bootstrap-admit":
            command = [
                sys.executable,
                str(BOOTSTRAP),
                "--workstation",
                str(args.workstation),
                "--packet",
                str(args.packet),
                "--candidates",
                str(args.candidates),
                "--profile",
                str(args.profile),
                "--admission-source-root",
                str(args.admission_source_root),
            ]
            if args.out is not None:
                command.extend(["--out", str(args.out)])
            completed = subprocess.run(command, check=False, capture_output=True)
            sys.stdout.buffer.write(completed.stdout)
            return completed.returncode

        return law.main(
            [
                "--workstation",
                str(args.workstation),
                "--packet",
                str(args.packet),
                "--candidates",
                str(args.candidates),
                "--profile",
                str(args.profile),
                "--admission-source-root",
                str(args.admission_source_root),
            ]
            + ([] if args.out is None else ["--out", str(args.out)])
        )
    except law.AdmissionError as exc:
        emit(law.refusal_document(exc.code, str(exc)))
        return 1
    except (OSError, ValueError) as exc:
        emit(law.refusal_document("ADMISSION_FILESYSTEM_ERROR", str(exc)))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
