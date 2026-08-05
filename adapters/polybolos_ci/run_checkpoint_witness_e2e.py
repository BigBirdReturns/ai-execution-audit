#!/usr/bin/env python3
"""Qualify bounded Command Intelligence checkpoints and entity witnesses.

The transaction uses the built pinned public Command Intelligence server. It
loads 5,000 and then 20,000 synthetic unclassified observations, compares the
bounded candidate transaction with the complete snapshot, exercises cold and
warm checkpoint paths, verifies the transaction independently, replays the WAL
across restart, invalidates the checkpoint after mutation and provider removal,
and proves an old witness cannot be promoted into a new checkpoint.

No private COMMAND CORE source, private Lattice service, targeting, engagement,
effector, emulator-input, process-launch, or weapons surface is exercised.
"""
from __future__ import annotations

import copy
import json
import math
import os
import shutil
import signal
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from run_live_e2e import free_port, sha256, stop_server, wait_ready, write_json

HERE = Path(__file__).resolve().parent
VERIFIER = HERE / "checkpoint" / "checkpoint_verifier.mjs"
ENTITY_BATCH = 5_000
STALE_AFTER_MS = 86_400_000
FIXTURE_TIMESTAMP = "2026-08-01T00:00:00.000Z"
INGEST_KEY = "polybolos-ci-checkpoint-ingest-key"
CANDIDATE_KEY = "polybolos-ci-checkpoint-candidate-key"
SOFTWARE_RECORD_ID = "public-osiris-b9c0289-plus-qualified-overlay"
MAX_COLD_CHECKPOINT_MS = 5_000.0
MAX_WARM_P99_MS = 500.0
MAX_VERIFY_MS = 500.0
MAX_ONE_WITNESS_BYTES = 32 * 1024
MAX_FOUR_WITNESS_BYTES = 64 * 1024
MIN_SNAPSHOT_TO_BOUNDED_RATIO = 20.0


def http_json_raw(
    url: str,
    *,
    method: str = "GET",
    body: Any | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> tuple[int, dict[str, str], Any | None, bytes]:
    payload = None if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")
    request_headers = {"Accept": "application/json", **(headers or {})}
    if payload is not None:
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=payload, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            parsed = json.loads(raw.decode("utf-8")) if raw else None
            return response.status, dict(response.headers.items()), parsed, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        parsed = json.loads(raw.decode("utf-8")) if raw else None
        return exc.code, dict(exc.headers.items()), parsed, raw


def header_value(headers: dict[str, str], name: str) -> str | None:
    wanted = name.lower()
    for key, value in headers.items():
        if key.lower() == wanted:
            return value
    return None


def parse_server_timing(value: str | None) -> dict[str, float]:
    metrics: dict[str, float] = {}
    if not value:
        return metrics
    for component in value.split(","):
        fields = [field.strip() for field in component.split(";") if field.strip()]
        if not fields:
            continue
        name = fields[0]
        for field in fields[1:]:
            if field.startswith("dur="):
                try:
                    metrics[name] = float(field[4:])
                except ValueError:
                    pass
    return metrics


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        raise RuntimeError("percentile requires at least one value")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def start_server(target: Path, port: int, wal: Path, log: Path) -> subprocess.Popen[str]:
    log.parent.mkdir(parents=True, exist_ok=True)
    handle = log.open("w", encoding="utf-8")
    env = os.environ.copy()
    env.update(
        {
            "SDK_INGEST_KEY": INGEST_KEY,
            "SDK_CANDIDATE_KEY": CANDIDATE_KEY,
            "CI_STORE_PATH": str(wal),
            "CI_SOFTWARE_RECORD_ID": SOFTWARE_RECORD_ID,
            "NEXT_TELEMETRY_DISABLED": "1",
            "NODE_ENV": "production",
        }
    )
    process = subprocess.Popen(
        [
            "npm",
            "start",
            "--",
            "--hostname",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=target,
        env=env,
        text=True,
        stdout=handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    process._polybolos_log_handle = handle  # type: ignore[attr-defined]
    return process


def scale_entities(source_index: int, count: int = ENTITY_BATCH) -> list[dict[str, Any]]:
    return [
        {
            "id": f"track-{index:05d}",
            "name": f"CHECKPOINT {source_index} TRACK {index:05d}",
            "domain": "AIR",
            "entityType": "TRACK",
            "position": {
                "lat": 30 + source_index + ((index % 1_000) / 10_000),
                "lng": -120 + ((index % 2_000) / 10_000),
                "alt": 1_000 + index,
                "heading": index % 360,
                "speed": 100 + (index % 500),
            },
            "threat": "LOW",
            "classification": "UNCLASSIFIED",
            "confidence": 1,
            "timestamp": FIXTURE_TIMESTAMP,
            "properties": {"fixtureIndex": index, "fixtureSource": source_index},
        }
        for index in range(count)
    ]


def ingest(
    base_url: str,
    source: str,
    entities: list[dict[str, Any]],
    *,
    replace_snapshot: bool = True,
) -> dict[str, Any]:
    status, _, parsed, _ = http_json_raw(
        f"{base_url}/api/sdk/ingest",
        method="POST",
        body={
            "source": source,
            "replaceSnapshot": replace_snapshot,
            "entities": entities,
        },
        headers={"Authorization": f"Bearer {INGEST_KEY}"},
        timeout=60.0,
    )
    if status != 200 or not isinstance(parsed, dict):
        raise RuntimeError(f"ingest failed for {source}: HTTP {status} {parsed!r}")
    if parsed.get("accepted") != len(entities) or parsed.get("rejected") != 0:
        raise RuntimeError(f"ingest was incomplete for {source}: {parsed!r}")
    return parsed


def normalized_id(source: str, original_id: str) -> str:
    return f"ext-{source}-{original_id}"


def candidate_body(entity_ids: list[str]) -> dict[str, Any]:
    return {
        "producer": "command-core-fixture",
        "actionClass": "track-priority-candidate",
        "staleAfterMs": STALE_AFTER_MS,
        "entityIds": entity_ids,
        "payload": {
            "entityIds": entity_ids,
            "priority": 7,
            "explanation": "synthetic bounded candidate only",
        },
    }


def bounded_candidate(
    base_url: str,
    entity_ids: list[str],
) -> tuple[dict[str, Any], bytes, dict[str, str], float]:
    started = time.perf_counter()
    status, headers, parsed, raw = http_json_raw(
        f"{base_url}/api/sdk/candidate/bounded",
        method="POST",
        body=candidate_body(entity_ids),
        headers={"Authorization": f"Bearer {CANDIDATE_KEY}"},
        timeout=30.0,
    )
    elapsed_ms = (time.perf_counter() - started) * 1_000
    if status != 201 or not isinstance(parsed, dict):
        raise RuntimeError(f"bounded candidate failed: HTTP {status} {parsed!r}")
    if parsed.get("schema") != "polybolos-command-candidate-transaction/2":
        raise RuntimeError("bounded candidate returned the wrong transaction schema")
    return parsed, raw, headers, elapsed_ms


def full_snapshot(base_url: str) -> tuple[dict[str, Any], bytes, float]:
    started = time.perf_counter()
    status, _, parsed, raw = http_json_raw(
        f"{base_url}/api/sdk/snapshot?staleAfterMs={STALE_AFTER_MS}",
        timeout=60.0,
    )
    elapsed_ms = (time.perf_counter() - started) * 1_000
    if status != 200 or not isinstance(parsed, dict):
        raise RuntimeError(f"full snapshot failed: HTTP {status}")
    return parsed, raw, elapsed_ms


def run_verifier(
    transaction_path: Path,
    receipt_path: Path,
    log_path: Path,
    *,
    expected_success: bool,
    expected_error: str | None = None,
) -> tuple[float, dict[str, Any]]:
    started = time.perf_counter()
    result = subprocess.run(
        ["node", str(VERIFIER), str(transaction_path), str(receipt_path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    elapsed_ms = (time.perf_counter() - started) * 1_000
    log_path.write_text(result.stdout, encoding="utf-8")
    if not receipt_path.is_file():
        raise RuntimeError("detached verifier did not emit a receipt")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if expected_success:
        if result.returncode != 0 or receipt.get("candidateVerified") is not True:
            raise RuntimeError(f"detached verifier failed unexpectedly: {receipt!r}")
    else:
        if result.returncode == 0:
            raise RuntimeError("detached verifier accepted an invalid transaction")
        if expected_error and receipt.get("error") != expected_error:
            raise RuntimeError(
                f"detached verifier refused for the wrong reason: expected {expected_error}, observed {receipt!r}"
            )
    return elapsed_ms, receipt


def assert_bounded_transaction(
    transaction: dict[str, Any],
    raw: bytes,
    expected_entities: int,
    expected_witnesses: int,
    max_bytes: int,
) -> None:
    if "snapshot" in transaction:
        raise RuntimeError("bounded transaction embedded a full snapshot")
    checkpoint = transaction.get("checkpoint")
    if not isinstance(checkpoint, dict):
        raise RuntimeError("bounded transaction omitted its checkpoint")
    if checkpoint.get("entityCount") != expected_entities:
        raise RuntimeError(
            f"bounded checkpoint entity count is wrong: expected {expected_entities}, observed {checkpoint.get('entityCount')}"
        )
    if "entities" in checkpoint:
        raise RuntimeError("bounded checkpoint embedded the full entity set")
    witnesses = transaction.get("witnesses")
    if not isinstance(witnesses, list) or len(witnesses) != expected_witnesses:
        raise RuntimeError("bounded transaction witness count is wrong")
    if len(raw) > max_bytes:
        raise RuntimeError(f"bounded transaction exceeds {max_bytes} bytes: {len(raw)}")
    for witness in witnesses:
        siblings = witness.get("siblings") if isinstance(witness, dict) else None
        if not isinstance(siblings, list) or len(siblings) > 16:
            raise RuntimeError("entity witness is not logarithmically bounded")


def warm_measurements(
    base_url: str,
    entity_ids: list[str],
    *,
    samples: int,
    checkpoint_id: str,
) -> tuple[list[float], list[int]]:
    latencies: list[float] = []
    sizes: list[int] = []
    for _ in range(samples):
        transaction, raw, headers, elapsed_ms = bounded_candidate(base_url, entity_ids)
        if header_value(headers, "X-CI-Checkpoint-Cache") != "hit":
            raise RuntimeError("warm bounded candidate missed the checkpoint cache")
        if transaction.get("checkpoint", {}).get("checkpointId") != checkpoint_id:
            raise RuntimeError("warm bounded candidate changed semantic checkpoint identity")
        latencies.append(elapsed_ms)
        sizes.append(len(raw))
    return latencies, sizes


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: run_checkpoint_witness_e2e.py <qualified-target-checkout> <output-dir>", file=sys.stderr)
        return 2

    target = Path(sys.argv[1]).resolve()
    output = Path(sys.argv[2]).resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    if not (target / ".next").is_dir():
        raise RuntimeError("qualified target build is missing; run source qualification first")
    if not VERIFIER.is_file():
        raise RuntimeError(f"detached checkpoint verifier is missing: {VERIFIER}")

    wal = output / "command-intelligence-checkpoint.wal"
    lock = Path(f"{wal}.lock")
    process: subprocess.Popen[str] | None = None
    checks: dict[str, bool] = {}
    metrics: dict[str, Any] = {}
    artifacts: dict[str, Any] = {}

    sources = ["checkpoint-a", "checkpoint-b", "checkpoint-c", "checkpoint-d"]
    refs = [normalized_id(source, "track-04999") for source in sources]

    try:
        port1 = free_port()
        base1 = f"http://127.0.0.1:{port1}"
        process = start_server(target, port1, wal, output / "next-checkpoint-pass-1.log")
        wait_ready(base1, process)

        ingest_a = ingest(base1, sources[0], scale_entities(0))
        write_json(output / "ingest-5000.json", ingest_a)
        five_transaction, five_raw, five_headers, five_elapsed = bounded_candidate(base1, [refs[0]])
        write_json(output / "bounded-5000.json", five_transaction)
        five_snapshot, five_snapshot_raw, five_snapshot_elapsed = full_snapshot(base1)
        write_json(output / "snapshot-5000.json", five_snapshot)
        assert_bounded_transaction(
            five_transaction,
            five_raw,
            expected_entities=5_000,
            expected_witnesses=1,
            max_bytes=MAX_ONE_WITNESS_BYTES,
        )
        five_checkpoint_id = five_transaction["checkpoint"]["checkpointId"]
        five_timing = parse_server_timing(header_value(five_headers, "Server-Timing"))
        if header_value(five_headers, "X-CI-Checkpoint-Cache") != "miss":
            raise RuntimeError("initial 5,000-entity checkpoint did not report a cache miss")
        if five_timing.get("checkpoint", MAX_COLD_CHECKPOINT_MS + 1) > MAX_COLD_CHECKPOINT_MS:
            raise RuntimeError(f"5,000-entity checkpoint compile exceeded {MAX_COLD_CHECKPOINT_MS} ms")
        five_verify_ms, five_verify = run_verifier(
            output / "bounded-5000.json",
            output / "bounded-5000.verification.json",
            output / "bounded-5000.verifier.log",
            expected_success=True,
        )
        five_warm, five_warm_sizes = warm_measurements(
            base1,
            [refs[0]],
            samples=20,
            checkpoint_id=five_checkpoint_id,
        )
        if percentile(five_warm, 0.99) > MAX_WARM_P99_MS:
            raise RuntimeError("5,000-entity warm candidate p99 exceeded the bound")
        checks["bounded_checkpoint_at_5000"] = True
        checks["detached_witness_verification_at_5000"] = True

        for index, source in enumerate(sources[1:], start=1):
            result = ingest(base1, source, scale_entities(index))
            write_json(output / f"ingest-{source}.json", result)

        twenty_transaction, twenty_raw, twenty_headers, twenty_elapsed = bounded_candidate(base1, refs)
        write_json(output / "bounded-20000.json", twenty_transaction)
        twenty_snapshot, twenty_snapshot_raw, twenty_snapshot_elapsed = full_snapshot(base1)
        write_json(output / "snapshot-20000.json", twenty_snapshot)
        assert_bounded_transaction(
            twenty_transaction,
            twenty_raw,
            expected_entities=20_000,
            expected_witnesses=4,
            max_bytes=MAX_FOUR_WITNESS_BYTES,
        )
        twenty_checkpoint_id = twenty_transaction["checkpoint"]["checkpointId"]
        twenty_witness_ids = [row["witnessId"] for row in twenty_transaction["witnesses"]]
        twenty_timing = parse_server_timing(header_value(twenty_headers, "Server-Timing"))
        if header_value(twenty_headers, "X-CI-Checkpoint-Cache") != "miss":
            raise RuntimeError("initial 20,000-entity checkpoint did not report a cache miss")
        if twenty_timing.get("checkpoint", MAX_COLD_CHECKPOINT_MS + 1) > MAX_COLD_CHECKPOINT_MS:
            raise RuntimeError(f"20,000-entity checkpoint compile exceeded {MAX_COLD_CHECKPOINT_MS} ms")
        ratio = len(twenty_snapshot_raw) / max(1, len(twenty_raw))
        if ratio < MIN_SNAPSHOT_TO_BOUNDED_RATIO:
            raise RuntimeError(
                f"bounded transaction did not materially reduce transfer size: ratio {ratio:.2f}"
            )
        twenty_verify_ms, twenty_verify = run_verifier(
            output / "bounded-20000.json",
            output / "bounded-20000.verification.json",
            output / "bounded-20000.verifier.log",
            expected_success=True,
        )
        if twenty_verify_ms > MAX_VERIFY_MS:
            raise RuntimeError(f"detached 20,000-entity witness verification exceeded {MAX_VERIFY_MS} ms")
        twenty_warm, twenty_warm_sizes = warm_measurements(
            base1,
            refs,
            samples=50,
            checkpoint_id=twenty_checkpoint_id,
        )
        twenty_p99 = percentile(twenty_warm, 0.99)
        if twenty_p99 > MAX_WARM_P99_MS:
            raise RuntimeError(f"20,000-entity warm candidate p99 exceeded {MAX_WARM_P99_MS} ms")
        checks["bounded_checkpoint_at_20000"] = True
        checks["checkpoint_cache_serves_warm_candidates"] = True
        checks["full_cop_removed_from_candidate_transaction"] = True
        checks["detached_witness_verification_at_20000"] = True

        stop_server(process, lock)
        process = None

        port2 = free_port()
        base2 = f"http://127.0.0.1:{port2}"
        restart_started = time.perf_counter()
        process = start_server(target, port2, wal, output / "next-checkpoint-pass-2.log")
        wait_ready(base2, process)
        restart_ready_ms = (time.perf_counter() - restart_started) * 1_000
        restart_transaction, restart_raw, restart_headers, restart_elapsed = bounded_candidate(base2, refs)
        write_json(output / "bounded-20000-after-restart.json", restart_transaction)
        assert_bounded_transaction(
            restart_transaction,
            restart_raw,
            expected_entities=20_000,
            expected_witnesses=4,
            max_bytes=MAX_FOUR_WITNESS_BYTES,
        )
        if restart_transaction["checkpoint"]["checkpointId"] != twenty_checkpoint_id:
            raise RuntimeError("WAL replay changed checkpoint identity")
        if [row["witnessId"] for row in restart_transaction["witnesses"]] != twenty_witness_ids:
            raise RuntimeError("WAL replay changed entity witness identities")
        if header_value(restart_headers, "X-CI-Checkpoint-Cache") != "miss":
            raise RuntimeError("new process did not rebuild its checkpoint cache")
        restart_verify_ms, _ = run_verifier(
            output / "bounded-20000-after-restart.json",
            output / "bounded-20000-after-restart.verification.json",
            output / "bounded-20000-after-restart.verifier.log",
            expected_success=True,
        )
        checks["wal_replay_preserves_checkpoint_and_witness_identity"] = True

        changed_entity = scale_entities(0, 1)[0]
        changed_entity["name"] = "CHECKPOINT A TRACK 00000 MUTATED"
        changed_entity["threat"] = "CRITICAL"
        mutation_result = ingest(
            base2,
            sources[0],
            [changed_entity],
            replace_snapshot=False,
        )
        write_json(output / "mutation-result.json", mutation_result)
        mutated_transaction, mutated_raw, mutated_headers, mutated_elapsed = bounded_candidate(base2, refs)
        write_json(output / "bounded-after-mutation.json", mutated_transaction)
        mutated_checkpoint_id = mutated_transaction["checkpoint"]["checkpointId"]
        if mutated_checkpoint_id == twenty_checkpoint_id:
            raise RuntimeError("entity mutation did not invalidate the checkpoint")
        if header_value(mutated_headers, "X-CI-Checkpoint-Cache") != "miss":
            raise RuntimeError("entity mutation did not invalidate the checkpoint cache")
        checks["entity_mutation_invalidates_checkpoint"] = True

        old_witness_against_new_checkpoint = copy.deepcopy(twenty_transaction)
        old_witness_against_new_checkpoint["checkpoint"] = mutated_transaction["checkpoint"]
        write_json(
            output / "old-witness-against-new-checkpoint.json",
            old_witness_against_new_checkpoint,
        )
        _, mismatch_receipt = run_verifier(
            output / "old-witness-against-new-checkpoint.json",
            output / "old-witness-against-new-checkpoint.verification.json",
            output / "old-witness-against-new-checkpoint.verifier.log",
            expected_success=False,
            expected_error="witness_checkpoint_mismatch",
        )
        checks["old_witness_refused_against_new_checkpoint"] = True

        removal_result = ingest(base2, sources[0], [], replace_snapshot=True)
        write_json(output / "provider-removal-result.json", removal_result)
        remaining_refs = refs[1:]
        removed_transaction, removed_raw, removed_headers, removed_elapsed = bounded_candidate(
            base2,
            remaining_refs,
        )
        write_json(output / "bounded-after-provider-removal.json", removed_transaction)
        assert_bounded_transaction(
            removed_transaction,
            removed_raw,
            expected_entities=15_000,
            expected_witnesses=3,
            max_bytes=MAX_FOUR_WITNESS_BYTES,
        )
        if removed_transaction["checkpoint"]["checkpointId"] == mutated_checkpoint_id:
            raise RuntimeError("provider removal did not invalidate the checkpoint")
        if header_value(removed_headers, "X-CI-Checkpoint-Cache") != "miss":
            raise RuntimeError("provider removal did not invalidate the checkpoint cache")

        status, _, missing_removed, _ = http_json_raw(
            f"{base2}/api/sdk/candidate/bounded",
            method="POST",
            body=candidate_body([refs[0]]),
            headers={"Authorization": f"Bearer {CANDIDATE_KEY}"},
            timeout=30.0,
        )
        if status != 409 or not isinstance(missing_removed, dict):
            raise RuntimeError("removed provider entity remained eligible for a witness")
        if missing_removed.get("error") != f"CI_CHECKPOINT_ENTITY_NOT_FOUND: {refs[0]}":
            raise RuntimeError(f"provider-removal refusal was wrong: {missing_removed!r}")
        checks["provider_removal_invalidates_checkpoint_and_witness"] = True

        stop_server(process, lock)
        process = None

        port3 = free_port()
        base3 = f"http://127.0.0.1:{port3}"
        process = start_server(target, port3, wal, output / "next-checkpoint-pass-3.log")
        wait_ready(base3, process)
        final_transaction, final_raw, _, final_elapsed = bounded_candidate(base3, remaining_refs)
        write_json(output / "bounded-after-removal-restart.json", final_transaction)
        if (
            final_transaction["checkpoint"]["checkpointId"]
            != removed_transaction["checkpoint"]["checkpointId"]
        ):
            raise RuntimeError("provider-removal checkpoint changed across restart")
        run_verifier(
            output / "bounded-after-removal-restart.json",
            output / "bounded-after-removal-restart.verification.json",
            output / "bounded-after-removal-restart.verifier.log",
            expected_success=True,
        )
        checks["provider_removal_checkpoint_survives_restart"] = True

        metrics = {
            "entities5000": {
                "checkpointId": five_checkpoint_id,
                "coldRequestMs": round(five_elapsed, 3),
                "checkpointCompileMs": round(five_timing.get("checkpoint", -1), 3),
                "transactionBytes": len(five_raw),
                "snapshotBytes": len(five_snapshot_raw),
                "snapshotRequestMs": round(five_snapshot_elapsed, 3),
                "detachedVerifyMs": round(five_verify_ms, 3),
                "warmP50Ms": round(percentile(five_warm, 0.50), 3),
                "warmP95Ms": round(percentile(five_warm, 0.95), 3),
                "warmP99Ms": round(percentile(five_warm, 0.99), 3),
                "warmResponseBytesMin": min(five_warm_sizes),
                "warmResponseBytesMax": max(five_warm_sizes),
                "witnessDepth": len(five_transaction["witnesses"][0]["siblings"]),
            },
            "entities20000": {
                "checkpointId": twenty_checkpoint_id,
                "coldRequestMs": round(twenty_elapsed, 3),
                "checkpointCompileMs": round(twenty_timing.get("checkpoint", -1), 3),
                "transactionBytes": len(twenty_raw),
                "snapshotBytes": len(twenty_snapshot_raw),
                "snapshotRequestMs": round(twenty_snapshot_elapsed, 3),
                "snapshotToBoundedRatio": round(ratio, 3),
                "detachedVerifyMs": round(twenty_verify_ms, 3),
                "warmSamples": len(twenty_warm),
                "warmMeanMs": round(statistics.fmean(twenty_warm), 3),
                "warmP50Ms": round(percentile(twenty_warm, 0.50), 3),
                "warmP95Ms": round(percentile(twenty_warm, 0.95), 3),
                "warmP99Ms": round(twenty_p99, 3),
                "warmResponseBytesMin": min(twenty_warm_sizes),
                "warmResponseBytesMax": max(twenty_warm_sizes),
                "witnessDepths": [len(row["siblings"]) for row in twenty_transaction["witnesses"]],
            },
            "restart": {
                "readyMs": round(restart_ready_ms, 3),
                "candidateMs": round(restart_elapsed, 3),
                "detachedVerifyMs": round(restart_verify_ms, 3),
            },
            "mutation": {
                "candidateMs": round(mutated_elapsed, 3),
                "priorCheckpointId": twenty_checkpoint_id,
                "mutatedCheckpointId": mutated_checkpoint_id,
                "oldWitnessRefusal": mismatch_receipt.get("error"),
            },
            "providerRemoval": {
                "candidateMs": round(removed_elapsed, 3),
                "remainingEntities": removed_transaction["checkpoint"]["entityCount"],
                "checkpointId": removed_transaction["checkpoint"]["checkpointId"],
                "restartCandidateMs": round(final_elapsed, 3),
            },
        }
        write_json(output / "checkpoint-performance.json", metrics)

        for path in sorted(output.iterdir()):
            if path.is_file() and path.name != "checkpoint-e2e-receipt.json":
                artifacts[path.name] = {"bytes": path.stat().st_size, "sha256": sha256(path)}

        receipt = {
            "schema": "ai-execution-audit/polybolos-ci-checkpoint-witness-e2e@1",
            "status": "pass",
            "targetCommit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=target, text=True
            ).strip(),
            "checks": checks,
            "metrics": metrics,
            "identities": {
                "walSha256": sha256(wal),
                "checkpoint5000": five_checkpoint_id,
                "checkpoint20000": twenty_checkpoint_id,
                "checkpointAfterMutation": mutated_checkpoint_id,
                "checkpointAfterProviderRemoval": removed_transaction["checkpoint"]["checkpointId"],
                "witnesses20000": twenty_witness_ids,
                "verification5000": five_verify,
                "verification20000": twenty_verify,
            },
            "artifacts": artifacts,
            "claimBoundary": (
                "This transaction qualifies bounded checkpoints and entity witnesses against synthetic unclassified data in the pinned public Command Intelligence source. "
                "It does not test private COMMAND CORE, private Lattice, operational command authority, targeting, engagement, effector control, weapons employment, or combat effectiveness."
            ),
        }
        write_json(output / "checkpoint-e2e-receipt.json", receipt)
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 0
    finally:
        if process is not None:
            try:
                stop_server(process, lock)
            except Exception:
                try:
                    if process.poll() is None:
                        os.killpg(process.pid, signal.SIGKILL)
                except Exception:
                    pass


if __name__ == "__main__":
    raise SystemExit(main())
