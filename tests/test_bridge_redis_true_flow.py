import asyncio
import importlib
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional

import pytest
from starlette.requests import Request

from open_a2a.discovery_nats import NatsDiscoveryProvider
from open_a2a.transport import MessageSubscription, TransportAdapter


@dataclass
class _Sub(MessageSubscription):
    subject: str
    transport: "FakeTransport"
    active: bool = True

    async def unsubscribe(self) -> None:
        if not self.active:
            return
        self.active = False
        self.transport._subs[self.subject] = [
            cb for cb in self.transport._subs.get(self.subject, []) if cb is not self._cb
        ]

    @property
    def _cb(self) -> Callable[[bytes], Awaitable[None]]:
        return self.transport._sub_handle_to_cb[id(self)]


class FakeTransport(TransportAdapter):
    def __init__(self) -> None:
        self._subs: dict[str, list[Callable[[bytes], Awaitable[None]]]] = {}
        self._sub_handle_to_cb: dict[int, Callable[[bytes], Awaitable[None]]] = {}

    async def connect(self) -> None:
        return

    async def disconnect(self) -> None:
        self._subs.clear()
        self._sub_handle_to_cb.clear()

    async def publish(self, subject: str, data: bytes) -> None:
        for cb in list(self._subs.get(subject, [])):
            await cb(data)

    async def subscribe(
        self, subject: str, cb: Callable[[bytes], Awaitable[None]]
    ) -> MessageSubscription:
        self._subs.setdefault(subject, []).append(cb)
        h = _Sub(subject=subject, transport=self)
        self._sub_handle_to_cb[id(h)] = cb
        return h


def _mk_request(headers: Optional[Dict[str, str]] = None) -> Request:
    raw_headers = []
    for k, v in (headers or {}).items():
        raw_headers.append((k.lower().encode("utf-8"), v.encode("utf-8")))
    scope: dict[str, Any] = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "headers": raw_headers,
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


def test_bridge_redis_backend_register_then_discover_via_responder(monkeypatch: pytest.MonkeyPatch) -> None:
    async def run() -> None:
        # Enable redis backend mode in bridge.main.
        monkeypatch.setenv("BRIDGE_DISCOVERY_REDIS_URL", "redis://fake:6379/0")
        monkeypatch.setenv("OA2A_STRICT_SECURITY", "0")

        from tests.test_bridge_redis_registry import FakeRedis

        from bridge import main as bridge_main

        importlib.reload(bridge_main)

        # Wire up fake redis and fake NATS transport.
        fake_redis = FakeRedis()
        bridge_main._redis = fake_redis

        t = FakeTransport()
        bridge_main.discovery = NatsDiscoveryProvider(transport=t)
        await bridge_main.discovery.connect()
        bridge_main._discovery_status = "connected"
        bridge_main._discovery_error = ""

        # Register an agent via the Bridge API handler.
        req = bridge_main.RegisterCapabilitiesRequest(
            agent_id="agent-a",
            capabilities=["intent.food.order"],
            meta={"agent_id": "agent-a", "region": "test"},
            ttl_seconds=30,
        )
        await bridge_main.register_capabilities(req, request=_mk_request())

        # Discover should yield that meta via NATS responder + redis registry.
        results = await bridge_main.discovery.discover("intent.food.order", timeout_seconds=0.01)
        assert len(results) == 1
        assert results[0]["agent_id"] == "agent-a"
        assert results[0]["region"] == "test"

        # Stats should reflect registry state.
        stats = await bridge_main.discovery_stats(request=_mk_request())
        assert stats.providers_total >= 1
        assert stats.by_capability["intent.food.order"] >= 1

        # Expire and cleanup: emulate by rewriting registration with past expiry.
        now = time.time()
        reg_b = bridge_main._Registration(
            agent_id="agent-a",
            capabilities=["intent.food.order"],
            meta={"agent_id": "agent-a", "region": "test"},
            expires_at_ts=now - 1,
            updated_at="t-expired",
        )
        await bridge_main._redis_upsert_registration(reg_b)
        await bridge_main._redis_cleanup_expired()

        stats2 = await bridge_main.discovery_stats(request=_mk_request())
        assert stats2.providers_total == 0

        await bridge_main.discovery.disconnect()

    asyncio.run(run())

