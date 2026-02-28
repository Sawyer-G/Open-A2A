#!/usr/bin/env python3
"""
Merchant Agent - 商家 Agent 示例

订阅「想吃面」意图，自动回复报价；收到订单确认后发布配送请求。
"""

import asyncio
import os
import uuid

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from open_a2a import (
    Intent,
    Offer,
    OrderConfirm,
    LogisticsRequest,
    LogisticsAccept,
    IntentBroadcaster,
)
from open_a2a.intent import Location, TOPIC_LOGISTICS_ACCEPT_PREFIX

# 商家位置（取餐点）
MERCHANT_LOCATION = Location(lat=31.23, lon=121.47)
DEFAULT_DELIVERY = Location(lat=31.25, lon=121.50)


async def main() -> None:
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    merchant_id = os.getenv("MERCHANT_ID", "merchant-001")

    broadcaster = IntentBroadcaster(nats_url)
    await broadcaster.connect()

    # 记录本商家发出的 offer_id，用于过滤订单确认
    my_offer_ids: set[str] = set()

    async def handle_intent(intent: Intent) -> None:
        print(f"[Merchant] 收到意图: {intent.type} from {intent.sender_id}")
        if intent.type.lower() == "noodle":
            offer = Offer(
                intent_id=intent.id,
                price=18.0,
                unit="UNIT",
                eta_minutes=15,
                description="手工拉面，不加香菜",
                sender_id=merchant_id,
            )
            my_offer_ids.add(offer.id)
            await broadcaster.publish_offer(offer, intent.reply_to)
            print(f"[Merchant] 已回复报价: {offer.price} {offer.unit} (offer_id={offer.id})")

    async def handle_order_confirm(confirm: OrderConfirm) -> None:
        if confirm.offer_id not in my_offer_ids:
            return
        print(f"[Merchant] 收到订单确认: order={confirm.id}, offer={confirm.offer_id}")
        delivery = confirm.delivery or DEFAULT_DELIVERY
        reply_to = f"{TOPIC_LOGISTICS_ACCEPT_PREFIX}.{uuid.uuid4()}"
        req = LogisticsRequest(
            order_id=confirm.id,
            pickup=MERCHANT_LOCATION,
            delivery=delivery,
            fee=3.0,
            unit="UNIT",
            reply_to=reply_to,
            sender_id=merchant_id,
        )
        print(f"[Merchant] 发布配送请求: order={req.order_id}, 运费={req.fee} {req.unit}")
        accepts = await broadcaster.publish_and_collect_logistics_accepts(req, timeout_seconds=10.0)
        for a in accepts:
            print(f"[Merchant] 骑手接单: {a.sender_id}, ETA {a.eta_minutes} 分钟")
        if accepts:
            print(f"[Merchant] 订单 {confirm.id} 已分配骑手，模拟结算完成")

    await broadcaster.subscribe_intents(handle_intent)
    await broadcaster.subscribe_order_confirm(handle_order_confirm)
    print(f"[Merchant] 已订阅 intent.food.order 与 order_confirm，等待... (Ctrl+C 退出)")

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await broadcaster.disconnect()
        print("[Merchant] 已退出")


if __name__ == "__main__":
    asyncio.run(main())
