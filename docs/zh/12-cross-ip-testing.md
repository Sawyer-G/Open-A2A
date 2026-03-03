# 跨 IP 测试指南

> 前提：算力便宜、硬件成本低，**每个人都有自己的 AI Agent**，且 Agent 部署在**各自网络**（家庭、办公室、不同运营商/地区）。因此跨 IP、跨网络的验证是**必要**的，而非可选。

---

## 1. 为什么跨 IP 测试是必要的

| 前提 | 含义 |
|------|------|
| 每人都有自己的 Agent | 消费者、商家、配送方等角色对应不同的人/主体，各自运行自己的 Agent |
| 各自网络部署 | 每个 Agent 在不同机器、不同公网 IP 或私网（NAT 后）下运行 |
| 框架目标 | 让这些分散在不同网络中的 Agent 能发现彼此、互通意图与报价 |

若只在单机或同一 NATS 内验证，无法保证「真实分布」下的连通性。**跨 IP 测试**用于验证：在不同 IP、不同网络下的 Agent 能否正确发现、通信并完成意图→报价→确认→委托的闭环。

---

## 2. 推荐的两类跨 IP 场景

### 场景一：双机 NATS 集群（两台不同公网 IP 的服务器）

**拓扑**：两人各自有一台有公网 IP 的机器（如两台 VPS），各自跑一个 NATS 节点并组成集群；一方跑 Merchant，另一方跑 Consumer，通过集群共享主题空间互通。

```
┌─────────────────────────────┐     ┌─────────────────────────────┐
│  服务器 A (公网 IP_A)        │     │  服务器 B (公网 IP_B)        │
│  - NATS 节点 A :4222,:6222   │◄───►│  - NATS 节点 B :4222,:6222   │
│  - Merchant (连 localhost)   │     │  - Consumer (连 localhost)   │
└─────────────────────────────┘     └─────────────────────────────┘
           集群路由 6222 互通
```

**验证目标**：B 上的 Consumer 发布意图后，能收到 A 上的 Merchant 的报价。

---

### 场景二：公网 + 私网（Relay 出站）

**拓扑**：一方在公网（如 VPS）跑 NATS + Relay + Merchant；另一方在家庭/公司内网（无公网 IP，或不想暴露端口），只跑 Consumer，通过 **Relay WebSocket 出站** 连到公网 Relay，参与同一 NATS 主题空间。

```
┌─────────────────────────────────────────┐     ┌─────────────────────────┐
│  服务器 A (公网 IP_A)                    │     │  用户 B (家庭/内网)      │
│  - NATS :4222                            │     │  - 无公网 IP / 仅出站    │
│  - Relay :8765 (ws://IP_A:8765)         │◄───►│  - Consumer             │
│  - Merchant (连 NATS)                    │     │    RELAY_WS_URL=ws://.. │
└─────────────────────────────────────────┘     └─────────────────────────┘
```

**验证目标**：B 的 Consumer 只通过出站连接 `ws://IP_A:8765`，即可发布意图并收到 A 上 Merchant 的报价。

---

## 3. 场景一：双机 NATS 集群 — 操作步骤

### 3.1 准备

- **服务器 A**、**服务器 B**：两台不同公网 IP 的机器（如两台 VPS），已安装 Docker 与 Python 3.9+，且彼此能访问对方**集群端口**（见下）。
- 防火墙：每台机开放 **4222**（NATS 客户端）、**6222**（NATS 集群路由）。若只从本机跑 Agent，可只对另一台服务器放行 6222。

### 3.2 服务器 A

1. 创建 NATS 配置（将 `IP_B` 替换为 B 的公网 IP 或域名）：

```conf
# deploy/nats-cluster/nats-a.conf（多机版）
port: 4222
cluster {
  name: opena2a
  listen: 0.0.0.0:6222
  routes: [
    nats://IP_B:6222
  ]
}
```

2. 启动 NATS（任选一种）：

```bash
# 方式 1：Docker
docker run -d --name nats-a -p 4222:4222 -p 6222:6222 \
  -v $(pwd)/nats-a.conf:/config/nats.conf \
  nats:latest -c /config/nats.conf

# 方式 2：若用项目 deploy 目录，先改 nats-a.conf 中 routes 为 nats://IP_B:6222，再：
# docker compose -f deploy/nats-cluster/docker-compose.yml up -d  # 需改为多机时 B 用 IP_B
```

3. 克隆项目并跑 Merchant（连本机 NATS）：

```bash
git clone https://github.com/Sawyer-G/Open-A2A.git && cd Open-A2A
make venv && make install
export NATS_URL=nats://127.0.0.1:4222
make run-merchant
```

保持 Merchant 运行。

### 3.3 服务器 B

1. 创建 NATS 配置（将 `IP_A` 替换为 A 的公网 IP 或域名）：

```conf
# nats-b.conf（多机版）
port: 4222
cluster {
  name: opena2a
  listen: 0.0.0.0:6222
  routes: [
    nats://IP_A:6222
  ]
}
```

2. 启动 NATS：

```bash
docker run -d --name nats-b -p 4222:4222 -p 6222:6222 \
  -v $(pwd)/nats-b.conf:/config/nats.conf \
  nats:latest -c /config/nats.conf
```

3. 跑 Consumer（连本机 NATS，集群会与 A 同步主题）：

```bash
cd Open-A2A
make venv && make install
export NATS_URL=nats://127.0.0.1:4222
make run-consumer
```

### 3.4 验证

- 在 B 上应看到 Consumer 发布意图后，收到来自 A 上 Merchant 的报价。
- 若收不到：检查 A/B 间 6222 是否互通（`telnet IP_A 6222` / `telnet IP_B 6222`）、防火墙、`routes` 中的 IP 是否写对。

---

## 4. 场景二：公网 + 私网（Relay 出站）— 操作步骤

### 4.1 服务器 A（公网，提供 NATS + Relay + Merchant）

1. 启动 NATS：

```bash
docker run -d -p 4222:4222 nats:latest
```

2. 启动 Relay（需先 `make install-relay`）：

```bash
cd Open-A2A
make venv && make install-relay
export NATS_URL=nats://127.0.0.1:4222
make run-relay
```

Relay 默认监听 `0.0.0.0:8765`，确保防火墙放行 **8765**（WebSocket）。

3. 另开终端，跑 Merchant：

```bash
export NATS_URL=nats://127.0.0.1:4222
make run-merchant
```

### 4.2 用户 B（家庭/内网，仅出站）

- 只需能访问 A 的公网 IP 和 8765 端口（出站即可，无需 B 有公网 IP 或入站端口）。

在 B 的机器上：

```bash
cd Open-A2A
make venv && make install-relay
export RELAY_WS_URL=ws://IP_A:8765
python example/consumer_via_relay.py
```

（将 `IP_A` 换成 A 的公网 IP 或域名。）

### 4.3 验证

- B 的 Consumer 经 Relay 发布意图后，应收到 A 上 Merchant 的报价。
- 说明：B 侧无需 NATS、无需公网 IP，仅通过出站 WebSocket 即可参与，符合「每个人在自己网络下部署」的前提。

---

## 5. 可选：DHT 发现跨网

若双方**不在同一 NATS 集群**（例如两个完全独立的网络、两个不同组织的 NATS），可先用 **DHT 发现** 找到对方，再通过 Relay 或其它通道互通。DHT 发现的使用见 [06-progress.md](./06-progress.md) 的「DHT 发现后端」与 `make run-discovery-dht-demo`；跨集群场景下 DHT + Relay 的组合可在此基础上扩展。

---

## 6. 小结

| 场景 | 适用 | 验证点 |
|------|------|--------|
| **双机 NATS 集群** | 两人各有公网服务器 | 不同 IP 的 Agent 通过共享 NATS 主题空间互通 |
| **公网 + 私网 Relay** | 一方公网、一方在家/内网 | 无公网 IP 的 Agent 经 Relay 出站即可参与 |
| **DHT + Relay** | 多集群/异构网络 | 发现与连通性（见文档与示例） |

在「算力便宜 + 每人都有自己的 Agent + 各自网络部署」的前提下，**跨 IP 测试是验证框架能否达成目标的必要步骤**；建议至少完成场景一与场景二，再视需求做 DHT/多集群验证。

---

## 7. 复杂网络与动态 IP：对普通用户意味着什么？

现实中，绝大多数人的 Agent 会运行在「复杂、受限、动态」的网络环境中：

- 家用 WiFi / 4G / 5G，**在运营商 NAT 后面**，没有固定公网 IP；
- 公司局域网，只有少数服务器有公网入口，大部分机器只能**出站访问**；
- 设备可能频繁切换网络（家里 WiFi、手机热点、公司 VPN 等）。

在这种前提下，Open-A2A 的设计思路是：

- **普通用户不需要在路由器上手动开放端口。**
  - 他们的个人 Agent 只需要「能出站访问某个公共入口」，例如某个 Relay 的 WebSocket 地址、某个公共 NATS / Bridge。
  - 这对应本指南中的「公网 + 私网 Relay」场景：家用/移动设备只通过 `ws://IP_A:8765` 出站连接，即可参与网络。
- **稳定 IP/端口的责任交给少数基础设施节点。**
  - 例如：由社区/服务商提供一批长期运行的 NATS 节点、Relay 节点、DHT bootstrap 节点，这些节点有固定域名/IP，并在防火墙中开放必要端口（4222、8765 等）。
  - 普通用户的 Agent 只需要知道这些「入口地址」，像连公网 API 一样连过去即可。
- **DHT 与发现负责「在复杂网络下找到对方」。**
  - 即使不同参与方使用的是不同 NATS 集群或传输方式，只要通过 DHT / 发现协议在「逻辑网络」中互相注册和查询，就可以在上层达成协作，而不需要每个人都在自己的路由器上做端口映射。

因此：

- 本文档中要求「开放 4222 / 6222 / 8765」的是**那些愿意承担公共基础设施角色的节点运营者**（例如你现在的 GCP 实例），而不是每一个最终使用框架的个人。
- 对于普通用户而言，更典型的接入方式是：
  - 在本地或个人服务器上运行 Agent；
  - 通过出站连接（NATS URL、Relay WebSocket、Bridge HTTP 等）加入到某个已有的 Open-A2A 网络中；
  - 无需在自家 WiFi / 移动网络上手工开放端口。

这正是 Open-A2A 试图解决的问题之一：在「每个人都有自己的 Agent、网络环境复杂多变」的现实下，通过**少量稳定节点 + 标准协议**，让所有 Agent 仍然可以在一张开放网络中协作。
