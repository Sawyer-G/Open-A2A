# Node X (operator node) kit: copyable deployment checklist

> For operators who want to run a public entry node.  
> Goal: provide **copy & run** artifacts without drifting from Open-A2A’s “protocol / infrastructure layer” positioning.

This guide corresponds to the operator kit in this repo: `deploy/node-x/`.

---

## 1. What is “Node X”?

Node X is a public infrastructure entry that typically provides:

- A shared subject space (NATS)
- An easy outbound-first entry (Relay: WS/WSS)
- (Optional) an HTTP adapter and directory-style capability discovery (Bridge: `/health`, register/discover)

By default, **Node X should not bind to any specific business runtime** (e.g., forwarding all network intents into the operator’s own OpenClaw). That would conflict with the protocol-layer goal.

---

## 2. Ports & firewall checklist (be explicit)

### 2.1 Recommended public ports

- **Relay**: `8765/tcp` (`RELAY_WS_PORT`)  
  Most end users can join by making an outbound WS/WSS connection.

- **Bridge (optional)**: `8080/tcp` (`BRIDGE_PORT`)  
  Expose this only if you want to provide:
  - `/health` operational checks
  - `/api/register_capabilities`, `/api/discover` for “always discoverable” (Path B)
  
  Strongly recommended to put behind an HTTPS reverse proxy (and add rate limiting / auth).

### 2.2 Recommended private-only ports

- **NATS**: `4222/tcp`  
  Keep private by default (only Relay/Bridge use it via Docker network).  
  If you really want to offer direct NATS access to advanced users, then consider exposing 4222 with stricter auth/ACL/TLS.

---

## 3. Copyable artifacts (in this repo)

Directory: `deploy/node-x/`

- `docker-compose.node-x.yml`
  - Does **not** publish NATS 4222 to host by default
  - Publishes Relay 8765 and Bridge 8080 (adjust as needed)
  - Uses a fixed Docker network name `open-a2a` for easier diagnostics

- `nats.conf`
  - Minimal NATS auth + permissions template (users + subject ACLs)
  - You must change passwords (at least `agent_public`)

- `.env.node-x.example`
  - Operator-friendly `.env` template

- `scripts/diagnose-node-x.sh`
  - Port checks + Bridge `/health` + NATS ping via `nats-box` container + discover query

---

## 4. Copy & run steps

From the repo root:

```bash
cp deploy/node-x/.env.node-x.example .env
# edit deploy/node-x/nats.conf and change passwords (at least agent_public)
docker compose -f deploy/node-x/docker-compose.node-x.yml --env-file .env up -d --build
bash scripts/diagnose-node-x.sh
```

Minimum required edits:

- Change passwords in `deploy/node-x/nats.conf` and `.env` (keep them consistent)
- Update `BRIDGE_META_JSON.endpoint` to your public domain/IP (if Bridge is public)

---

## 5. Recommended operator defaults (avoid drifting from project intent)

For a **public entry node**, recommended:

- `BRIDGE_ENABLE_FORWARD=0` (do not forward all network intents into one OpenClaw)
- `BRIDGE_ENABLE_DISCOVERY=1` (provide register/discover directory APIs)
- Use Relay as the primary entry (lowest friction for end users)

For a **personal node that runs your own OpenClaw**, recommended:

- `BRIDGE_ENABLE_FORWARD=1`
- Configure `OPENCLAW_GATEWAY_URL` and `OPENCLAW_HOOKS_TOKEN`

---

## 5.1 (Recommended) Provide verifiable directory meta (RFC-004)

If you expose directory-style discovery (`/api/register_capabilities`, `/api/discover`), it is recommended to enable **meta proof** in Bridge:

- Other nodes can verify the signature and confirm the meta is authored by the `did:key` holder.
- This is **not** a credit system; it only enables verifiability. Trust policy remains a local decision.

Optional `.env` settings:

```bash
BRIDGE_ENABLE_META_PROOF=1
BRIDGE_PUBLIC_URL=https://bridge.open-a2a.org
# For production, keep the DID stable across restarts and store the seed securely:
BRIDGE_DID_SEED_B64=BASE64_SEED
```

Protocol details: `spec/rfc-004-identity-and-trust.md`.

---

## 6. Optional hardening (not required by this kit)

This kit stays intentionally minimal. Common next steps:

- Put Relay/Bridge behind an HTTPS reverse proxy (TLS, WAF, rate limiting)
- Enable NATS TLS, stronger account isolation, finer subject ACLs
- Observability: metrics, log aggregation, alerting
- Multi-operator connectivity (X↔Y): selective subject bridging (e.g. `intent.food.*`)

