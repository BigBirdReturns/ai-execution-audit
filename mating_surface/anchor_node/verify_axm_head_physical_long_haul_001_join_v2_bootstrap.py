from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

EXPECTED_VERIFIER_SHA256 = "986dc33080352d978992102b8bf2e3b2a1f795a956529983b90eee055cb758f7"
VERDICT_SCHEMA = "axm-head/physical-long-haul-001-join-verdict@2"


class BootstrapError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def fail(code: str, message: str) -> None:
    raise BootstrapError(code, message)


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ensure_output_safe(carrier: Path, out: Path | None) -> None:
    if out is None:
        return
    carrier_resolved = carrier.resolve()
    out_resolved = out.resolve(strict=False)
    if out_resolved == carrier_resolved or carrier_resolved in out_resolved.parents:
        fail("OUTPUT_OVERLAPS_CARRIER", "verdict output may not be inside the measured carrier")
    if out.exists():
        out_stat = out.stat()
        for member in carrier.rglob("*"):
            if member.is_file():
                stat = member.stat()
                if stat.st_dev == out_stat.st_dev and stat.st_ino == out_stat.st_ino:
                    fail("OUTPUT_ALIASES_CARRIER", "verdict output aliases a measured carrier file")


def emit_refusal(code: str, message: str) -> int:
    value = {
        "schema": VERDICT_SCHEMA,
        "status": "REFUSED",
        "code": code,
        "message": message,
        "bootstrapAuthenticated": False,
        "physicalAuthorizationProduced": False,
        "physicalExecutionStarted": False,
        "workersLaunched": 0,
        "listenersCreated": 0,
        "authority": "none",
    }
    sys.stdout.buffer.write(canonical_json_bytes(value))
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Authenticate and invoke the JOIN-v2 standalone verifier")
    parser.add_argument("carrier", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        carrier = args.carrier
        if not carrier.is_dir() or carrier.is_symlink():
            fail("CARRIER_DIRECTORY_INVALID", "carrier must be a non-symlink directory")
        verifier = carrier / "RECOVERY" / "verify_join.py"
        if not verifier.is_file() or verifier.is_symlink():
            fail("VERIFIER_MEMBER_INVALID", "embedded verifier is missing or symlinked")
        digest = sha256_bytes(verifier.read_bytes())
        if digest != EXPECTED_VERIFIER_SHA256:
            fail("VERIFIER_SUBSTITUTION_REFUSED", "embedded verifier digest differs; untrusted bytes were not executed")
        ensure_output_safe(carrier, args.out)
        command = [sys.executable, str(verifier), str(carrier)]
        if args.out is not None:
            command.extend(["--out", str(args.out)])
        env = os.environ.copy()
        env["AXM_HEAD_JOIN_V2_BOOTSTRAP_AUTHENTICATED"] = "1"
        env["AXM_HEAD_JOIN_V2_VERIFIER_SHA256"] = digest
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, check=False)
        sys.stdout.buffer.write(result.stdout)
        if result.stderr:
            sys.stderr.buffer.write(result.stderr)
        return result.returncode
    except (BootstrapError, OSError) as exc:
        code = exc.code if isinstance(exc, BootstrapError) else "BOOTSTRAP_IO_FAILED"
        return emit_refusal(code, str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
