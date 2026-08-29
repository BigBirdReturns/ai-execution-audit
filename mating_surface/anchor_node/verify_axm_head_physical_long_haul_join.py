from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

PROFILE_SCHEMA = "axm-head/physical-long-haul-profile@2"
PROFILE_ID = "axm-head/physical-long-haul-join@2"
FIXTURE_SCHEMA = "axm-head/physical-long-haul-fixture-catalog@1"
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
AUTH_SCHEMA = "axm-head/named-human-physical-authorization@1"
STAGE_SCHEMA = "stc-mary/private-flight-stage-receipt@1"
TERMINALS = ("PREPARED_NOT_ARMED", "PRIVATE_SELF_ATTESTED", "HOLD")
STAGES = (
    "VERIFY_INPUTS", "MOUNT_PERSONAL_FLOOR", "BIND_GRACE",
    "RUN_PERSONAL_FLOOR_BASELINE", "ATTACH_HALO3",
    "RUN_HALO3_ACCELERATED", "REMOVE_HALO3",
    "VERIFY_PERSONAL_FLOOR_CONTINUITY", "REMOVE_LATTICE",
    "VERIFY_LOCAL_CONTINUITY", "PARTITION_TWO_CELLS",
    "RESTORE_LINK_HOLD_CONFLICT", "REPLACE_HEAD",
    "REBUILD_PROJECTIONS", "COLD_SUCCESSOR_VERIFY",
    "SEAL_PRIVATE_EVIDENCE",
)
STAGE_TERMINALS = {stage: ("HUMAN_REQUIRED" if stage == "RESTORE_LINK_HOLD_CONFLICT" else "PASS") for stage in STAGES}
PHASES = (
    "admitted_checkout", "artifact_coordinates", "readiness", "feed",
    "personal_floor", "halo3", "post_halo3_continuity",
    "two_cell_partition", "successor_head", "flight_plan",
    "private_packet", "sealed_flight",
)
STOP_CONDITIONS = (
    "source_coordinate_drift", "dirty_or_moving_checkout",
    "private_coordinate_mismatch", "unexpected_worker_or_listener",
    "authorization_field_present", "authority_not_none",
    "receipt_refusal", "physical_action_before_separate_authorization",
)
DEPENDENCIES_ABSENT = ("AWS", "Lattice", "WAN", "original_host", "remote_model_provider", "repository_history")
PUBLIC_SOURCES = {
    "axmRemovableVolumeSupplier": {"repository": "BigBirdReturns/ai-execution-audit", "commit": "b452bb32e26249deab90db124f157bc62ad0850d", "tree": "c557bddc17ad62f6ad36bac5a6ef57338429a951", "role": "admitted_synthetic_contract"},
    "stcMaryConductor": {"repository": "BigBirdReturns/ai-execution-audit", "commit": "772ce582e1b19b7a2060c50be8ebf40c1f8723b2", "tree": "3f708c52782784e687cf1f0b68fd7d37a507ef4c", "role": "admitted_operator_layer"},
    "physicalFlightExecutionFloor": {"repository": "BigBirdReturns/ai-execution-audit", "commit": "d31e59f5fd30e57b1917c00832b189ee2ea3e12f", "tree": "2a6a155e9615eb847781f87566bac32d4c9dc126", "role": "admitted_not_executed"},
    "preflightReviewCard": {"repository": "BigBirdReturns/ai-execution-audit", "commit": "ec61bc3488cb5ae06ed9db2862a9f6910d310a79", "tree": "d2daba1d32a8de744b8b90f6cd42f7c4bff4fa67", "role": "admitted_preflight_law"},
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
ISSUE = {"repository": "BigBirdReturns/ai-execution-audit", "issueNumber": 37, "role": "sole_private_physical_flight_execution_coordinate"}
PREFLIGHT = {
    "profileId": "axm-head/physical-flight-preflight-review-card@1",
    "profileCanonicalSha256": SOURCE_DIGESTS["preflightProfileCanonicalSha256"],
    "standaloneVerifierSha256": SOURCE_DIGESTS["preflightStandaloneVerifierSha256"],
    "carrierId": "axmheadpreflightcarrier1_decd7e3c9158f25602eeafc4544f09f7570d726ebb9a7758b36a050441338772",
    "terminal": "READY_FOR_HUMAN_REVIEW", "reviewCardActionCount": 12,
    "authorizedActionCount": 0, "phaseSequence": list(PHASES),
    "packetStageSequence": list(STAGES), "stopConditions": list(STOP_CONDITIONS),
    "physicalAuthorizationProduced": False, "privateEvidenceBodies": 0,
    "authority": "none",
}
STRONGER_CLAIMS = {
    "physicalEstateQualified": False, "representativeOperatorQualified": False,
    "fieldNetworkQualified": False, "operationalC2Qualified": False,
    "productionLatticeQualified": False, "missionAuthorityGranted": False,
    "commandAuthorityGranted": False,
    "targetingEngagementEffectorOrWeaponsCapability": False,
}
CLAIM_BOUNDARY = 'Provider-free postflight verification membrane for one private STC MARY physical-flight self-attestation. It binds exact admitted public sources to allowlisted body-free private receipts, requires a separately custodied private proof root to authenticate the complete single-campaign receipt graph, derives route, continuity, two-cell, successor, sealed-package, authorization-order, and cross-stage predicates, and may emit PRIVATE_SELF_ATTESTED only when that authenticated private_local_attested denominator closes. The proof root never enters the carrier or repository. The join does not launch, authorize, or execute a physical campaign, publish a private body, qualify a representative operator, field network, operational C2 system, production Lattice integration, or grant mission, command, targeting, engagement, effector, or weapons authority.'
OBJECT_SCHEMAS = (PROFILE_SCHEMA, SOURCE_SCHEMA, ROUTE_SCHEMA, CONTINUITY_SCHEMA, TWO_CELL_SCHEMA, SUCCESSOR_SCHEMA, DISPOSITION_SCHEMA, JOIN_SCHEMA, VERIFICATION_SCHEMA, PUBLIC_SCHEMA)
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SHA256_REF = re.compile(r"^sha256:[0-9a-f]{64}$")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{2,255}$")
PRIVATE_PATTERNS = (
    re.compile(r"[A-Za-z]:\\"), re.compile(r"\\\\[^\\]+\\"),
    re.compile(r"/(?:home|Users|mnt|tmp|var|private)/", re.I),
    re.compile(r"(?:https?|ssh|tcp|udp)://", re.I),
    re.compile(r"\b(?:localhost|OCTO-[A-Z0-9-]+)\b", re.I),
    re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b"),
    re.compile(r"\b[a-z0-9][a-z0-9-]{0,62}(?:\.[a-z0-9][a-z0-9-]{0,62})+\b", re.I),
    re.compile(r"AKIA[0-9A-Z]{16}|BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY|Authorization:\s*Bearer|(?:password|secret|token|api[_-]?key)\s*[:=]", re.I),
)
EXPECTED_MEMBER_PATHS = (
    "JOIN/source-binding.json", "JOIN/route-attestation.json",
    "JOIN/continuity-attestation.json", "JOIN/two-cell-attestation.json",
    "JOIN/successor-attestation.json", "JOIN/private-disposition-binding.json",
    "JOIN/join.json", "PUBLIC/status.json", "RECOVERY/profile.json",
    "RECOVERY/fixture-catalog.json", "RECOVERY/verify_join.py",
)

class JoinError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code

def fail(code: str, message: str) -> None:
    raise JoinError(code, message)

def canonical_json_bytes(value: Any) -> bytes:
    try:
        return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError) as exc:
        fail("NON_CANONICAL_JSON", str(exc))

def pretty_json_bytes(value: Any) -> bytes:
    try:
        return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError) as exc:
        fail("NON_CANONICAL_JSON", str(exc))

def strict_equal(actual: Any, expected: Any) -> bool:
    return canonical_json_bytes(actual) == canonical_json_bytes(expected)

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def content_id(prefix: str, body: dict[str, Any]) -> str:
    return f"{prefix}_{sha256_bytes(canonical_json_bytes(body))}"

def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail("JSON_READ_FAILED", f"{path}: {exc}")
    if type(value) is not dict:
        fail("JSON_OBJECT_REQUIRED", f"{path} must contain one object")
    return value

def require_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        fail("OBJECT_KEYS_INVALID", f"{label} missing={sorted(expected-actual)} unknown={sorted(actual-expected)}")

def require_bool(value: Any, label: str) -> bool:
    if type(value) is not bool:
        fail("BOOLEAN_REQUIRED", label)
    return value

def require_int(value: Any, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        fail("INTEGER_REQUIRED", label)
    return value

def require_string(value: Any, label: str, pattern: re.Pattern[str] | None = None, max_len: int = 512) -> str:
    if type(value) is not str or not value or len(value) > max_len:
        fail("STRING_REQUIRED", label)
    if pattern is not None and pattern.fullmatch(value) is None:
        fail("STRING_PATTERN_INVALID", label)
    return value

def scan_private(value: Any, label: str = "input") -> None:
    if type(value) is dict:
        for key, child in value.items():
            scan_private(child, f"{label}.{key}")
    elif type(value) is list:
        if len(value) > 256:
            fail("ARRAY_BOUND_EXCEEDED", label)
        for index, child in enumerate(value):
            scan_private(child, f"{label}[{index}]")
    elif type(value) is str:
        if len(value) > 1024:
            fail("STRING_BOUND_EXCEEDED", label)
        for pattern in PRIVATE_PATTERNS:
            if pattern.search(value):
                fail("PRIVATE_MATERIAL_REFUSED", label)

def validate_profile_object(profile: dict[str, Any]) -> dict[str, Any]:
    require_keys(profile, {
        "schema", "profileId", "version", "status", "owningProject", "owningRepository",
        "publicSources", "sourceDigests", "physicalFlightIssue", "preflightLaw",
        "objectSchemas", "terminalStates", "packetStageSequence", "requiredStageTerminals",
        "dependenciesAbsent", "bootstrapRequired", "repositoryOutputAllowed", "networkRequired",
        "externalServiceCalls", "operationalCredentials", "privateEvidenceBodiesPublic",
        "workersLaunched", "listenersCreated", "authority", "strongerClaims", "claimBoundary",
        "fixtureCatalogCanonicalSha256", "standaloneVerifierSha256",
    }, "profile")
    if profile["schema"] != PROFILE_SCHEMA or profile["profileId"] != PROFILE_ID or profile["version"] != 2:
        fail("PROFILE_IDENTITY_INVALID", "profile")
    if profile["status"] != "candidate_contract_only" or profile["owningProject"] != "Estate" or profile["owningRepository"] != "BigBirdReturns/ai-execution-audit":
        fail("PROFILE_SCOPE_INVALID", "profile")
    if not strict_equal(profile["publicSources"], PUBLIC_SOURCES) or not strict_equal(profile["sourceDigests"], SOURCE_DIGESTS):
        fail("SOURCE_COORDINATES_INVALID", "profile")
    if not strict_equal(profile["physicalFlightIssue"], ISSUE) or not strict_equal(profile["preflightLaw"], PREFLIGHT):
        fail("SOURCE_LAW_INVALID", "profile")
    if profile["objectSchemas"] != list(OBJECT_SCHEMAS) or profile["terminalStates"] != list(TERMINALS):
        fail("OBJECT_DENOMINATOR_INVALID", "profile")
    if profile["packetStageSequence"] != list(STAGES) or not strict_equal(profile["requiredStageTerminals"], STAGE_TERMINALS):
        fail("STAGE_DENOMINATOR_INVALID", "profile")
    if profile["dependenciesAbsent"] != list(DEPENDENCIES_ABSENT):
        fail("DEPENDENCY_DENOMINATOR_INVALID", "profile")
    if profile["bootstrapRequired"] is not True or profile["repositoryOutputAllowed"] is not False or profile["networkRequired"] is not False:
        fail("PROFILE_CUSTODY_INVALID", "profile")
    expected = {
        "externalServiceCalls": 0, "operationalCredentials": 0,
        "privateEvidenceBodiesPublic": 0, "workersLaunched": 0,
        "listenersCreated": 0, "authority": "none",
        "strongerClaims": STRONGER_CLAIMS, "claimBoundary": CLAIM_BOUNDARY,
    }
    for key, wanted in expected.items():
        if not strict_equal(profile[key], wanted):
            fail("PROFILE_NONCLAIM_INVALID", key)
    require_string(profile["fixtureCatalogCanonicalSha256"], "fixture digest", HEX64)
    require_string(profile["standaloneVerifierSha256"], "verifier digest", HEX64)
    return profile

def validate_profile(path: Path) -> dict[str, Any]:
    return validate_profile_object(read_json(path))

def validate_fixture_catalog(profile: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    require_keys(catalog, {"schema", "status", "cases"}, "fixture catalog")
    if catalog["schema"] != FIXTURE_SCHEMA or catalog["status"] != "synthetic_qualification_only":
        fail("FIXTURE_IDENTITY_INVALID", "fixture catalog")
    if type(catalog["cases"]) is not list or not catalog["cases"]:
        fail("FIXTURE_CASES_INVALID", "fixture catalog")
    ids: list[str] = []
    for index, row in enumerate(catalog["cases"]):
        if type(row) is not dict:
            fail("FIXTURE_CASE_INVALID", str(index))
        require_keys(row, {"caseId", "expectedTerminal", "input"}, f"case[{index}]")
        ids.append(require_string(row["caseId"], f"case[{index}].caseId", ID_RE))
        if row["expectedTerminal"] not in TERMINALS:
            fail("FIXTURE_TERMINAL_INVALID", str(index))
        validate_input_shape(row["input"])
        if row["input"]["privateDisposition"]["evidenceTier"] == "private_local_attested":
            fail("FIXTURE_PHYSICAL_PROMOTION_REFUSED", row["caseId"])
    if len(ids) != len(set(ids)):
        fail("FIXTURE_CASE_DUPLICATE", "case ids")
    if sha256_bytes(canonical_json_bytes(catalog)) != profile["fixtureCatalogCanonicalSha256"]:
        fail("FIXTURE_CATALOG_DIGEST_INVALID", "fixture catalog")
    return catalog

def validate_source_binding(value: dict[str, Any]) -> None:
    require_keys(value, {"publicSources", "sourceDigests", "physicalFlightIssue", "preflight"}, "sourceBinding")
    if not strict_equal(value["publicSources"], PUBLIC_SOURCES) or not strict_equal(value["sourceDigests"], SOURCE_DIGESTS):
        fail("SOURCE_BINDING_INVALID", "public source identity differs")
    if not strict_equal(value["physicalFlightIssue"], ISSUE) or not strict_equal(value["preflight"], PREFLIGHT):
        fail("SOURCE_BINDING_INVALID", "issue or preflight law differs")

def validate_route_shape(value: dict[str, Any]) -> None:
    require_keys(value, {"present", "evidenceTier", "memoryPoolingUsed", "residentRoute", "acceleratorRoute"}, "route")
    require_bool(value["present"], "route.present"); require_bool(value["memoryPoolingUsed"], "route.memoryPoolingUsed")
    require_string(value["evidenceTier"], "route.evidenceTier")
    if not value["present"]:
        if value["residentRoute"] is not None or value["acceleratorRoute"] is not None:
            fail("ABSENT_ROUTE_INVALID", "route")
        return
    for label in ("residentRoute", "acceleratorRoute"):
        row = value[label]
        if type(row) is not dict:
            fail("ROUTE_OBJECT_REQUIRED", label)
        require_keys(row, {"routeClass", "memoryMiB", "requiredMemoryMiB", "missionSha256", "outputSha256", "classificationSha256", "verifierSha256", "throughputMilliItemsPerSecond", "independentlyVerified", "receiptId"}, label)
        require_string(row["routeClass"], label+".routeClass", ID_RE)
        require_int(row["memoryMiB"], label+".memoryMiB", 1); require_int(row["requiredMemoryMiB"], label+".requiredMemoryMiB", 1)
        for key in ("missionSha256", "outputSha256", "classificationSha256", "verifierSha256", "receiptId"):
            require_string(row[key], label+"."+key, SHA256_REF)
        require_int(row["throughputMilliItemsPerSecond"], label+".throughput", 1)
        require_bool(row["independentlyVerified"], label+".independentlyVerified")

def validate_continuity_shape(value: dict[str, Any]) -> None:
    require_keys(value, {"present", "evidenceTier", "baselineOutputSha256", "postRemovalOutputSha256", "canonicalStateBeforeSha256", "canonicalStateAfterSha256", "residentFloorAvailableAfter", "halo3AbsentAfter", "latticeAbsentDuringLocalContinuity", "independentlyVerified", "receiptId"}, "continuity")
    require_bool(value["present"], "continuity.present"); require_string(value["evidenceTier"], "continuity.evidenceTier")
    for key in ("residentFloorAvailableAfter", "halo3AbsentAfter", "latticeAbsentDuringLocalContinuity", "independentlyVerified"):
        require_bool(value[key], "continuity."+key)
    for key in ("baselineOutputSha256", "postRemovalOutputSha256", "canonicalStateBeforeSha256", "canonicalStateAfterSha256", "receiptId"):
        if value["present"]: require_string(value[key], "continuity."+key, SHA256_REF)
        elif value[key] is not None: fail("ABSENT_CONTINUITY_INVALID", key)

def validate_two_cell_shape(value: dict[str, Any]) -> None:
    require_keys(value, {"present", "evidenceTier", "commonParentSha256", "leftChildSha256", "rightChildSha256", "leftHostClassSha256", "rightHostClassSha256", "reunionTerminal", "automaticMergeAllowed", "retainedChildSha256", "unresolvedObligationCount", "independentlyVerified", "receiptId"}, "twoCell")
    require_bool(value["present"], "twoCell.present"); require_string(value["evidenceTier"], "twoCell.evidenceTier")
    require_bool(value["automaticMergeAllowed"], "twoCell.automaticMergeAllowed"); require_bool(value["independentlyVerified"], "twoCell.independentlyVerified")
    require_int(value["unresolvedObligationCount"], "twoCell.unresolvedObligationCount")
    if type(value["retainedChildSha256"]) is not list: fail("ARRAY_REQUIRED", "retainedChildSha256")
    for key in ("commonParentSha256", "leftChildSha256", "rightChildSha256", "leftHostClassSha256", "rightHostClassSha256", "receiptId"):
        if value["present"]: require_string(value[key], "twoCell."+key, SHA256_REF)
        elif value[key] is not None: fail("ABSENT_TWO_CELL_INVALID", key)
    if value["present"]: require_string(value["reunionTerminal"], "twoCell.reunionTerminal")
    elif value["reunionTerminal"] is not None or value["retainedChildSha256"]: fail("ABSENT_TWO_CELL_INVALID", "twoCell")

def validate_successor_shape(value: dict[str, Any]) -> None:
    require_keys(value, {"present", "evidenceTier", "originalHeadClassSha256", "replacementHeadClassSha256", "missionId", "canonicalStateSha256", "proofRootSha256", "namedHumanAuthorityClass", "unresolvedObligationCount", "nextSafeActionSha256", "answers", "verificationTerminal", "dependenciesAbsent", "independentlyVerified", "receiptId"}, "successor")
    require_bool(value["present"], "successor.present"); require_string(value["evidenceTier"], "successor.evidenceTier")
    require_int(value["unresolvedObligationCount"], "successor.unresolvedObligationCount"); require_bool(value["independentlyVerified"], "successor.independentlyVerified")
    if type(value["answers"]) is not dict or type(value["dependenciesAbsent"]) is not list: fail("SUCCESSOR_COLLECTION_INVALID", "successor")
    for key in ("originalHeadClassSha256", "replacementHeadClassSha256", "canonicalStateSha256", "proofRootSha256", "nextSafeActionSha256", "receiptId"):
        if value["present"]: require_string(value[key], "successor."+key, SHA256_REF)
        elif value[key] is not None: fail("ABSENT_SUCCESSOR_INVALID", key)
    if value["present"]:
        require_string(value["missionId"], "successor.missionId", ID_RE); require_string(value["namedHumanAuthorityClass"], "successor.namedHumanAuthorityClass", ID_RE); require_string(value["verificationTerminal"], "successor.verificationTerminal")
    elif any(value[key] is not None for key in ("missionId", "namedHumanAuthorityClass", "verificationTerminal")) or value["answers"] or value["dependenciesAbsent"]:
        fail("ABSENT_SUCCESSOR_INVALID", "successor")

def validate_authorization_shape(value: dict[str, Any], campaign: str) -> None:
    require_keys(value, {"schema", "present", "evidenceTier", "receiptId", "preflightCarrierId", "campaignId", "authorizationSequence", "firstPhysicalReceiptSequence", "namedHumanAuthorityClass", "terminal"}, "authorization")
    if value["schema"] != AUTH_SCHEMA: fail("AUTHORIZATION_SCHEMA_INVALID", "authorization")
    require_bool(value["present"], "authorization.present"); require_string(value["evidenceTier"], "authorization.evidenceTier")
    if value["preflightCarrierId"] != PREFLIGHT["carrierId"] or value["campaignId"] != campaign: fail("AUTHORIZATION_BINDING_INVALID", "authorization")
    if value["present"]:
        require_string(value["receiptId"], "authorization.receiptId", SHA256_REF)
        require_int(value["authorizationSequence"], "authorization.authorizationSequence")
        require_int(value["firstPhysicalReceiptSequence"], "authorization.firstPhysicalReceiptSequence", 1)
        require_string(value["namedHumanAuthorityClass"], "authorization.namedHumanAuthorityClass", ID_RE)
        require_string(value["terminal"], "authorization.terminal")
    else:
        if any(value[key] is not None for key in ("receiptId", "authorizationSequence", "firstPhysicalReceiptSequence", "namedHumanAuthorityClass")) or value["terminal"] != "ABSENT":
            fail("ABSENT_AUTHORIZATION_INVALID", "authorization")

def validate_stage_receipt_shape(row: dict[str, Any], index: int) -> None:
    require_keys(row, {"schema", "sequence", "stage", "terminal", "receiptId", "previousReceiptId", "evidenceTier", "evidenceBodyCount", "evidenceRootSha256", "canonicalMissionStateSha256"}, f"stage[{index}]")
    if row["schema"] != STAGE_SCHEMA: fail("STAGE_SCHEMA_INVALID", str(index))
    require_int(row["sequence"], f"stage[{index}].sequence", 1)
    require_string(row["stage"], f"stage[{index}].stage", ID_RE); require_string(row["terminal"], f"stage[{index}].terminal", ID_RE)
    for key in ("receiptId", "previousReceiptId", "evidenceRootSha256", "canonicalMissionStateSha256"):
        require_string(row[key], f"stage[{index}].{key}", SHA256_REF)
    require_string(row["evidenceTier"], f"stage[{index}].evidenceTier")
    require_int(row["evidenceBodyCount"], f"stage[{index}].evidenceBodyCount")

def validate_disposition_shape(value: dict[str, Any], campaign: str) -> None:
    require_keys(value, {"present", "evidenceTier", "authorization", "stageReceipts", "publicEvidenceBodyCount", "privateEvidenceBodyCount", "canonicalMissionStateSha256", "sealedVerificationTerminal", "sealedPackageSha256", "sourceDispositionSha256", "privateMaterialScanTerminal", "privatePhysicalFlightCompleted", "selfAttestationOnly", "strongerClaims", "authority"}, "privateDisposition")
    require_bool(value["present"], "privateDisposition.present"); require_string(value["evidenceTier"], "privateDisposition.evidenceTier")
    validate_authorization_shape(value["authorization"], campaign)
    if type(value["stageReceipts"]) is not list: fail("ARRAY_REQUIRED", "stageReceipts")
    for index, row in enumerate(value["stageReceipts"]):
        if type(row) is not dict: fail("STAGE_OBJECT_REQUIRED", str(index))
        validate_stage_receipt_shape(row, index)
    require_int(value["publicEvidenceBodyCount"], "publicEvidenceBodyCount"); require_int(value["privateEvidenceBodyCount"], "privateEvidenceBodyCount")
    require_bool(value["privatePhysicalFlightCompleted"], "privatePhysicalFlightCompleted"); require_bool(value["selfAttestationOnly"], "selfAttestationOnly")
    if not strict_equal(value["strongerClaims"], STRONGER_CLAIMS) or value["authority"] != "none": fail("AUTHORITY_PROMOTION_REFUSED", "privateDisposition")
    for key in ("canonicalMissionStateSha256", "sealedPackageSha256", "sourceDispositionSha256"):
        if value["present"]: require_string(value[key], "privateDisposition."+key, SHA256_REF)
        elif value[key] is not None: fail("ABSENT_DISPOSITION_INVALID", key)
    if value["present"]:
        require_string(value["sealedVerificationTerminal"], "sealedVerificationTerminal"); require_string(value["privateMaterialScanTerminal"], "privateMaterialScanTerminal")
    elif any(value[key] is not None for key in ("sealedVerificationTerminal", "privateMaterialScanTerminal")) or value["stageReceipts"]:
        fail("ABSENT_DISPOSITION_INVALID", "privateDisposition")

def validate_input_shape(value: dict[str, Any]) -> dict[str, Any]:
    if type(value) is not dict: fail("INPUT_OBJECT_REQUIRED", "input")
    require_keys(value, {"schema", "campaignId", "sourceBinding", "route", "continuity", "twoCell", "successor", "privateDisposition"}, "input")
    if value["schema"] != INPUT_SCHEMA: fail("INPUT_SCHEMA_INVALID", "input")
    campaign = require_string(value["campaignId"], "campaignId", ID_RE)
    if type(value["sourceBinding"]) is not dict: fail("SOURCE_BINDING_OBJECT_REQUIRED", "sourceBinding")
    validate_source_binding(value["sourceBinding"])
    for key in ("route", "continuity", "twoCell", "successor", "privateDisposition"):
        if type(value[key]) is not dict: fail("COMPONENT_OBJECT_REQUIRED", key)
    validate_route_shape(value["route"]); validate_continuity_shape(value["continuity"]); validate_two_cell_shape(value["twoCell"]); validate_successor_shape(value["successor"]); validate_disposition_shape(value["privateDisposition"], campaign)
    scan_private(value)
    return value

def build_source_binding(value: dict[str, Any]) -> dict[str, Any]:
    body = {"schema": SOURCE_SCHEMA, "profileId": PROFILE_ID, **copy.deepcopy(value)}
    body["sourceBindingId"] = content_id("axmheadsourcebinding2", body)
    return body

def make_attestation(schema: str, prefix: str, evidence: dict[str, Any], predicates: dict[str, bool], reasons: list[str]) -> dict[str, Any]:
    body = {"schema": schema, "profileId": PROFILE_ID, "evidence": copy.deepcopy(evidence), "predicates": predicates, "valid": not reasons, "reasonCodes": sorted(set(reasons))}
    body["attestationId"] = content_id(prefix, body)
    return body

def evaluate_route(value: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    predicates = {"present": value["present"], "privateTier": value["evidenceTier"] == "private_local_attested", "perRouteMemorySufficient": False, "semanticIdentityPreserved": False, "acceleratorFaster": False, "independentlyVerified": False, "memoryPoolingAbsent": value["memoryPoolingUsed"] is False}
    if value["present"]:
        resident, accelerator = value["residentRoute"], value["acceleratorRoute"]
        predicates["perRouteMemorySufficient"] = resident["memoryMiB"] >= resident["requiredMemoryMiB"] and accelerator["memoryMiB"] >= accelerator["requiredMemoryMiB"]
        predicates["semanticIdentityPreserved"] = all(resident[key] == accelerator[key] for key in ("missionSha256", "outputSha256", "classificationSha256", "verifierSha256")) and resident["routeClass"] == "resident_personal_floor" and accelerator["routeClass"] == "optional_accelerator"
        predicates["acceleratorFaster"] = accelerator["throughputMilliItemsPerSecond"] > resident["throughputMilliItemsPerSecond"]
        predicates["independentlyVerified"] = resident["independentlyVerified"] is True and accelerator["independentlyVerified"] is True
    if value["present"] and not predicates["privateTier"]: reasons.append("ROUTE_EVIDENCE_TIER_INVALID")
    for key, code in (("perRouteMemorySufficient", "PER_ROUTE_MEMORY_INSUFFICIENT"), ("semanticIdentityPreserved", "ACCELERATOR_SEMANTIC_MISMATCH"), ("acceleratorFaster", "OPTIONAL_ROUTE_NOT_ACCELERATING"), ("independentlyVerified", "ROUTE_NOT_INDEPENDENTLY_VERIFIED"), ("memoryPoolingAbsent", "MEMORY_POOLING_REFUSED")):
        if value["present"] and not predicates[key]: reasons.append(code)
    return make_attestation(ROUTE_SCHEMA, "axmheadrouteattestation2", value, predicates, reasons)

def evaluate_continuity(value: dict[str, Any]) -> dict[str, Any]:
    predicates = {"present": value["present"], "privateTier": value["evidenceTier"] == "private_local_attested", "acceptedOutputRetained": False, "canonicalStateUnchanged": False, "residentFloorRetained": value["residentFloorAvailableAfter"], "acceleratorAbsent": value["halo3AbsentAfter"], "latticeUnnecessary": value["latticeAbsentDuringLocalContinuity"], "independentlyVerified": value["independentlyVerified"]}
    reasons: list[str] = []
    if value["present"]:
        predicates["acceptedOutputRetained"] = value["baselineOutputSha256"] == value["postRemovalOutputSha256"]
        predicates["canonicalStateUnchanged"] = value["canonicalStateBeforeSha256"] == value["canonicalStateAfterSha256"]
        if not predicates["privateTier"]: reasons.append("CONTINUITY_EVIDENCE_TIER_INVALID")
        for key, code in (("acceptedOutputRetained", "POST_REMOVAL_OUTPUT_MISMATCH"), ("canonicalStateUnchanged", "CANONICAL_STATE_DRIFT"), ("residentFloorRetained", "RESIDENT_FLOOR_NOT_RETAINED"), ("acceleratorAbsent", "ACCELERATOR_REMOVAL_NOT_PROVED"), ("latticeUnnecessary", "LATTICE_DEPENDENCY_RETAINED"), ("independentlyVerified", "CONTINUITY_NOT_INDEPENDENTLY_VERIFIED")):
            if not predicates[key]: reasons.append(code)
    return make_attestation(CONTINUITY_SCHEMA, "axmheadcontinuityattestation2", value, predicates, reasons)

def evaluate_two_cell(value: dict[str, Any]) -> dict[str, Any]:
    predicates = {"present": value["present"], "privateTier": value["evidenceTier"] == "private_local_attested", "distinctHostClasses": False, "distinctChildren": False, "bothBranchesRetained": False, "humanRequired": value["reunionTerminal"] == "HUMAN_REQUIRED", "automaticMergeAbsent": value["automaticMergeAllowed"] is False, "unresolvedObligationRetained": value["unresolvedObligationCount"] > 0, "independentlyVerified": value["independentlyVerified"]}
    reasons: list[str] = []
    if value["present"]:
        predicates["distinctHostClasses"] = value["leftHostClassSha256"] != value["rightHostClassSha256"]
        predicates["distinctChildren"] = value["leftChildSha256"] != value["rightChildSha256"]
        predicates["bothBranchesRetained"] = value["retainedChildSha256"] == [value["leftChildSha256"], value["rightChildSha256"]]
        if not predicates["privateTier"]: reasons.append("TWO_CELL_EVIDENCE_TIER_INVALID")
        for key, code in (("distinctHostClasses", "SAME_HOST_CLASS_REFUSED"), ("distinctChildren", "CELL_DIVERGENCE_ABSENT"), ("bothBranchesRetained", "BRANCH_RETENTION_INVALID"), ("humanRequired", "REUNION_TERMINAL_INVALID"), ("automaticMergeAbsent", "AUTOMATIC_REUNION_MERGE_REFUSED"), ("unresolvedObligationRetained", "UNRESOLVED_OBLIGATION_ABSENT"), ("independentlyVerified", "TWO_CELL_NOT_INDEPENDENTLY_VERIFIED")):
            if not predicates[key]: reasons.append(code)
    return make_attestation(TWO_CELL_SCHEMA, "axmheadtwocellattestation2", value, predicates, reasons)

def expected_successor_answers(value: dict[str, Any]) -> dict[str, str]:
    return {"whatMission": value["missionId"], "currentState": value["canonicalStateSha256"], "whoMayAct": value["namedHumanAuthorityClass"], "whatProvesIt": value["proofRootSha256"], "whatRemainsUnresolved": str(value["unresolvedObligationCount"]), "nextSafeAction": value["nextSafeActionSha256"]}

def evaluate_successor(value: dict[str, Any]) -> dict[str, Any]:
    predicates = {"present": value["present"], "privateTier": value["evidenceTier"] == "private_local_attested", "replacementClassDistinct": False, "answersReconstructed": False, "dependenciesAbsent": value["dependenciesAbsent"] == list(DEPENDENCIES_ABSENT), "verificationPassed": value["verificationTerminal"] == "PASS", "independentlyVerified": value["independentlyVerified"]}
    reasons: list[str] = []
    if value["present"]:
        predicates["replacementClassDistinct"] = value["originalHeadClassSha256"] != value["replacementHeadClassSha256"]
        predicates["answersReconstructed"] = strict_equal(value["answers"], expected_successor_answers(value))
        if not predicates["privateTier"]: reasons.append("SUCCESSOR_EVIDENCE_TIER_INVALID")
        for key, code in (("replacementClassDistinct", "SAME_HEAD_CLASS_REFUSED"), ("answersReconstructed", "COLD_SUCCESSOR_ANSWERS_MISMATCH"), ("dependenciesAbsent", "SUCCESSOR_DEPENDENCY_RETAINED"), ("verificationPassed", "SUCCESSOR_VERIFICATION_FAILED"), ("independentlyVerified", "SUCCESSOR_NOT_INDEPENDENTLY_VERIFIED")):
            if not predicates[key]: reasons.append(code)
    return make_attestation(SUCCESSOR_SCHEMA, "axmheadsuccessorattestation2", value, predicates, reasons)

def evaluate_disposition(value: dict[str, Any], campaign: str) -> dict[str, Any]:
    auth = value["authorization"]
    receipts = value["stageReceipts"]
    predicates = {"present": value["present"], "privateTier": value["evidenceTier"] == "private_local_attested", "authorizationDistinctAndPrior": False, "completeStageDenominator": False, "requiredTerminalsRetained": False, "receiptChainComplete": False, "privateEvidencePresent": value["privateEvidenceBodyCount"] > 0, "publicEvidenceAbsent": value["publicEvidenceBodyCount"] == 0, "canonicalStateUnchanged": False, "sealedVerificationPassed": value["sealedVerificationTerminal"] == "PASS", "privateMaterialScanPassed": value["privateMaterialScanTerminal"] == "PASS", "privateFlightCompleted": value["privatePhysicalFlightCompleted"] is True, "selfAttestationOnly": value["selfAttestationOnly"] is True, "strongerClaimsAbsent": strict_equal(value["strongerClaims"], STRONGER_CLAIMS) and value["authority"] == "none"}
    reasons: list[str] = []
    if value["present"]:
        predicates["authorizationDistinctAndPrior"] = auth["present"] is True and auth["evidenceTier"] == "private_local_attested" and auth["terminal"] == "AUTHORIZED" and auth["authorizationSequence"] == 0 and auth["firstPhysicalReceiptSequence"] == 1 and auth["namedHumanAuthorityClass"] == "GRACE" and bool(receipts) and auth["receiptId"] not in {row["receiptId"] for row in receipts} and receipts[0]["previousReceiptId"] == auth["receiptId"]
        predicates["completeStageDenominator"] = len(receipts) == len(STAGES) and [row["stage"] for row in receipts] == list(STAGES) and [row["sequence"] for row in receipts] == list(range(1, len(STAGES)+1)) and len({row["receiptId"] for row in receipts}) == len(receipts)
        predicates["requiredTerminalsRetained"] = predicates["completeStageDenominator"] and all(row["terminal"] == STAGE_TERMINALS[row["stage"]] for row in receipts)
        predicates["receiptChainComplete"] = predicates["completeStageDenominator"] and all(receipts[index]["previousReceiptId"] == (auth["receiptId"] if index == 0 else receipts[index-1]["receiptId"]) for index in range(len(receipts)))
        predicates["canonicalStateUnchanged"] = bool(receipts) and all(row["canonicalMissionStateSha256"] == value["canonicalMissionStateSha256"] for row in receipts)
        body_total = sum(row["evidenceBodyCount"] for row in receipts)
        predicates["privateEvidencePresent"] = value["privateEvidenceBodyCount"] == body_total and body_total > 0 and all(row["evidenceBodyCount"] > 0 for row in receipts)
        if not predicates["privateTier"] or any(row["evidenceTier"] != "private_local_attested" for row in receipts): reasons.append("PRIVATE_DISPOSITION_EVIDENCE_TIER_INVALID")
        for key, code in (("authorizationDistinctAndPrior", "NAMED_HUMAN_AUTHORIZATION_INVALID"), ("completeStageDenominator", "STAGE_DENOMINATOR_INVALID"), ("requiredTerminalsRetained", "STAGE_TERMINAL_INVALID"), ("receiptChainComplete", "STAGE_RECEIPT_CHAIN_INVALID"), ("privateEvidencePresent", "PRIVATE_EVIDENCE_DENOMINATOR_INVALID"), ("publicEvidenceAbsent", "PUBLIC_EVIDENCE_BODY_REFUSED"), ("canonicalStateUnchanged", "PACKET_CANONICAL_STATE_DRIFT"), ("sealedVerificationPassed", "SEALED_VERIFICATION_FAILED"), ("privateMaterialScanPassed", "PRIVATE_MATERIAL_SCAN_FAILED"), ("privateFlightCompleted", "PRIVATE_FLIGHT_COMPLETION_FALSE"), ("selfAttestationOnly", "SELF_ATTESTATION_BOUNDARY_INVALID"), ("strongerClaimsAbsent", "AUTHORITY_OR_CLAIM_PROMOTION_REFUSED")):
            if not predicates[key]: reasons.append(code)
    return make_attestation(DISPOSITION_SCHEMA, "axmheaddispositionbinding2", value, predicates, reasons)

def build_objects(profile: dict[str, Any], input_value: dict[str, Any]) -> dict[str, dict[str, Any]]:
    validate_profile_object(profile); validate_input_shape(input_value)
    source = build_source_binding(input_value["sourceBinding"])
    route = evaluate_route(input_value["route"]); continuity = evaluate_continuity(input_value["continuity"]); two_cell = evaluate_two_cell(input_value["twoCell"]); successor = evaluate_successor(input_value["successor"]); disposition = evaluate_disposition(input_value["privateDisposition"], input_value["campaignId"])
    components = (route, continuity, two_cell, successor, disposition)
    present = [row["evidence"]["present"] for row in components]
    if not any(present):
        terminal = "PREPARED_NOT_ARMED"; reasons = ["NAMED_HUMAN_AUTHORIZATION_ABSENT", "PRIVATE_RECEIPT_DENOMINATOR_ABSENT"]
    elif all(present) and all(row["valid"] for row in components):
        terminal = "PRIVATE_SELF_ATTESTED"; reasons = ["COMPLETE_PRIVATE_RECEIPT_DENOMINATOR_RECONSTRUCTED", "SELF_ATTESTATION_ONLY"]
    else:
        terminal = "HOLD"; reasons = []
        if not all(present): reasons.append("PARTIAL_PRIVATE_RECEIPT_DENOMINATOR")
        for row in components: reasons.extend(row["reasonCodes"])
        if all(present) and any(row["evidence"]["evidenceTier"] == "synthetic_simulation" for row in components): reasons.append("SYNTHETIC_EVIDENCE_CANNOT_SATISFY_PHYSICAL")
        reasons = sorted(set(reasons)) or ["PRIVATE_RECEIPT_DENOMINATOR_HELD"]
    predicates = {
        "exactPublicSourceGraph": True,
        "preflightReviewCompletedWithoutAuthorization": True,
        "routeValid": route["valid"], "continuityValid": continuity["valid"],
        "twoCellValid": two_cell["valid"], "successorValid": successor["valid"],
        "privateDispositionValid": disposition["valid"],
        "privatePhysicalFlightCompleted": terminal == "PRIVATE_SELF_ATTESTED",
        "selfAttestationOnly": terminal == "PRIVATE_SELF_ATTESTED",
        "publicEvidenceBodies": 0, "physicalExecutionStartedByJoin": False,
        "workersLaunched": 0, "listenersCreated": 0, "authority": "none",
    }
    join_body = {"schema": JOIN_SCHEMA, "profileId": PROFILE_ID, "campaignId": input_value["campaignId"], "sourceBindingId": source["sourceBindingId"], "routeAttestationId": route["attestationId"], "continuityAttestationId": continuity["attestationId"], "twoCellAttestationId": two_cell["attestationId"], "successorAttestationId": successor["attestationId"], "privateDispositionBindingId": disposition["attestationId"], "terminal": terminal, "reasonCodes": reasons, "predicates": predicates, "claimBoundary": CLAIM_BOUNDARY, "strongerClaims": copy.deepcopy(STRONGER_CLAIMS), "authority": "none"}
    join_body["joinId"] = content_id("axmheadphysicallonghauljoin2", join_body)
    public_body = {"schema": PUBLIC_SCHEMA, "profileId": PROFILE_ID, "campaignId": input_value["campaignId"], "joinId": join_body["joinId"], "sourceBindingId": source["sourceBindingId"], "terminal": terminal, "reasonCodes": reasons, "privatePhysicalFlightCompleted": terminal == "PRIVATE_SELF_ATTESTED", "selfAttestationOnly": terminal == "PRIVATE_SELF_ATTESTED", "publicEvidenceBodies": 0, "privateEvidenceBodies": input_value["privateDisposition"]["privateEvidenceBodyCount"] if terminal == "PRIVATE_SELF_ATTESTED" else 0, "physicalExecutionStartedByJoin": False, "missionVolumeMaterializedByJoin": False, "workersLaunched": 0, "listenersCreated": 0, "issue37AdvancedByJoin": False, "strongerClaims": copy.deepcopy(STRONGER_CLAIMS), "authority": "none", "claimBoundary": CLAIM_BOUNDARY}
    public_body["publicStatusId"] = content_id("axmheadphysicallonghaulpublicstatus2", public_body)
    return {"source": source, "route": route, "continuity": continuity, "twoCell": two_cell, "successor": successor, "disposition": disposition, "join": join_body, "public": public_body}

import argparse
import os
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

def object_without_id(value: dict[str, Any], key: str) -> dict[str, Any]:
    result = copy.deepcopy(value); result.pop(key, None); return result

def verify_id(value: dict[str, Any], key: str, prefix: str) -> None:
    observed = value.get(key)
    if type(observed) is not str or observed != content_id(prefix, object_without_id(value, key)):
        fail("CONTENT_ID_INVALID", key)

def refuse_symlinks_and_collect(root: Path) -> list[str]:
    paths: list[str] = []
    for path in root.rglob("*"):
        if path.is_symlink(): fail("SYMLINK_MEMBER_REFUSED", str(path))
        if path.is_file(): paths.append(path.relative_to(root).as_posix())
    return sorted(paths)

def verify_carrier(root: Path) -> dict[str, Any]:
    root = root.resolve()
    if not root.is_dir(): fail("CARRIER_DIRECTORY_REQUIRED", str(root))
    observed = refuse_symlinks_and_collect(root)
    expected = ["MANIFEST.json", *EXPECTED_MEMBER_PATHS]
    if observed != sorted(expected): fail("FILE_DENOMINATOR_INVALID", "carrier file denominator differs")
    for rel in ("MANIFEST.json", *EXPECTED_MEMBER_PATHS):
        if not rel.endswith(".json"):
            continue
        data = (root / rel).read_bytes()
        try:
            value = json.loads(data.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            fail("JSON_MEMBER_INVALID", rel)
        if data != canonical_json_bytes(value):
            fail("NON_CANONICAL_MEMBER_BYTES", rel)
    manifest = read_json(root / "MANIFEST.json")
    require_keys(manifest, {"schema", "profileId", "terminal", "joinId", "sourceBindingId", "publicStatusId", "files", "bindings", "nonClaims", "carrierId"}, "manifest")
    if manifest["schema"] != MANIFEST_SCHEMA or manifest["profileId"] != PROFILE_ID: fail("MANIFEST_IDENTITY_INVALID", "manifest")
    rows = []
    for rel in sorted(EXPECTED_MEMBER_PATHS):
        data = (root / rel).read_bytes(); rows.append({"path": rel, "size": len(data), "sha256": sha256_bytes(data)})
    if not strict_equal(manifest["files"], rows): fail("MANIFEST_FILE_ROWS_INVALID", "manifest")
    profile_bytes = (root / "RECOVERY/profile.json").read_bytes(); catalog_bytes = (root / "RECOVERY/fixture-catalog.json").read_bytes(); verifier_bytes = (root / "RECOVERY/verify_join.py").read_bytes()
    profile = validate_profile_object(json.loads(profile_bytes.decode("utf-8")))
    catalog = json.loads(catalog_bytes.decode("utf-8")); validate_fixture_catalog(profile, catalog)
    bindings = {"profileCanonicalSha256": sha256_bytes(canonical_json_bytes(profile)), "fixtureCatalogCanonicalSha256": sha256_bytes(canonical_json_bytes(catalog)), "standaloneVerifierSha256": sha256_bytes(verifier_bytes)}
    if not strict_equal(manifest["bindings"], bindings): fail("MANIFEST_BINDINGS_INVALID", "manifest")
    source = read_json(root / "JOIN/source-binding.json"); route = read_json(root / "JOIN/route-attestation.json"); continuity = read_json(root / "JOIN/continuity-attestation.json"); two_cell = read_json(root / "JOIN/two-cell-attestation.json"); successor = read_json(root / "JOIN/successor-attestation.json"); disposition = read_json(root / "JOIN/private-disposition-binding.json"); joined = read_json(root / "JOIN/join.json"); public = read_json(root / "PUBLIC/status.json")
    verify_id(source, "sourceBindingId", "axmheadsourcebinding2"); verify_id(route, "attestationId", "axmheadrouteattestation2"); verify_id(continuity, "attestationId", "axmheadcontinuityattestation2"); verify_id(two_cell, "attestationId", "axmheadtwocellattestation2"); verify_id(successor, "attestationId", "axmheadsuccessorattestation2"); verify_id(disposition, "attestationId", "axmheaddispositionbinding2"); verify_id(joined, "joinId", "axmheadphysicallonghauljoin2"); verify_id(public, "publicStatusId", "axmheadphysicallonghaulpublicstatus2")
    input_value = {"schema": INPUT_SCHEMA, "campaignId": joined["campaignId"], "sourceBinding": {"publicSources": source["publicSources"], "sourceDigests": source["sourceDigests"], "physicalFlightIssue": source["physicalFlightIssue"], "preflight": source["preflight"]}, "route": route["evidence"], "continuity": continuity["evidence"], "twoCell": two_cell["evidence"], "successor": successor["evidence"], "privateDisposition": disposition["evidence"]}
    expected_objects = build_objects(profile, input_value)
    actual_map = {"source": source, "route": route, "continuity": continuity, "twoCell": two_cell, "successor": successor, "disposition": disposition, "join": joined, "public": public}
    for key in actual_map:
        if not strict_equal(actual_map[key], expected_objects[key]): fail("RECONSTRUCTION_MISMATCH", key)
    if manifest["terminal"] != joined["terminal"] or manifest["joinId"] != joined["joinId"] or manifest["sourceBindingId"] != source["sourceBindingId"] or manifest["publicStatusId"] != public["publicStatusId"]: fail("MANIFEST_OBJECT_BINDING_INVALID", "manifest")
    if not strict_equal(manifest["nonClaims"], {"physicalExecutionStartedByJoin": False, "missionVolumeMaterializedByJoin": False, "workersLaunched": 0, "listenersCreated": 0, "publicEvidenceBodies": 0, "strongerClaims": STRONGER_CLAIMS, "authority": "none"}): fail("MANIFEST_NONCLAIM_INVALID", "manifest")
    carrier_basis = object_without_id(manifest, "carrierId")
    if manifest["carrierId"] != content_id("axmheadphysicallonghaulcarrier2", carrier_basis): fail("CARRIER_ID_INVALID", "manifest")
    return {"schema": VERIFICATION_SCHEMA, "status": "PASS", "terminal": joined["terminal"], "profileId": PROFILE_ID, "carrierId": manifest["carrierId"], "joinId": joined["joinId"], "sourceBindingId": source["sourceBindingId"], "publicStatusId": public["publicStatusId"], "authoritativeFiles": len(EXPECTED_MEMBER_PATHS), "bootstrapAuthenticated": False, "bootstrapVerifierSha256": None, "bootstrapProfileSha256": None, "privatePhysicalFlightCompleted": joined["terminal"] == "PRIVATE_SELF_ATTESTED", "selfAttestationOnly": joined["terminal"] == "PRIVATE_SELF_ATTESTED", "physicalExecutionStartedByJoin": False, "missionVolumeMaterializedByJoin": False, "workersLaunched": 0, "listenersCreated": 0, "publicEvidenceBodies": 0, "strongerClaims": copy.deepcopy(STRONGER_CLAIMS), "authority": "none"}

def output_overlaps(root: Path, out: Path) -> bool:
    root = root.resolve(); candidate = out.resolve(strict=False)
    if candidate == root or root in candidate.parents: return True
    if candidate.exists():
        stat = candidate.stat()
        for rel in ("MANIFEST.json", *EXPECTED_MEMBER_PATHS):
            member = root / rel
            if member.exists() and member.stat().st_dev == stat.st_dev and member.stat().st_ino == stat.st_ino: return True
    return False

def emit(value: dict[str, Any], out: Path | None) -> None:
    data = canonical_json_bytes(value)
    if out is not None: out.parent.mkdir(parents=True, exist_ok=True); out.write_bytes(data)
    sys.stdout.buffer.write(data)

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("carrier", type=Path); parser.add_argument("--out", type=Path); args = parser.parse_args(argv)
    try:
        if args.out is not None and output_overlaps(args.carrier, args.out): fail("VERDICT_OUTPUT_OVERLAP_REFUSED", str(args.out))
        receipt = verify_carrier(args.carrier); emit(receipt, args.out); return 0
    except JoinError as exc:
        receipt = {"schema": VERIFICATION_SCHEMA, "status": "REFUSED", "errorCode": exc.code, "message": exc.code, "bootstrapAuthenticated": False, "bootstrapVerifierSha256": None, "bootstrapProfileSha256": None, "physicalExecutionStartedByJoin": False, "missionVolumeMaterializedByJoin": False, "workersLaunched": 0, "listenersCreated": 0, "publicEvidenceBodies": 0, "strongerClaims": copy.deepcopy(STRONGER_CLAIMS), "authority": "none"}; emit(receipt, args.out); return 2
# JOIN v2 private-proof and single-campaign closure.
import hmac
import secrets

PRIVATE_PROOF_ROOT_SCHEMA = "axm-head/private-proof-root@1"
PRIVATE_PROOF_SCHEMA = "axm-head/private-proof-envelope@1"
PRIVATE_PROOF_ALGORITHM = "HMAC-SHA-256"
PROOF_ROOT_ID_RE = re.compile(r"^axmheadprivateproofroot1_[0-9a-f]{64}$")
HMAC_REF = re.compile(r"^hmac-sha256:[0-9a-f]{64}$")
PRIVATE_PROOF_ROOT_CLAIM_BOUNDARY = (
    "Private local authentication root for one issue-37 campaign. It authenticates one body-free "
    "receipt graph, remains outside the repository and carrier, and grants no physical, mission, "
    "command, targeting, engagement, effector, or weapons authority."
)
PRIVATE_PROOF_CLAIM_BOUNDARY = (
    "Body-free authentication envelope for one complete private receipt graph. Verification requires "
    "the separately custodied private proof root; the envelope contains no key or evidence body and "
    "grants no authority."
)
STAGE_COMPONENT_BINDINGS = {
    "BIND_GRACE": "authorization",
    "RUN_PERSONAL_FLOOR_BASELINE": "residentRoute",
    "RUN_HALO3_ACCELERATED": "acceleratorRoute",
    "VERIFY_PERSONAL_FLOOR_CONTINUITY": "continuity",
    "PARTITION_TWO_CELLS": "twoCell",
    "COLD_SUCCESSOR_VERIFY": "successor",
    "SEAL_PRIVATE_EVIDENCE": "sealedPackage",
}
PRIVATE_PROOF_LAW = {
    "rootSchema": PRIVATE_PROOF_ROOT_SCHEMA,
    "envelopeSchema": PRIVATE_PROOF_SCHEMA,
    "algorithm": PRIVATE_PROOF_ALGORITHM,
    "rootEmbeddedInCarrier": False,
    "rootRequiredForSelfAttestation": True,
    "rootRepositoryAllowed": False,
    "campaignBindingRequired": True,
    "componentBindingRequired": True,
    "stageComponentBindings": STAGE_COMPONENT_BINDINGS,
}

_legacy_evaluate_route = evaluate_route
_legacy_evaluate_continuity = evaluate_continuity
_legacy_evaluate_two_cell = evaluate_two_cell
_legacy_evaluate_successor = evaluate_successor
_legacy_evaluate_disposition = evaluate_disposition

def _sha256_ref(value: Any) -> str:
    return "sha256:" + sha256_bytes(canonical_json_bytes(value))

def _proof_root_digest_ref(proof_root_id: str) -> str:
    require_string(proof_root_id, "proofRootId", PROOF_ROOT_ID_RE)
    return "sha256:" + proof_root_id.rsplit("_", 1)[1]

def _component_scope(value: dict[str, Any], campaign: str, label: str) -> None:
    if value["campaignId"] != campaign:
        fail("COMPONENT_CAMPAIGN_MISMATCH", label)
    proof_root_id = value["proofRootId"]
    tier = value["evidenceTier"]
    if tier == "private_local_attested":
        require_string(proof_root_id, label + ".proofRootId", PROOF_ROOT_ID_RE)
    elif proof_root_id is not None:
        fail("NONPRIVATE_PROOF_ROOT_REFUSED", label)

def validate_profile_object(profile: dict[str, Any]) -> dict[str, Any]:
    require_keys(profile, {
        "schema", "profileId", "version", "status", "owningProject", "owningRepository",
        "publicSources", "sourceDigests", "physicalFlightIssue", "preflightLaw",
        "objectSchemas", "terminalStates", "packetStageSequence", "requiredStageTerminals",
        "dependenciesAbsent", "bootstrapRequired", "repositoryOutputAllowed", "networkRequired",
        "externalServiceCalls", "operationalCredentials", "privateEvidenceBodiesPublic",
        "workersLaunched", "listenersCreated", "authority", "strongerClaims", "claimBoundary",
        "fixtureCatalogCanonicalSha256", "standaloneVerifierSha256", "privateProofLaw",
    }, "profile")
    if profile["schema"] != PROFILE_SCHEMA or profile["profileId"] != PROFILE_ID or profile["version"] != 2:
        fail("PROFILE_IDENTITY_INVALID", "profile")
    if profile["status"] != "candidate_contract_only" or profile["owningProject"] != "Estate" or profile["owningRepository"] != "BigBirdReturns/ai-execution-audit":
        fail("PROFILE_SCOPE_INVALID", "profile")
    if not strict_equal(profile["publicSources"], PUBLIC_SOURCES) or not strict_equal(profile["sourceDigests"], SOURCE_DIGESTS):
        fail("SOURCE_COORDINATES_INVALID", "profile")
    if not strict_equal(profile["physicalFlightIssue"], ISSUE) or not strict_equal(profile["preflightLaw"], PREFLIGHT):
        fail("SOURCE_LAW_INVALID", "profile")
    if profile["objectSchemas"] != list(OBJECT_SCHEMAS) or profile["terminalStates"] != list(TERMINALS):
        fail("OBJECT_DENOMINATOR_INVALID", "profile")
    if profile["packetStageSequence"] != list(STAGES) or not strict_equal(profile["requiredStageTerminals"], STAGE_TERMINALS):
        fail("STAGE_DENOMINATOR_INVALID", "profile")
    if profile["dependenciesAbsent"] != list(DEPENDENCIES_ABSENT):
        fail("DEPENDENCY_DENOMINATOR_INVALID", "profile")
    if not strict_equal(profile["privateProofLaw"], PRIVATE_PROOF_LAW):
        fail("PRIVATE_PROOF_LAW_INVALID", "profile")
    if profile["bootstrapRequired"] is not True or profile["repositoryOutputAllowed"] is not False or profile["networkRequired"] is not False:
        fail("PROFILE_CUSTODY_INVALID", "profile")
    expected = {
        "externalServiceCalls": 0, "operationalCredentials": 0,
        "privateEvidenceBodiesPublic": 0, "workersLaunched": 0,
        "listenersCreated": 0, "authority": "none",
        "strongerClaims": STRONGER_CLAIMS, "claimBoundary": CLAIM_BOUNDARY,
    }
    for key, wanted in expected.items():
        if not strict_equal(profile[key], wanted):
            fail("PROFILE_NONCLAIM_INVALID", key)
    require_string(profile["fixtureCatalogCanonicalSha256"], "fixture digest", HEX64)
    require_string(profile["standaloneVerifierSha256"], "verifier digest", HEX64)
    return profile

def validate_profile(path: Path) -> dict[str, Any]:
    return validate_profile_object(read_json(path))

def validate_route_shape(value: dict[str, Any], campaign: str | None = None) -> None:
    require_keys(value, {"campaignId", "proofRootId", "present", "evidenceTier", "memoryPoolingUsed", "residentRoute", "acceleratorRoute"}, "route")
    campaign = campaign or require_string(value["campaignId"], "route.campaignId", ID_RE)
    require_string(value["campaignId"], "route.campaignId", ID_RE)
    require_bool(value["present"], "route.present")
    require_bool(value["memoryPoolingUsed"], "route.memoryPoolingUsed")
    require_string(value["evidenceTier"], "route.evidenceTier")
    _component_scope(value, campaign, "route")
    if not value["present"]:
        if value["residentRoute"] is not None or value["acceleratorRoute"] is not None:
            fail("ABSENT_ROUTE_INVALID", "route")
        return
    for label in ("residentRoute", "acceleratorRoute"):
        row = value[label]
        if type(row) is not dict:
            fail("ROUTE_OBJECT_REQUIRED", label)
        require_keys(row, {"routeClass", "memoryMiB", "requiredMemoryMiB", "missionSha256", "outputSha256", "classificationSha256", "verifierSha256", "throughputMilliItemsPerSecond", "independentlyVerified", "receiptId"}, label)
        require_string(row["routeClass"], label + ".routeClass", ID_RE)
        require_int(row["memoryMiB"], label + ".memoryMiB", 1)
        require_int(row["requiredMemoryMiB"], label + ".requiredMemoryMiB", 1)
        for key in ("missionSha256", "outputSha256", "classificationSha256", "verifierSha256", "receiptId"):
            require_string(row[key], label + "." + key, SHA256_REF)
        require_int(row["throughputMilliItemsPerSecond"], label + ".throughput", 1)
        require_bool(row["independentlyVerified"], label + ".independentlyVerified")

def validate_continuity_shape(value: dict[str, Any], campaign: str | None = None) -> None:
    require_keys(value, {"campaignId", "proofRootId", "present", "evidenceTier", "baselineOutputSha256", "postRemovalOutputSha256", "canonicalStateBeforeSha256", "canonicalStateAfterSha256", "residentFloorAvailableAfter", "halo3AbsentAfter", "latticeAbsentDuringLocalContinuity", "independentlyVerified", "receiptId"}, "continuity")
    campaign = campaign or require_string(value["campaignId"], "continuity.campaignId", ID_RE)
    require_string(value["campaignId"], "continuity.campaignId", ID_RE)
    require_bool(value["present"], "continuity.present")
    require_string(value["evidenceTier"], "continuity.evidenceTier")
    _component_scope(value, campaign, "continuity")
    for key in ("residentFloorAvailableAfter", "halo3AbsentAfter", "latticeAbsentDuringLocalContinuity", "independentlyVerified"):
        require_bool(value[key], "continuity." + key)
    for key in ("baselineOutputSha256", "postRemovalOutputSha256", "canonicalStateBeforeSha256", "canonicalStateAfterSha256", "receiptId"):
        if value["present"]:
            require_string(value[key], "continuity." + key, SHA256_REF)
        elif value[key] is not None:
            fail("ABSENT_CONTINUITY_INVALID", key)

def validate_two_cell_shape(value: dict[str, Any], campaign: str | None = None) -> None:
    require_keys(value, {"campaignId", "proofRootId", "present", "evidenceTier", "commonParentSha256", "leftChildSha256", "rightChildSha256", "leftHostClassSha256", "rightHostClassSha256", "reunionTerminal", "automaticMergeAllowed", "retainedChildSha256", "unresolvedObligationCount", "independentlyVerified", "receiptId"}, "twoCell")
    campaign = campaign or require_string(value["campaignId"], "twoCell.campaignId", ID_RE)
    require_string(value["campaignId"], "twoCell.campaignId", ID_RE)
    require_bool(value["present"], "twoCell.present")
    require_string(value["evidenceTier"], "twoCell.evidenceTier")
    _component_scope(value, campaign, "twoCell")
    require_bool(value["automaticMergeAllowed"], "twoCell.automaticMergeAllowed")
    require_bool(value["independentlyVerified"], "twoCell.independentlyVerified")
    require_int(value["unresolvedObligationCount"], "twoCell.unresolvedObligationCount")
    if type(value["retainedChildSha256"]) is not list:
        fail("ARRAY_REQUIRED", "retainedChildSha256")
    for key in ("commonParentSha256", "leftChildSha256", "rightChildSha256", "leftHostClassSha256", "rightHostClassSha256", "receiptId"):
        if value["present"]:
            require_string(value[key], "twoCell." + key, SHA256_REF)
        elif value[key] is not None:
            fail("ABSENT_TWO_CELL_INVALID", key)
    if value["present"]:
        require_string(value["reunionTerminal"], "twoCell.reunionTerminal")
    elif value["reunionTerminal"] is not None or value["retainedChildSha256"]:
        fail("ABSENT_TWO_CELL_INVALID", "twoCell")

def validate_successor_shape(value: dict[str, Any], campaign: str | None = None) -> None:
    require_keys(value, {"campaignId", "proofRootId", "present", "evidenceTier", "originalHeadClassSha256", "replacementHeadClassSha256", "missionId", "canonicalStateSha256", "proofRootSha256", "namedHumanAuthorityClass", "unresolvedObligationCount", "nextSafeActionSha256", "answers", "verificationTerminal", "dependenciesAbsent", "independentlyVerified", "receiptId"}, "successor")
    campaign = campaign or require_string(value["campaignId"], "successor.campaignId", ID_RE)
    require_string(value["campaignId"], "successor.campaignId", ID_RE)
    require_bool(value["present"], "successor.present")
    require_string(value["evidenceTier"], "successor.evidenceTier")
    _component_scope(value, campaign, "successor")
    require_int(value["unresolvedObligationCount"], "successor.unresolvedObligationCount")
    require_bool(value["independentlyVerified"], "successor.independentlyVerified")
    if type(value["answers"]) is not dict or type(value["dependenciesAbsent"]) is not list:
        fail("SUCCESSOR_COLLECTION_INVALID", "successor")
    for key in ("originalHeadClassSha256", "replacementHeadClassSha256", "canonicalStateSha256", "proofRootSha256", "nextSafeActionSha256", "receiptId"):
        if value["present"]:
            require_string(value[key], "successor." + key, SHA256_REF)
        elif value[key] is not None:
            fail("ABSENT_SUCCESSOR_INVALID", key)
    if value["present"]:
        require_string(value["missionId"], "successor.missionId", ID_RE)
        require_string(value["namedHumanAuthorityClass"], "successor.namedHumanAuthorityClass", ID_RE)
        require_string(value["verificationTerminal"], "successor.verificationTerminal")
    elif any(value[key] is not None for key in ("missionId", "namedHumanAuthorityClass", "verificationTerminal")) or value["answers"] or value["dependenciesAbsent"]:
        fail("ABSENT_SUCCESSOR_INVALID", "successor")

def validate_authorization_shape(value: dict[str, Any], campaign: str) -> None:
    require_keys(value, {"schema", "campaignId", "proofRootId", "present", "evidenceTier", "receiptId", "preflightCarrierId", "authorizationSequence", "firstPhysicalReceiptSequence", "namedHumanAuthorityClass", "terminal"}, "authorization")
    if value["schema"] != AUTH_SCHEMA:
        fail("AUTHORIZATION_SCHEMA_INVALID", "authorization")
    require_string(value["campaignId"], "authorization.campaignId", ID_RE)
    require_bool(value["present"], "authorization.present")
    require_string(value["evidenceTier"], "authorization.evidenceTier")
    _component_scope(value, campaign, "authorization")
    if value["preflightCarrierId"] != PREFLIGHT["carrierId"] or value["campaignId"] != campaign:
        fail("AUTHORIZATION_BINDING_INVALID", "authorization")
    if value["present"]:
        require_string(value["receiptId"], "authorization.receiptId", SHA256_REF)
        require_int(value["authorizationSequence"], "authorization.authorizationSequence")
        require_int(value["firstPhysicalReceiptSequence"], "authorization.firstPhysicalReceiptSequence", 1)
        require_string(value["namedHumanAuthorityClass"], "authorization.namedHumanAuthorityClass", ID_RE)
        require_string(value["terminal"], "authorization.terminal")
    elif any(value[key] is not None for key in ("receiptId", "authorizationSequence", "firstPhysicalReceiptSequence", "namedHumanAuthorityClass")) or value["terminal"] != "ABSENT":
        fail("ABSENT_AUTHORIZATION_INVALID", "authorization")

def validate_stage_receipt_shape(row: dict[str, Any], index: int, campaign: str | None = None) -> None:
    require_keys(row, {"schema", "campaignId", "proofRootId", "sequence", "stage", "terminal", "receiptId", "previousReceiptId", "evidenceTier", "evidenceBodyCount", "evidenceRootSha256", "canonicalMissionStateSha256"}, f"stage[{index}]")
    if row["schema"] != STAGE_SCHEMA:
        fail("STAGE_SCHEMA_INVALID", str(index))
    campaign = campaign or require_string(row["campaignId"], f"stage[{index}].campaignId", ID_RE)
    require_string(row["campaignId"], f"stage[{index}].campaignId", ID_RE)
    _component_scope(row, campaign, f"stage[{index}]")
    require_int(row["sequence"], f"stage[{index}].sequence", 1)
    require_string(row["stage"], f"stage[{index}].stage", ID_RE)
    require_string(row["terminal"], f"stage[{index}].terminal", ID_RE)
    for key in ("receiptId", "previousReceiptId", "evidenceRootSha256", "canonicalMissionStateSha256"):
        require_string(row[key], f"stage[{index}].{key}", SHA256_REF)
    require_string(row["evidenceTier"], f"stage[{index}].evidenceTier")
    require_int(row["evidenceBodyCount"], f"stage[{index}].evidenceBodyCount")

def validate_private_proof_shape(value: dict[str, Any] | None, campaign: str, proof_root_id: str | None, disposition_present: bool, evidence_tier: str) -> None:
    if value is None:
        return
    if not disposition_present or evidence_tier != "private_local_attested":
        fail("NONPRIVATE_PROOF_ENVELOPE_REFUSED", "privateDisposition.proof")
    require_keys(value, {"schema", "algorithm", "campaignId", "proofRootId", "graphSha256", "authorizationReceiptId", "stageTailReceiptId", "componentBindings", "authenticationTag", "claimBoundary"}, "privateDisposition.proof")
    if value["schema"] != PRIVATE_PROOF_SCHEMA or value["algorithm"] != PRIVATE_PROOF_ALGORITHM:
        fail("PRIVATE_PROOF_SCHEMA_INVALID", "privateDisposition.proof")
    if value["campaignId"] != campaign or value["proofRootId"] != proof_root_id:
        fail("PRIVATE_PROOF_SCOPE_INVALID", "privateDisposition.proof")
    require_string(value["proofRootId"], "privateDisposition.proof.proofRootId", PROOF_ROOT_ID_RE)
    for key in ("graphSha256", "authorizationReceiptId", "stageTailReceiptId"):
        require_string(value[key], "privateDisposition.proof." + key, SHA256_REF)
    require_keys(value["componentBindings"], {"sourceBindingSha256", "routeSha256", "continuitySha256", "twoCellSha256", "successorSha256", "authorizationSha256", "stageChainSha256", "privateDispositionSha256"}, "privateDisposition.proof.componentBindings")
    for key, child in value["componentBindings"].items():
        require_string(child, "privateDisposition.proof.componentBindings." + key, SHA256_REF)
    require_string(value["authenticationTag"], "privateDisposition.proof.authenticationTag", HMAC_REF)
    if value["claimBoundary"] != PRIVATE_PROOF_CLAIM_BOUNDARY:
        fail("PRIVATE_PROOF_CLAIM_BOUNDARY_INVALID", "privateDisposition.proof")

def validate_disposition_shape(value: dict[str, Any], campaign: str) -> None:
    require_keys(value, {"campaignId", "proofRootId", "present", "evidenceTier", "authorization", "stageReceipts", "publicEvidenceBodyCount", "privateEvidenceBodyCount", "canonicalMissionStateSha256", "sealedVerificationTerminal", "sealedPackageSha256", "sourceDispositionSha256", "privateMaterialScanTerminal", "privatePhysicalFlightCompleted", "selfAttestationOnly", "strongerClaims", "authority", "proof"}, "privateDisposition")
    require_string(value["campaignId"], "privateDisposition.campaignId", ID_RE)
    require_bool(value["present"], "privateDisposition.present")
    require_string(value["evidenceTier"], "privateDisposition.evidenceTier")
    _component_scope(value, campaign, "privateDisposition")
    validate_authorization_shape(value["authorization"], campaign)
    if type(value["stageReceipts"]) is not list:
        fail("ARRAY_REQUIRED", "stageReceipts")
    for index, row in enumerate(value["stageReceipts"]):
        if type(row) is not dict:
            fail("STAGE_OBJECT_REQUIRED", str(index))
        validate_stage_receipt_shape(row, index, campaign)
    require_int(value["publicEvidenceBodyCount"], "publicEvidenceBodyCount")
    require_int(value["privateEvidenceBodyCount"], "privateEvidenceBodyCount")
    require_bool(value["privatePhysicalFlightCompleted"], "privatePhysicalFlightCompleted")
    require_bool(value["selfAttestationOnly"], "selfAttestationOnly")
    if not strict_equal(value["strongerClaims"], STRONGER_CLAIMS) or value["authority"] != "none":
        fail("AUTHORITY_PROMOTION_REFUSED", "privateDisposition")
    for key in ("canonicalMissionStateSha256", "sealedPackageSha256", "sourceDispositionSha256"):
        if value["present"]:
            require_string(value[key], "privateDisposition." + key, SHA256_REF)
        elif value[key] is not None:
            fail("ABSENT_DISPOSITION_INVALID", key)
    if value["present"]:
        require_string(value["sealedVerificationTerminal"], "sealedVerificationTerminal")
        require_string(value["privateMaterialScanTerminal"], "privateMaterialScanTerminal")
    elif any(value[key] is not None for key in ("sealedVerificationTerminal", "privateMaterialScanTerminal")) or value["stageReceipts"]:
        fail("ABSENT_DISPOSITION_INVALID", "privateDisposition")
    validate_private_proof_shape(value["proof"], campaign, value["proofRootId"], value["present"], value["evidenceTier"])

def validate_input_shape(value: dict[str, Any]) -> dict[str, Any]:
    if type(value) is not dict:
        fail("INPUT_OBJECT_REQUIRED", "input")
    require_keys(value, {"schema", "campaignId", "sourceBinding", "route", "continuity", "twoCell", "successor", "privateDisposition"}, "input")
    if value["schema"] != INPUT_SCHEMA:
        fail("INPUT_SCHEMA_INVALID", "input")
    campaign = require_string(value["campaignId"], "campaignId", ID_RE)
    if type(value["sourceBinding"]) is not dict:
        fail("SOURCE_BINDING_OBJECT_REQUIRED", "sourceBinding")
    validate_source_binding(value["sourceBinding"])
    for key in ("route", "continuity", "twoCell", "successor", "privateDisposition"):
        if type(value[key]) is not dict:
            fail("COMPONENT_OBJECT_REQUIRED", key)
    validate_route_shape(value["route"], campaign)
    validate_continuity_shape(value["continuity"], campaign)
    validate_two_cell_shape(value["twoCell"], campaign)
    validate_successor_shape(value["successor"], campaign)
    validate_disposition_shape(value["privateDisposition"], campaign)
    scan_private(value)
    return value

def _root_body(root: dict[str, Any]) -> tuple[dict[str, Any], bytes]:
    require_keys(root, {"schema", "proofRootId", "campaignId", "preflightCarrierId", "physicalFlightIssue", "algorithm", "status", "keySha256", "keyHex", "authority", "claimBoundary"}, "private proof root")
    if root["schema"] != PRIVATE_PROOF_ROOT_SCHEMA or root["algorithm"] != PRIVATE_PROOF_ALGORITHM or root["status"] != "private_local_authentication_root":
        fail("PRIVATE_PROOF_ROOT_IDENTITY_INVALID", "private proof root")
    campaign = require_string(root["campaignId"], "private proof root campaign", ID_RE)
    if root["preflightCarrierId"] != PREFLIGHT["carrierId"] or not strict_equal(root["physicalFlightIssue"], ISSUE):
        fail("PRIVATE_PROOF_ROOT_SOURCE_INVALID", "private proof root")
    require_string(root["keySha256"], "private proof root key digest", SHA256_REF)
    key_hex = require_string(root["keyHex"], "private proof root key", HEX64)
    key = bytes.fromhex(key_hex)
    if root["keySha256"] != "sha256:" + sha256_bytes(key):
        fail("PRIVATE_PROOF_ROOT_KEY_INVALID", "private proof root")
    if root["authority"] != "none" or root["claimBoundary"] != PRIVATE_PROOF_ROOT_CLAIM_BOUNDARY:
        fail("PRIVATE_PROOF_ROOT_BOUNDARY_INVALID", "private proof root")
    body = {
        "schema": root["schema"], "campaignId": campaign,
        "preflightCarrierId": root["preflightCarrierId"],
        "physicalFlightIssue": root["physicalFlightIssue"],
        "algorithm": root["algorithm"], "status": root["status"],
        "keySha256": root["keySha256"], "authority": root["authority"],
        "claimBoundary": root["claimBoundary"],
    }
    expected = content_id("axmheadprivateproofroot1", body)
    if root["proofRootId"] != expected:
        fail("PRIVATE_PROOF_ROOT_ID_INVALID", "private proof root")
    return body, key

def create_private_proof_root(campaign: str, key: bytes | None = None) -> dict[str, Any]:
    campaign = require_string(campaign, "campaignId", ID_RE)
    key = key if key is not None else secrets.token_bytes(32)
    if type(key) is not bytes or len(key) != 32:
        fail("PRIVATE_PROOF_ROOT_KEY_INVALID", "private proof root")
    body = {
        "schema": PRIVATE_PROOF_ROOT_SCHEMA,
        "campaignId": campaign,
        "preflightCarrierId": PREFLIGHT["carrierId"],
        "physicalFlightIssue": copy.deepcopy(ISSUE),
        "algorithm": PRIVATE_PROOF_ALGORITHM,
        "status": "private_local_authentication_root",
        "keySha256": "sha256:" + sha256_bytes(key),
        "authority": "none",
        "claimBoundary": PRIVATE_PROOF_ROOT_CLAIM_BOUNDARY,
    }
    return {**body, "proofRootId": content_id("axmheadprivateproofroot1", body), "keyHex": key.hex()}

def load_private_proof_root(path: Path) -> dict[str, Any]:
    candidate = path.resolve()
    repository = REPOSITORY_ROOT.resolve()
    if Path(__file__).name != "verify_join.py" and (candidate == repository or repository in candidate.parents):
        fail("PRIVATE_PROOF_ROOT_REPOSITORY_REFUSED", "private proof root")
    if not candidate.is_file() or candidate.is_symlink():
        fail("PRIVATE_PROOF_ROOT_FILE_INVALID", "private proof root")
    root = read_json(candidate)
    _root_body(root)
    return root

def _disposition_without_proof(value: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(value)
    result["proof"] = None
    return result

def _private_graph_basis(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": value["schema"],
        "campaignId": value["campaignId"],
        "sourceBinding": copy.deepcopy(value["sourceBinding"]),
        "route": copy.deepcopy(value["route"]),
        "continuity": copy.deepcopy(value["continuity"]),
        "twoCell": copy.deepcopy(value["twoCell"]),
        "successor": copy.deepcopy(value["successor"]),
        "privateDisposition": _disposition_without_proof(value["privateDisposition"]),
    }

def _proof_body(value: dict[str, Any], proof_root_id: str) -> dict[str, Any]:
    disposition = value["privateDisposition"]
    receipts = disposition["stageReceipts"]
    authorization = disposition["authorization"]
    graph = _private_graph_basis(value)
    bindings = {
        "sourceBindingSha256": _sha256_ref(value["sourceBinding"]),
        "routeSha256": _sha256_ref(value["route"]),
        "continuitySha256": _sha256_ref(value["continuity"]),
        "twoCellSha256": _sha256_ref(value["twoCell"]),
        "successorSha256": _sha256_ref(value["successor"]),
        "authorizationSha256": _sha256_ref(authorization),
        "stageChainSha256": _sha256_ref(receipts),
        "privateDispositionSha256": _sha256_ref(_disposition_without_proof(disposition)),
    }
    return {
        "schema": PRIVATE_PROOF_SCHEMA,
        "algorithm": PRIVATE_PROOF_ALGORITHM,
        "campaignId": value["campaignId"],
        "proofRootId": proof_root_id,
        "graphSha256": _sha256_ref(graph),
        "authorizationReceiptId": authorization["receiptId"],
        "stageTailReceiptId": receipts[-1]["receiptId"] if receipts else "sha256:" + "0" * 64,
        "componentBindings": bindings,
        "claimBoundary": PRIVATE_PROOF_CLAIM_BOUNDARY,
    }

def authenticate_private_input(value: dict[str, Any], root: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(value)
    result["privateDisposition"]["proof"] = None
    validate_input_shape(result)
    _, key = _root_body(root)
    campaign = result["campaignId"]
    proof_root_id = root["proofRootId"]
    if root["campaignId"] != campaign:
        fail("PRIVATE_PROOF_ROOT_CAMPAIGN_MISMATCH", "private proof root")
    components = [result["route"], result["continuity"], result["twoCell"], result["successor"], result["privateDisposition"]]
    if not all(component["present"] and component["evidenceTier"] == "private_local_attested" for component in components):
        fail("PRIVATE_PROOF_DENOMINATOR_INCOMPLETE", "private input")
    scoped = [*components, result["privateDisposition"]["authorization"], *result["privateDisposition"]["stageReceipts"]]
    if any(row["campaignId"] != campaign or row["proofRootId"] != proof_root_id for row in scoped):
        fail("PRIVATE_PROOF_SCOPE_INVALID", "private input")
    body = _proof_body(result, proof_root_id)
    tag = hmac.new(key, canonical_json_bytes(body), hashlib.sha256).hexdigest()
    result["privateDisposition"]["proof"] = {**body, "authenticationTag": "hmac-sha256:" + tag}
    validate_input_shape(result)
    return result

def private_proof_authenticated(value: dict[str, Any], root: dict[str, Any] | None) -> bool:
    proof = value["privateDisposition"]["proof"]
    if proof is None or root is None:
        return False
    try:
        _, key = _root_body(root)
        if root["campaignId"] != value["campaignId"] or root["proofRootId"] != proof["proofRootId"]:
            return False
        expected_body = _proof_body(value, root["proofRootId"])
        actual_body = {key_name: copy.deepcopy(proof[key_name]) for key_name in expected_body}
        if not strict_equal(actual_body, expected_body):
            return False
        expected_tag = "hmac-sha256:" + hmac.new(key, canonical_json_bytes(expected_body), hashlib.sha256).hexdigest()
        return hmac.compare_digest(proof["authenticationTag"], expected_tag)
    except JoinError:
        return False

def _augment_attestation(value: dict[str, Any], prefix: str, predicates: dict[str, bool], reasons: list[str]) -> dict[str, Any]:
    result = copy.deepcopy(value)
    result["predicates"].update(predicates)
    result["reasonCodes"] = sorted(set([*result["reasonCodes"], *reasons]))
    result["valid"] = not result["reasonCodes"]
    body = {key: child for key, child in result.items() if key != "attestationId"}
    result["attestationId"] = content_id(prefix, body)
    return result

def _scope_predicates(value: dict[str, Any], campaign: str, proof_root_id: str | None) -> tuple[dict[str, bool], list[str]]:
    campaign_bound = value["campaignId"] == campaign
    proof_bound = (
        value["evidenceTier"] != "private_local_attested"
        or (proof_root_id is not None and value["proofRootId"] == proof_root_id)
    )
    reasons = []
    if not campaign_bound:
        reasons.append("COMPONENT_CAMPAIGN_MISMATCH")
    if not proof_bound:
        reasons.append("COMPONENT_PROOF_ROOT_MISMATCH")
    return {"campaignBound": campaign_bound, "proofRootBound": proof_bound}, reasons

def _cross_stage_predicates(value: dict[str, Any]) -> tuple[dict[str, bool], list[str]]:
    route = value["route"]
    continuity = value["continuity"]
    two_cell = value["twoCell"]
    successor = value["successor"]
    disposition = value["privateDisposition"]
    receipts = disposition["stageReceipts"]
    by_stage = {row["stage"]: row for row in receipts}
    all_present = all(row["present"] for row in (route, continuity, two_cell, successor, disposition))
    predicates = {
        "singleCampaign": False,
        "singleProofRoot": False,
        "routeContinuityLinked": False,
        "canonicalStateLinked": False,
        "successorProofRootLinked": False,
        "stageComponentReceiptsLinked": False,
    }
    reasons: list[str] = []
    if not all_present:
        return predicates, reasons
    campaign = value["campaignId"]
    scoped = [route, continuity, two_cell, successor, disposition, disposition["authorization"], *receipts]
    predicates["singleCampaign"] = all(row["campaignId"] == campaign for row in scoped)
    roots = {row["proofRootId"] for row in scoped}
    predicates["singleProofRoot"] = len(roots) == 1 and None not in roots
    resident = route["residentRoute"]
    accelerator = route["acceleratorRoute"]
    predicates["routeContinuityLinked"] = (
        resident["outputSha256"] == accelerator["outputSha256"]
        == continuity["baselineOutputSha256"]
        == continuity["postRemovalOutputSha256"]
    )
    canonical = disposition["canonicalMissionStateSha256"]
    predicates["canonicalStateLinked"] = (
        continuity["canonicalStateBeforeSha256"] == canonical
        and continuity["canonicalStateAfterSha256"] == canonical
        and two_cell["commonParentSha256"] == canonical
        and successor["canonicalStateSha256"] == canonical
    )
    proof_root_id = disposition["proofRootId"]
    predicates["successorProofRootLinked"] = (
        proof_root_id is not None
        and successor["proofRootSha256"] == _proof_root_digest_ref(proof_root_id)
    )
    expected_stage_roots = {
        "BIND_GRACE": disposition["authorization"]["receiptId"],
        "RUN_PERSONAL_FLOOR_BASELINE": resident["receiptId"],
        "RUN_HALO3_ACCELERATED": accelerator["receiptId"],
        "VERIFY_PERSONAL_FLOOR_CONTINUITY": continuity["receiptId"],
        "PARTITION_TWO_CELLS": two_cell["receiptId"],
        "COLD_SUCCESSOR_VERIFY": successor["receiptId"],
        "SEAL_PRIVATE_EVIDENCE": disposition["sealedPackageSha256"],
    }
    predicates["stageComponentReceiptsLinked"] = (
        set(expected_stage_roots).issubset(by_stage)
        and all(by_stage[stage]["evidenceRootSha256"] == receipt for stage, receipt in expected_stage_roots.items())
    )
    for key, code in (
        ("singleCampaign", "CROSS_COMPONENT_CAMPAIGN_MISMATCH"),
        ("singleProofRoot", "CROSS_COMPONENT_PROOF_ROOT_MISMATCH"),
        ("routeContinuityLinked", "ROUTE_CONTINUITY_LINK_MISMATCH"),
        ("canonicalStateLinked", "CANONICAL_STATE_CHAIN_MISMATCH"),
        ("successorProofRootLinked", "SUCCESSOR_PROOF_ROOT_MISMATCH"),
        ("stageComponentReceiptsLinked", "STAGE_COMPONENT_RECEIPT_LINK_MISMATCH"),
    ):
        if not predicates[key]:
            reasons.append(code)
    return predicates, reasons

def build_objects(profile: dict[str, Any], input_value: dict[str, Any], proof_root: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    if proof_root is None:
        proof_root = globals().get("_ACTIVE_PRIVATE_PROOF_ROOT")
    if proof_root is not None:
        _root_body(proof_root)
    validate_profile_object(profile)
    validate_input_shape(input_value)
    source = build_source_binding(input_value["sourceBinding"])
    campaign = input_value["campaignId"]
    proof_root_id = proof_root["proofRootId"] if proof_root is not None else None
    route = _augment_attestation(
        _legacy_evaluate_route(input_value["route"]),
        "axmheadrouteattestation2",
        *_scope_predicates(input_value["route"], campaign, proof_root_id),
    )
    continuity = _augment_attestation(
        _legacy_evaluate_continuity(input_value["continuity"]),
        "axmheadcontinuityattestation2",
        *_scope_predicates(input_value["continuity"], campaign, proof_root_id),
    )
    two_cell = _augment_attestation(
        _legacy_evaluate_two_cell(input_value["twoCell"]),
        "axmheadtwocellattestation2",
        *_scope_predicates(input_value["twoCell"], campaign, proof_root_id),
    )
    successor = _augment_attestation(
        _legacy_evaluate_successor(input_value["successor"]),
        "axmheadsuccessorattestation2",
        *_scope_predicates(input_value["successor"], campaign, proof_root_id),
    )
    disposition_base = _legacy_evaluate_disposition(input_value["privateDisposition"], campaign)
    scope_predicates, scope_reasons = _scope_predicates(input_value["privateDisposition"], campaign, proof_root_id)
    chain_predicates, chain_reasons = _cross_stage_predicates(input_value)
    proof_authenticated = private_proof_authenticated(input_value, proof_root)
    proof_reasons: list[str] = []
    if input_value["privateDisposition"]["present"] and not proof_authenticated:
        proof_reasons.append("PRIVATE_PROOF_NOT_AUTHENTICATED")
    disposition = _augment_attestation(
        disposition_base,
        "axmheaddispositionbinding2",
        {**scope_predicates, **chain_predicates, "privateProofAuthenticated": proof_authenticated},
        [*scope_reasons, *chain_reasons, *proof_reasons],
    )
    components = (route, continuity, two_cell, successor, disposition)
    present = [row["evidence"]["present"] for row in components]
    if not any(present):
        terminal = "PREPARED_NOT_ARMED"
        reasons = ["NAMED_HUMAN_AUTHORIZATION_ABSENT", "PRIVATE_RECEIPT_DENOMINATOR_ABSENT"]
    elif all(present) and all(row["valid"] for row in components) and proof_authenticated:
        terminal = "PRIVATE_SELF_ATTESTED"
        reasons = ["COMPLETE_AUTHENTICATED_PRIVATE_RECEIPT_GRAPH_RECONSTRUCTED", "SELF_ATTESTATION_ONLY"]
    else:
        terminal = "HOLD"
        reasons = []
        if not all(present):
            reasons.append("PARTIAL_PRIVATE_RECEIPT_DENOMINATOR")
        for row in components:
            reasons.extend(row["reasonCodes"])
        if all(present) and any(row["evidence"]["evidenceTier"] == "synthetic_simulation" for row in components):
            reasons.append("SYNTHETIC_EVIDENCE_CANNOT_SATISFY_PHYSICAL")
        reasons = sorted(set(reasons)) or ["PRIVATE_RECEIPT_DENOMINATOR_HELD"]
    predicates = {
        "exactPublicSourceGraph": True,
        "preflightReviewCompletedWithoutAuthorization": True,
        "routeValid": route["valid"],
        "continuityValid": continuity["valid"],
        "twoCellValid": two_cell["valid"],
        "successorValid": successor["valid"],
        "privateDispositionValid": disposition["valid"],
        "privateProofAuthenticated": proof_authenticated,
        "privatePhysicalFlightCompleted": terminal == "PRIVATE_SELF_ATTESTED",
        "selfAttestationOnly": terminal == "PRIVATE_SELF_ATTESTED",
        "publicEvidenceBodies": 0,
        "physicalExecutionStartedByJoin": False,
        "workersLaunched": 0,
        "listenersCreated": 0,
        "authority": "none",
    }
    join_body = {
        "schema": JOIN_SCHEMA, "profileId": PROFILE_ID, "campaignId": campaign,
        "sourceBindingId": source["sourceBindingId"],
        "routeAttestationId": route["attestationId"],
        "continuityAttestationId": continuity["attestationId"],
        "twoCellAttestationId": two_cell["attestationId"],
        "successorAttestationId": successor["attestationId"],
        "privateDispositionBindingId": disposition["attestationId"],
        "terminal": terminal, "reasonCodes": reasons, "predicates": predicates,
        "claimBoundary": CLAIM_BOUNDARY, "strongerClaims": copy.deepcopy(STRONGER_CLAIMS),
        "authority": "none",
    }
    join_body["joinId"] = content_id("axmheadphysicallonghauljoin2", join_body)
    public_body = {
        "schema": PUBLIC_SCHEMA, "profileId": PROFILE_ID, "campaignId": campaign,
        "joinId": join_body["joinId"], "sourceBindingId": source["sourceBindingId"],
        "terminal": terminal, "reasonCodes": reasons,
        "privatePhysicalFlightCompleted": terminal == "PRIVATE_SELF_ATTESTED",
        "selfAttestationOnly": terminal == "PRIVATE_SELF_ATTESTED",
        "publicEvidenceBodies": 0,
        "privateEvidenceBodies": input_value["privateDisposition"]["privateEvidenceBodyCount"] if terminal == "PRIVATE_SELF_ATTESTED" else 0,
        "physicalExecutionStartedByJoin": False,
        "missionVolumeMaterializedByJoin": False,
        "workersLaunched": 0, "listenersCreated": 0,
        "issue37AdvancedByJoin": False,
        "strongerClaims": copy.deepcopy(STRONGER_CLAIMS),
        "authority": "none", "claimBoundary": CLAIM_BOUNDARY,
    }
    public_body["publicStatusId"] = content_id("axmheadphysicallonghaulpublicstatus2", public_body)
    return {
        "source": source, "route": route, "continuity": continuity,
        "twoCell": two_cell, "successor": successor, "disposition": disposition,
        "join": join_body, "public": public_body,
    }



_ACTIVE_PRIVATE_PROOF_ROOT: dict[str, Any] | None = None
_legacy_verify_carrier = verify_carrier

def verify_carrier(root: Path, proof_root: dict[str, Any] | None = None) -> dict[str, Any]:
    global _ACTIVE_PRIVATE_PROOF_ROOT
    previous = _ACTIVE_PRIVATE_PROOF_ROOT
    _ACTIVE_PRIVATE_PROOF_ROOT = proof_root
    try:
        receipt = _legacy_verify_carrier(root)
    finally:
        _ACTIVE_PRIVATE_PROOF_ROOT = previous
    receipt["privateProofAuthenticated"] = receipt["terminal"] == "PRIVATE_SELF_ATTESTED"
    receipt["privateProofRootId"] = proof_root["proofRootId"] if receipt["privateProofAuthenticated"] and proof_root is not None else None
    return receipt

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("carrier", type=Path)
    parser.add_argument("--proof-root", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.out is not None and output_overlaps(args.carrier, args.out):
            fail("VERDICT_OUTPUT_OVERLAP_REFUSED", "verdict output")
        proof_root = load_private_proof_root(args.proof_root) if args.proof_root is not None else None
        receipt = verify_carrier(args.carrier, proof_root)
        emit(receipt, args.out)
        return 0
    except JoinError as exc:
        receipt = {
            "schema": VERIFICATION_SCHEMA,
            "status": "REFUSED",
            "errorCode": exc.code,
            "message": exc.code,
            "bootstrapAuthenticated": False,
            "bootstrapVerifierSha256": None,
            "bootstrapProfileSha256": None,
            "privateProofAuthenticated": False,
            "privateProofRootId": None,
            "physicalExecutionStartedByJoin": False,
            "missionVolumeMaterializedByJoin": False,
            "workersLaunched": 0,
            "listenersCreated": 0,
            "publicEvidenceBodies": 0,
            "strongerClaims": copy.deepcopy(STRONGER_CLAIMS),
            "authority": "none",
        }
        emit(receipt, args.out)
        return 2


if __name__ == "__main__": raise SystemExit(main())
