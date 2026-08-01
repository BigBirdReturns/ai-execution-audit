import { NextRequest, NextResponse } from 'next/server';
import { createCommandCandidate } from '@/lib/sdk/candidate';
import { getCommandIntelligenceServerState } from '@/lib/sdk/serverState';
import {
  createCommandIntelligenceSnapshot,
  deriveStableObservationAt,
} from '@/lib/sdk/snapshot';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const MAX_BODY_BYTES = 256 * 1024;
const DEFAULT_STALE_AFTER_MS = 300_000;
const MAX_STALE_AFTER_MS = 86_400_000;

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function parseStaleAfterMs(value: unknown): number {
  if (value === undefined) return DEFAULT_STALE_AFTER_MS;
  if (!Number.isInteger(value) || Number(value) < 1_000 || Number(value) > MAX_STALE_AFTER_MS) {
    throw new Error(`staleAfterMs must be an integer between 1000 and ${MAX_STALE_AFTER_MS}`);
  }
  return Number(value);
}

function candidateKey(): string | null {
  const value = process.env.SDK_CANDIDATE_KEY?.trim();
  return value ? value : null;
}

export async function POST(request: NextRequest) {
  const configuredKey = candidateKey();
  if (!configuredKey) {
    return NextResponse.json(
      {
        schema: 'polybolos-command-candidate-error/1',
        error: 'CANDIDATE_ENDPOINT_DISABLED',
      },
      { status: 503, headers: { 'Cache-Control': 'no-store' } },
    );
  }

  if (request.headers.get('authorization') !== `Bearer ${configuredKey}`) {
    return NextResponse.json(
      {
        schema: 'polybolos-command-candidate-error/1',
        error: 'CANDIDATE_AUTH_REQUIRED',
      },
      { status: 401, headers: { 'Cache-Control': 'no-store' } },
    );
  }

  const contentLength = Number(request.headers.get('content-length'));
  if (Number.isFinite(contentLength) && contentLength > MAX_BODY_BYTES) {
    return NextResponse.json(
      {
        schema: 'polybolos-command-candidate-error/1',
        error: 'CANDIDATE_BODY_LIMIT',
      },
      { status: 413, headers: { 'Cache-Control': 'no-store' } },
    );
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      {
        schema: 'polybolos-command-candidate-error/1',
        error: 'CANDIDATE_JSON_INVALID',
      },
      { status: 400, headers: { 'Cache-Control': 'no-store' } },
    );
  }

  if (!isRecord(body)) {
    return NextResponse.json(
      {
        schema: 'polybolos-command-candidate-error/1',
        error: 'CANDIDATE_BODY_INVALID',
      },
      { status: 400, headers: { 'Cache-Control': 'no-store' } },
    );
  }

  try {
    const staleAfterMs = parseStaleAfterMs(body.staleAfterMs);
    const producer = typeof body.producer === 'string' ? body.producer : '';
    const actionClass = typeof body.actionClass === 'string' ? body.actionClass : '';
    const payload = isRecord(body.payload) ? body.payload : body.payload;
    const state = getCommandIntelligenceServerState();
    const nowMs = Date.now();
    const observedAt = deriveStableObservationAt(
      state.store,
      staleAfterMs,
      nowMs,
      state.startedAt,
    );
    const snapshot = createCommandIntelligenceSnapshot(
      state.store,
      observedAt,
      staleAfterMs,
    );
    const createdAt = typeof body.createdAt === 'string'
      ? body.createdAt
      : new Date(nowMs).toISOString();
    const candidate = createCommandCandidate(snapshot, {
      producer,
      createdAt,
      actionClass,
      payload: payload as Record<string, unknown>,
    });

    return NextResponse.json(
      {
        schema: 'polybolos-command-candidate-transaction/1',
        snapshot,
        candidate,
        persistence: state.persistence,
        claimBoundary:
          'This transaction binds a candidate action to an exact Command Intelligence snapshot. It carries no command, engagement, targeting, effector, or execution authority.',
      },
      { status: 201, headers: { 'Cache-Control': 'no-store' } },
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : 'candidate transaction failed';
    const status = message.startsWith('CI_') ? 409 : 400;
    return NextResponse.json(
      {
        schema: 'polybolos-command-candidate-error/1',
        error: message,
      },
      { status, headers: { 'Cache-Control': 'no-store' } },
    );
  }
}
