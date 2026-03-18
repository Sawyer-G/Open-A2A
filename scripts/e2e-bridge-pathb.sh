#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

compose() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    echo "[e2e] docker compose not found" >&2
    exit 2
  fi
}

wait_http() {
  local url="$1"
  local name="$2"
  for _ in $(seq 1 60); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      echo "[e2e] ok: $name"
      return 0
    fi
    sleep 0.5
  done
  echo "[e2e] timeout: $name ($url)" >&2
  return 1
}

json_has() {
  local url="$1"
  local needle="$2"
  if curl -fsS "$url" | grep -q "$needle"; then
    return 0
  fi
  echo "[e2e] expected to find '$needle' in $url" >&2
  curl -fsS "$url" >&2 || true
  return 1
}

mode="${1:-}"
if [[ -z "$mode" ]]; then
  echo "Usage: $0 {single-persist|redis-ha|single-persist-external|redis-ha-external}" >&2
  exit 2
fi

export BRIDGE_DISCOVERY_REGISTER_TOKEN="${BRIDGE_DISCOVERY_REGISTER_TOKEN:-test-register}"
export BRIDGE_DISCOVERY_DISCOVER_TOKEN="${BRIDGE_DISCOVERY_DISCOVER_TOKEN:-test-discover}"
export BRIDGE_DISCOVERY_DEFAULT_TTL_SECONDS="${BRIDGE_DISCOVERY_DEFAULT_TTL_SECONDS:-60}"
export BRIDGE_DISCOVERY_CLEANUP_INTERVAL_SECONDS="${BRIDGE_DISCOVERY_CLEANUP_INTERVAL_SECONDS:-2}"

CAP="intent.food.order"
AGENT_ID="e2e-agent-a"

register_payload() {
  cat <<JSON
{"agent_id":"$AGENT_ID","capabilities":["$CAP"],"meta":{"agent_id":"$AGENT_ID","capabilities":["$CAP"],"endpoints":[{"type":"http","url":"http://example.invalid"}]}}
JSON
}

single_persist() {
  local file="$ROOT/deploy/bridge-pathb/docker-compose.pathb.single.yml"
  echo "[e2e] up single-persist"
  compose -f "$file" up -d --build
  trap 'compose -f "$file" down -v' EXIT

  wait_http "http://127.0.0.1:8080/health" "bridge health"

  echo "[e2e] register capabilities"
  curl -fsS -X POST "http://127.0.0.1:8080/api/register_capabilities" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $BRIDGE_DISCOVERY_REGISTER_TOKEN" \
    -d "$(register_payload)" >/dev/null

  echo "[e2e] discover should hit"
  json_has "http://127.0.0.1:8080/api/discover?capability=$CAP" "$AGENT_ID"

  echo "[e2e] restart bridge (verify persistence)"
  compose -f "$file" restart bridge
  wait_http "http://127.0.0.1:8080/health" "bridge health after restart"

  echo "[e2e] discover should still hit after restart"
  json_has "http://127.0.0.1:8080/api/discover?capability=$CAP" "$AGENT_ID"

  echo "[e2e] done: single-persist"
}

single_persist_external() {
  # Use an already-running NATS (no pulling nats image).
  # Provide E2E_EXTERNAL_NATS_URL like: nats://host.docker.internal:4222
  local nats_url="${E2E_EXTERNAL_NATS_URL:-}"
  if [[ -z "$nats_url" ]]; then
    echo "[e2e] E2E_EXTERNAL_NATS_URL is required for external mode" >&2
    exit 2
  fi

  echo "[e2e] build bridge image"
  docker build -f "$ROOT/Dockerfile.bridge" -t open-a2a-bridge:e2e "$ROOT" >/dev/null

  echo "[e2e] run bridge (external nats)"
  local cid
  cid="$(docker run -d --rm \
    -p 8080:8080 \
    -e NATS_URL="$nats_url" \
    -e BRIDGE_ENABLE_FORWARD=0 \
    -e BRIDGE_ENABLE_DISCOVERY=1 \
    -e BRIDGE_DISCOVERY_DEFAULT_TTL_SECONDS="$BRIDGE_DISCOVERY_DEFAULT_TTL_SECONDS" \
    -e BRIDGE_DISCOVERY_CLEANUP_INTERVAL_SECONDS="$BRIDGE_DISCOVERY_CLEANUP_INTERVAL_SECONDS" \
    -e BRIDGE_DISCOVERY_REGISTER_TOKEN="$BRIDGE_DISCOVERY_REGISTER_TOKEN" \
    -e BRIDGE_DISCOVERY_DISCOVER_TOKEN="$BRIDGE_DISCOVERY_DISCOVER_TOKEN" \
    -e BRIDGE_DISCOVERY_RL_PER_MINUTE="${BRIDGE_DISCOVERY_RL_PER_MINUTE:-600}" \
    -e BRIDGE_DISCOVERY_PERSIST_PATH="/data/bridge_registry.json" \
    -v open_a2a_bridge_e2e_data:/data \
    open-a2a-bridge:e2e)"
  trap 'docker stop "$cid" >/dev/null 2>&1 || true; docker volume rm -f open_a2a_bridge_e2e_data >/dev/null 2>&1 || true' EXIT

  wait_http "http://127.0.0.1:8080/health" "bridge health"

  echo "[e2e] register capabilities"
  curl -fsS -X POST "http://127.0.0.1:8080/api/register_capabilities" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $BRIDGE_DISCOVERY_REGISTER_TOKEN" \
    -d "$(register_payload)" >/dev/null

  echo "[e2e] discover should hit"
  json_has "http://127.0.0.1:8080/api/discover?capability=$CAP" "$AGENT_ID"

  echo "[e2e] restart bridge container (verify persistence)"
  docker restart "$cid" >/dev/null
  wait_http "http://127.0.0.1:8080/health" "bridge health after restart"

  echo "[e2e] discover should still hit after restart"
  json_has "http://127.0.0.1:8080/api/discover?capability=$CAP" "$AGENT_ID"

  echo "[e2e] done: single-persist-external"
}

redis_ha() {
  local file="$ROOT/deploy/bridge-pathb/docker-compose.pathb.ha.yml"
  echo "[e2e] up redis-ha"
  compose -f "$file" up -d --build
  trap 'compose -f "$file" down -v' EXIT

  wait_http "http://127.0.0.1:8081/health" "bridge-1 health"
  wait_http "http://127.0.0.1:8082/health" "bridge-2 health"

  echo "[e2e] register on bridge-1"
  curl -fsS -X POST "http://127.0.0.1:8081/api/register_capabilities" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $BRIDGE_DISCOVERY_REGISTER_TOKEN" \
    -d "$(register_payload)" >/dev/null

  echo "[e2e] discover on bridge-2 should hit (shared redis registry)"
  json_has "http://127.0.0.1:8082/api/discover?capability=$CAP" "$AGENT_ID"

  echo "[e2e] done: redis-ha"
}

redis_ha_external() {
  # Use already-running NATS+Redis (no pulling images).
  # Provide:
  # - E2E_EXTERNAL_NATS_URL like nats://host.docker.internal:4222
  # - E2E_EXTERNAL_REDIS_URL like redis://host.docker.internal:6379/0
  local nats_url="${E2E_EXTERNAL_NATS_URL:-}"
  local redis_url="${E2E_EXTERNAL_REDIS_URL:-}"
  if [[ -z "$nats_url" || -z "$redis_url" ]]; then
    echo "[e2e] E2E_EXTERNAL_NATS_URL and E2E_EXTERNAL_REDIS_URL are required for external mode" >&2
    exit 2
  fi

  echo "[e2e] build bridge image"
  docker build -f "$ROOT/Dockerfile.bridge" -t open-a2a-bridge:e2e "$ROOT" >/dev/null

  echo "[e2e] run bridge-1 and bridge-2 (external nats/redis)"
  local c1 c2
  c1="$(docker run -d --rm -p 8081:8080 \
    -e NATS_URL="$nats_url" \
    -e BRIDGE_ENABLE_FORWARD=0 \
    -e BRIDGE_ENABLE_DISCOVERY=1 \
    -e BRIDGE_DISCOVERY_REDIS_URL="$redis_url" \
    -e BRIDGE_DISCOVERY_DEFAULT_TTL_SECONDS="$BRIDGE_DISCOVERY_DEFAULT_TTL_SECONDS" \
    -e BRIDGE_DISCOVERY_CLEANUP_INTERVAL_SECONDS="$BRIDGE_DISCOVERY_CLEANUP_INTERVAL_SECONDS" \
    -e BRIDGE_DISCOVERY_REGISTER_TOKEN="$BRIDGE_DISCOVERY_REGISTER_TOKEN" \
    -e BRIDGE_DISCOVERY_DISCOVER_TOKEN="$BRIDGE_DISCOVERY_DISCOVER_TOKEN" \
    -e BRIDGE_DISCOVERY_RL_PER_MINUTE="${BRIDGE_DISCOVERY_RL_PER_MINUTE:-600}" \
    open-a2a-bridge:e2e)"
  c2="$(docker run -d --rm -p 8082:8080 \
    -e NATS_URL="$nats_url" \
    -e BRIDGE_ENABLE_FORWARD=0 \
    -e BRIDGE_ENABLE_DISCOVERY=1 \
    -e BRIDGE_DISCOVERY_REDIS_URL="$redis_url" \
    -e BRIDGE_DISCOVERY_DEFAULT_TTL_SECONDS="$BRIDGE_DISCOVERY_DEFAULT_TTL_SECONDS" \
    -e BRIDGE_DISCOVERY_CLEANUP_INTERVAL_SECONDS="$BRIDGE_DISCOVERY_CLEANUP_INTERVAL_SECONDS" \
    -e BRIDGE_DISCOVERY_REGISTER_TOKEN="$BRIDGE_DISCOVERY_REGISTER_TOKEN" \
    -e BRIDGE_DISCOVERY_DISCOVER_TOKEN="$BRIDGE_DISCOVERY_DISCOVER_TOKEN" \
    -e BRIDGE_DISCOVERY_RL_PER_MINUTE="${BRIDGE_DISCOVERY_RL_PER_MINUTE:-600}" \
    open-a2a-bridge:e2e)"
  trap 'docker stop "$c1" "$c2" >/dev/null 2>&1 || true' EXIT

  wait_http "http://127.0.0.1:8081/health" "bridge-1 health"
  wait_http "http://127.0.0.1:8082/health" "bridge-2 health"

  echo "[e2e] register on bridge-1"
  curl -fsS -X POST "http://127.0.0.1:8081/api/register_capabilities" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $BRIDGE_DISCOVERY_REGISTER_TOKEN" \
    -d "$(register_payload)" >/dev/null

  echo "[e2e] discover on bridge-2 should hit (shared redis registry)"
  json_has "http://127.0.0.1:8082/api/discover?capability=$CAP" "$AGENT_ID"

  echo "[e2e] done: redis-ha-external"
}

case "$mode" in
  single-persist) single_persist ;;
  redis-ha) redis_ha ;;
  single-persist-external) single_persist_external ;;
  redis-ha-external) redis_ha_external ;;
  *) echo "Unknown mode: $mode" >&2; exit 2 ;;
esac

