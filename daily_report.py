"""
Informe diario exportable de NEXUS (texto + HTML imprimible a PDF).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from config import REPORTS_DIR
from paper_trading import summarize_paper_trading
from signal_track_record import evaluate_track_record


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def build_daily_report(snapshot: Dict[str, Any] | None = None) -> Dict[str, str]:
    if snapshot is None:
        from nexus_desktop import build_snapshot
        snap = build_snapshot(use_news=True, export=False)
    else:
        snap = snapshot
    data = snap["data"]
    decision = snap["decision"]
    rotation = snap["rotation"]
    paper = summarize_paper_trading(limit=5)
    track = evaluate_track_record(forward_days=5, limit=100)

    macro = decision.get("macro_action") or decision.get("action")
    ops = decision.get("operational_action") or decision.get("action")
    lines = [
        f"INFORME DIARIO NEXUS — {snap.get('captured_at_utc', _now_stamp())}",
        "",
        "RESUMEN",
        f"  Estado motor   : {snap.get('status')}",
        f"  Macro          : {macro}",
        f"  Operativa      : {ops}",
        f"  Score          : {decision.get('score')}/100",
        f"  Confianza      : {decision.get('confidence')}",
        f"  Pausa          : {decision.get('operational_pause_reason') or '—'}",
        "",
        "PULSO MERCADO",
        f"  VIX            : {data.get('VIX')}",
        f"  Bono 10Y       : {data.get('US10Y')}%",
        f"  Curva 2Y-10Y   : {data.get('Yield_Curve_Spread')} pp",
        f"  IPC YoY        : {data.get('CPI_YoY_Pct')}%",
        f"  M2 14s         : {data.get('M2_Change_Pct')}%",
        "",
        "GLOBAL",
    ]
    for region, metrics in (data.get("GlobalMarkets") or {}).items():
        lines.append(f"  {region:<10} 1M {metrics.get('momentum_1m'):+.2f}%" if metrics.get("momentum_1m") is not None else f"  {region:<10} —")
    lines.extend([
        "",
        "ROTACIÓN",
        f"  Estado         : {rotation.get('state')}",
        f"  Leaders 1M     : {rotation.get('leaders_avg_1m')}",
        f"  Receivers 1M   : {rotation.get('receivers_avg_1m')}",
        "",
        "PAPER TRADING",
        f"  Retorno NEXUS  : {paper.get('total_return_pct'):+.2f}%",
        f"  Buy&Hold SPY   : {paper.get('benchmark_return_pct'):+.2f}%",
        f"  Alpha vs SPY   : {paper.get('alpha_vs_spy_pct'):+.2f}%",
        "",
        "TRACK RECORD",
        f"  Muestras       : {track.get('sample_size', 0)}",
        f"  Acierto macro  : {track.get('macro_buy_hit_rate_pct', '—')}%",
        "",
        "ALERTAS",
    ])
    for alert in snap.get("alerts", [])[:8]:
        lines.append(f"  - {alert}")

    text_report = "\n".join(lines)
    html_report = _to_html(snap, paper, track, text_report)
    return {"text": text_report, "html": html_report}


def _to_html(snapshot, paper, track, text_report: str) -> str:
    escaped = text_report.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><title>Informe NEXUS</title>
<style>
body {{ font-family: Menlo, monospace; background:#fff; color:#111; padding:24px; max-width:900px; margin:auto; }}
h1 {{ color:#0b4f6c; }} pre {{ white-space: pre-wrap; line-height: 1.5; }}
</style></head><body>
<h1>Informe Diario NEXUS</h1>
<p>Generado: {snapshot.get('captured_at_utc', _now_stamp())}</p>
<pre>{escaped}</pre>
<p><em>Abre en Safari/Chrome → Imprimir → Guardar como PDF.</em></p>
</body></html>"""


def export_daily_report(snapshot: Dict[str, Any] | None = None, reports_dir: Path = REPORTS_DIR) -> Dict[str, str]:
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = _now_stamp()
    report = build_daily_report(snapshot)
    text_path = reports_dir / f"daily_{stamp}.txt"
    html_path = reports_dir / f"daily_{stamp}.html"
    text_path.write_text(report["text"], encoding="utf-8")
    html_path.write_text(report["html"], encoding="utf-8")
    return {"text_path": str(text_path), "html_path": str(html_path)}


def format_daily_report(snapshot: Dict[str, Any] | None = None) -> str:
    return build_daily_report(snapshot)["text"]


if __name__ == "__main__":
    paths = export_daily_report()
    print(format_daily_report())
    print("")
    print(f"Exportado: {paths['text_path']}")
    print(f"Exportado: {paths['html_path']}")
