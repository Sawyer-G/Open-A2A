# NATS 集群与联邦

> 使多台服务器共享同一主题空间，实现「跨服务器」发现与意图互通。Agent 只需连接集群中任意节点即可。

---

## 1. 为什么需要集群

| 场景 | 单 NATS | NATS 集群 |
|------|---------|-----------|
| 部署 | 一台服务器一个 NATS | 多台服务器组成一个逻辑 NATS |
| 发现 | 仅同机/同进程 | 所有连到集群的 Agent 可互相发现 |
| 意图/报价 | 仅同 NATS 内 | 集群内任意节点发布的主题，全集群可见 |

Open-A2A 的发现（`open_a2a.discovery.query.*`）与意图主题（`intent.food.*` 等）都基于 NATS 主题。**只要多台服务器上的 NATS 组成一个集群**，部署在不同服务器上的 Agent 即可互相发现、互通消息，无需改业务代码。

---

## 2. 集群配置要点

- **客户端端口**：默认 `4222`，Agent 连接此端口。
- **集群路由端口**：用于服务器间同步（如 `6222`），各节点需配置 `listen` 与 `routes`。
- **全 mesh**：建议每台服务器在 `routes` 中列出**其他所有节点**（或至少能连通的节点），形成全连接，避免消息只在一跳内转发。

### 2.1 两节点示例（同机）

**节点 A**（`nats-a.conf`）：

```conf
port: 4222
cluster {
  name: opena2a
  listen: 0.0.0.0:6222
  routes: [
    nats://127.0.0.1:6223
  ]
}
```

**节点 B**（`nats-b.conf`）：

```conf
port: 4223
cluster {
  name: opena2a
  listen: 0.0.0.0:6223
  routes: [
    nats://127.0.0.1:6222
  ]
}
```

- Agent 连 `nats://localhost:4222` 或 `nats://localhost:4223` 均可，主题在集群内共享。
- Relay、Bridge 的 `NATS_URL` 指向任一方即可。

### 2.2 多机部署

将 `routes` 中的地址改为**其他服务器的 IP 或域名 + 集群端口**，例如：

- 服务器 1：`listen: 0.0.0.0:6222`，`routes: [ nats://server2:6222, nats://server3:6222 ]`
- 服务器 2：`listen: 0.0.0.0:6222`，`routes: [ nats://server1:6222, nats://server3:6222 ]`
- 服务器 3：同上，列出 server1、server2

每台服务器开放**客户端端口 4222**（供 Agent/Relay 连接）和**集群端口 6222**（供其他 NATS 节点连接）。防火墙需放行集群端口。

---

## 3. Docker Compose 示例（两节点集群）

```yaml
# docker-compose.nats-cluster.yml
services:
  nats-a:
    image: nats:latest
    command: ["-c", "/config/nats.conf"]
    volumes:
      - ./nats-a.conf:/config/nats.conf
    ports:
      - "4222:4222"
      - "6222:6222"
    networks:
      - nats-net

  nats-b:
    image: nats:latest
    command: ["-c", "/config/nats.conf"]
    volumes:
      - ./nats-b.conf:/config/nats.conf
    ports:
      - "4223:4222"
      - "6223:6222"
    networks:
      - nats-net
    depends_on:
      - nats-a

networks:
  nats-net:
    driver: bridge
```

将上面两段 `nats-a.conf` / `nats-b.conf` 分别存为文件，其中节点 B 的 `routes` 可写为 `nats://nats-a:6222`（Docker 服务名）。

---

## 4. 与 Open-A2A 的关系

- **发现**：`NatsDiscoveryProvider` 与 `IntentBroadcaster` 无需修改；只要 `NATS_URL` 指向集群内任一台，即可发现集群内所有已注册的 Agent，并收发意图/报价。
- **Relay**：Relay 的 `NATS_URL` 指向集群内任一台，经 Relay 出站连接的 Agent 与直连 NATS 的 Agent 同在集群内互通。
- **跨集群 / 异构网络**：若需「不同 NATS 集群」或「无 NATS 一方」互通，需依赖 **DHT 发现后端** 或 NATS 联邦（见 [RFC-002](../spec/rfc-002-discovery.md)、[06-progress](./06-progress.md)）。

### 4.1 当每个人都运行自己的节点时会发生什么？

在实际网络中，很多参与者会各自运行一套 **NATS / Relay / Bridge**：

- 如果大家都连接到**同一个 NATS 集群**，则共享一个逻辑主题空间 —— 在这个集群中，Intent / Offer 等主题对所有节点可见；
- 如果各自运行**彼此独立的 NATS** 且不做联邦，那么就是多个互不相连的网络，发现与意图广播只在各自网络内部生效；
- 如果配置了 **联邦或应用层 Bridge（例如 Bridge↔Bridge 的 HTTP 转发）**，则只有被选中的主题（如 `intent.food.*`）会在网络之间传播。

这意味着 Open-A2A 鼓励的是「多运营者节点组成的网状结构」，而非单一中心。每个运营者可以自行决定哪些主题对外共享、哪些只在本地网络内使用。

---

## 5. 参考

- [NATS Clustering 官方文档](https://docs.nats.io/running-a-nats-service/configuration/clustering/cluster_config)
- 项目进度与发现扩展： [06-progress.md](./06-progress.md)
