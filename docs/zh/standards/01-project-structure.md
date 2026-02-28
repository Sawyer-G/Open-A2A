# 项目结构与代码规范

## 1. 目录结构

```
Open-A2A/
├── .cursor/                    # Cursor IDE 配置
│   └── rules/                  # AI 协作规则
├── docs/                       # 项目文档
│   ├── zh/                     # 中文文档
│   ├── en/                     # 英文文档
│   └── ...
├── spec/                       # 核心协议规范（RFC 文档）
├── core/                       # 协议参考实现（Python SDK）
├── example/                    # 示例与 Demo
├── .gitignore
├── README.md
├── LICENSE
└── pyproject.toml              # 或 requirements.txt
```

### 1.1 各目录职责

| 目录 | 职责 | 说明 |
|------|------|------|
| `spec/` | 协议定义 | Agent 间握手、消息格式、语义字典等 RFC 文档 |
| `core/` | 参考实现 | 协议的 Python SDK，供其他项目引用 |
| `example/` | 示例代码 | Consumer、Merchant、Carrier 等 Demo |
| `docs/` | 项目文档 | 架构、需求、开发指南等（中英双语） |

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

- **语言**：Python 3.10+
- **包管理**：优先使用 `pyproject.toml`（Poetry 或 PEP 621）
- **代码风格**：遵循 PEP 8，使用 `ruff` 或 `black` 格式化
- **类型注解**：鼓励使用类型提示（Type Hints）
