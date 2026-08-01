import assert from 'node:assert/strict';
import test from 'node:test';
import {
  FaultMachineError,
  createFaultFrame,
  createTestPacket,
  runFaultScenario,
  validateFaultScenario,
  verifyTestPacket,
} from '../core/fault_machine.mjs';

const ARTIFACT_SHA = '1'.repeat(64);
const artifactTransaction = {
  schema: 'standards-mating-surface-artifact-transaction/1',
  status: 'pass',
  admission: {
    schema: 'standards-mating-surface-artifact-admission/1',
    admissionId: 'standardartifactadmission1_fixture',
    standardId: 'siso-std-019-2020-c2sim',
    standardRevision: 'C2SIM fixture revision',
    artifactSha256: ARTIFACT_SHA,
  },
  use: {
    schema: 'standards-mating-surface-artifact-use/1',
    useId: 'standardartifactuse1_fixture',
    profileId: 'joint-edge-command-authority/0.1',
    mode: 'rehearsal',
    portId: 'simulation-and-rehearsal',
  },
};
const catalog = {
  schema: 'standards-mating-surface-xsd11-catalog/1',
  catalogId: 'standardxsd11catalog1_fixture',
  artifactAdmissionId: artifactTransaction.admission.admissionId,
  artifactUseId: artifactTransaction.use.useId,
  artifactSha256: ARTIFACT_SHA,
  standardId: artifactTransaction.admission.standardId,
};

function packet(index, payloadText = `opaque-transport-fixture-${index}`) {
  const payload = Buffer.from(payloadText, 'utf8');
  const receipt = createTestPacket({
    artifactTransaction,
    catalog,
    payload,
    messageIdentity: `fixture-message-${index}`,
    sourceSystemId: 'synthetic-test-source',
    observedAt: `2026-08-01T00:00:${String(index).padStart(2, '0')}Z`,
  });
  return { receipt, payload };
}

function fixtureSet(count = 7) {
  const rows = Array.from({ length: count }, (_, index) => packet(index + 1));
  return {
    packets: rows.map((row) => row.receipt),
    payloads: new Map(rows.map((row) => [row.receipt.packetId, row.payload])),
  };
}

function scenario(packetIds) {
  return {
    schema: 'standards-port-fault-scenario/1',
    scenarioId: 'rehearsal-partition-delay-duplicate-queue',
    mode: 'rehearsal',
    profileId: artifactTransaction.use.profileId,
    portId: artifactTransaction.use.portId,
    standardId: artifactTransaction.admission.standardId,
    artifactUseId: artifactTransaction.use.useId,
    initialLinkState: 'up',
    partitionPolicy: 'buffer',
    queueCapacity: 2,
    events: [
      { step: 0, type: 'send', packetId: packetIds[0], behavior: 'pass' },
      { step: 1, type: 'send', packetId: packetIds[1], behavior: 'duplicate', copies: 2 },
      { step: 2, type: 'send', packetId: packetIds[2], behavior: 'delay', releaseAt: 7 },
      { step: 3, type: 'link', state: 'down' },
      { step: 4, type: 'send', packetId: packetIds[3], behavior: 'pass' },
      { step: 5, type: 'send', packetId: packetIds[4], behavior: 'pass' },
      { step: 6, type: 'send', packetId: packetIds[5], behavior: 'pass' },
      { step: 7, type: 'link', state: 'up' },
      { step: 8, type: 'send', packetId: packetIds[6], behavior: 'drop' },
    ],
    claimBoundary: 'synthetic transport fault fixture only',
  };
}

function runFixture() {
  const set = fixtureSet();
  return runFaultScenario({
    scenario: scenario(set.packets.map((row) => row.packetId)),
    packets: set.packets,
    payloads: set.payloads,
    artifactTransaction,
    catalog,
  });
}

test('runs a deterministic drop, duplicate, delay, partition, queue, and reconnect sequence', () => {
  const first = runFixture();
  const second = runFixture();
  assert.equal(first.runId, second.runId);
  assert.equal(first.journalRoot, second.journalRoot);
  assert.deepEqual(first.metrics, {
    sentPackets: 7,
    deliveredCopies: 6,
    deliveredUniquePackets: 5,
    droppedPackets: 2,
    explicitDrops: 1,
    linkDownDrops: 0,
    queueCapacityDrops: 1,
    duplicateExtraCopies: 1,
    delayedPackets: 1,
    bufferedPackets: 2,
    pendingDelayedPackets: 0,
    pendingBufferedPackets: 0,
    reordered: true,
    finalLinkState: 'up',
  });
  assert.deepEqual(
    first.deliveries.map((row) => row.messageIdentity),
    [
      'fixture-message-1',
      'fixture-message-2',
      'fixture-message-2',
      'fixture-message-4',
      'fixture-message-5',
      'fixture-message-3',
    ],
  );
  assert.deepEqual(first.drops.map((row) => row.reason), ['queue_capacity', 'explicit_fault']);
  assert.equal(first.journal.at(-1).recordId, first.journalRoot);
});

test('creates a read-only frame without payload bytes or provider surface state', () => {
  const run = runFixture();
  const frame = createFaultFrame(run);
  const encoded = JSON.stringify(frame);
  assert.equal(frame.schema, 'standards-port-test-frame/1');
  assert.equal(frame.status, 'complete');
  assert.equal(frame.metrics.deliveredCopies, 6);
  assert.equal(encoded.includes('opaque-transport-fixture'), false);
  assert.equal('payload' in frame, false);
  assert.equal('commandAuthority' in frame, false);
  assert.match(frame.claimBoundary, /replaceable test hosts/);
});

test('refuses payload substitution after packet binding', () => {
  const row = packet(1, 'original-payload');
  assert.throws(
    () => verifyTestPacket(
      row.receipt,
      Buffer.from('altered-payload', 'utf8'),
      artifactTransaction,
      catalog,
    ),
    (error) => error instanceof FaultMachineError && error.code === 'PACKET_IDENTITY_INVALID',
  );
});

test('refuses operational use of a rehearsal artifact', () => {
  const operational = structuredClone(artifactTransaction);
  operational.use.mode = 'operational';
  assert.throws(
    () => createTestPacket({
      artifactTransaction: operational,
      catalog,
      payload: Buffer.from('fixture', 'utf8'),
      messageIdentity: 'message-1',
      sourceSystemId: 'source-1',
      observedAt: '2026-08-01T00:00:00Z',
    }),
    (error) => error instanceof FaultMachineError && error.code === 'ARTIFACT_TRANSACTION_INVALID',
  );
});

test('refuses packets bound to another standard, port, profile, or artifact use', () => {
  const set = fixtureSet(1);
  const base = scenario([set.packets[0].packetId]);
  base.events = [{ step: 0, type: 'send', packetId: set.packets[0].packetId, behavior: 'pass' }];
  for (const [field, value] of [
    ['standardId', 'another-standard'],
    ['portId', 'another-port'],
    ['profileId', 'another-profile'],
    ['artifactUseId', 'another-use'],
  ]) {
    const changed = { ...base, [field]: value };
    assert.throws(
      () => runFaultScenario({
        scenario: changed,
        packets: set.packets,
        payloads: set.payloads,
        artifactTransaction,
        catalog,
      }),
      (error) => error instanceof FaultMachineError && error.code === 'PACKET_SCENARIO_MISMATCH',
    );
  }
});

test('leaves delayed and buffered packets visibly pending when no recovery event occurs', () => {
  const set = fixtureSet(2);
  const pendingScenario = {
    schema: 'standards-port-fault-scenario/1',
    scenarioId: 'pending-partition',
    mode: 'rehearsal',
    profileId: artifactTransaction.use.profileId,
    portId: artifactTransaction.use.portId,
    standardId: artifactTransaction.admission.standardId,
    artifactUseId: artifactTransaction.use.useId,
    initialLinkState: 'down',
    partitionPolicy: 'buffer',
    queueCapacity: 2,
    events: [
      { step: 0, type: 'send', packetId: set.packets[0].packetId, behavior: 'pass' },
      { step: 1, type: 'send', packetId: set.packets[1].packetId, behavior: 'delay', releaseAt: 10 },
    ],
  };
  const run = runFaultScenario({
    scenario: pendingScenario,
    packets: set.packets,
    payloads: set.payloads,
    artifactTransaction,
    catalog,
  });
  assert.equal(run.metrics.pendingBufferedPackets, 1);
  assert.equal(run.metrics.pendingDelayedPackets, 1);
  assert.equal(createFaultFrame(run).status, 'pending');
});

test('refuses unknown scenario fields and ambiguous event shapes', () => {
  const set = fixtureSet(1);
  const base = scenario([set.packets[0].packetId]);
  base.events = [{ step: 0, type: 'send', packetId: set.packets[0].packetId, behavior: 'pass' }];
  assert.throws(
    () => validateFaultScenario({ ...base, providerUi: true }),
    (error) => error instanceof FaultMachineError && error.code === 'SCENARIO_FIELDS_INVALID',
  );
  assert.throws(
    () => validateFaultScenario({
      ...base,
      events: [{ step: 0, type: 'send', packetId: set.packets[0].packetId, behavior: 'pass', copies: 2 }],
    }),
    (error) => error instanceof FaultMachineError && error.code === 'SCENARIO_BEHAVIOR_INVALID',
  );
});
