from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .common import BACKENDS, ToolchainError
from .plan import compile_plan
from .profile import validate_profile
from .readiness import doctor_command
from .workload import compare_workloads, generate_feed, run_workload, verify_workload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Provider-free local preparation tools for the STC MARY physical flight.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="capture one private local readiness observation")
    doctor.add_argument("--repository", required=True)
    doctor.add_argument("--out", required=True)
    doctor.add_argument("--artifact", action="append", default=[], metavar="LABEL=PATH")
    doctor.set_defaults(func=doctor_command)

    feed = subparsers.add_parser("generate-feed", help="generate a deterministic invented local feed")
    feed.add_argument("--out", required=True)
    feed.add_argument("--records", type=int, default=262144)
    feed.add_argument("--features", type=int, default=32)
    feed.add_argument("--classes", type=int, default=8)
    feed.add_argument("--seed", type=int, default=20260827)
    feed.set_defaults(func=generate_feed)

    workload = subparsers.add_parser("run-workload", help="run the deterministic aperture workload")
    workload.add_argument("--feed", required=True)
    workload.add_argument("--backend", choices=BACKENDS, required=True)
    workload.add_argument("--device-index", type=int, default=0)
    workload.add_argument("--out", required=True)
    workload.set_defaults(func=run_workload)

    verify = subparsers.add_parser("verify-workload", help="independently verify one workload result")
    verify.add_argument("--feed", required=True)
    verify.add_argument("--result", required=True)
    verify.add_argument("--out", required=True)
    verify.set_defaults(func=verify_workload)

    compare = subparsers.add_parser("compare-workloads", help="compare baseline, accelerated, and post-removal outputs")
    compare.add_argument("--baseline", required=True)
    compare.add_argument("--accelerated", required=True)
    compare.add_argument("--continuity", required=True)
    compare.add_argument("--out", required=True)
    compare.set_defaults(func=compare_workloads)

    plan = subparsers.add_parser("compile-plan", help="compile readiness and workload receipts into a local flight plan")
    plan.add_argument("--repository", required=True)
    plan.add_argument("--readiness", required=True)
    plan.add_argument("--feed", required=True)
    plan.add_argument("--baseline", required=True)
    plan.add_argument("--accelerated")
    plan.add_argument("--continuity")
    plan.add_argument("--cell-verification")
    plan.add_argument("--successor-verification")
    plan.add_argument("--campaign-label", required=True)
    plan.add_argument("--required-commit", required=True)
    plan.add_argument("--out", required=True)
    plan.set_defaults(func=compile_plan)

    profile = subparsers.add_parser("validate-profile", help="validate the closed toolchain profile")
    profile.add_argument("path")
    profile.set_defaults(func=lambda args: {"status": "PASS", "profileId": validate_profile(Path(args.path))["profileId"]})
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        print(json.dumps(args.func(args), indent=2, ensure_ascii=False))
        return 0
    except ToolchainError as error:
        print(f"{error.code}: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("INTERRUPTED: operator interrupted the local toolchain", file=sys.stderr)
        return 130
