import { NextRequest, NextResponse } from 'next/server';
import { createCheckpointCommandCandidate } from '@/lib/sdk/boundedCandidate';
import { getCommandIntelligenceCheckpoint } from '@/lib/sdk/checkpoint';
import { getCommandIntelligenceServerState } from '@/lib/sdk/serverState';
import { deriveStableObservationAt } from '@/lib/sdk/snapshot';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const MAX_BODY_BYTES = 256 * 1024;
const DEFAULT_STALE_AFTER_MS = 300_000;
const MAX_STALE_AFTER_MS = 86_400_000;
const MAX_ENTITY_WITNESSES = 16;

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

function parseEntityIds(value: unknown): string[] {
  if (!Array.isArray(value) || value.length < 1 || value.length > MAX_ENTITY_WITNESSES) {
    throw new Error(`entityIds must contain between 1 and ${MAX_ENTITY_WITNESSES} entries`);
  }
  const ids = value.map((row) => {
    if (typeof row !== 'string') throw new Error('entityIds entries must be strings');
    const id = row.trim();
    if (!id || id.length > 256) throw new Error('entityIds entries must be non-empty and bounded');
    return id;
  });
  if (new Set(ids).size !== ids.length) throw new Error('entityIds must not contain duplicates');
  return ids.sort();
}

function candidateKey(): string | null {
  const value = process.env.SDK_CANDIDATE_KEY?.trim();
  return value ? value : null;
}

function softwareRecordId(): string {
  const value = process.env.CI_SOFTWARE_RECORD_ID?.trim();
  return value || 'public-ci-overlay-unbound';
}

export async function POST(request: NextRequest) {
  const configuredKey = candidateKey();
  if (!configuredKey) {
    return NextResponse.json(
      {
        schema: 'polybolos-command-candidate-error/2',
        error: 'CANDIDATE_ENDPOINT_DISABLED',
      },
      { status: 503, headers: { 'Cache-Control': 'no-store' } },
    );
  }

  if (request.headers.get('authorization') !== `Bearer ${configuredKey}`) {
    return NextResponse.json(
      {
        schema: 'polybolos-command-candidate-error/2',
        error: 'CANDIDATE_AUTH_REQUIRED',
      },
      { status: 401, headers: { 'Cache-Control': 'no-store' } },
    );
  }

  const contentLength = Number(request.headers.get('content-length'));
  if (Number.isFinite(contentLength) && contentLength > MAX_BODY_BYTES) {
    return NextResponse.json(
      {
        schema: 'polybolos-command-candidate-error/2',
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
        schema: 'polybolos-command-candidate-error/2',
        error: 'CANDIDATE_JSON_INVALID',
      },
      { status: 400, headers: { 'Cache-Control': 'no-store' } },
    );
  }

  if (!isRecord(body)) {
    return NextResponse.json(
      {
        schema: 'polybolos-command-candidate-error/2',
        error: 'CANDIDATE_BODY_INVALID',
      },
      { status: 400, headers: { 'Cache-Control': 'no-store' } },
    );
  }

  try {
    const staleAfterMs = parseStaleAfterMs(body.staleAfterMs);
    const entityIds = parseEntityIds(body.entityIds);
    const producer = typeof body.producer === 'string' ? body.producer : '';
    const actionClass = typeof body.actionClass === 'string' ? body.actionClass : '';
    if (!isRecord(body.payload)) throw new Error('candidate payload must be an object');

    const state = getCommandIntelligenceServerState();
    const nowMs = Date.now();
    const observedAt = deriveStableObservationAt(
      state.store,
      staleAfterMs,
      nowMs,
      state.startedAt,
    );
    const witnessStarted = performance.now();
    const compiled = getCommandIntelligenceCheckpoint(
      state.store,
      observedAt,
      staleAfterMs,
      softwareRecordId(),
    );
    const witnesses = entityIds.map((entityId) => compiled.witness(entityId));
    const witnessMilliseconds = performance.now() - witnessStarted - compiled.compileMilliseconds;
    const createdAt = typeof body.createdAt === 'string'
      ? body.createdAt
      : new Date(nowMs).toISOString();
    const candidate = createCheckpointCommandCandidate(
      compiled.checkpoint,
      witnesses,
      {
        producer,
        createdAt,
        actionClass,
        payload: body.payload,
      },
    );

    return NextResponse.json(
      {
        schema: 'polybolos-command-candidate-transaction/2',
        checkpoint: compiled.checkpoint,
        witnesses,
        candidate,
        persistence: state.persistence,
        claimBoundary:
          'This bounded transaction binds a candidate action to one Command Intelligence checkpoint and the cited entity witnesses. It carries no command, engagement, targeting, effector, or execution authority.',
      },
      {
        status: 201,
        headers: {
          'Cache-Control': 'no-store',
          'X-CI-Checkpoint-Cache': compiled.cache,
          'X-CI-Checkpoint-Id': compiled.checkpoint.checkpointId,
          'Server-Timing': [
            `checkpoint;dur=${compiled.compileMilliseconds.toFixed(3)}`,
            `witness;dur=${Math.max(0, witnessMilliseconds).toFixed(3)}`,
          ].join(', '),
        },
      },
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : 'bounded candidate transaction failed';
    const status = message.startsWith('CI_') ? 409 : 400;
    return NextResponse.json(
      {
        schema: 'polybolos-command-candidate-error/2',
        error: message,
      },
      { status, headers: { 'Cache-Control': 'no-store' } },
    );
  }
}
