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
        self.assertIn("Biotecnología", result.summary)
        self.assertRegex(result.summary, r"Semiconductores|Infraestructura IA")

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

        self.assertEqual(result.state, "LIDERAZGO AÚN DOMINANTE")
        self.assertGreater(result.leaders_avg_1m, result.receivers_avg_1m)

    def test_exposes_representative_names_and_asia_themes(self):
        data = {
            "Assets": {"SPY": _asset(mom1=1.0)},
            "RotationAssets": {
                "XLK": _asset(mom1=2.0),
                "EWJ": _asset(mom1=3.0),
                "FXI": _asset(mom1=-1.0),
                "AAXJ": _asset(mom1=1.5),
                "EWY": _asset(mom1=0.5),
            },
        }

        result = RotationEngine(data).evaluate()
        xlk = next(theme for theme in result.themes if theme.ticker == "XLK")
        asia = [theme for theme in result.themes if theme.group == "Asia"]

        self.assertIn("NVIDIA", xlk.names)
        self.assertTrue(xlk.news_topics)
        self.assertEqual(len(asia), 4)
        self.assertTrue(any(theme.theme == "Japón" for theme in asia))
        self.assertTrue(all(theme.names for theme in asia))

    def test_exposes_company_tickers_and_metrics_for_theme(self):
        data = {
            "Assets": {"SPY": _asset(mom1=1.0)},
            "RotationAssets": {"XLK": _asset(mom1=2.0)},
            "RotationCompanies": {"AAPL": _asset(price=210.0, mom1=4.0)},
        }

        result = RotationEngine(data).evaluate()
        xlk = next(theme for theme in result.themes if theme.ticker == "XLK")
        apple = next(company for company in xlk.companies if company["ticker"] == "AAPL")

        self.assertEqual(apple["name"], "Apple")
        self.assertEqual(apple["price"], 210.0)
        self.assertEqual(apple["momentum_1m"], 4.0)
        self.assertEqual(xlk.price, 100.0)

    def test_each_theme_exposes_fifteen_companies_with_action_indicator(self):
        data = {
            "Assets": {"SPY": _asset(mom1=1.0)},
            "RotationAssets": {theme["ticker"]: _asset(mom1=1.0) for theme in __import__("rotation_engine").ROTATION_THEMES},
            "RotationCompanies": {},
        }
        result = RotationEngine(data).evaluate()

        self.assertTrue(all(len(theme.companies) == 15 for theme in result.themes))
        self.assertTrue(all(company["action"] == "SIN DATOS" for company in result.themes[0].companies))
        self.assertTrue(any(theme.ticker == "EWP" and theme.theme == "España / IBEX" for theme in result.themes))

    def test_observed_leaders_follow_momentum_not_tech_group(self):
        data = {
            "Assets": {"SPY": _asset(mom1=1.0, mom3=5.0)},
            "RotationAssets": {
                "XLU": _asset(mom1=4.0, mom3=22.0),
                "XBI": _asset(mom1=3.5, mom3=18.0),
                "SMH": _asset(mom1=-2.0, mom3=16.0),
                "XLK": _asset(mom1=-1.0, mom3=14.0),
                "AIQ": _asset(mom1=-1.5, mom3=12.0),
                "XLV": _asset(mom1=0.2, mom3=1.0),
            },
        }

        result = RotationEngine(data).evaluate()
        xlu = next(theme for theme in result.themes if theme.ticker == "XLU")
        xlv = next(theme for theme in result.themes if theme.ticker == "XLV")

        self.assertEqual(xlu.leadership, "lider")
        self.assertNotEqual(xlv.leadership, "lider")
        self.assertNotEqual(result.state, "LIDERAZGO TECH DOMINANTE")

    def test_company_action_is_technical_not_an_order(self):
        data = {
            "Assets": {"SPY": _asset(mom1=1.0)},
            "RotationAssets": {"XLK": _asset(mom1=2.0)},
            "RotationCompanies": {"AAPL": _asset(price=210.0, mom1=4.0)},
        }
        result = RotationEngine(data).evaluate()
        apple = next(
            company
            for theme in result.themes if theme.ticker == "XLK"
            for company in theme.companies if company["ticker"] == "AAPL"
        )
        self.assertEqual(apple["action"], "FUERTE")

    def test_company_score_scales_with_momentum_magnitude(self):
        weak = RotationEngine._company_score(_asset(mom1=0.3, mom3=0.4))
        strong = RotationEngine._company_score(_asset(mom1=7.0, mom3=18.0))
        self.assertIsNotNone(weak)
        self.assertIsNotNone(strong)
        self.assertGreater(strong - weak, 10)


if __name__ == "__main__":
    unittest.main()
