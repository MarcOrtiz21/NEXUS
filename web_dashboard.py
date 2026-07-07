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
from paper_trading import summarize_paper_trading
from risk_filters.news_feed import fetch_news_items
from rotation_engine import RotationEngine

app = FastAPI(title="NEXUS Dashboard", version="1.1")


def _build_live_snapshot() -> dict:
    data = fetch_market_data()
    news_items = fetch_news_items(max_per_feed=6)
    logic = LogicEngine(data, news_items=news_items)
    status, alerts = logic.evaluate()
    decision = DecisionEngine(data, status, alerts).evaluate()
    rotation = RotationEngine(data).evaluate()
    return {
        "status": status.value,
        "alerts": alerts[:12],
        "decision": decision.to_dict(),
        "rotation": rotation.to_dict(),
        "market": {
            "VIX": data.get("VIX"),
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
    .grid { display:grid; grid-template-columns: repeat(auto-fit,minmax(320px,1fr)); gap:16px; }
    .card { background:#0B0F17; border:1px solid #293245; border-radius:10px; padding:16px; }
    h1 { color:#3ED6FF; }
    h2 { color:#8D9BB0; font-size:14px; margin-top:0; }
    .metric { font-size:28px; color:#36C26A; }
    canvas { background:#101625; border-radius:8px; padding:8px; }
  </style>
</head>
<body>
  <h1>NEXUS Dashboard</h1>
  <div class="grid">
    <div class="card"><h2>Estado</h2><div id="status" class="metric">—</div><div id="action"></div></div>
    <div class="card"><h2>Score</h2><div id="score" class="metric">—</div><div id="confidence"></div></div>
    <div class="card"><h2>Macro</h2><div id="macro"></div></div>
    <div class="card"><h2>Paper Trading</h2><div id="paper"></div></div>
  </div>
  <div class="card" style="margin-top:16px;">
    <h2>Evolución del score</h2>
    <canvas id="scoreChart" height="100"></canvas>
  </div>
  <script>
    let chart;
    async function refresh() {
      const [live, history, paper] = await Promise.all([
        fetch('/api/live').then(r => r.json()),
        fetch('/api/history').then(r => r.json()),
        fetch('/api/paper').then(r => r.json()),
      ]);
      document.getElementById('status').textContent = live.status;
      document.getElementById('action').textContent = 'Acción: ' + live.decision.action;
      document.getElementById('score').textContent = live.decision.score + '/100';
      document.getElementById('confidence').textContent = 'Confianza: ' + live.decision.confidence;
      document.getElementById('macro').innerHTML = [
        'VIX: ' + live.market.VIX,
        '10Y: ' + live.market.US10Y + '%',
        'Curva 2Y-10Y: ' + live.market.Yield_Curve_Spread,
        'IPC YoY: ' + live.market.CPI_YoY_Pct + '%',
        'M2 14s: ' + live.market.M2_Change_Pct + '%',
        'China M2 YoY: ' + live.market.China_M2_YoY_Pct + '%',
      ].map(x => '<div>' + x + '</div>').join('');
      document.getElementById('paper').innerHTML = [
        'Valor: $' + Number(paper.portfolio.current_value).toLocaleString(),
        'Retorno: ' + paper.total_return_pct + '%',
        'Última acción: ' + paper.portfolio.last_action,
      ].map(x => '<div>' + x + '</div>').join('');

      const labels = history.score_timeline.map(p => (p.captured_at || '').slice(0, 16));
      const scores = history.score_timeline.map(p => p.score);
      if (!chart) {
        chart = new Chart(document.getElementById('scoreChart'), {
          type: 'line',
          data: { labels, datasets: [{ label: 'Score NEXUS', data: scores, borderColor:'#3ED6FF', tension:0.2 }] },
          options: { scales: { y: { min: 0, max: 100 } } }
        });
      } else {
        chart.data.labels = labels;
        chart.data.datasets[0].data = scores;
        chart.update();
      }
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


@app.get("/api/history")
def api_history() -> JSONResponse:
    return JSONResponse(summarize_history(limit=100))


@app.get("/api/paper")
def api_paper() -> JSONResponse:
    return JSONResponse(summarize_paper_trading(limit=50))


def main() -> None:
    import uvicorn
    uvicorn.run("web_dashboard:app", host=WEB_DASHBOARD_HOST, port=WEB_DASHBOARD_PORT, reload=False)


if __name__ == "__main__":
    main()
