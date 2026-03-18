# RFC-002: Agent 发现 (Discovery)

> 版本：0.1.0-draft | 状态：草稿

## 1. 概述

本协议定义 Open-A2A 网络中 **Agent 发现** 的语义与主题约定，服务于「跨网络 Agent 通信」中的「如何发现彼此」。与 RFC-001 意图协议配合：发现解决「谁在、谁能响应」，意图协议解决「如何交互」。

## 2. 目标

- **能力注册**：Agent 可声明自己支持的能力（如订阅 `intent.food.order`）。
- **能力查询**：任意方可查询「谁支持某能力」，用于路由、网关或跨集群发现。
- **传输无关**：发现接口可基于不同实现（NATS 请求-响应、DHT、全局索引等）。

## 3. 主题约定（NATS 参考实现）

| 主题 | 方向 | 说明 |
|------|------|------|
| `open_a2a.discovery.query.{capability}` | 查询方 → 已注册方 | 发现请求；payload 含 `reply_to`，响应方应向 `reply_to` 回复 |

**capability** 与意图主题对应，例如：`intent.food.order`、`intent.logistics.request`。

### 3.1 请求格式

查询方发布到 `open_a2a.discovery.query.{capability}`：

```json
{ "reply_to": "_INBOX.open_a2a.<unique>" }
```

### 3.2 响应格式

已注册的 Agent 向 `reply_to` 发布任意 JSON 元数据，例如：

```json
{
  "agent_id": "merchant-001",
  "capability": "intent.food.order",
  "endpoint": "nats://node1:4222"
}
```

为了跨实现互操作，推荐 discovery 的响应 meta 至少包含 RFC-004 定义的最小字段集合：

- `agent_id`
- `did`
- `endpoints`
- `capabilities`
- `proof`

实现方与调用方仍可扩展 meta 字段，但应避免破坏签名验证（见 RFC-004 的 canonical JSON 与 meta proof 规则）。

## 4. 跨服务器扩展

- **同 NATS / NATS 集群**：`NatsDiscoveryProvider` 即可；所有节点共享同一主题空间。NATS 集群配置见 [10-nats-cluster-federation.md](../docs/zh/10-nats-cluster-federation.md)。
- **多 NATS 集群**：通过 NATS 集群路由/联邦共享主题；或使用 DHT 发现（见下）。
- **DHT/DPI**：已实现 `DhtDiscoveryProvider`（`open_a2a/discovery_dht.py`），基于 Kademlia DHT；能力注册/发现写入 DHT，与 NATS 无关，供跨网络、跨集群发现。需 `pip install open-a2a[dht]`。

## 5. 参考实现

- `open_a2a/discovery.py`：`DiscoveryProvider` 抽象
- `open_a2a/discovery_nats.py`：`NatsDiscoveryProvider`（请求-响应，同 NATS/集群）
- `open_a2a/discovery_dht.py`：`DhtDiscoveryProvider`（Kademlia DHT，跨网络）
- `example/discovery_demo.py`：NATS 发现示例
- `example/discovery_dht_demo.py`：DHT 发现示例（`make run-discovery-dht-demo`）
- 身份与信任（meta 最小字段与 proof）：`spec/rfc-004-identity-and-trust.md`
