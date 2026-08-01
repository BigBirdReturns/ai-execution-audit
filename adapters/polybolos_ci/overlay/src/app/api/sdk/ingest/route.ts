import { timingSafeEqual } from 'node:crypto';
import { NextRequest, NextResponse } from 'next/server';
import {
  getSdkStore,
  recordIngest,
} from '@/lib/sdk/serverStore';
import {
  normalizeExternalEntity,
  normalizeSourceId,
} from '@/lib/sdk/validation';

const MAX_ENTITIES_PER_REQUEST = 5000;

function providedApiKey(request: NextRequest, body: Record<string, unknown>): string | null {
  const authorization = request.headers.get('authorization');
  if (authorization?.toLowerCase().startsWith('bearer ')) {
    return authorization.slice(7).trim() || null;
  }
  return typeof body.apiKey === 'string' ? body.apiKey : null;
}

function keysEqual(expected: string, observed: string | null): boolean {
  if (!observed) return false;
  const left = Buffer.from(expected);
  const right = Buffer.from(observed);
  return left.length === right.length && timingSafeEqual(left, right);
}

export async function POST(request: NextRequest) {
  const configuredKey = process.env.SDK_INGEST_KEY;
  if (!configuredKey) {
    return NextResponse.json(
      {
        accepted: 0,
        rejected: 0,
        errors: ['Ingest endpoint disabled — SDK_INGEST_KEY not configured'],
        timestamp: new Date().toISOString(),
      },
      { status: 503 },
    );
  }

  let body: Record<string, unknown>;
  try {
    const parsed = await request.json();
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      throw new Error('request body must be an object');
    }
    body = parsed as Record<string, unknown>;
  } catch {
    return NextResponse.json(
      {
        accepted: 0,
        rejected: 0,
        errors: ['Invalid JSON request body'],
        timestamp: new Date().toISOString(),
      },
      { status: 400 },
    );
  }

  if (!keysEqual(configuredKey, providedApiKey(request, body))) {
    return NextResponse.json(
      {
        accepted: 0,
        rejected: 0,
        errors: ['Invalid API key'],
        timestamp: new Date().toISOString(),
      },
      { status: 401 },
    );
  }

  const source = normalizeSourceId(body.source);
  if (!source) {
    return NextResponse.json(
      {
        accepted: 0,
        rejected: 0,
        errors: ['Invalid source identifier'],
        timestamp: new Date().toISOString(),
      },
      { status: 400 },
    );
  }

  if (!Array.isArray(body.entities)) {
    return NextResponse.json(
      {
        accepted: 0,
        rejected: 0,
        errors: ['Invalid payload structure. Required: { source, entities[] }'],
        timestamp: new Date().toISOString(),
      },
      { status: 400 },
    );
  }
  if (body.entities.length > MAX_ENTITIES_PER_REQUEST) {
    return NextResponse.json(
      {
        accepted: 0,
        rejected: body.entities.length,
        errors: [`Request exceeds ${MAX_ENTITIES_PER_REQUEST} entity limit`],
        timestamp: new Date().toISOString(),
      },
      { status: 413 },
    );
  }

  const store = getSdkStore();
  let accepted = 0;
  let rejected = 0;
  const errors: string[] = [];

  for (const candidate of body.entities) {
    if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate)) {
      rejected += 1;
      if (errors.length < 20) errors.push('Entity must be an object');
      continue;
    }
    const normalized = normalizeExternalEntity(
      source,
      candidate as Record<string, unknown>,
    );
    if (!normalized.entity) {
      rejected += 1;
      if (normalized.error && errors.length < 20) errors.push(normalized.error);
      continue;
    }
    store.entities.set(normalized.entity.id, normalized.entity);
    accepted += 1;
  }

  recordIngest(source, accepted, rejected, store);

  return NextResponse.json({
    accepted,
    rejected,
    errors,
    version: store.version,
    timestamp: new Date().toISOString(),
  });
}

export async function GET() {
  const store = getSdkStore();
  return NextResponse.json({
    sdk: 'polybolos',
    version: '1.1.0',
    entityCount: store.entities.size,
    storeVersion: store.version,
    recentIngestions: store.ingestLog.slice(-10),
    timestamp: new Date().toISOString(),
  });
}
