#!/usr/bin/env python3
"""
Relay 负载 E2E 加密验证脚本

同一进程内：一端经 EncryptedTransportAdapter + RelayClientTransport 发布明文，
另一端用相同密钥订阅并解密，验证 Relay 上只能看到密文、对端能收到明文。

前置：NATS + Relay 已启动（make run-relay），且已 make install-e2e。
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

RELAY_WS_URL = os.getenv("RELAY_WS_URL", "ws://localhost:8765")
TEST_SUBJECT = "open_a2a.e2e_verify.test"
TEST_SECRET = b"local-e2e-test-secret"
PLAINTEXT = b"hello relay e2e"


async def main() -> None:
    try:
        from open_a2a import RelayClientTransport, EncryptedTransportAdapter
    except ImportError as e:
        print("请先安装 Relay 与 E2E 依赖: make install-relay && make install-e2e")
        raise SystemExit(1) from e

    base = RelayClientTransport(relay_ws_url=RELAY_WS_URL)
    transport = EncryptedTransportAdapter(base, shared_secret=TEST_SECRET)
    await transport.connect()
    print(f"[E2E 验证] 已连接 Relay: {RELAY_WS_URL}，使用负载加密")

    received = asyncio.Event()
    received_payload: list[bytes] = []

    async def on_message(data: bytes) -> None:
        received_payload.append(data)
        received.set()

    sub = await transport.subscribe(TEST_SUBJECT, on_message)
    await asyncio.sleep(0.2)

    await transport.publish(TEST_SUBJECT, PLAINTEXT)
    try:
        await asyncio.wait_for(received.wait(), timeout=5.0)
    except asyncio.TimeoutError:
        await sub.unsubscribe()
        await transport.disconnect()
        print("[E2E 验证] 超时未收到消息，请确认 NATS 与 Relay 已启动")
        raise SystemExit(1)

    await sub.unsubscribe()
    await transport.disconnect()

    if received_payload and received_payload[0] == PLAINTEXT:
        print(f"[E2E 验证] 通过：收到解密消息: {received_payload[0]!r}")
    else:
        print(f"[E2E 验证] 失败：期望 {PLAINTEXT!r}，收到 {received_payload}")
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
