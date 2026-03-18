# Bridge Directory Registry（目录注册表，原 Path B）Operator 套件

> 目标：把 Bridge 的**目录注册表（Directory Registry，原 Path B）**（`/api/register_capabilities` + `/api/discover`）从“功能可用”推进到“运营可复制”。  
> 本目录提供两种推荐形态：**单机（落盘）**与 **HA（Redis 后端，多实例）**，并附带跨容器 E2E 自检脚本。

## 1. 形态选择（推荐）

- **单机（推荐起步）**：`docker-compose.directory-registry.single.yml`
  - 使用 `BRIDGE_DISCOVERY_PERSIST_PATH` 把注册表落盘到 volume
  - 适合：单节点、低成本、重启可恢复
- **HA（推荐公网/多实例）**：`docker-compose.directory-registry.ha.yml`
  - 使用 `BRIDGE_DISCOVERY_REDIS_URL` 作为注册表后端（多实例共享）
  - 适合：需要滚动升级、容灾、多个 Bridge 实例
  - 生产建议：在两个 Bridge 前面加反向代理/LB（本 compose 用不同端口演示）

## 1.1 最小安全默认值（公网建议）

- **强烈建议启用鉴权**：
  - `BRIDGE_DISCOVERY_REGISTER_TOKEN`
  - `BRIDGE_DISCOVERY_DISCOVER_TOKEN`
- **推荐启用 strict**：`OA2A_STRICT_SECURITY=1`
- **建议把 Bridge 放在 HTTPS 反代后**（nginx/Caddy/Traefik/云 LB），而不是直接裸跑公网 `:8080`

---

## 2. “照抄可跑”的操作指南

### 2.1 单机（落盘恢复）

目标：单实例 + 重启不丢目录。

```bash
export BRIDGE_DISCOVERY_REGISTER_TOKEN="change-me"
export BRIDGE_DISCOVERY_DISCOVER_TOKEN="change-me"

docker compose -f deploy/bridge-directory-registry/docker-compose.directory-registry.single.yml up -d --build
curl -sS http://127.0.0.1:8080/health | jq .
```

关键点：

- `BRIDGE_DISCOVERY_PERSIST_PATH=/data/bridge_registry.json` 已在 compose 内设置，并挂载了 volume
- 如果要“公开给互联网使用”，请把 `8080` 放到 HTTPS 反代后，并开启 strict + token

### 2.2 HA（Redis 后端 + 多实例）

目标：多实例共享目录，便于滚动升级/容灾。

```bash
export BRIDGE_DISCOVERY_REGISTER_TOKEN="change-me"
export BRIDGE_DISCOVERY_DISCOVER_TOKEN="change-me"

docker compose -f deploy/bridge-directory-registry/docker-compose.directory-registry.ha.yml up -d --build
curl -sS http://127.0.0.1:8081/health | jq .
curl -sS http://127.0.0.1:8082/health | jq .
```

生产建议：

- Redis 建议开启 AOF 或 RDB 持久化（本示例仅最小可用；生产请按你的 SRE 规范配置）
- Bridge 多实例前置 LB/反代对外暴露单一域名（例如 `https://bridge.open-a2a.org`）

---

## 3. 反向代理（HTTPS）要点（避免踩坑）

无论 nginx/Caddy/Traefik/云 LB，建议保证：

- **长连接/超时**：避免 proxy 默认超时把连接切断
- **保留真实来源 IP**（如需 IP 限流/审计）
- **限制 body 大小**：避免异常大包滥用（在反代层先拦一层）

本目录提供一个最小示例文件：

- `deploy/bridge-directory-registry/Caddyfile.example`

---

## 4. 常见故障排查（高频坑）

- **discover 为空**：
  - 先确认 provider 是否有定期续租（TTL 到期会过期）
  - 看 `GET /api/discovery_stats` 是否有 providers_total 变化
- **strict 模式启动失败**：
  - 缺 token / 仍是 `change-me-*` 占位符会被拒绝启动（这是预期行为）
- **多实例不一致**（HA）：
  - 确认两实例都指向同一 `BRIDGE_DISCOVERY_REDIS_URL`
  - 确认 Redis 可写/无权限问题

## 2. 一键 E2E 自检（跨容器）

在仓库根目录执行：

```bash
bash scripts/e2e/bridge-directory-registry.sh single-persist
bash scripts/e2e/bridge-directory-registry.sh redis-ha
```

若你的环境无法访问 Docker Hub（无法拉取 `nats` / `redis` 镜像），也可以复用你**已有在跑的 NATS/Redis** 来做验证：

```bash
export E2E_EXTERNAL_NATS_URL="nats://host.docker.internal:4222"
export E2E_EXTERNAL_REDIS_URL="redis://host.docker.internal:6379/0"  # 仅 redis-ha-external 需要

bash scripts/e2e/bridge-directory-registry.sh single-persist-external
bash scripts/e2e/bridge-directory-registry.sh redis-ha-external
```

自检覆盖：

- **single-persist**：注册 → discover → 重启 Bridge → discover 仍命中（验证落盘恢复）
- **redis-ha**：在 Bridge-1 注册，在 Bridge-2 discover 命中（验证多实例共享注册表）

## 3. 环境变量（脚本会自动注入）

脚本会为测试注入以下变量（你也可自行设置）：

- `BRIDGE_DISCOVERY_REGISTER_TOKEN`
- `BRIDGE_DISCOVERY_DISCOVER_TOKEN`
- `BRIDGE_DISCOVERY_DEFAULT_TTL_SECONDS`
- `BRIDGE_DISCOVERY_CLEANUP_INTERVAL_SECONDS`

## 4. 注意事项

- 本套件只关注 **目录注册表/持续可发现**（Directory Registry，原 Path B），不强制开启 OpenClaw 转发：
  - 若你不需要 OpenClaw webhook 转发，可设置 `BRIDGE_ENABLE_FORWARD=0`
- NATS 在此套件里默认保持 Docker 内网可达（不对公网暴露 `4222`）。

