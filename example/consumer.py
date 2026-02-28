#!/usr/bin/env python3
"""
Consumer Agent - 消费者 Agent 示例

发送「想吃面」意图，收集商家报价，选择后确认订单。
"""

import asyncio
import os

# 支持从项目根目录运行
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from open_a2a import Intent, Offer, OrderConfirm, IntentBroadcaster
from open_a2a.intent import Location, TOPIC_INTENT_FOOD_OFFER_PREFIX


async def main() -> None:
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    consumer_id = os.getenv("CONSUMER_ID", "consumer-001")

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
            sender_id=consumer_id,
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

        if not offers:
            print("[Consumer] 无报价，退出")
            return

        # 选择第一个报价（可扩展为选最低价等）
        chosen = offers[0]
        print(f"[Consumer] 选择 {chosen.sender_id} 的报价，确认订单...")

        confirm = OrderConfirm(
            intent_id=intent.id,
            offer_id=chosen.id,
            consumer_id=consumer_id,
            delivery=intent.location,  # 配送地址使用意图中的位置
        )
        await broadcaster.publish_order_confirm(confirm)
        print(f"[Consumer] 已发布订单确认 order={confirm.id}，等待配送...")
        await asyncio.sleep(2)  # 给 Merchant/Carrier 处理时间
        print("[Consumer] 订单已提交，流程完成")

    finally:
        await broadcaster.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
