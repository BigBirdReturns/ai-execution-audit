import os

from reference_impl.axm_runtime import run as run_reference
from tools.verify import main as verify_main


def test_bounded_determinism(temp_outdir):
    os.environ["NO_NETWORK"] = "1"
    ir_path = "ir/demo_ir.json"
    prompt = "Refund request for order 123"

    hashes = []
    for i in range(10):
        out = os.path.join(temp_outdir, f"run_{i}")
        run_reference(
            ir_path=ir_path,
            user_input=prompt,
            out_dir=out,
            provenance_path=os.path.join("provenance", "provenance.log.jsonl"),
        )
        rep = verify_main(out)
        hashes.append(rep["decision_record_sha256"])

    assert len(set(hashes)) == 1
