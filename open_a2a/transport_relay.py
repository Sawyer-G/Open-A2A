"""
Relay 传输适配器（出站优先）

Agent 无需公网 IP 或 webhook：通过 WebSocket 主动连接 Open-A2A Relay，
即可参与主题的发布与订阅。由框架提供可达性，用户无需申请域名或配置回调。

支持 wss://：可选传入 ssl.SSLContext，或设置 RELAY_WS_SSL_VERIFY=0 以信任自签名证书（仅开发/测试）。

增强（面向公网/弱网）：
- 可选鉴权：通过 WebSocket `Authorization: Bearer <token>` 或 URL query `?token=` 传递
- 可选自动重连：指数退避 + 重连后自动恢复订阅（resubscribe）
"""

import asyncio
import base64
import inspect
import json
import os
import ssl
import uuid
from typing import Any, Awaitable, Callable, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

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
        *,
        auth_token: Optional[str] = None,
        auto_reconnect: Optional[bool] = None,
        reconnect_initial_backoff_seconds: float = 0.5,
        reconnect_max_backoff_seconds: float = 10.0,
        connect_timeout_seconds: float = 10.0,
    ) -> None:
        if websockets is None:
            raise ImportError("websockets is required. Install with: pip install open-a2a[relay]")
        self._relay_ws_url = relay_ws_url
        self._ssl: Optional[ssl.SSLContext] = ssl
        self._ws = None
        self._recv_task: Optional[asyncio.Task] = None
        self._run_task: Optional[asyncio.Task] = None
        self._connected_evt = asyncio.Event()
        self._stop = False
        self._remote_subjects: set[str] = set()
        self._subs: dict[str, dict[str, Callable[[bytes], Awaitable[None]]]] = {}
        # subject -> {sub_id -> cb}
        self._lock = asyncio.Lock()
        self._auth_token = (
            (auth_token or "").strip()
            or os.getenv("RELAY_CLIENT_AUTH_TOKEN", "").strip()
            or os.getenv("RELAY_AUTH_TOKEN", "").strip()
        )
        if auto_reconnect is None:
            auto_reconnect = os.getenv("RELAY_AUTO_RECONNECT", "1").strip().lower() in (
                "1",
                "true",
                "yes",
            )
        self._auto_reconnect = bool(auto_reconnect)
        self._reconnect_initial = float(reconnect_initial_backoff_seconds)
        self._reconnect_max = float(reconnect_max_backoff_seconds)
        self._connect_timeout = float(connect_timeout_seconds)

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
        if self._run_task and not self._run_task.done():
            return None
        self._stop = False
        self._connected_evt.clear()
        self._run_task = asyncio.create_task(self._run_forever())
        try:
            await asyncio.wait_for(self._connected_evt.wait(), timeout=self._connect_timeout)
        except asyncio.TimeoutError as e:
            raise TimeoutError("Relay connection timed out") from e
        return None

    def _ws_connect_kwargs(self, *, ws_url: Optional[str] = None) -> dict[str, Any]:
        # 如果 URL query 已含 token，则让 Relay 通过 query token 鉴权，避免 Authorization header
        # 在某些客户端/版本组合下出现解析差异导致的误拒绝。
        url_for_auth = ws_url or self._relay_ws_url
        parsed = urlparse(url_for_auth)
        has_query_token = any(k == "token" for k, _ in parse_qsl(parsed.query, keep_blank_values=True))

        ssl_ctx = self._resolve_ssl()
        headers = []
        if self._auth_token and not has_query_token:
            headers.append(("Authorization", f"Bearer {self._auth_token}"))
        kwargs: dict[str, Any] = {
            "ping_interval": 20,
            "ping_timeout": 20,
            "ssl": ssl_ctx,
        }
        if headers:
            # websockets 旧版本使用 extra_headers；新版本使用 additional_headers
            header_arg = "extra_headers"
            try:
                sig = inspect.signature(websockets.connect)
                if "additional_headers" in sig.parameters:
                    header_arg = "additional_headers"
            except Exception:
                pass
            kwargs[header_arg] = headers
        return kwargs

    def _resolve_relay_ws_url_with_token(self) -> str:
        """
        Relay 支持从 URL query 读取 token: ?token=...
        为了兼容不同 websockets/header 路径，把 token 也追加到 URL。
        """
        if not self._auth_token:
            return self._relay_ws_url

        parsed = urlparse(self._relay_ws_url)
        q = parse_qsl(parsed.query, keep_blank_values=True)
        if any(k == "token" for k, _ in q):
            return self._relay_ws_url
        q.append(("token", self._auth_token))
        new_query = urlencode(q)
        return urlunparse(parsed._replace(query=new_query))

    async def _run_forever(self) -> None:
        backoff = self._reconnect_initial
        while not self._stop:
            try:
                self._remote_subjects.clear()
                ws_url = self._resolve_relay_ws_url_with_token()
                self._ws = await websockets.connect(ws_url, **self._ws_connect_kwargs(ws_url=ws_url))
                self._connected_evt.set()
                backoff = self._reconnect_initial
                await self._resubscribe_all()
                await self._receive_loop()
            except asyncio.CancelledError:
                break
            except Exception:
                # swallow and retry if enabled
                pass
            finally:
                try:
                    if self._ws:
                        await self._ws.close()
                except Exception:
                    pass
                self._ws = None
                self._remote_subjects.clear()
            if self._stop or not self._auto_reconnect:
                break
            await asyncio.sleep(backoff)
            backoff = min(self._reconnect_max, backoff * 2.0)

    async def _receive_loop(self) -> None:
        try:
            if not self._ws:
                return
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
        self._stop = True
        if self._run_task:
            self._run_task.cancel()
            try:
                await self._run_task
            except asyncio.CancelledError:
                pass
            self._run_task = None
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        self._subs.clear()
        self._remote_subjects.clear()
        self._connected_evt.clear()

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
        need_remote_sub = False
        async with self._lock:
            if subject not in self._subs:
                self._subs[subject] = {}
                need_remote_sub = True
            self._subs[subject][sub_id] = cb
        if need_remote_sub and self._ws and subject not in self._remote_subjects:
            await self._ws.send(json.dumps({"type": "subscribe", "subject": subject}))
            self._remote_subjects.add(subject)
        return _RelaySubscription(self, subject, sub_id)

    async def _unsubscribe(self, subject: str, sub_id: str) -> None:
        should_remote_unsub = False
        async with self._lock:
            if subject in self._subs:
                self._subs[subject].pop(sub_id, None)
                if not self._subs[subject]:
                    del self._subs[subject]
                    should_remote_unsub = True
        if self._ws:
            if should_remote_unsub and subject in self._remote_subjects:
                await self._ws.send(json.dumps({"type": "unsubscribe", "subject": subject}))
                self._remote_subjects.discard(subject)

    async def _resubscribe_all(self) -> None:
        if not self._ws:
            return
        async with self._lock:
            subjects = list(self._subs.keys())
        for subject in subjects:
            try:
                await self._ws.send(json.dumps({"type": "subscribe", "subject": subject}))
                self._remote_subjects.add(subject)
            except Exception:
                # Connection may be closing; let outer loop retry.
                return
