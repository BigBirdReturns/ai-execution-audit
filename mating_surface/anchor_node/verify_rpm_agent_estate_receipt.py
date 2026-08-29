from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

PROFILE_SCHEMA = "rpm-agent-estate-profile/1"
PROFILE_ID = "rpm-agent/evidence-membrane/0.1"
RECEIPT_SCHEMA = "rpm-agent/estate-qualification-receipt@1"
PUBLIC_STATUS_SCHEMA = "rpm-agent/estate-public-status@1"
VERIFICATION_SCHEMA = "rpm-agent/estate-receipt-verification@1"
TERMINALS = ("READY_FOR_RUNTIME_QUALIFICATION", "HARDENING_REQUIRED", "REFUSED")
SEVERITIES = ("HOLD", "REFUSE")
EFFECT_CLASSES = ("SIMULATED", "OBSERVED", "REQUESTED", "ACKNOWLEDGED", "REFUSED")
TOOL_OPERATIONS = (
    "verify_identity",
    "check_device_status",
    "pair_device",
    "start_measurement",
    "troubleshoot_step",
    "escalate_to_nurse",
)
EXTERNAL_EFFECT_OPERATIONS = (
    "verify_identity",
    "pair_device",
    "escalate_to_nurse",
)
REQUIRED_DEVICES = (
    "bp_device",
    "pulse_oximeter",
    "scale",
    "thermometer",
)
TELEMETRY_SOURCES = (
    "DEVICE_OBSERVED",
    "PATIENT_REPORTED",
    "SIMULATED",
    "MODEL_DERIVED",
)
EXPECTED_PROFILE_KEYS = {
    "schema",
    "profileId",
    "status",
    "sourceCoordinate",
    "criticalGitBlobs",
    "referenceArtifacts",
    "objectSchemas",
    "effectClasses",
    "toolOperations",
    "externalEffectOperations",
    "requiredDevices",
    "telemetrySources",
    "terminalStates",
    "gates",
    "declaredSafetyPredicates",
    "expectedCurrentAssessment",
    "claimBoundary",
}
_HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_RECEIPT_ID_RE = re.compile(r"^rpmqual1_[0-9a-f]{64}$")


class VerificationError(RuntimeError):
    pass


def canonical_json_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise VerificationError(f"value is not canonical JSON: {exc}") from exc
    return (text + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"unable to read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise VerificationError(f"{path} must contain one JSON object")
    return value


def require_exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise VerificationError(
            f"{label} keys differ: missing={sorted(expected - actual)} "
            f"unknown={sorted(actual - expected)}"
        )


def require_safe_repo_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise VerificationError(f"{label} must be a non-empty string")
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if (
        posix.is_absolute()
        or not posix.parts
        or ".." in posix.parts
        or "\\" in value
        or windows.is_absolute()
        or bool(windows.drive)
    ):
        raise VerificationError(f"{label} must be a safe repository-relative path")
    return value


def derive_terminal(findings: list[dict[str, Any]]) -> str:
    severities = [finding["severity"] for finding in findings]
    if "REFUSE" in severities:
        return "REFUSED"
    if "HOLD" in severities:
        return "HARDENING_REQUIRED"
    return "READY_FOR_RUNTIME_QUALIFICATION"


def validate_profile(profile: dict[str, Any]) -> None:
    require_exact_keys(profile, EXPECTED_PROFILE_KEYS, "profile")
    if profile.get("schema") != PROFILE_SCHEMA or profile.get("profileId") != PROFILE_ID:
        raise VerificationError("profile identity differs")
    if profile.get("status") != "candidate_contract_only":
        raise VerificationError("profile status differs")
    source = profile.get("sourceCoordinate")
    if not isinstance(source, dict):
        raise VerificationError("profile sourceCoordinate is invalid")
    if set(source) != {"repository", "commit", "tree", "status"}:
        raise VerificationError("profile sourceCoordinate keys differ")
    if _HEX40_RE.fullmatch(str(source.get("commit", ""))) is None:
        raise VerificationError("profile commit is invalid")
    if _HEX40_RE.fullmatch(str(source.get("tree", ""))) is None:
        raise VerificationError("profile tree is invalid")
    critical = profile.get("criticalGitBlobs")
    if not isinstance(critical, dict) or not critical:
        raise VerificationError("profile criticalGitBlobs is invalid")
    for path, digest in critical.items():
        require_safe_repo_path(path, "profile criticalGitBlobs path")
        if _HEX40_RE.fullmatch(str(digest)) is None:
            raise VerificationError(f"profile critical blob digest is invalid for {path}")
    references = profile.get("referenceArtifacts")
    if not isinstance(references, dict) or not references:
        raise VerificationError("profile referenceArtifacts is invalid")
    for path, digest in references.items():
        require_safe_repo_path(path, "profile referenceArtifacts path")
        if _HEX64_RE.fullmatch(str(digest)) is None:
            raise VerificationError(f"profile reference digest is invalid for {path}")
    if profile.get("effectClasses") != list(EFFECT_CLASSES):
        raise VerificationError("profile effect class denominator differs")
    object_schemas = profile.get("objectSchemas")
    if (
        not isinstance(object_schemas, list)
        or not object_schemas
        or len(object_schemas) != len(set(object_schemas))
        or any(not isinstance(item, str) or not item for item in object_schemas)
    ):
        raise VerificationError("profile objectSchemas is invalid")
    if profile.get("toolOperations") != list(TOOL_OPERATIONS):
        raise VerificationError("profile tool operation denominator differs")
    if profile.get("externalEffectOperations") != list(EXTERNAL_EFFECT_OPERATIONS):
        raise VerificationError("profile external effect denominator differs")
    if profile.get("requiredDevices") != list(REQUIRED_DEVICES):
        raise VerificationError("profile required-device denominator differs")
    if profile.get("telemetrySources") != list(TELEMETRY_SOURCES):
        raise VerificationError("profile telemetry-source denominator differs")
    if profile.get("terminalStates") != list(TERMINALS):
        raise VerificationError("profile terminal denominator differs")
    predicates = profile.get("declaredSafetyPredicates")
    if (
        not isinstance(predicates, list)
        or not predicates
        or predicates != sorted(predicates)
        or len(predicates) != len(set(predicates))
        or any(not isinstance(item, str) or not item for item in predicates)
    ):
        raise VerificationError("profile safety predicate denominator is invalid")
    if not isinstance(profile.get("claimBoundary"), str) or not profile["claimBoundary"]:
        raise VerificationError("profile claimBoundary is invalid")


def validate_finding(finding: dict[str, Any], index: int) -> None:
    require_exact_keys(
        finding,
        {"gate", "code", "severity", "path", "evidence", "requiredAction"},
        f"findings[{index}]",
    )
    for key in ("gate", "code", "path", "evidence", "requiredAction"):
        if not isinstance(finding[key], str) or not finding[key]:
            raise VerificationError(f"findings[{index}].{key} must be a non-empty string")
    if finding["severity"] not in SEVERITIES:
        raise VerificationError(f"findings[{index}].severity is invalid")


def verify_receipt(profile: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    validate_profile(profile)
    require_exact_keys(
        receipt,
        {
            "receiptId",
            "schema",
            "profileId",
            "source",
            "terminal",
            "findings",
            "claims",
            "publicStatus",
            "claimBoundary",
        },
        "receipt",
    )
    if receipt["schema"] != RECEIPT_SCHEMA or receipt["profileId"] != PROFILE_ID:
        raise VerificationError("receipt identity differs")
    if _RECEIPT_ID_RE.fullmatch(str(receipt["receiptId"])) is None:
        raise VerificationError("receiptId syntax is invalid")
    if receipt["claimBoundary"] != profile["claimBoundary"]:
        raise VerificationError("receipt claimBoundary differs from the profile")

    source = receipt["source"]
    if not isinstance(source, dict):
        raise VerificationError("source must be an object")
    require_exact_keys(
        source,
        {
            "repository",
            "commit",
            "tree",
            "criticalGitBlobs",
            "materialization",
            "workingTreeRead",
            "executed",
            "patientDataProcessed",
        },
        "source",
    )
    profile_source = profile["sourceCoordinate"]
    for key in ("repository", "commit", "tree"):
        if source[key] != profile_source[key]:
            raise VerificationError(f"source.{key} differs from the frozen profile")
    if source["criticalGitBlobs"] != dict(sorted(profile["criticalGitBlobs"].items())):
        raise VerificationError("source criticalGitBlobs differ from the frozen profile")
    if source["materialization"] != "exact_git_blob_bytes":
        raise VerificationError("source materialization must remain exact_git_blob_bytes")
    if source["workingTreeRead"] is not False:
        raise VerificationError("semantic qualification cannot read mutable working-tree bytes")
    if source["executed"] is not False or source["patientDataProcessed"] is not False:
        raise VerificationError("static qualification cannot execute source or process patient data")

    findings = receipt["findings"]
    if not isinstance(findings, list):
        raise VerificationError("findings must be a list")
    for index, finding in enumerate(findings):
        if not isinstance(finding, dict):
            raise VerificationError(f"findings[{index}] must be an object")
        validate_finding(finding, index)
    sort_key = lambda item: (item["code"], item["path"], item["evidence"])
    if findings != sorted(findings, key=sort_key):
        raise VerificationError("findings are not in canonical order")
    if len({(item["code"], item["path"], item["evidence"]) for item in findings}) != len(findings):
        raise VerificationError("findings contain duplicate witnesses")

    derived_terminal = derive_terminal(findings)
    if receipt["terminal"] != derived_terminal:
        raise VerificationError("stored terminal differs from independently derived terminal")

    claims = receipt["claims"]
    if not isinstance(claims, dict):
        raise VerificationError("claims must be an object")
    require_exact_keys(
        claims,
        {
            "controlPlaneStructurallyReady",
            "controlPlaneQualified",
            "clinicalSafetyQualified",
            "clinicalEfficacyQualified",
            "externalEffectsObserved",
            "runtimeCampaignExecuted",
            "physicalEstateQualified",
            "authority",
        },
        "claims",
    )
    expected_claims = {
        "controlPlaneStructurallyReady": derived_terminal == "READY_FOR_RUNTIME_QUALIFICATION",
        "controlPlaneQualified": False,
        "clinicalSafetyQualified": False,
        "clinicalEfficacyQualified": False,
        "externalEffectsObserved": False,
        "runtimeCampaignExecuted": False,
        "physicalEstateQualified": False,
        "authority": "none",
    }
    if claims != expected_claims:
        raise VerificationError("claims differ from the terminal and static claim boundary")

    status = receipt["publicStatus"]
    if not isinstance(status, dict):
        raise VerificationError("publicStatus must be an object")
    require_exact_keys(
        status,
        {
            "schema",
            "profileId",
            "terminal",
            "findingCodes",
            "sourceExecuted",
            "patientDataProcessed",
            "controlPlaneStructurallyReady",
            "runtimeQualificationRequired",
            "clinicalSafetyQualified",
            "authority",
        },
        "publicStatus",
    )
    expected_status = {
        "schema": PUBLIC_STATUS_SCHEMA,
        "profileId": PROFILE_ID,
        "terminal": derived_terminal,
        "findingCodes": [finding["code"] for finding in findings],
        "sourceExecuted": False,
        "patientDataProcessed": False,
        "controlPlaneStructurallyReady": derived_terminal == "READY_FOR_RUNTIME_QUALIFICATION",
        "runtimeQualificationRequired": True,
        "clinicalSafetyQualified": False,
        "authority": "none",
    }
    if status != expected_status:
        raise VerificationError("publicStatus differs from independently reconstructed projection")

    body = {key: value for key, value in receipt.items() if key != "receiptId"}
    expected_receipt_id = f"rpmqual1_{sha256_bytes(canonical_json_bytes(body))}"
    if receipt["receiptId"] != expected_receipt_id:
        raise VerificationError("receiptId differs from canonical receipt body")

    verification_body = {
        "schema": VERIFICATION_SCHEMA,
        "profileId": PROFILE_ID,
        "receiptId": receipt["receiptId"],
        "terminal": derived_terminal,
        "findingCodes": [finding["code"] for finding in findings],
        "verified": True,
        "sourceExecuted": False,
        "patientDataProcessed": False,
        "controlPlaneStructurallyReady": derived_terminal == "READY_FOR_RUNTIME_QUALIFICATION",
        "controlPlaneQualified": False,
        "runtimeQualificationRequired": True,
        "clinicalSafetyQualified": False,
        "authority": "none",
    }
    verification_body["verificationId"] = (
        f"rpmverification1_{sha256_bytes(canonical_json_bytes(verification_body))}"
    )
    return verification_body


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify one RPM-Agent Estate qualification receipt.")
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        profile = read_json(args.profile.resolve())
        receipt = read_json(args.receipt.resolve())
        result = verify_receipt(profile, receipt)
        data = canonical_json_bytes(result)
        if args.out is not None:
            args.out.resolve().parent.mkdir(parents=True, exist_ok=True)
            args.out.resolve().write_bytes(data)
        sys.stdout.buffer.write(data)
        return 0
    except VerificationError as exc:
        print(f"verification refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
