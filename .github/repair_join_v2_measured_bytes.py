from __future__ import annotations

from pathlib import Path

root = Path.cwd()
bootstrap_path = root / "mating_surface/anchor_node/verify_axm_head_physical_long_haul_001_join_v2_bootstrap.py"
tests_path = root / "mating_surface/anchor_node/conformance/test_axm_head_physical_long_haul_001_join_v2.py"
workflow_path = root / ".github/workflows/axm-head-physical-long-haul-001-join-v2.yml"
contract_path = root / "mating_surface/anchor_node/AXM-HEAD-PHYSICAL-LONG-HAUL-001-JOIN-v2.md"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one replacement target, found {count}")
    return text.replace(old, new, 1)


bootstrap = bootstrap_path.read_text(encoding="utf-8")
bootstrap = replace_once(
    bootstrap,
    '}\n\n\nclass BootstrapError',
    '}\n\n\nMEASURED_VERIFIER_LAUNCHER = (\n'
    '    "import sys\\n"\n'
    '    "source = sys.stdin.buffer.read()\\n"\n'
    '    "name = \'<authenticated-join-v2-verifier>\'\\n"\n'
    '    "namespace = {\'__name__\': \'__main__\', \'__file__\': name}\\n"\n'
    '    "exec(compile(source, name, \'exec\'), namespace, namespace)\\n"\n'
    ')\n\n\nclass BootstrapError',
    "measured verifier launcher",
)
bootstrap = replace_once(
    bootstrap,
    '\n\ndef main(argv: list[str] | None = None) -> int:\n',
    '\n\ndef invoke_measured_verifier(verifier_bytes: bytes, carrier: Path, env: dict[str, str]) -> subprocess.CompletedProcess[bytes]:\n'
    '    return subprocess.run(\n'
    '        [sys.executable, "-I", "-c", MEASURED_VERIFIER_LAUNCHER, str(carrier)],\n'
    '        input=verifier_bytes,\n'
    '        stdout=subprocess.PIPE,\n'
    '        stderr=subprocess.PIPE,\n'
    '        env=env,\n'
    '        check=False,\n'
    '    )\n'
    '\n'
    '\n'
    'def main(argv: list[str] | None = None) -> int:\n',
    "measured verifier invocation helper",
)
bootstrap = replace_once(
    bootstrap,
    '        measured_digest = sha256_bytes(verifier.read_bytes())\n',
    '        verifier_bytes = verifier.read_bytes()\n'
    '        measured_digest = sha256_bytes(verifier_bytes)\n',
    "single verifier byte read",
)
bootstrap = replace_once(
    bootstrap,
    '        result = subprocess.run(\n'
    '            [sys.executable, str(verifier), str(carrier)],\n'
    '            stdout=subprocess.PIPE,\n'
    '            stderr=subprocess.PIPE,\n'
    '            env=env,\n'
    '            check=False,\n'
    '        )\n',
    '        result = invoke_measured_verifier(verifier_bytes, carrier, env)\n',
    "execute measured bytes",
)

tests = tests_path.read_text(encoding="utf-8")
extra_test = r'''

    def test_47_bootstrap_executes_measured_bytes_not_reopened_path(self):
        carrier = self.build("measured-verifier-race")
        verifier_path = carrier / "RECOVERY/verify_join.py"
        measured_bytes = verifier_path.read_bytes()
        marker = self.root / "malicious-verifier-executed.txt"
        verifier_path.write_text(
            "from pathlib import Path\n"
            f"Path({str(marker)!r}).write_text('executed', encoding='utf-8')\n",
            encoding="utf-8",
        )
        env = os.environ.copy()
        env.pop("AXM_HEAD_JOIN_V2_BOOTSTRAP_AUTHENTICATED", None)
        env.pop("AXM_HEAD_JOIN_V2_VERIFIER_SHA256", None)
        result = BOOTSTRAP.invoke_measured_verifier(measured_bytes, carrier, env)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr, b"")
        self.assertFalse(marker.exists())
        refusal = json.loads(result.stdout)
        self.assertEqual(refusal["status"], "REFUSED")
        self.assertFalse(refusal["bootstrapAuthenticated"])
'''
tests = replace_once(
    tests,
    '\n\nif __name__ == "__main__":\n    unittest.main()\n',
    extra_test + '\n\nif __name__ == "__main__":\n    unittest.main()\n',
    "measured verifier hostile witness",
)

workflow = workflow_path.read_text(encoding="utf-8")
if workflow.count("Ran 46 tests") < 1:
    raise SystemExit("workflow 46-test target missing")
workflow = workflow.replace("Ran 46 tests", "Ran 47 tests")
if workflow.count('"focusedWitnesses": 46') < 1:
    raise SystemExit("workflow 46-witness target missing")
workflow = workflow.replace('"focusedWitnesses": 46', '"focusedWitnesses": 47')

contract = contract_path.read_text(encoding="utf-8")
contract = replace_once(
    contract,
    "The external bootstrap hashes the embedded verifier before execution, invokes it without an authentication channel or output path, requires one canonical direct `PASS` receipt with `bootstrapAuthenticated: false`, validates every physical and authority non-claim, and then constructs the authenticated receipt itself.",
    "The external bootstrap reads and hashes the embedded verifier once, then executes those exact measured bytes through a trusted isolated stdin launcher rather than reopening the carrier pathname. It invokes the measured verifier without an authentication channel or output path, requires one canonical direct `PASS` receipt with `bootstrapAuthenticated: false`, validates every physical and authority non-claim, and then constructs the authenticated receipt itself.",
    "measured verifier documentation",
)
contract = replace_once(
    contract,
    "The focused suite contains forty-six permanent witnesses.",
    "The focused suite contains forty-seven permanent witnesses.",
    "witness count",
)
contract = replace_once(
    contract,
    "malicious verifier substitution, verdict output overlap",
    "malicious verifier substitution, post-measurement verifier-path replacement, verdict output overlap",
    "TOCTOU hostile witness ledger",
)

bootstrap_path.write_text(bootstrap, encoding="utf-8", newline="\n")
tests_path.write_text(tests, encoding="utf-8", newline="\n")
workflow_path.write_text(workflow, encoding="utf-8", newline="\n")
contract_path.write_text(contract, encoding="utf-8", newline="\n")
