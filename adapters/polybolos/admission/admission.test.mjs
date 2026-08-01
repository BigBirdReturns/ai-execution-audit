import assert from 'node:assert/strict';
import { generateKeyPairSync } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import {
  ShapeAdmissionError,
  deriveConfirmationTargetId,
  evaluateMapCoverage,
  prepareConfirmedMap,
  promoteConfirmedMap,
  signMapAttestation,
  translateAdmittedExternal,
  verifyConfirmedMap,
  verifyMapAttestation,
} from './admission.mjs';
import {
  compareShapeProfiles,
  profileExternalShape,
} from './shape_profile.mjs';
import { deriveMapId } from '../translation/congruence.mjs';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));

function load(relative) {
  return JSON.parse(readFileSync(join(ROOT, relative), 'utf8'));
}

function keys() {
  const { privateKey, publicKey } = generateKeyPairSync('ed25519');
  return {
    privateKeyPem: privateKey.export({ type: 'pkcs8', format: 'pem' }),
    publicKeyPem: publicKey.export({ type: 'spki', format: 'pem' }),
  };
}

function baseFixture() {
  const external = load('fixtures/public-known-minimum/provisional-input.json');
  const map = load('contract/provisional-shape-map.json');
  const losses = load('contract/declared-losses.json');
  const profile = profileExternalShape(external);
  const maintainerKeys = keys();
  const trust = {
    schema: 'axm-polybolos-maintainer-trust/1',
    keys: [{
      keyId: 'polybolos-maintainer-key-1',
      maintainer: 'Synthetic Polybolos Maintainer',
      organization: 'Polybolos fixture authority',
      algorithm: 'Ed25519',
      publicKeyPem: maintainerKeys.publicKeyPem,
    }],
  };
  const target = prepareConfirmedMap(map, profile);
  const attestation = signMapAttestation({
    maintainer: 'Synthetic Polybolos Maintainer',
    organization: 'Polybolos fixture authority',
    externalShape: map.externalShape,
    profileId: profile.profileId,
    confirmationTargetId: target.confirmationTargetId,
    reviewedAt: '2026-08-01T00:00:00.000Z',
    expiresAt: '2026-09-01T00:00:00.000Z',
    limitations: ['Synthetic fixture only', 'No operational Polybolos schema claim'],
  }, 'polybolos-maintainer-key-1', maintainerKeys.privateKeyPem);
  return {
    external,
    map,
    losses,
    profile,
    maintainerKeys,
    trust,
    target,
    attestation,
  };
}

test('shape profile retains structure while excluding fixture values', () => {
  const { external, profile } = baseFixture();
  assert.equal(profile.externalShape, external.schema);
  assert.match(profile.profileId, /^polybolosshape1_[0-9a-f]{64}$/);
  assert.match(profile.fixtureDigest, /^polybolosfixture1_[0-9a-f]{64}$/);
  const serialized = JSON.stringify(profile);
  assert.equal(serialized.includes('fixture-request-0001'), false);
  assert.equal(serialized.includes('synthetic-track-0001'), false);
  assert.equal(serialized.includes('not-copied-into-neutral-candidate'), false);
  assert.ok(profile.paths.some((row) => row.path === '/decision/priority'));
  assert.ok(profile.paths.some((row) => row.path === '/entity_ids/*'));
});

test('value changes preserve profile identity while structural changes do not', () => {
  const { external, profile } = baseFixture();
  const changedValues = structuredClone(external);
  changedValues.request_id = 'another-request';
  changedValues.decision.priority = 999;
  changedValues.entity_ids = ['different-track'];
  const sameShape = profileExternalShape(changedValues);
  assert.equal(sameShape.profileId, profile.profileId);
  assert.notEqual(sameShape.fixtureDigest, profile.fixtureDigest);
  assert.equal(compareShapeProfiles(profile, sameShape).equal, true);

  const changedShape = structuredClone(external);
  changedShape.decision.new_required_field = true;
  const different = profileExternalShape(changedShape);
  const diff = compareShapeProfiles(profile, different);
  assert.equal(diff.equal, false);
  assert.ok(diff.added.includes('/decision/new_required_field'));
});

test('coverage proves every mapped source path was observed and leaves unknown native surfaces visible', () => {
  const { map, profile } = baseFixture();
  const coverage = evaluateMapCoverage(map, profile);
  assert.equal(coverage.complete, true);
  assert.equal(coverage.missingSourcePaths.length, 0);
  assert.deepEqual(coverage.unknownTopLevelFields, ['native_kinematics', 'private_extension']);
});

test('prepares a deterministic confirmed target without admitting it by itself', () => {
  const { map, profile } = baseFixture();
  const first = prepareConfirmedMap(map, profile);
  const second = prepareConfirmedMap(structuredClone(map), structuredClone(profile));
  assert.equal(first.confirmationTargetId, second.confirmationTargetId);
  assert.equal(first.preparedMap.mapId, second.preparedMap.mapId);
  assert.equal(first.preparedMap.status, 'confirmed');
  assert.equal(first.preparedMap.sourceProfileId, profile.profileId);
  assert.equal(first.preparedMap.confirmedFromMapId, deriveMapId(map));
  assert.ok(first.preparedMap.mappings.every((row) => row.status === 'confirmed'));
  assert.equal(first.confirmationTargetId, deriveConfirmationTargetId(first.preparedMap));
  assert.equal(Object.prototype.hasOwnProperty.call(first.preparedMap, 'confirmation'), false);
});

test('trusted maintainer attestation promotes and admits one exact structural profile', () => {
  const fx = baseFixture();
  const promotion = promoteConfirmedMap(
    fx.map,
    fx.profile,
    fx.attestation,
    fx.trust,
    '2026-08-02T00:00:00.000Z',
  );
  assert.equal(promotion.status, 'confirmed');
  assert.equal(promotion.confirmedMap.confirmation.attestationId, fx.attestation.attestationId);
  const verification = verifyConfirmedMap(
    promotion.confirmedMap,
    fx.attestation,
    fx.trust,
    '2026-08-02T00:00:00.000Z',
  );
  assert.equal(verification.verified, true);
  const admitted = translateAdmittedExternal(
    fx.external,
    promotion.confirmedMap,
    fx.losses,
    fx.attestation,
    fx.trust,
    '2026-08-02T00:00:00.000Z',
  );
  assert.equal(admitted.projection.mode, 'live');
  assert.equal(admitted.projection.mappingStatus, 'confirmed');
  assert.equal(admitted.observedProfile.profileId, fx.profile.profileId);
});

test('untrusted, tampered, future, and expired attestations fail closed', () => {
  const fx = baseFixture();
  const emptyTrust = { schema: 'axm-polybolos-maintainer-trust/1', keys: [] };
  assert.throws(
    () => verifyMapAttestation(fx.attestation, emptyTrust, {
      externalShape: fx.map.externalShape,
      profileId: fx.profile.profileId,
      confirmationTargetId: fx.target.confirmationTargetId,
    }, '2026-08-02T00:00:00.000Z'),
    (error) => error instanceof ShapeAdmissionError && error.code === 'ATTESTATION_KEY_UNTRUSTED',
  );

  const tampered = structuredClone(fx.attestation);
  tampered.limitations.push('silently changed after signing');
  assert.throws(
    () => verifyMapAttestation(tampered, fx.trust, {
      externalShape: fx.map.externalShape,
      profileId: fx.profile.profileId,
      confirmationTargetId: fx.target.confirmationTargetId,
    }, '2026-08-02T00:00:00.000Z'),
    (error) => error instanceof ShapeAdmissionError
      && ['ATTESTATION_IDENTITY_INVALID', 'ATTESTATION_SIGNATURE_INVALID'].includes(error.code),
  );

  assert.throws(
    () => verifyMapAttestation(fx.attestation, fx.trust, {
      externalShape: fx.map.externalShape,
      profileId: fx.profile.profileId,
      confirmationTargetId: fx.target.confirmationTargetId,
    }, '2026-07-31T00:00:00.000Z'),
    (error) => error instanceof ShapeAdmissionError && error.code === 'ATTESTATION_NOT_YET_ACTIVE',
  );

  assert.throws(
    () => verifyMapAttestation(fx.attestation, fx.trust, {
      externalShape: fx.map.externalShape,
      profileId: fx.profile.profileId,
      confirmationTargetId: fx.target.confirmationTargetId,
    }, '2026-09-02T00:00:00.000Z'),
    (error) => error instanceof ShapeAdmissionError && error.code === 'ATTESTATION_EXPIRED',
  );
});

test('map changes after confirmation invalidate the confirmation target even when map identity is recomputed', () => {
  const fx = baseFixture();
  const promotion = promoteConfirmedMap(
    fx.map,
    fx.profile,
    fx.attestation,
    fx.trust,
    '2026-08-02T00:00:00.000Z',
  );
  const tampered = structuredClone(promotion.confirmedMap);
  tampered.mappings.find((row) => row.semantic === 'candidate priority').target = '/payload/score';
  tampered.mapId = null;
  tampered.mapId = deriveMapId(tampered);
  assert.throws(
    () => verifyConfirmedMap(tampered, fx.attestation, fx.trust, '2026-08-02T00:00:00.000Z'),
    (error) => error instanceof ShapeAdmissionError && error.code === 'MAP_CONFIRMATION_TARGET_INVALID',
  );
});

test('structural drift refuses live translation even when all mapped fields still exist', () => {
  const fx = baseFixture();
  const promotion = promoteConfirmedMap(
    fx.map,
    fx.profile,
    fx.attestation,
    fx.trust,
    '2026-08-02T00:00:00.000Z',
  );
  const drifted = structuredClone(fx.external);
  drifted.new_native_surface = { mode: 'added-after-confirmation' };
  assert.throws(
    () => translateAdmittedExternal(
      drifted,
      promotion.confirmedMap,
      fx.losses,
      fx.attestation,
      fx.trust,
      '2026-08-02T00:00:00.000Z',
    ),
    (error) => error instanceof ShapeAdmissionError && error.code === 'LIVE_SHAPE_PROFILE_MISMATCH',
  );
});

test('coverage refuses confirmation when a required source path is absent from the representative profile', () => {
  const fx = baseFixture();
  const incomplete = structuredClone(fx.external);
  delete incomplete.producer_build_id;
  const incompleteProfile = profileExternalShape(incomplete);
  const coverage = evaluateMapCoverage(fx.map, incompleteProfile);
  assert.equal(coverage.complete, false);
  assert.deepEqual(coverage.missingSourcePaths, ['/producer_build_id']);
  assert.throws(
    () => prepareConfirmedMap(fx.map, incompleteProfile),
    (error) => error instanceof ShapeAdmissionError && error.code === 'MAP_COVERAGE_INCOMPLETE',
  );
});
