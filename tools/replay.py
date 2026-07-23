import json
import os
from typing import Any, Dict

from reference_impl.axm_runtime import run as run_reference
from tools.verify import main as verify_main


def read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main(bundle_dir: str, out_dir: str) -> Dict[str, Any]:
    report = verify_main(bundle_dir, require_manifest=True)
    if report["status"] != "ok":
        raise RuntimeError("replay bundle verification failed")
    input_bundle = read_json(os.path.join(bundle_dir, "artifacts", "input_bundle.json"))
    if input_bundle.get("adapter") == "ahead-rev-sim.loop@1":
        from tools.ahead_rev_sim import replay as replay_ahead_rev_sim

        return replay_ahead_rev_sim(bundle_dir, out_dir)

    ir_path = os.path.join(bundle_dir, "ir", "demo_ir.json")
    os.makedirs(out_dir, exist_ok=True)
    return run_reference(
        ir_path=ir_path,
        user_input=input_bundle["input"],
        out_dir=out_dir,
        provenance_path=os.path.join("provenance", "provenance.log.jsonl"),
        model_artifact_hash=None,
    )


if __name__ == "__main__":
    import sys
    bundle = sys.argv[1]
    out = sys.argv[2]
    result = main(bundle, out)
    print(json.dumps(result, indent=2, sort_keys=True))