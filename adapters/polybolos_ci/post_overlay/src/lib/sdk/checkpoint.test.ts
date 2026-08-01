import { describe, expect, it } from 'vitest';
import { CommandIntelligenceStore } from './entityStore';
import {
  deriveCheckpointId,
  deriveEntityWitnessId,
  getCommandIntelligenceCheckpoint,
  verifyEntityWitness,
} from './checkpoint';
import {
  Classification,
  Domain,
  EntityType,
  ThreatLevel,
  type PolybolosEntity,
} from './types';

function entity(index: number): PolybolosEntity {
  return {
    id: `fixture-${String(index).padStart(4, '0')}`,
    name: `FIXTURE ${index}`,
    domain: Domain.AIR,
    entityType: EntityType.TRACK,
    position: { lat: 34 + index / 10_000, lng: -118 - index / 10_000 },
    threat: ThreatLevel.LOW,
    classification: Classification.UNCLASSIFIED,
    source: { provider: 'fixture-provider', feed: 'fixture-feed', confidence: 1 },
    timestamp: '2026-08-01T00:00:00.000Z',
    properties: { fixtureIndex: index },
    display: { color: '#00E5FF', icon: 'dot', layerType: 'circle' },
  };
}

function storeWith(count: number): CommandIntelligenceStore {
  const store = new CommandIntelligenceStore();
  store.replaceFeed(
    'fixture-provider',
    'fixture-feed',
    Array.from({ length: count }, (_, index) => entity(index)),
    '2026-08-01T00:00:00.000Z',
  );
  return store;
}

describe('Command Intelligence checkpoint and entity witness', () => {
  it('commits an odd-sized sorted entity set and verifies every witness', () => {
    const store = storeWith(5);
    const compiled = getCommandIntelligenceCheckpoint(
      store,
      '2026-08-01T00:00:00.000Z',
      86_400_000,
      'software-fixture-1',
    );
    expect(compiled.cache).toBe('miss');
    expect(compiled.checkpoint.entityCount).toBe(5);
    expect(compiled.checkpoint.checkpointId).toBe(deriveCheckpointId(compiled.checkpoint));
    expect(compiled.checkpoint.entityRoot).toMatch(/^[0-9a-f]{64}$/);

    for (let index = 0; index < 5; index += 1) {
      const witness = compiled.witness(entity(index).id);
      expect(witness.witnessId).toBe(deriveEntityWitnessId(witness));
      expect(verifyEntityWitness(compiled.checkpoint, witness)).toBe(true);
    }
  });

  it('reuses one semantic checkpoint and invalidates it after store mutation', () => {
    const store = storeWith(3);
    const first = getCommandIntelligenceCheckpoint(
      store,
      '2026-08-01T00:00:00.000Z',
      86_400_000,
      'software-fixture-1',
    );
    const second = getCommandIntelligenceCheckpoint(
      store,
      '2026-08-01T00:00:00.000Z',
      86_400_000,
      'software-fixture-1',
    );
    expect(second.cache).toBe('hit');
    expect(second.checkpoint.checkpointId).toBe(first.checkpoint.checkpointId);

    store.upsert(entity(9), '2026-08-01T00:00:01.000Z');
    const changed = getCommandIntelligenceCheckpoint(
      store,
      '2026-08-01T00:00:01.000Z',
      86_400_000,
      'software-fixture-1',
    );
    expect(changed.cache).toBe('miss');
    expect(changed.checkpoint.checkpointId).not.toBe(first.checkpoint.checkpointId);
    expect(changed.checkpoint.entityCount).toBe(4);
  });

  it('refuses tampered entities, paths, roots, and checkpoint identities', () => {
    const store = storeWith(4);
    const compiled = getCommandIntelligenceCheckpoint(
      store,
      '2026-08-01T00:00:00.000Z',
      86_400_000,
      'software-fixture-1',
    );
    const witness = compiled.witness(entity(2).id);

    const changedEntity = structuredClone(witness);
    changedEntity.entity.name = 'ALTERED';
    expect(verifyEntityWitness(compiled.checkpoint, changedEntity)).toBe(false);

    const changedPath = structuredClone(witness);
    changedPath.siblings[0].hash = '0'.repeat(64);
    changedPath.witnessId = deriveEntityWitnessId(changedPath);
    expect(verifyEntityWitness(compiled.checkpoint, changedPath)).toBe(false);

    const changedRoot = structuredClone(compiled.checkpoint);
    changedRoot.entityRoot = '1'.repeat(64);
    changedRoot.checkpointId = deriveCheckpointId(changedRoot);
    expect(verifyEntityWitness(changedRoot, witness)).toBe(false);

    const changedCheckpointId = structuredClone(compiled.checkpoint);
    changedCheckpointId.checkpointId = `checkpoint1_${'f'.repeat(64)}`;
    expect(verifyEntityWitness(changedCheckpointId, witness)).toBe(false);
  });

  it('keeps a 5,000-entity witness logarithmic and bounded', () => {
    const store = storeWith(5_000);
    const compiled = getCommandIntelligenceCheckpoint(
      store,
      '2026-08-01T00:00:00.000Z',
      86_400_000,
      'software-fixture-1',
    );
    const witness = compiled.witness('fixture-4999');
    expect(witness.siblings.length).toBeLessThanOrEqual(13);
    expect(verifyEntityWitness(compiled.checkpoint, witness)).toBe(true);
    expect(Buffer.byteLength(JSON.stringify(witness), 'utf8')).toBeLessThan(16 * 1024);
  });
});
