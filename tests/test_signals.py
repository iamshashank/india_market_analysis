"""Health gate + discovery-inflection signals — graceful degradation + sanity."""
from signals import health, inflection


def test_health_empty_row_is_unknown():
    res = health.assess({})
    assert res["score"] is None
    assert res["label"] == "Unknown"
    assert res["flags"] == []


def test_health_strong_clean_company():
    res = health.assess({
        "debt_to_equity": 0.1, "current_ratio": 2.5, "profit_margin": 0.2,
        "return_on_assets": 0.15, "fcf_margin": 0.18,
        "operating_cashflow": 120.0, "net_income": 100.0,
    })
    assert res["score"] is not None and res["score"] >= 70
    assert res["label"] == "Strong"
    assert res["flags"] == []


def test_health_distress_flags_raised():
    res = health.assess({
        "debt_to_equity": 3.0, "current_ratio": 0.6, "profit_margin": -0.1,
        "fcf_margin": -0.05, "operating_cashflow": -10.0, "net_income": 50.0,
    })
    assert res["label"] in ("Distress", "Watch")
    # several specific red flags should be present
    joined = " ".join(res["flags"]).lower()
    assert "leverage" in joined
    assert "liquidity" in joined


def test_inflection_defaults_to_neutralish_without_signals():
    res = inflection.assess({}, {}, under_covered=50.0, quality=50.0, consistency=50.0)
    assert 0 <= res["score"] <= 100
    assert res["label"] in ("Quiet", "Stirring", "Inflecting")


def test_inflection_high_when_hidden_and_waking():
    res = inflection.assess(
        {"vol_trend": 2.0, "pct_of_52w_high": 0.95, "above_200dma": 0.3},
        {"velocity": 3.0},
        under_covered=85.0, quality=70.0, consistency=70.0,
    )
    assert res["score"] >= 65
    assert res["label"] == "Inflecting"
