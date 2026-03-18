# OpenClaw（Docker）环境下集成 Open-A2A 指南

> 适用场景：你的 OpenClaw Gateway 运行在 Docker 容器中，希望在同一台服务器上运行 Open-A2A 的 NATS / Relay / Bridge 等组件，并让两者互通。

---

## 1. 场景概览

在这个场景中，典型的拓扑是：

- OpenClaw 通过自己的 `docker-compose` 在服务器上运行（容器名示例：`openclaw-openclaw-gateway-1`，端口 `18789`）；
- Open-A2A 通过本项目提供的 `docker-compose.deploy.yml` 拉起：
  - `nats`：消息总线（默认端口 `4222`）；
  - `relay`：WebSocket Relay（默认端口 `8765`）；
  - `solid`：自托管 Solid Pod（可选）；
  - `open-a2a-bridge`：Bridge 网关（默认端口 `8080`），负责对接 OpenClaw。

关键问题在于：

- Bridge 容器如何访问 OpenClaw Gateway？
- OpenClaw 如何把请求发给 Bridge，又如何接收来自 Open-A2A 的回调？

本指南基于实际踩坑经验，总结出一条尽量“免踩坑”的标准配置路径。

---

## 2. 前置条件

在开始之前，请确保：

- 你已经在服务器上运行了 OpenClaw（Docker 方式），`docker ps` 中能看到 Gateway 容器，例如：

```bash
docker ps | grep -i gateway
```

- 服务器上已安装 `docker` 与 `docker-compose`；
- 已 clone 本仓库：

```bash
git clone https://github.com/Sawyer-G/Open-A2A.git
cd Open-A2A
```

---

## 3. 使用辅助脚本启动 Open-A2A 组件

推荐使用仓库自带的脚本，在 OpenClaw 所在服务器上执行：

```bash
bash scripts/setup-openclaw-bridge.sh
```

脚本将完成：

1. 检查并创建 `.env`（不存在则从 `.env.example` 拷贝）；
2. 询问并写入 `NATS_URL`、`OPENCLAW_GATEWAY_URL`、`OPENCLAW_HOOKS_TOKEN`；
3. 执行：

```bash
docker-compose -f docker-compose.deploy.yml up -d --build
```

此外，脚本还提供：

- 自动尝试通过 `docker ps` / `docker inspect` 探测 OpenClaw Gateway 容器名，并给出智能默认的 `OPENCLAW_GATEWAY_URL`（例如 `http://openclaw-openclaw-gateway-1:18789`）；
- `diagnose` 子命令，用于在部署后快速自查配置是否正确：

```bash
bash scripts/setup-openclaw-bridge.sh diagnose
```

`diagnose` 会检查：

- `.env` 中的 `NATS_URL` / `OPENCLAW_GATEWAY_URL` / `OPENCLAW_HOOKS_TOKEN`；
- Bridge 容器中的环境变量；
- 从宿主机到 `OPENCLAW_GATEWAY_URL` 的连通性；
- 本机 `http://localhost:8080/health` 接口的状态。

---

## 4. 关键配置 1：`OPENCLAW_GATEWAY_URL`

**最常见的错误**：在 `.env` 中写了：

```bash
OPENCLAW_GATEWAY_URL=http://localhost:18789
```

这在 Bridge 容器内的含义是：“访问 Bridge 自己这一只容器的 18789 端口”，而不是 OpenClaw Gateway。结果是：

- Bridge 无法访问 OpenClaw；
- Bridge 日志里看不到访问 Gateway 的记录；
- `/agents` / NATS 发现结果为空。

### 正确思路：用「容器名:端口」

在 **Docker 共享网络** 中，推荐让 `OPENCLAW_GATEWAY_URL` 指向：

```bash
http://<OpenClaw Gateway 容器名>:18789
```

例如，如果 `docker ps` 显示 Gateway 的 `NAMES` 为：

```text
openclaw-openclaw-gateway-1
```

则可以在 `.env` 中写：

```bash
OPENCLAW_GATEWAY_URL=http://openclaw-openclaw-gateway-1:18789
```

> 实际容器名取决于你自己的 `docker-compose` 项目名与服务名，上述只是常见示例。关键原则是：**不要在 Bridge 容器里用 `localhost` 指向 OpenClaw**。

### 临时方案：使用宿主机 IP

如果暂时不方便让 Open-A2A 与 OpenClaw 共用 Docker 网络，可以退而求其次，使用宿主机 IP：

```bash
OPENCLAW_GATEWAY_URL=http://<宿主机IP>:18789
```

前提是：

- OpenClaw Gateway 对外映射了 `18789` 端口；
- Bridge 容器所在网络可以访问宿主机该 IP。

---

## 5. 关键配置 2：共享 Docker 网络

若希望使用「容器名:端口」的写法（推荐），则需要确保：

- `open-a2a-bridge` 所在网络中，存在 OpenClaw Gateway 容器；
- 通常做法是让 Bridge 加入 OpenClaw 的应用网络，例如：

```yaml
# 片段示例：docker-compose.deploy.yml
services:
  open-a2a-bridge:
    # ...
    networks:
      - default
      - openclaw_openclaw-network  # OpenClaw 的网络名

networks:
  default:
    driver: bridge
  openclaw_openclaw-network:
    external: true
```

> 这里的 `openclaw_openclaw-network` 应与你实际的 OpenClaw `docker-compose` 定义的网络名保持一致。可以通过 `docker network ls` 查看。

如果网络没有共享，Bridge 在解析 `openclaw-openclaw-gateway-1` 时会报类似：

```text
[Bridge] 转发意图到 OpenClaw 失败: [Errno -3] Temporary failure in name resolution
```

这时要么：

- 调整 `docker-compose.deploy.yml`，让 Bridge 加入 OpenClaw 网络；
- 要么改用宿主机 IP 的 `OPENCLAW_GATEWAY_URL`（见上一节）。

---

## 6. 关键配置 3：Hook Token（`OPENCLAW_HOOKS_TOKEN`）

为了让 Bridge 能把来自 Open-A2A 的回调推回 OpenClaw，需要配置一个安全的 Hook Token。

### OpenClaw 侧（示例）

在 OpenClaw 的配置中（例如 `openclaw.json`）增加 Hooks 设置：

```json
{
  "hooks": {
    "enabled": true,
    "token": "open-a2a-bridge-token-2026",
    "path": "/hooks"
  }
}
```

这里的 `token` 字段就是 OpenClaw 期望的 Bearer Token。

### Open-A2A 侧（`.env`）

在 `.env` 中配置：

```bash
OPENCLAW_HOOKS_TOKEN=open-a2a-bridge-token-2026
```

要求是：

- **两边的 Token 必须完全一致**；
- Bridge 在调用 OpenClaw 的 `/hooks/agent` 时会带上：

```http
Authorization: Bearer <OPENCLAW_HOOKS_TOKEN>
```

若 Token 不匹配，OpenClaw 会返回 401/403，导致 Agent 注册和回调失败。

---

## 7. OpenClaw 侧如何集成 Bridge

当前支持两类集成方式：

1. **HTTP Tool + Webhook（通用方案）**
   - 在 OpenClaw 中配置一个 HTTP Tool，指向：
     - `POST http://<Bridge 地址>:8080/api/publish_intent`
   - 在 OpenClaw 中配置一个 Webhook，指向：
     - `{OPENCLAW_GATEWAY_URL}/hooks/agent`，并使用上文约定的 Hook Token。

2. **OpenClaw Skill（进阶方案 / 官方插件候选）**
   - 在 `~/.openclaw/skills/open-a2a/` 下编写自定义 Skill；
   - 在 Skill 内读取 `BRIDGE_URL` 环境变量，并将 Agent 请求转发到 Bridge；
   - 在本仓库的 `temp/needfix.md` 中有一个初步的 Skill 目录与配置示例，可作为未来官方 Skill 的原型。

对于多数用户，推荐先使用 **HTTP Tool + Webhook** 路线（配合本指南与 `docs/zh/openclaw-tool-example.md`）。当官方 Skill 成熟后，可以在文档中将 Skill 作为优先推荐路径。

---

## 7.1 持续被发现（目录式 discover）

除了“意图广播 → 收到后响应”这种事件式协作外，Open-A2A 也支持 **能力发现**（Discovery）：其他节点可以像查目录一样查询“谁支持某个能力（capability）”。

在 NATS 发现实现中，所谓的 `register` 并不是写入一个中心化注册表，而是：

- 订阅 `open_a2a.discovery.query.{capability}`；
- 当其他人查询该 capability 时，回复一份 `meta`。

因此要“持续被发现”，注册方需要保持在线（常见做法是让 Bridge 常驻运行并代 OpenClaw 注册）。

Bridge 支持两种方式：

1) **启动时自动注册（推荐）**

在 `.env` 中配置：

```bash
BRIDGE_ENABLE_DISCOVERY=1
BRIDGE_AGENT_ID=openclaw-agent
BRIDGE_CAPABILITIES=intent.food.order,intent.logistics.request
# 可选：补充 meta（JSON 字符串）
BRIDGE_META_JSON={"region":"shanghai","endpoint":"https://bridge.open-a2a.org"}
```

2) **通过 HTTP 接口注册/更新（适合 OpenClaw Tool/Skill 调用）**

```bash
curl -X POST http://localhost:8080/api/register_capabilities \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"openclaw-agent","capabilities":["intent.food.order"],"meta":{"region":"shanghai"}}'
```

其他节点查询：

```bash
curl "http://localhost:8080/api/discover?capability=intent.food.order&timeout_seconds=3" | jq .
```

---

## 8. 常见问题与排查清单

### 8.1 Bridge 日志里看不到访问 OpenClaw 的记录

可能原因：

- OpenClaw 侧还未配置 Tool / Skill 调用 Bridge；
- `OPENCLAW_GATEWAY_URL` 指错（例如仍然是 `localhost`，或网络不通）。

建议步骤：

1. 在 OpenClaw 中手动触发一次针对 Bridge 的调用（Tool 或 Skill）；
2. 在服务器上查看 Bridge 日志：

```bash
docker logs -f open-a2a-open-a2a-bridge-1
```

若仍然没有任何请求日志，多半是 OpenClaw 侧尚未连通。

### 8.2 `curl` 调用 Bridge 或 Hook 报 `Empty reply from server`

若服务器上开启了 HTTP 代理（Clash、V2Ray 等），可能导致本地请求被代理截获。

排查方式：

```bash
unset http_proxy https_proxy
curl http://localhost:8080/...
```

或使用：

```bash
curl --noproxy '*' http://localhost:8080/...
```

### 8.3 完整配置检查清单

在部署完成后，建议按以下顺序快速自检：

- [ ] **Bridge 容器环境变量正确**

```bash
docker exec open-a2a-open-a2a-bridge-1 env | grep OPENCLAW
```

- [ ] **Bridge 和 OpenClaw 网络连通（容器名可解析）**

```bash
docker exec open-a2a-open-a2a-bridge-1 ping openclaw-openclaw-gateway-1
```

> 将 `openclaw-openclaw-gateway-1` 替换为你实际的 Gateway 容器名。

- [ ] **Hook 端点可访问（Token 正确）**

```bash
curl -X POST http://localhost:18789/hooks/agent \
  -H "Authorization: Bearer open-a2a-bridge-token-2026" \
  -d '{"message":"test"}'
```

> 若返回 2xx，说明 Hook 通路基本正常。

- [ ] **Bridge API 响应正常**

```bash
curl -X POST http://localhost:8080/api/publish_intent \
  -H "Content-Type: application/json" \
  -d '{"intent":"test","params":{}}'
```

若以上几项都正常，再结合 NATS CLI 或 `nats-box` 订阅相关主题（例如 `agents.>`），即可进一步验证 Agent 发现是否工作正常。

---

## 9. 进一步优化方向

本指南主要基于当前版本的部署方式，总结了在 OpenClaw-Docker 场景下最常见的坑。框架后续可以在以下方向继续改进：

- 在 `scripts/setup-openclaw-bridge.sh` 中自动探测 OpenClaw Gateway 容器名与网络；
- 为 Bridge 提供 `/health` 接口，统一检查 NATS / OpenClaw / 自身状态；
- 发布官方 OpenClaw Skill，减少用户在 Tool / Webhook 级别的手工配置；
- 在 `docker-compose.deploy.yml` 中预置对 OpenClaw 网络的友好支持。

这些改进的设计草案可参考本仓库 `temp/needfix.md` 中的「后续框架调整建议草案」一节。

