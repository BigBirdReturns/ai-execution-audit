import os
import shutil
import tempfile
import zipfile
from pathlib import Path

import pytest

from reference_impl.axm_runtime import run as run_reference
from tools.pack_replay_bundle import main as pack_bundle
from tools.vendor_hints import assert_no_forbidden_hints
from tools.red_team.fake_control_plane import FakeControlPlane


@pytest.mark.redteam
def test_red_team_harness_detects_vendor_control_plane_dependency(temp_outdir):
    """Prove the suite catches vendor dependencies.

    This test intentionally enables two external dependencies (license + scheduler)
    against localhost "fake control plane" endpoints.

    The run itself may succeed, but vendor independence must fail because the replay bundle
    contains control-plane URLs and dependency markers.
    """
    out = temp_outdir

    lic = FakeControlPlane()
    sch = FakeControlPlane()
    lic_host, lic_port = lic.start()
    sch_host, sch_port = sch.start()

    lic_url = f"http://{lic_host}:{lic_port}/license"
    sch_url = f"http://{sch_host}:{sch_port}/scheduler"

    env = os.environ.copy()
    env["AI_AUDIT_VENDOR_LICENSE_URL"] = lic_url
    env["AI_AUDIT_SCHEDULER_URL"] = sch_url

    try:
        # Run with dependencies enabled
        # (Do not use the block_network fixture here; we want the calls to happen.)
        # Use env injection by temporarily setting os.environ.
        os.environ.update({
            "AI_AUDIT_VENDOR_LICENSE_URL": lic_url,
            "AI_AUDIT_SCHEDULER_URL": sch_url,
            "AI_AUDIT_DEP_TIMEOUT_S": "0.5",
        })

        run_reference(
            ir_path=os.path.join("ir", "demo_ir.json"),
            user_input="red team harness",
            out_dir=out,
            provenance_path=os.path.join("provenance", "provenance.log.jsonl"),
            model_artifact_hash=None,
        )

        # Pack and extract replay bundle
        bundle_zip = pack_bundle(out)
        bundle_root = tempfile.mkdtemp(prefix="ai-exec-audit-redteam-")
        with zipfile.ZipFile(bundle_zip, "r") as z:
            z.extractall(bundle_root)

        # The hint scanner must flag the bundle
        with pytest.raises(AssertionError):
            assert_no_forbidden_hints(bundle_root)

    finally:
        # cleanup
        for k in ["AI_AUDIT_VENDOR_LICENSE_URL", "AI_AUDIT_SCHEDULER_URL", "AI_AUDIT_DEP_TIMEOUT_S"]:
            os.environ.pop(k, None)
        lic.stop()
        sch.stop()
        shutil.rmtree(bundle_root, ignore_errors=True)
