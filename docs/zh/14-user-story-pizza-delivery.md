# 用户故事：订购披萨（A 商家 / B 消费者 / C 骑手）在主节点 X 上协作

> 本文档用一个完整的「订购披萨并送达」故事，解释 Open-A2A 当前实现的协议如何在多参与方、多 Agent、多网络入口节点的环境中工作。  
> 注意：披萨/外卖仅为示例场景，用于具象化协议层的 Intent / Offer / Confirm / Logistics 交互原语。

---

## 1. 角色与节点

- **用户 A（商家）**：部署 `A-agent`，负责接收订单意图并报价、确认出餐、发起配送请求。
- **用户 B（消费者）**：部署 `B-agent`，负责发布“想要披萨”的意图、收集商家报价、确认下单。
- **用户 C（骑手）**：部署 `C-agent`，负责接收配送请求并接单、模拟送达。
- **主节点 X（运营方）**：你运营的公共/联盟入口节点，提供共享的消息主题空间与接入方式。

主节点 X 通常包含：

- **NATS**（默认 `4222`）：协议主题空间（Intent/Offer/Logistics 等都在主题上流动）。
- **Relay**（默认 `8765`，可选）：出站优先入口（终端 Agent 只需向外建立 WebSocket 连接即可加入主题空间）。
- **Bridge**（默认 `8080`，可选）：运行时适配层（例如 OpenClaw 通过 HTTP Tool/Webhook 接入，无需理解 NATS）。

---

## 2. 接入方式（A/B/C 如何使用主节点 X）

根据部署环境，A/B/C 常见有两种接入方式：

### 方式 A：直连 NATS

当 A/B/C 的 Agent 可以直接访问 X 的 NATS 时：

- 将各自 Agent 的 `NATS_URL` 指向主节点 X（示例：`nats://user:pass@nats.open-a2a.org:4222`）
- 直连 NATS 的 Agent 会直接在同一主题空间中发布/订阅消息

### 方式 B：通过 Relay 出站接入（更贴近真实网络）

当 A/B/C 位于 NAT/公司网络等只能出站的环境：

- 将各自 Agent 的 `RELAY_WS_URL` 指向主节点 X 的 Relay（示例：`ws://relay.open-a2a.org:8765`）
- Agent 通过 WebSocket 出站连接到 Relay，由 Relay 代为连接 NATS 并桥接主题

> 对 OpenClaw：通常通过 Bridge 的 HTTP Tool/Webhook 接入。它与直连 NATS 在协议语义上等价，只是传输层由 Bridge/Relay 代劳。

---

## 3. 两种“被发现”的方式：事件式触达 vs 目录式发现

在 Open-A2A 中，“发现”通常有两种体验：

### 3.1 事件式触达（无需目录注册）

- B 广播一个 Intent（例如 `intent.food.order`）
- A 订阅该主题，收到后决定是否回复 Offer

这是一种**事件驱动**的协作方式：是否“被发现”由意图的广播触发。

### 3.2 目录注册表（持续被发现，原 Path B）

如果希望其他节点能够像查目录一样查询“谁支持某能力（capability）”，可以使用 Discovery：

- `capability` 与协议主题一致（如 `intent.food.order`、`intent.logistics.request`）
- 在 NATS 发现实现中，`register` 并非写入中心化注册表，而是：
  - 订阅 `open_a2a.discovery.query.{capability}`
  - 当收到查询请求时，回复一份 `meta`
- 因此只要注册方进程在线，就可**持续被 discover**

主节点 X 上的 Bridge 已提供：

- `POST /api/register_capabilities`：注册/更新能力（携带 meta）
- `GET /api/discover?capability=...`：查询支持某 capability 的 Agent 列表

---

## 4. 完整协作流程：订披萨 → 报价 → 下单 → 配送 → 送达

下面以当前已实现的 Phase 3 消息为基础（披萨只是 `type="Pizza"` 的一种意图），描述一次完整流程。

### Step 1：B 发布披萨意图（Intent）

- **主题**：`intent.food.order`
- **意图内容（概念）**：
  - `action="Food_Order"`
  - `type="Pizza"`
  - `constraints=["无洋葱","30分钟内"]`（示例）
  - `location=(lat,lon)`
  - `reply_to=intent.food.offer.{intent_id}`（用于收集报价）

B-agent 可以选择：

- 只广播不等待（`collect_offers=false`），或
- 广播并在超时窗口内收集多个 Offer（`collect_offers=true`）

### Step 2：A 收到 Intent，回复 Offer（报价）

- **A-agent 订阅**：`intent.food.order`
- **A-agent 发布 Offer 到**：`intent.food.offer.{intent_id}`（也就是 B 的 `reply_to`）
- Offer 通常包含：价格、描述、预计时间、商家标识等

### Step 3：B 选择报价并确认下单（OrderConfirm）

B-agent 在收集到多个商家报价后，选择一个最合适的并发布确认：

- **主题**：`intent.food.order_confirm`
- **内容**：携带选中的 Offer / merchant_id / intent_id 等关键信息

### Step 4：A 发起配送请求（LogisticsRequest）

A-agent 在收到订单确认后，向网络发起配送请求：

- **主题**：`intent.logistics.request`
- **内容**：
  - 配送起点（商家地址）与终点（消费者位置）
  - `reply_to=intent.logistics.accept.{request_id}`（用于收集骑手接单）

### Step 5：C 收到配送请求并接单（LogisticsAccept）

- **C-agent 订阅**：`intent.logistics.request`
- **C-agent 发布 LogisticsAccept 到**：`intent.logistics.accept.{request_id}`
- A-agent 收集多个接单/报价，选择一个骑手

### Step 6：送达与完成（当前实现为模拟）

当前仓库的示例中，骑手侧会“模拟送达”，并完成一次端到端的协作链路验证。真实生产场景下：

- 送达证明（PoD）与资金结算通常接入外部系统（链上或链下）
- Open-A2A 在协议层提供“可插拔结算原语”，但不强绑定某一种具体支付/业务实现

---

## 5. 主节点 X 的价值

- **共享主题空间**：让 A/B/C 只需接入同一入口即可协作。
- **降低接入门槛**：
  - 终端网络受限：通过 Relay 出站接入。
  - 运行时不懂 NATS：通过 Bridge（HTTP Tool/Webhook）接入。
- **多运营者网络基础**：未来可通过 NATS 集群/联邦或 DHT 将多个入口节点组成更大的协作网（不是区块链，不需要全网共识账本）。

