# DHT 社区 Bootstrap：列表与治理流程

> 目标：让跨节点 discover 的 DHT 路径从“技术可用”变成“用户可接入”。  
> Bootstrap 仅用于加入同一张 Kademlia DHT 网（发现索引入口），**不提供信任背书**（信任见 RFC-004）。

---

## 1. 社区 Bootstrap 列表（暂行）

当前你有两种选择：

1) **使用社区 Bootstrap（推荐，接入门槛最低）**  
2) **自建 Bootstrap（适合运营者/企业内部网络）**

> 说明：在我们正式提供公共域名节点前，仓库先提供“可复制的 bootstrap 套件 + 贡献流程”。当社区节点上线后，本列表会更新为真实可用地址。

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

---

## 4. 下线/替换规则（暂行）

- 若连续不可达超过 24 小时，可从列表移除或标记为 `inactive`
- 维护者可提交 PR 主动下线/迁移地址

