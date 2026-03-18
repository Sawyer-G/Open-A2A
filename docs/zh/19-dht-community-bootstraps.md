# DHT 社区 Bootstrap：列表与治理流程

> 目标：让跨节点 discover 的 DHT 路径从“技术可用”变成“用户可接入”。  
> Bootstrap 仅用于加入同一张 Kademlia DHT 网（发现索引入口），**不提供信任背书**（信任见 RFC-004）。

---

## 1. 社区 Bootstrap 列表（暂行）

当前你有两种选择：

1) **使用社区 Bootstrap（推荐，接入门槛最低）**  
2) **自建 Bootstrap（适合运营者/企业内部网络）**

> 说明：在我们正式提供公共域名节点前，仓库先提供“可复制的 bootstrap 套件 + 贡献流程”。当社区节点上线后，本列表会更新为真实可用地址。

### 1.1 在线节点（可用）

- **`dht.open-a2a.org:8469`**
  - **协议**：TCP + UDP
  - **维护者**：Open-A2A（Sawyer）
  - **上线**：2026-03-18
  - **备注**：用于加入 Open-A2A 社区 DHT overlay（不提供信任背书）

> 冗余目标（P0）：社区列表至少应长期在线 **2 个** bootstrap（不同主机/不同运营者更佳），避免单点。
> 当前仍缺第 2 个入口，欢迎社区按下文流程贡献。

---

## 2. 如何运行一个 Bootstrap 节点（复制即用）

仓库提供了可复制套件：`deploy/dht-bootstrap/`

在仓库根目录执行：

```bash
docker compose -f deploy/dht-bootstrap/docker-compose.yml up -d --build
```

你需要在云防火墙/安全组开放（同时 TCP + UDP）：

- `DHT_PORT`（默认 `8469`）

可选：你也可以把多个 bootstrap 节点“链式加入同一张网”（用于扩容与冗余）：

```bash
export DHT_BOOTSTRAP="seed-1.example.org:8469,seed-2.example.org:8469"
docker compose -f deploy/dht-bootstrap/docker-compose.yml up -d --build
```

---

## 3. 如何把你的节点加入社区列表（治理）

请通过 PR 提交以下信息到本文件：

- **域名或公网 IP**：例如 `seed-1.example.org`
- **端口**：推荐 `8469`
- **区域**（可选）：例如 `ap-southeast-1`
- **维护者**（可选）：用于故障通知（邮箱/社媒/issue）

我们建议的最小准入标准：

- 节点长期在线（至少 95% uptime）
- 端口对外可达（TCP/UDP）
- 允许被其他节点 bootstrap
- 与现有节点“可互相 bootstrap”（建议：节点 A 启动时设置 `DHT_BOOTSTRAP=<现有入口>`，确保加入同一张 overlay）

建议的最小健康验证（上线前自测）：

- 从你本机跑一次 “join + write + read” 验证（见 `docs/zh/18-dht-bootstrap-guide.md` 的 Docker 验证步骤）

---

## 4. 下线/替换规则（暂行）

- 若连续不可达超过 24 小时，可从列表移除或标记为 `inactive`
- 维护者可提交 PR 主动下线/迁移地址

