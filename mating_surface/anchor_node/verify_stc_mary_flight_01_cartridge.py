from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any

PROFILE_SCHEMA = "stc-mary/flight-01-cartridge-profile/1"
PROFILE_ID = "stc-mary/flight-01-cartridge@1"
PROFILE_CANONICAL_SHA256 = "c3f4f7a2ca45a9cfd08cc4d19cd48b5c0c4fbf013f6783e092cb8a3701902b50"
MANIFEST_SCHEMA = "stc-mary/flight-01-cartridge-manifest/1"
SOURCE_BINDING_SCHEMA = "stc-mary/flight-01-source-binding/1"
MISSION_SCHEMA = "stc-mary/flight-01-mission/1"
WORK_UNIT_SCHEMA = "stc-mary/flight-01-work-unit/1"
PUBLIC_STATUS_SCHEMA = "stc-mary/flight-01-public-status/1"
TERMINAL = "PREPARED_NOT_ARMED"
AUTHORITY = "none"
EXPECTED_FILES = (
    "CARTRIDGE/mission.json",
    "CARTRIDGE/work-unit.json",
    "PUBLIC/status.json",
    "RECOVERY/profile.json",
    "RECOVERY/source-binding.json",
    "RECOVERY/verify_cartridge.py",
)
EXPECTED_DIRECTORIES = {"CARTRIDGE", "PUBLIC", "RECOVERY"}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
ALLOWED_PUBLIC_COUNT_KEYS = {"privateEvidenceBodies", "publicEvidenceBodies"}
PRIVATE_KEY_FRAGMENTS = (
    "privatepath",
    "hostname",
    "hostidentity",
    "endpoint",
    "credential",
    "password",
    "secret",
    "token",
    "serial",
    "stdout",
    "stderr",
    "telemetrybody",
    "evidencebody",
    "operatorrecord",
    "environmentvalue",
)


class CartridgeError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def fail(code: str, message: str) -> None:
    raise CartridgeError(code, message)


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


def content_id(prefix: str, body: dict[str, Any]) -> str:
    return f"{prefix}_{sha256_bytes(canonical_json_bytes(body))}"


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail("DUPLICATE_JSON_KEY", f"duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_json_bytes(data: bytes, label: str) -> dict[str, Any]:
    if b"\r" in data:
        fail("NON_LF_AUTHORITATIVE_BYTES", f"{label} contains CR bytes")
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_pairs_no_duplicates)
    except (UnicodeError, json.JSONDecodeError) as exc:
        fail("JSON_READ_FAILED", f"{label}: {exc}")
    if not isinstance(value, dict):
        fail("JSON_OBJECT_REQUIRED", f"{label} must contain one JSON object")
    return value


def require_exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        fail("OBJECT_KEYS_INVALID", f"{label} missing={sorted(expected - actual)} unknown={sorted(actual - expected)}")


def require_bool(value: Any, label: str) -> bool:
    if type(value) is not bool:
        fail("BOOLEAN_REQUIRED", f"{label} must be boolean")
    return value


def require_int(value: Any, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        fail("INTEGER_REQUIRED", f"{label} must be integer >= {minimum}")
    return value


def require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        fail("STRING_REQUIRED", f"{label} must be non-empty string")
    return value


def require_string_list(value: Any, label: str, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        fail("STRING_LIST_REQUIRED", f"{label} must be a string list")
    items = [require_string(item, f"{label}[{index}]") for index, item in enumerate(value)]
    if len(items) != len(set(items)):
        fail("DUPLICATE_LIST_VALUE", f"{label} contains duplicates")
    return items


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def validate_output_path(root: Path, out: Path | None) -> None:
    if out is None:
        return
    resolved = out.resolve(strict=False)
    if is_within(resolved, root):
        fail("VERDICT_INSIDE_CARTRIDGE", "verdict output may not be inside the measured cartridge")
    if out.exists():
        fail("VERDICT_OUTPUT_EXISTS", "verdict output must not already exist")
    if out.parent.exists() and out.parent.is_symlink():
        fail("VERDICT_PARENT_SYMLINK", "verdict parent may not be a symlink")


def validate_tree(root: Path) -> None:
    if not root.is_dir() or root.is_symlink():
        fail("CARTRIDGE_ROOT_INVALID", "cartridge root must be a regular directory")
    files: set[str] = set()
    directories: set[str] = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        pure = PurePosixPath(relative)
        if pure.is_absolute() or ".." in pure.parts or "\\" in relative:
            fail("UNSAFE_MEMBER_PATH", relative)
        if path.is_symlink():
            fail("SYMLINK_MEMBER_REFUSED", relative)
        if path.is_dir():
            directories.add(relative)
        elif path.is_file():
            files.add(relative)
        else:
            fail("NON_REGULAR_MEMBER_REFUSED", relative)
    expected_files = {"MANIFEST.json", *EXPECTED_FILES}
    if files != expected_files:
        fail("FILE_DENOMINATOR_INVALID", f"missing={sorted(expected_files - files)} unknown={sorted(files - expected_files)}")
    if directories != EXPECTED_DIRECTORIES:
        fail("DIRECTORY_DENOMINATOR_INVALID", f"missing={sorted(EXPECTED_DIRECTORIES - directories)} unknown={sorted(directories - EXPECTED_DIRECTORIES)}")


def read_member(root: Path, relative: str) -> bytes:
    path = root / PurePosixPath(relative)
    if not path.is_file() or path.is_symlink():
        fail("MEMBER_INVALID", relative)
    data = path.read_bytes()
    if b"\r" in data:
        fail("NON_LF_AUTHORITATIVE_BYTES", relative)
    return data


def validate_profile(profile: dict[str, Any]) -> dict[str, Any]:
    require_exact_keys(
        profile,
        {
            "schema",
            "profileId",
            "status",
            "sourceCoordinates",
            "issueBindings",
            "artifactLabels",
            "terminalStates",
            "phaseSequence",
            "flightPlanGates",
            "packetStageSequence",
            "feed",
            "missionLaw",
            "workUnitLaw",
            "claimBoundary",
        },
        "profile",
    )
    if profile["schema"] != PROFILE_SCHEMA or profile["profileId"] != PROFILE_ID:
        fail("PROFILE_IDENTITY_INVALID", "profile identity differs")
    if profile["status"] != "candidate_contract_only":
        fail("PROFILE_STATUS_INVALID", "profile status differs")
    if sha256_bytes(canonical_json_bytes(profile)) != PROFILE_CANONICAL_SHA256:
        fail("PROFILE_CANONICAL_DIGEST_INVALID", "profile canonical digest differs")
    if profile["terminalStates"] != ["PREPARED_NOT_ARMED", "REFUSED"]:
        fail("TERMINAL_DENOMINATOR_INVALID", "terminal denominator differs")
    if profile["artifactLabels"] != ["cartridge", "model", "verifier", "storage"]:
        fail("ARTIFACT_LABEL_DENOMINATOR_INVALID", "artifact label denominator differs")
    if profile["issueBindings"] != {"privateFlight": 37, "postflightJoin": 49}:
        fail("ISSUE_BINDING_INVALID", "issue bindings differ")
    source_coordinates = profile["sourceCoordinates"]
    require_exact_keys(
        source_coordinates,
        {
            "maryPortable",
            "axmHeadSupplier",
            "physicalFlightPreflight",
            "physicalFlightExecutionFloor",
        },
        "profile.sourceCoordinates",
    )
    if "flightConductor" in source_coordinates:
        fail("CONDUCTOR_SEMANTIC_COUPLING_REFUSED", "operator provenance may not enter cartridge semantic identity")
    if len(profile["phaseSequence"]) != 12 or len(profile["flightPlanGates"]) != 8 or len(profile["packetStageSequence"]) != 16:
        fail("MISSION_DENOMINATOR_INVALID", "phase, gate, or stage denominator differs")
    feed = profile["feed"]
    if feed != {"records": 262144, "features": 32, "classes": 8, "seed": 20260827}:
        fail("FEED_LAW_INVALID", "feed law differs")
    mission_law = profile["missionLaw"]
    require_exact_keys(
        mission_law,
        {
            "missionName",
            "campaignLabel",
            "namedHumanBind",
            "humanAuthorizationRequired",
            "systemAuthority",
            "invariantRefs",
            "nextSafeAction",
        },
        "profile.missionLaw",
    )
    if mission_law["missionName"] != "STC Mission Cartridge 01":
        fail("MISSION_NAME_INVALID", "missionName differs")
    if mission_law["campaignLabel"] != "PRIVATE-STC-MARY-FLIGHT-01":
        fail("CAMPAIGN_LABEL_INVALID", "campaignLabel differs")
    if mission_law["namedHumanBind"] != "GRACE" or require_bool(mission_law["humanAuthorizationRequired"], "missionLaw.humanAuthorizationRequired") is not True:
        fail("HUMAN_BIND_INVALID", "named-human law differs")
    if mission_law["systemAuthority"] != AUTHORITY:
        fail("AUTHORITY_INVALID", "mission systemAuthority must remain none")
    require_string_list(mission_law["invariantRefs"], "missionLaw.invariantRefs", nonempty=True)
    work_law = profile["workUnitLaw"]
    require_exact_keys(
        work_law,
        {
            "kind",
            "privacyLane",
            "authorityClass",
            "requiredCapabilities",
            "residentFloorBackend",
            "optionalAcceleratorBackend",
            "resultRequirements",
        },
        "profile.workUnitLaw",
    )
    if work_law["kind"] != "deterministic-integer-linear-aperture":
        fail("WORK_KIND_INVALID", "work-unit kind differs")
    if work_law["privacyLane"] != "private-local" or work_law["authorityClass"] != "compute-only":
        fail("WORK_AUTHORITY_INVALID", "work-unit privacy or authority differs")
    if work_law["residentFloorBackend"] != "python" or work_law["optionalAcceleratorBackend"] != "torch-cuda":
        fail("BACKEND_LAW_INVALID", "backend law differs")
    require_string_list(work_law["requiredCapabilities"], "workUnitLaw.requiredCapabilities", nonempty=True)
    require_string_list(work_law["resultRequirements"], "workUnitLaw.resultRequirements", nonempty=True)
    require_string(profile["claimBoundary"], "profile.claimBoundary")
    return profile


def build_source_binding(profile: dict[str, Any]) -> dict[str, Any]:
    body = {
        "schema": SOURCE_BINDING_SCHEMA,
        "profileId": PROFILE_ID,
        "sourceCoordinates": profile["sourceCoordinates"],
        "issueBindings": profile["issueBindings"],
        "artifactLabels": profile["artifactLabels"],
        "profileCanonicalSha256": PROFILE_CANONICAL_SHA256,
        "authority": AUTHORITY,
    }
    return {**body, "sourceBindingId": content_id("stcmarysourcebinding1", body)}


def build_work_unit(profile: dict[str, Any]) -> dict[str, Any]:
    law = profile["workUnitLaw"]
    body = {
        "schema": WORK_UNIT_SCHEMA,
        "profileId": PROFILE_ID,
        "kind": law["kind"],
        "feed": profile["feed"],
        "privacyLane": law["privacyLane"],
        "authorityClass": law["authorityClass"],
        "requiredCapabilities": law["requiredCapabilities"],
        "residentFloorBackend": law["residentFloorBackend"],
        "optionalAcceleratorBackend": law["optionalAcceleratorBackend"],
        "resultRequirements": law["resultRequirements"],
        "networkRequired": False,
        "externalServiceCalls": 0,
        "operationalCredentials": 0,
        "systemAuthority": AUTHORITY,
        "claimBoundary": "Immutable bounded compute law only; no execution receipt, result acceptance, physical qualification, or authority.",
    }
    return {**body, "workUnitId": content_id("stcmaryworkunit1", body)}


def build_mission(profile: dict[str, Any], source_binding: dict[str, Any], work_unit: dict[str, Any]) -> dict[str, Any]:
    law = profile["missionLaw"]
    cartridge_body = {
        "profileCanonicalSha256": PROFILE_CANONICAL_SHA256,
        "sourceBindingId": source_binding["sourceBindingId"],
        "workUnitId": work_unit["workUnitId"],
        "missionLaw": law,
        "phaseSequence": profile["phaseSequence"],
        "flightPlanGates": profile["flightPlanGates"],
        "packetStageSequence": profile["packetStageSequence"],
    }
    cartridge_id = content_id("stcmarycartridge1", cartridge_body)
    body = {
        "schema": MISSION_SCHEMA,
        "profileId": PROFILE_ID,
        "cartridgeId": cartridge_id,
        "missionName": law["missionName"],
        "campaignLabel": law["campaignLabel"],
        "namedHumanBind": law["namedHumanBind"],
        "humanAuthorizationRequired": law["humanAuthorizationRequired"],
        "systemAuthority": law["systemAuthority"],
        "invariantRefs": law["invariantRefs"],
        "phaseSequence": profile["phaseSequence"],
        "flightPlanGates": profile["flightPlanGates"],
        "packetStageSequence": profile["packetStageSequence"],
        "sourceBindingId": source_binding["sourceBindingId"],
        "workUnitId": work_unit["workUnitId"],
        "nextSafeAction": law["nextSafeAction"],
        "claimBoundary": profile["claimBoundary"],
    }
    return {**body, "missionId": content_id("stcmarymission1", body)}


def build_public_status(profile: dict[str, Any], mission: dict[str, Any], work_unit: dict[str, Any], source_binding: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": PUBLIC_STATUS_SCHEMA,
        "profileId": PROFILE_ID,
        "cartridgeId": mission["cartridgeId"],
        "missionId": mission["missionId"],
        "workUnitId": work_unit["workUnitId"],
        "sourceBindingId": source_binding["sourceBindingId"],
        "terminal": TERMINAL,
        "artifactCoordinateBound": False,
        "privatePreflightCompiled": False,
        "humanReviewComplete": False,
        "authorizationProduced": False,
        "workstationInitialized": False,
        "physicalExecutionStarted": False,
        "packetStagesRecorded": 0,
        "privateEvidenceBodies": 0,
        "publicEvidenceBodies": 0,
        "physicalEstateQualified": False,
        "representativeOperatorQualified": False,
        "fieldNetworkQualified": False,
        "operationalC2Qualified": False,
        "productionLatticeQualified": False,
        "missionAuthority": AUTHORITY,
        "commandAuthority": AUTHORITY,
        "authority": AUTHORITY,
        "nextSafeAction": profile["missionLaw"]["nextSafeAction"],
        "claimBoundary": profile["claimBoundary"],
    }


def scan_public_status(status: dict[str, Any]) -> None:
    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                compact = re.sub(r"[^a-z0-9]", "", key.lower())
                if key not in ALLOWED_PUBLIC_COUNT_KEYS and any(fragment in compact for fragment in PRIVATE_KEY_FRAGMENTS):
                    fail("PRIVATE_PUBLIC_FIELD_REFUSED", f"{path}.{key}")
                walk(item, f"{path}.{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{path}[{index}]")
    walk(status, "status")


def expected_objects(profile: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    source = build_source_binding(profile)
    work = build_work_unit(profile)
    mission = build_mission(profile, source, work)
    status = build_public_status(profile, mission, work, source)
    return source, work, mission, status


def verify_cartridge(root: Path) -> dict[str, Any]:
    supplied_root = root.expanduser()
    if supplied_root.is_symlink():
        fail("CARTRIDGE_ROOT_INVALID", "cartridge root must be a regular non-symlink directory")
    root = supplied_root.resolve(strict=True)
    validate_tree(root)

    member_bytes = {relative: read_member(root, relative) for relative in EXPECTED_FILES}
    profile = validate_profile(parse_json_bytes(member_bytes["RECOVERY/profile.json"], "RECOVERY/profile.json"))
    source, work, mission, status = expected_objects(profile)

    stored_source = parse_json_bytes(member_bytes["RECOVERY/source-binding.json"], "RECOVERY/source-binding.json")
    if canonical_json_bytes(stored_source) != canonical_json_bytes(source):
        fail("SOURCE_BINDING_RECONSTRUCTION_FAILED", "stored source binding differs from reconstruction")
    stored_work = parse_json_bytes(member_bytes["CARTRIDGE/work-unit.json"], "CARTRIDGE/work-unit.json")
    if canonical_json_bytes(stored_work) != canonical_json_bytes(work):
        fail("WORK_UNIT_RECONSTRUCTION_FAILED", "stored work unit differs from reconstruction")
    stored_mission = parse_json_bytes(member_bytes["CARTRIDGE/mission.json"], "CARTRIDGE/mission.json")
    if canonical_json_bytes(stored_mission) != canonical_json_bytes(mission):
        fail("MISSION_RECONSTRUCTION_FAILED", "stored mission differs from reconstruction")
    stored_status = parse_json_bytes(member_bytes["PUBLIC/status.json"], "PUBLIC/status.json")
    if canonical_json_bytes(stored_status) != canonical_json_bytes(status):
        fail("PUBLIC_STATUS_RECONSTRUCTION_FAILED", "stored public status differs from reconstruction")
    scan_public_status(stored_status)

    manifest_data = read_member(root, "MANIFEST.json")
    manifest = parse_json_bytes(manifest_data, "MANIFEST.json")
    require_exact_keys(
        manifest,
        {
            "schema",
            "profileId",
            "bundleId",
            "cartridgeId",
            "terminal",
            "memberCount",
            "members",
            "authority",
            "claimBoundary",
        },
        "manifest",
    )
    if manifest["schema"] != MANIFEST_SCHEMA or manifest["profileId"] != PROFILE_ID:
        fail("MANIFEST_IDENTITY_INVALID", "manifest identity differs")
    if manifest["cartridgeId"] != mission["cartridgeId"] or manifest["terminal"] != TERMINAL:
        fail("MANIFEST_BINDING_INVALID", "manifest cartridge or terminal differs")
    if manifest["authority"] != AUTHORITY or manifest["claimBoundary"] != profile["claimBoundary"]:
        fail("MANIFEST_CLAIM_BOUNDARY_INVALID", "manifest authority or claim boundary differs")
    require_int(manifest["memberCount"], "manifest.memberCount")
    if manifest["memberCount"] != len(EXPECTED_FILES):
        fail("MANIFEST_MEMBER_COUNT_INVALID", "manifest memberCount differs")
    if not isinstance(manifest["members"], list) or len(manifest["members"]) != len(EXPECTED_FILES):
        fail("MANIFEST_MEMBERS_INVALID", "manifest members denominator differs")

    expected_rows = []
    for relative in sorted(EXPECTED_FILES):
        data = member_bytes[relative]
        expected_rows.append({"path": relative, "bytes": len(data), "sha256": sha256_bytes(data)})
    if manifest["members"] != expected_rows:
        fail("MANIFEST_MEMBER_IDENTITY_INVALID", "manifest member identities differ")

    manifest_body = {
        "schema": MANIFEST_SCHEMA,
        "profileId": PROFILE_ID,
        "cartridgeId": mission["cartridgeId"],
        "terminal": TERMINAL,
        "memberCount": len(EXPECTED_FILES),
        "members": expected_rows,
        "authority": AUTHORITY,
        "claimBoundary": profile["claimBoundary"],
    }
    expected_bundle_id = content_id("stcmarycartridgebundle1", manifest_body)
    if manifest["bundleId"] != expected_bundle_id:
        fail("BUNDLE_ID_INVALID", "bundleId differs from reconstructed manifest body")

    checks = [
        "closed-file-denominator",
        "closed-directory-denominator",
        "lf-only-authoritative-bytes",
        "profile-canonical-digest",
        "exact-source-binding",
        "exact-work-unit-reconstruction",
        "exact-mission-reconstruction",
        "exact-public-status-reconstruction",
        "manifest-member-byte-identities",
        "bundle-identity-reconstruction",
        "private-public-field-refusal",
        "authority-none",
    ]
    return {
        "schema": "stc-mary/flight-01-cartridge-verdict/1",
        "status": "PASS",
        "terminal": TERMINAL,
        "bundleId": expected_bundle_id,
        "cartridgeId": mission["cartridgeId"],
        "missionId": mission["missionId"],
        "workUnitId": work["workUnitId"],
        "sourceBindingId": source["sourceBindingId"],
        "publicStatus": status,
        "checks": checks,
        "bootstrapAuthenticated": False,
        "physicalExecutionStarted": False,
        "workstationInitialized": False,
        "packetStagesRecorded": 0,
        "privateEvidenceBodies": 0,
        "publicEvidenceBodies": 0,
        "authority": AUTHORITY,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify one STC MARY Flight 01 cartridge bundle")
    parser.add_argument("cartridge", type=Path)
    parser.add_argument("--out", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        supplied_root = args.cartridge.expanduser()
        if supplied_root.is_symlink():
            fail("CARTRIDGE_ROOT_INVALID", "cartridge root must be a regular non-symlink directory")
        root = supplied_root.resolve(strict=True)
        validate_output_path(root, args.out)
        verdict = verify_cartridge(supplied_root)
        data = canonical_json_bytes(verdict)
        if args.out is None:
            sys.stdout.buffer.write(data)
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_bytes(data)
        return 0
    except CartridgeError as exc:
        refusal = {
            "schema": "stc-mary/flight-01-cartridge-verdict/1",
            "status": "REFUSED",
            "code": exc.code,
            "message": str(exc),
            "authority": AUTHORITY,
        }
        sys.stdout.buffer.write(canonical_json_bytes(refusal))
        return 1
    except (OSError, ValueError) as exc:
        refusal = {
            "schema": "stc-mary/flight-01-cartridge-verdict/1",
            "status": "REFUSED",
            "code": "FILESYSTEM_ERROR",
            "message": str(exc),
            "authority": AUTHORITY,
        }
        sys.stdout.buffer.write(canonical_json_bytes(refusal))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
