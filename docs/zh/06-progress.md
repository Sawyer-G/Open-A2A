# 项目进度

> 最后更新：2026-02-28

## 总体状态

| 阶段 | 状态 | 说明 |
|------|------|------|
| **Phase 1: Hello Open-A2A** | ✅ 已完成 | 广播-响应流程已跑通并验证 |
| **Phase 2: 隐私与身份认证** | ✅ 已完成 | did:key 签名 + 偏好存储抽象 |
| **Phase 3: 复杂场景模拟** | ✅ 已完成 | A-B-C 全链路 + 模拟结算 |

---

## Phase 1 完成项

### 1. 协议规范

- **RFC-001 意图协议**（`spec/rfc-001-intent-protocol.md`）
  - 主题结构：`intent.food.order`、`intent.food.offer.{id}`
  - 消息格式：Intent、Offer 的 JSON 定义
  - 交互流程说明

### 2. 核心 SDK（`open_a2a/`）

| 模块 | 说明 |
|------|------|
| `intent.py` | Intent、Offer、Location 数据模型 |
| `broadcaster.py` | NATS 封装：发布意图、订阅意图、发布/收集报价 |
| `agent.py` | BaseAgent 基类（预留扩展） |

### 3. 示例 Demo（`example/`）

| 文件 | 说明 |
|------|------|
| `consumer.py` | 发布「想吃面条」意图，收集商家报价 |
| `merchant.py` | 订阅意图，自动回复 Offer |

### 4. 开发环境

- 虚拟环境（`.venv/`）
- Makefile：`venv`、`install`、`install-full`、`install-solid`、`install-bridge`、`run-merchant`、`run-consumer`、`run-carrier`、`run-bridge`
- `pyproject.toml`、`requirements.txt`、`.env.example`

### 5. 验证结果

- NATS 消息通道正常
- Consumer 发布意图 → Merchant 收到并回复 → Consumer 收到报价
- 流程已通过实际运行验证

---

## Phase 3 完成项

### 1. 协议扩展（RFC-001）

- 新增主题：`intent.food.order_confirm`、`intent.logistics.request`、`intent.logistics.accept.{id}`
- 新增消息：OrderConfirm、LogisticsRequest、LogisticsAccept

### 2. SDK 扩展

| 模块 | 新增 |
|------|------|
| `intent.py` | OrderConfirm、LogisticsRequest、LogisticsAccept、delivery 字段 |
| `broadcaster.py` | publish_order_confirm、subscribe_order_confirm、publish_logistics_request、subscribe_logistics_requests、publish_logistics_accept、publish_and_collect_logistics_accepts |

### 3. 示例 Demo

| 文件 | 说明 |
|------|------|
| `consumer.py` | 选择报价后发布 OrderConfirm |
| `merchant.py` | 订阅 order_confirm，发布 LogisticsRequest，收集 LogisticsAccept |
| `carrier.py` | 订阅配送请求，自动接单并模拟送达 |

### 4. A-B-C 全流程

```
Consumer → Intent → Merchant(s) → Offer
Consumer → OrderConfirm → Merchant
Merchant → LogisticsRequest → Carrier(s) → LogisticsAccept
Merchant 收到接单 → 模拟结算完成
Carrier 模拟送达
```

### 5. Makefile

- 新增 `make run-carrier`、`make run-bridge`、`make install-bridge`

---

## Phase 2 完成项

### 1. DID 身份与消息签名

- **identity.py**：基于 [didlite](https://github.com/jondepalma/didlite-pkg) 的 `AgentIdentity`，支持 `did:key` 生成与 JWS 签名/验签
- **broadcaster.py**：可选 `identity` 参数，发布时对 Intent/Offer 签名，订阅时解析 JWS 或 JSON
- **intent.py**：Intent、Offer 新增 `sender_did` 字段（验签后填充）

### 2. 偏好存储抽象

- **preferences.py**：`PreferencesProvider` 抽象基类，`FilePreferencesProvider` 基于 JSON 文件实现
- **SolidPodPreferencesProvider**：从自托管 Solid Pod 读写偏好（**推荐**，`pip install open-a2a[solid]`），符合数据主权
- **deploy/solid/docker-compose.solid.yml**：自托管 Solid 一键部署
- **example/profile.json**：示例偏好文件（constraints、location）
- **example/upload_profile_to_solid.py**：将本地 profile.json 上传到 Pod 的脚本

### 3. 示例更新

- **consumer.py**：支持从 `profile.json` 或 Solid Pod 读取偏好，`USE_IDENTITY=1` 时启用 DID 签名
- **merchant.py**：`USE_IDENTITY=1` 时启用 DID 签名

### 4. 依赖与安装

- **pyproject.toml**：新增可选依赖 `[identity]`（didlite）、`[solid]`（solid-file）、`[bridge]`（fastapi、uvicorn、httpx）
- **Makefile**：新增 `make install-full`、`make install-solid`、`make install-bridge`、`make run-bridge`

### 5. 虚拟环境规范

- **.cursor/rules**：新增虚拟环境规范，要求使用 `.venv/bin/pip`、`.venv/bin/python`，避免污染系统环境

---

## Bridge 扩展（OpenClaw 集成）

- **bridge/main.py**：FastAPI 服务，`POST /api/publish_intent` 发布意图并可选收集报价，`GET /health` 健康检查
- **NATS 订阅转发**：订阅 `intent.food.order`，收到后转发给 OpenClaw `/hooks/agent`（需配置 `OPENCLAW_GATEWAY_URL`、`OPENCLAW_HOOKS_TOKEN`）
- **能力发现（NATS）**：支持通过 `POST /api/register_capabilities` 注册能力（Bridge 在线时持续可被 discover），并通过 `GET /api/discover` 查询“谁支持某能力”
- **Dockerfile.bridge**：Bridge 镜像构建
- **deploy/quickstart/docker-compose.full.yml**：全栈 quickstart（NATS + Relay + Solid + Bridge）
- **docs/zh/openclaw-tool-example.md**：OpenClaw Tool 配置示例

---

## 提交历史

| 提交 | 说明 |
|------|------|
| `4bffee1` | feat: 实现 Phase 1 Hello Open-A2A 框架 |
| `ab543fd` | chore: 初始化项目，添加文档与规范 |

---

## 传输层抽象（设计原则 2.3）

- **transport.py**：`TransportAdapter` 抽象基类，定义 `connect`、`disconnect`、`publish`、`subscribe` 接口
- **transport_nats.py**：`NatsTransportAdapter`，NATS 参考实现
- **broadcaster.py**：`IntentBroadcaster` 支持注入 `transport` 参数，默认使用 NATS，保持向后兼容
- 未来可扩展：HTTP、WebSocket、DHT、P2P 等传输适配器

---

## Agent 发现（跨服务器发现）

- **discovery.py**：`DiscoveryProvider` 抽象，定义 `register`、`unregister`、`discover`
- **discovery_nats.py**：`NatsDiscoveryProvider`，基于 NATS 请求-响应，无需中心化注册表
- **主题**：`open_a2a.discovery.query.{capability}`，capability 与意图主题对应（如 `intent.food.order`）
- **spec/rfc-002-discovery.md**：发现协议草稿
- **example/discovery_demo.py**：`make run-discovery-demo` 运行示例
- **扩展**：同 NATS/集群内已可用；多 NATS 集群见 [10-nats-cluster-federation.md](./10-nats-cluster-federation.md)；跨网络发现见 DHT 后端

---

## DHT 发现后端（跨网络，无中心索引）

- **discovery_dht.py**：`DhtDiscoveryProvider`，基于 Kademlia DHT；能力注册/发现写入 DHT，不依赖同一 NATS
- **适用**：不同 NATS 集群、不同传输的 Agent 通过公共或自建 bootstrap 加入同一 DHT 网即可互相发现
- **公共 bootstrap 列表**：未传 `bootstrap_nodes` 时使用 `get_default_dht_bootstrap()`；优先读环境变量 `OPEN_A2A_DHT_BOOTSTRAP`（格式 `host1:port1,host2:port2`），未设置时使用 `DEFAULT_DHT_BOOTSTRAP`（可预置社区公共节点）。所有人配置同一列表即加入同一 DHT 网。
- **依赖**：`pip install open-a2a[dht]`（kademlia）；示例 `make run-discovery-dht-demo`、`example/discovery_dht_demo.py`
- **与 NATS 发现关系**：NATS 发现适用于「同一 NATS/集群」；DHT 发现适用于「跨集群/完全异构网络」

---

## NATS 集群联邦

- **文档**：[10-nats-cluster-federation.md](./10-nats-cluster-federation.md)：配置说明、两节点示例、Docker Compose
- **部署**：`deploy/nats-cluster/` 下 `nats-a.conf`、`nats-b.conf`、`docker-compose.yml`，多台服务器共享主题空间后，发现与意图互通

---

## Relay 传输（出站优先，RFC-003）

- **relay/main.py**：WebSocket 服务，连接 NATS，桥接 Client 的 subscribe/unsubscribe/publish 与 NATS 主题
- **transport_relay.py**：`RelayClientTransport`，实现 TransportAdapter；Agent 通过 `relay_ws_url` 出站连接即可参与网络
- **协议**：JSON over WebSocket（subscribe / unsubscribe / publish；message 下行），见 spec/rfc-003-relay-transport.md
- **示例**：`example/consumer_via_relay.py`、`make run-relay`、`make install-relay`
- **意义**：无公网 IP/域名/webhook 的 Agent 由框架提供可达性，无需用户自建回调

---

## 下一步计划

1. ~~**Open-A2A Bridge**~~ ✅ 已实现（`bridge/main.py`、`Dockerfile.bridge`、`make run-bridge`）
2. ~~**传输层抽象**~~ ✅ 已实现（`TransportAdapter`、`NatsTransportAdapter`）
3. ~~**Agent 跨服务器发现**~~ ✅ 已实现（`DiscoveryProvider`、`NatsDiscoveryProvider`，RFC-002）
4. ~~**可选：多 Merchant 场景测试**~~ ✅ 已实现：`example/multi_merchant_demo.py`、`make run-multi-merchant-demo`；可选 `make run-merchant-2`/`run-merchant-3` 手动多终端验证；**可选**：真实支付通道对接
5. ~~**可选：Solid Pod 客户端凭证认证**~~ ✅ 已实现：`SolidPodPreferencesProvider` 支持 OAuth2 客户端凭证（SOLID_CLIENT_ID/SOLID_CLIENT_SECRET），可选 SOLID_IDP 发现或 SOLID_TOKEN_URL；保留用户名/密码兼容，见 docs/zh/08-solid-self-hosted.md
6. ~~**Relay 传输（出站优先）**~~ ✅ 已实现（`relay/main.py`、`RelayClientTransport`、RFC-003）
7. ~~**多 NATS 集群联邦 或 DHT 发现后端**~~ ✅ 已实现（NATS 集群见 10-nats-cluster-federation + deploy/nats-cluster；DHT 见 DhtDiscoveryProvider、RFC-002）
8. ~~**可选：公共 DHT bootstrap 节点**~~ ✅ 已实现（环境变量 `OPEN_A2A_DHT_BOOTSTRAP`、`get_default_dht_bootstrap()`）
9. ~~**可选：Relay 端到端加密**~~ ✅ 已实现：Relay 服务端 TLS（wss，RELAY_WS_TLS/SSL_CERT/KEY）；负载 E2E 见 `EncryptedTransportAdapter`（open-a2a[e2e]），RFC-003 §6

---

## 后续工作建议（工程与生态）

> 注：以下为在当前 MVP 已完成基础上的「增强路线」，不影响现有功能使用。

1. **多运行时 / 多语言接入**
   - 在现有 Python SDK + Bridge 的基础上，优先提供至少一个 TypeScript/Node SDK 或简单 HTTP 客户端封装，方便 JS 生态的 Agent 直接接入 Open-A2A。
   - 为 OpenClaw / ZeroClaw 等运行时整理「官方推荐接入方式」和完整示例（Tool / Channel / Bridge 模式）。

2. **Discovery & Registry 的产品化**
   - 在 `DiscoveryProvider` + NATS/DHT 实现之上，抽象出一个更易用的「Agent 能力目录 / 注册中心」：
     - 提供简单的 HTTP API 或 Python 封装，用于注册/查询 Agent 能力；
     - 附带权限/可见性选项（公开、私有、仅联盟内可见等）。
   - 当前进展：
     - Bridge 已提供基础 HTTP API：`/api/register_capabilities`、`/api/discover`（基于 NATS Discovery 的请求-响应，无中心化注册表）。
     - 后续可在此基础上补充：权限/可见性策略、DHT 后端的同构 HTTP 接口、以及对 OpenClaw Skill 的一键接入。

3. **安全与运营 best practice 下沉为默认配置**
   - 将 `13-security-considerations.md` 中的建议逐步固化到默认配置与脚本中：
     - 提供开启账号/密码、NKEY、TLS 的示例配置与一键脚本；
     - 为公共节点运营者给出基础的限流、日志与监控示例。

4. **开发者体验与 Quick Start**
   - 在文档中新增一个极简「快速上手」路径：
     - 使用公共 NATS / Relay 节点，5 分钟跑通第一条 Intent → Offer；
     - 然后按层次引导到：本地起节点 / 集成运行时 / 使用 DID & 偏好 / Discovery。

5. **论文与标准化输出**
   - 基于 `research/open-a2a-paper-outline.md`，完成一版可投 Workshop/预印本的论文草稿：
     - 系统描述现有协议、实现与实验（包括当前 GCP 公共节点与跨 IP / Relay 测试）；
     - 明确 Open-A2A 在现有 MAS / MCP / Web3 工作中的定位与贡献。

## 跨 IP / 跨网络测试（必要验证）

- **前提**：算力便宜、每人都有自己的 Agent、各自网络部署 → 跨 IP 测试是**必要**的。
- **文档**：[12-cross-ip-testing.md](./12-cross-ip-testing.md)：双机 NATS 集群、公网+私网 Relay 出站，步骤与验证点。
- **建议**：至少完成「双机集群」与「Relay 出站」两类场景，再视需求做 DHT/多集群。

---

## CI / 自动化测试

- **GitHub Actions**：`.github/workflows/ci.yml`，在 push 到 main 及 PR 时运行
  - **Lint**：`ruff check open_a2a/ relay/ tests/`
  - **Test**：`pytest tests/`（Python 3.9、3.11 矩阵）
- **本地**：`make lint`、`make test`（需 `make install` 含 dev 依赖）
- **tests/**：最小冒烟测试（包导入、版本、Intent 序列化往返），无 NATS 依赖

---

## 多 Merchant 场景验证

- **目的**：验证同一意图被多个商家同时接收并各自回复报价，Consumer 能收集到多份报价。
- **自动化**：`make run-multi-merchant-demo`（需 NATS 已启动）。脚本启动 N 个 Merchant 进程（默认 3，可设 `MULTI_MERCHANT_N=5`），Consumer 发布一次意图，验证收到 ≥ N 个报价后退出。
- **手动**：终端 1–3 分别运行 `make run-merchant`、`make run-merchant-2`、`make run-merchant-3`，终端 4 运行 `make run-consumer`，应看到 3 个报价。
