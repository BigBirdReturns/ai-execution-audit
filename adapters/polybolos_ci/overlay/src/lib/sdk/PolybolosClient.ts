/**
 * Polybolos Command Intelligence client controller.
 *
 * Normalizes OSIRIS feeds and an optional Lattice adapter into one bounded
 * entity store. Feed snapshots replace their prior contents; missing source
 * identifiers receive deterministic fallback IDs; invalid coordinates are
 * refused instead of entering the Common Operating Picture.
 */

import {
  type PolybolosEntity,
  type PolybolosClientConfig,
  type SDKStatus,
  Domain,
  EntityType,
  ThreatLevel,
  Classification,
} from './types';
import { LatticeAdapter } from './LatticeAdapter';
import {
  isValidLatLng,
  normalizeTimestamp,
  sanitizeText,
  stableId,
  validEntityCoordinates,
} from './validation';

const THREAT_RANK: Record<ThreatLevel, number> = {
  [ThreatLevel.NONE]: 0,
  [ThreatLevel.LOW]: 1,
  [ThreatLevel.ELEVATED]: 2,
  [ThreatLevel.HIGH]: 3,
  [ThreatLevel.CRITICAL]: 4,
};

function observedAt(record: Record<string, unknown>): string {
  return (
    normalizeTimestamp(record.timestamp) ??
    normalizeTimestamp(record.last_seen) ??
    normalizeTimestamp(record.time) ??
    new Date().toISOString()
  );
}

export function translateFlights(flights: unknown, subtype: string): PolybolosEntity[] {
  if (!Array.isArray(flights)) return [];
  const colorMap: Record<string, string> = {
    commercial: '#00E5FF',
    private: '#00E676',
    jets: '#FF69B4',
    military: '#FF3D3D',
  };
  const threatMap: Record<string, ThreatLevel> = {
    commercial: ThreatLevel.NONE,
    private: ThreatLevel.NONE,
    jets: ThreatLevel.LOW,
    military: ThreatLevel.ELEVATED,
  };

  const result: PolybolosEntity[] = [];
  for (const raw of flights) {
    if (!raw || typeof raw !== 'object') continue;
    const f = raw as Record<string, unknown>;
    if (!isValidLatLng(f.lat, f.lng)) continue;
    const originalId = sanitizeText(f.icao24, 64) ?? sanitizeText(f.callsign, 64);
    const id = originalId
      ? `osiris-air-${originalId}`
      : stableId('osiris-air', [subtype, f.lat, f.lng, f.alt, f.registration, f.model]);
    result.push({
      id,
      name: sanitizeText(f.callsign, 160) ?? 'UNKNOWN',
      domain: Domain.AIR,
      entityType: EntityType.TRACK,
      position: {
        lat: f.lat,
        lng: f.lng,
        alt: typeof f.alt === 'number' && Number.isFinite(f.alt) ? f.alt : undefined,
        heading:
          typeof f.heading === 'number' && Number.isFinite(f.heading)
            ? f.heading
            : undefined,
        speed:
          typeof f.speed_knots === 'number' && Number.isFinite(f.speed_knots)
            ? f.speed_knots
            : undefined,
      },
      threat: threatMap[subtype] ?? ThreatLevel.NONE,
      classification: Classification.UNCLASSIFIED,
      source: {
        provider: 'osiris',
        feed: `flights-${subtype}`,
        originalId: originalId ?? undefined,
        confidence: 0.9,
      },
      timestamp: observedAt(f),
      properties: {
        model: f.model,
        registration: f.registration,
        icao24: f.icao24,
        subtype,
      },
      display: {
        color: colorMap[subtype] ?? '#00E5FF',
        icon: `plane-${subtype === 'military' ? 'red' : 'cyan'}`,
        layerType: 'symbol',
      },
    });
  }
  return result;
}

export function translateMaritime(ships: unknown): PolybolosEntity[] {
  if (!Array.isArray(ships)) return [];
  const result: PolybolosEntity[] = [];
  for (const raw of ships) {
    if (!raw || typeof raw !== 'object') continue;
    const s = raw as Record<string, unknown>;
    if (!isValidLatLng(s.lat, s.lng)) continue;
    const originalId = sanitizeText(s.mmsi, 64) ?? sanitizeText(s.id, 64);
    const id = originalId
      ? `osiris-sea-${originalId}`
      : stableId('osiris-sea', [s.lat, s.lng, s.name, s.flag, s.type]);
    const military = s.type === 'military';
    result.push({
      id,
      name: sanitizeText(s.name, 160) ?? (originalId ? `MMSI-${originalId}` : 'UNKNOWN'),
      domain: Domain.SEA,
      entityType: EntityType.TRACK,
      position: {
        lat: s.lat,
        lng: s.lng,
        heading:
          typeof s.heading === 'number' && Number.isFinite(s.heading)
            ? s.heading
            : undefined,
        speed:
          typeof s.speed === 'number' && Number.isFinite(s.speed) ? s.speed : undefined,
      },
      threat: military ? ThreatLevel.ELEVATED : ThreatLevel.NONE,
      classification: Classification.UNCLASSIFIED,
      source: {
        provider: 'osiris',
        feed: 'maritime-ais',
        originalId: originalId ?? undefined,
        confidence: 0.85,
      },
      timestamp: observedAt(s),
      properties: {
        type: s.type,
        destination: s.destination,
        flag: s.flag,
        mmsi: s.mmsi,
      },
      display: {
        color: military ? '#FF1744' : s.type === 'tanker' ? '#FF9500' : '#00BCD4',
        icon: 'dot-orange',
        layerType: 'circle',
      },
    });
  }
  return result;
}

export function translateEarthquakes(events: unknown): PolybolosEntity[] {
  if (!Array.isArray(events)) return [];
  const result: PolybolosEntity[] = [];
  for (const raw of events) {
    if (!raw || typeof raw !== 'object') continue;
    const eq = raw as Record<string, unknown>;
    if (!isValidLatLng(eq.lat, eq.lng)) continue;
    const magnitude =
      typeof eq.magnitude === 'number' && Number.isFinite(eq.magnitude)
        ? eq.magnitude
        : 0;
    const originalId = sanitizeText(eq.id, 120);
    result.push({
      id: originalId
        ? `osiris-event-eq-${originalId}`
        : stableId('osiris-event-eq', [eq.lat, eq.lng, magnitude, eq.place]),
      name: `M${magnitude} ${sanitizeText(eq.place, 160) ?? 'Earthquake'}`,
      domain: Domain.LAND,
      entityType: EntityType.EVENT,
      position: { lat: eq.lat, lng: eq.lng },
      threat:
        magnitude >= 6
          ? ThreatLevel.CRITICAL
          : magnitude >= 5
            ? ThreatLevel.HIGH
            : magnitude >= 4
              ? ThreatLevel.ELEVATED
              : ThreatLevel.LOW,
      classification: Classification.UNCLASSIFIED,
      source: {
        provider: 'osiris',
        feed: 'usgs-earthquakes',
        originalId: originalId ?? undefined,
        confidence: 0.99,
      },
      timestamp: observedAt(eq),
      properties: { magnitude, depth: eq.depth, place: eq.place },
      display: {
        color: magnitude >= 6 ? '#FF1744' : '#FF9500',
        icon: 'dot-red',
        layerType: 'circle',
        glow: magnitude >= 5,
      },
    });
  }
  return result;
}

export function translateSatellites(satellites: unknown): PolybolosEntity[] {
  if (!Array.isArray(satellites)) return [];
  const result: PolybolosEntity[] = [];
  for (const raw of satellites) {
    if (!raw || typeof raw !== 'object') continue;
    const s = raw as Record<string, unknown>;
    if (!isValidLatLng(s.lat, s.lng)) continue;
    const originalId = sanitizeText(s.noradId, 64);
    const altitudeKm =
      typeof s.alt === 'number' && Number.isFinite(s.alt) ? s.alt : undefined;
    result.push({
      id: originalId
        ? `osiris-space-${originalId}`
        : stableId('osiris-space', [s.lat, s.lng, s.name, s.mission]),
      name: sanitizeText(s.name, 160) ?? 'UNKNOWN SAT',
      domain: Domain.SPACE,
      entityType: EntityType.TRACK,
      position: {
        lat: s.lat,
        lng: s.lng,
        alt: altitudeKm === undefined ? undefined : altitudeKm * 1000,
      },
      threat: ThreatLevel.NONE,
      classification: Classification.UNCLASSIFIED,
      source: {
        provider: 'osiris',
        feed: 'satnogs',
        originalId: originalId ?? undefined,
        confidence: 0.95,
      },
      timestamp: observedAt(s),
      properties: { mission: s.mission, noradId: s.noradId, color: s.color },
      display: {
        color: sanitizeText(s.color, 32) ?? '#D4AF37',
        icon: 'dot-gold',
        layerType: 'circle',
      },
    });
  }
  return result;
}

export function translateFires(fires: unknown): PolybolosEntity[] {
  if (!Array.isArray(fires)) return [];
  const result: PolybolosEntity[] = [];
  for (const raw of fires) {
    if (!raw || typeof raw !== 'object') continue;
    const f = raw as Record<string, unknown>;
    if (!isValidLatLng(f.lat, f.lng)) continue;
    result.push({
      id: stableId('osiris-event-fire', [
        f.lat,
        f.lng,
        f.acq_date,
        f.acq_time,
        f.satellite,
      ]),
      name: 'Active Fire',
      domain: Domain.LAND,
      entityType: EntityType.EVENT,
      position: { lat: f.lat, lng: f.lng },
      threat: ThreatLevel.ELEVATED,
      classification: Classification.UNCLASSIFIED,
      source: { provider: 'osiris', feed: 'nasa-firms', confidence: 0.9 },
      timestamp: observedAt(f),
      properties: { brightness: f.brightness },
      display: {
        color: '#FF6B00',
        icon: 'dot-fire',
        layerType: 'circle',
      },
    });
  }
  return result;
}

export function translateCctv(cameras: unknown): PolybolosEntity[] {
  if (!Array.isArray(cameras)) return [];
  const result: PolybolosEntity[] = [];
  for (const raw of cameras) {
    if (!raw || typeof raw !== 'object') continue;
    const c = raw as Record<string, unknown>;
    if (!isValidLatLng(c.lat, c.lng)) continue;
    const originalId = sanitizeText(c.id, 120);
    result.push({
      id: originalId
        ? `osiris-sensor-cctv-${originalId}`
        : stableId('osiris-sensor-cctv', [c.lat, c.lng, c.name, c.source]),
      name: sanitizeText(c.name, 160) ?? 'Camera',
      domain: Domain.LAND,
      entityType: EntityType.SENSOR,
      position: { lat: c.lat, lng: c.lng },
      threat: ThreatLevel.NONE,
      classification: Classification.UNCLASSIFIED,
      source: {
        provider: 'osiris',
        feed: 'cctv-network',
        originalId: originalId ?? undefined,
        confidence: 1,
      },
      timestamp: observedAt(c),
      properties: {
        city: c.city,
        country: c.country,
        source: c.source,
        feed_url: c.feed_url,
        stream_url: c.stream_url,
      },
      display: {
        color: '#39FF14',
        icon: 'dot-cctv',
        layerType: 'circle',
      },
    });
  }
  return result;
}

export function translateRadiation(stations: unknown): PolybolosEntity[] {
  if (!Array.isArray(stations)) return [];
  const result: PolybolosEntity[] = [];
  for (const raw of stations) {
    if (!raw || typeof raw !== 'object') continue;
    const r = raw as Record<string, unknown>;
    if (!isValidLatLng(r.lat, r.lng)) continue;
    const status = sanitizeText(r.status, 32)?.toUpperCase() ?? 'NORMAL';
    result.push({
      id: stableId('osiris-sensor-rad', [r.name, r.lat, r.lng, r.network]),
      name: sanitizeText(r.name, 160) ?? 'Radiation Monitor',
      domain: Domain.LAND,
      entityType: EntityType.SENSOR,
      position: { lat: r.lat, lng: r.lng },
      threat:
        status === 'DANGER'
          ? ThreatLevel.CRITICAL
          : status === 'WARNING'
            ? ThreatLevel.HIGH
            : ThreatLevel.LOW,
      classification: Classification.UNCLASSIFIED,
      source: { provider: 'osiris', feed: 'radiation-network', confidence: 0.95 },
      timestamp: observedAt(r),
      properties: {
        reading: r.reading,
        status,
        network: r.network,
        city: r.city,
        country: r.country,
      },
      display: {
        color: status === 'DANGER' ? '#FF1744' : status === 'WARNING' ? '#FF9500' : '#AB47BC',
        icon: 'dot-red',
        layerType: 'circle',
        glow: status === 'DANGER',
      },
    });
  }
  return result;
}

export class PolybolosClient {
  private config: PolybolosClientConfig;
  private latticeAdapter: LatticeAdapter | null = null;
  private entityStore: Map<string, PolybolosEntity> = new Map();
  private activeFeeds = new Set<string>();
  private startTime = Date.now();
  private lastUpdate = new Date(this.startTime).toISOString();
  private sseConnection: EventSource | null = null;
  private sseState: 'idle' | 'connecting' | 'streaming' | 'error' = 'idle';

  constructor(config: PolybolosClientConfig) {
    this.config = config;
    if (config.lattice) this.latticeAdapter = new LatticeAdapter(config.lattice);
  }

  async initialize(): Promise<void> {
    if (this.latticeAdapter) await this.latticeAdapter.connect();
    this.connectSse();
    this.emitUpdate();
  }

  ingestOsirisData(data: Record<string, unknown>): void {
    this.replaceFeed('flights-commercial', translateFlights(data.commercial_flights, 'commercial'));
    this.replaceFeed('flights-private', translateFlights(data.private_flights, 'private'));
    this.replaceFeed('flights-jets', translateFlights(data.private_jets, 'jets'));
    this.replaceFeed('flights-military', translateFlights(data.military_flights, 'military'));
    this.replaceFeed('maritime-ais', translateMaritime(data.maritime_ships));
    this.replaceFeed('satnogs', translateSatellites(data.satellites));
    this.replaceFeed('usgs-earthquakes', translateEarthquakes(data.earthquakes));
    this.replaceFeed('nasa-firms', translateFires(data.fires));
    this.replaceFeed('cctv-network', translateCctv(data.cameras));
    this.replaceFeed('radiation-network', translateRadiation(data.radiation));

    if (this.latticeAdapter) {
      this.replaceProviderFeed(
        'anduril-lattice',
        'entity-stream',
        this.latticeAdapter.getEntities(),
      );
    }
    this.lastUpdate = new Date().toISOString();
    this.emitUpdate();
  }

  getEntities(domain?: Domain): PolybolosEntity[] {
    const all = Array.from(this.entityStore.values()).sort((a, b) => a.id.localeCompare(b.id));
    return domain ? all.filter((entity) => entity.domain === domain) : all;
  }

  getEntityCountByDomain(): Record<Domain, number> {
    const counts = {} as Record<Domain, number>;
    for (const domain of Object.values(Domain)) counts[domain] = 0;
    for (const entity of this.entityStore.values()) counts[entity.domain] += 1;
    return counts;
  }

  getThreats(minLevel: ThreatLevel = ThreatLevel.ELEVATED): PolybolosEntity[] {
    const minimum = THREAT_RANK[minLevel];
    return this.getEntities().filter((entity) => THREAT_RANK[entity.threat] >= minimum);
  }

  getStatus(): SDKStatus {
    const latticeStatus = this.latticeAdapter?.getStatus() ?? 'disconnected';
    return {
      connected: this.sseState === 'streaming' || latticeStatus === 'streaming',
      feedCount: this.activeFeeds.size,
      entityCount: this.entityStore.size,
      latticeStatus,
      lastUpdate: this.lastUpdate,
      uptime: Date.now() - this.startTime,
    };
  }

  toGeoJSON(domain?: Domain): GeoJSON.FeatureCollection {
    return {
      type: 'FeatureCollection',
      features: this.getEntities(domain)
        .filter(validEntityCoordinates)
        .map((entity) => ({
          type: 'Feature' as const,
          geometry: {
            type: 'Point' as const,
            coordinates: [entity.position.lng, entity.position.lat],
          },
          properties: {
            id: entity.id,
            name: entity.name,
            domain: entity.domain,
            entityType: entity.entityType,
            threat: entity.threat,
            color: entity.display.color,
            icon: entity.display.icon,
            heading: entity.position.heading ?? 0,
            alt: entity.position.alt,
            speed: entity.position.speed,
            glow: entity.display.glow ?? false,
            scale: entity.display.scale ?? 1,
            source: entity.source.provider,
            ...entity.properties,
          },
        })),
    };
  }

  destroy(): void {
    this.sseConnection?.close();
    this.sseConnection = null;
    this.sseState = 'idle';
    this.latticeAdapter?.disconnect();
    this.entityStore.clear();
    this.activeFeeds.clear();
  }

  private connectSse(): void {
    if (typeof EventSource === 'undefined' || !this.config.osirisBaseUrl) return;
    this.sseState = 'connecting';
    try {
      this.sseConnection = new EventSource(`${this.config.osirisBaseUrl}/api/sdk/stream`);
      this.sseConnection.onopen = () => {
        this.sseState = 'streaming';
        this.emitUpdate();
      };
      this.sseConnection.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as {
            type?: string;
            payload?: unknown;
          };
          if (data.type === 'entity_update' && Array.isArray(data.payload)) {
            for (const candidate of data.payload) {
              if (!candidate || typeof candidate !== 'object') continue;
              const entity = candidate as PolybolosEntity;
              if (!validEntityCoordinates(entity)) continue;
              this.entityStore.set(entity.id, entity);
              this.activeFeeds.add(`${entity.source.provider}:${entity.source.feed}`);
            }
            this.lastUpdate = new Date().toISOString();
            this.emitUpdate();
          } else if (data.type === 'entity_remove' && Array.isArray(data.payload)) {
            for (const removal of data.payload) {
              if (removal && typeof removal === 'object' && 'id' in removal) {
                this.entityStore.delete(String((removal as { id: unknown }).id));
              }
            }
            this.emitUpdate();
          }
        } catch {
          // Malformed events do not mutate the local COP.
        }
      };
      this.sseConnection.onerror = () => {
        this.sseState = 'error';
        this.emitUpdate();
      };
    } catch {
      this.sseState = 'error';
    }
  }

  private replaceFeed(feed: string, entities: PolybolosEntity[]): void {
    this.replaceProviderFeed('osiris', feed, entities);
  }

  private replaceProviderFeed(
    provider: string,
    feed: string,
    entities: PolybolosEntity[],
  ): void {
    const nextIds = new Set(entities.map((entity) => entity.id));
    for (const [id, existing] of this.entityStore.entries()) {
      if (
        existing.source.provider === provider &&
        existing.source.feed === feed &&
        !nextIds.has(id)
      ) {
        this.entityStore.delete(id);
      }
    }
    for (const entity of entities) {
      if (validEntityCoordinates(entity)) this.entityStore.set(entity.id, entity);
    }
    const key = provider === 'osiris' ? feed : `${provider}:${feed}`;
    if (entities.length > 0) this.activeFeeds.add(key);
    else this.activeFeeds.delete(key);
  }

  private emitUpdate(): void {
    this.config.onEntityUpdate?.(this.getEntities());
    this.config.onStatusChange?.(this.getStatus());
  }
}
