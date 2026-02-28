"""
NATS 意图广播与订阅 (RFC-001)
"""

import asyncio
from typing import Awaitable, Callable, Optional

from open_a2a.intent import (
    Intent,
    Offer,
    TOPIC_INTENT_FOOD_ORDER,
    TOPIC_INTENT_FOOD_OFFER_PREFIX,
)

try:
    from nats.aio.client import Client as NATSClient
    from nats.errors import TimeoutError as NATSTimeoutError
except ImportError:
    NATSClient = None  # type: ignore
    NATSTimeoutError = Exception  # type: ignore


class IntentBroadcaster:
    """
    意图广播器 - 封装 NATS 发布/订阅
    """

    def __init__(self, nats_url: str = "nats://localhost:4222") -> None:
        if NATSClient is None:
            raise ImportError("nats-py is required. Install with: pip install nats-py")
        self._nats_url = nats_url
        self._nc: Optional[NATSClient] = None

    async def connect(self) -> None:
        """连接 NATS"""
        self._nc = NATSClient()
        await self._nc.connect(self._nats_url)

    async def disconnect(self) -> None:
        """断开连接"""
        if self._nc:
            await self._nc.drain()
            self._nc = None

    async def publish_intent(self, intent: Intent) -> None:
        """
        发布意图到 intent.food.order
        """
        if not self._nc:
            raise RuntimeError("Not connected. Call connect() first.")
        await self._nc.publish(
            TOPIC_INTENT_FOOD_ORDER,
            intent.to_json().encode("utf-8"),
        )

    async def subscribe_intents(
        self,
        handler: Callable[[Intent], Awaitable[None]],
    ) -> None:
        """
        订阅 intent.food.order，收到意图时调用 handler
        """
        if not self._nc:
            raise RuntimeError("Not connected. Call connect() first.")

        async def _handler(msg):
            data = msg.data.decode("utf-8")
            intent = Intent.from_json(data)
            await handler(intent)

        await self._nc.subscribe(
            TOPIC_INTENT_FOOD_ORDER,
            cb=_handler,
        )

    async def publish_offer(self, offer: Offer, reply_to: str) -> None:
        """
        发布报价到意图的 reply_to 主题
        """
        if not self._nc:
            raise RuntimeError("Not connected. Call connect() first.")
        await self._nc.publish(
            reply_to,
            offer.to_json().encode("utf-8"),
        )

    async def publish_and_collect_offers(
        self,
        intent: Intent,
        timeout_seconds: float = 10.0,
        on_offer: Optional[Callable[[Offer], Awaitable[None]]] = None,
    ) -> list[Offer]:
        """
        发布意图并收集报价。先订阅 reply_to，再发布，等待 timeout 后返回。
        """
        if not self._nc:
            raise RuntimeError("Not connected. Call connect() first.")

        subject = intent.reply_to
        offers: list[Offer] = []

        async def _handler(msg):
            data = msg.data.decode("utf-8")
            offer = Offer.from_json(data)
            offers.append(offer)
            if on_offer:
                await on_offer(offer)

        sub = await self._nc.subscribe(subject, cb=_handler)
        await self.publish_intent(intent)

        await asyncio.sleep(timeout_seconds)
        await sub.unsubscribe()

        return offers
