#!/usr/bin/env python3
"""
DHT Discovery Renewal (client best practice)

Purpose:
- Demonstrate how a client should periodically "renew" DHT registrations
  to keep directory quality and avoid zombie meta.

Notes:
- DHT itself does not enforce TTL. Open-A2A embeds `_expires_at_ts` into each record and filters on read.
- Re-registering the same capability replaces the previous record (same _reg_id) and refreshes expiry.

Usage:
  export OPEN_A2A_DHT_BOOTSTRAP="bootstrap.example.org:8469"
  export DHT_PORT=8468
  export AGENT_ID=merchant-dht-001
  export CAPABILITY=intent.food.order
  export RENEW_EVERY_SECONDS=120
  python example/dht_discovery_renew.py
"""

import asyncio
import os
from typing import Any

from open_a2a.discovery_dht import DhtDiscoveryProvider


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


async def main() -> None:
    port = int(_env("DHT_PORT", "8468") or "8468")
    agent_id = _env("AGENT_ID", "agent-dht-001")
    capability = _env("CAPABILITY", "intent.food.order")
    renew_every = float(_env("RENEW_EVERY_SECONDS", "120") or "120")

    d = DhtDiscoveryProvider(dht_port=port)
    await d.connect()
    try:
        meta: dict[str, Any] = {"agent_id": agent_id, "capabilities": [capability], "endpoints": []}
        print(f"[dht-renew] agent_id={agent_id} capability={capability} renew_every={renew_every}s")
        while True:
            await d.register(capability, meta)
            print("[dht-renew] ok")
            await asyncio.sleep(renew_every)
    finally:
        await d.disconnect()


if __name__ == "__main__":
    asyncio.run(main())

