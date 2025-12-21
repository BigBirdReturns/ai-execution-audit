"""Vendor dependency hint scanner.

This intentionally uses crude string heuristics.

Goal: if any artifact in a replay bundle references an external control plane
(license server, scheduler endpoint, registry, telemetry), treat the run as
*not vendor independent*.

The point is not perfect classification. The point is that audit should fail
loudly when external dependencies exist.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List

# Keep this list simple and legible. Add items only when they are load-bearing.
FORBIDDEN_HINTS: List[str] = [
    "http://",
    "https://",
    "license",
    "licence",
    "token",
    "apikey",
    "api_key",
    "scheduler",
    "slurm",
    "run:ai",
    "runai",
    "telemetry",
    "phone_home",
    "call_home",
    "metrics",
    "control plane",
    "control_plane",
    "registry",
    "docker.io",
    "ghcr.io",
    "nvcr.io",
]


def iter_text_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*"):
        if p.is_dir():
            continue
        # Only scan plausible text-ish files
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".whl"}:
            continue
        yield p


def assert_no_forbidden_hints(root: str | os.PathLike) -> None:
    root_path = Path(root)
    for p in iter_text_files(root_path):
        try:
            blob = p.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            continue
        for s in FORBIDDEN_HINTS:
            if s in blob:
                raise AssertionError(f"Found forbidden hint '{s}' in {p}")
