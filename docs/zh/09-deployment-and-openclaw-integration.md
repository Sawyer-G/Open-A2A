# 服务器部署与 OpenClaw 集成指南

> 如何将 Open-A2A 部署到用户现有服务器，并与已部署的 OpenClaw 等服务集成。

---

## 1. 整体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        用户服务器 (同一台或同网段)                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────────────────┐   │
│   │   NATS      │     │ Solid Pod   │     │  OpenClaw (已部署)      │   │
│   │ 消息总线    │     │ 偏好存储    │     │  - Gateway              │   │
│   │ :4222      │     │ :8443       │     │  - WhatsApp/Telegram   │   │
│   └──────┬──────┘     └──────┬──────┘     │  - Agent + Tools       │   │
│          │                   │           └───────────┬─────────────┘   │
│          │                   │                       │                  │
│          ▼                   ▼                       ▼                  │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │              Open-A2A Bridge（适配层，Python 进程）               │  │
│   │  - 订阅 NATS 意图主题 → 转发给 OpenClaw /hooks/agent             │  │
│   │  - 暴露 HTTP API → OpenClaw 作为 Tool 调用，发布意图到 NATS       │  │
│   └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 部署步骤

### 2.1 前置条件

- 服务器已部署 **OpenClaw**（Gateway 可访问）
- 已安装 **Docker** 和 **Docker Compose**
- 网络互通（NATS、Solid、OpenClaw 可互相访问）

### 2.2 一键部署（Docker Compose）

在项目根目录创建 `docker-compose.deploy.yml`：

```yaml
# Open-A2A 完整部署（NATS + Solid + Bridge）
# 与已有 OpenClaw 配合使用

services:
  nats:
    image: nats:latest
    ports:
      - "4222:4222"
    restart: unless-stopped

  solid:
    image: aveltens/solid-server:latest
    ports:
      - "8443:8443"
    restart: unless-stopped

  open-a2a-bridge:
    build:
      context: .
      dockerfile: Dockerfile.bridge
    environment:
      - NATS_URL=nats://nats:4222
      - OPENCLAW_GATEWAY_URL=http://host.docker.internal:3000  # 替换为实际 OpenClaw 地址
      - OPENCLAW_HOOKS_TOKEN=${OPENCLAW_HOOKS_TOKEN}
    depends_on:
      - nats
    restart: unless-stopped
```

### 2.3 环境变量

| 变量 | 说明 | 示例 |
|------|------|------|
| `NATS_URL` | NATS 地址 | `nats://localhost:4222` |
| `OPENCLAW_GATEWAY_URL` | OpenClaw Gateway 地址 | `http://localhost:3000` |
| `OPENCLAW_HOOKS_TOKEN` | OpenClaw Webhook 令牌 | 与 OpenClaw 配置一致 |

---

## 3. 与 OpenClaw 的集成方式

### 方式 A：Tool 集成（用户发起意图）

**场景**：用户在 WhatsApp/Telegram 对 OpenClaw 说「帮我订一份面」，Agent 调用 Open-A2A 工具发布意图。

**实现**：

1. 部署 **Open-A2A Bridge**，暴露 HTTP API：
   ```
   POST /api/publish_intent
   Body: { "action": "Food_Order", "type": "Noodle", "constraints": ["No_Coriander"], ... }
   ```

2. 在 OpenClaw 中配置 **自定义 Tool**（或使用 `http_request`）：
   - 工具名：`open_a2a_publish_intent`
   - 调用：`POST {OPEN_A2A_BRIDGE_URL}/api/publish_intent`
   - Agent 在需要时调用该工具，将用户意图发布到 NATS

3. 其他商家/配送 Agent 订阅 NATS，收到意图后响应。

### 方式 B：Channel 集成（接收外部意图）

**场景**：其他 Agent 在 NATS 上发布意图，OpenClaw 的 Agent 需要响应（如商家 Agent 收到「想吃面」后报价）。

**实现**：

1. **Open-A2A Bridge** 订阅 NATS 主题 `intent.food.order` 等。

2. 收到 Intent 后，调用 OpenClaw 的 **Webhook**：
   ```
   POST {OPENCLAW_GATEWAY}/hooks/agent
   Headers: x-openclaw-token: {OPENCLAW_HOOKS_TOKEN}
   Body: {
     "sessionKey": "open-a2a-intent-{intent_id}",
     "message": "收到意图：用户想吃面条，约束：No_Coriander，请根据你的能力回复报价。",
     "channel": "open_a2a"
   }
   ```

3. OpenClaw Agent 处理该消息，生成报价，Bridge 再将报价发布回 NATS（`intent.food.offer.{id}`）。

### 方式 C：混合（完整 A-B-C 流程）

- **Consumer 侧**：用户通过 OpenClaw（WhatsApp）说「订面」→ Tool 发布 Intent
- **Merchant 侧**：OpenClaw 作为商家 Agent，Bridge 将 Intent 转给 OpenClaw → Agent 报价 → Bridge 发回 NATS
- **Carrier 侧**：可独立运行 `example/carrier.py`，或同样通过 Bridge 接入 OpenClaw

---

## 4. Open-A2A Bridge 实现

Bridge 已实现，位于 `bridge/main.py`。

| 功能 | 实现 |
|------|------|
| 订阅 NATS 意图 | `IntentBroadcaster.subscribe_intents()`，收到后转发 |
| 转发给 OpenClaw | `httpx.post(gateway_url + "/hooks/agent", ...)` |
| 暴露发布 API | `POST /api/publish_intent`，可选收集报价并返回 |
| 健康检查 | `GET /health` |

**运行方式**：
```bash
make install-bridge && make run-bridge
# 或
docker compose -f docker-compose.deploy.yml up -d
```

**API 示例**：
```bash
curl -X POST http://localhost:8080/api/publish_intent \
  -H "Content-Type: application/json" \
  -d '{"type":"Noodle","constraints":["No_Coriander"],"collect_offers":true}'
```

**OpenClaw Tool 配置**：见 [openclaw-tool-example.md](./openclaw-tool-example.md)

---

## 5. 网络与安全

| 考虑 | 建议 |
|------|------|
| NATS 暴露 | 生产环境建议仅内网访问，或通过 TLS + 认证 |
| Solid | 生产环境使用真实证书，限制访问 |
| OpenClaw Gateway | 确保 `hooks.token` 配置正确，Bridge 调用时携带 |
| Bridge | 仅在内网或通过反向代理暴露，避免直接公网 |

---

## 6. 与现有服务共存

若服务器上已有：

- **NATS**：直接复用，将 `NATS_URL` 指向现有实例
- **OpenClaw**：无需修改 OpenClaw 部署，仅配置 Tool/Webhook 指向 Bridge
- **Solid**：可选，若已有自托管 Solid，配置 `SOLID_*` 环境变量即可
- **其他 Agent 运行时**：同样通过 Bridge 的 HTTP API 或 NATS 订阅接入

---

## 7. 下一步

1. ~~实现 **Open-A2A Bridge** 完整代码（含 Dockerfile）~~ ✅ 已完成
2. ~~编写 OpenClaw 的 **Open-A2A Tool** 配置示例~~ ✅ 见 [openclaw-tool-example.md](./openclaw-tool-example.md)
3. 提供 **TypeScript SDK** 或 HTTP 客户端，便于 OpenClaw 直接调用（见 07-multi-language-sdk.md）
