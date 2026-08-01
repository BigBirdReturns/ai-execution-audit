import assert from 'node:assert/strict';
import { generateKeyPairSync } from 'node:crypto';
import {
  appendFileSync,
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
  PartitionAuthorityRuntime,
  signAuthorityEnvelope,
  signLinkObservation,
  verifyLinkObservation,
} from './partition_runtime.mjs';

function pemPair() {
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
        {
          id: 'total-isolation',
          states: { headquarters: 'down', 'local-control': 'down' },
          partition: true,
          allowedActionClasses: [],
          maxOfflineMs: 1_000,
          requiresLocalOperator: false,
          expiryDisposition: 'safe_state',
        },
      ],
    },
    ...overrides,
  };
}

function trust(authorityKeys, nodeKeys) {
  return {
    authorityTrustStore: {
      schema: 'axm-authority-trust/1',
      keys: [
        {
          keyId: 'authority-key-1',
          issuer: 'fixture-commander',
          algorithm: 'Ed25519',
          publicKeyPem: authorityKeys.publicKeyPem,
        },
      ],
    },
    nodeTrustStore: {
      schema: 'axm-node-trust/1',
      keys: [
        {
          keyId: 'node-key-1',
          nodeId: 'fixture-node-1',
          algorithm: 'Ed25519',
          publicKeyPem: nodeKeys.publicKeyPem,
        },
      ],
    },
  };
}

function observation(nodeKeys, observedAt, links, localOperatorPresent = true) {
  return signLinkObservation(
    {
      schema: 'axm-link-observation/1',
      nodeId: 'fixture-node-1',
      observedAt,
      links,
      localOperatorPresent,
    },
    'node-key-1',
    nodeKeys.privateKeyPem,
  );
}

function fixture() {
  const root = mkdtempSync(join(tmpdir(), 'polybolos-partition-'));
  const journalPath = join(root, 'partition.journal');
  const authorityKeys = pemPair();
  const nodeKeys = pemPair();
  const stores = trust(authorityKeys, nodeKeys);
  let clockMs = Date.parse('2026-08-01T00:00:02.000Z');
  const clock = () => clockMs;
  const setClock = (value) => {
    clockMs = Date.parse(value);
  };
  const authority = signAuthorityEnvelope(
    authorityBody(),
    'authority-key-1',
    authorityKeys.privateKeyPem,
  );
  const runtimeConfig = {
    journalPath,
    nodeId: 'fixture-node-1',
    journalKeyId: 'node-key-1',
    journalPrivateKeyPem: nodeKeys.privateKeyPem,
    nodeTrustStore: stores.nodeTrustStore,
    authorityTrustStore: stores.authorityTrustStore,
    clock,
  };
  return {
    root,
    journalPath,
    authorityKeys,
    nodeKeys,
    authority,
    transaction: transaction(),
    runtimeConfig,
    setClock,
    cleanup() {
      rmSync(root, { recursive: true, force: true });
    },
  };
}

test('owns one partition epoch across repeated observations, restart, expiry, and reconciliation', () => {
  const fx = fixture();
  try {
    let runtime = new PartitionAuthorityRuntime(fx.runtimeConfig);
    runtime.observe(
      observation(
        fx.nodeKeys,
        '2026-08-01T00:00:02.000Z',
        { headquarters: 'up', 'local-control': 'up' },
      ),
      fx.authority,
    );
    assert.equal(runtime.evaluate(fx.transaction, fx.authority).disposition, 'allow');

    fx.setClock('2026-08-01T00:00:03.000Z');
    const firstPartition = runtime.observe(
      observation(
        fx.nodeKeys,
        '2026-08-01T00:00:03.000Z',
        { headquarters: 'down', 'local-control': 'up' },
      ),
      fx.authority,
    );
    assert.equal(firstPartition.profileId, 'headquarters-denied');
    const epochId = firstPartition.activeEpochId;
    assert.ok(epochId);
    assert.equal(runtime.evaluate(fx.transaction, fx.authority).disposition, 'allow');

    fx.setClock('2026-08-01T00:00:05.000Z');
    const repeated = runtime.observe(
      observation(
        fx.nodeKeys,
        '2026-08-01T00:00:05.000Z',
        { headquarters: 'down', 'local-control': 'up' },
      ),
      fx.authority,
    );
    assert.equal(repeated.activeEpochId, epochId);
    assert.equal(runtime.snapshot().activeEpoch.startedAt, '2026-08-01T00:00:03.000Z');
    runtime.close();

    fx.setClock('2026-08-01T00:00:07.000Z');
    runtime = new PartitionAuthorityRuntime(fx.runtimeConfig);
    assert.equal(runtime.snapshot().activeEpoch.epochId, epochId);
    assert.equal(runtime.snapshot().activeEpoch.startedAt, '2026-08-01T00:00:03.000Z');
    assert.equal(runtime.evaluate(fx.transaction, fx.authority).disposition, 'allow');

    fx.setClock('2026-08-01T00:00:09.000Z');
    const expired = runtime.evaluate(fx.transaction, fx.authority);
    assert.equal(expired.disposition, 'safe_state');
    assert.equal(expired.reason.code, 'partition_offline_lease_expired');

    runtime.observe(
      observation(
        fx.nodeKeys,
        '2026-08-01T00:00:09.000Z',
        { headquarters: 'up', 'local-control': 'up' },
      ),
      fx.authority,
    );
    assert.equal(runtime.snapshot().activeEpoch, null);
    assert.equal(runtime.snapshot().pendingReconciliation.epoch.epochId, epochId);

    const returningAuthority = signAuthorityEnvelope(
      authorityBody({ supersedes: [fx.authority.authorityId] }),
      'authority-key-1',
      fx.authorityKeys.privateKeyPem,
    );
    const reconciliation = runtime.reconcile(returningAuthority);
    assert.equal(reconciliation.disposition, 'explicitly_superseded');
    assert.equal(reconciliation.priorAuthorityId, fx.authority.authorityId);
    assert.equal(reconciliation.returningAuthorityId, returningAuthority.authorityId);
    assert.ok(reconciliation.localDecisionIds.length >= 3);
    assert.equal(runtime.snapshot().pendingReconciliation, null);
    runtime.close();
  } finally {
    fx.cleanup();
  }
});

test('refuses action when the signed profile requires a missing local operator', () => {
  const fx = fixture();
  try {
    const runtime = new PartitionAuthorityRuntime(fx.runtimeConfig);
    fx.setClock('2026-08-01T00:00:03.000Z');
    runtime.observe(
      observation(
        fx.nodeKeys,
        '2026-08-01T00:00:03.000Z',
        { headquarters: 'down', 'local-control': 'up' },
        false,
      ),
      fx.authority,
    );
    const decision = runtime.evaluate(fx.transaction, fx.authority);
    assert.equal(decision.disposition, 'safe_state');
    assert.equal(decision.reason.code, 'partition_local_operator_absent');
    runtime.close();
  } finally {
    fx.cleanup();
  }
});

test('refuses an action class that does not survive total isolation', () => {
  const fx = fixture();
  try {
    const runtime = new PartitionAuthorityRuntime(fx.runtimeConfig);
    fx.setClock('2026-08-01T00:00:03.000Z');
    runtime.observe(
      observation(
        fx.nodeKeys,
        '2026-08-01T00:00:03.000Z',
        { headquarters: 'down', 'local-control': 'down' },
        false,
      ),
      fx.authority,
    );
    const decision = runtime.evaluate(fx.transaction, fx.authority);
    assert.equal(decision.disposition, 'refuse');
    assert.equal(decision.reason.code, 'partition_action_not_surviving');
    runtime.close();
  } finally {
    fx.cleanup();
  }
});

test('refuses a tampered signed link observation', () => {
  const fx = fixture();
  try {
    const signed = observation(
      fx.nodeKeys,
      '2026-08-01T00:00:02.000Z',
      { headquarters: 'up', 'local-control': 'up' },
    );
    signed.links.headquarters = 'down';
    assert.throws(
      () => verifyLinkObservation(signed, fx.runtimeConfig.nodeTrustStore),
      /signature did not verify|identity does not match/,
    );
  } finally {
    fx.cleanup();
  }
});

test('refuses a second writer on the same partition journal', () => {
  const fx = fixture();
  try {
    const first = new PartitionAuthorityRuntime(fx.runtimeConfig);
    assert.throws(
      () => new PartitionAuthorityRuntime(fx.runtimeConfig),
      /already owned/,
    );
    first.close();
  } finally {
    fx.cleanup();
  }
});

test('refuses a rewritten complete journal record', () => {
  const fx = fixture();
  try {
    const runtime = new PartitionAuthorityRuntime(fx.runtimeConfig);
    runtime.observe(
      observation(
        fx.nodeKeys,
        '2026-08-01T00:00:02.000Z',
        { headquarters: 'up', 'local-control': 'up' },
      ),
      fx.authority,
    );
    runtime.close();

    const lines = readFileSync(fx.journalPath, 'utf8').trimEnd().split('\n');
    const record = JSON.parse(lines.at(-1));
    record.stateAfter.currentProfileId = 'forged-profile';
    lines[lines.length - 1] = JSON.stringify(record);
    writeFileSync(fx.journalPath, `${lines.join('\n')}\n`, 'utf8');

    assert.throws(
      () => new PartitionAuthorityRuntime(fx.runtimeConfig),
      /identity is invalid|signature did not verify/,
    );
  } finally {
    fx.cleanup();
  }
});

test('recovers an incomplete journal tail without rewriting the valid prefix', () => {
  const fx = fixture();
  try {
    const runtime = new PartitionAuthorityRuntime(fx.runtimeConfig);
    runtime.observe(
      observation(
        fx.nodeKeys,
        '2026-08-01T00:00:02.000Z',
        { headquarters: 'up', 'local-control': 'up' },
      ),
      fx.authority,
    );
    runtime.close();
    const prefix = readFileSync(fx.journalPath);
    const tail = Buffer.from('{"incomplete":', 'utf8');
    appendFileSync(fx.journalPath, tail);

    const recovered = new PartitionAuthorityRuntime(fx.runtimeConfig);
    assert.equal(recovered.snapshot().diagnostics.truncatedTailBytes, tail.length);
    recovered.close();
    assert.deepEqual(readFileSync(fx.journalPath), prefix);
  } finally {
    fx.cleanup();
  }
});
