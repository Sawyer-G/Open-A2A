# OpenClaw Integration with Open-A2A (Quick Guide)

> This document is for users who already have **OpenClaw** running locally or on a server and want to integrate it with the **Open-A2A** framework so that their Agents can discover and collaborate with other Agents across networks.

---

## 1. High-Level Integration Model

- **OpenClaw handles**: user conversations, reasoning, tool calling, and session management.
- **Open-A2A handles**: cross-network Agent-to-Agent protocol and transport (NATS/Relay/Discovery, etc.).

There are two complementary integration modes:

1. **Tool mode**: OpenClaw calls an HTTP Tool → Bridge → Open-A2A network (broadcast intents, collect responses).
2. **Channel mode**: External Agents publish intents on the Open-A2A network → Bridge → OpenClaw `/hooks/agent` (OpenClaw acts as an Agent in the network).

---

## 2. Prerequisites

- OpenClaw is running locally or on a server, and its Gateway is reachable (e.g. `http://localhost:3000`).
- You have a NATS node available (local NATS or a public node such as `nats://...`).
- On the same machine as OpenClaw, run the Open-A2A Bridge (ideally via `docker-compose.deploy.yml`):

### 2.1 One-click Bridge setup (script, optional)

If you prefer not to edit `.env` and docker-compose manually, you can use the helper script:

```bash
git clone https://github.com/Sawyer-G/Open-A2A.git
cd Open-A2A

bash scripts/setup-openclaw-bridge.sh
```

The script will:

- Create or update `.env` based on `.env.example`;
- Prompt for `NATS_URL` / `OPENCLAW_GATEWAY_URL` / `OPENCLAW_HOOKS_TOKEN` and append them to `.env`;
- Run `docker-compose -f docker-compose.deploy.yml up -d --build` to start `nats + relay + solid + open-a2a-bridge`.

After it finishes, you can check container status with `docker ps`, then continue in this document to configure OpenClaw Tools and Hooks.

### 2.2 Manual docker-compose (equivalent to the script)

```bash
git clone https://github.com/Sawyer-G/Open-A2A.git
cd Open-A2A

cp .env.example .env  # then edit .env to set NATS_URL / OPENCLAW_GATEWAY_URL / OPENCLAW_HOOKS_TOKEN

docker-compose -f docker-compose.deploy.yml up -d --build

docker ps  # you should see nats / relay / solid / open-a2a-bridge containers
```

By default, Bridge listens on `http://localhost:8080` and connects to NATS via `NATS_URL` (local or public).

> **Note**: If you use Bridge's "forward intents to OpenClaw" feature (Channel integration), you may need to enable `hooks.allowRequestSessionKey=true` in OpenClaw so that external sessions can use custom `sessionKey` values.

---

## 3. Tool Mode: OpenClaw Initiates Intents via Open-A2A

### 3.1 Configure an HTTP Tool in OpenClaw

If OpenClaw supports an `http_request` (or similar HTTP call) tool, you can configure:

- **Tool name**: `open_a2a_publish_intent`

- **Call**:

  ```http
  POST {BRIDGE_URL}/api/publish_intent
  Content-Type: application/json

  {
    "action": "Generic_Request",
    "type": "Noodle",
    "constraints": ["No_Coriander", "<30min"],
    "lat": 31.23,
    "lon": 121.47,
    "collect_offers": true,
    "timeout_seconds": 10
  }
  ```

Where:

- `{BRIDGE_URL}` is typically `http://localhost:8080` (if Bridge runs on the same host);
- `type` / `constraints` / `lat` / `lon` are filled by the OpenClaw Agent based on the user conversation.

**Tool description** (for the Agent), for example:

```text
Publish an intent into the Open-A2A network. When the user asks to find a service
(e.g. "order noodles", "find a courier", "find a provider for X"), call this tool
to broadcast the intent and collect responses from other Agents.

Parameters:
- type: category of the request (e.g. "Noodle", "Food_Delivery", "Generic_Service")
- constraints: list of constraints (e.g. "No_Coriander", "<30min", "budget<20")
- lat/lon: approximate location of the user
```

### 3.2 YAML Configuration Example

If OpenClaw uses YAML for tool configuration, a minimal config might look like:

```yaml
tools:
  - name: open_a2a_publish_intent
    type: http_request
    description: Publish an intent to the Open-A2A network and collect responses from other Agents. Use when the user wants to find a provider or service via Open-A2A.
    config:
      url: "http://localhost:8080/api/publish_intent"
      method: POST
      headers:
        Content-Type: application/json
```

In practice you will want to map OpenClaw Agent slots (e.g. food type, constraints, location) into the JSON body.

### 3.3 Response Format (Example)

Bridge returns a JSON payload like:

```json
{
  "intent_id": "uuid-xxx",
  "offers_count": 2,
  "offers": [
    {
      "id": "offer-1",
      "intent_id": "uuid-xxx",
      "price": 18,
      "unit": "UNIT",
      "description": "Handmade noodles"
    }
  ],
  "message": "Intent published, 2 offers received"
}
```

The Agent can:

- Read `offers_count` to know how many responses were received;
- Iterate over `offers` to summarize or compare price/ETA/options;
- Present a shortlist to the user and ask which offer they prefer, then proceed (e.g. send an `OrderConfirm` via another Tool or follow-up action).

---

## 4. Channel Mode: OpenClaw as an Agent in the Open-A2A Network

In channel mode, external Agents publish intents into the Open-A2A network, and Bridge forwards those intents to OpenClaw:

1. **Bridge subscribes to NATS intent subjects** (e.g. `intent.food.order` or any domain-specific `intent.*` subjects).  
2. When an `Intent` is received, Bridge calls:

   ```http
   POST {OPENCLAW_GATEWAY_URL}/hooks/agent
   Headers:
     x-openclaw-token: {OPENCLAW_HOOKS_TOKEN}
     Content-Type: application/json

   Body:
   {
     "sessionKey": "open-a2a-intent-{intent_id}",
     "message": "Received an intent from the Open-A2A network: ... (summary derived from the Intent)",
     "channel": "open_a2a"
   }
   ```

3. OpenClaw treats this as a message on the `open_a2a` channel and passes it to the Agent;  
4. The Agent can:
   - Read the summarized message and (optionally) the structured fields of the Intent;
   - Decide whether to accept, quote a price, ask follow-up questions, etc.;
   - Use another Tool (e.g. `open_a2a_reply_offer`) to send its response back into the Open-A2A network.

> The exact message format for replies (Offers, LogisticsAccept, etc.) can reuse existing Open-A2A models or be extended per domain. The key point is: OpenClaw only sees HTTP Hooks; NATS/Relay details are handled by the Bridge.

---

## 5. Summary: How OpenClaw Uses Open-A2A

- **Initiating collaboration**:
  - The user tells OpenClaw “help me find an Agent that can do X”;  
  - The OpenClaw Agent calls the `open_a2a_publish_intent` Tool;  
  - Bridge broadcasts the intent into the Open-A2A network and returns responses;  
  - OpenClaw summarizes and presents options to the user.

- **Participating in collaboration**:
  - External Agents publish intents on Open-A2A;  
  - Bridge converts these intents into `hooks/agent` messages for OpenClaw;  
  - The OpenClaw Agent handles them like any other channel, and can respond back via Bridge.

From OpenClaw's perspective, integrating with Open-A2A only requires:

- Running the Bridge (Docker or local Python) connected to a NATS node; and  
- Configuring **one HTTP Tool** and **one Webhook**.  

All lower-level concerns (NATS/Relay/DHT/Discovery) are encapsulated by the Open-A2A layer and your existing public or local nodes.

