"""
Relay 传输适配器（出站优先）

Agent 无需公网 IP 或 webhook：通过 WebSocket 主动连接 Open-A2A Relay，
即可参与主题的发布与订阅。由框架提供可达性，用户无需申请域名或配置回调。
"""

import asyncio
import base64
import json
import uuid
from typing import Awaitable, Callable, Optional

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


class RelayClientTransport(TransportAdapter):
    """
    通过 Relay 的传输适配器（出站连接）

    连接 Open-A2A Relay 的 WebSocket 地址（如 ws://relay.example.com/），
    即可 publish/subscribe，无需本机被外网访问。
    """

    def __init__(self, relay_ws_url: str = "ws://localhost:8765") -> None:
        if websockets is None:
            raise ImportError("websockets is required. Install with: pip install open-a2a[relay]")
        self._relay_ws_url = relay_ws_url
        self._ws = None
        self._recv_task: Optional[asyncio.Task] = None
        self._subs: dict[str, dict[str, Callable[[bytes], Awaitable[None]]]] = {}  # subject -> {sub_id -> cb}
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        self._ws = await websockets.connect(
            self._relay_ws_url,
            ping_interval=20,
            ping_timeout=20,
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
