from __future__ import annotations

import importlib.util
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from .common import (
    BACKENDS,
    FEATURE_HEADER,
    assert_content_id,
    assert_sha256,
    canonical_json,
    content_id,
    require,
    safe_int,
    sha256_bytes,
    stable_keys,
)
from .workload_feed import iter_feature_records

def semantic_digest(class_ids: bytes, class_counts: Sequence[int], manifest: Mapping[str, Any]) -> str:
    body = {
        "schema": "stc-mary-aperture-semantic-output/1",
        "feedId": manifest["feedId"],
        "recordCount": manifest["recordCount"],
        "classCount": manifest["classCount"],
        "classCounts": list(class_counts),
        "classificationStreamSha256": sha256_bytes(class_ids),
    }
    return sha256_bytes(canonical_json(body).encode("utf-8"))


def classify_python(feature_path: Path, record_count: int, feature_count: int, class_count: int, weights: Sequence[Sequence[int]]) -> tuple[bytes, list[int], float]:
    started = time.perf_counter()
    output = bytearray(record_count)
    counts = [0] * class_count
    index = 0
    for record in iter_feature_records(feature_path, record_count, feature_count):
        best_class = 0
        best_score = -10**18
        for class_index in range(class_count):
            score = 0
            for feature_index in range(feature_count):
                score += int(record[feature_index]) * int(weights[feature_index][class_index])
            if score > best_score:
                best_score = score
                best_class = class_index
        output[index] = best_class
        counts[best_class] += 1
        index += 1
    elapsed = time.perf_counter() - started
    require(index == record_count, "WORKLOAD_RECORD_DENOMINATOR_INVALID", "python backend classified the wrong record count")
    return bytes(output), counts, elapsed


def classify_numpy(feature_path: Path, record_count: int, feature_count: int, class_count: int, weights: Sequence[Sequence[int]]) -> tuple[bytes, list[int], float, str]:
    require(importlib.util.find_spec("numpy") is not None, "BACKEND_UNAVAILABLE", "NumPy backend is unavailable")
    import numpy as np  # type: ignore

    started = time.perf_counter()
    data = np.memmap(feature_path, mode="r", dtype=np.uint8, offset=FEATURE_HEADER.size, shape=(record_count, feature_count))
    matrix = np.asarray(weights, dtype=np.float32)
    logits = np.asarray(data, dtype=np.float32) @ matrix
    classes = np.argmax(logits, axis=1).astype(np.uint8, copy=False)
    class_ids = classes.tobytes(order="C")
    counts = np.bincount(classes, minlength=class_count).astype(np.int64).tolist()
    elapsed = time.perf_counter() - started
    return class_ids, [int(row) for row in counts], elapsed, str(np.__version__)


def classify_torch(feature_path: Path, record_count: int, feature_count: int, class_count: int, weights: Sequence[Sequence[int]], *, cuda: bool, device_index: int) -> tuple[bytes, list[int], float, str, float, str]:
    require(importlib.util.find_spec("torch") is not None, "BACKEND_UNAVAILABLE", "Torch backend is unavailable")
    import torch  # type: ignore

    if cuda:
        require(torch.cuda.is_available(), "BACKEND_UNAVAILABLE", "Torch CUDA backend is unavailable")
        require(0 <= device_index < torch.cuda.device_count(), "BACKEND_DEVICE_INVALID", "Torch CUDA device index is unavailable")
        device = torch.device(f"cuda:{device_index}")
        device_class = f"cuda_accelerator:{device_index}"
    else:
        device = torch.device("cpu")
        device_class = "resident_cpu"
    torch.use_deterministic_algorithms(True)
    raw = bytearray(feature_path.read_bytes()[FEATURE_HEADER.size:])
    require(len(raw) == record_count * feature_count, "FEED_FILE_SIZE_INVALID", "feature payload size differs")
    started = time.perf_counter()
    data = torch.frombuffer(raw, dtype=torch.uint8).reshape(record_count, feature_count).to(device=device, dtype=torch.float32)
    weight_tensor = torch.tensor(weights, dtype=torch.float32, device=device)
    if cuda:
        torch.cuda.synchronize(device)
    compute_started = time.perf_counter()
    classes = torch.argmax(data @ weight_tensor, dim=1).to(dtype=torch.uint8)
    if cuda:
        torch.cuda.synchronize(device)
    compute_elapsed = time.perf_counter() - compute_started
    classes_cpu = classes.cpu().contiguous()
    class_ids = bytes(classes_cpu.numpy().tobytes()) if importlib.util.find_spec("numpy") else bytes(classes_cpu.tolist())
    counts = [int(row) for row in torch.bincount(classes_cpu.to(dtype=torch.int64), minlength=class_count).tolist()]
    total_elapsed = time.perf_counter() - started
    return class_ids, counts, total_elapsed, str(torch.__version__), compute_elapsed, device_class


def workload_result_body(*, manifest: Mapping[str, Any], backend: str, backend_version: str, device_class: str, class_ids: bytes, counts: Sequence[int], elapsed_seconds: float, compute_seconds: float | None = None) -> dict[str, Any]:
    return {
        "schema": "stc-mary-aperture-workload-result/1",
        "feedId": manifest["feedId"],
        "backend": backend,
        "backendVersion": backend_version,
        "deviceClass": device_class,
        "recordCount": manifest["recordCount"],
        "featureCount": manifest["featureCount"],
        "classCount": manifest["classCount"],
        "classCounts": list(counts),
        "classificationStreamSha256": sha256_bytes(class_ids),
        "semanticOutputSha256": semantic_digest(class_ids, counts, manifest),
        "elapsedSeconds": round(elapsed_seconds, 9),
        "computeSeconds": round(compute_seconds if compute_seconds is not None else elapsed_seconds, 9),
        "throughputRecordsPerSecond": round(manifest["recordCount"] / elapsed_seconds, 3),
        "outputBytes": len(class_ids),
        "externalServiceCalls": 0,
        "operationalCredentials": 0,
        "authority": "none",
        "claimBoundary": "Local deterministic aperture-workload result. Timing is host-specific; semantic output is backend-independent. This result grants no physical, mission, command, targeting, engagement, effector, or weapons authority.",
    }


def validate_workload_result(result: Mapping[str, Any]) -> None:
    stable_keys(result, [
        "schema", "resultId", "feedId", "backend", "backendVersion", "deviceClass", "recordCount", "featureCount",
        "classCount", "classCounts", "classificationStreamSha256", "semanticOutputSha256", "elapsedSeconds", "computeSeconds",
        "throughputRecordsPerSecond", "outputBytes", "externalServiceCalls", "operationalCredentials", "authority", "claimBoundary",
    ], "WORKLOAD_RESULT_INVALID", "workload result")
    require(result["schema"] == "stc-mary-aperture-workload-result/1", "WORKLOAD_RESULT_INVALID", "workload result schema differs")
    require(result["backend"] in BACKENDS, "WORKLOAD_RESULT_INVALID", "workload backend differs")
    assert_content_id(result["feedId"], "WORKLOAD_RESULT_INVALID", "feed ID")
    assert_sha256(result["classificationStreamSha256"], "WORKLOAD_RESULT_INVALID", "classification digest")
    assert_sha256(result["semanticOutputSha256"], "WORKLOAD_RESULT_INVALID", "semantic digest")
    safe_int(result["recordCount"], 1, 50_000_000, "WORKLOAD_RESULT_INVALID", "record count")
    safe_int(result["featureCount"], 1, 64, "WORKLOAD_RESULT_INVALID", "feature count")
    class_count = safe_int(result["classCount"], 2, 32, "WORKLOAD_RESULT_INVALID", "class count")
    require(isinstance(result["classCounts"], list) and len(result["classCounts"]) == class_count, "WORKLOAD_RESULT_INVALID", "class count denominator differs")
    require(all(isinstance(row, int) and row >= 0 for row in result["classCounts"]), "WORKLOAD_RESULT_INVALID", "class counts are invalid")
    require(sum(result["classCounts"]) == result["recordCount"], "WORKLOAD_RESULT_INVALID", "class counts do not close record denominator")
    require(isinstance(result["elapsedSeconds"], (int, float)) and result["elapsedSeconds"] > 0, "WORKLOAD_RESULT_INVALID", "elapsed time is invalid")
    require(isinstance(result["throughputRecordsPerSecond"], (int, float)) and result["throughputRecordsPerSecond"] > 0, "WORKLOAD_RESULT_INVALID", "throughput is invalid")
    require(result["outputBytes"] == result["recordCount"], "WORKLOAD_RESULT_INVALID", "classification output size differs")
    require(result["externalServiceCalls"] == 0 and result["operationalCredentials"] == 0 and result["authority"] == "none", "WORKLOAD_RESULT_CLAIM_INVALID", "workload widens service, credential, or authority")
    body = dict(result)
    result_id = body.pop("resultId")
    require(result_id == content_id("stcmaryapertureworkloadresult1", body), "WORKLOAD_RESULT_ID_INVALID", "workload result identity differs")
