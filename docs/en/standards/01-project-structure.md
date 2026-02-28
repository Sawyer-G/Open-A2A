# Project Structure & Code Standards

## 1. Directory Structure

```
Open-A2A/
├── .cursor/                    # Cursor IDE config
│   └── rules/                  # AI rules (incl. venv convention)
├── docs/                       # Project documentation
│   ├── zh/                     # Chinese docs
│   ├── en/                     # English docs
│   └── standards/              # Standards
├── spec/                       # Core protocol specs (RFC)
├── open_a2a/                   # Python reference implementation (SDK)
│   ├── intent.py               # Message models
│   ├── broadcaster.py         # Intent broadcast (TransportAdapter-based)
│   ├── transport.py           # Transport layer abstract interface
│   ├── transport_nats.py      # NATS transport adapter
│   ├── identity.py            # DID identity (Phase 2)
│   ├── preferences.py         # Preferences abstraction (Phase 2)
│   └── agent.py               # BaseAgent
├── bridge/                     # Open-A2A Bridge (OpenClaw adapter)
│   ├── __init__.py
│   └── main.py
├── example/                    # Examples & Demos
│   ├── consumer.py
│   ├── merchant.py
│   ├── carrier.py
│   ├── profile.json           # Preferences example (Phase 2)
│   └── upload_profile_to_solid.py
├── .venv/                      # Virtual env (not committed)
├── Makefile                    # venv, install, install-full, install-solid, install-bridge, run-*
├── pyproject.toml
├── Dockerfile.bridge
├── docker-compose.solid.yml
├── docker-compose.deploy.yml
└── README.md
```

### 1.1 Directory Responsibilities

| Directory | Responsibility | Notes |
|-----------|----------------|-------|
| `spec/` | Protocol definition | Handshake, message format, semantic dictionary |
| `open_a2a/` | Reference implementation | Python SDK for other projects |
| `bridge/` | Adapter layer | Open-A2A Bridge, connects NATS with OpenClaw |
| `example/` | Sample code | Consumer, Merchant, Carrier demos |
| `docs/` | Project docs | Architecture, requirements, guides (bilingual) |

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
- **Package management**: `pyproject.toml` (PEP 621); optional deps `[identity]`, `[dev]`
- **Style**: PEP 8, format with `ruff`
- **Types**: Encourage type hints
- **Virtual env**: Use `.venv/bin/python`, `.venv/bin/pip`, or `make` targets; avoid polluting system
