from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import ADMITTED_PACKET_COMMIT, BACKENDS, TOOLCHAIN_PROFILE_ID, TOOLCHAIN_SCHEMA, read_json, require, stable_keys


def validate_profile(path: Path) -> dict[str, Any]:
    profile = read_json(path)
    stable_keys(profile, [
        "schema", "profileId", "status", "predecessorCommit", "privateOutputPatterns", "commands", "backends",
        "localObservations", "flightPlanGates", "claimBoundary",
    ], "TOOLCHAIN_PROFILE_INVALID", "toolchain profile")
    require(profile["schema"] == TOOLCHAIN_SCHEMA and profile["profileId"] == TOOLCHAIN_PROFILE_ID, "TOOLCHAIN_PROFILE_INVALID", "toolchain profile schema or identity differs")
    require(profile["status"] == "candidate_design_only" and profile["predecessorCommit"] == ADMITTED_PACKET_COMMIT, "TOOLCHAIN_PROFILE_INVALID", "toolchain status or predecessor differs")
    require(profile["privateOutputPatterns"] == [
        "^stc-mary-local-prep-[a-z0-9][a-z0-9._-]*$",
        "^stc-mary-local-feed-[a-z0-9][a-z0-9._-]*$",
        "^stc-mary-local-plan-[a-z0-9][a-z0-9._-]*$",
    ], "TOOLCHAIN_PROFILE_INVALID", "private output patterns differ")
    require(profile["commands"] == ["doctor", "generate-feed", "run-workload", "verify-workload", "compare-workloads", "compile-plan", "validate-profile"], "TOOLCHAIN_PROFILE_INVALID", "command denominator differs")
    require(profile["backends"] == list(BACKENDS), "TOOLCHAIN_PROFILE_INVALID", "backend denominator differs")
    require(isinstance(profile["localObservations"], list) and len(profile["localObservations"]) >= 10, "TOOLCHAIN_PROFILE_INVALID", "local observation denominator is incomplete")
    require(profile["flightPlanGates"] == ["admitted_checkout", "personal_floor", "halo3", "post_halo3_continuity", "lattice_absence", "two_cell_partition", "successor_head", "private_evidence_root"], "TOOLCHAIN_PROFILE_INVALID", "flight-plan gate denominator differs")
    return profile
