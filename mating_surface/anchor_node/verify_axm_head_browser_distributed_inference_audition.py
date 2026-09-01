from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

PROFILE_SCHEMA = "axm-head-browser-distributed-inference-audition-profile/1"
CAPTURE_SCHEMA = "axm-head/browser-distributed-inference-capture@1"
RAW_CAPTURE_SCHEMA = "axm-head/browser-probe-private-capture@1"
CONTROL_SCHEMA = "axm-head/browser-distributed-inference-audition-control@1"
MATERIALIZATION_SCHEMA = "axm-head/browser-distributed-inference-audition-materialization@1"
DECISION_SCHEMA = "axm-head/browser-distributed-inference-audition-decision@1"
VERDICT_SCHEMA = "axm-head/browser-distributed-inference-audition-verdict@1"
PUBLIC_SCHEMA = "axm-head/browser-distributed-inference-audition-public@1"
INTERFACE = "axm/distributed-model-inference@1"
PROFILE_ID = "axm-head/browser-distributed-inference-audition/0.1"
ISSUE_REF = "BigBirdReturns/ai-execution-audit#92"
SOURCE_FLOOR_COMMIT = "8d18d2c4b6df505751574f219c8c8dd69877a6df"
SOURCE_FLOOR_TREE = "7c8d1786cbae8277c55ca17d115b44c9ec4cae7d"
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


class VerifyError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def pretty_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def sha256_ref(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def load(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VerifyError("JSON_INVALID", f"{path}: {exc}") from exc
    if not isinstance(value, dict):
        raise VerifyError("OBJECT_INVALID", f"{path}: root must be object")
    return value


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise VerifyError(code, message)


def exact_keys(value: dict[str, Any], expected: set[str], code: str) -> None:
    require(isinstance(value, dict), code, f"expected object, got {type(value).__name__}")
    actual = set(value)
    require(actual == set(expected), code, f"missing={sorted(set(expected) - actual)} extra={sorted(actual - set(expected))}")


def is_ref(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def capture_digest(capture: dict[str, Any]) -> str:
    normalized = copy.deepcopy(capture)
    normalized["storedReceiptDigest"] = None
    return sha256_ref(normalized)


def receipt(capture: dict[str, Any]) -> dict[str, Any]:
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
        require(is_ref(row["evidenceRef"]), "CONTROL_MEMBER_EVIDENCE_INVALID", str(row["evidenceRef"]))
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
    capture["storedReceiptDigest"] = sha256_ref(receipt(capture))
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


def public_leak(value: Any) -> bool:
    fragments = (
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
        return any(
            any(fragment in str(key).replace("_", "").replace("-", "").lower() for fragment in fragments)
            or public_leak(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(public_leak(child) for child in value)
    if isinstance(value, str):
        lowered = value.lower()
        return "://" in value or "bearer " in lowered or PRIVATE_ADDRESS_RE.search(value) is not None
    return False


def performance_complete(capture: dict[str, Any]) -> bool:
    perf = capture["performance"]
    try:
        prompt = int(perf["promptTokenCount"])
        output = int(perf["outputTokenCount"])
        start = float(perf["startMonotonicMs"])
        first = float(perf["firstTokenMonotonicMs"])
        last = float(perf["lastTokenMonotonicMs"])
    except (TypeError, ValueError):
        return False
    marks = perf["tokenMarks"]
    if prompt <= 0 or output <= 0 or not (start <= first <= last) or len(marks) != output:
        return False
    return (
        [row.get("index") for row in marks] == list(range(output))
        and [row.get("monotonicMs") for row in marks] == sorted(row.get("monotonicMs") for row in marks)
        and marks[0].get("monotonicMs") == first
        and marks[-1].get("monotonicMs") == last
    )


def model_complete(capture: dict[str, Any]) -> bool:
    model = capture["model"]
    if not (
        isinstance(model["claimedId"], str)
        and model["claimedId"] == model["boundModelId"]
        and is_ref(model["observedManifestDigest"])
        and isinstance(model["artifactTotalBytes"], int)
        and model["artifactTotalBytes"] > 0
        and model["layers"]
    ):
        return False
    member_ids = {row["memberIdHash"] for row in capture["formation"]["members"]}
    total = 0
    previous = -1
    for layer in sorted(model["layers"], key=lambda row: row["layerStart"]):
        if not (
            layer["layerStart"] == previous + 1
            and layer["layerEnd"] >= layer["layerStart"]
            and layer["memberIdHash"] in member_ids
            and is_ref(layer["artifactDigest"])
            and isinstance(layer["artifactBytes"], int)
            and layer["artifactBytes"] > 0
        ):
            return False
        previous = layer["layerEnd"]
        total += layer["artifactBytes"]
    return (
        total == model["artifactTotalBytes"]
        and total == capture["formation"]["modelCapacityBytes"]
        and previous >= 1
    )


def validate_profile(profile: dict[str, Any]) -> None:
    require(profile.get("schema") == PROFILE_SCHEMA, "PROFILE_SCHEMA_INVALID", str(profile.get("schema")))
    require(profile.get("profileId") == PROFILE_ID, "PROFILE_ID_INVALID", str(profile.get("profileId")))
    require(profile.get("status") == "candidate_source_only", "PROFILE_STATUS_INVALID", str(profile.get("status")))
    require(profile.get("issueRef") == ISSUE_REF, "ISSUE_REF_INVALID", str(profile.get("issueRef")))
    require(profile.get("captureLimits") == {"events": 4096, "encodedBytes": 1048576}, "CAPTURE_LIMITS_INVALID", str(profile.get("captureLimits")))
    require(tuple(profile.get("observationReceiptKinds", ())) == OBSERVATION_RECEIPT_KINDS, "RECEIPT_DENOMINATOR_INVALID", str(profile.get("observationReceiptKinds")))
    require(tuple(profile.get("publicProjectionAllowedKeys", ())) == PUBLIC_PROJECTION_ALLOWED_KEYS, "PUBLIC_KEY_DENOMINATOR_INVALID", str(profile.get("publicProjectionAllowedKeys")))
    require(profile.get("claimBoundary") == CLAIM_BOUNDARY, "CLAIM_BOUNDARY_INVALID", str(profile.get("claimBoundary")))
    binding = profile.get("commodityBinding")
    require(isinstance(binding, dict), "COMMODITY_BINDING_INVALID", str(binding))
    require(
        (binding.get("admissionCommit"), binding.get("admissionTree"), binding.get("interface"))
        == (SOURCE_FLOOR_COMMIT, SOURCE_FLOOR_TREE, INTERFACE),
        "COMMODITY_BINDING_INVALID",
        str(binding),
    )
    members = binding.get("productMembers")
    observed = tuple((row.get("path"), row.get("sha")) for row in members if isinstance(row, dict)) if isinstance(members, list) else ()
    require(observed == COMMODITY_PRODUCT_MEMBERS, "COMMODITY_MEMBER_DENOMINATOR_INVALID", str(observed))



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
        require(is_ref(capture["rawEvidenceRef"]), "RAW_EVIDENCE_REF_INVALID", str(capture["rawEvidenceRef"]))
        require(is_ref(capture["controlEvidenceRef"]), "CONTROL_EVIDENCE_REF_INVALID", str(capture["controlEvidenceRef"]))
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
    require(capture["storedReceiptDigest"] is None or is_ref(capture["storedReceiptDigest"]), "STORED_RECEIPT_DIGEST_INVALID", str(capture["storedReceiptDigest"]))
    if capture["supplierAdmissionReceipt"] is not None:
        require(isinstance(capture["supplierAdmissionReceipt"], dict), "SUPPLIER_ADMISSION_RECEIPT_INVALID", "admission receipt must be object or null")

    instrumentation = capture["instrumentation"]
    require(is_ref(instrumentation["probeSha256"]), "PROBE_ARTIFACT_DIGEST_INVALID", str(instrumentation["probeSha256"]))
    for key in ("applicationStartMonotonicMs", "installedAtMonotonicMs"):
        require(isinstance(instrumentation[key], (int, float)) and not isinstance(instrumentation[key], bool), "INSTRUMENTATION_TIME_INVALID", key)
    require(isinstance(instrumentation["installedBeforeApplication"], bool), "INSTRUMENTATION_FLAG_INVALID", str(instrumentation["installedBeforeApplication"]))
    for key in ("events", "encodedBytes"):
        require(isinstance(capture["limits"][key], int) and not isinstance(capture["limits"][key], bool) and capture["limits"][key] >= 0, "CAPTURE_LIMIT_INVALID", key)
    for row in capture["formation"]["members"]:
        require(is_ref(row["memberIdHash"]), "FORMATION_MEMBER_ID_INVALID", str(row["memberIdHash"]))
        require(isinstance(row["physicallyUnique"], bool), "FORMATION_MEMBER_UNIQUENESS_INVALID", str(row["physicallyUnique"]))
        require(isinstance(row["pledgedBytes"], int) and row["pledgedBytes"] > 0, "FORMATION_PLEDGE_INVALID", str(row["pledgedBytes"]))
        require(isinstance(row["role"], str) and row["role"], "FORMATION_ROLE_INVALID", str(row["role"]))
    for row in capture["transport"]["activationChannels"]:
        require(is_ref(row["channelIdHash"]), "ACTIVATION_CHANNEL_ID_INVALID", str(row["channelIdHash"]))
    require(all(is_ref(row) for row in capture["transport"]["signalingEndpointHashes"]), "SIGNALING_ENDPOINT_HASH_INVALID", str(capture["transport"]["signalingEndpointHashes"]))

def reconstruct(capture: dict[str, Any], profile: dict[str, Any]) -> tuple[str, list[str], str, str]:
    validate_profile(profile)
    validate_capture_shape(capture, profile)
    live_capture = capture["sourceKind"] in {"synthetic-live-capture", "physical-private-local"}
    violations: set[str] = set()
    instrumentation = capture["instrumentation"]
    if (
        instrumentation["installedBeforeApplication"] is not True
        or instrumentation["installedAtMonotonicMs"] > instrumentation["applicationStartMonotonicMs"]
    ):
        violations.add("INSTRUMENTATION_LATE")
    if instrumentation["probeSha256"] != PROBE_SHA256_REF:
        violations.add("PROBE_ARTIFACT_MISMATCH")
    work = capture["workUnit"]
    if work["requiredInterface"] != INTERFACE or work["authorityClass"] != "compute-only":
        violations.add("TASK_INTERFACE_INVALID")
    if work["supplierRef"] is not None:
        violations.add("TASK_SUPPLIER_PINNED")
    events = capture["limits"]["events"]
    encoded = capture["limits"]["encodedBytes"]
    if not isinstance(events, int) or isinstance(events, bool) or events < 0 or events > profile["captureLimits"]["events"]:
        violations.add("CAPTURE_EVENT_CEILING_EXCEEDED")
    if not isinstance(encoded, int) or isinstance(encoded, bool) or encoded < 0 or encoded > profile["captureLimits"]["encodedBytes"]:
        violations.add("CAPTURE_BYTE_CEILING_EXCEEDED")
    members = capture["formation"]["members"]
    ids = [row["memberIdHash"] for row in members]
    if len(ids) != len(set(ids)):
        violations.add("FORMATION_MEMBER_DUPLICATE")
    if any(row["physicallyUnique"] is not True for row in members):
        violations.add("FORMATION_MEMBER_UNIQUENESS_UNPROVED")
    if public_leak(capture["proposedPublicProjection"]):
        violations.add("PUBLIC_PROJECTION_LEAK")
    if capture["privacy"]["claimsEndToEndConfidentiality"] is True:
        violations.add("PRIVACY_CLAIM_EXCEEDS_OBSERVER")
    if capture["supplierAdmissionReceipt"] is not None:
        violations.add("SUPPLIER_SELF_ADMISSION_ATTEMPT")

    live = live_capture
    if live:
        availability = capture["availability"]
        if not (availability["observed"] is True and is_ref(availability["evidenceRef"])):
            violations.add("AVAILABILITY_OBSERVATION_MISSING")
        adapter = capture["adapter"]
        if not (
            adapter["executableObserved"] is True
            and is_ref(adapter["artifactDigest"])
            and adapter["artifactBytes"] > 0
            and is_ref(adapter["evidenceRef"])
        ):
            violations.add("EXECUTABLE_ADAPTER_ARTIFACT_MISSING")
        formation = capture["formation"]
        if formation["capacityBasis"] == "ui-display":
            violations.add("UI_ONLY_CAPACITY")
        if not (
            formation["artifactBound"] is True
            and formation["capacityBasis"] == "artifact-bound-shards"
            and formation["partitionMode"] == "pipeline-layer"
            and formation["modelCapacityBytes"] > 0
            and is_ref(formation["capacityReceiptRef"])
            and is_ref(formation["topologyReceiptRef"])
        ):
            violations.add("ARTIFACT_BINDING_MISSING")
        if formation["modelCapacityBytes"] > sum(row["pledgedBytes"] for row in members):
            violations.add("ARTIFACT_BINDING_MISSING")
        transport = capture["transport"]
        if not (
            transport["peerConnectionCount"] > 0
            and transport["selectedCandidatePairObserved"] is True
            and transport["selectedCandidatePairClass"] in {"host", "srflx", "relay", "prflx"}
        ):
            violations.add("SELECTED_CANDIDATE_PAIR_MISSING")
        channels = transport["activationChannels"]
        if not channels or not all(
            row["ordered"] is True
            and row["maxRetransmits"] is None
            and row["maxPacketLifeTime"] is None
            and row["bytesSent"] >= 0
            and row["bytesReceived"] >= 0
            and is_ref(row["channelIdHash"])
            and (row["bytesSent"] + row["bytesReceived"] > 0)
            for row in channels
        ) or len(channels) < max(1, len(members) - 1):
            violations.add("ACTIVATION_CHANNEL_NOT_ORDERED_RELIABLE")
        if not model_complete(capture):
            violations.add("MODEL_IDENTITY_MISMATCH")
        if not performance_complete(capture):
            violations.add("PERFORMANCE_DENOMINATOR_INCOMPLETE")
        drop = capture["drop"]
        if not (
            drop["controlled"] is True
            and drop["memberIdHash"] in set(ids)
            and drop["observedTerminal"] in {"HALTED", "DEGRADED_REPLANNED", "RECOVERED"}
            and is_ref(drop["evidenceRef"])
        ):
            violations.add("DROP_TERMINAL_MISSING")
        eq = capture["equivalence"]
        if not (
            eq["match"] is True
            and is_ref(eq["referenceDigest"])
            and eq["referenceDigest"] == eq["candidateDigest"]
            and eq["promptTokenCount"] == capture["performance"]["promptTokenCount"]
            and eq["outputTokenCount"] == capture["performance"]["outputTokenCount"]
            and is_ref(eq["evidenceRef"])
        ):
            violations.add("OUTPUT_EQUIVALENCE_MISSING")
        privacy = capture["privacy"]
        if not (
            set(capture["receiptRefs"]) == set(OBSERVATION_RECEIPT_KINDS)
            and all(is_ref(capture["receiptRefs"].get(kind)) for kind in OBSERVATION_RECEIPT_KINDS)
            and privacy["declarationPresent"] is True
            and privacy["scope"] == "browser-observed-network-surface-only"
            and is_ref(privacy["evidenceRef"])
        ):
            violations.add("RECEIPT_DENOMINATOR_INCOMPLETE")

    captured = capture_digest(capture)
    receipt_digest = sha256_ref(receipt(capture))
    if capture["storedReceiptDigest"] != receipt_digest:
        violations.add("STORED_RECEIPT_MISMATCH")
    if violations:
        return "HOLD", [code for code in REASON_ORDER if code in violations], captured, receipt_digest
    if live:
        return "OBSERVED_ROUTE_CANDIDATE", [], captured, receipt_digest
    return "PREPARED_FOR_PHYSICAL_AUDITION", ["PHYSICAL_AUDITION_NOT_EXECUTED"], captured, receipt_digest


def verify(
    profile: dict[str, Any],
    capture: dict[str, Any],
    decision: dict[str, Any],
    *,
    raw: dict[str, Any] | None = None,
    control: dict[str, Any] | None = None,
) -> dict[str, Any]:
    require(decision.get("schema") == DECISION_SCHEMA, "DECISION_SCHEMA_INVALID", str(decision.get("schema")))
    require((raw is None) == (control is None), "RAW_CONTROL_PAIR_REQUIRED", "raw and control must be supplied together")
    raw_reconstructed = False
    if capture.get("sourceKind") in {"synthetic-live-capture", "physical-private-local"}:
        require(raw is not None and control is not None, "RAW_EVIDENCE_NOT_SUPPLIED", "live capture verification requires raw probe capture and control")
    if raw is not None and control is not None:
        materialized, _ = materialize_probe_capture(raw, control, profile)
        require(materialized == capture, "RAW_MATERIALIZATION_MISMATCH", "normalized capture differs from independently reconstructed raw/control materialization")
        raw_reconstructed = True
    terminal, reasons, captured, receipt_digest = reconstruct(capture, profile)
    require(decision.get("terminal") == terminal, "TERMINAL_MISMATCH", f"stored={decision.get('terminal')} rebuilt={terminal}")
    require(decision.get("reasonCodes") == reasons, "REASON_CODES_MISMATCH", str(decision.get("reasonCodes")))
    require(decision.get("captureDigest") == captured, "CAPTURE_DIGEST_MISMATCH", str(decision.get("captureDigest")))
    require(decision.get("observationReceiptDigest") == receipt_digest, "RECEIPT_DIGEST_MISMATCH", str(decision.get("observationReceiptDigest")))
    require(decision.get("actualSupplierQualified") is False, "SUPPLIER_CLAIM_PROMOTED", "actual supplier qualified")
    require(decision.get("supplierAdmissionReceiptPresent") is False, "SUPPLIER_ADMISSION_PROMOTED", "admission receipt present")
    require(decision.get("executionOccurred") is False, "EXECUTION_CLAIM_PROMOTED", "execution occurred")
    require(decision.get("physicalEstateQualified") is False, "ESTATE_CLAIM_PROMOTED", "physical Estate qualified")
    require(decision.get("missionAuthority") == "none" and decision.get("commandAuthority") == "none", "AUTHORITY_PROMOTED", "authority changed")
    require(decision.get("bootstrapAuthenticated") is False, "DIRECT_VERIFIER_SELF_AUTHENTICATED", "direct decision claims bootstrap")
    public = decision.get("publicProjection")
    require(isinstance(public, dict) and public.get("schema") == PUBLIC_SCHEMA, "PUBLIC_PROJECTION_INVALID", str(public))
    require(set(public) == set(profile["publicProjectionAllowedKeys"]), "PUBLIC_PROJECTION_DENOMINATOR_INVALID", str(sorted(public)))
    require(not public_leak(public), "PUBLIC_PROJECTION_LEAK", "stored public projection leaks")
    require(public.get("captureDigest") == captured and public.get("observationReceiptDigest") == receipt_digest, "PUBLIC_PROJECTION_BINDING_INVALID", "projection not bound")
    decision_digest = sha256_ref(decision)
    return {
        "schema": VERDICT_SCHEMA,
        "status": "PASS",
        "terminal": terminal,
        "reasonCodes": reasons,
        "captureDigest": captured,
        "observationReceiptDigest": receipt_digest,
        "decisionDigest": decision_digest,
        "storedReceiptReconstructed": True,
        "publicProjectionReconstructed": True,
        "rawEvidenceReconstructed": raw_reconstructed,
        "bootstrapAuthenticated": False,
        "actualSupplierQualified": False,
        "supplierAdmissionReceiptPresent": False,
        "executionOccurred": False,
        "physicalEstateQualified": False,
        "missionAuthority": "none",
        "commandAuthority": "none",
    }


def emit(value: Any) -> None:
    sys.stdout.buffer.write(pretty_bytes(value))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile")
    parser.add_argument("capture")
    parser.add_argument("decision")
    parser.add_argument("--raw")
    parser.add_argument("--control")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    try:
        verdict = verify(
            load(args.profile),
            load(args.capture),
            load(args.decision),
            raw=load(args.raw) if args.raw else None,
            control=load(args.control) if args.control else None,
        )
        data = pretty_bytes(verdict)
        if args.out:
            Path(args.out).write_bytes(data)
        sys.stdout.buffer.write(data)
        return 0
    except (VerifyError, KeyError, TypeError, ValueError) as exc:
        code = exc.code if isinstance(exc, VerifyError) else "STRUCTURE_INVALID"
        message = exc.message if isinstance(exc, VerifyError) else str(exc)
        body = {"schema": VERDICT_SCHEMA, "status": "REFUSED", "code": code, "message": message, "bootstrapAuthenticated": False}
        data = pretty_bytes(body)
        if args.out:
            Path(args.out).write_bytes(data)
        sys.stdout.buffer.write(data)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
