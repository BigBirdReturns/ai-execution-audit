from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

EXPECTED_VERIFIER_SHA256 = "8ba7f39f512a4f683bf6780ff0ac3a128d10d83dd07b59f4e7e62946f41b5761"
TRUSTED_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
VERDICT_SCHEMA = "axm-head/physical-long-haul-001-join-verdict@2"
DIRECT_VERDICT_KEYS = {
    "schema",
    "status",
    "carrierId",
    "joinContractId",
    "stateId",
    "decisionId",
    "terminal",
    "fileCount",
    "profileCanonicalSha256",
    "standaloneVerifierSha256",
    "bootstrapAuthenticated",
    "physicalAuthorizationProduced",
    "physicalExecutionStarted",
    "missionVolumeMaterialized",
    "workersLaunched",
    "listenersCreated",
    "authority",
}


MEASURED_VERIFIER_LAUNCHER = (
    "import sys\n"
    "source = sys.stdin.buffer.read()\n"
    "name = '<authenticated-join-v2-verifier>'\n"
    "namespace = {'__name__': '__main__', '__file__': name}\n"
    "exec(compile(source, name, 'exec'), namespace, namespace)\n"
)


class BootstrapError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def fail(code: str, message: str) -> None:
    raise BootstrapError(code, message)


def canonical_json_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        fail("NON_CANONICAL_JSON", str(exc))
    return (text + "\n").encode("utf-8")


def type_strict_equal(actual: Any, expected: Any) -> bool:
    return canonical_json_bytes(actual) == canonical_json_bytes(expected)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ensure_output_safe(carrier: Path, out: Path | None) -> None:
    if out is None:
        return
    carrier_resolved = carrier.resolve()
    out_resolved = out.resolve(strict=False)
    repository_resolved = TRUSTED_REPOSITORY_ROOT.resolve()
    if out_resolved == repository_resolved or repository_resolved in out_resolved.parents:
        fail("REPOSITORY_OUTPUT_REFUSED", "verdict output may not be written inside the repository")
    if out_resolved == carrier_resolved or carrier_resolved in out_resolved.parents:
        fail("OUTPUT_OVERLAPS_CARRIER", "verdict output may not be inside the measured carrier")
    if out.exists():
        out_stat = out.stat()
        for member in carrier.rglob("*"):
            if member.is_file():
                stat = member.stat()
                if stat.st_dev == out_stat.st_dev and stat.st_ino == out_stat.st_ino:
                    fail("OUTPUT_ALIASES_CARRIER", "verdict output aliases a measured carrier file")


def validate_direct_verdict(value: Any, verifier_digest: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail("DIRECT_VERDICT_INVALID", "direct verifier must emit one JSON object")
    if set(value) != DIRECT_VERDICT_KEYS:
        fail("DIRECT_VERDICT_KEYS_INVALID", "direct verifier verdict denominator differs")
    expected = {
        "schema": VERDICT_SCHEMA,
        "status": "PASS",
        "terminal": "PREPARED_NOT_ARMED",
        "fileCount": 5,
        "standaloneVerifierSha256": verifier_digest,
        "bootstrapAuthenticated": False,
        "physicalAuthorizationProduced": False,
        "physicalExecutionStarted": False,
        "missionVolumeMaterialized": False,
        "workersLaunched": 0,
        "listenersCreated": 0,
        "authority": "none",
    }
    for key, expected_value in expected.items():
        if not type_strict_equal(value[key], expected_value):
            fail("DIRECT_VERDICT_SEMANTICS_INVALID", f"direct verifier {key} differs")
    for key in ("carrierId", "joinContractId", "stateId", "decisionId", "profileCanonicalSha256"):
        if not isinstance(value[key], str) or not value[key]:
            fail("DIRECT_VERDICT_IDENTITY_INVALID", f"direct verifier {key} is invalid")
    authenticated = dict(value)
    authenticated["bootstrapAuthenticated"] = True
    return authenticated


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


def invoke_measured_verifier(verifier_bytes: bytes, carrier: Path, env: dict[str, str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-I", "-c", MEASURED_VERIFIER_LAUNCHER, str(carrier)],
        input=verifier_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=False,
    )


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
        verifier_bytes = verifier.read_bytes()
        measured_digest = sha256_bytes(verifier_bytes)
        if measured_digest != EXPECTED_VERIFIER_SHA256:
            fail("VERIFIER_SUBSTITUTION_REFUSED", "embedded verifier digest differs; untrusted bytes were not executed")
        ensure_output_safe(carrier, args.out)

        env = os.environ.copy()
        env.pop("AXM_HEAD_JOIN_V2_BOOTSTRAP_AUTHENTICATED", None)
        env.pop("AXM_HEAD_JOIN_V2_VERIFIER_SHA256", None)
        result = invoke_measured_verifier(verifier_bytes, carrier, env)
        if result.stderr:
            sys.stderr.buffer.write(result.stderr)
        if result.returncode != 0:
            sys.stdout.buffer.write(result.stdout)
            return result.returncode
        try:
            direct = json.loads(result.stdout.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            fail("DIRECT_VERDICT_PARSE_FAILED", str(exc))
        if result.stdout != canonical_json_bytes(direct):
            fail("DIRECT_VERDICT_NONCANONICAL", "direct verifier verdict bytes are not canonical")

        authenticated = validate_direct_verdict(direct, measured_digest)
        data = canonical_json_bytes(authenticated)
        if args.out is not None:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_bytes(data)
        sys.stdout.buffer.write(data)
        return 0
    except (BootstrapError, OSError, TypeError, ValueError) as exc:
        code = exc.code if isinstance(exc, BootstrapError) else "BOOTSTRAP_IO_FAILED"
        return emit_refusal(code, str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
