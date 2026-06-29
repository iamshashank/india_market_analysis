"""Strategy registry + the core-v1 backward-compatibility invariant."""
from core.config import WEIGHTS
from signals import strategy


def test_core_v1_is_default():
    assert strategy.active().version in {"core-v1", strategy.active().version}
    assert strategy.get("core-v1").version == "core-v1"


def test_core_v1_weights_equal_legacy_config():
    # The whole point of versioning: default behaviour must equal original V1.
    assert strategy.get("core-v1").weights == dict(WEIGHTS)


def test_unknown_version_falls_back_to_core_v1():
    assert strategy.get("does-not-exist").version == "core-v1"


def test_registry_lists_known_versions():
    versions = {s["version"] for s in strategy.list_versions()}
    assert "core-v1" in versions
    assert "quality-compounder-v1" in versions


def test_register_adds_a_version():
    s = strategy.Strategy(
        version="unit-test-v0", label="t", description="t",
        weights=dict(WEIGHTS), compounder_pillars={}, catalyst_pillars={},
    )
    strategy.register(s)
    assert strategy.get("unit-test-v0").version == "unit-test-v0"
