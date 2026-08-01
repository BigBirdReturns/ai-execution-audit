#!/usr/bin/env python3
"""Apply the retained Polybolos Command Intelligence hardening overlay.

The target is the actual public Command Intelligence implementation in
simplifaisoul/osiris, pinned by TARGET.json. The script refuses to modify an
unknown checkout: the commit and every replaced file's Git blob identity must
match the retained target before any file is written.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TARGET_SPEC = HERE / "TARGET.json"
OVERLAY_ROOT = HERE / "overlay"
RECEIPT_NAME = "polybolos-ci-overlay-receipt.json"


def _run(*args: str, cwd: Path) -> str:
    proc = subprocess.run(
        args,
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc.stdout.strip()


def _git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()  # noqa: S324 - Git object identity


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def apply(target_root: Path) -> dict[str, Any]:
    target_root = target_root.resolve()
    spec = json.loads(TARGET_SPEC.read_text(encoding="utf-8"))

    if not (target_root / ".git").exists():
        raise RuntimeError(f"not a Git checkout: {target_root}")

    observed_commit = _run("git", "rev-parse", "HEAD", cwd=target_root)
    expected_commit = spec["commit"]
    if observed_commit != expected_commit:
        raise RuntimeError(
            f"target commit mismatch: expected {expected_commit}, observed {observed_commit}"
        )

    before: dict[str, str] = {}
    for rel, expected_blob in spec["files"].items():
        path = target_root / rel
        if not path.is_file():
            raise RuntimeError(f"required target file missing: {rel}")
        observed_blob = _git_blob_sha(path.read_bytes())
        if observed_blob != expected_blob:
            raise RuntimeError(
                f"target blob mismatch for {rel}: expected {expected_blob}, observed {observed_blob}"
            )
        before[rel] = _sha256(path)

    overlay_files = sorted(p for p in OVERLAY_ROOT.rglob("*") if p.is_file())
    if not overlay_files:
        raise RuntimeError(f"overlay is empty: {OVERLAY_ROOT}")

    written: dict[str, dict[str, str]] = {}
    for source in overlay_files:
        rel = source.relative_to(OVERLAY_ROOT).as_posix()
        destination = target_root / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        written[rel] = {
            "sha256": _sha256(destination),
            "git_blob_sha": _git_blob_sha(destination.read_bytes()),
        }

    receipt = {
        "schema": "ai-execution-audit/polybolos-ci-overlay-receipt@1",
        "target_repository": spec["repository"],
        "target_commit": observed_commit,
        "verified_original_files": before,
        "written_files": written,
        "claim_boundary": spec["claim_boundary"],
    }
    (target_root / RECEIPT_NAME).write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return receipt


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: apply_overlay.py <osiris-checkout>", file=sys.stderr)
        return 2
    try:
        receipt = apply(Path(sys.argv[1]))
    except Exception as exc:  # bounded CLI failure
        print(f"POLYBOLOS_CI_OVERLAY_REFUSED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
