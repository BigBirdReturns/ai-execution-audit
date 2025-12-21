import os
import zipfile

from reference_impl.axm_runtime import run as run_reference
from tools.pack_replay_bundle import main as pack_main
from tools.replay import main as replay_main
from tools.verify import main as verify_main


def test_offline_replay(temp_outdir, block_network):
    os.environ["NO_NETWORK"] = "1"

    ir_path = "ir/demo_ir.json"
    out = os.path.join(temp_outdir, "orig")
    replay_out = os.path.join(temp_outdir, "replay")

    run_reference(
        ir_path=ir_path,
        user_input="Need to reschedule an appointment next week",
        out_dir=out,
        provenance_path=os.path.join("provenance", "provenance.log.jsonl"),
    )

    # Pack minimal replay bundle
    bundle_path = pack_main(out)

    # Extract bundle to a fresh directory to simulate a separate auditor environment
    bundle_dir = os.path.join(temp_outdir, "bundle_extract")
    os.makedirs(bundle_dir, exist_ok=True)
    with zipfile.ZipFile(bundle_path, "r") as z:
        z.extractall(bundle_dir)

    # Replay from bundle artifacts only
    replay_main(bundle_dir, replay_out)

    r_orig = verify_main(out)
    r_replay = verify_main(replay_out)
    assert r_orig["decision_record_sha256"] == r_replay["decision_record_sha256"]
