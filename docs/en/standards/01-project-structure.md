# Project Structure & Code Standards

## 1. Directory Structure

```
Open-A2A/
├── .cursor/                    # Cursor IDE config
│   └── rules/                  # AI collaboration rules
├── docs/                       # Project documentation
│   ├── zh/                     # Chinese docs
│   ├── en/                     # English docs
│   └── ...
├── spec/                       # Core protocol specs (RFC)
├── core/                       # Python reference implementation (SDK)
├── example/                    # Examples & Demos
├── .gitignore
├── README.md
├── LICENSE
└── pyproject.toml              # or requirements.txt
```

### 1.1 Directory Responsibilities

| Directory | Responsibility | Notes |
|-----------|----------------|-------|
| `spec/` | Protocol definition | Handshake, message format, semantic dictionary |
| `core/` | Reference implementation | Python SDK for other projects |
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

- **Language**: Python 3.10+
- **Package management**: Prefer `pyproject.toml` (Poetry or PEP 621)
- **Style**: PEP 8, format with `ruff` or `black`
- **Types**: Encourage type hints
