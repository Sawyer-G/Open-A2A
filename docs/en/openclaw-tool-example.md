# OpenClaw Open-A2A Tool Configuration Example

> Configure Open-A2A's `publish_intent` as a Tool that OpenClaw Agents can call.

---

## 1. Prerequisites

- Open-A2A Bridge is running (e.g. `http://localhost:8080`).
- OpenClaw is deployed and allows configuring custom Tools.

**Note**: If you also use Bridge's "forward intents to OpenClaw" feature (Channel integration), you may need to enable `hooks.allowRequestSessionKey=true` in OpenClaw, depending on your webhook configuration.

---

## 2. Using an `http_request` Tool

If OpenClaw supports an `http_request` (or similar HTTP call) tool, you can configure:

- **Tool name**: `open_a2a_publish_intent`

- **Call**:

  ```http
  POST {BRIDGE_URL}/api/publish_intent
  Content-Type: application/json

  {
    "type": "Noodle",
    "constraints": ["No_Coriander", "<30min"],
    "lat": 31.23,
    "lon": 121.47,
    "collect_offers": true,
    "timeout_seconds": 10
  }
  ```

- **Tool description** (for the Agent):

  ```text
  Publish an intent into the Open-A2A network. When the user expresses a desire
  for some food (e.g. noodles, rice) or a general service, call this tool to
  broadcast the intent and collect merchant offers.

  Parameters:
  - type: category of the request (e.g. "Noodle")
  - constraints: list of constraints (e.g. "No_Coriander", "<30min")
  - lat/lon: approximate location of the user
  ```

---

## 3. Custom Tool Configuration (YAML Example)

If OpenClaw uses YAML to configure tools, a minimal config might look like:

```yaml
tools:
  - name: open_a2a_publish_intent
    type: http_request
    description: Publish an intent to the Open-A2A network and collect offers. Use when the user wants food delivery or similar services.
    config:
      url: "http://localhost:8080/api/publish_intent"
      method: POST
      headers:
        Content-Type: application/json
```

In practice you may want to add parameter mapping from Agent slots to the JSON body.

---

## 4. Response Format

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

- Read `offers_count` to know how many offers were received.
- Iterate over `offers` to summarize or compare price/ETA/options.
- Present a shortlist to the user and ask which offer they prefer, then proceed to send an `OrderConfirm` via another Tool or follow-up action.

