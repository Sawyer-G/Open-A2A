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
- **Examples**: `USE_IDENTITY=1` enables DID signing; `profile.json` or self-hosted Solid for preferences; `upload_profile_to_solid.py`; `deploy/solid/docker-compose.solid.yml` for self-hosted Pod

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
- **Capability discovery (NATS)**: `POST /api/register_capabilities` to register capabilities (always discoverable while Bridge is running); `GET /api/discover` to query who supports a capability
- **Dockerfile.bridge**: Bridge image build
- **deploy/quickstart/docker-compose.full.yml**: Full quickstart (NATS + Relay + Solid + Bridge)

## Transport Layer Abstraction (Design Principle 2.3)

- **transport.py**: `TransportAdapter` abstract base class; `connect`, `disconnect`, `publish`, `subscribe`
- **transport_nats.py**: `NatsTransportAdapter`, NATS reference implementation
- **broadcaster.py**: `IntentBroadcaster` accepts `transport` parameter; defaults to NATS, backward compatible
- Future: HTTP, WebSocket, DHT, P2P adapters

## Agent Discovery (Cross-Server Discovery)

- **discovery.py**: `DiscoveryProvider` abstract; `register`, `unregister`, `discover`
- **discovery_nats.py**: `NatsDiscoveryProvider`, NATS request-reply, no central registry
- **Subject**: `open_a2a.discovery.query.{capability}` (e.g. `intent.food.order`)
- **spec/rfc-002-discovery.md**: Discovery protocol draft
- **example/discovery_demo.py**: `make run-discovery-demo`
- **Extension**: Same NATS/cluster; multi-cluster see NATS cluster doc; cross-network see DHT backend

## DHT Discovery Backend (Cross-Network)

- **discovery_dht.py**: `DhtDiscoveryProvider`, Kademlia DHT; register/discover in DHT, independent of NATS
- **Use case**: Agents on different NATS clusters or transports join same DHT (bootstrap) to discover each other
- **Public bootstrap list**: When `bootstrap_nodes` is not passed, `get_default_dht_bootstrap()` is used; it reads env `OPEN_A2A_DHT_BOOTSTRAP` (format `host1:port1,host2:port2`) first, else `DEFAULT_DHT_BOOTSTRAP`. Everyone using the same list joins the same DHT.
- **Install**: `pip install open-a2a[dht]` (kademlia); example `make run-discovery-dht-demo`, `example/discovery_dht_demo.py`

## NATS Cluster Federation

- **Doc**: [10-nats-cluster-federation.md](../zh/10-nats-cluster-federation.md) (config, two-node example, Docker Compose)
- **Deploy**: `deploy/nats-cluster/` with nats-a.conf, nats-b.conf, docker-compose.yml

## Relay Transport (Outbound-First, RFC-003)

- **relay/main.py**: WebSocket server, connects to NATS, bridges client subscribe/unsubscribe/publish to NATS subjects
- **transport_relay.py**: `RelayClientTransport` implements TransportAdapter; agents connect outbound via `relay_ws_url` to join the network
- **Protocol**: JSON over WebSocket (subscribe/unsubscribe/publish; message downstream), see spec/rfc-003-relay-transport.md
- **Example**: `example/consumer_via_relay.py`, `make run-relay`, `make install-relay`
- **Purpose**: Agents without public IP/domain/webhook get reachability from the framework

## Next Steps

1. ~~**Open-A2A Bridge**~~ ✅ Done
2. ~~**Transport layer abstraction**~~ ✅ Done
3. ~~**Agent cross-server discovery**~~ ✅ Done (`DiscoveryProvider`, `NatsDiscoveryProvider`, RFC-002)
4. ~~**Optional: Multi-Merchant test**~~ ✅ Done: `example/multi_merchant_demo.py`, `make run-multi-merchant-demo`; optional `run-merchant-2`/`run-merchant-3` for manual verification; **Optional**: real payment channel
5. ~~**Optional: Solid Pod client credentials auth**~~ ✅ Done: `SolidPodPreferencesProvider` supports OAuth2 client credentials (SOLID_CLIENT_ID/SOLID_CLIENT_SECRET), optional SOLID_IDP discovery or SOLID_TOKEN_URL; username/password remains supported, see docs/zh/08-solid-self-hosted.md
6. ~~**Relay transport (outbound-first)**~~ ✅ Done (`relay/main.py`, `RelayClientTransport`, RFC-003)
7. ~~**NATS cluster federation or DHT discovery**~~ ✅ Done (NATS cluster: 10-nats-cluster-federation + deploy/nats-cluster; DHT: DhtDiscoveryProvider, RFC-002)
8. ~~**Optional: Public DHT bootstrap**~~ ✅ Done (env `OPEN_A2A_DHT_BOOTSTRAP`, `get_default_dht_bootstrap()`)
9. ~~**Optional: Relay E2E encryption**~~ ✅ Done: Relay server TLS (wss, RELAY_WS_TLS/SSL_CERT/KEY); payload E2E via `EncryptedTransportAdapter` (open-a2a[e2e]), RFC-003 §6

---

## Multi-Merchant scenario

- **Goal**: Verify one intent is received by multiple merchants and each replies with an offer; consumer collects multiple offers.
- **Automated**: `make run-multi-merchant-demo` (NATS must be running). Script starts N merchants (default 3, set `MULTI_MERCHANT_N=5`), consumer publishes once, verifies ≥ N offers.
- **Manual**: Run `make run-merchant`, `make run-merchant-2`, `make run-merchant-3` in three terminals, then `make run-consumer` in a fourth; you should see 3 offers.
