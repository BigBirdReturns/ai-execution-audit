import json
import os
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .provenance_logger import ProvenanceLogger, now_unix_ms, runtime_fingerprint, sha256_obj, sha256_bytes

IMPL = "reference_impl.deterministic_ir"
VERSION = "0.1.0"

class IRExecutionError(Exception):
    pass

def canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _maybe_call_external_dependency(logger: ProvenanceLogger, kind: str, url: str) -> None:
    """Intentionally simulate a control-plane dependency.

    This is used by the red team harness to prove that the audit suite catches
    vendor dependencies (license servers, schedulers, registries, telemetry).
    """
    timeout_s = float(os.environ.get("AI_AUDIT_DEP_TIMEOUT_S", "0.5"))
    event = {
        "ts_ms": now_unix_ms(),
        "event": "external_dependency",
        "kind": kind,
        "url": url,
    }
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            event["status"] = "ok"
            event["http_status"] = int(getattr(resp, "status", 200))
    except Exception as e:
        # Failure still proves the dependency exists.
        event["status"] = "error"
        event["error_type"] = type(e).__name__
    logger.append(event)
def write_bytes(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)

def read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def execute_ir(ir: Dict[str, Any], user_input: str) -> Dict[str, Any]:
    """
    Deterministic IR interpreter.

    IR format:
    {
      "name": "demo",
      "steps": [
        {"op":"normalize_ws"},
        {"op":"lower"},
        {"op":"classify_contains", "labels": {"refund":"billing", "appointment":"scheduling"}, "default":"general"},
        {"op":"emit_decision"}
      ]
    }
    """
    text = user_input
    label = None

    for step in ir.get("steps", []):
        op = step.get("op")
        if op == "normalize_ws":
            text = " ".join(text.split())
        elif op == "lower":
            text = text.lower()
        elif op == "classify_contains":
            labels = step.get("labels", {})
            default = step.get("default", "general")
            label = default
            for k, v in labels.items():
                if k in text:
                    label = v
                    break
        elif op == "emit_decision":
            if label is None:
                label = "general"
        else:
            raise IRExecutionError(f"Unknown op: {op}")

    return {
        "label": label,
        "normalized_text": text,
        "policy": {
            "route_to": label,
            "confidence": 1.0,  # deterministic reference impl
        },
    }

def run(
    ir_path: str,
    user_input: str,
    out_dir: str,
    provenance_path: str,
    model_artifact_hash: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute IR and emit audit artifacts.

    The environment variable NO_NETWORK can be used by tests to indicate that
    the runtime must not attempt any network access.
    """
    ir = read_json(ir_path)
    ir_hash = sha256_obj(ir)
    # Optional override to simulate an upgraded runtime without changing code.
    # Used by examples to demonstrate runtime drift.
    ver = os.environ.get("AI_AUDIT_RUNTIME_VERSION_OVERRIDE", VERSION)
    rf = runtime_fingerprint(IMPL, ver).to_dict()

    input_bundle = {"input": user_input}
    input_hash = sha256_obj(input_bundle)

    decision = execute_ir(ir, user_input)
    decision_bytes = canonical_json(decision)
    decision_hash = sha256_bytes(decision_bytes)

    artifacts_dir = os.path.join(out_dir, "artifacts")
    prov_dir = os.path.join(out_dir, "provenance")
    ir_dir = os.path.join(out_dir, "ir")
    os.makedirs(artifacts_dir, exist_ok=True)
    os.makedirs(prov_dir, exist_ok=True)
    os.makedirs(ir_dir, exist_ok=True)

    write_bytes(os.path.join(artifacts_dir, "input_bundle.json"), canonical_json(input_bundle))
    write_bytes(os.path.join(artifacts_dir, "decision_record.json"), decision_bytes)
    write_bytes(os.path.join(ir_dir, "demo_ir.json"), canonical_json(ir))

    logger = ProvenanceLogger(os.path.join(out_dir, provenance_path))
    logger.append({
        "ts_ms": now_unix_ms(),
        "event": "run_start",
        "runtime": rf,
        "ir_hash": ir_hash,
        "model_hash": model_artifact_hash,
        "input_hash": input_hash,
        "no_network": bool(os.environ.get("NO_NETWORK")),
    })
    # Red team harness: optional simulation of vendor control-plane dependencies.
    # These are OFF by default. Tests can enable them to prove detection.
    lic_url = os.environ.get("AI_AUDIT_VENDOR_LICENSE_URL")
    sch_url = os.environ.get("AI_AUDIT_SCHEDULER_URL")
    if lic_url:
        _maybe_call_external_dependency(logger, kind="license_server", url=lic_url)
    if sch_url:
        _maybe_call_external_dependency(logger, kind="scheduler_endpoint", url=sch_url)

    # Silent dependency variant: no network calls, but embeds policy fingerprints.
    # OFF by default. Red team tests can enable it to prove detection without URLs.
    if os.environ.get("AI_AUDIT_SILENT_DEPENDENCY"):
        fp = os.environ.get("AI_AUDIT_SCHEDULER_FINGERPRINT", "unknown")
        ph = os.environ.get("AI_AUDIT_POLICY_HASH", "unknown")
        logger.append({
            "ts_ms": now_unix_ms(),
            "event": "embedded_dependency",
            "scheduler_fingerprint": fp,
            "policy_hash": ph,
        })

    logger.append({
        "ts_ms": now_unix_ms(),
        "event": "decision_emitted",
        "decision_hash": decision_hash,
    })
    logger.append({
        "ts_ms": now_unix_ms(),
        "event": "run_end",
        "status": "ok",
    })

    return {
        "runtime": rf,
        "ir_hash": ir_hash,
        "model_hash": model_artifact_hash,
        "input_hash": input_hash,
        "decision_hash": decision_hash,
        "out_dir": out_dir,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Reference runtime that emits audit artifacts.")
    parser.add_argument("--ir", dest="ir_path", required=True, help="Path to deterministic IR JSON.")
    parser.add_argument("--input", dest="user_input", required=True, help="User input string.")
    parser.add_argument("--outdir", dest="out_dir", default="out", help="Output directory.")
    parser.add_argument(
        "--provenance",
        dest="provenance_path",
        default=os.path.join("provenance", "provenance.log.jsonl"),
        help="Relative path for provenance log inside the output directory.",
    )
    args = parser.parse_args()

    res = run(
        ir_path=args.ir_path,
        user_input=args.user_input,
        out_dir=args.out_dir,
        provenance_path=args.provenance_path,
    )
    print(json.dumps(res, indent=2, sort_keys=True))
