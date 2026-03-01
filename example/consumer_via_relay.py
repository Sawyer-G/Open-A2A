#!/usr/bin/env python3
"""
Consumer 经 Relay 出站连接示例

模拟无公网 IP 的 Agent：不直连 NATS，而是连接 Open-A2A Relay（WebSocket 出站），
通过 Relay 参与意图发布与报价收集。无需域名或 webhook 配置。

前置：先启动 NATS 与 Relay（make run-relay），再运行本示例。
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from open_a2a import Intent, Offer, IntentBroadcaster
from open_a2a.intent import Location, TOPIC_INTENT_FOOD_OFFER_PREFIX

# 使用 Relay 的 WebSocket 地址（出站连接）
RELAY_WS_URL = os.getenv("RELAY_WS_URL", "ws://localhost:8765")


async def main() -> None:
    from open_a2a import RelayClientTransport
    transport = RelayClientTransport(relay_ws_url=RELAY_WS_URL)
    broadcaster = IntentBroadcaster(transport=transport)
    await broadcaster.connect()
    print(f"[Consumer via Relay] 已通过 Relay 连接: {RELAY_WS_URL}")

    intent = Intent(
        action="Food_Order",
        type="Noodle",
        location=Location(lat=31.23, lon=121.47),
        constraints=["No_Coriander", "<30min"],
        reply_to="",
        sender_id="consumer-relay-001",
    )
    intent.reply_to = f"{TOPIC_INTENT_FOOD_OFFER_PREFIX}.{intent.id}"

    print("[Consumer via Relay] 发布意图，等待报价 (10秒)...")
    try:
        offers = await broadcaster.publish_and_collect_offers(intent, timeout_seconds=10.0)
        print(f"[Consumer via Relay] 收到 {len(offers)} 个报价")
        for o in offers:
            print(f"  - {o.sender_id or o.sender_did}: {o.price} {o.unit}")
    finally:
        await broadcaster.disconnect()
    print("[Consumer via Relay] 完成")


if __name__ == "__main__":
    asyncio.run(main())
