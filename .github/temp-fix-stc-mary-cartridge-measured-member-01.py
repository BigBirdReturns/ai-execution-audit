from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path("mating_surface/anchor_node")
VERIFIER = ROOT / "verify_stc_mary_flight_01_cartridge.py"
BOOTSTRAP = ROOT / "verify_stc_mary_flight_01_cartridge_bootstrap.py"
TOOL = ROOT / "stc_mary_flight_01_cartridge.py"
TESTS = ROOT / "conformance/test_stc_mary_flight_01_cartridge.py"
DOC = ROOT / "STC-MARY-FLIGHT-01-CARTRIDGE-01.md"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


verifier = VERIFIER.read_text(encoding="utf-8")
verifier = replace_once(
    verifier,
    '''def verify_cartridge(root: Path) -> dict[str, Any]:
    supplied_root = validate_cartridge_coordinate(root)
    root = supplied_root.resolve(strict=True)
    validate_tree(root)

    member_bytes = {relative: read_member(root, relative) for relative in EXPECTED_FILES}
    profile = validate_profile(parse_json_bytes(member_bytes["RECOVERY/profile.json"], "RECOVERY/profile.json"))
''',
    '''def verify_cartridge(root: Path, measured_verifier_bytes: bytes | None = None) -> dict[str, Any]:
    supplied_root = validate_cartridge_coordinate(root)
    root = supplied_root.resolve(strict=True)
    validate_tree(root)

    member_bytes = {relative: read_member(root, relative) for relative in EXPECTED_FILES}
    measured_verifier_sha256: str | None = None
    if measured_verifier_bytes is not None:
        if type(measured_verifier_bytes) is not bytes:
            fail("MEASURED_VERIFIER_BYTES_INVALID", "bootstrap measured verifier bytes must be one immutable byte string")
        measured_verifier_sha256 = sha256_bytes(measured_verifier_bytes)
        if member_bytes["RECOVERY/verify_cartridge.py"] != measured_verifier_bytes:
            fail(
                "MEASURED_VERIFIER_MEMBER_MISMATCH",
                "stored verifier member differs from the verifier bytes measured and executed by the bootstrap",
            )
    profile = validate_profile(parse_json_bytes(member_bytes["RECOVERY/profile.json"], "RECOVERY/profile.json"))
''',
    "measured verifier member binding",
)
verifier = replace_once(
    verifier,
    '''    checks = [
        "closed-file-denominator",
        "closed-directory-denominator",
        "lf-only-authoritative-bytes",
        "profile-canonical-digest",
        "exact-source-binding",
        "exact-work-unit-reconstruction",
        "exact-mission-reconstruction",
        "exact-public-status-reconstruction",
        "manifest-member-byte-identities",
        "bundle-identity-reconstruction",
        "private-public-field-refusal",
        "authority-none",
    ]
''',
    '''    checks = [
        "closed-file-denominator",
        "closed-directory-denominator",
        "lf-only-authoritative-bytes",
        "profile-canonical-digest",
        "exact-source-binding",
        "exact-work-unit-reconstruction",
        "exact-mission-reconstruction",
        "exact-public-status-reconstruction",
        "manifest-member-byte-identities",
        "bundle-identity-reconstruction",
        "private-public-field-refusal",
        "authority-none",
    ]
    if measured_verifier_sha256 is not None:
        checks.append("measured-verifier-member-binding")
''',
    "measured binding check receipt",
)
verifier = replace_once(
    verifier,
    '''        "publicStatus": status,
        "checks": checks,
        "bootstrapAuthenticated": False,
''',
    '''        "publicStatus": status,
        "checks": checks,
        "measuredVerifierSha256": measured_verifier_sha256,
        "bootstrapAuthenticated": False,
''',
    "measured verifier verdict field",
)
verifier = replace_once(
    verifier,
    '''        root = supplied_root.resolve(strict=True)
        validate_output_path(root, args.out)
        verdict = verify_cartridge(supplied_root)
''',
    '''        root = supplied_root.resolve(strict=True)
        validate_output_path(root, args.out)
        measured_verifier_bytes = globals().get("_STC_MARY_BOOTSTRAP_MEASURED_VERIFIER_BYTES")
        verdict = verify_cartridge(supplied_root, measured_verifier_bytes=measured_verifier_bytes)
''',
    "measured verifier main plumbing",
)
VERIFIER.write_text(verifier, encoding="utf-8", newline="\n")
verifier_sha = hashlib.sha256(VERIFIER.read_bytes()).hexdigest()

bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
bootstrap = replace_once(
    bootstrap,
    '''namespace = {
    "__name__": "__main__",
    "__file__": "<measured-stc-mary-flight-01-cartridge-verifier>",
}
''',
    '''namespace = {
    "__name__": "__main__",
    "__file__": "<measured-stc-mary-flight-01-cartridge-verifier>",
    "_STC_MARY_BOOTSTRAP_MEASURED_VERIFIER_BYTES": source,
}
''',
    "launcher measured-byte custody",
)
old_bootstrap_digest = next(
    line for line in bootstrap.splitlines() if line.startswith("EXPECTED_EMBEDDED_VERIFIER_SHA256 = ")
)
bootstrap = bootstrap.replace(
    old_bootstrap_digest,
    f'EXPECTED_EMBEDDED_VERIFIER_SHA256 = "{verifier_sha}"',
    1,
)
bootstrap = replace_once(
    bootstrap,
    '''        if verdict.get("bootstrapAuthenticated") is not False:
            fail("EMBEDDED_VERDICT_BOOTSTRAP_STATE_INVALID", "embedded verifier may not self-assert bootstrap authentication")
        verdict["bootstrapAuthenticated"] = True
''',
    '''        if verdict.get("bootstrapAuthenticated") is not False:
            fail("EMBEDDED_VERDICT_BOOTSTRAP_STATE_INVALID", "embedded verifier may not self-assert bootstrap authentication")
        if verdict.get("measuredVerifierSha256") != observed:
            fail(
                "EMBEDDED_VERIFIER_MEMBER_BINDING_INVALID",
                "embedded verifier did not bind the stored verifier member to the measured execution bytes",
            )
        verdict["bootstrapAuthenticated"] = True
''',
    "bootstrap measured-member handshake",
)
BOOTSTRAP.write_text(bootstrap, encoding="utf-8", newline="\n")

tool = TOOL.read_text(encoding="utf-8")
old_tool_digest = next(line for line in tool.splitlines() if line.startswith("EXPECTED_VERIFIER_SHA256 = "))
tool = tool.replace(old_tool_digest, f'EXPECTED_VERIFIER_SHA256 = "{verifier_sha}"', 1)
TOOL.write_text(tool, encoding="utf-8", newline="\n")

tests = TESTS.read_text(encoding="utf-8")
tests = replace_once(
    tests,
    '''import stc_mary_flight_01_cartridge as tool
import verify_stc_mary_flight_01_cartridge as verifier
''',
    '''import stc_mary_flight_01_cartridge as tool
import verify_stc_mary_flight_01_cartridge as verifier
import verify_stc_mary_flight_01_cartridge_bootstrap as bootstrap
''',
    "bootstrap test import",
)
tests = replace_once(
    tests,
    '''        self.assertTrue(verdict["bootstrapAuthenticated"])
        self.assertEqual(verdict["authority"], "none")
''',
    '''        self.assertTrue(verdict["bootstrapAuthenticated"])
        self.assertEqual(verdict["measuredVerifierSha256"], tool.EXPECTED_VERIFIER_SHA256)
        self.assertIn("measured-verifier-member-binding", verdict["checks"])
        self.assertEqual(verdict["authority"], "none")
''',
    "authenticated measured-member assertion",
)
tests = replace_once(
    tests,
    '''        code, verdict = run_bootstrap(hijack, env=environment)
        self.assertNotEqual(code, 0)
        self.assertEqual(verdict["code"], "FILE_DENOMINATOR_INVALID")
        self.assertFalse(marker.exists())
''',
    '''        code, verdict = run_bootstrap(hijack, env=environment)
        self.assertNotEqual(code, 0)
        self.assertEqual(verdict["code"], "FILE_DENOMINATOR_INVALID")
        self.assertFalse(marker.exists())

        member_race = self.parent / "cartridge-verifier-member-race"
        tool.build_cartridge(PROFILE, member_race)
        measured_bytes = (member_race / "RECOVERY/verify_cartridge.py").read_bytes()
        (member_race / "RECOVERY/verify_cartridge.py").write_text(
            "# substituted after bootstrap measurement\\n",
            encoding="utf-8",
            newline="\\n",
        )
        resign_manifest(member_race)
        raced = subprocess.run(
            [
                sys.executable,
                "-I",
                "-S",
                "-c",
                bootstrap.ISOLATED_VERIFIER_LAUNCHER,
                str(member_race),
            ],
            input=measured_bytes,
            check=False,
            capture_output=True,
        )
        raced_verdict = json.loads(raced.stdout.decode("utf-8"))
        self.assertNotEqual(raced.returncode, 0)
        self.assertEqual(raced_verdict["code"], "MEASURED_VERIFIER_MEMBER_MISMATCH")
''',
    "post-measurement member substitution witness",
)
TESTS.write_text(tests, encoding="utf-8", newline="\n")

doc = DOC.read_text(encoding="utf-8")
doc = replace_once(
    doc,
    '''`verify` uses the external bootstrap. The bootstrap hashes `RECOVERY/verify_cartridge.py` before execution and refuses substitution without running the untrusted file. The embedded verifier then reconstructs the profile, source binding, work-unit, mission, public status, member rows, manifest, cartridge identity, mission identity, work-unit identity, source-binding identity, and bundle identity. Stored semantics are compared through canonical JSON bytes so JSON Boolean and integer substitutions cannot pass through Python equality. The authenticated verdict carries the reconstructed public status in memory, and `public-projection` emits that object without reopening `PUBLIC/status.json`; a concurrent post-verification member replacement therefore cannot enter the projection. The projection route has one authenticated object and performs no second filesystem read of the projected member.
''',
    '''`verify` uses the external bootstrap. The bootstrap hashes `RECOVERY/verify_cartridge.py` before execution and refuses substitution without running the untrusted file. The isolated launcher injects those same measured bytes into the trusted verifier namespace; the verifier requires the stored `RECOVERY/verify_cartridge.py` member to remain byte-identical to the measured execution bytes, and the bootstrap requires the returned measured digest before it can set `bootstrapAuthenticated = true`. A verifier-member replacement and resigned manifest between measurement and child verification therefore terminates refusal rather than authenticating a different bundle member. The embedded verifier then reconstructs the profile, source binding, work-unit, mission, public status, member rows, manifest, cartridge identity, mission identity, work-unit identity, source-binding identity, and bundle identity. Stored semantics are compared through canonical JSON bytes so JSON Boolean and integer substitutions cannot pass through Python equality. The authenticated verdict carries the reconstructed public status in memory, and `public-projection` emits that object without reopening `PUBLIC/status.json`; a concurrent post-verification member replacement therefore cannot enter the projection. The projection route has one authenticated object and performs no second filesystem read of the projected member.
''',
    "measured verifier member documentation",
)
DOC.write_text(doc, encoding="utf-8", newline="\n")

print(f"embedded verifier sha256: {verifier_sha}")
