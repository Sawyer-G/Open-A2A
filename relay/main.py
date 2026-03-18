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
from datetime import datetime, timezone
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

from open_a2a.opslog import log_event

NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
RELAY_WS_HOST = os.getenv("RELAY_WS_HOST", "0.0.0.0")
RELAY_WS_PORT = int(os.getenv("RELAY_WS_PORT", "8765"))
RELAY_WS_TLS = os.getenv("RELAY_WS_TLS", "").strip().lower() in ("1", "true", "yes")
RELAY_WS_SSL_CERT = os.getenv("RELAY_WS_SSL_CERT", "").strip()
RELAY_WS_SSL_KEY = os.getenv("RELAY_WS_SSL_KEY", "").strip()
OA2A_STRICT_SECURITY = os.getenv("OA2A_STRICT_SECURITY", "").strip().lower() in ("1", "true", "yes")

# Minimal ops endpoint (HTTP JSON). Keep private by default.
RELAY_HTTP_ENABLE = os.getenv("RELAY_HTTP_ENABLE", "1").strip().lower() in ("1", "true", "yes")
RELAY_HTTP_HOST = os.getenv("RELAY_HTTP_HOST", "127.0.0.1").strip() or "127.0.0.1"
RELAY_HTTP_PORT = int(os.getenv("RELAY_HTTP_PORT", "8766"))

# --- Ops/Security knobs (public entrypoint hardening) ---
RELAY_AUTH_TOKEN = os.getenv("RELAY_AUTH_TOKEN", "").strip()

# Subject allow/block lists (comma-separated). Supports NATS-style ">" suffix wildcard.
RELAY_SUBJECT_ALLOWLIST = os.getenv(
    "RELAY_SUBJECT_ALLOWLIST", "intent.>,open_a2a.>,_INBOX.open_a2a.>"
).strip()
RELAY_SUBJECT_BLOCKLIST = os.getenv("RELAY_SUBJECT_BLOCKLIST", "").strip()

# Per-connection limits
RELAY_MAX_SUBSCRIPTIONS_PER_CONN = int(os.getenv("RELAY_MAX_SUBSCRIPTIONS_PER_CONN", "128"))
RELAY_MAX_MESSAGE_BYTES = int(os.getenv("RELAY_MAX_MESSAGE_BYTES", "65536"))
RELAY_MAX_JSON_BYTES = int(os.getenv("RELAY_MAX_JSON_BYTES", "262144"))
RELAY_RL_PUB_PER_SEC = int(os.getenv("RELAY_RL_PUB_PER_SEC", "30"))

def _security_boot_check() -> None:
    """
    Fail fast for obviously insecure public deployments when OA2A_STRICT_SECURITY=1.

    Defaults to warnings only to keep backwards compatibility.
    """
    issues: list[str] = []

    host = (RELAY_WS_HOST or "").strip()
    is_public_bind = host in ("0.0.0.0", "::", "")
    if is_public_bind and not RELAY_AUTH_TOKEN:
        issues.append("RELAY_AUTH_TOKEN 未设置（Relay 绑定公网地址时建议启用鉴权）")

    allow = RELAY_SUBJECT_ALLOWLIST.strip()
    if "_INBOX.>" in allow:
        issues.append("RELAY_SUBJECT_ALLOWLIST 包含 _INBOX.>（过宽，建议使用 _INBOX.open_a2a.>）")

    if "change-me" in NATS_URL:
        issues.append("NATS_URL 疑似仍包含 change-me 占位密码，请先修改")

    if not issues:
        return

    msg = "[Relay][security] " + "；".join(issues)
    if OA2A_STRICT_SECURITY:
        raise SystemExit(msg + "。已启用 OA2A_STRICT_SECURITY=1，拒绝在不安全配置下启动。")
    print(msg + "。你可以设置 OA2A_STRICT_SECURITY=1 来强制拒绝启动。")
    log_event(
        "open-a2a-relay",
        "warn",
        "security_warning",
        issues=issues,
        strict=bool(OA2A_STRICT_SECURITY),
    )


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


def _ops_snapshot() -> dict[str, Any]:
    return {
        "service": "open-a2a-relay",
        "status": "ok",
        "ts": datetime.now(timezone.utc).isoformat(),
        "nats_url": NATS_URL,
        "ws": {"host": RELAY_WS_HOST, "port": RELAY_WS_PORT, "tls": bool(RELAY_WS_TLS)},
        "limits": {
            "max_subscriptions_per_conn": RELAY_MAX_SUBSCRIPTIONS_PER_CONN,
            "max_message_bytes": RELAY_MAX_MESSAGE_BYTES,
            "max_json_bytes": RELAY_MAX_JSON_BYTES,
            "rl_pub_per_sec": RELAY_RL_PUB_PER_SEC,
        },
        "auth_enabled": bool(RELAY_AUTH_TOKEN),
        "subjects": {
            "allowlist": RELAY_SUBJECT_ALLOWLIST,
            "blocklist": RELAY_SUBJECT_BLOCKLIST,
        },
        "runtime": {
            "clients": len(_client_subjects),
            "nats_subject_subscriptions": len(_nats_subs),
        },
    }


def _prom_escape_label_value(v: str) -> str:
    return (
        v.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace('"', '\\"')
        .replace("\r", "")
    )


def _render_prometheus_metrics() -> bytes:
    """
    Prometheus text exposition format.

    Contract:
      - /healthz returns JSON
      - /metrics returns Prometheus metrics
    """
    snap = _ops_snapshot()
    runtime = snap.get("runtime") or {}
    ws = snap.get("ws") or {}
    limits = snap.get("limits") or {}
    subjects = snap.get("subjects") or {}

    allow = _prom_escape_label_value(str(subjects.get("allowlist") or ""))
    block = _prom_escape_label_value(str(subjects.get("blocklist") or ""))

    lines: list[str] = []
    lines.append("# HELP oa2a_relay_up Relay process is up (1).")
    lines.append("# TYPE oa2a_relay_up gauge")
    lines.append("oa2a_relay_up 1")

    lines.append("# HELP oa2a_relay_clients Connected websocket clients.")
    lines.append("# TYPE oa2a_relay_clients gauge")
    lines.append(f"oa2a_relay_clients {int(runtime.get('clients') or 0)}")

    lines.append(
        "# HELP oa2a_relay_nats_subject_subscriptions "
        "Active NATS subscriptions by subject."
    )
    lines.append("# TYPE oa2a_relay_nats_subject_subscriptions gauge")
    lines.append(
        "oa2a_relay_nats_subject_subscriptions "
        f"{int(runtime.get('nats_subject_subscriptions') or 0)}"
    )

    lines.append("# HELP oa2a_relay_auth_enabled Whether relay auth token is enabled (1/0).")
    lines.append("# TYPE oa2a_relay_auth_enabled gauge")
    lines.append(f"oa2a_relay_auth_enabled {1 if snap.get('auth_enabled') else 0}")

    lines.append("# HELP oa2a_relay_ws_tls Whether websocket TLS is enabled (1/0).")
    lines.append("# TYPE oa2a_relay_ws_tls gauge")
    lines.append(f"oa2a_relay_ws_tls {1 if ws.get('tls') else 0}")

    lines.append(
        "# HELP oa2a_relay_limits_max_subscriptions_per_conn "
        "Max subscriptions allowed per connection."
    )
    lines.append("# TYPE oa2a_relay_limits_max_subscriptions_per_conn gauge")
    lines.append(
        "oa2a_relay_limits_max_subscriptions_per_conn "
        f"{int(limits.get('max_subscriptions_per_conn') or 0)}"
    )

    lines.append(
        "# HELP oa2a_relay_limits_max_message_bytes "
        "Max NATS message bytes allowed."
    )
    lines.append("# TYPE oa2a_relay_limits_max_message_bytes gauge")
    lines.append(f"oa2a_relay_limits_max_message_bytes {int(limits.get('max_message_bytes') or 0)}")

    lines.append("# HELP oa2a_relay_limits_max_json_bytes Max JSON frame bytes allowed.")
    lines.append("# TYPE oa2a_relay_limits_max_json_bytes gauge")
    lines.append(f"oa2a_relay_limits_max_json_bytes {int(limits.get('max_json_bytes') or 0)}")

    lines.append(
        "# HELP oa2a_relay_limits_rl_pub_per_sec "
        "Publish rate limit per second (best-effort)."
    )
    lines.append("# TYPE oa2a_relay_limits_rl_pub_per_sec gauge")
    lines.append(f"oa2a_relay_limits_rl_pub_per_sec {int(limits.get('rl_pub_per_sec') or 0)}")

    lines.append("# HELP oa2a_relay_subjects_allowlist Configured subject allowlist.")
    lines.append("# TYPE oa2a_relay_subjects_allowlist gauge")
    lines.append(f'oa2a_relay_subjects_allowlist{{value="{allow}"}} 1')

    if block:
        lines.append("# HELP oa2a_relay_subjects_blocklist Configured subject blocklist.")
        lines.append("# TYPE oa2a_relay_subjects_blocklist gauge")
        lines.append(f'oa2a_relay_subjects_blocklist{{value="{block}"}} 1')

    return ("\n".join(lines) + "\n").encode("utf-8")


async def _handle_ops(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        line = await reader.readline()
        path = "/"
        try:
            parts = line.decode("utf-8", errors="ignore").split(" ")
            if len(parts) >= 2:
                path = parts[1]
        except Exception:
            path = "/"

        if path.startswith("/metrics"):
            body = _render_prometheus_metrics()
            headers = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/plain; version=0.0.4; charset=utf-8\r\n"
                b"Cache-Control: no-store\r\n"
                + f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
            )
            writer.write(headers + body)
            await writer.drain()
            return

        if path.startswith("/healthz") or path.startswith("/"):
            body = json.dumps(_ops_snapshot(), ensure_ascii=False).encode("utf-8")
            headers = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: application/json; charset=utf-8\r\n"
                b"Cache-Control: no-store\r\n"
                + f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
            )
            writer.write(headers + body)
            await writer.drain()
    except Exception:
        pass
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


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
    log_event("open-a2a-relay", "info", "nats_connected", nats_url=NATS_URL)


async def main() -> None:
    if websockets is None:
        raise RuntimeError("websockets is required for relay. pip install open-a2a[relay]")
    _security_boot_check()
    await _run_nats()
    ops_server = None
    if RELAY_HTTP_ENABLE:
        try:
            ops_server = await asyncio.start_server(_handle_ops, RELAY_HTTP_HOST, RELAY_HTTP_PORT)
            print(f"[Relay] ops endpoint: http://{RELAY_HTTP_HOST}:{RELAY_HTTP_PORT}/healthz")
            log_event(
                "open-a2a-relay",
                "info",
                "ops_endpoint_listening",
                host=RELAY_HTTP_HOST,
                port=RELAY_HTTP_PORT,
            )
        except Exception as e:
            print(f"[Relay] ops endpoint 启动失败（将继续运行 WS）：{e}")
            log_event("open-a2a-relay", "warn", "ops_endpoint_failed", error=str(e))
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
        try:
            await asyncio.Future()
        finally:
            if ops_server:
                ops_server.close()
                await ops_server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
