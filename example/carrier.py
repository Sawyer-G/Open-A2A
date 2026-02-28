#!/usr/bin/env python3
"""
Carrier Agent - 配送员 Agent 示例

订阅配送请求，自动接单。
"""

import asyncio
import os

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from open_a2a import LogisticsRequest, LogisticsAccept, IntentBroadcaster


async def main() -> None:
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    carrier_id = os.getenv("CARRIER_ID", "carrier-001")

    broadcaster = IntentBroadcaster(nats_url)
    await broadcaster.connect()

    async def handle_logistics_request(req: LogisticsRequest) -> None:
        print(f"[Carrier] 收到配送请求: order={req.order_id}, 运费={req.fee} {req.unit}")
        # 简单逻辑：直接接单
        accept = LogisticsAccept(
            request_id=req.id,
            eta_minutes=20,
            sender_id=carrier_id,
        )
        await broadcaster.publish_logistics_accept(accept, req.reply_to)
        print(f"[Carrier] 已接单，预计 {accept.eta_minutes} 分钟送达")
        # 模拟送达（实际可发布 intent.logistics.delivered）
        await asyncio.sleep(1)
        print(f"[Carrier] 订单 {req.order_id} 模拟送达")

    await broadcaster.subscribe_logistics_requests(handle_logistics_request)
    print(f"[Carrier] 已订阅 intent.logistics.request，等待配送请求... (Ctrl+C 退出)")

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await broadcaster.disconnect()
        print("[Carrier] 已退出")


if __name__ == "__main__":
    asyncio.run(main())
