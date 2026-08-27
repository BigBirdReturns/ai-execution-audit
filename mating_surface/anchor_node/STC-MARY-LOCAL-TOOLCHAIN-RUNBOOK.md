# STC MARY local execution toolchain

This toolchain prepares the actual local Estate for the admitted STC Mission Cartridge and MARY Portable Command-Intelligence Cell private flight. It observes real Windows and accelerator state, hashes private local artifacts, generates an invented unclassified workload, proves one backend-independent mission result across the resident floor and HALO3, and compiles a flight plan with explicit readiness and wake conditions.

The toolchain does not execute the sixteen-stage flight by itself. Its private outputs remain outside the public repository. Its public projections contain counts and content identities only. No hardware, runtime, model, verifier, scheduler, or readiness receipt acquires mission or command authority.

## Preconditions

Use a clean checkout of the exact admitted toolchain commit, Python 3.11 or later, and a private evidence parent outside the repository. The local packet and plan destinations must not already exist.

From PowerShell:

```powershell
$Repo = 'PATH_TO_EXACT_ADMITTED_CHECKOUT'
$Tool = Join-Path $Repo 'mating_surface\anchor_node\stc-mary-local-toolchain.ps1'
$Private = 'PATH_TO_PRIVATE_EVIDENCE_PARENT'
```

Set `STC_MARY_PYTHON` to an exact interpreter path when more than one Python installation exists.

## 1. Capture readiness and hash the actual inputs

Declare every load-bearing local artifact. A file receives one digest. A directory receives an ordered manifest over every regular file plus one content identity. Symlinks fail closed.

```powershell
$Prep = Join-Path $Private 'stc-mary-local-prep-flight-01'
& $Tool doctor `
  --repository $Repo `
  --out $Prep `
  --artifact "cartridge=PATH_TO_STC_CARTRIDGE" `
  --artifact "model=PATH_TO_MODEL_OR_EXECUTABLE" `
  --artifact "verifier=PATH_TO_INDEPENDENT_VERIFIER" `
  --artifact "storage=PATH_TO_STORAGE_SUBSTRATE"
```

The private readiness record includes the actual host, user, repository, runtimes, Windows inventory, display and NPU devices, NVIDIA seats, volumes, adapters, listeners, power scheme, Lattice-shaped process and service probes, Python backend availability, and declared artifact manifests. `readiness-public-projection.json` removes the local paths and host identity.

## 2. Generate the invented local feed

The workload uses an integer linear aperture classifier. Every feature and weight remains within a range whose products and sums are exactly representable in float32, allowing Python, NumPy, Torch CPU, and Torch CUDA to produce the same class stream.

```powershell
$Feed = Join-Path $Private 'stc-mary-local-feed-flight-01'
& $Tool generate-feed `
  --out $Feed `
  --records 262144 `
  --features 32 `
  --classes 8 `
  --seed 20260827
```

The feed is invented and unclassified. Its manifest binds the generator, dimensions, rule matrix, binary feature payload, byte count, and SHA-256.

## 3. Establish the resident personal floor

Run the stdlib backend first. It is the mission-closed fallback and the independent semantic reference.

```powershell
$Baseline = Join-Path $Private 'personal-floor-baseline.json'
$BaselineVerification = Join-Path $Private 'personal-floor-baseline-verification.json'

& $Tool run-workload --feed $Feed --backend python --out $Baseline
& $Tool verify-workload --feed $Feed --result $Baseline --out $BaselineVerification
```

A locally available NumPy or Torch CPU route may also be measured, but the personal-floor result must remain resident CPU work and must verify through the separate stdlib path.

## 4. Audition HALO3

The HALO3 gate accepts only `torch-cuda`. A faster CPU library does not qualify the accelerator. Use the exact CUDA device index selected by the private NVIDIA and Torch census.

```powershell
$Accelerated = Join-Path $Private 'halo3-accelerated.json'
$AcceleratedVerification = Join-Path $Private 'halo3-accelerated-verification.json'

& $Tool run-workload --feed $Feed --backend torch-cuda --device-index 0 --out $Accelerated
& $Tool verify-workload --feed $Feed --result $Accelerated --out $AcceleratedVerification
```

HALO3 qualifies for this bounded workload only when it returns the exact baseline semantic and classification digests and exceeds baseline end-to-end throughput.

## 5. Remove HALO3 and re-prove the personal floor

Use the separately declared reversible interruption method. For the first flight, process-level worker interruption is preferable to firmware, BIOS, voltage, reset, or destructive device operations. After HALO3 is absent or inaccessible, rerun the resident floor.

```powershell
$Continuity = Join-Path $Private 'personal-floor-after-halo3-removal.json'
$ContinuityVerification = Join-Path $Private 'personal-floor-after-halo3-removal-verification.json'
$Comparison = Join-Path $Private 'personal-floor-halo3-comparison.json'

& $Tool run-workload --feed $Feed --backend python --out $Continuity
& $Tool verify-workload --feed $Feed --result $Continuity --out $ContinuityVerification
& $Tool compare-workloads `
  --baseline $Baseline `
  --accelerated $Accelerated `
  --continuity $Continuity `
  --out $Comparison
```

The comparison closes only when all three runs produce one accepted semantic output, HALO3 accelerates it, and the resident floor reproduces it after HALO3 removal.

## 6. Compile the local flight plan

Use the exact admission commit from the toolchain admission receipt, not a branch name or moving `main`.

```powershell
$Plan = Join-Path $Private 'stc-mary-local-plan-flight-01'
$AdmittedCommit = 'REPLACE_WITH_EXACT_ADMITTED_TOOLCHAIN_COMMIT'

& $Tool compile-plan `
  --repository $Repo `
  --readiness (Join-Path $Prep 'readiness-private.json') `
  --feed $Feed `
  --baseline $Baseline `
  --accelerated $Accelerated `
  --continuity $Continuity `
  --campaign-label 'PRIVATE-STC-MARY-FLIGHT-01' `
  --required-commit $AdmittedCommit `
  --out $Plan
```

The compiler independently evaluates eight gates: admitted checkout, personal floor, HALO3, post-removal continuity, Lattice absence, two-cell partition, successor HEAD, and private evidence root. It emits `READY`, `HOLD`, or `REFUSE` with an exact wake condition. It cannot convert the unmeasured two-cell or successor work into readiness.

`flight-config.generated.json` deliberately retains `REPLACE_WITH_` values for the successor HEAD and both partition cells. The admitted packet refuses those placeholders until the second host and cells are actually bound.

## 7. Hand the prepared plan to the admitted private packet

After every placeholder is replaced and the checkout gate is READY:

```powershell
$Packet = Join-Path $Private 'stc-mary-private-flight-local-01'
$PacketRunner = Join-Path $Repo 'mating_surface\anchor_node\stc-mary-private-flight.ps1'

& $PacketRunner init $Packet 'PRIVATE-STC-MARY-FLIGHT-01'
& $PacketRunner configure $Packet (Join-Path $Plan 'flight-config.generated.json')
& $PacketRunner status $Packet
```

Continue issue 37 through the admitted sixteen-stage packet. The two-cell carrier and cold-successor carrier remain the next local-toolchain increment. They must operate without repository history, preserve divergent state, and return `HUMAN_REQUIRED` rather than automatically selecting a winner.
