#!/usr/bin/env python3
"""Run the pinned public Command Intelligence source through its native toolchain."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_command(name: str, command: list[str], cwd: Path, evidence_dir: Path, env: dict[str, str]) -> dict[str, Any]:
    started = time.time()
    proc = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    log_path = evidence_dir / f"{name}.log"
    log_path.write_text(proc.stdout, encoding="utf-8", errors="replace")
    return {
        "name": name,
        "command": command,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "duration_ms": round((time.time() - started) * 1000, 3),
        "log": log_path.relative_to(evidence_dir.parent).as_posix(),
        "log_sha256": sha256_file(log_path),
    }


def git_output(target: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=target, text=True).strip()


def build_replay_bundle(target: Path, output_root: Path, out_zip: Path) -> None:
    source_archive = output_root / "target-source.tar"
    with source_archive.open("wb") as f:
        subprocess.run(
            ["git", "archive", "--format=tar", "HEAD"],
            cwd=target,
            check=True,
            stdout=f,
        )

    # Preserve the complete integration factory rather than only the first
    # overlay generation. The generated cabinet directory is omitted because
    # its exact bundle, manifest, and materializer are already retained here.
    shutil.copytree(
        HERE,
        output_root / "adapter-custody",
        ignore=shutil.ignore_patterns("cabinet", "__pycache__", "*.pyc"),
    )
    (output_root / "target-overlay.diff").write_text(
        subprocess.check_output(["git", "diff", "--binary"], cwd=target, text=True),
        encoding="utf-8",
    )

    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(output_root.rglob("*")):
            if path.is_file() and path != out_zip:
                zf.write(path, path.relative_to(output_root).as_posix())


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: run_source_qualification.py <target-checkout> <output-dir>", file=sys.stderr)
        return 2

    target = Path(sys.argv[1]).resolve()
    output_root = Path(sys.argv[2]).resolve()
    if output_root.exists():
        shutil.rmtree(output_root)
    artifacts = output_root / "artifacts"
    evidence = output_root / "evidence"
    provenance = output_root / "provenance"
    artifacts.mkdir(parents=True)
    evidence.mkdir(parents=True)
    provenance.mkdir(parents=True)

    target_commit = git_output(target, "rev-parse", "HEAD")
    overlay_receipt_path = target / "polybolos-ci-overlay-receipt.json"
    if not overlay_receipt_path.is_file():
        raise RuntimeError("overlay receipt missing; apply_overlay.py must run first")
    overlay_receipt = json.loads(overlay_receipt_path.read_text(encoding="utf-8"))

    env = os.environ.copy()
    env.update({
        "CI": "true",
        "NEXT_TELEMETRY_DISABLED": "1",
        "NODE_OPTIONS": "--max-old-space-size=6144",
    })

    commands = [
        ("npm-ci", ["npm", "ci"]),
        ("npm-test", ["npm", "test"]),
        (
            "command-intelligence-lint",
            ["npx", "--no-install", "eslint", "src/lib/sdk", "src/app/api/sdk"],
        ),
        ("npm-build", ["npm", "run", "build"]),
    ]
    results: list[dict[str, Any]] = []
    install_ok = True
    for name, command in commands:
        if name != "npm-ci" and not install_ok:
            results.append({
                "name": name,
                "command": command,
                "returncode": None,
                "passed": False,
                "skipped": True,
                "reason": "npm ci failed",
            })
            continue
        result = run_command(name, command, target, evidence, env)
        results.append(result)
        if name == "npm-ci":
            install_ok = result["passed"]

    required_pass = all(result.get("passed") is True for result in results)
    (artifacts / "command-results.json").write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    input_bundle = {
        "schema": "ai-execution-audit/polybolos-ci-input@1",
        "target_repository": "simplifaisoul/osiris",
        "target_commit": target_commit,
        "package_lock_sha256": sha256_file(target / "package-lock.json"),
        "overlay_receipt": overlay_receipt,
        "commands": [result["command"] for result in results],
    }
    (artifacts / "input_bundle.json").write_text(
        json.dumps(input_bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    decision_record = {
        "schema": "ai-execution-audit/polybolos-ci-decision@1",
        "classification": "source_qualification",
        "status": "pass" if required_pass else "fail",
        "target_commit": target_commit,
        "requirements": {
            result["name"]: {
                "pass": result.get("passed") is True,
                "returncode": result.get("returncode"),
                "skipped": result.get("skipped", False),
                "log_sha256": result.get("log_sha256"),
            }
            for result in results
        },
        "claim_boundary": {
            "public_source_and_overlay_qualified": required_pass,
            "private_components_tested": False,
            "live_external_service_tested": False,
            "offline_dependency_replay": False,
            "offline_dependency_note": "npm dependencies are pinned by package-lock but not vendored into this bundle",
            "repository_wide_lint": False,
            "repository_wide_lint_note": "The upstream unscoped `eslint` command exceeds 6 GiB on a hosted runner. This transaction lints every Command Intelligence SDK and API file, runs the complete Vitest suite, and builds the complete Next application.",
            "integration_factory_retained": True,
            "integration_factory_note": "The replay bundle retains the exact target source archive, complete adapter custody, and binary target diff. Generated cabinet bytes are reconstructable from the retained cabinet bundle and materializer.",
        },
    }
    (artifacts / "decision_record.json").write_text(
        json.dumps(decision_record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    events = [
        {
            "event": "target_verified",
            "target_commit": target_commit,
            "overlay_receipt_sha256": sha256_file(overlay_receipt_path),
        },
        *[
            {
                "event": "command_finished",
                "name": result["name"],
                "passed": result.get("passed") is True,
                "returncode": result.get("returncode"),
                "duration_ms": result.get("duration_ms"),
                "log_sha256": result.get("log_sha256"),
            }
            for result in results
        ],
        {"event": "qualification_finished", "status": decision_record["status"]},
    ]
    (provenance / "provenance.log.jsonl").write_text(
        "".join(json.dumps(event, sort_keys=True) + "\n" for event in events),
        encoding="utf-8",
    )

    verify_targets = [
        artifacts / "input_bundle.json",
        artifacts / "decision_record.json",
        artifacts / "command-results.json",
        provenance / "provenance.log.jsonl",
        *sorted(evidence.glob("*.log")),
    ]
    verify_report = {
        "schema": "ai-execution-audit/verify-report@1",
        "status": "ok" if required_pass else "failed",
        "files": {
            path.relative_to(output_root).as_posix(): sha256_file(path)
            for path in verify_targets
        },
    }
    (artifacts / "verify_report.json").write_text(
        json.dumps(verify_report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    build_replay_bundle(target, output_root, artifacts / "replay_bundle.zip")
    print(json.dumps(decision_record, indent=2, sort_keys=True))
    return 0 if required_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
