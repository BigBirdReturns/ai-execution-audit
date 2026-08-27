import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import {
  MissionProfileError,
  missionProfileReceipt,
  validateMissionProfile,
} from '../validate_mission_profile.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const PROFILE = resolve(HERE, '../mission-profile-01.json');

async function loadProfile() {
  return JSON.parse(await readFile(PROFILE, 'utf8'));
}

function assertCode(fn, code) {
  assert.throws(fn, (error) => error instanceof MissionProfileError && error.code === code);
}

test('Mission Profile 01 validates without granting authority', async () => {
  const profile = await loadProfile();
  assert.equal(validateMissionProfile(profile), profile);
  const receipt = missionProfileReceipt(profile);
  assert.equal(receipt.status, 'PASS');
  assert.equal(receipt.authority, 'none');
  assert.match(receipt.sha256, /^[0-9a-f]{64}$/);
});

test('candidate design cannot self-promote', async () => {
  const profile = await loadProfile();
  profile.status = 'accepted';
  assertCode(() => validateMissionProfile(profile), 'PROFILE_STATUS_INVALID');
});

test('authority and effects must remain none', async () => {
  const profile = await loadProfile();
  profile.fieldEffect = 'deployed';
  assertCode(() => validateMissionProfile(profile), 'PROFILE_EFFECT_INVALID');
});

test('source base is exact and immutable', async () => {
  const profile = await loadProfile();
  profile.sourceBase.commit = '0'.repeat(40);
  assertCode(() => validateMissionProfile(profile), 'SOURCE_BASE_INVALID');
});

test('claim kinds may not be reordered or silently collapsed', async () => {
  const profile = await loadProfile();
  profile.claimKinds.splice(1, 1);
  assertCode(() => validateMissionProfile(profile), 'CLAIM_KINDS_INVALID');
});

test('model authority invariant cannot be removed', async () => {
  const profile = await loadProfile();
  profile.invariants = profile.invariants.filter((row) => !row.includes('models may propose'));
  assertCode(() => validateMissionProfile(profile), 'INVARIANTS_INVALID');
});

test('Lattice membrane can never own canonical state', async () => {
  const profile = await loadProfile();
  profile.optionalLatticeMembrane.canonicalStateOwner = true;
  assertCode(() => validateMissionProfile(profile), 'LATTICE_MEMBRANE_INVALID');
});

test('Lattice membrane cannot become an operational credential dependency', async () => {
  const profile = await loadProfile();
  profile.optionalLatticeMembrane.operationalCredentialsRequired = true;
  assertCode(() => validateMissionProfile(profile), 'LATTICE_MEMBRANE_INVALID');
});

test('first vertical slice remains zero-service and zero-credential', async () => {
  const profile = await loadProfile();
  profile.firstVerticalSlice.externalServices = 1;
  assertCode(() => validateMissionProfile(profile), 'VERTICAL_SLICE_INVALID');
});

test('hostile qualification denominator cannot silently shrink', async () => {
  const profile = await loadProfile();
  profile.hostileQualification.pop();
  assertCode(() => validateMissionProfile(profile), 'HOSTILE_SCENARIOS_INVALID');
});

test('weapons and operational claims must remain explicitly false', async () => {
  const profile = await loadProfile();
  profile.claimBoundary.weaponsOrEffectorCapability = true;
  assertCode(() => validateMissionProfile(profile), 'CLAIM_BOUNDARY_INVALID');
});

test('unexpected fields fail closed', async () => {
  const profile = await loadProfile();
  profile.marketingClaim = 'field ready';
  assertCode(() => validateMissionProfile(profile), 'PROFILE_FIELDS_INVALID');
});
