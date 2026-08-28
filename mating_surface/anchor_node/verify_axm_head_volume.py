from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

PROFILE_SCHEMA = "axm-head-edge-demo-profile/1"
PROFILE_ID = "axm-head/edge-demo/0.1"
CATALOG_SCHEMA = "axm-head-edge-demo-fixture-catalog/1"
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
VERDICT_SCHEMA = "axm-head/mission-volume-verdict@1"
TERMINALS = ("QUALIFIED_ASSEMBLY", "QUALIFICATION_PLAN", "HOLD")
PERMITTED_AUTHORITY = ("read-only", "compute-only")
CASE_IDS = (
    "qualified-gpu-with-resident-fallback",
    "qualification-plan-missing-adapter",
    "hold-undeclared-mutation-interface",
    "qualification-plan-no-memory-pooling",
)
OBJECT_SCHEMAS = (
    EQUIPMENT_SCHEMA,
    WORK_UNIT_BINDING_SCHEMA,
    DECISION_SCHEMA,
    ROUTE_DENOMINATOR_SCHEMA,
    CARTRIDGE_SCHEMA,
    SAVE_SCHEMA,
    LEDGER_SCHEMA,
    COLD_SUCCESSOR_SCHEMA,
    PUBLIC_STATUS_SCHEMA,
    VOLUME_SCHEMA,
)
PROFILE_CANONICAL_SHA256 = "c6529dbe52c678f8ae7ede650b706b1de22f10f6444dd99a5720e41b03cf7078"
FIXTURE_CATALOG_CANONICAL_SHA256 = "82e4bf7e8d18fae61a1e17d1cf758d46004d08dd4b877f933be5c96663b67291"
PUBLIC_CLAIM_BOUNDARY = (
    "Provider-free synthetic contract joining one MARY-style work unit, observed foreign equipment, "
    "independently evaluated compute routes, immutable cartridge identity, mutable save custody, "
    "non-authoritative cache, and cold-successor recovery on a removable mission volume. This profile "
    "executes no physical task and establishes no physical Estate, representative operator, field network, "
    "operational C2, production Lattice, targeting, engagement, effector, or weapons qualification or authority."
)
CARTRIDGE_CLAIM_BOUNDARY = "Immutable mission law, invariants, and human-authority boundary only; no execution authority."
VERDICT_CLAIM_BOUNDARY = (
    "This verdict proves synthetic mission-volume integrity, exact admitted profile and fixture provenance, "
    "complete task and route custody, independently reconstructed successor answers, and internal binding only. "
    "It proves no physical equipment, field operation, representative operator, operational C2, production "
    "Lattice, targeting, engagement, effector, or weapons capability."
)
DEPENDENCIES_ABSENT = ("WAN", "AWS", "Lattice", "remote_model_provider", "original_host", "repository_history")
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
    "RECOVERY/profile.json": "governing-profile",
    "RECOVERY/fixture-catalog.json": "fixture-catalog",
    "RECOVERY/verify_volume.py": "standalone-verifier",
    "PUBLIC/status.json": "public-projection",
}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SHA256_REF = re.compile(r"^sha256:[0-9a-f]{64}$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._:/@-]{2,127}$")


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


def pretty_json_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        fail("NON_CANONICAL_JSON", str(exc))
    return (text + "\n").encode("utf-8")


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



def cartridge_law_body(mission: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": CARTRIDGE_SCHEMA,
        "profileId": PROFILE_ID,
        "missionId": mission["missionId"],
        "cartridgeId": mission["cartridgeId"],
        "invariantRefs": mission["invariantRefs"],
        "humanAuthority": mission["humanAuthority"],
        "systemAuthority": "none",
        "claimBoundary": CARTRIDGE_CLAIM_BOUNDARY,
    }


def cartridge_law_sha256(mission: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(cartridge_law_body(mission)))

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



def output_path_overlaps_volume(volume: Path, out: Path) -> bool:
    root = volume.expanduser().resolve(strict=False)
    candidate = out.expanduser().resolve(strict=False)
    if candidate == root or root in candidate.parents:
        return True
    if out.exists() and root.is_dir():
        for member in root.rglob("*"):
            if not member.is_file():
                continue
            try:
                if out.samefile(member):
                    return True
            except OSError:
                continue
    return False


def require_output_outside_volume(volume: Path, out: Path) -> None:
    if output_path_overlaps_volume(volume, out):
        fail("OUTPUT_INSIDE_VOLUME", "verdict output must remain outside the verified volume")

def validate_profile(profile: dict[str, Any]) -> None:
    exact(
        profile,
        {
            "schema",
            "profileId",
            "status",
            "sourceCoordinates",
            "supplierBindings",
            "objectSchemas",
            "terminalStates",
            "permittedAuthorityClasses",
            "volumeLayout",
            "fixtureCaseIds",
            "claimBoundary",
        },
        "profile",
    )
    if profile["schema"] != PROFILE_SCHEMA or profile["profileId"] != PROFILE_ID:
        fail("PROFILE_IDENTITY_INVALID", "embedded profile schema or profileId differs")
    if profile["status"] != "candidate_contract_only":
        fail("PROFILE_STATUS_INVALID", "embedded profile status differs")
    if profile["sourceCoordinates"] != SOURCE_COORDINATES:
        fail("PROFILE_SOURCE_COORDINATES_INVALID", "embedded profile source coordinates differ")
    if profile["supplierBindings"] != SUPPLIER_BINDINGS:
        fail("PROFILE_SUPPLIER_BINDINGS_INVALID", "embedded profile supplier bindings differ")
    if profile["objectSchemas"] != list(OBJECT_SCHEMAS):
        fail("PROFILE_OBJECT_DENOMINATOR_INVALID", "embedded profile object denominator differs")
    if profile["terminalStates"] != list(TERMINALS):
        fail("PROFILE_TERMINAL_DENOMINATOR_INVALID", "embedded profile terminal denominator differs")
    if profile["permittedAuthorityClasses"] != list(PERMITTED_AUTHORITY):
        fail("PROFILE_AUTHORITY_DENOMINATOR_INVALID", "embedded profile authority denominator differs")
    if profile["volumeLayout"] != LAYOUT:
        fail("PROFILE_LAYOUT_INVALID", "embedded profile layout differs")
    if profile["fixtureCaseIds"] != list(CASE_IDS):
        fail("PROFILE_CASE_DENOMINATOR_INVALID", "embedded profile case denominator differs")
    if profile["claimBoundary"] != PUBLIC_CLAIM_BOUNDARY:
        fail("PROFILE_CLAIM_BOUNDARY_INVALID", "embedded profile claim boundary differs")
    if sha256_bytes(canonical_json_bytes(profile)) != PROFILE_CANONICAL_SHA256:
        fail("PROFILE_CANONICAL_DIGEST_INVALID", "embedded profile canonical digest differs from the admitted profile")


def validate_catalog(catalog: dict[str, Any]) -> None:
    exact(catalog, {"schema", "profileId", "cases"}, "fixtureCatalog")
    if catalog["schema"] != CATALOG_SCHEMA or catalog["profileId"] != PROFILE_ID:
        fail("CATALOG_IDENTITY_INVALID", "embedded fixture catalog identity differs")
    cases = catalog["cases"]
    if not isinstance(cases, list):
        fail("CATALOG_CASES_INVALID", "embedded fixture catalog cases must be a list")
    case_ids = [case.get("caseId") if isinstance(case, dict) else None for case in cases]
    if case_ids != list(CASE_IDS):
        fail("CATALOG_CASE_DENOMINATOR_INVALID", "embedded fixture catalog case denominator differs")
    if sha256_bytes(canonical_json_bytes(catalog)) != FIXTURE_CATALOG_CANONICAL_SHA256:
        fail("CATALOG_CANONICAL_DIGEST_INVALID", "embedded fixture catalog canonical digest differs from the admitted catalog")


def validate_mission(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail("MISSION_INVALID", f"{label} must be an object")
    exact(value, {"missionId", "cartridgeId", "cartridgeSha256", "invariantRefs", "save", "humanAuthority"}, label)
    string(value["missionId"], f"{label}.missionId", ID_RE)
    string(value["cartridgeId"], f"{label}.cartridgeId", ID_RE)
    string(value["cartridgeSha256"], f"{label}.cartridgeSha256", HEX64)
    string_list(value["invariantRefs"], f"{label}.invariantRefs", True)
    save = value["save"]
    if not isinstance(save, dict):
        fail("MISSION_SAVE_INVALID", f"{label}.save must be an object")
    exact(save, {"frontier", "stateSha256", "unresolvedObligations", "nextSafeAction"}, f"{label}.save")
    integer(save["frontier"], f"{label}.save.frontier")
    string(save["stateSha256"], f"{label}.save.stateSha256", HEX64)
    string_list(save["unresolvedObligations"], f"{label}.save.unresolvedObligations")
    string(save["nextSafeAction"], f"{label}.save.nextSafeAction")
    authority = value["humanAuthority"]
    if not isinstance(authority, dict):
        fail("HUMAN_AUTHORITY_INVALID", f"{label}.humanAuthority must be an object")
    exact(authority, {"actorId", "required", "actionClass"}, f"{label}.humanAuthority")
    string(authority["actorId"], f"{label}.humanAuthority.actorId", ID_RE)
    boolean(authority["required"], f"{label}.humanAuthority.required")
    string(authority["actionClass"], f"{label}.humanAuthority.actionClass", ID_RE)
    if value["cartridgeSha256"] != cartridge_law_sha256(value):
        fail("CARTRIDGE_LAW_DIGEST_INVALID", f"{label}.cartridgeSha256 does not bind the canonical cartridge law")
    return value



def validate_cartridge(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail("CARTRIDGE_INVALID", f"{label} must be an object")
    exact(
        value,
        {
            "schema",
            "profileId",
            "missionId",
            "cartridgeId",
            "cartridgeSha256",
            "invariantRefs",
            "humanAuthority",
            "systemAuthority",
            "claimBoundary",
        },
        label,
    )
    if value["schema"] != CARTRIDGE_SCHEMA or value["profileId"] != PROFILE_ID:
        fail("CARTRIDGE_IDENTITY_INVALID", f"{label} schema or profileId differs")
    string(value["missionId"], f"{label}.missionId", ID_RE)
    string(value["cartridgeId"], f"{label}.cartridgeId", ID_RE)
    string(value["cartridgeSha256"], f"{label}.cartridgeSha256", HEX64)
    string_list(value["invariantRefs"], f"{label}.invariantRefs", True)
    authority = value["humanAuthority"]
    if not isinstance(authority, dict):
        fail("HUMAN_AUTHORITY_INVALID", f"{label}.humanAuthority must be an object")
    exact(authority, {"actorId", "required", "actionClass"}, f"{label}.humanAuthority")
    string(authority["actorId"], f"{label}.humanAuthority.actorId", ID_RE)
    boolean(authority["required"], f"{label}.humanAuthority.required")
    string(authority["actionClass"], f"{label}.humanAuthority.actionClass", ID_RE)
    if value["systemAuthority"] != "none":
        fail("CARTRIDGE_AUTHORITY_INVALID", f"{label} may not claim system authority")
    if value["claimBoundary"] != CARTRIDGE_CLAIM_BOUNDARY:
        fail("CARTRIDGE_CLAIM_BOUNDARY_INVALID", f"{label} claim boundary differs")
    if value["cartridgeSha256"] != cartridge_law_sha256(value):
        fail("CARTRIDGE_LAW_DIGEST_INVALID", f"{label}.cartridgeSha256 does not bind the canonical cartridge law")
    return value

def validate_task(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail("TASK_INVALID", f"{label} must be an object")
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


def validate_equipment(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail("EQUIPMENT_INVALID", f"{label} must be an object")
    exact(
        value,
        {
            "equipmentId",
            "supplierSchema",
            "estatePhaseRef",
            "estatePhaseSha256",
            "interface",
            "observedAtUnixNs",
            "freshUntilUnixNs",
            "observationTimeUnixNs",
            "evidenceRef",
        },
        label,
    )
    string(value["equipmentId"], f"{label}.equipmentId", ID_RE)
    if value["supplierSchema"] != SUPPLIER_BINDINGS["maryEstatePhaseSchema"]:
        fail("ESTATE_PHASE_SCHEMA_INVALID", f"{label}.supplierSchema differs")
    string(value["estatePhaseRef"], f"{label}.estatePhaseRef", ID_RE)
    string(value["estatePhaseSha256"], f"{label}.estatePhaseSha256", HEX64)
    interface = value["interface"]
    if not isinstance(interface, dict):
        fail("INTERFACE_INVALID", f"{label}.interface must be an object")
    exact(interface, {"declared", "readOnly", "adapterRef", "adapterAvailable"}, f"{label}.interface")
    boolean(interface["declared"], f"{label}.interface.declared")
    boolean(interface["readOnly"], f"{label}.interface.readOnly")
    string(interface["adapterRef"], f"{label}.interface.adapterRef", ID_RE)
    boolean(interface["adapterAvailable"], f"{label}.interface.adapterAvailable")
    observed = integer(value["observedAtUnixNs"], f"{label}.observedAtUnixNs", 1)
    fresh = integer(value["freshUntilUnixNs"], f"{label}.freshUntilUnixNs", 1)
    now = integer(value["observationTimeUnixNs"], f"{label}.observationTimeUnixNs", 1)
    if fresh < observed or now < observed:
        fail("EQUIPMENT_TIME_INVALID", f"{label} observation time interval is invalid")
    string(value["evidenceRef"], f"{label}.evidenceRef", SHA256_REF)
    return value


def validate_route(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail("ROUTE_INVALID", f"{label} must be an object")
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


def validate_case(case: Any, label: str) -> dict[str, Any]:
    if not isinstance(case, dict):
        fail("CASE_INVALID", f"{label} must be an object")
    exact(case, {"caseId", "expectedTerminal", "mission", "task", "equipment", "routes"}, label)
    string(case["caseId"], f"{label}.caseId", ID_RE)
    if case["expectedTerminal"] not in TERMINALS:
        fail("EXPECTED_TERMINAL_INVALID", f"{label}.expectedTerminal differs")
    mission = validate_mission(case["mission"], f"{label}.mission")
    task = validate_task(case["task"], f"{label}.task")
    validate_equipment(case["equipment"], f"{label}.equipment")
    routes = case["routes"]
    if not isinstance(routes, list) or not routes:
        fail("ROUTE_DENOMINATOR_INVALID", f"{label}.routes must be non-empty")
    ids: list[str] = []
    for index, route in enumerate(routes):
        validate_route(route, f"{label}.routes[{index}]")
        ids.append(route["routeId"])
    if len(ids) != len(set(ids)):
        fail("DUPLICATE_ROUTE_ID", f"{label}.routes contains duplicates")
    if mission["humanAuthority"]["actionClass"] != task["authorityClass"]:
        fail("AUTHORITY_BINDING_INVALID", f"{label} mission and task authority differ")
    return case


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


def make_work_unit_binding(task: dict[str, Any]) -> dict[str, Any]:
    body = {
        "schema": WORK_UNIT_BINDING_SCHEMA,
        "profileId": PROFILE_ID,
        "workUnitRef": task["workUnitRef"],
        "workUnitSha256": task["workUnitSha256"],
        "supplierSchema": task["supplierSchema"],
        "task": task,
    }
    return {**body, "workUnitBindingId": content_id("axmheadworkunit1", body)}


def make_equipment_observation(equipment: dict[str, Any]) -> dict[str, Any]:
    body = {"schema": EQUIPMENT_SCHEMA, "profileId": PROFILE_ID, **equipment}
    return {**body, "observationId": content_id("axmheadobservation1", body)}


def make_route_denominator(case: dict[str, Any]) -> dict[str, Any]:
    routes = sorted(case["routes"], key=lambda row: row["routeId"])
    body = {
        "schema": ROUTE_DENOMINATOR_SCHEMA,
        "profileId": PROFILE_ID,
        "caseId": case["caseId"],
        "supplierSchema": SUPPLIER_BINDINGS["maryRouteDescriptorSchema"],
        "fabricSchemas": {
            "seatSnapshot": SUPPLIER_BINDINGS["estateSeatSnapshotSchema"],
            "routeSelection": SUPPLIER_BINDINGS["estateRouteSelectionSchema"],
            "workerLease": SUPPLIER_BINDINGS["estateWorkerLeaseSchema"],
        },
        "routeCount": len(routes),
        "routes": routes,
    }
    return {**body, "routeDenominatorId": content_id("axmheadroutes1", body)}


def decide_case(case: dict[str, Any]) -> dict[str, Any]:
    validate_case(case, "case")
    task = case["task"]
    equipment = case["equipment"]
    interface = equipment["interface"]
    work_unit = make_work_unit_binding(task)
    observation = make_equipment_observation(equipment)
    denominator = make_route_denominator(case)
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
    by_id = {route["routeId"]: route for route in denominator["routes"]}
    resident_floor_available = any(row["eligible"] and by_id[row["routeId"]]["residentFloor"] for row in evaluations)
    body: dict[str, Any] = {
        "schema": DECISION_SCHEMA,
        "profileId": PROFILE_ID,
        "caseId": case["caseId"],
        "workUnitRef": task["workUnitRef"],
        "workUnitSha256": task["workUnitSha256"],
        "workUnitBindingId": work_unit["workUnitBindingId"],
        "equipmentId": equipment["equipmentId"],
        "estatePhaseRef": equipment["estatePhaseRef"],
        "estatePhaseSha256": equipment["estatePhaseSha256"],
        "equipmentObservationId": observation["observationId"],
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


def make_cartridge(case: dict[str, Any]) -> dict[str, Any]:
    mission = case["mission"]
    return {
        **cartridge_law_body(mission),
        "cartridgeSha256": mission["cartridgeSha256"],
    }


def make_save(case: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    mission = case["mission"]
    task = case["task"]
    return {
        "schema": SAVE_SCHEMA,
        "profileId": PROFILE_ID,
        "missionId": mission["missionId"],
        "cartridgeId": mission["cartridgeId"],
        "workUnitRef": task["workUnitRef"],
        "workUnitSha256": task["workUnitSha256"],
        "frontier": mission["save"]["frontier"],
        "stateSha256": mission["save"]["stateSha256"],
        "unresolvedObligations": mission["save"]["unresolvedObligations"],
        "nextSafeAction": mission["save"]["nextSafeAction"],
        "lastDecisionId": decision["decisionId"],
        "terminal": decision["terminal"],
    }


def make_ledger(case: dict[str, Any], denominator: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    body = {
        "schema": LEDGER_SCHEMA,
        "sequence": 1,
        "caseId": case["caseId"],
        "missionId": case["mission"]["missionId"],
        "cartridgeId": case["mission"]["cartridgeId"],
        "workUnitRef": case["task"]["workUnitRef"],
        "equipmentId": case["equipment"]["equipmentId"],
        "routeDenominatorId": denominator["routeDenominatorId"],
        "decisionId": decision["decisionId"],
        "terminal": decision["terminal"],
        "executionOccurred": False,
        "systemAuthority": "none",
    }
    return {**body, "eventId": content_id("axmheadledger1", body)}


def make_recovery(case: dict[str, Any], equipment: dict[str, Any], denominator: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    mission = case["mission"]
    authority = mission["humanAuthority"]
    answers = {
        "whatMission": mission["missionId"],
        "currentState": f"frontier {mission['save']['frontier']} terminal {decision['terminal']}",
        "whoMayAct": authority["actorId"] if authority["required"] else "no named human required",
        "whatProvesIt": [equipment["evidenceRef"], *[route["evidenceRef"] for route in denominator["routes"]]],
        "whatRemainsUnresolved": mission["save"]["unresolvedObligations"],
        "nextSafeAction": mission["save"]["nextSafeAction"],
    }
    return {
        "schema": COLD_SUCCESSOR_SCHEMA,
        "profileId": PROFILE_ID,
        "bindings": {
            "missionId": mission["missionId"],
            "cartridgeId": mission["cartridgeId"],
            "workUnitRef": case["task"]["workUnitRef"],
            "workUnitSha256": case["task"]["workUnitSha256"],
            "equipmentId": case["equipment"]["equipmentId"],
            "estatePhaseRef": case["equipment"]["estatePhaseRef"],
            "routeDenominatorId": denominator["routeDenominatorId"],
            "stateSha256": mission["save"]["stateSha256"],
            "decisionId": decision["decisionId"],
        },
        "answers": answers,
        "dependenciesAbsent": list(DEPENDENCIES_ABSENT),
        "systemAuthority": "none",
    }


def make_public(case: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": PUBLIC_STATUS_SCHEMA,
        "profileId": PROFILE_ID,
        "caseId": case["caseId"],
        "terminal": decision["terminal"],
        "qualifiedAssembly": decision["terminal"] == "QUALIFIED_ASSEMBLY",
        "qualificationPlan": decision["terminal"] == "QUALIFICATION_PLAN",
        "hold": decision["terminal"] == "HOLD",
        "executionOccurred": False,
        "privateEvidenceBodies": 0,
        "physicalFlightCompleted": False,
        "physicalEstateQualified": False,
        "representativeOperatorQualified": False,
        "fieldNetworkQualified": False,
        "operationalC2Qualified": False,
        "productionLatticeQualified": False,
        "systemAuthority": "none",
        "claimBoundary": PUBLIC_CLAIM_BOUNDARY,
    }


def object_diff(actual: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    return sorted(key for key in set(actual) | set(expected) if actual.get(key) != expected.get(key))


def require_equal(actual: dict[str, Any], expected: dict[str, Any], code: str, label: str) -> None:
    if actual != expected:
        fail(code, f"{label} differs from independently reconstructed object: {object_diff(actual, expected)}")


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
            "standaloneVerifierSha256",
            "bootstrapRequired",
            "fixtureCaseIds",
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
    if manifest["caseId"] not in CASE_IDS or manifest["terminal"] not in TERMINALS:
        fail("MANIFEST_CASE_OR_TERMINAL_INVALID", "manifest case or terminal differs")
    if manifest["sourceCoordinates"] != SOURCE_COORDINATES or manifest["supplierBindings"] != SUPPLIER_BINDINGS:
        fail("MANIFEST_SOURCE_BINDING_INVALID", "manifest source or supplier bindings differ")
    if manifest["profileCanonicalSha256"] != PROFILE_CANONICAL_SHA256:
        fail("MANIFEST_PROFILE_DIGEST_INVALID", "manifest profile digest differs")
    if manifest["fixtureCatalogCanonicalSha256"] != FIXTURE_CATALOG_CANONICAL_SHA256:
        fail("MANIFEST_CATALOG_DIGEST_INVALID", "manifest fixture catalog digest differs")
    string(manifest["standaloneVerifierSha256"], "manifest.standaloneVerifierSha256", HEX64)
    if boolean(manifest["bootstrapRequired"], "manifest.bootstrapRequired") is not True:
        fail("BOOTSTRAP_POLICY_INVALID", "manifest must require external bootstrap authentication")
    if manifest["fixtureCaseIds"] != list(CASE_IDS):
        fail("MANIFEST_CASE_DENOMINATOR_INVALID", "manifest fixture case denominator differs")
    if manifest["layout"] != LAYOUT:
        fail("MANIFEST_LAYOUT_INVALID", "manifest layout differs")
    if manifest["cachePolicy"] != {"authoritative": False, "includedInVolumeId": False, "allowedPrefix": "CACHE/"}:
        fail("CACHE_POLICY_INVALID", "manifest cache policy differs")
    if manifest["systemAuthority"] != "none" or boolean(manifest["executionOccurred"], "manifest.executionOccurred"):
        fail("MANIFEST_AUTHORITY_INVALID", "manifest may not claim execution or authority")
    if manifest["claimBoundary"] != PUBLIC_CLAIM_BOUNDARY:
        fail("MANIFEST_CLAIM_BOUNDARY_INVALID", "manifest claim boundary differs")
    rows = manifest["files"]
    if not isinstance(rows, list):
        fail("MANIFEST_FILES_INVALID", "manifest.files must be a list")
    seen: list[str] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            fail("MANIFEST_FILE_INVALID", f"manifest.files[{index}] must be an object")
        exact(row, {"path", "role", "bytes", "sha256"}, f"manifest.files[{index}]")
        relative = clean_relative_path(string(row["path"], f"manifest.files[{index}].path"))
        string(row["role"], f"manifest.files[{index}].role", ID_RE)
        integer(row["bytes"], f"manifest.files[{index}].bytes")
        string(row["sha256"], f"manifest.files[{index}].sha256", HEX64)
        if relative.startswith("CACHE/"):
            fail("CACHE_MANIFESTED", "cache files may not enter the authoritative manifest")
        seen.append(relative)
    if seen != sorted(seen) or len(seen) != len(set(seen)):
        fail("MANIFEST_FILE_DENOMINATOR_INVALID", "manifest paths must be unique and sorted")
    if {row["path"]: row["role"] for row in rows} != REQUIRED_FILES:
        fail("MANIFEST_FILE_DENOMINATOR_INVALID", "manifest file denominator or roles differ")
    body = dict(manifest)
    declared = string(body.pop("volumeId"), "manifest.volumeId")
    if declared != content_id("axmheadvolume1", body):
        fail("VOLUME_ID_INVALID", "manifest volumeId invalid")
    return manifest, rows


def verify_files(root: Path, rows: list[dict[str, Any]]) -> None:
    for path in root.rglob("*"):
        if path.is_symlink():
            fail("SYMLINK_REFUSED", f"symlink is not permitted: {path.relative_to(root).as_posix()}")
    by_path = {row["path"]: row for row in rows}
    for relative, row in by_path.items():
        path = root.joinpath(*relative.split("/"))
        if not path.is_file():
            fail("MANIFESTED_FILE_MISSING", relative)
        data = path.read_bytes()
        if len(data) != row["bytes"] or sha256_bytes(data) != row["sha256"]:
            fail("FILE_DIGEST_MISMATCH", relative)
    allowed = set(by_path) | {"MANIFEST.json"}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative in allowed or relative.startswith("CACHE/"):
            continue
        fail("UNMANIFESTED_FILE", relative)


def verify_objects(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    profile = read_json(root / "RECOVERY/profile.json")
    catalog = read_json(root / "RECOVERY/fixture-catalog.json")
    validate_profile(profile)
    validate_catalog(catalog)
    if manifest["profileCanonicalSha256"] != sha256_bytes(canonical_json_bytes(profile)):
        fail("PROFILE_MANIFEST_BINDING_INVALID", "manifest profile digest differs from embedded profile")
    if manifest["fixtureCatalogCanonicalSha256"] != sha256_bytes(canonical_json_bytes(catalog)):
        fail("CATALOG_MANIFEST_BINDING_INVALID", "manifest catalog digest differs from embedded catalog")
    verifier_sha = sha256_file(root / "RECOVERY/verify_volume.py")
    if manifest["standaloneVerifierSha256"] != verifier_sha:
        fail("VERIFIER_MANIFEST_BINDING_INVALID", "manifest verifier digest differs from embedded verifier")

    case = next((row for row in catalog["cases"] if row["caseId"] == manifest["caseId"]), None)
    if case is None:
        fail("CASE_NOT_FOUND", "manifest case is absent from the admitted fixture catalog")
    validate_case(case, "selectedCase")
    work_unit = make_work_unit_binding(case["task"])
    equipment = make_equipment_observation(case["equipment"])
    denominator = make_route_denominator(case)
    decision = decide_case(case)
    if decision["terminal"] != case["expectedTerminal"]:
        fail("EXPECTED_TERMINAL_MISMATCH", "selected case terminal differs from the admitted catalog")
    cartridge = make_cartridge(case)
    save = make_save(case, decision)
    ledger = make_ledger(case, denominator, decision)
    recovery = make_recovery(case, equipment, denominator, decision)
    public = make_public(case, decision)

    actual_cartridge = read_json(root / "CARTRIDGE/mission.json")
    validate_cartridge(actual_cartridge, "cartridge")
    actual_work_unit = read_json(root / "CARTRIDGE/work-unit.json")
    actual_save = read_json(root / "SAVE/state.json")
    actual_equipment = read_json(root / "ROUTES/equipment-observation.json")
    actual_denominator = read_json(root / "ROUTES/candidate-routes.json")
    actual_decision = read_json(root / "ROUTES/intake-decision.json")
    actual_recovery = read_json(root / "RECOVERY/cold-successor.json")
    actual_public = read_json(root / "PUBLIC/status.json")
    try:
        lines = (root / "SAVE/ledger.jsonl").read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        fail("LEDGER_READ_FAILED", str(exc))
    if len(lines) != 1:
        fail("LEDGER_DENOMINATOR_INVALID", "fixture ledger must contain exactly one event")
    try:
        actual_ledger = json.loads(lines[0])
    except json.JSONDecodeError as exc:
        fail("LEDGER_JSON_INVALID", str(exc))
    if not isinstance(actual_ledger, dict):
        fail("LEDGER_EVENT_INVALID", "ledger event must be an object")

    require_equal(actual_cartridge, cartridge, "CARTRIDGE_RECONSTRUCTION_MISMATCH", "cartridge")
    require_equal(actual_work_unit, work_unit, "WORK_UNIT_RECONSTRUCTION_MISMATCH", "work unit")
    require_equal(actual_save, save, "SAVE_RECONSTRUCTION_MISMATCH", "save")
    require_equal(actual_equipment, equipment, "EQUIPMENT_RECONSTRUCTION_MISMATCH", "equipment observation")
    require_equal(actual_denominator, denominator, "ROUTE_DENOMINATOR_RECONSTRUCTION_MISMATCH", "route denominator")
    require_equal(actual_decision, decision, "DECISION_RECOMPUTATION_MISMATCH", "intake decision")
    require_equal(actual_ledger, ledger, "LEDGER_RECONSTRUCTION_MISMATCH", "ledger event")
    require_equal(actual_recovery, recovery, "RECOVERY_RECONSTRUCTION_MISMATCH", "cold-successor answers")
    require_equal(actual_public, public, "PUBLIC_RECONSTRUCTION_MISMATCH", "public projection")

    expected_cartridge_binding = {
        "missionId": cartridge["missionId"],
        "cartridgeId": cartridge["cartridgeId"],
        "declaredCartridgeSha256": cartridge["cartridgeSha256"],
    }
    expected_work_unit_binding = {
        "workUnitRef": work_unit["workUnitRef"],
        "workUnitSha256": work_unit["workUnitSha256"],
        "supplierSchema": work_unit["supplierSchema"],
        "workUnitBindingId": work_unit["workUnitBindingId"],
    }
    expected_save_binding = {
        "cartridgeId": save["cartridgeId"],
        "workUnitRef": save["workUnitRef"],
        "frontier": save["frontier"],
        "stateSha256": save["stateSha256"],
    }
    expected_equipment_binding = {
        "equipmentId": equipment["equipmentId"],
        "estatePhaseRef": equipment["estatePhaseRef"],
        "estatePhaseSha256": equipment["estatePhaseSha256"],
        "observationId": equipment["observationId"],
    }
    expected_route_binding = {
        "routeDenominatorId": denominator["routeDenominatorId"],
        "routeCount": denominator["routeCount"],
        "routeIds": [route["routeId"] for route in denominator["routes"]],
        "supplierSchema": denominator["supplierSchema"],
    }
    expected_bindings = {
        "cartridgeBinding": expected_cartridge_binding,
        "workUnitBinding": expected_work_unit_binding,
        "saveBinding": expected_save_binding,
        "equipmentBinding": expected_equipment_binding,
        "routeDenominator": expected_route_binding,
    }
    for key, expected in expected_bindings.items():
        if manifest[key] != expected:
            fail("MANIFEST_OBJECT_BINDING_INVALID", f"manifest.{key} differs from reconstructed object")
    if manifest["terminal"] != decision["terminal"]:
        fail("TERMINAL_BINDING_INVALID", "manifest terminal differs from reconstructed decision")

    encoded_public = json.dumps(actual_public, sort_keys=True)
    for pattern in (r"[A-Za-z]:\\", r"/home/", r"/Users/", r"OCTO-(?:W|L)[0-9]+", r"Authorization:\s*Bearer"):
        if re.search(pattern, encoded_public, re.I):
            fail("PUBLIC_PRIVATE_MATERIAL", f"public projection matched {pattern}")

    return {
        "terminal": manifest["terminal"],
        "caseId": manifest["caseId"],
        "volumeId": manifest["volumeId"],
        "workUnitRef": work_unit["workUnitRef"],
        "routeCount": denominator["routeCount"],
        "decisionId": decision["decisionId"],
        "profileCanonicalSha256": PROFILE_CANONICAL_SHA256,
        "fixtureCatalogCanonicalSha256": FIXTURE_CATALOG_CANONICAL_SHA256,
        "standaloneVerifierSha256": verifier_sha,
        "successorAnswersReconstructed": True,
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
        "schema": VERDICT_SCHEMA,
        "status": "PASS",
        **result,
        "manifestSha256": sha256_file(root / "MANIFEST.json"),
        "fileCount": len(rows),
        "bootstrapAuthenticated": False,
        "claimBoundary": VERDICT_CLAIM_BOUNDARY,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Standalone verifier for AXM HEAD removable mission volumes")
    parser.add_argument("volume", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    safe_out = args.out
    try:
        if safe_out is not None:
            require_output_outside_volume(args.volume, safe_out)
        verdict = verify_volume(args.volume)
        data = pretty_json_bytes(verdict)
        if safe_out is not None:
            safe_out.parent.mkdir(parents=True, exist_ok=True)
            safe_out.write_bytes(data)
        sys.stdout.buffer.write(data)
        return 0
    except VerifyError as exc:
        if exc.code == "OUTPUT_INSIDE_VOLUME":
            safe_out = None
        verdict = {"schema": VERDICT_SCHEMA, "status": "REFUSED", "code": exc.code, "message": str(exc)}
        data = pretty_json_bytes(verdict)
        if safe_out is not None:
            safe_out.parent.mkdir(parents=True, exist_ok=True)
            safe_out.write_bytes(data)
        sys.stdout.buffer.write(data)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
