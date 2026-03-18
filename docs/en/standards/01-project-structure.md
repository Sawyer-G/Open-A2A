# Project Structure & Code Standards

## 1. Directory Structure

```
Open-A2A/
├── .cursor/                    # Cursor IDE config
│   └── rules/                  # AI rules (incl. venv convention)
├── docs/                       # Project documentation (zh/en mirror)
│   ├── zh/                     # Chinese docs
│   │   ├── 00-design-principles.md through 11-relay-e2e-verify.md
│   │   ├── openclaw-tool-example.md
│   │   ├── reference/
│   │   └── standards/          # This file, git, documentation, contribution
│   └── en/                     # English docs (same structure as zh)
│       ├── 00-… through 09-deployment-and-openclaw-integration.md
│       ├── reference/
│       └── standards/
├── spec/                       # Core protocol specs (RFC)
│   ├── rfc-001-intent-protocol.md
│   ├── rfc-002-discovery.md
│   ├── rfc-003-relay-transport.md
│   └── rfc-004-identity-and-trust.md
├── open_a2a/                   # Python reference implementation (SDK)
│   ├── intent.py               # Message models
│   ├── broadcaster.py          # Intent broadcast (TransportAdapter-based)
│   ├── transport.py            # Transport layer abstract interface
│   ├── transport_nats.py       # NATS transport adapter
│   ├── transport_relay.py      # Relay transport adapter (outbound)
│   ├── transport_encrypt.py    # Payload E2E encryption wrapper (Relay)
│   ├── discovery.py            # Agent discovery abstract
│   ├── discovery_nats.py       # NATS discovery implementation
│   ├── discovery_dht.py        # DHT discovery (cross-network)
│   ├── identity.py             # DID identity (Phase 2)
│   ├── preferences.py          # Preferences (Phase 2, Solid OAuth2 client credentials)
│   ├── agent.py                # BaseAgent
│   └── __init__.py
├── bridge/                     # Open-A2A Bridge (OpenClaw adapter)
│   ├── __init__.py
│   └── main.py
├── relay/                      # Open-A2A Relay (WebSocket <-> NATS, outbound-first)
│   ├── __init__.py
│   └── main.py
├── deploy/                     # Deployment examples
│   └── nats-cluster/           # Two-node NATS cluster (docker-compose, conf)
├── example/                    # Examples & Demos
│   ├── consumer.py
│   ├── merchant.py
│   ├── carrier.py
│   ├── consumer_via_relay.py   # Consumer via Relay (outbound)
│   ├── discovery_demo.py       # NATS discovery demo
│   ├── discovery_dht_demo.py   # DHT discovery demo
│   ├── multi_merchant_demo.py   # Multi-Merchant scenario verification
│   ├── relay_e2e_verify.py     # Relay payload E2E verification
│   ├── profile.json            # Preferences example (Phase 2)
│   └── upload_profile_to_solid.py
├── .venv/                      # Virtual env (not committed)
├── .gitignore
├── .env.example                # Env var template
├── Makefile                    # venv, install, install-*, run-*
├── pyproject.toml
├── requirements.txt            # Optional, can coexist with pyproject.toml
├── Dockerfile.bridge
├── deploy/solid/docker-compose.solid.yml
├── deploy/quickstart/docker-compose.full.yml
├── LICENSE
├── NOTICE
└── README.md
```

### 1.1 Directory Responsibilities

| Directory | Responsibility | Notes |
|-----------|----------------|-------|
| `spec/` | Protocol definition | Handshake, message format, semantic dictionary |
| `open_a2a/` | Reference implementation | Python SDK for other projects |
| `bridge/` | Adapter layer | Open-A2A Bridge, connects NATS with OpenClaw |
| `example/` | Sample code | Consumer, Merchant, Carrier demos |
| `docs/` | Project docs | Architecture, requirements, guides; `zh/` and `en/` mirror, each with `standards/`, `reference/` |
| `relay/` | Relay server | WebSocket↔NATS, outbound-first, optional TLS |
| `deploy/` | Deployment examples | NATS cluster etc. |

---

## 2. Naming Conventions

### 2.1 File Naming

| Type | Convention | Example |
|------|------------|---------|
| Python module | lowercase + underscore | `intent_broadcaster.py` |
| Python package | lowercase | `core/` |
| Docs | lowercase + hyphen or number prefix | `01-project-overview.md` |
| Protocol docs | RFC number | `spec/rfc-001-intent-protocol.md` |

### 2.2 Code Naming

| Type | Convention | Example |
|------|------------|---------|
| Class | PascalCase | `IntentBroadcaster` |
| Function/method | snake_case | `publish_intent()` |
| Constant | UPPER_SNAKE_CASE | `DEFAULT_TOPIC_PREFIX` |
| Private member | leading underscore | `_internal_method()` |

### 2.3 Branches & Commits

See [git.md](./git.md).

---

## 3. Code Organization Principles

### 3.1 Modularity

- Single responsibility per module; avoid "god classes"
- Define contracts via interfaces/abstract classes for testability and extension
- Prefer dependency injection over hardcoded dependencies

### 3.2 Testability

- Separate business logic from I/O (network, storage)
- Unit tests for core logic
- Tests colocated with source or in `tests/`

### 3.3 Config & Secrets

- Load config via env vars or config files
- Never commit secrets (keys, tokens)
- Provide `.env.example` as template

---

## 4. Tech Stack Conventions

- **Language**: Python 3.9+
- **Package management**: `pyproject.toml` (PEP 621); optional deps `[identity]`, `[solid]`, `[bridge]`, `[relay]`, `[dht]`, `[e2e]`, `[dev]`; root may keep `requirements.txt` for `pip install -r` compatibility
- **Style**: PEP 8, format with `ruff`
- **Types**: Encourage type hints
- **Virtual env**: Use `.venv/bin/python`, `.venv/bin/pip`, or `make` targets; avoid polluting system
