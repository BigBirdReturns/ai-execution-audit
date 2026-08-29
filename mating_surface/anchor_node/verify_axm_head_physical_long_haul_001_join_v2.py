from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

PROFILE_SCHEMA = "axm-head-physical-long-haul-001-join-v2-profile/2"
PROFILE_ID = "axm-head/physical-long-haul-001/join-v2"
STATE_SCHEMA = "axm-head/physical-long-haul-001-join-state@2"
DECISION_SCHEMA = "axm-head/physical-long-haul-001-join-decision@2"
PUBLIC_SCHEMA = "axm-head/physical-long-haul-001-public-status@2"
MANIFEST_SCHEMA = "axm-head/physical-long-haul-001-join-manifest@2"
VERDICT_SCHEMA = "axm-head/physical-long-haul-001-join-verdict@2"
PROFILE_CANONICAL_SHA256 = "66a4e11b0023a67e0d545b9d29817819da17e9195304261f1fd30a6f6da74e56"
CLAIM_BOUNDARY = (
    "Public preflight join binding the admitted AXM HEAD mission-volume contract to the admitted STC MARY "
    "conductor, frozen physical-flight floor, and sole issue #37 execution coordinate. It may validate body-free "
    "private coordinate headers and compile an exact operator card, but it performs no physical action, materializes "
    "no mission volume, launches no worker, creates no listener, grants no authorization, and establishes no physical "
    "Estate, representative operator, field network, operational C2, production Lattice, mission, command, targeting, "
    "engagement, effector, or weapons qualification or authority."
)
EXPECTED_RELATIVE_FILES = (
    "JOIN/preparation-state.json",
    "JOIN/decision.json",
    "PUBLIC/status.json",
    "RECOVERY/profile.json",
    "RECOVERY/verify_join.py",
)
PREPARED_REASON_CODES = (
    "ADMITTED_PUBLIC_FLOOR_BOUND",
    "EXECUTION_CARD_ABSENT",
    "PRIVATE_COORDINATES_ABSENT",
    "SEPARATE_HUMAN_AUTHORIZATION_ABSENT",
)
NEXT_SAFE_ACTION = (
    "Resolve the two exact clean checkouts and four body-free private coordinate headers, compile the deterministic "
    "operator card, and return the card for separate named-human review. Do not begin physical execution."
)
WAKE_CONDITION = (
    "The exact conductor and physical-floor checkouts are clean and detached, all four private coordinates are "
    "content-bound without exposing paths or bodies, and the compiled operator card matches the admitted profile."
)
CONTROL_QUESTION = (
    "Does the exact operator card tell the named human what to touch, what to run, what receipt must appear, and what "
    "condition stops the campaign while every action remains unauthorized?"
)


class VerificationError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def fail(code: str, message: str) -> None:
    raise VerificationError(code, message)


def canonical_json_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        fail("NON_CANONICAL_JSON", str(exc))
    return (text + "\n").encode("utf-8")


def type_strict_equal(actual: Any, expected: Any) -> bool:
    return canonical_json_bytes(actual) == canonical_json_bytes(expected)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def content_id(prefix: str, body: dict[str, Any]) -> str:
    return f"{prefix}_{sha256_bytes(canonical_json_bytes(body))}"


def read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail("JSON_READ_FAILED", f"{path}: {exc}")
    if not isinstance(value, dict):
        fail("JSON_OBJECT_REQUIRED", f"{path} must contain one JSON object")
    return value


def exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        fail("OBJECT_KEYS_INVALID", f"{label} missing={sorted(expected - actual)} unknown={sorted(actual - expected)}")


def join_contract_id(profile: dict[str, Any]) -> str:
    body = {
        "schema": PROFILE_SCHEMA,
        "profileId": PROFILE_ID,
        "owningProject": profile["owningProject"],
        "owningRepository": profile["owningRepository"],
        "sourceCoordinates": profile["sourceCoordinates"],
        "physicalFlightIssue": profile["physicalFlightIssue"],
        "phaseSequence": profile["phaseSequence"],
        "flightPlanGates": profile["flightPlanGates"],
        "packetStageSequence": profile["packetStageSequence"],
        "claimBoundary": CLAIM_BOUNDARY,
    }
    return content_id("axmheadphysjoin2", body)


def prepared_state(profile: dict[str, Any]) -> dict[str, Any]:
    basis: dict[str, Any] = {
        "schema": STATE_SCHEMA,
        "profileId": PROFILE_ID,
        "joinContractId": join_contract_id(profile),
        "sourceCoordinates": profile["sourceCoordinates"],
        "physicalFlightIssue": profile["physicalFlightIssue"],
        "checkoutBindings": {},
        "privateCoordinateHeaders": [],
        "physicalExecutionStarted": False,
        "workersLaunched": 0,
        "listenersCreated": 0,
        "authorization": {"granted": False, "actorId": None, "transactionId": None},
        "authority": "none",
    }
    value = {**basis, "preparationBasisId": content_id("axmheadjoinbasis2", basis), "executionCard": None}
    return {**value, "stateId": content_id("axmheadjoinstate2", value)}


def prepared_decision(profile: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema": DECISION_SCHEMA,
        "profileId": PROFILE_ID,
        "joinContractId": join_contract_id(profile),
        "stateId": state["stateId"],
        "executionCardId": None,
        "terminal": "PREPARED_NOT_ARMED",
        "reasonCodes": list(PREPARED_REASON_CODES),
        "nextSafeAction": NEXT_SAFE_ACTION,
        "wakeCondition": WAKE_CONDITION,
        "controlQuestion": CONTROL_QUESTION,
        "errorCode": None,
        "errorMessage": None,
        "physicalAuthorizationProduced": False,
        "physicalExecutionStarted": False,
        "missionVolumeMaterialized": False,
        "workersLaunched": 0,
        "listenersCreated": 0,
        "authority": "none",
        "claimBoundary": CLAIM_BOUNDARY,
    }
    return {**body, "decisionId": content_id("axmheadjoindecision2", body)}


def public_status(profile: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": PUBLIC_SCHEMA,
        "profileId": PROFILE_ID,
        "joinContractId": join_contract_id(profile),
        "stateId": decision["stateId"],
        "decisionId": decision["decisionId"],
        "executionCardId": decision["executionCardId"],
        "terminal": decision["terminal"],
        "reasonCodes": decision["reasonCodes"],
        "nextSafeAction": decision["nextSafeAction"],
        "physicalFlightIssue": profile["physicalFlightIssue"],
        "canonicalCommit": profile["sourceCoordinates"]["admittedAxmHeadSupplier"]["commit"],
        "canonicalTree": profile["sourceCoordinates"]["admittedAxmHeadSupplier"]["tree"],
        "physicalAuthorizationProduced": False,
        "physicalExecutionStarted": False,
        "missionVolumeMaterialized": False,
        "workersLaunched": 0,
        "listenersCreated": 0,
        "physicalEstateQualified": False,
        "representativeOperatorQualified": False,
        "fieldNetworkQualified": False,
        "operationalC2Qualified": False,
        "productionLatticeQualified": False,
        "missionAuthority": "none",
        "commandAuthority": "none",
        "targetingEngagementEffectorWeaponsCapability": False,
        "privateEvidenceBodies": 0,
        "authority": "none",
        "claimBoundary": CLAIM_BOUNDARY,
    }

def validate_profile(profile: dict[str, Any]) -> None:
    if profile.get("schema") != PROFILE_SCHEMA or profile.get("profileId") != PROFILE_ID:
        fail("PROFILE_IDENTITY_INVALID", "profile schema or profileId differs")
    if profile.get("claimBoundary") != CLAIM_BOUNDARY:
        fail("CLAIM_BOUNDARY_INVALID", "profile claimBoundary differs")
    if profile.get("physicalAuthorizationProduced") is not False:
        fail("PROFILE_AUTHORIZATION_INVALID", "profile must not produce physical authorization")
    if profile.get("workersLaunched") != 0 or profile.get("listenersCreated") != 0:
        fail("PROFILE_ACTIVITY_INVALID", "profile workers and listeners must remain zero")
    if profile.get("authority") != "none":
        fail("PROFILE_AUTHORITY_INVALID", "profile authority must remain none")
    digest = sha256_bytes(canonical_json_bytes(profile))
    if digest != PROFILE_CANONICAL_SHA256:
        fail("PROFILE_CANONICAL_DIGEST_INVALID", "profile canonical digest differs from the admitted candidate")


def ensure_output_safe(carrier: Path, out: Path | None) -> None:
    if out is None:
        return
    carrier_resolved = carrier.resolve()
    out_resolved = out.resolve(strict=False)
    if out_resolved == carrier_resolved or carrier_resolved in out_resolved.parents:
        fail("OUTPUT_OVERLAPS_CARRIER", "verdict output may not be inside the measured carrier")
    if out.exists():
        out_stat = out.stat()
        for member in carrier.rglob("*"):
            if member.is_file():
                stat = member.stat()
                if stat.st_dev == out_stat.st_dev and stat.st_ino == out_stat.st_ino:
                    fail("OUTPUT_ALIASES_CARRIER", "verdict output aliases a measured carrier file")


def verify(carrier: Path) -> dict[str, Any]:
    if not carrier.is_dir() or carrier.is_symlink():
        fail("CARRIER_DIRECTORY_INVALID", "carrier must be a non-symlink directory")
    manifest_path = carrier / "MANIFEST.json"
    profile_path = carrier / "RECOVERY" / "profile.json"
    verifier_path = carrier / "RECOVERY" / "verify_join.py"
    state_path = carrier / "JOIN" / "preparation-state.json"
    decision_path = carrier / "JOIN" / "decision.json"
    public_path = carrier / "PUBLIC" / "status.json"
    for path in (manifest_path, profile_path, verifier_path, state_path, decision_path, public_path):
        if not path.is_file() or path.is_symlink():
            fail("CARRIER_MEMBER_INVALID", f"required regular member missing or symlinked: {path.relative_to(carrier).as_posix()}")

    profile = read_object(profile_path)
    validate_profile(profile)
    expected_state = prepared_state(profile)
    expected_decision = prepared_decision(profile, expected_state)
    expected_public = public_status(profile, expected_decision)
    actual_state = read_object(state_path)
    actual_decision = read_object(decision_path)
    actual_public = read_object(public_path)
    if not type_strict_equal(actual_state, expected_state):
        fail("PREPARATION_STATE_MISMATCH", "prepared state is not reconstructed from the admitted profile")
    if not type_strict_equal(actual_decision, expected_decision):
        fail("DECISION_MISMATCH", "decision is not reconstructed from the prepared state")
    if not type_strict_equal(actual_public, expected_public):
        fail("PUBLIC_STATUS_MISMATCH", "public status is not reconstructed from the decision")

    actual_files = sorted(path.relative_to(carrier).as_posix() for path in carrier.rglob("*") if path.is_file())
    expected_all = sorted(("MANIFEST.json", *EXPECTED_RELATIVE_FILES))
    if actual_files != expected_all:
        fail("FILE_DENOMINATOR_INVALID", f"carrier file denominator differs: {actual_files}")

    manifest = read_object(manifest_path)
    exact_keys(
        manifest,
        {
            "schema",
            "profileId",
            "joinContractId",
            "stateId",
            "decisionId",
            "terminal",
            "sourceCoordinates",
            "physicalFlightIssue",
            "profileCanonicalSha256",
            "standaloneVerifierSha256",
            "bootstrapRequired",
            "files",
            "fileCount",
            "physicalAuthorizationProduced",
            "physicalExecutionStarted",
            "missionVolumeMaterialized",
            "workersLaunched",
            "listenersCreated",
            "authority",
            "claimBoundary",
            "carrierId",
        },
        "manifest",
    )
    if manifest["schema"] != MANIFEST_SCHEMA or manifest["profileId"] != PROFILE_ID:
        fail("MANIFEST_IDENTITY_INVALID", "manifest identity differs")
    if manifest["joinContractId"] != join_contract_id(profile):
        fail("MANIFEST_JOIN_ID_INVALID", "manifest joinContractId differs")
    if manifest["stateId"] != expected_state["stateId"] or manifest["decisionId"] != expected_decision["decisionId"]:
        fail("MANIFEST_DECISION_BINDING_INVALID", "manifest state or decision binding differs")
    if manifest["terminal"] != "PREPARED_NOT_ARMED":
        fail("MANIFEST_TERMINAL_INVALID", "carrier terminal must remain PREPARED_NOT_ARMED")
    if not type_strict_equal(manifest["sourceCoordinates"], profile["sourceCoordinates"]) or not type_strict_equal(
        manifest["physicalFlightIssue"], profile["physicalFlightIssue"]
    ):
        fail("MANIFEST_SOURCE_BINDING_INVALID", "manifest source or issue binding differs")
    if manifest["profileCanonicalSha256"] != PROFILE_CANONICAL_SHA256:
        fail("MANIFEST_PROFILE_DIGEST_INVALID", "manifest profile digest differs")
    verifier_digest = sha256_bytes(verifier_path.read_bytes())
    if manifest["standaloneVerifierSha256"] != verifier_digest:
        fail("MANIFEST_VERIFIER_DIGEST_INVALID", "manifest verifier digest differs from embedded bytes")
    if manifest["bootstrapRequired"] is not True:
        fail("MANIFEST_BOOTSTRAP_INVALID", "bootstrapRequired must remain true")
    if type(manifest["fileCount"]) is not int or manifest["fileCount"] != len(EXPECTED_RELATIVE_FILES):
        fail("MANIFEST_FILE_COUNT_INVALID", "manifest fileCount differs")
    rows = manifest["files"]
    if not isinstance(rows, list) or len(rows) != len(EXPECTED_RELATIVE_FILES):
        fail("MANIFEST_FILES_INVALID", "manifest files denominator differs")
    expected_rows = []
    for relative in EXPECTED_RELATIVE_FILES:
        data = (carrier / Path(*relative.split("/"))).read_bytes()
        expected_rows.append({"path": relative, "bytes": len(data), "sha256": sha256_bytes(data)})
    if not type_strict_equal(rows, expected_rows):
        fail("MANIFEST_FILE_ROWS_INVALID", "manifest file rows differ from measured bytes")
    for key, expected in (
        ("physicalAuthorizationProduced", False),
        ("physicalExecutionStarted", False),
        ("missionVolumeMaterialized", False),
        ("workersLaunched", 0),
        ("listenersCreated", 0),
        ("authority", "none"),
        ("claimBoundary", CLAIM_BOUNDARY),
    ):
        if not type_strict_equal(manifest[key], expected):
            fail("MANIFEST_NONCLAIM_INVALID", f"manifest {key} differs")
    body = dict(manifest)
    carrier_id = body.pop("carrierId")
    if carrier_id != content_id("axmheadjoincarrier2", body):
        fail("CARRIER_ID_INVALID", "carrierId does not bind the complete manifest")

    return {
        "schema": VERDICT_SCHEMA,
        "status": "PASS",
        "carrierId": carrier_id,
        "joinContractId": manifest["joinContractId"],
        "stateId": manifest["stateId"],
        "decisionId": manifest["decisionId"],
        "terminal": "PREPARED_NOT_ARMED",
        "fileCount": len(EXPECTED_RELATIVE_FILES),
        "profileCanonicalSha256": PROFILE_CANONICAL_SHA256,
        "standaloneVerifierSha256": verifier_digest,
        "bootstrapAuthenticated": False,
        "physicalAuthorizationProduced": False,
        "physicalExecutionStarted": False,
        "missionVolumeMaterialized": False,
        "workersLaunched": 0,
        "listenersCreated": 0,
        "authority": "none",
    }


def emit(value: dict[str, Any], out: Path | None) -> None:
    data = canonical_json_bytes(value)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
    sys.stdout.buffer.write(data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify one AXM HEAD physical long-haul JOIN-v2 carrier")
    parser.add_argument("carrier", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        ensure_output_safe(args.carrier, args.out)
        verdict = verify(args.carrier)
        emit(verdict, args.out)
        return 0
    except VerificationError as exc:
        refused = {
            "schema": VERDICT_SCHEMA,
            "status": "REFUSED",
            "code": exc.code,
            "message": str(exc),
            "bootstrapAuthenticated": os.environ.get("AXM_HEAD_JOIN_V2_BOOTSTRAP_AUTHENTICATED") == "1",
            "physicalAuthorizationProduced": False,
            "physicalExecutionStarted": False,
            "workersLaunched": 0,
            "listenersCreated": 0,
            "authority": "none",
        }
        emit(refused, None)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
