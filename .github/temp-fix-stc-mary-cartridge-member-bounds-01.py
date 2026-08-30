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


version_helpers = '''MINIMUM_PYTHON = (3, 12)


def require_supported_python() -> None:
    if sys.version_info < MINIMUM_PYTHON:
        fail(
            "PYTHON_VERSION_UNSUPPORTED",
            f"Python {MINIMUM_PYTHON[0]}.{MINIMUM_PYTHON[1]} or newer is required for junction-safe cartridge custody",
        )


'''

coordinate_helpers = '''def coordinate_component_is_link(path: Path) -> bool:
    require_supported_python()
    try:
        return path.is_symlink() or path.is_junction()
    except OSError as exc:
        fail("CARTRIDGE_ROOT_INVALID", f"cartridge coordinate component could not be inspected: {path}: {exc}")


def validate_cartridge_coordinate(path: Path) -> Path:
    require_supported_python()
    try:
        supplied = path.expanduser()
    except RuntimeError as exc:
        fail("CARTRIDGE_PATH_EXPANSION_FAILED", f"cartridge coordinate user expansion failed: {exc}")
    absolute = Path(os.path.abspath(os.fspath(supplied)))
    parts = absolute.parts
    if not parts:
        fail("CARTRIDGE_ROOT_INVALID", "cartridge coordinate is empty")
    current = Path(parts[0])
    if coordinate_component_is_link(current):
        fail("CARTRIDGE_ROOT_INVALID", f"cartridge coordinate contains a symlink or junction component: {current}")
    for part in parts[1:]:
        current = current / part
        if coordinate_component_is_link(current):
            fail("CARTRIDGE_ROOT_INVALID", f"cartridge coordinate contains a symlink or junction component: {current}")
    return absolute


'''

old_coordinate_helpers = '''def coordinate_component_is_link(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        junction_probe = getattr(path, "is_junction", None)
        return bool(callable(junction_probe) and junction_probe())
    except OSError as exc:
        fail("CARTRIDGE_ROOT_INVALID", f"cartridge coordinate component could not be inspected: {path}: {exc}")


def validate_cartridge_coordinate(path: Path) -> Path:
    supplied = path.expanduser()
    absolute = Path(os.path.abspath(os.fspath(supplied)))
    parts = absolute.parts
    if not parts:
        fail("CARTRIDGE_ROOT_INVALID", "cartridge coordinate is empty")
    current = Path(parts[0])
    if coordinate_component_is_link(current):
        fail("CARTRIDGE_ROOT_INVALID", f"cartridge coordinate contains a symlink or junction component: {current}")
    for part in parts[1:]:
        current = current / part
        if coordinate_component_is_link(current):
            fail("CARTRIDGE_ROOT_INVALID", f"cartridge coordinate contains a symlink or junction component: {current}")
    return absolute


'''

old_bootstrap_coordinate_helpers = old_coordinate_helpers.replace("    return absolute\n", "    return supplied\n")

verifier = VERIFIER.read_text(encoding="utf-8")
verifier = replace_once(
    verifier,
    'EXPECTED_DIRECTORIES = {"CARTRIDGE", "PUBLIC", "RECOVERY"}\n',
    'EXPECTED_DIRECTORIES = {"CARTRIDGE", "PUBLIC", "RECOVERY"}\nMAX_MEMBER_BYTES = 1_048_576\n',
    "member limit constant",
)
verifier = replace_once(
    verifier,
    '''def fail(code: str, message: str) -> None:
    raise CartridgeError(code, message)


''',
    '''def fail(code: str, message: str) -> None:
    raise CartridgeError(code, message)


''' + version_helpers,
    "verifier Python floor",
)
verifier = replace_once(verifier, old_coordinate_helpers, coordinate_helpers, "verifier coordinate custody")
verifier = replace_once(
    verifier,
    '''def read_member(root: Path, relative: str) -> bytes:
    path = root / PurePosixPath(relative)
    if not path.is_file() or path.is_symlink():
        fail("MEMBER_INVALID", relative)
    data = path.read_bytes()
    if b"\\r" in data:
        fail("NON_LF_AUTHORITATIVE_BYTES", relative)
    return data
''',
    '''def read_member(root: Path, relative: str) -> bytes:
    path = root / PurePosixPath(relative)
    if not path.is_file() or path.is_symlink():
        fail("MEMBER_INVALID", relative)
    size = path.stat().st_size
    if size < 0 or size > MAX_MEMBER_BYTES:
        fail(
            "MEMBER_SIZE_INVALID",
            f"{relative} exceeds the bounded member size: maximum={MAX_MEMBER_BYTES} observed={size}",
        )
    try:
        with path.open("rb") as handle:
            data = handle.read(MAX_MEMBER_BYTES + 1)
    except MemoryError:
        fail("MEMBER_SIZE_INVALID", f"{relative} exceeded the bounded member read allocation")
    if len(data) != size or len(data) > MAX_MEMBER_BYTES:
        fail(
            "MEMBER_SIZE_INVALID",
            f"{relative} changed during bounded read: expected={size} observed={len(data)}",
        )
    if b"\\r" in data:
        fail("NON_LF_AUTHORITATIVE_BYTES", relative)
    return data
''',
    "bounded member reader",
)
VERIFIER.write_text(verifier, encoding="utf-8", newline="\n")
verifier_sha = hashlib.sha256(VERIFIER.read_bytes()).hexdigest()
verifier_bytes = len(VERIFIER.read_bytes())

bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
bootstrap = replace_once(
    bootstrap,
    '''def fail(code: str, message: str) -> None:
    raise BootstrapError(code, message)


''',
    '''def fail(code: str, message: str) -> None:
    raise BootstrapError(code, message)


''' + version_helpers,
    "bootstrap Python floor",
)
bootstrap = replace_once(
    bootstrap,
    old_bootstrap_coordinate_helpers,
    coordinate_helpers,
    "bootstrap coordinate custody",
)
old_digest = next(line for line in bootstrap.splitlines() if line.startswith("EXPECTED_EMBEDDED_VERIFIER_SHA256 = "))
old_size = next(line for line in bootstrap.splitlines() if line.startswith("EXPECTED_EMBEDDED_VERIFIER_BYTES = "))
bootstrap = bootstrap.replace(old_digest, f'EXPECTED_EMBEDDED_VERIFIER_SHA256 = "{verifier_sha}"', 1)
bootstrap = bootstrap.replace(old_size, f"EXPECTED_EMBEDDED_VERIFIER_BYTES = {verifier_bytes}", 1)
BOOTSTRAP.write_text(bootstrap, encoding="utf-8", newline="\n")

tool = TOOL.read_text(encoding="utf-8")
tool = replace_once(
    tool,
    '''def fail(code: str, message: str) -> None:
    raise BuildError(code, message)


''',
    '''def fail(code: str, message: str) -> None:
    raise BuildError(code, message)


''' + version_helpers,
    "tool Python floor",
)
tool = replace_once(tool, old_coordinate_helpers, coordinate_helpers, "tool coordinate custody")
old_tool_digest = next(line for line in tool.splitlines() if line.startswith("EXPECTED_VERIFIER_SHA256 = "))
tool = tool.replace(old_tool_digest, f'EXPECTED_VERIFIER_SHA256 = "{verifier_sha}"', 1)
TOOL.write_text(tool, encoding="utf-8", newline="\n")

tests = TESTS.read_text(encoding="utf-8")
tests = replace_once(
    tests,
    '''        code, oversized_verdict = run_bootstrap(oversized)
        self.assertNotEqual(code, 0)
        self.assertEqual(oversized_verdict["code"], "EMBEDDED_VERIFIER_SIZE_INVALID")
        self.assertFalse(oversized_verdict["embeddedVerifierExecuted"])
''',
    '''        code, oversized_verdict = run_bootstrap(oversized)
        self.assertNotEqual(code, 0)
        self.assertEqual(oversized_verdict["code"], "EMBEDDED_VERIFIER_SIZE_INVALID")
        self.assertFalse(oversized_verdict["embeddedVerifierExecuted"])

        for relative in ("PUBLIC/status.json", "MANIFEST.json"):
            with self.subTest(oversized_member=relative):
                bounded = self.parent / ("cartridge-oversized-" + relative.replace("/", "-"))
                tool.build_cartridge(PROFILE, bounded)
                member = bounded / relative
                with member.open("wb") as handle:
                    handle.seek(verifier.MAX_MEMBER_BYTES)
                    handle.write(b"x")
                self.assertEqual(member.stat().st_size, verifier.MAX_MEMBER_BYTES + 1)
                code, bounded_verdict = run_bootstrap(bounded)
                self.assertNotEqual(code, 0)
                self.assertEqual(bounded_verdict["code"], "MEMBER_SIZE_INVALID")
''',
    "all-member size witnesses",
)
tests = replace_once(
    tests,
    '''    def test_21_existing_output_refused(self) -> None:
''',
    '''        with patch.object(Path, "expanduser", side_effect=RuntimeError("unknown user")):
            with self.assertRaises(tool.BuildError) as tool_expansion:
                tool.validate_cartridge_coordinate(Path("~missing-user/cartridge"))
            self.assertEqual(tool_expansion.exception.code, "CARTRIDGE_PATH_EXPANSION_FAILED")
            with self.assertRaises(verifier.CartridgeError) as verifier_expansion:
                verifier.validate_cartridge_coordinate(Path("~missing-user/cartridge"))
            self.assertEqual(verifier_expansion.exception.code, "CARTRIDGE_PATH_EXPANSION_FAILED")
            with self.assertRaises(bootstrap.BootstrapError) as bootstrap_expansion:
                bootstrap.validate_cartridge_coordinate(Path("~missing-user/cartridge"))
            self.assertEqual(bootstrap_expansion.exception.code, "CARTRIDGE_PATH_EXPANSION_FAILED")

        with patch.object(sys, "version_info", (3, 11, 9)):
            with self.assertRaises(tool.BuildError) as tool_version:
                tool.validate_cartridge_coordinate(self.root)
            self.assertEqual(tool_version.exception.code, "PYTHON_VERSION_UNSUPPORTED")
            with self.assertRaises(verifier.CartridgeError) as verifier_version:
                verifier.validate_cartridge_coordinate(self.root)
            self.assertEqual(verifier_version.exception.code, "PYTHON_VERSION_UNSUPPORTED")
            with self.assertRaises(bootstrap.BootstrapError) as bootstrap_version:
                bootstrap.validate_cartridge_coordinate(self.root)
            self.assertEqual(bootstrap_version.exception.code, "PYTHON_VERSION_UNSUPPORTED")

    def test_21_existing_output_refused(self) -> None:
''',
    "structured expansion and Python-floor witnesses",
)
TESTS.write_text(tests, encoding="utf-8", newline="\n")

doc = DOC.read_text(encoding="utf-8")
doc = replace_once(
    doc,
    '''A copied bundle remains verifiable from a foreign working directory with standard-library Python. Repository history, MARY source, the builder, the original checkout, a network service, provider credential, and private evidence are not required.''',
    '''A copied bundle remains verifiable from a foreign working directory with standard-library Python 3.12 or newer. Older interpreters terminate a structured `PYTHON_VERSION_UNSUPPORTED` refusal before coordinate inspection because junction-safe custody depends on the standard `Path.is_junction()` contract. Unresolvable `~user` coordinates terminate `CARTRIDGE_PATH_EXPANSION_FAILED` rather than escaping through an uncaught runtime exception. Repository history, MARY source, the builder, the original checkout, a network service, provider credential, and private evidence are not required.''',
    "portable Python requirement",
)
doc = replace_once(
    doc,
    '''The embedded verifier then reconstructs the profile, source binding, work-unit, mission, public status, member rows, manifest, cartridge identity, mission identity, work-unit identity, source-binding identity, and bundle identity.''',
    '''Every closed-denominator member, including `MANIFEST.json`, is size-checked against a trusted one-mebibyte ceiling before a bounded `maximum + 1` read. Oversized regular or sparse members, moving-length reads, and bounded-allocation failure terminate structured `MEMBER_SIZE_INVALID` before JSON parsing. The embedded verifier then reconstructs the profile, source binding, work-unit, mission, public status, member rows, manifest, cartridge identity, mission identity, work-unit identity, source-binding identity, and bundle identity.''',
    "bounded all-member documentation",
)
DOC.write_text(doc, encoding="utf-8", newline="\n")

print(f"embedded verifier sha256: {verifier_sha}")
print(f"embedded verifier bytes: {verifier_bytes}")
