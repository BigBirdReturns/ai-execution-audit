from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

EXPECTED_EMBEDDED_VERIFIER_SHA256 = "c3ba0d6a051ff4610f4ed5c95032a5d4e0d8c8257d9f50830483a1e6f1469d9b"
AUTHORITY = "none"
ISOLATED_VERIFIER_LAUNCHER = """import sys
source = sys.stdin.buffer.read()
namespace = {
    "__name__": "__main__",
    "__file__": "<measured-stc-mary-flight-01-cartridge-verifier>",
    "_STC_MARY_BOOTSTRAP_MEASURED_VERIFIER_BYTES": source,
}
exec(
    compile(source, "<measured-stc-mary-flight-01-cartridge-verifier>", "exec"),
    namespace,
    namespace,
)
"""


class BootstrapError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def fail(code: str, message: str) -> None:
    raise BootstrapError(code, message)


def canonical_json_bytes(value: Any) -> bytes:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return (text + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def coordinate_component_is_link(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        junction_probe = getattr(path, "is_junction", None)
        return bool(callable(junction_probe) and junction_probe())
    except OSError as exc:
        fail("CARTRIDGE_ROOT_INVALID", f"cartridge coordinate component could not be inspected: {path}: {exc}")


def validate_cartridge_coordinate(path: Path) -> Path:
    supplied = path.expanduser()
    absolute = Path(os.path.abspath(os.fspath(supplied)))
    parts = absolute.parts
    if not parts:
        fail("CARTRIDGE_ROOT_INVALID", "cartridge coordinate is empty")
    current = Path(parts[0])
    if coordinate_component_is_link(current):
        fail("CARTRIDGE_ROOT_INVALID", f"cartridge coordinate contains a symlink or junction component: {current}")
    for part in parts[1:]:
        current = current / part
        if coordinate_component_is_link(current):
            fail("CARTRIDGE_ROOT_INVALID", f"cartridge coordinate contains a symlink or junction component: {current}")
    return supplied


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Authenticate and execute the embedded STC MARY Flight 01 cartridge verifier")
    parser.add_argument("cartridge", type=Path)
    parser.add_argument("--out", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        supplied_root = validate_cartridge_coordinate(args.cartridge)
        root = supplied_root.resolve(strict=True)
        if not root.is_dir():
            fail("CARTRIDGE_ROOT_INVALID", "cartridge root must be a regular non-symlink directory")
        if args.out is not None:
            if is_within(args.out.resolve(strict=False), root):
                fail("VERDICT_INSIDE_CARTRIDGE", "bootstrap verdict may not be written inside the measured cartridge")
            if args.out.exists():
                fail("VERDICT_OUTPUT_EXISTS", "bootstrap verdict output must not already exist")
        verifier = root / "RECOVERY" / "verify_cartridge.py"
        if not verifier.is_file() or verifier.is_symlink():
            fail("EMBEDDED_VERIFIER_MISSING", "embedded verifier is missing or not regular")
        verifier_bytes = verifier.read_bytes()
        observed = sha256_bytes(verifier_bytes)
        if observed != EXPECTED_EMBEDDED_VERIFIER_SHA256:
            fail("EMBEDDED_VERIFIER_UNTRUSTED", "embedded verifier digest differs; untrusted code was not executed")
        completed = subprocess.run(
            [
                sys.executable,
                "-I",
                "-S",
                "-c",
                ISOLATED_VERIFIER_LAUNCHER,
                str(root),
            ],
            cwd=str(root.parent),
            input=verifier_bytes,
            check=False,
            capture_output=True,
        )
        try:
            verdict = json.loads(completed.stdout.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            fail("EMBEDDED_VERIFIER_OUTPUT_INVALID", str(exc))
        if completed.returncode != 0 or verdict.get("status") != "PASS":
            code = verdict.get("code", "EMBEDDED_VERIFIER_REFUSED") if isinstance(verdict, dict) else "EMBEDDED_VERIFIER_REFUSED"
            fail(str(code), "embedded verifier refused the cartridge")
        if verdict.get("bootstrapAuthenticated") is not False:
            fail("EMBEDDED_VERDICT_BOOTSTRAP_STATE_INVALID", "embedded verifier may not self-assert bootstrap authentication")
        if verdict.get("measuredVerifierSha256") != observed:
            fail(
                "EMBEDDED_VERIFIER_MEMBER_BINDING_INVALID",
                "embedded verifier did not bind the stored verifier member to the measured execution bytes",
            )
        verdict["bootstrapAuthenticated"] = True
        verdict["embeddedVerifierSha256"] = observed
        verdict["bootstrapVerifier"] = "external-measured-bytes-isolated-before-execution"
        data = canonical_json_bytes(verdict)
        if args.out is None:
            sys.stdout.buffer.write(data)
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_bytes(data)
        return 0
    except BootstrapError as exc:
        refusal = {
            "schema": "stc-mary/flight-01-cartridge-bootstrap-verdict/1",
            "status": "REFUSED",
            "code": exc.code,
            "message": str(exc),
            "embeddedVerifierExecuted": False if exc.code == "EMBEDDED_VERIFIER_UNTRUSTED" else None,
            "authority": AUTHORITY,
        }
        sys.stdout.buffer.write(canonical_json_bytes(refusal))
        return 1
    except (OSError, ValueError) as exc:
        refusal = {
            "schema": "stc-mary/flight-01-cartridge-bootstrap-verdict/1",
            "status": "REFUSED",
            "code": "BOOTSTRAP_FILESYSTEM_ERROR",
            "message": str(exc),
            "authority": AUTHORITY,
        }
        sys.stdout.buffer.write(canonical_json_bytes(refusal))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
