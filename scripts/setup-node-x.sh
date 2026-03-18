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

NONINTERACTIVE="${OA2A_SETUP_NONINTERACTIVE:-0}"
if [[ "$NONINTERACTIVE" == "1" || "$NONINTERACTIVE" == "true" || "$NONINTERACTIVE" == "yes" ]]; then
  NONINTERACTIVE=1
else
  NONINTERACTIVE=0
fi

SHOW_SECRETS="${SHOW_SECRETS:-0}"
if [[ "$SHOW_SECRETS" == "1" || "$SHOW_SECRETS" == "true" || "$SHOW_SECRETS" == "yes" ]]; then
  SHOW_SECRETS=1
else
  SHOW_SECRETS=0
fi

need_cmd() { command -v "$1" >/dev/null 2>&1 || { echo "[error] missing command: $1" >&2; exit 1; }; }
need_cmd awk
need_cmd sed

is_truthy() {
  local v="${1:-}"
  v="$(echo "$v" | tr '[:upper:]' '[:lower:]' | xargs)"
  [[ "$v" == "1" || "$v" == "true" || "$v" == "yes" || "$v" == "y" || "$v" == "on" ]]
}

prompt() {
  local label="$1"
  local def="${2:-}"
  local secret="${3:-0}"
  local input=""
  if [[ "$NONINTERACTIVE" -eq 1 ]]; then
    echo "$def"
    return 0
  fi
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

prompt_yesno() {
  local label="$1"
  local def="${2:-1}" # 1=yes, 0=no
  local def_txt="1"
  if [[ "$def" == "0" ]]; then
    def_txt="0"
  fi
  local v
  v="$(prompt "$label [1/0]" "$def_txt" 0)"
  if is_truthy "$v"; then
    echo "1"
  else
    echo "0"
  fi
}

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

# Optional interactive wizard (only for init).
if [[ "$ACTION" == "init" && "$NONINTERACTIVE" -eq 0 ]]; then
  echo "== Node X init wizard =="
  echo
  echo "This wizard will help you produce a safer default operator node:"
  echo "  - NATS stays private by default (only Relay/Bridge use it)."
  echo "  - Relay is the recommended public entry (WS/WSS)."
  echo "  - Bridge can provide Directory Registry APIs (register/discover) with optional auth."
  echo

  # Strict security default to enabled for operator nodes.
  strict_current="$(get_kv "OA2A_STRICT_SECURITY")"
  strict_default="1"
  if [[ -n "${strict_current:-}" ]]; then
    if is_truthy "$strict_current"; then
      strict_default="1"
    else
      strict_default="0"
    fi
  fi
  strict_value="$(prompt_yesno "Enable OA2A_STRICT_SECURITY (recommended for public nodes)" "$strict_default")"
  set_kv "OA2A_STRICT_SECURITY" "$strict_value"

  # Relay ops endpoint (recommended to keep private / localhost only).
  echo
  relay_ops_enable_current="$(get_kv "RELAY_HTTP_ENABLE")"
  relay_ops_enable_default="1"
  if [[ -n "${relay_ops_enable_current:-}" ]]; then
    if is_truthy "$relay_ops_enable_current"; then
      relay_ops_enable_default="1"
    else
      relay_ops_enable_default="0"
    fi
  fi
  relay_ops_enable="$(prompt_yesno "Enable Relay ops endpoint (/healthz, /metrics) (keep private)" "$relay_ops_enable_default")"
  set_kv "RELAY_HTTP_ENABLE" "$relay_ops_enable"
  if [[ "$relay_ops_enable" == "1" ]]; then
    relay_ops_host="$(get_kv "RELAY_HTTP_HOST")"
    relay_ops_host="${relay_ops_host:-127.0.0.1}"
    relay_ops_port="$(get_kv "RELAY_HTTP_PORT")"
    relay_ops_port="${relay_ops_port:-8766}"
    relay_ops_host="$(prompt "Relay ops bind host (recommended 127.0.0.1)" "$relay_ops_host" 0)"
    relay_ops_port="$(prompt "Relay ops port" "$relay_ops_port" 0)"
    set_kv "RELAY_HTTP_HOST" "$relay_ops_host"
    set_kv "RELAY_HTTP_PORT" "$relay_ops_port"
  fi

  # Bridge public endpoint hint: used for meta JSON only (not a secret).
  bridge_port="$(get_kv "BRIDGE_PORT")"
  bridge_port="${bridge_port:-8080}"
  set_kv "BRIDGE_PORT" "$bridge_port"
  bridge_public_host="$(get_kv "BRIDGE_PUBLIC_HOST")"
  bridge_public_host="${bridge_public_host:-}"
  bridge_public_host="$(prompt "Optional: BRIDGE_PUBLIC_HOST (domain or IP, used to build meta endpoint)" "$bridge_public_host" 0)"
  if [[ -n "${bridge_public_host:-}" ]]; then
    set_kv "BRIDGE_PUBLIC_HOST" "$bridge_public_host"
  fi

  # Identity/Trust (RFC-004): meta proof (optional but recommended for public directory-style discovery).
  echo
  meta_proof_current="$(get_kv "BRIDGE_ENABLE_META_PROOF")"
  meta_proof_default="0"
  if [[ -n "${meta_proof_current:-}" ]]; then
    if is_truthy "$meta_proof_current"; then
      meta_proof_default="1"
    else
      meta_proof_default="0"
    fi
  fi
  meta_proof_enable="$(prompt_yesno "Enable BRIDGE_ENABLE_META_PROOF (RFC-004 verifiable meta)?" "$meta_proof_default")"
  set_kv "BRIDGE_ENABLE_META_PROOF" "$meta_proof_enable"
  if [[ "$meta_proof_enable" == "1" ]]; then
    # Public URL is recommended so meta can point to a stable operator endpoint (not secret).
    bridge_public_url="$(get_kv "BRIDGE_PUBLIC_URL")"
    if [[ -z "${bridge_public_url:-}" && -n "${bridge_public_host:-}" ]]; then
      bridge_public_url="https://${bridge_public_host}"
    fi
    bridge_public_url="$(prompt "Optional: BRIDGE_PUBLIC_URL (recommended for public nodes)" "$bridge_public_url" 0)"
    if [[ -n "${bridge_public_url:-}" ]]; then
      set_kv "BRIDGE_PUBLIC_URL" "$bridge_public_url"
    fi

    echo
    echo "[info] Stable identity across restarts (recommended): set BRIDGE_DID_SEED_B64."
    echo "       - Keep it secret. Do NOT commit it to git."
    echo "       - If empty, Bridge may generate a new DID on each restart."
    did_seed_current="$(get_kv "BRIDGE_DID_SEED_B64")"
    did_seed_value="$(prompt "Optional: paste BRIDGE_DID_SEED_B64 (base64 seed)" "$did_seed_current" 1)"
    if [[ -n "${did_seed_value:-}" ]]; then
      set_kv "BRIDGE_DID_SEED_B64" "$did_seed_value"
    fi
  fi

  # Directory Registry auth tokens: in strict mode, we strongly recommend enabling.
  disc_enable="$(get_kv "BRIDGE_ENABLE_DISCOVERY")"
  if [[ -z "${disc_enable:-}" ]]; then
    disc_enable="1"
  fi
  if is_truthy "$disc_enable"; then
    disc_enable="1"
  else
    disc_enable="0"
  fi
  disc_enable="$(prompt_yesno "Enable BRIDGE_ENABLE_DISCOVERY (recommended for operator nodes)" "$disc_enable")"
  set_kv "BRIDGE_ENABLE_DISCOVERY" "$disc_enable"

  if [[ "$disc_enable" == "1" ]]; then
    echo
    bridge_agent_id="$(get_kv "BRIDGE_AGENT_ID")"
    bridge_agent_id="${bridge_agent_id:-node-x-bridge}"
    bridge_agent_id="$(prompt "Bridge agent id (BRIDGE_AGENT_ID)" "$bridge_agent_id" 0)"
    set_kv "BRIDGE_AGENT_ID" "$bridge_agent_id"

    bridge_caps="$(get_kv "BRIDGE_CAPABILITIES")"
    bridge_caps="${bridge_caps:-intent.food.order,intent.logistics.request}"
    bridge_caps="$(prompt "Bridge capabilities (comma-separated) (BRIDGE_CAPABILITIES)" "$bridge_caps" 0)"
    set_kv "BRIDGE_CAPABILITIES" "$bridge_caps"

    # TTL / cleanup interval (directory quality).
    echo
    echo "[info] Directory Registry TTL controls how long entries stay \"online\" without renewal."
    echo "       Shorter TTL => better freshness but requires more frequent renewals."
    ttl_current="$(get_kv "BRIDGE_DISCOVERY_DEFAULT_TTL_SECONDS")"
    ttl_current="${ttl_current:-60}"
    ttl_value="$(prompt "Default TTL (seconds) for discovery entries (BRIDGE_DISCOVERY_DEFAULT_TTL_SECONDS)" "$ttl_current" 0)"
    set_kv "BRIDGE_DISCOVERY_DEFAULT_TTL_SECONDS" "$ttl_value"

    cleanup_current="$(get_kv "BRIDGE_DISCOVERY_CLEANUP_INTERVAL_SECONDS")"
    cleanup_current="${cleanup_current:-5}"
    cleanup_value="$(prompt "Cleanup interval (seconds) for pruning expired entries (BRIDGE_DISCOVERY_CLEANUP_INTERVAL_SECONDS)" "$cleanup_current" 0)"
    set_kv "BRIDGE_DISCOVERY_CLEANUP_INTERVAL_SECONDS" "$cleanup_value"
  fi

  if [[ "$strict_value" == "1" && "$disc_enable" == "1" ]]; then
    echo
    echo "[info] Strict mode + discovery enabled: recommend enabling auth tokens for Directory Registry APIs."
    auth_enable="$(prompt_yesno "Enable Directory Registry auth tokens (register/discover)" 1)"
    if [[ "$auth_enable" == "1" ]]; then
      # Tokens will be generated below by gen_or_keep; here we only ensure keys exist.
      :
    else
      # Explicitly clear to avoid confusion in strict mode.
      set_kv "BRIDGE_DISCOVERY_REGISTER_TOKEN" ""
      set_kv "BRIDGE_DISCOVERY_DISCOVER_TOKEN" ""
    fi
  fi

  # Federation (optional): ask for remote NATS if operator wants X↔Y.
  echo
  fed_enable="$(prompt_yesno "Optional: configure federation (X↔Y subject bridge) now?" 0)"
  if [[ "$fed_enable" == "1" ]]; then
    set_kv "OA2A_FED_SUBJECTS" "$(get_kv "OA2A_FED_SUBJECTS")"
    if [[ -z "$(get_kv "OA2A_FED_SUBJECTS")" ]]; then
      set_kv "OA2A_FED_SUBJECTS" "intent.>"
    fi
    fed_b="$(get_kv "OA2A_FED_NATS_B")"
    fed_b="$(prompt "Paste OA2A_FED_NATS_B (remote operator Y NATS URL)" "$fed_b" 0)"
    if [[ -n "${fed_b:-}" ]]; then
      set_kv "OA2A_FED_NATS_B" "$fed_b"
    fi
  fi

  echo
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

# If we have a public host hint, keep BRIDGE_META_JSON in sync (best-effort).
bridge_public_host_val="$(get_kv "BRIDGE_PUBLIC_HOST")"
bridge_public_url_val="$(get_kv "BRIDGE_PUBLIC_URL")"
bridge_port_val="$(get_kv "BRIDGE_PORT")"
bridge_port_val="${bridge_port_val:-8080}"
bridge_agent_id_val="$(get_kv "BRIDGE_AGENT_ID")"
bridge_caps_val="$(get_kv "BRIDGE_CAPABILITIES")"
bridge_caps_json="[]"
if [[ -n "${bridge_caps_val:-}" ]]; then
  # Build JSON array from comma-separated list (best-effort, no external deps).
  bridge_caps_json="$(CAPS="$bridge_caps_val" python - <<'PY' 2>/dev/null || true
import os, json
caps = os.environ.get("CAPS","")
out=[]
for s in caps.split(","):
  s=s.strip()
  if s:
    out.append(s)
print(json.dumps(out, ensure_ascii=False))
PY
)"
  if [[ -z "${bridge_caps_json:-}" ]]; then
    bridge_caps_json="[]"
  fi
fi

bridge_endpoint=""
if [[ -n "${bridge_public_url_val:-}" ]]; then
  bridge_endpoint="${bridge_public_url_val}"
elif [[ -n "${bridge_public_host_val:-}" ]]; then
  bridge_endpoint="http://${bridge_public_host_val}:${bridge_port_val}"
fi

if [[ -n "${bridge_endpoint:-}" ]]; then
  # Build a minimal meta document (best-effort) aligned with RFC-004 guidance.
  # Note: meta proof is attached by Bridge at runtime when enabled.
  meta_json="$(AGENT_ID="$bridge_agent_id_val" CAPS_JSON="$bridge_caps_json" ENDPOINT="$bridge_endpoint" python - <<'PY' 2>/dev/null || true
import os, json
agent_id=os.environ.get("AGENT_ID","")
caps_json=os.environ.get("CAPS_JSON","[]")
endpoint=os.environ.get("ENDPOINT","")
try:
  caps=json.loads(caps_json)
except Exception:
  caps=[]
meta={"agent_id":agent_id,"capabilities":caps,"endpoints":[{"type":"http","url":endpoint}]}
print(json.dumps(meta, ensure_ascii=False))
PY
)"
  if [[ -n "${meta_json:-}" ]]; then
    set_kv "BRIDGE_META_JSON" "$meta_json"
  fi
fi

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

