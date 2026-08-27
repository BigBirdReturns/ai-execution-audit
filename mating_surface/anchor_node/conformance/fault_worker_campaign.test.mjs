import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import {
  FaultWorkerCampaignError,
  runFaultWorkerCampaign,
  runWorkerLossRecovery,
  verifyFaultWorkerCampaign,
  verifyWorkerLossRecovery,
} from '../fault_worker_campaign.mjs';
import { runVerticalSlice } from '../vertical_slice.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const FIXTURE = resolve(HERE, '../fixtures/mp01-observation-package.json');

async function bundle() {
  const source = JSON.parse(await readFile(FIXTURE, 'utf8'));
  return runVerticalSlice(source);
}

function clone(value) {
  return structuredClone(value);
}

function assertCode(fn, code) {
  assert.throws(fn, (error) => error instanceof FaultWorkerCampaignError && error.code === code);
}

test('transport campaign exercises duplicate, buffering, delay, and complete closure', async () => {
  const campaign = runFaultWorkerCampaign(await bundle());
  assert.equal(campaign.faultRun.metrics.duplicateExtraCopies, 1);
  assert.equal(campaign.faultRun.metrics.bufferedPackets, 1);
  assert.equal(campaign.faultRun.metrics.delayedPackets, 1);
  assert.equal(campaign.faultRun.metrics.pendingDelayedPackets, 0);
  assert.equal(campaign.faultRun.metrics.pendingBufferedPackets, 0);
  assert.equal(campaign.faultFrame.status, 'complete');
  assert.equal(campaign.faultVerification.status, 'pass');
});

test('duplicate proposal delivery creates one accept and one replay refusal', async () => {
  const campaign = runFaultWorkerCampaign(await bundle());
  assert.equal(campaign.duplicateReceiverReceipts.length, 2);
  assert.equal(campaign.duplicateReceiverReceipts[0].disposition, 'accept');
  assert.equal(campaign.duplicateReceiverReceipts[0].reason, 'MESSAGE_ACCEPTED');
  assert.equal(campaign.duplicateReceiverReceipts[1].disposition, 'refuse');
  assert.equal(campaign.duplicateReceiverReceipts[1].reason, 'MESSAGE_REPLAY');
});

test('worker loss yields one accepted fallback completion', async () => {
  const recovery = runWorkerLossRecovery(await bundle());
  assert.equal(recovery.workers.find((row) => row.workerId === 'SYN-WORKER-PRIMARY').state, 'EXITED');
  assert.equal(recovery.workers.find((row) => row.workerId === 'SYN-WORKER-FALLBACK').state, 'ACTIVE');
  assert.equal(recovery.acceptedCompletionCount, 1);
  assert.equal(recovery.completionReceipt.workerId, 'SYN-WORKER-FALLBACK');
  assert.equal(recovery.completionReceipt.leaseGeneration, 2);
  assert.equal(recovery.terminalState, 'completed');
  assert.equal(recovery.operatorInterventions, 0);
});

test('stale primary and duplicate fallback completions are refused', async () => {
  const recovery = runWorkerLossRecovery(await bundle());
  assert.deepEqual(
    recovery.refusals.map((row) => row.reason).sort(),
    ['DUPLICATE_TERMINAL_COMPLETION', 'STALE_OR_EXITED_WORKER_LEASE'],
  );
});

test('worker recovery replays exactly', async () => {
  const sourceBundle = await bundle();
  const recovery = runWorkerLossRecovery(sourceBundle);
  assert.equal(verifyWorkerLossRecovery(recovery, sourceBundle), recovery);
});

test('full fault-worker campaign verifies deterministically', async () => {
  const sourceBundle = await bundle();
  const campaign = runFaultWorkerCampaign(sourceBundle);
  const receipt = verifyFaultWorkerCampaign(campaign, sourceBundle);
  assert.equal(receipt.status, 'PASS');
  assert.equal(receipt.duplicateReplayRefused, true);
  assert.equal(receipt.workerLossRecovered, true);
  assert.equal(receipt.acceptedCompletionCount, 1);
  assert.equal(receipt.pendingFaultState, 0);
  assert.equal(receipt.externalServiceCalls, 0);
  assert.equal(receipt.authority, 'none');
});

test('repeated fault-worker campaigns are identical', async () => {
  const sourceBundle = await bundle();
  assert.deepEqual(runFaultWorkerCampaign(sourceBundle), runFaultWorkerCampaign(sourceBundle));
});

test('campaign cannot inflate accepted completion count', async () => {
  const sourceBundle = await bundle();
  const campaign = clone(runFaultWorkerCampaign(sourceBundle));
  campaign.workerRecovery.acceptedCompletionCount = 2;
  assertCode(() => verifyFaultWorkerCampaign(campaign, sourceBundle), 'WORKER_RECOVERY_INVALID');
});

test('campaign cannot erase stale completion refusal', async () => {
  const sourceBundle = await bundle();
  const campaign = clone(runFaultWorkerCampaign(sourceBundle));
  campaign.workerRecovery.refusals = campaign.workerRecovery.refusals.filter(
    (row) => row.reason !== 'STALE_OR_EXITED_WORKER_LEASE',
  );
  assertCode(() => verifyFaultWorkerCampaign(campaign, sourceBundle), 'WORKER_RECOVERY_INVALID');
});

test('campaign cannot carry authority or external calls', async () => {
  const sourceBundle = await bundle();
  const campaign = clone(runFaultWorkerCampaign(sourceBundle));
  campaign.authority = true;
  assertCode(() => verifyFaultWorkerCampaign(campaign, sourceBundle), 'CAMPAIGN_INVALID');
});
