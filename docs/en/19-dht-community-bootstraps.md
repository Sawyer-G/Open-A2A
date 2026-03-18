# DHT community bootstraps: list & governance

> Goal: make the DHT path for cross-node discovery not only “implemented”, but actually “easy to join”.  
> Bootstraps are entry points to join the Kademlia overlay. They **do not** provide trust/authority (see RFC-004 for trust).

---

## 1. Community bootstrap list (interim)

You have two options:

1) **Use community bootstraps (recommended: lowest friction)**  
2) **Run your own bootstraps (operators / private networks)**

> Note: until the project publishes official community bootstraps with stable domains, this repo provides a copyable bootstrap kit + a contribution process. Once community nodes are online, this document will list real addresses.

### 1.1 Online nodes (available)

- **`dht.open-a2a.org:8469`**
  - **Protocols**: TCP + UDP
  - **Maintainer**: Open-A2A (Sawyer)
  - **Since**: 2026-03-18
  - **Notes**: entrypoint to join the Open-A2A community DHT overlay (no trust/authority implied)

> Redundancy goal (P0): the community list should have at least **2 long-running** bootstraps (preferably different hosts/operators) to avoid a single point of failure.
> Today we still lack the 2nd entrypoint — contributions welcome.

---

## 2. Run a bootstrap node (copy & run)

This repo includes a kit: `deploy/dht-bootstrap/`

From the repo root:

```bash
docker compose -f deploy/dht-bootstrap/docker-compose.yml up -d --build
```

Open firewall/security group for both TCP and UDP:

- `DHT_PORT` (default `8469`)

Optional: chain-join multiple bootstraps into the same overlay:

```bash
export DHT_BOOTSTRAP="seed-1.example.org:8469,seed-2.example.org:8469"
docker compose -f deploy/dht-bootstrap/docker-compose.yml up -d --build
```

---

## 3. How to add your node to the community list

Submit a PR updating this document with:

- **Domain or public IP** (e.g. `seed-1.example.org`)
- **Port** (recommended `8469`)
- **Region** (optional)
- **Maintainer contact** (optional, for incident coordination)

Minimum recommended requirements:

- long-lived availability (e.g. 95% uptime)
- TCP/UDP reachable
- can be used as a bootstrap by other nodes
- can bootstrap into the same overlay as existing entries (recommended: start your node with `DHT_BOOTSTRAP=<existing entry>`)

Recommended preflight (before publishing your node):

- Run a “join + write + read” check from your laptop (see `docs/en/18-dht-bootstrap-guide.md`)

---

## 4. Removal / replacement (interim)

- If unreachable for 24 hours, it may be removed or marked `inactive`
- Maintainers can submit PRs to rotate addresses

