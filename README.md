<div align="center">
  <img src="assets/AppIcon.png" alt="NEXUS logo" width="144">
  <h1>NEXUS Workstation</h1>
  <p><strong>Market intelligence for disciplined decisions.</strong></p>
  <p>Workstation 3.5 · Native macOS interface · Python decision engine · Explainable market context</p>
  <p>
    <img alt="macOS 14+" src="https://img.shields.io/badge/macOS-14%2B-111111?logo=apple">
    <img alt="Swift 5.9+" src="https://img.shields.io/badge/Swift-5.9%2B-F05138?logo=swift&logoColor=white">
    <img alt="Python 3.11+" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
    <img alt="Release 3.5" src="https://img.shields.io/badge/release-3.5-0A84FF">
  </p>
</div>

<p align="center">
  <a href="#características">Características</a> ·
  <a href="#arquitectura">Arquitectura</a> ·
  <a href="#inicio-rápido">Inicio rápido</a> ·
  <a href="#desarrollo-y-pruebas">Pruebas</a>
</p>

## Sobre NEXUS

NEXUS es una workstation de análisis de mercado que combina ingestión de datos, filtros de riesgo, análisis técnico y macroeconómico, noticias y un motor de decisión explicable.

La aplicación está diseñada para responder tres preguntas:

1. ¿Qué contexto de mercado estamos observando?
2. ¿Qué factores están impulsando la lectura?
3. ¿Qué acción operativa es razonable y qué debería evitarse?

NEXUS no ejecuta operaciones reales ni sustituye asesoramiento financiero. Las señales, escenarios y simulaciones son herramientas de análisis.

### Novedades de la versión 3.5

- Interfaz nativa bilingüe en español e inglés.
- Resumen ejecutivo más compacto, con plan por activo, ranking técnico y contexto macro.
- Terminal de tres gráficos configurable: foco principal y dos paneles laterales.
- Configuraciones propias persistentes para paneles, intervalo y rango.
- Gráficos de divisas ampliados, USD/EUR invertido con precisión y oro COMEX.
- RSI con divergencias alcistas/bajistas, MACD y cursor sincronizado durante el arrastre.
- Navegación sectorial por temas y empresas, con inspector técnico lateral.

## Características

### Interfaz nativa macOS

- Aplicación SwiftUI para macOS 14+.
- Navegación adaptativa para ventanas pequeñas y pantalla completa.
- Tema oscuro, tarjetas consistentes y controles compactos.
- Inspector de activos con score, tendencia, momentum y volatilidad.
- Lector interno de noticias con filtros de tono.
- Cambio de idioma en caliente entre español e inglés.

### Modos de análisis

- **Resumen**: decisión operativa, ranking, pulso macro y asignación.
- **Noticias**: fuentes, sentimiento, narrativas por tema y lectura contextual.
- **Historial**: cambios de decisión, score, precios y atribución entre snapshots.
- **Forex y oro**: USD/EUR, EUR/USD, principales cruces, oro, momentum y catalizadores.
- **Rotación sectorial**: líderes, receptores de flujo, sectores neutrales y débiles.
- **Gráficos**: terminal 2/3–1/3 configurable, velas a demanda, RSI/MACD, divergencias y cursor compartido.
- **Cartera virtual**: simulación, comparación con SPY, drawdown, concentración y escenarios.
- **Global**: regiones, VIX, tipos, liquidez, valoración y calidad de datos.

### Inteligencia y calidad

- Clasificación descriptiva del régimen: expansión, transición, cautela o estrés.
- Anomalías de volatilidad, curva de tipos y momentum.
- Factores estructurados detrás de la decisión.
- Estado y calidad de las fuentes de datos.
- Hash de auditoría por snapshot.
- Track record histórico y resultados agrupados por señal operativa.

## Arquitectura

```mermaid
flowchart TB
    subgraph sources["Fuentes externas"]
        YF["Yahoo Finance<br/>precios y OHLCV"]
        FRED["FRED / macro<br/>tipos e inflación"]
        RSS["RSS y proveedores<br/>noticias y calendario"]
    end

    subgraph data["Capa de datos"]
        ING["Data ingestion<br/>normalización y aliases"]
        CACHE[("Caché atómica<br/>rápida + lenta")]
        QUALITY["DataQuality<br/>frescura y procedencia"]
        SERIES["Chart series<br/>rangos e indicadores"]
    end

    subgraph intelligence["Inteligencia y control de riesgo"]
        LOGIC["LogicEngine<br/>estado de mercado"]
        RISK{"Filtros operativos<br/>VIX · calendario · sentimiento"}
        ROTATION["RotationEngine<br/>temas y empresas"]
        NEWS["News intelligence<br/>tono y narrativas"]
        DECISION["DecisionEngine<br/>score · acción · asignación"]
        EXPLAIN["Decision intelligence<br/>régimen · anomalías · auditoría"]
    end

    subgraph persistence["Persistencia"]
        HISTORY[("Snapshots e historial")]
        PAPER["Paper trading<br/>y track record"]
        SETTINGS[("Preferencias<br/>y watchlist")]
    end

    subgraph delivery["Entrega local"]
        API["FastAPI local<br/>/api/native · /chart"]
        UI["SwiftUI Workstation 3.5"]
        VIEWS["Resumen · Forex · Rotación<br/>Gráficos · Global · Historial"]
    end

    YF --> ING
    FRED --> ING
    RSS --> ING
    ING --> CACHE --> QUALITY
    CACHE --> SERIES
    QUALITY --> LOGIC
    QUALITY --> ROTATION
    QUALITY --> NEWS
    LOGIC --> RISK
    NEWS --> RISK
    ROTATION --> DECISION
    RISK --> DECISION
    DECISION --> EXPLAIN
    DECISION --> HISTORY --> PAPER
    SERIES --> API
    NEWS --> API
    ROTATION --> API
    EXPLAIN --> API
    HISTORY --> API
    PAPER --> API
    SETTINGS <--> API
    API --> UI --> VIEWS

    classDef source fill:#18202b,stroke:#5e81ac,color:#fff;
    classDef engine fill:#202a22,stroke:#4caf70,color:#fff;
    classDef gate fill:#30251c,stroke:#ff9f0a,color:#fff;
    classDef app fill:#14273b,stroke:#0a84ff,color:#fff;
    class YF,FRED,RSS source;
    class LOGIC,ROTATION,NEWS,DECISION,EXPLAIN engine;
    class RISK gate;
    class API,UI,VIEWS app;
```

### Flujo de una evaluación

1. La ingesta recupera precios, macro, divisas, calendario y noticias, usando caché cuando corresponde.
2. La capa de calidad etiqueta frescura, procedencia y huecos antes de evaluar.
3. Los motores de mercado, rotación y noticias generan señales independientes.
4. VIX, calendario y sentimiento actúan como compuertas de riesgo; pueden bloquear una señal técnica.
5. `DecisionEngine` combina contexto, score y bloqueos para producir acción y asignación.
6. La evaluación se explica, audita y persiste junto con historial y paper trading.
7. FastAPI publica un snapshot estable y series OHLCV; SwiftUI solo representa ese contrato.

## Inicio rápido

### Requisitos

- macOS 14 o superior.
- Python 3.11+ recomendado.
- Swift 5.9+.
- Dependencias Python del proyecto.
- Opcional: `FRED_API_KEY` para datos macro adicionales.

### Preparar el entorno

```bash
git clone https://github.com/MarcOrtiz21/NEXUS.git
cd NEXUS
./setup.command
```

Si ya existe el entorno virtual:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install pytest
```

### Ejecutar la aplicación nativa

La forma recomendada en macOS es:

```bash
./scripts/run_native.command
```

También puede construirse e instalarse en Aplicaciones:

```bash
./scripts/install_mac_app.sh
open "/Applications/NEXUS Workstation.app"
```

## API nativa

El backend local se sirve en `http://127.0.0.1:8765`.

| Endpoint | Uso |
| --- | --- |
| `GET /api/native` | Snapshot completo para SwiftUI |
| `GET /api/native/refresh` | Actualiza y persiste un snapshot |
| `GET /api/native/chart/{ticker}` | OHLCV e indicadores por intervalo/rango |
| `POST /api/native/settings` | Guarda preferencias nativas |
| `POST /api/native/watchlist` | Actualiza la lista de seguimiento |
| `GET /api/health` | Estado del backend |

El payload incluye decisión, mercado, activos, noticias, calendario, historial, cartera virtual, track record, inteligencia derivada y auditoría.

## Desarrollo y pruebas

Compilar la interfaz SwiftUI:

```bash
swift build --package-path native
```

Ejecutar toda la suite Python:

```bash
.venv/bin/python -m pytest
```

Las pruebas cubren ingestión/cache, calendario, motor de decisión, historial, noticias, sentimiento, cartera virtual, track record y contrato del API nativo.

## Estructura del proyecto

```text
NEXUS/
├── native/                 # Aplicación SwiftUI y modelos del API
├── risk_filters/           # Calendario, noticias y sentimiento
├── data/                   # Datos locales y snapshots de ejecución
├── tests/                  # Suite de regresión Python
├── assets/                 # Icono y recursos de la aplicación
├── native_api.py           # Contrato FastAPI para la app nativa
├── decision_engine.py      # Score, acción y asignación
├── decision_intelligence.py# Régimen, anomalías y calidad
├── data_ingestion.py      # Mercado, macro, caché y procedencia
├── paper_trading.py       # Simulación de cartera
└── scripts/                # Build, instalación y ejecución
```

## Datos y limitaciones

- Los datos de mercado pueden proceder de caché cuando una fuente no está disponible.
- Las narrativas de noticias son agrupaciones heurísticas y no prueban causalidad.
- Los escenarios de cartera son aproximaciones mecánicas, no predicciones.
- El track record depende del número y frecuencia de snapshots históricos.
- Las claves y credenciales deben permanecer fuera del repositorio.

## Licencia

Uso privado y experimental. Define la licencia de distribución antes de publicar una versión pública.
