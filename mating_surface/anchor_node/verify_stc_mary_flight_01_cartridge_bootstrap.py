from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

EXPECTED_EMBEDDED_VERIFIER_SHA256 = "36a97c016b8fd44b2a355a02eb7735aeee262643f737b87d980eb1e08e7e5c61"
EXPECTED_EMBEDDED_VERIFIER_BYTES = 27837
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


MINIMUM_PYTHON = (3, 12)


def require_supported_python() -> None:
    if sys.version_info < MINIMUM_PYTHON:
        fail(
            "PYTHON_VERSION_UNSUPPORTED",
            f"Python {MINIMUM_PYTHON[0]}.{MINIMUM_PYTHON[1]} or newer is required for junction-safe cartridge custody",
        )


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


def coordinate_component_is_link(path: Path, *, code: str, label: str) -> bool:
    require_supported_python()
    try:
        return path.is_symlink() or path.is_junction()
    except OSError as exc:
        fail(code, f"{label} component could not be inspected: {path}: {exc}")


def validate_lexical_coordinate(
    path: Path,
    *,
    label: str,
    expansion_code: str,
    invalid_code: str,
) -> Path:
    require_supported_python()
    if any(part == os.pardir for part in path.parts):
        fail(invalid_code, f"{label} may not contain a parent-directory segment")
    try:
        supplied = path.expanduser()
    except RuntimeError as exc:
        fail(expansion_code, f"{label} user expansion failed: {exc}")
    if any(part == os.pardir for part in supplied.parts):
        fail(invalid_code, f"{label} may not contain a parent-directory segment")
    try:
        absolute = Path(os.path.abspath(os.fspath(supplied)))
    except (OSError, ValueError) as exc:
        fail(invalid_code, f"{label} could not be made absolute: {exc}")
    parts = absolute.parts
    if not parts:
        fail(invalid_code, f"{label} is empty")
    current = Path(parts[0])
    if coordinate_component_is_link(current, code=invalid_code, label=label):
        fail(invalid_code, f"{label} contains a symlink or junction component: {current}")
    for part in parts[1:]:
        current = current / part
        if coordinate_component_is_link(current, code=invalid_code, label=label):
            fail(invalid_code, f"{label} contains a symlink or junction component: {current}")
    return absolute


def validate_cartridge_coordinate(path: Path) -> Path:
    return validate_lexical_coordinate(
        path,
        label="cartridge coordinate",
        expansion_code="CARTRIDGE_PATH_EXPANSION_FAILED",
        invalid_code="CARTRIDGE_ROOT_INVALID",
    )


def validate_output_coordinate(path: Path) -> Path:
    return validate_lexical_coordinate(
        path,
        label="verdict output coordinate",
        expansion_code="VERDICT_PATH_EXPANSION_FAILED",
        invalid_code="VERDICT_PATH_INVALID",
    )


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
            fail("CARTRIDGE_ROOT_INVALID", "cartridge root must be a regular non-linked directory")
        output = None if args.out is None else validate_output_coordinate(args.out)
        if output is not None:
            if is_within(output.resolve(strict=False), root):
                fail("VERDICT_INSIDE_CARTRIDGE", "bootstrap verdict may not be written inside the measured cartridge")
            if output.exists():
                fail("VERDICT_OUTPUT_EXISTS", "bootstrap verdict output must not already exist")
        recovery = root / "RECOVERY"
        if coordinate_component_is_link(recovery, code="EMBEDDED_VERIFIER_MISSING", label="embedded verifier parent") or not recovery.is_dir():
            fail("EMBEDDED_VERIFIER_MISSING", "embedded verifier parent is missing, linked, or not regular")
        verifier = recovery / "verify_cartridge.py"
        if coordinate_component_is_link(verifier, code="EMBEDDED_VERIFIER_MISSING", label="embedded verifier") or not verifier.is_file():
            fail("EMBEDDED_VERIFIER_MISSING", "embedded verifier is missing, linked, or not regular")
        verifier_size = verifier.stat().st_size
        if verifier_size != EXPECTED_EMBEDDED_VERIFIER_BYTES:
            fail(
                "EMBEDDED_VERIFIER_SIZE_INVALID",
                f"embedded verifier size differs: expected={EXPECTED_EMBEDDED_VERIFIER_BYTES} observed={verifier_size}",
            )
        try:
            with verifier.open("rb") as handle:
                verifier_bytes = handle.read(EXPECTED_EMBEDDED_VERIFIER_BYTES + 1)
        except MemoryError:
            fail("EMBEDDED_VERIFIER_SIZE_INVALID", "embedded verifier exceeded the bounded read allocation")
        if len(verifier_bytes) != EXPECTED_EMBEDDED_VERIFIER_BYTES:
            fail(
                "EMBEDDED_VERIFIER_SIZE_INVALID",
                f"embedded verifier changed during bounded read: expected={EXPECTED_EMBEDDED_VERIFIER_BYTES} observed={len(verifier_bytes)}",
            )
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
        if output is None:
            sys.stdout.buffer.write(data)
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(data)
        return 0
    except BootstrapError as exc:
        refusal = {
            "schema": "stc-mary/flight-01-cartridge-bootstrap-verdict/1",
            "status": "REFUSED",
            "code": exc.code,
            "message": str(exc),
            "embeddedVerifierExecuted": False
            if exc.code in {"EMBEDDED_VERIFIER_UNTRUSTED", "EMBEDDED_VERIFIER_SIZE_INVALID"}
            else None,
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
