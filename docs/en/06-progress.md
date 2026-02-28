# Project Progress

> Last updated: 2026-02-28

## Overall Status

| Phase | Status | Notes |
|-------|--------|-------|
| **Phase 1: Hello Open-A2A** | ✅ Done | Broadcast-response flow verified |
| **Phase 2: Privacy & Identity** | ✅ Done | did:key signing + preferences abstraction |
| **Phase 3: Complex Scenario** | ✅ Done | A-B-C full flow + simulated settlement |

---

## Phase 1 Completed

### 1. Protocol Spec

- **RFC-001 Intent Protocol** (`spec/rfc-001-intent-protocol.md`)
  - Subject structure: `intent.food.order`, `intent.food.offer.{id}`
  - Message format: Intent, Offer JSON definitions
  - Interaction flow

### 2. Core SDK (`open_a2a/`)

| Module | Description |
|--------|-------------|
| `intent.py` | Intent, Offer, Location data models |
| `broadcaster.py` | NATS wrapper: publish intent, subscribe, publish/collect offers |
| `agent.py` | BaseAgent base class (for future extension) |

### 3. Example Demo (`example/`)

| File | Description |
|------|-------------|
| `consumer.py` | Publishes "want noodles" intent, collects merchant offers |
| `merchant.py` | Subscribes to intents, auto-replies with Offer |

### 4. Dev Environment

- Virtual env (`.venv/`)
- Makefile: `venv`, `install`, `run-merchant`, `run-consumer`
- `pyproject.toml`, `requirements.txt`, `.env.example`

### 5. Verification

- NATS messaging works
- Consumer publishes → Merchant receives and replies → Consumer receives offer
- Flow verified by actual run

---

## Phase 2 Completed

- **identity.py**: `AgentIdentity` based on [didlite](https://github.com/jondepalma/didlite-pkg), `did:key` + JWS sign/verify
- **preferences.py**: `PreferencesProvider` abstract, `FilePreferencesProvider` (JSON file), `SolidPodPreferencesProvider` (self-hosted Solid, **recommended**)
- **broadcaster.py**: Optional `identity` param for signing; parse JWS or JSON on receive
- **intent.py**: `sender_did` field on Intent, Offer
- **Makefile**: `make install-full`, `make install-solid`, `make install-bridge`, `make run-bridge`
- **Examples**: `USE_IDENTITY=1` enables DID signing; `profile.json` or self-hosted Solid for preferences; `upload_profile_to_solid.py`; `docker-compose.solid.yml` for self-hosted Pod

---

## Phase 3 Completed

- **RFC-001**: OrderConfirm, LogisticsRequest, LogisticsAccept
- **carrier.py**: Subscribes to logistics requests, auto-accepts
- **merchant.py**: Subscribes to order_confirm, publishes LogisticsRequest
- **consumer.py**: Publishes OrderConfirm after selecting offer
- **Makefile**: `make run-carrier`

---

## Commit History

| Commit | Description |
|--------|-------------|
| `4bffee1` | feat: implement Phase 1 Hello Open-A2A framework |
| `ab543fd` | chore: initial project setup with docs and standards |

---

## Bridge Extension (OpenClaw Integration)

- **bridge/main.py**: FastAPI service; `POST /api/publish_intent` to publish intent and optionally collect offers; `GET /health` for health check
- **NATS subscription forwarding**: Subscribes to `intent.food.order`, forwards to OpenClaw `/hooks/agent` (requires `OPENCLAW_GATEWAY_URL`, `OPENCLAW_HOOKS_TOKEN`)
- **Dockerfile.bridge**: Bridge image build
- **docker-compose.deploy.yml**: One-click deploy (NATS + Solid + Bridge)

## Next Steps

1. ~~**Open-A2A Bridge**~~ ✅ Done
2. **Optional**: Multi-Merchant test, transport layer abstraction
3. **Optional**: Solid Pod client credentials auth (current: username/password)
4. **Optional**: Agent cross-server discovery (DHT, NATS cluster federation)
