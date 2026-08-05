import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { NextRequest } from 'next/server';
import {
  verifyCheckpointCommandCandidateBinding,
  type CheckpointCommandCandidateTransaction,
} from '@/lib/sdk/boundedCandidate';
import {
  getCommandIntelligenceServerState,
  resetCommandIntelligenceServerStateForTests,
} from '@/lib/sdk/serverState';
import {
  Classification,
  Domain,
  EntityType,
  ThreatLevel,
} from '@/lib/sdk/types';
import { POST } from './route';

function request(body: Record<string, unknown>, key = 'candidate-fixture-key'): NextRequest {
  return new NextRequest('http://localhost/api/sdk/candidate/bounded', {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      authorization: `Bearer ${key}`,
    },
    body: JSON.stringify(body),
  });
}

function seed(count = 8): void {
  const entities = Array.from({ length: count }, (_, index) => ({
    id: `fixture-track-${index}`,
    name: `FIXTURE TRACK ${index}`,
    domain: Domain.AIR,
    entityType: EntityType.TRACK,
    position: { lat: 34 + index / 1_000, lng: -118 - index / 1_000 },
    threat: ThreatLevel.LOW,
    classification: Classification.UNCLASSIFIED,
    source: { provider: 'fixture-provider', feed: 'fixture-feed', confidence: 1 },
    timestamp: '2026-08-01T00:00:00.000Z',
    properties: {},
    display: { color: '#00E5FF', icon: 'dot', layerType: 'circle' as const },
  }));
  getCommandIntelligenceServerState().store.replaceFeed(
    'fixture-provider',
    'fixture-feed',
    entities,
    '2026-08-01T00:00:00.000Z',
  );
}

beforeEach(() => {
  process.env.SDK_CANDIDATE_KEY = 'candidate-fixture-key';
  process.env.CI_SOFTWARE_RECORD_ID = 'software-fixture-1';
  resetCommandIntelligenceServerStateForTests();
  seed();
});

afterEach(() => {
  delete process.env.SDK_CANDIDATE_KEY;
  delete process.env.CI_SOFTWARE_RECORD_ID;
  resetCommandIntelligenceServerStateForTests();
});

describe('bounded Command Intelligence candidate transaction', () => {
  it('binds a candidate to one checkpoint and exact entity witnesses', async () => {
    const body = {
      producer: 'command-core-fixture',
      actionClass: 'track-priority-candidate',
      staleAfterMs: 86_400_000,
      entityIds: ['fixture-track-7', 'fixture-track-0'],
      payload: {
        entityId: 'fixture-track-7',
        priority: 7,
        explanation: 'synthetic candidate only',
      },
    };
    const first = await POST(request(body));
    expect(first.status).toBe(201);
    expect(first.headers.get('x-ci-checkpoint-cache')).toBe('miss');
    const transaction = await first.json() as CheckpointCommandCandidateTransaction;
    expect(transaction.schema).toBe('polybolos-command-candidate-transaction/2');
    expect(transaction.checkpoint.entityCount).toBe(8);
    expect(transaction.witnesses).toHaveLength(2);
    expect(transaction.candidate.checkpointId).toBe(transaction.checkpoint.checkpointId);
    expect(transaction.candidate.evidence.map((row) => row.entityId)).toEqual([
      'fixture-track-0',
      'fixture-track-7',
    ]);
    expect(verifyCheckpointCommandCandidateBinding(transaction)).toBe(true);
    expect(JSON.stringify(transaction)).not.toContain('"entities":[');
    expect(Buffer.byteLength(JSON.stringify(transaction), 'utf8')).toBeLessThan(32 * 1024);

    const second = await POST(request(body));
    expect(second.status).toBe(201);
    expect(second.headers.get('x-ci-checkpoint-cache')).toBe('hit');
    expect(second.headers.get('x-ci-checkpoint-id')).toBe(transaction.checkpoint.checkpointId);
  });

  it('refuses unknown and duplicate entity references', async () => {
    const unknown = await POST(request({
      producer: 'fixture',
      actionClass: 'fixture-candidate',
      entityIds: ['missing-track'],
      payload: {},
    }));
    expect(unknown.status).toBe(409);
    expect(await unknown.json()).toMatchObject({
      error: 'CI_CHECKPOINT_ENTITY_NOT_FOUND: missing-track',
    });

    const duplicate = await POST(request({
      producer: 'fixture',
      actionClass: 'fixture-candidate',
      entityIds: ['fixture-track-0', 'fixture-track-0'],
      payload: {},
    }));
    expect(duplicate.status).toBe(400);
    expect(await duplicate.json()).toMatchObject({ error: 'entityIds must not contain duplicates' });
  });

  it('retains separate credentials and rejects candidate self-authorization', async () => {
    process.env.SDK_INGEST_KEY = 'ingest-only-key';
    const wrongCredential = await POST(request({
      producer: 'fixture',
      actionClass: 'fixture-candidate',
      entityIds: ['fixture-track-0'],
      payload: {},
    }, 'ingest-only-key'));
    delete process.env.SDK_INGEST_KEY;
    expect(wrongCredential.status).toBe(401);

    const authorityField = await POST(request({
      producer: 'fixture',
      actionClass: 'fixture-candidate',
      entityIds: ['fixture-track-0'],
      payload: { commandAuthority: true },
    }));
    expect(authorityField.status).toBe(400);
    expect((await authorityField.json()).error).toContain('may not carry authority field');
  });
});
