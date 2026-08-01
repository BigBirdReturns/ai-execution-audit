import { createHash } from 'node:crypto';
import type { PersistenceKind } from './persistence';
import type { CommandIntelligenceSnapshot } from './snapshot';
import {
  Classification,
  Domain,
  ThreatLevel,
  type PolybolosEntity,
} from './types';

const THREAT_ORDER: ThreatLevel[] = [
  ThreatLevel.NONE,
  ThreatLevel.LOW,
  ThreatLevel.ELEVATED,
  ThreatLevel.HIGH,
  ThreatLevel.CRITICAL,
];

export interface CabinetProjectionOptions {
  domains?: Domain[];
  minimumThreat?: ThreatLevel;
  limit?: number;
  persistence: PersistenceKind;
  persistenceDiagnostics: Record<string, unknown>;
}

export interface CabinetEntity {
  id: string;
  name: string;
  domain: Domain;
  entityType: PolybolosEntity['entityType'];
  position: PolybolosEntity['position'];
  threat: ThreatLevel;
  classification: Classification;
  source: {
    provider: string;
    feed: string;
    confidence: number;
  };
  timestamp: string;
}

export interface CommandIntelligenceCabinetFrame {
  schema: 'polybolos-command-intelligence-cabinet-frame/1';
  frameId: string;
  stateId: string;
  snapshotId: string;
  sequence: number;
  observedAt: string;
  filters: {
    domains: Domain[];
    minimumThreat: ThreatLevel;
    limit: number;
  };
  counts: {
    observed: number;
    eligible: number;
    included: number;
    truncated: number;
    staleFeeds: number;
    byDomain: Record<string, number>;
    byThreat: Record<string, number>;
    byClassification: Record<string, number>;
    bySource: Record<string, number>;
  };
  lamps: {
    empty: boolean;
    stale: boolean;
    critical: boolean;
    unknownClassification: boolean;
    truncated: boolean;
    durableLocalState: boolean;
  };
  persistence: {
    kind: PersistenceKind;
    diagnostics: Record<string, unknown>;
  };
  entities: CabinetEntity[];
  claimBoundary: string;
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

function digest(prefix: 'ciframe1' | 'cistate1', value: unknown): string {
  return `${prefix}_${createHash('sha256').update(canonicalJson(value), 'utf8').digest('hex')}`;
}

function increment(target: Record<string, number>, key: string): void {
  target[key] = (target[key] ?? 0) + 1;
}

function cabinetEntity(entity: PolybolosEntity): CabinetEntity {
  return {
    id: entity.id,
    name: entity.name,
    domain: entity.domain,
    entityType: entity.entityType,
    position: entity.position,
    threat: entity.threat,
    classification: entity.classification,
    source: {
      provider: entity.source.provider,
      feed: entity.source.feed,
      confidence: entity.source.confidence,
    },
    timestamp: entity.timestamp,
  };
}

export function projectCommandIntelligenceCabinetFrame(
  snapshot: CommandIntelligenceSnapshot,
  options: CabinetProjectionOptions,
): CommandIntelligenceCabinetFrame {
  const domains = Array.from(new Set(options.domains ?? Object.values(Domain))).sort();
  const minimumThreat = options.minimumThreat ?? ThreatLevel.NONE;
  const minimumIndex = THREAT_ORDER.indexOf(minimumThreat);
  if (minimumIndex < 0) throw new Error(`unsupported minimumThreat: ${minimumThreat}`);
  const limit = options.limit ?? 512;
  if (!Number.isInteger(limit) || limit < 1 || limit > 5000) {
    throw new Error('cabinet limit must be an integer between 1 and 5000');
  }

  const eligible = snapshot.entities
    .filter(
      (entity) =>
        domains.includes(entity.domain) &&
        THREAT_ORDER.indexOf(entity.threat) >= minimumIndex,
    )
    .sort((a, b) => {
      const threat = THREAT_ORDER.indexOf(b.threat) - THREAT_ORDER.indexOf(a.threat);
      return threat !== 0 ? threat : a.id.localeCompare(b.id);
    });
  const included = eligible.slice(0, limit).map(cabinetEntity);

  const byDomain: Record<string, number> = {};
  const byThreat: Record<string, number> = {};
  const byClassification: Record<string, number> = {};
  const bySource: Record<string, number> = {};
  for (const entity of eligible) {
    increment(byDomain, entity.domain);
    increment(byThreat, entity.threat);
    increment(byClassification, entity.classification);
    increment(bySource, `${entity.source.provider}/${entity.source.feed}`);
  }

  const staleFeeds = snapshot.feeds.filter((feed) => feed.stale).length;
  const semanticBody = {
    schema: 'polybolos-command-intelligence-cabinet-frame/1' as const,
    sequence: snapshot.sequence,
    filters: { domains, minimumThreat, limit },
    counts: {
      observed: snapshot.entityCount,
      eligible: eligible.length,
      included: included.length,
      truncated: Math.max(0, eligible.length - included.length),
      staleFeeds,
      byDomain,
      byThreat,
      byClassification,
      bySource,
    },
    lamps: {
      empty: included.length === 0,
      stale: staleFeeds > 0,
      critical: (byThreat[ThreatLevel.CRITICAL] ?? 0) > 0,
      unknownClassification: (byClassification[Classification.UNKNOWN] ?? 0) > 0,
      truncated: eligible.length > included.length,
      durableLocalState: options.persistence === 'append_only_wal',
    },
    persistence: {
      kind: options.persistence,
      diagnostics: options.persistenceDiagnostics,
    },
    entities: included,
    claimBoundary:
      'This read-only local cabinet frame contains derived observations only. It grants no command or operational authority.',
  };
  const stateId = digest('cistate1', semanticBody);
  const body = {
    ...semanticBody,
    stateId,
    snapshotId: snapshot.snapshotId,
    observedAt: snapshot.observedAt,
  };

  return { ...body, frameId: digest('ciframe1', body) };
}

export function verifyCommandIntelligenceCabinetFrame(
  frame: CommandIntelligenceCabinetFrame,
): boolean {
  const { frameId, ...body } = frame;
  return frameId === digest('ciframe1', body);
}
