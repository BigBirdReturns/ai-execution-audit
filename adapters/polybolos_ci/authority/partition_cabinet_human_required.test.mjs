import assert from 'node:assert/strict';
import { generateKeyPairSync } from 'node:crypto';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { deriveCandidateId, deriveSnapshotId } from './authority_gate.mjs';
import { createPartitionReconciliationFrame } from './partition_cabinet.mjs';
import {
  PartitionAuthorityRuntime,
  signAuthorityEnvelope,
  signLinkObservation,
} from './partition_runtime.mjs';

function keys() {
  const { privateKey, publicKey } = generateKeyPairSync('ed25519');
  return {
    privateKeyPem: privateKey.export({ type: 'pkcs8', format: 'pem' }),
    publicKeyPem: publicKey.export({ type: 'spki', format: 'pem' }),
  };
}

function transaction() {
  const snapshot = {
    schema: 'polybolos-command-intelligence-snapshot/1',
    snapshotId: '',
    sequence: 1,
    observedAt: '2026-08-01T00:00:00.000Z',
    entityCount: 0,
    feeds: [],
    entities: [],
    claimBoundary: 'observation only',
  };
  snapshot.snapshotId = deriveSnapshotId(snapshot);
  const candidate = {
    schema: 'polybolos-command-candidate/1',
    candidateId: '',
    snapshotId: snapshot.snapshotId,
    producer: 'command-core-fixture',
    createdAt: '2026-08-01T00:00:01.000Z',
    actionClass: 'track-priority-candidate',
    payload: { entityId: 'track-1', priority: 7 },
    claimBoundary: 'no command authority',
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

function authorityBody(note) {
  return {
    schema: 'axm-command-authority/1',
    issuer: 'fixture-commander',
    subject: 'polybolos-command-candidate',
    notBefore: '2026-08-01T00:00:00.000Z',
    expiresAt: '2026-08-01T00:20:00.000Z',
    maxSnapshotAgeMs: 1_200_000,
    allowedProducers: ['command-core-fixture'],
    allowedActionClasses: ['track-priority-candidate'],
    requiredPayloadFields: ['entityId', 'priority'],
    allowedPayloadFields: ['entityId', 'priority'],
    maxPayloadBytes: 4_096,
    note,
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
        {
          id: 'headquarters-denied',
          states: { headquarters: 'down', 'local-control': 'up' },
          partition: true,
          allowedActionClasses: ['track-priority-candidate'],
          maxOfflineMs: 5_000,
          requiresLocalOperator: true,
          expiryDisposition: 'safe_state',
        },
      ],
    },
  };
}

function observation(nodeKeys, observedAt, links) {
  return signLinkObservation(
    {
      schema: 'axm-link-observation/1',
      nodeId: 'fixture-node-1',
      observedAt,
      links,
      localOperatorPresent: true,
    },
    'node-key-1',
    nodeKeys.privateKeyPem,
  );
}

test('keeps a non-superseding returning authority pending for human disposition', () => {
  const root = mkdtempSync(join(tmpdir(), 'polybolos-human-required-'));
  const authorityKeys = keys();
  const nodeKeys = keys();
  const authorityTrustStore = {
    schema: 'axm-authority-trust/1',
    keys: [
      {
        keyId: 'authority-key-1',
        issuer: 'fixture-commander',
        algorithm: 'Ed25519',
        publicKeyPem: authorityKeys.publicKeyPem,
      },
    ],
  };
  const nodeTrustStore = {
    schema: 'axm-node-trust/1',
    keys: [
      {
        keyId: 'node-key-1',
        nodeId: 'fixture-node-1',
        algorithm: 'Ed25519',
        publicKeyPem: nodeKeys.publicKeyPem,
      },
    ],
  };
  const priorAuthority = signAuthorityEnvelope(
    authorityBody('prior authority'),
    'authority-key-1',
    authorityKeys.privateKeyPem,
  );
  const returningAuthority = signAuthorityEnvelope(
    authorityBody('returning authority without explicit supersession'),
    'authority-key-1',
    authorityKeys.privateKeyPem,
  );
  let clockMs = Date.parse('2026-08-01T00:00:02.000Z');
  const journalPath = join(root, 'partition.journal');
  const runtime = new PartitionAuthorityRuntime({
    journalPath,
    nodeId: 'fixture-node-1',
    journalKeyId: 'node-key-1',
    journalPrivateKeyPem: nodeKeys.privateKeyPem,
    nodeTrustStore,
    authorityTrustStore,
    clock: () => clockMs,
  });

  try {
    runtime.observe(
      observation(
        nodeKeys,
        '2026-08-01T00:00:02.000Z',
        { headquarters: 'up', 'local-control': 'up' },
      ),
      priorAuthority,
    );
    clockMs = Date.parse('2026-08-01T00:00:03.000Z');
    runtime.observe(
      observation(
        nodeKeys,
        '2026-08-01T00:00:03.000Z',
        { headquarters: 'down', 'local-control': 'up' },
      ),
      priorAuthority,
    );
    runtime.evaluate(transaction(), priorAuthority);
    clockMs = Date.parse('2026-08-01T00:00:04.000Z');
    const restored = observation(
      nodeKeys,
      '2026-08-01T00:00:04.000Z',
      { headquarters: 'up', 'local-control': 'up' },
    );
    runtime.observe(restored, priorAuthority);
    const reconciliation = runtime.reconcile(returningAuthority);
    assert.equal(reconciliation.disposition, 'human_required');
    assert.ok(runtime.snapshot().pendingReconciliation);
    assert.equal(runtime.snapshot().currentAuthorityId, priorAuthority.authorityId);
    runtime.close();

    const frame = createPartitionReconciliationFrame({
      returningAuthority,
      authorityTrustStore,
      restoredObservation: restored,
      nodeTrustStore,
      reconciliation,
      journalPath,
      capturedAt: '2026-08-01T00:00:05.000Z',
    });
    assert.equal(frame.disposition, 'human_required');
    assert.equal(frame.lamps.reconciliationPending, true);
    assert.equal(frame.lamps.humanRequired, true);
    assert.equal(frame.lamps.reconciliationComplete, false);
    assert.equal(frame.reconciliation.priorAuthorityId, priorAuthority.authorityId);
    assert.equal(frame.reconciliation.returningAuthorityId, returningAuthority.authorityId);
    assert.equal(frame.evidence.kind, 'reconciliation');
  } finally {
    try {
      runtime.close();
    } catch {}
    rmSync(root, { recursive: true, force: true });
  }
});
