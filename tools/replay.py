import json
import os
from typing import Any, Dict, Optional

from reference_impl.axm_runtime import run as run_reference

def read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def main(bundle_dir: str, out_dir: str) -> Dict[str, Any]:
    # Minimal replay inputs are input_bundle + IR path
    input_bundle = read_json(os.path.join(bundle_dir, "artifacts", "input_bundle.json"))
    ir_path = os.path.join(bundle_dir, "ir", "demo_ir.json")
    os.makedirs(out_dir, exist_ok=True)

    # Replay into a fresh output directory
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
    res = main(bundle, out)
    print(json.dumps(res, indent=2, sort_keys=True))
