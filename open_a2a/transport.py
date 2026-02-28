"""
传输层抽象 (Transport Layer Abstraction)

设计原则 2.3：传输层可替换。当前以 NATS 为参考实现，架构预留传输适配器抽象，
未来可支持 HTTP、WebSocket、DHT、P2P 等不同底层。
"""

from abc import ABC, abstractmethod
from typing import Awaitable, Callable, Protocol, runtime_checkable


@runtime_checkable
class MessageSubscription(Protocol):
    """订阅句柄，用于取消订阅"""

    async def unsubscribe(self) -> None:
        """取消订阅"""
        ...


class TransportAdapter(ABC):
    """
    传输适配器抽象基类

    定义 Agent 间消息发布/订阅的通用接口，与具体传输实现（NATS、HTTP、WebSocket 等）解耦。
    服务于「跨网络 Agent 通信」核心目标。
    """

    @abstractmethod
    async def connect(self) -> None:
        """建立连接"""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """断开连接"""
        ...

    @abstractmethod
    async def publish(self, subject: str, data: bytes) -> None:
        """
        向指定主题发布消息

        :param subject: 主题（如 intent.food.order）
        :param data: 消息体（字节）
        """
        ...

    @abstractmethod
    async def subscribe(
        self,
        subject: str,
        cb: Callable[[bytes], Awaitable[None]],
    ) -> MessageSubscription:
        """
        订阅主题，收到消息时调用 cb

        :param subject: 主题
        :param cb: 回调，接收消息体 bytes
        :return: 订阅句柄，用于 unsubscribe
        """
        ...
