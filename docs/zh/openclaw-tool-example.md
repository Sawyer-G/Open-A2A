# OpenClaw Open-A2A Tool 配置示例

> 将 Open-A2A 的 `publish_intent` 配置为 OpenClaw 可调用的工具。

## 1. 前置条件

- Open-A2A Bridge 已运行（如 `http://localhost:8080`）
- OpenClaw 已部署并可配置自定义 Tool

**注意**：若使用 Bridge 的「意图转发到 OpenClaw」功能（Channel 集成），需在 OpenClaw 配置中启用 `hooks.allowRequestSessionKey=true`。

## 2. 使用 http_request 工具

若 OpenClaw 支持 `http_request` 或类似 HTTP 调用工具，可配置：

**工具名**：`open_a2a_publish_intent`

**调用方式**：
```
POST {BRIDGE_URL}/api/publish_intent
Content-Type: application/json

{
  "type": "Noodle",
  "constraints": ["No_Coriander", "<30min"],
  "lat": 31.23,
  "lon": 121.47,
  "collect_offers": true,
  "timeout_seconds": 10
}
```

**工具描述**（供 Agent 理解何时调用）：
```
发布意图到 Open-A2A 网络。当用户表达想吃某类食物（如面条、米饭）或需要某类服务时，调用此工具将意图广播到网络并收集商家报价。参数：type（类型）、constraints（约束列表，如忌口、时间）、lat/lon（位置）。
```

## 3. 自定义 Tool 配置（YAML 示例）

若 OpenClaw 使用 YAML 配置工具，可参考：

```yaml
tools:
  - name: open_a2a_publish_intent
    type: http_request
    description: 发布意图到 Open-A2A 网络，收集商家报价。用户说想吃面、订餐等时使用。
    config:
      url: "http://localhost:8080/api/publish_intent"
      method: POST
      headers:
        Content-Type: application/json
```

## 4. 响应格式

Bridge 返回示例：

```json
{
  "intent_id": "uuid-xxx",
  "offers_count": 2,
  "offers": [
    {
      "id": "offer-1",
      "intent_id": "uuid-xxx",
      "price": 18,
      "unit": "UNIT",
      "description": "手工拉面"
    }
  ],
  "message": "已发布意图，收到 2 个报价"
}
```

Agent 可根据 `offers` 向用户展示报价并协助选择。
