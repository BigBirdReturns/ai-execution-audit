from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path, PurePosixPath

EXPECTED_SHA256 = {
    "mating_surface/anchor_node/rpm-agent-evidence-membrane-profile-01.json": "3356356d2018936e14a34daa95474ddb53da8bb466403e7575d1d9bfaf279ca2",
    "mating_surface/anchor_node/rpm_agent_effects.py": "0e2e2389f2f846e3da7d9dce4c0f890e8c87ded4a7270f3e6722d9bdf339f652",
    "mating_surface/anchor_node/rpm_agent_estate_qualifier.py": "02d030807bb885765cb7b480f055af40c9c35d9a4f35582afc80e31a40f987ec",
    "mating_surface/anchor_node/verify_rpm_agent_estate_receipt.py": "b47213ca353a77fb36afb26cd467b28dd85707bdd8171d0cab6a1f5747b2f4ee",
}
QUALIFIER_PATH = "mating_surface/anchor_node/rpm_agent_estate_qualifier.py"


class BootstrapError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_measured_regular_file(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or not pure.parts or ".." in pure.parts:
        raise BootstrapError(f"measured path is unsafe: {relative}")
    if root.is_symlink():
        raise BootstrapError("measured root cannot be a symlink")

    cursor = root
    for part in pure.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise BootstrapError(f"measured path traverses a symlink: {relative}")

    try:
        root_resolved = root.resolve(strict=True)
        resolved = cursor.resolve(strict=True)
        resolved.relative_to(root_resolved)
    except (OSError, ValueError) as exc:
        raise BootstrapError(f"measured file is missing or escapes root: {relative}") from exc
    if not resolved.is_file():
        raise BootstrapError(f"measured file is not regular: {relative}")
    return resolved


def validate_bootstrap_files(root: Path) -> None:
    for relative, expected in EXPECTED_SHA256.items():
        path = resolve_measured_regular_file(root, relative)
        actual = sha256_file(path)
        if actual != expected:
            raise BootstrapError(
                f"measured file digest mismatch for {relative}: expected {expected}, observed {actual}"
            )


def main(argv: list[str] | None = None) -> int:
    forwarded = list(sys.argv[1:] if argv is None else argv)
    root = Path(__file__).resolve().parents[2]
    try:
        validate_bootstrap_files(root)
    except BootstrapError as exc:
        print(f"bootstrap refused: {exc}", file=sys.stderr)
        return 2

    qualifier = root / QUALIFIER_PATH
    completed = subprocess.run([sys.executable, str(qualifier), *forwarded], check=False)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
