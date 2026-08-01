#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

const SHA256 = /^[0-9a-f]{64}$/;
const LINK_STATES = new Set(['up', 'down']);
const PARTITION_POLICIES = new Set(['buffer', 'drop']);
const MODES = new Set(['test', 'rehearsal']);
const BEHAVIORS = new Set(['pass', 'drop', 'duplicate', 'delay']);
const DROP_REASONS = new Set(['explicit_fault', 'link_down', 'queue_capacity']);
const EVENT_PHASE = 'apply_event_then_release_due';
const MAX_QUEUE_CAPACITY = 1_024;
const MAX_DUPLICATE_COPIES = 8;

const RUN_KEYS = new Set([
  'schema',
  'runId',
  'scenarioId',
  'scenarioDigest',
  'mode',
  'profileId',
  'portId',
  'standardId',
  'artifactUseId',
  'initialLinkState',
  'partitionPolicy',
  'queueCapacity',
  'eventPhase',
  'packetIds',
  'sendOrder',
  'deliveries',
  'drops',
  'pending',
  'metrics',
  'journalRoot',
  'journal',
  'claimBoundary',
]);
const FRAME_KEYS = new Set([
  'schema',
  'frameId',
  'runId',
  'scenarioId',
  'scenarioDigest',
  'mode',
  'profileId',
  'portId',
  'standardId',
  'artifactUseId',
  'eventPhase',
  'status',
  'metrics',
  'journalRoot',
  'lastEvent',
  'claimBoundary',
]);
const METRIC_KEYS = new Set([
  'sentPackets',
  'deliveredCopies',
  'deliveredUniquePackets',
  'droppedPackets',
  'explicitDrops',
  'linkDownDrops',
  'queueCapacityDrops',
  'duplicateExtraCopies',
  'delayedPackets',
  'bufferedPackets',
  'pendingDelayedPackets',
  'pendingBufferedPackets',
  'reordered',
  'finalLinkState',
]);
const PENDING_KEYS = new Set(['delayedPacketIds', 'bufferedPacketIds']);
const LAST_EVENT_KEYS = new Set(['recordId', 'step', 'type']);
const JOURNAL_KEYS = new Set(['schema', 'recordId', 'recordIndex', 'previousRecordId', 'step', 'type', 'detail']);
const DELIVERY_KEYS = new Set([
  'schema',
  'deliveryId',
  'packetId',
  'messageIdentity',
  'payloadDigest',
  'sendStep',
  'deliveryStep',
  'copyIndex',
  'copies',
  'delayed',
  'buffered',
]);
const DROP_KEYS = new Set([
  'schema',
  'dropId',
  'packetId',
  'messageIdentity',
  'sendStep',
  'dropStep',
  'copies',
  'delayed',
  'buffered',
  'reason',
]);
const DETAIL_KEYS = new Map([
  ['link', new Set(['priorState', 'state'])],
  ['send', new Set(['packetId', 'messageIdentity', 'behavior'])],
  ['drop', new Set(['dropId', 'packetId', 'reason'])],
  ['buffer', new Set(['packetId', 'queueDepth', 'queueCapacity'])],
  ['deliver', new Set(['deliveryId', 'packetId', 'copyIndex', 'delayed', 'buffered'])],
  ['dequeue', new Set(['packetId', 'queueDepth'])],
  ['delay_schedule', new Set(['packetId', 'releaseAt'])],
  ['delay_release', new Set(['packetId', 'scheduledReleaseAt'])],
]);
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

function exactKeys(value, allowed, code, label) {
  requireCondition(isRecord(value), code, `${label} must be an object`);
  const actual = Object.keys(value);
  const unexpected = actual.filter((key) => !allowed.has(key)).sort();
  requireCondition(unexpected.length === 0, code, `${label} contains unsupported field ${unexpected[0]}`);
  const missing = [...allowed].filter((key) => !Object.prototype.hasOwnProperty.call(value, key));
  requireCondition(missing.length === 0, code, `${label} is missing field ${missing[0]}`);
}

function boundedString(value, code, label) {
  requireCondition(typeof value === 'string' && value.trim().length > 0, code, `${label} must be a non-empty string`);
  return value;
}

function prefixedDigest(value, prefix, code, label) {
  requireCondition(
    typeof value === 'string' && new RegExp(`^${prefix}_[0-9a-f]{64}$`).test(value),
    code,
    `${label} is not a ${prefix} digest`,
  );
  return value;
}

function nonNegativeInteger(value, code, label) {
  requireCondition(Number.isSafeInteger(value) && value >= 0, code, `${label} must be a non-negative safe integer`);
  return value;
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

function verifyDeliveries(deliveries) {
  requireCondition(Array.isArray(deliveries), 'DELIVERIES_INVALID', 'deliveries must be an array');
  const byId = new Map();
  for (const [index, delivery] of deliveries.entries()) {
    exactKeys(delivery, DELIVERY_KEYS, 'DELIVERY_FIELDS_INVALID', `delivery ${index}`);
    requireCondition(delivery.schema === 'standards-port-fault-delivery/1', 'DELIVERY_SCHEMA_INVALID', 'delivery schema is invalid');
    prefixedDigest(delivery.packetId, 'standardtestpacket1', 'DELIVERY_PACKET_INVALID', 'delivery packetId');
    boundedString(delivery.messageIdentity, 'DELIVERY_MESSAGE_INVALID', 'delivery messageIdentity');
    requireCondition(SHA256.test(delivery.payloadDigest), 'DELIVERY_PAYLOAD_DIGEST_INVALID', 'delivery payload digest is invalid');
    nonNegativeInteger(delivery.sendStep, 'DELIVERY_STEP_INVALID', 'delivery sendStep');
    nonNegativeInteger(delivery.deliveryStep, 'DELIVERY_STEP_INVALID', 'delivery deliveryStep');
    requireCondition(delivery.deliveryStep >= delivery.sendStep, 'DELIVERY_STEP_INVALID', 'delivery precedes send');
    requireCondition(
      Number.isSafeInteger(delivery.copies)
        && delivery.copies >= 1
        && delivery.copies <= MAX_DUPLICATE_COPIES,
      'DELIVERY_COPY_INVALID',
      'delivery copies is invalid',
    );
    requireCondition(
      Number.isSafeInteger(delivery.copyIndex)
        && delivery.copyIndex >= 0
        && delivery.copyIndex < delivery.copies,
      'DELIVERY_COPY_INVALID',
      'delivery copyIndex is invalid',
    );
    requireCondition(typeof delivery.delayed === 'boolean', 'DELIVERY_FLAG_INVALID', 'delivery delayed flag is invalid');
    requireCondition(typeof delivery.buffered === 'boolean', 'DELIVERY_FLAG_INVALID', 'delivery buffered flag is invalid');
    const { deliveryId: _deliveryId, schema: _schema, ...body } = delivery;
    prefixedDigest(delivery.deliveryId, 'standardfaultdelivery1', 'DELIVERY_ID_INVALID', 'delivery deliveryId');
    requireCondition(delivery.deliveryId === digest('standardfaultdelivery1', body), 'DELIVERY_ID_INVALID', 'delivery identity is invalid');
    requireCondition(!byId.has(delivery.deliveryId), 'DELIVERY_DUPLICATE_ID', 'delivery identity is duplicated');
    byId.set(delivery.deliveryId, delivery);
  }
  return byId;
}

function verifyDrops(drops) {
  requireCondition(Array.isArray(drops), 'DROPS_INVALID', 'drops must be an array');
  const byId = new Map();
  for (const [index, dropped] of drops.entries()) {
    exactKeys(dropped, DROP_KEYS, 'DROP_FIELDS_INVALID', `drop ${index}`);
    requireCondition(dropped.schema === 'standards-port-fault-drop/1', 'DROP_SCHEMA_INVALID', 'drop schema is invalid');
    prefixedDigest(dropped.packetId, 'standardtestpacket1', 'DROP_PACKET_INVALID', 'drop packetId');
    boundedString(dropped.messageIdentity, 'DROP_MESSAGE_INVALID', 'drop messageIdentity');
    nonNegativeInteger(dropped.sendStep, 'DROP_STEP_INVALID', 'drop sendStep');
    nonNegativeInteger(dropped.dropStep, 'DROP_STEP_INVALID', 'drop dropStep');
    requireCondition(dropped.dropStep >= dropped.sendStep, 'DROP_STEP_INVALID', 'drop precedes send');
    requireCondition(
      Number.isSafeInteger(dropped.copies)
        && dropped.copies >= 1
        && dropped.copies <= MAX_DUPLICATE_COPIES,
      'DROP_COPY_INVALID',
      'drop copies is invalid',
    );
    requireCondition(typeof dropped.delayed === 'boolean', 'DROP_FLAG_INVALID', 'drop delayed flag is invalid');
    requireCondition(typeof dropped.buffered === 'boolean', 'DROP_FLAG_INVALID', 'drop buffered flag is invalid');
    requireCondition(DROP_REASONS.has(dropped.reason), 'DROP_REASON_INVALID', 'drop reason is invalid');
    const { dropId: _dropId, schema: _schema, ...body } = dropped;
    prefixedDigest(dropped.dropId, 'standardfaultdrop1', 'DROP_ID_INVALID', 'drop dropId');
    requireCondition(dropped.dropId === digest('standardfaultdrop1', body), 'DROP_ID_INVALID', 'drop identity is invalid');
    requireCondition(!byId.has(dropped.dropId), 'DROP_DUPLICATE_ID', 'drop identity is duplicated');
    byId.set(dropped.dropId, dropped);
  }
  return byId;
}

function verifyJournal(run, deliveriesById, dropsById) {
  requireCondition(Array.isArray(run.journal), 'JOURNAL_INVALID', 'fault journal must be an array');
  let previousRecordId = '0'.repeat(64);
  let previousStep = -1;
  let linkState = run.initialLinkState;
  const queue = [];
  const scheduled = new Map();
  const sent = new Map();
  const sendOrder = [];
  const deliveryJournalIds = new Set();
  const dropJournalIds = new Set();
  const bufferedPacketIds = new Set();
  const delayedPacketIds = new Set();
  let currentStep = null;
  let primarySeenAtStep = false;
  let delayReleaseSeenAtStep = false;

  for (let index = 0; index < run.journal.length; index += 1) {
    const record = run.journal[index];
    exactKeys(record, JOURNAL_KEYS, 'JOURNAL_RECORD_FIELDS_INVALID', `journal record ${index}`);
    requireCondition(record.schema === 'standards-port-fault-record/1', 'JOURNAL_RECORD_SCHEMA_INVALID', `journal record ${index} is invalid`);
    requireCondition(record.recordIndex === index, 'JOURNAL_RECORD_INDEX_INVALID', `journal record ${index} has another index`);
    requireCondition(record.previousRecordId === previousRecordId, 'JOURNAL_CHAIN_INVALID', `journal record ${index} breaks the chain`);
    nonNegativeInteger(record.step, 'JOURNAL_STEP_INVALID', `journal record ${index} step`);
    requireCondition(record.step >= previousStep, 'JOURNAL_STEP_INVALID', `journal record ${index} has a regressing step`);
    requireCondition(DETAIL_KEYS.has(record.type), 'JOURNAL_RECORD_TYPE_INVALID', `journal record ${index} has unsupported type ${record.type}`);
    exactKeys(record.detail, DETAIL_KEYS.get(record.type), 'JOURNAL_DETAIL_FIELDS_INVALID', `${record.type} detail`);
    if (record.step !== currentStep) {
      currentStep = record.step;
      primarySeenAtStep = false;
      delayReleaseSeenAtStep = false;
    }
    if (!primarySeenAtStep) {
      requireCondition(
        record.type === 'send' || record.type === 'link',
        'JOURNAL_EVENT_PHASE_INVALID',
        `step ${record.step} does not begin with a scenario event`,
      );
      primarySeenAtStep = true;
    } else {
      requireCondition(
        record.type !== 'send' && record.type !== 'link',
        'JOURNAL_EVENT_PHASE_INVALID',
        `step ${record.step} contains more than one scenario event`,
      );
    }
    if (record.type === 'delay_release') delayReleaseSeenAtStep = true;
    requireCondition(
      !delayReleaseSeenAtStep || record.type !== 'dequeue',
      'JOURNAL_EVENT_PHASE_INVALID',
      'FIFO recovery may not occur after due-delay release at the same step',
    );
    const body = {
      recordIndex: record.recordIndex,
      previousRecordId: record.previousRecordId,
      step: record.step,
      type: record.type,
      detail: record.detail,
    };
    prefixedDigest(record.recordId, 'standardfaultrecord1', 'JOURNAL_RECORD_ID_INVALID', `journal record ${index} recordId`);
    requireCondition(record.recordId === digest('standardfaultrecord1', body), 'JOURNAL_RECORD_ID_INVALID', `journal record ${index} identity is invalid`);

    const detail = record.detail;
    if (record.type === 'link') {
      requireCondition(LINK_STATES.has(detail.priorState) && LINK_STATES.has(detail.state), 'JOURNAL_LINK_INVALID', 'journal link state is invalid');
      requireCondition(detail.priorState === linkState, 'JOURNAL_LINK_INVALID', 'journal link prior state does not match');
      requireCondition(detail.state !== detail.priorState, 'JOURNAL_LINK_INVALID', 'journal link transition is a no-op');
      linkState = detail.state;
    } else if (record.type === 'send') {
      prefixedDigest(detail.packetId, 'standardtestpacket1', 'JOURNAL_SEND_INVALID', 'send packetId');
      boundedString(detail.messageIdentity, 'JOURNAL_SEND_INVALID', 'send messageIdentity');
      requireCondition(BEHAVIORS.has(detail.behavior), 'JOURNAL_SEND_INVALID', 'send behavior is invalid');
      requireCondition(!sent.has(detail.packetId), 'JOURNAL_SEND_DUPLICATE', `packet ${detail.packetId} was sent twice`);
      sent.set(detail.packetId, {
        step: record.step,
        behavior: detail.behavior,
        messageIdentity: detail.messageIdentity,
      });
      sendOrder.push(detail.packetId);
    } else if (record.type === 'delay_schedule') {
      const send = sent.get(detail.packetId);
      requireCondition(send?.behavior === 'delay', 'JOURNAL_DELAY_INVALID', 'delay schedule does not follow a delay send');
      nonNegativeInteger(detail.releaseAt, 'JOURNAL_DELAY_INVALID', 'delay releaseAt');
      requireCondition(detail.releaseAt > send.step, 'JOURNAL_DELAY_INVALID', 'delay releaseAt does not follow send');
      requireCondition(record.step === send.step, 'JOURNAL_DELAY_INVALID', 'delay schedule step differs from send');
      requireCondition(!scheduled.has(detail.packetId), 'JOURNAL_DELAY_INVALID', 'packet was scheduled twice');
      scheduled.set(detail.packetId, { releaseAt: detail.releaseAt, sendStep: send.step });
      delayedPacketIds.add(detail.packetId);
    } else if (record.type === 'delay_release') {
      const pending = scheduled.get(detail.packetId);
      requireCondition(pending, 'JOURNAL_DELAY_INVALID', 'delay release has no schedule');
      requireCondition(detail.scheduledReleaseAt === pending.releaseAt, 'JOURNAL_DELAY_INVALID', 'delay release cites another schedule');
      requireCondition(record.step >= pending.releaseAt, 'JOURNAL_DELAY_INVALID', 'delay released before its schedule');
      scheduled.delete(detail.packetId);
    } else if (record.type === 'buffer') {
      requireCondition(run.partitionPolicy === 'buffer', 'JOURNAL_BUFFER_INVALID', 'buffer record exists under drop policy');
      requireCondition(linkState === 'down', 'JOURNAL_BUFFER_INVALID', 'buffer record exists while link is up');
      requireCondition(sent.has(detail.packetId), 'JOURNAL_BUFFER_INVALID', 'buffered packet was not sent');
      requireCondition(detail.queueCapacity === run.queueCapacity, 'JOURNAL_BUFFER_INVALID', 'buffer record uses another queue capacity');
      requireCondition(!queue.includes(detail.packetId), 'JOURNAL_BUFFER_INVALID', 'packet is already buffered');
      requireCondition(queue.length < run.queueCapacity, 'JOURNAL_BUFFER_INVALID', 'buffer exceeds queue capacity');
      queue.push(detail.packetId);
      requireCondition(detail.queueDepth === queue.length, 'JOURNAL_BUFFER_INVALID', 'buffer queue depth is invalid');
      bufferedPacketIds.add(detail.packetId);
    } else if (record.type === 'dequeue') {
      requireCondition(linkState === 'up', 'JOURNAL_DEQUEUE_INVALID', 'dequeue occurs while link is down');
      requireCondition(queue.length > 0, 'JOURNAL_DEQUEUE_INVALID', 'dequeue occurs on an empty queue');
      const expectedPacketId = queue.shift();
      requireCondition(detail.packetId === expectedPacketId, 'JOURNAL_DEQUEUE_INVALID', 'dequeue violates FIFO order');
      requireCondition(detail.queueDepth === queue.length, 'JOURNAL_DEQUEUE_INVALID', 'dequeue queue depth is invalid');
    } else if (record.type === 'deliver') {
      requireCondition(linkState === 'up', 'JOURNAL_DELIVERY_INVALID', 'delivery occurs while link is down');
      const delivery = deliveriesById.get(detail.deliveryId);
      requireCondition(delivery, 'JOURNAL_DELIVERY_INVALID', 'journal cites unknown delivery');
      requireCondition(!deliveryJournalIds.has(detail.deliveryId), 'JOURNAL_DELIVERY_INVALID', 'delivery appears twice in journal');
      requireCondition(detail.packetId === delivery.packetId, 'JOURNAL_DELIVERY_INVALID', 'journal delivery packet differs');
      requireCondition(detail.copyIndex === delivery.copyIndex, 'JOURNAL_DELIVERY_INVALID', 'journal delivery copy differs');
      requireCondition(detail.delayed === delivery.delayed, 'JOURNAL_DELIVERY_INVALID', 'journal delivery delayed flag differs');
      requireCondition(detail.buffered === delivery.buffered, 'JOURNAL_DELIVERY_INVALID', 'journal delivery buffered flag differs');
      requireCondition(record.step === delivery.deliveryStep, 'JOURNAL_DELIVERY_INVALID', 'journal delivery step differs');
      deliveryJournalIds.add(detail.deliveryId);
    } else if (record.type === 'drop') {
      const dropped = dropsById.get(detail.dropId);
      requireCondition(dropped, 'JOURNAL_DROP_INVALID', 'journal cites unknown drop');
      requireCondition(!dropJournalIds.has(detail.dropId), 'JOURNAL_DROP_INVALID', 'drop appears twice in journal');
      requireCondition(detail.packetId === dropped.packetId, 'JOURNAL_DROP_INVALID', 'journal drop packet differs');
      requireCondition(detail.reason === dropped.reason, 'JOURNAL_DROP_INVALID', 'journal drop reason differs');
      requireCondition(record.step === dropped.dropStep, 'JOURNAL_DROP_INVALID', 'journal drop step differs');
      if (dropped.reason === 'explicit_fault') {
        requireCondition(sent.get(dropped.packetId)?.behavior === 'drop', 'JOURNAL_DROP_INVALID', 'explicit drop does not follow drop behavior');
      } else if (dropped.reason === 'link_down') {
        requireCondition(linkState === 'down' && run.partitionPolicy === 'drop', 'JOURNAL_DROP_INVALID', 'link-down drop has invalid link or policy state');
      } else if (dropped.reason === 'queue_capacity') {
        requireCondition(linkState === 'down' && run.partitionPolicy === 'buffer', 'JOURNAL_DROP_INVALID', 'queue-capacity drop has invalid link or policy state');
        requireCondition(queue.length >= run.queueCapacity, 'JOURNAL_DROP_INVALID', 'queue-capacity drop occurred before the queue was full');
      }
      dropJournalIds.add(detail.dropId);
    }

    previousRecordId = record.recordId;
    previousStep = record.step;
  }

  requireCondition(canonicalJson(sendOrder) === canonicalJson(run.sendOrder), 'JOURNAL_SEND_ORDER_INVALID', 'journal send order differs from run');
  requireCondition(deliveryJournalIds.size === deliveriesById.size, 'JOURNAL_DELIVERY_CLOSURE_INVALID', 'delivery array and journal do not close');
  requireCondition(dropJournalIds.size === dropsById.size, 'JOURNAL_DROP_CLOSURE_INVALID', 'drop array and journal do not close');
  requireCondition(linkState === run.metrics.finalLinkState, 'JOURNAL_LINK_INVALID', 'final link state does not reconstruct');
  requireCondition(canonicalJson(queue) === canonicalJson(run.pending.bufferedPacketIds), 'JOURNAL_BUFFER_CLOSURE_INVALID', 'pending buffer does not reconstruct');

  const pendingDelayed = [...scheduled.entries()]
    .sort((left, right) =>
      left[1].releaseAt - right[1].releaseAt
      || left[1].sendStep - right[1].sendStep
      || left[0].localeCompare(right[0])
    )
    .map(([packetId]) => packetId);
  requireCondition(canonicalJson(pendingDelayed) === canonicalJson(run.pending.delayedPacketIds), 'JOURNAL_DELAY_CLOSURE_INVALID', 'pending delay schedule does not reconstruct');

  return {
    journalRoot: previousRecordId,
    sent,
    sendOrder,
    delayedPacketIds,
    bufferedPacketIds,
    finalLinkState: linkState,
  };
}

function verifyOutcomeClosure(run, journalState) {
  const packetIds = run.packetIds;
  const packetSet = new Set(packetIds);
  const sendSet = new Set(run.sendOrder);
  requireCondition(packetIds.length === sendSet.size, 'FAULT_RUN_PACKET_SET_INVALID', 'packet set and send order differ in size');
  requireCondition(canonicalJson(packetIds) === canonicalJson([...sendSet].sort()), 'FAULT_RUN_PACKET_SET_INVALID', 'packet IDs are not the sorted exact send set');

  const deliveredByPacket = new Map();
  for (const delivery of run.deliveries) {
    requireCondition(packetSet.has(delivery.packetId), 'DELIVERY_PACKET_UNKNOWN', 'delivery cites unknown packet');
    const send = journalState.sent.get(delivery.packetId);
    requireCondition(send, 'DELIVERY_PACKET_UNKNOWN', 'delivery packet was not sent');
    requireCondition(delivery.sendStep === send.step, 'DELIVERY_SEND_MISMATCH', 'delivery send step differs from journal');
    requireCondition(delivery.messageIdentity === send.messageIdentity, 'DELIVERY_SEND_MISMATCH', 'delivery message identity differs from journal');
    requireCondition(delivery.delayed === (send.behavior === 'delay'), 'DELIVERY_SEND_MISMATCH', 'delivery delayed flag differs from send behavior');
    requireCondition(
      delivery.buffered === journalState.bufferedPacketIds.has(delivery.packetId),
      'DELIVERY_SEND_MISMATCH',
      'delivery buffered flag differs from journal history',
    );
    if (send.behavior === 'duplicate') {
      requireCondition(delivery.copies >= 2, 'DELIVERY_COPY_INVALID', 'duplicate send did not retain duplicate copies');
    } else {
      requireCondition(delivery.copies === 1, 'DELIVERY_COPY_INVALID', 'non-duplicate send produced duplicate copies');
    }
    const group = deliveredByPacket.get(delivery.packetId) ?? [];
    group.push(delivery);
    deliveredByPacket.set(delivery.packetId, group);
  }
  for (const group of deliveredByPacket.values()) {
    const copies = group[0].copies;
    requireCondition(group.every((row) => row.copies === copies), 'DELIVERY_COPY_INVALID', 'delivery copies disagree within a packet');
    requireCondition(group.length === copies, 'DELIVERY_COPY_INVALID', 'delivery copies are incomplete');
    requireCondition(
      canonicalJson(group.map((row) => row.copyIndex).sort((a, b) => a - b))
        === canonicalJson(Array.from({ length: copies }, (_, index) => index)),
      'DELIVERY_COPY_INVALID',
      'delivery copy indices are incomplete',
    );
  }

  const droppedByPacket = new Map();
  for (const dropped of run.drops) {
    requireCondition(packetSet.has(dropped.packetId), 'DROP_PACKET_UNKNOWN', 'drop cites unknown packet');
    requireCondition(!droppedByPacket.has(dropped.packetId), 'DROP_PACKET_DUPLICATE', 'packet has multiple drop outcomes');
    const send = journalState.sent.get(dropped.packetId);
    requireCondition(send, 'DROP_PACKET_UNKNOWN', 'dropped packet was not sent');
    requireCondition(dropped.sendStep === send.step, 'DROP_SEND_MISMATCH', 'drop send step differs from journal');
    requireCondition(dropped.messageIdentity === send.messageIdentity, 'DROP_SEND_MISMATCH', 'drop message identity differs from journal');
    requireCondition(dropped.delayed === (send.behavior === 'delay'), 'DROP_SEND_MISMATCH', 'drop delayed flag differs from send behavior');
    requireCondition(dropped.buffered === false, 'DROP_SEND_MISMATCH', 'drop may not claim completed buffering');
    if (send.behavior === 'duplicate') {
      requireCondition(dropped.copies >= 2, 'DROP_COPY_INVALID', 'duplicate send lost its copy count');
    } else {
      requireCondition(dropped.copies === 1, 'DROP_COPY_INVALID', 'non-duplicate drop has duplicate copies');
    }
    droppedByPacket.set(dropped.packetId, dropped);
  }

  const pendingDelayed = new Set(run.pending.delayedPacketIds);
  const pendingBuffered = new Set(run.pending.bufferedPacketIds);
  requireCondition(pendingDelayed.size === run.pending.delayedPacketIds.length, 'FAULT_RUN_PENDING_INVALID', 'pending delayed packet IDs are duplicated');
  requireCondition(pendingBuffered.size === run.pending.bufferedPacketIds.length, 'FAULT_RUN_PENDING_INVALID', 'pending buffered packet IDs are duplicated');
  for (const packetId of [...pendingDelayed, ...pendingBuffered]) {
    requireCondition(packetSet.has(packetId), 'FAULT_RUN_PENDING_INVALID', 'pending state cites unknown packet');
  }

  const deliveredSet = new Set(deliveredByPacket.keys());
  const droppedSet = new Set(droppedByPacket.keys());
  for (const packetId of packetIds) {
    const categories = [
      deliveredSet.has(packetId),
      droppedSet.has(packetId),
      pendingDelayed.has(packetId),
      pendingBuffered.has(packetId),
    ].filter(Boolean).length;
    requireCondition(categories === 1, 'FAULT_RUN_OUTCOME_CLOSURE_INVALID', `packet ${packetId} does not have exactly one terminal or pending outcome`);
  }
}

function recomputeMetrics(run, journalState) {
  const deliveredOrder = firstUnique(run.deliveries.map((row) => row.packetId));
  const expectedDeliveredOrder = run.sendOrder.filter((packetId) => deliveredOrder.includes(packetId));
  return {
    sentPackets: run.sendOrder.length,
    deliveredCopies: run.deliveries.length,
    deliveredUniquePackets: new Set(run.deliveries.map((row) => row.packetId)).size,
    droppedPackets: run.drops.length,
    explicitDrops: run.drops.filter((row) => row.reason === 'explicit_fault').length,
    linkDownDrops: run.drops.filter((row) => row.reason === 'link_down').length,
    queueCapacityDrops: run.drops.filter((row) => row.reason === 'queue_capacity').length,
    duplicateExtraCopies: run.deliveries.filter((row) => row.copyIndex > 0).length,
    delayedPackets: journalState.delayedPacketIds.size,
    bufferedPackets: journalState.bufferedPacketIds.size,
    pendingDelayedPackets: run.pending.delayedPacketIds.length,
    pendingBufferedPackets: run.pending.bufferedPacketIds.length,
    reordered: canonicalJson(deliveredOrder) !== canonicalJson(expectedDeliveredOrder),
    finalLinkState: journalState.finalLinkState,
  };
}

export function verifyFaultRun(run) {
  exactKeys(run, RUN_KEYS, 'FAULT_RUN_FIELDS_INVALID', 'fault run');
  requireCondition(run.schema === 'standards-port-fault-run/1', 'FAULT_RUN_SCHEMA_INVALID', 'fault run schema is invalid');
  for (const key of ['scenarioId', 'mode', 'profileId', 'portId', 'standardId', 'artifactUseId', 'claimBoundary']) {
    boundedString(run[key], 'FAULT_RUN_FIELD_INVALID', `fault run field ${key}`);
  }
  prefixedDigest(run.runId, 'standardfaultrun1', 'FAULT_RUN_FIELD_INVALID', 'fault run runId');
  prefixedDigest(run.scenarioDigest, 'standardfaultscenario1', 'FAULT_RUN_FIELD_INVALID', 'fault run scenarioDigest');
  prefixedDigest(run.journalRoot, 'standardfaultrecord1', 'FAULT_RUN_JOURNAL_ROOT_INVALID', 'fault run journalRoot');
  requireCondition(MODES.has(run.mode), 'FAULT_RUN_MODE_INVALID', 'fault run mode is invalid');
  requireCondition(LINK_STATES.has(run.initialLinkState), 'FAULT_RUN_LINK_INVALID', 'fault run initial link state is invalid');
  requireCondition(PARTITION_POLICIES.has(run.partitionPolicy), 'FAULT_RUN_PARTITION_POLICY_INVALID', 'fault run partition policy is invalid');
  requireCondition(
    Number.isSafeInteger(run.queueCapacity) && run.queueCapacity >= 0 && run.queueCapacity <= MAX_QUEUE_CAPACITY,
    'FAULT_RUN_QUEUE_INVALID',
    'fault run queue capacity is invalid',
  );
  requireCondition(run.partitionPolicy !== 'drop' || run.queueCapacity === 0, 'FAULT_RUN_QUEUE_INVALID', 'drop policy retains an unused queue capacity');
  requireCondition(run.eventPhase === EVENT_PHASE, 'FAULT_RUN_EVENT_PHASE_INVALID', 'fault run event phase is invalid');
  requireCondition(Array.isArray(run.packetIds) && Array.isArray(run.sendOrder), 'FAULT_RUN_PACKET_SET_INVALID', 'fault run packet set is invalid');
  requireCondition(new Set(run.packetIds).size === run.packetIds.length, 'FAULT_RUN_PACKET_SET_INVALID', 'fault run packet IDs are not unique');
  for (const packetId of run.packetIds) {
    prefixedDigest(packetId, 'standardtestpacket1', 'FAULT_RUN_PACKET_SET_INVALID', 'fault run packetId');
  }
  requireCondition(new Set(run.sendOrder).size === run.sendOrder.length, 'FAULT_RUN_SEND_ORDER_INVALID', 'fault run sends a packet more than once');
  requireCondition(run.sendOrder.every((packetId) => run.packetIds.includes(packetId)), 'FAULT_RUN_SEND_ORDER_INVALID', 'fault run send order cites an unknown packet');

  exactKeys(run.pending, PENDING_KEYS, 'FAULT_RUN_PENDING_INVALID', 'fault run pending');
  requireCondition(Array.isArray(run.pending.delayedPacketIds) && Array.isArray(run.pending.bufferedPacketIds), 'FAULT_RUN_PENDING_INVALID', 'fault run pending lists are invalid');
  exactKeys(run.metrics, METRIC_KEYS, 'FAULT_RUN_METRICS_INVALID', 'fault run metrics');
  for (const key of [...METRIC_KEYS].filter((key) => !['reordered', 'finalLinkState'].includes(key))) {
    nonNegativeInteger(run.metrics[key], 'FAULT_RUN_METRICS_INVALID', `metric ${key}`);
  }
  requireCondition(typeof run.metrics.reordered === 'boolean', 'FAULT_RUN_METRICS_INVALID', 'metric reordered is invalid');
  requireCondition(LINK_STATES.has(run.metrics.finalLinkState), 'FAULT_RUN_METRICS_INVALID', 'metric finalLinkState is invalid');

  const deliveriesById = verifyDeliveries(run.deliveries);
  const dropsById = verifyDrops(run.drops);
  const journalState = verifyJournal(run, deliveriesById, dropsById);
  requireCondition(run.journalRoot === journalState.journalRoot, 'FAULT_RUN_JOURNAL_ROOT_INVALID', 'fault run journal root is invalid');
  verifyOutcomeClosure(run, journalState);
  const metrics = recomputeMetrics(run, journalState);
  requireCondition(canonicalJson(run.metrics) === canonicalJson(metrics), 'FAULT_RUN_METRICS_INVALID', 'fault run metrics do not reconstruct');

  const body = {
    scenarioId: run.scenarioId,
    scenarioDigest: run.scenarioDigest,
    mode: run.mode,
    profileId: run.profileId,
    portId: run.portId,
    standardId: run.standardId,
    artifactUseId: run.artifactUseId,
    initialLinkState: run.initialLinkState,
    partitionPolicy: run.partitionPolicy,
    queueCapacity: run.queueCapacity,
    eventPhase: run.eventPhase,
    packetIds: run.packetIds,
    sendOrder: run.sendOrder,
    deliveries: run.deliveries,
    drops: run.drops,
    pending: run.pending,
    metrics: run.metrics,
    journalRoot: run.journalRoot,
  };
  requireCondition(run.runId === digest('standardfaultrun1', body), 'FAULT_RUN_ID_INVALID', 'fault run identity does not match its contents');
  return {
    schema: 'standards-port-fault-run-verification/1',
    status: 'pass',
    runId: run.runId,
    scenarioDigest: run.scenarioDigest,
    journalRoot: run.journalRoot,
    journalRecords: run.journal.length,
    deliveries: run.deliveries.length,
    drops: run.drops.length,
    outcomeClosureVerified: true,
    metricsVerified: true,
    runIdentityVerified: true,
    claimBoundary:
      'This receipt verifies deterministic fault-run identities, journal transitions, outcome closure, and structural metrics. It does not validate payload semantics, operational performance, or authority.',
  };
}

export function verifyFaultFrame(frame, run) {
  const runReceipt = verifyFaultRun(run);
  assertReadOnlyFrame(frame);
  exactKeys(frame, FRAME_KEYS, 'FRAME_FIELDS_INVALID', 'test frame');
  requireCondition(frame.schema === 'standards-port-test-frame/1', 'FRAME_SCHEMA_INVALID', 'test frame schema is invalid');
  prefixedDigest(frame.frameId, 'standardporttestframe1', 'FRAME_ID_INVALID', 'test frame frameId');
  boundedString(frame.claimBoundary, 'FRAME_FIELD_INVALID', 'test frame claimBoundary');
  if (frame.lastEvent !== null) exactKeys(frame.lastEvent, LAST_EVENT_KEYS, 'FRAME_LAST_EVENT_INVALID', 'test frame lastEvent');
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
    scenarioDigest: run.scenarioDigest,
    mode: run.mode,
    profileId: run.profileId,
    portId: run.portId,
    standardId: run.standardId,
    artifactUseId: run.artifactUseId,
    eventPhase: run.eventPhase,
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
    status: 'pass',
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
