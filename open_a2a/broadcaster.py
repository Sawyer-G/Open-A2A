"""
意图广播与订阅 (RFC-001)

基于传输层抽象，默认使用 NATS。可通过 transport 参数注入其他实现（HTTP、WebSocket 等）。
"""

import asyncio
from typing import TYPE_CHECKING, Awaitable, Callable, Optional

from open_a2a.intent import (
    Intent,
    Offer,
    OrderConfirm,
    LogisticsRequest,
    LogisticsAccept,
    TOPIC_INTENT_FOOD_ORDER,
    TOPIC_INTENT_FOOD_OFFER_PREFIX,
    TOPIC_ORDER_CONFIRM,
    TOPIC_LOGISTICS_REQUEST,
    TOPIC_LOGISTICS_ACCEPT_PREFIX,
)
from open_a2a.transport import TransportAdapter

if TYPE_CHECKING:
    from open_a2a.identity import AgentIdentity


def _get_identity_module():
    """延迟导入 identity，避免循环依赖"""
    try:
        from open_a2a import identity
        return identity
    except ImportError:
        return None


def _default_transport(nats_url: str) -> TransportAdapter:
    """延迟导入 NATS 适配器，避免循环依赖"""
    from open_a2a.transport_nats import NatsTransportAdapter
    return NatsTransportAdapter(nats_url)


class IntentBroadcaster:
    """
    意图广播器 - 基于传输适配器的发布/订阅

    支持注入自定义 TransportAdapter，实现传输层可替换（设计原则 2.3）。
    默认使用 NATS。
    """

    def __init__(
        self,
        nats_url: str = "nats://localhost:4222",
        transport: Optional[TransportAdapter] = None,
        identity: Optional["AgentIdentity"] = None,  # noqa: F821
    ) -> None:
        if transport is not None:
            self._transport = transport
            self._owns_transport = False
        else:
            self._transport = _default_transport(nats_url)
            self._owns_transport = True
        self._identity = identity

    async def connect(self) -> None:
        """建立传输连接"""
        await self._transport.connect()

    async def disconnect(self) -> None:
        """断开连接（仅当 broadcaster 拥有 transport 时断开）"""
        if self._owns_transport:
            await self._transport.disconnect()

    def _maybe_sign(self, payload: dict) -> bytes:
        """若配置了 identity 则签名，否则返回 JSON"""
        if self._identity:
            mod = _get_identity_module()
            if mod and mod.AgentIdentity.is_available():
                jws = self._identity.sign(payload)
                return jws.encode("utf-8")
        import json
        return json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def _parse_incoming(self, data: bytes):
        """解析入站消息：支持 JWS 或 JSON"""
        text = data.decode("utf-8")
        mod = _get_identity_module()
        if mod:
            return mod.parse_message(text)
        import json
        return json.loads(text), None

    async def publish_intent(self, intent: Intent) -> None:
        """
        发布意图到 intent.food.order
        """
        payload = intent.to_dict()
        body = self._maybe_sign(payload)
        await self._transport.publish(TOPIC_INTENT_FOOD_ORDER, body)

    async def subscribe_intents(
        self,
        handler: Callable[[Intent], Awaitable[None]],
    ) -> None:
        """
        订阅 intent.food.order，收到意图时调用 handler
        """
        async def _handler(data: bytes):
            payload, signer_did = self._parse_incoming(data)
            intent = Intent.from_dict(payload, signer_did=signer_did)
            await handler(intent)

        await self._transport.subscribe(TOPIC_INTENT_FOOD_ORDER, cb=_handler)

    async def publish_offer(self, offer: Offer, reply_to: str) -> None:
        """
        发布报价到意图的 reply_to 主题
        """
        payload = offer.to_dict()
        body = self._maybe_sign(payload)
        await self._transport.publish(reply_to, body)

    async def publish_and_collect_offers(
        self,
        intent: Intent,
        timeout_seconds: float = 10.0,
        on_offer: Optional[Callable[[Offer], Awaitable[None]]] = None,
    ) -> list[Offer]:
        """
        发布意图并收集报价。先订阅 reply_to，再发布，等待 timeout 后返回。
        """
        subject = intent.reply_to
        offers: list[Offer] = []

        async def _handler(data: bytes):
            payload, signer_did = self._parse_incoming(data)
            offer = Offer.from_dict(payload, signer_did=signer_did)
            offers.append(offer)
            if on_offer:
                await on_offer(offer)

        sub = await self._transport.subscribe(subject, cb=_handler)
        await self.publish_intent(intent)

        await asyncio.sleep(timeout_seconds)
        await sub.unsubscribe()

        return offers

    # --- 订单确认 (Phase 3) ---

    async def publish_order_confirm(self, confirm: OrderConfirm) -> None:
        """发布订单确认到 intent.food.order_confirm"""
        await self._transport.publish(
            TOPIC_ORDER_CONFIRM,
            confirm.to_json().encode("utf-8"),
        )

    async def subscribe_order_confirm(
        self,
        handler: Callable[[OrderConfirm], Awaitable[None]],
    ) -> None:
        """订阅 intent.food.order_confirm"""
        async def _handler(data: bytes):
            confirm = OrderConfirm.from_json(data.decode("utf-8"))
            await handler(confirm)

        await self._transport.subscribe(TOPIC_ORDER_CONFIRM, cb=_handler)

    # --- 配送 (Phase 3) ---

    async def publish_logistics_request(self, req: LogisticsRequest) -> None:
        """发布配送请求到 intent.logistics.request"""
        await self._transport.publish(
            TOPIC_LOGISTICS_REQUEST,
            req.to_json().encode("utf-8"),
        )

    async def subscribe_logistics_requests(
        self,
        handler: Callable[[LogisticsRequest], Awaitable[None]],
    ) -> None:
        """订阅 intent.logistics.request"""
        async def _handler(data: bytes):
            req = LogisticsRequest.from_json(data.decode("utf-8"))
            await handler(req)

        await self._transport.subscribe(TOPIC_LOGISTICS_REQUEST, cb=_handler)

    async def publish_logistics_accept(
        self, accept: LogisticsAccept, reply_to: str
    ) -> None:
        """发布配送接单到 reply_to"""
        await self._transport.publish(
            reply_to,
            accept.to_json().encode("utf-8"),
        )

    async def publish_and_collect_logistics_accepts(
        self,
        req: LogisticsRequest,
        timeout_seconds: float = 10.0,
        on_accept: Optional[
            Callable[[LogisticsAccept], Awaitable[None]]
        ] = None,
    ) -> list[LogisticsAccept]:
        """发布配送请求并收集接单"""
        subject = req.reply_to
        accepts: list[LogisticsAccept] = []

        async def _handler(data: bytes):
            accept = LogisticsAccept.from_json(data.decode("utf-8"))
            accepts.append(accept)
            if on_accept:
                await on_accept(accept)

        sub = await self._transport.subscribe(subject, cb=_handler)
        await self.publish_logistics_request(req)

        await asyncio.sleep(timeout_seconds)
        await sub.unsubscribe()

        return accepts
