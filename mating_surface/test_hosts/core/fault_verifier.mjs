#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

const SHA256 = /^[0-9a-f]{64}$/;
const FORBIDDEN_FRAME_KEYS = new Set([
  'payload',
  'payloadbytes',
  'commandauthority',
  'targeting',
  'engagement',
  'effectorcontrol',
  'execute',
  'execution',
]);

export class FaultVerificationError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'FaultVerificationError';
    this.code = code;
  }
}

function requireCondition(condition, code, message) {
  if (!condition) throw new FaultVerificationError(code, message);
}

function isRecord(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

export function canonicalJson(value) {
  if (value === null) return 'null';
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`;
  if (typeof value === 'object') {
    requireCondition(isRecord(value), 'NON_JSON_VALUE', 'canonical JSON requires plain objects');
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
      .join(',')}}`;
  }
  if (typeof value === 'number') {
    requireCondition(Number.isFinite(value), 'NON_JSON_NUMBER', 'non-finite numbers are not admissible');
  }
  const encoded = JSON.stringify(value);
  requireCondition(encoded !== undefined, 'NON_JSON_VALUE', 'non-JSON values are not admissible');
  return encoded;
}

function digest(prefix, value) {
  return `${prefix}_${createHash('sha256').update(canonicalJson(value), 'utf8').digest('hex')}`;
}

function firstUnique(values) {
  const seen = new Set();
  const result = [];
  for (const value of values) {
    if (!seen.has(value)) {
      seen.add(value);
      result.push(value);
    }
  }
  return result;
}

function normalizedKey(key) {
  return key.replace(/[^a-z0-9]/gi, '').toLowerCase();
}

function assertReadOnlyFrame(value, path = '$') {
  if (Array.isArray(value)) {
    value.forEach((row, index) => assertReadOnlyFrame(row, `${path}[${index}]`));
    return;
  }
  if (!isRecord(value)) return;
  for (const [key, nested] of Object.entries(value)) {
    requireCondition(
      !FORBIDDEN_FRAME_KEYS.has(normalizedKey(key)),
      'FRAME_FORBIDDEN_FIELD',
      `read-only frame contains forbidden field ${key} at ${path}`,
    );
    assertReadOnlyFrame(nested, `${path}.${key}`);
  }
}

function verifyJournal(journal) {
  requireCondition(Array.isArray(journal), 'JOURNAL_INVALID', 'fault journal must be an array');
  let previousRecordId = '0'.repeat(64);
  let previousStep = -1;
  for (let index = 0; index < journal.length; index += 1) {
    const record = journal[index];
    requireCondition(
      isRecord(record) && record.schema === 'standards-port-fault-record/1',
      'JOURNAL_RECORD_SCHEMA_INVALID',
      `fault journal record ${index} is invalid`,
    );
    requireCondition(record.recordIndex === index, 'JOURNAL_RECORD_INDEX_INVALID', `journal record ${index} has another index`);
    requireCondition(record.previousRecordId === previousRecordId, 'JOURNAL_CHAIN_INVALID', `journal record ${index} breaks the chain`);
    requireCondition(Number.isInteger(record.step) && record.step >= previousStep, 'JOURNAL_STEP_INVALID', `journal record ${index} has a regressing step`);
    requireCondition(typeof record.type === 'string' && record.type, 'JOURNAL_RECORD_TYPE_INVALID', `journal record ${index} has no type`);
    requireCondition(isRecord(record.detail), 'JOURNAL_RECORD_DETAIL_INVALID', `journal record ${index} detail is invalid`);
    const body = {
      recordIndex: record.recordIndex,
      previousRecordId: record.previousRecordId,
      step: record.step,
      type: record.type,
      detail: record.detail,
    };
    requireCondition(
      record.recordId === digest('standardfaultrecord1', body),
      'JOURNAL_RECORD_ID_INVALID',
      `journal record ${index} identity is invalid`,
    );
    previousRecordId = record.recordId;
    previousStep = record.step;
  }
  return previousRecordId;
}

function verifyDeliveries(deliveries) {
  requireCondition(Array.isArray(deliveries), 'DELIVERIES_INVALID', 'deliveries must be an array');
  const ids = new Set();
  for (const delivery of deliveries) {
    requireCondition(
      isRecord(delivery) && delivery.schema === 'standards-port-fault-delivery/1',
      'DELIVERY_SCHEMA_INVALID',
      'delivery schema is invalid',
    );
    requireCondition(SHA256.test(delivery.payloadDigest), 'DELIVERY_PAYLOAD_DIGEST_INVALID', 'delivery payload digest is invalid');
    const { deliveryId: _deliveryId, schema: _schema, ...body } = delivery;
    requireCondition(
      delivery.deliveryId === digest('standardfaultdelivery1', body),
      'DELIVERY_ID_INVALID',
      'delivery identity is invalid',
    );
    requireCondition(!ids.has(delivery.deliveryId), 'DELIVERY_DUPLICATE_ID', 'delivery identity is duplicated');
    ids.add(delivery.deliveryId);
  }
}

function verifyDrops(drops) {
  requireCondition(Array.isArray(drops), 'DROPS_INVALID', 'drops must be an array');
  const ids = new Set();
  for (const dropped of drops) {
    requireCondition(
      isRecord(dropped) && dropped.schema === 'standards-port-fault-drop/1',
      'DROP_SCHEMA_INVALID',
      'drop schema is invalid',
    );
    const { dropId: _dropId, schema: _schema, ...body } = dropped;
    requireCondition(
      dropped.dropId === digest('standardfaultdrop1', body),
      'DROP_ID_INVALID',
      'drop identity is invalid',
    );
    requireCondition(!ids.has(dropped.dropId), 'DROP_DUPLICATE_ID', 'drop identity is duplicated');
    ids.add(dropped.dropId);
  }
}

function recomputeMetrics(run) {
  const deliveredOrder = firstUnique(run.deliveries.map((row) => row.packetId));
  const expectedDeliveredOrder = run.sendOrder.filter((packetId) => deliveredOrder.includes(packetId));
  const delayedPackets = new Set(
    run.journal
      .filter((row) => row.type === 'delay_schedule')
      .map((row) => row.detail.packetId),
  );
  const bufferedPackets = new Set(
    run.journal
      .filter((row) => row.type === 'buffer')
      .map((row) => row.detail.packetId),
  );
  const linkRecords = run.journal.filter((row) => row.type === 'link');
  const finalLinkState = linkRecords.length > 0
    ? linkRecords.at(-1).detail.state
    : run.metrics.finalLinkState;
  return {
    sentPackets: run.sendOrder.length,
    deliveredCopies: run.deliveries.length,
    deliveredUniquePackets: new Set(run.deliveries.map((row) => row.packetId)).size,
    droppedPackets: run.drops.length,
    explicitDrops: run.drops.filter((row) => row.reason === 'explicit_fault').length,
    linkDownDrops: run.drops.filter((row) => row.reason === 'link_down').length,
    queueCapacityDrops: run.drops.filter((row) => row.reason === 'queue_capacity').length,
    duplicateExtraCopies: run.deliveries.filter((row) => row.copyIndex > 0).length,
    delayedPackets: delayedPackets.size,
    bufferedPackets: bufferedPackets.size,
    pendingDelayedPackets: run.pending.delayedPacketIds.length,
    pendingBufferedPackets: run.pending.bufferedPacketIds.length,
    reordered: canonicalJson(deliveredOrder) !== canonicalJson(expectedDeliveredOrder),
    finalLinkState,
  };
}

export function verifyFaultRun(run) {
  requireCondition(
    isRecord(run) && run.schema === 'standards-port-fault-run/1',
    'FAULT_RUN_SCHEMA_INVALID',
    'fault run schema is invalid',
  );
  for (const key of ['runId', 'scenarioId', 'mode', 'profileId', 'portId', 'standardId', 'artifactUseId']) {
    requireCondition(typeof run[key] === 'string' && run[key], 'FAULT_RUN_FIELD_INVALID', `fault run field ${key} is invalid`);
  }
  requireCondition(Array.isArray(run.packetIds) && Array.isArray(run.sendOrder), 'FAULT_RUN_PACKET_SET_INVALID', 'fault run packet set is invalid');
  requireCondition(new Set(run.packetIds).size === run.packetIds.length, 'FAULT_RUN_PACKET_SET_INVALID', 'fault run packet IDs are not unique');
  requireCondition(new Set(run.sendOrder).size === run.sendOrder.length, 'FAULT_RUN_SEND_ORDER_INVALID', 'fault run sends a packet more than once');
  requireCondition(run.sendOrder.every((packetId) => run.packetIds.includes(packetId)), 'FAULT_RUN_SEND_ORDER_INVALID', 'fault run send order cites an unknown packet');
  requireCondition(isRecord(run.pending), 'FAULT_RUN_PENDING_INVALID', 'fault run pending state is invalid');
  requireCondition(Array.isArray(run.pending.delayedPacketIds) && Array.isArray(run.pending.bufferedPacketIds), 'FAULT_RUN_PENDING_INVALID', 'fault run pending lists are invalid');

  verifyDeliveries(run.deliveries);
  verifyDrops(run.drops);
  const journalRoot = verifyJournal(run.journal);
  requireCondition(run.journalRoot === journalRoot, 'FAULT_RUN_JOURNAL_ROOT_INVALID', 'fault run journal root is invalid');
  const metrics = recomputeMetrics(run);
  requireCondition(canonicalJson(run.metrics) === canonicalJson(metrics), 'FAULT_RUN_METRICS_INVALID', 'fault run metrics do not reconstruct');

  const body = {
    scenarioId: run.scenarioId,
    mode: run.mode,
    profileId: run.profileId,
    portId: run.portId,
    standardId: run.standardId,
    artifactUseId: run.artifactUseId,
    packetIds: run.packetIds,
    sendOrder: run.sendOrder,
    deliveries: run.deliveries,
    drops: run.drops,
    metrics: run.metrics,
    journalRoot: run.journalRoot,
  };
  requireCondition(
    run.runId === digest('standardfaultrun1', body),
    'FAULT_RUN_ID_INVALID',
    'fault run identity does not match its contents',
  );
  return {
    schema: 'standards-port-fault-run-verification/1',
    runId: run.runId,
    journalRoot,
    journalRecords: run.journal.length,
    deliveries: run.deliveries.length,
    drops: run.drops.length,
    metricsVerified: true,
    runIdentityVerified: true,
    claimBoundary:
      'This receipt verifies the deterministic fault-run identities, journal chain, and structural metrics. It does not validate payload semantics, operational performance, or authority.',
  };
}

export function verifyFaultFrame(frame, run) {
  const runReceipt = verifyFaultRun(run);
  requireCondition(
    isRecord(frame) && frame.schema === 'standards-port-test-frame/1',
    'FRAME_SCHEMA_INVALID',
    'test frame schema is invalid',
  );
  assertReadOnlyFrame(frame);
  const expectedStatus =
    run.metrics.pendingDelayedPackets === 0 && run.metrics.pendingBufferedPackets === 0
      ? 'complete'
      : 'pending';
  const expectedLastEvent = run.journal.length > 0
    ? {
        recordId: run.journal.at(-1).recordId,
        step: run.journal.at(-1).step,
        type: run.journal.at(-1).type,
      }
    : null;
  const body = {
    runId: run.runId,
    scenarioId: run.scenarioId,
    mode: run.mode,
    profileId: run.profileId,
    portId: run.portId,
    standardId: run.standardId,
    artifactUseId: run.artifactUseId,
    status: expectedStatus,
    metrics: run.metrics,
    journalRoot: run.journalRoot,
    lastEvent: expectedLastEvent,
  };
  requireCondition(frame.frameId === digest('standardporttestframe1', body), 'FRAME_ID_INVALID', 'test frame identity is invalid');
  for (const [key, value] of Object.entries(body)) {
    requireCondition(canonicalJson(frame[key]) === canonicalJson(value), 'FRAME_RUN_MISMATCH', `test frame field ${key} differs from the verified run`);
  }
  return {
    schema: 'standards-port-test-frame-verification/1',
    frameId: frame.frameId,
    runId: run.runId,
    runVerification: runReceipt,
    frameIdentityVerified: true,
    readOnlyBoundaryVerified: true,
    claimBoundary:
      'This receipt verifies one read-only test-host frame against a detached fault run. It grants no payload, provider, command, targeting, engagement, effector, or execution surface.',
  };
}

async function main(argv) {
  if (argv.length < 2 || argv.length > 3) {
    console.error('usage: fault_verifier.mjs <fault-run.json> <test-frame.json> [verification.json]');
    return 2;
  }
  const [runPath, framePath, outputPath] = argv;
  try {
    const [run, frame] = await Promise.all([
      readFile(runPath, 'utf8').then(JSON.parse),
      readFile(framePath, 'utf8').then(JSON.parse),
    ]);
    const receipt = verifyFaultFrame(frame, run);
    if (outputPath) await writeFile(outputPath, `${JSON.stringify(receipt, null, 2)}\n`, 'utf8');
    process.stdout.write(`${JSON.stringify(receipt, null, 2)}\n`);
    return 0;
  } catch (error) {
    const receipt = {
      schema: 'standards-port-test-frame-verification/1',
      status: 'refuse',
      error: error instanceof FaultVerificationError ? error.code : 'FAULT_VERIFICATION_FAILED',
      message: error instanceof Error ? error.message : 'fault verification failed',
    };
    if (outputPath) await writeFile(outputPath, `${JSON.stringify(receipt, null, 2)}\n`, 'utf8');
    process.stderr.write(`${JSON.stringify(receipt, null, 2)}\n`);
    return 1;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exitCode = await main(process.argv.slice(2));
}
