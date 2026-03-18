#!/usr/bin/env python3
"""
Node X operator kit - security gate (fail-fast)

Goal: make "default security" a closed loop for public/operator deployments.
When OA2A_STRICT_SECURITY=1, this script validates common foot-guns and exits
non-zero to block the stack from starting.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


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

    # --- NATS template placeholders (must be replaced in strict mode) ---
    nats_conf_path = Path(_getenv("OA2A_NATS_CONF_PATH", "/nats.conf"))
    try:
        nats_conf = nats_conf_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        issues.append(f"无法读取 nats.conf（{nats_conf_path}）：{e}")
        nats_conf = ""

    if "change-me-" in nats_conf:
        issues.append("deploy/node-x/nats.conf 仍包含 change-me-* 占位密码（strict 模式必须修改）")

    # --- Relay public entry auth ---
    relay_host = _getenv("RELAY_WS_HOST", "0.0.0.0")
    relay_public_bind = relay_host in ("0.0.0.0", "::", "")
    relay_auth = _getenv("RELAY_AUTH_TOKEN", "")
    if relay_public_bind and not relay_auth:
        issues.append("Relay 绑定公网地址但未设置 RELAY_AUTH_TOKEN（strict 模式要求鉴权）")

    # --- Bridge discovery auth ---
    bridge_enable_discovery = _is_truthy(os.getenv("BRIDGE_ENABLE_DISCOVERY", "1"))
    if bridge_enable_discovery:
        reg_token = _getenv("BRIDGE_DISCOVERY_REGISTER_TOKEN", "")
        dis_token = _getenv("BRIDGE_DISCOVERY_DISCOVER_TOKEN", "")
        if not reg_token or not dis_token:
            issues.append(
                "Bridge discovery 已启用但未配置 BRIDGE_DISCOVERY_REGISTER_TOKEN/BRIDGE_DISCOVERY_DISCOVER_TOKEN"
            )

    # --- Environment placeholders (must be replaced) ---
    for name in ("NATS_RELAY_PASS", "NATS_BRIDGE_PASS"):
        v = _getenv(name, "")
        if not v or v.startswith("change-me-"):
            issues.append(f"{name} 仍为占位/空值（strict 模式必须修改）")

    # Optional direct NATS credentials: only enforce if user keeps agent_public configured.
    nats_public_user = _getenv("NATS_PUBLIC_USER", "")
    nats_public_pass = _getenv("NATS_PUBLIC_PASS", "")
    if nats_public_user and nats_public_pass.startswith("change-me-"):
        issues.append("NATS_PUBLIC_PASS 仍为占位（若启用/暴露 NATS 直连请修改并收敛权限）")

    if not issues:
        print("[security-gate] ok (strict security checks passed).")
        return 0

    for it in issues:
        _err(it)
    _err("已启用 OA2A_STRICT_SECURITY=1，拒绝在不安全配置下启动。")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

