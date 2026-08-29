from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "mating_surface/anchor_node/axm_head_physical_long_haul_join.py"
VERIFIER = ROOT / "mating_surface/anchor_node/verify_axm_head_physical_long_haul_join.py"
PROFILE = ROOT / "mating_surface/anchor_node/axm-head-physical-long-haul-join-profile-01.json"
TESTS = ROOT / "mating_surface/anchor_node/conformance/test_axm_head_physical_long_haul_join.py"
CONTRACT = ROOT / "mating_surface/anchor_node/AXM-HEAD-PHYSICAL-LONG-HAUL-JOIN-01.md"
WORKFLOW = ROOT / ".github/workflows/axm-head-physical-long-haul-join-01.yml"
PAYLOAD = ROOT / ".join-v2-auth-receipt-repair/axm-head-physical-long-haul-join-01.yml.payload"
COUNT_FILE = ROOT / ".join-v2-auth-receipt-repair/focused-test-count"

OLD_PREDICATE = '        predicates["authorizationDistinctAndPrior"] = auth["present"] is True and auth["evidenceTier"] == "private_local_attested" and auth["terminal"] == "AUTHORIZED" and auth["authorizationSequence"] == 0 and auth["firstPhysicalReceiptSequence"] == 1 and auth["namedHumanAuthorityClass"] == "GRACE" and bool(receipts) and receipts[0]["previousReceiptId"] == auth["receiptId"]\n'
NEW_PREDICATE = '        predicates["authorizationDistinctAndPrior"] = auth["present"] is True and auth["evidenceTier"] == "private_local_attested" and auth["terminal"] == "AUTHORIZED" and auth["authorizationSequence"] == 0 and auth["firstPhysicalReceiptSequence"] == 1 and auth["namedHumanAuthorityClass"] == "GRACE" and bool(receipts) and auth["receiptId"] not in {row["receiptId"] for row in receipts} and receipts[0]["previousReceiptId"] == auth["receiptId"]\n'

NEW_TEST = '''    def test_authorization_receipt_identity_reuse_holds_after_complete_resigning(self):
        value = private_input()
        authorization_id = value["privateDisposition"]["authorization"]["receiptId"]
        receipts = value["privateDisposition"]["stageReceipts"]
        receipts[0]["receiptId"] = authorization_id
        receipts[1]["previousReceiptId"] = authorization_id
        value = resign_private_input(value)
        result = tool.build_objects(self.profile, value, TEST_PROOF_ROOT)
        self.assertEqual(result["join"]["terminal"], "HOLD")
        self.assertIn("NAMED_HUMAN_AUTHORIZATION_INVALID", result["join"]["reasonCodes"])

'''

CONTRACT_SECTION = '''

## Authorization receipt identity closure

Named-human authorization and physical execution are separate transactions. The authorization receipt identity must therefore differ from every one of the sixteen physical packet-stage receipt identities. The first stage must point back to the authorization receipt, while the second stage must point to the first stage receipt. Reusing the authorization identity as the first physical receipt is refused even when the complete graph is re-authenticated with the valid private proof root.
'''


def canonical_json_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text.replace("\r\n", "\n").replace("\r", "\n"), encoding="utf-8", newline="\n")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one predecessor, observed {count}")
    return text.replace(old, new, 1)


for path in (BUILDER, VERIFIER):
    text = path.read_text(encoding="utf-8")
    text = replace_once(text, OLD_PREDICATE, NEW_PREDICATE, f"authorization predicate {path.name}")
    write_text(path, text)

tests = TESTS.read_text(encoding="utf-8")
marker = '    def test_public_evidence_body_holds(self):\n'
if "test_authorization_receipt_identity_reuse_holds_after_complete_resigning" in tests:
    raise SystemExit("authorization identity witness already present")
tests = replace_once(tests, marker, NEW_TEST + marker, "authorization witness insertion")
write_text(TESTS, tests)

verifier_digest = hashlib.sha256(VERIFIER.read_bytes()).hexdigest()
profile = json.loads(PROFILE.read_text(encoding="utf-8"))
profile["standaloneVerifierSha256"] = verifier_digest
write_text(PROFILE, json.dumps(profile, sort_keys=True, indent=2, ensure_ascii=False) + "\n")
profile_digest = hashlib.sha256(canonical_json_bytes(profile)).hexdigest()
fixture_digest = profile["fixtureCatalogCanonicalSha256"]

builder = BUILDER.read_text(encoding="utf-8")
builder, count = re.subn(
    r'^PROFILE_CANONICAL_SHA256 = "[0-9a-f]{64}"$',
    f'PROFILE_CANONICAL_SHA256 = "{profile_digest}"',
    builder,
    count=1,
    flags=re.MULTILINE,
)
if count != 1:
    raise SystemExit(f"profile digest constant predecessor count {count}")
builder, count = re.subn(
    r'^STANDALONE_VERIFIER_SHA256 = "[0-9a-f]{64}"$',
    f'STANDALONE_VERIFIER_SHA256 = "{verifier_digest}"',
    builder,
    count=1,
    flags=re.MULTILINE,
)
if count != 1:
    raise SystemExit(f"verifier digest constant predecessor count {count}")
write_text(BUILDER, builder)

contract = CONTRACT.read_text(encoding="utf-8")
if "## Authorization receipt identity closure" in contract:
    raise SystemExit("authorization identity contract section already present")
contract += CONTRACT_SECTION
contract, count = re.subn(
    r'profile canonical SHA-256: [0-9a-f]{64}',
    f'profile canonical SHA-256: {profile_digest}',
    contract,
    count=1,
)
if count != 1:
    raise SystemExit(f"contract profile digest predecessor count {count}")
contract, count = re.subn(
    r'standalone verifier SHA-256: [0-9a-f]{64}',
    f'standalone verifier SHA-256: {verifier_digest}',
    contract,
    count=1,
)
if count != 1:
    raise SystemExit(f"contract verifier digest predecessor count {count}")
write_text(CONTRACT, contract)

result = subprocess.run(
    [
        sys.executable, "-m", "unittest", "discover",
        "-s", "mating_surface/anchor_node/conformance",
        "-p", "test_axm_head_physical_long_haul_join.py",
        "-v",
    ],
    cwd=ROOT,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    check=False,
)
if result.returncode != 0:
    sys.stdout.buffer.write(result.stdout)
    sys.stderr.buffer.write(result.stderr)
    raise SystemExit(result.returncode)
if result.stdout:
    raise SystemExit("focused tests emitted stdout")
match = re.search(rb"Ran (\d+) tests", result.stderr)
if match is None:
    raise SystemExit("focused test denominator missing")
focused_count = int(match.group(1))
if focused_count != 61:
    raise SystemExit(f"expected 61 focused tests, observed {focused_count}")

workflow = WORKFLOW.read_text(encoding="utf-8")
workflow = replace_once(
    workflow,
    'grep -F "Ran 60 tests"',
    f'grep -F "Ran {focused_count} tests"',
    "permanent workflow focused denominator",
)
PAYLOAD.parent.mkdir(parents=True, exist_ok=True)
write_text(PAYLOAD, workflow)
COUNT_FILE.write_text(str(focused_count) + "\n", encoding="utf-8")

print(json.dumps({
    "status": "PASS",
    "focusedTests": focused_count,
    "profileCanonicalSha256": profile_digest,
    "fixtureCatalogCanonicalSha256": fixture_digest,
    "standaloneVerifierSha256": verifier_digest,
    "authorizationReceiptDistinctFromEveryStage": True,
    "physicalExecutionStarted": False,
    "workersLaunched": 0,
    "listenersCreated": 0,
    "authority": "none",
}, sort_keys=True))
