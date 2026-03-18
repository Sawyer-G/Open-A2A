import asyncio
import importlib
import time
from typing import Dict, Optional, Set, Tuple, Union

import pytest


class FakeRedis:
    """
    Minimal async Redis stub for bridge registry tests.

    Supports the subset of commands used by bridge/main.py.
    """

    def __init__(self) -> None:
        self._kv: Dict[str, Tuple[bytes, Optional[int]]] = {}  # key -> (value_bytes, exat_ts)
        self._z: Dict[str, Dict[str, float]] = {}  # key -> member -> score
        self._s: Dict[str, Set[str]] = {}  # key -> members

    def _now(self) -> float:
        return time.time()

    def _is_expired(self, exat: Optional[int]) -> bool:
        return exat is not None and exat <= int(self._now())

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        return None

    async def set(self, key: str, value: str, exat: Optional[int] = None) -> None:
        self._kv[key] = (value.encode("utf-8"), exat)

    async def get(self, key: str) -> Optional[bytes]:
        item = self._kv.get(key)
        if not item:
            return None
        raw, exat = item
        if self._is_expired(exat):
            self._kv.pop(key, None)
            return None
        return raw

    async def mget(self, keys: list[str]) -> list[Optional[bytes]]:
        out: list[Optional[bytes]] = []
        for k in keys:
            out.append(await self.get(k))
        return out

    async def delete(self, key: str) -> None:
        self._kv.pop(key, None)

    async def sadd(self, key: str, *members: str) -> None:
        self._s.setdefault(key, set()).update([str(m) for m in members])

    async def smembers(self, key: str) -> Set[bytes]:
        return {m.encode("utf-8") for m in self._s.get(key, set())}

    async def zadd(self, key: str, mapping: dict[str, float]) -> None:
        z = self._z.setdefault(key, {})
        for member, score in mapping.items():
            z[str(member)] = float(score)

    async def zrem(self, key: str, *members: str) -> None:
        z = self._z.get(key, {})
        for m in members:
            z.pop(str(m), None)

    async def zrangebyscore(
        self, key: str, min: Union[float, str], max: Union[float, str]
    ) -> list[bytes]:
        z = self._z.get(key, {})
        min_v = float("-inf") if min == "-inf" else float(min)
        max_v = float("inf") if max in ("+inf", "inf") else float(max)
        items = [(m, s) for m, s in z.items() if s >= min_v and s <= max_v]
        items.sort(key=lambda x: x[1])
        return [m.encode("utf-8") for m, _ in items]

    async def zcount(self, key: str, min: Union[float, str], max: Union[float, str]) -> int:
        ids = await self.zrangebyscore(key, min=min, max=max)
        return len(ids)


def test_bridge_redis_registry_upsert_list_stats_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    async def run() -> None:
        """
        Validate that the redis backend stores registrations, indexes by capability,
        and supports stats + expiration cleanup.
        """
        monkeypatch.setenv("BRIDGE_DISCOVERY_REDIS_URL", "redis://fake:6379/0")
        from bridge import main as bridge_main

        importlib.reload(bridge_main)

        fake = FakeRedis()
        bridge_main._redis = fake

        now = time.time()
        reg_a = bridge_main._Registration(
            agent_id="a",
            capabilities=["intent.food.order", "intent.logistics.request"],
            meta={"agent_id": "a", "did": "did:key:a", "proof": {"type": "jws"}},
            expires_at_ts=now + 10,
            updated_at="t1",
        )
        reg_b = bridge_main._Registration(
            agent_id="b",
            capabilities=["intent.food.order"],
            meta={"agent_id": "b", "did": "", "proof": None},
            expires_at_ts=now + 10,
            updated_at="t2",
        )
        await bridge_main._redis_upsert_registration(reg_a)
        await bridge_main._redis_upsert_registration(reg_b)

        metas = await bridge_main._redis_list_active_metas_for_capability("intent.food.order")
        assert {m["agent_id"] for m in metas} == {"a", "b"}

        total, verified, by_cap = await bridge_main._redis_stats()
        assert total == 2
        assert verified == 1
        assert by_cap["intent.food.order"] == 2
        assert by_cap["intent.logistics.request"] == 1

        # expire one agent and cleanup
        reg_b2 = bridge_main._Registration(
            agent_id="b",
            capabilities=["intent.food.order"],
            meta={"agent_id": "b", "did": "", "proof": None},
            expires_at_ts=now - 1,
            updated_at="t3",
        )
        await bridge_main._redis_upsert_registration(reg_b2)
        await bridge_main._redis_cleanup_expired()

        metas2 = await bridge_main._redis_list_active_metas_for_capability("intent.food.order")
        assert {m["agent_id"] for m in metas2} == {"a"}

        total2, verified2, by_cap2 = await bridge_main._redis_stats()
        assert total2 == 1
        assert verified2 == 1
        assert by_cap2["intent.food.order"] == 1

    asyncio.run(run())

