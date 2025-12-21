import os
import json
import zipfile

from reference_impl.axm_runtime import run as run_reference
from tools.pack_replay_bundle import main as pack_main
from tools.replay import main as replay_main
from tools.verify import main as verify_main


def parse_provenance(path: str):
    events = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            events.append(json.loads(line))
    return events


def test_audit_reconstruction_from_artifacts(temp_outdir):
    os.environ["NO_NETWORK"] = "1"
    ir_path = "ir/demo_ir.json"
    out = os.path.join(temp_outdir, "orig")

    run_reference(
        ir_path=ir_path,
        user_input="Appointment scheduling question",
        out_dir=out,
        provenance_path=os.path.join("provenance", "provenance.log.jsonl"),
    )

    prov_path = os.path.join(out, "provenance", "provenance.log.jsonl")
    events = parse_provenance(prov_path)

    start = [e for e in events if e.get("event") == "run_start"][0]
    assert "runtime" in start
    assert "ir_hash" in start
    assert "input_hash" in start

    # Bundle the minimum artifacts, then reconstruct in a clean directory
    bundle_path = pack_main(out)
    bundle_dir = os.path.join(temp_outdir, "bundle_extract")
    os.makedirs(bundle_dir, exist_ok=True)
    with zipfile.ZipFile(bundle_path, "r") as z:
        z.extractall(bundle_dir)

    recon_out = os.path.join(temp_outdir, "reconstructed")
    replay_main(bundle_dir, recon_out)

    rep_orig = verify_main(out)
    rep_recon = verify_main(recon_out)
    assert rep_orig["decision_record_sha256"] == rep_recon["decision_record_sha256"]
