from decision_intelligence import (
    classify_market_regime,
    data_quality_summary,
    detect_market_anomalies,
    score_attribution,
)


def test_regime_marks_stress_from_high_vix():
    result = classify_market_regime({"VIX": 31, "Assets": {"SPY": {}}})
    assert result["label"] == "ESTRÉS"


def test_anomalies_detect_vix_and_negative_momentum():
    data = {
        "VIX": 30,
        "VIX_MA20": 20,
        "Yield_Curve_Spread": -0.4,
        "Assets": {"SPY": {"momentum_1m": -6}},
    }
    assert len(detect_market_anomalies(data)) == 4


def test_quality_and_attribution_are_descriptive():
    data = {
        "DataQuality": {"VIX": {"status": "OK"}, "CPI": {"status": "MISSING"}},
        "Assets": {"SPY": {"momentum_1m": 2}},
        "VIX": 15,
    }
    assert data_quality_summary(data)["unhealthy"] == 1
    assert score_attribution(data, {"score": 60})["score"] == 60
