from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SCHEMA = "axm-head/browser-distributed-inference-audition-bootstrap-verdict@1"
DIRECT_SCHEMA = "axm-head/browser-distributed-inference-audition-verdict@1"


def pretty(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("verifier")
    parser.add_argument("profile")
    parser.add_argument("capture")
    parser.add_argument("decision")
    parser.add_argument("--raw")
    parser.add_argument("--control")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    if bool(args.raw) != bool(args.control):
        parser.error("--raw and --control must be supplied together")
    verifier = Path(args.verifier).resolve()
    profile = Path(args.profile).resolve()
    capture = Path(args.capture).resolve()
    decision = Path(args.decision).resolve()
    raw = Path(args.raw).resolve() if args.raw else None
    control = Path(args.control).resolve() if args.control else None
    output = Path(args.out).resolve() if args.out else None
    try:
        source = verifier.read_bytes()
        measured_sha = hashlib.sha256(source).hexdigest()
        launcher = (
            "import sys; source=sys.stdin.buffer.read(); "
            "sys.argv=['measured-verifier', *sys.argv[1:]]; "
            "ns={'__name__':'__main__','__file__':'<measured-verifier>'}; "
            "exec(compile(source,'<measured-verifier>','exec'),ns)"
        )
        with tempfile.TemporaryDirectory(prefix="axm-browser-audition-bootstrap-") as temporary:
            verifier_args = [str(profile), str(capture), str(decision)]
            if raw is not None and control is not None:
                verifier_args.extend(["--raw", str(raw), "--control", str(control)])
            result = subprocess.run(
                [sys.executable, "-I", "-S", "-c", launcher, *verifier_args],
                input=source,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=temporary,
                check=False,
            )
        if result.stderr != b"":
            raise RuntimeError("measured verifier emitted stderr")
        direct = json.loads(result.stdout.decode("utf-8"))
        if result.returncode != 0 or direct.get("schema") != DIRECT_SCHEMA or direct.get("status") != "PASS":
            raise RuntimeError(f"direct verifier refused: {direct}")
        if direct.get("bootstrapAuthenticated") is not False:
            raise RuntimeError("direct verifier self-authenticated")
        if direct.get("terminal") == "OBSERVED_ROUTE_CANDIDATE" and direct.get("rawEvidenceReconstructed") is not True:
            raise RuntimeError("direct verifier did not reconstruct raw evidence")
        after = verifier.read_bytes()
        if after != source:
            raise RuntimeError("verifier member changed after measurement")
        outer = {
            "schema": SCHEMA,
            "status": "PASS",
            "terminal": direct["terminal"],
            "reasonCodes": direct["reasonCodes"],
            "captureDigest": direct["captureDigest"],
            "observationReceiptDigest": direct["observationReceiptDigest"],
            "decisionDigest": direct["decisionDigest"],
            "embeddedVerifierSha256": measured_sha,
            "storedVerifierMemberBound": True,
            "storedReceiptReconstructed": True,
            "publicProjectionReconstructed": True,
            "rawEvidenceReconstructed": direct.get("rawEvidenceReconstructed") is True,
            "bootstrapAuthenticated": True,
            "actualSupplierQualified": False,
            "supplierAdmissionReceiptPresent": False,
            "executionOccurred": False,
            "physicalEstateQualified": False,
            "missionAuthority": "none",
            "commandAuthority": "none",
        }
        data = pretty(outer)
        if output is not None:
            output.write_bytes(data)
        sys.stdout.buffer.write(data)
        return 0
    except (OSError, UnicodeError, json.JSONDecodeError, RuntimeError) as exc:
        body = {"schema": SCHEMA, "status": "REFUSED", "code": "BOOTSTRAP_REFUSED", "message": str(exc), "bootstrapAuthenticated": False}
        data = pretty(body)
        if output is not None:
            output.write_bytes(data)
        sys.stdout.buffer.write(data)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
