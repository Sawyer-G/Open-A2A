#!/usr/bin/env python3
"""
Consumer via Relay (full A→B→C)

比 `example/consumer_via_relay.py` 多一步：在收集到报价后，会像 `example/consumer.py`
一样发布 `OrderConfirm`，从而触发 Merchant -> LogisticsRequest -> Carrier -> 模拟送达。

时间统计脚本 `scripts/bench_abc_latency.py` 依赖日志关键字，尽量与 consumer.py 保持一致：
- [Consumer] 发布意图
- <- 收到报价:
- [Consumer] 已发布订单确认 ...
- [Consumer] 订单已提交，流程完成
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from open_a2a import Intent, Offer, OrderConfirm, IntentBroadcaster, RelayClientTransport
from open_a2a.intent import Location, TOPIC_INTENT_FOOD_OFFER_PREFIX


def _load_constraints() -> list[str]:
    # 保持与 consumer.py 的默认行为一致（可按需在 env 覆盖）
    return os.getenv("CONSTRAINTS", "No_Coriander,<30min").split(",")


async def main() -> None:
    relay_ws_url = os.getenv("RELAY_WS_URL", "ws://localhost:8765")
    consumer_id = os.getenv("CONSUMER_ID", "consumer-relay-full-001")
    intent_type = os.getenv("INTENT_TYPE", "Pizza")

    transport = RelayClientTransport(relay_ws_url=relay_ws_url)
    broadcaster = IntentBroadcaster(transport=transport)
    await broadcaster.connect()

    constraints = _load_constraints()
    location = Location(lat=31.23, lon=121.47)

    try:
        intent = Intent(
            action="Food_Order",
            type=intent_type,
            location=location,
            constraints=constraints,
            reply_to="",
            sender_id=consumer_id,
        )
        intent.reply_to = f"{TOPIC_INTENT_FOOD_OFFER_PREFIX}.{intent.id}"

        print(f"[Consumer] 发布意图: {intent.type}, 约束: {intent.constraints}")
        print("[Consumer] 等待报价 (10秒)...")

        async def on_offer(offer: Offer) -> None:
            who = offer.sender_did or offer.sender_id
            print(f"  <- 收到报价: {who} {offer.price} {offer.unit}")

        offers = await broadcaster.publish_and_collect_offers(
            intent,
            timeout_seconds=10.0,
            on_offer=on_offer,
        )

        print(f"[Consumer] 共收到 {len(offers)} 个报价")
        if not offers:
            print("[Consumer] 无报价，退出")
            return

        chosen = offers[0]
        who = chosen.sender_did or chosen.sender_id
        print(f"[Consumer] 选择 {who} 的报价，确认订单...")

        confirm = OrderConfirm(
            intent_id=intent.id,
            offer_id=chosen.id,
            consumer_id=consumer_id,
            delivery=intent.location,
        )
        await broadcaster.publish_order_confirm(confirm)
        print(f"[Consumer] 已发布订单确认 order={confirm.id}，等待配送...")

        # 给 Merchant/Carrier 处理时间（与 consumer.py 保持一致）
        await asyncio.sleep(2)
        print("[Consumer] 订单已提交，流程完成")
    finally:
        await broadcaster.disconnect()


if __name__ == "__main__":
    asyncio.run(main())

