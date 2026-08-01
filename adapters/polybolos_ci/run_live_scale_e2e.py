#!/usr/bin/env python3
"""Run the actual public Command Intelligence path at the 5,000-entity boundary.

This transaction uses the real authenticated ingest, paginated SSE, durable WAL,
read-only cabinet, MAME diagnostic, and complete-snapshot removal surfaces. It
also proves that a second writer, a complete-record WAL mutation, and an
oversized cabinet projection cannot quietly become accepted state.

The fixture is synthetic and unclassified. No candidate action, target,
effector, command, emulator input, or weapons surface is exercised.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from run_live_e2e import (
    CABINET,
    assert_read_only_frame,
    free_port,
    header_value,
    http_json,
    run_bridge,
    run_mame_harness,
    sha256,
    start_server,
    stop_server,
    wait_ready,
    write_json,
)

ENTITY_COUNT = 5_000
STALE_AFTER_MS = 86_400_000
CABINET_LIMIT = 12
FIXTURE_TIMESTAMP = '2026-08-01T00:00:00.000Z'
INGEST_KEY = 'polybolos-ci-e2e-fixture-key'


def canonical_hash(values: list[str]) -> str:
    payload = '\n'.join(sorted(values)).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


def scale_entities() -> list[dict[str, Any]]:
    return [
        {
            'id': f'track-{index:05d}',
            'name': f'SCALE TRACK {index:05d}',
            'domain': 'AIR',
            'entityType': 'TRACK',
            'position': {
                'lat': 30 + ((index % 1_000) / 10_000),
                'lng': -120 + ((index % 2_000) / 10_000),
                'alt': 1_000 + index,
                'heading': index % 360,
                'speed': 100 + (index % 500),
            },
            'threat': 'CRITICAL',
            'classification': 'UNCLASSIFIED',
            'confidence': 1,
            'timestamp': FIXTURE_TIMESTAMP,
            'properties': {
                'action': 'source-only property; must never cross the cabinet boundary',
                'fixtureIndex': index,
            },
        }
        for index in range(ENTITY_COUNT)
    ]


def read_sse_until(
    url: str,
    predicate: Callable[[list[dict[str, Any]]], bool],
    *,
    timeout: float = 30.0,
) -> tuple[list[dict[str, Any]], int, float]:
    request = urllib.request.Request(
        url,
        headers={'Accept': 'text/event-stream', 'Cache-Control': 'no-cache'},
    )
    events: list[dict[str, Any]] = []
    data_lines: list[str] = []
    total_bytes = 0
    started = time.monotonic()
    deadline = started + timeout
    with urllib.request.urlopen(request, timeout=5.0) as response:
        if response.status != 200:
            raise RuntimeError(f'SSE route returned HTTP {response.status}')
        while time.monotonic() < deadline:
            raw = response.readline()
            if not raw:
                break
            total_bytes += len(raw)
            line = raw.decode('utf-8').rstrip('\r\n')
            if line == '':
                if data_lines:
                    event = json.loads('\n'.join(data_lines))
                    if not isinstance(event, dict):
                        raise RuntimeError('SSE data event is not an object')
                    events.append(event)
                    data_lines = []
                    if predicate(events):
                        return events, total_bytes, time.monotonic() - started
                continue
            if line.startswith('data:'):
                data_lines.append(line[5:].lstrip())
        raise RuntimeError(
            f'SSE predicate was not satisfied after {len(events)} events and {time.monotonic() - started:.3f}s'
        )


def terminate_without_lock_check(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
    handle = getattr(process, '_polybolos_log_handle', None)
    if handle is not None:
        handle.close()


def wait_for_refusal(
    base_url: str,
    process: subprocess.Popen[str],
    *,
    timeout: float = 20.0,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            if process.returncode == 0:
                raise RuntimeError('refusal server exited successfully instead of refusing state')
            return
        request = urllib.request.Request(
            f'{base_url}/api/sdk/cabinet?staleAfterMs={STALE_AFTER_MS}&limit={CABINET_LIMIT}',
            headers={'Accept': 'application/json'},
        )
        try:
            with urllib.request.urlopen(request, timeout=1.0) as response:
                if response.status == 200:
                    raise RuntimeError('conflicting or corrupt provider became readable')
                if response.status >= 400:
                    return
        except urllib.error.HTTPError as exc:
            if exc.code >= 400:
                return
        except urllib.error.URLError:
            pass
        time.sleep(0.2)
    raise RuntimeError('expected provider refusal did not become observable')


def require_log_token(path: Path, token: str) -> None:
    text = path.read_text(encoding='utf-8', errors='replace')
    if token not in text:
        raise RuntimeError(f'expected refusal token {token!r} is absent from {path.name}')


def main() -> int:
    if len(sys.argv) != 3:
        print('usage: run_live_scale_e2e.py <qualified-target-checkout> <output-dir>', file=sys.stderr)
        return 2

    target = Path(sys.argv[1]).resolve()
    output = Path(sys.argv[2]).resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    if not (target / '.next').is_dir():
        raise RuntimeError('qualified target build is missing; run source qualification first')
    if not (CABINET / 'bridge.py').is_file():
        raise RuntimeError('materialized cabinet is missing')

    wal = output / 'command-intelligence-scale.wal'
    lock = Path(f'{wal}.lock')
    frame = output / 'polybolos-ci-scale-frame.json'
    frame_receipt = output / 'polybolos-ci-scale-frame.receipt.json'
    frame_before_removal = output / 'frame-before-provider-removal.json'
    process: subprocess.Popen[str] | None = None
    checks: dict[str, bool] = {}
    metrics: dict[str, Any] = {}

    try:
        port1 = free_port()
        base1 = f'http://127.0.0.1:{port1}'
        process = start_server(target, port1, wal, output / 'next-scale-pass-1.log')
        wait_ready(base1, process)

        entities = scale_entities()
        fixture_ids = [f'ext-scale-fixture-track-{index:05d}' for index in range(ENTITY_COUNT)]
        fixture_ids_sha256 = canonical_hash(fixture_ids)
        ingest_started = time.monotonic()
        status, _, ingest_result = http_json(
            f'{base1}/api/sdk/ingest',
            method='POST',
            body={
                'source': 'scale-fixture',
                'replaceSnapshot': True,
                'entities': entities,
            },
            headers={'Authorization': f'Bearer {INGEST_KEY}'},
            timeout=30.0,
        )
        ingest_elapsed = time.monotonic() - ingest_started
        write_json(output / 'scale-ingest-result.json', ingest_result)
        if status != 200 or not isinstance(ingest_result, dict):
            raise RuntimeError(f'5,000-entity ingest failed: HTTP {status}')
        if ingest_result.get('accepted') != ENTITY_COUNT or ingest_result.get('rejected') != 0:
            raise RuntimeError(f'5,000-entity ingest was incomplete: {ingest_result!r}')
        if ingest_result.get('sequence') != ENTITY_COUNT:
            raise RuntimeError(f'unexpected post-ingest sequence: {ingest_result.get("sequence")}')
        metrics['ingestSeconds'] = round(ingest_elapsed, 6)
        checks['authenticated_5000_entity_ingest'] = True

        snapshot_events, snapshot_bytes, snapshot_seconds = read_sse_until(
            f'{base1}/api/sdk/stream?after=0',
            lambda rows: any(row.get('type') == 'snapshot_complete' for row in rows),
        )
        pages = [row for row in snapshot_events if row.get('type') == 'snapshot_page']
        complete = next(row for row in snapshot_events if row.get('type') == 'snapshot_complete')
        page_sizes = [
            len(row.get('payload', {}).get('entities', []))
            for row in pages
            if isinstance(row.get('payload'), dict)
        ]
        streamed_ids = [
            entity.get('id')
            for row in pages
            for entity in row.get('payload', {}).get('entities', [])
            if isinstance(row.get('payload'), dict) and isinstance(entity, dict)
        ]
        if len(pages) != 10 or page_sizes != [500] * 10:
            raise RuntimeError(f'initial SSE pagination is wrong: {page_sizes}')
        if complete.get('payload') != {
            'sequence': ENTITY_COUNT,
            'entityCount': ENTITY_COUNT,
            'pages': 10,
        }:
            raise RuntimeError(f'initial SSE completion is wrong: {complete!r}')
        if len(streamed_ids) != ENTITY_COUNT or len(set(streamed_ids)) != ENTITY_COUNT:
            raise RuntimeError('initial SSE snapshot contains missing or duplicate entities')
        if canonical_hash([str(value) for value in streamed_ids]) != fixture_ids_sha256:
            raise RuntimeError('initial SSE snapshot identity differs from the ingested fixture')
        metrics['initialSse'] = {
            'seconds': round(snapshot_seconds, 6),
            'bytes': snapshot_bytes,
            'pages': len(pages),
            'pageSizes': page_sizes,
            'idsSha256': fixture_ids_sha256,
        }
        write_json(output / 'initial-sse-summary.json', metrics['initialSse'])
        checks['paginated_sse_delivers_all_5000'] = True

        endpoint1 = f'{base1}/api/sdk/cabinet'
        mirror_started = time.monotonic()
        run_bridge(
            endpoint1,
            frame,
            frame_receipt,
            output / 'scale-mirror-pass-1.log',
            expected_success=True,
        )
        metrics['cabinetMirrorSeconds'] = round(time.monotonic() - mirror_started, 6)
        before = json.loads(frame.read_text(encoding='utf-8'))
        assert_read_only_frame(before, 'SCALE TRACK 00000')
        if before.get('counts', {}).get('observed') != ENTITY_COUNT:
            raise RuntimeError('cabinet did not observe all 5,000 entities')
        if before.get('counts', {}).get('included') != CABINET_LIMIT:
            raise RuntimeError('cabinet projection did not preserve its bounded limit')
        if before.get('counts', {}).get('truncated') != ENTITY_COUNT - CABINET_LIMIT:
            raise RuntimeError('cabinet truncation receipt is wrong')
        if before.get('lamps', {}).get('truncated') is not True:
            raise RuntimeError('cabinet failed to expose scale truncation')
        shutil.copy2(frame, frame_before_removal)
        before_sha = sha256(frame_before_removal)
        before_state = str(before['stateId'])
        before_capture = str(before['frameId'])
        checks['cabinet_bounded_projection_of_5000'] = True

        port_conflict = free_port()
        conflict_log = output / 'next-concurrent-writer.log'
        conflict = start_server(target, port_conflict, wal, conflict_log)
        try:
            wait_for_refusal(f'http://127.0.0.1:{port_conflict}', conflict)
        finally:
            terminate_without_lock_check(conflict)
        require_log_token(conflict_log, 'CI_WAL_LOCKED')
        checks['concurrent_wal_writer_refused'] = True

        stop_server(process, lock)
        process = None
        run_mame_harness(
            frame_before_removal,
            'SCALE TRACK 00000',
            output / 'mame-scale-offline.log',
        )
        checks['mame_reads_bounded_scale_frame_offline'] = True

        port2 = free_port()
        base2 = f'http://127.0.0.1:{port2}'
        restart_started = time.monotonic()
        process = start_server(target, port2, wal, output / 'next-scale-pass-2.log')
        wait_ready(base2, process)
        metrics['walRestartSeconds'] = round(time.monotonic() - restart_started, 6)
        status, headers, restarted = http_json(
            f'{base2}/api/sdk/cabinet?staleAfterMs={STALE_AFTER_MS}&limit={CABINET_LIMIT}'
        )
        write_json(output / 'frame-after-scale-restart-response.json', restarted)
        if status != 200 or not isinstance(restarted, dict):
            raise RuntimeError('scale WAL replay cabinet route failed')
        assert_read_only_frame(restarted, 'SCALE TRACK 00000')
        if restarted.get('counts', {}).get('observed') != ENTITY_COUNT:
            raise RuntimeError('scale WAL replay lost entities')
        if restarted.get('stateId') != before_state or restarted.get('frameId') != before_capture:
            raise RuntimeError('scale WAL replay changed a stable cabinet identity')
        restarted_etag = header_value(headers, 'ETag')
        if restarted_etag not in {f'W/"{before_state}"', f'"{before_state}"'}:
            raise RuntimeError(f'scale WAL replay emitted the wrong ETag: {restarted_etag}')
        checks['wal_replays_all_5000_with_stable_identity'] = True

        status, _, removal_result = http_json(
            f'{base2}/api/sdk/ingest',
            method='POST',
            body={'source': 'scale-fixture', 'replaceSnapshot': True, 'entities': []},
            headers={'Authorization': f'Bearer {INGEST_KEY}'},
            timeout=30.0,
        )
        write_json(output / 'scale-provider-removal-result.json', removal_result)
        if status != 200 or not isinstance(removal_result, dict):
            raise RuntimeError('scale provider removal failed')
        if removal_result.get('sequence') != ENTITY_COUNT * 2:
            raise RuntimeError(f'unexpected post-removal sequence: {removal_result!r}')

        removal_events, removal_bytes, removal_seconds = read_sse_until(
            f'{base2}/api/sdk/stream?after={ENTITY_COUNT}',
            lambda rows: len([row for row in rows if row.get('type') == 'entity_remove']) >= ENTITY_COUNT,
            timeout=35.0,
        )
        if any(row.get('type') == 'resync_required' for row in removal_events):
            raise RuntimeError('retained 5,000-event delta unexpectedly required resync')
        removals = [row for row in removal_events if row.get('type') == 'entity_remove']
        removal_ids = [
            row.get('payload', {}).get('id')
            for row in removals
            if isinstance(row.get('payload'), dict)
        ]
        removal_sequences = [row.get('sequence') for row in removals]
        if removal_sequences != list(range(ENTITY_COUNT + 1, ENTITY_COUNT * 2 + 1)):
            raise RuntimeError('scale removal SSE sequence is incomplete or out of order')
        if canonical_hash([str(value) for value in removal_ids]) != fixture_ids_sha256:
            raise RuntimeError('scale removal SSE did not remove the exact ingested fixture')
        metrics['removalSse'] = {
            'seconds': round(removal_seconds, 6),
            'bytes': removal_bytes,
            'events': len(removals),
            'firstSequence': removal_sequences[0],
            'lastSequence': removal_sequences[-1],
            'idsSha256': fixture_ids_sha256,
        }
        write_json(output / 'removal-sse-summary.json', metrics['removalSse'])
        checks['delta_sse_delivers_all_5000_removals'] = True

        endpoint2 = f'{base2}/api/sdk/cabinet'
        run_bridge(
            endpoint2,
            frame,
            frame_receipt,
            output / 'scale-mirror-after-removal.log',
            expected_success=True,
        )
        after = json.loads(frame.read_text(encoding='utf-8'))
        assert_read_only_frame(after, None)
        if after.get('counts', {}).get('observed') != 0:
            raise RuntimeError('scale provider removal left retained entities')
        after_state = str(after['stateId'])
        if after_state == before_state:
            raise RuntimeError('scale provider removal did not change semantic state')
        after_sha = sha256(frame)
        shutil.copy2(frame, output / 'frame-after-scale-provider-removal.json')
        checks['complete_scale_snapshot_removes_all_entities'] = True

        stop_server(process, lock)
        process = None

        port3 = free_port()
        base3 = f'http://127.0.0.1:{port3}'
        process = start_server(target, port3, wal, output / 'next-scale-pass-3.log')
        wait_ready(base3, process)
        status, _, final_frame = http_json(
            f'{base3}/api/sdk/cabinet?staleAfterMs={STALE_AFTER_MS}&limit={CABINET_LIMIT}'
        )
        write_json(output / 'frame-after-scale-removal-restart-response.json', final_frame)
        if status != 200 or not isinstance(final_frame, dict):
            raise RuntimeError('post-removal scale replay failed')
        assert_read_only_frame(final_frame, None)
        if final_frame.get('stateId') != after_state:
            raise RuntimeError('post-removal scale state changed across restart')
        checks['scale_removal_survives_restart'] = True
        stop_server(process, lock)
        process = None

        good_wal_bytes = wal.read_bytes()
        good_wal_sha = hashlib.sha256(good_wal_bytes).hexdigest()

        corrupt_wal = output / 'corrupt-command-intelligence.wal'
        corrupted = bytearray(good_wal_bytes)
        marker = b'SCALE TRACK'
        offset = corrupted.find(marker)
        if offset < 0:
            raise RuntimeError('unable to locate a deterministic WAL mutation point')
        corrupted[offset] = ord('X')
        corrupt_wal.write_bytes(corrupted)
        corrupt_log = output / 'next-corrupt-wal.log'
        corrupt_port = free_port()
        corrupt_process = start_server(target, corrupt_port, corrupt_wal, corrupt_log)
        corrupt_base = f'http://127.0.0.1:{corrupt_port}'
        try:
            wait_for_refusal(corrupt_base, corrupt_process)
        finally:
            terminate_without_lock_check(corrupt_process)
        require_log_token(corrupt_log, 'CI_WAL_RECORD_HASH')
        Path(f'{corrupt_wal}.lock').unlink(missing_ok=True)
        corrupt_record = {
            'bytes': len(corrupted),
            'sha256': hashlib.sha256(corrupted).hexdigest(),
            'goodWalSha256': good_wal_sha,
            'mutatedOffset': offset,
            'refusalToken': 'CI_WAL_RECORD_HASH',
        }
        write_json(output / 'corrupt-wal-refusal.json', corrupt_record)
        corrupt_wal.unlink()
        checks['complete_record_wal_tamper_refused'] = True

        tail_wal = output / 'truncated-tail-command-intelligence.wal'
        tail_wal.write_bytes(good_wal_bytes + b'{"incomplete":')
        tail_port = free_port()
        tail_base = f'http://127.0.0.1:{tail_port}'
        tail_process = start_server(target, tail_port, tail_wal, output / 'next-truncated-tail.log')
        try:
            wait_ready(tail_base, tail_process)
            status, _, tail_frame = http_json(
                f'{tail_base}/api/sdk/cabinet?staleAfterMs={STALE_AFTER_MS}&limit={CABINET_LIMIT}'
            )
            write_json(output / 'truncated-tail-frame.json', tail_frame)
            if status != 200 or not isinstance(tail_frame, dict):
                raise RuntimeError('truncated-tail recovery route failed')
            assert_read_only_frame(tail_frame, None)
            diagnostics = tail_frame.get('persistence', {}).get('diagnostics', {})
            if not isinstance(diagnostics, dict) or diagnostics.get('truncatedTailBytes') != 14:
                raise RuntimeError(f'truncated-tail recovery receipt is wrong: {diagnostics!r}')
        finally:
            stop_server(tail_process, Path(f'{tail_wal}.lock'))
        if tail_wal.read_bytes() != good_wal_bytes:
            raise RuntimeError('truncated-tail recovery altered the valid WAL prefix')
        write_json(
            output / 'truncated-tail-recovery.json',
            {
                'status': 'pass',
                'truncatedTailBytes': 14,
                'recoveredWalSha256': sha256(tail_wal),
                'expectedWalSha256': good_wal_sha,
            },
        )
        tail_wal.unlink()
        checks['incomplete_wal_tail_recovers_exact_prefix'] = True

        receipt = {
            'schema': 'ai-execution-audit/polybolos-ci-live-scale@1',
            'status': 'pass',
            'targetCommit': subprocess.check_output(
                ['git', 'rev-parse', 'HEAD'], cwd=target, text=True
            ).strip(),
            'fixture': {
                'source': 'scale-fixture',
                'entities': ENTITY_COUNT,
                'idsSha256': fixture_ids_sha256,
                'timestamp': FIXTURE_TIMESTAMP,
            },
            'checks': checks,
            'metrics': metrics,
            'identities': {
                'beforeRemoval': {
                    'stateId': before_state,
                    'frameId': before_capture,
                    'frameSha256': before_sha,
                },
                'afterRemoval': {
                    'stateId': after_state,
                    'frameSha256': after_sha,
                },
                'walSha256': good_wal_sha,
            },
            'artifacts': {
                path.name: {'bytes': path.stat().st_size, 'sha256': sha256(path)}
                for path in sorted(output.iterdir())
                if path.is_file() and path.name != 'scale-e2e-receipt.json'
            },
            'claimBoundary':
                'This transaction qualifies a synthetic 5,000-entity load against the pinned public Command Intelligence source, local WAL, SSE, and read-only MAME/MotionDeck projection. It does not test private COMMAND CORE, private Lattice, operational authority, weapons employment, or combat effectiveness.',
        }
        write_json(output / 'scale-e2e-receipt.json', receipt)
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 0
    finally:
        if process is not None:
            try:
                stop_server(process, lock)
            except Exception:
                pass


if __name__ == '__main__':
    raise SystemExit(main())
