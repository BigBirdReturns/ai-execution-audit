from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol


@dataclass
class RunResult:
    out_dir: str
    decision_record_path: str
    provenance_log_path: str


class RuntimeAdapter(Protocol):
    """Minimal adapter contract.

    A real adapter should:
    - Execute a run using a real runtime (scheduler, container, SDK).
    - Materialize artifacts in out_dir in the same layout as reference_impl.
    - Return paths for decision record and provenance log.
    """

    name: str

    def run(self, ir_path: str, user_input: str, out_dir: str, **kwargs: Any) -> RunResult:
        ...


def adapter_metadata(name: str, notes: str) -> Dict[str, str]:
    return {"name": name, "notes": notes}
