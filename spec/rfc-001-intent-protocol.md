# RFC-001: 意图协议 (Intent Protocol)

> 版本：0.1.0-draft | 状态：草稿

## 1. 概述

本协议定义 Open-A2A 网络中 Agent 间意图广播与响应的消息格式与主题规范。适用于 Phase 1「Hello Open-A2A」及后续扩展。

## 2. 主题结构 (Subject Structure)

```
intent.{domain}.{action}[.{sub}]
```

| 部分 | 说明 | 示例 |
|------|------|------|
| `intent` | 固定前缀 | - |
| `domain` | 领域 | `food`, `logistics`, `service` |
| `action` | 动作类型 | `order`, `offer`, `request` |
| `sub` | 可选子主题 | 如 `reply.{intent_id}` |

### 2.1 预定义主题

| 主题 | 方向 | 说明 |
|------|------|------|
| `intent.food.order` | Consumer → 网络 | 消费者发布「想吃」意图 |
| `intent.food.offer.{intent_id}` | Merchant → Consumer | 商家针对某意图回复报价 |
| `intent.food.order_confirm` | Consumer → Merchant | 消费者确认订单（接受某 Offer） |
| `intent.logistics.request` | Merchant → 网络 | 商家发布配送请求 |
| `intent.logistics.accept.{request_id}` | Carrier → Merchant | 骑手接单 |

## 3. 消息格式

### 3.1 意图消息 (Intent)

消费者向 `intent.food.order` 发布：

```json
{
  "id": "uuid-v4",
  "action": "Food_Order",
  "type": "Noodle",
  "location": {
    "lat": 31.23,
    "lon": 121.47
  },
  "constraints": ["No_Coriander", "<30min"],
  "reply_to": "intent.food.offer.{id}",
  "timestamp": "2026-02-28T12:00:00Z",
  "sender_id": "agent-consumer-001"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | ✓ | 意图唯一标识 (UUID) |
| `action` | string | ✓ | 动作类型，见语义字典 |
| `type` | string | ✓ | 子类型，如 Noodle |
| `location` | object | - | 位置，含 lat/lon |
| `constraints` | array | - | 约束列表 |
| `reply_to` | string | ✓ | 回复主题，商家将 Offer 发往此处 |
| `timestamp` | string | ✓ | ISO 8601 |
| `sender_id` | string | - | 发送方标识 |
| `sender_did` | string | - | Phase 2: 验签后的 did:key，可选 |

### 3.2 报价消息 (Offer)

商家向 `reply_to` 主题发布：

```json
{
  "id": "uuid-v4",
  "intent_id": "original-intent-id",
  "price": 18,
  "unit": "UNIT",
  "eta_minutes": 15,
  "description": "手工拉面，不加香菜",
  "timestamp": "2026-02-28T12:00:05Z",
  "sender_id": "agent-merchant-001"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | ✓ | Offer 唯一标识 |
| `intent_id` | string | ✓ | 对应的意图 ID |
| `price` | number | ✓ | 价格 |
| `unit` | string | ✓ | 单位，如 UNIT |
| `eta_minutes` | number | - | 预计送达分钟数 |
| `description` | string | - | 描述 |
| `timestamp` | string | ✓ | ISO 8601 |
| `sender_id` | string | - | 商家标识 |
| `sender_did` | string | - | Phase 2: 验签后的 did:key，可选 |

## 4. 语义字典 (Semantic Vocabulary)

| Action | 说明 |
|--------|------|
| `Food_Order` | 食品订单意图 |
| `Logistics_Request` | 配送请求 (Phase 3) |

## 5. 交互流程

```
Consumer                          NATS                          Merchant(s)
   |                                 |                                  |
   |  publish(intent.food.order)     |                                  |
   |-------------------------------->|                                  |
   |                                 |  subscribe(intent.food.order)    |
   |                                 |--------------------------------->|
   |                                 |                                  |
   |                                 |     publish(reply_to, offer)      |
   |  subscribe(reply_to)            |<---------------------------------|
   |<--------------------------------|                                  |
   |                                 |                                  |
```

## 6. Phase 3 扩展：配送与订单确认

### 6.1 订单确认 (OrderConfirm)

消费者向 `intent.food.order_confirm` 发布，表示接受某 Offer：

```json
{
  "id": "uuid-v4",
  "intent_id": "original-intent-id",
  "offer_id": "accepted-offer-id",
  "consumer_id": "consumer-001",
  "delivery": {"lat": 31.25, "lon": 121.50},
  "timestamp": "2026-02-28T12:01:00Z"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | ✓ | 订单唯一标识 |
| `intent_id` | string | ✓ | 原始意图 ID |
| `offer_id` | string | ✓ | 接受的 Offer ID |
| `consumer_id` | string | - | 消费者标识 |
| `delivery` | object | - | 配送地址，含 lat/lon，用于 LogisticsRequest |
| `timestamp` | string | ✓ | ISO 8601 |

### 6.2 配送请求 (LogisticsRequest)

商家向 `intent.logistics.request` 发布：

```json
{
  "id": "uuid-v4",
  "order_id": "order-from-confirm",
  "pickup": {"lat": 31.23, "lon": 121.47},
  "delivery": {"lat": 31.25, "lon": 121.50},
  "fee": 3,
  "unit": "UNIT",
  "reply_to": "intent.logistics.accept.{id}",
  "timestamp": "2026-02-28T12:02:00Z",
  "sender_id": "merchant-001"
}
```

### 6.3 配送接单 (LogisticsAccept)

骑手向 `reply_to` 主题发布：

```json
{
  "id": "uuid-v4",
  "request_id": "logistics-request-id",
  "eta_minutes": 20,
  "timestamp": "2026-02-28T12:02:05Z",
  "sender_id": "carrier-001"
}
```

### 6.4 A-B-C 全流程

```
Consumer → Intent → Merchant(s) → Offer
Consumer → OrderConfirm → Merchant
Merchant → LogisticsRequest → Carrier(s) → LogisticsAccept
(模拟) Carrier 送达 → 结算
```

---

## 7. 扩展说明

- Phase 2：`sender_id` 替换为 `did:key`，消息增加签名字段
