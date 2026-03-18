#!/usr/bin/env python3
"""
Open-A2A Subject Bridge (X <-> Y)

Minimal "federation" implementation for independent NATS servers:
- Connect to two NATS servers (side A and side B)
- Subscribe to an allowlist of subjects on both sides
- Forward messages across, with loop/storm protection:
  - Headers: X-OA2A-Bridge, X-OA2A-Hop
  - Dedupe (in-memory, TTL) to suppress accidental loops
- Periodic stats logs for operational observability

This intentionally stays at the protocol/infrastructure layer: it forwards subjects, not business semantics.
"""

import asyncio
import hashlib
import os
import time
from dataclasses import dataclass
from typing import Any, Optional

try:
    from nats.aio.client import Client as NATSClient
except ImportError:
    NATSClient = None  # type: ignore


def _env_bool(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "y")


def _split_subjects(value: str) -> list[str]:
    out: list[str] = []
    for s in (value or "").split(","):
        s = s.strip()
        if s:
            out.append(s)
    return out


@dataclass
class BridgeConfig:
    bridge_id: str
    nats_a: str
    nats_b: str
    subjects: list[str]
    max_hops: int
    dedupe_ttl_seconds: float
    stats_interval_seconds: float
    log_forward_samples: bool


class _DedupeCache:
    def __init__(self, ttl_seconds: float) -> None:
        self._ttl = float(ttl_seconds)
        self._items: dict[str, float] = {}

    def seen_recently(self, key: str) -> bool:
        now = time.time()
        expired_before = now - self._ttl
        # simple sweep (TTL cache size is expected to be small for MVP)
        for k, ts in list(self._items.items()):
            if ts < expired_before:
                self._items.pop(k, None)
        if key in self._items:
            return True
        self._items[key] = now
        return False


class SubjectBridge:
    def __init__(self, cfg: BridgeConfig) -> None:
        if NATSClient is None:
            raise RuntimeError("nats-py is required. Install with: pip install nats-py")
        if not cfg.subjects:
            raise ValueError("SUBJECTS is empty; set OA2A_FED_SUBJECTS")
        self.cfg = cfg
        self._nc_a: Optional[Any] = None
        self._nc_b: Optional[Any] = None
        self._dedupe = _DedupeCache(cfg.dedupe_ttl_seconds)
        self._lock = asyncio.Lock()
        self._stats = {
            "a_to_b_forwarded": 0,
            "b_to_a_forwarded": 0,
            "skipped_hop": 0,
            "skipped_self": 0,
            "skipped_dedupe": 0,
            "errors": 0,
        }

    async def connect(self) -> None:
        self._nc_a = NATSClient()
        self._nc_b = NATSClient()
        await self._nc_a.connect(self.cfg.nats_a)
        await self._nc_b.connect(self.cfg.nats_b)
        print(f"[FedBridge] connected: A={self.cfg.nats_a}  B={self.cfg.nats_b}")

    async def disconnect(self) -> None:
        if self._nc_a:
            await self._nc_a.drain()
            self._nc_a = None
        if self._nc_b:
            await self._nc_b.drain()
            self._nc_b = None

    def _msg_key(self, subject: str, data: bytes, headers: Optional[dict[str, str]]) -> str:
        h = hashlib.sha256()
        h.update(subject.encode("utf-8"))
        h.update(b"\0")
        h.update(data)
        # headers are not fully stable across libs; only include our loop-control keys
        if headers:
            for k in ("X-OA2A-Bridge", "X-OA2A-Hop"):
                v = headers.get(k)
                if v is not None:
                    h.update(b"\0")
                    h.update(k.encode("utf-8"))
                    h.update(b"=")
                    h.update(v.encode("utf-8"))
        return h.hexdigest()

    async def _forward(self, src: str, msg: Any) -> None:
        """
        src: "A" or "B"
        forward direction is determined by src
        """
        nc_src = self._nc_a if src == "A" else self._nc_b
        nc_dst = self._nc_b if src == "A" else self._nc_a
        if not nc_src or not nc_dst:
            return

        subject = msg.subject
        data = msg.data
        headers_in = dict(msg.headers or {})

        # 1) loop protection: skip messages we forwarded ourselves
        if headers_in.get("X-OA2A-Bridge") == self.cfg.bridge_id:
            async with self._lock:
                self._stats["skipped_self"] += 1
            return

        # 2) hop limit
        try:
            hop = int(headers_in.get("X-OA2A-Hop", "0") or "0")
        except ValueError:
            hop = 0
        if hop >= self.cfg.max_hops:
            async with self._lock:
                self._stats["skipped_hop"] += 1
            return

        # 3) dedupe (best-effort)
        key = self._msg_key(subject, data, headers_in)
        if self._dedupe.seen_recently(key):
            async with self._lock:
                self._stats["skipped_dedupe"] += 1
            return

        headers_out = dict(headers_in)
        headers_out["X-OA2A-Bridge"] = self.cfg.bridge_id
        headers_out["X-OA2A-Hop"] = str(hop + 1)

        try:
            await nc_dst.publish(subject, data, headers=headers_out)
            async with self._lock:
                if src == "A":
                    self._stats["a_to_b_forwarded"] += 1
                else:
                    self._stats["b_to_a_forwarded"] += 1
            if self.cfg.log_forward_samples:
                print(f"[FedBridge] {src} -> {'B' if src == 'A' else 'A'}  {subject}  bytes={len(data)}")
        except Exception as e:
            async with self._lock:
                self._stats["errors"] += 1
            print(f"[FedBridge] forward error ({src}): {e}")

    async def run(self) -> None:
        if not self._nc_a or not self._nc_b:
            raise RuntimeError("not connected")

        async def handler_a(msg: Any) -> None:
            await self._forward("A", msg)

        async def handler_b(msg: Any) -> None:
            await self._forward("B", msg)

        for subj in self.cfg.subjects:
            await self._nc_a.subscribe(subj, cb=handler_a)
            await self._nc_b.subscribe(subj, cb=handler_b)
        print(f"[FedBridge] subjects: {', '.join(self.cfg.subjects)}")
        print(
            "[FedBridge] loop control: headers X-OA2A-Bridge / X-OA2A-Hop; "
            f"max_hops={self.cfg.max_hops}; dedupe_ttl={self.cfg.dedupe_ttl_seconds}s"
        )

        async def stats_task() -> None:
            while True:
                await asyncio.sleep(self.cfg.stats_interval_seconds)
                async with self._lock:
                    s = dict(self._stats)
                print(
                    "[FedBridge][stats] "
                    f"a->b={s['a_to_b_forwarded']} "
                    f"b->a={s['b_to_a_forwarded']} "
                    f"skip_self={s['skipped_self']} "
                    f"skip_hop={s['skipped_hop']} "
                    f"skip_dedupe={s['skipped_dedupe']} "
                    f"errors={s['errors']}"
                )

        t = asyncio.create_task(stats_task())
        try:
            await asyncio.Future()
        finally:
            t.cancel()


def _load_config() -> BridgeConfig:
    bridge_id = os.getenv("OA2A_FED_BRIDGE_ID", "x-y-bridge")
    nats_a = os.getenv("OA2A_FED_NATS_A", "nats://localhost:4222")
    nats_b = os.getenv("OA2A_FED_NATS_B", "nats://localhost:5222")
    # Default recommendation: only bridge intent subjects across operators.
    subjects = _split_subjects(os.getenv("OA2A_FED_SUBJECTS", "intent.>"))
    max_hops = int(os.getenv("OA2A_FED_MAX_HOPS", "1"))
    dedupe_ttl_seconds = float(os.getenv("OA2A_FED_DEDUPE_TTL_SECONDS", "3"))
    stats_interval_seconds = float(os.getenv("OA2A_FED_STATS_INTERVAL_SECONDS", "10"))
    log_forward_samples = _env_bool("OA2A_FED_LOG_FORWARD_SAMPLES", "0")
    return BridgeConfig(
        bridge_id=bridge_id,
        nats_a=nats_a,
        nats_b=nats_b,
        subjects=subjects,
        max_hops=max_hops,
        dedupe_ttl_seconds=dedupe_ttl_seconds,
        stats_interval_seconds=stats_interval_seconds,
        log_forward_samples=log_forward_samples,
    )


async def main() -> None:
    cfg = _load_config()
    b = SubjectBridge(cfg)
    await b.connect()
    try:
        await b.run()
    finally:
        await b.disconnect()


if __name__ == "__main__":
    asyncio.run(main())

