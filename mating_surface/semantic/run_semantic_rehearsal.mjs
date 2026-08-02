#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { basename, join } from 'node:path';
import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import {
  createFaultFrame,
  createTestPacket,
  runFaultScenario,
} from '../test_hosts/core/fault_machine.mjs';
import { verifyFaultFrame } from '../test_hosts/core/fault_verifier.mjs';
import {
  MessageAuthorityRuntime,
  createDefaultRehearsalAuthorityProfile,
} from './authority_sidecar.mjs';

function requireCondition(condition, message) {
  if (!condition) throw new Error(message);
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
    requireCondition(isRecord(value), 'canonical JSON requires plain objects');
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
      .join(',')}}`;
  }
  if (typeof value === 'number') requireCondition(Number.isFinite(value), 'non-finite number');
  const encoded = JSON.stringify(value);
  requireCondition(encoded !== undefined, 'non-JSON value');
  return encoded;
}

export function digest(prefix, value) {
  return `${prefix}_${createHash('sha256').update(canonicalJson(value), 'utf8').digest('hex')}`;
}

function sha256Bytes(bytes) {
  return createHash('sha256').update(bytes).digest('hex');
}

function sha256File(path) {
  return sha256Bytes(readFileSync(path));
}

function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf8'));
}

function writeJson(path, value) {
  writeFileSync(path, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
}

function messageReceiptBody(receipt) {
  const {
    schema: _schema,
    messageReceiptId: _messageReceiptId,
    claimBoundary: _claimBoundary,
    ...body
  } = receipt;
  return body;
}

export function verifyConversation(conversation, conversationDir) {
  requireCondition(
    isRecord(conversation) && conversation.schema === 'c2sim-semantic-conversation/1',
    'semantic conversation schema is invalid',
  );
  requireCondition(Array.isArray(conversation.messages) && conversation.messages.length === 4, 'semantic conversation must contain four messages');
  const expectedClasses = ['submit_initialization', 'object_initialization', 'order', 'report'];
  requireCondition(
    canonicalJson(conversation.messageClasses) === canonicalJson(expectedClasses),
    'semantic conversation class order is invalid',
  );
  const payloadByMessageId = new Map();
  const receiptByMessageId = new Map();
  const messageIds = [];
  for (const receipt of conversation.messages) {
    requireCondition(receipt.schema === 'c2sim-semantic-message-receipt/1', 'semantic message receipt schema is invalid');
    requireCondition(basename(receipt.fileName) === receipt.fileName, 'semantic message file path escapes the conversation directory');
    const path = join(conversationDir, 'messages', receipt.fileName);
    const bytes = readFileSync(path);
    requireCondition(receipt.payloadSha256 === sha256Bytes(bytes), `payload digest mismatch for ${receipt.fileName}`);
    requireCondition(receipt.payloadBytes === bytes.length, `payload length mismatch for ${receipt.fileName}`);
    requireCondition(
      receipt.messageReceiptId === digest('c2simsemanticmessage1', messageReceiptBody(receipt)),
      `semantic receipt identity mismatch for ${receipt.fileName}`,
    );
    requireCondition(receipt.validation?.status === 'pass', `${receipt.fileName} did not pass schema validation`);
    requireCondition(!receiptByMessageId.has(receipt.messageId), `duplicate semantic message ID ${receipt.messageId}`);
    payloadByMessageId.set(receipt.messageId, bytes);
    receiptByMessageId.set(receipt.messageId, receipt);
    messageIds.push(receipt.messageId);
  }
  requireCondition(canonicalJson(messageIds) === canonicalJson(conversation.messageIds), 'conversation message IDs differ from receipts');
  const body = {
    artifactAdmissionId: conversation.artifactAdmissionId,
    artifactUseId: conversation.artifactUseId,
    catalogId: conversation.catalogId,
    conversationId: conversation.conversationId,
    messageReceiptIds: conversation.messageReceiptIds,
    messageIds: conversation.messageIds,
    messageClasses: conversation.messageClasses,
    replyChain: conversation.replyChain,
    taskId: conversation.taskId,
    orderId: conversation.orderId,
    reportId: conversation.reportId,
    negativeChecks: conversation.negativeChecks,
  };
  requireCondition(
    conversation.semanticConversationId === digest('c2simsemanticconversation1', body),
    'semantic conversation identity is invalid',
  );
  requireCondition(Object.values(conversation.negativeChecks).every(Boolean), 'semantic negative controls did not all pass');
  return { payloadByMessageId, receiptByMessageId };
}

function createScenario(packetsByClass, transaction) {
  return {
    schema: 'standards-port-fault-scenario/1',
    scenarioId: 'c2sim-semantic-partition-replay-reconciliation',
    mode: 'rehearsal',
    profileId: transaction.use.profileId,
    portId: transaction.use.portId,
    standardId: transaction.admission.standardId,
    artifactUseId: transaction.use.useId,
    initialLinkState: 'up',
    partitionPolicy: 'buffer',
    queueCapacity: 2,
    events: [
      { step: 0, type: 'send', packetId: packetsByClass.get('submit_initialization').packetId, behavior: 'pass' },
      { step: 1, type: 'send', packetId: packetsByClass.get('object_initialization').packetId, behavior: 'pass' },
      { step: 2, type: 'link', state: 'down' },
      { step: 3, type: 'send', packetId: packetsByClass.get('order').packetId, behavior: 'duplicate', copies: 2 },
      { step: 4, type: 'send', packetId: packetsByClass.get('report').packetId, behavior: 'delay', releaseAt: 6 },
      { step: 6, type: 'link', state: 'up' },
    ],
    claimBoundary:
      'This scenario transports four schema-valid C2SIM rehearsal messages through deterministic partition, duplication, delay, replay, and reconciliation conditions. It is not an operational network scenario.',
  };
}

export function createHostFrame({ conversation, faultRun, faultVerification, authority, receiverReceipts, reconciliation }) {
  const accepted = receiverReceipts.filter((row) => row.disposition === 'accept');
  const refused = receiverReceipts.filter((row) => row.disposition === 'refuse');
  const body = {
    semanticConversationId: conversation.semanticConversationId,
    standardId: faultRun.standardId,
    artifactUseId: faultRun.artifactUseId,
    scenarioDigest: faultRun.scenarioDigest,
    faultRunId: faultRun.runId,
    faultJournalRoot: faultRun.journalRoot,
    faultFrameId: faultVerification.frameId,
    authorityProfileId: authority.profile.profileId,
    authorityGeneration: authority.profile.authorityGeneration,
    partitionEpochId: reconciliation.partitionEpochId,
    reconciliationId: reconciliation.reconciliationId,
    reconciliationStatus: reconciliation.status,
    status: reconciliation.status === 'explicitly_superseded' ? 'reconciled' : 'attention_required',
    messages: {
      schemaValid: conversation.messages.length,
      authorityAllowed: authority.decisions.filter((row) => row.disposition === 'allow').length,
      receiverAccepted: accepted.length,
      receiverRefused: refused.length,
      replayRefused: refused.filter((row) => row.reason === 'MESSAGE_REPLAY').length,
    },
    transport: faultRun.metrics,
    lastEvent: faultRun.journal.length > 0
      ? {
          recordId: faultRun.journal.at(-1).recordId,
          step: faultRun.journal.at(-1).step,
          type: faultRun.journal.at(-1).type,
        }
      : null,
    hostContracts: [
      {
        host: 'mame',
        mode: 'read_only',
        inputs: ['select_fixture', 'step', 'reset_rehearsal'],
        outputs: ['transport_metrics', 'authority_dispositions', 'replay_refusal', 'reconciliation_status'],
      },
      {
        host: 'motiondeck',
        mode: 'read_only',
        inputs: ['select_fixture', 'step', 'reset_rehearsal'],
        outputs: ['transport_metrics', 'authority_dispositions', 'replay_refusal', 'reconciliation_status'],
      },
    ],
  };
  return {
    schema: 'standards-semantic-rehearsal-frame/1',
    frameId: digest('standardsemanticrehearsalframe1', body),
    ...body,
    claimBoundary:
      'This frame is a read-only projection for replaceable rehearsal hosts. It contains no XML payload, provider interface, authority mutation, targeting, engagement, effector, or execution surface.',
  };
}

function main(argv) {
  if (argv.length !== 4) {
    console.error('usage: run_semantic_rehearsal.mjs <conversation-dir> <artifact-transaction.json> <xsd11-catalog.json> <output-dir>');
    return 2;
  }
  const [conversationDir, transactionPath, catalogPath, outputDir] = argv;
  rmSync(outputDir, { recursive: true, force: true });
  mkdirSync(outputDir, { recursive: true });
  const conversation = readJson(join(conversationDir, 'conversation.json'));
  const transaction = readJson(transactionPath);
  const catalog = readJson(catalogPath);
  const { payloadByMessageId, receiptByMessageId } = verifyConversation(conversation, conversationDir);

  requireCondition(transaction.admission.admissionId === conversation.artifactAdmissionId, 'conversation uses another artifact admission');
  requireCondition(transaction.use.useId === conversation.artifactUseId, 'conversation uses another artifact use');
  requireCondition(catalog.catalogId === conversation.catalogId, 'conversation uses another catalog');

  const packets = [];
  const payloads = new Map();
  const packetsByClass = new Map();
  for (const receipt of conversation.messages) {
    const payload = payloadByMessageId.get(receipt.messageId);
    const packet = createTestPacket({
      artifactTransaction: transaction,
      catalog,
      payload,
      messageIdentity: receipt.messageId,
      sourceSystemId: receipt.fromSystem,
      observedAt: receipt.sentAt,
    });
    packets.push(packet);
    payloads.set(packet.packetId, payload);
    packetsByClass.set(receipt.messageClass, packet);
  }

  const scenario = createScenario(packetsByClass, transaction);
  const authorityProfile = createDefaultRehearsalAuthorityProfile({
    artifactAdmissionId: transaction.admission.admissionId,
    artifactUseId: transaction.use.useId,
    catalogId: catalog.catalogId,
    authorityGeneration: 1,
    offlineLeaseSteps: 5,
  });
  const authorityRuntime = new MessageAuthorityRuntime(authorityProfile);
  const decisions = [];
  const ticketByMessageId = new Map();
  const packetById = new Map(packets.map((packet) => [packet.packetId, packet]));

  for (const event of scenario.events) {
    if (event.type === 'link') {
      authorityRuntime.setLinkState(event.state === 'up' ? 'connected' : 'headquarters_denied', event.step);
      continue;
    }
    const packet = packetById.get(event.packetId);
    const receipt = receiptByMessageId.get(packet.messageIdentity);
    const result = authorityRuntime.evaluateMessage(receipt, {
      step: event.step,
      localOperatorPresent: receipt.messageClass === 'order',
    });
    decisions.push(result.decision);
    requireCondition(result.decision.disposition === 'allow', `${receipt.messageClass} was not admitted by the rehearsal profile`);
    ticketByMessageId.set(receipt.messageId, result.ticket);
  }

  const faultRun = runFaultScenario({
    scenario,
    packets,
    payloads,
    artifactTransaction: transaction,
    catalog,
  });
  const faultFrame = createFaultFrame(faultRun);
  const faultVerification = verifyFaultFrame(faultFrame, faultRun);
  const receiverReceipts = faultRun.deliveries.map((delivery) => {
    const ticket = ticketByMessageId.get(delivery.messageIdentity);
    requireCondition(ticket, `delivery ${delivery.deliveryId} has no admission ticket`);
    return authorityRuntime.receiveDelivery(ticket, delivery, delivery.deliveryStep);
  });
  const orderReceipts = receiverReceipts.filter((row) => row.messageClass === 'order');
  requireCondition(orderReceipts.length === 2, 'duplicated order did not produce two receiver receipts');
  requireCondition(orderReceipts[0].disposition === 'accept', 'first order copy was not accepted');
  requireCondition(orderReceipts[1].reason === 'MESSAGE_REPLAY', 'second order copy was not refused as replay');
  requireCondition(receiverReceipts.filter((row) => row.disposition === 'accept').length === 4, 'receiver did not accept the four unique semantic messages');

  const reconciliation = authorityRuntime.reconcile({
    step: 7,
    returningAuthorityGeneration: 2,
    supersedesGeneration: 1,
  });
  requireCondition(reconciliation.status === 'explicitly_superseded', 'returning authority did not explicitly reconcile the partition');
  const authority = {
    profile: authorityProfile,
    decisions,
    tickets: [...ticketByMessageId.values()],
    receiverReceipts,
    reconciliation,
    runtimeState: authorityRuntime.snapshot(),
  };
  const hostFrame = createHostFrame({
    conversation,
    faultRun,
    faultVerification,
    authority,
    receiverReceipts,
    reconciliation,
  });

  const retained = {
    'semantic-binding.json': {
      schema: 'standards-semantic-packet-binding/1',
      semanticConversationId: conversation.semanticConversationId,
      bindings: packets.map((packet) => {
        const receipt = receiptByMessageId.get(packet.messageIdentity);
        return {
          messageReceiptId: receipt.messageReceiptId,
          messageId: receipt.messageId,
          messageClass: receipt.messageClass,
          payloadSha256: receipt.payloadSha256,
          packetId: packet.packetId,
          packetPayloadDigest: packet.payloadDigest,
        };
      }),
      claimBoundary:
        'This manifest binds schema-valid semantic receipts to payload-opaque transport packets. It does not wrap or rewrite the C2SIM XML.',
    },
    'scenario.json': scenario,
    'fault-run.json': faultRun,
    'fault-frame.json': faultFrame,
    'fault-verification.json': faultVerification,
    'authority.json': authority,
    'semantic-host-frame.json': hostFrame,
  };
  for (const [name, value] of Object.entries(retained)) writeJson(join(outputDir, name), value);

  const encodedEvidence = JSON.stringify(retained);
  for (const payload of payloadByMessageId.values()) {
    requireCondition(!encodedEvidence.includes(payload.toString('utf8')), 'C2SIM XML payload escaped into retained sidecar evidence');
  }
  const fileHashes = Object.fromEntries(
    Object.keys(retained).map((name) => [name, { sha256: sha256File(join(outputDir, name)) }]),
  );
  const qualificationBody = {
    semanticConversationId: conversation.semanticConversationId,
    scenarioDigest: faultRun.scenarioDigest,
    faultRunId: faultRun.runId,
    authorityDecisionIds: decisions.map((row) => row.decisionId),
    receiverReceiptIds: receiverReceipts.map((row) => row.receiverReceiptId),
    reconciliationId: reconciliation.reconciliationId,
    hostFrameId: hostFrame.frameId,
    files: fileHashes,
  };
  const qualification = {
    schema: 'standards-semantic-rehearsal-qualification/1',
    status: 'pass',
    qualificationId: digest('standardsemanticrehearsalqualification1', qualificationBody),
    ...qualificationBody,
    assertions: {
      fourSchemaValidMessages: true,
      exactSemanticToTransportBinding: true,
      unchangedStandardPayloads: true,
      partitionBoundAuthority: true,
      duplicateOrderReplayRefused: true,
      explicitReconciliation: true,
      payloadFreeReadOnlyHostFrame: true,
    },
    claimBoundary:
      'This qualification covers one deterministic unclassified C2SIM rehearsal conversation and its external sidecars. It does not establish an operational coalition profile, network, command authority, or weapons effect.',
  };
  writeJson(join(outputDir, 'qualification.json'), qualification);

  process.stdout.write(`${JSON.stringify({
    status: qualification.status,
    qualificationId: qualification.qualificationId,
    semanticConversationId: conversation.semanticConversationId,
    faultRunId: faultRun.runId,
    hostFrameId: hostFrame.frameId,
    receiverAccepted: receiverReceipts.filter((row) => row.disposition === 'accept').length,
    receiverReplayRefused: receiverReceipts.filter((row) => row.reason === 'MESSAGE_REPLAY').length,
    reconciliationStatus: reconciliation.status,
    outputDir,
  }, null, 2)}\n`);
  return 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exitCode = main(process.argv.slice(2));
}
