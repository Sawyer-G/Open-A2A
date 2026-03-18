#!/usr/bin/env python3
"""
Consumer Agent - 消费者 Agent 示例

发送「想吃面」意图，收集商家报价，选择后确认订单。
支持 Phase 2：从 profile.json 读取偏好，可选 DID 签名。
"""

import asyncio
import os
from pathlib import Path

# 支持从项目根目录运行
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from open_a2a import Intent, Offer, OrderConfirm, IntentBroadcaster
from open_a2a.intent import Location, TOPIC_INTENT_FOOD_OFFER_PREFIX

# Phase 2: 可选偏好与身份（支持 Solid Pod）
def _load_preferences():
    # 优先从自托管 Solid Pod 读取（符合数据主权，需设置 SOLID_* 环境变量）
    if os.getenv("SOLID_POD_ENDPOINT"):
        try:
            from open_a2a import SolidPodPreferencesProvider
            return SolidPodPreferencesProvider()
        except (ImportError, ValueError) as e:
            print(f"[Consumer] Solid Pod 不可用: {e}，回退到本地 profile.json")
    # 回退到本地 profile.json
    profile_path = Path(__file__).parent / "profile.json"
    if profile_path.exists():
        from open_a2a import FilePreferencesProvider
        return FilePreferencesProvider(profile_path)
    return None

def _create_identity():
    if os.getenv("USE_IDENTITY", "").lower() in ("1", "true", "yes"):
        try:
            from open_a2a import AgentIdentity
            return AgentIdentity() if AgentIdentity else None
        except ImportError:
            pass
    return None


async def main() -> None:
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    consumer_id = os.getenv("CONSUMER_ID", "consumer-001")

    prefs = _load_preferences()
    identity = _create_identity()
    broadcaster = IntentBroadcaster(nats_url, identity=identity)
    await broadcaster.connect()

    # 从偏好或默认值构建意图参数
    if prefs:
        constraints = prefs.get_constraints()
        loc_data = prefs.get_location()
        location = Location(**loc_data) if loc_data else Location(lat=31.23, lon=121.47)
        if identity:
            print(f"[Consumer] 使用 DID 签名: {identity.did}")
    else:
        constraints = ["No_Coriander", "<30min"]
        location = Location(lat=31.23, lon=121.47)

    try:
        # 创建意图：想吃披萨，约束来自偏好或默认
        intent = Intent(
            action="Food_Order",
            type="Pizza",
            location=location,
            constraints=constraints,
            reply_to="",  # 下面设置
            sender_id=consumer_id,
        )
        intent.reply_to = f"{TOPIC_INTENT_FOOD_OFFER_PREFIX}.{intent.id}"

        print(f"[Consumer] 发布意图: {intent.type}, 约束: {intent.constraints}")
        print(f"[Consumer] 等待报价 (10秒)...")

        async def on_offer(offer: Offer) -> None:
            who = offer.sender_did or offer.sender_id
            print(f"  <- 收到报价: {who} {offer.price} {offer.unit}")

        offers = await broadcaster.publish_and_collect_offers(
            intent,
            timeout_seconds=10.0,
            on_offer=on_offer,
        )

        print(f"[Consumer] 共收到 {len(offers)} 个报价")
        for o in offers:
            who = o.sender_did or o.sender_id
            print(f"  - {who}: {o.price} {o.unit}, {o.description or '-'}")

        if not offers:
            print("[Consumer] 无报价，退出")
            return

        # 选择第一个报价（可扩展为选最低价等）
        chosen = offers[0]
        who = chosen.sender_did or chosen.sender_id
        print(f"[Consumer] 选择 {who} 的报价，确认订单...")

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
