"""
Open-A2A Core SDK

去中心化 Agent 间协作协议的 Python 参考实现。
"""

from open_a2a.intent import Intent, Offer
from open_a2a.broadcaster import IntentBroadcaster
from open_a2a.agent import BaseAgent

__all__ = [
    "Intent",
    "Offer",
    "IntentBroadcaster",
    "BaseAgent",
]

__version__ = "0.1.0"
