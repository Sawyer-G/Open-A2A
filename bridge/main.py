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
from open_a2a.discovery_nats import NatsDiscoveryProvider

# --- 配置 ---
NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
OPENCLAW_GATEWAY_URL = os.getenv("OPENCLAW_GATEWAY_URL", "").rstrip("/")
OPENCLAW_HOOKS_TOKEN = os.getenv("OPENCLAW_HOOKS_TOKEN", "")
BRIDGE_ENABLE_FORWARD = os.getenv("BRIDGE_ENABLE_FORWARD", "1").lower() in ("1", "true", "yes")

# --- Discovery（持续被发现）配置 ---
# NATS Discovery 的 “register” 本质是在 NATS 上订阅 open_a2a.discovery.query.{capability}，
# 当其他人查询时回复 meta，因此只要进程在线即可持续被发现（无需中心化注册表）。
BRIDGE_ENABLE_DISCOVERY = os.getenv("BRIDGE_ENABLE_DISCOVERY", "1").lower() in ("1", "true", "yes")
BRIDGE_AGENT_ID = os.getenv("BRIDGE_AGENT_ID", "openclaw-agent")
BRIDGE_CAPABILITIES = os.getenv("BRIDGE_CAPABILITIES", "intent.food.order")
BRIDGE_META_JSON = os.getenv("BRIDGE_META_JSON", "")

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


class RegisterCapabilitiesRequest(BaseModel):
    """注册能力（用于持续被发现）。可由 OpenClaw Tool/Skill 调用。"""

    agent_id: str = Field(default="openclaw-agent", description="Agent ID")
    capabilities: list[str] = Field(
        default_factory=lambda: ["intent.food.order"],
        description="能力列表（与意图主题一致，例如 intent.food.order）",
    )
    meta: dict[str, Any] = Field(default_factory=dict, description="能力元数据（endpoint/did/region 等）")


class RegisterCapabilitiesResponse(BaseModel):
    ok: bool = True
    registered_count: int = 0
    message: str = ""


class DiscoverResponse(BaseModel):
    capability: str
    results: list[dict[str, Any]] = Field(default_factory=list)
    count: int = 0


# --- 全局 Broadcaster 与状态（在 lifespan 中初始化）---
broadcaster: Optional[IntentBroadcaster] = None
_nats_status: str = "unknown"
_nats_error: str = ""

# --- 全局 Discovery Provider 与状态 ---
discovery: Optional[NatsDiscoveryProvider] = None
_discovery_status: str = "unknown"
_discovery_error: str = ""
_registered_capabilities: list[str] = []
_registered_meta: dict[str, Any] = {}


def _parse_capabilities(value: str) -> list[str]:
    caps = [c.strip() for c in (value or "").split(",") if c.strip()]
    seen: set[str] = set()
    out: list[str] = []
    for c in caps:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _default_meta(agent_id: str) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "agent_id": agent_id,
        "runtime": "openclaw",
        "bridge": {"kind": "open-a2a-bridge", "health": "/health"},
    }
    if OPENCLAW_GATEWAY_URL:
        meta["openclaw_gateway_url"] = OPENCLAW_GATEWAY_URL
    return meta


async def _apply_registration(agent_id: str, capabilities: list[str], meta: dict[str, Any]) -> int:
    """
    使注册状态与给定输入一致：
      1) 取消旧注册
      2) 用新 meta 重新注册全部 capabilities
    """
    global discovery, _registered_capabilities, _registered_meta
    if not discovery:
        raise RuntimeError("discovery provider not initialized")

    for cap in list(_registered_capabilities):
        try:
            await discovery.unregister(cap)
        except Exception:
            pass
    _registered_capabilities = []
    _registered_meta = meta

    for cap in capabilities:
        await discovery.register(cap, meta)
        _registered_capabilities.append(cap)

    return len(_registered_capabilities)


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
    except httpx.HTTPStatusError as e:
        resp = e.response
        body_preview = resp.text[:200] if resp.text else ""
        print(
            f"[Bridge] 转发意图到 OpenClaw 失败（HTTP {resp.status_code}）: "
            f"url={url}, body_preview={body_preview}"
        )
    except httpx.RequestError as e:
        print(
            f"[Bridge] 转发意图到 OpenClaw 失败（请求错误，可能是网络/域名问题）: {e}"
        )
    except Exception as e:
        print(f"[Bridge] 转发意图到 OpenClaw 失败（未知错误）: {e}")


async def _run_nats_subscriber() -> None:
    """后台任务：订阅 NATS 意图，转发给 OpenClaw"""
    global broadcaster
    if not broadcaster:
        print("[Bridge] NATS Broadcaster 未初始化，跳过转发订阅。")
        return
    if not BRIDGE_ENABLE_FORWARD:
        print("[Bridge] BRIDGE_ENABLE_FORWARD=0，已禁用向 OpenClaw 转发意图。")
        return
    if not OPENCLAW_GATEWAY_URL:
        print("[Bridge] OPENCLAW_GATEWAY_URL 未配置，无法向 OpenClaw 转发意图。")
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
    global (
        broadcaster,
        discovery,
        _nats_status,
        _nats_error,
        _discovery_status,
        _discovery_error,
    )
    broadcaster = IntentBroadcaster(NATS_URL)
    try:
        await broadcaster.connect()
        _nats_status = "connected"
        _nats_error = ""
        print(f"[Bridge] 已连接 NATS: {NATS_URL}")
    except Exception as e:
        _nats_status = "error"
        _nats_error = str(e)
        broadcaster = None
        print(f"[Bridge] 连接 NATS 失败: {e}")

    # Discovery：用于能力注册与查询（持续被发现）
    discovery_keepalive_task = None
    if BRIDGE_ENABLE_DISCOVERY and _nats_status == "connected":
        discovery = NatsDiscoveryProvider(NATS_URL)
        try:
            await discovery.connect()
            _discovery_status = "connected"
            _discovery_error = ""

            caps = _parse_capabilities(BRIDGE_CAPABILITIES)
            meta = _default_meta(BRIDGE_AGENT_ID)
            if BRIDGE_META_JSON.strip():
                try:
                    meta.update(json.loads(BRIDGE_META_JSON))
                except json.JSONDecodeError as e:
                    print(f"[Bridge] BRIDGE_META_JSON 解析失败，将忽略该字段: {e}")

            if caps:
                n = await _apply_registration(BRIDGE_AGENT_ID, caps, meta)
                print(f"[Bridge] Discovery 已注册能力 {n} 个: {', '.join(caps)}")

            # 保持一个 task 引用，便于 graceful shutdown（未来可扩展心跳/定时刷新）
            discovery_keepalive_task = asyncio.create_task(asyncio.sleep(10**9))
        except Exception as e:
            _discovery_status = "error"
            _discovery_error = str(e)
            discovery = None
            print(f"[Bridge] Discovery 连接/注册失败: {e}")
    else:
        _discovery_status = "disabled"
        _discovery_error = ""
    task = None
    if BRIDGE_ENABLE_FORWARD and OPENCLAW_GATEWAY_URL:
        task = asyncio.create_task(_run_nats_subscriber())
    try:
        yield
    finally:
        if discovery_keepalive_task:
            discovery_keepalive_task.cancel()
            try:
                await discovery_keepalive_task
            except asyncio.CancelledError:
                pass
        if discovery:
            try:
                for cap in list(_registered_capabilities):
                    await discovery.unregister(cap)
            except Exception:
                pass
            await discovery.disconnect()
            print("[Bridge] 已断开 Discovery")
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
async def health() -> dict[str, Any]:
    """
    健康检查：
      - bridge: 自身状态
      - nats: 与 NATS 的连接状态
      - openclaw: 对 OPENCLAW_GATEWAY_URL 的连通性（若已配置）
    """
    # NATS 状态来自 lifespan 中的全局标记
    nats_info = {
        "status": _nats_status,
        "url": NATS_URL,
        "error": _nats_error,
    }

    # OpenClaw 状态：若未配置 URL，则视为 "disabled"
    openclaw_status = "disabled"
    openclaw_error = ""
    if OPENCLAW_GATEWAY_URL:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{OPENCLAW_GATEWAY_URL}/")
                resp.raise_for_status()
            openclaw_status = "ok"
        except httpx.HTTPStatusError as e:
            openclaw_status = "error"
            openclaw_error = f"HTTP {e.response.status_code}"
        except httpx.RequestError as e:
            openclaw_status = "error"
            openclaw_error = f"request error: {e}"
        except Exception as e:
            openclaw_status = "error"
            openclaw_error = f"unexpected error: {e}"

    openclaw_info = {
        "status": openclaw_status,
        "url": OPENCLAW_GATEWAY_URL,
        "error": openclaw_error,
    }

    return {
        "bridge": {
            "status": "ok",
            "version": app.version,
        },
        "nats": nats_info,
        "discovery": {
            "status": _discovery_status,
            "error": _discovery_error,
            "agent_id": BRIDGE_AGENT_ID,
            "registered_capabilities": list(_registered_capabilities),
            "registered_count": len(_registered_capabilities),
        },
        "openclaw": openclaw_info,
    }


@app.post("/api/register_capabilities", response_model=RegisterCapabilitiesResponse)
async def register_capabilities(req: RegisterCapabilitiesRequest) -> RegisterCapabilitiesResponse:
    """
    注册/更新本节点（或 OpenClaw Agent）支持的能力，用于被其他节点持续 discover。

    NATS Discovery 没有中心化注册表；register 的实现是订阅查询主题并在被查询时返回 meta。
    因此要“持续被发现”，注册方需要保持进程在线（例如 Bridge 常驻运行）。
    """
    global _discovery_status, _discovery_error
    if not BRIDGE_ENABLE_DISCOVERY:
        raise HTTPException(status_code=403, detail="Discovery disabled (BRIDGE_ENABLE_DISCOVERY=0)")
    if not discovery or _discovery_status != "connected":
        raise HTTPException(
            status_code=503,
            detail=f"Discovery not connected: {_discovery_error or _discovery_status}",
        )

    caps: list[str] = []
    for c in req.capabilities:
        c = (c or "").strip()
        if c:
            caps.append(c)
    if not caps:
        raise HTTPException(status_code=400, detail="capabilities is empty")

    meta = _default_meta(req.agent_id)
    meta.update(req.meta or {})
    try:
        n = await _apply_registration(req.agent_id, caps, meta)
        return RegisterCapabilitiesResponse(ok=True, registered_count=n, message="capabilities registered")
    except Exception as e:
        _discovery_status = "error"
        _discovery_error = str(e)
        raise HTTPException(status_code=500, detail=f"register failed: {e}")


@app.get("/api/discover", response_model=DiscoverResponse)
async def discover_capability(capability: str, timeout_seconds: float = 3.0) -> DiscoverResponse:
    """查询支持某能力的 Agent 列表（NATS Discovery request-reply）。"""
    if not discovery or _discovery_status != "connected":
        raise HTTPException(status_code=503, detail=f"Discovery not connected: {_discovery_error or _discovery_status}")
    cap = (capability or "").strip()
    if not cap:
        raise HTTPException(status_code=400, detail="capability is required")
    timeout = max(0.5, min(float(timeout_seconds), 15.0))
    results = await discovery.discover(cap, timeout_seconds=timeout)
    return DiscoverResponse(capability=cap, results=results, count=len(results))

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
