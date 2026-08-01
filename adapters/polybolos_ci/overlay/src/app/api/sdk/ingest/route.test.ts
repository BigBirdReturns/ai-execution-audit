import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { NextRequest } from 'next/server';
import { resetSdkStoreForTests, getSdkStore } from '@/lib/sdk/serverStore';
import { POST } from './route';

function request(
  body: Record<string, unknown>,
  key = 'fixture-key',
): NextRequest {
  return new NextRequest('http://localhost/api/sdk/ingest', {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      authorization: `Bearer ${key}`,
    },
    body: JSON.stringify(body),
  });
}

beforeEach(() => {
  process.env.SDK_INGEST_KEY = 'fixture-key';
  resetSdkStoreForTests();
});

afterEach(() => {
  delete process.env.SDK_INGEST_KEY;
});

describe('Command Intelligence external ingest', () => {
  it('accepts valid zero-valued coordinates', async () => {
    const response = await POST(
      request({
        source: 'fixture-source',
        entities: [{ id: 'origin', position: { lat: 0, lng: 0 } }],
      }),
    );
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ accepted: 1, rejected: 0 });
    expect(getSdkStore().entities.get('ext-fixture-source-origin')?.position).toEqual({
      lat: 0,
      lng: 0,
      alt: undefined,
      heading: undefined,
      speed: undefined,
    });
  });

  it('rejects invalid geographic state and enum values', async () => {
    const response = await POST(
      request({
        source: 'fixture-source',
        entities: [
          { id: 'bad-lat', position: { lat: 91, lng: 0 } },
          {
            id: 'bad-classification',
            position: { lat: 1, lng: 1 },
            classification: 'COSMIC_TOP_SECRET',
          },
        ],
      }),
    );
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ accepted: 0, rejected: 2 });
    expect(getSdkStore().entities.size).toBe(0);
  });

  it('rejects unbounded source identifiers', async () => {
    const response = await POST(
      request({
        source: '../escape',
        entities: [{ id: 'a', position: { lat: 1, lng: 1 } }],
      }),
    );
    expect(response.status).toBe(400);
    expect(await response.json()).toMatchObject({ accepted: 0 });
  });

  it('rejects oversized batches before mutation', async () => {
    const entities = Array.from({ length: 5001 }, (_, index) => ({
      id: `entity-${index}`,
      position: { lat: 1, lng: 1 },
    }));
    const response = await POST(request({ source: 'fixture', entities }));
    expect(response.status).toBe(413);
    expect(getSdkStore().entities.size).toBe(0);
  });

  it('rejects invalid credentials', async () => {
    const response = await POST(
      request(
        {
          source: 'fixture',
          entities: [{ id: 'a', position: { lat: 1, lng: 1 } }],
        },
        'wrong-key',
      ),
    );
    expect(response.status).toBe(401);
    expect(getSdkStore().entities.size).toBe(0);
  });
});
