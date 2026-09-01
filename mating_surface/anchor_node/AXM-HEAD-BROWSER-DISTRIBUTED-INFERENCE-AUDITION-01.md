# AXM HEAD Browser Distributed-Inference Audition 01

## Object

This source defines a supplier-neutral browser observation and verification membrane for implementations of `axm/distributed-model-inference@1`. It is the successor transaction to the distributed-inference commodity admitted by PR #91 and the implementation object for issue #92.

The actors remain separate. The Estate owns work-unit requirements, route comparison, leases, validators, evidence custody, and disposition. A browser-delivered implementation supplies only an executable candidate below the replaceable adapter boundary. Nehanth Narendrula and SwarmLLM remain one public supplier observation already present on the floor. Neither the actor nor the product receives a privileged schema, work-unit field, terminal, or validator.

## Exact predecessor binding

```text
repository:
BigBirdReturns/ai-execution-audit

commodity admission commit:
8d18d2c4b6df505751574f219c8c8dd69877a6df

commodity admission tree:
7c8d1786cbae8277c55ca17d115b44c9ec4cae7d

commodity interface:
axm/distributed-model-inference@1

commodity product members:
7 exact Git blobs
```

The profile freezes the seven predecessor blob identities. This object does not rewrite the commodity, supplier catalog, route law, no-memory-pooling law, or public SwarmLLM disposition.

## Mechanism

The JavaScript probe is intended for installation as an initialization script before supplier application code. It observes browser APIs that can carry a distributed inference route:

```text
navigator.gpu adapter and device acquisition
fetch request and response metadata without response bodies
WebSocket and EventSource signaling byte counts
RTCPeerConnection lifecycle and selected candidate-pair class
RTCDataChannel ordering, reliability configuration, and byte counts
model-artifact identities supplied by the audition controller
token appearance timestamps without token text
controlled member removal and observed recovery terminal
output-equivalence digest comparison
privacy declarations scoped to observer visibility
```

The probe does not retain prompts, completions, token text, SDP, ICE addresses, device labels, raw URLs, model URLs, credentials, or response bodies. Endpoint, member, model, and channel identifiers are reduced to per-capture random opaque identifiers. The raw private event ledger is bounded by both event and encoded-byte ceilings before semantic evaluation. A separate controller record carries only the declared work unit, test controls, expected public projection, and physical-member uniqueness assertions. The normalized route capture is then deterministically materialized from those two independently identified objects and binds both SHA-256 references.

Browser observation has a hard epistemic boundary. A visible peer connection can establish that the browser formed a route. It cannot prove that an unseen server never received a prompt. Absence of a visible HTTP prompt is therefore recorded as observer silence rather than end-to-end confidentiality. Network exposure and privacy declaration remain separate receipts.

## Receipt denominator

A complete route observation carries exactly nine independently named receipt classes:

```text
current-availability-observation
executable-adapter-artifact
formation-capacity-receipt
formation-topology-receipt
member-drop-behavior-receipt
model-output-equivalence-receipt
performance-receipt
network-exposure-observation
privacy-declaration
```

The supplier-admission receipt is deliberately outside this denominator. An audition may establish an observed route candidate. It cannot admit its own supplier.

Formation capacity cannot come from a room label or summed memory display. The capture must bind unique physical members to measured model artifacts and contiguous layer ranges. `modelCapacityBytes` must remain within the member pledge ceiling, but that arithmetic ceiling is not itself admission evidence.

Performance requires the prompt-token count, output-token count, start time, first-token time, last-token time, and one monotonic mark for every output token. No token body is retained. Output equivalence requires a separately produced reference digest, an equal candidate digest, and matching token denominators.

## Closed terminals

```text
PREPARED_FOR_PHYSICAL_AUDITION
OBSERVED_ROUTE_CANDIDATE
HOLD
```

`PREPARED_FOR_PHYSICAL_AUDITION` means the source, probe, profile, fixtures, decision logic, independent verifier, and measured-verifier bootstrap are qualified, while no complete live route capture is present.

`OBSERVED_ROUTE_CANDIDATE` requires a complete capture with early instrumentation, current availability, an executable adapter artifact, unique members, artifact-bound capacity, observed topology, an ordered reliable activation channel, model identity, complete timing, controlled member removal, output equivalence, the nine receipt classes, and privacy treatment confined to browser visibility. The synthetic fixture reaches this terminal only to prove source semantics. It retains `syntheticConformanceOnly: true`, `executionOccurred: false`, and `actualSupplierQualified: false`.

`HOLD` refuses late instrumentation, UI-only capacity, duplicate members, missing selected topology, unreliable activation transport, model-label substitution, incomplete timing, uncontrolled member loss, public evidence leakage, privacy overclaim, supplier-specific work-unit pinning, capture-limit breach, raw event or summary disagreement, raw-body or network-identity leakage, normalized-capture divergence from raw evidence, supplier self-admission, and stored-receipt forgery.

## Independent reconstruction

The materializer first validates the bounded raw event ledger and controller record, reconstructs every normalized adapter, formation, model, transport, timing, drop, equivalence, privacy, and receipt-reference field, and binds the raw and controller object digests into the normalized capture. The builder then derives the capture digest while excluding only the stored observation-receipt digest field. A stored digest must equal that reconstruction.

For an observed route candidate, the standalone verifier independently rematerializes the normalized capture from the supplied raw event ledger and controller record before repeating the classification, capture digest, observation receipt, terminal, reason-code, claim-boundary, and public-projection checks. A normalized capture that is internally consistent but differs from the raw evidence therefore refuses. Called directly, the verifier is structurally unable to claim bootstrap authentication. The external bootstrap resolves the verifier, profile, normalized capture, decision, raw ledger, controller record, and optional verdict output against the caller's working directory before it enters a foreign temporary directory. It then measures the verifier bytes once, executes only those measured bytes under an isolated interpreter, requires the stored verifier member to remain byte-identical after execution, and only then emits `bootstrapAuthenticated: true`.

## Source qualification

CI does not launch a browser, contact an endpoint, download a model, create a peer connection, or perform inference. It materializes the ten authoritative source members from exact Git blobs, verifies the seven-member predecessor commodity binding, compiles the Python sources, checks the JavaScript syntax, executes the fifty-four-test hostile suite, evaluates all fifteen fixtures, exercises the PowerShell entrypoint on Windows, and compares canonical campaign, profile, probe, and source-set receipts across Ubuntu, Windows, exact head, and synthesized merge coordinates. The job-level environment uses only static values available before runner assignment; runner-specific paths are consumed inside steps after a runner exists and enter Python as command-line arguments rather than interpolated source literals. Exact Git-blob rematerialization may differ from checkout-normalized working-tree bytes on Windows, so coordinate custody compares every closed source member with the selected Git object and separately refuses any drift outside the ten-member source set instead of relying on blanket working-tree cleanliness.

## Operator surface

```powershell
$Root = 'mating_surface\anchor_node'
$Profile = Join-Path $Root 'axm-head-browser-distributed-inference-audition-profile-01.json'
$Fixtures = Join-Path $Root 'fixtures\axm-head-browser-distributed-inference-audition-cases-01.json'
$Tool = Join-Path $Root 'axm-head-browser-distributed-inference-audition.ps1'

& $Tool validate-profile $Profile
& $Tool validate-fixtures $Profile $Fixtures
& $Tool campaign $Profile $Fixtures
& $Tool probe-digest (Join-Path $Root 'browser_distributed_inference_probe.js')

# After one controlled browser run has produced bounded raw and controller records:
& $Tool materialize $Profile '<private-raw.json>' '<private-control.json>' `
  --out '<private-normalized-capture.json>' `
  --receipt-out '<private-materialization-receipt.json>'
& $Tool assess $Profile '<private-normalized-capture.json>'
& $Tool bootstrap-verify $Profile '<private-normalized-capture.json>' '<private-decision.json>' `
  --raw '<private-raw.json>' --control '<private-control.json>'
```

A later physical transaction may inject the probe into a controlled browser context and materialize a private capture. That transaction must bind the exact probe digest, preserve raw evidence privately, derive a body-free public projection, and stop at `OBSERVED_ROUTE_CANDIDATE` until a separate supplier-admission decision exists.

## Claim boundary

```text
supplier-neutral audition source constructed: true
synthetic route semantics exercised: true
public supplier observed on commodity floor: true
browser launched by this source transaction: false
external endpoint contacted by CI: false
model downloaded by CI: false
inference executed by CI: false
physical audition completed: false
actual SwarmLLM qualified: false
actual supplier qualified: false
supplier admission receipt present: false
physical Estate qualified: false
mission authority: none
command authority: none
```

## Control question

Can a browser-delivered distributed-inference implementation be observed, interrupted, reconstructed, and compared as one replaceable Estate route while making its UI, supplier identity, aggregate-memory claim, and privacy marketing incapable of qualifying themselves?
