import { createHash } from 'node:crypto';
import { canonicalJson } from './authority_gate.mjs';
import {
  verifyLinkObservation,
  verifyPartitionAuthority,
} from './partition_runtime.mjs';

function requireCondition(condition, message) {
  if (!condition) throw new Error(message);
}

function isRecord(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function digest(prefix, value) {
  return `${prefix}_${createHash('sha256').update(canonicalJson(value), 'utf8').digest('hex')}`;
}

function parseTime(value, label) {
  const milliseconds = Date.parse(value);
  requireCondition(Number.isFinite(milliseconds), `${label} is not a valid date-time`);
  return milliseconds;
}

function profileFor(authority, observation) {
  return authority.partitionPolicy.profiles.find((profile) =>
    Object.entries(profile.states).every(([link, state]) => observation.links[link] === state)
    && Object.keys(observation.links).length === Object.keys(profile.states).length
  ) ?? null;
}

function boundedLease(profile, decision) {
  if (!profile.partition) {
    return {
      partitioned: false,
      maxOfflineMs: 0,
      elapsedMs: null,
      remainingMs: null,
      expired: false,
      warning: false,
    };
  }
  const elapsedMs = Number.isFinite(decision.elapsedMs) ? Math.max(0, Number(decision.elapsedMs)) : null;
  const remainingMs = elapsedMs === null ? null : Math.max(0, profile.maxOfflineMs - elapsedMs);
  return {
    partitioned: true,
    maxOfflineMs: profile.maxOfflineMs,
    elapsedMs,
    remainingMs,
    expired: elapsedMs !== null && elapsedMs > profile.maxOfflineMs,
    warning:
      elapsedMs !== null
      && elapsedMs <= profile.maxOfflineMs
      && remainingMs <= Math.max(1, Math.floor(profile.maxOfflineMs * 0.2)),
  };
}

function frameFromSemantic(semantic, capturedAt) {
  parseTime(capturedAt, 'capturedAt');
  const stateId = digest('partitionstate1', semantic);
  return {
    schema: 'polybolos-partition-cabinet-frame/1',
    stateId,
    frameId: digest('partitionframe1', { stateId, capturedAt }),
    capturedAt: new Date(Date.parse(capturedAt)).toISOString(),
    ...semantic,
    claimBoundary:
      'This frame is a read-only diagnostic projection of verified partition-authority receipts. It grants no command, targeting, engagement, effector, emulator-input, process-launch, or weapons authority.',
  };
}

export function createPartitionDecisionFrame({
  authority,
  authorityTrustStore,
  observation,
  nodeTrustStore,
  decision,
  capturedAt,
}) {
  const verifiedAuthority = verifyPartitionAuthority(authority, authorityTrustStore);
  const verifiedObservation = verifyLinkObservation(observation, nodeTrustStore);
  requireCondition(
    isRecord(decision) && decision.schema === 'axm-partition-authority-decision/1',
    'partition decision schema is invalid',
  );
  requireCondition(decision.authorityId === verifiedAuthority.authorityId, 'decision authority does not match the frame authority');
  requireCondition(
    decision.baseDecision?.candidateVerified === true && decision.baseDecision?.authorityVerified === true,
    'partition frame requires verified candidate and authority receipts',
  );
  const profile = profileFor(verifiedAuthority, verifiedObservation);
  requireCondition(profile, 'signed observation does not map to an authority profile');
  requireCondition(profile.id === decision.profileId, 'decision profile does not match the signed observation');
  requireCondition(
    !profile.partition || decision.epochId,
    'partition decision is missing its runtime-owned epoch',
  );

  const lease = boundedLease(profile, decision);
  const semantic = {
    mode: 'candidate',
    authorityId: decision.authorityId,
    snapshotId: decision.snapshotId,
    candidateId: decision.candidateId,
    decisionId: decision.decisionId,
    profileId: profile.id,
    epochId: decision.epochId,
    epochStartedAt: decision.epochStartedAt,
    disposition: decision.disposition,
    reasonCode: decision.reason?.code ?? decision.baseDecision?.reasons?.[0]?.code ?? 'unknown',
    links: Object.fromEntries(Object.entries(verifiedObservation.links).sort(([a], [b]) => a.localeCompare(b))),
    localOperatorPresent: verifiedObservation.localOperatorPresent,
    lease,
    verification: {
      candidate: true,
      authority: true,
      linkObservation: true,
    },
    reconciliation: null,
    counts: {
      localDecisions: 1,
    },
    lamps: {
      connected: !profile.partition,
      partitioned: profile.partition,
      candidateEligible: decision.disposition === 'allow',
      hold: decision.disposition === 'hold',
      refused: decision.disposition === 'refuse',
      safeState: decision.disposition === 'safe_state',
      leaseWarning: lease.warning,
      leaseExpired: lease.expired,
      localOperatorPresent: verifiedObservation.localOperatorPresent,
      reconciliationPending: false,
      reconciliationComplete: false,
      humanRequired: false,
    },
  };
  return frameFromSemantic(semantic, capturedAt);
}

export function createPartitionReconciliationFrame({
  returningAuthority,
  authorityTrustStore,
  restoredObservation,
  nodeTrustStore,
  reconciliation,
  capturedAt,
}) {
  const verifiedAuthority = verifyPartitionAuthority(returningAuthority, authorityTrustStore);
  const verifiedObservation = verifyLinkObservation(restoredObservation, nodeTrustStore);
  requireCondition(
    isRecord(reconciliation) && reconciliation.schema === 'axm-partition-reconciliation/1',
    'reconciliation schema is invalid',
  );
  requireCondition(
    reconciliation.returningAuthorityId === verifiedAuthority.authorityId,
    'reconciliation returning authority does not match',
  );
  requireCondition(
    reconciliation.disposition === 'explicitly_superseded' || reconciliation.disposition === 'human_required',
    'reconciliation disposition is invalid',
  );
  const profile = profileFor(verifiedAuthority, verifiedObservation);
  requireCondition(profile && !profile.partition, 'reconciliation frame requires a signed connected profile');
  const localDecisionIds = Array.isArray(reconciliation.localDecisionIds)
    ? reconciliation.localDecisionIds.filter((value) => typeof value === 'string')
    : [];
  const semantic = {
    mode: 'reconciliation',
    authorityId: verifiedAuthority.authorityId,
    snapshotId: null,
    candidateId: null,
    decisionId: reconciliation.reconciliationId,
    profileId: profile.id,
    epochId: reconciliation.epochId,
    epochStartedAt: reconciliation.startedAt,
    disposition: reconciliation.disposition,
    reasonCode:
      reconciliation.disposition === 'explicitly_superseded'
        ? 'partition_explicitly_superseded'
        : 'partition_human_disposition_required',
    links: Object.fromEntries(Object.entries(verifiedObservation.links).sort(([a], [b]) => a.localeCompare(b))),
    localOperatorPresent: verifiedObservation.localOperatorPresent,
    lease: {
      partitioned: false,
      maxOfflineMs: 0,
      elapsedMs: Math.max(0, parseTime(reconciliation.endedAt, 'reconciliation endedAt') - parseTime(reconciliation.startedAt, 'reconciliation startedAt')),
      remainingMs: null,
      expired: false,
      warning: false,
    },
    verification: {
      candidate: null,
      authority: true,
      linkObservation: true,
    },
    reconciliation: {
      reconciliationId: reconciliation.reconciliationId,
      priorAuthorityId: reconciliation.priorAuthorityId,
      returningAuthorityId: reconciliation.returningAuthorityId,
      disposition: reconciliation.disposition,
      localDecisionIdsSha256: createHash('sha256')
        .update([...localDecisionIds].sort().join('\n'), 'utf8')
        .digest('hex'),
    },
    counts: {
      localDecisions: localDecisionIds.length,
    },
    lamps: {
      connected: true,
      partitioned: false,
      candidateEligible: false,
      hold: false,
      refused: false,
      safeState: false,
      leaseWarning: false,
      leaseExpired: false,
      localOperatorPresent: verifiedObservation.localOperatorPresent,
      reconciliationPending: reconciliation.disposition === 'human_required',
      reconciliationComplete: reconciliation.disposition === 'explicitly_superseded',
      humanRequired: reconciliation.disposition === 'human_required',
    },
  };
  return frameFromSemantic(semantic, capturedAt);
}
