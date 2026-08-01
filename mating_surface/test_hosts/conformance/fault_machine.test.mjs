import assert from 'node:assert/strict';
import test from 'node:test';
import {
  FaultMachineError,
  createFaultFrame,
  createTestPacket,
  deriveFaultScenarioDigest,
  runFaultScenario,
  validateFaultScenario,
  verifyTestPacket,
} from '../core/fault_machine.mjs';
import {
  FaultVerificationError,
  verifyFaultFrame,
  verifyFaultRun,
} from '../core/fault_verifier.mjs';

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
    rows,
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
  const inputScenario = scenario(set.packets.map((row) => row.packetId));
  const run = runFaultScenario({
    scenario: inputScenario,
    packets: set.packets,
    payloads: set.payloads,
    artifactTransaction,
    catalog,
  });
  return { set, inputScenario, run, frame: createFaultFrame(run) };
}

test('runs and independently verifies the full deterministic transport-fault sequence', () => {
  const first = runFixture();
  const second = runFixture();
  assert.equal(first.run.runId, second.run.runId);
  assert.equal(first.run.journalRoot, second.run.journalRoot);
  assert.equal(first.frame.frameId, second.frame.frameId);
  assert.equal(first.run.scenarioDigest, deriveFaultScenarioDigest(first.inputScenario));
  assert.deepEqual(first.run.metrics, {
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
    first.run.deliveries.map((row) => row.messageIdentity),
    [
      'fixture-message-1',
      'fixture-message-2',
      'fixture-message-2',
      'fixture-message-4',
      'fixture-message-5',
      'fixture-message-3',
    ],
  );
  assert.deepEqual(first.run.drops.map((row) => row.reason), ['queue_capacity', 'explicit_fault']);
  const verification = verifyFaultFrame(first.frame, first.run);
  assert.equal(verification.status, 'pass');
  assert.equal(verification.runVerification.outcomeClosureVerified, true);
});

test('defines same-step recovery as event application, FIFO flush, then due-delay release', () => {
  const { run } = runFixture();
  const stepSeven = run.journal.filter((row) => row.step === 7).map((row) => row.type);
  assert.deepEqual(stepSeven, ['link', 'dequeue', 'deliver', 'dequeue', 'deliver', 'delay_release', 'deliver']);
  assert.equal(run.eventPhase, 'apply_event_then_release_due');
});

test('creates a read-only frame without payload bytes or provider surface state', () => {
  const { set, run, frame } = runFixture();
  const encoded = JSON.stringify(frame);
  assert.equal(frame.schema, 'standards-port-test-frame/1');
  assert.equal(frame.status, 'complete');
  assert.equal(frame.metrics.deliveredCopies, 6);
  for (const row of set.rows) {
    assert.equal(encoded.includes(row.payload.toString('utf8')), false);
  }
  assert.equal('payload' in frame, false);
  assert.equal('commandAuthority' in frame, false);
  assert.equal(frame.scenarioDigest, run.scenarioDigest);
});

test('refuses payload substitution with a payload-specific error', () => {
  const row = packet(1, 'original-payload');
  assert.throws(
    () => verifyTestPacket(
      row.receipt,
      Buffer.from('altered-payload', 'utf8'),
      artifactTransaction,
      catalog,
    ),
    (error) => error instanceof FaultMachineError && error.code === 'PACKET_PAYLOAD_MISMATCH',
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

test('requires the packet and payload sets to exactly match scenario sends', () => {
  const set = fixtureSet(2);
  const onePacketScenario = {
    ...scenario([set.packets[0].packetId]),
    events: [{ step: 0, type: 'send', packetId: set.packets[0].packetId, behavior: 'pass' }],
  };
  assert.throws(
    () => runFaultScenario({
      scenario: onePacketScenario,
      packets: set.packets,
      payloads: set.payloads,
      artifactTransaction,
      catalog,
    }),
    (error) => error instanceof FaultMachineError && error.code === 'PACKET_SET_NOT_EXACT',
  );

  const onePacket = fixtureSet(1);
  onePacket.payloads.set('unknown-packet', Buffer.from('extra', 'utf8'));
  assert.throws(
    () => runFaultScenario({
      scenario: {
        ...scenario([onePacket.packets[0].packetId]),
        events: [{ step: 0, type: 'send', packetId: onePacket.packets[0].packetId, behavior: 'pass' }],
      },
      packets: onePacket.packets,
      payloads: onePacket.payloads,
      artifactTransaction,
      catalog,
    }),
    (error) => error instanceof FaultMachineError && error.code === 'PAYLOAD_SET_NOT_EXACT',
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

test('keeps unresolved delay and buffer state inside the run identity', () => {
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
    claimBoundary: 'pending fixture',
  };
  const run = runFaultScenario({
    scenario: pendingScenario,
    packets: set.packets,
    payloads: set.payloads,
    artifactTransaction,
    catalog,
  });
  assert.deepEqual(run.pending, {
    delayedPacketIds: [set.packets[1].packetId],
    bufferedPacketIds: [set.packets[0].packetId],
  });
  assert.equal(createFaultFrame(run).status, 'pending');
  assert.equal(verifyFaultRun(run).status, 'pass');

  const altered = structuredClone(run);
  [altered.pending.delayedPacketIds[0], altered.pending.bufferedPacketIds[0]] = [
    altered.pending.bufferedPacketIds[0],
    altered.pending.delayedPacketIds[0],
  ];
  assert.throws(
    () => verifyFaultRun(altered),
    (error) => error instanceof FaultVerificationError
      && ['JOURNAL_BUFFER_CLOSURE_INVALID', 'JOURNAL_DELAY_CLOSURE_INVALID', 'FAULT_RUN_ID_INVALID'].includes(error.code),
  );
});

test('executes drop-policy partition behavior without retaining unused queue state', () => {
  const set = fixtureSet(1);
  const dropScenario = {
    schema: 'standards-port-fault-scenario/1',
    scenarioId: 'drop-policy-partition',
    mode: 'rehearsal',
    profileId: artifactTransaction.use.profileId,
    portId: artifactTransaction.use.portId,
    standardId: artifactTransaction.admission.standardId,
    artifactUseId: artifactTransaction.use.useId,
    initialLinkState: 'down',
    partitionPolicy: 'drop',
    queueCapacity: 0,
    events: [{ step: 0, type: 'send', packetId: set.packets[0].packetId, behavior: 'pass' }],
    claimBoundary: 'drop policy fixture',
  };
  const run = runFaultScenario({
    scenario: dropScenario,
    packets: set.packets,
    payloads: set.payloads,
    artifactTransaction,
    catalog,
  });
  assert.equal(run.metrics.linkDownDrops, 1);
  assert.equal(run.metrics.pendingBufferedPackets, 0);
  assert.equal(run.metrics.finalLinkState, 'down');
  assert.equal(verifyFaultRun(run).status, 'pass');
});

test('refuses no-op link events, unused queue capacity, and ambiguous event fields', () => {
  const set = fixtureSet(1);
  const base = {
    ...scenario([set.packets[0].packetId]),
    events: [{ step: 0, type: 'send', packetId: set.packets[0].packetId, behavior: 'pass' }],
  };
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
  assert.throws(
    () => validateFaultScenario({
      ...base,
      events: [{ step: 0, type: 'link', state: 'up' }],
    }),
    (error) => error instanceof FaultMachineError && error.code === 'SCENARIO_LINK_NOOP',
  );
  assert.throws(
    () => validateFaultScenario({
      ...base,
      partitionPolicy: 'drop',
      queueCapacity: 1,
    }),
    (error) => error instanceof FaultMachineError && error.code === 'SCENARIO_QUEUE_UNUSED',
  );
});

test('detached verification refuses journal, delivery, run-field, and frame-surface tampering', () => {
  const { run, frame } = runFixture();

  const journalTamper = structuredClone(run);
  journalTamper.journal[0].detail.behavior = 'drop';
  assert.throws(
    () => verifyFaultRun(journalTamper),
    (error) => error instanceof FaultVerificationError && error.code === 'JOURNAL_RECORD_ID_INVALID',
  );

  const deliveryTamper = structuredClone(run);
  deliveryTamper.deliveries[1].copyIndex = 1;
  assert.throws(
    () => verifyFaultRun(deliveryTamper),
    (error) => error instanceof FaultVerificationError
      && ['DELIVERY_ID_INVALID', 'DELIVERY_DUPLICATE_ID'].includes(error.code),
  );

  const fieldTamper = { ...structuredClone(run), providerUi: true };
  assert.throws(
    () => verifyFaultRun(fieldTamper),
    (error) => error instanceof FaultVerificationError && error.code === 'FAULT_RUN_FIELDS_INVALID',
  );

  const frameTamper = structuredClone(frame);
  frameTamper.lastEvent.payload = 'forbidden';
  assert.throws(
    () => verifyFaultFrame(frameTamper, run),
    (error) => error instanceof FaultVerificationError && error.code === 'FRAME_FORBIDDEN_FIELD',
  );
});

test('scenario digest changes when executable scenario content changes but ignores explanatory prose', () => {
  const set = fixtureSet(1);
  const base = {
    ...scenario([set.packets[0].packetId]),
    events: [{ step: 0, type: 'send', packetId: set.packets[0].packetId, behavior: 'pass' }],
  };
  const proseOnly = { ...base, claimBoundary: 'different explanation' };
  const changed = {
    ...base,
    events: [{ step: 0, type: 'send', packetId: set.packets[0].packetId, behavior: 'drop' }],
  };
  assert.equal(deriveFaultScenarioDigest(base), deriveFaultScenarioDigest(proseOnly));
  assert.notEqual(deriveFaultScenarioDigest(base), deriveFaultScenarioDigest(changed));
});
