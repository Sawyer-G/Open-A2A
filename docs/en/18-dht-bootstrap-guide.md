# DHT bootstrap (product guide): preferred for cross-node discovery

> Use this when Node X and Node Y run **independent NATS servers** (not in the same cluster, and you do not bridge discovery subjects) but you still want directory-style “discover across nodes”.  
> Recommendation: **use DHT discovery** (`DhtDiscoveryProvider`) instead of bridging `_INBOX.*` via subject-bridges.

---

## 1. Why prefer DHT for cross-node discovery?

NATS Discovery (RFC-002) works great within a single NATS subject space, but cross-node setups face:

- queries are published on one side, replies typically go to `_INBOX.*`;
- making B respond to A requires bridging both the query subject and the reply subjects;
- in practice this often implies bridging `_INBOX.*`, which increases message volume and loop risk.

Therefore, for multi-operator networks with independent NATS:

> Prefer **DHT discovery** (Kademlia) for cross-node directory indexing.

---

## 2. Configure `OPEN_A2A_DHT_BOOTSTRAP`

Environment variable: `OPEN_A2A_DHT_BOOTSTRAP`

Format:

```text
host1:port1,host2:port2
```

Example:

```bash
export OPEN_A2A_DHT_BOOTSTRAP="1.2.3.4:8469,bootstrap.example.org:8469"
```

Implementation: `open_a2a/discovery_dht.py` (`ENV_DHT_BOOTSTRAP = "OPEN_A2A_DHT_BOOTSTRAP"`).

---

## 3. “Community bootstrap list” (placeholder)

The built-in `DEFAULT_DHT_BOOTSTRAP` is currently empty (placeholder):  
`open_a2a/discovery_dht.py` → `DEFAULT_DHT_BOOTSTRAP = []`

You have two options:

1) **Run your own bootstrap (recommended for operators)**
- Run a long-lived DHT node on a public server (e.g. port `8469`)
- Publish it as `OPEN_A2A_DHT_BOOTSTRAP` for participants

2) **Use community bootstrap (future)**
- This repo already includes a copyable bootstrap kit: `deploy/dht-bootstrap/`
- Community list & governance: `docs/en/19-dht-community-bootstraps.md`

---

## 4. Minimal verification (dev demo)

The repo includes a demo: `example/discovery_dht_demo.py`  
It starts two local DHT nodes and demonstrates register/discover.

```bash
make install-dht
make run-discovery-dht-demo
```

---

## 5. Operator tips

- Keep bootstrap nodes online (like “entry DNS”)
- Use at least 2 bootstrap nodes for resiliency
- DHT provides discovery indexing only; communication still happens via endpoints (NATS/Relay/HTTP)
- **Directory quality**: DHT won’t delete stale records automatically. Providers should **renew periodically**
  by re-registering (repeat `register()` to refresh expiry).
  - See: `example/dht_discovery_renew.py` (`make run-dht-discovery-renew`)

