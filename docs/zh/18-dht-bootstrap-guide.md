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

## 3. “社区 bootstrap 列表”（可用默认 + 可覆盖）

当前仓库已内置一个**可用默认**的 `DEFAULT_DHT_BOOTSTRAP`（方便“开箱即用”加入同一 DHT 网）：  
`open_a2a/discovery_dht.py` → `DEFAULT_DHT_BOOTSTRAP = [("dht.open-a2a.org", 8469), ...]`

> 运营建议：生产环境仍建议你显式设置 `OPEN_A2A_DHT_BOOTSTRAP`（便于替换/扩容/容灾），而不是长期依赖代码内置默认。

你可以选择两种方式：

1) **自建 bootstrap（推荐运营者）**
- 在一台公网服务器上运行一个 DHT 节点（端口例如 `8469/udp+tcp`，视实现而定）
- 将该地址作为 `OPEN_A2A_DHT_BOOTSTRAP` 提供给网络参与者

2) **使用社区 bootstrap（未来）**
- 当前仓库已提供可复制的 bootstrap 套件：`deploy/dht-bootstrap/`
- 社区列表与治理流程见：`docs/zh/19-dht-community-bootstraps.md`

---

## 4. 最小可复制的运行方式（开发验证）

仓库自带 demo：`example/discovery_dht_demo.py`  
它会在单进程内启动两个 DHT 节点互相 bootstrap，用于验证“注册/发现”逻辑。

```bash
make install-dht
make run-discovery-dht-demo
```

### 4.1 使用 Docker 在本机做一次“外网 bootstrap 可用性”验证（推荐）

> 目的：验证你的 DHT bootstrap（例如 `dht.open-a2a.org:8469`）在**外网环境**下可加入、可写入、可读出。  
> 该验证不依赖本机 Python 环境，直接在 Docker 容器里安装 `open-a2a[dht]` 后运行。

前置：

- 本机已安装 Docker
- 你要验证的 bootstrap 已对公网开放端口（建议 **UDP 8469**，可选 TCP 8469）

在仓库根目录执行（会启动两个临时 DHT 节点 A/B，都 bootstrap 到同一个公网入口；A 写入，B 读出）：

```bash
## 方式 1：使用脚本（推荐）
bash scripts/e2e-dht-bootstrap.sh dht.open-a2a.org:8469

## 方式 2：手动 docker run（等价）
docker run --rm -t -v "$PWD:/repo" -w /repo python:3.12-slim bash -lc \
  "python -m pip install -q --no-cache-dir -e '.[dht]' && python - <<'PY'
import asyncio
from open_a2a.discovery_dht import DhtDiscoveryProvider

BOOT = [('dht.open-a2a.org', 8469)]
CAP = 'intent.food.order'

async def main():
  a = DhtDiscoveryProvider(dht_port=18468, bootstrap_nodes=BOOT)
  b = DhtDiscoveryProvider(dht_port=18469, bootstrap_nodes=BOOT)
  await a.connect()
  await b.connect()
  try:
    meta = {'agent_id':'local-e2e-a','capabilities':[CAP],'endpoints':[]}
    await a.register(CAP, meta)
    await asyncio.sleep(1.0)
    res = await b.discover(CAP, timeout_seconds=2.0)
    print('discover_count', len(res))
    hit = [x for x in res if isinstance(x, dict) and x.get('agent_id')=='local-e2e-a']
    print('hit', bool(hit))
    if hit:
      print('hit_meta', hit[0])
    else:
      print('sample', res[:3])
  finally:
    await a.disconnect()
    await b.disconnect()

asyncio.run(main())
PY"
```

预期输出包含：

- `discover_count` 大于 0
- `hit True`

提示：

- 运行过程中可能出现类似 `Did not receive reply ...` 的日志（kademlia 路由探测/节点不可达的噪声），不一定代表失败；以最后的 `hit True` 为准。

---

## 5. 运营建议（避免踩坑）

- bootstrap 节点应长期在线（像“入口 DNS”一样），否则新节点加入困难
- bootstrap 列表至少 2 个节点更稳健（避免单点）
- DHT 只提供“发现索引”，并不替代传输层；发现后仍需通过 NATS/Relay/HTTP 等 endpoint 实际通信
- **目录质量**：DHT 不会自动删除旧记录，建议所有注册方按 TTL 周期**定期续租**（重复 register 即可刷新过期时间）
  - 参考：`example/dht_discovery_renew.py`（`make run-dht-discovery-renew`）

