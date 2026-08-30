from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import stat
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any, Iterable, Mapping

PROFILE_SCHEMA = "axm-head/physical-long-haul-profile@2"
PROFILE_ID = "axm-head/physical-long-haul@2"
JOIN_NAME = "AXM-HEAD-PHYSICAL-LONG-HAUL-001-JOIN-v2"
INPUT_SCHEMA = "axm-head/physical-long-haul-input@2"
FIXTURE_CATALOG_SCHEMA = "axm-head/physical-long-haul-fixture-catalog@2"
SOURCE_BINDING_SCHEMA = "axm-head/physical-flight-source-binding@2"
ROUTE_ATTESTATION_SCHEMA = "axm-head/physical-route-attestation@2"
CONTINUITY_ATTESTATION_SCHEMA = "axm-head/continuity-attestation@2"
TWO_CELL_ATTESTATION_SCHEMA = "axm-head/two-cell-attestation@2"
SUCCESSOR_ATTESTATION_SCHEMA = "axm-head/successor-attestation@2"
DISPOSITION_BINDING_SCHEMA = "axm-head/private-flight-disposition-binding@2"
JOIN_SCHEMA = "axm-head/physical-long-haul-join@2"
VERIFICATION_SCHEMA = "axm-head/physical-long-haul-verification@2"
PUBLIC_STATUS_SCHEMA = "axm-head/physical-long-haul-public-status@2"
ENVELOPE_SCHEMA = "axm-head/physical-long-haul-verifier-envelope@2"
PREFLIGHT_REFERENCE_SCHEMA = "axm-head/preflight-disposition-reference@1"
AUTHORIZATION_SCHEMA = "stc-mary/named-human-authorization@1"
STAGE_RECEIPT_SCHEMA = "stc-mary/private-flight-stage-receipt@1"
PRIVATE_EVIDENCE_PROVENANCE_SCHEMA = "axm-head/private-evidence-provenance@2"
PRIVATE_EVIDENCE_PROVENANCE_PAYLOAD_SCHEMA = "axm-head/private-evidence-provenance-payload@2"
PRIVATE_EVIDENCE_PROVENANCE_ALGORITHM = "rsa-pkcs1v15-sha256"
EXPECTED_CAMPAIGN_ID = "PRIVATE-STC-MARY-FLIGHT-01"
EXPECTED_AUTHORIZATION_SCOPE = "private-stc-mary-flight-01"

PRIVATE_EVIDENCE_PROVENANCE_TRUST_ROOT = {
    "algorithm": "rsa-pkcs1v15-sha256",
    "keyId": "axmheadprivateevidencetrustroot1_a7433c79c93efa9af76915fbac14a65807425c73e1a156068e0645fb1fa1301e",
    "modulusHex": "cfcca8d34a7a813578450b4796b64dc5d925e776e69eb47bc396f00c42f583be3d435a78a88f67fc569ace656f4167d50a2a5c5fe1a4eaf607f3c0dcc390c643685c731e2f4d3b16da76bd00858500a5c3162fafb03587c26309a2251079396afdffd5554a14bc664406cd7d9a3b02e391453c3f40fa72512791172995bfb9600a6378e7e39680f5dd6ea7aaf93f7ab248c85abc03f7ba110416703a7c03d863e258f59754c1a79ec69ff39973916c4e9b8eba7ace15a511f41d3b5b2c1587fc330d302766b2645b90c05e9c3630a431373a0c1af9224d9eeb91a42dbc784617a3d097093a1195e66c8a68201756197df892c90cdc80b2ebe6d346af15442e99",
    "publicExponent": 65537
}
RSA_SHA256_DIGEST_INFO_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")

# Filled after the profile and verifier are frozen.
PROFILE_CANONICAL_SHA256 = "81a876b4b525e514abc72bf1ca005636fed54d54f55474d002176841b0044a64"
FIXTURE_CATALOG_CANONICAL_SHA256 = "a90866a8d561769d61337a39d76d1f89a37bfe72d9de076195e9055367cdd41a"

TERMINALS = ("PREPARED_NOT_ARMED", "PRIVATE_SELF_ATTESTED", "HOLD")
EVIDENCE_TIERS = ("none", "synthetic", "private_local_attested")
PREFLIGHT_TERMINALS = ("PREPARED_NOT_ARMED", "HOLD", "READY_FOR_HUMAN_REVIEW", "REFUSED")

STAGE_SEQUENCE = (
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

EXPECTED_STAGE_TERMINALS = {
    stage: ("HUMAN_REQUIRED" if stage == "RESTORE_LINK_HOLD_CONFLICT" else "PASS")
    for stage in STAGE_SEQUENCE
}

PREFLIGHT_PHASE_SEQUENCE = (
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

PREFLIGHT_STOP_CONDITIONS = (
    "source_coordinate_drift",
    "dirty_or_moving_checkout",
    "private_coordinate_mismatch",
    "unexpected_worker_or_listener",
    "authorization_field_present",
    "authority_not_none",
    "receipt_refusal",
    "physical_action_before_separate_authorization",
)

PREFLIGHT_RECEIPT_CLASSES = (
    "conductor_source_receipt",
    "conductor_artifact_coordinate",
    "stc-mary-local-readiness-private/1",
    "stc-mary-invented-aperture-feed/1",
    "stc-mary-aperture-workload-result/1",
    "stc-mary-aperture-workload-verification/1",
    "stc-mary-aperture-workload-comparison/1",
    "stc-mary-offline-two-cell-verification/1",
    "stc-mary-offline-successor-verification/1",
    "stc-mary-local-flight-plan/1",
    "stc-mary-private-flight-packet-config/1",
    "stc-mary-private-flight-packet-status/1",
    "stc-mary-private-flight-packet-state/1",
    "stc-mary-private-flight-sealed-verification/1",
    "stc-mary-physical-flight-public-disposition/1",
)

COLD_SUCCESSOR_ANSWER_KEYS = (
    "whatMission",
    "currentState",
    "whoMayAct",
    "whatProvesIt",
    "whatRemainsUnresolved",
    "nextSafeAction",
)

OBJECT_SCHEMAS = (
    PROFILE_SCHEMA,
    SOURCE_BINDING_SCHEMA,
    ROUTE_ATTESTATION_SCHEMA,
    CONTINUITY_ATTESTATION_SCHEMA,
    TWO_CELL_ATTESTATION_SCHEMA,
    SUCCESSOR_ATTESTATION_SCHEMA,
    DISPOSITION_BINDING_SCHEMA,
    JOIN_SCHEMA,
    VERIFICATION_SCHEMA,
    PUBLIC_STATUS_SCHEMA,
)

CASE_IDS = (
    "prepared-exact-public-sources-no-private-flight",
    "hold-complete-synthetic-private-shape",
    "hold-preflight-card-substituted-for-human-authorization",
    "hold-incomplete-private-receipt-denominator",
    "hold-broken-stage-predecessor-chain",
    "hold-same-host-two-cell-attestation",
    "hold-wrong-conflict-terminal",
    "hold-successor-answer-forgery",
    "hold-sealed-package-verification-failure",
    "hold-preflight-not-ready-for-human-review",
)

EXPECTED_PUBLIC_SOURCES = {
    "admittedAxmHeadSupplier": {
        "repository": "BigBirdReturns/ai-execution-audit",
        "commit": "b452bb32e26249deab90db124f157bc62ad0850d",
        "tree": "c557bddc17ad62f6ad36bac5a6ef57338429a951",
        "status": "admitted_synthetic_contract",
    },
    "admittedConductor": {
        "repository": "BigBirdReturns/ai-execution-audit",
        "commit": "dd486472a8c610a20ee062dd6746c86fe8ede4b4",
        "tree": "d17a6d9554ee60aa692985af4e6771a4ee00ef85",
        "archiveSha256": "ff415d5b6f0033a1bdb9ae3b5f49828766e61ce668a8213ef3ad176908bd30dc",
        "predecessorCommits": [
            "772ce582e1b19b7a2060c50be8ebf40c1f8723b2",
            "ccc6f1bb817614d0948900499c80f4f91e8bade0",
            "1047b90d2c2077cff297b9d5e24e333fe7dcf8cc",
            "a99c1c76daf383edd31ada2e3a8f8bf5c57a7888",
        ],
        "status": "admitted_bounded_single_action_operator",
    },
    "physicalFlightFloor": {
        "repository": "BigBirdReturns/ai-execution-audit",
        "commit": "d31e59f5fd30e57b1917c00832b189ee2ea3e12f",
        "tree": "2a6a155e9615eb847781f87566bac32d4c9dc126",
        "status": "admitted_not_executed",
    },
    "admittedPreflightReviewCard": {
        "repository": "BigBirdReturns/ai-execution-audit",
        "commit": "ec61bc3488cb5ae06ed9db2862a9f6910d310a79",
        "tree": "d2daba1d32a8de744b8b90f6cd42f7c4bff4fa67",
        "profileSchema": "axm-head/physical-flight-preflight-review-card-profile/1",
        "profileId": "axm-head/physical-flight-preflight-review-card@1",
        "profileCanonicalSha256": "c0ef16ec7d7fbea70d59618d2a7c59cec42178c61cfeb564c839969e40ce2f56",
        "standaloneVerifierSha256": "c483507c0246fdcc502e21f60937f0ff81df020871120ab56abd619131ef49d2",
        "status": "admitted_preflight_contract",
    },
    "physicalFlightIssue": {
        "repository": "BigBirdReturns/ai-execution-audit",
        "issueNumber": 37,
        "role": "sole_private_physical_flight_execution_coordinate",
    },
}

EXPECTED_SOURCE_DIGESTS = {
    "axmProfileCanonicalSha256": "c6529dbe52c678f8ae7ede650b706b1de22f10f6444dd99a5720e41b03cf7078",
    "axmFixtureCatalogCanonicalSha256": "82e4bf7e8d18fae61a1e17d1cf758d46004d08dd4b877f933be5c96663b67291",
    "axmStandaloneVerifierSha256": "8ca6d225fc162e78fb1af41c9cd89c188491a08fe71a69b58c6c12cd9acf4e44",
    "axmExternalBootstrapSha256": "885a2de66ac339d410bfebed97967fd863e3b7ad77ff3f0e9823ce6c94497d76",
    "conductorProfileRawSha256": "ca1fa71c7168dbcca9ff3e77930d06621350f5509ca922968eb3b40e709cadeb",
    "physicalFlightProfileCanonicalSha256": "3b987b9288083f52d30ba6fc5598b190169d1b30c1860556b302c7461df246b7",
    "privatePacketProfileCanonicalSha256": "9208b6c28556ee2ba04a1bfdbc792dba457891fa9a8394aa80913a8e66dcd65c",
    "preflightProfileCanonicalSha256": "c0ef16ec7d7fbea70d59618d2a7c59cec42178c61cfeb564c839969e40ce2f56",
    "preflightStandaloneVerifierSha256": "c483507c0246fdcc502e21f60937f0ff81df020871120ab56abd619131ef49d2",
}

CLAIM_BOUNDARY = (
    "Provider-free postflight verification membrane for one private STC MARY physical-flight self-attestation. "
    "It binds exact admitted public sources, a distinct named-human authorization receipt, a complete private "
    "sixteen-stage denominator, route and continuity attestations, two distinct physical cells, HUMAN_REQUIRED "
    "reunion custody, replacement-HEAD recovery, six independently reconstructed cold-successor answers, and a "
    "detached verified sealed package. PRIVATE_SELF_ATTESTED remains local self-attestation only and grants no "
    "physical Estate, representative-operator, field-network, operational-C2, production-Lattice, mission, command, "
    "targeting, engagement, effector, or weapons qualification or authority."
)

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SHA256_REF = re.compile(r"^sha256:[0-9a-f]{64}$")
CONTENT_ID = re.compile(r"^[a-z0-9][a-z0-9._-]*_[0-9a-f]{64}$")
BASE64URL = re.compile(r"^[A-Za-z0-9_-]+$")
BOUNDED_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{2,255}$")
HOST_CLASS = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
WINDOWS_PATH_RE = re.compile(r"(?i)(?:^|[\s\"'])(?:[a-z]:[\\/]|\\\\[^\\/]+[\\/])")
POSIX_ABSOLUTE_PATH_RE = re.compile(r"(?:^|[\s\"'(=])(?:/|~/)[^\s\"'<>|]+")
POSIX_RELATIVE_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9._~+@-])(?:"
    r"(?:\.{1,2}|~)/(?:[A-Za-z0-9._~+@-]+)(?:/[A-Za-z0-9._~+@-]+)*"
    r"|(?:[A-Za-z0-9._~+@-]+/){3,}[A-Za-z0-9._~+@-]+"
    r"|(?:[A-Za-z0-9._~+@-]+/){2,}[A-Za-z0-9_~+@-][A-Za-z0-9._~+@-]*\.[A-Za-z0-9][A-Za-z0-9._-]*"
    r")(?![A-Za-z0-9._~+@-])",
    re.I,
)
IPV4_RE = re.compile(r"(?<![0-9])(?:25[0-5]|2[0-4][0-9]|1?[0-9]{1,2})(?:\.(?:25[0-5]|2[0-4][0-9]|1?[0-9]{1,2})){3}(?![0-9])")
URI_RE = re.compile(r"(?i)\b(?:https?|ssh|tcp|udp|ws|wss)://")
CREDENTIAL_RE = re.compile(r"AKIA[0-9A-Z]{16}|BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY|Authorization:\s*Bearer|SYNTHETIC-CREDENTIAL-[A-Za-z0-9._-]+", re.I)
PRIVATE_HOST_RE = re.compile(r"\b(?:OCTO-(?:W|L|N)\d+|PRIVATE-HOST-\d+)\b", re.I)
MAX_JSON_BYTES = 32 * 1024 * 1024
MAX_VERIFIER_BYTES = 4 * 1024 * 1024

FORBIDDEN_PRIVATE_KEYS = {
    "privatePath",
    "hostname",
    "endpoint",
    "credential",
    "environment",
    "operatorRecord",
    "stdout",
    "stderr",
    "telemetryBody",
    "evidenceBody",
    "evidenceFilename",
    "hardwareSerial",
    "seatIdentity",
}


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


def pretty_json_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        fail("NON_CANONICAL_JSON", str(exc))
    return (text + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def content_id(prefix: str, body: Mapping[str, Any]) -> str:
    return f"{prefix}_{sha256_bytes(canonical_json_bytes(dict(body)))}"


def base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def base64url_decode(value: str, label: str) -> bytes:
    require_string(value, label, BASE64URL, maximum=8192)
    padding = "=" * ((4 - len(value) % 4) % 4)
    try:
        decoded = base64.urlsafe_b64decode((value + padding).encode("ascii"))
    except (binascii.Error, ValueError, UnicodeError) as exc:
        fail("PROVENANCE_SIGNATURE_ENCODING_INVALID", f"{label}: {exc}")
    if base64url_encode(decoded) != value:
        fail("PROVENANCE_SIGNATURE_ENCODING_INVALID", f"{label}: noncanonical base64url encoding")
    return decoded


def rsa_pkcs1_v1_5_encoded_message(message: bytes, modulus: int) -> bytes:
    digest_info = RSA_SHA256_DIGEST_INFO_PREFIX + hashlib.sha256(message).digest()
    width = (modulus.bit_length() + 7) // 8
    padding_length = width - len(digest_info) - 3
    if width < 256 or padding_length < 8:
        fail("PROVENANCE_TRUST_ROOT_INVALID", "RSA provenance trust root must be at least 2048 bits")
    return b"\x00\x01" + (b"\xff" * padding_length) + b"\x00" + digest_info


def verify_rsa_pkcs1_v1_5_sha256(message: bytes, signature: bytes, trust_root: Mapping[str, Any]) -> bool:
    try:
        modulus = int(str(trust_root["modulusHex"]), 16)
        exponent = int(trust_root["publicExponent"])
    except (KeyError, TypeError, ValueError):
        return False
    width = (modulus.bit_length() + 7) // 8
    if len(signature) != width or exponent != 65537:
        return False
    signature_integer = int.from_bytes(signature, "big")
    if signature_integer >= modulus:
        return False
    encoded = pow(signature_integer, exponent, modulus).to_bytes(width, "big")
    try:
        expected = rsa_pkcs1_v1_5_encoded_message(message, modulus)
    except JoinError:
        return False
    return hmac.compare_digest(encoded, expected)


def read_regular_file_bytes(path: Path, *, label: str, maximum: int) -> bytes:
    try:
        before = path.lstat()
    except OSError as exc:
        fail("FILE_READ_FAILED", f"{label}: {path}: {exc}")
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        fail("REGULAR_FILE_REQUIRED", f"{label}: {path} must be one regular non-symlink file")
    if before.st_size > maximum:
        fail("FILE_SIZE_LIMIT", f"{label}: {path} exceeds {maximum} bytes")

    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        fail("FILE_READ_FAILED", f"{label}: {path}: {exc}")
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            fail("REGULAR_FILE_REQUIRED", f"{label}: {path} did not open as a regular file")
        if before.st_dev != opened.st_dev or before.st_ino != opened.st_ino:
            fail("FILE_IDENTITY_CHANGED", f"{label}: {path} changed before it was opened")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, maximum + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum:
                fail("FILE_SIZE_LIMIT", f"{label}: {path} exceeds {maximum} bytes")
        after = os.fstat(descriptor)
        stable = (
            opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns
        ) == (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns
        )
        if not stable:
            fail("FILE_CHANGED_DURING_READ", f"{label}: {path} changed while it was measured")
        data = b"".join(chunks)
        if len(data) != after.st_size:
            fail("FILE_SIZE_CHANGED", f"{label}: {path} measured byte count differs from file size")
        return data
    finally:
        os.close(descriptor)


def current_verifier_sha256() -> str:
    return sha256_bytes(
        read_regular_file_bytes(Path(__file__), label="standalone verifier", maximum=MAX_VERIFIER_BYTES)
    )


def body_without(value: Mapping[str, Any], key: str) -> dict[str, Any]:
    result = dict(value)
    result.pop(key, None)
    return result


def assert_content_id(value: Mapping[str, Any], id_key: str, prefix: str, code: str) -> None:
    observed = require_string(value.get(id_key), id_key, CONTENT_ID)
    expected = content_id(prefix, body_without(value, id_key))
    if observed != expected:
        fail(code, f"{id_key} differs from canonical content identity")


def parse_json_object_bytes(data: bytes, *, label: str) -> dict[str, Any]:
    if data.startswith(b"\xef\xbb\xbf"):
        fail("UTF8_BOM_FORBIDDEN", f"{label} contains a UTF-8 BOM")

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                fail("DUPLICATE_JSON_KEY", f"{label} contains duplicate key {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=reject_duplicate_keys)
    except JoinError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        fail("JSON_READ_FAILED", f"{label}: {exc}")
    if not isinstance(value, dict):
        fail("JSON_OBJECT_REQUIRED", f"{label} must contain one JSON object")
    return value


def read_json(path: Path) -> dict[str, Any]:
    data = read_regular_file_bytes(path, label="JSON input", maximum=MAX_JSON_BYTES)
    return parse_json_object_bytes(data, label=str(path))


def require_exact_keys(value: Any, expected: Iterable[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        fail("OBJECT_REQUIRED", f"{label} must be an object")
    actual = set(value)
    required = set(expected)
    if actual != required:
        fail("OBJECT_KEYS_INVALID", f"{label} missing={sorted(required - actual)} unknown={sorted(actual - required)}")
    return value


def require_string(value: Any, label: str, pattern: re.Pattern[str] | None = None, *, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        fail("STRING_REQUIRED", f"{label} must be a non-empty string no longer than {maximum} characters")
    if pattern is not None and pattern.fullmatch(value) is None:
        fail("STRING_PATTERN_INVALID", f"{label} has an invalid value")
    return value


def require_optional_string(value: Any, label: str, pattern: re.Pattern[str] | None = None, *, maximum: int = 4096) -> str | None:
    if value is None:
        return None
    return require_string(value, label, pattern, maximum=maximum)


def require_bool(value: Any, label: str) -> bool:
    if type(value) is not bool:
        fail("BOOLEAN_REQUIRED", f"{label} must be boolean")
    return value


def require_int(value: Any, label: str, minimum: int = 0, maximum: int = 2**63 - 1) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        fail("INTEGER_REQUIRED", f"{label} must be an integer in [{minimum}, {maximum}]")
    return value


def require_list(value: Any, label: str, *, maximum: int = 256) -> list[Any]:
    if not isinstance(value, list) or len(value) > maximum:
        fail("LIST_REQUIRED", f"{label} must be a list with no more than {maximum} entries")
    return value


def require_string_list(value: Any, label: str, *, maximum: int = 256, unique: bool = True) -> list[str]:
    items = require_list(value, label, maximum=maximum)
    result = [require_string(item, f"{label}[{index}]") for index, item in enumerate(items)]
    if unique and len(result) != len(set(result)):
        fail("DUPLICATE_LIST_VALUE", f"{label} contains duplicate values")
    return result


def scan_forbidden_private_material(value: Any, label: str = "input") -> None:
    def walk(node: Any, path: str) -> None:
        if isinstance(node, Mapping):
            for key, child in node.items():
                if key in FORBIDDEN_PRIVATE_KEYS:
                    fail("PRIVATE_MATERIAL_KEY_FORBIDDEN", f"{path}.{key} is not an allowlisted body-free field")
                walk(child, f"{path}.{key}")
        elif isinstance(node, list):
            for index, child in enumerate(node):
                walk(child, f"{path}[{index}]")
        elif isinstance(node, str):
            if WINDOWS_PATH_RE.search(node):
                fail("PRIVATE_PATH_DETECTED", f"{path} contains a Windows or UNC path")
            if POSIX_ABSOLUTE_PATH_RE.search(node) or POSIX_RELATIVE_PATH_RE.search(node):
                fail("PRIVATE_PATH_DETECTED", f"{path} contains a POSIX absolute or path-shaped relative value")
            if PRIVATE_HOST_RE.search(node):
                fail("PRIVATE_HOST_DETECTED", f"{path} contains a private Estate host identity")
            if IPV4_RE.search(node):
                fail("PRIVATE_ENDPOINT_DETECTED", f"{path} contains an IPv4 endpoint")
            if URI_RE.search(node):
                fail("PRIVATE_ENDPOINT_DETECTED", f"{path} contains a network endpoint")
            if CREDENTIAL_RE.search(node):
                fail("CREDENTIAL_MATERIAL_DETECTED", f"{path} contains credential-shaped material")

    walk(value, label)


def validate_profile_value(profile: dict[str, Any]) -> dict[str, Any]:
    require_exact_keys(
        profile,
        {
            "schema",
            "profileId",
            "joinName",
            "status",
            "owningProject",
            "repository",
            "sourceBindings",
            "sourceDigests",
            "objectSchemas",
            "terminalStates",
            "evidenceTiers",
            "privateEvidenceProvenanceTrustRoot",
            "stageSequence",
            "preflightPhaseSequence",
            "preflightStopConditions",
            "preflightReceiptClasses",
            "coldSuccessorAnswerKeys",
            "fixtureCaseIds",
            "bootstrapRequired",
            "repositoryOutputAllowed",
            "networkRequired",
            "externalServiceCalls",
            "operationalCredentials",
            "authority",
            "claimBoundary",
        },
        "profile",
    )
    if profile["schema"] != PROFILE_SCHEMA or profile["profileId"] != PROFILE_ID or profile["joinName"] != JOIN_NAME:
        fail("PROFILE_IDENTITY_INVALID", "profile identity differs from JOIN-v2")
    if profile["status"] != "candidate_contract_only":
        fail("PROFILE_STATUS_INVALID", "profile status must remain candidate_contract_only")
    if profile["owningProject"] != "Estate" or profile["repository"] != "BigBirdReturns/ai-execution-audit":
        fail("PROFILE_SCOPE_INVALID", "profile owner or repository differs")
    if profile["sourceBindings"] != EXPECTED_PUBLIC_SOURCES:
        fail("PROFILE_SOURCE_BINDINGS_INVALID", "profile sourceBindings differ from the exact admitted source graph")
    if profile["sourceDigests"] != EXPECTED_SOURCE_DIGESTS:
        fail("PROFILE_SOURCE_DIGESTS_INVALID", "profile sourceDigests differ from the exact admitted digest census")
    if profile["objectSchemas"] != list(OBJECT_SCHEMAS):
        fail("OBJECT_SCHEMA_DENOMINATOR_INVALID", "profile objectSchemas denominator differs")
    if profile["terminalStates"] != list(TERMINALS):
        fail("TERMINAL_DENOMINATOR_INVALID", "profile terminalStates denominator differs")
    if profile["evidenceTiers"] != list(EVIDENCE_TIERS):
        fail("EVIDENCE_TIER_DENOMINATOR_INVALID", "profile evidenceTiers denominator differs")
    if profile["privateEvidenceProvenanceTrustRoot"] != PRIVATE_EVIDENCE_PROVENANCE_TRUST_ROOT:
        fail("PRIVATE_EVIDENCE_PROVENANCE_TRUST_ROOT_INVALID", "profile provenance trust root differs")
    if profile["stageSequence"] != list(STAGE_SEQUENCE):
        fail("STAGE_DENOMINATOR_INVALID", "profile stageSequence differs")
    if profile["preflightPhaseSequence"] != list(PREFLIGHT_PHASE_SEQUENCE):
        fail("PREFLIGHT_PHASE_DENOMINATOR_INVALID", "profile preflightPhaseSequence differs")
    if profile["preflightStopConditions"] != list(PREFLIGHT_STOP_CONDITIONS):
        fail("PREFLIGHT_STOP_DENOMINATOR_INVALID", "profile preflightStopConditions differs")
    if profile["preflightReceiptClasses"] != list(PREFLIGHT_RECEIPT_CLASSES):
        fail("PREFLIGHT_RECEIPT_DENOMINATOR_INVALID", "profile preflightReceiptClasses differs")
    if profile["coldSuccessorAnswerKeys"] != list(COLD_SUCCESSOR_ANSWER_KEYS):
        fail("SUCCESSOR_ANSWER_DENOMINATOR_INVALID", "profile coldSuccessorAnswerKeys differs")
    if profile["fixtureCaseIds"] != list(CASE_IDS):
        fail("FIXTURE_CASE_DENOMINATOR_INVALID", "profile fixtureCaseIds differs")
    for key, expected in (
        ("bootstrapRequired", True),
        ("repositoryOutputAllowed", False),
        ("networkRequired", False),
    ):
        if require_bool(profile[key], f"profile.{key}") is not expected:
            fail("PROFILE_BOUNDARY_INVALID", f"profile.{key} differs")
    if require_int(profile["externalServiceCalls"], "profile.externalServiceCalls") != 0:
        fail("PROFILE_BOUNDARY_INVALID", "externalServiceCalls must remain zero")
    if require_int(profile["operationalCredentials"], "profile.operationalCredentials") != 0:
        fail("PROFILE_BOUNDARY_INVALID", "operationalCredentials must remain zero")
    if profile["authority"] != "none" or profile["claimBoundary"] != CLAIM_BOUNDARY:
        fail("CLAIM_BOUNDARY_INVALID", "profile authority or claimBoundary differs")
    if sha256_bytes(canonical_json_bytes(profile)) != PROFILE_CANONICAL_SHA256:
        fail("PROFILE_CANONICAL_DIGEST_INVALID", "profile canonical digest differs")
    return profile


def validate_profile(path: Path) -> dict[str, Any]:
    return validate_profile_value(read_json(path))


def validate_preflight_reference(value: Any, label: str) -> dict[str, Any]:
    item = dict(
        require_exact_keys(
            value,
            {
                "schema",
                "receiptId",
                "digest",
                "terminal",
                "reviewCardActionCount",
                "authorizedActionCount",
                "completedAtUnixNs",
                "phaseSequence",
                "packetStageSequence",
                "stopConditions",
                "receiptClasses",
                "bodyPresent",
            },
            label,
        )
    )
    if item["schema"] != PREFLIGHT_REFERENCE_SCHEMA:
        fail("PREFLIGHT_REFERENCE_SCHEMA_INVALID", f"{label}.schema differs")
    require_string(item["receiptId"], f"{label}.receiptId", CONTENT_ID)
    require_string(item["digest"], f"{label}.digest", SHA256_REF)
    terminal = require_string(item["terminal"], f"{label}.terminal")
    if terminal not in PREFLIGHT_TERMINALS:
        fail("PREFLIGHT_TERMINAL_INVALID", f"{label}.terminal is outside the closed preflight denominator")
    require_int(item["reviewCardActionCount"], f"{label}.reviewCardActionCount", 0, 64)
    require_int(item["authorizedActionCount"], f"{label}.authorizedActionCount", 0, 64)
    require_int(item["completedAtUnixNs"], f"{label}.completedAtUnixNs", 1)
    require_string_list(item["phaseSequence"], f"{label}.phaseSequence", maximum=32)
    require_string_list(item["packetStageSequence"], f"{label}.packetStageSequence", maximum=32)
    require_string_list(item["stopConditions"], f"{label}.stopConditions", maximum=32)
    require_string_list(item["receiptClasses"], f"{label}.receiptClasses", maximum=64)
    if require_bool(item["bodyPresent"], f"{label}.bodyPresent"):
        fail("PRIVATE_BODY_FORBIDDEN", f"{label} carries a body")
    assert_content_id(item, "receiptId", "axmheadpreflightdisposition1", "PREFLIGHT_REFERENCE_ID_INVALID")
    return item


def validate_source_binding(value: Any, label: str = "sourceBinding") -> dict[str, Any]:
    item = dict(
        require_exact_keys(
            value,
            {"schema", "sourceBindingId", "profileId", "publicSources", "preflightDisposition"},
            label,
        )
    )
    if item["schema"] != SOURCE_BINDING_SCHEMA or item["profileId"] != PROFILE_ID:
        fail("SOURCE_BINDING_IDENTITY_INVALID", f"{label} identity differs")
    require_string(item["sourceBindingId"], f"{label}.sourceBindingId", CONTENT_ID)
    if item["publicSources"] != EXPECTED_PUBLIC_SOURCES:
        fail("SOURCE_BINDING_COORDINATES_INVALID", f"{label}.publicSources differs from exact admitted coordinates")
    if item["preflightDisposition"] is not None:
        validate_preflight_reference(item["preflightDisposition"], f"{label}.preflightDisposition")
    assert_content_id(item, "sourceBindingId", "axmheadphysicalflightsourcebinding2", "SOURCE_BINDING_CONTENT_ID_INVALID")
    return item


def validate_common_attestation(
    value: Any,
    label: str,
    *,
    schema: str,
    id_key: str,
    id_prefix: str,
    extra_keys: Iterable[str],
) -> dict[str, Any]:
    common = {
        "schema",
        id_key,
        "profileId",
        "evidenceTier",
        "issueNumber",
        "campaignId",
        "observedAtUnixNs",
        "authorizationReceiptId",
        "privateEvidenceBodyCount",
        "publicEvidenceBodyCount",
        "bodyPresent",
    }
    item = dict(require_exact_keys(value, common | set(extra_keys), label))
    if item["schema"] != schema or item["profileId"] != PROFILE_ID:
        fail("ATTESTATION_IDENTITY_INVALID", f"{label} identity differs")
    require_string(item[id_key], f"{label}.{id_key}", CONTENT_ID)
    tier = require_string(item["evidenceTier"], f"{label}.evidenceTier")
    if tier not in ("synthetic", "private_local_attested"):
        fail("ATTESTATION_EVIDENCE_TIER_INVALID", f"{label}.evidenceTier must be synthetic or private_local_attested")
    if require_int(item["issueNumber"], f"{label}.issueNumber", 1) != 37:
        fail("ISSUE_37_BINDING_MISMATCH", f"{label}.issueNumber differs")
    require_string(item["campaignId"], f"{label}.campaignId", BOUNDED_ID)
    require_int(item["observedAtUnixNs"], f"{label}.observedAtUnixNs", 1)
    require_string(item["authorizationReceiptId"], f"{label}.authorizationReceiptId", CONTENT_ID)
    require_int(item["privateEvidenceBodyCount"], f"{label}.privateEvidenceBodyCount", 1, 1_000_000)
    if require_int(item["publicEvidenceBodyCount"], f"{label}.publicEvidenceBodyCount", 0, 0) != 0:
        fail("PUBLIC_EVIDENCE_BODY_COUNT_INVALID", f"{label}.publicEvidenceBodyCount must be zero")
    if require_bool(item["bodyPresent"], f"{label}.bodyPresent"):
        fail("PRIVATE_BODY_FORBIDDEN", f"{label} carries a private body")
    assert_content_id(item, id_key, id_prefix, "ATTESTATION_CONTENT_ID_INVALID")
    return item


def validate_route(value: Any, label: str, *, optional_expected: bool) -> dict[str, Any]:
    route = dict(
        require_exact_keys(
            value,
            {
                "routeId",
                "routeClass",
                "hostClass",
                "memoryBytes",
                "outputSha256",
                "semanticIdentity",
                "classificationIdentity",
                "throughputUnits",
                "independentVerificationStatus",
                "optional",
            },
            label,
        )
    )
    require_string(route["routeId"], f"{label}.routeId", BOUNDED_ID)
    require_string(route["routeClass"], f"{label}.routeClass", HOST_CLASS)
    require_string(route["hostClass"], f"{label}.hostClass", HOST_CLASS)
    require_int(route["memoryBytes"], f"{label}.memoryBytes", 1)
    require_string(route["outputSha256"], f"{label}.outputSha256", HEX64)
    require_string(route["semanticIdentity"], f"{label}.semanticIdentity", BOUNDED_ID)
    require_string(route["classificationIdentity"], f"{label}.classificationIdentity", BOUNDED_ID)
    require_int(route["throughputUnits"], f"{label}.throughputUnits", 1)
    require_string(route["independentVerificationStatus"], f"{label}.independentVerificationStatus")
    optional = require_bool(route["optional"], f"{label}.optional")
    if optional is not optional_expected:
        fail("ROUTE_OPTIONALITY_INVALID", f"{label}.optional differs")
    return route


def validate_route_attestation(value: Any, label: str = "routeAttestation") -> dict[str, Any]:
    item = validate_common_attestation(
        value,
        label,
        schema=ROUTE_ATTESTATION_SCHEMA,
        id_key="routeAttestationId",
        id_prefix="axmheadphysicalrouteattestation2",
        extra_keys={
            "cartridgeId",
            "missionStateDigest",
            "residentRoute",
            "acceleratorRoute",
            "memoryPoolingAllowed",
            "requiredMemoryBytes",
        },
    )
    require_string(item["cartridgeId"], f"{label}.cartridgeId", BOUNDED_ID)
    require_string(item["missionStateDigest"], f"{label}.missionStateDigest", HEX64)
    validate_route(item["residentRoute"], f"{label}.residentRoute", optional_expected=False)
    validate_route(item["acceleratorRoute"], f"{label}.acceleratorRoute", optional_expected=True)
    require_bool(item["memoryPoolingAllowed"], f"{label}.memoryPoolingAllowed")
    require_int(item["requiredMemoryBytes"], f"{label}.requiredMemoryBytes", 1)
    return item


def validate_continuity_attestation(value: Any, label: str = "continuityAttestation") -> dict[str, Any]:
    item = validate_common_attestation(
        value,
        label,
        schema=CONTINUITY_ATTESTATION_SCHEMA,
        id_key="continuityAttestationId",
        id_prefix="axmheadcontinuityattestation2",
        extra_keys={
            "cartridgeId",
            "baselineOutputSha256",
            "acceleratedOutputSha256",
            "postRemovalOutputSha256",
            "baselineMissionStateDigest",
            "postRemovalMissionStateDigest",
            "acceleratorRemoved",
            "residentFloorAvailableAfterRemoval",
            "latticeRemoved",
            "localContinuityVerified",
            "independentVerificationStatus",
        },
    )
    require_string(item["cartridgeId"], f"{label}.cartridgeId", BOUNDED_ID)
    for key in (
        "baselineOutputSha256",
        "acceleratedOutputSha256",
        "postRemovalOutputSha256",
        "baselineMissionStateDigest",
        "postRemovalMissionStateDigest",
    ):
        require_string(item[key], f"{label}.{key}", HEX64)
    for key in (
        "acceleratorRemoved",
        "residentFloorAvailableAfterRemoval",
        "latticeRemoved",
        "localContinuityVerified",
    ):
        require_bool(item[key], f"{label}.{key}")
    require_string(item["independentVerificationStatus"], f"{label}.independentVerificationStatus")
    return item


def validate_cell(value: Any, label: str) -> dict[str, Any]:
    cell = dict(require_exact_keys(value, {"cellId", "hostClass", "stateDigest", "branchId", "verificationStatus"}, label))
    require_string(cell["cellId"], f"{label}.cellId", BOUNDED_ID)
    require_string(cell["hostClass"], f"{label}.hostClass", HOST_CLASS)
    require_string(cell["stateDigest"], f"{label}.stateDigest", HEX64)
    require_string(cell["branchId"], f"{label}.branchId", BOUNDED_ID)
    require_string(cell["verificationStatus"], f"{label}.verificationStatus")
    return cell


def validate_two_cell_attestation(value: Any, label: str = "twoCellAttestation") -> dict[str, Any]:
    item = validate_common_attestation(
        value,
        label,
        schema=TWO_CELL_ATTESTATION_SCHEMA,
        id_key="twoCellAttestationId",
        id_prefix="axmheadtwocellattestation2",
        extra_keys={"leftCell", "rightCell", "reunion"},
    )
    validate_cell(item["leftCell"], f"{label}.leftCell")
    validate_cell(item["rightCell"], f"{label}.rightCell")
    reunion = dict(
        require_exact_keys(
            item["reunion"],
            {"terminal", "automaticMergeAllowed", "retainedBranchIds", "unresolvedObligationCount"},
            f"{label}.reunion",
        )
    )
    require_string(reunion["terminal"], f"{label}.reunion.terminal")
    require_bool(reunion["automaticMergeAllowed"], f"{label}.reunion.automaticMergeAllowed")
    require_string_list(reunion["retainedBranchIds"], f"{label}.reunion.retainedBranchIds", maximum=4)
    require_int(reunion["unresolvedObligationCount"], f"{label}.reunion.unresolvedObligationCount", 0, 1_000_000)
    return item


def validate_successor_answers(value: Any, label: str) -> dict[str, str]:
    answers = dict(require_exact_keys(value, COLD_SUCCESSOR_ANSWER_KEYS, label))
    return {key: require_string(answers[key], f"{label}.{key}", maximum=1024) for key in COLD_SUCCESSOR_ANSWER_KEYS}


def validate_successor_attestation(value: Any, label: str = "successorAttestation") -> dict[str, Any]:
    item = validate_common_attestation(
        value,
        label,
        schema=SUCCESSOR_ATTESTATION_SCHEMA,
        id_key="successorAttestationId",
        id_prefix="axmheadsuccessorattestation2",
        extra_keys={
            "originalHeadClass",
            "successorHeadClass",
            "originalHostPresent",
            "repositoryHistoryPresent",
            "cartridgeId",
            "missionStateDigest",
            "evidenceRootSha256",
            "humanAuthorityReceiptId",
            "unresolvedObligationCount",
            "nextSafeAction",
            "answers",
            "verificationStatus",
        },
    )
    require_string(item["originalHeadClass"], f"{label}.originalHeadClass", HOST_CLASS)
    require_string(item["successorHeadClass"], f"{label}.successorHeadClass", HOST_CLASS)
    require_bool(item["originalHostPresent"], f"{label}.originalHostPresent")
    require_bool(item["repositoryHistoryPresent"], f"{label}.repositoryHistoryPresent")
    require_string(item["cartridgeId"], f"{label}.cartridgeId", BOUNDED_ID)
    require_string(item["missionStateDigest"], f"{label}.missionStateDigest", HEX64)
    require_string(item["evidenceRootSha256"], f"{label}.evidenceRootSha256", HEX64)
    require_string(item["humanAuthorityReceiptId"], f"{label}.humanAuthorityReceiptId", CONTENT_ID)
    require_int(item["unresolvedObligationCount"], f"{label}.unresolvedObligationCount", 0, 1_000_000)
    require_string(item["nextSafeAction"], f"{label}.nextSafeAction", maximum=1024)
    validate_successor_answers(item["answers"], f"{label}.answers")
    require_string(item["verificationStatus"], f"{label}.verificationStatus")
    return item


def validate_authorization_receipt(value: Any, label: str) -> dict[str, Any]:
    item = dict(
        require_exact_keys(
            value,
            {
                "schema",
                "receiptId",
                "digest",
                "actorRef",
                "actorClass",
                "issueNumber",
                "campaignId",
                "scope",
                "issuedAtUnixNs",
                "firstPhysicalActionUnixNs",
                "preflightReceiptId",
                "preflightTerminal",
                "preflightAuthorizedActionCount",
                "preflightCompletedAtUnixNs",
                "bodyPresent",
                "authorityClass",
            },
            label,
        )
    )
    if item["schema"] != AUTHORIZATION_SCHEMA:
        fail("AUTHORIZATION_SCHEMA_INVALID", f"{label}.schema differs")
    require_string(item["receiptId"], f"{label}.receiptId", CONTENT_ID)
    require_string(item["digest"], f"{label}.digest", SHA256_REF)
    require_string(item["actorRef"], f"{label}.actorRef", CONTENT_ID)
    actor_class = require_string(item["actorClass"], f"{label}.actorClass")
    if actor_class not in ("named_human", "preflight_card"):
        fail("AUTHORIZATION_ACTOR_CLASS_INVALID", f"{label}.actorClass is outside the closed denominator")
    if require_int(item["issueNumber"], f"{label}.issueNumber", 1) != 37:
        fail("ISSUE_37_BINDING_MISMATCH", f"{label}.issueNumber differs")
    require_string(item["campaignId"], f"{label}.campaignId", BOUNDED_ID)
    require_string(item["scope"], f"{label}.scope", BOUNDED_ID)
    require_int(item["issuedAtUnixNs"], f"{label}.issuedAtUnixNs", 1)
    require_int(item["firstPhysicalActionUnixNs"], f"{label}.firstPhysicalActionUnixNs", 1)
    require_string(item["preflightReceiptId"], f"{label}.preflightReceiptId", CONTENT_ID)
    terminal = require_string(item["preflightTerminal"], f"{label}.preflightTerminal")
    if terminal not in PREFLIGHT_TERMINALS:
        fail("PREFLIGHT_TERMINAL_INVALID", f"{label}.preflightTerminal differs")
    require_int(item["preflightAuthorizedActionCount"], f"{label}.preflightAuthorizedActionCount", 0, 64)
    require_int(item["preflightCompletedAtUnixNs"], f"{label}.preflightCompletedAtUnixNs", 1)
    if require_bool(item["bodyPresent"], f"{label}.bodyPresent"):
        fail("PRIVATE_BODY_FORBIDDEN", f"{label} carries a body")
    authority_class = require_string(item["authorityClass"], f"{label}.authorityClass")
    if authority_class not in ("bounded_operator_authorization", "none"):
        fail("AUTHORIZATION_CLASS_INVALID", f"{label}.authorityClass differs")
    assert_content_id(item, "receiptId", "stcmarynamedhumanauthorization1", "AUTHORIZATION_CONTENT_ID_INVALID")
    return item


def validate_stage_receipt(value: Any, label: str) -> dict[str, Any]:
    item = dict(
        require_exact_keys(
            value,
            {
                "schema",
                "receiptId",
                "receiptDigest",
                "stage",
                "terminal",
                "previousReceiptId",
                "observedAtUnixNs",
                "authorizationReceiptId",
                "evidenceBodyCount",
                "bodyPresent",
            },
            label,
        )
    )
    if item["schema"] != STAGE_RECEIPT_SCHEMA:
        fail("STAGE_RECEIPT_SCHEMA_INVALID", f"{label}.schema differs")
    require_string(item["receiptId"], f"{label}.receiptId", CONTENT_ID)
    require_string(item["receiptDigest"], f"{label}.receiptDigest", SHA256_REF)
    require_string(item["stage"], f"{label}.stage")
    require_string(item["terminal"], f"{label}.terminal")
    require_optional_string(item["previousReceiptId"], f"{label}.previousReceiptId", CONTENT_ID)
    require_int(item["observedAtUnixNs"], f"{label}.observedAtUnixNs", 1)
    require_string(item["authorizationReceiptId"], f"{label}.authorizationReceiptId", CONTENT_ID)
    require_int(item["evidenceBodyCount"], f"{label}.evidenceBodyCount", 1, 1_000_000)
    if require_bool(item["bodyPresent"], f"{label}.bodyPresent"):
        fail("PRIVATE_BODY_FORBIDDEN", f"{label} carries a body")
    assert_content_id(item, "receiptId", "stcmaryprivateflightstage1", "STAGE_RECEIPT_CONTENT_ID_INVALID")
    return item


def validate_packet(value: Any, label: str) -> dict[str, Any]:
    packet = dict(require_exact_keys(value, {"stageSequence", "stageReceipts"}, label))
    require_string_list(packet["stageSequence"], f"{label}.stageSequence", maximum=32)
    receipts = require_list(packet["stageReceipts"], f"{label}.stageReceipts", maximum=32)
    packet["stageReceipts"] = [validate_stage_receipt(row, f"{label}.stageReceipts[{index}]") for index, row in enumerate(receipts)]
    return packet


def validate_sealed_package(value: Any, label: str) -> dict[str, Any]:
    sealed = dict(
        require_exact_keys(
            value,
            {
                "packageDigest",
                "evidenceRootSha256",
                "detachedVerification",
                "verificationReceiptDigest",
                "publicDispositionDigest",
                "sealedAtUnixNs",
                "bodyPresent",
            },
            label,
        )
    )
    require_string(sealed["packageDigest"], f"{label}.packageDigest", SHA256_REF)
    require_string(sealed["evidenceRootSha256"], f"{label}.evidenceRootSha256", HEX64)
    status = require_string(sealed["detachedVerification"], f"{label}.detachedVerification")
    if status not in ("PASS", "FAIL"):
        fail("SEALED_VERIFICATION_STATUS_INVALID", f"{label}.detachedVerification differs")
    require_string(sealed["verificationReceiptDigest"], f"{label}.verificationReceiptDigest", SHA256_REF)
    require_string(sealed["publicDispositionDigest"], f"{label}.publicDispositionDigest", SHA256_REF)
    require_int(sealed["sealedAtUnixNs"], f"{label}.sealedAtUnixNs", 1)
    if require_bool(sealed["bodyPresent"], f"{label}.bodyPresent"):
        fail("PRIVATE_BODY_FORBIDDEN", f"{label} carries a sealed package body")
    return sealed


def validate_source_disposition(value: Any, label: str) -> dict[str, Any]:
    disposition = dict(
        require_exact_keys(
            value,
            {
                "schema",
                "digest",
                "privatePhysicalFlightCompleted",
                "selfAttestationOnly",
                "physicalEstateQualified",
                "representativeOperatorQualified",
                "fieldNetworkQualified",
                "operationalC2Qualified",
                "productionLatticeQualified",
                "missionAuthorityGranted",
                "commandAuthorityGranted",
                "targetingEngagementEffectorOrWeaponsCapability",
                "publicEvidenceBodyCount",
                "authority",
                "bodyPresent",
            },
            label,
        )
    )
    if disposition["schema"] != "stc-mary/physical-flight-public-disposition@1":
        fail("SOURCE_DISPOSITION_SCHEMA_INVALID", f"{label}.schema differs")
    require_string(disposition["digest"], f"{label}.digest", SHA256_REF)
    for key in (
        "privatePhysicalFlightCompleted",
        "selfAttestationOnly",
        "physicalEstateQualified",
        "representativeOperatorQualified",
        "fieldNetworkQualified",
        "operationalC2Qualified",
        "productionLatticeQualified",
        "missionAuthorityGranted",
        "commandAuthorityGranted",
        "targetingEngagementEffectorOrWeaponsCapability",
        "bodyPresent",
    ):
        require_bool(disposition[key], f"{label}.{key}")
    require_int(disposition["publicEvidenceBodyCount"], f"{label}.publicEvidenceBodyCount", 0, 1_000_000)
    require_string(disposition["authority"], f"{label}.authority")
    if disposition["bodyPresent"]:
        fail("PRIVATE_BODY_FORBIDDEN", f"{label} carries a public-disposition body")
    expected_digest = f"sha256:{sha256_bytes(canonical_json_bytes(body_without(disposition, 'digest')))}"
    if disposition["digest"] != expected_digest:
        fail("SOURCE_DISPOSITION_DIGEST_INVALID", f"{label}.digest differs from canonical body-free disposition bytes")
    return disposition


def validate_cartridge_binding(value: Any, label: str) -> dict[str, Any]:
    cartridge = dict(
        require_exact_keys(
            value,
            {
                "cartridgeId",
                "missionStateDigest",
                "humanAuthorityReceiptId",
                "unresolvedObligationCount",
                "nextSafeAction",
            },
            label,
        )
    )
    require_string(cartridge["cartridgeId"], f"{label}.cartridgeId", BOUNDED_ID)
    require_string(cartridge["missionStateDigest"], f"{label}.missionStateDigest", HEX64)
    require_string(cartridge["humanAuthorityReceiptId"], f"{label}.humanAuthorityReceiptId", CONTENT_ID)
    require_int(cartridge["unresolvedObligationCount"], f"{label}.unresolvedObligationCount", 0, 1_000_000)
    require_string(cartridge["nextSafeAction"], f"{label}.nextSafeAction", maximum=1024)
    return cartridge


def validate_disposition_binding(value: Any, label: str = "privateFlightDispositionBinding") -> dict[str, Any]:
    item = validate_common_attestation(
        value,
        label,
        schema=DISPOSITION_BINDING_SCHEMA,
        id_key="dispositionBindingId",
        id_prefix="axmheadprivateflightdispositionbinding2",
        extra_keys={"preflightReceiptId", "authorizationReceipt", "packet", "sealedPackage", "sourceDisposition", "cartridge"},
    )
    require_string(item["preflightReceiptId"], f"{label}.preflightReceiptId", CONTENT_ID)
    validate_authorization_receipt(item["authorizationReceipt"], f"{label}.authorizationReceipt")
    validate_packet(item["packet"], f"{label}.packet")
    validate_sealed_package(item["sealedPackage"], f"{label}.sealedPackage")
    validate_source_disposition(item["sourceDisposition"], f"{label}.sourceDisposition")
    validate_cartridge_binding(item["cartridge"], f"{label}.cartridge")
    return item


def validate_private_evidence_provenance(value: Any, label: str = "privateEvidenceProvenance") -> dict[str, Any]:
    item = dict(
        require_exact_keys(
            value,
            {"schema", "provenanceId", "profileId", "keyId", "algorithm", "payloadSha256", "signatureBase64Url"},
            label,
        )
    )
    if item["schema"] != PRIVATE_EVIDENCE_PROVENANCE_SCHEMA or item["profileId"] != PROFILE_ID:
        fail("PRIVATE_EVIDENCE_PROVENANCE_IDENTITY_INVALID", f"{label} identity differs")
    require_string(item["provenanceId"], f"{label}.provenanceId", CONTENT_ID)
    require_string(item["keyId"], f"{label}.keyId", BOUNDED_ID)
    require_string(item["algorithm"], f"{label}.algorithm", BOUNDED_ID)
    require_string(item["payloadSha256"], f"{label}.payloadSha256", HEX64)
    base64url_decode(item["signatureBase64Url"], f"{label}.signatureBase64Url")
    if item["keyId"] != PRIVATE_EVIDENCE_PROVENANCE_TRUST_ROOT["keyId"]:
        fail("PRIVATE_EVIDENCE_PROVENANCE_KEY_INVALID", f"{label}.keyId differs from the frozen trust root")
    if item["algorithm"] != PRIVATE_EVIDENCE_PROVENANCE_ALGORITHM:
        fail("PRIVATE_EVIDENCE_PROVENANCE_ALGORITHM_INVALID", f"{label}.algorithm differs")
    assert_content_id(item, "provenanceId", "axmheadprivateevidenceprovenance2", "PRIVATE_EVIDENCE_PROVENANCE_CONTENT_ID_INVALID")
    return item


def private_evidence_provenance_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    route = value.get("routeAttestation")
    continuity = value.get("continuityAttestation")
    two_cell = value.get("twoCellAttestation")
    successor = value.get("successorAttestation")
    disposition = value.get("privateFlightDispositionBinding")
    if not all(isinstance(item, Mapping) for item in (route, continuity, two_cell, successor, disposition)):
        fail("PRIVATE_EVIDENCE_PROVENANCE_DENOMINATOR_INCOMPLETE", "complete private objects are required before provenance can be derived")
    packet = disposition["packet"]
    sealed = disposition["sealedPackage"]
    return {
        "schema": PRIVATE_EVIDENCE_PROVENANCE_PAYLOAD_SCHEMA,
        "profileId": PROFILE_ID,
        "sourceBindingId": value["sourceBinding"]["sourceBindingId"],
        "issueNumber": 37,
        "campaignId": disposition["campaignId"],
        "authorizationReceiptId": disposition["authorizationReceipt"]["receiptId"],
        "routeAttestationId": route["routeAttestationId"],
        "continuityAttestationId": continuity["continuityAttestationId"],
        "twoCellAttestationId": two_cell["twoCellAttestationId"],
        "successorAttestationId": successor["successorAttestationId"],
        "dispositionBindingId": disposition["dispositionBindingId"],
        "stageReceiptIds": [row["receiptId"] for row in packet["stageReceipts"]],
        "sealedPackageDigest": sealed["packageDigest"],
        "sealedVerificationReceiptDigest": sealed["verificationReceiptDigest"],
        "publicDispositionDigest": sealed["publicDispositionDigest"],
        "evidenceTier": "private_local_attested",
    }


def validate_input_value(value: dict[str, Any]) -> dict[str, Any]:
    scan_forbidden_private_material(value)
    item = dict(
        require_exact_keys(
            value,
            {
                "schema",
                "profileId",
                "caseId",
                "sourceBinding",
                "routeAttestation",
                "continuityAttestation",
                "twoCellAttestation",
                "successorAttestation",
                "privateFlightDispositionBinding",
                "privateEvidenceProvenance",
            },
            "input",
        )
    )
    if item["schema"] != INPUT_SCHEMA or item["profileId"] != PROFILE_ID:
        fail("INPUT_IDENTITY_INVALID", "input identity differs")
    require_string(item["caseId"], "input.caseId", BOUNDED_ID)
    validate_source_binding(item["sourceBinding"])
    if item["routeAttestation"] is not None:
        validate_route_attestation(item["routeAttestation"])
    if item["continuityAttestation"] is not None:
        validate_continuity_attestation(item["continuityAttestation"])
    if item["twoCellAttestation"] is not None:
        validate_two_cell_attestation(item["twoCellAttestation"])
    if item["successorAttestation"] is not None:
        validate_successor_attestation(item["successorAttestation"])
    if item["privateFlightDispositionBinding"] is not None:
        validate_disposition_binding(item["privateFlightDispositionBinding"])
    if item["privateEvidenceProvenance"] is not None:
        validate_private_evidence_provenance(item["privateEvidenceProvenance"])
    return item


def validate_input(path: Path) -> dict[str, Any]:
    return validate_input_value(read_json(path))


def expected_successor_answers(
    *,
    cartridge_id: str,
    mission_state_digest: str,
    authorization_receipt_id: str,
    evidence_root_sha256: str,
    unresolved_obligation_count: int,
    next_safe_action: str,
) -> dict[str, str]:
    noun = "obligation" if unresolved_obligation_count == 1 else "obligations"
    return {
        "whatMission": f"Continue cartridge {cartridge_id} under issue #37.",
        "currentState": f"Canonical state {mission_state_digest}; reunion terminal HUMAN_REQUIRED.",
        "whoMayAct": f"Named-human authorization receipt {authorization_receipt_id} only.",
        "whatProvesIt": f"Detached sealed evidence root sha256:{evidence_root_sha256} with PASS verification.",
        "whatRemainsUnresolved": f"{unresolved_obligation_count} unresolved reconciliation {noun}.",
        "nextSafeAction": next_safe_action,
    }


def add_reason(reasons: list[str], code: str, condition: bool) -> None:
    if condition and code not in reasons:
        reasons.append(code)


def complete_private_objects(value: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]] | None:
    keys = (
        "routeAttestation",
        "continuityAttestation",
        "twoCellAttestation",
        "successorAttestation",
        "privateFlightDispositionBinding",
    )
    present = [value[key] is not None for key in keys]
    if not any(present):
        return None
    if not all(present):
        return None
    return tuple(value[key] for key in keys)  # type: ignore[return-value]


def derive_predicates(value: dict[str, Any]) -> tuple[OrderedDict[str, bool], list[str], dict[str, Any]]:
    source = value["sourceBinding"]
    preflight = source["preflightDisposition"]
    predicates: OrderedDict[str, bool] = OrderedDict()
    reasons: list[str] = []
    context: dict[str, Any] = {
        "evidenceTier": "none",
        "privateEvidenceBodyCount": 0,
        "publicEvidenceBodyCount": 0,
        "unresolvedObligationCount": 0,
        "residentThroughputUnits": 0,
        "acceleratorThroughputUnits": 0,
        "residentRouteClass": None,
        "acceleratorRouteClass": None,
        "hostClassesDistinct": False,
        "headClassesDistinct": False,
        "authorizationReceiptId": None,
        "cartridgeId": None,
        "missionStateDigest": None,
        "privateEvidenceProvenanceAuthenticated": False,
        "privateEvidenceProvenanceKeyId": None,
        "privateEvidenceProvenancePayloadSha256": None,
    }

    predicates["publicSourceCoordinatesExact"] = source["publicSources"] == EXPECTED_PUBLIC_SOURCES
    add_reason(reasons, "PUBLIC_SOURCE_COORDINATES_MISMATCH", not predicates["publicSourceCoordinatesExact"])

    predicates["preflightReferencePresent"] = preflight is not None
    if preflight is None:
        add_reason(reasons, "PREFLIGHT_DISPOSITION_ABSENT", True)
    else:
        predicates["preflightTerminalReadyForHumanReview"] = preflight["terminal"] == "READY_FOR_HUMAN_REVIEW"
        predicates["preflightReviewCardActionDenominatorExact"] = preflight["reviewCardActionCount"] == 12
        predicates["preflightAuthorizedActionCountZero"] = preflight["authorizedActionCount"] == 0
        predicates["preflightPhaseSequenceExact"] = preflight["phaseSequence"] == list(PREFLIGHT_PHASE_SEQUENCE)
        predicates["preflightPacketStageDenominatorExact"] = preflight["packetStageSequence"] == list(STAGE_SEQUENCE)
        predicates["preflightStopConditionDenominatorExact"] = preflight["stopConditions"] == list(PREFLIGHT_STOP_CONDITIONS)
        predicates["preflightReceiptClassDenominatorExact"] = preflight["receiptClasses"] == list(PREFLIGHT_RECEIPT_CLASSES)
        add_reason(reasons, "PREFLIGHT_NOT_READY_FOR_HUMAN_REVIEW", not predicates["preflightTerminalReadyForHumanReview"])
        add_reason(reasons, "PREFLIGHT_ACTION_DENOMINATOR_MISMATCH", not predicates["preflightReviewCardActionDenominatorExact"])
        add_reason(reasons, "PREFLIGHT_AUTHORIZED_ACTION_PRESENT", not predicates["preflightAuthorizedActionCountZero"])
        add_reason(reasons, "PREFLIGHT_PHASE_DENOMINATOR_MISMATCH", not predicates["preflightPhaseSequenceExact"])
        add_reason(reasons, "PREFLIGHT_STAGE_DENOMINATOR_MISMATCH", not predicates["preflightPacketStageDenominatorExact"])
        add_reason(reasons, "PREFLIGHT_STOP_DENOMINATOR_MISMATCH", not predicates["preflightStopConditionDenominatorExact"])
        add_reason(reasons, "PREFLIGHT_RECEIPT_DENOMINATOR_MISMATCH", not predicates["preflightReceiptClassDenominatorExact"])

    private_keys = (
        "routeAttestation",
        "continuityAttestation",
        "twoCellAttestation",
        "successorAttestation",
        "privateFlightDispositionBinding",
    )
    present = [value[key] is not None for key in private_keys]
    predicates["privateReceiptDenominatorAbsent"] = not any(present)
    predicates["privateReceiptDenominatorComplete"] = all(present)
    add_reason(reasons, "PRIVATE_RECEIPT_DENOMINATOR_INCOMPLETE", any(present) and not all(present))

    if not all(present):
        return predicates, reasons, context

    route = value["routeAttestation"]
    continuity = value["continuityAttestation"]
    two_cell = value["twoCellAttestation"]
    successor = value["successorAttestation"]
    disposition = value["privateFlightDispositionBinding"]
    authorization = disposition["authorizationReceipt"]
    packet = disposition["packet"]
    sealed = disposition["sealedPackage"]
    source_disposition = disposition["sourceDisposition"]
    cartridge = disposition["cartridge"]

    tiers = [route["evidenceTier"], continuity["evidenceTier"], two_cell["evidenceTier"], successor["evidenceTier"], disposition["evidenceTier"]]
    campaigns = [route["campaignId"], continuity["campaignId"], two_cell["campaignId"], successor["campaignId"], disposition["campaignId"], authorization["campaignId"]]
    auth_refs = [route["authorizationReceiptId"], continuity["authorizationReceiptId"], two_cell["authorizationReceiptId"], successor["authorizationReceiptId"], disposition["authorizationReceiptId"]]
    observed_times = [route["observedAtUnixNs"], continuity["observedAtUnixNs"], two_cell["observedAtUnixNs"], successor["observedAtUnixNs"], disposition["observedAtUnixNs"]]

    predicates["evidenceTierUniform"] = len(set(tiers)) == 1
    predicates["campaignIdentityUniform"] = (
        len(set(campaigns)) == 1 and campaigns[0] == EXPECTED_CAMPAIGN_ID
    )
    predicates["authorizationReferenceUniform"] = len(set(auth_refs + [authorization["receiptId"]])) == 1
    predicates["issueBindingExact"] = all(obj["issueNumber"] == 37 for obj in (route, continuity, two_cell, successor, disposition)) and authorization["issueNumber"] == 37
    add_reason(reasons, "EVIDENCE_TIER_MISMATCH", not predicates["evidenceTierUniform"])
    add_reason(reasons, "CAMPAIGN_IDENTITY_MISMATCH", not predicates["campaignIdentityUniform"])
    add_reason(reasons, "AUTHORIZATION_REFERENCE_MISMATCH", not predicates["authorizationReferenceUniform"])
    add_reason(reasons, "ISSUE_37_BINDING_MISMATCH", not predicates["issueBindingExact"])

    tier = tiers[0] if predicates["evidenceTierUniform"] else "none"
    context["evidenceTier"] = tier
    context["authorizationReceiptId"] = authorization["receiptId"]
    context["cartridgeId"] = cartridge["cartridgeId"]
    context["missionStateDigest"] = cartridge["missionStateDigest"]

    provenance = value["privateEvidenceProvenance"]
    if tier == "private_local_attested":
        predicates["privateEvidenceProvenancePresent"] = provenance is not None
        payload = private_evidence_provenance_payload(value)
        payload_bytes = canonical_json_bytes(payload)
        payload_sha256 = sha256_bytes(payload_bytes)
        predicates["privateEvidenceProvenancePayloadExact"] = provenance is not None and provenance["payloadSha256"] == payload_sha256
        signature_valid = False
        if provenance is not None and predicates["privateEvidenceProvenancePayloadExact"]:
            signature = base64url_decode(provenance["signatureBase64Url"], "privateEvidenceProvenance.signatureBase64Url")
            signature_valid = verify_rsa_pkcs1_v1_5_sha256(payload_bytes, signature, PRIVATE_EVIDENCE_PROVENANCE_TRUST_ROOT)
        predicates["privateEvidenceProvenanceAuthenticated"] = signature_valid
        add_reason(reasons, "PRIVATE_EVIDENCE_PROVENANCE_REQUIRED", provenance is None)
        add_reason(reasons, "PRIVATE_EVIDENCE_PROVENANCE_PAYLOAD_MISMATCH", provenance is not None and not predicates["privateEvidenceProvenancePayloadExact"] )
        add_reason(reasons, "PRIVATE_EVIDENCE_PROVENANCE_AUTHENTICATION_FAILED", provenance is not None and predicates["privateEvidenceProvenancePayloadExact"] and not signature_valid)
        context["privateEvidenceProvenanceAuthenticated"] = signature_valid
        if provenance is not None:
            context["privateEvidenceProvenanceKeyId"] = provenance["keyId"]
            context["privateEvidenceProvenancePayloadSha256"] = provenance["payloadSha256"]
    else:
        predicates["privateEvidenceProvenanceAbsentOutsidePrivateTier"] = provenance is None
        add_reason(reasons, "PRIVATE_EVIDENCE_PROVENANCE_UNEXPECTED", provenance is not None)

    predicates["preflightReferenceCrossBound"] = preflight is not None and disposition["preflightReceiptId"] == preflight["receiptId"] and authorization["preflightReceiptId"] == preflight["receiptId"]
    predicates["authorizationReceiptDistinctFromPreflight"] = preflight is not None and authorization["receiptId"] != preflight["receiptId"]
    predicates["namedHumanAuthorizationDistinct"] = authorization["actorClass"] == "named_human" and authorization["authorityClass"] == "bounded_operator_authorization"
    predicates["preflightNotPromotedToAuthorization"] = authorization["actorClass"] != "preflight_card"
    preflight_actor_identities = (
        set()
        if preflight is None
        else {preflight["receiptId"], source["sourceBindingId"]}
    )
    predicates["authorizationScopeCoversCampaign"] = (
        authorization["campaignId"] == EXPECTED_CAMPAIGN_ID
        and authorization["scope"] == EXPECTED_AUTHORIZATION_SCOPE
    )
    predicates["namedHumanActorDistinctFromPreflight"] = (
        preflight is not None
        and authorization["actorRef"] not in preflight_actor_identities
    )
    predicates["authorizationPreflightCompletionCrossBound"] = (
        preflight is not None
        and authorization["preflightCompletedAtUnixNs"] == preflight["completedAtUnixNs"]
    )
    predicates["authorizationIssuedAfterPreflightCompletion"] = (
        preflight is not None
        and authorization["issuedAtUnixNs"] > preflight["completedAtUnixNs"]
    )
    predicates["authorizationFollowsCompletedPreflight"] = (
        preflight is not None
        and authorization["preflightTerminal"] == "READY_FOR_HUMAN_REVIEW"
        and authorization["preflightAuthorizedActionCount"] == 0
        and predicates["authorizationPreflightCompletionCrossBound"]
        and predicates["authorizationIssuedAfterPreflightCompletion"]
        and authorization["issuedAtUnixNs"] < authorization["firstPhysicalActionUnixNs"]
    )
    predicates["physicalObservationsFollowAuthorization"] = all(time >= authorization["firstPhysicalActionUnixNs"] for time in observed_times)
    add_reason(reasons, "PREFLIGHT_REFERENCE_MISMATCH", not predicates["preflightReferenceCrossBound"])
    add_reason(reasons, "AUTHORIZATION_RECEIPT_NOT_DISTINCT", not predicates["authorizationReceiptDistinctFromPreflight"])
    add_reason(reasons, "NAMED_HUMAN_AUTHORIZATION_REQUIRED", not predicates["namedHumanAuthorizationDistinct"])
    add_reason(reasons, "PREFLIGHT_CARD_CANNOT_AUTHORIZE", not predicates["preflightNotPromotedToAuthorization"])
    add_reason(reasons, "AUTHORIZATION_SCOPE_MISMATCH", not predicates["authorizationScopeCoversCampaign"])
    add_reason(reasons, "PREFLIGHT_IDENTITY_CANNOT_BE_HUMAN_ACTOR", not predicates["namedHumanActorDistinctFromPreflight"])
    add_reason(reasons, "PREFLIGHT_COMPLETION_REFERENCE_MISMATCH", not predicates["authorizationPreflightCompletionCrossBound"])
    add_reason(reasons, "AUTHORIZATION_BEFORE_PREFLIGHT_COMPLETION", not predicates["authorizationIssuedAfterPreflightCompletion"])
    add_reason(reasons, "AUTHORIZATION_BOUNDARY_INVALID", not predicates["authorizationFollowsCompletedPreflight"])
    add_reason(reasons, "PHYSICAL_ACTION_BEFORE_AUTHORIZATION", not predicates["physicalObservationsFollowAuthorization"])

    resident = route["residentRoute"]
    accelerator = route["acceleratorRoute"]
    predicates["routeIdentitiesDistinct"] = resident["routeId"] != accelerator["routeId"]
    predicates["routeMemoryEvaluatedIndependently"] = route["memoryPoolingAllowed"] is False and resident["memoryBytes"] > 0 and accelerator["memoryBytes"] > 0
    predicates["eachRouteMemorySufficient"] = resident["memoryBytes"] >= route["requiredMemoryBytes"] and accelerator["memoryBytes"] >= route["requiredMemoryBytes"]
    predicates["residentBaselineIndependentlyVerified"] = resident["independentVerificationStatus"] == "PASS"
    predicates["acceleratorIndependentlyVerified"] = accelerator["independentVerificationStatus"] == "PASS"
    predicates["acceleratorPreservesAcceptedOutput"] = accelerator["outputSha256"] == resident["outputSha256"]
    predicates["acceleratorPreservesSemanticIdentity"] = accelerator["semanticIdentity"] == resident["semanticIdentity"]
    predicates["acceleratorPreservesClassificationIdentity"] = accelerator["classificationIdentity"] == resident["classificationIdentity"]
    predicates["acceleratorOutperformsResident"] = accelerator["throughputUnits"] > resident["throughputUnits"]
    add_reason(reasons, "ROUTE_IDENTITIES_NOT_DISTINCT", not predicates["routeIdentitiesDistinct"])
    add_reason(reasons, "ROUTE_MEMORY_POOLING_FORBIDDEN", not predicates["routeMemoryEvaluatedIndependently"])
    add_reason(reasons, "INDIVIDUAL_ROUTE_MEMORY_INSUFFICIENT", not predicates["eachRouteMemorySufficient"])
    add_reason(reasons, "RESIDENT_BASELINE_NOT_VERIFIED", not predicates["residentBaselineIndependentlyVerified"])
    add_reason(reasons, "ACCELERATOR_NOT_VERIFIED", not predicates["acceleratorIndependentlyVerified"])
    add_reason(reasons, "ACCELERATOR_OUTPUT_MISMATCH", not predicates["acceleratorPreservesAcceptedOutput"])
    add_reason(reasons, "ACCELERATOR_SEMANTIC_MISMATCH", not predicates["acceleratorPreservesSemanticIdentity"])
    add_reason(reasons, "ACCELERATOR_CLASSIFICATION_MISMATCH", not predicates["acceleratorPreservesClassificationIdentity"])
    add_reason(reasons, "ACCELERATOR_NOT_FASTER", not predicates["acceleratorOutperformsResident"])

    context["residentThroughputUnits"] = resident["throughputUnits"]
    context["acceleratorThroughputUnits"] = accelerator["throughputUnits"]
    context["residentRouteClass"] = resident["routeClass"]
    context["acceleratorRouteClass"] = accelerator["routeClass"]

    predicates["routeCartridgeCrossBound"] = route["cartridgeId"] == continuity["cartridgeId"] == successor["cartridgeId"] == cartridge["cartridgeId"]
    predicates["canonicalMissionStateUnchanged"] = (
        route["missionStateDigest"]
        == continuity["baselineMissionStateDigest"]
        == continuity["postRemovalMissionStateDigest"]
        == successor["missionStateDigest"]
        == cartridge["missionStateDigest"]
    )
    predicates["continuityOutputsCrossBound"] = (
        continuity["baselineOutputSha256"] == resident["outputSha256"]
        and continuity["acceleratedOutputSha256"] == accelerator["outputSha256"]
        and continuity["postRemovalOutputSha256"] == resident["outputSha256"]
    )
    predicates["postRemovalResidentContinuityVerified"] = (
        continuity["acceleratorRemoved"] is True
        and continuity["residentFloorAvailableAfterRemoval"] is True
        and continuity["independentVerificationStatus"] == "PASS"
    )
    predicates["latticeUnnecessaryForLocalContinuity"] = continuity["latticeRemoved"] is True and continuity["localContinuityVerified"] is True
    add_reason(reasons, "CARTRIDGE_BINDING_MISMATCH", not predicates["routeCartridgeCrossBound"])
    add_reason(reasons, "CANONICAL_MISSION_STATE_CHANGED", not predicates["canonicalMissionStateUnchanged"])
    add_reason(reasons, "CONTINUITY_OUTPUT_MISMATCH", not predicates["continuityOutputsCrossBound"])
    add_reason(reasons, "POST_REMOVAL_CONTINUITY_NOT_VERIFIED", not predicates["postRemovalResidentContinuityVerified"])
    add_reason(reasons, "LATTICE_REQUIRED_FOR_LOCAL_CONTINUITY", not predicates["latticeUnnecessaryForLocalContinuity"])

    left = two_cell["leftCell"]
    right = two_cell["rightCell"]
    reunion = two_cell["reunion"]
    predicates["twoCellHostClassesDistinct"] = left["hostClass"] != right["hostClass"]
    predicates["twoCellIdentitiesDistinct"] = left["cellId"] != right["cellId"]
    predicates["twoCellBranchesDistinct"] = left["branchId"] != right["branchId"]
    predicates["twoCellStatesIndependentlyVerified"] = left["verificationStatus"] == "PASS" and right["verificationStatus"] == "PASS"
    predicates["reunionTerminalHumanRequired"] = reunion["terminal"] == "HUMAN_REQUIRED"
    predicates["automaticReunionMergeForbidden"] = reunion["automaticMergeAllowed"] is False
    predicates["bothBranchesRetained"] = set(reunion["retainedBranchIds"]) == {left["branchId"], right["branchId"]} and len(reunion["retainedBranchIds"]) == 2
    predicates["unresolvedReconciliationObligationRetained"] = reunion["unresolvedObligationCount"] > 0
    add_reason(reasons, "TWO_CELL_HOST_CLASSES_NOT_DISTINCT", not predicates["twoCellHostClassesDistinct"])
    add_reason(reasons, "TWO_CELL_IDENTITIES_NOT_DISTINCT", not predicates["twoCellIdentitiesDistinct"])
    add_reason(reasons, "TWO_CELL_BRANCHES_NOT_DISTINCT", not predicates["twoCellBranchesDistinct"])
    add_reason(reasons, "TWO_CELL_VERIFICATION_FAILED", not predicates["twoCellStatesIndependentlyVerified"])
    add_reason(reasons, "REUNION_NOT_HUMAN_REQUIRED", not predicates["reunionTerminalHumanRequired"])
    add_reason(reasons, "AUTOMATIC_REUNION_MERGE_FORBIDDEN", not predicates["automaticReunionMergeForbidden"])
    add_reason(reasons, "REUNION_BRANCH_CUSTODY_MISMATCH", not predicates["bothBranchesRetained"])
    add_reason(reasons, "UNRESOLVED_OBLIGATION_REQUIRED", not predicates["unresolvedReconciliationObligationRetained"])
    context["hostClassesDistinct"] = predicates["twoCellHostClassesDistinct"]
    context["unresolvedObligationCount"] = reunion["unresolvedObligationCount"]

    expected_answers = expected_successor_answers(
        cartridge_id=cartridge["cartridgeId"],
        mission_state_digest=cartridge["missionStateDigest"],
        authorization_receipt_id=authorization["receiptId"],
        evidence_root_sha256=sealed["evidenceRootSha256"],
        unresolved_obligation_count=cartridge["unresolvedObligationCount"],
        next_safe_action=cartridge["nextSafeAction"],
    )
    predicates["replacementHeadClassDistinct"] = successor["originalHeadClass"] != successor["successorHeadClass"]
    predicates["successorAbsentDependenciesPreserved"] = successor["originalHostPresent"] is False and successor["repositoryHistoryPresent"] is False
    predicates["successorBindingsExact"] = (
        successor["cartridgeId"] == cartridge["cartridgeId"]
        and successor["missionStateDigest"] == cartridge["missionStateDigest"]
        and successor["evidenceRootSha256"] == sealed["evidenceRootSha256"]
        and successor["humanAuthorityReceiptId"] == authorization["receiptId"] == cartridge["humanAuthorityReceiptId"]
        and successor["unresolvedObligationCount"] == cartridge["unresolvedObligationCount"] == reunion["unresolvedObligationCount"]
        and successor["nextSafeAction"] == cartridge["nextSafeAction"]
    )
    predicates["coldSuccessorAnswersReconstructed"] = successor["answers"] == expected_answers
    predicates["successorIndependentlyVerified"] = successor["verificationStatus"] == "PASS"
    add_reason(reasons, "REPLACEMENT_HEAD_CLASS_NOT_DISTINCT", not predicates["replacementHeadClassDistinct"])
    add_reason(reasons, "SUCCESSOR_DEPENDENCY_WIDENED", not predicates["successorAbsentDependenciesPreserved"])
    add_reason(reasons, "SUCCESSOR_BINDING_MISMATCH", not predicates["successorBindingsExact"])
    add_reason(reasons, "COLD_SUCCESSOR_ANSWERS_MISMATCH", not predicates["coldSuccessorAnswersReconstructed"])
    add_reason(reasons, "SUCCESSOR_VERIFICATION_FAILED", not predicates["successorIndependentlyVerified"])
    context["headClassesDistinct"] = predicates["replacementHeadClassDistinct"]

    stage_sequence = packet["stageSequence"]
    receipts = packet["stageReceipts"]
    predicates["stageSequenceExact"] = stage_sequence == list(STAGE_SEQUENCE)
    predicates["stageReceiptCountExact"] = len(receipts) == len(STAGE_SEQUENCE)
    predicates["stageReceiptStagesExact"] = len(receipts) == len(STAGE_SEQUENCE) and [row["stage"] for row in receipts] == list(STAGE_SEQUENCE)
    predicates["stageReceiptIdsUnique"] = len({row["receiptId"] for row in receipts}) == len(receipts)
    predicates["stageTerminalsExact"] = len(receipts) == len(STAGE_SEQUENCE) and all(row["terminal"] == EXPECTED_STAGE_TERMINALS[stage] for row, stage in zip(receipts, STAGE_SEQUENCE))
    chain_valid = len(receipts) == len(STAGE_SEQUENCE)
    timestamps_valid = chain_valid
    auth_valid = chain_valid
    evidence_valid = chain_valid
    previous: str | None = None
    last_time = authorization["firstPhysicalActionUnixNs"]
    if chain_valid:
        for row in receipts:
            if row["previousReceiptId"] != previous:
                chain_valid = False
            if row["observedAtUnixNs"] < last_time:
                timestamps_valid = False
            if row["authorizationReceiptId"] != authorization["receiptId"]:
                auth_valid = False
            if row["evidenceBodyCount"] <= 0:
                evidence_valid = False
            previous = row["receiptId"]
            last_time = row["observedAtUnixNs"]
    predicates["stagePredecessorChainComplete"] = chain_valid
    predicates["stageTimestampsFollowAuthorization"] = timestamps_valid
    predicates["stageAuthorizationCrossBound"] = auth_valid
    predicates["eachStageHasPrivateEvidence"] = evidence_valid
    add_reason(reasons, "STAGE_SEQUENCE_MISMATCH", not predicates["stageSequenceExact"])
    add_reason(reasons, "STAGE_RECEIPT_COUNT_MISMATCH", not predicates["stageReceiptCountExact"])
    add_reason(reasons, "STAGE_RECEIPT_ORDER_MISMATCH", not predicates["stageReceiptStagesExact"])
    add_reason(reasons, "STAGE_RECEIPT_ID_DUPLICATE", not predicates["stageReceiptIdsUnique"])
    add_reason(reasons, "STAGE_TERMINAL_MISMATCH", not predicates["stageTerminalsExact"])
    add_reason(reasons, "STAGE_PREDECESSOR_CHAIN_BROKEN", not predicates["stagePredecessorChainComplete"])
    add_reason(reasons, "STAGE_TIMESTAMP_BEFORE_AUTHORIZATION", not predicates["stageTimestampsFollowAuthorization"])
    add_reason(reasons, "STAGE_AUTHORIZATION_MISMATCH", not predicates["stageAuthorizationCrossBound"])
    add_reason(reasons, "STAGE_PRIVATE_EVIDENCE_REQUIRED", not predicates["eachStageHasPrivateEvidence"])

    predicates["sealedPackageDetachedVerificationPass"] = sealed["detachedVerification"] == "PASS"
    predicates["sealedPackageFollowsStages"] = bool(receipts) and sealed["sealedAtUnixNs"] >= max(row["observedAtUnixNs"] for row in receipts)
    expected_public_digest = f"sha256:{sha256_bytes(canonical_json_bytes(source_disposition))}"
    predicates["sealedPublicDispositionDigestExact"] = sealed["publicDispositionDigest"] == expected_public_digest
    predicates["publicEvidenceBodyCountZero"] = source_disposition["publicEvidenceBodyCount"] == 0 and all(obj["publicEvidenceBodyCount"] == 0 for obj in (route, continuity, two_cell, successor, disposition))
    predicates["privateEvidenceBodyCountPositive"] = (
        sum(obj["privateEvidenceBodyCount"] for obj in (route, continuity, two_cell, successor, disposition))
        + sum(row["evidenceBodyCount"] for row in receipts)
    ) > 0
    predicates["sourceDispositionClaimsSelfAttestationOnly"] = source_disposition["privatePhysicalFlightCompleted"] is True and source_disposition["selfAttestationOnly"] is True
    predicates["strongerQualificationsRemainFalse"] = all(
        source_disposition[key] is False
        for key in (
            "physicalEstateQualified",
            "representativeOperatorQualified",
            "fieldNetworkQualified",
            "operationalC2Qualified",
            "productionLatticeQualified",
            "missionAuthorityGranted",
            "commandAuthorityGranted",
            "targetingEngagementEffectorOrWeaponsCapability",
        )
    )
    predicates["systemAuthorityRemainsNone"] = source_disposition["authority"] == "none"
    add_reason(reasons, "SEALED_PACKAGE_VERIFICATION_FAILED", not predicates["sealedPackageDetachedVerificationPass"])
    add_reason(reasons, "SEALED_PACKAGE_TIMESTAMP_INVALID", not predicates["sealedPackageFollowsStages"])
    add_reason(reasons, "SEALED_PUBLIC_DISPOSITION_DIGEST_MISMATCH", not predicates["sealedPublicDispositionDigestExact"])
    add_reason(reasons, "PUBLIC_EVIDENCE_BODY_COUNT_NONZERO", not predicates["publicEvidenceBodyCountZero"])
    add_reason(reasons, "PRIVATE_EVIDENCE_BODY_COUNT_ZERO", not predicates["privateEvidenceBodyCountPositive"])
    add_reason(reasons, "PRIVATE_FLIGHT_DISPOSITION_INVALID", not predicates["sourceDispositionClaimsSelfAttestationOnly"])
    add_reason(reasons, "STRONGER_QUALIFICATION_PROMOTED", not predicates["strongerQualificationsRemainFalse"])
    add_reason(reasons, "AUTHORITY_PROMOTED", not predicates["systemAuthorityRemainsNone"])

    context["privateEvidenceBodyCount"] = (
        sum(obj["privateEvidenceBodyCount"] for obj in (route, continuity, two_cell, successor, disposition))
        + sum(row["evidenceBodyCount"] for row in receipts)
    )
    context["publicEvidenceBodyCount"] = source_disposition["publicEvidenceBodyCount"]

    return predicates, reasons, context


def determine_terminal(value: dict[str, Any], predicates: Mapping[str, bool], reasons: list[str], context: dict[str, Any]) -> tuple[str, list[str]]:
    present = [
        value["routeAttestation"] is not None,
        value["continuityAttestation"] is not None,
        value["twoCellAttestation"] is not None,
        value["successorAttestation"] is not None,
        value["privateFlightDispositionBinding"] is not None,
    ]
    if not any(present):
        prepared_reasons = [code for code in reasons if code.startswith("PREFLIGHT_") or code.startswith("PUBLIC_SOURCE_")]
        if value["sourceBinding"]["preflightDisposition"] is not None and not prepared_reasons:
            return "PREPARED_NOT_ARMED", ["PRIVATE_RECEIPT_DENOMINATOR_ABSENT"]
        return "HOLD", prepared_reasons or ["PREFLIGHT_DISPOSITION_ABSENT"]
    if not all(present):
        return "HOLD", reasons or ["PRIVATE_RECEIPT_DENOMINATOR_INCOMPLETE"]

    all_predicates = all(value for key, value in predicates.items() if key != "privateReceiptDenominatorAbsent")
    tier = context["evidenceTier"]
    if all_predicates and tier == "private_local_attested" and context["privateEvidenceProvenanceAuthenticated"]:
        return "PRIVATE_SELF_ATTESTED", []
    if all_predicates and tier == "synthetic":
        return "HOLD", ["SYNTHETIC_EVIDENCE_CANNOT_ATTEST"]
    if tier == "synthetic" and "SYNTHETIC_EVIDENCE_CANNOT_ATTEST" not in reasons:
        reasons = list(reasons) + ["SYNTHETIC_EVIDENCE_CANNOT_ATTEST"]
    return "HOLD", reasons or ["PRIVATE_RECEIPT_DENOMINATOR_NOT_ACCEPTED"]


def source_summary(source_binding: dict[str, Any]) -> dict[str, Any]:
    preflight = source_binding["preflightDisposition"]
    return {
        "axmSupplierCommit": EXPECTED_PUBLIC_SOURCES["admittedAxmHeadSupplier"]["commit"],
        "axmSupplierTree": EXPECTED_PUBLIC_SOURCES["admittedAxmHeadSupplier"]["tree"],
        "conductorCommit": EXPECTED_PUBLIC_SOURCES["admittedConductor"]["commit"],
        "conductorTree": EXPECTED_PUBLIC_SOURCES["admittedConductor"]["tree"],
        "conductorArchiveSha256": EXPECTED_PUBLIC_SOURCES["admittedConductor"]["archiveSha256"],
        "conductorPredecessorCommits": EXPECTED_PUBLIC_SOURCES["admittedConductor"]["predecessorCommits"],
        "physicalFlightFloorCommit": EXPECTED_PUBLIC_SOURCES["physicalFlightFloor"]["commit"],
        "physicalFlightFloorTree": EXPECTED_PUBLIC_SOURCES["physicalFlightFloor"]["tree"],
        "preflightCommit": EXPECTED_PUBLIC_SOURCES["admittedPreflightReviewCard"]["commit"],
        "preflightTree": EXPECTED_PUBLIC_SOURCES["admittedPreflightReviewCard"]["tree"],
        "preflightReceiptId": None if preflight is None else preflight["receiptId"],
        "physicalFlightIssueNumber": 37,
    }


def make_join_object(value: dict[str, Any], predicates: Mapping[str, bool], reasons: list[str], context: dict[str, Any], terminal: str) -> dict[str, Any]:
    private_completed = terminal == "PRIVATE_SELF_ATTESTED"
    body = {
        "schema": JOIN_SCHEMA,
        "profileId": PROFILE_ID,
        "sourceBindingId": value["sourceBinding"]["sourceBindingId"],
        "routeAttestationId": None if value["routeAttestation"] is None else value["routeAttestation"]["routeAttestationId"],
        "continuityAttestationId": None if value["continuityAttestation"] is None else value["continuityAttestation"]["continuityAttestationId"],
        "twoCellAttestationId": None if value["twoCellAttestation"] is None else value["twoCellAttestation"]["twoCellAttestationId"],
        "successorAttestationId": None if value["successorAttestation"] is None else value["successorAttestation"]["successorAttestationId"],
        "dispositionBindingId": None if value["privateFlightDispositionBinding"] is None else value["privateFlightDispositionBinding"]["dispositionBindingId"],
        "terminal": terminal,
        "reasonCodes": reasons,
        "derivedPredicates": dict(predicates),
        "privateEvidenceBodyCount": context["privateEvidenceBodyCount"],
        "publicEvidenceBodyCount": context["publicEvidenceBodyCount"],
        "unresolvedObligationCount": context["unresolvedObligationCount"],
        "privatePhysicalFlightCompleted": private_completed,
        "selfAttestationOnly": private_completed,
        "physicalEstateQualified": False,
        "representativeOperatorQualified": False,
        "fieldNetworkQualified": False,
        "operationalC2Qualified": False,
        "productionLatticeQualified": False,
        "missionAuthorityGranted": False,
        "commandAuthorityGranted": False,
        "targetingEngagementEffectorOrWeaponsCapability": False,
        "authority": "none",
    }
    return {"joinObjectId": content_id("axmheadphysicallonghauljoin2", body), **body}


def make_verification_object(join: dict[str, Any], predicates: Mapping[str, bool], context: dict[str, Any]) -> dict[str, Any]:
    body = {
        "schema": VERIFICATION_SCHEMA,
        "profileId": PROFILE_ID,
        "joinObjectId": join["joinObjectId"],
        "status": "PASS",
        "terminal": join["terminal"],
        "checkedPredicateCount": len(predicates),
        "satisfiedPredicateCount": sum(1 for value in predicates.values() if value),
        "sourceBindingsReconstructed": True,
        "preflightBoundaryReconstructed": True,
        "authorizationBoundaryReconstructed": True,
        "stageDenominatorReconstructed": True,
        "routeSemanticsReconstructed": True,
        "continuityPredicatesReconstructed": True,
        "twoCellCustodyReconstructed": True,
        "successorAnswersReconstructed": True,
        "sealedPackagePredicateReconstructed": True,
        "publicDispositionReconstructed": True,
        "standaloneVerifierSha256": current_verifier_sha256(),
        "bootstrapRequired": True,
        "privateShapeComplete": all(value for key, value in predicates.items() if key != "privateReceiptDenominatorAbsent"),
        "evidenceTier": context["evidenceTier"],
        "privateEvidenceProvenanceAuthenticated": context["privateEvidenceProvenanceAuthenticated"],
        "privateEvidenceProvenanceKeyId": context["privateEvidenceProvenanceKeyId"],
        "authority": "none",
    }
    return {"verificationId": content_id("axmheadphysicallonghaulverification2", body), **body}


def make_public_status_object(value: dict[str, Any], join: dict[str, Any], verification: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    body = {
        "schema": PUBLIC_STATUS_SCHEMA,
        "profileId": PROFILE_ID,
        "joinObjectId": join["joinObjectId"],
        "verificationId": verification["verificationId"],
        "terminal": join["terminal"],
        "reasonCodes": join["reasonCodes"],
        "sources": source_summary(value["sourceBinding"]),
        "evidenceTier": context["evidenceTier"],
        "privateEvidenceProvenanceAuthenticated": context["privateEvidenceProvenanceAuthenticated"],
        "privateEvidenceProvenanceKeyId": context["privateEvidenceProvenanceKeyId"],
        "privateEvidenceProvenancePayloadSha256": context["privateEvidenceProvenancePayloadSha256"],
        "authorizationReceiptId": context["authorizationReceiptId"],
        "cartridgeId": context["cartridgeId"],
        "missionStateDigest": context["missionStateDigest"],
        "residentRouteClass": context["residentRouteClass"],
        "acceleratorRouteClass": context["acceleratorRouteClass"],
        "residentThroughputUnits": context["residentThroughputUnits"],
        "acceleratorThroughputUnits": context["acceleratorThroughputUnits"],
        "twoCellHostClassesDistinct": context["hostClassesDistinct"],
        "replacementHeadClassDistinct": context["headClassesDistinct"],
        "unresolvedObligationCount": context["unresolvedObligationCount"],
        "privateEvidenceBodyCount": context["privateEvidenceBodyCount"],
        "publicEvidenceBodyCount": 0,
        "privatePhysicalFlightCompleted": join["privatePhysicalFlightCompleted"],
        "selfAttestationOnly": join["selfAttestationOnly"],
        "physicalEstateQualified": False,
        "representativeOperatorQualified": False,
        "fieldNetworkQualified": False,
        "operationalC2Qualified": False,
        "productionLatticeQualified": False,
        "missionAuthorityGranted": False,
        "commandAuthorityGranted": False,
        "targetingEngagementEffectorOrWeaponsCapability": False,
        "workersLaunched": 0,
        "listenersCreated": 0,
        "missionVolumeMaterialized": False,
        "issue37AdvancedByVerification": False,
        "authority": "none",
        "claimBoundary": CLAIM_BOUNDARY,
    }
    public = {"publicStatusId": content_id("axmheadphysicallonghaulpublicstatus2", body), **body}
    scan_forbidden_private_material(public, "publicStatus")
    return public


def evaluate_input(profile: dict[str, Any], value: dict[str, Any]) -> dict[str, Any]:
    validate_profile_value(profile)
    validate_input_value(value)
    predicates, reasons, context = derive_predicates(value)
    terminal, final_reasons = determine_terminal(value, predicates, reasons, context)
    join = make_join_object(value, predicates, final_reasons, context, terminal)
    verification = make_verification_object(join, predicates, context)
    public = make_public_status_object(value, join, verification, context)
    envelope = {
        "schema": ENVELOPE_SCHEMA,
        "status": "PASS",
        "bootstrapAuthenticated": False,
        "profileCanonicalSha256": PROFILE_CANONICAL_SHA256,
        "standaloneVerifierSha256": current_verifier_sha256(),
        "join": join,
        "verification": verification,
        "publicStatus": public,
    }
    scan_forbidden_private_material(envelope, "envelope")
    return envelope



def validate_catalog_value(catalog: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    validate_profile_value(profile)
    require_exact_keys(catalog, {"schema", "profileId", "cases"}, "fixtureCatalog")
    if catalog["schema"] != FIXTURE_CATALOG_SCHEMA or catalog["profileId"] != PROFILE_ID:
        fail("FIXTURE_CATALOG_IDENTITY_INVALID", "fixture catalog identity differs")
    rows = require_list(catalog["cases"], "fixtureCatalog.cases", maximum=64)
    if len(rows) != len(CASE_IDS):
        fail("FIXTURE_CASE_DENOMINATOR_INVALID", "fixture case count differs")
    observed_ids: list[str] = []
    for index, row in enumerate(rows):
        case = dict(require_exact_keys(row, {"caseId", "expectedTerminal", "expectedReasonCodes", "input"}, f"fixtureCatalog.cases[{index}]"))
        case_id = require_string(case["caseId"], f"fixtureCatalog.cases[{index}].caseId", BOUNDED_ID)
        observed_ids.append(case_id)
        terminal = require_string(case["expectedTerminal"], f"fixtureCatalog.cases[{index}].expectedTerminal")
        if terminal not in TERMINALS or terminal == "PRIVATE_SELF_ATTESTED":
            fail("SYNTHETIC_FIXTURE_TERMINAL_INVALID", f"{case_id} may not claim PRIVATE_SELF_ATTESTED")
        expected_reasons = require_string_list(case["expectedReasonCodes"], f"fixtureCatalog.cases[{index}].expectedReasonCodes", maximum=64)
        input_value = validate_input_value(case["input"])
        if input_value["privateEvidenceProvenance"] is not None:
            fail("SYNTHETIC_FIXTURE_PROVENANCE_FORBIDDEN", f"{case_id} may not carry authenticated private provenance")
        for key in (
            "routeAttestation",
            "continuityAttestation",
            "twoCellAttestation",
            "successorAttestation",
            "privateFlightDispositionBinding",
        ):
            if input_value[key] is not None and input_value[key]["evidenceTier"] == "private_local_attested":
                fail("PRIVATE_FIXTURE_FORBIDDEN", f"{case_id} contains private_local_attested fixture evidence")
        result = evaluate_input(profile, input_value)
        if result["join"]["terminal"] != terminal or result["join"]["reasonCodes"] != expected_reasons:
            fail("FIXTURE_EXPECTATION_MISMATCH", f"{case_id} expected terminal or reasons differ")
        if result["publicStatus"]["privatePhysicalFlightCompleted"] is not False:
            fail("SYNTHETIC_FIXTURE_PHYSICAL_CLAIM", f"{case_id} promoted a physical completion claim")
    if observed_ids != list(CASE_IDS):
        fail("FIXTURE_CASE_DENOMINATOR_INVALID", "fixture case identities or ordering differ")
    if sha256_bytes(canonical_json_bytes(catalog)) != FIXTURE_CATALOG_CANONICAL_SHA256:
        fail("FIXTURE_CATALOG_CANONICAL_DIGEST_INVALID", "fixture catalog canonical digest differs")
    return catalog


def validate_catalog(path: Path, profile: dict[str, Any]) -> dict[str, Any]:
    return validate_catalog_value(read_json(path), profile)


def find_case(catalog: dict[str, Any], case_id: str) -> dict[str, Any]:
    for row in catalog["cases"]:
        if row["caseId"] == case_id:
            return row
    fail("FIXTURE_CASE_NOT_FOUND", f"unknown fixture case: {case_id}")


def refused_envelope(exc: JoinError) -> dict[str, Any]:
    return {
        "schema": ENVELOPE_SCHEMA,
        "status": "REFUSED",
        "bootstrapAuthenticated": False,
        "code": exc.code,
        "message": str(exc),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify one AXM HEAD physical long-haul postflight join input")
    parser.add_argument("profile", type=Path)
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        profile = validate_profile(args.profile)
        value = validate_input(args.input)
        result = evaluate_input(profile, value)
        sys.stdout.buffer.write(canonical_json_bytes(result))
        return 0
    except JoinError as exc:
        sys.stdout.buffer.write(canonical_json_bytes(refused_envelope(exc)))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
