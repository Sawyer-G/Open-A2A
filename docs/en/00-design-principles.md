# Design Principles

> This document defines Open-A2A's core design goals and principles — the "north star" for understanding architecture and requirements.

---

## 1. Core Goals (Not Food Delivery)

Open-A2A's **core goals** are not to implement food delivery, takeout, or any specific business. They are:

| Goal | Description |
|------|-------------|
| **Cross-Network Agent Communication** | Agents may reside in different networks (different NATS clusters, protocols, trust domains). The framework must solve "how to discover each other and establish communication." |
| **Data Interaction Form and Logic** | Define the **structure** (format, topics, serialization) and **interaction patterns** (broadcast-collect, request-reply, delegate-confirm, etc.) of messages between Agents, so they can be reused across any collaboration scenario. |

The food delivery scenario is an **inspiration** and **example implementation** — not the business goal of the framework.

---

## 2. Design Principles

### 2.1 Protocol Layer, Not Business Layer

- Open-A2A defines "how Agents communicate," not "what to buy, deliver, or settle."
- Business semantics are extended by each domain (`intent.{domain}.{action}` — `domain` can be anything).

### 2.2 Extensible Interaction Patterns

- Intent broadcast + multi-response collection
- Request + directed reply (reply_to)
- Sub-task delegation (A delegates to B, B delegates to C)
- These patterns should be abstracted as composable **interaction primitives**, not hardcoded in a single workflow.

### 2.3 Replaceable Transport Layer

- NATS is the current reference implementation, but the architecture should reserve a **transport adapter** abstraction.
- Future support for HTTP, WebSocket, DHT, P2P, etc., to handle heterogeneous "各自网络" (each agent's own network).

### 2.4 Identity and Data Sovereignty

- Agent identity does not rely on centralized accounts; uses decentralized identifiers (DID).
- Data interaction follows minimal disclosure; supports Verifiable Credentials (VC).

### 2.5 Decentralization vs Public Infrastructure Nodes

- **Decentralized at the protocol layer**:
  - Anyone can run their own NATS / Relay / Bridge / DHT nodes that speak the Open-A2A protocols.
  - Nodes interconnect via open specifications; Agents are not bound to a single entrypoint.
  - The protocol does not mandate a single gateway or official platform; it encourages multiple operators to coexist.
- **Public nodes at the infrastructure layer**:
  - Similar to Ethereum's Infura/Alchemy, IPFS bootstrap nodes, or Bitcoin DNS seeds.
  - To lower the barrier for regular users, the project or community may provide a set of long-running public entrypoints (NATS/Relay/Bridge with domain names) as **default examples**.
  - These nodes are **replaceable**: users or other communities can run their own nodes or switch to different providers.
- **End-users should only need outbound connectivity**:
  - A typical user's Agent runs behind NAT / WiFi / dynamic IP. It should only need to make outbound connections to some public entry (NATS/Relay/Bridge), without opening ports on their router.
  - A smaller number of participants who are willing to operate infrastructure can run public nodes and publish their connection details in documentation, collectively forming the broader Open-A2A network.

---

## 3. Relationship to Example Scenarios

| Concept | Role |
|---------|------|
| **Food delivery / delivery** | Inspiration, Demo, use case to validate protocol feasibility |
| **Intent / Offer / OrderConfirm** | Concrete instantiation of generic patterns in the "order" scenario; can be abstracted as Request / Proposal / Accept |
| **Consumer / Merchant / Carrier** | Role names in the example; other scenarios may use Requester / Provider / Delegator, etc. |

When reading requirements and architecture docs, distinguish: **what is generic capability** vs **what is food-delivery-specific wording**.

---

## 4. Reading Recommendations

- **Newcomers**: Read this document first, then [01-project-overview.md](./01-project-overview.md)
- **Architecture design**: Use this document as a constraint; ensure 03-architecture does not deviate.
- **Feature development**: Ensure new capabilities serve "cross-network communication" or "data interaction form/logic," not a single business workflow.
