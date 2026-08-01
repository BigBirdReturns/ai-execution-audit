import assert from 'node:assert/strict';
import { createHash, generateKeyPairSync } from 'node:crypto';
import test from 'node:test';
import {
  canonicalJson as checkpointCanonicalJson,
  deriveCandidateId,
  deriveCheckpointId,
  deriveWitnessId,
} from '../checkpoint/checkpoint_verifier.mjs';
import { signAuthorityEnvelope } from './partition_runtime.mjs';
import { evaluateCheckpointCandidateAuthority } from './checkpoint_authority_gate.mjs';

function hashText(value) {
  return createHash('sha256').update(value, 'utf8').digest('hex');
}

function leaf(entity) {
  return hashText(`polybolos-ci-entity-leaf-v1\0${checkpointCanonicalJson(entity)}`);
}

function fixtureTransaction() {
  const entity = {
    id: 'fixture-track-1',
    name: 'FIXTURE TRACK ONE',
    domain: 'AIR',
    entityType: 'TRACK',
    position: { lat: 34.1478, lng: -118.1445 },
    threat: 'LOW',
    classification: 'UNCLASSIFIED',
    source: { provider: 'fixture', feed: 'tracks', confidence: 1 },
    timestamp: '2026-08-01T00:00:00.000Z',
    properties: {},
    display: { color: '#00E5FF', icon: 'dot', layerType: 'circle' },
  };
  const leafHash = leaf(entity);
  const checkpoint = {
    schema: 'polybolos-command-intelligence-checkpoint/1',
    checkpointId: '',
    sequence: 1,
    observedAt: '2026-08-01T00:00:00.000Z',
    staleAfterMs: 1_200_000,
    entityCount: 1,
    feedCount: 1,
    feedsDigest: hashText('fixture-feeds'),
    entityRoot: leafHash,
    softwareRecordId: 'software-fixture-1',
    hashAlgorithm: 'sha256',
    treeAlgorithm: 'sorted-entity-id-pair-duplicate-last-v1',
    claimBoundary: 'no authority',
  };
  checkpoint.checkpointId = deriveCheckpointId(checkpoint);
  const witness = {
    schema: 'polybolos-command-intelligence-entity-witness/1',
    witnessId: '',
    checkpointId: checkpoint.checkpointId,
    entityId: entity.id,
    entityIndex: 0,
    entityCount: 1,
    leafHash,
    siblings: [],
    entity,
    claimBoundary: 'no authority',
  };
  witness.witnessId = deriveWitnessId(witness);
  const candidate = {
    schema: 'polybolos-command-candidate/2',
    candidateId: '',
    checkpointId: checkpoint.checkpointId,
    evidence: [{ entityId: witness.entityId, witnessId: witness.witnessId }],
    producer: 'command-core-fixture',
    createdAt: '2026-08-01T00:00:01.000Z',
    actionClass: 'track-priority-candidate',
    payload: {
      entityId: entity.id,
      priority: 7,
      explanation: 'synthetic candidate only',
    },
    claimBoundary: 'no authority',
  };
  candidate.candidateId = deriveCandidateId(candidate);
  return {
    schema: 'polybolos-command-candidate-transaction/2',
    checkpoint,
    witnesses: [witness],
    candidate,
    persistence: 'process_memory',
    claimBoundary: 'no authority',
  };
}

function setup() {
  const { privateKey, publicKey } = generateKeyPairSync('ed25519');
  const privateKeyPem = privateKey.export({ type: 'pkcs8', format: 'pem' });
  const publicKeyPem = publicKey.export({ type: 'spki', format: 'pem' });
  const trustStore = {
    schema: 'axm-authority-trust/1',
    keys: [{
      keyId: 'authority-key-1',
      issuer: 'fixture-commander',
      algorithm: 'Ed25519',
      publicKeyPem,
    }],
  };
  const authorityBody = (overrides = {}) => ({
    schema: 'axm-command-authority/1',
    issuer: 'fixture-commander',
    subject: 'polybolos-command-candidate',
    notBefore: '2026-08-01T00:00:00.000Z',
    expiresAt: '2026-08-01T00:20:00.000Z',
    maxObservationAgeMs: 1_200_000,
    allowedProducers: ['command-core-fixture'],
    allowedActionClasses: ['track-priority-candidate'],
    allowedSoftwareRecordIds: ['software-fixture-1'],
    maxEvidenceWitnesses: 4,
    maxObservedEntities: 20_000,
    requiredPayloadFields: ['entityId', 'priority'],
    allowedPayloadFields: ['entityId', 'priority', 'explanation'],
    maxPayloadBytes: 4_096,
    partitionPolicy: {
      links: ['headquarters', 'local-control'],
      profiles: [
        {
          id: 'connected',
          states: { headquarters: 'up', 'local-control': 'up' },
          partition: false,
          allowedActionClasses: ['track-priority-candidate'],
          maxOfflineMs: 0,
          requiresLocalOperator: false,
          expiryDisposition: 'safe_state',
        },
      ],
    },
    ...overrides,
  });
  const sign = (overrides = {}) => signAuthorityEnvelope(
    authorityBody(overrides),
    'authority-key-1',
    privateKeyPem,
  );
  return { trustStore, sign };
}

test('allows a checkpoint-bound candidate inside signed software and evidence bounds', () => {
  const transaction = fixtureTransaction();
  const { trustStore, sign } = setup();
  const decision = evaluateCheckpointCandidateAuthority(
    transaction,
    sign(),
    trustStore,
    '2026-08-01T00:00:02.000Z',
  );
  assert.equal(decision.disposition, 'allow');
  assert.equal(decision.candidateVerified, true);
  assert.equal(decision.checkpointVerified, true);
  assert.equal(decision.authorityVerified, true);
  assert.equal(decision.witnessCount, 1);
  assert.deepEqual(decision.entityIds, ['fixture-track-1']);
});

test('refuses an unapproved software identity and an unproven payload reference', () => {
  const transaction = fixtureTransaction();
  const { trustStore, sign } = setup();
  const wrongSoftware = evaluateCheckpointCandidateAuthority(
    transaction,
    sign({ allowedSoftwareRecordIds: ['some-other-build'] }),
    trustStore,
    '2026-08-01T00:00:02.000Z',
  );
  assert.equal(wrongSoftware.disposition, 'refuse');
  assert.equal(wrongSoftware.reasons[0].code, 'checkpoint_software_not_authorized');

  const missingEvidence = structuredClone(transaction);
  missingEvidence.candidate.payload.entityId = 'fixture-track-2';
  missingEvidence.candidate.candidateId = deriveCandidateId(missingEvidence.candidate);
  const decision = evaluateCheckpointCandidateAuthority(
    missingEvidence,
    sign(),
    trustStore,
    '2026-08-01T00:00:02.000Z',
  );
  assert.equal(decision.disposition, 'refuse');
  assert.equal(decision.reasons[0].code, 'candidate_evidence_reference_unproven');
});

test('refuses a tampered witness even when its identity and candidate evidence are recomputed', () => {
  const transaction = fixtureTransaction();
  const { trustStore, sign } = setup();
  transaction.witnesses[0].entity.name = 'ALTERED';
  transaction.witnesses[0].witnessId = deriveWitnessId(transaction.witnesses[0]);
  transaction.candidate.evidence[0].witnessId = transaction.witnesses[0].witnessId;
  transaction.candidate.candidateId = deriveCandidateId(transaction.candidate);
  const decision = evaluateCheckpointCandidateAuthority(
    transaction,
    sign(),
    trustStore,
    '2026-08-01T00:00:02.000Z',
  );
  assert.equal(decision.disposition, 'refuse');
  assert.equal(decision.candidateVerified, false);
  assert.match(decision.reasons[0].code, /witness_/);
});

test('holds stale checkpoints, enters safe state on authority expiry, and enforces observed scale', () => {
  const transaction = fixtureTransaction();
  const { trustStore, sign } = setup();
  const stale = evaluateCheckpointCandidateAuthority(
    transaction,
    sign({ maxObservationAgeMs: 500 }),
    trustStore,
    '2026-08-01T00:00:02.000Z',
  );
  assert.equal(stale.disposition, 'hold');
  assert.equal(stale.reasons[0].code, 'checkpoint_too_old');

  const expired = evaluateCheckpointCandidateAuthority(
    transaction,
    sign({ expiresAt: '2026-08-01T00:00:01.500Z' }),
    trustStore,
    '2026-08-01T00:00:02.000Z',
  );
  assert.equal(expired.disposition, 'safe_state');
  assert.equal(expired.reasons[0].code, 'authority_expired');

  const scale = evaluateCheckpointCandidateAuthority(
    transaction,
    sign({ maxObservedEntities: 0 }),
    trustStore,
    '2026-08-01T00:00:02.000Z',
  );
  assert.equal(scale.disposition, 'refuse');
  assert.equal(scale.reasons[0].code, 'authority_observed_entities_invalid');
});
