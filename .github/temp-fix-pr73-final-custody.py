from __future__ import annotations

import hashlib
import re
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


def replace_range(text: str, start: str, end: str, replacement: str, label: str) -> str:
    pattern = re.compile(rf"^{re.escape(start)}.*?(?=^{re.escape(end)})", re.MULTILINE | re.DOTALL)
    updated, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        raise SystemExit(f"{label}: expected one range, found {count}")
    return updated


VERIFIER_COORDINATE_HELPERS = '''def coordinate_component_is_link(path: Path, *, code: str, label: str) -> bool:
    require_supported_python()
    try:
        return path.is_symlink() or path.is_junction()
    except OSError as exc:
        fail(code, f"{label} component could not be inspected: {path}: {exc}")


def validate_lexical_coordinate(
    path: Path,
    *,
    label: str,
    expansion_code: str,
    invalid_code: str,
) -> Path:
    require_supported_python()
    if any(part == os.pardir for part in path.parts):
        fail(invalid_code, f"{label} may not contain a parent-directory segment")
    try:
        supplied = path.expanduser()
    except RuntimeError as exc:
        fail(expansion_code, f"{label} user expansion failed: {exc}")
    if any(part == os.pardir for part in supplied.parts):
        fail(invalid_code, f"{label} may not contain a parent-directory segment")
    try:
        absolute = Path(os.path.abspath(os.fspath(supplied)))
    except (OSError, ValueError) as exc:
        fail(invalid_code, f"{label} could not be made absolute: {exc}")
    parts = absolute.parts
    if not parts:
        fail(invalid_code, f"{label} is empty")
    current = Path(parts[0])
    if coordinate_component_is_link(current, code=invalid_code, label=label):
        fail(invalid_code, f"{label} contains a symlink or junction component: {current}")
    for part in parts[1:]:
        current = current / part
        if coordinate_component_is_link(current, code=invalid_code, label=label):
            fail(invalid_code, f"{label} contains a symlink or junction component: {current}")
    return absolute


def validate_cartridge_coordinate(path: Path) -> Path:
    return validate_lexical_coordinate(
        path,
        label="cartridge coordinate",
        expansion_code="CARTRIDGE_PATH_EXPANSION_FAILED",
        invalid_code="CARTRIDGE_ROOT_INVALID",
    )


def validate_output_coordinate(path: Path) -> Path:
    return validate_lexical_coordinate(
        path,
        label="verdict output coordinate",
        expansion_code="VERDICT_PATH_EXPANSION_FAILED",
        invalid_code="VERDICT_PATH_INVALID",
    )


'''

TOOL_COORDINATE_HELPERS = '''def coordinate_component_is_link(path: Path, *, code: str, label: str) -> bool:
    require_supported_python()
    try:
        return path.is_symlink() or path.is_junction()
    except OSError as exc:
        fail(code, f"{label} component could not be inspected: {path}: {exc}")


def validate_lexical_coordinate(
    path: Path,
    *,
    label: str,
    expansion_code: str,
    invalid_code: str,
) -> Path:
    require_supported_python()
    if any(part == os.pardir for part in path.parts):
        fail(invalid_code, f"{label} may not contain a parent-directory segment")
    try:
        supplied = path.expanduser()
    except RuntimeError as exc:
        fail(expansion_code, f"{label} user expansion failed: {exc}")
    if any(part == os.pardir for part in supplied.parts):
        fail(invalid_code, f"{label} may not contain a parent-directory segment")
    try:
        absolute = Path(os.path.abspath(os.fspath(supplied)))
    except (OSError, ValueError) as exc:
        fail(invalid_code, f"{label} could not be made absolute: {exc}")
    parts = absolute.parts
    if not parts:
        fail(invalid_code, f"{label} is empty")
    current = Path(parts[0])
    if coordinate_component_is_link(current, code=invalid_code, label=label):
        fail(invalid_code, f"{label} contains a symlink or junction component: {current}")
    for part in parts[1:]:
        current = current / part
        if coordinate_component_is_link(current, code=invalid_code, label=label):
            fail(invalid_code, f"{label} contains a symlink or junction component: {current}")
    return absolute


def validate_cartridge_coordinate(path: Path) -> Path:
    return validate_lexical_coordinate(
        path,
        label="cartridge coordinate",
        expansion_code="CARTRIDGE_PATH_EXPANSION_FAILED",
        invalid_code="CARTRIDGE_ROOT_INVALID",
    )


def validate_output_coordinate(path: Path, *, label: str = "output coordinate") -> Path:
    return validate_lexical_coordinate(
        path,
        label=label,
        expansion_code="OUTPUT_PATH_EXPANSION_FAILED",
        invalid_code="OUTPUT_PATH_INVALID",
    )


'''

VERIFIER_TREE_AND_READ = '''def validate_tree(root: Path) -> None:
    if coordinate_component_is_link(root, code="CARTRIDGE_ROOT_INVALID", label="cartridge root") or not root.is_dir():
        fail("CARTRIDGE_ROOT_INVALID", "cartridge root must be a regular non-linked directory")
    files: set[str] = set()
    directories: set[str] = set()
    pending = [root]
    while pending:
        directory = pending.pop()
        try:
            entries = tuple(directory.iterdir())
        except OSError as exc:
            fail("CARTRIDGE_TREE_READ_FAILED", f"{directory}: {exc}")
        for path in entries:
            relative = path.relative_to(root).as_posix()
            pure = PurePosixPath(relative)
            if pure.is_absolute() or ".." in pure.parts or "\\\\" in relative:
                fail("UNSAFE_MEMBER_PATH", relative)
            if coordinate_component_is_link(path, code="SYMLINK_MEMBER_REFUSED", label="cartridge member"):
                fail("SYMLINK_MEMBER_REFUSED", relative)
            try:
                if path.is_dir():
                    directories.add(relative)
                    pending.append(path)
                elif path.is_file():
                    files.add(relative)
                else:
                    fail("NON_REGULAR_MEMBER_REFUSED", relative)
            except OSError as exc:
                fail("NON_REGULAR_MEMBER_REFUSED", f"{relative}: {exc}")
    expected_files = {"MANIFEST.json", *EXPECTED_FILES}
    if files != expected_files:
        fail("FILE_DENOMINATOR_INVALID", f"missing={sorted(expected_files - files)} unknown={sorted(files - expected_files)}")
    if directories != EXPECTED_DIRECTORIES:
        fail("DIRECTORY_DENOMINATOR_INVALID", f"missing={sorted(EXPECTED_DIRECTORIES - directories)} unknown={sorted(directories - EXPECTED_DIRECTORIES)}")


def read_member(root: Path, relative: str) -> bytes:
    path = root / PurePosixPath(relative)
    if coordinate_component_is_link(path, code="MEMBER_INVALID", label=f"cartridge member {relative}") or not path.is_file():
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


'''


def patch_verifier() -> None:
    text = VERIFIER.read_text(encoding="utf-8")
    text = replace_range(
        text,
        "def coordinate_component_is_link",
        "def validate_output_path",
        VERIFIER_COORDINATE_HELPERS,
        "verifier coordinate helpers",
    )
    text = replace_range(
        text,
        "def validate_tree",
        "def validate_profile",
        VERIFIER_TREE_AND_READ,
        "verifier tree and member read",
    )
    text = replace_once(
        text,
        '''        supplied_root = validate_cartridge_coordinate(args.cartridge)\n        root = supplied_root.resolve(strict=True)\n        validate_output_path(root, args.out)\n        measured_verifier_bytes = globals().get("_STC_MARY_BOOTSTRAP_MEASURED_VERIFIER_BYTES")''',
        '''        supplied_root = validate_cartridge_coordinate(args.cartridge)\n        root = supplied_root.resolve(strict=True)\n        output = None if args.out is None else validate_output_coordinate(args.out)\n        validate_output_path(root, output)\n        measured_verifier_bytes = globals().get("_STC_MARY_BOOTSTRAP_MEASURED_VERIFIER_BYTES")''',
        "verifier main output coordinate",
    )
    text = replace_once(
        text,
        '''        if args.out is None:\n            sys.stdout.buffer.write(data)\n        else:\n            args.out.parent.mkdir(parents=True, exist_ok=True)\n            args.out.write_bytes(data)''',
        '''        if output is None:\n            sys.stdout.buffer.write(data)\n        else:\n            output.parent.mkdir(parents=True, exist_ok=True)\n            output.write_bytes(data)''',
        "verifier main output write",
    )
    VERIFIER.write_text(text, encoding="utf-8", newline="\n")


def patch_bootstrap(verifier_sha: str, verifier_bytes: int) -> None:
    text = BOOTSTRAP.read_text(encoding="utf-8")
    text = re.sub(
        r'^EXPECTED_EMBEDDED_VERIFIER_SHA256 = "[0-9a-f]{64}"$',
        f'EXPECTED_EMBEDDED_VERIFIER_SHA256 = "{verifier_sha}"',
        text,
        count=1,
        flags=re.MULTILINE,
    )
    text = re.sub(
        r'^EXPECTED_EMBEDDED_VERIFIER_BYTES = [0-9]+$',
        f'EXPECTED_EMBEDDED_VERIFIER_BYTES = {verifier_bytes}',
        text,
        count=1,
        flags=re.MULTILINE,
    )
    text = replace_range(
        text,
        "def coordinate_component_is_link",
        "def parse_args",
        VERIFIER_COORDINATE_HELPERS,
        "bootstrap coordinate helpers",
    )
    text = replace_once(
        text,
        '''        supplied_root = validate_cartridge_coordinate(args.cartridge)\n        root = supplied_root.resolve(strict=True)\n        if not root.is_dir():\n            fail("CARTRIDGE_ROOT_INVALID", "cartridge root must be a regular non-symlink directory")\n        if args.out is not None:\n            if is_within(args.out.resolve(strict=False), root):\n                fail("VERDICT_INSIDE_CARTRIDGE", "bootstrap verdict may not be written inside the measured cartridge")\n            if args.out.exists():\n                fail("VERDICT_OUTPUT_EXISTS", "bootstrap verdict output must not already exist")\n        verifier = root / "RECOVERY" / "verify_cartridge.py"\n        if not verifier.is_file() or verifier.is_symlink():\n            fail("EMBEDDED_VERIFIER_MISSING", "embedded verifier is missing or not regular")''',
        '''        supplied_root = validate_cartridge_coordinate(args.cartridge)\n        root = supplied_root.resolve(strict=True)\n        if not root.is_dir():\n            fail("CARTRIDGE_ROOT_INVALID", "cartridge root must be a regular non-linked directory")\n        output = None if args.out is None else validate_output_coordinate(args.out)\n        if output is not None:\n            if is_within(output.resolve(strict=False), root):\n                fail("VERDICT_INSIDE_CARTRIDGE", "bootstrap verdict may not be written inside the measured cartridge")\n            if output.exists():\n                fail("VERDICT_OUTPUT_EXISTS", "bootstrap verdict output must not already exist")\n        recovery = root / "RECOVERY"\n        if coordinate_component_is_link(recovery, code="EMBEDDED_VERIFIER_MISSING", label="embedded verifier parent") or not recovery.is_dir():\n            fail("EMBEDDED_VERIFIER_MISSING", "embedded verifier parent is missing, linked, or not regular")\n        verifier = recovery / "verify_cartridge.py"\n        if coordinate_component_is_link(verifier, code="EMBEDDED_VERIFIER_MISSING", label="embedded verifier") or not verifier.is_file():\n            fail("EMBEDDED_VERIFIER_MISSING", "embedded verifier is missing, linked, or not regular")''',
        "bootstrap main coordinate and verifier parent",
    )
    text = replace_once(
        text,
        '''        if args.out is None:\n            sys.stdout.buffer.write(data)\n        else:\n            args.out.parent.mkdir(parents=True, exist_ok=True)\n            args.out.write_bytes(data)''',
        '''        if output is None:\n            sys.stdout.buffer.write(data)\n        else:\n            output.parent.mkdir(parents=True, exist_ok=True)\n            output.write_bytes(data)''',
        "bootstrap output write",
    )
    BOOTSTRAP.write_text(text, encoding="utf-8", newline="\n")


def patch_tool(verifier_sha: str) -> None:
    text = TOOL.read_text(encoding="utf-8")
    text = re.sub(
        r'^EXPECTED_VERIFIER_SHA256 = "[0-9a-f]{64}"$',
        f'EXPECTED_VERIFIER_SHA256 = "{verifier_sha}"',
        text,
        count=1,
        flags=re.MULTILINE,
    )
    text = replace_range(
        text,
        "def coordinate_component_is_link",
        "def validate_output_root",
        TOOL_COORDINATE_HELPERS,
        "tool coordinate helpers",
    )
    text = replace_range(
        text,
        "def validate_output_root",
        "def validate_projection_output",
        '''def validate_output_root(out: Path) -> Path:
    absolute = validate_output_coordinate(out, label="cartridge build output coordinate")
    resolved = absolute.resolve(strict=False)
    if absolute.exists():
        fail("OUTPUT_EXISTS", "cartridge output must not already exist")
    if not absolute.parent.exists() or not absolute.parent.is_dir():
        fail("OUTPUT_PARENT_INVALID", "cartridge output parent must be an existing regular directory")
    if resolved == Path(resolved.anchor) or resolved == Path.home().resolve() or resolved == Path.cwd().resolve():
        fail("OUTPUT_ROOT_UNSAFE", "cartridge output may not be a filesystem root, home, or current directory")
    if has_git_ancestor(resolved.parent):
        fail("REPOSITORY_LOCAL_OUTPUT_REFUSED", "cartridge output must remain outside every Git repository")
    return resolved


''',
        "tool build output root",
    )
    text = replace_range(
        text,
        "def source_file",
        "def build_cartridge",
        '''def source_file(name: str) -> Path:
    path = Path(__file__).resolve().parent / name
    if coordinate_component_is_link(path, code="SOURCE_MEMBER_MISSING", label="source member") or not path.is_file():
        fail("SOURCE_MEMBER_MISSING", name)
    return path


''',
        "tool source file",
    )
    text = replace_range(
        text,
        "def run_bootstrap",
        "def public_projection",
        '''def run_bootstrap(root: Path, out: Path | None = None) -> dict[str, Any]:
    absolute_root = validate_cartridge_coordinate(root)
    absolute_out = None if out is None else validate_output_coordinate(out, label="bootstrap verdict output coordinate")
    bootstrap = source_file(BOOTSTRAP_FILENAME)
    command = [sys.executable, str(bootstrap), str(absolute_root)]
    if absolute_out is not None:
        command.extend(["--out", str(absolute_out)])
    completed = subprocess.run(command, cwd=str(absolute_root.parent), check=False, capture_output=True)
    if absolute_out is not None and completed.returncode == 0:
        try:
            return json.loads(absolute_out.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            fail("BOOTSTRAP_VERDICT_READ_FAILED", str(exc))
    try:
        verdict = json.loads(completed.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        fail("BOOTSTRAP_OUTPUT_INVALID", str(exc))
    if completed.returncode != 0:
        code = verdict.get("code", "BOOTSTRAP_REFUSED") if isinstance(verdict, dict) else "BOOTSTRAP_REFUSED"
        fail(str(code), "external bootstrap refused the cartridge")
    return verdict


''',
        "tool bootstrap launch",
    )
    text = replace_once(
        text,
        '''        elif args.command == "public-projection":\n            supplied_root = validate_cartridge_coordinate(args.cartridge)\n            root = supplied_root.resolve(strict=True)\n            validate_projection_output(root, args.out)\n            emit(public_projection(supplied_root), args.out)''',
        '''        elif args.command == "public-projection":\n            supplied_root = validate_cartridge_coordinate(args.cartridge)\n            root = supplied_root.resolve(strict=True)\n            output = None if args.out is None else validate_output_coordinate(args.out, label="public projection output coordinate")\n            validate_projection_output(root, output)\n            emit(public_projection(supplied_root), output)''',
        "tool projection output coordinate",
    )
    TOOL.write_text(text, encoding="utf-8", newline="\n")


def patch_tests() -> None:
    text = TESTS.read_text(encoding="utf-8")
    helper_anchor = '''    payload = out.read_bytes() if out is not None and out.exists() and completed.returncode == 0 else completed.stdout\n    return completed.returncode, json.loads(payload.decode("utf-8"))\n\n\nclass CartridgeTest(unittest.TestCase):\n'''
    helper_replacement = '''    payload = out.read_bytes() if out is not None and out.exists() and completed.returncode == 0 else completed.stdout\n    return completed.returncode, json.loads(payload.decode("utf-8"))\n\n\ndef make_directory_link(link: Path, target: Path) -> None:\n    if os.name == "nt":\n        completed = subprocess.run(\n            ["cmd.exe", "/d", "/c", f'mklink /J "{link}" "{target}"'],\n            check=False,\n            capture_output=True,\n            text=True,\n        )\n        if completed.returncode != 0:\n            raise OSError(f"junction creation failed: {completed.stdout} {completed.stderr}")\n    else:\n        link.symlink_to(target, target_is_directory=True)\n\n\ndef remove_directory_link(link: Path) -> None:\n    if os.name == "nt":\n        if link.exists():\n            link.rmdir()\n    elif link.is_symlink():\n        link.unlink()\n\n\nclass CartridgeTest(unittest.TestCase):\n'''
    text = replace_once(text, helper_anchor, helper_replacement, "test directory-link helper")

    test20_insert = '''\n        dotdot_safe = self.parent / "dotdot-safe"\n        dotdot_safe.mkdir()\n        normalized_cartridge = dotdot_safe / "cartridge"\n        shutil.copytree(self.root, normalized_cartridge)\n        dotdot_target = self.parent / "dotdot-target"\n        dotdot_target.mkdir()\n        dotdot_link = dotdot_safe / "link"\n        make_directory_link(dotdot_link, dotdot_target)\n        dotdot_coordinate = dotdot_link / ".." / "cartridge"\n        self.assertIn("..", dotdot_coordinate.parts)\n        try:\n            code, dotdot_bootstrap = run_bootstrap(dotdot_coordinate, cwd=self.parent)\n            self.assertNotEqual(code, 0)\n            self.assertEqual(dotdot_bootstrap["code"], "CARTRIDGE_ROOT_INVALID")\n\n            dotdot_direct = subprocess.run(\n                [sys.executable, str(EMBEDDED_VERIFIER_SOURCE), str(dotdot_coordinate)],\n                cwd=str(self.parent),\n                check=False,\n                capture_output=True,\n            )\n            self.assertNotEqual(dotdot_direct.returncode, 0)\n            self.assertEqual(json.loads(dotdot_direct.stdout.decode("utf-8"))["code"], "CARTRIDGE_ROOT_INVALID")\n\n            dotdot_tool = subprocess.run(\n                [sys.executable, str(MAIN_TOOL), "verify", str(dotdot_coordinate)],\n                cwd=str(self.parent),\n                check=False,\n                capture_output=True,\n            )\n            self.assertNotEqual(dotdot_tool.returncode, 0)\n            self.assertEqual(json.loads(dotdot_tool.stdout.decode("utf-8"))["code"], "CARTRIDGE_ROOT_INVALID")\n\n            with self.assertRaises(tool.BuildError) as dotdot_tool_library:\n                tool.validate_cartridge_coordinate(dotdot_coordinate)\n            self.assertEqual(dotdot_tool_library.exception.code, "CARTRIDGE_ROOT_INVALID")\n            with self.assertRaises(verifier.CartridgeError) as dotdot_verifier_library:\n                verifier.validate_cartridge_coordinate(dotdot_coordinate)\n            self.assertEqual(dotdot_verifier_library.exception.code, "CARTRIDGE_ROOT_INVALID")\n            with self.assertRaises(bootstrap.BootstrapError) as dotdot_bootstrap_library:\n                bootstrap.validate_cartridge_coordinate(dotdot_coordinate)\n            self.assertEqual(dotdot_bootstrap_library.exception.code, "CARTRIDGE_ROOT_INVALID")\n        finally:\n            remove_directory_link(dotdot_link)\n\n        linked_member_root = self.parent / "cartridge-linked-public"\n        tool.build_cartridge(PROFILE, linked_member_root)\n        external_public = self.parent / "external-public"\n        (linked_member_root / "PUBLIC").rename(external_public)\n        linked_public = linked_member_root / "PUBLIC"\n        make_directory_link(linked_public, external_public)\n        try:\n            code, linked_member_verdict = run_bootstrap(linked_member_root)\n            self.assertNotEqual(code, 0)\n            self.assertEqual(linked_member_verdict["code"], "SYMLINK_MEMBER_REFUSED")\n\n            linked_member_direct = subprocess.run(\n                [sys.executable, str(EMBEDDED_VERIFIER_SOURCE), str(linked_member_root)],\n                check=False,\n                capture_output=True,\n            )\n            self.assertNotEqual(linked_member_direct.returncode, 0)\n            self.assertEqual(\n                json.loads(linked_member_direct.stdout.decode("utf-8"))["code"],\n                "SYMLINK_MEMBER_REFUSED",\n            )\n        finally:\n            remove_directory_link(linked_public)\n'''
    text = replace_once(
        text,
        '''            self.assertEqual(bootstrap_version.exception.code, "PYTHON_VERSION_UNSUPPORTED")\n\n    def test_21_existing_output_refused(self) -> None:\n''',
        '''            self.assertEqual(bootstrap_version.exception.code, "PYTHON_VERSION_UNSUPPORTED")\n''' + test20_insert + '''\n    def test_21_existing_output_refused(self) -> None:\n''',
        "test traversal and internal junction witnesses",
    )

    test21_insert = '''\n        physical_output_parent = self.parent / "physical-verdict-parent"\n        (physical_output_parent / "nested").mkdir(parents=True)\n        linked_output_parent = self.parent / "linked-verdict-parent"\n        make_directory_link(linked_output_parent, physical_output_parent)\n        try:\n            linked_verdict = linked_output_parent / "nested" / "verdict.json"\n            code, linked_output_verdict = run_bootstrap(self.root, linked_verdict)\n            self.assertNotEqual(code, 0)\n            self.assertEqual(linked_output_verdict["code"], "VERDICT_PATH_INVALID")\n            self.assertFalse((physical_output_parent / "nested" / "verdict.json").exists())\n\n            tool_linked_verdict = linked_output_parent / "nested" / "tool-verdict.json"\n            tool_verify = subprocess.run(\n                [sys.executable, str(MAIN_TOOL), "verify", str(self.root), "--out", str(tool_linked_verdict)],\n                check=False,\n                capture_output=True,\n            )\n            self.assertNotEqual(tool_verify.returncode, 0)\n            self.assertEqual(json.loads(tool_verify.stdout.decode("utf-8"))["code"], "OUTPUT_PATH_INVALID")\n            self.assertFalse((physical_output_parent / "nested" / "tool-verdict.json").exists())\n\n            linked_projection = linked_output_parent / "nested" / "projection.json"\n            projected = subprocess.run(\n                [sys.executable, str(MAIN_TOOL), "public-projection", str(self.root), "--out", str(linked_projection)],\n                check=False,\n                capture_output=True,\n            )\n            self.assertNotEqual(projected.returncode, 0)\n            self.assertEqual(json.loads(projected.stdout.decode("utf-8"))["code"], "OUTPUT_PATH_INVALID")\n            self.assertFalse((physical_output_parent / "nested" / "projection.json").exists())\n        finally:\n            remove_directory_link(linked_output_parent)\n'''
    text = replace_once(
        text,
        '''        self.assertNotEqual(code, 0)\n        self.assertEqual(verdict["code"], "VERDICT_OUTPUT_EXISTS")\n\n    def test_22_repository_local_build_refused(self) -> None:\n''',
        '''        self.assertNotEqual(code, 0)\n        self.assertEqual(verdict["code"], "VERDICT_OUTPUT_EXISTS")\n''' + test21_insert + '''\n    def test_22_repository_local_build_refused(self) -> None:\n''',
        "test linked output witnesses",
    )

    test22_insert = '''\n        physical_build_parent = self.parent / "physical-build-parent"\n        (physical_build_parent / "nested").mkdir(parents=True)\n        linked_build_parent = self.parent / "linked-build-parent"\n        make_directory_link(linked_build_parent, physical_build_parent)\n        try:\n            linked_build_output = linked_build_parent / "nested" / "product"\n            with self.assertRaises(tool.BuildError) as linked_build:\n                tool.build_cartridge(PROFILE, linked_build_output)\n            self.assertEqual(linked_build.exception.code, "OUTPUT_PATH_INVALID")\n            self.assertFalse((physical_build_parent / "nested" / "product").exists())\n        finally:\n            remove_directory_link(linked_build_parent)\n\n        dotdot_parent = self.parent / "build-dotdot-safe"\n        dotdot_parent.mkdir()\n        dotdot_output = dotdot_parent / ".." / "build-dotdot-product"\n        self.assertIn("..", dotdot_output.parts)\n        with self.assertRaises(tool.BuildError) as dotdot_build:\n            tool.build_cartridge(PROFILE, dotdot_output)\n        self.assertEqual(dotdot_build.exception.code, "OUTPUT_PATH_INVALID")\n        self.assertFalse((self.parent / "build-dotdot-product").exists())\n'''
    text = replace_once(
        text,
        '''        with self.assertRaises(tool.BuildError) as caught:\n            tool.build_cartridge(PROFILE, repo / "product")\n        self.assertEqual(caught.exception.code, "REPOSITORY_LOCAL_OUTPUT_REFUSED")\n\n    def test_23_foreign_working_directory_bootstrap(self) -> None:\n''',
        '''        with self.assertRaises(tool.BuildError) as caught:\n            tool.build_cartridge(PROFILE, repo / "product")\n        self.assertEqual(caught.exception.code, "REPOSITORY_LOCAL_OUTPUT_REFUSED")\n''' + test22_insert + '''\n    def test_23_foreign_working_directory_bootstrap(self) -> None:\n''',
        "test linked build output witnesses",
    )
    TESTS.write_text(text, encoding="utf-8", newline="\n")


def patch_doc() -> None:
    text = DOC.read_text(encoding="utf-8")
    insertion = '''## Coordinate and member custody

All cartridge verification, projection, verdict-output, and build-output coordinates require standard-library Python 3.12 or newer. Each entrypoint rejects a parent-directory segment before normalization and inspects every lexical absolute component before resolution. A symlink or Windows junction in the final component or any existing ancestor terminates structured refusal. Build, verdict, and projection outputs therefore cannot be redirected through a linked ancestor.

The verifier walks the cartridge tree without following links. A symlink or junction at the root, in any expected directory, or at any member path is refused before classification or reading. Every authoritative member, including `MANIFEST.json`, is limited to 1 MiB and read through a bounded `maximum + 1` operation after a size precondition. The embedded verifier retains its stricter exact-size, exact-digest, measured-byte, and stored-member binding.

'''
    text = replace_once(text, "## Build and verification\n", insertion + "## Build and verification\n", "documentation custody section")
    text = text.replace(
        "A copied bundle remains verifiable from a foreign working directory with standard-library Python.",
        "A copied bundle remains verifiable from a foreign working directory with standard-library Python 3.12 or newer.",
    )
    DOC.write_text(text, encoding="utf-8", newline="\n")


patch_verifier()
verifier_data = VERIFIER.read_bytes()
verifier_sha = hashlib.sha256(verifier_data).hexdigest()
patch_bootstrap(verifier_sha, len(verifier_data))
patch_tool(verifier_sha)
patch_tests()
patch_doc()

print(f"embedded verifier sha256: {verifier_sha}")
print(f"embedded verifier bytes: {len(verifier_data)}")
