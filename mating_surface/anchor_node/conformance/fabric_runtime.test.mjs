import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import {
  FabricRuntimeError,
  createFabricWorkload,
  createSeatAdmission,
  createSeatAdmissions,
  createSeatSnapshot,
  createWorkerLease,
  runFabricRoutingSlice,
  selectRoute,
  validateFabricRoutingSlice,
  validateFabricWorkload,
  validateInventedSeatRegistry,
  validateRouteSelection,
  validateSeatAdmission,
  validateSeatSnapshot,
  validateWorkerLease,
  verifyFabricRoutingSlice,
  verifyRouteSelection,
  verifySeatAdmission,
  verifySeatSnapshot,
  verifyWorkerLease,
  workerLeaseStateAt,
} from '../fabric_runtime.mjs';
import { runVerticalSlice } from '../vertical_slice.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const REGISTRY_PATH = resolve(HERE, '../fixtures/mp01-invented-seat-registry.json');
const PROFILE_PATH = resolve(HERE, '../fabric-profile-01.json');
const OBSERVATION_PATH = resolve(HERE, '../fixtures/mp01-observation-package.json');

async function fixtures() {
  const [registry, fabricProfile, sourcePackage] = await Promise.all([
    readFile(REGISTRY_PATH, 'utf8').then(JSON.parse),
    readFile(PROFILE_PATH, 'utf8').then(JSON.parse),
    readFile(OBSERVATION_PATH, 'utf8').then(JSON.parse),
  ]);
  return {
    registry,
    fabricProfile,
    bundle: runVerticalSlice(sourcePackage),
  };
}

async function routingFixture(options = {}) {
  const source = await fixtures();
  const slice = runFabricRoutingSlice({ ...source, ...options });
  return { ...source, slice };
}

function assertCode(fn, code) {
  assert.throws(fn, (error) => error instanceof FabricRuntimeError && error.code === code);
}

test('invented seat registry validates without private Estate evidence', async () => {
  const { registry } = await fixtures();
  assert.equal(validateInventedSeatRegistry(registry), registry);
  assert.equal(registry.seats.length, 3);
  assert.equal(registry.seats.every((row) => row.seatId.startsWith('SYN-SEAT-')), true);
});

test('seat snapshot is content-addressed, deterministic, and per-seat only', async () => {
  const { registry } = await fixtures();
  const first = createSeatSnapshot(registry);
  const second = createSeatSnapshot(registry);
  assert.deepEqual(first, second);
  assert.match(first.snapshotId, /^estateseatsnapshot1_[0-9a-f]{64}$/);
  assert.equal(first.memoryAccounting, 'per_seat_only');
  assert.equal(first.aggregateFitAllowed, false);
  assert.equal(validateSeatSnapshot(first), first);
  assert.equal(verifySeatSnapshot(first, registry), first);
});

test('fabric workload binds the admitted MP01 artifact without mission-state mutation', async () => {
  const { bundle } = await fixtures();
  const workload = createFabricWorkload(bundle);
  assert.equal(validateFabricWorkload(workload), workload);
  assert.equal(workload.canonicalMissionStateIdBefore, workload.canonicalMissionStateIdAfter);
  assert.equal(workload.expectedOutputDigest, bundle.taskReceipt.outputDigest);
  assert.equal(workload.effectClass, 'local_artifact_only');
  assert.equal(workload.authority, false);
});

test('default admission denominator admits two seats and refuses the undersized optional seat', async () => {
  const { registry, bundle } = await fixtures();
  const snapshot = createSeatSnapshot(registry);
  const workload = createFabricWorkload(bundle);
  const admissions = createSeatAdmissions(snapshot, workload);
  assert.equal(admissions.length, 3);
  assert.equal(admissions.filter((row) => row.disposition === 'admit').length, 2);
  const optional = admissions.find((row) => row.seatId === 'SYN-SEAT-OPTIONAL-C');
  assert.equal(optional.disposition, 'refuse');
  assert.deepEqual(optional.reasons, ['INSUFFICIENT_INDEPENDENT_SEAT_MEMORY']);
});

test('seat absent from the exact snapshot produces a closed refusal receipt', async () => {
  const { registry, bundle } = await fixtures();
  const snapshot = createSeatSnapshot(registry);
  const workload = createFabricWorkload(bundle);
  const refusal = createSeatAdmission({
    snapshot,
    workload,
    seatId: 'SYN-SEAT-ABSENT-Z',
  });
  assert.equal(refusal.disposition, 'refuse');
  assert.equal(refusal.seatPresent, false);
  assert.deepEqual(refusal.reasons, ['SEAT_NOT_IN_SNAPSHOT']);
  assert.equal(validateSeatAdmission(refusal), refusal);
  assert.equal(verifySeatAdmission(refusal, snapshot, workload), refusal);
});

test('deterministic route selects the resident seat and preserves rejected lineage', async () => {
  const { registry, bundle } = await fixtures();
  const snapshot = createSeatSnapshot(registry);
  const workload = createFabricWorkload(bundle);
  const admissions = createSeatAdmissions(snapshot, workload);
  const route = selectRoute({ snapshot, workload, admissions });
  assert.equal(route.selectedSeatId, 'SYN-SEAT-RESIDENT-A');
  assert.equal(route.selectionPolicy, 'resident_then_fallback_then_optional_lexical');
  assert.equal(route.candidateAdmissionIds.length, 2);
  assert.equal(route.rejectedAdmissionIds.length, 1);
  assert.equal(route.memoryAggregationUsed, false);
  assert.equal(route.terminalReceipt.status, 'pending_execution');
  assert.equal(validateRouteSelection(route), route);
  assert.equal(verifyRouteSelection(route, snapshot, workload, admissions), route);
});

test('explicit admitted fallback route remains deterministic', async () => {
  const { registry, bundle } = await fixtures();
  const snapshot = createSeatSnapshot(registry);
  const workload = createFabricWorkload(bundle);
  const admissions = createSeatAdmissions(snapshot, workload);
  const route = selectRoute({
    snapshot,
    workload,
    admissions,
    preferredSeatId: 'SYN-SEAT-FALLBACK-B',
  });
  assert.equal(route.selectedSeatId, 'SYN-SEAT-FALLBACK-B');
  assert.equal(route.selectionPolicy, 'explicit_admitted_seat');
  assert.equal(verifyRouteSelection(route, snapshot, workload, admissions), route);
});

test('explicit selection refuses an unadmitted optional seat', async () => {
  const { registry, bundle } = await fixtures();
  const snapshot = createSeatSnapshot(registry);
  const workload = createFabricWorkload(bundle);
  const admissions = createSeatAdmissions(snapshot, workload);
  assertCode(
    () => selectRoute({
      snapshot,
      workload,
      admissions,
      preferredSeatId: 'SYN-SEAT-OPTIONAL-C',
    }),
    'PREFERRED_SEAT_NOT_ADMITTED',
  );
});

test('independent seat memory is never summed into one fit value', async () => {
  const { registry, bundle } = await fixtures();
  for (const seat of registry.seats) seat.acceleratorMemoryMiB = 9000;
  const snapshot = createSeatSnapshot(registry);
  const workload = createFabricWorkload(bundle);
  const admissions = createSeatAdmissions(snapshot, workload);
  assert.equal(admissions.every((row) => row.disposition === 'refuse'), true);
  assert.equal(admissions.every((row) => row.reasons.includes('INSUFFICIENT_INDEPENDENT_SEAT_MEMORY')), true);
  assertCode(() => selectRoute({ snapshot, workload, admissions }), 'NO_QUALIFIED_ROUTE');
});

test('runtime drift refuses only the affected seat', async () => {
  const { registry, bundle } = await fixtures();
  registry.seats.find((row) => row.seatId === 'SYN-SEAT-FALLBACK-B').runtimeVersion = 'synthetic-local-executor/2.0.0';
  const snapshot = createSeatSnapshot(registry);
  const workload = createFabricWorkload(bundle);
  const admissions = createSeatAdmissions(snapshot, workload);
  const fallback = admissions.find((row) => row.seatId === 'SYN-SEAT-FALLBACK-B');
  assert.equal(fallback.disposition, 'refuse');
  assert.equal(fallback.reasons.includes('RUNTIME_VERSION_MISMATCH'), true);
  assert.equal(selectRoute({ snapshot, workload, admissions }).selectedSeatId, 'SYN-SEAT-RESIDENT-A');
});

test('model or executable drift refuses the affected seat', async () => {
  const { registry, bundle } = await fixtures();
  registry.seats[0].modelOrExecutableDigests = ['4'.repeat(64)];
  const snapshot = createSeatSnapshot(registry);
  const workload = createFabricWorkload(bundle);
  const admission = createSeatAdmission({ snapshot, workload, seatId: registry.seats[0].seatId });
  assert.equal(admission.disposition, 'refuse');
  assert.equal(admission.reasons.includes('MODEL_OR_EXECUTABLE_NOT_ADMITTED'), true);
});

test('verifier drift refuses the affected seat', async () => {
  const { registry, bundle } = await fixtures();
  registry.seats[0].verifierIds = ['SYN-VERIFIER-OTHER-02'];
  const snapshot = createSeatSnapshot(registry);
  const workload = createFabricWorkload(bundle);
  const admission = createSeatAdmission({ snapshot, workload, seatId: registry.seats[0].seatId });
  assert.equal(admission.disposition, 'refuse');
  assert.equal(admission.reasons.includes('VERIFIER_NOT_ADMITTED'), true);
});

test('inaccessible resident seat deterministically falls back without topology law', async () => {
  const { registry, bundle } = await fixtures();
  registry.seats.find((row) => row.seatId === 'SYN-SEAT-RESIDENT-A').state = 'inaccessible';
  const snapshot = createSeatSnapshot(registry);
  const workload = createFabricWorkload(bundle);
  const admissions = createSeatAdmissions(snapshot, workload);
  const route = selectRoute({ snapshot, workload, admissions });
  assert.equal(route.selectedSeatId, 'SYN-SEAT-FALLBACK-B');
  assert.equal(route.rejectedAdmissionIds.length, 2);
});

test('route selection refuses a silently shortened admission denominator', async () => {
  const { registry, bundle } = await fixtures();
  const snapshot = createSeatSnapshot(registry);
  const workload = createFabricWorkload(bundle);
  const admissions = createSeatAdmissions(snapshot, workload);
  admissions.pop();
  assertCode(
    () => selectRoute({ snapshot, workload, admissions }),
    'SEAT_ADMISSION_DENOMINATOR_INVALID',
  );
});

test('route receipt cannot claim pooled memory', async () => {
  const { slice } = await routingFixture();
  const changed = structuredClone(slice.routeSelection);
  changed.memoryAggregationUsed = true;
  assertCode(() => validateRouteSelection(changed), 'ROUTE_SELECTION_MEMORY_INVALID');
});

test('route receipt cannot invent terminal execution evidence', async () => {
  const { slice } = await routingFixture();
  const changed = structuredClone(slice.routeSelection);
  changed.terminalReceipt.status = 'completed';
  changed.terminalReceipt.currentReceiptId = 'invented-success';
  assertCode(() => validateRouteSelection(changed), 'ROUTE_SELECTION_TERMINAL_INVALID');
});

test('worker lease is finite, route-bound, and expires after its terminal step', async () => {
  const { slice } = await routingFixture();
  const lease = slice.workerLease;
  assert.equal(validateWorkerLease(lease), lease);
  assert.equal(verifyWorkerLease(lease, slice.routeSelection), lease);
  assert.equal(workerLeaseStateAt(lease, lease.expiresAtStep), 'active');
  assert.equal(workerLeaseStateAt(lease, lease.expiresAtStep + 1), 'expired');
  assert.equal(lease.releaseEvidenceRequired, true);
  assert.equal(lease.completionAuthority, false);
});

test('worker lease cannot widen its expiry after identity issuance', async () => {
  const { slice } = await routingFixture();
  const changed = structuredClone(slice.workerLease);
  changed.expiresAtStep += 1;
  assertCode(() => validateWorkerLease(changed), 'WORKER_LEASE_INVALID');
});

test('worker lease cannot move to another seat', async () => {
  const { slice } = await routingFixture();
  const changed = createWorkerLease({ routeSelection: slice.routeSelection });
  changed.seatId = 'SYN-SEAT-FALLBACK-B';
  assertCode(
    () => verifyWorkerLease(changed, slice.routeSelection),
    'WORKER_LEASE_ID_INVALID',
  );
});

test('full routing slice verifies and keeps canonical MP01 state unchanged', async () => {
  const { registry, fabricProfile, bundle, slice } = await routingFixture();
  assert.equal(validateFabricRoutingSlice(slice), slice);
  const verification = verifyFabricRoutingSlice(slice, { registry, fabricProfile, bundle });
  assert.equal(verification.status, 'PASS');
  assert.equal(verification.canonicalStateUnchanged, true);
  assert.equal(verification.memoryAggregationUsed, false);
  assert.equal(verification.executionClaimed, false);
  assert.equal(verification.completionClaimed, false);
  assert.equal(verification.authority, 'none');
});

test('repeated routing slices are byte-equivalent', async () => {
  const source = await fixtures();
  const first = runFabricRoutingSlice(source);
  const second = runFabricRoutingSlice(source);
  assert.deepEqual(first, second);
  assert.equal(first.routingSliceId, second.routingSliceId);
});

test('routing slice cannot claim canonical-state mutation', async () => {
  const { slice } = await routingFixture();
  const changed = structuredClone(slice);
  changed.canonicalMissionStateIdAfterRouting = 'another-state';
  assertCode(() => validateFabricRoutingSlice(changed), 'FABRIC_ROUTING_STATE_MUTATION');
});

test('routing slice cannot claim execution or accepted completion', async () => {
  for (const key of ['executionStarted', 'completionAccepted']) {
    const { slice } = await routingFixture();
    slice[key] = true;
    assertCode(() => validateFabricRoutingSlice(slice), 'FABRIC_ROUTING_CLAIM_INVALID');
  }
});

test('private physical identifiers fail the invented public registry boundary', async () => {
  const { registry } = await fixtures();
  registry.seats[0].hostIdentityClass = 'synthetic-octo-w01';
  assertCode(
    () => validateInventedSeatRegistry(registry),
    'PRIVATE_EVIDENCE_BOUNDARY_INVALID',
  );
});

test('snapshot content tampering breaks its identity', async () => {
  const { registry } = await fixtures();
  const snapshot = createSeatSnapshot(registry);
  snapshot.seats[0].acceleratorMemoryMiB += 1;
  assertCode(() => validateSeatSnapshot(snapshot), 'SEAT_SNAPSHOT_ID_INVALID');
});
