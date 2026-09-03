#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

EXPECTED_RELEASE = "AXM-Issue-105-Browser-Physical-Audition-Flight-Package-03-Release.zip"
EXPECTED_RELEASE_BYTES = 3_438_484
EXPECTED_RELEASE_SHA256 = "884630ee32a75545373bc88b725c976cc1e61bffd240315a14afea81c20e6d09"
EXPECTED_MAIN = "3c11dbca48ae777137675bb9bf485f0c42daf7a4"
EXPECTED_TREE = "5f30f024b13be3becc5d81c970927004ab0cac31"
EXPECTED_RELEASE_ID = "axmbrowserphysicalflightrelease_48bded1a98f703e2a044765bcd786b82eb9c097c26a43bc420945f97f074e566"
EXPECTED_TRANSACTION = "axmbrowserphysicalrun_b90f76feb0a7324dac7fbd8780a7079a8123c85cdf4a06233467e675803722dc"
SHA_REF = re.compile(r"^sha256:[0-9a-f]{64}$")
ZERO = {
    "browserSeatsPhysicallyOperated": 0,
    "browserLaunched": False,
    "supplierEndpointContacted": False,
    "modelDownloadedByThisTransaction": False,
    "rangeShardsDownloaded": 0,
    "peerConnectionFormed": False,
    "inferenceExecuted": False,
    "physicalMemberEvidenceAccepted": 0,
    "rawCapturesAccepted": 0,
    "namedHumanConfirmationSupplied": False,
    "routeTerminalProduced": False,
    "actualSupplierQualified": False,
    "physicalEstateQualified": False,
    "physicalUniquenessProved": False,
    "missionAuthority": "none",
    "commandAuthority": "none",
}


class Refusal(RuntimeError):
    pass


def load(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise Refusal(f"MEMBER_MISSING_OR_LINKED:{path.name}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise Refusal(f"JSON_INVALID:{path.name}") from exc
    if not isinstance(value, dict):
        raise Refusal(f"JSON_ROOT_INVALID:{path.name}")
    return value


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def require_zero(value: dict[str, Any], label: str) -> None:
    for key, expected in ZERO.items():
        if value.get(key) != expected:
            raise Refusal(f"BOUNDARY_WIDENED:{label}:{key}")


def safe_extract(archive: Path, destination: Path) -> Path:
    with zipfile.ZipFile(archive) as zf:
        seen: set[str] = set()
        for info in zf.infolist():
            pure = PurePosixPath(info.filename)
            if (
                not info.filename
                or pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or info.filename in seen
                or (info.external_attr >> 16) & 0o170000 == 0o120000
            ):
                raise Refusal(f"ARCHIVE_MEMBER_UNSAFE:{info.filename}")
            seen.add(info.filename)
        zf.extractall(destination)
    roots = [p for p in destination.iterdir() if p.is_dir()]
    if len(roots) != 1:
        raise Refusal("ARCHIVE_ROOT_DENOMINATOR_INVALID")
    return roots[0]


def verify(root: Path) -> dict[str, Any]:
    root = root.resolve()
    package = load(root / "PACKAGE.json")
    join = load(root / "ISSUE105-CURRENT-IDENTITY-JOIN.json")
    retirement = load(root / "DISPOSABLE-REF-RETIREMENT.json")
    if package.get("status") != "READY_FOR_TWO_HOST_PREPARATION":
        raise Refusal("PACKAGE_STATE_INVALID")
    package_identity = package.get("identityBody")
    if not isinstance(package_identity, dict):
        raise Refusal("PACKAGE_IDENTITY_BODY_INVALID")
    if package.get("packetId") != "axmissue105currentrejoinpacket_" + hashlib.sha256(canonical(package_identity)).hexdigest():
        raise Refusal("PACKAGE_IDENTITY_INVALID")
    if join.get("status") != "PASS" or join.get("identityJoinId") != package.get("identityJoinId"):
        raise Refusal("IDENTITY_JOIN_INVALID")
    body = join.get("identityBody")
    if not isinstance(body, dict):
        raise Refusal("IDENTITY_BODY_INVALID")
    if join.get("identityJoinId") != "axmissue105currentidentityjoin_" + hashlib.sha256(canonical(body)).hexdigest():
        raise Refusal("IDENTITY_JOIN_ID_INVALID")
    repository = body.get("repository", {})
    carrier = body.get("privateCarrier", {})
    if repository.get("mainCommit") != EXPECTED_MAIN or repository.get("mainTree") != EXPECTED_TREE:
        raise Refusal("REPOSITORY_FLOOR_INVALID")
    if carrier.get("releaseId") != EXPECTED_RELEASE_ID or carrier.get("preparedTransactionId") != EXPECTED_TRANSACTION:
        raise Refusal("PRIVATE_CARRIER_IDENTITY_INVALID")
    if retirement.get("status") != "STALE_DO_NOT_EXECUTE" or retirement.get("remoteRefsDeleted") is not False:
        raise Refusal("DISPOSABLE_REF_RETIREMENT_INVALID")
    require_zero(package.get("claimBoundary", {}), "PACKAGE")
    require_zero(join.get("claimBoundary", {}), "IDENTITY_JOIN")
    require_zero(retirement.get("claimBoundary", {}), "RETIREMENT")

    expected: dict[str, str] = {}
    checksum_path = root / "SHA256SUMS.txt"
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        parts = line.split("  ", 1)
        if len(parts) != 2 or not re.fullmatch(r"[0-9a-f]{64}", parts[0]):
            raise Refusal("CHECKSUM_LINE_INVALID")
        rel = PurePosixPath(parts[1])
        if rel.is_absolute() or ".." in rel.parts or "\\" in parts[1] or parts[1] in expected:
            raise Refusal("CHECKSUM_PATH_INVALID")
        expected[parts[1]] = parts[0]
    actual = {
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() and p.name != "SHA256SUMS.txt"
    }
    if actual != set(expected):
        raise Refusal("CHECKSUM_DENOMINATOR_INVALID")
    for rel, wanted in expected.items():
        path = root / rel
        if path.is_symlink() or digest(path) != wanted:
            raise Refusal(f"CHECKSUM_MISMATCH:{rel}")
    declared_members = package_identity.get("members")
    if not isinstance(declared_members, list):
        raise Refusal("PACKAGE_MEMBER_LEDGER_INVALID")
    declared = {
        row.get("path"): (row.get("bytes"), row.get("sha256"))
        for row in declared_members
        if isinstance(row, dict)
    }
    payload = actual - {"PACKAGE.json"}
    if set(declared) != payload:
        raise Refusal("PACKAGE_MEMBER_DENOMINATOR_INVALID")
    for rel in payload:
        path = root / rel
        if declared[rel] != (path.stat().st_size, "sha256:" + digest(path)):
            raise Refusal(f"PACKAGE_MEMBER_IDENTITY_INVALID:{rel}")

    release_archive = root / EXPECTED_RELEASE
    if release_archive.stat().st_size != EXPECTED_RELEASE_BYTES or digest(release_archive) != EXPECTED_RELEASE_SHA256:
        raise Refusal("RELEASE_ARCHIVE_INVALID")
    with tempfile.TemporaryDirectory(prefix="issue105-current-release-") as temporary:
        release_root = safe_extract(release_archive, Path(temporary))
        completed = subprocess.run(
            [sys.executable, str(release_root / "verification" / "verify_release.py"), str(release_root)],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise Refusal("EMBEDDED_RELEASE_VERIFIER_REFUSED")
        release_verdict = json.loads(completed.stdout)
        if (
            release_verdict.get("status") != "PASS"
            or release_verdict.get("releaseId") != EXPECTED_RELEASE_ID
            or release_verdict.get("transactionId") != EXPECTED_TRANSACTION
            or release_verdict.get("preparedTerminal") != "PREPARED_NOT_EXECUTED"
        ):
            raise Refusal("EMBEDDED_RELEASE_VERDICT_INVALID")
    return {
        "schema": "axm-private/issue105-current-rejoin-preparation-verdict@1",
        "status": "PASS",
        "packetId": package["packetId"],
        "identityJoinId": package["identityJoinId"],
        "membersVerified": len(expected),
        "embeddedReleaseVerified": True,
        "maximumPreparationTerminal": "READY_FOR_EXACT_RANGE_CUSTODY",
        **ZERO,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, nargs="?", default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.root), sort_keys=True, indent=2))
        return 0
    except Refusal as exc:
        print(json.dumps({"schema": "axm-private/issue105-current-rejoin-preparation-verdict@1", "status": "REFUSED", "reasonCode": str(exc).split(":", 1)[0], **ZERO}, sort_keys=True, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
