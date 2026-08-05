#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import {
  canonicalJson,
  deriveCandidateId,
  deriveCheckpointId,
  deriveWitnessId,
  verifyCheckpointCandidateTransaction,
} from '../../polybolos_ci/checkpoint/checkpoint_verifier.mjs';

function hashText(value) {
  return createHash('sha256').update(value, 'utf8').digest('hex');
}

function leaf(entity) {
  return hashText(`polybolos-ci-entity-leaf-v1\0${canonicalJson(entity)}`);
}

function node(left, right) {
  return hashText(`polybolos-ci-entity-node-v1\0${left}\0${right}`);
}

function entity(index) {
  return {
    id: `synthetic-track-${String(index + 1).padStart(4, '0')}`,
    name: `SYNTHETIC TRACK ${index + 1}`,
    domain: 'AIR',
    entityType: 'TRACK',
    position: {
      lat: 34.1000 + index / 1000,
      lng: -118.1000 - index / 1000,
    },
    threat: 'LOW',
    classification: 'UNCLASSIFIED',
    source: {
      provider: 'synthetic-axm-fixture',
      feed: 'tracks',
      confidence: 1,
    },
    timestamp: '2026-08-01T00:00:00.000Z',
    properties: {},
    display: {
      color: '#ffffff',
      icon: 'dot',
      layerType: 'circle',
    },
  };
}

const output = resolve(process.argv[2] ?? 'qualification/polybolos-adapter/checkpoint-fixture.json');
const entities = [0, 1, 2, 3].map(entity).sort((a, b) => a.id.localeCompare(b.id));
const leaves = entities.map(leaf);
const level1 = [node(leaves[0], leaves[1]), node(leaves[2], leaves[3])];
const root = node(level1[0], level1[1]);
const checkpoint = {
  schema: 'polybolos-command-intelligence-checkpoint/1',
  checkpointId: '',
  sequence: 4,
  observedAt: '2026-08-01T00:00:00.000Z',
  staleAfterMs: 86_400_000,
  entityCount: entities.length,
  feedCount: 1,
  feedsDigest: hashText('synthetic-axm-fixture-feed'),
  entityRoot: root,
  softwareRecordId: 'synthetic-axm-checkpoint-fixture-v1',
  hashAlgorithm: 'sha256',
  treeAlgorithm: 'sorted-entity-id-pair-duplicate-last-v1',
  claimBoundary:
    'Synthetic checkpoint for adapter conformance only. It is not a Polybolos Command Intelligence observation or operational feed.',
};
checkpoint.checkpointId = deriveCheckpointId(checkpoint);

const witnesses = entities.map((row, index) => {
  const siblingIndex = index % 2 === 0 ? index + 1 : index - 1;
  const siblingSide = index % 2 === 0 ? 'right' : 'left';
  const parentSiblingIndex = index < 2 ? 1 : 0;
  const parentSiblingSide = index < 2 ? 'right' : 'left';
  const witness = {
    schema: 'polybolos-command-intelligence-entity-witness/1',
    witnessId: '',
    checkpointId: checkpoint.checkpointId,
    entityId: row.id,
    entityIndex: index,
    entityCount: entities.length,
    leafHash: leaves[index],
    siblings: [
      { side: siblingSide, hash: leaves[siblingIndex] },
      { side: parentSiblingSide, hash: level1[parentSiblingIndex] },
    ],
    entity: row,
    claimBoundary:
      'Synthetic membership witness for adapter conformance only. It carries no command authority.',
  };
  witness.witnessId = deriveWitnessId(witness);
  return witness;
});
const evidence = witnesses
  .map((witness) => ({ entityId: witness.entityId, witnessId: witness.witnessId }))
  .sort((a, b) => a.entityId.localeCompare(b.entityId));
const candidate = {
  schema: 'polybolos-command-candidate/2',
  candidateId: '',
  checkpointId: checkpoint.checkpointId,
  evidence,
  producer: 'synthetic-reference-producer',
  createdAt: '2026-08-01T00:00:01.000Z',
  actionClass: 'track-priority-candidate',
  payload: {
    entityIds: entities.map((row) => row.id),
    priority: 7,
  },
  claimBoundary:
    'Synthetic candidate for adapter conformance only. It carries no command authority.',
};
candidate.candidateId = deriveCandidateId(candidate);
const transaction = {
  schema: 'polybolos-command-candidate-transaction/2',
  checkpoint,
  witnesses,
  candidate,
  persistence: 'synthetic_fixture',
  claimBoundary:
    'Self-contained neutral checkpoint transaction for AXM adapter conformance. It is not a Polybolos product or operational transaction.',
};
const verification = verifyCheckpointCandidateTransaction(transaction);
mkdirSync(dirname(output), { recursive: true });
writeFileSync(output, `${JSON.stringify(transaction, null, 2)}\n`, 'utf8');
writeFileSync(`${output}.verification.json`, `${JSON.stringify(verification, null, 2)}\n`, 'utf8');
process.stdout.write(`${JSON.stringify({
  status: 'pass',
  checkpointId: checkpoint.checkpointId,
  candidateId: candidate.candidateId,
  witnessCount: witnesses.length,
  output,
}, null, 2)}\n`);
