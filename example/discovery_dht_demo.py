#!/usr/bin/env python3
"""
DHT 发现示例：跨网络发现（不依赖同一 NATS）

需要至少两个 DHT 节点才能可靠存储；本示例在单进程内启动两个节点互相 bootstrap，
演示能力注册与发现。实际部署时各 Agent 连接公共或自建 bootstrap 即可跨 NATS 集群发现。
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 需要 pip install open-a2a[dht]
try:
    from open_a2a import DhtDiscoveryProvider
except ImportError as e:
    print("请先安装 DHT 依赖: pip install open-a2a[dht]")
    sys.exit(1)

from open_a2a.intent import TOPIC_INTENT_FOOD_ORDER


async def main() -> None:
    port_a = int(os.getenv("DHT_PORT", "8468"))
    port_b = port_a + 1
    host = os.getenv("DHT_BOOTSTRAP_HOST", "127.0.0.1")

    # 先启动节点 B，再启动节点 A（A bootstrap 到 B），形成小 DHT 网
    discovery_b = DhtDiscoveryProvider(dht_port=port_b, bootstrap_nodes=[])
    await discovery_b.connect()
    discovery_a = DhtDiscoveryProvider(dht_port=port_a, bootstrap_nodes=[(host, port_b)])
    await discovery_a.connect()
    await asyncio.sleep(0.3)

    await discovery_a.register(
        TOPIC_INTENT_FOOD_ORDER,
        {"agent_id": "merchant-dht-001", "capability": TOPIC_INTENT_FOOD_ORDER},
    )
    print(f"[DHT A] 已注册能力: {TOPIC_INTENT_FOOD_ORDER}")

    await asyncio.sleep(0.5)
    agents = await discovery_b.discover(TOPIC_INTENT_FOOD_ORDER, timeout_seconds=3.0)
    print(f"[DHT B] 发现 {len(agents)} 个 Agent:")
    for a in agents:
        print(f"  - {a.get('agent_id', a)}")

    await discovery_a.unregister(TOPIC_INTENT_FOOD_ORDER)
    await discovery_a.disconnect()
    await discovery_b.disconnect()
    print("[DHT] 完成")


if __name__ == "__main__":
    asyncio.run(main())
