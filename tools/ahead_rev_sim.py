from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

from tools.pack_replay_bundle import BUNDLE_FILES, main as pack_bundle
from tools.verify import main as verify_bundle

ADAPTER_ID = "ahead-rev-sim.loop@1"
COMMAND = "from ahead_rev_sim.cli import main; main(['loop'])"
SOURCE_FILES = [
    "__init__.py",
    "cli.py",
    "debugger.py",
    "energy.py",
    "history.py",
    "isa.py",
    "machine.py",
    "memory.py",
    "metrics.py",
    "parser.py",
    "reversible_memory.py",
    "examples/__init__.py",
    "examples/prog_increment.py",
    "examples/run_example.py",
    "examples/run_loop.py",
]
RAW_ARTIFACTS = ["artifacts/loop.stdout.bin", "artifacts/loop.stderr.bin"]


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value)


def _run_loop(python_root: Path) -> subprocess.CompletedProcess[bytes]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(python_root)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    env["NO_NETWORK"] = "1"
    return subprocess.run(
        [sys.executable, "-c", COMMAND],
        cwd=python_root,
        env=env,
        capture_output=True,
        check=False,
        timeout=60,
    )


def _decision(result: subprocess.CompletedProcess[bytes]) -> dict[str, Any]:
    return {
        "adapter": ADAPTER_ID,
        "command": ["loop"],
        "exit_code": result.returncode,
        "stderr_bytes": len(result.stderr),
        "stderr_sha256": _sha256_bytes(result.stderr),
        "stdout_bytes": len(result.stdout),
        "stdout_sha256": _sha256_bytes(result.stdout),
    }


def _source_commit(source_repo: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(source_repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _write_run_artifacts(out_dir: Path, result: subprocess.CompletedProcess[bytes], source_commit: str | None) -> None:
    input_bundle = {"adapter": ADAPTER_ID, "command": ["loop"]}
    ir = {
        "adapter": ADAPTER_ID,
        "command": ["loop"],
        "entrypoint": "ahead_rev_sim.cli:main",
        "source_files": SOURCE_FILES,
    }
    decision = _decision(result)
    provenance = [
        {"adapter": ADAPTER_ID, "event": "run_start", "python": sys.version.split()[0], "source_commit": source_commit},
        {"adapter": ADAPTER_ID, "event": "run_end", **decision},
    ]
    _write_bytes(out_dir / "artifacts" / "input_bundle.json", _canonical_bytes(input_bundle))
    _write_bytes(out_dir / "artifacts" / "decision_record.json", _canonical_bytes(decision))
    _write_bytes(out_dir / "artifacts" / "loop.stdout.bin", result.stdout)
    _write_bytes(out_dir / "artifacts" / "loop.stderr.bin", result.stderr)
    _write_bytes(out_dir / "ir" / "demo_ir.json", _canonical_bytes(ir))
    provenance_bytes = b"".join(_canonical_bytes(event) + b"\n" for event in provenance)
    _write_bytes(out_dir / "provenance" / "provenance.log.jsonl", provenance_bytes)


def capture(source_repo: str | Path, out_dir: str | Path) -> str:
    source_repo = Path(source_repo).resolve()
    source_root = source_repo / "src"
    package_root = source_root / "ahead_rev_sim"
    out_dir = Path(out_dir)
    runtime_package = out_dir / "runtime" / "ahead_rev_sim"
    runtime_files: list[str] = []
    for rel in SOURCE_FILES:
        source = package_root / Path(*rel.split("/"))
        if not source.is_file():
            raise FileNotFoundError(f"Ahead Rev Sim source file is missing: {source}")
        destination = runtime_package / Path(*rel.split("/"))
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        runtime_files.append("runtime/ahead_rev_sim/" + rel)

    result = _run_loop(source_root)
    _write_run_artifacts(out_dir, result, _source_commit(source_repo))
    return pack_bundle(str(out_dir), list(BUNDLE_FILES) + RAW_ARTIFACTS + runtime_files)


def replay(bundle_dir: str | Path, out_dir: str | Path) -> dict[str, Any]:
    bundle_dir = Path(bundle_dir)
    report = verify_bundle(str(bundle_dir), require_manifest=True)
    if report["status"] != "ok":
        raise RuntimeError("Ahead Rev Sim replay bundle verification failed")
    input_bundle = json.loads((bundle_dir / "artifacts" / "input_bundle.json").read_text(encoding="utf-8"))
    if input_bundle != {"adapter": ADAPTER_ID, "command": ["loop"]}:
        raise ValueError("unsupported Ahead Rev Sim replay input")

    result = _run_loop(bundle_dir / "runtime")
    out_dir = Path(out_dir)
    source_commit = None
    _write_run_artifacts(out_dir, result, source_commit)
    expected = (bundle_dir / "artifacts" / "decision_record.json").read_bytes()
    actual = (out_dir / "artifacts" / "decision_record.json").read_bytes()
    if actual != expected:
        raise RuntimeError("Ahead Rev Sim replay decision differs from captured decision")
    return _decision(result)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Capture or replay the fixed Ahead Rev Sim loop operation.")
    subparsers = parser.add_subparsers(dest="action", required=True)
    capture_parser = subparsers.add_parser("capture")
    capture_parser.add_argument("source_repo")
    capture_parser.add_argument("out_dir")
    replay_parser = subparsers.add_parser("replay")
    replay_parser.add_argument("bundle_dir")
    replay_parser.add_argument("out_dir")
    args = parser.parse_args()
    if args.action == "capture":
        print(capture(args.source_repo, args.out_dir))
    else:
        print(json.dumps(replay(args.bundle_dir, args.out_dir), indent=2, sort_keys=True))