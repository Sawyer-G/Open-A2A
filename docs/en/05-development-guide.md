# Development Guide

## 0. Dependency management (recommended)

- **Source of truth**: `pyproject.toml` (PEP 621). Optional extras: `.[identity]`, `.[solid]`, `.[bridge]`, `.[relay]`, `.[dht]`, `.[e2e]`, `.[dev]`.
- **Recommended install**: use `make` targets (virtualenv + editable install) so contributors share the same entrypoint.
- **`requirements.txt`**: kept only as a minimal/compatibility list for environments that require `pip install -r`.

## 1. Resource Stack (Step-by-Step)

Follow the layered architecture; integrate in this order:

### Step 1: Trust Layer (DID & Auth)

| Tool | Description | Status |
|------|-------------|--------|
| [didlite](https://github.com/jondepalma/didlite-pkg) | Lightweight Python `did:key` + JWS signing | ✅ Integrated (`pip install open-a2a[identity]`) |
| [SSI-SDK](https://github.com/TalaoLabs/ssi-sdk) | Lightweight self-hosted identity SDK | Alternative |
| [SpruceID (DIDKit)](https://github.com/spruceed/didkit) | Production DID & VC tools | Alternative |
| [Veramo](https://veramo.io/) | Modular TypeScript DID framework | Alternative |

### Step 2: Data Sovereignty (Solid Pod)

| Tool | Description | Status |
|------|-------------|--------|
| `FilePreferencesProvider` | JSON-based preferences, see `open_a2a/preferences.py` | ✅ Implemented |
| `SolidPodPreferencesProvider` | Read/write from self-hosted Solid Pod (**recommended**), `pip install open-a2a[solid]` | ✅ Implemented |
| [solid-file](https://github.com/twonote/solid-file-python) | Python Solid Pod client; supports Node Solid Server | ✅ Integrated |
| [deploy/solid/docker-compose.solid.yml](../deploy/solid/docker-compose.solid.yml) | One-click self-hosted Solid deployment | ✅ Provided |
| [08-solid-self-hosted.md](./08-solid-self-hosted.md) | Self-hosted Solid setup guide | Required reading |

### Step 3: Agent Runtime (Capability Layer)

Open-A2A **does not implement** Agent inference. Integrate with mature runtimes:

| Project | Description | Open-A2A Integration |
|---------|-------------|----------------------|
| **Open-A2A Bridge** | `bridge/main.py`, FastAPI service | ✅ Implemented, `make install-bridge && make run-bridge`, see [09-deployment-and-openclaw-integration.md](./09-deployment-and-openclaw-integration.md) |
| [OpenClaw](https://github.com/openclaw/openclaw) | Personal AI assistant, multi-channel (WhatsApp, Telegram, etc.), TypeScript | Connect via Bridge as Tool or Channel |
| [ZeroClaw](https://github.com/zeroclaw-labs/zeroclaw) | Lightweight Rust runtime (<5MB RAM), trait-driven | Pluggable Provider/Channel implementing Open-A2A |
| [Ollama](https://ollama.com/) | Local LLM inference | As Agent's model backend |
| [MCP](https://modelcontextprotocol.io/) | Model Context Protocol | Tool exposure, semantic handshake |

### Step 4: A2A & P2P

| Tool | Description |
|------|-------------|
| [DIDComm-Python](https://github.com/sicpa-dcl/didcomm-python) | Encrypted Agent-to-Agent communication |
| [libp2p (py-libp2p)](https://github.com/libp2p/py-libp2p) | P2P discovery & NAT traversal |

---

## 2. Architecture Optimizations (2026 Perspective)

### 2.1 Intent Mesh

**Pain**: How does Agent A know which Agent globally can serve?

**Optimization**: Introduce **Dequier (decentralized query layer)**. Agent broadcasts encrypted intent to local nodes; capable Agents proactively handshake instead of A searching everywhere.

### 2.2 Streaming Micropayments

**Pain**: Pay first or data first?

**Optimization**: Integrate **Lightning Network** or **Farcaster Frame**. Charge per token or per second; auto-pay ~$0.0001 per round to minimize default risk.

---

## 3. Integration with Agent Runtimes

### 3.1 Integration Architecture

```
User / Merchant / Rider
        │
        ▼
┌─────────────────────────────────────┐
│  OpenClaw / ZeroClaw (Agent Runtime) │
│  - NLU, decision, tool calling      │
│  - Pluggable: Open-A2A Tool/Channel │
└─────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────┐
│  Open-A2A Protocol Layer             │
│  - RFC-001 intent/offer format      │
│  - NATS topics, pub/sub             │
└─────────────────────────────────────┘
```

### 3.2 Integration Modes

| Mode | Description |
|------|-------------|
| **Tool** | Wrap as Agent-callable tool; user says "want noodles" → tool publishes intent and returns offers |
| **Channel** | Like OpenClaw's WhatsApp channel; Agent subscribes to Open-A2A topics and responds |
| **Bridge** | Adapter connecting Open-A2A SDK to Agent runtime; runtime need not know NATS |

### 3.3 Competitors & Alternatives

| Project | Focus | Insight for Open-A2A |
|---------|-------|----------------------|
| [Olas (Autonolas)](https://olas.network/) | Multi-agent consensus, joint signatures; finance-grade | Reference "Registry" for asset-related collaboration |
| [Morpheus](https://mor.org/) | Decentralized compute; users pay tokens to run global Agents | Smart Agent Protocol worth studying |
| [Fetch.ai (Almanac)](https://fetch.ai/) | Agent directory; contract-based address/capability registry | Need similar decentralized index for addressing |

---

## 4. Multi-Language SDK Planning

Open-A2A currently provides only a Python reference implementation. When the project matures and non-Python integration is needed, consider TypeScript, Go, Java, etc.

**Form**: A protocol (RFC) is language-agnostic; multi-language SDKs are different implementations of the same protocol, expanding adoption. See [Google A2A](https://github.com/a2aproject/A2A) for Python, JS, Java, Go, .NET implementations.

**Details**: [07-multi-language-sdk.md](./07-multi-language-sdk.md)—why, when, language priority, repo layout, maintenance.
