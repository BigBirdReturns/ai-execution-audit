import json
import os
import hashlib
from typing import Any, Dict

def _canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def main(out_dir: str) -> Dict[str, Any]:
    artifacts = os.path.join(out_dir, "artifacts")
    provenance = os.path.join(out_dir, "provenance", "provenance.log.jsonl")

    report = {
        "input_bundle_sha256": sha256_file(os.path.join(artifacts, "input_bundle.json")),
        "decision_record_sha256": sha256_file(os.path.join(artifacts, "decision_record.json")),
        "provenance_log_sha256": sha256_file(provenance),
        "status": "ok",
    }

    os.makedirs(os.path.join(out_dir, "artifacts"), exist_ok=True)
    with open(os.path.join(out_dir, "artifacts", "verify_report.json"), "wb") as f:
        f.write(_canon(report))

    return report

if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    rep = main(out)
    print(json.dumps(rep, indent=2, sort_keys=True))
