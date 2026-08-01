import { describe, expect, it } from 'vitest';
import {
  projectCommandIntelligenceCabinetFrame,
  verifyCommandIntelligenceCabinetFrame,
} from './cabinetProjection';
import {
  Classification,
  Domain,
  EntityType,
  ThreatLevel,
  type PolybolosEntity,
} from './types';
import type { CommandIntelligenceSnapshot } from './snapshot';

function entity(
  id: string,
  threat: ThreatLevel,
  domain = Domain.AIR,
  classification = Classification.UNCLASSIFIED,
): PolybolosEntity {
  return {
    id,
    name: id,
    domain,
    entityType: EntityType.TRACK,
    position: { lat: 34, lng: -118 },
    threat,
    classification,
    source: { provider: 'fixture', feed: 'tracks', confidence: 1 },
    timestamp: '2026-08-01T00:00:00.000Z',
    properties: { forbidden_action_hint: 'retained only outside cabinet projection' },
    display: { color: '#FF1744', icon: 'dot', layerType: 'circle' },
  };
}

function snapshot(): CommandIntelligenceSnapshot {
  const entities = [
    entity('low', ThreatLevel.LOW),
    entity('critical-b', ThreatLevel.CRITICAL, Domain.SEA),
    entity('critical-a', ThreatLevel.CRITICAL, Domain.AIR, Classification.UNKNOWN),
    entity('high', ThreatLevel.HIGH),
  ];
  return {
    schema: 'polybolos-command-intelligence-snapshot/1',
    snapshotId: 'ci1_fixture',
    sequence: 4,
    observedAt: '2026-08-01T00:00:01.000Z',
    entityCount: entities.length,
    feeds: [
      {
        provider: 'fixture',
        feed: 'tracks',
        entityCount: entities.length,
        lastUpdate: '2026-08-01T00:00:00.000Z',
        stale: true,
      },
    ],
    entities,
    claimBoundary: 'fixture',
  };
}

describe('Command Intelligence cabinet projection', () => {
  it('is deterministic, bounded, and threat ordered', () => {
    const options = {
      minimumThreat: ThreatLevel.HIGH,
      limit: 2,
      persistence: 'append_only_wal' as const,
      persistenceDiagnostics: { durable: true },
    };
    const first = projectCommandIntelligenceCabinetFrame(snapshot(), options);
    const second = projectCommandIntelligenceCabinetFrame(snapshot(), options);
    expect(first).toEqual(second);
    expect(first.entities.map((row) => row.id)).toEqual(['critical-a', 'critical-b']);
    expect(first.counts).toMatchObject({ eligible: 3, included: 2, truncated: 1 });
    expect(first.lamps).toMatchObject({
      stale: true,
      critical: true,
      unknownClassification: true,
      truncated: true,
      durableLocalState: true,
    });
    expect(verifyCommandIntelligenceCabinetFrame(first)).toBe(true);
  });

  it('projects no arbitrary properties or action-like fields', () => {
    const frame = projectCommandIntelligenceCabinetFrame(snapshot(), {
      limit: 10,
      persistence: 'process_memory',
      persistenceDiagnostics: { durable: false },
    });
    expect(JSON.stringify(frame.entities)).not.toContain('forbidden_action_hint');
    for (const projected of frame.entities) {
      for (const forbidden of [
        'properties',
        'display',
        'action',
        'effector',
        'engagement',
        'targeting',
      ]) {
        expect(projected).not.toHaveProperty(forbidden);
      }
    }
    expect(frame.claimBoundary).toContain('no command');
  });

  it('separates capture identity from stable semantic state', () => {
    const firstSnapshot = snapshot();
    const secondSnapshot = {
      ...snapshot(),
      snapshotId: 'ci1_second_capture',
      observedAt: '2026-08-01T00:00:02.000Z',
    };
    const options = {
      limit: 10,
      persistence: 'process_memory' as const,
      persistenceDiagnostics: { durable: false },
    };
    const first = projectCommandIntelligenceCabinetFrame(firstSnapshot, options);
    const second = projectCommandIntelligenceCabinetFrame(secondSnapshot, options);
    expect(first.stateId).toBe(second.stateId);
    expect(first.frameId).not.toBe(second.frameId);
  });

  it('detects frame tampering', () => {
    const frame = projectCommandIntelligenceCabinetFrame(snapshot(), {
      limit: 10,
      persistence: 'process_memory',
      persistenceDiagnostics: {},
    });
    frame.entities[0].name = 'changed';
    expect(verifyCommandIntelligenceCabinetFrame(frame)).toBe(false);
  });

  it('rejects an unbounded limit', () => {
    expect(() =>
      projectCommandIntelligenceCabinetFrame(snapshot(), {
        limit: 5001,
        persistence: 'process_memory',
        persistenceDiagnostics: {},
      }),
    ).toThrow(/between 1 and 5000/);
  });
});
