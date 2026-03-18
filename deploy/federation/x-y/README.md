# X↔Y 多运营者互联（独立 NATS + 只桥接部分主题）

> 目标：让运营者能“配得出来”方式 2：各自独立 NATS，但只同步部分 subject（更符合数据边界与网状结构）。

本目录是一个**最小可用**的参考实现：

- 两套独立 NATS：`nats-x` 与 `nats-y`
- 一个 subject bridge：同时连接两边 NATS，并按 allowlist 将消息双向转发

## 快速启动（本机 Docker）

在仓库根目录执行：

```bash
docker compose -f deploy/federation/x-y/docker-compose.yml up -d --build
docker ps
```

你会得到：

- `nats-x`：客户端端口映射到宿主机 `4222`；监控端口 `8222`
- `nats-y`：客户端端口映射到宿主机 `5222`；监控端口 `9222`
- `subject-bridge`：连接两边并桥接 subject（默认 `intent.>`）

## 默认桥接哪些 subject（建议）

最小推荐 allowlist：

- `intent.>`：意图/报价/确认等事件流（跨节点协作的核心）

可选（谨慎）：

- `open_a2a.discovery.query.>`：跨节点“查询能力”  
  但注意 NATS Discovery 的 reply 通常发到 `_INBOX.*`，要实现完整跨节点发现，需要额外桥接 inbox（风险较高）。更推荐跨节点发现用 DHT。

## 如何避免环路/风暴

本 bridge 内置三层保护：

1) **自发消息跳过**：若消息 headers 带 `X-OA2A-Bridge=<bridge_id>`，说明是本桥转发过来的，不再转回去。
2) **Hop 限制**：`X-OA2A-Hop` 递增，超过 `OA2A_FED_MAX_HOPS` 直接丢弃（默认 1）。
3) **去重（TTL）**：对最近消息做哈希去重（默认 3 秒），抑制误配导致的反复转发。

> 运营建议：同一对节点之间尽量只跑**一个**桥接器；避免并行多桥造成拓扑环路。

## 观测（指标/日志）

- **Bridge 日志**：`subject-bridge` 每 10 秒输出一行统计：
  - `a->b / b->a` 转发计数
  - `skip_self / skip_hop / skip_dedupe / errors`
- **Bridge 运维端点（HTTP JSON，可选）**：
  - 默认监听：`http://127.0.0.1:9464/healthz`（可通过 `OA2A_FED_HTTP_*` 配置）
- **NATS 监控端口**（本示例已启用）：
  - X：`http://localhost:8222/`（连接数、订阅数等）
  - Y：`http://localhost:9222/`

## 配置项（环境变量）

| 变量 | 说明 | 默认 |
|---|---|---|
| `OA2A_FED_NATS_A` | NATS A URL | `nats://nats-x:4222` |
| `OA2A_FED_NATS_B` | NATS B URL | `nats://nats-y:4222` |
| `OA2A_FED_SUBJECTS` | 允许桥接的 subject（逗号分隔） | `intent.>` |
| `OA2A_FED_BRIDGE_ID` | bridge 身份标识（用于环路防护） | `x-y-bridge` |
| `OA2A_FED_MAX_HOPS` | 最大转发跳数 | `1` |
| `OA2A_FED_DEDUPE_TTL_SECONDS` | 去重 TTL（秒） | `3` |
| `OA2A_FED_STATS_INTERVAL_SECONDS` | 统计输出间隔（秒） | `10` |
| `OA2A_FED_LOG_FORWARD_SAMPLES` | 输出每条转发样例日志 | `0` |

