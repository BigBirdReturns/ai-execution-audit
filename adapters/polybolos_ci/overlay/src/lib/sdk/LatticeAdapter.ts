/**
 * Polybolos Command Intelligence — Lattice entity adapter.
 *
 * The browser adapter accepts a credential-free SSE endpoint, normally a
 * same-origin server proxy. It never places bearer tokens in URLs. Direct
 * production Lattice authentication belongs on the server side or in a native
 * client that can set authenticated transport headers.
 */

import {
  type PolybolosEntity,
  type LatticeConfig,
  type LatticeConnectionStatus,
  Domain,
  EntityType,
  ThreatLevel,
  Classification,
} from './types';
import {
  isClassification,
  isValidLatLng,
  normalizeTimestamp,
  sanitizeText,
} from './validation';

export interface LatticeTrack {
  entityId: string;
  displayName?: string;
  trackType: string;
  position: {
    latitude_deg: number;
    longitude_deg: number;
    altitude_hae_m?: number;
  };
  kinematics?: {
    speed_mps?: number;
    heading_deg?: number;
  };
  classification?: string;
  allegiance?: string;
  timestamp?: string;
  metadata?: Record<string, string>;
}

const LATTICE_DOMAIN_MAP: Record<string, Domain> = {
  AIR: Domain.AIR,
  SURFACE: Domain.SEA,
  SUBSURFACE: Domain.SUBSURFACE,
  SPACE: Domain.SPACE,
  LAND: Domain.LAND,
};

const ALLEGIANCE_THREAT_MAP: Record<string, ThreatLevel> = {
  HOSTILE: ThreatLevel.CRITICAL,
  SUSPECT: ThreatLevel.HIGH,
  UNKNOWN: ThreatLevel.ELEVATED,
  NEUTRAL: ThreatLevel.LOW,
  FRIENDLY: ThreatLevel.NONE,
};

const ALLEGIANCE_COLOR_MAP: Record<string, string> = {
  HOSTILE: '#FF1744',
  SUSPECT: '#FF9500',
  UNKNOWN: '#FFD700',
  NEUTRAL: '#00BCD4',
  FRIENDLY: '#00E676',
};

const THREAT_RANK: Record<ThreatLevel, number> = {
  [ThreatLevel.NONE]: 0,
  [ThreatLevel.LOW]: 1,
  [ThreatLevel.ELEVATED]: 2,
  [ThreatLevel.HIGH]: 3,
  [ThreatLevel.CRITICAL]: 4,
};

const CREDENTIAL_QUERY_KEYS = new Set([
  'token',
  'access_token',
  'api_key',
  'apikey',
  'authorization',
  'auth',
]);

export function credentialFreeStreamUrl(endpoint: string): string {
  const base = typeof window === 'undefined' ? 'http://localhost' : window.location.origin;
  const url = new URL(endpoint, base);
  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    throw new Error(`unsupported Lattice stream protocol: ${url.protocol}`);
  }
  for (const key of Array.from(url.searchParams.keys())) {
    if (CREDENTIAL_QUERY_KEYS.has(key.toLowerCase())) url.searchParams.delete(key);
  }
  return url.toString();
}

export class LatticeAdapter {
  private config: LatticeConfig;
  private status: LatticeConnectionStatus = 'disconnected';
  private entityBuffer: Map<string, PolybolosEntity> = new Map();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private eventSource: EventSource | null = null;
  private reconnectDelayMs = 1000;

  constructor(config: LatticeConfig) {
    this.config = config;
  }

  getStatus(): LatticeConnectionStatus {
    return this.status;
  }

  getEntities(): PolybolosEntity[] {
    return Array.from(this.entityBuffer.values()).sort((a, b) => a.id.localeCompare(b.id));
  }

  getEntityCount(): number {
    return this.entityBuffer.size;
  }

  async connect(): Promise<void> {
    this.disconnectTransportOnly();

    if (!this.config.endpoint || typeof EventSource === 'undefined') {
      this.setStatus('disconnected');
      return;
    }

    let streamUrl: string;
    try {
      streamUrl = credentialFreeStreamUrl(this.config.endpoint);
    } catch {
      this.setStatus('error');
      return;
    }

    this.setStatus('connecting');
    try {
      this.eventSource = new EventSource(streamUrl);
      this.eventSource.onopen = () => {
        this.reconnectDelayMs = 1000;
        this.setStatus('streaming');
      };
      this.eventSource.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data) as LatticeTrack | { payload?: LatticeTrack };
          const track = 'payload' in parsed && parsed.payload ? parsed.payload : (parsed as LatticeTrack);
          this.ingestTrack(track);
        } catch {
          // A malformed record contributes no entity and no authority.
        }
      };
      this.eventSource.onerror = () => {
        this.setStatus('error');
        this.disconnectTransportOnly();
        this.scheduleReconnect();
      };
    } catch {
      this.setStatus('error');
      this.scheduleReconnect();
    }
  }

  disconnect(): void {
    this.disconnectTransportOnly();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.entityBuffer.clear();
    this.setStatus('disconnected');
  }

  ingestTrack(track: LatticeTrack): PolybolosEntity {
    const entity = this.translateTrack(track);
    this.entityBuffer.set(entity.id, entity);
    return entity;
  }

  translateTrack(track: LatticeTrack): PolybolosEntity {
    const entityId = sanitizeText(track?.entityId, 160);
    if (!entityId) throw new Error('Lattice track missing a bounded entityId');
    if (!track.position || !isValidLatLng(
      track.position.latitude_deg,
      track.position.longitude_deg,
    )) {
      throw new Error(`Lattice track ${entityId} has invalid coordinates`);
    }

    const trackType = sanitizeText(track.trackType, 32)?.toUpperCase() ?? 'LAND';
    const domain = LATTICE_DOMAIN_MAP[trackType] ?? Domain.LAND;
    const allegiance = sanitizeText(track.allegiance, 32)?.toUpperCase() ?? 'UNKNOWN';
    const threat = ALLEGIANCE_THREAT_MAP[allegiance] ?? ThreatLevel.ELEVATED;
    const color = ALLEGIANCE_COLOR_MAP[allegiance] ?? '#FFD700';
    const rawClassification = sanitizeText(track.classification, 32)?.toUpperCase();
    const classification = isClassification(rawClassification)
      ? rawClassification
      : Classification.UNCLASSIFIED;

    let icon = 'dot-gold';
    if (domain === Domain.AIR) icon = 'plane-cyan';
    else if (domain === Domain.SEA) icon = 'dot-orange';

    return {
      id: `lattice-${entityId}`,
      name: sanitizeText(track.displayName, 160) ?? `TRACK-${entityId.slice(0, 8)}`,
      domain,
      entityType: EntityType.TRACK,
      position: {
        lat: track.position.latitude_deg,
        lng: track.position.longitude_deg,
        alt: Number.isFinite(track.position.altitude_hae_m)
          ? track.position.altitude_hae_m
          : undefined,
        heading: Number.isFinite(track.kinematics?.heading_deg)
          ? track.kinematics?.heading_deg
          : undefined,
        speed: Number.isFinite(track.kinematics?.speed_mps)
          ? (track.kinematics?.speed_mps as number) * 1.94384
          : undefined,
      },
      threat,
      classification,
      source: {
        provider: 'anduril-lattice',
        feed: 'entity-stream',
        originalId: entityId,
        confidence: 0.95,
      },
      timestamp: normalizeTimestamp(track.timestamp) ?? new Date().toISOString(),
      properties: {
        allegiance,
        trackType,
        ...(track.metadata ?? {}),
      },
      display: {
        color,
        icon,
        layerType: domain === Domain.AIR ? 'symbol' : 'circle',
        glow: THREAT_RANK[threat] >= THREAT_RANK[ThreatLevel.HIGH],
        scale: threat === ThreatLevel.CRITICAL ? 1.5 : 1,
      },
    };
  }

  private disconnectTransportOnly(): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }

  private setStatus(status: LatticeConnectionStatus): void {
    this.status = status;
    this.config.onStatusChange?.(status);
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;
    const delay = this.reconnectDelayMs;
    this.reconnectDelayMs = Math.min(this.reconnectDelayMs * 2, 30000);
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      void this.connect();
    }, delay);
  }
}
