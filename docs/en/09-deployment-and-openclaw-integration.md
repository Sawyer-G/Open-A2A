# Deployment & OpenClaw Integration Guide

> How to deploy Open-A2A on your server and integrate with OpenClaw or similar Agent runtimes.

---

## 1. Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        User Server (same host or LAN)                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────────────────┐   │
│   │   NATS      │     │ Solid Pod   │     │  OpenClaw (deployed)   │   │
│   │ Message Bus │     │ Preferences │     │  - Gateway             │   │
│   │ :4222       │     │ :8443       │     │  - WhatsApp/Telegram   │   │
│   └──────┬──────┘     └──────┬──────┘     │  - Agent + Tools       │   │
│          │                   │           └───────────┬─────────────┘   │
│          │                   │                       │                  │
│          ▼                   ▼                       ▼                  │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │              Open-A2A Bridge (adapter, Python process)         │  │
│   │  - Subscribe NATS intent topics → forward to OpenClaw /hooks   │  │
│   │  - Expose HTTP API → OpenClaw calls Tool → publish to NATS     │  │
│   └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Prerequisites

- OpenClaw is already deployed and its **Gateway** is reachable.
- Docker and Docker Compose are installed on the server (for the Docker path).
- Network connectivity: NATS, Solid, and OpenClaw can reach each other on the necessary ports.

---

## 3. One-Click Deploy (Docker Compose)

You can use the provided quickstart compose file and helper script to spin up a full node stack.

### 3.1 Using the helper script (recommended)

On the same server where OpenClaw is running:

```bash
git clone https://github.com/Sawyer-G/Open-A2A.git
cd Open-A2A

bash scripts/setup-openclaw-bridge.sh
```

The script will:

1. Create or update `.env` based on `.env.example`;
2. Prompt for `NATS_URL`, `OPENCLAW_GATEWAY_URL`, and `OPENCLAW_HOOKS_TOKEN`, then append them to `.env`;
3. Run:

```bash
docker compose -f deploy/quickstart/docker-compose.full.yml --env-file .env up -d --build
```

In addition, the script:

- Tries to auto-detect an OpenClaw Gateway container (by matching names that contain `gateway`) and uses it to propose a sensible default `OPENCLAW_GATEWAY_URL` (e.g. `http://openclaw-openclaw-gateway-1:18789`);
- Provides a `diagnose` subcommand to quickly check configuration and connectivity:

```bash
bash scripts/setup-openclaw-bridge.sh diagnose
```

`diagnose` will:

- Show `NATS_URL` / `OPENCLAW_GATEWAY_URL` / `OPENCLAW_HOOKS_TOKEN` from `.env`;
- Inspect environment variables inside the Bridge container;
- Test connectivity from the host to `OPENCLAW_GATEWAY_URL` via `curl`;
- Call `http://localhost:8080/health` to verify that Bridge can see NATS and (optionally) OpenClaw.

### 3.2 Manual docker-compose (equivalent to the script)

If you prefer to manage `.env` yourself:

```bash
git clone https://github.com/Sawyer-G/Open-A2A.git
cd Open-A2A

cp .env.example .env  # then edit .env as needed (NATS_URL / OPENCLAW_GATEWAY_URL / OPENCLAW_HOOKS_TOKEN)

docker compose -f deploy/quickstart/docker-compose.full.yml --env-file .env up -d --build
docker ps  # nats / relay / solid / open-a2a-bridge should be running
```

This compose file starts:

- `nats`: NATS message bus (`4222`);
- `relay`: Open-A2A Relay (`8765`, WebSocket outbound entrypoint);
- `solid`: self-hosted Solid Pod (`8443`);
- `open-a2a-bridge`: Bridge service (`8080`) for integration with OpenClaw or other runtimes.

### 3.4 Security defaults (public vs private)

This quickstart is meant to get an end-to-end demo running fast. If you plan to expose it publicly, keep the blast radius minimal:

- **Recommended public ports**:
  - Relay: `RELAY_WS_PORT` (default `8765`)
  - Bridge: `BRIDGE_PORT` (default `8080`, recommended behind an HTTPS reverse proxy)
- **Do NOT expose by default**:
  - NATS `4222` (quickstart keeps it private; if you need public NATS, use `deploy/node-x/` with stronger auth/ACL/TLS)
- **Strict mode requirements (recommended for public nodes)**:
  - `OA2A_STRICT_SECURITY=1`
  - `RELAY_AUTH_TOKEN` must be set
  - If discovery is enabled (`BRIDGE_ENABLE_DISCOVERY=1`), set `BRIDGE_DISCOVERY_REGISTER_TOKEN` and `BRIDGE_DISCOVERY_DISCOVER_TOKEN`

Additional note (more mature public shape):

- Relay can be scaled horizontally (multiple instances connected to the same NATS). Put a WebSocket-capable reverse proxy / load balancer in front and expose a single `wss://relay.<domain>`.

#### 3.4.1 Firewall / security group port matrix (recommended)

> Goal: make the “quickstart” not only runnable, but safely runnable by default. The table below reflects quickstart + DHT bootstrap.

| Component | Port | Proto | Public? | Notes |
|---|---:|---|---|---|
| Relay | 8765 | TCP | ✅ recommended | Outbound entrypoint for Agents; strict mode requires `RELAY_AUTH_TOKEN` |
| Bridge | 8080 | TCP | ⚠️ optional | HTTP API (recommended behind HTTPS reverse proxy); if not integrating OpenClaw, set `BRIDGE_ENABLE_FORWARD=0` |
| Solid | 8443 | TCP | ⚠️ optional | Self-hosted preferences; keep private if not needed |
| DHT bootstrap | 8469 | UDP | ✅ recommended | Cross-node discovery entry (recommended to at least open UDP) |
| DHT bootstrap | 8469 | TCP | ⚠️ optional | The kit currently exposes both TCP/UDP; you may later narrow to UDP-only after verification |
| NATS | 4222 | TCP | ❌ no | **Keep private** (Relay/Bridge use it via the Docker network). For public NATS access, use `deploy/node-x/` with stronger auth/ACL/TLS |

DNS notes:

- In Cloudflare, create A records for subdomains like `relay` / `dht` pointing to your server IP and set **DNS only** (especially for `dht:8469`, which cannot be proxied as HTTP).

### 3.3 Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `NATS_URL` | NATS address | `nats://localhost:4222` |
| `OPENCLAW_GATEWAY_URL` | OpenClaw Gateway URL | `http://localhost:3000` or `http://gateway:3000` |
| `OPENCLAW_HOOKS_TOKEN` | Webhook token configured in OpenClaw | same as `hooks.token` in `openclaw.json` |

---

## 4. Integration Modes

### 4.1 Mode A: Tool Integration (User-Initiated Intents)

**Scenario**: A user says to OpenClaw on WhatsApp/Telegram, “Help me order noodles.” The Agent calls an Open-A2A Tool to publish the intent into the network.

**Implementation**:

1. Deploy **Open-A2A Bridge** and expose HTTP API:

   ```http
   POST /api/publish_intent
   Content-Type: application/json

   {
     "action": "Food_Order",
     "type": "Noodle",
     "constraints": ["No_Coriander"],
     "lat": 31.23,
     "lon": 121.47,
     "collect_offers": true,
     "timeout_seconds": 10
   }
   ```

2. In OpenClaw, configure a **Tool** (or `http_request` tool):

   - Name: `open_a2a_publish_intent`
   - Call: `POST {OPEN_A2A_BRIDGE_URL}/api/publish_intent`
   - The Agent invokes this Tool when the user expresses an intent that should be broadcast to the Open-A2A network.

3. Other merchant/carrier Agents subscribe to NATS, receive the intent, and respond with Offers.

### 4.2 Mode B: Channel Integration (Receiving External Intents)

**Scenario**: Other Agents publish intents on NATS; an OpenClaw Agent should react (e.g., merchant Agent responding to “I want noodles”).

**Implementation**:

1. **Bridge** subscribes to NATS topics such as `intent.food.order`.

2. When it receives an `Intent`, Bridge calls OpenClaw's **Webhook**:

   ```http
   POST {OPENCLAW_GATEWAY_URL}/hooks/agent
   Headers:
     x-openclaw-token: {OPENCLAW_HOOKS_TOKEN}
     Content-Type: application/json

   Body:
   {
     "sessionKey": "open-a2a-intent-{intent_id}",
     "message": "Received intent: user wants noodles, constraints: No_Coriander. Please respond with an offer.",
     "channel": "open_a2a"
   }
   ```

3. OpenClaw Agent processes this message, generates an offer, and Bridge can publish that Offer back to NATS (e.g., on `intent.food.offer.{id}`).

### 4.3 Mode C: Combined (Full A-B-C Flow)

- **Consumer side**: User talks to OpenClaw (“order noodles”) → Agent calls the Open-A2A Tool → Bridge publishes Intent.
- **Merchant side**: OpenClaw (as a merchant Agent) receives forwarded intents via `/hooks/agent` → generates Offers → Bridge sends them back to NATS.
- **Carrier side**: A separate Carrier Agent can run with the Open-A2A SDK (Python) or also be integrated via Bridge.

---

## 5. Bridge Implementation

The Bridge is implemented in `bridge/main.py`.

| Feature | Implementation |
|---------|----------------|
| Subscribe intents | `IntentBroadcaster.subscribe_intents()`, then forward |
| Forward to OpenClaw | `httpx.post(gateway_url + "/hooks/agent", ...)` |
| Publish API | `POST /api/publish_intent`, optionally collects offers and returns them |
| Health check | `GET /health` |
| Ops metrics (JSON) | `GET /ops/metrics` (backend, online providers, capability distribution, etc.) |
| Ops metrics (Prometheus) | `GET /ops/metrics/prometheus` (normalized names for scraping) |
| Capability discovery (NATS) | `POST /api/register_capabilities`, `GET /api/discover` (request-reply, no central registry) |

**Run**:

```bash
make install-bridge && make run-bridge
# or
docker compose -f deploy/quickstart/docker-compose.full.yml --env-file .env up -d
```

**API example**:

```bash
curl -X POST http://localhost:8080/api/publish_intent \
  -H "Content-Type: application/json" \
  -d '{"type":"Noodle","constraints":["No_Coriander"],"collect_offers":true}'
```

For a concrete OpenClaw Tool configuration example, see `docs/zh/openclaw-tool-example.md`.

---

### 5.1 Normalized observability (Prometheus + reference table)

> Goal: Bridge / Relay / Federation (SubjectBridge) can all be scraped with one consistent metric naming scheme.

#### 5.1.1 Endpoint reference (keep private by default)

| Component | JSON snapshot | Prometheus metrics |
|---|---|---|
| Bridge (FastAPI) | `GET /health`, `GET /ops/metrics` | `GET /ops/metrics/prometheus` |
| Relay (ops HTTP) | `GET /healthz` | `GET /metrics` |
| SubjectBridge (ops HTTP) | `GET /healthz` | `GET /metrics` |

#### 5.1.2 Metric name spec (minimal set)

Bridge:

- `oa2a_bridge_up` (gauge)
- `oa2a_bridge_nats_connected` (gauge, 1/0)
- `oa2a_bridge_discovery_backend{backend="memory|file|redis"}` (gauge)
- `oa2a_bridge_discovery_providers_total` (gauge)
- `oa2a_bridge_discovery_providers_verified` (gauge)
- `oa2a_bridge_discovery_providers_unverified` (gauge)
- `oa2a_bridge_discovery_capabilities_total` (gauge)
- `oa2a_bridge_discovery_capability_providers{capability="..."}` (gauge)

Relay:

- `oa2a_relay_up` (gauge)
- `oa2a_relay_clients` (gauge)
- `oa2a_relay_nats_subject_subscriptions` (gauge)
- `oa2a_relay_auth_enabled` (gauge, 1/0)
- `oa2a_relay_ws_tls` (gauge, 1/0)

SubjectBridge (Federation):

- `oa2a_fed_up{bridge_id="..."}` (gauge)
- `oa2a_fed_a_to_b_forwarded_total{bridge_id="..."}` (counter)
- `oa2a_fed_b_to_a_forwarded_total{bridge_id="..."}` (counter)
- `oa2a_fed_skipped_self_total{bridge_id="..."}` (counter)
- `oa2a_fed_skipped_hop_total{bridge_id="..."}` (counter)
- `oa2a_fed_skipped_dedupe_total{bridge_id="..."}` (counter)
- `oa2a_fed_errors_total{bridge_id="..."}` (counter)

### 5.2 Directory registry (“always discoverable”, formerly Path B)

If you want other nodes to continuously discover your Agent (directory-style discovery), the simplest approach is:

- Keep Bridge running as a long-lived process;
- Register the Agent’s capabilities in NATS Discovery.

Bridge supports both:

1) **Auto-register on startup** (recommended):

- Configure:
  - `BRIDGE_ENABLE_DISCOVERY=1`
  - `BRIDGE_AGENT_ID=openclaw-agent`
  - `BRIDGE_CAPABILITIES=intent.food.order,intent.logistics.request` (comma-separated)
  - Optional: `BRIDGE_META_JSON='{"region":"shanghai","endpoint":"https://bridge.open-a2a.org"}'`

2) **Register/update via HTTP** (useful for OpenClaw Tool/Skill):

```bash
curl -X POST http://localhost:8080/api/register_capabilities \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"openclaw-agent","capabilities":["intent.food.order"],"meta":{"region":"shanghai"},"ttl_seconds":60}'
```

Other nodes can query:

```bash
curl "http://localhost:8080/api/discover?capability=intent.food.order&timeout_seconds=3" | jq .
```

Notes:

- NATS Discovery has **no global registry**; “register” is implemented by subscribing to `open_a2a.discovery.query.{capability}` and replying with `meta`.
- Therefore the Agent (or Bridge acting for it) must stay online to remain discoverable.

#### 5.2.1 Operator-grade features (TTL / auth / rate limit / observability)

To avoid “zombie registrations” and improve operability for public nodes, Bridge also provides:

- **TTL & expiration**: registrations expire if not renewed; renew by calling `POST /api/register_capabilities` again
- **Access control (optional)**: Bearer tokens for register/discover
- **Rate limiting (optional)**: simple per-IP limit (requests per minute)
- **Observability**: `GET /api/discovery_stats` for provider counts, capability distribution, and recent errors

Relevant environment variables are documented in `.env.example`:

- `BRIDGE_DISCOVERY_DEFAULT_TTL_SECONDS`
- `BRIDGE_DISCOVERY_CLEANUP_INTERVAL_SECONDS`
- `BRIDGE_DISCOVERY_REDIS_URL` (recommended: Redis registry backend for multi-instance/HA; when set, Bridge does not rely on in-memory/file registry)
- `BRIDGE_DISCOVERY_PERSIST_PATH` (optional: persist the directory registry for single-instance restart recovery; disabled by default)
- `BRIDGE_DISCOVERY_REGISTER_TOKEN` / `BRIDGE_DISCOVERY_DISCOVER_TOKEN`
- `BRIDGE_DISCOVERY_RL_PER_MINUTE`

#### 5.2.2 Recommended operator shapes (single instance / HA)

> Bridge already supports three registry backends: **in-memory / file persistence / Redis**. Below is the recommended operator guidance to make deployments copyable.

**Single instance (recommended to start: file persistence)**

- **When**: one node, low ops cost, you can accept a single point of failure but want the registry to survive restarts
- **Key config**:
  - Set `BRIDGE_DISCOVERY_PERSIST_PATH=/data/bridge_registry.json` (and mount a volume)
  - Leave `BRIDGE_DISCOVERY_REDIS_URL` empty
- **Pros**: minimal dependencies, fastest path to production
- **Cons**: still single instance (no native rolling upgrades)

**HA (recommended for public nodes: Redis backend + multiple instances)**

- **When**: public service, rolling upgrades, failover, multiple Bridge instances
- **Key config**:
  - Set `BRIDGE_DISCOVERY_REDIS_URL=redis://...`
  - Run multiple Bridge instances pointing to the same Redis
  - Put an HTTPS reverse proxy / load balancer (nginx/Caddy/Traefik) in front, exposing a single `bridge.open-a2a.org`
- **Pros**: shared registry, horizontal scaling
- **Cons**: adds Redis ops cost; plan backups/monitoring

Copyable artifacts:

- `deploy/bridge-directory-registry/` (single/HA docker-compose)
- `scripts/e2e-bridge-directory-registry.sh` (cross-container E2E checks)

#### 5.2.3 More systematic E2E (cross-process / cross-container)

From the repo root:

```bash
bash scripts/e2e-bridge-directory-registry.sh single-persist
bash scripts/e2e-bridge-directory-registry.sh redis-ha
```

If your environment cannot access Docker Hub (cannot pull `nats` / `redis` images), you can reuse an **already-running NATS/Redis**:

```bash
export E2E_EXTERNAL_NATS_URL="nats://host.docker.internal:4222"
export E2E_EXTERNAL_REDIS_URL="redis://host.docker.internal:6379/0"  # only needed for redis-ha-external

bash scripts/e2e-bridge-directory-registry.sh single-persist-external
bash scripts/e2e-bridge-directory-registry.sh redis-ha-external
```

What it verifies:

- `single-persist`: register → discover → restart Bridge → discover still hits (validates `BRIDGE_DISCOVERY_PERSIST_PATH`)
- `redis-ha`: register on Bridge-1 → discover on Bridge-2 (validates multi-instance consistency via `BRIDGE_DISCOVERY_REDIS_URL`)

---

## 5.1 Bare-metal deployment (advanced)

If you prefer **not** to use Docker on the server, you can run the Open-A2A Bridge directly on the host using the provided helper script:

```bash
git clone https://github.com/Sawyer-G/Open-A2A.git
cd Open-A2A

bash scripts/setup-openclaw-bridge-baremetal.sh
```

This script will:

- Ensure `python3` and `make` are available on the host;
- Create or update `.env` with `NATS_URL`, `OPENCLAW_GATEWAY_URL`, and `OPENCLAW_HOOKS_TOKEN`;
- Run `make install-bridge` to install Bridge dependencies into `.venv/`;
- Start the Bridge via `.venv/bin/uvicorn bridge.main:app --host 0.0.0.0 --port 8080` in the background, writing logs to `logs/bridge.log`.

Prerequisites:

- You already have a reachable NATS server (local or public) and set its address in `NATS_URL`;
- OpenClaw’s Gateway is reachable from this host at `OPENCLAW_GATEWAY_URL`.

After the script finishes, you can verify connectivity via:

```bash
curl http://localhost:8080/health | jq .
```

The Tool/Webhook configuration steps in OpenClaw are identical to the Docker deployment; the only difference is that `BRIDGE_URL` now points to the host (e.g. `http://<server-ip>:8080`) instead of a Docker container.

---

## 6. Networking and Security

| Aspect | Recommendation |
|--------|----------------|
| NATS exposure | In production, prefer limiting NATS to internal networks or using TLS + authentication. Only expose the client port (default `4222`) when you intend to let external Agents connect directly. |
| Solid | Use real TLS certificates and restrict access. |
| OpenClaw Gateway | Ensure `hooks.token` (or equivalent) is configured correctly; Bridge must send it with each webhook call. |
| Bridge | Prefer exposing Bridge via a reverse proxy (nginx/Caddy/Traefik) rather than directly to the public Internet. |

---

## 7. Coexistence with Existing Services

If the server already has:

- **NATS**: Reuse it; point `NATS_URL` to the existing instance.
- **OpenClaw**: No need to modify its deployment; just configure Tools/Webhooks to point to Bridge.
- **Solid**: Optional; if you already run a self-hosted Solid Pod, configure `SOLID_*` env vars.
- **Other Agent runtimes**: Integrate via Bridge HTTP API or by subscribing to NATS directly.

---

## 8. Public Entry Nodes, Domains, and Decentralization

From an operations perspective, the Open-A2A network will often include a small number of **public entry nodes**:

- NATS / Relay / Bridge / DHT bootstrap nodes operated by the project or community.
- Bound to one or more domain names (e.g., `nats.example.net`, `relay.example.net`, `bridge.example.net`).
- Used in docs and SDK examples as the default `NATS_URL` / `RELAY_WS_URL` / `OPEN_A2A_BRIDGE_URL`.

This **does not contradict** the decentralization goal, because:

- At the protocol level, anyone can run their own nodes; Agents are free to connect to different operators.
- There is no requirement that traffic must go through a single official node; users and communities can stand up alternative infrastructure.
- This mirrors common Web3 practice (Ethereum RPC providers, IPFS bootstrap nodes, etc.): public endpoints lower the barrier to entry but are not the only way to participate.

For end-users:

- Typical users / devices (behind NAT, WiFi, dynamic IPs) should only need **outbound connectivity** to some public entry (NATS / Relay / Bridge) and do not need to open ports on their own routers.
- A smaller number of advanced users or organizations can operate public nodes and publish connection details; together they form a broader, multi-operator Open-A2A network.

---

## 9. Next Steps

1. ✅ Implement the full **Open-A2A Bridge** (with Dockerfile).
2. ✅ Provide an **OpenClaw Tool** configuration example (see `docs/zh/openclaw-tool-example.md`).
3. Plan a **TypeScript SDK** or HTTP client for OpenClaw/ZeroClaw to call Open-A2A more directly (see `07-multi-language-sdk.md`).
