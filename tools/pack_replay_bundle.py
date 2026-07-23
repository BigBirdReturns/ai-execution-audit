import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import zipfile

BUNDLE_FILES = [
    "artifacts/input_bundle.json",
    "artifacts/decision_record.json",
    "provenance/provenance.log.jsonl",
    "ir/demo_ir.json",
]
MANIFEST_PATH = "artifacts/replay_manifest.json"
RESERVED_PAYLOAD_PATHS = {
    MANIFEST_PATH,
    "artifacts/replay_bundle.zip",
    "artifacts/verify_report.json",
}


def validate_bundle_path(rel: str) -> str:
    if not isinstance(rel, str) or not rel:
        raise ValueError("bundle path must be a non-empty string")
    if "\\" in rel or ":" in rel or rel.startswith("/") or rel.endswith("/") or "//" in rel:
        raise ValueError(f"unsafe bundle path: {rel!r}")
    path = PurePosixPath(rel)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise ValueError(f"unsafe bundle path: {rel!r}")
    if path.as_posix() != rel:
        raise ValueError(f"non-canonical bundle path: {rel!r}")
    return rel


def validate_payload_path(rel: str) -> str:
    validate_bundle_path(rel)
    if rel in RESERVED_PAYLOAD_PATHS:
        raise ValueError(f"reserved bundle payload path: {rel}")
    return rel


def _sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _selected_files(out_dir: str | Path, bundle_files: list[str] | None) -> list[str]:
    selected = list(BUNDLE_FILES if bundle_files is None else bundle_files)
    if len(selected) != len(set(selected)):
        raise ValueError("duplicate replay bundle path")
    root = Path(out_dir)
    for rel in selected:
        validate_payload_path(rel)
        if not (root / Path(*rel.split("/"))).is_file():
            raise FileNotFoundError(f"replay bundle payload is missing: {rel}")
    return sorted(selected)


def main(out_dir: str, bundle_files: list[str] | None = None) -> str:
    root = Path(out_dir)
    artifacts = root / "artifacts"
    bundle_path = artifacts / "replay_bundle.zip"
    artifacts.mkdir(parents=True, exist_ok=True)
    selected = _selected_files(root, bundle_files)

    manifest = {
        "format": "ai-execution-audit-replay-bundle@1",
        "files": {
            rel: {"sha256": _sha256_file(root / Path(*rel.split("/")))}
            for rel in selected
        },
    }
    manifest_path = artifacts / "replay_manifest.json"
    with manifest_path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, sort_keys=True, separators=(",", ":"))
        f.write("\n")

    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for rel in selected:
            archive.write(root / Path(*rel.split("/")), arcname=rel)
        archive.write(manifest_path, arcname=MANIFEST_PATH)
    return str(bundle_path)


def safe_extract_bundle(bundle_zip: str | Path, destination: str | Path) -> str:
    destination = Path(destination)
    with zipfile.ZipFile(bundle_zip, "r") as archive:
        infos = archive.infolist()
        names: list[str] = []
        for info in infos:
            rel = validate_bundle_path(info.filename)
            if info.is_dir():
                raise ValueError(f"directory member is not allowed: {rel}")
            mode = (info.external_attr >> 16) & 0xFFFF
            if mode and stat.S_ISLNK(mode):
                raise ValueError(f"symlink member is not allowed: {rel}")
            names.append(rel)
        if len(names) != len(set(names)):
            raise ValueError("duplicate replay bundle member")
        if MANIFEST_PATH not in names:
            raise ValueError("replay bundle manifest is missing")
        try:
            manifest = json.loads(archive.read(MANIFEST_PATH).decode("utf-8-sig"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid replay bundle manifest") from exc
        if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), dict):
            raise ValueError("invalid replay bundle manifest shape")
        payload = set()
        for rel in manifest["files"]:
            payload.add(validate_payload_path(rel))
        expected = payload | {MANIFEST_PATH}
        if set(names) != expected:
            raise ValueError("zip members do not exactly match the replay manifest")

        destination.mkdir(parents=True, exist_ok=True)
        resolved_root = destination.resolve()
        for rel in sorted(names):
            target = destination / Path(*rel.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            resolved_target = target.resolve()
            if resolved_root != resolved_target and resolved_root not in resolved_target.parents:
                raise ValueError(f"bundle member escapes destination: {rel}")
            target.write_bytes(archive.read(rel))
    return str(destination)


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    print(main(out))