import unittest

from rotation_engine import RotationEngine


def _asset(price=100.0, ma20=98.0, ma50=95.0, ma200=90.0, mom1=2.0, mom3=8.0, vol=18.0):
    return {
        "price": price,
        "ma20": ma20,
        "ma50": ma50,
        "ma200": ma200,
        "momentum_1m": mom1,
        "momentum_3m": mom3,
        "volatility_20d": vol,
    }


class RotationEngineTests(unittest.TestCase):
    def test_detects_healthy_rotation_from_leaders_to_receivers(self):
        data = {
            "Assets": {"SPY": _asset(mom1=0.5)},
            "RotationAssets": {
                "AIQ": _asset(mom1=-2.0, mom3=12.0),
                "SMH": _asset(mom1=-3.0, mom3=18.0),
                "XLK": _asset(mom1=0.2, mom3=10.0),
                "XBI": _asset(mom1=5.0, mom3=4.0),
                "XLV": _asset(mom1=3.0, mom3=2.0),
                "KIE": _asset(mom1=2.5, mom3=1.0),
                "PJP": _asset(mom1=1.5, mom3=1.0),
            },
        }

        result = RotationEngine(data).evaluate()

        self.assertEqual(result.state, "ROTACIÓN ACTIVA Y SANA")
        self.assertGreater(result.receivers_avg_1m, result.leaders_avg_1m)
        self.assertTrue(any(theme.theme == "Biotecnología" for theme in result.themes))

    def test_detects_tech_leadership_when_receivers_lag(self):
        data = {
            "Assets": {"SPY": _asset(mom1=2.0)},
            "RotationAssets": {
                "AIQ": _asset(mom1=6.0, mom3=20.0),
                "SMH": _asset(mom1=8.0, mom3=25.0),
                "XLK": _asset(mom1=5.0, mom3=16.0),
                "XBI": _asset(mom1=-2.0, mom3=-4.0),
                "XLV": _asset(mom1=-1.0, mom3=1.0),
                "KIE": _asset(mom1=0.0, mom3=1.0),
                "PJP": _asset(mom1=-0.5, mom3=0.0),
            },
        }

        result = RotationEngine(data).evaluate()

        self.assertEqual(result.state, "LIDERAZGO TECH DOMINANTE")
        self.assertGreater(result.leaders_avg_1m, result.receivers_avg_1m)


if __name__ == "__main__":
    unittest.main()
