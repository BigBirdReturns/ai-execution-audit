from __future__ import annotations

from pathlib import Path

ROOT = Path("mating_surface/anchor_node")
TOOL = ROOT / "stc_mary_flight_01_cartridge.py"
TESTS = ROOT / "conformance/test_stc_mary_flight_01_cartridge.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


tool = TOOL.read_text(encoding="utf-8")
tool = replace_once(
    tool,
    '''def validate_cartridge_coordinate(path: Path) -> Path:
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
''',
    '''def validate_cartridge_coordinate(path: Path) -> Path:
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
''',
    "absolute cartridge coordinate",
)
tool = replace_once(
    tool,
    '''def run_bootstrap(root: Path, out: Path | None = None) -> dict[str, Any]:
    supplied_root = validate_cartridge_coordinate(root)
    bootstrap = source_file(BOOTSTRAP_FILENAME)
    command = [sys.executable, str(bootstrap), str(supplied_root)]
    if out is not None:
        command.extend(["--out", str(out)])
    completed = subprocess.run(command, cwd=str(supplied_root.parent), check=False, capture_output=True)
    if out is not None and completed.returncode == 0:
        try:
            return json.loads(out.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            fail("BOOTSTRAP_VERDICT_READ_FAILED", str(exc))
''',
    '''def run_bootstrap(root: Path, out: Path | None = None) -> dict[str, Any]:
    absolute_root = validate_cartridge_coordinate(root)
    absolute_out = None if out is None else Path(os.path.abspath(os.fspath(out.expanduser())))
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
''',
    "absolute bootstrap arguments",
)
TOOL.write_text(tool, encoding="utf-8", newline="\n")

tests = TESTS.read_text(encoding="utf-8")
tests = replace_once(
    tests,
    '''    def test_23_foreign_working_directory_bootstrap(self) -> None:
        foreign = self.parent / "foreign"
        foreign.mkdir()
        code, verdict = run_bootstrap(self.root, cwd=foreign)
        self.assertEqual(code, 0)
        self.assertTrue(verdict["bootstrapAuthenticated"])
''',
    '''    def test_23_foreign_working_directory_bootstrap(self) -> None:
        foreign = self.parent / "foreign"
        foreign.mkdir()
        code, verdict = run_bootstrap(self.root, cwd=foreign)
        self.assertEqual(code, 0)
        self.assertTrue(verdict["bootstrapAuthenticated"])

        relative_parent = self.parent / "relative-base"
        relative_parent.mkdir()
        relative_root = relative_parent / "cartridge"
        shutil.copytree(self.root, relative_root)
        relative_root_argument = Path("relative-base") / "cartridge"
        relative_output_argument = Path("relative-verdict.json")
        relative_output = self.parent / relative_output_argument
        misplaced_output = relative_parent / relative_output_argument

        relative_verify = subprocess.run(
            [
                sys.executable,
                str(MAIN_TOOL),
                "verify",
                str(relative_root_argument),
                "--out",
                str(relative_output_argument),
            ],
            cwd=str(self.parent),
            check=False,
            capture_output=True,
        )
        self.assertEqual(relative_verify.returncode, 0, relative_verify.stdout.decode("utf-8", errors="replace"))
        self.assertTrue(relative_output.is_file())
        relative_verdict = load_json(relative_output)
        self.assertEqual(relative_verdict["status"], "PASS")
        self.assertTrue(relative_verdict["bootstrapAuthenticated"])
        self.assertFalse(misplaced_output.exists())

        relative_projection = subprocess.run(
            [sys.executable, str(MAIN_TOOL), "public-projection", str(relative_root_argument)],
            cwd=str(self.parent),
            check=False,
            capture_output=True,
        )
        self.assertEqual(relative_projection.returncode, 0, relative_projection.stdout.decode("utf-8", errors="replace"))
        relative_projection_value = json.loads(relative_projection.stdout.decode("utf-8"))
        self.assertEqual(relative_projection_value["authority"], "none")
        self.assertEqual(relative_projection_value["publicEvidenceBodies"], 0)
''',
    "relative coordinate witness",
)
TESTS.write_text(tests, encoding="utf-8", newline="\n")
