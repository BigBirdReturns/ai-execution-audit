import { createHash } from 'node:crypto';
import { canonicalJson } from './authority_gate.mjs';
import { evaluateCheckpointCandidateAuthority } from './checkpoint_authority_gate.mjs';
import {
  PartitionAuthorityRuntime,
  verifyPartitionAuthority,
} from './partition_runtime.mjs';

const MAX_CLOCK_SKEW_MS = 5_000;

function digest(prefix, value) {
  return `${prefix}_${createHash('sha256').update(canonicalJson(value), 'utf8').digest('hex')}`;
}

function parseTime(value, label) {
  const milliseconds = Date.parse(value);
  if (!Number.isFinite(milliseconds)) throw new Error(`${label} is not a valid date-time`);
  return milliseconds;
}

function iso(milliseconds) {
  return new Date(milliseconds).toISOString();
}

export class CheckpointPartitionAuthorityRuntime extends PartitionAuthorityRuntime {
  evaluateCheckpoint(transaction, authority) {
    const nowMs = this.clock();
    const checkedAt = iso(nowMs);
    const verifiedAuthority = verifyPartitionAuthority(authority, this.authorityTrustStore);
    const baseDecision = evaluateCheckpointCandidateAuthority(
      transaction,
      verifiedAuthority,
      this.authorityTrustStore,
      checkedAt,
    );
    let disposition = baseDecision.disposition;
    let code = baseDecision.reasons[0]?.code ?? 'base_checkpoint_authority_refused';
    let message = baseDecision.reasons[0]?.message ?? 'base checkpoint authority gate refused candidate';
    let profile = null;
    let elapsedMs = null;

    if (disposition === 'allow') {
      if (!this.state.lastObservation || !this.state.currentProfileId) {
        disposition = 'safe_state';
        code = 'partition_topology_unknown';
        message = 'no signed current topology is available';
      } else if (this.state.currentAuthorityId !== verifiedAuthority.authorityId) {
        disposition = 'refuse';
        code = 'partition_authority_mismatch';
        message = 'runtime topology was admitted under another authority';
      } else {
        profile = verifiedAuthority.partitionPolicy.profiles.find(
          (row) => row.id === this.state.currentProfileId,
        ) ?? null;
        if (!profile) {
          disposition = 'safe_state';
          code = 'partition_profile_unknown';
          message = 'signed topology does not map to an admitted profile';
        } else if (!profile.allowedActionClasses.includes(transaction.candidate.actionClass)) {
          disposition = 'refuse';
          code = 'partition_action_not_surviving';
          message = 'candidate action class does not survive the current communications profile';
        } else if (profile.requiresLocalOperator && !this.state.lastObservation.localOperatorPresent) {
          disposition = 'safe_state';
          code = 'partition_local_operator_absent';
          message = 'current partition profile requires a local operator';
        } else if (profile.partition) {
          if (!this.state.activeEpoch) {
            disposition = 'safe_state';
            code = 'partition_epoch_missing';
            message = 'partition profile has no runtime-owned epoch';
          } else {
            const startedAtMs = parseTime(this.state.activeEpoch.startedAt, 'partition epoch startedAt');
            elapsedMs = Math.max(0, nowMs - startedAtMs);
            if (nowMs + MAX_CLOCK_SKEW_MS < startedAtMs) {
              disposition = 'hold';
              code = 'partition_clock_regression';
              message = 'runtime clock is earlier than the persisted partition epoch';
            } else if (elapsedMs > profile.maxOfflineMs) {
              disposition = profile.expiryDisposition;
              code = 'partition_offline_lease_expired';
              message = 'runtime-owned offline lease has expired';
            }
          }
        }
      }
    }

    const body = {
      baseDecisionId: baseDecision.decisionId,
      candidateId: transaction?.candidate?.candidateId ?? null,
      checkpointId: transaction?.checkpoint?.checkpointId ?? null,
      authorityId: verifiedAuthority.authorityId,
      checkedAt,
      profileId: profile?.id ?? this.state.currentProfileId,
      epochId: this.state.activeEpoch?.epochId ?? null,
      epochStartedAt: this.state.activeEpoch?.startedAt ?? null,
      elapsedMs,
      disposition,
      reason: { code, message },
    };
    const decision = {
      schema: 'axm-checkpoint-partition-authority-decision/1',
      decisionId: digest('checkpointpartitiondecision1', body),
      ...body,
      baseDecision,
      claimBoundary:
        'This receipt applies signed communications-state constraints to a checkpoint-bound candidate. It has no actuation surface and cannot itself execute, target, engage, command an effector, or release a weapon.',
    };

    this.commit(
      {
        type: 'checkpoint_candidate_evaluated',
        at: checkedAt,
        decisionId: decision.decisionId,
        checkpointId: decision.checkpointId,
        disposition,
        reasonCode: code,
      },
      (state) => {
        state.decisionIds.push(decision.decisionId);
        if (state.decisionIds.length > 20_000) {
          state.decisionIds.splice(0, state.decisionIds.length - 20_000);
        }
        if (state.activeEpoch) state.activeEpoch.decisionIds.push(decision.decisionId);
      },
    );
    return decision;
  }
}
