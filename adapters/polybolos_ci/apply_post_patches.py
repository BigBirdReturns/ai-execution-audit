#!/usr/bin/env python3
"""Apply exact CI-discovered patches after the retained source integration."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "POST_PATCHES.json"
RECEIPT_NAME = "polybolos-ci-overlay-receipt.json"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_git(target: Path, *args: str) -> str:
    process = subprocess.run(
        ["git", *args],
        cwd=target,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return process.stdout


def apply(target: Path) -> dict[str, Any]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    applied: list[dict[str, Any]] = []
    for row in manifest["patches"]:
        path = HERE / row["path"]
        data = path.read_bytes()
        if len(data) != int(row["bytes"]):
            raise RuntimeError(f"post patch byte-length mismatch: {row['path']}")
        observed = sha256(data)
        if observed != row["sha256"]:
            raise RuntimeError(
                f"post patch SHA-256 mismatch for {row['path']}: expected {row['sha256']}, observed {observed}"
            )
        run_git(target, "apply", "--check", "--whitespace=error-all", str(path))
        run_git(target, "apply", "--whitespace=error-all", str(path))
        applied.append(
            {
                "path": row["path"],
                "bytes": len(data),
                "sha256": observed,
                "purpose": row["purpose"],
            }
        )

    receipt_path = target / RECEIPT_NAME
    if not receipt_path.is_file():
        raise RuntimeError("base overlay receipt is missing")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["post_patches"] = applied
    receipt["post_patch_claim_boundary"] = manifest["claim_boundary"]
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "schema": "ai-execution-audit/polybolos-ci-post-patch-receipt@1",
        "status": "pass",
        "patches": applied,
        "overlay_receipt_sha256": sha256(receipt_path.read_bytes()),
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: apply_post_patches.py <target-checkout>", file=sys.stderr)
        return 2
    try:
        receipt = apply(Path(sys.argv[1]).resolve())
    except Exception as exc:
        print(f"POLYBOLOS_CI_POST_PATCH_REFUSED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
