"""Pruebas de tenencias GLD con datos 100 % sintéticos.

No sustituyas estos valores por filas reales del archivo WGTS: sus condiciones
prohíben redistribuirlas y este repositorio es público.
"""

import io
import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
from openpyxl import Workbook

from gld_holdings import (
    count_revisions,
    fetch_gld_holdings,
    holdings_data_fields,
    known_holdings_rows,
    parse_gld_archive,
    release_at_for_session,
    summarize_gld_holdings,
)
from gold_demand import build_gold_demand
from gold_outlook import build_gold_outlook


HEADER = (
    "Date", "Closing Price", "Ounces of Gold per Share", "NAV/Share at 10:30am NYT",
    "Indicative Price per Share at 4:15pm NYT", "Mid point of bid/ask spread at 4:15pm NYT",
    "Premium/Discount of GLD Mid Point vs Indicative Value of GLD at 4:15pm NYT",
    "Daily Share Volume", "Total Ounces of Gold in the Trust", "Tonnes of Gold",
    "Total Net Asset Value in the Trust",
)


def _synthetic_xlsx(sessions=40, start="2030-01-02", base_tonnes=100.0, step=0.5, holiday_at=None):
    workbook = Workbook()
    workbook.active.title = "Disclaimer"
    workbook.active.append(["Synthetic fixture"])
    sheet = workbook.create_sheet("US GLD Historical Archive")
    sheet.append(HEADER)
    for index, day in enumerate(pd.bdate_range(start, periods=sessions)):
        label = day.strftime("%d-%b-%Y")
        if holiday_at is not None and index == holiday_at:
            sheet.append((label,) + ("US Holiday",) * 10)
            continue
        tonnes = base_tonnes + index * step
        ounces = tonnes * 32150.7466
        sheet.append((label, 10.0, 0.01, 10.0, 10.0, 10.0, 0.0, 1000, ounces, tonnes, ounces * 1000))
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _rows(sessions=400, base=100.0, step=0.1, start="2030-01-02"):
    rows = []
    for index, day in enumerate(pd.bdate_range(start, periods=sessions)):
        session = day.date()
        rows.append({
            "date": session.isoformat(),
            "release_at": release_at_for_session(session).isoformat(timespec="seconds"),
            "fund_id": "GLD",
            "tonnes": round(base + index * step, 4),
        })
    return rows


class _Response:
    def __init__(self, content=b"", status=200):
        self.content = content
        self.status_code = status
        self.headers = {"Last-Modified": "Wed, 01 Jan 2031 03:00:00 GMT"}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _Session:
    def __init__(self, response):
        self.response = response
        self.calls = 0

    def get(self, *_args, **_kwargs):
        self.calls += 1
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class GldHoldingsTests(unittest.TestCase):
    def test_parser_skips_holidays_and_derives_shares(self):
        rows = parse_gld_archive(_synthetic_xlsx(sessions=10, holiday_at=3))
        self.assertEqual(len(rows), 9)
        self.assertEqual(rows[0]["fund_id"], "GLD")
        self.assertEqual(rows[0]["tonnes"], 100.0)
        self.assertAlmostEqual(rows[0]["shares_outstanding_derived"], round(100.0 * 32150.7466 / 0.01))
        self.assertTrue(all(row["date"] < next_row["date"] for row, next_row in zip(rows, rows[1:])))

    def test_release_is_next_us_business_day_morning(self):
        friday = release_at_for_session(date(2030, 1, 4))
        self.assertEqual(friday, datetime(2030, 1, 7, 12, 0, tzinfo=timezone.utc))
        before_holiday = release_at_for_session(date(2030, 12, 24))
        self.assertEqual(before_holiday.date(), date(2030, 12, 26))

    def test_known_rows_never_include_unpublished_session(self):
        rows = _rows(sessions=5)
        same_day_close = datetime(2030, 1, 4, 21, 0, tzinfo=timezone.utc)
        known = known_holdings_rows(rows, same_day_close)
        self.assertEqual(known[-1]["date"], "2030-01-03")

    def test_summary_measures_stock_differences(self):
        rows = _rows(sessions=400, step=0.1)
        summary = summarize_gld_holdings(rows, as_of=datetime(2031, 12, 31, tzinfo=timezone.utc))
        self.assertEqual(summary["unit"], "metric_tonnes")
        self.assertEqual(summary["change_kind"], "difference_in_stock")
        self.assertAlmostEqual(summary["change_1d_tonnes"], 0.1, places=3)
        self.assertAlmostEqual(summary["change_21d_tonnes"], 2.1, places=3)
        self.assertIsNotNone(summary["change_63d_pct"])
        self.assertFalse(summary["score_enabled"])
        self.assertIn("uso personal", summary["data_notice"])
        fields = holdings_data_fields(summary)
        self.assertEqual(fields["GLD_Holdings_AsOf"], summary["as_of"])
        self.assertIn("GLD_Holdings_ReleaseAt", fields)

    def test_summary_marks_old_data_stale_and_missing_without_rows(self):
        stale = summarize_gld_holdings(_rows(sessions=30), as_of=date(2030, 6, 1))
        self.assertEqual(stale["status"], "STALE")
        missing = summarize_gld_holdings([], as_of=date(2030, 6, 1))
        self.assertEqual(missing["status"], "MISSING")
        self.assertEqual(holdings_data_fields(missing), {})

    def test_revisions_are_counted_between_downloads(self):
        previous = _rows(sessions=5)
        current = [dict(row) for row in previous]
        current[2]["tonnes"] += 1.0
        self.assertEqual(count_revisions(previous, current), 1)

    def test_fetch_stores_hashed_snapshot_and_degrades_to_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = Path(folder) / "gld.json"
            raw_dir = Path(folder) / "raw"
            ok = fetch_gld_holdings(
                refresh=True, cache_path=cache, raw_dir=raw_dir,
                session=_Session(_Response(_synthetic_xlsx())),
            )
            self.assertEqual(ok["source_status"], "OK")
            self.assertEqual(len(ok["snapshot"]["sha256"]), 64)
            self.assertEqual(len(list(raw_dir.glob("gld_archive_*.xlsx"))), 1)
            manifest = [json.loads(line) for line in (raw_dir / "manifest.jsonl").read_text().splitlines()]
            self.assertEqual(manifest[0]["sha256"], ok["snapshot"]["sha256"])

            degraded = fetch_gld_holdings(
                refresh=True, cache_path=cache, raw_dir=raw_dir,
                session=_Session(RuntimeError("offline")),
            )
            self.assertEqual(degraded["source_status"], "STALE")
            self.assertEqual(len(degraded["rows"]), len(ok["rows"]))

            missing = fetch_gld_holdings(
                refresh=True, cache_path=Path(folder) / "none.json", raw_dir=raw_dir,
                session=_Session(_Response(status=503)),
            )
            self.assertEqual(missing["source_status"], "MISSING")
            self.assertEqual(missing["rows"], [])

    def test_raw_snapshot_retention_keeps_recent_files(self):
        with tempfile.TemporaryDirectory() as folder:
            raw_dir = Path(folder) / "raw"
            for index in range(3):
                fetch_gld_holdings(
                    refresh=True, cache_path=Path(folder) / "gld.json", raw_dir=raw_dir, retention=2,
                    session=_Session(_Response(_synthetic_xlsx(base_tonnes=100.0 + index))),
                )
            self.assertEqual(len(list(raw_dir.glob("gld_archive_*.xlsx"))), 2)
            self.assertEqual(len((raw_dir / "manifest.jsonl").read_text().splitlines()), 3)

    def test_outlook_group_stays_out_of_score_until_gate(self):
        summary = summarize_gld_holdings(_rows(sessions=400, step=0.3), as_of=date(2031, 12, 31))
        data = holdings_data_fields(summary)
        context = build_gold_outlook(data)
        group = next(item for item in context["groups"] if item["id"] == "etf_holdings")
        self.assertFalse(group["score_enabled"])
        self.assertGreater(group["short_signal"], 0)
        enabled = build_gold_outlook({**data, "GLD_Holdings_Model_Eligible": True})
        group = next(item for item in enabled["groups"] if item["id"] == "etf_holdings")
        self.assertTrue(group["score_enabled"])

    def test_demand_payload_separates_holdings_from_proxy(self):
        summary = summarize_gld_holdings(_rows(sessions=30), as_of=date(2030, 2, 14))
        demand = build_gold_demand({}, [], summary)
        self.assertEqual(demand["etf_holdings"]["fund_id"], "GLD")
        self.assertEqual(demand["actual_etf_flows_status"], "GLD_ONLY")
        self.assertFalse(demand["score_enabled"])
        self.assertEqual(build_gold_demand({}, [])["actual_etf_flows_status"], "STANDBY")


if __name__ == "__main__":
    unittest.main()
