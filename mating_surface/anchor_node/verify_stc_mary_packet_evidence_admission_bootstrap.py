"""External bootstrap for the packet evidence admission gate.

The standalone gate reports ``bootstrapAuthenticated: false`` when it is called
directly, and it is structurally incapable of setting that flag itself. Only this
external bootstrap may set it, and only after it has:

1. measured the frozen gate bytes on disk;
2. copied those measured bytes into a foreign temporary directory outside the
   repository, outside the packet, and outside the admission workspace;
3. executed the measured copy in an isolated interpreter (``-I -S``) whose working
   directory is that foreign temporary directory;
4. validated the direct receipt, including that the gate bound the stored admission
   source member to the exact bytes that executed, and that the run recorded no packet
   stage, set no operator confirmation, called no packet recorder, mutated no packet
   byte, and generated no human statement or stage confirmation of its own.

The gate is never imported, and the on-disk file is never executed in place.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

BOOTSTRAP_SCHEMA = "stc-mary/packet-evidence-admission-bootstrap-verdict/1"
VERIFIER_FILENAME = "verify_stc_mary_packet_evidence_admission.py"
AUTHORITY = "none"
MINIMUM_PYTHON = (3, 12)
MAX_VERIFIER_BYTES = 1_048_576
ADMITTED_TERMINALS = ("READY_FOR_NAMED_HUMAN_DECISION", "ADMISSIBLE_FOR_PACKET_RECORDING", "HOLD")

ISOLATED_VERIFIER_LAUNCHER = """import sys
source = sys.stdin.buffer.read()
namespace = {
    "__name__": "__main__",
    "__file__": "<measured-stc-mary-packet-evidence-admission-gate>",
    "_STC_MARY_BOOTSTRAP_MEASURED_VERIFIER_BYTES": source,
}
sys.argv = ["<measured-verifier>"] + sys.argv[1:]
exec(
    compile(source, "<measured-stc-mary-packet-evidence-admission-gate>", "exec"),
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


def require_supported_python() -> None:
    if sys.version_info < MINIMUM_PYTHON:
        fail(
            "PYTHON_VERSION_UNSUPPORTED",
            f"Python {MINIMUM_PYTHON[0]}.{MINIMUM_PYTHON[1]} or newer is required for junction-safe custody",
        )


def canonical_json_bytes(value: Any) -> bytes:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return (text + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def coordinate_component_is_link(path: Path, *, code: str, label: str) -> bool:
    require_supported_python()
    try:
        return path.is_symlink() or path.is_junction()
    except OSError as exc:
        fail(code, f"{label} component could not be inspected: {exc}")
        raise


def validate_lexical_coordinate(path: Path, *, label: str, code: str) -> Path:
    require_supported_python()
    if any(part == os.pardir for part in path.parts):
        fail(code, f"{label} may not contain a parent-directory segment")
    try:
        supplied = path.expanduser()
    except RuntimeError as exc:
        fail(code, f"{label} user expansion failed: {exc}")
        raise
    try:
        absolute = Path(os.path.abspath(os.fspath(supplied)))
    except (OSError, ValueError) as exc:
        fail(code, f"{label} could not be made absolute: {exc}")
        raise
    parts = absolute.parts
    if not parts:
        fail(code, f"{label} is empty")
    current = Path(parts[0])
    if coordinate_component_is_link(current, code=code, label=label):
        fail(code, f"{label} contains a symlink or junction component")
    for part in parts[1:]:
        current = current / part
        if coordinate_component_is_link(current, code=code, label=label):
            fail(code, f"{label} contains a symlink or junction component")
    return absolute


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def measure_verifier(anchor: Path) -> tuple[Path, bytes, str]:
    verifier = anchor / VERIFIER_FILENAME
    if coordinate_component_is_link(verifier, code="VERIFIER_MISSING", label="verifier") or not verifier.is_file():
        fail("VERIFIER_MISSING", "the admitted gate is missing, linked, or not a regular file")
    size = verifier.stat().st_size
    if size > MAX_VERIFIER_BYTES:
        fail("VERIFIER_SIZE_INVALID", "the admitted gate exceeds the bounded read allocation")
    with verifier.open("rb") as handle:
        data = handle.read(MAX_VERIFIER_BYTES + 1)
    if len(data) != size:
        fail("VERIFIER_SIZE_INVALID", "the admitted gate changed during the bounded read")
    return verifier, data, sha256_bytes(data)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure and isolate the STC MARY packet evidence admission gate, then execute the measured bytes"
    )
    parser.add_argument("--workstation", type=Path, required=True)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--admission-source-root", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    scratch: str | None = None
    try:
        require_supported_python()
        anchor = Path(__file__).resolve().parent
        _verifier, verifier_bytes, observed = measure_verifier(anchor)

        output = None
        if args.out is not None:
            output = validate_lexical_coordinate(
                args.out, label="verdict output coordinate", code="VERDICT_PATH_INVALID"
            )
            for forbidden, label in (
                (args.packet, "packet"),
                (args.candidates, "admission workspace"),
                (args.admission_source_root, "admission source root"),
            ):
                if is_within(output, Path(os.path.abspath(os.fspath(forbidden)))):
                    fail("VERDICT_INSIDE_MEASURED_SURFACE", f"bootstrap verdict may not be written inside the {label}")
            if output.exists():
                fail("VERDICT_OUTPUT_EXISTS", "bootstrap verdict output must not already exist")

        scratch = tempfile.mkdtemp(prefix="stc-mary-evidence-admission-")
        foreign = Path(scratch).resolve()
        # The isolation directory must be foreign to every surface this run measures or
        # reads: the admission source root, the frozen workstation, the configured packet,
        # and the admission workspace. It is deliberately NOT compared against the
        # bootstrap's own parent tree, which may legitimately be a staging directory
        # during qualification.
        for measured, label in (
            (args.admission_source_root, "admission source root"),
            (args.workstation, "workstation"),
            (args.packet, "packet"),
            (args.candidates, "admission workspace"),
        ):
            if is_within(foreign, Path(os.path.abspath(os.fspath(measured)))):
                fail("FOREIGN_DIRECTORY_UNSAFE", f"the isolation directory is inside the {label}")

        completed = subprocess.run(
            [
                sys.executable,
                "-I",
                "-S",
                "-c",
                ISOLATED_VERIFIER_LAUNCHER,
                "--workstation",
                str(args.workstation),
                "--packet",
                str(args.packet),
                "--candidates",
                str(args.candidates),
                "--profile",
                str(args.profile),
                "--admission-source-root",
                str(args.admission_source_root),
            ],
            cwd=str(foreign),
            input=verifier_bytes,
            check=False,
            capture_output=True,
        )
        try:
            receipt = json.loads(completed.stdout.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            fail("VERIFIER_OUTPUT_INVALID", str(exc))
            raise
        if not isinstance(receipt, dict):
            fail("VERIFIER_OUTPUT_INVALID", "the measured gate did not emit an object")
        if completed.returncode != 0 or receipt.get("status") != "PASS":
            fail(str(receipt.get("code", "ADMISSION_REFUSED")), str(receipt.get("message", "the measured gate refused")))
        if receipt.get("terminal") not in ADMITTED_TERMINALS:
            fail("VERDICT_TERMINAL_INVALID", "the measured gate reported a terminal outside the admitted denominator")
        if receipt.get("bootstrapAuthenticated") is not False:
            fail(
                "VERDICT_BOOTSTRAP_STATE_INVALID",
                "the measured gate may not self-assert bootstrap authentication",
            )
        if receipt.get("measuredVerifierSha256") != observed:
            fail(
                "VERIFIER_MEMBER_BINDING_INVALID",
                "the measured gate did not bind the stored admission source member to the executed bytes",
            )
        if (
            receipt.get("packetStagesRecorded") != 0
            or receipt.get("operatorConfirmedFlagsSet") != 0
            or receipt.get("packetRecorderInvoked") is not False
            or receipt.get("packetMutated") is not False
        ):
            fail("VERDICT_RECORDING_STATE_INVALID", "the measured gate reported packet recording or mutation")
        if (
            receipt.get("humanStatementsGeneratedByThisGate") != 0
            or receipt.get("stageConfirmationsIssuedByThisGate") != 0
        ):
            fail(
                "VERDICT_HUMAN_DECISION_STATE_INVALID",
                "the measured gate reported manufacturing a human statement or stage confirmation",
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
        sys.stdout.buffer.write(
            canonical_json_bytes(
                {
                    "schema": BOOTSTRAP_SCHEMA,
                    "status": "REFUSED",
                    "code": exc.code,
                    "message": str(exc),
                    "bootstrapAuthenticated": False,
                    "verifierExecuted": exc.code not in {"VERIFIER_MISSING", "VERIFIER_SIZE_INVALID"},
                    "packetStagesRecorded": 0,
                    "operatorConfirmedFlagsSet": 0,
                    "authority": AUTHORITY,
                }
            )
        )
        return 1
    except (OSError, ValueError) as exc:
        sys.stdout.buffer.write(
            canonical_json_bytes(
                {
                    "schema": BOOTSTRAP_SCHEMA,
                    "status": "REFUSED",
                    "code": "BOOTSTRAP_FILESYSTEM_ERROR",
                    "message": str(exc),
                    "bootstrapAuthenticated": False,
                    "packetStagesRecorded": 0,
                    "operatorConfirmedFlagsSet": 0,
                    "authority": AUTHORITY,
                }
            )
        )
        return 1
    finally:
        if scratch is not None:
            shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
