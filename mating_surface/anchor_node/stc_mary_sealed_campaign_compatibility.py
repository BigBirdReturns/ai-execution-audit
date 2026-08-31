"""Operator front-end for the sealed-campaign compatibility verifier.

This module owns no verification law. Every predicate lives in
``verify_stc_mary_sealed_campaign_compatibility.py`` so that the bytes an operator
runs here and the bytes the external bootstrap measures and executes are the same
bytes. This front-end only resolves coordinates, selects a lane, and prints.

Lanes
-----
``verify``          run the admitted verifier in this process (not bootstrap-authenticated)
``bootstrap-verify``run the external bootstrap, which measures the verifier and executes
                    the measured copy from a foreign temporary directory
``profile-digest``  print the canonical digest of the admitted profile, for pinning
``source-set``      print the repair verifier source set receipt, separately identified
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
DEFAULT_PROFILE = HERE / "stc-mary-sealed-campaign-compatibility-profile-01.json"
BOOTSTRAP = HERE / "verify_stc_mary_sealed_campaign_compatibility_bootstrap.py"

sys.path.insert(0, str(HERE))

import verify_stc_mary_sealed_campaign_compatibility as law  # noqa: E402


def emit(value: Any) -> None:
    sys.stdout.buffer.write(law.canonical_json_bytes(value))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Operator front-end for the STC MARY sealed-campaign compatibility verifier"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("verify", "bootstrap-verify"):
        lane = sub.add_parser(name)
        lane.add_argument("--workstation", type=Path, required=True)
        lane.add_argument("--conductor-checkout", type=Path, required=True)
        lane.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
        lane.add_argument("--repair-source-root", type=Path, default=REPOSITORY_ROOT)
        lane.add_argument("--out", type=Path)

    digest = sub.add_parser("profile-digest")
    digest.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)

    source = sub.add_parser("source-set")
    source.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    source.add_argument("--repair-source-root", type=Path, default=REPOSITORY_ROOT)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.command == "profile-digest":
            profile = law.load_profile(args.profile)
            emit(
                {
                    "schema": "stc-mary/sealed-campaign-compatibility-profile-digest/1",
                    "profileId": profile["profileId"],
                    "canonicalSha256": law.sha256_bytes(law.canonical_json_bytes(profile)),
                    "authority": law.AUTHORITY,
                }
            )
            return 0

        if args.command == "source-set":
            profile = law.load_profile(args.profile)
            emit(
                law.measure_source_set(
                    law.validate_lexical_coordinate(
                        args.repair_source_root, label="repair source root", code="REPAIR_SOURCE_SET_INVALID"
                    ),
                    profile["repairSourceMembers"],
                    schema=law.REPAIR_SOURCE_SET_SCHEMA,
                    profile_id=law.PROFILE_ID,
                    claim_boundary=law.REPAIR_SOURCE_SET_CLAIM_BOUNDARY,
                    id_key="sourceSetId",
                    id_prefix=law.REPAIR_SOURCE_SET_ID_PREFIX,
                    code="REPAIR_SOURCE_SET_INVALID",
                    label="repair verifier source set",
                )
            )
            return 0

        if args.command == "bootstrap-verify":
            command = [
                sys.executable,
                str(BOOTSTRAP),
                "--workstation",
                str(args.workstation),
                "--conductor-checkout",
                str(args.conductor_checkout),
                "--profile",
                str(args.profile),
                "--repair-source-root",
                str(args.repair_source_root),
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
                "--conductor-checkout",
                str(args.conductor_checkout),
                "--profile",
                str(args.profile),
                "--repair-source-root",
                str(args.repair_source_root),
            ]
            + ([] if args.out is None else ["--out", str(args.out)])
        )
    except law.CompatibilityError as exc:
        emit(law.refusal_document(exc.code, str(exc)))
        return 1
    except (OSError, ValueError) as exc:
        emit(law.refusal_document("COMPATIBILITY_FILESYSTEM_ERROR", str(exc)))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
