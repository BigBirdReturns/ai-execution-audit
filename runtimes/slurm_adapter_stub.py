"""SLURM adapter stub.

This file is a template. It does not call SLURM.

A real implementation would:
- Submit a job (sbatch) that runs the target runtime.
- Capture job metadata: partition, qos, priority, constraints, node list.
- Emit a scheduler fingerprint event into provenance.
- Copy back decision_record.json and provenance log into out_dir.

The purpose is to show how SLURM becomes an audit boundary, as in the thesis.
"""

from __future__ import annotations

from .base import RunResult


class SlurmAdapterStub:
    name = "slurm_stub"

    def run(self, ir_path: str, user_input: str, out_dir: str, **kwargs) -> RunResult:
        raise NotImplementedError("Implement SLURM submission and artifact capture here.")
