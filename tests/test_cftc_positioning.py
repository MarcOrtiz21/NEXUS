import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from cftc_positioning import (
    _derive,
    _parse_row,
    known_cot_rows,
    positioning_data_fields,
    release_at_for_report,
    summarize_gold_positioning,
)


def _raw(day: str, long: int, short: int, oi: int = 400_000):
    return {
        "report_date_as_yyyy_mm_dd": f"{day}T00:00:00.000",
        "market_and_exchange_names": "GOLD - COMMODITY EXCHANGE INC.",
        "cftc_contract_market_code": "088691",
        "open_interest_all": str(oi),
        "m_money_positions_long_all": str(long),
        "m_money_positions_short_all": str(short),
        "m_money_positions_spread": "30000",
        "change_in_m_money_long_all": "1000",
        "change_in_m_money_short_all": "-500",
        "pct_of_oi_m_money_long_all": str(long / oi * 100),
        "pct_of_oi_m_money_short_all": str(short / oi * 100),
        "pct_of_oi_m_money_spread": "7.5",
        "conc_gross_le_4_tdr_long": "20.0",
        "conc_gross_le_4_tdr_short": "40.0",
        "conc_gross_le_8_tdr_long": "30.0",
        "conc_gross_le_8_tdr_short": "58.0",
        "contract_units": "(CONTRACTS OF 100 TROY OUNCES)",
    }


class CFTCPositioningTests(unittest.TestCase):
    def test_canonical_contracts_and_open_interest_units(self):
        row = _parse_row(_raw("2026-09-15", 142_394, 9_278, 409_899))
        self.assertEqual(row["managed_money_net_contracts"], 133_116)
        self.assertAlmostEqual(row["managed_money_net_pct_oi"], 32.4753, places=4)
        self.assertEqual(row["contract_units"], "CONTRACTS OF 100 TROY OUNCES")

    def test_regular_release_is_third_business_day_at_1530_eastern(self):
        release = release_at_for_report(date(2026, 9, 15))
        self.assertEqual(release.date(), date(2026, 9, 18))
        self.assertEqual(release.hour, 19)  # EDT -> UTC
        self.assertEqual(release.minute, 30)

    def test_shutdown_override_prevents_lookahead(self):
        row = _parse_row(_raw("2025-10-07", 120_000, 40_000))
        self.assertEqual(str(row["release_at"])[:10], "2025-11-21")
        self.assertEqual(known_cot_rows([row], date(2025, 11, 20)), [])
        self.assertEqual(len(known_cot_rows([row], date(2025, 11, 21))), 1)

    def test_summary_derives_percentile_change_and_divergence(self):
        rows = []
        for index in range(32):
            day = date.fromordinal(date(2025, 1, 7).toordinal() + index * 7).isoformat()
            rows.append(_parse_row(_raw(day, 90_000 + index * 2_000, 35_000)))
        rows = _derive([row for row in rows if row])
        summary = summarize_gold_positioning(
            rows,
            as_of=datetime(2025, 8, 20, tzinfo=timezone.utc),
            gold_momentum_1m=-3.0,
        )
        self.assertEqual(summary["status"], "OK")
        self.assertIsNotNone(summary["percentile_3y"])
        self.assertGreater(summary["four_week_change_contracts"], 0)
        self.assertEqual(summary["price_positioning_divergence"], "PRECIO CAE · POSICIÓN SUBE")
        self.assertEqual(positioning_data_fields(summary)["CFTC_MM_Net_Contracts"], summary["net_contracts"])


if __name__ == "__main__":
    unittest.main()
