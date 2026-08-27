import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import {
  AnchorNodeError,
  buildCanonicalMissionState,
  createDeterministicModelProposal,
  runVerticalSlice,
  validateSyntheticObservationPackage,
  verifyVerticalSlice,
} from '../vertical_slice.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const FIXTURE = resolve(HERE, '../fixtures/mp01-observation-package.json');

async function loadFixture() {
  return JSON.parse(await readFile(FIXTURE, 'utf8'));
}

function clone(value) {
  return structuredClone(value);
}

function assertCode(fn, code) {
  assert.throws(fn, (error) => error instanceof AnchorNodeError && error.code === code);
}

test('synthetic fixture validates and contains both required observation kinds', async () => {
  const fixture = await loadFixture();
  assert.equal(validateSyntheticObservationPackage(fixture), fixture);
  assert.deepEqual(
    fixture.observations.map((row) => row.kind).sort(),
    ['synthetic_airspace', 'synthetic_logistics'],
  );
});

test('canonical state preserves observations, typed uncertainty, and one open obligation', async () => {
  const state = buildCanonicalMissionState(await loadFixture());
  assert.equal(state.canonical, true);
  assert.equal(state.entities.length, 2);
  assert.equal(state.relationships[0].state, 'candidate');
  assert.equal(state.relationships[0].uncertainty.state, 'UNRESOLVED');
  assert.equal(state.obligations[0].claimKind, 'obligation');
  assert.equal(state.obligations[0].status, 'open');
  assert.equal(state.taskStates.length, 0);
});

test('deterministic model surface emits inference without authority', async () => {
  const proposal = createDeterministicModelProposal(buildCanonicalMissionState(await loadFixture()));
  assert.equal(proposal.claimKind, 'inference');
  assert.equal(proposal.authority, false);
  assert.equal(proposal.modelQualified, false);
  assert.equal(proposal.requestedEffect, 'local_artifact_only');
});

test('vertical slice completes one local non-kinetic task under denied communications', async () => {
  const bundle = runVerticalSlice(await loadFixture());
  assert.equal(bundle.authorityDecision.linkState, 'headquarters_denied');
  assert.equal(bundle.authorityDecision.disposition, 'allow');
  assert.equal(bundle.authorityDecision.localOperatorPresent, true);
  assert.equal(bundle.taskReceipt.effectClass, 'local_artifact_only');
  assert.equal(bundle.taskReceipt.status, 'completed');
  assert.equal(bundle.missionStateAfter.taskStates.length, 1);
  assert.equal(bundle.externalServiceCalls, 0);
  assert.equal(bundle.operationalCredentials, 0);
  assert.equal(bundle.latticeRequired, false);
});

test('detached replay reproduces the complete material state transition', async () => {
  const bundle = runVerticalSlice(await loadFixture());
  const receipt = verifyVerticalSlice(bundle);
  assert.equal(receipt.status, 'PASS');
  assert.equal(receipt.runId, bundle.runId);
  assert.equal(receipt.finalMissionStateId, bundle.missionStateAfter.missionStateId);
  assert.equal(receipt.externalServiceCalls, 0);
  assert.equal(receipt.latticeRequired, false);
});

test('repeated runs are byte-equivalent under canonical JSON semantics', async () => {
  const fixture = await loadFixture();
  const first = runVerticalSlice(fixture);
  const second = runVerticalSlice(fixture);
  assert.deepEqual(first, second);
});

test('missing local operator prevents the proposal from becoming an executable task', async () => {
  const fixture = await loadFixture();
  assertCode(() => runVerticalSlice(fixture, { localOperatorPresent: false }), 'AUTHORITY_NOT_GRANTED');
});

test('expired offline lease prevents task completion', async () => {
  const fixture = await loadFixture();
  assertCode(
    () => runVerticalSlice(fixture, { authorityEvaluationStep: 2, taskStep: 5 }),
    'TASK_LEASE_EXPIRED',
  );
});

test('tampering with source evidence breaks detached replay', async () => {
  const bundle = runVerticalSlice(await loadFixture());
  const tampered = clone(bundle);
  tampered.sourcePackage.observations[0].attributes.motion = 'westbound';
  assertCode(() => verifyVerticalSlice(tampered), 'DETACHED_REPLAY_MISMATCH');
});

test('model output cannot be promoted into authority', async () => {
  const bundle = runVerticalSlice(await loadFixture());
  const tampered = clone(bundle);
  tampered.modelProposal.authority = true;
  assertCode(() => verifyVerticalSlice(tampered), 'MODEL_AUTHORITY_INVALID');
});

test('task effect cannot be widened beyond local artifact creation', async () => {
  const bundle = runVerticalSlice(await loadFixture());
  const tampered = clone(bundle);
  tampered.taskReceipt.effectClass = 'external_effect';
  assertCode(() => verifyVerticalSlice(tampered), 'TASK_EFFECT_INVALID');
});

test('fixture cannot silently become real or mixed custody', async () => {
  const fixture = await loadFixture();
  const tampered = clone(fixture);
  tampered.classification = 'mixed';
  assertCode(() => validateSyntheticObservationPackage(tampered), 'OBSERVATION_CLASSIFICATION_INVALID');
});
