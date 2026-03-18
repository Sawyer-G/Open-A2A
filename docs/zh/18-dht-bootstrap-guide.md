# DHT Bootstrap（产品化指引）：跨节点 discover 的首选路径

> 适用场景：当节点 X 与节点 Y **各自独立 NATS**（不在同一集群/不桥接 discovery subject）时，你仍希望跨节点进行“目录式发现”。  
> 结论：**优先使用 DHT discovery**（`DhtDiscoveryProvider`），而不是在 subject-bridge 中桥接 `_INBOX.*`。

---

## 1. 为什么跨节点 discover 推荐用 DHT？

NATS Discovery（RFC-002）在同一个 NATS subject 空间内效果很好，但跨节点场景会遇到：

- query 在 A 节点发出，reply 往往发到 `_INBOX.*`；
- 如果你想让 B 节点的 provider 响应 A 的 query，需要桥接 query subject + reply subject；
- 这通常意味着要桥接 `_INBOX.*`，会带来**放大消息量与环路风险**。

因此在“多运营者、各自独立 NATS”的网络里：

> **跨节点 discover 推荐走 DHT**（Kademlia），把能力索引写入去中心化哈希表，天然跨网络。

---

## 2. 如何配置 `OPEN_A2A_DHT_BOOTSTRAP`

环境变量：`OPEN_A2A_DHT_BOOTSTRAP`

格式：

```text
host1:port1,host2:port2
```

示例：

```bash
export OPEN_A2A_DHT_BOOTSTRAP="1.2.3.4:8469,bootstrap.example.org:8469"
```

代码位置：`open_a2a/discovery_dht.py`（`ENV_DHT_BOOTSTRAP = "OPEN_A2A_DHT_BOOTSTRAP"`）。

---

## 3. “社区 bootstrap 列表”（占位）

当前仓库内置的 `DEFAULT_DHT_BOOTSTRAP` 还是空列表（占位）：  
`open_a2a/discovery_dht.py` → `DEFAULT_DHT_BOOTSTRAP = []`

你可以选择两种方式：

1) **自建 bootstrap（推荐运营者）**
- 在一台公网服务器上运行一个 DHT 节点（端口例如 `8469/udp+tcp`，视实现而定）
- 将该地址作为 `OPEN_A2A_DHT_BOOTSTRAP` 提供给网络参与者

2) **使用社区 bootstrap（未来）**
- 当项目提供公共 bootstrap 节点后，会将其填入 `DEFAULT_DHT_BOOTSTRAP` 或在本文档列出

---

## 4. 最小可复制的运行方式（开发验证）

仓库自带 demo：`example/discovery_dht_demo.py`  
它会在单进程内启动两个 DHT 节点互相 bootstrap，用于验证“注册/发现”逻辑。

```bash
make install-dht
make run-discovery-dht-demo
```

---

## 5. 运营建议（避免踩坑）

- bootstrap 节点应长期在线（像“入口 DNS”一样），否则新节点加入困难
- bootstrap 列表至少 2 个节点更稳健（避免单点）
- DHT 只提供“发现索引”，并不替代传输层；发现后仍需通过 NATS/Relay/HTTP 等 endpoint 实际通信
- **目录质量**：DHT 不会自动删除旧记录，建议所有注册方按 TTL 周期**定期续租**（重复 register 即可刷新过期时间）
  - 参考：`example/dht_discovery_renew.py`（`make run-dht-discovery-renew`）

