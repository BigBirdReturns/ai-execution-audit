from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

PROFILE_ID = "axm-head/edge-demo/0.1"
EQUIPMENT_SCHEMA = "axm-head/equipment-observation@1"
WORK_UNIT_BINDING_SCHEMA = "axm-head/work-unit-binding@1"
DECISION_SCHEMA = "axm-head/equipment-intake-decision@1"
ROUTE_DENOMINATOR_SCHEMA = "axm-head/route-denominator@1"
CARTRIDGE_SCHEMA = "axm-head/cartridge@1"
SAVE_SCHEMA = "axm-head/save@1"
LEDGER_SCHEMA = "axm-head/ledger-event@1"
COLD_SUCCESSOR_SCHEMA = "axm-head/cold-successor@1"
PUBLIC_STATUS_SCHEMA = "axm-head/public-status@1"
VOLUME_SCHEMA = "axm-head/mission-volume@1"
TERMINALS = ("QUALIFIED_ASSEMBLY", "QUALIFICATION_PLAN", "HOLD")
PERMITTED_AUTHORITY = ("read-only", "compute-only")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SHA256_REF = re.compile(r"^sha256:[0-9a-f]{64}$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._:/@-]{2,127}$")
SOURCE_COORDINATES = {
    "auditRuntime": {
        "repository": "BigBirdReturns/ai-execution-audit",
        "commit": "772ce582e1b19b7a2060c50be8ebf40c1f8723b2",
        "tree": "3f708c52782784e687cf1f0b68fd7d37a507ef4c",
        "status": "admitted",
    },
    "physicalFlightFloor": {
        "repository": "BigBirdReturns/ai-execution-audit",
        "commit": "d31e59f5fd30e57b1917c00832b189ee2ea3e12f",
        "tree": "2a6a155e9615eb847781f87566bac32d4c9dc126",
        "status": "admitted_not_executed",
    },
    "maryMetabolism": {
        "repository": "BigBirdReturns/mary-portable",
        "commit": "9151e0b8de973faede371c816db2602c47b854bd",
        "tree": "4a43991b0178919ebfaedae120d7cd96b20091de",
        "status": "qualified_draft_not_admitted",
    },
}
SUPPLIER_BINDINGS = {
    "maryWorkUnitSchema": "invitation-home/work-unit@v0alpha1",
    "maryRouteDescriptorSchema": "invitation-home/route-descriptor@v0alpha1",
    "maryEstatePhaseSchema": "invitation-home/estate-phase@v0alpha1",
    "estateSeatSnapshotSchema": "estate-seat-snapshot/1",
    "estateRouteSelectionSchema": "estate-route-selection/1",
    "estateWorkerLeaseSchema": "estate-worker-lease/1",
}
LAYOUT = {
    "cartridge": "CARTRIDGE",
    "save": "SAVE",
    "routes": "ROUTES",
    "cache": "CACHE",
    "recovery": "RECOVERY",
    "public": "PUBLIC",
}
REQUIRED_FILES = {
    "CARTRIDGE/mission.json": "cartridge",
    "CARTRIDGE/work-unit.json": "work-unit-binding",
    "SAVE/state.json": "save",
    "SAVE/ledger.jsonl": "ledger",
    "ROUTES/equipment-observation.json": "equipment-observation",
    "ROUTES/candidate-routes.json": "route-denominator",
    "ROUTES/intake-decision.json": "intake-decision",
    "RECOVERY/cold-successor.json": "cold-successor",
    "PUBLIC/status.json": "public-projection",
    "RECOVERY/verify_volume.py": "standalone-verifier",
}


class VerifyError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def fail(code: str, message: str) -> None:
    raise VerifyError(code, message)


def canonical_json_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        fail("NON_CANONICAL_JSON", str(exc))
    return (text + "\n").encode("utf-8")


def pretty_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(chunk)
    except OSError as exc:
        fail("FILE_READ_FAILED", f"{path}: {exc}")
    return h.hexdigest()


def content_id(prefix: str, body: dict[str, Any]) -> str:
    return f"{prefix}_{sha256_bytes(canonical_json_bytes(body))}"


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail("JSON_READ_FAILED", f"{path}: {exc}")
    if not isinstance(value, dict):
        fail("JSON_OBJECT_REQUIRED", f"{path} must contain one JSON object")
    return value


def exact(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        fail("OBJECT_KEYS_INVALID", f"{label} missing={sorted(expected - actual)} unknown={sorted(actual - expected)}")


def string(value: Any, label: str, pattern: re.Pattern[str] | None = None) -> str:
    if not isinstance(value, str) or not value:
        fail("STRING_REQUIRED", f"{label} must be a non-empty string")
    if pattern is not None and pattern.fullmatch(value) is None:
        fail("STRING_PATTERN_INVALID", f"{label} has an invalid value")
    return value


def boolean(value: Any, label: str) -> bool:
    if type(value) is not bool:
        fail("BOOLEAN_REQUIRED", f"{label} must be boolean")
    return value


def integer(value: Any, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        fail("INTEGER_REQUIRED", f"{label} must be integer >= {minimum}")
    return value


def string_list(value: Any, label: str, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        fail("STRING_LIST_REQUIRED", f"{label} must be a string list")
    result = [string(item, f"{label}[{index}]") for index, item in enumerate(value)]
    if len(set(result)) != len(result):
        fail("DUPLICATE_LIST_VALUE", f"{label} contains duplicates")
    return result


def clean_relative_path(value: str) -> str:
    if not value or value.startswith(("/", "\\")) or "\\" in value:
        fail("RELATIVE_PATH_INVALID", f"invalid path {value!r}")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        fail("RELATIVE_PATH_INVALID", f"invalid path {value!r}")
    return value


def validate_human_authority(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail("HUMAN_AUTHORITY_INVALID", f"{label} must be object")
    exact(value, {"actorId", "required", "actionClass"}, label)
    string(value["actorId"], f"{label}.actorId", ID_RE)
    boolean(value["required"], f"{label}.required")
    string(value["actionClass"], f"{label}.actionClass", ID_RE)
    return value


def validate_task(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail("TASK_INVALID", f"{label} must be object")
    exact(
        value,
        {
            "workUnitRef",
            "workUnitSha256",
            "supplierSchema",
            "requiredCapabilities",
            "privacyLane",
            "authorityClass",
            "requiredValidatorRef",
            "wallTimeMs",
            "minimumMemoryBytes",
        },
        label,
    )
    string(value["workUnitRef"], f"{label}.workUnitRef", ID_RE)
    string(value["workUnitSha256"], f"{label}.workUnitSha256", HEX64)
    if value["supplierSchema"] != SUPPLIER_BINDINGS["maryWorkUnitSchema"]:
        fail("WORK_UNIT_SCHEMA_INVALID", f"{label}.supplierSchema differs")
    string_list(value["requiredCapabilities"], f"{label}.requiredCapabilities", True)
    string(value["privacyLane"], f"{label}.privacyLane", ID_RE)
    string(value["authorityClass"], f"{label}.authorityClass", ID_RE)
    string(value["requiredValidatorRef"], f"{label}.requiredValidatorRef", ID_RE)
    integer(value["wallTimeMs"], f"{label}.wallTimeMs", 1)
    integer(value["minimumMemoryBytes"], f"{label}.minimumMemoryBytes")
    return value


def validate_equipment_fields(value: dict[str, Any], label: str) -> None:
    string(value["equipmentId"], f"{label}.equipmentId", ID_RE)
    if value["supplierSchema"] != SUPPLIER_BINDINGS["maryEstatePhaseSchema"]:
        fail("ESTATE_PHASE_SCHEMA_INVALID", f"{label}.supplierSchema differs")
    string(value["estatePhaseRef"], f"{label}.estatePhaseRef", ID_RE)
    string(value["estatePhaseSha256"], f"{label}.estatePhaseSha256", HEX64)
    interface = value["interface"]
    if not isinstance(interface, dict):
        fail("INTERFACE_INVALID", f"{label}.interface must be object")
    exact(interface, {"declared", "readOnly", "adapterRef", "adapterAvailable"}, f"{label}.interface")
    boolean(interface["declared"], f"{label}.interface.declared")
    boolean(interface["readOnly"], f"{label}.interface.readOnly")
    string(interface["adapterRef"], f"{label}.interface.adapterRef", ID_RE)
    boolean(interface["adapterAvailable"], f"{label}.interface.adapterAvailable")
    observed = integer(value["observedAtUnixNs"], f"{label}.observedAtUnixNs", 1)
    fresh = integer(value["freshUntilUnixNs"], f"{label}.freshUntilUnixNs", 1)
    now = integer(value["observationTimeUnixNs"], f"{label}.observationTimeUnixNs", 1)
    if fresh < observed:
        fail("FRESHNESS_INTERVAL_INVALID", f"{label}.freshUntilUnixNs precedes observedAtUnixNs")
    if now < observed:
        fail("OBSERVATION_CLOCK_INVALID", f"{label}.observationTimeUnixNs precedes observedAtUnixNs")
    string(value["evidenceRef"], f"{label}.evidenceRef", SHA256_REF)


def validate_route(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail("ROUTE_INVALID", f"{label} must be object")
    exact(
        value,
        {
            "routeId",
            "supplierSchema",
            "supplierRouteRef",
            "supplierRouteSha256",
            "fabricSeatRef",
            "hostClass",
            "routeClass",
            "available",
            "residentFloor",
            "optionalOrgan",
            "capabilities",
            "privacyLanes",
            "validatorRefs",
            "memoryBytes",
            "maximumWallTimeMs",
            "preferenceRank",
            "evidenceRef",
        },
        label,
    )
    string(value["routeId"], f"{label}.routeId", ID_RE)
    if value["supplierSchema"] != SUPPLIER_BINDINGS["maryRouteDescriptorSchema"]:
        fail("ROUTE_SCHEMA_INVALID", f"{label}.supplierSchema differs")
    string(value["supplierRouteRef"], f"{label}.supplierRouteRef", ID_RE)
    string(value["supplierRouteSha256"], f"{label}.supplierRouteSha256", HEX64)
    string(value["fabricSeatRef"], f"{label}.fabricSeatRef", ID_RE)
    string(value["hostClass"], f"{label}.hostClass", ID_RE)
    string(value["routeClass"], f"{label}.routeClass", ID_RE)
    boolean(value["available"], f"{label}.available")
    resident = boolean(value["residentFloor"], f"{label}.residentFloor")
    optional = boolean(value["optionalOrgan"], f"{label}.optionalOrgan")
    if resident and optional:
        fail("ROUTE_ROLE_CONFLICT", f"{label} cannot be resident and optional")
    string_list(value["capabilities"], f"{label}.capabilities", True)
    string_list(value["privacyLanes"], f"{label}.privacyLanes", True)
    string_list(value["validatorRefs"], f"{label}.validatorRefs", True)
    integer(value["memoryBytes"], f"{label}.memoryBytes")
    integer(value["maximumWallTimeMs"], f"{label}.maximumWallTimeMs", 1)
    integer(value["preferenceRank"], f"{label}.preferenceRank")
    string(value["evidenceRef"], f"{label}.evidenceRef", SHA256_REF)
    return value


def route_evaluation(route: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    exclusions: list[str] = []
    if not route["available"]:
        exclusions.append("ROUTE_UNAVAILABLE")
    if not set(task["requiredCapabilities"]).issubset(route["capabilities"]):
        exclusions.append("CAPABILITY_MISMATCH")
    if task["privacyLane"] not in route["privacyLanes"]:
        exclusions.append("PRIVACY_LANE_MISMATCH")
    if task["requiredValidatorRef"] not in route["validatorRefs"]:
        exclusions.append("VALIDATOR_UNAVAILABLE")
    if route["memoryBytes"] < task["minimumMemoryBytes"]:
        exclusions.append("INDIVIDUAL_ROUTE_MEMORY_INSUFFICIENT")
    if route["maximumWallTimeMs"] < task["wallTimeMs"]:
        exclusions.append("WALL_TIME_BUDGET_INSUFFICIENT")
    return {"routeId": route["routeId"], "eligible": not exclusions, "exclusions": exclusions}


def recompute_decision(
    *,
    case_id: str,
    work_unit: dict[str, Any],
    equipment: dict[str, Any],
    denominator: dict[str, Any],
) -> dict[str, Any]:
    task = work_unit["task"]
    interface = equipment["interface"]
    reason_codes: list[str] = []
    missing: list[str] = []
    hard_hold = False
    if task["authorityClass"] not in PERMITTED_AUTHORITY:
        hard_hold = True
        reason_codes.append("AUTHORITY_CLASS_WITHHELD")
    if not interface["declared"]:
        hard_hold = True
        reason_codes.append("INTERFACE_UNDECLARED")
    if not interface["readOnly"]:
        hard_hold = True
        reason_codes.append("PROBE_NOT_READ_ONLY")
    if equipment["observationTimeUnixNs"] > equipment["freshUntilUnixNs"]:
        hard_hold = True
        reason_codes.append("EQUIPMENT_OBSERVATION_STALE")

    evaluations = [route_evaluation(route, task) for route in denominator["routes"]]
    eligible_ids = [row["routeId"] for row in evaluations if row["eligible"]]
    selected_route_id: str | None = None
    if hard_hold:
        terminal = "HOLD"
    elif not interface["adapterAvailable"]:
        terminal = "QUALIFICATION_PLAN"
        reason_codes.append("ADAPTER_UNAVAILABLE")
        missing.append(interface["adapterRef"])
    elif not eligible_ids:
        terminal = "QUALIFICATION_PLAN"
        reason_codes.append("NO_QUALIFIED_ROUTE")
        exclusion_codes = sorted({code for row in evaluations for code in row["exclusions"]})
        missing.extend(f"route-property:{code.lower()}" for code in exclusion_codes)
    else:
        terminal = "QUALIFIED_ASSEMBLY"
        reason_codes.append("ASSEMBLY_QUALIFIED")
        eligible_routes = [route for route in denominator["routes"] if route["routeId"] in eligible_ids]
        selected_route_id = min(eligible_routes, key=lambda row: (row["preferenceRank"], row["routeId"]))["routeId"]

    selected_route = next((route for route in denominator["routes"] if route["routeId"] == selected_route_id), None)
    route_by_id = {route["routeId"]: route for route in denominator["routes"]}
    resident_floor_available = any(row["eligible"] and route_by_id[row["routeId"]]["residentFloor"] for row in evaluations)
    body: dict[str, Any] = {
        "schema": DECISION_SCHEMA,
        "profileId": PROFILE_ID,
        "caseId": case_id,
        "workUnitRef": work_unit["workUnitRef"],
        "workUnitSha256": work_unit["workUnitSha256"],
        "workUnitBindingId": work_unit["workUnitBindingId"],
        "equipmentId": equipment["equipmentId"],
        "estatePhaseRef": equipment["estatePhaseRef"],
        "estatePhaseSha256": equipment["estatePhaseSha256"],
        "equipmentObservationId": equipment["observationId"],
        "routeDenominatorId": denominator["routeDenominatorId"],
        "terminal": terminal,
        "reasonCodes": sorted(reason_codes),
        "missingProperties": sorted(set(missing)),
        "routeEvaluations": evaluations,
        "eligibleRouteIds": sorted(eligible_ids),
        "selectedRouteId": selected_route_id,
        "residentFloorAvailable": resident_floor_available,
        "optionalOrganSelected": bool(selected_route and selected_route["optionalOrgan"]),
        "systemAuthority": "none",
        "executionOccurred": False,
    }
    return {**body, "decisionId": content_id("axmheaddecision1", body)}


def verify_manifest(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = read_json(root / "MANIFEST.json")
    exact(
        manifest,
        {
            "schema",
            "profileId",
            "caseId",
            "terminal",
            "sourceCoordinates",
            "supplierBindings",
            "profileCanonicalSha256",
            "fixtureCatalogCanonicalSha256",
            "layout",
            "cartridgeBinding",
            "workUnitBinding",
            "saveBinding",
            "equipmentBinding",
            "routeDenominator",
            "cachePolicy",
            "files",
            "systemAuthority",
            "executionOccurred",
            "claimBoundary",
            "volumeId",
        },
        "manifest",
    )
    if manifest["schema"] != VOLUME_SCHEMA or manifest["profileId"] != PROFILE_ID:
        fail("MANIFEST_IDENTITY_INVALID", "manifest schema or profileId differs")
    string(manifest["caseId"], "manifest.caseId", ID_RE)
    if manifest["terminal"] not in TERMINALS:
        fail("TERMINAL_INVALID", "manifest terminal is outside closed denominator")
    if manifest["sourceCoordinates"] != SOURCE_COORDINATES:
        fail("SOURCE_COORDINATES_INVALID", "manifest source coordinates differ from verifier")
    if manifest["supplierBindings"] != SUPPLIER_BINDINGS:
        fail("SUPPLIER_BINDINGS_INVALID", "manifest supplier bindings differ from verifier")
    string(manifest["profileCanonicalSha256"], "manifest.profileCanonicalSha256", HEX64)
    string(manifest["fixtureCatalogCanonicalSha256"], "manifest.fixtureCatalogCanonicalSha256", HEX64)
    if manifest["layout"] != LAYOUT:
        fail("VOLUME_LAYOUT_INVALID", "manifest layout differs")
    if manifest["systemAuthority"] != "none" or boolean(manifest["executionOccurred"], "manifest.executionOccurred"):
        fail("MANIFEST_AUTHORITY_INVALID", "manifest may not claim execution or authority")
    string(manifest["claimBoundary"], "manifest.claimBoundary")
    if manifest["cachePolicy"] != {"authoritative": False, "includedInVolumeId": False, "allowedPrefix": "CACHE/"}:
        fail("CACHE_POLICY_INVALID", "cache policy differs")

    for key, expected in (
        ("cartridgeBinding", {"missionId", "cartridgeId", "declaredCartridgeSha256"}),
        ("workUnitBinding", {"workUnitRef", "workUnitSha256", "supplierSchema", "workUnitBindingId"}),
        ("saveBinding", {"cartridgeId", "workUnitRef", "frontier", "stateSha256"}),
        ("equipmentBinding", {"equipmentId", "estatePhaseRef", "estatePhaseSha256", "observationId"}),
        ("routeDenominator", {"routeDenominatorId", "routeCount", "routeIds", "supplierSchema"}),
    ):
        value = manifest[key]
        if not isinstance(value, dict):
            fail("MANIFEST_BINDING_INVALID", f"manifest.{key} must be object")
        exact(value, expected, f"manifest.{key}")

    rows = manifest["files"]
    if not isinstance(rows, list):
        fail("MANIFEST_FILES_INVALID", "manifest.files must be list")
    seen: list[str] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            fail("MANIFEST_FILE_INVALID", f"manifest.files[{index}] must be object")
        exact(row, {"path", "role", "bytes", "sha256"}, f"manifest.files[{index}]")
        relative = clean_relative_path(string(row["path"], f"manifest.files[{index}].path"))
        string(row["role"], f"manifest.files[{index}].role", ID_RE)
        integer(row["bytes"], f"manifest.files[{index}].bytes")
        string(row["sha256"], f"manifest.files[{index}].sha256", HEX64)
        if relative.startswith("CACHE/"):
            fail("CACHE_MANIFESTED", "cache files must not enter the authoritative manifest")
        seen.append(relative)
    if seen != sorted(seen) or len(seen) != len(set(seen)):
        fail("MANIFEST_FILE_DENOMINATOR_INVALID", "manifest paths must be unique and sorted")
    roles = {row["path"]: row["role"] for row in rows}
    if roles != REQUIRED_FILES:
        fail("MANIFEST_FILE_DENOMINATOR_INVALID", "manifest file denominator or roles differ")

    body = dict(manifest)
    declared_volume_id = string(body.pop("volumeId"), "manifest.volumeId")
    if declared_volume_id != content_id("axmheadvolume1", body):
        fail("VOLUME_ID_INVALID", "manifest volumeId invalid")
    return manifest, rows


def verify_files(root: Path, rows: list[dict[str, Any]]) -> None:
    for path in root.rglob("*"):
        if path.is_symlink():
            fail("SYMLINK_REFUSED", f"symlink is not permitted: {path.relative_to(root).as_posix()}")
    row_by_path = {row["path"]: row for row in rows}
    for relative, row in row_by_path.items():
        path = root.joinpath(*relative.split("/"))
        if not path.is_file():
            fail("MANIFESTED_FILE_MISSING", relative)
        data = path.read_bytes()
        if len(data) != row["bytes"] or sha256_bytes(data) != row["sha256"]:
            fail("FILE_DIGEST_MISMATCH", relative)
    allowed = set(row_by_path) | {"MANIFEST.json"}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative in allowed or relative.startswith("CACHE/"):
            continue
        fail("UNMANIFESTED_FILE", relative)


def verify_objects(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    cartridge = read_json(root / "CARTRIDGE/mission.json")
    exact(
        cartridge,
        {"schema", "profileId", "missionId", "cartridgeId", "cartridgeSha256", "invariantRefs", "humanAuthority", "systemAuthority", "claimBoundary"},
        "cartridge",
    )
    if cartridge["schema"] != CARTRIDGE_SCHEMA or cartridge["profileId"] != PROFILE_ID:
        fail("CARTRIDGE_IDENTITY_INVALID", "cartridge schema or profileId differs")
    string(cartridge["missionId"], "cartridge.missionId", ID_RE)
    string(cartridge["cartridgeId"], "cartridge.cartridgeId", ID_RE)
    string(cartridge["cartridgeSha256"], "cartridge.cartridgeSha256", HEX64)
    string_list(cartridge["invariantRefs"], "cartridge.invariantRefs", True)
    human_authority = validate_human_authority(cartridge["humanAuthority"], "cartridge.humanAuthority")
    if cartridge["systemAuthority"] != "none":
        fail("CARTRIDGE_AUTHORITY_INVALID", "cartridge systemAuthority must be none")
    string(cartridge["claimBoundary"], "cartridge.claimBoundary")

    work_unit = read_json(root / "CARTRIDGE/work-unit.json")
    exact(
        work_unit,
        {"schema", "profileId", "workUnitRef", "workUnitSha256", "supplierSchema", "task", "workUnitBindingId"},
        "workUnit",
    )
    if work_unit["schema"] != WORK_UNIT_BINDING_SCHEMA or work_unit["profileId"] != PROFILE_ID:
        fail("WORK_UNIT_BINDING_INVALID", "work unit binding identity differs")
    task = validate_task(work_unit["task"], "workUnit.task")
    if work_unit["workUnitRef"] != task["workUnitRef"] or work_unit["workUnitSha256"] != task["workUnitSha256"] or work_unit["supplierSchema"] != task["supplierSchema"]:
        fail("WORK_UNIT_BINDING_INVALID", "work unit wrapper differs from task")
    work_unit_body = dict(work_unit)
    declared_work_unit_id = string(work_unit_body.pop("workUnitBindingId"), "workUnit.workUnitBindingId")
    if declared_work_unit_id != content_id("axmheadworkunit1", work_unit_body):
        fail("WORK_UNIT_BINDING_ID_INVALID", "work unit binding id invalid")
    if human_authority["actionClass"] != task["authorityClass"]:
        fail("AUTHORITY_BINDING_INVALID", "cartridge human authority and work unit authority differ")

    save = read_json(root / "SAVE/state.json")
    exact(
        save,
        {"schema", "profileId", "missionId", "cartridgeId", "workUnitRef", "workUnitSha256", "frontier", "stateSha256", "unresolvedObligations", "nextSafeAction", "lastDecisionId", "terminal"},
        "save",
    )
    if save["schema"] != SAVE_SCHEMA or save["profileId"] != PROFILE_ID:
        fail("SAVE_IDENTITY_INVALID", "save identity differs")
    string(save["missionId"], "save.missionId", ID_RE)
    string(save["cartridgeId"], "save.cartridgeId", ID_RE)
    string(save["workUnitRef"], "save.workUnitRef", ID_RE)
    string(save["workUnitSha256"], "save.workUnitSha256", HEX64)
    integer(save["frontier"], "save.frontier")
    string(save["stateSha256"], "save.stateSha256", HEX64)
    string_list(save["unresolvedObligations"], "save.unresolvedObligations")
    string(save["nextSafeAction"], "save.nextSafeAction")
    string(save["lastDecisionId"], "save.lastDecisionId")
    if save["terminal"] not in TERMINALS:
        fail("SAVE_TERMINAL_INVALID", "save terminal invalid")

    equipment = read_json(root / "ROUTES/equipment-observation.json")
    exact(
        equipment,
        {"schema", "profileId", "equipmentId", "supplierSchema", "estatePhaseRef", "estatePhaseSha256", "interface", "observedAtUnixNs", "freshUntilUnixNs", "observationTimeUnixNs", "evidenceRef", "observationId"},
        "equipment",
    )
    if equipment["schema"] != EQUIPMENT_SCHEMA or equipment["profileId"] != PROFILE_ID:
        fail("EQUIPMENT_IDENTITY_INVALID", "equipment observation identity differs")
    validate_equipment_fields(equipment, "equipment")
    equipment_body = dict(equipment)
    declared_observation_id = string(equipment_body.pop("observationId"), "equipment.observationId")
    if declared_observation_id != content_id("axmheadobservation1", equipment_body):
        fail("EQUIPMENT_OBSERVATION_ID_INVALID", "equipment observation id invalid")

    denominator = read_json(root / "ROUTES/candidate-routes.json")
    exact(
        denominator,
        {"schema", "profileId", "caseId", "supplierSchema", "fabricSchemas", "routeCount", "routes", "routeDenominatorId"},
        "routeDenominator",
    )
    if denominator["schema"] != ROUTE_DENOMINATOR_SCHEMA or denominator["profileId"] != PROFILE_ID:
        fail("ROUTE_DENOMINATOR_IDENTITY_INVALID", "route denominator identity differs")
    string(denominator["caseId"], "routeDenominator.caseId", ID_RE)
    if denominator["supplierSchema"] != SUPPLIER_BINDINGS["maryRouteDescriptorSchema"]:
        fail("ROUTE_SCHEMA_INVALID", "route denominator supplier schema differs")
    expected_fabric = {
        "seatSnapshot": SUPPLIER_BINDINGS["estateSeatSnapshotSchema"],
        "routeSelection": SUPPLIER_BINDINGS["estateRouteSelectionSchema"],
        "workerLease": SUPPLIER_BINDINGS["estateWorkerLeaseSchema"],
    }
    if denominator["fabricSchemas"] != expected_fabric:
        fail("FABRIC_SCHEMA_BINDING_INVALID", "route denominator fabric schemas differ")
    routes = denominator["routes"]
    if not isinstance(routes, list) or not routes:
        fail("ROUTE_DENOMINATOR_INVALID", "route denominator routes must be non-empty")
    route_ids: list[str] = []
    for index, route in enumerate(routes):
        validate_route(route, f"routeDenominator.routes[{index}]")
        route_ids.append(route["routeId"])
    if route_ids != sorted(route_ids) or len(route_ids) != len(set(route_ids)):
        fail("ROUTE_DENOMINATOR_INVALID", "routes must be unique and sorted")
    if integer(denominator["routeCount"], "routeDenominator.routeCount", 1) != len(routes):
        fail("ROUTE_COUNT_INVALID", "routeCount differs")
    denominator_body = dict(denominator)
    declared_denominator_id = string(denominator_body.pop("routeDenominatorId"), "routeDenominator.routeDenominatorId")
    if declared_denominator_id != content_id("axmheadroutes1", denominator_body):
        fail("ROUTE_DENOMINATOR_ID_INVALID", "route denominator id invalid")

    decision = read_json(root / "ROUTES/intake-decision.json")
    exact(
        decision,
        {
            "schema",
            "profileId",
            "caseId",
            "workUnitRef",
            "workUnitSha256",
            "workUnitBindingId",
            "equipmentId",
            "estatePhaseRef",
            "estatePhaseSha256",
            "equipmentObservationId",
            "routeDenominatorId",
            "terminal",
            "reasonCodes",
            "missingProperties",
            "routeEvaluations",
            "eligibleRouteIds",
            "selectedRouteId",
            "residentFloorAvailable",
            "optionalOrganSelected",
            "systemAuthority",
            "executionOccurred",
            "decisionId",
        },
        "decision",
    )
    if decision["schema"] != DECISION_SCHEMA or decision["profileId"] != PROFILE_ID:
        fail("DECISION_IDENTITY_INVALID", "decision identity differs")
    if decision["terminal"] not in TERMINALS:
        fail("DECISION_TERMINAL_INVALID", "decision terminal invalid")
    if decision["systemAuthority"] != "none" or boolean(decision["executionOccurred"], "decision.executionOccurred"):
        fail("DECISION_AUTHORITY_INVALID", "decision may not claim execution or authority")
    decision_body = dict(decision)
    declared_decision_id = string(decision_body.pop("decisionId"), "decision.decisionId")
    if declared_decision_id != content_id("axmheaddecision1", decision_body):
        fail("DECISION_ID_INVALID", "decisionId invalid")
    expected_decision = recompute_decision(
        case_id=denominator["caseId"],
        work_unit=work_unit,
        equipment=equipment,
        denominator=denominator,
    )
    if decision != expected_decision:
        differing = sorted(key for key in set(decision) | set(expected_decision) if decision.get(key) != expected_decision.get(key))
        fail("DECISION_RECOMPUTATION_MISMATCH", f"decision differs from independently recomputed result: {differing}")

    try:
        ledger_lines = (root / "SAVE/ledger.jsonl").read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        fail("LEDGER_READ_FAILED", str(exc))
    if len(ledger_lines) != 1:
        fail("LEDGER_DENOMINATOR_INVALID", "fixture ledger must contain exactly one event")
    try:
        ledger = json.loads(ledger_lines[0])
    except json.JSONDecodeError as exc:
        fail("LEDGER_JSON_INVALID", str(exc))
    if not isinstance(ledger, dict):
        fail("LEDGER_EVENT_INVALID", "ledger event must be object")
    exact(
        ledger,
        {"schema", "sequence", "caseId", "missionId", "cartridgeId", "workUnitRef", "equipmentId", "routeDenominatorId", "decisionId", "terminal", "executionOccurred", "systemAuthority", "eventId"},
        "ledger",
    )
    if ledger["schema"] != LEDGER_SCHEMA or integer(ledger["sequence"], "ledger.sequence", 1) != 1:
        fail("LEDGER_EVENT_INVALID", "ledger identity invalid")
    if boolean(ledger["executionOccurred"], "ledger.executionOccurred") or ledger["systemAuthority"] != "none":
        fail("LEDGER_AUTHORITY_INVALID", "ledger may not claim execution or authority")
    ledger_body = dict(ledger)
    declared_event_id = string(ledger_body.pop("eventId"), "ledger.eventId")
    if declared_event_id != content_id("axmheadledger1", ledger_body):
        fail("LEDGER_EVENT_ID_INVALID", "ledger eventId invalid")

    recovery = read_json(root / "RECOVERY/cold-successor.json")
    exact(recovery, {"schema", "profileId", "bindings", "answers", "dependenciesAbsent", "systemAuthority"}, "recovery")
    if recovery["schema"] != COLD_SUCCESSOR_SCHEMA or recovery["profileId"] != PROFILE_ID or recovery["systemAuthority"] != "none":
        fail("RECOVERY_INVALID", "recovery identity or authority invalid")
    bindings = recovery["bindings"]
    if not isinstance(bindings, dict):
        fail("RECOVERY_BINDING_INVALID", "recovery bindings must be object")
    exact(
        bindings,
        {"missionId", "cartridgeId", "workUnitRef", "workUnitSha256", "equipmentId", "estatePhaseRef", "routeDenominatorId", "stateSha256", "decisionId"},
        "recovery.bindings",
    )
    answers = recovery["answers"]
    if not isinstance(answers, dict):
        fail("RECOVERY_ANSWERS_INVALID", "recovery answers must be object")
    exact(answers, {"whatMission", "currentState", "whoMayAct", "whatProvesIt", "whatRemainsUnresolved", "nextSafeAction"}, "recovery.answers")
    string(answers["whatMission"], "answers.whatMission")
    string(answers["currentState"], "answers.currentState")
    string(answers["whoMayAct"], "answers.whoMayAct")
    string_list(answers["whatProvesIt"], "answers.whatProvesIt")
    string_list(answers["whatRemainsUnresolved"], "answers.whatRemainsUnresolved")
    string(answers["nextSafeAction"], "answers.nextSafeAction")
    expected_absent = ["WAN", "AWS", "Lattice", "remote_model_provider", "original_host", "repository_history"]
    if recovery["dependenciesAbsent"] != expected_absent:
        fail("RECOVERY_DEPENDENCIES_INVALID", "dependenciesAbsent differs")

    public = read_json(root / "PUBLIC/status.json")
    exact(
        public,
        {"schema", "profileId", "caseId", "terminal", "qualifiedAssembly", "qualificationPlan", "hold", "executionOccurred", "privateEvidenceBodies", "physicalFlightCompleted", "physicalEstateQualified", "representativeOperatorQualified", "fieldNetworkQualified", "operationalC2Qualified", "productionLatticeQualified", "systemAuthority", "claimBoundary"},
        "public",
    )
    if public["schema"] != PUBLIC_STATUS_SCHEMA or public["profileId"] != PROFILE_ID:
        fail("PUBLIC_STATUS_INVALID", "public status identity invalid")
    if public["systemAuthority"] != "none" or boolean(public["executionOccurred"], "public.executionOccurred"):
        fail("PUBLIC_AUTHORITY_INVALID", "public status may not claim authority or execution")
    for field in ("physicalFlightCompleted", "physicalEstateQualified", "representativeOperatorQualified", "fieldNetworkQualified", "operationalC2Qualified", "productionLatticeQualified"):
        if boolean(public[field], f"public.{field}"):
            fail("PUBLIC_CLAIM_PROMOTION", f"public.{field} must remain false")
    if integer(public["privateEvidenceBodies"], "public.privateEvidenceBodies") != 0:
        fail("PRIVATE_BODY_COUNT_INVALID", "synthetic volume must expose zero private evidence bodies")
    expected_flags = {
        "qualifiedAssembly": public["terminal"] == "QUALIFIED_ASSEMBLY",
        "qualificationPlan": public["terminal"] == "QUALIFICATION_PLAN",
        "hold": public["terminal"] == "HOLD",
    }
    for field, expected in expected_flags.items():
        if boolean(public[field], f"public.{field}") != expected:
            fail("PUBLIC_TERMINAL_FLAGS_INVALID", field)
    encoded_public = json.dumps(public, sort_keys=True)
    forbidden = [r"[A-Za-z]:\\", r"/home/", r"/Users/", r"OCTO-(?:W|L)[0-9]+", r"Authorization:\s*Bearer"]
    for pattern in forbidden:
        if re.search(pattern, encoded_public, re.I):
            fail("PUBLIC_PRIVATE_MATERIAL", f"public projection matched {pattern}")

    if manifest["caseId"] != denominator["caseId"] or manifest["caseId"] != decision["caseId"] or manifest["caseId"] != public["caseId"] or manifest["caseId"] != ledger["caseId"]:
        fail("CASE_BINDING_INVALID", "case identity differs across volume")
    if manifest["terminal"] != decision["terminal"] or manifest["terminal"] != save["terminal"] or manifest["terminal"] != public["terminal"] or manifest["terminal"] != ledger["terminal"]:
        fail("TERMINAL_BINDING_INVALID", "terminal differs across volume")
    if cartridge["missionId"] != save["missionId"] or cartridge["missionId"] != ledger["missionId"] or cartridge["missionId"] != recovery["bindings"]["missionId"]:
        fail("MISSION_BINDING_INVALID", "mission identity differs")
    if cartridge["cartridgeId"] != save["cartridgeId"] or cartridge["cartridgeId"] != ledger["cartridgeId"] or cartridge["cartridgeId"] != recovery["bindings"]["cartridgeId"]:
        fail("CARTRIDGE_SAVE_BINDING_INVALID", "cartridge identity differs")
    if work_unit["workUnitRef"] != save["workUnitRef"] or work_unit["workUnitRef"] != ledger["workUnitRef"] or work_unit["workUnitRef"] != recovery["bindings"]["workUnitRef"]:
        fail("WORK_UNIT_BINDING_INVALID", "work unit reference differs")
    if work_unit["workUnitSha256"] != save["workUnitSha256"] or work_unit["workUnitSha256"] != recovery["bindings"]["workUnitSha256"]:
        fail("WORK_UNIT_BINDING_INVALID", "work unit digest differs")
    if equipment["equipmentId"] != ledger["equipmentId"] or equipment["equipmentId"] != recovery["bindings"]["equipmentId"]:
        fail("EQUIPMENT_BINDING_INVALID", "equipment identity differs")
    if equipment["estatePhaseRef"] != recovery["bindings"]["estatePhaseRef"]:
        fail("ESTATE_PHASE_BINDING_INVALID", "estate phase reference differs")
    if denominator["routeDenominatorId"] != ledger["routeDenominatorId"] or denominator["routeDenominatorId"] != recovery["bindings"]["routeDenominatorId"]:
        fail("ROUTE_DENOMINATOR_BINDING_INVALID", "route denominator differs")
    if decision["decisionId"] != save["lastDecisionId"] or decision["decisionId"] != ledger["decisionId"] or decision["decisionId"] != recovery["bindings"]["decisionId"]:
        fail("DECISION_BINDING_INVALID", "decision identity differs")
    if save["stateSha256"] != recovery["bindings"]["stateSha256"]:
        fail("STATE_BINDING_INVALID", "state digest differs")

    expected_cartridge_binding = {
        "missionId": cartridge["missionId"],
        "cartridgeId": cartridge["cartridgeId"],
        "declaredCartridgeSha256": cartridge["cartridgeSha256"],
    }
    if manifest["cartridgeBinding"] != expected_cartridge_binding:
        fail("MANIFEST_CARTRIDGE_BINDING_INVALID", "manifest cartridgeBinding differs")
    expected_work_unit_binding = {
        "workUnitRef": work_unit["workUnitRef"],
        "workUnitSha256": work_unit["workUnitSha256"],
        "supplierSchema": work_unit["supplierSchema"],
        "workUnitBindingId": work_unit["workUnitBindingId"],
    }
    if manifest["workUnitBinding"] != expected_work_unit_binding:
        fail("MANIFEST_WORK_UNIT_BINDING_INVALID", "manifest workUnitBinding differs")
    expected_save_binding = {
        "cartridgeId": save["cartridgeId"],
        "workUnitRef": save["workUnitRef"],
        "frontier": save["frontier"],
        "stateSha256": save["stateSha256"],
    }
    if manifest["saveBinding"] != expected_save_binding:
        fail("MANIFEST_SAVE_BINDING_INVALID", "manifest saveBinding differs")
    expected_equipment_binding = {
        "equipmentId": equipment["equipmentId"],
        "estatePhaseRef": equipment["estatePhaseRef"],
        "estatePhaseSha256": equipment["estatePhaseSha256"],
        "observationId": equipment["observationId"],
    }
    if manifest["equipmentBinding"] != expected_equipment_binding:
        fail("MANIFEST_EQUIPMENT_BINDING_INVALID", "manifest equipmentBinding differs")
    expected_route_binding = {
        "routeDenominatorId": denominator["routeDenominatorId"],
        "routeCount": denominator["routeCount"],
        "routeIds": [route["routeId"] for route in denominator["routes"]],
        "supplierSchema": denominator["supplierSchema"],
    }
    if manifest["routeDenominator"] != expected_route_binding:
        fail("MANIFEST_ROUTE_DENOMINATOR_INVALID", "manifest routeDenominator differs")

    return {
        "terminal": manifest["terminal"],
        "caseId": manifest["caseId"],
        "volumeId": manifest["volumeId"],
        "workUnitRef": work_unit["workUnitRef"],
        "routeCount": denominator["routeCount"],
        "decisionId": decision["decisionId"],
        "cacheNonAuthoritative": True,
        "executionOccurred": False,
        "systemAuthority": "none",
    }


def verify_volume(root: Path) -> dict[str, Any]:
    if not root.is_dir():
        fail("VOLUME_ROOT_INVALID", f"volume root is not a directory: {root}")
    manifest, rows = verify_manifest(root)
    verify_files(root, rows)
    result = verify_objects(root, manifest)
    return {
        "schema": "axm-head/mission-volume-verdict@1",
        "status": "PASS",
        **result,
        "manifestSha256": sha256_file(root / "MANIFEST.json"),
        "fileCount": len(rows),
        "claimBoundary": "This verdict proves synthetic mission-volume integrity, complete task and route custody, independent decision reconstruction, and internal binding only. It proves no physical equipment, field operation, representative operator, operational C2, production Lattice, targeting, engagement, effector, or weapons capability.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Standalone verifier for AXM HEAD removable mission volumes")
    parser.add_argument("volume", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        verdict = verify_volume(args.volume)
        text = pretty_json(verdict)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_bytes(text.encode("utf-8"))
        sys.stdout.buffer.write(text.encode("utf-8"))
        return 0
    except VerifyError as exc:
        verdict = {"schema": "axm-head/mission-volume-verdict@1", "status": "REFUSED", "code": exc.code, "message": str(exc)}
        text = pretty_json(verdict)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_bytes(text.encode("utf-8"))
        sys.stdout.buffer.write(text.encode("utf-8"))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
