"""Base Agent - Agent 基类，供 Consumer/Merchant 继承."""

from abc import ABC
from typing import Optional

from open_a2a.broadcaster import IntentBroadcaster
from open_a2a.discovery_dht import DhtDiscoveryProvider
from open_a2a.discovery_nats import NatsDiscoveryProvider
from open_a2a.identity import AgentIdentity, IdentityNotAvailable


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


class AgentStack:
    """
    A higher-level, batteries-included stack for common agent runtime wiring:

    - IntentBroadcaster (NATS pub/sub)
    - Optional discovery provider:
        - NATS discovery (same subject space) via NatsDiscoveryProvider
        - DHT discovery (cross-network) via DhtDiscoveryProvider
    - Optional identity (did:key + JWS) via AgentIdentity

    This stays at protocol/infrastructure level: it wires transports and discovery,
    and leaves business semantics to the application.
    """

    def __init__(
        self,
        *,
        agent_id: str,
        nats_url: str = "nats://localhost:4222",
        discovery: str = "nats",
        dht_port: int = 8468,
        enable_identity: bool = False,
        did_seed: "Optional[bytes]" = None,
    ) -> None:
        self.agent_id = agent_id
        self.broadcaster = IntentBroadcaster(nats_url)
        self.identity: "Optional[AgentIdentity]" = None
        if enable_identity:
            try:
                self.identity = AgentIdentity(seed=did_seed)
            except IdentityNotAvailable:
                self.identity = None

        self.discovery_mode = discovery
        if discovery == "nats":
            self.discovery = NatsDiscoveryProvider(nats_url)
        elif discovery == "dht":
            self.discovery = DhtDiscoveryProvider(dht_port=dht_port)
        elif discovery in ("none", ""):
            self.discovery = None
        else:
            raise ValueError("discovery must be one of: nats, dht, none")

    async def start(self) -> None:
        await self.broadcaster.connect()
        if self.discovery:
            await self.discovery.connect()

    async def stop(self) -> None:
        if self.discovery:
            await self.discovery.disconnect()
        await self.broadcaster.disconnect()

