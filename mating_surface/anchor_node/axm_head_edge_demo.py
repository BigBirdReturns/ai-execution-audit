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
STANDALONE_VERIFIER_SHA256 = "8ca6d225fc162e78fb1af41c9cd89c188491a08fe71a69b58c6c12cd9acf4e44"
PUBLIC_CLAIM_BOUNDARY = (
    "Provider-free synthetic contract joining one MARY-style work unit, observed foreign equipment, "
    "independently evaluated compute routes, immutable cartridge identity, mutable save custody, "
    "non-authoritative cache, and cold-successor recovery on a removable mission volume. This profile "
    "executes no physical task and establishes no physical Estate, representative operator, field network, "
    "operational C2, production Lattice, targeting, engagement, effector, or weapons qualification or authority."
)
CARTRIDGE_CLAIM_BOUNDARY = "Immutable mission law, invariants, and human-authority boundary only; no execution authority."
DEPENDENCIES_ABSENT = ("WAN", "AWS", "Lattice", "remote_model_provider", "original_host", "repository_history")
EXPECTED_SOURCE_COORDINATES = {
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
EXPECTED_SUPPLIER_BINDINGS = {
    "maryWorkUnitSchema": "invitation-home/work-unit@v0alpha1",
    "maryRouteDescriptorSchema": "invitation-home/route-descriptor@v0alpha1",
    "maryEstatePhaseSchema": "invitation-home/estate-phase@v0alpha1",
    "estateSeatSnapshotSchema": "estate-seat-snapshot/1",
    "estateRouteSelectionSchema": "estate-route-selection/1",
    "estateWorkerLeaseSchema": "estate-worker-lease/1",
}
EXPECTED_LAYOUT = {
    "cartridge": "CARTRIDGE",
    "save": "SAVE",
    "routes": "ROUTES",
    "cache": "CACHE",
    "recovery": "RECOVERY",
    "public": "PUBLIC",
}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SHA256_REF = re.compile(r"^sha256:[0-9a-f]{64}$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._:/@-]{2,127}$")


class DemoError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def fail(code: str, message: str) -> None:
    raise DemoError(code, message)


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


def require_exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        fail("OBJECT_KEYS_INVALID", f"{label} missing={sorted(expected - actual)} unknown={sorted(actual - expected)}")


def require_string(value: Any, label: str, *, pattern: re.Pattern[str] | None = None) -> str:
    if not isinstance(value, str) or not value:
        fail("STRING_REQUIRED", f"{label} must be a non-empty string")
    if pattern is not None and pattern.fullmatch(value) is None:
        fail("STRING_PATTERN_INVALID", f"{label} has an invalid value")
    return value


def require_bool(value: Any, label: str) -> bool:
    if type(value) is not bool:
        fail("BOOLEAN_REQUIRED", f"{label} must be boolean")
    return value


def require_int(value: Any, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        fail("INTEGER_REQUIRED", f"{label} must be an integer >= {minimum}")
    return value


def require_string_list(value: Any, label: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        fail("STRING_LIST_REQUIRED", f"{label} must be a string list")
    result = [require_string(item, f"{label}[{index}]") for index, item in enumerate(value)]
    if len(set(result)) != len(result):
        fail("DUPLICATE_LIST_VALUE", f"{label} contains duplicates")
    return result


def validate_profile(path: Path) -> dict[str, Any]:
    profile = read_json(path)
    require_exact_keys(
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
        fail("PROFILE_IDENTITY_INVALID", "profile schema or profileId differs")
    if profile["status"] != "candidate_contract_only":
        fail("PROFILE_STATUS_INVALID", "profile status must remain candidate_contract_only")
    if profile["sourceCoordinates"] != EXPECTED_SOURCE_COORDINATES:
        fail("SOURCE_COORDINATES_INVALID", "sourceCoordinates differ from the frozen exact supplier coordinates")
    if profile["supplierBindings"] != EXPECTED_SUPPLIER_BINDINGS:
        fail("SUPPLIER_BINDINGS_INVALID", "supplierBindings differ from the frozen join contract")
    if profile["objectSchemas"] != list(OBJECT_SCHEMAS):
        fail("OBJECT_SCHEMA_DENOMINATOR_INVALID", "objectSchemas denominator differs")
    if profile["terminalStates"] != list(TERMINALS):
        fail("TERMINAL_DENOMINATOR_INVALID", "terminalStates must be closed and ordered")
    if profile["permittedAuthorityClasses"] != list(PERMITTED_AUTHORITY):
        fail("AUTHORITY_DENOMINATOR_INVALID", "permittedAuthorityClasses differs")
    if profile["volumeLayout"] != EXPECTED_LAYOUT:
        fail("VOLUME_LAYOUT_INVALID", "volumeLayout differs from the closed removable-volume layout")
    if profile["fixtureCaseIds"] != list(CASE_IDS):
        fail("CASE_DENOMINATOR_INVALID", "fixtureCaseIds differs from the closed version-0.1 denominator")
    if profile["claimBoundary"] != PUBLIC_CLAIM_BOUNDARY:
        fail("CLAIM_BOUNDARY_INVALID", "profile claimBoundary differs from the admitted non-claim text")
    if sha256_bytes(canonical_json_bytes(profile)) != PROFILE_CANONICAL_SHA256:
        fail("PROFILE_CANONICAL_DIGEST_INVALID", "profile canonical digest differs from the admitted profile")
    return profile


def validate_mission(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail("MISSION_INVALID", f"{label} must be an object")
    require_exact_keys(value, {"missionId", "cartridgeId", "cartridgeSha256", "invariantRefs", "save", "humanAuthority"}, label)
    require_string(value["missionId"], f"{label}.missionId", pattern=ID_RE)
    require_string(value["cartridgeId"], f"{label}.cartridgeId", pattern=ID_RE)
    require_string(value["cartridgeSha256"], f"{label}.cartridgeSha256", pattern=HEX64)
    require_string_list(value["invariantRefs"], f"{label}.invariantRefs", nonempty=True)
    save = value["save"]
    if not isinstance(save, dict):
        fail("SAVE_INVALID", f"{label}.save must be an object")
    require_exact_keys(save, {"frontier", "stateSha256", "unresolvedObligations", "nextSafeAction"}, f"{label}.save")
    require_int(save["frontier"], f"{label}.save.frontier")
    require_string(save["stateSha256"], f"{label}.save.stateSha256", pattern=HEX64)
    require_string_list(save["unresolvedObligations"], f"{label}.save.unresolvedObligations")
    require_string(save["nextSafeAction"], f"{label}.save.nextSafeAction")
    authority = value["humanAuthority"]
    if not isinstance(authority, dict):
        fail("HUMAN_AUTHORITY_INVALID", f"{label}.humanAuthority must be an object")
    require_exact_keys(authority, {"actorId", "required", "actionClass"}, f"{label}.humanAuthority")
    require_string(authority["actorId"], f"{label}.humanAuthority.actorId", pattern=ID_RE)
    require_bool(authority["required"], f"{label}.humanAuthority.required")
    require_string(authority["actionClass"], f"{label}.humanAuthority.actionClass", pattern=ID_RE)
    if value["cartridgeSha256"] != cartridge_law_sha256(value):
        fail("CARTRIDGE_LAW_DIGEST_INVALID", f"{label}.cartridgeSha256 does not bind the canonical cartridge law")
    return value


def validate_task(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail("TASK_INVALID", f"{label} must be an object")
    require_exact_keys(
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
    require_string(value["workUnitRef"], f"{label}.workUnitRef", pattern=ID_RE)
    require_string(value["workUnitSha256"], f"{label}.workUnitSha256", pattern=HEX64)
    if value["supplierSchema"] != EXPECTED_SUPPLIER_BINDINGS["maryWorkUnitSchema"]:
        fail("WORK_UNIT_SCHEMA_INVALID", f"{label}.supplierSchema differs from the frozen MARY binding")
    require_string_list(value["requiredCapabilities"], f"{label}.requiredCapabilities", nonempty=True)
    require_string(value["privacyLane"], f"{label}.privacyLane", pattern=ID_RE)
    require_string(value["authorityClass"], f"{label}.authorityClass", pattern=ID_RE)
    require_string(value["requiredValidatorRef"], f"{label}.requiredValidatorRef", pattern=ID_RE)
    require_int(value["wallTimeMs"], f"{label}.wallTimeMs", minimum=1)
    require_int(value["minimumMemoryBytes"], f"{label}.minimumMemoryBytes")
    return value


def validate_equipment(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail("EQUIPMENT_INVALID", f"{label} must be an object")
    require_exact_keys(
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
    require_string(value["equipmentId"], f"{label}.equipmentId", pattern=ID_RE)
    if value["supplierSchema"] != EXPECTED_SUPPLIER_BINDINGS["maryEstatePhaseSchema"]:
        fail("ESTATE_PHASE_SCHEMA_INVALID", f"{label}.supplierSchema differs from the frozen MARY binding")
    require_string(value["estatePhaseRef"], f"{label}.estatePhaseRef", pattern=ID_RE)
    require_string(value["estatePhaseSha256"], f"{label}.estatePhaseSha256", pattern=HEX64)
    interface = value["interface"]
    if not isinstance(interface, dict):
        fail("INTERFACE_INVALID", f"{label}.interface must be an object")
    require_exact_keys(interface, {"declared", "readOnly", "adapterRef", "adapterAvailable"}, f"{label}.interface")
    require_bool(interface["declared"], f"{label}.interface.declared")
    require_bool(interface["readOnly"], f"{label}.interface.readOnly")
    require_string(interface["adapterRef"], f"{label}.interface.adapterRef", pattern=ID_RE)
    require_bool(interface["adapterAvailable"], f"{label}.interface.adapterAvailable")
    observed = require_int(value["observedAtUnixNs"], f"{label}.observedAtUnixNs", minimum=1)
    fresh = require_int(value["freshUntilUnixNs"], f"{label}.freshUntilUnixNs", minimum=1)
    now = require_int(value["observationTimeUnixNs"], f"{label}.observationTimeUnixNs", minimum=1)
    if fresh < observed or now < observed:
        fail("EQUIPMENT_TIME_INVALID", f"{label} observation time interval is invalid")
    require_string(value["evidenceRef"], f"{label}.evidenceRef", pattern=SHA256_REF)
    return value


def validate_route(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail("ROUTE_INVALID", f"{label} must be an object")
    require_exact_keys(
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
    require_string(value["routeId"], f"{label}.routeId", pattern=ID_RE)
    if value["supplierSchema"] != EXPECTED_SUPPLIER_BINDINGS["maryRouteDescriptorSchema"]:
        fail("ROUTE_SCHEMA_INVALID", f"{label}.supplierSchema differs from the frozen MARY binding")
    require_string(value["supplierRouteRef"], f"{label}.supplierRouteRef", pattern=ID_RE)
    require_string(value["supplierRouteSha256"], f"{label}.supplierRouteSha256", pattern=HEX64)
    require_string(value["fabricSeatRef"], f"{label}.fabricSeatRef", pattern=ID_RE)
    require_string(value["hostClass"], f"{label}.hostClass", pattern=ID_RE)
    require_string(value["routeClass"], f"{label}.routeClass", pattern=ID_RE)
    require_bool(value["available"], f"{label}.available")
    resident = require_bool(value["residentFloor"], f"{label}.residentFloor")
    optional = require_bool(value["optionalOrgan"], f"{label}.optionalOrgan")
    if resident and optional:
        fail("ROUTE_ROLE_CONFLICT", f"{label} cannot be residentFloor and optionalOrgan")
    require_string_list(value["capabilities"], f"{label}.capabilities", nonempty=True)
    require_string_list(value["privacyLanes"], f"{label}.privacyLanes", nonempty=True)
    require_string_list(value["validatorRefs"], f"{label}.validatorRefs", nonempty=True)
    require_int(value["memoryBytes"], f"{label}.memoryBytes")
    require_int(value["maximumWallTimeMs"], f"{label}.maximumWallTimeMs", minimum=1)
    require_int(value["preferenceRank"], f"{label}.preferenceRank")
    require_string(value["evidenceRef"], f"{label}.evidenceRef", pattern=SHA256_REF)
    return value


def validate_case(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail("CASE_INVALID", f"{label} must be an object")
    require_exact_keys(value, {"caseId", "expectedTerminal", "mission", "task", "equipment", "routes"}, label)
    require_string(value["caseId"], f"{label}.caseId", pattern=ID_RE)
    if value["expectedTerminal"] not in TERMINALS:
        fail("EXPECTED_TERMINAL_INVALID", f"{label}.expectedTerminal is not closed")
    mission = validate_mission(value["mission"], f"{label}.mission")
    task = validate_task(value["task"], f"{label}.task")
    validate_equipment(value["equipment"], f"{label}.equipment")
    routes = value["routes"]
    if not isinstance(routes, list) or not routes:
        fail("ROUTE_DENOMINATOR_INVALID", f"{label}.routes must be a non-empty list")
    route_ids: list[str] = []
    for index, route in enumerate(routes):
        validate_route(route, f"{label}.routes[{index}]")
        route_ids.append(route["routeId"])
    if len(set(route_ids)) != len(route_ids):
        fail("DUPLICATE_ROUTE_ID", f"{label}.routes contains duplicate routeId")
    if mission["humanAuthority"]["actionClass"] != task["authorityClass"]:
        fail("AUTHORITY_BINDING_INVALID", f"{label} mission and task authority classes differ")
    return value


def validate_fixture_catalog(path: Path, profile: dict[str, Any]) -> dict[str, Any]:
    catalog = read_json(path)
    require_exact_keys(catalog, {"schema", "profileId", "cases"}, "fixtureCatalog")
    if catalog["schema"] != CATALOG_SCHEMA or catalog["profileId"] != profile["profileId"]:
        fail("CATALOG_IDENTITY_INVALID", "fixture catalog identity differs")
    cases = catalog["cases"]
    if not isinstance(cases, list):
        fail("CASE_DENOMINATOR_INVALID", "fixture catalog cases must be a list")
    case_ids: list[str] = []
    for index, case in enumerate(cases):
        validate_case(case, f"fixtureCatalog.cases[{index}]")
        case_ids.append(case["caseId"])
    if case_ids != list(CASE_IDS) or case_ids != profile["fixtureCaseIds"]:
        fail("CASE_DENOMINATOR_INVALID", "fixture catalog case denominator differs from the admitted profile")
    if sha256_bytes(canonical_json_bytes(catalog)) != FIXTURE_CATALOG_CANONICAL_SHA256:
        fail("FIXTURE_CATALOG_CANONICAL_DIGEST_INVALID", "fixture catalog canonical digest differs from the admitted catalog")
    return catalog


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


def make_work_unit_binding(task: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    body = {
        "schema": WORK_UNIT_BINDING_SCHEMA,
        "profileId": profile["profileId"],
        "workUnitRef": task["workUnitRef"],
        "workUnitSha256": task["workUnitSha256"],
        "supplierSchema": task["supplierSchema"],
        "task": task,
    }
    return {**body, "workUnitBindingId": content_id("axmheadworkunit1", body)}


def make_equipment_observation(equipment: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    body = {"schema": EQUIPMENT_SCHEMA, "profileId": profile["profileId"], **equipment}
    return {**body, "observationId": content_id("axmheadobservation1", body)}


def make_route_denominator(case: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    routes = sorted(case["routes"], key=lambda row: row["routeId"])
    body = {
        "schema": ROUTE_DENOMINATOR_SCHEMA,
        "profileId": profile["profileId"],
        "caseId": case["caseId"],
        "supplierSchema": profile["supplierBindings"]["maryRouteDescriptorSchema"],
        "fabricSchemas": {
            "seatSnapshot": profile["supplierBindings"]["estateSeatSnapshotSchema"],
            "routeSelection": profile["supplierBindings"]["estateRouteSelectionSchema"],
            "workerLease": profile["supplierBindings"]["estateWorkerLeaseSchema"],
        },
        "routeCount": len(routes),
        "routes": routes,
    }
    return {**body, "routeDenominatorId": content_id("axmheadroutes1", body)}


def decide_case(case: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    validate_case(case, "case")
    task = case["task"]
    equipment = case["equipment"]
    interface = equipment["interface"]
    work_unit = make_work_unit_binding(task, profile)
    observation = make_equipment_observation(equipment, profile)
    denominator = make_route_denominator(case, profile)
    reason_codes: list[str] = []
    missing: list[str] = []
    hard_hold = False
    if task["authorityClass"] not in profile["permittedAuthorityClasses"]:
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
        "profileId": profile["profileId"],
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


def find_case(catalog: dict[str, Any], case_id: str) -> dict[str, Any]:
    for case in catalog["cases"]:
        if case["caseId"] == case_id:
            return case
    fail("CASE_NOT_FOUND", f"caseId {case_id!r} is absent")


def make_recovery(case: dict[str, Any], equipment: dict[str, Any], denominator: dict[str, Any], decision: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    mission = case["mission"]
    authority = mission["humanAuthority"]
    return {
        "schema": COLD_SUCCESSOR_SCHEMA,
        "profileId": profile["profileId"],
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
        "answers": {
            "whatMission": mission["missionId"],
            "currentState": f"frontier {mission['save']['frontier']} terminal {decision['terminal']}",
            "whoMayAct": authority["actorId"] if authority["required"] else "no named human required",
            "whatProvesIt": [equipment["evidenceRef"], *[route["evidenceRef"] for route in denominator["routes"]]],
            "whatRemainsUnresolved": mission["save"]["unresolvedObligations"],
            "nextSafeAction": mission["save"]["nextSafeAction"],
        },
        "dependenciesAbsent": list(DEPENDENCIES_ABSENT),
        "systemAuthority": "none",
    }


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def clean_relative_path(value: str) -> str:
    if not value or value.startswith(("/", "\\")) or "\\" in value:
        fail("RELATIVE_PATH_INVALID", f"invalid relative path {value!r}")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        fail("RELATIVE_PATH_INVALID", f"invalid relative path {value!r}")
    return value


def normalized_source_bytes(path: Path) -> bytes:
    try:
        return path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    except (OSError, UnicodeError) as exc:
        fail("SOURCE_READ_FAILED", f"{path}: {exc}")


def build_volume(
    *,
    profile_path: Path,
    catalog_path: Path,
    case_id: str,
    out: Path,
    verifier_source_path: Path | None = None,
) -> dict[str, Any]:
    profile = validate_profile(profile_path)
    catalog = validate_fixture_catalog(catalog_path, profile)
    case = find_case(catalog, case_id)
    decision = decide_case(case, profile)
    if decision["terminal"] != case["expectedTerminal"]:
        fail("EXPECTED_TERMINAL_MISMATCH", f"case expected {case['expectedTerminal']} but decided {decision['terminal']}")
    if out.exists():
        fail("OUTPUT_EXISTS", f"output already exists: {out}")
    verifier_path = verifier_source_path or Path(__file__).with_name("verify_axm_head_volume.py")
    verifier_bytes = normalized_source_bytes(verifier_path)
    if sha256_bytes(verifier_bytes) != STANDALONE_VERIFIER_SHA256:
        fail("VERIFIER_TRUST_MISMATCH", "standalone verifier bytes differ from the admitted verifier")
    out.mkdir(parents=True)
    for directory in profile["volumeLayout"].values():
        (out / directory).mkdir()

    mission = case["mission"]
    work_unit = make_work_unit_binding(case["task"], profile)
    equipment = make_equipment_observation(case["equipment"], profile)
    denominator = make_route_denominator(case, profile)
    cartridge = {
        **cartridge_law_body(mission),
        "cartridgeSha256": mission["cartridgeSha256"],
    }
    save = {
        "schema": SAVE_SCHEMA,
        "profileId": profile["profileId"],
        "missionId": mission["missionId"],
        "cartridgeId": mission["cartridgeId"],
        "workUnitRef": case["task"]["workUnitRef"],
        "workUnitSha256": case["task"]["workUnitSha256"],
        "frontier": mission["save"]["frontier"],
        "stateSha256": mission["save"]["stateSha256"],
        "unresolvedObligations": mission["save"]["unresolvedObligations"],
        "nextSafeAction": mission["save"]["nextSafeAction"],
        "lastDecisionId": decision["decisionId"],
        "terminal": decision["terminal"],
    }
    ledger_body = {
        "schema": LEDGER_SCHEMA,
        "sequence": 1,
        "caseId": case["caseId"],
        "missionId": mission["missionId"],
        "cartridgeId": mission["cartridgeId"],
        "workUnitRef": case["task"]["workUnitRef"],
        "equipmentId": case["equipment"]["equipmentId"],
        "routeDenominatorId": denominator["routeDenominatorId"],
        "decisionId": decision["decisionId"],
        "terminal": decision["terminal"],
        "executionOccurred": False,
        "systemAuthority": "none",
    }
    ledger_event = {**ledger_body, "eventId": content_id("axmheadledger1", ledger_body)}
    recovery = make_recovery(case, equipment, denominator, decision, profile)
    public = {
        "schema": PUBLIC_STATUS_SCHEMA,
        "profileId": profile["profileId"],
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

    payloads: dict[str, bytes] = {
        "CARTRIDGE/mission.json": pretty_json_bytes(cartridge),
        "CARTRIDGE/work-unit.json": pretty_json_bytes(work_unit),
        "SAVE/state.json": pretty_json_bytes(save),
        "SAVE/ledger.jsonl": canonical_json_bytes(ledger_event),
        "ROUTES/equipment-observation.json": pretty_json_bytes(equipment),
        "ROUTES/candidate-routes.json": pretty_json_bytes(denominator),
        "ROUTES/intake-decision.json": pretty_json_bytes(decision),
        "RECOVERY/cold-successor.json": pretty_json_bytes(recovery),
        "RECOVERY/profile.json": pretty_json_bytes(profile),
        "RECOVERY/fixture-catalog.json": pretty_json_bytes(catalog),
        "RECOVERY/verify_volume.py": verifier_bytes,
        "PUBLIC/status.json": pretty_json_bytes(public),
    }
    roles = {
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
    file_rows: list[dict[str, Any]] = []
    for relative in sorted(payloads):
        clean_relative_path(relative)
        data = payloads[relative]
        write_bytes(out / relative, data)
        file_rows.append({"path": relative, "role": roles[relative], "bytes": len(data), "sha256": sha256_bytes(data)})

    manifest_body: dict[str, Any] = {
        "schema": VOLUME_SCHEMA,
        "profileId": profile["profileId"],
        "caseId": case["caseId"],
        "terminal": decision["terminal"],
        "sourceCoordinates": profile["sourceCoordinates"],
        "supplierBindings": profile["supplierBindings"],
        "profileCanonicalSha256": PROFILE_CANONICAL_SHA256,
        "fixtureCatalogCanonicalSha256": FIXTURE_CATALOG_CANONICAL_SHA256,
        "standaloneVerifierSha256": STANDALONE_VERIFIER_SHA256,
        "bootstrapRequired": True,
        "fixtureCaseIds": list(CASE_IDS),
        "layout": profile["volumeLayout"],
        "cartridgeBinding": {
            "missionId": mission["missionId"],
            "cartridgeId": mission["cartridgeId"],
            "declaredCartridgeSha256": mission["cartridgeSha256"],
        },
        "workUnitBinding": {
            "workUnitRef": case["task"]["workUnitRef"],
            "workUnitSha256": case["task"]["workUnitSha256"],
            "supplierSchema": case["task"]["supplierSchema"],
            "workUnitBindingId": work_unit["workUnitBindingId"],
        },
        "saveBinding": {
            "cartridgeId": mission["cartridgeId"],
            "workUnitRef": case["task"]["workUnitRef"],
            "frontier": mission["save"]["frontier"],
            "stateSha256": mission["save"]["stateSha256"],
        },
        "equipmentBinding": {
            "equipmentId": case["equipment"]["equipmentId"],
            "estatePhaseRef": case["equipment"]["estatePhaseRef"],
            "estatePhaseSha256": case["equipment"]["estatePhaseSha256"],
            "observationId": equipment["observationId"],
        },
        "routeDenominator": {
            "routeDenominatorId": denominator["routeDenominatorId"],
            "routeCount": denominator["routeCount"],
            "routeIds": [route["routeId"] for route in denominator["routes"]],
            "supplierSchema": denominator["supplierSchema"],
        },
        "cachePolicy": {"authoritative": False, "includedInVolumeId": False, "allowedPrefix": "CACHE/"},
        "files": file_rows,
        "systemAuthority": "none",
        "executionOccurred": False,
        "claimBoundary": PUBLIC_CLAIM_BOUNDARY,
    }
    manifest = {**manifest_body, "volumeId": content_id("axmheadvolume1", manifest_body)}
    write_bytes(out / "MANIFEST.json", pretty_json_bytes(manifest))
    return manifest


def print_json(value: Any) -> None:
    sys.stdout.buffer.write(pretty_json_bytes(value))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AXM HEAD edge-demo contract and removable-volume fixture builder")
    sub = parser.add_subparsers(dest="command", required=True)
    p_profile = sub.add_parser("validate-profile")
    p_profile.add_argument("profile", type=Path)
    p_catalog = sub.add_parser("validate-fixtures")
    p_catalog.add_argument("profile", type=Path)
    p_catalog.add_argument("fixtures", type=Path)
    p_decide = sub.add_parser("decide")
    p_decide.add_argument("profile", type=Path)
    p_decide.add_argument("fixtures", type=Path)
    p_decide.add_argument("case_id")
    p_build = sub.add_parser("build-volume")
    p_build.add_argument("profile", type=Path)
    p_build.add_argument("fixtures", type=Path)
    p_build.add_argument("case_id")
    p_build.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate-profile":
            profile = validate_profile(args.profile)
            print_json(
                {
                    "status": "PASS",
                    "profileId": profile["profileId"],
                    "profileCanonicalSha256": PROFILE_CANONICAL_SHA256,
                    "objectSchemaCount": len(profile["objectSchemas"]),
                    "fixtureCaseCount": len(profile["fixtureCaseIds"]),
                }
            )
        elif args.command == "validate-fixtures":
            profile = validate_profile(args.profile)
            catalog = validate_fixture_catalog(args.fixtures, profile)
            decisions = [decide_case(case, profile) for case in catalog["cases"]]
            for case, decision in zip(catalog["cases"], decisions):
                if case["expectedTerminal"] != decision["terminal"]:
                    fail("EXPECTED_TERMINAL_MISMATCH", f"{case['caseId']} expected {case['expectedTerminal']} got {decision['terminal']}")
            print_json(
                {
                    "status": "PASS",
                    "caseCount": len(decisions),
                    "fixtureCatalogCanonicalSha256": FIXTURE_CATALOG_CANONICAL_SHA256,
                    "caseIds": [case["caseId"] for case in catalog["cases"]],
                    "terminals": [row["terminal"] for row in decisions],
                }
            )
        elif args.command == "decide":
            profile = validate_profile(args.profile)
            catalog = validate_fixture_catalog(args.fixtures, profile)
            print_json(decide_case(find_case(catalog, args.case_id), profile))
        elif args.command == "build-volume":
            print_json(build_volume(profile_path=args.profile, catalog_path=args.fixtures, case_id=args.case_id, out=args.out))
        return 0
    except DemoError as exc:
        print_json({"status": "REFUSED", "code": exc.code, "message": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
