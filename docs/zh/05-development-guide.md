# 开发指南

## 1. 分步开发资源手册 (Resource Stack)

按分层架构，建议按以下顺序集成资源：

### Step 1: 基础信任层 (DID & Auth)

| 工具 | 说明 | 状态 |
|------|------|------|
| [didlite](https://github.com/jondepalma/didlite-pkg) | 轻量 Python `did:key` + JWS 签名，零依赖膨胀 | ✅ 已集成（`pip install open-a2a[identity]`） |
| [SSI-SDK](https://github.com/TalaoLabs/ssi-sdk) | 轻量级自建身份 SDK，支持生成 `did:key` | 备选 |
| [SpruceID (DIDKit)](https://github.com/spruceed/didkit) | 工业级 DID 和 VC 处理工具，支持 Rust/Python/Node | 备选 |
| [Veramo](https://veramo.io/) | TypeScript 模块化 DID 框架 | 备选 |

### Step 2: 数据主权层 (Solid Pod)

| 工具 | 说明 | 状态 |
|------|------|------|
| `FilePreferencesProvider` | 基于 JSON 的偏好存储，见 `open_a2a/preferences.py` | ✅ 已实现 |
| `SolidPodPreferencesProvider` | 从自托管 Solid Pod 读写偏好（**推荐**），`pip install open-a2a[solid]` | ✅ 已实现 |
| [solid-file](https://github.com/twonote/solid-file-python) | Python Solid Pod 客户端，支持 Node Solid Server | ✅ 已集成 |
| [deploy/solid/docker-compose.solid.yml](../deploy/solid/docker-compose.solid.yml) | 自托管 Solid 一键部署 | ✅ 已提供 |
| [08-solid-self-hosted.md](./08-solid-self-hosted.md) | 自托管 Solid 配置指南 | 必读 |

### Step 3: 能力执行层 (Agent 运行时)

Open-A2A **不实现** Agent 推理能力，建议与成熟运行时集成：

| 项目 | 说明 | 与 Open-A2A 的集成点 |
|------|------|---------------------|
| **Open-A2A Bridge** | `bridge/main.py`，FastAPI 服务 | ✅ 已实现，`make install-bridge && make run-bridge`，见 [09-deployment-and-openclaw-integration.md](./09-deployment-and-openclaw-integration.md) |
| [OpenClaw](https://github.com/openclaw/openclaw) | 个人 AI 助手，多通道（WhatsApp、Telegram 等），TypeScript | 通过 Bridge 作为 Tool 或 Channel 接入 |
| [ZeroClaw](https://github.com/zeroclaw-labs/zeroclaw) | 轻量 Rust 运行时（<5MB RAM），Trait 驱动 | 可插拔 Provider/Channel 实现 Open-A2A |
| [Ollama](https://ollama.com/) | 本地 LLM 推理 | 作为 Agent 的模型底座 |
| [MCP](https://modelcontextprotocol.io/) | 模型上下文协议 | 工具暴露、语义握手 |

### Step 4: 传输层抽象 (Transport Layer)

| 组件 | 说明 | 状态 |
|------|------|------|
| `TransportAdapter` | 抽象接口：`connect`、`disconnect`、`publish`、`subscribe` | ✅ 已实现（`open_a2a/transport.py`） |
| `NatsTransportAdapter` | NATS 参考实现 | ✅ 已实现（`open_a2a/transport_nats.py`） |
| `IntentBroadcaster` | 支持 `transport` 参数注入，默认 NATS | ✅ 已实现 |

**用法**：`IntentBroadcaster(nats_url=...)` 保持向后兼容；自定义传输可 `IntentBroadcaster(transport=MyTransportAdapter())`。未来可扩展 HTTP、WebSocket、DHT、P2P 等适配器。

### Step 5: 交互协作层 (A2A & P2P)

| 工具 | 说明 |
|------|------|
| [DIDComm-Python](https://github.com/sicpa-dcl/didcomm-python) | Agent 间加密通信首选库 |
| [libp2p (py-libp2p)](https://github.com/libp2p/py-libp2p) | P2P 发现与 NAT 穿透 |

---

## 2. 架构优化建议 (2026 视角)

### 2.1 引入「意图内存网格 (Intent Mesh)」

**痛点**：Agent A 如何知道全球哪个 Agent 能提供服务？

**优化**：引入 **Dequier (去中心化查询层)**。Agent 将加密的「意图」广播到本地节点，由具备该能力的 Agent 主动握手，而非 Agent 满世界去找人。

### 2.2 采用「流式微支付 (Streaming Micropayments)」

**痛点**：先付钱还是先给数据？

**优化**：在交互层引入 **Lightning Network (闪电网络)** 或 **Farcaster Frame** 逻辑。Agent 间协作按 Token 或按秒计费，每完成一轮对话自动支付 $0.0001，将违约风险降至最低。

---

## 3. 与 Agent 运行时的集成

### 3.1 集成架构

```
用户 / 商户 / 骑手
        │
        ▼
┌─────────────────────────────────────┐
│  OpenClaw / ZeroClaw（Agent 运行时）  │
│  - 自然语言理解、决策、工具调用        │
│  - 可插拔：Open-A2A Tool / Channel   │
└─────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────┐
│  Open-A2A 协议层                     │
│  - RFC-001 意图/报价格式             │
│  - NATS 主题、发布/订阅               │
└─────────────────────────────────────┘
```

### 3.2 集成方式

| 方式 | 说明 |
|------|------|
| **Tool** | 封装为 Agent 可调用的工具，用户说「想吃面」→ 工具发布意图并返回报价 |
| **Channel** | 类似 OpenClaw 的 WhatsApp 通道，Agent 订阅 Open-A2A 主题并响应 |
| **Bridge** | 适配层连接 Open-A2A SDK 与 Agent 运行时，运行时无需关心 NATS |

### 3.3 竞品与替代方案分析

| 方案 | 核心差异点 | 对 Open-A2A 的启示 |
|------|------------|---------------------|
| [Olas (Autonolas)](https://olas.network/) | 强调「多智能体共识」，多个 Agent 共同决策并签名，适合金融等高安全场景 | 协作涉及资产时，参考其「服务注册（Registry）」机制 |
| [Morpheus](https://mor.org/) | 侧重「算力去中心化」，类似去中心化操作系统，用户支付代币调动全球 Agent | 其智能体接口标准（Smart Agent Protocol）值得参考 |
| [Fetch.ai (Almanac)](https://fetch.ai/) | 解决「Agent 目录」问题，有类似电话本的合约，Agent 可注册地址和能力 | 框架需要类似的「去中心化索引」来解决交互寻址 |

---

## 4. 多语言 SDK 规划

当前 Open-A2A 仅提供 Python 参考实现。当项目成熟、有非 Python 技术栈的接入需求时，可考虑提供 TypeScript、Go、Java 等多语言 SDK。

**形式说明**：协议（RFC）与语言无关；多语言 SDK 是同一协议的不同实现，用于扩大采用范围。参考 [Google A2A](https://github.com/a2aproject/A2A) 的 Python、JS、Java、Go、.NET 等多语言实现。

**详细规划**：见 [07-multi-language-sdk.md](./07-multi-language-sdk.md)，包括：
- 为何需要多语言、何时考虑
- 语言优先级、仓库组织、核心能力清单
- 维护考量与参考资源
