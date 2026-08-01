import { createHash } from 'node:crypto';
import type { CommandIntelligenceSnapshot } from './snapshot';

export interface CommandCandidateInput {
  producer: string;
  createdAt: string;
  actionClass: string;
  payload: Record<string, unknown>;
}

export interface CommandCandidateReceipt {
  schema: 'polybolos-command-candidate/1';
  candidateId: string;
  snapshotId: string;
  producer: string;
  createdAt: string;
  actionClass: string;
  payload: Record<string, unknown>;
  claimBoundary: string;
}

const MAX_PAYLOAD_DEPTH = 8;
const MAX_PAYLOAD_NODES = 4_096;
const MAX_OBJECT_KEYS = 512;
const MAX_ARRAY_ITEMS = 2_048;
const MAX_KEY_LENGTH = 128;
const MAX_STRING_LENGTH = 64 * 1024;

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

const FORBIDDEN_OBJECT_KEYS = new Set(['__proto__', 'constructor', 'prototype']);

function normalizedKey(key: string): string {
  return key.replace(/[^a-z0-9]/gi, '').toLowerCase();
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function assertJsonCandidateValue(
  value: unknown,
  path: string,
  depth: number,
  counter: { nodes: number },
): void {
  counter.nodes += 1;
  if (counter.nodes > MAX_PAYLOAD_NODES) {
    throw new Error(`candidate payload exceeds ${MAX_PAYLOAD_NODES} bounded values`);
  }
  if (depth > MAX_PAYLOAD_DEPTH) {
    throw new Error(`candidate payload exceeds maximum depth ${MAX_PAYLOAD_DEPTH}`);
  }

  if (value === null || typeof value === 'boolean') return;
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) throw new Error(`candidate payload contains a non-finite number at ${path}`);
    return;
  }
  if (typeof value === 'string') {
    if (value.length > MAX_STRING_LENGTH) {
      throw new Error(`candidate payload string exceeds ${MAX_STRING_LENGTH} characters at ${path}`);
    }
    return;
  }
  if (Array.isArray(value)) {
    if (value.length > MAX_ARRAY_ITEMS) {
      throw new Error(`candidate payload array exceeds ${MAX_ARRAY_ITEMS} items at ${path}`);
    }
    value.forEach((item, index) => {
      assertJsonCandidateValue(item, `${path}[${index}]`, depth + 1, counter);
    });
    return;
  }
  if (!isPlainObject(value)) {
    throw new Error(`candidate payload contains a non-JSON value at ${path}`);
  }

  const entries = Object.entries(value);
  if (entries.length > MAX_OBJECT_KEYS) {
    throw new Error(`candidate payload object exceeds ${MAX_OBJECT_KEYS} keys at ${path}`);
  }
  for (const [key, nested] of entries) {
    if (!key || key.length > MAX_KEY_LENGTH) {
      throw new Error(`candidate payload contains an invalid key at ${path}`);
    }
    if (FORBIDDEN_OBJECT_KEYS.has(key)) {
      throw new Error(`candidate payload contains forbidden object key ${key} at ${path}`);
    }
    if (RESERVED_AUTHORITY_KEYS.has(normalizedKey(key))) {
      throw new Error(`candidate payload may not carry authority field ${key} at ${path}`);
    }
    assertJsonCandidateValue(nested, `${path}.${key}`, depth + 1, counter);
  }
}

export function assertCandidatePayload(value: unknown): asserts value is Record<string, unknown> {
  if (!isPlainObject(value)) throw new Error('candidate payload must be an object');
  assertJsonCandidateValue(value, '$', 0, { nodes: 0 });
}

function canonicalJson(value: unknown): string {
  if (value === null) return 'null';
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`;
  if (typeof value === 'object') {
    const row = value as Record<string, unknown>;
    return `{${Object.keys(row)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(row[key])}`)
      .join(',')}}`;
  }
  if (typeof value === 'number' && !Number.isFinite(value)) {
    throw new Error('candidate identity cannot include non-finite numbers');
  }
  const encoded = JSON.stringify(value);
  if (encoded === undefined) throw new Error('candidate identity contains a non-JSON value');
  return encoded;
}

function candidateId(value: unknown): string {
  return `candidate1_${createHash('sha256').update(canonicalJson(value), 'utf8').digest('hex')}`;
}

export function createCommandCandidate(
  snapshot: CommandIntelligenceSnapshot,
  input: CommandCandidateInput,
): CommandCandidateReceipt {
  const createdAtMs = Date.parse(input.createdAt);
  const observedAtMs = Date.parse(snapshot.observedAt);
  if (!Number.isFinite(createdAtMs)) throw new Error('candidate createdAt must be a valid date-time');
  if (!Number.isFinite(observedAtMs)) throw new Error('snapshot observedAt must be a valid date-time');
  if (createdAtMs < observedAtMs) {
    throw new Error('candidate cannot predate the Command Intelligence snapshot it cites');
  }
  const producer = input.producer.trim();
  const actionClass = input.actionClass.trim();
  if (!producer || producer.length > 128) throw new Error('candidate producer is required and bounded');
  if (!actionClass || actionClass.length > 128) throw new Error('candidate actionClass is required and bounded');
  assertCandidatePayload(input.payload);

  const identityBody = {
    snapshotId: snapshot.snapshotId,
    producer,
    createdAt: new Date(createdAtMs).toISOString(),
    actionClass,
    payload: input.payload,
  };
  return {
    schema: 'polybolos-command-candidate/1',
    candidateId: candidateId(identityBody),
    ...identityBody,
    claimBoundary:
      'This record binds a candidate action to an exact Command Intelligence snapshot. It carries no command authority and cannot authorize execution.',
  };
}

export function verifyCommandCandidateBinding(
  candidate: CommandCandidateReceipt,
  snapshot: CommandIntelligenceSnapshot,
): boolean {
  if (!candidate || candidate.schema !== 'polybolos-command-candidate/1') return false;
  if (candidate.snapshotId !== snapshot.snapshotId) return false;
  if (typeof candidate.candidateId !== 'string' || !candidate.candidateId.startsWith('candidate1_')) {
    return false;
  }
  try {
    const rebuilt = createCommandCandidate(snapshot, {
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
