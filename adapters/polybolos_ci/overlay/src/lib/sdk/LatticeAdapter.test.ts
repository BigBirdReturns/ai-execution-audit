import { afterEach, describe, expect, it, vi } from 'vitest';
import { Classification } from './types';
import {
  LatticeAdapter,
  credentialFreeStreamUrl,
  type LatticeTrack,
} from './LatticeAdapter';

class FakeEventSource {
  static last: FakeEventSource | null = null;
  readonly url: string;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  closed = false;

  constructor(url: string | URL) {
    this.url = String(url);
    FakeEventSource.last = this;
  }

  close() {
    this.closed = true;
  }
}

function track(overrides: Partial<LatticeTrack> = {}): LatticeTrack {
  return {
    entityId: 'track-1',
    displayName: 'TRACK ONE',
    trackType: 'AIR',
    position: { latitude_deg: 34, longitude_deg: -118 },
    classification: 'SECRET',
    allegiance: 'HOSTILE',
    timestamp: '2026-07-31T12:00:00Z',
    ...overrides,
  };
}

afterEach(() => {
  FakeEventSource.last = null;
  vi.unstubAllGlobals();
});

describe('Command Intelligence Lattice adapter', () => {
  it('removes credential query parameters from browser stream URLs', () => {
    const url = credentialFreeStreamUrl(
      'https://example.test/stream?token=secret&access_token=also-secret&view=all',
    );
    expect(url).not.toContain('secret');
    expect(url).toContain('view=all');
  });

  it('does not claim authentication before the transport opens', async () => {
    vi.stubGlobal('EventSource', FakeEventSource as unknown as typeof EventSource);
    const states: string[] = [];
    const adapter = new LatticeAdapter({
      endpoint: 'https://example.test/stream?token=secret',
      token: 'must-not-enter-url',
      onStatusChange: (status) => states.push(status),
    });

    await adapter.connect();
    expect(adapter.getStatus()).toBe('connecting');
    expect(states).toEqual(['connecting']);
    expect(FakeEventSource.last?.url).not.toContain('secret');
    expect(FakeEventSource.last?.url).not.toContain('must-not-enter-url');

    FakeEventSource.last?.onopen?.({} as Event);
    expect(adapter.getStatus()).toBe('streaming');
  });

  it('preserves an admitted source classification', () => {
    const adapter = new LatticeAdapter({ endpoint: '/proxy/lattice', token: 'server-only' });
    const entity = adapter.ingestTrack(track());
    expect(entity.classification).toBe(Classification.SECRET);
  });

  it('rejects malformed geographic state', () => {
    const adapter = new LatticeAdapter({ endpoint: '/proxy/lattice', token: 'server-only' });
    expect(() =>
      adapter.ingestTrack(
        track({ position: { latitude_deg: 120, longitude_deg: -118 } }),
      ),
    ).toThrow(/invalid coordinates/);
  });
});
