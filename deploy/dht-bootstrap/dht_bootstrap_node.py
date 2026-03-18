#!/usr/bin/env python3
"""
Open-A2A DHT bootstrap node (operator/community infrastructure)

Goal:
- Run a long-lived Kademlia DHT node that other nodes can bootstrap from.

Notes:
- This node does NOT imply trust/identity. It's an entry point to join the DHT overlay.
- For multi-operator networks, provide at least 2 bootstrap nodes to avoid single points of failure.
"""

import asyncio
import os
from typing import List, Tuple

try:
    from kademlia.network import Server as KademliaServer
except ImportError as e:
    raise RuntimeError("kademlia is required. Install with: pip install open-a2a[dht]") from e


def _env(name: str, default: str) -> str:
    return os.getenv(name, default).strip()


def _parse_bootstrap(value: str) -> List[Tuple[str, int]]:
    out: List[Tuple[str, int]] = []
    raw = (value or "").strip()
    if not raw:
        return out
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            continue
        host, port_str = part.rsplit(":", 1)
        try:
            out.append((host.strip(), int(port_str.strip())))
        except ValueError:
            continue
    return out


async def main() -> None:
    host = _env("DHT_HOST", "0.0.0.0")
    port = int(_env("DHT_PORT", "8469") or "8469")
    bootstrap = _parse_bootstrap(_env("DHT_BOOTSTRAP", ""))

    node = KademliaServer()
    await node.listen(port, interface=host)
    if bootstrap:
        await node.bootstrap(bootstrap)

    print(f"[dht-bootstrap] listening: {host}:{port}")
    if bootstrap:
        print(f"[dht-bootstrap] bootstrapped to: {', '.join([f'{h}:{p}' for h,p in bootstrap])}")
    else:
        print("[dht-bootstrap] no upstream bootstrap configured (this can be a seed node)")

    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())

