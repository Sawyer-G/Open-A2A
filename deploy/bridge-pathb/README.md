# Bridge Path B（目录注册表）Operator 套件

> 目标：把 Bridge 的 Path B（`/api/register_capabilities` + `/api/discover`）从“功能可用”推进到“运营可复制”。  
> 本目录提供两种推荐形态：**单机（落盘）**与 **HA（Redis 后端，多实例）**，并附带跨容器 E2E 自检脚本。

## 1. 形态选择（推荐）

- **单机（推荐起步）**：`docker-compose.pathb.single.yml`
  - 使用 `BRIDGE_DISCOVERY_PERSIST_PATH` 把注册表落盘到 volume
  - 适合：单节点、低成本、重启可恢复
- **HA（推荐公网/多实例）**：`docker-compose.pathb.ha.yml`
  - 使用 `BRIDGE_DISCOVERY_REDIS_URL` 作为注册表后端（多实例共享）
  - 适合：需要滚动升级、容灾、多个 Bridge 实例
  - 生产建议：在两个 Bridge 前面加反向代理/LB（本 compose 用不同端口演示）

## 2. 一键 E2E 自检（跨容器）

在仓库根目录执行：

```bash
bash scripts/e2e-bridge-pathb.sh single-persist
bash scripts/e2e-bridge-pathb.sh redis-ha
```

若你的环境无法访问 Docker Hub（无法拉取 `nats` / `redis` 镜像），也可以复用你**已有在跑的 NATS/Redis** 来做验证：

```bash
export E2E_EXTERNAL_NATS_URL="nats://host.docker.internal:4222"
export E2E_EXTERNAL_REDIS_URL="redis://host.docker.internal:6379/0"  # 仅 redis-ha-external 需要

bash scripts/e2e-bridge-pathb.sh single-persist-external
bash scripts/e2e-bridge-pathb.sh redis-ha-external
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

- 本套件只关注 **目录注册表/持续可发现**（Path B），不强制开启 OpenClaw 转发：
  - 若你不需要 OpenClaw webhook 转发，可设置 `BRIDGE_ENABLE_FORWARD=0`
- NATS 在此套件里默认保持 Docker 内网可达（不对公网暴露 `4222`）。

