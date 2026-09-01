"""Bridge the admitted evidence denominator to the bodies a successor packet will carry.

The admitted packet-evidence-admission@2 gate decides that forty-three exact evidence
bodies are admissible for packet recording, publishes a per-stage evidence-admission root
over them, and then deliberately stops. It places nothing in the packet. Nothing in the
transaction previously connected the roles it admitted to the files a stage record hashes,
so a packet could carry any non-empty bodies at all and still copy the gate's roots into
its stage records. A sealed packet could then name a forty-three-role denominator over a
completely unrelated set of files, and every downstream verification would agree with
itself.

This verifier closes that gap. It consumes the objects the gate itself identified --

    the bootstrap-authenticated ADMISSIBLE_FOR_PACKET_RECORDING receipt
    the ADMISSION-REQUEST.json the receipt names by requestId
    the candidate evidence workspace the request's body paths resolve inside
    the successor packet the roles are destined for
    the admitted @2 profile, read through the successor profile's canonical-digest pin

-- and independently replays the candidate-body mapping. For every admitted role it
re-measures the candidate body, recomputes the body's own content identity, recomputes
each stage evidence-admission root and non-human root exactly as the gate computes them,
recomputes the complete admission digest root, and requires all of it to equal what the
receipt published. It then names one deterministic packet coordinate per role.

It never imports the construction law, the runtime, the orchestrator or the gate. A defect
in any of those cannot authenticate the mapping this receipt asserts.

After the complete denominator verifies, transaction mode promotes only an exact,
recoverable prefix into the packet and emits its completion receipt only at 43 / 43. It
records no stage, authenticates no human principal, admits no evidence of its own, and
grants no authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

PROFILE_SCHEMA = "stc-mary/successor-packet-flight-profile/1"
PROFILE_ID = "stc-mary/successor-packet-flight-01@1"
ADMISSION_PROFILE_SCHEMA = "stc-mary/packet-evidence-admission-profile/1"

AUTHORITY = "none"
MINIMUM_PYTHON = (3, 12)

CONTENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*_[0-9a-f]{64}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
RELATIVE_MEMBER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,255}$")

MAX_JSON_BYTES = 64 * 1024 * 1024
MAX_EVIDENCE_BYTES = 64 * 1024 * 1024

# The bootstrap adds three annotations and flips the gate's own bootstrapAuthenticated
# from false to true. The gate signed its body while that flag was still false.
BOOTSTRAP_ANNOTATIONS = ("bootstrapSchema", "bootstrapVerifier", "bootstrapVerifierSha256")
BOOTSTRAP_FLAG = "bootstrapAuthenticated"

HUMAN = "named_human_statement"
RECEIPT = "accepted_predecessor_receipt"
CURRENT = "current_local_observation"

# The two scopes the admitted gate computes a stage root under. They are reproduced here
# because this verifier must recompute the gate's roots byte for byte; they are not a new
# contract, and a drift in either one is a refusal rather than a reinterpretation.
ALL_ROLES_SCOPE = "all-admitted-evidence-roles"
NON_HUMAN_SCOPE = "non-human-evidence-roles"


class MaterializationError(RuntimeError):
    """One coded, bounded refusal. It carries no private coordinate."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def fail(code: str, message: str) -> None:
    raise MaterializationError(code, message)


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        fail(code, message)


def require_supported_python() -> None:
    require(
        sys.version_info[:2] >= MINIMUM_PYTHON,
        "PYTHON_RUNTIME_UNSUPPORTED",
        f"this verifier requires Python {MINIMUM_PYTHON[0]}.{MINIMUM_PYTHON[1]} or newer",
    )


def canonical_json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        fail("NON_CANONICAL_JSON", str(exc))
        raise


def canonical_json_bytes(value: Any) -> bytes:
    return (canonical_json(value) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def content_id(prefix: str, value: Any) -> str:
    return f"{prefix}_{sha256_bytes(canonical_json(value).encode('utf-8'))}"


def assert_identity(value: Mapping[str, Any], id_key: str, prefix: str, code: str, label: str) -> str:
    observed = value.get(id_key)
    require(isinstance(observed, str), code, f"{label} {id_key} is missing")
    body = {key: item for key, item in value.items() if key != id_key}
    require(observed == content_id(prefix, body), code, f"{label} {id_key} differs from its content identity")
    return observed


def exact_keys(value: Any, expected: Iterable[str], code: str, label: str) -> Mapping[str, Any]:
    require(isinstance(value, Mapping), code, f"{label} must be an object")
    require(set(value.keys()) == set(expected), code, f"{label} field denominator differs")
    return value


def assert_content_id(value: Any, code: str, label: str) -> str:
    require(
        isinstance(value, str) and CONTENT_ID_RE.fullmatch(value) is not None,
        code,
        f"{label} is not a content identity",
    )
    return value


def assert_sha256(value: Any, code: str, label: str) -> str:
    require(
        isinstance(value, str) and SHA256_RE.fullmatch(value) is not None,
        code,
        f"{label} is not a lowercase SHA-256 digest",
    )
    return value


def assert_relative_member(value: Any, code: str, label: str) -> str:
    require(
        isinstance(value, str) and "\\" not in value and RELATIVE_MEMBER_RE.fullmatch(value) is not None,
        code,
        f"{label} is not a bounded POSIX-relative coordinate",
    )
    return value


def coordinate_component_is_link(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        if os.name == "nt" and path.exists():
            try:
                return bool(path.lstat().st_file_attributes & 0x400)
            except (OSError, AttributeError):
                return False
        return False
    except OSError:
        return False


def validate_lexical_coordinate(path: Path, *, label: str, code: str) -> Path:
    if any(part == os.pardir for part in path.parts):
        fail(code, f"{label} may not contain a parent-directory segment")
    absolute = Path(os.path.abspath(os.fspath(path.expanduser())))
    current = Path(absolute.parts[0])
    if coordinate_component_is_link(current):
        fail(code, f"{label} contains a symlink or junction component")
    for part in absolute.parts[1:]:
        current = current / part
        if coordinate_component_is_link(current):
            fail(code, f"{label} contains a symlink or junction component")
    return absolute


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def read_bounded_bytes(path: Path, maximum: int, *, code: str, label: str) -> bytes:
    if coordinate_component_is_link(path):
        fail(code, f"{label} is a symlink or junction")
    try:
        stat = path.stat()
    except OSError as exc:
        fail(code, f"{label} could not be inspected: {exc}")
        raise
    require(path.is_file(), code, f"{label} is not a regular file")
    require(stat.st_size <= maximum, code, f"{label} exceeds the bounded read allocation")
    with path.open("rb") as handle:
        data = handle.read(maximum + 1)
    require(len(data) <= maximum, code, f"{label} changed during the bounded read")
    return data


def parse_json_bytes(data: bytes, *, code: str, label: str) -> Mapping[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(code, f"{label} is not valid UTF-8 JSON: {exc}")
        raise
    require(isinstance(value, Mapping), code, f"{label} must be a JSON object")
    return value


def read_json_file(path: Path, *, code: str, label: str) -> Mapping[str, Any]:
    return parse_json_bytes(
        read_bounded_bytes(path, MAX_JSON_BYTES, code=code, label=label), code=code, label=label
    )


def load_profiles(profile_path: Path, repository: Path) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    profile = read_json_file(profile_path, code="PROFILE_UNREADABLE", label="successor flight profile")
    require(profile.get("schema") == PROFILE_SCHEMA, "PROFILE_INVALID", "successor flight profile schema differs")
    require(profile.get("profileId") == PROFILE_ID, "PROFILE_INVALID", "successor flight profile identity differs")
    require(profile.get("authority") == AUTHORITY, "AUTHORITY_WIDENED", "successor flight profile grants authority")
    law = profile["admissionProfile"]
    admission = read_json_file(
        repository / law["relativePath"], code="ADMISSION_PROFILE_UNREADABLE", label="admission profile"
    )
    require(
        admission.get("schema") == ADMISSION_PROFILE_SCHEMA,
        "ADMISSION_PROFILE_INVALID",
        "admission profile schema differs",
    )
    require(
        admission.get("profileId") == law["profileId"],
        "ADMISSION_PROFILE_INVALID",
        "admission profile identity is not the admitted profile this source is bound to",
    )
    require(
        sha256_bytes(canonical_json_bytes(admission)) == law["canonicalSha256"],
        "ADMISSION_PROFILE_CANONICAL_DIGEST_INVALID",
        "admission profile canonical digest differs from the pinned admitted digest",
    )
    return profile, admission


# --------------------------------------------------------------------------------
# deterministic packet coordinates, safe on every supported filesystem
# --------------------------------------------------------------------------------


def assert_safe_destination(destination: str, *, law: Mapping[str, Any], code: str, label: str) -> str:
    """Require one generated packet coordinate to be portable, not merely locally valid.

    The coordinate is derived from an admitted evidence role key, so the admitted profile
    decides these paths. Two admitted keys already differ only by stage, and a future role
    key could differ from an existing one only by case. That must refuse here rather than
    on the Windows hosted leg, half way through materializing a packet.
    """
    require(
        isinstance(destination, str) and 0 < len(destination) <= law["maxRelativePathLength"],
        code,
        f"{label} is empty or exceeds the bounded relative-path length",
    )
    assert_relative_member(destination, code, label)
    components = destination.split("/")
    require(bool(components), code, f"{label} has no path component")
    reserved = {name.casefold() for name in law["reservedComponents"]}
    for component in components:
        require(
            0 < len(component) <= law["maxComponentLength"],
            code,
            f"{label} component is empty or exceeds the bounded component length",
        )
        require(component not in (".", ".."), code, f"{label} contains a relative segment")
        for character in law["forbiddenCharacters"]:
            require(character not in component, code, f"{label} component contains {character!r}")
        require(
            component == component.strip(),
            code,
            f"{label} component carries leading or trailing whitespace",
        )
        require(not component.endswith("."), code, f"{label} component ends in a dot")
        # A Windows device name is reserved with or without an extension, and the check is
        # on the stem rather than the whole component for exactly that reason.
        require(
            component.split(".")[0].casefold() not in reserved,
            code,
            f"{label} component is a reserved device name",
        )
    return destination


def assert_portable_destination_set(destinations: Sequence[str], *, law: Mapping[str, Any], code: str) -> None:
    """Require the complete generated set to be unique exactly and under casefold."""
    require(
        len(set(destinations)) == len(destinations),
        code,
        "two admitted evidence roles generate one packet coordinate",
    )
    require(
        law["casefoldUniqueness"] is True,
        "PROFILE_INVALID",
        "the profile does not require case-insensitive uniqueness of packet coordinates",
    )
    folded = [destination.casefold() for destination in destinations]
    require(
        len(set(folded)) == len(folded),
        code,
        "two admitted evidence roles generate packet coordinates that collide on a "
        "case-insensitive filesystem",
    )


# --------------------------------------------------------------------------------
# the gate's own root algorithm, reproduced
# --------------------------------------------------------------------------------


def stage_evidence_root(
    admission: Mapping[str, Any], *, scope: str, sequence: int, stage: str, rows: Sequence[Mapping[str, Any]]
) -> str:
    """Recompute one stage evidence-admission root exactly as the admitted gate does.

    The six fields below, the sort key and the scope string are the gate's, not this
    verifier's. If the admitted profile ever changes them its canonical digest changes,
    the pin refuses, and this function is never reached carrying a stale algorithm.
    """
    return content_id(
        admission["digests"]["stageEvidenceRootPrefix"],
        {
            "scope": scope,
            "sequence": sequence,
            "stage": stage,
            "roles": sorted(
                (
                    {
                        "evidenceRole": row["evidenceRole"],
                        "provenanceClass": row["provenanceClass"],
                        "evidenceClass": row["evidenceClass"],
                        "bodyContentId": row["bodyContentId"],
                        "bodySha256": row["bodySha256"],
                        "bodyBytes": row["bodyBytes"],
                    }
                    for row in rows
                ),
                key=lambda row: row["evidenceRole"],
            ),
        },
    )


def admission_digest_root(admission: Mapping[str, Any], stage_rows: Sequence[Mapping[str, Any]]) -> str:
    """Recompute the complete admission digest root exactly as the admitted gate does."""
    return content_id(
        admission["digests"]["admissionRootPrefix"],
        [
            {
                "sequence": row["sequence"],
                "stage": row["stage"],
                "evidenceAdmissionRoot": row["evidenceAdmissionRoot"],
                "observationDigest": row["observationDigest"],
            }
            for row in stage_rows
        ],
    )


# --------------------------------------------------------------------------------
# the admitted receipt and the request it names
# --------------------------------------------------------------------------------


def load_admission_receipt(
    *, profile: Mapping[str, Any], path: Path, packet_id: str, campaign_id: str, canonical: str, contract_id: str
) -> Mapping[str, Any]:
    receipt_law = profile["admissionProfile"]
    codes = profile["evidenceMaterialization"]["refusalCodes"]
    receipt = read_json_file(path, code="ADMISSION_RECEIPT_INVALID", label="admission receipt")
    require(
        receipt.get("schema") == receipt_law["receiptSchema"] and receipt.get("status") == "PASS",
        "ADMISSION_RECEIPT_INVALID",
        "admission receipt schema or status differs",
    )
    require(
        receipt.get("profileId") == receipt_law["profileId"],
        "ADMISSION_RECEIPT_INVALID",
        "admission receipt was issued under another admission profile",
    )
    require(
        receipt.get("terminal") == receipt_law["requiredTerminal"],
        "ADMISSION_TERMINAL_INVALID",
        "the admission receipt does not carry ADMISSIBLE_FOR_PACKET_RECORDING",
    )
    require(
        receipt.get(BOOTSTRAP_FLAG) is True,
        "ADMISSION_RECEIPT_NOT_BOOTSTRAP_AUTHENTICATED",
        "this verifier consumes only an externally bootstrap-authenticated admission receipt",
    )
    for key in BOOTSTRAP_ANNOTATIONS:
        require(
            key in receipt,
            "ADMISSION_RECEIPT_NOT_BOOTSTRAP_AUTHENTICATED",
            f"admission receipt lacks {key}",
        )
    signed_body = {
        key: value
        for key, value in receipt.items()
        if key not in BOOTSTRAP_ANNOTATIONS and key != receipt_law["receiptIdKey"]
    }
    signed_body[BOOTSTRAP_FLAG] = False
    require(
        receipt.get(receipt_law["receiptIdKey"]) == content_id(receipt_law["receiptIdPrefix"], signed_body),
        "ADMISSION_RECEIPT_IDENTITY_INVALID",
        "the admission receipt identity does not recompute from the body the gate signed",
    )
    require(
        receipt.get("packetId") == packet_id
        and receipt.get("campaignId") == campaign_id
        and receipt.get("canonicalMissionStateDigest") == canonical
        and receipt.get("successorContractId") == contract_id,
        codes["binding"],
        "the admission receipt does not admit this packet, campaign, canonical state and contract",
    )
    require(receipt.get("authority") == AUTHORITY, "AUTHORITY_WIDENED", "admission receipt grants authority")
    return receipt


def load_request(
    *, profile: Mapping[str, Any], admission: Mapping[str, Any], candidates: Path, receipt: Mapping[str, Any]
) -> Mapping[str, Any]:
    """Read the exact admission request the receipt was issued over.

    The receipt names one requestId. Re-identifying the request on disk and requiring that
    identity is what makes this replay a measurement of the admitted transaction rather
    than of whatever happens to be sitting in the workspace now.
    """
    request_law = admission["request"]
    codes = profile["evidenceMaterialization"]["refusalCodes"]
    request = read_json_file(
        candidates / request_law["fileName"], code=codes["requestBinding"], label="admission request"
    )
    exact_keys(request, request_law["keys"], codes["requestBinding"], "admission request")
    require(
        request["schema"] == request_law["schema"],
        codes["requestBinding"],
        "admission request schema differs",
    )
    require(request["authority"] == AUTHORITY, "AUTHORITY_WIDENED", "admission request grants authority")
    request_id = assert_identity(
        request, request_law["idKey"], request_law["idPrefix"], codes["requestBinding"], "admission request"
    )
    require(
        request_id == receipt.get("requestId"),
        codes["requestBinding"],
        "the admission request on disk is not the request the admission receipt was issued over",
    )
    require(
        request["packetId"] == receipt["packetId"]
        and request["campaignId"] == receipt["campaignId"]
        and request["canonicalMissionStateDigest"] == receipt["canonicalMissionStateDigest"],
        codes["requestBinding"],
        "the admission request names another packet, campaign or canonical mission state",
    )
    return request


# --------------------------------------------------------------------------------
# one admitted role, replayed
# --------------------------------------------------------------------------------


def replay_role(
    *,
    profile: Mapping[str, Any],
    admission: Mapping[str, Any],
    descriptor: Mapping[str, Any],
    role_law: Mapping[str, Any],
    stage: str,
    sequence: int,
    candidates: Path,
    packet: Path,
    evidence_directory: str,
    campaign_id: str,
    packet_id: str,
) -> dict[str, Any]:
    """Re-measure one candidate body and derive its exact role row.

    Campaign and packet identity are carried once by the parent receipt, so each body is
    checked against them here rather than restated on every row. A body re-signed for
    another campaign or packet changes its own content identity, and this is where that
    is caught against the transaction the receipt names.
    """
    materialization_law = profile["evidenceMaterialization"]
    codes = materialization_law["refusalCodes"]
    destination_law = materialization_law["destination"]
    role = role_law["evidenceRole"]
    role_key = role_law["evidenceRoleKey"]
    provenance = role_law["provenanceClass"]
    label = f"{stage} evidence role {role_key}"

    exact_keys(descriptor, admission["descriptorKeys"], codes["invalid"], f"{label} descriptor")
    require(
        descriptor["provenanceClass"] == provenance,
        codes["bodySubstituted"],
        f"{label} descriptor names a provenance class the admitted stage role does not carry",
    )
    require(
        descriptor["evidenceClass"] in admission["evidenceClassByProvenance"][provenance],
        codes["bodySubstituted"],
        f"{label} evidence class is inconsistent with its admitted provenance class",
    )

    relative = assert_relative_member(descriptor["bodyPath"], codes["invalid"], f"{label} body path")
    body_path = validate_lexical_coordinate(candidates / relative, label=f"{label} body", code=codes["invalid"])
    require(
        is_within(body_path, candidates),
        codes["invalid"],
        f"{label} body escapes the admission workspace",
    )
    require(
        not is_within(body_path, packet),
        codes["invalid"],
        f"{label} body is staged inside the packet; the gate admits nothing into the packet",
    )
    data = read_bounded_bytes(body_path, MAX_EVIDENCE_BYTES, code=codes["bodySubstituted"], label=f"{label} body")
    require(len(data) > 0, codes["bodySubstituted"], f"{label} body is empty")
    measured_sha256 = sha256_bytes(data)
    require(
        descriptor["bodySha256"] == measured_sha256 and descriptor["bodyBytes"] == len(data),
        codes["bodySubstituted"],
        f"{label} candidate body differs from the digest and byte count the gate admitted",
    )
    assert_sha256(measured_sha256, codes["bodySubstituted"], f"{label} body digest")

    opaque_law = admission["opaqueInstrument"]
    opaque_class = descriptor["opaqueInstrumentClass"]
    instrument_receipt_id: str | None = None
    instrument_receipt_path: str | None = None
    instrument_receipt_sha256: str | None = None
    instrument_receipt_bytes: int | None = None
    instrument_receipt_destination: str | None = None
    source_receipt_id: str | None = None
    source_observation_id: str | None = None
    reuse_class: str | None = None

    if opaque_class is not None:
        # An opaque instrument body carries no parsed identity of its own, so its content
        # identity is its separately admitted instrument receipt. That receipt is evidence
        # in its own right and occupies its own packet coordinate.
        require(
            provenance == opaque_law["provenanceClass"],
            codes["bodySubstituted"],
            f"{label} offers an opaque instrument body for a provenance class that does not admit one",
        )
        require(
            opaque_class in opaque_law["admittedInstrumentClasses"],
            codes["bodySubstituted"],
            f"{label} names an instrument class outside the admitted denominator",
        )
        require(
            descriptor["bodySchema"] is None and descriptor["bodyContentId"] is None,
            codes["invalid"],
            f"{label} opaque body may not claim a parsed schema or content identity",
        )
        require(
            descriptor["mediaType"] in opaque_law["mediaTypes"],
            codes["bodySubstituted"],
            f"{label} opaque media type is not admitted",
        )
        instrument_receipt_path = assert_relative_member(
            descriptor["instrumentReceiptPath"], codes["invalid"], f"{label} instrument receipt path"
        )
        receipt_coordinate = validate_lexical_coordinate(
            candidates / instrument_receipt_path, label=f"{label} instrument receipt", code=codes["invalid"]
        )
        require(
            is_within(receipt_coordinate, candidates),
            codes["invalid"],
            f"{label} instrument receipt escapes the admission workspace",
        )
        receipt_data = read_bounded_bytes(
            receipt_coordinate, MAX_JSON_BYTES, code=codes["bodySubstituted"], label=f"{label} instrument receipt"
        )
        instrument = parse_json_bytes(
            receipt_data, code=codes["invalid"], label=f"{label} instrument receipt"
        )
        exact_keys(instrument, opaque_law["receiptKeys"], codes["invalid"], f"{label} instrument receipt")
        instrument_receipt_id = assert_identity(
            instrument,
            opaque_law["receiptIdKey"],
            opaque_law["receiptIdPrefix"],
            codes["bodyIdentityForged"],
            f"{label} instrument receipt",
        )
        require(
            instrument["instrumentClass"] == opaque_class,
            codes["bodySubstituted"],
            f"{label} instrument receipt names another instrument class",
        )
        require(
            instrument["opaqueBodySha256"] == measured_sha256 and instrument["opaqueBodyBytes"] == len(data),
            codes["bodySubstituted"],
            f"{label} instrument receipt does not bind the measured opaque body",
        )
        require(
            instrument["campaignId"] == campaign_id and instrument["packetId"] == packet_id,
            codes["bodySubstituted"],
            f"{label} instrument receipt was authenticated for another campaign or packet",
        )
        require(
            instrument["stage"] == stage and instrument["sequence"] == sequence,
            codes["bodySubstituted"],
            f"{label} instrument receipt was authenticated for another stage or sequence",
        )
        instrument_receipt_sha256 = sha256_bytes(receipt_data)
        instrument_receipt_bytes = len(receipt_data)
        body_content_id = instrument_receipt_id
        body_schema = None
        body_file = destination_law["opaqueBodyFileTemplate"].format(evidenceRoleKey=role_key)
        instrument_receipt_destination = (
            f"{evidence_directory}/"
            + destination_law["instrumentReceiptFileTemplate"].format(evidenceRoleKey=role_key)
        )
    else:
        schema_law = admission["bodySchemas"][provenance]
        require(
            descriptor["bodySchema"] == schema_law["schema"],
            codes["bodySubstituted"],
            f"{label} descriptor names an unknown or absent body schema",
        )
        require(
            descriptor["instrumentReceiptPath"] is None,
            codes["invalid"],
            f"{label} parsed body may not carry an instrument receipt path",
        )
        require(
            descriptor["mediaType"] in admission["mediaTypeByProvenance"][provenance],
            codes["bodySubstituted"],
            f"{label} media type is inconsistent with the admitted body schema",
        )
        body = parse_json_bytes(data, code=codes["bodySubstituted"], label=f"{label} body")
        exact_keys(body, schema_law["keys"], codes["bodySubstituted"], f"{label} body")
        require(
            body["schema"] == schema_law["schema"],
            codes["bodySubstituted"],
            f"{label} body schema differs from the descriptor",
        )
        body_content_id = assert_identity(
            body, schema_law["idKey"], schema_law["idPrefix"], codes["bodyIdentityForged"], f"{label} body"
        )
        require(
            descriptor["bodyContentId"] == body_content_id,
            codes["bodyIdentityForged"],
            f"{label} descriptor content identity differs from the recomputed body identity",
        )
        # The body names its own campaign, packet, role, stage and sequence. Requiring
        # them here is what stops a body admitted for one coordinate being materialized
        # under another, and it is why the row itself need not repeat the constants.
        require(
            body["campaignId"] == campaign_id and body["packetId"] == packet_id,
            codes["bodySubstituted"],
            f"{label} body was authenticated for another campaign or packet",
        )
        require(
            body["evidenceRole"] == role and body["stage"] == stage and body["sequence"] == sequence,
            codes["bodySubstituted"],
            f"{label} body was authenticated for another role, stage or sequence",
        )
        require(
            body["provenanceClass"] == provenance,
            codes["bodySubstituted"],
            f"{label} body names another provenance class than the admitted role",
        )
        body_schema = schema_law["schema"]
        if provenance == RECEIPT:
            source_receipt_id = assert_content_id(
                body["sourceReceiptId"], codes["bodySubstituted"], f"{label} source receipt identity"
            )
            reuse_class = body["reuseClass"]
            require(
                reuse_class == schema_law["requiredReuseClass"],
                codes["bodySubstituted"],
                f"{label} reused predecessor receipt carries an unadmitted reuse class",
            )
        elif provenance == CURRENT:
            source_observation_id = assert_content_id(
                body["sourceObservationId"], codes["bodySubstituted"], f"{label} source observation identity"
            )
        body_file = destination_law["bodyFileTemplate"].format(evidenceRoleKey=role_key)

    path_law = destination_law["pathSafety"]
    destination = f"{evidence_directory}/{body_file}"
    assert_safe_destination(
        destination, law=path_law, code=codes["destinationInvalid"], label=f"{label} packet destination"
    )
    if instrument_receipt_destination is not None:
        assert_safe_destination(
            instrument_receipt_destination,
            law=path_law,
            code=codes["destinationInvalid"],
            label=f"{label} instrument receipt destination",
        )

    row = {
        "sequence": sequence,
        "stage": stage,
        "evidenceRole": role,
        "evidenceRoleKey": role_key,
        "provenanceClass": provenance,
        "evidenceClass": descriptor["evidenceClass"],
        "mediaType": descriptor["mediaType"],
        "bodySchema": body_schema,
        "bodyContentId": body_content_id,
        "bodySha256": measured_sha256,
        "bodyBytes": len(data),
        "candidateBodyPath": relative,
        "packetDestination": destination,
        "opaqueInstrumentClass": opaque_class,
        "instrumentReceiptId": instrument_receipt_id,
        "instrumentReceiptPath": instrument_receipt_path,
        "instrumentReceiptSha256": instrument_receipt_sha256,
        "instrumentReceiptBytes": instrument_receipt_bytes,
        "instrumentReceiptDestination": instrument_receipt_destination,
        "sourceReceiptId": source_receipt_id,
        "sourceObservationId": source_observation_id,
        "reuseClass": reuse_class,
        # Filled once the stage's complete root has been recomputed from every role.
        "evidenceAdmissionRoot": None,
    }
    exact_keys(row, materialization_law["roleRowKeys"], codes["invalid"], f"{label} materialization row")
    return row


# --------------------------------------------------------------------------------
# the whole mapping
# --------------------------------------------------------------------------------


def materialize_evidence(
    *,
    packet: Path,
    admission_receipt: Path,
    candidates: Path,
    repository: Path,
    profile_path: Path,
    transaction_workspace: Path | None = None,
    completion_receipt: Path | None = None,
    interrupt_after_bodies: int | None = None,
    interrupt_before_completion: bool = False,
) -> dict[str, Any]:
    require_supported_python()
    packet = validate_lexical_coordinate(packet, label="packet root", code="PACKET_ROOT_INVALID")
    candidates = validate_lexical_coordinate(
        candidates, label="candidate evidence workspace", code="CANDIDATE_WORKSPACE_INVALID"
    )
    repository = validate_lexical_coordinate(repository, label="repository root", code="SOURCE_ROOT_INVALID")
    profile, admission = load_profiles(
        validate_lexical_coordinate(profile_path, label="successor flight profile", code="PROFILE_UNREADABLE"),
        repository,
    )
    materialization_law = profile["evidenceMaterialization"]
    codes = materialization_law["refusalCodes"]
    packet_law = profile["packet"]
    denominator = profile["denominator"]
    # A role row is a member of one authenticated receipt, never a portable assertion. The
    # profile declares that, and the declaration is read rather than assumed.
    require(
        materialization_law["rowClass"] == "receipt-subordinate",
        "PROFILE_INVALID",
        "the profile does not classify materialized evidence rows as receipt-subordinate",
    )

    require(
        not is_within(candidates, packet),
        codes["invalid"],
        "the candidate evidence workspace may not live inside the packet it feeds",
    )

    marker = read_json_file(
        packet / packet_law["files"]["marker"], code="PACKET_MARKER_INVALID", label="packet marker"
    )
    exact_keys(marker, packet_law["markerKeys"], "PACKET_MARKER_INVALID", "packet marker")
    assert_identity(
        marker, packet_law["markerIdKey"], packet_law["markerIdPrefix"], "PACKET_MARKER_INVALID", "packet marker"
    )
    require(
        marker["packetProfileId"] == packet_law["packetProfileId"],
        "PACKET_PROFILE_INVALID",
        "packet marker does not carry the successor packet profile",
    )
    packet_id = assert_content_id(marker["packetId"], "PACKET_MARKER_INVALID", "packet identity")

    state = read_json_file(packet / packet_law["files"]["state"], code="PACKET_STATE_INVALID", label="packet state")
    exact_keys(state, packet_law["stateKeys"], "PACKET_STATE_INVALID", "packet state")
    assert_identity(
        state, packet_law["stateIdKey"], packet_law["stateIdPrefix"], "PACKET_STATE_INVALID", "packet state"
    )
    require(
        state["packetId"] == packet_id,
        "PACKET_PROFILE_SUCCESSION_SPLIT",
        "the packet state names another packet than its marker",
    )
    require(
        state["sealed"] is False,
        "PACKET_ALREADY_SEALED",
        "a sealed packet cannot receive materialized evidence",
    )

    config = read_json_file(
        packet / packet_law["files"]["config"], code="PACKET_CONFIG_INVALID", label="packet configuration"
    )
    canonical = assert_sha256(
        config["canonicalMissionStateDigest"], "PACKET_CONFIG_INVALID", "canonical mission state digest"
    )
    contract = read_json_file(
        packet / packet_law["files"]["successorContract"],
        code="SUCCESSOR_CONTRACT_INVALID",
        label="successor contract",
    )
    contract_id = assert_identity(
        contract,
        profile["lineage"]["successorContractIdKey"],
        profile["lineage"]["successorContractIdPrefix"],
        "SUCCESSOR_CONTRACT_INVALID",
        "successor contract",
    )
    campaign_id = assert_content_id(contract["campaignId"], "SUCCESSOR_CONTRACT_INVALID", "campaign identity")

    receipt = load_admission_receipt(
        profile=profile,
        path=validate_lexical_coordinate(
            admission_receipt, label="admission receipt", code="ADMISSION_RECEIPT_INVALID"
        ),
        packet_id=packet_id,
        campaign_id=campaign_id,
        canonical=canonical,
        contract_id=contract_id,
    )
    admission_id = receipt[profile["admissionProfile"]["receiptIdKey"]]
    request = load_request(profile=profile, admission=admission, candidates=candidates, receipt=receipt)

    stages = list(admission["stageSequence"])
    require(
        len(stages) == denominator["stageDenominator"],
        codes["denominator"],
        "the admitted stage sequence is not the admitted stage denominator",
    )
    receipt_stages = {row["stage"]: row for row in receipt["stages"]}
    request_stages = {row["stage"]: row for row in request["stages"]}
    require(
        set(receipt_stages) == set(stages) and set(request_stages) == set(stages),
        codes["denominator"],
        "the admission receipt or request does not carry one row per admitted stage",
    )

    role_rows: list[dict[str, Any]] = []
    stage_rows: list[dict[str, Any]] = []
    statement_bindings: list[dict[str, Any]] = []
    seen_identities: set[str] = set()
    seen_digests: set[str] = set()
    seen_destinations: set[str] = set()
    physical_bodies = 0

    for index, stage in enumerate(stages):
        sequence = index + 1
        stage_law = admission["stages"][stage]
        state_row = state["stages"][index]
        require(
            state_row["stage"] == stage and state_row["sequence"] == sequence,
            "PACKET_STATE_INVALID",
            f"the packet state does not carry {stage} in sequence order",
        )
        evidence_directory = assert_relative_member(
            state_row["evidenceDirectory"], codes["destinationInvalid"], f"{stage} evidence directory"
        )

        stage_request = request_stages[stage]
        exact_keys(
            stage_request, admission["request"]["stageKeys"], codes["requestBinding"], f"{stage} stage request"
        )
        descriptors = stage_request["evidence"]
        require(isinstance(descriptors, list), codes["requestBinding"], f"{stage} evidence must be a list")

        admitted_role_names = {role_law["evidenceRole"] for role_law in stage_law["evidenceRoles"]}
        offered: dict[str, Mapping[str, Any]] = {}
        for descriptor in descriptors:
            require(isinstance(descriptor, Mapping), codes["invalid"], f"{stage} descriptor must be an object")
            role = descriptor.get("evidenceRole")
            require(
                role in admitted_role_names,
                codes["roleUnadmitted"],
                f"{stage} carries an evidence role outside the admitted stage denominator",
            )
            require(
                role not in offered,
                codes["roleDuplicated"],
                f"{stage} carries more than one body for evidence role {role}",
            )
            offered[role] = descriptor

        stage_role_rows: list[dict[str, Any]] = []
        for role_law in stage_law["evidenceRoles"]:
            descriptor = offered.get(role_law["evidenceRole"])
            require(
                descriptor is not None,
                codes["roleMissing"],
                f"{stage} does not carry the admitted evidence role {role_law['evidenceRoleKey']}",
            )
            row = replay_role(
                profile=profile,
                admission=admission,
                descriptor=descriptor,
                role_law=role_law,
                stage=stage,
                sequence=sequence,
                candidates=candidates,
                packet=packet,
                evidence_directory=evidence_directory,
                campaign_id=campaign_id,
                packet_id=packet_id,
            )
            require(
                row["bodyContentId"] not in seen_identities and row["bodySha256"] not in seen_digests,
                codes["bodyIdentityForged"],
                "the same evidence identity or body bytes are materialized for more than one role",
            )
            seen_identities.add(row["bodyContentId"])
            seen_digests.add(row["bodySha256"])
            for destination in (row["packetDestination"], row["instrumentReceiptDestination"]):
                if destination is None:
                    continue
                require(
                    destination not in seen_destinations,
                    codes["destinationInvalid"],
                    f"two admitted bodies claim one packet coordinate: {destination}",
                )
                seen_destinations.add(destination)
                physical_bodies += 1
            stage_role_rows.append(row)

        require(
            len(stage_role_rows) == stage_law["evidenceRoleDenominator"],
            codes["denominator"],
            f"{stage} did not materialize its admitted evidence-role denominator",
        )

        # ---- the two roots, recomputed rather than copied --------------------------
        evidence_root = stage_evidence_root(
            admission, scope=ALL_ROLES_SCOPE, sequence=sequence, stage=stage, rows=stage_role_rows
        )
        non_human_root = stage_evidence_root(
            admission,
            scope=NON_HUMAN_SCOPE,
            sequence=sequence,
            stage=stage,
            rows=[row for row in stage_role_rows if row["provenanceClass"] != HUMAN],
        )
        receipt_row = receipt_stages[stage]
        require(
            evidence_root == receipt_row["evidenceAdmissionRoot"]
            and non_human_root == receipt_row["nonHumanEvidenceAdmissionRoot"],
            codes["stageRootMismatch"],
            f"{stage} evidence-admission root recomputed from the admitted bodies differs from the "
            "root the gate published",
        )
        require(
            receipt_row["evidenceAdmissionRootFinal"] is True,
            codes["stageRootMismatch"],
            f"{stage} root was not published as final",
        )
        require(
            sorted(row["bodyContentId"] for row in stage_role_rows)
            == sorted(receipt_row["admittedEvidenceIdentities"]),
            codes["denominator"],
            f"{stage} materialized identities are not the exact identities the gate admitted",
        )
        for row in stage_role_rows:
            row["evidenceAdmissionRoot"] = evidence_root

        # ---- the exact statement bindings the receipt could not publish ------------
        for row in stage_role_rows:
            if row["provenanceClass"] != HUMAN:
                continue
            binding = {
                "sequence": sequence,
                "stage": stage,
                "evidenceRole": row["evidenceRole"],
                "statementId": row["bodyContentId"],
                "bodySha256": row["bodySha256"],
                "nonHumanEvidenceAdmissionRoot": non_human_root,
                "evidenceAdmissionRoot": evidence_root,
            }
            exact_keys(
                binding,
                materialization_law["statementBindingKeys"],
                codes["statementBinding"],
                f"{stage} statement binding",
            )
            statement_bindings.append(binding)

        stage_row = {
            "sequence": sequence,
            "stage": stage,
            "evidenceRoleDenominator": stage_law["evidenceRoleDenominator"],
            "materializedRoleCount": len(stage_role_rows),
            "physicalBodyCount": sum(
                1 if row["instrumentReceiptDestination"] is None else 2 for row in stage_role_rows
            ),
            "evidenceAdmissionRoot": evidence_root,
            "nonHumanEvidenceAdmissionRoot": non_human_root,
            "observationDigest": receipt_row["observationDigest"],
        }
        exact_keys(stage_row, materialization_law["stageRowKeys"], codes["invalid"], f"{stage} stage row")
        stage_rows.append(stage_row)
        role_rows.extend(stage_role_rows)

    # ---- the complete denominator, exactly ------------------------------------------
    human_rows = [row for row in role_rows if row["provenanceClass"] == HUMAN]
    require(
        len(role_rows) == denominator["evidenceRoleDenominator"],
        codes["denominator"],
        "the materialized role denominator is not the admitted forty-three",
    )
    require(
        len(role_rows) - len(human_rows) == denominator["nonHumanEvidenceRoleCount"]
        and len(human_rows) == denominator["humanStatementRoleCount"],
        codes["denominator"],
        "the materialized human and non-human split is not the admitted split",
    )
    require(
        len(statement_bindings) == denominator["humanStatementRoleCount"]
        and len({row["statementId"] for row in statement_bindings}) == len(statement_bindings)
        and len({row["stage"] for row in statement_bindings}) == len(statement_bindings),
        codes["statementBinding"],
        "the statement bindings are not three distinct statements on three distinct stages",
    )
    require(
        receipt["admittedEvidenceRoleCount"] == len(role_rows)
        and receipt["admittedHumanStatementCount"] == len(human_rows)
        and receipt["missingEvidenceRoleCount"] == 0,
        codes["denominator"],
        "the admission receipt admits a denominator this replay did not materialize",
    )
    require(
        physical_bodies == len(seen_destinations),
        codes["destinationInvalid"],
        "the physical body count is not the exact set of packet coordinates this receipt names",
    )
    # Uniqueness is proved over the complete generated destination set, not over the
    # admitted role keys: two admitted keys already differ only by stage.
    assert_portable_destination_set(
        sorted(seen_destinations),
        law=materialization_law["destination"]["pathSafety"],
        code=codes["destinationInvalid"],
    )

    measured_admission_root = admission_digest_root(admission, stage_rows)
    require(
        measured_admission_root == receipt["evidenceAdmissionDigestRoot"],
        codes["admissionRootMismatch"],
        "the complete admission digest root recomputed from the admitted bodies differs from the gate's",
    )

    body = {
        "schema": materialization_law["schema"],
        "status": materialization_law["requiredStatus"],
        "profileId": PROFILE_ID,
        "admissionId": admission_id,
        "admissionProfileId": profile["admissionProfile"]["profileId"],
        "requestId": receipt["requestId"],
        "packetId": packet_id,
        "campaignId": campaign_id,
        "canonicalMissionStateDigest": canonical,
        "successorContractId": contract_id,
        "evidenceRoleDenominator": denominator["evidenceRoleDenominator"],
        "materializedRoleCount": len(role_rows),
        "nonHumanEvidenceRoleCount": len(role_rows) - len(human_rows),
        "humanStatementRoleCount": len(human_rows),
        # Every one of these is a refusal above, so a receipt reaching a reader with a
        # non-zero value has been hand-written rather than measured. The consumers
        # require all three to be zero.
        "extraEvidenceRoleCount": 0,
        "missingEvidenceRoleCount": 0,
        "duplicateBodyIdentityCount": 0,
        "physicalBodyCount": physical_bodies,
        "evidenceAdmissionDigestRoot": measured_admission_root,
        "stages": stage_rows,
        "roles": role_rows,
        "statementBindings": statement_bindings,
        "authority": AUTHORITY,
        "claimBoundary": materialization_law["claimBoundary"],
    }
    signed = {**body, materialization_law["idKey"]: content_id(materialization_law["idPrefix"], body)}
    exact_keys(signed, materialization_law["keys"], codes["invalid"], "evidence materialization receipt")
    if transaction_workspace is not None:
        require(completion_receipt is not None, "MATERIALIZATION_COMPLETION_PATH_ABSENT", "transactional materialization requires a completion receipt path")
        promote_materialized_evidence(
            profile=profile,
            packet=packet,
            candidates=candidates,
            receipt=signed,
            transaction_workspace=transaction_workspace,
            completion_receipt=completion_receipt,
            interrupt_after_bodies=interrupt_after_bodies,
            interrupt_before_completion=interrupt_before_completion,
        )
    return signed


def transaction_state(
    *, profile: Mapping[str, Any], receipt: Mapping[str, Any], promoted: int, status: str
) -> dict[str, Any]:
    transaction_law = profile["evidenceMaterialization"]["transaction"]
    body = {
        "schema": transaction_law["schema"],
        "status": status,
        "packetId": receipt["packetId"],
        "materializationReceiptId": receipt[profile["evidenceMaterialization"]["idKey"]],
        "expectedPhysicalBodyCount": receipt["physicalBodyCount"],
        "promotedPhysicalBodyCount": promoted,
        "authority": AUTHORITY,
        "claimBoundary": transaction_law["claimBoundary"],
    }
    return {**body, transaction_law["idKey"]: content_id(transaction_law["idPrefix"], body)}


def write_canonical(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))


def promotion_pairs(receipt: Mapping[str, Any]) -> list[tuple[str, str, str, int]]:
    pairs: list[tuple[str, str, str, int]] = []
    for row in receipt["roles"]:
        pairs.append((row["candidateBodyPath"], row["packetDestination"], row["bodySha256"], row["bodyBytes"]))
        if row["instrumentReceiptDestination"] is not None:
            pairs.append(
                (
                    row["instrumentReceiptPath"], row["instrumentReceiptDestination"],
                    row["instrumentReceiptSha256"], row["instrumentReceiptBytes"],
                )
            )
    return sorted(pairs, key=lambda row: row[1])


def promote_materialized_evidence(
    *, profile: Mapping[str, Any], packet: Path, candidates: Path, receipt: Mapping[str, Any],
    transaction_workspace: Path, completion_receipt: Path, interrupt_after_bodies: int | None = None,
    interrupt_before_completion: bool = False,
) -> None:
    """Promote a verified exact prefix and issue completion only at the full denominator."""
    codes = profile["evidenceMaterialization"]["refusalCodes"]
    transaction_law = profile["evidenceMaterialization"]["transaction"]
    transaction_workspace = validate_lexical_coordinate(
        transaction_workspace, label="materialization transaction workspace", code="MATERIALIZATION_TRANSACTION_INVALID"
    )
    completion_receipt = validate_lexical_coordinate(
        completion_receipt, label="materialization completion receipt", code="RECEIPT_PATH_INVALID"
    )
    require(not is_within(transaction_workspace, packet), "MATERIALIZATION_TRANSACTION_INVALID", "transaction workspace may not live inside the packet")
    require(not is_within(completion_receipt, packet), "RECEIPT_INSIDE_MEASURED_SURFACE", "completion receipt may not live inside the packet")
    transaction_workspace.mkdir(parents=True, exist_ok=True)
    state_path = transaction_workspace / transaction_law["stateFile"]
    expected = promotion_pairs(receipt)
    expected_by_destination = {row[1]: row for row in expected}
    require(len(expected) == receipt["physicalBodyCount"], codes["denominator"], "physical body denominator differs")

    # Every source body was already parsed and root-checked before this function is
    # reached. Re-read all bytes once more before the first promotion so no partial packet
    # can exist beside a request that had already drifted.
    source_bytes: dict[str, bytes] = {}
    for source_relative, destination_relative, digest, size in expected:
        source = validate_lexical_coordinate(candidates / source_relative, label="candidate body", code=codes["bodySubstituted"])
        require(is_within(source, candidates), codes["bodySubstituted"], "candidate body escapes its workspace")
        data = read_bounded_bytes(source, MAX_EVIDENCE_BYTES, code=codes["bodySubstituted"], label=source_relative)
        require(sha256_bytes(data) == digest and len(data) == size, codes["bodySubstituted"], f"candidate body drifted: {source_relative}")
        source_bytes[destination_relative] = data

    present_entries: dict[str, Path] = {}
    for directory in sorted({str(Path(row[1]).parent.as_posix()) for row in expected}):
        evidence_dir = packet / directory
        require(evidence_dir.is_dir(), codes["destinationInvalid"], f"packet evidence directory is absent: {directory}")
        for entry in evidence_dir.iterdir():
            relative = entry.relative_to(packet).as_posix()
            require(entry.is_file() and relative in expected_by_destination, codes["unmaterializedEvidence"], f"unexpected packet evidence body: {relative}")
            present_entries[relative] = entry
    for relative, path in present_entries.items():
        _, _, digest, size = expected_by_destination[relative]
        data = read_bounded_bytes(path, MAX_EVIDENCE_BYTES, code=codes["bodySubstituted"], label=relative)
        require(sha256_bytes(data) == digest and len(data) == size, codes["bodySubstituted"], f"existing packet body is inconsistent: {relative}")

    if state_path.exists():
        state = read_json_file(state_path, code="MATERIALIZATION_TRANSACTION_INVALID", label="materialization transaction")
        exact_keys(state, transaction_law["keys"], "MATERIALIZATION_TRANSACTION_INVALID", "materialization transaction")
        assert_identity(state, transaction_law["idKey"], transaction_law["idPrefix"], "MATERIALIZATION_TRANSACTION_INVALID", "materialization transaction")
        require(
            state["packetId"] == receipt["packetId"]
            and state["materializationReceiptId"] == receipt[profile["evidenceMaterialization"]["idKey"]]
            and state["expectedPhysicalBodyCount"] == len(expected),
            "MATERIALIZATION_TRANSACTION_MISMATCH", "materialization transaction belongs to another receipt",
        )
        require(
            state["status"] in ("in_progress", "complete")
            and state["claimBoundary"] == transaction_law["claimBoundary"],
            "MATERIALIZATION_TRANSACTION_INVALID",
            "materialization transaction state or claim boundary differs",
        )
        require(state["promotedPhysicalBodyCount"] <= len(present_entries), "MATERIALIZATION_PREFIX_INCONSISTENT", "transaction claims bodies the packet does not hold")
    else:
        write_canonical(state_path, transaction_state(profile=profile, receipt=receipt, promoted=0, status="in_progress"))

    promoted = len(present_entries)
    for _, destination_relative, _, _ in expected:
        if destination_relative in present_entries:
            continue
        destination = validate_lexical_coordinate(packet / destination_relative, label="packet evidence body", code=codes["destinationInvalid"])
        require(is_within(destination, packet) and not destination.exists(), codes["destinationInvalid"], f"packet destination is invalid: {destination_relative}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source_bytes[destination_relative])
        promoted += 1
        write_canonical(
            state_path,
            transaction_state(profile=profile, receipt=receipt, promoted=promoted, status="in_progress"),
        )
        if interrupt_after_bodies is not None and promoted == interrupt_after_bodies:
            fail("MATERIALIZATION_INTERRUPTED", f"synthetic interruption after {promoted} promoted bodies")

    require(promoted == len(expected), "MATERIALIZATION_PREFIX_INCOMPLETE", "materialization did not reach the full denominator")
    write_canonical(state_path, transaction_state(profile=profile, receipt=receipt, promoted=promoted, status="complete"))
    if interrupt_before_completion:
        fail("MATERIALIZATION_INTERRUPTED", "synthetic interruption before completion receipt")
    data = canonical_json_bytes(receipt)
    if completion_receipt.exists():
        require(read_bounded_bytes(completion_receipt, MAX_JSON_BYTES, code=codes["invalid"], label="completion receipt") == data, "MATERIALIZATION_COMPLETION_MISMATCH", "completion receipt differs on replay")
    else:
        completion_receipt.parent.mkdir(parents=True, exist_ok=True)
        completion_receipt.write_bytes(data)


def refusal_document(code: str, message: str) -> dict[str, Any]:
    return {
        "schema": "stc-mary/successor-flight-evidence-materialization/1",
        "status": "REFUSED",
        "code": code,
        "message": message,
        "packetMutated": False,
        "packetStagesRecorded": 0,
        "authority": AUTHORITY,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay the admitted candidate-body mapping into one exact materialization receipt"
    )
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--admission-receipt", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument(
        "--profile",
        type=Path,
        default=Path(__file__).resolve().parent / "stc-mary-successor-packet-flight-01-profile-01.json",
    )
    parser.add_argument("--out", type=Path)
    parser.add_argument("--transaction-workspace", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        receipt = materialize_evidence(
            packet=args.packet,
            admission_receipt=args.admission_receipt,
            candidates=args.candidates,
            repository=args.repository_root,
            profile_path=args.profile,
            transaction_workspace=args.transaction_workspace,
            completion_receipt=args.out,
        )
        data = canonical_json_bytes(receipt)
        if args.out is None:
            require(args.transaction_workspace is None, "MATERIALIZATION_COMPLETION_PATH_ABSENT", "transaction workspace requires --out")
            sys.stdout.buffer.write(data)
        else:
            out = validate_lexical_coordinate(
                args.out, label="materialization receipt output", code="RECEIPT_PATH_INVALID"
            )
            # The profile declares that this receipt lives outside the surface it measured.
            # A declared boundary with no predicate behind it is decoration, so the flag is
            # read here rather than assumed.
            profile = read_json_file(
                validate_lexical_coordinate(
                    args.profile, label="successor flight profile", code="PROFILE_UNREADABLE"
                ),
                code="PROFILE_UNREADABLE",
                label="successor flight profile",
            )
            require(
                profile["evidenceMaterialization"]["writtenInsidePacket"] is False,
                "PROFILE_INVALID",
                "the profile permits the materialization receipt to be written inside the packet",
            )
            require(
                not is_within(out, Path(os.path.abspath(os.fspath(args.packet)))),
                "RECEIPT_INSIDE_MEASURED_SURFACE",
                "the materialization receipt may not be written inside the packet",
            )
            if args.transaction_workspace is None:
                require(not out.exists(), "RECEIPT_OUTPUT_EXISTS", "receipt output must not already exist")
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(data)
            else:
                require(out.exists() and out.read_bytes() == data, "MATERIALIZATION_COMPLETION_MISMATCH", "transaction did not promote the exact completion receipt")
        return 0
    except MaterializationError as exc:
        sys.stdout.buffer.write(canonical_json_bytes(refusal_document(exc.code, str(exc))))
        return 1
    except (OSError, ValueError, KeyError) as exc:
        sys.stdout.buffer.write(
            canonical_json_bytes(refusal_document("MATERIALIZATION_FILESYSTEM_ERROR", str(exc)))
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
