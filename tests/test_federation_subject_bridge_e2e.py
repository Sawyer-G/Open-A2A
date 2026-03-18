import asyncio
import importlib
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

import pytest


@dataclass
class _Msg:
    subject: str
    data: bytes
    headers: Optional[dict[str, str]] = None


def _match(pattern: str, subject: str) -> bool:
    if pattern.endswith(">"):
        return subject.startswith(pattern[:-1])
    return pattern == subject


class FakeNATSClient:
    def __init__(self) -> None:
        self._subs: list[tuple[str, Callable[[_Msg], Awaitable[None]]]] = []
        self.connected_to: str = ""

    async def connect(self, url: str) -> None:
        self.connected_to = url

    async def subscribe(self, subject: str, cb: Callable[[_Msg], Awaitable[None]]) -> Any:
        self._subs.append((subject, cb))
        return object()

    async def publish(self, subject: str, data: bytes, headers: Optional[dict[str, str]] = None) -> None:
        msg = _Msg(subject=subject, data=data, headers=headers or {})
        # Deliver to all matching subscriptions (best-effort, sequential for determinism).
        for pat, cb in list(self._subs):
            if _match(pat, subject):
                await cb(msg)

    async def drain(self) -> None:
        self._subs.clear()


def test_subject_bridge_forwards_and_prevents_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    async def run() -> None:
        import federation.subject_bridge as sb

        importlib.reload(sb)

        # Patch NATS client to avoid real network.
        monkeypatch.setattr(sb, "NATSClient", FakeNATSClient, raising=True)

        cfg = sb.BridgeConfig(
            bridge_id="x-y-bridge",
            nats_a="nats://a:4222",
            nats_b="nats://b:4222",
            subjects=["intent.>"],
            max_hops=1,
            dedupe_ttl_seconds=10.0,
            stats_interval_seconds=999.0,
            log_forward_samples=False,
        )
        b = sb.SubjectBridge(cfg)
        await b.connect()

        received_on_b: list[_Msg] = []

        async def sink_b(msg: _Msg) -> None:
            received_on_b.append(msg)

        # Subscribe a sink on B to observe forwarded message.
        assert b._nc_b is not None
        await b._nc_b.subscribe("intent.>", cb=sink_b)

        task = asyncio.create_task(b.run())
        try:
            # Give run() a moment to set up subscriptions.
            await asyncio.sleep(0)

            # Publish on A; should forward to B once, and NOT bounce back.
            assert b._nc_a is not None
            await b._nc_a.publish("intent.food.order", b"hello", headers={})

            await asyncio.sleep(0)

            assert len(received_on_b) >= 1
            assert received_on_b[0].subject == "intent.food.order"
            assert received_on_b[0].data == b"hello"

            # Forwarded message should carry loop-control headers.
            h = received_on_b[0].headers or {}
            assert h.get("X-OA2A-Bridge") == "x-y-bridge"
            assert h.get("X-OA2A-Hop") == "1"

            # Ensure bridge observed at least one forward and one self-skip (from B handler).
            async with b._lock:
                s = dict(b._stats)
            assert s["a_to_b_forwarded"] >= 1
            assert s["skipped_self"] >= 1
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            await b.disconnect()

    asyncio.run(run())

