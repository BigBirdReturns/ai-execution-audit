import { beforeEach, describe, expect, it } from 'vitest';
import {
  activeFeedCount,
  buildSdkStatus,
  chunkEntities,
  getSdkStore,
  resetSdkStoreForTests,
} from './serverStore';
import {
  Classification,
  Domain,
  EntityType,
  ThreatLevel,
  type PolybolosEntity,
} from './types';

function entity(id: string, provider = 'osiris', feed = 'fixture'): PolybolosEntity {
  return {
    id,
    name: id,
    domain: Domain.LAND,
    entityType: EntityType.TRACK,
    position: { lat: 0, lng: 0 },
    threat: ThreatLevel.NONE,
    classification: Classification.UNCLASSIFIED,
    source: { provider, feed, confidence: 1 },
    timestamp: '2026-07-31T12:00:00.000Z',
    properties: {},
    display: { color: '#fff', icon: 'dot', layerType: 'circle' },
  };
}

beforeEach(() => {
  resetSdkStoreForTests();
});

describe('Command Intelligence server store', () => {
  it('counts distinct source/feed pairs rather than inventing nine active feeds', () => {
    const store = getSdkStore();
    store.entities.set('a', entity('a', 'osiris', 'air'));
    store.entities.set('b', entity('b', 'osiris', 'air'));
    store.entities.set('c', entity('c', 'osiris', 'sea'));
    expect(activeFeedCount(store)).toBe(2);
    expect(buildSdkStatus(store).feedCount).toBe(2);
  });

  it('batches a complete snapshot without dropping records after 500', () => {
    const rows = Array.from({ length: 1201 }, (_, index) => entity(`entity-${index}`));
    const batches = chunkEntities(rows, 500);
    expect(batches.map((batch) => batch.length)).toEqual([500, 500, 201]);
    expect(batches.flat().map((row) => row.id)).toEqual(rows.map((row) => row.id));
  });

  it('rejects invalid batch sizes', () => {
    expect(() => chunkEntities([], 0)).toThrow(/batchSize/);
    expect(() => chunkEntities([], 5001)).toThrow(/batchSize/);
  });
});
