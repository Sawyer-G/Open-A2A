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
import json
import time
from dataclasses import dataclass
from typing import Any, Optional
from pathlib import Path

from open_a2a.opslog import log_event

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
    # Optional: persist dedupe cache to survive restarts.
    # Empty path disables persistence (default).
    dedupe_persist_path: str = ""
    dedupe_persist_interval_seconds: float = 2.0
    dedupe_max_items: int = 50000
    stats_interval_seconds: float = 10.0
    log_forward_samples: bool = False


class _DedupeCache:
    def __init__(
        self,
        ttl_seconds: float,
        *,
        persist_path: str = "",
        persist_interval_seconds: float = 2.0,
        max_items: int = 50000,
    ) -> None:
        self._ttl = float(ttl_seconds)
        self._items: dict[str, float] = {}
        self._persist_path = (persist_path or "").strip()
        self._persist_interval_seconds = float(persist_interval_seconds)
        self._max_items = int(max_items)
        self._dirty = False
        self._last_persist_ts = 0.0
        if self._persist_path:
            self._load_best_effort()

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
        self._dirty = True
        self._maybe_compact(now)
        return False

    def _maybe_compact(self, now_ts: float) -> None:
        if self._max_items <= 0:
            return
        if len(self._items) <= self._max_items:
            return
        # keep newest max_items entries
        keep = sorted(self._items.items(), key=lambda it: it[1], reverse=True)[: self._max_items]
        self._items = {k: ts for k, ts in keep}
        self._dirty = True

    def _load_best_effort(self) -> None:
        try:
            p = Path(self._persist_path)
            if not p.exists():
                return
            raw = p.read_text(encoding="utf-8", errors="ignore")
            doc = json.loads(raw) if raw else {}
            items = doc.get("items") if isinstance(doc, dict) else None
            if not isinstance(items, dict):
                return
            now = time.time()
            expired_before = now - self._ttl
            loaded: dict[str, float] = {}
            for k, v in items.items():
                try:
                    ts = float(v)
                except Exception:
                    continue
                if ts >= expired_before:
                    loaded[str(k)] = ts
            self._items = loaded
            self._dirty = False
        except Exception:
            return

    def persist_best_effort(self) -> None:
        if not self._persist_path:
            return
        now = time.time()
        if not self._dirty and (now - self._last_persist_ts) < self._persist_interval_seconds:
            return
        # prune before persist
        expired_before = now - self._ttl
        for k, ts in list(self._items.items()):
            if ts < expired_before:
                self._items.pop(k, None)
        self._maybe_compact(now)
        doc = {"items": self._items, "ts": now}
        try:
            p = Path(self._persist_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(p.suffix + ".tmp")
            tmp.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            tmp.replace(p)
            self._dirty = False
            self._last_persist_ts = now
        except Exception:
            return


class SubjectBridge:
    def __init__(self, cfg: BridgeConfig) -> None:
        if NATSClient is None:
            raise RuntimeError("nats-py is required. Install with: pip install nats-py")
        if not cfg.subjects:
            raise ValueError("SUBJECTS is empty; set OA2A_FED_SUBJECTS")
        self.cfg = cfg
        self._nc_a: Optional[Any] = None
        self._nc_b: Optional[Any] = None
        self._dedupe = _DedupeCache(
            cfg.dedupe_ttl_seconds,
            persist_path=cfg.dedupe_persist_path,
            persist_interval_seconds=cfg.dedupe_persist_interval_seconds,
            max_items=cfg.dedupe_max_items,
        )
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
        log_event(
            "open-a2a-subject-bridge",
            "info",
            "nats_connected",
            nats_a=self.cfg.nats_a,
            nats_b=self.cfg.nats_b,
        )

    async def disconnect(self) -> None:
        # best-effort persist dedupe state for restart continuity
        try:
            self._dedupe.persist_best_effort()
        except Exception:
            pass
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
            log_event(
                "open-a2a-subject-bridge",
                "warn",
                "forward_error",
                src=src,
                error=str(e),
                subject=subject,
            )

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
        log_event(
            "open-a2a-subject-bridge",
            "info",
            "bridge_started",
            bridge_id=self.cfg.bridge_id,
            subjects=self.cfg.subjects,
            max_hops=self.cfg.max_hops,
            dedupe_ttl_seconds=self.cfg.dedupe_ttl_seconds,
        )

        async def stats_task() -> None:
            while True:
                await asyncio.sleep(self.cfg.stats_interval_seconds)
                try:
                    self._dedupe.persist_best_effort()
                except Exception:
                    pass
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
                log_event(
                    "open-a2a-subject-bridge",
                    "info",
                    "stats",
                    **s,
                )

        t = asyncio.create_task(stats_task())
        try:
            await asyncio.Future()
        finally:
            t.cancel()


async def _run_ops_http(b: SubjectBridge, host: str, port: int) -> Any:
    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            line = await reader.readline()
            path = "/"
            try:
                parts = line.decode("utf-8", errors="ignore").split(" ")
                if len(parts) >= 2:
                    path = parts[1]
            except Exception:
                path = "/"
            if not (path.startswith("/healthz") or path.startswith("/metrics") or path.startswith("/")):
                body = b"not found"
                writer.write(
                    b"HTTP/1.1 404 Not Found\r\nContent-Length: "
                    + str(len(body)).encode("ascii")
                    + b"\r\n\r\n"
                    + body
                )
                await writer.drain()
                return

            async with b._lock:
                s = dict(b._stats)
            if path.startswith("/metrics"):
                bid = b.cfg.bridge_id.replace("\\", "\\\\").replace('"', '\\"')
                lines = [
                    "# HELP oa2a_fed_up Subject bridge process is up (1).",
                    "# TYPE oa2a_fed_up gauge",
                    f'oa2a_fed_up{{bridge_id="{bid}"}} 1',
                    "# HELP oa2a_fed_a_to_b_forwarded_total Forwarded messages from A to B.",
                    "# TYPE oa2a_fed_a_to_b_forwarded_total counter",
                    f'oa2a_fed_a_to_b_forwarded_total{{bridge_id="{bid}"}} {int(s.get("a_to_b_forwarded") or 0)}',
                    "# HELP oa2a_fed_b_to_a_forwarded_total Forwarded messages from B to A.",
                    "# TYPE oa2a_fed_b_to_a_forwarded_total counter",
                    f'oa2a_fed_b_to_a_forwarded_total{{bridge_id="{bid}"}} {int(s.get("b_to_a_forwarded") or 0)}',
                    "# HELP oa2a_fed_skipped_self_total Skipped messages forwarded by this bridge.",
                    "# TYPE oa2a_fed_skipped_self_total counter",
                    f'oa2a_fed_skipped_self_total{{bridge_id="{bid}"}} {int(s.get("skipped_self") or 0)}',
                    "# HELP oa2a_fed_skipped_hop_total Dropped due to hop limit.",
                    "# TYPE oa2a_fed_skipped_hop_total counter",
                    f'oa2a_fed_skipped_hop_total{{bridge_id="{bid}"}} {int(s.get("skipped_hop") or 0)}',
                    "# HELP oa2a_fed_skipped_dedupe_total Dropped due to dedupe.",
                    "# TYPE oa2a_fed_skipped_dedupe_total counter",
                    f'oa2a_fed_skipped_dedupe_total{{bridge_id="{bid}"}} {int(s.get("skipped_dedupe") or 0)}',
                    "# HELP oa2a_fed_errors_total Forward/publish errors.",
                    "# TYPE oa2a_fed_errors_total counter",
                    f'oa2a_fed_errors_total{{bridge_id="{bid}"}} {int(s.get("errors") or 0)}',
                    "# HELP oa2a_fed_config_max_hops Configured max hop limit.",
                    "# TYPE oa2a_fed_config_max_hops gauge",
                    f'oa2a_fed_config_max_hops{{bridge_id="{bid}"}} {int(b.cfg.max_hops)}',
                    "# HELP oa2a_fed_config_dedupe_ttl_seconds Configured dedupe TTL seconds.",
                    "# TYPE oa2a_fed_config_dedupe_ttl_seconds gauge",
                    f'oa2a_fed_config_dedupe_ttl_seconds{{bridge_id="{bid}"}} {float(b.cfg.dedupe_ttl_seconds)}',
                ]
                body = ("\n".join(lines) + "\n").encode("utf-8")
                writer.write(
                    b"HTTP/1.1 200 OK\r\n"
                    b"Content-Type: text/plain; version=0.0.4; charset=utf-8\r\n"
                    b"Cache-Control: no-store\r\n"
                    + f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
                    + body
                )
                await writer.drain()
                return

            payload = {
                "service": "open-a2a-subject-bridge",
                "status": "ok",
                "bridge_id": b.cfg.bridge_id,
                "nats_a": b.cfg.nats_a,
                "nats_b": b.cfg.nats_b,
                "subjects": b.cfg.subjects,
                "max_hops": b.cfg.max_hops,
                "dedupe_ttl_seconds": b.cfg.dedupe_ttl_seconds,
                "stats": s,
            }
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            writer.write(
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: application/json; charset=utf-8\r\n"
                b"Cache-Control: no-store\r\n"
                + f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
                + body
            )
            await writer.drain()
        except Exception:
            pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    import json

    return await asyncio.start_server(handler, host, port)


def _load_config() -> BridgeConfig:
    bridge_id = os.getenv("OA2A_FED_BRIDGE_ID", "x-y-bridge")
    nats_a = os.getenv("OA2A_FED_NATS_A", "nats://localhost:4222")
    nats_b = os.getenv("OA2A_FED_NATS_B", "nats://localhost:5222")
    # Default recommendation: only bridge intent subjects across operators.
    subjects = _split_subjects(os.getenv("OA2A_FED_SUBJECTS", "intent.>"))
    max_hops = int(os.getenv("OA2A_FED_MAX_HOPS", "1"))
    dedupe_ttl_seconds = float(os.getenv("OA2A_FED_DEDUPE_TTL_SECONDS", "3"))
    dedupe_persist_path = os.getenv("OA2A_FED_DEDUPE_PERSIST_PATH", "").strip()
    dedupe_persist_interval_seconds = float(
        os.getenv("OA2A_FED_DEDUPE_PERSIST_INTERVAL_SECONDS", "2")
    )
    dedupe_max_items = int(os.getenv("OA2A_FED_DEDUPE_MAX_ITEMS", "50000"))
    stats_interval_seconds = float(os.getenv("OA2A_FED_STATS_INTERVAL_SECONDS", "10"))
    log_forward_samples = _env_bool("OA2A_FED_LOG_FORWARD_SAMPLES", "0")
    return BridgeConfig(
        bridge_id=bridge_id,
        nats_a=nats_a,
        nats_b=nats_b,
        subjects=subjects,
        max_hops=max_hops,
        dedupe_ttl_seconds=dedupe_ttl_seconds,
        dedupe_persist_path=dedupe_persist_path,
        dedupe_persist_interval_seconds=dedupe_persist_interval_seconds,
        dedupe_max_items=dedupe_max_items,
        stats_interval_seconds=stats_interval_seconds,
        log_forward_samples=log_forward_samples,
    )


async def main() -> None:
    cfg = _load_config()
    b = SubjectBridge(cfg)
    await b.connect()
    ops = None
    if _env_bool("OA2A_FED_HTTP_ENABLE", "1"):
        host = os.getenv("OA2A_FED_HTTP_HOST", "127.0.0.1").strip() or "127.0.0.1"
        port = int(os.getenv("OA2A_FED_HTTP_PORT", "9464"))
        try:
            ops = await _run_ops_http(b, host, port)
            print(f"[FedBridge] ops endpoint: http://{host}:{port}/healthz")
        except Exception as e:
            print(f"[FedBridge] ops endpoint 启动失败（将继续运行桥接）：{e}")
    try:
        await b.run()
    finally:
        if ops:
            ops.close()
            await ops.wait_closed()
        await b.disconnect()


if __name__ == "__main__":
    asyncio.run(main())

