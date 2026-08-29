from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ANCHOR = ROOT / "mating_surface" / "anchor_node"
TESTS = ANCHOR / "conformance" / "test_axm_head_physical_long_haul_001_join_v2.py"
WORKFLOW = ROOT / ".github" / "workflows" / "axm-head-physical-long-haul-001-join-v2.yml"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one target, found {count}")
    return text.replace(old, new, 1)


tests = TESTS.read_text(encoding="utf-8")
if "def test_43_direct_verifier_ignores_forged_authentication_environment" in tests:
    raise SystemExit("P1 closure witnesses already exist")
addition = r'''
    def test_43_direct_verifier_ignores_forged_authentication_environment(self):
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

    def test_44_bootstrap_constructs_authenticated_receipt_bytes(self):
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

    def test_45_resigned_member_type_confusion_refuses(self):
        cases = (
            ("PUBLIC/status.json", "physicalExecutionStarted", 0, "public status is not reconstructed"),
            ("JOIN/decision.json", "physicalAuthorizationProduced", 0, "decision is not reconstructed"),
            ("JOIN/preparation-state.json", "workersLaunched", False, "prepared state is not reconstructed"),
        )
        for index, (relative, key, replacement, message) in enumerate(cases):
            with self.subTest(relative=relative, key=key, replacement=replacement):
                carrier = self.build(f"type-confusion-member-{index}")
                self.mutate_json_and_resign(
                    carrier,
                    relative,
                    lambda value, k=key, r=replacement: value.__setitem__(k, r),
                )
                with self.assertRaisesRegex(VERIFIER.VerificationError, message):
                    VERIFIER.verify(carrier)

    def test_46_resigned_manifest_type_confusion_refuses(self):
        cases = (
            ("physicalExecutionStarted", 0, "manifest physicalExecutionStarted differs"),
            ("bootstrapRequired", 1, "bootstrapRequired must remain true"),
            ("fileCount", False, "manifest fileCount differs"),
        )
        for index, (key, replacement, message) in enumerate(cases):
            with self.subTest(key=key, replacement=replacement):
                carrier = self.build(f"type-confusion-manifest-{index}")
                manifest_path = carrier / "MANIFEST.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest[key] = replacement
                body = dict(manifest)
                body.pop("carrierId")
                manifest["carrierId"] = TOOL.content_id("axmheadjoincarrier2", body)
                manifest_path.write_bytes(TOOL.pretty_json_bytes(manifest))
                with self.assertRaisesRegex(VERIFIER.VerificationError, message):
                    VERIFIER.verify(carrier)
'''
guard = '\n\nif __name__ == "__main__":\n'
tests = replace_once(tests, guard, "\n" + addition.rstrip() + guard, "append P1 closure witnesses")
TESTS.write_text(tests, encoding="utf-8", newline="\n")

workflow = WORKFLOW.read_text(encoding="utf-8")
workflow = workflow.replace("Ran 42 tests", "Ran 46 tests")
workflow = workflow.replace('"focusedWitnesses": 42', '"focusedWitnesses": 46')
if workflow.count("Ran 46 tests") < 1:
    raise SystemExit("test-count assertion was not updated")
if workflow.count('"focusedWitnesses": 46') < 1:
    raise SystemExit("qualification receipt denominator was not updated")
WORKFLOW.write_text(workflow, encoding="utf-8", newline="\n")
print("46")
