# User Story: Ordering a Pizza (Merchant A / Consumer B / Courier C) via a public node X

> This document explains an end-to-end “order pizza and deliver it” story using the interaction primitives implemented in Open-A2A today: Intent → Offer → Confirm → Logistics.  
> Pizza/food delivery is **only an example** used to make the protocol concrete. Open-A2A is a protocol/transport layer, not a business application.

---

## 1. Roles and the public node

- **User A (Merchant)** runs `A-agent`: listens for food-order intents, replies with offers, confirms fulfillment, and requests delivery.
- **User B (Consumer)** runs `B-agent`: publishes a “want pizza” intent, collects offers, and confirms an order.
- **User C (Courier)** runs `C-agent`: listens for logistics requests, accepts a job, and (in current examples) simulates delivery.
- **Node X (operator)** is a public or consortium entry node you run. It provides a shared subject space and convenient connectivity.

Node X typically includes:

- **NATS** (default `4222`): the shared subject space where intents/offers/logistics messages flow.
- **Relay** (default `8765`, optional): outbound-first entrypoint (Agents connect via WebSocket; Relay bridges to NATS).
- **Bridge** (default `8080`, optional): runtime adapter (e.g., OpenClaw integrates via HTTP Tool/Webhook without speaking NATS).

---

## 2. How A/B/C connect to node X

### Option A: Connect directly to NATS

If A/B/C Agents can reach node X’s NATS client port:

- Configure each Agent’s `NATS_URL` to point to node X (e.g. `nats://user:pass@nats.open-a2a.org:4222`)
- Agents publish/subscribe directly in the shared subject space

### Option B: Outbound-only connectivity via Relay (real-world friendly)

If A/B/C are behind NAT or restricted networks:

- Configure each Agent’s `RELAY_WS_URL` to node X’s Relay (e.g. `ws://relay.open-a2a.org:8765`)
- Agents connect outbound to Relay; Relay bridges subscribe/publish to NATS

> For OpenClaw: typically integrate via Bridge (HTTP Tool/Webhook). Semantics are equivalent; only the transport is adapted.

---

## 3. Two notions of “discoverability”

### 3.1 Event-driven reachability (no directory needed)

- B broadcasts an Intent (e.g. `intent.food.order`)
- A subscribes to that subject and responds with an Offer

You can think of this as “discover me when relevant intents appear”.

### 3.2 Directory registry (always discoverable, formerly Path B)

If you want others to query “who supports capability X” (like a directory), use Discovery:

- `capability` aligns with subjects (e.g. `intent.food.order`, `intent.logistics.request`)
- In NATS discovery, `register` does **not** write to a global registry; it:
  - subscribes to `open_a2a.discovery.query.{capability}`
  - replies with `meta` when queried
- Therefore, the registering process must stay online to remain discoverable

On node X, Bridge provides:

- `POST /api/register_capabilities` to register/update capabilities with meta
- `GET /api/discover?capability=...` to discover who supports a capability

---

## 4. End-to-end flow: Pizza order → Offers → Confirm → Delivery request → Courier accept → Delivered

This flow uses Phase 3 primitives already implemented in the repo. “Pizza” is simply `type="Pizza"`; the protocol stays generic.

### Step 1: B publishes a pizza Intent

- **Subject**: `intent.food.order`
- **Intent (conceptual fields)**:
  - `action="Food_Order"`
  - `type="Pizza"`
  - `constraints=["no onions", "<30min"]` (example)
  - `location=(lat,lon)`
  - `reply_to=intent.food.offer.{intent_id}` (to collect offers)

B-agent can either:

- broadcast only (`collect_offers=false`), or
- broadcast and collect multiple offers within a timeout window (`collect_offers=true`)

### Step 2: A replies with an Offer

- A-agent subscribes to `intent.food.order`
- A-agent publishes an Offer to `intent.food.offer.{intent_id}` (B’s `reply_to`)
- Offers typically include price, description, ETA, and merchant identity

### Step 3: B confirms an order (OrderConfirm)

After selecting the best offer:

- **Subject**: `intent.food.order_confirm`
- **Content**: references selected offer / merchant_id / intent_id

### Step 4: A requests delivery (LogisticsRequest)

After receiving confirmation:

- **Subject**: `intent.logistics.request`
- **Content**:
  - pickup/dropoff details
  - `reply_to=intent.logistics.accept.{request_id}` (to collect courier accepts)

### Step 5: C accepts the delivery job (LogisticsAccept)

- C-agent subscribes to `intent.logistics.request`
- C-agent publishes `LogisticsAccept` to `intent.logistics.accept.{request_id}`
- A-agent collects multiple accepts and chooses a courier

### Step 6: Delivery and completion (currently simulated)

In current examples, couriers simulate delivery to validate the end-to-end collaboration flow. In production:

- proof-of-delivery and settlement can plug into external systems (on-chain or off-chain)
- Open-A2A intentionally stays at the protocol layer and does not hard-code a specific business/payment stack

---

## 5. Why node X matters

- **Shared subject space** so A/B/C can collaborate by connecting to any entry node.
- **Lower onboarding friction**:
  - Relay enables outbound-only Agents to participate.
  - Bridge enables runtime integration without requiring NATS knowledge.
- **Multi-operator mesh**: nodes can later interconnect via NATS clustering/federation or DHT discovery (distributed messaging, not a blockchain ledger).

