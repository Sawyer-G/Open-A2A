"""
Open-A2A Core SDK

去中心化 Agent 间协作协议的 Python 参考实现。
"""

from open_a2a.intent import (
    Intent,
    Offer,
    OrderConfirm,
    LogisticsRequest,
    LogisticsAccept,
    Location,
)
from open_a2a.broadcaster import IntentBroadcaster
from open_a2a.agent import BaseAgent

try:
    from open_a2a.identity import AgentIdentity
except ImportError:
    AgentIdentity = None  # type: ignore

from open_a2a.preferences import FilePreferencesProvider, PreferencesProvider

__all__ = [
    "Intent",
    "Offer",
    "OrderConfirm",
    "LogisticsRequest",
    "LogisticsAccept",
    "Location",
    "IntentBroadcaster",
    "BaseAgent",
    "AgentIdentity",
    "PreferencesProvider",
    "FilePreferencesProvider",
]

__version__ = "0.1.0"
