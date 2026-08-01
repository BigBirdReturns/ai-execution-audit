import assert from 'node:assert/strict';
import { generateKeyPairSync } from 'node:crypto';
import {
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import {
  deriveCandidateId,
  deriveSnapshotId,
} from './authority_gate.mjs';
import {
  createPartitionDecisionFrame,
  createPartitionReconciliationFrame,
} from './partition_cabinet.mjs';
import {
  PartitionAuthorityRuntime,
  signAuthorityEnvelope,
  signLinkObservation,
} from './partition_runtime.mjs';

function keyPair() {
  const { privateKey, publicKey } = generateKeyPairSync('ed25519');
  return {
    privateKeyPem: privateKey.export({ type: 'pkcs8', format: 'pem' }),
    publicKeyPem: publicKey.export({ type: 'spki', format: 'pem' }),
  };
}

function buildTransaction() {
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

function authorityBody(overrides = {}) {
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
    ...overrides,
  };
}

function linkObservation(nodeKeys, observedAt, links) {
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

function fixture() {
  const root = mkdtempSync(join(tmpdir(), 'polybolos-partition-cabinet-'));
  const journalPath = join(root, 'partition.journal');
  const authorityKeys = keyPair();
  const nodeKeys = keyPair();
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
  const authority = signAuthorityEnvelope(
    authorityBody(),
    'authority-key-1',
    authorityKeys.privateKeyPem,
  );
  let clockMs = Date.parse('2026-08-01T00:00:02.000Z');
  const runtimeConfig = {
    journalPath,
    nodeId: 'fixture-node-1',
    journalKeyId: 'node-key-1',
    journalPrivateKeyPem: nodeKeys.privateKeyPem,
    nodeTrustStore,
    authorityTrustStore,
    clock: () => clockMs,
  };
  const setClock = (value) => {
    clockMs = Date.parse(value);
  };
  return {
    root,
    journalPath,
    authorityKeys,
    nodeKeys,
    authorityTrustStore,
    nodeTrustStore,
    authority,
    runtimeConfig,
    setClock,
    transaction: buildTransaction(),
    cleanup() {
      rmSync(root, { recursive: true, force: true });
    },
  };
}

test('projects candidate, safe-state, and reconciliation receipts only after signed-journal verification', () => {
  const fx = fixture();
  try {
    const runtime = new PartitionAuthorityRuntime(fx.runtimeConfig);
    const connected = linkObservation(
      fx.nodeKeys,
      '2026-08-01T00:00:02.000Z',
      { headquarters: 'up', 'local-control': 'up' },
    );
    runtime.observe(connected, fx.authority);
    const connectedDecision = runtime.evaluate(fx.transaction, fx.authority);

    fx.setClock('2026-08-01T00:00:03.000Z');
    const denied = linkObservation(
      fx.nodeKeys,
      '2026-08-01T00:00:03.000Z',
      { headquarters: 'down', 'local-control': 'up' },
    );
    runtime.observe(denied, fx.authority);
    const initialDecision = runtime.evaluate(fx.transaction, fx.authority);

    fx.setClock('2026-08-01T00:00:05.000Z');
    const deniedRepeat = linkObservation(
      fx.nodeKeys,
      '2026-08-01T00:00:05.000Z',
      { headquarters: 'down', 'local-control': 'up' },
    );
    runtime.observe(deniedRepeat, fx.authority);

    fx.setClock('2026-08-01T00:00:09.000Z');
    const expiredDecision = runtime.evaluate(fx.transaction, fx.authority);
    assert.equal(expiredDecision.disposition, 'safe_state');

    const initialFrame = createPartitionDecisionFrame({
      authority: fx.authority,
      authorityTrustStore: fx.authorityTrustStore,
      observation: denied,
      nodeTrustStore: fx.nodeTrustStore,
      decision: initialDecision,
      journalPath: fx.journalPath,
      capturedAt: '2026-08-01T00:00:10.000Z',
    });
    const initialFrameLater = createPartitionDecisionFrame({
      authority: fx.authority,
      authorityTrustStore: fx.authorityTrustStore,
      observation: denied,
      nodeTrustStore: fx.nodeTrustStore,
      decision: initialDecision,
      journalPath: fx.journalPath,
      capturedAt: '2026-08-01T00:00:11.000Z',
    });
    assert.equal(initialFrame.mode, 'candidate');
    assert.equal(initialFrame.profileId, 'headquarters-denied');
    assert.equal(initialFrame.disposition, 'allow');
    assert.equal(initialFrame.lamps.partitioned, true);
    assert.equal(initialFrame.lamps.candidateEligible, true);
    assert.equal(initialFrame.lamps.signedEvidence, true);
    assert.equal(initialFrame.verification.signedJournal, true);
    assert.match(initialFrame.evidence.recordId, /^partitionrecord1_/);
    assert.equal(initialFrame.stateId, initialFrameLater.stateId);
    assert.notEqual(initialFrame.frameId, initialFrameLater.frameId);

    const expiredFrame = createPartitionDecisionFrame({
      authority: fx.authority,
      authorityTrustStore: fx.authorityTrustStore,
      observation: deniedRepeat,
      nodeTrustStore: fx.nodeTrustStore,
      decision: expiredDecision,
      journalPath: fx.journalPath,
      capturedAt: '2026-08-01T00:00:12.000Z',
    });
    assert.equal(expiredFrame.disposition, 'safe_state');
    assert.equal(expiredFrame.reasonCode, 'partition_offline_lease_expired');
    assert.equal(expiredFrame.lamps.safeState, true);
    assert.equal(expiredFrame.lamps.leaseExpired, true);
    assert.equal(expiredFrame.lease.elapsedMs, 6_000);

    const serialized = JSON.stringify(expiredFrame).toLowerCase();
    for (const forbidden of ['"payload"', '"signature"', '"privatekey"', '"execute":true']) {
      assert.equal(serialized.includes(forbidden), false);
    }

    const restored = linkObservation(
      fx.nodeKeys,
      '2026-08-01T00:00:09.000Z',
      { headquarters: 'up', 'local-control': 'up' },
    );
    runtime.observe(restored, fx.authority);
    const returningAuthority = signAuthorityEnvelope(
      authorityBody({ supersedes: [fx.authority.authorityId] }),
      'authority-key-1',
      fx.authorityKeys.privateKeyPem,
    );
    const reconciliation = runtime.reconcile(returningAuthority);
    runtime.close();

    const reconciliationFrame = createPartitionReconciliationFrame({
      returningAuthority,
      authorityTrustStore: fx.authorityTrustStore,
      restoredObservation: restored,
      nodeTrustStore: fx.nodeTrustStore,
      reconciliation,
      journalPath: fx.journalPath,
      capturedAt: '2026-08-01T00:00:13.000Z',
    });
    assert.equal(reconciliationFrame.mode, 'reconciliation');
    assert.equal(reconciliationFrame.disposition, 'explicitly_superseded');
    assert.equal(reconciliationFrame.lamps.connected, true);
    assert.equal(reconciliationFrame.lamps.reconciliationComplete, true);
    assert.equal(reconciliationFrame.lamps.humanRequired, false);
    assert.ok(reconciliationFrame.counts.localDecisions >= 3);
    assert.match(reconciliationFrame.reconciliation.localDecisionIdsSha256, /^[0-9a-f]{64}$/);

    assert.equal(connectedDecision.disposition, 'allow');
  } finally {
    fx.cleanup();
  }
});

test('refuses a decision that is altered after it was signed into the journal', () => {
  const fx = fixture();
  try {
    const runtime = new PartitionAuthorityRuntime(fx.runtimeConfig);
    fx.setClock('2026-08-01T00:00:03.000Z');
    const denied = linkObservation(
      fx.nodeKeys,
      '2026-08-01T00:00:03.000Z',
      { headquarters: 'down', 'local-control': 'up' },
    );
    runtime.observe(denied, fx.authority);
    const decision = runtime.evaluate(fx.transaction, fx.authority);
    runtime.close();

    const tampered = structuredClone(decision);
    tampered.disposition = 'safe_state';
    assert.throws(
      () => createPartitionDecisionFrame({
        authority: fx.authority,
        authorityTrustStore: fx.authorityTrustStore,
        observation: denied,
        nodeTrustStore: fx.nodeTrustStore,
        decision: tampered,
        journalPath: fx.journalPath,
        capturedAt: '2026-08-01T00:00:04.000Z',
      }),
      /decision identity is invalid|disposition differs/,
    );
  } finally {
    fx.cleanup();
  }
});

test('refuses a complete journal record rewrite before building a frame', () => {
  const fx = fixture();
  try {
    const runtime = new PartitionAuthorityRuntime(fx.runtimeConfig);
    fx.setClock('2026-08-01T00:00:03.000Z');
    const denied = linkObservation(
      fx.nodeKeys,
      '2026-08-01T00:00:03.000Z',
      { headquarters: 'down', 'local-control': 'up' },
    );
    runtime.observe(denied, fx.authority);
    const decision = runtime.evaluate(fx.transaction, fx.authority);
    runtime.close();

    const lines = readFileSync(fx.journalPath, 'utf8').trimEnd().split('\n');
    const record = JSON.parse(lines.at(-1));
    record.event.disposition = 'safe_state';
    lines[lines.length - 1] = JSON.stringify(record);
    writeFileSync(fx.journalPath, `${lines.join('\n')}\n`, 'utf8');

    assert.throws(
      () => createPartitionDecisionFrame({
        authority: fx.authority,
        authorityTrustStore: fx.authorityTrustStore,
        observation: denied,
        nodeTrustStore: fx.nodeTrustStore,
        decision,
        journalPath: fx.journalPath,
        capturedAt: '2026-08-01T00:00:04.000Z',
      }),
      /journal identity is invalid|journal signature is invalid/,
    );
  } finally {
    fx.cleanup();
  }
});
