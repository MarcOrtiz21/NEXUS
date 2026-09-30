import tempfile
import unittest
import calendar
from datetime import date, timedelta
from pathlib import Path

from gold_demand import (
    SAFE_INDEX_CURRENT,
    SAFE_INDEX_PREVIOUS,
    RBI_BULLETIN_INDEX,
    build_etf_market_proxy,
    fetch_official_gold_demand,
    parse_ecb_gold_csv,
    parse_rbi_bulletin_html_links,
    parse_rbi_gold_html,
    rbi_previous_bulletin_url,
    _rbi_cache_within_limit,
    parse_safe_gold_html,
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
SAFE_2025 = '<table><tr><td>Item</td><td>2025.08</td><td>2025.09</td></tr><tr><td>Gold</td><td>300</td><td>310</td></tr><tr><td></td><td>7300万盎司</td><td>7300万盎司</td><td>7350万盎司</td><td>7350万盎司</td></tr></table>'
SAFE_2026 = '<table><tr><td>Item</td><td>2026.07</td><td>2026.08</td></tr><tr><td>Gold</td><td>400</td><td>420</td></tr><tr><td></td><td>7608万盎司</td><td>7608万盎司</td><td>7673万盎司</td><td>7673万盎司</td></tr></table>'
SAFE_LINK_2025 = 'https://www.safe.gov.cn/safe/2025/0206/27115.html'
SAFE_LINK_2026 = 'https://www.safe.gov.cn/safe/2026/0206/27116.html'
RBI_HTML_URL = f"{RBI_BULLETIN_INDEX}?Id=24213"
RBI_PDF_ONLY_INDEX = '<tr><td>33. Foreign Exchange Reserves</td><td><a href="https://rbidocs.rbi.org.in/rdocs/Bulletin/PDFs/33.PDF">PDF</a></td></tr>'


def rbi_html(release_date=None, latest_date=None):
    release_date = release_date or date.today()
    latest_date = latest_date or release_date - timedelta(days=7)
    previous = latest_date - timedelta(days=7)
    return f'''<b>33. Foreign Exchange Reserves</b>
<b>Date : {release_date.strftime('%B %d, %Y')}</b>
<table width="95%">
<tr><td>Item</td><td>Unit</td><td>{previous.year}</td><td>{latest_date.year}</td></tr>
<tr><td>{previous.strftime('%b. %d')}</td><td>{latest_date.strftime('%b. %d')}</td></tr>
<tr><td>1.2 Gold</td><td>₹ Crore</td><td>100000</td><td>900000</td></tr>
<tr><td></td><td>US $ Million</td><td>110000</td><td>120000</td></tr>
<tr><td></td><td>Volume (Metric Tonnes)</td><td>880.34</td><td>880.52</td></tr>
</table>'''


def safe_mapping():
    return {
        SAFE_INDEX_PREVIOUS: f'<a href="/safe/2025/0206/27115.html">html</a>',
        SAFE_INDEX_CURRENT: f'<a href="/safe/2026/0206/27116.html">html</a>',
        SAFE_LINK_2025: SAFE_2025,
        SAFE_LINK_2026: SAFE_2026,
    }


def treasury_page(value):
    return f"<tr><th>--volume in millions of fine troy ounces</th><td>{value}</td></tr>"


class GoldDemandTests(unittest.TestCase):
    def test_safe_uses_physical_ounces_not_gold_value(self):
        rows = parse_safe_gold_html(SAFE_2026)
        self.assertEqual(rows[-1]["period"], "2026-08")
        self.assertAlmostEqual(rows[-1]["tonnes"], 2386.57, places=2)
        self.assertEqual(parse_safe_gold_html('<table><tr><td>Gold</td><td>420</td></tr></table>'), [])

    def test_rbi_extracts_only_physical_tonnes_and_publication_date(self):
        rows = parse_rbi_gold_html(rbi_html(), RBI_HTML_URL)
        self.assertEqual(rows[-1]["period"], (date.today() - timedelta(days=7)).isoformat())
        self.assertEqual(rows[-1]["tonnes"], 880.52)
        self.assertEqual(rows[-1]["release_date"], date.today().isoformat())
        self.assertEqual(rows[-1]["url"], RBI_HTML_URL)
        self.assertEqual(parse_rbi_gold_html(rbi_html().replace("Volume (Metric Tonnes)", "US $ Million"), RBI_HTML_URL), [])
        self.assertEqual(parse_rbi_gold_html(rbi_html(), "https://example.com/Id=24213"), [])
        august = rbi_html(date(2026, 8, 25), date(2026, 7, 31)).replace("Date : August", "Date : Aug")
        self.assertEqual(parse_rbi_gold_html(august, RBI_HTML_URL)[-1]["release_date"], "2026-08-25")

    def test_rbi_pdf_only_index_is_not_interpreted_as_html(self):
        self.assertEqual(parse_rbi_bulletin_html_links(RBI_PDF_ONLY_INDEX), [])
        index = f'<tr><td>33. Foreign Exchange Reserves</td><td><a href="{RBI_HTML_URL}">HTML</a></td></tr>'
        self.assertEqual(parse_rbi_bulletin_html_links(index), [RBI_HTML_URL])

    def test_pdf_only_bulletin_uses_previous_official_html_as_archive(self):
        today = date.today()
        current_index = (
            f"Reserve Bank of India Bulletin - {calendar.month_name[today.month]} {today.year}"
            + RBI_PDF_ONLY_INDEX
        )
        archive_url = rbi_previous_bulletin_url(current_index)
        self.assertIsNotNone(archive_url)
        archive_index = f'<tr><td>33. Foreign Exchange Reserves</td><td><a href="{RBI_HTML_URL}">HTML</a></td></tr>'
        mapping = {
            RBI_BULLETIN_INDEX: current_index,
            archive_url: archive_index,
            RBI_HTML_URL: rbi_html(today - timedelta(days=30), today - timedelta(days=35)),
        }
        with tempfile.TemporaryDirectory() as directory:
            payload = fetch_official_gold_demand(refresh=True, cache_path=Path(directory) / "demand.json", session=_Session(mapping))
        india = next(item for item in payload["reserves"] if item["id"] == "rbi")
        self.assertEqual(india["status"], "ARCHIVED")
        self.assertEqual(india["tonnes"], 880.52)
        self.assertIn("edición anterior", india["note"].lower())
        self.assertEqual(payload["coverage"]["archived"], 1)
        self.assertFalse(india["score_enabled"])
        self.assertFalse(india["aggregation_allowed"])
        self.assertEqual(
            rbi_previous_bulletin_url("Reserve Bank of India Bulletin - January 2026"),
            f"{RBI_BULLETIN_INDEX}?mon=12&yr=2025",
        )

    def test_archived_rbi_cache_expires_by_observation_not_file_age(self):
        cached = {"reserves": [{"id": "rbi", "status": "ARCHIVED",
                                "as_of": (date.today() - timedelta(days=76)).isoformat()}]}
        self.assertFalse(_rbi_cache_within_limit(cached))
        cached["reserves"][0]["as_of"] = (date.today() - timedelta(days=40)).isoformat()
        self.assertTrue(_rbi_cache_within_limit(cached))

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
        mapping.update(safe_mapping())
        mapping[RBI_BULLETIN_INDEX] = RBI_PDF_ONLY_INDEX
        with tempfile.TemporaryDirectory() as directory:
            payload = fetch_official_gold_demand(
                refresh=True,
                cache_path=Path(directory) / "demand.json",
                session=_Session(mapping),
            )
        self.assertEqual(payload["status"], "PARTIAL")
        self.assertFalse(payload["score_enabled"])
        self.assertEqual(payload["coverage"]["available"], 3)
        self.assertEqual(payload["coverage"]["fresh"], 3)
        self.assertEqual(payload["coverage"]["stale"], 0)
        self.assertEqual(payload["coverage"]["archived"], 0)
        self.assertEqual(payload["coverage"]["missing"], 2)
        self.assertEqual(payload["coverage"]["tracked"], 5)
        self.assertEqual(payload["coverage"]["basis"], "tracked_sources_not_world")
        self.assertFalse(payload["coverage"]["world_total_available"])
        china = next(item for item in payload["reserves"] if item["id"] == "safe")
        self.assertAlmostEqual(china["change_12m_tonnes"], 116.016, places=3)
        self.assertEqual(china["scope_id"], "CN")
        self.assertEqual(china["measure_kind"], "monetary_gold_stock")
        self.assertEqual(china["change_kind"], "difference_in_stocks")
        self.assertFalse(china["aggregation_allowed"])
        self.assertIsNone(china["release_at"])
        rbi = next(item for item in payload["reserves"] if item["id"] == "rbi")
        self.assertEqual(rbi["status"], "MISSING")
        self.assertIn("PDF", rbi["note"])
        self.assertNotIn("India RBI", " ".join(payload["errors"]))
        self.assertEqual(next(item for item in payload["reserves"] if item["id"] == "rbi")["scope_id"], "IN")
        self.assertEqual(next(item for item in payload["reserves"] if item["id"] == "nbp")["scope_id"], "PL")
        self.assertEqual(payload["reserves"][1]["change_tonnes"], 0.0)

    def test_recent_rbi_html_is_context_not_global_purchase_signal(self):
        links = parse_us_treasury_links(INDEX_HTML)
        mapping = {
            "https://data-api.ecb.europa.eu/service/data/RAS/M.N.4F.W1.S121.S1.LE.A.FA.R.F11._Z.XGO.XAU._Z.N.ALL?lastNObservations=24&detail=dataonly": ECB_CSV,
            "https://home.treasury.gov/data/us-international-reserve-position": INDEX_HTML,
            links[0]: treasury_page("261.499"),
            links[4]: treasury_page("261.499"),
            RBI_BULLETIN_INDEX: f'<tr><td>33. Foreign Exchange Reserves</td><td><a href="{RBI_HTML_URL}">HTML</a></td></tr>',
            RBI_HTML_URL: rbi_html(),
        }
        mapping.update(safe_mapping())
        with tempfile.TemporaryDirectory() as directory:
            payload = fetch_official_gold_demand(refresh=True, cache_path=Path(directory) / "demand.json", session=_Session(mapping))
        india = next(item for item in payload["reserves"] if item["id"] == "rbi")
        self.assertEqual(payload["coverage"]["available"], 4)
        self.assertEqual(india["status"], "OK")
        self.assertEqual(india["tonnes"], 880.52)
        self.assertEqual(india["release_date"], date.today().isoformat())
        self.assertIsNone(india["release_at"])
        self.assertEqual(india["scope_id"], "IN")
        self.assertFalse(india["score_enabled"])
        self.assertFalse(india["aggregation_allowed"])

    def test_old_rbi_html_does_not_become_current_reserves(self):
        old_date = date.today() - timedelta(days=120)
        html_index = f'<tr><td>33. Foreign Exchange Reserves</td><td><a href="{RBI_HTML_URL}">HTML</a></td></tr>'
        mapping = {
            RBI_BULLETIN_INDEX: html_index,
            RBI_HTML_URL: rbi_html(release_date=old_date, latest_date=old_date - timedelta(days=7)),
        }
        with tempfile.TemporaryDirectory() as directory:
            payload = fetch_official_gold_demand(refresh=True, cache_path=Path(directory) / "demand.json", session=_Session(mapping))
        india = next(item for item in payload["reserves"] if item["id"] == "rbi")
        self.assertEqual(india["status"], "MISSING")
        self.assertIsNone(india["tonnes"])

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
        healthy.update(safe_mapping())
        healthy[RBI_BULLETIN_INDEX] = RBI_PDF_ONLY_INDEX
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "demand.json"
            fetch_official_gold_demand(refresh=True, cache_path=path, session=_Session(healthy))
            failing = dict(healthy)
            failing["https://data-api.ecb.europa.eu/service/data/RAS/M.N.4F.W1.S121.S1.LE.A.FA.R.F11._Z.XGO.XAU._Z.N.ALL?lastNObservations=24&detail=dataonly"] = RuntimeError("offline")
            payload = fetch_official_gold_demand(refresh=True, cache_path=path, session=_Session(failing))
        ecb = next(item for item in payload["reserves"] if item["id"] == "ecb")
        self.assertEqual(ecb["status"], "STALE")
        self.assertEqual(ecb["tonnes"], 508.417)
        self.assertEqual(payload["coverage"]["fresh"], 2)
        self.assertEqual(payload["coverage"]["stale"], 1)

    def test_missing_volume_does_not_become_neutral(self):
        proxy = build_etf_market_proxy([{"date": "2026-09-01", "value": 100}] * 30)
        self.assertEqual(proxy["status"], "MISSING")
        self.assertNotIn("signed_volume_balance", proxy)


if __name__ == "__main__":
    unittest.main()
