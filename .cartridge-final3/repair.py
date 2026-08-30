from pathlib import Path

TOOL = Path("mating_surface/anchor_node/stc_mary_flight_01_cartridge.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


text = TOOL.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''from verify_stc_mary_flight_01_cartridge import (
    AUTHORITY,
''',
    '''from verify_stc_mary_flight_01_cartridge import (
    AUTHORITY,
    CartridgeError,
''',
    "CartridgeError import",
)
text = replace_once(
    text,
    '''def fail(code: str, message: str) -> None:
    raise BuildError(code, message)


''',
    '''def fail(code: str, message: str) -> None:
    raise BuildError(code, message)


def resolve_tool_cartridge_coordinate(path: Path) -> Path:
    try:
        return resolve_cartridge_coordinate(path)
    except CartridgeError as exc:
        fail(exc.code, str(exc))


''',
    "tool coordinate error translation",
)
text = text.replace("root = resolve_cartridge_coordinate(root)", "root = resolve_tool_cartridge_coordinate(root)")
text = text.replace("root = resolve_cartridge_coordinate(args.cartridge)", "root = resolve_tool_cartridge_coordinate(args.cartridge)")
if text.count("resolve_tool_cartridge_coordinate(") != 3:
    raise SystemExit("tool coordinate helper use denominator differs")
TOOL.write_text(text, encoding="utf-8", newline="\n")
