# NEXUS Native (SwiftUI)

App macOS nativa que habla con el motor Python vía FastAPI (`http://127.0.0.1:8765`).

## Qué incluye

- Chip único de estado (`BLOCKED · Bloqueo 6h`)
- Banner accionable con countdown cuando hay bloqueo macro
- Comparativa vs ayer / snapshot anterior (score, SPY, oro, EURUSD)
- Historial de acontecimientos (cambios de señal) + series GLD / EURUSD
- Noticias multi-fuente con tono (positiva/negativa/mixta/neutra) y apertura en el navegador

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
- `GET /api/health` — healthcheck

Requisitos: macOS 14+, Swift 5.9+, `.venv` del repo con dependencias NEXUS.
