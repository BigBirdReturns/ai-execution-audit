#!/usr/bin/env python3
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "mating_surface/anchor_node/verify_axm_head_physical_long_haul_join.py"
BOOTSTRAP = ROOT / "mating_surface/anchor_node/axm_head_physical_long_haul_join.py"
TESTS = ROOT / "mating_surface/anchor_node/conformance/test_axm_head_physical_long_haul_join.py"
FIXTURES = ROOT / "mating_surface/anchor_node/fixtures/axm-head-physical-long-haul-join-cases-01.json"
DOC = ROOT / "mating_surface/anchor_node/AXM-HEAD-PHYSICAL-LONG-HAUL-JOIN-01.md"

OLD_FIXTURE_DIGEST = "db903e2d6e0238161783242b49ad55e105078f4f2f0733f74a30ad697eb1863a"
OLD_VERIFIER_DIGEST = "72cd88355a57c71e2cad25028f5562f02e6543f10072e400ee8b0ca469b4596e"
PREFLIGHT_COMPLETED_AT_UNIX_NS = 900
EXPECTED_CAMPAIGN_ID = "PRIVATE-STC-MARY-FLIGHT-01"
EXPECTED_AUTHORIZATION_SCOPE = "private-stc-mary-flight-01"


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def pretty_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def body_without(value: Mapping[str, Any], key: str) -> dict[str, Any]:
    result = dict(value)
    result.pop(key, None)
    return result


def content_id(prefix: str, value: Mapping[str, Any], id_key: str) -> str:
    return f"{prefix}_{sha256_bytes(canonical_json_bytes(body_without(value, id_key)))}"


def refresh(value: dict[str, Any], key: str, prefix: str) -> None:
    value[key] = content_id(prefix, value, key)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor, observed {count}")
    return text.replace(old, new, 1)


def rechain_stage_receipts(disposition: dict[str, Any]) -> None:
    previous = None
    for row in disposition["packet"]["stageReceipts"]:
        row["previousReceiptId"] = previous
        refresh(row, "receiptId", "stcmaryprivateflightstage1")
        previous = row["receiptId"]


def expected_successor_answers(
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
        "whatProvesIt": (
            f"Detached sealed evidence root sha256:{evidence_root_sha256} "
            "with PASS verification."
        ),
        "whatRemainsUnresolved": (
            f"{unresolved_obligation_count} unresolved reconciliation {noun}."
        ),
        "nextSafeAction": next_safe_action,
    }


def update_fixtures() -> str:
    catalog = json.loads(FIXTURES.read_text(encoding="utf-8"))
    if sha256_bytes(canonical_json_bytes(catalog)) != OLD_FIXTURE_DIGEST:
        raise SystemExit("fixture catalog predecessor digest differs")

    for case in catalog["cases"]:
        value = case["input"]
        source = value["sourceBinding"]
        preflight = source["preflightDisposition"]
        if preflight is not None:
            if "completedAtUnixNs" in preflight:
                raise SystemExit(f"{case['caseId']}: completion time already present")
            preflight["completedAtUnixNs"] = PREFLIGHT_COMPLETED_AT_UNIX_NS
            refresh(preflight, "receiptId", "axmheadpreflightdisposition1")
            preflight_id = preflight["receiptId"]
        else:
            preflight_id = None

        disposition = value.get("privateFlightDispositionBinding")
        if disposition is not None:
            if preflight_id is None:
                raise SystemExit(f"{case['caseId']}: private disposition lacks preflight")
            authorization = disposition["authorizationReceipt"]
            if "preflightCompletedAtUnixNs" in authorization:
                raise SystemExit(f"{case['caseId']}: copied completion time already present")
            disposition["preflightReceiptId"] = preflight_id
            authorization["preflightReceiptId"] = preflight_id
            authorization["preflightCompletedAtUnixNs"] = PREFLIGHT_COMPLETED_AT_UNIX_NS
            refresh(authorization, "receiptId", "stcmarynamedhumanauthorization1")
            authorization_id = authorization["receiptId"]

            for object_key in (
                "routeAttestation",
                "continuityAttestation",
                "twoCellAttestation",
                "successorAttestation",
            ):
                obj = value.get(object_key)
                if obj is not None:
                    obj["authorizationReceiptId"] = authorization_id

            disposition["authorizationReceiptId"] = authorization_id
            disposition["cartridge"]["humanAuthorityReceiptId"] = authorization_id
            for row in disposition["packet"]["stageReceipts"]:
                row["authorizationReceiptId"] = authorization_id
            rechain_stage_receipts(disposition)

            successor = value.get("successorAttestation")
            if successor is not None:
                successor["humanAuthorityReceiptId"] = authorization_id
                successor["answers"] = expected_successor_answers(
                    cartridge_id=disposition["cartridge"]["cartridgeId"],
                    mission_state_digest=disposition["cartridge"]["missionStateDigest"],
                    authorization_receipt_id=authorization_id,
                    evidence_root_sha256=disposition["sealedPackage"]["evidenceRootSha256"],
                    unresolved_obligation_count=disposition["cartridge"]["unresolvedObligationCount"],
                    next_safe_action=disposition["cartridge"]["nextSafeAction"],
                )

            object_specs = (
                ("routeAttestation", "routeAttestationId", "axmheadphysicalrouteattestation2"),
                ("continuityAttestation", "continuityAttestationId", "axmheadcontinuityattestation2"),
                ("twoCellAttestation", "twoCellAttestationId", "axmheadtwocellattestation2"),
                ("successorAttestation", "successorAttestationId", "axmheadsuccessorattestation2"),
            )
            for object_key, id_key, prefix in object_specs:
                obj = value.get(object_key)
                if obj is not None:
                    refresh(obj, id_key, prefix)
            refresh(
                disposition,
                "dispositionBindingId",
                "axmheadprivateflightdispositionbinding2",
            )

        refresh(source, "sourceBindingId", "axmheadphysicalflightsourcebinding2")
        if value.get("privateEvidenceProvenance") is not None:
            raise SystemExit(f"{case['caseId']}: synthetic fixture carries provenance")

    FIXTURES.write_bytes(pretty_json_bytes(catalog))
    return sha256_bytes(canonical_json_bytes(catalog))


def update_verifier(fixture_digest: str) -> str:
    verifier = VERIFIER.read_text(encoding="utf-8")
    verifier = replace_once(
        verifier,
        '''PRIVATE_EVIDENCE_PROVENANCE_ALGORITHM = "rsa-pkcs1v15-sha256"

PRIVATE_EVIDENCE_PROVENANCE_TRUST_ROOT = {''',
        f'''PRIVATE_EVIDENCE_PROVENANCE_ALGORITHM = "rsa-pkcs1v15-sha256"
EXPECTED_CAMPAIGN_ID = "{EXPECTED_CAMPAIGN_ID}"
EXPECTED_AUTHORIZATION_SCOPE = "{EXPECTED_AUTHORIZATION_SCOPE}"

PRIVATE_EVIDENCE_PROVENANCE_TRUST_ROOT = {{''',
        "campaign and authorization scope constants",
    )
    verifier = replace_once(
        verifier,
        '''                "reviewCardActionCount",
                "authorizedActionCount",
                "phaseSequence",''',
        '''                "reviewCardActionCount",
                "authorizedActionCount",
                "completedAtUnixNs",
                "phaseSequence",''',
        "preflight exact-key denominator",
    )
    verifier = replace_once(
        verifier,
        '''    require_int(item["authorizedActionCount"], f"{label}.authorizedActionCount", 0, 64)
    require_string_list(item["phaseSequence"],''',
        '''    require_int(item["authorizedActionCount"], f"{label}.authorizedActionCount", 0, 64)
    require_int(item["completedAtUnixNs"], f"{label}.completedAtUnixNs", 1)
    require_string_list(item["phaseSequence"],''',
        "preflight completion validation",
    )
    verifier = replace_once(
        verifier,
        '''                "preflightAuthorizedActionCount",
                "bodyPresent",''',
        '''                "preflightAuthorizedActionCount",
                "preflightCompletedAtUnixNs",
                "bodyPresent",''',
        "authorization exact-key denominator",
    )
    verifier = replace_once(
        verifier,
        '''    require_int(item["preflightAuthorizedActionCount"], f"{label}.preflightAuthorizedActionCount", 0, 64)
    if require_bool(item["bodyPresent"],''',
        '''    require_int(item["preflightAuthorizedActionCount"], f"{label}.preflightAuthorizedActionCount", 0, 64)
    require_int(item["preflightCompletedAtUnixNs"], f"{label}.preflightCompletedAtUnixNs", 1)
    if require_bool(item["bodyPresent"],''',
        "authorization copied completion validation",
    )
    verifier = replace_once(
        verifier,
        '''    predicates["campaignIdentityUniform"] = len(set(campaigns)) == 1''',
        '''    predicates["campaignIdentityUniform"] = (
        len(set(campaigns)) == 1 and campaigns[0] == EXPECTED_CAMPAIGN_ID
    )''',
        "exact campaign identity predicate",
    )
    verifier = replace_once(
        verifier,
        '''    predicates["preflightNotPromotedToAuthorization"] = authorization["actorClass"] != "preflight_card"
    predicates["authorizationFollowsCompletedPreflight"] = (''',
        '''    predicates["preflightNotPromotedToAuthorization"] = authorization["actorClass"] != "preflight_card"
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
    predicates["authorizationFollowsCompletedPreflight"] = (''',
        "authorization custody predicates",
    )
    verifier = replace_once(
        verifier,
        '''        and authorization["preflightAuthorizedActionCount"] == 0
        and authorization["issuedAtUnixNs"] < authorization["firstPhysicalActionUnixNs"]''',
        '''        and authorization["preflightAuthorizedActionCount"] == 0
        and predicates["authorizationPreflightCompletionCrossBound"]
        and predicates["authorizationIssuedAfterPreflightCompletion"]
        and authorization["issuedAtUnixNs"] < authorization["firstPhysicalActionUnixNs"]''',
        "authorization chronology predicate",
    )
    verifier = replace_once(
        verifier,
        '''    add_reason(reasons, "PREFLIGHT_CARD_CANNOT_AUTHORIZE", not predicates["preflightNotPromotedToAuthorization"])
    add_reason(reasons, "AUTHORIZATION_BOUNDARY_INVALID", not predicates["authorizationFollowsCompletedPreflight"])''',
        '''    add_reason(reasons, "PREFLIGHT_CARD_CANNOT_AUTHORIZE", not predicates["preflightNotPromotedToAuthorization"])
    add_reason(reasons, "AUTHORIZATION_SCOPE_MISMATCH", not predicates["authorizationScopeCoversCampaign"])
    add_reason(reasons, "PREFLIGHT_IDENTITY_CANNOT_BE_HUMAN_ACTOR", not predicates["namedHumanActorDistinctFromPreflight"])
    add_reason(reasons, "PREFLIGHT_COMPLETION_REFERENCE_MISMATCH", not predicates["authorizationPreflightCompletionCrossBound"])
    add_reason(reasons, "AUTHORIZATION_BEFORE_PREFLIGHT_COMPLETION", not predicates["authorizationIssuedAfterPreflightCompletion"])
    add_reason(reasons, "AUTHORIZATION_BOUNDARY_INVALID", not predicates["authorizationFollowsCompletedPreflight"])''',
        "authorization custody reasons",
    )
    verifier = replace_once(
        verifier,
        '''    predicates["twoCellHostClassesDistinct"] = left["hostClass"] != right["hostClass"]
    predicates["twoCellBranchesDistinct"] = left["branchId"] != right["branchId"]''',
        '''    predicates["twoCellHostClassesDistinct"] = left["hostClass"] != right["hostClass"]
    predicates["twoCellIdentitiesDistinct"] = left["cellId"] != right["cellId"]
    predicates["twoCellBranchesDistinct"] = left["branchId"] != right["branchId"]''',
        "two-cell identity predicate",
    )
    verifier = replace_once(
        verifier,
        '''    add_reason(reasons, "TWO_CELL_HOST_CLASSES_NOT_DISTINCT", not predicates["twoCellHostClassesDistinct"])
    add_reason(reasons, "TWO_CELL_BRANCHES_NOT_DISTINCT", not predicates["twoCellBranchesDistinct"])''',
        '''    add_reason(reasons, "TWO_CELL_HOST_CLASSES_NOT_DISTINCT", not predicates["twoCellHostClassesDistinct"])
    add_reason(reasons, "TWO_CELL_IDENTITIES_NOT_DISTINCT", not predicates["twoCellIdentitiesDistinct"])
    add_reason(reasons, "TWO_CELL_BRANCHES_NOT_DISTINCT", not predicates["twoCellBranchesDistinct"])''',
        "two-cell identity reason",
    )
    verifier = replace_once(
        verifier,
        f'FIXTURE_CATALOG_CANONICAL_SHA256 = "{OLD_FIXTURE_DIGEST}"',
        f'FIXTURE_CATALOG_CANONICAL_SHA256 = "{fixture_digest}"',
        "fixture catalog digest",
    )
    VERIFIER.write_text(verifier, encoding="utf-8", newline="\n")
    return sha256_bytes(VERIFIER.read_bytes())


def update_bootstrap(verifier_digest: str) -> None:
    bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
    bootstrap = replace_once(
        bootstrap,
        f'STANDALONE_VERIFIER_SHA256 = "{OLD_VERIFIER_DIGEST}"',
        f'STANDALONE_VERIFIER_SHA256 = "{verifier_digest}"',
        "bootstrap verifier digest",
    )
    BOOTSTRAP.write_text(bootstrap, encoding="utf-8", newline="\n")


def update_tests() -> int:
    tests = TESTS.read_text(encoding="utf-8")
    before_methods = sum(
        1
        for node in ast.walk(ast.parse(tests))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    )
    if before_methods != 76:
        raise SystemExit(f"focused predecessor denominator differs: {before_methods}")

    tests = replace_once(
        tests,
        '''    def test_preflight_card_cannot_substitute_for_named_human(self) -> None:
        result = self.evaluate(self.case("hold-preflight-card-substituted-for-human-authorization"))
        self.assertIn("PREFLIGHT_CARD_CANNOT_AUTHORIZE", result["join"]["reasonCodes"])
        self.assertIn("NAMED_HUMAN_AUTHORIZATION_REQUIRED", result["join"]["reasonCodes"])
''',
        '''    def test_preflight_card_cannot_substitute_for_named_human(self) -> None:
        result = self.evaluate(self.case("hold-preflight-card-substituted-for-human-authorization"))
        self.assertIn("PREFLIGHT_CARD_CANNOT_AUTHORIZE", result["join"]["reasonCodes"])
        self.assertIn("NAMED_HUMAN_AUTHORIZATION_REQUIRED", result["join"]["reasonCodes"])

        signed = self.complete()
        self.retier_private(signed, "private_local_attested")
        preflight_id = signed["sourceBinding"]["preflightDisposition"]["receiptId"]
        self.replace_authorization(
            signed,
            lambda authorization: authorization.update({"actorRef": preflight_id}),
        )
        self.sign_private_with_test_root(signed)
        actor_result = self.evaluate_with_test_trust_root(signed)
        self.assertEqual(actor_result["join"]["terminal"], "HOLD")
        self.assertIn(
            "PREFLIGHT_IDENTITY_CANNOT_BE_HUMAN_ACTOR",
            actor_result["join"]["reasonCodes"],
        )
''',
        "preflight actor witness",
    )
    tests = replace_once(
        tests,
        '''        self.assertEqual(result["join"]["terminal"], "HOLD")
        self.assertIn("CAMPAIGN_IDENTITY_MISMATCH", result["join"]["reasonCodes"])

    def test_physical_action_before_authorization_is_held(self) -> None:''',
        '''        self.assertEqual(result["join"]["terminal"], "HOLD")
        self.assertIn("CAMPAIGN_IDENTITY_MISMATCH", result["join"]["reasonCodes"])

        scoped = self.complete()
        self.retier_private(scoped, "private_local_attested")
        self.replace_authorization(
            scoped,
            lambda authorization: authorization.update({"scope": "unrelated-scope"}),
        )
        self.sign_private_with_test_root(scoped)
        scope_result = self.evaluate_with_test_trust_root(scoped)
        self.assertEqual(scope_result["join"]["terminal"], "HOLD")
        self.assertIn(
            "AUTHORIZATION_SCOPE_MISMATCH",
            scope_result["join"]["reasonCodes"],
        )

    def test_physical_action_before_authorization_is_held(self) -> None:''',
        "authorization scope witness",
    )
    tests = replace_once(
        tests,
        '''    def test_authorization_timestamp_order_is_held(self) -> None:
        value = self.complete()
        self.replace_authorization(value, lambda auth: auth.update({"issuedAtUnixNs": 2200, "firstPhysicalActionUnixNs": 2000}))
        self.assertIn("AUTHORIZATION_BOUNDARY_INVALID", self.evaluate(value)["join"]["reasonCodes"])
''',
        '''    def test_authorization_timestamp_order_is_held(self) -> None:
        value = self.complete()
        self.replace_authorization(value, lambda auth: auth.update({"issuedAtUnixNs": 2200, "firstPhysicalActionUnixNs": 2000}))
        self.assertIn("AUTHORIZATION_BOUNDARY_INVALID", self.evaluate(value)["join"]["reasonCodes"])

        signed = self.complete()
        self.retier_private(signed, "private_local_attested")
        completed_at = signed["sourceBinding"]["preflightDisposition"]["completedAtUnixNs"]
        self.replace_authorization(
            signed,
            lambda authorization: authorization.update(
                {
                    "issuedAtUnixNs": completed_at - 1,
                    "preflightCompletedAtUnixNs": completed_at,
                }
            ),
        )
        self.sign_private_with_test_root(signed)
        chronology_result = self.evaluate_with_test_trust_root(signed)
        self.assertEqual(chronology_result["join"]["terminal"], "HOLD")
        self.assertIn(
            "AUTHORIZATION_BEFORE_PREFLIGHT_COMPLETION",
            chronology_result["join"]["reasonCodes"],
        )
''',
        "preflight chronology witness",
    )
    tests = replace_once(
        tests,
        '''    def test_same_host_two_cell_is_held(self) -> None:
        result = self.evaluate(self.case("hold-same-host-two-cell-attestation"))
        self.assertIn("TWO_CELL_HOST_CLASSES_NOT_DISTINCT", result["join"]["reasonCodes"])
''',
        '''    def test_same_host_two_cell_is_held(self) -> None:
        result = self.evaluate(self.case("hold-same-host-two-cell-attestation"))
        self.assertIn("TWO_CELL_HOST_CLASSES_NOT_DISTINCT", result["join"]["reasonCodes"])

        signed = self.complete()
        self.retier_private(signed, "private_local_attested")
        two_cell = signed["twoCellAttestation"]
        two_cell["rightCell"]["cellId"] = two_cell["leftCell"]["cellId"]
        self.refresh_top(
            signed,
            "twoCellAttestation",
            "twoCellAttestationId",
            "axmheadtwocellattestation2",
        )
        self.sign_private_with_test_root(signed)
        identity_result = self.evaluate_with_test_trust_root(signed)
        self.assertEqual(identity_result["join"]["terminal"], "HOLD")
        self.assertIn(
            "TWO_CELL_IDENTITIES_NOT_DISTINCT",
            identity_result["join"]["reasonCodes"],
        )
''',
        "two-cell identity witness",
    )
    after_methods = sum(
        1
        for node in ast.walk(ast.parse(tests))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    )
    if after_methods != 76:
        raise SystemExit(f"focused successor denominator differs: {after_methods}")
    TESTS.write_text(tests, encoding="utf-8", newline="\n")
    return after_methods


def update_documentation() -> None:
    doc = DOC.read_text(encoding="utf-8")
    doc = replace_once(
        doc,
        "named-human authorization distinct from the preflight receipt\n"
        "authorization precedes physical observation and packet receipts\n",
        "preflight completion timestamp retained and cross-bound\n"
        "named-human authorization scope bound to the exact campaign\n"
        "named-human actor identity distinct from the preflight receipt and source binding\n"
        "authorization issued after preflight completion and before physical observation and packet receipts\n",
        "authorization reconstruction documentation",
    )
    doc = replace_once(
        doc,
        "two complete cells independently verified\n"
        "two actual host classes distinct\n"
        "two branches distinct and both retained\n",
        "two complete cells independently verified\n"
        "two cell identities distinct\n"
        "two actual host classes distinct\n"
        "two branches distinct and both retained\n",
        "two-cell reconstruction documentation",
    )
    doc = replace_once(
        doc,
        "Can an independently authenticated local verifier reconstruct the complete private continuity, partition, reunion, successor, and sealed-package predicates from body-free `private_local_attested` receipts, while making the admitted preflight card, synthetic evidence, source coordinates, hardware identity, and self-consistent forgery incapable of manufacturing physical evidence or authority?",
        "Can an independently authenticated local verifier reconstruct the complete private continuity, ordered campaign-bound authorization, distinct-cell partition, reunion, successor, and sealed-package predicates from body-free `private_local_attested` receipts, while making the admitted preflight card, synthetic evidence, source coordinates, hardware identity, and self-consistent forgery incapable of manufacturing physical evidence or authority?",
        "control question",
    )
    DOC.write_text(doc, encoding="utf-8", newline="\n")


def main() -> None:
    fixture_digest = update_fixtures()
    verifier_digest = update_verifier(fixture_digest)
    update_bootstrap(verifier_digest)
    focused_methods = update_tests()
    update_documentation()
    print(
        json.dumps(
            {
                "schema": "axm-head/pr61-authorization-custody-repair@1",
                "status": "PASS",
                "fixtureCatalogCanonicalSha256": fixture_digest,
                "standaloneVerifierSha256": verifier_digest,
                "preflightCompletedAtUnixNs": PREFLIGHT_COMPLETED_AT_UNIX_NS,
                "expectedCampaignId": EXPECTED_CAMPAIGN_ID,
                "expectedAuthorizationScope": EXPECTED_AUTHORIZATION_SCOPE,
                "focusedMethods": focused_methods,
                "physicalExecutionOccurred": False,
                "issue37Advanced": False,
                "workersLaunched": 0,
                "listenersCreated": 0,
                "authority": "none",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
