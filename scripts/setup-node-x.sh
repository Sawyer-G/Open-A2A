#!/usr/bin/env bash
set -euo pipefail

# Node X operator kit bootstrapper
#
# Goals:
# - Generate strong secrets/tokens
# - Write them into repo-root .env
# - Keep deploy/node-x/nats.conf passwords in sync with .env
# - Reduce manual steps for operators (while keeping strict security gates)
#
# Usage:
#   bash scripts/setup-node-x.sh init
#   bash scripts/setup-node-x.sh rotate  # rotate secrets (updates .env + nats.conf)
#
# Notes:
# - This script never prints secrets unless you pass SHOW_SECRETS=1.
# - It edits files in-place. Git users: review diff after running.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ACTION="${1:-}"
if [[ -z "$ACTION" ]]; then
  echo "Usage: $0 {init|rotate}" >&2
  exit 2
fi

ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"
ENV_TEMPLATE="${ENV_TEMPLATE:-$ROOT_DIR/deploy/node-x/.env.node-x.example}"
NATS_CONF="${NATS_CONF:-$ROOT_DIR/deploy/node-x/nats.conf}"

SHOW_SECRETS="${SHOW_SECRETS:-0}"
if [[ "$SHOW_SECRETS" == "1" || "$SHOW_SECRETS" == "true" || "$SHOW_SECRETS" == "yes" ]]; then
  SHOW_SECRETS=1
else
  SHOW_SECRETS=0
fi

need_cmd() { command -v "$1" >/dev/null 2>&1 || { echo "[error] missing command: $1" >&2; exit 1; }; }
need_cmd awk
need_cmd sed

rand_token() {
  # Prefer openssl if available; fallback to python.
  if command -v openssl >/dev/null 2>&1; then
    # 32 bytes -> 43 chars base64url-ish after trimming
    openssl rand -base64 32 | tr -d '\n' | tr '+/' '-_' | tr -d '='
  else
    python - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
  fi
}

rand_pass() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -base64 24 | tr -d '\n' | tr '+/' '-_' | tr -d '='
  else
    python - <<'PY'
import secrets
print(secrets.token_urlsafe(24))
PY
  fi
}

ensure_env_file() {
  if [[ -f "$ENV_FILE" ]]; then
    return 0
  fi
  if [[ ! -f "$ENV_TEMPLATE" ]]; then
    echo "[error] env template not found: $ENV_TEMPLATE" >&2
    exit 2
  fi
  cp "$ENV_TEMPLATE" "$ENV_FILE"
  echo "[info] created $ENV_FILE from template"
}

set_kv() {
  local key="$1"
  local val="$2"
  # Replace existing KEY=... line; else append.
  if grep -qE "^${key}=" "$ENV_FILE" 2>/dev/null; then
    # BSD/macOS sed compatible: use -i ''.
    sed -i '' -E "s|^${key}=.*|${key}=${val}|g" "$ENV_FILE"
  else
    printf "\n%s=%s\n" "$key" "$val" >>"$ENV_FILE"
  fi
}

get_kv() {
  local key="$1"
  awk -F= -v k="$key" 'BEGIN{v=""} $0 ~ ("^"k"=") {sub("^"k"=","",$0); v=$0} END{print v}' "$ENV_FILE" 2>/dev/null || true
}

is_placeholder() {
  local v="${1:-}"
  [[ -z "$v" || "$v" == change-me-* ]]
}

sync_nats_conf_password() {
  local user="$1"
  local pass="$2"
  if [[ ! -f "$NATS_CONF" ]]; then
    echo "[error] nats.conf not found: $NATS_CONF" >&2
    exit 2
  fi
  # Replace password for a given user block:
  #   user: "relay"
  #   password: "..."
  #
  # This is a best-effort textual replace scoped by user line proximity.
  perl -0777 -i -pe "s/(user:\\s*\"$user\"\\s*\\n\\s*password:\\s*\")([^\"]*)(\")/\\1$pass\\3/g" "$NATS_CONF"
}

need_cmd perl

ensure_env_file

echo "== Node X setup =="
echo "  ENV_FILE:   $ENV_FILE"
echo "  NATS_CONF:  $NATS_CONF"
echo

if [[ "$ACTION" != "init" && "$ACTION" != "rotate" ]]; then
  echo "[error] unknown action: $ACTION" >&2
  exit 2
fi

# Generate or reuse (init tries to keep non-placeholder values; rotate always regenerates)
gen_or_keep() {
  local key="$1"
  local kind="$2" # token|pass
  local current
  current="$(get_kv "$key")"
  if [[ "$ACTION" == "rotate" || $(is_placeholder "$current"; echo $?) -eq 0 ]]; then
    if [[ "$kind" == "token" ]]; then
      set_kv "$key" "$(rand_token)"
    else
      set_kv "$key" "$(rand_pass)"
    fi
  fi
}

# Core secrets
gen_or_keep "NATS_RELAY_PASS" "pass"
gen_or_keep "NATS_BRIDGE_PASS" "pass"
gen_or_keep "NATS_PUBLIC_PASS" "pass"
gen_or_keep "RELAY_AUTH_TOKEN" "token"
gen_or_keep "BRIDGE_DISCOVERY_REGISTER_TOKEN" "token"
gen_or_keep "BRIDGE_DISCOVERY_DISCOVER_TOKEN" "token"

# Keep NATS usernames aligned with nats.conf defaults unless operator changed them.
NATS_RELAY_USER="$(get_kv "NATS_RELAY_USER")"
NATS_BRIDGE_USER="$(get_kv "NATS_BRIDGE_USER")"
NATS_PUBLIC_USER="$(get_kv "NATS_PUBLIC_USER")"
NATS_RELAY_USER="${NATS_RELAY_USER:-relay}"
NATS_BRIDGE_USER="${NATS_BRIDGE_USER:-bridge}"
NATS_PUBLIC_USER="${NATS_PUBLIC_USER:-agent_public}"

# Sync nats.conf passwords
relay_pass="$(get_kv "NATS_RELAY_PASS")"
bridge_pass="$(get_kv "NATS_BRIDGE_PASS")"
public_pass="$(get_kv "NATS_PUBLIC_PASS")"

sync_nats_conf_password "$NATS_RELAY_USER" "$relay_pass"
sync_nats_conf_password "$NATS_BRIDGE_USER" "$bridge_pass"
sync_nats_conf_password "$NATS_PUBLIC_USER" "$public_pass"

echo "[info] synced deploy/node-x/nats.conf passwords with .env"

if [[ "$SHOW_SECRETS" -eq 1 ]]; then
  echo
  echo "== Generated/Current secrets =="
  echo "  NATS_RELAY_PASS=$relay_pass"
  echo "  NATS_BRIDGE_PASS=$bridge_pass"
  echo "  NATS_PUBLIC_PASS=$public_pass"
  echo "  RELAY_AUTH_TOKEN=$(get_kv "RELAY_AUTH_TOKEN")"
  echo "  BRIDGE_DISCOVERY_REGISTER_TOKEN=$(get_kv "BRIDGE_DISCOVERY_REGISTER_TOKEN")"
  echo "  BRIDGE_DISCOVERY_DISCOVER_TOKEN=$(get_kv "BRIDGE_DISCOVERY_DISCOVER_TOKEN")"
else
  echo "[info] secrets written to $ENV_FILE (set SHOW_SECRETS=1 to print)"
fi

echo
echo "[next]"
echo "  docker compose -f deploy/node-x/docker-compose.node-x.yml --env-file \"$ENV_FILE\" up -d --build"
echo "  bash scripts/diagnose-node-x.sh"

