#!/usr/bin/env python3
"""
Consumer-only "time to first offer" benchmark for Open-A2A Relay scenarios.

Why consumer-only?
- In cross-IP / relay-mediated validation, merchant and carrier are expected to
  run on the public node (where NATS is reachable).
- From the consumer side we only need to measure:
    t0: consumer intent publish line
    t1: first offer arrival line

We parse stdout from the consumer process and compute:
- time_to_first_offer_ms = (t1 - t0) * 1000
"""

from __future__ import annotations

import argparse
import csv
import os
import queue
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, pstdev


CONS_INTENT_SUBSTR = "[Consumer] 发布意图"
CONS_OFFER_SUBSTR = "<- 收到报价:"
CONS_FLOW_COMPLETE_SUBSTR = "[Consumer] 订单已提交"

OFFER_RE = re.compile(
    r"<-\s*收到报价:\s*(?P<who>\S+)\s+(?P<price>[0-9]+(?:\.[0-9]+)?)\s+(?P<unit>\S+)"
)


@dataclass
class TrialResult:
    trial: int
    time_to_first_offer_ms: float | None
    offer_sender: str | None
    offer_price: str | None
    offer_unit: str | None
    t0_offset_s: float | None
    t1_offset_s: float | None
    tend_offset_s: float | None
    error: str | None


def _reader_thread(
    name: str,
    proc: subprocess.Popen[str],
    q: "queue.Queue[tuple[str, float, str | None]]",
) -> None:
    assert proc.stdout is not None
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        q.put((name, time.monotonic(), line.rstrip("\n")))
    q.put((name, time.monotonic(), None))  # sentinel


def _stop_process(proc: subprocess.Popen[str], timeout_s: float = 5.0) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, 2)  # SIGINT
    except Exception:
        try:
            proc.terminate()
        except Exception:
            pass
    try:
        proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, 9)  # SIGKILL
        except Exception:
            proc.kill()


def run_trials(
    *,
    trials: int,
    timeout_s: float,
    startup_wait_s: float,
    consumer_script: str,
    relay_ws_url: str,
    output_csv: Path,
    constraints: str,
    consumer_id: str,
    verbose: bool,
    repo_root: Path,
) -> list[TrialResult]:
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    results: list[TrialResult] = []
    for trial in range(1, trials + 1):
        q: "queue.Queue[tuple[str, float, str | None]]" = queue.Queue()

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["RELAY_WS_URL"] = relay_ws_url
        env["CONSTRAINTS"] = constraints
        env["CONSUMER_ID"] = consumer_id

        # Consumer-only benchmark: merchant/carrier are assumed to be running on the public node.
        consumer = subprocess.Popen(
            ["python3", consumer_script],
            cwd=str(repo_root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            preexec_fn=os.setsid,
        )

        reader = threading.Thread(target=_reader_thread, args=("consumer", consumer, q), daemon=True)
        reader.start()

        if startup_wait_s > 0:
            time.sleep(startup_wait_s)

        trial_start = time.monotonic()
        t0: float | None = None
        t1: float | None = None
        tend: float | None = None
        offer_sender: str | None = None
        offer_price: str | None = None
        offer_unit: str | None = None
        error: str | None = None

        while True:
            if time.monotonic() - trial_start > timeout_s:
                error = f"timeout>{timeout_s}s (missing events)"
                break

            try:
                _, ts, line = q.get(timeout=0.2)
            except queue.Empty:
                continue

            if line is None:
                # Consumer finished; if we never saw completion, treat it as failure for clarity.
                break

            if verbose:
                print(f"[consumer] {line}")

            if t0 is None and (CONS_INTENT_SUBSTR in line):
                t0 = ts

            if t1 is None and (CONS_OFFER_SUBSTR in line):
                t1 = ts
                m = OFFER_RE.search(line)
                if m:
                    offer_sender = m.group("who")
                    offer_price = m.group("price")
                    offer_unit = m.group("unit")

            if tend is None and (CONS_FLOW_COMPLETE_SUBSTR in line):
                tend = ts
                break

        _stop_process(consumer, timeout_s=2.0)

        if t0 is None or t1 is None:
            results.append(
                TrialResult(
                    trial=trial,
                    time_to_first_offer_ms=None,
                    offer_sender=offer_sender,
                    offer_price=offer_price,
                    offer_unit=offer_unit,
                    t0_offset_s=(t0 - trial_start) if t0 is not None else None,
                    t1_offset_s=(t1 - trial_start) if t1 is not None else None,
                    tend_offset_s=(tend - t0) if (tend is not None and t0 is not None) else None,
                    error=error or "missing t0/t1 from consumer logs",
                )
            )
            continue

        results.append(
            TrialResult(
                trial=trial,
                time_to_first_offer_ms=(t1 - t0) * 1000,
                offer_sender=offer_sender,
                offer_price=offer_price,
                offer_unit=offer_unit,
                t0_offset_s=(t0 - trial_start),
                t1_offset_s=(t1 - trial_start),
                tend_offset_s=(tend - t0) if (tend is not None) else None,
                error=error,
            )
        )

    with output_csv.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "trial",
                "time_to_first_offer_ms",
                "offer_sender",
                "offer_price",
                "offer_unit",
                "t0_offset_s",
                "t1_offset_s",
                "tend_offset_s",
                "error",
            ]
        )
        for r in results:
            w.writerow(
                [
                    r.trial,
                    r.time_to_first_offer_ms if r.time_to_first_offer_ms is not None else "",
                    r.offer_sender or "",
                    r.offer_price or "",
                    r.offer_unit or "",
                    r.t0_offset_s if r.t0_offset_s is not None else "",
                    r.t1_offset_s if r.t1_offset_s is not None else "",
                    r.tend_offset_s if r.tend_offset_s is not None else "",
                    r.error or "",
                ]
            )

    valid = [r.time_to_first_offer_ms for r in results if r.time_to_first_offer_ms is not None]
    if valid:
        t_mean = mean(valid)
        t_std = pstdev(valid)
        print(f"\n=== Summary ===")
        print(f"Valid trials: {len(valid)}/{trials}")
        print(f"Time to first offer (ms): mean={t_mean:.2f}, std={t_std:.2f}")
    else:
        print(f"\n=== Summary ===")
        print(f"No valid trials (all missing t0/t1). Trials={trials}")

    return results


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=10)
    ap.add_argument("--timeout", type=float, default=35.0, help="per-trial timeout seconds")
    ap.add_argument("--startup-wait", type=float, default=0.0, help="optional sleep after launching consumer")
    ap.add_argument(
        "--relay-ws-url",
        type=str,
        required=True,
        help="Public Relay WebSocket URL (e.g., ws://relay.open-a2a.org:8765)",
    )
    ap.add_argument(
        "--consumer-script",
        type=str,
        default="example/consumer_via_relay_full.py",
        help="Consumer script path relative to Open-A2A repo root",
    )
    ap.add_argument(
        "--constraints",
        type=str,
        default="No_Coriander,<30min",
        help="Comma-separated constraints passed to consumer via env CONSTRAINTS",
    )
    ap.add_argument("--consumer-id", type=str, default="consumer-relay-full-001")
    ap.add_argument(
        "--output",
        type=str,
        required=True,
        help="CSV output path (absolute or relative to Open-A2A repo root)",
    )
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[1]  # Open-A2A/
    output_csv = Path(args.output)
    if not output_csv.is_absolute():
        output_csv = (repo_root / output_csv).resolve()

    run_trials(
        trials=args.trials,
        timeout_s=args.timeout,
        startup_wait_s=args.startup_wait,
        consumer_script=args.consumer_script,
        relay_ws_url=args.relay_ws_url,
        output_csv=output_csv,
        constraints=args.constraints,
        consumer_id=args.consumer_id,
        verbose=args.verbose,
        repo_root=repo_root,
    )


if __name__ == "__main__":
    main()

