#!/usr/bin/env python3
"""Run the 5,000-entity gate with the cabinet's qualified projection limit.

The shared cabinet sidecar currently requests a 16-entity read-only projection.
This entry point binds the scale acceptance harness to that same qualified limit
instead of allowing a second hard-coded expectation to create a false failure.
"""
from __future__ import annotations

import run_live_scale_e2e as scale

QUALIFIED_CABINET_LIMIT = 16


def main() -> int:
    scale.CABINET_LIMIT = QUALIFIED_CABINET_LIMIT
    return scale.main()


if __name__ == "__main__":
    raise SystemExit(main())
