import asyncio
import json
from dataclasses import dataclass
from typing import Awaitable, Callable

import pytest

from open_a2a.discovery_dht import ENV_DHT_BOOTSTRAP, get_default_dht_bootstrap
from open_a2a.discovery_nats import NatsDiscoveryProvider
from open_a2a.transport import MessageSubscription, TransportAdapter


def test_dht_bootstrap_parse_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_DHT_BOOTSTRAP, raising=False)
    # When env is not set, we use the built-in community bootstrap defaults.
    boots = get_default_dht_bootstrap()
    assert isinstance(boots, list)
    assert len(boots) >= 1
    assert ("dht.open-a2a.org", 8469) in boots


def test_dht_bootstrap_parse_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_DHT_BOOTSTRAP, "1.2.3.4:8469, bootstrap.example.org:8470")
    assert get_default_dht_bootstrap() == [("1.2.3.4", 8469), ("bootstrap.example.org", 8470)]


def test_dht_bootstrap_parse_ignores_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_DHT_BOOTSTRAP, "bad, ok.example.org:1234, also-bad:xx")
    assert get_default_dht_bootstrap() == [("ok.example.org", 1234)]


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
        self._subs.setdefault(subject, []).append(cb)
        h = _Sub(subject=subject, transport=self)
        self._sub_handle_to_cb[id(h)] = cb
        return h


def test_nats_discovery_register_responder_multi_reply() -> None:
    async def run() -> None:
        t = FakeTransport()
        d = NatsDiscoveryProvider(transport=t)
        await d.connect()

        def responder(_: dict) -> list[dict]:
            return [{"agent_id": "a1"}, {"agent_id": "a2"}]

        await d.register_responder("intent.food.order", responder)

        reply_to = "_INBOX.open_a2a.test"
        query = json.dumps({"reply_to": reply_to}, ensure_ascii=False).encode("utf-8")
        await t.publish("open_a2a.discovery.query.intent.food.order", query)

        # Two metas should be published to reply_to
        replies = [x for x in t.published if x[0] == reply_to]
        assert len(replies) == 2
        assert json.loads(replies[0][1].decode("utf-8"))["agent_id"] == "a1"
        assert json.loads(replies[1][1].decode("utf-8"))["agent_id"] == "a2"

        await d.disconnect()

    asyncio.run(run())

