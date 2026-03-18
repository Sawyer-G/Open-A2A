#!/usr/bin/env bash
set -euo pipefail

# DHT bootstrap E2E check (join + write + read) from your laptop.
#
# This script is intentionally Docker-first, so it doesn't depend on your local Python env.
# If your environment cannot pull images from Docker Hub, you may need to run the same logic
# in your own build environment.
#
# Usage:
#   bash scripts/e2e-dht-bootstrap.sh dht.open-a2a.org:8469
#
# Output:
#   - exits 0 if discover hit succeeds
#   - exits non-zero otherwise

BOOT="${1:-}"
if [[ -z "$BOOT" ]]; then
  echo "Usage: $0 host:port" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CAP="${CAPABILITY:-intent.food.order}"
AGENT_ID="${AGENT_ID:-local-e2e-a}"

echo "[e2e-dht] bootstrap=$BOOT cap=$CAP agent_id=$AGENT_ID"

docker run --rm -t \
  --env BOOT="$BOOT" --env CAP="$CAP" --env AGENT_ID="$AGENT_ID" \
  -v "$ROOT:/repo" -w /repo \
  python:3.12-slim bash -lc \
  "python -m pip install -q --no-cache-dir -e '.[dht]' && python - <<'PY'
import asyncio, os
from open_a2a.discovery_dht import DhtDiscoveryProvider

boot = os.environ['BOOT']
host, port = boot.rsplit(':', 1)
BOOT = [(host, int(port))]
CAP = os.environ['CAP']
AGENT_ID = os.environ['AGENT_ID']

async def main():
  a = DhtDiscoveryProvider(dht_port=18468, bootstrap_nodes=BOOT)
  b = DhtDiscoveryProvider(dht_port=18469, bootstrap_nodes=BOOT)
  await a.connect()
  await b.connect()
  try:
    meta = {'agent_id':AGENT_ID,'capabilities':[CAP],'endpoints':[]}
    await a.register(CAP, meta)
    await asyncio.sleep(1.0)
    res = await b.discover(CAP, timeout_seconds=2.0)
    hit = [x for x in res if isinstance(x, dict) and x.get('agent_id')==AGENT_ID]
    print('discover_count', len(res))
    print('hit', bool(hit))
    if hit:
      print('hit_meta', hit[0])
      raise SystemExit(0)
    raise SystemExit(3)
  finally:
    await a.disconnect()
    await b.disconnect()

asyncio.run(main())
PY" \
  

