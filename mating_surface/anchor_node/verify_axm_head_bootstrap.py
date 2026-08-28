from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

VERDICT_SCHEMA = "axm-head/mission-volume-verdict@1"
EXPECTED_VERIFIER_SHA256 = "ef68da907bd5c196a3a10c2874dae20c42cdb547ba14030a968e99d866ee3542"


def pretty_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def emit(value: dict[str, Any], out: Path | None) -> int:
    data = pretty_json_bytes(value)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
    sys.stdout.buffer.write(data)
    return 0 if value.get("status") == "PASS" else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Authenticate and execute the admitted AXM HEAD volume verifier")
    parser.add_argument("volume", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    verifier = args.volume / "RECOVERY" / "verify_volume.py"
    try:
        if not args.volume.is_dir():
            return emit(
                {
                    "schema": VERDICT_SCHEMA,
                    "status": "REFUSED",
                    "code": "VOLUME_ROOT_INVALID",
                    "message": f"volume root is not a directory: {args.volume}",
                    "bootstrapAuthenticated": False,
                },
                args.out,
            )
        if verifier.is_symlink() or not verifier.is_file():
            return emit(
                {
                    "schema": VERDICT_SCHEMA,
                    "status": "REFUSED",
                    "code": "VERIFIER_FILE_INVALID",
                    "message": "RECOVERY/verify_volume.py must be one regular file",
                    "bootstrapAuthenticated": False,
                },
                args.out,
            )
        observed = sha256_file(verifier)
        if observed != EXPECTED_VERIFIER_SHA256:
            return emit(
                {
                    "schema": VERDICT_SCHEMA,
                    "status": "REFUSED",
                    "code": "VERIFIER_TRUST_MISMATCH",
                    "message": "embedded verifier digest differs from the admitted verifier",
                    "expectedVerifierSha256": EXPECTED_VERIFIER_SHA256,
                    "observedVerifierSha256": observed,
                    "bootstrapAuthenticated": False,
                },
                args.out,
            )
        result = subprocess.run(
            [sys.executable, str(verifier), str(args.volume)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.stderr:
            return emit(
                {
                    "schema": VERDICT_SCHEMA,
                    "status": "REFUSED",
                    "code": "VERIFIER_STDERR_REFUSED",
                    "message": result.stderr.decode("utf-8", errors="replace"),
                    "standaloneVerifierSha256": observed,
                    "bootstrapAuthenticated": True,
                },
                args.out,
            )
        try:
            verdict = json.loads(result.stdout.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            return emit(
                {
                    "schema": VERDICT_SCHEMA,
                    "status": "REFUSED",
                    "code": "VERIFIER_OUTPUT_INVALID",
                    "message": str(exc),
                    "standaloneVerifierSha256": observed,
                    "bootstrapAuthenticated": True,
                },
                args.out,
            )
        if not isinstance(verdict, dict) or verdict.get("schema") != VERDICT_SCHEMA or verdict.get("status") not in {"PASS", "REFUSED"}:
            return emit(
                {
                    "schema": VERDICT_SCHEMA,
                    "status": "REFUSED",
                    "code": "VERIFIER_VERDICT_INVALID",
                    "message": "embedded verifier returned an invalid verdict object",
                    "standaloneVerifierSha256": observed,
                    "bootstrapAuthenticated": True,
                },
                args.out,
            )
        verdict["bootstrapAuthenticated"] = True
        verdict["standaloneVerifierSha256"] = observed
        return emit(verdict, args.out)
    except OSError as exc:
        return emit(
            {
                "schema": VERDICT_SCHEMA,
                "status": "REFUSED",
                "code": "BOOTSTRAP_IO_FAILED",
                "message": str(exc),
                "bootstrapAuthenticated": False,
            },
            args.out,
        )


if __name__ == "__main__":
    raise SystemExit(main())
