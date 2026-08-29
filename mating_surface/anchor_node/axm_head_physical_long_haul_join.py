from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import types
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

HERE = Path(__file__).resolve().parent
DEFAULT_PROFILE = HERE / "axm-head-physical-long-haul-join-profile-01.json"
DEFAULT_FIXTURES = HERE / "fixtures" / "axm-head-physical-long-haul-join-cases-01.json"
DEFAULT_VERIFIER = HERE / "verify_axm_head_physical_long_haul_join.py"
STANDALONE_VERIFIER_SHA256 = "2b9761bb612e2092e2290d31ea2d07a7e7bc301daa38e04a6dd7dfdc52c7ad69"
ENVELOPE_SCHEMA = "axm-head/physical-long-haul-verifier-envelope@2"
MAX_JSON_BYTES = 32 * 1024 * 1024
MAX_VERIFIER_BYTES = 4 * 1024 * 1024

WINDOWS_PATH_RE = re.compile(r"(?i)(?:^|[\s\"'])(?:[a-z]:[\\/]|\\\\[^\\/]+[\\/])")
IPV4_RE = re.compile(r"(?<![0-9])(?:25[0-5]|2[0-4][0-9]|1?[0-9]{1,2})(?:\.(?:25[0-5]|2[0-4][0-9]|1?[0-9]{1,2})){3}(?![0-9])")
URI_RE = re.compile(r"(?i)\b(?:https?|ssh|tcp|udp|ws|wss)://")
CREDENTIAL_RE = re.compile(r"AKIA[0-9A-Z]{16}|BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY|Authorization:\s*Bearer|SYNTHETIC-CREDENTIAL-[A-Za-z0-9._-]+", re.I)
PRIVATE_HOST_RE = re.compile(r"\b(?:OCTO-(?:W|L|N)\d+|PRIVATE-HOST-\d+)\b", re.I)
FORBIDDEN_PRIVATE_KEYS = {
    "privatePath",
    "hostname",
    "endpoint",
    "credential",
    "environment",
    "operatorRecord",
    "stdout",
    "stderr",
    "telemetryBody",
    "evidenceBody",
    "evidenceFilename",
    "hardwareSerial",
    "seatIdentity",
}


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


def pretty_json_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        fail("NON_CANONICAL_JSON", str(exc))
    return (text + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_regular_file_bytes(path: Path, *, label: str, maximum: int) -> bytes:
    try:
        before = path.lstat()
    except OSError as exc:
        fail("FILE_READ_FAILED", f"{label}: {path}: {exc}")
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        fail("REGULAR_FILE_REQUIRED", f"{label}: {path} must be one regular non-symlink file")
    if before.st_size > maximum:
        fail("FILE_SIZE_LIMIT", f"{label}: {path} exceeds {maximum} bytes")

    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        fail("FILE_READ_FAILED", f"{label}: {path}: {exc}")
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            fail("REGULAR_FILE_REQUIRED", f"{label}: {path} did not open as a regular file")
        if before.st_dev != opened.st_dev or before.st_ino != opened.st_ino:
            fail("FILE_IDENTITY_CHANGED", f"{label}: {path} changed before it was opened")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, maximum + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum:
                fail("FILE_SIZE_LIMIT", f"{label}: {path} exceeds {maximum} bytes")
        after = os.fstat(descriptor)
        stable = (
            opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns
        ) == (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns
        )
        if not stable:
            fail("FILE_CHANGED_DURING_READ", f"{label}: {path} changed while it was measured")
        data = b"".join(chunks)
        if len(data) != after.st_size:
            fail("FILE_SIZE_CHANGED", f"{label}: {path} measured byte count differs from file size")
        return data
    finally:
        os.close(descriptor)


def parse_json_object_bytes(data: bytes, *, label: str) -> dict[str, Any]:
    if data.startswith(b"\xef\xbb\xbf"):
        fail("UTF8_BOM_FORBIDDEN", f"{label} contains a UTF-8 BOM")

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                fail("DUPLICATE_JSON_KEY", f"{label} contains duplicate key {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=reject_duplicate_keys)
    except BootstrapError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        fail("JSON_READ_FAILED", f"{label}: {exc}")
    if not isinstance(value, dict):
        fail("JSON_OBJECT_REQUIRED", f"{label} must contain one JSON object")
    return value


def require_measured_verifier(path: Path = DEFAULT_VERIFIER) -> bytes:
    data = read_regular_file_bytes(path, label="standalone verifier", maximum=MAX_VERIFIER_BYTES)
    digest = sha256_bytes(data)
    if digest != STANDALONE_VERIFIER_SHA256:
        fail("VERIFIER_SOURCE_DIGEST_INVALID", f"standalone verifier digest differs: {digest}")
    return data


def ensure_output_parent(path: Path) -> Path:
    absolute = path.absolute()
    if absolute.exists() or absolute.is_symlink():
        fail("OUTPUT_EXISTS", f"output already exists: {absolute}")
    parent = absolute.parent
    try:
        metadata = parent.lstat()
    except OSError as exc:
        fail("OUTPUT_PARENT_INVALID", f"output parent is unavailable: {parent}: {exc}")
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        fail("OUTPUT_PARENT_INVALID", f"output parent must be one existing non-symlink directory: {parent}")
    return absolute


def write_new_output(path: Path, data: bytes) -> None:
    absolute = ensure_output_parent(path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(absolute, flags, 0o600)
        view = memoryview(data)
        written = 0
        while written < len(view):
            count = os.write(descriptor, view[written:])
            if count <= 0:
                fail("OUTPUT_WRITE_FAILED", f"zero-byte write for {absolute}")
            written += count
        os.fsync(descriptor)
    except FileExistsError:
        fail("OUTPUT_EXISTS", f"output already exists: {absolute}")
    except OSError as exc:
        try:
            if absolute.exists():
                absolute.unlink()
        except OSError:
            pass
        fail("OUTPUT_WRITE_FAILED", f"{absolute}: {exc}")
    finally:
        if descriptor is not None:
            os.close(descriptor)


def scan_forbidden_private_material(value: Any, label: str = "receipt") -> None:
    def walk(node: Any, path: str) -> None:
        if isinstance(node, Mapping):
            for key, child in node.items():
                if key in FORBIDDEN_PRIVATE_KEYS:
                    fail("PRIVATE_MATERIAL_KEY_FORBIDDEN", f"{path}.{key} is not an allowlisted field")
                walk(child, f"{path}.{key}")
        elif isinstance(node, list):
            for index, child in enumerate(node):
                walk(child, f"{path}[{index}]")
        elif isinstance(node, str):
            if WINDOWS_PATH_RE.search(node):
                fail("PRIVATE_PATH_DETECTED", f"{path} contains a Windows or UNC path")
            if PRIVATE_HOST_RE.search(node):
                fail("PRIVATE_HOST_DETECTED", f"{path} contains a private Estate host identity")
            if IPV4_RE.search(node) or URI_RE.search(node):
                fail("PRIVATE_ENDPOINT_DETECTED", f"{path} contains a network endpoint")
            if CREDENTIAL_RE.search(node):
                fail("CREDENTIAL_MATERIAL_DETECTED", f"{path} contains credential-shaped material")

    walk(value, label)


@contextmanager
def trusted_verifier_module() -> Iterator[types.ModuleType]:
    verifier_bytes = require_measured_verifier()
    with tempfile.TemporaryDirectory(prefix="axm-head-postflight-join-module-") as temp_text:
        measured_path = Path(temp_text) / "verify_join.py"
        measured_path.write_bytes(verifier_bytes)
        module = types.ModuleType("axm_head_physical_long_haul_join_measured_verifier")
        module.__file__ = str(measured_path)
        module.__package__ = None
        code = compile(verifier_bytes, str(measured_path), "exec", dont_inherit=True)
        exec(code, module.__dict__)
        yield module


def bootstrap_verify(*, profile_path: Path, input_path: Path, out: Path | None = None) -> dict[str, Any]:
    verifier_bytes = require_measured_verifier()
    measured_digest = sha256_bytes(verifier_bytes)
    profile_bytes = read_regular_file_bytes(profile_path, label="profile", maximum=MAX_JSON_BYTES)
    input_bytes = read_regular_file_bytes(input_path, label="join input", maximum=MAX_JSON_BYTES)
    # Parse once here to reject duplicate keys and malformed encodings before any subprocess is launched.
    parse_json_object_bytes(profile_bytes, label=str(profile_path))
    parse_json_object_bytes(input_bytes, label=str(input_path))

    with tempfile.TemporaryDirectory(prefix="axm-head-postflight-join-verifier-") as temp_text:
        root = Path(temp_text)
        measured_path = root / "verify_join.py"
        measured_profile = root / "profile.json"
        measured_input = root / "input.json"
        measured_path.write_bytes(verifier_bytes)
        measured_profile.write_bytes(profile_bytes)
        measured_input.write_bytes(input_bytes)
        environment = dict(os.environ)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["PYTHONHASHSEED"] = "0"
        result = subprocess.run(
            [sys.executable, str(measured_path), str(measured_profile), str(measured_input)],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            check=False,
        )
        if result.stderr:
            fail("VERIFIER_STDERR_NONEMPTY", result.stderr.decode("utf-8", errors="replace"))
        receipt = parse_json_object_bytes(result.stdout, label="standalone verifier stdout")
        if result.returncode != 0 or receipt.get("status") != "PASS":
            code = receipt.get("code", "VERIFIER_REFUSED")
            message = receipt.get("message", "standalone verifier refused the input")
            fail(str(code), str(message))
        if receipt.get("schema") != ENVELOPE_SCHEMA:
            fail("VERIFIER_ENVELOPE_SCHEMA_INVALID", "standalone verifier envelope schema differs")
        if receipt.get("bootstrapAuthenticated") is not False:
            fail("VERIFIER_AUTHENTICATION_STATE_INVALID", "standalone verifier claimed bootstrap authentication")
        if receipt.get("standaloneVerifierSha256") != measured_digest:
            fail("VERIFIER_SELF_IDENTITY_MISMATCH", "standalone verifier did not report the measured bytes")
        receipt["bootstrapAuthenticated"] = True
        receipt["standaloneVerifierSha256"] = measured_digest
        scan_forbidden_private_material(receipt, "authenticatedReceipt")
        data = canonical_json_bytes(receipt)
        if out is not None:
            write_new_output(out, data)
        sys.stdout.buffer.write(data)
        return receipt


def refused_envelope(exc: BootstrapError) -> dict[str, Any]:
    return {
        "schema": ENVELOPE_SCHEMA,
        "status": "REFUSED",
        "bootstrapAuthenticated": False,
        "code": exc.code,
        "message": str(exc),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build fixtures and authenticate the AXM HEAD postflight JOIN-v2 verifier")
    sub = parser.add_subparsers(dest="command", required=True)

    profile_parser = sub.add_parser("validate-profile")
    profile_parser.add_argument("profile", nargs="?", type=Path, default=DEFAULT_PROFILE)

    fixtures_parser = sub.add_parser("validate-fixtures")
    fixtures_parser.add_argument("profile", nargs="?", type=Path, default=DEFAULT_PROFILE)
    fixtures_parser.add_argument("fixtures", nargs="?", type=Path, default=DEFAULT_FIXTURES)

    emit_parser = sub.add_parser("emit-fixture")
    emit_parser.add_argument("case_id")
    emit_parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    emit_parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    emit_parser.add_argument("--out", required=True, type=Path)

    decide_parser = sub.add_parser("evaluate")
    decide_parser.add_argument("input", type=Path)
    decide_parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)

    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("input", type=Path)
    verify_parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    verify_parser.add_argument("--out", type=Path)

    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            bootstrap_verify(profile_path=args.profile, input_path=args.input, out=args.out)
            return 0

        with trusted_verifier_module() as verify:
            if args.command == "validate-profile":
                profile = verify.validate_profile(args.profile)
                result = {
                    "schema": "axm-head/physical-long-haul-profile-validation@2",
                    "status": "PASS",
                    "profileId": profile["profileId"],
                    "canonicalSha256": verify.PROFILE_CANONICAL_SHA256,
                    "objectCount": len(profile["objectSchemas"]),
                    "terminalStates": profile["terminalStates"],
                }
                sys.stdout.buffer.write(verify.canonical_json_bytes(result))
            elif args.command == "validate-fixtures":
                profile = verify.validate_profile(args.profile)
                catalog = verify.validate_catalog(args.fixtures, profile)
                result = {
                    "schema": "axm-head/physical-long-haul-fixture-validation@2",
                    "status": "PASS",
                    "profileId": profile["profileId"],
                    "canonicalSha256": verify.FIXTURE_CATALOG_CANONICAL_SHA256,
                    "caseIds": [row["caseId"] for row in catalog["cases"]],
                    "privateSelfAttestedFixtureCount": 0,
                }
                sys.stdout.buffer.write(verify.canonical_json_bytes(result))
            elif args.command == "emit-fixture":
                profile = verify.validate_profile(args.profile)
                catalog = verify.validate_catalog(args.fixtures, profile)
                case = verify.find_case(catalog, args.case_id)
                write_new_output(args.out, verify.pretty_json_bytes(case["input"]))
                result = {
                    "schema": "axm-head/physical-long-haul-fixture-emission@2",
                    "status": "PASS",
                    "caseId": case["caseId"],
                    "expectedTerminal": case["expectedTerminal"],
                    "outputCreated": True,
                }
                sys.stdout.buffer.write(verify.canonical_json_bytes(result))
            else:
                profile = verify.validate_profile(args.profile)
                input_value = verify.validate_input(args.input)
                result = verify.evaluate_input(profile, input_value)
                sys.stdout.buffer.write(verify.canonical_json_bytes(result))
        return 0
    except BootstrapError as exc:
        sys.stdout.buffer.write(canonical_json_bytes(refused_envelope(exc)))
        return 2
    except Exception as exc:
        # A trusted measured verifier may raise its own JoinError class. Preserve its stable code without
        # importing or executing the sibling verifier before digest authentication.
        code = getattr(exc, "code", None)
        if isinstance(code, str):
            wrapped = BootstrapError(code, str(exc))
            sys.stdout.buffer.write(canonical_json_bytes(refused_envelope(wrapped)))
            return 2
        raise


if __name__ == "__main__":
    raise SystemExit(main())
