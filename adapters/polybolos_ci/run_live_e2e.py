#!/usr/bin/env python3
"""Qualify the actual public Command Intelligence server through its local cabinet seam.

The transaction starts the built OSIRIS application with a local append-only
WAL, ingests one bounded fixture through the real authenticated route, mirrors
the read-only cabinet frame, proves 304 custody, stops the provider, proves the
last good frame survives, replays the WAL across restart, runs the MAME
diagnostic plugin against the offline frame, removes the provider-owned track
through a complete empty snapshot, and proves that removal also survives a
second restart.

No candidate action, target, effector, command, emulator input, or weapons
surface is exercised.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CABINET = HERE / "cabinet"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def http_json(
    url: str,
    *,
    method: str = "GET",
    body: Any | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 5.0,
) -> tuple[int, dict[str, str], Any | None]:
    payload = None if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")
    request_headers = {"Accept": "application/json", **(headers or {})}
    if payload is not None:
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url,
        data=payload,
        headers=request_headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            parsed = json.loads(raw.decode("utf-8")) if raw else None
            return response.status, dict(response.headers.items()), parsed
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        parsed = json.loads(raw.decode("utf-8")) if raw else None
        return exc.code, dict(exc.headers.items()), parsed


def header_value(headers: dict[str, str], name: str) -> str | None:
    wanted = name.lower()
    for key, value in headers.items():
        if key.lower() == wanted:
            return value
    return None


def wait_ready(base_url: str, process: subprocess.Popen[str], timeout: float = 45.0) -> None:
    deadline = time.monotonic() + timeout
    last_error = "not attempted"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Next server exited before readiness with {process.returncode}")
        try:
            status, _, body = http_json(
                f"{base_url}/api/sdk/cabinet?staleAfterMs=86400000&limit=16",
                timeout=1.5,
            )
            if status == 200 and isinstance(body, dict):
                return
            last_error = f"HTTP {status}: {body!r}"
        except Exception as exc:  # readiness retry
            last_error = f"{type(exc).__name__}: {exc}"
        time.sleep(0.25)
    raise RuntimeError(f"Next server did not become ready: {last_error}")


def start_server(target: Path, port: int, wal: Path, log: Path) -> subprocess.Popen[str]:
    log.parent.mkdir(parents=True, exist_ok=True)
    handle = log.open("w", encoding="utf-8")
    env = os.environ.copy()
    env.update(
        {
            "SDK_INGEST_KEY": "polybolos-ci-e2e-fixture-key",
            "CI_STORE_PATH": str(wal),
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


def stop_server(process: subprocess.Popen[str], lock_path: Path) -> None:
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=12)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
    handle = getattr(process, "_polybolos_log_handle", None)
    if handle is not None:
        handle.close()
    deadline = time.monotonic() + 5
    while lock_path.exists() and time.monotonic() < deadline:
        time.sleep(0.1)
    if lock_path.exists():
        raise RuntimeError(f"WAL lock survived graceful provider stop: {lock_path}")


def run_bridge(
    endpoint: str,
    frame: Path,
    receipt: Path,
    log: Path,
    *,
    expected_success: bool,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(CABINET / "bridge.py"),
        "--once",
        "--endpoint",
        endpoint,
        "--frame",
        str(frame),
        "--receipt",
        str(receipt),
        "--stale-after-ms",
        "86400000",
        "--limit",
        "16",
        "--timeout",
        "2",
    ]
    result = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    log.write_text(result.stdout, encoding="utf-8")
    if expected_success and result.returncode != 0:
        raise RuntimeError(f"cabinet mirror failed unexpectedly: {result.stdout}")
    if not expected_success and result.returncode == 0:
        raise RuntimeError("cabinet mirror unexpectedly reached a stopped provider")
    return result


def run_mame_harness(frame: Path, expected_entity: str, log: Path) -> None:
    env = os.environ.copy()
    env["POLYBOLOS_CI_CABINET_FRAME"] = str(frame)
    result = subprocess.run(
        [
            "lua5.4",
            str(CABINET / "mame" / "test_harness.lua"),
            str(CABINET / "mame" / "polybolosci" / "init.lua"),
            expected_entity,
        ],
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    log.write_text(result.stdout, encoding="utf-8")
    if result.returncode != 0 or "POLYBOLOS_CI_MAME_FRAME_PASS" not in result.stdout:
        raise RuntimeError(f"MAME diagnostic harness failed: {result.stdout}")


def assert_read_only_frame(frame: dict[str, Any], expected_entity: str | None) -> None:
    if frame.get("schema") != "polybolos-command-intelligence-cabinet-frame/1":
        raise RuntimeError("unexpected cabinet schema")
    if not str(frame.get("frameId", "")).startswith("ciframe1_"):
        raise RuntimeError("capture identity missing")
    if not str(frame.get("stateId", "")).startswith("cistate1_"):
        raise RuntimeError("semantic state identity missing")
    if "no command" not in str(frame.get("claimBoundary", "")).lower():
        raise RuntimeError("cabinet claim boundary does not deny command authority")
    serialized = json.dumps(frame, sort_keys=True).lower()
    for forbidden in (
        '"action"',
        '"targeting"',
        '"engagement"',
        '"effector"',
        '"properties"',
        '"display"',
    ):
        if forbidden in serialized:
            raise RuntimeError(f"forbidden field crossed into cabinet frame: {forbidden}")
    names = [row.get("name") for row in frame.get("entities", []) if isinstance(row, dict)]
    if expected_entity is None:
        if names:
            raise RuntimeError(f"provider-removal frame is not empty: {names}")
    elif expected_entity not in names:
        raise RuntimeError(f"expected entity is absent from cabinet frame: {names}")


def provider_unreachable(url: str) -> bool:
    try:
        http_json(url, timeout=0.75)
        return False
    except Exception:
        return True


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: run_live_e2e.py <qualified-target-checkout> <output-dir>", file=sys.stderr)
        return 2

    target = Path(sys.argv[1]).resolve()
    output = Path(sys.argv[2]).resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    if not (target / ".next").is_dir():
        raise RuntimeError("qualified target build is missing; run source qualification first")
    for required in (
        CABINET / "bridge.py",
        CABINET / "mame" / "test_harness.lua",
        CABINET / "mame" / "polybolosci" / "init.lua",
    ):
        if not required.is_file():
            raise RuntimeError(f"materialized cabinet dependency missing: {required}")

    wal = output / "command-intelligence.wal"
    lock = Path(f"{wal}.lock")
    frame = output / "polybolos-ci-cabinet-frame.json"
    mirror_receipt = output / "polybolos-ci-cabinet-frame.receipt.json"
    first_frame = output / "frame-before-provider-removal.json"
    base_query = "/api/sdk/cabinet?staleAfterMs=86400000&limit=16"
    process: subprocess.Popen[str] | None = None
    checks: dict[str, Any] = {}

    try:
        port1 = free_port()
        base1 = f"http://127.0.0.1:{port1}"
        process = start_server(target, port1, wal, output / "next-pass-1.log")
        wait_ready(base1, process)
        ingest = {
            "source": "e2e-fixture",
            "replaceSnapshot": True,
            "entities": [
                {
                    "id": "track-1",
                    "name": "E2E TRACK ONE",
                    "domain": "AIR",
                    "entityType": "TRACK",
                    "position": {
                        "lat": 34.1478,
                        "lng": -118.1445,
                        "alt": 9144,
                        "heading": 90,
                        "speed": 320,
                    },
                    "threat": "CRITICAL",
                    "classification": "SECRET",
                    "confidence": 1,
                    "timestamp": "2026-08-01T00:00:00.000Z",
                    "properties": {
                        "action": "this arbitrary source property must never cross the cabinet boundary"
                    },
                }
            ],
        }
        status, _, ingest_result = http_json(
            f"{base1}/api/sdk/ingest",
            method="POST",
            body=ingest,
            headers={"Authorization": "Bearer polybolos-ci-e2e-fixture-key"},
        )
        write_json(output / "ingest-result.json", ingest_result)
        if status != 200 or not isinstance(ingest_result, dict) or ingest_result.get("accepted") != 1:
            raise RuntimeError(f"real ingest route failed: HTTP {status} {ingest_result!r}")

        endpoint1 = f"{base1}/api/sdk/cabinet"
        run_bridge(
            endpoint1,
            frame,
            mirror_receipt,
            output / "mirror-pass-1.log",
            expected_success=True,
        )
        live_frame = json.loads(frame.read_text(encoding="utf-8"))
        assert_read_only_frame(live_frame, "E2E TRACK ONE")
        shutil.copy2(frame, first_frame)
        first_frame_sha = sha256(first_frame)
        first_state_id = live_frame["stateId"]
        first_capture_id = live_frame["frameId"]

        run_bridge(
            endpoint1,
            frame,
            mirror_receipt,
            output / "mirror-pass-1-not-modified.log",
            expected_success=True,
        )
        receipt_304 = json.loads(mirror_receipt.read_text(encoding="utf-8"))
        if receipt_304.get("status") != "not_modified":
            raise RuntimeError(f"semantic ETag did not produce 304: {receipt_304!r}")
        if sha256(frame) != first_frame_sha:
            raise RuntimeError("304 transaction changed the retained frame")
        checks["live_ingest_and_mirror"] = True
        checks["semantic_etag_304"] = True

        stop_server(process, lock)
        process = None
        if not provider_unreachable(f"{base1}{base_query}"):
            raise RuntimeError("provider remained reachable after stop")
        run_bridge(
            endpoint1,
            frame,
            mirror_receipt,
            output / "mirror-provider-down.log",
            expected_success=False,
        )
        if sha256(frame) != first_frame_sha:
            raise RuntimeError("provider loss replaced the last known good frame")
        failure_receipt = json.loads(mirror_receipt.read_text(encoding="utf-8"))
        if failure_receipt.get("status") != "failed":
            raise RuntimeError("provider-loss receipt is not failed")
        run_mame_harness(frame, "E2E TRACK ONE", output / "mame-offline.log")
        checks["provider_loss_preserves_frame"] = True
        checks["mame_reads_offline_frame"] = True

        port2 = free_port()
        base2 = f"http://127.0.0.1:{port2}"
        process = start_server(target, port2, wal, output / "next-pass-2.log")
        wait_ready(base2, process)
        status, headers, restarted_frame = http_json(f"{base2}{base_query}")
        write_json(output / "frame-after-restart-response.json", restarted_frame)
        if status != 200 or not isinstance(restarted_frame, dict):
            raise RuntimeError(f"restarted cabinet route failed: HTTP {status}")
        assert_read_only_frame(restarted_frame, "E2E TRACK ONE")
        if restarted_frame.get("stateId") != first_state_id:
            raise RuntimeError("WAL replay changed semantic state identity")
        if restarted_frame.get("frameId") != first_capture_id:
            raise RuntimeError("WAL replay changed capture identity without a semantic transition")
        restarted_etag = header_value(headers, "ETag")
        if restarted_etag not in {f'W/"{first_state_id}"', f'"{first_state_id}"'}:
            raise RuntimeError(f"restarted server emitted the wrong semantic ETag: {restarted_etag}")

        endpoint2 = f"{base2}/api/sdk/cabinet"
        run_bridge(
            endpoint2,
            frame,
            mirror_receipt,
            output / "mirror-after-restart.log",
            expected_success=True,
        )
        restarted_receipt = json.loads(mirror_receipt.read_text(encoding="utf-8"))
        if restarted_receipt.get("status") != "not_modified":
            raise RuntimeError("sidecar did not reuse semantic state after WAL replay")
        checks["wal_replay_stable_identity"] = True

        status, _, removal_result = http_json(
            f"{base2}/api/sdk/ingest",
            method="POST",
            body={
                "source": "e2e-fixture",
                "replaceSnapshot": True,
                "entities": [],
            },
            headers={"Authorization": "Bearer polybolos-ci-e2e-fixture-key"},
        )
        write_json(output / "provider-removal-result.json", removal_result)
        if status != 200 or not isinstance(removal_result, dict):
            raise RuntimeError(f"provider-removal ingest failed: HTTP {status}")
        run_bridge(
            endpoint2,
            frame,
            mirror_receipt,
            output / "mirror-after-provider-removal.log",
            expected_success=True,
        )
        removed_frame = json.loads(frame.read_text(encoding="utf-8"))
        assert_read_only_frame(removed_frame, None)
        if removed_frame.get("stateId") == first_state_id:
            raise RuntimeError("provider removal did not change semantic state identity")
        removed_state_id = removed_frame["stateId"]
        removed_frame_sha = sha256(frame)
        shutil.copy2(frame, output / "frame-after-provider-removal.json")
        checks["provider_complete_snapshot_removes_track"] = True

        stop_server(process, lock)
        process = None

        port3 = free_port()
        base3 = f"http://127.0.0.1:{port3}"
        process = start_server(target, port3, wal, output / "next-pass-3.log")
        wait_ready(base3, process)
        status, _, final_frame = http_json(f"{base3}{base_query}")
        write_json(output / "frame-after-removal-restart-response.json", final_frame)
        if status != 200 or not isinstance(final_frame, dict):
            raise RuntimeError(f"post-removal restart failed: HTTP {status}")
        assert_read_only_frame(final_frame, None)
        if final_frame.get("stateId") != removed_state_id:
            raise RuntimeError("provider-removal state did not survive WAL replay")
        checks["provider_removal_survives_restart"] = True

        stop_server(process, lock)
        process = None
        if sha256(frame) != removed_frame_sha:
            raise RuntimeError("final provider stop mutated the retained removal frame")

        receipt = {
            "schema": "ai-execution-audit/polybolos-ci-live-e2e@1",
            "status": "pass",
            "targetCommit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=target, text=True
            ).strip(),
            "checks": checks,
            "identities": {
                "beforeRemoval": {
                    "stateId": first_state_id,
                    "frameId": first_capture_id,
                    "frameSha256": first_frame_sha,
                },
                "afterRemoval": {
                    "stateId": removed_state_id,
                    "frameSha256": removed_frame_sha,
                },
                "walSha256": sha256(wal),
            },
            "artifacts": {
                path.name: {"bytes": path.stat().st_size, "sha256": sha256(path)}
                for path in sorted(output.iterdir())
                if path.is_file() and path.name != "e2e-receipt.json"
            },
            "claimBoundary":
                "This transaction qualifies the pinned public Command Intelligence source, local WAL replay, and read-only MAME/MotionDeck projection. It does not test private COMMAND CORE, private Lattice, operational authority, weapons employment, or combat effectiveness.",
        }
        write_json(output / "e2e-receipt.json", receipt)
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 0
    finally:
        if process is not None:
            try:
                stop_server(process, lock)
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
