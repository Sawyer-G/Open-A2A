import importlib
import asyncio

import pytest


def test_relay_default_allows_open_a2a_inbox(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RELAY_SUBJECT_ALLOWLIST", raising=False)
    monkeypatch.delenv("RELAY_SUBJECT_BLOCKLIST", raising=False)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        import relay.main as relay_main

        importlib.reload(relay_main)

        assert relay_main._is_subject_allowed("_INBOX.open_a2a.123") is True
        assert relay_main._is_subject_allowed("intent.food.order") is True
        assert relay_main._is_subject_allowed("open_a2a.discovery.query.intent.food.order") is True
    finally:
        loop.close()
        asyncio.set_event_loop(None)


def test_relay_default_blocks_other_inbox(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RELAY_SUBJECT_ALLOWLIST", raising=False)
    monkeypatch.delenv("RELAY_SUBJECT_BLOCKLIST", raising=False)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        import relay.main as relay_main

        importlib.reload(relay_main)

        assert relay_main._is_subject_allowed("_INBOX.someone_else.123") is False
    finally:
        loop.close()
        asyncio.set_event_loop(None)

