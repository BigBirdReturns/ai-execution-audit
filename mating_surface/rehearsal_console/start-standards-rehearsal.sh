#!/usr/bin/env sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -f "$HERE/mating_surface/rehearsal_console/server.mjs" ]; then
  ROOT="$HERE"
else
  ROOT=$(CDPATH= cd -- "$HERE/../.." && pwd)
fi
EVIDENCE="$ROOT/evidence"
MANIFEST="$ROOT/build-manifest.json"

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js 24 or newer is required." >&2
  exit 1
fi
if [ ! -f "$ROOT/mating_surface/rehearsal_console/server.mjs" ]; then
  echo "Rehearsal console source is missing." >&2
  exit 1
fi
if [ ! -f "$EVIDENCE/semantic-conversation/conversation.json" ]; then
  echo "Rehearsal evidence is missing." >&2
  exit 1
fi

(
  sleep 1
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open http://127.0.0.1:8787 >/dev/null 2>&1 || true
  elif command -v open >/dev/null 2>&1; then
    open http://127.0.0.1:8787 >/dev/null 2>&1 || true
  fi
) &

exec node "$ROOT/mating_surface/rehearsal_console/server.mjs" \
  --evidence "$EVIDENCE" \
  --build-manifest "$MANIFEST" \
  --host 127.0.0.1 \
  --port 8787
