import json
import math
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from gold_experiment import (EXPERIMENT_ID, RULES, register_experiment, clean_prices,
                             predict_blend, update_experiment, experiment_summary)


def report():
    return {"compatible_with_live": True, "model_fingerprint": "production-test",
            "samples": [{"horizon_days": h,"decision_at": f"{2000+i}-01-15",
                         "evaluated_at": f"{2000+i}-05-01","direction_up":i%2}
                        for h in [21,63] for i in range(25)]}


def prices(day, hour="20:20"):
    dates = pd.bdate_range(end=day, periods=900)
    points = [{"date":d.date().isoformat(),"close":100*math.exp(i*.0002+.002*math.sin(i))}
              for i,d in enumerate(dates)]
    return {"status":"OK","fetched_at":f"{day}T{hour}:00+00:00","points":points}


def outlook(cache):
    return {"model_fingerprint":"production-test","short_term":{"fresh_coverage_pct":100,"probability_up":55},
            "medium_term":{"fresh_coverage_pct":100,"probability_up":60},
            "groups":[{"id":"technical","details":[{"label":"Precio GLD","value":cache["points"][-1]["close"]}]}]}


class GoldExperimentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name)/"experiment.sqlite3"
        self.addCleanup(self.temp.cleanup)

    def register(self):
        return register_experiment(report(), registered_at="2026-10-08T12:00:00+00:00", db_path=self.db)

    def test_registration_is_frozen_and_does_not_train_on_future(self):
        r = report()
        r["samples"].extend({"horizon_days":h,"decision_at":"2026-10-01","evaluated_at":"2026-11-01","direction_up":1} for h in [21,63])
        first = register_experiment(r,registered_at="2026-10-08T12:00:00+00:00",db_path=self.db)
        again = register_experiment(report(),registered_at="2026-12-01T12:00:00+00:00",db_path=self.db)
        self.assertEqual(first,again)
        self.assertEqual(first["base"]["21"]["sample_size"],25)
        self.assertEqual(first["base"]["21"]["probability"],48)
        with sqlite3.connect(self.db) as c:
            with self.assertRaises(sqlite3.IntegrityError):
                c.execute("UPDATE experiment_registry SET registered_at='2026-01-01'")

    def test_unregistered_read_does_not_create_database(self):
        self.assertEqual(experiment_summary(db_path=self.db)["status"],"NOT_REGISTERED")
        self.assertFalse(self.db.exists())

    def test_three_years_required_and_blend_fixed(self):
        self.assertIsNone(predict_blend([("2026-01-01",100)]*756,48,21))
        points=clean_prices(prices("2026-10-15")["points"],"2026-10-15T20:30:00+00:00")
        result=predict_blend(points,48,21)
        self.assertAlmostEqual(result["probability"],.5*result["trend"]+24,places=3)

    def test_future_and_unclosed_candles_are_invisible(self):
        points=[{"date":"2026-10-14","close":100},{"date":"2026-10-15","close":200},{"date":"2026-10-16","close":300}]
        clean=clean_prices(points,"2026-10-15T19:00:00+00:00")
        self.assertEqual(clean,[("2026-10-14",100)])
        with self.assertRaises(ValueError):
            clean_prices([{"date":"2026-10-14","close":100},{"date":"2026-10-14","close":101}],"2026-10-15T20:30:00+00:00")

    def test_previews_do_not_record_and_monthly_capture_deduplicates(self):
        self.register(); cache=prices("2026-10-15"); active=outlook(cache)
        args=dict(captured_at="2026-10-15T20:30:00+00:00",prices=cache,db_path=self.db)
        view=update_experiment(active,**args)
        self.assertEqual(view["horizons"][0]["predictions"],0)
        saved=update_experiment(active,persist=True,**args)
        repeated=update_experiment(active,persist=True,**args)
        self.assertEqual(saved["horizons"][0]["predictions"],1)
        self.assertEqual(repeated["horizons"][0]["predictions"],1)
        self.assertFalse(saved["score_enabled"])
        with sqlite3.connect(self.db) as c:
            with self.assertRaises(sqlite3.IntegrityError):
                c.execute("UPDATE experiment_predictions SET probability=99")

    def test_before_cut_day_stale_future_cache_and_changed_production_block_capture(self):
        self.register()
        for day, status in [("2026-10-14","OK"),("2026-10-15","STALE")]:
            cache={**prices(day),"status":status}
            v=update_experiment(outlook(cache),persist=True,captured_at=f"{day}T20:30:00+00:00",prices=cache,db_path=self.db)
            self.assertEqual(v["horizons"][0]["predictions"],0)
        cache=prices("2026-10-15",hour="21:00")
        v=update_experiment(outlook(cache),persist=True,captured_at="2026-10-15T20:30:00+00:00",prices=cache,db_path=self.db)
        self.assertEqual(v["horizons"][0]["predictions"],0)
        v=update_experiment({**outlook(cache),"model_fingerprint":"changed"},db_path=self.db)
        self.assertEqual(v["status"],"PRODUCTION_CHANGED")

    def test_modified_implementation_is_blocked(self):
        self.register()
        with patch("gold_experiment._implementation",return_value="changed"):
            self.assertEqual(experiment_summary(db_path=self.db)["status"],"RULES_CHANGED")

    def test_outcomes_are_only_settled_after_observed_sessions(self):
        self.register(); initial=prices("2026-10-15")
        update_experiment(outlook(initial),persist=True,captured_at="2026-10-15T20:30:00+00:00",prices=initial,db_path=self.db)
        future = pd.bdate_range("2026-10-16","2026-11-13")
        cache={"status":"OK","fetched_at":"2026-11-13T21:20:00+00:00",
               "points":initial["points"]+[{"date":d.date().isoformat(),"close":130} for d in future]}
        update_experiment(outlook(cache),persist=True,captured_at="2026-11-13T21:30:00+00:00",prices=cache,db_path=self.db)
        v=experiment_summary(db_path=self.db,cutoff="2026-11-14T12:00:00+00:00")
        self.assertEqual(v["horizons"][0]["settled"],1)
        self.assertEqual(v["horizons"][1]["settled"],0)
        self.assertIsNone(v["horizons"][0]["brier_score"])
        with sqlite3.connect(self.db) as c:
            with self.assertRaises(sqlite3.IntegrityError):
                c.execute("UPDATE experiment_outcomes SET direction_up=0")
