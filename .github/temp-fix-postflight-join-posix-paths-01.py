from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path("mating_surface/anchor_node")
VERIFIER = ROOT / "verify_axm_head_physical_long_haul_join.py"
BOOTSTRAP = ROOT / "axm_head_physical_long_haul_join.py"
TESTS = ROOT / "conformance/test_axm_head_physical_long_haul_join.py"
DOC = ROOT / "AXM-HEAD-PHYSICAL-LONG-HAUL-JOIN-01.md"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


path_constants = '''WINDOWS_PATH_RE = re.compile(r"(?i)(?:^|[\\s\\\"'])(?:[a-z]:[\\\\/]|\\\\\\\\[^\\\\/]+[\\\\/])")
POSIX_ABSOLUTE_PATH_RE = re.compile(r"(?:^|[\\s\\\"'(=])(?:/|~/)[^\\s\\\"'<>|]+")
POSIX_RELATIVE_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9._~+@-])(?:"
    r"(?:\\.{1,2}|~)/(?:[A-Za-z0-9._~+@-]+)(?:/[A-Za-z0-9._~+@-]+)*"
    r"|(?:[A-Za-z0-9._~+@-]+/){3,}[A-Za-z0-9._~+@-]+"
    r"|(?:[A-Za-z0-9._~+@-]+/){2,}[A-Za-z0-9_~+@-][A-Za-z0-9._~+@-]*\\.[A-Za-z0-9][A-Za-z0-9._-]*"
    r")(?![A-Za-z0-9._~+@-])",
    re.I,
)
'''

old_windows = 'WINDOWS_PATH_RE = re.compile(r"(?i)(?:^|[\\s\\\"\'])(?:[a-z]:[\\\\/]|\\\\\\\\[^\\\\/]+[\\\\/])")\n'

verifier = VERIFIER.read_text(encoding="utf-8")
verifier = replace_once(verifier, old_windows, path_constants, "verifier POSIX path constants")
verifier = replace_once(
    verifier,
    '''            if WINDOWS_PATH_RE.search(node):
                fail("PRIVATE_PATH_DETECTED", f"{path} contains a Windows or UNC path")
            if PRIVATE_HOST_RE.search(node):
''',
    '''            if WINDOWS_PATH_RE.search(node):
                fail("PRIVATE_PATH_DETECTED", f"{path} contains a Windows or UNC path")
            if POSIX_ABSOLUTE_PATH_RE.search(node) or POSIX_RELATIVE_PATH_RE.search(node):
                fail("PRIVATE_PATH_DETECTED", f"{path} contains a POSIX absolute or path-shaped relative value")
            if PRIVATE_HOST_RE.search(node):
''',
    "verifier POSIX path scan",
)
verifier = replace_once(
    verifier,
    '''def validate_input_value(value: dict[str, Any]) -> dict[str, Any]:
    item = dict(
''',
    '''def validate_input_value(value: dict[str, Any]) -> dict[str, Any]:
    scan_forbidden_private_material(value)
    item = dict(
''',
    "private membrane before semantic validation",
)
verifier = replace_once(
    verifier,
    '''    if item["privateEvidenceProvenance"] is not None:
        validate_private_evidence_provenance(item["privateEvidenceProvenance"])
    scan_forbidden_private_material(item)
    return item
''',
    '''    if item["privateEvidenceProvenance"] is not None:
        validate_private_evidence_provenance(item["privateEvidenceProvenance"])
    return item
''',
    "remove late duplicate private scan",
)
VERIFIER.write_text(verifier, encoding="utf-8", newline="\n")
verifier_sha = hashlib.sha256(VERIFIER.read_bytes()).hexdigest()

bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
bootstrap = replace_once(bootstrap, old_windows, path_constants, "bootstrap POSIX path constants")
bootstrap = replace_once(
    bootstrap,
    '''            if WINDOWS_PATH_RE.search(node):
                fail("PRIVATE_PATH_DETECTED", f"{path} contains a Windows or UNC path")
            if PRIVATE_HOST_RE.search(node):
''',
    '''            if WINDOWS_PATH_RE.search(node):
                fail("PRIVATE_PATH_DETECTED", f"{path} contains a Windows or UNC path")
            if POSIX_ABSOLUTE_PATH_RE.search(node) or POSIX_RELATIVE_PATH_RE.search(node):
                fail("PRIVATE_PATH_DETECTED", f"{path} contains a POSIX absolute or path-shaped relative value")
            if PRIVATE_HOST_RE.search(node):
''',
    "bootstrap POSIX path scan",
)
old_digest = next(line for line in bootstrap.splitlines() if line.startswith("STANDALONE_VERIFIER_SHA256 = "))
bootstrap = bootstrap.replace(old_digest, f'STANDALONE_VERIFIER_SHA256 = "{verifier_sha}"', 1)
BOOTSTRAP.write_text(bootstrap, encoding="utf-8", newline="\n")

tests = TESTS.read_text(encoding="utf-8")
tests = replace_once(
    tests,
    '''    def test_private_path_in_allowlisted_string_is_refused(self) -> None:
        value = self.complete()
        value["privateFlightDispositionBinding"]["cartridge"]["nextSafeAction"] = "Read C:\\\\private\\\\evidence.json"
        self.refresh_top(value, "privateFlightDispositionBinding", "dispositionBindingId", "axmheadprivateflightdispositionbinding2")
        with self.assertRaises(mod.JoinError) as context:
            mod.validate_input_value(value)
        self.assertEqual(context.exception.code, "PRIVATE_PATH_DETECTED")
''',
    '''    def test_private_path_in_allowlisted_string_is_refused(self) -> None:
        candidates = (
            "Read C:\\\\private\\\\evidence.json",
            "Read /home/alice/private/evidence.json",
            "Read /Users/alice/private/evidence.json",
            "home/alice/private/evidence.json",
            "Read home/alice/private/evidence.json",
            "./private/evidence.json",
            "../private/evidence.json",
            "~/private/evidence.json",
        )
        for candidate in candidates:
            with self.subTest(candidate=candidate):
                value = self.complete()
                value["privateFlightDispositionBinding"]["cartridge"]["nextSafeAction"] = candidate
                self.refresh_top(
                    value,
                    "privateFlightDispositionBinding",
                    "dispositionBindingId",
                    "axmheadprivateflightdispositionbinding2",
                )
                with self.assertRaises(mod.JoinError) as context:
                    mod.validate_input_value(value)
                self.assertEqual(context.exception.code, "PRIVATE_PATH_DETECTED")
                with self.assertRaises(bootstrap.BootstrapError) as bootstrap_context:
                    bootstrap.scan_forbidden_private_material(value)
                self.assertEqual(bootstrap_context.exception.code, "PRIVATE_PATH_DETECTED")

        path_shaped_id = self.complete()
        path_shaped_id["privateFlightDispositionBinding"]["cartridge"]["cartridgeId"] = (
            "home/alice/private/evidence.json"
        )
        with self.assertRaises(mod.JoinError) as context:
            mod.validate_input_value(path_shaped_id)
        self.assertEqual(context.exception.code, "PRIVATE_PATH_DETECTED")
        with self.assertRaises(bootstrap.BootstrapError) as bootstrap_context:
            bootstrap.scan_forbidden_private_material(path_shaped_id)
        self.assertEqual(bootstrap_context.exception.code, "PRIVATE_PATH_DETECTED")
''',
    "POSIX path witnesses",
)
tests = replace_once(
    tests,
    '''    def test_unknown_field_is_refused(self) -> None:
        value = self.complete()
        value["routeAttestation"]["hostname"] = "redacted"
        with self.assertRaises(mod.JoinError) as context:
            mod.validate_input_value(value)
        self.assertEqual(context.exception.code, "OBJECT_KEYS_INVALID")
''',
    '''    def test_unknown_field_is_refused(self) -> None:
        generic = self.complete()
        generic["routeAttestation"]["unknownField"] = "redacted"
        with self.assertRaises(mod.JoinError) as context:
            mod.validate_input_value(generic)
        self.assertEqual(context.exception.code, "OBJECT_KEYS_INVALID")

        forbidden = self.complete()
        forbidden["routeAttestation"]["hostname"] = "redacted"
        with self.assertRaises(mod.JoinError) as context:
            mod.validate_input_value(forbidden)
        self.assertEqual(context.exception.code, "PRIVATE_MATERIAL_KEY_FORBIDDEN")
''',
    "separate schema and private-key witnesses",
)
TESTS.write_text(tests, encoding="utf-8", newline="\n")

doc = DOC.read_text(encoding="utf-8")
doc = replace_once(
    doc,
    '''The local input may carry body-free content references, counts, route classes, host classes, bounded performance units, timestamps, terminal states, and content identities. It may not carry a private path, evidence filename, hostname, seat identity, hardware serial, network endpoint, credential, environment value, operator record, stdout, stderr, telemetry body, evidence body, or sealed package body.
''',
    '''The local input may carry body-free content references, counts, route classes, host classes, bounded performance units, timestamps, terminal states, and content identities. It may not carry a private path, evidence filename, hostname, seat identity, hardware serial, network endpoint, credential, environment value, operator record, stdout, stderr, telemetry body, evidence body, or sealed package body. Both the standalone verifier and external bootstrap reject Windows drive and UNC paths, POSIX absolute paths including `/home/...` and `/Users/...`, dot-relative and home-relative paths, and path-shaped relative values such as `home/alice/private/evidence.json`, even when placed in an otherwise allowlisted identifier or free-form field. The private-material membrane runs before content-identity and semantic validation, so a path-shaped identifier or forbidden private key cannot be downgraded into a generic schema or digest refusal.
''',
    "POSIX path membrane documentation",
)
DOC.write_text(doc, encoding="utf-8", newline="\n")

print(f"standalone verifier sha256: {verifier_sha}")
