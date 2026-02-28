# Open-A2A

> 去中心化 Agent 间协作协议 —— 后互联网时代的 TCP/IP

[English](#english) | 简体中文

---

## 这是什么？

**Open-A2A**（Open Agent-to-Agent Network）是一套开源的、去中心化的 AI 智能体协作协议。我们定义规则，不卖软件。

当 AI 助手普及后，点外卖、约车、找服务不应再经过中心化平台。Open-A2A 让 **消费者 Agent**、**商家 Agent**、**配送 Agent** 直接对话，价值在参与者之间 100% 流动，没有中间商抽成。

## 为什么需要它？

| 现状 | Open-A2A 愿景 |
|------|---------------|
| 平台抽成 10%~30% | 零抽成，价值直达参与者 |
| 平台掌控数据、操纵选择 | 数据主权归个人，AI 只服务其主人 |
| 必须依赖中心化 App | Agent 间直连，遵循开放协议即可互通 |

## 核心能力（MVP：「一碗面条的旅程」）

- **全网发现**：Agent A 广播「我想吃面」，附近的商家 Agent 毫秒级响应
- **意图协商**：A 与 B 的 Agent 自动沟通忌口、价格、时间，用户只需说一句话
- **三方调度**：商家确认订单后，配送 Agent 自动接单，无需平台调度员
- **价值结算**：交付证明触发后，资金瞬间分配给商家和骑手，无平台扣费

## 架构概览

```
┌─────────────────────────────────────────────────────────┐
│  L3 意图协作层   │ 意图协议 RFC │ LLM 语义对齐 │ 原子结算  │
├─────────────────────────────────────────────────────────┤
│  L2 通信调度层   │ NATS 广播    │ Hypercore DHT │ Gossip   │
├─────────────────────────────────────────────────────────┤
│  L1 数字舱基础层 │ DID 身份     │ Solid Pod    │ Ollama   │
└─────────────────────────────────────────────────────────┘
```

## 项目结构

| 目录 | 说明 |
|------|------|
| [`spec/`](./spec) | 核心协议规范（RFC 文档） |
| [`core/`](./core) | 协议的 Python 参考实现（SDK） |
| [`example/`](./example) | 示例：Consumer、Merchant、Carrier Demo |
| [`docs/`](./docs) | 项目文档、架构、需求、开发指南 |

## 快速开始

> 项目处于早期开发阶段，协议与参考实现正在完善中。

**开发路线图**：

1. **Hello Open-A2A**：NATS 广播-响应（Consumer ↔ Merchant）
2. **隐私与身份**：DID + Solid Pod 集成
3. **全链路闭环**：A-B-C 三方 + 模拟结算

详见 [开发路线图](./docs/zh/04-roadmap.md) / [Roadmap](./docs/en/04-roadmap.md)。

## 文档 / Documentation

| 中文 | English |
|------|---------|
| [docs/zh/](./docs/zh/README.md) | [docs/en/](./docs/en/README.md) |

| 文档 | Document | 说明 |
|------|----------|------|
| [项目概览](./docs/zh/01-project-overview.md) | [Overview](./docs/en/01-project-overview.md) | 背景、愿景 / Background, vision |
| [产品需求](./docs/zh/02-requirements.md) | [Requirements](./docs/en/02-requirements.md) | 功能、用户故事 / Features, user story |
| [系统架构](./docs/zh/03-architecture.md) | [Architecture](./docs/en/03-architecture.md) | 三层网格、技术栈 / Three-tier mesh |
| [开发路线图](./docs/zh/04-roadmap.md) | [Roadmap](./docs/en/04-roadmap.md) | MVP 步骤 / MVP phases |
| [开发指南](./docs/zh/05-development-guide.md) | [Dev Guide](./docs/en/05-development-guide.md) | 资源栈、竞品 / Resources, competitors |
| [项目进度](./docs/zh/06-progress.md) | [Progress](./docs/en/06-progress.md) | 当前完成项 / Current status |

## 参与贡献 / Contributing

我们欢迎全球开源开发者、Web3 极客、研究者的参与。  
We welcome contributors worldwide—open source developers, Web3 enthusiasts, researchers.

- **贡献指南** / **Contribution**: [zh](./docs/zh/standards/03-contribution.md) | [en](./docs/en/standards/03-contribution.md)
- **项目规范** / **Standards**: [zh](./docs/zh/standards/) | [en](./docs/en/standards/)

## 技术栈

- **身份**：DID (did:key)、SpruceID、Solid Pod
- **通信**：NATS JetStream、libp2p、DIDComm
- **Agent**：MCP、Ollama、LangGraph
- **结算**：HTLC、闪电网络（或第三方支付 API 作为可插拔通道）

## License

待定。项目采用开源友好许可。

---

## English

**Open-A2A** is an open-source, decentralized protocol for AI Agent-to-Agent collaboration. We define the rules—no platform, no middleman.

When AI assistants become ubiquitous, ordering food, booking rides, and finding services should happen directly between Agents—without centralized platforms taking 10–30% of every transaction.

**Vision**: The Agentic Economy. Consumer Agent ↔ Merchant Agent ↔ Delivery Agent. Value flows 100% to participants.

**Status**: Early development. See [docs/en/](./docs/en/) for architecture, roadmap, and contribution guidelines.
