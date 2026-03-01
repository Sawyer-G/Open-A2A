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

from open_a2a.preferences import (
    FilePreferencesProvider,
    PreferencesProvider,
    SolidPodPreferencesProvider,
)
from open_a2a.transport import TransportAdapter
from open_a2a.transport_nats import NatsTransportAdapter
from open_a2a.discovery import DiscoveryProvider, DISCOVERY_QUERY_PREFIX
from open_a2a.discovery_nats import NatsDiscoveryProvider

try:
    from open_a2a.transport_relay import RelayClientTransport
except ImportError:
    RelayClientTransport = None  # type: ignore

try:
    from open_a2a.transport_encrypt import EncryptedTransportAdapter
except ImportError:
    EncryptedTransportAdapter = None  # type: ignore

try:
    from open_a2a.discovery_dht import (
        DhtDiscoveryProvider,
        get_default_dht_bootstrap,
        DEFAULT_DHT_BOOTSTRAP,
        ENV_DHT_BOOTSTRAP,
    )
except ImportError:
    DhtDiscoveryProvider = None  # type: ignore
    get_default_dht_bootstrap = None  # type: ignore
    DEFAULT_DHT_BOOTSTRAP = []  # type: ignore
    ENV_DHT_BOOTSTRAP = "OPEN_A2A_DHT_BOOTSTRAP"  # type: ignore

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
    "SolidPodPreferencesProvider",
    "TransportAdapter",
    "NatsTransportAdapter",
    "DiscoveryProvider",
    "NatsDiscoveryProvider",
    "DhtDiscoveryProvider",
    "get_default_dht_bootstrap",
    "DEFAULT_DHT_BOOTSTRAP",
    "ENV_DHT_BOOTSTRAP",
    "DISCOVERY_QUERY_PREFIX",
    "RelayClientTransport",
    "EncryptedTransportAdapter",
]

__version__ = "0.1.0"
