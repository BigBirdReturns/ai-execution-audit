#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

const MAX_WITNESSES = 16;
const MAX_WITNESS_DEPTH = 64;
const MAX_PAYLOAD_DEPTH = 8;
const MAX_PAYLOAD_NODES = 4_096;
const RESERVED_AUTHORITY_KEYS = new Set([
  'authorized', 'isauthorized', 'authorization', 'authority', 'authoritygranted',
  'approved', 'isapproved', 'approval', 'allow', 'allowed', 'execute',
  'executionauthorized', 'executionapproved', 'engagementauthorized',
  'engagementapproved', 'commandauthority', 'releaseauthority', 'weaponsrelease',
  'weaponsreleaseauthorized', 'effectorcommand', 'actuationauthorized',
]);

export class CheckpointVerificationError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'CheckpointVerificationError';
    this.code = code;
  }
}

function requireCondition(condition, code, message) {
  if (!condition) throw new CheckpointVerificationError(code, message);
}

function isRecord(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

export function canonicalJson(value) {
  if (value === null) return 'null';
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`;
  if (typeof value === 'object') {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
      .join(',')}}`;
  }
  if (typeof value === 'number') {
    requireCondition(Number.isFinite(value), 'non_json_number', 'non-finite numbers are not admissible');
  }
  const encoded = JSON.stringify(value);
  requireCondition(encoded !== undefined, 'non_json_value', 'non-JSON values are not admissible');
  return encoded;
}

function hashText(value) {
  return createHash('sha256').update(value, 'utf8').digest('hex');
}

function digest(prefix, value) {
  return `${prefix}_${hashText(canonicalJson(value))}`;
}

function normalizedKey(key) {
  return key.replace(/[^a-z0-9]/gi, '').toLowerCase();
}

function assertNoAuthorityFields(value, path = '$', depth = 0, counter = { nodes: 0 }) {
  counter.nodes += 1;
  requireCondition(counter.nodes <= MAX_PAYLOAD_NODES, 'candidate_payload_bounds', 'candidate payload exceeds bounded value count');
  requireCondition(depth <= MAX_PAYLOAD_DEPTH, 'candidate_payload_bounds', 'candidate payload exceeds bounded depth');
  if (value === null || typeof value === 'string' || typeof value === 'boolean') return;
  if (typeof value === 'number') {
    requireCondition(Number.isFinite(value), 'candidate_payload_non_json', `non-finite number at ${path}`);
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((item, index) => assertNoAuthorityFields(item, `${path}[${index}]`, depth + 1, counter));
    return;
  }
  requireCondition(isRecord(value), 'candidate_payload_non_json', `non-JSON value at ${path}`);
  for (const [key, nested] of Object.entries(value)) {
    requireCondition(
      !RESERVED_AUTHORITY_KEYS.has(normalizedKey(key)),
      'candidate_payload_authority_field',
      `candidate payload carries reserved authority field ${key} at ${path}`,
    );
    assertNoAuthorityFields(nested, `${path}.${key}`, depth + 1, counter);
  }
}

function entityLeafHash(entity) {
  return hashText(`polybolos-ci-entity-leaf-v1\0${canonicalJson(entity)}`);
}

function entityNodeHash(left, right) {
  return hashText(`polybolos-ci-entity-node-v1\0${left}\0${right}`);
}

export function deriveCheckpointId(checkpoint) {
  requireCondition(isRecord(checkpoint), 'checkpoint_invalid', 'checkpoint must be an object');
  const { checkpointId: _checkpointId, claimBoundary: _claimBoundary, ...body } = checkpoint;
  return digest('checkpoint1', body);
}

export function deriveWitnessId(witness) {
  requireCondition(isRecord(witness), 'witness_invalid', 'witness must be an object');
  const { witnessId: _witnessId, claimBoundary: _claimBoundary, ...body } = witness;
  return digest('entitywitness1', body);
}

export function deriveCandidateId(candidate) {
  requireCondition(isRecord(candidate), 'candidate_invalid', 'candidate must be an object');
  const { candidateId: _candidateId, claimBoundary: _claimBoundary, ...body } = candidate;
  return digest('candidate2', body);
}

export function verifyEntityWitness(checkpoint, witness) {
  requireCondition(
    isRecord(checkpoint) && checkpoint.schema === 'polybolos-command-intelligence-checkpoint/1',
    'checkpoint_schema_invalid',
    'checkpoint schema is invalid',
  );
  requireCondition(checkpoint.checkpointId === deriveCheckpointId(checkpoint), 'checkpoint_identity_invalid', 'checkpoint identity does not match its contents');
  requireCondition(
    isRecord(witness) && witness.schema === 'polybolos-command-intelligence-entity-witness/1',
    'witness_schema_invalid',
    'entity witness schema is invalid',
  );
  requireCondition(witness.witnessId === deriveWitnessId(witness), 'witness_identity_invalid', 'witness identity does not match its contents');
  requireCondition(witness.checkpointId === checkpoint.checkpointId, 'witness_checkpoint_mismatch', 'witness cites another checkpoint');
  requireCondition(isRecord(witness.entity), 'witness_entity_invalid', 'witness entity is invalid');
  requireCondition(witness.entityId === witness.entity.id, 'witness_entity_mismatch', 'witness entity identity differs from its payload');
  requireCondition(witness.entityCount === checkpoint.entityCount, 'witness_count_mismatch', 'witness entity count differs from checkpoint');
  requireCondition(Number.isInteger(witness.entityIndex) && witness.entityIndex >= 0 && witness.entityIndex < witness.entityCount, 'witness_index_invalid', 'witness entity index is invalid');
  requireCondition(Array.isArray(witness.siblings) && witness.siblings.length <= MAX_WITNESS_DEPTH, 'witness_path_invalid', 'witness path is invalid');
  let current = entityLeafHash(witness.entity);
  requireCondition(current === witness.leafHash, 'witness_leaf_invalid', 'witness leaf hash is invalid');
  for (const sibling of witness.siblings) {
    requireCondition(isRecord(sibling) && /^[0-9a-f]{64}$/.test(sibling.hash), 'witness_path_invalid', 'witness sibling hash is invalid');
    if (sibling.side === 'left') current = entityNodeHash(sibling.hash, current);
    else if (sibling.side === 'right') current = entityNodeHash(current, sibling.hash);
    else throw new CheckpointVerificationError('witness_path_invalid', 'witness sibling side is invalid');
  }
  requireCondition(current === checkpoint.entityRoot, 'witness_root_invalid', 'witness does not reconstruct the checkpoint entity root');
  return witness.entity;
}

function normalizedEvidence(witnesses) {
  const entityIds = new Set();
  const witnessIds = new Set();
  const rows = witnesses.map((witness) => {
    requireCondition(!entityIds.has(witness.entityId), 'witness_duplicate_entity', 'candidate transaction duplicates an entity witness');
    requireCondition(!witnessIds.has(witness.witnessId), 'witness_duplicate_identity', 'candidate transaction duplicates a witness identity');
    entityIds.add(witness.entityId);
    witnessIds.add(witness.witnessId);
    return { entityId: witness.entityId, witnessId: witness.witnessId };
  });
  return rows.sort((a, b) => a.entityId.localeCompare(b.entityId));
}

export function verifyCheckpointCandidateTransaction(transaction) {
  requireCondition(
    isRecord(transaction) && transaction.schema === 'polybolos-command-candidate-transaction/2',
    'transaction_schema_invalid',
    'bounded candidate transaction schema is invalid',
  );
  const checkpoint = transaction.checkpoint;
  requireCondition(
    isRecord(checkpoint) && checkpoint.schema === 'polybolos-command-intelligence-checkpoint/1',
    'checkpoint_schema_invalid',
    'checkpoint schema is invalid',
  );
  requireCondition(checkpoint.checkpointId === deriveCheckpointId(checkpoint), 'checkpoint_identity_invalid', 'checkpoint identity does not match its contents');
  requireCondition(Number.isInteger(checkpoint.sequence) && checkpoint.sequence >= 0, 'checkpoint_sequence_invalid', 'checkpoint sequence is invalid');
  requireCondition(Number.isInteger(checkpoint.entityCount) && checkpoint.entityCount >= 1, 'checkpoint_count_invalid', 'checkpoint entity count is invalid');
  requireCondition(Number.isFinite(Date.parse(checkpoint.observedAt)), 'checkpoint_time_invalid', 'checkpoint observedAt is invalid');
  requireCondition(checkpoint.hashAlgorithm === 'sha256', 'checkpoint_hash_invalid', 'checkpoint hash algorithm is unsupported');
  requireCondition(checkpoint.treeAlgorithm === 'sorted-entity-id-pair-duplicate-last-v1', 'checkpoint_tree_invalid', 'checkpoint tree algorithm is unsupported');

  const witnesses = transaction.witnesses;
  requireCondition(Array.isArray(witnesses) && witnesses.length >= 1 && witnesses.length <= MAX_WITNESSES, 'witness_count_invalid', 'transaction witness count is invalid');
  const entities = new Map();
  for (const witness of witnesses) {
    const entity = verifyEntityWitness(checkpoint, witness);
    entities.set(entity.id, entity);
  }

  const candidate = transaction.candidate;
  requireCondition(
    isRecord(candidate) && candidate.schema === 'polybolos-command-candidate/2',
    'candidate_schema_invalid',
    'bounded candidate schema is invalid',
  );
  requireCondition(candidate.checkpointId === checkpoint.checkpointId, 'candidate_checkpoint_mismatch', 'candidate cites another checkpoint');
  assertNoAuthorityFields(candidate.payload);
  requireCondition(candidate.candidateId === deriveCandidateId(candidate), 'candidate_binding_invalid', 'candidate identity does not match its binding');
  const expectedEvidence = normalizedEvidence(witnesses);
  requireCondition(canonicalJson(candidate.evidence) === canonicalJson(expectedEvidence), 'candidate_evidence_mismatch', 'candidate evidence does not match supplied witnesses');
  const candidateTime = Date.parse(candidate.createdAt);
  const checkpointTime = Date.parse(checkpoint.observedAt);
  requireCondition(Number.isFinite(candidateTime), 'candidate_time_invalid', 'candidate createdAt is invalid');
  requireCondition(candidateTime >= checkpointTime, 'candidate_predates_checkpoint', 'candidate predates its checkpoint');

  return {
    schema: 'axm-checkpoint-candidate-verification/1',
    checkpointId: checkpoint.checkpointId,
    candidateId: candidate.candidateId,
    checkpointTime,
    candidateTime,
    entityIds: [...entities.keys()].sort(),
    witnessCount: witnesses.length,
    candidateVerified: true,
    checkpointVerified: true,
    claimBoundary:
      'This receipt verifies a bounded Command Intelligence checkpoint, entity witnesses, and candidate binding. It carries no command, targeting, engagement, effector, or execution authority.',
  };
}

async function main(argv) {
  if (argv.length < 1 || argv.length > 2) {
    console.error('usage: checkpoint_verifier.mjs <transaction.json> [receipt.json]');
    return 2;
  }
  const transaction = JSON.parse(await readFile(argv[0], 'utf8'));
  try {
    const receipt = verifyCheckpointCandidateTransaction(transaction);
    if (argv[1]) await writeFile(argv[1], `${JSON.stringify(receipt, null, 2)}\n`, 'utf8');
    process.stdout.write(`${JSON.stringify(receipt, null, 2)}\n`);
    return 0;
  } catch (error) {
    const receipt = {
      schema: 'axm-checkpoint-candidate-verification/1',
      candidateVerified: false,
      checkpointVerified: false,
      error: error instanceof CheckpointVerificationError ? error.code : 'transaction_invalid',
      message: error instanceof Error ? error.message : 'transaction verification failed',
    };
    if (argv[1]) await writeFile(argv[1], `${JSON.stringify(receipt, null, 2)}\n`, 'utf8');
    process.stderr.write(`${JSON.stringify(receipt, null, 2)}\n`);
    return 1;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exitCode = await main(process.argv.slice(2));
}
