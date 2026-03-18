# Node X Operator Kit (copy & run)

本目录提供一套“可直接复制”的节点 X（运营者节点）部署套件，目标是：

- 给普通用户一个**默认可用**的公共入口（Relay/Bridge）
- 让运营者能在不理解全部实现细节的情况下，快速、安全地跑起来
- 保持 Open-A2A 的定位：这是**协议/基础设施层**，不是业务平台

## 你将得到什么

- `docker-compose.node-x.yml`：运营节点的 Compose（NATS 内网、Relay/Bridge 可选公网）
- `nats.conf`：最小可用的 NATS 鉴权与权限模板（可按需加 TLS）
- `.env.node-x.example`：运营侧建议的环境变量模板
- `../../scripts/diagnose-node-x.sh`：一键自检脚本（端口、健康检查、NATS ping、Discovery 查询）

---

## 快速开始（Docker）

1) 复制环境变量模板并按需修改：

```bash
cp .env.node-x.example ../../.env
```

2) 编辑 NATS 配置并修改用户/密码（至少改 `agent_public` 的密码）：

```bash
vim nats.conf
```

3) 启动：

```bash
docker compose -f docker-compose.node-x.yml --env-file ../../.env up -d --build
```

4) 自检：

```bash
bash ../../scripts/diagnose-node-x.sh
```

---

## 安全建议（公网节点务必做）

Node X 往往会对公网开放 Relay（以及可选的 Bridge）。如果你希望“默认安全”而不是依赖人工检查，推荐：

1) **改掉所有 `change-me-*` 占位密码/Token**
- `.env` 里的 `NATS_RELAY_PASS`、`NATS_BRIDGE_PASS`（以及可选的 `NATS_PUBLIC_PASS`）
- `deploy/node-x/nats.conf` 里的对应密码（必须与 `.env` 一致）

2) **开启严格安全模式（fail-fast）**

在 `.env` 中设置：

```bash
OA2A_STRICT_SECURITY=1
```

效果：

- Relay/Bridge 启动时会做安全自检；发现明显不安全配置会直接拒绝启动
- `scripts/diagnose-node-x.sh` 在 strict 模式下也会对占位密码/缺鉴权等问题直接报错退出

3) **公网 Relay 建议开启鉴权**
- 设置 `RELAY_AUTH_TOKEN`，避免匿名滥用

4) **对外提供目录 discover 时建议启用鉴权**
- 设置 `BRIDGE_DISCOVERY_REGISTER_TOKEN` / `BRIDGE_DISCOVERY_DISCOVER_TOKEN`


## 端口与云防火墙（建议）

### 建议默认对公网开放

- `RELAY_WS_PORT`（默认 `8765`）：Agent 出站连接入口（推荐开放）
- `BRIDGE_PORT`（默认 `8080`）：HTTP 接入与运维诊断（可选开放；建议走 HTTPS 反代）

### 建议默认不对公网开放（仅内网/同机容器网络）

- NATS `4222`：建议保持内网，仅 Relay/Bridge 使用。若确需对外提供直连 NATS，再开放并启用更严格鉴权/ACL/TLS。

---

## 运行形态建议（运营者视角）

- **公共入口优先 Relay**：终端用户通常只需要出站连接 WS/WSS 即可接入，降低门槛。
- **Bridge 默认不转发到运营者 OpenClaw**：运营节点不应把全网意图转发到某个特定业务运行时。若运营者要把 Bridge 用作“目录/适配层”，建议 `BRIDGE_ENABLE_FORWARD=0`、`BRIDGE_ENABLE_DISCOVERY=1`。

---

## （可选）X↔Y 多运营者互联（federation / subject bridge）

如果你已经运营了节点 X，且希望与另一个运营者的节点 Y **只共享一部分主题**（建议默认只桥接 `intent.>`），可以启用本仓库的 `subject-bridge`（方式 2：独立 NATS + 只桥接部分 subject）。

### 你需要准备什么

- **节点 X（本套件）**：默认 NATS 为内网服务（容器网络内可访问 `nats:4222`）
- **节点 Y**：一个可访问的 NATS 地址（通常带鉴权），例如 `nats://<user>:<pass>@nats-y.example.org:4222`

> 注意：`subject-bridge` 需要在两侧都具备对所桥接 subject 的订阅/发布权限。建议为 federation 专门创建最小权限用户，而不是复用 `agent_public`。

### 启用方式（Docker Compose profile）

1) 在仓库根目录 `.env` 中设置至少两项：

- `OA2A_FED_NATS_B`：指向节点 Y 的 NATS
- （可选）`OA2A_FED_SUBJECTS`：桥接 allowlist，默认 `intent.>`

2) 启动时带上 `--profile federation`：

```bash
docker compose -f deploy/node-x/docker-compose.node-x.yml --env-file .env --profile federation up -d --build
```

### 观测

- **subject-bridge `/healthz`**：默认映射到本机 `127.0.0.1:9464`  
  你可以访问 `http://127.0.0.1:9464/healthz` 查看转发计数与丢弃原因（hop/self/dedupe/errors）。
- **NATS 监控端口**：若你在 NATS 配置中启用了 `http` 监控端口，可用于排查订阅/连接状态。

更多原理与推荐默认值请参考：

- `docs/zh/16-multi-operator-federation-subject-bridge.md`

