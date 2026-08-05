import type { PolybolosEntity, SDKStatus } from './types';

export interface IngestLogEntry {
  source: string;
  count: number;
  rejected: number;
  timestamp: string;
}

export interface PolybolosSdkStore {
  entities: Map<string, PolybolosEntity>;
  lastUpdate: number;
  version: number;
  startedAt: number;
  ingestLog: IngestLogEntry[];
}

const globalForSdk = globalThis as typeof globalThis & {
  __polybolosSdkStore?: PolybolosSdkStore;
};

function createStore(): PolybolosSdkStore {
  const now = Date.now();
  return {
    entities: new Map<string, PolybolosEntity>(),
    lastUpdate: now,
    version: 0,
    startedAt: now,
    ingestLog: [],
  };
}

export function getSdkStore(): PolybolosSdkStore {
  if (!globalForSdk.__polybolosSdkStore) {
    globalForSdk.__polybolosSdkStore = createStore();
  }
  return globalForSdk.__polybolosSdkStore;
}

export function resetSdkStoreForTests(): PolybolosSdkStore {
  globalForSdk.__polybolosSdkStore = createStore();
  return globalForSdk.__polybolosSdkStore;
}

export function activeFeedCount(store = getSdkStore()): number {
  const feeds = new Set<string>();
  for (const entity of store.entities.values()) {
    feeds.add(`${entity.source.provider}:${entity.source.feed}`);
  }
  return feeds.size;
}

export function latticeStatus(
  store = getSdkStore(),
): SDKStatus['latticeStatus'] {
  for (const entity of store.entities.values()) {
    if (entity.source.provider === 'anduril-lattice') return 'streaming';
  }
  return 'disconnected';
}

export function buildSdkStatus(store = getSdkStore()): SDKStatus {
  return {
    connected: true,
    feedCount: activeFeedCount(store),
    entityCount: store.entities.size,
    latticeStatus: latticeStatus(store),
    lastUpdate: new Date(store.lastUpdate).toISOString(),
    uptime: Date.now() - store.startedAt,
  };
}

export function orderedEntities(store = getSdkStore()): PolybolosEntity[] {
  return Array.from(store.entities.values()).sort((a, b) => a.id.localeCompare(b.id));
}

export function chunkEntities(
  entities: PolybolosEntity[],
  batchSize = 500,
): PolybolosEntity[][] {
  if (!Number.isInteger(batchSize) || batchSize < 1 || batchSize > 5000) {
    throw new RangeError('batchSize must be an integer between 1 and 5000');
  }
  const batches: PolybolosEntity[][] = [];
  for (let offset = 0; offset < entities.length; offset += batchSize) {
    batches.push(entities.slice(offset, offset + batchSize));
  }
  return batches;
}

export function recordIngest(
  source: string,
  accepted: number,
  rejected: number,
  store = getSdkStore(),
): void {
  if (accepted > 0) {
    store.version += 1;
    store.lastUpdate = Date.now();
  }
  store.ingestLog.push({
    source,
    count: accepted,
    rejected,
    timestamp: new Date().toISOString(),
  });
  if (store.ingestLog.length > 100) {
    store.ingestLog.splice(0, store.ingestLog.length - 100);
  }
}
