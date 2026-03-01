"""
Agent 发现抽象 (Discovery)

服务于「跨网络 Agent 通信」：解决「如何发现彼此」。
定义能力注册与查询接口，与具体实现（NATS、DHT、全局索引等）解耦。
"""

from abc import ABC, abstractmethod
from typing import Any

# 发现主题前缀（与传输实现约定）
DISCOVERY_QUERY_PREFIX = "open_a2a.discovery.query"


class DiscoveryProvider(ABC):
    """
    Agent 发现提供者抽象

    Agent 可注册自己支持的能力（如 intent.food.order），
    其他 Agent 可查询「谁支持某能力」，用于跨节点、跨集群发现。
    """

    @abstractmethod
    async def connect(self) -> None:
        """建立与发现后端的连接（若需要）"""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """断开连接"""
        ...

    @abstractmethod
    async def register(self, capability: str, meta: dict[str, Any]) -> None:
        """
        注册本 Agent 支持的能力

        :param capability: 能力标识，与协议主题对应（如 intent.food.order）
        :param meta: 可选元数据，如 agent_id、endpoint、did、region 等，供发现方使用
        """
        ...

    @abstractmethod
    async def unregister(self, capability: str) -> None:
        """取消对某能力的注册"""
        ...

    @abstractmethod
    async def discover(self, capability: str, timeout_seconds: float = 5.0) -> list[dict[str, Any]]:
        """
        发现支持某能力的 Agent 列表

        :param capability: 能力标识
        :param timeout_seconds: 等待响应的最长时间
        :return: 响应方提供的 meta 列表，可能为空
        """
        ...
