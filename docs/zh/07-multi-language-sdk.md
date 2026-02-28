# 多语言 SDK 规划指南

> 本文档记录「协议 + 多语言参考实现」的形式，供项目成熟后扩展时参考。

---

## 1. 什么是多语言 SDK？

**协议**（如 RFC-001）定义的是消息格式、主题规范、交互逻辑，与具体编程语言无关。  
**SDK**（Software Development Kit）是协议的**具体实现**，让开发者用某种语言调用协议能力。

**多语言 SDK**：同一套协议，提供多种语言的实现（Python、TypeScript、Go、Java 等），使不同技术栈的开发者都能接入。

---

## 2. 为什么需要多语言 SDK？

| 原因 | 说明 |
|------|------|
| **技术栈差异** | 不同团队/公司使用不同语言：Web 用 TypeScript，企业用 Java，云原生用 Go，AI 研究用 Python |
| **降低接入成本** | 若只有 Python SDK，TypeScript 开发者需自己实现或通过 FFI 调用，门槛高 |
| **扩大采用范围** | 协议要成为「通用标准」，需覆盖主流生态，多语言是常见做法 |
| **参考案例** | [Google A2A](https://github.com/a2aproject/A2A) 提供 Python、JavaScript、Java、Go、.NET 等 SDK |

---

## 3. 当前 Open-A2A 的状态

| 项目 | 状态 |
|------|------|
| **协议规范** | RFC-001 已定义，与语言无关 |
| **参考实现** | 仅 Python（`open_a2a/`），作为首版验证 |
| **多语言** | 未实现，待项目成熟后考虑 |

**选择 Python 作为首版的原因**：快速验证、AI 生态契合、开发成本低。这是**阶段性选择**，非协议本身限制。

---

## 4. 未来扩展时的实现要点

### 4.1 协议优先（Protocol First）

- **规范即真相**：`spec/` 下的 RFC 是唯一权威，各语言 SDK 必须符合
- **不依赖实现**：协议用 JSON 等通用格式，不依赖某语言的特性
- **测试一致性**：可考虑跨语言一致性测试（如相同输入产生相同语义的消息）

### 4.2 语言优先级建议

| 优先级 | 语言 | 典型场景 | 说明 |
|--------|------|----------|------|
| 1 | Python | 已实现 | 当前参考实现 |
| 2 | TypeScript/JavaScript | Web、Node.js、OpenClaw 等 | 与现有 Agent 生态集成 |
| 3 | Go | 云原生、高性能服务 | NATS 官方客户端为 Go |
| 4 | Java | 企业后端、Android | 企业采用 |
| 5 | Rust | 边缘、高性能 | 可选，与 ZeroClaw 等契合 |

实际顺序可根据**社区需求**和**贡献者能力**调整。

### 4.3 仓库组织方式

**方案 A：单仓库多目录**

```
open-a2a/
├── spec/           # 协议规范（共享）
├── python/         # open_a2a（或 sdk-python）
├── typescript/     # sdk-ts 或 @open-a2a/sdk
├── go/             # sdk-go
└── ...
```

**方案 B：多仓库（参考 Google A2A）**

```
open-a2a/spec          # 协议规范
open-a2a/open-a2a-py  # Python SDK
open-a2a/open-a2a-ts  # TypeScript SDK
open-a2a/open-a2a-go  # Go SDK
...
```

多仓库便于独立发布、独立版本号，但需维护跨仓库的 CI 与发布流程。

### 4.4 各语言 SDK 需实现的核心能力

| 能力 | 说明 |
|------|------|
| 消息模型 | Intent、Offer、OrderConfirm、LogisticsRequest、LogisticsAccept 等数据类 |
| Broadcaster | 连接 NATS、发布/订阅、`publish_and_collect` 等模式 |
| Identity（可选） | `did:key` 生成、JWS 签名/验签 |
| Preferences（可选） | 偏好存储抽象 |

### 4.5 维护考量

- **人力**：每增加一种语言，需有人维护、修 bug、跟进协议变更
- **一致性**：协议更新时，各语言 SDK 需同步更新
- **测试**：可考虑协议级测试套件，各语言实现跑同一套用例
- **文档**：各 SDK 的 API 文档、示例需维护

---

## 5. 何时考虑多语言？

| 信号 | 说明 |
|------|------|
| 有非 Python 技术栈的团队希望接入 | 明确需求出现 |
| 协议稳定，RFC 变更频率降低 | 避免多语言同步成本过高 |
| 有社区贡献者愿意维护某语言实现 | 可持续维护 |
| 与 OpenClaw、ZeroClaw 等集成时需 TypeScript/Rust | 生态驱动 |

---

## 6. 参考资源

- [Google A2A 多语言 SDK](https://github.com/a2aproject/A2A)：Python、JS、Java、Go、.NET
- [MCP 多语言实现](https://modelcontextprotocol.io/)：协议规范 + 各语言实现
- [NATS 客户端](https://nats.io/download/)：官方提供 Go、Java、Python、Node 等

---

## 7. 小结

- 协议与实现分离：协议是规范，多语言 SDK 是不同实现
- 当前 Open-A2A 以 Python 参考实现为主，多语言为**未来扩展选项**
- 扩展时遵循「协议优先」、按需求排优先级、考虑维护成本
- 本文档供项目成熟后决策与实施时参考
