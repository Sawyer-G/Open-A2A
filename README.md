# Open-A2A

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![GitHub](https://img.shields.io/badge/GitHub-Open--A2A-181717?logo=github)](https://github.com/Sawyer-G/Open-A2A)

> Decentralized Agent-to-Agent protocol — the TCP/IP of the post‑internet era.

English | [简体中文文档](./docs/zh/README.md)

---

## Table of Contents

- [Project Positioning](#project-positioning)
- [What is this?](#what-is-this)
- [Why do we need it?](#why-do-we-need-it)
- [Core Capabilities (\"A Bowl of Noodles\")](#core-capabilities-a-bowl-of-noodles)
- [Architecture Overview](#architecture-overview)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Roadmap](#roadmap)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [Tech Stack](#tech-stack)
- [License](#license)

---

## Project Positioning

**Open-A2A** focuses on the **protocol and transport layer**, not on a specific business.  
It defines how Agents communicate (message structure, topics, interaction patterns), **not** what they buy, deliver, or settle.  
The food-delivery use case is an **example** used to validate the protocol, not the end goal.

---

## What is this?

**Open-A2A** (Open Agent-to-Agent Network) is an open-source, decentralized protocol for AI Agent-to-Agent collaboration.  
We define the rules — no platform, no middleman.

As AI assistants become ubiquitous, ordering food, booking rides, and finding services should **no longer require centralized platforms**.  
Open-A2A lets **Consumer Agents**, **Merchant Agents**, and **Delivery Agents** talk directly, so value flows 100% between participants.

---

## Why do we need it?

| Today | Open-A2A Vision |
|-------|-----------------|
| Platforms take 10–30% fees | Zero platform fee; value flows directly to participants. |
| Platforms own data and control choices | Data sovereignty belongs to individuals; AI serves its owner. |
| Everything goes through centralized apps | Agents connect directly using open protocols. |

---

## Core Capabilities (“A Bowl of Noodles” Journey)

Using “order a bowl of noodles” as a concrete example, Open-A2A enables:

- **Global discovery**: A Consumer Agent broadcasts “I want noodles”; nearby Merchant Agents respond within milliseconds.
- **Intent negotiation**: Consumer and Merchant Agents automatically negotiate constraints (no coriander), price, and time; the human only says one sentence.
- **Three-party coordination**: After the merchant confirms the order, a Delivery Agent automatically picks it up — no centralized dispatcher.
- **Value settlement**: Once proof of delivery is recorded, funds are distributed instantly to merchant and courier — no platform cut.

These are examples of general interaction patterns: broadcast + collect, request + reply, delegate + confirm.

---

## Architecture Overview

Conceptually, the system is a three‑layer mesh:

```
┌─────────────────────────────────────────────────────────────┐
│  L3 Intent & Collaboration │ Intent protocol RFC │ LLM      │
│                           │ semantic alignment  │ Settlement│
├─────────────────────────────────────────────────────────────┤
│  L2 Communication & Routing │ Transport adapters │ NATS/DHT │
│                             │ Gossip/Federation │          │
├─────────────────────────────────────────────────────────────┤
│  L1 Digital Cabin (Base)    │ DID identity      │ Solid Pod│
│                             │ Agent runtimes    │          │
└─────────────────────────────────────────────────────────────┘
```

- **L1 Digital Cabin**: Identity (DID), data sovereignty (Solid Pod / profiles), local Agent runtimes (OpenClaw, ZeroClaw, MCP, Ollama…).
- **L2 Communication**: Transport abstraction (NATS, Relay, HTTP/WebSocket, DHT, P2P), discovery (NATS/DHT), clustering/federation.
- **L3 Collaboration**: Intent protocol (RFC‑001), semantic alignment via LLMs, and settlement primitives.

See [`docs/en/03-architecture.md`](./docs/en/03-architecture.md) for details.

---

## Project Structure

| Path | Description |
|------|-------------|
| [`spec/`](./spec) | Core protocol specs (RFCs). |
| [`open_a2a/`](./open_a2a) | Python reference implementation (SDK). |
| [`example/`](./example) | Examples: Consumer, Merchant, Carrier demos. |
| [`bridge/`](./bridge) | Bridge/adapter for Agent runtimes like OpenClaw. |
| [`docs/`](./docs) | Design docs, architecture, requirements, guides. |

---

## Quick Start

> Run all Python commands in a virtualenv (`.venv/bin/python` or `make`) to avoid polluting your system Python.

### 1. Local demo (A→B→C flow)

#### 1.1 Start a local NATS

```bash
docker run -p 4222:4222 nats:latest
```

#### 1.2 Install and run the examples

```bash
make venv && make install
# or: make install-full   # includes optional deps like identity/dev
```

In three terminals:

```bash
make run-merchant    # Terminal 1
make run-carrier     # Terminal 2
make run-consumer    # Terminal 3
```

This runs the full A→B→C flow: Consumer → Merchant(s) → Carrier.

---

### 2. Run a full node (NATS + Relay + Solid + Bridge)

To spin up a full Open-A2A node stack on a server (or locally with Docker), use the quickstart compose file:

```bash
git clone https://github.com/Sawyer-G/Open-A2A.git
cd Open-A2A

cp .env.example .env  # then edit .env as needed (NATS_URL, etc.)

docker compose -f deploy/quickstart/docker-compose.full.yml --env-file .env up -d --build

docker ps  # you should see nats / relay / solid / open-a2a-bridge containers
```

This brings up:

- `nats`: NATS message bus (`4222`);
- `relay`: WebSocket Relay (`8765`) for outbound-only Agents;
- `solid`: self-hosted Solid Pod (`8443`) for preferences (optional);
- `open-a2a-bridge`: HTTP Bridge (`8080`) for integrating runtimes like OpenClaw.

See [`docs/en/09-deployment-and-openclaw-integration.md`](./docs/en/09-deployment-and-openclaw-integration.md) and [`docs/en/12-cross-ip-testing.md`](./docs/en/12-cross-ip-testing.md) for deployment and cross-IP testing details.

---

### 3. Integrate with OpenClaw

If you already have OpenClaw running on a server, you can use the helper script to run Bridge + NATS + Relay + Solid alongside it:

```bash
git clone https://github.com/Sawyer-G/Open-A2A.git
cd Open-A2A

bash scripts/setup-openclaw-bridge.sh
```

The script will:

- Create or update `.env` based on `.env.example`;
- Prompt for `NATS_URL` / `OPENCLAW_GATEWAY_URL` / `OPENCLAW_HOOKS_TOKEN`;
- Try to auto-detect an OpenClaw Gateway container name and propose a sensible default `OPENCLAW_GATEWAY_URL` (e.g. `http://openclaw-openclaw-gateway-1:18789`);
- Run `docker compose -f deploy/quickstart/docker-compose.full.yml up -d --build`.

You can also diagnose common connectivity issues with:

```bash
bash scripts/setup-openclaw-bridge.sh diagnose
```

For advanced users who prefer not to use Docker, there is a bare-metal helper:

```bash
bash scripts/setup-openclaw-bridge-baremetal.sh
```

Then, in OpenClaw:

- Configure an HTTP Tool that calls the Bridge at `/api/publish_intent`;
- Configure a webhook at `{OPENCLAW_GATEWAY_URL}/hooks/agent` with the provided token.

See [`docs/en/openclaw-tool-example.md`](./docs/en/openclaw-tool-example.md) for detailed Tool + Hook configuration, and the Chinese version under `docs/zh/openclaw-tool-example.md` if you prefer Chinese.  
For a Docker-specific OpenClaw integration guide, see:

- English: [`docs/en/09-openclaw-docker-quickstart.md`](./docs/en/09-openclaw-docker-quickstart.md)
- Chinese: [`docs/zh/09-openclaw-docker-quickstart.md`](./docs/zh/09-openclaw-docker-quickstart.md)

---

## Roadmap

| Phase | Status |
|-------|--------|
| Hello Open-A2A (NATS broadcast–response) | ✅ Done |
| Privacy & Identity (did:key + preferences) | ✅ Done |
| Full chain (A–B–C + simulated settlement) | ✅ Done |
| Transport abstraction (`TransportAdapter`) | ✅ Done |
| Open-A2A Bridge (OpenClaw integration) | ✅ Done |
| Agent discovery (NATS/DHT), Relay transport, NATS cluster federation | ✅ Done |

See [`docs/en/04-roadmap.md`](./docs/en/04-roadmap.md) and [`docs/en/06-progress.md`](./docs/en/06-progress.md) for detailed progress.

---

## Documentation

| Topic | English |
|-------|---------|
| Design principles | [`00-design-principles`](./docs/en/00-design-principles.md) |
| Project overview | [`01-project-overview`](./docs/en/01-project-overview.md) |
| Requirements | [`02-requirements`](./docs/en/02-requirements.md) |
| Architecture | [`03-architecture`](./docs/en/03-architecture.md) |
| Roadmap | [`04-roadmap`](./docs/en/04-roadmap.md) |
| Development guide | [`05-development-guide`](./docs/en/05-development-guide.md) |
| Progress | [`06-progress`](./docs/en/06-progress.md) |
| Multi-language SDK planning | [`07-multi-language-sdk`](./docs/en/07-multi-language-sdk.md) |
| Self-hosted Solid Pod | [`08-solid-self-hosted`](./docs/en/08-solid-self-hosted.md) |
| Deployment & OpenClaw | [`09-deployment-and-openclaw-integration`](./docs/en/09-deployment-and-openclaw-integration.md) |
| OpenClaw (Docker) quickstart | [`09-openclaw-docker-quickstart`](./docs/en/09-openclaw-docker-quickstart.md) |
| NATS cluster & federation | [`10-nats-cluster-federation`](./docs/en/10-nats-cluster-federation.md) |
| Relay E2E encryption | [`11-relay-e2e-verify`](./docs/en/11-relay-e2e-verify.md) |
| Cross-IP testing | [`12-cross-ip-testing`](./docs/en/12-cross-ip-testing.md) |
| Security considerations | [`13-security-considerations`](./docs/en/13-security-considerations.md) |
| User story (pizza delivery) | [`14-user-story-pizza-delivery`](./docs/en/14-user-story-pizza-delivery.md) |
| Node X operator kit | [`15-node-x-operator-kit`](./docs/en/15-node-x-operator-kit.md) |
| Multi-operator federation (subject bridge) | [`16-multi-operator-federation-subject-bridge`](./docs/en/16-multi-operator-federation-subject-bridge.md) |
| Identity & trust (operator guide) | [`17-identity-and-trust`](./docs/en/17-identity-and-trust.md) |
| DHT bootstrap guide | [`18-dht-bootstrap-guide`](./docs/en/18-dht-bootstrap-guide.md) |
| DHT community bootstraps | [`19-dht-community-bootstraps`](./docs/en/19-dht-community-bootstraps.md) |
| Prometheus alert templates | [`20-observability-alerts-prometheus`](./docs/en/20-observability-alerts-prometheus.md) |
| OpenClaw Tool example | [`openclaw-tool-example`](./docs/en/openclaw-tool-example.md) |

**Doc entrypoints**:  
- English: [`docs/en/`](./docs/en/README.md)  
- Chinese: [`docs/zh/`](./docs/zh/README.md)

---

## Contributing

We welcome contributions from global open-source developers, Web3 builders, and researchers.

- **Contribution guide**: [`docs/en/standards/03-contribution.md`](./docs/en/standards/03-contribution.md)  
- **Project standards**: [`docs/en/standards/`](./docs/en/standards/)

If you prefer Chinese, see the corresponding docs under `docs/zh/`.

---

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| Identity & Data | DID (`did:key`) via [`didlite`](https://github.com/jondepalma/didlite-pkg); preferences via `profile.json` or self-hosted Solid Pod. |
| Communication | Transport abstraction (NATS reference implementation), extensible to HTTP/WebSocket/DHT; can interop with libp2p, DIDComm. |
| Agent runtimes | MCP, Ollama, OpenClaw / ZeroClaw (via Bridge integration). |
| Settlement | Pluggable: simulation / HTLC / Lightning / third-party APIs. |

---

## License

[Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0). See [`LICENSE`](./LICENSE) and [`NOTICE`](./NOTICE) for details.

