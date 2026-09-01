from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SCHEMA = "axm-head/browser-physical-audition-packet-bootstrap-verdict@1"
DIRECT_SCHEMA = "axm-head/browser-physical-audition-packet-verdict@1"
MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_SOURCE_BYTES = 4 * 1024 * 1024


def pretty(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def sha256_ref(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def lexical_absolute(path: str | Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def is_linkish(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        junction = getattr(path, "is_junction", None)
        if callable(junction) and junction():
            return True
        metadata = path.lstat()
    except (FileNotFoundError, OSError, ValueError):
        return False
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(reparse and getattr(metadata, "st_file_attributes", 0) & reparse)


def assert_unlinked_coordinate(path: str | Path) -> Path:
    absolute = lexical_absolute(path)
    for candidate in reversed((absolute, *absolute.parents)):
        if candidate.exists() or candidate.is_symlink():
            if is_linkish(candidate):
                raise RuntimeError(f"unsafe linked coordinate: {candidate}")
    return absolute


def path_is_within(path: Path, root: Path) -> bool:
    absolute_path = lexical_absolute(path)
    absolute_root = lexical_absolute(root)
    try:
        common = os.path.commonpath((str(absolute_path), str(absolute_root)))
    except ValueError:
        return False
    return os.path.normcase(common) == os.path.normcase(str(absolute_root))


def secure_read_bytes(
    path: str | Path,
    *,
    maximum_bytes: int,
    expected_bytes: int | None = None,
    expected_sha256: str | None = None,
) -> bytes:
    absolute = assert_unlinked_coordinate(path)
    try:
        before = absolute.lstat()
    except OSError as exc:
        raise RuntimeError(f"required file unavailable: {absolute}: {exc}") from exc
    if not stat.S_ISREG(before.st_mode):
        raise RuntimeError(f"regular file required: {absolute}")
    limit = expected_bytes if expected_bytes is not None else maximum_bytes
    if not isinstance(limit, int) or limit < 0 or limit > maximum_bytes:
        raise RuntimeError(f"invalid file-size limit: {absolute}: {limit}")
    if expected_bytes is not None and before.st_size != expected_bytes:
        raise RuntimeError(f"file size mismatch: {absolute}: expected={expected_bytes} observed={before.st_size}")
    if expected_bytes is None and before.st_size > maximum_bytes:
        raise RuntimeError(f"file exceeds bound: {absolute}: {before.st_size}")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(absolute, flags)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise RuntimeError(f"regular file required: {absolute}")
        chunks: list[bytes] = []
        remaining = limit + 1
        while remaining > 0:
            chunk = os.read(descriptor, min(65536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
        after_open = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if len(data) > limit:
        raise RuntimeError(f"file exceeds bound: {absolute}: {len(data)}")
    if opened.st_size != after_open.st_size or after_open.st_size != len(data):
        raise RuntimeError(f"file changed during read: {absolute}")
    after_path = absolute.lstat()
    if before.st_size != after_path.st_size or getattr(before, "st_mtime_ns", None) != getattr(after_path, "st_mtime_ns", None):
        raise RuntimeError(f"file changed during read: {absolute}")
    assert_unlinked_coordinate(absolute)
    observed = sha256_ref(data)
    if expected_sha256 is not None and observed != expected_sha256:
        raise RuntimeError(f"source substitution: {absolute}: expected={expected_sha256} observed={observed}")
    return data


def write_new(path: Path, data: bytes) -> None:
    absolute = lexical_absolute(path)
    assert_unlinked_coordinate(absolute.parent)
    absolute.parent.mkdir(parents=True, exist_ok=True)
    assert_unlinked_coordinate(absolute.parent)
    if absolute.exists() or absolute.is_symlink():
        existing = secure_read_bytes(absolute, maximum_bytes=max(MAX_SOURCE_BYTES, len(data)), expected_bytes=len(data))
        if existing != data:
            raise RuntimeError(f"output collision: {absolute}")
        return
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(absolute, flags, 0o600)
    try:
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise RuntimeError(f"output write refused: {absolute}")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    if secure_read_bytes(absolute, maximum_bytes=max(MAX_SOURCE_BYTES, len(data)), expected_bytes=len(data)) != data:
        raise RuntimeError(f"output write mismatch: {absolute}")


def binding_for(profile: dict[str, Any], basename: str) -> dict[str, Any]:
    rows = [
        row
        for row in profile.get("packetSourceBindings", [])
        if isinstance(row, dict) and Path(row.get("path", "")).name == basename
    ]
    if len(rows) != 1:
        raise RuntimeError(f"packet source binding missing or duplicated: {basename}")
    row = rows[0]
    if set(row) != {"bytes", "path", "sha256"}:
        raise RuntimeError(f"packet source binding malformed: {basename}")
    if not isinstance(row["bytes"], int) or row["bytes"] <= 0 or row["bytes"] > MAX_SOURCE_BYTES:
        raise RuntimeError(f"packet source byte bound invalid: {basename}")
    return row


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("verifier")
    parser.add_argument("profile")
    parser.add_argument("packet_root")
    parser.add_argument("decision")
    parser.add_argument("--now-ms", type=int, required=True)
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    output: Path | None = None
    try:
        verifier = assert_unlinked_coordinate(args.verifier)
        profile_path = assert_unlinked_coordinate(args.profile)
        packet_root = assert_unlinked_coordinate(args.packet_root)
        decision = assert_unlinked_coordinate(args.decision)
        source_root = profile_path.parent
        if verifier.parent != source_root:
            raise RuntimeError(f"packet verifier is outside profile source root: {verifier}")
        if decision != packet_root / "private" / "packet-decision.json":
            raise RuntimeError(f"packet decision coordinate invalid: {decision}")
        if args.out:
            output = assert_unlinked_coordinate(args.out)
            if path_is_within(output, packet_root):
                raise RuntimeError(f"output lies inside measured packet: {output}")
            if path_is_within(output, source_root):
                raise RuntimeError(f"output lies inside measured source: {output}")

        profile_bytes = secure_read_bytes(profile_path, maximum_bytes=MAX_JSON_BYTES)
        profile = json.loads(profile_bytes.decode("utf-8"))
        if not isinstance(profile, dict):
            raise RuntimeError("profile object required")
        binding = binding_for(profile, verifier.name)
        source = secure_read_bytes(
            verifier,
            maximum_bytes=MAX_SOURCE_BYTES,
            expected_bytes=binding["bytes"],
            expected_sha256=binding["sha256"],
        )
        measured_ref = sha256_ref(source)
        launcher = (
            "import sys; source=sys.stdin.buffer.read(); "
            "sys.argv=['measured-packet-verifier', *sys.argv[1:]]; "
            "ns={'__name__':'__main__','__file__':'<measured-packet-verifier>'}; "
            "exec(compile(source,'<measured-packet-verifier>','exec'),ns)"
        )
        with tempfile.TemporaryDirectory(prefix="axm-browser-physical-packet-bootstrap-") as temporary:
            result = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-S",
                    "-c",
                    launcher,
                    str(profile_path),
                    str(packet_root),
                    str(decision),
                    "--now-ms",
                    str(args.now_ms),
                ],
                input=source,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=source_root,
                check=False,
                timeout=120,
            )
        if result.stderr != b"":
            raise RuntimeError("measured packet verifier emitted stderr")
        direct = json.loads(result.stdout.decode("utf-8"))
        if result.returncode != 0 or direct.get("schema") != DIRECT_SCHEMA or direct.get("status") != "PASS":
            raise RuntimeError(f"direct packet verifier refused: {direct}")
        if direct.get("bootstrapAuthenticated") is not False:
            raise RuntimeError("direct packet verifier self-authenticated")
        if direct.get("seatCount", 0) > 0 and direct.get("rawEvidenceReconstructed") is not True:
            raise RuntimeError("direct packet verifier did not reconstruct all supplied raw evidence")
        public = direct.get("publicProjection")
        if not isinstance(public, dict) or direct.get("publicProjectionDigest") != sha256_ref(
            json.dumps(public, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ):
            raise RuntimeError("direct packet verifier public projection binding is invalid")
        secure_read_bytes(
            verifier,
            maximum_bytes=MAX_SOURCE_BYTES,
            expected_bytes=binding["bytes"],
            expected_sha256=binding["sha256"],
        )
        body = {
            "schema": SCHEMA,
            "status": "PASS",
            "terminal": direct["terminal"],
            "reasonCodes": direct["reasonCodes"],
            "packetDecisionId": direct["packetDecisionId"],
            "packetEvidenceRoot": direct["packetEvidenceRoot"],
            "sourceBindingId": direct["sourceBindingId"],
            "seatCount": direct["seatCount"],
            "seatCapturesIndependentlyReconstructed": direct["seatCapturesIndependentlyReconstructed"],
            "namedHumanConfirmed": direct["namedHumanConfirmed"],
            "syntheticConformanceOnly": direct["syntheticConformanceOnly"],
            "physicalExecutionObserved": direct["physicalExecutionObserved"],
            "publicProjection": public,
            "publicProjectionDigest": direct["publicProjectionDigest"],
            "embeddedVerifierSha256": measured_ref,
            "storedVerifierMemberBound": True,
            "rawEvidenceReconstructed": direct["rawEvidenceReconstructed"],
            "storedDecisionReconstructed": True,
            "publicProjectionReconstructed": True,
            "bootstrapAuthenticated": True,
            "actualSupplierQualified": False,
            "supplierAdmissionReceiptPresent": False,
            "physicalEstateQualified": False,
            "missionAuthority": "none",
            "commandAuthority": "none",
            "targetingAuthority": "none",
            "engagementAuthority": "none",
            "effectorAuthority": "none",
            "weaponsAuthority": "none",
        }
        data = pretty(body)
        if output is not None:
            write_new(output, data)
        sys.stdout.buffer.write(data)
        return 0
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
        RuntimeError,
        subprocess.TimeoutExpired,
    ) as exc:
        body = {
            "schema": SCHEMA,
            "status": "REFUSED",
            "code": "BOOTSTRAP_REFUSED",
            "message": str(exc),
            "bootstrapAuthenticated": False,
            "actualSupplierQualified": False,
            "physicalExecutionObserved": False,
            "authority": "none",
        }
        data = pretty(body)
        if output is not None:
            try:
                write_new(output, data)
            except Exception:
                pass
        sys.stdout.buffer.write(data)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
