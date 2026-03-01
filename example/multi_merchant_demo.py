#!/usr/bin/env python3
"""
多 Merchant 场景验证

启动 N 个 Merchant 进程（不同 MERCHANT_ID），Consumer 发布一次意图，
验证能收到 N 个报价（多商家同时响应同一意图）。

前置：NATS 已启动（如 docker run -p 4222:4222 nats:latest）。
用法：从项目根目录执行
  make run-multi-merchant-demo
  或 MULTI_MERCHANT_N=5 .venv/bin/python example/multi_merchant_demo.py
"""

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

# 项目根
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
N_MERCHANTS = int(os.getenv("MULTI_MERCHANT_N", "3"))
WAIT_SUBSCRIBE = float(os.getenv("MULTI_MERCHANT_WAIT", "2.5"))
COLLECT_TIMEOUT = 8.0


async def run_consumer_and_collect_offers() -> list:
    """在进程内连接 NATS，发布意图并收集报价。"""
    from open_a2a import Intent, Offer, IntentBroadcaster
    from open_a2a.intent import Location, TOPIC_INTENT_FOOD_OFFER_PREFIX

    broadcaster = IntentBroadcaster(NATS_URL)
    await broadcaster.connect()

    intent = Intent(
        action="Food_Order",
        type="Noodle",
        location=Location(lat=31.23, lon=121.47),
        constraints=["No_Coriander", "<30min"],
        reply_to="",
        sender_id="consumer-multi-demo",
    )
    intent.reply_to = f"{TOPIC_INTENT_FOOD_OFFER_PREFIX}.{intent.id}"

    offers = await broadcaster.publish_and_collect_offers(
        intent, timeout_seconds=COLLECT_TIMEOUT
    )
    await broadcaster.disconnect()
    return offers


def main() -> None:
    python = ROOT / ".venv" / "bin" / "python"
    if not python.exists():
        python = Path(sys.executable)
    merchant_script = ROOT / "example" / "merchant.py"
    if not merchant_script.exists():
        print(f"错误: 未找到 {merchant_script}")
        sys.exit(1)

    env = os.environ.copy()
    env["NATS_URL"] = NATS_URL
    procs = []
    for i in range(1, N_MERCHANTS + 1):
        mid = f"merchant-{i:03d}"
        env["MERCHANT_ID"] = mid
        p = subprocess.Popen(
            [str(python), str(merchant_script)],
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        procs.append((mid, p))
    print(f"[多 Merchant] 已启动 {N_MERCHANTS} 个 Merchant: {[m for m, _ in procs]}")

    try:
        print(f"[多 Merchant] 等待 {WAIT_SUBSCRIBE}s 使 Merchant 完成订阅...")
        time.sleep(WAIT_SUBSCRIBE)

        print("[多 Merchant] Consumer 发布意图并收集报价...")
        offers = asyncio.run(run_consumer_and_collect_offers())

        print(f"[多 Merchant] 共收到 {len(offers)} 个报价")
        for o in offers:
            who = o.sender_did or o.sender_id
            print(f"  - {who}: {o.price} {o.unit}")

        if len(offers) >= N_MERCHANTS:
            print(f"[多 Merchant] 验证通过: 收到 {len(offers)} 个报价 (期望至少 {N_MERCHANTS})")
        else:
            print(f"[多 Merchant] 警告: 期望至少 {N_MERCHANTS} 个报价，实际 {len(offers)}。请确认 NATS 已启动且无其他错误。")
    finally:
        for mid, p in procs:
            p.terminate()
            try:
                p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                p.kill()
        print("[多 Merchant] 已终止所有 Merchant 进程")


if __name__ == "__main__":
    main()
