"""Record a stc-mary/private-flight-packet/0.2 successor packet from an admitted receipt.

This is the only surface in the source set that causes a stage to be recorded, and it can
do so only from evidence somebody else already admitted.

Three inputs are mandatory and none is produced here:

    1. an externally bootstrap-authenticated ADMISSIBLE_FOR_PACKET_RECORDING receipt
       from the admitted packet-evidence-admission@2 gate, for this exact packet
    2. an evidence-materialization receipt from the separately authenticated bridge
       verifier, naming all forty-three admitted evidence roles, the body identity and
       digest of each, and one deterministic packet coordinate per role
    3. a named-human authentication verification receipt satisfying the closed interface
       issue #94 owns, covering all three statements and all sixteen confirmations

The second exists because the admission receipt publishes forty-three evidence roles but
places no body in the packet. Without it this orchestrator would record whatever files
happened to sit in each stage directory while copying the gate's forty-three-role roots
beside them, and the packet's denominator would be unrelated to the admitted one. Nothing
enters a stage's evidence directory here except the closed set that receipt names.

The third exists because the first cannot carry it. The admission receipt's human
statements and stage confirmations each carry an ``authenticationBinding`` string beside a
self-declared ``actorClass``. A machine can write both. This orchestrator therefore
refuses to read either as proof that the human principal acted, and requires a separate
receipt from a mechanism that actually verified them. Until issue #94 admits such a
mechanism, only the synthetic source fixture satisfies it, and that fixture may be used
only against a synthetic campaign.

The recorder-facing confirmation state for each stage is derived from exactly one place:
the authenticated stage-confirmation identity the admission receipt bound to that stage.
There is no ``operatorConfirmed`` input anywhere in this module.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import stc_mary_successor_flight_law as law  # noqa: E402
import stc_mary_successor_packet_runtime as runtime  # noqa: E402

PROFILE_PATH = HERE / "stc-mary-successor-packet-flight-01-profile-01.json"

ORCHESTRATION_SCHEMA = "stc-mary/successor-flight-orchestration-receipt/1"
ORCHESTRATION_ID_KEY = "orchestrationReceiptId"
ORCHESTRATION_ID_PREFIX = "stcmarysuccessorflightorchestration1"

# What the admission bootstrap does to the gate's own receipt after it has measured and
# isolated the gate: it ADDS the three annotations below, and it FLIPS the gate's own
# self-reported bootstrapAuthenticated from false to true. The gate signed its body while
# that flag was still false, so re-identifying the receipt means removing the three
# annotations and restoring the flag -- not removing all four.
BOOTSTRAP_ANNOTATIONS = ("bootstrapSchema", "bootstrapVerifier", "bootstrapVerifierSha256")
BOOTSTRAP_FLAG = "bootstrapAuthenticated"


def signed_admission_body(receipt: Mapping[str, Any], id_key: str) -> dict[str, Any]:
    """Reconstruct exactly the body the admission gate signed."""
    body = {
        key: value
        for key, value in receipt.items()
        if key not in BOOTSTRAP_ANNOTATIONS and key != id_key
    }
    body[BOOTSTRAP_FLAG] = False
    return body


ORCHESTRATION_CLAIM = (
    "Recording receipt for one synthetic successor packet. It reports which admitted evidence "
    "bodies were materialized into which packet coordinates, and which authenticated named-human "
    "decisions caused each stage to be recorded. It seals "
    "nothing, asserts nothing about a sealed run, public disposition, sealed manifest or "
    "detached verification, qualifies no physical estate, operator, field network, operational "
    "C2 or production Lattice, and grants no mission, command, targeting, engagement, effector "
    "or weapons authority."
)


# --------------------------------------------------------------------------------
# the admitted receipt
# --------------------------------------------------------------------------------


def load_admission_receipt(
    *, profile: Mapping[str, Any], path: Path, packet: Mapping[str, Any], campaign_id: str
) -> Mapping[str, Any]:
    law_block = profile["admissionProfile"]
    code = "ADMISSION_RECEIPT_INVALID"
    receipt = law.read_json_file(path, code=code, label="admission receipt")
    law.require(receipt.get("schema") == law_block["receiptSchema"], code, "admission receipt schema differs")
    law.require(receipt.get("status") == "PASS", code, "admission receipt did not pass")
    law.require(
        receipt.get("profileId") == law_block["profileId"],
        code,
        "admission receipt was issued under another admission profile",
    )
    law.require(
        receipt.get("terminal") == law_block["requiredTerminal"],
        "ADMISSION_TERMINAL_INVALID",
        "the admission receipt does not carry ADMISSIBLE_FOR_PACKET_RECORDING",
    )

    # ---- externally bootstrap-authenticated, not self-asserted -----------------
    law.require(
        receipt.get("bootstrapAuthenticated") is True,
        "ADMISSION_RECEIPT_NOT_BOOTSTRAP_AUTHENTICATED",
        "this orchestrator consumes only an externally bootstrap-authenticated admission receipt",
    )
    for key in BOOTSTRAP_ANNOTATIONS:
        law.require(key in receipt, "ADMISSION_RECEIPT_NOT_BOOTSTRAP_AUTHENTICATED", f"admission receipt lacks {key}")
    law.assert_sha256(receipt["bootstrapVerifierSha256"], code, "bootstrap verifier digest")
    law.require(
        receipt["bootstrapVerifierSha256"] == receipt.get("measuredVerifierSha256"),
        "ADMISSION_RECEIPT_NOT_BOOTSTRAP_AUTHENTICATED",
        "the bootstrap verdict and the measured gate name different verifier bytes",
    )
    # The gate signed its body before the bootstrap annotated it, so the identity is
    # recomputed over the body the gate actually signed.
    signed_body = signed_admission_body(receipt, law_block["receiptIdKey"])
    law.require(
        receipt.get(law_block["receiptIdKey"])
        == law.content_id(law_block["receiptIdPrefix"], signed_body),
        "ADMISSION_RECEIPT_IDENTITY_INVALID",
        "the admission receipt identity does not recompute from the body the gate signed",
    )

    # ---- bound to this exact packet and campaign --------------------------------
    marker, state, config = packet["marker"], packet["state"], packet["config"]
    law.require(
        receipt.get("packetId") == marker["packetId"],
        "ADMISSION_PACKET_BINDING_INVALID",
        "the admission receipt admits another packet",
    )
    law.require(
        receipt.get("campaignId") == campaign_id,
        "ADMISSION_CAMPAIGN_BINDING_INVALID",
        "the admission receipt belongs to another campaign",
    )
    law.require(
        receipt.get("canonicalMissionStateDigest") == config["canonicalMissionStateDigest"],
        "CANONICAL_MISSION_STATE_CHANGED",
        "the admission receipt names another canonical mission state than the configured packet",
    )
    law.require(
        receipt.get("successorPacketProfileId") == profile["packet"]["packetProfileId"]
        and receipt.get("predecessorPacketProfileId") == profile["packet"]["predecessorPacketProfileId"]
        and receipt.get("packetMarkerProfileId") == state["packetProfileId"]
        and receipt.get("packetStateProfileId") == state["packetProfileId"],
        "ADMISSION_SUCCESSION_BINDING_INVALID",
        "the admission receipt names another packet-profile succession than this packet",
    )
    law.require(
        receipt.get("directFrozenPacketApplication") is False,
        "ADMISSION_SUCCESSION_BINDING_INVALID",
        "the admission receipt claims direct frozen packet application",
    )

    # ---- the packet's own lineage, as the gate measured it -----------------------
    law.require(
        receipt.get("successorContractId") == packet["successorContractId"]
        and receipt.get("successorSourceSetId") == packet["successorSourceSetId"]
        and receipt.get("packetHandoffId") == packet["packetHandoffId"]
        and receipt.get("predecessorPacketId") == packet["predecessorPacketId"],
        "ADMISSION_LINEAGE_BINDING_INVALID",
        "the admission receipt measured another lineage than this packet carries",
    )

    # ---- the complete denominator ------------------------------------------------
    denominator = profile["denominator"]
    law.require(
        receipt.get("evidenceRoleDenominator") == denominator["evidenceRoleDenominator"]
        and receipt.get("nonHumanEvidenceRoleDenominator") == denominator["nonHumanEvidenceRoleCount"]
        and receipt.get("humanStatementRoleDenominator") == denominator["humanStatementRoleCount"]
        and receipt.get("stageConfirmationDenominator") == denominator["stageConfirmationDenominator"]
        and receipt.get("stageDenominator") == denominator["stageDenominator"],
        "ADMISSION_DENOMINATOR_INVALID",
        "the admission receipt denominator differs from the admitted denominator",
    )
    law.require(
        receipt.get("admittedEvidenceRoleCount") == denominator["evidenceRoleDenominator"]
        and receipt.get("admittedNonHumanEvidenceRoleCount") == denominator["nonHumanEvidenceRoleCount"]
        and receipt.get("admittedHumanStatementCount") == denominator["humanStatementRoleCount"]
        and receipt.get("missingEvidenceRoleCount") == 0,
        "ADMISSION_DENOMINATOR_INCOMPLETE",
        "the admission receipt admits an incomplete evidence denominator",
    )
    law.require(
        receipt.get("suppliedStageConfirmationCount") == denominator["stageConfirmationDenominator"],
        "ADMISSION_DENOMINATOR_INCOMPLETE",
        "the admission receipt does not carry sixteen exact stage decisions",
    )
    law.require(
        receipt.get("confirmationDenominatorInvitable") is True,
        "ADMISSION_DENOMINATOR_INCOMPLETE",
        "the admission receipt reports the confirmation denominator as not invitable",
    )

    # ---- the gate recorded nothing on its own behalf ------------------------------
    law.require(
        receipt.get("packetStagesRecorded") == 0
        and receipt.get("operatorConfirmedFlagsSet") == 0
        and receipt.get("packetRecorderInvoked") is False
        and receipt.get("packetMutated") is False
        and receipt.get("humanStatementsGeneratedByThisGate") == 0
        and receipt.get("stageConfirmationsIssuedByThisGate") == 0,
        "ADMISSION_RECEIPT_RECORDING_STATE_INVALID",
        "the admission receipt reports recording, mutation, or manufactured human decisions",
    )
    law.require(receipt.get("authority") == law.AUTHORITY, "AUTHORITY_WIDENED", "admission receipt grants authority")
    return receipt


def stage_authorizations(
    *, profile: Mapping[str, Any], admission: Mapping[str, Any], receipt: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Turn the admitted receipt into exactly sixteen recording authorizations."""
    stages = law.stage_sequence(admission)
    decisions = receipt.get("stageDecisions")
    requirements = receipt.get("stageConfirmationRequirements")
    law.require(
        isinstance(decisions, list) and len(decisions) == len(stages),
        "ADMISSION_DENOMINATOR_INCOMPLETE",
        "the admission receipt does not carry one decision per stage",
    )
    law.require(
        isinstance(requirements, list) and len(requirements) == len(stages),
        "ADMISSION_DENOMINATOR_INCOMPLETE",
        "the admission receipt does not carry one confirmation requirement per stage",
    )
    by_stage = {row["stage"]: row for row in requirements}
    seen: set[str] = set()
    authorizations: list[dict[str, Any]] = []
    for index, stage in enumerate(stages):
        decision = decisions[index]
        law.require(
            decision["stage"] == stage and decision["sequence"] == index + 1,
            "ADMISSION_DECISION_ORDER_INVALID",
            "the admitted decisions are not in the sixteen-stage denominator order",
        )
        law.require(
            decision["decisionCode"] == "RECORD_STAGE",
            "STAGE_NOT_ADMITTED_FOR_RECORDING",
            f"the named human did not admit {stage} for recording",
        )
        confirmation_id = law.assert_content_id(
            decision["stageConfirmationId"], "ADMISSION_DECISION_INVALID", f"{stage} stage confirmation identity"
        )
        law.require(
            confirmation_id not in seen,
            "STAGE_CONFIRMATION_REPLAYED",
            f"one stage confirmation identity is bound to more than one stage: {stage}",
        )
        seen.add(confirmation_id)
        requirement = by_stage[stage]
        law.require(
            requirement["evidenceAdmissionRootFinal"] is True
            and requirement["confirmationInvitable"] is True,
            "STAGE_ROOT_NOT_FINAL",
            f"{stage} was confirmed against a root the gate did not report as final",
        )
        law.require(
            decision["evidenceAdmissionRoot"] == requirement["evidenceAdmissionRoot"]
            and decision["observationDigest"] == requirement["observationDigest"]
            and decision["requiredTerminal"] == requirement["requiredTerminal"]
            and decision["requiredTerminal"] == admission["stages"][stage]["requiredTerminal"],
            "STAGE_DECISION_BINDING_INVALID",
            f"{stage} decision does not bind the root, observation and terminal the gate published",
        )
        authorizations.append(
            {
                "stage": stage,
                "admissionId": receipt[profile["admissionProfile"]["receiptIdKey"]],
                "stageConfirmationId": confirmation_id,
                "evidenceAdmissionRoot": decision["evidenceAdmissionRoot"],
                "observationDigest": decision["observationDigest"],
                "requiredTerminal": decision["requiredTerminal"],
                "controlQuestion": requirement["controlQuestion"],
            }
        )
    return authorizations


# --------------------------------------------------------------------------------
# the materialized evidence denominator
# --------------------------------------------------------------------------------


def load_materialization_receipt(
    *,
    profile: Mapping[str, Any],
    admission: Mapping[str, Any],
    path: Path,
    receipt: Mapping[str, Any],
    packet: Mapping[str, Any],
    campaign_id: str,
) -> Mapping[str, Any]:
    """Require the separately authenticated bridge between admitted roles and packet bodies.

    This orchestrator does not replay the candidate workspace itself. It requires a receipt
    from a verifier that did, re-identifies it, and binds it to the same admission receipt,
    request, packet, campaign and admission root the gate published. A hand-written receipt
    cannot survive: its identity is over its own complete body, including all forty-three
    role rows.
    """
    law_block = profile["evidenceMaterialization"]
    codes = law_block["refusalCodes"]
    # A role row is a member of one authenticated receipt. Nothing here reads a row until
    # the complete parent receipt has re-identified and bound itself to this campaign,
    # packet, request and admission root.
    law.require(
        law_block["rowClass"] == "receipt-subordinate",
        "PROFILE_INVALID",
        "the profile does not classify materialized evidence rows as receipt-subordinate",
    )
    law.require(path.is_file(), codes["absent"], "no evidence-materialization receipt was supplied")
    body = law.read_json_file(path, code=codes["invalid"], label="evidence materialization receipt")
    law.exact_keys(body, law_block["keys"], codes["invalid"], "evidence materialization receipt")
    law.require(
        body["schema"] == law_block["schema"] and body["status"] == law_block["requiredStatus"],
        codes["invalid"],
        "evidence materialization receipt schema or status differs",
    )
    law.require(
        body["profileId"] == law.PROFILE_ID
        and body["admissionProfileId"] == profile["admissionProfile"]["profileId"],
        codes["invalid"],
        "the materialization receipt was issued under another profile succession",
    )
    law.assert_identity(
        body, law_block["idKey"], law_block["idPrefix"], codes["invalid"], "evidence materialization receipt"
    )
    law.require(
        body["authority"] == law.AUTHORITY,
        "AUTHORITY_WIDENED",
        "evidence materialization receipt grants authority",
    )

    receipt_id_key = profile["admissionProfile"]["receiptIdKey"]
    law.require(
        body["admissionId"] == receipt[receipt_id_key]
        and body["requestId"] == receipt["requestId"]
        and body["packetId"] == packet["marker"]["packetId"]
        and body["campaignId"] == campaign_id
        and body["canonicalMissionStateDigest"] == packet["config"]["canonicalMissionStateDigest"]
        and body["successorContractId"] == packet["successorContractId"]
        and body["evidenceAdmissionDigestRoot"] == receipt["evidenceAdmissionDigestRoot"],
        codes["binding"],
        "the materialization receipt does not bind this admission receipt, request, packet and admission root",
    )

    denominator = profile["denominator"]
    law.require(
        body["evidenceRoleDenominator"] == denominator["evidenceRoleDenominator"]
        and body["materializedRoleCount"] == denominator["evidenceRoleDenominator"]
        and body["nonHumanEvidenceRoleCount"] == denominator["nonHumanEvidenceRoleCount"]
        and body["humanStatementRoleCount"] == denominator["humanStatementRoleCount"],
        codes["denominator"],
        "the materialization receipt does not carry the admitted forty-three-role denominator",
    )
    law.require(
        body["extraEvidenceRoleCount"] == 0
        and body["missingEvidenceRoleCount"] == 0
        and body["duplicateBodyIdentityCount"] == 0,
        codes["denominator"],
        "the materialization receipt reports extra, missing or duplicated evidence roles",
    )

    stages = law.stage_sequence(admission)
    sequence_by_stage = {stage: index + 1 for index, stage in enumerate(stages)}
    rows = body["roles"]
    law.require(
        isinstance(rows, list) and len(rows) == denominator["evidenceRoleDenominator"],
        codes["denominator"],
        "the materialization receipt does not carry one row per admitted evidence role",
    )
    destinations: set[str] = set()
    for row in rows:
        law.exact_keys(row, law_block["roleRowKeys"], codes["invalid"], "materialized evidence role row")
        law.require(row["stage"] in stages, codes["binding"], "a materialized role names an unknown stage")
        # A row carried over to another stage keeps the sequence of the stage it was
        # admitted for, so the two are required to agree.
        law.require(
            row["sequence"] == sequence_by_stage[row["stage"]],
            codes["binding"],
            f"a materialized role names {row['stage']} at another stage's sequence",
        )
        law.assert_content_id(row["bodyContentId"], codes["invalid"], "materialized body identity")
        law.assert_sha256(row["bodySha256"], codes["invalid"], "materialized body digest")
        law.assert_content_id(
            row["evidenceAdmissionRoot"], codes["invalid"], "materialized stage evidence-admission root"
        )
        # Every retained provenance column is required to be present exactly when its
        # provenance class calls for it. Retention that nothing checks is a column a
        # hand-written receipt can null out, so each one is load-bearing here.
        provenance = row["provenanceClass"]
        law.require(
            (row["sourceReceiptId"] is not None) == (provenance == "accepted_predecessor_receipt")
            and (row["reuseClass"] is not None) == (provenance == "accepted_predecessor_receipt")
            and (row["sourceObservationId"] is not None) == (provenance == "current_local_observation")
            and (row["bodySchema"] is None) == (row["opaqueInstrumentClass"] is not None)
            and (row["instrumentReceiptId"] is not None) == (row["opaqueInstrumentClass"] is not None)
            and (row["instrumentReceiptDestination"] is not None) == (row["opaqueInstrumentClass"] is not None),
            codes["invalid"],
            f"a materialized {provenance} role does not retain the provenance its class requires",
        )
        for destination in (row["packetDestination"], row["instrumentReceiptDestination"]):
            if destination is None:
                continue
            law.require(
                law.RELATIVE_MEMBER_RE.fullmatch(destination) is not None and "\\" not in destination,
                codes["destinationInvalid"],
                f"materialized packet coordinate is not an admitted relative member: {destination}",
            )
            law.require(
                destination not in destinations,
                codes["destinationInvalid"],
                f"two materialized bodies claim one packet coordinate: {destination}",
            )
            destinations.add(destination)
    law.require(
        body["physicalBodyCount"] == len(destinations),
        codes["destinationInvalid"],
        "the materialization receipt's physical body count is not the set of coordinates it names",
    )

    bindings = body["statementBindings"]
    law.require(
        isinstance(bindings, list) and len(bindings) == denominator["humanStatementRoleCount"],
        codes["statementBinding"],
        "the materialization receipt does not bind three named-human statements",
    )
    for binding in bindings:
        law.exact_keys(
            binding, law_block["statementBindingKeys"], codes["statementBinding"], "named-human statement binding"
        )
        law.assert_content_id(binding["statementId"], codes["statementBinding"], "named-human statement identity")
    return body


def materialize_stage_evidence(
    *, profile: Mapping[str, Any], packet: Path, candidates: Path, role_rows: Sequence[Mapping[str, Any]]
) -> int:
    """Copy exactly the admitted bodies into their deterministic packet coordinates.

    Every stage evidence directory must be empty first. A directory that already holds a
    file is refused here, before a single stage record exists: a body nobody admitted
    would otherwise be hashed into the stage record, counted as private evidence, and
    sealed beside a root that never covered it.
    """
    codes = profile["evidenceMaterialization"]["refusalCodes"]
    directories = sorted({str(Path(row["packetDestination"]).parent.as_posix()) for row in role_rows})
    for relative in directories:
        directory = packet / relative
        law.require(
            directory.is_dir(),
            codes["destinationInvalid"],
            f"the packet has no evidence directory at {relative}",
        )
        existing = sorted(entry.name for entry in directory.iterdir())
        if existing:
            law.fail(
                codes["unmaterializedEvidence"],
                f"{relative} already holds evidence this transaction did not admit: {existing[0]}",
            )

    written = 0
    for row in role_rows:
        pairs = [(row["candidateBodyPath"], row["packetDestination"], row["bodySha256"], row["bodyBytes"])]
        if row["instrumentReceiptDestination"] is not None:
            pairs.append(
                (
                    row["instrumentReceiptPath"],
                    row["instrumentReceiptDestination"],
                    row["instrumentReceiptSha256"],
                    row["instrumentReceiptBytes"],
                )
            )
        for source_relative, destination_relative, digest, size in pairs:
            source = law.validate_lexical_coordinate(
                candidates / source_relative, label="admitted evidence body", code=codes["bodySubstituted"]
            )
            law.require(
                law.is_within(source, candidates),
                codes["bodySubstituted"],
                f"an admitted body escapes the candidate workspace: {source_relative}",
            )
            data = law.read_bounded_bytes(
                source,
                law.MAX_EVIDENCE_BYTES,
                code=codes["bodySubstituted"],
                label=f"admitted evidence body {source_relative}",
            )
            law.require(
                law.sha256_bytes(data) == digest and len(data) == size,
                codes["bodySubstituted"],
                f"the candidate body changed since it was admitted: {source_relative}",
            )
            destination = law.validate_lexical_coordinate(
                packet / destination_relative, label="packet evidence coordinate", code=codes["destinationInvalid"]
            )
            law.require(
                law.is_within(destination, packet),
                codes["destinationInvalid"],
                f"a materialized coordinate escapes the packet: {destination_relative}",
            )
            law.require(
                not destination.exists(),
                codes["destinationInvalid"],
                f"a materialized coordinate already exists: {destination_relative}",
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("wb") as handle:
                handle.write(data)
            written += 1
    return written


# --------------------------------------------------------------------------------
# the closed named-human authentication interface (issue #94)
# --------------------------------------------------------------------------------


def verify_named_human_authentication(
    *,
    profile: Mapping[str, Any],
    admission: Mapping[str, Any],
    path: Path,
    receipt: Mapping[str, Any],
    packet: Mapping[str, Any],
    campaign_id: str,
    campaign_label: str,
    authorizations: list[dict[str, Any]],
    statement_bindings: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any]:
    """Require a separate receipt that a human principal actually acted.

    This orchestrator never reads ``authenticationBinding`` or ``actorClass`` as proof.
    Both are text supplied by the same body that declares them, so a machine can write
    either. The interface below is what issue #94 must satisfy; this source exercises it
    with a synthetic fixture that authenticates nobody.
    """
    law_block = profile["humanAuthentication"]
    codes = law_block["refusalCodes"]
    law.require(path.is_file(), codes["absent"], "no named-human authentication verification receipt was supplied")
    body = law.read_json_file(path, code=codes["binding"], label="named-human authentication receipt")
    law.exact_keys(body, law_block["receiptKeys"], codes["binding"], "named-human authentication receipt")
    law.require(
        body["schema"] == law_block["receiptSchema"],
        codes["binding"],
        "named-human authentication receipt schema differs",
    )
    law.assert_identity(
        body,
        law_block["receiptIdKey"],
        law_block["receiptIdPrefix"],
        codes["binding"],
        "named-human authentication receipt",
    )
    law.require(
        body["principalClass"] == law_block["requiredPrincipalClass"],
        codes["binding"],
        "named-human authentication receipt does not name a named-human principal",
    )
    law.require(
        body["authority"] == law.AUTHORITY, "AUTHORITY_WIDENED", "named-human authentication receipt grants authority"
    )
    law.assert_unix_ns(body["verifiedAtUnixNs"], codes["binding"], "authentication verification coordinate")
    law.assert_bounded_text(body["mechanismId"], codes["binding"], "authentication mechanism identity", 256)

    # A synthetic mechanism may only ever authenticate a synthetic campaign. This is the
    # wall that keeps a source fixture from reaching a live campaign.
    if body["mechanismId"] == law_block["syntheticMechanismId"]:
        law.require(
            campaign_label.startswith(law_block["syntheticCampaignLabelPrefix"]),
            codes["syntheticAppliedToCampaign"],
            "the synthetic authentication fixture may not be applied to a live campaign",
        )

    law.require(
        body["admissionId"] == receipt[profile["admissionProfile"]["receiptIdKey"]]
        and body["packetId"] == packet["marker"]["packetId"]
        and body["campaignId"] == campaign_id,
        codes["binding"],
        "the authentication receipt does not bind this admission receipt, packet and campaign",
    )

    # ---- all sixteen confirmations, exactly ---------------------------------------
    expected_confirmations = sorted(row["stageConfirmationId"] for row in authorizations)
    confirmations = body["confirmationIds"]
    law.require(
        isinstance(confirmations, list) and sorted(confirmations) == expected_confirmations,
        codes["incomplete"],
        "the authentication receipt does not authenticate the exact sixteen stage confirmations",
    )

    # ---- all three statements, one per statement-owing stage -----------------------
    statement_stages = [
        stage
        for stage in law.stage_sequence(admission)
        if admission["stages"][stage]["availabilityClass"] == "REQUIRES_HUMAN_STATEMENT"
    ]
    law.require(
        len(statement_stages) == profile["denominator"]["humanStatementRoleCount"],
        "ADMISSION_DENOMINATOR_INVALID",
        "the admitted profile does not declare three statement-owing stages",
    )
    statements = body["statementIds"]
    law.require(
        isinstance(statements, list)
        and len(statements) == len(statement_stages)
        and len(set(statements)) == len(statements),
        codes["incomplete"],
        "the authentication receipt does not authenticate three distinct named-human statements",
    )
    # The admission receipt publishes every evidence identity a stage admitted, not which
    # of them is the named-human statement, so membership in that set proves only that an
    # identity belongs to the stage -- it could be the stage's accepted receipt or its
    # current observation. The materialization bridge derived the exact statement of each
    # statement-owing stage from the admitted provenance class, and this binds to that.
    bindings_by_stage = {row["stage"]: row for row in statement_bindings}
    law.require(
        sorted(bindings_by_stage) == sorted(statement_stages),
        codes["incomplete"],
        "the materialized statement bindings do not cover exactly the statement-owing stages",
    )
    law.require(
        sorted(statements) == sorted(row["statementId"] for row in statement_bindings),
        codes["incomplete"],
        "the authentication receipt does not authenticate the exact named-human statement of each "
        "statement-owing stage",
    )
    for stage in statement_stages:
        binding = bindings_by_stage[stage]
        law.require(
            binding["evidenceAdmissionRoot"] == next(
                row["evidenceAdmissionRoot"] for row in authorizations if row["stage"] == stage
            ),
            codes["binding"],
            f"the {stage} statement binds another evidence-admission root than the authorized one",
        )

    # ---- and every one of them was actually authenticated ---------------------------
    authenticated = body["authenticatedStatementIds"]
    law.require(
        isinstance(authenticated, list) and sorted(authenticated) == sorted(statements),
        codes["incomplete"],
        "the authentication receipt names statements it did not authenticate",
    )
    return body


# --------------------------------------------------------------------------------
# orchestration
# --------------------------------------------------------------------------------


def read_packet_lineage(profile: Mapping[str, Any], packet: Path) -> dict[str, Any]:
    lineage_law = profile["lineage"]
    contract = law.read_json_file(
        packet / profile["packet"]["files"]["successorContract"],
        code="SUCCESSOR_CONTRACT_INVALID",
        label="successor contract",
    )
    law.exact_keys(
        contract, lineage_law["successorContractKeys"], "SUCCESSOR_CONTRACT_INVALID", "successor contract"
    )
    law.assert_identity(
        contract,
        lineage_law["successorContractIdKey"],
        lineage_law["successorContractIdPrefix"],
        "SUCCESSOR_CONTRACT_INVALID",
        "successor contract",
    )
    return {
        "successorContractId": contract[lineage_law["successorContractIdKey"]],
        "successorSourceSetId": contract["successorSourceSetId"],
        "packetHandoffId": contract["packetHandoffId"],
        "predecessorPacketId": contract["predecessorPacketId"],
        "campaignId": contract["campaignId"],
        "campaignLabel": contract["campaignLabel"],
    }


def orchestrate(
    *,
    packet: Path,
    admission_receipt: Path,
    materialization_receipt: Path,
    authentication_receipt: Path,
    candidates: Path,
    repository: Path,
    profile_path: Path = PROFILE_PATH,
) -> dict[str, Any]:
    law.require_supported_python()
    packet = law.validate_lexical_coordinate(packet, label="packet root", code="PACKET_ROOT_INVALID")
    repository = law.validate_lexical_coordinate(repository, label="repository root", code="SOURCE_ROOT_INVALID")
    profile = law.load_profile(
        law.validate_lexical_coordinate(profile_path, label="successor flight profile", code="PROFILE_UNREADABLE")
    )
    admission = law.load_admission_profile(repository, profile)

    loaded = law.load_packet(profile, packet)
    lineage = read_packet_lineage(profile, packet)
    law.require(
        lineage["campaignLabel"] == loaded["marker"]["campaignLabel"],
        "SUCCESSOR_CONTRACT_INVALID",
        "the successor contract belongs to another campaign than the packet",
    )
    surface = {**loaded, **lineage}

    receipt = load_admission_receipt(
        profile=profile,
        path=law.validate_lexical_coordinate(
            admission_receipt, label="admission receipt", code="ADMISSION_RECEIPT_INVALID"
        ),
        packet=surface,
        campaign_id=lineage["campaignId"],
    )
    authorizations = stage_authorizations(profile=profile, admission=admission, receipt=receipt)
    candidates = law.validate_lexical_coordinate(
        candidates, label="candidate evidence workspace", code="CANDIDATE_WORKSPACE_INVALID"
    )
    law.require(
        not law.is_within(candidates, packet),
        profile["evidenceMaterialization"]["refusalCodes"]["invalid"],
        "the candidate evidence workspace may not live inside the packet it feeds",
    )
    materialization = load_materialization_receipt(
        profile=profile,
        admission=admission,
        path=law.validate_lexical_coordinate(
            materialization_receipt,
            label="evidence materialization receipt",
            code=profile["evidenceMaterialization"]["refusalCodes"]["absent"],
        ),
        receipt=receipt,
        packet=surface,
        campaign_id=lineage["campaignId"],
    )
    roles_by_stage: dict[str, list[Mapping[str, Any]]] = {}
    for row in materialization["roles"]:
        roles_by_stage.setdefault(row["stage"], []).append(row)
    # Every stage root is reconstructed from the materialized rows here, before a single
    # body is copied and long before a stage is recorded. Doing it only inside the
    # recorder would let a row rebound in stage fourteen pass while stages one to thirteen
    # were already written; a rebinding anywhere must refuse with the packet untouched.
    for index, authorization in enumerate(authorizations):
        stage = authorization["stage"]
        stage_rows = roles_by_stage.get(stage, [])
        law.require(
            bool(stage_rows)
            and all(
                row["evidenceAdmissionRoot"] == authorization["evidenceAdmissionRoot"] for row in stage_rows
            ),
            profile["evidenceMaterialization"]["refusalCodes"]["stageRootMismatch"],
            f"{stage} materialized roles do not carry the evidence-admission root the named human decided over",
        )
        law.require(
            len(stage_rows) == admission["stages"][stage]["evidenceRoleDenominator"],
            profile["evidenceMaterialization"]["refusalCodes"]["denominator"],
            f"{stage} did not materialize its admitted evidence-role denominator",
        )
        law.require(
            law.stage_evidence_root(
                admission,
                scope=law.ALL_ROLES_SCOPE,
                sequence=index + 1,
                stage=stage,
                rows=stage_rows,
            )
            == authorization["evidenceAdmissionRoot"],
            profile["evidenceMaterialization"]["refusalCodes"]["stageRootMismatch"],
            f"{stage} evidence-admission root reconstructed from the materialized roles differs "
            "from the root the named human decided over",
        )
    authentication = verify_named_human_authentication(
        profile=profile,
        admission=admission,
        path=law.validate_lexical_coordinate(
            authentication_receipt,
            label="named-human authentication receipt",
            code=profile["humanAuthentication"]["refusalCodes"]["absent"],
        ),
        receipt=receipt,
        packet=surface,
        campaign_id=lineage["campaignId"],
        campaign_label=lineage["campaignLabel"],
        authorizations=authorizations,
        statement_bindings=materialization["statementBindings"],
    )

    law.require(
        loaded["state"]["completedStageCount"] == 0,
        "PACKET_STAGES_ALREADY_RECORDED",
        "this orchestrator records a packet that begins at zero of sixteen",
    )

    materialized_bodies = materialize_stage_evidence(
        profile=profile, packet=packet, candidates=candidates, role_rows=materialization["roles"]
    )
    law.require(
        materialized_bodies == materialization["physicalBodyCount"],
        profile["evidenceMaterialization"]["refusalCodes"]["denominator"],
        "the materialized body count differs from the count the materialization receipt names",
    )

    recorded: list[dict[str, Any]] = []
    terminal_counts = {"PASS": 0, "HUMAN_REQUIRED": 0, "REFUSED": 0}
    for authorization in authorizations:
        result = runtime.record_stage(
            profile=profile,
            admission=admission,
            packet=packet,
            stage=authorization["stage"],
            authorization=authorization,
            role_rows=roles_by_stage[authorization["stage"]],
        )
        record = result["record"]
        terminal_counts[record["terminalState"]] += 1
        recorded.append(
            {
                "sequence": record["sequence"],
                "stage": record["stage"],
                "terminalState": record["terminalState"],
                "recordDigest": record[profile["packet"]["stageRecord"]["idKey"]],
                "stageConfirmationId": record["stageConfirmationId"],
                "evidenceAdmissionRoot": record["evidenceAdmissionRoot"],
                "observationDigest": record["observationDigest"],
                "evidenceBodyCount": len(record["evidenceFiles"]),
            }
        )

    expected_terminals = profile["denominator"]["recordedTerminalCounts"]
    law.require(
        terminal_counts == expected_terminals,
        "RECORDED_TERMINAL_DENOMINATOR_INVALID",
        "the recorded terminal denominator differs from the admitted denominator",
    )

    final = law.load_packet(profile, packet)["state"]
    law.require(
        final["completedStageCount"] == profile["denominator"]["stageDenominator"]
        and final["nextStage"] is None
        and final["sealed"] is False,
        "PACKET_INCOMPLETE",
        "the packet did not reach exact sixteen of sixteen unsealed",
    )

    body = {
        "schema": ORCHESTRATION_SCHEMA,
        "status": "PASS",
        "profileId": law.PROFILE_ID,
        "admissionId": receipt[profile["admissionProfile"]["receiptIdKey"]],
        "admissionProfileId": profile["admissionProfile"]["profileId"],
        "admissionTerminal": receipt["terminal"],
        "admissionBootstrapAuthenticated": True,
        "authenticationVerificationId": authentication[
            profile["humanAuthentication"]["receiptIdKey"]
        ],
        "authenticationMechanismId": authentication["mechanismId"],
        "campaignId": lineage["campaignId"],
        "campaignLabel": lineage["campaignLabel"],
        "canonicalMissionStateDigest": loaded["config"]["canonicalMissionStateDigest"],
        "packetId": loaded["marker"]["packetId"],
        "packetProfileId": loaded["marker"]["packetProfileId"],
        "successorContractId": lineage["successorContractId"],
        "successorSourceSetId": lineage["successorSourceSetId"],
        "packetHandoffId": lineage["packetHandoffId"],
        "predecessorPacketId": lineage["predecessorPacketId"],
        "evidenceRoleDenominator": profile["denominator"]["evidenceRoleDenominator"],
        "nonHumanEvidenceRoleDenominator": profile["denominator"]["nonHumanEvidenceRoleCount"],
        "humanStatementRoleDenominator": profile["denominator"]["humanStatementRoleCount"],
        "stageConfirmationDenominator": profile["denominator"]["stageConfirmationDenominator"],
        "evidenceAdmissionDigestRoot": receipt["evidenceAdmissionDigestRoot"],
        "materializationReceiptId": materialization[profile["evidenceMaterialization"]["idKey"]],
        "materializedEvidenceRoleCount": materialization["materializedRoleCount"],
        "materializedPrivateEvidenceBodyCount": materialized_bodies,
        "namedHumanStatementBindings": [
            {"stage": row["stage"], "evidenceRole": row["evidenceRole"], "statementId": row["statementId"]}
            for row in materialization["statementBindings"]
        ],
        "unadmittedEvidenceBodiesRecorded": 0,
        "completedStageCount": final["completedStageCount"],
        "recordedTerminalCounts": terminal_counts,
        "recordedStages": recorded,
        "stateId": final[profile["packet"]["stateIdKey"]],
        "sealed": False,
        "sealedDispositionId": None,
        "operatorConfirmedFlagsRead": 0,
        "selfAssertedActorClassesTrusted": 0,
        "predecessorPacketMutated": False,
        "physicalEstateQualified": False,
        "representativeOperatorQualified": False,
        "fieldNetworkQualified": False,
        "operationalC2Qualified": False,
        "productionLatticeQualified": False,
        "missionAuthorityGranted": False,
        "commandAuthorityGranted": False,
        "authority": law.AUTHORITY,
        "claimBoundary": ORCHESTRATION_CLAIM,
    }
    return law.sign(body, ORCHESTRATION_ID_KEY, ORCHESTRATION_ID_PREFIX)


def refusal_document(code: str, message: str) -> dict[str, Any]:
    return {
        "schema": ORCHESTRATION_SCHEMA,
        "status": "REFUSED",
        "code": code,
        "message": message,
        "sealed": False,
        "operatorConfirmedFlagsRead": 0,
        "selfAssertedActorClassesTrusted": 0,
        "predecessorPacketMutated": False,
        "authority": law.AUTHORITY,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Record one successor packet from a bootstrap-authenticated admission receipt"
    )
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--admission-receipt", type=Path, required=True)
    parser.add_argument("--materialization-receipt", type=Path, required=True)
    parser.add_argument("--authentication-receipt", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=HERE.parent.parent)
    parser.add_argument("--out", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        receipt = orchestrate(
            packet=args.packet,
            admission_receipt=args.admission_receipt,
            materialization_receipt=args.materialization_receipt,
            authentication_receipt=args.authentication_receipt,
            candidates=args.candidates,
            repository=args.repository_root,
        )
        data = law.canonical_json_bytes(receipt)
        if args.out is None:
            sys.stdout.buffer.write(data)
        else:
            out = law.validate_lexical_coordinate(
                args.out, label="orchestration receipt output", code="RECEIPT_PATH_INVALID"
            )
            law.require(
                not law.is_within(out, args.packet.resolve(strict=False)),
                "RECEIPT_INSIDE_MEASURED_SURFACE",
                "the orchestration receipt may not be written inside the packet",
            )
            law.require(not out.exists(), "RECEIPT_OUTPUT_EXISTS", "receipt output must not already exist")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
        return 0
    except law.SuccessorFlightError as exc:
        sys.stdout.buffer.write(law.canonical_json_bytes(refusal_document(exc.code, str(exc))))
        return 1
    except (OSError, ValueError) as exc:
        sys.stdout.buffer.write(
            law.canonical_json_bytes(refusal_document("ORCHESTRATOR_FILESYSTEM_ERROR", str(exc)))
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
