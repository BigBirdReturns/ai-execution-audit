from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

PROFILE_SCHEMA = "axm-head-physical-long-haul-001-join-v2-profile/2"
PROFILE_ID = "axm-head/physical-long-haul-001/join-v2"
STATE_SCHEMA = "axm-head/physical-long-haul-001-join-state@2"
CARD_SCHEMA = "axm-head/physical-operator-card@2"
DECISION_SCHEMA = "axm-head/physical-long-haul-001-join-decision@2"
PUBLIC_SCHEMA = "axm-head/physical-long-haul-001-public-status@2"
MANIFEST_SCHEMA = "axm-head/physical-long-haul-001-join-manifest@2"
PROFILE_CANONICAL_SHA256 = "66a4e11b0023a67e0d545b9d29817819da17e9195304261f1fd30a6f6da74e56"
STANDALONE_VERIFIER_SHA256 = "8ba7f39f512a4f683bf6780ff0ac3a128d10d83dd07b59f4e7e62946f41b5761"
TERMINALS = ("PREPARED_NOT_ARMED", "HOLD", "READY_FOR_HUMAN_REVIEW", "REFUSED")
ARTIFACT_LABELS = ("cartridge", "model", "verifier", "storage")
PHASE_SEQUENCE = (
    "admitted_checkout",
    "artifact_coordinates",
    "readiness",
    "feed",
    "personal_floor",
    "halo3",
    "post_halo3_continuity",
    "two_cell_partition",
    "successor_head",
    "flight_plan",
    "private_packet",
    "sealed_flight",
)
FLIGHT_PLAN_GATES = (
    "admitted_checkout",
    "personal_floor",
    "halo3",
    "post_halo3_continuity",
    "lattice_absence",
    "two_cell_partition",
    "successor_head",
    "private_evidence_root",
)
PACKET_STAGE_SEQUENCE = (
    "VERIFY_INPUTS",
    "MOUNT_PERSONAL_FLOOR",
    "BIND_GRACE",
    "RUN_PERSONAL_FLOOR_BASELINE",
    "ATTACH_HALO3",
    "RUN_HALO3_ACCELERATED",
    "REMOVE_HALO3",
    "VERIFY_PERSONAL_FLOOR_CONTINUITY",
    "REMOVE_LATTICE",
    "VERIFY_LOCAL_CONTINUITY",
    "PARTITION_TWO_CELLS",
    "RESTORE_LINK_HOLD_CONFLICT",
    "REPLACE_HEAD",
    "REBUILD_PROJECTIONS",
    "COLD_SUCCESSOR_VERIFY",
    "SEAL_PRIVATE_EVIDENCE",
)
EXPECTED_SOURCE_COORDINATES = {
    "admittedAxmHeadSupplier": {
        "repository": "BigBirdReturns/ai-execution-audit",
        "commit": "b452bb32e26249deab90db124f157bc62ad0850d",
        "tree": "c557bddc17ad62f6ad36bac5a6ef57338429a951",
        "status": "admitted",
    },
    "supplierConstructionRecord": {
        "repository": "BigBirdReturns/ai-execution-audit",
        "commit": "e185b3de109b0fb9be1dddcc33c3d410b8f1fc46",
        "tree": "c557bddc17ad62f6ad36bac5a6ef57338429a951",
        "status": "qualified_then_squash_admitted",
    },
    "admittedConductor": {
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
}
EXPECTED_ISSUE = {
    "repository": "BigBirdReturns/ai-execution-audit",
    "issueNumber": 37,
    "role": "sole_private_physical_flight_execution_coordinate",
}
CLAIM_BOUNDARY = (
    "Public preflight join binding the admitted AXM HEAD mission-volume contract to the admitted STC MARY "
    "conductor, frozen physical-flight floor, and sole issue #37 execution coordinate. It may validate body-free "
    "private coordinate headers and compile an exact operator card, but it performs no physical action, materializes "
    "no mission volume, launches no worker, creates no listener, grants no authorization, and establishes no physical "
    "Estate, representative operator, field network, operational C2, production Lattice, mission, command, targeting, "
    "engagement, effector, or weapons qualification or authority."
)
PREPARED_REASON_CODES = (
    "ADMITTED_PUBLIC_FLOOR_BOUND",
    "EXECUTION_CARD_ABSENT",
    "PRIVATE_COORDINATES_ABSENT",
    "SEPARATE_HUMAN_AUTHORIZATION_ABSENT",
)
PREPARED_NEXT_SAFE_ACTION = (
    "Resolve the two exact clean checkouts and four body-free private coordinate headers, compile the deterministic "
    "operator card, and return the card for separate named-human review. Do not begin physical execution."
)
PREPARED_WAKE_CONDITION = (
    "The exact conductor and physical-floor checkouts are clean and detached, all four private coordinates are "
    "content-bound without exposing paths or bodies, and the compiled operator card matches the admitted profile."
)
CONTROL_QUESTION = (
    "Does the exact operator card tell the named human what to touch, what to run, what receipt must appear, and what "
    "condition stops the campaign while every action remains unauthorized?"
)
EXPECTED_RELATIVE_FILES = (
    "JOIN/preparation-state.json",
    "JOIN/decision.json",
    "PUBLIC/status.json",
    "RECOVERY/profile.json",
    "RECOVERY/verify_join.py",
)
HEX40 = re.compile(r"^[0-9a-f]{40}$")
SHA256_REF = re.compile(r"^sha256:[0-9a-f]{64}$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._:/@-]{2,255}$")
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class JoinError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def fail(code: str, message: str) -> None:
    raise JoinError(code, message)


def canonical_json_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        fail("NON_CANONICAL_JSON", str(exc))
    return (text + "\n").encode("utf-8")


def type_strict_equal(actual: Any, expected: Any) -> bool:
    return canonical_json_bytes(actual) == canonical_json_bytes(expected)


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


def read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail("JSON_READ_FAILED", f"{path}: {exc}")
    if not isinstance(value, dict):
        fail("JSON_OBJECT_REQUIRED", f"{path} must contain one JSON object")
    return value


def ensure_repository_external_output(path: Path | None) -> None:
    if path is None:
        return
    repository = REPOSITORY_ROOT.resolve()
    candidate = path.resolve(strict=False)
    if candidate == repository or repository in candidate.parents:
        fail("REPOSITORY_OUTPUT_REFUSED", "JOIN-v2 output may not be written inside the repository")


def require_exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        fail("OBJECT_KEYS_INVALID", f"{label} missing={sorted(expected - actual)} unknown={sorted(actual - expected)}")


def require_bool(value: Any, label: str) -> bool:
    if type(value) is not bool:
        fail("BOOLEAN_REQUIRED", f"{label} must be boolean")
    return value


def require_int(value: Any, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        fail("INTEGER_REQUIRED", f"{label} must be an integer >= {minimum}")
    return value


def require_string(value: Any, label: str, *, pattern: re.Pattern[str] | None = None) -> str:
    if not isinstance(value, str) or not value:
        fail("STRING_REQUIRED", f"{label} must be a non-empty string")
    if pattern is not None and pattern.fullmatch(value) is None:
        fail("STRING_PATTERN_INVALID", f"{label} has an invalid value")
    return value


def validate_profile(path: Path) -> dict[str, Any]:
    profile = read_object(path)
    require_exact_keys(
        profile,
        {
            "schema",
            "profileId",
            "status",
            "owningProject",
            "owningRepository",
            "sourceCoordinates",
            "physicalFlightIssue",
            "terminalStates",
            "artifactLabels",
            "phaseSequence",
            "flightPlanGates",
            "packetStageSequence",
            "phasePlans",
            "stopConditions",
            "bootstrapRequired",
            "repositoryOutputAllowed",
            "networkRequired",
            "externalServiceCalls",
            "operationalCredentials",
            "privateEvidenceBodiesPublic",
            "physicalAuthorizationProduced",
            "workersLaunched",
            "listenersCreated",
            "authority",
            "claimBoundary",
        },
        "profile",
    )
    if profile["schema"] != PROFILE_SCHEMA or profile["profileId"] != PROFILE_ID:
        fail("PROFILE_IDENTITY_INVALID", "profile schema or profileId differs")
    if profile["status"] != "candidate_contract_only":
        fail("PROFILE_STATUS_INVALID", "profile status must remain candidate_contract_only")
    if profile["owningProject"] != "Estate" or profile["owningRepository"] != "BigBirdReturns/ai-execution-audit":
        fail("PROFILE_SCOPE_INVALID", "profile owning project or repository differs")
    if not type_strict_equal(profile["sourceCoordinates"], EXPECTED_SOURCE_COORDINATES):
        fail("SOURCE_COORDINATES_INVALID", "profile source coordinates differ from the admitted join floor")
    if not type_strict_equal(profile["physicalFlightIssue"], EXPECTED_ISSUE):
        fail("PHYSICAL_ISSUE_INVALID", "issue #37 must remain the sole physical-flight coordinate")
    if profile["terminalStates"] != list(TERMINALS):
        fail("TERMINAL_DENOMINATOR_INVALID", "terminal state denominator differs")
    if profile["artifactLabels"] != list(ARTIFACT_LABELS):
        fail("ARTIFACT_DENOMINATOR_INVALID", "private artifact denominator differs")
    if profile["phaseSequence"] != list(PHASE_SEQUENCE):
        fail("PHASE_DENOMINATOR_INVALID", "conductor phase denominator differs")
    if profile["flightPlanGates"] != list(FLIGHT_PLAN_GATES):
        fail("GATE_DENOMINATOR_INVALID", "flight-plan gate denominator differs")
    if profile["packetStageSequence"] != list(PACKET_STAGE_SEQUENCE):
        fail("PACKET_STAGE_DENOMINATOR_INVALID", "packet stage denominator differs")
    plans = profile["phasePlans"]
    if not isinstance(plans, list) or [row.get("phase") for row in plans if isinstance(row, dict)] != list(PHASE_SEQUENCE):
        fail("PHASE_PLAN_DENOMINATOR_INVALID", "phase plan denominator differs")
    for index, plan in enumerate(plans):
        if not isinstance(plan, dict):
            fail("PHASE_PLAN_INVALID", f"phasePlans[{index}] must be an object")
        require_exact_keys(
            plan,
            {"phase", "actionClass", "commandSurface", "operatorAction", "receiptClasses", "humanRequired", "physicalAction"},
            f"phasePlans[{index}]",
        )
        require_string(plan["actionClass"], f"phasePlans[{index}].actionClass", pattern=ID_RE)
        require_string(plan["commandSurface"], f"phasePlans[{index}].commandSurface")
        require_string(plan["operatorAction"], f"phasePlans[{index}].operatorAction")
        if not isinstance(plan["receiptClasses"], list) or not plan["receiptClasses"]:
            fail("RECEIPT_DENOMINATOR_INVALID", f"phasePlans[{index}].receiptClasses must be non-empty")
        for receipt_index, receipt in enumerate(plan["receiptClasses"]):
            require_string(receipt, f"phasePlans[{index}].receiptClasses[{receipt_index}]")
        require_bool(plan["humanRequired"], f"phasePlans[{index}].humanRequired")
        require_bool(plan["physicalAction"], f"phasePlans[{index}].physicalAction")
    if not isinstance(profile["stopConditions"], list) or len(profile["stopConditions"]) != len(set(profile["stopConditions"])):
        fail("STOP_CONDITIONS_INVALID", "stopConditions must be a unique list")
    if profile["bootstrapRequired"] is not True or profile["repositoryOutputAllowed"] is not False:
        fail("PROFILE_CUSTODY_INVALID", "bootstrap and repository-output boundaries differ")
    for key, expected in (
        ("networkRequired", False),
        ("externalServiceCalls", 0),
        ("operationalCredentials", 0),
        ("privateEvidenceBodiesPublic", 0),
        ("physicalAuthorizationProduced", False),
        ("workersLaunched", 0),
        ("listenersCreated", 0),
        ("authority", "none"),
        ("claimBoundary", CLAIM_BOUNDARY),
    ):
        if not type_strict_equal(profile[key], expected):
            fail("PROFILE_NONCLAIM_INVALID", f"profile {key} differs")
    if sha256_bytes(canonical_json_bytes(profile)) != PROFILE_CANONICAL_SHA256:
        fail("PROFILE_CANONICAL_DIGEST_INVALID", "profile canonical digest differs")
    return profile


def join_contract_id(profile: dict[str, Any]) -> str:
    body = {
        "schema": PROFILE_SCHEMA,
        "profileId": PROFILE_ID,
        "owningProject": profile["owningProject"],
        "owningRepository": profile["owningRepository"],
        "sourceCoordinates": profile["sourceCoordinates"],
        "physicalFlightIssue": profile["physicalFlightIssue"],
        "phaseSequence": profile["phaseSequence"],
        "flightPlanGates": profile["flightPlanGates"],
        "packetStageSequence": profile["packetStageSequence"],
        "claimBoundary": CLAIM_BOUNDARY,
    }
    return content_id("axmheadphysjoin2", body)


def state_basis_body(profile: dict[str, Any], value: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": STATE_SCHEMA,
        "profileId": PROFILE_ID,
        "joinContractId": join_contract_id(profile),
        "sourceCoordinates": value["sourceCoordinates"],
        "physicalFlightIssue": value["physicalFlightIssue"],
        "checkoutBindings": value["checkoutBindings"],
        "privateCoordinateHeaders": value["privateCoordinateHeaders"],
        "physicalExecutionStarted": value["physicalExecutionStarted"],
        "workersLaunched": value["workersLaunched"],
        "listenersCreated": value["listenersCreated"],
        "authorization": value["authorization"],
        "authority": value["authority"],
    }


def make_state(
    profile: dict[str, Any],
    *,
    checkout_bindings: dict[str, Any] | None = None,
    private_coordinate_headers: list[dict[str, Any]] | None = None,
    execution_card: dict[str, Any] | None = None,
    physical_execution_started: bool = False,
    workers_launched: int = 0,
    listeners_created: int = 0,
    authorization: dict[str, Any] | None = None,
    authority: str = "none",
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "schema": STATE_SCHEMA,
        "profileId": PROFILE_ID,
        "joinContractId": join_contract_id(profile),
        "sourceCoordinates": copy.deepcopy(profile["sourceCoordinates"]),
        "physicalFlightIssue": copy.deepcopy(profile["physicalFlightIssue"]),
        "checkoutBindings": copy.deepcopy(checkout_bindings or {}),
        "privateCoordinateHeaders": copy.deepcopy(private_coordinate_headers or []),
        "physicalExecutionStarted": physical_execution_started,
        "workersLaunched": workers_launched,
        "listenersCreated": listeners_created,
        "authorization": copy.deepcopy(authorization or {"granted": False, "actorId": None, "transactionId": None}),
        "authority": authority,
    }
    value["preparationBasisId"] = content_id("axmheadjoinbasis2", state_basis_body(profile, value))
    value["executionCard"] = copy.deepcopy(execution_card)
    body = dict(value)
    value["stateId"] = content_id("axmheadjoinstate2", body)
    return value


def prepared_state(profile: dict[str, Any]) -> dict[str, Any]:
    return make_state(profile)


def validate_checkout_bindings(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail("CHECKOUT_BINDINGS_INVALID", "checkoutBindings must be an object")
    unknown = set(value) - {"conductor", "physicalFloor"}
    if unknown:
        fail("CHECKOUT_BINDINGS_INVALID", f"unknown checkout binding keys: {sorted(unknown)}")
    expectations = {
        "conductor": EXPECTED_SOURCE_COORDINATES["admittedConductor"],
        "physicalFloor": EXPECTED_SOURCE_COORDINATES["physicalFlightFloor"],
    }
    for name, row in value.items():
        if not isinstance(row, dict):
            fail("CHECKOUT_BINDING_INVALID", f"checkoutBindings.{name} must be an object")
        require_exact_keys(row, {"commit", "tree", "detached", "clean"}, f"checkoutBindings.{name}")
        require_string(row["commit"], f"checkoutBindings.{name}.commit", pattern=HEX40)
        require_string(row["tree"], f"checkoutBindings.{name}.tree", pattern=HEX40)
        require_bool(row["detached"], f"checkoutBindings.{name}.detached")
        require_bool(row["clean"], f"checkoutBindings.{name}.clean")
        if row["commit"] != expectations[name]["commit"] or row["tree"] != expectations[name]["tree"]:
            fail("CHECKOUT_COORDINATE_INVALID", f"checkoutBindings.{name} differs from the frozen coordinate")
    return value


def validate_private_headers(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        fail("PRIVATE_HEADERS_INVALID", "privateCoordinateHeaders must be a list")
    labels: list[str] = []
    for index, row in enumerate(value):
        if not isinstance(row, dict):
            fail("PRIVATE_HEADER_INVALID", f"privateCoordinateHeaders[{index}] must be an object")
        require_exact_keys(row, {"label", "contentRef", "exists", "symlinkRoot", "overlapFree"}, f"privateCoordinateHeaders[{index}]")
        label = require_string(row["label"], f"privateCoordinateHeaders[{index}].label")
        if label not in ARTIFACT_LABELS:
            fail("PRIVATE_HEADER_LABEL_INVALID", f"unknown private coordinate label: {label}")
        require_string(row["contentRef"], f"privateCoordinateHeaders[{index}].contentRef", pattern=SHA256_REF)
        require_bool(row["exists"], f"privateCoordinateHeaders[{index}].exists")
        require_bool(row["symlinkRoot"], f"privateCoordinateHeaders[{index}].symlinkRoot")
        require_bool(row["overlapFree"], f"privateCoordinateHeaders[{index}].overlapFree")
        labels.append(label)
    if len(labels) != len(set(labels)):
        fail("PRIVATE_HEADER_DUPLICATE", "privateCoordinateHeaders contains duplicate labels")
    return value


def validate_authorization(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail("AUTHORIZATION_INVALID", "authorization must be an object")
    require_exact_keys(value, {"granted", "actorId", "transactionId"}, "authorization")
    require_bool(value["granted"], "authorization.granted")
    for key in ("actorId", "transactionId"):
        if value[key] is not None:
            require_string(value[key], f"authorization.{key}", pattern=ID_RE)
    if not value["granted"] and (value["actorId"] is not None or value["transactionId"] is not None):
        fail("AUTHORIZATION_INVALID", "absent authorization may not carry actor or transaction identity")
    return value


def validate_state(value: Any, profile: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail("STATE_INVALID", "state must be an object")
    require_exact_keys(
        value,
        {
            "schema",
            "profileId",
            "joinContractId",
            "sourceCoordinates",
            "physicalFlightIssue",
            "checkoutBindings",
            "privateCoordinateHeaders",
            "physicalExecutionStarted",
            "workersLaunched",
            "listenersCreated",
            "authorization",
            "authority",
            "preparationBasisId",
            "executionCard",
            "stateId",
        },
        "state",
    )
    if value["schema"] != STATE_SCHEMA or value["profileId"] != PROFILE_ID:
        fail("STATE_IDENTITY_INVALID", "state schema or profileId differs")
    if value["joinContractId"] != join_contract_id(profile):
        fail("STATE_JOIN_BINDING_INVALID", "state joinContractId differs")
    if not type_strict_equal(value["sourceCoordinates"], profile["sourceCoordinates"]):
        fail("STATE_SOURCE_BINDING_INVALID", "state source coordinates differ")
    if not type_strict_equal(value["physicalFlightIssue"], profile["physicalFlightIssue"]):
        fail("STATE_ISSUE_BINDING_INVALID", "state physical-flight issue differs")
    validate_checkout_bindings(value["checkoutBindings"])
    validate_private_headers(value["privateCoordinateHeaders"])
    require_bool(value["physicalExecutionStarted"], "state.physicalExecutionStarted")
    require_int(value["workersLaunched"], "state.workersLaunched")
    require_int(value["listenersCreated"], "state.listenersCreated")
    validate_authorization(value["authorization"])
    require_string(value["authority"], "state.authority")
    basis = state_basis_body(profile, value)
    expected_basis_id = content_id("axmheadjoinbasis2", basis)
    if value["preparationBasisId"] != expected_basis_id:
        fail("STATE_BASIS_ID_INVALID", "preparationBasisId does not bind the body-free preparation basis")
    if value["executionCard"] is not None and not isinstance(value["executionCard"], dict):
        fail("EXECUTION_CARD_INVALID", "executionCard must be null or an object")
    body = dict(value)
    actual_state_id = body.pop("stateId")
    if actual_state_id != content_id("axmheadjoinstate2", body):
        fail("STATE_ID_INVALID", "stateId does not bind the complete state")
    return value


def prerequisites_complete(state: dict[str, Any]) -> bool:
    checkouts = state["checkoutBindings"]
    if set(checkouts) != {"conductor", "physicalFloor"}:
        return False
    if not all(row["detached"] and row["clean"] for row in checkouts.values()):
        return False
    headers = state["privateCoordinateHeaders"]
    if {row["label"] for row in headers} != set(ARTIFACT_LABELS):
        return False
    return all(row["exists"] and not row["symlinkRoot"] and row["overlapFree"] for row in headers)


def compile_execution_card(profile: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    validate_state(state, profile)
    if state["physicalExecutionStarted"] or state["workersLaunched"] or state["listenersCreated"]:
        fail("ACTIVITY_ALREADY_STARTED", "operator card cannot be compiled after physical activity begins")
    if state["authorization"]["granted"] or state["authority"] != "none":
        fail("AUTHORITY_ALREADY_PRESENT", "operator card cannot be compiled with authorization or authority present")
    if state["executionCard"] is not None:
        fail("EXECUTION_CARD_ALREADY_PRESENT", "compile from a card-free preparation state")
    if not prerequisites_complete(state):
        fail("PREPARATION_INCOMPLETE", "both exact checkouts and all four safe private coordinate headers are required")
    sorted_headers = sorted(state["privateCoordinateHeaders"], key=lambda row: row["label"])
    checkout_set_id = content_id("axmheadjoincheckouts2", state["checkoutBindings"])
    private_coordinate_set_id = content_id("axmheadjoinprivatecoords2", {"headers": sorted_headers})
    actions: list[dict[str, Any]] = []
    first_physical: int | None = None
    for ordinal, plan in enumerate(profile["phasePlans"], start=1):
        action = {
            "ordinal": ordinal,
            "phase": plan["phase"],
            "actionClass": plan["actionClass"],
            "commandSurface": plan["commandSurface"],
            "operatorAction": plan["operatorAction"],
            "receiptClasses": plan["receiptClasses"],
            "humanRequired": plan["humanRequired"],
            "physicalAction": plan["physicalAction"],
            "authorized": False,
            "stopConditions": profile["stopConditions"],
        }
        if first_physical is None and plan["physicalAction"]:
            first_physical = ordinal
        actions.append(action)
    body: dict[str, Any] = {
        "schema": CARD_SCHEMA,
        "profileId": PROFILE_ID,
        "joinContractId": join_contract_id(profile),
        "preparationBasisId": state["preparationBasisId"],
        "checkoutSetId": checkout_set_id,
        "privateCoordinateSetId": private_coordinate_set_id,
        "physicalFlightIssue": profile["physicalFlightIssue"],
        "actions": actions,
        "actionCount": len(actions),
        "firstPhysicalActionOrdinal": first_physical,
        "reviewState": "PENDING_NAMED_HUMAN_REVIEW",
        "physicalAuthorizationProduced": False,
        "physicalExecutionStarted": False,
        "missionVolumeMaterialized": False,
        "workersLaunched": 0,
        "listenersCreated": 0,
        "authority": "none",
        "controlQuestion": CONTROL_QUESTION,
        "claimBoundary": CLAIM_BOUNDARY,
    }
    return {**body, "cardId": content_id("axmheadoperatorcard2", body)}


def attach_compiled_card(profile: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    card = compile_execution_card(profile, state)
    return make_state(
        profile,
        checkout_bindings=state["checkoutBindings"],
        private_coordinate_headers=state["privateCoordinateHeaders"],
        execution_card=card,
        physical_execution_started=state["physicalExecutionStarted"],
        workers_launched=state["workersLaunched"],
        listeners_created=state["listenersCreated"],
        authorization=state["authorization"],
        authority=state["authority"],
    )


def make_decision(
    profile: dict[str, Any],
    state: dict[str, Any] | None,
    *,
    terminal: str,
    reason_codes: list[str],
    next_safe_action: str,
    wake_condition: str,
    error_code: str | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema": DECISION_SCHEMA,
        "profileId": PROFILE_ID,
        "joinContractId": join_contract_id(profile),
        "stateId": state["stateId"] if state else None,
        "executionCardId": state["executionCard"]["cardId"] if state and state["executionCard"] else None,
        "terminal": terminal,
        "reasonCodes": sorted(set(reason_codes)),
        "nextSafeAction": next_safe_action,
        "wakeCondition": wake_condition,
        "controlQuestion": CONTROL_QUESTION,
        "errorCode": error_code,
        "errorMessage": error_message,
        "physicalAuthorizationProduced": False,
        "physicalExecutionStarted": False,
        "missionVolumeMaterialized": False,
        "workersLaunched": 0,
        "listenersCreated": 0,
        "authority": "none",
        "claimBoundary": CLAIM_BOUNDARY,
    }
    return {**body, "decisionId": content_id("axmheadjoindecision2", body)}


def evaluate_preparation(profile: dict[str, Any], value: Any) -> dict[str, Any]:
    try:
        state = validate_state(value, profile)
    except JoinError as exc:
        return make_decision(
            profile,
            None,
            terminal="REFUSED",
            reason_codes=[exc.code],
            next_safe_action="Quarantine the altered preparation object and reconstruct it from the admitted JOIN-v2 source.",
            wake_condition="A newly reconstructed body-free state validates against the exact admitted coordinates and closed schema.",
            error_code=exc.code,
            error_message=str(exc),
        )
    if state["physicalExecutionStarted"]:
        return make_decision(
            profile,
            state,
            terminal="REFUSED",
            reason_codes=["PHYSICAL_EXECUTION_ALREADY_STARTED"],
            next_safe_action="Stop and preserve the unexpected activity record for review; do not treat this join as authorization.",
            wake_condition="A separate investigation resolves the unauthorized start and a new preparation state begins from zero activity.",
        )
    if state["workersLaunched"] != 0 or state["listenersCreated"] != 0:
        return make_decision(
            profile,
            state,
            terminal="REFUSED",
            reason_codes=["UNEXPECTED_RUNTIME_ACTIVITY"],
            next_safe_action="Stop the unexpected workers or listeners and reconstruct a zero-activity preparation state.",
            wake_condition="Workers and listeners are both zero before any card review or physical authorization transaction.",
        )
    if state["authorization"]["granted"] or state["authority"] != "none":
        return make_decision(
            profile,
            state,
            terminal="REFUSED",
            reason_codes=["AUTHORITY_PROMOTION_REFUSED"],
            next_safe_action="Remove the forged authority-bearing object from consideration and reconstruct the preparation state.",
            wake_condition="The join carries no authorization, acting authority, or machine-created permission.",
        )
    if not state["checkoutBindings"] and not state["privateCoordinateHeaders"] and state["executionCard"] is None:
        return make_decision(
            profile,
            state,
            terminal="PREPARED_NOT_ARMED",
            reason_codes=list(PREPARED_REASON_CODES),
            next_safe_action=PREPARED_NEXT_SAFE_ACTION,
            wake_condition=PREPARED_WAKE_CONDITION,
        )
    if not prerequisites_complete(state):
        reasons: list[str] = []
        if set(state["checkoutBindings"]) != {"conductor", "physicalFloor"}:
            reasons.append("EXACT_CHECKOUTS_INCOMPLETE")
        elif not all(row["detached"] and row["clean"] for row in state["checkoutBindings"].values()):
            reasons.append("CHECKOUT_NOT_CLEAN_DETACHED")
        labels = {row["label"] for row in state["privateCoordinateHeaders"]}
        if labels != set(ARTIFACT_LABELS):
            reasons.append("PRIVATE_COORDINATE_DENOMINATOR_INCOMPLETE")
        if any(not row["exists"] or row["symlinkRoot"] or not row["overlapFree"] for row in state["privateCoordinateHeaders"]):
            reasons.append("PRIVATE_COORDINATE_UNSAFE")
        return make_decision(
            profile,
            state,
            terminal="HOLD",
            reason_codes=reasons or ["PREPARATION_INCOMPLETE"],
            next_safe_action="Complete only the missing clean-checkout or body-free private-coordinate prerequisite, then reconstruct the state.",
            wake_condition=PREPARED_WAKE_CONDITION,
        )
    expected_card: dict[str, Any]
    card_free = make_state(
        profile,
        checkout_bindings=state["checkoutBindings"],
        private_coordinate_headers=state["privateCoordinateHeaders"],
        authorization=state["authorization"],
        authority=state["authority"],
    )
    expected_card = compile_execution_card(profile, card_free)
    if state["executionCard"] is None:
        return make_decision(
            profile,
            state,
            terminal="HOLD",
            reason_codes=["EXECUTION_CARD_ABSENT"],
            next_safe_action="Compile the deterministic operator card from this exact body-free preparation basis and change nothing else.",
            wake_condition="The card exactly matches the admitted phase plan, private-coordinate set, checkouts, stop conditions, and zero-authority boundary.",
        )
    if not type_strict_equal(state["executionCard"], expected_card):
        return make_decision(
            profile,
            state,
            terminal="REFUSED",
            reason_codes=["EXECUTION_CARD_MISMATCH"],
            next_safe_action="Discard the caller-supplied card and recompile it from the admitted JOIN-v2 source.",
            wake_condition="The complete card is byte-equivalent to the deterministic profile-derived card and every action remains unauthorized.",
        )
    return make_decision(
        profile,
        state,
        terminal="READY_FOR_HUMAN_REVIEW",
        reason_codes=["BODY_FREE_PREPARATION_BOUND", "EXACT_OPERATOR_CARD_COMPILED", "SEPARATE_HUMAN_AUTHORIZATION_REQUIRED"],
        next_safe_action="Review the exact operator card as a separate human transaction. Do not execute any listed action merely because the card exists.",
        wake_condition="A named human explicitly accepts or rejects one bounded next action under issue #37 without changing this join's authority none state.",
    )


def public_status(profile: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": PUBLIC_SCHEMA,
        "profileId": PROFILE_ID,
        "joinContractId": join_contract_id(profile),
        "stateId": decision["stateId"],
        "decisionId": decision["decisionId"],
        "executionCardId": decision["executionCardId"],
        "terminal": decision["terminal"],
        "reasonCodes": decision["reasonCodes"],
        "nextSafeAction": decision["nextSafeAction"],
        "physicalFlightIssue": profile["physicalFlightIssue"],
        "canonicalCommit": profile["sourceCoordinates"]["admittedAxmHeadSupplier"]["commit"],
        "canonicalTree": profile["sourceCoordinates"]["admittedAxmHeadSupplier"]["tree"],
        "physicalAuthorizationProduced": False,
        "physicalExecutionStarted": False,
        "missionVolumeMaterialized": False,
        "workersLaunched": 0,
        "listenersCreated": 0,
        "physicalEstateQualified": False,
        "representativeOperatorQualified": False,
        "fieldNetworkQualified": False,
        "operationalC2Qualified": False,
        "productionLatticeQualified": False,
        "missionAuthority": "none",
        "commandAuthority": "none",
        "targetingEngagementEffectorWeaponsCapability": False,
        "privateEvidenceBodies": 0,
        "authority": "none",
        "claimBoundary": CLAIM_BOUNDARY,
    }


def build_carrier(*, profile_path: Path, out: Path) -> dict[str, Any]:
    profile = validate_profile(profile_path)
    ensure_repository_external_output(out)
    if out.exists():
        fail("OUTPUT_EXISTS", "carrier output must not already exist")
    verifier_source = Path(__file__).resolve().with_name("verify_axm_head_physical_long_haul_001_join_v2.py")
    if not verifier_source.is_file():
        fail("VERIFIER_SOURCE_MISSING", "standalone verifier source is missing")
    verifier_bytes = verifier_source.read_bytes()
    if sha256_bytes(verifier_bytes) != STANDALONE_VERIFIER_SHA256:
        fail("VERIFIER_SOURCE_DIGEST_INVALID", "standalone verifier source digest differs")
    state = prepared_state(profile)
    decision = evaluate_preparation(profile, state)
    if decision["terminal"] != "PREPARED_NOT_ARMED":
        fail("PREPARED_TERMINAL_INVALID", "canonical carrier must begin PREPARED_NOT_ARMED")
    public = public_status(profile, decision)
    members: dict[str, bytes] = {
        "JOIN/preparation-state.json": pretty_json_bytes(state),
        "JOIN/decision.json": pretty_json_bytes(decision),
        "PUBLIC/status.json": pretty_json_bytes(public),
        "RECOVERY/profile.json": pretty_json_bytes(profile),
        "RECOVERY/verify_join.py": verifier_bytes,
    }
    for relative, data in members.items():
        path = out.joinpath(*relative.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    rows = [{"path": relative, "bytes": len(members[relative]), "sha256": sha256_bytes(members[relative])} for relative in EXPECTED_RELATIVE_FILES]
    body: dict[str, Any] = {
        "schema": MANIFEST_SCHEMA,
        "profileId": PROFILE_ID,
        "joinContractId": join_contract_id(profile),
        "stateId": state["stateId"],
        "decisionId": decision["decisionId"],
        "terminal": "PREPARED_NOT_ARMED",
        "sourceCoordinates": profile["sourceCoordinates"],
        "physicalFlightIssue": profile["physicalFlightIssue"],
        "profileCanonicalSha256": PROFILE_CANONICAL_SHA256,
        "standaloneVerifierSha256": STANDALONE_VERIFIER_SHA256,
        "bootstrapRequired": True,
        "files": rows,
        "fileCount": len(rows),
        "physicalAuthorizationProduced": False,
        "physicalExecutionStarted": False,
        "missionVolumeMaterialized": False,
        "workersLaunched": 0,
        "listenersCreated": 0,
        "authority": "none",
        "claimBoundary": CLAIM_BOUNDARY,
    }
    manifest = {**body, "carrierId": content_id("axmheadjoincarrier2", body)}
    (out / "MANIFEST.json").write_bytes(pretty_json_bytes(manifest))
    return manifest


def emit(value: dict[str, Any], out: Path | None = None, *, pretty: bool = False) -> None:
    ensure_repository_external_output(out)
    data = pretty_json_bytes(value) if pretty else canonical_json_bytes(value)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
    sys.stdout.buffer.write(data)


def run_bootstrap(carrier: Path, out: Path | None) -> int:
    ensure_repository_external_output(out)
    bootstrap = Path(__file__).resolve().with_name("verify_axm_head_physical_long_haul_001_join_v2_bootstrap.py")
    command = [sys.executable, str(bootstrap), str(carrier)]
    if out is not None:
        command.extend(["--out", str(out)])
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    sys.stdout.buffer.write(result.stdout)
    if result.stderr:
        sys.stderr.buffer.write(result.stderr)
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build and evaluate AXM HEAD physical long-haul JOIN-v2")
    sub = parser.add_subparsers(dest="command", required=True)
    validate_parser = sub.add_parser("validate-profile")
    validate_parser.add_argument("profile", type=Path)
    prepared_parser = sub.add_parser("prepared-state")
    prepared_parser.add_argument("profile", type=Path)
    prepared_parser.add_argument("--out", type=Path)
    evaluate_parser = sub.add_parser("evaluate")
    evaluate_parser.add_argument("profile", type=Path)
    evaluate_parser.add_argument("state", type=Path)
    evaluate_parser.add_argument("--out", type=Path)
    compile_parser = sub.add_parser("compile-card")
    compile_parser.add_argument("profile", type=Path)
    compile_parser.add_argument("state", type=Path)
    compile_parser.add_argument("--out", type=Path)
    build_parser = sub.add_parser("build-carrier")
    build_parser.add_argument("profile", type=Path)
    build_parser.add_argument("--out", type=Path, required=True)
    verify_parser = sub.add_parser("verify-carrier")
    verify_parser.add_argument("carrier", type=Path)
    verify_parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate-profile":
            profile = validate_profile(args.profile)
            emit({"status": "PASS", "profileId": profile["profileId"], "profileCanonicalSha256": PROFILE_CANONICAL_SHA256, "authority": "none"})
            return 0
        if args.command == "prepared-state":
            profile = validate_profile(args.profile)
            emit(prepared_state(profile), args.out, pretty=True)
            return 0
        if args.command == "evaluate":
            profile = validate_profile(args.profile)
            decision = evaluate_preparation(profile, read_object(args.state))
            emit(decision, args.out, pretty=True)
            return 0 if decision["terminal"] != "REFUSED" else 2
        if args.command == "compile-card":
            profile = validate_profile(args.profile)
            state = validate_state(read_object(args.state), profile)
            compiled = attach_compiled_card(profile, state)
            emit(compiled, args.out, pretty=True)
            return 0
        if args.command == "build-carrier":
            manifest = build_carrier(profile_path=args.profile, out=args.out)
            emit({"status": "PASS", "carrierId": manifest["carrierId"], "terminal": manifest["terminal"], "authority": "none"})
            return 0
        if args.command == "verify-carrier":
            return run_bootstrap(args.carrier, args.out)
        fail("COMMAND_INVALID", f"unknown command: {args.command}")
    except JoinError as exc:
        emit(
            {
                "status": "REFUSED",
                "code": exc.code,
                "message": str(exc),
                "physicalAuthorizationProduced": False,
                "physicalExecutionStarted": False,
                "workersLaunched": 0,
                "listenersCreated": 0,
                "authority": "none",
            }
        )
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
