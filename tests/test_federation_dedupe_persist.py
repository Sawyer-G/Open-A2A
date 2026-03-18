import time


from federation.subject_bridge import _DedupeCache


def test_dedupe_persist_survives_restart(tmp_path) -> None:
    p = tmp_path / "dedupe.json"
    c1 = _DedupeCache(60, persist_path=str(p), persist_interval_seconds=0.0, max_items=1000)
    assert c1.seen_recently("k1") is False
    c1.persist_best_effort()

    # "restart"
    c2 = _DedupeCache(60, persist_path=str(p), persist_interval_seconds=0.0, max_items=1000)
    assert c2.seen_recently("k1") is True


def test_dedupe_persist_respects_ttl(tmp_path) -> None:
    p = tmp_path / "dedupe.json"
    c1 = _DedupeCache(0.01, persist_path=str(p), persist_interval_seconds=0.0, max_items=1000)
    assert c1.seen_recently("k1") is False
    c1.persist_best_effort()
    time.sleep(0.05)

    c2 = _DedupeCache(0.01, persist_path=str(p), persist_interval_seconds=0.0, max_items=1000)
    assert c2.seen_recently("k1") is False

