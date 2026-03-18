#!/usr/bin/env python3
"""
Open-A2A Relay - WebSocket <-> NATS 桥接

为无公网 IP / 无域名的 Agent 提供出站连接：Agent 仅需主动连接本 Relay，
即可参与 NATS 主题的发布与订阅，无需自建 webhook 或端口映射。

协议（JSON over WebSocket）：
  Client -> Relay: subscribe / unsubscribe / publish
  Relay -> Client: message（NATS 消息转发）
"""

import asyncio
import base64
import json
import os
import ssl
import sys
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from nats.aio.client import Client as NATSClient
except ImportError:
    NATSClient = None  # type: ignore

try:
    import websockets
except ImportError:
    websockets = None  # type: ignore

NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
RELAY_WS_HOST = os.getenv("RELAY_WS_HOST", "0.0.0.0")
RELAY_WS_PORT = int(os.getenv("RELAY_WS_PORT", "8765"))
RELAY_WS_TLS = os.getenv("RELAY_WS_TLS", "").strip().lower() in ("1", "true", "yes")
RELAY_WS_SSL_CERT = os.getenv("RELAY_WS_SSL_CERT", "").strip()
RELAY_WS_SSL_KEY = os.getenv("RELAY_WS_SSL_KEY", "").strip()

# --- Ops/Security knobs (public entrypoint hardening) ---
RELAY_AUTH_TOKEN = os.getenv("RELAY_AUTH_TOKEN", "").strip()

# Subject allow/block lists (comma-separated). Supports NATS-style ">" suffix wildcard.
RELAY_SUBJECT_ALLOWLIST = os.getenv("RELAY_SUBJECT_ALLOWLIST", "intent.>,open_a2a.>,_INBOX.>").strip()
RELAY_SUBJECT_BLOCKLIST = os.getenv("RELAY_SUBJECT_BLOCKLIST", "").strip()

# Per-connection limits
RELAY_MAX_SUBSCRIPTIONS_PER_CONN = int(os.getenv("RELAY_MAX_SUBSCRIPTIONS_PER_CONN", "128"))
RELAY_MAX_MESSAGE_BYTES = int(os.getenv("RELAY_MAX_MESSAGE_BYTES", "65536"))
RELAY_MAX_JSON_BYTES = int(os.getenv("RELAY_MAX_JSON_BYTES", "262144"))
RELAY_RL_PUB_PER_SEC = int(os.getenv("RELAY_RL_PUB_PER_SEC", "30"))


def _make_ssl_context() -> Optional[ssl.SSLContext]:
    """启用 TLS 时构建 SSL 上下文，用于 wss://"""
    if not RELAY_WS_TLS or not RELAY_WS_SSL_CERT or not RELAY_WS_SSL_KEY:
        return None
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(RELAY_WS_SSL_CERT, RELAY_WS_SSL_KEY)
    return ctx


def _split_patterns(value: str) -> list[str]:
    return [p.strip() for p in (value or "").split(",") if p.strip()]


def _match_subject(pattern: str, subject: str) -> bool:
    if pattern.endswith(">"):
        prefix = pattern[:-1]
        return subject.startswith(prefix)
    return subject == pattern


def _is_subject_allowed(subject: str) -> bool:
    allow = _split_patterns(RELAY_SUBJECT_ALLOWLIST)
    block = _split_patterns(RELAY_SUBJECT_BLOCKLIST)
    if block and any(_match_subject(p, subject) for p in block):
        return False
    if not allow:
        return True
    return any(_match_subject(p, subject) for p in allow)


def _extract_auth_token(ws: Any) -> str:
    try:
        auth = (ws.request_headers.get("Authorization") or "").strip()
        if auth.lower().startswith("bearer "):
            return auth.split(" ", 1)[1].strip()
    except Exception:
        pass
    try:
        path = getattr(ws, "path", "") or ""
        q = urlparse(path).query
        token = (parse_qs(q).get("token") or [""])[0]
        return str(token).strip()
    except Exception:
        return ""


async def _send_error(ws: Any, message: str) -> None:
    try:
        await ws.send(json.dumps({"type": "error", "message": message}, ensure_ascii=False))
    except Exception:
        pass

# 每个 subject 一个 NATS 订阅，收到后广播给所有订阅了该 subject 的 WebSocket
_nats: Optional[Any] = None
_client_subjects: dict[Any, set[str]] = {}  # ws -> set(subject)
_nats_subs: dict[str, Any] = {}  # subject -> nats subscription
_lock = asyncio.Lock()


async def _ensure_nats_sub(subject: str) -> None:
    """确保 NATS 已订阅 subject，收到消息时转发给所有订阅了该 subject 的 client"""
    global _nats, _nats_subs, _client_subjects
    async with _lock:
        if subject in _nats_subs:
            return

        async def handler(msg):
            body_b64 = base64.b64encode(msg.data).decode("ascii")
            payload = json.dumps({"type": "message", "subject": msg.subject, "body": body_b64})
            to_remove = []
            for ws, subs in list(_client_subjects.items()):
                if subject in subs:
                    try:
                        await ws.send(payload)
                    except Exception:
                        to_remove.append(ws)
            for ws in to_remove:
                _client_subjects.pop(ws, None)

        sub = await _nats.subscribe(subject, cb=handler)
        _nats_subs[subject] = sub


async def _remove_nats_sub_if_unused(subject: str) -> None:
    """若没有 client 再订阅该 subject，则取消 NATS 订阅"""
    global _nats_subs, _client_subjects
    async with _lock:
        for subs in _client_subjects.values():
            if subject in subs:
                return
        sub = _nats_subs.pop(subject, None)
        if sub:
            await sub.unsubscribe()


async def _handle_ws(ws: Any) -> None:
    global _nats, _client_subjects
    _client_subjects[ws] = set()
    # Auth (optional)
    if RELAY_AUTH_TOKEN:
        token = _extract_auth_token(ws)
        if token != RELAY_AUTH_TOKEN:
            try:
                await _send_error(ws, "unauthorized")
                await ws.close(code=4401, reason="unauthorized")
            except Exception:
                pass
            _client_subjects.pop(ws, None)
            return

    # Basic per-connection publish rate limit (per-second window)
    pub_count = 0
    pub_window_start = asyncio.get_event_loop().time()
    try:
        async for raw in ws:
            try:
                # Frame size guard
                if isinstance(raw, (bytes, bytearray)):
                    if len(raw) > RELAY_MAX_JSON_BYTES:
                        await _send_error(ws, "payload too large")
                        continue
                    raw = raw.decode("utf-8", errors="ignore")
                if len(raw) > RELAY_MAX_JSON_BYTES:
                    await _send_error(ws, "payload too large")
                    continue

                msg = json.loads(raw)
                typ = msg.get("type")
                if typ == "subscribe":
                    subject = msg.get("subject")
                    if subject:
                        if not _is_subject_allowed(subject):
                            await _send_error(ws, f"subject not allowed: {subject}")
                            continue
                        if len(_client_subjects[ws]) >= RELAY_MAX_SUBSCRIPTIONS_PER_CONN:
                            await _send_error(ws, "too many subscriptions")
                            continue
                        _client_subjects[ws].add(subject)
                        await _ensure_nats_sub(subject)
                elif typ == "unsubscribe":
                    subject = msg.get("subject")
                    if subject:
                        _client_subjects[ws].discard(subject)
                        await _remove_nats_sub_if_unused(subject)
                elif typ == "publish":
                    subject = msg.get("subject")
                    body_b64 = msg.get("body")
                    if subject is not None and body_b64 is not None:
                        if not _is_subject_allowed(subject):
                            await _send_error(ws, f"subject not allowed: {subject}")
                            continue
                        # Per-second publish rate limit
                        now = asyncio.get_event_loop().time()
                        if now - pub_window_start >= 1.0:
                            pub_window_start = now
                            pub_count = 0
                        pub_count += 1
                        if RELAY_RL_PUB_PER_SEC > 0 and pub_count > RELAY_RL_PUB_PER_SEC:
                            await _send_error(ws, "publish rate limited")
                            continue
                        data = base64.b64decode(body_b64)
                        if len(data) > RELAY_MAX_MESSAGE_BYTES:
                            await _send_error(ws, "message too large")
                            continue
                        await _nats.publish(subject, data)
            except (json.JSONDecodeError, KeyError, TypeError):
                pass  # 忽略格式错误
    except websockets.exceptions.ConnectionClosed:
        pass  # 客户端正常断开
    finally:
        subs = _client_subjects.pop(ws, None)
        if subs:
            for subject in subs:
                await _remove_nats_sub_if_unused(subject)


async def _run_nats() -> None:
    global _nats
    if NATSClient is None:
        raise RuntimeError("nats-py is required for relay. pip install nats-py")
    _nats = NATSClient()
    await _nats.connect(NATS_URL)
    print(f"[Relay] 已连接 NATS: {NATS_URL}")


async def main() -> None:
    if websockets is None:
        raise RuntimeError("websockets is required for relay. pip install open-a2a[relay]")
    await _run_nats()
    ssl_ctx = _make_ssl_context()
    if ssl_ctx:
        print(f"[Relay] 已启用 TLS (wss://)，证书: {RELAY_WS_SSL_CERT}")
    async with websockets.serve(
        _handle_ws,
        RELAY_WS_HOST,
        RELAY_WS_PORT,
        ping_interval=20,
        ping_timeout=20,
        ssl=ssl_ctx,
    ):
        scheme = "wss" if ssl_ctx else "ws"
        print(
            f"[Relay] WebSocket 监听 {scheme}://{RELAY_WS_HOST}:{RELAY_WS_PORT}，"
            "Agent 可出站连接此处参与网络"
        )
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
