import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { NextRequest } from 'next/server';
import {
  verifyCommandCandidateBinding,
  type CommandCandidateReceipt,
} from '@/lib/sdk/candidate';
import {
  getCommandIntelligenceServerState,
  resetCommandIntelligenceServerStateForTests,
} from '@/lib/sdk/serverState';
import type { CommandIntelligenceSnapshot } from '@/lib/sdk/snapshot';
import {
  Classification,
  Domain,
  EntityType,
  ThreatLevel,
} from '@/lib/sdk/types';
import { POST } from './route';

function request(
  body: Record<string, unknown>,
  key = 'candidate-fixture-key',
): NextRequest {
  return new NextRequest('http://localhost/api/sdk/candidate', {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      authorization: `Bearer ${key}`,
    },
    body: JSON.stringify(body),
  });
}

function seedObservation(): void {
  getCommandIntelligenceServerState().store.upsert({
    id: 'fixture-track-1',
    name: 'FIXTURE TRACK ONE',
    domain: Domain.AIR,
    entityType: EntityType.TRACK,
    position: { lat: 34.1478, lng: -118.1445, alt: 9144 },
    threat: ThreatLevel.LOW,
    classification: Classification.UNCLASSIFIED,
    source: { provider: 'fixture-provider', feed: 'fixture-feed', confidence: 1 },
    timestamp: new Date().toISOString(),
    properties: {},
    display: { color: '#00E5FF', icon: 'dot', layerType: 'circle' },
  });
}

beforeEach(() => {
  process.env.SDK_CANDIDATE_KEY = 'candidate-fixture-key';
  resetCommandIntelligenceServerStateForTests();
  seedObservation();
});

afterEach(() => {
  delete process.env.SDK_CANDIDATE_KEY;
  resetCommandIntelligenceServerStateForTests();
});

describe('Command Intelligence candidate transaction', () => {
  it('binds a candidate to the exact current snapshot without granting authority', async () => {
    const response = await POST(
      request({
        producer: 'command-core-fixture',
        actionClass: 'track-priority-candidate',
        staleAfterMs: 86_400_000,
        payload: {
          entityId: 'fixture-track-1',
          priority: 7,
          explanation: 'synthetic test candidate only',
        },
      }),
    );

    expect(response.status).toBe(201);
    expect(response.headers.get('cache-control')).toBe('no-store');
    const transaction = await response.json() as {
      schema: string;
      snapshot: CommandIntelligenceSnapshot;
      candidate: CommandCandidateReceipt;
      claimBoundary: string;
    };

    expect(transaction.schema).toBe('polybolos-command-candidate-transaction/1');
    expect(transaction.snapshot.entityCount).toBe(1);
    expect(transaction.candidate.snapshotId).toBe(transaction.snapshot.snapshotId);
    expect(verifyCommandCandidateBinding(transaction.candidate, transaction.snapshot)).toBe(true);
    expect(transaction.candidate.claimBoundary.toLowerCase()).toContain('no command authority');
    expect(transaction.claimBoundary.toLowerCase()).toContain('no command');

    const serialized = JSON.stringify(transaction).toLowerCase();
    for (const forbidden of [
      '"authorized":true',
      '"allow":true',
      '"execute":true',
      '"engagementauthority"',
      '"commandauthority"',
      '"effectorcommand"',
    ]) {
      expect(serialized).not.toContain(forbidden);
    }
  });

  it('is disabled until a separate candidate credential is configured', async () => {
    delete process.env.SDK_CANDIDATE_KEY;
    const response = await POST(
      request({
        producer: 'fixture',
        actionClass: 'fixture-candidate',
        payload: {},
      }),
    );
    expect(response.status).toBe(503);
    expect(await response.json()).toMatchObject({ error: 'CANDIDATE_ENDPOINT_DISABLED' });
  });

  it('rejects the ingest credential and any other unrecognized credential', async () => {
    process.env.SDK_INGEST_KEY = 'ingest-only-key';
    const response = await POST(
      request(
        {
          producer: 'fixture',
          actionClass: 'fixture-candidate',
          payload: {},
        },
        'ingest-only-key',
      ),
    );
    delete process.env.SDK_INGEST_KEY;
    expect(response.status).toBe(401);
    expect(await response.json()).toMatchObject({ error: 'CANDIDATE_AUTH_REQUIRED' });
  });

  it('rejects a non-object candidate payload', async () => {
    const response = await POST(
      request({
        producer: 'fixture',
        actionClass: 'fixture-candidate',
        payload: 'authorize me',
      }),
    );
    expect(response.status).toBe(400);
    expect(await response.json()).toMatchObject({
      error: 'candidate payload must be an object',
    });
  });

  it('rejects a candidate that predates the snapshot it cites', async () => {
    const response = await POST(
      request({
        producer: 'fixture',
        actionClass: 'fixture-candidate',
        createdAt: '2000-01-01T00:00:00.000Z',
        payload: {},
      }),
    );
    expect(response.status).toBe(400);
    expect(await response.json()).toMatchObject({
      error: 'candidate cannot predate the Command Intelligence snapshot it cites',
    });
  });
});
