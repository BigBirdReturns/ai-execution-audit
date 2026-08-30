from __future__ import annotations

from pathlib import Path

ROOT = Path("mating_surface/anchor_node")
VERIFIER = ROOT / "verify_stc_mary_flight_01_cartridge.py"
BOOTSTRAP = ROOT / "verify_stc_mary_flight_01_cartridge_bootstrap.py"
TESTS = ROOT / "conformance/test_stc_mary_flight_01_cartridge.py"
DOC = ROOT / "STC-MARY-FLIGHT-01-CARTRIDGE-01.md"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


verifier_size = len(VERIFIER.read_bytes())

bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
digest_line = next(
    line for line in bootstrap.splitlines()
    if line.startswith("EXPECTED_EMBEDDED_VERIFIER_SHA256 = ")
)
bootstrap = replace_once(
    bootstrap,
    digest_line + "\n",
    digest_line + f"\nEXPECTED_EMBEDDED_VERIFIER_BYTES = {verifier_size}\n",
    "frozen verifier byte length",
)
bootstrap = replace_once(
    bootstrap,
    '''        verifier = root / "RECOVERY" / "verify_cartridge.py"
        if not verifier.is_file() or verifier.is_symlink():
            fail("EMBEDDED_VERIFIER_MISSING", "embedded verifier is missing or not regular")
        verifier_bytes = verifier.read_bytes()
        observed = sha256_bytes(verifier_bytes)
''',
    '''        verifier = root / "RECOVERY" / "verify_cartridge.py"
        if not verifier.is_file() or verifier.is_symlink():
            fail("EMBEDDED_VERIFIER_MISSING", "embedded verifier is missing or not regular")
        verifier_size = verifier.stat().st_size
        if verifier_size != EXPECTED_EMBEDDED_VERIFIER_BYTES:
            fail(
                "EMBEDDED_VERIFIER_SIZE_INVALID",
                f"embedded verifier size differs: expected={EXPECTED_EMBEDDED_VERIFIER_BYTES} observed={verifier_size}",
            )
        try:
            with verifier.open("rb") as handle:
                verifier_bytes = handle.read(EXPECTED_EMBEDDED_VERIFIER_BYTES + 1)
        except MemoryError:
            fail("EMBEDDED_VERIFIER_SIZE_INVALID", "embedded verifier exceeded the bounded read allocation")
        if len(verifier_bytes) != EXPECTED_EMBEDDED_VERIFIER_BYTES:
            fail(
                "EMBEDDED_VERIFIER_SIZE_INVALID",
                f"embedded verifier changed during bounded read: expected={EXPECTED_EMBEDDED_VERIFIER_BYTES} observed={len(verifier_bytes)}",
            )
        observed = sha256_bytes(verifier_bytes)
''',
    "bounded verifier read",
)
bootstrap = replace_once(
    bootstrap,
    '''            "embeddedVerifierExecuted": False if exc.code == "EMBEDDED_VERIFIER_UNTRUSTED" else None,
''',
    '''            "embeddedVerifierExecuted": False
            if exc.code in {"EMBEDDED_VERIFIER_UNTRUSTED", "EMBEDDED_VERIFIER_SIZE_INVALID"}
            else None,
''',
    "structured non-execution refusal",
)
BOOTSTRAP.write_text(bootstrap, encoding="utf-8", newline="\n")

tests = TESTS.read_text(encoding="utf-8")
tests = replace_once(
    tests,
    '''        embedded = self.root / "RECOVERY/verify_cartridge.py"
        embedded.write_text("raise SystemExit('MALICIOUS EXECUTED')\\n", encoding="utf-8")
''',
    '''        embedded = self.root / "RECOVERY/verify_cartridge.py"
        malicious_verifier = b"raise SystemExit('MALICIOUS EXECUTED')\\n"
        self.assertLess(len(malicious_verifier), bootstrap.EXPECTED_EMBEDDED_VERIFIER_BYTES)
        embedded.write_bytes(
            malicious_verifier
            + b"#" * (bootstrap.EXPECTED_EMBEDDED_VERIFIER_BYTES - len(malicious_verifier))
        )
''',
    "same-size digest substitution witness",
)
tests = replace_once(
    tests,
    '''        self.assertNotEqual(raced.returncode, 0)
        self.assertEqual(raced_verdict["code"], "MEASURED_VERIFIER_MEMBER_MISMATCH")
''',
    '''        self.assertNotEqual(raced.returncode, 0)
        self.assertEqual(raced_verdict["code"], "MEASURED_VERIFIER_MEMBER_MISMATCH")

        oversized = self.parent / "cartridge-oversized-verifier"
        tool.build_cartridge(PROFILE, oversized)
        oversized_verifier = oversized / "RECOVERY/verify_cartridge.py"
        with oversized_verifier.open("wb") as handle:
            handle.seek(bootstrap.EXPECTED_EMBEDDED_VERIFIER_BYTES)
            handle.write(b"x")
        self.assertEqual(
            oversized_verifier.stat().st_size,
            bootstrap.EXPECTED_EMBEDDED_VERIFIER_BYTES + 1,
        )
        code, oversized_verdict = run_bootstrap(oversized)
        self.assertNotEqual(code, 0)
        self.assertEqual(oversized_verdict["code"], "EMBEDDED_VERIFIER_SIZE_INVALID")
        self.assertFalse(oversized_verdict["embeddedVerifierExecuted"])
''',
    "oversized verifier witness",
)
TESTS.write_text(tests, encoding="utf-8", newline="\n")

doc = DOC.read_text(encoding="utf-8")
doc = replace_once(
    doc,
    '''The bootstrap hashes `RECOVERY/verify_cartridge.py` before execution and refuses substitution without running the untrusted file. The isolated launcher injects those same measured bytes into the trusted verifier namespace;''',
    '''The bootstrap first requires the verifier's regular-file size to equal the frozen source length, then performs one bounded read of at most that length plus one byte before hashing. Oversized regular or sparse files therefore terminate a structured non-execution refusal without unbounded allocation. The bootstrap hashes `RECOVERY/verify_cartridge.py` before execution and refuses substitution without running the untrusted file. The isolated launcher injects those same measured bytes into the trusted verifier namespace;''',
    "bounded verifier documentation",
)
DOC.write_text(doc, encoding="utf-8", newline="\n")

print(f"frozen embedded verifier bytes: {verifier_size}")
