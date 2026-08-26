import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import {
  LatticeMembraneError,
  projectVerticalSliceToLattice,
  reconcileInboundCandidate,
  validateInboundLatticeEnvelope,
  validateOutboundLatticeEnvelope,
  verifyLatticeRemoval,
} from '../lattice_membrane.mjs';
import { runVerticalSlice } from '../vertical_slice.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const OBSERVATIONS = resolve(HERE, '../fixtures/mp01-observation-package.json');
const INBOUND = resolve(HERE, '../fixtures/mp01-lattice-inbound-candidate.json');

async function json(path) {
  return JSON.parse(await readFile(path, 'utf8'));
}

async function bundle() {
  return runVerticalSlice(await json(OBSERVATIONS));
}

function clone(value) {
  return structuredClone(value);
}

function assertCode(fn, code) {
  assert.throws(fn, (error) => error instanceof LatticeMembraneError && error.code === code);
}

test('outbound contract simulator projects entity, task, and object primitives', async () => {
  const run = await bundle();
  const envelope = projectVerticalSliceToLattice(run);
  assert.equal(validateOutboundLatticeEnvelope(envelope), envelope);
  assert.equal(envelope.adapterMode, 'contract_simulator_only');
  assert.equal(envelope.canonicalStateOwner, false);
  assert.equal(envelope.operationalCredentials, 0);
  assert.equal(envelope.entities.length, 2);
  assert.equal(envelope.tasks.length, 1);
  assert.equal(envelope.objects.length, 1);
});

test('outbound projections preserve synthetic external identifiers', async () => {
  const envelope = projectVerticalSliceToLattice(await bundle());
  assert.deepEqual(
    envelope.entities.map((row) => row.externalId).sort(),
    ['SYN-DEPOT-BRAVO', 'SYN-TRACK-ALPHA'],
  );
});

test('no projected primitive carries authority', async () => {
  const envelope = projectVerticalSliceToLattice(await bundle());
  for (const row of [...envelope.entities, ...envelope.tasks, ...envelope.objects]) {
    assert.equal(row.authority, false);
  }
});

test('removing the Lattice contract simulator preserves canonical local state', async () => {
  const run = await bundle();
  const envelope = projectVerticalSliceToLattice(run);
  const receipt = verifyLatticeRemoval(run, envelope);
  assert.equal(receipt.status, 'PASS');
  assert.equal(receipt.localContinuityPreserved, true);
  assert.equal(receipt.canonicalMissionStateIdBeforeRemoval, run.missionStateAfter.missionStateId);
  assert.equal(receipt.canonicalMissionStateIdAfterRemoval, run.missionStateAfter.missionStateId);
  assert.equal(receipt.latticeRequired, false);
});

test('inbound candidate remains external and creates a human review obligation', async () => {
  const run = await bundle();
  const inbound = await json(INBOUND);
  assert.equal(validateInboundLatticeEnvelope(inbound), inbound);
  const receipt = reconcileInboundCandidate(run.missionStateAfter, inbound);
  assert.equal(receipt.status, 'human_required');
  assert.equal(receipt.canonicalStateMutated, false);
  assert.equal(receipt.canonicalMissionStateIdBefore, run.missionStateAfter.missionStateId);
  assert.equal(receipt.canonicalMissionStateIdAfter, run.missionStateAfter.missionStateId);
  assert.equal(receipt.obligation.claimKind, 'obligation');
  assert.equal(receipt.obligation.authority, false);
});

test('outbound envelope cannot claim canonical-state ownership', async () => {
  const envelope = projectVerticalSliceToLattice(await bundle());
  const tampered = clone(envelope);
  tampered.canonicalStateOwner = true;
  assertCode(() => validateOutboundLatticeEnvelope(tampered), 'LATTICE_CANONICAL_OWNERSHIP_INVALID');
});

test('outbound task cannot widen itself beyond local artifact creation', async () => {
  const envelope = projectVerticalSliceToLattice(await bundle());
  const tampered = clone(envelope);
  tampered.tasks[0].effectClass = 'external_effect';
  assertCode(() => validateOutboundLatticeEnvelope(tampered), 'OUTBOUND_TASK_INVALID');
});

test('inbound envelope cannot carry authority', async () => {
  const inbound = await json(INBOUND);
  inbound.authority = true;
  assertCode(() => validateInboundLatticeEnvelope(inbound), 'LATTICE_AUTHORITY_INVALID');
});

test('inbound envelope cannot require operational credentials', async () => {
  const inbound = await json(INBOUND);
  inbound.operationalCredentials = 1;
  assertCode(() => validateInboundLatticeEnvelope(inbound), 'INBOUND_ENVELOPE_INVALID');
});

test('projection and removal verification are deterministic', async () => {
  const run = await bundle();
  const first = projectVerticalSliceToLattice(run);
  const second = projectVerticalSliceToLattice(run);
  assert.deepEqual(first, second);
  assert.deepEqual(verifyLatticeRemoval(run, first), verifyLatticeRemoval(run, second));
});
