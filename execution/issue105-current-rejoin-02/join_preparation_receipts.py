#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPECTED_MAIN = "3c11dbca48ae777137675bb9bf485f0c42daf7a4"
EXPECTED_RELEASE_ID = "axmbrowserphysicalflightrelease_48bded1a98f703e2a044765bcd786b82eb9c097c26a43bc420945f97f074e566"
EXPECTED_PACKAGE_ID = "axmbrowserphysicalflightpackage_812d83141a0f339f0ada89339a5ba98f375c788a3aafdbd91aaa2bb450929a19"
EXPECTED_TRANSACTION = "axmbrowserphysicalrun_b90f76feb0a7324dac7fbd8780a7079a8123c85cdf4a06233467e675803722dc"
EXPECTED_SEATS = {
    "W01": {
        "terminal": "W01_CURRENT_CONTROLLER_AND_SEAT02_PREPARED",
        "roles": {"controller", "seat-02"},
        "seatId": "seat-02",
        "capsuleId": "axmbrowserphysicalseatcapsule_d9898cb5ff6df1c9312d80bed0851985c634fb395e6ec63cc1469ab9851c6df6",
        "capsuleArchiveSha256": "sha256:0f6211976f03260d2c645c613e8ba690de83e72fbac9e7d4a5320f6952cdf491",
    },
    "L01": {
        "terminal": "L01_CURRENT_SEAT01_PREPARED",
        "roles": {"seat-01"},
        "seatId": "seat-01",
        "capsuleId": "axmbrowserphysicalseatcapsule_5dc5e85984afb654dfc353731f2e3822807db98884d88cfb2a3cb5b3bf18b024",
        "capsuleArchiveSha256": "sha256:5e06e8d9f5b3ec69dd1e9db1f68b0630042cd58dea730aa56aba6ec4c23670bb",
    },
}
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


class Hold(RuntimeError):
    pass


def load(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise Hold(f"RECEIPT_MISSING_OR_LINKED:{path.name}")
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise Hold(f"RECEIPT_JSON_INVALID:{path.name}") from exc
    if not isinstance(value, dict):
        raise Hold(f"RECEIPT_ROOT_INVALID:{path.name}")
    return value


def file_ref(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def require_zero(value: dict[str, Any], label: str) -> None:
    for key, expected in ZERO.items():
        if value.get(key) != expected:
            raise Hold(f"EXECUTION_OR_AUTHORITY_WIDENED:{label}:{key}")


def validate_host(receipt: dict[str, Any], role: str, identity_join_id: str, packet_id: str, preparer_sha256: str) -> dict[str, Any]:
    expected = EXPECTED_SEATS[role]
    if receipt.get("schema") != "axm-private/issue105-current-host-preparation@1":
        raise Hold(f"HOST_RECEIPT_SCHEMA_INVALID:{role}")
    if receipt.get("status") != "PASS" or receipt.get("terminal") != expected["terminal"] or receipt.get("reasonCode") is not None:
        raise Hold(f"HOST_RECEIPT_TERMINAL_INVALID:{role}")
    exact = {
        "requestedHostRole": role,
        "identityJoinId": identity_join_id,
        "rejoinPacketId": packet_id,
        "repositoryMainCommit": EXPECTED_MAIN,
        "releaseId": EXPECTED_RELEASE_ID,
        "packageId": EXPECTED_PACKAGE_ID,
        "transactionId": EXPECTED_TRANSACTION,
        "seatId": expected["seatId"],
        "capsuleId": expected["capsuleId"],
        "capsuleArchiveSha256": expected["capsuleArchiveSha256"],
        "preparerSha256": preparer_sha256,
    }
    for key, wanted in exact.items():
        if receipt.get(key) != wanted:
            raise Hold(f"HOST_RECEIPT_BINDING_INVALID:{role}:{key}")
    if not isinstance(receipt.get("hostRef"), str) or not SHA_REF.fullmatch(receipt["hostRef"]):
        raise Hold(f"HOST_REFERENCE_INVALID:{role}")
    if not isinstance(receipt.get("persistentRootRef"), str) or not SHA_REF.fullmatch(receipt["persistentRootRef"]):
        raise Hold(f"PERSISTENT_ROOT_REFERENCE_INVALID:{role}")
    if receipt.get("persistenceScope") != "HOST_LOCAL_OUTSIDE_TRANSPORT_STAGE":
        raise Hold(f"PERSISTENCE_SCOPE_INVALID:{role}")
    if receipt.get("persistentMaterialVerifiedAfterPrepare") is not True:
        raise Hold(f"PERSISTENT_MATERIAL_NOT_VERIFIED:{role}")
    rows = receipt.get("preparedRoles")
    if not isinstance(rows, list):
        raise Hold(f"PREPARED_ROLE_DENOMINATOR_INVALID:{role}")
    observed: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or row.get("role") not in expected["roles"] or row.get("role") in observed:
            raise Hold(f"PREPARED_ROLE_INVALID:{role}")
        if row.get("state") not in {"PREPARED", "REUSED_EXACT"}:
            raise Hold(f"PREPARED_ROLE_STATE_INVALID:{role}")
        if not isinstance(row.get("destinationRef"), str) or not SHA_REF.fullmatch(row["destinationRef"]):
            raise Hold(f"DESTINATION_REFERENCE_INVALID:{role}")
        observed.add(row["role"])
    if observed != expected["roles"]:
        raise Hold(f"PREPARED_ROLE_SET_INVALID:{role}")
    require_zero(receipt, role)
    return {
        "hostRole": role,
        "hostRef": receipt["hostRef"],
        "persistentRootRef": receipt["persistentRootRef"],
        "persistenceScope": receipt["persistenceScope"],
        "persistentMaterialVerifiedAfterPrepare": True,
        "preparedRoles": sorted(observed),
        "seatId": expected["seatId"],
        "capsuleId": expected["capsuleId"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--identity", type=Path, default=Path("ISSUE105-CURRENT-IDENTITY-JOIN.json"))
    parser.add_argument("--package", type=Path, default=Path("PACKAGE.json"))
    parser.add_argument("--w01", type=Path, default=Path("receipts/ISSUE105-W01-PREPARATION-RECEIPT.json"))
    parser.add_argument("--l01", type=Path, default=Path("receipts/ISSUE105-L01-PREPARATION-RECEIPT.json"))
    parser.add_argument("--output", type=Path, default=Path("receipts/ISSUE105-TWO-SEAT-PREPARATION-JOIN.json"))
    args = parser.parse_args()
    try:
        identity = load(args.identity)
        package = load(args.package)
        if identity.get("status") != "PASS" or identity.get("identityJoinId") != package.get("identityJoinId"):
            raise Hold("CURRENT_IDENTITY_JOIN_INVALID")
        if identity.get("identityBody", {}).get("repository", {}).get("mainCommit") != EXPECTED_MAIN:
            raise Hold("CURRENT_REPOSITORY_FLOOR_INVALID")
        require_zero(identity.get("claimBoundary", {}), "IDENTITY_JOIN")
        require_zero(package.get("claimBoundary", {}), "PACKAGE")
        members = package.get("identityBody", {}).get("members", [])
        preparer_rows = [row for row in members if isinstance(row, dict) and row.get("path") == "Prepare-Current-Host.ps1"]
        if len(preparer_rows) != 1 or not isinstance(preparer_rows[0].get("sha256"), str) or not SHA_REF.fullmatch(preparer_rows[0]["sha256"]):
            raise Hold("HOST_PREPARER_IDENTITY_INVALID")
        preparer_sha256 = preparer_rows[0]["sha256"]
        w01 = validate_host(load(args.w01), "W01", identity["identityJoinId"], package["packetId"], preparer_sha256)
        l01 = validate_host(load(args.l01), "L01", identity["identityJoinId"], package["packetId"], preparer_sha256)
        if w01["hostRef"] == l01["hostRef"]:
            raise Hold("HOST_REFERENCE_COLLISION")
        result = {
            "schema": "axm-private/issue105-two-seat-preparation-join@1",
            "status": "PASS",
            "terminal": "READY_FOR_EXACT_RANGE_CUSTODY",
            "reasonCode": None,
            "observedAtUtc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "identityJoinId": identity["identityJoinId"],
            "rejoinPacketId": package["packetId"],
            "repositoryMainCommit": EXPECTED_MAIN,
            "releaseId": EXPECTED_RELEASE_ID,
            "packageId": EXPECTED_PACKAGE_ID,
            "transactionId": EXPECTED_TRANSACTION,
            "identityJoinReceiptRef": file_ref(args.identity),
            "w01PreparationReceiptRef": file_ref(args.w01),
            "l01PreparationReceiptRef": file_ref(args.l01),
            "hostReferencesDistinct": True,
            "distinctPhysicalSeatsConfirmed": False,
            "hosts": [w01, l01],
            **ZERO,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except Hold as exc:
        result = {
            "schema": "axm-private/issue105-two-seat-preparation-join@1",
            "status": "HOLD",
            "terminal": "HOLD",
            "reasonCode": str(exc).split(":", 1)[0],
            **ZERO,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, sort_keys=True, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
