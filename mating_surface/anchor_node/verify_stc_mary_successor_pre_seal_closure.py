"""Close one 0.2 successor packet at exact sixteen of sixteen, before it is sealed.

This is the surface that decides a packet is finished recording. It is deliberately not
the surface that seals it, and it imports nothing from the source set that recorded it.

It binds, in one object:

    forty-three admitted evidence roles, re-measured in the candidate workspace and again
        in the packet, and required to be the same bytes in both
    one exact evidence-materialization receipt, re-identified and bound to the admission
        request the gate was issued over
    every stage evidence-admission root, recomputed from the bodies the packet carries
    the complete evidence-admission digest root, recomputed from those stage roots
    three authenticated named-human statement identities, bound to an exact stage and role
    sixteen authenticated stage-confirmation identities
    the final packet-stage record identity root
    the pre-seal evidence-manifest root, re-hashed from the bodies on disk and carrying
        role and provenance per body
    the retained two-branch HUMAN_REQUIRED conflict
    an unsealed packet state
    an absent sealed root
    authority none

The evidence legs matter most. A stage record that merely copied the gate's root would be
self-consistent over any files at all, so this closure replays the admitted mapping itself
-- independently of the bridge that produced the materialization receipt -- and refuses
unless packet evidence rows, materialization receipt, admission request, measured candidate
bodies and the gate's own stage roots all name one set of bodies.

Every one of those is a pre-seal fact. Nothing here asserts anything about a sealed run,
a public disposition, a sealed manifest or a detached verification: those are reserved
to the post-seal closure, which cannot run until the objects it describes exist.

It writes nothing into the packet. The closure receipt is emitted to a coordinate outside
every surface it measured, and the seal adapter consumes it from there.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

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

DENOMINATOR_INCOMPLETE = "PRE_SEAL_CLOSURE_DENOMINATOR_INCOMPLETE"

# The scope string the admitted gate computes a stage's complete role root under.
ALL_ROLES_SCOPE = "all-admitted-evidence-roles"

# The bootstrap adds three annotations and flips the gate's own bootstrapAuthenticated
# from false to true. The gate signed while it was still false.
BOOTSTRAP_ANNOTATIONS = ("bootstrapSchema", "bootstrapVerifier", "bootstrapVerifierSha256")
BOOTSTRAP_FLAG = "bootstrapAuthenticated"

class PreSealClosureError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def fail(code: str, message: str) -> None:
    raise PreSealClosureError(code, message)


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


def read_json_file(path: Path, *, code: str, label: str) -> Mapping[str, Any]:
    data = read_bounded_bytes(path, MAX_JSON_BYTES, code=code, label=label)
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(code, f"{label} is not valid UTF-8 JSON: {exc}")
        raise
    require(isinstance(value, Mapping), code, f"{label} must be a JSON object")
    return value


def require_exact_stage_evidence_directory(
    *, packet: Path, evidence_directory: str, expected_coordinates: set[str], stage: str
) -> None:
    """Close the actual stage directory, including entry names and entry types."""
    directory = validate_lexical_coordinate(
        packet / evidence_directory,
        label=f"{stage} evidence directory",
        code="PACKET_EVIDENCE_TREE_INVALID",
    )
    require(
        is_within(directory, packet) and directory.is_dir(),
        "PACKET_EVIDENCE_TREE_INVALID",
        f"{stage} evidence directory is absent or escapes the packet",
    )
    entries = list(directory.iterdir())
    observed = {f"{evidence_directory}/{entry.name}" for entry in entries}
    require(
        observed == expected_coordinates,
        "PACKET_EVIDENCE_TREE_INVALID",
        f"{stage} actual evidence entry denominator differs from the recorded materialized set",
    )
    for entry in entries:
        require(
            not coordinate_component_is_link(entry) and entry.is_file(),
            "PACKET_EVIDENCE_TREE_INVALID",
            f"{stage} evidence entry is not one regular non-link file: {entry.name}",
        )


def load_profiles(profile_path: Path, repository: Path) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    profile = read_json_file(profile_path, code="PROFILE_UNREADABLE", label="successor flight profile")
    require(profile.get("schema") == PROFILE_SCHEMA, "PROFILE_INVALID", "successor flight profile schema differs")
    require(profile.get("profileId") == PROFILE_ID, "PROFILE_INVALID", "successor flight profile identity differs")
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
        sha256_bytes(canonical_json_bytes(admission)) == law["canonicalSha256"],
        "ADMISSION_PROFILE_CANONICAL_DIGEST_INVALID",
        "admission profile canonical digest differs from the pinned admitted digest",
    )
    return profile, admission


# --------------------------------------------------------------------------------
# the admitted gate's root algorithms, reproduced
# --------------------------------------------------------------------------------


def stage_evidence_root(admission, *, scope, sequence, stage, rows):
    """Recompute one stage evidence-admission root exactly as the admitted gate does."""
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


def admission_digest_root(admission, stage_rows):
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


def load_materialization_receipt(
    *, profile: Mapping[str, Any], path: Path, receipt: Mapping[str, Any], admission_id: str,
    packet_id: str, campaign_id: str, canonical: str, contract_id: str,
) -> Mapping[str, Any]:
    """Read and re-identify the materialization receipt, then bind it to the admitted gate."""
    law_block = profile["evidenceMaterialization"]
    codes = law_block["refusalCodes"]
    require(
        law_block["rowClass"] == "receipt-subordinate",
        "PROFILE_INVALID",
        "the profile does not classify materialized evidence rows as receipt-subordinate",
    )
    require(path.is_file(), codes["absent"], "no evidence-materialization receipt was supplied")
    body = read_json_file(path, code=codes["invalid"], label="evidence materialization receipt")
    exact_keys(body, law_block["keys"], codes["invalid"], "evidence materialization receipt")
    require(
        body["schema"] == law_block["schema"] and body["status"] == law_block["requiredStatus"],
        codes["invalid"],
        "evidence materialization receipt schema or status differs",
    )
    assert_identity(
        body, law_block["idKey"], law_block["idPrefix"], codes["invalid"], "evidence materialization receipt"
    )
    require(
        body["authority"] == AUTHORITY,
        "AUTHORITY_WIDENED",
        "evidence materialization receipt grants authority",
    )
    require(
        body["admissionId"] == admission_id
        and body["requestId"] == receipt["requestId"]
        and body["packetId"] == packet_id
        and body["campaignId"] == campaign_id
        and body["canonicalMissionStateDigest"] == canonical
        and body["successorContractId"] == contract_id
        and body["evidenceAdmissionDigestRoot"] == receipt["evidenceAdmissionDigestRoot"],
        codes["binding"],
        "the materialization receipt does not bind this admission receipt, request, packet and admission root",
    )
    require(
        body["extraEvidenceRoleCount"] == 0
        and body["missingEvidenceRoleCount"] == 0
        and body["duplicateBodyIdentityCount"] == 0,
        codes["denominator"],
        "the materialization receipt reports extra, missing or duplicated evidence roles",
    )
    return body


def load_admission_request(
    *, profile: Mapping[str, Any], admission: Mapping[str, Any], candidates: Path, request_id: str
) -> Mapping[str, Any]:
    """Read and re-identify the exact admission request the gate was issued over."""
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
    measured = assert_identity(
        request, request_law["idKey"], request_law["idPrefix"], codes["requestBinding"], "admission request"
    )
    require(
        measured == request_id,
        codes["requestBinding"],
        "the admission request on disk is not the request this admission and materialization name",
    )
    return request


def replay_materialized_role(
    *,
    profile: Mapping[str, Any],
    role_row: Mapping[str, Any],
    descriptor: Mapping[str, Any],
    candidates: Path,
    packet: Path,
) -> None:
    """Prove one role's admitted descriptor, candidate body and packet body are one body."""
    codes = profile["evidenceMaterialization"]["refusalCodes"]
    label = f"{role_row['stage']} evidence role {role_row['evidenceRoleKey']}"
    require(
        descriptor["provenanceClass"] == role_row["provenanceClass"]
        and descriptor["evidenceClass"] == role_row["evidenceClass"]
        and descriptor["mediaType"] == role_row["mediaType"]
        and descriptor["bodySchema"] == role_row["bodySchema"]
        and descriptor["bodySha256"] == role_row["bodySha256"]
        and descriptor["bodyBytes"] == role_row["bodyBytes"]
        and descriptor["bodyPath"] == role_row["candidateBodyPath"]
        and descriptor["opaqueInstrumentClass"] == role_row["opaqueInstrumentClass"],
        codes["bodySubstituted"],
        f"{label} materialized row differs from the descriptor the gate admitted",
    )
    if role_row["opaqueInstrumentClass"] is None:
        require(
            descriptor["bodyContentId"] == role_row["bodyContentId"],
            codes["bodyIdentityForged"],
            f"{label} materialized identity differs from the admitted descriptor identity",
        )
    else:
        require(
            descriptor["bodyContentId"] is None
            and role_row["bodyContentId"] == role_row["instrumentReceiptId"],
            codes["bodyIdentityForged"],
            f"{label} opaque identity is not its admitted instrument receipt identity",
        )

    pairs = [(role_row["candidateBodyPath"], role_row["packetDestination"], role_row["bodySha256"], role_row["bodyBytes"])]
    if role_row["instrumentReceiptDestination"] is not None:
        require(
            descriptor["instrumentReceiptPath"] == role_row["instrumentReceiptPath"],
            codes["bodySubstituted"],
            f"{label} materialized instrument receipt is not the admitted one",
        )
        pairs.append(
            (
                role_row["instrumentReceiptPath"],
                role_row["instrumentReceiptDestination"],
                role_row["instrumentReceiptSha256"],
                role_row["instrumentReceiptBytes"],
            )
        )
    for candidate_relative, packet_relative, digest, size in pairs:
        candidate_path = validate_lexical_coordinate(
            candidates / candidate_relative, label=f"{label} candidate body", code=codes["bodySubstituted"]
        )
        require(
            is_within(candidate_path, candidates),
            codes["bodySubstituted"],
            f"{label} candidate body escapes the admission workspace",
        )
        candidate_data = read_bounded_bytes(
            candidate_path, MAX_EVIDENCE_BYTES, code=codes["bodySubstituted"], label=f"{label} candidate body"
        )
        require(
            sha256_bytes(candidate_data) == digest and len(candidate_data) == size,
            codes["bodySubstituted"],
            f"{label} candidate body is not the body the gate admitted",
        )
        packet_path = validate_lexical_coordinate(
            packet / packet_relative, label=f"{label} packet body", code=codes["destinationInvalid"]
        )
        require(
            is_within(packet_path, packet),
            "STAGE_EVIDENCE_ESCAPES_PACKET",
            f"{label} packet body escapes the packet",
        )
        packet_data = read_bounded_bytes(
            packet_path, MAX_EVIDENCE_BYTES, code=codes["bodySubstituted"], label=f"{label} packet body"
        )
        require(
            packet_data == candidate_data,
            codes["bodySubstituted"],
            f"{label} packet body is not the admitted candidate body",
        )


# --------------------------------------------------------------------------------
# closure
# --------------------------------------------------------------------------------


def close_pre_seal(
    *,
    packet: Path,
    admission_receipt: Path,
    materialization_receipt: Path,
    authentication_receipt: Path,
    candidates: Path,
    profile_path: Path,
    repository: Path,
    replay_sealed_predecessor: bool = False,
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
    packet_law = profile["packet"]
    closure_law = profile["preSealClosure"]
    record_law = packet_law["stageRecord"]
    stages = list(admission["stageSequence"])

    marker = read_json_file(
        packet / packet_law["files"]["marker"], code="PACKET_MARKER_INVALID", label="packet marker"
    )
    exact_keys(marker, packet_law["markerKeys"], "PACKET_MARKER_INVALID", "packet marker")
    assert_identity(
        marker, packet_law["markerIdKey"], packet_law["markerIdPrefix"], "PACKET_MARKER_INVALID", "packet marker"
    )
    packet_id = assert_content_id(marker["packetId"], "PACKET_MARKER_INVALID", "packet identity")

    state = read_json_file(
        packet / packet_law["files"]["state"], code="PACKET_STATE_INVALID", label="packet state"
    )
    exact_keys(state, packet_law["stateKeys"], "PACKET_STATE_INVALID", "packet state")
    assert_identity(
        state, packet_law["stateIdKey"], packet_law["stateIdPrefix"], "PACKET_STATE_INVALID", "packet state"
    )
    require(
        state["packetId"] == packet_id,
        "PACKET_CAMPAIGN_BINDING_INVALID",
        "the packet state names another packet than its marker",
    )

    # ---- unsealed, and no sealed root exists ---------------------------------------
    require(
        (state["sealed"] is False and state["sealedDispositionId"] is None)
        or (
            replay_sealed_predecessor
            and state["sealed"] is True
            and isinstance(state["sealedDispositionId"], str)
        ),
        "PACKET_ALREADY_SEALED",
        "a sealed packet cannot receive a pre-seal closure outside authenticated seal recovery",
    )
    require(
        state["completedStageCount"] == profile["denominator"]["stageDenominator"]
        and state["nextStage"] is None,
        "PACKET_INCOMPLETE",
        "the packet has not reached exact sixteen of sixteen",
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

    # ---- the admitted receipt, still bootstrap-authenticated -----------------------
    receipt = read_json_file(
        validate_lexical_coordinate(
            admission_receipt, label="admission receipt", code="ADMISSION_RECEIPT_INVALID"
        ),
        code="ADMISSION_RECEIPT_INVALID",
        label="admission receipt",
    )
    require(
        receipt.get("bootstrapAuthenticated") is True,
        "ADMISSION_RECEIPT_NOT_BOOTSTRAP_AUTHENTICATED",
        "the pre-seal closure consumes only a bootstrap-authenticated admission receipt",
    )
    receipt_law = profile["admissionProfile"]
    signed_body = {
        key: value
        for key, value in receipt.items()
        if key not in BOOTSTRAP_ANNOTATIONS and key != receipt_law["receiptIdKey"]
    }
    signed_body[BOOTSTRAP_FLAG] = False
    admission_id = receipt.get(receipt_law["receiptIdKey"])
    require(
        admission_id == content_id(receipt_law["receiptIdPrefix"], signed_body),
        "ADMISSION_RECEIPT_IDENTITY_INVALID",
        "the admission receipt identity does not recompute from the body the gate signed",
    )
    require(
        receipt.get("terminal") == receipt_law["requiredTerminal"]
        and receipt.get("packetId") == packet_id
        and receipt.get("campaignId") == campaign_id
        and receipt.get("canonicalMissionStateDigest") == canonical
        and receipt.get("successorContractId") == contract_id,
        "ADMISSION_RECEIPT_BINDING_INVALID",
        "the admission receipt does not admit this packet, campaign, canonical state and contract",
    )
    evidence_admission_root = assert_content_id(
        receipt.get("evidenceAdmissionDigestRoot"), "ADMISSION_RECEIPT_INVALID", "evidence admission digest root"
    )

    # ---- the admitted roles, replayed against the workspace and the packet -----------
    materialization_law = profile["evidenceMaterialization"]
    materialization_codes = materialization_law["refusalCodes"]
    require(
        not is_within(candidates, packet),
        materialization_codes["invalid"],
        "the candidate evidence workspace may not live inside the packet it fed",
    )
    materialization = load_materialization_receipt(
        profile=profile,
        path=validate_lexical_coordinate(
            materialization_receipt,
            label="evidence materialization receipt",
            code=materialization_codes["absent"],
        ),
        receipt=receipt,
        admission_id=admission_id,
        packet_id=packet_id,
        campaign_id=campaign_id,
        canonical=canonical,
        contract_id=contract_id,
    )
    materialization_id = materialization[materialization_law["idKey"]]
    request = load_admission_request(
        profile=profile, admission=admission, candidates=candidates, request_id=materialization["requestId"]
    )
    descriptors_by_role: dict[tuple[str, str], Mapping[str, Any]] = {}
    for stage_request in request["stages"]:
        for descriptor in stage_request["evidence"]:
            key = (stage_request["stage"], descriptor["evidenceRole"])
            require(
                key not in descriptors_by_role,
                materialization_codes["roleDuplicated"],
                "the admission request offers one evidence role twice for one stage",
            )
            descriptors_by_role[key] = descriptor

    role_rows = materialization["roles"]
    require(
        isinstance(role_rows, list) and len(role_rows) == profile["denominator"]["evidenceRoleDenominator"],
        materialization_codes["denominator"],
        "the materialization receipt does not carry the admitted forty-three evidence roles",
    )
    roles_by_stage: dict[str, list[Mapping[str, Any]]] = {}
    materialized_identities: set[str] = set()
    materialized_coordinates: dict[str, Mapping[str, Any]] = {}
    for role_row in role_rows:
        exact_keys(
            role_row,
            materialization_law["roleRowKeys"],
            materialization_codes["invalid"],
            "materialized evidence role row",
        )
        descriptor = descriptors_by_role.get((role_row["stage"], role_row["evidenceRole"]))
        require(
            descriptor is not None,
            materialization_codes["roleUnadmitted"],
            f"{role_row['stage']} materialized a role the admission request never offered",
        )
        replay_materialized_role(
            profile=profile,
            role_row=role_row,
            descriptor=descriptor,
            candidates=candidates,
            packet=packet,
        )
        require(
            role_row["bodyContentId"] not in materialized_identities,
            materialization_codes["bodyIdentityForged"],
            "one evidence identity is materialized for more than one role",
        )
        materialized_identities.add(role_row["bodyContentId"])
        for coordinate in (role_row["packetDestination"], role_row["instrumentReceiptDestination"]):
            if coordinate is None:
                continue
            require(
                coordinate not in materialized_coordinates,
                materialization_codes["destinationInvalid"],
                f"two admitted bodies occupy one packet coordinate: {coordinate}",
            )
            materialized_coordinates[coordinate] = role_row
        roles_by_stage.setdefault(role_row["stage"], []).append(role_row)

    # Statements are attributed by admitted provenance class, not by stage membership.
    statement_bindings = materialization["statementBindings"]
    require(
        len(statement_bindings) == profile["denominator"]["humanStatementRoleCount"],
        materialization_codes["statementBinding"],
        "the materialization receipt does not bind three named-human statements",
    )
    for binding in statement_bindings:
        exact_keys(
            binding,
            materialization_law["statementBindingKeys"],
            materialization_codes["statementBinding"],
            "named-human statement binding",
        )
        matched = [
            row
            for row in roles_by_stage[binding["stage"]]
            if row["evidenceRole"] == binding["evidenceRole"]
        ]
        require(
            len(matched) == 1
            and matched[0]["bodyContentId"] == binding["statementId"]
            and matched[0]["provenanceClass"] == "named_human_statement",
            materialization_codes["statementBinding"],
            f"the {binding['stage']} statement binding does not name that stage's admitted named-human role",
        )

    # ---- the authenticated named-human decisions ------------------------------------
    authentication_law = profile["humanAuthentication"]
    authentication = read_json_file(
        validate_lexical_coordinate(
            authentication_receipt,
            label="named-human authentication receipt",
            code=authentication_law["refusalCodes"]["absent"],
        ),
        code=authentication_law["refusalCodes"]["binding"],
        label="named-human authentication receipt",
    )
    exact_keys(
        authentication,
        authentication_law["receiptKeys"],
        authentication_law["refusalCodes"]["binding"],
        "named-human authentication receipt",
    )
    assert_identity(
        authentication,
        authentication_law["receiptIdKey"],
        authentication_law["receiptIdPrefix"],
        authentication_law["refusalCodes"]["binding"],
        "named-human authentication receipt",
    )
    authentication_id = authentication[authentication_law["receiptIdKey"]]
    require(
        authentication["admissionId"] == admission_id
        and authentication["packetId"] == packet_id
        and authentication["campaignId"] == campaign_id,
        authentication_law["refusalCodes"]["binding"],
        "the authentication receipt does not bind this admission receipt, packet and campaign",
    )
    statement_ids = sorted(authentication["statementIds"])
    confirmation_ids = sorted(authentication["confirmationIds"])
    require(
        len(statement_ids) == profile["denominator"]["humanStatementRoleCount"]
        and len(set(statement_ids)) == len(statement_ids),
        DENOMINATOR_INCOMPLETE,
        "the closure requires three distinct authenticated named-human statements",
    )
    require(
        len(confirmation_ids) == profile["denominator"]["stageConfirmationDenominator"]
        and len(set(confirmation_ids)) == len(confirmation_ids),
        DENOMINATOR_INCOMPLETE,
        "the closure requires sixteen distinct authenticated stage confirmations",
    )
    require(
        sorted(authentication["authenticatedStatementIds"]) == statement_ids,
        DENOMINATOR_INCOMPLETE,
        "the authentication receipt names statements it did not authenticate",
    )
    require(
        statement_ids == sorted(row["statementId"] for row in statement_bindings),
        DENOMINATOR_INCOMPLETE,
        "the authenticated statements are not the exact named-human statement of each statement-owing stage",
    )

    # ---- the sixteen stage records, re-identified in order ---------------------------
    record_rows: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    measured_stage_rows: list[dict[str, Any]] = []
    terminal_counts = {"PASS": 0, "HUMAN_REQUIRED": 0, "REFUSED": 0}
    conflict_branches: list[str] = []
    conflict_stage = admission["bodySchemas"]["named_human_statement"]["conflictStage"]
    seen_confirmations: set[str] = set()

    for index, stage in enumerate(stages):
        row = state["stages"][index]
        require(
            row["stage"] == stage and row["sequence"] == index + 1 and row["status"] == "recorded",
            "PACKET_INCOMPLETE",
            f"stage {stage} is not recorded in sequence order",
        )
        record = read_json_file(
            packet / Path(row["draftPath"]).parent / record_law["fileName"],
            code="STAGE_RECORD_INVALID",
            label=f"{stage} stage record",
        )
        exact_keys(record, record_law["keys"], "STAGE_RECORD_INVALID", f"{stage} stage record")
        record_id = assert_identity(
            record, record_law["idKey"], record_law["idPrefix"], "STAGE_RECORD_INVALID", f"{stage} stage record"
        )
        require(
            record_id == row["recordDigest"],
            "STAGE_RECORD_BINDING_INVALID",
            f"{stage} stage record identity differs from the packet state",
        )
        require(
            record["packetId"] == packet_id
            and record["stage"] == stage
            and record["sequence"] == index + 1
            and record["admissionId"] == admission_id
            and record["canonicalMissionStateIdBefore"] == canonical
            and record["canonicalMissionStateIdAfter"] == canonical,
            "STAGE_RECORD_BINDING_INVALID",
            f"{stage} stage record does not bind this packet, admission and canonical state",
        )
        require(
            record["terminalState"] == admission["stages"][stage]["requiredTerminal"],
            "STAGE_TERMINAL_INVALID",
            f"{stage} stage record names a terminal the stage does not require",
        )
        terminal_counts[record["terminalState"]] += 1
        confirmation_id = assert_content_id(
            record["stageConfirmationId"], "STAGE_RECORD_INVALID", f"{stage} stage confirmation identity"
        )
        require(
            confirmation_id in confirmation_ids,
            "STAGE_CONFIRMATION_NOT_AUTHENTICATED",
            f"{stage} was recorded under a stage confirmation the authentication receipt did not authenticate",
        )
        require(
            confirmation_id not in seen_confirmations,
            "STAGE_CONFIRMATION_REPLAYED",
            f"one authenticated stage confirmation is bound to more than one stage: {stage}",
        )
        seen_confirmations.add(confirmation_id)

        if stage == conflict_stage:
            observation = record["observation"]
            left = assert_sha256(
                observation.get("leftStateDigest"), "CONFLICT_BRANCHES_LOST", "retained left branch digest"
            )
            right = assert_sha256(
                observation.get("rightStateDigest"), "CONFLICT_BRANCHES_LOST", "retained right branch digest"
            )
            require(left != right, "CONFLICT_BRANCHES_LOST", "the retained conflict branches are not distinct")
            require(
                observation.get("automaticMerge") is False
                and observation.get("resolution") == "human_required"
                and record["terminalState"] == "HUMAN_REQUIRED",
                "CONFLICT_OBLIGATION_DISCHARGED",
                "the retained conflict was merged or resolved instead of held for the named human",
            )
            conflict_branches = sorted([left, right])

        stage_roles = roles_by_stage.get(stage, [])
        expected_coordinates: dict[str, tuple[Mapping[str, Any], bool]] = {}
        for role_row in stage_roles:
            expected_coordinates[role_row["packetDestination"]] = (role_row, False)
            if role_row["instrumentReceiptDestination"] is not None:
                expected_coordinates[role_row["instrumentReceiptDestination"]] = (role_row, True)
        require_exact_stage_evidence_directory(
            packet=packet,
            evidence_directory=row["evidenceDirectory"],
            expected_coordinates=set(expected_coordinates),
            stage=stage,
        )
        require(
            {row["relativePath"] for row in record["evidenceFiles"]} == set(expected_coordinates)
            and len(record["evidenceFiles"]) == len(expected_coordinates),
            materialization_codes["unmaterializedEvidence"],
            f"{stage} records evidence bodies that are not exactly the admitted materialized set",
        )

        for evidence in record["evidenceFiles"]:
            exact_keys(
                evidence, record_law["evidenceRowKeys"], "STAGE_EVIDENCE_INVALID", f"{stage} stage evidence row"
            )
            relative = evidence["relativePath"]
            role_row, is_instrument_receipt = expected_coordinates[relative]
            expected_identity = (
                role_row["instrumentReceiptId"] if is_instrument_receipt else role_row["bodyContentId"]
            )
            expected_digest = (
                role_row["instrumentReceiptSha256"] if is_instrument_receipt else role_row["bodySha256"]
            )
            expected_bytes = (
                role_row["instrumentReceiptBytes"] if is_instrument_receipt else role_row["bodyBytes"]
            )
            require(
                evidence["evidenceRole"] == role_row["evidenceRole"]
                and evidence["provenanceClass"] == role_row["provenanceClass"]
                and evidence["evidenceClass"] == role_row["evidenceClass"]
                and evidence["bodyContentId"] == expected_identity
                and evidence["sha256"] == expected_digest
                and evidence["bytes"] == expected_bytes,
                materialization_codes["bodySubstituted"],
                f"{stage} stage evidence row does not describe the admitted body at {relative}",
            )
            require(
                RELATIVE_MEMBER_RE.fullmatch(relative) is not None and "\\" not in relative,
                "STAGE_EVIDENCE_INVALID",
                f"recorded evidence path is not an admitted relative member: {relative}",
            )
            body_path = validate_lexical_coordinate(
                packet / relative, label="recorded evidence body", code="STAGE_EVIDENCE_INVALID"
            )
            require(
                is_within(body_path, packet),
                "STAGE_EVIDENCE_ESCAPES_PACKET",
                f"recorded evidence escapes the packet: {relative}",
            )
            data = read_bounded_bytes(
                body_path, MAX_EVIDENCE_BYTES, code="STAGE_EVIDENCE_INVALID", label=f"recorded evidence {relative}"
            )
            require(
                sha256_bytes(data) == evidence["sha256"] and len(data) == evidence["bytes"],
                "STAGE_EVIDENCE_DRIFT",
                f"recorded evidence changed after recording: {relative}",
            )
            manifest_rows.append(
                {
                    "sequence": index + 1,
                    "stage": stage,
                    "relativePath": relative,
                    "sha256": evidence["sha256"],
                    "bytes": evidence["bytes"],
                    "evidenceClass": evidence["evidenceClass"],
                    "evidenceRole": evidence["evidenceRole"],
                    "provenanceClass": evidence["provenanceClass"],
                    "bodyContentId": evidence["bodyContentId"],
                }
            )
        # The recorded root is recomputed from the bodies the packet carries, and required
        # to equal both the gate's published root and the root the record names. A record
        # that copied a root it did not measure cannot survive this.
        receipt_stage_row = next(row for row in receipt["stages"] if row["stage"] == stage)
        measured_stage_root = stage_evidence_root(
            admission,
            scope=ALL_ROLES_SCOPE,
            sequence=index + 1,
            stage=stage,
            rows=stage_roles,
        )
        require(
            len(stage_roles) == admission["stages"][stage]["evidenceRoleDenominator"],
            materialization_codes["denominator"],
            f"{stage} does not carry its admitted evidence-role denominator",
        )
        require(
            measured_stage_root == receipt_stage_row["evidenceAdmissionRoot"]
            and measured_stage_root == record["evidenceAdmissionRoot"],
            materialization_codes["stageRootMismatch"],
            f"{stage} evidence-admission root recomputed from the packet differs from the gate's or the record's",
        )
        measured_stage_rows.append(
            {
                "sequence": index + 1,
                "stage": stage,
                "evidenceAdmissionRoot": measured_stage_root,
                "observationDigest": receipt_stage_row["observationDigest"],
            }
        )
        record_rows.append(
            {
                "sequence": index + 1,
                "stage": stage,
                "terminalState": record["terminalState"],
                "recordDigest": record_id,
                "evidenceAdmissionRoot": measured_stage_root,
                "observationDigest": record["observationDigest"],
            }
        )

    require(
        terminal_counts == profile["denominator"]["recordedTerminalCounts"],
        "RECORDED_TERMINAL_DENOMINATOR_INVALID",
        "the recorded terminal denominator differs from the admitted denominator",
    )
    require(
        len(conflict_branches) == 2,
        "CONFLICT_BRANCHES_LOST",
        "the packet does not retain the two divergent branches of the held conflict",
    )
    require(
        sorted(seen_confirmations) == confirmation_ids,
        "STAGE_CONFIRMATION_NOT_AUTHENTICATED",
        "the recorded stage confirmations are not exactly the authenticated sixteen",
    )
    require(
        len(manifest_rows) == len(materialized_coordinates)
        and len(manifest_rows) == materialization["physicalBodyCount"],
        materialization_codes["unmaterializedEvidence"],
        "the packet carries a different number of private evidence bodies than the admitted set",
    )
    require(
        admission_digest_root(admission, measured_stage_rows) == evidence_admission_root,
        materialization_codes["admissionRootMismatch"],
        "the complete admission digest root recomputed from the packet differs from the gate's",
    )

    stage_record_root = content_id(closure_law["recordRootPrefix"], record_rows)
    manifest_root = content_id(
        closure_law["manifestRootPrefix"],
        {"bodies": manifest_rows, "bodyCount": len(manifest_rows)},
    )

    body = {
        "schema": closure_law["schema"],
        "status": closure_law["requiredStatus"],
        "admissionId": admission_id,
        "authenticationVerificationId": authentication_id,
        "campaignId": campaign_id,
        "canonicalMissionStateDigest": canonical,
        "completedStageCount": state["completedStageCount"],
        "conflictRetainedBranchDigests": conflict_branches,
        "conflictStage": conflict_stage,
        "evidenceAdmissionDigestRoot": evidence_admission_root,
        "humanStatementIds": statement_ids,
        "materializationReceiptId": materialization_id,
        "materializedEvidenceRoleCount": len(role_rows),
        "packetId": packet_id,
        "privateEvidenceBodyCount": len(manifest_rows),
        "preSealEvidenceManifestRoot": manifest_root,
        "recordedTerminalCounts": terminal_counts,
        "sealedRootAbsent": True,
        "stageConfirmationIds": confirmation_ids,
        "stageRecordIdentityRoot": stage_record_root,
        "successorContractId": contract_id,
        "successorSourceSetId": contract["successorSourceSetId"],
        "unsealed": True,
        "authority": AUTHORITY,
        "claimBoundary": closure_law["claimBoundary"],
    }
    closure = {**body, closure_law["idKey"]: content_id(closure_law["idPrefix"], body)}
    exact_keys(closure, closure_law["keys"], "PRE_SEAL_CLOSURE_INVALID", "pre-seal closure")
    assert_no_post_seal_assertion(closure, profile)
    return closure


def assert_no_post_seal_assertion(closure: Mapping[str, Any], profile: Mapping[str, Any]) -> None:
    """A pre-seal object may not carry a post-seal field, even by accident."""
    reserved = {key.lower() for key in profile["postSealClosure"]["requiredValues"]}
    for key in closure:
        require(
            key.lower() not in reserved,
            "POST_SEAL_ASSERTION_BEFORE_SEALING",
            f"the pre-seal closure carries a post-seal assertion: {key}",
        )


def refusal_document(code: str, message: str) -> dict[str, Any]:
    return {
        "schema": "stc-mary/successor-flight-pre-seal-closure/1",
        "status": "REFUSED",
        "code": code,
        "message": message,
        "sealedRootAbsent": True,
        "authority": AUTHORITY,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Close one 0.2 successor packet at exact sixteen of sixteen, before sealing"
    )
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--admission-receipt", type=Path, required=True)
    parser.add_argument("--materialization-receipt", type=Path, required=True)
    parser.add_argument("--authentication-receipt", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        output = None
        if args.out is not None:
            output = validate_lexical_coordinate(args.out, label="closure output", code="CLOSURE_PATH_INVALID")
            # The profile has always declared that this closure is emitted outside every
            # surface it measured. Reading the flag is what makes that a rule rather than
            # a comment beside an independently hardcoded check.
            declared = read_json_file(
                validate_lexical_coordinate(
                    args.profile, label="successor flight profile", code="PROFILE_UNREADABLE"
                ),
                code="PROFILE_UNREADABLE",
                label="successor flight profile",
            )
            if declared["preSealClosure"]["writtenInsidePacket"] is not False:
                fail("PROFILE_INVALID", "the profile permits the pre-seal closure to be written inside the packet")
            if is_within(output, Path(os.path.abspath(os.fspath(args.packet)))):
                fail("CLOSURE_INSIDE_MEASURED_SURFACE", "the pre-seal closure may not be written inside the packet")
            if output.exists():
                fail("CLOSURE_OUTPUT_EXISTS", "pre-seal closure output must not already exist")
        closure = close_pre_seal(
            packet=args.packet,
            admission_receipt=args.admission_receipt,
            materialization_receipt=args.materialization_receipt,
            authentication_receipt=args.authentication_receipt,
            candidates=args.candidates,
            profile_path=args.profile,
            repository=args.repository_root,
        )
        data = canonical_json_bytes(closure)
        if output is None:
            sys.stdout.buffer.write(data)
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(data)
        return 0
    except PreSealClosureError as exc:
        sys.stdout.buffer.write(canonical_json_bytes(refusal_document(exc.code, str(exc))))
        return 1
    except (OSError, ValueError) as exc:
        sys.stdout.buffer.write(
            canonical_json_bytes(refusal_document("PRE_SEAL_CLOSURE_FILESYSTEM_ERROR", str(exc)))
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
