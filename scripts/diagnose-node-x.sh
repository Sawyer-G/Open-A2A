#!/usr/bin/env bash

# Node X operator diagnose script (Docker-based)
#
# Goals:
# - No dependency on local "nats" CLI
# - Provide quick signals for: containers, ports, /health, NATS ping, discovery query
#
# Usage:
#   bash scripts/diagnose-node-x.sh
#   # or specify env/compose:
#   ENV_FILE=.env COMPOSE_FILE=deploy/node-x/docker-compose.node-x.yml bash scripts/diagnose-node-x.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/deploy/node-x/docker-compose.node-x.yml}"
NETWORK_NAME="${OPEN_A2A_NETWORK_NAME:-open-a2a}"

# Load .env into this process for port/password checks (best-effort).
# shellcheck disable=SC1090
if [[ -f "$ENV_FILE" ]]; then
  set -a
  source "$ENV_FILE" || true
  set +a
fi

STRICT="${OA2A_STRICT_SECURITY:-0}"
if [[ "$STRICT" == "1" || "$STRICT" == "true" || "$STRICT" == "yes" ]]; then
  STRICT=1
else
  STRICT=0
fi

fail_or_warn() {
  local msg="$1"
  if [[ "$STRICT" -eq 1 ]]; then
    echo "  [error] $msg"
    exit 1
  else
    echo "  [warn] $msg"
  fi
}

print_kv() {
  local key="$1"
  local val="${2:-}"
  printf "  %-24s %s\n" "$key" "$val"
}

tcp_check() {
  local host="$1"
  local port="$2"
  timeout 2 bash -c "cat < /dev/null > /dev/tcp/${host}/${port}" 2>/dev/null
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "[error] missing command: $1"; exit 1; }
}

echo "== Open-A2A Node X diagnose =="
echo

require_cmd docker

if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE="docker-compose"
else
  echo "[error] docker compose not found"
  exit 1
fi

echo "[info] Using compose: $COMPOSE"
print_kv "ENV_FILE" "$ENV_FILE"
print_kv "COMPOSE_FILE" "$COMPOSE_FILE"
print_kv "NETWORK" "$NETWORK_NAME"
echo

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "[error] compose file not found: $COMPOSE_FILE"
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[warn] .env not found at $ENV_FILE (some checks will use defaults)"
fi

echo "[step] Container status"
$COMPOSE -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps || true
echo

echo "[step] Host port checks"
RELAY_PORT="${RELAY_WS_PORT:-8765}"
BRIDGE_PORT="${BRIDGE_PORT:-8080}"

if tcp_check "127.0.0.1" "$RELAY_PORT"; then
  print_kv "relay port open" "127.0.0.1:${RELAY_PORT} (ok)"
else
  print_kv "relay port open" "127.0.0.1:${RELAY_PORT} (fail)"
fi

if tcp_check "127.0.0.1" "$BRIDGE_PORT"; then
  print_kv "bridge port open" "127.0.0.1:${BRIDGE_PORT} (ok)"
else
  print_kv "bridge port open" "127.0.0.1:${BRIDGE_PORT} (fail)"
fi
echo

echo "[step] Security sanity checks (recommended for public nodes)"
warned=0
if [[ "${NATS_RELAY_PASS:-}" == change-me-* || -z "${NATS_RELAY_PASS:-}" ]]; then
  echo "  [warn] NATS_RELAY_PASS is default/empty; change it before public use."
  warned=1
fi
if [[ "${NATS_BRIDGE_PASS:-}" == change-me-* || -z "${NATS_BRIDGE_PASS:-}" ]]; then
  echo "  [warn] NATS_BRIDGE_PASS is default/empty; change it before public use."
  warned=1
fi
if [[ -z "${RELAY_AUTH_TOKEN:-}" ]]; then
  echo "  [warn] RELAY_AUTH_TOKEN is not set; public Relay without auth can be abused."
  warned=1
fi
if [[ "${RELAY_SUBJECT_ALLOWLIST:-}" == *"_INBOX.>"* ]]; then
  echo "  [warn] RELAY_SUBJECT_ALLOWLIST contains _INBOX.> (too broad). Prefer _INBOX.open_a2a.>."
  warned=1
fi

# Strict-mode: fail fast on clearly unsafe defaults for public/operator nodes.
if [[ "$STRICT" -eq 1 ]]; then
  if [[ "${NATS_RELAY_PASS:-}" == change-me-* || -z "${NATS_RELAY_PASS:-}" ]]; then
    fail_or_warn "STRICT: NATS_RELAY_PASS 仍为占位/空值（必须修改）"
  fi
  if [[ "${NATS_BRIDGE_PASS:-}" == change-me-* || -z "${NATS_BRIDGE_PASS:-}" ]]; then
    fail_or_warn "STRICT: NATS_BRIDGE_PASS 仍为占位/空值（必须修改）"
  fi
  if [[ "${NATS_PUBLIC_PASS:-}" == change-me-* && -n "${NATS_PUBLIC_USER:-}" ]]; then
    fail_or_warn "STRICT: NATS_PUBLIC_PASS 仍为占位（若开放 NATS 直连必须修改）"
  fi

  # Relay public entry should have auth token.
  RELAY_HOST="${RELAY_WS_HOST:-0.0.0.0}"
  if [[ "$RELAY_HOST" == "0.0.0.0" || "$RELAY_HOST" == "::" || -z "$RELAY_HOST" ]]; then
    if [[ -z "${RELAY_AUTH_TOKEN:-}" ]]; then
      fail_or_warn "STRICT: Relay 绑定公网地址但未设置 RELAY_AUTH_TOKEN"
    fi
  fi

  # If Bridge exposes directory discovery, require auth tokens.
  if [[ "${BRIDGE_ENABLE_DISCOVERY:-1}" == "1" || "${BRIDGE_ENABLE_DISCOVERY:-1}" == "true" ]]; then
    if [[ -z "${BRIDGE_DISCOVERY_REGISTER_TOKEN:-}" || -z "${BRIDGE_DISCOVERY_DISCOVER_TOKEN:-}" ]]; then
      fail_or_warn "STRICT: Bridge discovery 启用但未配置 BRIDGE_DISCOVERY_REGISTER_TOKEN/BRIDGE_DISCOVERY_DISCOVER_TOKEN"
    fi
  fi
fi

if [[ $warned -eq 0 ]]; then
  echo "  ok"
fi
echo

echo "[step] Bridge /health (if exposed)"
if command -v curl >/dev/null 2>&1; then
  curl -sS "http://127.0.0.1:${BRIDGE_PORT}/health" | sed 's/^/  /' || echo "  [warn] /health not reachable"
else
  echo "  [warn] curl not found, skip /health"
fi
echo

echo "[step] NATS ping via nats-box (no local CLI required)"
NATS_USER="${NATS_BRIDGE_USER:-bridge}"
NATS_PASS="${NATS_BRIDGE_PASS:-change-me-bridge-pass}"
NATS_URL="nats://${NATS_USER}:${NATS_PASS}@nats:4222"

docker run --rm --network "$NETWORK_NAME" natsio/nats-box:latest \
  nats --server "$NATS_URL" ping -c 1 2>/dev/null \
  && echo "  NATS ping: ok (${NATS_URL})" \
  || echo "  [warn] NATS ping failed (${NATS_URL})"
echo

echo "[step] Discovery query (optional)"
CAP="${BRIDGE_CAPABILITIES:-intent.food.order}"
CAP_FIRST="${CAP%%,*}"
if command -v curl >/dev/null 2>&1; then
  AUTH_HEADER=()
  if [[ -n "${BRIDGE_DISCOVERY_DISCOVER_TOKEN:-}" ]]; then
    AUTH_HEADER=(-H "Authorization: Bearer ${BRIDGE_DISCOVERY_DISCOVER_TOKEN}")
  fi
  curl -sS "${AUTH_HEADER[@]}" "http://127.0.0.1:${BRIDGE_PORT}/api/discover?capability=${CAP_FIRST}&timeout_seconds=2" \
    | sed 's/^/  /' \
    || echo "  [warn] discover API not reachable (Bridge may be private or disabled)"
else
  echo "  [warn] curl not found, skip /api/discover"
fi
echo

echo "[step] Discovery stats (optional)"
if command -v curl >/dev/null 2>&1; then
  AUTH_HEADER=()
  if [[ -n "${BRIDGE_DISCOVERY_DISCOVER_TOKEN:-}" ]]; then
    AUTH_HEADER=(-H "Authorization: Bearer ${BRIDGE_DISCOVERY_DISCOVER_TOKEN}")
  fi
  curl -sS "${AUTH_HEADER[@]}" "http://127.0.0.1:${BRIDGE_PORT}/api/discovery_stats" \
    | sed 's/^/  /' \
    || echo "  [warn] /api/discovery_stats not reachable (or auth required)"
else
  echo "  [warn] curl not found, skip /api/discovery_stats"
fi
echo

echo "[done] If you see failures above:"
echo "  - verify deploy/node-x/nats.conf passwords match .env"
echo "  - verify firewall allows ${RELAY_PORT}/tcp (and ${BRIDGE_PORT}/tcp if you expose Bridge)"
echo "  - verify docker network name is '${NETWORK_NAME}'"

