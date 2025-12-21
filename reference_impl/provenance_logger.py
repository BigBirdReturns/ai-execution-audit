import hashlib
import json
import os
import platform
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

def _canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def sha256_obj(obj: Any) -> str:
    return sha256_bytes(_canon(obj))

@dataclass
class RuntimeFingerprint:
    python: str
    platform: str
    implementation: str
    version: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "python": self.python,
            "platform": self.platform,
            "implementation": self.implementation,
            "version": self.version,
        }

def runtime_fingerprint(implementation: str, version: str) -> RuntimeFingerprint:
    return RuntimeFingerprint(
        python=sys.version.split(" ")[0],
        platform=platform.platform(),
        implementation=implementation,
        version=version,
    )

class ProvenanceLogger:
    """
    Append-only JSONL provenance ledger.

    The ledger is intentionally boring:
    - canonical JSON
    - event timestamps
    - stable hashes of inputs/outputs/IR/runtime
    """

    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def append(self, event: Dict[str, Any]) -> None:
        line = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

def now_unix_ms() -> int:
    return int(time.time() * 1000)
