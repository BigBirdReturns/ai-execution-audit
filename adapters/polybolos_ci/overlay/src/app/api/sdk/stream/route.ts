import {
  buildSdkStatus,
  chunkEntities,
  getSdkStore,
  orderedEntities,
} from '@/lib/sdk/serverStore';

export const dynamic = 'force-dynamic';

const HEARTBEAT_MS = 15000;
const SNAPSHOT_POLL_MS = 1000;
const BATCH_SIZE = 500;

function encodeEvent(value: unknown): Uint8Array {
  return new TextEncoder().encode(`data: ${JSON.stringify(value)}\n\n`);
}

export function buildSnapshotEvents() {
  const store = getSdkStore();
  const entities = orderedEntities(store);
  const batches = chunkEntities(entities, BATCH_SIZE);
  if (batches.length === 0) {
    return [
      {
        type: 'entity_update',
        timestamp: new Date().toISOString(),
        version: store.version,
        batchIndex: 0,
        batchCount: 0,
        complete: true,
        payload: [],
      },
    ];
  }
  return batches.map((payload, batchIndex) => ({
    type: 'entity_update',
    timestamp: new Date().toISOString(),
    version: store.version,
    batchIndex,
    batchCount: batches.length,
    complete: batchIndex === batches.length - 1,
    payload,
  }));
}

export async function GET() {
  const store = getSdkStore();
  let heartbeat: ReturnType<typeof setInterval> | null = null;
  let snapshotPoll: ReturnType<typeof setInterval> | null = null;

  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      let closed = false;
      let lastSentVersion = store.version;

      const send = (value: unknown) => {
        if (closed) return;
        try {
          controller.enqueue(encodeEvent(value));
        } catch {
          closed = true;
        }
      };

      const stop = () => {
        closed = true;
        if (heartbeat) clearInterval(heartbeat);
        if (snapshotPoll) clearInterval(snapshotPoll);
        heartbeat = null;
        snapshotPoll = null;
      };

      send({
        type: 'status',
        timestamp: new Date().toISOString(),
        payload: buildSdkStatus(store),
      });
      for (const event of buildSnapshotEvents()) send(event);

      heartbeat = setInterval(() => {
        if (closed) return;
        send({
          type: 'heartbeat',
          timestamp: new Date().toISOString(),
          payload: {
            entityCount: store.entities.size,
            feedCount: buildSdkStatus(store).feedCount,
            version: store.version,
          },
        });
      }, HEARTBEAT_MS);

      snapshotPoll = setInterval(() => {
        if (closed || store.version === lastSentVersion) return;
        lastSentVersion = store.version;
        for (const event of buildSnapshotEvents()) send(event);
      }, SNAPSHOT_POLL_MS);

      // Retain cleanup on the controller for cancellation paths that do not
      // throw into enqueue.
      Object.assign(controller, { __polybolosStop: stop });
    },
    cancel(reason) {
      void reason;
      if (heartbeat) clearInterval(heartbeat);
      if (snapshotPoll) clearInterval(snapshotPoll);
      heartbeat = null;
      snapshotPoll = null;
    },
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-store, must-revalidate',
      Connection: 'keep-alive',
      'X-Accel-Buffering': 'no',
    },
  });
}
