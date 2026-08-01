import { createHash } from 'node:crypto';
import {
  canonicalCheckpointJson,
  deriveCheckpointId,
  verifyEntityWitness,
  type CommandIntelligenceCheckpoint,
  type CommandIntelligenceEntityWitness,
} from './checkpoint';
import { assertCandidatePayload } from './candidate';

export interface CheckpointCandidateEvidenceRef {
  entityId: string;
  witnessId: string;
}

export interface CheckpointCommandCandidateInput {
  producer: string;
  createdAt: string;
  actionClass: string;
  payload: Record<string, unknown>;
}

export interface CheckpointCommandCandidateReceipt {
  schema: 'polybolos-command-candidate/2';
  candidateId: string;
  checkpointId: string;
  evidence: CheckpointCandidateEvidenceRef[];
  producer: string;
  createdAt: string;
  actionClass: string;
  payload: Record<string, unknown>;
  claimBoundary: string;
}

export interface CheckpointCommandCandidateTransaction {
  schema: 'polybolos-command-candidate-transaction/2';
  checkpoint: CommandIntelligenceCheckpoint;
  witnesses: CommandIntelligenceEntityWitness[];
  candidate: CheckpointCommandCandidateReceipt;
  persistence: string;
  claimBoundary: string;
}

function digest(prefix: string, value: unknown): string {
  return `${prefix}_${createHash('sha256')
    .update(canonicalCheckpointJson(value), 'utf8')
    .digest('hex')}`;
}

function normalizedEvidence(
  witnesses: CommandIntelligenceEntityWitness[],
): CheckpointCandidateEvidenceRef[] {
  const seenEntities = new Set<string>();
  const seenWitnesses = new Set<string>();
  const evidence = witnesses.map((witness) => {
    if (seenEntities.has(witness.entityId)) {
      throw new Error(`candidate cites duplicate entity witness ${witness.entityId}`);
    }
    if (seenWitnesses.has(witness.witnessId)) {
      throw new Error(`candidate cites duplicate witness identity ${witness.witnessId}`);
    }
    seenEntities.add(witness.entityId);
    seenWitnesses.add(witness.witnessId);
    return { entityId: witness.entityId, witnessId: witness.witnessId };
  });
  return evidence.sort((a, b) => a.entityId.localeCompare(b.entityId));
}

export function deriveCheckpointCandidateId(
  candidate: CheckpointCommandCandidateReceipt,
): string {
  const { candidateId: _candidateId, claimBoundary: _claimBoundary, ...body } = candidate;
  return digest('candidate2', body);
}

export function createCheckpointCommandCandidate(
  checkpoint: CommandIntelligenceCheckpoint,
  witnesses: CommandIntelligenceEntityWitness[],
  input: CheckpointCommandCandidateInput,
): CheckpointCommandCandidateReceipt {
  if (checkpoint.schema !== 'polybolos-command-intelligence-checkpoint/1') {
    throw new Error('candidate checkpoint schema is invalid');
  }
  if (checkpoint.checkpointId !== deriveCheckpointId(checkpoint)) {
    throw new Error('candidate checkpoint identity is invalid');
  }
  if (!Array.isArray(witnesses) || witnesses.length < 1 || witnesses.length > 16) {
    throw new Error('candidate must cite between 1 and 16 entity witnesses');
  }
  for (const witness of witnesses) {
    if (!verifyEntityWitness(checkpoint, witness)) {
      throw new Error(`candidate entity witness is invalid: ${witness?.entityId ?? 'unknown'}`);
    }
  }

  const createdAtMs = Date.parse(input.createdAt);
  const observedAtMs = Date.parse(checkpoint.observedAt);
  if (!Number.isFinite(createdAtMs)) throw new Error('candidate createdAt must be a valid date-time');
  if (!Number.isFinite(observedAtMs)) throw new Error('checkpoint observedAt must be a valid date-time');
  if (createdAtMs < observedAtMs) {
    throw new Error('candidate cannot predate the Command Intelligence checkpoint it cites');
  }
  const producer = input.producer.trim();
  const actionClass = input.actionClass.trim();
  if (!producer || producer.length > 128) throw new Error('candidate producer is required and bounded');
  if (!actionClass || actionClass.length > 128) throw new Error('candidate actionClass is required and bounded');
  assertCandidatePayload(input.payload);

  const body = {
    schema: 'polybolos-command-candidate/2' as const,
    checkpointId: checkpoint.checkpointId,
    evidence: normalizedEvidence(witnesses),
    producer,
    createdAt: new Date(createdAtMs).toISOString(),
    actionClass,
    payload: input.payload,
  };
  return {
    ...body,
    candidateId: digest('candidate2', body),
    claimBoundary:
      'This record binds a candidate action to one bounded Command Intelligence checkpoint and its cited entity witnesses. It carries no command authority and cannot authorize execution.',
  };
}

export function verifyCheckpointCommandCandidateBinding(
  transaction: CheckpointCommandCandidateTransaction,
): boolean {
  try {
    if (transaction.schema !== 'polybolos-command-candidate-transaction/2') return false;
    const { checkpoint, witnesses, candidate } = transaction;
    if (checkpoint.checkpointId !== deriveCheckpointId(checkpoint)) return false;
    if (!Array.isArray(witnesses) || witnesses.length < 1 || witnesses.length > 16) return false;
    if (!witnesses.every((witness) => verifyEntityWitness(checkpoint, witness))) return false;
    if (candidate.schema !== 'polybolos-command-candidate/2') return false;
    if (candidate.checkpointId !== checkpoint.checkpointId) return false;
    if (candidate.candidateId !== deriveCheckpointCandidateId(candidate)) return false;
    const expectedEvidence = normalizedEvidence(witnesses);
    if (canonicalCheckpointJson(candidate.evidence) !== canonicalCheckpointJson(expectedEvidence)) {
      return false;
    }
    const rebuilt = createCheckpointCommandCandidate(checkpoint, witnesses, {
      producer: candidate.producer,
      createdAt: candidate.createdAt,
      actionClass: candidate.actionClass,
      payload: candidate.payload,
    });
    return rebuilt.candidateId === candidate.candidateId;
  } catch {
    return false;
  }
}
