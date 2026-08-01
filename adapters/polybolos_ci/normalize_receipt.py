#!/usr/bin/env python3
"""Recompute the overlay receipt's changed-file ledger without whitespace loss.

``apply_overlay.py`` uses ordinary human-readable Git output for most bounded
checks. Git porcelain paths, however, can begin after a leading-space status
code. This script uses NUL-delimited porcelain output so the first record cannot
lose its status byte when text is trimmed. It rewrites only the derived
``final_changes`` section after the overlay transaction has completed.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

RECEIPT_NAME = "polybolos-ci-overlay-receipt.json"


def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()  # noqa: S324 - Git identity


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def final_changes(target: Path) -> dict[str, dict[str, Any]]:
    output = subprocess.check_output(
        [
            "git",
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
        ],
        cwd=target,
    )
    records = output.split(b"\0")
    changes: dict[str, dict[str, Any]] = {}
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        if len(record) < 4:
            raise RuntimeError(f"malformed porcelain record: {record!r}")
        status = record[:2].decode("ascii")
        rel = record[3:].decode("utf-8", errors="strict")
        if status[0] in {"R", "C"}:
            if index >= len(records) or not records[index]:
                raise RuntimeError(f"rename/copy record missing destination: {rel}")
            rel = records[index].decode("utf-8", errors="strict")
            index += 1
        path = target / rel
        row: dict[str, Any] = {"status": status}
        if path.is_file():
            data = path.read_bytes()
            row.update(
                {
                    "bytes": len(data),
                    "sha256": sha256_bytes(data),
                    "git_blob_sha": git_blob_sha(data),
                }
            )
        else:
            row["deleted"] = True
        changes[rel] = row
    return dict(sorted(changes.items()))


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: normalize_receipt.py <target-checkout>", file=sys.stderr)
        return 2
    target = Path(sys.argv[1]).resolve()
    receipt_path = target / RECEIPT_NAME
    if not receipt_path.is_file():
        print(f"receipt missing: {receipt_path}", file=sys.stderr)
        return 1
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["final_changes"] = final_changes(target)
    receipt["final_changes_parser"] = "git-status-porcelain-v1-z"
    if "slint.config.mjs" in receipt["final_changes"]:
        raise RuntimeError("path-shift defect survived NUL-delimited recomputation")
    if not (target / "eslint.config.mjs").is_file():
        raise RuntimeError("expected eslint.config.mjs is absent after overlay")
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "schema": "ai-execution-audit/polybolos-ci-receipt-normalization@1",
                "status": "pass",
                "changed_files": len(receipt["final_changes"]),
                "receipt_sha256": sha256_bytes(receipt_path.read_bytes()),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
