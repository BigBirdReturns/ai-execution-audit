import { createHash } from 'node:crypto';
import { CommandIntelligenceStore } from './entityStore';
import type { FeedStatus, PolybolosEntity } from './types';

export interface CommandIntelligenceSnapshot {
  schema: 'polybolos-command-intelligence-snapshot/1';
  snapshotId: string;
  sequence: number;
  observedAt: string;
  entityCount: number;
  feeds: FeedStatus[];
  entities: PolybolosEntity[];
  claimBoundary: string;
}

export interface SnapshotDiff {
  schema: 'polybolos-command-intelligence-diff/1';
  from: string;
  to: string;
  added: string[];
  removed: string[];
  changed: string[];
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
  if (typeof value === 'number' && !Number.isFinite(value)) return 'null';
  return JSON.stringify(value);
}

function digest(prefix: string, value: unknown): string {
  return `${prefix}_${createHash('sha256').update(canonicalJson(value), 'utf8').digest('hex')}`;
}

export function deriveStableObservationAt(
  store: CommandIntelligenceStore,
  staleAfterMs: number,
  nowMs: number,
  floorMs: number,
): string {
  if (!Number.isFinite(nowMs) || !Number.isFinite(floorMs)) {
    throw new Error('stable observation time requires finite clocks');
  }
  if (!Number.isFinite(staleAfterMs) || staleAfterMs < 0) {
    throw new Error('staleAfterMs must be a non-negative finite number');
  }

  const lastUpdateMs = Date.parse(store.getLastUpdate() ?? '');
  let markerMs = Math.max(0, floorMs);
  if (Number.isFinite(lastUpdateMs)) markerMs = Math.max(markerMs, lastUpdateMs);

  const evaluationMs = Math.max(nowMs, markerMs);
  for (const feed of store.getFeedStatuses(staleAfterMs, evaluationMs)) {
    const feedUpdateMs = Date.parse(feed.lastUpdate ?? '');
    if (!Number.isFinite(feedUpdateMs)) continue;
    const staleTransitionMs = feedUpdateMs + staleAfterMs + 1;
    if (staleTransitionMs <= evaluationMs) {
      markerMs = Math.max(markerMs, staleTransitionMs);
    }
  }

  return new Date(markerMs || evaluationMs).toISOString();
}

export function createCommandIntelligenceSnapshot(
  store: CommandIntelligenceStore,
  observedAt: string,
  staleAfterMs = 5 * 60_000,
): CommandIntelligenceSnapshot {
  const entities = store.getEntities();
  const feeds = store.getFeedStatuses(staleAfterMs, Date.parse(observedAt));
  const body = {
    sequence: store.getSequence(),
    observedAt,
    feeds,
    entities,
  };
  return {
    schema: 'polybolos-command-intelligence-snapshot/1',
    snapshotId: digest('ci1', body),
    sequence: body.sequence,
    observedAt,
    entityCount: entities.length,
    feeds,
    entities,
    claimBoundary:
      'This artifact records Command Intelligence observations and source health. It carries no command authority and does not certify threat identity, engagement legality, or operational effectiveness.',
  };
}

function entityFingerprint(entity: PolybolosEntity): string {
  return digest('entity1', entity);
}

export function diffCommandIntelligenceSnapshots(
  from: CommandIntelligenceSnapshot,
  to: CommandIntelligenceSnapshot,
): SnapshotDiff {
  const before = new Map(from.entities.map((entity) => [entity.id, entityFingerprint(entity)]));
  const after = new Map(to.entities.map((entity) => [entity.id, entityFingerprint(entity)]));
  const added = Array.from(after.keys()).filter((id) => !before.has(id)).sort();
  const removed = Array.from(before.keys()).filter((id) => !after.has(id)).sort();
  const changed = Array.from(after.keys())
    .filter((id) => before.has(id) && before.get(id) !== after.get(id))
    .sort();
  return {
    schema: 'polybolos-command-intelligence-diff/1',
    from: from.snapshotId,
    to: to.snapshotId,
    added,
    removed,
    changed,
  };
}
