import asyncio
import importlib
from dataclasses import dataclass
from typing import Awaitable, Callable

import pytest

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
        self.published: list[tuple[str, bytes]] = []
        self.subscribed: list[str] = []

    async def connect(self) -> None:
        return

    async def disconnect(self) -> None:
        self._subs.clear()
        self._sub_handle_to_cb.clear()

    async def publish(self, subject: str, data: bytes) -> None:
        self.published.append((subject, data))
        for cb in list(self._subs.get(subject, [])):
            await cb(data)

    async def subscribe(
        self, subject: str, cb: Callable[[bytes], Awaitable[None]]
    ) -> MessageSubscription:
        self.subscribed.append(subject)
        self._subs.setdefault(subject, []).append(cb)
        h = _Sub(subject=subject, transport=self)
        self._sub_handle_to_cb[id(h)] = cb
        return h


def test_nats_discovery_reply_to_uses_open_a2a_inbox_and_relay_allows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run() -> None:
        t = FakeTransport()
        d = NatsDiscoveryProvider(transport=t)
        await d.connect()

        # Trigger discover: it should create a reply_to subject
        # that is compatible with Relay defaults.
        _ = await d.discover("intent.food.order", timeout_seconds=0.01)

        assert t.subscribed, "discover() should subscribe to reply_to inbox"
        reply_to = t.subscribed[0]
        assert reply_to.startswith("_INBOX.open_a2a."), reply_to

        await d.disconnect()

        # Verify relay default allowlist accepts the reply_to subject.
        monkeypatch.delenv("RELAY_SUBJECT_ALLOWLIST", raising=False)
        monkeypatch.delenv("RELAY_SUBJECT_BLOCKLIST", raising=False)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            import relay.main as relay_main

            importlib.reload(relay_main)
            assert relay_main._is_subject_allowed(reply_to) is True
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    asyncio.run(run())

