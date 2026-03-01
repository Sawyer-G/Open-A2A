"""
Relay 传输适配器（出站优先）

Agent 无需公网 IP 或 webhook：通过 WebSocket 主动连接 Open-A2A Relay，
即可参与主题的发布与订阅。由框架提供可达性，用户无需申请域名或配置回调。

支持 wss://：可选传入 ssl.SSLContext，或设置 RELAY_WS_SSL_VERIFY=0 以信任自签名证书（仅开发/测试）。
"""

import asyncio
import base64
import json
import os
import ssl
import uuid
from typing import Any, Awaitable, Callable, Optional

from open_a2a.transport import MessageSubscription, TransportAdapter

try:
    import websockets
except ImportError:
    websockets = None  # type: ignore


class _RelaySubscription(MessageSubscription):
    def __init__(self, transport: "RelayClientTransport", subject: str, sub_id: str) -> None:
        self._transport = transport
        self._subject = subject
        self._sub_id = sub_id

    async def unsubscribe(self) -> None:
        await self._transport._unsubscribe(self._subject, self._sub_id)


def _default_ssl_for_wss() -> Optional[ssl.SSLContext]:
    """wss 且未传入 ssl 时：RELAY_WS_SSL_VERIFY=0 则使用不校验的上下文（仅开发/自签名）。"""
    if os.getenv("RELAY_WS_SSL_VERIFY", "").strip().lower() in ("0", "false", "no"):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    return None


class RelayClientTransport(TransportAdapter):
    """
    通过 Relay 的传输适配器（出站连接）

    连接 Open-A2A Relay 的 WebSocket 地址（如 ws:// 或 wss://relay.example.com/），
    即可 publish/subscribe，无需本机被外网访问。

    wss 自签名证书：可传入 ssl= 自定义 SSLContext，或设置环境变量
    RELAY_WS_SSL_VERIFY=0（仅开发/测试，不校验服务端证书）。
    """

    def __init__(
        self,
        relay_ws_url: str = "ws://localhost:8765",
        ssl: Optional[ssl.SSLContext] = None,
    ) -> None:
        if websockets is None:
            raise ImportError("websockets is required. Install with: pip install open-a2a[relay]")
        self._relay_ws_url = relay_ws_url
        self._ssl: Optional[ssl.SSLContext] = ssl
        self._ws = None
        self._recv_task: Optional[asyncio.Task] = None
        self._subs: dict[str, dict[str, Callable[[bytes], Awaitable[None]]]] = {}
        # subject -> {sub_id -> cb}
        self._lock = asyncio.Lock()

    def _resolve_ssl(self) -> Any:
        """解析连接时使用的 ssl 参数（仅 wss 需要）。"""
        if not self._relay_ws_url.strip().lower().startswith("wss://"):
            return None
        if self._ssl is not None:
            return self._ssl
        custom = _default_ssl_for_wss()
        if custom is not None:
            return custom
        return ssl.create_default_context()

    async def connect(self) -> None:
        ssl_ctx = self._resolve_ssl()
        self._ws = await websockets.connect(
            self._relay_ws_url,
            ping_interval=20,
            ping_timeout=20,
            ssl=ssl_ctx,
        )
        self._recv_task = asyncio.create_task(self._receive_loop())
        return None

    async def _receive_loop(self) -> None:
        try:
            async for raw in self._ws:
                try:
                    msg = json.loads(raw)
                    if msg.get("type") != "message":
                        continue
                    subject = msg.get("subject")
                    body_b64 = msg.get("body")
                    if subject is None or body_b64 is None:
                        continue
                    data = base64.b64decode(body_b64)
                    async with self._lock:
                        cbs = self._subs.get(subject, {})
                    for cb in cbs.values():
                        try:
                            await cb(data)
                        except Exception:
                            pass
                except (json.JSONDecodeError, KeyError, TypeError):
                    pass
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    async def disconnect(self) -> None:
        if self._recv_task:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass
            self._recv_task = None
        if self._ws:
            await self._ws.close()
            self._ws = None
        self._subs.clear()

    async def publish(self, subject: str, data: bytes) -> None:
        if not self._ws:
            raise RuntimeError("Not connected. Call connect() first.")
        body_b64 = base64.b64encode(data).decode("ascii")
        payload = json.dumps({"type": "publish", "subject": subject, "body": body_b64})
        await self._ws.send(payload)

    async def subscribe(
        self,
        subject: str,
        cb: Callable[[bytes], Awaitable[None]],
    ) -> MessageSubscription:
        if not self._ws:
            raise RuntimeError("Not connected. Call connect() first.")
        sub_id = uuid.uuid4().hex
        async with self._lock:
            if subject not in self._subs:
                self._subs[subject] = {}
            self._subs[subject][sub_id] = cb
        await self._ws.send(json.dumps({"type": "subscribe", "subject": subject}))
        return _RelaySubscription(self, subject, sub_id)

    async def _unsubscribe(self, subject: str, sub_id: str) -> None:
        async with self._lock:
            if subject in self._subs:
                self._subs[subject].pop(sub_id, None)
                if not self._subs[subject]:
                    del self._subs[subject]
        if self._ws:
            await self._ws.send(json.dumps({"type": "unsubscribe", "subject": subject}))
