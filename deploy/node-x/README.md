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

