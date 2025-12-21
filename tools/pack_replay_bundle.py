import os
import zipfile

def main(out_dir: str) -> str:
    bundle_path = os.path.join(out_dir, "artifacts", "replay_bundle.zip")
    os.makedirs(os.path.join(out_dir, "artifacts"), exist_ok=True)

    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        # Minimal set
        z.write(os.path.join(out_dir, "artifacts", "input_bundle.json"), arcname="artifacts/input_bundle.json")
        z.write(os.path.join(out_dir, "artifacts", "decision_record.json"), arcname="artifacts/decision_record.json")
        z.write(os.path.join(out_dir, "provenance", "provenance.log.jsonl"), arcname="provenance/provenance.log.jsonl")
        z.write(os.path.join(out_dir, "ir", "demo_ir.json"), arcname="ir/demo_ir.json")

    return bundle_path

if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv)>1 else "."
    print(main(out))
