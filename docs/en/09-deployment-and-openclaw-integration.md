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
- Docker and Docker Compose are installed on the server.
- Network connectivity: NATS, Solid, and OpenClaw can reach each other on the necessary ports.

---

## 3. One-Click Deploy (Docker Compose)

At the project root, you can use the provided `docker-compose.deploy.yml`:

```yaml
# Open-A2A full deployment (NATS + Solid + Bridge)
# Designed to work alongside an existing OpenClaw deployment.

services:
  nats:
    image: nats:latest
    ports:
      - "4222:4222"
    restart: unless-stopped

  solid:
    image: aveltens/solid-server:latest
    ports:
      - "8443:8443"
    restart: unless-stopped

  open-a2a-bridge:
    build:
      context: .
      dockerfile: Dockerfile.bridge
    ports:
      - "8080:8080"
    environment:
      - NATS_URL=nats://nats:4222
      - OPENCLAW_GATEWAY_URL=${OPENCLAW_GATEWAY_URL:-}
      - OPENCLAW_HOOKS_TOKEN=${OPENCLAW_HOOKS_TOKEN:-}
      - BRIDGE_ENABLE_FORWARD=${BRIDGE_ENABLE_FORWARD:-1}
    depends_on:
      - nats
    restart: unless-stopped
```

### 3.1 Environment Variables

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

**Run**:

```bash
make install-bridge && make run-bridge
# or
docker compose -f docker-compose.deploy.yml up -d
```

**API example**:

```bash
curl -X POST http://localhost:8080/api/publish_intent \
  -H "Content-Type: application/json" \
  -d '{"type":"Noodle","constraints":["No_Coriander"],"collect_offers":true}'
```

For a concrete OpenClaw Tool configuration example, see `docs/zh/openclaw-tool-example.md`.

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
