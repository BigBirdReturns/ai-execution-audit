import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import {
  MessageAuthorityRuntime,
  canonicalJson,
  createDefaultRehearsalAuthorityProfile,
} from '../semantic/authority_sidecar.mjs';
import {
  createTestPacket,
  runFaultScenario,
} from '../test_hosts/core/fault_machine.mjs';
import { verifyConversation } from '../semantic/run_semantic_rehearsal.mjs';

const LINK_STATES = new Set(['connected', 'headquarters_denied', 'isolated']);
const RETURN_MODES = new Set(['continuous', 'superseding', 'conflicting', 'absent']);
const ISSUABLE_CLASSES = new Set(['order', 'report']);
const LEASE_PRESETS = new Set([0, 2, 5, 10]);
const MAX_ADVANCE_STEPS = 100;

export class RehearsalSessionError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'RehearsalSessionError';
    this.code = code;
  }
}

function requireCondition(condition, code, message) {
  if (!condition) throw new RehearsalSessionError(code, message);
}

function isRecord(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function digest(prefix, value) {
  return `${prefix}_${createHash('sha256').update(canonicalJson(value), 'utf8').digest('hex')}`;
}

function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf8'));
}

function normalizeConfig(input = {}) {
  requireCondition(isRecord(input), 'CONFIG_INVALID', 'configuration must be an object');
  const config = {
    offlineLeaseSteps: input.offlineLeaseSteps ?? 5,
    localOperatorPresent: input.localOperatorPresent ?? true,
    duplicateOrder: input.duplicateOrder ?? true,
    delayReport: input.delayReport ?? true,
    returnMode: input.returnMode ?? 'superseding',
  };
  requireCondition(
    Number.isSafeInteger(config.offlineLeaseSteps) && LEASE_PRESETS.has(config.offlineLeaseSteps),
    'LEASE_PRESET_INVALID',
    'offlineLeaseSteps must be one of 0, 2, 5, or 10',
  );
  for (const key of ['localOperatorPresent', 'duplicateOrder', 'delayReport']) {
    requireCondition(typeof config[key] === 'boolean', 'CONFIG_INVALID', `${key} must be boolean`);
  }
  requireCondition(RETURN_MODES.has(config.returnMode), 'RETURN_MODE_INVALID', 'returnMode is invalid');
  return config;
}

function publicDecision(decision) {
  if (!decision) return null;
  return {
    decisionId: decision.decisionId,
    messageId: decision.messageId,
    messageClass: decision.messageClass,
    evaluatedAtStep: decision.evaluatedAtStep,
    linkState: decision.linkState,
    partitionEpochId: decision.partitionEpochId,
    offlineElapsedSteps: decision.offlineElapsedSteps,
    leaseExpiresAtStep: decision.leaseExpiresAtStep,
    localOperatorPresent: decision.localOperatorPresent,
    disposition: decision.disposition,
    reason: decision.reason,
  };
}

function publicReceiverReceipt(receipt) {
  return {
    receiverReceiptId: receipt.receiverReceiptId,
    messageId: receipt.messageId,
    messageClass: receipt.messageClass,
    receivedAtStep: receipt.receivedAtStep,
    disposition: receipt.disposition,
    reason: receipt.reason,
  };
}

function publicReconciliation(receipt) {
  if (!receipt) return null;
  return {
    reconciliationId: receipt.reconciliationId,
    partitionEpochId: receipt.partitionEpochId,
    localAuthorityGeneration: receipt.localAuthorityGeneration,
    returningAuthorityGeneration: receipt.returningAuthorityGeneration,
    supersedesGeneration: receipt.supersedesGeneration,
    reconciledAtStep: receipt.reconciledAtStep,
    status: receipt.status,
  };
}

export function loadRehearsalFixture(evidenceRoot) {
  const root = resolve(evidenceRoot);
  const conversationDir = join(root, 'semantic-conversation');
  const conversation = readJson(join(conversationDir, 'conversation.json'));
  const transaction = readJson(join(root, 'artifact-transaction.json'));
  const catalog = readJson(join(root, 'xsd11-catalog.json'));
  const { payloadByMessageId, receiptByMessageId } = verifyConversation(conversation, conversationDir);

  requireCondition(
    transaction?.admission?.admissionId === conversation.artifactAdmissionId,
    'FIXTURE_ARTIFACT_MISMATCH',
    'semantic conversation uses another artifact admission',
  );
  requireCondition(
    transaction?.use?.useId === conversation.artifactUseId,
    'FIXTURE_ARTIFACT_MISMATCH',
    'semantic conversation uses another artifact use',
  );
  requireCondition(
    catalog?.catalogId === conversation.catalogId,
    'FIXTURE_CATALOG_MISMATCH',
    'semantic conversation uses another structural catalog',
  );

  const packetByClass = new Map();
  const receiptByClass = new Map();
  const payloadByPacketId = new Map();
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
    packetByClass.set(receipt.messageClass, packet);
    receiptByClass.set(receipt.messageClass, receipt);
    payloadByPacketId.set(packet.packetId, payload);
  }

  return {
    root,
    conversation,
    transaction,
    catalog,
    packetByClass,
    receiptByClass,
    payloadByPacketId,
    fixtureIdentity: {
      semanticConversationId: conversation.semanticConversationId,
      artifactAdmissionId: conversation.artifactAdmissionId,
      artifactUseId: conversation.artifactUseId,
      catalogId: conversation.catalogId,
      standardId: transaction.admission.standardId,
      standardRevision: transaction.admission.standardRevision,
    },
  };
}

function deriveAuthorityPosture(runtimeState, profile, step, reconciliation) {
  if (reconciliation) {
    return {
      mode: reconciliation.status,
      partitionEpochId: reconciliation.partitionEpochId,
      startedAtStep: reconciliation.partitionStartedAtStep,
      expiresAtStep: reconciliation.partitionStartedAtStep + profile.offlineLeaseSteps,
      elapsedSteps: reconciliation.partitionClosedAtStep - reconciliation.partitionStartedAtStep,
      remainingSteps: 0,
      expired: reconciliation.partitionClosedAtStep > reconciliation.partitionStartedAtStep + profile.offlineLeaseSteps,
    };
  }
  if (runtimeState.linkState === 'connected') {
    return {
      mode: 'connected',
      partitionEpochId: null,
      startedAtStep: null,
      expiresAtStep: null,
      elapsedSteps: 0,
      remainingSteps: null,
      expired: false,
    };
  }
  const epoch = runtimeState.partitionEpoch;
  requireCondition(epoch, 'PARTITION_EPOCH_MISSING', 'degraded runtime has no partition epoch');
  const expiresAtStep = epoch.startedAtStep + profile.offlineLeaseSteps;
  const elapsedSteps = Math.max(0, step - epoch.startedAtStep);
  const expired = step > expiresAtStep;
  return {
    mode: expired ? 'lease_expired' : runtimeState.linkState,
    partitionEpochId: epoch.partitionEpochId,
    startedAtStep: epoch.startedAtStep,
    expiresAtStep,
    elapsedSteps,
    remainingSteps: Math.max(0, expiresAtStep - step),
    expired,
  };
}

export class StandardsRehearsalSession {
  constructor({ fixture, provenance = {}, config = {} }) {
    requireCondition(fixture?.conversation, 'FIXTURE_INVALID', 'fixture is missing the semantic conversation');
    this.fixture = fixture;
    this.provenance = structuredClone(provenance);
    this.reset(config);
  }

  reset(config = {}) {
    this.config = normalizeConfig(config);
    this.profile = createDefaultRehearsalAuthorityProfile({
      artifactAdmissionId: this.fixture.transaction.admission.admissionId,
      artifactUseId: this.fixture.transaction.use.useId,
      catalogId: this.fixture.catalog.catalogId,
      authorityGeneration: 1,
      offlineLeaseSteps: this.config.offlineLeaseSteps,
    });
    this.runtime = new MessageAuthorityRuntime(this.profile);
    this.currentStep = -1;
    this.transportEvents = [];
    this.sentClasses = new Set();
    this.ticketByMessageId = new Map();
    this.processedDeliveryIds = new Set();
    this.transportRun = null;
    this.reconciliation = null;
    this.userActions = [];
    this.events = [];
    this._issueAutomatic('submit_initialization');
    this._issueAutomatic('object_initialization');
    this._record('reset', {
      disposition: 'ready',
      reason: 'INITIALIZATION_ACCEPTED',
      config: this.config,
    });
    return this.publicState();
  }

  _nextStep(delta = 1) {
    requireCondition(
      Number.isSafeInteger(delta) && delta >= 1 && delta <= MAX_ADVANCE_STEPS,
      'STEP_DELTA_INVALID',
      `step delta must be between 1 and ${MAX_ADVANCE_STEPS}`,
    );
    this.currentStep += delta;
    return this.currentStep;
  }

  _record(action, result = {}, user = false, input = null) {
    const row = {
      sequence: this.events.length,
      step: this.currentStep,
      action,
      disposition: result.disposition ?? null,
      reason: result.reason ?? null,
      messageClass: result.messageClass ?? null,
      decisionId: result.decisionId ?? null,
      receiverReceiptId: result.receiverReceiptId ?? null,
      reconciliationId: result.reconciliationId ?? null,
    };
    this.events.push(row);
    if (user) this.userActions.push({ action, input: input ?? {} });
    return row;
  }

  _issueAutomatic(messageClass) {
    const step = this._nextStep();
    const receipt = this.fixture.receiptByClass.get(messageClass);
    const result = this.runtime.evaluateMessage(receipt, {
      step,
      localOperatorPresent: true,
    });
    requireCondition(result.decision.disposition === 'allow', 'INITIALIZATION_REFUSED', `${messageClass} was not admitted`);
    this.ticketByMessageId.set(receipt.messageId, result.ticket);
    this.sentClasses.add(messageClass);
    this.transportEvents.push({
      step,
      type: 'send',
      packetId: this.fixture.packetByClass.get(messageClass).packetId,
      behavior: 'pass',
    });
    this._recomputeTransport();
    this._record('automatic_message', {
      ...result.decision,
      messageClass,
    });
  }

  _transportScenario() {
    return {
      schema: 'standards-port-fault-scenario/1',
      scenarioId: 'interactive-c2sim-denied-communications-rehearsal',
      mode: 'rehearsal',
      profileId: this.fixture.transaction.use.profileId,
      portId: this.fixture.transaction.use.portId,
      standardId: this.fixture.transaction.admission.standardId,
      artifactUseId: this.fixture.transaction.use.useId,
      initialLinkState: 'up',
      partitionPolicy: 'buffer',
      queueCapacity: 4,
      events: this.transportEvents,
      claimBoundary:
        'This scenario is assembled by the local standards rehearsal host and executed by the canonical payload-opaque fault machine. It is not an operational network or command scenario.',
    };
  }

  _recomputeTransport() {
    const sendPacketIds = this.transportEvents
      .filter((event) => event.type === 'send')
      .map((event) => event.packetId);
    const packets = sendPacketIds.map((packetId) => {
      for (const packet of this.fixture.packetByClass.values()) {
        if (packet.packetId === packetId) return packet;
      }
      throw new RehearsalSessionError('PACKET_UNKNOWN', `unknown packet ${packetId}`);
    });
    const payloads = new Map(
      sendPacketIds.map((packetId) => [packetId, this.fixture.payloadByPacketId.get(packetId)]),
    );
    this.transportRun = runFaultScenario({
      scenario: this._transportScenario(),
      packets,
      payloads,
      artifactTransaction: this.fixture.transaction,
      catalog: this.fixture.catalog,
    });
    for (const delivery of this.transportRun.deliveries) {
      if (this.processedDeliveryIds.has(delivery.deliveryId)) continue;
      const ticket = this.ticketByMessageId.get(delivery.messageIdentity);
      requireCondition(ticket, 'DELIVERY_TICKET_MISSING', `delivery ${delivery.deliveryId} has no authority ticket`);
      const receipt = this.runtime.receiveDelivery(ticket, delivery, delivery.deliveryStep);
      this.processedDeliveryIds.add(delivery.deliveryId);
      this._record('receiver_delivery', receipt);
    }
  }

  setConfiguration(patch) {
    requireCondition(isRecord(patch), 'CONFIG_INVALID', 'configuration patch must be an object');
    const allowed = new Set(['localOperatorPresent', 'duplicateOrder', 'delayReport', 'returnMode']);
    const unknown = Object.keys(patch).filter((key) => !allowed.has(key));
    requireCondition(unknown.length === 0, 'CONFIG_FIELD_INVALID', `unsupported live configuration field ${unknown[0]}`);
    const next = normalizeConfig({ ...this.config, ...patch });
    requireCondition(
      next.offlineLeaseSteps === this.config.offlineLeaseSteps,
      'LEASE_CHANGE_REQUIRES_RESET',
      'offline lease changes require reset',
    );
    this.config = next;
    this._record('set_configuration', {
      disposition: 'updated',
      reason: 'LIVE_CONFIGURATION_UPDATED',
    }, true, patch);
    return this.publicState();
  }

  cutHeadquarters() {
    requireCondition(this.runtime.linkState === 'connected', 'LINK_TRANSITION_INVALID', 'headquarters can only be cut from connected state');
    const step = this._nextStep();
    this.runtime.setLinkState('headquarters_denied', step);
    this.transportEvents.push({ step, type: 'link', state: 'down' });
    this._recomputeTransport();
    this._record('cut_headquarters', {
      disposition: 'degraded',
      reason: 'HEADQUARTERS_LINK_DENIED',
    }, true);
    return this.publicState();
  }

  isolate() {
    requireCondition(this.runtime.linkState !== 'isolated', 'LINK_TRANSITION_INVALID', 'node is already isolated');
    requireCondition(this.runtime.linkState !== 'connected' || this.transportEvents.at(-1)?.type !== 'link', 'LINK_TRANSITION_INVALID', 'invalid isolation transition');
    const prior = this.runtime.linkState;
    const step = this._nextStep();
    this.runtime.setLinkState('isolated', step);
    if (prior === 'connected') {
      this.transportEvents.push({ step, type: 'link', state: 'down' });
      this._recomputeTransport();
    }
    this._record('isolate', {
      disposition: 'degraded',
      reason: 'NODE_ISOLATED',
    }, true);
    return this.publicState();
  }

  restore() {
    requireCondition(this.runtime.linkState !== 'connected', 'LINK_TRANSITION_INVALID', 'communications are already connected');
    const step = this._nextStep();
    this.runtime.setLinkState('connected', step);
    this.transportEvents.push({ step, type: 'link', state: 'up' });
    this._recomputeTransport();
    this._record('restore', {
      disposition: 'connected',
      reason: 'COMMUNICATIONS_RESTORED',
    }, true);
    return this.publicState();
  }

  issue(messageClass) {
    requireCondition(ISSUABLE_CLASSES.has(messageClass), 'MESSAGE_CLASS_INVALID', 'only order and report may be issued interactively');
    requireCondition(!this.sentClasses.has(messageClass), 'MESSAGE_ALREADY_SENT', `${messageClass} has already entered transport`);
    const step = this._nextStep();
    const receipt = this.fixture.receiptByClass.get(messageClass);
    const result = this.runtime.evaluateMessage(receipt, {
      step,
      localOperatorPresent: this.config.localOperatorPresent,
    });
    this._record('issue_message', result.decision, true, { messageClass });
    if (result.decision.disposition !== 'allow') return this.publicState();

    this.ticketByMessageId.set(receipt.messageId, result.ticket);
    this.sentClasses.add(messageClass);
    const event = {
      step,
      type: 'send',
      packetId: this.fixture.packetByClass.get(messageClass).packetId,
      behavior: 'pass',
    };
    if (messageClass === 'order' && this.config.duplicateOrder) {
      event.behavior = 'duplicate';
      event.copies = 2;
    }
    if (messageClass === 'report' && this.config.delayReport) {
      event.behavior = 'delay';
      event.releaseAt = step + 1;
    }
    this.transportEvents.push(event);
    this._recomputeTransport();
    return this.publicState();
  }

  advance(steps = 1) {
    this._nextStep(steps);
    this._record('advance', {
      disposition: 'advanced',
      reason: 'AUTHORITY_CLOCK_ADVANCED',
    }, true, { steps });
    return this.publicState();
  }

  reconcile() {
    requireCondition(this.runtime.linkState === 'connected', 'RECONCILIATION_LINK_INVALID', 'restore communications before reconciliation');
    requireCondition(this.runtime.closedEpochs.length > 0, 'RECONCILIATION_EPOCH_MISSING', 'no closed partition epoch exists');
    if (this.config.returnMode === 'absent') {
      this._record('reconcile', {
        disposition: 'not_attempted',
        reason: 'RETURNING_AUTHORITY_ABSENT',
      }, true);
      return this.publicState();
    }
    const step = this._nextStep();
    const args = {
      step,
      returningAuthorityGeneration: 1,
      supersedesGeneration: null,
    };
    if (this.config.returnMode === 'superseding') {
      args.returningAuthorityGeneration = 2;
      args.supersedesGeneration = 1;
    } else if (this.config.returnMode === 'conflicting') {
      args.returningAuthorityGeneration = 2;
      args.supersedesGeneration = null;
    }
    this.reconciliation = this.runtime.reconcile(args);
    this._record('reconcile', {
      disposition: this.reconciliation.status,
      reason: 'RETURNING_AUTHORITY_CLASSIFIED',
      reconciliationId: this.reconciliation.reconciliationId,
    }, true);
    return this.publicState();
  }

  apply(action, input = {}) {
    switch (action) {
      case 'reset':
        this.userActions.push({ action: 'reset', input });
        return this.reset(input);
      case 'set_configuration':
        return this.setConfiguration(input);
      case 'cut_headquarters':
        return this.cutHeadquarters();
      case 'isolate':
        return this.isolate();
      case 'restore':
        return this.restore();
      case 'issue_order':
        return this.issue('order');
      case 'issue_report':
        return this.issue('report');
      case 'advance':
        return this.advance(input.steps ?? 1);
      case 'reconcile':
        return this.reconcile();
      default:
        throw new RehearsalSessionError('ACTION_UNKNOWN', `unknown action ${action}`);
    }
  }

  publicState() {
    const runtimeState = this.runtime.snapshot();
    const decisions = this.runtime.decisions.map(publicDecision);
    const receiverReceipts = this.runtime.receiverReceipts.map(publicReceiverReceipt);
    const posture = deriveAuthorityPosture(
      runtimeState,
      this.profile,
      this.currentStep,
      this.reconciliation,
    );
    const accepted = receiverReceipts.filter((row) => row.disposition === 'accept');
    const refused = receiverReceipts.filter((row) => row.disposition === 'refuse');
    const latestDecision = decisions.at(-1) ?? null;
    const latestReceiver = receiverReceipts.at(-1) ?? null;
    const status = this.reconciliation?.status
      ?? (latestDecision?.disposition === 'safe_state' ? 'safe_state' : posture.mode);
    const stateBody = {
      fixture: this.fixture.fixtureIdentity,
      config: this.config,
      currentStep: this.currentStep,
      status,
      linkState: runtimeState.linkState,
      posture,
      latestDecision,
      latestReceiver,
      reconciliation: publicReconciliation(this.reconciliation),
      messages: {
        schemaValid: this.fixture.conversation.messages.length,
        authorityDecisions: decisions.length,
        authorityAllowed: decisions.filter((row) => row.disposition === 'allow').length,
        authorityHeld: decisions.filter((row) => row.disposition === 'hold').length,
        authorityRefused: decisions.filter((row) => row.disposition === 'refuse').length,
        safeStateDecisions: decisions.filter((row) => row.disposition === 'safe_state').length,
        receiverAccepted: accepted.length,
        receiverRefused: refused.length,
        replayRefused: refused.filter((row) => row.reason === 'MESSAGE_REPLAY').length,
        expiredTickets: refused.filter((row) => row.reason === 'ADMISSION_TICKET_EXPIRED').length,
      },
      transport: this.transportRun
        ? {
            runId: this.transportRun.runId,
            journalRoot: this.transportRun.journalRoot,
            metrics: this.transportRun.metrics,
            pending: this.transportRun.pending,
          }
        : null,
      decisions,
      receiverReceipts,
      events: this.events.slice(-80),
      provenance: this.provenance,
    };
    return {
      schema: 'standards-interactive-rehearsal-state/1',
      stateId: digest('standardsinteractivestate1', stateBody),
      ...stateBody,
      claimBoundary:
        'This state is produced by the canonical standards authority runtime and a local deterministic rehearsal conductor. It alters no C2SIM XML and grants no operational authority.',
    };
  }

  exportReceipt() {
    const state = this.publicState();
    const body = {
      fixtureIdentity: this.fixture.fixtureIdentity,
      config: this.config,
      userActions: this.userActions,
      finalStateId: state.stateId,
      authorityDecisionIds: state.decisions.map((row) => row.decisionId),
      receiverReceiptIds: state.receiverReceipts.map((row) => row.receiverReceiptId),
      reconciliationId: state.reconciliation?.reconciliationId ?? null,
      transportRunId: state.transport?.runId ?? null,
      provenance: this.provenance,
    };
    return {
      schema: 'standards-interactive-rehearsal-receipt/1',
      receiptId: digest('standardsinteractiverehearsal1', body),
      ...body,
      claimBoundary:
        'This receipt replays one local standards rehearsal session. It does not prove target-host installation, operational command authority, or weapons effect.',
    };
  }
}

export function verifySessionReceipt(receipt, { fixture, provenance = {} }) {
  requireCondition(
    isRecord(receipt) && receipt.schema === 'standards-interactive-rehearsal-receipt/1',
    'SESSION_RECEIPT_INVALID',
    'interactive rehearsal receipt schema is invalid',
  );
  requireCondition(Array.isArray(receipt.userActions), 'SESSION_RECEIPT_INVALID', 'userActions must be an array');
  const session = new StandardsRehearsalSession({ fixture, provenance, config: receipt.config });
  for (const row of receipt.userActions) {
    requireCondition(isRecord(row) && typeof row.action === 'string', 'SESSION_RECEIPT_INVALID', 'user action is invalid');
    if (row.action === 'reset') {
      session.reset(row.input ?? {});
      continue;
    }
    session.apply(row.action, row.input ?? {});
  }
  const rebuilt = session.exportReceipt();
  requireCondition(
    rebuilt.receiptId === receipt.receiptId,
    'SESSION_RECEIPT_MISMATCH',
    'interactive rehearsal receipt does not replay to the same identity',
  );
  return {
    schema: 'standards-interactive-rehearsal-verification/1',
    status: 'pass',
    receiptId: receipt.receiptId,
    finalStateId: rebuilt.finalStateId,
    userActions: receipt.userActions.length,
    authorityDecisionIds: rebuilt.authorityDecisionIds,
    receiverReceiptIds: rebuilt.receiverReceiptIds,
    reconciliationId: rebuilt.reconciliationId,
    transportRunId: rebuilt.transportRunId,
    claimBoundary:
      'This receipt replays the interactive session through the same canonical authority runtime and fixture custody. It grants no operational authority.',
  };
}
