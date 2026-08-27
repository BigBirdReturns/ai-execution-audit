import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import {
  FabricExecutionError,
  createPrimarySeatLossEvidence,
  deriveTerminalCampaignSchedule,
  runFabricExecutionCampaign,
  verifyFabricRun,
} from '../fabric_execution.mjs';
import { runFabricRoutingSlice } from '../fabric_runtime.mjs';
import { runVerticalSlice } from '../vertical_slice.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const REGISTRY_PATH = resolve(HERE, '../fixtures/mp01-invented-seat-registry.json');
const PROFILE_PATH = resolve(HERE, '../fabric-profile-01.json');
const OBSERVATION_PATH = resolve(HERE, '../fixtures/mp01-observation-package.json');

async function baseInputs() {
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

function assertCode(fn, code) {
  assert.throws(fn, (error) => error instanceof FabricExecutionError && error.code === code);
}

test('default terminal schedule preserves the admitted campaign identities', async () => {
  const inputs = await baseInputs();
  const routingSlice = runFabricRoutingSlice(inputs);
  const schedule = deriveTerminalCampaignSchedule(routingSlice.workerLease);
  assert.deepEqual(schedule, {
    lossAtStep: 22,
    fallbackLeaseIssuedAtStep: 23,
    fallbackLeaseDurationSteps: 6,
    stalePrimaryAtStep: 24,
    wrongOutputAtStep: 24,
    unverifiableAtStep: 25,
    acceptedAtStep: 26,
    latePrimaryAtStep: 26,
    duplicateAtStep: 27,
  });
  const run = runFabricExecutionCampaign({ ...inputs, routingSlice });
  assert.equal(
    run.fabricRunId,
    'estatefabricrun1_47aa7c765f482f31c0003f204232f63f31482bddeefc86cde2bda66ebcd5b7b3',
  );
  assert.equal(
    run.acceptedCandidateId,
    'estatecompletioncandidate1_f6b8ec10637903886f7d4d22b97dcae776be2e36f4ece3a17e6f3c8e47c0f227',
  );
});

test('terminal campaign derives every event from a non-default predecessor lease', async () => {
  const inputs = await baseInputs();
  const routingSlice = runFabricRoutingSlice({
    ...inputs,
    leaseIssuedAtStep: 30,
    leaseDurationSteps: 9,
  });
  const schedule = deriveTerminalCampaignSchedule(routingSlice.workerLease);
  assert.deepEqual(schedule, {
    lossAtStep: 34,
    fallbackLeaseIssuedAtStep: 35,
    fallbackLeaseDurationSteps: 6,
    stalePrimaryAtStep: 36,
    wrongOutputAtStep: 36,
    unverifiableAtStep: 37,
    acceptedAtStep: 38,
    latePrimaryAtStep: 40,
    duplicateAtStep: 41,
  });
  const loss = createPrimarySeatLossEvidence({ routingSlice });
  assert.equal(loss.observedAtStep, schedule.lossAtStep);
  const run = runFabricExecutionCampaign({ ...inputs, routingSlice });
  assert.equal(run.primarySeatLossEvidence.observedAtStep, 34);
  assert.equal(run.fallbackWorkerLease.issuedAtStep, 35);
  assert.equal(run.fallbackWorkerLease.expiresAtStep, 41);
  assert.deepEqual(
    run.candidates.map((row) => row.completedAtStep),
    [36, 36, 37, 38, 40, 41],
  );
  const verification = verifyFabricRun(run, { ...inputs, routingSlice });
  assert.equal(verification.status, 'PASS');
  assert.equal(verification.acceptedCompletionCount, 1);
});

test('one-step primary leases still yield a bounded stale, fallback, expiry, and duplicate campaign', async () => {
  const inputs = await baseInputs();
  const routingSlice = runFabricRoutingSlice({
    ...inputs,
    leaseIssuedAtStep: 50,
    leaseDurationSteps: 1,
  });
  const schedule = deriveTerminalCampaignSchedule(routingSlice.workerLease);
  assert.equal(schedule.lossAtStep, 50);
  assert.equal(schedule.fallbackLeaseIssuedAtStep, 51);
  assert.equal(schedule.stalePrimaryAtStep, 51);
  assert.equal(schedule.latePrimaryAtStep > routingSlice.workerLease.expiresAtStep, true);
  const run = runFabricExecutionCampaign({ ...inputs, routingSlice });
  assert.equal(run.acceptedCompletionCount, 1);
  assert.equal(run.refusals.some((row) => row.reasons.includes('LEASE_EXPIRED')), true);
  assert.equal(run.refusals.some((row) => row.reasons.includes('STALE_LEASE_GENERATION')), true);
});

test('terminal campaign refuses a predecessor lease with no representable post-expiry step', async () => {
  const inputs = await baseInputs();
  const routingSlice = runFabricRoutingSlice({
    ...inputs,
    leaseIssuedAtStep: 999_999_999,
    leaseDurationSteps: 1,
  });
  assertCode(
    () => deriveTerminalCampaignSchedule(routingSlice.workerLease),
    'TERMINAL_SCHEDULE_HEADROOM_INVALID',
  );
  assertCode(
    () => runFabricExecutionCampaign({ ...inputs, routingSlice }),
    'TERMINAL_SCHEDULE_HEADROOM_INVALID',
  );
});
