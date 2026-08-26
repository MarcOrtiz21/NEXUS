import unittest

from decision_intelligence import (
    apply_stance_confidence,
    build_fx_gold_digest,
    build_fx_gold_plan,
    build_session_digest,
    build_session_plan,
    classify_market_regime,
    classify_vix_regime,
    compact_score_drivers,
    data_quality_summary,
    detect_market_anomalies,
    freshness_layers,
    fx_gold_operational_alignment,
    prior_history_row,
    refine_stance_confidence,
    rotation_flow_bucket,
    rotation_operational_alignment,
    score_attribution,
    track_record_thesis,
)


class DecisionIntelligenceTests(unittest.TestCase):
    def test_regime_marks_stress_from_high_vix(self):
        result = classify_market_regime({"VIX": 31, "Assets": {"SPY": {}}})
        self.assertEqual(result["label"], "ESTRÉS")

    def test_vix_regime_uses_config_bands_not_raw_points(self):
        calm = classify_vix_regime(14)
        caution = classify_vix_regime(26)
        stress = classify_vix_regime(32)
        self.assertEqual(calm["label"], "CALMA")
        self.assertEqual(calm["multiplier"], 1.0)
        self.assertEqual(caution["label"], "CAUTELA")
        self.assertLess(caution["multiplier"], 1.0)
        self.assertEqual(stress["label"], "ESTRÉS")
        self.assertGreater(stress["penalty"], caution["penalty"])

    def test_anomalies_detect_vix_and_negative_momentum(self):
        data = {
            "VIX": 30,
            "VIX_MA20": 20,
            "Yield_Curve_Spread": -0.4,
            "Assets": {"SPY": {"momentum_1m": -6}},
        }
        self.assertEqual(len(detect_market_anomalies(data)), 4)

    def test_quality_and_attribution_are_descriptive(self):
        data = {
            "DataQuality": {"VIX": {"status": "OK"}, "CPI": {"status": "MISSING"}},
            "Assets": {"SPY": {"momentum_1m": 2}},
            "VIX": 15,
        }
        self.assertEqual(data_quality_summary(data)["unhealthy"], 1)
        self.assertEqual(score_attribution(data, {"score": 60})["score"], 60)

    def test_flow_bucket_matches_rotation_columns(self):
        self.assertEqual(rotation_flow_bucket("Entrada clara de flujo"), "recibiendo")
        self.assertEqual(rotation_flow_bucket("Mejora incipiente"), "recibiendo")
        self.assertEqual(rotation_flow_bucket("Descanso sano tras liderazgo"), "perdiendo")
        self.assertEqual(rotation_flow_bucket("Corrección activa"), "perdiendo")
        self.assertEqual(rotation_flow_bucket("Liderazgo aún fuerte"), "neutrales")

    def test_alignment_warns_when_operativa_pauses_and_rotation_is_buying(self):
        result = rotation_operational_alignment(
            {
                "operational_action": "ESPERAR / NO ABRIR",
                "operational_pause_reason": "Filtro de riesgo activo (calendario macro US o sentimiento extremo)",
            },
            {
                "themes": [
                    {"ticker": "XBI", "theme": "Biotecnología", "signal": "Entrada clara de flujo"},
                    {"ticker": "XLK", "theme": "Tecnología grande", "signal": "Liderazgo aún fuerte"},
                ]
            },
            {"should_block": True},
        )
        self.assertTrue(result["conflict"])
        self.assertEqual(result["receiving_count"], 1)
        self.assertIn("vigilancia", result["detail"])

    def test_alignment_silent_when_operativa_allows_entry(self):
        result = rotation_operational_alignment(
            {"operational_action": "COMPRAR", "operational_pause_reason": None},
            {"themes": [{"ticker": "XBI", "theme": "Biotecnología", "signal": "Entrada clara de flujo"}]},
            {"should_block": False},
        )
        self.assertFalse(result["conflict"])
        self.assertEqual(result["stance"], "aligned")

    def test_alignment_silent_when_no_receiving_themes(self):
        result = rotation_operational_alignment(
            {"operational_action": "ESPERAR / NO ABRIR", "operational_pause_reason": "calendario"},
            {"themes": [{"ticker": "XLK", "signal": "Liderazgo aún fuerte"}]},
        )
        self.assertFalse(result["conflict"])

    def test_fx_alignment_warns_when_operativa_pauses_and_fx_is_directional(self):
        result = fx_gold_operational_alignment(
            {
                "operational_action": "ESPERAR / NO ABRIR",
                "operational_pause_reason": "calendario",
            },
            {"should_block": True},
            {"action": "COMPRAR EURO / VENDER DOLAR", "rel_1m": 1.2},
            {"bias": "MIXTO"},
        )
        self.assertTrue(result["conflict"])
        self.assertIn("vigilancia", result["detail"])

    def test_fx_alignment_silent_when_fx_and_gold_are_waiting(self):
        result = fx_gold_operational_alignment(
            {"operational_action": "ESPERAR / NO ABRIR", "operational_pause_reason": "calendario"},
            {"should_block": True},
            {"action": "MANTENER / ESPERAR", "rel_1m": 0.1},
            {"bias": "MIXTO"},
        )
        self.assertFalse(result["conflict"])

    def test_fx_alignment_silent_when_operativa_allows_entry(self):
        result = fx_gold_operational_alignment(
            {"operational_action": "COMPRAR", "operational_pause_reason": None},
            {"should_block": False},
            {"action": "COMPRAR EURO / VENDER DOLAR", "rel_1m": 1.1},
            {"bias": "REFUGIO"},
        )
        self.assertFalse(result["conflict"])
        self.assertEqual(result["stance"], "aligned")

    def test_prior_row_skips_just_exported_snapshot(self):
        rows = [{"captured_at": "a"}, {"captured_at": "b"}]
        self.assertEqual(prior_history_row(rows, exported=True)["captured_at"], "a")
        self.assertEqual(prior_history_row(rows, exported=False)["captured_at"], "b")
        self.assertIsNone(prior_history_row([{"captured_at": "only"}], exported=True))

    def test_session_digest_reports_action_vix_and_rotation_crossings(self):
        digest = build_session_digest(
            {
                "operational_action": "ESPERAR / NO ABRIR",
                "score": 52,
                "vix": 18.4,
                "rotation_themes": [
                    {"ticker": "XBI", "theme": "Biotecnología", "signal": "Entrada clara de flujo"},
                    {"ticker": "XLE", "theme": "Energía tradicional", "signal": "Corrección activa"},
                    {"ticker": "XLK", "theme": "Tecnología grande", "signal": "Liderazgo aún fuerte"},
                ],
            },
            {
                "captured_at": "2026-08-16T08:00:00+00:00",
                "operational_action": "COMPRAR",
                "score": 61,
                "vix": 14.2,
                "rotation_themes": [
                    {"ticker": "XBI", "theme": "Biotecnología", "signal": "Aún sin confirmación"},
                    {"ticker": "XLE", "theme": "Energía tradicional", "signal": "Mejora incipiente"},
                    {"ticker": "XLK", "theme": "Tecnología grande", "signal": "Liderazgo aún fuerte"},
                ],
            },
        )
        self.assertTrue(digest["has_prior"])
        self.assertTrue(digest["action"]["changed"])
        self.assertEqual(digest["score"]["delta"], -9.0)
        self.assertEqual(digest["vix"]["delta"], 4.2)
        tickers = {item["ticker"] for item in digest["rotation_crossings"]}
        self.assertEqual(tickers, {"XBI", "XLE"})
        self.assertIn("ESPERAR", digest["headline"])

    def test_session_digest_without_prior_rotation_explains_gap(self):
        digest = build_session_digest(
            {"operational_action": "COMPRAR", "score": 70, "vix": 12, "rotation_themes": []},
            {"operational_action": "COMPRAR", "score": 68, "vix": 12.5},
        )
        self.assertEqual(digest["rotation_crossings"], [])
        self.assertIn("rotación", (digest["rotation_note"] or "").lower())

    def test_fx_gold_digest_without_prior(self):
        digest = build_fx_gold_digest(
            {"eurusd": 1.17, "gld": 310, "forex_action": "MANTENER / ESPERAR", "gold_bias": "MIXTO"},
            None,
        )
        self.assertFalse(digest["has_prior"])
        self.assertIn("evaluación anterior", digest["headline"].lower())
        self.assertEqual(digest["eurusd"]["label"], "sin base previa")
        self.assertEqual(digest["forex_action"]["label"], "MANTENER / ESPERAR")

    def test_fx_gold_digest_reports_pips_and_action_change(self):
        digest = build_fx_gold_digest(
            {
                "eurusd": 1.1720,
                "gld": 312.4,
                "forex_action": "COMPRAR EURO / VENDER DOLAR",
                "gold_bias": "REFUGIO",
            },
            {
                "captured_at": "2026-08-16T08:00:00+00:00",
                "forex_action": "MANTENER / ESPERAR",
                "gold_bias": "MIXTO",
                "prices": {"EURUSD": 1.1700, "GLD": 310.0},
            },
        )
        self.assertTrue(digest["has_prior"])
        self.assertTrue(digest["forex_action"]["changed"])
        self.assertEqual(digest["eurusd"]["pips"], 20.0)
        self.assertEqual(digest["gld"]["delta"], 2.4)
        self.assertIn("20", digest["eurusd"]["label"])
        self.assertIn("COMPRAR EURO", digest["headline"])

    def test_fx_gold_digest_ignores_missing_prior_action(self):
        digest = build_fx_gold_digest(
            {"eurusd": 1.1701, "gld": 310.1, "forex_action": "MANTENER / ESPERAR", "gold_bias": "MIXTO"},
            {"captured_at": "2026-08-16T08:00:00+00:00", "prices": {"EURUSD": 1.1700, "GLD": 310.0}},
        )
        self.assertFalse(digest["forex_action"]["changed"])
        self.assertFalse(digest["gold_bias"]["changed"])
        self.assertIn("próxima captura", digest["summary"].lower())
        self.assertIn("Sin cambios relevantes", digest["headline"])

    def test_fx_plan_is_wait_and_buy_nothing_when_operativa_pauses(self):
        plan = build_fx_gold_plan(
            {"operational_action": "ESPERAR / NO ABRIR", "operational_pause_reason": "calendario"},
            {"should_block": True},
            {"action": "COMPRAR EURO / VENDER DOLAR"},
            {"bias": "MIXTO"},
        )
        self.assertEqual(plan["stance"], "ESPERAR")
        self.assertEqual(plan["buy"], "Nada ahora")
        self.assertIn("No comprar", plan["verdict"])

    def test_fx_plan_names_euro_when_operativa_allows_buy(self):
        plan = build_fx_gold_plan(
            {"operational_action": "COMPRAR", "operational_pause_reason": None},
            {"should_block": False},
            {"action": "COMPRAR EURO / VENDER DOLAR"},
            {"bias": "MIXTO"},
        )
        self.assertEqual(plan["stance"], "COMPRAR")
        self.assertIn("EURO", plan["buy"])
        self.assertTrue(plan["allows_entry"])

    def test_session_plan_names_fx_bias_when_operativa_pauses(self):
        plan = build_session_plan(
            {
                "operational_action": "ESPERAR / NO ABRIR",
                "macro_action": "COMPRAR",
                "operational_pause_reason": "calendario",
                "macro_allocation": {"SPY": 45, "QQQ": 20, "CASH": 35},
                "favored_assets": ["Liquidez"],
            },
            {"should_block": True, "block_hours": 6},
            {"action": "COMPRAR EURO / VENDER DOLAR"},
            {"bias": "MIXTO"},
        )
        self.assertEqual(plan["stance"], "ESPERAR")
        self.assertEqual(plan["buy_label"], "AHORA")
        self.assertEqual(plan["buy"], "Nada ahora")
        self.assertIn("No abrir", plan["verdict"])
        self.assertIn("calendario", plan["verdict"])
        spy = next(item for item in plan["legs"] if item["ticker"] == "SPY")
        self.assertEqual(spy["now"], "NO ABRIR")
        self.assertEqual(spy["open_weight"], 45)
        self.assertIn("cartera", spy["weight_note"].lower())
        fx = next(item for item in plan["legs"] if item["ticker"] == "EURUSD")
        self.assertEqual(fx["now"], "NO ABRIR")
        self.assertIn("euro", fx["verb"].lower())
        labels = {item["label"]: item["value"] for item in plan["context"]}
        self.assertEqual(labels["FX"], "Comprar euro / vender dólar")
        self.assertIn("Activo", labels["BLOQUEO"])

    def test_session_plan_is_buy_when_operativa_allows(self):
        plan = build_session_plan(
            {
                "operational_action": "COMPRAR",
                "macro_action": "COMPRAR",
                "operational_pause_reason": None,
                "allocation": {"SPY": 50, "QQQ": 20, "CASH": 30},
                "favored_assets": ["S&P 500"],
            },
            {"should_block": False},
            {"action": "COMPRAR EURO / VENDER DOLAR"},
            {"bias": "REFUGIO"},
        )
        self.assertEqual(plan["stance"], "COMPRAR")
        self.assertEqual(plan["buy_label"], "COMPRAR")
        self.assertIn("euro", plan["buy"].lower())
        self.assertTrue(plan["allows_entry"])
        self.assertIn("COMPRAR", plan["verdict"])
        spy = next(item for item in plan["legs"] if item["ticker"] == "SPY")
        self.assertEqual(spy["now"], "COMPRAR")
        self.assertEqual(spy["open_weight"], 50)

    def test_freshness_headline_uses_layer_ages(self):
        result = freshness_layers({
            "Freshness": {
                "market": {"label": "Mercado", "age_seconds": 180, "status": "STALE"},
                "macro": {"label": "Macro", "age_seconds": 7200, "status": "OK"},
                "companies": {"label": "Empresas", "age_seconds": 90000, "status": "STALE"},
            }
        })
        self.assertEqual(result["tone"], "warn")
        self.assertIn("Mercado 3 min", result["headline"])
        self.assertIn("Macro 2 h", result["headline"])
        self.assertIn("Empresas 1 d", result["headline"])

    def test_freshness_macro_headline_adds_observation_date(self):
        result = freshness_layers({
            "Freshness": {
                "market": {"label": "Mercado", "age_seconds": 20, "status": "OK"},
                "macro": {"label": "Macro", "age_seconds": 7200, "status": "OK", "as_of": "2026-07-15"},
                "companies": {"label": "Empresas", "age_seconds": 400, "status": "OK"},
            }
        })
        self.assertIn("Macro 2 h · obs. 15 jul", result["headline"])

    def test_confidence_drops_when_sanity_rejects_a_print(self):
        result = refine_stance_confidence(
            {"confidence": "ALTA"},
            {
                "Freshness": {"market": {"status": "OK", "age_seconds": 20}},
                "DataQuality": {
                    "VIX": {"status": "MISSING", "detail": "saneamiento cruzado: VIX 140.0 fuera de rango"},
                },
            },
        )
        self.assertEqual(result["level"], "BAJA")
        self.assertTrue(any("cruce" in reason for reason in result["reasons"]))

    def test_confidence_drops_when_market_cache_is_stale(self):
        result = refine_stance_confidence(
            {"confidence": "ALTA", "score": 80},
            {"Freshness": {"market": {"status": "STALE", "age_seconds": 4000, "label": "Mercado"}}},
        )
        self.assertEqual(result["level"], "MEDIA")
        self.assertIn("mercado", result["note"].lower())

    def test_confidence_drops_for_estimated_calendar_block(self):
        result = refine_stance_confidence(
            {"confidence": "ALTA"},
            {"Freshness": {"market": {"status": "OK", "age_seconds": 20}}},
            {"should_block": True, "confidence": "LOW"},
        )
        self.assertEqual(result["level"], "MEDIA")
        self.assertIn("calendario", result["note"].lower())

    def test_apply_stance_confidence_mutates_decision(self):
        decision = {"confidence": "ALTA", "missing_inputs": ["VIX"]}
        apply_stance_confidence(decision, {}, {})
        self.assertEqual(decision["confidence"], "BAJA")
        self.assertTrue(decision["confidence_note"])

    def test_score_drivers_group_rules_without_inventing_weights(self):
        drivers = compact_score_drivers({
            "score_breakdown": [
                {"factor": "Volatilidad", "reason": "VIX contenido"},
                {"factor": "Volatilidad", "reason": "sin pánico"},
                {"factor": "Tipos y liquidez", "reason": "curva no invertida"},
            ]
        })
        self.assertEqual(drivers[0]["factor"], "Volatilidad")
        self.assertIn("VIX contenido", drivers[0]["detail"])
        self.assertEqual(len(drivers), 2)

    def test_track_record_thesis_warns_when_buy_misses_spy(self):
        thesis = track_record_thesis({
            "sample_size": 20,
            "forward_days": 5,
            "macro_buy_count": 8,
            "macro_buy_hit_rate_pct": 37.5,
            "macro_buy_avg_return_pct": -0.4,
        })
        self.assertFalse(thesis["beats_spy"])
        self.assertEqual(thesis["tone"], "warn")
        self.assertIn("no se confirmó", thesis["headline"])

    def test_track_record_thesis_mentions_twenty_day_hit_rate(self):
        thesis = track_record_thesis({
            "sample_size": 20,
            "forward_days": 5,
            "macro_buy_count": 8,
            "macro_buy_hit_rate_pct": 62.5,
            "macro_buy_avg_return_pct": 0.8,
            "macro_buy_count_20d": 8,
            "macro_buy_hit_rate_20d_pct": 50.0,
        })
        self.assertIn("20d", thesis["detail"])
        self.assertEqual(thesis["hit_rate_20d_pct"], 50.0)

    def test_session_plan_exposes_confidence_and_score_drivers(self):
        plan = build_session_plan(
            {
                "operational_action": "ESPERAR / NO ABRIR",
                "macro_action": "COMPRAR",
                "operational_pause_reason": "calendario",
                "confidence": "MEDIA",
                "confidence_note": "Bajada: calendario estimado, no oficial",
                "score": 62,
                "score_breakdown": [{"factor": "Volatilidad", "reason": "VIX contenido"}],
                "macro_allocation": {"SPY": 45, "CASH": 55},
            },
            {"should_block": True, "block_hours": 6},
            {},
            {"bias": "MIXTO"},
        )
        self.assertEqual(plan["confidence"], "MEDIA")
        self.assertIn("calendario", plan["confidence_note"])
        self.assertEqual(plan["score_drivers"][0]["factor"], "Volatilidad")
        self.assertEqual(plan["score"], 62)


if __name__ == "__main__":
    unittest.main()
