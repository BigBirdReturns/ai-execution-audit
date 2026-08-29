from __future__ import annotations

from pathlib import Path
import hashlib

root = Path.cwd()
verifier_path = root / "mating_surface/anchor_node/verify_axm_head_physical_long_haul_001_join_v2.py"
builder_path = root / "mating_surface/anchor_node/axm_head_physical_long_haul_001_join_v2.py"
bootstrap_path = root / "mating_surface/anchor_node/verify_axm_head_physical_long_haul_001_join_v2_bootstrap.py"
tests_path = root / "mating_surface/anchor_node/conformance/test_axm_head_physical_long_haul_001_join_v2.py"
workflow_path = root / ".github/workflows/axm-head-physical-long-haul-001-join-v2.yml"
contract_path = root / "mating_surface/anchor_node/AXM-HEAD-PHYSICAL-LONG-HAUL-001-JOIN-v2.md"

old_digest = "c0ea446f93c578fcc5adecd19f479078a48bb7c0e1df217fbfd3243d05a5ed0e"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one replacement target, found {count}")
    return text.replace(old, new, 1)


verifier = verifier_path.read_text(encoding="utf-8")
verifier = replace_once(
    verifier,
    '\n\ndef ensure_output_safe(carrier: Path, out: Path | None) -> None:\n',
    '\n\ndef containing_git_repository(path: Path) -> Path | None:\n'
    '    candidate = path if path.is_dir() else path.parent\n'
    '    for ancestor in (candidate, *candidate.parents):\n'
    '        if (ancestor / ".git").exists():\n'
    '            return ancestor.resolve()\n'
    '    return None\n'
    '\n'
    '\n'
    'def ensure_output_safe(carrier: Path, out: Path | None) -> None:\n',
    "repository detector",
)
verifier = replace_once(
    verifier,
    '    carrier_resolved = carrier.resolve()\n'
    '    out_resolved = out.resolve(strict=False)\n'
    '    if out_resolved == carrier_resolved or carrier_resolved in out_resolved.parents:',
    '    carrier_resolved = carrier.resolve()\n'
    '    out_resolved = out.resolve(strict=False)\n'
    '    source_repository = Path(__file__).resolve().parents[2]\n'
    '    if (source_repository / ".git").exists() and (\n'
    '        out_resolved == source_repository or source_repository in out_resolved.parents\n'
    '    ):\n'
    '        fail("REPOSITORY_OUTPUT_REFUSED", "verdict output may not be written inside the trusted repository")\n'
    '    output_repository = containing_git_repository(out_resolved)\n'
    '    if output_repository is not None:\n'
    '        fail("REPOSITORY_OUTPUT_REFUSED", "verdict output may not be written inside a Git repository")\n'
    '    if out_resolved == carrier_resolved or carrier_resolved in out_resolved.parents:',
    "direct repository output refusal",
)
verifier = replace_once(
    verifier,
    '        emit(refused, None)\n'
    '        return 2\n'
    '\n'
    '\n'
    'if __name__ == "__main__":',
    '        emit(refused, None)\n'
    '        return 2\n'
    '    except OSError as exc:\n'
    '        refused = {\n'
    '            "schema": VERDICT_SCHEMA,\n'
    '            "status": "REFUSED",\n'
    '            "code": "CARRIER_IO_FAILED",\n'
    '            "message": f"carrier I/O failed: {type(exc).__name__}: {exc}",\n'
    '            "bootstrapAuthenticated": False,\n'
    '            "physicalAuthorizationProduced": False,\n'
    '            "physicalExecutionStarted": False,\n'
    '            "workersLaunched": 0,\n'
    '            "listenersCreated": 0,\n'
    '            "authority": "none",\n'
    '        }\n'
    '        emit(refused, None)\n'
    '        return 2\n'
    '\n'
    '\n'
    'if __name__ == "__main__":',
    "canonical I/O refusal",
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

tests = tests_path.read_text(encoding="utf-8")
tests = replace_once(
    tests,
    'import unittest\nfrom pathlib import Path\n',
    'import unittest\nfrom pathlib import Path\nfrom unittest import mock\n',
    "mock import",
)
extra_tests = r'''

    def test_48_direct_verifier_refuses_repository_output_without_mutation(self):
        carrier = self.build("direct-repository-output")
        output = ANCHOR / ".join-v2-direct-repository-output-refused.json"
        try:
            self.assertFalse(output.exists())
            completed = subprocess.run(
                [
                    sys.executable,
                    str(carrier / "RECOVERY/verify_join.py"),
                    str(carrier),
                    "--out",
                    str(output),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(completed.returncode, 2)
            self.assertEqual(completed.stderr, b"")
            refusal = json.loads(completed.stdout)
            self.assertEqual(refusal["status"], "REFUSED")
            self.assertEqual(refusal["code"], "REPOSITORY_OUTPUT_REFUSED")
            self.assertFalse(refusal["bootstrapAuthenticated"])
            self.assertFalse(output.exists())
        finally:
            if output.exists():
                output.unlink()

    def test_49_carrier_io_race_emits_canonical_unauthenticated_refusal(self):
        carrier = self.build("carrier-io-race")
        captured = []
        original_verify = VERIFIER.verify

        def raced_verify(path):
            with mock.patch.object(Path, "read_bytes", side_effect=OSError("simulated carrier member race")):
                return original_verify(path)

        def capture_emit(value, out):
            captured.append((value, out, VERIFIER.canonical_json_bytes(value)))

        with mock.patch.object(VERIFIER, "verify", side_effect=raced_verify), mock.patch.object(
            VERIFIER, "emit", side_effect=capture_emit
        ):
            return_code = VERIFIER.main([str(carrier)])

        self.assertEqual(return_code, 2)
        self.assertEqual(len(captured), 1)
        refusal, out, receipt_bytes = captured[0]
        self.assertIsNone(out)
        self.assertEqual(refusal["status"], "REFUSED")
        self.assertEqual(refusal["code"], "CARRIER_IO_FAILED")
        self.assertFalse(refusal["bootstrapAuthenticated"])
        self.assertFalse(refusal["physicalAuthorizationProduced"])
        self.assertFalse(refusal["physicalExecutionStarted"])
        self.assertEqual(refusal["workersLaunched"], 0)
        self.assertEqual(refusal["listenersCreated"], 0)
        self.assertEqual(refusal["authority"], "none")
        self.assertEqual(json.loads(receipt_bytes), refusal)
'''
tests = replace_once(
    tests,
    '\n\nif __name__ == "__main__":\n    unittest.main()\n',
    extra_tests + '\n\nif __name__ == "__main__":\n    unittest.main()\n',
    "direct I/O hostile witnesses",
)

workflow = workflow_path.read_text(encoding="utf-8")
if workflow.count("Ran 47 tests") < 1:
    raise SystemExit("workflow 47-test target missing")
workflow = workflow.replace("Ran 47 tests", "Ran 49 tests")
if workflow.count('"focusedWitnesses": 47') < 1:
    raise SystemExit("workflow 47-witness target missing")
workflow = workflow.replace('"focusedWitnesses": 47', '"focusedWitnesses": 49')

contract = replace_once(
    contract,
    "The focused suite contains forty-seven permanent witnesses.",
    "The focused suite contains forty-nine permanent witnesses.",
    "witness count",
)
contract = replace_once(
    contract,
    "non-canonical direct refusal, repository-local output, rewritten profile provenance",
    "non-canonical direct refusal, repository-local builder, bootstrap, and direct-verifier output, canonical carrier-I/O race refusal, rewritten profile provenance",
    "direct I/O witness ledger",
)

verifier_path.write_text(verifier, encoding="utf-8", newline="\n")
builder_path.write_text(builder, encoding="utf-8", newline="\n")
bootstrap_path.write_text(bootstrap, encoding="utf-8", newline="\n")
tests_path.write_text(tests, encoding="utf-8", newline="\n")
workflow_path.write_text(workflow, encoding="utf-8", newline="\n")
contract_path.write_text(contract, encoding="utf-8", newline="\n")

print(f"new standalone verifier sha256: {new_digest}")
