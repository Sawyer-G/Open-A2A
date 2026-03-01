# Open-A2A

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![GitHub](https://img.shields.io/badge/GitHub-Open--A2A-181717?logo=github)](https://github.com/Sawyer-G/Open-A2A)

> 去中心化 Agent 间协作协议 —— 后互联网时代的 TCP/IP

[English](#english) | 简体中文

---

## 目录

- [项目定位](#项目定位)
- [这是什么？](#这是什么)
- [为什么需要它？](#为什么需要它)
- [核心能力](#核心能力示例一碗面条的旅程)
- [架构概览](#架构概览)
- [项目结构](#项目结构)
- [快速开始](#快速开始)
- [开发路线图](#开发路线图)
- [文档](#文档)
- [参与贡献](#参与贡献)
- [技术栈](#技术栈)
- [License](#license)

---

## 项目定位

**Open-A2A** 做的是**协议层与底层架构**，不是具体业务：定义 Agent 间如何通信（消息结构、主题、交互模式），不定义买什么、送什么。送餐是**示例场景**，用于验证协议。

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

## 核心能力（示例：「一碗面条的旅程」）

- **全网发现**：Agent A 广播「我想吃面」，附近的商家 Agent 毫秒级响应
- **意图协商**：A 与 B 的 Agent 自动沟通忌口、价格、时间，用户只需说一句话
- **三方调度**：商家确认订单后，配送 Agent 自动接单，无需平台调度员
- **价值结算**：交付证明触发后，资金瞬间分配给商家和骑手，无平台扣费

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│  L3 意图协作层   │ 意图协议 RFC │ LLM 语义对齐 │ 原子结算     │
├─────────────────────────────────────────────────────────────┤
│  L2 通信调度层   │ 传输层抽象   │ NATS / DHT   │ Gossip       │
├─────────────────────────────────────────────────────────────┤
│  L1 数字舱基础层 │ DID 身份     │ Solid Pod    │ Agent 运行时 │
└─────────────────────────────────────────────────────────────┘
```

## 项目结构

| 目录 | 说明 |
|------|------|
| [`spec/`](./spec) | 核心协议规范（RFC 文档） |
| [`open_a2a/`](./open_a2a) | 协议的 Python 参考实现（SDK） |
| [`example/`](./example) | 示例：Consumer、Merchant、Carrier Demo |
| [`bridge/`](./bridge) | OpenClaw 等 Agent 运行时的适配层 |
| [`docs/`](./docs) | 项目文档、架构、需求、开发指南 |

## 快速开始

> 所有 Python 操作请在虚拟环境中执行（`.venv/bin/python` 或 `make`），避免污染系统环境。

**1. 启动 NATS**

```bash
docker run -p 4222:4222 nats:latest
```

**2. 安装并运行示例**

```bash
make venv && make install
# 或 make install-full   # 含 identity、dev 依赖
```

在三个终端分别运行：

```bash
make run-merchant    # 终端 1
make run-carrier    # 终端 2
make run-consumer   # 终端 3
```

**3. 与 OpenClaw 集成**

```bash
make install-bridge && make run-bridge
```

详见 [部署与 OpenClaw 集成](./docs/zh/09-deployment-and-openclaw-integration.md)。

## 开发路线图

| 阶段 | 状态 |
|------|------|
| Hello Open-A2A（NATS 广播-响应） | ✅ 已完成 |
| 隐私与身份（did:key + 偏好存储） | ✅ 已完成 |
| 全链路闭环（A-B-C + 模拟结算） | ✅ 已完成 |
| 传输层抽象（TransportAdapter） | ✅ 已完成 |
| Open-A2A Bridge（OpenClaw 适配） | ✅ 已完成 |

详见 [开发路线图](./docs/zh/04-roadmap.md) / [Roadmap](./docs/en/04-roadmap.md)、[项目进度](./docs/zh/06-progress.md)。

## 文档

| 文档 | 中文 | English |
|------|------|---------|
| 项目概览 | [01-project-overview](./docs/zh/01-project-overview.md) | [Overview](./docs/en/01-project-overview.md) |
| 产品需求 | [02-requirements](./docs/zh/02-requirements.md) | [Requirements](./docs/en/02-requirements.md) |
| 系统架构 | [03-architecture](./docs/zh/03-architecture.md) | [Architecture](./docs/en/03-architecture.md) |
| 开发路线图 | [04-roadmap](./docs/zh/04-roadmap.md) | [Roadmap](./docs/en/04-roadmap.md) |
| 开发指南 | [05-development-guide](./docs/zh/05-development-guide.md) | [Dev Guide](./docs/en/05-development-guide.md) |
| 项目进度 | [06-progress](./docs/zh/06-progress.md) | [Progress](./docs/en/06-progress.md) |

**文档入口**：[docs/zh/](./docs/zh/README.md) | [docs/en/](./docs/en/README.md)

## 参与贡献

我们欢迎全球开源开发者、Web3 极客、研究者的参与。

- **贡献指南**：[中文](./docs/zh/standards/03-contribution.md) \| [English](./docs/en/standards/03-contribution.md)
- **项目规范**：[中文](./docs/zh/standards/) \| [English](./docs/en/standards/)

## 技术栈

| 层级 | 技术 |
|------|------|
| 身份与数据 | DID (did:key) [didlite](https://github.com/jondepalma/didlite-pkg)，偏好存储：profile.json 或自托管 Solid Pod |
| 通信 | 传输层抽象（NATS 参考实现），可扩展 HTTP/WebSocket/DHT；libp2p、DIDComm |
| Agent 运行时 | MCP、Ollama、OpenClaw / ZeroClaw（通过 Bridge 接入） |
| 结算 | 可插拔（模拟 / HTLC / 闪电网络 / 第三方 API） |

## License

[Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0)。详见 [LICENSE](./LICENSE) 与 [NOTICE](./NOTICE)。

---

<a name="english"></a>

## English

**Open-A2A** is an open-source, decentralized protocol for AI Agent-to-Agent collaboration. We define the rules—no platform, no middleman.

**Positioning**: Protocol and transport layer—we define how Agents communicate (message format, topics, interaction patterns), not business semantics. The “food delivery” scenario is an example to validate the protocol.

**Vision**: The Agentic Economy. Consumer Agent ↔ Merchant Agent ↔ Delivery Agent. Value flows 100% to participants.

**Status**: Phase 1–3 done; transport abstraction and OpenClaw Bridge implemented. See [docs/en/](./docs/en/) for architecture, roadmap, and contribution guidelines.
