from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from verify_stc_mary_flight_01_cartridge import (
    AUTHORITY,
    EXPECTED_FILES,
    MANIFEST_SCHEMA,
    PROFILE_CANONICAL_SHA256,
    PROFILE_ID,
    TERMINAL,
    build_mission,
    build_public_status,
    build_source_binding,
    build_work_unit,
    canonical_json_bytes,
    content_id,
    parse_json_bytes,
    pretty_json_bytes,
    sha256_bytes,
    validate_profile,
    verify_cartridge,
)

EXPECTED_VERIFIER_SHA256 = "35208fc39b454bc3b2d621c847f163a583dff14ded29a95223ac6bfd64f709cd"
PROFILE_FILENAME = "stc-mary-flight-01-cartridge-profile-01.json"
VERIFIER_FILENAME = "verify_stc_mary_flight_01_cartridge.py"
BOOTSTRAP_FILENAME = "verify_stc_mary_flight_01_cartridge_bootstrap.py"


class BuildError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def fail(code: str, message: str) -> None:
    raise BuildError(code, message)


def load_profile(path: Path) -> dict[str, Any]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        fail("PROFILE_READ_FAILED", str(exc))
    return validate_profile(parse_json_bytes(data, str(path)))


def has_git_ancestor(path: Path) -> bool:
    current = path.resolve(strict=False)
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return True
    return False


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


def validate_output_root(out: Path) -> Path:
    resolved = out.resolve(strict=False)
    if out.exists():
        fail("OUTPUT_EXISTS", "cartridge output must not already exist")
    if not out.parent.exists() or not out.parent.is_dir() or out.parent.is_symlink():
        fail("OUTPUT_PARENT_INVALID", "cartridge output parent must be an existing regular directory")
    if resolved == Path(resolved.anchor) or resolved == Path.home().resolve() or resolved == Path.cwd().resolve():
        fail("OUTPUT_ROOT_UNSAFE", "cartridge output may not be a filesystem root, home, or current directory")
    if has_git_ancestor(out.parent):
        fail("REPOSITORY_LOCAL_OUTPUT_REFUSED", "cartridge output must remain outside every Git repository")
    return resolved


def validate_projection_output(root: Path, out: Path | None) -> None:
    if out is not None and is_within(out, root):
        fail("PROJECTION_INSIDE_CARTRIDGE", "public projection may not be written inside the measured cartridge")


def source_file(name: str) -> Path:
    path = Path(__file__).resolve().parent / name
    if not path.is_file() or path.is_symlink():
        fail("SOURCE_MEMBER_MISSING", name)
    return path


def build_cartridge(profile_path: Path, out: Path) -> dict[str, Any]:
    profile = load_profile(profile_path)
    out = validate_output_root(out)

    verifier_source = source_file(VERIFIER_FILENAME)
    verifier_bytes = verifier_source.read_bytes()
    if b"\r" in verifier_bytes:
        fail("VERIFIER_NON_LF_BYTES", "standalone verifier must use LF-only bytes")
    if sha256_bytes(verifier_bytes) != EXPECTED_VERIFIER_SHA256:
        fail("VERIFIER_SOURCE_DIGEST_INVALID", "standalone verifier source differs from the frozen identity")

    source_binding = build_source_binding(profile)
    work_unit = build_work_unit(profile)
    mission = build_mission(profile, source_binding, work_unit)
    status = build_public_status(profile, mission, work_unit, source_binding)

    member_payloads: dict[str, bytes] = {
        "CARTRIDGE/mission.json": pretty_json_bytes(mission),
        "CARTRIDGE/work-unit.json": pretty_json_bytes(work_unit),
        "PUBLIC/status.json": pretty_json_bytes(status),
        "RECOVERY/profile.json": pretty_json_bytes(profile),
        "RECOVERY/source-binding.json": pretty_json_bytes(source_binding),
        "RECOVERY/verify_cartridge.py": verifier_bytes,
    }
    if tuple(sorted(member_payloads)) != tuple(sorted(EXPECTED_FILES)):
        fail("MEMBER_DENOMINATOR_INTERNAL_ERROR", "builder member denominator differs")

    rows = [
        {"path": relative, "bytes": len(data), "sha256": sha256_bytes(data)}
        for relative, data in sorted(member_payloads.items())
    ]
    manifest_body = {
        "schema": MANIFEST_SCHEMA,
        "profileId": PROFILE_ID,
        "cartridgeId": mission["cartridgeId"],
        "terminal": TERMINAL,
        "memberCount": len(rows),
        "members": rows,
        "authority": AUTHORITY,
        "claimBoundary": profile["claimBoundary"],
    }
    manifest = {**manifest_body, "bundleId": content_id("stcmarycartridgebundle1", manifest_body)}

    try:
        out.mkdir()
        for directory in ("CARTRIDGE", "PUBLIC", "RECOVERY"):
            (out / directory).mkdir()
        for relative, data in member_payloads.items():
            target = out / relative
            target.write_bytes(data)
        (out / "MANIFEST.json").write_bytes(pretty_json_bytes(manifest))
    except OSError:
        raise

    verdict = verify_cartridge(out)
    return {
        "schema": "stc-mary/flight-01-cartridge-build/1",
        "status": "PASS",
        "bundleId": verdict["bundleId"],
        "cartridgeId": verdict["cartridgeId"],
        "missionId": verdict["missionId"],
        "workUnitId": verdict["workUnitId"],
        "sourceBindingId": verdict["sourceBindingId"],
        "terminal": TERMINAL,
        "memberCount": len(rows),
        "output": str(out),
        "physicalExecutionStarted": False,
        "workstationInitialized": False,
        "authority": AUTHORITY,
    }


def run_bootstrap(root: Path, out: Path | None = None) -> dict[str, Any]:
    supplied_root = validate_cartridge_coordinate(root)
    bootstrap = source_file(BOOTSTRAP_FILENAME)
    command = [sys.executable, str(bootstrap), str(supplied_root)]
    if out is not None:
        command.extend(["--out", str(out)])
    completed = subprocess.run(command, cwd=str(supplied_root.parent), check=False, capture_output=True)
    if out is not None and completed.returncode == 0:
        try:
            return json.loads(out.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            fail("BOOTSTRAP_VERDICT_READ_FAILED", str(exc))
    try:
        verdict = json.loads(completed.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        fail("BOOTSTRAP_OUTPUT_INVALID", str(exc))
    if completed.returncode != 0:
        code = verdict.get("code", "BOOTSTRAP_REFUSED") if isinstance(verdict, dict) else "BOOTSTRAP_REFUSED"
        fail(str(code), "external bootstrap refused the cartridge")
    return verdict


def public_projection(root: Path) -> dict[str, Any]:
    supplied_root = validate_cartridge_coordinate(root)
    supplied_root.resolve(strict=True)
    verdict = run_bootstrap(supplied_root)
    if verdict.get("status") != "PASS" or verdict.get("bootstrapAuthenticated") is not True:
        fail("AUTHENTICATED_VERIFICATION_REQUIRED", "cartridge must pass the external bootstrap")
    projection = verdict.get("publicStatus")
    if not isinstance(projection, dict):
        fail("AUTHENTICATED_PUBLIC_STATUS_REQUIRED", "authenticated verdict omitted the reconstructed public status")
    return projection


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build and verify the immutable STC MARY Flight 01 mission cartridge")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate-profile")
    validate_parser.add_argument("profile", type=Path)

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("profile", type=Path)
    build_parser.add_argument("--out", type=Path, required=True)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("cartridge", type=Path)
    verify_parser.add_argument("--out", type=Path)

    projection_parser = subparsers.add_parser("public-projection")
    projection_parser.add_argument("cartridge", type=Path)
    projection_parser.add_argument("--out", type=Path)
    return parser.parse_args(argv)


def emit(value: dict[str, Any], out: Path | None = None) -> None:
    data = canonical_json_bytes(value)
    if out is None:
        sys.stdout.buffer.write(data)
    else:
        if out.exists():
            fail("OUTPUT_EXISTS", "output file must not already exist")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.command == "validate-profile":
            profile = load_profile(args.profile)
            emit(
                {
                    "schema": "stc-mary/flight-01-cartridge-profile-verdict/1",
                    "status": "PASS",
                    "profileId": PROFILE_ID,
                    "profileCanonicalSha256": PROFILE_CANONICAL_SHA256,
                    "phaseCount": len(profile["phaseSequence"]),
                    "gateCount": len(profile["flightPlanGates"]),
                    "stageCount": len(profile["packetStageSequence"]),
                    "authority": AUTHORITY,
                }
            )
        elif args.command == "build":
            emit(build_cartridge(args.profile, args.out))
        elif args.command == "verify":
            verdict = run_bootstrap(args.cartridge, args.out)
            if args.out is None:
                emit(verdict)
        elif args.command == "public-projection":
            supplied_root = validate_cartridge_coordinate(args.cartridge)
            root = supplied_root.resolve(strict=True)
            validate_projection_output(root, args.out)
            emit(public_projection(supplied_root), args.out)
        else:
            fail("COMMAND_INVALID", args.command)
        return 0
    except (BuildError, OSError, ValueError) as exc:
        code = exc.code if isinstance(exc, BuildError) else "BUILD_FILESYSTEM_ERROR"
        refusal = {
            "schema": "stc-mary/flight-01-cartridge-tool-verdict/1",
            "status": "REFUSED",
            "code": code,
            "message": str(exc),
            "authority": AUTHORITY,
        }
        sys.stdout.buffer.write(canonical_json_bytes(refusal))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
