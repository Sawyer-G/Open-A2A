#!/usr/bin/env python3
"""
Open-A2A Bridge - 连接 NATS 与 OpenClaw 的适配层

功能:
  - POST /api/publish_intent: OpenClaw 作为 Tool 调用，发布意图到 NATS
  - 订阅 NATS 意图主题，转发给 OpenClaw /hooks/agent
"""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import Any, Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# 支持从项目根目录运行
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from open_a2a import Intent, IntentBroadcaster, Location
from open_a2a.intent import TOPIC_INTENT_FOOD_OFFER_PREFIX

# --- 配置 ---
NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
OPENCLAW_GATEWAY_URL = os.getenv("OPENCLAW_GATEWAY_URL", "").rstrip("/")
OPENCLAW_HOOKS_TOKEN = os.getenv("OPENCLAW_HOOKS_TOKEN", "")
BRIDGE_ENABLE_FORWARD = os.getenv("BRIDGE_ENABLE_FORWARD", "1").lower() in ("1", "true", "yes")

# --- Pydantic 模型 ---


class PublishIntentRequest(BaseModel):
    """发布意图请求（OpenClaw Tool 调用）"""
    action: str = Field(default="Food_Order", description="意图动作")
    type: str = Field(default="Noodle", description="意图类型")
    constraints: list[str] = Field(default_factory=list, description="约束列表")
    lat: float = Field(default=31.23, description="纬度")
    lon: float = Field(default=121.47, description="经度")
    sender_id: str = Field(default="openclaw-consumer", description="发送者 ID")
    collect_offers: bool = Field(default=True, description="是否收集报价")
    timeout_seconds: float = Field(default=10.0, ge=1, le=60, description="收集报价超时秒数")


class PublishIntentResponse(BaseModel):
    """发布意图响应"""
    intent_id: str
    offers_count: int = 0
    offers: list[dict[str, Any]] = Field(default_factory=list)
    message: str = ""


# --- 全局 Broadcaster（在 lifespan 中初始化）---
broadcaster: Optional[IntentBroadcaster] = None


async def forward_intent_to_openclaw(intent: Intent) -> None:
    """将收到的意图转发给 OpenClaw /hooks/agent"""
    if not OPENCLAW_GATEWAY_URL or not OPENCLAW_HOOKS_TOKEN:
        return
    url = f"{OPENCLAW_GATEWAY_URL}/hooks/agent"
    constraints_str = "、".join(intent.constraints) if intent.constraints else "无"
    loc_str = f"({intent.location.lat}, {intent.location.lon})" if intent.location else ""
    message = (
        f"【Open-A2A 意图】收到消费者意图：{intent.type}，"
        f"约束：{constraints_str}，位置：{loc_str}。"
        f"请根据你的能力回复报价（JSON 格式：intent_id, price, unit, description）。"
    )
    payload = {
        "message": message,
        "sessionKey": f"open-a2a-intent-{intent.id}",
        "agentId": "hooks",
        "name": "OpenA2A",
        "wakeMode": "now",
        "deliver": True,
        "channel": "last",
    }
    headers = {"x-openclaw-token": OPENCLAW_HOOKS_TOKEN, "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
    except Exception as e:
        print(f"[Bridge] 转发意图到 OpenClaw 失败: {e}")


async def _run_nats_subscriber() -> None:
    """后台任务：订阅 NATS 意图，转发给 OpenClaw"""
    global broadcaster
    if not broadcaster or not BRIDGE_ENABLE_FORWARD or not OPENCLAW_GATEWAY_URL:
        return
    try:
        await broadcaster.subscribe_intents(forward_intent_to_openclaw)
        print("[Bridge] 已订阅 intent.food.order，转发到 OpenClaw")
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：连接 NATS，启动订阅任务"""
    global broadcaster
    broadcaster = IntentBroadcaster(NATS_URL)
    await broadcaster.connect()
    print(f"[Bridge] 已连接 NATS: {NATS_URL}")
    task = None
    if BRIDGE_ENABLE_FORWARD and OPENCLAW_GATEWAY_URL:
        task = asyncio.create_task(_run_nats_subscriber())
    try:
        yield
    finally:
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if broadcaster:
            await broadcaster.disconnect()
            print("[Bridge] 已断开 NATS")


app = FastAPI(
    title="Open-A2A Bridge",
    description="连接 NATS 与 OpenClaw 的适配层",
    version="0.2.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict[str, str]:
    """健康检查"""
    return {"status": "ok", "service": "open-a2a-bridge"}


@app.post("/api/publish_intent", response_model=PublishIntentResponse)
async def publish_intent(req: PublishIntentRequest) -> PublishIntentResponse:
    """
    发布意图到 NATS（OpenClaw Tool 调用此接口）
    可选：收集报价并返回
    """
    if not broadcaster:
        raise HTTPException(status_code=503, detail="NATS 未连接")
    location = Location(lat=req.lat, lon=req.lon)
    intent = Intent(
        action=req.action,
        type=req.type,
        location=location,
        constraints=req.constraints,
        reply_to="",
        sender_id=req.sender_id,
    )
    intent.reply_to = f"{TOPIC_INTENT_FOOD_OFFER_PREFIX}.{intent.id}"
    if req.collect_offers:
        offers = await broadcaster.publish_and_collect_offers(
            intent, timeout_seconds=req.timeout_seconds
        )
        return PublishIntentResponse(
            intent_id=intent.id,
            offers_count=len(offers),
            offers=[o.to_dict() for o in offers],
            message=f"已发布意图，收到 {len(offers)} 个报价",
        )
    await broadcaster.publish_intent(intent)
    return PublishIntentResponse(
        intent_id=intent.id,
        message="意图已发布到 NATS",
    )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("BRIDGE_PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
