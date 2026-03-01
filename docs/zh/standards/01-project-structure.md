# 项目结构与代码规范

## 1. 目录结构

```
Open-A2A/
├── .cursor/                    # Cursor IDE 配置
│   └── rules/                  # AI 协作规则（含虚拟环境规范）
├── docs/                       # 项目文档（中英镜像）
│   ├── zh/                     # 中文文档
│   │   ├── 00-design-principles.md ～ 11-relay-e2e-verify.md
│   │   ├── openclaw-tool-example.md
│   │   ├── reference/          # 参考资料
│   │   └── standards/          # 规范（本文件、git、documentation、contribution）
│   └── en/                     # 英文文档（与 zh 结构镜像）
│       ├── 00-design-principles.md ～ 09-deployment-and-openclaw-integration.md
│       ├── reference/
│       └── standards/
├── spec/                       # 核心协议规范（RFC 文档）
│   ├── rfc-001-intent-protocol.md
│   ├── rfc-002-discovery.md
│   └── rfc-003-relay-transport.md
├── open_a2a/                   # 协议参考实现（Python SDK）
│   ├── intent.py               # 消息模型
│   ├── broadcaster.py         # 意图广播（基于 TransportAdapter）
│   ├── transport.py            # 传输层抽象接口
│   ├── transport_nats.py       # NATS 传输适配器
│   ├── transport_relay.py      # Relay 传输适配器（出站连接）
│   ├── transport_encrypt.py    # 负载 E2E 加密包装（Relay）
│   ├── discovery.py            # Agent 发现抽象
│   ├── discovery_nats.py       # NATS 发现实现
│   ├── discovery_dht.py        # DHT 发现实现（跨网络）
│   ├── identity.py             # DID 身份（Phase 2）
│   ├── preferences.py          # 偏好存储（Phase 2，含 Solid OAuth2 客户端凭证）
│   ├── agent.py                # BaseAgent 基类
│   └── __init__.py
├── bridge/                     # Open-A2A Bridge（OpenClaw 适配层）
│   ├── __init__.py
│   └── main.py
├── relay/                      # Open-A2A Relay（WebSocket <-> NATS，出站优先）
│   ├── __init__.py
│   └── main.py
├── deploy/                     # 部署示例
│   └── nats-cluster/           # 两节点 NATS 集群（docker-compose、conf）
├── example/                    # 示例与 Demo
│   ├── consumer.py
│   ├── merchant.py
│   ├── carrier.py
│   ├── consumer_via_relay.py   # 经 Relay 出站
│   ├── discovery_demo.py       # NATS 发现示例
│   ├── discovery_dht_demo.py   # DHT 发现示例
│   ├── multi_merchant_demo.py   # 多 Merchant 场景验证
│   ├── relay_e2e_verify.py     # Relay 负载 E2E 验证
│   ├── profile.json            # 偏好示例（Phase 2）
│   └── upload_profile_to_solid.py
├── .venv/                      # 虚拟环境（不提交）
├── .gitignore
├── .env.example                # 环境变量模板
├── Makefile                    # venv, install, install-*, run-*
├── pyproject.toml
├── requirements.txt            # 可选，与 pyproject.toml 并存
├── Dockerfile.bridge
├── docker-compose.solid.yml
├── docker-compose.deploy.yml
├── LICENSE
├── NOTICE
└── README.md
```

### 1.1 各目录职责

| 目录 | 职责 | 说明 |
|------|------|------|
| `spec/` | 协议定义 | Agent 间握手、消息格式、语义字典等 RFC 文档 |
| `open_a2a/` | 参考实现 | 协议的 Python SDK，供其他项目引用 |
| `bridge/` | 适配层 | Open-A2A Bridge，连接 NATS 与 OpenClaw |
| `example/` | 示例代码 | Consumer、Merchant、Carrier 等 Demo |
| `docs/` | 项目文档 | 架构、需求、开发指南等；`zh/` 与 `en/` 镜像，各含 `standards/`、`reference/` |
| `relay/` | Relay 服务 | WebSocket↔NATS，出站优先，可选 TLS |
| `deploy/` | 部署示例 | NATS 集群等 |

---

## 2. 命名规范

### 2.1 文件命名

| 类型 | 规范 | 示例 |
|------|------|------|
| Python 模块 | 小写 + 下划线 | `intent_broadcaster.py` |
| Python 包 | 小写 | `core/` |
| 文档 | 小写 + 连字符 或 序号前缀 | `01-project-overview.md` |
| 协议文档 | RFC 编号 | `spec/rfc-001-intent-protocol.md` |

### 2.2 代码命名

| 类型 | 规范 | 示例 |
|------|------|------|
| 类名 | PascalCase | `IntentBroadcaster` |
| 函数/方法 | snake_case | `publish_intent()` |
| 常量 | UPPER_SNAKE_CASE | `DEFAULT_TOPIC_PREFIX` |
| 私有成员 | 前缀单下划线 | `_internal_method()` |

### 2.3 分支与提交

参见 [git.md](./git.md)。

---

## 3. 代码组织原则

### 3.1 模块化

- 每个模块职责单一，避免「上帝类」
- 通过接口/抽象类定义契约，便于测试和扩展
- 依赖注入优于硬编码依赖

### 3.2 可测试性

- 业务逻辑与 I/O（网络、存储）分离
- 核心逻辑应有单元测试
- 测试文件与源文件同目录或置于 `tests/`

### 3.3 配置与敏感信息

- 配置通过环境变量或配置文件加载
- 敏感信息（密钥、Token）不得提交到仓库
- 提供 `.env.example` 作为模板

---

## 4. 技术栈约定

- **语言**：Python 3.9+
- **包管理**：`pyproject.toml`（PEP 621），可选依赖 `[identity]`、`[solid]`、`[bridge]`、`[relay]`、`[dht]`、`[e2e]`、`[dev]`；根目录可保留 `requirements.txt` 以兼容 `pip install -r`
- **代码风格**：遵循 PEP 8，使用 `ruff` 格式化
- **类型注解**：鼓励使用类型提示（Type Hints）
- **虚拟环境**：所有 Python 操作使用 `.venv/bin/python`、`.venv/bin/pip` 或 `make` 目标，避免污染系统环境
