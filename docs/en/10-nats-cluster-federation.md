# NATS Cluster & Federation

> Share a single logical subject space across multiple servers so Agents on different machines can discover each other and exchange intents/offers. Agents only need to connect to **any** node in the cluster.

---

## 1. Why a Cluster?

| Scenario | Single NATS | NATS Cluster |
|---------|-------------|--------------|
| Deployment | One NATS server per machine | Multiple servers form one logical NATS |
| Discovery | Only same process / same server | All Agents connected to the cluster can discover each other |
| Intents/Offers | Only visible within that NATS | Any subject published on one node is visible to the whole cluster |

Open-A2A's discovery (`open_a2a.discovery.query.*`) and intent subjects (`intent.food.*`, etc.) are all NATS subjects. **As long as the NATS servers form a cluster**, Agents deployed on different servers can discover each other and exchange messages without changing business logic.

---

## 2. Key Cluster Configuration Points

- **Client port**: default `4222`, used by Agents and Relay to connect.
- **Cluster (route) port**: used for server-to-server routing (e.g. `6222`); each node must configure `cluster { listen, routes }`.
- **Full mesh recommended**: in `routes`, list **all other nodes** (or at least all reachable ones) so the cluster forms a full mesh and messages don't get stuck on a single hop.

### 2.1 Two-node Example (Same Machine)

**Node A** (`nats-a.conf`):

```conf
port: 4222
cluster {
  name: opena2a
  listen: 0.0.0.0:6222
  routes: [
    nats://127.0.0.1:6223
  ]
}
```

**Node B** (`nats-b.conf`):

```conf
port: 4223
cluster {
  name: opena2a
  listen: 0.0.0.0:6223
  routes: [
    nats://127.0.0.1:6222
  ]
}
```

- Agents can connect to `nats://localhost:4222` or `nats://localhost:4223`; subjects are shared across the cluster.
- Relay and Bridge can point `NATS_URL` to either node.

### 2.2 Multi-Machine Deployment

For each server, change `routes` to the **other servers' IP or hostname + cluster port**. Example:

- Server 1:
  - `listen: 0.0.0.0:6222`
  - `routes: [ nats://server2:6222, nats://server3:6222 ]`
- Server 2:
  - `listen: 0.0.0.0:6222`
  - `routes: [ nats://server1:6222, nats://server3:6222 ]`
- Server 3:
  - Same pattern, listing server1 and server2.

Each server must:

- Expose **client port 4222** (for Agents/Relay).
- Expose **cluster port 6222** (for other NATS nodes).
- Allow these ports in the firewall/security group as appropriate.

---

## 3. Docker Compose Example (Two-Node Cluster)

```yaml
# docker-compose.nats-cluster.yml
services:
  nats-a:
    image: nats:latest
    command: ["-c", "/config/nats.conf"]
    volumes:
      - ./nats-a.conf:/config/nats.conf
    ports:
      - "4222:4222"
      - "6222:6222"
    networks:
      - nats-net

  nats-b:
    image: nats:latest
    command: ["-c", "/config/nats.conf"]
    volumes:
      - ./nats-b.conf:/config/nats.conf
    ports:
      - "4223:4222"
      - "6223:6222"
    networks:
      - nats-net
    depends_on:
      - nats-a

networks:
  nats-net:
    driver: bridge
```

Save the two configs above as `nats-a.conf` and `nats-b.conf`. In Docker, node B's `routes` can use `nats://nats-a:6222` (service name).

---

## 4. How It Relates to Open-A2A

- **Discovery**: `NatsDiscoveryProvider` and `IntentBroadcaster` do not need any change. As long as `NATS_URL` points to **any** node in the cluster, Agents can discover all registered capabilities and exchange intents/offers.
- **Relay**: Point Relay's `NATS_URL` to any node; Agents that connect outbound via Relay are in the same logical cluster as Agents that connect directly to NATS.
- **Cross-cluster / heterogeneous networks**: When Agents are on **different clusters** or when some participants don't use NATS, use the **DHT discovery backend** or NATS federation (see `spec/rfc-002-discovery.md` and `docs/en/06-progress.md`).

### 4.1 What happens when everyone runs their own node?

In practice, many operators will run their **own** NATS / Relay / Bridge stack:

- If they all connect to the **same NATS cluster**, they automatically share one logical subject space — intents and offers are visible everywhere in that cluster.
- If they run **independent NATS servers** with no federation, they form separate networks; discovery only happens within each network.
- If they configure **federation or application-level bridges** between nodes, only the chosen subjects (e.g. `intent.food.*`) are propagated across networks.

This means Open-A2A encourages a mesh of cooperating nodes, not a single global monolith. Operators decide which topics to share and which to keep local.

### 4.2 Option 2: independent NATS + selective subject bridging (MVP)

If you want Node X and Node Y to run **independent NATS servers** but share only selected subjects (e.g. `intent.food.>`), use a subject-bridge approach:

- Each side keeps its own NATS (autonomy and clear data boundaries)
- Only allowlisted subjects are propagated (avoid “sync everything”)
- The bridge must include loop/storm protections (headers/hop/dedupe)

This repo provides an MVP implementation and a copyable example:

- Doc: `docs/en/16-multi-operator-federation-subject-bridge.md`
- Example: `deploy/federation-x-y/` (two independent NATS + subject-bridge)

---

## 5. References

- [NATS Clustering Configuration](https://docs.nats.io/running-a-nats-service/configuration/clustering/cluster_config)
- Open-A2A progress and discovery extensions: see `docs/en/06-progress.md`

