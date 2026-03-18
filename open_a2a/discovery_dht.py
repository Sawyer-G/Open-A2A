"""
DHT 发现实现（跨网络、去中心化索引）

基于 Kademlia DHT：能力注册/发现写入分布式哈希表，不依赖「同一 NATS」。
适用于不同 NATS 集群、不同传输的 Agent 互相发现（DPI 思路，见需求文档）。

Bootstrap：可通过环境变量 OPEN_A2A_DHT_BOOTSTRAP 或公共列表加入同一 DHT 网。
"""

import asyncio
import json
import os
import time
import uuid
from typing import Any, List, Optional, Tuple

from open_a2a.discovery import DiscoveryProvider

try:
    from kademlia.network import Server as KademliaServer
except ImportError:
    KademliaServer = None  # type: ignore

DHT_KEY_PREFIX = "open_a2a:discovery:"
# Directory-quality TTL (seconds). Clients should renew periodically.
# This is NOT enforced by the DHT layer itself; we embed expires_at_ts in each record and filter on read.
DHT_VALUE_TTL = 300

# 公共 bootstrap 列表（预留）：社区或项目提供的长期节点，使所有人加入同一 DHT 网。
# 当前为空；后续可在此或通过 OPEN_A2A_DHT_BOOTSTRAP 配置。
DEFAULT_DHT_BOOTSTRAP: List[Tuple[str, int]] = []

ENV_DHT_BOOTSTRAP = "OPEN_A2A_DHT_BOOTSTRAP"


def get_default_dht_bootstrap() -> List[Tuple[str, int]]:
    """
    获取默认 DHT bootstrap 节点列表。

    优先读环境变量 OPEN_A2A_DHT_BOOTSTRAP，格式：host1:port1,host2:port2
    未设置时返回 DEFAULT_DHT_BOOTSTRAP（可预置公共节点）。
    """
    raw = os.getenv(ENV_DHT_BOOTSTRAP, "").strip()
    if not raw:
        return list(DEFAULT_DHT_BOOTSTRAP)
    result: List[Tuple[str, int]] = []
    for part in raw.split(","):
        part = part.strip()
        if ":" in part:
            host, port_str = part.rsplit(":", 1)
            try:
                result.append((host.strip(), int(port_str.strip())))
            except ValueError:
                continue
    return result if result else list(DEFAULT_DHT_BOOTSTRAP)


def _dht_key(capability: str) -> str:
    return f"{DHT_KEY_PREFIX}{capability}"


def _now_ts() -> float:
    return time.time()


def _prune_records(lst: list[dict[str, Any]], *, now_ts: float) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for x in lst:
        if not isinstance(x, dict):
            continue
        exp = x.get("_expires_at_ts")
        try:
            exp_ts = float(exp) if exp is not None else None
        except (TypeError, ValueError):
            exp_ts = None
        if exp_ts is None or exp_ts > now_ts:
            out.append(x)
    return out


class DhtDiscoveryProvider(DiscoveryProvider):
    """
    基于 Kademlia DHT 的发现实现

    各 Agent 运行本机 DHT 节点并连接公共或自建 bootstrap，
    注册/发现通过 DHT 读写，与 NATS 集群无关，实现跨网络发现。
    """

    def __init__(
        self,
        dht_port: int = 8468,
        bootstrap_nodes: Optional[List[Tuple[str, int]]] = None,
    ) -> None:
        if KademliaServer is None:
            raise ImportError(
                "kademlia is required for DHT discovery. Install with: pip install open-a2a[dht]"
            )
        self._dht_port = dht_port
        self._bootstrap = (
            bootstrap_nodes if bootstrap_nodes is not None else get_default_dht_bootstrap()
        )
        self._node: Optional[KademliaServer] = None
        self._my_regs: dict[str, str] = {}  # capability -> _reg_id

    async def connect(self) -> None:
        self._node = KademliaServer()
        await self._node.listen(self._dht_port)
        if self._bootstrap:
            await self._node.bootstrap(self._bootstrap)

    async def disconnect(self) -> None:
        if self._node:
            self._node.stop()
            self._node = None
        self._my_regs.clear()

    async def register(self, capability: str, meta: dict[str, Any]) -> None:
        if not self._node:
            raise RuntimeError("Not connected. Call connect() first.")
        key = _dht_key(capability)
        reg_id = self._my_regs.get(capability) or uuid.uuid4().hex
        self._my_regs[capability] = reg_id

        now_ts = _now_ts()
        expires_at_ts = now_ts + float(DHT_VALUE_TTL)
        meta_with_id = {**meta, "_reg_id": reg_id, "_expires_at_ts": expires_at_ts}

        try:
            raw = await self._node.get(key)
            lst: list[dict[str, Any]] = json.loads(raw) if raw else []
        except (TypeError, json.JSONDecodeError):
            lst = []
        if not isinstance(lst, list):
            lst = []

        # Prune expired and "renew" by replacing the same _reg_id if it exists.
        lst2 = _prune_records([x for x in lst if isinstance(x, dict)], now_ts=now_ts)
        lst2 = [x for x in lst2 if x.get("_reg_id") != reg_id]
        lst2.append(meta_with_id)
        await self._node.set(key, json.dumps(lst2, ensure_ascii=False))

    async def unregister(self, capability: str) -> None:
        if not self._node:
            return
        reg_id = self._my_regs.pop(capability, None)
        if reg_id is None:
            return
        key = _dht_key(capability)
        try:
            raw = await self._node.get(key)
            lst: list[dict[str, Any]] = json.loads(raw) if raw else []
        except (TypeError, json.JSONDecodeError):
            return
        if not isinstance(lst, list):
            return
        new_lst = [x for x in lst if isinstance(x, dict) and x.get("_reg_id") != reg_id]
        if new_lst:
            await self._node.set(key, json.dumps(new_lst, ensure_ascii=False))
        else:
            await self._node.set(key, json.dumps([]))

    async def discover(self, capability: str, timeout_seconds: float = 5.0) -> list[dict[str, Any]]:
        if not self._node:
            raise RuntimeError("Not connected. Call connect() first.")
        key = _dht_key(capability)
        try:
            raw = await asyncio.wait_for(self._node.get(key), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            return []
        if not raw:
            return []
        try:
            lst = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if not isinstance(lst, list):
            return []

        now_ts = _now_ts()
        kept = _prune_records([x for x in lst if isinstance(x, dict)], now_ts=now_ts)
        # Best-effort hygiene: write back pruned list to reduce zombie records.
        if len(kept) != len([x for x in lst if isinstance(x, dict)]):
            try:
                await self._node.set(key, json.dumps(kept, ensure_ascii=False))
            except Exception:
                pass

        # 去掉内部字段，只返回对外 meta
        return [{k: v for k, v in x.items() if not k.startswith("_")} for x in kept]
