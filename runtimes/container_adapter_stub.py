"""Container adapter stub.

This file is a template. It does not call Docker or containerd.

A real implementation would:
- Run the target runtime in a container.
- Capture image digest, base image provenance, and runtime args.
- Emit container fingerprint hints into provenance.
- Copy back artifacts into out_dir.

This helps demonstrate when container abstraction hides execution details.
"""

from __future__ import annotations

from .base import RunResult


class ContainerAdapterStub:
    name = "container_stub"

    def run(self, ir_path: str, user_input: str, out_dir: str, **kwargs) -> RunResult:
        raise NotImplementedError("Implement container execution and artifact capture here.")
