# 节点 X（运营节点）一键部署套件：可复制配置清单

> 适用对象：希望运营“公共入口节点”的个人/团队/社区。  
> 目标：在不偏离 Open-A2A「协议层」定位的前提下，提供一套**可直接复制**、可运维的部署产物。

本指南对应仓库内的运营套件：`deploy/node-x/`。

---

## 1. 你要运营的“节点 X”是什么？

节点 X 是一个公共基础设施入口，主要职责是：

- 提供一个共享的主题空间（NATS）
- 提供一个更易接入的出站入口（Relay：WS/WSS）
-（可选）提供 HTTP 适配与目录能力（Bridge：/health、register/discover 等）

**节点 X 不应该默认绑定任何具体业务运行时**（例如把全网 intent 转发到运营者自己的 OpenClaw）。这会偏离协议层定位。

---

## 2. 端口与云防火墙清单（必须明确）

### 2.1 建议默认对公网开放

- **Relay**：`8765/tcp`（`RELAY_WS_PORT`）  
  终端用户只要能出站连接 WS/WSS，就可以加入网络。

- **Bridge（可选）**：`8080/tcp`（`BRIDGE_PORT`）  
  如果你希望对外提供：
  - `/health` 运维自检
  - `/api/register_capabilities`、`/api/discover` 目录注册表（Directory Registry，原 Path B）
  
  则可以开放该端口，但**强烈建议放在 HTTPS 反代后**（并加限流/鉴权）。

### 2.2 建议默认不对公网开放

- **NATS**：`4222/tcp`  
  默认只给 Relay/Bridge 在同机容器网络内使用。  
  若你要提供“高级用户直连 NATS”，再考虑开放 4222，并启用更严格的鉴权/ACL/TLS。

---

## 3. 可直接复制的部署产物（仓库内）

目录：`deploy/node-x/`

- `docker-compose.node-x.yml`
  - 默认 **不映射** NATS 4222 到宿主机（避免意外公网暴露）
  - 映射 Relay 8765、Bridge 8080（可按需关闭/改端口）
  - 统一使用固定网络名 `open-a2a`，便于诊断

- `nats.conf`
  - 最小 NATS 鉴权与权限模板（users + permissions）
  - 你必须改密码（至少改 `agent_public`）

- `.env.node-x.example`
  - 一份可复制的运营侧 `.env` 模板

- `scripts/diagnose-node-x.sh`
  - 端口检查 + Bridge /health + 通过 `nats-box` 容器做 NATS ping + discover 查询

---

## 4. 一键部署步骤（复制即可）

在仓库根目录执行：

```bash
cp deploy/node-x/.env.node-x.example .env
# 编辑 deploy/node-x/nats.conf 并修改密码（至少改 agent_public）
docker compose -f deploy/node-x/docker-compose.node-x.yml --env-file .env up -d --build
bash scripts/diagnose-node-x.sh
```

你需要做的唯一“必须修改”是：

- 在 `deploy/node-x/nats.conf` 和 `.env` 中把密码改掉，并保持一致
- 把 `.env` 里的 `BRIDGE_META_JSON.endpoint` 改成你的公网域名/IP（如果你对外开放 Bridge）

---

## 5. 推荐的运营默认值（避免偏离项目初衷）

如果你是“公共入口节点”，推荐：

- `BRIDGE_ENABLE_FORWARD=0`（不把全网 intent 转发到某个 OpenClaw）
- `BRIDGE_ENABLE_DISCOVERY=1`（对外提供 register/discover 的目录能力）
- 对外主入口是 Relay（终端用户接入门槛最低）
- （推荐）开启严格安全模式：`OA2A_STRICT_SECURITY=1`（检测到明显不安全配置会拒绝启动）

如果你是“自用节点（你自己跑 OpenClaw）”，才推荐：

- `BRIDGE_ENABLE_FORWARD=1`
- 配置 `OPENCLAW_GATEWAY_URL`、`OPENCLAW_HOOKS_TOKEN`

---

## 5.1（推荐）对外提供“可验真的目录 meta”（RFC-004）

如果你对外提供目录式 discover（`/api/register_capabilities`、`/api/discover`），建议在 Bridge 侧开启 **meta proof**：

- 其他节点拿到你的 `meta` 后，可以验证签名，确认这份 meta 确实由该 `did:key` 的私钥持有者生成；
- 这不等于“信用体系”，只是“可验真”能力，信任策略仍由对方节点自行决定。

在 `.env` 中（可选）开启：

```bash
BRIDGE_ENABLE_META_PROOF=1
BRIDGE_PUBLIC_URL=https://bridge.open-a2a.org
# 生产建议固定 DID（避免重启身份变化），并妥善保管 seed：
BRIDGE_DID_SEED_B64=BASE64_SEED
```

协议细节见：`spec/rfc-004-identity-and-trust.md`。

---

## 5.2（推荐）目录质量与运营控制：TTL / 鉴权 / 限流 / 观测

如果节点 X 对外提供目录式 discover，建议同时启用以下“运营级能力”：

- **TTL/过期回收**：防止僵尸注册长期占用目录。注册方需周期性续租（再次调用 `POST /api/register_capabilities`）。
- **访问控制（可选）**：为 register/discover 设置 Bearer Token，避免被任意人滥用。
- **速率限制（可选）**：按 IP 限流，降低 DoS 风险。
- **观测**：使用 `GET /api/discovery_stats` 查看 provider 数量、capability 分布与错误信息。

对应环境变量见 `.env.example` 或 `deploy/node-x/.env.node-x.example`。

### 5.2.1（推荐）多实例/HA：使用 Redis 作为目录注册表后端

如果你希望 Bridge 以多副本方式运行（或希望目录状态由共享存储持久化），推荐启用 Redis 后端：

- 设置 `BRIDGE_DISCOVERY_REDIS_URL=redis://redis:6379/0`
- 该模式下目录注册表与 capability 索引会写入 Redis，适用于多实例一致性
- 单实例场景仍可使用 `BRIDGE_DISCOVERY_PERSIST_PATH`（文件持久化）作为轻量选择

## 6. 运营者后续增强（不在本套件强制）

这套 Node X kit 刻意保持“最小可用”，后续常见增强包括：

- Relay / Bridge 前置反代（HTTPS、WAF、限流、鉴权）
- NATS TLS、账户隔离、更细粒度的 subject ACL
- 观测：指标、日志集中、告警
  - Bridge：`GET /ops/metrics`（JSON，目录后端/在线 provider/capability 分布等）
  - Relay：`http://{RELAY_HTTP_HOST}:{RELAY_HTTP_PORT}/healthz`（JSON，连接数/订阅数等，建议仅内网）
- 多运营者互联（X↔Y）：选择性桥接主题（如 `intent.food.*`）

