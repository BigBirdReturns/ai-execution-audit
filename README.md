# ai-execution-audit

Execution auditability is not a model problem.
It is an execution control problem.

This repository turns that claim into code.

It defines a small set of **binary tests** that an AI runtime must pass to be considered **externally auditable** in regulated, safety relevant, or sovereignty constrained environments.

## What this tests

An auditable system must satisfy all four requirements:

1. **Offline replay**
   - Reproduce decisions with no network and no external services.

2. **Audit reconstruction from artifacts alone**
   - Reconstruct what executed using only a replay bundle.
   - No dashboards, no vendor APIs, no remote logs.

3. **Bounded determinism**
   - Produce identical decision records given the same inputs and pinned artifacts.

4. **Vendor independence**
   - Execute and audit after vendor support ends or access is severed.

If a runtime cannot pass these tests, an external party cannot independently verify what happened.
At that point audit collapses into vendor attestation.

## Why this exists

Modern AI stacks increasingly bind together:
- accelerator hardware
- proprietary kernels and libraries
- adaptive runtimes
- orchestration and scheduling
- observability and policy enforcement

When the runtime is adaptive and the control plane is opaque, you lose the ability to answer basic audit questions:
- What code ran
- With what inputs
- Under what policy
- With what determinism bounds
- With what provenance

This repo provides a minimal harness to test those properties.

## Quick start

### One-command run

macOS/Linux:
```bash
./run_audit.sh
```

Windows PowerShell:
```powershell
.\run_audit.ps1
```


### Option A: Source first (recommended)

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

### Option B: Docker (convenience only)

Docker is a deployment wrapper, not an audit boundary.
Use it for convenience, not as the reference method.

```bash
docker build -t ai-execution-audit .
docker run --rm -it ai-execution-audit pytest -q
```

## How the reference implementation works

The reference runtime passes the tests by:
- executing a deterministic intermediate representation (IR)
- writing an append only provenance ledger
- packaging a replay bundle that can be verified and replayed offline

Key folders:

- `ir/`                      deterministic IR inputs
- `reference_impl/`          a minimal runtime that emits audit artifacts
- `provenance/`              provenance ledger output (gitkept)
- `artifacts/`               replay bundles and verification reports (gitkept)
- `tools/`                   pack, replay, and verify utilities
- `tests/`                   the auditability test suite

## Artifacts produced by a run

A successful run produces:
- `artifacts/replay_bundle.zip`          all inputs and pinned artifacts required for replay
- `artifacts/replay_manifest.json`       producer-recorded SHA-256 identity for every bundled artifact
- `artifacts/verify_report.json`         hash verification report
- `provenance/provenance.log.jsonl`      append only provenance ledger

See `docs/provenance_schema.json` for the formal schema.

## Worked failure scenarios

These are short, concrete reproductions of common audit failure modes:

- `examples/failure_scenarios/runtime_upgrade_drift/`
- `examples/failure_scenarios/scheduler_unavailable/`

## Extending to other runtimes

To test a different runtime, do not edit the tests.
Create an adapter that produces the same artifact set as the reference implementation.

Start here: `docs/extending.md`.

## Background signals (non normative references)

This project was motivated by recent consolidation in the AI execution and scheduling stack and by DOE efforts to scale national lab AI infrastructure.

- NVIDIA acquisition of SchedMD (Slurm): https://blogs.nvidia.com/blog/nvidia-acquires-schedmd/
- Reuters coverage: https://www.reuters.com/business/nvidia-buys-ai-software-provider-schedmd-expand-open-source-ai-push-2025-12-15/
- DOE announcement on Solstice and Equinox systems: https://www.energy.gov/articles/energy-department-announces-new-partnership-nvidia-and-oracle-build-largest-doe-ai
- Argonne overview: https://www.anl.gov/article/argonne-expands-nations-ai-infrastructure-with-powerful-new-supercomputers
- Reuters on DOE Genesis Mission partnerships: https://www.reuters.com/business/retail-consumer/us-energy-department-taps-big-tech-ai-powered-research-push-2025-12-18/

## License

Apache-2.0 (see `LICENSE`).

## Red team harness

This repository includes an intentional "red team" harness that simulates vendor control-plane
dependencies (license servers and scheduler endpoints) and proves the suite catches them.

See `tools/red_team/` and `tests/test_red_team_harness.py`.

## Audit verdict artifact

Run a one-command verdict generator:

```bash
python -m tools.audit_verdict .
cat artifacts/audit_verdict.json
```

The verdict is a single JSON file designed for screenshots and reports.

## Runtime adapters

See `docs/adapters.md` and `runtimes/*_stub.py` for templates to wrap real stacks (SLURM, containers, vendor SDKs) and run them through the same audit checks.

### Real local adapter: Ahead Rev Sim

The first real-project path captures Ahead Rev Sim's deterministic `loop` CLI, copies its observed Python source closure into the replay bundle, records raw stdout/stderr bytes, and replays without consulting the original checkout:

```powershell
python -m tools.ahead_rev_sim capture D:\Projects\Ahead-Rev-Sim\main out\ahead
python -c "from tools.pack_replay_bundle import safe_extract_bundle; safe_extract_bundle(r'out\ahead\artifacts\replay_bundle.zip', r'out\ahead-extracted')"
python -m tools.verify out\ahead-extracted --require-manifest
python -m tools.replay out\ahead-extracted out\ahead-replayed
```

This proves source-contained replay for that operation under a compatible local Python interpreter. The interpreter itself is not bundled. The replay manifest detects missing, extra, or changed payload bytes; it is not a signature or authenticity proof.
\n## Example output (for preview)\n\nSee `examples/demo_output/` for a sample artifact set and verdict JSON generated by the reference implementation.
