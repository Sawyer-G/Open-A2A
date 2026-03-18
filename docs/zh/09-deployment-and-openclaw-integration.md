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

## 1.1 一键部署完整节点（Docker：NATS + Relay + Solid + Bridge）

> 若你希望在一台服务器上快速起一套 **完整的 Open-A2A 节点栈**（作为公共入口或测试网节点），可以使用 quickstart compose：`deploy/quickstart/docker-compose.full.yml`。

### 步骤（示例）

```bash
# 1. 在服务器上克隆仓库
git clone https://github.com/Sawyer-G/Open-A2A.git
cd Open-A2A

# 2. 如有需要，先配置 .env（例如 NATS_URL、OPENCLAW_GATEWAY_URL 等）
cp .env.example .env
# 根据你的环境修改 .env 中的占位符

# 3. 一键启动
docker compose -f deploy/quickstart/docker-compose.full.yml --env-file .env up -d --build

# 4. 查看服务状态
docker ps
```

启动后默认包含：

- `nats`：NATS 消息总线（默认 `4222`）；
- `relay`：Open-A2A Relay（默认 `8765`，WebSocket 出站入口）；
- `solid`：自托管 Solid Pod（默认 `8443`）；
- `open-a2a-bridge`：Bridge 服务（默认 `8080`），用于与 OpenClaw 等运行时集成。

你可以根据需要在云厂商防火墙中开放对应端口，并通过 DNS 将子域（如 `nats.open-a2a.org`、`relay.open-a2a.org`）解析到这台服务器（建议使用 **仅 DNS** 模式，不通过 HTTP 代理）。

---

## 2. 部署步骤

### 2.1 前置条件

- 服务器已部署 **OpenClaw**（Gateway 可访问）
- 已安装 **Docker** 和 **Docker Compose**
- 网络互通（NATS、Solid、OpenClaw 可互相访问）

### 2.2 一键部署（Docker Compose）

使用仓库内置的 quickstart compose（如需生产化运营节点，请改用 `deploy/node-x/`）：

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
      context: ../..
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
| 能力发现（NATS） | `POST /api/register_capabilities`、`GET /api/discover`（请求-响应，无中心化注册表） |

**运行方式**：
```bash
make install-bridge && make run-bridge
# 或
docker compose -f deploy/quickstart/docker-compose.full.yml --env-file .env up -d
```

**API 示例**：
```bash
curl -X POST http://localhost:8080/api/publish_intent \
  -H "Content-Type: application/json" \
  -d '{"type":"Noodle","constraints":["No_Coriander"],"collect_offers":true}'
```

**OpenClaw Tool 配置**：见 [openclaw-tool-example.md](./openclaw-tool-example.md)

---

### 4.1 持续被发现：能力注册（register）与查询（discover）

如果你希望其他节点能够“像查目录一样”持续发现你的 Agent（而不是仅在广播意图时被动触达），推荐让 Bridge 作为常驻进程，替 OpenClaw Agent 在 NATS 上注册能力。

Bridge 支持两种方式：

1) **启动时自动注册（推荐）**

通过环境变量配置：

- `BRIDGE_ENABLE_DISCOVERY=1`
- `BRIDGE_AGENT_ID=openclaw-agent`
- `BRIDGE_CAPABILITIES=intent.food.order,intent.logistics.request`（逗号分隔）
- 可选：`BRIDGE_META_JSON='{"region":"shanghai","endpoint":"https://bridge.open-a2a.org"}'`

2) **通过 HTTP 接口注册/更新（适合 OpenClaw Tool/Skill 调用）**

```bash
curl -X POST http://localhost:8080/api/register_capabilities \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"openclaw-agent","capabilities":["intent.food.order"],"meta":{"region":"shanghai"},"ttl_seconds":60}'
```

其他节点可查询某能力的提供者列表：

```bash
curl "http://localhost:8080/api/discover?capability=intent.food.order&timeout_seconds=3" | jq .
```

说明：

- NATS Discovery **没有中心化注册表**；`register` 的实现是订阅 `open_a2a.discovery.query.{capability}` 并在被查询时返回 `meta`。
- 因此要“持续被发现”，注册方（或代注册的 Bridge）需要保持在线。

#### 4.1.1 运营级能力（TTL / 鉴权 / 限流 / 观测）

为了避免“僵尸注册”（长期不在线的 provider 仍在目录中）、并提升公共节点的可运维性，Bridge 额外提供：

- **TTL/过期回收**：`ttl_seconds` 到期未续租将自动移除；续租方式是再次调用 `POST /api/register_capabilities`
- **访问控制（可选）**：可为 register/discover 分别设置 Bearer Token
- **速率限制（可选）**：简单的按 IP 限流（每分钟请求数）
- **观测**：`GET /api/discovery_stats` 返回当前在线 provider 数、按 capability 的分布、以及最近错误

相关环境变量见 `.env.example`：

- `BRIDGE_DISCOVERY_DEFAULT_TTL_SECONDS`
- `BRIDGE_DISCOVERY_CLEANUP_INTERVAL_SECONDS`
- `BRIDGE_DISCOVERY_REDIS_URL`（推荐：Redis 注册表后端，用于多实例/HA；设定后不再依赖单实例内存/文件）
- `BRIDGE_DISCOVERY_PERSIST_PATH`（可选：目录持久化文件路径，用于单实例重启恢复；默认关闭）
- `BRIDGE_DISCOVERY_REGISTER_TOKEN` / `BRIDGE_DISCOVERY_DISCOVER_TOKEN`
- `BRIDGE_DISCOVERY_RL_PER_MINUTE`

## 5.1 非 Docker 部署（高级用户）

对于不希望在服务器上使用 Docker 的用户，可以直接在宿主机上运行 Open-A2A Bridge（以及可选的 Relay）。推荐使用仓库自带脚本：

```bash
git clone https://github.com/Sawyer-G/Open-A2A.git
cd Open-A2A

bash scripts/setup-openclaw-bridge-baremetal.sh
```

该脚本会：

- 检查本机是否已安装 `python3` 和 `make`；
- 创建/更新 `.env` 中的 `NATS_URL`、`OPENCLAW_GATEWAY_URL`、`OPENCLAW_HOOKS_TOKEN`；
- 使用 `make install-bridge` 在 `.venv/` 中安装 Bridge 依赖；
- 使用 `.venv/bin/uvicorn` 在本机后台启动 Bridge 服务（默认 `0.0.0.0:8080`），日志写入 `logs/bridge.log`。

前置条件：

- 服务器上已经有可用的 NATS（或可以使用公共 NATS 节点），并在 `NATS_URL` 中配置正确；
- OpenClaw Gateway 能够通过 `OPENCLAW_GATEWAY_URL` 从本机访问到。

运行成功后，可以通过：

```bash
curl http://localhost:8080/health | jq .
```

来检查 Bridge 与 NATS / OpenClaw 的连通状态。

后续在 OpenClaw 中配置 Tool / Webhook 的方式与 Docker 部署完全一致，唯一差异只是 Bridge 的地址从容器端口变为宿主机端口（通常是 `http://<服务器IP>:8080`）。

---

## 5. 网络与安全

| 考虑 | 建议 |
|------|------|
| NATS 暴露 | 如果希望**其他机器上的 Agent 直接连到这台服务器的 NATS**（如本机 Consumer ↔ 远程 Merchant），需要在防火墙中放行 NATS 客户端端口（默认 `4222`）。如果只在同一台机 / 内网使用，可将 NATS 仅监听内网地址，或通过 TLS + 认证限制访问。 |
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

## 7. OpenClaw 已在 Docker 时如何自动接入

若 OpenClaw 已经跑在 Docker（同一台机或同一编排内），只要让 **Bridge 与 OpenClaw 网络互通**，即可实现「自动」调用框架：

| 方向 | 行为 | 说明 |
|------|------|------|
| **NATS → OpenClaw** | 自动 | Bridge 订阅 NATS 意图主题，收到后自动 `POST` 到 OpenClaw `/hooks/agent`，无需人工转发 |
| **OpenClaw → 框架** | 自动 | 在 OpenClaw 中配置 Open-A2A Tool（见 [openclaw-tool-example.md](./openclaw-tool-example.md)），用户说「订面」等时 Agent 自动调用 Tool，即调用 Bridge 的 `POST /api/publish_intent` |

### 7.1 网络互通方式

**方式 A：Bridge 与 OpenClaw 在同一 Docker 网络**

- 若 OpenClaw 由独立 compose 部署，先查其网络名（如 `openclaw_default`）。启动 Bridge 时加入该网络：
  ```yaml
  # 在你的 compose（例如 deploy/quickstart/docker-compose.full.yml 或 deploy/node-x/docker-compose.node-x.yml）
  # 的 open-a2a-bridge 下增加
  networks:
    - default
    - openclaw_default  # 与 OpenClaw 同一网络
  ```
  并设置：
  ```bash
  OPENCLAW_GATEWAY_URL=http://<OpenClaw Gateway 服务名>:<端口>
  ```
  例如 OpenClaw Gateway 服务名为 `gateway`、端口 3000，则 `OPENCLAW_GATEWAY_URL=http://gateway:3000`。
- 若你把 Bridge 和 OpenClaw 写进**同一份** compose：给 Bridge 和 OpenClaw 同一 `networks`，用 OpenClaw 的**服务名**填 `OPENCLAW_GATEWAY_URL` 即可。

**方式 B：OpenClaw 在宿主机、Bridge 在 Docker**

- 使用文档中的 `host.docker.internal`（Linux 需 Docker 20.10+ 或 `extra_hosts`）：
  ```bash
  OPENCLAW_GATEWAY_URL=http://host.docker.internal:3000
  ```

**方式 C：OpenClaw 在 Docker、其他机器通过 Bridge 发布意图**

- Bridge 对外暴露 `8080`，OpenClaw 内配置 Tool 的 URL 为「能访问到 Bridge 的地址」：若 OpenClaw 与 Bridge 同机同网，Tool URL 填 `http://open-a2a-bridge:8080`（服务名）或 `http://主机IP:8080`。

### 7.2 小结

- **可以**在已部署 OpenClaw（含 Docker）的服务器上再部署 NATS + Bridge；配置好 `OPENCLAW_GATEWAY_URL` 与 `OPENCLAW_HOOKS_TOKEN` 后，**意图会自动从 NATS 转发到 OpenClaw**，OpenClaw 侧**无需改代码**，只需能收到 webhook 并配置 Tool。
- OpenClaw 作为「消费者」时，通过配置好的 Tool **自动调用** Bridge 的发布接口，即完成对框架的调用。

---

## 8. FAQ：用户是否必须开放 4222 端口？

- **不是所有用户都需要手动开放 4222。**
  - 对于「普通使用者」（只在本机或公司内网跑 Agent，连接到别人提供的 NATS / Relay），他们只需要向外**出站连接**即可，不必在自己的路由器或云服务器上开放任何端口。
  - 对于「运行公共 NATS 节点或作为网络枢纽的服务器」（例如你这台 GCP 机器，希望别人的 Agent 能连进来），则**需要对这些 Agent 所在网络放行 NATS 客户端端口**（默认 4222，或你自定义的端口）。
- 如果希望避免在服务器上直接暴露 4222，也可以：
  - 只在内网开放 NATS，由 **Relay** 对外提供 WebSocket 出站接入（对外只暴露 Relay 端口，例如 8765）；
  - 或使用 SSH 隧道等方式，让远程 Agent 通过安全通道访问内网 NATS。

换句话说：**开放 4222 是「运行公共/对外 NATS 节点」的责任，而不是每个最终用户的必选动作。普通用户更多是连接别人提供的 NATS/Relay，而不是自己开放端口。**

---

## 9. 公共入口节点、域名与去中心化的关系

从运维视角看，Open-A2A 网络中通常会出现少量「公共入口节点」：

- 由项目方或社区运营的 NATS / Relay / Bridge / DHT bootstrap 节点；
- 绑定一个或多个域名（例如 `nats.example.net`、`relay.example.net`、`bridge.example.net`），为所有 Agent 提供稳定的接入地址；
- 在文档和 SDK 示例中，常作为默认的 `NATS_URL`、`RELAY_WS_URL`、`OPEN_A2A_BRIDGE_URL`。

这**并不违背去中心化的目标**，原因在于：

- 协议层设计始终允许**任意人运行自己的节点**：任何人都可以起一套 NATS/Relay/Bridge，并在社区中公布自己的接入地址；
- Agent 不绑定某一个入口节点，理论上可以：
  - 选择不同运营者的节点；
  - 同时连接多个节点（多宿接入）；
  - 根据 DHT/发现协议发现新的节点/能力提供者；
- 与很多 Web3 项目类似：「官方/社区节点」的存在是为了**降低接入门槛**，不等于「必须通过这一个中心才能参与」。

对未来用户而言，推荐模式是：

- **普通用户/终端 Agent**：只需出站连到某个可用入口（官方或第三方运营的节点），无需自己开放端口或搭建基础设施；
- **高级用户/运营者**：可以运行自己的公共节点和域名，服务于自己组织或社区；只要遵守协议规范，就能与其他节点一起构成更大的 Open-A2A 网络。

---

## 10. 下一步

1. ~~实现 **Open-A2A Bridge** 完整代码（含 Dockerfile）~~ ✅ 已完成
2. ~~编写 OpenClaw 的 **Open-A2A Tool** 配置示例~~ ✅ 见 [openclaw-tool-example.md](./openclaw-tool-example.md)
3. 提供 **TypeScript SDK** 或 HTTP 客户端，便于 OpenClaw 直接调用（见 07-multi-language-sdk.md）
