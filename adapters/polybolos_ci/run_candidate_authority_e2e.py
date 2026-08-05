#!/usr/bin/env python3
"""Run the actual Command Intelligence candidate through an external authority gate.

The transaction starts the qualified public OSIRIS build, ingests one synthetic
observation through the real authenticated CI route, asks the real CI candidate
route to bind a proposal to the exact current snapshot, and then evaluates that
candidate with a separately signed Ed25519 authority envelope.

The authority gate emits eligibility only. No actuation, targeting, engagement,
effector, emulator-input, or weapons surface is present.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from run_live_e2e import http_json, wait_ready, write_json

HERE = Path(__file__).resolve().parent
AUTHORITY_GATE = HERE / "authority" / "authority_gate.mjs"
INGEST_KEY = "polybolos-ci-candidate-ingest-key"
CANDIDATE_KEY = "polybolos-ci-candidate-key"

RESERVED_AUTHORITY_KEYS = {
    "authorized",
    "isauthorized",
    "authorization",
    "authority",
    "authoritygranted",
    "approved",
    "isapproved",
    "approval",
    "allow",
    "allowed",
    "execute",
    "executionauthorized",
    "executionapproved",
    "engagementauthorized",
    "engagementapproved",
    "commandauthority",
    "releaseauthority",
    "weaponsrelease",
    "weaponsreleaseauthorized",
    "effectorcommand",
    "actuationauthorized",
}


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def digest(prefix: str, value: Any) -> str:
    return f"{prefix}_{hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()}"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalized_key(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def assert_no_authority_fields(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if normalized_key(str(key)) in RESERVED_AUTHORITY_KEYS:
                raise RuntimeError(f"candidate payload carried authority field {key} at {path}")
            assert_no_authority_fields(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            assert_no_authority_fields(nested, f"{path}[{index}]")


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def start_server(target: Path, port: int, wal: Path, log: Path) -> subprocess.Popen[str]:
    handle = log.open("w", encoding="utf-8")
    env = os.environ.copy()
    env.update(
        {
            "SDK_INGEST_KEY": INGEST_KEY,
            "SDK_CANDIDATE_KEY": CANDIDATE_KEY,
            "CI_STORE_PATH": str(wal),
            "NEXT_TELEMETRY_DISABLED": "1",
            "NODE_ENV": "production",
        }
    )
    process = subprocess.Popen(
        [
            "npm",
            "start",
            "--",
            "--hostname",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=target,
        env=env,
        text=True,
        stdout=handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    process._polybolos_log_handle = handle  # type: ignore[attr-defined]
    return process


def stop_server(process: subprocess.Popen[str], lock_path: Path) -> None:
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=12)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
    handle = getattr(process, "_polybolos_log_handle", None)
    if handle is not None:
        handle.close()
    deadline = time.monotonic() + 5
    while lock_path.exists() and time.monotonic() < deadline:
        time.sleep(0.1)
    if lock_path.exists():
        raise RuntimeError(f"candidate WAL lock survived provider stop: {lock_path}")


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def verify_transaction_identity(transaction: dict[str, Any]) -> None:
    snapshot = transaction["snapshot"]
    expected_snapshot = digest(
        "ci1",
        {
            "sequence": snapshot["sequence"],
            "observedAt": snapshot["observedAt"],
            "feeds": snapshot["feeds"],
            "entities": snapshot["entities"],
        },
    )
    if snapshot.get("snapshotId") != expected_snapshot:
        raise RuntimeError("detached Python verifier rejected the snapshot identity")

    candidate = transaction["candidate"]
    expected_candidate = digest(
        "candidate1",
        {
            "snapshotId": candidate["snapshotId"],
            "producer": candidate["producer"],
            "createdAt": iso(parse_iso(candidate["createdAt"])),
            "actionClass": candidate["actionClass"],
            "payload": candidate["payload"],
        },
    )
    if candidate.get("candidateId") != expected_candidate:
        raise RuntimeError("detached Python verifier rejected the candidate identity")
    if candidate.get("snapshotId") != snapshot.get("snapshotId"):
        raise RuntimeError("candidate did not cite the returned snapshot")
    assert_no_authority_fields(candidate.get("payload"))


def issue_authority(
    output: Path,
    transaction: dict[str, Any],
) -> tuple[Path, Path, str]:
    if shutil.which("openssl") is None:
        raise RuntimeError("OpenSSL is required for the retained Ed25519 fixture")

    private_key = output / "authority-private.pem"
    public_key = output / "authority-public.pem"
    signature_path = output / "authority.sig"
    message_path = output / "authority-message.json"
    authority_path = output / "authority.json"
    trust_path = output / "authority-trust.json"

    subprocess.run(
        ["openssl", "genpkey", "-algorithm", "ED25519", "-out", str(private_key)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    subprocess.run(
        ["openssl", "pkey", "-in", str(private_key), "-pubout", "-out", str(public_key)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    snapshot_time = parse_iso(transaction["snapshot"]["observedAt"])
    candidate_time = parse_iso(transaction["candidate"]["createdAt"])
    body = {
        "schema": "axm-command-authority/1",
        "issuer": "fixture-commander",
        "subject": "polybolos-command-candidate",
        "notBefore": iso(snapshot_time - timedelta(seconds=1)),
        "expiresAt": iso(candidate_time + timedelta(minutes=5)),
        "maxSnapshotAgeMs": 120_000,
        "allowedProducers": ["command-core-fixture"],
        "allowedActionClasses": ["track-priority-candidate"],
        "requiredPayloadFields": ["entityId", "priority"],
        "allowedPayloadFields": ["entityId", "priority", "explanation"],
        "maxPayloadBytes": 4_096,
    }
    authority_id = digest("authority1", body)
    signed_body = {**body, "authorityId": authority_id}
    message_path.write_text(canonical_json(signed_body), encoding="utf-8")
    subprocess.run(
        [
            "openssl",
            "pkeyutl",
            "-sign",
            "-inkey",
            str(private_key),
            "-rawin",
            "-in",
            str(message_path),
            "-out",
            str(signature_path),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    authority = {
        **signed_body,
        "signature": {
            "algorithm": "Ed25519",
            "keyId": "fixture-key-1",
            "value": base64.b64encode(signature_path.read_bytes()).decode("ascii"),
        },
    }
    trust = {
        "schema": "axm-authority-trust/1",
        "keys": [
            {
                "keyId": "fixture-key-1",
                "issuer": "fixture-commander",
                "algorithm": "Ed25519",
                "publicKeyPem": public_key.read_text(encoding="utf-8"),
            }
        ],
    }
    write_json(authority_path, authority)
    write_json(trust_path, trust)
    private_key.unlink()
    signature_path.unlink()
    message_path.unlink()
    return authority_path, trust_path, authority_id


def run_gate(
    transaction_path: Path,
    authority_path: Path,
    trust_path: Path,
    checked_at: str,
    decision_path: Path,
    log_path: Path,
    expected_disposition: str,
) -> dict[str, Any]:
    result = subprocess.run(
        [
            "node",
            str(AUTHORITY_GATE),
            str(transaction_path),
            str(authority_path),
            str(trust_path),
            checked_at,
            str(decision_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    log_path.write_text(result.stdout, encoding="utf-8")
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    if decision.get("disposition") != expected_disposition:
        raise RuntimeError(
            f"authority gate returned {decision.get('disposition')!r}, expected {expected_disposition!r}"
        )
    expected_returncode = 0 if expected_disposition == "allow" else 1
    if result.returncode != expected_returncode:
        raise RuntimeError(
            f"authority gate return code {result.returncode} did not match {expected_disposition}"
        )
    return decision


def main() -> int:
    if len(sys.argv) != 3:
        print(
            "usage: run_candidate_authority_e2e.py <qualified-target-checkout> <output-dir>",
            file=sys.stderr,
        )
        return 2

    target = Path(sys.argv[1]).resolve()
    output = Path(sys.argv[2]).resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    if not (target / ".next").is_dir():
        raise RuntimeError("qualified target build is missing")
    if not AUTHORITY_GATE.is_file():
        raise RuntimeError("detached authority gate is missing")

    wal = output / "candidate-command-intelligence.wal"
    lock = Path(f"{wal}.lock")
    process: subprocess.Popen[str] | None = None
    checks: dict[str, bool] = {}

    try:
        port = free_port()
        base = f"http://127.0.0.1:{port}"
        process = start_server(target, port, wal, output / "next-candidate.log")
        wait_ready(base, process)

        status, _, ingest_result = http_json(
            f"{base}/api/sdk/ingest",
            method="POST",
            body={
                "source": "candidate-fixture",
                "replaceSnapshot": True,
                "entities": [
                    {
                        "id": "track-1",
                        "name": "CANDIDATE TRACK ONE",
                        "domain": "AIR",
                        "entityType": "TRACK",
                        "position": {"lat": 34.1478, "lng": -118.1445, "alt": 9144},
                        "threat": "LOW",
                        "classification": "UNCLASSIFIED",
                        "confidence": 1,
                        "properties": {"sourceOnly": True},
                    }
                ],
            },
            headers={"Authorization": f"Bearer {INGEST_KEY}"},
            timeout=15,
        )
        write_json(output / "ingest-result.json", ingest_result)
        if status != 200 or ingest_result.get("accepted") != 1:
            raise RuntimeError(f"actual CI ingest failed: HTTP {status} {ingest_result!r}")

        candidate_body = {
            "producer": "command-core-fixture",
            "actionClass": "track-priority-candidate",
            "staleAfterMs": 86_400_000,
            "payload": {
                "entityId": "ext-candidate-fixture-track-1",
                "priority": 7,
                "explanation": "synthetic candidate only",
            },
        }
        status, _, transaction = http_json(
            f"{base}/api/sdk/candidate",
            method="POST",
            body=candidate_body,
            headers={"Authorization": f"Bearer {CANDIDATE_KEY}"},
            timeout=15,
        )
        if status != 201 or not isinstance(transaction, dict):
            raise RuntimeError(f"actual CI candidate route failed: HTTP {status} {transaction!r}")
        transaction_path = output / "candidate-transaction.json"
        write_json(transaction_path, transaction)
        verify_transaction_identity(transaction)
        checks["actual_ci_candidate_bound_to_exact_snapshot"] = True
        checks["detached_python_identity_verifier"] = True

        status, _, wrong_key = http_json(
            f"{base}/api/sdk/candidate",
            method="POST",
            body=candidate_body,
            headers={"Authorization": f"Bearer {INGEST_KEY}"},
            timeout=15,
        )
        write_json(output / "candidate-wrong-key.json", wrong_key)
        if status != 401 or wrong_key.get("error") != "CANDIDATE_AUTH_REQUIRED":
            raise RuntimeError("candidate route accepted or misclassified the ingest credential")
        checks["candidate_credential_separate_from_ingest"] = True

        self_authorizing = {
            **candidate_body,
            "payload": {
                "entityId": "ext-candidate-fixture-track-1",
                "authorized": True,
            },
        }
        status, _, self_authority_result = http_json(
            f"{base}/api/sdk/candidate",
            method="POST",
            body=self_authorizing,
            headers={"Authorization": f"Bearer {CANDIDATE_KEY}"},
            timeout=15,
        )
        write_json(output / "candidate-self-authority-refusal.json", self_authority_result)
        if status != 400 or "may not carry authority field" not in self_authority_result.get("error", ""):
            raise RuntimeError("candidate route did not refuse self-authorization")
        checks["candidate_self_authorization_refused"] = True

        authority_path, trust_path, authority_id = issue_authority(output, transaction)
        candidate_time = parse_iso(transaction["candidate"]["createdAt"])
        checked_at = iso(candidate_time + timedelta(seconds=1))
        decision_path = output / "authority-decision.json"
        decision = run_gate(
            transaction_path,
            authority_path,
            trust_path,
            checked_at,
            decision_path,
            output / "authority-gate.log",
            "allow",
        )
        if not decision.get("candidateVerified") or not decision.get("authorityVerified"):
            raise RuntimeError("allow decision did not carry both verification receipts")
        checks["signed_external_authority_allows_only_eligible_candidate"] = True

        tampered = json.loads(transaction_path.read_text(encoding="utf-8"))
        tampered["candidate"]["payload"]["priority"] = 99
        tampered_path = output / "tampered-candidate-transaction.json"
        write_json(tampered_path, tampered)
        tampered_decision = run_gate(
            tampered_path,
            authority_path,
            trust_path,
            checked_at,
            output / "tampered-candidate-decision.json",
            output / "tampered-candidate-gate.log",
            "refuse",
        )
        if tampered_decision["reasons"][0]["code"] != "candidate_binding_invalid":
            raise RuntimeError("tampered candidate was refused for the wrong reason")
        checks["tampered_candidate_refused"] = True

        authority = json.loads(authority_path.read_text(encoding="utf-8"))
        signature = authority["signature"]["value"]
        authority["signature"]["value"] = f"{signature[:-4]}AAAA"
        bad_authority_path = output / "tampered-authority.json"
        write_json(bad_authority_path, authority)
        signature_decision = run_gate(
            transaction_path,
            bad_authority_path,
            trust_path,
            checked_at,
            output / "tampered-authority-decision.json",
            output / "tampered-authority-gate.log",
            "refuse",
        )
        if signature_decision["reasons"][0]["code"] != "authority_signature_invalid":
            raise RuntimeError("tampered authority was refused for the wrong reason")
        checks["tampered_authority_signature_refused"] = True

        valid_authority = json.loads(authority_path.read_text(encoding="utf-8"))
        expired_at = iso(parse_iso(valid_authority["expiresAt"]) + timedelta(seconds=1))
        expired_decision = run_gate(
            transaction_path,
            authority_path,
            trust_path,
            expired_at,
            output / "expired-authority-decision.json",
            output / "expired-authority-gate.log",
            "safe_state",
        )
        if expired_decision["reasons"][0]["code"] != "authority_expired":
            raise RuntimeError("expired authority did not enter safe state")
        checks["expired_authority_enters_safe_state"] = True

        stop_server(process, lock)
        process = None

        receipt = {
            "schema": "ai-execution-audit/polybolos-ci-candidate-authority-e2e@1",
            "status": "pass",
            "targetCommit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=target, text=True
            ).strip(),
            "checks": checks,
            "identities": {
                "snapshotId": transaction["snapshot"]["snapshotId"],
                "candidateId": transaction["candidate"]["candidateId"],
                "authorityId": authority_id,
                "decisionId": decision["decisionId"],
                "walSha256": sha256(wal),
            },
            "artifacts": {
                path.name: {"bytes": path.stat().st_size, "sha256": sha256(path)}
                for path in sorted(output.iterdir())
                if path.is_file() and path.name != "candidate-authority-e2e-receipt.json"
            },
            "claimBoundary": (
                "This transaction qualifies candidate binding and external signed authority eligibility "
                "against the pinned public Command Intelligence source. It does not test private COMMAND "
                "CORE, private Lattice, operational targeting, engagement, effector control, weapons "
                "employment, or combat effectiveness."
            ),
        }
        write_json(output / "candidate-authority-e2e-receipt.json", receipt)
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 0
    finally:
        if process is not None:
            try:
                stop_server(process, lock)
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
