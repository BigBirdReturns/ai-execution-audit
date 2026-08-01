import { createHash } from 'node:crypto';
import type { CommandIntelligenceStore } from './entityStore';
import type { FeedStatus, PolybolosEntity } from './types';

export interface CommandIntelligenceCheckpoint {
  schema: 'polybolos-command-intelligence-checkpoint/1';
  checkpointId: string;
  sequence: number;
  observedAt: string;
  staleAfterMs: number;
  entityCount: number;
  feedCount: number;
  feedsDigest: string;
  entityRoot: string;
  softwareRecordId: string;
  hashAlgorithm: 'sha256';
  treeAlgorithm: 'sorted-entity-id-pair-duplicate-last-v1';
  claimBoundary: string;
}

export interface EntityWitnessSibling {
  side: 'left' | 'right';
  hash: string;
}

export interface CommandIntelligenceEntityWitness {
  schema: 'polybolos-command-intelligence-entity-witness/1';
  witnessId: string;
  checkpointId: string;
  entityId: string;
  entityIndex: number;
  entityCount: number;
  leafHash: string;
  siblings: EntityWitnessSibling[];
  entity: PolybolosEntity;
  claimBoundary: string;
}

export interface CompiledCommandIntelligenceCheckpoint {
  checkpoint: CommandIntelligenceCheckpoint;
  cache: 'hit' | 'miss';
  compileMilliseconds: number;
  witness(entityId: string): CommandIntelligenceEntityWitness;
}

interface CachedCheckpoint {
  checkpoint: CommandIntelligenceCheckpoint;
  compiledAt: number;
  entities: PolybolosEntity[];
  entityIndex: Map<string, number>;
  levels: string[][];
}

const EMPTY_ENTITY_ROOT = hashText('polybolos-ci-empty-entity-tree-v1');
const STORE_CACHE = new WeakMap<CommandIntelligenceStore, Map<string, CachedCheckpoint>>();
const MAX_CACHE_ENTRIES_PER_STORE = 4;
const MAX_WITNESS_DEPTH = 64;

export function canonicalCheckpointJson(value: unknown): string {
  if (value === null) return 'null';
  if (Array.isArray(value)) return `[${value.map(canonicalCheckpointJson).join(',')}]`;
  if (typeof value === 'object') {
    const row = value as Record<string, unknown>;
    return `{${Object.keys(row)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalCheckpointJson(row[key])}`)
      .join(',')}}`;
  }
  if (typeof value === 'number' && !Number.isFinite(value)) {
    throw new Error('checkpoint identity cannot include non-finite numbers');
  }
  const encoded = JSON.stringify(value);
  if (encoded === undefined) throw new Error('checkpoint identity contains a non-JSON value');
  return encoded;
}

function hashText(value: string): string {
  return createHash('sha256').update(value, 'utf8').digest('hex');
}

function digest(prefix: string, value: unknown): string {
  return `${prefix}_${hashText(canonicalCheckpointJson(value))}`;
}

function entityLeafHash(entity: PolybolosEntity): string {
  return hashText(`polybolos-ci-entity-leaf-v1\0${canonicalCheckpointJson(entity)}`);
}

function entityNodeHash(left: string, right: string): string {
  return hashText(`polybolos-ci-entity-node-v1\0${left}\0${right}`);
}

function feedsDigest(feeds: FeedStatus[]): string {
  return hashText(`polybolos-ci-feeds-v1\0${canonicalCheckpointJson(feeds)}`);
}

function assertCheckpointInputs(
  sequence: number,
  observedAt: string,
  staleAfterMs: number,
  softwareRecordId: string,
): void {
  if (!Number.isInteger(sequence) || sequence < 0) {
    throw new Error('checkpoint sequence must be a non-negative integer');
  }
  if (!Number.isFinite(Date.parse(observedAt))) {
    throw new Error('checkpoint observedAt must be a valid date-time');
  }
  if (!Number.isInteger(staleAfterMs) || staleAfterMs < 1_000 || staleAfterMs > 86_400_000) {
    throw new Error('checkpoint staleAfterMs must be an integer between 1000 and 86400000');
  }
  if (!softwareRecordId || softwareRecordId.length > 256) {
    throw new Error('checkpoint softwareRecordId is required and bounded');
  }
}

function buildLevels(entities: PolybolosEntity[]): string[][] {
  if (entities.length === 0) return [[EMPTY_ENTITY_ROOT]];
  const levels: string[][] = [entities.map(entityLeafHash)];
  while (levels.at(-1)!.length > 1) {
    const prior = levels.at(-1)!;
    const next: string[] = [];
    for (let index = 0; index < prior.length; index += 2) {
      const left = prior[index];
      const right = prior[index + 1] ?? left;
      next.push(entityNodeHash(left, right));
    }
    levels.push(next);
  }
  return levels;
}

export function deriveCheckpointId(checkpoint: CommandIntelligenceCheckpoint): string {
  const { checkpointId: _checkpointId, claimBoundary: _claimBoundary, ...body } = checkpoint;
  return digest('checkpoint1', body);
}

export function deriveEntityWitnessId(witness: CommandIntelligenceEntityWitness): string {
  const { witnessId: _witnessId, claimBoundary: _claimBoundary, ...body } = witness;
  return digest('entitywitness1', body);
}

function buildWitness(cached: CachedCheckpoint, entityId: string): CommandIntelligenceEntityWitness {
  const entityIndex = cached.entityIndex.get(entityId);
  if (entityIndex === undefined) throw new Error(`CI_CHECKPOINT_ENTITY_NOT_FOUND: ${entityId}`);
  const entity = cached.entities[entityIndex];
  const siblings: EntityWitnessSibling[] = [];
  let index = entityIndex;
  for (let levelIndex = 0; levelIndex < cached.levels.length - 1; levelIndex += 1) {
    const level = cached.levels[levelIndex];
    const onRight = index % 2 === 1;
    const siblingIndex = onRight ? index - 1 : index + 1;
    siblings.push({
      side: onRight ? 'left' : 'right',
      hash: level[siblingIndex] ?? level[index],
    });
    index = Math.floor(index / 2);
  }
  if (siblings.length > MAX_WITNESS_DEPTH) {
    throw new Error('CI_CHECKPOINT_WITNESS_DEPTH: entity witness exceeds bounded depth');
  }
  const body = {
    schema: 'polybolos-command-intelligence-entity-witness/1' as const,
    checkpointId: cached.checkpoint.checkpointId,
    entityId,
    entityIndex,
    entityCount: cached.entities.length,
    leafHash: entityLeafHash(entity),
    siblings,
    entity,
  };
  const witness: CommandIntelligenceEntityWitness = {
    ...body,
    witnessId: '',
    claimBoundary:
      'This witness proves that one normalized observation was included in one Command Intelligence checkpoint. It carries no command, targeting, engagement, effector, or execution authority.',
  };
  witness.witnessId = deriveEntityWitnessId(witness);
  return witness;
}

export function verifyEntityWitness(
  checkpoint: CommandIntelligenceCheckpoint,
  witness: CommandIntelligenceEntityWitness,
): boolean {
  try {
    if (checkpoint.schema !== 'polybolos-command-intelligence-checkpoint/1') return false;
    if (checkpoint.checkpointId !== deriveCheckpointId(checkpoint)) return false;
    if (witness.schema !== 'polybolos-command-intelligence-entity-witness/1') return false;
    if (witness.checkpointId !== checkpoint.checkpointId) return false;
    if (witness.entityId !== witness.entity.id) return false;
    if (witness.entityCount !== checkpoint.entityCount) return false;
    if (!Number.isInteger(witness.entityIndex) || witness.entityIndex < 0 || witness.entityIndex >= witness.entityCount) {
      return false;
    }
    if (!Array.isArray(witness.siblings) || witness.siblings.length > MAX_WITNESS_DEPTH) return false;
    if (witness.witnessId !== deriveEntityWitnessId(witness)) return false;
    let current = entityLeafHash(witness.entity);
    if (current !== witness.leafHash) return false;
    for (const sibling of witness.siblings) {
      if (!sibling || !/^[0-9a-f]{64}$/.test(sibling.hash)) return false;
      if (sibling.side === 'left') current = entityNodeHash(sibling.hash, current);
      else if (sibling.side === 'right') current = entityNodeHash(current, sibling.hash);
      else return false;
    }
    return current === checkpoint.entityRoot;
  } catch {
    return false;
  }
}

function cacheFor(store: CommandIntelligenceStore): Map<string, CachedCheckpoint> {
  let cache = STORE_CACHE.get(store);
  if (!cache) {
    cache = new Map();
    STORE_CACHE.set(store, cache);
  }
  return cache;
}

function cacheKey(
  sequence: number,
  observedAt: string,
  staleAfterMs: number,
  softwareRecordId: string,
): string {
  return `${sequence}\0${observedAt}\0${staleAfterMs}\0${softwareRecordId}`;
}

function compileCheckpoint(
  store: CommandIntelligenceStore,
  observedAt: string,
  staleAfterMs: number,
  softwareRecordId: string,
): CachedCheckpoint {
  const sequence = store.getSequence();
  assertCheckpointInputs(sequence, observedAt, staleAfterMs, softwareRecordId);
  const entities = store.getEntities();
  const entityIndex = new Map<string, number>();
  entities.forEach((entity, index) => {
    if (entityIndex.has(entity.id)) throw new Error(`CI_CHECKPOINT_DUPLICATE_ENTITY: ${entity.id}`);
    entityIndex.set(entity.id, index);
  });
  const feeds = store.getFeedStatuses(staleAfterMs, Date.parse(observedAt));
  const levels = buildLevels(entities);
  const base = {
    schema: 'polybolos-command-intelligence-checkpoint/1' as const,
    sequence,
    observedAt: new Date(Date.parse(observedAt)).toISOString(),
    staleAfterMs,
    entityCount: entities.length,
    feedCount: feeds.length,
    feedsDigest: feedsDigest(feeds),
    entityRoot: levels.at(-1)![0],
    softwareRecordId,
    hashAlgorithm: 'sha256' as const,
    treeAlgorithm: 'sorted-entity-id-pair-duplicate-last-v1' as const,
  };
  const checkpoint: CommandIntelligenceCheckpoint = {
    ...base,
    checkpointId: digest('checkpoint1', base),
    claimBoundary:
      'This checkpoint commits to one normalized Command Intelligence state without carrying the full common operating picture. It carries no command, targeting, engagement, effector, or execution authority.',
  };
  return {
    checkpoint,
    compiledAt: Date.now(),
    entities,
    entityIndex,
    levels,
  };
}

export function getCommandIntelligenceCheckpoint(
  store: CommandIntelligenceStore,
  observedAt: string,
  staleAfterMs: number,
  softwareRecordId: string,
): CompiledCommandIntelligenceCheckpoint {
  const sequence = store.getSequence();
  const key = cacheKey(sequence, observedAt, staleAfterMs, softwareRecordId);
  const cache = cacheFor(store);
  const existing = cache.get(key);
  if (existing) {
    cache.delete(key);
    cache.set(key, existing);
    return {
      checkpoint: existing.checkpoint,
      cache: 'hit',
      compileMilliseconds: 0,
      witness: (entityId) => buildWitness(existing, entityId),
    };
  }

  const started = performance.now();
  const compiled = compileCheckpoint(store, observedAt, staleAfterMs, softwareRecordId);
  const compileMilliseconds = performance.now() - started;
  cache.set(key, compiled);
  while (cache.size > MAX_CACHE_ENTRIES_PER_STORE) {
    const oldest = cache.keys().next().value;
    if (typeof oldest !== 'string') break;
    cache.delete(oldest);
  }
  return {
    checkpoint: compiled.checkpoint,
    cache: 'miss',
    compileMilliseconds,
    witness: (entityId) => buildWitness(compiled, entityId),
  };
}
