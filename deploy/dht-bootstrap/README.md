# DHT bootstrap node (community/operator kit)

This kit runs a long-lived DHT bootstrap node for Open-A2A cross-node discovery.

## What this is (and is not)

- **Is**: an entry point for nodes to join the same Kademlia DHT overlay (`DhtDiscoveryProvider`).
- **Is NOT**: an identity/trust authority. Trust is handled separately (see RFC-004).

## Quick start (Docker)

From the repo root:

```bash
docker compose -f deploy/dht-bootstrap/docker-compose.yml up -d --build
```

Expose `DHT_PORT` (default `8469`) on your firewall for both TCP and UDP.

## Configuration

- `DHT_HOST` (default `0.0.0.0`): bind address
- `DHT_PORT` (default `8469`): listen port
- `DHT_BOOTSTRAP` (optional): upstream bootstrap list, comma-separated `host:port`

Example:

```bash
export DHT_PORT=8469
export DHT_BOOTSTRAP="seed-1.example.org:8469,seed-2.example.org:8469"
docker compose -f deploy/dht-bootstrap/docker-compose.yml up -d --build
```

## Operator notes

- Run at least **two** independent bootstrap nodes for resiliency.
- Keep bootstrap nodes stable (like DNS seeds): long-lived, monitored, with automatic restart.

