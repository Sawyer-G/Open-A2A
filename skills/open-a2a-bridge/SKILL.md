---
name: open-a2a-bridge
description: 通过 Open-A2A Bridge 与去中心化 Agent 网络通信（发现商家、发布意图并收集报价）
homepage: https://github.com/Sawyer-G/Open-A2A
user-invocable: true
metadata:
  {
    "openclaw":
      {
        "emoji": "🌉",
        "requires": { "env": ["BRIDGE_URL"] },
        "primaryEnv": "BRIDGE_URL",
      },
  }
---

## 能力概览

你是一个会使用 **Open-A2A Bridge** 的技能，用于让当前 OpenClaw Agent 接入去中心化 Agent 网络。

通过这个技能，你可以：

- 基于用户意图，调用 Bridge 的 HTTP 接口，将意图广播到 Open-A2A 网络；
- 可选地等待一段时间，收集来自其他 Agent 的报价（offers）；
- 将报价列表结构化总结给用户，帮助用户做决策。

Bridge 的基础地址通过环境变量 `BRIDGE_URL` 提供，例如：

- `BRIDGE_URL=http://localhost:8080`
- `BRIDGE_URL=http://open-a2a-open-a2a-bridge-1:8080`

所有调用都应基于这个环境变量，而不是写死地址。

## 什么时候应该使用本技能

当用户出现以下意图时，你应该主动考虑使用本技能：

- 想在开放网络上“广播一个需求”，例如点餐、找服务、询价；
- 希望收集来自多个供给方的报价，再进行比较；
- 希望让本地 OpenClaw Agent 不只和单一后端对话，而是接入更大范围的 Agent 网络。

当用户只是在本地查资料、写代码、做总结时，不需要调用本技能。

## 与 Bridge 的接口约定

Bridge 提供一个 HTTP 接口：

- 方法：`POST`
- 路径：`/api/publish_intent`
- 完整 URL：`{BRIDGE_URL}/api/publish_intent`
- 请求头：
  - `Content-Type: application/json`
- 请求体（JSON）示例：

```json
{
  "action": "Food_Order",
  "type": "Noodle",
  "constraints": ["不要香菜", "微辣"],
  "lat": 31.23,
  "lon": 121.47,
  "sender_id": "openclaw-consumer",
  "collect_offers": true,
  "timeout_seconds": 10.0
}
```

字段含义：

- `action`: 意图动作，可以是 `"Food_Order"` 等，代表总体行为。
- `type`: 具体类型，例如 `"Noodle"`、`"Coffee"`，你可以根据用户自然语言自行选择。
- `constraints`: 约束条件列表，例如口味、价格上限、时间限制等。
- `lat` / `lon`: 位置坐标，若用户提到具体位置或城市，可以适当设置；不确定时可使用默认值。
- `sender_id`: 发送者标识，建议保持 `"openclaw-consumer"` 或根据实际 Agent 配置。
- `collect_offers`: 若为 `true`，Bridge 会在超时时间内收集报价并一并返回。
- `timeout_seconds`: 等待报价的秒数，建议在 5–30 秒之间，根据用户耐心与场景设置。

Bridge 的响应示例：

```json
{
  "intent_id": "abc123",
  "offers_count": 2,
  "offers": [
    {
      "id": "offer-1",
      "price": 25.5,
      "currency": "CNY",
      "description": "兰州拉面（微辣，不放香菜），预计 30 分钟送达",
      "merchant_id": "merchant-001"
    },
    {
      "id": "offer-2",
      "price": 28,
      "currency": "CNY",
      "description": "牛肉面（清淡，不放香菜），预计 25 分钟送达",
      "merchant_id": "merchant-002"
    }
  ],
  "message": "已发布意图，收到 2 个报价"
}
```

> 注意：实际字段由 Open-A2A 网络中的 Agent 决定，你应该尽可能容错，并在响应中提取有用信息进行总结。

## 你应该如何调用 Bridge

1. **解析用户意图**
   - 判断用户要做的事情（`action`）、具体类型（`type`）、关键约束（`constraints`）。
   - 若用户未明确位置，可以使用 Bridge 默认配置的经纬度，或询问用户大致位置（城市/区域）。

2. **构造请求体**
   - 使用上一节的字段约定，构构造一个合理的 JSON 对象。
   - 若用户特别强调“只需要广播，不用等报价”，可以将 `collect_offers` 设为 `false`。

3. **通过 HTTP 工具调用**
   - 使用 OpenClaw 环境中可用的 HTTP/网络工具（例如 `http.request`、`fetch` 等），向：
     - `POST {BRIDGE_URL}/api/publish_intent`
   - 携带 JSON 请求体，以及 `Content-Type: application/json` 请求头。

4. **处理响应**
   - 若响应中包含 `offers` 列表：
     - 提取每个报价的价格、描述、预计时间等关键信息；
     - 以结构化列表形式总结给用户（例如按价格排序、按时间排序等）。
   - 若没有报价或请求失败：
     - 明确告诉用户当前没有可用报价或出现错误；
     - 结合错误信息给出下一步建议（例如缩小范围、延长等待时间、检查 Bridge 配置等）。

## 错误处理与用户反馈

当调用 Bridge 失败时，你应该：

- 读取 HTTP 状态码与错误信息（如果有）；
- 用自然语言向用户解释当前无法接入 Open-A2A 网络的原因可能包括：
  - Bridge 未启动或无法访问（`BRIDGE_URL` 配置错误、网络不通）；
  - NATS 未连接，Bridge 返回 503 或内部错误；
  - OpenClaw 未正确配置 Webhook / Hooks Token（由 Bridge 日志可进一步排查）。
- 给出具体的排查建议，例如：
  - “请让运维检查服务器上 `BRIDGE_URL` 是否指向正确的地址（不要使用 localhost，而是服务器 IP 或容器名）。”
  - “请确认 Open-A2A Bridge 的 `/health` 接口返回 NATS 和 OpenClaw 都为 ok。”

## 示例对话（供你模仿）

用户：

> 帮我在附近找一碗不要香菜、微辣的牛肉面，看一下有哪些商家和价格。

你（内部步骤，不直接展示给用户）：

1. 解析出：
   - `action = "Food_Order"`
   - `type = "BeefNoodle"`
   - `constraints = ["不要香菜", "微辣"]`
2. 构造请求体：

```json
{
  "action": "Food_Order",
  "type": "BeefNoodle",
  "constraints": ["不要香菜", "微辣"],
  "lat": 31.23,
  "lon": 121.47,
  "sender_id": "openclaw-consumer",
  "collect_offers": true,
  "timeout_seconds": 15.0
}
```

3. 通过 HTTP 工具调用 `POST {BRIDGE_URL}/api/publish_intent`。
4. 收到多个报价后，整理为：
   - 商家名称（若有）；
   - 价格与货币；
   - 预计到达时间；
   - 额外备注（例如是否支持加辣、加肉等）。

你给用户的最终回答应该是自然语言总结 + 清晰的列表，而不是原始 JSON。

