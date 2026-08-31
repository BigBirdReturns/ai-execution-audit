"""Permanent witnesses for the STC MARY sealed-campaign compatibility verifier.

Every fixture in this file is synthetic. No real campaign identity, no private
coordinate, no evidence body, and no sealed Campaign package appears here. The
fixtures reproduce only the body-free object shapes, the predecessor refusal, and the
cross-binding mechanism, so that the law can be exercised without importing any
private material into the public repository.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ANCHOR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ANCHOR.parent.parent
sys.path.insert(0, str(ANCHOR))

import stc_mary_sealed_campaign_compatibility as frontend  # noqa: E402
import verify_stc_mary_sealed_campaign_compatibility as law  # noqa: E402
import verify_stc_mary_sealed_campaign_compatibility_bootstrap as bootstrap  # noqa: E402

PROFILE = ANCHOR / "stc-mary-sealed-campaign-compatibility-profile-01.json"

SYNTHETIC_CAMPAIGN_LABEL = "SYNTHETIC-COMPAT-WITNESS-01"
OTHER_CAMPAIGN_LABEL = "SYNTHETIC-COMPAT-WITNESS-02"


def cid(prefix: str, body) -> str:
    return law.content_id(prefix, body)


def sign(body: dict, id_key: str, prefix: str) -> dict:
    return {**body, id_key: cid(prefix, body)}


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def resign(path: Path, id_key: str, prefix: str) -> dict:
    value = load_json(path)
    value.pop(id_key, None)
    signed = sign(value, id_key, prefix)
    write_json(path, signed)
    return signed


class Fixture:
    """One complete, internally consistent synthetic campaign that passes."""

    def __init__(self, root: Path, profile: dict, campaign_label: str = SYNTHETIC_CAMPAIGN_LABEL):
        self.root = root
        self.profile = profile
        self.campaign_label = campaign_label
        self.checkout = root / "conductor-checkout"
        self.workstation = root / "workstation"
        self.packet = root / "campaign" / "packet"
        self.sealed = root / "campaign" / "sealed"
        self._build()

    # -- predecessor conductor checkout -----------------------------------
    def _build_checkout(self) -> str:
        law_block = self.profile["predecessor"]
        predicate = law_block["impossiblePredicate"]
        for relative in law_block["sourceMembers"]:
            member = self.checkout / relative
            member.parent.mkdir(parents=True, exist_ok=True)
            if relative == predicate["relativePath"]:
                member.write_text(
                    "# synthetic predecessor conductor stand-in\n"
                    "def validate_public_disposition(value, campaign_label):\n"
                    f"    {predicate['expression']}\n",
                    encoding="utf-8",
                )
            else:
                member.write_text(f"# synthetic predecessor member: {relative}\n", encoding="utf-8")
        measured = law.measure_source_set(
            self.checkout,
            law_block["sourceMembers"],
            schema=law_block["sourceSetSchema"],
            profile_id=law_block["conductorProfileId"],
            claim_boundary=law_block["sourceSetClaimBoundary"],
            id_key=law_block["sourceSetIdKey"],
            id_prefix=law_block["sourceSetIdPrefix"],
            code="PREDECESSOR_SOURCE_SET_INVALID",
            label="predecessor source set",
        )
        return measured[law_block["sourceSetIdKey"]]

    # -- sealed package ----------------------------------------------------
    def _build_sealed(self) -> None:
        sealed_law = self.profile["sealedPackage"]
        denominator = self.profile["campaignDenominator"]
        self.sealed.mkdir(parents=True, exist_ok=True)

        run_body = {
            "schema": "stc-mary-private-flight-run/1",
            "flightMode": sealed_law["requiredFlightMode"],
            "stageCount": denominator["stageDenominator"],
        }
        run = sign(run_body, "runId", "stcmaryprivateflightrun1")
        self.run_id = run["runId"]

        disposition_body = {
            "schema": sealed_law["publicDispositionSchema"],
            "runId": self.run_id,
            "profileId": "stc-mary/physical-flight/0.1",
            "flightMode": sealed_law["requiredFlightMode"],
            "stageReceiptIds": [
                cid("stcmarystagereceipt1", {"sequence": index})
                for index in range(1, denominator["stageDenominator"] + 1)
            ],
            "stageCount": denominator["stageDenominator"],
            "successfulStageCount": denominator["successfulStageCount"],
            "humanRequiredStageCount": denominator["humanRequiredStageCount"],
            "evidenceDigestRoot": cid("stcmarypublicevidenceroot1", ["synthetic"]),
            "privatePhysicalEvidenceBodyCount": denominator["privateEvidenceBodyCount"],
            "publicEvidenceBodyCount": denominator["publicEvidenceBodyCount"],
            "privatePhysicalFlightCompleted": True,
            "selfAttestationOnly": True,
            "physicalEstateQualified": False,
            "representativeOperatorQualified": False,
            "fieldNetworkQualified": False,
            "operationalC2Qualified": False,
            "productionLatticeQualified": False,
            "authority": "none",
            "claimBoundary": "Synthetic body-free disposition for conformance only. It grants no qualification or authority.",
        }
        disposition = sign(disposition_body, "dispositionId", sealed_law["publicDispositionIdPrefix"])
        self.disposition_id = disposition["dispositionId"]

        marker_body = {
            "schema": sealed_law["markerSchema"],
            "runId": self.run_id,
            "dispositionId": self.disposition_id,
            "flightMode": sealed_law["requiredFlightMode"],
            "publicEvidenceBodyCount": denominator["publicEvidenceBodyCount"],
            "authority": "none",
            "claimBoundary": "Synthetic sealed marker for conformance only.",
        }
        marker = sign(marker_body, "markerId", sealed_law["markerIdPrefix"])

        verification_body = {
            "schema": sealed_law["verificationSchema"],
            "runId": self.run_id,
            "dispositionId": self.disposition_id,
            "status": "PASS",
            "fileCount": denominator["manifestFileCount"],
            "stageCount": denominator["stageDenominator"],
            "privatePhysicalEvidenceBodyCount": denominator["privateEvidenceBodyCount"],
            "publicEvidenceBodyCount": denominator["publicEvidenceBodyCount"],
            "bodyFreePublicDisposition": True,
            "deterministicReceiptReplay": True,
            "physicalEstateQualified": False,
            "representativeOperatorQualified": False,
            "fieldNetworkQualified": False,
            "operationalC2Qualified": False,
            "productionLatticeQualified": False,
            "authority": "none",
            "claimBoundary": "Synthetic detached verification for conformance only.",
        }
        verification = sign(verification_body, "verificationId", sealed_law["verificationIdPrefix"])

        write_json(self.sealed / sealed_law["markerFile"], marker)
        write_json(self.sealed / sealed_law["runFile"], run)
        write_json(self.sealed / sealed_law["publicDispositionFile"], disposition)
        write_json(self.sealed / sealed_law["verificationFile"], verification)
        (self.sealed / "review.html").write_text("<!doctype html><title>synthetic</title>\n", encoding="utf-8")
        self.rebuild_manifest()
        write_json(self.sealed / sealed_law["detachedVerificationFile"], verification)

    def rebuild_manifest(self) -> None:
        sealed_law = self.profile["sealedPackage"]
        rows = []
        for name in sorted(sealed_law["manifestMemberFiles"]):
            data = (self.sealed / name).read_bytes()
            rows.append({"path": name, "bytes": len(data), "sha256": law.sha256_bytes(data)})
        manifest_marker = load_json(self.sealed / sealed_law["markerFile"])
        body = {
            "schema": sealed_law["manifestSchema"],
            "runId": manifest_marker["runId"],
            "dispositionId": manifest_marker["dispositionId"],
            "files": rows,
            "fileCount": len(rows),
            "publicEvidenceBodyCount": 0,
            "authority": "none",
            "claimBoundary": "Synthetic sealed manifest for conformance only.",
        }
        write_json(self.sealed / sealed_law["manifestFile"], sign(body, "manifestId", sealed_law["manifestIdPrefix"]))

    # -- packet ------------------------------------------------------------
    def _build_packet(self) -> None:
        packet_law = self.profile["packet"]
        denominator = self.profile["campaignDenominator"]
        marker_body = {
            "schema": packet_law["markerSchema"],
            "packetProfileId": "stc-mary/private-flight-packet/0.1",
            "physicalProfileId": "stc-mary/physical-flight/0.1",
            "campaignLabel": self.campaign_label,
            "packetId": cid("stcmaryprivateflightpacket1", {"campaignLabel": self.campaign_label}),
            "authority": "none",
            "claimBoundary": "Synthetic packet marker for conformance only.",
        }
        marker = sign(marker_body, "markerId", packet_law["markerIdPrefix"])
        write_json(self.packet / packet_law["markerFile"], marker)

        state_body = {
            "schema": packet_law["stateSchema"],
            "packetId": marker["packetId"],
            "campaignLabel": self.campaign_label,
            "packetProfileId": marker["packetProfileId"],
            "physicalProfileId": marker["physicalProfileId"],
            "configurationState": "configured",
            "stageDenominator": denominator["stageDenominator"],
            "stages": [{"sequence": index, "status": "recorded"} for index in range(1, denominator["stageDenominator"] + 1)],
            "completedStageCount": denominator["stageDenominator"],
            "nextStage": None,
            "sealed": True,
            "sealedDispositionId": self.disposition_id,
            "authority": "none",
            "claimBoundary": "Synthetic packet state for conformance only.",
        }
        write_json(self.packet / packet_law["stateFile"], sign(state_body, "stateId", packet_law["stateIdPrefix"]))

    # -- workstation -------------------------------------------------------
    def _build_workstation(self, source_set_id: str) -> None:
        pre = self.profile["predecessor"]
        ws_law = self.profile["workstation"]
        self.workstation.mkdir(parents=True, exist_ok=True)

        campaign_id = cid("stcmaryflightconductorcampaign1", {"campaignLabel": self.campaign_label})

        path_map_body = {
            "schema": pre["pathMapSchema"],
            "campaignId": campaign_id,
            "paths": {
                "packet": str(self.packet),
                "packetState": str(self.packet / self.profile["packet"]["stateFile"]),
                "sealed": str(self.sealed),
            },
            "authority": "none",
            "claimBoundary": "Synthetic private path map for conformance only.",
        }
        path_map = sign(path_map_body, pre["pathMapIdKey"], pre["pathMapIdPrefix"])
        write_json(self.workstation / ws_law["pathMapFile"], path_map)

        config_body = {
            "schema": pre["configSchema"],
            "profileId": pre["conductorProfileId"],
            "campaignId": campaign_id,
            "campaignLabel": self.campaign_label,
            "conductorSourceSetId": source_set_id,
            "pathMapId": path_map[pre["pathMapIdKey"]],
            "authority": "none",
            "claimBoundary": "Synthetic private campaign configuration for conformance only.",
        }
        config = sign(config_body, pre["configIdKey"], pre["configIdPrefix"])
        write_json(self.workstation / ws_law["configFile"], config)

        marker_body = {
            "schema": pre["markerSchema"],
            "profileId": pre["conductorProfileId"],
            "campaignId": campaign_id,
            "campaignLabel": self.campaign_label,
            "createdAtUnixNs": 1756000000000000000,
            "configId": config[pre["configIdKey"]],
            "pathMapId": path_map[pre["pathMapIdKey"]],
            "sourceSetId": source_set_id,
            "authority": "none",
            "claimBoundary": "Synthetic conductor workstation marker for conformance only.",
        }
        write_json(self.workstation / ws_law["markerFile"], sign(marker_body, pre["markerIdKey"], pre["markerIdPrefix"]))

        ledger_body = {
            "schema": pre["ledgerSchema"],
            "profileId": pre["conductorProfileId"],
            "campaignId": campaign_id,
            "currentPhase": pre["refusedPhase"],
            "currentPhaseState": "REFUSED",
            "closedPhaseCount": 11,
            "heldPhaseCount": 0,
            "refusedPhaseCount": 1,
            "phases": [
                {"sequence": 1, "phase": "private_packet", "state": "CLOSED", "reasonCode": None},
                {
                    "sequence": 2,
                    "phase": pre["refusedPhase"],
                    "state": "REFUSED",
                    "reasonCode": pre["refusalCode"],
                },
            ],
            "authority": "none",
            "claimBoundary": "Synthetic predecessor ledger for conformance only.",
        }
        write_json(self.workstation / ws_law["ledgerFile"], sign(ledger_body, pre["ledgerIdKey"], pre["ledgerIdPrefix"]))

    def _build(self) -> None:
        source_set_id = self._build_checkout()
        self._build_sealed()
        self._build_packet()
        self._build_workstation(source_set_id)

    def rebind_chain(self) -> None:
        """Re-point marker, verification, manifest and detached copy at the current disposition.

        Used only by witnesses that must isolate a claim or denominator violation. Without
        it the identity cross-binding fires first and every claim witness would collapse
        into the same binding refusal, proving nothing about the claim law.
        """
        sealed_law = self.profile["sealedPackage"]
        disposition = load_json(self.sealed_path("publicDispositionFile"))
        self.disposition_id = disposition["dispositionId"]

        marker = load_json(self.sealed_path("markerFile"))
        marker["dispositionId"] = self.disposition_id
        marker["runId"] = disposition["runId"]
        marker.pop("markerId", None)
        write_json(self.sealed_path("markerFile"), sign(marker, "markerId", sealed_law["markerIdPrefix"]))

        verification = load_json(self.sealed_path("verificationFile"))
        verification["dispositionId"] = self.disposition_id
        verification["runId"] = disposition["runId"]
        verification.pop("verificationId", None)
        verification = sign(verification, "verificationId", sealed_law["verificationIdPrefix"])
        write_json(self.sealed_path("verificationFile"), verification)

        self.rebuild_manifest()
        write_json(self.sealed_path("detachedVerificationFile"), verification)

        state_path = self.packet_path("stateFile")
        state = load_json(state_path)
        state["sealedDispositionId"] = self.disposition_id
        state.pop("stateId", None)
        write_json(state_path, sign(state, "stateId", self.profile["packet"]["stateIdPrefix"]))

    # -- helpers -----------------------------------------------------------
    def run(self, **overrides):
        return law.verify_sealed_campaign_compatibility(
            workstation=overrides.get("workstation", self.workstation),
            conductor_checkout=overrides.get("conductor_checkout", self.checkout),
            profile_path=PROFILE,
            repair_source_root=REPOSITORY_ROOT,
            measured_verifier_bytes=overrides.get("measured_verifier_bytes"),
        )

    def sealed_path(self, key: str) -> Path:
        return self.sealed / self.profile["sealedPackage"][key]

    def packet_path(self, key: str) -> Path:
        return self.packet / self.profile["packet"][key]

    def workstation_path(self, key: str) -> Path:
        return self.workstation / self.profile["workstation"][key]

    def sealed_bytes_fence(self) -> dict[str, str]:
        return {
            entry.name: law.sha256_bytes(entry.read_bytes())
            for entry in sorted(self.sealed.iterdir())
        }


class CompatibilityWitnessCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="stc-mary-compat-witness-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.profile = load_json(PROFILE)
        self.fixture = Fixture(self.tmp / "case", self.profile)

    def assert_refuses(self, code: str, **overrides) -> None:
        with self.assertRaises(law.CompatibilityError) as caught:
            self.fixture.run(**overrides)
        self.assertEqual(caught.exception.code, code)


class PositiveTerminal(CompatibilityWitnessCase):
    def test_complete_synthetic_campaign_closes_compatible(self) -> None:
        receipt = self.fixture.run()
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["terminal"], "SEALED_CAMPAIGN_COMPATIBLE")
        self.assertEqual(receipt["predecessorRefusal"], "PUBLIC_DISPOSITION_BINDING_INVALID")
        self.assertEqual(receipt["stageDenominator"], 16)
        self.assertEqual(receipt["successfulStageCount"], 15)
        self.assertEqual(receipt["humanRequiredStageCount"], 1)
        self.assertEqual(receipt["refusedStageCount"], 0)
        self.assertTrue(receipt["unresolvedObligationRetained"])
        self.assertEqual(receipt["privateEvidenceBodies"], 37)
        self.assertEqual(receipt["publicEvidenceBodies"], 0)
        self.assertTrue(receipt["bodyFreePublicDisposition"])
        self.assertTrue(receipt["deterministicReceiptReplay"])
        self.assertTrue(receipt["privatePhysicalFlightCompleted"])
        self.assertFalse(receipt["packageMutated"])
        self.assertFalse(receipt["packetStagesReplayed"])
        self.assertFalse(receipt["predecessorLedgerRewritten"])
        self.assertFalse(receipt["predecessorConductorExecuted"])
        self.assertEqual(receipt["authority"], "none")
        self.assertFalse(receipt["bootstrapAuthenticated"])

    def test_predecessor_and_repair_sources_are_separately_identified(self) -> None:
        receipt = self.fixture.run()
        self.assertNotEqual(receipt["predecessorSourceSetId"], receipt["repairSourceSetId"])
        self.assertTrue(receipt["predecessorSourceSetId"].startswith("stcmaryflightconductorsourceset1_"))
        self.assertTrue(receipt["repairSourceSetId"].startswith("stcmarysealedcampaigncompatibilitysourceset1_"))

    def test_receipt_identity_reconstructs(self) -> None:
        receipt = self.fixture.run()
        body = {key: value for key, value in receipt.items() if key != law.RECEIPT_ID_KEY}
        self.assertEqual(receipt[law.RECEIPT_ID_KEY], law.content_id(law.RECEIPT_ID_PREFIX, body))

    def test_restart_witness_closes_without_resealing_or_mutation(self) -> None:
        """The exact package the predecessor refused closes here, unchanged."""
        before = self.fixture.sealed_bytes_fence()
        packet_state_before = self.fixture.packet_path("stateFile").read_bytes()
        ledger_before = self.fixture.workstation_path("ledgerFile").read_bytes()

        receipt = self.fixture.run()
        self.assertEqual(receipt["terminal"], "SEALED_CAMPAIGN_COMPATIBLE")

        self.assertEqual(self.fixture.sealed_bytes_fence(), before)
        self.assertEqual(self.fixture.packet_path("stateFile").read_bytes(), packet_state_before)
        self.assertEqual(self.fixture.workstation_path("ledgerFile").read_bytes(), ledger_before)

        ledger = load_json(self.fixture.workstation_path("ledgerFile"))
        sealed_row = next(row for row in ledger["phases"] if row["phase"] == "sealed_flight")
        self.assertEqual(sealed_row["state"], "REFUSED")
        self.assertEqual(sealed_row["reasonCode"], "PUBLIC_DISPOSITION_BINDING_INVALID")

    def test_receipt_carries_no_private_coordinate(self) -> None:
        receipt = self.fixture.run()
        serialized = json.dumps(receipt)
        self.assertNotIn(str(self.fixture.sealed), serialized)
        self.assertNotIn(str(self.fixture.packet), serialized)
        self.assertNotIn(str(self.fixture.workstation), serialized)
        law.assert_no_private_material(receipt, code="X", label="receipt")


class PredecessorWitnesses(CompatibilityWitnessCase):
    def test_predecessor_source_drift_refuses(self) -> None:
        member = self.fixture.checkout / "mating_surface/anchor_node/stc-mary-flight-conductor.ps1"
        member.write_text("# drifted\n", encoding="utf-8")
        self.assert_refuses("PREDECESSOR_SOURCE_SET_DRIFT")

    def test_absent_impossible_predicate_refuses(self) -> None:
        relative = self.profile["predecessor"]["impossiblePredicate"]["relativePath"]
        target = self.fixture.checkout / relative
        target.write_text("# predicate removed\n", encoding="utf-8")
        # Re-pin the workstation to the drifted source set so the predicate check is what fails.
        self.fixture._build_workstation(
            law.measure_source_set(
                self.fixture.checkout,
                self.profile["predecessor"]["sourceMembers"],
                schema=self.profile["predecessor"]["sourceSetSchema"],
                profile_id=self.profile["predecessor"]["conductorProfileId"],
                claim_boundary=self.profile["predecessor"]["sourceSetClaimBoundary"],
                id_key="sourceSetId",
                id_prefix=self.profile["predecessor"]["sourceSetIdPrefix"],
                code="X",
                label="drifted",
            )["sourceSetId"]
        )
        self.assert_refuses("PREDECESSOR_PREDICATE_ABSENT")

    def test_discharged_predecessor_refusal_refuses(self) -> None:
        path = self.fixture.workstation_path("ledgerFile")
        ledger = load_json(path)
        for row in ledger["phases"]:
            if row["phase"] == "sealed_flight":
                row["state"] = "CLOSED"
                row["reasonCode"] = None
        write_json(path, ledger)
        resign(path, "ledgerId", "stcmaryflightconductorledger1")
        self.assert_refuses("PREDECESSOR_REFUSAL_ABSENT")

    def test_rewritten_refusal_reason_refuses(self) -> None:
        path = self.fixture.workstation_path("ledgerFile")
        ledger = load_json(path)
        for row in ledger["phases"]:
            if row["phase"] == "sealed_flight":
                row["reasonCode"] = "SOMETHING_ELSE"
        write_json(path, ledger)
        resign(path, "ledgerId", "stcmaryflightconductorledger1")
        self.assert_refuses("PREDECESSOR_REFUSAL_MISMATCH")

    def test_ledger_from_another_campaign_refuses(self) -> None:
        path = self.fixture.workstation_path("ledgerFile")
        ledger = load_json(path)
        ledger["campaignId"] = law.content_id("stcmaryflightconductorcampaign1", {"campaignLabel": OTHER_CAMPAIGN_LABEL})
        write_json(path, ledger)
        resign(path, "ledgerId", "stcmaryflightconductorledger1")
        self.assert_refuses("PREDECESSOR_LEDGER_INVALID")


class PacketWitnesses(CompatibilityWitnessCase):
    def test_packet_state_from_another_campaign_refuses(self) -> None:
        path = self.fixture.packet_path("stateFile")
        state = load_json(path)
        state["campaignLabel"] = OTHER_CAMPAIGN_LABEL
        write_json(path, state)
        resign(path, "stateId", "stcmaryprivateflightpacketstate1")
        self.assert_refuses("PACKET_CAMPAIGN_BINDING_INVALID")

    def test_unsealed_packet_state_refuses(self) -> None:
        path = self.fixture.packet_path("stateFile")
        state = load_json(path)
        state["sealed"] = False
        write_json(path, state)
        resign(path, "stateId", "stcmaryprivateflightpacketstate1")
        self.assert_refuses("PACKET_NOT_SEALED")

    def test_sealed_disposition_id_mismatch_refuses(self) -> None:
        path = self.fixture.packet_path("stateFile")
        state = load_json(path)
        state["sealedDispositionId"] = law.content_id("stcmarypublicphysicalflightdisposition1", {"other": True})
        write_json(path, state)
        resign(path, "stateId", "stcmaryprivateflightpacketstate1")
        self.assert_refuses("PACKET_SEALED_DISPOSITION_MISMATCH")

    def test_incomplete_stage_denominator_refuses(self) -> None:
        path = self.fixture.packet_path("stateFile")
        state = load_json(path)
        state["completedStageCount"] = 15
        state["nextStage"] = "SEAL_PRIVATE_EVIDENCE"
        write_json(path, state)
        resign(path, "stateId", "stcmaryprivateflightpacketstate1")
        self.assert_refuses("PACKET_STAGE_DENOMINATOR_INVALID")

    def test_packet_marker_substitution_refuses(self) -> None:
        path = self.fixture.packet_path("markerFile")
        marker = load_json(path)
        marker["campaignLabel"] = OTHER_CAMPAIGN_LABEL
        write_json(path, marker)
        resign(path, "markerId", "stcmaryprivateflightpacketroot1")
        self.assert_refuses("PACKET_CAMPAIGN_BINDING_INVALID")


class SealedPackageWitnesses(CompatibilityWitnessCase):
    def test_added_campaign_label_field_refuses(self) -> None:
        path = self.fixture.sealed_path("publicDispositionFile")
        disposition = load_json(path)
        disposition["campaignLabel"] = SYNTHETIC_CAMPAIGN_LABEL
        write_json(path, disposition)
        resign(path, "dispositionId", "stcmarypublicphysicalflightdisposition1")
        self.fixture.rebuild_manifest()
        self.assert_refuses("PUBLIC_DISPOSITION_SCHEMA_INVALID")

    def test_disposition_run_id_mismatch_refuses(self) -> None:
        path = self.fixture.sealed_path("publicDispositionFile")
        disposition = load_json(path)
        disposition["runId"] = law.content_id("stcmaryprivateflightrun1", {"other": True})
        write_json(path, disposition)
        resign(path, "dispositionId", "stcmarypublicphysicalflightdisposition1")
        self.fixture.rebuild_manifest()
        self.assert_refuses("PUBLIC_DISPOSITION_BINDING_INVALID")

    def test_disposition_identity_mismatch_refuses(self) -> None:
        path = self.fixture.sealed_path("publicDispositionFile")
        disposition = load_json(path)
        disposition["profileId"] = "stc-mary/physical-flight/9.9"
        write_json(path, disposition)
        resign(path, "dispositionId", "stcmarypublicphysicalflightdisposition1")
        self.fixture.rebuild_manifest()
        self.assert_refuses("PUBLIC_DISPOSITION_BINDING_INVALID")

    def test_unsigned_disposition_edit_refuses(self) -> None:
        path = self.fixture.sealed_path("publicDispositionFile")
        disposition = load_json(path)
        disposition["profileId"] = "stc-mary/physical-flight/9.9"
        write_json(path, disposition)
        self.fixture.rebuild_manifest()
        self.assert_refuses("PUBLIC_DISPOSITION_ID_INVALID")

    def test_detached_verification_drift_refuses(self) -> None:
        path = self.fixture.sealed_path("detachedVerificationFile")
        detached = load_json(path)
        detached["status"] = "REFUSED"
        write_json(path, detached)
        self.assert_refuses("DETACHED_VERIFICATION_DRIFT")

    def test_sealed_marker_binding_mismatch_refuses(self) -> None:
        path = self.fixture.sealed_path("markerFile")
        marker = load_json(path)
        marker["runId"] = law.content_id("stcmaryprivateflightrun1", {"other": True})
        write_json(path, marker)
        resign(path, "markerId", "stcmaryprivateflightsealedroot1")
        self.fixture.rebuild_manifest()
        self.assert_refuses("SEALED_RUN_BINDING_INVALID")

    def test_sealed_manifest_binding_mismatch_refuses(self) -> None:
        path = self.fixture.sealed_path("manifestFile")
        manifest = load_json(path)
        manifest["dispositionId"] = law.content_id("stcmarypublicphysicalflightdisposition1", {"other": True})
        write_json(path, manifest)
        resign(path, "manifestId", "stcmaryprivateflightsealedmanifest1")
        self.assert_refuses("SEALED_MANIFEST_BINDING_INVALID")

    def test_member_byte_drift_refuses(self) -> None:
        (self.fixture.sealed / "review.html").write_text("<!doctype html><title>drift</title>\n", encoding="utf-8")
        self.assert_refuses("SEALED_PACKAGE_FILE_MISMATCH")

    def test_extra_sealed_root_file_refuses(self) -> None:
        (self.fixture.sealed / "extra.json").write_text("{}\n", encoding="utf-8")
        self.assert_refuses("SEALED_ROOT_DENOMINATOR_INVALID")

    def test_missing_sealed_root_file_refuses(self) -> None:
        self.fixture.sealed_path("detachedVerificationFile").unlink()
        self.assert_refuses("SEALED_ROOT_DENOMINATOR_INVALID")


class ClaimBoundaryWitnesses(CompatibilityWitnessCase):
    def test_qualification_widening_refuses(self) -> None:
        path = self.fixture.sealed_path("publicDispositionFile")
        disposition = load_json(path)
        disposition["physicalEstateQualified"] = True
        write_json(path, disposition)
        resign(path, "dispositionId", "stcmarypublicphysicalflightdisposition1")
        self.fixture.rebind_chain()
        self.assert_refuses("QUALIFICATION_WIDENED")

    def test_authority_widening_refuses(self) -> None:
        path = self.fixture.sealed_path("publicDispositionFile")
        disposition = load_json(path)
        disposition["authority"] = "operator"
        write_json(path, disposition)
        resign(path, "dispositionId", "stcmarypublicphysicalflightdisposition1")
        self.fixture.rebind_chain()
        self.assert_refuses("AUTHORITY_WIDENED")

    def test_private_material_in_disposition_refuses(self) -> None:
        path = self.fixture.sealed_path("publicDispositionFile")
        disposition = load_json(path)
        disposition["claimBoundary"] = "Synthetic disposition sealed from D:\\private\\campaign root."
        write_json(path, disposition)
        resign(path, "dispositionId", "stcmarypublicphysicalflightdisposition1")
        self.fixture.rebind_chain()
        self.assert_refuses("PUBLIC_DISPOSITION_PRIVATE_MATERIAL")

    def test_discharged_human_obligation_refuses(self) -> None:
        path = self.fixture.sealed_path("publicDispositionFile")
        disposition = load_json(path)
        disposition["successfulStageCount"] = 16
        disposition["humanRequiredStageCount"] = 0
        write_json(path, disposition)
        resign(path, "dispositionId", "stcmarypublicphysicalflightdisposition1")
        self.fixture.rebind_chain()
        self.assert_refuses("PUBLIC_DISPOSITION_DENOMINATOR_INVALID")

    def test_private_evidence_denominator_drift_refuses(self) -> None:
        path = self.fixture.sealed_path("publicDispositionFile")
        disposition = load_json(path)
        disposition["privatePhysicalEvidenceBodyCount"] = 36
        write_json(path, disposition)
        resign(path, "dispositionId", "stcmarypublicphysicalflightdisposition1")
        self.fixture.rebind_chain()
        self.assert_refuses("PRIVATE_EVIDENCE_DENOMINATOR_INVALID")

    def test_public_evidence_widening_refuses(self) -> None:
        path = self.fixture.sealed_path("publicDispositionFile")
        disposition = load_json(path)
        disposition["publicEvidenceBodyCount"] = 1
        write_json(path, disposition)
        resign(path, "dispositionId", "stcmarypublicphysicalflightdisposition1")
        self.fixture.rebind_chain()
        self.assert_refuses("PUBLIC_EVIDENCE_WIDENED")


class WorkstationWitnesses(CompatibilityWitnessCase):
    def test_config_source_set_disagreement_refuses(self) -> None:
        path = self.fixture.workstation_path("configFile")
        config = load_json(path)
        config["conductorSourceSetId"] = law.content_id("stcmaryflightconductorsourceset1", {"other": True})
        write_json(path, config)
        resign(path, "configId", "stcmaryflightconductorconfig1")
        self.assert_refuses("CAMPAIGN_CONFIG_INVALID")

    def test_substituted_config_refuses(self) -> None:
        path = self.fixture.workstation_path("configFile")
        config = load_json(path)
        config["campaignLabel"] = OTHER_CAMPAIGN_LABEL
        write_json(path, config)
        resign(path, "configId", "stcmaryflightconductorconfig1")
        self.assert_refuses("CAMPAIGN_CONFIG_INVALID")

    def test_unsigned_marker_edit_refuses(self) -> None:
        path = self.fixture.workstation_path("markerFile")
        marker = load_json(path)
        marker["campaignLabel"] = OTHER_CAMPAIGN_LABEL
        write_json(path, marker)
        self.assert_refuses("WORKSTATION_MARKER_ID_INVALID")

    def test_cross_campaign_path_map_refuses(self) -> None:
        path = self.fixture.workstation_path("pathMapFile")
        path_map = load_json(path)
        path_map["campaignId"] = law.content_id("stcmaryflightconductorcampaign1", {"campaignLabel": OTHER_CAMPAIGN_LABEL})
        write_json(path, path_map)
        resign(path, "pathMapId", "stcmaryflightconductorpathmap1")
        self.assert_refuses("PATH_MAP_INVALID")


class BootstrapWitnesses(CompatibilityWitnessCase):
    def bootstrap_command(self, out: Path | None = None) -> list[str]:
        command = [
            sys.executable,
            str(ANCHOR / "verify_stc_mary_sealed_campaign_compatibility_bootstrap.py"),
            "--workstation",
            str(self.fixture.workstation),
            "--conductor-checkout",
            str(self.fixture.checkout),
            "--profile",
            str(PROFILE),
            "--repair-source-root",
            str(REPOSITORY_ROOT),
        ]
        if out is not None:
            command.extend(["--out", str(out)])
        return command

    def test_direct_call_is_not_bootstrap_authenticated(self) -> None:
        receipt = self.fixture.run()
        self.assertFalse(receipt["bootstrapAuthenticated"])
        self.assertIsNone(receipt["measuredVerifierSha256"])
        self.assertNotIn("measured-verifier-member-binding", receipt["checks"])

    def test_bootstrap_authenticates_measured_bytes(self) -> None:
        completed = subprocess.run(self.bootstrap_command(), capture_output=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stdout.decode("utf-8", "replace"))
        receipt = json.loads(completed.stdout.decode("utf-8"))
        self.assertEqual(receipt["status"], "PASS")
        self.assertTrue(receipt["bootstrapAuthenticated"])
        self.assertEqual(
            receipt["measuredVerifierSha256"],
            law.sha256_bytes((ANCHOR / "verify_stc_mary_sealed_campaign_compatibility.py").read_bytes()),
        )
        self.assertIn("measured-verifier-member-binding", receipt["checks"])
        self.assertEqual(receipt["bootstrapVerifier"], "external-measured-bytes-isolated-before-execution")

    def test_bootstrap_refuses_when_verifier_is_absent(self) -> None:
        staged = self.tmp / "staged-anchor"
        staged.mkdir()
        shutil.copy2(
            ANCHOR / "verify_stc_mary_sealed_campaign_compatibility_bootstrap.py",
            staged / "verify_stc_mary_sealed_campaign_compatibility_bootstrap.py",
        )
        # Executed through the staged copy, whose sibling verifier is absent.
        completed = subprocess.run(
            [
                sys.executable,
                str(staged / "verify_stc_mary_sealed_campaign_compatibility_bootstrap.py"),
                "--workstation",
                str(self.fixture.workstation),
                "--conductor-checkout",
                str(self.fixture.checkout),
                "--profile",
                str(PROFILE),
                "--repair-source-root",
                str(REPOSITORY_ROOT),
            ],
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 1)
        verdict = json.loads(completed.stdout.decode("utf-8"))
        self.assertEqual(verdict["status"], "REFUSED")
        self.assertEqual(verdict["code"], "VERIFIER_MISSING")
        self.assertFalse(verdict["bootstrapAuthenticated"])
        self.assertFalse(verdict["verifierExecuted"])

    def test_bootstrap_refuses_tampered_verifier(self) -> None:
        staged = self.tmp / "tampered-anchor"
        staged.mkdir()
        shutil.copy2(
            ANCHOR / "verify_stc_mary_sealed_campaign_compatibility_bootstrap.py",
            staged / "verify_stc_mary_sealed_campaign_compatibility_bootstrap.py",
        )
        tampered = (ANCHOR / "verify_stc_mary_sealed_campaign_compatibility.py").read_text(encoding="utf-8")
        tampered += "\n# tampered copy that is not the stored repair source member\n"
        (staged / "verify_stc_mary_sealed_campaign_compatibility.py").write_text(tampered, encoding="utf-8")
        completed = subprocess.run(
            [
                sys.executable,
                str(staged / "verify_stc_mary_sealed_campaign_compatibility_bootstrap.py"),
                "--workstation",
                str(self.fixture.workstation),
                "--conductor-checkout",
                str(self.fixture.checkout),
                "--profile",
                str(PROFILE),
                "--repair-source-root",
                str(REPOSITORY_ROOT),
            ],
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 1)
        verdict = json.loads(completed.stdout.decode("utf-8"))
        self.assertEqual(verdict["status"], "REFUSED")
        self.assertEqual(verdict["code"], "MEASURED_VERIFIER_MEMBER_BINDING_INVALID")
        self.assertFalse(verdict["bootstrapAuthenticated"])


class SourcePinningWitnesses(CompatibilityWitnessCase):
    def test_repair_source_may_not_claim_a_predecessor_member(self) -> None:
        predecessor_members = set(self.profile["predecessor"]["sourceMembers"])
        repair_members = set(self.profile["repairSourceMembers"])
        self.assertTrue(predecessor_members.isdisjoint(repair_members))

    def test_repair_source_does_not_touch_conductor_sources(self) -> None:
        for member in self.profile["repairSourceMembers"]:
            self.assertNotIn("flight-conductor", member)
            self.assertNotIn("flight_conductor", member)

    def test_frontend_and_verifier_agree(self) -> None:
        out = self.tmp / "frontend-receipt.json"
        code = frontend.main(
            [
                "verify",
                "--workstation",
                str(self.fixture.workstation),
                "--conductor-checkout",
                str(self.fixture.checkout),
                "--profile",
                str(PROFILE),
                "--repair-source-root",
                str(REPOSITORY_ROOT),
                "--out",
                str(out),
            ]
        )
        self.assertEqual(code, 0)
        self.assertEqual(load_json(out)[law.RECEIPT_ID_KEY], self.fixture.run()[law.RECEIPT_ID_KEY])

    def test_bootstrap_never_imports_the_verifier(self) -> None:
        source = (ANCHOR / "verify_stc_mary_sealed_campaign_compatibility_bootstrap.py").read_text(encoding="utf-8")
        self.assertNotIn("import verify_stc_mary_sealed_campaign_compatibility", source)
        self.assertEqual(bootstrap.VERIFIER_FILENAME, "verify_stc_mary_sealed_campaign_compatibility.py")
        # The measured bytes are piped in and executed from a synthetic __file__, never
        # imported and never executed in place, in an isolated interpreter.
        self.assertIn('"-I"', source)
        self.assertIn('"-S"', source)
        self.assertIn("sys.stdin.buffer.read()", bootstrap.ISOLATED_VERIFIER_LAUNCHER)
        self.assertIn("<measured-", bootstrap.ISOLATED_VERIFIER_LAUNCHER)

    def test_substituted_profile_refuses(self) -> None:
        forged = self.tmp / "forged-profile.json"
        profile = load_json(PROFILE)
        profile["campaignDenominator"]["privateEvidenceBodyCount"] = 1
        write_json(forged, profile)
        with self.assertRaises(law.CompatibilityError) as caught:
            law.load_profile(forged)
        self.assertEqual(caught.exception.code, "PROFILE_CANONICAL_DIGEST_INVALID")

    def test_admitted_profile_digest_is_pinned(self) -> None:
        self.assertEqual(
            law.sha256_bytes(law.canonical_json_bytes(load_json(PROFILE))),
            law.PROFILE_CANONICAL_SHA256,
        )

    def test_profile_digest_is_stable(self) -> None:
        profile = law.load_profile(PROFILE)
        first = law.sha256_bytes(law.canonical_json_bytes(profile))
        second = law.sha256_bytes(law.canonical_json_bytes(law.load_profile(PROFILE)))
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
