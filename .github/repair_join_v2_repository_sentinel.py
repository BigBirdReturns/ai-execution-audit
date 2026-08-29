from __future__ import annotations

from pathlib import Path
import hashlib

root = Path.cwd()
verifier_path = root / "mating_surface/anchor_node/verify_axm_head_physical_long_haul_001_join_v2.py"
builder_path = root / "mating_surface/anchor_node/axm_head_physical_long_haul_001_join_v2.py"
bootstrap_path = root / "mating_surface/anchor_node/verify_axm_head_physical_long_haul_001_join_v2_bootstrap.py"
contract_path = root / "mating_surface/anchor_node/AXM-HEAD-PHYSICAL-LONG-HAUL-001-JOIN-v2.md"

old_digest = "ab7d043faf7155880bd025ac2b9bd03400ce8c0b11df2fb5c49e4fb521074289"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one replacement target, found {count}")
    return text.replace(old, new, 1)


verifier = verifier_path.read_text(encoding="utf-8")
verifier = replace_once(
    verifier,
    'def containing_git_repository(path: Path) -> Path | None:\n'
    '    candidate = path if path.is_dir() else path.parent\n'
    '    for ancestor in (candidate, *candidate.parents):\n'
    '        if (ancestor / ".git").exists():\n'
    '            return ancestor.resolve()\n'
    '    return None\n',
    'REPOSITORY_SENTINELS = (\n'
    '    ".github/workflows/axm-head-physical-long-haul-001-join-v2.yml",\n'
    '    "mating_surface/anchor_node/AXM-HEAD-PHYSICAL-LONG-HAUL-001-JOIN-v2.md",\n'
    ')\n'
    '\n'
    '\n'
    'def is_join_repository_root(path: Path) -> bool:\n'
    '    if (path / ".git").exists():\n'
    '        return True\n'
    '    return all((path / Path(*relative.split("/"))).is_file() for relative in REPOSITORY_SENTINELS)\n'
    '\n'
    '\n'
    'def containing_join_repository(path: Path) -> Path | None:\n'
    '    candidate = path if path.is_dir() else path.parent\n'
    '    for ancestor in (candidate, *candidate.parents):\n'
    '        if is_join_repository_root(ancestor):\n'
    '            return ancestor.resolve()\n'
    '    return None\n',
    "repository sentinel detector",
)
verifier = replace_once(
    verifier,
    '    if (source_repository / ".git").exists() and (\n'
    '        out_resolved == source_repository or source_repository in out_resolved.parents\n'
    '    ):',
    '    if is_join_repository_root(source_repository) and (\n'
    '        out_resolved == source_repository or source_repository in out_resolved.parents\n'
    '    ):',
    "source repository sentinel check",
)
verifier = replace_once(
    verifier,
    '    output_repository = containing_git_repository(out_resolved)\n',
    '    output_repository = containing_join_repository(out_resolved)\n',
    "output repository sentinel check",
)
new_digest = hashlib.sha256(verifier.encode("utf-8")).hexdigest()

builder = builder_path.read_text(encoding="utf-8")
bootstrap = bootstrap_path.read_text(encoding="utf-8")
contract = contract_path.read_text(encoding="utf-8")
for label, text in (("builder", builder), ("bootstrap", bootstrap), ("contract", contract)):
    count = text.count(old_digest)
    if count != 1:
        raise SystemExit(f"{label}: expected one old verifier digest, found {count}")
builder = builder.replace(old_digest, new_digest)
bootstrap = bootstrap.replace(old_digest, new_digest)
contract = contract.replace(old_digest, new_digest)
contract = replace_once(
    contract,
    "repository-local builder, bootstrap, and direct-verifier output",
    "repository-local builder, bootstrap, and direct-verifier output in both live checkouts and exact Git-blob materializations",
    "repository materialization documentation",
)

verifier_path.write_text(verifier, encoding="utf-8", newline="\n")
builder_path.write_text(builder, encoding="utf-8", newline="\n")
bootstrap_path.write_text(bootstrap, encoding="utf-8", newline="\n")
contract_path.write_text(contract, encoding="utf-8", newline="\n")

print(f"new standalone verifier sha256: {new_digest}")
