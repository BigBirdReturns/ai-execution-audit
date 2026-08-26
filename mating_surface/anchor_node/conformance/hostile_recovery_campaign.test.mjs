import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { runFaultWorkerCampaign } from '../fault_worker_campaign.mjs';
import {
  HostileRecoveryError,
  buildDerivedProjections,
  renderAfterActionHtml,
  runConflictingAuthorityReconciliation,
  runHostileRecoveryCampaign,
  runInterfaceDriftRefusal,
  runProjectionDestructionRebuild,
  verifyHostileRecoveryCampaign,
} from '../hostile_recovery_campaign.mjs';
import { runVerticalSlice } from '../vertical_slice.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const FIXTURE = resolve(HERE, '../fixtures/mp01-observation-package.json');

async function bundle() {
  const source = JSON.parse(await readFile(FIXTURE, 'utf8'));
  return runVerticalSlice(source);
}

async function campaignInputs() {
  const sourceBundle = await bundle();
  const faultCampaign = runFaultWorkerCampaign(sourceBundle);
  return { sourceBundle, faultCampaign };
}

function clone(value) {
  return structuredClone(value);
}

function assertCode(fn, code) {
  assert.throws(fn, (error) => error instanceof HostileRecoveryError && error.code === code);
}

test('conflicting returning authority remains human-required and does not mutate canonical state', async () => {
  const sourceBundle = await bundle();
  const receipt = runConflictingAuthorityReconciliation(sourceBundle);
  assert.equal(receipt.status, 'human_required');
  assert.equal(receipt.reconciliation.status, 'human_required');
  assert.equal(receipt.canonicalStateMutated, false);
  assert.equal(receipt.canonicalMissionStateIdBefore, sourceBundle.missionStateAfter.missionStateId);
  assert.equal(receipt.canonicalMissionStateIdAfter, sourceBundle.missionStateAfter.missionStateId);
  assert.equal(receipt.authority, false);
});

test('moved approved interface control refuses without interaction or post-state claim', () => {
  const receipt = runInterfaceDriftRefusal();
  assert.equal(receipt.disposition, 'refuse');
  assert.equal(receipt.reason, 'INTERFACE_DRIFT');
  assert.equal(receipt.interactionPerformed, false);
  assert.equal(receipt.postStateClaimed, false);
  assert.equal(receipt.authority, false);
});

test('graph, query, and cache projections rebuild from canonical state exactly', async () => {
  const sourceBundle = await bundle();
  const result = runProjectionDestructionRebuild(sourceBundle);
  assert.equal(result.projections.canonicalStateOwner, false);
  assert.equal(result.receipt.status, 'PASS');
  assert.equal(result.receipt.byteEquivalent, true);
  assert.equal(result.receipt.canonicalStateMutated, false);
  assert.equal(result.receipt.canonicalMissionStateIdBefore, sourceBundle.missionStateAfter.missionStateId);
  assert.equal(result.receipt.canonicalMissionStateIdAfter, sourceBundle.missionStateAfter.missionStateId);
  assert.deepEqual(
    buildDerivedProjections(sourceBundle.missionStateAfter),
    result.projections,
  );
});

test('after-action HTML is static, deterministic, and contains the retained refusal states', async () => {
  const { sourceBundle, faultCampaign } = await campaignInputs();
  const first = runHostileRecoveryCampaign(sourceBundle, faultCampaign);
  const second = runHostileRecoveryCampaign(sourceBundle, faultCampaign);
  assert.equal(first.html, second.html);
  assert.match(first.html, /human_required/);
  assert.match(first.html, /refuse: INTERFACE_DRIFT/);
  assert.match(first.html, /Duplicate replay refused: true/);
  assert.match(first.html, /Worker loss recovered: true/);
  assert.doesNotMatch(first.html, /<script/i);
  assert.doesNotMatch(first.html, /https?:\/\//i);
  assert.equal(first.campaign.afterAction.generatedFromReceiptsOnly, true);
  assert.equal(first.campaign.afterAction.hiddenBrowserState, false);
});

test('full hostile-recovery campaign verifies deterministically', async () => {
  const { sourceBundle, faultCampaign } = await campaignInputs();
  const result = runHostileRecoveryCampaign(sourceBundle, faultCampaign);
  const receipt = verifyHostileRecoveryCampaign(
    result.campaign,
    result.html,
    sourceBundle,
    faultCampaign,
  );
  assert.equal(receipt.status, 'PASS');
  assert.equal(receipt.authorityConflictHeld, true);
  assert.equal(receipt.interfaceDriftRefused, true);
  assert.equal(receipt.projectionRebuilt, true);
  assert.equal(receipt.afterActionReceiptOnly, true);
  assert.equal(receipt.externalServiceCalls, 0);
  assert.equal(receipt.authority, 'none');
});

test('repeated combined campaigns are byte-equivalent', async () => {
  const { sourceBundle, faultCampaign } = await campaignInputs();
  const first = runHostileRecoveryCampaign(sourceBundle, faultCampaign);
  const second = runHostileRecoveryCampaign(sourceBundle, faultCampaign);
  assert.deepEqual(first.campaign, second.campaign);
  assert.equal(first.html, second.html);
});

test('authority conflict cannot be silently converted into continuous authority', async () => {
  const { sourceBundle, faultCampaign } = await campaignInputs();
  const result = runHostileRecoveryCampaign(sourceBundle, faultCampaign);
  const tampered = clone(result.campaign);
  tampered.authorityConflict.status = 'continuous_authority';
  assertCode(
    () => verifyHostileRecoveryCampaign(tampered, result.html, sourceBundle, faultCampaign),
    'HOSTILE_CAMPAIGN_INVALID',
  );
});

test('interface drift cannot be followed by an invented interaction', async () => {
  const { sourceBundle, faultCampaign } = await campaignInputs();
  const result = runHostileRecoveryCampaign(sourceBundle, faultCampaign);
  const tampered = clone(result.campaign);
  tampered.interfaceDrift.interactionPerformed = true;
  assertCode(
    () => verifyHostileRecoveryCampaign(tampered, result.html, sourceBundle, faultCampaign),
    'HOSTILE_CAMPAIGN_INVALID',
  );
});

test('projection rebuild cannot claim canonical-state mutation', async () => {
  const { sourceBundle, faultCampaign } = await campaignInputs();
  const result = runHostileRecoveryCampaign(sourceBundle, faultCampaign);
  const tampered = clone(result.campaign);
  tampered.projectionRebuild.receipt.canonicalStateMutated = true;
  assertCode(
    () => verifyHostileRecoveryCampaign(tampered, result.html, sourceBundle, faultCampaign),
    'HOSTILE_CAMPAIGN_INVALID',
  );
});

test('after-action HTML tampering is refused', async () => {
  const { sourceBundle, faultCampaign } = await campaignInputs();
  const result = runHostileRecoveryCampaign(sourceBundle, faultCampaign);
  assertCode(
    () => verifyHostileRecoveryCampaign(
      result.campaign,
      result.html.replace('human_required', 'continuous_authority'),
      sourceBundle,
      faultCampaign,
    ),
    'AFTER_ACTION_HTML_MISMATCH',
  );
});

test('campaign cannot carry authority or external calls', async () => {
  const { sourceBundle, faultCampaign } = await campaignInputs();
  const result = runHostileRecoveryCampaign(sourceBundle, faultCampaign);
  const tampered = clone(result.campaign);
  tampered.authority = true;
  assertCode(
    () => verifyHostileRecoveryCampaign(tampered, result.html, sourceBundle, faultCampaign),
    'HOSTILE_CAMPAIGN_INVALID',
  );
});

test('rendered after-action data escapes hostile text', () => {
  const html = renderAfterActionHtml({
    canonicalMissionStateId: '<img src=x onerror=alert(1)>',
    taskReceiptId: '<script>alert(1)</script>',
    duplicateReplayRefused: true,
    workerLossRecovered: true,
    authorityConflictStatus: 'human_required',
    interfaceDisposition: 'refuse',
    interfaceReason: 'INTERFACE_DRIFT',
    projectionRebuildStatus: 'PASS',
    unresolvedObligations: ['<script>bad()</script>'],
  });
  assert.doesNotMatch(html, /<script>alert\(1\)<\/script>/);
  assert.doesNotMatch(html, /<img src=x/);
  assert.match(html, /&lt;script&gt;bad\(\)&lt;\/script&gt;/);
});
