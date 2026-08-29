from __future__ import annotations

from pathlib import Path
import hashlib

root = Path.cwd()
builder_path = root / "mating_surface/anchor_node/axm_head_physical_long_haul_001_join_v2.py"
verifier_path = root / "mating_surface/anchor_node/verify_axm_head_physical_long_haul_001_join_v2.py"
bootstrap_path = root / "mating_surface/anchor_node/verify_axm_head_physical_long_haul_001_join_v2_bootstrap.py"
tests_path = root / "mating_surface/anchor_node/conformance/test_axm_head_physical_long_haul_001_join_v2.py"
workflow_path = root / ".github/workflows/axm-head-physical-long-haul-001-join-v2.yml"
contract_path = root / "mating_surface/anchor_node/AXM-HEAD-PHYSICAL-LONG-HAUL-001-JOIN-v2.md"

old_digest = "47e72c4a0eec643463e17ba4deb16ab345f06fc5e6a191f7e5124d7f92f249a4"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one replacement target, found {count}")
    return text.replace(old, new, 1)


builder = builder_path.read_text(encoding="utf-8")
builder = replace_once(
    builder,
    'ID_RE = re.compile(r"^[a-z0-9][a-z0-9._:/@-]{2,255}$")\n\n\nclass JoinError',
    'ID_RE = re.compile(r"^[a-z0-9][a-z0-9._:/@-]{2,255}$")\nREPOSITORY_ROOT = Path(__file__).resolve().parents[2]\n\n\nclass JoinError',
    "repository root binding",
)
builder = replace_once(
    builder,
    '    return (text + "\\n").encode("utf-8")\n\n\ndef pretty_json_bytes',
    '    return (text + "\\n").encode("utf-8")\n\n\ndef type_strict_equal(actual: Any, expected: Any) -> bool:\n    return canonical_json_bytes(actual) == canonical_json_bytes(expected)\n\n\ndef pretty_json_bytes',
    "type-strict helper",
)
builder = replace_once(
    builder,
    '\n\ndef require_exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:\n',
    '\n\ndef ensure_repository_external_output(path: Path | None) -> None:\n'
    '    if path is None:\n'
    '        return\n'
    '    repository = REPOSITORY_ROOT.resolve()\n'
    '    candidate = path.resolve(strict=False)\n'
    '    if candidate == repository or repository in candidate.parents:\n'
    '        fail("REPOSITORY_OUTPUT_REFUSED", "JOIN-v2 output may not be written inside the repository")\n'
    '\n'
    '\n'
    'def require_exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:\n',
    "repository output guard",
)
for old, new, label in (
    (
        'if profile["sourceCoordinates"] != EXPECTED_SOURCE_COORDINATES:',
        'if not type_strict_equal(profile["sourceCoordinates"], EXPECTED_SOURCE_COORDINATES):',
        "profile source typing",
    ),
    (
        'if profile["physicalFlightIssue"] != EXPECTED_ISSUE:',
        'if not type_strict_equal(profile["physicalFlightIssue"], EXPECTED_ISSUE):',
        "profile issue typing",
    ),
    (
        'if profile[key] != expected:',
        'if not type_strict_equal(profile[key], expected):',
        "profile nonclaim typing",
    ),
    (
        'if value["sourceCoordinates"] != profile["sourceCoordinates"]:',
        'if not type_strict_equal(value["sourceCoordinates"], profile["sourceCoordinates"]):',
        "state source typing",
    ),
    (
        'if value["physicalFlightIssue"] != profile["physicalFlightIssue"]:',
        'if not type_strict_equal(value["physicalFlightIssue"], profile["physicalFlightIssue"]):',
        "state issue typing",
    ),
    (
        'if state["executionCard"] != expected_card:',
        'if not type_strict_equal(state["executionCard"], expected_card):',
        "execution-card typing",
    ),
):
    builder = replace_once(builder, old, new, label)
builder = replace_once(
    builder,
    '    profile = validate_profile(profile_path)\n    if out.exists():',
    '    profile = validate_profile(profile_path)\n    ensure_repository_external_output(out)\n    if out.exists():',
    "carrier output guard",
)
builder = replace_once(
    builder,
    'def emit(value: dict[str, Any], out: Path | None = None, *, pretty: bool = False) -> None:\n'
    '    data = pretty_json_bytes(value) if pretty else canonical_json_bytes(value)',
    'def emit(value: dict[str, Any], out: Path | None = None, *, pretty: bool = False) -> None:\n'
    '    ensure_repository_external_output(out)\n'
    '    data = pretty_json_bytes(value) if pretty else canonical_json_bytes(value)',
    "emit output guard",
)
builder = replace_once(
    builder,
    'def run_bootstrap(carrier: Path, out: Path | None) -> int:\n'
    '    bootstrap = Path(__file__).resolve().with_name("verify_axm_head_physical_long_haul_001_join_v2_bootstrap.py")',
    'def run_bootstrap(carrier: Path, out: Path | None) -> int:\n'
    '    ensure_repository_external_output(out)\n'
    '    bootstrap = Path(__file__).resolve().with_name("verify_axm_head_physical_long_haul_001_join_v2_bootstrap.py")',
    "bootstrap output guard",
)

verifier = verifier_path.read_text(encoding="utf-8")
verifier = replace_once(
    verifier,
    '            "bootstrapAuthenticated": os.environ.get("AXM_HEAD_JOIN_V2_BOOTSTRAP_AUTHENTICATED") == "1",',
    '            "bootstrapAuthenticated": False,',
    "direct refusal authentication",
)
new_digest = hashlib.sha256(verifier.encode("utf-8")).hexdigest()

bootstrap = bootstrap_path.read_text(encoding="utf-8")
bootstrap = replace_once(
    bootstrap,
    f'EXPECTED_VERIFIER_SHA256 = "{old_digest}"\nVERDICT_SCHEMA',
    f'EXPECTED_VERIFIER_SHA256 = "{old_digest}"\n'
    'TRUSTED_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]\n'
    'VERDICT_SCHEMA',
    "bootstrap repository root binding",
)
bootstrap = replace_once(
    bootstrap,
    '    carrier_resolved = carrier.resolve()\n'
    '    out_resolved = out.resolve(strict=False)\n'
    '    if out_resolved == carrier_resolved or carrier_resolved in out_resolved.parents:',
    '    carrier_resolved = carrier.resolve()\n'
    '    out_resolved = out.resolve(strict=False)\n'
    '    repository_resolved = TRUSTED_REPOSITORY_ROOT.resolve()\n'
    '    if out_resolved == repository_resolved or repository_resolved in out_resolved.parents:\n'
    '        fail("REPOSITORY_OUTPUT_REFUSED", "verdict output may not be written inside the repository")\n'
    '    if out_resolved == carrier_resolved or carrier_resolved in out_resolved.parents:',
    "bootstrap repository output guard",
)

tests = tests_path.read_text(encoding="utf-8")
extra_tests = r'''

    def test_43_caller_supplied_card_type_confusion_refuses(self):
        cases = (
            ("action.authorized", lambda card: card["actions"][0].__setitem__("authorized", 0)),
            ("card.physicalAuthorizationProduced", lambda card: card.__setitem__("physicalAuthorizationProduced", 0)),
            ("card.actionCount", lambda card: card.__setitem__("actionCount", 12.0)),
            ("card.firstPhysicalActionOrdinal", lambda card: card.__setitem__("firstPhysicalActionOrdinal", 5.0)),
        )
        for label, mutate in cases:
            with self.subTest(label=label):
                state = self.full_state(card=True)
                mutate(state["executionCard"])
                body = dict(state)
                body.pop("stateId")
                state["stateId"] = TOOL.content_id("axmheadjoinstate2", body)
                decision = TOOL.evaluate_preparation(self.profile, state)
                self.assertEqual(decision["terminal"], "REFUSED")
                self.assertIn("EXECUTION_CARD_MISMATCH", decision["reasonCodes"])

    def test_44_issue_binding_type_confusion_refuses(self):
        state = self.full_state()
        state["physicalFlightIssue"]["issueNumber"] = 37.0
        state["preparationBasisId"] = TOOL.content_id(
            "axmheadjoinbasis2", TOOL.state_basis_body(self.profile, state)
        )
        body = dict(state)
        body.pop("stateId")
        state["stateId"] = TOOL.content_id("axmheadjoinstate2", body)
        decision = TOOL.evaluate_preparation(self.profile, state)
        self.assertEqual(decision["terminal"], "REFUSED")
        self.assertEqual(decision["errorCode"], "STATE_ISSUE_BINDING_INVALID")

    def test_45_direct_refusal_ignores_forged_authentication_environment(self):
        carrier = self.build("forged-auth-refusal")
        (carrier / "EXTRA.txt").write_text("extra\n", encoding="utf-8")
        env = os.environ.copy()
        env["AXM_HEAD_JOIN_V2_BOOTSTRAP_AUTHENTICATED"] = "1"
        env["AXM_HEAD_JOIN_V2_VERIFIER_SHA256"] = TOOL.STANDALONE_VERIFIER_SHA256
        completed = subprocess.run(
            [sys.executable, str(carrier / "RECOVERY/verify_join.py"), str(carrier)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stderr, b"")
        refusal = json.loads(completed.stdout)
        self.assertEqual(refusal["status"], "REFUSED")
        self.assertFalse(refusal["bootstrapAuthenticated"])

    def test_46_repository_output_is_refused_before_writing(self):
        carrier = self.build("external-carrier")
        inside_dir = ANCHOR / ".join-v2-repository-output-refused-test"
        inside_file = ANCHOR / ".join-v2-repository-output-refused-test.json"
        try:
            with self.assertRaisesRegex(TOOL.JoinError, "inside the repository"):
                TOOL.build_carrier(profile_path=PROFILE_PATH, out=inside_dir)
            with self.assertRaisesRegex(TOOL.JoinError, "inside the repository"):
                TOOL.emit({"status": "PASS"}, inside_file)
            with self.assertRaisesRegex(TOOL.JoinError, "inside the repository"):
                TOOL.run_bootstrap(carrier, inside_file)
            self.assertFalse(inside_dir.exists())
            self.assertFalse(inside_file.exists())
        finally:
            if inside_dir.is_dir():
                shutil.rmtree(inside_dir)
            elif inside_dir.exists():
                inside_dir.unlink()
            if inside_file.exists():
                inside_file.unlink()
'''
tests = replace_once(
    tests,
    '\n\nif __name__ == "__main__":\n    unittest.main()\n',
    extra_tests + '\n\nif __name__ == "__main__":\n    unittest.main()\n',
    "new hostile witnesses",
)

workflow = workflow_path.read_text(encoding="utf-8")
if workflow.count("Ran 42 tests") < 1:
    raise SystemExit("workflow test-count target missing")
workflow = workflow.replace("Ran 42 tests", "Ran 46 tests")
if workflow.count('"focusedWitnesses": 42') < 1:
    raise SystemExit("workflow focused-witness target missing")
workflow = workflow.replace('"focusedWitnesses": 42', '"focusedWitnesses": 46')

contract = contract_path.read_text(encoding="utf-8")
contract = replace_once(
    contract,
    "forty-two permanent witnesses",
    "forty-six permanent witnesses",
    "contract witness count",
)
contract = replace_once(
    contract,
    "A substituted verifier is refused before its bytes run. Verdict output inside the measured carrier or "
    "hard-linked to a measured member is refused without mutation.",
    "A substituted verifier is refused before its bytes run. Direct refusal remains canonical and unauthenticated "
    "even when a caller forges legacy environment variables. Verdict output inside the measured carrier, hard-linked "
    "to a measured member, or resolved anywhere under the repository root is refused before mutation.",
    "contract refusal and output custody",
)
contract = replace_once(
    contract,
    "Boolean/integer JSON type confusion after complete re-signing, forged bootstrap environment variables, "
    "rewritten profile provenance",
    "Boolean/integer JSON type confusion after complete re-signing in both carrier and private review-card semantics, "
    "issue-number type confusion, forged bootstrap environment variables, non-canonical direct refusal, "
    "repository-local output, rewritten profile provenance",
    "contract hostile witness ledger",
)

for label, text in (("builder", builder), ("bootstrap", bootstrap), ("contract", contract)):
    count = text.count(old_digest)
    if count != 1:
        raise SystemExit(f"{label}: expected one old verifier digest, found {count}")
builder = builder.replace(old_digest, new_digest)
bootstrap = bootstrap.replace(old_digest, new_digest)
contract = contract.replace(old_digest, new_digest)

builder_path.write_text(builder, encoding="utf-8", newline="\n")
verifier_path.write_text(verifier, encoding="utf-8", newline="\n")
bootstrap_path.write_text(bootstrap, encoding="utf-8", newline="\n")
tests_path.write_text(tests, encoding="utf-8", newline="\n")
workflow_path.write_text(workflow, encoding="utf-8", newline="\n")
contract_path.write_text(contract, encoding="utf-8", newline="\n")

print(f"new standalone verifier sha256: {new_digest}")
