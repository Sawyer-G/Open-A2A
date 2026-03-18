#!/usr/bin/env python3
"""
Quickstart (full stack) - security gate (fail-fast)

This is for deploy/quickstart/docker-compose.full.yml.
When OA2A_STRICT_SECURITY=1, block startup on common unsafe defaults:
  - public Relay without auth token
  - Bridge discovery enabled without bearer tokens

Note: quickstart is for demos; for operator-grade public nodes, use deploy/node-x/.
"""

from __future__ import annotations

import os
import sys


def _is_truthy(v: str | None) -> bool:
    return (v or "").strip().lower() in ("1", "true", "yes", "y", "on")


def _getenv(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or "").strip()


def _err(msg: str) -> None:
    print(f"[security-gate][error] {msg}", file=sys.stderr)


def main() -> int:
    strict = _is_truthy(os.getenv("OA2A_STRICT_SECURITY"))
    if not strict:
        print("[security-gate] OA2A_STRICT_SECURITY not enabled; skip checks.")
        return 0

    issues: list[str] = []

    # Relay public entry should have auth token in strict mode.
    relay_host = _getenv("RELAY_WS_HOST", "0.0.0.0")
    relay_public_bind = relay_host in ("0.0.0.0", "::", "")
    relay_auth = _getenv("RELAY_AUTH_TOKEN", "")
    if relay_public_bind and not relay_auth:
        issues.append("STRICT: Relay 绑定公网地址但未设置 RELAY_AUTH_TOKEN")

    # If Bridge exposes directory discovery, require auth tokens.
    bridge_enable_discovery = _is_truthy(os.getenv("BRIDGE_ENABLE_DISCOVERY", "1"))
    if bridge_enable_discovery:
        reg_token = _getenv("BRIDGE_DISCOVERY_REGISTER_TOKEN", "")
        dis_token = _getenv("BRIDGE_DISCOVERY_DISCOVER_TOKEN", "")
        if not reg_token or not dis_token:
            issues.append(
                "STRICT: Bridge discovery 启用但未配置 BRIDGE_DISCOVERY_REGISTER_TOKEN/BRIDGE_DISCOVERY_DISCOVER_TOKEN"
            )

    if not issues:
        print("[security-gate] ok (strict security checks passed).")
        return 0

    for it in issues:
        _err(it)
    _err("已启用 OA2A_STRICT_SECURITY=1，拒绝在不安全配置下启动。")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

