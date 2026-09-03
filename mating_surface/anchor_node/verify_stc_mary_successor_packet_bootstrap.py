"""Measure and isolate the successor packet verifier, then execute the measured bytes.

The verifier cannot authenticate itself. Run directly it reports
``bootstrapAuthenticated: false`` and refuses to claim otherwise. This bootstrap reads the
verifier's bytes from disk, digests them, pipes exactly those bytes into a fresh isolated
interpreter with a foreign working directory, and only then compares what the measured
verifier says it executed against what this process actually measured.

The packet it verifies carries its own copy of the verifier as a source member. A run is
authenticated only when the executed bytes, the bytes on disk and the bytes the packet
carries are all one digest.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

BOOTSTRAP_SCHEMA = "stc-mary/successor-packet-verification-bootstrap-verdict/1"
VERIFIER_NAME = "verify_stc_mary_successor_packet.py"
MINIMUM_PYTHON = (3, 12)
AUTHORITY = "none"

# The measured bytes are executed from stdin, never from a path the child could resolve
# to a different file than the one this process digested.
ISOLATED_VERIFIER_LAUNCHER = """
import sys
source = sys.stdin.buffer.read()
namespace = {
    "__name__": "stc_mary_successor_packet_verifier_measured",
    "__file__": "<measured-successor-packet-verifier>",
    "_STC_MARY_SUCCESSOR_MEASURED_VERIFIER_BYTES": source,
}
exec(compile(source, "<measured-successor-packet-verifier>", "exec"), namespace)
raise SystemExit(namespace["main"](sys.argv[1:]))
"""


class BootstrapError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def fail(code: str, message: str) -> None:
    raise BootstrapError(code, message)


def require_supported_python() -> None:
    if sys.version_info[:2] < MINIMUM_PYTHON:
        fail(
            "PYTHON_RUNTIME_UNSUPPORTED",
            f"this bootstrap requires Python {MINIMUM_PYTHON[0]}.{MINIMUM_PYTHON[1]} or newer",
        )


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n"
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def scrubbed_environment() -> dict[str, str]:
    admitted = {
        "COMSPEC", "LANG", "LC_ALL", "PATH", "PATHEXT", "SYSTEMDRIVE", "SYSTEMROOT",
        "TEMP", "TMP", "TMPDIR", "WINDIR",
    }
    return {key: value for key, value in os.environ.items() if key.upper() in admitted}


def coordinate_component_is_link(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        if os.name == "nt" and path.exists():
            try:
                return bool(path.lstat().st_file_attributes & 0x400)
            except (OSError, AttributeError):
                return False
        return False
    except OSError:
        return False


def validate_lexical_coordinate(path: Path, *, label: str, code: str) -> Path:
    if any(part == os.pardir for part in path.parts):
        fail(code, f"{label} may not contain a parent-directory segment")
    absolute = Path(os.path.abspath(os.fspath(path.expanduser())))
    current = Path(absolute.parts[0])
    if coordinate_component_is_link(current):
        fail(code, f"{label} contains a symlink or junction component")
    for part in absolute.parts[1:]:
        current = current / part
        if coordinate_component_is_link(current):
            fail(code, f"{label} contains a symlink or junction component")
    return absolute


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def measure_verifier(anchor: Path) -> tuple[Path, bytes, str]:
    verifier = validate_lexical_coordinate(
        anchor / VERIFIER_NAME, label="successor packet verifier", code="VERIFIER_UNREADABLE"
    )
    if not verifier.is_file():
        fail("VERIFIER_UNREADABLE", "the successor packet verifier is not a regular file")
    data = verifier.read_bytes()
    if not data:
        fail("VERIFIER_UNREADABLE", "the successor packet verifier is empty")
    return verifier, data, sha256_bytes(data)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure and isolate the STC MARY successor packet verifier, then execute the measured bytes"
    )
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    return parser.parse_args(argv)


def refusal_document(code: str, message: str) -> dict[str, Any]:
    return {
        "schema": BOOTSTRAP_SCHEMA,
        "status": "REFUSED",
        "code": code,
        "message": message,
        "bootstrapAuthenticated": False,
        "stagesRecordedByThisVerifier": 0,
        "authority": AUTHORITY,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    scratch: str | None = None
    try:
        require_supported_python()
        anchor = Path(__file__).resolve().parent
        _verifier, verifier_bytes, observed = measure_verifier(anchor)

        output = None
        if args.out is not None:
            output = validate_lexical_coordinate(args.out, label="verdict output", code="VERDICT_PATH_INVALID")
            for forbidden, label in ((args.packet, "packet"), (args.repository_root, "repository root")):
                if is_within(output, Path(os.path.abspath(os.fspath(forbidden)))):
                    fail("VERDICT_INSIDE_MEASURED_SURFACE", f"the verdict may not be written inside the {label}")
            if output.exists():
                fail("VERDICT_OUTPUT_EXISTS", "bootstrap verdict output must not already exist")

        scratch = tempfile.mkdtemp(prefix="stc-mary-successor-packet-")
        foreign = Path(scratch).resolve()
        for measured, label in ((args.packet, "packet"), (args.repository_root, "repository root")):
            if is_within(foreign, Path(os.path.abspath(os.fspath(measured)))):
                fail("FOREIGN_DIRECTORY_UNSAFE", f"the isolation directory is inside the {label}")

        completed = subprocess.run(
            [
                sys.executable,
                "-I",
                "-S",
                "-B",
                "-c",
                ISOLATED_VERIFIER_LAUNCHER,
                "--packet",
                str(args.packet),
                "--profile",
                str(args.profile),
                "--repository-root",
                str(args.repository_root),
            ],
            cwd=str(foreign),
            input=verifier_bytes,
            check=False,
            capture_output=True,
            env=scrubbed_environment(),
        )
        try:
            receipt = json.loads(completed.stdout.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            fail("VERIFIER_OUTPUT_INVALID", str(exc))
            raise
        if not isinstance(receipt, dict):
            fail("VERIFIER_OUTPUT_INVALID", "the measured verifier did not emit an object")
        if completed.returncode != 0 or receipt.get("status") != "PASS":
            fail(
                str(receipt.get("code", "SUCCESSOR_PACKET_REFUSED")),
                str(receipt.get("message", "the measured verifier refused")),
            )
        if receipt.get("bootstrapAuthenticated") is not False:
            fail(
                "VERDICT_BOOTSTRAP_STATE_INVALID",
                "the measured verifier may not self-assert bootstrap authentication",
            )
        if receipt.get("measuredVerifierSha256") != observed:
            fail(
                "VERIFIER_MEMBER_BINDING_INVALID",
                "the measured verifier did not bind the packet's stored source member to the executed bytes",
            )
        if (
            receipt.get("stagesRecordedByThisVerifier") != 0
            or receipt.get("packetMutated") is not False
            or receipt.get("completedStageCount") != 0
            or receipt.get("sealed") is not False
        ):
            fail("VERDICT_RECORDING_STATE_INVALID", "the measured verifier reported recording, sealing or mutation")
        if receipt.get("humanPrincipalsAuthenticated") != 0 or receipt.get("evidenceAdmitted") != 0:
            fail(
                "VERDICT_AUTHENTICATION_STATE_INVALID",
                "the measured verifier reported admitting evidence or authenticating a human principal",
            )

        receipt["bootstrapAuthenticated"] = True
        receipt["bootstrapVerifierSha256"] = observed
        receipt["bootstrapVerifier"] = "external-measured-bytes-isolated-before-execution"
        receipt["bootstrapSchema"] = BOOTSTRAP_SCHEMA
        data = canonical_json_bytes(receipt)
        if output is None:
            sys.stdout.buffer.write(data)
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(data)
        return 0
    except BootstrapError as exc:
        sys.stdout.buffer.write(canonical_json_bytes(refusal_document(exc.code, str(exc))))
        return 1
    except (OSError, ValueError) as exc:
        sys.stdout.buffer.write(canonical_json_bytes(refusal_document("BOOTSTRAP_FILESYSTEM_ERROR", str(exc))))
        return 1
    finally:
        if scratch is not None:
            import shutil

            shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
