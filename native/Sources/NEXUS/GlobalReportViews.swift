import SwiftUI

struct GlobalView: View {
    @EnvironmentObject private var store: NexusStore

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: NexusLayout.spacing) {
                NexusAdaptiveGrid(minimumWidth: 220) {
                    marketCard("BOLSA", "SPY", "Índice de referencia")
                    marketCard("ORO", "GLD", "Activo defensivo")
                    marketCard("DÓLAR", "UUP", "Fuerza del dólar")
                    metricCard("VOLATILIDAD", number("VIX", decimals: 1), vixHint)
                }
                NexusAdaptiveGrid(minimumWidth: 300) {
                    riskCard
                    ratesCard
                }
                NexusAdaptiveGrid(minimumWidth: 190) {
                    regionCard(title: "Europa", key: "Europa")
                    regionCard(title: "Japón", key: "Japon")
                    regionCard(title: "China", key: "China")
                    regionCard(title: "Asia emergente", key: "Asia_EM")
                }
                NexusAdaptiveGrid(minimumWidth: 250) {
                    liquidityCard
                    valuationCard
                    correlationCard
                }
                NexusAdaptiveGrid(minimumWidth: 220) {
                    regimeCard
                    anomaliesCard
                    dataQualityCard
                }
                assetsCard
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(20)
        }
        .scrollBounceBehavior(.basedOnSize)
    }

    private func marketCard(_ title: String, _ ticker: String, _ hint: String) -> some View {
        let asset = store.snapshot?.assets?[ticker]
        return NexusSummaryMetricCard(
            title: title,
            value: price(asset?.price),
            hint: "\(hint) · 1M \(formatPct(asset?.momentum1m))",
            tone: (asset?.momentum1m ?? 0) >= 0 ? NexusTheme.good : NexusTheme.bad
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
        .nexusSizedCard(NexusLayout.standardCardHeight)
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
        .nexusSizedCard(NexusLayout.standardCardHeight)
    }

    private var assetsCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            NexusSectionHeader(title: "ACTIVOS CLAVE", detail: "precio, momentum y volatilidad")
            ForEach(["SPY", "GLD", "UUP", "EURUSD"], id: \.self) { ticker in
                let asset = store.snapshot?.assets?[ticker] ?? (ticker == "EURUSD" ? store.snapshot?.forex?.EURUSD : nil)
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
                Text(price(asset?.price)).frame(width: 78, alignment: .trailing)
                Text("1M \(formatPct(asset?.momentum1m))").frame(width: 86, alignment: .trailing)
                Text("Vol \(formatPct(asset?.volatility20d))").frame(width: 86, alignment: .trailing)
                Spacer()
                Text(trend(asset)).foregroundStyle(NexusTheme.toneColor(trend(asset)))
            }
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(ticker).fontWeight(.semibold)
                    Text(price(asset?.price)).foregroundStyle(NexusTheme.muted)
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
            hint: "1M \(formatPct(asset?.momentum1m)) · 3M \(formatPct(asset?.momentum3m))",
            tone: (asset?.momentum1m ?? 0) >= 0 ? NexusTheme.good : NexusTheme.bad
        )
    }

    private var liquidityCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            NexusSectionHeader(title: "LIQUIDEZ")
            NexusKVRow(label: "M2 EE. UU.", value: number("M2_Change_Pct", suffix: "%", decimals: 1))
            NexusKVRow(label: "M2 China", value: number("China_M2_YoY_Pct", suffix: "%", decimals: 1))
            Text("La liquidez es un contexto macro, no una orden aislada.")
                .font(.caption2).foregroundStyle(NexusTheme.muted)
        }
        .nexusCard().nexusSizedCard(NexusLayout.compactCardHeight)
    }

    private var valuationCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            NexusSectionHeader(title: "VALORACIÓN USA")
            NexusKVRow(label: "PER forward", value: number("PE_Forward", decimals: 1))
            NexusKVRow(label: "Percentil", value: number("PE_Forward_Percentile", suffix: "%", decimals: 0))
            NexusKVRow(label: "PER trailing", value: number("PE_Trailing", decimals: 1))
        }
        .nexusCard().nexusSizedCard(NexusLayout.compactCardHeight)
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
        .nexusCard().nexusSizedCard(NexusLayout.compactCardHeight)
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
        .nexusCard().nexusSizedCard(NexusLayout.metricCardHeight)
    }

    private var dataQualityCard: some View {
        let quality = store.snapshot?.intelligence?.dataQuality
        return NexusSummaryMetricCard(
            title: "CALIDAD DE DATOS",
            value: "\(quality?.total ?? 0) fuentes",
            hint: (quality?.unhealthy ?? 0) == 0 ? "sin incidencias detectadas" : "\(quality?.unhealthy ?? 0) incidencias: \(quality?.critical?.first ?? "revisar")",
            tone: (quality?.unhealthy ?? 0) == 0 ? NexusTheme.good : NexusTheme.warn
        )
    }

    private func number(_ key: String, suffix: String = "", decimals: Int) -> String {
        guard let value = store.snapshot?.market?[key]?.value else { return "—" }
        return String(format: "%.\(decimals)f%@", value, suffix)
    }

    private func price(_ value: Double?) -> String {
        guard let value else { return "—" }
        return String(format: value < 10 ? "%.4f" : "%.2f", value)
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
        ScrollView {
            VStack(alignment: .leading, spacing: NexusLayout.spacing) {
                decisionCard
                NexusAdaptiveGrid(minimumWidth: 260) {
                    NexusSummaryMetricCard(title: "SCORE", value: "\(store.snapshot?.decision?.score ?? 0)/100", hint: "convicción actual")
                    NexusSummaryMetricCard(title: "RIESGO", value: GlobalViewRiskLabel(vix: store.snapshot?.market?["VIX"]?.value), hint: "según volatilidad")
                    NexusSummaryMetricCard(title: "NOTICIAS", value: store.snapshot?.news?.sentiment?.dominant ?? "—", hint: store.snapshot?.news?.sentiment?.details ?? "sin titulares")
                }
                prioritiesCard
                scoreBreakdownCard
                changesCard
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(20)
        }
        .scrollBounceBehavior(.basedOnSize)
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
                    Button("Ver ficha") { store.showAsset(asset) }.buttonStyle(.borderless)
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
        VStack(alignment: .leading, spacing: 6) {
            NexusSectionHeader(title: "FACTORES DEL SCORE", detail: "reglas activas")
            ForEach(Array((store.snapshot?.decision?.scoreBreakdown ?? []).prefix(6).enumerated()), id: \.offset) { _, item in
                HStack(alignment: .top) {
                    Text(item.factor ?? "Factor").font(.caption.weight(.semibold)).frame(width: 110, alignment: .leading)
                    Text(item.reason ?? "—").font(.caption).foregroundStyle(NexusTheme.muted)
                }
            }
            Text("Describe las reglas activas; no asigna pesos inventados a cada componente.")
                .font(.caption2).foregroundStyle(NexusTheme.muted)
        }
        .nexusCard()
    }
}

private func GlobalViewRiskLabel(vix: Double?) -> String {
    guard let vix else { return "Sin datos" }
    if vix >= 25 { return "Alto" }
    if vix >= 18 { return "Medio" }
    return "Contenido"
}
