import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import test from 'node:test';
import {
  canonicalJson,
  deriveCandidateId,
  deriveCheckpointId,
  deriveWitnessId,
  verifyCheckpointCandidateTransaction,
} from './checkpoint_verifier.mjs';

function hashText(value) {
  return createHash('sha256').update(value, 'utf8').digest('hex');
}

function leaf(entity) {
  return hashText(`polybolos-ci-entity-leaf-v1\0${canonicalJson(entity)}`);
}

function node(left, right) {
  return hashText(`polybolos-ci-entity-node-v1\0${left}\0${right}`);
}

function fixture() {
  const entities = [0, 1, 2].map((index) => ({
    id: `fixture-${index}`,
    name: `FIXTURE ${index}`,
    domain: 'AIR',
    entityType: 'TRACK',
    position: { lat: 34 + index / 1000, lng: -118 - index / 1000 },
    threat: 'LOW',
    classification: 'UNCLASSIFIED',
    source: { provider: 'fixture', feed: 'tracks', confidence: 1 },
    timestamp: '2026-08-01T00:00:00.000Z',
    properties: {},
    display: { color: '#00E5FF', icon: 'dot', layerType: 'circle' },
  }));
  const leaves = entities.map(leaf);
  const level1 = [node(leaves[0], leaves[1]), node(leaves[2], leaves[2])];
  const root = node(level1[0], level1[1]);
  const checkpoint = {
    schema: 'polybolos-command-intelligence-checkpoint/1',
    checkpointId: '',
    sequence: 3,
    observedAt: '2026-08-01T00:00:00.000Z',
    staleAfterMs: 86_400_000,
    entityCount: 3,
    feedCount: 1,
    feedsDigest: hashText('fixture-feeds'),
    entityRoot: root,
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
    entityId: entities[2].id,
    entityIndex: 2,
    entityCount: 3,
    leafHash: leaves[2],
    siblings: [
      { side: 'right', hash: leaves[2] },
      { side: 'left', hash: level1[0] },
    ],
    entity: entities[2],
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
    payload: { entityId: witness.entityId, priority: 7 },
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

test('verifies a bounded checkpoint candidate transaction', () => {
  const receipt = verifyCheckpointCandidateTransaction(fixture());
  assert.equal(receipt.candidateVerified, true);
  assert.equal(receipt.checkpointVerified, true);
  assert.deepEqual(receipt.entityIds, ['fixture-2']);
});

test('refuses a tampered entity even when the witness identity is recomputed', () => {
  const transaction = fixture();
  transaction.witnesses[0].entity.name = 'ALTERED';
  transaction.witnesses[0].witnessId = deriveWitnessId(transaction.witnesses[0]);
  transaction.candidate.evidence[0].witnessId = transaction.witnesses[0].witnessId;
  transaction.candidate.candidateId = deriveCandidateId(transaction.candidate);
  assert.throws(
    () => verifyCheckpointCandidateTransaction(transaction),
    /leaf hash is invalid|entity root/,
  );
});

test('refuses candidate self-authorization after recomputing its identity', () => {
  const transaction = fixture();
  transaction.candidate.payload.commandAuthority = true;
  transaction.candidate.candidateId = deriveCandidateId(transaction.candidate);
  assert.throws(
    () => verifyCheckpointCandidateTransaction(transaction),
    /reserved authority field/,
  );
});

test('refuses missing, duplicated, or mismatched witness evidence', () => {
  const missing = fixture();
  missing.candidate.evidence = [];
  missing.candidate.candidateId = deriveCandidateId(missing.candidate);
  assert.throws(() => verifyCheckpointCandidateTransaction(missing), /evidence does not match/);

  const duplicated = fixture();
  duplicated.witnesses.push(structuredClone(duplicated.witnesses[0]));
  assert.throws(() => verifyCheckpointCandidateTransaction(duplicated), /duplicates an entity witness/);

  const wrongCheckpoint = fixture();
  wrongCheckpoint.witnesses[0].checkpointId = `checkpoint1_${'0'.repeat(64)}`;
  wrongCheckpoint.witnesses[0].witnessId = deriveWitnessId(wrongCheckpoint.witnesses[0]);
  wrongCheckpoint.candidate.evidence[0].witnessId = wrongCheckpoint.witnesses[0].witnessId;
  wrongCheckpoint.candidate.candidateId = deriveCandidateId(wrongCheckpoint.candidate);
  assert.throws(() => verifyCheckpointCandidateTransaction(wrongCheckpoint), /another checkpoint/);
});
