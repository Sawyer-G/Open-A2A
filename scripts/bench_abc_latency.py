#!/usr/bin/env python3
"""
Local A→B→C latency benchmark for Open-A2A examples.

Definition (most aligned with A→B→C):
- t0:   Consumer publishes the intent  ("[Consumer] 发布意图")
- t1:   Consumer receives first offer ("<- 收到报价:")
- t_end: Carrier completes delivery     ("[Carrier] 订单 ... 模拟送达")

We parse stdout logs of the three example agents and compute:
- time_to_first_offer_ms = (t1 - t0) * 1000
- end_to_end_abc_latency_ms = (t_end - t0) * 1000

Notes:
- Assumes NATS is already running and examples connect to nats://localhost:4222 by default.
- Uses wrapper-controlled monotonic timestamps, so it doesn't rely on synchronized clocks across terminals.
"""

from __future__ import annotations

import argparse
import csv
import os
import queue
import re
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, pstdev


CONS_INTENT_SUBSTR = "[Consumer] 发布意图"
CONS_OFFER_SUBSTR = "<- 收到报价:"
CONS_FLOW_COMPLETE_SUBSTR = "[Consumer] 订单已提交"

CARRIER_DELIVERED_SUBSTR = "[Carrier] 订单"
DELIVERED_KEYWORD = "模拟送达"

MERCHANT_LOGISTICS_REQ_SUBSTR = "[Merchant] 发布配送请求"


OFFER_RE = re.compile(
    r"<-\s*收到报价:\s*(?P<who>\S+)\s+(?P<price>[0-9]+(?:\.[0-9]+)?)\s+(?P<unit>\S+)"
)


@dataclass
class TrialResult:
    trial: int
    time_to_first_offer_ms: float | None
    end_to_end_abc_latency_ms: float | None
    time_logistics_req_to_delivery_ms: float | None
    offer_sender: str | None
    offer_price: str | None
    offer_unit: str | None
    t0_offset_s: float | None
    t1_offset_s: float | None
    tlogreq_offset_s: float | None
    tend_offset_s: float | None
    error: str | None


def _reader_thread(name: str, proc: subprocess.Popen[str], q: queue.Queue[tuple[str, float, str | None]]) -> None:
    assert proc.stdout is not None
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        q.put((name, time.monotonic(), line.rstrip("\n")))
    q.put((name, time.monotonic(), None))  # sentinel for this proc


def _start_make_target(make_target: str, cwd: Path, env: dict[str, str]) -> subprocess.Popen[str]:
    # Run in its own process group so we can terminate the whole tree.
    # preexec_fn is POSIX-specific, which is fine for macOS/Linux.
    return subprocess.Popen(
        ["make", make_target],
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        preexec_fn=os.setsid,
    )


def _stop_process(proc: subprocess.Popen[str], proc_name: str, timeout_s: float = 5.0) -> None:
    if proc.poll() is not None:
        return
    try:
        # SIGINT is friendly (your examples catch KeyboardInterrupt in a loop).
        os.killpg(proc.pid, signal.SIGINT)
    except Exception:
        try:
            proc.terminate()
        except Exception:
            pass
    try:
        proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except Exception:
            proc.kill()


def run_trials(trials: int, timeout_s: float, startup_wait_s: float, output_csv: Path, verbose: bool) -> list[TrialResult]:
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    repo_root = Path(__file__).resolve().parents[1]  # Open-A2A/

    results: list[TrialResult] = []

    for trial in range(1, trials + 1):
        # Wrapper-controlled parsing timestamps (monotonic)
        q: queue.Queue[tuple[str, float, str | None]] = queue.Queue()

        env = os.environ.copy()
        env.setdefault("NATS_URL", "nats://localhost:4222")
        # Help stdout flushing from child python processes.
        env["PYTHONUNBUFFERED"] = "1"

        merchant = _start_make_target("run-merchant", repo_root, env)
        carrier = _start_make_target("run-carrier", repo_root, env)
        time.sleep(startup_wait_s)

        consumer_mode = env.get("OPEN_A2A_CONSUMER_MODE", "direct")
        # consumer_mode:
        # - direct: run example/consumer.py via make run-consumer
        # - via_relay_full: run example/consumer_via_relay_full.py directly (Relay + OrderConfirm)
        if consumer_mode == "via_relay_full":
            venv_python = repo_root / ".venv" / "bin" / "python"
            consumer = subprocess.Popen(
                [str(venv_python), "example/consumer_via_relay_full.py"],
                cwd=str(repo_root),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                preexec_fn=os.setsid,
            )
        else:
            consumer = _start_make_target("run-consumer", repo_root, env)

        # Reader threads for each proc
        threads = [
            threading.Thread(target=_reader_thread, args=("merchant", merchant, q), daemon=True),
            threading.Thread(target=_reader_thread, args=("carrier", carrier, q), daemon=True),
            threading.Thread(target=_reader_thread, args=("consumer", consumer, q), daemon=True),
        ]
        for t in threads:
            t.start()

        trial_start = time.monotonic()
        t0: float | None = None
        t1: float | None = None
        tlogreq: float | None = None
        tend: float | None = None
        offer_sender: str | None = None
        offer_price: str | None = None
        offer_unit: str | None = None

        # Track proc sentinels so we don't hang on missing streams.
        finished_procs: set[str] = set()
        error: str | None = None

        if verbose:
            print(f"\n=== Trial {trial} ===")

        while True:
            # Timeout
            if time.monotonic() - trial_start > timeout_s:
                error = f"timeout>{timeout_s}s (missing events)"
                break

            try:
                name, ts, line = q.get(timeout=0.2)
            except queue.Empty:
                continue

            if line is None:
                finished_procs.add(name)
                # If all procs finished but we never got tend, consider it failure.
                if len(finished_procs) == 3 and tend is None:
                    error = "processes finished but no carrier simulated delivery detected"
                    break
                continue

            if verbose:
                print(f"[{name}] {line}")

            # t0: consumer intent publish
            if t0 is None and (CONS_INTENT_SUBSTR in line):
                t0 = ts

            # t1: first offer arrival
            if t1 is None and (CONS_OFFER_SUBSTR in line):
                t1 = ts
                m = OFFER_RE.search(line)
                if m:
                    offer_sender = m.group("who")
                    offer_price = m.group("price")
                    offer_unit = m.group("unit")

            # tlogreq: merchant publishes logistics request (B -> C trigger)
            if tlogreq is None and (MERCHANT_LOGISTICS_REQ_SUBSTR in line):
                tlogreq = ts

            # t_end: carrier delivery completion
            if tend is None and (CARRIER_DELIVERED_SUBSTR in line) and (DELIVERED_KEYWORD in line):
                tend = ts
                # Success: we can stop the other long-running agents.
                break

        # Cleanup
        _stop_process(merchant, "merchant")
        _stop_process(carrier, "carrier")
        _stop_process(consumer, "consumer", timeout_s=2.0)

        if t0 is None:
            # Without t0 we can't compute latencies.
            results.append(
                TrialResult(
                    trial=trial,
                    time_to_first_offer_ms=None,
                    end_to_end_abc_latency_ms=None,
                    time_logistics_req_to_delivery_ms=None,
                    offer_sender=offer_sender,
                    offer_price=offer_price,
                    offer_unit=offer_unit,
                    t0_offset_s=None,
                    t1_offset_s=(t1 - t0) if (t1 is not None and t0 is not None) else None,
                    tlogreq_offset_s=(tlogreq - trial_start) if tlogreq is not None else None,
                    tend_offset_s=(tend - t0) if (tend is not None and t0 is not None) else None,
                    error=error or "missing consumer intent event",
                )
            )
            continue

        time_to_first_offer_ms = (t1 - t0) * 1000 if t1 is not None else None
        end_to_end_abc_latency_ms = (tend - t0) * 1000 if tend is not None else None
        time_logistics_req_to_delivery_ms = (tend - tlogreq) * 1000 if (tend is not None and tlogreq is not None) else None

        results.append(
            TrialResult(
                trial=trial,
                time_to_first_offer_ms=time_to_first_offer_ms,
                end_to_end_abc_latency_ms=end_to_end_abc_latency_ms,
                time_logistics_req_to_delivery_ms=time_logistics_req_to_delivery_ms,
                offer_sender=offer_sender,
                offer_price=offer_price,
                offer_unit=offer_unit,
                t0_offset_s=(t0 - trial_start),
                t1_offset_s=((t1 - trial_start) if t1 is not None else None),
                tlogreq_offset_s=((tlogreq - trial_start) if tlogreq is not None else None),
                tend_offset_s=((tend - trial_start) if tend is not None else None),
                error=error,
            )
        )

        # Drain the queue quickly (best-effort) before next trial.
        while not q.empty():
            try:
                q.get_nowait()
            except queue.Empty:
                break

    # Write CSV
    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "trial",
                "time_to_first_offer_ms",
                "end_to_end_abc_latency_ms",
                "time_logistics_req_to_delivery_ms",
                "offer_sender",
                "offer_price",
                "offer_unit",
                "t0_offset_s",
                "t1_offset_s",
                "tlogreq_offset_s",
                "tend_offset_s",
                "error",
            ]
        )
        for r in results:
            writer.writerow(
                [
                    r.trial,
                    r.time_to_first_offer_ms if r.time_to_first_offer_ms is not None else "",
                    r.end_to_end_abc_latency_ms if r.end_to_end_abc_latency_ms is not None else "",
                    r.time_logistics_req_to_delivery_ms if r.time_logistics_req_to_delivery_ms is not None else "",
                    r.offer_sender or "",
                    r.offer_price or "",
                    r.offer_unit or "",
                    "" if r.t0_offset_s is None else r.t0_offset_s,
                    "" if r.t1_offset_s is None else r.t1_offset_s,
                    "" if r.tlogreq_offset_s is None else r.tlogreq_offset_s,
                    "" if r.tend_offset_s is None else r.tend_offset_s,
                    r.error or "",
                ]
            )

    # Summary (ignore failures where metric is missing)
    valid_t1 = [r.time_to_first_offer_ms for r in results if r.time_to_first_offer_ms is not None]
    valid_tend = [r.end_to_end_abc_latency_ms for r in results if r.end_to_end_abc_latency_ms is not None]
    valid_tlog_to_delivery = [r.time_logistics_req_to_delivery_ms for r in results if r.time_logistics_req_to_delivery_ms is not None]

    def _stat(x: list[float]) -> tuple[float, float]:
        if not x:
            return (float("nan"), float("nan"))
        if len(x) == 1:
            return (x[0], 0.0)
        # population stddev (pstdev) is fine for a benchmark sample; switch to stdev if you prefer.
        return (mean(x), pstdev(x))

    t1_mean, t1_std = _stat(valid_t1)
    tend_mean, tend_std = _stat(valid_tend)
    tlog_to_delivery_mean, tlog_to_delivery_std = _stat(valid_tlog_to_delivery)

    print("\n=== Summary (local A→B→C) ===")
    print(f"Output CSV: {output_csv}")
    print(f"Trials: {trials} | Valid time_to_first_offer: {len(valid_t1)}/{trials}")
    print(f"Time to first offer (local): mean={t1_mean:.2f} ms, std={t1_std:.2f} ms")
    print(f"Valid end_to_end_abc_latency: {len(valid_tend)}/{trials}")
    print(f"End-to-end A→B→C latency (local): mean={tend_mean:.2f} ms, std={tend_std:.2f} ms")
    print(f"Valid logistics_req_to_delivery: {len(valid_tlog_to_delivery)}/{trials}")
    print(
        f"Protocol-aligned latency (logistics request → carrier delivery): "
        f"mean={tlog_to_delivery_mean:.2f} ms, std={tlog_to_delivery_std:.2f} ms"
    )

    print(
        "\nSuggested table fill:\n"
        f"- Time to first offer (local) \\textbf{{{t1_mean:.0f}}} ms (std {t1_std:.0f})\n"
        f"- End-to-end A--B--C latency \\textbf{{{tend_mean:.0f}}} ms (std {tend_std:.0f})\n"
        f"- Logistics request → carrier delivery \\textbf{{{tlog_to_delivery_mean:.0f}}} ms (std {tlog_to_delivery_std:.0f})\n"
    )

    return results


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=10, help="number of repeated local runs")
    ap.add_argument("--timeout", type=float, default=35.0, help="per-trial timeout seconds")
    ap.add_argument("--startup-wait", type=float, default=1.0, help="seconds to wait after starting merchant+carrier")
    ap.add_argument(
        "--output",
        type=str,
        default="../open-a2a-research/paper/benchmarks/abc_latency_local.csv",
        help="CSV output path (relative to Open-A2A repo root is OK)",
    )
    ap.add_argument("--verbose", action="store_true", help="print logs during trials")
    ap.add_argument(
        "--consumer-mode",
        type=str,
        default="direct",
        choices=["direct", "via_relay_full"],
        help="consumer execution mode",
    )
    ap.add_argument("--nats-url", type=str, default=None, help="NATS connection string for merchant/carrier (and direct consumer)")
    ap.add_argument("--relay-ws-url", type=str, default=None, help="Relay WS URL for via_relay_full consumer")
    args = ap.parse_args()

    # Resolve output relative to Open-A2A repo root
    repo_root = Path(__file__).resolve().parents[1]
    output_csv = Path(args.output)
    if not output_csv.is_absolute():
        output_csv = (repo_root / output_csv).resolve()

    # Inject selected mode into env read by run_trials
    os.environ["OPEN_A2A_CONSUMER_MODE"] = args.consumer_mode
    if args.nats_url:
        os.environ["NATS_URL"] = args.nats_url
    if args.relay_ws_url:
        os.environ["RELAY_WS_URL"] = args.relay_ws_url

    run_trials(
        trials=args.trials,
        timeout_s=args.timeout,
        startup_wait_s=args.startup_wait,
        output_csv=output_csv,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()

