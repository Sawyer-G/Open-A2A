# Product Requirements

## 1. Core Features (MVP: "A Bowl of Noodles Journey")

| Module | Required Behavior | User Experience |
|--------|-------------------|-----------------|
| **Discovery** | Agent A publishes "I want noodles" intent; B (merchant) in the network perceives and responds | AI automatically finds nearby noodle shops that match my taste |
| **Negotiation** | A and B's Agents automatically discuss: dietary restrictions (no spice), timing, price | I say one sentence; AI handles all pre-sale communication |
| **Coordination** | After B-Agent confirms order, broadcasts delivery intent; C (rider) accepts | Merchant doesn't manually find delivery; rider receives task from Agent |
| **Settlement** | After delivery, Agent A automatically pays B and C (simulated) | Money goes directly to the cook and the rider—no platform cut |
| **Standardized Protocol** | Define shared semantic vocabulary (e.g., `Order_Food`, `Logistics_Request`) | Any open-source Agent following the protocol can "understand" others |

---

## 2. Product Boundaries

- **Centralized Moderation**: This project will **never** touch centralized content moderation or credit endorsement
- **Hardware**: No low-power device support (assume sufficient resources)
- **UI**: No complex mobile app; main output is **API specs and open protocol reference implementation**

---

## 3. User Story: A Late-Night Bowl of Beef Noodles (Platform-Free)

**Scenario**: Friday 11:30 PM, programmer Alice just finished overtime. She tells her phone (personal AI pod): "I want a hot bowl of noodles, same as usual—no cilantro, delivered within 30 minutes."

### A. Intent Broadcast & Millisecond Discovery

- **Alice's Agent (A)** activates, reads preferences from **Solid Pod** (no cilantro, prefers hand-pulled noodles, location, budget)
- **A-Agent** broadcasts encrypted intent to **Open-A2A network**: `{Action: Food_Order, Type: Noodle, Location: [X, Y], Constraints: [No_Coriander, <30min]}`
- Within 3 km, 50+ **merchant Agents** receive the broadcast instantly

### B. Heterogeneous Agent Auto-Negotiation

- **Restaurant B's Agent** checks kitchen inventory, finds one last hand-pulled noodle portion, replies with Offer: `18 UNIT`
- **Restaurant D's Agent** bids `16 UNIT`, but **A-Agent** sees D's yesterday rating ("noodles too soft") and auto-passes
- **A-Agent** selects B and completes DID-signed contract in 0.5 seconds

### C. Decentralized Logistics

- **B-Agent** confirms order, publishes **delivery tender** to the network
- Rider Bob (Carrier C)'s **C-Agent** detects order path 95% overlaps with Bob's route home, reward meets expectation
- **C-Agent** auto-accepts, sends ETA to Alice's **A-Agent**  
  **No dispatcher, no platform taking 20% of delivery fee**

### D. Atomic Settlement

- 20 minutes later, Bob delivers
- Alice's phone detects Bob's proximity (or scan confirmation), triggers **Open-A2A Proof of Delivery**
- **Instant settlement**: Alice's `21 UNIT` (18 noodles + 3 delivery) is split by smart contract:
  - `18 UNIT` to merchant B (no settlement delay)
  - `3 UNIT` to rider Bob (full amount, no platform cut)
- Alice eats, merchant earns more, rider gets full fee. **Zero flows to any middleman**

---

## 4. Rules & Constraints

### Tech Stack Requirements

- **Open Source**: Fully open stack (e.g., Python, Rust, libp2p)
- **Open Architecture**: All communication based on DID; no private account systems

### Design Principles

- **Performance First**: Assume unlimited compute; sub-second intent matching required
- **Extensibility**: Protocol must scale from "order noodles" to "book flights", "form dev teams"

### Open Questions & PM Suggestions

| Challenge | PM Suggestion |
|-----------|---------------|
| **Global Indexing**: Without a platform, how does A find B? | Introduce **DPI (Decentralized Protocol Index)**, like DHT in P2P |
| **Dispute Resolution**: Noodles arrived but broken—who decides? | Reserve "Arbitration Agent" interface; users choose trusted third-party (e.g., DAO) |
| **Spam Prevention**: How to prevent 10,000 B-Agents from spamming A? | DID-based **anti-spam threshold** (e.g., micro-stake) |
