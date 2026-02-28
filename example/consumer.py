#!/usr/bin/env python3
"""
Consumer Agent - 消费者 Agent 示例

发送「想吃面」意图，收集商家报价。
"""

import asyncio
import os

# 支持从项目根目录运行
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from open_a2a import Intent, Offer, IntentBroadcaster
from open_a2a.intent import Location, TOPIC_INTENT_FOOD_OFFER_PREFIX


async def main() -> None:
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")

    broadcaster = IntentBroadcaster(nats_url)
    await broadcaster.connect()

    try:
        # 创建意图：想吃面条，不加香菜，30分钟内
        intent = Intent(
            action="Food_Order",
            type="Noodle",
            location=Location(lat=31.23, lon=121.47),
            constraints=["No_Coriander", "<30min"],
            reply_to="",  # 下面设置
            sender_id="consumer-001",
        )
        intent.reply_to = f"{TOPIC_INTENT_FOOD_OFFER_PREFIX}.{intent.id}"

        print(f"[Consumer] 发布意图: {intent.type}, 约束: {intent.constraints}")
        print(f"[Consumer] 等待报价 (10秒)...")

        async def on_offer(offer: Offer) -> None:
            print(f"  <- 收到报价: {offer.sender_id} {offer.price} {offer.unit}")

        offers = await broadcaster.publish_and_collect_offers(
            intent,
            timeout_seconds=10.0,
            on_offer=on_offer,
        )

        print(f"[Consumer] 共收到 {len(offers)} 个报价")
        for o in offers:
            print(f"  - {o.sender_id}: {o.price} {o.unit}, {o.description or '-'}")

    finally:
        await broadcaster.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
