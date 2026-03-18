#!/usr/bin/env bash

# Simple helper script: start Open-A2A Bridge + NATS + Relay + Solid
# on the same server where OpenClaw is running.
#
# Usage:
#   1) Clone this repo on the OpenClaw server
#   2) cd Open-A2A
#   3) bash scripts/setup-openclaw-bridge.sh
#   4) Enter NATS_URL / OPENCLAW_GATEWAY_URL / OPENCLAW_HOOKS_TOKEN when prompted
#
# Requirements:
#   - docker and docker-compose are installed
#   - OpenClaw Gateway is reachable from this machine

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="$ROOT_DIR/.env"
COMPOSE_FILE="$ROOT_DIR/deploy/quickstart/docker-compose.full.yml"

is_truthy() {
  local v="${1:-}"
  [[ "${v,,}" == "1" || "${v,,}" == "true" || "${v,,}" == "yes" || "${v,,}" == "y" || "${v,,}" == "on" ]]
}

get_kv() {
  local key="$1"
  if [[ ! -f "$ENV_FILE" ]]; then
    return 0
  fi
  # Read last occurrence to match docker-compose env precedence style.
  grep -E "^${key}=" "$ENV_FILE" 2>/dev/null | tail -n 1 | cut -d'=' -f2- || true
}

set_kv() {
  local key="$1"
  local val="$2"
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "[error] .env not found at $ENV_FILE" >&2
    exit 2
  fi
  if grep -qE "^${key}=" "$ENV_FILE" 2>/dev/null; then
    # macOS/BSD sed compatible
    sed -i '' -E "s|^${key}=.*|${key}=${val}|g" "$ENV_FILE"
  else
    printf "\n%s=%s\n" "$key" "$val" >>"$ENV_FILE"
  fi
}

prompt() {
  local label="$1"
  local def="${2:-}"
  local secret="${3:-0}"
  local input=""
  if [[ -n "$def" ]]; then
    if [[ "$secret" == "1" ]]; then
      read -rsp "$label (default hidden): " input
      echo
      echo "${input:-$def}"
      return 0
    fi
    read -rp "$label (default $def): " input
    echo "${input:-$def}"
    return 0
  fi
  if [[ "$secret" == "1" ]]; then
    read -rsp "$label: " input
    echo
    echo "$input"
    return 0
  fi
  read -rp "$label: " input
  echo "$input"
}

prompt_required() {
  local key="$1"
  local label="$2"
  local def="${3:-}"
  local secret="${4:-0}"
  local current
  current="$(get_kv "$key")"
  if [[ -n "${current:-}" ]]; then
    echo "$current"
    return 0
  fi
  local v
  v="$(prompt "$label" "$def" "$secret")"
  while [[ -z "${v:-}" ]]; do
    echo "[warn] $key is required." >&2
    v="$(prompt "$label" "$def" "$secret")"
  done
  echo "$v"
}

detect_compose() {
  if docker compose version >/dev/null 2>&1; then
    echo "docker compose"
    return 0
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    echo "docker-compose"
    return 0
  fi
  echo ""
  return 1
}

detect_gateway_default() {
  # 优先：尝试通过容器名中带 gateway 的容器自动推断
  local cid name
  cid="$(docker ps --filter "name=gateway" --format '{{.ID}}' | head -n 1 || true)"
  if [[ -n "${cid:-}" ]]; then
    name="$(docker inspect "$cid" --format '{{.Name}}' 2>/dev/null | sed 's#^/##')"
    if [[ -n "${name:-}" ]]; then
      echo "http://${name}:18789"
      return 0
    fi
  fi
  # 兜底：留空，让后续交互使用示例值
  echo ""
}

diagnose() {
  echo "== Open-A2A / OpenClaw integration diagnose =="
  echo

  if [[ ! -f "$ENV_FILE" ]]; then
    echo "[warn] .env not found at $ENV_FILE"
  else
    echo "[info] .env found, current related variables:"
    grep -E "NATS_URL|OPENCLAW_GATEWAY_URL|OPENCLAW_HOOKS_TOKEN" "$ENV_FILE" || echo "  (no matching keys)"
  fi

  echo
  echo "[step] Checking Bridge container environment (if running)..."
  if docker ps --format '{{.Names}}' | grep -q '^open-a2a-open-a2a-bridge-1$'; then
    docker exec open-a2a-open-a2a-bridge-1 env | grep -E "NATS_URL|OPENCLAW_GATEWAY_URL|OPENCLAW_HOOKS_TOKEN" || echo "  (no env vars found in container)"
  else
    echo "[warn] Bridge container open-a2a-open-a2a-bridge-1 not running."
  fi

  echo
  echo "[step] Checking connectivity to OpenClaw Gateway from host..."
  if grep -q "OPENCLAW_GATEWAY_URL" "$ENV_FILE" 2>/dev/null; then
    GATEWAY_URL="$(grep "OPENCLAW_GATEWAY_URL" "$ENV_FILE" | tail -n1 | cut -d'=' -f2-)"
    echo "  Using OPENCLAW_GATEWAY_URL from .env: $GATEWAY_URL"
    curl -sS -o /dev/null -w "  HTTP status: %{http_code}\n" "${GATEWAY_URL}/" || echo "  [warn] curl to ${GATEWAY_URL}/ failed"
  else
    echo "  [warn] OPENCLAW_GATEWAY_URL not set in .env, skip host curl check."
  fi

  echo
  echo "[step] Checking Bridge API on host (http://localhost:8080)..."
  curl -sS -o /dev/null -w "  /health status: %{http_code}\n" "http://localhost:8080/health" || echo "  [warn] /health not available, try /api/publish_intent manually."

  echo
  echo "[done] Diagnose finished. See warnings above for potential misconfigurations."
}

main() {
  local cmd="${1:-run}"

  case "$cmd" in
    diagnose)
      diagnose
      return 0
      ;;
    run|*)
      ;;
  esac

  echo "== Open-A2A / OpenClaw integration helper =="
  echo

  if [[ -f "$ENV_FILE" ]]; then
    echo "[info] Found existing .env, will append/update key variables."
  else
    echo "[info] No .env found, creating from .env.example."
    cp .env.example .env
  fi

  echo
  echo "This wizard will help you run a full node stack on this machine:"
  echo "  - NATS (private by default in quickstart)"
  echo "  - Relay (WS public entry recommended)"
  echo "  - Bridge (OpenClaw adapter + optional Directory Registry APIs)"
  echo "  - Solid (optional)"
  echo

  # Strict security (recommended for any public deployment)
  STRICT_CURRENT="$(get_kv "OA2A_STRICT_SECURITY")"
  STRICT_DEFAULT="${STRICT_CURRENT:-1}"
  STRICT_VALUE="$(prompt "Enable OA2A_STRICT_SECURITY? (recommended for public nodes) [1/0]" "$STRICT_DEFAULT" 0)"
  if is_truthy "$STRICT_VALUE"; then
    STRICT_VALUE="1"
  else
    STRICT_VALUE="0"
  fi

  NATS_URL_VALUE="$(prompt "Enter NATS_URL (for quickstart, use service name)" "nats://nats:4222" 0)"

  # 自动探测 OpenClaw Gateway 容器名，提供更合理的默认值
  AUTO_GATEWAY_URL="$(detect_gateway_default)"
  GATEWAY_DEFAULT_HINT="${AUTO_GATEWAY_URL:-http://localhost:3000}"
  echo "[info] Detected default OpenClaw Gateway URL: ${AUTO_GATEWAY_URL:-<none, fallback to example>}"
  # Forwarding is optional; if enabled, gateway url + hooks token are required.
  FWD_CURRENT="$(get_kv "BRIDGE_ENABLE_FORWARD")"
  FWD_DEFAULT="${FWD_CURRENT:-1}"
  FWD_VALUE="$(prompt "Enable BRIDGE_ENABLE_FORWARD (Bridge -> OpenClaw hooks) [1/0]" "$FWD_DEFAULT" 0)"
  if is_truthy "$FWD_VALUE"; then
    FWD_VALUE="1"
    OPENCLAW_GATEWAY_URL_VALUE="$(prompt_required "OPENCLAW_GATEWAY_URL" "Enter OpenClaw Gateway URL" "$GATEWAY_DEFAULT_HINT" 0)"
    OPENCLAW_HOOKS_TOKEN_VALUE="$(prompt_required "OPENCLAW_HOOKS_TOKEN" "Paste OpenClaw hooks token" "" 1)"
  else
    FWD_VALUE="0"
    OPENCLAW_GATEWAY_URL_VALUE="$(get_kv "OPENCLAW_GATEWAY_URL")"
    OPENCLAW_HOOKS_TOKEN_VALUE="$(get_kv "OPENCLAW_HOOKS_TOKEN")"
  fi

  # Relay auth token is required in strict mode when Relay is public.
  RELAY_HOST_CURRENT="$(get_kv "RELAY_WS_HOST")"
  RELAY_HOST_DEFAULT="${RELAY_HOST_CURRENT:-0.0.0.0}"
  RELAY_WS_HOST_VALUE="$(prompt "Relay bind host (public nodes use 0.0.0.0)" "$RELAY_HOST_DEFAULT" 0)"
  RELAY_WS_PORT_VALUE="$(prompt "Relay WS port" "${RELAY_WS_PORT:-8765}" 0)"
  RELAY_AUTH_TOKEN_VALUE="$(get_kv "RELAY_AUTH_TOKEN")"
  if [[ "$STRICT_VALUE" == "1" && ( "$RELAY_WS_HOST_VALUE" == "0.0.0.0" || "$RELAY_WS_HOST_VALUE" == "::" || -z "$RELAY_WS_HOST_VALUE" ) ]]; then
    RELAY_AUTH_TOKEN_VALUE="$(prompt_required "RELAY_AUTH_TOKEN" "Paste RELAY_AUTH_TOKEN (required in strict mode for public Relay)" "" 1)"
  else
    if [[ -z "${RELAY_AUTH_TOKEN_VALUE:-}" ]]; then
      RELAY_AUTH_TOKEN_VALUE="$(prompt "Optional: RELAY_AUTH_TOKEN (recommended even for internal nodes)" "" 1)"
    fi
  fi

  # Directory Registry APIs (HTTP register/discover) — if enabled in strict mode, require tokens.
  DISC_CURRENT="$(get_kv "BRIDGE_ENABLE_DISCOVERY")"
  DISC_DEFAULT="${DISC_CURRENT:-1}"
  DISC_VALUE="$(prompt "Enable BRIDGE_ENABLE_DISCOVERY (NATS discovery + optional Directory Registry APIs) [1/0]" "$DISC_DEFAULT" 0)"
  if is_truthy "$DISC_VALUE"; then
    DISC_VALUE="1"
  else
    DISC_VALUE="0"
  fi

  BRIDGE_DISCOVERY_REGISTER_TOKEN_VALUE="$(get_kv "BRIDGE_DISCOVERY_REGISTER_TOKEN")"
  BRIDGE_DISCOVERY_DISCOVER_TOKEN_VALUE="$(get_kv "BRIDGE_DISCOVERY_DISCOVER_TOKEN")"
  if [[ "$STRICT_VALUE" == "1" && "$DISC_VALUE" == "1" ]]; then
    BRIDGE_DISCOVERY_REGISTER_TOKEN_VALUE="$(prompt_required "BRIDGE_DISCOVERY_REGISTER_TOKEN" "Paste BRIDGE_DISCOVERY_REGISTER_TOKEN (Directory Registry register token)" "" 1)"
    BRIDGE_DISCOVERY_DISCOVER_TOKEN_VALUE="$(prompt_required "BRIDGE_DISCOVERY_DISCOVER_TOKEN" "Paste BRIDGE_DISCOVERY_DISCOVER_TOKEN (Directory Registry discover token)" "" 1)"
  fi

  echo
  echo "[info] Will write/update .env:"
  echo "  OA2A_STRICT_SECURITY=$STRICT_VALUE"
  echo "  NATS_URL=$NATS_URL_VALUE"
  echo "  RELAY_WS_HOST=$RELAY_WS_HOST_VALUE"
  echo "  RELAY_WS_PORT=$RELAY_WS_PORT_VALUE"
  echo "  RELAY_AUTH_TOKEN=$( [[ -n "${RELAY_AUTH_TOKEN_VALUE:-}" ]] && echo '[provided]' || echo '[empty]' )"
  echo "  BRIDGE_ENABLE_FORWARD=$FWD_VALUE"
  echo "  OPENCLAW_GATEWAY_URL=${OPENCLAW_GATEWAY_URL_VALUE:-}"
  echo "  OPENCLAW_HOOKS_TOKEN=$( [[ -n "${OPENCLAW_HOOKS_TOKEN_VALUE:-}" ]] && echo '[provided]' || echo '[empty]' )"
  echo "  BRIDGE_ENABLE_DISCOVERY=$DISC_VALUE"
  echo "  BRIDGE_DISCOVERY_REGISTER_TOKEN=$( [[ -n "${BRIDGE_DISCOVERY_REGISTER_TOKEN_VALUE:-}" ]] && echo '[provided]' || echo '[empty]' )"
  echo "  BRIDGE_DISCOVERY_DISCOVER_TOKEN=$( [[ -n "${BRIDGE_DISCOVERY_DISCOVER_TOKEN_VALUE:-}" ]] && echo '[provided]' || echo '[empty]' )"
  echo

  # Update keys (do not blindly append duplicates).
  set_kv "OA2A_STRICT_SECURITY" "$STRICT_VALUE"
  set_kv "NATS_URL" "$NATS_URL_VALUE"
  set_kv "RELAY_WS_HOST" "$RELAY_WS_HOST_VALUE"
  set_kv "RELAY_WS_PORT" "$RELAY_WS_PORT_VALUE"
  if [[ -n "${RELAY_AUTH_TOKEN_VALUE:-}" ]]; then
    set_kv "RELAY_AUTH_TOKEN" "$RELAY_AUTH_TOKEN_VALUE"
  fi
  set_kv "BRIDGE_ENABLE_FORWARD" "$FWD_VALUE"
  if [[ -n "${OPENCLAW_GATEWAY_URL_VALUE:-}" ]]; then
    set_kv "OPENCLAW_GATEWAY_URL" "$OPENCLAW_GATEWAY_URL_VALUE"
  fi
  if [[ -n "${OPENCLAW_HOOKS_TOKEN_VALUE:-}" ]]; then
    set_kv "OPENCLAW_HOOKS_TOKEN" "$OPENCLAW_HOOKS_TOKEN_VALUE"
  fi
  set_kv "BRIDGE_ENABLE_DISCOVERY" "$DISC_VALUE"
  if [[ -n "${BRIDGE_DISCOVERY_REGISTER_TOKEN_VALUE:-}" ]]; then
    set_kv "BRIDGE_DISCOVERY_REGISTER_TOKEN" "$BRIDGE_DISCOVERY_REGISTER_TOKEN_VALUE"
  fi
  if [[ -n "${BRIDGE_DISCOVERY_DISCOVER_TOKEN_VALUE:-}" ]]; then
    set_kv "BRIDGE_DISCOVERY_DISCOVER_TOKEN" "$BRIDGE_DISCOVERY_DISCOVER_TOKEN_VALUE"
  fi

  echo "[info] Updated $ENV_FILE"
  echo

  # 3. Use docker-compose to bring up the full stack
  local compose_bin
  compose_bin="$(detect_compose || true)"
  if [[ -z "${compose_bin:-}" ]]; then
    echo "[error] docker compose not found (need Docker Compose v2 or docker-compose)"
    exit 1
  fi
  echo "[info] Starting NATS + Relay + Solid + Bridge via compose ..."
  echo "  Compose file: $COMPOSE_FILE"
  $compose_bin -f "$COMPOSE_FILE" up -d --build

  echo
  echo "[done] Compose started, current container status:"
  docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "open-a2a|nats|solid" || true

  echo
  echo "Next steps in OpenClaw:"
  echo "  - Configure a Tool that calls the Bridge at /api/publish_intent"
  echo "  - Configure a webhook at $OPENCLAW_GATEWAY_URL_VALUE/hooks/agent with the provided token"
  echo "  - See docs/en/openclaw-tool-example.md or docs/zh/openclaw-tool-example.md for Tool + Hook details."
}

main "${1:-run}"
