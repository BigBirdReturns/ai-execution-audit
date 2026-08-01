#!/usr/bin/env node
import { createHash, createPublicKey, verify as verifySignature } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

const RESERVED_AUTHORITY_KEYS = new Set([
  'authorized',
  'isauthorized',
  'authorization',
  'authority',
  'authoritygranted',
  'approved',
  'isapproved',
  'approval',
  'allow',
  'allowed',
  'execute',
  'executionauthorized',
  'executionapproved',
  'engagementauthorized',
  'engagementapproved',
  'commandauthority',
  'releaseauthority',
  'weaponsrelease',
  'weaponsreleaseauthorized',
  'effectorcommand',
  'actuationauthorized',
]);

const MAX_PAYLOAD_DEPTH = 8;
const MAX_PAYLOAD_NODES = 4_096;
const MAX_CLOCK_SKEW_MS = 5_000;

class GateError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'GateError';
    this.code = code;
  }
}

function requireCondition(condition, code, message) {
  if (!condition) throw new GateError(code, message);
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
    if (!Number.isFinite(value)) throw new GateError('non_json_number', 'non-finite numbers are not admissible');
  }
  const encoded = JSON.stringify(value);
  if (encoded === undefined) throw new GateError('non_json_value', 'non-JSON values are not admissible');
  return encoded;
}

function digest(prefix, value) {
  return `${prefix}_${createHash('sha256').update(canonicalJson(value), 'utf8').digest('hex')}`;
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

export function deriveSnapshotId(snapshot) {
  requireCondition(isRecord(snapshot), 'snapshot_invalid', 'snapshot must be an object');
  return digest('ci1', {
    sequence: snapshot.sequence,
    observedAt: snapshot.observedAt,
    feeds: snapshot.feeds,
    entities: snapshot.entities,
  });
}

export function deriveCandidateId(candidate) {
  requireCondition(isRecord(candidate), 'candidate_invalid', 'candidate must be an object');
  const createdAtMs = Date.parse(candidate.createdAt);
  requireCondition(Number.isFinite(createdAtMs), 'candidate_time_invalid', 'candidate createdAt is invalid');
  return digest('candidate1', {
    snapshotId: candidate.snapshotId,
    producer: candidate.producer,
    createdAt: new Date(createdAtMs).toISOString(),
    actionClass: candidate.actionClass,
    payload: candidate.payload,
  });
}

function authorityIdentityBody(authority) {
  requireCondition(isRecord(authority), 'authority_invalid', 'authority must be an object');
  const { authorityId: _authorityId, signature: _signature, ...body } = authority;
  return body;
}

export function deriveAuthorityId(authority) {
  return digest('authority1', authorityIdentityBody(authority));
}

function signedAuthorityBody(authority) {
  return {
    ...authorityIdentityBody(authority),
    authorityId: authority.authorityId,
  };
}

function verifyTransaction(transaction) {
  requireCondition(
    isRecord(transaction) && transaction.schema === 'polybolos-command-candidate-transaction/1',
    'transaction_schema_invalid',
    'candidate transaction schema is invalid',
  );
  const snapshot = transaction.snapshot;
  const candidate = transaction.candidate;
  requireCondition(
    isRecord(snapshot) && snapshot.schema === 'polybolos-command-intelligence-snapshot/1',
    'snapshot_schema_invalid',
    'snapshot schema is invalid',
  );
  requireCondition(
    snapshot.snapshotId === deriveSnapshotId(snapshot),
    'snapshot_identity_invalid',
    'snapshot identity does not match its contents',
  );
  requireCondition(
    isRecord(candidate) && candidate.schema === 'polybolos-command-candidate/1',
    'candidate_schema_invalid',
    'candidate schema is invalid',
  );
  requireCondition(
    candidate.snapshotId === snapshot.snapshotId,
    'candidate_snapshot_mismatch',
    'candidate cites a different snapshot',
  );
  assertNoAuthorityFields(candidate.payload);
  requireCondition(
    candidate.candidateId === deriveCandidateId(candidate),
    'candidate_binding_invalid',
    'candidate identity does not match its binding',
  );
  const candidateTime = Date.parse(candidate.createdAt);
  const snapshotTime = Date.parse(snapshot.observedAt);
  requireCondition(Number.isFinite(snapshotTime), 'snapshot_time_invalid', 'snapshot observedAt is invalid');
  requireCondition(candidateTime >= snapshotTime, 'candidate_predates_snapshot', 'candidate predates its snapshot');
  return { snapshot, candidate, snapshotTime, candidateTime };
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
    isRecord(authority.signature) && authority.signature.algorithm === 'Ed25519',
    'authority_signature_invalid',
    'authority signature metadata is invalid',
  );
  requireCondition(
    isRecord(trustStore) && trustStore.schema === 'axm-authority-trust/1' && Array.isArray(trustStore.keys),
    'trust_store_invalid',
    'trust store schema is invalid',
  );
  const trustKey = trustStore.keys.find((row) =>
    isRecord(row)
    && row.keyId === authority.signature.keyId
    && row.issuer === authority.issuer
    && row.algorithm === 'Ed25519'
  );
  requireCondition(trustKey, 'authority_key_untrusted', 'authority signing key is not trusted for the issuer');
  requireCondition(typeof trustKey.publicKeyPem === 'string', 'trust_store_invalid', 'trusted key has no public key');
  requireCondition(typeof authority.signature.value === 'string', 'authority_signature_invalid', 'signature value is missing');

  let verified = false;
  try {
    verified = verifySignature(
      null,
      Buffer.from(canonicalJson(signedAuthorityBody(authority)), 'utf8'),
      createPublicKey(trustKey.publicKeyPem),
      Buffer.from(authority.signature.value, 'base64'),
    );
  } catch {
    verified = false;
  }
  requireCondition(verified, 'authority_signature_invalid', 'authority signature did not verify');
  return authority;
}

function sortedUniqueStrings(value, code, label) {
  requireCondition(Array.isArray(value), code, `${label} must be an array`);
  const rows = value.map((row) => {
    requireCondition(typeof row === 'string' && row.trim(), code, `${label} entries must be non-empty strings`);
    return row.trim();
  });
  return [...new Set(rows)].sort();
}

function reason(code, message) {
  return { code, message };
}

function buildDecision({ disposition, reasons, checkedAt, candidate, snapshot, authority, candidateVerified, authorityVerified }) {
  const body = {
    disposition,
    reasons,
    checkedAt,
    candidateId: candidate?.candidateId ?? null,
    snapshotId: snapshot?.snapshotId ?? null,
    authorityId: authority?.authorityId ?? null,
    candidateVerified,
    authorityVerified,
  };
  return {
    schema: 'axm-candidate-authority-decision/1',
    decisionId: digest('authoritydecision1', body),
    ...body,
    claimBoundary:
      'This receipt determines candidate eligibility under one verified authority envelope. It carries no actuation surface and does not itself execute, target, engage, command an effector, or release a weapon.',
  };
}

export function evaluateCandidateAuthority(transaction, authority, trustStore, checkedAt) {
  const checkedAtMs = Date.parse(checkedAt);
  if (!Number.isFinite(checkedAtMs)) {
    return buildDecision({
      disposition: 'refuse',
      reasons: [reason('checked_at_invalid', 'authority evaluation time is invalid')],
      checkedAt,
      candidate: transaction?.candidate,
      snapshot: transaction?.snapshot,
      authority,
      candidateVerified: false,
      authorityVerified: false,
    });
  }

  let verifiedTransaction;
  try {
    verifiedTransaction = verifyTransaction(transaction);
  } catch (error) {
    const code = error instanceof GateError ? error.code : 'transaction_invalid';
    return buildDecision({
      disposition: 'refuse',
      reasons: [reason(code, error instanceof Error ? error.message : 'candidate transaction is invalid')],
      checkedAt: new Date(checkedAtMs).toISOString(),
      candidate: transaction?.candidate,
      snapshot: transaction?.snapshot,
      authority,
      candidateVerified: false,
      authorityVerified: false,
    });
  }

  let verifiedAuthority;
  try {
    verifiedAuthority = verifyAuthority(authority, trustStore);
  } catch (error) {
    const code = error instanceof GateError ? error.code : 'authority_invalid';
    return buildDecision({
      disposition: 'refuse',
      reasons: [reason(code, error instanceof Error ? error.message : 'authority is invalid')],
      checkedAt: new Date(checkedAtMs).toISOString(),
      candidate: verifiedTransaction.candidate,
      snapshot: verifiedTransaction.snapshot,
      authority,
      candidateVerified: true,
      authorityVerified: false,
    });
  }

  const notBeforeMs = Date.parse(verifiedAuthority.notBefore);
  const expiresAtMs = Date.parse(verifiedAuthority.expiresAt);
  if (!Number.isFinite(notBeforeMs) || !Number.isFinite(expiresAtMs) || expiresAtMs <= notBeforeMs) {
    return buildDecision({
      disposition: 'refuse',
      reasons: [reason('authority_window_invalid', 'authority validity window is invalid')],
      checkedAt: new Date(checkedAtMs).toISOString(),
      candidate: verifiedTransaction.candidate,
      snapshot: verifiedTransaction.snapshot,
      authority: verifiedAuthority,
      candidateVerified: true,
      authorityVerified: true,
    });
  }
  if (checkedAtMs < notBeforeMs) {
    return buildDecision({
      disposition: 'hold',
      reasons: [reason('authority_not_yet_active', 'authority is not yet active')],
      checkedAt: new Date(checkedAtMs).toISOString(),
      candidate: verifiedTransaction.candidate,
      snapshot: verifiedTransaction.snapshot,
      authority: verifiedAuthority,
      candidateVerified: true,
      authorityVerified: true,
    });
  }
  if (checkedAtMs > expiresAtMs) {
    return buildDecision({
      disposition: 'safe_state',
      reasons: [reason('authority_expired', 'authority has expired')],
      checkedAt: new Date(checkedAtMs).toISOString(),
      candidate: verifiedTransaction.candidate,
      snapshot: verifiedTransaction.snapshot,
      authority: verifiedAuthority,
      candidateVerified: true,
      authorityVerified: true,
    });
  }

  const maxSnapshotAgeMs = Number(verifiedAuthority.maxSnapshotAgeMs);
  if (!Number.isInteger(maxSnapshotAgeMs) || maxSnapshotAgeMs < 0) {
    return buildDecision({
      disposition: 'refuse',
      reasons: [reason('authority_snapshot_age_invalid', 'authority snapshot-age bound is invalid')],
      checkedAt: new Date(checkedAtMs).toISOString(),
      candidate: verifiedTransaction.candidate,
      snapshot: verifiedTransaction.snapshot,
      authority: verifiedAuthority,
      candidateVerified: true,
      authorityVerified: true,
    });
  }
  if (verifiedTransaction.snapshotTime > checkedAtMs + MAX_CLOCK_SKEW_MS) {
    return buildDecision({
      disposition: 'hold',
      reasons: [reason('snapshot_from_future', 'snapshot time exceeds permitted clock skew')],
      checkedAt: new Date(checkedAtMs).toISOString(),
      candidate: verifiedTransaction.candidate,
      snapshot: verifiedTransaction.snapshot,
      authority: verifiedAuthority,
      candidateVerified: true,
      authorityVerified: true,
    });
  }
  if (checkedAtMs - verifiedTransaction.snapshotTime > maxSnapshotAgeMs) {
    return buildDecision({
      disposition: 'hold',
      reasons: [reason('snapshot_too_old', 'snapshot exceeds the authority freshness bound')],
      checkedAt: new Date(checkedAtMs).toISOString(),
      candidate: verifiedTransaction.candidate,
      snapshot: verifiedTransaction.snapshot,
      authority: verifiedAuthority,
      candidateVerified: true,
      authorityVerified: true,
    });
  }

  let allowedProducers;
  let allowedActionClasses;
  try {
    allowedProducers = sortedUniqueStrings(verifiedAuthority.allowedProducers, 'authority_producers_invalid', 'allowedProducers');
    allowedActionClasses = sortedUniqueStrings(verifiedAuthority.allowedActionClasses, 'authority_actions_invalid', 'allowedActionClasses');
  } catch (error) {
    return buildDecision({
      disposition: 'refuse',
      reasons: [reason(error.code ?? 'authority_constraints_invalid', error.message)],
      checkedAt: new Date(checkedAtMs).toISOString(),
      candidate: verifiedTransaction.candidate,
      snapshot: verifiedTransaction.snapshot,
      authority: verifiedAuthority,
      candidateVerified: true,
      authorityVerified: true,
    });
  }

  if (!allowedProducers.includes(verifiedTransaction.candidate.producer)) {
    return buildDecision({
      disposition: 'refuse',
      reasons: [reason('candidate_producer_not_authorized', 'candidate producer is outside the authority envelope')],
      checkedAt: new Date(checkedAtMs).toISOString(),
      candidate: verifiedTransaction.candidate,
      snapshot: verifiedTransaction.snapshot,
      authority: verifiedAuthority,
      candidateVerified: true,
      authorityVerified: true,
    });
  }
  if (!allowedActionClasses.includes(verifiedTransaction.candidate.actionClass)) {
    return buildDecision({
      disposition: 'refuse',
      reasons: [reason('candidate_action_not_authorized', 'candidate action class is outside the authority envelope')],
      checkedAt: new Date(checkedAtMs).toISOString(),
      candidate: verifiedTransaction.candidate,
      snapshot: verifiedTransaction.snapshot,
      authority: verifiedAuthority,
      candidateVerified: true,
      authorityVerified: true,
    });
  }

  const payload = verifiedTransaction.candidate.payload;
  const payloadKeys = Object.keys(payload).sort();
  if (verifiedAuthority.requiredPayloadFields !== undefined) {
    let required;
    try {
      required = sortedUniqueStrings(verifiedAuthority.requiredPayloadFields, 'authority_payload_fields_invalid', 'requiredPayloadFields');
    } catch (error) {
      return buildDecision({
        disposition: 'refuse',
        reasons: [reason(error.code ?? 'authority_payload_fields_invalid', error.message)],
        checkedAt: new Date(checkedAtMs).toISOString(),
        candidate: verifiedTransaction.candidate,
        snapshot: verifiedTransaction.snapshot,
        authority: verifiedAuthority,
        candidateVerified: true,
        authorityVerified: true,
      });
    }
    const missing = required.filter((key) => !Object.hasOwn(payload, key));
    if (missing.length) {
      return buildDecision({
        disposition: 'refuse',
        reasons: [reason('candidate_payload_required_fields_missing', `candidate payload is missing: ${missing.join(', ')}`)],
        checkedAt: new Date(checkedAtMs).toISOString(),
        candidate: verifiedTransaction.candidate,
        snapshot: verifiedTransaction.snapshot,
        authority: verifiedAuthority,
        candidateVerified: true,
        authorityVerified: true,
      });
    }
  }
  if (verifiedAuthority.allowedPayloadFields !== undefined) {
    let allowedFields;
    try {
      allowedFields = sortedUniqueStrings(verifiedAuthority.allowedPayloadFields, 'authority_payload_fields_invalid', 'allowedPayloadFields');
    } catch (error) {
      return buildDecision({
        disposition: 'refuse',
        reasons: [reason(error.code ?? 'authority_payload_fields_invalid', error.message)],
        checkedAt: new Date(checkedAtMs).toISOString(),
        candidate: verifiedTransaction.candidate,
        snapshot: verifiedTransaction.snapshot,
        authority: verifiedAuthority,
        candidateVerified: true,
        authorityVerified: true,
      });
    }
    const unexpected = payloadKeys.filter((key) => !allowedFields.includes(key));
    if (unexpected.length) {
      return buildDecision({
        disposition: 'refuse',
        reasons: [reason('candidate_payload_fields_not_authorized', `candidate payload contains unauthorized fields: ${unexpected.join(', ')}`)],
        checkedAt: new Date(checkedAtMs).toISOString(),
        candidate: verifiedTransaction.candidate,
        snapshot: verifiedTransaction.snapshot,
        authority: verifiedAuthority,
        candidateVerified: true,
        authorityVerified: true,
      });
    }
  }

  const payloadBytes = Buffer.byteLength(canonicalJson(payload), 'utf8');
  const maxPayloadBytes = Number(verifiedAuthority.maxPayloadBytes);
  if (!Number.isInteger(maxPayloadBytes) || maxPayloadBytes < 2 || payloadBytes > maxPayloadBytes) {
    return buildDecision({
      disposition: 'refuse',
      reasons: [reason('candidate_payload_size_not_authorized', 'candidate payload exceeds or lacks a valid authority size bound')],
      checkedAt: new Date(checkedAtMs).toISOString(),
      candidate: verifiedTransaction.candidate,
      snapshot: verifiedTransaction.snapshot,
      authority: verifiedAuthority,
      candidateVerified: true,
      authorityVerified: true,
    });
  }

  return buildDecision({
    disposition: 'allow',
    reasons: [reason('candidate_within_verified_authority', 'candidate is eligible under the verified authority envelope')],
    checkedAt: new Date(checkedAtMs).toISOString(),
    candidate: verifiedTransaction.candidate,
    snapshot: verifiedTransaction.snapshot,
    authority: verifiedAuthority,
    candidateVerified: true,
    authorityVerified: true,
  });
}

async function main(argv) {
  if (argv.length !== 5) {
    console.error('usage: authority_gate.mjs <transaction.json> <authority.json> <trust.json> <checked-at> <decision.json>');
    return 2;
  }
  const [transactionPath, authorityPath, trustPath, checkedAt, outputPath] = argv;
  const [transaction, authority, trustStore] = await Promise.all([
    readFile(transactionPath, 'utf8').then(JSON.parse),
    readFile(authorityPath, 'utf8').then(JSON.parse),
    readFile(trustPath, 'utf8').then(JSON.parse),
  ]);
  const decision = evaluateCandidateAuthority(transaction, authority, trustStore, checkedAt);
  await writeFile(outputPath, `${JSON.stringify(decision, null, 2)}\n`, 'utf8');
  process.stdout.write(`${JSON.stringify(decision, null, 2)}\n`);
  return decision.disposition === 'allow' ? 0 : 1;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exitCode = await main(process.argv.slice(2));
}
