#!/usr/bin/env python3
"""Materialize the retained read-only Polybolos CI cabinet bridge.

The bridge is kept as a deterministic tar archive compressed with zlib and
encoded as base85 so the repository carries one bounded custody object. This
script verifies the decoded archive, rejects unsafe tar entries, extracts only
the manifest-declared files, and re-verifies every materialized byte.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import shutil
import sys
import tarfile
import zlib
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
MANIFEST_PATH = HERE / "CABINET_BUNDLE.json"
BUNDLE_PATH = HERE / "cabinet_bundle.b85"
DEFAULT_OUTPUT = HERE / "cabinet"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_member(name: str) -> bool:
    path = Path(name)
    return (
        bool(name)
        and not path.is_absolute()
        and ".." not in path.parts
        and all(part not in {"", "."} for part in path.parts)
    )


def materialize(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    encoded = "".join(BUNDLE_PATH.read_text(encoding="ascii").split())
    try:
        archive = zlib.decompress(base64.b85decode(encoded.encode("ascii")))
    except Exception as exc:
        raise RuntimeError(f"cabinet bundle decode failed: {exc}") from exc

    expected_bytes = int(manifest["decoded_tar_bytes"])
    expected_sha256 = str(manifest["decoded_tar_sha256"])
    if len(archive) != expected_bytes:
        raise RuntimeError(
            f"cabinet archive length mismatch: expected {expected_bytes}, observed {len(archive)}"
        )
    observed_sha256 = _sha256(archive)
    if observed_sha256 != expected_sha256:
        raise RuntimeError(
            f"cabinet archive SHA-256 mismatch: expected {expected_sha256}, observed {observed_sha256}"
        )

    expected_files = manifest["files"]
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    seen: set[str] = set()
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tf:
        for member in tf.getmembers():
            if not member.isfile() or member.issym() or member.islnk():
                raise RuntimeError(f"unsupported cabinet archive member: {member.name}")
            if not _safe_member(member.name):
                raise RuntimeError(f"unsafe cabinet archive path: {member.name}")
            if member.name not in expected_files:
                raise RuntimeError(f"undeclared cabinet archive member: {member.name}")
            extracted = tf.extractfile(member)
            if extracted is None:
                raise RuntimeError(f"unable to read cabinet archive member: {member.name}")
            data = extracted.read()
            destination = output / member.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            destination.chmod(member.mode & 0o777)
            seen.add(member.name)

    missing = set(expected_files) - seen
    if missing:
        raise RuntimeError(f"cabinet archive missing declared files: {sorted(missing)}")

    verified: dict[str, Any] = {}
    for rel, expected in expected_files.items():
        path = output / rel
        data = path.read_bytes()
        observed = _sha256(data)
        if len(data) != int(expected["bytes"]):
            raise RuntimeError(f"cabinet file length mismatch: {rel}")
        if observed != expected["sha256"]:
            raise RuntimeError(f"cabinet file SHA-256 mismatch: {rel}")
        verified[rel] = {"bytes": len(data), "sha256": observed}

    receipt = {
        "schema": "ai-execution-audit/polybolos-ci-cabinet-materialization@1",
        "archive_sha256": observed_sha256,
        "output": str(output),
        "files": verified,
        "claim_boundary": "The materialized bridge is a read-only local observation projection. It grants no command, engagement, input, emulator-memory, or weapons authority.",
    }
    (output / "MATERIALIZATION_RECEIPT.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return receipt


def main() -> int:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    try:
        receipt = materialize(output)
    except Exception as exc:
        print(f"POLYBOLOS_CI_CABINET_REFUSED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
