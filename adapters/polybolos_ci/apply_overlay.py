#!/usr/bin/env python3
"""Apply the retained Polybolos Command Intelligence integration.

The target is the actual public Command Intelligence implementation in
``simplifaisoul/osiris``, pinned by ``TARGET.json``. The transaction refuses an
unknown checkout: the commit and every named upstream blob must match before any
file is written.

The small v1 hardening overlay is copied first. The larger v2 integration patch
is reconstructed from whitespace-insensitive base64 parts, checked against
pinned compressed and decoded identities, and admitted only after
``git apply --check`` succeeds. A final reviewable post-overlay is then copied
over the admitted v2 tree for narrowly scoped fixes discovered by the real CI
run.
"""
from __future__ import annotations

import base64
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TARGET_SPEC = HERE / "TARGET.json"
OVERLAY_ROOT = HERE / "overlay"
POST_OVERLAY_ROOT = HERE / "post_overlay"
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


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _copy_tree(source_root: Path, target_root: Path) -> dict[str, dict[str, str]]:
    if not source_root.exists():
        return {}
    files = sorted(path for path in source_root.rglob("*") if path.is_file())
    if not files:
        raise RuntimeError(f"declared overlay tree is empty: {source_root}")

    copied: dict[str, dict[str, str]] = {}
    for source in files:
        rel = source.relative_to(source_root).as_posix()
        destination = target_root / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        copied[rel] = {
            "sha256": _sha256(destination),
            "git_blob_sha": _git_blob_sha(destination.read_bytes()),
        }
    return copied


def _decode_upgrade(
    spec: dict[str, Any],
) -> tuple[bytes, list[dict[str, Any]], dict[str, Any]]:
    upgrade = spec.get("upgrade_v2")
    if not isinstance(upgrade, dict):
        return b"", [], {}

    if upgrade.get("encoding") != "zlib+base64":
        raise RuntimeError(f"unsupported upgrade_v2 encoding: {upgrade.get('encoding')!r}")

    parts_glob = str(upgrade.get("parts_glob", ""))
    if not parts_glob:
        raise RuntimeError("upgrade_v2 parts_glob is missing")
    part_paths = sorted(HERE.glob(parts_glob))
    expected_part_count = int(upgrade.get("parts_count", 0))
    if not part_paths:
        raise RuntimeError(f"upgrade_v2 declared but no patch parts match {parts_glob!r}")
    if expected_part_count and len(part_paths) != expected_part_count:
        raise RuntimeError(
            f"upgrade_v2 part-count mismatch: expected {expected_part_count}, observed {len(part_paths)}"
        )

    parts: list[dict[str, Any]] = []
    encoded_chunks: list[str] = []
    for path in part_paths:
        raw = path.read_bytes()
        parts.append(
            {
                "path": path.relative_to(HERE).as_posix(),
                "bytes": len(raw),
                "sha256": _sha256_bytes(raw),
            }
        )
        encoded_chunks.append("".join(path.read_text(encoding="ascii").split()))

    encoded = "".join(encoded_chunks).encode("ascii")
    try:
        compressed = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise RuntimeError(f"upgrade_v2 base64 decode failed: {exc}") from exc

    expected_compressed_bytes = int(upgrade["compressed_bytes"])
    expected_compressed_sha256 = str(upgrade["compressed_sha256"])
    observed_compressed_sha256 = _sha256_bytes(compressed)
    if len(compressed) != expected_compressed_bytes:
        raise RuntimeError(
            "upgrade_v2 compressed byte-length mismatch: "
            f"expected {expected_compressed_bytes}, observed {len(compressed)}"
        )
    if observed_compressed_sha256 != expected_compressed_sha256:
        raise RuntimeError(
            "upgrade_v2 compressed SHA-256 mismatch: "
            f"expected {expected_compressed_sha256}, observed {observed_compressed_sha256}"
        )

    try:
        patch = zlib.decompress(compressed)
    except Exception as exc:
        raise RuntimeError(f"upgrade_v2 zlib decode failed: {exc}") from exc

    expected_bytes = int(upgrade["decoded_patch_bytes"])
    expected_sha256 = str(upgrade["decoded_patch_sha256"])
    observed_sha256 = _sha256_bytes(patch)
    if len(patch) != expected_bytes:
        raise RuntimeError(
            f"upgrade_v2 decoded byte-length mismatch: expected {expected_bytes}, observed {len(patch)}"
        )
    if observed_sha256 != expected_sha256:
        raise RuntimeError(
            f"upgrade_v2 decoded SHA-256 mismatch: expected {expected_sha256}, observed {observed_sha256}"
        )

    transport = {
        "encoding": "zlib+base64",
        "parts_glob": parts_glob,
        "parts_count": len(part_paths),
        "encoded_bytes": len(encoded),
        "compressed_bytes": len(compressed),
        "compressed_sha256": observed_compressed_sha256,
    }
    return patch, parts, transport


def _patch_paths(patch_path: Path, target_root: Path) -> list[str]:
    output = _run("git", "apply", "--numstat", str(patch_path), cwd=target_root)
    paths: list[str] = []
    for line in output.splitlines():
        fields = line.split("\t", 2)
        if len(fields) == 3:
            paths.append(fields[2])
    return sorted(set(paths))


def _final_changes(target_root: Path) -> dict[str, dict[str, Any]]:
    output = _run(
        "git",
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        cwd=target_root,
    )
    changes: dict[str, dict[str, Any]] = {}
    for line in output.splitlines():
        if len(line) < 4:
            continue
        status = line[:2]
        rel = line[3:]
        if " -> " in rel:
            rel = rel.split(" -> ", 1)[1]
        path = target_root / rel
        row: dict[str, Any] = {"status": status}
        if path.is_file():
            data = path.read_bytes()
            row.update(
                {
                    "bytes": len(data),
                    "sha256": _sha256_bytes(data),
                    "git_blob_sha": _git_blob_sha(data),
                }
            )
        else:
            row["deleted"] = True
        changes[rel] = row
    return changes


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
    if _run("git", "status", "--porcelain", cwd=target_root):
        raise RuntimeError("target checkout is not clean before overlay admission")

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

    upgrade_patch, upgrade_parts, upgrade_transport = _decode_upgrade(spec)
    copied = _copy_tree(OVERLAY_ROOT, target_root)

    upgrade_record: dict[str, Any] | None = None
    if upgrade_patch:
        with tempfile.NamedTemporaryFile(
            prefix="polybolos-ci-v2-",
            suffix=".patch",
            delete=False,
        ) as temporary:
            temporary.write(upgrade_patch)
            patch_path = Path(temporary.name)
        try:
            changed_paths = _patch_paths(patch_path, target_root)
            _run(
                "git",
                "apply",
                "--check",
                "--whitespace=error-all",
                str(patch_path),
                cwd=target_root,
            )
            _run(
                "git",
                "apply",
                "--whitespace=error-all",
                str(patch_path),
                cwd=target_root,
            )
        finally:
            patch_path.unlink(missing_ok=True)
        upgrade_record = {
            **upgrade_transport,
            "decoded_patch_bytes": len(upgrade_patch),
            "decoded_patch_sha256": _sha256_bytes(upgrade_patch),
            "parts": upgrade_parts,
            "changed_paths": changed_paths,
        }

    post_overlay = _copy_tree(POST_OVERLAY_ROOT, target_root)
    final_changes = _final_changes(target_root)
    if not final_changes:
        raise RuntimeError("overlay transaction produced no target changes")

    receipt = {
        "schema": "ai-execution-audit/polybolos-ci-overlay-receipt@3",
        "target_repository": spec["repository"],
        "target_commit": observed_commit,
        "verified_original_files": before,
        "copied_overlay_files": copied,
        "upgrade_v2": upgrade_record,
        "post_overlay_files": post_overlay,
        "final_changes": final_changes,
        "claim_boundary": spec["claim_boundary"],
    }
    (target_root / RECEIPT_NAME).write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
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
