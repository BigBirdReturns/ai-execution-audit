import assert from 'node:assert/strict';
import { generateKeyPairSync, sign } from 'node:crypto';
import test from 'node:test';
import {
  canonicalJson,
  deriveAuthorityId,
  deriveCandidateId,
  deriveSnapshotId,
  evaluateCandidateAuthority,
} from './authority_gate.mjs';

function buildTransaction(overrides = {}) {
  const snapshot = {
    schema: 'polybolos-command-intelligence-snapshot/1',
    snapshotId: '',
    sequence: 1,
    observedAt: '2026-08-01T00:00:00.000Z',
    entityCount: 1,
    feeds: [
      {
        provider: 'fixture-provider',
        feed: 'fixture-feed',
        entityCount: 1,
        lastUpdate: '2026-08-01T00:00:00.000Z',
        stale: false,
      },
    ],
    entities: [
      {
        id: 'fixture-track-1',
        name: 'FIXTURE TRACK ONE',
        domain: 'AIR',
        entityType: 'TRACK',
        position: { lat: 34.1478, lng: -118.1445 },
        threat: 'LOW',
        classification: 'UNCLASSIFIED',
        source: { provider: 'fixture-provider', feed: 'fixture-feed', confidence: 1 },
        timestamp: '2026-08-01T00:00:00.000Z',
        properties: {},
        display: { color: '#00E5FF', icon: 'dot', layerType: 'circle' },
      },
    ],
    claimBoundary: 'observation only',
    ...(overrides.snapshot ?? {}),
  };
  snapshot.snapshotId = deriveSnapshotId(snapshot);

  const candidate = {
    schema: 'polybolos-command-candidate/1',
    candidateId: '',
    snapshotId: snapshot.snapshotId,
    producer: 'command-core-fixture',
    createdAt: '2026-08-01T00:00:01.000Z',
    actionClass: 'track-priority-candidate',
    payload: {
      entityId: 'fixture-track-1',
      priority: 7,
      explanation: 'synthetic candidate only',
    },
    claimBoundary: 'no command authority',
    ...(overrides.candidate ?? {}),
  };
  candidate.candidateId = deriveCandidateId(candidate);

  return {
    schema: 'polybolos-command-candidate-transaction/1',
    snapshot,
    candidate,
    persistence: 'process_memory',
    claimBoundary: 'no execution authority',
  };
}

function signedAuthority(overrides = {}) {
  const { privateKey, publicKey } = generateKeyPairSync('ed25519');
  const body = {
    schema: 'axm-command-authority/1',
    issuer: 'fixture-commander',
    subject: 'polybolos-command-candidate',
    notBefore: '2026-08-01T00:00:00.000Z',
    expiresAt: '2026-08-01T00:05:00.000Z',
    maxSnapshotAgeMs: 120_000,
    allowedProducers: ['command-core-fixture'],
    allowedActionClasses: ['track-priority-candidate'],
    requiredPayloadFields: ['entityId', 'priority'],
    allowedPayloadFields: ['entityId', 'priority', 'explanation'],
    maxPayloadBytes: 4_096,
    ...overrides,
  };
  const authorityId = deriveAuthorityId(body);
  const signedBody = { ...body, authorityId };
  const signature = sign(
    null,
    Buffer.from(canonicalJson(signedBody), 'utf8'),
    privateKey,
  ).toString('base64');
  const authority = {
    ...signedBody,
    signature: {
      algorithm: 'Ed25519',
      keyId: 'fixture-key-1',
      value: signature,
    },
  };
  const trustStore = {
    schema: 'axm-authority-trust/1',
    keys: [
      {
        keyId: 'fixture-key-1',
        issuer: 'fixture-commander',
        algorithm: 'Ed25519',
        publicKeyPem: publicKey.export({ type: 'spki', format: 'pem' }),
      },
    ],
  };
  return { authority, trustStore };
}

function reasonCode(decision) {
  return decision.reasons[0]?.code;
}

test('allows a verified candidate inside one signed authority envelope', () => {
  const transaction = buildTransaction();
  const { authority, trustStore } = signedAuthority();
  const decision = evaluateCandidateAuthority(
    transaction,
    authority,
    trustStore,
    '2026-08-01T00:00:02.000Z',
  );

  assert.equal(decision.disposition, 'allow');
  assert.equal(reasonCode(decision), 'candidate_within_verified_authority');
  assert.equal(decision.candidateVerified, true);
  assert.equal(decision.authorityVerified, true);
  assert.match(decision.decisionId, /^authoritydecision1_[0-9a-f]{64}$/);
  assert.match(decision.claimBoundary, /no actuation surface/i);
});

test('refuses a candidate whose payload changed after binding', () => {
  const transaction = buildTransaction();
  transaction.candidate.payload.priority = 99;
  const { authority, trustStore } = signedAuthority();
  const decision = evaluateCandidateAuthority(
    transaction,
    authority,
    trustStore,
    '2026-08-01T00:00:02.000Z',
  );

  assert.equal(decision.disposition, 'refuse');
  assert.equal(reasonCode(decision), 'candidate_binding_invalid');
  assert.equal(decision.candidateVerified, false);
});

test('refuses self-authorization even when the candidate identity is recomputed', () => {
  const transaction = buildTransaction({
    candidate: { payload: { entityId: 'fixture-track-1', authorized: true } },
  });
  transaction.candidate.candidateId = deriveCandidateId(transaction.candidate);
  const { authority, trustStore } = signedAuthority();
  const decision = evaluateCandidateAuthority(
    transaction,
    authority,
    trustStore,
    '2026-08-01T00:00:02.000Z',
  );

  assert.equal(decision.disposition, 'refuse');
  assert.equal(reasonCode(decision), 'candidate_payload_authority_field');
});

test('refuses an authority with a corrupted signature', () => {
  const transaction = buildTransaction();
  const { authority, trustStore } = signedAuthority();
  authority.signature.value = `${authority.signature.value.slice(0, -4)}AAAA`;
  const decision = evaluateCandidateAuthority(
    transaction,
    authority,
    trustStore,
    '2026-08-01T00:00:02.000Z',
  );

  assert.equal(decision.disposition, 'refuse');
  assert.equal(reasonCode(decision), 'authority_signature_invalid');
  assert.equal(decision.authorityVerified, false);
});

test('holds a verified candidate when the cited observation is too old', () => {
  const transaction = buildTransaction();
  const { authority, trustStore } = signedAuthority({ maxSnapshotAgeMs: 1_000 });
  const decision = evaluateCandidateAuthority(
    transaction,
    authority,
    trustStore,
    '2026-08-01T00:00:03.000Z',
  );

  assert.equal(decision.disposition, 'hold');
  assert.equal(reasonCode(decision), 'snapshot_too_old');
});

test('enters safe state after verified authority expires', () => {
  const transaction = buildTransaction();
  const { authority, trustStore } = signedAuthority({
    expiresAt: '2026-08-01T00:00:01.500Z',
  });
  const decision = evaluateCandidateAuthority(
    transaction,
    authority,
    trustStore,
    '2026-08-01T00:00:02.000Z',
  );

  assert.equal(decision.disposition, 'safe_state');
  assert.equal(reasonCode(decision), 'authority_expired');
});

test('refuses a producer or action class outside the signed envelope', () => {
  const transaction = buildTransaction({
    candidate: { producer: 'unlisted-producer' },
  });
  transaction.candidate.candidateId = deriveCandidateId(transaction.candidate);
  const { authority, trustStore } = signedAuthority();
  const decision = evaluateCandidateAuthority(
    transaction,
    authority,
    trustStore,
    '2026-08-01T00:00:02.000Z',
  );

  assert.equal(decision.disposition, 'refuse');
  assert.equal(reasonCode(decision), 'candidate_producer_not_authorized');
});
