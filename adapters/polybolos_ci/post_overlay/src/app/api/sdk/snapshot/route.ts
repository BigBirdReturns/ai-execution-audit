import { NextRequest, NextResponse } from 'next/server';
import { getCommandIntelligenceServerState } from '@/lib/sdk/serverState';
import {
  createCommandIntelligenceSnapshot,
  deriveStableObservationAt,
} from '@/lib/sdk/snapshot';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  const state = getCommandIntelligenceServerState();
  const requested = Number(request.nextUrl.searchParams.get('staleAfterMs') ?? 300_000);
  const staleAfterMs = Number.isFinite(requested)
    ? Math.min(86_400_000, Math.max(1_000, Math.trunc(requested)))
    : 300_000;
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
  return NextResponse.json(snapshot, {
    headers: {
      'Cache-Control': 'no-store',
      ETag: `"${snapshot.snapshotId}"`,
    },
  });
}
