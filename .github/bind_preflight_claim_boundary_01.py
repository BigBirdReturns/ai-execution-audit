from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

NEW_PATHS = (
    ".github/workflows/axm-head-physical-flight-preflight-review-card-01.yml",
    "mating_surface/anchor_node/AXM-HEAD-PHYSICAL-FLIGHT-PREFLIGHT-REVIEW-CARD-01.md",
    "mating_surface/anchor_node/axm-head-physical-flight-preflight-review-card-01-profile.json",
    "mating_surface/anchor_node/axm-head-physical-flight-preflight-review-card-01.ps1",
    "mating_surface/anchor_node/axm_head_physical_flight_preflight_review_card_01.py",
    "mating_surface/anchor_node/verify_axm_head_physical_flight_preflight_review_card_01.py",
    "mating_surface/anchor_node/verify_axm_head_physical_flight_preflight_review_card_01_bootstrap.py",
    "mating_surface/anchor_node/conformance/test_axm_head_physical_flight_preflight_review_card_01.py",
)

BUILDER = ROOT / "mating_surface/anchor_node/axm_head_physical_flight_preflight_review_card_01.py"
VERIFIER = ROOT / "mating_surface/anchor_node/verify_axm_head_physical_flight_preflight_review_card_01.py"
BOOTSTRAP = ROOT / "mating_surface/anchor_node/verify_axm_head_physical_flight_preflight_review_card_01_bootstrap.py"

CLAIM_BOUNDARY = (
    "Public physical-flight preflight review-card contract binding the admitted AXM HEAD mission-volume contract to "
    "the admitted STC MARY conductor, frozen physical-flight floor, and sole issue #37 execution coordinate. It may "
    "validate body-free private coordinate headers and compile an exact unauthorized operator card for separate "
    "named-human review, but it performs no physical action, materializes no mission volume, launches no worker, "
    "creates no listener, grants no authorization, consumes no private evidence body, and establishes no physical "
    "Estate, representative operator, field network, operational C2, production Lattice, mission, command, targeting, "
    "engagement, effector, or weapons qualification or authority."
)

CLAIM_BLOCK = '''CLAIM_BOUNDARY = (
    "Public physical-flight preflight review-card contract binding the admitted AXM HEAD mission-volume contract to "
    "the admitted STC MARY conductor, frozen physical-flight floor, and sole issue #37 execution coordinate. It may "
    "validate body-free private coordinate headers and compile an exact unauthorized operator card for separate "
    "named-human review, but it performs no physical action, materializes no mission volume, launches no worker, "
    "creates no listener, grants no authorization, consumes no private evidence body, and establishes no physical "
    "Estate, representative operator, field network, operational C2, production Lattice, mission, command, targeting, "
    "engagement, effector, or weapons qualification or authority."
)'''

CLAIM_RE = re.compile(r'^CLAIM_BOUNDARY = \(\n(?:    "[^"\n]*"\n)+\)', re.MULTILINE)
VERIFIER_DIGEST_RE = re.compile(r'STANDALONE_VERIFIER_SHA256 = "([0-9a-f]{64})"')


def read_text(path: Path) -> str:
    data = path.read_bytes()
    if b"\r" in data:
        raise SystemExit(f"CR bytes refused: {path.relative_to(ROOT).as_posix()}")
    return data.decode("utf-8")


def write_text(path: Path, text: str) -> None:
    if "\r" in text:
        raise SystemExit(f"generated CR refused: {path.relative_to(ROOT).as_posix()}")
    path.write_bytes(text.encode("utf-8"))


def assignment_value(path: Path, name: str):
    tree = ast.parse(read_text(path), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            return ast.literal_eval(node.value)
    raise SystemExit(f"assignment absent: {path.name}:{name}")


def replace_digest(paths: list[Path], old: str, new: str) -> int:
    count = 0
    for path in paths:
        text = read_text(path)
        occurrences = text.count(old)
        if occurrences:
            write_text(path, text.replace(old, new))
            count += occurrences
    return count


def main() -> int:
    paths = [ROOT / relative for relative in NEW_PATHS]
    for path in paths:
        if not path.is_file():
            raise SystemExit(f"reclassified member missing: {path.relative_to(ROOT).as_posix()}")

    for path in (BUILDER, VERIFIER):
        text = read_text(path)
        rewritten, count = CLAIM_RE.subn(CLAIM_BLOCK, text, count=1)
        if count != 1:
            raise SystemExit(f"claim-boundary assignment denominator differs: {path.name}:{count}")
        write_text(path, rewritten)
        if assignment_value(path, "CLAIM_BOUNDARY") != CLAIM_BOUNDARY:
            raise SystemExit(f"claim-boundary value differs: {path.name}")

    builder_text = read_text(BUILDER)
    match = VERIFIER_DIGEST_RE.search(builder_text)
    if match is None:
        raise SystemExit("intermediate verifier digest absent from builder")
    intermediate_digest = match.group(1)
    final_digest = hashlib.sha256(VERIFIER.read_bytes()).hexdigest()
    replaced = replace_digest(paths, intermediate_digest, final_digest)
    if replaced < 3:
        raise SystemExit(f"verifier digest denominator incomplete: {replaced}")

    if f'STANDALONE_VERIFIER_SHA256 = "{final_digest}"' not in read_text(BUILDER):
        raise SystemExit("builder verifier digest differs after claim binding")
    if f'EXPECTED_VERIFIER_SHA256 = "{final_digest}"' not in read_text(BOOTSTRAP):
        raise SystemExit("bootstrap verifier digest differs after claim binding")
    if hashlib.sha256(VERIFIER.read_bytes()).hexdigest() != final_digest:
        raise SystemExit("verifier bytes moved after digest binding")

    print(f"claimBoundary=bound verifierSha256={final_digest} authority=none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
