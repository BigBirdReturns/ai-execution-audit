from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from .common import (
    STAGES,
    TOOLCHAIN_PROFILE_ID,
    assert_content_id,
    assert_sha256,
    bounded_string,
    canonical_json,
    content_id,
    read_json,
    require,
    sha256_bytes,
    stable_keys,
    validate_new_private_root,
    write_json,
)
from .workload import validate_feed_manifest, validate_workload_result


def load_optional_json(path: str | None) -> dict[str, Any] | None:
    return read_json(Path(path)) if path else None


def gate(name: str, status: str, evidence: Sequence[str], wake_condition: str | None = None) -> dict[str, Any]:
    require(status in {"READY", "HOLD", "REFUSE"}, "PLAN_GATE_INVALID", "plan gate status differs")
    body = {"name": name, "status": status, "evidence": list(evidence), "wakeCondition": wake_condition}
    return {**body, "gateId": content_id("stcmarylocalflightgate1", body)}


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def compile_plan(args: Any) -> dict[str, Any]:
    readiness = read_json(Path(args.readiness))
    stable_keys(readiness, [
        "schema", "readinessId", "profileId", "capturedAtUnixNs", "host", "repository", "commands", "pythonModules", "torch",
        "nvidiaQuery", "nvidiaGpus", "windows", "artifacts", "externalServiceCalls", "operationalCredentials", "authority", "claimBoundary",
    ], "READINESS_PRIVATE_INVALID", "readiness private record")
    assert_content_id(readiness["readinessId"], "READINESS_PRIVATE_INVALID", "readiness ID")
    baseline = read_json(Path(args.baseline))
    validate_workload_result(baseline)
    accelerated = load_optional_json(args.accelerated)
    continuity = load_optional_json(args.continuity)
    if accelerated:
        validate_workload_result(accelerated)
    if continuity:
        validate_workload_result(continuity)
    feed_manifest = read_json(Path(args.feed) / "feed-manifest.json")
    validate_feed_manifest(feed_manifest, Path(args.feed).resolve())
    output = validate_new_private_root(Path(args.out), repository_root=Path(args.repository))
    output.mkdir()

    required_commit = bounded_string(args.required_commit, "PLAN_REQUIRED_COMMIT_INVALID", "required commit", 40)
    require(re.fullmatch(r"[0-9a-f]{40}", required_commit) is not None, "PLAN_REQUIRED_COMMIT_INVALID", "required commit must be a full lowercase Git SHA-1")
    campaign_label = bounded_string(args.campaign_label, "PLAN_CAMPAIGN_LABEL_INVALID", "campaign label", 256)
    require(not campaign_label.startswith("REPLACE_WITH_"), "PLAN_CAMPAIGN_LABEL_INVALID", "campaign label remains a placeholder")

    gates: list[dict[str, Any]] = []
    repo_head = readiness["repository"]["head"]
    checkout_ready = repo_head == required_commit and readiness["repository"]["clean"]
    gates.append(gate(
        "admitted_checkout",
        "READY" if checkout_ready else "HOLD",
        [readiness["readinessId"]],
        None if checkout_ready else f"checkout exact admitted toolchain commit {required_commit} with a clean worktree",
    ))
    require(baseline["backend"] != "torch-cuda" and baseline["deviceClass"].startswith("resident_cpu"), "PLAN_BASELINE_INVALID", "baseline must be a resident-floor CPU result")
    gates.append(gate("personal_floor", "READY", [baseline["resultId"]]))
    halo3_ready = bool(
        accelerated
        and accelerated["backend"] == "torch-cuda"
        and accelerated["deviceClass"].startswith("cuda_accelerator")
        and accelerated["semanticOutputSha256"] == baseline["semanticOutputSha256"]
        and accelerated["throughputRecordsPerSecond"] > baseline["throughputRecordsPerSecond"]
    )
    gates.append(gate(
        "halo3",
        "READY" if halo3_ready else "HOLD",
        [accelerated["resultId"]] if accelerated else [],
        None if halo3_ready else "run the same feed through torch-cuda on one admitted 24 GiB-class seat and prove identical semantic output with higher throughput",
    ))
    continuity_ready = bool(
        continuity
        and continuity["backend"] != "torch-cuda"
        and continuity["deviceClass"].startswith("resident_cpu")
        and continuity["semanticOutputSha256"] == baseline["semanticOutputSha256"]
    )
    gates.append(gate(
        "post_halo3_continuity",
        "READY" if continuity_ready else "HOLD",
        [continuity["resultId"]] if continuity else [],
        None if continuity_ready else "remove or make HALO3 inaccessible, rerun the resident floor, and preserve the baseline semantic output",
    ))
    windows = readiness.get("windows", {})
    parsed = windows.get("parsed", {}) if isinstance(windows, Mapping) else {}
    lattice_probe_complete = bool(isinstance(windows, Mapping) and windows.get("applicable") is True and "latticeProcesses" in parsed and "latticeServices" in parsed)
    lattice_absent = lattice_probe_complete and not _list(parsed.get("latticeProcesses")) and not _list(parsed.get("latticeServices"))
    gates.append(gate(
        "lattice_absence",
        "READY" if lattice_absent else "HOLD",
        [readiness["readinessId"]],
        None if lattice_absent else "complete the Windows process and service probe with the optional Lattice-shaped surface absent",
    ))
    gates.append(gate("two_cell_partition", "HOLD", [], "bind a second independently executable cell and create two offline state bundles from one common state"))
    gates.append(gate("successor_head", "HOLD", [], "bind and verify a second host or successor medium that can run the cold-successor verifier without repository history"))
    gates.append(gate("private_evidence_root", "READY", [readiness["readinessId"]]))

    source_digests = [
        artifact["files"][0]["sha256"]
        if artifact["kind"] == "file" and artifact["fileCount"] == 1
        else sha256_bytes(canonical_json({key: value for key, value in artifact.items() if key != "privatePath"}).encode("utf-8"))
        for artifact in readiness["artifacts"]
    ]
    source_digests.extend([
        assert_sha256(feed_manifest["featureSha256"], "PLAN_INPUT_INVALID", "feed feature digest"),
        assert_sha256(baseline["semanticOutputSha256"], "PLAN_INPUT_INVALID", "baseline semantic digest"),
    ])
    source_digests = sorted(set(source_digests))
    canonical_state_digest = sha256_bytes(canonical_json({
        "feedId": feed_manifest["feedId"],
        "semanticOutputSha256": baseline["semanticOutputSha256"],
        "authorityBoundary": "named_human_bind",
        "externalServiceCalls": 0,
        "operationalCredentials": 0,
    }).encode("utf-8"))
    config = {
        "schema": "stc-mary-private-flight-packet-config/1",
        "campaignLabel": campaign_label,
        "sourceObjectDigests": source_digests,
        "identityClasses": {
            "personalFloor": "private_resident_cpu_execution_seat",
            "halo3": "private_optional_24gib_cuda_accelerator",
            "initialHead": "private_initial_windows_head",
            "successorHead": "REPLACE_WITH_PRIVATE_SUCCESSOR_HEAD",
            "graceBind": "named_human_operator_grace",
            "lattice": "private_optional_interoperability_membrane",
            "leftCell": "REPLACE_WITH_PRIVATE_LEFT_CELL",
            "rightCell": "REPLACE_WITH_PRIVATE_RIGHT_CELL",
        },
        "canonicalMissionStateDigest": canonical_state_digest,
        "authority": "none",
        "claimBoundary": "Generated local packet configuration. Replace every unbound identity class before packet configuration; no machine acquires authority.",
    }
    ready_names = {row["name"] for row in gates if row["status"] == "READY"}
    stages: list[dict[str, Any]] = []
    for index, stage in enumerate(STAGES, start=1):
        status = "READY_TO_RECORD" if stage in {"VERIFY_INPUTS", "MOUNT_PERSONAL_FLOOR", "BIND_GRACE", "RUN_PERSONAL_FLOOR_BASELINE"} else "HOLD"
        if stage in {"ATTACH_HALO3", "RUN_HALO3_ACCELERATED"} and "halo3" in ready_names:
            status = "READY_TO_RECORD"
        if stage in {"REMOVE_HALO3", "VERIFY_PERSONAL_FLOOR_CONTINUITY"} and "post_halo3_continuity" in ready_names:
            status = "READY_TO_RECORD"
        if stage in {"REMOVE_LATTICE", "VERIFY_LOCAL_CONTINUITY"} and "lattice_absence" in ready_names:
            status = "READY_TO_RECORD"
        if stage in {"PARTITION_TWO_CELLS", "RESTORE_LINK_HOLD_CONFLICT"} and "two_cell_partition" in ready_names:
            status = "READY_TO_RECORD"
        if stage in {"REPLACE_HEAD", "COLD_SUCCESSOR_VERIFY"} and "successor_head" in ready_names:
            status = "READY_TO_RECORD"
        if stage in {"REBUILD_PROJECTIONS", "SEAL_PRIVATE_EVIDENCE"}:
            status = "READY_AFTER_PREDECESSORS"
        stages.append({"sequence": index, "stage": stage, "status": status})

    plan_body = {
        "schema": "stc-mary-local-flight-plan/1",
        "profileId": TOOLCHAIN_PROFILE_ID,
        "campaignLabel": campaign_label,
        "requiredCommit": required_commit,
        "readinessId": readiness["readinessId"],
        "feedId": feed_manifest["feedId"],
        "baselineResultId": baseline["resultId"],
        "acceleratedResultId": accelerated["resultId"] if accelerated else None,
        "continuityResultId": continuity["resultId"] if continuity else None,
        "gates": gates,
        "stagePlan": stages,
        "readyGateCount": sum(1 for row in gates if row["status"] == "READY"),
        "holdGateCount": sum(1 for row in gates if row["status"] == "HOLD"),
        "refuseGateCount": sum(1 for row in gates if row["status"] == "REFUSE"),
        "flightExecuted": False,
        "physicalEstateQualified": False,
        "representativeOperatorQualified": False,
        "fieldNetworkQualified": False,
        "operationalC2Qualified": False,
        "productionLatticeQualified": False,
        "externalServiceCalls": 0,
        "operationalCredentials": 0,
        "authority": "none",
        "claimBoundary": "Local preparation plan for issue 37. It reports readiness and wake conditions only and does not claim that the physical flight occurred or grant any physical, mission, command, targeting, engagement, effector, or weapons authority.",
    }
    plan = {**plan_body, "planId": content_id("stcmarylocalflightplan1", plan_body)}
    marker_body = {
        "schema": "stc-mary-local-plan-root/1",
        "profileId": TOOLCHAIN_PROFILE_ID,
        "planId": plan["planId"],
        "authority": "none",
        "claimBoundary": "Marker for one private local plan root outside public Git.",
    }
    write_json(output / "PLAN-ROOT.json", {**marker_body, "markerId": content_id("stcmarylocalplanroot1", marker_body)})
    write_json(output / "local-flight-plan.json", plan)
    write_json(output / "flight-config.generated.json", config)
    next_actions = f"""# STC MARY local flight handoff

Plan: `{plan['planId']}`

Ready gates: {plan['readyGateCount']}  
Hold gates: {plan['holdGateCount']}  
Refuse gates: {plan['refuseGateCount']}

Do not configure the admitted packet until every `REPLACE_WITH_` identity class in `flight-config.generated.json` has been replaced with a private local identity class and the checkout gate is READY.

```powershell
$Repo = 'PATH_TO_EXACT_ADMITTED_CHECKOUT'
$Packet = 'PATH_OUTSIDE_REPOSITORY\\stc-mary-private-flight-local-01'
$Runner = Join-Path $Repo 'mating_surface\\anchor_node\\stc-mary-private-flight.ps1'
& $Runner init $Packet '{campaign_label}'
& $Runner configure $Packet '{str((output / 'flight-config.generated.json').resolve())}'
& $Runner status $Packet
```

The two-cell and successor-HEAD gates remain separate physical transactions. No hold may be edited into READY without a new evidence receipt.
"""
    (output / "NEXT-ACTIONS.md").write_text(next_actions, encoding="utf-8", newline="\n")
    return {"status": "PASS", "output": str(output), "planId": plan["planId"], "readyGates": plan["readyGateCount"], "holdGates": plan["holdGateCount"]}
