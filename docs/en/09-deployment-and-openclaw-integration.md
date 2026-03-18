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

### 5.2 “Always discoverable” via capability registration

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
  -d '{"agent_id":"openclaw-agent","capabilities":["intent.food.order"],"meta":{"region":"shanghai"}}'
```

Other nodes can query:

```bash
curl "http://localhost:8080/api/discover?capability=intent.food.order&timeout_seconds=3" | jq .
```

Notes:

- NATS Discovery has **no global registry**; “register” is implemented by subscribing to `open_a2a.discovery.query.{capability}` and replying with `meta`.
- Therefore the Agent (or Bridge acting for it) must stay online to remain discoverable.

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
