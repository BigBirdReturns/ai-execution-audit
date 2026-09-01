"""Close one 0.2 successor packet at exact sixteen of sixteen, before it is sealed.

This is the surface that decides a packet is finished recording. It is deliberately not
the surface that seals it, and it imports nothing from the source set that recorded it.

It binds, in one object:

    three authenticated named-human statement identities
    sixteen authenticated stage-confirmation identities
    the final packet-stage record identity root
    the complete evidence-admission digest root
    the pre-seal evidence-manifest root, re-hashed from the bodies on disk
    the retained two-branch HUMAN_REQUIRED conflict
    an unsealed packet state
    an absent sealed root
    authority none

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

# The bootstrap adds three annotations and flips the gate's own bootstrapAuthenticated
# from false to true. The gate signed while it was still false.
BOOTSTRAP_ANNOTATIONS = ("bootstrapSchema", "bootstrapVerifier", "bootstrapVerifierSha256")
BOOTSTRAP_FLAG = "bootstrapAuthenticated"

CLAIM_BOUNDARY = (
    "Pre-seal closure for one synthetic successor packet at exact sixteen of sixteen. It binds "
    "the authenticated named-human decisions, the final stage-record identity root, the complete "
    "admission root and the re-measured pre-seal evidence manifest of an unsealed packet. It "
    "asserts nothing about a sealed run, public disposition, sealed manifest or detached "
    "verification, seals nothing, records nothing, qualifies no physical estate, representative "
    "operator, field network, operational C2 or production Lattice, and grants no mission, "
    "command, targeting, engagement, effector or weapons authority."
)


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
# closure
# --------------------------------------------------------------------------------


def close_pre_seal(
    *,
    packet: Path,
    admission_receipt: Path,
    authentication_receipt: Path,
    profile_path: Path,
    repository: Path,
) -> dict[str, Any]:
    require_supported_python()
    packet = validate_lexical_coordinate(packet, label="packet root", code="PACKET_ROOT_INVALID")
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
        state["sealed"] is False and state["sealedDispositionId"] is None,
        "PACKET_ALREADY_SEALED",
        "a sealed packet cannot receive a pre-seal closure",
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

    # ---- the sixteen stage records, re-identified in order ---------------------------
    record_rows: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
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

        for evidence in record["evidenceFiles"]:
            exact_keys(
                evidence, record_law["evidenceRowKeys"], "STAGE_EVIDENCE_INVALID", f"{stage} stage evidence row"
            )
            relative = evidence["relativePath"]
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
                }
            )
        record_rows.append(
            {
                "sequence": index + 1,
                "stage": stage,
                "terminalState": record["terminalState"],
                "recordDigest": record_id,
                "evidenceAdmissionRoot": record["evidenceAdmissionRoot"],
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
        "packetId": packet_id,
        "preSealEvidenceManifestRoot": manifest_root,
        "recordedTerminalCounts": terminal_counts,
        "sealedRootAbsent": True,
        "stageConfirmationIds": confirmation_ids,
        "stageRecordIdentityRoot": stage_record_root,
        "successorContractId": contract_id,
        "successorSourceSetId": contract["successorSourceSetId"],
        "unsealed": True,
        "authority": AUTHORITY,
        "claimBoundary": CLAIM_BOUNDARY,
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
    parser.add_argument("--authentication-receipt", type=Path, required=True)
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
            if is_within(output, Path(os.path.abspath(os.fspath(args.packet)))):
                fail("CLOSURE_INSIDE_MEASURED_SURFACE", "the pre-seal closure may not be written inside the packet")
            if output.exists():
                fail("CLOSURE_OUTPUT_EXISTS", "pre-seal closure output must not already exist")
        closure = close_pre_seal(
            packet=args.packet,
            admission_receipt=args.admission_receipt,
            authentication_receipt=args.authentication_receipt,
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
