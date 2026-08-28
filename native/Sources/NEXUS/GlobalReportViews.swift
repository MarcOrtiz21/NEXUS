import SwiftUI

struct GlobalView: View {
    @EnvironmentObject private var store: NexusStore

    var body: some View {
        NexusPage {
            NexusResponsiveGrid(wideColumns: 4, mediumColumns: 2) {
                marketCard("BOLSA", "SPY", "Índice de referencia")
                marketCard("ORO", "GLD", "Activo defensivo")
                fxMarketCard
                metricCard("VOLATILIDAD", number("VIX", decimals: 1), vixHint)
            }
            regionalHeatmap
            NexusResponsiveGrid(wideColumns: 2, mediumColumns: 1) {
                riskCard
                ratesCard
            }
            NexusResponsiveGrid(wideColumns: 2, mediumColumns: 1) {
                liquidityCard
                valuationCard
                correlationCard
            }
            NexusResponsiveGrid(wideColumns: 3, mediumColumns: 1) {
                regimeCard
                anomaliesCard
                dataQualityCard
            }
            assetsCard
        }
    }

    private var regionalKeys: [(title: String, key: String)] {
        [("Europa", "Europa"), ("España (IBEX)", "Espana"), ("Japón", "Japon"), ("China", "China"), ("Asia emergente", "Asia_EM")]
    }

    private var rankedRegions: [(title: String, key: String, asset: AssetMetrics?)] {
        regionalKeys
            .map { ($0.title, $0.key, store.snapshot?.globalMarkets?[$0.key]) }
            .sorted { ($0.2?.momentum1m ?? -.infinity) > ($1.2?.momentum1m ?? -.infinity) }
    }

    private var regionalHeatmap: some View {
        VStack(alignment: .leading, spacing: 8) {
            NexusSectionHeader(title: "Mapa regional", help: "Comparación homogénea de proxies. España usa EWP como aproximación al IBEX.")
            ForEach(Array(rankedRegions.enumerated()), id: \.offset) { index, row in
                HStack(spacing: 10) {
                    Text("\(index + 1)")
                        .font(.caption.monospacedDigit().weight(.bold))
                        .frame(width: 18)
                    Text(row.title)
                        .font(.caption.weight(.semibold))
                        .frame(minWidth: 110, alignment: .leading)
                    NexusMiniSparkline(points: sparkline(for: regionTicker(row.key)), width: 72, height: 28)
                    NexusScoreBar(value: regionScore(row.asset), showValue: true)
                    Text("1M \(formatPct(row.asset?.momentum1m))")
                        .font(.caption2.monospacedDigit())
                        .frame(width: 90, alignment: .trailing)
                    Text(trend(row.asset))
                        .font(.caption2)
                        .foregroundStyle(NexusTheme.toneColor(trend(row.asset)))
                    Text("Vol \(formatPct(row.asset?.volatility20d))")
                        .font(.caption2)
                        .foregroundStyle(NexusTheme.muted)
                        .frame(width: 90, alignment: .trailing)
                }
                if row.asset?.price == nil {
                    NexusMissingSource(title: "\(row.title) sin dato", detail: row.key == "Espana" ? "Proxy IBEX (EWP) pendiente de actualización." : "Serie regional pendiente de actualización.")
                }
                Divider().opacity(0.10)
            }
        }
        .nexusCard()
    }

    private func regionScore(_ asset: AssetMetrics?) -> Double? {
        guard let asset, asset.price != nil else { return nil }
        var score = 50.0
        if let mom = asset.momentum1m { score += mom > 0 ? 15 : -15 }
        if let mom3 = asset.momentum3m { score += mom3 > 0 ? 10 : -10 }
        if let price = asset.price, let ma50 = asset.ma50 {
            score += price >= ma50 ? 15 : -15
        }
        return min(100, max(0, score))
    }

    private func marketCard(_ title: String, _ ticker: String, _ hint: String) -> some View {
        let asset = store.snapshot?.assets?[ticker]
        return NexusSummaryMetricCard(
            title: title,
            value: price(asset?.price),
            hint: asset?.price == nil ? "Sin dato: actualiza la fuente de mercado" : "\(hint) · 1M \(formatPct(asset?.momentum1m))",
            tone: (asset?.momentum1m ?? 0) >= 0 ? NexusTheme.good : NexusTheme.bad
        )
    }

    private var fxMarketCard: some View {
        let asset = usdEurMetrics
        return NexusSummaryMetricCard(
            title: "USD/EUR",
            value: asset?.price.map { String(format: "%.5f", $0) } ?? "—",
            hint: asset?.price == nil ? "Sin dato: actualiza EUR/USD" : "Fuerza bilateral del dólar · 1M \(formatPct(asset?.momentum1m))",
            tone: (asset?.momentum1m ?? 0) >= 0 ? NexusTheme.good : NexusTheme.bad
        )
    }

    private var usdEurMetrics: AssetMetrics? {
        guard let eur = store.snapshot?.forex?.EURUSD else { return nil }
        return AssetMetrics(
            price: inverse(eur.price),
            ma20: inverse(eur.ma20),
            ma50: inverse(eur.ma50),
            ma200: inverse(eur.ma200),
            momentum1m: inverseReturn(eur.momentum1m),
            momentum3m: inverseReturn(eur.momentum3m),
            volatility20d: eur.volatility20d
        )
    }

    private func metricCard(_ title: String, _ value: String, _ hint: String) -> some View {
        NexusSummaryMetricCard(title: title, value: value, hint: hint, tone: vixTone)
    }

    private var riskCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            NexusSectionHeader(title: "TERMÓMETRO DE RIESGO", help: "Combina volatilidad, tendencia del mercado y acción operativa.")
            NexusScoreBar(value: Double(store.snapshot?.decision?.score ?? 0))
            NexusKVRow(label: "VIX", value: number("VIX", decimals: 1), tone: vixTone)
            NexusKVRow(label: "Acción", value: store.snapshot?.decision?.operationalAction ?? "—", tone: NexusTheme.toneColor(store.snapshot?.decision?.operationalAction))
            NexusKVRow(label: "Confianza", value: store.snapshot?.decision?.confidence ?? "—")
        }
        .nexusCard()
        .frame(maxWidth: .infinity, alignment: .topLeading)
    }

    private var ratesCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            NexusSectionHeader(title: "TIPOS E INFLACIÓN", help: "Factores macro que suelen condicionar la valoración y el dólar.")
            NexusKVRow(label: "Bono EE. UU. 10Y", value: number("US10Y", suffix: "%", decimals: 2))
            NexusKVRow(label: "Inflación", value: number("CPI_YoY_Pct", suffix: "%", decimals: 1))
            NexusKVRow(label: "Curva 10Y–2Y", value: number("Yield_Curve_Spread", suffix: " pp", decimals: 2))
            Text("Revisa estos factores junto con la tendencia: no constituyen una señal de compra aislada.")
                .font(.caption)
                .foregroundStyle(NexusTheme.muted)
        }
        .nexusCard()
        .frame(maxWidth: .infinity, alignment: .topLeading)
    }

    private var assetsCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            NexusSectionHeader(title: "ACTIVOS CLAVE", detail: "precio, momentum y volatilidad")
            ForEach(["SPY", "GLD", "USDEUR", "EURUSD"], id: \.self) { ticker in
                let asset = ticker == "USDEUR"
                    ? usdEurMetrics
                    : (store.snapshot?.assets?[ticker] ?? (ticker == "EURUSD" ? store.snapshot?.forex?.EURUSD : nil))
                assetRow(ticker: ticker, asset: asset)
                Divider().opacity(0.12)
            }
        }
        .nexusCard()
    }

    private func assetRow(ticker: String, asset: AssetMetrics?) -> some View {
        ViewThatFits(in: .horizontal) {
            HStack {
                Text(ticker).frame(width: 62, alignment: .leading)
                NexusMiniSparkline(points: sparkline(for: ticker), width: 72, height: 26)
                Text(assetPrice(ticker, asset?.price)).frame(width: 78, alignment: .trailing)
                Text("1M \(formatPct(asset?.momentum1m))").frame(width: 86, alignment: .trailing)
                Text("Vol \(formatPct(asset?.volatility20d))").frame(width: 86, alignment: .trailing)
                Spacer()
                Text(trend(asset)).foregroundStyle(NexusTheme.toneColor(trend(asset)))
            }
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(ticker).fontWeight(.semibold)
                    Text(assetPrice(ticker, asset?.price)).foregroundStyle(NexusTheme.muted)
                }
                Spacer()
                VStack(alignment: .trailing, spacing: 2) {
                    Text("1M \(formatPct(asset?.momentum1m))")
                    Text(trend(asset)).foregroundStyle(NexusTheme.toneColor(trend(asset)))
                }
            }
        }
        .font(.caption)
    }

    private func regionCard(title: String, key: String) -> some View {
        let asset = store.snapshot?.globalMarkets?[key]
        return NexusSummaryMetricCard(
            title: title,
            value: price(asset?.price),
                            hint: asset?.price == nil
                                ? (key == "Espana" ? "Proxy IBEX (EWP) pendiente de actualización" : "Serie regional pendiente de actualización")
                                : (key == "Espana"
                                   ? "Proxy IBEX (EWP) · 1M \(formatPct(asset?.momentum1m))"
                                   : "1M \(formatPct(asset?.momentum1m)) · 3M \(formatPct(asset?.momentum3m))"),
            tone: (asset?.momentum1m ?? 0) >= 0 ? NexusTheme.good : NexusTheme.bad
        )
    }

    private var liquidityCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            NexusSectionHeader(title: "LIQUIDEZ")
            NexusKVRow(label: "M2 EE. UU.", value: number("M2_Change_Pct", suffix: "%", decimals: 1))
            NexusKVRow(label: "M2 China", value: number("China_M2_YoY_Pct", suffix: "%", decimals: 1))
            if let asOf = store.snapshot?.intelligence?.dataQuality?.observations?["M2_Change_Pct"] {
                Text("Observación FRED \(asOf). No es la hora de captura de NEXUS.")
                    .font(.caption2).foregroundStyle(NexusTheme.muted)
            } else {
                Text("La liquidez es un contexto macro, no una orden aislada.")
                    .font(.caption2).foregroundStyle(NexusTheme.muted)
            }
        }
        .nexusCard()
        .frame(maxWidth: .infinity, alignment: .topLeading)
    }

    private var valuationCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            NexusSectionHeader(title: "VALORACIÓN USA")
            NexusKVRow(label: "PER forward", value: number("PE_Forward", decimals: 1))
            NexusKVRow(label: "Percentil", value: number("PE_Forward_Percentile", suffix: "%", decimals: 0))
            NexusKVRow(label: "PER trailing", value: number("PE_Trailing", decimals: 1))
        }
        .nexusCard()
        .frame(maxWidth: .infinity, alignment: .topLeading)
    }

    private var correlationCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            NexusSectionHeader(title: "CONCENTRACIÓN")
            Text(number("Correlation_Proxy", decimals: 2))
                .font(.title2.monospacedDigit().weight(.bold))
            Text("Correlación sectorial: alta implica menor diversificación efectiva.")
                .font(.caption).foregroundStyle(NexusTheme.muted)
            NexusKVRow(label: "VIX vs MA20", value: vixVsMA20)
        }
        .nexusCard()
        .frame(maxWidth: .infinity, alignment: .topLeading)
    }

    private var regimeCard: some View {
        let regime = store.snapshot?.intelligence?.regime
        return NexusSummaryMetricCard(
            title: "RÉGIMEN",
            value: regime?.label ?? "Sin datos",
            hint: regime?.summary ?? "Contexto de mercado",
            tone: NexusTheme.toneColor(regime?.tone)
        )
    }

    private var anomaliesCard: some View {
        let anomalies = store.snapshot?.intelligence?.anomalies ?? []
        return VStack(alignment: .leading, spacing: 6) {
            NexusSectionHeader(title: "ANOMALÍAS", detail: "\(anomalies.count)")
            Text(anomalies.first?.title ?? "Sin lecturas extremas detectadas.")
                .font(.subheadline.weight(.semibold))
            Text("Avisos descriptivos; confirmar antes de actuar.")
                .font(.caption2).foregroundStyle(NexusTheme.muted)
        }
        .nexusCard()
        .frame(maxWidth: .infinity, alignment: .topLeading)
    }

    private var dataQualityCard: some View {
        let quality = store.snapshot?.intelligence?.dataQuality
        let obs = quality?.observations?["CPI_YoY_Pct"]
        let hint: String
        if (quality?.unhealthy ?? 0) != 0 {
            hint = "\(quality?.unhealthy ?? 0) incidencias: \(quality?.critical?.first ?? "revisar")"
        } else if let obs {
            hint = "IPC observación \(obs)"
        } else {
            hint = "sin incidencias detectadas"
        }
        return NexusSummaryMetricCard(
            title: "CALIDAD DE DATOS",
            value: "\(quality?.total ?? 0) fuentes",
            hint: hint,
            tone: (quality?.unhealthy ?? 0) == 0 ? NexusTheme.good : NexusTheme.warn
        )
    }

    private func number(_ key: String, suffix: String = "", decimals: Int) -> String {
        guard let value = store.snapshot?.market?[key]?.value else { return "No disponible" }
        return String(format: "%.\(decimals)f%@", value, suffix)
    }

    private func price(_ value: Double?) -> String {
        guard let value else { return "No disponible" }
        return String(format: value < 10 ? "%.4f" : "%.2f", value)
    }

    private func assetPrice(_ ticker: String, _ value: Double?) -> String {
        guard let value else { return "No disponible" }
        return ticker == "USDEUR" || ticker == "EURUSD"
            ? String(format: "%.5f", value)
            : price(value)
    }

    private func inverse(_ value: Double?) -> Double? {
        guard let value, value != 0 else { return nil }
        return 1 / value
    }

    private func inverseReturn(_ percent: Double?) -> Double? {
        guard let percent else { return nil }
        let factor = 1 + percent / 100
        guard factor > 0 else { return nil }
        return (1 / factor - 1) * 100
    }

    private func regionTicker(_ key: String) -> String {
        switch key {
        case "Europa": return "FEZ"
        case "Espana": return "EWP"
        case "Japon": return "EWJ"
        case "China": return "FXI"
        case "Asia_EM": return "AAXJ"
        default: return key
        }
    }

    private func sparkline(for ticker: String) -> [SparklinePoint] {
        store.snapshot?.sparklines?[ticker]
            ?? store.snapshot?.sparklines?["^\(ticker)"]
            ?? []
    }

    private func trend(_ asset: AssetMetrics?) -> String {
        guard let asset, let price = asset.price, let ma50 = asset.ma50 else { return "Sin tendencia" }
        return price >= ma50 ? "Sobre MA50" : "Bajo MA50"
    }

    private var vixTone: Color {
        guard let vix = store.snapshot?.market?["VIX"]?.value else { return NexusTheme.muted }
        return vix >= 25 ? NexusTheme.bad : vix >= 18 ? NexusTheme.warn : NexusTheme.good
    }

    private var vixHint: String {
        guard let vix = store.snapshot?.market?["VIX"]?.value else { return "sin lectura disponible" }
        return vix >= 25 ? "estrés elevado" : vix >= 18 ? "precaución" : "riesgo contenido"
    }

    private var vixVsMA20: String {
        guard let vix = store.snapshot?.market?["VIX"]?.value,
              let ma = store.snapshot?.market?["VIX_MA20"]?.value, ma != 0 else { return "—" }
        return formatPct((vix / ma - 1) * 100)
    }
}

struct ReportView: View {
    @EnvironmentObject private var store: NexusStore

    var body: some View {
        NexusPage {
            decisionCard
            NexusResponsiveGrid(wideColumns: 3, mediumColumns: 1) {
                VStack(alignment: .leading, spacing: 8) {
                    NexusSectionHeader(title: "Diagnóstico actual")
                    Text(store.snapshot?.decision?.operationalAction ?? "Sin decisión")
                        .font(.title3.weight(.bold))
                        .foregroundStyle(NexusTheme.toneColor(store.snapshot?.decision?.operationalAction))
                    Text(store.snapshot?.decision?.rationale ?? "Actualiza para generar una lectura razonada.")
                        .font(.caption)
                        .foregroundStyle(NexusTheme.muted)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .nexusCard()
                .frame(maxWidth: .infinity, alignment: .topLeading)
                VStack(alignment: .leading, spacing: 8) {
                    NexusSectionHeader(title: "Riesgos")
                    NexusKVRow(label: "VIX", value: GlobalViewRiskLabel(vix: store.snapshot?.market?["VIX"]?.value), tone: NexusTheme.toneColor(store.snapshot?.status))
                    NexusKVRow(label: "Bloqueo", value: store.snapshot?.calendar?.shouldBlock == true ? "Activo" : "Libre")
                    NexusKVRow(label: "Noticias", value: store.snapshot?.news?.sentiment?.dominant ?? "—")
                    Text("Un bloqueo o VIX elevado anula entradas aunque el score técnico sea alto.")
                        .font(.caption2)
                        .foregroundStyle(NexusTheme.muted)
                }
                .nexusCard()
                .frame(maxWidth: .infinity, alignment: .topLeading)
            }
            scoreBreakdownCard
            changesCard
            VStack(alignment: .leading, spacing: 8) {
                NexusSectionHeader(title: "Próximas condiciones de reevaluación")
                Text(reevalCondition)
                    .font(.subheadline)
                    .fixedSize(horizontal: false, vertical: true)
                Text("Datos \(relativeAge(from: store.snapshot?.capturedAtUtc))")
                    .font(.caption)
                    .foregroundStyle(NexusTheme.muted)
            }
            .nexusCard()
        }
    }

    private var reevalCondition: String {
        let next = store.snapshot?.calendar?.nextEvent?.title
        if store.snapshot?.calendar?.shouldBlock == true {
            return "Reevaluar cuando expire el bloqueo\(next.map { " y se publique \($0)" } ?? "")."
        }
        return "Una variación material del score, del VIX o del liderazgo de activos activaría una nueva decisión."
    }

    private var decisionCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            NexusSectionHeader(title: "DECISIÓN DE LA ÚLTIMA EVALUACIÓN", detail: relativeAge(from: store.snapshot?.capturedAtUtc))
            Text(store.snapshot?.decision?.operationalAction ?? store.snapshot?.decision?.action ?? "Sin decisión")
                .font(.system(size: 34, weight: .bold, design: .rounded))
                .foregroundStyle(NexusTheme.toneColor(store.snapshot?.decision?.operationalAction ?? store.snapshot?.decision?.action))
            Text(store.snapshot?.decision?.rationale ?? "Actualiza para generar una lectura razonada.")
                .font(.subheadline)
                .foregroundStyle(NexusTheme.muted)
                .fixedSize(horizontal: false, vertical: true)
        }
        .nexusCard()
    }

    private var prioritiesCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            NexusSectionHeader(title: "ACTIVOS A PRIORIZAR")
            ForEach(store.snapshot?.decision?.favoredAssets ?? [], id: \.self) { asset in
                HStack {
                    Image(systemName: "checkmark.circle.fill").foregroundStyle(NexusTheme.good)
                    Text(asset).fontWeight(.semibold)
                    Spacer()
                    NexusActionButton(title: "Ver ficha", systemImage: "sidebar.trailing") {
                        store.showAsset(asset)
                    }
                }
                Divider().opacity(0.12)
            }
            if (store.snapshot?.decision?.favoredAssets ?? []).isEmpty {
                Text("No hay activos priorizados en esta evaluación.").foregroundStyle(NexusTheme.muted)
            }
        }
        .nexusCard()
    }

    private var changesCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            NexusSectionHeader(title: "CAMBIOS DESDE LA LECTURA ANTERIOR")
            if let changes = store.snapshot?.changeAttribution?.topAssetMovers, !changes.isEmpty {
                ForEach(changes.prefix(5), id: \.ticker) { item in
                    NexusKVRow(label: item.label ?? item.ticker ?? "Activo", value: "score \(formatDelta(item.scoreDelta))", tone: (item.scoreDelta ?? 0) >= 0 ? NexusTheme.good : NexusTheme.bad)
                }
            } else {
                Text("Aún no hay una comparación anterior persistida.").foregroundStyle(NexusTheme.muted)
            }
        }
        .nexusCard()
    }

    private var scoreBreakdownCard: some View {
        let drivers = store.snapshot?.sessionPlan?.scoreDrivers ?? []
        return VStack(alignment: .leading, spacing: 6) {
            NexusSectionHeader(title: "FACTORES DEL SCORE", detail: "mismos que en Resumen")
            if drivers.isEmpty {
                Text("Los factores aparecerán junto a «Qué hacer ahora» en Resumen.")
                    .font(.caption)
                    .foregroundStyle(NexusTheme.muted)
            } else {
                ForEach(drivers.prefix(6)) { item in
                    HStack(alignment: .top) {
                        Text(item.factor ?? "Factor").font(.caption.weight(.semibold)).frame(width: 110, alignment: .leading)
                        Text(item.detail ?? "—").font(.caption).foregroundStyle(NexusTheme.muted)
                    }
                }
            }
            Text("Son las reglas que movieron el score. La confianza baja si el dato está caducado.")
                .font(.caption2).foregroundStyle(NexusTheme.muted)
        }
        .nexusCard()
    }
}

struct ReportOverviewContent: View {
    @EnvironmentObject private var store: NexusStore

    var body: some View {
        NexusResponsiveGrid(wideColumns: 3, mediumColumns: 3) {
            newsPulseCard
            dataQualityCard
            sessionDigestCard
            risksCard
            changesCard
            reevaluationCard
        }
    }

    private var newsPulseCard: some View {
        let news = store.snapshot?.news
        let sentiment = news?.sentiment
        return VStack(alignment: .leading, spacing: 6) {
            NexusSectionHeader(title: "Pulso de noticias")
            HStack(alignment: .firstTextBaseline) {
                Text(sentiment?.dominant ?? "Neutral")
                    .font(.headline.weight(.bold))
                    .foregroundStyle(NexusTheme.toneColor(sentiment?.dominant))
                Spacer()
                Text("\(news?.count ?? 0) titulares")
                    .font(.caption2.monospacedDigit().weight(.semibold))
                    .foregroundStyle(NexusTheme.muted)
            }
            if let details = sentiment?.details, !details.isEmpty {
                Text(details)
                    .font(.caption2)
                    .foregroundStyle(NexusTheme.muted)
                    .lineLimit(2)
            }
            if let narrative = news?.narratives?.narratives?.first {
                HStack(spacing: 6) {
                    Circle()
                        .fill(NexusTheme.toneColor(narrative.dominantTone))
                        .frame(width: 6, height: 6)
                    Text(narrative.topic ?? "Tema")
                        .font(.caption2.weight(.semibold))
                    Spacer()
                    Text("\(narrative.headlineCount ?? 0)")
                        .font(.caption2.monospacedDigit())
                        .foregroundStyle(NexusTheme.muted)
                }
            }
        }
        .frame(maxWidth: .infinity, minHeight: 96, alignment: .topLeading)
        .nexusCard()
        .contentShape(Rectangle())
        .onTapGesture { store.selected = .news }
        .help("Abrir noticias")
    }

    private var dataQualityCard: some View {
        VStack(alignment: .leading, spacing: 6) {
            NexusSectionHeader(
                title: "Calidad de datos",
                help: "Frescura por capa: mercado (Yahoo), macro (FRED/PER) y empresas."
            )
            Text(freshnessShort)
                .font(.headline.weight(.bold))
                .foregroundStyle(NexusTheme.toneColor(store.snapshot?.freshness?.tone))
            Text(store.snapshot?.freshness?.headline ?? store.engineStatus)
                .font(.caption2)
                .foregroundStyle(NexusTheme.muted)
                .lineLimit(2)
        }
        .frame(maxWidth: .infinity, minHeight: 96, alignment: .topLeading)
        .nexusCard()
    }

    private var sessionDigestCard: some View {
        let digest = store.snapshot?.sessionDigest
        return VStack(alignment: .leading, spacing: 8) {
            NexusSectionHeader(
                title: "Cambios de sesión",
                help: "Resume variaciones de score, VIX y cruces de rotación frente a la evaluación anterior."
            )
            Text(digest?.headline ?? "Sin comparación todavía")
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(digest?.hasPrior == true ? NexusTheme.text : NexusTheme.muted)
                .lineLimit(2)
            if digest?.hasPrior == true {
                HStack(spacing: 14) {
                    digestMetric("Score", digest?.score?.delta)
                    digestMetric("VIX", digest?.vix?.delta)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Acción")
                            .font(.caption2)
                            .foregroundStyle(NexusTheme.muted)
                        Text(digest?.action?.label ?? digest?.action?.to ?? "Sin cambio")
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(digest?.action?.changed == true ? NexusTheme.warn : NexusTheme.text)
                            .lineLimit(1)
                    }
                }
                if let crossing = digest?.rotationCrossings?.first {
                    HStack(spacing: 6) {
                        Image(systemName: "arrow.triangle.swap")
                            .font(.caption2)
                            .foregroundStyle(NexusTheme.accent)
                        Text(crossing.theme ?? crossing.ticker ?? "Tema")
                            .font(.caption.weight(.semibold))
                            .lineLimit(1)
                        Spacer(minLength: 4)
                        Text("\(crossing.fromLabel ?? "—") → \(crossing.toLabel ?? "—")")
                            .font(.caption2)
                            .foregroundStyle(NexusTheme.muted)
                            .lineLimit(1)
                    }
                }
            } else {
                Text(digest?.summary ?? "Se completará tras disponer de una evaluación anterior.")
                    .font(.caption2)
                    .foregroundStyle(NexusTheme.muted)
                    .lineLimit(2)
            }
        }
        .frame(maxWidth: .infinity, minHeight: 96, alignment: .topLeading)
        .nexusCard()
    }

    private func digestMetric(_ label: String, _ delta: Double?) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(LocalizedStringKey(label))
                .font(.caption2)
                .foregroundStyle(NexusTheme.muted)
            Text(delta.map { String(format: "%+.1f", $0) } ?? "—")
                .font(.caption.monospacedDigit().weight(.bold))
                .foregroundStyle((delta ?? 0) > 0 ? NexusTheme.good : (delta ?? 0) < 0 ? NexusTheme.bad : NexusTheme.text)
        }
    }

    private var risksCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            NexusSectionHeader(title: "Riesgos")
            NexusKVRow(label: "VIX", value: GlobalViewRiskLabel(vix: store.snapshot?.market?["VIX"]?.value))
            NexusKVRow(label: "Bloqueo", value: store.snapshot?.calendar?.shouldBlock == true ? "Activo" : "Libre")
            NexusKVRow(label: "Noticias", value: store.snapshot?.news?.sentiment?.dominant ?? "—")
            Text("El bloqueo y el VIX prevalecen sobre la fuerza técnica.")
                .font(.caption2)
                .foregroundStyle(NexusTheme.muted)
        }
        .frame(maxWidth: .infinity, minHeight: 96, alignment: .topLeading)
        .nexusCard()
    }

    private var changesCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            NexusSectionHeader(title: "Cambios por activo")
            let changes = store.snapshot?.changeAttribution?.topAssetMovers ?? []
            ForEach(changes.prefix(4), id: \.ticker) { item in
                NexusKVRow(
                    label: item.label ?? item.ticker ?? "Activo",
                    value: "score \(formatDelta(item.scoreDelta))",
                    tone: (item.scoreDelta ?? 0) >= 0 ? NexusTheme.good : NexusTheme.bad
                )
            }
            if changes.isEmpty {
                Text("Aún no hay comparación anterior persistida.")
                    .font(.caption)
                    .foregroundStyle(NexusTheme.muted)
            }
        }
        .frame(maxWidth: .infinity, minHeight: 96, alignment: .topLeading)
        .nexusCard()
    }

    private var reevaluationCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            NexusSectionHeader(title: "Próxima reevaluación")
            Text(reevaluationText)
                .font(.subheadline.weight(.semibold))
                .fixedSize(horizontal: false, vertical: true)
            Text("Datos \(relativeAge(from: store.snapshot?.capturedAtUtc))")
                .font(.caption2)
                .foregroundStyle(NexusTheme.muted)
        }
        .frame(maxWidth: .infinity, minHeight: 96, alignment: .topLeading)
        .nexusCard()
    }

    private var freshnessShort: String {
        let statuses = (store.snapshot?.freshness?.layers ?? []).compactMap(\.status)
        if statuses.contains(where: { $0 == "MISSING" || $0 == "ERROR" }) { return "Huecos" }
        if statuses.contains("STALE") { return "Caducado" }
        if statuses.contains("OK") { return "Al día" }
        return relativeAge(from: store.snapshot?.capturedAtUtc)
    }

    private var reevaluationText: String {
        let next = store.snapshot?.calendar?.nextEvent?.title
        if store.snapshot?.calendar?.shouldBlock == true {
            return "Reevaluar cuando expire el bloqueo\(next.map { " y se publique \($0)" } ?? "")."
        }
        return "Un cambio material del score, VIX o liderazgo activará una nueva decisión."
    }
}

private func GlobalViewRiskLabel(vix: Double?) -> String {
    guard let vix else { return "Sin datos" }
    if vix >= 25 { return "Alto" }
    if vix >= 18 { return "Medio" }
    return "Contenido"
}
