from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/axm-head-physical-flight-preflight-review-card-01.yml"
CONTRACT = ROOT / "mating_surface/anchor_node/AXM-HEAD-PHYSICAL-FLIGHT-PREFLIGHT-REVIEW-CARD-01.md"


def read_lf(path: Path) -> str:
    data = path.read_bytes()
    if b"\r" in data:
        raise SystemExit(f"CR bytes refused: {path.relative_to(ROOT).as_posix()}")
    return data.decode("utf-8")


def write_lf(path: Path, text: str) -> None:
    if "\r" in text:
        raise SystemExit(f"generated CR refused: {path.relative_to(ROOT).as_posix()}")
    path.write_bytes(text.encode("utf-8"))


def replace_exact(text: str, old: str, new: str, expected: int, label: str) -> str:
    observed = text.count(old)
    if observed != expected:
        raise SystemExit(f"{label} denominator differs: expected={expected} observed={observed}")
    return text.replace(old, new)


def main() -> int:
    workflow = read_lf(WORKFLOW)
    contract = read_lf(CONTRACT)

    workflow = replace_exact(
        workflow,
        "axm-head-physical-flight-preflight-preflight-review-card-01",
        "axm-head-physical-flight-preflight-review-card-01",
        4,
        "duplicated preflight workflow identity",
    )

    axm_old = '''            python -m unittest discover \\
              -s mating_surface/anchor_node/conformance \\
              -p 'test_axm_head_edge_demo.py' \\
              -v 2>&1 | tee "$DEST/inherited-axm-head-tests.txt"
            python -m unittest discover \\
'''
    axm_new = '''            python -m unittest discover \\
              -s mating_surface/anchor_node/conformance \\
              -p 'test_axm_head_edge_demo.py' \\
              -v 2>&1 | tee "$DEST/inherited-axm-head-tests.txt"
            grep -F "Ran 38 tests" "$DEST/inherited-axm-head-tests.txt"
            grep -Fx "OK" "$DEST/inherited-axm-head-tests.txt"

            python -m unittest discover \\
'''
    workflow = replace_exact(workflow, axm_old, axm_new, 1, "inherited AXM witness binding")

    conductor_old = '''            python -m unittest discover \\
              -s mating_surface/anchor_node/conformance \\
              -p 'test_stc_mary_flight_conductor.py' \\
              -v 2>&1 | tee "$DEST/inherited-conductor-tests.txt"

            CARRIER='''
    conductor_new = '''            python -m unittest discover \\
              -s mating_surface/anchor_node/conformance \\
              -p 'test_stc_mary_flight_conductor.py' \\
              -v 2>&1 | tee "$DEST/inherited-conductor-tests.txt"
            grep -F "Ran 25 tests" "$DEST/inherited-conductor-tests.txt"
            grep -Fx "OK" "$DEST/inherited-conductor-tests.txt"

            CARRIER='''
    workflow = replace_exact(workflow, conductor_old, conductor_new, 1, "inherited conductor witness binding")

    contract = replace_exact(
        contract,
        "The preparation state binds the preflight review-card contract contract, exact source coordinates",
        "The preparation state binds the preflight review-card contract, exact source coordinates",
        1,
        "contract wording repair",
    )

    if "preflight-preflight" in workflow:
        raise SystemExit("duplicated preflight identity survived")
    for marker in (
        'grep -F "Ran 49 tests" "$DEST/preflight-review-card-01-tests.txt"',
        'grep -F "Ran 38 tests" "$DEST/inherited-axm-head-tests.txt"',
        'grep -F "Ran 25 tests" "$DEST/inherited-conductor-tests.txt"',
    ):
        if workflow.count(marker) != 1:
            raise SystemExit(f"witness marker denominator differs: {marker}")
    if "contract contract" in contract:
        raise SystemExit("duplicated contract wording survived")

    write_lf(WORKFLOW, workflow)
    write_lf(CONTRACT, contract)
    print("workflowWitnessDenominators=49,38,25 duplicatedIdentity=0 contractWording=PASS authority=none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
