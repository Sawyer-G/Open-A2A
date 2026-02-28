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
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Intent":
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
        )

    @classmethod
    def from_json(cls, s: str) -> "Intent":
        return cls.from_dict(json.loads(s))


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
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Offer":
        return cls(
            id=data["id"],
            intent_id=data["intent_id"],
            price=data["price"],
            unit=data["unit"],
            eta_minutes=data.get("eta_minutes"),
            description=data.get("description", ""),
            timestamp=data.get("timestamp", ""),
            sender_id=data.get("sender_id", ""),
        )

    @classmethod
    def from_json(cls, s: str) -> "Offer":
        return cls.from_dict(json.loads(s))


# 主题常量 (RFC-001)
TOPIC_INTENT_FOOD_ORDER = "intent.food.order"
TOPIC_INTENT_FOOD_OFFER_PREFIX = "intent.food.offer"
