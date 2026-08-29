from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

OLD_TO_NEW = {
    ".github/workflows/axm-head-physical-long-haul-001-join-v2.yml":
        ".github/workflows/axm-head-physical-flight-preflight-review-card-01.yml",
    "mating_surface/anchor_node/AXM-HEAD-PHYSICAL-LONG-HAUL-001-JOIN-v2.md":
        "mating_surface/anchor_node/AXM-HEAD-PHYSICAL-FLIGHT-PREFLIGHT-REVIEW-CARD-01.md",
    "mating_surface/anchor_node/axm-head-physical-long-haul-001-join-v2-profile.json":
        "mating_surface/anchor_node/axm-head-physical-flight-preflight-review-card-01-profile.json",
    "mating_surface/anchor_node/axm-head-physical-long-haul-001-join-v2.ps1":
        "mating_surface/anchor_node/axm-head-physical-flight-preflight-review-card-01.ps1",
    "mating_surface/anchor_node/axm_head_physical_long_haul_001_join_v2.py":
        "mating_surface/anchor_node/axm_head_physical_flight_preflight_review_card_01.py",
    "mating_surface/anchor_node/verify_axm_head_physical_long_haul_001_join_v2.py":
        "mating_surface/anchor_node/verify_axm_head_physical_flight_preflight_review_card_01.py",
    "mating_surface/anchor_node/verify_axm_head_physical_long_haul_001_join_v2_bootstrap.py":
        "mating_surface/anchor_node/verify_axm_head_physical_flight_preflight_review_card_01_bootstrap.py",
    "mating_surface/anchor_node/conformance/test_axm_head_physical_long_haul_001_join_v2.py":
        "mating_surface/anchor_node/conformance/test_axm_head_physical_flight_preflight_review_card_01.py",
}

OLD_PROFILE_DIGEST_RE = re.compile(r'PROFILE_CANONICAL_SHA256 = "([0-9a-f]{64})"')
OLD_VERIFIER_DIGEST_RE = re.compile(r'STANDALONE_VERIFIER_SHA256 = "([0-9a-f]{64})"')

OLD_CLAIM_BOUNDARY = (
    "Public preflight join binding the admitted AXM HEAD mission-volume contract to the admitted STC MARY "
    "conductor, frozen physical-flight floor, and sole issue #37 execution coordinate. It may validate body-free "
    "private coordinate headers and compile an exact operator card, but it performs no physical action, materializes "
    "no mission volume, launches no worker, creates no listener, grants no authorization, and establishes no physical "
    "Estate, representative operator, field network, operational C2, production Lattice, mission, command, targeting, "
    "engagement, effector, or weapons qualification or authority."
)
NEW_CLAIM_BOUNDARY = (
    "Public physical-flight preflight review-card contract binding the admitted AXM HEAD mission-volume contract to "
    "the admitted STC MARY conductor, frozen physical-flight floor, and sole issue #37 execution coordinate. It may "
    "validate body-free private coordinate headers and compile an exact unauthorized operator card for separate "
    "named-human review, but it performs no physical action, materializes no mission volume, launches no worker, "
    "creates no listener, grants no authorization, consumes no private evidence body, and establishes no physical "
    "Estate, representative operator, field network, operational C2, production Lattice, mission, command, targeting, "
    "engagement, effector, or weapons qualification or authority."
)

REPLACEMENTS = (
    (OLD_CLAIM_BOUNDARY, NEW_CLAIM_BOUNDARY),
    (
        "Build and evaluate AXM HEAD physical long-haul JOIN-v2",
        "Build and evaluate the AXM HEAD physical-flight preflight review-card contract",
    ),
    (
        "Verify one AXM HEAD physical long-haul JOIN-v2 carrier",
        "Verify one AXM HEAD physical-flight preflight review-card carrier",
    ),
    (
        "Authenticate and invoke the JOIN-v2 standalone verifier",
        "Authenticate and invoke the preflight review-card standalone verifier",
    ),
    (
        "axm-head-physical-long-haul-001-join-v2-profile/2",
        "axm-head/physical-flight-preflight-review-card-profile/1",
    ),
    (
        "axm-head/physical-long-haul-001/join-v2",
        "axm-head/physical-flight-preflight-review-card@1",
    ),
    (
        "axm-head/physical-long-haul-001-join-state@2",
        "axm-head/physical-flight-preflight-review-card-state@1",
    ),
    (
        "axm-head/physical-operator-card@2",
        "axm-head/physical-flight-preflight-operator-card@1",
    ),
    (
        "axm-head/physical-long-haul-001-join-decision@2",
        "axm-head/physical-flight-preflight-review-decision@1",
    ),
    (
        "axm-head/physical-long-haul-001-public-status@2",
        "axm-head/physical-flight-preflight-public-status@1",
    ),
    (
        "axm-head/physical-long-haul-001-join-manifest@2",
        "axm-head/physical-flight-preflight-review-card-manifest@1",
    ),
    (
        "axm-head/physical-long-haul-001-join-verdict@2",
        "axm-head/physical-flight-preflight-review-card-verdict@1",
    ),
    (
        "axm-head/physical-long-haul-source-coordinate@2",
        "axm-head/physical-flight-preflight-source-coordinate@1",
    ),
    (
        "axm-head/physical-long-haul-join-qualification@2",
        "axm-head/physical-flight-preflight-review-card-qualification@1",
    ),
    (
        "axm-head/physical-long-haul-cross-coordinate-qualification@2",
        "axm-head/physical-flight-preflight-review-card-cross-coordinate-qualification@1",
    ),
    ("AXM_HEAD_JOIN_V2_BOOTSTRAP_AUTHENTICATED", "AXM_HEAD_PREFLIGHT_REVIEW_CARD_01_BOOTSTRAP_AUTHENTICATED"),
    ("AXM_HEAD_JOIN_V2_VERIFIER_SHA256", "AXM_HEAD_PREFLIGHT_REVIEW_CARD_01_VERIFIER_SHA256"),
    ("AXM_HEAD_JOIN_V2_PYTHON", "AXM_HEAD_PREFLIGHT_REVIEW_CARD_01_PYTHON"),
    ("<authenticated-join-v2-verifier>", "<authenticated-preflight-review-card-01-verifier>"),
    ("joinContractId", "preflightContractId"),
    ("join_contract_id", "preflight_contract_id"),
    ("STATE_JOIN_BINDING_INVALID", "STATE_PREFLIGHT_BINDING_INVALID"),
    ("MANIFEST_JOIN_ID_INVALID", "MANIFEST_PREFLIGHT_ID_INVALID"),
    ("JoinV2Tests", "PreflightReviewCard01Tests"),
    ("JoinError", "PreflightError"),
    ("is_join_repository_root", "is_preflight_repository_root"),
    ("containing_join_repository", "containing_preflight_repository"),
    ("axmheadphysjoin2", "axmheadpreflightcontract1"),
    ("axmheadjoinbasis2", "axmheadpreflightbasis1"),
    ("axmheadjoinstate2", "axmheadpreflightstate1"),
    ("axmheadjoincheckouts2", "axmheadpreflightcheckouts1"),
    ("axmheadjoinprivatecoords2", "axmheadpreflightprivatecoords1"),
    ("axmheadoperatorcard2", "axmheadpreflightcard1"),
    ("axmheadjoindecision2", "axmheadpreflightdecision1"),
    ("axmheadjoincarrier2", "axmheadpreflightcarrier1"),
    ("JOIN/preparation-state.json", "PREFLIGHT/preparation-state.json"),
    ("JOIN/decision.json", "PREFLIGHT/decision.json"),
    ("RECOVERY/verify_join.py", "RECOVERY/verify_preflight.py"),
    ("verify_join.py", "verify_preflight.py"),
    ("JOIN/\n", "PREFLIGHT/\n"),
    ("AXM HEAD Physical Long Haul 001 Join v2", "AXM HEAD Physical Flight Preflight Review Card 01"),
    ("AXM-HEAD-PHYSICAL-LONG-HAUL-001-JOIN-v2", "AXM-HEAD-PHYSICAL-FLIGHT-PREFLIGHT-REVIEW-CARD-01"),
    ("axm-head-physical-long-haul-001-join-v2", "axm-head-physical-flight-preflight-review-card-01"),
    ("axm_head_physical_long_haul_001_join_v2", "axm_head_physical_flight_preflight_review_card_01"),
    ("JoinV2", "PreflightReviewCard01"),
    ("join_v2", "preflight_review_card_01"),
    ("JOIN-v2", "PREFLIGHT-REVIEW-CARD-01"),
    ("join-v2", "preflight-review-card-01"),
    ("JOIN v2", "Preflight Review Card 01"),
    ("Physical Long Haul", "Physical Flight Preflight"),
    ("physical long-haul", "physical-flight preflight"),
    ("Public preflight join", "Public physical-flight preflight review-card contract"),
    ("public preflight join", "public physical-flight preflight review-card contract"),
    ("This join", "This preflight review-card contract"),
    ("this join", "this preflight review-card contract"),
    ("The join", "The preflight review-card contract"),
    ("the join", "the preflight review-card contract"),
    ("join's authority", "preflight contract's authority"),
    ("join contract", "preflight contract"),
    ("join source", "preflight source"),
    ("join floor", "preflight floor"),
    ("join carrier", "preflight carrier"),
    ("join state", "preflight state"),
    ("join decision", "preflight decision"),
    ("join profile", "preflight profile"),
    ("join verdict", "preflight verdict"),
)

FORBIDDEN_FINAL_TOKENS = (
    "axm-head-physical-long-haul-001-join-v2",
    "AXM-HEAD-PHYSICAL-LONG-HAUL-001-JOIN-v2",
    "axm_head_physical_long_haul_001_join_v2",
    "physical-long-haul-001-join",
    "physical-long-haul",
    "JOIN-v2",
    "join-v2",
    "join_v2",
    "JoinV2",
    "joinContractId",
    "join_contract_id",
    "axmheadjoin",
    "axmheadphysjoin",
    "AXM_HEAD_JOIN_V2",
    "JOIN/preparation-state.json",
    "JOIN/decision.json",
    "verify_join.py",
    "Public preflight join",
    "public preflight join",
)

NEW_PROFILE_SCHEMA = "axm-head/physical-flight-preflight-review-card-profile/1"
NEW_PROFILE_ID = "axm-head/physical-flight-preflight-review-card@1"


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n"
    ).encode("utf-8")


def read_lf_text(path: Path) -> str:
    data = path.read_bytes()
    if b"\r" in data:
        raise SystemExit(f"non-LF source refused: {path.relative_to(ROOT).as_posix()}")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SystemExit(f"non-UTF-8 source refused: {path}: {exc}") from exc


def write_lf_text(path: Path, text: str) -> None:
    if "\r" in text:
        raise SystemExit(f"generated CR refused: {path.relative_to(ROOT).as_posix()}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def replace_all(text: str) -> str:
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    return text


def replace_digest_everywhere(paths: list[Path], old: str, new: str, label: str) -> None:
    count = 0
    for path in paths:
        text = read_lf_text(path)
        occurrences = text.count(old)
        if occurrences:
            write_lf_text(path, text.replace(old, new))
            count += occurrences
    if count == 0:
        raise SystemExit(f"{label} digest was not present in transformed product")


def main() -> int:
    if not (ROOT / ".git").exists():
        raise SystemExit("repository working tree required")

    old_builder = ROOT / "mating_surface/anchor_node/axm_head_physical_long_haul_001_join_v2.py"
    builder_text = read_lf_text(old_builder)
    profile_match = OLD_PROFILE_DIGEST_RE.search(builder_text)
    verifier_match = OLD_VERIFIER_DIGEST_RE.search(builder_text)
    if profile_match is None or verifier_match is None:
        raise SystemExit("unable to recover predecessor digest identities")
    old_profile_digest = profile_match.group(1)
    old_verifier_digest = verifier_match.group(1)

    for old_relative, new_relative in OLD_TO_NEW.items():
        old_path = ROOT / old_relative
        new_path = ROOT / new_relative
        if not old_path.is_file():
            raise SystemExit(f"missing predecessor member: {old_relative}")
        if new_path.exists():
            raise SystemExit(f"successor member already exists: {new_relative}")
        transformed = replace_all(read_lf_text(old_path))
        write_lf_text(new_path, transformed)
        old_path.unlink()

    new_paths = [ROOT / relative for relative in OLD_TO_NEW.values()]
    profile_path = ROOT / "mating_surface/anchor_node/axm-head-physical-flight-preflight-review-card-01-profile.json"
    builder_path = ROOT / "mating_surface/anchor_node/axm_head_physical_flight_preflight_review_card_01.py"
    verifier_path = ROOT / "mating_surface/anchor_node/verify_axm_head_physical_flight_preflight_review_card_01.py"
    bootstrap_path = ROOT / "mating_surface/anchor_node/verify_axm_head_physical_flight_preflight_review_card_01_bootstrap.py"

    profile = json.loads(read_lf_text(profile_path))
    if not isinstance(profile, dict):
        raise SystemExit("profile must remain one JSON object")
    if profile.get("schema") != NEW_PROFILE_SCHEMA or profile.get("profileId") != NEW_PROFILE_ID:
        raise SystemExit("reclassified profile identity differs")
    if profile.get("claimBoundary") != NEW_CLAIM_BOUNDARY:
        raise SystemExit("reclassified claim boundary differs")
    new_profile_digest = hashlib.sha256(canonical_json_bytes(profile)).hexdigest()
    replace_digest_everywhere(new_paths, old_profile_digest, new_profile_digest, "profile")

    verifier_bytes = verifier_path.read_bytes()
    if b"\r" in verifier_bytes:
        raise SystemExit("reclassified verifier contains CR bytes")
    new_verifier_digest = hashlib.sha256(verifier_bytes).hexdigest()
    replace_digest_everywhere(new_paths, old_verifier_digest, new_verifier_digest, "verifier")

    combined_parts: list[str] = []
    for path in new_paths:
        text = read_lf_text(path)
        combined_parts.append(text)
        if path.suffix == ".py":
            ast.parse(text, filename=str(path))
    combined = "\n".join(combined_parts)
    for token in FORBIDDEN_FINAL_TOKENS:
        if token in combined:
            raise SystemExit(f"predecessor identity survived reclassification: {token}")

    required_tokens = (
        "AXM HEAD Physical Flight Preflight Review Card 01",
        "axm-head/physical-flight-preflight-review-card@1",
        "preflightContractId",
        "PREFLIGHT/preparation-state.json",
        "RECOVERY/verify_preflight.py",
        "READY_FOR_HUMAN_REVIEW",
        "physicalAuthorizationProduced",
        "authority",
    )
    for token in required_tokens:
        if token not in combined:
            raise SystemExit(f"required successor identity absent: {token}")

    builder = read_lf_text(builder_path)
    verifier = read_lf_text(verifier_path)
    bootstrap = read_lf_text(bootstrap_path)
    if f'PROFILE_CANONICAL_SHA256 = "{new_profile_digest}"' not in builder:
        raise SystemExit("builder profile digest differs")
    if f'PROFILE_CANONICAL_SHA256 = "{new_profile_digest}"' not in verifier:
        raise SystemExit("verifier profile digest differs")
    if f'STANDALONE_VERIFIER_SHA256 = "{new_verifier_digest}"' not in builder:
        raise SystemExit("builder verifier digest differs")
    if f'EXPECTED_VERIFIER_SHA256 = "{new_verifier_digest}"' not in bootstrap:
        raise SystemExit("bootstrap verifier digest differs")

    workflow_path = ROOT / ".github/workflows/axm-head-physical-flight-preflight-review-card-01.yml"
    workflow = read_lf_text(workflow_path)
    if "permissions:\n  contents: read\n" not in workflow:
        raise SystemExit("permanent workflow must remain read-only")

    print(
        json.dumps(
            {
                "status": "PASS",
                "oldProfileSha256": old_profile_digest,
                "newProfileSha256": new_profile_digest,
                "oldVerifierSha256": old_verifier_digest,
                "newVerifierSha256": new_verifier_digest,
                "oldPathCount": len(OLD_TO_NEW),
                "newPathCount": len(new_paths),
                "authority": "none",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
