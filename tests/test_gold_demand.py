import tempfile
import unittest
from pathlib import Path

from gold_demand import (
    build_etf_market_proxy,
    fetch_official_gold_demand,
    parse_ecb_gold_csv,
    parse_us_treasury_gold_page,
    parse_us_treasury_links,
)


class _Response:
    def __init__(self, text, status=200):
        self.text = text
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class _Session:
    def __init__(self, mapping):
        self.mapping = mapping

    def get(self, url, **_kwargs):
        value = self.mapping[url]
        if isinstance(value, Exception):
            raise value
        return _Response(value)


ECB_CSV = """TIME_PERIOD,OBS_VALUE,OBS_STATUS
2026-07,16.300,A
2026-08,16.346,A
"""
INDEX_HTML = """
<a href=/data/us-international-reserve-position/09112026>September 11</a>
<a href=/data/us-international-reserve-position/09042026>September 4</a>
<a href=/data/us-international-reserve-position/08282026>August 28</a>
<a href=/data/us-international-reserve-position/08212026>August 21</a>
<a href=/data/us-international-reserve-position/08142026>August 14</a>
"""


def treasury_page(value):
    return f"<tr><th>--volume in millions of fine troy ounces</th><td>{value}</td></tr>"


class GoldDemandTests(unittest.TestCase):
    def test_ecb_csv_converts_million_ounces_to_tonnes(self):
        rows = parse_ecb_gold_csv(ECB_CSV)
        self.assertEqual(rows[-1]["period"], "2026-08")
        self.assertAlmostEqual(rows[-1]["tonnes"], 508.417, places=3)

    def test_treasury_links_and_page_are_parsed(self):
        links = parse_us_treasury_links(INDEX_HTML)
        self.assertTrue(links[0].endswith("09112026"))
        row = parse_us_treasury_gold_page(treasury_page("261.499"), links[0])
        self.assertEqual(row["period"], "2026-09-11")
        self.assertAlmostEqual(row["tonnes"], 8133.528, places=3)

    def test_official_fetch_preserves_partial_scope_and_month_change(self):
        links = parse_us_treasury_links(INDEX_HTML)
        mapping = {
            "https://data-api.ecb.europa.eu/service/data/RAS/M.N.4F.W1.S121.S1.LE.A.FA.R.F11._Z.XGO.XAU._Z.N.ALL?lastNObservations=24&detail=dataonly": ECB_CSV,
            "https://home.treasury.gov/data/us-international-reserve-position": INDEX_HTML,
            links[0]: treasury_page("261.499"),
            links[4]: treasury_page("261.499"),
        }
        with tempfile.TemporaryDirectory() as directory:
            payload = fetch_official_gold_demand(
                refresh=True,
                cache_path=Path(directory) / "demand.json",
                session=_Session(mapping),
            )
        self.assertEqual(payload["status"], "PARTIAL")
        self.assertFalse(payload["score_enabled"])
        self.assertEqual(payload["coverage"]["available"], 2)
        self.assertEqual(payload["reserves"][1]["change_tonnes"], 0.0)

    def test_etf_proxy_is_not_an_actual_flow_or_score(self):
        points = [
            {"date": f"2026-08-{index + 1:02d}", "value": 100 + index, "volume": 1_000 + index}
            for index in range(21)
        ]
        proxy = build_etf_market_proxy(points)
        self.assertEqual(proxy["status"], "PROXY")
        self.assertEqual(proxy["label"], "PRESIÓN COMPRADORA")
        self.assertFalse(proxy["score_enabled"])
        self.assertIn("no mide entradas", proxy["note"])

    def test_source_failure_preserves_cached_record_as_stale(self):
        links = parse_us_treasury_links(INDEX_HTML)
        healthy = {
            "https://data-api.ecb.europa.eu/service/data/RAS/M.N.4F.W1.S121.S1.LE.A.FA.R.F11._Z.XGO.XAU._Z.N.ALL?lastNObservations=24&detail=dataonly": ECB_CSV,
            "https://home.treasury.gov/data/us-international-reserve-position": INDEX_HTML,
            links[0]: treasury_page("261.499"),
            links[4]: treasury_page("261.499"),
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "demand.json"
            fetch_official_gold_demand(refresh=True, cache_path=path, session=_Session(healthy))
            failing = dict(healthy)
            failing["https://data-api.ecb.europa.eu/service/data/RAS/M.N.4F.W1.S121.S1.LE.A.FA.R.F11._Z.XGO.XAU._Z.N.ALL?lastNObservations=24&detail=dataonly"] = RuntimeError("offline")
            payload = fetch_official_gold_demand(refresh=True, cache_path=path, session=_Session(failing))
        ecb = next(item for item in payload["reserves"] if item["id"] == "ecb")
        self.assertEqual(ecb["status"], "STALE")
        self.assertEqual(ecb["tonnes"], 508.417)

    def test_missing_volume_does_not_become_neutral(self):
        proxy = build_etf_market_proxy([{"date": "2026-09-01", "value": 100}] * 30)
        self.assertEqual(proxy["status"], "MISSING")
        self.assertNotIn("signed_volume_balance", proxy)


if __name__ == "__main__":
    unittest.main()
