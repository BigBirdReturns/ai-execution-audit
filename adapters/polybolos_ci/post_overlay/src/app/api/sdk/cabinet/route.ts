import { NextRequest, NextResponse } from 'next/server';
import {
  projectCommandIntelligenceCabinetFrame,
} from '@/lib/sdk/cabinetProjection';
import { getCommandIntelligenceServerState } from '@/lib/sdk/serverState';
import {
  createCommandIntelligenceSnapshot,
  deriveStableObservationAt,
} from '@/lib/sdk/snapshot';
import { Domain, ThreatLevel } from '@/lib/sdk/types';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const CACHE_CONTROL = 'private, no-cache, max-age=0';

function etagMatches(value: string | null, stateId: string): boolean {
  if (!value) return false;
  return value.split(',').some((candidate) => {
    const token = candidate.trim();
    if (token === '*') return true;
    const withoutWeak = token.startsWith('W/') ? token.slice(2).trim() : token;
    return withoutWeak === `"${stateId}"`;
  });
}

function parseDomains(value: string | null): Domain[] {
  if (!value) return Object.values(Domain);
  const parsed = Array.from(
    new Set(value.split(',').map((item) => item.trim().toUpperCase()).filter(Boolean)),
  );
  if (parsed.length === 0) throw new Error('domains must contain at least one value');
  for (const domain of parsed) {
    if (!Object.values(Domain).includes(domain as Domain)) {
      throw new Error(`unsupported domain: ${domain}`);
    }
  }
  return parsed as Domain[];
}

function parseThreat(value: string | null): ThreatLevel {
  if (!value) return ThreatLevel.NONE;
  const normalized = value.trim().toUpperCase();
  if (!Object.values(ThreatLevel).includes(normalized as ThreatLevel)) {
    throw new Error(`unsupported minimumThreat: ${value}`);
  }
  return normalized as ThreatLevel;
}

function parseInteger(
  value: string | null,
  fallback: number,
  minimum: number,
  maximum: number,
  label: string,
): number {
  if (value === null) return fallback;
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < minimum || parsed > maximum) {
    throw new Error(`${label} must be an integer between ${minimum} and ${maximum}`);
  }
  return parsed;
}

export async function GET(request: NextRequest) {
  try {
    const domains = parseDomains(request.nextUrl.searchParams.get('domains'));
    const minimumThreat = parseThreat(request.nextUrl.searchParams.get('minimumThreat'));
    const limit = parseInteger(
      request.nextUrl.searchParams.get('limit'),
      512,
      1,
      5000,
      'limit',
    );
    const staleAfterMs = parseInteger(
      request.nextUrl.searchParams.get('staleAfterMs'),
      300_000,
      1_000,
      86_400_000,
      'staleAfterMs',
    );
    const state = getCommandIntelligenceServerState();
    const observedAt = deriveStableObservationAt(
      state.store,
      staleAfterMs,
      Date.now(),
      state.startedAt,
    );
    const snapshot = createCommandIntelligenceSnapshot(
      state.store,
      observedAt,
      staleAfterMs,
    );
    const frame = projectCommandIntelligenceCabinetFrame(snapshot, {
      domains,
      minimumThreat,
      limit,
      persistence: state.persistence,
      persistenceDiagnostics: state.store.getPersistenceDiagnostics(),
    });
    const etag = `W/"${frame.stateId}"`;
    if (etagMatches(request.headers.get('if-none-match'), frame.stateId)) {
      return new Response(null, {
        status: 304,
        headers: { ETag: etag, 'Cache-Control': CACHE_CONTROL },
      });
    }
    return NextResponse.json(frame, {
      headers: { ETag: etag, 'Cache-Control': CACHE_CONTROL },
    });
  } catch (error) {
    return NextResponse.json(
      {
        schema: 'polybolos-command-intelligence-cabinet-error/1',
        error: error instanceof Error ? error.message : 'invalid cabinet request',
      },
      { status: 400, headers: { 'Cache-Control': CACHE_CONTROL } },
    );
  }
}
