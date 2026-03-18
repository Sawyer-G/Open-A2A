# Multi-operator federation (Option 2): independent NATS + selective subject bridging (MVP)

> This document turns the “concept” into something operators can actually configure:  
> **Node X and Node Y run independent NATS servers**, but only sync a chosen subset of subjects (e.g. `intent.food.*`) to preserve data boundaries while enabling cross-node collaboration.

---

## 1. When should you use Option 2?

Use Option 2 when you want:

- Each operator keeps their own NATS (autonomy, clear data boundaries)
- Only a subset of subjects is shared across operators (e.g. share intents/offers, keep internal topics private)

---

## 2. MVP implementation (provided in this repo)

This repo includes a lightweight **Subject Bridge** that:

- Connects to NATS A and NATS B
- Subscribes to an allowlist of subjects
- Forwards messages both ways (A→B and B→A)
- Includes loop/storm protections (headers + hop limit + dedupe)
- Prints periodic stats logs for basic observability

Artifacts:

- Implementation: `federation/subject_bridge.py`
- Container image: `Dockerfile.federation-bridge`
- Example (two independent NATS + bridge): `deploy/federation/x-y/`

---

## 3. Which subjects should be bridged? (default recommendations)

### 3.1 Minimal recommended allowlist (default)

- `intent.>`  
  This is the core cross-node event stream (intents, offers, confirmations, logistics, etc.).

### 3.2 More controlled sharing (recommended for real operators)

Example (share only food + logistics domains):

- `intent.food.>`
- `intent.logistics.>`

### 3.3 Discovery (be cautious)

You may want to bridge:

- `open_a2a.discovery.query.>`

But in practice, NATS Discovery replies are usually sent to `_INBOX.*`.  
To make cross-node discover truly work, you’d also need to bridge the corresponding reply subjects, which increases risk and complexity.

Recommended:

- Prefer DHT (`DhtDiscoveryProvider`) for cross-node directory-style discovery
- Use subject bridging primarily for event flow interop (intent/offer)

---

## 4. How to avoid loops / storms (must-have)

This MVP includes three basic protections:

1) **Skip self-forwarded messages**: if headers contain `X-OA2A-Bridge=<bridge_id>`, the message is considered forwarded by this bridge and will not be forwarded back.
2) **Hop limit**: `X-OA2A-Hop` is incremented and dropped once it exceeds `OA2A_FED_MAX_HOPS` (default 1).
3) **TTL dedupe**: recent messages are hashed and deduped for a short TTL window (default 3 seconds).

Operational recommendations:

- Run **one** bridge per X↔Y pair
- Avoid multi-bridge topologies that create loops (X↔Y↔Z↔X) until you have stronger controls
- Start with a narrow allowlist, expand gradually

---

## 5. Observability (metrics / logs)

### 5.1 Bridge stats logs

By default, the bridge prints one stats line every 10 seconds:

- `a->b` / `b->a`: forwarded counts
- `skip_self`: skipped because it was forwarded by this bridge
- `skip_hop`: dropped due to hop limit
- `skip_dedupe`: dropped by dedupe
- `errors`: publish/forward errors

### 5.2 NATS monitoring endpoints

Enable NATS `http` monitoring endpoints (enabled in the example):

- `http://<node-x>:8222/`
- `http://<node-y>:8222/`

They help you validate subscriptions, connection counts, and detect abnormal growth during incidents.

---

## 6. Copy & run example (local)

```bash
docker compose -f deploy/federation/x-y/docker-compose.yml up -d --build
```

Default allowlist is `intent.>`.

To narrow sharing:

```bash
OA2A_FED_SUBJECTS=intent.food.>,intent.logistics.>
```

---

## 7. Configuration reference (environment variables)

| Variable | Description | Default |
|---|---|---|
| `OA2A_FED_NATS_A` | NATS A URL | `nats://nats-x:4222` |
| `OA2A_FED_NATS_B` | NATS B URL | `nats://nats-y:4222` |
| `OA2A_FED_SUBJECTS` | Allowlisted subjects (comma-separated) | `intent.>` |
| `OA2A_FED_BRIDGE_ID` | Bridge identifier | `x-y-bridge` |
| `OA2A_FED_MAX_HOPS` | Max hop count | `1` |
| `OA2A_FED_DEDUPE_TTL_SECONDS` | Dedupe TTL | `3` |
| `OA2A_FED_STATS_INTERVAL_SECONDS` | Stats interval | `10` |
| `OA2A_FED_LOG_FORWARD_SAMPLES` | Print per-message forward samples | `0` |

Ops endpoint (optional, keep private):

| Variable | Description | Default |
|---|---|---|
| `OA2A_FED_HTTP_ENABLE` | Enable HTTP JSON endpoint | `1` |
| `OA2A_FED_HTTP_HOST` | Bind host | `127.0.0.1` |
| `OA2A_FED_HTTP_PORT` | Bind port (`/healthz`) | `9464` |

