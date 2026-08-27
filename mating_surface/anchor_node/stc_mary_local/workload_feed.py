from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Iterator, Mapping

from .common import (
    FEATURE_HEADER,
    FEATURE_MAGIC,
    assert_sha256,
    MAX_FEED_BYTES,
    content_id,
    is_inside,
    read_json,
    require,
    safe_int,
    stable_keys,
    stream_sha256,
    validate_new_private_root,
    write_json,
)

class XorShift32:
    def __init__(self, seed: int):
        require(0 < seed <= 0xFFFFFFFF, "FEED_SEED_INVALID", "seed must be 1..2^32-1")
        self.state = seed & 0xFFFFFFFF

    def next_u32(self) -> int:
        x = self.state
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= (x >> 17) & 0xFFFFFFFF
        x ^= (x << 5) & 0xFFFFFFFF
        self.state = x & 0xFFFFFFFF
        return self.state

    def feature(self) -> int:
        return self.next_u32() & 0x0F

    def weight(self) -> int:
        return int(self.next_u32() % 17) - 8


def generate_weights(seed: int, feature_count: int, class_count: int) -> list[list[int]]:
    rng = XorShift32(seed ^ 0xA5A55A5A)
    return [[rng.weight() for _ in range(class_count)] for _ in range(feature_count)]


def feed_manifest_body(*, seed: int, record_count: int, feature_count: int, class_count: int, weights: list[list[int]], feature_sha256: str, feature_bytes: int) -> dict[str, Any]:
    return {
        "schema": "stc-mary-invented-aperture-feed/1",
        "classification": "invented_unclassified_synthetic_only",
        "generator": "xorshift32-low-nibble/1",
        "seed": seed,
        "recordCount": record_count,
        "featureCount": feature_count,
        "classCount": class_count,
        "featureValueRange": [0, 15],
        "weightValueRange": [-8, 8],
        "weights": weights,
        "featureFile": "features.bin",
        "featureSha256": feature_sha256,
        "featureBytes": feature_bytes,
        "expectedHeaderBytes": FEATURE_HEADER.size,
        "semanticKernel": "bounded-integer-linear-aperture-classifier/1",
        "externalServiceCalls": 0,
        "operationalCredentials": 0,
        "authority": "none",
        "claimBoundary": "Invented unclassified local feed for deterministic CPU and accelerator audition. It grants no physical, mission, command, targeting, engagement, effector, or weapons authority.",
    }


def generate_feed(args: Any) -> dict[str, Any]:
    record_count = safe_int(args.records, 1, 50_000_000, "FEED_RECORD_COUNT_INVALID", "record count")
    feature_count = safe_int(args.features, 1, 64, "FEED_FEATURE_COUNT_INVALID", "feature count")
    class_count = safe_int(args.classes, 2, 32, "FEED_CLASS_COUNT_INVALID", "class count")
    seed = safe_int(args.seed, 1, 0xFFFFFFFF, "FEED_SEED_INVALID", "seed")
    payload_bytes = record_count * feature_count
    require(FEATURE_HEADER.size + payload_bytes <= MAX_FEED_BYTES, "FEED_SIZE_INVALID", "feed exceeds byte denominator")
    output = validate_new_private_root(Path(args.out))
    output.mkdir()
    features_path = output / "features.bin"
    rng = XorShift32(seed)
    digest = hashlib.sha256()
    header = FEATURE_HEADER.pack(FEATURE_MAGIC, 1, record_count, feature_count, class_count, seed)
    digest.update(header)
    with features_path.open("wb") as handle:
        handle.write(header)
        remaining = payload_bytes
        chunk_size = 4 * 1024 * 1024
        while remaining:
            count = min(remaining, chunk_size)
            chunk = bytearray(count)
            for index in range(count):
                chunk[index] = rng.feature()
            handle.write(chunk)
            digest.update(chunk)
            remaining -= count
    feature_bytes = features_path.stat().st_size
    feature_sha = digest.hexdigest()
    weights = generate_weights(seed, feature_count, class_count)
    body = feed_manifest_body(
        seed=seed,
        record_count=record_count,
        feature_count=feature_count,
        class_count=class_count,
        weights=weights,
        feature_sha256=feature_sha,
        feature_bytes=feature_bytes,
    )
    manifest = {**body, "feedId": content_id("stcmaryaperturefeed1", body)}
    marker_body = {
        "schema": "stc-mary-local-feed-root/1",
        "profileId": "stc-mary/local-toolchain/0.1",
        "feedId": manifest["feedId"],
        "authority": "none",
        "claimBoundary": "Marker for one invented local feed root outside public Git.",
    }
    write_json(output / "FEED-ROOT.json", {**marker_body, "markerId": content_id("stcmarylocalfeedroot1", marker_body)})
    write_json(output / "feed-manifest.json", manifest)
    return {"status": "PASS", "output": str(output), "feedId": manifest["feedId"], "featureSha256": feature_sha, "featureBytes": feature_bytes}


def validate_feed_manifest(manifest: Mapping[str, Any], feed_dir: Path) -> tuple[Path, int, int, int, list[list[int]]]:
    stable_keys(manifest, [
        "schema", "feedId", "classification", "generator", "seed", "recordCount", "featureCount", "classCount",
        "featureValueRange", "weightValueRange", "weights", "featureFile", "featureSha256", "featureBytes",
        "expectedHeaderBytes", "semanticKernel", "externalServiceCalls", "operationalCredentials", "authority", "claimBoundary",
    ], "FEED_MANIFEST_INVALID", "feed manifest")
    require(manifest["schema"] == "stc-mary-invented-aperture-feed/1", "FEED_MANIFEST_INVALID", "feed schema differs")
    require(manifest["classification"] == "invented_unclassified_synthetic_only", "FEED_MANIFEST_INVALID", "feed classification differs")
    record_count = safe_int(manifest["recordCount"], 1, 50_000_000, "FEED_MANIFEST_INVALID", "record count")
    feature_count = safe_int(manifest["featureCount"], 1, 64, "FEED_MANIFEST_INVALID", "feature count")
    class_count = safe_int(manifest["classCount"], 2, 32, "FEED_MANIFEST_INVALID", "class count")
    safe_int(manifest["seed"], 1, 0xFFFFFFFF, "FEED_MANIFEST_INVALID", "seed")
    require(manifest["featureValueRange"] == [0, 15] and manifest["weightValueRange"] == [-8, 8], "FEED_MANIFEST_INVALID", "feed numeric ranges differ")
    weights = manifest["weights"]
    require(isinstance(weights, list) and len(weights) == feature_count, "FEED_MANIFEST_INVALID", "weight row denominator differs")
    for row in weights:
        require(isinstance(row, list) and len(row) == class_count, "FEED_MANIFEST_INVALID", "weight column denominator differs")
        for value in row:
            safe_int(value, -8, 8, "FEED_MANIFEST_INVALID", "weight")
    assert_sha256(manifest["featureSha256"], "FEED_MANIFEST_INVALID", "feature digest")
    expected_body = dict(manifest)
    feed_id = expected_body.pop("feedId")
    require(feed_id == content_id("stcmaryaperturefeed1", expected_body), "FEED_ID_INVALID", "feed identity differs")
    feature_path = (feed_dir / manifest["featureFile"]).resolve()
    require(is_inside(feed_dir.resolve(), feature_path), "FEED_PATH_INVALID", "feature file escapes feed root")
    require(feature_path.is_file(), "FEED_FILE_MISSING", "feature file is absent")
    sha, size = stream_sha256(feature_path)
    require(sha == manifest["featureSha256"] and size == manifest["featureBytes"], "FEED_FILE_DIGEST_MISMATCH", "feature file digest or size differs")
    with feature_path.open("rb") as handle:
        raw = handle.read(FEATURE_HEADER.size)
    require(len(raw) == FEATURE_HEADER.size, "FEED_HEADER_INVALID", "feature header is truncated")
    magic, version, records, features, classes, seed = FEATURE_HEADER.unpack(raw)
    require(magic == FEATURE_MAGIC and version == 1, "FEED_HEADER_INVALID", "feature header magic or version differs")
    require(records == record_count and features == feature_count and classes == class_count and seed == manifest["seed"], "FEED_HEADER_INVALID", "feature header dimensions or seed differ")
    require(size == FEATURE_HEADER.size + record_count * feature_count, "FEED_FILE_SIZE_INVALID", "feature payload size differs")
    return feature_path, record_count, feature_count, class_count, weights


def load_feed(feed_dir: Path) -> tuple[dict[str, Any], Path, int, int, int, list[list[int]]]:
    feed_dir = feed_dir.expanduser().resolve()
    require(feed_dir.is_dir(), "FEED_ROOT_MISSING", "feed root is absent")
    manifest = read_json(feed_dir / "feed-manifest.json")
    feature_path, record_count, feature_count, class_count, weights = validate_feed_manifest(manifest, feed_dir)
    return manifest, feature_path, record_count, feature_count, class_count, weights


def iter_feature_records(feature_path: Path, record_count: int, feature_count: int, *, chunk_records: int = 8192) -> Iterator[memoryview]:
    with feature_path.open("rb") as handle:
        handle.seek(FEATURE_HEADER.size)
        remaining = record_count
        while remaining:
            records = min(remaining, chunk_records)
            raw = handle.read(records * feature_count)
            require(len(raw) == records * feature_count, "FEED_TRUNCATED", "feature payload is truncated")
            view = memoryview(raw)
            for offset in range(0, len(raw), feature_count):
                yield view[offset:offset + feature_count]
            remaining -= records
        require(handle.read(1) == b"", "FEED_TRAILING_BYTES", "feature payload contains trailing bytes")
