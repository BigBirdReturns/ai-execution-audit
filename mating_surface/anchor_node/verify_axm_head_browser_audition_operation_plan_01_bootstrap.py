from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


def regular(path: Path) -> bytes:
    info = path.lstat()
    attrs = getattr(info, "st_file_attributes", 0)
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
        raise ValueError(f"verifier is not a regular file: {path}")
    return path.read_bytes()


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(json.dumps({"status": "REFUSED", "code": "ARGUMENT_DENOMINATOR_INVALID"}, sort_keys=True))
        return 2
    verifier, profile, repository, extension = map(Path, argv)
    try:
        data = regular(verifier)
        verifier_sha = "sha256:" + hashlib.sha256(data).hexdigest()
        repository_root = repository.resolve(strict=True)
        expected = repository_root / "mating_surface/anchor_node/verify_axm_head_browser_audition_operation_plan_01.py"
        if regular(expected) != data:
            raise ValueError("stored verifier bytes differ from repository member")
        with tempfile.TemporaryDirectory(prefix="axm-operation-plan-bootstrap-") as temp:
            measured = Path(temp) / verifier.name
            measured.write_bytes(data)
            completed = subprocess.run(
                [sys.executable, str(measured), str(profile.resolve(strict=True)), str(repository_root), str(extension.resolve(strict=True))],
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            if completed.returncode != 0:
                raise ValueError(completed.stdout or completed.stderr)
            verdict = json.loads(completed.stdout)
        if verdict.get("status") != "PASS" or verdict.get("bootstrapAuthenticated") is not False:
            raise ValueError("measured verifier did not return the direct PASS boundary")
        verdict["bootstrapAuthenticated"] = True
        verdict["storedVerifierMemberBound"] = True
        verdict["measuredVerifierSha256"] = verifier_sha
        print(json.dumps(verdict, sort_keys=True, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "REFUSED", "code": "BOOTSTRAP_FAILED", "message": str(exc), "bootstrapAuthenticated": False}, sort_keys=True, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
