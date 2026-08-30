from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ANCHOR = Path("mating_surface/anchor_node")
PROFILE = ANCHOR / "stc-mary-flight-01-cartridge-profile-01.json"
VERIFIER = ANCHOR / "verify_stc_mary_flight_01_cartridge.py"
BUILDER = ANCHOR / "stc_mary_flight_01_cartridge.py"
BOOTSTRAP = ANCHOR / "verify_stc_mary_flight_01_cartridge_bootstrap.py"
TESTS = ANCHOR / "conformance/test_stc_mary_flight_01_cartridge.py"
RUNBOOK = ANCHOR / "STC-MARY-FLIGHT-01-CARTRIDGE-01.md"

OLD_PROFILE = "b6bccd589208dee38beb9b9a499b40f819de558efbae7b3e722d32b607478385"
OLD_VERIFIER = "8b05e211911ee30204ff0d4a07a3448d27228a9e1920380ca4df5a43049e0f5d"


def canonical_json_bytes(value):
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one replacement anchor, found {count}")
    return text.replace(old, new, 1)


profile = json.loads(PROFILE.read_text(encoding="utf-8"))
source_coordinates = profile.get("sourceCoordinates")
if not isinstance(source_coordinates, dict):
    raise SystemExit("profile sourceCoordinates missing")
removed = source_coordinates.pop("flightConductor", None)
if not isinstance(removed, dict):
    raise SystemExit("flightConductor semantic source was not present exactly once")
profile["claimBoundary"] = (
    "Immutable public mission-law cartridge for STC MARY private physical flight 01. "
    "It binds the admitted MARY tenant, AXM supplier, preflight contract, frozen execution "
    "floor, mission denominator, work-unit law, named-human boundary, and authority-none "
    "invariants. Compatible conductor implementations and their repair lineage are "
    "non-authoritative operator provenance outside the cartridge semantic identity. "
    "The cartridge contains no private coordinate, evidence body, observation, telemetry, "
    "authorization, host identity, model bytes, verifier bytes, storage identity, execution "
    "result, physical qualification, representative-operator qualification, field-network "
    "qualification, operational-C2 qualification, production-Lattice qualification, mission "
    "authority, command authority, targeting, engagement, effector, or weapons capability."
)
PROFILE.write_text(
    json.dumps(profile, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
    newline="\n",
)
profile_sha = hashlib.sha256(canonical_json_bytes(profile)).hexdigest()

verifier = VERIFIER.read_text(encoding="utf-8")
verifier = replace_once(
    verifier,
    f'PROFILE_CANONICAL_SHA256 = "{OLD_PROFILE}"',
    f'PROFILE_CANONICAL_SHA256 = "{profile_sha}"',
    "verifier profile digest",
)
issue_anchor = (
    '    if profile["issueBindings"] != {"privateFlight": 37, "postflightJoin": 49}:\n'
    '        fail("ISSUE_BINDING_INVALID", "issue bindings differ")\n'
)
source_validation = issue_anchor + (
    '    source_coordinates = profile["sourceCoordinates"]\n'
    '    require_exact_keys(\n'
    '        source_coordinates,\n'
    '        {\n'
    '            "maryPortable",\n'
    '            "axmHeadSupplier",\n'
    '            "physicalFlightPreflight",\n'
    '            "physicalFlightExecutionFloor",\n'
    '        },\n'
    '        "profile.sourceCoordinates",\n'
    '    )\n'
    '    if "flightConductor" in source_coordinates:\n'
    '        fail("CONDUCTOR_SEMANTIC_COUPLING_REFUSED", "operator provenance may not enter cartridge semantic identity")\n'
)
verifier = replace_once(
    verifier,
    issue_anchor,
    source_validation,
    "source-coordinate validation",
)
VERIFIER.write_text(verifier, encoding="utf-8", newline="\n")
verifier_sha = hashlib.sha256(VERIFIER.read_bytes()).hexdigest()

builder = BUILDER.read_text(encoding="utf-8")
builder = replace_once(
    builder,
    f'EXPECTED_VERIFIER_SHA256 = "{OLD_VERIFIER}"',
    f'EXPECTED_VERIFIER_SHA256 = "{verifier_sha}"',
    "builder verifier digest",
)
BUILDER.write_text(builder, encoding="utf-8", newline="\n")

bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
bootstrap = replace_once(
    bootstrap,
    f'EXPECTED_EMBEDDED_VERIFIER_SHA256 = "{OLD_VERIFIER}"',
    f'EXPECTED_EMBEDDED_VERIFIER_SHA256 = "{verifier_sha}"',
    "bootstrap verifier digest",
)
BOOTSTRAP.write_text(bootstrap, encoding="utf-8", newline="\n")

tests = TESTS.read_text(encoding="utf-8")
tests = replace_once(
    tests,
    f'self.assertEqual(verifier.PROFILE_CANONICAL_SHA256, "{OLD_PROFILE}")',
    f'self.assertEqual(verifier.PROFILE_CANONICAL_SHA256, "{profile_sha}")',
    "test profile digest",
)
tests = replace_once(
    tests,
    '            value["sourceCoordinates"]["flightConductor"]["commit"] = "0" * 40',
    '            value["sourceCoordinates"]["axmHeadSupplier"]["commit"] = "0" * 40',
    "semantic source mutation witness",
)
test06_anchor = (
    '        self.assertEqual(mission["workUnitId"], work["workUnitId"])\n'
    '        self.assertEqual(mission["sourceBindingId"], source["sourceBindingId"])\n'
    '        self.assertEqual(self.build["cartridgeId"], mission["cartridgeId"])\n'
)
test06_expanded = test06_anchor + (
    '        profile = load_json(PROFILE)\n'
    '        self.assertNotIn("flightConductor", profile["sourceCoordinates"])\n'
    '        self.assertNotIn("flightConductor", source["sourceCoordinates"])\n'
    '        provenance_before = {"activeConductor": "772ce582e1b19b7a2060c50be8ebf40c1f8723b2"}\n'
    '        provenance_after = {"activeConductor": "dd486472a8c610a20ee062dd6746c86fe8ede4b4"}\n'
    '        self.assertNotEqual(provenance_before, provenance_after)\n'
    '        other = self.parent / "cartridge-provenance-independent"\n'
    '        rebuilt = tool.build_cartridge(PROFILE, other)\n'
    '        self.assertEqual(self.build["bundleId"], rebuilt["bundleId"])\n'
    '        self.assertEqual(self.build["cartridgeId"], rebuilt["cartridgeId"])\n'
    '        self.assertEqual(self.build["missionId"], rebuilt["missionId"])\n'
    '        self.assertEqual(self.build["workUnitId"], rebuilt["workUnitId"])\n'
    '        self.assertEqual(self.build["sourceBindingId"], rebuilt["sourceBindingId"])\n'
)
tests = replace_once(
    tests,
    test06_anchor,
    test06_expanded,
    "operator-provenance independence witness",
)
TESTS.write_text(tests, encoding="utf-8", newline="\n")

runbook = RUNBOOK.read_text(encoding="utf-8")
source_section = re.compile(r"## Exact source graph\n\n.*?\n## Cartridge law\n", re.S)
replacement = """## Semantic source graph

The cartridge semantic identity freezes exactly four public source roles:

```text
MARY Portable tenant:
BigBirdReturns/mary-portable
commit f382633d7349a5d748d2f0b6092f96570f6e5d26
tree   a18f6612b8119beac68292ef4d7f8a5b35e1b0fa
release v0.2.0
archive sha256 bd67c865032ae0977d8c2ada1c07b5e7564fe2ddf6e65f19b63ad41749359009

AXM removable mission-volume supplier:
commit b452bb32e26249deab90db124f157bc62ad0850d
tree   c557bddc17ad62f6ad36bac5a6ef57338429a951

physical-flight preflight review card:
commit ec61bc3488cb5ae06ed9db2862a9f6910d310a79
tree   d2daba1d32a8de744b8b90f6cd42f7c4bff4fa67

physical-flight execution floor:
commit d31e59f5fd30e57b1917c00832b189ee2ea3e12f
tree   2a6a155e9615eb847781f87566bac32d4c9dc126
```

The executable conductor is deliberately excluded from the profile, source binding, cartridge identity, mission identity, work-unit identity, public status, manifest, and bundle identity. Compatible conductor repair lineage is non-authoritative operator provenance, retained outside the portable cartridge:

```text
772ce582e1b19b7a2060c50be8ebf40c1f8723b2
original admitted conductor

ccc6f1bb817614d0948900499c80f4f91e8bade0
readiness artifact-identity compatibility

1047b90d2c2077cff297b9d5e24e333fe7dcf8cc
single-action authorization containment

a99c1c76daf383edd31ada2e3a8f8bf5c57a7888
native stdout/stderr separation

dd486472a8c610a20ee062dd6746c86fe8ede4b4
bounded incremental streams and finite timeout
```

Updating this compatible operator provenance cannot alter cartridge semantics, authorize execution, or promote a physical or authority claim. Issue #37 remains the sole private execution coordinate. Issue #49 remains the postflight join coordinate.

## Cartridge law
"""
runbook, count = source_section.subn(replacement, runbook, count=1)
if count != 1:
    raise SystemExit(f"runbook source section replacement count: {count}")
runbook = runbook.replace(
    "STC Mission Cartridge 01 states the mission identity, work-unit law, source graph, stage and gate denominators, invariants, and authority boundary that the conductor is allowed to bind.",
    "STC Mission Cartridge 01 states the mission identity, work-unit law, semantic source graph, stage and gate denominators, invariants, and authority boundary that a compatible conductor may bind.",
)
RUNBOOK.write_text(runbook, encoding="utf-8", newline="\n")

print(
    json.dumps(
        {
            "status": "PASS",
            "profileCanonicalSha256": profile_sha,
            "standaloneVerifierSha256": verifier_sha,
            "semanticSourceRoles": sorted(profile["sourceCoordinates"]),
            "conductorInSemanticProfile": False,
        },
        sort_keys=True,
    )
)
