# 多运营者互联（方式 2）：独立 NATS + 只桥接部分主题（最小可用实现）

> 本文解决一个“运营者真的配得出来”的问题：  
> **节点 X 与节点 Y 各自运行独立 NATS**，但希望只同步部分 subject（如 `intent.food.*`），形成可控的数据边界与网状互联。

---

## 1. 什么时候用方式 2？

当你希望：

- 每个运营者保留自己的 NATS（自治、数据边界清晰）
- 只共享一部分主题给其他运营者（例如只共享“意图/报价”，不共享偏好/内部控制主题）

你就应该使用“方式 2：独立 NATS + 主题桥接”。

---

## 2. 最小可用实现（本仓库已提供）

本仓库提供了一个轻量的 **Subject Bridge**：

- 同时连接 NATS A 与 NATS B
- 按 allowlist 订阅指定 subject
- 双向转发消息（A→B、B→A）
- 内置环路/风暴保护（header + hop + 去重）
- 周期性输出统计日志，便于观测

对应文件：

- 实现：`federation/subject_bridge.py`
- 容器镜像：`Dockerfile.federation-bridge`
- 示例（两套独立 NATS + bridge）：`deploy/federation/x-y/`

---

## 3. 桥接哪些 subject（默认建议）

### 3.1 最小推荐 allowlist（建议默认）

- `intent.>`  
  这是跨节点协作最核心的事件流（Intent/Offer/Confirm/Logistics 等）。

### 3.2 进阶：按 domain 精细化共享（更符合“数据边界”）

例如只共享外卖相关：

- `intent.food.>`
- `intent.logistics.>`

### 3.3 关于 Discovery（谨慎）

你可能会想桥接：

- `open_a2a.discovery.query.>`

但需要理解一个现实点：NATS Discovery 的 reply 通常发到 `_INBOX.*`。  
如果要实现“跨节点 discover”，还需要额外桥接对应的 reply subject（这会引入更大的风险与复杂度）。

**推荐做法**：

- 跨节点“目录式发现”优先用 DHT 后端（`DhtDiscoveryProvider`）；
- 方式 2 的 subject bridge 优先用于“事件流互通”（intent/offer）。

---

## 4. 如何避免环路/风暴（必须做）

在多运营者网络里，最常见的事故是“桥接器互相转发导致风暴”。本实现提供三层最小保护：

1) **自发消息跳过**：如果消息 headers 带 `X-OA2A-Bridge=<bridge_id>`，说明它来自本桥转发，不再转回去。
2) **Hop 限制**：使用 `X-OA2A-Hop` 递增，超过 `OA2A_FED_MAX_HOPS` 直接丢弃（默认 1）。
3) **去重 TTL**：对最近消息做哈希去重（默认 3 秒），抑制误配导致的反复转发。

运营建议：

- 同一对节点（X↔Y）尽量只跑**一个**桥接器；
- 不要“多桥并行”或“X↔Y↔Z↔X 环”直接上生产；
- 若要网状互联（多节点），建议先限定共享主题范围，再逐步扩展。

---

## 5. 观测（指标/日志）

### 5.1 Bridge 自身统计日志

`subject-bridge` 默认每 10 秒输出一行：

- `a->b` / `b->a`：转发数量
- `skip_self`：跳过本桥已转发消息
- `skip_hop`：超过 hop 限制被丢弃
- `skip_dedupe`：命中去重被丢弃
- `errors`：发布失败/异常计数

### 5.2 NATS 监控端口

建议开启 NATS `http` 监控端口（示例已启用）：

- `http://<node-x>:8222/`
- `http://<node-y>:8222/`

它能提供连接数、订阅数、route/gateway/leaf 等运行态信息（方便排查“订阅是否生效”“转发是否异常增长”）。

---

## 6. 直接可复制的示例（本机）

```bash
docker compose -f deploy/federation/x-y/docker-compose.yml up -d --build
```

默认桥接 allowlist：`intent.>`。

你可以通过环境变量调整为更精细化共享，例如：

```bash
OA2A_FED_SUBJECTS=intent.food.>,intent.logistics.>
```

---

## 7. 配置参考（环境变量）

| 变量 | 说明 | 默认 |
|---|---|---|
| `OA2A_FED_NATS_A` | NATS A URL | `nats://nats-x:4222` |
| `OA2A_FED_NATS_B` | NATS B URL | `nats://nats-y:4222` |
| `OA2A_FED_SUBJECTS` | 允许桥接的 subject（逗号分隔） | `intent.>` |
| `OA2A_FED_BRIDGE_ID` | bridge 身份标识 | `x-y-bridge` |
| `OA2A_FED_MAX_HOPS` | 最大 hop | `1` |
| `OA2A_FED_DEDUPE_TTL_SECONDS` | 去重 TTL | `3` |
| `OA2A_FED_STATS_INTERVAL_SECONDS` | 统计间隔 | `10` |
| `OA2A_FED_LOG_FORWARD_SAMPLES` | 是否打印每条转发样例 | `0` |

