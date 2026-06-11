#!/usr/bin/env bash
# Chunked full sync of InfoLobby SPARQL into Supabase.
#
# Loops `services/info_lobby_sync/run_sync.py` with increasing --offset
# until every kind reports zero fetched records, so memory per chunk is
# bounded (about ~CHUNK_SIZE × ~2KB records × 3 kinds peak). Each chunk
# saves its metrics JSON to a timestamped directory; the loop is
# resumable by re-running with the right START_OFFSET / chunk count.
#
# Idempotency comes from the bulk pipeline (commit aece0a6): re-running
# a chunk with the same offset just no-ops.
#
# Env:
#   CHUNK_SIZE     records per kind per chunk (default 100000)
#   START_OFFSET   starting offset per kind (default 0)
#   RATE_SLEEP     seconds between SPARQL calls (default 1.0)
#   PYTHON         python interpreter (default .venv/bin/python)
#
# Usage:
#   ./scripts/sync_infolobby_full.sh
#   START_OFFSET=300000 ./scripts/sync_infolobby_full.sh   # resume after killed run

set -euo pipefail

CHUNK_SIZE="${CHUNK_SIZE:-100000}"
START_OFFSET="${START_OFFSET:-0}"
RATE_SLEEP="${RATE_SLEEP:-1.0}"
PYTHON="${PYTHON:-.venv/bin/python}"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

if [ ! -f .env ]; then
  echo "missing .env at repo root" >&2
  exit 2
fi
# shellcheck disable=SC1091
set -a; . ./.env; set +a

RUN_DIR="data/info_lobby/sync-runs/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$RUN_DIR"
echo "metrics dir: $RUN_DIR"

offset="$START_OFFSET"
chunk_num=0
total_audiencias=0
total_viajes=0
total_donativos=0

while true; do
  chunk_num=$((chunk_num + 1))
  metrics_file="$RUN_DIR/chunk-$(printf '%03d' "$chunk_num")-offset-$offset.json"

  echo
  echo "[$(date -u +%H:%M:%SZ)] chunk $chunk_num: offset=$offset, max=$CHUNK_SIZE"
  # stdout of run_sync.py is the metrics JSON; redirect into the file.
  if ! "$PYTHON" -m services.info_lobby_sync.run_sync \
        --offset "$offset" \
        --max-records "$CHUNK_SIZE" \
        --rate-sleep "$RATE_SLEEP" \
      > "$metrics_file" 2>>"$RUN_DIR/run.log"; then
    echo "  chunk $chunk_num FAILED — see $RUN_DIR/run.log" >&2
    # Keep going so a transient failure doesn't stop the whole sync.
  fi

  # Extract fetched counts with the same Python (no jq dependency).
  read -r f_audiencias f_viajes f_donativos status < <(
    "$PYTHON" - "$metrics_file" <<'PY'
import json, sys
with open(sys.argv[1]) as f:
    m = json.load(f)
fetched = m.get("fetched", {})
print(
    fetched.get("audiencias", 0),
    fetched.get("viajes", 0),
    fetched.get("donativos", 0),
    m.get("status", "?"),
)
PY
  )

  total_audiencias=$((total_audiencias + f_audiencias))
  total_viajes=$((total_viajes + f_viajes))
  total_donativos=$((total_donativos + f_donativos))

  echo "  fetched: audiencias=$f_audiencias viajes=$f_viajes donativos=$f_donativos  status=$status"
  echo "  running totals: audiencias=$total_audiencias viajes=$total_viajes donativos=$total_donativos"

  # Stop when all three kinds returned zero — corpus exhausted.
  if [ "$f_audiencias" -eq 0 ] && [ "$f_viajes" -eq 0 ] && [ "$f_donativos" -eq 0 ]; then
    echo
    echo "[$(date -u +%H:%M:%SZ)] all kinds exhausted at offset $offset after $chunk_num chunks"
    break
  fi

  offset=$((offset + CHUNK_SIZE))
done

echo
echo "=== Final ==="
echo "chunks run:     $chunk_num"
echo "audiencias:     $total_audiencias"
echo "viajes:         $total_viajes"
echo "donativos:      $total_donativos"
echo "metrics dir:    $RUN_DIR"
