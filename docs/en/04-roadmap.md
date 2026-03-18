# Development Roadmap

## MVP Implementation Steps

### Phase 1: Hello Open-A2A

**Goal**: Run "broadcast-response" between two machines (or processes).

**Tasks**:

1. Configure local NATS server
2. Implement `Consumer.py`: send intent messages
3. Implement `Merchant.py`: listen and reply with an Offer

---

### Phase 2: Privacy & Identity ✅

**Goal**: Ensure only real Agents can communicate.

**Completed**:

1. ✅ Integrated `did:key` (via didlite); optional JWS signing, verification on receive
2. ✅ Preferences abstraction (`FilePreferencesProvider`, `SolidPodPreferencesProvider`); Agent reads from `profile.json` or self-hosted Solid Pod (self-hosted recommended for data sovereignty)

---

### Phase 3: Complex Scenario Simulation ✅

**Goal**: Full A-B-C flow for "ordering pizza".

**Completed**:

1. ✅ Added `Carrier.py` (delivery agent)
2. ✅ Simulated payment flow (Merchant logs "结算完成" on LogisticsAccept)
3. ✅ RFC-001 extended; codebase open

---

### Future: Multi-Language SDK (TBD)

**Goal**: When the project matures, provide reference implementations in TypeScript, Go, Java, etc.

**Reference**: See [07-multi-language-sdk.md](./07-multi-language-sdk.md).  
**Triggers**: Non-Python integration demand, stable protocol, community maintainers.
