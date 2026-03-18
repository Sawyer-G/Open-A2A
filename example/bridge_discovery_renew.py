#!/usr/bin/env python3
"""
Bridge Discovery Renewal (Path B client best practice)

Purpose:
- Demonstrate how a client should periodically renew capability registrations
  when Bridge enables TTL expiration (operator-grade directory).

Usage:
  export BRIDGE_URL=http://localhost:8080
  export AGENT_ID=merchant-001
  export CAPABILITIES=intent.food.order,intent.logistics.request
  export TTL_SECONDS=60
  export RENEW_EVERY_SECONDS=30
  # optional:
  export BRIDGE_DISCOVERY_REGISTER_TOKEN=...
  python example/bridge_discovery_renew.py
"""

import json
import os
import time
from typing import Any

import httpx


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _split_caps(value: str) -> list[str]:
    return [c.strip() for c in (value or "").split(",") if c.strip()]


def main() -> None:
    bridge_url = _env("BRIDGE_URL", "http://localhost:8080").rstrip("/")
    agent_id = _env("AGENT_ID", "agent-001")
    caps = _split_caps(_env("CAPABILITIES", "intent.food.order"))
    ttl = float(_env("TTL_SECONDS", "60") or "60")
    renew_every = float(_env("RENEW_EVERY_SECONDS", str(max(10.0, ttl / 2))) or "30")
    token = _env("BRIDGE_DISCOVERY_REGISTER_TOKEN", "")

    meta: dict[str, Any] = {"agent_id": agent_id, "endpoints": [], "capabilities": caps}
    if _env("META_JSON", ""):
        try:
            meta.update(json.loads(_env("META_JSON")))
        except json.JSONDecodeError:
            pass

    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"{bridge_url}/api/register_capabilities"
    payload = {"agent_id": agent_id, "capabilities": caps, "meta": meta, "ttl_seconds": ttl}

    print(f"[renew] Bridge: {bridge_url}")
    print(f"[renew] agent_id={agent_id} caps={caps} ttl={ttl}s renew_every={renew_every}s")

    with httpx.Client(timeout=5.0) as client:
        while True:
            try:
                r = client.post(url, headers=headers, json=payload)
                if r.status_code >= 400:
                    print(f"[renew][warn] HTTP {r.status_code}: {r.text}")
                else:
                    data = r.json()
                    print(f"[renew] ok expires_at={data.get('expires_at','')}")
            except Exception as e:
                print(f"[renew][warn] request failed: {e}")
            time.sleep(renew_every)


if __name__ == "__main__":
    main()

