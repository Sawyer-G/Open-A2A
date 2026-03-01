"""
Base Agent - Agent 基类，供 Consumer/Merchant 继承
"""

from abc import ABC

from open_a2a.broadcaster import IntentBroadcaster


class BaseAgent(ABC):
    """
    Agent 基类 - 封装连接与基础能力
    """

    def __init__(
        self,
        agent_id: str,
        nats_url: str = "nats://localhost:4222",
    ) -> None:
        self.agent_id = agent_id
        self._broadcaster = IntentBroadcaster(nats_url)

    async def start(self) -> None:
        """启动 Agent，连接 NATS"""
        await self._broadcaster.connect()

    async def stop(self) -> None:
        """停止 Agent"""
        await self._broadcaster.disconnect()

    @property
    def broadcaster(self) -> IntentBroadcaster:
        return self._broadcaster
