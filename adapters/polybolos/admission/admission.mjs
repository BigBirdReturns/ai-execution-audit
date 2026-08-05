import {
  createHash,
  createPrivateKey,
  createPublicKey,
  sign as signMessage,
  verify as verifyMessage,
} from 'node:crypto';
import {
  canonicalJson,
  deriveMapId,
  translateExternalProposal,
  validateShapeMap,
} from '../translation/congruence.mjs';
import {
  compareShapeProfiles,
  profileExternalShape,
} from './shape_profile.mjs';

export class ShapeAdmissionError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'ShapeAdmissionError';
    this.code = code;
  }
}

function requireCondition(condition, code, message) {
  if (!condition) throw new ShapeAdmissionError(code, message);
}

function isRecord(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function digest(prefix, value) {
  return `${prefix}_${createHash('sha256').update(canonicalJson(value), 'utf8').digest('hex')}`;
}

function normalizedTime(value, code, label) {
  const milliseconds = Date.parse(value);
  requireCondition(Number.isFinite(milliseconds), code, `${label} is not a valid date-time`);
  return new Date(milliseconds).toISOString();
}

function mapSourcePaths(map) {
  return map.mappings.map((row) => row.source).sort();
}

export function evaluateMapCoverage(map, profile) {
  const { mapId } = validateShapeMap(map);
  requireCondition(
    isRecord(profile) && profile.schema === 'axm-polybolos-shape-profile/1',
    'PROFILE_SCHEMA_INVALID',
    'shape profile is invalid',
  );
  requireCondition(map.externalShape === profile.externalShape, 'PROFILE_SHAPE_MISMATCH', 'shape map and profile name different external shapes');
  const observed = new Set(profile.paths.map((row) => row.path));
  const mapped = mapSourcePaths(map);
  const missing = mapped.filter((path) => !observed.has(path));
  const present = mapped.filter((path) => observed.has(path));
  const mappedTopLevel = new Set(mapped.map((path) => path.split('/').filter(Boolean)[0]));
  const observedTopLevel = profile.paths
    .map((row) => row.path)
    .filter((path) => /^\/[^/]+$/.test(path))
    .map((path) => path.slice(1));
  const unknownTopLevel = [...new Set(observedTopLevel.filter((name) => name !== 'schema' && !mappedTopLevel.has(name)))].sort();
  return {
    schema: 'axm-polybolos-map-coverage/1',
    mapId,
    profileId: profile.profileId,
    complete: missing.length === 0,
    mappedSourceCount: mapped.length,
    presentSourceCount: present.length,
    missingSourcePaths: missing,
    unknownTopLevelFields: unknownTopLevel,
    authorityLikePaths: profile.authorityLikePaths,
    claimBoundary:
      'Coverage establishes that mapped source paths were observed in one structural profile. It does not establish semantic correctness, universal optionality, or operational compatibility.',
  };
}

function confirmationTargetBody(map) {
  const {
    mapId: _mapId,
    claimBoundary: _claimBoundary,
    confirmation: _confirmation,
    confirmationTargetId: _confirmationTargetId,
    ...body
  } = map;
  return body;
}

export function deriveConfirmationTargetId(map) {
  return digest('polybolosconfirmationtarget1', confirmationTargetBody(map));
}

export function prepareConfirmedMap(provisionalMap, profile) {
  const { mapId: provisionalMapId } = validateShapeMap(provisionalMap);
  requireCondition(provisionalMap.status === 'provisional', 'MAP_NOT_PROVISIONAL', 'only a provisional map may be prepared for confirmation');
  const coverage = evaluateMapCoverage(provisionalMap, profile);
  requireCondition(coverage.complete, 'MAP_COVERAGE_INCOMPLETE', 'shape profile does not contain every mapped source path');
  const prepared = structuredClone(provisionalMap);
  prepared.mapId = null;
  prepared.status = 'confirmed';
  prepared.confirmedFromMapId = provisionalMapId;
  prepared.sourceProfileId = profile.profileId;
  prepared.mappings = prepared.mappings.map((row) => ({ ...row, status: 'confirmed' }));
  prepared.confirmationTargetId = deriveConfirmationTargetId(prepared);
  prepared.mapId = deriveMapId(prepared);
  return {
    schema: 'axm-polybolos-confirmation-target/1',
    provisionalMapId,
    profileId: profile.profileId,
    confirmationTargetId: prepared.confirmationTargetId,
    preparedMapId: prepared.mapId,
    preparedMap: prepared,
    coverage,
    claimBoundary:
      'This target is ready for maintainer review. It is not admitted for live translation until a trusted signed attestation is verified.',
  };
}

function attestationIdentityBody(attestation) {
  const { attestationId: _attestationId, signature: _signature, claimBoundary: _claimBoundary, ...body } = attestation;
  return body;
}

export function deriveMapAttestationId(attestation) {
  return digest('polybolosattestation1', attestationIdentityBody(attestation));
}

function signedAttestationBody(attestation) {
  const { signature: _signature, ...body } = attestation;
  return body;
}

export function signMapAttestation(input, keyId, privateKeyPem) {
  requireCondition(isRecord(input), 'ATTESTATION_INPUT_INVALID', 'attestation input must be an object');
  const reviewedAt = normalizedTime(input.reviewedAt, 'ATTESTATION_TIME_INVALID', 'reviewedAt');
  const expiresAt = normalizedTime(input.expiresAt, 'ATTESTATION_TIME_INVALID', 'expiresAt');
  requireCondition(Date.parse(expiresAt) > Date.parse(reviewedAt), 'ATTESTATION_TIME_INVALID', 'attestation expiry must follow review time');
  requireCondition(typeof keyId === 'string' && keyId.trim(), 'ATTESTATION_KEY_INVALID', 'attestation key ID is required');
  const body = {
    schema: 'axm-polybolos-map-attestation/1',
    maintainer: input.maintainer,
    organization: input.organization,
    externalShape: input.externalShape,
    profileId: input.profileId,
    confirmationTargetId: input.confirmationTargetId,
    reviewedAt,
    expiresAt,
    limitations: Array.isArray(input.limitations) ? [...new Set(input.limitations.map((row) => String(row).trim()).filter(Boolean))].sort() : [],
  };
  for (const field of ['maintainer', 'organization', 'externalShape', 'profileId', 'confirmationTargetId']) {
    requireCondition(typeof body[field] === 'string' && body[field].trim(), 'ATTESTATION_INPUT_INVALID', `attestation field ${field} is required`);
  }
  const attestation = {
    ...body,
    attestationId: '',
    signature: {
      algorithm: 'Ed25519',
      keyId: keyId.trim(),
      value: '',
    },
    claimBoundary:
      'This signature confirms one structural profile and one explicit translation target. It does not transfer command authority or certify Polybolos operational performance.',
  };
  attestation.attestationId = deriveMapAttestationId(attestation);
  attestation.signature.value = signMessage(
    null,
    Buffer.from(canonicalJson(signedAttestationBody(attestation)), 'utf8'),
    createPrivateKey(privateKeyPem),
  ).toString('base64');
  return attestation;
}

function trustedKey(attestation, trustStore) {
  requireCondition(
    isRecord(trustStore)
      && trustStore.schema === 'axm-polybolos-maintainer-trust/1'
      && Array.isArray(trustStore.keys),
    'ATTESTATION_TRUST_INVALID',
    'maintainer trust store is invalid',
  );
  return trustStore.keys.find((row) =>
    isRecord(row)
    && row.keyId === attestation.signature?.keyId
    && row.maintainer === attestation.maintainer
    && row.organization === attestation.organization
    && row.algorithm === 'Ed25519'
  );
}

export function verifyMapAttestation(attestation, trustStore, expected, checkedAt) {
  requireCondition(
    isRecord(attestation) && attestation.schema === 'axm-polybolos-map-attestation/1',
    'ATTESTATION_SCHEMA_INVALID',
    'map attestation schema is invalid',
  );
  requireCondition(attestation.attestationId === deriveMapAttestationId(attestation), 'ATTESTATION_IDENTITY_INVALID', 'map attestation identity does not match its contents');
  requireCondition(
    isRecord(attestation.signature)
      && attestation.signature.algorithm === 'Ed25519'
      && typeof attestation.signature.value === 'string',
    'ATTESTATION_SIGNATURE_INVALID',
    'map attestation signature metadata is invalid',
  );
  const key = trustedKey(attestation, trustStore);
  requireCondition(key && typeof key.publicKeyPem === 'string', 'ATTESTATION_KEY_UNTRUSTED', 'map attestation key is not trusted');
  let verified = false;
  try {
    verified = verifyMessage(
      null,
      Buffer.from(canonicalJson(signedAttestationBody(attestation)), 'utf8'),
      createPublicKey(key.publicKeyPem),
      Buffer.from(attestation.signature.value, 'base64'),
    );
  } catch {
    verified = false;
  }
  requireCondition(verified, 'ATTESTATION_SIGNATURE_INVALID', 'map attestation signature did not verify');
  requireCondition(isRecord(expected), 'ATTESTATION_EXPECTED_INVALID', 'expected attestation target is invalid');
  for (const field of ['externalShape', 'profileId', 'confirmationTargetId']) {
    requireCondition(attestation[field] === expected[field], 'ATTESTATION_TARGET_MISMATCH', `map attestation differs on ${field}`);
  }
  const checkedAtMs = Date.parse(checkedAt);
  requireCondition(Number.isFinite(checkedAtMs), 'ATTESTATION_CHECK_TIME_INVALID', 'attestation check time is invalid');
  const reviewedAtMs = Date.parse(attestation.reviewedAt);
  const expiresAtMs = Date.parse(attestation.expiresAt);
  requireCondition(checkedAtMs >= reviewedAtMs, 'ATTESTATION_NOT_YET_ACTIVE', 'map attestation review time is in the future');
  requireCondition(checkedAtMs <= expiresAtMs, 'ATTESTATION_EXPIRED', 'map attestation has expired');
  return {
    schema: 'axm-polybolos-map-attestation-verification/1',
    attestationId: attestation.attestationId,
    maintainer: attestation.maintainer,
    organization: attestation.organization,
    externalShape: attestation.externalShape,
    profileId: attestation.profileId,
    confirmationTargetId: attestation.confirmationTargetId,
    checkedAt: new Date(checkedAtMs).toISOString(),
    verified: true,
  };
}

export function promoteConfirmedMap(provisionalMap, profile, attestation, trustStore, checkedAt) {
  const target = prepareConfirmedMap(provisionalMap, profile);
  const verification = verifyMapAttestation(attestation, trustStore, {
    externalShape: provisionalMap.externalShape,
    profileId: profile.profileId,
    confirmationTargetId: target.confirmationTargetId,
  }, checkedAt);
  const confirmed = structuredClone(target.preparedMap);
  confirmed.mapId = null;
  confirmed.confirmation = {
    attestationId: attestation.attestationId,
    maintainer: attestation.maintainer,
    organization: attestation.organization,
    keyId: attestation.signature.keyId,
    reviewedAt: attestation.reviewedAt,
    expiresAt: attestation.expiresAt,
  };
  confirmed.mapId = deriveMapId(confirmed);
  return {
    schema: 'axm-polybolos-map-promotion/1',
    status: 'confirmed',
    confirmedMap: confirmed,
    target,
    attestationVerification: verification,
    claimBoundary:
      'Promotion confirms the explicit adapter mapping against one structural profile. It does not make the external system an AXM product or grant command authority.',
  };
}

function confirmationTargetFromConfirmedMap(map) {
  const copy = structuredClone(map);
  copy.mapId = null;
  delete copy.confirmation;
  const expected = deriveConfirmationTargetId(copy);
  return { copy, expected };
}

export function verifyConfirmedMap(map, attestation, trustStore, checkedAt) {
  const { mapId } = validateShapeMap(map);
  requireCondition(map.status === 'confirmed', 'MAP_NOT_CONFIRMED', 'shape map is not confirmed');
  requireCondition(map.mappings.every((row) => row.status === 'confirmed'), 'MAP_NOT_CONFIRMED', 'shape map contains unconfirmed fields');
  requireCondition(isRecord(map.confirmation), 'MAP_CONFIRMATION_MISSING', 'confirmed map has no confirmation metadata');
  requireCondition(map.confirmation.attestationId === attestation.attestationId, 'MAP_CONFIRMATION_MISMATCH', 'confirmed map cites another attestation');
  const target = confirmationTargetFromConfirmedMap(map);
  requireCondition(map.confirmationTargetId === target.expected, 'MAP_CONFIRMATION_TARGET_INVALID', 'confirmed map target identity does not match its contents');
  const verification = verifyMapAttestation(attestation, trustStore, {
    externalShape: map.externalShape,
    profileId: map.sourceProfileId,
    confirmationTargetId: map.confirmationTargetId,
  }, checkedAt);
  return {
    schema: 'axm-polybolos-confirmed-map-verification/1',
    mapId,
    profileId: map.sourceProfileId,
    confirmationTargetId: map.confirmationTargetId,
    attestationVerification: verification,
    verified: true,
  };
}

export function translateAdmittedExternal(external, confirmedMap, lossRegistry, attestation, trustStore, checkedAt) {
  const mapVerification = verifyConfirmedMap(confirmedMap, attestation, trustStore, checkedAt);
  const observedProfile = profileExternalShape(external, { externalShape: confirmedMap.externalShape });
  requireCondition(observedProfile.profileId === confirmedMap.sourceProfileId, 'LIVE_SHAPE_PROFILE_MISMATCH', 'live external shape differs from the confirmed structural profile');
  const projection = translateExternalProposal(external, confirmedMap, lossRegistry, { mode: 'live' });
  return {
    schema: 'axm-polybolos-admitted-translation/1',
    projection,
    observedProfile,
    mapVerification,
    shapeDiff: compareShapeProfiles(observedProfile, observedProfile),
    claimBoundary:
      'This receipt admits one external object through a confirmed structural and semantic adapter. It remains an AXM-neutral candidate projection and carries no command authority.',
  };
}
