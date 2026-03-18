# OpenClaw 集成 Open-A2A 快速指南

> 本文档面向已经在本地或服务器上部署了 **OpenClaw** 的用户，说明如何让 OpenClaw 通过 Open-A2A 框架与其他 Agent 建立联系、广播意图并接收外部意图。

---

## 1. 集成目标概览

- **OpenClaw 负责**：理解用户自然语言、决策、调用工具、管理会话。
- **Open-A2A 负责**：跨网络 Agent 间的协议与传输（NATS/Relay/Discovery 等）。

集成方式分两部分：

1. **Tool 模式**：OpenClaw 调用一个 HTTP Tool → Bridge → Open-A2A 网络（广播意图、收集报价）。
2. **Channel 模式**：外部 Agent 在 Open-A2A 网络中发布意图 → Bridge → OpenClaw `/hooks/agent`（OpenClaw 成为网络中的一个 Agent）。

---

## 2. 前置条件

- OpenClaw 已在本地或服务器上运行，并可访问其 Gateway（例如 `http://localhost:3000`）。
- 你有一个可用的 NATS 节点（本地 NATS 或公共节点 `nats://...`）。
- 在同一台机器上运行 Open-A2A Bridge（推荐使用 `deploy/quickstart/docker-compose.full.yml`）：

### 2.1 一键启动 Bridge（脚本方式，可选）

如果你不想手动配置 `.env` 与 docker-compose，可以使用提供的脚本一键启动：

```bash
git clone https://github.com/Sawyer-G/Open-A2A.git
cd Open-A2A

bash scripts/setup-openclaw-bridge.sh
```

脚本会：

- 基于 `.env.example` 创建或更新 `.env`；
- 询问并写入 `NATS_URL` / `OPENCLAW_GATEWAY_URL` / `OPENCLAW_HOOKS_TOKEN`；
- 调用 `docker compose -f deploy/quickstart/docker-compose.full.yml --env-file .env up -d --build` 启动 `nats + relay + solid + open-a2a-bridge`。

运行结束后，可用 `docker ps` 检查容器状态，然后继续按本文档配置 OpenClaw 的 Tool 与 Hook。

### 2.2 手动使用 docker-compose 启动（与脚本效果等价）

```bash
git clone https://github.com/Sawyer-G/Open-A2A.git
cd Open-A2A

cp .env.example .env  # 然后根据实际环境修改 NATS_URL / OPENCLAW_GATEWAY_URL / OPENCLAW_HOOKS_TOKEN 等

docker compose -f deploy/quickstart/docker-compose.full.yml --env-file .env up -d --build

docker ps  # 应看到 nats / relay / solid / open-a2a-bridge 等容器
```

默认 Bridge 会监听 `http://localhost:8080`，并通过 `NATS_URL` 连接到 NATS 或你的公共节点。

> **注意**：若使用 Bridge 的「意图转发到 OpenClaw」功能（Channel 集成），需在 OpenClaw 配置中启用 `hooks.allowRequestSessionKey=true`，以便让外部会话使用自定义 `sessionKey`。

---

## 3. Tool 模式：OpenClaw 发起意图（调用 Open-A2A 网络）

### 3.1 在 OpenClaw 中配置 HTTP Tool

若 OpenClaw 支持 `http_request` 或类似 HTTP 调用工具，可配置：

- **工具名**：`open_a2a_publish_intent`
- **调用方式**：

```http
POST {BRIDGE_URL}/api/publish_intent
Content-Type: application/json

{
  "action": "Generic_Request",
  "type": "Noodle",
  "constraints": ["No_Coriander", "<30min"],
  "lat": 31.23,
  "lon": 121.47,
  "collect_offers": true,
  "timeout_seconds": 10
}
```

其中：

- `{BRIDGE_URL}` 通常为 `http://localhost:8080`（若与 OpenClaw 同机）；
- `type` / `constraints` / `lat` / `lon` 等字段由 OpenClaw Agent 根据用户对话填充。

**工具描述**（供 Agent 理解何时调用），示例：

```text
发布意图到 Open-A2A 网络。当用户表达想吃某类食物（如面条、米饭）或需要某类服务时，调用此工具将意图广播到网络并收集其他 Agent 的报价或响应。参数：type（类型）、constraints（约束列表，如忌口、时间）、lat/lon（位置）。
```

### 3.2 YAML 配置示例

若 OpenClaw 使用 YAML 配置工具，可参考：

```yaml
tools:
  - name: open_a2a_publish_intent
    type: http_request
    description: 发布意图到 Open-A2A 网络，收集其他 Agent 的报价或响应。用户说“帮我找能做 X 的服务”时使用。
    config:
      url: "http://localhost:8080/api/publish_intent"
      method: POST
      headers:
        Content-Type: application/json
```

### 3.3 Bridge 返回格式（示例）

```json
{
  "intent_id": "uuid-xxx",
  "offers_count": 2,
  "offers": [
    {
      "id": "offer-1",
      "intent_id": "uuid-xxx",
      "price": 18,
      "unit": "UNIT",
      "description": "手工拉面"
    }
  ],
  "message": "已发布意图，收到 2 个报价"
}
```

OpenClaw Agent 可根据 `offers` 字段生成自然语言回复，向用户展示不同 Agent 给出的报价/方案，并协助选择。

---

## 4. Channel 模式：OpenClaw 作为网络中的 Agent 接收外部意图

在 Channel 模式下，外部 Agent 通过 Open-A2A 网络发布 Intent，Bridge 将这些 Intent 转发给 OpenClaw：

1. **Bridge 订阅 NATS 上的意图主题**（如 `intent.food.order` 或你自定义的 domain）。  
2. 收到 Intent 后，Bridge 调用：

```http
POST {OPENCLAW_GATEWAY_URL}/hooks/agent
Headers:
  x-openclaw-token: {OPENCLAW_HOOKS_TOKEN}
  Content-Type: application/json

Body:
{
  "sessionKey": "open-a2a-intent-{intent_id}",
  "message": "收到一个来自 Open-A2A 网络的意图：……（根据 Intent 填写摘要）",
  "channel": "open_a2a"
}
```

3. OpenClaw 将这条消息当作 `open_a2a` 渠道的一次用户输入，交给 Agent 处理；  
4. Agent 可以：
   - 读取 Intent 摘要与结构化字段；
   - 决定是否接单、报价或继续追问细节；
   - 通过某个 Tool（例如自定义的 `open_a2a_reply_offer`）把应答再发回 Open-A2A 网络。

> 具体的「从 OpenClaw 回复到 Open-A2A」的格式，可以复用 `Offer`、`LogisticsAccept` 等标准消息，或根据业务扩展。关键是：OpenClaw 只看到 HTTP Hook，底层 NATS/Relay 细节由 Bridge 处理。

---

## 5. 小结：OpenClaw 如何使用 Open-A2A

- **发起协作**：  
  - 用户对 OpenClaw 说「帮我找能做 X 的 Agent」；  
  - OpenClaw Agent 调用 `open_a2a_publish_intent` Tool；  
  - Bridge 将意图广播到 Open-A2A 网络，并把响应结果返回给 OpenClaw。

- **参与协作**：  
  - 外部 Agent 在 Open-A2A 上发布 Intent；  
  - Bridge 将 Intent 转成 OpenClaw `hooks/agent` 消息；  
  - OpenClaw Agent 像处理任意 channel 的用户请求那样处理，并可通过 Bridge 再发回回复。

对于 OpenClaw 用户而言，集成 Open-A2A 不需要理解 NATS/Relay/DHT 等底层细节：  
- 只需要运行 Bridge（Docker 或本地 Python），  
- 配置一个 HTTP Tool + 一个 Hook，  
- 就可以把自己的个人助手或服务 Agent 接入一个开放的 Agent-to-Agent 网络。

