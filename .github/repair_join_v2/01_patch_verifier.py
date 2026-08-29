from __future__ import annotations

from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parents[2]
VERIFIER = ROOT / "mating_surface" / "anchor_node" / "verify_axm_head_physical_long_haul_001_join_v2.py"
DIGEST_FILE = Path(__file__).resolve().parent / "verifier-digest.txt"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one target, found {count}")
    return text.replace(old, new, 1)


def regex_once(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f"{label}: expected one target, found {count}")
    return updated


text = VERIFIER.read_text(encoding="utf-8")
text = replace_once(text, "import os\n", "", "remove verifier os import")
text = replace_once(
    text,
    '    return (text + "\\n").encode("utf-8")\n\n\ndef sha256_bytes(data: bytes) -> str:\n',
    '    return (text + "\\n").encode("utf-8")\n\n\ndef type_strict_equal(actual: Any, expected: Any) -> bool:\n'
    '    return canonical_json_bytes(actual) == canonical_json_bytes(expected)\n\n\ndef sha256_bytes(data: bytes) -> str:\n',
    "add type-strict equality",
)
text = replace_once(
    text,
    '''    expected_state = prepared_state(profile)
    expected_decision = prepared_decision(profile, expected_state)
    expected_public = public_status(profile, expected_decision)
    if read_object(state_path) != expected_state:
        fail("PREPARATION_STATE_MISMATCH", "prepared state is not reconstructed from the admitted profile")
    if read_object(decision_path) != expected_decision:
        fail("DECISION_MISMATCH", "decision is not reconstructed from the prepared state")
    if read_object(public_path) != expected_public:
        fail("PUBLIC_STATUS_MISMATCH", "public status is not reconstructed from the decision")
''',
    '''    expected_state = prepared_state(profile)
    expected_decision = prepared_decision(profile, expected_state)
    expected_public = public_status(profile, expected_decision)
    actual_state = read_object(state_path)
    actual_decision = read_object(decision_path)
    actual_public = read_object(public_path)
    if not type_strict_equal(actual_state, expected_state):
        fail("PREPARATION_STATE_MISMATCH", "prepared state is not reconstructed from the admitted profile")
    if not type_strict_equal(actual_decision, expected_decision):
        fail("DECISION_MISMATCH", "decision is not reconstructed from the prepared state")
    if not type_strict_equal(actual_public, expected_public):
        fail("PUBLIC_STATUS_MISMATCH", "public status is not reconstructed from the decision")
''',
    "type-strict reconstructed members",
)
text = replace_once(
    text,
    '    if manifest["sourceCoordinates"] != profile["sourceCoordinates"] or manifest["physicalFlightIssue"] != profile["physicalFlightIssue"]:\n'
    '        fail("MANIFEST_SOURCE_BINDING_INVALID", "manifest source or issue binding differs")\n',
    '    if not type_strict_equal(manifest["sourceCoordinates"], profile["sourceCoordinates"]) or not type_strict_equal(\n'
    '        manifest["physicalFlightIssue"], profile["physicalFlightIssue"]\n'
    '    ):\n'
    '        fail("MANIFEST_SOURCE_BINDING_INVALID", "manifest source or issue binding differs")\n',
    "type-strict source binding",
)
text = replace_once(
    text,
    '    if manifest["fileCount"] != len(EXPECTED_RELATIVE_FILES):\n'
    '        fail("MANIFEST_FILE_COUNT_INVALID", "manifest fileCount differs")\n',
    '    if type(manifest["fileCount"]) is not int or manifest["fileCount"] != len(EXPECTED_RELATIVE_FILES):\n'
    '        fail("MANIFEST_FILE_COUNT_INVALID", "manifest fileCount differs")\n',
    "type-strict file count",
)
text = replace_once(
    text,
    '    if rows != expected_rows:\n'
    '        fail("MANIFEST_FILE_ROWS_INVALID", "manifest file rows differ from measured bytes")\n',
    '    if not type_strict_equal(rows, expected_rows):\n'
    '        fail("MANIFEST_FILE_ROWS_INVALID", "manifest file rows differ from measured bytes")\n',
    "type-strict file rows",
)
text = replace_once(
    text,
    '        if manifest[key] != expected:\n'
    '            fail("MANIFEST_NONCLAIM_INVALID", f"manifest {key} differs")\n',
    '        if not type_strict_equal(manifest[key], expected):\n'
    '            fail("MANIFEST_NONCLAIM_INVALID", f"manifest {key} differs")\n',
    "type-strict manifest semantics",
)
text = regex_once(
    text,
    r'\n    authenticated = \(\n        os\.environ\.get\("AXM_HEAD_JOIN_V2_BOOTSTRAP_AUTHENTICATED"\) == "1"\n'
    r'        and os\.environ\.get\("AXM_HEAD_JOIN_V2_VERIFIER_SHA256"\) == verifier_digest\n'
    r'    \)\n    return \{',
    '\n    return {',
    "remove environment authentication",
)
text = replace_once(
    text,
    '        "bootstrapAuthenticated": authenticated,\n',
    '        "bootstrapAuthenticated": False,\n',
    "direct verifier remains unauthenticated",
)

VERIFIER.write_text(text, encoding="utf-8", newline="\n")
digest = hashlib.sha256(VERIFIER.read_bytes()).hexdigest()
DIGEST_FILE.write_text(digest + "\n", encoding="utf-8", newline="\n")
print(digest)
