import os
import json
import tempfile
import shutil

from tools.audit_verdict import main as verdict_main


def test_audit_verdict_emits_json() -> None:
    tmp = tempfile.mkdtemp(prefix="audit_verdict_")
    try:
        verdict = verdict_main(tmp)
        path = os.path.join(tmp, "artifacts", "audit_verdict.json")
        assert os.path.exists(path)
        data = json.load(open(path, "r", encoding="utf-8"))
        assert "requirements" in data
        assert set(data["requirements"].keys()) >= {
            "offline_replay",
            "audit_reconstruction",
            "bounded_determinism",
            "vendor_independence",
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
