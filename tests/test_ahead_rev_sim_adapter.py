import hashlib
import os
from pathlib import Path
import shutil
import zipfile

import pytest

from tools.ahead_rev_sim import capture, replay
from tools.pack_replay_bundle import safe_extract_bundle
from tools.verify import main as verify_main

EXPECTED_STDOUT_SHA = "c1e27a06feaab45caa27f9177ecd47e2c582c9ed7c5f0677f2b87f99e3b7b730"


def test_real_ahead_rev_sim_capture_replay_and_tamper(temp_outdir):
    configured = os.environ.get("AHEAD_REV_SIM_REPO")
    if not configured:
        pytest.skip("AHEAD_REV_SIM_REPO is required for the real integration path")
    source_repo = Path(configured)
    if not source_repo.is_dir():
        pytest.fail(f"AHEAD_REV_SIM_REPO does not exist: {source_repo}")

    root = Path(temp_outdir)
    original = root / "original"
    extracted = root / "extracted"
    replayed = root / "replayed"
    bundle = capture(source_repo, original)
    safe_extract_bundle(bundle, extracted)
    assert verify_main(str(extracted), require_manifest=True)["status"] == "ok"

    decision = replay(extracted, replayed)
    assert (original / "artifacts" / "decision_record.json").read_bytes() == (
        replayed / "artifacts" / "decision_record.json"
    ).read_bytes()
    stdout = (replayed / "artifacts" / "loop.stdout.bin").read_bytes()
    assert len(stdout) == 295
    assert hashlib.sha256(stdout).hexdigest() == EXPECTED_STDOUT_SHA
    assert (replayed / "artifacts" / "loop.stderr.bin").read_bytes() == b""
    assert decision["exit_code"] == 0

    extra = root / "extra"
    shutil.copytree(extracted, extra)
    (extra / "runtime" / "ahead_rev_sim" / "unchecked.py").write_text("x=1\n", encoding="utf-8")
    assert verify_main(str(extra), require_manifest=True)["status"] == "rejected"

    tampered = root / "tampered"
    shutil.copytree(extracted, tampered)
    with (tampered / "runtime" / "ahead_rev_sim" / "machine.py").open("ab") as handle:
        handle.write(b"\n# tamper\n")
    assert verify_main(str(tampered), require_manifest=True)["status"] == "rejected"

    bad_zip = root / "bad.zip"
    with zipfile.ZipFile(bad_zip, "w") as archive:
        archive.writestr("../escape.txt", b"bad")
    with pytest.raises(ValueError):
        safe_extract_bundle(bad_zip, root / "bad-extract")