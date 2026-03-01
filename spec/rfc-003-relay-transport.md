# RFC-003: Relay 传输（出站优先）

> 版本：0.1.0-draft | 状态：草稿

## 1. 概述

个人 AI Agent 常处于无公网 IP、无域名、无 webhook 配置的环境。本协议定义 **Open-A2A Relay** 与 **Relay 客户端** 之间的 WebSocket 协议，使 Agent 仅通过**出站连接**即可参与主题的发布与订阅，由框架提供可达性。

## 2. 目标

- **出站优先**：Agent 主动连接 Relay，无需本机被外网访问。
- **与 NATS 语义一致**：Relay 桥接 WebSocket 与 NATS，主题与消息格式与 RFC-001 一致。
- **传输可替换**：Relay 为 TransportAdapter 的一种实现（RelayClientTransport），与直连 NATS 的 Agent 可互通（经同一 NATS）。

## 3. 协议（JSON over WebSocket）

### 3.1 Client -> Relay

| type        | 说明     | 字段                |
|-------------|----------|---------------------|
| subscribe   | 订阅主题 | subject: string     |
| unsubscribe | 取消订阅 | subject: string     |
| publish     | 发布消息 | subject: string, body: string (base64) |

### 3.2 Relay -> Client

| type    | 说明         | 字段                |
|---------|--------------|---------------------|
| message | 转发 NATS 消息 | subject: string, body: string (base64) |

### 3.3 示例

```json
// Client 订阅
{"type": "subscribe", "subject": "intent.food.order"}

// Relay 转发给 Client
{"type": "message", "subject": "intent.food.order", "body": "eyJpZCI6InV1aWQifQ=="}

// Client 发布
{"type": "publish", "subject": "intent.food.offer.xxx", "body": "eyJwcmljZSI6MTh9"}
```

## 4. 参考实现

- **Relay 服务端**：`relay/main.py`，连接 NATS，暴露 WebSocket，桥接订阅与发布。
- **客户端传输**：`open_a2a/transport_relay.py`，`RelayClientTransport` 实现 TransportAdapter。
- **示例**：`example/consumer_via_relay.py`，经 Relay 发布意图并收集报价。

## 5. 部署与扩展

- 单 Relay：适合开发与小规模；Agent 配置 `RELAY_WS_URL` 即可（如 `ws://relay.example.com`）。
- 多 Relay / 高可用：可部署多个 Relay 实例，均连接同一 NATS 集群；Agent 任选其一或按地域选择。
- 与直连 NATS 的 Agent 互通：Relay 仅做传输桥接，主题与消息与 NATS 一致，故直连 NATS 的 Merchant 与经 Relay 的 Consumer 可正常交互。

## 6. 端到端加密（E2E）

### 6.1 传输层 TLS（wss）

- Relay 服务端可通过 `RELAY_WS_TLS=1`、`RELAY_WS_SSL_CERT`、`RELAY_WS_SSL_KEY` 启用 TLS，对外提供 **wss://**。
- 客户端将 `RELAY_WS_URL` 设为 `wss://...` 即可加密信道，防止窃听与篡改。

### 6.2 负载加密（Relay 不可见明文）

- 可选：使用 `EncryptedTransportAdapter` 包装 `RelayClientTransport`（或其它 Transport），对消息体进行对称加密。
- 通信双方配置相同密钥（`OPEN_A2A_RELAY_PAYLOAD_SECRET` 或构造时传入 `shared_secret`），Relay 与 NATS 仅能看到密文。
- 依赖：`pip install open-a2a[e2e]`（cryptography）。
