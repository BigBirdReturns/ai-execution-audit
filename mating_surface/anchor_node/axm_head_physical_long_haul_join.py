from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPOSITORY_ROOT = HERE.parents[1]
VERIFIER_SOURCE = HERE / "verify_axm_head_physical_long_haul_join.py"
PROFILE_CANONICAL_SHA256 = "99395d94b8c08ed3ed9459fa1793dfc9a9436c21af60de1fea356808eb6db657"
FIXTURE_CATALOG_CANONICAL_SHA256 = "12a6bdcb406e83c964d229d0f2b3a30e39026f88440a34ff17586f057b234a62"
STANDALONE_VERIFIER_SHA256 = "14340e6e9c54394be1e057dd928f10b3079c668acbdf7a3bdcf81fec45ec9861"

spec = importlib.util.spec_from_file_location("join_v2_verifier_core", VERIFIER_SOURCE)
if spec is None or spec.loader is None:
    raise RuntimeError("unable to load JOIN-v2 verifier core")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)

PROFILE_SCHEMA = core.PROFILE_SCHEMA
PROFILE_ID = core.PROFILE_ID
FIXTURE_SCHEMA = core.FIXTURE_SCHEMA
INPUT_SCHEMA = core.INPUT_SCHEMA
MANIFEST_SCHEMA = core.MANIFEST_SCHEMA
EXPECTED_MEMBER_PATHS = core.EXPECTED_MEMBER_PATHS
STRONGER_CLAIMS = core.STRONGER_CLAIMS
CLAIM_BOUNDARY = core.CLAIM_BOUNDARY
JoinError = core.JoinError
canonical_json_bytes = core.canonical_json_bytes
sha256_bytes = core.sha256_bytes
content_id = core.content_id
load_trust_root = core.load_trust_root


def fail(code: str, message: str = "") -> None:
    raise JoinError(code, message)


def read_json(path: Path) -> dict[str, Any]:
    return core.read_json(path)


def validate_exact_profile(path: Path) -> dict[str, Any]:
    profile = read_json(path)
    core.validate_profile_object(profile)
    if path.read_bytes() != canonical_json_bytes(profile):
        fail("PROFILE_NONCANONICAL_BYTES")
    if sha256_bytes(canonical_json_bytes(profile)) != PROFILE_CANONICAL_SHA256:
        fail("PROFILE_CANONICAL_DIGEST_INVALID")
    if profile["fixtureCatalogCanonicalSha256"] != FIXTURE_CATALOG_CANONICAL_SHA256:
        fail("PROFILE_FIXTURE_DIGEST_INVALID")
    if profile["standaloneVerifierSha256"] != STANDALONE_VERIFIER_SHA256:
        fail("PROFILE_VERIFIER_DIGEST_INVALID")
    return profile


def validate_exact_catalog(
    profile: dict[str, Any], path: Path
) -> dict[str, Any]:
    catalog = read_json(path)
    core.validate_catalog_object(profile, catalog)
    if path.read_bytes() != canonical_json_bytes(catalog):
        fail("FIXTURE_NONCANONICAL_BYTES")
    if sha256_bytes(canonical_json_bytes(catalog)) != FIXTURE_CATALOG_CANONICAL_SHA256:
        fail("FIXTURE_CATALOG_DIGEST_INVALID")
    return catalog


def find_case(catalog: dict[str, Any], case_id: str) -> dict[str, Any]:
    for row in catalog["cases"]:
        if row["caseId"] == case_id:
            return row
    fail("FIXTURE_CASE_NOT_FOUND", case_id)


def write_carrier(
    profile: dict[str, Any],
    catalog: dict[str, Any],
    input_value: dict[str, Any],
    out: Path,
    trust: tuple[bytes, str] | None = None,
    allow_synthetic: bool = True,
) -> dict[str, Any]:
    if out.exists():
        fail("OUTPUT_ALREADY_EXISTS")
    objects = core.build_objects(
        profile,
        input_value,
        trust=trust,
        allow_synthetic=allow_synthetic,
    )
    verifier_bytes = VERIFIER_SOURCE.read_bytes()
    if sha256_bytes(verifier_bytes) != STANDALONE_VERIFIER_SHA256:
        fail("VERIFIER_SOURCE_DIGEST_INVALID")
    members = {
        "JOIN/source-binding.json": canonical_json_bytes(objects["source"]),
        "JOIN/route-attestation.json": canonical_json_bytes(objects["route"]),
        "JOIN/continuity-attestation.json": canonical_json_bytes(objects["continuity"]),
        "JOIN/two-cell-attestation.json": canonical_json_bytes(objects["twoCell"]),
        "JOIN/successor-attestation.json": canonical_json_bytes(objects["successor"]),
        "JOIN/private-disposition-binding.json": canonical_json_bytes(
            objects["disposition"]
        ),
        "JOIN/join.json": canonical_json_bytes(objects["join"]),
        "PUBLIC/status.json": canonical_json_bytes(objects["public"]),
        "RECOVERY/profile.json": canonical_json_bytes(profile),
        "RECOVERY/fixture-catalog.json": canonical_json_bytes(catalog),
        "RECOVERY/verify_join.py": verifier_bytes,
    }
    rows = [
        {"path": rel, "size": len(data), "sha256": sha256_bytes(data)}
        for rel, data in sorted(members.items())
    ]
    terminal = objects["join"]["terminal"]
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "profileId": PROFILE_ID,
        "carrierId": None,
        "terminal": terminal,
        "joinId": objects["join"]["joinId"],
        "sourceBindingId": objects["source"]["sourceBindingId"],
        "publicStatusId": objects["public"]["publicStatusId"],
        "trustRootSha256": trust[1]
        if terminal == "PRIVATE_SELF_ATTESTED" and trust is not None
        else None,
        "files": rows,
        "bindings": {
            "profileCanonicalSha256": PROFILE_CANONICAL_SHA256,
            "fixtureCatalogCanonicalSha256": FIXTURE_CATALOG_CANONICAL_SHA256,
            "standaloneVerifierSha256": STANDALONE_VERIFIER_SHA256,
        },
        "nonClaims": {
            "physicalExecutionStartedByJoin": False,
            "missionVolumeMaterializedByJoin": False,
            "issue37LedgerAdvancedByJoin": False,
            "workersLaunched": 0,
            "listenersCreated": 0,
            "publicEvidenceBodies": 0,
            "strongerClaims": copy.deepcopy(STRONGER_CLAIMS),
            "authority": "none",
        },
    }
    manifest["carrierId"] = content_id(
        "axmheadphysicallonghaulcarrier2",
        {key: value for key, value in manifest.items() if key != "carrierId"},
    )
    out.mkdir(parents=True, exist_ok=False)
    for rel, data in members.items():
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (out / "MANIFEST.json").write_bytes(canonical_json_bytes(manifest))
    return {
        "schema": "axm-head/physical-long-haul-build@2",
        "status": "PASS",
        "terminal": terminal,
        "carrierId": manifest["carrierId"],
        "joinId": objects["join"]["joinId"],
        "publicStatusId": objects["public"]["publicStatusId"],
        "trustRootBound": terminal == "PRIVATE_SELF_ATTESTED",
        "authoritativeFiles": len(members),
        "privatePhysicalFlightCompleted": terminal == "PRIVATE_SELF_ATTESTED",
        "physicalExecutionStartedByJoin": False,
        "missionVolumeMaterializedByJoin": False,
        "issue37LedgerAdvancedByJoin": False,
        "workersLaunched": 0,
        "listenersCreated": 0,
        "authority": "none",
    }


def path_overlaps(root: Path, out: Path) -> bool:
    resolved_root = root.resolve()
    candidate = out.resolve(strict=False)
    if candidate == resolved_root or resolved_root in candidate.parents:
        return True
    if candidate.exists():
        candidate_stat = candidate.stat()
        for path in resolved_root.rglob("*"):
            if path.is_file() and not path.is_symlink():
                path_stat = path.stat()
                if (
                    path_stat.st_dev == candidate_stat.st_dev
                    and path_stat.st_ino == candidate_stat.st_ino
                ):
                    return True
    return False


def measured_carrier_bytes(carrier: Path) -> dict[str, bytes]:
    carrier = carrier.resolve()
    if not carrier.is_dir():
        fail("CARRIER_DIRECTORY_REQUIRED")
    expected = ["MANIFEST.json", *EXPECTED_MEMBER_PATHS]
    observed: list[str] = []
    for path in carrier.rglob("*"):
        if path.is_symlink():
            fail("SYMLINK_MEMBER_REFUSED")
        if path.is_file():
            observed.append(path.relative_to(carrier).as_posix())
    if sorted(observed) != sorted(expected):
        fail("FILE_DENOMINATOR_INVALID")
    measured: dict[str, bytes] = {}
    for rel in expected:
        path = carrier / rel
        before = path.stat()
        data = path.read_bytes()
        after = path.stat()
        if (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ):
            fail("MUTABLE_CARRIER_RACE_REFUSED", rel)
        if before.st_size != len(data):
            fail("MUTABLE_CARRIER_RACE_REFUSED", rel)
        measured[rel] = data
    return measured


def bootstrap_verify(
    carrier: Path,
    out: Path | None,
    trust_root: Path | None = None,
) -> dict[str, Any]:
    carrier = carrier.resolve()
    if out is not None:
        repository = REPOSITORY_ROOT.resolve()
        candidate = out.resolve(strict=False)
        if candidate == repository or repository in candidate.parents:
            fail("REPOSITORY_OUTPUT_REFUSED")
        if path_overlaps(carrier, out):
            fail("VERDICT_OUTPUT_OVERLAP_REFUSED")
    measured = measured_carrier_bytes(carrier)
    profile_bytes = measured["RECOVERY/profile.json"]
    catalog_bytes = measured["RECOVERY/fixture-catalog.json"]
    verifier_bytes = measured["RECOVERY/verify_join.py"]
    try:
        profile_value = json.loads(profile_bytes.decode("utf-8"))
        catalog_value = json.loads(catalog_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        fail("BOOTSTRAP_SOURCE_AUTHENTICATION_FAILED")
    if profile_bytes != canonical_json_bytes(profile_value):
        fail("BOOTSTRAP_SOURCE_AUTHENTICATION_FAILED")
    if catalog_bytes != canonical_json_bytes(catalog_value):
        fail("BOOTSTRAP_SOURCE_AUTHENTICATION_FAILED")
    if sha256_bytes(profile_bytes) != PROFILE_CANONICAL_SHA256:
        fail("BOOTSTRAP_SOURCE_AUTHENTICATION_FAILED")
    if sha256_bytes(catalog_bytes) != FIXTURE_CATALOG_CANONICAL_SHA256:
        fail("BOOTSTRAP_SOURCE_AUTHENTICATION_FAILED")
    if sha256_bytes(verifier_bytes) != STANDALONE_VERIFIER_SHA256:
        fail("BOOTSTRAP_SOURCE_AUTHENTICATION_FAILED")
    if trust_root is not None:
        load_trust_root(trust_root)
    with tempfile.TemporaryDirectory(prefix="axm-head-join-v2-snapshot-") as tmp:
        snapshot = Path(tmp) / "carrier"
        for rel, data in measured.items():
            target = snapshot / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        verifier = snapshot / "RECOVERY/verify_join.py"
        command = [sys.executable, str(verifier), str(snapshot)]
        if trust_root is not None:
            command.extend(["--trust-root", str(trust_root.resolve(strict=True))])
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.upper().startswith("AXM_")
        }
        result = subprocess.run(
            command,
            cwd=tmp,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    try:
        direct = json.loads(result.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        fail("DIRECT_VERDICT_INVALID")
    if result.returncode != 0 or direct.get("status") != "PASS":
        fail("DIRECT_VERIFICATION_FAILED", str(direct.get("errorCode", "unknown")))
    if direct.get("bootstrapAuthenticated") is not False:
        fail("DIRECT_VERDICT_INVALID")
    authenticated = copy.deepcopy(direct)
    authenticated["bootstrapAuthenticated"] = True
    authenticated["bootstrapVerifierSha256"] = STANDALONE_VERIFIER_SHA256
    authenticated["bootstrapProfileSha256"] = PROFILE_CANONICAL_SHA256
    data = canonical_json_bytes(authenticated)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
    return authenticated


def emit(value: dict[str, Any]) -> None:
    sys.stdout.buffer.write(canonical_json_bytes(value))


def refusal(exc: JoinError) -> dict[str, Any]:
    return core.refusal(exc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("validate-profile")
    command.add_argument("profile", type=Path)
    command = sub.add_parser("validate-fixtures")
    command.add_argument("profile", type=Path)
    command.add_argument("fixtures", type=Path)
    command = sub.add_parser("evaluate-fixture")
    command.add_argument("profile", type=Path)
    command.add_argument("fixtures", type=Path)
    command.add_argument("case")
    command = sub.add_parser("build-fixture")
    command.add_argument("profile", type=Path)
    command.add_argument("fixtures", type=Path)
    command.add_argument("case")
    command.add_argument("--out", type=Path, required=True)
    command = sub.add_parser("build-private")
    command.add_argument("profile", type=Path)
    command.add_argument("fixtures", type=Path)
    command.add_argument("input", type=Path)
    command.add_argument("--trust-root", type=Path, required=True)
    command.add_argument("--out", type=Path, required=True)
    command = sub.add_parser("verify-join")
    command.add_argument("carrier", type=Path)
    command.add_argument("--trust-root", type=Path)
    command.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate-profile":
            profile = validate_exact_profile(args.profile)
            emit(
                {
                    "schema": "axm-head/physical-long-haul-profile-validation@2",
                    "status": "PASS",
                    "profileId": profile["profileId"],
                    "profileCanonicalSha256": PROFILE_CANONICAL_SHA256,
                    "privateTrustRootRequiredForPromotion": True,
                    "physicalExecutionStartedByJoin": False,
                    "workersLaunched": 0,
                    "listenersCreated": 0,
                    "authority": "none",
                }
            )
        elif args.command == "validate-fixtures":
            profile = validate_exact_profile(args.profile)
            catalog = validate_exact_catalog(profile, args.fixtures)
            emit(
                {
                    "schema": "axm-head/physical-long-haul-fixture-validation@2",
                    "status": "PASS",
                    "cases": len(catalog["cases"]),
                    "fixtureCatalogCanonicalSha256": FIXTURE_CATALOG_CANONICAL_SHA256,
                    "privateSelfAttestedFixtures": 0,
                    "privatePhysicalFlightCompletedFixtures": 0,
                    "authority": "none",
                }
            )
        elif args.command == "evaluate-fixture":
            profile = validate_exact_profile(args.profile)
            catalog = validate_exact_catalog(profile, args.fixtures)
            row = find_case(catalog, args.case)
            objects = core.build_objects(
                profile, row["input"], trust=None, allow_synthetic=True
            )
            emit(objects["public"])
        elif args.command == "build-fixture":
            profile = validate_exact_profile(args.profile)
            catalog = validate_exact_catalog(profile, args.fixtures)
            row = find_case(catalog, args.case)
            result = write_carrier(
                profile,
                catalog,
                row["input"],
                args.out,
                trust=None,
                allow_synthetic=True,
            )
            emit(result)
        elif args.command == "build-private":
            profile = validate_exact_profile(args.profile)
            catalog = validate_exact_catalog(profile, args.fixtures)
            trust = load_trust_root(args.trust_root)
            if trust is None:
                fail("TRUST_ROOT_REQUIRED")
            input_value = read_json(args.input)
            result = write_carrier(
                profile,
                catalog,
                input_value,
                args.out,
                trust=trust,
                allow_synthetic=False,
            )
            emit(result)
        elif args.command == "verify-join":
            receipt = bootstrap_verify(args.carrier, args.out, args.trust_root)
            emit(receipt)
        return 0
    except JoinError as exc:
        emit(refusal(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
