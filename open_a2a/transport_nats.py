"""
NATS 传输适配器

TransportAdapter 的 NATS 参考实现。
"""

from typing import Awaitable, Callable, Optional

from open_a2a.transport import MessageSubscription, TransportAdapter

try:
    from nats.aio.client import Client as NATSClient
except ImportError:
    NATSClient = None  # type: ignore


class _NatsSubscription(MessageSubscription):
    """NATS 订阅句柄"""

    def __init__(self, sub) -> None:
        self._sub = sub

    async def unsubscribe(self) -> None:
        await self._sub.unsubscribe()


class NatsTransportAdapter(TransportAdapter):
    """基于 NATS 的传输适配器"""

    def __init__(self, nats_url: str = "nats://localhost:4222") -> None:
        if NATSClient is None:
            raise ImportError("nats-py is required. Install with: pip install nats-py")
        self._nats_url = nats_url
        self._nc: Optional[NATSClient] = None

    async def connect(self) -> None:
        self._nc = NATSClient()
        await self._nc.connect(self._nats_url)

    async def disconnect(self) -> None:
        if self._nc:
            await self._nc.drain()
            self._nc = None

    async def publish(self, subject: str, data: bytes) -> None:
        if not self._nc:
            raise RuntimeError("Not connected. Call connect() first.")
        await self._nc.publish(subject, data)

    async def subscribe(
        self,
        subject: str,
        cb: Callable[[bytes], Awaitable[None]],
    ) -> MessageSubscription:
        if not self._nc:
            raise RuntimeError("Not connected. Call connect() first.")

        async def _handler(msg):
            await cb(msg.data)

        sub = await self._nc.subscribe(subject, cb=_handler)
        return _NatsSubscription(sub)
