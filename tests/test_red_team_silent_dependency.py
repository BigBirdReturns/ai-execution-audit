import os
import shutil
import tempfile
import zipfile

import pytest

from reference_impl.axm_runtime import run as run_reference
from tools.pack_replay_bundle import main as pack_bundle
from tools.vendor_hints import assert_no_forbidden_hints


@pytest.mark.redteam
def test_red_team_silent_dependency_is_detected() -> None:
    tmp = tempfile.mkdtemp(prefix="audit_redteam_silent_")
    try:
        out_dir = os.path.join(tmp, "out")
        os.makedirs(out_dir, exist_ok=True)

        env = os.environ.copy()
        env["NO_NETWORK"] = "1"
        env["AI_AUDIT_SILENT_DEPENDENCY"] = "1"
        env["AI_AUDIT_SCHEDULER_FINGERPRINT"] = "slurm:partition=gpu:prio=high"
        env["AI_AUDIT_POLICY_HASH"] = "deadbeef" * 8

        # Run reference implementation with the silent dependency enabled
        old_env = os.environ.copy()
        os.environ.clear()
        os.environ.update(env)
        try:
            run_reference(
                ir_path=os.path.join("ir", "demo_ir.json"),
                user_input="hello",
                out_dir=out_dir,
                provenance_path=os.path.join("provenance", "provenance.log.jsonl"),
            )
        finally:
            os.environ.clear()
            os.environ.update(old_env)

        # Pack replay bundle and extract
        bundle_zip = pack_bundle(out_dir)
        bundle_dir = os.path.join(tmp, "bundle")
        os.makedirs(bundle_dir, exist_ok=True)
        with zipfile.ZipFile(bundle_zip, "r") as z:
            z.extractall(bundle_dir)

        # Vendor independence must fail loudly
        with pytest.raises(AssertionError):
            assert_no_forbidden_hints(bundle_dir)

    finally:
        shutil.rmtree(tmp, ignore_errors=True)
