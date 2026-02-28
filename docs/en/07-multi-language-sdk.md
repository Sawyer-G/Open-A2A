# Multi-Language SDK Planning Guide

> This document records the "protocol + multi-language reference implementations" approach for future expansion when the project matures.

---

## 1. What is a Multi-Language SDK?

A **protocol** (e.g., RFC-001) defines message formats, topic structure, and interaction logic—it is language-agnostic.  
An **SDK** (Software Development Kit) is a **concrete implementation** of the protocol, enabling developers to use it in a specific language.

**Multi-language SDK**: One protocol, multiple implementations (Python, TypeScript, Go, Java, etc.), so developers across tech stacks can integrate.

---

## 2. Why Multi-Language SDKs?

| Reason | Description |
|--------|-------------|
| **Tech stack diversity** | Different teams use different languages: Web/TypeScript, enterprise/Java, cloud-native/Go, AI/Python |
| **Lower integration cost** | With only a Python SDK, TypeScript developers must implement from scratch or use FFI—high barrier |
| **Broader adoption** | To become a "universal standard," a protocol must cover major ecosystems; multi-language is common |
| **Reference** | [Google A2A](https://github.com/a2aproject/A2A) provides Python, JavaScript, Java, Go, .NET SDKs |

---

## 3. Current Open-A2A Status

| Item | Status |
|------|--------|
| **Protocol spec** | RFC-001 defined, language-agnostic |
| **Reference impl** | Python only (`open_a2a/`), for initial validation |
| **Multi-language** | Not implemented; to be considered when project matures |

**Why Python first**: Fast validation, AI ecosystem fit, low development cost. This is a **phased choice**, not a protocol limitation.

---

## 4. Implementation Notes for Future Expansion

### 4.1 Protocol First

- **Spec as truth**: RFCs in `spec/` are the single source of truth; all language SDKs must comply
- **Implementation-agnostic**: Protocol uses generic formats (e.g., JSON), not language-specific features
- **Consistency tests**: Consider cross-language conformance tests (same input → same semantic output)

### 4.2 Suggested Language Priority

| Priority | Language | Typical use | Notes |
|----------|----------|-------------|-------|
| 1 | Python | Implemented | Current reference |
| 2 | TypeScript/JavaScript | Web, Node.js, OpenClaw | Agent ecosystem integration |
| 3 | Go | Cloud-native, high-perf | NATS official client is Go |
| 4 | Java | Enterprise, Android | Enterprise adoption |
| 5 | Rust | Edge, high-perf | Optional; fits ZeroClaw etc. |

Order can be adjusted by **community demand** and **contributor capacity**.

### 4.3 Repository Layout

**Option A: Monorepo**

```
open-a2a/
├── spec/           # Protocol (shared)
├── python/         # open_a2a
├── typescript/     # @open-a2a/sdk
├── go/             # sdk-go
└── ...
```

**Option B: Multi-repo (like Google A2A)**

```
open-a2a/spec
open-a2a/open-a2a-py
open-a2a/open-a2a-ts
open-a2a/open-a2a-go
...
```

### 4.4 Core Capabilities per SDK

| Capability | Description |
|------------|-------------|
| Message models | Intent, Offer, OrderConfirm, LogisticsRequest, LogisticsAccept |
| Broadcaster | NATS connect, publish/subscribe, `publish_and_collect` patterns |
| Identity (optional) | `did:key` generation, JWS sign/verify |
| Preferences (optional) | Preferences storage abstraction |

### 4.5 Maintenance

- **Manpower**: Each language needs maintainers, bug fixes, protocol updates
- **Consistency**: Protocol changes must be reflected in all SDKs
- **Testing**: Protocol-level test suite; all SDKs run same cases
- **Docs**: API docs and examples per SDK

---

## 5. When to Consider Multi-Language?

| Signal | Description |
|--------|-------------|
| Non-Python teams want to integrate | Clear demand |
| Protocol stable, RFC changes infrequent | Avoid high sync cost |
| Contributors willing to maintain a language | Sustainable |
| Integration with OpenClaw, ZeroClaw needs TS/Rust | Ecosystem-driven |

---

## 6. References

- [Google A2A multi-language SDKs](https://github.com/a2aproject/A2A)
- [MCP implementations](https://modelcontextprotocol.io/)
- [NATS clients](https://nats.io/download/)

---

## 7. Summary

- Protocol and implementation are separate; multi-language SDKs are different implementations of the same spec
- Open-A2A currently has a Python reference; multi-language is a **future expansion option**
- When expanding: protocol first, prioritize by demand, consider maintenance cost
- This doc is for future decision-making and implementation
