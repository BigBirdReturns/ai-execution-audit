import { createHash } from 'node:crypto';

const LINK_STATES = new Set(['connected', 'headquarters_denied', 'isolated']);
const MESSAGE_CLASSES = new Set([
  'submit_initialization',
  'object_initialization',
  'order',
  'report',
]);
const DISPOSITIONS = new Set(['allow', 'hold', 'refuse', 'safe_state']);
const MAX_LEASE_STEPS = 1_000_000;
const MAX_GENERATION = 1_000_000_000;

export class AuthoritySidecarError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'AuthoritySidecarError';
    this.code = code;
  }
}

function requireCondition(condition, code, message) {
  if (!condition) throw new AuthoritySidecarError(code, message);
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
  const unexpected = Object.keys(value).filter((key) => !allowed.has(key)).sort();
  requireCondition(unexpected.length === 0, code, `${label} contains unsupported field ${unexpected[0]}`);
  const missing = [...allowed].filter((key) => !Object.prototype.hasOwnProperty.call(value, key));
  requireCondition(missing.length === 0, code, `${label} is missing field ${missing[0]}`);
}

function boundedString(value, code, label, max = 512) {
  requireCondition(typeof value === 'string', code, `${label} must be a string`);
  const normalized = value.trim();
  requireCondition(normalized.length > 0 && normalized.length <= max, code, `${label} is empty or unbounded`);
  return normalized;
}

function safeStep(value, code, label) {
  requireCondition(Number.isSafeInteger(value) && value >= 0, code, `${label} must be a non-negative safe integer`);
  return value;
}

function safeGeneration(value, code, label) {
  requireCondition(
    Number.isSafeInteger(value) && value >= 1 && value <= MAX_GENERATION,
    code,
    `${label} must be an integer between 1 and ${MAX_GENERATION}`,
  );
  return value;
}

const PROFILE_KEYS = new Set([
  'schema',
  'profileId',
  'standardId',
  'artifactAdmissionId',
  'artifactUseId',
  'catalogId',
  'authorityGeneration',
  'offlineLeaseSteps',
  'profiles',
  'claimBoundary',
]);
const COMM_PROFILE_KEYS = new Set(['allowedMessageClasses', 'localOperatorRequiredClasses']);

export function validateAuthorityProfile(profile) {
  exactKeys(profile, PROFILE_KEYS, 'AUTHORITY_PROFILE_FIELDS_INVALID', 'authority profile');
  requireCondition(
    profile.schema === 'standards-message-authority-profile/1',
    'AUTHORITY_PROFILE_SCHEMA_INVALID',
    'authority profile schema is invalid',
  );
  for (const key of ['profileId', 'standardId', 'artifactAdmissionId', 'artifactUseId', 'catalogId', 'claimBoundary']) {
    boundedString(profile[key], 'AUTHORITY_PROFILE_FIELD_INVALID', key);
  }
  safeGeneration(profile.authorityGeneration, 'AUTHORITY_PROFILE_GENERATION_INVALID', 'authorityGeneration');
  requireCondition(
    Number.isSafeInteger(profile.offlineLeaseSteps)
      && profile.offlineLeaseSteps >= 0
      && profile.offlineLeaseSteps <= MAX_LEASE_STEPS,
    'AUTHORITY_PROFILE_LEASE_INVALID',
    `offlineLeaseSteps must be between 0 and ${MAX_LEASE_STEPS}`,
  );
  requireCondition(isRecord(profile.profiles), 'AUTHORITY_PROFILE_COMM_INVALID', 'profiles must be an object');
  exactKeys(profile.profiles, LINK_STATES, 'AUTHORITY_PROFILE_COMM_INVALID', 'profiles');
  for (const state of LINK_STATES) {
    const row = profile.profiles[state];
    exactKeys(row, COMM_PROFILE_KEYS, 'AUTHORITY_PROFILE_COMM_INVALID', `${state} profile`);
    for (const key of COMM_PROFILE_KEYS) {
      requireCondition(Array.isArray(row[key]), 'AUTHORITY_PROFILE_COMM_INVALID', `${state}.${key} must be an array`);
      requireCondition(new Set(row[key]).size === row[key].length, 'AUTHORITY_PROFILE_COMM_INVALID', `${state}.${key} contains duplicates`);
      for (const messageClass of row[key]) {
        requireCondition(MESSAGE_CLASSES.has(messageClass), 'AUTHORITY_PROFILE_MESSAGE_CLASS_INVALID', `unknown message class ${messageClass}`);
      }
    }
    requireCondition(
      row.localOperatorRequiredClasses.every((messageClass) => row.allowedMessageClasses.includes(messageClass)),
      'AUTHORITY_PROFILE_COMM_INVALID',
      `${state} requires a local operator for a message class that is not allowed`,
    );
  }
  return profile;
}

const RECEIPT_REQUIRED = new Set([
  'schema',
  'messageReceiptId',
  'artifactAdmissionId',
  'artifactUseId',
  'artifactSha256',
  'catalogId',
  'standardId',
  'standardRevision',
  'fileName',
  'payloadSha256',
  'payloadBytes',
  'messageId',
  'conversationId',
  'communicativeAct',
  'fromSystem',
  'toSystem',
  'inReplyToMessageId',
  'sentAt',
  'protocol',
  'protocolVersion',
  'securityClassification',
  'messageClass',
  'validation',
  'claimBoundary',
]);

export function validateSemanticMessageReceipt(receipt, profile) {
  requireCondition(isRecord(receipt), 'SEMANTIC_RECEIPT_INVALID', 'semantic message receipt must be an object');
  const missing = [...RECEIPT_REQUIRED].filter((key) => !Object.prototype.hasOwnProperty.call(receipt, key));
  requireCondition(missing.length === 0, 'SEMANTIC_RECEIPT_INVALID', `semantic receipt is missing field ${missing[0]}`);
  requireCondition(
    receipt.schema === 'c2sim-semantic-message-receipt/1',
    'SEMANTIC_RECEIPT_SCHEMA_INVALID',
    'semantic message receipt schema is invalid',
  );
  for (const key of ['messageReceiptId', 'artifactAdmissionId', 'artifactUseId', 'catalogId', 'standardId', 'messageId', 'conversationId', 'payloadSha256', 'messageClass']) {
    boundedString(receipt[key], 'SEMANTIC_RECEIPT_INVALID', key);
  }
  requireCondition(MESSAGE_CLASSES.has(receipt.messageClass), 'SEMANTIC_RECEIPT_CLASS_INVALID', `unsupported message class ${receipt.messageClass}`);
  requireCondition(isRecord(receipt.validation) && receipt.validation.status === 'pass', 'SEMANTIC_RECEIPT_VALIDATION_INVALID', 'semantic message did not pass schema validation');
  requireCondition(receipt.standardId === profile.standardId, 'SEMANTIC_RECEIPT_BINDING_INVALID', 'message uses another standard');
  requireCondition(receipt.artifactAdmissionId === profile.artifactAdmissionId, 'SEMANTIC_RECEIPT_BINDING_INVALID', 'message uses another artifact admission');
  requireCondition(receipt.artifactUseId === profile.artifactUseId, 'SEMANTIC_RECEIPT_BINDING_INVALID', 'message uses another artifact use');
  requireCondition(receipt.catalogId === profile.catalogId, 'SEMANTIC_RECEIPT_BINDING_INVALID', 'message uses another structural catalog');
  return receipt;
}

function decisionBody(decision) {
  const { decisionId: _decisionId, claimBoundary: _claimBoundary, ...body } = decision;
  return body;
}

function ticketBody(ticket) {
  const { ticketId: _ticketId, claimBoundary: _claimBoundary, ...body } = ticket;
  return body;
}

function receiverBody(receipt) {
  const { receiverReceiptId: _receiverReceiptId, claimBoundary: _claimBoundary, ...body } = receipt;
  return body;
}

export function verifyAuthorityDecision(decision, profile) {
  validateAuthorityProfile(profile);
  requireCondition(
    isRecord(decision) && decision.schema === 'standards-message-authority-decision/1',
    'AUTHORITY_DECISION_INVALID',
    'authority decision schema is invalid',
  );
  requireCondition(DISPOSITIONS.has(decision.disposition), 'AUTHORITY_DECISION_INVALID', 'authority decision disposition is invalid');
  requireCondition(MESSAGE_CLASSES.has(decision.messageClass), 'AUTHORITY_DECISION_INVALID', 'authority decision message class is invalid');
  requireCondition(decision.profileId === profile.profileId, 'AUTHORITY_DECISION_BINDING_INVALID', 'authority decision uses another profile');
  requireCondition(decision.authorityGeneration === profile.authorityGeneration, 'AUTHORITY_DECISION_BINDING_INVALID', 'authority decision uses another generation');
  requireCondition(
    decision.decisionId === digest('standardmessageauthoritydecision1', decisionBody(decision)),
    'AUTHORITY_DECISION_ID_INVALID',
    'authority decision identity is invalid',
  );
  return decision;
}

export function verifyAdmissionTicket(ticket, decision, profile) {
  verifyAuthorityDecision(decision, profile);
  requireCondition(
    isRecord(ticket) && ticket.schema === 'standards-message-admission-ticket/1',
    'ADMISSION_TICKET_INVALID',
    'admission ticket schema is invalid',
  );
  requireCondition(decision.disposition === 'allow', 'ADMISSION_TICKET_INVALID', 'ticket belongs to a non-allow decision');
  requireCondition(ticket.decisionId === decision.decisionId, 'ADMISSION_TICKET_BINDING_INVALID', 'ticket cites another decision');
  for (const key of ['profileId', 'authorityGeneration', 'messageReceiptId', 'messageId', 'messageClass', 'payloadSha256', 'linkState', 'partitionEpochId']) {
    requireCondition(canonicalJson(ticket[key]) === canonicalJson(decision[key]), 'ADMISSION_TICKET_BINDING_INVALID', `ticket field ${key} differs from decision`);
  }
  requireCondition(ticket.issuedAtStep === decision.evaluatedAtStep, 'ADMISSION_TICKET_BINDING_INVALID', 'ticket issue step differs from decision');
  requireCondition(ticket.expiresAtStep === decision.leaseExpiresAtStep, 'ADMISSION_TICKET_BINDING_INVALID', 'ticket expiry differs from decision');
  requireCondition(
    ticket.ticketId === digest('standardmessageadmissionticket1', ticketBody(ticket)),
    'ADMISSION_TICKET_ID_INVALID',
    'admission ticket identity is invalid',
  );
  return ticket;
}

export function verifyReceiverReceipt(receipt, ticket, delivery) {
  requireCondition(
    isRecord(receipt) && receipt.schema === 'standards-message-receiver-receipt/1',
    'RECEIVER_RECEIPT_INVALID',
    'receiver receipt schema is invalid',
  );
  requireCondition(isRecord(ticket) && ticket.schema === 'standards-message-admission-ticket/1', 'RECEIVER_RECEIPT_INVALID', 'receiver receipt ticket is invalid');
  requireCondition(isRecord(delivery) && delivery.schema === 'standards-port-fault-delivery/1', 'RECEIVER_RECEIPT_INVALID', 'receiver receipt delivery is invalid');
  requireCondition(['accept', 'refuse'].includes(receipt.disposition), 'RECEIVER_RECEIPT_INVALID', 'receiver disposition is invalid');
  requireCondition(receipt.ticketId === ticket.ticketId, 'RECEIVER_RECEIPT_BINDING_INVALID', 'receiver receipt cites another ticket');
  requireCondition(receipt.decisionId === ticket.decisionId, 'RECEIVER_RECEIPT_BINDING_INVALID', 'receiver receipt cites another decision');
  requireCondition(receipt.deliveryId === delivery.deliveryId, 'RECEIVER_RECEIPT_BINDING_INVALID', 'receiver receipt cites another delivery');
  requireCondition(receipt.messageId === ticket.messageId, 'RECEIVER_RECEIPT_BINDING_INVALID', 'receiver receipt message differs');
  requireCondition(receipt.messageClass === ticket.messageClass, 'RECEIVER_RECEIPT_BINDING_INVALID', 'receiver receipt class differs');
  requireCondition(receipt.payloadSha256 === ticket.payloadSha256, 'RECEIVER_RECEIPT_BINDING_INVALID', 'receiver receipt payload differs');
  requireCondition(receipt.receivedAtStep === delivery.deliveryStep, 'RECEIVER_RECEIPT_BINDING_INVALID', 'receiver receipt step differs');
  requireCondition(
    receipt.receiverReceiptId === digest('standardmessagereceiverreceipt1', receiverBody(receipt)),
    'RECEIVER_RECEIPT_ID_INVALID',
    'receiver receipt identity is invalid',
  );
  return receipt;
}

export function verifyReconciliation(reconciliation, profile, decisions, receiverReceipts) {
  validateAuthorityProfile(profile);
  requireCondition(
    isRecord(reconciliation) && reconciliation.schema === 'standards-message-reconciliation/1',
    'RECONCILIATION_INVALID',
    'reconciliation schema is invalid',
  );
  requireCondition(
    reconciliation.profileId === profile.profileId
      && reconciliation.localAuthorityGeneration === profile.authorityGeneration,
    'RECONCILIATION_BINDING_INVALID',
    'reconciliation uses another profile or local generation',
  );
  requireCondition(
    canonicalJson(reconciliation.authorityDecisionIds)
      === canonicalJson(decisions.map((row) => row.decisionId)),
    'RECONCILIATION_BINDING_INVALID',
    'reconciliation decision lineage differs',
  );
  requireCondition(
    canonicalJson(reconciliation.receiverReceiptIds)
      === canonicalJson(receiverReceipts.map((row) => row.receiverReceiptId)),
    'RECONCILIATION_BINDING_INVALID',
    'reconciliation receiver lineage differs',
  );
  const { reconciliationId: _reconciliationId, claimBoundary: _claimBoundary, schema: _schema, ...body } = reconciliation;
  requireCondition(
    reconciliation.reconciliationId === digest('standardmessagereconciliation1', body),
    'RECONCILIATION_ID_INVALID',
    'reconciliation identity is invalid',
  );
  return reconciliation;
}

export class MessageAuthorityRuntime {
  constructor(profile) {
    this.profile = structuredClone(validateAuthorityProfile(profile));
    this.linkState = 'connected';
    this.partitionEpoch = null;
    this.closedEpochs = [];
    this.decisions = [];
    this.tickets = new Map();
    this.acceptedMessageIds = new Set();
    this.acceptedDeliveryIds = new Set();
    this.receiverReceipts = [];
    this.lastStep = 0;
  }

  setLinkState(nextState, step) {
    requireCondition(LINK_STATES.has(nextState), 'LINK_STATE_INVALID', `unknown link state ${nextState}`);
    safeStep(step, 'LINK_STEP_INVALID', 'link step');
    requireCondition(step >= this.lastStep, 'RUNTIME_STEP_REGRESSION', 'link step regresses runtime time');
    requireCondition(nextState !== this.linkState, 'LINK_STATE_NOOP', 'link transition must change state');
    const priorState = this.linkState;
    if (priorState === 'connected' && nextState !== 'connected') {
      const body = {
        profileId: this.profile.profileId,
        authorityGeneration: this.profile.authorityGeneration,
        startedAtStep: step,
      };
      this.partitionEpoch = {
        schema: 'standards-message-partition-epoch/1',
        partitionEpochId: digest('standardmessagepartitionepoch1', body),
        ...body,
      };
    } else if (priorState !== 'connected' && nextState === 'connected') {
      requireCondition(this.partitionEpoch !== null, 'PARTITION_EPOCH_MISSING', 'reconnect has no active partition epoch');
      this.closedEpochs.push({ ...this.partitionEpoch, closedAtStep: step });
    } else {
      requireCondition(this.partitionEpoch !== null, 'PARTITION_EPOCH_MISSING', 'degraded transition has no active partition epoch');
    }
    this.linkState = nextState;
    this.lastStep = step;
    return this.snapshot();
  }

  evaluateMessage(receipt, { step, localOperatorPresent }) {
    validateSemanticMessageReceipt(receipt, this.profile);
    safeStep(step, 'AUTHORITY_STEP_INVALID', 'authority evaluation step');
    requireCondition(step >= this.lastStep, 'RUNTIME_STEP_REGRESSION', 'authority evaluation step regresses runtime time');
    requireCondition(typeof localOperatorPresent === 'boolean', 'LOCAL_OPERATOR_STATE_INVALID', 'localOperatorPresent must be boolean');
    this.lastStep = step;

    const commProfile = this.profile.profiles[this.linkState];
    let disposition = 'allow';
    let reason = 'MESSAGE_CLASS_ADMITTED';
    let partitionEpochId = null;
    let leaseExpiresAtStep = null;
    let offlineElapsedSteps = 0;

    if (this.linkState !== 'connected') {
      requireCondition(this.partitionEpoch !== null, 'PARTITION_EPOCH_MISSING', 'degraded authority evaluation has no partition epoch');
      partitionEpochId = this.partitionEpoch.partitionEpochId;
      offlineElapsedSteps = step - this.partitionEpoch.startedAtStep;
      leaseExpiresAtStep = this.partitionEpoch.startedAtStep + this.profile.offlineLeaseSteps;
      if (offlineElapsedSteps > this.profile.offlineLeaseSteps) {
        disposition = 'safe_state';
        reason = 'OFFLINE_LEASE_EXPIRED';
      }
    }
    if (disposition === 'allow' && !commProfile.allowedMessageClasses.includes(receipt.messageClass)) {
      disposition = 'refuse';
      reason = 'MESSAGE_CLASS_NOT_AUTHORIZED_IN_PROFILE';
    }
    if (
      disposition === 'allow'
      && commProfile.localOperatorRequiredClasses.includes(receipt.messageClass)
      && !localOperatorPresent
    ) {
      disposition = 'hold';
      reason = 'LOCAL_OPERATOR_REQUIRED';
    }

    requireCondition(DISPOSITIONS.has(disposition), 'DISPOSITION_INVALID', 'authority runtime produced an invalid disposition');
    const decision = {
      schema: 'standards-message-authority-decision/1',
      decisionId: '',
      profileId: this.profile.profileId,
      authorityGeneration: this.profile.authorityGeneration,
      messageReceiptId: receipt.messageReceiptId,
      messageId: receipt.messageId,
      messageClass: receipt.messageClass,
      payloadSha256: receipt.payloadSha256,
      evaluatedAtStep: step,
      linkState: this.linkState,
      partitionEpochId,
      offlineElapsedSteps,
      leaseExpiresAtStep,
      localOperatorPresent,
      disposition,
      reason,
      claimBoundary:
        'This sidecar decision references one unchanged schema-valid rehearsal message. It does not alter the standard payload or create operational command authority.',
    };
    decision.decisionId = digest('standardmessageauthoritydecision1', decisionBody(decision));
    this.decisions.push(decision);

    let ticket = null;
    if (disposition === 'allow') {
      const ticketCandidate = {
        schema: 'standards-message-admission-ticket/1',
        ticketId: '',
        decisionId: decision.decisionId,
        profileId: this.profile.profileId,
        authorityGeneration: this.profile.authorityGeneration,
        messageReceiptId: receipt.messageReceiptId,
        messageId: receipt.messageId,
        messageClass: receipt.messageClass,
        payloadSha256: receipt.payloadSha256,
        issuedAtStep: step,
        linkState: this.linkState,
        partitionEpochId,
        expiresAtStep: leaseExpiresAtStep,
        claimBoundary:
          'This ticket admits one exact rehearsal message for transport and receiver replay checks. It is not a command, task, engagement, or execution instruction.',
      };
      ticketCandidate.ticketId = digest('standardmessageadmissionticket1', ticketBody(ticketCandidate));
      ticket = ticketCandidate;
      this.tickets.set(receipt.messageId, ticket);
    }
    return { decision, ticket };
  }

  receiveDelivery(ticket, delivery, step) {
    safeStep(step, 'RECEIVER_STEP_INVALID', 'receiver step');
    requireCondition(isRecord(ticket) && ticket.schema === 'standards-message-admission-ticket/1', 'ADMISSION_TICKET_INVALID', 'admission ticket is invalid');
    requireCondition(isRecord(delivery) && delivery.schema === 'standards-port-fault-delivery/1', 'DELIVERY_INVALID', 'delivery receipt is invalid');
    requireCondition(ticket.ticketId === digest('standardmessageadmissionticket1', ticketBody(ticket)), 'ADMISSION_TICKET_INVALID', 'admission ticket identity is invalid');
    requireCondition(delivery.messageIdentity === ticket.messageId, 'DELIVERY_TICKET_MISMATCH', 'delivery message differs from ticket');
    requireCondition(delivery.payloadDigest === ticket.payloadSha256, 'DELIVERY_TICKET_MISMATCH', 'delivery payload differs from ticket');

    let disposition = 'accept';
    let reason = 'MESSAGE_ACCEPTED';
    if (ticket.expiresAtStep !== null && step > ticket.expiresAtStep) {
      disposition = 'refuse';
      reason = 'ADMISSION_TICKET_EXPIRED';
    } else if (this.acceptedMessageIds.has(ticket.messageId)) {
      disposition = 'refuse';
      reason = 'MESSAGE_REPLAY';
    } else if (this.acceptedDeliveryIds.has(delivery.deliveryId)) {
      disposition = 'refuse';
      reason = 'DELIVERY_REPLAY';
    }
    if (disposition === 'accept') {
      this.acceptedMessageIds.add(ticket.messageId);
      this.acceptedDeliveryIds.add(delivery.deliveryId);
    }
    const receipt = {
      schema: 'standards-message-receiver-receipt/1',
      receiverReceiptId: '',
      ticketId: ticket.ticketId,
      decisionId: ticket.decisionId,
      deliveryId: delivery.deliveryId,
      messageId: ticket.messageId,
      messageClass: ticket.messageClass,
      payloadSha256: ticket.payloadSha256,
      receivedAtStep: step,
      disposition,
      reason,
      claimBoundary:
        'This receiver receipt records admission or replay refusal for one exact rehearsal message. It does not interpret or execute the message body.',
    };
    receipt.receiverReceiptId = digest('standardmessagereceiverreceipt1', receiverBody(receipt));
    this.receiverReceipts.push(receipt);
    return receipt;
  }

  reconcile({ step, returningAuthorityGeneration, supersedesGeneration }) {
    safeStep(step, 'RECONCILIATION_STEP_INVALID', 'reconciliation step');
    requireCondition(step >= this.lastStep, 'RUNTIME_STEP_REGRESSION', 'reconciliation step regresses runtime time');
    requireCondition(this.linkState === 'connected', 'RECONCILIATION_LINK_INVALID', 'reconciliation requires connected state');
    requireCondition(this.closedEpochs.length > 0, 'RECONCILIATION_EPOCH_MISSING', 'reconciliation has no closed partition epoch');
    safeGeneration(returningAuthorityGeneration, 'RECONCILIATION_GENERATION_INVALID', 'returningAuthorityGeneration');
    if (supersedesGeneration !== null) safeGeneration(supersedesGeneration, 'RECONCILIATION_GENERATION_INVALID', 'supersedesGeneration');
    this.lastStep = step;

    let status = 'human_required';
    if (returningAuthorityGeneration === this.profile.authorityGeneration) {
      status = 'continuous_authority';
    } else if (
      returningAuthorityGeneration > this.profile.authorityGeneration
      && supersedesGeneration === this.profile.authorityGeneration
    ) {
      status = 'explicitly_superseded';
    }
    const epoch = this.closedEpochs.at(-1);
    const body = {
      profileId: this.profile.profileId,
      localAuthorityGeneration: this.profile.authorityGeneration,
      returningAuthorityGeneration,
      supersedesGeneration,
      partitionEpochId: epoch.partitionEpochId,
      partitionStartedAtStep: epoch.startedAtStep,
      partitionClosedAtStep: epoch.closedAtStep,
      reconciledAtStep: step,
      status,
      authorityDecisionIds: this.decisions.map((row) => row.decisionId),
      receiverReceiptIds: this.receiverReceipts.map((row) => row.receiverReceiptId),
    };
    return {
      schema: 'standards-message-reconciliation/1',
      reconciliationId: digest('standardmessagereconciliation1', body),
      ...body,
      claimBoundary:
        'This receipt preserves the partition history and classifies returning authority. It does not rewrite message history or silently merge conflicting authority.',
    };
  }

  snapshot() {
    const body = {
      profileId: this.profile.profileId,
      authorityGeneration: this.profile.authorityGeneration,
      linkState: this.linkState,
      partitionEpoch: this.partitionEpoch,
      closedEpochs: this.closedEpochs,
      decisionIds: this.decisions.map((row) => row.decisionId),
      ticketIds: [...this.tickets.values()].map((row) => row.ticketId),
      acceptedMessageIds: [...this.acceptedMessageIds].sort(),
      receiverReceiptIds: this.receiverReceipts.map((row) => row.receiverReceiptId),
      lastStep: this.lastStep,
    };
    return {
      schema: 'standards-message-authority-runtime-state/1',
      runtimeStateId: digest('standardmessageauthoritystate1', body),
      ...body,
      claimBoundary:
        'This state belongs to the rehearsal authority sidecar. It contains no standard payload bytes and no operational execution surface.',
    };
  }
}

export function createDefaultRehearsalAuthorityProfile({
  artifactAdmissionId,
  artifactUseId,
  catalogId,
  authorityGeneration = 1,
  offlineLeaseSteps = 5,
}) {
  return validateAuthorityProfile({
    schema: 'standards-message-authority-profile/1',
    profileId: 'c2sim-semantic-rehearsal-authority/1',
    standardId: 'siso-std-019-2020-c2sim',
    artifactAdmissionId,
    artifactUseId,
    catalogId,
    authorityGeneration,
    offlineLeaseSteps,
    profiles: {
      connected: {
        allowedMessageClasses: [...MESSAGE_CLASSES],
        localOperatorRequiredClasses: [],
      },
      headquarters_denied: {
        allowedMessageClasses: ['order', 'report'],
        localOperatorRequiredClasses: ['order'],
      },
      isolated: {
        allowedMessageClasses: ['report'],
        localOperatorRequiredClasses: [],
      },
    },
    claimBoundary:
      'This profile exists only for deterministic, unclassified C2SIM rehearsal. It grants no operational command, targeting, engagement, effector, or weapons authority.',
  });
}
