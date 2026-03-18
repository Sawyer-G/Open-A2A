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
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Optional
from dataclasses import dataclass
from fastapi import Request

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
from open_a2a.identity import AgentIdentity, build_meta_proof

# Optional Redis backend for directory registry (multi-instance HA)
try:
    import redis.asyncio as redis  # type: ignore
except Exception:
    redis = None  # type: ignore

# --- 配置 ---
NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
OPENCLAW_GATEWAY_URL = os.getenv("OPENCLAW_GATEWAY_URL", "").rstrip("/")
OPENCLAW_HOOKS_TOKEN = os.getenv("OPENCLAW_HOOKS_TOKEN", "")
BRIDGE_ENABLE_FORWARD = os.getenv("BRIDGE_ENABLE_FORWARD", "1").lower() in ("1", "true", "yes")
OA2A_STRICT_SECURITY = os.getenv("OA2A_STRICT_SECURITY", "").strip().lower() in ("1", "true", "yes")

# --- Discovery（持续被发现）配置 ---
# NATS Discovery 的 “register” 本质是在 NATS 上订阅 open_a2a.discovery.query.{capability}，
# 当其他人查询时回复 meta，因此只要进程在线即可持续被发现（无需中心化注册表）。
BRIDGE_ENABLE_DISCOVERY = os.getenv("BRIDGE_ENABLE_DISCOVERY", "1").lower() in ("1", "true", "yes")
BRIDGE_AGENT_ID = os.getenv("BRIDGE_AGENT_ID", "openclaw-agent")
BRIDGE_CAPABILITIES = os.getenv("BRIDGE_CAPABILITIES", "intent.food.order")
BRIDGE_META_JSON = os.getenv("BRIDGE_META_JSON", "")

# --- Identity/Trust (meta proof) ---
BRIDGE_ENABLE_META_PROOF = os.getenv("BRIDGE_ENABLE_META_PROOF", "0").lower() in ("1", "true", "yes")
BRIDGE_PUBLIC_URL = os.getenv("BRIDGE_PUBLIC_URL", "").rstrip("/")
BRIDGE_DID_SEED_B64 = os.getenv("BRIDGE_DID_SEED_B64", "").strip()

# --- Discovery Ops: TTL / Auth / Rate limit ---
BRIDGE_DISCOVERY_DEFAULT_TTL_SECONDS = float(os.getenv("BRIDGE_DISCOVERY_DEFAULT_TTL_SECONDS", "60"))
BRIDGE_DISCOVERY_CLEANUP_INTERVAL_SECONDS = float(
    os.getenv("BRIDGE_DISCOVERY_CLEANUP_INTERVAL_SECONDS", "5")
)
BRIDGE_DISCOVERY_PERSIST_PATH = os.getenv("BRIDGE_DISCOVERY_PERSIST_PATH", "").strip()
BRIDGE_DISCOVERY_REDIS_URL = os.getenv("BRIDGE_DISCOVERY_REDIS_URL", "").strip()
BRIDGE_DISCOVERY_REGISTER_TOKEN = os.getenv("BRIDGE_DISCOVERY_REGISTER_TOKEN", "").strip()
BRIDGE_DISCOVERY_DISCOVER_TOKEN = os.getenv("BRIDGE_DISCOVERY_DISCOVER_TOKEN", "").strip()
BRIDGE_DISCOVERY_RL_PER_MINUTE = int(os.getenv("BRIDGE_DISCOVERY_RL_PER_MINUTE", "60"))


def _security_boot_check() -> None:
    """
    Fail fast for obviously insecure operator deployments when OA2A_STRICT_SECURITY=1.

    Defaults to warnings only to keep backwards compatibility.
    """
    issues: list[str] = []

    if BRIDGE_ENABLE_DISCOVERY:
        if not BRIDGE_DISCOVERY_REGISTER_TOKEN or not BRIDGE_DISCOVERY_DISCOVER_TOKEN:
            issues.append("Bridge discovery 未配置 register/discover token（公网部署建议开启鉴权）")

    if BRIDGE_ENABLE_FORWARD and (not OPENCLAW_GATEWAY_URL or not OPENCLAW_HOOKS_TOKEN):
        issues.append("BRIDGE_ENABLE_FORWARD=1 但 OPENCLAW_GATEWAY_URL/OPENCLAW_HOOKS_TOKEN 未配置")

    if "change-me" in NATS_URL:
        issues.append("NATS_URL 疑似仍包含 change-me 占位密码，请先修改")

    if not issues:
        return

    msg = "[Bridge][security] " + "；".join(issues)
    if OA2A_STRICT_SECURITY:
        raise SystemExit(msg + "。已启用 OA2A_STRICT_SECURITY=1，拒绝在不安全配置下启动。")
    print(msg + "。你可以设置 OA2A_STRICT_SECURITY=1 来强制拒绝启动。")

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
    ttl_seconds: Optional[float] = Field(
        default=None,
        ge=5,
        le=24 * 3600,
        description="注册 TTL（秒）。到期未续租将被移除。未提供则使用默认值。",
    )


class RegisterCapabilitiesResponse(BaseModel):
    ok: bool = True
    registered_count: int = 0
    message: str = ""
    expires_at: str = ""


class DiscoverResponse(BaseModel):
    capability: str
    results: list[dict[str, Any]] = Field(default_factory=list)
    count: int = 0


class DiscoveryStatsResponse(BaseModel):
    status: str
    providers_total: int = 0
    providers_verified: int = 0
    providers_unverified: int = 0
    capabilities_total: int = 0
    by_capability: dict[str, int] = Field(default_factory=dict)
    last_cleanup_at: str = ""
    last_error: str = ""


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
_bridge_identity: Optional[AgentIdentity] = None


@dataclass
class _Registration:
    agent_id: str
    capabilities: list[str]
    meta: dict[str, Any]
    expires_at_ts: float
    updated_at: str


_registrations: dict[str, _Registration] = {}
_capability_subscriptions: set[str] = set()
_last_cleanup_at: str = ""
_last_discovery_ops_error: str = ""
_rl_buckets: dict[str, tuple[int, float]] = {}  # key -> (count, window_start_ts)
_redis: Optional[Any] = None


def _redis_enabled() -> bool:
    return bool(BRIDGE_DISCOVERY_REDIS_URL)


def _redis_require_available() -> None:
    if redis is None:
        raise RuntimeError(
            "Redis backend requested but redis is not installed. Install with: pip install open-a2a[bridge]"
        )


def _rk_agents() -> str:
    return "open_a2a:bridge:discovery:agents"


def _rk_caps() -> str:
    return "open_a2a:bridge:discovery:caps"


def _rk_reg(agent_id: str) -> str:
    return f"open_a2a:bridge:discovery:reg:{agent_id}"


def _rk_cap(cap: str) -> str:
    return f"open_a2a:bridge:discovery:cap:{cap}"


async def _redis_get_reg(agent_id: str) -> Optional[dict[str, Any]]:
    if not _redis:
        return None
    raw = await _redis.get(_rk_reg(agent_id))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


async def _redis_upsert_registration(reg: _Registration) -> None:
    """
    Store one provider registration and index by capability.

    Data model (MVP):
    - reg JSON at open_a2a:bridge:discovery:reg:{agent_id} with key expiry at expires_at_ts
    - global ZSET agents: member=agent_id, score=expires_at_ts
    - per-capability ZSET cap:{cap}: member=agent_id, score=expires_at_ts
    - SET caps: all seen capabilities
    """
    if not _redis:
        return
    prev = await _redis_get_reg(reg.agent_id)
    prev_caps = prev.get("capabilities") if isinstance(prev, dict) else None
    prev_caps = prev_caps if isinstance(prev_caps, list) else []

    # remove from old capability indexes if changed
    for c in prev_caps:
        c = str(c).strip()
        if c and c not in reg.capabilities:
            await _redis.zrem(_rk_cap(c), reg.agent_id)

    # write reg and index
    reg_doc = {
        "agent_id": reg.agent_id,
        "capabilities": list(reg.capabilities),
        "meta": reg.meta,
        "expires_at_ts": float(reg.expires_at_ts),
        "updated_at": reg.updated_at,
    }
    exp_ts = int(reg.expires_at_ts)
    await _redis.set(_rk_reg(reg.agent_id), json.dumps(reg_doc, ensure_ascii=False), exat=exp_ts)
    await _redis.zadd(_rk_agents(), {reg.agent_id: float(reg.expires_at_ts)})
    if reg.capabilities:
        await _redis.sadd(_rk_caps(), *list(reg.capabilities))
    for c in reg.capabilities:
        await _redis.zadd(_rk_cap(c), {reg.agent_id: float(reg.expires_at_ts)})


async def _redis_list_active_metas_for_capability(cap: str) -> list[dict[str, Any]]:
    if not _redis:
        return []
    now_ts = datetime.now(timezone.utc).timestamp()
    ids = await _redis.zrangebyscore(_rk_cap(cap), min=now_ts, max="+inf")
    if not ids:
        return []
    # decode
    agent_ids = [x.decode("utf-8") if isinstance(x, (bytes, bytearray)) else str(x) for x in ids]
    keys = [_rk_reg(aid) for aid in agent_ids]
    raws = await _redis.mget(keys)
    out: list[dict[str, Any]] = []
    missing_ids: list[str] = []
    for aid, raw in zip(agent_ids, raws):
        if not raw:
            missing_ids.append(aid)
            continue
        try:
            doc = json.loads(raw)
            meta = doc.get("meta") if isinstance(doc, dict) else None
            if isinstance(meta, dict):
                out.append(meta)
        except Exception:
            continue
    # Best-effort cleanup of index entries whose reg key is missing
    if missing_ids:
        try:
            await _redis.zrem(_rk_cap(cap), *missing_ids)
        except Exception:
            pass
    return out


async def _redis_stats() -> tuple[int, int, dict[str, int]]:
    """
    Returns: (providers_total, providers_verified, by_capability)
    """
    if not _redis:
        return 0, 0, {}
    now_ts = datetime.now(timezone.utc).timestamp()
    providers_total = int(await _redis.zcount(_rk_agents(), min=now_ts, max="+inf"))

    # compute by_capability from caps set; keep only caps with active providers
    by_cap: dict[str, int] = {}
    caps = await _redis.smembers(_rk_caps())
    for c in caps or []:
        cap = c.decode("utf-8") if isinstance(c, (bytes, bytearray)) else str(c)
        if not cap:
            continue
        cnt = int(await _redis.zcount(_rk_cap(cap), min=now_ts, max="+inf"))
        if cnt > 0:
            by_cap[cap] = cnt

    # verified count: best-effort scan of active providers
    verified = 0
    ids = await _redis.zrangebyscore(_rk_agents(), min=now_ts, max="+inf")
    if ids:
        agent_ids = [x.decode("utf-8") if isinstance(x, (bytes, bytearray)) else str(x) for x in ids]
        raws = await _redis.mget([_rk_reg(aid) for aid in agent_ids])
        for raw in raws or []:
            if not raw:
                continue
            try:
                doc = json.loads(raw)
                meta = doc.get("meta") if isinstance(doc, dict) else None
                if isinstance(meta, dict) and _is_verified(meta):
                    verified += 1
            except Exception:
                continue
    return providers_total, verified, by_cap


async def _redis_cleanup_expired() -> None:
    if not _redis:
        return
    now_ts = datetime.now(timezone.utc).timestamp()
    expired = await _redis.zrangebyscore(_rk_agents(), min="-inf", max=now_ts)
    if not expired:
        return
    agent_ids = [x.decode("utf-8") if isinstance(x, (bytes, bytearray)) else str(x) for x in expired]
    for aid in agent_ids:
        doc = await _redis_get_reg(aid)
        caps = doc.get("capabilities") if isinstance(doc, dict) else []
        caps = caps if isinstance(caps, list) else []
        for c in caps:
            cap = str(c).strip()
            if cap:
                await _redis.zrem(_rk_cap(cap), aid)
        await _redis.delete(_rk_reg(aid))
        await _redis.zrem(_rk_agents(), aid)



def _persist_enabled() -> bool:
    # file persistence is only for memory backend
    return (not _redis_enabled()) and bool(BRIDGE_DISCOVERY_PERSIST_PATH)


def _persist_safe_reg(reg: "_Registration") -> dict[str, Any]:
    return {
        "agent_id": reg.agent_id,
        "capabilities": list(reg.capabilities),
        "meta": reg.meta,
        "expires_at_ts": float(reg.expires_at_ts),
        "updated_at": reg.updated_at,
    }


def _save_registrations_to_disk() -> None:
    """
    Best-effort persistence for single-instance operator deployments.
    - Disabled by default (BRIDGE_DISCOVERY_PERSIST_PATH empty).
    - Atomic write: write temp then replace.
    """
    if not _persist_enabled():
        return
    try:
        path = Path(BRIDGE_DISCOVERY_PERSIST_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        now_ts = datetime.now(timezone.utc).timestamp()
        data = {
            "version": 1,
            "saved_at": _now_iso(),
            "registrations": {
                aid: _persist_safe_reg(reg)
                for aid, reg in _registrations.items()
                if reg.expires_at_ts > now_ts
            },
        }
        payload = json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=str(path.parent)) as f:
            f.write(payload)
            tmp = f.name
        os.replace(tmp, str(path))
    except Exception as e:
        # do not crash the service for persistence failures
        print(f"[Bridge] discovery 持久化失败（将继续以内存模式运行）: {e}")


def _load_registrations_from_disk() -> None:
    if not _persist_enabled():
        return
    path = Path(BRIDGE_DISCOVERY_PERSIST_PATH)
    if not path.exists():
        return
    try:
        raw = path.read_text(encoding="utf-8")
        doc = json.loads(raw)
        regs = doc.get("registrations") or {}
        if not isinstance(regs, dict):
            return
        now_ts = datetime.now(timezone.utc).timestamp()
        loaded = 0
        for aid, item in regs.items():
            if not isinstance(aid, str) or not isinstance(item, dict):
                continue
            exp = item.get("expires_at_ts")
            try:
                exp_ts = float(exp)
            except (TypeError, ValueError):
                continue
            if exp_ts <= now_ts:
                continue
            caps = item.get("capabilities") or []
            meta = item.get("meta") or {}
            updated_at = item.get("updated_at") or ""
            if not isinstance(caps, list) or not isinstance(meta, dict):
                continue
            _registrations[aid] = _Registration(
                agent_id=aid,
                capabilities=[str(c).strip() for c in caps if str(c).strip()],
                meta=meta,
                expires_at_ts=exp_ts,
                updated_at=str(updated_at),
            )
            loaded += 1
        if loaded:
            print(f"[Bridge] discovery 从磁盘恢复注册表: {loaded} 个 provider")
    except Exception as e:
        print(f"[Bridge] discovery 注册表恢复失败（忽略，继续空目录启动）: {e}")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_bearer(request: Request, token: str, *, name: str) -> None:
    if not token:
        return
    auth = (request.headers.get("authorization") or "").strip()
    expected = f"Bearer {token}"
    if auth != expected:
        raise HTTPException(status_code=401, detail=f"Unauthorized ({name})")


def _rate_limit(request: Request, *, bucket: str, limit_per_minute: int) -> None:
    if limit_per_minute <= 0:
        return
    client = request.client.host if request.client else "unknown"
    key = f"{bucket}:{client}"
    now = datetime.now(timezone.utc).timestamp()
    window = 60.0
    count, start = _rl_buckets.get(key, (0, now))
    if now - start >= window:
        count, start = 0, now
    count += 1
    _rl_buckets[key] = (count, start)
    if count > limit_per_minute:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


def _maybe_attach_identity_proof(meta: dict[str, Any]) -> None:
    """
    Ensure meta has did/proof fields following RFC-004.

    - If identity is unavailable/disabled, meta remains unverified (did empty, proof None).
    - If enabled and identity exists, attach did and proof.
    """
    global _bridge_identity
    if not BRIDGE_ENABLE_META_PROOF:
        return
    if _bridge_identity is None:
        # Best-effort: initialize identity. If didlite not installed, keep unverified.
        try:
            if BRIDGE_DID_SEED_B64:
                import base64

                seed = base64.b64decode(BRIDGE_DID_SEED_B64)
                _bridge_identity = AgentIdentity(seed=seed)
            else:
                _bridge_identity = AgentIdentity()
        except Exception as e:
            print(f"[Bridge] Identity 初始化失败，将以 unverified meta 继续: {e}")
            _bridge_identity = None
            return

    if _bridge_identity:
        meta["did"] = _bridge_identity.did
        meta["proof"] = build_meta_proof(_bridge_identity, meta, created_at=_now_iso())


def _is_verified(meta: dict[str, Any]) -> bool:
    # Minimal heuristic: did + proof present
    return bool(meta.get("did")) and bool(meta.get("proof"))


def _get_active_metas_for_capability(cap: str) -> list[dict[str, Any]]:
    # legacy sync wrapper (memory backend only)
    now_ts = datetime.now(timezone.utc).timestamp()
    return [
        reg.meta
        for reg in _registrations.values()
        if reg.expires_at_ts > now_ts and cap in reg.capabilities
    ]


async def _get_active_metas_for_capability_async(cap: str) -> list[dict[str, Any]]:
    if _redis_enabled():
        return await _redis_list_active_metas_for_capability(cap)
    return _get_active_metas_for_capability(cap)


async def _get_active_caps_async() -> set[str]:
    if _redis_enabled() and _redis:
        now_ts = datetime.now(timezone.utc).timestamp()
        caps_raw = await _redis.smembers(_rk_caps())
        out: set[str] = set()
        for c in caps_raw or []:
            cap = c.decode("utf-8") if isinstance(c, (bytes, bytearray)) else str(c)
            if not cap:
                continue
            try:
                cnt = int(await _redis.zcount(_rk_cap(cap), min=now_ts, max="+inf"))
            except Exception:
                continue
            if cnt > 0:
                out.add(cap)
        return out
    now_ts = datetime.now(timezone.utc).timestamp()
    out: set[str] = set()
    for reg in _registrations.values():
        if reg.expires_at_ts > now_ts:
            out.update(reg.capabilities)
    return out


async def _sync_discovery_subscriptions() -> None:
    """
    Ensure NATS discovery responders exist for all active capabilities.
    """
    global _capability_subscriptions, _last_discovery_ops_error
    if not discovery or _discovery_status != "connected":
        return

    active_caps = await _get_active_caps_async()

    # Add missing responders
    for cap in sorted(active_caps - _capability_subscriptions):
        try:
            await discovery.register_responder(
                cap, lambda _p=None, c=cap: _get_active_metas_for_capability_async(c)
            )
            _capability_subscriptions.add(cap)
        except Exception as e:
            _last_discovery_ops_error = str(e)

    # Remove responders that are no longer needed
    for cap in sorted(_capability_subscriptions - active_caps):
        try:
            await discovery.unregister(cap)
        except Exception:
            pass
        _capability_subscriptions.discard(cap)


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
        "did": "",
        "endpoints": [],
        "capabilities": [],
        "proof": None,
    }
    if OPENCLAW_GATEWAY_URL:
        meta["openclaw_gateway_url"] = OPENCLAW_GATEWAY_URL
    if BRIDGE_PUBLIC_URL:
        meta["endpoints"].append({"type": "http", "url": BRIDGE_PUBLIC_URL})
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

    # Back-compat globals for /health
    meta["capabilities"] = list(capabilities)
    _maybe_attach_identity_proof(meta)
    _registered_meta = meta

    ttl = BRIDGE_DISCOVERY_DEFAULT_TTL_SECONDS
    expires_at_ts = datetime.now(timezone.utc).timestamp() + ttl
    reg = _Registration(
        agent_id=agent_id,
        capabilities=list(capabilities),
        meta=meta,
        expires_at_ts=expires_at_ts,
        updated_at=_now_iso(),
    )
    _registrations[agent_id] = reg
    await _sync_discovery_subscriptions()
    _save_registrations_to_disk()

    # Maintain a legacy union view for /health (not used for responder anymore)
    union_caps: set[str] = set()
    now_ts = datetime.now(timezone.utc).timestamp()
    for r in _registrations.values():
        if r.expires_at_ts > now_ts:
            union_caps.update(r.capabilities)
    _registered_capabilities = sorted(union_caps)
    return len(reg.capabilities)


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
    global broadcaster
    global discovery
    global _nats_status
    global _nats_error
    global _discovery_status
    global _discovery_error
    _security_boot_check()
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

    # Optional Redis registry backend (for HA / multi-instance directory)
    global _redis
    if _redis_enabled():
        _redis_require_available()
        _redis = redis.from_url(BRIDGE_DISCOVERY_REDIS_URL, decode_responses=False)
        try:
            await _redis.ping()
            print("[Bridge] discovery registry backend: redis (connected)")
        except Exception as e:
            _redis = None
            raise RuntimeError(f"Redis registry connect failed: {e}")

    # Discovery：用于能力注册与查询（持续被发现）
    discovery_keepalive_task = None
    cleanup_task = None
    if BRIDGE_ENABLE_DISCOVERY and _nats_status == "connected":
        discovery = NatsDiscoveryProvider(NATS_URL)
        try:
            await discovery.connect()
            _discovery_status = "connected"
            _discovery_error = ""

            # Optional: restore directory registry before syncing subscriptions.
            if not _redis_enabled():
                _load_registrations_from_disk()

            caps = _parse_capabilities(BRIDGE_CAPABILITIES)
            meta = _default_meta(BRIDGE_AGENT_ID)
            if BRIDGE_META_JSON.strip():
                try:
                    meta.update(json.loads(BRIDGE_META_JSON))
                except json.JSONDecodeError as e:
                    print(f"[Bridge] BRIDGE_META_JSON 解析失败，将忽略该字段: {e}")

            if caps:
                # Auto-register as a provider with a long TTL (renewed by cleanup loop).
                ttl = max(BRIDGE_DISCOVERY_DEFAULT_TTL_SECONDS, 60.0)
                meta["capabilities"] = list(caps)
                _maybe_attach_identity_proof(meta)
                reg = _Registration(
                    agent_id=BRIDGE_AGENT_ID,
                    capabilities=list(caps),
                    meta=meta,
                    expires_at_ts=datetime.now(timezone.utc).timestamp() + ttl,
                    updated_at=_now_iso(),
                )
                if _redis_enabled():
                    await _redis_upsert_registration(reg)
                else:
                    _registrations[BRIDGE_AGENT_ID] = reg
                    _save_registrations_to_disk()
                await _sync_discovery_subscriptions()
                print(f"[Bridge] Discovery 已注册能力 {len(caps)} 个: {', '.join(caps)}")

            # 保持一个 task 引用，便于 graceful shutdown（未来可扩展心跳/定时刷新）
            discovery_keepalive_task = asyncio.create_task(asyncio.sleep(10**9))

            async def _cleanup_loop() -> None:
                global _last_cleanup_at, _last_discovery_ops_error
                while True:
                    await asyncio.sleep(BRIDGE_DISCOVERY_CLEANUP_INTERVAL_SECONDS)
                    if _redis_enabled():
                        try:
                            await _redis_cleanup_expired()
                            await _sync_discovery_subscriptions()
                        except Exception as e:
                            _last_discovery_ops_error = str(e)
                    else:
                        now_ts = datetime.now(timezone.utc).timestamp()
                        removed = []
                        for aid, reg in list(_registrations.items()):
                            if reg.expires_at_ts <= now_ts:
                                removed.append(aid)
                                _registrations.pop(aid, None)
                        if removed:
                            await _sync_discovery_subscriptions()
                            _save_registrations_to_disk()
                    _last_cleanup_at = _now_iso()

            cleanup_task = asyncio.create_task(_cleanup_loop())
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
        if cleanup_task:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass
        if discovery:
            try:
                for cap in list(_capability_subscriptions):
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
        if _redis:
            try:
                await _redis.close()
            except Exception:
                pass
            _redis = None


app = FastAPI(
    title="Open-A2A Bridge",
    description="连接 NATS 与 OpenClaw 的适配层",
    version="0.2.0",
    lifespan=lifespan,
)


@app.get("/ops/metrics")
async def ops_metrics() -> dict[str, Any]:
    """
    Minimal operator-friendly metrics snapshot (JSON).
    This is intentionally simple (no extra deps).
    """
    backend = "redis" if _redis_enabled() else ("file" if _persist_enabled() else "memory")
    providers_total = 0
    verified = 0
    by_cap: dict[str, int] = {}
    if _redis_enabled():
        try:
            providers_total, verified, by_cap = await _redis_stats()
        except Exception:
            pass
    else:
        now_ts = datetime.now(timezone.utc).timestamp()
        active = [r for r in _registrations.values() if r.expires_at_ts > now_ts]
        providers_total = len(active)
        for r in active:
            if _is_verified(r.meta):
                verified += 1
            for c in r.capabilities:
                by_cap[c] = by_cap.get(c, 0) + 1
    return {
        "service": "open-a2a-bridge",
        "status": "ok",
        "nats": {"status": _nats_status, "url": NATS_URL, "error": _nats_error},
        "discovery": {
            "status": _discovery_status,
            "backend": backend,
            "redis_enabled": _redis_enabled(),
            "providers_total": providers_total,
            "providers_verified": verified,
            "providers_unverified": max(0, providers_total - verified),
            "capabilities_total": len(by_cap),
            "by_capability": by_cap,
            "last_cleanup_at": _last_cleanup_at,
            "last_ops_error": _last_discovery_ops_error or _discovery_error,
        },
    }


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
            "providers_total": len(_registrations),
            "last_cleanup_at": _last_cleanup_at,
            "last_ops_error": _last_discovery_ops_error,
        },
        "openclaw": openclaw_info,
    }


@app.post("/api/register_capabilities", response_model=RegisterCapabilitiesResponse)
async def register_capabilities(req: RegisterCapabilitiesRequest, request: Request) -> RegisterCapabilitiesResponse:
    """
    注册/更新本节点（或 OpenClaw Agent）支持的能力，用于被其他节点持续 discover。

    NATS Discovery 没有中心化注册表；register 的实现是订阅查询主题并在被查询时返回 meta。
    因此要“持续被发现”，注册方需要保持进程在线（例如 Bridge 常驻运行）。
    """
    global _discovery_status, _discovery_error
    _require_bearer(request, BRIDGE_DISCOVERY_REGISTER_TOKEN, name="register")
    _rate_limit(request, bucket="register", limit_per_minute=BRIDGE_DISCOVERY_RL_PER_MINUTE)
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
        # Apply TTL
        ttl = float(req.ttl_seconds) if req.ttl_seconds is not None else BRIDGE_DISCOVERY_DEFAULT_TTL_SECONDS
        ttl = max(5.0, min(ttl, 24 * 3600.0))
        meta["capabilities"] = list(caps)
        _maybe_attach_identity_proof(meta)
        expires_at_ts = datetime.now(timezone.utc).timestamp() + ttl
        expires_at = datetime.fromtimestamp(expires_at_ts, tz=timezone.utc).isoformat()

        reg = _Registration(
            agent_id=req.agent_id,
            capabilities=list(caps),
            meta=meta,
            expires_at_ts=expires_at_ts,
            updated_at=_now_iso(),
        )
        if _redis_enabled():
            await _redis_upsert_registration(reg)
        else:
            _registrations[req.agent_id] = reg
            _save_registrations_to_disk()
        await _sync_discovery_subscriptions()

        # legacy view
        union_caps = await _get_active_caps_async()
        global _registered_capabilities, _registered_meta
        _registered_meta = meta
        _registered_capabilities = sorted(union_caps)

        return RegisterCapabilitiesResponse(
            ok=True,
            registered_count=len(caps),
            message="capabilities registered",
            expires_at=expires_at,
        )
    except Exception as e:
        _discovery_status = "error"
        _discovery_error = str(e)
        raise HTTPException(status_code=500, detail=f"register failed: {e}")


@app.get("/api/discover", response_model=DiscoverResponse)
async def discover_capability(capability: str, timeout_seconds: float = 3.0, request: Request = None) -> DiscoverResponse:
    """查询支持某能力的 Agent 列表（NATS Discovery request-reply）。"""
    # `request` is injected by FastAPI; keep it optional for backward compatibility with older clients/tests.
    if request:
        _require_bearer(request, BRIDGE_DISCOVERY_DISCOVER_TOKEN, name="discover")
        _rate_limit(request, bucket="discover", limit_per_minute=BRIDGE_DISCOVERY_RL_PER_MINUTE)
    if not discovery or _discovery_status != "connected":
        raise HTTPException(status_code=503, detail=f"Discovery not connected: {_discovery_error or _discovery_status}")
    cap = (capability or "").strip()
    if not cap:
        raise HTTPException(status_code=400, detail="capability is required")
    timeout = max(0.5, min(float(timeout_seconds), 15.0))
    results = await discovery.discover(cap, timeout_seconds=timeout)
    return DiscoverResponse(capability=cap, results=results, count=len(results))


@app.get("/api/discovery_stats", response_model=DiscoveryStatsResponse)
async def discovery_stats(request: Request) -> DiscoveryStatsResponse:
    _require_bearer(request, BRIDGE_DISCOVERY_DISCOVER_TOKEN, name="stats")
    _rate_limit(request, bucket="stats", limit_per_minute=BRIDGE_DISCOVERY_RL_PER_MINUTE)
    if _redis_enabled():
        total, verified, by_cap = await _redis_stats()
        active_total = total
    else:
        now_ts = datetime.now(timezone.utc).timestamp()
        active = [r for r in _registrations.values() if r.expires_at_ts > now_ts]
        by_cap = {}
        verified = 0
        for r in active:
            if _is_verified(r.meta):
                verified += 1
            for c in r.capabilities:
                by_cap[c] = by_cap.get(c, 0) + 1
        active_total = len(active)
    return DiscoveryStatsResponse(
        status=_discovery_status,
        providers_total=active_total,
        providers_verified=verified,
        providers_unverified=max(0, active_total - verified),
        capabilities_total=len(by_cap),
        by_capability=by_cap,
        last_cleanup_at=_last_cleanup_at,
        last_error=_last_discovery_ops_error or _discovery_error,
    )

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
