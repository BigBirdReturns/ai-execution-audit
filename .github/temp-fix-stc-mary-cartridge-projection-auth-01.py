from __future__ import annotations

import hashlib
from pathlib import Path

anchor = Path("mating_surface/anchor_node")
verifier_path = anchor / "verify_stc_mary_flight_01_cartridge.py"
builder_path = anchor / "stc_mary_flight_01_cartridge.py"
bootstrap_path = anchor / "verify_stc_mary_flight_01_cartridge_bootstrap.py"
tests_path = anchor / "conformance/test_stc_mary_flight_01_cartridge.py"
runbook_path = anchor / "STC-MARY-FLIGHT-01-CARTRIDGE-01.md"

old_verifier_sha = "f91d2f26f3c5cf141005433ae6aeb9d4ef072b49ec8258bc312cc629135156c9"


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one replacement anchor, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


replace_once(
    verifier_path,
    '''        "sourceBindingId": source["sourceBindingId"],
        "checks": checks,
        "bootstrapAuthenticated": False,
''',
    '''        "sourceBindingId": source["sourceBindingId"],
        "publicStatus": status,
        "checks": checks,
        "bootstrapAuthenticated": False,
''',
    "authenticated public-status verdict",
)

replace_once(
    builder_path,
    '''    root = supplied_root.resolve(strict=True)
    verdict = run_bootstrap(supplied_root)
    if verdict.get("status") != "PASS" or verdict.get("bootstrapAuthenticated") is not True:
        fail("AUTHENTICATED_VERIFICATION_REQUIRED", "cartridge must pass the external bootstrap")
    status_path = root / "PUBLIC" / "status.json"
    return parse_json_bytes(status_path.read_bytes(), str(status_path))
''',
    '''    supplied_root.resolve(strict=True)
    verdict = run_bootstrap(supplied_root)
    if verdict.get("status") != "PASS" or verdict.get("bootstrapAuthenticated") is not True:
        fail("AUTHENTICATED_VERIFICATION_REQUIRED", "cartridge must pass the external bootstrap")
    projection = verdict.get("publicStatus")
    if not isinstance(projection, dict):
        fail("AUTHENTICATED_PUBLIC_STATUS_REQUIRED", "authenticated verdict omitted the reconstructed public status")
    return projection
''',
    "projection post-authentication reopen removal",
)

replace_once(
    tests_path,
    '''from pathlib import Path

ANCHOR = Path(__file__).resolve().parents[1]
''',
    '''from pathlib import Path
from unittest.mock import patch

ANCHOR = Path(__file__).resolve().parents[1]
''',
    "mock import",
)

replace_once(
    tests_path,
    '''    def test_24_public_projection_is_body_free(self) -> None:
        projection = tool.public_projection(self.root)
        encoded = json.dumps(projection, sort_keys=True)
        self.assertNotIn("privatePath", encoded)
        self.assertNotIn("hostname", encoded)
        self.assertNotIn("credential", encoded)
        self.assertEqual(projection["publicEvidenceBodies"], 0)
        self.assertEqual(projection["authority"], "none")
''',
    '''    def test_24_public_projection_is_body_free(self) -> None:
        projection = tool.public_projection(self.root)
        encoded = json.dumps(projection, sort_keys=True)
        self.assertNotIn("privatePath", encoded)
        self.assertNotIn("hostname", encoded)
        self.assertNotIn("credential", encoded)
        self.assertEqual(projection["publicEvidenceBodies"], 0)
        self.assertEqual(projection["authority"], "none")

        authenticated_projection = dict(projection)
        original_bootstrap = tool.run_bootstrap

        def mutate_status_after_authentication(root: Path, out: Path | None = None) -> dict:
            verdict = original_bootstrap(root, out)
            (self.root / "PUBLIC/status.json").write_text(
                json.dumps(
                    {
                        "privatePath": "unverified-post-authentication-substitution",
                        "authority": "mission",
                    },
                    sort_keys=True,
                    indent=2,
                )
                + "\\n",
                encoding="utf-8",
                newline="\\n",
            )
            return verdict

        with patch.object(tool, "run_bootstrap", side_effect=mutate_status_after_authentication):
            projection_after_disk_mutation = tool.public_projection(self.root)

        self.assertEqual(projection_after_disk_mutation, authenticated_projection)
        self.assertNotIn("privatePath", projection_after_disk_mutation)
        self.assertEqual(projection_after_disk_mutation["authority"], "none")
''',
    "post-authentication projection mutation witness",
)

replace_once(
    runbook_path,
    '''`verify` uses the external bootstrap. The bootstrap hashes `RECOVERY/verify_cartridge.py` before execution and refuses substitution without running the untrusted file. The embedded verifier then reconstructs the profile, source binding, work-unit, mission, public status, member rows, manifest, cartridge identity, mission identity, work-unit identity, source-binding identity, and bundle identity. Stored semantics are compared through canonical JSON bytes so JSON Boolean and integer substitutions cannot pass through Python equality.
''',
    '''`verify` uses the external bootstrap. The bootstrap hashes `RECOVERY/verify_cartridge.py` before execution and refuses substitution without running the untrusted file. The embedded verifier then reconstructs the profile, source binding, work-unit, mission, public status, member rows, manifest, cartridge identity, mission identity, work-unit identity, source-binding identity, and bundle identity. Stored semantics are compared through canonical JSON bytes so JSON Boolean and integer substitutions cannot pass through Python equality. The authenticated verdict carries the reconstructed public status in memory, and `public-projection` emits that object without reopening `PUBLIC/status.json`; a concurrent post-verification member replacement therefore cannot enter the projection.
''',
    "runbook authenticated projection custody",
)

verifier_sha = hashlib.sha256(verifier_path.read_bytes()).hexdigest()
replace_once(
    builder_path,
    f'EXPECTED_VERIFIER_SHA256 = "{old_verifier_sha}"',
    f'EXPECTED_VERIFIER_SHA256 = "{verifier_sha}"',
    "builder frozen verifier digest",
)
replace_once(
    bootstrap_path,
    f'EXPECTED_EMBEDDED_VERIFIER_SHA256 = "{old_verifier_sha}"',
    f'EXPECTED_EMBEDDED_VERIFIER_SHA256 = "{verifier_sha}"',
    "bootstrap frozen verifier digest",
)

print(f"embedded verifier sha256: {verifier_sha}")
