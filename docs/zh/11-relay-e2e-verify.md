# Relay 端到端加密本地验证

## 前置条件

- 已安装：`make venv && make install && make install-relay`
- 验证负载 E2E 时还需：`make install-e2e`
- 本地 NATS：`docker run -p 4222:4222 nats:latest`（或已有 NATS 服务）

---

## 一、基础验证：经 Relay 连通（无加密）

确认 Consumer 经 Relay、Merchant 直连 NATS 能互通。

**终端 1 — NATS**

```bash
docker run -p 4222:4222 nats:latest
```

**终端 2 — Relay**

```bash
make run-relay
# 看到 [Relay] WebSocket 监听 ws://0.0.0.0:8765
```

**终端 3 — Merchant（直连 NATS）**

```bash
make run-merchant
```

**终端 4 — Consumer（经 Relay）**

```bash
RELAY_WS_URL=ws://localhost:8765 .venv/bin/python example/consumer_via_relay.py
```

**预期**：Consumer 打印「收到 N 个报价」，Merchant 打印收到意图并回复。说明 Relay 桥接正常。

---

## 二、验证 TLS（wss）

Relay 启用 TLS，客户端用 `wss://` 连接。

**1. 生成自签名证书（仅测试用）**

```bash
openssl req -x509 -newkey rsa:4096 -keyout relay-key.pem -out relay-cert.pem -days 365 -nodes -subj "/CN=localhost"
```

**2. 启动 Relay（TLS）**

```bash
export RELAY_WS_TLS=1
export RELAY_WS_SSL_CERT=$(pwd)/relay-cert.pem
export RELAY_WS_SSL_KEY=$(pwd)/relay-key.pem
make run-relay
# 看到 已启用 TLS (wss://)，WebSocket 监听 wss://0.0.0.0:8765
```

**3. 启动 Merchant（同上，直连 NATS）**

```bash
make run-merchant
```

**4. Consumer 使用 wss**

```bash
export RELAY_WS_URL=wss://localhost:8765
# 自签名证书会触发 SSL 校验失败，测试时可临时不校验（仅开发环境）：
.venv/bin/python -c "
import os, ssl
os.environ['RELAY_WS_URL'] = 'wss://localhost:8765'
# 不校验自签名证书（仅本地测试）
import asyncio
import websockets
async def run():
    ws = await websockets.connect('wss://localhost:8765', ssl=ssl.create_default_context(), close_timeout=1)
    print('wss 连接成功')
    await ws.close()
asyncio.run(run())
"
```

或用脚本跑完整流程：在 `consumer_via_relay.py` 里用 `wss://` 且 `ssl=ssl.create_default_context()` 时，自签名需设置 `ssl.check_hostname=False` 或加载该证书。**推荐**：本地验证 TLS 时用上面的小脚本确认 wss 握手成功即可；完整 Consumer 示例若要走 wss+自签名，需在 `RelayClientTransport` 里传自定义 `ssl` 上下文（当前 `websockets.connect` 默认会校验）。

**预期**：wss 连接成功，说明 TLS 通道建立正常。

---

## 三、验证负载 E2E（Relay 不可见明文）

通信双方使用相同密钥，Relay 只能看到密文。需双方都经 Relay 且都用 `EncryptedTransportAdapter`。

**1. 启动 NATS + Relay**（同上，终端 1、2）

**2. 运行 E2E 验证脚本（单进程内模拟双端）**

```bash
make install-e2e
.venv/bin/python example/relay_e2e_verify.py
```

脚本内：一端用 `EncryptedTransportAdapter(RelayClientTransport(...), shared_secret=b"test-secret")` 发布，另一端用相同 secret 订阅；验证能收到解密后的明文。

**预期**：脚本打印「收到解密消息: ...」，说明负载 E2E 加解密正常。

---

## 四、可选：与业务示例结合（负载 E2E）

若要让 `consumer_via_relay.py` 与 Merchant 都走负载 E2E，需两端都用 `EncryptedTransportAdapter` 且共享同一密钥；当前 `merchant.py` 直连 NATS，若要验证「Consumer 经 Relay + E2E，Merchant 经 Relay + E2E」，可临时写一个 `merchant_via_relay.py`，使用 `EncryptedTransportAdapter(RelayClientTransport(...), shared_secret=...)`，与 Consumer 端配置相同 `OPEN_A2A_RELAY_PAYLOAD_SECRET` 即可。
