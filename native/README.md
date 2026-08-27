# NEXUS Native 3.5 (SwiftUI)

App macOS nativa que habla con el motor Python vía FastAPI (`http://127.0.0.1:8765`).

## Qué incluye

- Resumen ejecutivo con decisión, ranking, VIX, macro y calidad de datos.
- Terminal configurable con un panel principal y dos laterales.
- Preset propio persistente para tickers, intervalo y rango.
- Velas, volumen, medias, RSI con divergencias y MACD.
- Cursor compartido en precio e indicadores mientras se mantiene pulsado y se arrastra.
- Forex y oro, rotación sectorial, compañías, noticias e inspector técnico.
- Interfaz localizable en español e inglés.

## Arranque rápido

```bash
./scripts/run_native.command
```

O en dos terminales:

```bash
./run_dashboard.command
cd native && swift run
```

## API

- `GET /api/native` — payload completo para la UI
- `GET /api/native/refresh` — igual + exporta snapshot al historial
- `GET /api/native/chart/{ticker}` — series OHLCV por intervalo y rango
- `POST /api/native/settings` — preferencias de usuario
- `POST /api/native/watchlist` — lista de seguimiento
- `GET /api/health` — healthcheck

Requisitos: macOS 14+, Swift 5.9+, `.venv` del repo con dependencias NEXUS.
