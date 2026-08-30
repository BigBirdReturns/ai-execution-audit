from __future__ import annotations

import hashlib
from pathlib import Path

ANCHOR = Path("mating_surface/anchor_node")
BUILDER = ANCHOR / "stc_mary_flight_01_cartridge.py"
VERIFIER = ANCHOR / "verify_stc_mary_flight_01_cartridge.py"
BOOTSTRAP = ANCHOR / "verify_stc_mary_flight_01_cartridge_bootstrap.py"
TESTS = ANCHOR / "conformance/test_stc_mary_flight_01_cartridge.py"
RUNBOOK = ANCHOR / "STC-MARY-FLIGHT-01-CARTRIDGE-01.md"
OLD_VERIFIER_SHA = "28f85f84591761394e278477b6a6e683b5d9a94194e58ceb8aaf65bbec1dd158"


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one replacement anchor, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


coordinate_helpers = '''def coordinate_component_is_link(path: Path) -> bool:
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
    return supplied


'''

replace_once(
    BUILDER,
    '''def validate_output_root(out: Path) -> Path:
''',
    coordinate_helpers + '''def validate_output_root(out: Path) -> Path:
''',
    "builder coordinate helpers",
)
replace_once(
    BUILDER,
    '''def run_bootstrap(root: Path, out: Path | None = None) -> dict[str, Any]:
    bootstrap = source_file(BOOTSTRAP_FILENAME)
    command = [sys.executable, str(bootstrap), str(root)]
''',
    '''def run_bootstrap(root: Path, out: Path | None = None) -> dict[str, Any]:
    supplied_root = validate_cartridge_coordinate(root)
    bootstrap = source_file(BOOTSTRAP_FILENAME)
    command = [sys.executable, str(bootstrap), str(supplied_root)]
''',
    "builder bootstrap coordinate custody",
)
replace_once(
    BUILDER,
    '''    completed = subprocess.run(command, cwd=str(root.parent), check=False, capture_output=True)
''',
    '''    completed = subprocess.run(command, cwd=str(supplied_root.parent), check=False, capture_output=True)
''',
    "builder bootstrap working directory",
)
replace_once(
    BUILDER,
    '''def public_projection(root: Path) -> dict[str, Any]:
    supplied_root = root.expanduser()
    if supplied_root.is_symlink():
        fail("CARTRIDGE_ROOT_INVALID", "cartridge root must be a regular non-symlink directory")
    supplied_root.resolve(strict=True)
''',
    '''def public_projection(root: Path) -> dict[str, Any]:
    supplied_root = validate_cartridge_coordinate(root)
    supplied_root.resolve(strict=True)
''',
    "builder projection coordinate custody",
)
replace_once(
    BUILDER,
    '''        elif args.command == "public-projection":
            supplied_root = args.cartridge.expanduser()
            if supplied_root.is_symlink():
                fail("CARTRIDGE_ROOT_INVALID", "cartridge root must be a regular non-symlink directory")
            root = supplied_root.resolve(strict=True)
''',
    '''        elif args.command == "public-projection":
            supplied_root = validate_cartridge_coordinate(args.cartridge)
            root = supplied_root.resolve(strict=True)
''',
    "builder projection dispatcher custody",
)

replace_once(
    VERIFIER,
    '''def validate_output_path(root: Path, out: Path | None) -> None:
''',
    coordinate_helpers + '''def validate_output_path(root: Path, out: Path | None) -> None:
''',
    "verifier coordinate helpers",
)
replace_once(
    VERIFIER,
    '''def verify_cartridge(root: Path) -> dict[str, Any]:
    supplied_root = root.expanduser()
    if supplied_root.is_symlink():
        fail("CARTRIDGE_ROOT_INVALID", "cartridge root must be a regular non-symlink directory")
    root = supplied_root.resolve(strict=True)
''',
    '''def verify_cartridge(root: Path) -> dict[str, Any]:
    supplied_root = validate_cartridge_coordinate(root)
    root = supplied_root.resolve(strict=True)
''',
    "verifier library coordinate custody",
)
replace_once(
    VERIFIER,
    '''    try:
        supplied_root = args.cartridge.expanduser()
        if supplied_root.is_symlink():
            fail("CARTRIDGE_ROOT_INVALID", "cartridge root must be a regular non-symlink directory")
        root = supplied_root.resolve(strict=True)
''',
    '''    try:
        supplied_root = validate_cartridge_coordinate(args.cartridge)
        root = supplied_root.resolve(strict=True)
''',
    "verifier CLI coordinate custody",
)

replace_once(
    BOOTSTRAP,
    '''import json
import subprocess
''',
    '''import json
import os
import subprocess
''',
    "bootstrap os import",
)
replace_once(
    BOOTSTRAP,
    '''def parse_args(argv: list[str]) -> argparse.Namespace:
''',
    coordinate_helpers + '''def parse_args(argv: list[str]) -> argparse.Namespace:
''',
    "bootstrap coordinate helpers",
)
replace_once(
    BOOTSTRAP,
    '''    try:
        supplied_root = args.cartridge.expanduser()
        if supplied_root.is_symlink():
            fail("CARTRIDGE_ROOT_INVALID", "cartridge root must be a regular non-symlink directory")
        root = supplied_root.resolve(strict=True)
''',
    '''    try:
        supplied_root = validate_cartridge_coordinate(args.cartridge)
        root = supplied_root.resolve(strict=True)
''',
    "bootstrap coordinate custody",
)

ancestor_witness = '''
        ancestor_link = self.parent / "cartridge-parent-symlink"
        ancestor_link.symlink_to(self.root.parent, target_is_directory=True)
        nested_symlink_root = ancestor_link / self.root.name

        nested_bootstrap_out = self.parent / "nested-symlink-bootstrap-verdict.json"
        code, nested_bootstrap = run_bootstrap(nested_symlink_root, nested_bootstrap_out)
        self.assertNotEqual(code, 0)
        self.assertEqual(nested_bootstrap["code"], "CARTRIDGE_ROOT_INVALID")
        self.assertFalse(nested_bootstrap_out.exists())

        nested_direct_out = self.parent / "nested-symlink-direct-verdict.json"
        nested_direct = subprocess.run(
            [sys.executable, str(EMBEDDED_VERIFIER_SOURCE), str(nested_symlink_root), "--out", str(nested_direct_out)],
            check=False,
            capture_output=True,
        )
        nested_direct_verdict = json.loads(nested_direct.stdout.decode("utf-8"))
        self.assertNotEqual(nested_direct.returncode, 0)
        self.assertEqual(nested_direct_verdict["code"], "CARTRIDGE_ROOT_INVALID")
        self.assertFalse(nested_direct_out.exists())

        nested_tool_verify_out = self.parent / "nested-symlink-tool-verdict.json"
        nested_tool_verify = subprocess.run(
            [sys.executable, str(MAIN_TOOL), "verify", str(nested_symlink_root), "--out", str(nested_tool_verify_out)],
            check=False,
            capture_output=True,
        )
        nested_tool_verify_verdict = json.loads(nested_tool_verify.stdout.decode("utf-8"))
        self.assertNotEqual(nested_tool_verify.returncode, 0)
        self.assertEqual(nested_tool_verify_verdict["code"], "CARTRIDGE_ROOT_INVALID")
        self.assertFalse(nested_tool_verify_out.exists())

        nested_projection_out = self.parent / "nested-symlink-projection.json"
        nested_projected = subprocess.run(
            [sys.executable, str(MAIN_TOOL), "public-projection", str(nested_symlink_root), "--out", str(nested_projection_out)],
            check=False,
            capture_output=True,
        )
        nested_projected_verdict = json.loads(nested_projected.stdout.decode("utf-8"))
        self.assertNotEqual(nested_projected.returncode, 0)
        self.assertEqual(nested_projected_verdict["code"], "CARTRIDGE_ROOT_INVALID")
        self.assertFalse(nested_projection_out.exists())

        nested_library_bootstrap_out = self.parent / "nested-symlink-library-bootstrap.json"
        with self.assertRaises(tool.BuildError) as nested_library_bootstrap:
            tool.run_bootstrap(nested_symlink_root, nested_library_bootstrap_out)
        self.assertEqual(nested_library_bootstrap.exception.code, "CARTRIDGE_ROOT_INVALID")
        self.assertFalse(nested_library_bootstrap_out.exists())

        with self.assertRaises(tool.BuildError) as nested_library_projection:
            tool.public_projection(nested_symlink_root)
        self.assertEqual(nested_library_projection.exception.code, "CARTRIDGE_ROOT_INVALID")
        with self.assertRaises(verifier.CartridgeError) as nested_library_verification:
            verifier.verify_cartridge(nested_symlink_root)
        self.assertEqual(nested_library_verification.exception.code, "CARTRIDGE_ROOT_INVALID")
'''

replace_once(
    TESTS,
    '''        with self.assertRaises(verifier.CartridgeError) as library_verification:
            verifier.verify_cartridge(symlink_root)
        self.assertEqual(library_verification.exception.code, "CARTRIDGE_ROOT_INVALID")

    def test_21_existing_output_refused(self) -> None:
''',
    '''        with self.assertRaises(verifier.CartridgeError) as library_verification:
            verifier.verify_cartridge(symlink_root)
        self.assertEqual(library_verification.exception.code, "CARTRIDGE_ROOT_INVALID")
''' + ancestor_witness + '''
    def test_21_existing_output_refused(self) -> None:
''',
    "nested ancestor-link witness",
)

replace_once(
    RUNBOOK,
    '''A copied bundle remains verifiable from a foreign working directory with standard-library Python. Repository history, MARY source, the builder, the original checkout, a network service, provider credential, and private evidence are not required.
''',
    '''A copied bundle remains verifiable from a foreign working directory with standard-library Python. Repository history, MARY source, the builder, the original checkout, a network service, provider credential, and private evidence are not required. Before resolution, every verification and projection route walks the lexical absolute cartridge coordinate component by component and refuses a symlink or Windows junction in the final component or any ancestor, so the supplied coordinate cannot be retargeted through a linked parent.
''',
    "runbook ancestor-link custody",
)

verifier_sha = hashlib.sha256(VERIFIER.read_bytes()).hexdigest()
replace_once(
    BUILDER,
    f'EXPECTED_VERIFIER_SHA256 = "{OLD_VERIFIER_SHA}"',
    f'EXPECTED_VERIFIER_SHA256 = "{verifier_sha}"',
    "builder verifier digest",
)
replace_once(
    BOOTSTRAP,
    f'EXPECTED_EMBEDDED_VERIFIER_SHA256 = "{OLD_VERIFIER_SHA}"',
    f'EXPECTED_EMBEDDED_VERIFIER_SHA256 = "{verifier_sha}"',
    "bootstrap verifier digest",
)

print(f"embedded verifier sha256: {verifier_sha}")
