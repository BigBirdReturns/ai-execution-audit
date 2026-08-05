import assert from 'node:assert/strict';
import test from 'node:test';
import {
  AuthoritySidecarError,
  MessageAuthorityRuntime,
  createDefaultRehearsalAuthorityProfile,
  validateAuthorityProfile,
  verifyAdmissionTicket,
  verifyAuthorityDecision,
  verifyReceiverReceipt,
  verifyReconciliation,
} from '../authority_sidecar.mjs';

function receipt(messageClass, index = 1) {
  const suffix = String(index).padStart(2, '0');
  return {
    schema: 'c2sim-semantic-message-receipt/1',
    messageReceiptId: `c2simsemanticmessage1_${suffix.padEnd(64, '0')}`,
    artifactAdmissionId: 'artifact-admission',
    artifactUseId: 'artifact-use',
    artifactSha256: 'a'.repeat(64),
    catalogId: 'catalog-id',
    standardId: 'siso-std-019-2020-c2sim',
    standardRevision: 'C2SIM fixture',
    fileName: `${suffix}.xml`,
    payloadSha256: String(index).repeat(64).slice(0, 64),
    payloadBytes: 100 + index,
    messageId: `00000000-0000-4000-8000-${suffix.padStart(12, '0')}`,
    conversationId: '00000000-0000-4000-8000-000000000001',
    communicativeAct: messageClass === 'report' ? 'Inform' : 'Request',
    fromSystem: 'system-a',
    toSystem: 'system-b',
    inReplyToMessageId: null,
    sentAt: `2026-08-01T00:00:${suffix}Z`,
    protocol: 'C2SIM',
    protocolVersion: '1.0.1',
    securityClassification: 'Unclassified',
    messageClass,
    validation: { status: 'pass' },
    claimBoundary: 'fixture',
  };
}

function profile(overrides = {}) {
  return createDefaultRehearsalAuthorityProfile({
    artifactAdmissionId: 'artifact-admission',
    artifactUseId: 'artifact-use',
    catalogId: 'catalog-id',
    ...overrides,
  });
}

function delivery(ticket, index, deliveryStep) {
  return {
    schema: 'standards-port-fault-delivery/1',
    deliveryId: `standardfaultdelivery1_${String(index).padEnd(64, '0')}`,
    packetId: `standardtestpacket1_${String(index).padEnd(64, '0')}`,
    messageIdentity: ticket.messageId,
    payloadDigest: ticket.payloadSha256,
    sendStep: ticket.issuedAtStep,
    deliveryStep,
    copyIndex: 0,
    copies: 1,
    delayed: false,
    buffered: ticket.linkState !== 'connected',
  };
}

test('admits connected initialization and binds an unchanged payload', () => {
  const runtime = new MessageAuthorityRuntime(profile());
  const result = runtime.evaluateMessage(receipt('submit_initialization'), {
    step: 0,
    localOperatorPresent: false,
  });
  assert.equal(result.decision.disposition, 'allow');
  assert.equal(result.ticket.messageId, result.decision.messageId);
  assert.equal(result.ticket.payloadSha256, result.decision.payloadSha256);
  assert.equal(result.ticket.partitionEpochId, null);
});

test('starts one partition epoch and admits an order only while the local operator and lease survive', () => {
  const runtime = new MessageAuthorityRuntime(profile({ offlineLeaseSteps: 5 }));
  runtime.setLinkState('headquarters_denied', 2);
  const allowed = runtime.evaluateMessage(receipt('order', 2), {
    step: 3,
    localOperatorPresent: true,
  });
  assert.equal(allowed.decision.disposition, 'allow');
  assert.equal(allowed.ticket.expiresAtStep, 7);

  const held = runtime.evaluateMessage(receipt('order', 3), {
    step: 4,
    localOperatorPresent: false,
  });
  assert.equal(held.decision.disposition, 'hold');
  assert.equal(held.ticket, null);

  const expired = runtime.evaluateMessage(receipt('order', 4), {
    step: 8,
    localOperatorPresent: true,
  });
  assert.equal(expired.decision.disposition, 'safe_state');
  assert.equal(expired.decision.reason, 'OFFLINE_LEASE_EXPIRED');
});

test('keeps the same epoch when degradation deepens and refuses an order in total isolation', () => {
  const runtime = new MessageAuthorityRuntime(profile());
  runtime.setLinkState('headquarters_denied', 2);
  const firstEpoch = runtime.snapshot().partitionEpoch.partitionEpochId;
  runtime.setLinkState('isolated', 3);
  assert.equal(runtime.snapshot().partitionEpoch.partitionEpochId, firstEpoch);
  const result = runtime.evaluateMessage(receipt('order', 5), {
    step: 4,
    localOperatorPresent: true,
  });
  assert.equal(result.decision.disposition, 'refuse');
  assert.equal(result.decision.reason, 'MESSAGE_CLASS_NOT_AUTHORIZED_IN_PROFILE');
});

test('accepts one delivered message and refuses a second transport copy as message replay', () => {
  const runtime = new MessageAuthorityRuntime(profile());
  const { ticket } = runtime.evaluateMessage(receipt('order', 6), {
    step: 0,
    localOperatorPresent: true,
  });
  const first = runtime.receiveDelivery(ticket, delivery(ticket, 1, 1), 1);
  const second = runtime.receiveDelivery(ticket, delivery(ticket, 2, 1), 1);
  assert.equal(first.disposition, 'accept');
  assert.equal(second.disposition, 'refuse');
  assert.equal(second.reason, 'MESSAGE_REPLAY');
});

test('refuses a partition ticket delivered after its lease expires', () => {
  const runtime = new MessageAuthorityRuntime(profile({ offlineLeaseSteps: 2 }));
  runtime.setLinkState('headquarters_denied', 1);
  const { ticket } = runtime.evaluateMessage(receipt('report', 7), {
    step: 2,
    localOperatorPresent: false,
  });
  const result = runtime.receiveDelivery(ticket, delivery(ticket, 3, 4), 4);
  assert.equal(result.disposition, 'refuse');
  assert.equal(result.reason, 'ADMISSION_TICKET_EXPIRED');
});

test('classifies explicit supersession and leaves unproven replacement authority human-required', () => {
  const continuous = new MessageAuthorityRuntime(profile());
  continuous.setLinkState('headquarters_denied', 1);
  continuous.setLinkState('connected', 2);
  const explicit = continuous.reconcile({
    step: 3,
    returningAuthorityGeneration: 2,
    supersedesGeneration: 1,
  });
  assert.equal(explicit.status, 'explicitly_superseded');

  const ambiguous = new MessageAuthorityRuntime(profile());
  ambiguous.setLinkState('headquarters_denied', 1);
  ambiguous.setLinkState('connected', 2);
  const unresolved = ambiguous.reconcile({
    step: 3,
    returningAuthorityGeneration: 2,
    supersedesGeneration: null,
  });
  assert.equal(unresolved.status, 'human_required');
});

test('refuses product vocabulary and unknown message classes in the canonical profile', () => {
  const altered = profile();
  altered.profiles.connected.allowedMessageClasses.push('polybolos_internal_decision');
  assert.throws(
    () => validateAuthorityProfile(altered),
    (error) => error instanceof AuthoritySidecarError
      && error.code === 'AUTHORITY_PROFILE_MESSAGE_CLASS_INVALID',
  );
});

test('detached verification closes decisions, tickets, receiver receipts, and reconciliation', () => {
  const authorityProfile = profile();
  const runtime = new MessageAuthorityRuntime(authorityProfile);
  const evaluated = runtime.evaluateMessage(receipt('order', 8), {
    step: 0,
    localOperatorPresent: true,
  });
  const delivered = delivery(evaluated.ticket, 8, 1);
  const received = runtime.receiveDelivery(evaluated.ticket, delivered, 1);
  runtime.setLinkState('headquarters_denied', 2);
  runtime.setLinkState('connected', 3);
  const reconciliation = runtime.reconcile({
    step: 4,
    returningAuthorityGeneration: 2,
    supersedesGeneration: 1,
  });
  assert.equal(verifyAuthorityDecision(evaluated.decision, authorityProfile).decisionId, evaluated.decision.decisionId);
  assert.equal(verifyAdmissionTicket(evaluated.ticket, evaluated.decision, authorityProfile).ticketId, evaluated.ticket.ticketId);
  assert.equal(verifyReceiverReceipt(received, evaluated.ticket, delivered).receiverReceiptId, received.receiverReceiptId);
  assert.equal(
    verifyReconciliation(reconciliation, authorityProfile, runtime.decisions, runtime.receiverReceipts).reconciliationId,
    reconciliation.reconciliationId,
  );
});

test('detached verification refuses altered authority evidence', () => {
  const authorityProfile = profile();
  const runtime = new MessageAuthorityRuntime(authorityProfile);
  const evaluated = runtime.evaluateMessage(receipt('order', 9), {
    step: 0,
    localOperatorPresent: true,
  });
  const altered = structuredClone(evaluated.ticket);
  altered.payloadSha256 = 'f'.repeat(64);
  assert.throws(
    () => verifyAdmissionTicket(altered, evaluated.decision, authorityProfile),
    (error) => error instanceof AuthoritySidecarError
      && ['ADMISSION_TICKET_BINDING_INVALID', 'ADMISSION_TICKET_ID_INVALID'].includes(error.code),
  );
});
