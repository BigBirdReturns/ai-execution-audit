import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict

from tools.pack_replay_bundle import BUNDLE_FILES, validate_payload_path

SUPPORTED_MANIFEST_FORMAT = "ai-execution-audit-replay-bundle@1"
REQUIRED_BUNDLE_FILES = set(BUNDLE_FILES)
ALLOWED_ADAPTER_ARTIFACTS = {
    "artifacts/loop.stdout.bin",
    "artifacts/loop.stderr.bin",
}
EXCLUDED_GENERATED_FILES = {
    "artifacts/replay_manifest.json",
    "artifacts/replay_bundle.zip",
    "artifacts/verify_report.json",
}


def _canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _allowed_payload_path(rel: str) -> bool:
    return (
        rel in REQUIRED_BUNDLE_FILES
        or rel in ALLOWED_ADAPTER_ARTIFACTS
        or (rel.startswith("runtime/ahead_rev_sim/") and rel.endswith(".py"))
    )


def _actual_payload_files(root: Path) -> set[str]:
    actual: set[str] = set()
    if not root.is_dir():
        return actual
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel not in EXCLUDED_GENERATED_FILES:
            actual.add(rel)
    return actual


def _append_missing(report: Dict[str, Any], rel: str) -> None:
    if not any(
        mismatch.get("path") == rel and mismatch.get("error") == "missing"
        for mismatch in report["mismatches"]
    ):
        report["mismatches"].append({"path": rel, "error": "missing"})


def main(out_dir: str, require_manifest: bool = False) -> Dict[str, Any]:
    root = Path(out_dir)
    report: Dict[str, Any] = {"mismatches": [], "status": "ok"}
    report_fields = {
        "input_bundle_sha256": "artifacts/input_bundle.json",
        "decision_record_sha256": "artifacts/decision_record.json",
        "provenance_log_sha256": "provenance/provenance.log.jsonl",
    }

    for field, rel in report_fields.items():
        path = root / Path(*rel.split("/"))
        if path.is_file():
            report[field] = sha256_file(path)
        else:
            _append_missing(report, rel)

    artifacts = root / "artifacts"
    manifest_path = artifacts / "replay_manifest.json"
    if not manifest_path.is_file():
        if require_manifest:
            _append_missing(report, "artifacts/replay_manifest.json")
    else:
        report["manifest_sha256"] = sha256_file(manifest_path)
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = None
            report["mismatches"].append({"path": "artifacts/replay_manifest.json", "error": "invalid_json"})

        if not isinstance(manifest, dict) and manifest is not None:
            report["mismatches"].append({"path": "artifacts/replay_manifest.json", "error": "invalid_manifest_type"})
        if isinstance(manifest, dict):
            if manifest.get("format") != SUPPORTED_MANIFEST_FORMAT:
                report["mismatches"].append({"path": "artifacts/replay_manifest.json", "error": "unsupported_format"})
            files = manifest.get("files")
            safe_files: set[str] = set()
            if isinstance(files, dict):
                for rel in files:
                    try:
                        validate_payload_path(rel)
                    except (TypeError, ValueError):
                        report["mismatches"].append({"path": str(rel), "error": "invalid_bundle_path"})
                        continue
                    if not _allowed_payload_path(rel):
                        report["mismatches"].append({"path": rel, "error": "unsupported_bundle_path"})
                        continue
                    safe_files.add(rel)
            else:
                files = {}

            actual_files = _actual_payload_files(root)
            if safe_files != actual_files or not REQUIRED_BUNDLE_FILES.issubset(safe_files):
                report["mismatches"].append({
                    "path": "artifacts/replay_manifest.json",
                    "error": "bundle_file_set_mismatch",
                    "expected_files": sorted(safe_files),
                    "actual_files": sorted(actual_files),
                    "required_files": sorted(REQUIRED_BUNDLE_FILES),
                })

            for rel in sorted(safe_files):
                expected = files.get(rel)
                expected_hash = expected.get("sha256") if isinstance(expected, dict) else None
                path = root / Path(*rel.split("/"))
                if not path.is_file():
                    _append_missing(report, rel)
                    continue
                actual_hash = sha256_file(path)
                if expected_hash != actual_hash:
                    report["mismatches"].append({
                        "path": rel,
                        "expected_sha256": expected_hash,
                        "actual_sha256": actual_hash,
                    })

    report["status"] = "ok" if not report["mismatches"] else "rejected"
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "verify_report.json").write_bytes(_canon(report))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hash-check run artifacts or verify a replay bundle manifest.")
    parser.add_argument("out_dir", nargs="?", default=".")
    parser.add_argument("--require-manifest", action="store_true")
    args = parser.parse_args()
    result = main(args.out_dir, require_manifest=args.require_manifest)
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["status"] == "ok" else 1)