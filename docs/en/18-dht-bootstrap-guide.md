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

## 3. “Community bootstrap list” (usable default + overridable)

This repo now ships a **usable default** `DEFAULT_DHT_BOOTSTRAP` (so you can join a shared DHT network out of the box):  
`open_a2a/discovery_dht.py` → `DEFAULT_DHT_BOOTSTRAP = [("dht.open-a2a.org", 8469), ...]`

> Operator note: for production, you should still set `OPEN_A2A_DHT_BOOTSTRAP` explicitly (upgrade/scale/failover), rather than relying on the code default long-term.

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

### 4.1 Verify a public bootstrap from your laptop (Docker, recommended)

> Goal: verify your DHT bootstrap (e.g. `dht.open-a2a.org:8469`) is reachable from the Internet and supports join + write + read.  
> This check does not depend on your local Python environment: it runs inside a Docker container.

Prereqs:

- Docker installed locally
- Your bootstrap is reachable publicly (recommended **UDP 8469**, optional TCP 8469)

From the repo root (this starts two temporary DHT nodes A/B, both bootstrapped to the same public entry; A registers, B discovers):

```bash
## Option 1: use the script (recommended)
bash scripts/e2e-dht-bootstrap.sh dht.open-a2a.org:8469

## Option 2: manual docker run (equivalent)
docker run --rm -t -v "$PWD:/repo" -w /repo python:3.12-slim bash -lc \
  "python -m pip install -q --no-cache-dir -e '.[dht]' && python - <<'PY'
import asyncio
from open_a2a.discovery_dht import DhtDiscoveryProvider

BOOT = [('dht.open-a2a.org', 8469)]
CAP = 'intent.food.order'

async def main():
  a = DhtDiscoveryProvider(dht_port=18468, bootstrap_nodes=BOOT)
  b = DhtDiscoveryProvider(dht_port=18469, bootstrap_nodes=BOOT)
  await a.connect()
  await b.connect()
  try:
    meta = {'agent_id':'local-e2e-a','capabilities':[CAP],'endpoints':[]}
    await a.register(CAP, meta)
    await asyncio.sleep(1.0)
    res = await b.discover(CAP, timeout_seconds=2.0)
    print('discover_count', len(res))
    hit = [x for x in res if isinstance(x, dict) and x.get('agent_id')=='local-e2e-a']
    print('hit', bool(hit))
    if hit:
      print('hit_meta', hit[0])
    else:
      print('sample', res[:3])
  finally:
    await a.disconnect()
    await b.disconnect()

asyncio.run(main())
PY"
```

Expected output:

- `discover_count` > 0
- `hit True`

Note:

- You may see logs like `Did not receive reply ...` (kademlia routing probes / unreachable nodes). This is not necessarily a failure; treat the final `hit True` as the success signal.

---

## 5. Operator tips

- Keep bootstrap nodes online (like “entry DNS”)
- Use at least 2 bootstrap nodes for resiliency
- DHT provides discovery indexing only; communication still happens via endpoints (NATS/Relay/HTTP)
- **Directory quality**: DHT won’t delete stale records automatically. Providers should **renew periodically**
  by re-registering (repeat `register()` to refresh expiry).
  - See: `example/dht_discovery_renew.py` (`make run-dht-discovery-renew`)

