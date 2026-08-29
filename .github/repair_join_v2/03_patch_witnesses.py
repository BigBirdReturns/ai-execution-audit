from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
ANCHOR = ROOT / "mating_surface" / "anchor_node"
TESTS = ANCHOR / "conformance" / "test_axm_head_physical_long_haul_001_join_v2.py"


def replace_method(text: str, name: str, next_name: str, replacement: str) -> str:
    pattern = rf"    def {re.escape(name)}\(self\):\n.*?(?=    def {re.escape(next_name)}\(self\):)"
    updated, count = re.subn(pattern, replacement.rstrip() + "\n\n", text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f"{name}: expected one method target, found {count}")
    return updated


tests = TESTS.read_text(encoding="utf-8")
tests = replace_method(
    tests,
    "test_31_direct_verifier_passes_without_self_authentication",
    "test_32_bootstrap_authenticates_exact_verifier",
    '''    def test_31_direct_verifier_passes_without_self_authentication(self):
        carrier = self.build("forged-auth-environment")
        env = os.environ.copy()
        env["AXM_HEAD_JOIN_V2_BOOTSTRAP_AUTHENTICATED"] = "1"
        env["AXM_HEAD_JOIN_V2_VERIFIER_SHA256"] = TOOL.STANDALONE_VERIFIER_SHA256
        completed = subprocess.run(
            [sys.executable, str(carrier / "RECOVERY/verify_join.py"), str(carrier)],
            stdout=subprocess.PIPE,
            env=env,
            check=False,
        )
        self.assertEqual(completed.returncode, 0)
        verdict = json.loads(completed.stdout)
        self.assertEqual(verdict["status"], "PASS")
        self.assertFalse(verdict["bootstrapAuthenticated"])
''',
)
tests = replace_method(
    tests,
    "test_32_bootstrap_authenticates_exact_verifier",
    "test_33_unmanifested_file_refuses",
    '''    def test_32_bootstrap_authenticates_exact_verifier(self):
        carrier = self.build("bootstrap-custody")
        out = self.root / "authenticated-verdict.json"
        completed = subprocess.run(
            [sys.executable, str(BOOTSTRAP_PATH), str(carrier), "--out", str(out)],
            stdout=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, out.read_bytes())
        verdict = json.loads(completed.stdout)
        self.assertTrue(verdict["bootstrapAuthenticated"])
        self.assertEqual(verdict["standaloneVerifierSha256"], TOOL.STANDALONE_VERIFIER_SHA256)
''',
)
tests = replace_method(
    tests,
    "test_35_resigned_public_claim_promotion_refuses",
    "test_36_resigned_preparation_activity_refuses",
    '''    def test_35_resigned_public_claim_promotion_refuses(self):
        cases = (
            ("PUBLIC/status.json", "physicalExecutionStarted", True, "public status is not reconstructed"),
            ("PUBLIC/status.json", "physicalExecutionStarted", 0, "public status is not reconstructed"),
            ("JOIN/decision.json", "physicalAuthorizationProduced", True, "decision is not reconstructed"),
            ("JOIN/decision.json", "physicalAuthorizationProduced", 0, "decision is not reconstructed"),
        )
        for index, (relative, key, replacement, message) in enumerate(cases):
            with self.subTest(relative=relative, key=key, replacement=replacement):
                carrier = self.build(f"resigned-public-semantics-{index}")
                self.mutate_json_and_resign(
                    carrier,
                    relative,
                    lambda value, k=key, r=replacement: value.__setitem__(k, r),
                )
                with self.assertRaisesRegex(VERIFIER.VerificationError, message):
                    VERIFIER.verify(carrier)
''',
)
tests = replace_method(
    tests,
    "test_36_resigned_preparation_activity_refuses",
    "test_37_rewritten_profile_refuses_after_resigning",
    '''    def test_36_resigned_preparation_activity_refuses(self):
        member_cases = (
            ("workersLaunched", 1),
            ("workersLaunched", False),
        )
        for index, (key, replacement) in enumerate(member_cases):
            with self.subTest(member=key, replacement=replacement):
                carrier = self.build(f"resigned-preparation-{index}")
                self.mutate_json_and_resign(
                    carrier,
                    "JOIN/preparation-state.json",
                    lambda value, k=key, r=replacement: value.__setitem__(k, r),
                )
                with self.assertRaisesRegex(VERIFIER.VerificationError, "prepared state is not reconstructed"):
                    VERIFIER.verify(carrier)

        manifest_cases = (
            ("physicalExecutionStarted", True, "manifest physicalExecutionStarted differs"),
            ("physicalExecutionStarted", 0, "manifest physicalExecutionStarted differs"),
            ("bootstrapRequired", False, "bootstrapRequired must remain true"),
            ("bootstrapRequired", 1, "bootstrapRequired must remain true"),
            ("fileCount", False, "manifest fileCount differs"),
        )
        for index, (key, replacement, message) in enumerate(manifest_cases):
            with self.subTest(manifest=key, replacement=replacement):
                carrier = self.build(f"resigned-manifest-{index}")
                manifest_path = carrier / "MANIFEST.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest[key] = replacement
                body = dict(manifest)
                body.pop("carrierId")
                manifest["carrierId"] = TOOL.content_id("axmheadjoincarrier2", body)
                manifest_path.write_bytes(TOOL.pretty_json_bytes(manifest))
                with self.assertRaisesRegex(VERIFIER.VerificationError, message):
                    VERIFIER.verify(carrier)
''',
)
TESTS.write_text(tests, encoding="utf-8", newline="\n")
print("42")
