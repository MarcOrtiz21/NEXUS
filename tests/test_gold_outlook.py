import unittest

from gold_outlook import build_gold_outlook


class GoldOutlookTests(unittest.TestCase):
    def test_correlated_inflation_series_stay_in_one_group(self):
        outlook = build_gold_outlook({
            "CPI_MoM_Pct": 0.5,
            "CPI_YoY_Pct": 3.5,
            "Core_CPI_MoM_Pct": 0.4,
            "Core_CPI_YoY_Pct": 3.2,
            "PCE_MoM_Pct": 0.4,
            "PCE_YoY_Pct": 3.0,
            "Core_PCE_MoM_Pct": 0.3,
            "CPI_3M_Annualized_Pct": 4.0,
            "Core_CPI_3M_Annualized_Pct": 3.6,
            "PCE_3M_Annualized_Pct": 3.2,
            "Core_PCE_3M_Annualized_Pct": 3.0,
            "Core_PCE_YoY_Pct": 2.8,
        })
        inflation = next(group for group in outlook["groups"] if group["id"] == "inflation")
        self.assertEqual(len(inflation["details"]), 12)
        self.assertTrue(any(detail["label"] == "CPI 3M anualizado" for detail in inflation["details"]))
        self.assertLessEqual(abs(inflation["short_contribution"]), 14)
        self.assertLessEqual(abs(inflation["medium_contribution"]), 16)

    def test_missing_official_demand_is_not_a_neutral_vote(self):
        outlook = build_gold_outlook({"VIX": 22.0})
        official = next(group for group in outlook["groups"] if group["id"] == "official_demand")
        self.assertFalse(official["available"])
        self.assertIsNone(official["medium_contribution"])
        self.assertLess(outlook["medium_term"]["coverage_pct"], 100)

    def test_energy_exposes_monthly_and_yearly_in_one_capped_group(self):
        outlook = build_gold_outlook({
            "WTI_1M_Change_Pct": 10.0,
            "Energy_CPI_MoM_Pct": 1.5,
            "Energy_CPI_YoY_Pct": 8.0,
        })
        energy = next(group for group in outlook["groups"] if group["id"] == "energy")
        self.assertEqual(len(energy["details"]), 3)
        self.assertEqual(energy["coverage_pct"], 100.0)
        self.assertLessEqual(abs(energy["short_contribution"]), 6)
        self.assertLessEqual(abs(energy["medium_contribution"]), 8)

    def test_lower_real_yields_and_weaker_dollar_improve_signal(self):
        supportive = build_gold_outlook(
            {"Real_Yield_10Y_Pct": 0.2, "Real_Yield_10Y_1M_Change_Pp": -0.4, "VIX": 24},
            {"price": 210, "ma20": 200, "ma50": 190, "momentum_1m": 4},
            {"momentum_1m": -2},
        )
        adverse = build_gold_outlook(
            {"Real_Yield_10Y_Pct": 2.8, "Real_Yield_10Y_1M_Change_Pp": 0.4, "VIX": 13},
            {"price": 180, "ma20": 190, "ma50": 200, "momentum_1m": -4},
            {"momentum_1m": 2},
        )
        self.assertGreater(
            supportive["short_term"]["probability_up"],
            adverse["short_term"]["probability_up"],
        )

    def test_preliminary_model_never_claims_high_confidence(self):
        data = {
            "CPI_MoM_Pct": 0.2, "CPI_YoY_Pct": 2.5,
            "Core_CPI_MoM_Pct": 0.2, "Core_CPI_YoY_Pct": 2.5,
            "PCE_MoM_Pct": 0.2, "PCE_YoY_Pct": 2.2,
            "Core_PCE_MoM_Pct": 0.2, "Core_PCE_YoY_Pct": 2.2,
            "Real_Yield_10Y_Pct": 1.2, "Real_Yield_10Y_1M_Change_Pp": -0.1,
            "WTI_1M_Change_Pct": 2, "Energy_CPI_MoM_Pct": 0.4,
            "Unemployment_1M_Change_Pp": 0.1,
            "Payrolls_1M_Change_Thousands": 100,
            "Industrial_Production_MoM_Pct": -0.1,
            "M2_Change_Pct": 1.0, "VIX": 21,
        }
        outlook = build_gold_outlook(
            data,
            {"price": 205, "ma20": 200, "ma50": 195, "momentum_1m": 2},
            {"momentum_1m": -1},
        )
        self.assertNotEqual(outlook["short_term"]["confidence"], "ALTA")
        self.assertNotEqual(outlook["medium_term"]["confidence"], "ALTA")

    def test_details_expose_source_date_and_quality(self):
        outlook = build_gold_outlook({
            "CPI_MoM_Pct": 0.3,
            "DataQuality": {
                "CPI_MoM_Pct": {
                    "source": "FRED:CPIAUCSL",
                    "as_of": "2026-08-01",
                    "status": "OK",
                }
            },
        })
        inflation = next(group for group in outlook["groups"] if group["id"] == "inflation")
        detail = next(item for item in inflation["details"] if item["label"] == "CPI mensual")
        self.assertEqual(detail["source"], "FRED:CPIAUCSL")
        self.assertEqual(detail["as_of"], "2026-08-01")
        self.assertEqual(detail["quality"], "OK")

    def test_cftc_is_visible_but_does_not_score_until_promoted(self):
        data = {
            "CFTC_MM_Net_Contracts": 120_000,
            "CFTC_MM_Net_Pct_OI": 30.0,
            "CFTC_MM_Weekly_Change_Contracts": 8_000,
            "CFTC_MM_4W_Change_Contracts": 30_000,
            "CFTC_MM_Percentile_3Y": 75.0,
            "CFTC_MM_ZScore_3Y": 1.0,
        }
        context = build_gold_outlook(data)
        group = next(item for item in context["groups"] if item["id"] == "positioning")
        self.assertTrue(group["available"])
        self.assertFalse(group["score_enabled"])
        self.assertIsNone(group["short_contribution"])

        promoted = build_gold_outlook(data, include_positioning_in_score=True)
        active = next(item for item in promoted["groups"] if item["id"] == "positioning")
        self.assertTrue(active["score_enabled"])
        self.assertIsNotNone(active["short_contribution"])


if __name__ == "__main__":
    unittest.main()
