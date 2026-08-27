# STC MARY offline two-cell and cold-successor carrier

This carrier closes the two physical-flight preparation gates that the first local toolchain deliberately left on hold: `two_cell_partition` and `successor_head`. It creates content-addressed private bundles that can move without Git, WAN, AWS, Lattice, the original model provider, or the original host. Each bundle carries a standalone stdlib verifier.

The carrier does not execute the flight by itself. A hosted synthetic result proves only the bundle and refusal mechanics. Issue 37 may treat the two gates as ready only after private local attestations are produced on distinct actual host classes.

## Preconditions

Use an exact admitted checkout, Python 3.11 or later, and a private parent outside the public repository.

```powershell
$Repo = 'PATH_TO_EXACT_ADMITTED_CHECKOUT'
$Carrier = Join-Path $Repo 'mating_surface\anchor_node\stc-mary-offline-carrier.ps1'
$Private = 'PATH_TO_PRIVATE_EVIDENCE_PARENT'
```

Set `STC_MARY_PYTHON` to an exact interpreter path when multiple Python installations exist.

## 1. Generate closed input templates

```powershell
$Inputs = Join-Path $Private 'stc-mary-offline-inputs-flight-01'
& $Carrier template-inputs --out $Inputs --repository $Repo
```

Replace the invented template bodies with the actual private materials before the physical campaign:

- one common canonical-state file or directory;
- one attributed left-cell delta;
- one attributed right-cell delta;
- the named-human authority boundary;
- open unresolved obligations;
- the evidence envelope;
- the STC cartridge;
- one bounded next-safe-action text.

Deltas use `stc-mary-offline-cell-delta/1`. Every observation carries its evidence digest. Two identical deltas are refused because they do not prove a partition divergence.

## 2. Build the two offline cells

```powershell
$Pair = Join-Path $Private 'stc-mary-offline-pair-flight-01'
& $Carrier build-cell-pair `
  --common-state (Join-Path $Inputs 'common-state.json') `
  --left-delta (Join-Path $Inputs 'left-delta.json') `
  --right-delta (Join-Path $Inputs 'right-delta.json') `
  --authority (Join-Path $Inputs 'authority.json') `
  --campaign-label 'PRIVATE-STC-MARY-FLIGHT-01' `
  --out $Pair `
  --repository $Repo
```

The pair contains two complete bundles. Each has:

```text
common/
delta.json
authority.json
cell.json
manifest.json
verify_bundle.py
```

The left and right bundles bind one exact parent but produce different child state identities. Each carries `automaticMergeAllowed=false`, `networkRequired=false`, `repositoryHistoryRequired=false`, and `authority=none`.

## 3. Verify each cell on a distinct actual host

Move the complete `left` and `right` directories to separate hosts or independently bootable successor environments. Do not move only the manifest.

On the left host:

```powershell
python verify_bundle.py PATH_TO_LEFT_BUNDLE
& $Carrier verify-cell `
  --bundle PATH_TO_LEFT_BUNDLE `
  --mode private_local_attested `
  --out PATH_TO_PRIVATE_LEFT_VERIFICATION_JSON
```

On the right host:

```powershell
python verify_bundle.py PATH_TO_RIGHT_BUNDLE
& $Carrier verify-cell `
  --bundle PATH_TO_RIGHT_BUNDLE `
  --mode private_local_attested `
  --out PATH_TO_PRIVATE_RIGHT_VERIFICATION_JSON
```

Private mode derives the host-class digest from the executing environment. It refuses caller-supplied host identity. The two verification receipts must carry different host-class digests.

## 4. Reunite without selecting a winner

Return both bundles and both host verification receipts to one private custody root.

```powershell
$Reunion = Join-Path $Private 'stc-mary-reunion-flight-01'
& $Carrier reconcile-cells `
  --left-bundle PATH_TO_LEFT_BUNDLE `
  --right-bundle PATH_TO_RIGHT_BUNDLE `
  --left-verification PATH_TO_PRIVATE_LEFT_VERIFICATION_JSON `
  --right-verification PATH_TO_PRIVATE_RIGHT_VERIFICATION_JSON `
  --out $Reunion `
  --repository $Repo
```

The required terminal result is `HUMAN_REQUIRED`. The reunion retains both branch identities, proves the common parent, records two independent host classes, forbids automatic merge, and creates one unresolved reconciliation obligation.

`two-cell-verification.json` is the digest-only receipt accepted by the local flight-plan compiler. The cell bundles and host evidence remain private.

## 5. Build the cold-successor package

```powershell
$Successor = Join-Path $Private 'stc-mary-successor-flight-01'
& $Carrier build-successor `
  --cartridge PATH_TO_STC_CARTRIDGE `
  --canonical-state PATH_TO_CANONICAL_STATE `
  --authority PATH_TO_AUTHORITY_BOUNDARY_JSON `
  --obligations PATH_TO_OPEN_OBLIGATIONS_JSON `
  --evidence PATH_TO_EVIDENCE_ENVELOPE `
  --next-safe-action PATH_TO_NEXT_SAFE_ACTION_TEXT `
  --out $Successor `
  --repository $Repo
```

The bundle contains the cartridge, state, authority boundary, obligations, evidence envelope, next safe action, six-question answer, manifest, and standalone verifier. No repository history or original model bytes are assumed beyond the exact cartridge contents you selected.

## 6. Verify on the successor HEAD

Capture the original HEAD class digest from the private readiness receipt or a separately sealed local host-class receipt. Move the complete successor bundle to the replacement HEAD, then run:

```powershell
python verify_bundle.py PATH_TO_SUCCESSOR_BUNDLE
& $Carrier verify-successor `
  --bundle PATH_TO_SUCCESSOR_BUNDLE `
  --mode private_local_attested `
  --original-host-class-digest ORIGINAL_HEAD_CLASS_SHA256 `
  --out PATH_TO_PRIVATE_SUCCESSOR_VERIFICATION_JSON
```

The verifier refuses the original host class, reconstructs the complete file denominator, checks all component roots, answers the six cold-successor questions, and proves the following dependencies absent:

```text
WAN
AWS
Lattice
remote_model_provider
original_host
repository_history
```

`successor-verification.json` is the digest-only receipt accepted by the flight-plan compiler.

## 7. Recompile the local flight plan

Pass both private verification receipts into the admitted local toolchain:

```powershell
& (Join-Path $Repo 'mating_surface\anchor_node\stc-mary-local-toolchain.ps1') compile-plan `
  --repository $Repo `
  --readiness PATH_TO_READINESS_PRIVATE_JSON `
  --feed PATH_TO_FEED_ROOT `
  --baseline PATH_TO_BASELINE_JSON `
  --accelerated PATH_TO_ACCELERATED_JSON `
  --continuity PATH_TO_CONTINUITY_JSON `
  --cell-verification (Join-Path $Reunion 'two-cell-verification.json') `
  --successor-verification PATH_TO_PRIVATE_SUCCESSOR_VERIFICATION_JSON `
  --campaign-label 'PRIVATE-STC-MARY-FLIGHT-01' `
  --required-commit EXACT_ADMITTED_COMMIT `
  --out PATH_TO_NEW_PRIVATE_PLAN_ROOT
```

The two gates become `READY` only for `private_local_attested` receipts. Synthetic receipts remain `HOLD` even when every bundle check passes.
