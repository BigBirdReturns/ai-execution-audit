import { describe, expect, it } from 'vitest';
import { CommandIntelligenceStore } from './entityStore';
import { deriveStableObservationAt } from './snapshot';
import {
  Classification,
  Domain,
  EntityType,
  ThreatLevel,
  type PolybolosEntity,
} from './types';

function entity(timestamp: string): PolybolosEntity {
  return {
    id: 'track-1',
    name: 'TRACK ONE',
    domain: Domain.AIR,
    entityType: EntityType.TRACK,
    position: { lat: 34, lng: -118 },
    threat: ThreatLevel.LOW,
    classification: Classification.UNCLASSIFIED,
    source: { provider: 'fixture', feed: 'tracks', confidence: 1 },
    timestamp,
    properties: {},
    display: { color: '#00E5FF', icon: 'dot', layerType: 'circle' },
  };
}

describe('stable Command Intelligence observation time', () => {
  it('is stable between mutations and advances exactly at stale transition', () => {
    const store = new CommandIntelligenceStore();
    const floorMs = Date.parse('2026-08-01T00:00:00.000Z');
    const updateMs = floorMs + 1_000;
    const staleAfterMs = 5_000;

    expect(
      deriveStableObservationAt(store, staleAfterMs, floorMs + 500, floorMs),
    ).toBe('2026-08-01T00:00:00.000Z');

    store.upsert(entity(new Date(updateMs).toISOString()));
    expect(
      deriveStableObservationAt(store, staleAfterMs, updateMs + 4_000, floorMs),
    ).toBe(new Date(updateMs).toISOString());
    expect(
      deriveStableObservationAt(store, staleAfterMs, updateMs + staleAfterMs + 1, floorMs),
    ).toBe(new Date(updateMs + staleAfterMs + 1).toISOString());
    expect(
      deriveStableObservationAt(store, staleAfterMs, updateMs + staleAfterMs + 4_000, floorMs),
    ).toBe(new Date(updateMs + staleAfterMs + 1).toISOString());
  });

  it('does not let a later process start manufacture a new non-stale state', () => {
    const store = new CommandIntelligenceStore();
    const updateMs = Date.parse('2026-08-01T00:00:00.000Z');
    const staleAfterMs = 300_000;
    store.upsert(entity(new Date(updateMs).toISOString()));

    const beforeRestart = deriveStableObservationAt(
      store,
      staleAfterMs,
      updateMs + 10_000,
      updateMs - 1_000,
    );
    const afterRestart = deriveStableObservationAt(
      store,
      staleAfterMs,
      updateMs + 120_000,
      updateMs + 120_000,
    );
    expect(beforeRestart).toBe(new Date(updateMs).toISOString());
    expect(afterRestart).toBe(beforeRestart);
  });

  it('still advances to the one exact stale transition after restart', () => {
    const store = new CommandIntelligenceStore();
    const updateMs = Date.parse('2026-08-01T00:00:00.000Z');
    const staleAfterMs = 5_000;
    store.upsert(entity(new Date(updateMs).toISOString()));

    const afterRestartAndStale = deriveStableObservationAt(
      store,
      staleAfterMs,
      updateMs + 60_000,
      updateMs + 60_000,
    );
    expect(afterRestartAndStale).toBe(
      new Date(updateMs + staleAfterMs + 1).toISOString(),
    );
  });

  it('rejects invalid clocks', () => {
    const store = new CommandIntelligenceStore();
    expect(() => deriveStableObservationAt(store, -1, 0, 0)).toThrow(/staleAfterMs/);
    expect(() => deriveStableObservationAt(store, 1000, Number.NaN, 0)).toThrow(/finite clocks/);
  });
});
