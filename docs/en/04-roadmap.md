# Development Roadmap

## MVP Implementation Steps

### Phase 1: Hello Open-A2A

**Goal**: Run "broadcast-response" between two machines (or processes).

**Tasks**:

1. Configure local NATS server
2. Implement `Consumer.py`: send intent messages
3. Implement `Merchant.py`: listen and reply with an Offer

---

### Phase 2: Privacy & Identity

**Goal**: Ensure only real Agents can communicate.

**Tasks**:

1. Integrate `did:key` encryption; messages must be signed before send
2. Integrate Solid Pod; Agent reads user preferences from Pod, not hardcoded

---

### Phase 3: Complex Scenario Simulation

**Goal**: Full A-B-C flow for "ordering noodles".

**Tasks**:

1. Add `Carrier.py` (delivery agent)
2. Implement contract-based simulated payment flow
3. Open source codebase and publish first RFC
