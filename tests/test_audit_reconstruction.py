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


def test_tampered_replay_bundle_is_rejected(temp_outdir):
    out = os.path.join(temp_outdir, "orig")
    run_reference(
        ir_path="ir/demo_ir.json",
        user_input="Refund request for order 123",
        out_dir=out,
        provenance_path=os.path.join("provenance", "provenance.log.jsonl"),
    )
    bundle_path = pack_main(out)
    bundle_dir = os.path.join(temp_outdir, "tampered")
    os.makedirs(bundle_dir, exist_ok=True)
    with zipfile.ZipFile(bundle_path, "r") as z:
        z.extractall(bundle_dir)

    decision_path = os.path.join(bundle_dir, "artifacts", "decision_record.json")
    with open(decision_path, "r", encoding="utf-8") as f:
        decision = json.load(f)
    decision["label"] = "general"
    with open(decision_path, "w", encoding="utf-8") as f:
        json.dump(decision, f, sort_keys=True, separators=(",", ":"))

    report = verify_main(bundle_dir)
    assert report["status"] == "rejected"
    assert [m["path"] for m in report["mismatches"]] == ["artifacts/decision_record.json"]


def test_replay_manifest_contract_is_fail_closed(temp_outdir):
    out = os.path.join(temp_outdir, "orig")
    run_reference(
        ir_path="ir/demo_ir.json",
        user_input="Refund request for order 123",
        out_dir=out,
        provenance_path=os.path.join("provenance", "provenance.log.jsonl"),
    )
    pack_main(out)
    manifest_path = os.path.join(out, "artifacts", "replay_manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    del manifest["files"]["artifacts/decision_record.json"]
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, sort_keys=True, separators=(",", ":"))
    incomplete = verify_main(out, require_manifest=True)
    assert incomplete["status"] == "rejected"
    assert any(m.get("error") == "bundle_file_set_mismatch" for m in incomplete["mismatches"])

    manifest["format"] = "unsupported@0"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, sort_keys=True, separators=(",", ":"))
    unsupported = verify_main(out, require_manifest=True)
    assert unsupported["status"] == "rejected"
    assert any(m.get("error") == "unsupported_format" for m in unsupported["mismatches"])

    os.remove(manifest_path)
    missing = verify_main(out, require_manifest=True)
    assert missing["status"] == "rejected"
    assert {"path": "artifacts/replay_manifest.json", "error": "missing"} in missing["mismatches"]

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump([], f)
    wrong_type = verify_main(out, require_manifest=True)
    assert wrong_type["status"] == "rejected"
    assert {"path": "artifacts/replay_manifest.json", "error": "invalid_manifest_type"} in wrong_type["mismatches"]


def test_missing_required_artifact_writes_rejection_report(temp_outdir):
    out = os.path.join(temp_outdir, "orig")
    run_reference(
        ir_path="ir/demo_ir.json",
        user_input="Refund request for order 123",
        out_dir=out,
        provenance_path=os.path.join("provenance", "provenance.log.jsonl"),
    )
    pack_main(out)
    os.remove(os.path.join(out, "artifacts", "decision_record.json"))

    report = verify_main(out, require_manifest=True)
    assert report["status"] == "rejected"
    assert {"path": "artifacts/decision_record.json", "error": "missing"} in report["mismatches"]
    assert os.path.isfile(os.path.join(out, "artifacts", "verify_report.json"))


def test_missing_ir_artifact_writes_rejection_report(temp_outdir):
    out = os.path.join(temp_outdir, "orig")
    run_reference(
        ir_path="ir/demo_ir.json",
        user_input="Refund request for order 123",
        out_dir=out,
        provenance_path=os.path.join("provenance", "provenance.log.jsonl"),
    )
    pack_main(out)
    os.remove(os.path.join(out, "ir", "demo_ir.json"))

    report = verify_main(out, require_manifest=True)
    assert report["status"] == "rejected"
    assert {"path": "ir/demo_ir.json", "error": "missing"} in report["mismatches"]
    assert os.path.isfile(os.path.join(out, "artifacts", "verify_report.json"))
