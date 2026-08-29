from __future__ import annotations

import copy
import importlib.util
import json
import io
import os
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import verify_axm_head_physical_long_haul_join as mod
import axm_head_physical_long_haul_join as bootstrap

PROFILE = ROOT / "axm-head-physical-long-haul-join-profile-01.json"
FIXTURES = ROOT / "fixtures" / "axm-head-physical-long-haul-join-cases-01.json"
VERIFIER = ROOT / "verify_axm_head_physical_long_haul_join.py"
TOOL = ROOT / "axm_head_physical_long_haul_join.py"

TEST_PRIVATE_PROVENANCE_KEY = {'algorithm': 'rsa-pkcs1v15-sha256',
 'keyId': 'axmheadprivateevidencetrustroot1_ec9e1acaccc1eff237313d49279afd800b44f4e7bdac017fe0af682486d4ef44',
 'modulusHex': 'ab9273a16704ef7f7599443400988752cfb0d14bc5df3e7b05a69f9fb4c42400a0228f77814937dd605b67ab56f9e72cbc008443662aa22dd8c043b743e6cc2f1a4c170a68bf30dcbc453359a9f4b3f84369e7e44dd90698c8bc54d91aecb1f5a46accf1ffb6d9d52d6374432d99dc87adb314dd453060633b38f0fdf2f4556fd3e4d31f6e5822cc587773bc6f96dc68bff64084ded195993e6886cd77517a24fefe5031a4e03bb1129bfc31f4b8b7712c2c51fea78587486c60cc76cc10780423364b781cbd14936828eec12ca8a8c16d4d4ca52fc53ecad6112944fd3a757179c1c686c7ad4db01c1d06386e2935df1f84974147107a4686e88072b42ab727',
 'privateExponentHex': '2885eba7a88462e8d0e6c5541efbe7a2688993b578e3d4870bfba1e1ffb8ffe3e1eea7c20b183708a3749354c5b33aa5b735cc077b3f00952187afb6be63e9c00a4f047621ed5e661455a7de3aa52048b7eb70a8dcb630b7af59c4148f266e95dd22988b63e1552be38f84eb44fefd36529164912a815592ba6f25846578ce20bb5cd008c98353f55f12ca3d3456dc757c7032f7f29ecd05cb839b32406e58953700930049cf1790f25bbc80daf696c452e97d160dd1e7929e613b4965225c82c7235dfc94ab0304e70e914dd4ff3f65f655fe02c9aef56628bc669344881c601ad5ea9bc621f0ae5ecba466e8a4a9087756fbc66bd3db7aaab7e559acc713d1',
 'publicExponent': 65537,
 'schema': 'axm-head/private-evidence-provenance-signing-key@1'}
TEST_PRIVATE_PROVENANCE_TRUST_ROOT = {'keyId': 'axmheadprivateevidencetrustroot1_ec9e1acaccc1eff237313d49279afd800b44f4e7bdac017fe0af682486d4ef44',
 'algorithm': 'rsa-pkcs1v15-sha256',
 'modulusHex': 'ab9273a16704ef7f7599443400988752cfb0d14bc5df3e7b05a69f9fb4c42400a0228f77814937dd605b67ab56f9e72cbc008443662aa22dd8c043b743e6cc2f1a4c170a68bf30dcbc453359a9f4b3f84369e7e44dd90698c8bc54d91aecb1f5a46accf1ffb6d9d52d6374432d99dc87adb314dd453060633b38f0fdf2f4556fd3e4d31f6e5822cc587773bc6f96dc68bff64084ded195993e6886cd77517a24fefe5031a4e03bb1129bfc31f4b8b7712c2c51fea78587486c60cc76cc10780423364b781cbd14936828eec12ca8a8c16d4d4ca52fc53ecad6112944fd3a757179c1c686c7ad4db01c1d06386e2935df1f84974147107a4686e88072b42ab727',
 'publicExponent': 65537}


class AxmHeadPhysicalLongHaulJoinTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="axm-head-postflight-join-")
        self.root = Path(self.temp.name)
        self.profile = mod.validate_profile(PROFILE)
        self.catalog = mod.validate_catalog(FIXTURES, self.profile)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def case(self, case_id: str) -> dict:
        return copy.deepcopy(mod.find_case(self.catalog, case_id)["input"])

    def complete(self) -> dict:
        return self.case("hold-complete-synthetic-private-shape")

    @staticmethod
    def refresh_top(value: dict, key: str, id_key: str, prefix: str) -> None:
        obj = value[key]
        obj[id_key] = mod.content_id(prefix, mod.body_without(obj, id_key))

    @staticmethod
    def refresh_source(value: dict) -> None:
        source = value["sourceBinding"]
        if source["preflightDisposition"] is not None:
            pf = source["preflightDisposition"]
            pf["receiptId"] = mod.content_id("axmheadpreflightdisposition1", mod.body_without(pf, "receiptId"))
        source["sourceBindingId"] = mod.content_id("axmheadphysicalflightsourcebinding2", mod.body_without(source, "sourceBindingId"))

    def refresh_all_top(self, value: dict) -> None:
        self.refresh_top(value, "routeAttestation", "routeAttestationId", "axmheadphysicalrouteattestation2")
        self.refresh_top(value, "continuityAttestation", "continuityAttestationId", "axmheadcontinuityattestation2")
        self.refresh_top(value, "twoCellAttestation", "twoCellAttestationId", "axmheadtwocellattestation2")
        self.refresh_top(value, "successorAttestation", "successorAttestationId", "axmheadsuccessorattestation2")
        self.refresh_top(value, "privateFlightDispositionBinding", "dispositionBindingId", "axmheadprivateflightdispositionbinding2")

    @staticmethod
    def rechain_stage_receipts(disposition: dict) -> None:
        previous = None
        for row in disposition["packet"]["stageReceipts"]:
            row["previousReceiptId"] = previous
            row["receiptId"] = mod.content_id("stcmaryprivateflightstage1", mod.body_without(row, "receiptId"))
            previous = row["receiptId"]

    @staticmethod
    def refresh_source_disposition(disposition_binding: dict) -> None:
        source = disposition_binding["sourceDisposition"]
        source["digest"] = "sha256:" + mod.sha256_bytes(mod.canonical_json_bytes(mod.body_without(source, "digest")))
        disposition_binding["sealedPackage"]["publicDispositionDigest"] = "sha256:" + mod.sha256_bytes(mod.canonical_json_bytes(source))

    def retier_private(self, value: dict, tier: str) -> None:
        for key in (
            "routeAttestation",
            "continuityAttestation",
            "twoCellAttestation",
            "successorAttestation",
            "privateFlightDispositionBinding",
        ):
            value[key]["evidenceTier"] = tier
        self.refresh_all_top(value)

    def sign_private_with_test_root(self, value: dict) -> None:
        payload = mod.private_evidence_provenance_payload(value)
        payload_bytes = mod.canonical_json_bytes(payload)
        modulus = int(TEST_PRIVATE_PROVENANCE_KEY["modulusHex"], 16)
        private_exponent = int(TEST_PRIVATE_PROVENANCE_KEY["privateExponentHex"], 16)
        encoded = mod.rsa_pkcs1_v1_5_encoded_message(payload_bytes, modulus)
        signature = pow(int.from_bytes(encoded, "big"), private_exponent, modulus).to_bytes(len(encoded), "big")
        body = {
            "schema": mod.PRIVATE_EVIDENCE_PROVENANCE_SCHEMA,
            "profileId": mod.PROFILE_ID,
            "keyId": TEST_PRIVATE_PROVENANCE_KEY["keyId"],
            "algorithm": TEST_PRIVATE_PROVENANCE_KEY["algorithm"],
            "payloadSha256": mod.sha256_bytes(payload_bytes),
            "signatureBase64Url": mod.base64url_encode(signature),
        }
        value["privateEvidenceProvenance"] = {
            "provenanceId": mod.content_id("axmheadprivateevidenceprovenance2", body),
            **body,
        }

    def evaluate_with_test_trust_root(self, value: dict) -> dict:
        profile = copy.deepcopy(self.profile)
        profile["privateEvidenceProvenanceTrustRoot"] = TEST_PRIVATE_PROVENANCE_TRUST_ROOT
        digest = mod.sha256_bytes(mod.canonical_json_bytes(profile))
        with mock.patch.object(mod, "PRIVATE_EVIDENCE_PROVENANCE_TRUST_ROOT", TEST_PRIVATE_PROVENANCE_TRUST_ROOT), mock.patch.object(
            mod, "PROFILE_CANONICAL_SHA256", digest
        ):
            return mod.evaluate_input(mod.validate_profile_value(profile), mod.validate_input_value(value))

    def replace_authorization(self, value: dict, mutate) -> None:
        disposition = value["privateFlightDispositionBinding"]
        authorization = disposition["authorizationReceipt"]
        mutate(authorization)
        authorization["receiptId"] = mod.content_id("stcmarynamedhumanauthorization1", mod.body_without(authorization, "receiptId"))
        auth_id = authorization["receiptId"]
        for key in ("routeAttestation", "continuityAttestation", "twoCellAttestation", "successorAttestation"):
            value[key]["authorizationReceiptId"] = auth_id
        disposition["authorizationReceiptId"] = auth_id
        disposition["cartridge"]["humanAuthorityReceiptId"] = auth_id
        for row in disposition["packet"]["stageReceipts"]:
            row["authorizationReceiptId"] = auth_id
        self.rechain_stage_receipts(disposition)
        successor = value["successorAttestation"]
        successor["humanAuthorityReceiptId"] = auth_id
        successor["answers"] = mod.expected_successor_answers(
            cartridge_id=disposition["cartridge"]["cartridgeId"],
            mission_state_digest=disposition["cartridge"]["missionStateDigest"],
            authorization_receipt_id=auth_id,
            evidence_root_sha256=disposition["sealedPackage"]["evidenceRootSha256"],
            unresolved_obligation_count=disposition["cartridge"]["unresolvedObligationCount"],
            next_safe_action=disposition["cartridge"]["nextSafeAction"],
        )
        self.refresh_all_top(value)

    def evaluate(self, value: dict) -> dict:
        return mod.evaluate_input(self.profile, mod.validate_input_value(value))

    def run_bootstrap(self, value: dict, *, cwd: Path | None = None, out: Path | None = None) -> tuple[subprocess.CompletedProcess[bytes], dict]:
        input_path = self.root / f"input-{len(list(self.root.glob('input-*.json')))}.json"
        input_path.write_bytes(mod.pretty_json_bytes(value))
        command = [sys.executable, str(TOOL), "verify", str(input_path), "--profile", str(PROFILE)]
        if out is not None:
            command.extend(["--out", str(out)])
        result = subprocess.run(command, cwd=cwd or self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        return result, json.loads(result.stdout.decode("utf-8"))

    def test_profile_closes_exact_ten_object_denominator(self) -> None:
        self.assertEqual(self.profile["objectSchemas"], list(mod.OBJECT_SCHEMAS))
        self.assertEqual(len(self.profile["objectSchemas"]), 10)
        self.assertEqual(
            self.profile["privateEvidenceProvenanceTrustRoot"],
            mod.PRIVATE_EVIDENCE_PROVENANCE_TRUST_ROOT,
        )

    def test_profile_closes_exact_three_join_terminals(self) -> None:
        self.assertEqual(self.profile["terminalStates"], ["PREPARED_NOT_ARMED", "PRIVATE_SELF_ATTESTED", "HOLD"])

    def test_profile_binds_current_preflight_admission(self) -> None:
        preflight = self.profile["sourceBindings"]["admittedPreflightReviewCard"]
        self.assertEqual(preflight["commit"], "ec61bc3488cb5ae06ed9db2862a9f6910d310a79")
        self.assertEqual(preflight["tree"], "d2daba1d32a8de744b8b90f6cd42f7c4bff4fa67")
        self.assertEqual(preflight["profileCanonicalSha256"], "c0ef16ec7d7fbea70d59618d2a7c59cec42178c61cfeb564c839969e40ce2f56")
        self.assertEqual(preflight["standaloneVerifierSha256"], "c483507c0246fdcc502e21f60937f0ff81df020871120ab56abd619131ef49d2")

    def test_profile_binds_supplier_conductor_floor_and_issue_37(self) -> None:
        sources = self.profile["sourceBindings"]
        self.assertEqual(sources["admittedAxmHeadSupplier"]["commit"], "b452bb32e26249deab90db124f157bc62ad0850d")
        self.assertEqual(sources["admittedConductor"]["commit"], "772ce582e1b19b7a2060c50be8ebf40c1f8723b2")
        self.assertEqual(sources["physicalFlightFloor"]["commit"], "d31e59f5fd30e57b1917c00832b189ee2ea3e12f")
        self.assertEqual(sources["physicalFlightIssue"]["issueNumber"], 37)

    def test_profile_canonical_digest_is_frozen(self) -> None:
        self.assertEqual(mod.sha256_bytes(mod.canonical_json_bytes(self.profile)), mod.PROFILE_CANONICAL_SHA256)

    def test_profile_claim_promotion_is_refused(self) -> None:
        altered = copy.deepcopy(self.profile)
        altered["authority"] = "system"
        with self.assertRaises(mod.JoinError) as context:
            mod.validate_profile_value(altered)
        self.assertEqual(context.exception.code, "CLAIM_BOUNDARY_INVALID")

    def test_profile_preflight_coordinate_mutation_is_refused(self) -> None:
        altered = copy.deepcopy(self.profile)
        altered["sourceBindings"]["admittedPreflightReviewCard"]["commit"] = "0" * 40
        with self.assertRaises(mod.JoinError) as context:
            mod.validate_profile_value(altered)
        self.assertEqual(context.exception.code, "PROFILE_SOURCE_BINDINGS_INVALID")

    def test_profile_each_public_source_coordinate_mutation_is_refused(self) -> None:
        coordinate_keys = {
            "admittedAxmHeadSupplier": ("commit", "tree"),
            "admittedConductor": ("commit", "tree"),
            "physicalFlightFloor": ("commit", "tree"),
            "admittedPreflightReviewCard": ("commit", "tree"),
        }
        for source_name, keys in coordinate_keys.items():
            for key in keys:
                with self.subTest(source=source_name, key=key):
                    altered = copy.deepcopy(self.profile)
                    altered["sourceBindings"][source_name][key] = "0" * 40
                    with self.assertRaises(mod.JoinError) as context:
                        mod.validate_profile_value(altered)
                    self.assertEqual(context.exception.code, "PROFILE_SOURCE_BINDINGS_INVALID")

    def test_each_input_public_source_coordinate_mutation_is_refused(self) -> None:
        coordinate_keys = {
            "admittedAxmHeadSupplier": ("commit", "tree"),
            "admittedConductor": ("commit", "tree"),
            "physicalFlightFloor": ("commit", "tree"),
            "admittedPreflightReviewCard": ("commit", "tree"),
        }
        for source_name, keys in coordinate_keys.items():
            for key in keys:
                with self.subTest(source=source_name, key=key):
                    value = self.case("prepared-exact-public-sources-no-private-flight")
                    value["sourceBinding"]["publicSources"][source_name][key] = "0" * 40
                    self.refresh_source(value)
                    with self.assertRaises(mod.JoinError) as context:
                        mod.validate_input_value(value)
                    self.assertEqual(context.exception.code, "SOURCE_BINDING_COORDINATES_INVALID")

    def test_fixture_catalog_is_closed_and_synthetic_only(self) -> None:
        self.assertEqual([row["caseId"] for row in self.catalog["cases"]], list(mod.CASE_IDS))
        for row in self.catalog["cases"]:
            self.assertNotEqual(row["expectedTerminal"], "PRIVATE_SELF_ATTESTED")
            self.assertIsNone(row["input"]["privateEvidenceProvenance"])

    def test_fixture_catalog_canonical_digest_is_frozen(self) -> None:
        self.assertEqual(mod.sha256_bytes(mod.canonical_json_bytes(self.catalog)), mod.FIXTURE_CATALOG_CANONICAL_SHA256)

    def test_fixture_catalog_expansion_is_refused(self) -> None:
        altered = copy.deepcopy(self.catalog)
        altered["cases"].append(copy.deepcopy(altered["cases"][0]))
        with self.assertRaises(mod.JoinError) as context:
            mod.validate_catalog_value(altered, self.profile)
        self.assertEqual(context.exception.code, "FIXTURE_CASE_DENOMINATOR_INVALID")

    def test_prepared_static_sources_terminate_prepared_not_armed(self) -> None:
        result = self.evaluate(self.case("prepared-exact-public-sources-no-private-flight"))
        self.assertEqual(result["join"]["terminal"], "PREPARED_NOT_ARMED")
        self.assertFalse(result["publicStatus"]["privatePhysicalFlightCompleted"])

    def test_complete_synthetic_shape_is_held(self) -> None:
        result = self.evaluate(self.complete())
        self.assertEqual(result["join"]["terminal"], "HOLD")
        self.assertEqual(result["join"]["reasonCodes"], ["SYNTHETIC_EVIDENCE_CANNOT_ATTEST"])
        self.assertTrue(result["verification"]["privateShapeComplete"])

    def test_complete_private_local_attestation_reaches_self_attested_terminal(self) -> None:
        value = self.complete()
        self.retier_private(value, "private_local_attested")
        unsigned = self.evaluate(value)
        self.assertEqual(unsigned["join"]["terminal"], "HOLD")
        self.assertIn("PRIVATE_EVIDENCE_PROVENANCE_REQUIRED", unsigned["join"]["reasonCodes"])

        self.sign_private_with_test_root(value)
        signed = self.evaluate_with_test_trust_root(value)
        self.assertEqual(signed["join"]["terminal"], "PRIVATE_SELF_ATTESTED")
        self.assertTrue(signed["publicStatus"]["privatePhysicalFlightCompleted"])
        self.assertTrue(signed["publicStatus"]["selfAttestationOnly"])
        self.assertTrue(signed["publicStatus"]["privateEvidenceProvenanceAuthenticated"])

        forged = copy.deepcopy(value)
        provenance = forged["privateEvidenceProvenance"]
        replacement = "A" if provenance["signatureBase64Url"][-1] != "A" else "B"
        provenance["signatureBase64Url"] = provenance["signatureBase64Url"][:-1] + replacement
        provenance["provenanceId"] = mod.content_id(
            "axmheadprivateevidenceprovenance2",
            mod.body_without(provenance, "provenanceId"),
        )
        forged_result = self.evaluate_with_test_trust_root(forged)
        self.assertEqual(forged_result["join"]["terminal"], "HOLD")
        self.assertIn(
            "PRIVATE_EVIDENCE_PROVENANCE_AUTHENTICATION_FAILED",
            forged_result["join"]["reasonCodes"],
        )

        congruent = copy.deepcopy(value)
        congruent_provenance = congruent["privateEvidenceProvenance"]
        signature_bytes = mod.base64url_decode(
            congruent_provenance["signatureBase64Url"],
            "privateEvidenceProvenance.signatureBase64Url",
        )
        signature_integer = int.from_bytes(signature_bytes, "big")
        modulus = int(TEST_PRIVATE_PROVENANCE_TRUST_ROOT["modulusHex"], 16)
        congruent_integer = signature_integer + modulus
        self.assertLess(congruent_integer, 1 << (8 * len(signature_bytes)))
        congruent_provenance["signatureBase64Url"] = mod.base64url_encode(
            congruent_integer.to_bytes(len(signature_bytes), "big")
        )
        congruent_provenance["provenanceId"] = mod.content_id(
            "axmheadprivateevidenceprovenance2",
            mod.body_without(congruent_provenance, "provenanceId"),
        )
        congruent_result = self.evaluate_with_test_trust_root(congruent)
        self.assertEqual(congruent_result["join"]["terminal"], "HOLD")
        self.assertIn(
            "PRIVATE_EVIDENCE_PROVENANCE_AUTHENTICATION_FAILED",
            congruent_result["join"]["reasonCodes"],
        )

        bad_key_value = {
            "schema": bootstrap.PRIVATE_SIGNING_KEY_SCHEMA,
            **mod.PRIVATE_EVIDENCE_PROVENANCE_TRUST_ROOT,
            "privateExponentHex": "2",
        }
        bad_key_path = self.root / "bad-private-exponent.json"
        bad_key_path.write_bytes(mod.pretty_json_bytes(bad_key_value))
        unsigned_input = self.complete()
        self.retier_private(unsigned_input, "private_local_attested")
        unsigned_input_path = self.root / "unsigned-private-input.json"
        unsigned_input_path.write_bytes(mod.pretty_json_bytes(unsigned_input))
        bad_output = self.root / "bad-private-exponent-output.json"
        with self.assertRaises(bootstrap.BootstrapError) as context:
            bootstrap.sign_private_provenance(
                profile_path=PROFILE,
                input_path=unsigned_input_path,
                key_path=bad_key_path,
                out=bad_output,
            )
        self.assertEqual(context.exception.code, "PRIVATE_SIGNING_KEY_SIGNATURE_SELF_CHECK_FAILED")
        self.assertFalse(bad_output.exists())

        value["routeAttestation"]["residentRoute"]["throughputUnits"] += 1
        self.refresh_top(value, "routeAttestation", "routeAttestationId", "axmheadphysicalrouteattestation2")
        tampered = self.evaluate_with_test_trust_root(value)
        self.assertEqual(tampered["join"]["terminal"], "HOLD")
        self.assertIn("PRIVATE_EVIDENCE_PROVENANCE_PAYLOAD_MISMATCH", tampered["join"]["reasonCodes"])

    def test_private_self_attested_never_promotes_stronger_qualification(self) -> None:
        value = self.complete()
        self.retier_private(value, "private_local_attested")
        self.sign_private_with_test_root(value)
        public = self.evaluate_with_test_trust_root(value)["publicStatus"]
        for key in (
            "physicalEstateQualified", "representativeOperatorQualified", "fieldNetworkQualified",
            "operationalC2Qualified", "productionLatticeQualified", "missionAuthorityGranted",
            "commandAuthorityGranted", "targetingEngagementEffectorOrWeaponsCapability",
        ):
            self.assertFalse(public[key], key)
        self.assertEqual(public["authority"], "none")

    def test_preflight_card_cannot_substitute_for_named_human(self) -> None:
        result = self.evaluate(self.case("hold-preflight-card-substituted-for-human-authorization"))
        self.assertIn("PREFLIGHT_CARD_CANNOT_AUTHORIZE", result["join"]["reasonCodes"])
        self.assertIn("NAMED_HUMAN_AUTHORIZATION_REQUIRED", result["join"]["reasonCodes"])

    def test_preflight_authorized_action_count_is_held(self) -> None:
        value = self.complete()
        preflight = value["sourceBinding"]["preflightDisposition"]
        preflight["authorizedActionCount"] = 1
        self.refresh_source(value)
        preflight_id = preflight["receiptId"]
        value["privateFlightDispositionBinding"]["preflightReceiptId"] = preflight_id
        self.replace_authorization(
            value,
            lambda authorization: authorization.update(
                {
                    "preflightReceiptId": preflight_id,
                    "preflightAuthorizedActionCount": 1,
                }
            ),
        )
        result = self.evaluate(value)
        self.assertIn("PREFLIGHT_AUTHORIZED_ACTION_PRESENT", result["join"]["reasonCodes"])
        self.assertIn("AUTHORIZATION_BOUNDARY_INVALID", result["join"]["reasonCodes"])

    def test_incomplete_private_denominator_is_held(self) -> None:
        result = self.evaluate(self.case("hold-incomplete-private-receipt-denominator"))
        self.assertEqual(result["join"]["reasonCodes"], ["PRIVATE_RECEIPT_DENOMINATOR_INCOMPLETE"])

    def test_evidence_tier_mismatch_is_held(self) -> None:
        value = self.complete()
        value["routeAttestation"]["evidenceTier"] = "private_local_attested"
        self.refresh_top(value, "routeAttestation", "routeAttestationId", "axmheadphysicalrouteattestation2")
        self.assertIn("EVIDENCE_TIER_MISMATCH", self.evaluate(value)["join"]["reasonCodes"])

    def test_campaign_identity_mismatch_is_held(self) -> None:
        value = self.complete()
        value["continuityAttestation"]["campaignId"] = "OTHER-CAMPAIGN"
        self.refresh_top(value, "continuityAttestation", "continuityAttestationId", "axmheadcontinuityattestation2")
        self.assertIn("CAMPAIGN_IDENTITY_MISMATCH", self.evaluate(value)["join"]["reasonCodes"])

    def test_physical_action_before_authorization_is_held(self) -> None:
        value = self.complete()
        value["routeAttestation"]["observedAtUnixNs"] = 1500
        self.refresh_top(value, "routeAttestation", "routeAttestationId", "axmheadphysicalrouteattestation2")
        self.assertIn("PHYSICAL_ACTION_BEFORE_AUTHORIZATION", self.evaluate(value)["join"]["reasonCodes"])

    def test_authorization_timestamp_order_is_held(self) -> None:
        value = self.complete()
        self.replace_authorization(value, lambda auth: auth.update({"issuedAtUnixNs": 2200, "firstPhysicalActionUnixNs": 2000}))
        self.assertIn("AUTHORIZATION_BOUNDARY_INVALID", self.evaluate(value)["join"]["reasonCodes"])

    def test_route_memory_pooling_is_refused_semantically(self) -> None:
        value = self.complete()
        value["routeAttestation"]["memoryPoolingAllowed"] = True
        self.refresh_top(value, "routeAttestation", "routeAttestationId", "axmheadphysicalrouteattestation2")
        self.assertIn("ROUTE_MEMORY_POOLING_FORBIDDEN", self.evaluate(value)["join"]["reasonCodes"])

    def test_each_route_must_independently_meet_memory_floor(self) -> None:
        value = self.complete()
        value["routeAttestation"]["residentRoute"]["memoryBytes"] = 1024
        self.refresh_top(value, "routeAttestation", "routeAttestationId", "axmheadphysicalrouteattestation2")
        self.assertIn("INDIVIDUAL_ROUTE_MEMORY_INSUFFICIENT", self.evaluate(value)["join"]["reasonCodes"])

    def test_resident_baseline_verification_failure_is_held(self) -> None:
        value = self.complete()
        value["routeAttestation"]["residentRoute"]["independentVerificationStatus"] = "FAIL"
        self.refresh_top(value, "routeAttestation", "routeAttestationId", "axmheadphysicalrouteattestation2")
        self.assertIn("RESIDENT_BASELINE_NOT_VERIFIED", self.evaluate(value)["join"]["reasonCodes"])

    def test_accelerator_output_mismatch_is_held(self) -> None:
        value = self.complete()
        value["routeAttestation"]["acceleratorRoute"]["outputSha256"] = "1" * 64
        self.refresh_top(value, "routeAttestation", "routeAttestationId", "axmheadphysicalrouteattestation2")
        self.assertIn("ACCELERATOR_OUTPUT_MISMATCH", self.evaluate(value)["join"]["reasonCodes"])

    def test_accelerator_semantic_mismatch_is_held(self) -> None:
        value = self.complete()
        value["routeAttestation"]["acceleratorRoute"]["semanticIdentity"] = "different-semantic"
        self.refresh_top(value, "routeAttestation", "routeAttestationId", "axmheadphysicalrouteattestation2")
        self.assertIn("ACCELERATOR_SEMANTIC_MISMATCH", self.evaluate(value)["join"]["reasonCodes"])

    def test_accelerator_classification_mismatch_is_held(self) -> None:
        value = self.complete()
        value["routeAttestation"]["acceleratorRoute"]["classificationIdentity"] = "different-classification"
        self.refresh_top(value, "routeAttestation", "routeAttestationId", "axmheadphysicalrouteattestation2")
        self.assertIn("ACCELERATOR_CLASSIFICATION_MISMATCH", self.evaluate(value)["join"]["reasonCodes"])

    def test_nonaccelerating_optional_route_is_held(self) -> None:
        value = self.complete()
        value["routeAttestation"]["acceleratorRoute"]["throughputUnits"] = 1000
        self.refresh_top(value, "routeAttestation", "routeAttestationId", "axmheadphysicalrouteattestation2")
        self.assertIn("ACCELERATOR_NOT_FASTER", self.evaluate(value)["join"]["reasonCodes"])

    def test_post_removal_output_mismatch_is_held(self) -> None:
        value = self.complete()
        value["continuityAttestation"]["postRemovalOutputSha256"] = "2" * 64
        self.refresh_top(value, "continuityAttestation", "continuityAttestationId", "axmheadcontinuityattestation2")
        self.assertIn("CONTINUITY_OUTPUT_MISMATCH", self.evaluate(value)["join"]["reasonCodes"])

    def test_post_removal_state_mismatch_is_held(self) -> None:
        value = self.complete()
        value["continuityAttestation"]["postRemovalMissionStateDigest"] = "3" * 64
        self.refresh_top(value, "continuityAttestation", "continuityAttestationId", "axmheadcontinuityattestation2")
        self.assertIn("CANONICAL_MISSION_STATE_CHANGED", self.evaluate(value)["join"]["reasonCodes"])

    def test_lattice_dependency_is_held(self) -> None:
        value = self.complete()
        value["continuityAttestation"]["latticeRemoved"] = False
        self.refresh_top(value, "continuityAttestation", "continuityAttestationId", "axmheadcontinuityattestation2")
        self.assertIn("LATTICE_REQUIRED_FOR_LOCAL_CONTINUITY", self.evaluate(value)["join"]["reasonCodes"])

    def test_same_host_two_cell_is_held(self) -> None:
        result = self.evaluate(self.case("hold-same-host-two-cell-attestation"))
        self.assertIn("TWO_CELL_HOST_CLASSES_NOT_DISTINCT", result["join"]["reasonCodes"])

    def test_same_branch_two_cell_is_held(self) -> None:
        value = self.complete()
        value["twoCellAttestation"]["rightCell"]["branchId"] = value["twoCellAttestation"]["leftCell"]["branchId"]
        value["twoCellAttestation"]["reunion"]["retainedBranchIds"] = [value["twoCellAttestation"]["leftCell"]["branchId"]]
        self.refresh_top(value, "twoCellAttestation", "twoCellAttestationId", "axmheadtwocellattestation2")
        self.assertIn("TWO_CELL_BRANCHES_NOT_DISTINCT", self.evaluate(value)["join"]["reasonCodes"])

    def test_wrong_conflict_terminal_is_held(self) -> None:
        result = self.evaluate(self.case("hold-wrong-conflict-terminal"))
        self.assertIn("REUNION_NOT_HUMAN_REQUIRED", result["join"]["reasonCodes"])

    def test_automatic_reunion_merge_is_held(self) -> None:
        value = self.complete()
        value["twoCellAttestation"]["reunion"]["automaticMergeAllowed"] = True
        self.refresh_top(value, "twoCellAttestation", "twoCellAttestationId", "axmheadtwocellattestation2")
        self.assertIn("AUTOMATIC_REUNION_MERGE_FORBIDDEN", self.evaluate(value)["join"]["reasonCodes"])

    def test_reunion_must_retain_both_branches(self) -> None:
        value = self.complete()
        value["twoCellAttestation"]["reunion"]["retainedBranchIds"] = [value["twoCellAttestation"]["leftCell"]["branchId"]]
        self.refresh_top(value, "twoCellAttestation", "twoCellAttestationId", "axmheadtwocellattestation2")
        self.assertIn("REUNION_BRANCH_CUSTODY_MISMATCH", self.evaluate(value)["join"]["reasonCodes"])

    def test_reunion_requires_unresolved_obligation(self) -> None:
        value = self.complete()
        value["twoCellAttestation"]["reunion"]["unresolvedObligationCount"] = 0
        self.refresh_top(value, "twoCellAttestation", "twoCellAttestationId", "axmheadtwocellattestation2")
        self.assertIn("UNRESOLVED_OBLIGATION_REQUIRED", self.evaluate(value)["join"]["reasonCodes"])

    def test_replacement_head_class_must_differ(self) -> None:
        value = self.complete()
        value["successorAttestation"]["successorHeadClass"] = value["successorAttestation"]["originalHeadClass"]
        self.refresh_top(value, "successorAttestation", "successorAttestationId", "axmheadsuccessorattestation2")
        self.assertIn("REPLACEMENT_HEAD_CLASS_NOT_DISTINCT", self.evaluate(value)["join"]["reasonCodes"])

    def test_successor_may_not_depend_on_original_host(self) -> None:
        value = self.complete()
        value["successorAttestation"]["originalHostPresent"] = True
        self.refresh_top(value, "successorAttestation", "successorAttestationId", "axmheadsuccessorattestation2")
        self.assertIn("SUCCESSOR_DEPENDENCY_WIDENED", self.evaluate(value)["join"]["reasonCodes"])

    def test_each_cold_successor_answer_is_independently_derived(self) -> None:
        for key in mod.COLD_SUCCESSOR_ANSWER_KEYS:
            with self.subTest(key=key):
                value = self.complete()
                value["successorAttestation"]["answers"][key] = "forged answer"
                self.refresh_top(value, "successorAttestation", "successorAttestationId", "axmheadsuccessorattestation2")
                self.assertIn("COLD_SUCCESSOR_ANSWERS_MISMATCH", self.evaluate(value)["join"]["reasonCodes"])

    def test_duplicate_stage_denominator_is_refused(self) -> None:
        value = self.complete()
        stages = value["privateFlightDispositionBinding"]["packet"]["stageSequence"]
        stages[1] = stages[0]
        self.refresh_top(value, "privateFlightDispositionBinding", "dispositionBindingId", "axmheadprivateflightdispositionbinding2")
        with self.assertRaises(mod.JoinError) as context:
            mod.validate_input_value(value)
        self.assertEqual(context.exception.code, "DUPLICATE_LIST_VALUE")

    def test_duplicate_stage_receipt_id_is_held(self) -> None:
        value = self.complete()
        receipts = value["privateFlightDispositionBinding"]["packet"]["stageReceipts"]
        receipts[1] = copy.deepcopy(receipts[0])
        self.refresh_top(value, "privateFlightDispositionBinding", "dispositionBindingId", "axmheadprivateflightdispositionbinding2")
        reasons = self.evaluate(value)["join"]["reasonCodes"]
        self.assertIn("STAGE_RECEIPT_ID_DUPLICATE", reasons)
        self.assertIn("STAGE_RECEIPT_ORDER_MISMATCH", reasons)

    def test_stage_denominator_shortening_is_held(self) -> None:
        value = self.complete()
        value["privateFlightDispositionBinding"]["packet"]["stageReceipts"].pop()
        self.refresh_top(value, "privateFlightDispositionBinding", "dispositionBindingId", "axmheadprivateflightdispositionbinding2")
        self.assertIn("STAGE_RECEIPT_COUNT_MISMATCH", self.evaluate(value)["join"]["reasonCodes"])

    def test_stage_order_mutation_is_held(self) -> None:
        value = self.complete()
        rows = value["privateFlightDispositionBinding"]["packet"]["stageReceipts"]
        rows[4], rows[5] = rows[5], rows[4]
        self.refresh_top(value, "privateFlightDispositionBinding", "dispositionBindingId", "axmheadprivateflightdispositionbinding2")
        self.assertIn("STAGE_RECEIPT_ORDER_MISMATCH", self.evaluate(value)["join"]["reasonCodes"])

    def test_stage_predecessor_chain_break_is_held(self) -> None:
        result = self.evaluate(self.case("hold-broken-stage-predecessor-chain"))
        self.assertIn("STAGE_PREDECESSOR_CHAIN_BROKEN", result["join"]["reasonCodes"])

    def test_conflict_stage_terminal_must_be_human_required(self) -> None:
        value = self.complete()
        rows = value["privateFlightDispositionBinding"]["packet"]["stageReceipts"]
        conflict = next(row for row in rows if row["stage"] == "RESTORE_LINK_HOLD_CONFLICT")
        conflict["terminal"] = "PASS"
        self.rechain_stage_receipts(value["privateFlightDispositionBinding"])
        self.refresh_top(value, "privateFlightDispositionBinding", "dispositionBindingId", "axmheadprivateflightdispositionbinding2")
        self.assertIn("STAGE_TERMINAL_MISMATCH", self.evaluate(value)["join"]["reasonCodes"])

    def test_stage_timestamp_before_authorization_is_held(self) -> None:
        value = self.complete()
        rows = value["privateFlightDispositionBinding"]["packet"]["stageReceipts"]
        rows[0]["observedAtUnixNs"] = 1500
        self.rechain_stage_receipts(value["privateFlightDispositionBinding"])
        self.refresh_top(value, "privateFlightDispositionBinding", "dispositionBindingId", "axmheadprivateflightdispositionbinding2")
        self.assertIn("STAGE_TIMESTAMP_BEFORE_AUTHORIZATION", self.evaluate(value)["join"]["reasonCodes"])

    def test_stage_authorization_mismatch_is_held(self) -> None:
        value = self.complete()
        rows = value["privateFlightDispositionBinding"]["packet"]["stageReceipts"]
        rows[8]["authorizationReceiptId"] = "otherauthorization1_" + "a" * 64
        self.rechain_stage_receipts(value["privateFlightDispositionBinding"])
        self.refresh_top(value, "privateFlightDispositionBinding", "dispositionBindingId", "axmheadprivateflightdispositionbinding2")
        self.assertIn("STAGE_AUTHORIZATION_MISMATCH", self.evaluate(value)["join"]["reasonCodes"])

    def test_sealed_verification_failure_is_held(self) -> None:
        result = self.evaluate(self.case("hold-sealed-package-verification-failure"))
        self.assertIn("SEALED_PACKAGE_VERIFICATION_FAILED", result["join"]["reasonCodes"])

    def test_sealed_public_disposition_digest_mismatch_is_held(self) -> None:
        value = self.complete()
        value["privateFlightDispositionBinding"]["sealedPackage"]["publicDispositionDigest"] = "sha256:" + "4" * 64
        self.refresh_top(value, "privateFlightDispositionBinding", "dispositionBindingId", "axmheadprivateflightdispositionbinding2")
        self.assertIn("SEALED_PUBLIC_DISPOSITION_DIGEST_MISMATCH", self.evaluate(value)["join"]["reasonCodes"])

    def test_zero_private_evidence_is_refused_by_shape(self) -> None:
        value = self.complete()
        value["routeAttestation"]["privateEvidenceBodyCount"] = 0
        self.refresh_top(value, "routeAttestation", "routeAttestationId", "axmheadphysicalrouteattestation2")
        with self.assertRaises(mod.JoinError) as context:
            mod.validate_input_value(value)
        self.assertEqual(context.exception.code, "INTEGER_REQUIRED")

    def test_public_evidence_body_count_is_refused(self) -> None:
        value = self.complete()
        value["continuityAttestation"]["publicEvidenceBodyCount"] = 1
        self.refresh_top(value, "continuityAttestation", "continuityAttestationId", "axmheadcontinuityattestation2")
        with self.assertRaises(mod.JoinError) as context:
            mod.validate_input_value(value)
        self.assertEqual(context.exception.code, "INTEGER_REQUIRED")

    def test_source_disposition_digest_forgery_is_refused(self) -> None:
        value = self.complete()
        value["privateFlightDispositionBinding"]["sourceDisposition"]["digest"] = "sha256:" + "5" * 64
        self.refresh_top(value, "privateFlightDispositionBinding", "dispositionBindingId", "axmheadprivateflightdispositionbinding2")
        with self.assertRaises(mod.JoinError) as context:
            mod.validate_input_value(value)
        self.assertEqual(context.exception.code, "SOURCE_DISPOSITION_DIGEST_INVALID")

    def test_authority_promotion_is_held(self) -> None:
        value = self.complete()
        source = value["privateFlightDispositionBinding"]["sourceDisposition"]
        source["authority"] = "system"
        self.refresh_source_disposition(value["privateFlightDispositionBinding"])
        self.refresh_top(value, "privateFlightDispositionBinding", "dispositionBindingId", "axmheadprivateflightdispositionbinding2")
        self.assertIn("AUTHORITY_PROMOTED", self.evaluate(value)["join"]["reasonCodes"])

    def test_stronger_qualification_promotion_is_held(self) -> None:
        value = self.complete()
        source = value["privateFlightDispositionBinding"]["sourceDisposition"]
        source["operationalC2Qualified"] = True
        self.refresh_source_disposition(value["privateFlightDispositionBinding"])
        self.refresh_top(value, "privateFlightDispositionBinding", "dispositionBindingId", "axmheadprivateflightdispositionbinding2")
        self.assertIn("STRONGER_QUALIFICATION_PROMOTED", self.evaluate(value)["join"]["reasonCodes"])

    def test_private_path_in_allowlisted_string_is_refused(self) -> None:
        value = self.complete()
        value["privateFlightDispositionBinding"]["cartridge"]["nextSafeAction"] = "Read C:\\private\\evidence.json"
        self.refresh_top(value, "privateFlightDispositionBinding", "dispositionBindingId", "axmheadprivateflightdispositionbinding2")
        with self.assertRaises(mod.JoinError) as context:
            mod.validate_input_value(value)
        self.assertEqual(context.exception.code, "PRIVATE_PATH_DETECTED")

    def test_private_host_identity_is_refused(self) -> None:
        value = self.complete()
        value["successorAttestation"]["nextSafeAction"] = "Continue on PRIVATE-HOST-01"
        self.refresh_top(value, "successorAttestation", "successorAttestationId", "axmheadsuccessorattestation2")
        with self.assertRaises(mod.JoinError) as context:
            mod.validate_input_value(value)
        self.assertEqual(context.exception.code, "PRIVATE_HOST_DETECTED")

    def test_network_endpoint_is_refused(self) -> None:
        value = self.complete()
        value["successorAttestation"]["nextSafeAction"] = "Contact ssh://private-host"
        self.refresh_top(value, "successorAttestation", "successorAttestationId", "axmheadsuccessorattestation2")
        with self.assertRaises(mod.JoinError) as context:
            mod.validate_input_value(value)
        self.assertEqual(context.exception.code, "PRIVATE_ENDPOINT_DETECTED")

    def test_credential_material_is_refused(self) -> None:
        value = self.complete()
        value["successorAttestation"]["nextSafeAction"] = "SYNTHETIC-CREDENTIAL-TEST-01"
        self.refresh_top(value, "successorAttestation", "successorAttestationId", "axmheadsuccessorattestation2")
        with self.assertRaises(mod.JoinError) as context:
            mod.validate_input_value(value)
        self.assertEqual(context.exception.code, "CREDENTIAL_MATERIAL_DETECTED")

    def test_unknown_field_is_refused(self) -> None:
        value = self.complete()
        value["routeAttestation"]["hostname"] = "redacted"
        with self.assertRaises(mod.JoinError) as context:
            mod.validate_input_value(value)
        self.assertEqual(context.exception.code, "OBJECT_KEYS_INVALID")

    def test_content_identity_forgery_is_refused(self) -> None:
        value = self.complete()
        value["routeAttestation"]["routeAttestationId"] = "axmheadphysicalrouteattestation2_" + "0" * 64
        with self.assertRaises(mod.JoinError) as context:
            mod.validate_input_value(value)
        self.assertEqual(context.exception.code, "ATTESTATION_CONTENT_ID_INVALID")

    def test_json_boolean_substitution_is_refused(self) -> None:
        value = self.complete()
        value["continuityAttestation"]["latticeRemoved"] = 1
        self.refresh_top(value, "continuityAttestation", "continuityAttestationId", "axmheadcontinuityattestation2")
        with self.assertRaises(mod.JoinError) as context:
            mod.validate_input_value(value)
        self.assertEqual(context.exception.code, "BOOLEAN_REQUIRED")

    def test_direct_verifier_is_truthfully_unauthenticated(self) -> None:
        value = self.case("prepared-exact-public-sources-no-private-flight")
        input_path = self.root / "direct.json"
        input_path.write_bytes(mod.pretty_json_bytes(value))
        result = subprocess.run([sys.executable, str(VERIFIER), str(PROFILE), str(input_path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        receipt = json.loads(result.stdout.decode("utf-8"))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, b"")
        self.assertFalse(receipt["bootstrapAuthenticated"])

    def test_external_bootstrap_authenticates_measured_verifier(self) -> None:
        result, receipt = self.run_bootstrap(self.case("prepared-exact-public-sources-no-private-flight"))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, b"")
        self.assertTrue(receipt["bootstrapAuthenticated"])
        self.assertEqual(receipt["standaloneVerifierSha256"], bootstrap.STANDALONE_VERIFIER_SHA256)

    def test_external_bootstrap_works_from_foreign_directory(self) -> None:
        foreign = self.root / "foreign"
        foreign.mkdir()
        result, receipt = self.run_bootstrap(self.case("prepared-exact-public-sources-no-private-flight"), cwd=foreign)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(receipt["bootstrapAuthenticated"])

    def test_bootstrap_stdout_and_output_file_are_byte_identical(self) -> None:
        out = self.root / "receipt.json"
        result, _ = self.run_bootstrap(self.case("prepared-exact-public-sources-no-private-flight"), out=out)
        self.assertEqual(result.stdout, out.read_bytes())
        self.assertNotIn(b"\r\n", result.stdout)

    def test_existing_output_is_refused_without_overwrite(self) -> None:
        out = self.root / "existing.json"
        out.write_text("sentinel", encoding="utf-8")
        result, receipt = self.run_bootstrap(self.case("prepared-exact-public-sources-no-private-flight"), out=out)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(receipt["code"], "OUTPUT_EXISTS")
        self.assertEqual(out.read_text(encoding="utf-8"), "sentinel")

    def test_malicious_verifier_substitution_is_refused_before_execution(self) -> None:
        malicious = self.root / "malicious.py"
        marker = self.root / "executed"
        malicious.write_text(f"from pathlib import Path\nPath({str(marker)!r}).write_text('ran')\n", encoding="utf-8")
        with self.assertRaises(bootstrap.BootstrapError) as context:
            bootstrap.require_measured_verifier(malicious)
        self.assertEqual(context.exception.code, "VERIFIER_SOURCE_DIGEST_INVALID")
        self.assertFalse(marker.exists())

    def test_external_tool_does_not_import_substituted_sibling_verifier(self) -> None:
        tool = self.root / "axm_head_physical_long_haul_join.py"
        verifier = self.root / "verify_axm_head_physical_long_haul_join.py"
        marker = self.root / "executed-by-import"
        tool.write_bytes(TOOL.read_bytes())
        verifier.write_text(
            f"from pathlib import Path\nPath({str(marker)!r}).write_text('ran')\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [sys.executable, str(tool), "validate-profile", str(PROFILE)],
            cwd=self.root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        receipt = json.loads(result.stdout.decode("utf-8"))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr, b"")
        self.assertEqual(receipt["code"], "VERIFIER_SOURCE_DIGEST_INVALID")
        self.assertFalse(marker.exists())

    def test_bootstrap_snapshots_input_before_measured_execution(self) -> None:
        value = self.case("prepared-exact-public-sources-no-private-flight")
        input_path = self.root / "snapshot-input.json"
        input_path.write_bytes(mod.pretty_json_bytes(value))
        original_run = bootstrap.subprocess.run

        def mutate_then_run(*args, **kwargs):
            input_path.write_text('{"mutated":true}\n', encoding="utf-8")
            return original_run(*args, **kwargs)

        captured = io.BytesIO()
        with mock.patch.object(bootstrap.subprocess, "run", side_effect=mutate_then_run), mock.patch.object(
            bootstrap.sys, "stdout", SimpleNamespace(buffer=captured)
        ):
            receipt = bootstrap.bootstrap_verify(profile_path=PROFILE, input_path=input_path)
        self.assertEqual(receipt["join"]["terminal"], "PREPARED_NOT_ARMED")
        self.assertEqual(captured.getvalue(), b"")
        self.assertEqual(json.loads(input_path.read_text(encoding="utf-8")), {"mutated": True})

    def test_duplicate_json_key_is_refused_before_verifier_execution(self) -> None:
        input_path = self.root / "duplicate-key.json"
        input_path.write_bytes(b'{"schema":"first","schema":"second"}\n')
        result = subprocess.run(
            [sys.executable, str(TOOL), "verify", str(input_path), "--profile", str(PROFILE)],
            cwd=self.root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        receipt = json.loads(result.stdout.decode("utf-8"))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr, b"")
        self.assertEqual(receipt["code"], "DUPLICATE_JSON_KEY")

    def test_verifier_source_must_be_one_regular_file(self) -> None:
        with self.assertRaises(bootstrap.BootstrapError) as context:
            bootstrap.require_measured_verifier(self.root)
        self.assertEqual(context.exception.code, "REGULAR_FILE_REQUIRED")

    def test_authenticated_authoritative_bytes_are_lf_only(self) -> None:
        result, _ = self.run_bootstrap(self.case("prepared-exact-public-sources-no-private-flight"))
        self.assertEqual(result.returncode, 0)
        self.assertNotIn(b"\r\n", result.stdout)
        self.assertTrue(result.stdout.endswith(b"\n"))

    def test_public_projection_contains_zero_private_bodies(self) -> None:
        value = self.complete()
        self.retier_private(value, "private_local_attested")
        self.sign_private_with_test_root(value)
        public = self.evaluate_with_test_trust_root(value)["publicStatus"]
        self.assertEqual(public["publicEvidenceBodyCount"], 0)
        mod.scan_forbidden_private_material(public, "public")


if __name__ == "__main__":
    unittest.main()
