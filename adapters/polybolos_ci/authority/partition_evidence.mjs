import { createHash, createPublicKey, verify as verifyMessage } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { canonicalJson } from './authority_gate.mjs';

const ZERO_RECORD = '0'.repeat(64);

function requireCondition(condition, message) {
  if (!condition) throw new Error(message);
}

function isRecord(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function digest(prefix, value) {
  return `${prefix}_${createHash('sha256').update(canonicalJson(value), 'utf8').digest('hex')}`;
}

function recordIdentityBody(record) {
  const { recordId: _recordId, signature: _signature, ...body } = record;
  return body;
}

function signedRecordBody(record) {
  const { signature: _signature, ...body } = record;
  return body;
}

function trustedNodeKey(record, nodeTrustStore) {
  requireCondition(
    isRecord(nodeTrustStore) && nodeTrustStore.schema === 'axm-node-trust/1' && Array.isArray(nodeTrustStore.keys),
    'node trust store is invalid',
  );
  return nodeTrustStore.keys.find((row) =>
    isRecord(row)
    && row.keyId === record.signature?.keyId
    && row.nodeId === record.nodeId
    && row.algorithm === 'Ed25519'
  );
}

export function verifyPartitionJournal(journalPath, nodeTrustStore) {
  const bytes = readFileSync(journalPath);
  requireCondition(bytes.length > 0, 'partition journal is empty');
  requireCondition(bytes.at(-1) === 0x0a, 'partition journal contains an incomplete tail');
  const lines = bytes.toString('utf8').split('\n').filter(Boolean);
  const records = [];
  let previousRecordId = ZERO_RECORD;

  for (let index = 0; index < lines.length; index += 1) {
    let record;
    try {
      record = JSON.parse(lines[index]);
    } catch (error) {
      throw new Error(`partition journal JSON is invalid at record ${index + 1}: ${error.message}`);
    }
    requireCondition(
      isRecord(record) && record.schema === 'axm-partition-journal-record/1',
      `partition journal schema is invalid at record ${index + 1}`,
    );
    requireCondition(record.sequence === index + 1, `partition journal sequence is invalid at record ${index + 1}`);
    requireCondition(record.previousRecordId === previousRecordId, `partition journal chain is invalid at record ${index + 1}`);
    requireCondition(
      record.recordId === digest('partitionrecord1', recordIdentityBody(record)),
      `partition journal identity is invalid at record ${index + 1}`,
    );
    requireCondition(
      isRecord(record.signature)
        && record.signature.algorithm === 'Ed25519'
        && typeof record.signature.value === 'string',
      `partition journal signature metadata is invalid at record ${index + 1}`,
    );
    const key = trustedNodeKey(record, nodeTrustStore);
    requireCondition(key && typeof key.publicKeyPem === 'string', `partition journal key is untrusted at record ${index + 1}`);
    let verified = false;
    try {
      verified = verifyMessage(
        null,
        Buffer.from(canonicalJson(signedRecordBody(record)), 'utf8'),
        createPublicKey(key.publicKeyPem),
        Buffer.from(record.signature.value, 'base64'),
      );
    } catch {
      verified = false;
    }
    requireCondition(verified, `partition journal signature is invalid at record ${index + 1}`);
    requireCondition(isRecord(record.stateAfter), `partition journal state is invalid at record ${index + 1}`);
    requireCondition(record.stateAfter.journalSequence === record.sequence, `partition state sequence is invalid at record ${index + 1}`);
    previousRecordId = record.recordId;
    records.push(record);
  }

  return {
    schema: 'axm-partition-journal-verification/1',
    records,
    recordCount: records.length,
    lastRecordId: previousRecordId,
    journalSha256: createHash('sha256').update(bytes).digest('hex'),
    finalState: records.at(-1).stateAfter,
  };
}

function partitionDecisionIdentityBody(decision) {
  return {
    baseDecisionId: decision.baseDecisionId,
    candidateId: decision.candidateId,
    snapshotId: decision.snapshotId,
    authorityId: decision.authorityId,
    checkedAt: decision.checkedAt,
    profileId: decision.profileId,
    epochId: decision.epochId,
    epochStartedAt: decision.epochStartedAt,
    elapsedMs: decision.elapsedMs,
    disposition: decision.disposition,
    reason: decision.reason,
  };
}

export function verifyPartitionDecisionEvidence(decision, journalVerification) {
  requireCondition(
    isRecord(decision) && decision.schema === 'axm-partition-authority-decision/1',
    'partition decision schema is invalid',
  );
  requireCondition(
    decision.decisionId === digest('partitiondecision1', partitionDecisionIdentityBody(decision)),
    'partition decision identity is invalid',
  );
  const index = journalVerification.records.findIndex((record) =>
    record.event?.type === 'candidate_evaluated'
    && record.event?.decisionId === decision.decisionId
  );
  requireCondition(index >= 0, 'partition decision is absent from the signed journal');
  const record = journalVerification.records[index];
  requireCondition(record.event.at === decision.checkedAt, 'partition decision time differs from the signed journal');
  requireCondition(record.event.disposition === decision.disposition, 'partition disposition differs from the signed journal');
  requireCondition(record.event.reasonCode === decision.reason?.code, 'partition reason differs from the signed journal');
  requireCondition(
    Array.isArray(record.stateAfter.decisionIds) && record.stateAfter.decisionIds.includes(decision.decisionId),
    'partition decision is absent from signed runtime state',
  );
  if (decision.epochId) {
    const activeIds = record.stateAfter.activeEpoch?.decisionIds ?? [];
    const pendingIds = record.stateAfter.pendingReconciliation?.epoch?.decisionIds ?? [];
    requireCondition(
      activeIds.includes(decision.decisionId) || pendingIds.includes(decision.decisionId),
      'partition decision is absent from the signed epoch state',
    );
  }
  return {
    recordSequence: record.sequence,
    recordId: record.recordId,
    journalSha256: journalVerification.journalSha256,
    lastRecordId: journalVerification.lastRecordId,
  };
}

function reconciliationIdentityBody(reconciliation) {
  return {
    epochId: reconciliation.epochId,
    priorAuthorityId: reconciliation.priorAuthorityId,
    returningAuthorityId: reconciliation.returningAuthorityId,
    startedAt: reconciliation.startedAt,
    endedAt: reconciliation.endedAt,
    reconciledAt: reconciliation.reconciledAt,
    localDecisionIds: reconciliation.localDecisionIds,
    disposition: reconciliation.disposition,
  };
}

export function verifyPartitionReconciliationEvidence(reconciliation, journalVerification) {
  requireCondition(
    isRecord(reconciliation) && reconciliation.schema === 'axm-partition-reconciliation/1',
    'partition reconciliation schema is invalid',
  );
  requireCondition(
    reconciliation.reconciliationId === digest('partitionreconciliation1', reconciliationIdentityBody(reconciliation)),
    'partition reconciliation identity is invalid',
  );
  const index = journalVerification.records.findIndex((record) =>
    record.event?.type === 'partition_reconciled'
    && record.event?.reconciliationId === reconciliation.reconciliationId
  );
  requireCondition(index >= 0, 'partition reconciliation is absent from the signed journal');
  const record = journalVerification.records[index];
  const priorState = index > 0 ? journalVerification.records[index - 1].stateAfter : null;
  requireCondition(priorState?.pendingReconciliation, 'signed journal had no pending partition before reconciliation');
  requireCondition(
    priorState.pendingReconciliation.epoch.epochId === reconciliation.epochId,
    'reconciliation epoch differs from signed pending state',
  );
  requireCondition(
    priorState.pendingReconciliation.epoch.authorityId === reconciliation.priorAuthorityId,
    'reconciliation prior authority differs from signed pending state',
  );
  requireCondition(
    canonicalJson(priorState.pendingReconciliation.epoch.decisionIds) === canonicalJson(reconciliation.localDecisionIds),
    'reconciliation decision set differs from signed pending state',
  );
  requireCondition(record.event.at === reconciliation.reconciledAt, 'reconciliation time differs from signed journal');
  requireCondition(record.event.disposition === reconciliation.disposition, 'reconciliation disposition differs from signed journal');
  if (reconciliation.disposition === 'explicitly_superseded') {
    requireCondition(record.stateAfter.pendingReconciliation === null, 'explicit reconciliation did not clear signed pending state');
    requireCondition(
      record.stateAfter.currentAuthorityId === reconciliation.returningAuthorityId,
      'explicit reconciliation did not install the returning authority in signed state',
    );
  } else {
    requireCondition(record.stateAfter.pendingReconciliation !== null, 'human-required reconciliation silently cleared pending state');
  }
  return {
    recordSequence: record.sequence,
    recordId: record.recordId,
    journalSha256: journalVerification.journalSha256,
    lastRecordId: journalVerification.lastRecordId,
  };
}
