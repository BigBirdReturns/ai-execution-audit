from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

PROFILE_SCHEMA = "axm-head-browser-distributed-inference-audition-profile/1"
FIXTURE_SCHEMA = "axm-head/browser-distributed-inference-audition-fixtures@1"
CAPTURE_SCHEMA = "axm-head/browser-distributed-inference-capture@1"
RAW_CAPTURE_SCHEMA = "axm-head/browser-probe-private-capture@1"
CONTROL_SCHEMA = "axm-head/browser-distributed-inference-audition-control@1"
MATERIALIZATION_SCHEMA = "axm-head/browser-distributed-inference-audition-materialization@1"
DECISION_SCHEMA = "axm-head/browser-distributed-inference-audition-decision@1"
CAMPAIGN_SCHEMA = "axm-head/browser-distributed-inference-audition-campaign@1"
PUBLIC_SCHEMA = "axm-head/browser-distributed-inference-audition-public@1"
INTERFACE = "axm/distributed-model-inference@1"
PROFILE_ID = "axm-head/browser-distributed-inference-audition/0.1"
SOURCE_FLOOR_COMMIT = "8d18d2c4b6df505751574f219c8c8dd69877a6df"
SOURCE_FLOOR_TREE = "7c8d1786cbae8277c55ca17d115b44c9ec4cae7d"
ISSUE_REF = "BigBirdReturns/ai-execution-audit#92"
PROBE_SHA256_REF = "sha256:b1ded0348ffc0ec4246e9d18a08451216c89f98d6369e483808062430088565e"
CLAIM_BOUNDARY = 'Supplier-neutral source-qualified browser observation and verification membrane for distributed-model-inference routes. Synthetic fixtures qualify only the membrane. They do not qualify any public supplier, supplier actor, physical device, model output, privacy claim, or operational Estate. CI launches no browser, contacts no external endpoint, performs no inference, grants no mission or command authority, and changes no physical-flight state.'
COMMODITY_PRODUCT_MEMBERS = (
    ('.github/workflows/axm-head-distributed-inference-commodity-01.yml', 'd0888369be48a05482c8f51246173ed660353986'),
    ('mating_surface/anchor_node/AXM-HEAD-DISTRIBUTED-INFERENCE-COMMODITY-01.md', '1e3bbbda923b3c279b66cb192826d5f94d85d1a3'),
    ('mating_surface/anchor_node/axm-head-distributed-inference-commodity-profile-01.json', '3ae68329a288b1cbc5fef62d648ea3d301a8f7e9'),
    ('mating_surface/anchor_node/axm_head_distributed_inference_commodity.py', '97231a83c6e41c8da2f65735e940e1a6a5096c4b'),
    ('mating_surface/anchor_node/conformance/test_axm_head_distributed_inference_commodity.py', 'db12b0bb65c4d64e244733881b4e58c75d23244d'),
    ('mating_surface/anchor_node/fixtures/axm-head-distributed-inference-commodity-cases-01.json', 'a03941698d4808f9182fe5f157e5a4392fe479a2'),
    ('mating_surface/anchor_node/fixtures/axm-head-distributed-inference-suppliers-01.json', '79b532aa2e6ee063d62108dcdbc90e1ae7ce4d88'),
)
SOURCE_MEMBERS = (
    '.github/workflows/axm-head-browser-distributed-inference-audition-01.yml',
    'mating_surface/anchor_node/AXM-HEAD-BROWSER-DISTRIBUTED-INFERENCE-AUDITION-01.md',
    'mating_surface/anchor_node/axm-head-browser-distributed-inference-audition-profile-01.json',
    'mating_surface/anchor_node/axm-head-browser-distributed-inference-audition.ps1',
    'mating_surface/anchor_node/axm_head_browser_distributed_inference_audition.py',
    'mating_surface/anchor_node/browser_distributed_inference_probe.js',
    'mating_surface/anchor_node/verify_axm_head_browser_distributed_inference_audition.py',
    'mating_surface/anchor_node/verify_axm_head_browser_distributed_inference_audition_bootstrap.py',
    'mating_surface/anchor_node/conformance/test_axm_head_browser_distributed_inference_audition.py',
    'mating_surface/anchor_node/fixtures/axm-head-browser-distributed-inference-audition-cases-01.json',
)
PUBLIC_PROJECTION_ALLOWED_KEYS = (
    'actualSupplierQualified',
    'bootstrapAuthenticated',
    'captureDigest',
    'commandAuthority',
    'executionOccurred',
    'missionAuthority',
    'observationReceiptDigest',
    'physicalEstateQualified',
    'reasonCodes',
    'receiptKindsPresent',
    'schema',
    'sourceKind',
    'supplierAdmissionReceiptPresent',
    'syntheticConformanceOnly',
    'terminal',
)
TERMINALS = (
    "PREPARED_FOR_PHYSICAL_AUDITION",
    "OBSERVED_ROUTE_CANDIDATE",
    "HOLD",
)
CASE_IDS = (
    "observed-complete-synthetic-route",
    "prepared-public-observation-only",
    "hold-instrumentation-installed-late",
    "hold-ui-only-capacity",
    "hold-duplicate-member",
    "hold-selected-candidate-pair-missing",
    "hold-unreliable-activation-channel",
    "hold-model-identity-mismatch",
    "hold-performance-denominator-incomplete",
    "hold-drop-terminal-missing",
    "hold-public-projection-leak",
    "hold-privacy-overclaim",
    "hold-supplier-pinned-work-unit",
    "hold-capture-ceiling-exceeded",
    "hold-stored-receipt-forgery",
)
EXPECTED_TERMINALS = (
    "OBSERVED_ROUTE_CANDIDATE",
    "PREPARED_FOR_PHYSICAL_AUDITION",
    *("HOLD",) * 13,
)
OBSERVATION_RECEIPT_KINDS = (
    "current-availability-observation",
    "executable-adapter-artifact",
    "formation-capacity-receipt",
    "formation-topology-receipt",
    "member-drop-behavior-receipt",
    "model-output-equivalence-receipt",
    "performance-receipt",
    "network-exposure-observation",
    "privacy-declaration",
)
REASON_ORDER = (
    "INSTRUMENTATION_LATE",
    "PROBE_ARTIFACT_MISMATCH",
    "TASK_INTERFACE_INVALID",
    "TASK_SUPPLIER_PINNED",
    "CAPTURE_EVENT_CEILING_EXCEEDED",
    "CAPTURE_BYTE_CEILING_EXCEEDED",
    "FORMATION_MEMBER_DUPLICATE",
    "FORMATION_MEMBER_UNIQUENESS_UNPROVED",
    "UI_ONLY_CAPACITY",
    "ARTIFACT_BINDING_MISSING",
    "AVAILABILITY_OBSERVATION_MISSING",
    "EXECUTABLE_ADAPTER_ARTIFACT_MISSING",
    "SELECTED_CANDIDATE_PAIR_MISSING",
    "ACTIVATION_CHANNEL_NOT_ORDERED_RELIABLE",
    "MODEL_IDENTITY_MISMATCH",
    "PERFORMANCE_DENOMINATOR_INCOMPLETE",
    "DROP_TERMINAL_MISSING",
    "OUTPUT_EQUIVALENCE_MISSING",
    "RECEIPT_DENOMINATOR_INCOMPLETE",
    "PUBLIC_PROJECTION_LEAK",
    "PRIVACY_CLAIM_EXCEEDS_OBSERVER",
    "SUPPLIER_SELF_ADMISSION_ATTEMPT",
    "STORED_RECEIPT_MISMATCH",
)
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
PRIVATE_ADDRESS_RE = re.compile(
    r"(?:^|[^0-9])(?:10\.(?:\d{1,3}\.){2}\d{1,3}|192\.168\.(?:\d{1,3}\.)\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.(?:\d{1,3}\.)\d{1,3})(?:$|[^0-9])"
)


class AuditionError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def pretty_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_ref(value: Any) -> str:
    return "sha256:" + sha256_bytes(canonical_bytes(value))


def load_object(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AuditionError("JSON_INVALID", f"{path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AuditionError("OBJECT_INVALID", f"{path}: root must be object")
    return value


def exact_keys(value: dict[str, Any], expected: Iterable[str], code: str) -> None:
    expected_set = set(expected)
    actual = set(value)
    if actual != expected_set:
        raise AuditionError(
            code,
            f"missing={sorted(expected_set - actual)} extra={sorted(actual - expected_set)}",
        )


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise AuditionError(code, message)


def is_sha256_ref(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def validate_profile(path: str | Path) -> dict[str, Any]:
    profile = load_object(path)
    exact_keys(
        profile,
        {
            "captureLimits",
            "claimBoundary",
            "commodityBinding",
            "fixtureCaseIds",
            "issueRef",
            "observationReceiptKinds",
            "profileId",
            "publicProjectionAllowedKeys",
            "schema",
            "sourceMembers",
            "status",
            "terminalStates",
        },
        "PROFILE_KEYS_INVALID",
    )
    require(profile["schema"] == PROFILE_SCHEMA, "PROFILE_SCHEMA_INVALID", str(profile["schema"]))
    require(profile["profileId"] == PROFILE_ID, "PROFILE_ID_INVALID", str(profile["profileId"]))
    require(profile["status"] == "candidate_source_only", "PROFILE_STATUS_INVALID", str(profile["status"]))
    require(profile["issueRef"] == ISSUE_REF, "ISSUE_REF_INVALID", str(profile["issueRef"]))
    require(tuple(profile["terminalStates"]) == TERMINALS, "TERMINAL_DENOMINATOR_INVALID", str(profile["terminalStates"]))
    require(tuple(profile["fixtureCaseIds"]) == CASE_IDS, "CASE_DENOMINATOR_INVALID", str(profile["fixtureCaseIds"]))
    require(
        tuple(profile["observationReceiptKinds"]) == OBSERVATION_RECEIPT_KINDS,
        "RECEIPT_DENOMINATOR_INVALID",
        str(profile["observationReceiptKinds"]),
    )
    limits = profile["captureLimits"]
    require(limits == {"events": 4096, "encodedBytes": 1048576}, "CAPTURE_LIMITS_INVALID", str(limits))
    binding = profile["commodityBinding"]
    exact_keys(binding, {"admissionCommit", "admissionTree", "interface", "productMembers"}, "COMMODITY_BINDING_KEYS_INVALID")
    require(
        (binding["admissionCommit"], binding["admissionTree"], binding["interface"])
        == (SOURCE_FLOOR_COMMIT, SOURCE_FLOOR_TREE, INTERFACE),
        "COMMODITY_BINDING_INVALID",
        "admitted commodity coordinates or interface drifted",
    )
    members = binding["productMembers"]
    require(isinstance(members, list), "COMMODITY_MEMBER_DENOMINATOR_INVALID", str(type(members)))
    observed_members = tuple((row.get("path"), row.get("sha")) for row in members if isinstance(row, dict))
    require(observed_members == COMMODITY_PRODUCT_MEMBERS, "COMMODITY_MEMBER_DENOMINATOR_INVALID", str(observed_members))
    for member in members:
        exact_keys(member, {"path", "sha"}, "COMMODITY_MEMBER_KEYS_INVALID")
        require(isinstance(member["path"], str) and re.fullmatch(r"[0-9a-f]{40}", member["sha"]), "COMMODITY_MEMBER_IDENTITY_INVALID", str(member))
    source_members = profile["sourceMembers"]
    require(tuple(source_members) == SOURCE_MEMBERS, "SOURCE_MEMBER_DENOMINATOR_INVALID", str(source_members))
    allowed = profile["publicProjectionAllowedKeys"]
    require(tuple(allowed) == PUBLIC_PROJECTION_ALLOWED_KEYS, "PUBLIC_KEY_DENOMINATOR_INVALID", str(allowed))
    require(profile["claimBoundary"] == CLAIM_BOUNDARY, "CLAIM_BOUNDARY_INVALID", profile["claimBoundary"])
    return profile


CAPTURE_KEYS = {
    "adapter",
    "controlEvidenceRef",
    "availability",
    "drop",
    "equivalence",
    "formation",
    "instrumentation",
    "limits",
    "model",
    "performance",
    "privacy",
    "proposedPublicProjection",
    "rawEvidenceRef",
    "receiptRefs",
    "schema",
    "sourceKind",
    "storedReceiptDigest",
    "supplierAdmissionReceipt",
    "supplierObservationRef",
    "syntheticConformanceOnly",
    "transport",
    "workUnit",
}


def validate_capture_shape(capture: dict[str, Any], profile: dict[str, Any]) -> None:
    exact_keys(capture, CAPTURE_KEYS, "CAPTURE_KEYS_INVALID")
    require(capture["schema"] == CAPTURE_SCHEMA, "CAPTURE_SCHEMA_INVALID", str(capture["schema"]))
    require(capture["sourceKind"] in {"synthetic-live-capture", "public-observation-only", "physical-private-local"}, "SOURCE_KIND_INVALID", str(capture["sourceKind"]))
    require(isinstance(capture["syntheticConformanceOnly"], bool), "SYNTHETIC_FLAG_INVALID", str(capture["syntheticConformanceOnly"]))
    require(capture["supplierObservationRef"] is None or isinstance(capture["supplierObservationRef"], str), "SUPPLIER_OBSERVATION_REF_INVALID", str(capture["supplierObservationRef"]))
    if capture["sourceKind"] in {"synthetic-live-capture", "physical-private-local"}:
        require(is_sha256_ref(capture["rawEvidenceRef"]), "RAW_EVIDENCE_REF_INVALID", str(capture["rawEvidenceRef"]))
        require(is_sha256_ref(capture["controlEvidenceRef"]), "CONTROL_EVIDENCE_REF_INVALID", str(capture["controlEvidenceRef"]))
    else:
        require(capture["rawEvidenceRef"] is None, "RAW_EVIDENCE_REF_INVALID", str(capture["rawEvidenceRef"]))
        require(capture["controlEvidenceRef"] is None, "CONTROL_EVIDENCE_REF_INVALID", str(capture["controlEvidenceRef"]))

    if capture["sourceKind"] == "synthetic-live-capture":
        require(capture["syntheticConformanceOnly"] is True, "SYNTHETIC_FLAG_INVALID", "synthetic live capture must be conformance-only")
    else:
        require(capture["syntheticConformanceOnly"] is False, "SYNTHETIC_FLAG_INVALID", "non-synthetic capture cannot be marked conformance-only")

    exact_keys(capture["instrumentation"], {"applicationStartMonotonicMs", "installedAtMonotonicMs", "installedBeforeApplication", "probeSha256"}, "INSTRUMENTATION_KEYS_INVALID")
    exact_keys(capture["limits"], {"encodedBytes", "events"}, "LIMIT_KEYS_INVALID")
    exact_keys(capture["workUnit"], {"authorityClass", "requiredCapabilities", "requiredInterface", "requiredValidatorRefs", "supplierRef"}, "WORK_UNIT_KEYS_INVALID")
    exact_keys(capture["availability"], {"evidenceRef", "observed", "observedAtUnixMs"}, "AVAILABILITY_KEYS_INVALID")
    exact_keys(capture["adapter"], {"artifactBytes", "artifactDigest", "evidenceRef", "executableObserved"}, "ADAPTER_KEYS_INVALID")
    exact_keys(capture["formation"], {"artifactBound", "capacityBasis", "capacityReceiptRef", "members", "modelCapacityBytes", "partitionMode", "topologyReceiptRef"}, "FORMATION_KEYS_INVALID")
    exact_keys(capture["model"], {"artifactTotalBytes", "boundModelId", "claimedId", "layers", "observedManifestDigest"}, "MODEL_KEYS_INVALID")
    exact_keys(capture["transport"], {"activationChannels", "peerConnectionCount", "selectedCandidatePairClass", "selectedCandidatePairObserved", "signalingEndpointHashes"}, "TRANSPORT_KEYS_INVALID")
    exact_keys(capture["performance"], {"firstTokenMonotonicMs", "lastTokenMonotonicMs", "outputTokenCount", "promptTokenCount", "startMonotonicMs", "tokenMarks"}, "PERFORMANCE_KEYS_INVALID")
    exact_keys(capture["drop"], {"controlled", "evidenceRef", "memberIdHash", "observedTerminal", "recovered"}, "DROP_KEYS_INVALID")
    exact_keys(capture["equivalence"], {"candidateDigest", "evidenceRef", "match", "outputTokenCount", "promptTokenCount", "referenceDigest"}, "EQUIVALENCE_KEYS_INVALID")
    exact_keys(capture["privacy"], {"claimsEndToEndConfidentiality", "declarationPresent", "evidenceRef", "scope"}, "PRIVACY_KEYS_INVALID")

    require(isinstance(capture["formation"]["members"], list), "FORMATION_MEMBERS_INVALID", "members must be list")
    for row in capture["formation"]["members"]:
        exact_keys(row, {"memberIdHash", "physicallyUnique", "pledgedBytes", "role"}, "FORMATION_MEMBER_KEYS_INVALID")
    require(isinstance(capture["model"]["layers"], list), "MODEL_LAYERS_INVALID", "layers must be list")
    for row in capture["model"]["layers"]:
        exact_keys(row, {"artifactBytes", "artifactDigest", "layerEnd", "layerStart", "memberIdHash"}, "MODEL_LAYER_KEYS_INVALID")
    require(isinstance(capture["transport"]["activationChannels"], list), "ACTIVATION_CHANNELS_INVALID", "channels must be list")
    for row in capture["transport"]["activationChannels"]:
        exact_keys(row, {"bytesReceived", "bytesSent", "channelIdHash", "maxPacketLifeTime", "maxRetransmits", "ordered"}, "ACTIVATION_CHANNEL_KEYS_INVALID")
    require(isinstance(capture["performance"]["tokenMarks"], list), "TOKEN_MARKS_INVALID", "token marks must be list")
    for row in capture["performance"]["tokenMarks"]:
        exact_keys(row, {"index", "monotonicMs"}, "TOKEN_MARK_KEYS_INVALID")
    require(isinstance(capture["receiptRefs"], dict), "RECEIPT_REFS_INVALID", "receiptRefs must be object")
    require(isinstance(capture["proposedPublicProjection"], dict), "PUBLIC_PROJECTION_INVALID", "projection must be object")
    require(capture["storedReceiptDigest"] is None or is_sha256_ref(capture["storedReceiptDigest"]), "STORED_RECEIPT_DIGEST_INVALID", str(capture["storedReceiptDigest"]))
    if capture["supplierAdmissionReceipt"] is not None:
        require(isinstance(capture["supplierAdmissionReceipt"], dict), "SUPPLIER_ADMISSION_RECEIPT_INVALID", "admission receipt must be object or null")

    instrumentation = capture["instrumentation"]
    require(is_sha256_ref(instrumentation["probeSha256"]), "PROBE_ARTIFACT_DIGEST_INVALID", str(instrumentation["probeSha256"]))
    for key in ("applicationStartMonotonicMs", "installedAtMonotonicMs"):
        require(isinstance(instrumentation[key], (int, float)) and not isinstance(instrumentation[key], bool), "INSTRUMENTATION_TIME_INVALID", key)
    require(isinstance(instrumentation["installedBeforeApplication"], bool), "INSTRUMENTATION_FLAG_INVALID", str(instrumentation["installedBeforeApplication"]))
    for key in ("events", "encodedBytes"):
        require(isinstance(capture["limits"][key], int) and not isinstance(capture["limits"][key], bool) and capture["limits"][key] >= 0, "CAPTURE_LIMIT_INVALID", key)
    for row in capture["formation"]["members"]:
        require(is_sha256_ref(row["memberIdHash"]), "FORMATION_MEMBER_ID_INVALID", str(row["memberIdHash"]))
        require(isinstance(row["physicallyUnique"], bool), "FORMATION_MEMBER_UNIQUENESS_INVALID", str(row["physicallyUnique"]))
        require(isinstance(row["pledgedBytes"], int) and row["pledgedBytes"] > 0, "FORMATION_PLEDGE_INVALID", str(row["pledgedBytes"]))
        require(isinstance(row["role"], str) and row["role"], "FORMATION_ROLE_INVALID", str(row["role"]))
    for row in capture["transport"]["activationChannels"]:
        require(is_sha256_ref(row["channelIdHash"]), "ACTIVATION_CHANNEL_ID_INVALID", str(row["channelIdHash"]))
    require(all(is_sha256_ref(row) for row in capture["transport"]["signalingEndpointHashes"]), "SIGNALING_ENDPOINT_HASH_INVALID", str(capture["transport"]["signalingEndpointHashes"]))


RAW_CAPTURE_KEYS = {
    "schema",
    "installedAtMonotonicMs",
    "installedBeforeApplication",
    "limits",
    "observed",
    "refused",
    "events",
    "summaries",
}
RAW_EVENT_TYPES = {
    "adapter-artifact",
    "availability-observation",
    "cache-add",
    "cache-add-all",
    "cache-match",
    "cache-put",
    "eventsource-create",
    "eventsource-receive",
    "eventsource-state",
    "fetch-complete",
    "fetch-failed",
    "fetch-start",
    "formation-declaration",
    "formation-member",
    "indexeddb-open",
    "indexeddb-state",
    "indexeddb-transaction",
    "member-drop",
    "model-artifact",
    "model-manifest",
    "observation-receipt-ref",
    "output-equivalence",
    "performance-start",
    "privacy-declaration",
    "probe-installed",
    "rtc-data-channel",
    "rtc-data-channel-receive",
    "rtc-data-channel-send",
    "rtc-data-channel-state",
    "rtc-peer-create",
    "rtc-peer-state",
    "rtc-stats",
    "token-mark",
    "webgpu-adapter",
    "webgpu-device",
    "webgpu-device-lost",
    "webgpu-unavailable",
    "websocket-create",
    "websocket-receive",
    "websocket-send",
    "websocket-state",
}

CONTROL_KEYS = {
    "schema",
    "probeSha256",
    "sourceKind",
    "supplierObservationRef",
    "syntheticConformanceOnly",
    "applicationStartMonotonicMs",
    "workUnit",
    "memberUniquenessAssertions",
    "proposedPublicProjection",
    "supplierAdmissionReceipt",
}


def raw_identity_ref(value: Any) -> str:
    require(isinstance(value, str) and value.startswith("opaque:") and len(value) > 15, "RAW_OPAQUE_ID_INVALID", str(value))
    return sha256_ref({"probeOpaqueId": value})


def raw_capture_leaks(value: Any) -> bool:
    forbidden_keys = {
        "prompttext",
        "completiontext",
        "tokentext",
        "iceaddress",
        "candidateaddress",
        "devicelabel",
        "rawurl",
        "modelurl",
        "authorization",
        "password",
        "sdp",
    }
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).replace("_", "").replace("-", "").lower()
            if normalized in forbidden_keys or raw_capture_leaks(child):
                return True
        return False
    if isinstance(value, list):
        return any(raw_capture_leaks(child) for child in value)
    if isinstance(value, str):
        lowered = value.lower()
        return (
            "://" in value
            or "bearer " in lowered
            or "begin private key" in lowered
            or PRIVATE_ADDRESS_RE.search(value) is not None
        )
    return False


def event_rows(raw: dict[str, Any], event_type: str) -> list[dict[str, Any]]:
    return [row for row in raw["events"] if row.get("type") == event_type]


def one_event(raw: dict[str, Any], event_type: str, code: str) -> dict[str, Any]:
    rows = event_rows(raw, event_type)
    require(len(rows) == 1, code, f"{event_type}: count={len(rows)}")
    return rows[0]


def validate_raw_probe_capture(raw: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    exact_keys(raw, RAW_CAPTURE_KEYS, "RAW_CAPTURE_KEYS_INVALID")
    require(raw["schema"] == RAW_CAPTURE_SCHEMA, "RAW_CAPTURE_SCHEMA_INVALID", str(raw["schema"]))
    require(isinstance(raw["installedAtMonotonicMs"], (int, float)) and not isinstance(raw["installedAtMonotonicMs"], bool), "RAW_INSTALL_TIME_INVALID", str(raw["installedAtMonotonicMs"]))
    require(isinstance(raw["installedBeforeApplication"], bool), "RAW_INSTALL_FLAG_INVALID", str(raw["installedBeforeApplication"]))
    exact_keys(raw["limits"], {"events", "encodedBytes"}, "RAW_LIMIT_KEYS_INVALID")
    exact_keys(raw["observed"], {"eventCount", "encodedBytes"}, "RAW_OBSERVED_KEYS_INVALID")
    for key in ("events", "encodedBytes"):
        configured = raw["limits"][key]
        observed = raw["observed"]["eventCount" if key == "events" else key]
        require(isinstance(configured, int) and not isinstance(configured, bool) and 0 < configured <= profile["captureLimits"][key], "RAW_LIMIT_INVALID", key)
        require(isinstance(observed, int) and not isinstance(observed, bool) and 0 <= observed <= configured, "RAW_OBSERVED_LIMIT_INVALID", key)
    require(raw["refused"] in {None, "CAPTURE_EVENT_CEILING_EXCEEDED", "CAPTURE_BYTE_CEILING_EXCEEDED"}, "RAW_REFUSAL_INVALID", str(raw["refused"]))
    require(isinstance(raw["events"], list), "RAW_EVENTS_INVALID", "events must be list")
    require(raw["observed"]["eventCount"] == len(raw["events"]), "RAW_EVENT_COUNT_MISMATCH", str(raw["observed"]))
    previous = float(raw["installedAtMonotonicMs"])
    for index, row in enumerate(raw["events"]):
        require(isinstance(row, dict), "RAW_EVENT_INVALID", f"index={index}")
        require("type" in row and "monotonicMs" in row, "RAW_EVENT_KEYS_INVALID", f"index={index}")
        require(isinstance(row["type"], str) and row["type"], "RAW_EVENT_TYPE_INVALID", f"index={index}")
        require(row["type"] in RAW_EVENT_TYPES, "RAW_EVENT_TYPE_UNKNOWN", f"index={index} type={row['type']}")
        require(isinstance(row["monotonicMs"], (int, float)) and not isinstance(row["monotonicMs"], bool), "RAW_EVENT_TIME_INVALID", f"index={index}")
        require(float(row["monotonicMs"]) >= previous, "RAW_EVENT_ORDER_INVALID", f"index={index}")
        previous = float(row["monotonicMs"])
    require(not raw_capture_leaks(raw), "RAW_CAPTURE_BODY_OR_NETWORK_IDENTITY_LEAK", "raw probe capture contains forbidden body or network identity")
    reconstructed_encoded_bytes = sum(
        len(json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        for row in raw["events"]
    )
    require(
        raw["observed"]["encodedBytes"] == reconstructed_encoded_bytes,
        "RAW_ENCODED_BYTES_MISMATCH",
        f"stored={raw['observed']['encodedBytes']} rebuilt={reconstructed_encoded_bytes}",
    )

    summaries = raw["summaries"]
    exact_keys(
        summaries,
        {
            "memberCount",
            "members",
            "artifactCount",
            "artifacts",
            "tokenMarks",
            "drops",
            "equivalenceMarks",
            "privacyDeclarations",
            "peerConnectionCount",
            "dataChannelCount",
        },
        "RAW_SUMMARY_KEYS_INVALID",
    )
    summary_sources = (
        ("members", "memberCount", "formation-member"),
        ("artifacts", "artifactCount", "model-artifact"),
        ("tokenMarks", None, "token-mark"),
        ("drops", None, "member-drop"),
        ("equivalenceMarks", None, "output-equivalence"),
        ("privacyDeclarations", None, "privacy-declaration"),
    )
    for summary_key, count_key, event_type in summary_sources:
        observed_rows = [{key: value for key, value in row.items() if key not in {"type", "monotonicMs"}} for row in event_rows(raw, event_type)]
        require(summaries[summary_key] == observed_rows, "RAW_SUMMARY_MISMATCH", summary_key)
        if count_key is not None:
            require(summaries[count_key] == len(observed_rows), "RAW_SUMMARY_COUNT_MISMATCH", count_key)
    require(summaries["peerConnectionCount"] == len(event_rows(raw, "rtc-peer-create")), "RAW_SUMMARY_COUNT_MISMATCH", "peerConnectionCount")
    require(summaries["dataChannelCount"] == len(event_rows(raw, "rtc-data-channel")), "RAW_SUMMARY_COUNT_MISMATCH", "dataChannelCount")
    return raw


def validate_materialization_control(control: dict[str, Any]) -> dict[str, Any]:
    exact_keys(control, CONTROL_KEYS, "CONTROL_KEYS_INVALID")
    require(control["schema"] == CONTROL_SCHEMA, "CONTROL_SCHEMA_INVALID", str(control["schema"]))
    require(control["probeSha256"] == PROBE_SHA256_REF, "PROBE_ARTIFACT_MISMATCH", str(control["probeSha256"]))
    require(control["sourceKind"] in {"synthetic-live-capture", "physical-private-local"}, "CONTROL_SOURCE_KIND_INVALID", str(control["sourceKind"]))
    require(isinstance(control["syntheticConformanceOnly"], bool), "CONTROL_SYNTHETIC_FLAG_INVALID", str(control["syntheticConformanceOnly"]))
    require(control["syntheticConformanceOnly"] is (control["sourceKind"] == "synthetic-live-capture"), "CONTROL_SYNTHETIC_FLAG_INVALID", str(control["syntheticConformanceOnly"]))
    require(control["supplierObservationRef"] is None or isinstance(control["supplierObservationRef"], str), "CONTROL_SUPPLIER_REF_INVALID", str(control["supplierObservationRef"]))
    require(isinstance(control["applicationStartMonotonicMs"], (int, float)) and not isinstance(control["applicationStartMonotonicMs"], bool), "CONTROL_APPLICATION_START_INVALID", str(control["applicationStartMonotonicMs"]))
    require(isinstance(control["workUnit"], dict), "CONTROL_WORK_UNIT_INVALID", "workUnit must be object")
    exact_keys(control["workUnit"], {"authorityClass", "requiredCapabilities", "requiredInterface", "requiredValidatorRefs", "supplierRef"}, "WORK_UNIT_KEYS_INVALID")
    require(isinstance(control["memberUniquenessAssertions"], list), "CONTROL_MEMBER_ASSERTIONS_INVALID", "member assertions must be list")
    seen: set[str] = set()
    for row in control["memberUniquenessAssertions"]:
        exact_keys(row, {"probeMemberId", "physicallyUnique", "evidenceRef"}, "CONTROL_MEMBER_ASSERTION_KEYS_INVALID")
        raw_identity_ref(row["probeMemberId"])
        require(row["probeMemberId"] not in seen, "CONTROL_MEMBER_ASSERTION_DUPLICATE", row["probeMemberId"])
        seen.add(row["probeMemberId"])
        require(isinstance(row["physicallyUnique"], bool), "CONTROL_MEMBER_UNIQUENESS_INVALID", str(row["physicallyUnique"]))
        require(is_sha256_ref(row["evidenceRef"]), "CONTROL_MEMBER_EVIDENCE_INVALID", str(row["evidenceRef"]))
    require(isinstance(control["proposedPublicProjection"], dict), "CONTROL_PUBLIC_PROJECTION_INVALID", "projection must be object")
    require(control["supplierAdmissionReceipt"] is None or isinstance(control["supplierAdmissionReceipt"], dict), "CONTROL_SUPPLIER_ADMISSION_INVALID", "supplier admission must be object or null")
    return control


def _event_body(row: dict[str, Any]) -> dict[str, Any]:
    return {key: copy.deepcopy(value) for key, value in row.items() if key not in {"type", "monotonicMs"}}


def _required_event_body(raw: dict[str, Any], event_type: str, expected: set[str], code: str) -> dict[str, Any]:
    row = one_event(raw, event_type, code)
    exact_keys(row, {"type", "monotonicMs", *expected}, f"{code}_KEYS_INVALID")
    return _event_body(row)


def materialize_probe_capture(raw: dict[str, Any], control: dict[str, Any], profile: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    validate_raw_probe_capture(raw, profile)
    validate_materialization_control(control)
    require(event_rows(raw, "probe-installed"), "PROBE_INSTALL_EVENT_MISSING", "probe-installed event absent")
    require(event_rows(raw, "webgpu-adapter") and event_rows(raw, "webgpu-device"), "WEBGPU_OBSERVATION_MISSING", "WebGPU adapter/device not observed")

    availability = _required_event_body(raw, "availability-observation", {"observed", "observedAtUnixMs", "evidenceRef"}, "AVAILABILITY_EVENT_INVALID")
    adapter = _required_event_body(raw, "adapter-artifact", {"artifactBytes", "artifactDigest", "evidenceRef", "executableObserved"}, "ADAPTER_EVENT_INVALID")
    formation_decl = _required_event_body(raw, "formation-declaration", {"artifactBound", "capacityBasis", "capacityReceiptRef", "modelCapacityBytes", "partitionMode", "topologyReceiptRef"}, "FORMATION_EVENT_INVALID")
    model_manifest = _required_event_body(raw, "model-manifest", {"boundModelId", "claimedId", "observedManifestDigest"}, "MODEL_MANIFEST_EVENT_INVALID")
    performance_start = _required_event_body(raw, "performance-start", {"promptTokenCount", "startMonotonicMs"}, "PERFORMANCE_START_EVENT_INVALID")

    assertions = {row["probeMemberId"]: row for row in control["memberUniquenessAssertions"]}
    member_events = event_rows(raw, "formation-member")
    require(member_events, "FORMATION_MEMBER_EVENTS_MISSING", "formation-member events absent")
    members: list[dict[str, Any]] = []
    raw_member_ids: set[str] = set()
    for row in member_events:
        exact_keys(row, {"type", "monotonicMs", "memberIdHash", "role", "pledgedBytes"}, "RAW_MEMBER_EVENT_KEYS_INVALID")
        raw_id = row["memberIdHash"]
        raw_identity_ref(raw_id)
        require(raw_id not in raw_member_ids, "FORMATION_MEMBER_DUPLICATE", raw_id)
        raw_member_ids.add(raw_id)
        require(raw_id in assertions, "CONTROL_MEMBER_ASSERTION_MISSING", raw_id)
        members.append(
            {
                "memberIdHash": raw_identity_ref(raw_id),
                "physicallyUnique": assertions[raw_id]["physicallyUnique"],
                "pledgedBytes": row["pledgedBytes"],
                "role": row["role"],
            }
        )
    require(set(assertions) == raw_member_ids, "CONTROL_MEMBER_ASSERTION_DENOMINATOR_INVALID", str(sorted(set(assertions) ^ raw_member_ids)))

    layers: list[dict[str, Any]] = []
    for row in event_rows(raw, "model-artifact"):
        exact_keys(row, {"type", "monotonicMs", "artifactIdHash", "artifactBytes", "artifactDigest", "layerStart", "layerEnd", "memberIdHash"}, "RAW_MODEL_ARTIFACT_KEYS_INVALID")
        require(row["memberIdHash"] in raw_member_ids, "RAW_MODEL_ARTIFACT_MEMBER_INVALID", str(row["memberIdHash"]))
        layers.append(
            {
                "artifactBytes": row["artifactBytes"],
                "artifactDigest": row["artifactDigest"],
                "layerStart": row["layerStart"],
                "layerEnd": row["layerEnd"],
                "memberIdHash": raw_identity_ref(row["memberIdHash"]),
            }
        )
    require(layers, "RAW_MODEL_ARTIFACTS_MISSING", "model-artifact events absent")
    artifact_total = sum(row["artifactBytes"] for row in layers if isinstance(row["artifactBytes"], int))

    channel_configs: dict[str, dict[str, Any]] = {}
    for row in event_rows(raw, "rtc-data-channel"):
        exact_keys(row, {"type", "monotonicMs", "channelIdHash", "origin", "ordered", "maxRetransmits", "maxPacketLifeTime", "protocolHash"}, "RAW_CHANNEL_EVENT_KEYS_INVALID")
        raw_id = row["channelIdHash"]
        raw_identity_ref(raw_id)
        require(raw_id not in channel_configs, "RAW_CHANNEL_DUPLICATE", raw_id)
        channel_configs[raw_id] = row
    sent: dict[str, int] = {key: 0 for key in channel_configs}
    received: dict[str, int] = {key: 0 for key in channel_configs}
    for direction, event_type, target in (("send", "rtc-data-channel-send", sent), ("receive", "rtc-data-channel-receive", received)):
        for row in event_rows(raw, event_type):
            exact_keys(row, {"type", "monotonicMs", "channelIdHash", "bytes"}, "RAW_CHANNEL_TRAFFIC_KEYS_INVALID")
            require(row["channelIdHash"] in channel_configs, "RAW_CHANNEL_TRAFFIC_ORPHAN", f"{direction}:{row['channelIdHash']}")
            require(isinstance(row["bytes"], int) and row["bytes"] >= 0, "RAW_CHANNEL_TRAFFIC_INVALID", str(row["bytes"]))
            target[row["channelIdHash"]] += row["bytes"]
    channels = [
        {
            "channelIdHash": raw_identity_ref(raw_id),
            "ordered": row["ordered"],
            "maxRetransmits": row["maxRetransmits"],
            "maxPacketLifeTime": row["maxPacketLifeTime"],
            "bytesSent": sent[raw_id],
            "bytesReceived": received[raw_id],
        }
        for raw_id, row in channel_configs.items()
    ]

    selected_classes: list[str] = []
    for row in event_rows(raw, "rtc-stats"):
        exact_keys(row, {"type", "monotonicMs", "peerIdHash", "selectedPair"}, "RAW_RTC_STATS_KEYS_INVALID")
        pair = row["selectedPair"]
        if isinstance(pair, dict):
            candidate_class = pair.get("remoteCandidateType") or pair.get("localCandidateType")
            if candidate_class in {"host", "srflx", "relay", "prflx"}:
                selected_classes.append(candidate_class)
    exposure_rank = {"host": 0, "prflx": 1, "srflx": 2, "relay": 3}
    selected_class = max(selected_classes, key=lambda value: exposure_rank[value]) if selected_classes else None

    endpoint_raw_ids: set[str] = set()
    for event_type in ("fetch-start", "websocket-create", "eventsource-create"):
        for row in event_rows(raw, event_type):
            endpoint = row.get("endpointHash")
            if endpoint is not None:
                raw_identity_ref(endpoint)
                endpoint_raw_ids.add(endpoint)

    token_rows = event_rows(raw, "token-mark")
    token_marks: list[dict[str, Any]] = []
    for row in token_rows:
        exact_keys(row, {"type", "monotonicMs", "index"}, "RAW_TOKEN_MARK_KEYS_INVALID")
        token_marks.append({"index": row["index"], "monotonicMs": row["monotonicMs"]})
    require(token_marks, "RAW_TOKEN_MARKS_MISSING", "token-mark events absent")

    drop_raw = _required_event_body(raw, "member-drop", {"memberIdHash", "observedTerminal", "recovered", "controlled", "evidenceRef"}, "DROP_EVENT_INVALID")
    require(drop_raw["memberIdHash"] in raw_member_ids, "RAW_DROP_MEMBER_INVALID", str(drop_raw["memberIdHash"]))
    equivalence = _required_event_body(raw, "output-equivalence", {"referenceDigest", "candidateDigest", "promptTokenCount", "outputTokenCount", "match", "evidenceRef"}, "EQUIVALENCE_EVENT_INVALID")
    privacy = _required_event_body(raw, "privacy-declaration", {"scope", "evidenceRef", "claimsEndToEndConfidentiality"}, "PRIVACY_EVENT_INVALID")

    receipt_refs: dict[str, Any] = {}
    for row in event_rows(raw, "observation-receipt-ref"):
        exact_keys(row, {"type", "monotonicMs", "kind", "evidenceRef"}, "RAW_RECEIPT_REF_KEYS_INVALID")
        require(row["kind"] not in receipt_refs, "RAW_RECEIPT_REF_DUPLICATE", str(row["kind"]))
        receipt_refs[row["kind"]] = row["evidenceRef"]

    observed_limits = {
        "events": raw["observed"]["eventCount"],
        "encodedBytes": raw["observed"]["encodedBytes"],
    }
    if raw["refused"] == "CAPTURE_EVENT_CEILING_EXCEEDED":
        observed_limits["events"] = profile["captureLimits"]["events"] + 1
    if raw["refused"] == "CAPTURE_BYTE_CEILING_EXCEEDED":
        observed_limits["encodedBytes"] = profile["captureLimits"]["encodedBytes"] + 1

    capture: dict[str, Any] = {
        "schema": CAPTURE_SCHEMA,
        "sourceKind": control["sourceKind"],
        "syntheticConformanceOnly": control["syntheticConformanceOnly"],
        "supplierObservationRef": control["supplierObservationRef"],
        "rawEvidenceRef": sha256_ref(raw),
        "controlEvidenceRef": sha256_ref(control),
        "instrumentation": {
            "applicationStartMonotonicMs": control["applicationStartMonotonicMs"],
            "installedAtMonotonicMs": raw["installedAtMonotonicMs"],
            "installedBeforeApplication": raw["installedBeforeApplication"],
            "probeSha256": control["probeSha256"],
        },
        "limits": observed_limits,
        "workUnit": copy.deepcopy(control["workUnit"]),
        "availability": availability,
        "adapter": adapter,
        "formation": {
            **formation_decl,
            "members": members,
        },
        "model": {
            **model_manifest,
            "artifactTotalBytes": artifact_total,
            "layers": layers,
        },
        "transport": {
            "peerConnectionCount": len(event_rows(raw, "rtc-peer-create")),
            "selectedCandidatePairObserved": bool(selected_classes),
            "selectedCandidatePairClass": selected_class,
            "activationChannels": channels,
            "signalingEndpointHashes": sorted(raw_identity_ref(value) for value in endpoint_raw_ids),
        },
        "performance": {
            "promptTokenCount": performance_start["promptTokenCount"],
            "outputTokenCount": len(token_marks),
            "startMonotonicMs": performance_start["startMonotonicMs"],
            "firstTokenMonotonicMs": token_marks[0]["monotonicMs"],
            "lastTokenMonotonicMs": token_marks[-1]["monotonicMs"],
            "tokenMarks": token_marks,
        },
        "drop": {
            **drop_raw,
            "memberIdHash": raw_identity_ref(drop_raw["memberIdHash"]),
        },
        "equivalence": equivalence,
        "privacy": {
            "declarationPresent": True,
            **privacy,
        },
        "receiptRefs": receipt_refs,
        "proposedPublicProjection": copy.deepcopy(control["proposedPublicProjection"]),
        "supplierAdmissionReceipt": copy.deepcopy(control["supplierAdmissionReceipt"]),
        "storedReceiptDigest": None,
    }
    validate_capture_shape(capture, profile)
    capture["storedReceiptDigest"] = observation_receipt_digest(capture)
    validate_capture_shape(capture, profile)
    materialization = {
        "schema": MATERIALIZATION_SCHEMA,
        "status": "PASS",
        "rawCaptureDigest": capture["rawEvidenceRef"],
        "controlDigest": capture["controlEvidenceRef"],
        "normalizedCaptureDigest": capture_digest(capture),
        "probeSha256": control["probeSha256"],
        "rawEventCount": raw["observed"]["eventCount"],
        "rawEventsReconstructed": True,
        "actualSupplierQualified": False,
        "executionOccurred": False,
        "physicalEstateQualified": False,
        "missionAuthority": "none",
        "commandAuthority": "none",
    }
    return capture, materialization


def capture_digest(capture: dict[str, Any]) -> str:
    normalized = copy.deepcopy(capture)
    normalized["storedReceiptDigest"] = None
    return sha256_ref(normalized)


def observation_receipt(capture: dict[str, Any]) -> dict[str, Any]:
    members = sorted(
        (
            {
                "memberIdHash": row["memberIdHash"],
                "role": row["role"],
                "pledgedBytes": row["pledgedBytes"],
            }
            for row in capture["formation"]["members"]
        ),
        key=lambda row: (row["memberIdHash"], row["role"]),
    )
    channels = sorted(
        (
            {
                "channelIdHash": row["channelIdHash"],
                "ordered": row["ordered"],
                "maxRetransmits": row["maxRetransmits"],
                "maxPacketLifeTime": row["maxPacketLifeTime"],
                "bytesSent": row["bytesSent"],
                "bytesReceived": row["bytesReceived"],
            }
            for row in capture["transport"]["activationChannels"]
        ),
        key=lambda row: row["channelIdHash"],
    )
    return {
        "schema": "axm-head/browser-distributed-inference-observation-receipt@1",
        "captureDigest": capture_digest(capture),
        "sourceKind": capture["sourceKind"],
        "rawEvidenceRef": capture["rawEvidenceRef"],
        "controlEvidenceRef": capture["controlEvidenceRef"],
        "instrumentationBeforeApplication": capture["instrumentation"]["installedBeforeApplication"],
        "probeSha256": capture["instrumentation"]["probeSha256"],
        "availabilityObserved": capture["availability"]["observed"],
        "adapterArtifactDigest": capture["adapter"]["artifactDigest"],
        "partitionMode": capture["formation"]["partitionMode"],
        "modelCapacityBytes": capture["formation"]["modelCapacityBytes"],
        "members": members,
        "boundModelId": capture["model"]["boundModelId"],
        "observedManifestDigest": capture["model"]["observedManifestDigest"],
        "selectedCandidatePairClass": capture["transport"]["selectedCandidatePairClass"],
        "channels": channels,
        "performance": {
            "promptTokenCount": capture["performance"]["promptTokenCount"],
            "outputTokenCount": capture["performance"]["outputTokenCount"],
            "firstTokenMonotonicMs": capture["performance"]["firstTokenMonotonicMs"],
            "lastTokenMonotonicMs": capture["performance"]["lastTokenMonotonicMs"],
        },
        "dropTerminal": capture["drop"]["observedTerminal"],
        "outputEquivalent": capture["equivalence"]["match"],
        "privacyScope": capture["privacy"]["scope"],
        "receiptRefs": {key: capture["receiptRefs"].get(key) for key in OBSERVATION_RECEIPT_KINDS},
    }


def observation_receipt_digest(capture: dict[str, Any]) -> str:
    return sha256_ref(observation_receipt(capture))


def public_leak(value: Any) -> bool:
    forbidden_fragments = (
        "prompt",
        "completion",
        "tokentext",
        "iceaddress",
        "candidateaddress",
        "devicelabel",
        "rawurl",
        "modelurl",
        "credential",
        "authorization",
        "password",
        "sdp",
    )
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).replace("_", "").replace("-", "").lower()
            if any(fragment in lowered for fragment in forbidden_fragments):
                return True
            if public_leak(child):
                return True
        return False
    if isinstance(value, list):
        return any(public_leak(child) for child in value)
    if isinstance(value, str):
        lowered = value.lower()
        return (
            "://" in value
            or "bearer " in lowered
            or "begin private key" in lowered
            or PRIVATE_ADDRESS_RE.search(value) is not None
        )
    return False


def performance_complete(capture: dict[str, Any]) -> bool:
    perf = capture["performance"]
    try:
        prompt_count = int(perf["promptTokenCount"])
        output_count = int(perf["outputTokenCount"])
        start = float(perf["startMonotonicMs"])
        first = float(perf["firstTokenMonotonicMs"])
        last = float(perf["lastTokenMonotonicMs"])
    except (TypeError, ValueError):
        return False
    if prompt_count <= 0 or output_count <= 0 or not (start <= first <= last):
        return False
    marks = perf["tokenMarks"]
    if len(marks) != output_count:
        return False
    expected = list(range(output_count))
    observed = [row["index"] for row in marks]
    if observed != expected:
        return False
    times = [row["monotonicMs"] for row in marks]
    return times == sorted(times) and times[0] == first and times[-1] == last


def model_identity_complete(capture: dict[str, Any]) -> bool:
    model = capture["model"]
    if not (
        isinstance(model["claimedId"], str)
        and model["claimedId"]
        and model["claimedId"] == model["boundModelId"]
        and is_sha256_ref(model["observedManifestDigest"])
        and isinstance(model["artifactTotalBytes"], int)
        and model["artifactTotalBytes"] > 0
        and model["layers"]
    ):
        return False
    total = 0
    last_end = -1
    member_ids = {row["memberIdHash"] for row in capture["formation"]["members"]}
    for layer in sorted(model["layers"], key=lambda row: row["layerStart"]):
        if not (
            isinstance(layer["layerStart"], int)
            and isinstance(layer["layerEnd"], int)
            and layer["layerStart"] == last_end + 1
            and layer["layerEnd"] >= layer["layerStart"]
            and layer["memberIdHash"] in member_ids
            and is_sha256_ref(layer["artifactDigest"])
            and isinstance(layer["artifactBytes"], int)
            and layer["artifactBytes"] > 0
        ):
            return False
        last_end = layer["layerEnd"]
        total += layer["artifactBytes"]
    return (
        total == model["artifactTotalBytes"]
        and total == capture["formation"]["modelCapacityBytes"]
        and last_end >= 1
    )


def activation_channels_reliable(capture: dict[str, Any]) -> bool:
    channels = capture["transport"]["activationChannels"]
    if not channels:
        return False
    return all(
        row["ordered"] is True
        and row["maxRetransmits"] is None
        and row["maxPacketLifeTime"] is None
        and isinstance(row["bytesSent"], int)
        and row["bytesSent"] >= 0
        and isinstance(row["bytesReceived"], int)
        and row["bytesReceived"] >= 0
        and is_sha256_ref(row["channelIdHash"])
        and (row["bytesSent"] + row["bytesReceived"] > 0)
        for row in channels
    )


def assess_capture(capture: dict[str, Any], profile: dict[str, Any], *, case_id: str | None = None) -> dict[str, Any]:
    validate_capture_shape(capture, profile)
    violations: set[str] = set()
    instrumentation = capture["instrumentation"]
    if (
        instrumentation["installedBeforeApplication"] is not True
        or instrumentation["installedAtMonotonicMs"] > instrumentation["applicationStartMonotonicMs"]
    ):
        violations.add("INSTRUMENTATION_LATE")
    if instrumentation["probeSha256"] != PROBE_SHA256_REF:
        violations.add("PROBE_ARTIFACT_MISMATCH")

    work_unit = capture["workUnit"]
    if work_unit["requiredInterface"] != INTERFACE or work_unit["authorityClass"] != "compute-only":
        violations.add("TASK_INTERFACE_INVALID")
    if work_unit["supplierRef"] is not None:
        violations.add("TASK_SUPPLIER_PINNED")

    limits = capture["limits"]
    if not isinstance(limits["events"], int) or limits["events"] > profile["captureLimits"]["events"]:
        violations.add("CAPTURE_EVENT_CEILING_EXCEEDED")
    if not isinstance(limits["encodedBytes"], int) or limits["encodedBytes"] > profile["captureLimits"]["encodedBytes"]:
        violations.add("CAPTURE_BYTE_CEILING_EXCEEDED")

    members = capture["formation"]["members"]
    member_ids = [row["memberIdHash"] for row in members]
    if len(member_ids) != len(set(member_ids)):
        violations.add("FORMATION_MEMBER_DUPLICATE")
    if any(row["physicallyUnique"] is not True for row in members):
        violations.add("FORMATION_MEMBER_UNIQUENESS_UNPROVED")

    if public_leak(capture["proposedPublicProjection"]):
        violations.add("PUBLIC_PROJECTION_LEAK")
    privacy = capture["privacy"]
    if privacy["claimsEndToEndConfidentiality"] is True:
        violations.add("PRIVACY_CLAIM_EXCEEDS_OBSERVER")
    if capture["supplierAdmissionReceipt"] is not None:
        violations.add("SUPPLIER_SELF_ADMISSION_ATTEMPT")

    live_like = capture["sourceKind"] in {"synthetic-live-capture", "physical-private-local"}
    if live_like:
        availability = capture["availability"]
        if not (availability["observed"] is True and isinstance(availability["observedAtUnixMs"], int) and is_sha256_ref(availability["evidenceRef"])):
            violations.add("AVAILABILITY_OBSERVATION_MISSING")

        adapter = capture["adapter"]
        if not (
            adapter["executableObserved"] is True
            and is_sha256_ref(adapter["artifactDigest"])
            and isinstance(adapter["artifactBytes"], int)
            and adapter["artifactBytes"] > 0
            and is_sha256_ref(adapter["evidenceRef"])
        ):
            violations.add("EXECUTABLE_ADAPTER_ARTIFACT_MISSING")

        formation = capture["formation"]
        if formation["capacityBasis"] == "ui-display":
            violations.add("UI_ONLY_CAPACITY")
        if not (
            formation["artifactBound"] is True
            and formation["capacityBasis"] == "artifact-bound-shards"
            and formation["partitionMode"] == "pipeline-layer"
            and isinstance(formation["modelCapacityBytes"], int)
            and formation["modelCapacityBytes"] > 0
            and is_sha256_ref(formation["capacityReceiptRef"])
            and is_sha256_ref(formation["topologyReceiptRef"])
        ):
            violations.add("ARTIFACT_BINDING_MISSING")
        pledge_sum = sum(row["pledgedBytes"] for row in members if isinstance(row["pledgedBytes"], int))
        if formation["modelCapacityBytes"] > pledge_sum:
            violations.add("ARTIFACT_BINDING_MISSING")

        transport = capture["transport"]
        if not (
            isinstance(transport["peerConnectionCount"], int)
            and transport["peerConnectionCount"] > 0
            and transport["selectedCandidatePairObserved"] is True
            and transport["selectedCandidatePairClass"] in {"host", "srflx", "relay", "prflx"}
        ):
            violations.add("SELECTED_CANDIDATE_PAIR_MISSING")
        if not activation_channels_reliable(capture) or len(transport["activationChannels"]) < max(1, len(members) - 1):
            violations.add("ACTIVATION_CHANNEL_NOT_ORDERED_RELIABLE")

        if not model_identity_complete(capture):
            violations.add("MODEL_IDENTITY_MISMATCH")
        if not performance_complete(capture):
            violations.add("PERFORMANCE_DENOMINATOR_INCOMPLETE")

        drop = capture["drop"]
        if not (
            drop["controlled"] is True
            and drop["memberIdHash"] in set(member_ids)
            and drop["observedTerminal"] in {"HALTED", "DEGRADED_REPLANNED", "RECOVERED"}
            and isinstance(drop["recovered"], bool)
            and is_sha256_ref(drop["evidenceRef"])
        ):
            violations.add("DROP_TERMINAL_MISSING")

        equivalence = capture["equivalence"]
        if not (
            equivalence["match"] is True
            and is_sha256_ref(equivalence["referenceDigest"])
            and equivalence["referenceDigest"] == equivalence["candidateDigest"]
            and equivalence["promptTokenCount"] == capture["performance"]["promptTokenCount"]
            and equivalence["outputTokenCount"] == capture["performance"]["outputTokenCount"]
            and is_sha256_ref(equivalence["evidenceRef"])
        ):
            violations.add("OUTPUT_EQUIVALENCE_MISSING")

        if set(capture["receiptRefs"]) != set(OBSERVATION_RECEIPT_KINDS) or any(
            not is_sha256_ref(capture["receiptRefs"].get(kind)) for kind in OBSERVATION_RECEIPT_KINDS
        ):
            violations.add("RECEIPT_DENOMINATOR_INCOMPLETE")
        if not (
            privacy["declarationPresent"] is True
            and privacy["scope"] == "browser-observed-network-surface-only"
            and is_sha256_ref(privacy["evidenceRef"])
        ):
            violations.add("RECEIPT_DENOMINATOR_INCOMPLETE")

    rebuilt_receipt_digest = observation_receipt_digest(capture)
    if capture["storedReceiptDigest"] != rebuilt_receipt_digest:
        violations.add("STORED_RECEIPT_MISMATCH")

    if violations:
        terminal = "HOLD"
        reason_codes = [code for code in REASON_ORDER if code in violations]
    elif live_like:
        terminal = "OBSERVED_ROUTE_CANDIDATE"
        reason_codes = []
    else:
        terminal = "PREPARED_FOR_PHYSICAL_AUDITION"
        reason_codes = ["PHYSICAL_AUDITION_NOT_EXECUTED"]

    decision = {
        "schema": DECISION_SCHEMA,
        "caseId": case_id,
        "terminal": terminal,
        "reasonCodes": reason_codes,
        "sourceKind": capture["sourceKind"],
        "captureDigest": capture_digest(capture),
        "observationReceiptDigest": rebuilt_receipt_digest,
        "receiptKindsPresent": sorted(capture["receiptRefs"]),
        "syntheticConformanceOnly": capture["syntheticConformanceOnly"],
        "supplierAdmissionReceiptPresent": capture["supplierAdmissionReceipt"] is not None,
        "actualSupplierQualified": False,
        "executionOccurred": False,
        "physicalEstateQualified": False,
        "missionAuthority": "none",
        "commandAuthority": "none",
        "bootstrapAuthenticated": False,
    }
    decision["publicProjection"] = build_public_projection(decision, profile)
    return decision


def build_public_projection(decision: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    public = {
        "schema": PUBLIC_SCHEMA,
        "terminal": decision["terminal"],
        "reasonCodes": decision["reasonCodes"],
        "sourceKind": decision["sourceKind"],
        "captureDigest": decision["captureDigest"],
        "observationReceiptDigest": decision["observationReceiptDigest"],
        "receiptKindsPresent": decision["receiptKindsPresent"],
        "syntheticConformanceOnly": decision["syntheticConformanceOnly"],
        "supplierAdmissionReceiptPresent": decision["supplierAdmissionReceiptPresent"],
        "actualSupplierQualified": False,
        "executionOccurred": False,
        "physicalEstateQualified": False,
        "missionAuthority": "none",
        "commandAuthority": "none",
        "bootstrapAuthenticated": decision["bootstrapAuthenticated"],
    }
    require(set(public) == set(profile["publicProjectionAllowedKeys"]), "PUBLIC_PROJECTION_DENOMINATOR_INVALID", str(sorted(public)))
    require(not public_leak(public), "PUBLIC_PROJECTION_LEAK", "generated public projection contains forbidden material")
    return public


def apply_fixture_mutations(base: dict[str, Any], mutations: list[dict[str, Any]]) -> dict[str, Any]:
    value = copy.deepcopy(base)
    for mutation in mutations:
        require(isinstance(mutation, dict), "FIXTURE_MUTATION_INVALID", str(mutation))
        exact_keys(mutation, {"path", "value"}, "FIXTURE_MUTATION_KEYS_INVALID")
        path = mutation["path"]
        require(isinstance(path, list) and path and all(isinstance(part, (str, int)) for part in path), "FIXTURE_MUTATION_PATH_INVALID", str(path))
        cursor: Any = value
        for part in path[:-1]:
            try:
                cursor = cursor[part]
            except (KeyError, IndexError, TypeError) as exc:
                raise AuditionError("FIXTURE_MUTATION_PATH_INVALID", str(path)) from exc
        try:
            cursor[path[-1]] = copy.deepcopy(mutation["value"])
        except (KeyError, IndexError, TypeError) as exc:
            raise AuditionError("FIXTURE_MUTATION_PATH_INVALID", str(path)) from exc
    return value


def validate_fixture_catalog(path: str | Path, profile: dict[str, Any]) -> dict[str, Any]:
    catalog = load_object(path)
    exact_keys(catalog, {"baseCaptures", "cases", "materializationFixture", "schema"}, "FIXTURE_CATALOG_KEYS_INVALID")
    require(catalog["schema"] == FIXTURE_SCHEMA, "FIXTURE_SCHEMA_INVALID", str(catalog["schema"]))
    require(isinstance(catalog["baseCaptures"], dict), "FIXTURE_BASES_INVALID", "baseCaptures must be object")
    exact_keys(catalog["baseCaptures"], {"complete", "prepared"}, "FIXTURE_BASE_DENOMINATOR_INVALID")
    for name, capture in catalog["baseCaptures"].items():
        require(isinstance(capture, dict), "FIXTURE_BASE_INVALID", name)
        validate_capture_shape(capture, profile)
    materialization_fixture = catalog["materializationFixture"]
    require(isinstance(materialization_fixture, dict), "MATERIALIZATION_FIXTURE_INVALID", "materialization fixture must be object")
    exact_keys(materialization_fixture, {"raw", "control", "expectedReceipt"}, "MATERIALIZATION_FIXTURE_KEYS_INVALID")
    materialized_capture, materialization_receipt = materialize_probe_capture(
        copy.deepcopy(materialization_fixture["raw"]),
        copy.deepcopy(materialization_fixture["control"]),
        profile,
    )
    require(materialized_capture == catalog["baseCaptures"]["complete"], "MATERIALIZATION_FIXTURE_CAPTURE_MISMATCH", "raw/control fixture does not reconstruct complete capture")
    require(materialization_receipt == materialization_fixture["expectedReceipt"], "MATERIALIZATION_FIXTURE_RECEIPT_MISMATCH", "materialization receipt differs")
    require(isinstance(catalog["cases"], list), "FIXTURE_CASES_INVALID", "cases must be list")
    ids: list[str] = []
    terminals: list[str] = []
    expanded_cases: list[dict[str, Any]] = []
    for index, row in enumerate(catalog["cases"]):
        require(isinstance(row, dict), "FIXTURE_CASE_INVALID", f"index={index}")
        exact_keys(
            row,
            {
                "baseCapture",
                "caseId",
                "expectedReasonCodes",
                "expectedTerminal",
                "mutations",
                "rebuildStoredReceipt",
            },
            "FIXTURE_CASE_KEYS_INVALID",
        )
        require(row["caseId"] in CASE_IDS, "FIXTURE_CASE_ID_INVALID", str(row["caseId"]))
        require(row["baseCapture"] in catalog["baseCaptures"], "FIXTURE_BASE_REF_INVALID", str(row["baseCapture"]))
        require(isinstance(row["mutations"], list), "FIXTURE_MUTATIONS_INVALID", str(row["caseId"]))
        require(isinstance(row["rebuildStoredReceipt"], bool), "FIXTURE_REBUILD_FLAG_INVALID", str(row["caseId"]))
        require(row["expectedTerminal"] in TERMINALS, "FIXTURE_TERMINAL_INVALID", str(row["expectedTerminal"]))
        require(isinstance(row["expectedReasonCodes"], list), "FIXTURE_REASONS_INVALID", str(row["expectedReasonCodes"]))
        capture = apply_fixture_mutations(catalog["baseCaptures"][row["baseCapture"]], row["mutations"])
        if row["rebuildStoredReceipt"]:
            capture["storedReceiptDigest"] = observation_receipt_digest(capture)
        decision = assess_capture(copy.deepcopy(capture), profile, case_id=row["caseId"])
        require(decision["terminal"] == row["expectedTerminal"], "FIXTURE_EXPECTATION_INVALID", f"{row['caseId']}: {decision['terminal']}")
        require(decision["reasonCodes"] == row["expectedReasonCodes"], "FIXTURE_REASON_EXPECTATION_INVALID", f"{row['caseId']}: {decision['reasonCodes']}")
        ids.append(row["caseId"])
        terminals.append(row["expectedTerminal"])
        expanded_cases.append(
            {
                "caseId": row["caseId"],
                "expectedTerminal": row["expectedTerminal"],
                "expectedReasonCodes": copy.deepcopy(row["expectedReasonCodes"]),
                "capture": capture,
            }
        )
    require(tuple(ids) == CASE_IDS and len(ids) == len(set(ids)), "CASE_DENOMINATOR_INVALID", str(ids))
    require(tuple(terminals) == EXPECTED_TERMINALS, "TERMINAL_FIXTURE_DENOMINATOR_INVALID", str(terminals))
    return {"schema": catalog["schema"], "baseCaptures": copy.deepcopy(catalog["baseCaptures"]), "materializationFixture": copy.deepcopy(materialization_fixture), "cases": expanded_cases}

def campaign(profile: dict[str, Any], fixtures: dict[str, Any]) -> dict[str, Any]:
    decisions = [assess_capture(copy.deepcopy(row["capture"]), profile, case_id=row["caseId"]) for row in fixtures["cases"]]
    counts = {terminal: sum(row["terminal"] == terminal for row in decisions) for terminal in TERMINALS}
    status = "PASS" if counts == {
        "PREPARED_FOR_PHYSICAL_AUDITION": 1,
        "OBSERVED_ROUTE_CANDIDATE": 1,
        "HOLD": 13,
    } else "REFUSED"
    return {
        "schema": CAMPAIGN_SCHEMA,
        "status": status,
        "caseCount": len(decisions),
        "terminalCounts": counts,
        "decisions": decisions,
        "actualSupplierQualified": False,
        "executionOccurred": False,
        "physicalEstateQualified": False,
        "missionAuthority": "none",
        "commandAuthority": "none",
    }


def source_set(profile: dict[str, Any], repository_root: str | Path) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    members: list[dict[str, Any]] = []
    for relative in profile["sourceMembers"]:
        path = root.joinpath(*relative.split("/"))
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise AuditionError("SOURCE_MEMBER_UNAVAILABLE", f"{relative}: {exc}") from exc
        members.append({"path": relative, "bytes": len(data), "sha256": sha256_bytes(data)})
    body = {
        "schema": "axm-head/browser-distributed-inference-audition-source-set@1",
        "profileId": profile["profileId"],
        "members": members,
    }
    return {**body, "sourceSetId": "axmauditionsource1_" + sha256_bytes(canonical_bytes(body))}


def find_case(fixtures: dict[str, Any], case_id: str) -> dict[str, Any]:
    rows = [row for row in fixtures["cases"] if row["caseId"] == case_id]
    if len(rows) != 1:
        raise AuditionError("CASE_NOT_FOUND", case_id)
    return copy.deepcopy(rows[0])


def emit(value: Any) -> None:
    sys.stdout.buffer.write(pretty_bytes(value))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    command = sub.add_parser("validate-profile")
    command.add_argument("profile")

    command = sub.add_parser("validate-fixtures")
    command.add_argument("profile")
    command.add_argument("fixtures")

    command = sub.add_parser("assess")
    command.add_argument("profile")
    command.add_argument("capture")
    command.add_argument("--case-id")

    command = sub.add_parser("materialize")
    command.add_argument("profile")
    command.add_argument("raw")
    command.add_argument("control")
    command.add_argument("--out")
    command.add_argument("--receipt-out")

    command = sub.add_parser("campaign")
    command.add_argument("profile")
    command.add_argument("fixtures")

    command = sub.add_parser("probe-digest")
    command.add_argument("probe")

    command = sub.add_parser("source-set")
    command.add_argument("profile")
    command.add_argument("repository_root")

    args = parser.parse_args(argv)
    try:
        if args.command == "probe-digest":
            data = Path(args.probe).read_bytes()
            emit({"schema": "axm-head/browser-probe-digest@1", "bytes": len(data), "sha256": sha256_bytes(data)})
            return 0
        profile = validate_profile(args.profile)
        if args.command == "validate-profile":
            emit({"status": "PASS", "schema": profile["schema"], "profileId": profile["profileId"]})
            return 0
        if args.command == "source-set":
            emit(source_set(profile, args.repository_root))
            return 0
        if args.command == "assess":
            capture = load_object(args.capture)
            emit(assess_capture(capture, profile, case_id=args.case_id))
            return 0
        if args.command == "materialize":
            capture, receipt = materialize_probe_capture(load_object(args.raw), load_object(args.control), profile)
            if args.out:
                Path(args.out).write_bytes(pretty_bytes(capture))
            if args.receipt_out:
                Path(args.receipt_out).write_bytes(pretty_bytes(receipt))
            emit(capture)
            return 0
        fixtures = validate_fixture_catalog(args.fixtures, profile)
        if args.command == "validate-fixtures":
            emit({"status": "PASS", "caseCount": len(fixtures["cases"])})
            return 0
        emit(campaign(profile, fixtures))
        return 0
    except AuditionError as exc:
        emit({"status": "REFUSED", "code": exc.code, "message": exc.message})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
