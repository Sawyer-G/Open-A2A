#!/usr/bin/env python3
"""
Discovery 示例：能力注册与发现

演示 Agent 如何注册自己支持的能力（如 intent.food.order），
以及如何发现网络中支持某能力的其他 Agent。用于跨服务器/跨节点发现。
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from open_a2a import NatsDiscoveryProvider
from open_a2a.intent import TOPIC_INTENT_FOOD_ORDER


async def main() -> None:
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")

    # 发现提供者（可与 IntentBroadcaster 共用同一 NATS）
    discovery = NatsDiscoveryProvider(nats_url)
    await discovery.connect()

    # 1. 注册本 Agent 支持 intent.food.order
    capability = TOPIC_INTENT_FOOD_ORDER
    meta = {
        "agent_id": "merchant-001",
        "capability": capability,
        "description": "商家：可响应订餐意图",
    }
    await discovery.register(capability, meta)
    print(f"[Discovery] 已注册能力: {capability}")

    # 2. 模拟另一侧：发现支持该能力的 Agent（通常由 Consumer 或网关调用）
    async def do_discover():
        await asyncio.sleep(0.5)  # 确保注册已生效
        agents = await discovery.discover(capability, timeout_seconds=2.0)
        print(f"[Discovery] 发现 {len(agents)} 个 Agent 支持 {capability}:")
        for a in agents:
            print(f"  - {a.get('agent_id', a)}")

    await do_discover()

    await discovery.unregister(capability)
    print("[Discovery] 已取消注册")
    await discovery.disconnect()
    print("[Discovery] 完成")


if __name__ == "__main__":
    asyncio.run(main())
