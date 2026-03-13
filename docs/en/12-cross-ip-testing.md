# Cross-IP Testing Guide

> Assumptions: compute is cheap, hardware is affordable, and **everyone has their own AI Agent**, running in their **own network** (home, office, different ISPs). Under these assumptions, cross-IP / cross-network verification is **necessary**, not optional.

---

## 1. Why Cross-IP Testing Matters

| Assumption | Meaning |
|-----------|---------|
| Each person has an Agent | Consumer, merchant, carrier, etc. are different people/entities, each running their own Agent. |
| Deployed in own networks | Each Agent runs on a different machine, different public IP, or behind different NATs. |
| Framework goal | Let these Agents, scattered across networks, discover each other and exchange intents/offers. |

If we only test on a single machine or in a single NATS instance, we cannot be sure the framework works in **real-world distributed** setups.  
**Cross-IP testing** verifies that Agents under different IPs and networks can still discover, communicate, and complete the full intent → offer → confirm → delegate flow.

---

## 2. Recommended Cross-IP Scenarios

### Scenario 1: Dual-Server NATS Cluster (Two Different Public IPs)

**Topology**: Two people each have a VPS with a public IP. Each runs a NATS node; together they form a cluster. One runs Merchant, the other runs Consumer. They share one logical subject space via clustering.

```
┌─────────────────────────────┐     ┌─────────────────────────────┐
│  Server A (public IP_A)    │     │  Server B (public IP_B)    │
│  - NATS node A :4222,:6222 │◄───►│  - NATS node B :4222,:6222 │
│  - Merchant (localhost)    │     │  - Consumer (localhost)    │
└─────────────────────────────┘     └─────────────────────────────┘
            Routes on 6222
```

**Goal**: Consumer on B publishes an intent and receives an offer from Merchant on A.

---

### Scenario 2: Public + Private (Relay Outbound)

**Topology**: One side (A) runs NATS + Relay + Merchant on a public server; the other side (B) is at home/office behind NAT with **no public IP**. B only runs a Consumer that connects outbound to Relay via WebSocket.

```
┌─────────────────────────────────────────┐     ┌─────────────────────────┐
│  Server A (public IP_A)                │     │  User B (home/private)  │
│  - NATS :4222                          │     │  - No public IP         │
│  - Relay :8765 (ws://IP_A:8765)       │◄───►│  - Consumer             │
│  - Merchant (NATS)                     │     │    RELAY_WS_URL=ws://… │
└─────────────────────────────────────────┘     └─────────────────────────┘
```

**Goal**: B's Consumer, using only outbound WebSocket `ws://IP_A:8765`, can publish an intent and receive an offer from A's Merchant.

---

### Scenario 3: Single Public NATS Node (Testnet Entry)

> This scenario matches your current setup: you run a single **public NATS node** on a cloud VM, and local machines connect directly via public IP or domain to run the A-B-C flow end-to-end.

**Topology**:

```
┌─────────────────────────────┐
│  Public node (e.g. GCP, IP_S)│
│  - NATS :4222               │
│                             │
│  (Optional) future Relay/DHT│
└─────────────────────────────┘
             ▲
             │ NATS_URL=nats://user:pass@IP_S:4222
             ▼
┌─────────────────────────────┐
│  Local dev / other machines │
│  - Consumer / Merchant, etc.│
└─────────────────────────────┘
```

**Goal**: With only a single NATS node running on the public server, you can run `example/merchant.py` and `example/consumer.py` locally and complete the full intent → offer → confirm → logistics-request flow across the Internet.

#### 2.3.1 Public NATS Node Deployment (Example)

On the cloud server (e.g. GCP):

1. Install Docker (per your distro's docs).
2. Create a NATS config:

```conf
# ~/nats/nats.conf
port: 4222

authorization {
  users = [
    { user: "opena2a", password: "your-strong-password" }
  ]
}
```

3. Start the NATS container:

```bash
docker run -d \
  --name open-a2a-nats \
  -p 4222:4222 \
  -v ~/nats/nats.conf:/etc/nats/nats.conf:ro \
  nats:latest \
  -c /etc/nats/nats.conf
```

4. In your cloud firewall, open `tcp:4222` to this instance (at least from your own IP).

> **Domain & DNS configuration note**  
> - If you want to access the node via a hostname (e.g. `nats.open-a2a.org`), create an **A record** pointing that subdomain to the server's public IP.  
> - If you are using Cloudflare or similar, make sure this record is set to **DNS only** (no HTTP proxy/CDN in front; in Cloudflare this is the grey cloud, not orange). HTTP proxies typically do not support arbitrary TCP ports like 4222, and will cause connection timeouts from NATS clients.

#### 2.3.2 Local Examples Using the Public Node

On your local dev machine (project cloned, `.venv` created):

```bash
cd Open-A2A

export NATS_URL='nats://opena2a:your-strong-password@IP_S:4222'
.venv/bin/python example/merchant.py
```

In another terminal:

```bash
cd Open-A2A

export NATS_URL='nats://opena2a:your-strong-password@IP_S:4222'
.venv/bin/python example/consumer.py
```

If the `consumer` terminal shows logs like “received 1 offer, order submitted”, and the `merchant` terminal shows “received intent → replied with offer → received order confirm → published logistics request”, then:

- The public NATS node is working correctly;
- Local Agents can already participate in the Open-A2A network over the public Internet.

---

### Scenario 4: Public Relay Node (Outbound WebSocket Only)

> Building on Scenario 2 and 3, you now run a Relay on the same server and expose it as `relay.open-a2a.org`. Any client can join the network using **outbound WebSocket only**, without running NATS locally.

**Topology**:

```
┌─────────────────────────────────────────┐
│  Public node (GCP, IP_S)               │
│  - NATS :4222 (nats.open-a2a.org)      │
│  - Relay :8765 (ws://relay.open-a2a.org:8765) │
│  - Merchant (NATS)                     │
└─────────────────────────────────────────┘
             ▲
             │ NATS_URL=nats://user:pass@nats.open-a2a.org:4222
             ▼
┌─────────────────────────────┐
│  Local dev / other machines │
│  - Consumer via Relay       │
│    RELAY_WS_URL=ws://relay.open-a2a.org:8765 │
└─────────────────────────────┘
```

#### 2.4.1 Public Relay Deployment (Example)

On the same server as the public NATS:

1. Clone project and create virtualenv (if not already done):

```bash
git clone https://github.com/Sawyer-G/Open-A2A.git
cd Open-A2A
python3 -m venv .venv
. .venv/bin/activate
```

2. Install Relay extras:

```bash
.venv/bin/pip install ".[relay]"
```

3. Configure environment and start Relay:

```bash
export NATS_URL='nats://user:pass@nats.open-a2a.org:4222'
export RELAY_WS_HOST='0.0.0.0'
export RELAY_WS_PORT='8765'

.venv/bin/python relay/main.py
```

You should see logs like:

```text
[Relay] Connected to NATS: nats://user:pass@nats.open-a2a.org:4222
[Relay] WebSocket listening on ws://0.0.0.0:8765, Agents can connect outbound to join the network
```

In your cloud firewall, open `tcp:8765` to this instance.  
In DNS, add `relay.open-a2a.org -> IP_S` as an A record, set to **DNS only** (no HTTP proxy/CDN).

#### 2.4.2 Clients Using the Public Relay

On a local dev machine:

```bash
cd Open-A2A
. .venv/bin/activate
.venv/bin/pip install ".[relay]"  # skip if already installed

export RELAY_WS_URL='ws://relay.open-a2a.org:8765'
.venv/bin/python example/consumer_via_relay.py
```

In parallel, run Merchant (directly connected to NATS) either locally or on the server:

```bash
export NATS_URL='nats://user:pass@nats.open-a2a.org:4222'
.venv/bin/python example/merchant.py
```

If `consumer_via_relay.py` shows:

- “connected via Relay: ws://relay.open-a2a.org:8765”; and
- “received 1 offer” and completes the flow;

and `merchant.py` logs intents from `consumer-relay-001` and replies with offers, then:

- The public Relay node is working correctly; and
- Agents without local NATS can join the Open-A2A network using outbound WebSocket only.

---

## 3. Scenario 1: Dual-Server NATS Cluster — Steps

### 3.1 Preparation

- **Server A** and **Server B**: two VPSes with different public IPs; Docker and Python 3.9+ installed; each can reach the other's **cluster port**.
- Firewall: open **4222** (NATS client) and **6222** (NATS cluster route) on each server.  
  If you only run Agents locally on each server, you may only need to open 6222 to the other server.

### 3.2 Server A

1. Create NATS config (replace `IP_B` with B's public IP or hostname):

```conf
# deploy/nats-cluster/nats-a.conf (multi-machine)
port: 4222
cluster {
  name: opena2a
  listen: 0.0.0.0:6222
  routes: [
    nats://IP_B:6222
  ]
}
```

2. Start NATS (choose one):

```bash
# Option 1: Docker
docker run -d --name nats-a -p 4222:4222 -p 6222:6222 \
  -v $(pwd)/nats-a.conf:/config/nats.conf \
  nats:latest -c /config/nats.conf

# Option 2: Use deploy config
# Update routes in deploy/nats-cluster/nats-a.conf to nats://IP_B:6222, then:
# docker compose -f deploy/nats-cluster/docker-compose.yml up -d
```

3. Clone project and run Merchant (local NATS):

```bash
git clone https://github.com/Sawyer-G/Open-A2A.git && cd Open-A2A
make venv && make install
export NATS_URL=nats://127.0.0.1:4222
make run-merchant
```

Keep Merchant running.

### 3.3 Server B

1. Create NATS config (replace `IP_A` with A's public IP or hostname):

```conf
# nats-b.conf (multi-machine)
port: 4222
cluster {
  name: opena2a
  listen: 0.0.0.0:6222
  routes: [
    nats://IP_A:6222
  ]
}
```

2. Start NATS:

```bash
docker run -d --name nats-b -p 4222:4222 -p 6222:6222 \
  -v $(pwd)/nats-b.conf:/config/nats.conf \
  nats:latest -c /config/nats.conf
```

3. Run Consumer (local NATS; cluster syncs subjects with A):

```bash
cd Open-A2A
make venv && make install
export NATS_URL=nats://127.0.0.1:4222
make run-consumer
```

### 3.4 Verification

- On B, the Consumer should print that it receives an offer from A's Merchant after publishing an intent.
- If not:
  - Check A/B connectivity on 6222: `telnet IP_A 6222`, `telnet IP_B 6222`.
  - Check firewall rules.
  - Double-check `routes` IP/hostnames.

---

## 4. Scenario 2: Public + Private (Relay Outbound) — Steps

### 4.1 Server A (Public: NATS + Relay + Merchant)

1. Start NATS:

```bash
docker run -d -p 4222:4222 nats:latest
```

2. Start Relay (requires `make install-relay`):

```bash
cd Open-A2A
make venv && make install-relay
export NATS_URL=nats://127.0.0.1:4222
make run-relay
```

Relay listens on `0.0.0.0:8765`; make sure port **8765** is open in the firewall.

3. Start Merchant in another terminal:

```bash
export NATS_URL=nats://127.0.0.1:4222
make run-merchant
```

### 4.2 User B (Home/Private, Outbound Only)

- B only needs outbound access to `IP_A:8765`; no public IP or inbound port required.

On B's machine:

```bash
cd Open-A2A
make venv && make install-relay
export RELAY_WS_URL=ws://IP_A:8765
python example/consumer_via_relay.py
```

(Replace `IP_A` with A's public IP or domain.)

### 4.3 Verification

- B's Consumer should publish an intent via Relay and receive offers from A's Merchant.
- This shows B can participate in the network with **only outbound WebSocket**, which matches the "everyone has their own Agent in their own network" assumption.

---

## 5. Optional: DHT Discovery Across Networks

If the two sides are **not in the same NATS cluster** (e.g. two independent networks or organizations), you can:

- Use **DHT discovery** so Agents register and find each other in a shared DHT;
- Then connect via Relay or other transports to exchange messages.

See `docs/en/06-progress.md` (DHT discovery backend) and `make run-discovery-dht-demo` for examples. DHT + Relay is a natural combination for multi-cluster, heterogeneous-network setups.

---

## 6. Summary

| Scenario | Use Case | What it Verifies |
|---------|----------|------------------|
| **Dual NATS cluster** | Two people with public servers | Agents on different IPs share one logical NATS subject space. |
| **Public + private Relay** | One public server, one home/office user | An Agent without public IP joins the network via outbound WebSocket only. |
| **DHT + Relay** | Multi-cluster / heterogeneous networks | Cross-cluster discovery and reachability (see docs and examples). |

Under the assumptions “compute is cheap + everyone has an Agent + each deployed in its own network”, **cross-IP testing is a required validation step** to prove the framework achieves its goal. At minimum, we recommend running Scenario 1 and Scenario 2; then add DHT/multi-cluster scenarios as needed.

---

## 7. Complex Networks and Dynamic IPs: What It Means for End Users

In reality, most people's Agents will run in **complex, constrained, dynamic** network environments:

- Home WiFi / 4G / 5G, behind carrier NAT, without a stable public IP;
- Corporate LANs where only a few servers have public ingress; most machines have **outbound-only** connectivity;
- Devices that frequently switch networks (home WiFi, mobile hotspot, VPNs, etc.).

Given this, Open-A2A is designed so that:

- **End users should not have to open ports on their routers.**
  - Personal Agents only need to “connect out” to some public entrypoint (Relay WebSocket, public NATS/Bridge, etc.).
  - This matches the “Public + private Relay” scenario: home/mobile devices only dial `ws://IP_A:8765` outbound to join the network.
- **Stable IP/ports are the responsibility of a few infrastructure nodes.**
  - The community or service providers can run a small number of long-lived NATS nodes, Relay nodes, and DHT bootstrap nodes with fixed hostnames/IPs and open ports (4222, 8765, etc.).
  - Personal Agents just need to know these “entry addresses,” similar to connecting to any public API.
- **DHT and discovery handle “finding each other” in complex topologies.**
  - Even if participants use different NATS clusters or transports, they can still register and discover capabilities in a shared logical network via DHT and discovery protocols, without everyone doing port forwarding at home.

In short:

- Requirements like “open 4222/6222/8765” are for those who **choose to operate public infrastructure nodes** (like your GCP instance), **not** for every end user.
- Typical end users:
  - Run their Agent on a local machine or personal server;
  - Join an existing Open-A2A network via outbound connections (NATS URL, Relay WebSocket, Bridge HTTP);
  - Do not need to manually open ports on home WiFi or mobile networks.

This is one of the core problems Open-A2A aims to solve: given “everyone has their own Agent, network environments are messy and dynamic,” use a **small set of stable nodes + open protocols** so that all Agents can still collaborate on an open network.

