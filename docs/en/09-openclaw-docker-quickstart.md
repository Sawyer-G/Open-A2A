# OpenClaw (Docker) quickstart: integrate with Open-A2A

> Use this when your OpenClaw Gateway runs in Docker and you want Open-A2A (NATS/Relay/Bridge) on the same server.
> This guide focuses on the most common connectivity pitfalls and the recommended “works by default” setup.

---

## 1. Topology at a glance

Typical setup:

- OpenClaw runs via its own `docker-compose` (example gateway container name: `openclaw-openclaw-gateway-1`, port `18789`)
- Open-A2A runs via this repo’s compose (`deploy/quickstart/docker-compose.full.yml`):
  - `nats` (4222)
  - `relay` (8765)
  - `solid` (optional)
  - `open-a2a-bridge` (8080)

Key questions:

- How does the Bridge container reach OpenClaw Gateway?
- How does OpenClaw call Bridge (Tool) and receive callbacks (Webhook)?

---

## 2. Prerequisites

- OpenClaw is already running in Docker, and you can see the Gateway container:

```bash
docker ps | grep -i gateway
```

- Docker and Docker Compose are installed
- You cloned this repo:

```bash
git clone https://github.com/Sawyer-G/Open-A2A.git
cd Open-A2A
```

---

## 3. Start Open-A2A with the helper script (recommended)

Run on the same server where OpenClaw is running:

```bash
bash scripts/setup-openclaw-bridge.sh
```

The script will:

- Create/update `.env` (copy from `.env.example` if missing)
- Ask for `NATS_URL`, `OPENCLAW_GATEWAY_URL`, and `OPENCLAW_HOOKS_TOKEN`
- Start:

```bash
docker compose -f deploy/quickstart/docker-compose.full.yml --env-file .env up -d --build
```

It also provides a quick diagnose command:

```bash
bash scripts/setup-openclaw-bridge.sh diagnose
```

---

## 4. Critical config: `OPENCLAW_GATEWAY_URL`

Most common mistake:

```bash
OPENCLAW_GATEWAY_URL=http://localhost:18789
```

Inside the Bridge container, `localhost` means **the Bridge container itself**, not OpenClaw.

### Recommended: use `container-name:port`

If Bridge and OpenClaw share a Docker network, set:

```bash
OPENCLAW_GATEWAY_URL=http://<openclaw-gateway-container-name>:18789
```

Example:

```bash
OPENCLAW_GATEWAY_URL=http://openclaw-openclaw-gateway-1:18789
```

### Fallback: use the host IP

If you cannot share Docker networks for now:

```bash
OPENCLAW_GATEWAY_URL=http://<HOST_IP>:18789
```

Requirements:

- OpenClaw maps port `18789` to the host
- The Bridge container can reach the host IP

---

## 5. Optional but recommended: share Docker networks

To make `container-name:port` work, Bridge must join the same Docker network as OpenClaw.

Conceptually:

- keep Open-A2A’s default network
- add OpenClaw’s network as an external network
- attach `open-a2a-bridge` to both

If DNS resolution fails, you’ll see errors like:

```text
Temporary failure in name resolution
```

---

## 6. Hook token: `OPENCLAW_HOOKS_TOKEN`

Bridge calls OpenClaw’s webhook endpoint and must provide the correct token.

Set the same token on both sides:

- OpenClaw config (example): `hooks.token`
- `.env`:

```bash
OPENCLAW_HOOKS_TOKEN=your-token
```

---

## 7. Make your Agent “always discoverable” (optional)

Besides intent broadcast/response, Open-A2A supports directory-style discovery.

Recommended approach:

- Keep Bridge running as a long-lived process
- Register capabilities with TTL and renew periodically

See:

- `docs/en/09-deployment-and-openclaw-integration.md` (Discovery section)
- `example/bridge_discovery_renew.py`

