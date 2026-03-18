"""
NATS 发现实现

基于请求-响应：查询方向 open_a2a.discovery.query.{capability} 发送 reply_to，
已注册的 Agent 向 reply_to 回复自己的 meta。无需中心化注册表，适用于同 NATS 或 NATS 集群内发现。
"""

import asyncio
import json
import uuid
from typing import Any, Callable, Optional, Union

from open_a2a.discovery import DISCOVERY_QUERY_PREFIX, DiscoveryProvider
from open_a2a.transport import TransportAdapter


# 延迟导入，避免循环依赖
def _default_transport(nats_url: str) -> TransportAdapter:
    from open_a2a.transport_nats import NatsTransportAdapter
    return NatsTransportAdapter(nats_url)


def _query_subject(capability: str) -> str:
    """发现查询主题：open_a2a.discovery.query.{capability}"""
    return f"{DISCOVERY_QUERY_PREFIX}.{capability}"


class NatsDiscoveryProvider(DiscoveryProvider):
    """基于 NATS 的发现实现（请求-响应，多响应方）"""

    def __init__(
        self,
        nats_url: str = "nats://localhost:4222",
        transport: Optional[TransportAdapter] = None,
    ) -> None:
        if transport is not None:
            self._transport = transport
            self._owns_transport = False
        else:
            self._transport = _default_transport(nats_url)
            self._owns_transport = True
        self._subs: dict[str, Any] = {}  # capability -> subscription

    async def connect(self) -> None:
        await self._transport.connect()

    async def disconnect(self) -> None:
        for sub in self._subs.values():
            await sub.unsubscribe()
        self._subs.clear()
        if self._owns_transport:
            await self._transport.disconnect()

    async def register(self, capability: str, meta: dict[str, Any]) -> None:
        subject = _query_subject(capability)
        meta_bytes = json.dumps(meta, ensure_ascii=False).encode("utf-8")

        async def on_query(data: bytes) -> None:
            try:
                payload = json.loads(data.decode("utf-8"))
                reply_to = payload.get("reply_to")
                if reply_to:
                    await self._transport.publish(reply_to, meta_bytes)
            except (json.JSONDecodeError, KeyError):
                pass

        sub = await self._transport.subscribe(subject, cb=on_query)
        self._subs[capability] = sub

    async def register_responder(
        self,
        capability: str,
        responder: Union[
            Callable[[], list[dict[str, Any]]],
            Callable[[dict[str, Any]], list[dict[str, Any]]],
        ],
    ) -> None:
        """
        Register a dynamic responder for a capability.

        Unlike `register()`, this supports replying with **multiple** meta documents for the same capability
        (e.g., an operator bridge acting as a directory for multiple agents).
        """
        subject = _query_subject(capability)

        async def on_query(data: bytes) -> None:
            try:
                payload = json.loads(data.decode("utf-8"))
                reply_to = payload.get("reply_to")
                if not reply_to:
                    return

                try:
                    metas = responder(payload)  # type: ignore[misc]
                except TypeError:
                    metas = responder()  # type: ignore[misc]
                except Exception:
                    return

                for meta in metas or []:
                    try:
                        meta_bytes = json.dumps(meta, ensure_ascii=False).encode("utf-8")
                        await self._transport.publish(reply_to, meta_bytes)
                    except Exception:
                        continue
            except (json.JSONDecodeError, KeyError, TypeError):
                return

        sub = await self._transport.subscribe(subject, cb=on_query)
        self._subs[capability] = sub

    async def unregister(self, capability: str) -> None:
        sub = self._subs.pop(capability, None)
        if sub:
            await sub.unsubscribe()

    async def discover(self, capability: str, timeout_seconds: float = 5.0) -> list[dict[str, Any]]:
        reply_to = f"_INBOX.open_a2a.{uuid.uuid4().hex}"
        results: list[dict[str, Any]] = []

        async def on_reply(data: bytes) -> None:
            try:
                results.append(json.loads(data.decode("utf-8")))
            except json.JSONDecodeError:
                pass

        sub = await self._transport.subscribe(reply_to, cb=on_reply)
        try:
            request = json.dumps({"reply_to": reply_to}, ensure_ascii=False).encode("utf-8")
            await self._transport.publish(_query_subject(capability), request)
            await asyncio.sleep(timeout_seconds)
        finally:
            await sub.unsubscribe()

        return results
