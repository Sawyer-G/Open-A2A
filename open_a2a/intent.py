"""
意图与报价消息模型 (RFC-001)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
import json
import uuid


@dataclass
class Location:
    """位置信息"""

    lat: float
    lon: float

    def to_dict(self) -> dict[str, Any]:
        return {"lat": self.lat, "lon": self.lon}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Location":
        return cls(lat=data["lat"], lon=data["lon"])


@dataclass
class Intent:
    """
    意图消息 - 消费者向网络广播
    """

    action: str
    type: str
    reply_to: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    location: Optional[Location] = None
    constraints: list[str] = field(default_factory=list)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    sender_id: str = ""
    sender_did: Optional[str] = None  # Phase 2: did:key，验签后填充

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "action": self.action,
            "type": self.type,
            "location": self.location.to_dict() if self.location else None,
            "constraints": self.constraints,
            "reply_to": self.reply_to,
            "timestamp": self.timestamp,
            "sender_id": self.sender_id,
            "sender_did": self.sender_did,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any], signer_did: Optional[str] = None) -> "Intent":
        loc = None
        if data.get("location"):
            loc = Location.from_dict(data["location"])
        return cls(
            id=data["id"],
            action=data["action"],
            type=data["type"],
            location=loc,
            constraints=data.get("constraints", []),
            reply_to=data["reply_to"],
            timestamp=data.get("timestamp", ""),
            sender_id=data.get("sender_id", ""),
            sender_did=signer_did or data.get("sender_did"),
        )

    @classmethod
    def from_json(cls, s: str, signer_did: Optional[str] = None) -> "Intent":
        return cls.from_dict(json.loads(s), signer_did=signer_did)


@dataclass
class Offer:
    """
    报价消息 - 商家响应意图
    """

    intent_id: str
    price: float
    unit: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    eta_minutes: Optional[int] = None
    description: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    sender_id: str = ""
    sender_did: Optional[str] = None  # Phase 2: did:key，验签后填充

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "intent_id": self.intent_id,
            "price": self.price,
            "unit": self.unit,
            "eta_minutes": self.eta_minutes,
            "description": self.description,
            "timestamp": self.timestamp,
            "sender_id": self.sender_id,
            "sender_did": self.sender_did,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any], signer_did: Optional[str] = None) -> "Offer":
        return cls(
            id=data["id"],
            intent_id=data["intent_id"],
            price=data["price"],
            unit=data["unit"],
            eta_minutes=data.get("eta_minutes"),
            description=data.get("description", ""),
            timestamp=data.get("timestamp", ""),
            sender_id=data.get("sender_id", ""),
            sender_did=signer_did or data.get("sender_did"),
        )

    @classmethod
    def from_json(cls, s: str, signer_did: Optional[str] = None) -> "Offer":
        return cls.from_dict(json.loads(s), signer_did=signer_did)


@dataclass
class OrderConfirm:
    """
    订单确认 - 消费者接受某 Offer
    """

    intent_id: str
    offer_id: str
    consumer_id: str = ""
    delivery: Optional[Location] = None  # 配送地址，用于 LogisticsRequest
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "intent_id": self.intent_id,
            "offer_id": self.offer_id,
            "consumer_id": self.consumer_id,
            "delivery": self.delivery.to_dict() if self.delivery else None,
            "timestamp": self.timestamp,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OrderConfirm":
        delivery = None
        if data.get("delivery"):
            delivery = Location.from_dict(data["delivery"])
        return cls(
            id=data["id"],
            intent_id=data["intent_id"],
            offer_id=data["offer_id"],
            consumer_id=data.get("consumer_id", ""),
            delivery=delivery,
            timestamp=data.get("timestamp", ""),
        )

    @classmethod
    def from_json(cls, s: str) -> "OrderConfirm":
        return cls.from_dict(json.loads(s))


@dataclass
class LogisticsRequest:
    """
    配送请求 - 商家发布
    """

    order_id: str
    pickup: Location
    delivery: Location
    fee: float
    unit: str
    reply_to: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    sender_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "order_id": self.order_id,
            "pickup": self.pickup.to_dict(),
            "delivery": self.delivery.to_dict(),
            "fee": self.fee,
            "unit": self.unit,
            "reply_to": self.reply_to,
            "timestamp": self.timestamp,
            "sender_id": self.sender_id,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LogisticsRequest":
        return cls(
            id=data["id"],
            order_id=data["order_id"],
            pickup=Location.from_dict(data["pickup"]),
            delivery=Location.from_dict(data["delivery"]),
            fee=data["fee"],
            unit=data["unit"],
            reply_to=data["reply_to"],
            timestamp=data.get("timestamp", ""),
            sender_id=data.get("sender_id", ""),
        )

    @classmethod
    def from_json(cls, s: str) -> "LogisticsRequest":
        return cls.from_dict(json.loads(s))


@dataclass
class LogisticsAccept:
    """
    配送接单 - 骑手响应
    """

    request_id: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    eta_minutes: Optional[int] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    sender_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "request_id": self.request_id,
            "eta_minutes": self.eta_minutes,
            "timestamp": self.timestamp,
            "sender_id": self.sender_id,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LogisticsAccept":
        return cls(
            id=data["id"],
            request_id=data["request_id"],
            eta_minutes=data.get("eta_minutes"),
            timestamp=data.get("timestamp", ""),
            sender_id=data.get("sender_id", ""),
        )

    @classmethod
    def from_json(cls, s: str) -> "LogisticsAccept":
        return cls.from_dict(json.loads(s))


# 主题常量 (RFC-001)
TOPIC_INTENT_FOOD_ORDER = "intent.food.order"
TOPIC_INTENT_FOOD_OFFER_PREFIX = "intent.food.offer"
TOPIC_ORDER_CONFIRM = "intent.food.order_confirm"
TOPIC_LOGISTICS_REQUEST = "intent.logistics.request"
TOPIC_LOGISTICS_ACCEPT_PREFIX = "intent.logistics.accept"
