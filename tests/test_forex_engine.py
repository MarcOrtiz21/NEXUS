import unittest

from forex_engine import forex_bidirectional_rates, forex_leg_strength, forex_pair_strength, gold_signal


class ForexRatesTests(unittest.TestCase):
    def test_bidirectional_labels(self):
        rates = forex_bidirectional_rates({"price": 1.25})
        self.assertEqual(rates["eur_usd"], 1.25)
        self.assertEqual(rates["usd_eur"], 0.8)
        self.assertEqual(rates["eur_label"], "1 EUR = 1.2500 USD")
        self.assertEqual(rates["usd_label"], "1 USD = 0.8000 EUR")


class ForexStrengthTests(unittest.TestCase):
    def test_missing_metrics_are_none_not_zero(self):
        self.assertIsNone(forex_leg_strength({}))
        pair = forex_pair_strength({}, {})
        self.assertIsNone(pair["eur"])
        self.assertIsNone(pair["usd"])

    def test_flat_market_is_near_neutral_not_zero(self):
        strength = forex_leg_strength({
            "price": 1.10, "ma20": 1.10, "ma50": 1.10,
            "momentum_1m": 0.0, "momentum_3m": 0.0,
        })
        self.assertIsNotNone(strength)
        self.assertGreaterEqual(strength, 40)
        self.assertLessEqual(strength, 60)

    def test_uptrend_beats_downtrend(self):
        up = forex_leg_strength({
            "price": 1.20, "ma20": 1.15, "ma50": 1.10,
            "momentum_1m": 2.0, "momentum_3m": 3.0,
        })
        down = forex_leg_strength({
            "price": 1.00, "ma20": 1.05, "ma50": 1.10,
            "momentum_1m": -2.0, "momentum_3m": -3.0,
        })
        self.assertGreater(up, down)
        pair = forex_pair_strength(
            {"price": 1.20, "ma20": 1.15, "ma50": 1.10, "momentum_1m": 1.5},
            {"price": 28, "ma20": 28.4, "ma50": 28.8, "momentum_1m": -1.0},
        )
        self.assertGreater(pair["eur"], pair["usd"])


class GoldSignalTests(unittest.TestCase):
    def test_refuge_when_real_rates_are_low_and_vix_is_high(self):
        result = gold_signal(
            {"price": 200, "ma20": 190, "ma50": 180, "momentum_1m": 4.0},
            {"price": 28, "ma20": 28.2, "ma50": 28.5, "momentum_1m": -1.0},
            vix=28,
            us10y=3.5,
            cpi_yoy=3.8,
        )
        self.assertEqual(result["bias"], "REFUGIO")
        self.assertEqual(result["tone"], "GOOD")
        self.assertLess(result["real_rate"], 0.5)
        self.assertGreater(result["vs_dollar_1m"], 1)
        self.assertIn("dólar débil", result["vs_dollar_note"])

    def test_pressure_when_real_rates_and_dollar_are_strong(self):
        result = gold_signal(
            {"price": 180, "ma20": 185, "ma50": 190, "momentum_1m": -3.0},
            {"price": 30, "ma20": 29, "ma50": 28, "momentum_1m": 2.0},
            vix=13,
            us10y=4.8,
            cpi_yoy=2.2,
        )
        self.assertEqual(result["bias"], "PRESION")
        self.assertEqual(result["tone"], "BAD")
        self.assertIn("presiona", result["vs_dollar_note"])

    def test_missing_macro_inputs_stay_mixed_with_low_confidence(self):
        result = gold_signal({}, {}, vix=None, us10y=None, cpi_yoy=None)
        self.assertEqual(result["bias"], "MIXTO")
        self.assertEqual(result["confidence"], "BAJA")
        self.assertIsNone(result["real_rate"])
        self.assertIn("Falta", result["vs_dollar_note"])


if __name__ == "__main__":
    unittest.main()
