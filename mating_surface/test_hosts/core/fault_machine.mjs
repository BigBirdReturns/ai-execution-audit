import { createHash } from 'node:crypto';

const SHA256 = /^[0-9a-f]{64}$/;
const LINK_STATES = new Set(['up', 'down']);
const PARTITION_POLICIES = new Set(['buffer', 'drop']);
const MODES = new Set(['test', 'rehearsal']);
const BEHAVIORS = new Set(['pass', 'drop', 'duplicate', 'delay']);
const MAX_PAYLOAD_BYTES = 1024 * 1024;
const MAX_EVENTS = 10_000;
const MAX_QUEUE_CAPACITY = 1_024;
const MAX_DUPLICATE_COPIES = 8;

export class FaultMachineError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'FaultMachineError';
    this.code = code;
  }
}

function requireCondition(condition, code, message) {
  if (!condition) throw new FaultMachineError(code, message);
}

function isRecord(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function canonicalJson(value) {
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

function sha256(bytes) {
  requireCondition(Buffer.isBuffer(bytes), 'PAYLOAD_BYTES_INVALID', 'payload must be a Buffer');
  return createHash('sha256').update(bytes).digest('hex');
}

function exactKeys(value, allowed, code, label) {
  requireCondition(isRecord(value), code, `${label} must be an object`);
  const unexpected = Object.keys(value).filter((key) => !allowed.has(key)).sort();
  requireCondition(unexpected.length === 0, code, `${label} contains unsupported field ${unexpected[0]}`);
}

function boundedString(value, code, label, max = 512) {
  requireCondition(typeof value === 'string', code, `${label} must be a string`);
  const normalized = value.trim();
  requireCondition(normalized.length > 0 && normalized.length <= max, code, `${label} is empty or unbounded`);
  return normalized;
}

function normalizedDateTime(value, code, label) {
  requireCondition(typeof value === 'string', code, `${label} must be a date-time string`);
  const milliseconds = Date.parse(value);
  requireCondition(Number.isFinite(milliseconds), code, `${label} is not a valid date-time`);
  return new Date(milliseconds).toISOString();
}

function validateArtifactTransaction(transaction, catalog) {
  requireCondition(
    isRecord(transaction)
      && transaction.schema === 'standards-mating-surface-artifact-transaction/1'
      && transaction.status === 'pass',
    'ARTIFACT_TRANSACTION_INVALID',
    'artifact transaction is invalid',
  );
  const admission = transaction.admission;
  const use = transaction.use;
  requireCondition(
    isRecord(admission)
      && admission.schema === 'standards-mating-surface-artifact-admission/1'
      && typeof admission.admissionId === 'string'
      && SHA256.test(admission.artifactSha256),
    'ARTIFACT_TRANSACTION_INVALID',
    'artifact admission is invalid',
  );
  requireCondition(
    isRecord(use)
      && use.schema === 'standards-mating-surface-artifact-use/1'
      && MODES.has(use.mode)
      && typeof use.useId === 'string',
    'ARTIFACT_TRANSACTION_INVALID',
    'artifact use receipt is invalid or not test/rehearsal scoped',
  );
  requireCondition(
    isRecord(catalog)
      && catalog.schema === 'standards-mating-surface-xsd11-catalog/1'
      && typeof catalog.catalogId === 'string',
    'STANDARD_CATALOG_INVALID',
    'standard catalog is invalid',
  );
  requireCondition(
    catalog.artifactAdmissionId === admission.admissionId
      && catalog.artifactUseId === use.useId
      && catalog.artifactSha256 === admission.artifactSha256
      && catalog.standardId === admission.standardId,
    'STANDARD_CATALOG_MISMATCH',
    'standard catalog does not belong to the admitted artifact transaction',
  );
  return { admission, use };
}

function packetIdentityBody(packet) {
  const { packetId: _packetId, claimBoundary: _claimBoundary, ...body } = packet;
  return body;
}

export function deriveTestPacketId(packet) {
  return digest('standardtestpacket1', packetIdentityBody(packet));
}

export function createTestPacket({
  artifactTransaction,
  catalog,
  payload,
  messageIdentity,
  sourceSystemId,
  observedAt,
}) {
  const { admission, use } = validateArtifactTransaction(artifactTransaction, catalog);
  requireCondition(Buffer.isBuffer(payload), 'PAYLOAD_BYTES_INVALID', 'payload must be a Buffer');
  requireCondition(payload.length > 0 && payload.length <= MAX_PAYLOAD_BYTES, 'PAYLOAD_BYTES_INVALID', 'payload is empty or exceeds 1 MiB');
  const body = {
    schema: 'standards-port-test-packet/1',
    profileId: boundedString(use.profileId, 'PACKET_PROFILE_INVALID', 'profileId'),
    portId: boundedString(use.portId, 'PACKET_PORT_INVALID', 'portId'),
    standardId: boundedString(admission.standardId, 'PACKET_STANDARD_INVALID', 'standardId'),
    standardRevision: boundedString(admission.standardRevision, 'PACKET_STANDARD_INVALID', 'standardRevision'),
    artifactAdmissionId: boundedString(admission.admissionId, 'PACKET_ARTIFACT_INVALID', 'artifactAdmissionId'),
    artifactUseId: boundedString(use.useId, 'PACKET_ARTIFACT_INVALID', 'artifactUseId'),
    artifactSha256: admission.artifactSha256,
    catalogId: boundedString(catalog.catalogId, 'PACKET_CATALOG_INVALID', 'catalogId'),
    messageIdentity: boundedString(messageIdentity, 'PACKET_MESSAGE_ID_INVALID', 'messageIdentity'),
    sourceSystemId: boundedString(sourceSystemId, 'PACKET_SOURCE_INVALID', 'sourceSystemId'),
    observedAt: normalizedDateTime(observedAt, 'PACKET_TIME_INVALID', 'observedAt'),
    payloadDigest: sha256(payload),
    payloadBytes: payload.length,
    validationClass: 'opaque_transport_fixture',
  };
  const packet = {
    ...body,
    packetId: '',
    claimBoundary:
      'This packet binds opaque synthetic bytes to one admitted rehearsal artifact for transport-fault testing. It is not represented as a schema-valid command message and carries no authority.',
  };
  packet.packetId = deriveTestPacketId(packet);
  return packet;
}

export function verifyTestPacket(packet, payload, artifactTransaction, catalog) {
  requireCondition(
    isRecord(packet) && packet.schema === 'standards-port-test-packet/1',
    'PACKET_SCHEMA_INVALID',
    'test packet schema is invalid',
  );
  requireCondition(
    packet.validationClass === 'opaque_transport_fixture',
    'PACKET_VALIDATION_CLASS_INVALID',
    'test packet validation class is unsupported',
  );
  const rebuilt = createTestPacket({
    artifactTransaction,
    catalog,
    payload,
    messageIdentity: packet.messageIdentity,
    sourceSystemId: packet.sourceSystemId,
    observedAt: packet.observedAt,
  });
  requireCondition(packet.packetId === rebuilt.packetId, 'PACKET_IDENTITY_INVALID', 'test packet identity does not match its contents');
  requireCondition(packet.payloadDigest === rebuilt.payloadDigest, 'PACKET_PAYLOAD_MISMATCH', 'payload bytes do not match the test packet');
  requireCondition(packet.payloadBytes === rebuilt.payloadBytes, 'PACKET_PAYLOAD_MISMATCH', 'payload length does not match the test packet');
  return packet;
}

const SCENARIO_KEYS = new Set([
  'schema',
  'scenarioId',
  'mode',
  'profileId',
  'portId',
  'standardId',
  'artifactUseId',
  'initialLinkState',
  'partitionPolicy',
  'queueCapacity',
  'events',
  'claimBoundary',
]);
const LINK_EVENT_KEYS = new Set(['step', 'type', 'state']);
const SEND_EVENT_KEYS = new Set(['step', 'type', 'packetId', 'behavior', 'copies', 'releaseAt']);

export function validateFaultScenario(scenario) {
  exactKeys(scenario, SCENARIO_KEYS, 'SCENARIO_FIELDS_INVALID', 'scenario');
  requireCondition(
    scenario.schema === 'standards-port-fault-scenario/1',
    'SCENARIO_SCHEMA_INVALID',
    'fault scenario schema is invalid',
  );
  boundedString(scenario.scenarioId, 'SCENARIO_ID_INVALID', 'scenarioId');
  requireCondition(MODES.has(scenario.mode), 'SCENARIO_MODE_INVALID', 'scenario mode must be test or rehearsal');
  for (const key of ['profileId', 'portId', 'standardId', 'artifactUseId']) {
    boundedString(scenario[key], 'SCENARIO_BINDING_INVALID', key);
  }
  requireCondition(LINK_STATES.has(scenario.initialLinkState), 'SCENARIO_LINK_INVALID', 'initial link state is invalid');
  requireCondition(PARTITION_POLICIES.has(scenario.partitionPolicy), 'SCENARIO_PARTITION_POLICY_INVALID', 'partition policy is invalid');
  requireCondition(
    Number.isInteger(scenario.queueCapacity)
      && scenario.queueCapacity >= 0
      && scenario.queueCapacity <= MAX_QUEUE_CAPACITY,
    'SCENARIO_QUEUE_INVALID',
    `queueCapacity must be an integer between 0 and ${MAX_QUEUE_CAPACITY}`,
  );
  requireCondition(
    Array.isArray(scenario.events)
      && scenario.events.length > 0
      && scenario.events.length <= MAX_EVENTS,
    'SCENARIO_EVENTS_INVALID',
    `scenario must contain between 1 and ${MAX_EVENTS} events`,
  );

  let priorStep = -1;
  const sentPacketIds = new Set();
  for (const event of scenario.events) {
    requireCondition(isRecord(event), 'SCENARIO_EVENT_INVALID', 'scenario event must be an object');
    requireCondition(Number.isInteger(event.step) && event.step >= 0, 'SCENARIO_EVENT_INVALID', 'event step is invalid');
    requireCondition(event.step > priorStep, 'SCENARIO_EVENT_ORDER_INVALID', 'event steps must be strictly increasing');
    priorStep = event.step;

    if (event.type === 'link') {
      exactKeys(event, LINK_EVENT_KEYS, 'SCENARIO_EVENT_FIELDS_INVALID', 'link event');
      requireCondition(LINK_STATES.has(event.state), 'SCENARIO_LINK_INVALID', 'link event state is invalid');
      continue;
    }
    requireCondition(event.type === 'send', 'SCENARIO_EVENT_TYPE_INVALID', `unsupported event type ${event.type}`);
    exactKeys(event, SEND_EVENT_KEYS, 'SCENARIO_EVENT_FIELDS_INVALID', 'send event');
    const packetId = boundedString(event.packetId, 'SCENARIO_PACKET_INVALID', 'packetId');
    requireCondition(!sentPacketIds.has(packetId), 'SCENARIO_PACKET_DUPLICATE', `packet ${packetId} is sent more than once`);
    sentPacketIds.add(packetId);
    requireCondition(BEHAVIORS.has(event.behavior), 'SCENARIO_BEHAVIOR_INVALID', 'send behavior is invalid');

    if (event.behavior === 'duplicate') {
      requireCondition(
        Number.isInteger(event.copies)
          && event.copies >= 2
          && event.copies <= MAX_DUPLICATE_COPIES,
        'SCENARIO_DUPLICATE_INVALID',
        `duplicate copies must be between 2 and ${MAX_DUPLICATE_COPIES}`,
      );
      requireCondition(event.releaseAt === undefined, 'SCENARIO_BEHAVIOR_INVALID', 'duplicate behavior may not set releaseAt');
    } else if (event.behavior === 'delay') {
      requireCondition(
        Number.isInteger(event.releaseAt) && event.releaseAt > event.step,
        'SCENARIO_DELAY_INVALID',
        'delay releaseAt must be an integer after the send step',
      );
      requireCondition(event.copies === undefined, 'SCENARIO_BEHAVIOR_INVALID', 'delay behavior may not set copies');
    } else {
      requireCondition(event.copies === undefined, 'SCENARIO_BEHAVIOR_INVALID', `${event.behavior} behavior may not set copies`);
      requireCondition(event.releaseAt === undefined, 'SCENARIO_BEHAVIOR_INVALID', `${event.behavior} behavior may not set releaseAt`);
    }
  }
  return scenario;
}

function validatePacketSet(packets, payloads, artifactTransaction, catalog, scenario) {
  requireCondition(Array.isArray(packets) && packets.length > 0, 'PACKET_SET_INVALID', 'packet set is empty');
  requireCondition(payloads instanceof Map, 'PACKET_SET_INVALID', 'payloads must be a Map keyed by packetId');
  const byId = new Map();
  for (const packet of packets) {
    requireCondition(!byId.has(packet.packetId), 'PACKET_SET_DUPLICATE', `duplicate packet ${packet.packetId}`);
    const payload = payloads.get(packet.packetId);
    requireCondition(Buffer.isBuffer(payload), 'PACKET_PAYLOAD_MISSING', `payload is missing for packet ${packet.packetId}`);
    verifyTestPacket(packet, payload, artifactTransaction, catalog);
    requireCondition(packet.profileId === scenario.profileId, 'PACKET_SCENARIO_MISMATCH', 'packet profile differs from the scenario');
    requireCondition(packet.portId === scenario.portId, 'PACKET_SCENARIO_MISMATCH', 'packet port differs from the scenario');
    requireCondition(packet.standardId === scenario.standardId, 'PACKET_SCENARIO_MISMATCH', 'packet standard differs from the scenario');
    requireCondition(packet.artifactUseId === scenario.artifactUseId, 'PACKET_SCENARIO_MISMATCH', 'packet artifact use differs from the scenario');
    byId.set(packet.packetId, packet);
  }
  for (const event of scenario.events) {
    if (event.type === 'send') {
      requireCondition(byId.has(event.packetId), 'SCENARIO_PACKET_UNKNOWN', `scenario cites unknown packet ${event.packetId}`);
    }
  }
  return byId;
}

function createJournalAppender(journal) {
  return function append(step, type, detail) {
    const body = {
      recordIndex: journal.length,
      previousRecordId: journal.at(-1)?.recordId ?? '0'.repeat(64),
      step,
      type,
      detail,
    };
    const record = {
      schema: 'standards-port-fault-record/1',
      recordId: digest('standardfaultrecord1', body),
      ...body,
    };
    journal.push(record);
    return record;
  };
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

export function runFaultScenario({
  scenario,
  packets,
  payloads,
  artifactTransaction,
  catalog,
}) {
  validateFaultScenario(scenario);
  const packetById = validatePacketSet(packets, payloads, artifactTransaction, catalog, scenario);
  let linkState = scenario.initialLinkState;
  const queue = [];
  const scheduled = [];
  const journal = [];
  const append = createJournalAppender(journal);
  const deliveries = [];
  const drops = [];
  const sendOrder = [];
  const bufferedPacketIds = new Set();
  const delayedPacketIds = new Set();

  function dropAttempt(attempt, step, reason) {
    const body = {
      packetId: attempt.packet.packetId,
      messageIdentity: attempt.packet.messageIdentity,
      sendStep: attempt.sendStep,
      dropStep: step,
      copies: attempt.copies,
      delayed: attempt.delayed,
      buffered: attempt.buffered,
      reason,
    };
    const dropped = {
      schema: 'standards-port-fault-drop/1',
      dropId: digest('standardfaultdrop1', body),
      ...body,
    };
    drops.push(dropped);
    append(step, 'drop', {
      dropId: dropped.dropId,
      packetId: dropped.packetId,
      reason,
    });
  }

  function deliverAttempt(attempt, step) {
    if (linkState === 'down') {
      if (scenario.partitionPolicy === 'buffer' && queue.length < scenario.queueCapacity) {
        const queued = { ...attempt, buffered: true };
        queue.push(queued);
        bufferedPacketIds.add(attempt.packet.packetId);
        append(step, 'buffer', {
          packetId: attempt.packet.packetId,
          queueDepth: queue.length,
          queueCapacity: scenario.queueCapacity,
        });
      } else {
        const reason = scenario.partitionPolicy === 'buffer' ? 'queue_capacity' : 'link_down';
        dropAttempt(attempt, step, reason);
      }
      return;
    }

    for (let copyIndex = 0; copyIndex < attempt.copies; copyIndex += 1) {
      const body = {
        packetId: attempt.packet.packetId,
        messageIdentity: attempt.packet.messageIdentity,
        payloadDigest: attempt.packet.payloadDigest,
        sendStep: attempt.sendStep,
        deliveryStep: step,
        copyIndex,
        copies: attempt.copies,
        delayed: attempt.delayed,
        buffered: attempt.buffered,
      };
      const delivery = {
        schema: 'standards-port-fault-delivery/1',
        deliveryId: digest('standardfaultdelivery1', body),
        ...body,
      };
      deliveries.push(delivery);
      append(step, 'deliver', {
        deliveryId: delivery.deliveryId,
        packetId: delivery.packetId,
        copyIndex,
        delayed: delivery.delayed,
        buffered: delivery.buffered,
      });
    }
  }

  function flushQueue(step) {
    while (linkState === 'up' && queue.length > 0) {
      const attempt = queue.shift();
      append(step, 'dequeue', {
        packetId: attempt.packet.packetId,
        queueDepth: queue.length,
      });
      deliverAttempt(attempt, step);
    }
  }

  function processDue(step) {
    scheduled.sort((left, right) =>
      left.releaseAt - right.releaseAt
      || left.attempt.sendStep - right.attempt.sendStep
      || left.attempt.packet.packetId.localeCompare(right.attempt.packet.packetId)
    );
    while (scheduled.length > 0 && scheduled[0].releaseAt <= step) {
      const due = scheduled.shift();
      append(step, 'delay_release', {
        packetId: due.attempt.packet.packetId,
        scheduledReleaseAt: due.releaseAt,
      });
      deliverAttempt({ ...due.attempt, delayed: true }, step);
    }
  }

  for (const event of scenario.events) {
    if (event.type === 'link') {
      const priorState = linkState;
      linkState = event.state;
      append(event.step, 'link', { priorState, state: linkState });
      if (priorState === 'down' && linkState === 'up') flushQueue(event.step);
      processDue(event.step);
      continue;
    }

    const packet = packetById.get(event.packetId);
    sendOrder.push(packet.packetId);
    append(event.step, 'send', {
      packetId: packet.packetId,
      messageIdentity: packet.messageIdentity,
      behavior: event.behavior,
    });

    if (event.behavior === 'drop') {
      dropAttempt(
        { packet, sendStep: event.step, copies: 1, delayed: false, buffered: false },
        event.step,
        'explicit_fault',
      );
    } else if (event.behavior === 'delay') {
      delayedPacketIds.add(packet.packetId);
      scheduled.push({
        releaseAt: event.releaseAt,
        attempt: { packet, sendStep: event.step, copies: 1, delayed: true, buffered: false },
      });
      append(event.step, 'delay_schedule', {
        packetId: packet.packetId,
        releaseAt: event.releaseAt,
      });
    } else {
      deliverAttempt(
        {
          packet,
          sendStep: event.step,
          copies: event.behavior === 'duplicate' ? event.copies : 1,
          delayed: false,
          buffered: false,
        },
        event.step,
      );
    }
    processDue(event.step);
  }

  const deliveredOrder = firstUnique(deliveries.map((row) => row.packetId));
  const expectedDeliveredOrder = sendOrder.filter((packetId) => deliveredOrder.includes(packetId));
  const metrics = {
    sentPackets: sendOrder.length,
    deliveredCopies: deliveries.length,
    deliveredUniquePackets: new Set(deliveries.map((row) => row.packetId)).size,
    droppedPackets: drops.length,
    explicitDrops: drops.filter((row) => row.reason === 'explicit_fault').length,
    linkDownDrops: drops.filter((row) => row.reason === 'link_down').length,
    queueCapacityDrops: drops.filter((row) => row.reason === 'queue_capacity').length,
    duplicateExtraCopies: deliveries.filter((row) => row.copyIndex > 0).length,
    delayedPackets: delayedPacketIds.size,
    bufferedPackets: bufferedPacketIds.size,
    pendingDelayedPackets: scheduled.length,
    pendingBufferedPackets: queue.length,
    reordered: canonicalJson(deliveredOrder) !== canonicalJson(expectedDeliveredOrder),
    finalLinkState: linkState,
  };
  const body = {
    scenarioId: scenario.scenarioId,
    mode: scenario.mode,
    profileId: scenario.profileId,
    portId: scenario.portId,
    standardId: scenario.standardId,
    artifactUseId: scenario.artifactUseId,
    packetIds: [...packetById.keys()].sort(),
    sendOrder,
    deliveries,
    drops,
    metrics,
    journalRoot: journal.at(-1)?.recordId ?? '0'.repeat(64),
  };
  return {
    schema: 'standards-port-fault-run/1',
    runId: digest('standardfaultrun1', body),
    ...body,
    journal,
    pending: {
      delayedPacketIds: scheduled.map((row) => row.attempt.packet.packetId),
      bufferedPacketIds: queue.map((row) => row.packet.packetId),
    },
    claimBoundary:
      'This run exercises transport behavior over opaque test packets at a rehearsal or test port. It does not interpret standard payload semantics, grant authority, or represent operational network performance.',
  };
}

export function createFaultFrame(run) {
  requireCondition(
    isRecord(run) && run.schema === 'standards-port-fault-run/1',
    'FAULT_RUN_INVALID',
    'fault run receipt is invalid',
  );
  const body = {
    runId: run.runId,
    scenarioId: run.scenarioId,
    mode: run.mode,
    profileId: run.profileId,
    portId: run.portId,
    standardId: run.standardId,
    artifactUseId: run.artifactUseId,
    status:
      run.metrics.pendingDelayedPackets === 0 && run.metrics.pendingBufferedPackets === 0
        ? 'complete'
        : 'pending',
    metrics: run.metrics,
    journalRoot: run.journalRoot,
    lastEvent: run.journal.length > 0
      ? {
          recordId: run.journal.at(-1).recordId,
          step: run.journal.at(-1).step,
          type: run.journal.at(-1).type,
        }
      : null,
  };
  return {
    schema: 'standards-port-test-frame/1',
    frameId: digest('standardporttestframe1', body),
    ...body,
    claimBoundary:
      'This is a read-only transport-test frame for replaceable test hosts. It contains no payload bytes, provider interface, command authority, targeting, engagement, effector, or execution surface.',
  };
}
