"""Permanent witnesses for the STC MARY packet evidence admission gate.

Every fixture in this file is synthetic. No real campaign identity, no private
coordinate, no evidence body, and no packet from any live campaign appears here. The
fixtures reproduce only the body-free object shapes, the sixteen-stage evidence-role
denominator, and the binding mechanism, so that the law can be exercised without
importing any private material into the public repository.

The positive witnesses cover all sixteen stage contracts, reused predecessor receipts,
fresh local observations, opaque instrument bodies, the two named-human statement
stages, and the sixteen-decision confirmation denominator. The hostile witnesses prove
that arbitrary files, untouched templates, forged identities, stale receipts, machine
actors, replayed and blanket confirmations, and conflict-winner selection are all
incapable of manufacturing an admissible packet denominator.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ANCHOR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ANCHOR.parent.parent
sys.path.insert(0, str(ANCHOR))

import stc_mary_packet_evidence_admission as frontend  # noqa: E402
import verify_stc_mary_packet_evidence_admission as law  # noqa: E402
import verify_stc_mary_packet_evidence_admission_bootstrap as bootstrap  # noqa: E402

PROFILE = ANCHOR / "stc-mary-packet-evidence-admission-profile-01.json"

SYNTHETIC_CAMPAIGN_LABEL = "SYNTHETIC-ADMISSION-WITNESS-01"
OTHER_CAMPAIGN_LABEL = "SYNTHETIC-ADMISSION-WITNESS-02"

RECEIPT = "accepted_predecessor_receipt"
CURRENT = "current_local_observation"
HUMAN = "named_human_statement"

TRANSACTION_START = 1_800_000_000_000_000_000
TRANSACTION_END = TRANSACTION_START + 3_600_000_000_000

EVIDENCE_CLASS_BY_PROVENANCE = {
    RECEIPT: "private_instrument_receipt",
    CURRENT: "private_local_attestation",
    HUMAN: "private_operator_statement",
}

# The untouched envelope the live campaign already ships in its own products. It is a
# structurally valid, non-empty JSON file, which is exactly why the frozen recorder
# cannot tell it apart from real evidence.
ENVELOPE_TEMPLATE = {
    "schema": "stc-mary-private-evidence-envelope-template/1",
    "note": "REPLACE_WITH_LOCAL_EVIDENCE",
}

FROZEN_PACKET_PROFILE = ANCHOR / "stc-mary-private-flight-packet-profile-01.json"

# DIAGNOSTIC traversal driver. It drives the FROZEN, UNPATCHED packet recorder over a
# throwaway synthetic packet to establish exactly one narrow fact: that the frozen
# sequence is MECHANICALLY traversable from a configured zero-stage packet to detached
# verification.
#
# It establishes nothing about truthfulness, and it is not an admission witness. To
# record stage 16 at all it must satisfy the frozen observation contract, which requires
# publicDispositionBodyFree: true -- an assertion about a public disposition the sealer
# has not yet created. That assertion is untrue at the moment it is written, which is
# precisely why the frozen packet needs a successor observation contract and why this
# driver reports the keys it was forced to write.
ORDERING_WITNESS_DRIVER = r"""
import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const anchor = process.argv[2].replaceAll('\\', '/');
const root = process.argv[3];
const preSealStageSixteenEvidence = JSON.parse(process.argv[4]);
const packetModule = await import(`file://${anchor}/stc_mary_private_flight_packet.mjs`);
const { STC_MARY_STAGES } = await import(`file://${anchor}/stc_mary_physical_flight.mjs`);

const packet = join(root, 'stc-mary-private-flight-orderingwitness');
const sealed = join(root, 'stc-mary-private-flight-sealed-orderingwitness');
const sha256 = (t) => createHash('sha256').update(t, 'utf8').digest('hex');
const cid = (p, t) => `${p}_${sha256(t)}`;
const OUTPUT = cid('syntheticoutput1', 'accepted-mission-output');

const readJson = async (p) => JSON.parse(await readFile(p, 'utf8'));
const writeJson = async (p, v) => writeFile(p, `${JSON.stringify(v, null, 2)}\n`, 'utf8');

function observation(stage, o) {
  const v = structuredClone(o);
  switch (stage) {
    case 'VERIFY_INPUTS':
      v.profileValidated = true; v.sourceObjectsVerified = true;
      v.inputDigestRoot = cid('syntheticinputroot1', 'inputs'); break;
    case 'MOUNT_PERSONAL_FLOOR': v.mounted = true; v.missionClosed = true; break;
    case 'BIND_GRACE': v.bound = true; v.authoritySource = 'named_human_bind'; break;
    case 'RUN_PERSONAL_FLOOR_BASELINE':
      v.outputDigest = OUTPUT; v.throughputUnits = 100; v.verifierState = 'pass'; break;
    case 'ATTACH_HALO3': v.attached = true; v.optional = true; break;
    case 'RUN_HALO3_ACCELERATED':
      v.outputDigest = OUTPUT; v.throughputUnits = 400; v.verifierState = 'pass';
      v.fasterThanBaseline = true; break;
    case 'REMOVE_HALO3': v.attached = false; v.removalReceiptPresent = true; break;
    case 'VERIFY_PERSONAL_FLOOR_CONTINUITY':
      v.personalFloorAvailable = true; v.outputDigestMatches = true;
      v.halo3Required = false; v.throughputUnits = 100; break;
    case 'REMOVE_LATTICE': v.present = false; v.removalReceiptPresent = true; break;
    case 'VERIFY_LOCAL_CONTINUITY':
      v.localStateAvailable = true; v.latticeRequired = false;
      v.canonicalStateRecovered = true; break;
    case 'PARTITION_TWO_CELLS':
      v.cellCount = 2; v.eachCellLocallyValid = true; v.authorityWidened = false; break;
    case 'RESTORE_LINK_HOLD_CONFLICT':
      v.linkRestored = true; v.conflictDetected = true; v.automaticMerge = false;
      v.resolution = 'human_required';
      v.leftStateDigest = sha256('left-cell'); v.rightStateDigest = sha256('right-cell'); break;
    case 'REPLACE_HEAD':
      v.replacementAccepted = true; v.canonicalStateCopiedByDigest = true;
      v.authorityTransferred = false; break;
    case 'REBUILD_PROJECTIONS':
      v.projectionKinds = ['graph', 'query', 'cache', 'review'];
      v.rebuiltFromCanonicalReceipts = true;
      v.projectionDigestRoot = cid('syntheticprojectionroot1', 'projections'); break;
    case 'COLD_SUCCESSOR_VERIFY':
      v.recoveredCartridge = true; v.recoveredAuthorityBoundary = true;
      v.recoveredObligations = true; v.verificationState = 'pass'; break;
    case 'SEAL_PRIVATE_EVIDENCE':
      v.sealedEvidenceClass = 'private_physical_attested';
      v.evidenceDescriptorCount = 16;
      v.publicDispositionBodyFree = true;
      v.privateEvidenceBodiesCommittedToGit = false; break;
    default: throw new Error(`unhandled stage ${stage}`);
  }
  return v;
}

await mkdir(root, { recursive: true });
const init = await packetModule.initializePrivateFlightPacket(packet, 'SYNTHETIC-ORDERING-WITNESS-01');

const config = await readJson(join(packet, 'flight-config.json'));
config.sourceObjectDigests = [sha256('synthetic-source-object')];
config.canonicalMissionStateDigest = sha256('synthetic-canonical-mission-state');
config.identityClasses = {
  personalFloor: 'synthetic-personal-floor', halo3: 'synthetic-halo3',
  initialHead: 'synthetic-initial-head', successorHead: 'synthetic-successor-head',
  graceBind: 'synthetic-named-human-bind', lattice: 'synthetic-lattice',
  leftCell: 'synthetic-left-cell', rightCell: 'synthetic-right-cell',
};
const configPath = join(root, 'config.json');
await writeJson(configPath, config);
const configured = await packetModule.configurePrivateFlightPacket(packet, configPath);

let postSealObjectOfferedToStageSixteen = false;
let frozenStageSixteenObservationKeys = [];
const stageOrder = [];

for (const [index, stage] of STC_MARY_STAGES.entries()) {
  const sequence = index + 1;
  const dir = join(packet, `${String(sequence).padStart(2, '0')}-${stage}`);
  const draftPath = join(dir, 'stage-attestation.json');
  const draft = await readJson(draftPath);
  draft.observation = observation(stage, draft.observation);
  draft.operatorConfirmed = true;
  draft.evidenceClass = 'private_local_attestation';
  draft.mediaType = 'application/json';
  await writeJson(draftPath, draft);
  const names = stage === 'SEAL_PRIVATE_EVIDENCE'
    ? preSealStageSixteenEvidence
    : [`${stage.toLowerCase()}-receipt`];
  for (const name of names) {
    if (name.includes('sealed run') || name.includes('public disposition')) {
      postSealObjectOfferedToStageSixteen = true;
    }
    await writeJson(join(dir, 'evidence', `${name.replaceAll(' ', '-')}.json`), { stage, sequence, role: name });
  }
  if (stage === 'SEAL_PRIVATE_EVIDENCE') {
    frozenStageSixteenObservationKeys = Object.keys(draft.observation).sort();
  }
  const { state } = await packetModule.recordPrivateFlightStage(packet, stage);
  stageOrder.push({ sequence, stage, completed: state.completedStageCount });
}

const preSeal = await packetModule.privateFlightPacketStatus(packet);
const result = await packetModule.sealPrivateFlightPacket(packet, sealed);
const verification = await packetModule.verifySealedPrivateFlightPacket(sealed);
const disposition = await readJson(join(sealed, 'public-disposition.json'));

process.stdout.write(JSON.stringify({
  initialConfigurationState: init.state.configurationState,
  initialCompletedStageCount: init.state.completedStageCount,
  configuredState: configured.configurationState,
  configuredCompletedStageCount: configured.completedStageCount,
  stageOrder,
  preSealCompletedStageCount: preSeal.completedStageCount,
  preSealSealed: preSeal.sealed,
  frozenStageSixteenObservationKeys: frozenStageSixteenObservationKeys,
  postSealObjectOfferedToStageSixteen,
  runId: result.run.runId,
  dispositionId: result.disposition.dispositionId,
  verificationStatus: verification.status,
  stageCount: verification.stageCount,
  privateEvidenceBodies: verification.privatePhysicalEvidenceBodyCount,
  publicEvidenceBodies: verification.publicEvidenceBodyCount,
  bodyFreePublicDisposition: verification.bodyFreePublicDisposition,
  successfulStageCount: disposition.successfulStageCount,
  humanRequiredStageCount: disposition.humanRequiredStageCount,
  privatePhysicalFlightCompleted: disposition.privatePhysicalFlightCompleted,
  physicalEstateQualified: disposition.physicalEstateQualified,
  authority: verification.authority,
}));
"""


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


def synthetic_observation(stage: str, contract: dict) -> dict:
    """Build one observation that satisfies the stage contract exactly."""
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
        else:  # pragma: no cover - the contract denominator is closed
            raise AssertionError(f"unhandled observation field {stage}.{key}")
    return observation


class Fixture:
    """One complete, internally consistent synthetic admission workspace."""

    def __init__(self, root: Path, profile: dict, campaign_label: str = SYNTHETIC_CAMPAIGN_LABEL):
        self.root = root
        self.profile = profile
        self.campaign_label = campaign_label
        self.workstation = root / "workstation"
        self.packet = root / "campaign" / "stc-mary-private-flight-witness"
        self.candidates = root / "admission"
        self.canonical_mission_state_digest = sha256_text(f"canonical-mission-state:{campaign_label}")
        self.campaign_id = cid("stcmaryflightconductorcampaign1", {"campaignLabel": campaign_label})
        self.predecessor_coordinate = cid(
            "stcmaryflightconductoracceptedpredecessor1", {"campaignLabel": campaign_label}
        )
        self._build_workstation()
        self._build_packet()
        self._build_candidates()

    # -- frozen surfaces ---------------------------------------------------
    def _build_workstation(self) -> None:
        ws_law = self.profile["workstation"]
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
            self.workstation / ws_law["markerFile"], sign(body, ws_law["markerIdKey"], ws_law["markerIdPrefix"])
        )

    def _build_packet(self) -> None:
        packet_law = self.profile["packet"]
        self.packet_id = cid(
            "stcmaryprivateflightpacket1",
            {
                "campaignLabel": self.campaign_label,
                "packetProfileId": self.profile["predecessorPacketProfileId"],
                "physicalProfileId": self.profile["predecessorPhysicalProfileId"],
            },
        )
        marker = {
            "schema": packet_law["markerSchema"],
            "packetProfileId": self.profile["predecessorPacketProfileId"],
            "physicalProfileId": self.profile["predecessorPhysicalProfileId"],
            "campaignLabel": self.campaign_label,
            "packetId": self.packet_id,
            "authority": "none",
            "claimBoundary": "Synthetic packet marker for conformance only. It grants no authority.",
        }
        write_json(
            self.packet / packet_law["markerFile"],
            sign(marker, packet_law["markerIdKey"], packet_law["markerIdPrefix"]),
        )

        stages = [
            {
                "sequence": index + 1,
                "stage": stage,
                "status": "unrecorded",
                "draftPath": f"{index + 1:02d}-{stage}/stage-attestation.json",
                "evidenceDirectory": f"{index + 1:02d}-{stage}/evidence",
                "evidenceCount": 0,
                "recordDigest": None,
            }
            for index, stage in enumerate(self.profile["stageSequence"])
        ]
        state = {
            "schema": packet_law["stateSchema"],
            "packetId": self.packet_id,
            "campaignLabel": self.campaign_label,
            "packetProfileId": self.profile["predecessorPacketProfileId"],
            "physicalProfileId": self.profile["predecessorPhysicalProfileId"],
            "configurationState": "configured",
            "stageDenominator": list(self.profile["stageSequence"]),
            "stages": stages,
            "completedStageCount": 0,
            "nextStage": self.profile["stageSequence"][0],
            "sealed": False,
            "sealedDispositionId": None,
            "authority": "none",
            "claimBoundary": "Synthetic packet state for conformance only. It grants no authority.",
        }
        write_json(
            self.packet / packet_law["stateFile"], sign(state, packet_law["stateIdKey"], packet_law["stateIdPrefix"])
        )

        config = {
            "schema": packet_law["configSchema"],
            "campaignLabel": self.campaign_label,
            "sourceObjectDigests": [sha256_text("synthetic-source-object")],
            "identityClasses": {
                "personalFloor": "synthetic-personal-floor",
                "halo3": "synthetic-halo3",
                "initialHead": "synthetic-initial-head",
                "successorHead": "synthetic-successor-head",
                "graceBind": "synthetic-named-human-bind",
                "lattice": "synthetic-lattice",
                "leftCell": "synthetic-left-cell",
                "rightCell": "synthetic-right-cell",
            },
            "canonicalMissionStateDigest": self.canonical_mission_state_digest,
            "authority": "none",
            "claimBoundary": "Synthetic packet configuration for conformance only. It grants no authority.",
        }
        write_json(self.packet / packet_law["configFile"], config)

    # -- admission workspace ----------------------------------------------
    def stage_directory(self, sequence: int, stage: str) -> str:
        return f"bodies/{sequence:02d}-{stage}"

    def evidence_body(self, stage: str, sequence: int, role_law: dict, stage_law: dict) -> dict:
        provenance = role_law["provenanceClass"]
        schema_law = self.profile["bodySchemas"][provenance]
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
            conflict = stage == self.profile["bodySchemas"][HUMAN]["conflictStage"]
            observation = self.observations[stage]
            body.update(
                {
                    "actorClass": schema_law["requiredActorClass"],
                    "statementScope": f"Named-human statement for the {stage} stage of one synthetic packet.",
                    "acceptedEvidenceIds": [],
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

    def _build_candidates(self) -> None:
        self.transaction = sign(
            {
                "schema": self.profile["observationTransaction"]["schema"],
                "startedAtUnixNs": TRANSACTION_START,
                "endedAtUnixNs": TRANSACTION_END,
            },
            self.profile["observationTransaction"]["idKey"],
            self.profile["observationTransaction"]["idPrefix"],
        )
        self.transaction_id = self.transaction[self.profile["observationTransaction"]["idKey"]]

        self.observations = {
            stage: synthetic_observation(stage, self.profile["stages"][stage]["observation"])
            for stage in self.profile["stageSequence"]
        }

        receipt_ids: list[str] = []
        stages: list[dict[str, Any]] = []
        for index, stage in enumerate(self.profile["stageSequence"]):
            sequence = index + 1
            stage_law = self.profile["stages"][stage]
            descriptors = []
            for role_law in stage_law["evidenceRoles"]:
                if role_law["provenanceClass"] == HUMAN:
                    continue  # unsupplied at READY, by design
                if role_law["provenanceClass"] == RECEIPT:
                    receipt_ids.append(self.receipt_id(stage, role_law))
                descriptors.append(self.write_evidence(stage, sequence, role_law, stage_law))
            stages.append(
                {
                    "sequence": sequence,
                    "stage": stage,
                    "availabilityClass": stage_law["availabilityClass"],
                    "observation": self.observations[stage],
                    "evidence": descriptors,
                }
            )

        request = {
            "schema": self.profile["request"]["schema"],
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
            "stages": stages,
            "stageConfirmations": [],
            "batchConfirmation": None,
            "authority": "none",
            "claimBoundary": "Synthetic admission request for conformance only. It grants no authority.",
        }
        self.write_request(request)

    def write_evidence(self, stage: str, sequence: int, role_law: dict, stage_law: dict) -> dict:
        body = self.evidence_body(stage, sequence, role_law, stage_law)
        schema_law = self.profile["bodySchemas"][role_law["provenanceClass"]]
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

    # -- request helpers ---------------------------------------------------
    def request_path(self) -> Path:
        return self.candidates / self.profile["request"]["fileName"]

    def load_request(self) -> dict:
        return load_json(self.request_path())

    def write_request(self, request: dict) -> dict:
        law_block = self.profile["request"]
        request.pop(law_block["idKey"], None)
        signed = sign(request, law_block["idKey"], law_block["idPrefix"])
        write_json(self.request_path(), signed)
        return signed

    def mutate_request(self, mutate) -> dict:
        request = self.load_request()
        mutate(request)
        return self.write_request(request)

    def stage_row(self, request: dict, stage: str) -> dict:
        return next(row for row in request["stages"] if row["stage"] == stage)

    def descriptor(self, request: dict, stage: str, role: str) -> dict:
        return next(row for row in self.stage_row(request, stage)["evidence"] if row["evidenceRole"] == role)

    def role_law(self, stage: str, role: str) -> dict:
        return next(
            row for row in self.profile["stages"][stage]["evidenceRoles"] if row["evidenceRole"] == role
        )

    def resign_body(self, stage: str, role: str, mutate) -> dict:
        """Rewrite one evidence body, re-sign it, and re-point its descriptor."""
        request = self.load_request()
        descriptor = self.descriptor(request, stage, role)
        path = self.candidates / descriptor["bodyPath"]
        body = load_json(path)
        mutate(body)
        schema_law = self.profile["bodySchemas"][descriptor["provenanceClass"]]
        body.pop(schema_law["idKey"], None)
        body = sign(body, schema_law["idKey"], schema_law["idPrefix"])
        write_json(path, body)
        data = path.read_bytes()
        descriptor["bodySha256"] = law.sha256_bytes(data)
        descriptor["bodyBytes"] = len(data)
        descriptor["bodyContentId"] = body[schema_law["idKey"]]
        return self.write_request(request)

    # -- completing the denominator ---------------------------------------
    def add_human_statements(self) -> dict:
        request = self.load_request()
        for index, stage in enumerate(self.profile["stageSequence"]):
            sequence = index + 1
            stage_law = self.profile["stages"][stage]
            for role_law in stage_law["evidenceRoles"]:
                if role_law["provenanceClass"] != HUMAN:
                    continue
                descriptor = self.write_evidence(stage, sequence, role_law, stage_law)
                # The statement accepts exactly the non-human identities this gate
                # admitted for its own stage.
                row = self.stage_row(request, stage)
                accepted = sorted(entry["bodyContentId"] for entry in row["evidence"])
                path = self.candidates / descriptor["bodyPath"]
                body = load_json(path)
                schema_law = self.profile["bodySchemas"][HUMAN]
                body["acceptedEvidenceIds"] = accepted
                body.pop(schema_law["idKey"], None)
                body = sign(body, schema_law["idKey"], schema_law["idPrefix"])
                write_json(path, body)
                data = path.read_bytes()
                descriptor["bodySha256"] = law.sha256_bytes(data)
                descriptor["bodyBytes"] = len(data)
                descriptor["bodyContentId"] = body[schema_law["idKey"]]
                row["evidence"].append(descriptor)
        return self.write_request(request)

    def confirmations_from(self, receipt: dict, decision: str = "RECORD_STAGE") -> list[dict]:
        law_block = self.profile["confirmation"]
        rows = []
        for requirement in receipt["stageConfirmationRequirements"]:
            body = {
                "schema": law_block["schema"],
                "campaignId": self.campaign_id,
                "packetId": self.packet_id,
                "sequence": requirement["sequence"],
                "stage": requirement["stage"],
                "requiredTerminal": requirement["requiredTerminal"],
                "evidenceAdmissionRoot": requirement["evidenceAdmissionRoot"],
                "observationDigest": requirement["observationDigest"],
                "decisionCode": decision,
                "controlQuestionResponse": f"Yes, for {requirement['stage']}, on the admitted evidence root.",
                "actorClass": law_block["requiredActorClass"],
                "issuedAtUnixNs": TRANSACTION_END + 2_000_000_000,
                "authenticationBinding": "synthetic-local-named-human-authentication",
                "authority": "none",
                "claimBoundary": "Synthetic stage confirmation for conformance only. It grants no authority.",
            }
            rows.append(sign(body, law_block["idKey"], law_block["idPrefix"]))
        return rows

    def batch_from(self, confirmations: list[dict]) -> dict:
        law_block = self.profile["batchConfirmation"]
        body = {
            "schema": law_block["schema"],
            "campaignId": self.campaign_id,
            "packetId": self.packet_id,
            "stageCount": len(confirmations),
            "stages": [
                {
                    "sequence": row["sequence"],
                    "stage": row["stage"],
                    "requiredTerminal": row["requiredTerminal"],
                    "evidenceAdmissionRoot": row["evidenceAdmissionRoot"],
                    "observationDigest": row["observationDigest"],
                    "decisionCode": row["decisionCode"],
                    "controlQuestionResponse": row["controlQuestionResponse"],
                }
                for row in confirmations
            ],
            "actorClass": self.profile["confirmation"]["requiredActorClass"],
            "issuedAtUnixNs": TRANSACTION_END + 3_000_000_000,
            "authenticationBinding": "synthetic-local-named-human-authentication",
            "authority": "none",
            "claimBoundary": "Synthetic batch confirmation for conformance only. It grants no authority.",
        }
        return sign(body, law_block["idKey"], law_block["idPrefix"])

    def complete(self, decision: str = "RECORD_STAGE", with_batch: bool = False) -> dict:
        """Drive the fixture to the full forty-three-role, sixteen-decision state."""
        self.add_human_statements()
        pending = self.run()
        confirmations = self.confirmations_from(pending, decision=decision)
        batch = self.batch_from(confirmations) if with_batch else None

        def apply(request: dict) -> None:
            request["stageConfirmations"] = confirmations
            request["batchConfirmation"] = batch

        self.mutate_request(apply)
        return pending

    # -- helpers -----------------------------------------------------------
    def run(self, **overrides):
        return law.verify_packet_evidence_admission(
            workstation=overrides.get("workstation", self.workstation),
            packet=overrides.get("packet", self.packet),
            candidates=overrides.get("candidates", self.candidates),
            profile_path=PROFILE,
            admission_source_root=overrides.get("admission_source_root", REPOSITORY_ROOT),
            measured_verifier_bytes=overrides.get("measured_verifier_bytes"),
        )

    def packet_bytes_fence(self) -> dict[str, str]:
        return {
            entry.name: law.sha256_bytes(entry.read_bytes())
            for entry in sorted(self.packet.iterdir())
            if entry.is_file()
        }


class AdmissionWitnessCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="stc-mary-admission-witness-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.profile = load_json(PROFILE)
        self.fixture = Fixture(self.tmp / "case", self.profile)

    def assert_refuses(self, code: str, **overrides) -> None:
        with self.assertRaises(law.AdmissionError) as caught:
            self.fixture.run(**overrides)
        self.assertEqual(caught.exception.code, code)


# --------------------------------------------------------------------------------
# positive terminals
# --------------------------------------------------------------------------------


class PositiveTerminals(AdmissionWitnessCase):
    def test_forty_one_non_human_roles_close_ready_for_named_human_decision(self) -> None:
        receipt = self.fixture.run()
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["terminal"], "READY_FOR_NAMED_HUMAN_DECISION")
        self.assertEqual(receipt["stageDenominator"], 16)
        self.assertEqual(receipt["evidenceRoleDenominator"], 43)
        self.assertEqual(receipt["nonHumanEvidenceRoleDenominator"], 40)
        self.assertEqual(receipt["humanStatementRoleDenominator"], 3)
        self.assertEqual(receipt["admittedEvidenceRoleCount"], 40)
        self.assertEqual(receipt["admittedNonHumanEvidenceRoleCount"], 40)
        self.assertEqual(receipt["admittedHumanStatementCount"], 0)
        self.assertEqual(receipt["reusedPredecessorReceiptCount"], 23)
        self.assertEqual(receipt["currentObservationCount"], 17)
        self.assertEqual(receipt["missingEvidenceRoleCount"], 3)
        self.assertEqual(receipt["suppliedStageConfirmationCount"], 0)
        self.assertEqual(receipt["packetStagesRecorded"], 0)
        self.assertEqual(receipt["operatorConfirmedFlagsSet"], 0)
        self.assertFalse(receipt["packetRecorderInvoked"])
        self.assertFalse(receipt["packetMutated"])
        self.assertEqual(receipt["humanStatementsGeneratedByThisGate"], 0)
        self.assertEqual(receipt["stageConfirmationsIssuedByThisGate"], 0)
        self.assertEqual(receipt["authority"], "none")
        self.assertFalse(receipt["bootstrapAuthenticated"])

    def test_ready_prepares_two_statement_forms_and_sixteen_decision_records(self) -> None:
        receipt = self.fixture.run()
        self.assertEqual(len(receipt["humanStatementRequirements"]), 3)
        self.assertEqual(
            sorted(row["stage"] for row in receipt["humanStatementRequirements"]),
            ["BIND_GRACE", "RESTORE_LINK_HOLD_CONFLICT", "SEAL_PRIVATE_EVIDENCE"],
        )
        self.assertTrue(all(row["supplied"] is False for row in receipt["humanStatementRequirements"]))
        self.assertEqual(len(receipt["stageConfirmationRequirements"]), 16)
        self.assertEqual(
            [row["stage"] for row in receipt["stageConfirmationRequirements"]], self.profile["stageSequence"]
        )
        # The two stages still owing a statement are explicitly marked non-final, so a
        # confirmation is never invited against a root that has not settled.
        by_stage = {row["stage"]: row for row in receipt["stageConfirmationRequirements"]}
        self.assertFalse(by_stage["BIND_GRACE"]["evidenceAdmissionRootFinal"])
        self.assertFalse(by_stage["RESTORE_LINK_HOLD_CONFLICT"]["evidenceAdmissionRootFinal"])
        self.assertFalse(by_stage["SEAL_PRIVATE_EVIDENCE"]["evidenceAdmissionRootFinal"])
        self.assertTrue(by_stage["VERIFY_INPUTS"]["evidenceAdmissionRootFinal"])

    def test_ready_invites_no_stage_confirmation_at_all(self) -> None:
        """No confirmation is invitable until all sixteen final roots exist.

        The two statement-owing stages are the reason, but the gate is global: a
        confirmation issued against any stage before the denominator settles would go
        stale the moment a statement-bearing root moved.
        """
        receipt = self.fixture.run()
        self.assertFalse(receipt["confirmationDenominatorInvitable"])
        by_stage = {row["stage"]: row for row in receipt["stageConfirmationRequirements"]}
        for stage in ("BIND_GRACE", "RESTORE_LINK_HOLD_CONFLICT", "SEAL_PRIVATE_EVIDENCE"):
            self.assertFalse(by_stage[stage]["evidenceAdmissionRootFinal"], stage)
            self.assertFalse(by_stage[stage]["confirmationInvitable"], stage)
        self.assertTrue(
            all(row["confirmationInvitable"] is False for row in receipt["stageConfirmationRequirements"])
        )

    def test_landed_statements_invite_all_sixteen_confirmations(self) -> None:
        self.fixture.add_human_statements()
        receipt = self.fixture.run()
        self.assertTrue(receipt["confirmationDenominatorInvitable"])
        self.assertEqual(len(receipt["stageConfirmationRequirements"]), 16)
        self.assertTrue(all(row["confirmationInvitable"] for row in receipt["stageConfirmationRequirements"]))
        self.assertTrue(all(row["evidenceAdmissionRootFinal"] for row in receipt["stageConfirmationRequirements"]))

    def test_all_sixteen_stage_contracts_are_exercised(self) -> None:
        receipt = self.fixture.run()
        rows = {row["stage"]: row for row in receipt["stages"]}
        self.assertEqual(set(rows), set(self.profile["stageSequence"]))
        for stage, row in rows.items():
            stage_law = self.profile["stages"][stage]
            self.assertEqual(row["evidenceRoleDenominator"], stage_law["evidenceRoleDenominator"])
            self.assertEqual(row["availabilityClass"], stage_law["availabilityClass"])
            self.assertEqual(row["requiredTerminal"], stage_law["requiredTerminal"])
            self.assertTrue(row["observationDigest"].startswith("stcmarypacketevidenceobservationdigest1_"))
            self.assertTrue(row["evidenceAdmissionRoot"].startswith("stcmarypacketevidencestageroot1_"))
        self.assertEqual(rows["RESTORE_LINK_HOLD_CONFLICT"]["requiredTerminal"], "HUMAN_REQUIRED")

    def test_availability_matrix_matches_the_admitted_denominator(self) -> None:
        receipt = self.fixture.run()
        counts: dict[str, int] = {"MISSING_HISTORICAL_PHYSICAL_EVIDENCE": 0, "REFUSED_AS_UNRECOVERABLE": 0}
        for row in receipt["stages"]:
            counts[row["availabilityClass"]] = counts.get(row["availabilityClass"], 0) + 1
        self.assertEqual(counts, self.profile["denominator"]["availabilityClassCounts"])

    def test_complete_denominator_closes_admissible_for_packet_recording(self) -> None:
        self.fixture.complete()
        receipt = self.fixture.run()
        self.assertEqual(receipt["terminal"], "ADMISSIBLE_FOR_PACKET_RECORDING")
        self.assertEqual(receipt["admittedEvidenceRoleCount"], 43)
        self.assertEqual(receipt["admittedHumanStatementCount"], 3)
        self.assertEqual(receipt["missingEvidenceRoleCount"], 0)
        self.assertEqual(receipt["suppliedStageConfirmationCount"], 16)
        self.assertEqual(len(receipt["stageDecisions"]), 16)
        self.assertTrue(all(row["decisionCode"] == "RECORD_STAGE" for row in receipt["stageDecisions"]))
        # Even this terminal records nothing.
        self.assertEqual(receipt["packetStagesRecorded"], 0)
        self.assertEqual(receipt["operatorConfirmedFlagsSet"], 0)
        self.assertFalse(receipt["packetRecorderInvoked"])
        self.assertTrue(all(row["evidenceAdmissionRootFinal"] for row in receipt["stageConfirmationRequirements"]))

    def test_bounded_batch_confirmation_is_admitted_beside_the_exact_decisions(self) -> None:
        self.fixture.complete(with_batch=True)
        receipt = self.fixture.run()
        self.assertEqual(receipt["terminal"], "ADMISSIBLE_FOR_PACKET_RECORDING")
        self.assertTrue(receipt["batchConfirmationId"].startswith("stcmarypacketevidencebatchconfirmation1_"))

    def test_statements_supplied_without_decisions_hold(self) -> None:
        self.fixture.add_human_statements()
        receipt = self.fixture.run()
        self.assertEqual(receipt["terminal"], "HOLD")
        self.assertEqual(receipt["admittedEvidenceRoleCount"], 43)
        self.assertEqual(receipt["suppliedStageConfirmationCount"], 0)
        self.assertIn("stage decisions outstanding", receipt["holdReason"])

    def test_named_human_hold_decision_holds(self) -> None:
        self.fixture.complete(decision="HOLD_STAGE")
        receipt = self.fixture.run()
        self.assertEqual(receipt["terminal"], "HOLD")
        self.assertEqual(receipt["holdReason"], "named human held one or more stage decisions")
        self.assertEqual(receipt["packetStagesRecorded"], 0)

    def test_missing_non_human_role_holds_and_names_the_role(self) -> None:
        def drop(request: dict) -> None:
            row = self.fixture.stage_row(request, "VERIFY_INPUTS")
            row["evidence"] = [
                entry for entry in row["evidence"] if entry["evidenceRole"] != "source digest receipt"
            ]

        self.fixture.mutate_request(drop)
        receipt = self.fixture.run()
        self.assertEqual(receipt["terminal"], "HOLD")
        self.assertEqual(receipt["holdReason"], "non-human evidence roles outstanding")
        self.assertEqual(receipt["admittedEvidenceRoleCount"], 39)
        missing = [row for row in receipt["missingEvidenceRoles"] if row["stage"] == "VERIFY_INPUTS"]
        self.assertEqual([row["evidenceRole"] for row in missing], ["source digest receipt"])

    def test_receipt_identity_reconstructs(self) -> None:
        receipt = self.fixture.run()
        body = {key: value for key, value in receipt.items() if key != law.RECEIPT_ID_KEY}
        self.assertEqual(receipt[law.RECEIPT_ID_KEY], law.content_id(law.RECEIPT_ID_PREFIX, body))

    def test_receipt_carries_no_private_coordinate_or_evidence_body(self) -> None:
        self.fixture.complete()
        receipt = self.fixture.run()
        serialized = json.dumps(receipt)
        self.assertNotIn(str(self.fixture.packet), serialized)
        self.assertNotIn(str(self.fixture.candidates), serialized)
        self.assertNotIn(str(self.fixture.workstation), serialized)
        self.assertNotIn("bodies/", serialized)
        self.assertNotIn("synthetic-personal-floor", serialized)
        law.assert_no_private_material(receipt, code="X", label="receipt")

    def test_admission_leaves_the_packet_byte_identical(self) -> None:
        before = self.fixture.packet_bytes_fence()
        self.fixture.complete()
        receipt = self.fixture.run()
        self.assertEqual(receipt["terminal"], "ADMISSIBLE_FOR_PACKET_RECORDING")
        self.assertEqual(self.fixture.packet_bytes_fence(), before)
        state = load_json(self.fixture.packet / self.profile["packet"]["stateFile"])
        self.assertEqual(state["completedStageCount"], 0)
        self.assertTrue(all(row["status"] == "unrecorded" for row in state["stages"]))

    def test_gate_source_never_reaches_the_frozen_packet_recorder(self) -> None:
        """No admission source member may name the recorder or emit its operator Boolean.

        ``operatorConfirmedFlagsSet`` is this product's own always-zero counter and is
        deliberately a different token from the recorder's ``operatorConfirmed``.
        """
        for relative in self.profile["admissionSourceMembers"]:
            if not relative.endswith(".py") or relative.endswith(Path(__file__).name):
                continue
            text = (REPOSITORY_ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn("stc_mary_private_flight_packet", text, relative)
            self.assertNotIn('"operatorConfirmed"', text, relative)
            self.assertNotIn("operatorConfirmed=", text, relative)


# --------------------------------------------------------------------------------
# stage 16 ordering
# --------------------------------------------------------------------------------


class Stage16OrderingWitnesses(AdmissionWitnessCase):
    """The stage-16 repair, and the executable proof that the ordering is satisfiable."""

    SUPERSEDED = ("evidence manifest", "sealed run", "body-free public disposition")

    def test_no_stage_16_role_requires_an_object_sealing_has_not_produced(self) -> None:
        stage = self.profile["stages"]["SEAL_PRIVATE_EVIDENCE"]
        roles = {row["evidenceRole"] for row in stage["evidenceRoles"]}
        self.assertEqual(roles & set(self.SUPERSEDED), set())
        predicates = {key for row in stage["evidenceRoles"] for key in row["requiredPredicates"]}
        # The predicates profile @1 demanded, each a claim about an object that does not
        # exist until after sealing has already run.
        self.assertNotIn("runSealedNow", predicates)
        self.assertNotIn("dispositionIsBodyFree", predicates)

    def test_role_denominator_diverges_at_exactly_one_declared_stage(self) -> None:
        frozen = load_json(FROZEN_PACKET_PROFILE)
        succession = self.profile["stageRoleSuccession"]
        divergent = []
        for stage in self.profile["stageSequence"]:
            admitted = [row["evidenceRole"] for row in self.profile["stages"][stage]["evidenceRoles"]]
            if admitted != frozen["stages"][stage]["requiredEvidence"]:
                divergent.append(stage)
        self.assertEqual(divergent, [succession["supersededStage"]])
        self.assertEqual(succession["divergentStageCount"], len(divergent))
        self.assertEqual(
            succession["frozenAdvisoryRoles"],
            frozen["stages"][succession["supersededStage"]]["requiredEvidence"],
        )
        self.assertEqual(list(self.SUPERSEDED), succession["frozenAdvisoryRoles"])
        self.assertEqual(self.profile["supersedes"], succession["predecessorProfileId"])
        self.assertNotEqual(self.profile["profileId"], succession["predecessorProfileId"])

    def test_superseded_post_seal_roles_are_no_longer_admissible(self) -> None:
        def rename(request: dict) -> None:
            self.fixture.stage_row(request, "SEAL_PRIVATE_EVIDENCE")["evidence"][0]["evidenceRole"] = "sealed run"

        self.fixture.mutate_request(rename)
        self.assert_refuses("EVIDENCE_ROLE_UNKNOWN")

    def test_stage_16_observation_carries_only_pre_seal_facts(self) -> None:
        """Nothing stage 16 asserts may depend on an object sealing has not yet created."""
        contract = self.profile["stages"]["SEAL_PRIVATE_EVIDENCE"]["observation"]
        self.assertEqual(
            sorted(contract["keys"]),
            [
                "postSealClosureRequired",
                "preSealEvidenceManifestComplete",
                "privateBodiesOutsideGit",
                "sealAuthorizationBound",
            ],
        )
        self.assertTrue(all(value is True for value in contract["requiredValues"].values()))
        self.assertNotIn("publicDispositionBodyFree", contract["keys"])
        self.assertNotIn("sealedEvidenceClass", contract["keys"])

    def test_pre_seal_assertion_of_disposition_body_freedom_is_refused(self) -> None:
        """The exact defect this correction removes.

        A stage-16 observation may not claim the public disposition is body-free, because
        at admission time no disposition exists for that claim to be about.
        """

        def assert_future_object(request: dict) -> None:
            self.fixture.stage_row(request, "SEAL_PRIVATE_EVIDENCE")["observation"][
                "publicDispositionBodyFree"
            ] = True

        self.fixture.mutate_request(assert_future_object)
        self.assert_refuses("STAGE_OBSERVATION_INVALID")

    def test_frozen_observation_fields_are_declared_superseded(self) -> None:
        succession = self.profile["stageRoleSuccession"]
        self.assertIn("publicDispositionBodyFree", succession["supersededFrozenObservationFields"])
        self.assertTrue(succession["targetsSuccessorPacket"])
        self.assertFalse(succession["directFrozenPacketApplication"])
        self.assertIn("has not yet created", succession["supersededObservationReason"])

    def test_source_succession_forbids_direct_frozen_packet_application(self) -> None:
        succession = self.profile["sourceSuccession"]
        frozen = load_json(FROZEN_PACKET_PROFILE)
        self.assertEqual(succession["predecessorPacketProfileId"], frozen["profileId"])
        self.assertFalse(succession["directFrozenPacketApplication"])
        self.assertTrue(succession["successorPacketObservationContractRequired"])
        self.assertFalse(succession["predecessorPacketMutationAllowed"])

    def test_post_seal_assertions_are_reserved_to_the_post_seal_closure(self) -> None:
        contract = self.profile["postSealClosureContract"]
        self.assertFalse(contract["mayBeAssertedBeforeSealing"])
        self.assertIn("public disposition body-free", contract["reservedAssertions"])
        self.assertIn("detached verification PASS", contract["reservedAssertions"])
        self.assertEqual(contract["authority"], "none")
        # No stage-16 role or observation field may assert any of them.
        stage = self.profile["stages"]["SEAL_PRIVATE_EVIDENCE"]
        surface = set(stage["observation"]["keys"]) | {
            key for row in stage["evidenceRoles"] for key in row["requiredPredicates"]
        }
        self.assertNotIn("publicDispositionBodyFree", surface)
        self.assertNotIn("dispositionIsBodyFree", surface)
        self.assertNotIn("runSealedNow", surface)

    def test_seal_authorization_defers_bindings_that_do_not_yet_exist(self) -> None:
        """The seal authorization may not bind confirmations that are not yet issued.

        The three statements are supplied before the sixteen confirmations exist, so
        binding them at statement time would repeat the temporal defect one layer down.
        """
        law_block = self.profile["sealAuthorization"]
        self.assertIn("stageSixteenNonHumanEvidenceRoot", law_block["statementTimeBindings"])
        self.assertIn(
            "sixteen exact stage-confirmation identities", law_block["deferredToPreSealClosure"]
        )
        self.assertIn("final packet-stage record root", law_block["deferredToPreSealClosure"])
        self.assertIn("temporal defect", law_block["deferralReason"])

    def test_a_real_pre_record_packet_now_reaches_ready(self) -> None:
        """The regression this branch exists to fix.

        Under profile @1 a truthful zero-stage packet topped out at HOLD with the three
        stage-16 roles outstanding, because they demanded a sealed run and a disposition
        that cannot exist before sealing. Every non-human role is now supplied by a
        packet that has recorded nothing.
        """
        receipt = self.fixture.run()
        self.assertEqual(receipt["terminal"], "READY_FOR_NAMED_HUMAN_DECISION")
        self.assertEqual(receipt["admittedNonHumanEvidenceRoleCount"], 40)
        self.assertEqual(
            {row["provenanceClass"] for row in receipt["missingEvidenceRoles"]},
            {"named_human_statement"},
        )
        self.assertEqual(receipt["packetStagesRecorded"], 0)

    def test_frozen_recorder_traversal_is_mechanical_only(self) -> None:
        """Diagnostic. The frozen sequence is mechanically traversable, and only that.

        This drives the frozen, unpatched recorder from a configured 0/16 packet to
        detached verification. It is deliberately NOT an admission witness: to record
        stage 16 at all it must satisfy the frozen observation contract, which forces it
        to assert publicDispositionBodyFree about a disposition the sealer has not yet
        created. The traversal is therefore mechanical, the stage-16 admission is not
        semantically sound, and no packet completion is established by it.
        """
        node = shutil.which("node")
        self.assertIsNotNone(node, "node is required for the executable ordering witness")
        driver = self.tmp / "ordering-witness.mjs"
        driver.write_text(ORDERING_WITNESS_DRIVER, encoding="utf-8")
        pre_seal_roles = [
            row["evidenceRole"]
            for row in self.profile["stages"]["SEAL_PRIVATE_EVIDENCE"]["evidenceRoles"]
        ]
        completed = subprocess.run(
            [node, str(driver), str(ANCHOR), str(self.tmp / "ordering"), json.dumps(pre_seal_roles)],
            check=False,
            capture_output=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8", "replace"))
        result = json.loads(completed.stdout.decode("utf-8"))

        # It really did start from a configured packet with nothing recorded.
        self.assertEqual(result["initialConfigurationState"], "unconfigured")
        self.assertEqual(result["initialCompletedStageCount"], 0)
        self.assertEqual(result["configuredState"], "configured")
        self.assertEqual(result["configuredCompletedStageCount"], 0)

        # It advanced one stage at a time, in the closed order.
        self.assertEqual([row["stage"] for row in result["stageOrder"]], self.profile["stageSequence"])
        self.assertEqual([row["completed"] for row in result["stageOrder"]], list(range(1, 17)))

        # Stage 16 was recorded without any post-seal object.
        self.assertFalse(result["postSealObjectOfferedToStageSixteen"])
        self.assertEqual(result["preSealCompletedStageCount"], 16)
        self.assertFalse(result["preSealSealed"])

        # And sealing then succeeded and verified detached.
        self.assertEqual(result["verificationStatus"], "PASS")
        self.assertEqual(result["stageCount"], 16)
        self.assertEqual(result["successfulStageCount"], 15)
        self.assertEqual(result["humanRequiredStageCount"], 1)
        self.assertTrue(result["privatePhysicalFlightCompleted"])
        self.assertTrue(result["bodyFreePublicDisposition"])
        self.assertEqual(result["publicEvidenceBodies"], 0)
        self.assertGreater(result["privateEvidenceBodies"], 0)
        self.assertFalse(result["physicalEstateQualified"])
        self.assertEqual(result["authority"], "none")
        self.assertTrue(result["runId"].startswith("stcmaryphysicalflightrun1_"))

        # The boundary this diagnostic carries. Mechanical traversal only.
        mechanical_traversal_passed = result["verificationStatus"] == "PASS"
        semantic_stage16_admission_passed = (
            "publicDispositionBodyFree" not in result["frozenStageSixteenObservationKeys"]
        )
        physical_flight_completion_established = False
        self.assertTrue(mechanical_traversal_passed)
        # It had to assert a future object to get through the frozen contract at all.
        self.assertIn("publicDispositionBodyFree", result["frozenStageSixteenObservationKeys"])
        self.assertFalse(semantic_stage16_admission_passed)
        self.assertFalse(physical_flight_completion_established)

        # And the admitted profile refuses exactly that observation.
        with self.assertRaises(law.AdmissionError) as caught:
            law.validate_observation(
                "SEAL_PRIVATE_EVIDENCE",
                self.profile["stages"]["SEAL_PRIVATE_EVIDENCE"]["observation"],
                {key: True for key in result["frozenStageSixteenObservationKeys"]},
            )
        self.assertEqual(caught.exception.code, "STAGE_OBSERVATION_INVALID")

    def test_frozen_sealer_still_refuses_an_incomplete_packet(self) -> None:
        """The other arm of the original circularity, asserted from frozen source."""
        recorder = (ANCHOR / "stc_mary_private_flight_packet.mjs").read_text(encoding="utf-8")
        self.assertIn("all sixteen stages must be recorded before sealing", recorder)
        self.assertIn("PRIVATE_FLIGHT_PACKET_INCOMPLETE", recorder)


# --------------------------------------------------------------------------------
# opaque instrument bodies
# --------------------------------------------------------------------------------


class OpaqueInstrumentWitnesses(AdmissionWitnessCase):
    STAGE = "ATTACH_HALO3"
    ROLE = "runtime enumeration"
    INSTRUMENT_CLASS = "local_device_enumeration_capture"

    def make_opaque(self, *, with_receipt: bool = True, blob: bytes = b"\x00synthetic-device-enumeration\x01") -> None:
        request = self.fixture.load_request()
        descriptor = self.fixture.descriptor(request, self.STAGE, self.ROLE)
        role_law = self.fixture.role_law(self.STAGE, self.ROLE)
        opaque_law = self.profile["opaqueInstrument"]
        relative = f"{self.fixture.stage_directory(5, self.STAGE)}/{role_law['evidenceRoleKey']}.bin"
        path = self.fixture.candidates / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)

        descriptor["bodyPath"] = relative
        descriptor["bodySha256"] = law.sha256_bytes(blob)
        descriptor["bodyBytes"] = len(blob)
        descriptor["bodySchema"] = None
        descriptor["bodyContentId"] = None
        descriptor["mediaType"] = "application/octet-stream"
        descriptor["opaqueInstrumentClass"] = self.INSTRUMENT_CLASS

        if with_receipt:
            receipt_relative = f"{self.fixture.stage_directory(5, self.STAGE)}/{role_law['evidenceRoleKey']}-receipt.json"
            receipt_body = {
                "schema": opaque_law["receiptSchema"],
                "campaignId": self.fixture.campaign_id,
                "packetId": self.fixture.packet_id,
                "stage": self.STAGE,
                "sequence": 5,
                "evidenceRole": self.ROLE,
                "canonicalMissionStateDigest": self.fixture.canonical_mission_state_digest,
                "provenanceClass": opaque_law["provenanceClass"],
                "semanticPredicates": dict(role_law["requiredPredicates"]),
                "instrumentClass": self.INSTRUMENT_CLASS,
                "opaqueBodySha256": law.sha256_bytes(blob),
                "opaqueBodyBytes": len(blob),
                "capturedAtUnixNs": TRANSACTION_START + 2_000_000_000,
                "observationTransactionId": self.fixture.transaction_id,
                "authority": "none",
                "claimBoundary": "Synthetic instrument receipt for conformance only. It grants no authority.",
            }
            write_json(
                self.fixture.candidates / receipt_relative,
                sign(receipt_body, opaque_law["receiptIdKey"], opaque_law["receiptIdPrefix"]),
            )
            descriptor["instrumentReceiptPath"] = receipt_relative
        else:
            descriptor["instrumentReceiptPath"] = None
        self.fixture.write_request(request)

    def test_opaque_body_with_admitted_instrument_receipt_is_admitted(self) -> None:
        self.make_opaque()
        receipt = self.fixture.run()
        self.assertEqual(receipt["terminal"], "READY_FOR_NAMED_HUMAN_DECISION")
        self.assertEqual(receipt["admittedEvidenceRoleCount"], 40)

    def test_opaque_body_without_instrument_receipt_refuses(self) -> None:
        self.make_opaque(with_receipt=False)
        self.assert_refuses("OPAQUE_INSTRUMENT_RECEIPT_ABSENT")

    def test_instrument_receipt_that_does_not_bind_the_body_refuses(self) -> None:
        self.make_opaque()
        request = self.fixture.load_request()
        descriptor = self.fixture.descriptor(request, self.STAGE, self.ROLE)
        path = self.fixture.candidates / descriptor["instrumentReceiptPath"]
        body = load_json(path)
        body["opaqueBodySha256"] = sha256_text("another body entirely")
        opaque_law = self.profile["opaqueInstrument"]
        body.pop(opaque_law["receiptIdKey"], None)
        write_json(path, sign(body, opaque_law["receiptIdKey"], opaque_law["receiptIdPrefix"]))
        self.assert_refuses("OPAQUE_INSTRUMENT_BINDING_INVALID")

    def test_unadmitted_instrument_class_refuses(self) -> None:
        self.make_opaque()

        def widen(request: dict) -> None:
            self.fixture.descriptor(request, self.STAGE, self.ROLE)["opaqueInstrumentClass"] = "arbitrary_capture"

        self.fixture.mutate_request(widen)
        self.assert_refuses("OPAQUE_INSTRUMENT_CLASS_INVALID")

    def test_one_opaque_blob_cannot_satisfy_two_evidence_roles(self) -> None:
        """The whole point of the gate: one arbitrary blob is not a denominator."""
        blob = b"\x00one blob for every role\x01"
        self.make_opaque(blob=blob)
        request = self.fixture.load_request()
        role_law = self.fixture.role_law(self.STAGE, "power and residency receipt")
        opaque_law = self.profile["opaqueInstrument"]
        second = self.fixture.descriptor(request, self.STAGE, "power and residency receipt")
        relative = self.fixture.descriptor(request, self.STAGE, self.ROLE)["bodyPath"]
        receipt_relative = f"{self.fixture.stage_directory(5, self.STAGE)}/{role_law['evidenceRoleKey']}-receipt.json"
        receipt_body = {
            "schema": opaque_law["receiptSchema"],
            "campaignId": self.fixture.campaign_id,
            "packetId": self.fixture.packet_id,
            "stage": self.STAGE,
            "sequence": 5,
            "evidenceRole": "power and residency receipt",
            "canonicalMissionStateDigest": self.fixture.canonical_mission_state_digest,
            "provenanceClass": opaque_law["provenanceClass"],
            "semanticPredicates": dict(role_law["requiredPredicates"]),
            "instrumentClass": "local_power_and_residency_capture",
            "opaqueBodySha256": law.sha256_bytes(blob),
            "opaqueBodyBytes": len(blob),
            "capturedAtUnixNs": TRANSACTION_START + 3_000_000_000,
            "observationTransactionId": self.fixture.transaction_id,
            "authority": "none",
            "claimBoundary": "Synthetic instrument receipt for conformance only. It grants no authority.",
        }
        write_json(
            self.fixture.candidates / receipt_relative,
            sign(receipt_body, opaque_law["receiptIdKey"], opaque_law["receiptIdPrefix"]),
        )
        second["bodyPath"] = relative
        second["bodySha256"] = law.sha256_bytes(blob)
        second["bodyBytes"] = len(blob)
        second["bodySchema"] = None
        second["bodyContentId"] = None
        second["mediaType"] = "application/octet-stream"
        second["opaqueInstrumentClass"] = "local_power_and_residency_capture"
        second["instrumentReceiptPath"] = receipt_relative
        self.fixture.write_request(request)
        self.assert_refuses("DUPLICATE_EVIDENCE_IDENTITY")


# --------------------------------------------------------------------------------
# arbitrary bodies, templates, forged identities
# --------------------------------------------------------------------------------


class BodyWitnesses(AdmissionWitnessCase):
    STAGE = "VERIFY_INPUTS"
    ROLE = "input inventory receipt"

    def body_path(self) -> Path:
        descriptor = self.fixture.descriptor(self.fixture.load_request(), self.STAGE, self.ROLE)
        return self.fixture.candidates / descriptor["bodyPath"]

    def repoint(self, data: bytes) -> None:
        """Write arbitrary bytes and update the descriptor measurement honestly."""
        path = self.body_path()
        path.write_bytes(data)

        def apply(request: dict) -> None:
            descriptor = self.fixture.descriptor(request, self.STAGE, self.ROLE)
            descriptor["bodySha256"] = law.sha256_bytes(data)
            descriptor["bodyBytes"] = len(data)

        self.fixture.mutate_request(apply)

    def test_arbitrary_non_empty_file_refuses(self) -> None:
        self.repoint(b"this file is non-empty and proves nothing at all\n")
        self.assert_refuses("EVIDENCE_SCHEMA_INVALID")

    def test_untouched_evidence_envelope_template_refuses(self) -> None:
        self.repoint((json.dumps(ENVELOPE_TEMPLATE, indent=2) + "\n").encode("utf-8"))
        self.assert_refuses("EVIDENCE_SCHEMA_INVALID")

    def test_empty_body_refuses(self) -> None:
        self.repoint(b"")
        self.assert_refuses("EVIDENCE_BODY_EMPTY")

    def test_body_digest_mismatch_refuses(self) -> None:
        self.body_path().write_bytes(b'{"schema":"drifted"}\n')
        self.assert_refuses("EVIDENCE_BODY_MEASUREMENT_MISMATCH")

    def test_body_byte_count_mismatch_refuses(self) -> None:
        def apply(request: dict) -> None:
            self.fixture.descriptor(request, self.STAGE, self.ROLE)["bodyBytes"] += 1

        self.fixture.mutate_request(apply)
        self.assert_refuses("EVIDENCE_BODY_MEASUREMENT_MISMATCH")

    def test_absent_schema_refuses(self) -> None:
        def apply(request: dict) -> None:
            self.fixture.descriptor(request, self.STAGE, self.ROLE)["bodySchema"] = None

        self.fixture.mutate_request(apply)
        self.assert_refuses("EVIDENCE_SCHEMA_INVALID")

    def test_unknown_schema_refuses(self) -> None:
        def apply(request: dict) -> None:
            self.fixture.descriptor(request, self.STAGE, self.ROLE)["bodySchema"] = "somebody-elses/1"

        self.fixture.mutate_request(apply)
        self.assert_refuses("EVIDENCE_SCHEMA_INVALID")

    def test_forged_content_identity_refuses(self) -> None:
        def apply(request: dict) -> None:
            self.fixture.descriptor(request, self.STAGE, self.ROLE)["bodyContentId"] = cid(
                "stcmarypacketevidencepredecessorreceipt1", {"forged": True}
            )

        self.fixture.mutate_request(apply)
        self.assert_refuses("EVIDENCE_CONTENT_ID_FORGED")

    def test_body_edited_after_signing_refuses(self) -> None:
        path = self.body_path()
        body = load_json(path)
        body["semanticPredicates"]["admittedInputsInventoried"] = False
        write_json(path, body)
        data = path.read_bytes()

        def apply(request: dict) -> None:
            descriptor = self.fixture.descriptor(request, self.STAGE, self.ROLE)
            descriptor["bodySha256"] = law.sha256_bytes(data)
            descriptor["bodyBytes"] = len(data)

        self.fixture.mutate_request(apply)
        self.assert_refuses("EVIDENCE_CONTENT_ID_FORGED")

    def test_insufficient_semantics_refuses(self) -> None:
        self.fixture.resign_body(
            self.STAGE, self.ROLE, lambda body: body["semanticPredicates"].update({"cartridgeIdentityBound": False})
        )
        self.assert_refuses("EVIDENCE_SEMANTICS_INSUFFICIENT")

    def test_dropped_predicate_refuses(self) -> None:
        self.fixture.resign_body(
            self.STAGE, self.ROLE, lambda body: body["semanticPredicates"].pop("cartridgeIdentityBound")
        )
        self.assert_refuses("EVIDENCE_SEMANTICS_INSUFFICIENT")

    def test_evidence_class_inconsistent_with_body_refuses(self) -> None:
        def apply(request: dict) -> None:
            self.fixture.descriptor(request, self.STAGE, self.ROLE)["evidenceClass"] = "private_operator_statement"

        self.fixture.mutate_request(apply)
        self.assert_refuses("EVIDENCE_CLASS_INCONSISTENT")

    def test_media_type_inconsistent_with_body_refuses(self) -> None:
        def apply(request: dict) -> None:
            self.fixture.descriptor(request, self.STAGE, self.ROLE)["mediaType"] = "application/octet-stream"

        self.fixture.mutate_request(apply)
        self.assert_refuses("EVIDENCE_MEDIA_TYPE_INCONSISTENT")

    def test_descriptor_authority_widening_refuses(self) -> None:
        def apply(request: dict) -> None:
            self.fixture.descriptor(request, self.STAGE, self.ROLE)["authority"] = "operator"

        self.fixture.mutate_request(apply)
        self.assert_refuses("AUTHORITY_WIDENED")

    def test_body_authority_widening_refuses(self) -> None:
        self.fixture.resign_body(self.STAGE, self.ROLE, lambda body: body.update({"authority": "operator"}))
        self.assert_refuses("AUTHORITY_WIDENED")

    def test_body_escaping_the_workspace_refuses(self) -> None:
        def apply(request: dict) -> None:
            self.fixture.descriptor(request, self.STAGE, self.ROLE)["bodyPath"] = "../elsewhere.json"

        self.fixture.mutate_request(apply)
        self.assert_refuses("EVIDENCE_BODY_PATH_INVALID")


# --------------------------------------------------------------------------------
# campaign, packet, stage, role bindings
# --------------------------------------------------------------------------------


class BindingWitnesses(AdmissionWitnessCase):
    STAGE = "VERIFY_INPUTS"
    ROLE = "input inventory receipt"

    def test_request_from_another_campaign_refuses(self) -> None:
        other = cid("stcmaryflightconductorcampaign1", {"campaignLabel": OTHER_CAMPAIGN_LABEL})
        self.fixture.mutate_request(lambda request: request.update({"campaignId": other}))
        self.assert_refuses("REQUEST_CAMPAIGN_BINDING_INVALID")

    def test_request_for_another_packet_refuses(self) -> None:
        other = cid("stcmaryprivateflightpacket1", {"campaignLabel": OTHER_CAMPAIGN_LABEL})
        self.fixture.mutate_request(lambda request: request.update({"packetId": other}))
        self.assert_refuses("REQUEST_PACKET_BINDING_INVALID")

    def test_body_from_another_campaign_refuses(self) -> None:
        other = cid("stcmaryflightconductorcampaign1", {"campaignLabel": OTHER_CAMPAIGN_LABEL})
        self.fixture.resign_body(self.STAGE, self.ROLE, lambda body: body.update({"campaignId": other}))
        self.assert_refuses("EVIDENCE_CAMPAIGN_BINDING_INVALID")

    def test_body_from_another_packet_refuses(self) -> None:
        other = cid("stcmaryprivateflightpacket1", {"campaignLabel": OTHER_CAMPAIGN_LABEL})
        self.fixture.resign_body(self.STAGE, self.ROLE, lambda body: body.update({"packetId": other}))
        self.assert_refuses("EVIDENCE_PACKET_BINDING_INVALID")

    def test_valid_receipt_used_under_another_stage_refuses(self) -> None:
        self.fixture.resign_body(
            self.STAGE, self.ROLE, lambda body: body.update({"stage": "PARTITION_TWO_CELLS", "sequence": 11})
        )
        self.assert_refuses("EVIDENCE_STAGE_BINDING_INVALID")

    def test_valid_receipt_used_under_another_role_refuses(self) -> None:
        self.fixture.resign_body(
            self.STAGE, self.ROLE, lambda body: body.update({"evidenceRole": "source digest receipt"})
        )
        self.assert_refuses("EVIDENCE_ROLE_BINDING_INVALID")

    def test_evidence_role_outside_the_stage_denominator_refuses(self) -> None:
        def apply(request: dict) -> None:
            self.fixture.descriptor(request, self.STAGE, self.ROLE)["evidenceRole"] = "some other receipt"

        self.fixture.mutate_request(apply)
        self.assert_refuses("EVIDENCE_ROLE_UNKNOWN")

    def test_duplicate_role_refuses(self) -> None:
        def apply(request: dict) -> None:
            row = self.fixture.stage_row(request, self.STAGE)
            row["evidence"].append(dict(self.fixture.descriptor(request, self.STAGE, self.ROLE)))

        self.fixture.mutate_request(apply)
        self.assert_refuses("EVIDENCE_ROLE_DUPLICATED")

    def test_changed_canonical_mission_state_in_request_refuses(self) -> None:
        self.fixture.mutate_request(
            lambda request: request.update({"canonicalMissionStateDigest": sha256_text("moved")})
        )
        self.assert_refuses("CANONICAL_MISSION_STATE_CHANGED")

    def test_changed_canonical_mission_state_in_body_refuses(self) -> None:
        self.fixture.resign_body(
            self.STAGE, self.ROLE, lambda body: body.update({"canonicalMissionStateDigest": sha256_text("moved")})
        )
        self.assert_refuses("CANONICAL_MISSION_STATE_CHANGED")

    def test_provenance_class_the_role_does_not_admit_refuses(self) -> None:
        def apply(request: dict) -> None:
            self.fixture.descriptor(request, self.STAGE, self.ROLE)["provenanceClass"] = CURRENT

        self.fixture.mutate_request(apply)
        self.assert_refuses("EVIDENCE_PROVENANCE_INVALID")

    def test_wrong_availability_class_refuses(self) -> None:
        def apply(request: dict) -> None:
            self.fixture.stage_row(request, self.STAGE)["availabilityClass"] = "REQUIRES_CURRENT_LOCAL_OBSERVATION"

        self.fixture.mutate_request(apply)
        self.assert_refuses("STAGE_AVAILABILITY_CLASS_INVALID")

    def test_short_stage_denominator_refuses(self) -> None:
        self.fixture.mutate_request(lambda request: request["stages"].pop())
        self.assert_refuses("STAGE_DENOMINATOR_INVALID")

    def test_reordered_stage_denominator_refuses(self) -> None:
        def apply(request: dict) -> None:
            request["stages"][0], request["stages"][1] = request["stages"][1], request["stages"][0]

        self.fixture.mutate_request(apply)
        self.assert_refuses("STAGE_DENOMINATOR_INVALID")

    def test_forged_request_identity_refuses(self) -> None:
        request = self.fixture.load_request()
        request["claimBoundary"] = "quietly widened after signing"
        write_json(self.fixture.request_path(), request)
        self.assert_refuses("ADMISSION_REQUEST_ID_INVALID")


# --------------------------------------------------------------------------------
# provenance: reuse, current observation, staleness
# --------------------------------------------------------------------------------


class ProvenanceWitnesses(AdmissionWitnessCase):
    RECEIPT_STAGE = "VERIFY_INPUTS"
    RECEIPT_ROLE = "input inventory receipt"
    CURRENT_STAGE = "REMOVE_HALO3"
    CURRENT_ROLE = "device removal receipt"

    def test_reused_receipt_is_reported_as_a_reused_pre_stage_receipt(self) -> None:
        receipt = self.fixture.run()
        self.assertEqual(receipt["reusedPredecessorReceiptCount"], 23)
        row = next(entry for entry in receipt["stages"] if entry["stage"] == self.RECEIPT_STAGE)
        self.assertEqual(row["reusedPredecessorReceiptCount"], 2)
        self.assertEqual(row["currentObservationCount"], 0)

    def test_receipt_without_the_reuse_class_refuses(self) -> None:
        self.fixture.resign_body(
            self.RECEIPT_STAGE, self.RECEIPT_ROLE, lambda body: body.update({"reuseClass": "captured_during_stage"})
        )
        self.assert_refuses("PREDECESSOR_REUSE_CLASS_INVALID")

    def test_receipt_outside_the_accepted_graph_refuses(self) -> None:
        self.fixture.resign_body(
            self.RECEIPT_STAGE,
            self.RECEIPT_ROLE,
            lambda body: body.update(
                {"acceptedPredecessorCoordinate": cid("stcmaryflightconductoracceptedpredecessor1", {"other": True})}
            ),
        )
        self.assert_refuses("PREDECESSOR_OUTSIDE_ACCEPTED_GRAPH")

    def test_receipt_identity_not_in_its_coordinate_refuses(self) -> None:
        self.fixture.resign_body(
            self.RECEIPT_STAGE,
            self.RECEIPT_ROLE,
            lambda body: body.update({"sourceReceiptId": cid("syntheticpredecessorreceipt1", {"unknown": True})}),
        )
        self.assert_refuses("PREDECESSOR_OUTSIDE_ACCEPTED_GRAPH")

    def test_predecessor_coordinate_from_another_campaign_refuses(self) -> None:
        other = cid("stcmaryflightconductorcampaign1", {"campaignLabel": OTHER_CAMPAIGN_LABEL})

        def apply(request: dict) -> None:
            request["acceptedPredecessorGraph"][0]["campaignId"] = other

        self.fixture.mutate_request(apply)
        self.assert_refuses("PREDECESSOR_CAMPAIGN_BINDING_INVALID")

    def test_reused_receipt_backdated_into_the_transaction_refuses(self) -> None:
        self.fixture.resign_body(
            self.RECEIPT_STAGE,
            self.RECEIPT_ROLE,
            lambda body: body.update({"capturedAtUnixNs": TRANSACTION_START + 5}),
        )
        self.assert_refuses("PREDECESSOR_RECEIPT_MISREPRESENTED_AS_FRESH")

    def test_stale_current_observation_refuses(self) -> None:
        self.fixture.resign_body(
            self.CURRENT_STAGE,
            self.CURRENT_ROLE,
            lambda body: body.update({"capturedAtUnixNs": TRANSACTION_START - 1}),
        )
        self.assert_refuses("CURRENT_OBSERVATION_STALE")

    def test_current_observation_from_another_transaction_refuses(self) -> None:
        self.fixture.resign_body(
            self.CURRENT_STAGE,
            self.CURRENT_ROLE,
            lambda body: body.update(
                {"observationTransactionId": cid("stcmarypacketevidenceobservationtransaction1", {"other": True})}
            ),
        )
        self.assert_refuses("CURRENT_OBSERVATION_TRANSACTION_INVALID")

    def test_current_observation_claiming_history_refuses(self) -> None:
        self.fixture.resign_body(
            self.CURRENT_STAGE, self.CURRENT_ROLE, lambda body: body.update({"claimsHistoricalTransition": True})
        )
        self.assert_refuses("CURRENT_OBSERVATION_CLAIMS_HISTORY")

    def test_unbounded_observation_transaction_refuses(self) -> None:
        def apply(request: dict) -> None:
            transaction = dict(request["observationTransaction"])
            transaction["endedAtUnixNs"] = (
                transaction["startedAtUnixNs"] + self.profile["observationTransaction"]["maxWindowNs"] + 1
            )
            transaction.pop(self.profile["observationTransaction"]["idKey"], None)
            request["observationTransaction"] = sign(
                transaction,
                self.profile["observationTransaction"]["idKey"],
                self.profile["observationTransaction"]["idPrefix"],
            )

        self.fixture.mutate_request(apply)
        self.assert_refuses("OBSERVATION_TRANSACTION_UNBOUNDED")

    def test_forged_observation_transaction_identity_refuses(self) -> None:
        def apply(request: dict) -> None:
            request["observationTransaction"]["endedAtUnixNs"] += 1

        self.fixture.mutate_request(apply)
        self.assert_refuses("OBSERVATION_TRANSACTION_ID_INVALID")


# --------------------------------------------------------------------------------
# stage observations
# --------------------------------------------------------------------------------


class ObservationWitnesses(AdmissionWitnessCase):
    def test_template_observation_value_refuses(self) -> None:
        def apply(request: dict) -> None:
            self.fixture.stage_row(request, "VERIFY_INPUTS")["observation"]["profileValidated"] = False

        self.fixture.mutate_request(apply)
        self.assert_refuses("STAGE_OBSERVATION_INVALID")

    def test_placeholder_content_identity_refuses(self) -> None:
        def apply(request: dict) -> None:
            self.fixture.stage_row(request, "VERIFY_INPUTS")["observation"]["inputDigestRoot"] = "REPLACE_WITH_DIGEST"

        self.fixture.mutate_request(apply)
        self.assert_refuses("STAGE_OBSERVATION_INVALID")

    def test_extra_observation_field_refuses(self) -> None:
        def apply(request: dict) -> None:
            self.fixture.stage_row(request, "VERIFY_INPUTS")["observation"]["extra"] = True

        self.fixture.mutate_request(apply)
        self.assert_refuses("STAGE_OBSERVATION_INVALID")

    def test_conflict_observation_that_merges_refuses(self) -> None:
        def apply(request: dict) -> None:
            row = self.fixture.stage_row(request, "RESTORE_LINK_HOLD_CONFLICT")
            row["observation"]["automaticMerge"] = True

        self.fixture.mutate_request(apply)
        self.assert_refuses("STAGE_OBSERVATION_INVALID")

    def test_conflict_observation_with_collapsed_branches_refuses(self) -> None:
        def apply(request: dict) -> None:
            row = self.fixture.stage_row(request, "RESTORE_LINK_HOLD_CONFLICT")
            row["observation"]["rightStateDigest"] = row["observation"]["leftStateDigest"]

        self.fixture.mutate_request(apply)
        self.assert_refuses("STAGE_OBSERVATION_INVALID")

    def test_seal_stage_leaking_private_bodies_refuses(self) -> None:
        def apply(request: dict) -> None:
            row = self.fixture.stage_row(request, "SEAL_PRIVATE_EVIDENCE")
            row["observation"]["privateEvidenceBodiesCommittedToGit"] = True

        self.fixture.mutate_request(apply)
        self.assert_refuses("STAGE_OBSERVATION_INVALID")

    def test_replace_head_transferring_authority_refuses(self) -> None:
        def apply(request: dict) -> None:
            self.fixture.stage_row(request, "REPLACE_HEAD")["observation"]["authorityTransferred"] = True

        self.fixture.mutate_request(apply)
        self.assert_refuses("STAGE_OBSERVATION_INVALID")


# --------------------------------------------------------------------------------
# named-human statements
# --------------------------------------------------------------------------------


class HumanStatementWitnesses(AdmissionWitnessCase):
    def test_machine_authored_statement_refuses(self) -> None:
        self.fixture.add_human_statements()
        self.fixture.resign_body("BIND_GRACE", "operator statement", lambda body: body.update({"actorClass": "model"}))
        self.assert_refuses("HUMAN_STATEMENT_ACTOR_INVALID")

    def test_verifier_authored_statement_refuses(self) -> None:
        self.fixture.add_human_statements()
        self.fixture.resign_body(
            "BIND_GRACE", "operator statement", lambda body: body.update({"actorClass": "verifier"})
        )
        self.assert_refuses("HUMAN_STATEMENT_ACTOR_INVALID")

    def test_partial_statement_set_refuses(self) -> None:
        self.fixture.add_human_statements()

        def drop(request: dict) -> None:
            row = self.fixture.stage_row(request, "BIND_GRACE")
            row["evidence"] = [
                entry for entry in row["evidence"] if entry["evidenceRole"] != "operator statement"
            ]

        self.fixture.mutate_request(drop)
        self.assert_refuses("HUMAN_STATEMENT_DENOMINATOR_INVALID")

    def test_conflict_statement_selecting_a_winner_refuses(self) -> None:
        self.fixture.add_human_statements()
        self.fixture.resign_body(
            "RESTORE_LINK_HOLD_CONFLICT",
            "human-required obligation receipt",
            lambda body: body.update({"selectedWinner": body["retainedBranches"][0]}),
        )
        self.assert_refuses("CONFLICT_STATEMENT_SELECTS_WINNER")

    def test_conflict_statement_permitting_automatic_merge_refuses(self) -> None:
        self.fixture.add_human_statements()
        self.fixture.resign_body(
            "RESTORE_LINK_HOLD_CONFLICT",
            "human-required obligation receipt",
            lambda body: body.update({"automaticMerge": True}),
        )
        self.assert_refuses("CONFLICT_STATEMENT_AUTOMATIC_MERGE")

    def test_conflict_statement_dropping_a_branch_refuses(self) -> None:
        self.fixture.add_human_statements()
        self.fixture.resign_body(
            "RESTORE_LINK_HOLD_CONFLICT",
            "human-required obligation receipt",
            lambda body: body.update({"retainedBranches": body["retainedBranches"][:1]}),
        )
        self.assert_refuses("CONFLICT_STATEMENT_BRANCHES_LOST")

    def test_conflict_statement_discharging_the_obligation_refuses(self) -> None:
        self.fixture.add_human_statements()
        self.fixture.resign_body(
            "RESTORE_LINK_HOLD_CONFLICT",
            "human-required obligation receipt",
            lambda body: body.update({"terminalOrRetainedObligation": "PASS"}),
        )
        self.assert_refuses("HUMAN_STATEMENT_TERMINAL_INVALID")

    def test_statement_accepting_an_unadmitted_identity_refuses(self) -> None:
        self.fixture.add_human_statements()
        self.fixture.resign_body(
            "BIND_GRACE",
            "operator statement",
            lambda body: body.update(
                {"acceptedEvidenceIds": [cid("stcmarypacketevidencepredecessorreceipt1", {"unseen": True})]}
            ),
        )
        self.assert_refuses("HUMAN_STATEMENT_SCOPE_INVALID")

    def test_non_conflict_statement_carrying_conflict_fields_refuses(self) -> None:
        self.fixture.add_human_statements()
        self.fixture.resign_body(
            "BIND_GRACE",
            "operator statement",
            lambda body: body.update({"retainedBranches": [sha256_text("a"), sha256_text("b")]}),
        )
        self.assert_refuses("HUMAN_STATEMENT_SCOPE_INVALID")


# --------------------------------------------------------------------------------
# stage confirmations
# --------------------------------------------------------------------------------


class ConfirmationWitnesses(AdmissionWitnessCase):
    def test_machine_issued_confirmation_refuses(self) -> None:
        self.fixture.complete()

        def apply(request: dict) -> None:
            row = dict(request["stageConfirmations"][0])
            row["actorClass"] = "scheduler"
            row.pop(self.profile["confirmation"]["idKey"], None)
            request["stageConfirmations"][0] = sign(
                row, self.profile["confirmation"]["idKey"], self.profile["confirmation"]["idPrefix"]
            )

        self.fixture.mutate_request(apply)
        self.assert_refuses("STAGE_CONFIRMATION_ACTOR_INVALID")

    def test_missing_confirmation_refuses(self) -> None:
        self.fixture.complete()
        self.fixture.mutate_request(lambda request: request["stageConfirmations"].pop())
        self.assert_refuses("STAGE_CONFIRMATION_DENOMINATOR_INVALID")

    def test_replayed_confirmation_refuses(self) -> None:
        self.fixture.complete()

        def apply(request: dict) -> None:
            request["stageConfirmations"][1] = dict(request["stageConfirmations"][0])

        self.fixture.mutate_request(apply)
        self.assert_refuses("STAGE_CONFIRMATION_REPLAYED")

    def test_confirmation_bound_to_another_evidence_root_refuses(self) -> None:
        self.fixture.complete()

        def apply(request: dict) -> None:
            row = dict(request["stageConfirmations"][0])
            row["evidenceAdmissionRoot"] = cid("stcmarypacketevidencestageroot1", {"other": True})
            row.pop(self.profile["confirmation"]["idKey"], None)
            request["stageConfirmations"][0] = sign(
                row, self.profile["confirmation"]["idKey"], self.profile["confirmation"]["idPrefix"]
            )

        self.fixture.mutate_request(apply)
        self.assert_refuses("STAGE_CONFIRMATION_ROOT_MISMATCH")

    def test_confirmation_bound_to_another_observation_refuses(self) -> None:
        self.fixture.complete()

        def apply(request: dict) -> None:
            row = dict(request["stageConfirmations"][0])
            row["observationDigest"] = cid("stcmarypacketevidenceobservationdigest1", {"other": True})
            row.pop(self.profile["confirmation"]["idKey"], None)
            request["stageConfirmations"][0] = sign(
                row, self.profile["confirmation"]["idKey"], self.profile["confirmation"]["idPrefix"]
            )

        self.fixture.mutate_request(apply)
        self.assert_refuses("STAGE_CONFIRMATION_ROOT_MISMATCH")

    def test_confirmation_replayed_from_another_campaign_refuses(self) -> None:
        self.fixture.complete()
        other = cid("stcmaryflightconductorcampaign1", {"campaignLabel": OTHER_CAMPAIGN_LABEL})

        def apply(request: dict) -> None:
            row = dict(request["stageConfirmations"][0])
            row["campaignId"] = other
            row.pop(self.profile["confirmation"]["idKey"], None)
            request["stageConfirmations"][0] = sign(
                row, self.profile["confirmation"]["idKey"], self.profile["confirmation"]["idPrefix"]
            )

        self.fixture.mutate_request(apply)
        self.assert_refuses("STAGE_CONFIRMATION_CAMPAIGN_BINDING_INVALID")

    def test_confirmation_naming_another_terminal_refuses(self) -> None:
        self.fixture.complete()

        def apply(request: dict) -> None:
            row = next(
                entry for entry in request["stageConfirmations"] if entry["stage"] == "RESTORE_LINK_HOLD_CONFLICT"
            )
            row["requiredTerminal"] = "PASS"
            row.pop(self.profile["confirmation"]["idKey"], None)
            row.update(
                sign(row, self.profile["confirmation"]["idKey"], self.profile["confirmation"]["idPrefix"])
            )

        self.fixture.mutate_request(apply)
        self.assert_refuses("STAGE_CONFIRMATION_TERMINAL_INVALID")

    def test_named_human_refusal_refuses_the_whole_denominator(self) -> None:
        self.fixture.complete(decision="REFUSE_STAGE")
        self.assert_refuses("STAGE_DECISION_REFUSED")

    def test_confirmations_before_the_evidence_is_complete_refuse(self) -> None:
        """A named human may not confirm sixteen stages over an incomplete denominator.

        The confirmations are deliberately re-issued against the *incomplete* roots, so
        that the root-binding guard cannot be what fires and the completeness law is the
        predicate under witness.
        """
        self.fixture.complete()

        def drop(request: dict) -> None:
            row = self.fixture.stage_row(request, "VERIFY_INPUTS")
            row["evidence"] = [
                entry for entry in row["evidence"] if entry["evidenceRole"] != "source digest receipt"
            ]
            request["stageConfirmations"] = []

        self.fixture.mutate_request(drop)
        incomplete = self.fixture.run()
        self.assertEqual(incomplete["terminal"], "HOLD")
        confirmations = self.fixture.confirmations_from(incomplete)
        self.fixture.mutate_request(lambda request: request.update({"stageConfirmations": confirmations}))
        self.assert_refuses("STAGE_CONFIRMATION_ON_INCOMPLETE_EVIDENCE")

    def test_blanket_batch_confirmation_without_stage_enumeration_refuses(self) -> None:
        self.fixture.complete(with_batch=True)

        def apply(request: dict) -> None:
            batch = dict(request["batchConfirmation"])
            batch["stages"] = []
            batch["stageCount"] = 0
            batch.pop(self.profile["batchConfirmation"]["idKey"], None)
            request["batchConfirmation"] = sign(
                batch, self.profile["batchConfirmation"]["idKey"], self.profile["batchConfirmation"]["idPrefix"]
            )

        self.fixture.mutate_request(apply)
        self.assert_refuses("BATCH_CONFIRMATION_UNBOUNDED")

    def test_batch_confirmation_without_exact_decisions_refuses(self) -> None:
        """A batch may accompany the sixteen exact decisions; it may not replace them."""
        self.fixture.complete(with_batch=True)
        self.fixture.mutate_request(lambda request: request.update({"stageConfirmations": []}))
        self.assert_refuses("BATCH_CONFIRMATION_UNBOUNDED")

    def test_batch_confirmation_disagreeing_with_an_exact_decision_refuses(self) -> None:
        self.fixture.complete(with_batch=True)

        def apply(request: dict) -> None:
            batch = dict(request["batchConfirmation"])
            batch["stages"] = [dict(row) for row in batch["stages"]]
            batch["stages"][0]["decisionCode"] = "HOLD_STAGE"
            batch.pop(self.profile["batchConfirmation"]["idKey"], None)
            request["batchConfirmation"] = sign(
                batch, self.profile["batchConfirmation"]["idKey"], self.profile["batchConfirmation"]["idPrefix"]
            )

        self.fixture.mutate_request(apply)
        self.assert_refuses("BATCH_CONFIRMATION_ROOT_MISMATCH")


# --------------------------------------------------------------------------------
# the frozen packet surface
# --------------------------------------------------------------------------------


class FrozenPacketWitnesses(AdmissionWitnessCase):
    def test_unconfigured_packet_refuses(self) -> None:
        path = self.fixture.packet / self.profile["packet"]["stateFile"]
        state = load_json(path)
        state["configurationState"] = "unconfigured"
        state.pop("stateId", None)
        write_json(path, sign(state, "stateId", self.profile["packet"]["stateIdPrefix"]))
        self.assert_refuses("PACKET_NOT_CONFIGURED")

    def test_packet_that_already_recorded_a_stage_refuses(self) -> None:
        path = self.fixture.packet / self.profile["packet"]["stateFile"]
        state = load_json(path)
        state["stages"][0]["status"] = "recorded"
        state["stages"][0]["evidenceCount"] = 2
        state["stages"][0]["recordDigest"] = cid("stcmaryprivateflightstagerecord1", {"sequence": 1})
        state["completedStageCount"] = 1
        state["nextStage"] = self.profile["stageSequence"][1]
        state.pop("stateId", None)
        write_json(path, sign(state, "stateId", self.profile["packet"]["stateIdPrefix"]))
        self.assert_refuses("PACKET_STAGES_ALREADY_RECORDED")

    def test_sealed_packet_refuses(self) -> None:
        path = self.fixture.packet / self.profile["packet"]["stateFile"]
        state = load_json(path)
        state["sealed"] = True
        state["sealedDispositionId"] = cid("stcmarypublicphysicalflightdisposition1", {"synthetic": True})
        state.pop("stateId", None)
        write_json(path, sign(state, "stateId", self.profile["packet"]["stateIdPrefix"]))
        self.assert_refuses("PACKET_ALREADY_SEALED")

    def test_packet_from_another_campaign_refuses(self) -> None:
        path = self.fixture.packet / self.profile["packet"]["markerFile"]
        marker = load_json(path)
        marker["campaignLabel"] = OTHER_CAMPAIGN_LABEL
        marker.pop("markerId", None)
        write_json(path, sign(marker, "markerId", self.profile["packet"]["markerIdPrefix"]))
        self.assert_refuses("PACKET_CAMPAIGN_BINDING_INVALID")

    def test_forged_packet_state_identity_refuses(self) -> None:
        path = self.fixture.packet / self.profile["packet"]["stateFile"]
        state = load_json(path)
        state["claimBoundary"] = "quietly widened after signing"
        write_json(path, state)
        self.assert_refuses("PACKET_STATE_ID_INVALID")

    def test_workstation_marker_from_another_conductor_refuses(self) -> None:
        path = self.fixture.workstation / self.profile["workstation"]["markerFile"]
        marker = load_json(path)
        marker["profileId"] = "somebody-elses/0.1"
        marker.pop("markerId", None)
        write_json(path, sign(marker, "markerId", self.profile["workstation"]["markerIdPrefix"]))
        self.assert_refuses("WORKSTATION_MARKER_INVALID")

    def test_admission_workspace_inside_the_packet_refuses(self) -> None:
        inside = self.fixture.packet / "admission"
        shutil.copytree(self.fixture.candidates, inside)
        self.assert_refuses("ADMISSION_WORKSPACE_INSIDE_PACKET", candidates=inside)


# --------------------------------------------------------------------------------
# source identity and bootstrap
# --------------------------------------------------------------------------------


class SourceWitnesses(AdmissionWitnessCase):
    def test_admission_source_never_claims_the_frozen_packet_runtime(self) -> None:
        self.assertTrue(
            set(self.profile["admissionSourceMembers"]).isdisjoint(set(self.profile["frozenRuntimeMembers"]))
        )
        for relative in self.profile["frozenRuntimeMembers"]:
            self.assertTrue((REPOSITORY_ROOT / relative).is_file(), relative)

    def test_admission_source_set_is_separately_identified(self) -> None:
        receipt = self.fixture.run()
        self.assertTrue(receipt["admissionSourceSetId"].startswith("stcmarypacketevidenceadmissionsourceset1_"))
        self.assertEqual(receipt["admissionSourceMemberCount"], len(self.profile["admissionSourceMembers"]))

    def test_profile_canonical_digest_is_pinned(self) -> None:
        profile = law.load_profile(PROFILE)
        self.assertEqual(law.sha256_bytes(law.canonical_json_bytes(profile)), law.PROFILE_CANONICAL_SHA256)

    def test_drifted_profile_refuses(self) -> None:
        drifted = self.tmp / "drifted-profile.json"
        profile = load_json(PROFILE)
        profile["status"] = "quietly_widened"
        write_json(drifted, profile)
        with self.assertRaises(law.AdmissionError) as caught:
            law.load_profile(drifted)
        self.assertEqual(caught.exception.code, "PROFILE_CANONICAL_DIGEST_INVALID")

    def test_direct_run_cannot_self_assert_bootstrap_authentication(self) -> None:
        receipt = self.fixture.run()
        self.assertFalse(receipt["bootstrapAuthenticated"])
        self.assertIsNone(receipt["measuredVerifierSha256"])

    def test_measured_verifier_must_be_the_stored_source_member(self) -> None:
        self.assert_refuses("MEASURED_VERIFIER_MEMBER_BINDING_INVALID", measured_verifier_bytes=b"not the gate")

    def test_bootstrap_authenticates_the_measured_gate(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(ANCHOR / "verify_stc_mary_packet_evidence_admission_bootstrap.py"),
                "--workstation",
                str(self.fixture.workstation),
                "--packet",
                str(self.fixture.packet),
                "--candidates",
                str(self.fixture.candidates),
                "--profile",
                str(PROFILE),
                "--admission-source-root",
                str(REPOSITORY_ROOT),
            ],
            check=False,
            capture_output=True,
        )
        verdict = json.loads(completed.stdout.decode("utf-8"))
        self.assertEqual(completed.returncode, 0, verdict)
        self.assertTrue(verdict["bootstrapAuthenticated"])
        self.assertEqual(verdict["terminal"], "READY_FOR_NAMED_HUMAN_DECISION")
        self.assertEqual(verdict["packetStagesRecorded"], 0)
        self.assertEqual(verdict["operatorConfirmedFlagsSet"], 0)
        self.assertEqual(
            verdict["bootstrapVerifierSha256"],
            law.sha256_bytes((ANCHOR / "verify_stc_mary_packet_evidence_admission.py").read_bytes()),
        )

    def test_frontend_denominator_lane_is_body_free(self) -> None:
        document = frontend.denominator_document(law.load_profile(PROFILE))
        self.assertEqual(document["denominator"]["evidenceRoleDenominator"], 43)
        self.assertEqual(len(document["stages"]), 16)
        self.assertEqual(document["packetStagesRecorded"], 0)
        law.assert_no_private_material(document, code="X", label="denominator")

    def test_hosted_gate_pins_the_exact_witness_denominator(self) -> None:
        """The hosted gate must assert a count, not merely grep for a generic OK.

        A run that loses witnesses, or one whose discovery pattern silently stops
        matching, still prints OK. Pinning the number in the workflow closes that, and
        asserting the pin against live discovery here keeps the pin from drifting.
        """
        workflow = (
            REPOSITORY_ROOT / ".github/workflows/stc-mary-packet-evidence-admission-01.yml"
        ).read_text(encoding="utf-8")
        match = re.search(r'^\s*WITNESS_DENOMINATOR:\s*"(\d+)"\s*$', workflow, re.M)
        self.assertIsNotNone(match, "the hosted workflow pins no witness denominator")
        pinned = int(match.group(1))
        discovered = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__]).countTestCases()
        self.assertEqual(
            pinned,
            discovered,
            f"the hosted workflow pins {pinned} witnesses but this suite carries {discovered}",
        )
        self.assertIn("focused witness denominator differs", workflow)
        self.assertIn("did not terminate on a clean OK", workflow)

    def test_bootstrap_schema_is_separately_identified(self) -> None:
        self.assertNotEqual(bootstrap.BOOTSTRAP_SCHEMA, law.RECEIPT_SCHEMA)
        self.assertEqual(bootstrap.VERIFIER_FILENAME, "verify_stc_mary_packet_evidence_admission.py")


if __name__ == "__main__":
    unittest.main()
