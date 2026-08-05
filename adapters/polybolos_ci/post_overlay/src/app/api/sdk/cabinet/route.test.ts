import { beforeEach, describe, expect, it } from 'vitest';
import { NextRequest } from 'next/server';
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
import { GET } from './route';

beforeEach(() => {
  resetCommandIntelligenceServerStateForTests();
});

describe('GET /api/sdk/cabinet', () => {
  it('returns a verified read-only frame from the actual CI store', async () => {
    const state = getCommandIntelligenceServerState();
    state.store.upsert({
      id: 'track-1',
      name: 'TRACK ONE',
      domain: Domain.AIR,
      entityType: EntityType.TRACK,
      position: { lat: 34, lng: -118 },
      threat: ThreatLevel.CRITICAL,
      classification: Classification.SECRET,
      source: { provider: 'fixture', feed: 'tracks', confidence: 1 },
      timestamp: new Date().toISOString(),
      properties: { action: 'must not cross projection' },
      display: { color: '#FF1744', icon: 'dot', layerType: 'circle' },
    });

    const response = await GET(
      new NextRequest(
        'http://localhost/api/sdk/cabinet?domains=AIR&minimumThreat=HIGH&limit=10',
      ),
    );
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.schema).toBe('polybolos-command-intelligence-cabinet-frame/1');
    expect(body.entities).toHaveLength(1);
    expect(JSON.stringify(body)).not.toContain('must not cross projection');
    expect(response.headers.get('etag')).toContain(body.stateId);
  });

  it('honors weak, multiple, and wildcard If-None-Match validators', async () => {
    const first = await GET(new NextRequest('http://localhost/api/sdk/cabinet'));
    const etag = first.headers.get('etag');
    expect(etag).toBeTruthy();
    const second = await GET(
      new NextRequest('http://localhost/api/sdk/cabinet', {
        headers: { 'if-none-match': `"unrelated", ${etag ?? ''}` },
      }),
    );
    expect(second.status).toBe(304);

    const wildcard = await GET(
      new NextRequest('http://localhost/api/sdk/cabinet', {
        headers: { 'if-none-match': '*' },
      }),
    );
    expect(wildcard.status).toBe(304);
  });

  it('rejects unsupported filters', async () => {
    const response = await GET(
      new NextRequest('http://localhost/api/sdk/cabinet?domains=AIR,INVENTED&limit=9000'),
    );
    expect(response.status).toBe(400);
    expect(await response.json()).toMatchObject({
      schema: 'polybolos-command-intelligence-cabinet-error/1',
    });
  });
});
