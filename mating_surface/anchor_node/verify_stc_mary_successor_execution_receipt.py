"""Independently verify one final successor execution receipt.

This verifier is deliberately independent of the construction law and of the launcher
that issued the receipt.  Its caller must execute these admitted bytes under an external
measured bootstrap.  The verifier consumes ``ambientRepositorySourceTrusted: false`` as
law, binds the selected role to one authenticated source-admission member, and refuses
any environment-only claim of source execution identity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

AUTHORITY = "none"
MAX_JSON_BYTES = 64 * 1024 * 1024


class ExecutionReceiptError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def fail(code: str, message: str) -> None:
    raise ExecutionReceiptError(code, message)


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        fail(code, message)


def canonical_json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        fail("NON_CANONICAL_JSON", str(exc))
        raise


def canonical_json_bytes(value: Any) -> bytes:
    return (canonical_json(value) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def content_id(prefix: str, value: Any) -> str:
    return f"{prefix}_{sha256_bytes(canonical_json(value).encode('utf-8'))}"


def exact_keys(value: Any, expected: Iterable[str], code: str, label: str) -> Mapping[str, Any]:
    require(isinstance(value, Mapping), code, f"{label} must be an object")
    require(set(value) == set(expected), code, f"{label} field denominator differs")
    return value


def read_json(path: Path, *, code: str, label: str, canonical: bool = True) -> Mapping[str, Any]:
    require(not path.is_symlink() and path.is_file(), code, f"{label} is not a regular file")
    raw = path.read_bytes()
    require(len(raw) <= MAX_JSON_BYTES, code, f"{label} exceeds the bounded allocation")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(code, f"{label} is not UTF-8 JSON: {exc}")
        raise
    require(isinstance(value, Mapping), code, f"{label} must be an object")
    if canonical:
        require(raw == canonical_json_bytes(value), code, f"{label} is not canonical JSON")
    return value


def assert_identity(value: Mapping[str, Any], key: str, prefix: str, code: str, label: str) -> str:
    body = dict(value)
    observed = body.pop(key, None)
    require(
        isinstance(observed, str) and observed == content_id(prefix, body),
        code,
        f"{label} content identity differs",
    )
    return observed


def verify_execution_receipt(
    *,
    profile: Mapping[str, Any],
    execution_receipt: Path,
    expected_role: str,
    packet: Path | None = None,
    source_admission_receipt: Path | None = None,
) -> Mapping[str, Any]:
    """Verify and return the exact receipt consumed by a mutation or recovery."""
    custody = profile["executionCustody"]
    receipt = read_json(
        execution_receipt,
        code="EXECUTION_RECEIPT_INVALID",
        label="execution receipt",
    )
    exact_keys(receipt, custody["receiptKeys"], "EXECUTION_RECEIPT_INVALID", "execution receipt")
    assert_identity(
        receipt,
        custody["idKey"],
        custody["idPrefix"],
        "EXECUTION_RECEIPT_IDENTITY_INVALID",
        "execution receipt",
    )
    require(
        receipt["schema"] == custody["schema"]
        and receipt["status"] == "PASS"
        and receipt["processTerminal"] == "PASS"
        and receipt["isolated"] == 1
        and receipt["noSite"] == 1
        and receipt["dontWriteBytecode"] == 1
        and receipt["ambientRepositorySourceTrusted"] is False
        and receipt["authority"] == AUTHORITY,
        "EXECUTION_RECEIPT_TERMINAL_INVALID",
        "execution receipt does not prove isolated PASS with ambient repository trust refused",
    )
    require(receipt["operationRole"] == expected_role, "EXECUTION_ROLE_MISMATCH", "execution receipt names another operation role")

    output_binding = custody["outputArtifactBindings"].get(expected_role)
    if output_binding is None:
        require(
            receipt["outputArtifactId"] is None
            and receipt["outputArtifactSha256"] is None
            and receipt["outputArtifactBytes"] is None,
            "EXECUTION_OUTPUT_BINDING_UNADMITTED",
            "this operation role may not claim a produced artifact",
        )
    else:
        output_id = receipt["outputArtifactId"]
        output_digest = receipt["outputArtifactSha256"]
        require(
            isinstance(output_id, str)
            and output_id.startswith(output_binding["idPrefix"] + "_")
            and len(output_id.removeprefix(output_binding["idPrefix"] + "_")) == 64
            and all(character in "0123456789abcdef" for character in output_id[-64:])
            and isinstance(output_digest, str)
            and len(output_digest) == 64
            and all(character in "0123456789abcdef" for character in output_digest)
            and type(receipt["outputArtifactBytes"]) is int
            and receipt["outputArtifactBytes"] > 0,
            "EXECUTION_OUTPUT_BINDING_INVALID",
            "execution receipt does not bind one exact produced artifact identity, digest, and byte count",
        )

    roles = custody["roles"]
    require(set(roles) == set(custody["roleDenominator"]), "EXECUTION_ROLE_MAP_INVALID", "role denominator differs")
    require(expected_role in roles, "EXECUTION_ROLE_UNADMITTED", "operation role is not admitted")
    mapping = roles[expected_role]
    require(
        receipt["repositoryRelativeModulePath"] == mapping["repositoryPath"]
        and receipt["packetRelativeModulePath"] == mapping["packetPath"],
        "EXECUTION_ROLE_MODULE_MISMATCH",
        "operation role maps to another admitted module",
    )

    if packet is not None:
        packet = Path(os.path.abspath(os.fspath(packet)))
        admission_path = packet / profile["lineage"]["sourceAdmissionFile"]
        source_set = read_json(
            packet / profile["lineage"]["sourceSetFile"],
            code="EXECUTION_SOURCE_SET_INVALID",
            label="packet source set",
        )
        marker = read_json(packet / profile["packet"]["files"]["marker"], code="EXECUTION_PACKET_INVALID", label="packet marker")
        require(receipt["packetId"] == marker.get("packetId"), "EXECUTION_PACKET_MISMATCH", "execution receipt names another packet")
        assert_identity(
            source_set,
            profile["lineage"]["sourceSetIdKey"],
            profile["lineage"]["sourceSetIdPrefix"],
            "EXECUTION_SOURCE_SET_INVALID",
            "packet source set",
        )
    else:
        require(expected_role == "compile" and receipt["packetId"] is None, "EXECUTION_PACKET_MISMATCH", "only compile may omit packet identity")
        require(source_admission_receipt is not None, "EXECUTION_SOURCE_ADMISSION_ABSENT", "compile verification requires source admission")
        admission_path = source_admission_receipt
        source_set = None

    admission = read_json(admission_path, code="EXECUTION_SOURCE_ADMISSION_INVALID", label="source admission")
    admission_law = profile["sourceAdmission"]
    exact_keys(admission, admission_law["receiptKeys"], "EXECUTION_SOURCE_ADMISSION_INVALID", "source admission")
    assert_identity(
        admission,
        admission_law["idKey"],
        admission_law["idPrefix"],
        "EXECUTION_SOURCE_ADMISSION_INVALID",
        "source admission",
    )
    require(
        admission["status"] == "PASS"
        and admission["bootstrapAuthenticated"] is True
        and admission["workingTreeBytesTrusted"] is False
        and admission["authority"] == AUTHORITY,
        "EXECUTION_SOURCE_ADMISSION_INVALID",
        "source admission is not externally authenticated exact-Git custody",
    )
    for key in ("sourceAdmissionId", "sourceCommit", "sourceTree", "gitObjectFormat", "successorSourceSetId"):
        expected = admission[admission_law["idKey"]] if key == "sourceAdmissionId" else admission[key]
        require(receipt[key] == expected, "EXECUTION_SOURCE_BINDING_MISMATCH", f"execution receipt {key} differs")
    require(
        receipt["completeMeasuredSourceSetId"] == admission["successorSourceSetId"],
        "EXECUTION_SOURCE_SET_MISMATCH",
        "execution receipt does not bind the complete admitted source set",
    )
    if source_set is not None:
        require(
            source_set[profile["lineage"]["sourceSetIdKey"]] == receipt["completeMeasuredSourceSetId"],
            "EXECUTION_SOURCE_SET_MISMATCH",
            "packet source set differs from the execution receipt",
        )

    member_rows = [
        row for row in admission["members"]
        if isinstance(row, Mapping) and row.get("repositoryPath") == mapping["repositoryPath"]
    ]
    require(len(member_rows) == 1, "EXECUTION_MODULE_MEMBER_INVALID", "module Git blob does not resolve to exactly one source-admission row")
    row = member_rows[0]
    require(
        row.get("packetPath") == mapping["packetPath"]
        and row.get("gitBlob") == receipt["moduleGitBlobId"]
        and row.get("sha256") == receipt["moduleSha256"],
        "EXECUTION_MODULE_MEMBER_INVALID",
        "execution module differs from its authenticated source-admission member",
    )
    return receipt


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Independently verify one successor execution receipt")
    parser.add_argument("--execution-receipt", type=Path, required=True)
    parser.add_argument("--expected-role", required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--packet", type=Path)
    parser.add_argument("--source-admission-receipt", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        profile = read_json(args.profile, code="EXECUTION_PROFILE_INVALID", label="successor profile", canonical=False)
        receipt = verify_execution_receipt(
            profile=profile,
            execution_receipt=args.execution_receipt,
            expected_role=args.expected_role,
            packet=args.packet,
            source_admission_receipt=args.source_admission_receipt,
        )
        sys.stdout.buffer.write(canonical_json_bytes({
            "schema": "stc-mary/successor-execution-receipt-verification/1",
            "status": "PASS",
            "executionReceiptId": receipt[profile["executionCustody"]["idKey"]],
            "ambientRepositorySourceTrusted": False,
            "authority": AUTHORITY,
        }))
        return 0
    except ExecutionReceiptError as exc:
        sys.stdout.buffer.write(canonical_json_bytes({
            "schema": "stc-mary/successor-execution-receipt-verification/1",
            "status": "REFUSED",
            "code": exc.code,
            "message": str(exc),
            "ambientRepositorySourceTrusted": False,
            "authority": AUTHORITY,
        }))
        return 1
    except (OSError, ValueError, KeyError) as exc:
        sys.stdout.buffer.write(canonical_json_bytes({
            "schema": "stc-mary/successor-execution-receipt-verification/1",
            "status": "REFUSED",
            "code": "EXECUTION_RECEIPT_FILESYSTEM_ERROR",
            "message": str(exc),
            "ambientRepositorySourceTrusted": False,
            "authority": AUTHORITY,
        }))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
