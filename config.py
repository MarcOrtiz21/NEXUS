"""
Configuración centralizada de NEXUS (config.py)

Gestiona API keys opcionales y constantes del sistema.
Las claves se leen desde variables de entorno. Si no existen,
los módulos que las necesitan se desactivan con un mensaje informativo.

Para activar FRED (Liquidez M2, IPC):
    1. Regístrate gratis en https://fred.stlouisfed.org/docs/api/api_key.html
    2. Establece la variable de entorno: set FRED_API_KEY=tu_clave

Para activar NewsAPI (titulares de noticias premium):
    1. Regístrate gratis en https://newsapi.org/register
    2. Establece la variable de entorno: set NEWSAPI_KEY=tu_clave
    (Sin esta clave, NEXUS usa RSS gratuitos de CNBC/Reuters como fuente alternativa.)
"""

import os
from pathlib import Path

_BASE_DIR = Path(__file__).parent
_KEYS_DIRS = (_BASE_DIR / "APIKEYS", _BASE_DIR / "apikeys")
DATA_DIR = _BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
HISTORY_DIR = DATA_DIR / "history"


def _load_key(filename: str, env_var: str) -> str | None:
    """Lee una API key desde archivo local (APIKEYS/) o variable de entorno."""
    for keys_dir in _KEYS_DIRS:
        file_path = keys_dir / filename
        if file_path.exists():
            key = file_path.read_text(encoding="utf-8").strip()
            if key:
                return key
    return os.environ.get(env_var)


# ─── API Keys (opcionales) ───
FRED_API_KEY: str | None = _load_key("FRED.txt", "FRED_API_KEY")
NEWSAPI_KEY: str | None = _load_key("NEWSAPI.txt", "NEWSAPI_KEY")

# ─── Constantes del Motor Lógico ───
VIX_PANIC_THRESHOLD = 30       # VIX > 30 = pánico extremo
VIX_ELEVATED_THRESHOLD = 25    # VIX > 25 = elevado
VIX_ACCELERATION_PCT = 0.15    # 15% por encima de la MA = aceleración
CORR_HIGH_THRESHOLD = 0.6      # |corr| > 0.6 = riesgo sistémico
CORR_LOW_THRESHOLD = 0.3       # |corr| < 0.3 = rotación sana
US10Y_DANGER_THRESHOLD = 5.0   # Bono > 5% = riesgo estructural
US10Y_WARNING_THRESHOLD = 4.5  # Bono > 4.5% = presión sobre múltiplos

# ─── Feeds RSS gratuitos de noticias financieras ───
RSS_FEEDS = [
    {
        "name": "CNBC Top News",
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
        "weight": 1.0,
    },
    {
        "name": "Yahoo Finance S&P500",
        "url": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US",
        "weight": 1.0,
    },
    {
        "name": "Yahoo Finance Nasdaq",
        "url": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^IXIC&region=US&lang=en-US",
        "weight": 1.0,
    },
    {
        "name": "Yahoo Finance QQQ",
        "url": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=QQQ&region=US&lang=en-US",
        "weight": 1.0,
    },
    {
        "name": "MarketWatch Top Stories",
        "url": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
        "weight": 0.9,
    },
    {
        "name": "Myfxbook Forex News",
        "url": "https://www.myfxbook.com/rss/latest-forex-news",
        "weight": 0.9,
    },
    {
        "name": "Myfxbook Economic Calendar",
        "url": "https://www.myfxbook.com/rss/forex-economic-calendar-events",
        "weight": 1.0,
    },
]

# ─── Intervalo de refresco en segundos (modo loop) ───
REFRESH_INTERVAL_SECONDS = 300  # 5 minutos

# ─── Calidad/cache/export ───
MARKET_CACHE_FILE = CACHE_DIR / "market_data.json"
MARKET_CACHE_MAX_AGE_SECONDS = 60 * 60 * 6
FAST_MARKET_CACHE_FILE = CACHE_DIR / "fast_market.json"
SLOW_MACRO_CACHE_FILE = CACHE_DIR / "slow_macro.json"
FAST_MARKET_CACHE_TTL_SECONDS = 60 * 5
SLOW_MACRO_CACHE_TTL_SECONDS = 60 * 60 * 6
FRED_CALENDAR_CACHE_FILE = CACHE_DIR / "fred_release_calendar.json"
FRED_CALENDAR_CACHE_TTL_SECONDS = 60 * 60 * 6
FRED_CALENDAR_LOOKAHEAD_DAYS = 14
DECISIONS_HISTORY_JSONL = HISTORY_DIR / "decisions.jsonl"
DECISIONS_HISTORY_CSV = HISTORY_DIR / "decisions.csv"
PAPER_TRADES_JSONL = HISTORY_DIR / "paper_trades.jsonl"
PAPER_PORTFOLIO_JSON = HISTORY_DIR / "paper_portfolio.json"
REPORTS_DIR = DATA_DIR / "reports"

# ─── Calendario y dashboard ───
CALENDAR_RSS_URL = "https://www.myfxbook.com/rss/forex-economic-calendar-events"
CALENDAR_BLOCKS_SIGNALS = True
CALENDAR_BLOCK_HOURS_DEFAULT = 6
CALENDAR_BLOCK_HOURS_STRICT = 3
CALENDAR_BLOCK_HOURS_OPTIONS = (CALENDAR_BLOCK_HOURS_STRICT, CALENDAR_BLOCK_HOURS_DEFAULT)


def _resolve_calendar_block_hours() -> int:
    """Ventana de bloqueo antes de eventos macro. Permitido: 3h (estricto) o 6h (defecto)."""
    raw = os.environ.get("NEXUS_CALENDAR_BLOCK_HOURS", str(CALENDAR_BLOCK_HOURS_DEFAULT))
    try:
        hours = int(float(raw))
    except ValueError:
        return CALENDAR_BLOCK_HOURS_DEFAULT
    if hours in CALENDAR_BLOCK_HOURS_OPTIONS:
        return hours
    return CALENDAR_BLOCK_HOURS_DEFAULT


CALENDAR_BLOCK_HOURS = _resolve_calendar_block_hours()
CALENDAR_US_ONLY_BLOCKING = True
WEB_DASHBOARD_HOST = "127.0.0.1"
WEB_DASHBOARD_PORT = 8765

# ─── Mercados globales (ETFs proxy) ───
GLOBAL_MARKET_TICKERS = {
    "Europa": "FEZ",
    "Japon": "EWJ",
    "China": "FXI",
    "Asia_EM": "AAXJ",
}

# ─── Umbrales adicionales ───
YIELD_CURVE_INVERSION_THRESHOLD = -0.2   # 2Y-10Y spread (%)
PE_PERCENTILE_HIGH = 80
PE_PERCENTILE_LOW = 30
GLOBAL_MARKET_MOMENTUM_STRONG = 4.0
GLOBAL_MARKET_MOMENTUM_WEAK = -4.0
GLOBAL_MARKET_SCORE_WEIGHTS = {
    "Europa": 0.35,
    "China": 0.35,
    "Japon": 0.15,
    "Asia_EM": 0.15,
}
CHINA_M2_EXPANSION_THRESHOLD = 8.0
CHINA_M2_CONTRACTION_THRESHOLD = 4.0

# ─── Acciones (etiquetas UX vs canónicas para historial/tests) ───
ACTION_ESPERAR = "ESPERAR / NO ABRIR"
ACTION_MANTENER = "MANTENER POSICIONES"
ACTION_DISPLAY_ALIASES: dict[str, str] = {
    ACTION_ESPERAR: "ESPERAR",
    ACTION_MANTENER: "MANTENER",
}


def normalize_action(action: str | None) -> str:
    """Mapea etiquetas UX a acciones canónicas para comparación y track record."""
    if not action:
        return "DESCONOCIDO"
    return ACTION_DISPLAY_ALIASES.get(action, action)
