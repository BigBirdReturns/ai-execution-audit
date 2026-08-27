import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import {
  FabricProfileError,
  fabricProfileReceipt,
  validateFabricProfile,
} from '../validate_fabric_profile.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const PROFILE = resolve(HERE, '../fabric-profile-01.json');

async function loadProfile() {
  return JSON.parse(await readFile(PROFILE, 'utf8'));
}

function assertCode(fn, code) {
  assert.throws(fn, (error) => error instanceof FabricProfileError && error.code === code);
}

test('Estate fabric profile validates as a closed candidate without authority', async () => {
  const profile = await loadProfile();
  assert.equal(validateFabricProfile(profile), profile);
  const receipt = fabricProfileReceipt(profile);
  assert.equal(receipt.status, 'PASS');
  assert.equal(receipt.authority, 'none');
  assert.equal(receipt.predecessorCommit, 'f70645a70f40ad0cbe6bad1e4e665116ad4230b1');
  assert.equal(receipt.estateAuthorityCommit, '819e17d6a49b38855fb417dabcbe900b62798747');
  assert.equal(receipt.contractObjectCount, 8);
  assert.equal(receipt.routeBindingCount, 17);
  assert.equal(receipt.hostileScenarioCount, 15);
  assert.equal(receipt.evidenceTierCount, 4);
  assert.match(receipt.sha256, /^[0-9a-f]{64}$/);
});

test('fabric contract cannot self-promote', async () => {
  const profile = await loadProfile();
  profile.status = 'qualified';
  assertCode(() => validateFabricProfile(profile), 'FABRIC_PROFILE_STATUS_INVALID');
});

test('fabric adapter cannot acquire mission-state or field effect', async () => {
  const profile = await loadProfile();
  profile.missionStateEffect = 'mutated';
  assertCode(() => validateFabricProfile(profile), 'FABRIC_PROFILE_EFFECT_INVALID');
});

test('admitted MP01 predecessor is exact and immutable', async () => {
  const profile = await loadProfile();
  profile.predecessors.missionProfile.commit = '0'.repeat(40);
  assertCode(() => validateFabricProfile(profile), 'FABRIC_PREDECESSOR_INVALID');
});

test('Estate authority coordinate is exact and private-evidence custody stays digest-only', async () => {
  const profile = await loadProfile();
  profile.predecessors.estateAuthority.evidenceBodies = 'public_copy_allowed';
  assertCode(() => validateFabricProfile(profile), 'FABRIC_PREDECESSOR_INVALID');
});

test('public fixtures cannot admit private evidence bodies, hosts, paths, or credentials', async () => {
  for (const key of [
    'privateEvidenceBodiesAllowed',
    'privateHostnamesAllowed',
    'privatePathsAllowed',
    'operationalCredentialsRequired',
  ]) {
    const profile = await loadProfile();
    profile.publicFixturePolicy[key] = true;
    assertCode(() => validateFabricProfile(profile), 'PUBLIC_FIXTURE_POLICY_INVALID');
  }
});

test('fabric contract object denominator cannot shrink or reorder', async () => {
  const profile = await loadProfile();
  profile.contractObjects.reverse();
  assertCode(() => validateFabricProfile(profile), 'FABRIC_CONTRACT_OBJECTS_INVALID');
});

test('independent seat memory cannot be pooled for route fit', async () => {
  const profile = await loadProfile();
  profile.seatSemantics.memoryAggregation = 'sum_all_visible_vram';
  assertCode(() => validateFabricProfile(profile), 'SEAT_SEMANTICS_INVALID');
});

test('GPU presence cannot become seat admission', async () => {
  const profile = await loadProfile();
  profile.seatSemantics.gpuPresenceImpliesAdmission = true;
  assertCode(() => validateFabricProfile(profile), 'SEAT_SEMANTICS_INVALID');
});

test('observed topology cannot become constitutional state', async () => {
  const profile = await loadProfile();
  profile.seatSemantics.topologyRole = 'permanent_constitution';
  assertCode(() => validateFabricProfile(profile), 'SEAT_SEMANTICS_INVALID');
});

test('optional burst capacity cannot become resident-floor dependency', async () => {
  const profile = await loadProfile();
  profile.seatSemantics.optionalSeatRequiredForResidentContinuity = true;
  assertCode(() => validateFabricProfile(profile), 'SEAT_SEMANTICS_INVALID');
});

test('route identity denominator cannot omit verifier, output, or terminal receipt', async () => {
  for (const field of ['independent_verifier_identity', 'output_digest', 'terminal_receipt']) {
    const profile = await loadProfile();
    profile.routeBinding = profile.routeBinding.filter((row) => row !== field);
    assertCode(() => validateFabricProfile(profile), 'ROUTE_BINDING_INVALID');
  }
});

test('first fabric vertical slice remains local, zero-service, and non-mutating', async () => {
  const profile = await loadProfile();
  profile.firstVerticalSlice.missionStateMutation = true;
  assertCode(() => validateFabricProfile(profile), 'FABRIC_VERTICAL_SLICE_INVALID');
});

test('hostile fabric qualification denominator cannot silently shrink', async () => {
  const profile = await loadProfile();
  profile.hostileQualification.pop();
  assertCode(() => validateFabricProfile(profile), 'FABRIC_HOSTILE_SCENARIOS_INVALID');
});

test('evidence tiers cannot promote physical or representative-operator status', async () => {
  const physical = await loadProfile();
  physical.evidenceTiers[2].status = 'qualified';
  assertCode(() => validateFabricProfile(physical), 'EVIDENCE_TIERS_INVALID');

  const operator = await loadProfile();
  operator.evidenceTiers[3].status = 'qualified';
  assertCode(() => validateFabricProfile(operator), 'EVIDENCE_TIERS_INVALID');
});

test('fabric claims cannot manufacture synthetic, physical, operator, mission, or command authority', async () => {
  for (const key of [
    'syntheticFabricQualified',
    'physicalEstateQualified',
    'representativeOperatorQualified',
    'missionAuthorityFromHardware',
    'commandAuthorityGranted',
    'operationalC2Claim',
    'fieldNetworkClaim',
    'weaponsOrEffectorCapability',
  ]) {
    const profile = await loadProfile();
    profile.claimBoundary[key] = true;
    assertCode(() => validateFabricProfile(profile), 'FABRIC_CLAIM_BOUNDARY_INVALID');
  }
});

test('private physical identifiers fail the public contract boundary', async () => {
  const profile = await loadProfile();
  profile.purpose += ' OCTO-W01';
  assertCode(() => validateFabricProfile(profile), 'FABRIC_CLAIM_BOUNDARY_INVALID');
});

test('unexpected fields fail closed', async () => {
  const profile = await loadProfile();
  profile.currentPhysicalTopology = ['private-seat-1'];
  assertCode(() => validateFabricProfile(profile), 'FABRIC_PROFILE_FIELDS_INVALID');
});
