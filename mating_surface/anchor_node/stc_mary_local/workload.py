from __future__ import annotations

import platform
from pathlib import Path
from typing import Any

from .common import BACKENDS, content_id, read_json, require, sha256_bytes, write_json
from .workload_feed import load_feed, validate_feed_manifest
from .halo3_seat import load_halo3_seat_config, resolve_halo3_seat
from .readiness import torch_probe
from .workload_compute import (
    classify_numpy,
    classify_python,
    classify_torch,
    semantic_digest,
    validate_workload_result,
    workload_result_body,
)

__all__ = [
    "generate_feed",
    "validate_feed_manifest",
    "validate_workload_result",
    "run_workload",
    "verify_workload",
    "compare_workloads",
]
from .workload_feed import generate_feed

def run_workload(args: Any) -> dict[str, Any]:
    manifest, feature_path, record_count, feature_count, class_count, weights = load_feed(Path(args.feed))
    backend = args.backend
    require(backend in BACKENDS, "BACKEND_INVALID", "backend differs")
    halo3_seat_id = None
    observed_cuda_device_index = None
    if backend == "python":
        class_ids, counts, elapsed = classify_python(feature_path, record_count, feature_count, class_count, weights)
        backend_version, device_class, compute = platform.python_version(), "resident_cpu", elapsed
    elif backend == "numpy":
        class_ids, counts, elapsed, backend_version = classify_numpy(feature_path, record_count, feature_count, class_count, weights)
        device_class, compute = "resident_cpu", elapsed
    elif backend == "torch-cpu":
        class_ids, counts, elapsed, backend_version, compute, device_class = classify_torch(feature_path, record_count, feature_count, class_count, weights, cuda=False, device_index=0)
    else:
        require(args.halo3_seat_config is not None, "HALO3_SEAT_CONFIG_REQUIRED", "torch-cuda requires one exact HALO3 seat config")
        seat = load_halo3_seat_config(args.halo3_seat_config)
        torch = torch_probe()
        require(
            torch.get("cudaAvailable") is True,
            "HALO3_TORCH_INVENTORY_UNAVAILABLE",
            "Torch CUDA inventory is unavailable for exact-seat resolution",
        )
        observation = resolve_halo3_seat(
            seat,
            torch_devices=torch.get("devices", []),
        )
        observed_cuda_device_index = observation["currentCudaDeviceIndex"]
        if args.device_index is not None:
            require(
                args.device_index == observed_cuda_device_index,
                "HALO3_CUDA_INDEX_OBSERVATION_MISMATCH",
                "requested CUDA index differs from the exact HALO3 seat's current observation",
            )
        class_ids, counts, elapsed, backend_version, compute, device_class = classify_torch(
            feature_path,
            record_count,
            feature_count,
            class_count,
            weights,
            cuda=True,
            device_index=observed_cuda_device_index,
        )
        device_class = "cuda_accelerator"
        halo3_seat_id = seat["seatId"]
    body = workload_result_body(
        manifest=manifest,
        backend=backend,
        backend_version=backend_version,
        device_class=device_class,
        class_ids=class_ids,
        counts=counts,
        elapsed_seconds=elapsed,
        compute_seconds=compute,
        halo3_seat_id=halo3_seat_id,
        observed_cuda_device_index=observed_cuda_device_index,
    )
    result = {**body, "resultId": content_id("stcmaryapertureworkloadresult1", body)}
    validate_workload_result(result)
    output = Path(args.out).expanduser().resolve()
    require(not output.exists(), "OUTPUT_EXISTS", "workload result output already exists")
    require(output.parent.is_dir(), "OUTPUT_PARENT_MISSING", "workload result parent is absent")
    write_json(output, result)
    return {"status": "PASS", "resultId": result["resultId"], "semanticOutputSha256": result["semanticOutputSha256"], "throughputRecordsPerSecond": result["throughputRecordsPerSecond"], "output": str(output)}


def verify_workload(args: Any) -> dict[str, Any]:
    manifest, feature_path, record_count, feature_count, class_count, weights = load_feed(Path(args.feed))
    result = read_json(Path(args.result))
    validate_workload_result(result)
    require(result["feedId"] == manifest["feedId"], "WORKLOAD_RESULT_FEED_MISMATCH", "workload result belongs to another feed")
    class_ids, counts, elapsed = classify_python(feature_path, record_count, feature_count, class_count, weights)
    require(result["classificationStreamSha256"] == sha256_bytes(class_ids), "WORKLOAD_CLASSIFICATION_MISMATCH", "classification stream differs")
    require(result["semanticOutputSha256"] == semantic_digest(class_ids, counts, manifest) and result["classCounts"] == counts, "WORKLOAD_SEMANTIC_MISMATCH", "semantic output differs")
    body = {
        "schema": "stc-mary-aperture-workload-verification/1",
        "feedId": manifest["feedId"],
        "resultId": result["resultId"],
        "status": "PASS",
        "verifier": "python-stdlib-independent/1",
        "recordDenominatorVerified": True,
        "featureDigestVerified": True,
        "classificationDigestVerified": True,
        "semanticOutputVerified": True,
        "classCountsVerified": True,
        "halo3SeatId": result["halo3SeatId"],
        "verificationElapsedSeconds": round(elapsed, 9),
        "externalServiceCalls": 0,
        "operationalCredentials": 0,
        "authority": "none",
        "claimBoundary": "Independent stdlib verification of one deterministic local aperture workload. It grants no physical, mission, command, targeting, engagement, effector, or weapons authority.",
    }
    verification = {**body, "verificationId": content_id("stcmaryapertureworkloadverification1", body)}
    output = Path(args.out).expanduser().resolve()
    require(not output.exists(), "OUTPUT_EXISTS", "verification output already exists")
    require(output.parent.is_dir(), "OUTPUT_PARENT_MISSING", "verification output parent is absent")
    write_json(output, verification)
    return {"status": "PASS", "verificationId": verification["verificationId"], "output": str(output)}


def compare_workloads(args: Any) -> dict[str, Any]:
    baseline = read_json(Path(args.baseline))
    accelerated = read_json(Path(args.accelerated))
    continuity = read_json(Path(args.continuity))
    for row in [baseline, accelerated, continuity]:
        validate_workload_result(row)
    require(baseline["feedId"] == accelerated["feedId"] == continuity["feedId"], "WORKLOAD_COMPARISON_FEED_MISMATCH", "workload results belong to different feeds")
    require(
        accelerated["halo3SeatId"] is not None
        and baseline["halo3SeatId"] is None
        and continuity["halo3SeatId"] is None,
        "WORKLOAD_COMPARISON_SEAT_BINDING_INVALID",
        "three-way comparison has an invalid HALO3 seat binding",
    )
    require(baseline["semanticOutputSha256"] == accelerated["semanticOutputSha256"] == continuity["semanticOutputSha256"], "WORKLOAD_COMPARISON_OUTPUT_MISMATCH", "workload semantic outputs differ")
    require(baseline["classificationStreamSha256"] == accelerated["classificationStreamSha256"] == continuity["classificationStreamSha256"], "WORKLOAD_COMPARISON_OUTPUT_MISMATCH", "classification streams differ")
    acceleration = accelerated["throughputRecordsPerSecond"] / baseline["throughputRecordsPerSecond"]
    require(acceleration > 1.0, "WORKLOAD_ACCELERATION_NOT_PROVEN", "HALO3 result did not exceed personal-floor throughput")
    body = {
        "schema": "stc-mary-aperture-workload-comparison/1",
        "feedId": baseline["feedId"],
        "baselineResultId": baseline["resultId"],
        "acceleratedResultId": accelerated["resultId"],
        "halo3SeatId": accelerated["halo3SeatId"],
        "continuityResultId": continuity["resultId"],
        "semanticOutputSha256": baseline["semanticOutputSha256"],
        "sameAcceptedOutput": True,
        "halo3AccelerationFactor": round(acceleration, 6),
        "personalFloorContinuity": True,
        "halo3RequiredForContinuity": False,
        "externalServiceCalls": 0,
        "operationalCredentials": 0,
        "authority": "none",
        "claimBoundary": "Comparison of one accepted semantic output across resident, accelerated, and post-removal runs. It grants no physical Estate or authority claim.",
    }
    comparison = {**body, "comparisonId": content_id("stcmaryapertureworkloadcomparison1", body)}
    output = Path(args.out).expanduser().resolve()
    require(not output.exists(), "OUTPUT_EXISTS", "comparison output already exists")
    require(output.parent.is_dir(), "OUTPUT_PARENT_MISSING", "comparison output parent is absent")
    write_json(output, comparison)
    return {"status": "PASS", "comparisonId": comparison["comparisonId"], "accelerationFactor": comparison["halo3AccelerationFactor"], "output": str(output)}
