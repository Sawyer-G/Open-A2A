#!/usr/bin/env python3
"""
Merchant Agent - 商家 Agent 示例

订阅「想吃面」意图，自动回复报价。
"""

import asyncio
import os

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from open_a2a import Intent, Offer, IntentBroadcaster


async def main() -> None:
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    merchant_id = os.getenv("MERCHANT_ID", "merchant-001")

    broadcaster = IntentBroadcaster(nats_url)
    await broadcaster.connect()

    async def handle_intent(intent: Intent) -> None:
        print(f"[Merchant] 收到意图: {intent.type} from {intent.sender_id}")
        # 简单逻辑：匹配到面条就报价
        if intent.type.lower() == "noodle":
            offer = Offer(
                intent_id=intent.id,
                price=18.0,
                unit="UNIT",
                eta_minutes=15,
                description="手工拉面，不加香菜",
                sender_id=merchant_id,
            )
            await broadcaster.publish_offer(offer, intent.reply_to)
            print(f"[Merchant] 已回复报价: {offer.price} {offer.unit}")

    await broadcaster.subscribe_intents(handle_intent)
    print(f"[Merchant] 已订阅 intent.food.order，等待意图... (Ctrl+C 退出)")

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
