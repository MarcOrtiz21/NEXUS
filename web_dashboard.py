"""
Dashboard web local para NEXUS (FastAPI).
"""

from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from config import WEB_DASHBOARD_HOST, WEB_DASHBOARD_PORT
from data_ingestion import fetch_market_data
from decision_engine import DecisionEngine
from history_view import summarize_history
from logic_engine import LogicEngine
from native_api import build_native_snapshot
from paper_trading import summarize_paper_trading
from risk_filters.calendar import check_macro_events
from risk_filters.news_feed import fetch_news_items
from rotation_engine import RotationEngine
from signal_track_record import evaluate_track_record

app = FastAPI(title="NEXUS Dashboard", version="1.4")


def _build_live_snapshot() -> dict:
    data = fetch_market_data()
    news_items = fetch_news_items(max_per_feed=6)
    logic = LogicEngine(data, news_items=news_items)
    status, alerts = logic.evaluate()
    sentiment_result = getattr(logic, "sentiment_result", None)
    decision = DecisionEngine(data, status, alerts, sentiment_result=sentiment_result).evaluate()
    rotation = RotationEngine(data).evaluate()
    calendar = check_macro_events()
    return {
        "status": status.value,
        "alerts": alerts[:12],
        "decision": decision.to_dict(),
        "rotation": rotation.to_dict(),
        "calendar": {
            "should_block": calendar.get("should_block_signals"),
            "block_hours": calendar.get("block_hours"),
            "next_event": calendar.get("next_event"),
        },
        "market": {
            "VIX": data.get("VIX"),
            "VIX_MA20": data.get("VIX_MA20"),
            "US10Y": data.get("US10Y"),
            "US2Y": data.get("US2Y"),
            "Yield_Curve_Spread": data.get("Yield_Curve_Spread"),
            "CPI_YoY_Pct": data.get("CPI_YoY_Pct"),
            "M2_Change_Pct": data.get("M2_Change_Pct"),
            "China_M2_YoY_Pct": data.get("China_M2_YoY_Pct"),
            "PE_Forward": data.get("PE_Forward"),
            "PE_Forward_Percentile": data.get("PE_Forward_Percentile"),
            "Correlation_Proxy": data.get("Correlation_Proxy"),
        },
        "global_markets": data.get("GlobalMarkets", {}),
        "news_count": len(news_items),
        "news_items": news_items[:24],
        "news_sources": sorted({str(i.get("source") or "RSS") for i in news_items}),
    }


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return """
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <title>NEXUS Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    body { font-family: Menlo, monospace; background:#05070B; color:#D7DEE9; margin:0; padding:24px; }
    .grid { display:grid; grid-template-columns: repeat(auto-fit,minmax(280px,1fr)); gap:16px; }
    .card { background:#0B0F17; border:1px solid #293245; border-radius:10px; padding:16px; }
    h1 { color:#3ED6FF; margin-bottom:8px; }
    h2 { color:#8D9BB0; font-size:14px; margin-top:0; }
    .metric { font-size:28px; color:#36C26A; }
    .sub { color:#8D9BB0; font-size:12px; margin-top:6px; }
    canvas { background:#101625; border-radius:8px; padding:8px; width:100% !important; }
    .charts { display:grid; grid-template-columns: repeat(auto-fit,minmax(420px,1fr)); gap:16px; margin-top:16px; }
  </style>
</head>
<body>
  <h1>NEXUS Dashboard</h1>
  <div class="grid">
    <div class="card"><h2>Estado motor</h2><div id="status" class="metric">—</div><div id="calendar" class="sub"></div></div>
    <div class="card"><h2>Diagnóstico macro</h2><div id="macroAction" class="metric">—</div><div id="score" class="sub"></div></div>
    <div class="card"><h2>Señal operativa</h2><div id="opsAction" class="metric">—</div><div id="confidence" class="sub"></div></div>
    <div class="card"><h2>Paper vs SPY</h2><div id="paper"></div></div>
  </div>
  <div class="charts">
    <div class="card"><h2>Evolución del score</h2><canvas id="scoreChart" height="110"></canvas></div>
    <div class="card"><h2>VIX vs MA20</h2><canvas id="vixChart" height="110"></canvas></div>
    <div class="card"><h2>Curva 2Y-10Y (pp)</h2><canvas id="curveChart" height="110"></canvas></div>
    <div class="card"><h2>Rotación sectorial 1M</h2><canvas id="rotationChart" height="110"></canvas></div>
    <div class="card"><h2>Cambios de señal</h2><canvas id="signalChart" height="110"></canvas></div>
    <div class="card"><h2>Track record (macro COMPRAR)</h2><div id="trackRecord" class="sub"></div></div>
  </div>
  <script>
    let scoreChart, vixChart, curveChart, rotationChart, signalChart;
    const vixHistory = [];
    const curveHistory = [];

    function pushHistory(arr, value, max=30) {
      if (value === null || value === undefined) return;
      arr.push(Number(value));
      if (arr.length > max) arr.shift();
    }

    async function refresh() {
      const [live, history, paper, track] = await Promise.all([
        fetch('/api/live').then(r => r.json()),
        fetch('/api/history').then(r => r.json()),
        fetch('/api/paper').then(r => r.json()),
        fetch('/api/track-record').then(r => r.json()),
      ]);

      document.getElementById('status').textContent = live.status;
      document.getElementById('calendar').textContent = live.calendar.should_block
        ? `Calendario: bloqueo ${live.calendar.block_hours}h`
        : (live.calendar.next_event ? 'Próximo evento macro registrado' : 'Sin bloqueo calendario');
      document.getElementById('macroAction').textContent = live.decision.macro_action || live.decision.action;
      document.getElementById('score').textContent = `Score ${live.decision.score}/100`;
      document.getElementById('opsAction').textContent = live.decision.operational_action || live.decision.action;
      document.getElementById('confidence').textContent = `Confianza: ${live.decision.confidence}`;

      document.getElementById('paper').innerHTML = [
        `NEXUS: ${paper.total_return_pct}%`,
        `SPY B&H: ${paper.benchmark_return_pct}%`,
        `Alpha: ${paper.alpha_vs_spy_pct}%`,
        `Valor: $${Number(paper.portfolio.current_value).toLocaleString()}`,
      ].map(x => `<div>${x}</div>`).join('');

      pushHistory(vixHistory, live.market.VIX);
      pushHistory(curveHistory, live.market.Yield_Curve_Spread);

      const labels = history.score_timeline.map(p => (p.captured_at || '').slice(0, 16));
      const scores = history.score_timeline.map(p => p.score);
      const macroActions = history.score_timeline.map(p => p.macro_action || p.action);
      const opsActions = history.score_timeline.map(p => p.operational_action || p.action);
      const divergences = macroActions.map((m, i) => m !== opsActions[i] ? 1 : 0);

      if (!scoreChart) {
        scoreChart = new Chart(document.getElementById('scoreChart'), {
          type: 'line',
          data: { labels, datasets: [{ label: 'Score', data: scores, borderColor:'#3ED6FF', tension:0.2 }] },
          options: { scales: { y: { min: 0, max: 100 } } }
        });
      } else {
        scoreChart.data.labels = labels; scoreChart.data.datasets[0].data = scores; scoreChart.update();
      }

      const vixLabels = vixHistory.map((_, i) => i + 1);
      if (!vixChart) {
        vixChart = new Chart(document.getElementById('vixChart'), {
          type: 'line',
          data: { labels: vixLabels, datasets: [
            { label: 'VIX', data: vixHistory, borderColor:'#EF4F68', tension:0.2 },
            { label: 'MA20 ref', data: vixHistory.map(() => live.market.VIX_MA20), borderColor:'#8D9BB0', borderDash:[4,4], tension:0.2 },
          ]},
          options: { scales: { y: { beginAtZero: false } } }
        });
      } else {
        vixChart.data.labels = vixLabels;
        vixChart.data.datasets[0].data = vixHistory;
        vixChart.data.datasets[1].data = vixHistory.map(() => live.market.VIX_MA20);
        vixChart.update();
      }

      if (!curveChart) {
        curveChart = new Chart(document.getElementById('curveChart'), {
          type: 'bar',
          data: { labels: curveHistory.map((_, i) => i + 1), datasets: [{ label: '2Y-10Y', data: curveHistory, backgroundColor:'#F7C948' }] },
          options: { scales: { y: { beginAtZero: false } } }
        });
      } else {
        curveChart.data.labels = curveHistory.map((_, i) => i + 1);
        curveChart.data.datasets[0].data = curveHistory;
        curveChart.update();
      }

      const rotLabels = ['Leaders', 'Receivers'];
      const rotValues = [live.rotation.leaders_avg_1m || 0, live.rotation.receivers_avg_1m || 0];
      if (!rotationChart) {
        rotationChart = new Chart(document.getElementById('rotationChart'), {
          type: 'bar',
          data: { labels: rotLabels, datasets: [{ label: '1M %', data: rotValues, backgroundColor:['#36C26A','#3ED6FF'] }] },
        });
      } else {
        rotationChart.data.datasets[0].data = rotValues;
        rotationChart.update();
      }

      if (!signalChart) {
        signalChart = new Chart(document.getElementById('signalChart'), {
          type: 'bar',
          data: { labels, datasets: [{ label: 'Macro≠Ops', data: divergences, backgroundColor:'#EF4F68' }] },
          options: { scales: { y: { min: 0, max: 1, ticks: { stepSize: 1 } } } }
        });
      } else {
        signalChart.data.labels = labels;
        signalChart.data.datasets[0].data = divergences;
        signalChart.update();
      }

      const tr = track.sample_size ? `${track.macro_buy_hit_rate_pct ?? '—'}% acierto macro (${track.sample_size} muestras)` : track.message;
      document.getElementById('trackRecord').textContent = tr;
    }
    refresh();
    setInterval(refresh, 60000);
  </script>
</body>
</html>
"""


@app.get("/api/live")
def api_live() -> JSONResponse:
    return JSONResponse(_build_live_snapshot())


@app.get("/api/native")
def api_native() -> JSONResponse:
    """Contrato completo para la app SwiftUI."""
    return JSONResponse(build_native_snapshot(export=False))


@app.get("/api/native/refresh")
def api_native_refresh() -> JSONResponse:
    """Igual que /api/native pero persistiendo snapshot en historial."""
    return JSONResponse(build_native_snapshot(export=True))


@app.get("/api/history")
def api_history() -> JSONResponse:
    return JSONResponse(summarize_history(limit=100))


@app.get("/api/paper")
def api_paper() -> JSONResponse:
    return JSONResponse(summarize_paper_trading(limit=50))


@app.get("/api/track-record")
def api_track_record() -> JSONResponse:
    return JSONResponse(evaluate_track_record(forward_days=5, limit=100))


@app.get("/api/health")
def api_health() -> JSONResponse:
    return JSONResponse({
        "ok": True,
        "service": "nexus",
        "version": "1.4",
        "capabilities": {"rotation_companies": True, "native_settings": True},
    })


def main() -> None:
    import uvicorn
    uvicorn.run("web_dashboard:app", host=WEB_DASHBOARD_HOST, port=WEB_DASHBOARD_PORT, reload=False)


if __name__ == "__main__":
    main()
