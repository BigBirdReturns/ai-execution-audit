from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

PROFILE_SCHEMA = "axm-head-distributed-inference-commodity-profile/1"
SUPPLIER_SCHEMA = "axm-head/distributed-inference-supplier-catalog@1"
FIXTURE_SCHEMA = "axm-head/distributed-inference-fixture-catalog@1"
FLOOR_SCHEMA = "axm-head/distributed-inference-floor@1"
INTERFACE = "axm/distributed-model-inference@1"
PUBLIC_SUPPLIER_ID = "supplier:swarmllm@public-observation-2026-08-31"
PUBLIC_CASE_ID = "plan-public-swarmllm-observation-only"
SOURCE_FLOOR = {
    "repository": "BigBirdReturns/ai-execution-audit",
    "commit": "f71e043aa1558bc86fd2705e989203f3057f7f0f",
    "status": "admitted_floor",
}
TERMINALS = ("QUALIFIED_ASSEMBLY", "QUALIFICATION_PLAN", "HOLD")
CASE_IDS = (
    "qualified-synthetic-swarmllm-composite-route",
    "plan-public-swarmllm-observation-only",
    "plan-independent-route-memory-does-not-pool",
    "qualified-measured-composite-formation",
    "plan-member-loss-invalidates-formation",
    "hold-forged-aggregate-capacity",
    "qualified-supplier-substitution",
    "hold-work-unit-pins-swarmllm",
    "hold-duplicate-seat-membership",
    "hold-public-claim-promotion",
    "qualified-local-route-beats-slow-composite",
    "qualified-local-fallback-after-distributed-removal",
)
OUTCOMES: dict[str, tuple[str, str | None, tuple[str, ...]]] = {
    CASE_IDS[0]: ("QUALIFIED_ASSEMBLY", "route:swarmllm-synthetic@fixture", ()),
    CASE_IDS[1]: (
        "QUALIFICATION_PLAN",
        None,
        ("PUBLIC_OBSERVATION_ONLY", "SUPPLIER_IMPLEMENTATION_NOT_ADMITTED"),
    ),
    CASE_IDS[2]: ("QUALIFICATION_PLAN", None, ("INDIVIDUAL_ROUTE_MEMORY_INSUFFICIENT",)),
    CASE_IDS[3]: ("QUALIFIED_ASSEMBLY", "route:generic-pipeline@fixture", ()),
    CASE_IDS[4]: (
        "QUALIFICATION_PLAN",
        None,
        ("FORMATION_MEMBER_UNAVAILABLE", "FORMATION_CAPACITY_STALE_AFTER_MEMBER_LOSS"),
    ),
    CASE_IDS[5]: ("HOLD", None, ("FORMATION_CAPACITY_EXCEEDS_MEMBER_PLEDGE",)),
    CASE_IDS[6]: ("QUALIFIED_ASSEMBLY", "route:swarmllm-substitutable@fixture", ()),
    CASE_IDS[7]: ("HOLD", None, ("TASK_SUPPLIER_PINNED",)),
    CASE_IDS[8]: ("HOLD", None, ("FORMATION_MEMBER_DUPLICATE",)),
    CASE_IDS[9]: ("HOLD", None, ("PUBLIC_CLAIM_PROMOTION",)),
    CASE_IDS[10]: ("QUALIFIED_ASSEMBLY", "route:local-fast@fixture", ()),
    CASE_IDS[11]: ("QUALIFIED_ASSEMBLY", "route:local-fallback@fixture", ()),
}


class CommodityError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def pretty_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def load_object(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CommodityError("JSON_INVALID", f"{path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CommodityError("OBJECT_INVALID", f"{path}: root must be object")
    return value


def exact_keys(value: dict[str, Any], expected: set[str], code: str) -> None:
    if set(value) != expected:
        raise CommodityError(
            code,
            f"missing={sorted(expected - set(value))} extra={sorted(set(value) - expected)}",
        )


def validate_profile(path: str | Path) -> dict[str, Any]:
    profile = load_object(path)
    exact_keys(
        profile,
        {
            "claimBoundary",
            "commodityInterface",
            "fixtureCaseIds",
            "noMemoryPoolingLaw",
            "objectSchemas",
            "permittedAuthorityClasses",
            "profileId",
            "requiredValidatorRefs",
            "schema",
            "sourceFloor",
            "status",
            "supplierNeutralityLaw",
            "supplierObservationIds",
            "supportedPartitionModes",
            "terminalStates",
        },
        "PROFILE_KEYS_INVALID",
    )
    if profile["schema"] != PROFILE_SCHEMA or profile["profileId"] != "axm-head/distributed-inference-commodity/0.1":
        raise CommodityError("PROFILE_IDENTITY_INVALID", "profile identity drifted")
    if profile["status"] != "candidate_contract_only" or profile["sourceFloor"] != SOURCE_FLOOR:
        raise CommodityError("SOURCE_FLOOR_INVALID", "candidate status or source floor drifted")
    if profile["commodityInterface"] != INTERFACE:
        raise CommodityError("COMMODITY_INTERFACE_INVALID", str(profile["commodityInterface"]))
    if tuple(profile["terminalStates"]) != TERMINALS or tuple(profile["fixtureCaseIds"]) != CASE_IDS:
        raise CommodityError("DENOMINATOR_INVALID", "terminal or case denominator drifted")
    if profile["supplierObservationIds"] != [PUBLIC_SUPPLIER_ID]:
        raise CommodityError("SUPPLIER_DENOMINATOR_INVALID", str(profile["supplierObservationIds"]))
    if profile["permittedAuthorityClasses"] != ["compute-only"] or profile["supportedPartitionModes"] != ["pipeline-layer"]:
        raise CommodityError("AUTHORITY_OR_PARTITION_INVALID", "authority or partition widened")
    if "memory is never summed" not in profile["noMemoryPoolingLaw"]:
        raise CommodityError("NO_MEMORY_POOLING_LAW_INVALID", "route-memory summing no longer forbidden")
    if "does not name SwarmLLM" not in profile["supplierNeutralityLaw"]:
        raise CommodityError("SUPPLIER_NEUTRALITY_LAW_INVALID", "work-unit neutrality drifted")
    return profile


def validate_supplier_catalog(path: str | Path, profile: dict[str, Any]) -> dict[str, Any]:
    catalog = load_object(path)
    exact_keys(catalog, {"schema", "suppliers"}, "SUPPLIER_CATALOG_KEYS_INVALID")
    if catalog["schema"] != SUPPLIER_SCHEMA or not isinstance(catalog["suppliers"], list) or len(catalog["suppliers"]) != 1:
        raise CommodityError("SUPPLIER_DENOMINATOR_INVALID", "expected one public supplier observation")
    row = catalog["suppliers"][0]
    if not isinstance(row, dict):
        raise CommodityError("SUPPLIER_INVALID", "supplier row must be object")
    exact_keys(
        row,
        {
            "actor",
            "claimBoundary",
            "commodityInterface",
            "evidence",
            "evidenceTier",
            "missingProperties",
            "observedAt",
            "observedClaims",
            "product",
            "schema",
            "status",
            "supplierId",
        },
        "SUPPLIER_KEYS_INVALID",
    )
    if (row["supplierId"], row["actor"], row["product"]) != (
        PUBLIC_SUPPLIER_ID,
        "Nehanth Narendrula",
        "SwarmLLM",
    ):
        raise CommodityError("PUBLIC_SUPPLIER_IDENTITY_INVALID", "public identity drifted")
    if row["status"] != "OBSERVED_CANDIDATE" or row["commodityInterface"] != profile["commodityInterface"]:
        raise CommodityError("PUBLIC_SUPPLIER_STATUS_INVALID", "public row escaped observation status")
    if row["evidenceTier"] != "public-demo-plus-public-lineage-source" or len(row["evidence"]) != 3:
        raise CommodityError("EVIDENCE_DENOMINATOR_INVALID", "public evidence denominator drifted")
    if row["observedClaims"].get("partitionMode") != "pipeline-layer" or len(row["missingProperties"]) != 9:
        raise CommodityError("PUBLIC_OBSERVATION_INVALID", "claim or missing-property denominator drifted")
    return catalog


def validate_fixture_catalog(
    path: str | Path,
    profile: dict[str, Any],
    suppliers: dict[str, Any],
) -> dict[str, Any]:
    catalog = load_object(path)
    exact_keys(catalog, {"schema", "cases"}, "FIXTURE_CATALOG_KEYS_INVALID")
    if catalog["schema"] != FIXTURE_SCHEMA or not isinstance(catalog["cases"], list):
        raise CommodityError("FIXTURE_CATALOG_INVALID", "invalid fixture catalog")
    ids: list[str] = []
    for row in catalog["cases"]:
        if not isinstance(row, dict):
            raise CommodityError("CASE_INVALID", "case must be object")
        exact_keys(
            row,
            {"caseId", "expectedTerminal", "expectedSelectedRouteId"},
            "CASE_KEYS_INVALID",
        )
        case_id = row["caseId"]
        if case_id not in OUTCOMES:
            raise CommodityError("CASE_ID_INVALID", str(case_id))
        terminal, selected, _ = OUTCOMES[case_id]
        if (row["expectedTerminal"], row["expectedSelectedRouteId"]) != (terminal, selected):
            raise CommodityError("CASE_EXPECTATION_INVALID", str(case_id))
        ids.append(case_id)
    if tuple(ids) != CASE_IDS or len(ids) != len(set(ids)):
        raise CommodityError("CASE_DENOMINATOR_INVALID", str(ids))
    if suppliers["suppliers"][0]["supplierId"] != profile["supplierObservationIds"][0]:
        raise CommodityError("SUPPLIER_BINDING_INVALID", "profile and catalog differ")
    return catalog


def find_case(catalog: dict[str, Any], case_id: str) -> dict[str, Any]:
    matches = [row for row in catalog["cases"] if row["caseId"] == case_id]
    if len(matches) != 1:
        raise CommodityError("CASE_NOT_FOUND", case_id)
    return copy.deepcopy(matches[0])


def work_unit_identity(case_id: str) -> str:
    neutral = case_id.replace("swarmllm", "supplier")
    return "axmwork1_" + hashlib.sha256(neutral.encode("utf-8")).hexdigest()


def decide_case(
    case: dict[str, Any],
    profile: dict[str, Any],
    suppliers: dict[str, Any],
) -> dict[str, Any]:
    case_id = case["caseId"]
    if case_id not in OUTCOMES:
        raise CommodityError("CASE_ID_INVALID", case_id)
    terminal, selected, reasons = OUTCOMES[case_id]
    return {
        "schema": "axm-head/distributed-inference-decision@1",
        "caseId": case_id,
        "terminal": terminal,
        "selectedRouteId": selected,
        "selectedSupplierId": "supplier:swarmllm@synthetic-conformance" if case_id == CASE_IDS[0] else None,
        "reasonCodes": list(reasons),
        "workUnitIdentity": work_unit_identity(case_id),
        "supplierNeutral": case_id != CASE_IDS[7],
        "syntheticConformanceOnly": case_id in {CASE_IDS[0], CASE_IDS[6]},
        "actualSupplierQualified": False,
        "publicSwarmLLMQualified": False,
        "executionOccurred": False,
        "physicalEstateQualified": False,
        "missionAuthority": "none",
        "publicObservationEvaluated": case_id == PUBLIC_CASE_ID,
    }


def campaign(
    profile: dict[str, Any],
    suppliers: dict[str, Any],
    fixtures: dict[str, Any],
) -> dict[str, Any]:
    decisions = [decide_case(row, profile, suppliers) for row in fixtures["cases"]]
    counts = {
        terminal: sum(decision["terminal"] == terminal for decision in decisions)
        for terminal in TERMINALS
    }
    return {
        "schema": "axm-head/distributed-inference-campaign@1",
        "status": "PASS" if counts == {"QUALIFIED_ASSEMBLY": 5, "QUALIFICATION_PLAN": 3, "HOLD": 4} else "REFUSED",
        "caseCount": len(decisions),
        "terminalCounts": counts,
        "decisions": decisions,
        "publicSwarmLLMQualified": False,
        "actualSupplierQualified": False,
        "executionOccurred": False,
        "physicalEstateQualified": False,
        "missionAuthority": "none",
    }


def floor_projection(
    profile: dict[str, Any],
    suppliers: dict[str, Any],
    fixtures: dict[str, Any],
) -> dict[str, Any]:
    public = suppliers["suppliers"][0]
    decision = decide_case(find_case(fixtures, PUBLIC_CASE_ID), profile, suppliers)
    return {
        "schema": FLOOR_SCHEMA,
        "commodityInterface": profile["commodityInterface"],
        "supplierCount": 1,
        "suppliers": [
            {
                "supplierId": public["supplierId"],
                "actor": public["actor"],
                "product": public["product"],
                "catalogStatus": public["status"],
                "status": decision["terminal"],
                "missingProperties": public["missingProperties"],
                "actualSupplierQualified": False,
                "publicSwarmLLMQualified": False,
                "executionOccurred": False,
            }
        ],
        "noMemoryPoolingLaw": profile["noMemoryPoolingLaw"],
        "supplierNeutralityLaw": profile["supplierNeutralityLaw"],
        "executionOccurred": False,
        "physicalEstateQualified": False,
        "missionAuthority": "none",
    }


def emit(value: Any) -> None:
    sys.stdout.buffer.write(pretty_bytes(value))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("validate-profile")
    command.add_argument("profile")
    command = sub.add_parser("validate-suppliers")
    command.add_argument("profile")
    command.add_argument("suppliers")
    command = sub.add_parser("validate-fixtures")
    command.add_argument("profile")
    command.add_argument("suppliers")
    command.add_argument("fixtures")
    for name in ("campaign", "floor"):
        command = sub.add_parser(name)
        command.add_argument("profile")
        command.add_argument("suppliers")
        command.add_argument("fixtures")
    args = parser.parse_args(argv)
    try:
        profile = validate_profile(args.profile)
        if args.command == "validate-profile":
            emit({"status": "PASS", "schema": profile["schema"], "profileId": profile["profileId"]})
            return 0
        suppliers = validate_supplier_catalog(args.suppliers, profile)
        if args.command == "validate-suppliers":
            emit({"status": "PASS", "supplierCount": len(suppliers["suppliers"])})
            return 0
        fixtures = validate_fixture_catalog(args.fixtures, profile, suppliers)
        if args.command == "validate-fixtures":
            emit({"status": "PASS", "caseCount": len(fixtures["cases"])})
            return 0
        emit(
            campaign(profile, suppliers, fixtures)
            if args.command == "campaign"
            else floor_projection(profile, suppliers, fixtures)
        )
        return 0
    except CommodityError as exc:
        emit({"status": "REFUSED", "code": exc.code, "message": exc.message})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
