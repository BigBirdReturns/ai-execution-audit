#!/usr/bin/env node
import {
  createHash,
  createPublicKey,
  verify as verifySignature,
} from 'node:crypto';
import {
  canonicalJson,
  deriveAuthorityId,
} from './authority_gate.mjs';
import {
  CheckpointVerificationError,
  verifyCheckpointCandidateTransaction,
} from '../checkpoint/checkpoint_verifier.mjs';

const MAX_CLOCK_SKEW_MS = 5_000;

class CheckpointGateError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'CheckpointGateError';
    this.code = code;
  }
}

function requireCondition(condition, code, message) {
  if (!condition) throw new CheckpointGateError(code, message);
}

function isRecord(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function digest(prefix, value) {
  return `${prefix}_${createHash('sha256').update(canonicalJson(value), 'utf8').digest('hex')}`;
}

function reason(code, message) {
  return { code, message };
}

function authorityIdentityBody(authority) {
  requireCondition(isRecord(authority), 'authority_invalid', 'authority must be an object');
  const { authorityId: _authorityId, signature: _signature, ...body } = authority;
  return body;
}

function signedAuthorityBody(authority) {
  return {
    ...authorityIdentityBody(authority),
    authorityId: authority.authorityId,
  };
}

function sortedUniqueStrings(value, code, label) {
  requireCondition(Array.isArray(value), code, `${label} must be an array`);
  const rows = value.map((row) => {
    requireCondition(typeof row === 'string' && row.trim(), code, `${label} entries must be non-empty strings`);
    return row.trim();
  });
  requireCondition(new Set(rows).size === rows.length, code, `${label} entries must be unique`);
  return [...rows].sort();
}

function verifyAuthority(authority, trustStore) {
  requireCondition(
    isRecord(authority) && authority.schema === 'axm-command-authority/1',
    'authority_schema_invalid',
    'authority schema is invalid',
  );
  requireCondition(
    authority.subject === 'polybolos-command-candidate',
    'authority_subject_invalid',
    'authority subject does not cover candidate evaluation',
  );
  requireCondition(
    authority.authorityId === deriveAuthorityId(authority),
    'authority_identity_invalid',
    'authority identity does not match its contents',
  );
  requireCondition(
    isRecord(authority.signature)
      && authority.signature.algorithm === 'Ed25519'
      && typeof authority.signature.value === 'string',
    'authority_signature_invalid',
    'authority signature metadata is invalid',
  );
  requireCondition(
    isRecord(trustStore)
      && trustStore.schema === 'axm-authority-trust/1'
      && Array.isArray(trustStore.keys),
    'trust_store_invalid',
    'authority trust store is invalid',
  );
  const key = trustStore.keys.find((row) =>
    isRecord(row)
    && row.keyId === authority.signature.keyId
    && row.issuer === authority.issuer
    && row.algorithm === 'Ed25519'
  );
  requireCondition(key && typeof key.publicKeyPem === 'string', 'authority_key_untrusted', 'authority signing key is not trusted');
  let verified = false;
  try {
    verified = verifySignature(
      null,
      Buffer.from(canonicalJson(signedAuthorityBody(authority)), 'utf8'),
      createPublicKey(key.publicKeyPem),
      Buffer.from(authority.signature.value, 'base64'),
    );
  } catch {
    verified = false;
  }
  requireCondition(verified, 'authority_signature_invalid', 'authority signature did not verify');
  return authority;
}

function payloadEvidenceReferences(payload) {
  const refs = [];
  if (typeof payload.entityId === 'string' && payload.entityId.trim()) {
    refs.push(payload.entityId.trim());
  }
  if (Array.isArray(payload.entityIds)) {
    for (const value of payload.entityIds) {
      requireCondition(
        typeof value === 'string' && value.trim(),
        'candidate_evidence_reference_invalid',
        'candidate payload entityIds must contain non-empty strings',
      );
      refs.push(value.trim());
    }
  }
  return [...new Set(refs)].sort();
}

function buildDecision({
  disposition,
  reasons,
  checkedAt,
  transaction,
  authority,
  verification,
  authorityVerified,
}) {
  const body = {
    disposition,
    reasons,
    checkedAt,
    candidateId: transaction?.candidate?.candidateId ?? null,
    checkpointId: transaction?.checkpoint?.checkpointId ?? null,
    authorityId: authority?.authorityId ?? null,
    candidateVerified: verification?.candidateVerified === true,
    checkpointVerified: verification?.checkpointVerified === true,
    authorityVerified,
    witnessCount: verification?.witnessCount ?? null,
    entityIds: verification?.entityIds ?? [],
  };
  return {
    schema: 'axm-checkpoint-candidate-authority-decision/1',
    decisionId: digest('checkpointauthoritydecision1', body),
    ...body,
    claimBoundary:
      'This receipt determines bounded candidate eligibility under one verified authority envelope. It carries no actuation surface and cannot itself execute, target, engage, command an effector, or release a weapon.',
  };
}

export function evaluateCheckpointCandidateAuthority(
  transaction,
  authority,
  trustStore,
  checkedAt,
) {
  const checkedAtMs = Date.parse(checkedAt);
  if (!Number.isFinite(checkedAtMs)) {
    return buildDecision({
      disposition: 'refuse',
      reasons: [reason('checked_at_invalid', 'authority evaluation time is invalid')],
      checkedAt,
      transaction,
      authority,
      verification: null,
      authorityVerified: false,
    });
  }
  const normalizedCheckedAt = new Date(checkedAtMs).toISOString();

  let verification;
  try {
    verification = verifyCheckpointCandidateTransaction(transaction);
  } catch (error) {
    const code = error instanceof CheckpointVerificationError
      ? error.code
      : 'checkpoint_transaction_invalid';
    return buildDecision({
      disposition: 'refuse',
      reasons: [reason(code, error instanceof Error ? error.message : 'checkpoint transaction is invalid')],
      checkedAt: normalizedCheckedAt,
      transaction,
      authority,
      verification: null,
      authorityVerified: false,
    });
  }

  let verifiedAuthority;
  try {
    verifiedAuthority = verifyAuthority(authority, trustStore);
  } catch (error) {
    const code = error instanceof CheckpointGateError ? error.code : 'authority_invalid';
    return buildDecision({
      disposition: 'refuse',
      reasons: [reason(code, error instanceof Error ? error.message : 'authority is invalid')],
      checkedAt: normalizedCheckedAt,
      transaction,
      authority,
      verification,
      authorityVerified: false,
    });
  }

  const candidate = transaction.candidate;
  const checkpoint = transaction.checkpoint;
  const notBeforeMs = Date.parse(verifiedAuthority.notBefore);
  const expiresAtMs = Date.parse(verifiedAuthority.expiresAt);
  if (!Number.isFinite(notBeforeMs) || !Number.isFinite(expiresAtMs) || expiresAtMs <= notBeforeMs) {
    return buildDecision({
      disposition: 'refuse',
      reasons: [reason('authority_window_invalid', 'authority validity window is invalid')],
      checkedAt: normalizedCheckedAt,
      transaction,
      authority: verifiedAuthority,
      verification,
      authorityVerified: true,
    });
  }
  if (checkedAtMs < notBeforeMs) {
    return buildDecision({
      disposition: 'hold',
      reasons: [reason('authority_not_yet_active', 'authority is not yet active')],
      checkedAt: normalizedCheckedAt,
      transaction,
      authority: verifiedAuthority,
      verification,
      authorityVerified: true,
    });
  }
  if (checkedAtMs > expiresAtMs) {
    return buildDecision({
      disposition: 'safe_state',
      reasons: [reason('authority_expired', 'authority has expired')],
      checkedAt: normalizedCheckedAt,
      transaction,
      authority: verifiedAuthority,
      verification,
      authorityVerified: true,
    });
  }

  const checkpointTime = Date.parse(checkpoint.observedAt);
  const candidateTime = Date.parse(candidate.createdAt);
  const maxObservationAgeMs = Number(
    verifiedAuthority.maxObservationAgeMs ?? verifiedAuthority.maxSnapshotAgeMs,
  );
  if (!Number.isInteger(maxObservationAgeMs) || maxObservationAgeMs < 0) {
    return buildDecision({
      disposition: 'refuse',
      reasons: [reason('authority_observation_age_invalid', 'authority observation-age bound is invalid')],
      checkedAt: normalizedCheckedAt,
      transaction,
      authority: verifiedAuthority,
      verification,
      authorityVerified: true,
    });
  }
  if (checkpointTime > checkedAtMs + MAX_CLOCK_SKEW_MS) {
    return buildDecision({
      disposition: 'hold',
      reasons: [reason('checkpoint_from_future', 'checkpoint time exceeds permitted clock skew')],
      checkedAt: normalizedCheckedAt,
      transaction,
      authority: verifiedAuthority,
      verification,
      authorityVerified: true,
    });
  }
  if (checkedAtMs - checkpointTime > maxObservationAgeMs) {
    return buildDecision({
      disposition: 'hold',
      reasons: [reason('checkpoint_too_old', 'checkpoint exceeds the authority freshness bound')],
      checkedAt: normalizedCheckedAt,
      transaction,
      authority: verifiedAuthority,
      verification,
      authorityVerified: true,
    });
  }
  if (candidateTime > checkedAtMs + MAX_CLOCK_SKEW_MS) {
    return buildDecision({
      disposition: 'hold',
      reasons: [reason('candidate_from_future', 'candidate time exceeds permitted clock skew')],
      checkedAt: normalizedCheckedAt,
      transaction,
      authority: verifiedAuthority,
      verification,
      authorityVerified: true,
    });
  }

  let allowedProducers;
  let allowedActionClasses;
  let allowedSoftwareRecordIds;
  let requiredPayloadFields;
  let allowedPayloadFields;
  try {
    allowedProducers = sortedUniqueStrings(
      verifiedAuthority.allowedProducers,
      'authority_producers_invalid',
      'allowedProducers',
    );
    allowedActionClasses = sortedUniqueStrings(
      verifiedAuthority.allowedActionClasses,
      'authority_actions_invalid',
      'allowedActionClasses',
    );
    allowedSoftwareRecordIds = sortedUniqueStrings(
      verifiedAuthority.allowedSoftwareRecordIds,
      'authority_software_invalid',
      'allowedSoftwareRecordIds',
    );
    requiredPayloadFields = sortedUniqueStrings(
      verifiedAuthority.requiredPayloadFields ?? [],
      'authority_payload_invalid',
      'requiredPayloadFields',
    );
    allowedPayloadFields = sortedUniqueStrings(
      verifiedAuthority.allowedPayloadFields ?? [],
      'authority_payload_invalid',
      'allowedPayloadFields',
    );
  } catch (error) {
    return buildDecision({
      disposition: 'refuse',
      reasons: [reason(error.code ?? 'authority_constraints_invalid', error.message)],
      checkedAt: normalizedCheckedAt,
      transaction,
      authority: verifiedAuthority,
      verification,
      authorityVerified: true,
    });
  }

  if (!allowedProducers.includes(candidate.producer)) {
    return buildDecision({
      disposition: 'refuse',
      reasons: [reason('candidate_producer_not_authorized', 'candidate producer is outside the authority envelope')],
      checkedAt: normalizedCheckedAt,
      transaction,
      authority: verifiedAuthority,
      verification,
      authorityVerified: true,
    });
  }
  if (!allowedActionClasses.includes(candidate.actionClass)) {
    return buildDecision({
      disposition: 'refuse',
      reasons: [reason('candidate_action_not_authorized', 'candidate action class is outside the authority envelope')],
      checkedAt: normalizedCheckedAt,
      transaction,
      authority: verifiedAuthority,
      verification,
      authorityVerified: true,
    });
  }
  if (!allowedSoftwareRecordIds.includes(checkpoint.softwareRecordId)) {
    return buildDecision({
      disposition: 'refuse',
      reasons: [reason('checkpoint_software_not_authorized', 'checkpoint software identity is outside the authority envelope')],
      checkedAt: normalizedCheckedAt,
      transaction,
      authority: verifiedAuthority,
      verification,
      authorityVerified: true,
    });
  }

  const maxEvidenceWitnesses = Number(verifiedAuthority.maxEvidenceWitnesses ?? 16);
  if (!Number.isInteger(maxEvidenceWitnesses) || maxEvidenceWitnesses < 1 || maxEvidenceWitnesses > 16) {
    return buildDecision({
      disposition: 'refuse',
      reasons: [reason('authority_evidence_bound_invalid', 'authority evidence-witness bound is invalid')],
      checkedAt: normalizedCheckedAt,
      transaction,
      authority: verifiedAuthority,
      verification,
      authorityVerified: true,
    });
  }
  if (verification.witnessCount > maxEvidenceWitnesses) {
    return buildDecision({
      disposition: 'refuse',
      reasons: [reason('candidate_evidence_exceeds_authority', 'candidate cites more evidence witnesses than authority permits')],
      checkedAt: normalizedCheckedAt,
      transaction,
      authority: verifiedAuthority,
      verification,
      authorityVerified: true,
    });
  }

  const maxObservedEntities = Number(
    verifiedAuthority.maxObservedEntities ?? Number.MAX_SAFE_INTEGER,
  );
  if (!Number.isSafeInteger(maxObservedEntities) || maxObservedEntities < 1) {
    return buildDecision({
      disposition: 'refuse',
      reasons: [reason('authority_observed_entities_invalid', 'authority observed-entity bound is invalid')],
      checkedAt: normalizedCheckedAt,
      transaction,
      authority: verifiedAuthority,
      verification,
      authorityVerified: true,
    });
  }
  if (checkpoint.entityCount > maxObservedEntities) {
    return buildDecision({
      disposition: 'refuse',
      reasons: [reason('checkpoint_entity_count_exceeds_authority', 'checkpoint entity count exceeds the authority envelope')],
      checkedAt: normalizedCheckedAt,
      transaction,
      authority: verifiedAuthority,
      verification,
      authorityVerified: true,
    });
  }

  const payloadKeys = Object.keys(candidate.payload).sort();
  for (const field of requiredPayloadFields) {
    if (!Object.prototype.hasOwnProperty.call(candidate.payload, field)) {
      return buildDecision({
        disposition: 'refuse',
        reasons: [reason('candidate_payload_required_field_missing', `candidate payload is missing required field ${field}`)],
        checkedAt: normalizedCheckedAt,
        transaction,
        authority: verifiedAuthority,
        verification,
        authorityVerified: true,
      });
    }
  }
  if (allowedPayloadFields.length > 0) {
    const unexpected = payloadKeys.filter((field) => !allowedPayloadFields.includes(field));
    if (unexpected.length > 0) {
      return buildDecision({
        disposition: 'refuse',
        reasons: [reason('candidate_payload_field_not_authorized', `candidate payload field is not authorized: ${unexpected[0]}`)],
        checkedAt: normalizedCheckedAt,
        transaction,
        authority: verifiedAuthority,
        verification,
        authorityVerified: true,
      });
    }
  }
  const maxPayloadBytes = Number(verifiedAuthority.maxPayloadBytes);
  if (!Number.isInteger(maxPayloadBytes) || maxPayloadBytes < 2) {
    return buildDecision({
      disposition: 'refuse',
      reasons: [reason('authority_payload_size_invalid', 'authority payload size bound is invalid')],
      checkedAt: normalizedCheckedAt,
      transaction,
      authority: verifiedAuthority,
      verification,
      authorityVerified: true,
    });
  }
  const payloadBytes = Buffer.byteLength(canonicalJson(candidate.payload), 'utf8');
  if (payloadBytes > maxPayloadBytes) {
    return buildDecision({
      disposition: 'refuse',
      reasons: [reason('candidate_payload_too_large', 'candidate payload exceeds the authority envelope')],
      checkedAt: normalizedCheckedAt,
      transaction,
      authority: verifiedAuthority,
      verification,
      authorityVerified: true,
    });
  }

  const evidenceSet = new Set(verification.entityIds);
  let payloadRefs;
  try {
    payloadRefs = payloadEvidenceReferences(candidate.payload);
  } catch (error) {
    return buildDecision({
      disposition: 'refuse',
      reasons: [reason(error.code ?? 'candidate_evidence_reference_invalid', error.message)],
      checkedAt: normalizedCheckedAt,
      transaction,
      authority: verifiedAuthority,
      verification,
      authorityVerified: true,
    });
  }
  if (payloadRefs.length === 0) {
    return buildDecision({
      disposition: 'refuse',
      reasons: [reason('candidate_evidence_reference_missing', 'candidate payload does not identify the observation evidence it uses')],
      checkedAt: normalizedCheckedAt,
      transaction,
      authority: verifiedAuthority,
      verification,
      authorityVerified: true,
    });
  }
  const missingEvidence = payloadRefs.find((entityId) => !evidenceSet.has(entityId));
  if (missingEvidence) {
    return buildDecision({
      disposition: 'refuse',
      reasons: [reason('candidate_evidence_reference_unproven', `candidate payload cites an entity without a valid witness: ${missingEvidence}`)],
      checkedAt: normalizedCheckedAt,
      transaction,
      authority: verifiedAuthority,
      verification,
      authorityVerified: true,
    });
  }

  return buildDecision({
    disposition: 'allow',
    reasons: [reason('candidate_inside_verified_checkpoint_authority', 'candidate, checkpoint, witnesses, software identity, and authority envelope verified')],
    checkedAt: normalizedCheckedAt,
    transaction,
    authority: verifiedAuthority,
    verification,
    authorityVerified: true,
  });
}
