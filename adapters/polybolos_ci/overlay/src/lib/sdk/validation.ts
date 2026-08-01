import {
  Classification,
  Domain,
  EntityType,
  ThreatLevel,
  type PolybolosEntity,
} from './types';

const SOURCE_ID_RE = /^[a-z0-9][a-z0-9._-]{0,63}$/;
const ENTITY_ID_RE = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$/;

export function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

export function isValidLatLng(lat: unknown, lng: unknown): lat is number {
  return (
    isFiniteNumber(lat) &&
    isFiniteNumber(lng) &&
    lat >= -90 &&
    lat <= 90 &&
    lng >= -180 &&
    lng <= 180
  );
}

export function sanitizeText(value: unknown, maxLength = 160): string | null {
  if (typeof value !== 'string') return null;
  const normalized = value.trim();
  if (!normalized || normalized.length > maxLength) return null;
  return normalized;
}

export function normalizeSourceId(value: unknown): string | null {
  const text = sanitizeText(value, 64)?.toLowerCase();
  if (!text || !SOURCE_ID_RE.test(text)) return null;
  return text;
}

export function normalizeEntityId(value: unknown): string | null {
  const text = sanitizeText(value, 160);
  if (!text || !ENTITY_ID_RE.test(text)) return null;
  return text;
}

export function normalizeTimestamp(value: unknown): string | null {
  if (typeof value !== 'string' || value.length > 64) return null;
  const time = Date.parse(value);
  if (!Number.isFinite(time)) return null;
  return new Date(time).toISOString();
}

export function normalizeConfidence(value: unknown, fallback = 0.8): number {
  if (!isFiniteNumber(value)) return fallback;
  return Math.max(0, Math.min(1, value));
}

function enumHasValue<T extends Record<string, string>>(
  enumeration: T,
  value: unknown,
): value is T[keyof T] {
  return typeof value === 'string' && Object.values(enumeration).includes(value);
}

export function isDomain(value: unknown): value is Domain {
  return enumHasValue(Domain, value);
}

export function isEntityType(value: unknown): value is EntityType {
  return enumHasValue(EntityType, value);
}

export function isThreatLevel(value: unknown): value is ThreatLevel {
  return enumHasValue(ThreatLevel, value);
}

export function isClassification(value: unknown): value is Classification {
  return enumHasValue(Classification, value);
}

/**
 * Small deterministic non-cryptographic hash for stable fallback identity.
 * It is used only when an upstream feed omits its own identifier. It is not a
 * security primitive and is never presented as one.
 */
export function stableHash(input: string): string {
  let h1 = 0xdeadbeef ^ input.length;
  let h2 = 0x41c6ce57 ^ input.length;
  for (let i = 0; i < input.length; i += 1) {
    const code = input.charCodeAt(i);
    h1 = Math.imul(h1 ^ code, 2654435761);
    h2 = Math.imul(h2 ^ code, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^
    Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^
    Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  return `${(h2 >>> 0).toString(16).padStart(8, '0')}${(h1 >>> 0)
    .toString(16)
    .padStart(8, '0')}`;
}

export function stableId(prefix: string, parts: unknown[]): string {
  const material = parts
    .map((part) => (part === null || part === undefined ? '' : String(part)))
    .join('\u001f');
  return `${prefix}-${stableHash(material)}`;
}

export function validEntityCoordinates(entity: Pick<PolybolosEntity, 'position'>): boolean {
  return isValidLatLng(entity.position.lat, entity.position.lng);
}

export type ExternalEntityInput = Record<string, unknown>;

export function normalizeExternalEntity(
  source: string,
  input: ExternalEntityInput,
): { entity: PolybolosEntity | null; error: string | null } {
  const originalId = normalizeEntityId(input.id);
  if (!originalId) return { entity: null, error: 'invalid entity id' };

  const position = input.position;
  if (!position || typeof position !== 'object') {
    return { entity: null, error: `entity ${originalId}: missing position` };
  }
  const pos = position as Record<string, unknown>;
  if (!isValidLatLng(pos.lat, pos.lng)) {
    return { entity: null, error: `entity ${originalId}: invalid latitude/longitude` };
  }

  const domain = input.domain ?? Domain.LAND;
  const entityType = input.entityType ?? EntityType.TRACK;
  const threat = input.threat ?? ThreatLevel.NONE;
  const classification = input.classification ?? Classification.UNCLASSIFIED;

  if (!isDomain(domain)) return { entity: null, error: `entity ${originalId}: invalid domain` };
  if (!isEntityType(entityType)) {
    return { entity: null, error: `entity ${originalId}: invalid entityType` };
  }
  if (!isThreatLevel(threat)) {
    return { entity: null, error: `entity ${originalId}: invalid threat` };
  }
  if (!isClassification(classification)) {
    return { entity: null, error: `entity ${originalId}: invalid classification` };
  }

  const timestamp = normalizeTimestamp(input.timestamp) ?? new Date().toISOString();
  const name = sanitizeText(input.name, 160) ?? `ENTITY-${originalId}`;
  const properties =
    input.properties && typeof input.properties === 'object' && !Array.isArray(input.properties)
      ? (input.properties as Record<string, unknown>)
      : {};
  const display =
    input.display && typeof input.display === 'object' && !Array.isArray(input.display)
      ? (input.display as Record<string, unknown>)
      : {};

  const layerType =
    display.layerType === 'symbol' || display.layerType === 'line'
      ? display.layerType
      : 'circle';

  return {
    entity: {
      id: `ext-${source}-${originalId}`,
      name,
      domain,
      entityType,
      position: {
        lat: pos.lat,
        lng: pos.lng,
        alt: isFiniteNumber(pos.alt) ? pos.alt : undefined,
        heading: isFiniteNumber(pos.heading) ? pos.heading : undefined,
        speed: isFiniteNumber(pos.speed) ? pos.speed : undefined,
      },
      threat,
      classification,
      source: {
        provider: source,
        feed: 'ingest-api',
        originalId,
        confidence: normalizeConfidence(input.confidence),
      },
      timestamp,
      properties,
      display: {
        color: sanitizeText(display.color, 32) ?? '#D4AF37',
        icon: sanitizeText(display.icon, 64) ?? 'dot-gold',
        layerType,
        glow: display.glow === true,
        scale: isFiniteNumber(display.scale) ? Math.max(0.1, Math.min(10, display.scale)) : 1,
      },
    },
    error: null,
  };
}
