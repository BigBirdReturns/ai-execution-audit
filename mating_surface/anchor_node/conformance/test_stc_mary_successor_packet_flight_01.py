"""Permanent witnesses for the STC MARY successor packet flight 01 source set.

Every fixture in this file is synthetic. No live campaign identity, no private coordinate
and no real evidence body appears here. The campaign labels carry the SYNTHETIC- prefix
the source set requires, and the only human-authentication mechanism exercised is the
synthetic fixture, which authenticates nobody.

The centrepiece is one executable traversal that begins where the transaction requires it
to begin -- a configured 0.1 predecessor at zero of sixteen -- and walks the entire legal
order: compile, verify under measured-source bootstrap, admit through the separately
admitted packet-evidence-admission@2 gate and its own bootstrap, authenticate, record
sixteen stages in sequence, close pre-seal, seal, verify detached, close post-seal.

Constructing the completed final state directly would prove nothing about order, so the
traversal is built once per class and every ordering claim is asserted against what the
walk actually produced.

The evidence the packet carries is the admitted evidence and nothing else. The traversal
runs the evidence-materialization bridge over the same candidate workspace the admitted
gate measured, materializes exactly the forty-three admitted bodies into deterministic
per-role coordinates, and every stage evidence-admission root in the packet is
reconstructed from those bodies rather than copied from the receipt.

The hostile witnesses prove that a self-confirmed draft, a draft describing its own
evidence class, an unauthenticated confirmation, an out-of-order stage, an unbootstrapped
admission receipt, a synthetic authentication receipt aimed at a live campaign, a pre-seal
object carrying a post-seal assertion, a post-seal closure over an unsealed packet, and --
the one this transaction exists to refuse -- a packet carrying generic bodies beside a
forty-three-role root are all incapable of manufacturing a completed flight.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import atexit
import copy
from pathlib import Path
from typing import Any, Mapping
from unittest import mock

ANCHOR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ANCHOR.parent.parent
if str(ANCHOR) not in sys.path:
    sys.path.insert(0, str(ANCHOR))

import stc_mary_successor_flight_law as law  # noqa: E402
import invoke_stc_mary_successor_packet_source as execution_launcher  # noqa: E402
import invoke_stc_mary_successor_packet_source_bootstrap as execution_bootstrap  # noqa: E402
import stc_mary_successor_packet_compiler as compiler  # noqa: E402
import stc_mary_successor_packet_orchestrator as orchestrator  # noqa: E402
import stc_mary_successor_packet_runtime as runtime  # noqa: E402
import stc_mary_successor_seal_adapter as seal_adapter  # noqa: E402
import verify_stc_mary_successor_evidence_materialization as materialization_bridge  # noqa: E402
import verify_stc_mary_successor_execution_receipt as execution_receipt_verifier  # noqa: E402
import verify_stc_mary_successor_packet as packet_verifier  # noqa: E402
import verify_stc_mary_successor_post_seal_closure as post_seal  # noqa: E402
import verify_stc_mary_successor_pre_seal_closure as pre_seal  # noqa: E402
import verify_stc_mary_successor_source_admission as source_admission  # noqa: E402
import verify_stc_mary_successor_source_admission_bootstrap as source_bootstrap  # noqa: E402

PROFILE = ANCHOR / "stc-mary-successor-packet-flight-01-profile-01.json"
WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "stc-mary-successor-packet-flight-01.yml"

ADMISSION_PROFILE = ANCHOR / "stc-mary-packet-evidence-admission-profile-01.json"
ADMISSION_BOOTSTRAP = ANCHOR / "verify_stc_mary_packet_evidence_admission_bootstrap.py"

SYNTHETIC_CAMPAIGN_LABEL = "SYNTHETIC-SUCCESSOR-FLIGHT-WITNESS-01"
LIVE_CAMPAIGN_LABEL = "STC-MARY-CAMPAIGN-A"

RECEIPT = "accepted_predecessor_receipt"
CURRENT = "current_local_observation"
HUMAN = "named_human_statement"

EVIDENCE_CLASS_BY_PROVENANCE = {
    RECEIPT: "private_instrument_receipt",
    CURRENT: "private_local_attestation",
    HUMAN: "private_operator_statement",
}

TRANSACTION_START = 1_800_000_000_000_000_000
TRANSACTION_END = TRANSACTION_START + 3_600_000_000_000


def cid(prefix: str, body: Any) -> str:
    return law.content_id(prefix, body)


def sign(body: dict, id_key: str, prefix: str) -> dict:
    return {**body, id_key: cid(prefix, body)}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, indent=2) + "\n")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), *arguments], check=True, capture_output=True, text=True
    )
    return completed.stdout.strip()


def build_source_repository(root: Path, profile: Mapping[str, Any]) -> tuple[Path, str]:
    """Commit the current synthetic source fixture, then trust only its Git objects."""
    repository = root / "source-repository"
    repository.mkdir(parents=True)
    subprocess.run(["git", "init", "--quiet", "--initial-branch=main", str(repository)], check=True)
    git(repository, "config", "user.name", "STC MARY synthetic fixture")
    git(repository, "config", "user.email", "synthetic@example.invalid")
    git(repository, "config", "core.autocrlf", "false")

    tracked = subprocess.check_output(
        ["git", "-C", str(REPOSITORY_ROOT), "ls-files", "-z"]
    ).split(b"\0")
    paths = {raw.decode("utf-8") for raw in tracked if raw}
    paths.update(profile["successorSourceMembers"])
    for relative in sorted(paths):
        source = REPOSITORY_ROOT / relative
        if not source.is_file():
            continue
        destination = repository / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    git(repository, "add", "--all")
    git(repository, "commit", "--quiet", "-m", "synthetic exact-source fixture")
    return repository, git(repository, "rev-parse", "HEAD")


def synthetic_observation(stage: str, contract: dict) -> dict:
    """Build one observation that satisfies the admitted stage contract exactly."""
    observation: dict[str, Any] = {}
    for key in contract["keys"]:
        if key in contract.get("requiredValues", {}):
            observation[key] = contract["requiredValues"][key]
        elif key in contract.get("contentIdFields", []):
            observation[key] = cid("syntheticobservationdigest1", {"stage": stage, "field": key})
        elif key in contract.get("sha256Fields", []):
            observation[key] = sha256_text(f"{stage}:{key}")
        elif key in contract.get("boundedStringFields", []):
            observation[key] = f"synthetic-{key}"
        elif key in contract.get("integerFields", {}):
            observation[key] = contract["integerFields"][key][0]
        elif key in contract.get("enumFields", {}):
            observation[key] = contract["enumFields"][key][0]
        elif key in contract.get("uniqueStringArrayFields", {}):
            count = contract["uniqueStringArrayFields"][key]
            observation[key] = [f"synthetic-{key}-{index}" for index in range(count)]
        elif key in contract.get("exactStringArrayFields", {}):
            observation[key] = list(contract["exactStringArrayFields"][key])
        else:  # pragma: no cover - the admitted contract denominator is closed
            raise AssertionError(f"unhandled observation field {stage}.{key}")
    return observation


# --------------------------------------------------------------------------------
# one complete synthetic estate, walked in legal order
# --------------------------------------------------------------------------------


class SuccessorFlightWalk:
    """Drive the whole admitted order once, recording what each step produced."""

    def __init__(self, root: Path, *, campaign_label: str = SYNTHETIC_CAMPAIGN_LABEL) -> None:
        self.root = root
        self.campaign_label = campaign_label
        self.profile = load_json(PROFILE)
        self.admission_profile = load_json(ADMISSION_PROFILE)
        self.stages = list(self.admission_profile["stageSequence"])

        self.workstation = root / "workstation"
        self.predecessor = root / "campaign" / "stc-mary-private-flight-predecessor"
        self.packet = root / "campaign" / "stc-mary-private-flight-successor"
        self.candidates = root / "admission"
        self.receipts = root / "receipts"
        self.sealed = root / "campaign" / "stc-mary-private-flight-sealed-witness"

        self.canonical_mission_state_digest = sha256_text(f"canonical-mission-state:{campaign_label}")
        self.campaign_id = cid("stcmaryflightconductorcampaign1", {"campaignLabel": campaign_label})
        self.predecessor_coordinate = cid(
            "stcmaryflightconductoracceptedpredecessor1", {"campaignLabel": campaign_label}
        )
        self.non_human_roots: dict[str, str] = {}

    # -- step 0: the frozen conductor surface the admitted gate reads -----------
    def build_workstation(self) -> None:
        ws_law = self.admission_profile["workstation"]
        body = {
            "schema": ws_law["markerSchema"],
            "profileId": ws_law["conductorProfileId"],
            "campaignId": self.campaign_id,
            "campaignLabel": self.campaign_label,
            "createdAtUnixNs": TRANSACTION_START - 10_000_000_000_000,
            "configId": cid("stcmaryflightconductorconfig1", {"campaignLabel": self.campaign_label}),
            "pathMapId": cid("stcmaryflightconductorpathmap1", {"campaignLabel": self.campaign_label}),
            "sourceSetId": cid("stcmaryflightconductorsourceset1", {"campaignLabel": self.campaign_label}),
            "authority": "none",
            "claimBoundary": "Synthetic conductor marker for conformance only. It grants no authority.",
        }
        write_json(
            self.workstation / ws_law["markerFile"],
            sign(body, ws_law["markerIdKey"], ws_law["markerIdPrefix"]),
        )

    # -- step 1: a configured 0.1 predecessor at zero of sixteen ----------------
    def materialize_predecessor(self) -> dict:
        return compiler.materialize_synthetic_predecessor(
            profile=law.load_profile(PROFILE),
            packet=self.predecessor,
            campaign_label=self.campaign_label,
            canonical_mission_state_digest=self.canonical_mission_state_digest,
        )

    # -- step 2: compile the distinct 0.2 successor ------------------------------
    def compile(self) -> dict:
        self.predecessor_fence_before = self.fence(self.predecessor)
        self.source_repository, self.source_commit = build_source_repository(self.root, self.profile)
        self.source_admission_path = self.receipts / "source-admission.json"
        self.source_admission = source_bootstrap.authenticate(
            repository=self.source_repository, source_commit=self.source_commit
        )
        law.write_canonical_json(self.source_admission_path, self.source_admission)
        compile_result_path = self.receipts / "compile.json"
        compile_execution_path = self.receipts / "compile-execution-custody.json"
        execution_bootstrap.execute(
            role="compile",
            execution_receipt=compile_execution_path,
            repository=self.source_repository,
            source_admission_receipt=self.source_admission_path,
            packet=None,
            module_args=[
                "compile",
                "--workstation", str(self.workstation),
                "--predecessor", str(self.predecessor),
                "--successor", str(self.packet),
                "--repository-root", str(self.source_repository),
                "--source-admission-receipt", str(self.source_admission_path),
                "--out", str(compile_result_path),
            ],
        )
        self.compile_execution_receipt = load_json(compile_execution_path)
        receipt = load_json(compile_result_path)
        self.predecessor_fence_after = self.fence(self.predecessor)
        self.compile_receipt = receipt
        self.packet_id = receipt["successorPacketId"]
        return receipt

    def fence(self, root: Path) -> dict[str, str]:
        return {
            path.relative_to(root).as_posix(): law.sha256_bytes(path.read_bytes())
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }

    # -- step 3: verify the compiled packet under measured-source bootstrap ------
    def verify_packet(self) -> dict:
        out = self.receipts / "successor-packet-verification.json"
        execution_path = self.receipts / "verify-packet-execution.json"
        execution_bootstrap.execute(
            role="verify-packet",
            execution_receipt=execution_path,
            packet=self.packet,
            repository=None,
            source_admission_receipt=None,
            module_args=[
                "--packet",
                str(self.packet),
                "--profile",
                str(PROFILE),
                "--repository-root",
                str(self.source_repository),
                "--out",
                str(out),
            ],
        )
        self.verify_packet_execution_receipt = load_json(execution_path)
        self.packet_verification = load_json(out)
        return self.packet_verification

    # -- step 4: the admission workspace, for the separately admitted gate -------
    def evidence_body(self, stage: str, sequence: int, role_law: dict, stage_law: dict) -> dict:
        provenance = role_law["provenanceClass"]
        schema_law = self.admission_profile["bodySchemas"][provenance]
        body: dict[str, Any] = {
            "schema": schema_law["schema"],
            "campaignId": self.campaign_id,
            "packetId": self.packet_id,
            "stage": stage,
            "sequence": sequence,
            "evidenceRole": role_law["evidenceRole"],
            "canonicalMissionStateDigest": self.canonical_mission_state_digest,
            "provenanceClass": provenance,
            "semanticPredicates": dict(role_law["requiredPredicates"]),
            "authority": "none",
            "claimBoundary": "Synthetic evidence body for conformance only. It grants no authority.",
        }
        if provenance == RECEIPT:
            body.update(
                {
                    "sourceReceiptId": self.receipt_id(stage, role_law),
                    "sourceCampaignId": self.campaign_id,
                    "acceptedPredecessorCoordinate": self.predecessor_coordinate,
                    "reuseClass": schema_law["requiredReuseClass"],
                    "capturedAtUnixNs": TRANSACTION_START - 60_000_000_000,
                }
            )
        elif provenance == CURRENT:
            body.update(
                {
                    "sourceObservationId": cid(
                        "syntheticsourceobservation1", {"stage": stage, "role": role_law["evidenceRoleKey"]}
                    ),
                    "observationTransactionId": self.transaction_id,
                    "capturedAtUnixNs": TRANSACTION_START + 1_000_000_000,
                    "claimsHistoricalTransition": False,
                }
            )
        else:
            conflict = stage == self.admission_profile["bodySchemas"][HUMAN]["conflictStage"]
            observation = self.observations[stage]
            binding = self.admission_profile["bodySchemas"][HUMAN]["evidenceAdmissionBinding"]
            body.update(
                {
                    "actorClass": schema_law["requiredActorClass"],
                    "statementScope": f"Named-human statement for the {stage} stage of one synthetic packet.",
                    "acceptedEvidenceIds": [],
                    "nonHumanEvidenceAdmissionRoot": self.non_human_roots.get(
                        stage, cid(binding["rootPrefix"], {"unmeasured": stage})
                    ),
                    "terminalOrRetainedObligation": stage_law["requiredTerminal"],
                    "issuedAtUnixNs": TRANSACTION_END + 1_000_000_000,
                    "authenticationBinding": "synthetic-local-named-human-authentication",
                    "retainedBranches": (
                        [observation["leftStateDigest"], observation["rightStateDigest"]] if conflict else []
                    ),
                    "selectedWinner": None,
                    "automaticMerge": False if conflict else None,
                }
            )
        return sign(body, schema_law["idKey"], schema_law["idPrefix"])

    def receipt_id(self, stage: str, role_law: dict) -> str:
        return cid("syntheticpredecessorreceipt1", {"stage": stage, "role": role_law["evidenceRoleKey"]})

    def stage_directory(self, sequence: int, stage: str) -> str:
        return f"bodies/{sequence:02d}-{stage}"

    def write_evidence(self, stage: str, sequence: int, role_law: dict, stage_law: dict) -> dict:
        body = self.evidence_body(stage, sequence, role_law, stage_law)
        schema_law = self.admission_profile["bodySchemas"][role_law["provenanceClass"]]
        relative = f"{self.stage_directory(sequence, stage)}/{role_law['evidenceRoleKey']}.json"
        path = self.candidates / relative
        write_json(path, body)
        data = path.read_bytes()
        return {
            "evidenceRole": role_law["evidenceRole"],
            "provenanceClass": role_law["provenanceClass"],
            "evidenceClass": EVIDENCE_CLASS_BY_PROVENANCE[role_law["provenanceClass"]],
            "mediaType": "application/json",
            "bodyPath": relative,
            "bodySha256": law.sha256_bytes(data),
            "bodyBytes": len(data),
            "bodySchema": schema_law["schema"],
            "bodyContentId": body[schema_law["idKey"]],
            "opaqueInstrumentClass": None,
            "instrumentReceiptPath": None,
            "authority": "none",
            "claimBoundary": "Synthetic evidence descriptor for conformance only. It grants no authority.",
        }

    def build_admission_workspace(self) -> None:
        transaction_law = self.admission_profile["observationTransaction"]
        self.transaction = sign(
            {
                "schema": transaction_law["schema"],
                "startedAtUnixNs": TRANSACTION_START,
                "endedAtUnixNs": TRANSACTION_END,
            },
            transaction_law["idKey"],
            transaction_law["idPrefix"],
        )
        self.transaction_id = self.transaction[transaction_law["idKey"]]
        self.observations = {
            stage: synthetic_observation(stage, self.admission_profile["stages"][stage]["observation"])
            for stage in self.stages
        }

        receipt_ids: list[str] = []
        rows: list[dict[str, Any]] = []
        for index, stage in enumerate(self.stages):
            sequence = index + 1
            stage_law = self.admission_profile["stages"][stage]
            descriptors = []
            for role_law in stage_law["evidenceRoles"]:
                if role_law["provenanceClass"] == HUMAN:
                    continue  # unsupplied at READY, by design
                if role_law["provenanceClass"] == RECEIPT:
                    receipt_ids.append(self.receipt_id(stage, role_law))
                descriptors.append(self.write_evidence(stage, sequence, role_law, stage_law))
            rows.append(
                {
                    "sequence": sequence,
                    "stage": stage,
                    "availabilityClass": stage_law["availabilityClass"],
                    "observation": self.observations[stage],
                    "evidence": descriptors,
                }
            )
        request = {
            "schema": self.admission_profile["request"]["schema"],
            "campaignId": self.campaign_id,
            "packetId": self.packet_id,
            "canonicalMissionStateDigest": self.canonical_mission_state_digest,
            "observationTransaction": self.transaction,
            "acceptedPredecessorGraph": [
                {
                    "acceptedPredecessorCoordinate": self.predecessor_coordinate,
                    "campaignId": self.campaign_id,
                    "sourceReceiptIds": sorted(set(receipt_ids)),
                }
            ],
            "stages": rows,
            "stageConfirmations": [],
            "batchConfirmation": None,
            "authority": "none",
            "claimBoundary": "Synthetic admission request for conformance only. It grants no authority.",
        }
        self.write_request(request)

    def request_path(self) -> Path:
        return self.candidates / self.admission_profile["request"]["fileName"]

    def write_request(self, request: dict) -> dict:
        law_block = self.admission_profile["request"]
        request.pop(law_block["idKey"], None)
        signed = sign(request, law_block["idKey"], law_block["idPrefix"])
        write_json(self.request_path(), signed)
        return signed

    def load_request(self) -> dict:
        return load_json(self.request_path())

    def stage_row(self, request: dict, stage: str) -> dict:
        return next(row for row in request["stages"] if row["stage"] == stage)

    def run_admission(self, name: str) -> dict:
        """Run the separately admitted gate through its own bootstrap."""
        out = self.receipts / name
        with tempfile.TemporaryDirectory(prefix="stc-mary-admission-foreign-") as foreign:
            completed = subprocess.run(
                [
                    sys.executable, "-I", "-S", "-B",
                    str(ADMISSION_BOOTSTRAP),
                    "--workstation", str(self.workstation),
                    "--packet", str(self.packet),
                    "--candidates", str(self.candidates),
                    "--profile", str(ADMISSION_PROFILE),
                    "--admission-source-root", str(self.source_repository),
                    "--out", str(out),
                ],
                cwd=foreign,
                env=execution_launcher.scrubbed_environment(),
                check=False,
                capture_output=True,
            )
        if completed.returncode != 0:
            raise AssertionError(
                f"admission bootstrap refused: {completed.stdout.decode('utf-8', 'replace')}"
            )
        return load_json(out)

    def add_human_statements(self, pending: dict) -> None:
        self.non_human_roots = {
            row["stage"]: row["nonHumanEvidenceAdmissionRoot"] for row in pending["humanStatementRequirements"]
        }
        request = self.load_request()
        for index, stage in enumerate(self.stages):
            sequence = index + 1
            stage_law = self.admission_profile["stages"][stage]
            for role_law in stage_law["evidenceRoles"]:
                if role_law["provenanceClass"] != HUMAN:
                    continue
                descriptor = self.write_evidence(stage, sequence, role_law, stage_law)
                row = self.stage_row(request, stage)
                accepted = sorted(entry["bodyContentId"] for entry in row["evidence"])
                path = self.candidates / descriptor["bodyPath"]
                body = load_json(path)
                schema_law = self.admission_profile["bodySchemas"][HUMAN]
                body["acceptedEvidenceIds"] = accepted
                body.pop(schema_law["idKey"], None)
                body = sign(body, schema_law["idKey"], schema_law["idPrefix"])
                write_json(path, body)
                data = path.read_bytes()
                descriptor["bodySha256"] = law.sha256_bytes(data)
                descriptor["bodyBytes"] = len(data)
                descriptor["bodyContentId"] = body[schema_law["idKey"]]
                row["evidence"].append(descriptor)
                self.statement_ids = getattr(self, "statement_ids", [])
                self.statement_ids.append(descriptor["bodyContentId"])
        self.write_request(request)

    def add_stage_confirmations(self, pending: dict) -> None:
        law_block = self.admission_profile["confirmation"]
        confirmations = []
        for requirement in pending["stageConfirmationRequirements"]:
            body = {
                "schema": law_block["schema"],
                "campaignId": self.campaign_id,
                "packetId": self.packet_id,
                "sequence": requirement["sequence"],
                "stage": requirement["stage"],
                "requiredTerminal": requirement["requiredTerminal"],
                "evidenceAdmissionRoot": requirement["evidenceAdmissionRoot"],
                "observationDigest": requirement["observationDigest"],
                "decisionCode": "RECORD_STAGE",
                "controlQuestionResponse": f"Yes, for {requirement['stage']}, on the admitted evidence root.",
                "actorClass": law_block["requiredActorClass"],
                "issuedAtUnixNs": TRANSACTION_END + 2_000_000_000,
                "authenticationBinding": "synthetic-local-named-human-authentication",
                "authority": "none",
                "claimBoundary": "Synthetic stage confirmation for conformance only. It grants no authority.",
            }
            confirmations.append(sign(body, law_block["idKey"], law_block["idPrefix"]))
        request = self.load_request()
        request["stageConfirmations"] = confirmations
        self.write_request(request)
        self.confirmation_ids = [row[law_block["idKey"]] for row in confirmations]

    # -- step 5: the synthetic named-human authentication fixture ---------------
    def write_authentication_receipt(
        self, *, admission_receipt: Mapping[str, Any], name: str = "authentication.json", **overrides: Any
    ) -> Path:
        law_block = self.profile["humanAuthentication"]
        body = {
            "schema": law_block["receiptSchema"],
            "mechanismId": law_block["syntheticMechanismId"],
            "principalClass": law_block["requiredPrincipalClass"],
            "admissionId": admission_receipt[self.profile["admissionProfile"]["receiptIdKey"]],
            "packetId": self.packet_id,
            "campaignId": self.campaign_id,
            "statementIds": sorted(self.statement_ids),
            "authenticatedStatementIds": sorted(self.statement_ids),
            "confirmationIds": sorted(self.confirmation_ids),
            "verifiedAtUnixNs": TRANSACTION_END + 4_000_000_000,
            "authority": "none",
            "claimBoundary": (
                "Synthetic named-human authentication fixture for source qualification only. "
                "It authenticates no real person and may not be applied to a live campaign."
            ),
        }
        body.update(overrides)
        signed = sign(body, law_block["receiptIdKey"], law_block["receiptIdPrefix"])
        path = self.receipts / name
        write_json(path, signed)
        return path

    # -- step 6: bridge the admitted roles to packet coordinates ------------------
    def run_materialization(self, name: str = "evidence-materialization.json") -> dict:
        """Replay the admitted candidate-body mapping into one exact materialization receipt."""
        self.materialization_path = self.receipts / name
        execution_path = self.receipts / "materialize-or-resume-execution.json"
        execution_bootstrap.execute(
            role="materialize-or-resume",
            execution_receipt=execution_path,
            packet=self.packet,
            repository=None,
            source_admission_receipt=None,
            module_args=[
                "--packet", str(self.packet),
                "--admission-receipt", str(self.receipts / "admission-admissible.json"),
                "--candidates", str(self.candidates),
                "--repository-root", str(self.source_repository),
                "--profile", "@profile",
                "--transaction-workspace", str(self.receipts / "materialization-transaction"),
                "--out", str(self.materialization_path),
            ],
        )
        self.materialization_execution_receipt_path = execution_path
        self.materialization_execution_receipt = load_json(execution_path)
        return load_json(self.materialization_path)

    # -- step 7: draft each stage, then record it -------------------------------
    def write_stage_drafts(self, admission_receipt: Mapping[str, Any]) -> list[dict]:
        profile = law.load_profile(PROFILE)
        admission = law.load_admission_profile(self.source_repository, profile)
        authorizations = orchestrator.stage_authorizations(
            profile=profile, admission=admission, receipt=admission_receipt
        )
        state = law.load_packet(profile, self.packet)["state"]
        for index, stage in enumerate(self.stages):
            authorization = authorizations[index]
            draft = runtime.build_stage_draft(
                profile=profile,
                admission=admission,
                sequence=index + 1,
                stage=stage,
                observation=self.observations[stage],
                canonical_mission_state_digest=self.canonical_mission_state_digest,
                stage_confirmation_id=authorization["stageConfirmationId"],
            )
            row = state["stages"][index]
            law.write_canonical_json(self.packet / row["draftPath"], draft)
        # No evidence body is written here. A draft proposes an observation; the bodies a
        # stage records are materialized from the admitted set by the orchestrator, and a
        # file this fixture invented would be refused before the first stage is recorded.
        return authorizations

    # -- the whole order, once ---------------------------------------------------
    def walk(self) -> "SuccessorFlightWalk":
        self.build_workstation()
        self.predecessor_objects = self.materialize_predecessor()
        self.compile()
        self.verify_packet()
        self.build_admission_workspace()

        self.ready_receipt = self.run_admission("admission-ready.json")
        self.add_human_statements(self.ready_receipt)
        self.held_receipt = self.run_admission("admission-held.json")
        self.add_stage_confirmations(self.held_receipt)
        self.admission_receipt = self.run_admission("admission-admissible.json")

        self.authentication_path = self.write_authentication_receipt(admission_receipt=self.admission_receipt)
        self.materialization_receipt = self.run_materialization()
        self.authorizations = self.write_stage_drafts(self.admission_receipt)

        # The estate is copied here, drafted and bridged but with zero stages recorded, so
        # the hostile witnesses can attack the recording step itself without paying for a
        # second admission.
        self.pre_record_snapshot = self.root.parent / "snapshot-pre-record"
        shutil.copytree(self.root, self.pre_record_snapshot)

        orchestration_path = self.receipts / "orchestration.json"
        recording_execution_path = self.receipts / "record-or-resume-execution.json"
        execution_bootstrap.execute(
            role="record-or-resume",
            execution_receipt=recording_execution_path,
            packet=self.packet,
            repository=None,
            source_admission_receipt=None,
            module_args=[
                "--packet", str(self.packet),
                "--admission-receipt", str(self.receipts / "admission-admissible.json"),
                "--materialization-receipt", str(self.materialization_path),
                "--authentication-receipt", str(self.authentication_path),
                "--candidates", str(self.candidates),
                "--repository-root", str(self.source_repository),
                "--transaction-workspace", str(self.receipts / "recording-transactions"),
                "--out", str(orchestration_path),
            ],
        )
        self.recording_execution_receipt_path = recording_execution_path
        self.recording_execution_receipt = load_json(recording_execution_path)
        self.orchestration_receipt = load_json(orchestration_path)
        self.pre_seal_path = self.receipts / "pre-seal-closure.json"
        self.pre_seal_execution_receipt_path = self.receipts / "close-pre-seal-execution.json"
        execution_bootstrap.execute(
            role="close-pre-seal",
            execution_receipt=self.pre_seal_execution_receipt_path,
            packet=self.packet,
            repository=None,
            source_admission_receipt=None,
            module_args=[
                "--packet", str(self.packet),
                "--admission-receipt", str(self.receipts / "admission-admissible.json"),
                "--materialization-receipt", str(self.materialization_path),
                "--authentication-receipt", str(self.authentication_path),
                "--candidates", str(self.candidates),
                "--profile", "@profile",
                "--repository-root", str(self.source_repository),
                "--out", str(self.pre_seal_path),
            ],
        )
        self.pre_seal_execution_receipt = load_json(self.pre_seal_execution_receipt_path)
        self.pre_seal_closure = load_json(self.pre_seal_path)

        # The estate is copied here, at the one moment it is closed but unsealed, so the
        # hostile witnesses can attack that state without paying for a second traversal.
        self.pre_seal_snapshot = self.root.parent / "snapshot-pre-seal"
        shutil.copytree(self.root, self.pre_seal_snapshot)

        seal_receipt_path = self.receipts / "seal.json"
        seal_execution_path = self.receipts / "seal-or-resume-execution.json"
        execution_bootstrap.execute(
            role="seal-or-resume",
            execution_receipt=seal_execution_path,
            packet=self.packet,
            repository=None,
            source_admission_receipt=None,
            module_args=[
                "seal",
                "--packet", str(self.packet),
                "--sealed", str(self.sealed),
                "--pre-seal-closure", str(self.pre_seal_path),
                "--pre-seal-execution-receipt", str(self.pre_seal_execution_receipt_path),
                "--admission-receipt", str(self.receipts / "admission-admissible.json"),
                "--materialization-receipt", str(self.materialization_path),
                "--authentication-receipt", str(self.authentication_path),
                "--candidates", str(self.candidates),
                "--repository-root", str(self.source_repository),
                "--out", str(seal_receipt_path),
            ],
        )
        self.seal_execution_receipt_path = seal_execution_path
        self.seal_execution_receipt = load_json(seal_execution_path)
        self.seal_result = seal_adapter.seal_packet(
            packet=self.packet,
            sealed=self.sealed,
            pre_seal_closure=self.pre_seal_path,
            pre_seal_execution_receipt=self.pre_seal_execution_receipt_path,
            admission_receipt=self.receipts / "admission-admissible.json",
            materialization_receipt=self.materialization_path,
            authentication_receipt=self.authentication_path,
            candidates=self.candidates,
            repository=self.source_repository,
            source_execution_receipt=seal_execution_path,
        )
        self.detached_verification = seal_adapter.verify_detached(
            sealed=self.sealed, repository=self.source_repository
        )
        self.detached_path = self.receipts / "detached-verification.json"
        law.write_canonical_json(self.detached_path, self.detached_verification)

        self.post_seal_closure = post_seal.close_post_seal(
            packet=self.packet,
            sealed=self.sealed,
            pre_seal_closure=self.pre_seal_path,
            pre_seal_execution_receipt=self.pre_seal_execution_receipt_path,
            admission_receipt=self.receipts / "admission-admissible.json",
            materialization_receipt=self.materialization_path,
            authentication_receipt=self.authentication_path,
            candidates=self.candidates,
            detached_verification=self.detached_path,
            profile_path=PROFILE,
            repository=self.source_repository,
        )
        return self


# --------------------------------------------------------------------------------
# the one full legal-order traversal
# --------------------------------------------------------------------------------

_SHARED_WALK: SuccessorFlightWalk | None = None


def shared_walk() -> SuccessorFlightWalk:
    """Walk the whole admitted order exactly once for this process.

    Every class below asserts against the same traversal rather than rebuilding it, so
    the ordering claims and the hostile claims are made about one estate that really was
    produced in legal order.
    """
    global _SHARED_WALK
    if _SHARED_WALK is None:
        root = Path(tempfile.mkdtemp(prefix="stc-mary-successor-flight-"))
        atexit.register(shutil.rmtree, root, ignore_errors=True)
        _SHARED_WALK = SuccessorFlightWalk(root / "estate").walk()
    return _SHARED_WALK


def closure_replay_arguments(estate: Path) -> dict[str, Path]:
    """Coordinates sealing must replay and the measured closure receipt must bind."""
    receipts = estate / "receipts"
    return {
        "pre_seal_execution_receipt": receipts / "close-pre-seal-execution.json",
        "admission_receipt": receipts / "admission-admissible.json",
        "materialization_receipt": receipts / "evidence-materialization.json",
        "authentication_receipt": receipts / "authentication.json",
        "candidates": estate / "admission",
    }


class LegalOrderTraversal(unittest.TestCase):
    """One walk, built once, asserted many times.

    The walk begins at a configured 0.1 predecessor at zero of sixteen. Every claim below
    is asserted against what the traversal actually produced, never against a
    hand-constructed final state.
    """

    walk: SuccessorFlightWalk

    @classmethod
    def setUpClass(cls) -> None:
        cls.walk = shared_walk()

    # -- the beginning ---------------------------------------------------------
    def test_the_walk_begins_at_a_configured_predecessor_at_zero_of_sixteen(self) -> None:
        state = self.walk.predecessor_objects["state"]
        self.assertEqual(state["packetProfileId"], "stc-mary/private-flight-packet/0.1")
        self.assertEqual(state["configurationState"], "configured")
        self.assertEqual(state["completedStageCount"], 0)
        self.assertFalse(state["sealed"])
        self.assertEqual(len(state["stageDenominator"]), 16)

    def test_the_compiled_successor_is_distinct_from_its_predecessor(self) -> None:
        receipt = self.walk.compile_receipt
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["successorPacketProfileId"], "stc-mary/private-flight-packet/0.2")
        self.assertEqual(receipt["predecessorPacketProfileId"], "stc-mary/private-flight-packet/0.1")
        self.assertNotEqual(receipt["successorPacketId"], receipt["predecessorPacketId"])
        self.assertEqual(receipt["completedStageCount"], 0)
        self.assertEqual(receipt["stagesRecordedByThisSurface"], 0)
        self.assertEqual(receipt["authority"], "none")
        self.assertEqual(self.walk.compile_execution_receipt["operationRole"], "compile")
        self.assertEqual(self.walk.compile_execution_receipt["processTerminal"], "PASS")
        self.assertIsNone(self.walk.compile_execution_receipt["packetId"])

    def test_compilation_leaves_the_predecessor_byte_identical(self) -> None:
        self.assertEqual(self.walk.predecessor_fence_after, self.walk.predecessor_fence_before)
        self.assertFalse(self.walk.compile_receipt["predecessorMutated"])

    def test_the_successor_carries_every_declared_source_member(self) -> None:
        profile = self.walk.profile
        source_root = self.walk.packet / profile["lineage"]["sourceRoot"]
        for member in profile["successorSourceMembers"].values():
            self.assertTrue((source_root / member).is_file(), member)
        self.assertEqual(
            self.walk.compile_receipt["successorSourceMemberCount"],
            profile["successorSourceMemberDenominator"],
        )
        carried_admission = load_json(self.walk.packet / profile["lineage"]["sourceAdmissionFile"])
        self.assertEqual(carried_admission, self.walk.source_admission)
        self.assertEqual(
            carried_admission["successorSourceSetId"], self.walk.compile_receipt["successorSourceSetId"]
        )

    # -- independent verification ------------------------------------------------
    def test_the_compiled_packet_verifies_under_measured_source_bootstrap(self) -> None:
        verification = self.walk.packet_verification
        self.assertEqual(verification["status"], "PASS")
        self.assertTrue(verification["bootstrapAuthenticated"])
        self.assertEqual(verification["bootstrapVerifierSha256"], verification["measuredVerifierSha256"])
        self.assertEqual(verification["completedStageCount"], 0)
        self.assertEqual(verification["stageRecordsPresent"], 0)
        self.assertFalse(verification["sealed"])
        self.assertIn("measured-verifier-member-binding", verification["checks"])
        self.assertIn("source-admission-git-blob-members-bound", verification["checks"])
        self.assertEqual(verification["sourceAdmissionId"], self.walk.source_admission["sourceAdmissionId"])
        self.assertIn("packet-identity-derived-from-succession", verification["checks"])

    # -- admission, by the separately admitted gate --------------------------------
    def test_the_admitted_gate_reaches_admissible_for_this_exact_packet(self) -> None:
        receipt = self.walk.admission_receipt
        self.assertEqual(receipt["terminal"], "ADMISSIBLE_FOR_PACKET_RECORDING")
        self.assertTrue(receipt["bootstrapAuthenticated"])
        self.assertEqual(receipt["packetId"], self.walk.packet_id)
        self.assertEqual(receipt["admittedEvidenceRoleCount"], 43)
        self.assertEqual(receipt["admittedNonHumanEvidenceRoleCount"], 40)
        self.assertEqual(receipt["admittedHumanStatementCount"], 3)
        self.assertEqual(receipt["suppliedStageConfirmationCount"], 16)
        self.assertEqual(receipt["packetStagesRecorded"], 0)
        self.assertFalse(receipt["packetRecorderInvoked"])

    def test_the_admitted_gate_measured_the_lineage_this_packet_carries(self) -> None:
        receipt = self.walk.admission_receipt
        compile_receipt = self.walk.compile_receipt
        self.assertEqual(receipt["successorContractId"], compile_receipt["successorContractId"])
        self.assertEqual(receipt["successorSourceSetId"], compile_receipt["successorSourceSetId"])
        self.assertEqual(receipt["packetHandoffId"], compile_receipt["packetHandoffId"])
        self.assertEqual(receipt["predecessorPacketId"], compile_receipt["predecessorPacketId"])

    def test_the_ready_terminal_precedes_the_admissible_terminal(self) -> None:
        """The statements did not exist when the gate first published their roots."""
        self.assertEqual(self.walk.ready_receipt["terminal"], "READY_FOR_NAMED_HUMAN_DECISION")
        self.assertEqual(self.walk.ready_receipt["admittedHumanStatementCount"], 0)
        self.assertEqual(self.walk.held_receipt["terminal"], "HOLD")
        self.assertEqual(self.walk.held_receipt["admittedHumanStatementCount"], 3)
        self.assertEqual(self.walk.admission_receipt["terminal"], "ADMISSIBLE_FOR_PACKET_RECORDING")

    # -- recording ------------------------------------------------------------------
    def test_sixteen_stages_recorded_in_exact_sequence_order(self) -> None:
        receipt = self.walk.orchestration_receipt
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["completedStageCount"], 16)
        self.assertEqual(
            [row["stage"] for row in receipt["recordedStages"]], self.walk.stages
        )
        self.assertEqual(
            [row["sequence"] for row in receipt["recordedStages"]], list(range(1, 17))
        )

    def test_the_recorded_terminal_denominator_is_fifteen_one_zero(self) -> None:
        receipt = self.walk.orchestration_receipt
        self.assertEqual(receipt["recordedTerminalCounts"], {"PASS": 15, "HUMAN_REQUIRED": 1, "REFUSED": 0})

    def test_every_record_names_the_authenticated_confirmation_that_admitted_it(self) -> None:
        receipt = self.walk.orchestration_receipt
        recorded = {row["stageConfirmationId"] for row in receipt["recordedStages"]}
        self.assertEqual(recorded, set(self.walk.confirmation_ids))
        self.assertEqual(len(recorded), 16)

    def test_the_orchestrator_read_no_operator_confirmed_flag(self) -> None:
        receipt = self.walk.orchestration_receipt
        self.assertEqual(receipt["operatorConfirmedFlagsRead"], 0)
        self.assertEqual(receipt["selfAssertedActorClassesTrusted"], 0)
        self.assertFalse(receipt["predecessorPacketMutated"])

    def test_the_successor_stage_draft_schema_has_no_operator_boolean(self) -> None:
        keys = self.walk.profile["packet"]["stageDraft"]["keys"]
        self.assertNotIn("operatorConfirmed", keys)
        self.assertIn("stageConfirmationId", keys)

    # -- materialized evidence --------------------------------------------------------
    def test_the_bridge_materializes_every_admitted_evidence_role(self) -> None:
        """43 / 43, with nothing extra, nothing missing and nothing repeated."""
        receipt = self.walk.materialization_receipt
        denominator = self.walk.profile["denominator"]
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["materializedRoleCount"], 43)
        self.assertEqual(receipt["materializedRoleCount"], denominator["evidenceRoleDenominator"])
        self.assertEqual(receipt["nonHumanEvidenceRoleCount"], 40)
        self.assertEqual(receipt["humanStatementRoleCount"], 3)
        self.assertEqual(receipt["extraEvidenceRoleCount"], 0)
        self.assertEqual(receipt["missingEvidenceRoleCount"], 0)
        self.assertEqual(receipt["duplicateBodyIdentityCount"], 0)
        self.assertEqual(len(receipt["roles"]), 43)
        self.assertEqual(len({row["bodyContentId"] for row in receipt["roles"]}), 43)
        self.assertEqual(len({(row["stage"], row["evidenceRole"]) for row in receipt["roles"]}), 43)

    def test_the_bridge_reproduces_the_roots_the_gate_published(self) -> None:
        """The stage roots and the complete admission root are recomputed, not copied."""
        receipt = self.walk.materialization_receipt
        admitted = self.walk.admission_receipt
        self.assertEqual(
            receipt["evidenceAdmissionDigestRoot"], admitted["evidenceAdmissionDigestRoot"]
        )
        published = {row["stage"]: row["evidenceAdmissionRoot"] for row in admitted["stages"]}
        measured = {row["stage"]: row["evidenceAdmissionRoot"] for row in receipt["stages"]}
        self.assertEqual(measured, published)
        self.assertEqual(len(measured), 16)

    def test_every_admitted_role_occupies_its_own_packet_coordinate(self) -> None:
        receipt = self.walk.materialization_receipt
        destinations = [row["packetDestination"] for row in receipt["roles"]]
        self.assertEqual(len(set(destinations)), len(destinations))
        self.assertEqual(receipt["physicalBodyCount"], len(destinations))
        for row in receipt["roles"]:
            # The coordinate carries the role, so a body cannot be moved between roles
            # without moving the file the record hashes.
            self.assertTrue(
                row["packetDestination"].endswith(f"/{row['evidenceRoleKey']}.json"),
                row["packetDestination"],
            )
            self.assertTrue((self.walk.packet / row["packetDestination"]).is_file())

    def test_the_packet_carries_the_admitted_bodies_and_no_others(self) -> None:
        receipt = self.walk.materialization_receipt
        expected = {row["packetDestination"] for row in receipt["roles"]}
        present = {
            path.relative_to(self.walk.packet).as_posix()
            for path in self.walk.packet.glob("*/evidence/*")
            if path.is_file()
        }
        self.assertEqual(present, expected)
        for row in receipt["roles"]:
            candidate = (self.walk.candidates / row["candidateBodyPath"]).read_bytes()
            self.assertEqual((self.walk.packet / row["packetDestination"]).read_bytes(), candidate)

    def test_each_recorded_body_carries_its_own_role_and_provenance(self) -> None:
        by_destination = {
            row["packetDestination"]: row for row in self.walk.materialization_receipt["roles"]
        }
        seen = 0
        for record_path in sorted(self.walk.packet.glob("*/stage-record.json")):
            for evidence in load_json(record_path)["evidenceFiles"]:
                role_row = by_destination[evidence["relativePath"]]
                self.assertEqual(evidence["evidenceRole"], role_row["evidenceRole"])
                self.assertEqual(evidence["provenanceClass"], role_row["provenanceClass"])
                self.assertEqual(evidence["evidenceClass"], role_row["evidenceClass"])
                self.assertEqual(evidence["bodyContentId"], role_row["bodyContentId"])
                seen += 1
        self.assertEqual(seen, 43)

    def test_a_stage_of_mixed_provenance_is_not_flattened_to_one_class(self) -> None:
        """BIND_GRACE combines accepted receipts with a named-human statement.

        One draft-wide evidenceClass could not describe both, which is why the draft no
        longer carries one at all.
        """
        record = load_json(next(self.walk.packet.glob("03-BIND_GRACE/stage-record.json")))
        provenance = {row["provenanceClass"] for row in record["evidenceFiles"]}
        classes = {row["evidenceClass"] for row in record["evidenceFiles"]}
        self.assertIn("named_human_statement", provenance)
        self.assertGreater(len(provenance), 1)
        self.assertGreater(len(classes), 1)
        draft = load_json(next(self.walk.packet.glob("03-BIND_GRACE/stage-attestation.json")))
        self.assertNotIn("evidenceClass", draft)
        self.assertNotIn("mediaType", draft)

    def test_every_recorded_root_is_reconstructed_from_the_bodies_beside_it(self) -> None:
        """Recompute each stage root here, from the packet, and require the record to match."""
        profile = law.load_profile(PROFILE)
        admission = law.load_admission_profile(REPOSITORY_ROOT, profile)
        by_stage: dict[str, list[dict]] = {}
        for row in self.walk.materialization_receipt["roles"]:
            by_stage.setdefault(row["stage"], []).append(row)
        published = {row["stage"]: row["evidenceAdmissionRoot"] for row in self.walk.admission_receipt["stages"]}
        for index, stage in enumerate(self.walk.stages):
            record = load_json(
                next(self.walk.packet.glob(f"{index + 1:02d}-{stage}/stage-record.json"))
            )
            measured = law.stage_evidence_root(
                admission,
                scope=law.ALL_ROLES_SCOPE,
                sequence=index + 1,
                stage=stage,
                rows=by_stage[stage],
            )
            self.assertEqual(record["evidenceAdmissionRoot"], measured, stage)
            self.assertEqual(record["evidenceAdmissionRoot"], published[stage], stage)

    def test_the_three_statements_are_bound_to_an_exact_stage_and_role(self) -> None:
        bindings = self.walk.materialization_receipt["statementBindings"]
        self.assertEqual(len(bindings), 3)
        self.assertEqual(len({row["stage"] for row in bindings}), 3)
        by_stage = {row["stage"]: row for row in bindings}
        self.assertIn("BIND_GRACE", by_stage)
        self.assertIn("RESTORE_LINK_HOLD_CONFLICT", by_stage)
        authenticated = load_json(self.walk.authentication_path)["statementIds"]
        self.assertEqual(sorted(row["statementId"] for row in bindings), sorted(authenticated))
        # Each bound statement is that stage's named-human role, not merely an identity
        # the stage happened to admit.
        roles = {
            (row["stage"], row["evidenceRole"]): row
            for row in self.walk.materialization_receipt["roles"]
        }
        for binding in bindings:
            role_row = roles[(binding["stage"], binding["evidenceRole"])]
            self.assertEqual(role_row["provenanceClass"], "named_human_statement")
            self.assertEqual(role_row["bodyContentId"], binding["statementId"])

    def test_the_orchestration_receipt_reports_the_materialized_denominator(self) -> None:
        receipt = self.walk.orchestration_receipt
        self.assertEqual(
            receipt["materializationReceiptId"],
            self.walk.materialization_receipt["materializationReceiptId"],
        )
        self.assertEqual(receipt["materializedEvidenceRoleCount"], 43)
        self.assertEqual(receipt["materializedPrivateEvidenceBodyCount"], 43)
        self.assertEqual(receipt["unadmittedEvidenceBodiesRecorded"], 0)
        self.assertEqual(len(receipt["namedHumanStatementBindings"]), 3)
        self.assertEqual(sum(row["evidenceBodyCount"] for row in receipt["recordedStages"]), 43)

    # -- pre-seal closure -------------------------------------------------------------
    def test_pre_seal_closure_binds_the_authenticated_decisions_and_roots(self) -> None:
        closure = self.walk.pre_seal_closure
        self.assertEqual(closure["status"], "PASS")
        self.assertEqual(closure["completedStageCount"], 16)
        self.assertEqual(len(closure["humanStatementIds"]), 3)
        self.assertEqual(len(closure["stageConfirmationIds"]), 16)
        self.assertTrue(closure["unsealed"])
        self.assertTrue(closure["sealedRootAbsent"])
        self.assertTrue(closure["stageRecordIdentityRoot"].startswith("stcmarysuccessorstagerecordroot1_"))
        self.assertTrue(
            closure["preSealEvidenceManifestRoot"].startswith("stcmarysuccessorpresealevidencemanifest1_")
        )
        self.assertEqual(
            closure["evidenceAdmissionDigestRoot"], self.walk.admission_receipt["evidenceAdmissionDigestRoot"]
        )
        self.assertEqual(
            closure["materializationReceiptId"],
            self.walk.materialization_receipt["materializationReceiptId"],
        )
        self.assertEqual(closure["materializedEvidenceRoleCount"], 43)
        self.assertEqual(closure["privateEvidenceBodyCount"], 43)

    def test_pre_seal_closure_retains_two_distinct_conflict_branches(self) -> None:
        closure = self.walk.pre_seal_closure
        self.assertEqual(closure["conflictStage"], "RESTORE_LINK_HOLD_CONFLICT")
        self.assertEqual(len(closure["conflictRetainedBranchDigests"]), 2)
        self.assertEqual(len(set(closure["conflictRetainedBranchDigests"])), 2)

    def test_pre_seal_closure_asserts_nothing_about_a_post_seal_object(self) -> None:
        closure = self.walk.pre_seal_closure
        reserved = set(self.walk.profile["postSealClosure"]["requiredValues"])
        self.assertEqual(set(closure) & reserved, set())
        # The claim boundary is excluded on purpose: it is where the closure *denies*
        # asserting anything post-seal, so scanning it would match its own disclaimer.
        # The assertion surface is the fields.
        surface = json.dumps(
            {key: value for key, value in closure.items() if key != "claimBoundary"}
        ).lower()
        for token in (
            "sealed run",
            "detached verification",
            "sealedrunpresent",
            "detachedverificationstatus",
            "bodyfreepublicdisposition",
            "sealedmanifestvalid",
        ):
            self.assertNotIn(token, surface, token)
        for token in self.walk.profile["postSealClosure"]["reservedAssertions"]:
            self.assertNotIn(token.lower(), surface, token)

    # -- sealing and detached verification -----------------------------------------
    def test_the_sealed_result_is_body_free(self) -> None:
        disposition = self.walk.seal_result["disposition"]
        self.assertEqual(disposition["publicEvidenceBodyCount"], 0)
        self.assertEqual(disposition["stageCount"], 16)
        self.assertEqual(disposition["successfulStageCount"], 15)
        self.assertEqual(disposition["humanRequiredStageCount"], 1)
        serialized = json.dumps(disposition)
        self.assertNotIn(str(self.walk.packet), serialized)
        self.assertNotIn("bodies/", serialized)

    def test_the_sealed_run_names_the_pre_seal_closure_it_was_sealed_under(self) -> None:
        run = self.walk.seal_result["run"]
        self.assertEqual(
            run["preSealClosureId"], self.walk.pre_seal_closure["preSealClosureId"]
        )
        self.assertEqual(run["stageCount"], 16)
        self.assertEqual(
            run["privatePhysicalEvidenceBodyCount"],
            self.walk.materialization_receipt["physicalBodyCount"],
        )
        self.assertEqual(run["privatePhysicalEvidenceBodyCount"], 43)

    def test_detached_verification_reproduces_from_the_sealed_run_alone(self) -> None:
        verification = self.walk.detached_verification
        self.assertEqual(verification["status"], "PASS")
        self.assertTrue(verification["deterministicReceiptReplay"])
        stored = load_json(self.walk.sealed / "verification.json")
        self.assertEqual(law.canonical_json(stored), law.canonical_json(verification))

    # -- post-seal closure ------------------------------------------------------------
    def test_post_seal_closure_asserts_the_reserved_facts_from_measurement(self) -> None:
        closure = self.walk.post_seal_closure
        self.assertEqual(closure["status"], "PASS")
        self.assertTrue(closure["sealedRunPresent"])
        self.assertTrue(closure["dispositionPresent"])
        self.assertTrue(closure["bodyFreePublicDisposition"])
        self.assertTrue(closure["sealedManifestValid"])
        self.assertEqual(closure["detachedVerificationStatus"], "PASS")
        self.assertEqual(closure["publicEvidenceBodyCount"], 0)
        self.assertTrue(closure["privatePhysicalFlightCompleted"])
        self.assertEqual(closure["preSealClosureId"], self.walk.pre_seal_closure["preSealClosureId"])

    def test_completion_qualifies_nothing_stronger(self) -> None:
        closure = self.walk.post_seal_closure
        self.assertTrue(closure["allStrongerQualificationsFalse"])
        self.assertFalse(closure["missionAuthorityGranted"])
        self.assertFalse(closure["commandAuthorityGranted"])
        self.assertEqual(closure["authority"], "none")
        disposition = self.walk.seal_result["disposition"]
        for key in self.walk.profile["postSealClosure"]["strongerQualifications"]:
            self.assertFalse(disposition[key], key)

    def test_every_receipt_in_the_order_grants_no_authority(self) -> None:
        for name, receipt in (
            ("compile", self.walk.compile_receipt),
            ("verify", self.walk.packet_verification),
            ("admission", self.walk.admission_receipt),
            ("materialization", self.walk.materialization_receipt),
            ("orchestration", self.walk.orchestration_receipt),
            ("pre-seal", self.walk.pre_seal_closure),
            (
                "seal-transaction",
                load_json(
                    self.walk.sealed.parent
                    / f".{self.walk.sealed.name}.seal-transaction.json"
                ),
            ),
            ("detached", self.walk.detached_verification),
            ("post-seal", self.walk.post_seal_closure),
        ):
            self.assertEqual(receipt["authority"], "none", name)


# --------------------------------------------------------------------------------
# hostile witnesses
# --------------------------------------------------------------------------------


class RecordingConsentWitnesses(unittest.TestCase):
    """Recording consent has one channel, and nothing else may open it."""

    def setUp(self) -> None:
        self.profile = law.load_profile(PROFILE)
        self.admission = law.load_admission_profile(REPOSITORY_ROOT, self.profile)

    def test_a_draft_may_not_carry_a_self_declared_operator_boolean(self) -> None:
        draft = runtime.build_stage_draft(
            profile=self.profile,
            admission=self.admission,
            sequence=1,
            stage="VERIFY_INPUTS",
            observation=synthetic_observation(
                "VERIFY_INPUTS", self.admission["stages"]["VERIFY_INPUTS"]["observation"]
            ),
            canonical_mission_state_digest=sha256_text("canonical"),
            stage_confirmation_id=cid("stcmarypacketevidencestageconfirmation1", {"synthetic": True}),
        )
        widened = {**draft, "operatorConfirmed": True}
        with self.assertRaises(law.SuccessorFlightError) as caught:
            runtime.validate_stage_draft(
                profile=self.profile,
                admission=self.admission,
                draft=widened,
                stage="VERIFY_INPUTS",
                sequence=1,
                canonical_mission_state_digest=draft["canonicalMissionStateIdBefore"],
            )
        self.assertEqual(caught.exception.code, "STAGE_DRAFT_INVALID")

    def test_a_recording_authorization_must_name_its_own_stage(self) -> None:
        authorization = {
            "stage": "MOUNT_PERSONAL_FLOOR",
            "admissionId": cid("stcmarypacketevidenceadmission1", {"synthetic": True}),
            "stageConfirmationId": cid("stcmarypacketevidencestageconfirmation1", {"synthetic": True}),
            "evidenceAdmissionRoot": cid("stcmarypacketevidencestageroot1", {"synthetic": True}),
            "observationDigest": cid("stcmarypacketevidenceobservationdigest1", {"synthetic": True}),
            "requiredTerminal": "PASS",
            "controlQuestion": "synthetic control question",
        }
        with self.assertRaises(law.SuccessorFlightError) as caught:
            runtime.validate_authorization(authorization, stage="VERIFY_INPUTS")
        self.assertEqual(caught.exception.code, "RECORDING_AUTHORIZATION_INVALID")


class AdmissionReceiptWitnesses(unittest.TestCase):
    """The orchestrator consumes only what somebody else authenticated."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="stc-mary-successor-hostile-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.profile = law.load_profile(PROFILE)

    def test_a_self_signed_admission_receipt_is_refused(self) -> None:
        """A receipt the gate signed for itself never reaches the recorder."""
        receipt = {
            "schema": self.profile["admissionProfile"]["receiptSchema"],
            "status": "PASS",
            "profileId": self.profile["admissionProfile"]["profileId"],
            "terminal": "ADMISSIBLE_FOR_PACKET_RECORDING",
            "bootstrapAuthenticated": False,
        }
        path = self.tmp / "receipt.json"
        write_json(path, receipt)
        with self.assertRaises(law.SuccessorFlightError) as caught:
            orchestrator.load_admission_receipt(
                profile=self.profile,
                path=path,
                packet={"marker": {}, "state": {}, "config": {}},
                campaign_id=cid("stcmaryflightconductorcampaign1", {"synthetic": True}),
            )
        self.assertEqual(caught.exception.code, "ADMISSION_RECEIPT_NOT_BOOTSTRAP_AUTHENTICATED")

    def test_a_ready_terminal_is_not_a_recording_terminal(self) -> None:
        receipt = {
            "schema": self.profile["admissionProfile"]["receiptSchema"],
            "status": "PASS",
            "profileId": self.profile["admissionProfile"]["profileId"],
            "terminal": "READY_FOR_NAMED_HUMAN_DECISION",
            "bootstrapAuthenticated": True,
        }
        path = self.tmp / "ready.json"
        write_json(path, receipt)
        with self.assertRaises(law.SuccessorFlightError) as caught:
            orchestrator.load_admission_receipt(
                profile=self.profile,
                path=path,
                packet={"marker": {}, "state": {}, "config": {}},
                campaign_id=cid("stcmaryflightconductorcampaign1", {"synthetic": True}),
            )
        self.assertEqual(caught.exception.code, "ADMISSION_TERMINAL_INVALID")


class HumanAuthenticationInterfaceWitnesses(unittest.TestCase):
    """The interface issue #94 must satisfy, and the wall around the source fixture."""

    def setUp(self) -> None:
        self.profile = load_json(PROFILE)

    def test_the_interface_is_declared_closed_and_owned_by_issue_94(self) -> None:
        law_block = self.profile["humanAuthentication"]
        self.assertEqual(law_block["issue"], 94)
        self.assertEqual(law_block["requiredPrincipalClass"], "named_human")
        for key in ("statementIds", "authenticatedStatementIds", "confirmationIds", "admissionId", "packetId"):
            self.assertIn(key, law_block["receiptKeys"])

    def test_the_orchestrator_source_never_trusts_a_self_declared_actor_class(self) -> None:
        """The two text fields a machine can write are named only to be refused."""
        text = (ANCHOR / "stc_mary_successor_packet_orchestrator.py").read_text(encoding="utf-8")
        self.assertNotIn('body["actorClass"] ==', text)
        self.assertNotIn('receipt["authenticationBinding"]', text)
        self.assertIn("refuses to read either as proof", text)

    def test_campaign_application_is_held_by_the_profile(self) -> None:
        wall = self.profile["stopWall"]
        self.assertEqual(wall["campaignApplication"], "held")
        self.assertEqual(wall["liveCampaignLabelsAdmitted"], [])
        self.assertEqual(wall["requiredHumanAuthenticationMechanism"], "issue-94")

    def test_a_live_campaign_label_is_refused_at_materialization(self) -> None:
        with self.assertRaises(law.SuccessorFlightError) as caught:
            compiler.require_synthetic_campaign(self.profile, LIVE_CAMPAIGN_LABEL)
        self.assertEqual(caught.exception.code, "SYNTHETIC_AUTHENTICATION_APPLIED_TO_LIVE_CAMPAIGN")

    def test_a_synthetic_campaign_label_is_admitted(self) -> None:
        compiler.require_synthetic_campaign(self.profile, SYNTHETIC_CAMPAIGN_LABEL)


class ClosedEstateHostileWitnesses(unittest.TestCase):
    """Attacks on the estate the traversal actually produced.

    Each test works on a private copy, so one hostile mutation can never leak into
    another witness or into the positive traversal.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.walk = shared_walk()

    def copy_pre_seal_estate(self) -> Path:
        """A private copy of the estate at the closed-but-unsealed moment."""
        target = Path(tempfile.mkdtemp(prefix="stc-mary-successor-hostile-")) / "estate"
        self.addCleanup(shutil.rmtree, target.parent, ignore_errors=True)
        shutil.copytree(self.walk.pre_seal_snapshot, target)
        return target

    def copy_sealed_estate(self) -> Path:
        target = Path(tempfile.mkdtemp(prefix="stc-mary-successor-hostile-")) / "estate"
        self.addCleanup(shutil.rmtree, target.parent, ignore_errors=True)
        shutil.copytree(self.walk.root, target)
        return target

    def resign_authentication(self, estate: Path, mutate) -> Path:
        path = estate / "receipts" / "authentication.json"
        body = load_json(path)
        law_block = self.walk.profile["humanAuthentication"]
        body.pop(law_block["receiptIdKey"], None)
        mutate(body)
        write_json(path, sign(body, law_block["receiptIdKey"], law_block["receiptIdPrefix"]))
        return path

    def close_pre_seal(self, estate: Path) -> dict:
        return pre_seal.close_pre_seal(
            packet=estate / "campaign" / "stc-mary-private-flight-successor",
            admission_receipt=estate / "receipts" / "admission-admissible.json",
            materialization_receipt=estate / "receipts" / "evidence-materialization.json",
            authentication_receipt=estate / "receipts" / "authentication.json",
            candidates=estate / "admission",
            profile_path=PROFILE,
            repository=REPOSITORY_ROOT,
        )

    def external_seal_transaction(self, estate: Path) -> Path:
        path = estate.parent / "external-seal-transaction.json"
        law.write_canonical_json(path, self.walk.seal_result["transaction"])
        return path

    def close_post_seal(self, estate: Path) -> dict:
        return post_seal.close_post_seal(
            packet=estate / "campaign" / "stc-mary-private-flight-successor",
            sealed=estate / "campaign" / "stc-mary-private-flight-sealed-witness",
            pre_seal_closure=estate / "receipts" / "pre-seal-closure.json",
            pre_seal_execution_receipt=estate / "receipts" / "close-pre-seal-execution.json",
            admission_receipt=estate / "receipts" / "admission-admissible.json",
            materialization_receipt=estate / "receipts" / "evidence-materialization.json",
            authentication_receipt=estate / "receipts" / "authentication.json",
            candidates=estate / "admission",
            detached_verification=estate / "receipts" / "detached-verification.json",
            profile_path=PROFILE,
            repository=REPOSITORY_ROOT,
        )

    def rewrite_disposition(self, estate: Path, mutate) -> tuple[Path, Path]:
        """Re-sign every subordinate binding so only disposition semantics remain hostile."""
        sealed = estate / "campaign" / "stc-mary-private-flight-sealed-witness"
        packet = estate / "campaign" / "stc-mary-private-flight-successor"
        seal_law = self.walk.profile["seal"]
        packet_law = self.walk.profile["packet"]

        def resign(path: Path, id_key: str, prefix: str, change) -> dict:
            body = load_json(path)
            body.pop(id_key, None)
            change(body)
            signed = sign(body, id_key, prefix)
            law.write_canonical_json(path, signed)
            return signed

        disposition = resign(
            sealed / seal_law["files"]["disposition"],
            seal_law["dispositionIdKey"],
            seal_law["dispositionIdPrefix"],
            mutate,
        )
        disposition_id = disposition[seal_law["dispositionIdKey"]]
        verification = resign(
            sealed / seal_law["files"]["verification"],
            seal_law["verificationIdKey"],
            seal_law["verificationIdPrefix"],
            lambda body: body.update({"dispositionId": disposition_id}),
        )
        resign(
            sealed / seal_law["files"]["marker"],
            seal_law["markerIdKey"],
            seal_law["markerIdPrefix"],
            lambda body: body.update({"dispositionId": disposition_id}),
        )
        law.write_canonical_json(estate / "receipts" / "detached-verification.json", verification)

        def refence_manifest(body: dict) -> None:
            body["dispositionId"] = disposition_id
            body["files"] = [
                {
                    "path": name,
                    "bytes": len((sealed / name).read_bytes()),
                    "sha256": law.sha256_bytes((sealed / name).read_bytes()),
                }
                for name in seal_law["manifestFiles"]
            ]

        manifest = resign(
            sealed / seal_law["files"]["manifest"],
            seal_law["manifestIdKey"],
            seal_law["manifestIdPrefix"],
            refence_manifest,
        )
        state = resign(
            packet / packet_law["files"]["state"],
            packet_law["stateIdKey"],
            packet_law["stateIdPrefix"],
            lambda body: body.update({"sealedDispositionId": disposition_id}),
        )
        transaction_path = sealed.parent / f".{sealed.name}.seal-transaction.json"

        def rebind_transaction(body: dict) -> None:
            body.update(
                {
                    "status": "sealed_state_promoted",
                    "proposedSealedStateId": state[packet_law["stateIdKey"]],
                    "dispositionId": disposition_id,
                    "manifestId": manifest[seal_law["manifestIdKey"]],
                    "postSealClosureId": None,
                }
            )

        resign(
            transaction_path,
            seal_law["transaction"]["idKey"],
            seal_law["transaction"]["idPrefix"],
            rebind_transaction,
        )
        return sealed, packet

    def rewrite_closure_and_producer(self, estate: Path, mutate) -> tuple[Path, Path]:
        """Forge both self-consistent objects so deterministic replay must cause refusal."""
        closure_path = estate / "receipts" / "pre-seal-closure.json"
        closure_law = self.walk.profile["preSealClosure"]
        closure = load_json(closure_path)
        closure.pop(closure_law["idKey"], None)
        mutate(closure)
        closure = sign(closure, closure_law["idKey"], closure_law["idPrefix"])
        law.write_canonical_json(closure_path, closure)
        data = closure_path.read_bytes()

        receipt_path = estate / "receipts" / "close-pre-seal-execution.json"
        custody = self.walk.profile["executionCustody"]
        receipt = load_json(receipt_path)
        receipt.pop(custody["idKey"], None)
        receipt.update(
            {
                "outputArtifactId": closure[closure_law["idKey"]],
                "outputArtifactSha256": law.sha256_bytes(data),
                "outputArtifactBytes": len(data),
            }
        )
        law.write_canonical_json(receipt_path, sign(receipt, custody["idKey"], custody["idPrefix"]))
        return closure_path, receipt_path

    def rewrite_sealed_flight(
        self,
        estate: Path,
        *,
        mutate_run=lambda body: None,
        mutate_disposition=lambda body: None,
        mutate_marker=lambda body: None,
        mutate_verification=lambda body: None,
        mutate_manifest=lambda body: None,
    ) -> tuple[Path, Path]:
        """Re-sign and re-manifest a hostile sealed flight through every dependent identity."""
        sealed = estate / "campaign" / "stc-mary-private-flight-sealed-witness"
        packet = estate / "campaign" / "stc-mary-private-flight-successor"
        seal_law = self.walk.profile["seal"]
        packet_law = self.walk.profile["packet"]

        def rewrite(path: Path, id_key: str, prefix: str, change) -> dict:
            body = load_json(path)
            body.pop(id_key, None)
            change(body)
            value = sign(body, id_key, prefix)
            law.write_canonical_json(path, value)
            return value

        run = rewrite(
            sealed / seal_law["files"]["run"], seal_law["runIdKey"], seal_law["runIdPrefix"], mutate_run
        )

        def change_disposition(body: dict) -> None:
            body.update(
                {
                    "runId": run[seal_law["runIdKey"]],
                    "packetId": run["packetId"],
                    "campaignLabel": run["campaignLabel"],
                    "stageCount": run["stageCount"],
                    "successfulStageCount": run["successfulStageCount"],
                    "humanRequiredStageCount": run["humanRequiredStageCount"],
                }
            )
            mutate_disposition(body)

        disposition = rewrite(
            sealed / seal_law["files"]["disposition"],
            seal_law["dispositionIdKey"],
            seal_law["dispositionIdPrefix"],
            change_disposition,
        )

        def change_marker(body: dict) -> None:
            body.update(
                {
                    "packetId": run["packetId"],
                    "runId": run[seal_law["runIdKey"]],
                    "dispositionId": disposition[seal_law["dispositionIdKey"]],
                }
            )
            mutate_marker(body)

        rewrite(
            sealed / seal_law["files"]["marker"],
            seal_law["markerIdKey"],
            seal_law["markerIdPrefix"],
            change_marker,
        )

        def change_verification(body: dict) -> None:
            body.update(
                {
                    "packetId": run["packetId"],
                    "runId": run[seal_law["runIdKey"]],
                    "dispositionId": disposition[seal_law["dispositionIdKey"]],
                    "stageCount": run["stageCount"],
                    "privatePhysicalEvidenceBodyCount": run["privatePhysicalEvidenceBodyCount"],
                }
            )
            mutate_verification(body)

        verification = rewrite(
            sealed / seal_law["files"]["verification"],
            seal_law["verificationIdKey"],
            seal_law["verificationIdPrefix"],
            change_verification,
        )
        law.write_canonical_json(estate / "receipts" / "detached-verification.json", verification)

        def change_manifest(body: dict) -> None:
            body["runId"] = run[seal_law["runIdKey"]]
            body["dispositionId"] = disposition[seal_law["dispositionIdKey"]]
            body["files"] = [
                {
                    "path": name,
                    "bytes": len((sealed / name).read_bytes()),
                    "sha256": law.sha256_bytes((sealed / name).read_bytes()),
                }
                for name in seal_law["manifestFiles"]
            ]
            body["fileCount"] = len(body["files"])
            mutate_manifest(body)

        manifest = rewrite(
            sealed / seal_law["files"]["manifest"],
            seal_law["manifestIdKey"],
            seal_law["manifestIdPrefix"],
            change_manifest,
        )
        state = rewrite(
            packet / packet_law["files"]["state"],
            packet_law["stateIdKey"],
            packet_law["stateIdPrefix"],
            lambda body: body.update({"sealedDispositionId": disposition[seal_law["dispositionIdKey"]]}),
        )
        transaction_path = sealed.parent / f".{sealed.name}.seal-transaction.json"

        def change_transaction(body: dict) -> None:
            body.update(
                {
                    "status": "sealed_state_promoted",
                    "proposedSealedStateId": state[packet_law["stateIdKey"]],
                    "runId": run[seal_law["runIdKey"]],
                    "dispositionId": disposition[seal_law["dispositionIdKey"]],
                    "manifestId": manifest[seal_law["manifestIdKey"]],
                    "postSealClosureId": None,
                }
            )

        rewrite(
            transaction_path,
            seal_law["transaction"]["idKey"],
            seal_law["transaction"]["idPrefix"],
            change_transaction,
        )
        return sealed, packet

    def seal_estate(self, estate: Path, *, name: str = "stc-mary-private-flight-sealed-hostile") -> dict:
        return seal_adapter.seal_packet(
            packet=estate / "campaign" / "stc-mary-private-flight-successor",
            sealed=estate / "campaign" / name,
            pre_seal_closure=estate / "receipts" / "pre-seal-closure.json",
            **closure_replay_arguments(estate),
            repository=REPOSITORY_ROOT,
            source_execution_receipt=self.walk.seal_execution_receipt_path,
        )

    def create_symbolic_link(self, link: Path, target: Path) -> bool:
        try:
            link.symlink_to(target, target_is_directory=target.is_dir())
        except (NotImplementedError, OSError):
            return False
        return True

    def create_junction(self, link: Path, target: Path) -> bool:
        if os.name != "nt":
            return False
        completed = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return completed.returncode == 0 and link.exists()

    def mutate_packet_evidence_tree(self, estate: Path, attack: str) -> bool:
        packet = estate / "campaign" / "stc-mary-private-flight-successor"
        profile = self.walk.profile
        state = load_json(packet / profile["packet"]["files"]["state"])
        state_row = state["stages"][0]
        directory = packet / state_row["evidenceDirectory"]
        record = load_json(packet / Path(state_row["draftPath"]).parent / profile["packet"]["stageRecord"]["fileName"])
        required = packet / record["evidenceFiles"][0]["relativePath"]
        if attack == "extra-file":
            (directory / "unrecorded.json").write_bytes(b"{}\n")
        elif attack == "extra-directory":
            (directory / "unrecorded-directory").mkdir()
        elif attack == "extra-symlink":
            return self.create_symbolic_link(directory / "unrecorded-link.json", required)
        elif attack == "extra-junction":
            target = estate.parent / "junction-target"
            target.mkdir(exist_ok=True)
            return self.create_junction(directory / "unrecorded-junction", target)
        elif attack == "missing-file":
            required.unlink()
        elif attack == "file-as-directory":
            required.unlink()
            required.mkdir()
        elif attack == "file-as-symlink":
            target = estate.parent / "required-link-target.json"
            shutil.copyfile(required, target)
            required.unlink()
            if not self.create_symbolic_link(required, target):
                shutil.copyfile(target, required)
                return False
        else:  # pragma: no cover - the hostile attack denominator is closed here
            raise AssertionError(attack)
        return True

    # -- the authenticated denominator --------------------------------------------
    def test_a_closure_missing_one_authenticated_confirmation_refuses(self) -> None:
        estate = self.copy_pre_seal_estate()
        self.resign_authentication(
            estate, lambda body: body.update({"confirmationIds": body["confirmationIds"][:-1]})
        )
        with self.assertRaises(pre_seal.PreSealClosureError) as caught:
            self.close_pre_seal(estate)
        self.assertEqual(caught.exception.code, "PRE_SEAL_CLOSURE_DENOMINATOR_INCOMPLETE")

    def test_a_stage_recorded_under_an_unauthenticated_confirmation_refuses(self) -> None:
        """Swapping in a confirmation nobody authenticated breaks the closure."""
        estate = self.copy_pre_seal_estate()
        foreign = cid("stcmarypacketevidencestageconfirmation1", {"unauthenticated": True})
        self.resign_authentication(
            estate,
            lambda body: body.update(
                {"confirmationIds": sorted(body["confirmationIds"][:-1] + [foreign])}
            ),
        )
        with self.assertRaises(pre_seal.PreSealClosureError) as caught:
            self.close_pre_seal(estate)
        self.assertEqual(caught.exception.code, "STAGE_CONFIRMATION_NOT_AUTHENTICATED")

    def test_a_closure_naming_statements_it_did_not_authenticate_refuses(self) -> None:
        estate = self.copy_pre_seal_estate()
        self.resign_authentication(
            estate,
            lambda body: body.update({"authenticatedStatementIds": body["authenticatedStatementIds"][:-1]}),
        )
        with self.assertRaises(pre_seal.PreSealClosureError) as caught:
            self.close_pre_seal(estate)
        self.assertEqual(caught.exception.code, "PRE_SEAL_CLOSURE_DENOMINATOR_INCOMPLETE")

    def test_recorded_evidence_edited_after_recording_refuses(self) -> None:
        """The closure replays the admitted mapping before it reads a stage record.

        A body replaced in the packet therefore refuses as a substitution against the
        candidate the gate admitted, which is a stronger statement than drift against the
        record's own digest. The drift check itself is witnessed separately below.
        """
        estate = self.copy_pre_seal_estate()
        packet = estate / "campaign" / "stc-mary-private-flight-successor"
        body = next(packet.glob("01-*/evidence/*.json"))
        body.write_bytes(b'{"schema": "quietly-replaced"}\n')
        with self.assertRaises(pre_seal.PreSealClosureError) as caught:
            self.close_pre_seal(estate)
        self.assertEqual(caught.exception.code, "EVIDENCE_BODY_SUBSTITUTED")

    def test_recorded_evidence_still_fails_its_own_custody_check(self) -> None:
        estate = self.copy_pre_seal_estate()
        packet = estate / "campaign" / "stc-mary-private-flight-successor"
        next(packet.glob("01-*/evidence/*.json")).write_bytes(b'{"schema": "quietly-replaced"}\n')
        profile = law.load_profile(PROFILE)
        state = law.load_packet(profile, packet)["state"]
        records = runtime.read_stage_records(profile=profile, packet=packet, state=state)
        with self.assertRaises(law.SuccessorFlightError) as caught:
            runtime.verify_evidence_custody(packet=packet, records=records)
        self.assertEqual(caught.exception.code, "STAGE_EVIDENCE_DRIFT")

    def test_actual_packet_evidence_tree_substitutions_refuse_pre_seal(self) -> None:
        attacks = (
            "extra-file", "extra-directory", "extra-symlink", "extra-junction",
            "missing-file", "file-as-directory", "file-as-symlink",
        )
        for attack in attacks:
            with self.subTest(attack=attack):
                estate = self.copy_pre_seal_estate()
                if not self.mutate_packet_evidence_tree(estate, attack):
                    continue
                with self.assertRaises(pre_seal.PreSealClosureError) as caught:
                    self.close_pre_seal(estate)
                self.assertIn(
                    caught.exception.code,
                    {"PACKET_EVIDENCE_TREE_INVALID", "EVIDENCE_BODY_SUBSTITUTED", "EVIDENCE_DESTINATION_INVALID"},
                )

    def test_actual_packet_evidence_tree_substitutions_after_closure_refuse_sealing(self) -> None:
        attacks = (
            "extra-file", "extra-directory", "extra-symlink", "extra-junction",
            "missing-file", "file-as-directory", "file-as-symlink",
        )
        for attack in attacks:
            with self.subTest(attack=attack):
                estate = self.copy_pre_seal_estate()
                if not self.mutate_packet_evidence_tree(estate, attack):
                    continue
                with self.assertRaises(law.SuccessorFlightError) as caught:
                    self.seal_estate(estate)
                self.assertIn(
                    caught.exception.code,
                    {"PACKET_EVIDENCE_TREE_INVALID", "EVIDENCE_BODY_SUBSTITUTED", "EVIDENCE_DESTINATION_INVALID"},
                )

    def test_actual_packet_evidence_tree_substitutions_refuse_post_seal(self) -> None:
        attacks = (
            "extra-file", "extra-directory", "extra-symlink", "extra-junction",
            "missing-file", "file-as-directory", "file-as-symlink",
        )
        for attack in attacks:
            with self.subTest(attack=attack):
                estate = self.copy_sealed_estate()
                if not self.mutate_packet_evidence_tree(estate, attack):
                    continue
                with self.assertRaises(post_seal.PostSealClosureError) as caught:
                    self.close_post_seal(estate)
                self.assertIn(
                    caught.exception.code,
                    {"PACKET_EVIDENCE_TREE_INVALID", "EVIDENCE_BODY_SUBSTITUTED", "EVIDENCE_DESTINATION_INVALID"},
                )

    def test_forged_closure_roots_with_forged_producer_binding_refuse_replay(self) -> None:
        fields = (
            "stageRecordIdentityRoot",
            "preSealEvidenceManifestRoot",
            "evidenceAdmissionDigestRoot",
            "authenticationVerificationId",
            "materializationReceiptId",
        )
        for field in fields:
            with self.subTest(field=field):
                estate = self.copy_pre_seal_estate()
                self.rewrite_closure_and_producer(
                    estate, lambda body, key=field: body.update({key: cid("forgedclosurebinding1", {"field": key})})
                )
                with self.assertRaises(law.SuccessorFlightError) as caught:
                    self.seal_estate(estate)
                self.assertEqual(caught.exception.code, "PRE_SEAL_CLOSURE_REPLAY_MISMATCH")

    def test_forged_closure_producer_digest_refuses_before_sealing(self) -> None:
        estate = self.copy_pre_seal_estate()
        path = estate / "receipts" / "close-pre-seal-execution.json"
        custody = self.walk.profile["executionCustody"]
        receipt = load_json(path)
        receipt.pop(custody["idKey"], None)
        receipt["outputArtifactSha256"] = sha256_text("another closure")
        law.write_canonical_json(path, sign(receipt, custody["idKey"], custody["idPrefix"]))
        with self.assertRaises(law.SuccessorFlightError) as caught:
            self.seal_estate(estate)
        self.assertEqual(caught.exception.code, "PRE_SEAL_CLOSURE_OUTPUT_BINDING_INVALID")

    def test_closure_reuse_against_another_packet_or_source_set_refuses(self) -> None:
        substitutions = {
            "packetId": cid("stcmaryprivateflightpacket1", {"foreign": True}),
            "successorSourceSetId": cid("stcmarysuccessorsourceset1", {"foreign": True}),
        }
        for field, value in substitutions.items():
            with self.subTest(field=field):
                estate = self.copy_pre_seal_estate()
                self.rewrite_closure_and_producer(
                    estate, lambda body, key=field, replacement=value: body.update({key: replacement})
                )
                with self.assertRaises(law.SuccessorFlightError):
                    self.seal_estate(estate)

    # -- sealing --------------------------------------------------------------------
    def test_sealing_without_a_pre_seal_closure_refuses(self) -> None:
        estate = self.copy_pre_seal_estate()
        with self.assertRaises(law.SuccessorFlightError) as caught:
            seal_adapter.seal_packet(
                packet=estate / "campaign" / "stc-mary-private-flight-successor",
                sealed=estate / "campaign" / "stc-mary-private-flight-sealed-unclosed",
                pre_seal_closure=estate / "receipts" / "absent-closure.json",
                **closure_replay_arguments(estate),
                repository=REPOSITORY_ROOT,
                source_execution_receipt=self.walk.seal_execution_receipt_path,
            )
        self.assertEqual(caught.exception.code, "PRE_SEAL_CLOSURE_ABSENT")

    def test_sealing_under_another_packets_closure_refuses(self) -> None:
        estate = self.copy_pre_seal_estate()
        path = estate / "receipts" / "pre-seal-closure.json"
        closure = load_json(path)
        closure_law = self.walk.profile["preSealClosure"]
        closure.pop(closure_law["idKey"], None)
        closure["packetId"] = cid("stcmaryprivateflightpacket1", {"other": True})
        write_json(path, sign(closure, closure_law["idKey"], closure_law["idPrefix"]))
        with self.assertRaises(law.SuccessorFlightError) as caught:
            seal_adapter.seal_packet(
                packet=estate / "campaign" / "stc-mary-private-flight-successor",
                sealed=estate / "campaign" / "stc-mary-private-flight-sealed-foreign",
                pre_seal_closure=path,
                **closure_replay_arguments(estate),
                repository=REPOSITORY_ROOT,
                source_execution_receipt=self.walk.seal_execution_receipt_path,
            )
        self.assertEqual(caught.exception.code, "PRE_SEAL_CLOSURE_BINDING_INVALID")

    def test_a_sealed_directory_outside_the_admitted_pattern_refuses(self) -> None:
        estate = self.copy_pre_seal_estate()
        with self.assertRaises(law.SuccessorFlightError) as caught:
            seal_adapter.seal_packet(
                packet=estate / "campaign" / "stc-mary-private-flight-successor",
                sealed=estate / "campaign" / "arbitrary-output",
                pre_seal_closure=estate / "receipts" / "pre-seal-closure.json",
                **closure_replay_arguments(estate),
                repository=REPOSITORY_ROOT,
                source_execution_receipt=self.walk.seal_execution_receipt_path,
            )
        self.assertEqual(caught.exception.code, "SEALED_OUTPUT_UNSAFE")

    def test_sealing_refuses_sealed_directory_inside_packet_with_external_transaction(self) -> None:
        estate = self.copy_pre_seal_estate()
        packet = estate / "campaign" / "stc-mary-private-flight-successor"
        sealed = packet / "stc-mary-private-flight-sealed-inside-packet"
        transaction = self.external_seal_transaction(estate)
        with self.assertRaises(law.SuccessorFlightError) as caught:
            seal_adapter.seal_packet(
                packet=packet,
                sealed=sealed,
                pre_seal_closure=estate / "receipts" / "pre-seal-closure.json",
                **closure_replay_arguments(estate),
                repository=REPOSITORY_ROOT,
                transaction_receipt=transaction,
                source_execution_receipt=self.walk.seal_execution_receipt_path,
            )
        self.assertEqual(caught.exception.code, "SEALED_OUTPUT_UNSAFE")
        self.assertFalse(sealed.exists())
        self.assertFalse((sealed.parent / f".{sealed.name}.seal-staging").exists())

    def test_sealing_refuses_packet_inside_sealed_directory_with_external_transaction(self) -> None:
        estate = self.copy_pre_seal_estate()
        original_packet = estate / "campaign" / "stc-mary-private-flight-successor"
        sealed = estate / "campaign" / "stc-mary-private-flight-sealed-around-packet"
        sealed.mkdir()
        packet = sealed / "private-packet"
        shutil.move(original_packet, packet)
        transaction = self.external_seal_transaction(estate)
        with self.assertRaises(law.SuccessorFlightError) as caught:
            seal_adapter.seal_packet(
                packet=packet,
                sealed=sealed,
                pre_seal_closure=estate / "receipts" / "pre-seal-closure.json",
                **closure_replay_arguments(estate),
                repository=REPOSITORY_ROOT,
                transaction_receipt=transaction,
                source_execution_receipt=self.walk.seal_execution_receipt_path,
            )
        self.assertEqual(caught.exception.code, "SEALED_OUTPUT_UNSAFE")
        self.assertEqual(list(sealed.iterdir()), [packet])
        self.assertFalse((sealed.parent / f".{sealed.name}.seal-staging").exists())

    # -- detached verification --------------------------------------------------------
    def test_a_sealed_file_edited_after_sealing_refuses(self) -> None:
        estate = self.copy_sealed_estate()
        sealed = estate / "campaign" / "stc-mary-private-flight-sealed-witness"
        disposition = load_json(sealed / "public-disposition.json")
        disposition["stageCount"] = 15
        write_json(sealed / "public-disposition.json", disposition)
        with self.assertRaises(law.SuccessorFlightError) as caught:
            seal_adapter.verify_detached(sealed=sealed, repository=REPOSITORY_ROOT)
        self.assertEqual(caught.exception.code, "SEALED_FILE_MISMATCH")

    def test_a_hand_written_verification_does_not_reproduce(self) -> None:
        """The stored verification must be derivable from the sealed run alone."""
        estate = self.copy_sealed_estate()
        sealed = estate / "campaign" / "stc-mary-private-flight-sealed-witness"
        seal_law = self.walk.profile["seal"]
        verification = load_json(sealed / "verification.json")
        verification.pop(seal_law["verificationIdKey"], None)
        verification["privatePhysicalEvidenceBodyCount"] = 99
        signed = sign(verification, seal_law["verificationIdKey"], seal_law["verificationIdPrefix"])
        law.write_canonical_json(sealed / "verification.json", signed)
        manifest = load_json(sealed / "manifest.json")
        manifest.pop(seal_law["manifestIdKey"], None)
        data = (sealed / "verification.json").read_bytes()
        for row in manifest["files"]:
            if row["path"] == "verification.json":
                row["bytes"] = len(data)
                row["sha256"] = law.sha256_bytes(data)
        law.write_canonical_json(
            sealed / "manifest.json",
            sign(manifest, seal_law["manifestIdKey"], seal_law["manifestIdPrefix"]),
        )
        with self.assertRaises(law.SuccessorFlightError) as caught:
            seal_adapter.verify_detached(sealed=sealed, repository=REPOSITORY_ROOT)
        self.assertEqual(caught.exception.code, "SEALED_VERIFICATION_MISMATCH")

    def test_exact_five_file_surface_and_authority_none_pass_both_acceptance_surfaces(self) -> None:
        estate = self.copy_sealed_estate()
        sealed = estate / "campaign" / "stc-mary-private-flight-sealed-witness"
        expected = set(self.walk.profile["seal"]["files"].values())
        self.assertEqual({entry.name for entry in sealed.iterdir()}, expected)
        self.assertTrue(all(entry.is_file() and not entry.is_symlink() for entry in sealed.iterdir()))
        detached = seal_adapter.verify_detached(sealed=sealed, repository=REPOSITORY_ROOT)
        self.assertEqual(detached["status"], "PASS")
        self.assertEqual(detached["authority"], "none")
        closure = self.close_post_seal(estate)
        self.assertEqual(closure["status"], "PASS")
        self.assertEqual(closure["authority"], "none")

    def test_detached_refuses_one_unmanifested_regular_file(self) -> None:
        estate = self.copy_sealed_estate()
        sealed = estate / "campaign" / "stc-mary-private-flight-sealed-witness"
        (sealed / "unmanifested.json").write_bytes(b"{}\n")
        with self.assertRaises(law.SuccessorFlightError) as caught:
            seal_adapter.verify_detached(sealed=sealed, repository=REPOSITORY_ROOT)
        self.assertEqual(caught.exception.code, "SEALED_OUTPUT_INVALID")

    def test_post_seal_refuses_one_unmanifested_regular_file(self) -> None:
        estate = self.copy_sealed_estate()
        sealed = estate / "campaign" / "stc-mary-private-flight-sealed-witness"
        (sealed / "unmanifested.json").write_bytes(b"{}\n")
        with self.assertRaises(post_seal.PostSealClosureError) as caught:
            self.close_post_seal(estate)
        self.assertEqual(caught.exception.code, "SEALED_OUTPUT_INVALID")

    def test_detached_refuses_one_unmanifested_subdirectory(self) -> None:
        estate = self.copy_sealed_estate()
        sealed = estate / "campaign" / "stc-mary-private-flight-sealed-witness"
        (sealed / "unmanifested-directory").mkdir()
        with self.assertRaises(law.SuccessorFlightError) as caught:
            seal_adapter.verify_detached(sealed=sealed, repository=REPOSITORY_ROOT)
        self.assertEqual(caught.exception.code, "SEALED_OUTPUT_INVALID")

    def test_post_seal_refuses_one_unmanifested_subdirectory(self) -> None:
        estate = self.copy_sealed_estate()
        sealed = estate / "campaign" / "stc-mary-private-flight-sealed-witness"
        (sealed / "unmanifested-directory").mkdir()
        with self.assertRaises(post_seal.PostSealClosureError) as caught:
            self.close_post_seal(estate)
        self.assertEqual(caught.exception.code, "SEALED_OUTPUT_INVALID")

    def test_detached_refuses_one_unmanifested_symbolic_link_when_permitted(self) -> None:
        estate = self.copy_sealed_estate()
        sealed = estate / "campaign" / "stc-mary-private-flight-sealed-witness"
        link = sealed / "unmanifested-link.json"
        if not self.create_symbolic_link(link, sealed / "SEALED-ROOT.json"):
            self.assertFalse(link.exists())
            return
        with self.assertRaises(law.SuccessorFlightError) as caught:
            seal_adapter.verify_detached(sealed=sealed, repository=REPOSITORY_ROOT)
        self.assertEqual(caught.exception.code, "SEALED_OUTPUT_INVALID")

    def test_post_seal_refuses_one_unmanifested_symbolic_link_when_permitted(self) -> None:
        estate = self.copy_sealed_estate()
        sealed = estate / "campaign" / "stc-mary-private-flight-sealed-witness"
        link = sealed / "unmanifested-link.json"
        if not self.create_symbolic_link(link, sealed / "SEALED-ROOT.json"):
            self.assertFalse(link.exists())
            return
        with self.assertRaises(post_seal.PostSealClosureError) as caught:
            self.close_post_seal(estate)
        self.assertEqual(caught.exception.code, "SEALED_OUTPUT_INVALID")

    def test_detached_refuses_a_missing_required_entry(self) -> None:
        estate = self.copy_sealed_estate()
        sealed = estate / "campaign" / "stc-mary-private-flight-sealed-witness"
        (sealed / "verification.json").unlink()
        with self.assertRaises(law.SuccessorFlightError) as caught:
            seal_adapter.verify_detached(sealed=sealed, repository=REPOSITORY_ROOT)
        self.assertEqual(caught.exception.code, "SEALED_OUTPUT_INVALID")

    def test_post_seal_refuses_a_missing_required_entry(self) -> None:
        estate = self.copy_sealed_estate()
        sealed = estate / "campaign" / "stc-mary-private-flight-sealed-witness"
        (sealed / "verification.json").unlink()
        with self.assertRaises(post_seal.PostSealClosureError) as caught:
            self.close_post_seal(estate)
        self.assertEqual(caught.exception.code, "SEALED_OUTPUT_INVALID")

    def test_detached_refuses_required_entry_replaced_by_symbolic_link_when_permitted(self) -> None:
        estate = self.copy_sealed_estate()
        sealed = estate / "campaign" / "stc-mary-private-flight-sealed-witness"
        required = sealed / "verification.json"
        target = estate.parent / "verification-target.json"
        shutil.copyfile(required, target)
        required.unlink()
        if not self.create_symbolic_link(required, target):
            shutil.copyfile(target, required)
            return
        with self.assertRaises(law.SuccessorFlightError) as caught:
            seal_adapter.verify_detached(sealed=sealed, repository=REPOSITORY_ROOT)
        self.assertEqual(caught.exception.code, "SEALED_OUTPUT_INVALID")

    def test_post_seal_refuses_required_entry_replaced_by_symbolic_link_when_permitted(self) -> None:
        estate = self.copy_sealed_estate()
        sealed = estate / "campaign" / "stc-mary-private-flight-sealed-witness"
        required = sealed / "verification.json"
        target = estate.parent / "verification-target.json"
        shutil.copyfile(required, target)
        required.unlink()
        if not self.create_symbolic_link(required, target):
            shutil.copyfile(target, required)
            return
        with self.assertRaises(post_seal.PostSealClosureError) as caught:
            self.close_post_seal(estate)
        self.assertEqual(caught.exception.code, "SEALED_OUTPUT_INVALID")

    # -- post-seal closure ---------------------------------------------------------------
    def test_a_post_seal_closure_over_an_unsealed_packet_refuses(self) -> None:
        """The reserved assertions may not be made before the objects exist."""
        estate = self.copy_sealed_estate()
        packet = estate / "campaign" / "stc-mary-private-flight-successor"
        packet_law = self.walk.profile["packet"]
        state = load_json(packet / packet_law["files"]["state"])
        state.pop(packet_law["stateIdKey"], None)
        state["sealed"] = False
        state["sealedDispositionId"] = None
        law.write_canonical_json(
            packet / packet_law["files"]["state"],
            sign(state, packet_law["stateIdKey"], packet_law["stateIdPrefix"]),
        )
        with self.assertRaises(post_seal.PostSealClosureError) as caught:
            post_seal.close_post_seal(
                packet=packet,
                sealed=estate / "campaign" / "stc-mary-private-flight-sealed-witness",
                pre_seal_closure=estate / "receipts" / "pre-seal-closure.json",
                pre_seal_execution_receipt=estate / "receipts" / "close-pre-seal-execution.json",
                admission_receipt=estate / "receipts" / "admission-admissible.json",
                materialization_receipt=estate / "receipts" / "evidence-materialization.json",
                authentication_receipt=estate / "receipts" / "authentication.json",
                candidates=estate / "admission",
                detached_verification=estate / "receipts" / "detached-verification.json",
                profile_path=PROFILE,
                repository=REPOSITORY_ROOT,
            )
        self.assertEqual(caught.exception.code, "POST_SEAL_ASSERTION_BEFORE_SEALING")

    def test_post_seal_refuses_sealed_directory_inside_packet_with_external_transaction(self) -> None:
        estate = self.copy_sealed_estate()
        packet = estate / "campaign" / "stc-mary-private-flight-successor"
        original_sealed = estate / "campaign" / "stc-mary-private-flight-sealed-witness"
        sealed = packet / original_sealed.name
        shutil.move(original_sealed, sealed)
        transaction = self.external_seal_transaction(estate)
        with self.assertRaises(post_seal.PostSealClosureError) as caught:
            post_seal.close_post_seal(
                packet=packet,
                sealed=sealed,
                pre_seal_closure=estate / "receipts" / "pre-seal-closure.json",
                pre_seal_execution_receipt=estate / "receipts" / "close-pre-seal-execution.json",
                admission_receipt=estate / "receipts" / "admission-admissible.json",
                materialization_receipt=estate / "receipts" / "evidence-materialization.json",
                authentication_receipt=estate / "receipts" / "authentication.json",
                candidates=estate / "admission",
                detached_verification=estate / "receipts" / "detached-verification.json",
                profile_path=PROFILE,
                repository=REPOSITORY_ROOT,
                seal_transaction_receipt=transaction,
            )
        self.assertEqual(caught.exception.code, "SEALED_OUTPUT_UNSAFE")

    def test_post_seal_refuses_packet_inside_sealed_directory_with_external_transaction(self) -> None:
        estate = self.copy_sealed_estate()
        original_packet = estate / "campaign" / "stc-mary-private-flight-successor"
        sealed = estate / "campaign" / "stc-mary-private-flight-sealed-witness"
        packet = sealed / "private-packet"
        shutil.move(original_packet, packet)
        transaction = self.external_seal_transaction(estate)
        with self.assertRaises(post_seal.PostSealClosureError) as caught:
            post_seal.close_post_seal(
                packet=packet,
                sealed=sealed,
                pre_seal_closure=estate / "receipts" / "pre-seal-closure.json",
                pre_seal_execution_receipt=estate / "receipts" / "close-pre-seal-execution.json",
                admission_receipt=estate / "receipts" / "admission-admissible.json",
                materialization_receipt=estate / "receipts" / "evidence-materialization.json",
                authentication_receipt=estate / "receipts" / "authentication.json",
                candidates=estate / "admission",
                detached_verification=estate / "receipts" / "detached-verification.json",
                profile_path=PROFILE,
                repository=REPOSITORY_ROOT,
                seal_transaction_receipt=transaction,
            )
        self.assertEqual(caught.exception.code, "SEALED_OUTPUT_UNSAFE")

    def test_a_foreign_detached_verification_refuses(self) -> None:
        estate = self.copy_sealed_estate()
        path = estate / "receipts" / "detached-verification.json"
        seal_law = self.walk.profile["seal"]
        verification = load_json(path)
        verification.pop(seal_law["verificationIdKey"], None)
        verification["stageCount"] = 15
        write_json(path, sign(verification, seal_law["verificationIdKey"], seal_law["verificationIdPrefix"]))
        with self.assertRaises(post_seal.PostSealClosureError) as caught:
            post_seal.close_post_seal(
                packet=estate / "campaign" / "stc-mary-private-flight-successor",
                sealed=estate / "campaign" / "stc-mary-private-flight-sealed-witness",
                pre_seal_closure=estate / "receipts" / "pre-seal-closure.json",
                pre_seal_execution_receipt=estate / "receipts" / "close-pre-seal-execution.json",
                admission_receipt=estate / "receipts" / "admission-admissible.json",
                materialization_receipt=estate / "receipts" / "evidence-materialization.json",
                authentication_receipt=estate / "receipts" / "authentication.json",
                candidates=estate / "admission",
                detached_verification=path,
                profile_path=PROFILE,
                repository=REPOSITORY_ROOT,
            )
        self.assertEqual(caught.exception.code, "DETACHED_VERIFICATION_MISMATCH")

    def test_twin_forged_verification_copies_refuse_deterministic_post_seal_replay(self) -> None:
        estate = self.copy_sealed_estate()
        self.rewrite_sealed_flight(
            estate, mutate_verification=lambda body: body.update({"bodyFreePublicDisposition": False})
        )
        with self.assertRaises(post_seal.PostSealClosureError) as caught:
            self.close_post_seal(estate)
        self.assertEqual(caught.exception.code, "DETACHED_VERIFICATION_MISMATCH")

    def test_self_consistently_altered_sealed_runs_refuse_packet_reconstruction(self) -> None:
        attacks = {
            "canonical": lambda body: body.update({"canonicalMissionStateDigest": sha256_text("foreign canonical")}),
            "stage-count": lambda body: body.update({"stageCount": body["stageCount"] + 1}),
            "successful-count": lambda body: body.update({"successfulStageCount": body["successfulStageCount"] - 1}),
            "human-count": lambda body: body.update({"humanRequiredStageCount": body["humanRequiredStageCount"] + 1}),
            "body-count": lambda body: body.update({"privatePhysicalEvidenceBodyCount": body["privatePhysicalEvidenceBodyCount"] + 1}),
        }
        for name, mutate in attacks.items():
            with self.subTest(name=name):
                estate = self.copy_sealed_estate()
                self.rewrite_sealed_flight(estate, mutate_run=mutate)
                with self.assertRaises(post_seal.PostSealClosureError) as caught:
                    self.close_post_seal(estate)
                self.assertEqual(caught.exception.code, "SEALED_RUN_REPLAY_MISMATCH")

    def test_widened_marker_and_manifest_semantics_refuse_reconstruction(self) -> None:
        attacks = (
            ("marker-public-count", {"mutate_marker": lambda body: body.update({"publicEvidenceBodyCount": 1})}),
            ("marker-authority", {"mutate_marker": lambda body: body.update({"authority": "mission"})}),
            ("manifest-public-count", {"mutate_manifest": lambda body: body.update({"publicEvidenceBodyCount": 1})}),
            ("manifest-authority", {"mutate_manifest": lambda body: body.update({"authority": "mission"})}),
        )
        for name, changes in attacks:
            with self.subTest(name=name):
                estate = self.copy_sealed_estate()
                self.rewrite_sealed_flight(estate, **changes)
                with self.assertRaises(post_seal.PostSealClosureError):
                    self.close_post_seal(estate)

    def test_every_sealed_claim_boundary_drift_refuses_reconstruction(self) -> None:
        attacks = (
            {"mutate_run": lambda body: body.update({"claimBoundary": "drifted run claim"})},
            {"mutate_disposition": lambda body: body.update({"claimBoundary": "drifted disposition claim"})},
            {"mutate_marker": lambda body: body.update({"claimBoundary": "drifted marker claim"})},
            {"mutate_verification": lambda body: body.update({"claimBoundary": "drifted verification claim"})},
            {"mutate_manifest": lambda body: body.update({"claimBoundary": "drifted manifest claim"})},
        )
        for index, changes in enumerate(attacks, start=1):
            with self.subTest(object=index):
                estate = self.copy_sealed_estate()
                self.rewrite_sealed_flight(estate, **changes)
                with self.assertRaises(post_seal.PostSealClosureError):
                    self.close_post_seal(estate)

    def test_every_sealed_authority_widening_refuses_reconstruction(self) -> None:
        attacks = (
            {"mutate_run": lambda body: body.update({"authority": "mission"})},
            {"mutate_disposition": lambda body: body.update({"authority": "mission"})},
            {"mutate_marker": lambda body: body.update({"authority": "mission"})},
            {"mutate_verification": lambda body: body.update({"authority": "mission"})},
            {"mutate_manifest": lambda body: body.update({"authority": "mission"})},
        )
        for index, changes in enumerate(attacks, start=1):
            with self.subTest(object=index):
                estate = self.copy_sealed_estate()
                self.rewrite_sealed_flight(estate, **changes)
                with self.assertRaises(post_seal.PostSealClosureError):
                    self.close_post_seal(estate)

    def test_self_consistent_sealed_count_substitutions_refuse_reconstruction(self) -> None:
        attacks = (
            {"mutate_verification": lambda body: body.update({"fileCount": body["fileCount"] + 1})},
            {"mutate_manifest": lambda body: body.update({"fileCount": body["fileCount"] + 1})},
            {"mutate_marker": lambda body: body.update({"publicEvidenceBodyCount": 1})},
        )
        for index, changes in enumerate(attacks, start=1):
            with self.subTest(object=index):
                estate = self.copy_sealed_estate()
                self.rewrite_sealed_flight(estate, **changes)
                with self.assertRaises(post_seal.PostSealClosureError):
                    self.close_post_seal(estate)

    def test_each_self_consistent_stronger_qualification_refuses_detached_and_post_seal(self) -> None:
        for field in self.walk.profile["postSealClosure"]["strongerQualifications"]:
            with self.subTest(field=field):
                estate = self.copy_sealed_estate()
                sealed, _ = self.rewrite_disposition(
                    estate, lambda body, key=field: body.update({key: True})
                )
                with self.assertRaises(law.SuccessorFlightError) as detached:
                    seal_adapter.verify_detached(sealed=sealed, repository=REPOSITORY_ROOT)
                self.assertEqual(detached.exception.code, "SEALED_DISPOSITION_INVALID")
                with self.assertRaises(post_seal.PostSealClosureError) as closed:
                    self.close_post_seal(estate)
                self.assertEqual(closed.exception.code, "STRONGER_QUALIFICATION_CLAIMED")

    def test_self_consistent_mission_authority_refuses_detached(self) -> None:
        estate = self.copy_sealed_estate()
        sealed, _ = self.rewrite_disposition(
            estate, lambda body: body.update({"missionAuthorityGranted": True})
        )
        with self.assertRaises(law.SuccessorFlightError) as caught:
            seal_adapter.verify_detached(sealed=sealed, repository=REPOSITORY_ROOT)
        self.assertEqual(caught.exception.code, "SEALED_DISPOSITION_INVALID")

    def test_self_consistent_command_authority_refuses_detached(self) -> None:
        estate = self.copy_sealed_estate()
        sealed, _ = self.rewrite_disposition(
            estate, lambda body: body.update({"commandAuthorityGranted": True})
        )
        with self.assertRaises(law.SuccessorFlightError) as caught:
            seal_adapter.verify_detached(sealed=sealed, repository=REPOSITORY_ROOT)
        self.assertEqual(caught.exception.code, "SEALED_DISPOSITION_INVALID")

    def test_self_consistent_authority_widening_refuses_detached(self) -> None:
        estate = self.copy_sealed_estate()
        sealed, _ = self.rewrite_disposition(
            estate, lambda body: body.update({"authority": "mission"})
        )
        with self.assertRaises(law.SuccessorFlightError) as caught:
            seal_adapter.verify_detached(sealed=sealed, repository=REPOSITORY_ROOT)
        self.assertEqual(caught.exception.code, "SEALED_DISPOSITION_INVALID")

    def test_self_consistent_public_evidence_count_refuses_detached(self) -> None:
        estate = self.copy_sealed_estate()
        sealed, _ = self.rewrite_disposition(
            estate, lambda body: body.update({"publicEvidenceBodyCount": 1})
        )
        with self.assertRaises(law.SuccessorFlightError) as caught:
            seal_adapter.verify_detached(sealed=sealed, repository=REPOSITORY_ROOT)
        self.assertEqual(caught.exception.code, "SEALED_DISPOSITION_INVALID")

    def test_self_consistent_incomplete_private_flight_refuses_detached(self) -> None:
        estate = self.copy_sealed_estate()
        sealed, _ = self.rewrite_disposition(
            estate, lambda body: body.update({"privatePhysicalFlightCompleted": False})
        )
        with self.assertRaises(law.SuccessorFlightError) as caught:
            seal_adapter.verify_detached(sealed=sealed, repository=REPOSITORY_ROOT)
        self.assertEqual(caught.exception.code, "SEALED_DISPOSITION_INVALID")

    def test_each_self_consistent_disposition_run_count_disagreement_refuses_detached(self) -> None:
        for field in ("stageCount", "successfulStageCount", "humanRequiredStageCount"):
            with self.subTest(field=field):
                estate = self.copy_sealed_estate()
                sealed, _ = self.rewrite_disposition(
                    estate, lambda body, key=field: body.update({key: body[key] + 1})
                )
                with self.assertRaises(law.SuccessorFlightError) as caught:
                    seal_adapter.verify_detached(sealed=sealed, repository=REPOSITORY_ROOT)
                self.assertEqual(caught.exception.code, "SEALED_DISPOSITION_INVALID")

    def test_each_self_consistent_disposition_run_binding_disagreement_refuses_detached(self) -> None:
        replacements = {
            "runId": cid("stcmarysuccessorflightrun1", {"foreign": True}),
            "packetId": cid("stcmaryprivateflightpacket1", {"foreign": True}),
            "campaignLabel": "SYNTHETIC-FOREIGN-FLIGHT",
        }
        for field, value in replacements.items():
            with self.subTest(field=field):
                estate = self.copy_sealed_estate()
                sealed, _ = self.rewrite_disposition(
                    estate, lambda body, key=field, replacement=value: body.update({key: replacement})
                )
                with self.assertRaises(law.SuccessorFlightError) as caught:
                    seal_adapter.verify_detached(sealed=sealed, repository=REPOSITORY_ROOT)
                self.assertIn(caught.exception.code, {"SEALED_BINDING_INVALID", "SEALED_DISPOSITION_INVALID"})

    def test_self_consistent_disposition_claim_boundary_disagreement_refuses_detached(self) -> None:
        estate = self.copy_sealed_estate()
        sealed, _ = self.rewrite_disposition(
            estate, lambda body: body.update({"claimBoundary": "contradictory claim boundary"})
        )
        with self.assertRaises(law.SuccessorFlightError) as caught:
            seal_adapter.verify_detached(sealed=sealed, repository=REPOSITORY_ROOT)
        self.assertEqual(caught.exception.code, "SEALED_DISPOSITION_INVALID")

    # -- authentication, against the finished admission receipt ------------------------
    def test_the_synthetic_fixture_is_refused_against_a_live_campaign(self) -> None:
        profile = law.load_profile(PROFILE)
        admission = law.load_admission_profile(REPOSITORY_ROOT, profile)
        with self.assertRaises(law.SuccessorFlightError) as caught:
            orchestrator.verify_named_human_authentication(
                profile=profile,
                admission=admission,
                path=self.walk.authentication_path,
                receipt=self.walk.admission_receipt,
                packet={"marker": {"packetId": self.walk.packet_id}},
                campaign_id=self.walk.campaign_id,
                campaign_label=LIVE_CAMPAIGN_LABEL,
                authorizations=self.walk.authorizations,
                statement_bindings=self.walk.materialization_receipt["statementBindings"],
            )
        self.assertEqual(caught.exception.code, "SYNTHETIC_AUTHENTICATION_APPLIED_TO_LIVE_CAMPAIGN")

    def test_the_synthetic_fixture_is_admitted_against_its_own_synthetic_campaign(self) -> None:
        profile = law.load_profile(PROFILE)
        admission = law.load_admission_profile(REPOSITORY_ROOT, profile)
        body = orchestrator.verify_named_human_authentication(
            profile=profile,
            admission=admission,
            path=self.walk.authentication_path,
            receipt=self.walk.admission_receipt,
            packet={"marker": {"packetId": self.walk.packet_id}},
            campaign_id=self.walk.campaign_id,
            campaign_label=SYNTHETIC_CAMPAIGN_LABEL,
            authorizations=self.walk.authorizations,
            statement_bindings=self.walk.materialization_receipt["statementBindings"],
        )
        self.assertEqual(body["principalClass"], "named_human")
        self.assertEqual(len(body["statementIds"]), 3)
        self.assertEqual(len(body["confirmationIds"]), 16)


class MaterializedEvidenceHostileWitnesses(unittest.TestCase):
    """Attacks on the bridge between admitted roles and packet bodies.

    Each works on a private copy of the estate at the drafted-and-bridged moment, before
    any stage was recorded, so a refusal here is a refusal *before the first stage record
    exists* rather than after a packet was already built.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.walk = shared_walk()

    def copy_pre_record_estate(self) -> Path:
        target = Path(tempfile.mkdtemp(prefix="stc-mary-successor-materialize-")) / "estate"
        self.addCleanup(shutil.rmtree, target.parent, ignore_errors=True)
        shutil.copytree(self.walk.pre_record_snapshot, target)
        return target

    def orchestrate(self, estate: Path) -> dict:
        return orchestrator.orchestrate(
            packet=estate / "campaign" / "stc-mary-private-flight-successor",
            admission_receipt=estate / "receipts" / "admission-admissible.json",
            materialization_receipt=estate / "receipts" / "evidence-materialization.json",
            authentication_receipt=estate / "receipts" / "authentication.json",
            candidates=estate / "admission",
            repository=REPOSITORY_ROOT,
            transaction_workspace=estate / "receipts" / "recording-transactions",
            source_execution_receipt=self.walk.recording_execution_receipt_path,
        )

    def resign_materialization(self, estate: Path, mutate) -> Path:
        path = estate / "receipts" / "evidence-materialization.json"
        body = load_json(path)
        law_block = self.walk.profile["evidenceMaterialization"]
        body.pop(law_block["idKey"], None)
        mutate(body)
        law.write_canonical_json(path, sign(body, law_block["idKey"], law_block["idPrefix"]))
        return path

    def assert_no_stage_was_recorded(self, estate: Path) -> None:
        packet = estate / "campaign" / "stc-mary-private-flight-successor"
        self.assertEqual(list(packet.glob("*/stage-record.json")), [])
        self.assertEqual(law.load_packet(law.load_profile(PROFILE), packet)["state"]["completedStageCount"], 0)

    # -- the defect this transaction exists to refuse --------------------------------
    def test_one_generic_body_per_stage_refuses_before_the_first_record(self) -> None:
        """The traversal this source set previously qualified must now refuse.

        Writing one invented ``stage-evidence.json`` into each stage and recording sixteen
        stages used to reach a detached-verified seal reporting sixteen private bodies
        beside forty-three-role admission roots. It is now refused at materialization,
        before a single stage record is written.
        """
        estate = self.copy_pre_record_estate()
        packet = estate / "campaign" / "stc-mary-private-flight-successor"
        for index, stage in enumerate(self.walk.stages):
            directory = packet / f"{index + 1:02d}-{stage}" / "evidence"
            law.write_canonical_json(
                directory / "stage-evidence.json",
                {
                    "schema": "stc-mary/successor-flight-synthetic-evidence/1",
                    "stage": stage,
                    "sequence": index + 1,
                    "authority": "none",
                },
            )
        with self.assertRaises(law.SuccessorFlightError) as caught:
            self.orchestrate(estate)
        self.assertEqual(caught.exception.code, "PACKET_EVIDENCE_UNMATERIALIZED")
        self.assert_no_stage_was_recorded(estate)

    def test_one_extra_body_beside_the_admitted_set_refuses(self) -> None:
        estate = self.copy_pre_record_estate()
        packet = estate / "campaign" / "stc-mary-private-flight-successor"
        directory = packet / f"01-{self.walk.stages[0]}" / "evidence"
        law.write_canonical_json(directory / "extra.json", {"authority": "none"})
        with self.assertRaises(law.SuccessorFlightError) as caught:
            self.orchestrate(estate)
        self.assertEqual(caught.exception.code, "PACKET_EVIDENCE_UNMATERIALIZED")
        self.assert_no_stage_was_recorded(estate)

    # -- the materialization receipt itself -------------------------------------------
    def test_a_hand_written_materialization_receipt_does_not_reidentify(self) -> None:
        estate = self.copy_pre_record_estate()
        path = estate / "receipts" / "evidence-materialization.json"
        body = load_json(path)
        body["roles"][0]["bodySha256"] = sha256_text("substituted")
        law.write_canonical_json(path, body)
        with self.assertRaises(law.SuccessorFlightError) as caught:
            self.orchestrate(estate)
        self.assertEqual(caught.exception.code, "MATERIALIZATION_RECEIPT_INVALID")
        self.assert_no_stage_was_recorded(estate)

    def test_a_materialization_receipt_missing_one_role_refuses(self) -> None:
        estate = self.copy_pre_record_estate()
        self.resign_materialization(
            estate,
            lambda body: body.update(
                {"roles": body["roles"][:-1], "materializedRoleCount": len(body["roles"]) - 1}
            ),
        )
        with self.assertRaises(law.SuccessorFlightError) as caught:
            self.orchestrate(estate)
        self.assertEqual(caught.exception.code, "MATERIALIZATION_ROLE_DENOMINATOR_INVALID")
        self.assert_no_stage_was_recorded(estate)

    def test_a_role_stripped_of_its_retained_provenance_refuses(self) -> None:
        """Retention nothing checks is a column a hand-written receipt can null out."""
        def strip(body: dict) -> None:
            row = next(
                entry for entry in body["roles"]
                if entry["provenanceClass"] == "accepted_predecessor_receipt"
            )
            row["sourceReceiptId"] = None

        estate = self.copy_pre_record_estate()
        self.resign_materialization(estate, strip)
        with self.assertRaises(law.SuccessorFlightError) as caught:
            self.orchestrate(estate)
        self.assertEqual(caught.exception.code, "MATERIALIZATION_RECEIPT_INVALID")
        self.assert_no_stage_was_recorded(estate)

    def test_a_materialization_receipt_for_another_request_refuses(self) -> None:
        estate = self.copy_pre_record_estate()
        self.resign_materialization(
            estate,
            lambda body: body.update(
                {"requestId": cid("stcmarypacketevidenceadmissionrequest1", {"another": True})}
            ),
        )
        with self.assertRaises(law.SuccessorFlightError) as caught:
            self.orchestrate(estate)
        self.assertEqual(caught.exception.code, "MATERIALIZATION_BINDING_INVALID")
        self.assert_no_stage_was_recorded(estate)

    def test_candidate_drift_after_completed_materialization_is_not_source_evidence(self) -> None:
        estate = self.copy_pre_record_estate()
        row = load_json(estate / "receipts" / "evidence-materialization.json")["roles"][0]
        (estate / "admission" / row["candidateBodyPath"]).write_bytes(b'{"schema": "swapped"}\n')
        result = self.orchestrate(estate)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["completedStageCount"], 16)

    # -- a row is a member of one receipt, never a portable assertion -----------------
    def test_a_row_extracted_from_its_parent_receipt_is_not_a_receipt(self) -> None:
        """A single row, lifted out and offered on its own, authenticates nothing."""
        estate = self.copy_pre_record_estate()
        path = estate / "receipts" / "evidence-materialization.json"
        row = load_json(path)["roles"][0]
        law_block = self.walk.profile["evidenceMaterialization"]
        law.write_canonical_json(path, sign(dict(row), law_block["idKey"], law_block["idPrefix"]))
        with self.assertRaises(law.SuccessorFlightError) as caught:
            self.orchestrate(estate)
        self.assertEqual(caught.exception.code, "MATERIALIZATION_RECEIPT_INVALID")
        self.assert_no_stage_was_recorded(estate)

    def test_a_receipt_resigned_for_another_campaign_refuses(self) -> None:
        """The bodies are untouched; only the receipt's top-level campaign moved."""
        estate = self.copy_pre_record_estate()
        self.resign_materialization(
            estate,
            lambda body: body.update(
                {"campaignId": cid("stcmaryflightconductorcampaign1", {"campaignLabel": "SYNTHETIC-OTHER"})}
            ),
        )
        with self.assertRaises(law.SuccessorFlightError) as caught:
            self.orchestrate(estate)
        self.assertEqual(caught.exception.code, "MATERIALIZATION_BINDING_INVALID")
        self.assert_no_stage_was_recorded(estate)

    def test_a_receipt_resigned_for_another_packet_refuses(self) -> None:
        estate = self.copy_pre_record_estate()
        self.resign_materialization(
            estate,
            lambda body: body.update(
                {"packetId": cid("stcmaryprivateflightpacket1", {"another": True})}
            ),
        )
        with self.assertRaises(law.SuccessorFlightError) as caught:
            self.orchestrate(estate)
        self.assertEqual(caught.exception.code, "MATERIALIZATION_BINDING_INVALID")
        self.assert_no_stage_was_recorded(estate)

    def test_a_row_moved_to_another_stage_refuses_before_any_record(self) -> None:
        """Refused with the packet untouched, not after earlier stages were written."""
        def move(body: dict) -> None:
            row = next(entry for entry in body["roles"] if entry["stage"] == self.walk.stages[13])
            row["stage"] = self.walk.stages[0]

        estate = self.copy_pre_record_estate()
        self.resign_materialization(estate, move)
        with self.assertRaises(law.SuccessorFlightError) as caught:
            self.orchestrate(estate)
        self.assertEqual(caught.exception.code, "MATERIALIZATION_BINDING_INVALID")
        self.assert_no_stage_was_recorded(estate)

    def test_a_row_moved_to_another_evidence_role_refuses_before_any_record(self) -> None:
        """A late-stage rebinding must not let the earlier fifteen stages be recorded."""
        def rebind(body: dict) -> None:
            row = next(entry for entry in body["roles"] if entry["stage"] == self.walk.stages[13])
            row["evidenceRole"] = f"{row['evidenceRole']} (rebound)"

        estate = self.copy_pre_record_estate()
        self.resign_materialization(estate, rebind)
        with self.assertRaises(law.SuccessorFlightError) as caught:
            self.orchestrate(estate)
        self.assertEqual(caught.exception.code, "STAGE_EVIDENCE_ROOT_MISMATCH")
        self.assert_no_stage_was_recorded(estate)

    # -- a body re-signed for another coordinate --------------------------------------
    def replay_one_role(self, *, mutate) -> None:
        """Drive replay_role directly over a body re-signed for another coordinate.

        Campaign and packet identity live at receipt level, so the predicate that catches
        a re-signed body is the per-body check inside the bridge. It is exercised here
        directly rather than through a whole traversal.
        """
        walk = self.walk
        stage = walk.stages[0]
        stage_law = walk.admission_profile["stages"][stage]
        role_law = stage_law["evidenceRoles"][0]
        schema_law = walk.admission_profile["bodySchemas"][role_law["provenanceClass"]]

        root = Path(tempfile.mkdtemp(prefix="stc-mary-successor-rebind-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        body = walk.evidence_body(stage, 1, role_law, stage_law)
        body.pop(schema_law["idKey"], None)
        mutate(body)
        body = sign(body, schema_law["idKey"], schema_law["idPrefix"])
        relative = f"bodies/01-{stage}/{role_law['evidenceRoleKey']}.json"
        write_json(root / relative, body)
        data = (root / relative).read_bytes()
        descriptor = {
            "evidenceRole": role_law["evidenceRole"],
            "provenanceClass": role_law["provenanceClass"],
            "evidenceClass": EVIDENCE_CLASS_BY_PROVENANCE[role_law["provenanceClass"]],
            "mediaType": "application/json",
            "bodyPath": relative,
            "bodySha256": law.sha256_bytes(data),
            "bodyBytes": len(data),
            "bodySchema": schema_law["schema"],
            "bodyContentId": body[schema_law["idKey"]],
            "opaqueInstrumentClass": None,
            "instrumentReceiptPath": None,
            "authority": "none",
            "claimBoundary": "Synthetic evidence descriptor for conformance only. It grants no authority.",
        }
        with self.assertRaises(materialization_bridge.MaterializationError) as caught:
            materialization_bridge.replay_role(
                profile=load_json(PROFILE),
                admission=walk.admission_profile,
                descriptor=descriptor,
                role_law=role_law,
                stage=stage,
                sequence=1,
                candidates=root,
                packet=walk.packet,
                evidence_directory=f"01-{stage}/evidence",
                campaign_id=walk.campaign_id,
                packet_id=walk.packet_id,
            )
        self.assertEqual(caught.exception.code, "EVIDENCE_BODY_SUBSTITUTED")

    def test_a_body_resigned_for_another_campaign_refuses(self) -> None:
        self.replay_one_role(
            mutate=lambda body: body.update(
                {"campaignId": cid("stcmaryflightconductorcampaign1", {"campaignLabel": "SYNTHETIC-OTHER"})}
            )
        )

    def test_a_body_resigned_for_another_packet_refuses(self) -> None:
        self.replay_one_role(
            mutate=lambda body: body.update(
                {"packetId": cid("stcmaryprivateflightpacket1", {"another": True})}
            )
        )

    # -- the bridge refuses on its own inputs -----------------------------------------
    def bridge(self, estate: Path) -> dict:
        return materialization_bridge.materialize_evidence(
            packet=estate / "campaign" / "stc-mary-private-flight-successor",
            admission_receipt=estate / "receipts" / "admission-admissible.json",
            candidates=estate / "admission",
            repository=REPOSITORY_ROOT,
            profile_path=PROFILE,
        )

    def test_the_bridge_refuses_a_request_edited_after_admission(self) -> None:
        estate = self.copy_pre_record_estate()
        path = estate / "admission" / "ADMISSION-REQUEST.json"
        body = load_json(path)
        body["stages"][0]["evidence"] = body["stages"][0]["evidence"][:-1]
        write_json(path, body)
        with self.assertRaises(materialization_bridge.MaterializationError) as caught:
            self.bridge(estate)
        self.assertEqual(caught.exception.code, "ADMISSION_REQUEST_BINDING_INVALID")

    def test_the_bridge_refuses_a_candidate_body_edited_after_admission(self) -> None:
        estate = self.copy_pre_record_estate()
        body = next((estate / "admission" / "bodies").rglob("*.json"))
        body.write_bytes(b'{"schema": "swapped"}\n')
        with self.assertRaises(materialization_bridge.MaterializationError) as caught:
            self.bridge(estate)
        self.assertEqual(caught.exception.code, "EVIDENCE_BODY_SUBSTITUTED")

    def test_the_bridge_refuses_an_unbootstrapped_admission_receipt(self) -> None:
        estate = self.copy_pre_record_estate()
        path = estate / "receipts" / "admission-admissible.json"
        body = load_json(path)
        body["bootstrapAuthenticated"] = False
        write_json(path, body)
        with self.assertRaises(materialization_bridge.MaterializationError) as caught:
            self.bridge(estate)
        self.assertEqual(caught.exception.code, "ADMISSION_RECEIPT_NOT_BOOTSTRAP_AUTHENTICATED")

    def test_the_bridge_refuses_to_write_inside_the_packet(self) -> None:
        """Exercised through the real entrypoint, in its own process.

        The refusal document goes to stdout, so it is captured here rather than left to
        interleave with the witness report the hosted gate parses.
        """
        estate = self.copy_pre_record_estate()
        packet = estate / "campaign" / "stc-mary-private-flight-successor"
        module = ANCHOR / "verify_stc_mary_successor_evidence_materialization.py"
        with tempfile.TemporaryDirectory(prefix="stc-mary-materialization-foreign-") as foreign:
            completed = subprocess.run(
                [
                sys.executable, "-I", "-S", "-B", "-c", execution_launcher.ISOLATED_MODULE_LAUNCHER,
                str(module),
                "--packet",
                str(packet),
                "--admission-receipt",
                str(estate / "receipts" / "admission-admissible.json"),
                "--candidates",
                str(estate / "admission"),
                "--repository-root",
                str(REPOSITORY_ROOT),
                "--profile",
                str(PROFILE),
                "--out",
                str(packet / "smuggled.json"),
                ],
                input=module.read_bytes(),
                cwd=foreign,
                env=execution_launcher.scrubbed_environment(),
                check=False,
                capture_output=True,
            )
        self.assertEqual(completed.returncode, 1)
        refusal = json.loads(completed.stdout.decode("utf-8"))
        self.assertEqual(refusal["code"], "RECEIPT_INSIDE_MEASURED_SURFACE")
        self.assertFalse((packet / "smuggled.json").exists())


class VerifiedPrefixRestartWitnesses(unittest.TestCase):
    """Crash witnesses for evidence promotion and the contiguous recording prefix."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.walk = shared_walk()

    def copy_pre_record_estate(self) -> Path:
        target = Path(tempfile.mkdtemp(prefix="stc-mary-successor-restart-")) / "estate"
        self.addCleanup(shutil.rmtree, target.parent, ignore_errors=True)
        shutil.copytree(self.walk.pre_record_snapshot, target)
        return target

    def reset_materialization(self, estate: Path) -> tuple[Path, Path, Path]:
        packet = estate / "campaign" / "stc-mary-private-flight-successor"
        for body in packet.glob("*/evidence/*"):
            if body.is_file():
                body.unlink()
        receipt = estate / "receipts" / "evidence-materialization.json"
        receipt.unlink()
        transaction = estate / "receipts" / "materialization-transaction"
        shutil.rmtree(transaction, ignore_errors=True)
        return packet, receipt, transaction

    def materialize_with_interruption(
        self, *, after: int | None = None, before_completion: bool = False
    ) -> None:
        estate = self.copy_pre_record_estate()
        packet, receipt_path, transaction = self.reset_materialization(estate)
        arguments = {
            "packet": packet,
            "admission_receipt": estate / "receipts" / "admission-admissible.json",
            "candidates": estate / "admission",
            "repository": REPOSITORY_ROOT,
            "profile_path": PROFILE,
            "transaction_workspace": transaction,
            "completion_receipt": receipt_path,
            "source_execution_receipt": estate / "receipts" / "materialize-or-resume-execution.json",
        }
        with self.assertRaises(materialization_bridge.MaterializationError) as caught:
            materialization_bridge.materialize_evidence(
                **arguments,
                interrupt_after_bodies=after,
                interrupt_before_completion=before_completion,
            )
        self.assertEqual(caught.exception.code, "MATERIALIZATION_INTERRUPTED")
        resumed = materialization_bridge.materialize_evidence(**arguments)
        self.assertEqual(resumed, self.walk.materialization_receipt)
        self.assertEqual(load_json(receipt_path), resumed)
        state = load_json(transaction / "materialization-transaction.json")
        self.assertEqual(state["status"], "complete")
        self.assertEqual(state["promotedPhysicalBodyCount"], 43)
        self.assertEqual(len(list(packet.glob("*/evidence/*"))), 43)

    def test_materialization_resumes_after_one_promoted_body(self) -> None:
        self.materialize_with_interruption(after=1)

    def test_materialization_resumes_after_twenty_promoted_bodies(self) -> None:
        self.materialize_with_interruption(after=20)

    def test_materialization_resumes_after_all_bodies_before_completion_receipt(self) -> None:
        self.materialize_with_interruption(before_completion=True)

    def resume_recording(
        self, *, after_stage: int | None = None, phase: str | None = None
    ) -> tuple[Path, dict]:
        estate = self.copy_pre_record_estate()
        arguments = {
            "packet": estate / "campaign" / "stc-mary-private-flight-successor",
            "admission_receipt": estate / "receipts" / "admission-admissible.json",
            "materialization_receipt": estate / "receipts" / "evidence-materialization.json",
            "authentication_receipt": estate / "receipts" / "authentication.json",
            "candidates": estate / "admission",
            "repository": REPOSITORY_ROOT,
            "transaction_workspace": estate / "receipts" / "recording-transactions",
            "source_execution_receipt": self.walk.recording_execution_receipt_path,
        }
        with self.assertRaises(law.SuccessorFlightError) as caught:
            orchestrator.orchestrate(
                **arguments, interrupt_after_stage=after_stage, interrupt_phase=phase
            )
        self.assertEqual(caught.exception.code, "RECORDING_INTERRUPTED")
        resumed = orchestrator.orchestrate(**arguments)
        self.assertEqual(resumed, self.walk.orchestration_receipt)
        packet = arguments["packet"]
        final = law.load_packet(law.load_profile(PROFILE), packet)["state"]
        baseline_packet = (
            self.walk.pre_seal_snapshot / "campaign" / "stc-mary-private-flight-successor"
        )
        baseline = law.load_packet(law.load_profile(PROFILE), baseline_packet)["state"]
        self.assertEqual(final, baseline)
        self.assertEqual(
            [path.read_bytes() for path in sorted(packet.glob("*/stage-record.json"))],
            [path.read_bytes() for path in sorted(baseline_packet.glob("*/stage-record.json"))],
        )
        return estate, resumed

    def test_recording_resumes_after_stage_one(self) -> None:
        self.resume_recording(after_stage=1)

    def test_recording_resumes_after_stage_seven(self) -> None:
        self.resume_recording(after_stage=7)

    def test_recording_resumes_after_stage_fifteen_and_converges_through_post_seal(self) -> None:
        estate, _ = self.resume_recording(after_stage=15)
        packet = estate / "campaign" / "stc-mary-private-flight-successor"
        receipts = estate / "receipts"
        closure_path = receipts / "pre-seal-closure.json"
        closure_execution_path = receipts / "close-pre-seal-execution.json"
        execution_bootstrap.execute(
            role="close-pre-seal",
            execution_receipt=closure_execution_path,
            packet=packet,
            repository=None,
            source_admission_receipt=None,
            module_args=[
                "--packet", str(packet),
                "--admission-receipt", str(receipts / "admission-admissible.json"),
                "--materialization-receipt", str(receipts / "evidence-materialization.json"),
                "--authentication-receipt", str(receipts / "authentication.json"),
                "--candidates", str(estate / "admission"),
                "--profile", "@profile",
                "--repository-root", str(REPOSITORY_ROOT),
                "--out", str(closure_path),
            ],
        )
        self.assertEqual(load_json(closure_path), self.walk.pre_seal_closure)
        sealed = estate / "campaign" / "stc-mary-private-flight-sealed-witness"
        seal_adapter.seal_packet(
            packet=packet,
            sealed=sealed,
            pre_seal_closure=closure_path,
            **closure_replay_arguments(estate),
            repository=REPOSITORY_ROOT,
            source_execution_receipt=self.walk.seal_execution_receipt_path,
        )
        detached = seal_adapter.verify_detached(sealed=sealed, repository=REPOSITORY_ROOT)
        detached_path = receipts / "detached-verification.json"
        law.write_canonical_json(detached_path, detached)
        post = post_seal.close_post_seal(
            packet=packet,
            sealed=sealed,
            pre_seal_closure=closure_path,
            pre_seal_execution_receipt=estate / "receipts" / "close-pre-seal-execution.json",
            admission_receipt=estate / "receipts" / "admission-admissible.json",
            materialization_receipt=estate / "receipts" / "evidence-materialization.json",
            authentication_receipt=estate / "receipts" / "authentication.json",
            candidates=estate / "admission",
            detached_verification=detached_path,
            profile_path=PROFILE,
            repository=REPOSITORY_ROOT,
        )
        self.assertEqual(post, self.walk.post_seal_closure)

    def test_recording_reconciles_record_promotion_before_state_promotion(self) -> None:
        self.resume_recording(phase="after-record-promotion")

    def test_recording_reconciles_state_promotion_before_transaction_completion(self) -> None:
        self.resume_recording(phase="after-state-promotion")


class AtomicSealRestartWitnesses(unittest.TestCase):
    """Crash reconciliation keeps the final sealed coordinate all-or-nothing."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.walk = shared_walk()

    def copy_pre_seal_estate(self) -> Path:
        target = Path(tempfile.mkdtemp(prefix="stc-mary-successor-seal-restart-")) / "estate"
        self.addCleanup(shutil.rmtree, target.parent, ignore_errors=True)
        shutil.copytree(self.walk.pre_seal_snapshot, target)
        return target

    def coordinates(self, estate: Path) -> tuple[Path, Path, Path, dict]:
        sealed = estate / "campaign" / "stc-mary-private-flight-sealed-witness"
        staging = sealed.parent / f".{sealed.name}.seal-staging"
        transaction = estate / "receipts" / "seal-transaction.json"
        arguments = {
            "packet": estate / "campaign" / "stc-mary-private-flight-successor",
            "sealed": sealed,
            "pre_seal_closure": estate / "receipts" / "pre-seal-closure.json",
            **closure_replay_arguments(estate),
            "repository": REPOSITORY_ROOT,
            "transaction_receipt": transaction,
            "source_execution_receipt": self.walk.seal_execution_receipt_path,
        }
        return sealed, staging, transaction, arguments

    def resume(self, estate: Path, **interrupt: Any) -> tuple[dict, dict]:
        sealed, staging, transaction, arguments = self.coordinates(estate)
        with self.assertRaises(law.SuccessorFlightError) as caught:
            seal_adapter.seal_packet(**arguments, **interrupt)
        self.assertEqual(caught.exception.code, "SEAL_INTERRUPTED")
        result = seal_adapter.seal_packet(**arguments)
        self.assertTrue(sealed.is_dir())
        self.assertFalse(staging.exists())
        self.assertEqual(load_json(transaction)["status"], "sealed_state_promoted")
        for key in ("marker", "run", "disposition", "verification", "manifest", "state"):
            self.assertEqual(result[key], self.walk.seal_result[key])
        return result, arguments

    def test_partial_temporary_directory_resumes_without_visible_final(self) -> None:
        estate = self.copy_pre_seal_estate()
        sealed, staging, _, arguments = self.coordinates(estate)
        with self.assertRaises(law.SuccessorFlightError) as caught:
            seal_adapter.seal_packet(**arguments, interrupt_after_file=1)
        self.assertEqual(caught.exception.code, "SEAL_INTERRUPTED")
        self.assertFalse(sealed.exists())
        self.assertEqual(len(list(staging.iterdir())), 1)
        result = seal_adapter.seal_packet(**arguments)
        self.assertEqual(result["manifest"], self.walk.seal_result["manifest"])
        self.assertTrue(sealed.is_dir())
        self.assertFalse(staging.exists())

    def test_complete_verified_temporary_directory_promotes_on_restart(self) -> None:
        estate = self.copy_pre_seal_estate()
        sealed, staging, _, arguments = self.coordinates(estate)
        with self.assertRaises(law.SuccessorFlightError) as caught:
            seal_adapter.seal_packet(**arguments, interrupt_after_staging_verification=True)
        self.assertEqual(caught.exception.code, "SEAL_INTERRUPTED")
        self.assertFalse(sealed.exists())
        self.assertEqual(len(list(staging.iterdir())), 5)
        result = seal_adapter.seal_packet(**arguments)
        self.assertEqual(result["verification"], self.walk.seal_result["verification"])

    def test_final_directory_promotes_packet_state_on_restart(self) -> None:
        estate = self.copy_pre_seal_estate()
        sealed, staging, _, arguments = self.coordinates(estate)
        with self.assertRaises(law.SuccessorFlightError) as caught:
            seal_adapter.seal_packet(**arguments, interrupt_after_promotion=True)
        self.assertEqual(caught.exception.code, "SEAL_INTERRUPTED")
        self.assertTrue(sealed.is_dir())
        self.assertFalse(staging.exists())
        state = law.load_packet(law.load_profile(PROFILE), arguments["packet"])["state"]
        self.assertFalse(state["sealed"])
        result = seal_adapter.seal_packet(**arguments)
        self.assertTrue(result["state"]["sealed"])

    def test_sealed_packet_completes_transaction_and_post_seal_on_restart(self) -> None:
        estate = self.copy_pre_seal_estate()
        result, arguments = self.resume(estate, interrupt_after_state_promotion=True)
        receipts = estate / "receipts"
        detached_path = receipts / "detached-verification.json"
        law.write_canonical_json(detached_path, result["verification"])
        closure = post_seal.close_post_seal(
            packet=arguments["packet"],
            sealed=arguments["sealed"],
            pre_seal_closure=arguments["pre_seal_closure"],
            pre_seal_execution_receipt=arguments["pre_seal_execution_receipt"],
            admission_receipt=arguments["admission_receipt"],
            materialization_receipt=arguments["materialization_receipt"],
            authentication_receipt=arguments["authentication_receipt"],
            candidates=arguments["candidates"],
            detached_verification=detached_path,
            profile_path=PROFILE,
            repository=REPOSITORY_ROOT,
            seal_transaction_receipt=arguments["transaction_receipt"],
        )
        self.assertEqual(closure, self.walk.post_seal_closure)
        self.assertEqual(load_json(arguments["transaction_receipt"])["status"], "complete")
        replayed = seal_adapter.seal_packet(**arguments)
        self.assertEqual(replayed["transaction"]["status"], "complete")

    def test_sealed_packet_without_final_directory_refuses(self) -> None:
        estate = self.copy_pre_seal_estate()
        _, arguments = self.resume(estate, interrupt_after_state_promotion=True)
        preserved = arguments["sealed"].with_name("preserved-sealed-result")
        shutil.move(arguments["sealed"], preserved)
        with self.assertRaises(law.SuccessorFlightError) as caught:
            seal_adapter.seal_packet(**arguments)
        self.assertEqual(caught.exception.code, "SEALED_STATE_WITHOUT_VALID_FINAL")

    def test_temporary_and_final_directories_together_refuse(self) -> None:
        estate = self.copy_pre_seal_estate()
        sealed, staging, _, arguments = self.coordinates(estate)
        with self.assertRaises(law.SuccessorFlightError):
            seal_adapter.seal_packet(**arguments, interrupt_after_promotion=True)
        self.assertTrue(sealed.is_dir())
        staging.mkdir()
        with self.assertRaises(law.SuccessorFlightError) as caught:
            seal_adapter.seal_packet(**arguments)
        self.assertEqual(caught.exception.code, "SEAL_TRANSACTION_INCONSISTENT")

    def test_inconsistent_temporary_prefix_refuses(self) -> None:
        estate = self.copy_pre_seal_estate()
        _, staging, _, arguments = self.coordinates(estate)
        with self.assertRaises(law.SuccessorFlightError):
            seal_adapter.seal_packet(**arguments, interrupt_after_file=1)
        next(staging.iterdir()).write_bytes(b'{"substituted":true}\n')
        with self.assertRaises(law.SuccessorFlightError) as caught:
            seal_adapter.seal_packet(**arguments)
        self.assertEqual(caught.exception.code, "SEAL_TRANSACTION_INCONSISTENT")


class OrderingWitnesses(unittest.TestCase):
    """Order is not decoration: a stage out of sequence is refused before it is read."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="stc-mary-successor-order-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.walk = SuccessorFlightWalk(self.tmp / "estate")
        self.walk.build_workstation()
        self.walk.materialize_predecessor()
        self.walk.compile()
        self.profile = law.load_profile(PROFILE)
        self.admission = law.load_admission_profile(REPOSITORY_ROOT, self.profile)

    def authorization(self, stage: str) -> dict:
        return {
            "stage": stage,
            "admissionId": cid("stcmarypacketevidenceadmission1", {"synthetic": True}),
            "stageConfirmationId": cid("stcmarypacketevidencestageconfirmation1", {"stage": stage}),
            "evidenceAdmissionRoot": cid("stcmarypacketevidencestageroot1", {"stage": stage}),
            "observationDigest": cid("stcmarypacketevidenceobservationdigest1", {"stage": stage}),
            "requiredTerminal": self.admission["stages"][stage]["requiredTerminal"],
            "controlQuestion": self.admission["stages"][stage]["controlQuestion"],
        }

    def test_recording_the_second_stage_first_refuses(self) -> None:
        second = self.walk.stages[1]
        with self.assertRaises(law.SuccessorFlightError) as caught:
            runtime.record_stage(
                profile=self.profile,
                admission=self.admission,
                packet=self.walk.packet,
                stage=second,
                authorization=self.authorization(second),
                role_rows=[],
            )
        self.assertEqual(caught.exception.code, "STAGE_OUT_OF_ORDER")

    def test_a_compiled_packet_carries_no_stage_record_yet(self) -> None:
        state = law.load_packet(self.profile, self.walk.packet)["state"]
        self.assertEqual(state["completedStageCount"], 0)
        self.assertEqual(state["nextStage"], self.walk.stages[0])
        self.assertEqual(list(self.walk.packet.glob("*/stage-record.json")), [])

    def test_the_verifier_refuses_the_frozen_predecessor_outright(self) -> None:
        """The successor boundary is the refusal that fires, not a generic one."""
        with self.assertRaises(packet_verifier.SuccessorPacketError) as caught:
            packet_verifier.verify_successor_packet(
                packet=self.walk.predecessor,
                profile_path=PROFILE,
                repository=self.walk.source_repository,
            )
        self.assertEqual(caught.exception.code, "DIRECT_FROZEN_PACKET_APPLICATION_FORBIDDEN")

    def test_a_direct_verifier_run_cannot_self_assert_bootstrap_authentication(self) -> None:
        receipt = packet_verifier.verify_successor_packet(
            packet=self.walk.packet,
            profile_path=PROFILE,
            repository=self.walk.source_repository,
        )
        self.assertEqual(receipt["status"], "PASS")
        self.assertFalse(receipt["bootstrapAuthenticated"])
        self.assertIsNone(receipt["measuredVerifierSha256"])
        self.assertNotIn("measured-verifier-member-binding", receipt["checks"])

    def test_a_second_compilation_into_the_same_coordinate_refuses(self) -> None:
        with self.assertRaises(law.SuccessorFlightError) as caught:
            compiler.compile_successor_packet(
                workstation=self.walk.workstation,
                predecessor=self.walk.predecessor,
                successor=self.walk.packet,
                repository=self.walk.source_repository,
                source_admission_receipt=self.walk.source_admission_path,
            )
        self.assertEqual(caught.exception.code, "SUCCESSOR_OUTPUT_EXISTS")


class PacketCarriedExecutionCustodyWitnesses(unittest.TestCase):
    """The ambient repository cannot supply a successor execution module."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.walk = shared_walk()
        cls.receipt_path = cls.walk.receipts / "status-execution-custody.json"
        cls.receipt = execution_launcher.execute(
            role="status",
            execution_receipt_path=cls.receipt_path,
            module_args=["status", "--packet", str(cls.walk.packet)],
            packet=cls.walk.packet,
        )

    def packet_copy(self, name: str) -> Path:
        root = Path(tempfile.mkdtemp(prefix=f"stc-mary-custody-{name}-"))
        atexit.register(shutil.rmtree, root, ignore_errors=True)
        packet = root / "packet"
        shutil.copytree(self.walk.packet, packet)
        return packet

    def invoke_status(self, packet: Path, name: str, role: str = "status") -> dict[str, Any]:
        return execution_launcher.execute(
            role=role,
            execution_receipt_path=packet.parent / f"{name}-execution.json",
            module_args=["status", "--packet", str(packet)],
            packet=packet,
        )

    def invoke_status_bootstrap(self, packet: Path, name: str) -> dict[str, Any]:
        path = packet.parent / f"{name}-bootstrap-execution.json"
        execution_bootstrap.execute(
            role="status",
            execution_receipt=path,
            module_args=["status", "--packet", str(packet)],
            packet=packet,
            repository=None,
            source_admission_receipt=None,
        )
        return load_json(path)

    def test_status_executes_from_complete_packet_source_custody(self) -> None:
        receipt = self.receipt
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["processTerminal"], "PASS")
        self.assertEqual(receipt["operationRole"], "status")
        self.assertEqual(receipt["packetId"], self.walk.packet_id)
        self.assertEqual(receipt["sourceAdmissionId"], self.walk.source_admission["sourceAdmissionId"])
        self.assertEqual(receipt["successorSourceSetId"], self.walk.compile_receipt["successorSourceSetId"])
        self.assertEqual(receipt["completeMeasuredSourceSetId"], self.walk.compile_receipt["successorSourceSetId"])
        self.assertEqual((receipt["isolated"], receipt["noSite"], receipt["dontWriteBytecode"]), (1, 1, 1))
        self.assertFalse(receipt["ambientRepositorySourceTrusted"])
        self.assertEqual(load_json(self.receipt_path), receipt)

    def test_ambient_repository_drift_after_compilation_is_ignored(self) -> None:
        repository_path = "mating_surface/anchor_node/stc_mary_successor_packet_runtime.py"
        ambient = self.walk.source_repository / repository_path
        original = ambient.read_bytes()
        try:
            ambient.write_bytes(b"raise SystemExit('ambient drift must never execute')\n")
            receipt = self.invoke_status(self.walk.packet, "ambient-drift")
            self.assertEqual(receipt["processTerminal"], "PASS")
            self.assertEqual(receipt["moduleSha256"], law.sha256_bytes(
                (self.walk.packet / "lineage/successor-source/anchor_node/stc_mary_successor_packet_runtime.py").read_bytes()
            ))
        finally:
            ambient.write_bytes(original)

    def test_ambient_launcher_changed_has_no_effect(self) -> None:
        ambient = ANCHOR / "invoke_stc_mary_successor_packet_source.py"
        original = ambient.read_bytes()
        try:
            ambient.write_bytes(b"raise SystemExit('ambient launcher must never execute')\n")
            receipt = self.invoke_status_bootstrap(self.walk.packet, "ambient-launcher-drift")
            self.assertEqual(receipt["processTerminal"], "PASS")
            self.assertFalse(receipt["ambientRepositorySourceTrusted"])
        finally:
            ambient.write_bytes(original)

    def test_packet_carried_launcher_changed_refuses_before_execution(self) -> None:
        packet = self.packet_copy("launcher-drift")
        launcher = packet / "lineage/successor-source/anchor_node/invoke_stc_mary_successor_packet_source.py"
        launcher.write_bytes(b"raise SystemExit('substituted packet launcher')\n")
        with self.assertRaises(execution_bootstrap.LauncherBootstrapError) as caught:
            self.invoke_status_bootstrap(packet, "launcher-drift")
        self.assertEqual(caught.exception.code, "MEASURED_SOURCE_MEMBER_DRIFT")

    def test_user_site_pythonpath_and_sitecustomize_cannot_influence_imports(self) -> None:
        hostile = Path(tempfile.mkdtemp(prefix="stc-mary-hostile-user-site-"))
        self.addCleanup(shutil.rmtree, hostile, ignore_errors=True)
        (hostile / "sitecustomize.py").write_text("raise SystemExit('sitecustomize imported')\n", encoding="utf-8")
        (hostile / "stc_mary_successor_flight_law.py").write_text("raise SystemExit('fallback imported')\n", encoding="utf-8")
        with mock.patch.dict(
            os.environ,
            {"PYTHONPATH": str(hostile), "PYTHONUSERBASE": str(hostile), "PYTHONSTARTUP": str(hostile / "sitecustomize.py")},
            clear=False,
        ):
            receipt = self.invoke_status_bootstrap(self.walk.packet, "hostile-user-site")
        self.assertEqual((receipt["isolated"], receipt["noSite"], receipt["dontWriteBytecode"]), (1, 1, 1))

    def test_source_receipt_for_another_tree_refuses(self) -> None:
        packet = self.packet_copy("foreign-tree")
        admission_path = packet / self.walk.profile["lineage"]["sourceAdmissionFile"]
        admission = load_json(admission_path)
        admission["sourceTree"] = "0" * len(admission["sourceTree"])
        law.write_canonical_json(admission_path, admission)
        with self.assertRaises(execution_bootstrap.LauncherBootstrapError) as caught:
            self.invoke_status_bootstrap(packet, "foreign-tree")
        self.assertEqual(caught.exception.code, "SOURCE_ADMISSION_IDENTITY_INVALID")

    def test_packet_member_drift_refuses_while_repository_copy_is_intact(self) -> None:
        packet = self.packet_copy("member-drift")
        module = packet / "lineage/successor-source/anchor_node/stc_mary_successor_packet_runtime.py"
        module.write_bytes(module.read_bytes() + b"\n# drift\n")
        with self.assertRaises(execution_launcher.ExecutionCustodyError) as caught:
            self.invoke_status(packet, "member-drift")
        self.assertEqual(caught.exception.code, "PACKET_SOURCE_MEMBER_DRIFT")


class FinalExecutionReceiptWitnesses(unittest.TestCase):
    """The final receipt, ten-role map, and mutation identity are executable law."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.walk = shared_walk()
        cls.profile = cls.walk.profile
        cls.base_receipt = execution_launcher.execute(
            role="status",
            execution_receipt_path=cls.walk.receipts / "final-receipt-hostile-status.json",
            module_args=["status", "--packet", str(cls.walk.packet)],
            packet=cls.walk.packet,
        )

    def packet_copy(self, name: str) -> Path:
        root = Path(tempfile.mkdtemp(prefix=f"stc-mary-final-custody-{name}-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        packet = root / "packet"
        shutil.copytree(self.walk.packet, packet)
        return packet

    def invoke_status(self, packet: Path, name: str, role: str = "status") -> dict[str, Any]:
        return execution_launcher.execute(
            role=role,
            execution_receipt_path=packet.parent / f"{name}-execution.json",
            module_args=["status", "--packet", str(packet)],
            packet=packet,
        )

    def forged_receipt(self, mutate, name: str) -> Path:
        body = copy.deepcopy(self.base_receipt)
        custody = self.profile["executionCustody"]
        body.pop(custody["idKey"], None)
        mutate(body)
        forged = law.sign(body, custody["idKey"], custody["idPrefix"])
        root = Path(tempfile.mkdtemp(prefix=f"stc-mary-execution-receipt-{name}-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        path = root / "receipt.json"
        law.write_canonical_json(path, forged)
        return path

    def verify_forged(self, path: Path, expected_role: str = "status") -> None:
        execution_receipt_verifier.verify_execution_receipt(
            profile=self.profile,
            execution_receipt=path,
            expected_role=expected_role,
            packet=self.walk.packet,
        )

    def test_execution_receipt_naming_another_git_blob_refuses(self) -> None:
        path = self.forged_receipt(lambda body: body.update({"moduleGitBlobId": "0" * len(body["moduleGitBlobId"])}), "blob")
        with self.assertRaises(execution_receipt_verifier.ExecutionReceiptError) as caught:
            self.verify_forged(path)
        self.assertEqual(caught.exception.code, "EXECUTION_MODULE_MEMBER_INVALID")

    def test_wrong_operation_role_refuses(self) -> None:
        path = self.forged_receipt(lambda body: body.update({"operationRole": "verify-detached"}), "role")
        with self.assertRaises(execution_receipt_verifier.ExecutionReceiptError) as caught:
            self.verify_forged(path)
        self.assertEqual(caught.exception.code, "EXECUTION_ROLE_MISMATCH")

    def test_one_role_mapped_to_another_admitted_module_refuses(self) -> None:
        mapping = self.profile["executionCustody"]["roles"]["verify-detached"]
        path = self.forged_receipt(
            lambda body: body.update({
                "repositoryRelativeModulePath": mapping["repositoryPath"],
                "packetRelativeModulePath": mapping["packetPath"],
            }),
            "mapped-module",
        )
        with self.assertRaises(execution_receipt_verifier.ExecutionReceiptError) as caught:
            self.verify_forged(path)
        self.assertEqual(caught.exception.code, "EXECUTION_ROLE_MODULE_MISMATCH")

    def test_receipt_verifier_consumes_ambient_repository_trust_false(self) -> None:
        path = self.forged_receipt(lambda body: body.update({"ambientRepositorySourceTrusted": True}), "ambient-trust")
        with self.assertRaises(execution_receipt_verifier.ExecutionReceiptError) as caught:
            self.verify_forged(path)
        self.assertEqual(caught.exception.code, "EXECUTION_RECEIPT_TERMINAL_INVALID")

    def test_launcher_self_authentication_refuses(self) -> None:
        path = self.forged_receipt(lambda body: body.update({"bootstrapAuthenticated": True}), "self-authentication")
        with self.assertRaises(execution_receipt_verifier.ExecutionReceiptError) as caught:
            self.verify_forged(path)
        self.assertEqual(caught.exception.code, "EXECUTION_RECEIPT_INVALID")

    def test_environment_only_source_execution_identity_refuses(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="stc-mary-environment-only-execution-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        estate = root / "estate"
        shutil.copytree(self.walk.pre_record_snapshot, estate)
        with mock.patch.dict(os.environ, {"STC_MARY_SOURCE_EXECUTION_IDENTITY": "environment-only"}, clear=False):
            with self.assertRaises(law.SuccessorFlightError) as caught:
                orchestrator.orchestrate(
                    packet=estate / "campaign/stc-mary-private-flight-successor",
                    admission_receipt=estate / "receipts/admission-admissible.json",
                    materialization_receipt=estate / "receipts/evidence-materialization.json",
                    authentication_receipt=estate / "receipts/authentication.json",
                    candidates=estate / "admission",
                    repository=REPOSITORY_ROOT,
                    transaction_workspace=estate / "receipts/recording-transactions",
                    source_execution_receipt=None,
                )
        self.assertEqual(caught.exception.code, "SOURCE_EXECUTION_RECEIPT_ABSENT")

    def test_profile_exposes_exact_final_ten_role_map(self) -> None:
        expected = {
            "compile", "verify-packet", "verify-evidence-materialization", "materialize-or-resume",
            "record-or-resume", "close-pre-seal", "seal-or-resume", "verify-detached",
            "close-post-seal", "status",
        }
        custody = self.profile["executionCustody"]
        self.assertEqual(set(custody["roleDenominator"]), expected)
        self.assertEqual(set(custody["roles"]), expected)
        self.assertEqual(len(custody["roles"]), 10)
        for role, mapping in custody["roles"].items():
            self.assertEqual(self.profile["successorSourceMembers"][mapping["repositoryPath"]], mapping["packetPath"], role)

    def test_all_ten_roles_emit_independently_verified_receipts(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="stc-mary-ten-role-custody-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        receipts = {
            "compile": self.walk.compile_execution_receipt,
            "verify-packet": self.walk.verify_packet_execution_receipt,
            "materialize-or-resume": self.walk.materialization_execution_receipt,
            "record-or-resume": self.walk.recording_execution_receipt,
            "seal-or-resume": self.walk.seal_execution_receipt,
        }

        def run(role: str, packet: Path, arguments: list[str]) -> None:
            path = root / f"{role}.json"
            execution_bootstrap.execute(
                role=role,
                execution_receipt=path,
                module_args=arguments,
                packet=packet,
                repository=None,
                source_admission_receipt=None,
            )
            receipts[role] = load_json(path)

        pre_record = self.walk.pre_record_snapshot
        pre_record_packet = pre_record / "campaign/stc-mary-private-flight-successor"
        run("verify-evidence-materialization", pre_record_packet, [
            "--packet", str(pre_record_packet),
            "--admission-receipt", str(pre_record / "receipts/admission-admissible.json"),
            "--candidates", str(pre_record / "admission"),
            "--repository-root", str(REPOSITORY_ROOT),
            "--profile", "@profile",
            "--out", str(root / "verified-materialization.json"),
        ])
        pre_seal_packet = self.walk.pre_seal_snapshot / "campaign/stc-mary-private-flight-successor"
        run("close-pre-seal", pre_seal_packet, [
            "--packet", str(pre_seal_packet),
            "--admission-receipt", str(self.walk.pre_seal_snapshot / "receipts/admission-admissible.json"),
            "--materialization-receipt", str(self.walk.pre_seal_snapshot / "receipts/evidence-materialization.json"),
            "--authentication-receipt", str(self.walk.pre_seal_snapshot / "receipts/authentication.json"),
            "--candidates", str(self.walk.pre_seal_snapshot / "admission"),
            "--profile", "@profile", "--repository-root", str(REPOSITORY_ROOT),
            "--out", str(root / "pre-seal.json"),
        ])
        run("verify-detached", self.walk.packet, [
            "verify-detached", "--sealed", str(self.walk.sealed),
            "--repository-root", str(REPOSITORY_ROOT), "--out", str(root / "detached.json"),
        ])
        run("close-post-seal", self.walk.packet, [
            "--packet", str(self.walk.packet), "--sealed", str(self.walk.sealed),
            "--pre-seal-closure", str(self.walk.pre_seal_path),
            "--pre-seal-execution-receipt", str(root / "close-pre-seal.json"),
            "--admission-receipt", str(self.walk.receipts / "admission-admissible.json"),
            "--materialization-receipt", str(self.walk.materialization_path),
            "--authentication-receipt", str(self.walk.authentication_path),
            "--candidates", str(self.walk.candidates),
            "--detached-verification", str(self.walk.detached_path),
            "--profile", "@profile", "--repository-root", str(REPOSITORY_ROOT),
            "--out", str(root / "post-seal.json"),
        ])
        run("status", self.walk.packet, ["status", "--packet", str(self.walk.packet)])
        self.assertEqual(set(receipts), set(self.profile["executionCustody"]["roleDenominator"]))
        self.assertTrue(all(receipt["processTerminal"] == "PASS" for receipt in receipts.values()))

    def test_import_fallback_into_the_repository_is_impossible(self) -> None:
        packet = self.packet_copy("import-fallback")
        (packet / "lineage/successor-source/anchor_node/stc_mary_successor_flight_law.py").unlink()
        with self.assertRaises(execution_launcher.ExecutionCustodyError) as caught:
            self.invoke_status(packet, "import-fallback")
        self.assertEqual(caught.exception.code, "PACKET_SOURCE_MEMBER_DENOMINATOR_INVALID")

    def test_substituted_module_role_refuses(self) -> None:
        with self.assertRaises(execution_launcher.ExecutionCustodyError) as caught:
            self.invoke_status(self.walk.packet, "role-substitution", role="arbitrary-module")
        self.assertEqual(caught.exception.code, "MODULE_ROLE_UNADMITTED")

    def test_incomplete_packet_source_tree_refuses_before_execution(self) -> None:
        packet = self.packet_copy("incomplete-tree")
        member = packet / "lineage/successor-source/anchor_node/stc_mary_successor_packet_runtime.py"
        member.unlink()
        member.mkdir()
        with self.assertRaises(execution_launcher.ExecutionCustodyError) as caught:
            self.invoke_status(packet, "incomplete-tree")
        self.assertEqual(caught.exception.code, "PACKET_SOURCE_MEMBER_DENOMINATOR_INVALID")

    def test_source_receipt_from_another_commit_refuses(self) -> None:
        packet = self.packet_copy("foreign-source-receipt")
        path = packet / self.walk.profile["lineage"]["sourceAdmissionFile"]
        repository_member = self.walk.source_repository / "mating_surface/anchor_node/stc_mary_successor_packet_runtime.py"
        original = repository_member.read_bytes()
        try:
            repository_member.write_bytes(original + b"\n# foreign source commit\n")
            git(self.walk.source_repository, "add", "--all")
            git(self.walk.source_repository, "commit", "--quiet", "-m", "foreign source set")
            foreign_commit = git(self.walk.source_repository, "rev-parse", "HEAD")
            foreign_receipt = source_bootstrap.authenticate(
                repository=self.walk.source_repository, source_commit=foreign_commit
            )
        finally:
            repository_member.write_bytes(original)
        law.write_canonical_json(path, foreign_receipt)
        with self.assertRaises(execution_launcher.ExecutionCustodyError) as caught:
            self.invoke_status(packet, "foreign-source-receipt")
        self.assertEqual(caught.exception.code, "PACKET_SOURCE_MEMBER_DRIFT")

    def test_correct_member_count_with_one_member_replaced_refuses(self) -> None:
        packet = self.packet_copy("one-replaced")
        relative = "anchor_node/stc_mary_successor_packet_runtime.py"
        module = packet / "lineage/successor-source" / relative
        module.write_bytes(b"raise SystemExit('replacement')\n")
        source_set_path = packet / self.walk.profile["lineage"]["sourceSetFile"]
        source_set = load_json(source_set_path)
        row = next(row for row in source_set["members"] if row["relativePath"] == relative)
        row["sha256"] = law.sha256_bytes(module.read_bytes())
        row["bytes"] = len(module.read_bytes())
        source_set["totalBytes"] = sum(row["bytes"] for row in source_set["members"])
        source_set.pop(self.walk.profile["lineage"]["sourceSetIdKey"])
        law.write_canonical_json(
            source_set_path,
            law.sign(source_set, self.walk.profile["lineage"]["sourceSetIdKey"], self.walk.profile["lineage"]["sourceSetIdPrefix"]),
        )
        with self.assertRaises(execution_launcher.ExecutionCustodyError) as caught:
            self.invoke_status(packet, "one-replaced")
        self.assertEqual(caught.exception.code, "PACKET_SOURCE_MEMBER_DRIFT")


class PowerShellOperatorEntrypointWitnesses(unittest.TestCase):
    """Execute and hostile-test the admitted PowerShell ten-role operator surface."""

    ROLE_MODULES = {
        "compile": (
            "mating_surface/anchor_node/stc_mary_successor_packet_compiler.py",
            "anchor_node/stc_mary_successor_packet_compiler.py",
        ),
        "verify-packet": (
            "mating_surface/anchor_node/verify_stc_mary_successor_packet_bootstrap.py",
            "anchor_node/verify_stc_mary_successor_packet_bootstrap.py",
        ),
        "verify-evidence-materialization": (
            "mating_surface/anchor_node/verify_stc_mary_successor_evidence_materialization.py",
            "anchor_node/verify_stc_mary_successor_evidence_materialization.py",
        ),
        "materialize-or-resume": (
            "mating_surface/anchor_node/verify_stc_mary_successor_evidence_materialization.py",
            "anchor_node/verify_stc_mary_successor_evidence_materialization.py",
        ),
        "record-or-resume": (
            "mating_surface/anchor_node/stc_mary_successor_packet_orchestrator.py",
            "anchor_node/stc_mary_successor_packet_orchestrator.py",
        ),
        "close-pre-seal": (
            "mating_surface/anchor_node/verify_stc_mary_successor_pre_seal_closure.py",
            "anchor_node/verify_stc_mary_successor_pre_seal_closure.py",
        ),
        "seal-or-resume": (
            "mating_surface/anchor_node/stc_mary_successor_seal_adapter.py",
            "anchor_node/stc_mary_successor_seal_adapter.py",
        ),
        "verify-detached": (
            "mating_surface/anchor_node/stc_mary_successor_seal_adapter.py",
            "anchor_node/stc_mary_successor_seal_adapter.py",
        ),
        "close-post-seal": (
            "mating_surface/anchor_node/verify_stc_mary_successor_post_seal_closure.py",
            "anchor_node/verify_stc_mary_successor_post_seal_closure.py",
        ),
        "status": (
            "mating_surface/anchor_node/stc_mary_successor_packet_runtime.py",
            "anchor_node/stc_mary_successor_packet_runtime.py",
        ),
    }

    @classmethod
    def setUpClass(cls) -> None:
        cls.walk = shared_walk()
        cls.profile = cls.walk.profile
        cls.shell = shutil.which("pwsh") or shutil.which("powershell")
        if cls.shell is None:
            raise AssertionError("PowerShell is required to qualify the admitted PS1 operator entrypoint")
        cls.operator = (
            cls.walk.source_repository
            / "mating_surface/anchor_node/stc-mary-successor-packet-flight-01.ps1"
        )
        row = next(
            member for member in cls.walk.source_admission["members"]
            if member["repositoryPath"]
            == "mating_surface/anchor_node/stc-mary-successor-packet-flight-01.ps1"
        )
        admitted = subprocess.check_output(
            [
                "git", "-c", f"safe.directory={cls.walk.source_repository}",
                "-C", str(cls.walk.source_repository), "cat-file", "blob", row["gitBlob"],
            ]
        )
        if cls.operator.read_bytes() != admitted:
            raise AssertionError("the executed PS1 differs from its admitted Git blob")
        if law.sha256_bytes(admitted) != row["sha256"] or len(admitted) != row["bytes"]:
            raise AssertionError("the executed PS1 differs from its source-admission measurement")

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="stc-mary-powershell-operator-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.foreign_cwd = self.root / "foreign-working-directory"
        self.foreign_cwd.mkdir()
        self.assertFalse(law.is_within(self.foreign_cwd, REPOSITORY_ROOT))
        self.assertFalse(law.is_within(self.foreign_cwd, self.walk.source_repository))

    def invoke(
        self, operator: Path, command: str, arguments: list[str], *, python: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        invocation = [
            self.shell, "-NoLogo", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-File", str(operator), command,
            "-Python", sys.executable if python is None else python,
            *arguments,
        ]
        return subprocess.run(
            invocation,
            cwd=self.foreign_cwd,
            env=execution_launcher.scrubbed_environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            check=False,
        )

    def require_success(
        self,
        role: str,
        packet: Path | None,
        arguments: list[str],
        *,
        source_admission_receipt: Path | None = None,
    ) -> Mapping[str, Any]:
        execution_receipt = self.root / "execution-receipts" / f"{role}.json"
        execution_receipt.parent.mkdir(exist_ok=True)
        completed = self.invoke(
            self.operator,
            role,
            ["-ExecutionReceipt", str(execution_receipt), *arguments],
        )
        self.assertEqual(
            completed.returncode,
            0,
            f"{role} failed through admitted PS1\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
        )
        receipt = execution_receipt_verifier.verify_execution_receipt(
            profile=self.profile,
            execution_receipt=execution_receipt,
            expected_role=role,
            packet=packet,
            source_admission_receipt=source_admission_receipt,
        )
        repository_path, packet_path = self.ROLE_MODULES[role]
        row = next(
            member for member in self.walk.source_admission["members"]
            if member["repositoryPath"] == repository_path
        )
        self.assertEqual(receipt["operationRole"], role)
        self.assertEqual(receipt["repositoryRelativeModulePath"], repository_path)
        self.assertEqual(receipt["packetRelativeModulePath"], packet_path)
        self.assertEqual(receipt["moduleGitBlobId"], row["gitBlob"])
        self.assertEqual(
            receipt["completeMeasuredSourceSetId"],
            self.walk.source_admission["successorSourceSetId"],
        )
        self.assertIs(receipt["ambientRepositorySourceTrusted"], False)
        self.assertEqual(receipt["authority"], "none")
        return receipt

    def copy_estate(self, source: Path, name: str) -> Path:
        estate = self.root / name
        shutil.copytree(source, estate)
        return estate

    def trace_arguments(self, operator: Path, command: str, arguments: list[str]) -> tuple[int, list[str]]:
        trace = self.root / f"trace-{command}.json"
        tracer = self.root / f"trace-{command}.py"
        tracer.write_text(
            "import json,sys\n"
            "from pathlib import Path\n"
            f"Path({str(trace)!r}).write_text(json.dumps(sys.argv[1:]), encoding='utf-8')\n",
            encoding="utf-8",
            newline="\n",
        )
        if os.name == "nt":
            wrapper = self.root / f"trace-{command}.cmd"
            wrapper.write_text(
                f'@echo off\r\n"{sys.executable}" "{tracer}" %*\r\n',
                encoding="utf-8",
                newline="",
            )
        else:
            import shlex

            wrapper = self.root / f"trace-{command}.sh"
            wrapper.write_text(
                f"#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(tracer))} \"$@\"\n",
                encoding="utf-8",
                newline="\n",
            )
            wrapper.chmod(0o700)
        completed = self.invoke(operator, command, arguments, python=str(wrapper))
        return completed.returncode, load_json(trace) if trace.is_file() else []

    def trace_parameters(self, command: str) -> list[str]:
        value = str(self.root / "synthetic-coordinate")
        common = ["-ExecutionReceipt", str(self.root / f"{command}-execution.json")]
        by_role = {
            "compile": ["-Workstation", value, "-Predecessor", value, "-Packet", value,
                        "-SourceAdmissionReceipt", value, "-Out", value],
            "verify-packet": ["-Packet", value, "-Out", value],
            "verify-evidence-materialization": [
                "-Packet", value, "-AdmissionReceipt", value, "-Candidates", value, "-Out", value,
            ],
            "materialize-or-resume": [
                "-Packet", value, "-AdmissionReceipt", value, "-Candidates", value, "-Out", value,
            ],
            "record-or-resume": [
                "-Packet", value, "-AdmissionReceipt", value, "-MaterializationReceipt", value,
                "-AuthenticationReceipt", value, "-Candidates", value, "-Out", value,
            ],
            "close-pre-seal": [
                "-Packet", value, "-AdmissionReceipt", value, "-MaterializationReceipt", value,
                "-AuthenticationReceipt", value, "-Candidates", value, "-Out", value,
            ],
            "seal-or-resume": [
                "-Packet", value, "-Sealed", value, "-PreSealClosure", value,
                "-PreSealExecutionReceipt", value, "-AdmissionReceipt", value,
                "-MaterializationReceipt", value, "-AuthenticationReceipt", value,
                "-Candidates", value, "-Out", value,
            ],
            "verify-detached": ["-Packet", value, "-Sealed", value, "-Out", value],
            "close-post-seal": [
                "-Packet", value, "-Sealed", value, "-PreSealClosure", value,
                "-PreSealExecutionReceipt", value, "-AdmissionReceipt", value,
                "-MaterializationReceipt", value, "-AuthenticationReceipt", value,
                "-Candidates", value, "-DetachedVerification", value, "-Out", value,
            ],
            "status": ["-Packet", value],
        }
        return [*common, *by_role[command]]

    def assert_dispatch(
        self, operator: Path, command: str, profile: Mapping[str, Any] | None = None,
    ) -> None:
        profile = self.profile if profile is None else profile
        expected_repository, expected_packet = self.ROLE_MODULES[command]
        mapping = profile["executionCustody"]["roles"][command]
        self.assertEqual(mapping["repositoryPath"], expected_repository)
        self.assertEqual(mapping["packetPath"], expected_packet)
        returncode, traced = self.trace_arguments(operator, command, self.trace_parameters(command))
        self.assertEqual(returncode, 0)
        self.assertGreaterEqual(len(traced), 7, "the PS1 did not dispatch through Python")
        self.assertEqual(traced[:3], ["-I", "-S", "-B"])
        self.assertEqual(
            Path(traced[3]).resolve(),
            (operator.parent / "invoke_stc_mary_successor_packet_source_bootstrap.py").resolve(),
        )
        role_index = traced.index("--role")
        self.assertEqual(traced[role_index + 1], command)

    def mutated_operator(self, old: bytes, new: bytes, name: str) -> Path:
        anchor = self.root / name / "mating_surface" / "anchor_node"
        anchor.mkdir(parents=True)
        data = self.operator.read_bytes()
        self.assertEqual(data.count(old), 1, name)
        (anchor / self.operator.name).write_bytes(data.replace(old, new, 1))
        for launcher in (
            "invoke_stc_mary_successor_packet_source_bootstrap.py",
            "invoke_stc_mary_successor_packet_source.py",
        ):
            (anchor / launcher).write_bytes(b"# qualification trace placeholder\n")
        return anchor / self.operator.name

    def test_actual_admitted_ps1_dispatches_all_ten_roles_with_verified_receipts(self) -> None:
        compile_root = self.root / "compile"
        workstation = compile_root / "workstation"
        predecessor = compile_root / "predecessor"
        packet = compile_root / "successor"
        shutil.copytree(self.walk.workstation, workstation)
        shutil.copytree(self.walk.predecessor, predecessor)
        receipts: dict[str, Mapping[str, Any]] = {}
        receipts["compile"] = self.require_success(
            "compile",
            None,
            [
                "-Workstation", str(workstation), "-Predecessor", str(predecessor),
                "-Packet", str(packet), "-SourceAdmissionReceipt", str(self.walk.source_admission_path),
                "-Out", str(compile_root / "compile.json"),
            ],
            source_admission_receipt=self.walk.source_admission_path,
        )
        receipts["verify-packet"] = self.require_success(
            "verify-packet", packet,
            ["-Packet", str(packet), "-Out", str(compile_root / "verify-packet.json")],
        )

        evidence_estate = self.copy_estate(self.walk.pre_record_snapshot, "evidence-estate")
        evidence_packet = evidence_estate / "campaign/stc-mary-private-flight-successor"
        evidence_admission = evidence_estate / "receipts/admission-admissible.json"
        evidence_candidates = evidence_estate / "admission"
        receipts["verify-evidence-materialization"] = self.require_success(
            "verify-evidence-materialization", evidence_packet,
            [
                "-Packet", str(evidence_packet), "-AdmissionReceipt", str(evidence_admission),
                "-Candidates", str(evidence_candidates),
                "-Out", str(evidence_estate / "receipts/ps-verify-materialization.json"),
            ],
        )
        receipts["materialize-or-resume"] = self.require_success(
            "materialize-or-resume", evidence_packet,
            [
                "-Packet", str(evidence_packet), "-AdmissionReceipt", str(evidence_admission),
                "-Candidates", str(evidence_candidates),
                "-TransactionWorkspace", str(evidence_estate / "receipts/materialization-transaction"),
                "-Out", str(evidence_estate / "receipts/evidence-materialization.json"),
            ],
        )

        recording_estate = self.copy_estate(self.walk.pre_record_snapshot, "recording-estate")
        recording_packet = recording_estate / "campaign/stc-mary-private-flight-successor"
        recording_receipts = recording_estate / "receipts"
        receipts["record-or-resume"] = self.require_success(
            "record-or-resume", recording_packet,
            [
                "-Packet", str(recording_packet),
                "-AdmissionReceipt", str(recording_receipts / "admission-admissible.json"),
                "-MaterializationReceipt", str(recording_receipts / "evidence-materialization.json"),
                "-AuthenticationReceipt", str(recording_receipts / "authentication.json"),
                "-Candidates", str(recording_estate / "admission"),
                "-TransactionWorkspace", str(recording_receipts / "ps-recording-transactions"),
                "-Out", str(recording_receipts / "ps-orchestration.json"),
            ],
        )

        sealing_estate = self.copy_estate(self.walk.pre_seal_snapshot, "sealing-estate")
        sealing_packet = sealing_estate / "campaign/stc-mary-private-flight-successor"
        sealing_receipts = sealing_estate / "receipts"
        pre_seal_path = sealing_receipts / "ps-pre-seal.json"
        receipts["close-pre-seal"] = self.require_success(
            "close-pre-seal", sealing_packet,
            [
                "-Packet", str(sealing_packet),
                "-AdmissionReceipt", str(sealing_receipts / "admission-admissible.json"),
                "-MaterializationReceipt", str(sealing_receipts / "evidence-materialization.json"),
                "-AuthenticationReceipt", str(sealing_receipts / "authentication.json"),
                "-Candidates", str(sealing_estate / "admission"), "-Out", str(pre_seal_path),
            ],
        )
        pre_seal_execution_path = self.root / "execution-receipts" / "close-pre-seal.json"
        pre_seal_bytes = pre_seal_path.read_bytes()
        self.assertEqual(receipts["close-pre-seal"]["outputArtifactId"], load_json(pre_seal_path)["preSealClosureId"])
        self.assertEqual(receipts["close-pre-seal"]["outputArtifactSha256"], law.sha256_bytes(pre_seal_bytes))
        self.assertEqual(receipts["close-pre-seal"]["outputArtifactBytes"], len(pre_seal_bytes))
        sealed = self.root / "stc-mary-private-flight-sealed-ps-witness"
        seal_transaction = sealing_receipts / "ps-seal-transaction.json"
        receipts["seal-or-resume"] = self.require_success(
            "seal-or-resume", sealing_packet,
            [
                "-Packet", str(sealing_packet), "-Sealed", str(sealed),
                "-PreSealClosure", str(pre_seal_path),
                "-PreSealExecutionReceipt", str(pre_seal_execution_path),
                "-AdmissionReceipt", str(sealing_receipts / "admission-admissible.json"),
                "-MaterializationReceipt", str(sealing_receipts / "evidence-materialization.json"),
                "-AuthenticationReceipt", str(sealing_receipts / "authentication.json"),
                "-Candidates", str(sealing_estate / "admission"),
                "-SealTransactionReceipt", str(seal_transaction),
                "-Out", str(sealing_receipts / "ps-seal.json"),
            ],
        )
        detached_path = sealing_receipts / "ps-detached.json"
        receipts["verify-detached"] = self.require_success(
            "verify-detached", sealing_packet,
            ["-Packet", str(sealing_packet), "-Sealed", str(sealed), "-Out", str(detached_path)],
        )
        receipts["close-post-seal"] = self.require_success(
            "close-post-seal", sealing_packet,
            [
                "-Packet", str(sealing_packet), "-Sealed", str(sealed),
                "-PreSealClosure", str(pre_seal_path),
                "-PreSealExecutionReceipt", str(pre_seal_execution_path),
                "-AdmissionReceipt", str(sealing_receipts / "admission-admissible.json"),
                "-MaterializationReceipt", str(sealing_receipts / "evidence-materialization.json"),
                "-AuthenticationReceipt", str(sealing_receipts / "authentication.json"),
                "-Candidates", str(sealing_estate / "admission"),
                "-DetachedVerification", str(detached_path),
                "-SealTransactionReceipt", str(seal_transaction),
                "-Out", str(sealing_receipts / "ps-post-seal.json"),
            ],
        )
        receipts["status"] = self.require_success(
            "status", sealing_packet, ["-Packet", str(sealing_packet)],
        )
        self.assertEqual(set(receipts), set(self.ROLE_MODULES))

    def test_ps1_wrong_role_route_is_detected(self) -> None:
        operator = self.mutated_operator(
            b"Invoke-MeasuredSurface -Role 'status' -Arguments $arguments",
            b"Invoke-MeasuredSurface -Role 'verify-detached' -Arguments $arguments",
            "wrong-role-route",
        )
        with self.assertRaises(AssertionError):
            self.assert_dispatch(operator, "status")

    def test_ps1_measured_bootstrap_bypass_is_detected(self) -> None:
        operator = self.mutated_operator(
            b"invoke_stc_mary_successor_packet_source_bootstrap.py",
            b"invoke_stc_mary_successor_packet_source.py",
            "bootstrap-bypass",
        )
        with self.assertRaises(AssertionError):
            self.assert_dispatch(operator, "status")

    def test_ps1_missing_final_command_is_detected(self) -> None:
        operator = self.mutated_operator(b"'status' {", b"'missing-status' {", "missing-command")
        with self.assertRaises(AssertionError):
            self.assert_dispatch(operator, "status")

    def test_ps1_obsolete_public_commands_refuse(self) -> None:
        for command in ("record-or-resume-stages", "verify-successor-packet"):
            with self.subTest(command=command):
                returncode, traced = self.trace_arguments(self.operator, command, [])
                self.assertNotEqual(returncode, 0)
                self.assertEqual(traced, [])

    def test_ps1_profile_role_map_disagreement_is_detected(self) -> None:
        hostile = copy.deepcopy(self.profile)
        hostile["executionCustody"]["roles"]["status"] = copy.deepcopy(
            hostile["executionCustody"]["roles"]["verify-detached"]
        )
        with self.assertRaises(AssertionError):
            self.assert_dispatch(self.operator, "status", hostile)


class ExactGitSourceAdmissionWitnesses(unittest.TestCase):
    """Hostile witnesses for the exact commit/tree/blob source boundary."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(tempfile.mkdtemp(prefix="stc-mary-source-admission-"))
        atexit.register(shutil.rmtree, cls.root, ignore_errors=True)
        cls.profile = load_json(PROFILE)
        cls.repository, cls.commit = build_source_repository(cls.root, cls.profile)
        cls.direct = source_admission.admit_source(repository=cls.repository, source_commit=cls.commit)
        cls.authenticated = source_bootstrap.authenticate(repository=cls.repository, source_commit=cls.commit)

    def resign(self, receipt: Mapping[str, Any]) -> dict[str, Any]:
        body = copy.deepcopy(dict(receipt))
        body.pop(self.profile["sourceAdmission"]["idKey"], None)
        return law.sign(body, self.profile["sourceAdmission"]["idKey"], self.profile["sourceAdmission"]["idPrefix"])

    def validate_forged(self, receipt: Mapping[str, Any], name: str) -> None:
        path = self.root / f"{name}.json"
        law.write_canonical_json(path, self.resign(receipt))
        compiler.validate_source_admission(profile=self.profile, repository=self.repository, receipt_path=path)

    def test_exact_commit_tree_profile_and_members_are_admitted(self) -> None:
        receipt = self.authenticated
        self.assertTrue(receipt["bootstrapAuthenticated"])
        self.assertFalse(receipt["workingTreeBytesTrusted"])
        self.assertEqual(receipt["sourceCommit"], self.commit)
        self.assertEqual(receipt["memberCount"], 20)
        self.assertEqual(receipt["declaredSourceMemberDenominator"], 20)
        self.assertEqual(len({row["gitBlob"] for row in receipt["members"]}), 20)
        self.assertTrue(receipt["successorSourceSetId"].startswith("stcmarysuccessorsourceset1_"))

    def test_unknown_or_abbreviated_commit_refuses(self) -> None:
        for value in ("0" * 40, self.commit[:12]):
            with self.subTest(value=value), self.assertRaises(source_admission.SourceAdmissionError) as caught:
                source_admission.admit_source(repository=self.repository, source_commit=value)
            self.assertIn(caught.exception.code, {"SOURCE_COMMIT_UNKNOWN", "SOURCE_COMMIT_NOT_FULL"})

    def test_a_non_commit_object_refuses(self) -> None:
        blob = git(self.repository, "rev-parse", f"{self.commit}:{self.profile['sourceAdmission']['profilePath']}")
        with self.assertRaises(source_admission.SourceAdmissionError) as caught:
            source_admission.admit_source(repository=self.repository, source_commit=blob)
        self.assertEqual(caught.exception.code, "SOURCE_COMMIT_OBJECT_TYPE_INVALID")

    def test_tree_mismatch_refuses(self) -> None:
        forged = copy.deepcopy(self.authenticated)
        forged["sourceTree"] = "0" * 40
        with self.assertRaises(law.SuccessorFlightError) as caught:
            self.validate_forged(forged, "tree-mismatch")
        self.assertEqual(caught.exception.code, "SOURCE_TREE_MISMATCH")

    def test_profile_blob_mismatch_refuses(self) -> None:
        forged = copy.deepcopy(self.authenticated)
        forged["profileGitBlob"] = "0" * 40
        with self.assertRaises(law.SuccessorFlightError) as caught:
            self.validate_forged(forged, "profile-mismatch")
        self.assertEqual(caught.exception.code, "SOURCE_PROFILE_BLOB_MISMATCH")

    def test_a_member_absent_from_the_commit_refuses(self) -> None:
        altered = copy.deepcopy(self.profile)
        altered["successorSourceMembers"]["mating_surface/anchor_node/absent.py"] = "anchor_node/absent.py"
        altered["successorSourceMemberDenominator"] += 1
        profile_path = self.repository / self.profile["sourceAdmission"]["profilePath"]
        original = profile_path.read_bytes()
        try:
            law.write_canonical_json(profile_path, altered)
            git(self.repository, "add", "--all")
            git(self.repository, "commit", "--quiet", "-m", "declare absent source member")
            bad_commit = git(self.repository, "rev-parse", "HEAD")
            with self.assertRaises(source_admission.SourceAdmissionError) as caught:
                source_admission.admit_source(repository=self.repository, source_commit=bad_commit)
            self.assertEqual(caught.exception.code, "SOURCE_MEMBER_ABSENT")
        finally:
            profile_path.write_bytes(original)

    def test_repository_path_substitution_refuses(self) -> None:
        forged = copy.deepcopy(self.authenticated)
        forged["members"][0]["repositoryPath"] = forged["members"][1]["repositoryPath"]
        with self.assertRaises(law.SuccessorFlightError) as caught:
            self.validate_forged(forged, "repository-path")
        self.assertEqual(caught.exception.code, "SOURCE_MEMBER_SUBSTITUTED")

    def test_packet_path_substitution_refuses(self) -> None:
        forged = copy.deepcopy(self.authenticated)
        forged["members"][0]["packetPath"] = "anchor_node/substituted.py"
        with self.assertRaises(law.SuccessorFlightError) as caught:
            self.validate_forged(forged, "packet-path")
        self.assertEqual(caught.exception.code, "SOURCE_MEMBER_SUBSTITUTED")

    def test_correct_count_with_one_substituted_member_refuses(self) -> None:
        forged = copy.deepcopy(self.authenticated)
        forged["members"][0], forged["members"][1] = forged["members"][1], forged["members"][0]
        with self.assertRaises(law.SuccessorFlightError) as caught:
            self.validate_forged(forged, "member-substitution")
        self.assertEqual(caught.exception.code, "SOURCE_MEMBER_SUBSTITUTED")

    def test_git_blob_identity_mismatch_refuses(self) -> None:
        forged = copy.deepcopy(self.authenticated)
        forged["members"][0]["gitBlob"] = "0" * 40
        with self.assertRaises(law.SuccessorFlightError) as caught:
            self.validate_forged(forged, "blob-mismatch")
        self.assertEqual(caught.exception.code, "SOURCE_BLOB_IDENTITY_MISMATCH")

    def test_sha256_mismatch_refuses(self) -> None:
        forged = copy.deepcopy(self.authenticated)
        forged["members"][0]["sha256"] = "0" * 64
        with self.assertRaises(law.SuccessorFlightError) as caught:
            self.validate_forged(forged, "sha-mismatch")
        self.assertEqual(caught.exception.code, "SOURCE_SHA256_MISMATCH")

    def test_byte_count_mismatch_refuses(self) -> None:
        forged = copy.deepcopy(self.authenticated)
        forged["members"][0]["bytes"] += 1
        with self.assertRaises(law.SuccessorFlightError) as caught:
            self.validate_forged(forged, "byte-mismatch")
        self.assertEqual(caught.exception.code, "SOURCE_BYTE_COUNT_MISMATCH")

    def test_working_tree_mutation_is_ignored(self) -> None:
        row = self.authenticated["members"][0]
        path = self.repository / row["repositoryPath"]
        original = path.read_bytes()
        try:
            path.write_bytes(b"ambient mutation that is not a Git blob\n")
            repeated = source_admission.admit_source(repository=self.repository, source_commit=self.commit)
            self.assertEqual(repeated["successorSourceSetId"], self.direct["successorSourceSetId"])
            self.assertEqual(repeated["members"], self.direct["members"])
        finally:
            path.write_bytes(original)

    def test_crlf_checkout_and_lf_blob_have_one_source_identity(self) -> None:
        row = next(row for row in self.authenticated["members"] if row["repositoryPath"].endswith("source_admission.py"))
        path = self.repository / row["repositoryPath"]
        original = path.read_bytes()
        try:
            path.write_bytes(original.replace(b"\n", b"\r\n"))
            repeated = source_admission.admit_source(repository=self.repository, source_commit=self.commit)
            self.assertEqual(repeated["successorSourceSetId"], self.direct["successorSourceSetId"])
            self.assertEqual(repeated["sourceAdmissionId"], self.direct["sourceAdmissionId"])
        finally:
            path.write_bytes(original)

    def test_receipt_for_another_commit_or_tree_refuses(self) -> None:
        forged = copy.deepcopy(self.authenticated)
        forged["sourceCommit"] = "f" * 40
        with self.assertRaises(law.SuccessorFlightError) as caught:
            self.validate_forged(forged, "another-commit")
        self.assertEqual(caught.exception.code, "SOURCE_COMMIT_UNKNOWN")

    def test_direct_verifier_cannot_self_authenticate(self) -> None:
        self.assertFalse(self.direct["bootstrapAuthenticated"])
        self.assertIsNone(self.direct["bootstrapVerifierSha256"])
        self.assertNotEqual(self.direct["sourceAdmissionId"], self.authenticated["sourceAdmissionId"])

    def test_executed_verifier_bytes_must_equal_the_admitted_blob(self) -> None:
        blob, measured = source_bootstrap.verifier_blob(self.repository, self.commit)
        with mock.patch.object(source_bootstrap, "verifier_blob", return_value=(blob, measured + b"\n")):
            with self.assertRaises(source_bootstrap.BootstrapError) as caught:
                source_bootstrap.authenticate(repository=self.repository, source_commit=self.commit)
        self.assertEqual(caught.exception.code, "EXECUTED_VERIFIER_BYTES_DIFFER")

    def test_SOURCE_ADMISSION_SELF_AUTHENTICATED_hostile_witness(self) -> None:
        forged = copy.deepcopy(self.direct)
        forged["bootstrapAuthenticated"] = True
        blob, measured = source_bootstrap.verifier_blob(self.repository, self.commit)
        with self.assertRaises(source_bootstrap.BootstrapError) as caught:
            source_bootstrap.annotate_authenticated(
                forged,
                source_commit=self.commit,
                executed_sha256=law.sha256_bytes(measured),
                executed_bytes_count=len(measured),
                executed_blob_id=blob,
            )
        self.assertEqual(caught.exception.code, "SOURCE_ADMISSION_SELF_AUTHENTICATED")


class SourceBoundaryWitnesses(unittest.TestCase):
    """The source set stays inside its own product boundary."""

    def setUp(self) -> None:
        self.profile = load_json(PROFILE)

    def test_the_source_set_never_claims_the_frozen_packet_runtime(self) -> None:
        frozen = set(self.profile["frozenRuntimeMembers"])
        members = set(self.profile["successorSourceMembers"])
        self.assertEqual(frozen & members, set())

    def test_no_source_member_imports_or_drives_the_frozen_recorder(self) -> None:
        for relative in self.profile["successorSourceMembers"]:
            if not relative.endswith(".py") or relative.endswith(Path(__file__).name):
                continue
            text = (REPOSITORY_ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn("stc_mary_private_flight_packet", text, relative)
            self.assertNotIn("operatorConfirmed=", text, relative)

    def test_the_independent_verifiers_import_nothing_from_the_construction_law(self) -> None:
        """Independence is the whole point: a defect in the law may not authenticate it."""
        for name in (
            "verify_stc_mary_successor_packet.py",
            "verify_stc_mary_successor_evidence_materialization.py",
            "verify_stc_mary_successor_pre_seal_closure.py",
            "verify_stc_mary_successor_post_seal_closure.py",
            "verify_stc_mary_successor_source_admission.py",
        ):
            text = (ANCHOR / name).read_text(encoding="utf-8")
            self.assertNotIn("import stc_mary_successor_flight_law", text, name)
            self.assertNotIn("from stc_mary_successor_flight_law", text, name)

    def test_every_declared_source_member_exists(self) -> None:
        members = self.profile["successorSourceMembers"]
        self.assertEqual(len(members), self.profile["successorSourceMemberDenominator"])
        self.assertEqual(self.profile["successorSourceMemberDenominator"], 20)
        self.assertEqual(len(set(members.values())), len(members))
        for relative in members:
            self.assertTrue((REPOSITORY_ROOT / relative).is_file(), relative)

    def test_every_generated_packet_coordinate_is_portable_and_unique(self) -> None:
        """Enumerate the admitted denominator and prove the generated paths are safe.

        Two admitted role keys already differ only by stage -- ``verifier-receipt`` appears
        in RUN_PERSONAL_FLOOR_BASELINE and RUN_HALO3_ACCELERATED -- so uniqueness is proved
        over the complete stage-scoped destination rather than over the key. A future role
        key that collides only by case must refuse here, not on the Windows hosted leg
        half way through materializing a packet.
        """
        admitted = load_json(REPOSITORY_ROOT / self.profile["admissionProfile"]["relativePath"])
        destination_law = self.profile["evidenceMaterialization"]["destination"]
        path_law = destination_law["pathSafety"]
        destinations = []
        keys = []
        for sequence, stage in enumerate(admitted["stageSequence"], start=1):
            for role_law in admitted["stages"][stage]["evidenceRoles"]:
                key = role_law["evidenceRoleKey"]
                keys.append(key)
                destinations.append(
                    f"{sequence:02d}-{stage}/evidence/"
                    + destination_law["bodyFileTemplate"].format(evidenceRoleKey=key)
                )
        self.assertEqual(len(destinations), self.profile["denominator"]["evidenceRoleDenominator"])
        self.assertEqual(len(destinations), 43)
        # The keys are not unique; the destinations must be, exactly and under casefold.
        self.assertLess(len(set(keys)), len(keys))
        self.assertEqual(len(set(destinations)), 43)
        self.assertEqual(len({row.casefold() for row in destinations}), 43)
        for destination in destinations:
            materialization_bridge.assert_safe_destination(
                destination, law=path_law, code="EVIDENCE_DESTINATION_INVALID", label="destination"
            )
        materialization_bridge.assert_portable_destination_set(
            destinations, law=path_law, code="EVIDENCE_DESTINATION_INVALID"
        )

    def test_a_case_insensitive_coordinate_collision_refuses(self) -> None:
        path_law = self.profile["evidenceMaterialization"]["destination"]["pathSafety"]
        with self.assertRaises(materialization_bridge.MaterializationError) as caught:
            materialization_bridge.assert_portable_destination_set(
                ["01-A/evidence/verifier-receipt.json", "01-A/evidence/Verifier-Receipt.json"],
                law=path_law,
                code="EVIDENCE_DESTINATION_INVALID",
            )
        self.assertEqual(caught.exception.code, "EVIDENCE_DESTINATION_INVALID")

    def test_a_reserved_windows_component_refuses(self) -> None:
        path_law = self.profile["evidenceMaterialization"]["destination"]["pathSafety"]
        for unsafe in ("01-A/evidence/nul.json", "01-A/evidence/COM1.json", "01-A/evidence/aux.json"):
            with self.assertRaises(materialization_bridge.MaterializationError) as caught:
                materialization_bridge.assert_safe_destination(
                    unsafe, law=path_law, code="EVIDENCE_DESTINATION_INVALID", label="destination"
                )
            self.assertEqual(caught.exception.code, "EVIDENCE_DESTINATION_INVALID", unsafe)

    def test_the_materialized_row_is_declared_receipt_subordinate(self) -> None:
        """The classification is law the surfaces read, not prose beside the schema."""
        block = self.profile["evidenceMaterialization"]
        self.assertEqual(block["rowClass"], "receipt-subordinate")
        for name in (
            "verify_stc_mary_successor_evidence_materialization.py",
            "stc_mary_successor_packet_orchestrator.py",
            "verify_stc_mary_successor_pre_seal_closure.py",
        ):
            text = (ANCHOR / name).read_text(encoding="utf-8")
            self.assertIn('"rowClass"', text, name)
        # Campaign and packet identity are carried once, at receipt level, and never
        # repeated on a row.
        for key in ("campaignId", "packetId"):
            self.assertIn(key, block["keys"])
            self.assertNotIn(key, block["roleRowKeys"])

    def test_the_admitted_profile_is_pinned_by_canonical_digest(self) -> None:
        pin = self.profile["admissionProfile"]
        admitted = load_json(REPOSITORY_ROOT / pin["relativePath"])
        self.assertEqual(admitted["profileId"], pin["profileId"])
        self.assertEqual(
            law.sha256_bytes(law.canonical_json_bytes(admitted)), pin["canonicalSha256"]
        )

    def test_the_recorded_terminal_denominator_is_derived_not_restated(self) -> None:
        """15 / 1 / 0 is checked against the admitted stages, never merely declared."""
        profile = law.load_profile(PROFILE)
        admission = law.load_admission_profile(REPOSITORY_ROOT, profile)
        self.assertEqual(
            law.recorded_terminal_counts(admission),
            dict(profile["denominator"]["recordedTerminalCounts"]),
        )
        self.assertEqual(
            law.recorded_terminal_counts(admission), {"PASS": 15, "HUMAN_REQUIRED": 1, "REFUSED": 0}
        )

    def test_the_profile_restates_no_stage_sixteen_contract(self) -> None:
        """The Stage 16 surface is read from the admitted profile, never copied here."""
        serialized = json.dumps(self.profile)
        self.assertNotIn("publicDispositionBodyFree", serialized)
        self.assertNotIn("preSealEvidenceManifestComplete", serialized)
        self.assertNotIn("SEAL_PRIVATE_EVIDENCE", serialized)
        self.assertIn("stageSequence", self.profile["admissionProfile"]["derivedContracts"])

    def test_the_hosted_gate_pins_the_exact_witness_denominator(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        match = re.search(r'^\s*WITNESS_DENOMINATOR:\s*"(\d+)"\s*$', workflow, re.M)
        self.assertIsNotNone(match, "the workflow does not pin a witness denominator")
        pinned = int(match.group(1))
        discovered = unittest.defaultTestLoader.discover(
            str(Path(__file__).resolve().parent), pattern=Path(__file__).name
        )

        def count(suite: Any) -> int:
            if isinstance(suite, unittest.TestSuite):
                return sum(count(child) for child in suite)
            return 1

        self.assertEqual(pinned, count(discovered))

    def test_hosted_source_identity_aggregates_exact_four_leg_denominator(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        for leg in (
            "source-identity-ubuntu-latest-head",
            "source-identity-ubuntu-latest-merge",
            "source-identity-windows-latest-head",
            "source-identity-windows-latest-merge",
        ):
            self.assertIn(leg, workflow)
        self.assertIn("aggregate-source-identity:", workflow)
        self.assertIn("SUCCESSOR_SOURCE_SET_ID=", workflow)
        self.assertIn("four identity artifacts required", workflow)
        self.assertIn("one exact member-path set", workflow)
        self.assertIn("one exact member-digest set", workflow)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
