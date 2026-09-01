from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

MAX_VERIFIER_BYTES = 262144


def pretty(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")


def refusal(code: str, message: str) -> int:
    sys.stdout.buffer.write(pretty({
        "schema": "axm-head/browser-physical-audition-operator-console-bootstrap@1",
        "status": "REFUSED",
        "code": code,
        "message": message,
        "bootstrapAuthenticated": False,
        "actualSupplierQualified": False,
        "physicalEstateQualified": False,
        "missionAuthority": "none",
        "commandAuthority": "none",
    }))
    return 2


def lexical_regular(path: Path) -> bytes:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.parts[0])
    for part in absolute.parts[1:]:
        current = current / part
        if not current.exists() and not current.is_symlink():
            continue
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise ValueError(f"linked verifier coordinate: {current}")
        attributes = getattr(info, "st_file_attributes", 0)
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if attributes & reparse:
            raise ValueError(f"reparse verifier coordinate: {current}")
    info = absolute.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size < 1 or info.st_size > MAX_VERIFIER_BYTES:
        raise ValueError("verifier size or type invalid")
    with absolute.open("rb") as stream:
        data = stream.read(MAX_VERIFIER_BYTES + 1)
    if len(data) != info.st_size or len(data) > MAX_VERIFIER_BYTES:
        raise ValueError("verifier bounded read differs")
    return data


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        return refusal("ARGUMENT_DENOMINATOR_INVALID", "verifier, profile, repository root, and extension root are required")
    verifier, profile, repository, extension = map(Path, argv)
    try:
        measured = lexical_regular(verifier)
    except (OSError, ValueError) as exc:
        return refusal("VERIFIER_MEASUREMENT_FAILED", str(exc))
    digest = "sha256:" + hashlib.sha256(measured).hexdigest()
    launcher = (
        "import sys; data=sys.stdin.buffer.read(); "
        "namespace={'__name__':'__main__','__file__':'<measured-verifier>'}; "
        "exec(compile(data,'<measured-verifier>','exec'),namespace,namespace)"
    )
    completed = subprocess.run(
        [sys.executable, "-I", "-S", "-c", launcher, str(profile.resolve()), str(repository.resolve()), str(extension.resolve())],
        input=measured,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    try:
        inner = json.loads(completed.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        return refusal("MEASURED_VERIFIER_OUTPUT_INVALID", str(exc))
    if completed.returncode != 0 or completed.stderr or inner.get("status") != "PASS":
        return refusal("MEASURED_VERIFIER_REFUSED", json.dumps(inner, sort_keys=True)[:1024])
    if inner.get("bootstrapAuthenticated") is not False:
        return refusal("INNER_BOOTSTRAP_CLAIM_INVALID", "direct verifier claimed bootstrap authentication")
    stored = verifier.read_bytes()
    if stored != measured:
        return refusal("STORED_VERIFIER_MEMBER_MISMATCH", str(verifier))
    outer = dict(inner)
    outer.update({
        "schema": "axm-head/browser-physical-audition-operator-console-bootstrap@1",
        "bootstrapAuthenticated": True,
        "storedVerifierMemberBound": True,
        "measuredVerifierSha256": digest,
    })
    sys.stdout.buffer.write(pretty(outer))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
