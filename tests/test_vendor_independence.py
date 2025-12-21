import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

from reference_impl.axm_runtime import run as run_reference
from tools.pack_replay_bundle import main as pack_bundle
from tools.replay import main as replay_main
from tools.vendor_hints import assert_no_forbidden_hints

REQUIRED_BUNDLE_PATHS = [
    "artifacts/input_bundle.json",
    "artifacts/decision_record.json",
    "provenance/provenance.log.jsonl",
    "ir/demo_ir.json",
]

# Strings that should never appear in a self-contained replay bundle or logs.
FORBIDDEN_HINTS = [
    "http://",
    "https://",
    "slurm",
    "run:ai",
    "tensorrt",
    "triton",
    "cudnn",
    "telemetry",
    "license",
    "activation",
    "key server",
    "cloud",
    "call home",
    "phone home",
]


def _scan_text_for_forbidden(root: str) -> None:
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            # Only scan small-ish text-like files
            if os.path.getsize(p) > 2_000_000:
                continue
            if not any(fn.endswith(ext) for ext in (".json", ".jsonl", ".md", ".txt", ".log", ".yml", ".yaml")):
                continue
            try:
                blob = Path(p).read_text(encoding="utf-8", errors="ignore").lower()
            except Exception:
                continue
            for s in FORBIDDEN_HINTS:
                assert s not in blob, f"Found forbidden hint '{s}' in {p}"


def test_vendor_independence_replay_bundle_is_self_contained(temp_outdir, block_network):
    """Vendor independence means: you can replay and verify from a bundle,
    with no external services, no downloads, and no control-plane callbacks.

    This test creates a run with the reference implementation, packs a minimal
    replay bundle, extracts it into a fresh directory, and replays it with
    networking blocked. The replay output must match the original decision.
    """
    out = temp_outdir

    # 1) Create an initial run (produces provenance + artifacts + IR)
    res1 = run_reference(
        ir_path=os.path.join("ir", "demo_ir.json"),
        user_input="vendor independence test",
        out_dir=out,
        provenance_path=os.path.join("provenance", "provenance.log.jsonl"),
        model_artifact_hash=None,
    )

    # 2) Pack the replay bundle
    bundle_zip = pack_bundle(out)
    assert os.path.exists(bundle_zip)

    # 3) Validate bundle contents
    with zipfile.ZipFile(bundle_zip, "r") as z:
        names = set(z.namelist())
        for req in REQUIRED_BUNDLE_PATHS:
            assert req in names, f"Replay bundle missing required path: {req}"

    # 4) Extract into a clean directory that simulates post-vendor-offboarding
    bundle_root = tempfile.mkdtemp(prefix="bundle_extract_")
    try:
        with zipfile.ZipFile(bundle_zip, "r") as z:
            z.extractall(bundle_root)

        # 5) Scan extracted artifacts for forbidden hints (URLs, vendor callbacks, etc.)
        _scan_text_for_forbidden(bundle_root)

        # 6) Replay from bundle with networking blocked (fixture enforces it)
        replay_out = tempfile.mkdtemp(prefix="replay_out_")
        try:
            res2 = replay_main(bundle_dir=bundle_root, out_dir=replay_out)

            # 7) Compare canonical decision records
            decision1 = json.load(open(os.path.join(out, "artifacts", "decision_record.json"), "r", encoding="utf-8"))
            decision2 = json.load(open(os.path.join(replay_out, "artifacts", "decision_record.json"), "r", encoding="utf-8"))
            assert decision1 == decision2

            # 8) Also ensure the runtime returned the same output
            assert res1.get("output") == res2.get("output")
        finally:
            shutil.rmtree(replay_out, ignore_errors=True)
    finally:
        shutil.rmtree(bundle_root, ignore_errors=True)
