from __future__ import annotations

import argparse
import copy
import hashlib
import hmac
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

PROFILE_SCHEMA = "axm-head/physical-long-haul-profile@2"
PROFILE_ID = "axm-head/physical-long-haul-join@2"
FIXTURE_SCHEMA = "axm-head/physical-long-haul-fixture-catalog@2"
INPUT_SCHEMA = "axm-head/physical-long-haul-input@2"
SOURCE_SCHEMA = "axm-head/physical-flight-source-binding@2"
ROUTE_SCHEMA = "axm-head/physical-route-attestation@2"
CONTINUITY_SCHEMA = "axm-head/continuity-attestation@2"
TWO_CELL_SCHEMA = "axm-head/two-cell-attestation@2"
SUCCESSOR_SCHEMA = "axm-head/successor-attestation@2"
DISPOSITION_SCHEMA = "axm-head/private-flight-disposition-binding@2"
JOIN_SCHEMA = "axm-head/physical-long-haul-join@2"
VERIFICATION_SCHEMA = "axm-head/physical-long-haul-verification@2"
PUBLIC_SCHEMA = "axm-head/physical-long-haul-public-status@2"
MANIFEST_SCHEMA = "axm-head/physical-long-haul-manifest@2"
AUTH_SCHEMA = "axm-head/named-human-physical-authorization@2"
STAGE_SCHEMA = "stc-mary/private-flight-stage-receipt@2"
AUTHENTICATION_SCHEMA = "stc-mary/private-receipt-authentication@1"
AUTH_ALGORITHM = "hmac-sha256"

TERMINALS = ("PREPARED_NOT_ARMED", "PRIVATE_SELF_ATTESTED", "HOLD")
STAGES = (
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
STAGE_TERMINALS = {
    stage: ("HUMAN_REQUIRED" if stage == "RESTORE_LINK_HOLD_CONFLICT" else "PASS")
    for stage in STAGES
}
PHASES = (
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
STOP_CONDITIONS = (
    "source_coordinate_drift",
    "dirty_or_moving_checkout",
    "private_coordinate_mismatch",
    "unexpected_worker_or_listener",
    "authorization_field_present",
    "authority_not_none",
    "receipt_refusal",
    "physical_action_before_separate_authorization",
)
DEPENDENCIES_ABSENT = (
    "AWS",
    "Lattice",
    "WAN",
    "original_host",
    "remote_model_provider",
    "repository_history",
)
PUBLIC_SOURCES = {
    "axmRemovableVolumeSupplier": {
        "repository": "BigBirdReturns/ai-execution-audit",
        "commit": "b452bb32e26249deab90db124f157bc62ad0850d",
        "tree": "c557bddc17ad62f6ad36bac5a6ef57338429a951",
        "role": "admitted_synthetic_contract",
    },
    "stcMaryConductor": {
        "repository": "BigBirdReturns/ai-execution-audit",
        "commit": "772ce582e1b19b7a2060c50be8ebf40c1f8723b2",
        "tree": "3f708c52782784e687cf1f0b68fd7d37a507ef4c",
        "role": "admitted_operator_layer",
    },
    "physicalFlightExecutionFloor": {
        "repository": "BigBirdReturns/ai-execution-audit",
        "commit": "d31e59f5fd30e57b1917c00832b189ee2ea3e12f",
        "tree": "2a6a155e9615eb847781f87566bac32d4c9dc126",
        "role": "admitted_not_executed",
    },
    "preflightReviewCard": {
        "repository": "BigBirdReturns/ai-execution-audit",
        "commit": "ec61bc3488cb5ae06ed9db2862a9f6910d310a79",
        "tree": "d2daba1d32a8de744b8b90f6cd42f7c4bff4fa67",
        "role": "admitted_preflight_law",
    },
}
SOURCE_DIGESTS = {
    "axmProfileCanonicalSha256": "c6529dbe52c678f8ae7ede650b706b1de22f10f6444dd99a5720e41b03cf7078",
    "axmFixtureCatalogCanonicalSha256": "82e4bf7e8d18fae61a1e17d1cf758d46004d08dd4b877f933be5c96663b67291",
    "axmStandaloneVerifierSha256": "8ca6d225fc162e78fb1af41c9cd89c188491a08fe71a69b58c6c12cd9acf4e44",
    "axmExternalBootstrapSha256": "885a2de66ac339d410bfebed97967fd863e3b7ad77ff3f0e9823ce6c94497d76",
    "physicalFlightProfileCanonicalSha256": "3b987b9288083f52d30ba6fc5598b190169d1b30c1860556b302c7461df246b7",
    "privatePacketProfileCanonicalSha256": "9208b6c28556ee2ba04a1bfdbc792dba457891fa9a8394aa80913a8e66dcd65c",
    "preflightProfileCanonicalSha256": "c0ef16ec7d7fbea70d59618d2a7c59cec42178c61cfeb564c839969e40ce2f56",
    "preflightStandaloneVerifierSha256": "c483507c0246fdcc502e21f60937f0ff81df020871120ab56abd619131ef49d2",
}
ISSUE = {
    "repository": "BigBirdReturns/ai-execution-audit",
    "issueNumber": 37,
    "role": "sole_private_physical_flight_execution_coordinate",
}
PREFLIGHT = {
    "profileId": "axm-head/physical-flight-preflight-review-card@1",
    "profileCanonicalSha256": SOURCE_DIGESTS["preflightProfileCanonicalSha256"],
    "standaloneVerifierSha256": SOURCE_DIGESTS["preflightStandaloneVerifierSha256"],
    "carrierId": "axmheadpreflightcarrier1_decd7e3c9158f25602eeafc4544f09f7570d726ebb9a7758b36a050441338772",
    "terminal": "READY_FOR_HUMAN_REVIEW",
    "reviewCardActionCount": 12,
    "authorizedActionCount": 0,
    "phaseSequence": list(PHASES),
    "packetStageSequence": list(STAGES),
    "stopConditions": list(STOP_CONDITIONS),
    "physicalAuthorizationProduced": False,
    "privateEvidenceBodies": 0,
    "authority": "none",
}
STRONGER_CLAIMS = {
    "physicalEstateQualified": False,
    "representativeOperatorQualified": False,
    "fieldNetworkQualified": False,
    "operationalC2Qualified": False,
    "productionLatticeQualified": False,
    "missionAuthorityGranted": False,
    "commandAuthorityGranted": False,
    "targetingEngagementEffectorOrWeaponsCapability": False,
}
CLAIM_BOUNDARY = (
    "Provider-free postflight verification membrane for one private STC MARY "
    "physical-flight self-attestation. It binds exact admitted public sources to "
    "allowlisted body-free private receipts authenticated by a separately held "
    "campaign trust root, derives route, continuity, two-cell, successor, "
    "sealed-package, and authorization-order predicates, and may emit "
    "PRIVATE_SELF_ATTESTED only for one complete private_local_attested proof "
    "chain. It does not launch, authorize, or execute a physical campaign, "
    "publish a private body, qualify a representative operator, field network, "
    "operational C2 system, production Lattice integration, or grant mission, "
    "command, targeting, engagement, effector, or weapons authority."
)
OBJECT_SCHEMAS = (
    PROFILE_SCHEMA,
    SOURCE_SCHEMA,
    ROUTE_SCHEMA,
    CONTINUITY_SCHEMA,
    TWO_CELL_SCHEMA,
    SUCCESSOR_SCHEMA,
    DISPOSITION_SCHEMA,
    JOIN_SCHEMA,
    VERIFICATION_SCHEMA,
    PUBLIC_SCHEMA,
)
EXPECTED_MEMBER_PATHS = (
    "JOIN/source-binding.json",
    "JOIN/route-attestation.json",
    "JOIN/continuity-attestation.json",
    "JOIN/two-cell-attestation.json",
    "JOIN/successor-attestation.json",
    "JOIN/private-disposition-binding.json",
    "JOIN/join.json",
    "PUBLIC/status.json",
    "RECOVERY/profile.json",
    "RECOVERY/fixture-catalog.json",
    "RECOVERY/verify_join.py",
)
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SHA256_REF = re.compile(r"^sha256:[0-9a-f]{64}$")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{2,255}$")
PRIVATE_PATTERNS = (
    re.compile(r"[A-Za-z]:\\"),
    re.compile(r"\\\\[^\\]+\\"),
    re.compile(r"/(?:home|Users|mnt|tmp|var|private)/", re.I),
    re.compile(r"(?:https?|ssh|tcp|udp)://", re.I),
    re.compile(r"\b(?:localhost|OCTO-[A-Z0-9-]+)\b", re.I),
    re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b"),
    re.compile(r"\b[a-z0-9][a-z0-9-]{0,62}(?:\.[a-z0-9][a-z0-9-]{0,62})+\b", re.I),
    re.compile(
        r"AKIA[0-9A-Z]{16}|BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY|"
        r"Authorization:\s*Bearer|(?:password|secret|token|api[_-]?key)\s*[:=]",
        re.I,
    ),
)


class JoinError(RuntimeError):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


def fail(code: str, message: str = "") -> None:
    raise JoinError(code, message)


def canonical_json_bytes(value: Any) -> bytes:
    try:
        return (
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        fail("NON_CANONICAL_JSON", str(exc))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_ref(data: bytes) -> str:
    return "sha256:" + sha256_bytes(data)


def content_id(prefix: str, body: dict[str, Any]) -> str:
    return f"{prefix}_{sha256_bytes(canonical_json_bytes(body))}"


def strict_equal(actual: Any, expected: Any) -> bool:
    return canonical_json_bytes(actual) == canonical_json_bytes(expected)


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail("JSON_READ_FAILED", str(exc))
    if type(value) is not dict:
        fail("JSON_OBJECT_REQUIRED")
    return value


def require_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        fail(
            "OBJECT_KEYS_INVALID",
            f"{label} missing={sorted(expected - actual)} unknown={sorted(actual - expected)}",
        )


def require_bool(value: Any, label: str) -> bool:
    if type(value) is not bool:
        fail("BOOLEAN_REQUIRED", label)
    return value


def require_int(value: Any, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        fail("INTEGER_REQUIRED", label)
    return value


def require_string(
    value: Any,
    label: str,
    pattern: re.Pattern[str] | None = None,
    max_len: int = 1024,
) -> str:
    if type(value) is not str or not value or len(value) > max_len:
        fail("STRING_REQUIRED", label)
    if pattern is not None and pattern.fullmatch(value) is None:
        fail("STRING_PATTERN_INVALID", label)
    return value


def scan_private(value: Any, label: str = "input") -> None:
    if type(value) is dict:
        if len(value) > 128:
            fail("OBJECT_BOUND_EXCEEDED", label)
        for key, child in value.items():
            scan_private(child, f"{label}.{key}")
    elif type(value) is list:
        if len(value) > 256:
            fail("ARRAY_BOUND_EXCEEDED", label)
        for index, child in enumerate(value):
            scan_private(child, f"{label}[{index}]")
    elif type(value) is str:
        if len(value) > 2048:
            fail("STRING_BOUND_EXCEEDED", label)
        for pattern in PRIVATE_PATTERNS:
            if pattern.search(value):
                fail("PRIVATE_MATERIAL_REFUSED", label)


def load_trust_root(path: Path | None) -> tuple[bytes, str] | None:
    if path is None:
        return None
    try:
        resolved = path.resolve(strict=True)
        if path.is_symlink() or not resolved.is_file():
            fail("TRUST_ROOT_FILE_REQUIRED")
        data = resolved.read_bytes()
    except OSError as exc:
        fail("TRUST_ROOT_READ_FAILED", str(exc))
    if len(data) < 32 or len(data) > 4096:
        fail("TRUST_ROOT_SIZE_INVALID")
    return data, sha256_ref(data)


def unsigned_body(record: dict[str, Any]) -> dict[str, Any]:
    return {key: copy.deepcopy(value) for key, value in record.items() if key not in {"receiptId", "authentication"}}


def receipt_id(prefix: str, record: dict[str, Any]) -> str:
    return content_id(prefix, unsigned_body(record))


def authentication_value(
    secret: bytes,
    key_id: str,
    context: str,
    record_id: str,
    record: dict[str, Any],
) -> dict[str, Any]:
    payload_digest = sha256_ref(canonical_json_bytes(unsigned_body(record)))
    envelope = {
        "context": context,
        "receiptId": record_id,
        "payloadSha256": payload_digest,
    }
    mac = hmac.new(secret, canonical_json_bytes(envelope), hashlib.sha256).hexdigest()
    return {
        "schema": AUTHENTICATION_SCHEMA,
        "algorithm": AUTH_ALGORITHM,
        "keyId": key_id,
        "mac": "sha256:" + mac,
    }


def sign_record(
    record: dict[str, Any],
    prefix: str,
    context: str,
    secret: bytes,
    key_id: str,
) -> dict[str, Any]:
    result = copy.deepcopy(record)
    result["trustRootSha256"] = key_id
    result["receiptId"] = receipt_id(prefix, result)
    result["authentication"] = authentication_value(
        secret, key_id, context, result["receiptId"], result
    )
    return result


def validate_authentication_shape(value: Any, label: str) -> None:
    if type(value) is not dict:
        fail("AUTHENTICATION_OBJECT_REQUIRED", label)
    require_keys(value, {"schema", "algorithm", "keyId", "mac"}, label)
    if value["schema"] != AUTHENTICATION_SCHEMA or value["algorithm"] != AUTH_ALGORITHM:
        fail("AUTHENTICATION_SCHEMA_INVALID", label)
    require_string(value["keyId"], label + ".keyId", SHA256_REF)
    require_string(value["mac"], label + ".mac", SHA256_REF)


def verify_record(
    record: dict[str, Any],
    prefix: str,
    context: str,
    trust: tuple[bytes, str] | None,
    label: str,
) -> bool:
    claimed_id = record.get("receiptId")
    authentication = record.get("authentication")
    if claimed_id is None and authentication is None:
        return False
    require_string(claimed_id, label + ".receiptId", ID_RE)
    validate_authentication_shape(authentication, label + ".authentication")
    expected_id = receipt_id(prefix, record)
    if claimed_id != expected_id:
        fail("RECEIPT_ID_INVALID", label)
    if trust is None:
        fail("TRUST_ROOT_REQUIRED", label)
    secret, key_id = trust
    if record.get("trustRootSha256") != key_id or authentication["keyId"] != key_id:
        fail("TRUST_ROOT_MISMATCH", label)
    expected = authentication_value(secret, key_id, context, claimed_id, record)
    if not hmac.compare_digest(
        canonical_json_bytes(authentication), canonical_json_bytes(expected)
    ):
        fail("RECEIPT_AUTHENTICATION_INVALID", label)
    return True


def derive_proof_root(
    campaign_id: str,
    key_id: str,
    authorization_receipt_id: str,
    stage_receipt_ids: list[str],
) -> str:
    return sha256_ref(
        canonical_json_bytes(
            {
                "campaignId": campaign_id,
                "trustRootSha256": key_id,
                "authorizationReceiptId": authorization_receipt_id,
                "stageReceiptIds": stage_receipt_ids,
            }
        )
    )


def validate_profile_object(profile: dict[str, Any]) -> dict[str, Any]:
    require_keys(
        profile,
        {
            "schema",
            "profileId",
            "version",
            "status",
            "owningProject",
            "owningRepository",
            "publicSources",
            "sourceDigests",
            "physicalFlightIssue",
            "preflightLaw",
            "objectSchemas",
            "terminalStates",
            "packetStageSequence",
            "requiredStageTerminals",
            "dependenciesAbsent",
            "bootstrapRequired",
            "privateTrustRootRequiredForPromotion",
            "receiptAuthenticationAlgorithm",
            "repositoryOutputAllowed",
            "networkRequired",
            "externalServiceCalls",
            "operationalCredentials",
            "privateEvidenceBodiesPublic",
            "workersLaunched",
            "listenersCreated",
            "authority",
            "strongerClaims",
            "claimBoundary",
            "fixtureCatalogCanonicalSha256",
            "standaloneVerifierSha256",
        },
        "profile",
    )
    if (
        profile["schema"] != PROFILE_SCHEMA
        or profile["profileId"] != PROFILE_ID
        or profile["version"] != 2
    ):
        fail("PROFILE_IDENTITY_INVALID")
    if (
        profile["status"] != "candidate_contract_only"
        or profile["owningProject"] != "Estate"
        or profile["owningRepository"] != "BigBirdReturns/ai-execution-audit"
    ):
        fail("PROFILE_SCOPE_INVALID")
    if not strict_equal(profile["publicSources"], PUBLIC_SOURCES):
        fail("SOURCE_COORDINATES_INVALID")
    if not strict_equal(profile["sourceDigests"], SOURCE_DIGESTS):
        fail("SOURCE_DIGESTS_INVALID")
    if not strict_equal(profile["physicalFlightIssue"], ISSUE):
        fail("PHYSICAL_FLIGHT_ISSUE_INVALID")
    if not strict_equal(profile["preflightLaw"], PREFLIGHT):
        fail("PREFLIGHT_LAW_INVALID")
    if profile["objectSchemas"] != list(OBJECT_SCHEMAS):
        fail("OBJECT_DENOMINATOR_INVALID")
    if profile["terminalStates"] != list(TERMINALS):
        fail("TERMINAL_DENOMINATOR_INVALID")
    if profile["packetStageSequence"] != list(STAGES):
        fail("STAGE_DENOMINATOR_INVALID")
    if not strict_equal(profile["requiredStageTerminals"], STAGE_TERMINALS):
        fail("STAGE_TERMINALS_INVALID")
    if profile["dependenciesAbsent"] != list(DEPENDENCIES_ABSENT):
        fail("DEPENDENCY_DENOMINATOR_INVALID")
    if (
        profile["bootstrapRequired"] is not True
        or profile["privateTrustRootRequiredForPromotion"] is not True
        or profile["receiptAuthenticationAlgorithm"] != AUTH_ALGORITHM
        or profile["repositoryOutputAllowed"] is not False
        or profile["networkRequired"] is not False
    ):
        fail("PROFILE_CUSTODY_INVALID")
    expected = {
        "externalServiceCalls": 0,
        "operationalCredentials": 0,
        "privateEvidenceBodiesPublic": 0,
        "workersLaunched": 0,
        "listenersCreated": 0,
        "authority": "none",
        "strongerClaims": STRONGER_CLAIMS,
        "claimBoundary": CLAIM_BOUNDARY,
    }
    for key, wanted in expected.items():
        if not strict_equal(profile[key], wanted):
            fail("PROFILE_NONCLAIM_INVALID", key)
    require_string(
        profile["fixtureCatalogCanonicalSha256"],
        "fixtureCatalogCanonicalSha256",
        HEX64,
    )
    require_string(
        profile["standaloneVerifierSha256"],
        "standaloneVerifierSha256",
        HEX64,
    )
    return profile


def validate_catalog_object(
    profile: dict[str, Any], catalog: dict[str, Any]
) -> dict[str, Any]:
    require_keys(catalog, {"schema", "profileId", "cases"}, "catalog")
    if catalog["schema"] != FIXTURE_SCHEMA or catalog["profileId"] != PROFILE_ID:
        fail("FIXTURE_IDENTITY_INVALID")
    if type(catalog["cases"]) is not list or len(catalog["cases"]) != 4:
        fail("FIXTURE_DENOMINATOR_INVALID")
    case_ids: list[str] = []
    for index, row in enumerate(catalog["cases"]):
        if type(row) is not dict:
            fail("FIXTURE_CASE_OBJECT_REQUIRED", str(index))
        require_keys(row, {"caseId", "expectedTerminal", "input"}, f"case[{index}]")
        case_ids.append(require_string(row["caseId"], "caseId", ID_RE))
        if row["expectedTerminal"] not in {"PREPARED_NOT_ARMED", "HOLD"}:
            fail("FIXTURE_PHYSICAL_PROMOTION_REFUSED", row["caseId"])
        validate_input_shape(row["input"], trust=None, allow_synthetic=True)
        if contains_private_tier(row["input"]):
            fail("FIXTURE_PRIVATE_TIER_REFUSED", row["caseId"])
    if len(case_ids) != len(set(case_ids)):
        fail("FIXTURE_CASE_DUPLICATE")
    if sha256_bytes(canonical_json_bytes(catalog)) != profile["fixtureCatalogCanonicalSha256"]:
        fail("FIXTURE_CATALOG_DIGEST_INVALID")
    return catalog


def contains_private_tier(value: Any) -> bool:
    if type(value) is dict:
        return any(
            (key == "evidenceTier" and child == "private_local_attested")
            or contains_private_tier(child)
            for key, child in value.items()
        )
    if type(value) is list:
        return any(contains_private_tier(child) for child in value)
    return False


def validate_source_binding(value: dict[str, Any], campaign_id: str) -> None:
    require_keys(
        value,
        {
            "schema",
            "campaignId",
            "publicSources",
            "sourceDigests",
            "physicalFlightIssue",
            "preflight",
            "sourceBindingId",
        },
        "sourceBinding",
    )
    if value["schema"] != SOURCE_SCHEMA or value["campaignId"] != campaign_id:
        fail("SOURCE_BINDING_IDENTITY_INVALID")
    if not strict_equal(value["publicSources"], PUBLIC_SOURCES):
        fail("SOURCE_BINDING_INVALID")
    if not strict_equal(value["sourceDigests"], SOURCE_DIGESTS):
        fail("SOURCE_BINDING_DIGEST_INVALID")
    if not strict_equal(value["physicalFlightIssue"], ISSUE):
        fail("SOURCE_BINDING_ISSUE_INVALID")
    if not strict_equal(value["preflight"], PREFLIGHT):
        fail("SOURCE_BINDING_PREFLIGHT_INVALID")
    expected = content_id(
        "axmheadsourcebinding2",
        {key: copy.deepcopy(child) for key, child in value.items() if key != "sourceBindingId"},
    )
    if value["sourceBindingId"] != expected:
        fail("SOURCE_BINDING_CONTENT_ID_INVALID")


def validate_auth_record(
    value: dict[str, Any],
    campaign_id: str,
    trust: tuple[bytes, str] | None,
    allow_synthetic: bool,
) -> bool:
    require_keys(
        value,
        {
            "schema",
            "campaignId",
            "present",
            "evidenceTier",
            "preflightCarrierId",
            "physicalFlightIssueNumber",
            "authorizationSequence",
            "firstPhysicalReceiptSequence",
            "namedHumanAuthorityClass",
            "terminal",
            "trustRootSha256",
            "receiptId",
            "authentication",
        },
        "authorization",
    )
    if value["schema"] != AUTH_SCHEMA or value["campaignId"] != campaign_id:
        fail("AUTHORIZATION_IDENTITY_INVALID")
    require_bool(value["present"], "authorization.present")
    require_string(value["evidenceTier"], "authorization.evidenceTier")
    if value["preflightCarrierId"] != PREFLIGHT["carrierId"]:
        fail("AUTHORIZATION_PREFLIGHT_BINDING_INVALID")
    if value["physicalFlightIssueNumber"] != ISSUE["issueNumber"]:
        fail("AUTHORIZATION_ISSUE_BINDING_INVALID")
    if not value["present"]:
        if any(
            value[key] is not None
            for key in (
                "authorizationSequence",
                "firstPhysicalReceiptSequence",
                "namedHumanAuthorityClass",
                "trustRootSha256",
                "receiptId",
                "authentication",
            )
        ) or value["terminal"] != "ABSENT":
            fail("ABSENT_AUTHORIZATION_INVALID")
        return False
    require_int(value["authorizationSequence"], "authorizationSequence")
    require_int(value["firstPhysicalReceiptSequence"], "firstPhysicalReceiptSequence", 1)
    require_string(value["namedHumanAuthorityClass"], "namedHumanAuthorityClass", ID_RE)
    if value["terminal"] != "AUTHORIZED":
        fail("AUTHORIZATION_TERMINAL_INVALID")
    if value["evidenceTier"] == "private_local_attested":
        return verify_record(
            value,
            "stcmaryauthorization2",
            "named-human-physical-authorization-v2",
            trust,
            "authorization",
        )
    if not allow_synthetic:
        fail("AUTHORIZATION_EVIDENCE_TIER_INVALID")
    if value["authentication"] is not None:
        fail("SYNTHETIC_AUTHENTICATION_REFUSED")
    return False


def validate_stage_record(
    row: dict[str, Any],
    campaign_id: str,
    index: int,
    trust: tuple[bytes, str] | None,
    allow_synthetic: bool,
) -> bool:
    require_keys(
        row,
        {
            "schema",
            "campaignId",
            "sequence",
            "stage",
            "terminal",
            "previousReceiptId",
            "evidenceTier",
            "evidenceBodyCount",
            "evidenceRootSha256",
            "canonicalMissionStateSha256",
            "trustRootSha256",
            "receiptId",
            "authentication",
        },
        f"stage[{index}]",
    )
    if row["schema"] != STAGE_SCHEMA or row["campaignId"] != campaign_id:
        fail("STAGE_IDENTITY_INVALID", str(index))
    require_int(row["sequence"], "stage.sequence", 1)
    require_string(row["stage"], "stage.stage", ID_RE)
    require_string(row["terminal"], "stage.terminal", ID_RE)
    require_string(row["previousReceiptId"], "stage.previousReceiptId", ID_RE)
    require_string(row["evidenceTier"], "stage.evidenceTier")
    require_int(row["evidenceBodyCount"], "stage.evidenceBodyCount")
    require_string(row["evidenceRootSha256"], "stage.evidenceRootSha256", SHA256_REF)
    require_string(
        row["canonicalMissionStateSha256"],
        "stage.canonicalMissionStateSha256",
        SHA256_REF,
    )
    if row["evidenceTier"] == "private_local_attested":
        return verify_record(
            row,
            "stcmarystagereceipt2",
            "private-flight-stage-receipt-v2",
            trust,
            f"stage[{index}]",
        )
    if not allow_synthetic:
        fail("STAGE_EVIDENCE_TIER_INVALID", str(index))
    if row["authentication"] is not None:
        fail("SYNTHETIC_AUTHENTICATION_REFUSED", str(index))
    return False


def validate_route_record(
    value: dict[str, Any],
    campaign_id: str,
    trust: tuple[bytes, str] | None,
    allow_synthetic: bool,
) -> bool:
    require_keys(
        value,
        {
            "schema",
            "campaignId",
            "present",
            "evidenceTier",
            "proofRootSha256",
            "memoryPoolingUsed",
            "canonicalMissionStateSha256",
            "residentRoute",
            "acceleratorRoute",
            "stageEvidenceRoots",
            "trustRootSha256",
            "receiptId",
            "authentication",
        },
        "route",
    )
    if value["schema"] != ROUTE_SCHEMA or value["campaignId"] != campaign_id:
        fail("ROUTE_IDENTITY_INVALID")
    require_bool(value["present"], "route.present")
    require_string(value["evidenceTier"], "route.evidenceTier")
    require_bool(value["memoryPoolingUsed"], "route.memoryPoolingUsed")
    if not value["present"]:
        for key in (
            "proofRootSha256",
            "canonicalMissionStateSha256",
            "residentRoute",
            "acceleratorRoute",
            "stageEvidenceRoots",
            "trustRootSha256",
            "receiptId",
            "authentication",
        ):
            if value[key] is not None:
                fail("ABSENT_ROUTE_INVALID", key)
        return False
    require_string(value["proofRootSha256"], "route.proofRootSha256", SHA256_REF)
    require_string(
        value["canonicalMissionStateSha256"],
        "route.canonicalMissionStateSha256",
        SHA256_REF,
    )
    if type(value["stageEvidenceRoots"]) is not dict:
        fail("ROUTE_STAGE_BINDINGS_REQUIRED")
    require_keys(
        value["stageEvidenceRoots"],
        {"residentBaseline", "accelerated"},
        "route.stageEvidenceRoots",
    )
    for child in value["stageEvidenceRoots"].values():
        require_string(child, "route.stageEvidenceRoot", SHA256_REF)
    for label in ("residentRoute", "acceleratorRoute"):
        row = value[label]
        if type(row) is not dict:
            fail("ROUTE_OBJECT_REQUIRED", label)
        require_keys(
            row,
            {
                "routeClass",
                "memoryMiB",
                "requiredMemoryMiB",
                "missionSha256",
                "outputSha256",
                "classificationSha256",
                "verifierSha256",
                "throughputMilliItemsPerSecond",
                "independentlyVerified",
                "measurementReceiptId",
            },
            label,
        )
        require_string(row["routeClass"], label + ".routeClass", ID_RE)
        require_int(row["memoryMiB"], label + ".memoryMiB", 1)
        require_int(row["requiredMemoryMiB"], label + ".requiredMemoryMiB", 1)
        for key in (
            "missionSha256",
            "outputSha256",
            "classificationSha256",
            "verifierSha256",
            "measurementReceiptId",
        ):
            require_string(row[key], label + "." + key, SHA256_REF)
        require_int(
            row["throughputMilliItemsPerSecond"],
            label + ".throughputMilliItemsPerSecond",
            1,
        )
        require_bool(row["independentlyVerified"], label + ".independentlyVerified")
    if value["evidenceTier"] == "private_local_attested":
        return verify_record(
            value,
            "axmheadrouteevidence2",
            "physical-route-attestation-v2",
            trust,
            "route",
        )
    if not allow_synthetic:
        fail("ROUTE_EVIDENCE_TIER_INVALID")
    if value["authentication"] is not None:
        fail("SYNTHETIC_AUTHENTICATION_REFUSED")
    return False


def validate_continuity_record(
    value: dict[str, Any],
    campaign_id: str,
    trust: tuple[bytes, str] | None,
    allow_synthetic: bool,
) -> bool:
    require_keys(
        value,
        {
            "schema",
            "campaignId",
            "present",
            "evidenceTier",
            "proofRootSha256",
            "baselineOutputSha256",
            "postRemovalOutputSha256",
            "canonicalStateBeforeSha256",
            "canonicalStateAfterSha256",
            "residentFloorAvailableAfter",
            "halo3AbsentAfter",
            "latticeAbsentDuringLocalContinuity",
            "independentlyVerified",
            "stageEvidenceRoots",
            "trustRootSha256",
            "receiptId",
            "authentication",
        },
        "continuity",
    )
    if value["schema"] != CONTINUITY_SCHEMA or value["campaignId"] != campaign_id:
        fail("CONTINUITY_IDENTITY_INVALID")
    require_bool(value["present"], "continuity.present")
    require_string(value["evidenceTier"], "continuity.evidenceTier")
    for key in (
        "residentFloorAvailableAfter",
        "halo3AbsentAfter",
        "latticeAbsentDuringLocalContinuity",
        "independentlyVerified",
    ):
        require_bool(value[key], "continuity." + key)
    if not value["present"]:
        for key in (
            "proofRootSha256",
            "baselineOutputSha256",
            "postRemovalOutputSha256",
            "canonicalStateBeforeSha256",
            "canonicalStateAfterSha256",
            "stageEvidenceRoots",
            "trustRootSha256",
            "receiptId",
            "authentication",
        ):
            if value[key] is not None:
                fail("ABSENT_CONTINUITY_INVALID", key)
        return False
    for key in (
        "proofRootSha256",
        "baselineOutputSha256",
        "postRemovalOutputSha256",
        "canonicalStateBeforeSha256",
        "canonicalStateAfterSha256",
    ):
        require_string(value[key], "continuity." + key, SHA256_REF)
    if type(value["stageEvidenceRoots"]) is not dict:
        fail("CONTINUITY_STAGE_BINDINGS_REQUIRED")
    require_keys(
        value["stageEvidenceRoots"],
        {"postRemoval", "localContinuity"},
        "continuity.stageEvidenceRoots",
    )
    for child in value["stageEvidenceRoots"].values():
        require_string(child, "continuity.stageEvidenceRoot", SHA256_REF)
    if value["evidenceTier"] == "private_local_attested":
        return verify_record(
            value,
            "axmheadcontinuityevidence2",
            "continuity-attestation-v2",
            trust,
            "continuity",
        )
    if not allow_synthetic:
        fail("CONTINUITY_EVIDENCE_TIER_INVALID")
    if value["authentication"] is not None:
        fail("SYNTHETIC_AUTHENTICATION_REFUSED")
    return False


def validate_two_cell_record(
    value: dict[str, Any],
    campaign_id: str,
    trust: tuple[bytes, str] | None,
    allow_synthetic: bool,
) -> bool:
    require_keys(
        value,
        {
            "schema",
            "campaignId",
            "present",
            "evidenceTier",
            "proofRootSha256",
            "commonParentSha256",
            "leftChildSha256",
            "rightChildSha256",
            "leftHostClassSha256",
            "rightHostClassSha256",
            "reunionTerminal",
            "automaticMergeAllowed",
            "retainedChildSha256",
            "unresolvedObligationCount",
            "independentlyVerified",
            "stageEvidenceRoots",
            "trustRootSha256",
            "receiptId",
            "authentication",
        },
        "twoCell",
    )
    if value["schema"] != TWO_CELL_SCHEMA or value["campaignId"] != campaign_id:
        fail("TWO_CELL_IDENTITY_INVALID")
    require_bool(value["present"], "twoCell.present")
    require_string(value["evidenceTier"], "twoCell.evidenceTier")
    require_bool(value["automaticMergeAllowed"], "twoCell.automaticMergeAllowed")
    require_bool(value["independentlyVerified"], "twoCell.independentlyVerified")
    require_int(value["unresolvedObligationCount"], "twoCell.unresolvedObligationCount")
    if type(value["retainedChildSha256"]) is not list:
        fail("ARRAY_REQUIRED", "retainedChildSha256")
    if not value["present"]:
        for key in (
            "proofRootSha256",
            "commonParentSha256",
            "leftChildSha256",
            "rightChildSha256",
            "leftHostClassSha256",
            "rightHostClassSha256",
            "reunionTerminal",
            "stageEvidenceRoots",
            "trustRootSha256",
            "receiptId",
            "authentication",
        ):
            if value[key] is not None:
                fail("ABSENT_TWO_CELL_INVALID", key)
        if value["retainedChildSha256"]:
            fail("ABSENT_TWO_CELL_INVALID", "retainedChildSha256")
        return False
    for key in (
        "proofRootSha256",
        "commonParentSha256",
        "leftChildSha256",
        "rightChildSha256",
        "leftHostClassSha256",
        "rightHostClassSha256",
    ):
        require_string(value[key], "twoCell." + key, SHA256_REF)
    if value["reunionTerminal"] != "HUMAN_REQUIRED":
        require_string(value["reunionTerminal"], "twoCell.reunionTerminal", ID_RE)
    if len(value["retainedChildSha256"]) != 2:
        fail("RETAINED_CHILD_DENOMINATOR_INVALID")
    for child in value["retainedChildSha256"]:
        require_string(child, "retainedChildSha256", SHA256_REF)
    if type(value["stageEvidenceRoots"]) is not dict:
        fail("TWO_CELL_STAGE_BINDINGS_REQUIRED")
    require_keys(
        value["stageEvidenceRoots"],
        {"partition", "reunion"},
        "twoCell.stageEvidenceRoots",
    )
    for child in value["stageEvidenceRoots"].values():
        require_string(child, "twoCell.stageEvidenceRoot", SHA256_REF)
    if value["evidenceTier"] == "private_local_attested":
        return verify_record(
            value,
            "axmheadtwocellevidence2",
            "two-cell-attestation-v2",
            trust,
            "twoCell",
        )
    if not allow_synthetic:
        fail("TWO_CELL_EVIDENCE_TIER_INVALID")
    if value["authentication"] is not None:
        fail("SYNTHETIC_AUTHENTICATION_REFUSED")
    return False


def validate_successor_record(
    value: dict[str, Any],
    campaign_id: str,
    trust: tuple[bytes, str] | None,
    allow_synthetic: bool,
) -> bool:
    require_keys(
        value,
        {
            "schema",
            "campaignId",
            "present",
            "evidenceTier",
            "proofRootSha256",
            "originalHeadClassSha256",
            "replacementHeadClassSha256",
            "missionId",
            "canonicalStateSha256",
            "proofStateSha256",
            "namedHumanAuthorityClass",
            "unresolvedObligationCount",
            "nextSafeActionSha256",
            "answers",
            "verificationTerminal",
            "dependenciesAbsent",
            "independentlyVerified",
            "stageEvidenceRoots",
            "trustRootSha256",
            "receiptId",
            "authentication",
        },
        "successor",
    )
    if value["schema"] != SUCCESSOR_SCHEMA or value["campaignId"] != campaign_id:
        fail("SUCCESSOR_IDENTITY_INVALID")
    require_bool(value["present"], "successor.present")
    require_string(value["evidenceTier"], "successor.evidenceTier")
    require_int(value["unresolvedObligationCount"], "successor.unresolvedObligationCount")
    require_bool(value["independentlyVerified"], "successor.independentlyVerified")
    if type(value["answers"]) is not dict or type(value["dependenciesAbsent"]) is not list:
        fail("SUCCESSOR_COLLECTION_INVALID")
    if not value["present"]:
        for key in (
            "proofRootSha256",
            "originalHeadClassSha256",
            "replacementHeadClassSha256",
            "missionId",
            "canonicalStateSha256",
            "proofStateSha256",
            "namedHumanAuthorityClass",
            "nextSafeActionSha256",
            "verificationTerminal",
            "stageEvidenceRoots",
            "trustRootSha256",
            "receiptId",
            "authentication",
        ):
            if value[key] is not None:
                fail("ABSENT_SUCCESSOR_INVALID", key)
        if value["answers"] or value["dependenciesAbsent"]:
            fail("ABSENT_SUCCESSOR_INVALID")
        return False
    for key in (
        "proofRootSha256",
        "originalHeadClassSha256",
        "replacementHeadClassSha256",
        "canonicalStateSha256",
        "proofStateSha256",
        "nextSafeActionSha256",
    ):
        require_string(value[key], "successor." + key, SHA256_REF)
    require_string(value["missionId"], "successor.missionId", ID_RE)
    require_string(
        value["namedHumanAuthorityClass"],
        "successor.namedHumanAuthorityClass",
        ID_RE,
    )
    require_string(value["verificationTerminal"], "successor.verificationTerminal", ID_RE)
    require_keys(
        value["answers"],
        {
            "whatMission",
            "currentState",
            "whoMayAct",
            "whatProvesIt",
            "whatRemainsUnresolved",
            "nextSafeAction",
        },
        "successor.answers",
    )
    for child in value["answers"].values():
        require_string(child, "successor.answer", SHA256_REF)
    if type(value["stageEvidenceRoots"]) is not dict:
        fail("SUCCESSOR_STAGE_BINDINGS_REQUIRED")
    require_keys(
        value["stageEvidenceRoots"],
        {"replaceHead", "coldSuccessor"},
        "successor.stageEvidenceRoots",
    )
    for child in value["stageEvidenceRoots"].values():
        require_string(child, "successor.stageEvidenceRoot", SHA256_REF)
    if value["evidenceTier"] == "private_local_attested":
        return verify_record(
            value,
            "axmheadsuccessorevidence2",
            "successor-attestation-v2",
            trust,
            "successor",
        )
    if not allow_synthetic:
        fail("SUCCESSOR_EVIDENCE_TIER_INVALID")
    if value["authentication"] is not None:
        fail("SYNTHETIC_AUTHENTICATION_REFUSED")
    return False


def validate_disposition_record(
    value: dict[str, Any],
    campaign_id: str,
    trust: tuple[bytes, str] | None,
    allow_synthetic: bool,
) -> tuple[bool, list[bool]]:
    require_keys(
        value,
        {
            "schema",
            "campaignId",
            "present",
            "evidenceTier",
            "proofRootSha256",
            "authorization",
            "stageReceipts",
            "componentReceiptIds",
            "sealStageEvidenceRootSha256",
            "publicEvidenceBodyCount",
            "privateEvidenceBodyCount",
            "canonicalMissionStateSha256",
            "sealedVerificationTerminal",
            "sealedPackageSha256",
            "sourceDispositionSha256",
            "privateMaterialScanTerminal",
            "privatePhysicalFlightCompleted",
            "selfAttestationOnly",
            "strongerClaims",
            "authority",
            "trustRootSha256",
            "receiptId",
            "authentication",
        },
        "privateDisposition",
    )
    if value["schema"] != DISPOSITION_SCHEMA or value["campaignId"] != campaign_id:
        fail("DISPOSITION_IDENTITY_INVALID")
    require_bool(value["present"], "privateDisposition.present")
    require_string(value["evidenceTier"], "privateDisposition.evidenceTier")
    auth_verified = validate_auth_record(
        value["authorization"], campaign_id, trust, allow_synthetic
    )
    if type(value["stageReceipts"]) is not list:
        fail("STAGE_ARRAY_REQUIRED")
    stage_verified = [
        validate_stage_record(row, campaign_id, index, trust, allow_synthetic)
        for index, row in enumerate(value["stageReceipts"])
    ]
    require_int(value["publicEvidenceBodyCount"], "publicEvidenceBodyCount")
    require_int(value["privateEvidenceBodyCount"], "privateEvidenceBodyCount")
    require_bool(value["privatePhysicalFlightCompleted"], "privatePhysicalFlightCompleted")
    require_bool(value["selfAttestationOnly"], "selfAttestationOnly")
    if not strict_equal(value["strongerClaims"], STRONGER_CLAIMS) or value["authority"] != "none":
        fail("AUTHORITY_PROMOTION_REFUSED")
    if not value["present"]:
        for key in (
            "proofRootSha256",
            "componentReceiptIds",
            "sealStageEvidenceRootSha256",
            "canonicalMissionStateSha256",
            "sealedVerificationTerminal",
            "sealedPackageSha256",
            "sourceDispositionSha256",
            "privateMaterialScanTerminal",
            "trustRootSha256",
            "receiptId",
            "authentication",
        ):
            if value[key] is not None:
                fail("ABSENT_DISPOSITION_INVALID", key)
        if value["stageReceipts"]:
            fail("ABSENT_DISPOSITION_INVALID", "stageReceipts")
        return False, stage_verified
    for key in (
        "proofRootSha256",
        "sealStageEvidenceRootSha256",
        "canonicalMissionStateSha256",
        "sealedPackageSha256",
        "sourceDispositionSha256",
    ):
        require_string(value[key], "privateDisposition." + key, SHA256_REF)
    if type(value["componentReceiptIds"]) is not dict:
        fail("COMPONENT_RECEIPT_BINDINGS_REQUIRED")
    require_keys(
        value["componentReceiptIds"],
        {"route", "continuity", "twoCell", "successor"},
        "privateDisposition.componentReceiptIds",
    )
    for child in value["componentReceiptIds"].values():
        require_string(child, "componentReceiptId", ID_RE)
    require_string(
        value["sealedVerificationTerminal"], "sealedVerificationTerminal", ID_RE
    )
    require_string(
        value["privateMaterialScanTerminal"], "privateMaterialScanTerminal", ID_RE
    )
    if value["evidenceTier"] == "private_local_attested":
        verified = verify_record(
            value,
            "axmheadprivatedispositionevidence2",
            "private-flight-disposition-v2",
            trust,
            "privateDisposition",
        )
        return verified and auth_verified, stage_verified
    if not allow_synthetic:
        fail("DISPOSITION_EVIDENCE_TIER_INVALID")
    if value["authentication"] is not None:
        fail("SYNTHETIC_AUTHENTICATION_REFUSED")
    return False, stage_verified


def validate_input_shape(
    value: dict[str, Any],
    trust: tuple[bytes, str] | None,
    allow_synthetic: bool,
) -> dict[str, Any]:
    require_keys(
        value,
        {
            "schema",
            "campaignId",
            "sourceBinding",
            "route",
            "continuity",
            "twoCell",
            "successor",
            "privateDisposition",
        },
        "input",
    )
    if value["schema"] != INPUT_SCHEMA:
        fail("INPUT_SCHEMA_INVALID")
    scan_private(value)
    campaign_id = require_string(value["campaignId"], "campaignId", ID_RE)
    for key in (
        "sourceBinding",
        "route",
        "continuity",
        "twoCell",
        "successor",
        "privateDisposition",
    ):
        if type(value[key]) is not dict:
            fail("COMPONENT_OBJECT_REQUIRED", key)
    validate_source_binding(value["sourceBinding"], campaign_id)
    validate_route_record(value["route"], campaign_id, trust, allow_synthetic)
    validate_continuity_record(value["continuity"], campaign_id, trust, allow_synthetic)
    validate_two_cell_record(value["twoCell"], campaign_id, trust, allow_synthetic)
    validate_successor_record(value["successor"], campaign_id, trust, allow_synthetic)
    validate_disposition_record(
        value["privateDisposition"], campaign_id, trust, allow_synthetic
    )
    scan_private(value)
    return value


def evaluate_route(value: dict[str, Any], private_authenticated: bool) -> dict[str, Any]:
    predicates = {
        "present": value["present"],
        "privateReceiptAuthenticated": private_authenticated,
        "perRouteMemorySufficient": False,
        "semanticIdentityPreserved": False,
        "acceleratorFaster": False,
        "independentlyVerified": False,
        "memoryPoolingAbsent": value["memoryPoolingUsed"] is False,
    }
    reasons: list[str] = []
    if value["present"]:
        resident = value["residentRoute"]
        accelerator = value["acceleratorRoute"]
        predicates["perRouteMemorySufficient"] = (
            resident["memoryMiB"] >= resident["requiredMemoryMiB"]
            and accelerator["memoryMiB"] >= accelerator["requiredMemoryMiB"]
        )
        predicates["semanticIdentityPreserved"] = (
            resident["routeClass"] == "resident_personal_floor"
            and accelerator["routeClass"] == "optional_accelerator"
            and all(
                resident[key] == accelerator[key]
                for key in (
                    "missionSha256",
                    "outputSha256",
                    "classificationSha256",
                    "verifierSha256",
                )
            )
        )
        predicates["acceleratorFaster"] = (
            accelerator["throughputMilliItemsPerSecond"]
            > resident["throughputMilliItemsPerSecond"]
        )
        predicates["independentlyVerified"] = (
            resident["independentlyVerified"] is True
            and accelerator["independentlyVerified"] is True
        )
    requirements = {
        "privateReceiptAuthenticated": "ROUTE_RECEIPT_NOT_AUTHENTICATED",
        "perRouteMemorySufficient": "PER_ROUTE_MEMORY_INSUFFICIENT",
        "semanticIdentityPreserved": "ACCELERATOR_SEMANTIC_MISMATCH",
        "acceleratorFaster": "OPTIONAL_ROUTE_NOT_ACCELERATING",
        "independentlyVerified": "ROUTE_NOT_INDEPENDENTLY_VERIFIED",
        "memoryPoolingAbsent": "MEMORY_POOLING_REFUSED",
    }
    if value["present"]:
        reasons.extend(code for key, code in requirements.items() if not predicates[key])
    return make_attestation(
        ROUTE_SCHEMA, "axmheadrouteattestation2", value, predicates, reasons
    )


def evaluate_continuity(
    value: dict[str, Any], private_authenticated: bool
) -> dict[str, Any]:
    predicates = {
        "present": value["present"],
        "privateReceiptAuthenticated": private_authenticated,
        "acceptedOutputRetained": False,
        "canonicalStateUnchanged": False,
        "residentFloorRetained": value["residentFloorAvailableAfter"],
        "acceleratorAbsent": value["halo3AbsentAfter"],
        "latticeUnnecessary": value["latticeAbsentDuringLocalContinuity"],
        "independentlyVerified": value["independentlyVerified"],
    }
    reasons: list[str] = []
    if value["present"]:
        predicates["acceptedOutputRetained"] = (
            value["baselineOutputSha256"] == value["postRemovalOutputSha256"]
        )
        predicates["canonicalStateUnchanged"] = (
            value["canonicalStateBeforeSha256"]
            == value["canonicalStateAfterSha256"]
        )
        requirements = {
            "privateReceiptAuthenticated": "CONTINUITY_RECEIPT_NOT_AUTHENTICATED",
            "acceptedOutputRetained": "POST_REMOVAL_OUTPUT_MISMATCH",
            "canonicalStateUnchanged": "CANONICAL_STATE_DRIFT",
            "residentFloorRetained": "RESIDENT_FLOOR_NOT_RETAINED",
            "acceleratorAbsent": "ACCELERATOR_NOT_REMOVED",
            "latticeUnnecessary": "LATTICE_DEPENDENCY_RETAINED",
            "independentlyVerified": "CONTINUITY_NOT_INDEPENDENTLY_VERIFIED",
        }
        reasons.extend(code for key, code in requirements.items() if not predicates[key])
    return make_attestation(
        CONTINUITY_SCHEMA,
        "axmheadcontinuityattestation2",
        value,
        predicates,
        reasons,
    )


def evaluate_two_cell(value: dict[str, Any], private_authenticated: bool) -> dict[str, Any]:
    predicates = {
        "present": value["present"],
        "privateReceiptAuthenticated": private_authenticated,
        "distinctPhysicalHostClasses": False,
        "bothBranchesRetained": False,
        "humanRequiredConflict": value["reunionTerminal"] == "HUMAN_REQUIRED",
        "automaticMergeAbsent": value["automaticMergeAllowed"] is False,
        "unresolvedObligationRetained": value["unresolvedObligationCount"] > 0,
        "independentlyVerified": value["independentlyVerified"],
    }
    reasons: list[str] = []
    if value["present"]:
        predicates["distinctPhysicalHostClasses"] = (
            value["leftHostClassSha256"] != value["rightHostClassSha256"]
        )
        predicates["bothBranchesRetained"] = sorted(value["retainedChildSha256"]) == sorted(
            [value["leftChildSha256"], value["rightChildSha256"]]
        )
        requirements = {
            "privateReceiptAuthenticated": "TWO_CELL_RECEIPT_NOT_AUTHENTICATED",
            "distinctPhysicalHostClasses": "TWO_CELL_HOST_CLASS_COLLISION",
            "bothBranchesRetained": "DIVERGENT_BRANCH_LOSS",
            "humanRequiredConflict": "CONFLICT_TERMINAL_INVALID",
            "automaticMergeAbsent": "AUTOMATIC_MERGE_REFUSED",
            "unresolvedObligationRetained": "UNRESOLVED_OBLIGATION_REQUIRED",
            "independentlyVerified": "TWO_CELL_NOT_INDEPENDENTLY_VERIFIED",
        }
        reasons.extend(code for key, code in requirements.items() if not predicates[key])
    return make_attestation(
        TWO_CELL_SCHEMA, "axmheadtwocellattestation2", value, predicates, reasons
    )


def expected_successor_answers(value: dict[str, Any]) -> dict[str, str]:
    return {
        "whatMission": sha256_ref(canonical_json_bytes({"missionId": value["missionId"]})),
        "currentState": value["canonicalStateSha256"],
        "whoMayAct": sha256_ref(
            canonical_json_bytes(
                {"namedHumanAuthorityClass": value["namedHumanAuthorityClass"]}
            )
        ),
        "whatProvesIt": value["proofStateSha256"],
        "whatRemainsUnresolved": sha256_ref(
            canonical_json_bytes(
                {"unresolvedObligationCount": value["unresolvedObligationCount"]}
            )
        ),
        "nextSafeAction": value["nextSafeActionSha256"],
    }


def evaluate_successor(
    value: dict[str, Any], private_authenticated: bool
) -> dict[str, Any]:
    predicates = {
        "present": value["present"],
        "privateReceiptAuthenticated": private_authenticated,
        "replacementHeadClassDistinct": False,
        "answersReconstructed": False,
        "dependenciesAbsent": value["dependenciesAbsent"] == list(DEPENDENCIES_ABSENT),
        "verificationPassed": value["verificationTerminal"] == "PASS",
        "independentlyVerified": value["independentlyVerified"],
    }
    reasons: list[str] = []
    if value["present"]:
        predicates["replacementHeadClassDistinct"] = (
            value["originalHeadClassSha256"]
            != value["replacementHeadClassSha256"]
        )
        predicates["answersReconstructed"] = strict_equal(
            value["answers"], expected_successor_answers(value)
        )
        requirements = {
            "privateReceiptAuthenticated": "SUCCESSOR_RECEIPT_NOT_AUTHENTICATED",
            "replacementHeadClassDistinct": "REPLACEMENT_HEAD_CLASS_NOT_DISTINCT",
            "answersReconstructed": "SUCCESSOR_ANSWERS_MISMATCH",
            "dependenciesAbsent": "SUCCESSOR_DEPENDENCY_RETAINED",
            "verificationPassed": "SUCCESSOR_VERIFICATION_FAILED",
            "independentlyVerified": "SUCCESSOR_NOT_INDEPENDENTLY_VERIFIED",
        }
        reasons.extend(code for key, code in requirements.items() if not predicates[key])
    return make_attestation(
        SUCCESSOR_SCHEMA, "axmheadsuccessorattestation2", value, predicates, reasons
    )


def evaluate_disposition(
    value: dict[str, Any],
    private_authenticated: bool,
    stage_authenticated: list[bool],
) -> dict[str, Any]:
    authorization = value["authorization"]
    stages = value["stageReceipts"]
    predicates = {
        "present": value["present"],
        "privateReceiptAuthenticated": private_authenticated,
        "authorizationAuthenticated": False,
        "authorizationBeforePhysicalAction": False,
        "stageDenominatorExact": False,
        "stageTerminalsExact": False,
        "stageChainComplete": False,
        "stageReceiptsAuthenticated": False,
        "privateEvidencePresent": value["privateEvidenceBodyCount"] > 0,
        "publicEvidenceAbsent": value["publicEvidenceBodyCount"] == 0,
        "sealedVerificationPassed": value["sealedVerificationTerminal"] == "PASS",
        "privateMaterialScanPassed": value["privateMaterialScanTerminal"] == "PASS",
        "physicalFlightCompleted": value["privatePhysicalFlightCompleted"] is True,
        "selfAttestationOnly": value["selfAttestationOnly"] is True,
        "strongerClaimsAbsent": strict_equal(value["strongerClaims"], STRONGER_CLAIMS),
        "authorityAbsent": value["authority"] == "none",
    }
    reasons: list[str] = []
    if value["present"]:
        predicates["authorizationAuthenticated"] = (
            authorization["evidenceTier"] == "private_local_attested"
            and authorization["present"] is True
            and authorization.get("authentication") is not None
        )
        predicates["authorizationBeforePhysicalAction"] = (
            authorization["authorizationSequence"] == 0
            and authorization["firstPhysicalReceiptSequence"] == 1
            and bool(stages)
            and stages[0]["sequence"] == 1
            and stages[0]["previousReceiptId"] == authorization["receiptId"]
        )
        predicates["stageDenominatorExact"] = (
            len(stages) == len(STAGES)
            and [row["stage"] for row in stages] == list(STAGES)
            and [row["sequence"] for row in stages]
            == list(range(1, len(STAGES) + 1))
        )
        predicates["stageTerminalsExact"] = predicates["stageDenominatorExact"] and all(
            row["terminal"] == STAGE_TERMINALS[row["stage"]] for row in stages
        )
        predicates["stageChainComplete"] = predicates["stageDenominatorExact"] and all(
            stages[index]["previousReceiptId"]
            == (authorization["receiptId"] if index == 0 else stages[index - 1]["receiptId"])
            for index in range(len(stages))
        )
        predicates["stageReceiptsAuthenticated"] = (
            len(stage_authenticated) == len(STAGES) and all(stage_authenticated)
        )
        requirements = {
            "privateReceiptAuthenticated": "DISPOSITION_RECEIPT_NOT_AUTHENTICATED",
            "authorizationAuthenticated": "AUTHORIZATION_NOT_AUTHENTICATED",
            "authorizationBeforePhysicalAction": "AUTHORIZATION_ORDER_INVALID",
            "stageDenominatorExact": "STAGE_DENOMINATOR_INVALID",
            "stageTerminalsExact": "STAGE_TERMINALS_INVALID",
            "stageChainComplete": "STAGE_CHAIN_INVALID",
            "stageReceiptsAuthenticated": "STAGE_RECEIPTS_NOT_AUTHENTICATED",
            "privateEvidencePresent": "PRIVATE_EVIDENCE_REQUIRED",
            "publicEvidenceAbsent": "PUBLIC_EVIDENCE_BODY_REFUSED",
            "sealedVerificationPassed": "SEALED_VERIFICATION_FAILED",
            "privateMaterialScanPassed": "PRIVATE_MATERIAL_SCAN_FAILED",
            "physicalFlightCompleted": "PRIVATE_FLIGHT_NOT_COMPLETED",
            "selfAttestationOnly": "SELF_ATTESTATION_BOUNDARY_INVALID",
            "strongerClaimsAbsent": "STRONGER_CLAIM_PROMOTION_REFUSED",
            "authorityAbsent": "AUTHORITY_PROMOTION_REFUSED",
        }
        reasons.extend(code for key, code in requirements.items() if not predicates[key])
    return make_attestation(
        DISPOSITION_SCHEMA,
        "axmheaddispositionbinding2",
        value,
        predicates,
        reasons,
    )


def make_attestation(
    schema: str,
    prefix: str,
    evidence: dict[str, Any],
    predicates: dict[str, bool],
    reasons: list[str],
) -> dict[str, Any]:
    body = {
        "schema": schema,
        "profileId": PROFILE_ID,
        "evidence": copy.deepcopy(evidence),
        "predicates": predicates,
        "valid": not reasons,
        "reasonCodes": sorted(set(reasons)),
    }
    body["attestationId"] = content_id(prefix, body)
    return body


def cross_bindings(
    value: dict[str, Any],
    proof_root: str | None,
) -> list[str]:
    reasons: list[str] = []
    route = value["route"]
    continuity = value["continuity"]
    two_cell = value["twoCell"]
    successor = value["successor"]
    disposition = value["privateDisposition"]
    present = all(
        component["present"]
        for component in (route, continuity, two_cell, successor, disposition)
    )
    if not present:
        return reasons
    campaign_id = value["campaignId"]
    components = (route, continuity, two_cell, successor, disposition)
    if any(component["campaignId"] != campaign_id for component in components):
        reasons.append("CAMPAIGN_BINDING_MISMATCH")
    if proof_root is None or any(
        component["proofRootSha256"] != proof_root for component in components
    ):
        reasons.append("PROOF_ROOT_BINDING_MISMATCH")
    trust_roots = {component["trustRootSha256"] for component in components}
    trust_roots.add(disposition["authorization"]["trustRootSha256"])
    trust_roots.update(row["trustRootSha256"] for row in disposition["stageReceipts"])
    if len(trust_roots) != 1:
        reasons.append("TRUST_ROOT_BINDING_MISMATCH")
    stages = disposition["stageReceipts"]
    if len(stages) == len(STAGES):
        expected_stage_roots = {
            "routeResident": stages[3]["evidenceRootSha256"],
            "routeAccelerated": stages[5]["evidenceRootSha256"],
            "continuityPostRemoval": stages[7]["evidenceRootSha256"],
            "continuityLocal": stages[9]["evidenceRootSha256"],
            "twoCellPartition": stages[10]["evidenceRootSha256"],
            "twoCellReunion": stages[11]["evidenceRootSha256"],
            "successorReplace": stages[12]["evidenceRootSha256"],
            "successorCold": stages[14]["evidenceRootSha256"],
            "seal": stages[15]["evidenceRootSha256"],
        }
        observed_stage_roots = {
            "routeResident": route["stageEvidenceRoots"]["residentBaseline"],
            "routeAccelerated": route["stageEvidenceRoots"]["accelerated"],
            "continuityPostRemoval": continuity["stageEvidenceRoots"]["postRemoval"],
            "continuityLocal": continuity["stageEvidenceRoots"]["localContinuity"],
            "twoCellPartition": two_cell["stageEvidenceRoots"]["partition"],
            "twoCellReunion": two_cell["stageEvidenceRoots"]["reunion"],
            "successorReplace": successor["stageEvidenceRoots"]["replaceHead"],
            "successorCold": successor["stageEvidenceRoots"]["coldSuccessor"],
            "seal": disposition["sealStageEvidenceRootSha256"],
        }
        if not strict_equal(observed_stage_roots, expected_stage_roots):
            reasons.append("STAGE_EVIDENCE_BINDING_MISMATCH")
        if route["residentRoute"]["measurementReceiptId"] != expected_stage_roots["routeResident"]:
            reasons.append("RESIDENT_STAGE_BINDING_MISMATCH")
        if route["acceleratorRoute"]["measurementReceiptId"] != expected_stage_roots["routeAccelerated"]:
            reasons.append("ACCELERATOR_STAGE_BINDING_MISMATCH")
        if disposition["sealedPackageSha256"] != expected_stage_roots["seal"]:
            reasons.append("SEALED_STAGE_BINDING_MISMATCH")
        canonical_states = {row["canonicalMissionStateSha256"] for row in stages}
        canonical_states.update(
            {
                route["canonicalMissionStateSha256"],
                continuity["canonicalStateBeforeSha256"],
                continuity["canonicalStateAfterSha256"],
                successor["canonicalStateSha256"],
                disposition["canonicalMissionStateSha256"],
            }
        )
        if len(canonical_states) != 1:
            reasons.append("CANONICAL_STATE_BINDING_MISMATCH")
    if route["residentRoute"]["outputSha256"] != continuity["baselineOutputSha256"]:
        reasons.append("ROUTE_CONTINUITY_OUTPUT_MISMATCH")
    if route["residentRoute"]["outputSha256"] != continuity["postRemovalOutputSha256"]:
        reasons.append("POST_REMOVAL_ROUTE_OUTPUT_MISMATCH")
    expected_component_ids = {
        "route": route["receiptId"],
        "continuity": continuity["receiptId"],
        "twoCell": two_cell["receiptId"],
        "successor": successor["receiptId"],
    }
    if not strict_equal(disposition["componentReceiptIds"], expected_component_ids):
        reasons.append("COMPONENT_RECEIPT_BINDING_MISMATCH")
    return reasons


def build_objects(
    profile: dict[str, Any],
    value: dict[str, Any],
    trust: tuple[bytes, str] | None = None,
    allow_synthetic: bool = True,
) -> dict[str, dict[str, Any]]:
    validate_profile_object(profile)
    validate_input_shape(value, trust=trust, allow_synthetic=allow_synthetic)
    campaign_id = value["campaignId"]
    route_authenticated = (
        value["route"]["present"]
        and value["route"]["evidenceTier"] == "private_local_attested"
        and verify_record(
            value["route"],
            "axmheadrouteevidence2",
            "physical-route-attestation-v2",
            trust,
            "route",
        )
    )
    continuity_authenticated = (
        value["continuity"]["present"]
        and value["continuity"]["evidenceTier"] == "private_local_attested"
        and verify_record(
            value["continuity"],
            "axmheadcontinuityevidence2",
            "continuity-attestation-v2",
            trust,
            "continuity",
        )
    )
    two_cell_authenticated = (
        value["twoCell"]["present"]
        and value["twoCell"]["evidenceTier"] == "private_local_attested"
        and verify_record(
            value["twoCell"],
            "axmheadtwocellevidence2",
            "two-cell-attestation-v2",
            trust,
            "twoCell",
        )
    )
    successor_authenticated = (
        value["successor"]["present"]
        and value["successor"]["evidenceTier"] == "private_local_attested"
        and verify_record(
            value["successor"],
            "axmheadsuccessorevidence2",
            "successor-attestation-v2",
            trust,
            "successor",
        )
    )
    disposition_authenticated, stage_authenticated = validate_disposition_record(
        value["privateDisposition"], campaign_id, trust, allow_synthetic
    )
    route_attestation = evaluate_route(value["route"], route_authenticated)
    continuity_attestation = evaluate_continuity(
        value["continuity"], continuity_authenticated
    )
    two_cell_attestation = evaluate_two_cell(
        value["twoCell"], two_cell_authenticated
    )
    successor_attestation = evaluate_successor(
        value["successor"], successor_authenticated
    )
    disposition_attestation = evaluate_disposition(
        value["privateDisposition"],
        disposition_authenticated,
        stage_authenticated,
    )
    proof_root: str | None = None
    disposition = value["privateDisposition"]
    if disposition["present"] and disposition["authorization"]["receiptId"]:
        proof_root = derive_proof_root(
            campaign_id,
            disposition["authorization"]["trustRootSha256"],
            disposition["authorization"]["receiptId"],
            [row["receiptId"] for row in disposition["stageReceipts"]],
        )
    binding_reasons = cross_bindings(value, proof_root)
    any_private_shape = any(
        component["present"]
        for component in (
            value["route"],
            value["continuity"],
            value["twoCell"],
            value["successor"],
            value["privateDisposition"],
        )
    )
    all_valid = all(
        attestation["valid"]
        for attestation in (
            route_attestation,
            continuity_attestation,
            two_cell_attestation,
            successor_attestation,
            disposition_attestation,
        )
    ) and not binding_reasons
    terminal = (
        "PRIVATE_SELF_ATTESTED"
        if any_private_shape and all_valid
        else ("HOLD" if any_private_shape else "PREPARED_NOT_ARMED")
    )
    if terminal == "PRIVATE_SELF_ATTESTED" and trust is None:
        fail("TRUST_ROOT_REQUIRED")
    source = copy.deepcopy(value["sourceBinding"])
    join_body = {
        "schema": JOIN_SCHEMA,
        "profileId": PROFILE_ID,
        "campaignId": campaign_id,
        "sourceBindingId": source["sourceBindingId"],
        "attestationIds": {
            "route": route_attestation["attestationId"],
            "continuity": continuity_attestation["attestationId"],
            "twoCell": two_cell_attestation["attestationId"],
            "successor": successor_attestation["attestationId"],
            "privateDisposition": disposition_attestation["attestationId"],
        },
        "proofRootSha256": proof_root,
        "terminal": terminal,
        "reasonCodes": sorted(
            set(
                binding_reasons
                + route_attestation["reasonCodes"]
                + continuity_attestation["reasonCodes"]
                + two_cell_attestation["reasonCodes"]
                + successor_attestation["reasonCodes"]
                + disposition_attestation["reasonCodes"]
            )
        ),
        "predicates": {
            "privatePhysicalFlightCompleted": terminal == "PRIVATE_SELF_ATTESTED",
            "selfAttestationOnly": terminal == "PRIVATE_SELF_ATTESTED",
            "physicalExecutionStartedByJoin": False,
            "missionVolumeMaterializedByJoin": False,
            "issue37LedgerAdvancedByJoin": False,
        },
        "workersLaunched": 0,
        "listenersCreated": 0,
        "strongerClaims": copy.deepcopy(STRONGER_CLAIMS),
        "authority": "none",
        "claimBoundary": CLAIM_BOUNDARY,
    }
    join_body["joinId"] = content_id("axmheadphysicallonghauljoin2", join_body)
    public_body = {
        "schema": PUBLIC_SCHEMA,
        "profileId": PROFILE_ID,
        "campaignId": campaign_id,
        "joinId": join_body["joinId"],
        "sourceBindingId": source["sourceBindingId"],
        "terminal": terminal,
        "privatePhysicalFlightCompleted": terminal == "PRIVATE_SELF_ATTESTED",
        "selfAttestationOnly": terminal == "PRIVATE_SELF_ATTESTED",
        "physicalExecutionStartedByJoin": False,
        "missionVolumeMaterializedByJoin": False,
        "issue37LedgerAdvancedByJoin": False,
        "publicEvidenceBodies": 0,
        "workersLaunched": 0,
        "listenersCreated": 0,
        "strongerClaims": copy.deepcopy(STRONGER_CLAIMS),
        "authority": "none",
        "claimBoundary": CLAIM_BOUNDARY,
    }
    public_body["publicStatusId"] = content_id(
        "axmheadphysicallonghaulpublicstatus2", public_body
    )
    scan_private(public_body, "public")
    return {
        "source": source,
        "route": route_attestation,
        "continuity": continuity_attestation,
        "twoCell": two_cell_attestation,
        "successor": successor_attestation,
        "disposition": disposition_attestation,
        "join": join_body,
        "public": public_body,
    }


def verify_carrier(
    carrier: Path,
    trust: tuple[bytes, str] | None,
) -> dict[str, Any]:
    carrier = carrier.resolve()
    if not carrier.is_dir():
        fail("CARRIER_DIRECTORY_REQUIRED")
    expected = ["MANIFEST.json", *EXPECTED_MEMBER_PATHS]
    observed: list[str] = []
    for path in carrier.rglob("*"):
        if path.is_symlink():
            fail("SYMLINK_MEMBER_REFUSED")
        if path.is_file():
            observed.append(path.relative_to(carrier).as_posix())
    if sorted(observed) != sorted(expected):
        fail("FILE_DENOMINATOR_INVALID")
    manifest = read_json(carrier / "MANIFEST.json")
    require_keys(
        manifest,
        {
            "schema",
            "profileId",
            "carrierId",
            "terminal",
            "joinId",
            "sourceBindingId",
            "publicStatusId",
            "trustRootSha256",
            "files",
            "bindings",
            "nonClaims",
        },
        "manifest",
    )
    if manifest["schema"] != MANIFEST_SCHEMA or manifest["profileId"] != PROFILE_ID:
        fail("MANIFEST_IDENTITY_INVALID")
    expected_rows: list[dict[str, Any]] = []
    for rel in EXPECTED_MEMBER_PATHS:
        path = carrier / rel
        before = path.stat()
        data = path.read_bytes()
        after = path.stat()
        if (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ):
            fail("MUTABLE_CARRIER_RACE_REFUSED", rel)
        expected_rows.append(
            {"path": rel, "size": len(data), "sha256": sha256_bytes(data)}
        )
        if rel.endswith(".json"):
            parsed = json.loads(data.decode("utf-8"))
            if data != canonical_json_bytes(parsed):
                fail("NON_CANONICAL_MEMBER_BYTES", rel)
    if manifest["files"] != sorted(expected_rows, key=lambda row: row["path"]):
        fail("MANIFEST_FILE_BINDING_INVALID")
    expected_carrier_id = content_id(
        "axmheadphysicallonghaulcarrier2",
        {key: copy.deepcopy(value) for key, value in manifest.items() if key != "carrierId"},
    )
    if manifest["carrierId"] != expected_carrier_id:
        fail("CARRIER_ID_INVALID")
    profile = read_json(carrier / "RECOVERY/profile.json")
    catalog = read_json(carrier / "RECOVERY/fixture-catalog.json")
    validate_profile_object(profile)
    validate_catalog_object(profile, catalog)
    stored = {
        "source": read_json(carrier / "JOIN/source-binding.json"),
        "route": read_json(carrier / "JOIN/route-attestation.json"),
        "continuity": read_json(carrier / "JOIN/continuity-attestation.json"),
        "twoCell": read_json(carrier / "JOIN/two-cell-attestation.json"),
        "successor": read_json(carrier / "JOIN/successor-attestation.json"),
        "disposition": read_json(carrier / "JOIN/private-disposition-binding.json"),
        "join": read_json(carrier / "JOIN/join.json"),
        "public": read_json(carrier / "PUBLIC/status.json"),
    }
    input_value = {
        "schema": INPUT_SCHEMA,
        "campaignId": stored["join"]["campaignId"],
        "sourceBinding": stored["source"],
        "route": stored["route"]["evidence"],
        "continuity": stored["continuity"]["evidence"],
        "twoCell": stored["twoCell"]["evidence"],
        "successor": stored["successor"]["evidence"],
        "privateDisposition": stored["disposition"]["evidence"],
    }
    reconstructed = build_objects(
        profile,
        input_value,
        trust=trust,
        allow_synthetic=True,
    )
    for key in stored:
        if not strict_equal(stored[key], reconstructed[key]):
            fail("RECONSTRUCTION_MISMATCH", key)
    if manifest["terminal"] != reconstructed["join"]["terminal"]:
        fail("MANIFEST_TERMINAL_MISMATCH")
    if manifest["joinId"] != reconstructed["join"]["joinId"]:
        fail("MANIFEST_JOIN_BINDING_INVALID")
    if manifest["sourceBindingId"] != reconstructed["source"]["sourceBindingId"]:
        fail("MANIFEST_SOURCE_BINDING_INVALID")
    if manifest["publicStatusId"] != reconstructed["public"]["publicStatusId"]:
        fail("MANIFEST_PUBLIC_BINDING_INVALID")
    if reconstructed["join"]["terminal"] == "PRIVATE_SELF_ATTESTED":
        if trust is None:
            fail("TRUST_ROOT_REQUIRED")
        if manifest["trustRootSha256"] != trust[1]:
            fail("MANIFEST_TRUST_ROOT_MISMATCH")
    elif manifest["trustRootSha256"] is not None:
        fail("NONPRIVATE_TRUST_ROOT_REFUSED")
    expected_nonclaims = {
        "physicalExecutionStartedByJoin": False,
        "missionVolumeMaterializedByJoin": False,
        "issue37LedgerAdvancedByJoin": False,
        "workersLaunched": 0,
        "listenersCreated": 0,
        "publicEvidenceBodies": 0,
        "strongerClaims": STRONGER_CLAIMS,
        "authority": "none",
    }
    if not strict_equal(manifest["nonClaims"], expected_nonclaims):
        fail("MANIFEST_NONCLAIM_INVALID")
    return {
        "schema": VERIFICATION_SCHEMA,
        "status": "PASS",
        "terminal": reconstructed["join"]["terminal"],
        "carrierId": manifest["carrierId"],
        "joinId": reconstructed["join"]["joinId"],
        "sourceBindingId": reconstructed["source"]["sourceBindingId"],
        "publicStatusId": reconstructed["public"]["publicStatusId"],
        "trustRootAuthenticated": reconstructed["join"]["terminal"]
        == "PRIVATE_SELF_ATTESTED",
        "privatePhysicalFlightCompleted": reconstructed["join"]["terminal"]
        == "PRIVATE_SELF_ATTESTED",
        "selfAttestationOnly": reconstructed["join"]["terminal"]
        == "PRIVATE_SELF_ATTESTED",
        "physicalExecutionStartedByJoin": False,
        "missionVolumeMaterializedByJoin": False,
        "issue37LedgerAdvancedByJoin": False,
        "publicEvidenceBodies": 0,
        "workersLaunched": 0,
        "listenersCreated": 0,
        "strongerClaims": copy.deepcopy(STRONGER_CLAIMS),
        "authority": "none",
        "bootstrapAuthenticated": False,
    }


def refusal(exc: JoinError) -> dict[str, Any]:
    return {
        "schema": "axm-head/physical-long-haul-command-refusal@2",
        "status": "REFUSED",
        "errorCode": exc.code,
        "message": exc.code,
        "privatePhysicalFlightCompleted": False,
        "physicalExecutionStartedByJoin": False,
        "missionVolumeMaterializedByJoin": False,
        "issue37LedgerAdvancedByJoin": False,
        "workersLaunched": 0,
        "listenersCreated": 0,
        "publicEvidenceBodies": 0,
        "strongerClaims": copy.deepcopy(STRONGER_CLAIMS),
        "authority": "none",
        "bootstrapAuthenticated": False,
    }


def output_overlaps_carrier(carrier: Path, out: Path) -> bool:
    root = carrier.resolve()
    candidate = out.resolve(strict=False)
    if candidate == root or root in candidate.parents:
        return True
    if candidate.exists():
        candidate_stat = candidate.stat()
        for path in root.rglob("*"):
            if path.is_file() and not path.is_symlink():
                path_stat = path.stat()
                if (
                    path_stat.st_dev == candidate_stat.st_dev
                    and path_stat.st_ino == candidate_stat.st_ino
                ):
                    return True
    return False


def emit(value: dict[str, Any]) -> None:
    sys.stdout.buffer.write(canonical_json_bytes(value))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("carrier", type=Path)
    parser.add_argument("--trust-root", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.out is not None and output_overlaps_carrier(args.carrier, args.out):
            fail("VERDICT_OUTPUT_OVERLAP_REFUSED")
        trust = load_trust_root(args.trust_root)
        verdict = verify_carrier(args.carrier, trust)
        data = canonical_json_bytes(verdict)
        if args.out is not None:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_bytes(data)
        sys.stdout.buffer.write(data)
        return 0
    except JoinError as exc:
        result = refusal(exc)
        data = canonical_json_bytes(result)
        if args.out is not None and not output_overlaps_carrier(args.carrier, args.out):
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_bytes(data)
        sys.stdout.buffer.write(data)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
