from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path("mating_surface/anchor_node")
VERIFIER = ROOT / "verify_stc_mary_flight_01_cartridge.py"
BOOTSTRAP = ROOT / "verify_stc_mary_flight_01_cartridge_bootstrap.py"
TOOL = ROOT / "stc_mary_flight_01_cartridge.py"
TESTS = ROOT / "conformance/test_stc_mary_flight_01_cartridge.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


helper = '''def coordinate_has_link_component(path: Path) -> bool:
    lexical = Path(os.path.abspath(os.fspath(path.expanduser())))
    for candidate in reversed((lexical, *lexical.parents)):
        try:
            if candidate.is_symlink():
                return True
            is_junction = getattr(candidate, "is_junction", None)
            if callable(is_junction) and is_junction():
                return True
            metadata = os.lstat(candidate)
        except FileNotFoundError:
            continue
        attributes = getattr(metadata, "st_file_attributes", 0)
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        if reparse and attributes & reparse:
            return True
    return False


def resolve_cartridge_coordinate(path: Path) -> Path:
    if coordinate_has_link_component(path):
        fail("CARTRIDGE_ROOT_INVALID", "cartridge coordinate may not contain a symlink, junction, or reparse-point component")
    root = path.expanduser().resolve(strict=True)
    if not root.is_dir():
        fail("CARTRIDGE_ROOT_INVALID", "cartridge root must be a regular non-linked directory")
    return root


'''

verifier = VERIFIER.read_text(encoding="utf-8")
verifier = replace_once(verifier, "import re\nimport sys\n", "import re\nimport stat\nimport sys\n", "verifier stat import")
verifier = replace_once(
    verifier,
    '''def fail(code: str, message: str) -> None:
    raise CartridgeError(code, message)


''',
    '''def fail(code: str, message: str) -> None:
    raise CartridgeError(code, message)


''' + helper,
    "verifier coordinate helper",
)
verifier = replace_once(
    verifier,
    '''def verify_cartridge(root: Path) -> dict[str, Any]:
    supplied_root = root.expanduser()
    if supplied_root.is_symlink():
        fail("CARTRIDGE_ROOT_INVALID", "cartridge root must be a regular non-symlink directory")
    root = supplied_root.resolve(strict=True)
    validate_tree(root)
''',
    '''def verify_cartridge(root: Path) -> dict[str, Any]:
    root = resolve_cartridge_coordinate(root)
    validate_tree(root)
''',
    "verifier library coordinate",
)
verifier = replace_once(
    verifier,
    '''        "publicEvidenceBodies": 0,
        "authority": AUTHORITY,
    }
''',
    '''        "publicEvidenceBodies": 0,
        "publicStatus": stored_status,
        "authority": AUTHORITY,
    }
''',
    "authenticated public status",
)
verifier = replace_once(
    verifier,
    '''        supplied_root = args.cartridge.expanduser()
        if supplied_root.is_symlink():
            fail("CARTRIDGE_ROOT_INVALID", "cartridge root must be a regular non-symlink directory")
        root = supplied_root.resolve(strict=True)
        validate_output_path(root, args.out)
        verdict = verify_cartridge(supplied_root)
''',
    '''        root = resolve_cartridge_coordinate(args.cartridge)
        validate_output_path(root, args.out)
        verdict = verify_cartridge(root)
''',
    "verifier CLI coordinate",
)
VERIFIER.write_text(verifier, encoding="utf-8", newline="\n")
verifier_sha = hashlib.sha256(VERIFIER.read_bytes()).hexdigest()

bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
bootstrap = replace_once(bootstrap, "import json\nimport subprocess\n", "import json\nimport os\nimport stat\nimport subprocess\n", "bootstrap imports")
bootstrap_helper = helper.replace("CartridgeError", "BootstrapError")
bootstrap = replace_once(
    bootstrap,
    '''def fail(code: str, message: str) -> None:
    raise BootstrapError(code, message)


''',
    '''def fail(code: str, message: str) -> None:
    raise BootstrapError(code, message)


''' + bootstrap_helper,
    "bootstrap coordinate helper",
)
old_digest_line = next(line for line in bootstrap.splitlines() if line.startswith("EXPECTED_EMBEDDED_VERIFIER_SHA256 = "))
bootstrap = bootstrap.replace(old_digest_line, f'EXPECTED_EMBEDDED_VERIFIER_SHA256 = "{verifier_sha}"', 1)
bootstrap = replace_once(
    bootstrap,
    '''        supplied_root = args.cartridge.expanduser()
        if supplied_root.is_symlink():
            fail("CARTRIDGE_ROOT_INVALID", "cartridge root must be a regular non-symlink directory")
        root = supplied_root.resolve(strict=True)
        if not root.is_dir():
            fail("CARTRIDGE_ROOT_INVALID", "cartridge root must be a regular non-symlink directory")
''',
    '''        root = resolve_cartridge_coordinate(args.cartridge)
''',
    "bootstrap root coordinate",
)
bootstrap = replace_once(
    bootstrap,
    '''        if verdict.get("bootstrapAuthenticated") is not False:
            fail("EMBEDDED_VERDICT_BOOTSTRAP_STATE_INVALID", "embedded verifier may not self-assert bootstrap authentication")
        verdict["bootstrapAuthenticated"] = True
''',
    '''        if verdict.get("bootstrapAuthenticated") is not False:
            fail("EMBEDDED_VERDICT_BOOTSTRAP_STATE_INVALID", "embedded verifier may not self-assert bootstrap authentication")
        public_status = verdict.get("publicStatus")
        if not isinstance(public_status, dict) or public_status.get("authority") != AUTHORITY:
            fail("EMBEDDED_PUBLIC_STATUS_INVALID", "embedded verifier did not return the authenticated public status")
        verdict["bootstrapAuthenticated"] = True
''',
    "bootstrap authenticated status",
)
BOOTSTRAP.write_text(bootstrap, encoding="utf-8", newline="\n")

tool = TOOL.read_text(encoding="utf-8")
old_tool_digest = next(line for line in tool.splitlines() if line.startswith("EXPECTED_VERIFIER_SHA256 = "))
tool = tool.replace(old_tool_digest, f'EXPECTED_VERIFIER_SHA256 = "{verifier_sha}"', 1)
tool = replace_once(
    tool,
    '''    sha256_bytes,
    validate_profile,
    verify_cartridge,
)''',
    '''    sha256_bytes,
    validate_profile,
    verify_cartridge,
    resolve_cartridge_coordinate,
)''',
    "tool helper import",
)
tool = replace_once(
    tool,
    '''def public_projection(root: Path) -> dict[str, Any]:
    supplied_root = root.expanduser()
    if supplied_root.is_symlink():
        fail("CARTRIDGE_ROOT_INVALID", "cartridge root must be a regular non-symlink directory")
    root = supplied_root.resolve(strict=True)
    verdict = run_bootstrap(supplied_root)
    if verdict.get("status") != "PASS" or verdict.get("bootstrapAuthenticated") is not True:
        fail("AUTHENTICATED_VERIFICATION_REQUIRED", "cartridge must pass the external bootstrap")
    status_path = root / "PUBLIC" / "status.json"
    return parse_json_bytes(status_path.read_bytes(), str(status_path))
''',
    '''def public_projection(root: Path) -> dict[str, Any]:
    root = resolve_cartridge_coordinate(root)
    verdict = run_bootstrap(root)
    if verdict.get("status") != "PASS" or verdict.get("bootstrapAuthenticated") is not True:
        fail("AUTHENTICATED_VERIFICATION_REQUIRED", "cartridge must pass the external bootstrap")
    status = verdict.get("publicStatus")
    if not isinstance(status, dict) or status.get("authority") != AUTHORITY:
        fail("AUTHENTICATED_PUBLIC_STATUS_REQUIRED", "bootstrap verdict lacks the authenticated public status")
    return status
''',
    "tool projection authenticated bytes",
)
tool = replace_once(
    tool,
    '''        elif args.command == "public-projection":
            supplied_root = args.cartridge.expanduser()
            if supplied_root.is_symlink():
                fail("CARTRIDGE_ROOT_INVALID", "cartridge root must be a regular non-symlink directory")
            root = supplied_root.resolve(strict=True)
            validate_projection_output(root, args.out)
            emit(public_projection(supplied_root), args.out)
''',
    '''        elif args.command == "public-projection":
            root = resolve_cartridge_coordinate(args.cartridge)
            validate_projection_output(root, args.out)
            emit(public_projection(root), args.out)
''',
    "tool projection dispatcher",
)
TOOL.write_text(tool, encoding="utf-8", newline="\n")

tests = TESTS.read_text(encoding="utf-8")
tests = replace_once(tests, "import unittest\nfrom pathlib", "import unittest\nfrom unittest.mock import patch\nfrom pathlib", "test patch import")
nested_anchor = '''        with self.assertRaises(verifier.CartridgeError) as library_verification:
            verifier.verify_cartridge(symlink_root)
        self.assertEqual(library_verification.exception.code, "CARTRIDGE_ROOT_INVALID")
'''
nested_body = nested_anchor + '''
        nested_target_parent = self.parent / "nested-target"
        nested_target_parent.mkdir()
        nested_cartridge = nested_target_parent / "cartridge"
        shutil.copytree(self.root, nested_cartridge)
        nested_link_parent = self.parent / "nested-link-parent"
        nested_link_parent.symlink_to(nested_target_parent, target_is_directory=True)
        nested_coordinate = nested_link_parent / "cartridge"

        nested_out = self.parent / "nested-verdict.json"
        code, nested_verdict = run_bootstrap(nested_coordinate, nested_out)
        self.assertNotEqual(code, 0)
        self.assertEqual(nested_verdict["code"], "CARTRIDGE_ROOT_INVALID")
        self.assertFalse(nested_out.exists())
        nested_direct = subprocess.run(
            [sys.executable, str(EMBEDDED_VERIFIER_SOURCE), str(nested_coordinate)],
            check=False,
            capture_output=True,
        )
        self.assertNotEqual(nested_direct.returncode, 0)
        self.assertEqual(json.loads(nested_direct.stdout.decode("utf-8"))["code"], "CARTRIDGE_ROOT_INVALID")
        nested_projection = self.parent / "nested-projection.json"
        nested_projected = subprocess.run(
            [sys.executable, str(MAIN_TOOL), "public-projection", str(nested_coordinate), "--out", str(nested_projection)],
            check=False,
            capture_output=True,
        )
        self.assertNotEqual(nested_projected.returncode, 0)
        self.assertEqual(json.loads(nested_projected.stdout.decode("utf-8"))["code"], "CARTRIDGE_ROOT_INVALID")
        self.assertFalse(nested_projection.exists())
        with self.assertRaises(tool.BuildError) as nested_library_projection:
            tool.public_projection(nested_coordinate)
        self.assertEqual(nested_library_projection.exception.code, "CARTRIDGE_ROOT_INVALID")
        with self.assertRaises(verifier.CartridgeError) as nested_library_verification:
            verifier.verify_cartridge(nested_coordinate)
        self.assertEqual(nested_library_verification.exception.code, "CARTRIDGE_ROOT_INVALID")
'''
tests = replace_once(tests, nested_anchor, nested_body, "nested symlink witness")
projection_anchor = '''    def test_24_public_projection_is_body_free(self) -> None:
        projection = tool.public_projection(self.root)
        encoded = json.dumps(projection, sort_keys=True)
'''
projection_body = '''    def test_24_public_projection_is_body_free(self) -> None:
        authenticated = tool.run_bootstrap(self.root)
        self.assertEqual(authenticated["status"], "PASS")
        self.assertTrue(authenticated["bootstrapAuthenticated"])
        expected_projection = authenticated["publicStatus"]
        promoted = load_json(self.root / "PUBLIC/status.json")
        promoted["workstationInitialized"] = True
        promoted["authority"] = "mission"
        write_pretty(self.root / "PUBLIC/status.json", promoted)
        with patch.object(tool, "run_bootstrap", return_value=authenticated):
            projection = tool.public_projection(self.root)
        self.assertEqual(projection, expected_projection)
        self.assertFalse(projection["workstationInitialized"])
        self.assertEqual(projection["authority"], "none")
        encoded = json.dumps(projection, sort_keys=True)
'''
tests = replace_once(tests, projection_anchor, projection_body, "authenticated projection witness")
TESTS.write_text(tests, encoding="utf-8", newline="\n")

print(verifier_sha)
