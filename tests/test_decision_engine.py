import unittest

from decision_engine import DecisionEngine
from logic_engine import MarketStatus


def _asset(price=100.0, ma20=95.0, ma50=90.0, ma200=85.0, mom1=3.0, mom3=8.0, vol=14.0):
    return {
        "price": price,
        "ma20": ma20,
        "ma50": ma50,
        "ma200": ma200,
        "momentum_1m": mom1,
        "momentum_3m": mom3,
        "volatility_20d": vol,
    }


def _base_data():
    return {
        "VIX": 14.0,
        "US10Y": 3.8,
        "Correlation_Proxy": 0.12,
        "PE_Forward": 17.0,
        "PE_Trailing": 24.0,
        "M2_Change_Pct": 1.8,
        "CPI_YoY_Pct": 2.6,
        "Assets": {
            "SPY": _asset(),
            "QQQ": _asset(price=120.0, ma20=112.0, ma50=108.0, ma200=100.0),
            "TLT": _asset(),
            "GLD": _asset(),
            "UUP": _asset(),
        },
    }


class DecisionEngineTests(unittest.TestCase):
    def test_clear_buy_environment_returns_buy_signal(self):
        decision = DecisionEngine(_base_data(), MarketStatus.HEALTHY, []).evaluate()

        self.assertEqual(decision.action, "COMPRAR")
        self.assertGreaterEqual(decision.score, 75)
        self.assertIn("S&P 500", decision.inputs_used)
        self.assertEqual(sum(decision.allocation.values()), 100)
        self.assertEqual(decision.missing_inputs, [])
        self.assertIn("SPY", decision.asset_scores)
        self.assertGreater(decision.asset_scores["SPY"]["score"], 60)

    def test_eurusd_gets_a_real_technical_score(self):
        data = _base_data()
        data["Forex"] = {"EURUSD": _asset(price=1.17, ma20=1.16, ma50=1.15, ma200=1.12, mom1=1.2, mom3=2.0, vol=8.0)}
        decision = DecisionEngine(data, MarketStatus.HEALTHY, []).evaluate()
        self.assertIn("EURUSD", decision.asset_scores)
        self.assertGreater(decision.asset_scores["EURUSD"]["score"], 0)
        self.assertNotEqual(decision.asset_scores["EURUSD"]["action"], "SIN DATOS")

    def test_restrictive_macro_returns_wait_signal(self):
        data = _base_data()
        data.update({
            "VIX": 24.0,
            "US10Y": 4.8,
            "Correlation_Proxy": 0.5,
            "PE_Forward": None,
            "PE_Trailing": 29.0,
            "M2_Change_Pct": 0.2,
            "CPI_YoY_Pct": 4.4,
        })

        decision = DecisionEngine(data, MarketStatus.HEALTHY, []).evaluate()

        self.assertEqual(decision.action, "ESPERAR / NO ABRIR")
        self.assertLess(decision.score, 45)
        self.assertGreater(decision.allocation["CASH"], decision.allocation["SPY"])

    def test_panic_status_overrides_positive_supporting_data(self):
        data = _base_data()
        data["VIX"] = 35.0

        decision = DecisionEngine(data, MarketStatus.PANIC, ["pánico"]).evaluate()

        self.assertEqual(decision.action, "REDUCIR RIESGO")
        self.assertEqual(decision.operational_action, "REDUCIR RIESGO")
        self.assertEqual(decision.confidence, "ALTA")
        self.assertGreaterEqual(decision.allocation["CASH"], 40)

    def test_blocked_status_keeps_macro_but_pauses_operational(self):
        decision = DecisionEngine(_base_data(), MarketStatus.BLOCKED, ["calendario"]).evaluate()

        self.assertEqual(decision.macro_action, "COMPRAR")
        self.assertEqual(decision.operational_action, "ESPERAR / NO ABRIR")
        self.assertEqual(decision.action, "ESPERAR / NO ABRIR")
        self.assertIsNotNone(decision.operational_pause_reason)
        self.assertGreater(decision.macro_allocation["SPY"], decision.allocation["SPY"])

    def test_missing_critical_inputs_blocks_operational_signal(self):
        data = _base_data()
        data["Assets"]["QQQ"]["price"] = None

        decision = DecisionEngine(data, MarketStatus.HEALTHY, []).evaluate()

        self.assertEqual(decision.action, "DATOS INSUFICIENTES")
        self.assertEqual(decision.allocation["CASH"], 100)
        self.assertIn("precio QQQ", decision.missing_inputs)
        self.assertIn("CASH", decision.asset_scores)

    def test_caution_status_does_not_double_count_vix(self):
        data = _base_data()
        data["VIX"] = 26.0
        healthy = DecisionEngine(data, MarketStatus.HEALTHY, []).evaluate()
        caution = DecisionEngine(data, MarketStatus.CAUTION, []).evaluate()
        self.assertEqual(healthy.score, caution.score)

    def test_small_momentum_scores_less_than_a_large_move(self):
        tiny = _base_data()
        tiny["Assets"]["SPY"]["momentum_1m"] = 0.3
        huge = _base_data()
        huge["Assets"]["SPY"]["momentum_1m"] = 7.0
        tiny_score = DecisionEngine(tiny, MarketStatus.HEALTHY, [])._asset_trend_score(tiny["Assets"]["SPY"])
        huge_score = DecisionEngine(huge, MarketStatus.HEALTHY, [])._asset_trend_score(huge["Assets"]["SPY"])
        self.assertGreater(huge_score - tiny_score, 2)

    def test_poor_buy_history_dampens_risk_on_score(self):
        full = DecisionEngine(_base_data(), MarketStatus.HEALTHY, []).evaluate()
        damp = DecisionEngine(
            _base_data(),
            MarketStatus.HEALTHY,
            [],
            history_scale=0.7,
            history_reason="la muestra reciente de COMPRAR no confirma el sentido de SPY frente al índice",
        ).evaluate()
        self.assertGreater(full.score, 50)
        self.assertLess(damp.score, full.score)
        self.assertIn("muestra reciente", damp.rationale)


if __name__ == "__main__":
    unittest.main()
