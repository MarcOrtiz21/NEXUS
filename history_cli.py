#!/usr/bin/env python3
"""CLI para consultar historial y paper trading de NEXUS."""

import argparse
import sys

from history_view import format_history_report, summarize_history
from paper_trading import format_paper_report, summarize_paper_trading


def main() -> None:
    parser = argparse.ArgumentParser(description="Consulta historial y paper trading de NEXUS")
    parser.add_argument("--limit", type=int, default=20, help="Número de snapshots a consultar")
    parser.add_argument("--paper", action="store_true", help="Mostrar reporte de paper trading")
    parser.add_argument("--json", action="store_true", help="Salida JSON resumida")
    args = parser.parse_args()

    if sys.stdout.encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    if args.paper:
        if args.json:
            import json
            print(json.dumps(summarize_paper_trading(limit=args.limit), ensure_ascii=False, indent=2))
        else:
            print(format_paper_report(limit=args.limit))
        return

    if args.json:
        import json
        print(json.dumps(summarize_history(limit=args.limit), ensure_ascii=False, indent=2))
    else:
        print(format_history_report(limit=args.limit))


if __name__ == "__main__":
    main()
