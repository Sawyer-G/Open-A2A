"""最小冒烟测试：确保包可安装、可导入，版本与核心类型存在。"""


def test_package_has_version() -> None:
    import open_a2a
    assert hasattr(open_a2a, "__version__")
    assert isinstance(open_a2a.__version__, str)
    assert len(open_a2a.__version__) >= 5  # e.g. 0.2.0


def test_core_imports() -> None:
    from open_a2a import Intent, IntentBroadcaster, Offer
    assert Intent is not None
    assert Offer is not None
    assert IntentBroadcaster is not None


def test_intent_from_dict_roundtrip() -> None:
    """Intent 最小序列化/反序列化，不依赖 NATS。"""
    from open_a2a import Intent
    from open_a2a.intent import Location
    loc = Location(lat=31.23, lon=121.47)
    intent = Intent(
        action="Food_Order",
        type="Noodle",
        location=loc,
        constraints=["No_Coriander"],
        reply_to="",
        sender_id="test",
    )
    d = intent.to_dict()
    assert "id" in d
    assert d.get("type") == "Noodle"
    restored = Intent.from_dict(d)
    assert restored.id == intent.id
    assert restored.type == intent.type
