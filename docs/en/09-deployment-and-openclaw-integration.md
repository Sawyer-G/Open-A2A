# Deployment & OpenClaw Integration Guide

> How to deploy Open-A2A on your server and integrate with OpenClaw.

---

## 1. Architecture

```
NATS ←→ Open-A2A Bridge ←→ OpenClaw (Gateway)
         │
         ├── POST /api/publish_intent (Tool integration)
         └── Subscribe NATS → POST /hooks/agent (Channel integration)
```

---

## 2. Quick Start

```bash
make install-bridge && make run-bridge
# or
docker compose -f docker-compose.deploy.yml up -d
```

**Environment**: `NATS_URL`, `OPENCLAW_GATEWAY_URL`, `OPENCLAW_HOOKS_TOKEN`

---

## 3. API

**Publish intent**:
```bash
curl -X POST http://localhost:8080/api/publish_intent \
  -H "Content-Type: application/json" \
  -d '{"type":"Noodle","constraints":["No_Coriander"],"collect_offers":true}'
```

**Health**: `GET /health`

---

## 4. Integration Modes

| Mode | Description |
|------|-------------|
| **Tool** | OpenClaw calls `POST /api/publish_intent` when user says "order noodles" |
| **Channel** | Bridge subscribes to NATS, forwards intents to OpenClaw `/hooks/agent` |

See [zh/09-deployment-and-openclaw-integration.md](../zh/09-deployment-and-openclaw-integration.md) for full details (Chinese).
