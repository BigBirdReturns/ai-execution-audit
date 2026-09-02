#!/usr/bin/env python3
"""Recover exact SwarmLLM Qwen3.8 GGUF header and derive tensor/layer custody.

The tool captures public bytes only. It does not claim physical route execution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Iterable
from urllib.parse import quote

MODEL_REPO = "unsloth/Qwen3.8-27B-GGUF"
MODEL_REVISION = "main"
MODEL_FILENAME = "Qwen3.8-27B-Q4_0.gguf"
MODEL_URL = f"https://huggingface.co/{MODEL_REPO}/resolve/{MODEL_REVISION}/{MODEL_FILENAME}"
SITE_URLS = {
    "room.html": "https://swarmllm.ai/room",
    "engine.js": "https://swarmllm.ai/engine/engine.js",
    "gguf.js": "https://swarmllm.ai/engine/gguf.js",
    "qwen35.js": "https://swarmllm.ai/engine/qwen35.js",
    "peerjs.min.js": "https://cdn.jsdelivr.net/npm/peerjs@1.5.4/dist/peerjs.min.js",
}
EXPECTED_MODEL_SHA256 = "ede16c7b36e578ca87a8c70e011e4b4633a32c831c0ce76d0f474582384e671d"

T_U8, T_I8, T_U16, T_I16, T_U32, T_I32, T_F32, T_BOOL, T_STR, T_ARR, T_U64, T_I64, T_F64 = range(13)
GGML_TYPE_NAMES = {
    0: "F32", 1: "F16", 2: "Q4_0", 3: "Q4_1", 8: "Q8_0", 13: "Q5_K", 14: "Q6_K",
}
GGML_LAYOUT = {
    0: (1, 4),
    1: (1, 2),
    2: (32, 18),
    3: (32, 20),
    8: (32, 34),
    13: (256, 176),
    14: (256, 210),
}


class NeedMoreData(Exception):
    pass


class CustodyError(RuntimeError):
    pass


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, chunk: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(chunk):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def write_bytes(path: Path, data: bytes) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {"path": path.as_posix(), "bytes": len(data), "sha256": sha256_bytes(data)}


class Reader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.off = 0

    def need(self, n: int) -> None:
        if n < 0 or self.off + n > len(self.data):
            raise NeedMoreData(f"need {n} bytes at {self.off}, have {len(self.data)}")

    def raw(self, n: int) -> bytes:
        self.need(n)
        value = self.data[self.off:self.off+n]
        self.off += n
        return value

    def unpack(self, fmt: str) -> Any:
        size = struct.calcsize(fmt)
        self.need(size)
        value = struct.unpack_from(fmt, self.data, self.off)[0]
        self.off += size
        return value

    def u8(self) -> int: return self.unpack("<B")
    def i8(self) -> int: return self.unpack("<b")
    def u16(self) -> int: return self.unpack("<H")
    def i16(self) -> int: return self.unpack("<h")
    def u32(self) -> int: return self.unpack("<I")
    def i32(self) -> int: return self.unpack("<i")
    def u64(self) -> int: return self.unpack("<Q")
    def i64(self) -> int: return self.unpack("<q")
    def f32(self) -> float: return self.unpack("<f")
    def f64(self) -> float: return self.unpack("<d")

    def string(self, materialize: bool = True) -> str | None:
        length = self.u64()
        raw = self.raw(length)
        return raw.decode("utf-8") if materialize else None


def parse_value(reader: Reader, value_type: int, *, materialize: bool, key: str) -> Any:
    if value_type == T_U8: return reader.u8()
    if value_type == T_I8: return reader.i8()
    if value_type == T_U16: return reader.u16()
    if value_type == T_I16: return reader.i16()
    if value_type == T_U32: return reader.u32()
    if value_type == T_I32: return reader.i32()
    if value_type == T_F32: return reader.f32()
    if value_type == T_BOOL: return bool(reader.u8())
    if value_type == T_STR: return reader.string(materialize=materialize)
    if value_type == T_U64: return reader.u64()
    if value_type == T_I64: return reader.i64()
    if value_type == T_F64: return reader.f64()
    if value_type == T_ARR:
        element_type = reader.u32()
        count = reader.u64()
        keep = materialize and count <= 4096 and not key.startswith("tokenizer.")
        values = [] if keep else None
        start = reader.off
        for _ in range(count):
            value = parse_value(reader, element_type, materialize=keep, key=key)
            if keep:
                values.append(value)
        raw = reader.data[start:reader.off]
        return {
            "arrayType": element_type,
            "count": count,
            "values": values,
            "rawBytes": len(raw),
            "rawSha256": sha256_bytes(raw),
        }
    raise CustodyError(f"unsupported GGUF metadata type {value_type} for {key}")


def ggml_bytes(ggml_type: int, elements: int) -> int:
    if ggml_type not in GGML_LAYOUT:
        raise CustodyError(f"supplier runtime does not support ggml type {ggml_type}")
    block, size = GGML_LAYOUT[ggml_type]
    if elements % block:
        raise CustodyError(f"tensor element count {elements} not divisible by block {block} for type {ggml_type}")
    return elements // block * size


def parse_gguf_header(data: bytes) -> dict[str, Any]:
    reader = Reader(data)
    if reader.u32() != 0x46554747:
        raise CustodyError("not a GGUF file")
    version = reader.u32()
    if version < 2:
        raise CustodyError(f"unsupported GGUF version {version}")
    tensor_count = reader.u64()
    kv_count = reader.u64()
    metadata: dict[str, Any] = {}
    metadata_rows: list[dict[str, Any]] = []
    for _ in range(kv_count):
        key = reader.string()
        assert isinstance(key, str)
        value_type = reader.u32()
        value_start = reader.off
        materialize = not key.startswith("tokenizer.")
        value = parse_value(reader, value_type, materialize=materialize, key=key)
        value_end = reader.off
        raw = data[value_start:value_end]
        row = {
            "key": key,
            "type": value_type,
            "bytes": len(raw),
            "sha256": sha256_bytes(raw),
            "value": value,
        }
        metadata_rows.append(row)
        if not key.startswith("tokenizer.") or key in {
            "tokenizer.ggml.model", "tokenizer.ggml.pre", "tokenizer.ggml.bos_token_id",
            "tokenizer.ggml.eos_token_id", "tokenizer.ggml.padding_token_id",
        }:
            metadata[key] = value

    infos: list[dict[str, Any]] = []
    for _ in range(tensor_count):
        name = reader.string()
        assert isinstance(name, str)
        dimensions = [reader.u64() for _ in range(reader.u32())]
        ggml_type = reader.u32()
        relative_offset = reader.u64()
        shape = list(reversed(dimensions))
        elements = math.prod(shape)
        byte_length = ggml_bytes(ggml_type, elements)
        infos.append({
            "name": name,
            "shape": shape,
            "ggmlType": ggml_type,
            "ggmlTypeName": GGML_TYPE_NAMES.get(ggml_type, f"TYPE_{ggml_type}"),
            "elements": elements,
            "relativeOffset": relative_offset,
            "byteLength": byte_length,
        })
    header_bytes = reader.off
    alignment = int(metadata.get("general.alignment", 32))
    data_start = ((header_bytes + alignment - 1) // alignment) * alignment
    for row in infos:
        row["byteOffset"] = data_start + row["relativeOffset"]
        row["byteEndInclusive"] = row["byteOffset"] + row["byteLength"] - 1
    return {
        "version": version,
        "tensorCount": tensor_count,
        "metadataCount": kv_count,
        "headerBytes": header_bytes,
        "alignment": alignment,
        "dataStart": data_start,
        "metadata": metadata,
        "metadataRows": metadata_rows,
        "tensors": infos,
    }


def qwen35_layer_names(index: int) -> list[str]:
    prefix = f"blk.{index}."
    shared = [
        prefix + "attn_norm.weight",
        prefix + "post_attention_norm.weight",
        prefix + "ffn_gate.weight",
        prefix + "ffn_up.weight",
        prefix + "ffn_down.weight",
    ]
    if index % 4 == 3:
        return shared + [
            prefix + "attn_q.weight", prefix + "attn_k.weight", prefix + "attn_v.weight",
            prefix + "attn_output.weight", prefix + "attn_q_norm.weight", prefix + "attn_k_norm.weight",
        ]
    return shared + [
        prefix + "attn_qkv.weight", prefix + "attn_gate.weight", prefix + "ssm_beta.weight",
        prefix + "ssm_alpha.weight", prefix + "ssm_dt.bias", prefix + "ssm_a",
        prefix + "ssm_conv1d.weight", prefix + "ssm_norm.weight", prefix + "ssm_out.weight",
    ]


def derive_runtime_manifest(parsed: dict[str, Any], full_size: int | None) -> dict[str, Any]:
    tensors = {row["name"]: row for row in parsed["tensors"]}
    meta = parsed["metadata"]
    block_count = int(meta["qwen35.block_count"])
    nextn = int(meta.get("qwen35.nextn_predict_layers", 0))
    runtime_layers = block_count - nextn
    layers: list[dict[str, Any]] = []
    missing: list[str] = []
    for index in range(runtime_layers):
        names = qwen35_layer_names(index)
        rows = []
        for name in names:
            if name not in tensors:
                missing.append(name)
                continue
            rows.append(tensors[name])
        layers.append({
            "layer": index,
            "kind": "full-attention" if index % 4 == 3 else "gated-deltanet",
            "tensorCount": len(rows),
            "bytes": sum(row["byteLength"] for row in rows),
            "tensors": [
                {
                    "name": row["name"], "byteOffset": row["byteOffset"],
                    "byteEndInclusive": row["byteEndInclusive"], "byteLength": row["byteLength"],
                    "ggmlType": row["ggmlType"], "ggmlTypeName": row["ggmlTypeName"], "shape": row["shape"],
                }
                for row in rows
            ],
        })
    special_names = ["token_embd.weight", "output_norm.weight", "output.weight"]
    special = []
    for name in special_names:
        if name in tensors:
            row = tensors[name]
            special.append({
                "name": name, "byteOffset": row["byteOffset"], "byteEndInclusive": row["byteEndInclusive"],
                "byteLength": row["byteLength"], "ggmlType": row["ggmlType"],
                "ggmlTypeName": row["ggmlTypeName"], "shape": row["shape"],
            })
        elif name != "output.weight":
            missing.append(name)
    if missing:
        raise CustodyError(f"runtime tensor denominator missing: {missing[:20]}")
    max_end = max(row["byteEndInclusive"] for row in parsed["tensors"])
    if full_size is not None and max_end >= full_size:
        raise CustodyError(f"tensor end {max_end} exceeds full size {full_size}")
    type_counts: dict[str, int] = {}
    type_bytes: dict[str, int] = {}
    for row in parsed["tensors"]:
        name = row["ggmlTypeName"]
        type_counts[name] = type_counts.get(name, 0) + 1
        type_bytes[name] = type_bytes.get(name, 0) + row["byteLength"]
    return {
        "schema": "axm-private/swarmllm-qwen38-runtime-manifest@1",
        "modelUrl": MODEL_URL,
        "modelRepository": MODEL_REPO,
        "modelRevision": MODEL_REVISION,
        "modelFilename": MODEL_FILENAME,
        "expectedWholeFileSha256": f"sha256:{EXPECTED_MODEL_SHA256}",
        "fullFileBytes": full_size,
        "ggufVersion": parsed["version"],
        "ggufHeaderBytes": parsed["headerBytes"],
        "ggufDataStart": parsed["dataStart"],
        "tensorCount": parsed["tensorCount"],
        "blockCount": block_count,
        "nextNPredictLayers": nextn,
        "runtimeLayerCount": runtime_layers,
        "runtimeLayerBytes": sum(row["bytes"] for row in layers),
        "specialTensorBytes": sum(row["byteLength"] for row in special),
        "tensorTypeCounts": dict(sorted(type_counts.items())),
        "tensorTypeBytes": dict(sorted(type_bytes.items())),
        "specialTensors": special,
        "layers": layers,
        "claimBoundary": {
            "physicalExecutionObserved": False,
            "actualSupplierQualified": False,
            "physicalEstateQualified": False,
            "missionAuthority": "none",
            "commandAuthority": "none",
        },
    }


def assignment_for_pledges(manifest: dict[str, Any], pledges_gb: list[float]) -> dict[str, Any]:
    if len(pledges_gb) < 1 or any(value <= 0 for value in pledges_gb):
        raise CustodyError("pledges must be positive")
    layers = manifest["layers"]
    layer_count = len(layers)
    if layer_count < len(pledges_gb):
        raise CustodyError("more seats than runtime layers")
    sample_count = min(4, layer_count)
    layer_bytes = sum(row["bytes"] for row in layers[:sample_count]) / sample_count
    embed_bytes = sum(row["byteLength"] for row in manifest["specialTensors"] if row["name"] in {"token_embd.weight", "output.weight"})
    pledge_bytes = [value * 2**30 for value in pledges_gb]
    parts = [max(pledge_bytes[0] - embed_bytes, layer_bytes / 2)] + [max(value, layer_bytes / 2) for value in pledge_bytes[1:]]
    total_cap = sum(parts)
    exact = [layer_count * cap / total_cap for cap in parts]
    assigned = [math.floor(value) for value in exact]
    fractions = sorted(range(len(parts)), key=lambda index: exact[index] - assigned[index], reverse=True)
    remaining = layer_count - sum(assigned)
    for index in range(remaining):
        assigned[fractions[index % len(fractions)]] += 1
    for index in range(1, len(assigned)):
        if assigned[index] == 0:
            donor = max(range(len(assigned)), key=lambda position: assigned[position])
            assigned[donor] -= 1
            assigned[index] += 1
    ranges = []
    cursor = 0
    for count in assigned:
        ranges.append([cursor, cursor + count])
        cursor += count
    seats = []
    for index, (lo, hi) in enumerate(ranges):
        tensor_rows = [tensor for layer in layers[lo:hi] for tensor in layer["tensors"]]
        if index == 0:
            tensor_rows += manifest["specialTensors"]
        seats.append({
            "seatIndex": index,
            "pledgedGB": pledges_gb[index],
            "layerStart": lo,
            "layerEndExclusive": hi,
            "layerCount": hi - lo,
            "tensorCount": len(tensor_rows),
            "tensorBytes": sum(row["byteLength"] for row in tensor_rows),
            "ranges": [
                {
                    "name": row["name"],
                    "byteOffset": row["byteOffset"],
                    "byteEndInclusive": row["byteEndInclusive"],
                    "byteLength": row["byteLength"],
                }
                for row in sorted(tensor_rows, key=lambda row: row["byteOffset"])
            ],
        })
    return {
        "pledgesGB": pledges_gb,
        "estimatedPerLayerBytes": int(layer_bytes),
        "hostEmbedAndHeadBytes": embed_bytes,
        "assignedLayers": assigned,
        "ranges": ranges,
        "seats": seats,
    }


def fetch_range(session: Any, url: str, start: int, end: int, timeout: int = 120) -> tuple[bytes, dict[str, Any]]:
    response = session.get(url, headers={"Range": f"bytes={start}-{end}"}, timeout=timeout, allow_redirects=True)
    if response.status_code not in {200, 206}:
        raise CustodyError(f"range request failed {response.status_code}: {url}")
    data = response.content
    expected = end - start + 1
    if response.status_code == 206 and len(data) != expected:
        raise CustodyError(f"short range {start}-{end}: {len(data)} != {expected}")
    history = [
        {"status": row.status_code, "url": row.url, "headers": dict(sorted(row.headers.items()))}
        for row in response.history
    ]
    return data, {
        "requestUrl": url,
        "finalUrl": response.url,
        "status": response.status_code,
        "headers": dict(sorted(response.headers.items())),
        "redirects": history,
        "rangeStart": start,
        "rangeEndInclusive": end,
        "bytes": len(data),
        "sha256": sha256_bytes(data),
    }


def content_range_total(headers: dict[str, str]) -> int | None:
    value = headers.get("Content-Range") or headers.get("content-range")
    if not value:
        return None
    match = re.search(r"/([0-9]+)$", value)
    return int(match.group(1)) if match else None


def hf_metadata() -> dict[str, Any]:
    from huggingface_hub import HfApi
    info = HfApi().model_info(MODEL_REPO, revision=MODEL_REVISION, files_metadata=True)
    sibling = next((row for row in info.siblings or [] if row.rfilename == MODEL_FILENAME), None)
    if sibling is None:
        raise CustodyError(f"Hugging Face sibling missing: {MODEL_FILENAME}")
    lfs = sibling.lfs or {}
    if hasattr(lfs, "__dict__"):
        lfs = dict(lfs.__dict__)
    row = {
        "repository": MODEL_REPO,
        "requestedRevision": MODEL_REVISION,
        "resolvedSha": info.sha,
        "filename": sibling.rfilename,
        "size": sibling.size,
        "blobId": sibling.blob_id,
        "lfs": lfs,
    }
    raw_sha = lfs.get("sha256") if isinstance(lfs, dict) else None
    if raw_sha and raw_sha != EXPECTED_MODEL_SHA256:
        raise CustodyError(f"repository SHA-256 changed: {raw_sha}")
    return row


def fetch_site_adapter(session: Any, output: Path) -> dict[str, Any]:
    members = []
    for name, url in SITE_URLS.items():
        response = session.get(url, timeout=120, allow_redirects=True)
        if response.status_code != 200:
            raise CustodyError(f"adapter member fetch failed {response.status_code}: {url}")
        data = response.content
        target = output / "adapter" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        members.append({
            "name": name,
            "url": url,
            "finalUrl": response.url,
            "bytes": len(data),
            "sha256": sha256_bytes(data),
            "headers": dict(sorted(response.headers.items())),
        })
    identity_body = {"schema": "axm-private/swarmllm-live-adapter-artifact@1", "members": members}
    identity = "axmswarmllmliveadapter_" + hashlib.sha256(canonical_json(identity_body)).hexdigest()
    manifest = {
        **identity_body,
        "artifactId": identity,
        "memberCount": len(members),
        "claimBoundary": {
            "physicalExecutionObserved": False,
            "actualSupplierQualified": False,
            "physicalEstateQualified": False,
            "missionAuthority": "none",
            "commandAuthority": "none",
        },
    }
    (output / "ADAPTER.json").write_bytes(canonical_json(manifest))
    return manifest


def fetch_header_command(args: argparse.Namespace) -> int:
    import requests
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    session = requests.Session()
    session.headers.update({"User-Agent": "AXM-SwarmLLM-Custody/1.0"})

    metadata = hf_metadata()
    probe_data, probe_receipt = fetch_range(session, MODEL_URL, 0, 0)
    full_size = content_range_total(probe_receipt["headers"]) or metadata.get("size")
    if full_size is None:
        raise CustodyError("full model size unavailable")
    if metadata.get("size") and int(metadata["size"]) != int(full_size):
        raise CustodyError(f"repository and HTTP sizes differ: {metadata['size']} != {full_size}")

    size = 12 * 2**20
    captures = []
    parsed = None
    while size <= args.maximum_header_bytes:
        data, receipt = fetch_range(session, MODEL_URL, 0, size - 1)
        captures.append(receipt)
        try:
            parsed = parse_gguf_header(data)
            prefix = data
            break
        except NeedMoreData:
            size *= 2
    if parsed is None:
        raise CustodyError(f"GGUF header exceeded {args.maximum_header_bytes} bytes")

    exact_header_prefix = prefix[:parsed["dataStart"]]
    (output / "qwen38-gguf-header-prefix.bin").write_bytes(exact_header_prefix)
    runtime = derive_runtime_manifest(parsed, int(full_size))
    plans = [
        assignment_for_pledges(runtime, pair)
        for pair in ([8.5, 8.5], [10.0, 10.0], [12.0, 12.0], [16.0, 16.0], [20.0, 20.0], [24.0, 24.0])
    ]
    runtime["assignmentExamples"] = plans
    (output / "QWEN38-RUNTIME-MANIFEST.json").write_bytes(canonical_json(runtime))
    (output / "GGUF-METADATA.json").write_bytes(canonical_json({
        "schema": "axm-private/swarmllm-qwen38-gguf-metadata@1",
        "version": parsed["version"],
        "headerBytes": parsed["headerBytes"],
        "dataStart": parsed["dataStart"],
        "metadataRows": parsed["metadataRows"],
    }))
    (output / "GGUF-TENSORS.json").write_bytes(canonical_json({
        "schema": "axm-private/swarmllm-qwen38-gguf-tensors@1",
        "tensorCount": parsed["tensorCount"],
        "tensors": parsed["tensors"],
    }))
    adapter = fetch_site_adapter(session, output)
    receipt = {
        "schema": "axm-private/swarmllm-qwen38-header-custody@1",
        "status": "PASS",
        "modelUrl": MODEL_URL,
        "repositoryMetadata": metadata,
        "rangeProbe": probe_receipt,
        "headerFetches": captures,
        "fullFileBytes": full_size,
        "expectedWholeFileSha256": f"sha256:{EXPECTED_MODEL_SHA256}",
        "headerPrefixBytes": len(exact_header_prefix),
        "headerPrefixSha256": sha256_bytes(exact_header_prefix),
        "runtimeLayerCount": runtime["runtimeLayerCount"],
        "tensorCount": runtime["tensorCount"],
        "adapterArtifactId": adapter["artifactId"],
        "claimBoundary": runtime["claimBoundary"],
    }
    (output / "CUSTODY.json").write_bytes(canonical_json(receipt))
    inventory = []
    for path in sorted(p for p in output.rglob("*") if p.is_file() and p.name not in {"INVENTORY.json", "SHA256SUMS.txt"}):
        data = path.read_bytes()
        inventory.append({"path": path.relative_to(output).as_posix(), "bytes": len(data), "sha256": sha256_bytes(data)})
    (output / "INVENTORY.json").write_bytes(canonical_json({
        "schema": "axm-private/swarmllm-qwen38-custody-inventory@1",
        "memberCount": len(inventory),
        "members": inventory,
        "claimBoundary": runtime["claimBoundary"],
    }))
    with (output / "SHA256SUMS.txt").open("w", encoding="utf-8", newline="\n") as handle:
        for row in inventory:
            handle.write(f"{row['sha256'][7:]}  {row['path']}\n")
    print(json.dumps({
        "status": "PASS",
        "fullFileBytes": full_size,
        "headerPrefixBytes": len(exact_header_prefix),
        "runtimeLayers": runtime["runtimeLayerCount"],
        "tensors": runtime["tensorCount"],
        "adapterArtifactId": adapter["artifactId"],
    }, sort_keys=True))
    return 0


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def download_shard_command(args: argparse.Namespace) -> int:
    import requests
    manifest = load_json(Path(args.manifest))
    plan = assignment_for_pledges(manifest, [float(value) for value in args.pledge])
    seat = plan["seats"][args.seat]
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    session = requests.Session()
    session.headers.update({"User-Agent": "AXM-SwarmLLM-Custody/1.0"})
    index_rows = []
    shard_path = output / f"seat-{args.seat:02d}.model-shard.bin"
    digest = hashlib.sha256()
    written = 0
    with shard_path.open("wb") as target:
        for position, tensor in enumerate(seat["ranges"]):
            start = int(tensor["byteOffset"])
            end = int(tensor["byteEndInclusive"])
            data, receipt = fetch_range(session, manifest["modelUrl"], start, end, timeout=args.timeout)
            if len(data) != int(tensor["byteLength"]):
                raise CustodyError(f"tensor length differs: {tensor['name']}")
            target.write(data)
            digest.update(data)
            index_rows.append({
                "position": position,
                "name": tensor["name"],
                "sourceByteOffset": start,
                "sourceByteEndInclusive": end,
                "sourceByteLength": len(data),
                "shardOffset": written,
                "shardEndExclusive": written + len(data),
                "sha256": sha256_bytes(data),
                "http": receipt,
            })
            written += len(data)
    shard_digest = "sha256:" + digest.hexdigest()
    index = {
        "schema": "axm-private/swarmllm-model-shard-custody@1",
        "status": "PASS",
        "modelUrl": manifest["modelUrl"],
        "expectedWholeFileSha256": manifest["expectedWholeFileSha256"],
        "seatIndex": args.seat,
        "pledgesGB": plan["pledgesGB"],
        "layerStart": seat["layerStart"],
        "layerEndExclusive": seat["layerEndExclusive"],
        "layerCount": seat["layerCount"],
        "tensorCount": len(index_rows),
        "shardBytes": written,
        "shardSha256": shard_digest,
        "tensors": index_rows,
        "claimBoundary": manifest["claimBoundary"],
    }
    (output / "SHARD.json").write_bytes(canonical_json(index))
    print(json.dumps({"status": "PASS", "seat": args.seat, "bytes": written, "sha256": shard_digest}, sort_keys=True))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch-header")
    fetch.add_argument("--output", required=True)
    fetch.add_argument("--maximum-header-bytes", type=int, default=384 * 2**20)
    fetch.set_defaults(func=fetch_header_command)
    shard = sub.add_parser("download-shard")
    shard.add_argument("--manifest", required=True)
    shard.add_argument("--output", required=True)
    shard.add_argument("--seat", type=int, required=True)
    shard.add_argument("--pledge", action="append", required=True)
    shard.add_argument("--timeout", type=int, default=300)
    shard.set_defaults(func=download_shard_command)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        return int(args.func(args))
    except (CustodyError, NeedMoreData, OSError, ValueError, KeyError) as exc:
        print(json.dumps({"status": "REFUSED", "code": type(exc).__name__, "message": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
