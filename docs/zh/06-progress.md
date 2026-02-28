# 项目进度

> 最后更新：2026-02-28

## 总体状态

| 阶段 | 状态 | 说明 |
|------|------|------|
| **Phase 1: Hello Open-A2A** | ✅ 已完成 | 广播-响应流程已跑通并验证 |
| **Phase 2: 隐私与身份认证** | ⏳ 未开始 | DID + Solid Pod |
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
- Makefile：`venv`、`install`、`run-merchant`、`run-consumer`
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

- 新增 `make run-carrier`

---

## 提交历史

| 提交 | 说明 |
|------|------|
| `4bffee1` | feat: 实现 Phase 1 Hello Open-A2A 框架 |
| `ab543fd` | chore: 初始化项目，添加文档与规范 |

---

## 下一步计划

1. **Phase 2**：集成 `did:key` 与 Solid Pod
2. **集成研究**：调研 OpenClaw / ZeroClaw 的 Tool/Channel 扩展机制，设计 Open-A2A 适配层
3. **可选**：多 Merchant 场景测试、Docker Compose 编排、真实支付通道对接
