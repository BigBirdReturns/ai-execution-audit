from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


def regular(path: Path, maximum: int = 2_000_000) -> bytes:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.parts[0])
    for part in absolute.parts[1:]:
        current = current / part
        if current.exists() or current.is_symlink():
            info = current.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                raise ValueError(f"linked verifier coordinate refused: {current}")
    info = absolute.lstat()
    if not stat.S_ISREG(info.st_mode) or not 1 <= info.st_size <= maximum:
        raise ValueError(f"non-regular or unbounded input: {absolute}")
    data = absolute.read_bytes()
    if len(data) != info.st_size:
        raise ValueError(f"unstable input: {absolute}")
    return data


def main() -> int:
    if len(sys.argv) != 5:
        print(json.dumps({"status": "REFUSED", "code": "ARGUMENT_DENOMINATOR_INVALID"}, sort_keys=True))
        return 2
    verifier, profile, repository, extension = (Path(os.path.abspath(value)) for value in sys.argv[1:])
    try:
        verifier_bytes = regular(verifier)
        with tempfile.TemporaryDirectory(prefix="axm-flight-choreographer-verifier-") as temp:
            measured = Path(temp) / "measured_verifier.py"
            measured.write_bytes(verifier_bytes)
            completed = subprocess.run(
                [sys.executable, str(measured), str(profile), str(repository), str(extension)],
                capture_output=True,
                text=True,
                cwd=temp,
            )
        if completed.returncode != 0:
            raise ValueError(completed.stdout + completed.stderr)
        result = json.loads(completed.stdout)
        if result.get("status") != "PASS":
            raise ValueError(str(result))
        receipt = {
            "schema": "axm-head/browser-physical-flight-choreographer-bootstrap@1",
            "status": "PASS",
            "bootstrapAuthenticated": True,
            "verifierSha256": "sha256:" + hashlib.sha256(verifier_bytes).hexdigest(),
            "profileId": result["profileId"],
            "sourceBindingId": result["sourceBindingId"],
            "extensionId": result["extensionId"],
            "extensionMemberCount": result["extensionMemberCount"],
            "operationCardExecuted": False,
            "physicalExecutionObserved": False,
            "actualSupplierQualified": False,
            "physicalEstateQualified": False,
            "missionAuthority": "none",
            "commandAuthority": "none",
        }
        print(json.dumps(receipt, sort_keys=True, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({
            "schema": "axm-head/browser-physical-flight-choreographer-bootstrap@1",
            "status": "REFUSED",
            "code": "BOOTSTRAP_VERIFICATION_FAILED",
            "message": str(exc),
            "actualSupplierQualified": False,
            "physicalEstateQualified": False,
            "missionAuthority": "none",
            "commandAuthority": "none",
        }, sort_keys=True, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
