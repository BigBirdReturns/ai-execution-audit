#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { join } from 'node:path';
import { readFileSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { verifyFaultFrame } from '../test_hosts/core/fault_verifier.mjs';
import {
  validateAuthorityProfile,
  verifyAdmissionTicket,
  verifyAuthorityDecision,
  verifyReceiverReceipt,
  verifyReconciliation,
} from './authority_sidecar.mjs';
import {
  canonicalJson,
  createHostFrame,
  digest,
  verifyConversation,
} from './run_semantic_rehearsal.mjs';

class SemanticVerificationError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'SemanticVerificationError';
    this.code = code;
  }
}

function requireCondition(condition, code, message) {
  if (!condition) throw new SemanticVerificationError(code, message);
}

function isRecord(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf8'));
}

function sha256File(path) {
  return createHash('sha256').update(readFileSync(path)).digest('hex');
}

function verifyBinding(binding, conversation, faultRun) {
  requireCondition(
    isRecord(binding) && binding.schema === 'standards-semantic-packet-binding/1',
    'SEMANTIC_BINDING_INVALID',
    'semantic packet binding schema is invalid',
  );
  requireCondition(
    binding.semanticConversationId === conversation.semanticConversationId,
    'SEMANTIC_BINDING_INVALID',
    'semantic packet binding cites another conversation',
  );
  requireCondition(Array.isArray(binding.bindings), 'SEMANTIC_BINDING_INVALID', 'semantic packet bindings are missing');
  requireCondition(binding.bindings.length === conversation.messages.length, 'SEMANTIC_BINDING_INVALID', 'semantic packet count differs from conversation');
  const receipts = new Map(conversation.messages.map((row) => [row.messageId, row]));
  const packetIds = [];
  const seenMessages = new Set();
  for (const row of binding.bindings) {
    const receipt = receipts.get(row.messageId);
    requireCondition(receipt, 'SEMANTIC_BINDING_INVALID', `binding cites unknown message ${row.messageId}`);
    requireCondition(!seenMessages.has(row.messageId), 'SEMANTIC_BINDING_INVALID', `message ${row.messageId} is bound twice`);
    seenMessages.add(row.messageId);
    requireCondition(row.messageReceiptId === receipt.messageReceiptId, 'SEMANTIC_BINDING_INVALID', 'binding receipt identity differs');
    requireCondition(row.messageClass === receipt.messageClass, 'SEMANTIC_BINDING_INVALID', 'binding message class differs');
    requireCondition(row.payloadSha256 === receipt.payloadSha256, 'SEMANTIC_BINDING_INVALID', 'binding semantic payload differs');
    requireCondition(row.packetPayloadDigest === receipt.payloadSha256, 'SEMANTIC_BINDING_INVALID', 'transport packet payload differs');
    requireCondition(typeof row.packetId === 'string' && row.packetId.startsWith('standardtestpacket1_'), 'SEMANTIC_BINDING_INVALID', 'binding packet identity is invalid');
    packetIds.push(row.packetId);
  }
  requireCondition(
    canonicalJson([...packetIds].sort()) === canonicalJson(faultRun.packetIds),
    'SEMANTIC_BINDING_INVALID',
    'semantic packet binding differs from fault-run packet set',
  );
  return true;
}

function verifyAuthority(authority, conversation, faultRun) {
  requireCondition(isRecord(authority), 'AUTHORITY_BUNDLE_INVALID', 'authority bundle is invalid');
  const profile = validateAuthorityProfile(authority.profile);
  requireCondition(Array.isArray(authority.decisions), 'AUTHORITY_BUNDLE_INVALID', 'authority decisions are missing');
  requireCondition(Array.isArray(authority.tickets), 'AUTHORITY_BUNDLE_INVALID', 'authority tickets are missing');
  requireCondition(Array.isArray(authority.receiverReceipts), 'AUTHORITY_BUNDLE_INVALID', 'receiver receipts are missing');
  const messageReceipts = new Map(conversation.messages.map((row) => [row.messageReceiptId, row]));
  const decisionsById = new Map();
  for (const decision of authority.decisions) {
    verifyAuthorityDecision(decision, profile);
    requireCondition(messageReceipts.has(decision.messageReceiptId), 'AUTHORITY_BUNDLE_INVALID', 'authority decision cites unknown semantic receipt');
    decisionsById.set(decision.decisionId, decision);
  }
  const ticketsById = new Map();
  for (const ticket of authority.tickets) {
    const decision = decisionsById.get(ticket.decisionId);
    requireCondition(decision, 'AUTHORITY_BUNDLE_INVALID', 'admission ticket cites unknown decision');
    verifyAdmissionTicket(ticket, decision, profile);
    ticketsById.set(ticket.ticketId, ticket);
  }
  const deliveriesById = new Map(faultRun.deliveries.map((row) => [row.deliveryId, row]));
  for (const receipt of authority.receiverReceipts) {
    const ticket = ticketsById.get(receipt.ticketId);
    const delivery = deliveriesById.get(receipt.deliveryId);
    requireCondition(ticket && delivery, 'AUTHORITY_BUNDLE_INVALID', 'receiver receipt cites unknown ticket or delivery');
    verifyReceiverReceipt(receipt, ticket, delivery);
  }
  verifyReconciliation(authority.reconciliation, profile, authority.decisions, authority.receiverReceipts);
  requireCondition(
    authority.runtimeState?.schema === 'standards-message-authority-runtime-state/1',
    'AUTHORITY_BUNDLE_INVALID',
    'authority runtime state is missing',
  );
  const accepted = authority.receiverReceipts.filter((row) => row.disposition === 'accept');
  const replay = authority.receiverReceipts.filter((row) => row.reason === 'MESSAGE_REPLAY');
  requireCondition(accepted.length === 4, 'AUTHORITY_OUTCOME_INVALID', 'authority receiver did not accept four unique messages');
  requireCondition(replay.length === 1, 'AUTHORITY_OUTCOME_INVALID', 'authority receiver did not refuse exactly one duplicate order');
  requireCondition(authority.reconciliation.status === 'explicitly_superseded', 'AUTHORITY_OUTCOME_INVALID', 'partition did not close through explicit supersession');
  return true;
}

function verifyQualification(qualification, outputDir) {
  requireCondition(
    isRecord(qualification)
      && qualification.schema === 'standards-semantic-rehearsal-qualification/1'
      && qualification.status === 'pass',
    'QUALIFICATION_INVALID',
    'semantic rehearsal qualification is invalid',
  );
  requireCondition(isRecord(qualification.files), 'QUALIFICATION_INVALID', 'qualification file ledger is missing');
  for (const [name, row] of Object.entries(qualification.files)) {
    requireCondition(row.sha256 === sha256File(join(outputDir, name)), 'QUALIFICATION_FILE_MISMATCH', `qualification file ${name} changed`);
  }
  const body = {
    semanticConversationId: qualification.semanticConversationId,
    scenarioDigest: qualification.scenarioDigest,
    faultRunId: qualification.faultRunId,
    authorityDecisionIds: qualification.authorityDecisionIds,
    receiverReceiptIds: qualification.receiverReceiptIds,
    reconciliationId: qualification.reconciliationId,
    hostFrameId: qualification.hostFrameId,
    files: qualification.files,
  };
  requireCondition(
    qualification.qualificationId === digest('standardsemanticrehearsalqualification1', body),
    'QUALIFICATION_ID_INVALID',
    'semantic rehearsal qualification identity is invalid',
  );
  requireCondition(Object.values(qualification.assertions).every(Boolean), 'QUALIFICATION_ASSERTION_INVALID', 'semantic rehearsal qualification has a false assertion');
  return true;
}

function main(argv) {
  if (argv.length < 2 || argv.length > 3) {
    console.error('usage: verify_semantic_rehearsal.mjs <conversation-dir> <output-dir> [verification.json]');
    return 2;
  }
  const [conversationDir, outputDir, verificationPath] = argv;
  try {
    const conversation = readJson(join(conversationDir, 'conversation.json'));
    verifyConversation(conversation, conversationDir);
    const binding = readJson(join(outputDir, 'semantic-binding.json'));
    const faultRun = readJson(join(outputDir, 'fault-run.json'));
    const faultFrame = readJson(join(outputDir, 'fault-frame.json'));
    const faultVerification = readJson(join(outputDir, 'fault-verification.json'));
    const authority = readJson(join(outputDir, 'authority.json'));
    const hostFrame = readJson(join(outputDir, 'semantic-host-frame.json'));
    const qualification = readJson(join(outputDir, 'qualification.json'));

    verifyBinding(binding, conversation, faultRun);
    const reconstructedFault = verifyFaultFrame(faultFrame, faultRun);
    requireCondition(
      canonicalJson(reconstructedFault) === canonicalJson(faultVerification),
      'FAULT_VERIFICATION_MISMATCH',
      'retained fault verification does not reconstruct',
    );
    verifyAuthority(authority, conversation, faultRun);
    const reconstructedHost = createHostFrame({
      conversation,
      faultRun,
      faultVerification,
      authority,
      receiverReceipts: authority.receiverReceipts,
      reconciliation: authority.reconciliation,
    });
    requireCondition(
      canonicalJson(reconstructedHost) === canonicalJson(hostFrame),
      'HOST_FRAME_MISMATCH',
      'semantic host frame does not reconstruct',
    );
    const encodedHost = JSON.stringify(hostFrame).toLowerCase();
    requireCondition(!encodedHost.includes('<?xml'), 'HOST_FRAME_PAYLOAD_EXPOSURE', 'host frame exposes XML payload bytes');
    requireCondition(!encodedHost.includes('polybolos'), 'HOST_FRAME_PROVIDER_SURFACE', 'host frame contains provider vocabulary');
    requireCondition(!encodedHost.includes('dandelion'), 'HOST_FRAME_PROVIDER_SURFACE', 'host frame contains dandelion vocabulary');
    verifyQualification(qualification, outputDir);

    const body = {
      semanticConversationId: conversation.semanticConversationId,
      qualificationId: qualification.qualificationId,
      faultRunId: faultRun.runId,
      authorityDecisionIds: authority.decisions.map((row) => row.decisionId),
      receiverReceiptIds: authority.receiverReceipts.map((row) => row.receiverReceiptId),
      reconciliationId: authority.reconciliation.reconciliationId,
      hostFrameId: hostFrame.frameId,
    };
    const receipt = {
      schema: 'standards-semantic-rehearsal-verification/1',
      status: 'pass',
      verificationId: digest('standardsemanticrehearsalverification1', body),
      ...body,
      checks: {
        conversationIdentity: true,
        semanticPacketBinding: true,
        detachedFaultVerification: true,
        detachedAuthorityVerification: true,
        hostFrameReconstruction: true,
        qualificationFileCustody: true,
      },
      claimBoundary:
        'This receipt independently reconstructs the retained semantic rehearsal evidence. It does not establish an operational C2SIM profile, command authority, or weapons effect.',
    };
    if (verificationPath) writeFileSync(verificationPath, `${JSON.stringify(receipt, null, 2)}\n`, 'utf8');
    process.stdout.write(`${JSON.stringify(receipt, null, 2)}\n`);
    return 0;
  } catch (error) {
    const receipt = {
      schema: 'standards-semantic-rehearsal-verification/1',
      status: 'refuse',
      error: error instanceof SemanticVerificationError ? error.code : 'SEMANTIC_VERIFICATION_FAILED',
      message: error instanceof Error ? error.message : 'semantic rehearsal verification failed',
    };
    if (verificationPath) writeFileSync(verificationPath, `${JSON.stringify(receipt, null, 2)}\n`, 'utf8');
    process.stderr.write(`${JSON.stringify(receipt, null, 2)}\n`);
    return 1;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exitCode = main(process.argv.slice(2));
}
