import SwiftUI
import Charts

struct HistoryView: View {
    @EnvironmentObject private var store: NexusStore
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var periodDays = 30
    @State private var selectedPointID: String?
    @State private var selectedScoreDate: Date?

    var body: some View {
        NexusPage {
            Picker("Periodo", selection: $periodDays) {
                Text("7 días").tag(7)
                Text("30 días").tag(30)
                Text("3 meses").tag(90)
            }
            .pickerStyle(.segmented)
            .frame(maxWidth: 420)
            .help("Filtra evaluaciones persistidas, no velas de mercado continuas.")

            NexusResponsiveGrid(wideColumns: 4, mediumColumns: 2) {
                NexusSummaryMetricCard(title: "Muestras", value: "\(filteredTimeline.count)", hint: "evaluaciones del periodo")
                NexusSummaryMetricCard(title: "Score medio", value: number(periodAverage), hint: "convicción promedio", help: "Media del score en el periodo seleccionado.")
                NexusSummaryMetricCard(title: "Rango", value: periodRange, hint: "mínimo y máximo")
                NexusSummaryMetricCard(title: "Cambios", value: "\(filteredEvents.count)", hint: "cambios operativos")
            }

            VStack(alignment: .leading, spacing: 8) {
                NexusSectionHeader(
                    title: "Evolución del score",
                    help: "El score mide convicción, no rentabilidad. Pulsa un punto para ver la evaluación de ese día."
                )
                if filteredTimeline.count >= 2 {
                    Chart {
                        ForEach(filteredTimeline) { point in
                            LineMark(
                                x: .value("Fecha", pointDate(point) ?? .distantPast),
                                y: .value("Score", point.score ?? 0)
                            )
                            .interpolationMethod(.catmullRom)
                            .foregroundStyle(NexusTheme.accent)
                            AreaMark(
                                x: .value("Fecha", pointDate(point) ?? .distantPast),
                                y: .value("Score", point.score ?? 0)
                            )
                            .foregroundStyle(
                                LinearGradient(
                                    colors: [NexusTheme.accent.opacity(0.30), .clear],
                                    startPoint: .top,
                                    endPoint: .bottom
                                )
                            )
                        }
                        if let selected = selectedScorePoint, let date = pointDate(selected) {
                            RuleMark(x: .value("Selección", date))
                                .foregroundStyle(NexusTheme.text.opacity(0.35))
                                .lineStyle(StrokeStyle(lineWidth: 1, dash: [3, 3]))
                            PointMark(
                                x: .value("Fecha", date),
                                y: .value("Score", selected.score ?? 0)
                            )
                            .foregroundStyle(NexusTheme.text)
                            .symbolSize(40)
                        }
                    }
                    .chartYScale(domain: 0...100)
                    .chartOverlay { proxy in
                        ChartPlotTapOverlay(proxy: proxy, selectedDate: $selectedScoreDate)
                    }
                    .frame(minHeight: 240)
                    .frame(maxWidth: .infinity)
                    if let selected = selectedScorePoint {
                        HStack(spacing: 10) {
                            Text((pointDate(selected) ?? .distantPast), format: .dateTime.day().month(.abbreviated).year())
                                .font(.caption.weight(.semibold))
                            Text("Score \(selected.score.map(String.init) ?? "—")")
                                .font(.caption.monospacedDigit())
                            Text(selected.operationalAction ?? selected.action ?? "—")
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(NexusTheme.toneColor(selected.operationalAction ?? selected.action))
                            Spacer(minLength: 0)
                        }
                        .foregroundStyle(NexusTheme.muted)
                    } else {
                        Text("Pulsa la línea para ver score y acción de esa evaluación.")
                            .font(.caption2)
                            .foregroundStyle(NexusTheme.muted)
                    }
                } else {
                    Text("Se necesitan al menos dos evaluaciones en este periodo.")
                        .font(.caption)
                        .foregroundStyle(NexusTheme.muted)
                        .frame(maxWidth: .infinity, minHeight: 100)
                }
            }
            .nexusCard()

            NexusResponsiveGrid(wideColumns: 3, mediumColumns: 1) {
                historyReturnCard("SPY", help: "Variación entre el primer y último punto persistido del periodo.")
                historyReturnCard("GLD", help: "Variación entre el primer y último punto persistido del periodo.")
                historyReturnCard("EURUSD", help: "Variación entre el primer y último punto persistido del periodo.")
            }

            VStack(alignment: .leading, spacing: 8) {
                NexusSectionHeader(title: "Cambios operativos")
                Text("Solo aparecen momentos en que cambió la recomendación operativa.")
                    .font(.caption)
                    .foregroundStyle(NexusTheme.muted)
                if filteredEvents.isEmpty {
                    Text("La recomendación todavía no ha cambiado.")
                        .foregroundStyle(NexusTheme.muted)
                } else {
                    ForEach(filteredEvents.reversed()) { event in
                        HStack(alignment: .top, spacing: 12) {
                            Image(systemName: "arrow.triangle.swap")
                                .foregroundStyle(NexusTheme.warn)
                            VStack(alignment: .leading, spacing: 3) {
                                Text("\(event.from ?? "—") → \(event.to ?? "—")")
                                    .font(.subheadline.weight(.semibold))
                                Text(explain(event.to))
                                    .font(.caption)
                                    .foregroundStyle(NexusTheme.muted)
                            }
                            Spacer()
                            VStack(alignment: .trailing) {
                                Text("Score \(event.score ?? 0)")
                                Text(shortDate(event.capturedAt))
                            }
                            .font(.caption2)
                            .foregroundStyle(NexusTheme.muted)
                        }
                        .padding(.vertical, 5)
                        Divider().opacity(0.12)
                    }
                }
            }
            .nexusCard()

            if let attribution = store.snapshot?.changeAttribution {
                VStack(alignment: .leading, spacing: 8) {
                    NexusSectionHeader(
                        title: "Qué cambió desde la evaluación anterior",
                        help: attribution.note ?? "Comparación descriptiva; no demuestra causalidad."
                    )
                    if let movers = attribution.topAssetMovers, !movers.isEmpty {
                        ForEach(Array(movers.prefix(3).enumerated()), id: \.offset) { _, mover in
                            HStack {
                                Text(mover.label ?? mover.ticker ?? "Activo")
                                Spacer()
                                Text("score \(formatDelta(mover.scoreDelta))")
                                    .foregroundStyle((mover.scoreDelta ?? 0) >= 0 ? NexusTheme.good : NexusTheme.bad)
                            }
                            .font(.caption)
                        }
                    }
                }
                .nexusCard()
            }

            trackRecordCard

            VStack(alignment: .leading, spacing: 8) {
                NexusSectionHeader(title: "Evaluaciones", detail: "Selecciona una para entenderla")
                ForEach(Array(filteredTimeline.suffix(12).reversed())) { point in
                    Button {
                        withAnimation(reduceMotion ? nil : .easeInOut(duration: 0.15)) {
                            selectedPointID = selectedPointID == point.id ? nil : point.id
                        }
                    } label: {
                        VStack(alignment: .leading, spacing: 5) {
                            ViewThatFits(in: .horizontal) {
                                HStack(spacing: 12) {
                                    Text(shortDate(point.capturedAt))
                                        .frame(width: 120, alignment: .leading)
                                        .foregroundStyle(NexusTheme.muted)
                                    Text("Macro: \(point.macroAction ?? point.action ?? "—")")
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                    Text("Operativa: \(point.operationalAction ?? point.action ?? "—")")
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                    Text("\(point.score ?? 0)/100").fontWeight(.semibold)
                                    Image(systemName: selectedPointID == point.id ? "chevron.up" : "chevron.down")
                                }
                                VStack(alignment: .leading, spacing: 3) {
                                    HStack {
                                        Text(shortDate(point.capturedAt)).foregroundStyle(NexusTheme.muted)
                                        Spacer()
                                        Text("\(point.score ?? 0)/100").fontWeight(.semibold)
                                    }
                                    Text("Macro: \(point.macroAction ?? point.action ?? "—")")
                                    Text("Operativa: \(point.operationalAction ?? point.action ?? "—")")
                                }
                            }
                            if selectedPointID == point.id {
                                Text(explain(point.operationalAction ?? point.action))
                                    .font(.caption)
                                    .foregroundStyle(NexusTheme.muted)
                            }
                        }
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .font(.caption)
                    Divider().opacity(0.10)
                }
            }
            .nexusCard()
        }
    }

    private var trackRecordCard: some View {
        let track = store.snapshot?.trackRecord
        return VStack(alignment: .leading, spacing: 8) {
            NexusSectionHeader(title: "Track record", help: "Acierto retrospectivo vs SPY a horizonte corto. No es una garantía futura.")
            if let track {
                NexusResponsiveGrid(wideColumns: 3, mediumColumns: 1) {
                    NexusSummaryMetricCard(title: "Muestras", value: "\(track.sampleSize ?? 0)", hint: "forward \(track.forwardDays ?? 0)d")
                    NexusSummaryMetricCard(title: "Macro comprar", value: formatPct(track.macroBuyHitRatePct), hint: "n=\(track.macroBuyCount ?? 0)", tone: NexusTheme.good)
                    NexusSummaryMetricCard(title: "Defensivo", value: formatPct(track.defensiveHitRatePct), hint: "n=\(track.defensiveCount ?? 0)", tone: NexusTheme.warn)
                }
                if let message = track.message {
                    Text(message).font(.caption).foregroundStyle(NexusTheme.muted)
                }
            } else {
                Text("Aún no hay suficiente historial para un track record.")
                    .font(.caption)
                    .foregroundStyle(NexusTheme.muted)
            }
        }
        .nexusCard()
    }

    private var history: HistoryBlock? {
        store.snapshot?.historyPeriods?[periodKey] ?? store.snapshot?.history
    }
    private var periodKey: String { periodDays == 90 ? "90d" : "\(periodDays)d" }
    private var events: [ActionChange] { history?.events ?? history?.actionChanges ?? [] }
    private var timeline: [ScorePoint] { history?.scoreTimeline ?? [] }
    private var filteredTimeline: [ScorePoint] {
        if store.snapshot?.historyPeriods?[periodKey] != nil { return timeline }
        return timeline.filter { isInsidePeriod($0.capturedAt) }
    }
    private var filteredEvents: [ActionChange] {
        if store.snapshot?.historyPeriods?[periodKey] != nil { return events }
        return events.filter { isInsidePeriod($0.capturedAt) }
    }

    private var selectedScorePoint: ScorePoint? {
        guard let selectedScoreDate else { return nil }
        return filteredTimeline.min(by: { lhs, rhs in
            let left = abs((pointDate(lhs) ?? .distantPast).timeIntervalSince(selectedScoreDate))
            let right = abs((pointDate(rhs) ?? .distantPast).timeIntervalSince(selectedScoreDate))
            return left < right
        })
    }
    private var periodAverage: Double? {
        let scores = filteredTimeline.compactMap(\.score)
        guard !scores.isEmpty else { return nil }
        return Double(scores.reduce(0, +)) / Double(scores.count)
    }
    private var periodRange: String {
        let scores = filteredTimeline.compactMap(\.score)
        guard let low = scores.min(), let high = scores.max() else { return "—" }
        return "\(low)–\(high)"
    }

    private func historyReturnCard(_ ticker: String, help: String) -> some View {
        let series = history?.priceSeries?[ticker] ?? []
        let recent = series.filter { isInsidePeriod($0.capturedAt) }
        let first = recent.first?.value
        let last = recent.last?.value
        let change = (first ?? 0) > 0 ? ((last ?? 0) / (first ?? 1) - 1) * 100 : nil
        return NexusSummaryMetricCard(
            title: ticker,
            value: formatPct(change),
            hint: "variación del periodo",
            tone: (change ?? 0) >= 0 ? NexusTheme.good : NexusTheme.bad,
            help: help
        )
    }

    private func explain(_ action: String?) -> String {
        let value = (action ?? "").uppercased()
        if value.contains("NO ABRIR") { return "Un filtro de riesgo impide abrir posiciones aunque exista oportunidad macro." }
        if value.contains("COMPRAR PARCIAL") { return "Se permite una entrada reducida; todavía no hay confirmación completa." }
        if value.contains("COMPRAR") { return "Se puede aumentar exposición según la asignación sugerida." }
        if value.contains("REDUCIR") || value.contains("VENDER") { return "La prioridad es reducir riesgo y preservar capital." }
        return "No hay suficiente ventaja para modificar la exposición."
    }

    private func shortDate(_ raw: String?) -> String {
        String((raw ?? "—").prefix(16)).replacingOccurrences(of: "T", with: " ")
    }

    private func pointDate(_ point: ScorePoint) -> Date? {
        parseDate(point.capturedAt)
    }

    private func isInsidePeriod(_ raw: String?) -> Bool {
        guard let date = parseDate(raw) else { return true }
        return date >= Calendar.current.date(byAdding: .day, value: -periodDays, to: Date()) ?? .distantPast
    }

    private func parseDate(_ raw: String?) -> Date? {
        guard let raw else { return nil }
        return ISO8601DateFormatter.nexus.date(from: raw)
            ?? ISO8601DateFormatter.nexusFractional.date(from: raw)
    }

    private func number(_ value: Double?) -> String {
        value.map { String(format: "%.1f", $0) } ?? "—"
    }
}

struct ForexGoldView: View {
    enum Mode: Equatable {
        case forex
        case gold
    }

    @EnvironmentObject private var store: NexusStore
    @Environment(\.nexusBreakpoint) private var breakpoint
    @State private var selectedHeadline: NewsItem?
    @State private var showAllGoldFactors = false
    @AppStorage("nexus.forexGold.primaryPair") private var primaryPair = "USDEUR"
    let mode: Mode

    var body: some View {
        Group {
            switch mode {
            case .forex:
                forexPage
            case .gold:
                goldPage
            }
        }
        .sheet(item: $selectedHeadline) { item in
            headlineReader(item)
        }
    }

    private var forexPage: some View {
        NexusPage {
            let fx = store.snapshot?.forex
            exchangeRateStrip
            if store.snapshot?.fxAlignment?.conflict == true {
                fxAlignmentNotice
            }
            fxPlanCard
            NexusKPIStrip(items: [
                NexusKPI(title: "ACCIÓN FX", value: fx?.signal?.action ?? "—", hint: "calidad señal \(fx?.signal?.confidence ?? "—")", tone: NexusTheme.toneColor(fx?.signal?.action)),
                NexusKPI(title: "EUR/USD", value: number(fx?.rates?.eurUsd, digits: 5), hint: fx?.signal?.eurTrend ?? "tendencia —", tone: NexusTheme.toneColor(fx?.signal?.action)),
                NexusKPI(title: "USD/EUR", value: number(fx?.rates?.usdEur, digits: 5), hint: fx?.signal?.usdTrend ?? "tendencia —", tone: NexusTheme.toneColor(fx?.signal?.action)),
            ])
            pairSelector
            forexSparkline
            NexusResponsiveGrid(wideColumns: 2, mediumColumns: 1) {
                currencyOverviewCard
                relativeCard
            }
            NexusResponsiveGrid(wideColumns: 2, mediumColumns: 1) {
                forexNewsCard
                forexRangeCard
            }
            fxHeadlinesCard
            fxDigestCard
            fxCalendarCard
        }
    }

    private var goldPage: some View {
        NexusPage {
            goldOutlookHeader
            goldDriverStrip
            if store.snapshot?.gold?.change != nil {
                goldChangeCard
            }
            goldSparkline
            goldFactorSummary
            goldPositioningCard
            goldBacktestCard
            if hasGoldAblation {
                goldAblationCard
            }
            goldProbabilityHistoryCard
            goldDetailsLayout
            NexusResponsiveGrid(wideColumns: 2, mediumColumns: 1) {
                fxHeadlinesCard
                fxCalendarCard
            }
        }
    }

    @ViewBuilder
    private var goldDetailsLayout: some View {
        if breakpoint == .narrow {
            LazyVStack(spacing: NexusLayout.spacing) {
                inflationCard
                ratesEnergyCard
                goldCard
                goldVsDollarCard
                goldChangesCard
                goldMethodologyCard
            }
        } else {
            HStack(alignment: .top, spacing: NexusLayout.spacing) {
                LazyVStack(spacing: NexusLayout.spacing) {
                    inflationCard
                    goldCard
                    goldChangesCard
                }
                .frame(maxWidth: .infinity, alignment: .top)

                LazyVStack(spacing: NexusLayout.spacing) {
                    ratesEnergyCard
                    goldVsDollarCard
                    goldMethodologyCard
                }
                .frame(maxWidth: .infinity, alignment: .top)
            }
        }
    }

    private var exchangeRateStrip: some View {
        let rates = store.snapshot?.forex?.rates
        return NexusResponsiveGrid(wideColumns: 2, mediumColumns: 2) {
            VStack(alignment: .leading, spacing: 4) {
                Text("TIPO DE CAMBIO")
                    .font(.caption.weight(.bold))
                    .foregroundStyle(NexusTheme.accent)
                Text(rates?.eurLabel ?? "1 EUR = — USD")
                    .font(.system(size: 26, weight: .bold, design: .rounded))
                    .minimumScaleFactor(0.6)
                    .lineLimit(1)
                Text("Spot EUR/USD")
                    .font(.caption)
                    .foregroundStyle(NexusTheme.muted)
            }
            .nexusCard()
            .nexusInteractive(label: "Abrir detalle de EUR/USD") { store.showAsset("EURUSD") }
            VStack(alignment: .leading, spacing: 4) {
                Text("INVERSO")
                    .font(.caption.weight(.bold))
                    .foregroundStyle(NexusTheme.accent)
                Text(rates?.usdLabel ?? "1 USD = — EUR")
                    .font(.system(size: 26, weight: .bold, design: .rounded))
                    .minimumScaleFactor(0.6)
                    .lineLimit(1)
                Text("Cuántos euros compra 1 dólar")
                    .font(.caption)
                    .foregroundStyle(NexusTheme.muted)
            }
            .nexusCard()
            .nexusInteractive(label: "Abrir detalle de USD/EUR") { store.showAsset("USDEUR") }
        }
        .help("Ambos lados del mismo tipo de cambio. Clic para abrir el inspector de EUR/USD.")
    }

    private var fxAlignmentNotice: some View {
        NexusNoticeCard(
            title: store.snapshot?.fxAlignment?.title ?? "La operativa no autoriza entradas",
            detail: store.snapshot?.fxAlignment?.detail ?? "El sesgo de EUR/USD y oro es vigilancia, no una orden.",
            actionTitle: "Resumen"
        ) {
            store.selected = .overview
        }
    }

    private var digest: FxGoldDigest? { store.snapshot?.fxDigest }

    private var fxDigestCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            NexusSectionHeader(
                title: "Qué ha cambiado",
                help: "Compara EUR/USD y el sesgo de divisas con la última evaluación persistida. No es una orden."
            )
            Text(digest?.headline ?? "Sin comparación todavía")
                .font(.title3.weight(.bold))
            Text(digest?.summary ?? "Aún no hay una evaluación anterior.")
                .font(.subheadline)
                .foregroundStyle(NexusTheme.muted)
                .fixedSize(horizontal: false, vertical: true)

            HStack(spacing: 16) {
                digestMetric("EUR/USD", digest?.eurusd?.label ?? fxPipLabel, digestTone(digest?.eurusd?.pips))
                digestMetric("SEÑAL FX", digest?.forexAction?.label ?? digestChangeLabel(digest?.forexAction), digest?.forexAction?.changed == true ? NexusTheme.warn : NexusTheme.muted)
            }
            if digest?.hasPrior == true {
                Text("Ref. \(relativeAge(from: digest?.baselineCapturedAt))")
                    .font(.caption2)
                    .foregroundStyle(NexusTheme.muted)
            }
        }
        .nexusCard()
    }

    private var pairSelector: some View {
        HStack(spacing: 8) {
            Text("PAR PRINCIPAL")
                .font(.caption.weight(.bold))
                .foregroundStyle(NexusTheme.accent)
            Image(systemName: "questionmark.circle")
                .font(.caption2)
                .foregroundStyle(NexusTheme.muted)
                .help("Elige qué orientación del mismo tipo de cambio se muestra. USD/EUR es la vista inicial.")
            Picker("Par principal", selection: $primaryPair) {
                Text("USD/EUR").tag("USDEUR")
                Text("EUR/USD").tag("EURUSD")
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .frame(width: 190)
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 2)
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var forexSparkline: some View {
        NexusSparklineCard(
            title: primaryPair == "USDEUR" ? "USD/EUR" : "EUR/USD",
            help: "Par seleccionado con intervalo y rango independientes, zoom/pan e indicadores técnicos.",
            points: store.snapshot?.sparklines?[primaryPair] ?? [],
            showRelative: false,
            minHeight: 260,
            valueDigits: 5,
            ticker: primaryPair,
            news: newsLinked(to: "EURUSD", items: store.snapshot?.news?.items ?? []),
            onTap: { store.showAsset(primaryPair) },
            onOpenNews: { item in
                store.selectedNewsID = item.id
                store.selected = .news
            }
        )
        .id(primaryPair)
    }

    private var goldSparkline: some View {
        NexusSparklineCard(
            title: "Oro spot · XAU/USD",
            help: "Precio spot del oro frente al dólar. GLD se muestra más abajo como proxy negociable y no debe confundirse con esta cotización.",
            points: store.snapshot?.sparklines?["XAUUSD"] ?? [],
            showRelative: false,
            minHeight: 260,
            valueDigits: 2,
            ticker: "XAUUSD",
            news: newsLinked(
                to: "XAUUSD",
                items: store.snapshot?.news?.items ?? [],
                extra: newsLinked(to: "GLD", items: store.snapshot?.news?.items ?? [])
            ),
            calendarEvents: store.snapshot?.calendar?.goldUpcoming ?? [],
            spyPoints: store.snapshot?.sparklines?["SPY"] ?? [],
            onTap: { store.showAsset("XAUUSD") },
            onOpenNews: { item in
                store.selectedNewsID = item.id
                store.selected = .news
            }
        )
    }

    private var currencyOverviewCard: some View {
        let fx = store.snapshot?.forex
        let eur = fx?.EURUSD
        return VStack(alignment: .leading, spacing: 10) {
            NexusSectionHeader(
                title: "USD/EUR & EUR/USD",
                help: "Dos orientaciones del mismo tipo de cambio. Los movimientos y medias de USD/EUR se calculan invirtiendo EUR/USD."
            )
            HStack(alignment: .top, spacing: 18) {
                currencySide(
                    title: "USD/EUR",
                    spot: inverse(eur?.price),
                    ma20: inverse(eur?.ma20),
                    ma50: inverse(eur?.ma50),
                    momentum1m: inverseReturn(eur?.momentum1m),
                    momentum3m: inverseReturn(eur?.momentum3m),
                    trend: fx?.signal?.usdTrend
                )
                Divider()
                currencySide(
                    title: "EUR/USD",
                    spot: eur?.price,
                    ma20: eur?.ma20,
                    ma50: eur?.ma50,
                    momentum1m: eur?.momentum1m,
                    momentum3m: eur?.momentum3m,
                    trend: fx?.signal?.eurTrend
                )
            }
            Divider().opacity(0.12)
            HStack(spacing: 14) {
                metric("Relativo 1M", formatPct(fx?.signal?.rel1m))
                metric("Relativo 3M", formatPct(fx?.signal?.rel3m))
            }
            Text(fx?.signal?.evolution ?? fx?.signal?.summary ?? "Sin evolución relativa disponible.")
                .font(.caption)
                .foregroundStyle(NexusTheme.muted)
                .fixedSize(horizontal: false, vertical: true)
        }
        .nexusCard()
    }

    private func currencySide(
        title: String,
        spot: Double?,
        ma20: Double?,
        ma50: Double?,
        momentum1m: Double?,
        momentum3m: Double?,
        trend: String?
    ) -> some View {
        VStack(alignment: .leading, spacing: 7) {
            Text(LocalizedStringKey(title))
                .font(.caption.weight(.bold))
                .foregroundStyle(NexusTheme.accent)
            metric("Spot", number(spot, digits: 5))
            metric("MA20 / MA50", "\(number(ma20, digits: 5)) / \(number(ma50, digits: 5))")
            metric("Tendencia", trend ?? "—")
            MetricBar(label: "Mom 1M", value: momentum1m, range: -5...5)
            MetricBar(label: "Mom 3M", value: momentum3m, range: -10...10)
        }
        .frame(maxWidth: .infinity, alignment: .topLeading)
    }

    private var euroCard: some View {
        let fx = store.snapshot?.forex
        let eur = fx?.EURUSD
        return VStack(alignment: .leading, spacing: 8) {
            Text("EUR/USD")
                .font(.caption.weight(.bold))
                .foregroundStyle(NexusTheme.accent)
            metric("Spot", eur?.price.map { String(format: "%.4f", $0) } ?? "—")
            metric("MA20 / MA50", "\(number(eur?.ma20, digits: 4)) / \(number(eur?.ma50, digits: 4))")
            metric("Tendencia", fx?.signal?.eurTrend ?? "—")
            MetricBar(label: "Mom 1M", value: eur?.momentum1m, range: -5...5)
            MetricBar(label: "Mom 3M", value: eur?.momentum3m, range: -10...10)
            Text(fx?.dual?["eur_view"] ?? "—")
                .font(.caption)
                .foregroundStyle(NexusTheme.muted)
        }
        .nexusCard()
        .frame(maxWidth: .infinity, alignment: .topLeading)
        .nexusInteractive(label: "Abrir detalle de EUR/USD") { store.showAsset("EURUSD") }
        .help("Abrir detalle de EUR/USD")
    }

    private var dollarCard: some View {
        let fx = store.snapshot?.forex
        let eur = fx?.EURUSD
        return VStack(alignment: .leading, spacing: 8) {
            Text("USD/EUR")
                .font(.caption.weight(.bold))
                .foregroundStyle(NexusTheme.accent)
            metric("Spot", number(inverse(eur?.price), digits: 5))
            metric("MA20 / MA50", "\(number(inverse(eur?.ma20), digits: 5)) / \(number(inverse(eur?.ma50), digits: 5))")
            metric("Tendencia", fx?.signal?.usdTrend ?? "—")
            MetricBar(label: "Mom 1M", value: inverseReturn(eur?.momentum1m), range: -5...5)
            MetricBar(label: "Mom 3M", value: inverseReturn(eur?.momentum3m), range: -10...10)
            Text(fx?.dual?["usd_view"] ?? "—")
                .font(.caption)
                .foregroundStyle(NexusTheme.muted)
        }
        .nexusCard()
        .frame(maxWidth: .infinity, alignment: .topLeading)
        .nexusInteractive(label: "Abrir detalle de USD/EUR") { store.showAsset("USDEUR") }
        .help("Abrir detalle de USD/EUR")
    }

    private var goldOutlookHeader: some View {
        let outlook = store.snapshot?.gold?.outlook
        return VStack(alignment: .leading, spacing: NexusLayout.spacing) {
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: 3) {
                    Text("PERSPECTIVA DEL ORO")
                        .font(.caption.weight(.bold))
                        .foregroundStyle(NexusTheme.accent)
                    Text("Dirección agrupada, no permiso de entrada")
                        .font(.title2.weight(.bold))
                    Text(outlook?.asOf.map { "Datos hasta \($0)" } ?? "Esperando la primera captura macro completa")
                        .font(.caption)
                        .foregroundStyle(NexusTheme.muted)
                }
                Spacer()
                Text(goldStatusLabel(outlook?.status))
                    .font(.caption2.weight(.bold))
                    .foregroundStyle(NexusTheme.warn)
                    .padding(.horizontal, 9)
                    .padding(.vertical, 5)
                    .background(NexusTheme.warn.opacity(0.14), in: Capsule())
                    .accessibilityLabel("Modelo preliminar")
            }
            NexusResponsiveGrid(wideColumns: 2, mediumColumns: 2) {
                goldHorizonCard(title: "CORTO PLAZO", horizon: outlook?.shortTerm)
                goldHorizonCard(title: "MEDIO PLAZO", horizon: outlook?.mediumTerm)
            }
        }
    }

    private func goldHorizonCard(title: String, horizon: GoldHorizon?) -> some View {
        let tone = NexusTheme.toneColor(horizon?.tone ?? horizon?.label)
        return VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(title)
                    .font(.caption.weight(.bold))
                    .foregroundStyle(NexusTheme.accent)
                Spacer()
                Text("\(horizon?.horizonDays ?? 0) sesiones")
                    .font(.caption2)
                    .foregroundStyle(NexusTheme.muted)
            }
            HStack(alignment: .firstTextBaseline, spacing: 10) {
                Text(horizon?.label ?? "SIN DATOS")
                    .font(.title2.weight(.bold))
                    .foregroundStyle(tone)
                Spacer()
                Text(horizon?.probabilityUp.map { String(format: "%.0f%%", $0) } ?? "—")
                    .font(.system(size: 30, weight: .bold, design: .rounded).monospacedDigit())
                    .foregroundStyle(tone)
            }
            ProgressView(value: horizon?.probabilityUp ?? 0, total: 100)
                .tint(tone)
                .accessibilityLabel("Probabilidad alcista")
                .accessibilityValue(horizon?.probabilityUp.map { String(format: "%.0f por ciento", $0) } ?? "sin datos")
            HStack {
                Text("Confianza \(horizon?.confidence ?? "—")")
                Spacer()
                Text("Cobertura \(horizon?.coveragePct.map { String(format: "%.0f%%", $0) } ?? "—")")
            }
            .font(.caption)
            .foregroundStyle(NexusTheme.muted)
        }
        .nexusCard()
        .accessibilityElement(children: .combine)
    }

    private var goldFactorSummary: some View {
        let groups = store.snapshot?.gold?.outlook?.groups ?? []
        let ranked = groups.sorted {
            max(abs($0.shortContribution ?? 0), abs($0.mediumContribution ?? 0))
                > max(abs($1.shortContribution ?? 0), abs($1.mediumContribution ?? 0))
        }
        let primary = Array(ranked.prefix(3))
        let secondary = Array(ranked.dropFirst(3))
        return VStack(alignment: .leading, spacing: 10) {
            NexusSectionHeader(
                title: "CONTRIBUCIÓN POR FAMILIA",
                detail: "prioridad por impacto · límites anti-doble-conteo",
                help: "Cada familia aporta como máximo su peso, aunque contenga varios indicadores relacionados."
            )
            if groups.isEmpty {
                NexusEmptyState(
                    title: "Sin factores calculados",
                    detail: "Actualiza NEXUS para generar la primera perspectiva agrupada.",
                    symbol: "chart.bar.xaxis"
                )
            } else {
                ForEach(primary) { group in
                    goldContributionRow(group)
                    if group.id != primary.last?.id { Divider().opacity(0.10) }
                }
                if !secondary.isEmpty {
                    Divider().opacity(0.12)
                    DisclosureGroup(isExpanded: $showAllGoldFactors) {
                        VStack(alignment: .leading, spacing: 10) {
                            ForEach(secondary) { group in
                                goldContributionRow(group)
                                if group.id != secondary.last?.id { Divider().opacity(0.10) }
                            }
                        }
                        .padding(.top, 8)
                    } label: {
                        Text(showAllGoldFactors ? "Ocultar factores secundarios" : "Mostrar \(secondary.count) factores secundarios")
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(NexusTheme.accent)
                    }
                }
            }
        }
        .nexusCard()
    }

    private var goldDriverStrip: some View {
        let groups = (store.snapshot?.gold?.outlook?.groups ?? []).filter { $0.available == true }
        let support = groups.filter { ($0.shortContribution ?? 0) > 0.05 }
            .max { ($0.shortContribution ?? 0) < ($1.shortContribution ?? 0) }
        let pressure = groups.filter { ($0.shortContribution ?? 0) < -0.05 }
            .min { ($0.shortContribution ?? 0) < ($1.shortContribution ?? 0) }
        let medium = groups.max {
            abs($0.mediumContribution ?? 0) < abs($1.mediumContribution ?? 0)
        }
        return NexusResponsiveGrid(wideColumns: 3, mediumColumns: 3, spacing: 10) {
            goldDriverCard(title: "PRINCIPAL APOYO · 1M", group: support, value: support?.shortContribution)
            goldDriverCard(title: "PRINCIPAL PRESIÓN · 1M", group: pressure, value: pressure?.shortContribution)
            goldDriverCard(title: "MAYOR IMPACTO · 3M", group: medium, value: medium?.mediumContribution)
        }
    }

    private func goldDriverCard(title: String, group: GoldFactorGroup?, value: Double?) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(title)
                .font(.caption2.weight(.bold))
                .foregroundStyle(NexusTheme.accent)
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(group?.label ?? "Sin señal")
                    .font(.subheadline.weight(.semibold))
                    .lineLimit(1)
                Spacer(minLength: 4)
                Text(signed(value))
                    .font(.subheadline.monospacedDigit().weight(.bold))
                    .foregroundStyle(contributionTone(value))
            }
        }
        .nexusCard()
        .accessibilityElement(children: .combine)
    }

    private var goldChangeCard: some View {
        let change = store.snapshot?.gold?.change
        return VStack(alignment: .leading, spacing: 10) {
            NexusSectionHeader(
                title: "DESDE LA EVALUACIÓN ANTERIOR",
                detail: shortGoldDate(change?.previousCapturedAt),
                help: "Compara probabilidades y contribuciones con la última captura de un día anterior."
            )
            Text(change?.headline ?? "Sin comparación anterior")
                .font(.headline)
            NexusResponsiveGrid(wideColumns: 3, mediumColumns: 3, spacing: 10) {
                goldHorizonChangeCard("21 SESIONES", change?.short)
                goldHorizonChangeCard("63 SESIONES", change?.medium)
                VStack(alignment: .leading, spacing: 5) {
                    Text("FACTORES QUE MÁS CAMBIAN")
                        .font(.caption2.weight(.bold))
                        .foregroundStyle(NexusTheme.accent)
                    ForEach(change?.drivers ?? []) { driver in
                        HStack {
                            Text(driver.label ?? "Factor")
                                .lineLimit(1)
                            Spacer()
                            Text("1M \(signed(driver.shortDelta)) · 3M \(signed(driver.mediumDelta))")
                                .monospacedDigit()
                                .foregroundStyle(contributionTone(driver.shortDelta ?? driver.mediumDelta))
                        }
                        .font(.caption)
                    }
                    if change?.drivers?.isEmpty != false {
                        Text("Sin variaciones comparables")
                            .font(.caption)
                            .foregroundStyle(NexusTheme.muted)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .topLeading)
            }
        }
        .nexusCard()
    }

    private func goldHorizonChangeCard(_ title: String, _ change: GoldHorizonChange?) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(title)
                .font(.caption2.weight(.bold))
                .foregroundStyle(NexusTheme.accent)
            HStack(alignment: .firstTextBaseline) {
                Text(change?.currentLabel ?? "—")
                    .font(.subheadline.weight(.semibold))
                Spacer()
                Text(change?.deltaProbability.map { String(format: "%+.1f pp", $0) } ?? "—")
                    .font(.subheadline.monospacedDigit().weight(.bold))
                    .foregroundStyle(contributionTone(change?.deltaProbability))
            }
            Text("\(change?.previousProbability.map { String(format: "%.0f%%", $0) } ?? "—") → \(change?.currentProbability.map { String(format: "%.0f%%", $0) } ?? "—")")
                .font(.caption.monospacedDigit())
                .foregroundStyle(NexusTheme.muted)
        }
        .frame(maxWidth: .infinity, alignment: .topLeading)
        .accessibilityElement(children: .combine)
    }

    private func goldContributionRow(_ group: GoldFactorGroup) -> some View {
        let short = group.shortContribution
        let medium = group.mediumContribution
        let available = group.available == true
        return VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .firstTextBaseline) {
                Label(group.label ?? "Factor", systemImage: available ? "checkmark.circle.fill" : "clock.badge.questionmark")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(available ? NexusTheme.text : NexusTheme.muted)
                Spacer()
                if available && group.scoreEnabled != false {
                    Text("1M \(signed(short)) · 3M \(signed(medium))")
                        .font(.caption.monospacedDigit().weight(.semibold))
                        .foregroundStyle(contributionTone(short))
                } else if available {
                    Text("SOLO CONTEXTO")
                        .font(.caption2.weight(.bold))
                        .foregroundStyle(NexusTheme.warn)
                } else {
                    Text("PENDIENTE")
                        .font(.caption2.weight(.bold))
                        .foregroundStyle(NexusTheme.muted)
                }
            }
            HStack(spacing: 8) {
                GoldContributionBar(value: short, label: "1M")
                GoldContributionBar(value: medium, label: "3M")
            }
            Text(group.note ?? "")
                .font(.caption2)
                .foregroundStyle(NexusTheme.muted)
                .fixedSize(horizontal: false, vertical: true)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(group.label ?? "Factor"), corto plazo \(signed(short)), medio plazo \(signed(medium))")
    }

    private var inflationCard: some View {
        let details = goldGroup("inflation")?.details ?? []
        return VStack(alignment: .leading, spacing: 10) {
            NexusSectionHeader(
                title: "INFLACIÓN",
                detail: "mensual e interanual",
                help: "CPI y PCE se agrupan para que general, subyacente, mensual e interanual no sean votos independientes."
            )
            LazyVGrid(
                columns: [GridItem(.flexible()), GridItem(.flexible())],
                alignment: .leading,
                spacing: 8
            ) {
                ForEach(details) { detail in
                    VStack(alignment: .leading, spacing: 2) {
                        Text(detail.label ?? "Dato")
                            .font(.caption2)
                            .foregroundStyle(NexusTheme.muted)
                        Text(detail.display ?? "—")
                            .font(.subheadline.monospacedDigit().weight(.semibold))
                        if let provenance = goldDetailProvenance(detail) {
                            Text(provenance)
                                .font(.caption2)
                                .foregroundStyle(detail.quality == "OK" ? NexusTheme.muted : NexusTheme.warn)
                                .lineLimit(1)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
            if details.isEmpty {
                Text("Los datos aparecerán tras actualizar la caché macro.")
                    .font(.caption)
                    .foregroundStyle(NexusTheme.muted)
            }
        }
        .nexusCard()
        .frame(maxWidth: .infinity, alignment: .topLeading)
    }

    private var goldPositioningCard: some View {
        let positioning = store.snapshot?.gold?.positioning
        let points = positioning?.history ?? []
        let gate = store.snapshot?.gold?.backtest?.featureGates?["positioning"]
        return VStack(alignment: .leading, spacing: 12) {
            NexusSectionHeader(
                title: "POSICIONAMIENTO CFTC / COMEX",
                detail: positioning?.asOf.map { "informe \(String($0.prefix(10)))" },
                help: "Posiciones semanales de Managed Money en futuros COMEX Gold. El informe del martes solo entra desde su publicación oficial; contratos y porcentajes de interés abierto no se suman como votos separados."
            )

            if positioning?.status == "MISSING" || positioning == nil {
                NexusEmptyState(
                    title: "Sin informe CFTC disponible",
                    detail: "NEXUS mantendrá este factor fuera del score hasta recuperar una publicación verificable.",
                    symbol: "chart.line.downtrend.xyaxis"
                )
            } else {
                NexusResponsiveGrid(wideColumns: 4, mediumColumns: 2, spacing: 10) {
                    positioningMetric("NETO MANAGED MONEY", contracts(positioning?.netContracts), "\(formatPct(positioning?.netPctOI)) del OI")
                    positioningMetric("CAMBIO SEMANAL", signedContracts(positioning?.weeklyChangeContracts), "4 sem \(signedContracts(positioning?.fourWeekChangeContracts))")
                    positioningMetric("PERCENTIL 3 AÑOS", positioning?.percentile3Y.map { String(format: "%.0f", $0) } ?? "—", "z-score \(number(positioning?.zscore3Y, digits: 2))")
                    positioningMetric("ESTADO EN EL MODELO", gate == "ENABLED" ? "ACTIVO" : "CONTEXTO", gate == "ENABLED" ? "peso limitado" : "pendiente de ablación")
                }

                if points.count >= 2 {
                    Chart(points) { point in
                        if let date = sparklineDate(point.reportDate) {
                            if let value = point.positioningIndex {
                                LineMark(
                                    x: .value("Fecha", date),
                                    y: .value("Índice", value),
                                    series: .value("Serie", "Posicionamiento")
                                )
                                .foregroundStyle(by: .value("Serie", "Posicionamiento"))
                                .interpolationMethod(.catmullRom)
                            }
                            if let value = point.goldPriceIndex {
                                LineMark(
                                    x: .value("Fecha", date),
                                    y: .value("Índice", value),
                                    series: .value("Serie", "Oro spot")
                                )
                                .foregroundStyle(by: .value("Serie", "Oro spot"))
                                .interpolationMethod(.catmullRom)
                            }
                        }
                    }
                    .chartForegroundStyleScale([
                        "Posicionamiento": NexusTheme.accent,
                        "Oro spot": NexusTheme.warn,
                    ])
                    .chartLegend(position: .top, alignment: .leading)
                    .chartYAxis { AxisMarks(position: .leading) }
                    .frame(height: 210)
                    .accessibilityLabel("Evolución normalizada del posicionamiento CFTC y del oro spot")
                    Text("Comparación normalizada: oro spot base 100; posicionamiento = 100 + 20 × z-score de tres años.")
                        .font(.caption2)
                        .foregroundStyle(NexusTheme.muted)
                }

                NexusResponsiveGrid(wideColumns: 3, mediumColumns: 1, spacing: 10) {
                    positioningMetric("CONCENTRACIÓN 4 MAYORES", "L \(formatPct(positioning?.concentration4LongPct))", "C \(formatPct(positioning?.concentration4ShortPct))")
                    positioningMetric("CONCENTRACIÓN 8 MAYORES", "L \(formatPct(positioning?.concentration8LongPct))", "C \(formatPct(positioning?.concentration8ShortPct))")
                    positioningMetric("PRECIO VS POSICIÓN", positioning?.pricePositioningDivergence ?? "—", "publicado \(shortGoldDate(positioning?.releaseAt) ?? "—")")
                }
                Text("Fuente: \(positioning?.source ?? "CFTC") · Contrato \(positioning?.contractCode ?? "088691") · \(positioning?.contractUnits ?? "100 onzas troy por contrato")")
                    .font(.caption2)
                    .foregroundStyle(NexusTheme.muted)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .nexusCard()
        .frame(maxWidth: .infinity, alignment: .topLeading)
    }

    private func positioningMetric(_ title: String, _ value: String, _ hint: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.caption2.weight(.bold))
                .foregroundStyle(NexusTheme.accent)
            Text(value)
                .font(.title3.monospacedDigit().weight(.bold))
                .minimumScaleFactor(0.75)
                .lineLimit(1)
            Text(hint)
                .font(.caption2)
                .foregroundStyle(NexusTheme.muted)
                .lineLimit(2)
        }
        .padding(10)
        .frame(maxWidth: .infinity, minHeight: 76, alignment: .topLeading)
        .background(NexusTheme.cardInner, in: RoundedRectangle(cornerRadius: 9, style: .continuous))
        .accessibilityElement(children: .combine)
    }

    private func contracts(_ value: Double?) -> String {
        guard let value else { return "—" }
        return value.formatted(.number.precision(.fractionLength(0)))
    }

    private func signedContracts(_ value: Double?) -> String {
        guard let value else { return "—" }
        return String(format: "%+.0f", value)
    }

    private var ratesEnergyCard: some View {
        let ids = ["real_rates", "dollar", "energy", "activity", "liquidity"]
        let groups = ids.compactMap(goldGroup)
        return VStack(alignment: .leading, spacing: 10) {
            NexusSectionHeader(
                title: "TIPOS, ENERGÍA Y ACTIVIDAD",
                help: "Factores indirectos agrupados. Un dato ausente reduce cobertura; no se transforma en cero."
            )
            ForEach(groups) { group in
                VStack(alignment: .leading, spacing: 4) {
                    Text(group.label ?? "Factor")
                        .font(.caption.weight(.bold))
                        .foregroundStyle(NexusTheme.accent)
                    ForEach((group.details ?? []).filter { $0.available == true }) { detail in
                        VStack(alignment: .leading, spacing: 2) {
                            NexusKVRow(label: detail.label ?? "Dato", value: detail.display ?? "—")
                            if let provenance = goldDetailProvenance(detail) {
                                Text(provenance)
                                    .font(.caption2)
                                    .foregroundStyle(detail.quality == "OK" ? NexusTheme.muted : NexusTheme.warn)
                                    .lineLimit(1)
                            }
                        }
                    }
                    if group.available != true {
                        Text("Sin dato público disponible")
                            .font(.caption2)
                            .foregroundStyle(NexusTheme.muted)
                    }
                }
                if group.id != groups.last?.id { Divider().opacity(0.10) }
            }
        }
        .nexusCard()
        .frame(maxWidth: .infinity, alignment: .topLeading)
    }

    private var goldChangesCard: some View {
        let changes = store.snapshot?.gold?.outlook?.whatChangesSignal ?? []
        return VStack(alignment: .leading, spacing: 8) {
            NexusSectionHeader(title: "QUÉ CAMBIARÍA LA SEÑAL")
            ForEach(changes, id: \.self) { change in
                Label(change, systemImage: "arrow.triangle.branch")
                    .font(.caption)
                    .foregroundStyle(NexusTheme.text)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .nexusCard()
        .frame(maxWidth: .infinity, alignment: .topLeading)
    }

    private var goldMethodologyCard: some View {
        let outlook = store.snapshot?.gold?.outlook
        let history = store.snapshot?.gold?.history
        return VStack(alignment: .leading, spacing: 8) {
            NexusSectionHeader(title: "METODOLOGÍA Y COBERTURA")
            Text(outlook?.methodology ?? "Perspectiva todavía no disponible.")
                .font(.caption.weight(.semibold))
            ForEach(outlook?.dataNotes ?? [], id: \.self) { note in
                Label(note, systemImage: "info.circle")
                    .font(.caption2)
                    .foregroundStyle(NexusTheme.muted)
                    .fixedSize(horizontal: false, vertical: true)
            }
            HStack {
                Text("Fuentes privadas")
                    .foregroundStyle(NexusTheme.muted)
                Spacer()
                Text(outlook?.privateSourcesStatus ?? "STANDBY")
                    .fontWeight(.bold)
                    .foregroundStyle(NexusTheme.warn)
            }
            .font(.caption)
            Divider().opacity(0.12)
            NexusKVRow(
                label: "Predicciones en vivo guardadas",
                value: history?.predictions.map { String($0) } ?? "0"
            )
            NexusKVRow(
                label: "Observaciones versionadas",
                value: history?.observations.map { String($0) } ?? "0"
            )
            NexusKVRow(
                label: "Resultados vencidos en vivo · 21 / 63",
                value: "\(history?.validation?["short"]?.sampleSize ?? 0) / \(history?.validation?["medium"]?.sampleSize ?? 0)"
            )
            Text("El backtest histórico aparece en su panel propio. Este recuento corresponde solo al seguimiento en vivo y necesita 30 resultados vencidos por horizonte.")
                .font(.caption)
                .foregroundStyle(NexusTheme.muted)
                .fixedSize(horizontal: false, vertical: true)
        }
        .nexusCard()
        .frame(maxWidth: .infinity, alignment: .topLeading)
    }

    private var goldBacktestCard: some View {
        let report = store.snapshot?.gold?.backtest
        let ready = report?.status == "READY"
        let promoted = report?.passesBaselines == true
        return VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .firstTextBaseline, spacing: 12) {
                NexusSectionHeader(
                    title: "VALIDACIÓN HISTÓRICA POINT-IN-TIME",
                    detail: backtestPeriod(report),
                    help: "Cada corte solo usa datos que ya se habían publicado. Brier menor es mejor; precisión equilibrada mayor es mejor."
                )
                Spacer(minLength: 8)
                Text(promoted ? "CANDIDATO" : ready ? "PRELIMINAR" : "PENDIENTE")
                    .font(.caption2.weight(.bold))
                    .foregroundStyle(promoted ? NexusTheme.good : NexusTheme.warn)
                    .padding(.horizontal, 9)
                    .padding(.vertical, 5)
                    .background((promoted ? NexusTheme.good : NexusTheme.warn).opacity(0.14), in: Capsule())
            }

            if ready {
                ViewThatFits(in: .horizontal) {
                    HStack(alignment: .top, spacing: 12) {
                        goldBacktestHorizon("21", report: report)
                        goldBacktestHorizon("63", report: report)
                    }
                    VStack(alignment: .leading, spacing: 12) {
                        goldBacktestHorizon("21", report: report)
                        goldBacktestHorizon("63", report: report)
                    }
                }
                Text(promoted
                     ? "El modelo supera las referencias definidas en ambos horizontes."
                     : "Aún no supera de forma consistente a momentum y dólar + tipos reales; la confianza permanece limitada.")
                    .font(.caption)
                    .foregroundStyle(promoted ? NexusTheme.good : NexusTheme.warn)
                    .fixedSize(horizontal: false, vertical: true)
            } else {
                NexusEmptyState(
                    title: "Validación todavía no ejecutada",
                    detail: "Genera el informe histórico para comparar el modelo con referencias simples.",
                    symbol: "clock.arrow.circlepath"
                )
            }
        }
        .nexusCard()
        .frame(maxWidth: .infinity, alignment: .topLeading)
    }

    private var goldProbabilityHistoryCard: some View {
        let points = store.snapshot?.gold?.history?.recentPredictions ?? []
        return VStack(alignment: .leading, spacing: 10) {
            NexusSectionHeader(
                title: "HISTÓRICO DE PROBABILIDAD",
                detail: "últimas \(points.count) evaluaciones",
                help: "Evolución de la probabilidad alcista emitida en vivo. La línea central representa una lectura neutral del 50%."
            )
            if points.count >= 2 {
                Chart(points) { point in
                    if let date = goldPredictionDate(point.capturedAt) {
                        if let probability = point.shortProbability {
                            LineMark(
                                x: .value("Fecha", date),
                                y: .value("Probabilidad", probability),
                                series: .value("Horizonte", "21 sesiones")
                            )
                            .foregroundStyle(by: .value("Horizonte", "21 sesiones"))
                            .interpolationMethod(.catmullRom)
                        }
                        if let probability = point.mediumProbability {
                            LineMark(
                                x: .value("Fecha", date),
                                y: .value("Probabilidad", probability),
                                series: .value("Horizonte", "63 sesiones")
                            )
                            .foregroundStyle(by: .value("Horizonte", "63 sesiones"))
                            .interpolationMethod(.catmullRom)
                        }
                    }
                }
                .chartForegroundStyleScale([
                    "21 sesiones": NexusTheme.accent,
                    "63 sesiones": NexusTheme.warn,
                ])
                .chartYScale(domain: 15...85)
                .chartYAxis {
                    AxisMarks(position: .leading, values: [20, 35, 50, 65, 80]) { value in
                        AxisGridLine()
                        AxisValueLabel { if let number = value.as(Int.self) { Text("\(number)%") } }
                    }
                }
                .chartLegend(position: .top, alignment: .leading)
                .frame(height: 190)
            } else {
                NexusEmptyState(
                    title: "Aún falta otra evaluación",
                    detail: "La serie aparecerá al disponer de dos capturas guardadas en días distintos.",
                    symbol: "chart.xyaxis.line"
                )
            }
            Text("Resultados vencidos: \(store.snapshot?.gold?.history?.settledOutcomes ?? 0). Las probabilidades no equivalen a una orden de entrada.")
                .font(.caption)
                .foregroundStyle(NexusTheme.muted)
        }
        .nexusCard()
    }

    private var hasGoldAblation: Bool {
        let horizons = store.snapshot?.gold?.backtest?.horizons
        return !(horizons?["21"]?.ablation?.isEmpty ?? true) || !(horizons?["63"]?.ablation?.isEmpty ?? true)
    }

    private var goldAblationCard: some View {
        let report = store.snapshot?.gold?.backtest
        return VStack(alignment: .leading, spacing: 12) {
            NexusSectionHeader(
                title: "APORTE REAL POR FAMILIA",
                detail: "prueba de ablación",
                help: "Recalcula el histórico retirando una familia cada vez. Un Brier positivo significa que retirarla empeora el modelo; uno negativo señala posible redundancia."
            )
            ViewThatFits(in: .horizontal) {
                HStack(alignment: .top, spacing: 12) {
                    goldAblationHorizon("21", report: report)
                    goldAblationHorizon("63", report: report)
                }
                VStack(alignment: .leading, spacing: 12) {
                    goldAblationHorizon("21", report: report)
                    goldAblationHorizon("63", report: report)
                }
            }
            Text("Se muestran primero las familias que conviene revisar. Esta prueba detecta redundancia; no autoriza por sí sola a cambiar pesos.")
                .font(.caption)
                .foregroundStyle(NexusTheme.muted)
                .fixedSize(horizontal: false, vertical: true)
        }
        .nexusCard()
        .frame(maxWidth: .infinity, alignment: .topLeading)
    }

    private func goldAblationHorizon(_ key: String, report: GoldBacktestReport?) -> some View {
        let entries = (report?.horizons?[key]?.ablation ?? [:])
            .sorted { ($0.value.deltaBrierVsFull ?? 0) < ($1.value.deltaBrierVsFull ?? 0) }
        return VStack(alignment: .leading, spacing: 8) {
            Text("\(key) SESIONES")
                .font(.caption.weight(.bold))
                .foregroundStyle(NexusTheme.accent)
            ForEach(Array(entries.prefix(5)), id: \.key) { entry in
                HStack(spacing: 8) {
                    Circle()
                        .fill(ablationTone(entry.value.interpretation))
                        .frame(width: 7, height: 7)
                    Text(goldFactorLabel(entry.key))
                        .lineLimit(1)
                    Spacer(minLength: 8)
                    Text("Δ Brier \(signedDecimal(entry.value.deltaBrierVsFull))")
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(ablationTone(entry.value.interpretation))
                }
                .accessibilityElement(children: .combine)
                .accessibilityLabel("\(goldFactorLabel(entry.key)), cambio Brier \(signedDecimal(entry.value.deltaBrierVsFull)), \(entry.value.interpretation ?? "sin clasificación")")
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .topLeading)
        .background(NexusTheme.cardInner, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 10, style: .continuous).stroke(NexusTheme.border, lineWidth: 1))
    }

    private func goldFactorLabel(_ key: String) -> String {
        [
            "inflation": "Inflación", "real_rates": "Tipos reales", "dollar": "Dólar",
            "energy": "Energía", "activity": "Actividad", "liquidity": "Liquidez",
            "risk": "Riesgo", "technical": "Técnica", "official_demand": "Demanda oficial",
            "positioning": "Posicionamiento CFTC",
        ][key] ?? key
    }

    private func ablationTone(_ interpretation: String?) -> Color {
        switch interpretation {
        case "APORTA": return NexusTheme.good
        case "REVISAR": return NexusTheme.bad
        default: return NexusTheme.muted
        }
    }

    private func signedDecimal(_ value: Double?) -> String {
        guard let value else { return "—" }
        return String(format: "%+.4f", value)
    }

    private func goldBacktestHorizon(_ key: String, report: GoldBacktestReport?) -> some View {
        let result = report?.horizons?[key]
        let model = result?.model
        let momentum = result?.baselineMomentum
        let macro = result?.baselineDollarRealYield
        let passed = result?.passesBaselines == true
        return VStack(alignment: .leading, spacing: 7) {
            HStack {
                Text("\(key) SESIONES")
                    .font(.caption.weight(.bold))
                    .foregroundStyle(NexusTheme.accent)
                Spacer()
                Text("\(model?.sampleSize ?? 0) cortes")
                    .font(.caption2.monospacedDigit())
                    .foregroundStyle(NexusTheme.muted)
            }
            NexusKVRow(label: "Brier NEXUS", value: decimal(model?.brierScore, digits: 3))
            NexusKVRow(
                label: "Referencias",
                value: "Mom. \(decimal(momentum?.brierScore, digits: 3)) · Macro \(decimal(macro?.brierScore, digits: 3))"
            )
            NexusKVRow(
                label: "Precisión equilibrada",
                value: percentRatio(model?.balancedAccuracy),
                tone: passed ? NexusTheme.good : NexusTheme.warn
            )
            NexusKVRow(label: "Retorno medio observado", value: formatPct(model?.meanReturnPct))
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .topLeading)
        .background(NexusTheme.cardInner, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .stroke(NexusTheme.border, lineWidth: 1)
        )
        .accessibilityElement(children: .combine)
        .accessibilityLabel(
            "\(key) sesiones, \(model?.sampleSize ?? 0) cortes, Brier \(decimal(model?.brierScore, digits: 3)), precisión equilibrada \(percentRatio(model?.balancedAccuracy))"
        )
    }

    private func backtestPeriod(_ report: GoldBacktestReport?) -> String? {
        guard let start = report?.period?.start, let end = report?.period?.end else { return nil }
        return "\(start.prefix(4))–\(end.prefix(4))"
    }

    private func decimal(_ value: Double?, digits: Int) -> String {
        guard let value else { return "—" }
        return String(format: "%.*f", digits, value)
    }

    private func percentRatio(_ value: Double?) -> String {
        guard let value else { return "—" }
        return String(format: "%.1f%%", value * 100)
    }

    private func goldGroup(_ id: String) -> GoldFactorGroup? {
        store.snapshot?.gold?.outlook?.groups?.first(where: { $0.id == id })
    }

    private func signed(_ value: Double?) -> String {
        guard let value else { return "—" }
        return String(format: "%+.1f", value)
    }

    private func contributionTone(_ value: Double?) -> Color {
        guard let value else { return NexusTheme.muted }
        if abs(value) < 0.05 { return NexusTheme.muted }
        return value > 0 ? NexusTheme.good : NexusTheme.bad
    }

    private func goldStatusLabel(_ status: String?) -> String {
        switch status?.uppercased() {
        case "PRELIMINARY": return "PRELIMINAR"
        case "READY": return "LISTO"
        case .some(let value): return value
        case .none: return "PRELIMINAR"
        }
    }

    private func goldDetailProvenance(_ detail: GoldFactorDetail) -> String? {
        let source = detail.source?.replacingOccurrences(of: "FRED:", with: "FRED · ")
        let date = detail.asOf.map { String($0.prefix(10)) }
        let parts = [source, date].compactMap { value in
            guard let value, !value.isEmpty else { return nil as String? }
            return value
        }
        return parts.isEmpty ? nil : parts.joined(separator: " · ")
    }

    private func shortGoldDate(_ raw: String?) -> String? {
        guard let raw else { return nil }
        return String(raw.prefix(10))
    }

    private func goldPredictionDate(_ raw: String?) -> Date? {
        guard let raw else { return nil }
        return ISO8601DateFormatter.nexus.date(from: raw)
            ?? ISO8601DateFormatter.nexusFractional.date(from: raw)
    }

    private var goldCard: some View {
        let gold = store.snapshot?.gold
        let gld = gold?.GLD
        let signal = gold?.signal
        return VStack(alignment: .leading, spacing: 8) {
            Text("ETF PROXY · GLD")
                .font(.caption.weight(.bold))
                .foregroundStyle(NexusTheme.accent)
            Text(signal?.bias ?? "—")
                .font(.title3.weight(.bold))
                .foregroundStyle(NexusTheme.toneColor(signal?.tone ?? signal?.bias))
            metric("Precio ETF", number(gld?.price, digits: 2))
            metric("MA20 / MA50", "\(number(gld?.ma20, digits: 2)) / \(number(gld?.ma50, digits: 2))")
            MetricBar(label: "Mom 1M", value: gld?.momentum1m, range: -8...8)
            metric("Tipo real", signal?.realRate.map { String(format: "%.2f%%", $0) } ?? "—")
            metric("Fuente tipo real", signal?.realRateSource ?? "—")
            metric("VIX", number(signal?.vix, digits: 1))
            Text(signal?.summary ?? "Sin lectura de oro todavía.")
                .font(.caption)
                .foregroundStyle(NexusTheme.muted)
                .fixedSize(horizontal: false, vertical: true)
            Text("GLD se usa como proxy técnico y para la validación histórica; el gráfico principal muestra XAU/USD spot.")
                .font(.caption)
                .foregroundStyle(NexusTheme.muted)
                .fixedSize(horizontal: false, vertical: true)
        }
        .nexusCard()
        .nexusInteractive(label: "Abrir detalle del oro") { store.showAsset("GLD") }
        .help("Abrir detalle del oro")
    }

    private var relativeCard: some View {
        let signal = store.snapshot?.forex?.signal
        return VStack(alignment: .leading, spacing: 8) {
            Text("RELATIVO EUR VS USD")
                .font(.caption.weight(.bold))
                .foregroundStyle(NexusTheme.accent)
            MetricBar(label: "Dif. 1M", value: signal?.rel1m, range: -5...5)
            MetricBar(label: "Dif. 3M", value: signal?.rel3m, range: -10...10)
            metric("Cambio", formatPct(signal?.relChange))
            Text(signal?.evolution ?? "Sin evolución disponible.")
                .font(.subheadline.weight(.semibold))
            Text(signal?.summary ?? "El sesgo combina tendencia relativa y noticias.")
                .font(.caption)
                .foregroundStyle(NexusTheme.muted)
        }
        .nexusCard()
        .frame(maxWidth: .infinity, alignment: .topLeading)
    }

    private var goldVsDollarCard: some View {
        let gld = store.snapshot?.gold?.GLD
        let dollarMomentum = store.snapshot?.assets?["UUP"]?.momentum1m
        let relative = {
            guard let gold = gld?.momentum1m, let dollar = dollarMomentum else { return nil as Double? }
            return gold - dollar
        }()
        return VStack(alignment: .leading, spacing: 8) {
            NexusSectionHeader(
                title: "GLD vs índice dólar (UUP) · 1M",
                help: "Compara el proxy del oro con un proxy amplio del dólar. Así la lectura coincide con la variable dólar empleada por el modelo."
            )
            MetricBar(label: "GLD 1M", value: gld?.momentum1m, range: -8...8)
            MetricBar(label: "UUP 1M", value: dollarMomentum, range: -8...8)
            MetricBar(label: "Relativo GLD−UUP", value: relative, range: -8...8)
            Text(relative.map { $0 >= 0 ? "GLD gana fuerza relativa frente al índice dólar." : "El índice dólar gana fuerza relativa frente a GLD." } ?? "Sin comparación con el índice dólar todavía.")
                .font(.caption)
                .foregroundStyle(NexusTheme.muted)
                .fixedSize(horizontal: false, vertical: true)
        }
        .nexusCard()
        .nexusInteractive(label: "Abrir detalle del oro") { store.showAsset("GLD") }
        .help("Abrir detalle del oro")
    }

    private var fxHeadlinesCard: some View {
        let allItems = store.snapshot?.forex?.headlines ?? []
        let items = allItems.filter { item in
            let assets = Set(item.linkedAssets ?? [])
            return mode == .gold
                ? !assets.isDisjoint(with: ["GLD", "XAUUSD"])
                : !assets.isDisjoint(with: ["EURUSD", "UUP"])
        }
        return VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .firstTextBaseline) {
                NexusSectionHeader(
                    title: mode == .gold ? "Titulares del oro" : "Titulares de divisas",
                    help: "Coincidencia contextual por activo. No implica causalidad."
                )
                Spacer()
                NexusActionButton(title: "Noticias", systemImage: "newspaper", helpText: "Abrir la pestaña de noticias") {
                    store.selected = .news
                }
            }
            if items.isEmpty {
                Text("No hay titulares de euro, dólar u oro en esta captura.")
                    .font(.caption)
                    .foregroundStyle(NexusTheme.muted)
            } else {
                ForEach(items) { item in
                    Button {
                        selectedHeadline = item
                    } label: {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(headlineTags(item))
                                .font(.caption2.weight(.bold))
                                .foregroundStyle(NexusTheme.accent)
                            Text(item.title)
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(NexusTheme.text)
                                .multilineTextAlignment(.leading)
                                .lineLimit(2)
                            Text(item.source ?? "Fuente")
                                .font(.caption2)
                                .foregroundStyle(NexusTheme.muted)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .help("Leer «\(item.title)»")
                }
            }
        }
        .nexusCard()
    }

    private func headlineTags(_ item: NewsItem) -> String {
        let labels = (item.linkedAssets ?? []).map(headlineAssetLabel)
        return labels.isEmpty ? "Contexto FX/oro" : labels.joined(separator: " · ")
    }

    private func headlineAssetLabel(_ ticker: String) -> String {
        switch ticker {
        case "EURUSD": return "EUR/USD"
        case "XAUUSD": return "Oro spot"
        case "GLD": return "Oro"
        case "UUP": return "Dólar"
        default: return ticker
        }
    }

    @ViewBuilder
    private func headlineReader(_ item: NewsItem) -> some View {
        NavigationStack {
            Group {
                if let raw = item.url, let url = URL(string: raw) {
                    NewsReaderView(url: url)
                } else {
                    Text("Este titular no tiene enlace.")
                        .font(.subheadline)
                        .foregroundStyle(NexusTheme.muted)
                        .padding()
                }
            }
            .navigationTitle(item.source ?? "Noticia")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cerrar") { selectedHeadline = nil }
                        .keyboardShortcut(.cancelAction)
                }
            }
        }
        .frame(minWidth: 720, minHeight: 520)
    }

    private var fxPlanCard: some View {
        let plan = store.snapshot?.forex?.plan
        return NexusStanceCard(
            stance: plan?.stance ?? "ESPERAR",
            buy: plan?.buy ?? "Nada ahora",
            verdict: plan?.verdict ?? "Esperar a una lectura completa del par y de la operativa.",
            doing: plan?.doing ?? "Confirmar tendencia, relativo y que Resumen autorice entradas.",
            avoiding: plan?.avoiding ?? "No operar por un dato aislado ni contradecir un bloqueo.",
            changes: plan?.changes,
            help: "Veredicto del par EUR/USD. El oro es contexto. Si Resumen está pausado, no hay compra."
        )
    }

    private var fxCalendarCard: some View {
        let events = mode == .gold
            ? (store.snapshot?.calendar?.goldUpcoming ?? [])
            : (store.snapshot?.calendar?.fxUpcoming ?? [])
        return VStack(alignment: .leading, spacing: 8) {
            NexusSectionHeader(
                title: mode == .gold ? "Calendario del oro · 30 días" : "Calendario FX · 72h",
                help: mode == .gold
                    ? "Publicaciones oficiales de FOMC, CPI/PCE y NFP del próximo mes; el respaldo manual se etiqueta como estimado. Solo la ventana operativa configurada puede bloquear señales."
                    : "FOMC, CPI, NFP y BCE en las próximas 72 horas. Un bloqueo activo sigue mandando sobre la operativa."
            )
            if events.isEmpty {
                Text(mode == .gold
                    ? "No hay publicaciones de FOMC, CPI/PCE o NFP fechadas para los próximos 30 días."
                    : "No hay FOMC, CPI, NFP o BCE en las próximas 72 horas.")
                    .font(.caption)
                    .foregroundStyle(NexusTheme.muted)
            } else {
                ForEach(events) { event in
                    HStack(alignment: .top, spacing: 8) {
                        Circle()
                            .fill(event.blocksSignals == true ? NexusTheme.bad : NexusTheme.warn)
                            .frame(width: 7, height: 7)
                            .padding(.top, 5)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(event.title ?? "Evento")
                                .font(.caption.weight(.semibold))
                                .lineLimit(2)
                            Text(calendarWhen(event))
                                .font(.caption2)
                                .foregroundStyle(NexusTheme.muted)
                        }
                        Spacer(minLength: 4)
                        Text(event.impact ?? "")
                            .font(.caption2.weight(.bold))
                            .foregroundStyle(event.blocksSignals == true ? NexusTheme.bad : NexusTheme.warn)
                    }
                }
            }
        }
        .nexusCard()
    }

    private func digestTone(_ value: Double?) -> Color {
        guard let value else { return NexusTheme.muted }
        if abs(value) < 0.0001 { return NexusTheme.muted }
        return value >= 0 ? NexusTheme.good : NexusTheme.bad
    }

    private var fxPipLabel: String {
        guard let pips = digest?.eurusd?.pips else { return "—" }
        let sign = pips > 0 ? "+" : ""
        return String(format: "%@%.0f pips", sign, pips)
    }

    private func digestChangeLabel(_ change: DigestChange?) -> String {
        if change?.changed == true, let from = change?.from, let to = change?.to {
            return "\(from) → \(to)"
        }
        return change?.to ?? "—"
    }

    private func digestMetric(_ title: String, _ value: String, _ tone: Color) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(LocalizedStringKey(title))
                .font(.caption2.weight(.bold))
                .foregroundStyle(NexusTheme.muted)
            Text(value)
                .font(.caption.weight(.semibold))
                .foregroundStyle(tone)
                .lineLimit(2)
                .minimumScaleFactor(0.7)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func calendarWhen(_ event: CalendarEventItem) -> String {
        var base = "fecha estimada"
        if let hours = event.hoursUntil {
            if hours < 1 { base = "en \(Int(hours * 60)) min" }
            else if hours < 24 { base = "en \(Int(hours.rounded())) h" }
            else { base = "en \(Int((hours / 24).rounded())) d" }
        } else if let when = event.whenUtc {
            base = when
        }
        let source = (event.source ?? "").lowercased()
        if source.contains("estimado") || source.contains("manual") || event.estimated == true {
            return "\(base) · hora estimada"
        }
        if source.contains("rss") || source.contains("myfxbook") {
            return "\(base) · horario RSS"
        }
        return base
    }

    private var forexNewsCard: some View {
        let news = store.snapshot?.forex?.signal?.news
        return VStack(alignment: .leading, spacing: 7) {
            NexusSectionHeader(title: "SESGO DE NOTICIAS")
            NexusKVRow(label: "Euro", value: number(news?.eurScore, digits: 1), tone: NexusTheme.toneColor(news?.expectation))
            NexusKVRow(label: "Dólar", value: number(news?.usdScore, digits: 1))
            Text(news?.expectation ?? "Sin lectura de titulares.")
                .font(.caption)
                .foregroundStyle(NexusTheme.muted)
        }
        .nexusCard()
        .frame(maxWidth: .infinity, alignment: .topLeading)
    }

    private var forexRangeCard: some View {
        let eur = store.snapshot?.forex?.EURUSD
        let distance = eur?.price.flatMap { price in eur?.ma20.map { (price / $0 - 1) * 100 } }
        return VStack(alignment: .leading, spacing: 7) {
            NexusSectionHeader(title: "POSICIÓN TÉCNICA")
            NexusKVRow(label: "Vs MA20", value: formatPct(distance), tone: (distance ?? 0) >= 0 ? NexusTheme.good : NexusTheme.bad)
            NexusKVRow(label: "Vol. 20d", value: formatPct(eur?.volatility20d))
            Text("Evita perseguir el precio si se aleja demasiado de su media.")
                .font(.caption)
                .foregroundStyle(NexusTheme.muted)
        }
        .nexusCard()
        .frame(maxWidth: .infinity, alignment: .topLeading)
    }

    private func metric(_ label: String, _ value: String) -> some View {
        HStack {
            Text(LocalizedStringKey(label)).foregroundStyle(NexusTheme.muted)
            Spacer()
            Text(value).fontWeight(.semibold)
        }
        .font(.caption)
    }

    private func number(_ value: Double?, digits: Int) -> String {
        guard let value else { return "—" }
        return String(format: "%.\(digits)f", value)
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
}

struct GoldContributionBar: View {
    let value: Double?
    let label: String

    var body: some View {
        HStack(spacing: 5) {
            Text(label)
                .font(.caption2.weight(.bold))
                .foregroundStyle(NexusTheme.muted)
            Image(systemName: symbol)
                .font(.caption2)
                .foregroundStyle(tone)
            ProgressView(value: min(abs(value ?? 0), 22), total: 22)
                .tint(tone)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(label), contribución \(spokenValue)")
    }

    private var symbol: String {
        guard let value else { return "minus" }
        if value > 0.05 { return "arrow.up.right" }
        if value < -0.05 { return "arrow.down.right" }
        return "minus"
    }

    private var tone: Color {
        guard let value else { return NexusTheme.muted }
        if abs(value) <= 0.05 { return NexusTheme.muted }
        return value > 0 ? NexusTheme.good : NexusTheme.bad
    }

    private var spokenValue: String {
        guard let value else { return "no disponible" }
        return String(format: "%+.1f puntos", value)
    }
}

struct MetricBar: View {
    let label: String
    let value: Double?
    let range: ClosedRange<Double>

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(LocalizedStringKey(label)).foregroundStyle(NexusTheme.muted)
                Spacer()
                Text(formatPct(value))
                    .foregroundStyle(color)
            }
            .font(.caption)
            GeometryReader { proxy in
                ZStack(alignment: .leading) {
                    Capsule().fill(.white.opacity(0.10))
                    Capsule()
                        .fill(color)
                        .frame(width: max(3, proxy.size.width * progress))
                }
            }
            .frame(height: 4)
        }
    }

    private var progress: Double {
        guard let value else { return 0 }
        return min(1, max(0, (value - range.lowerBound) / (range.upperBound - range.lowerBound)))
    }

    private var color: Color {
        guard let value else { return NexusTheme.muted }
        return value >= 0 ? NexusTheme.good : NexusTheme.bad
    }
}


struct PaperView: View {
    @EnvironmentObject private var store: NexusStore

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: NexusLayout.spacing) {
                let paper = store.snapshot?.paper
                VStack(alignment: .leading, spacing: 6) {
                    Text("QUÉ ES PAPER")
                        .font(.caption.weight(.bold))
                        .foregroundStyle(NexusTheme.accent)
                    Text("Una simulación: aplica las decisiones de NEXUS a una cartera ficticia. No representa dinero real ni una recomendación de ejecución.")
                        .font(.subheadline)
                    Text("Sirve para comprobar si las señales habrían protegido o hecho crecer la cartera.")
                        .font(.caption)
                        .foregroundStyle(NexusTheme.muted)
                    Text("Se actualiza al reevaluar con persistencia y rebalancea a la asignación operativa, sin comisiones ni ejecución real.")
                        .font(.caption)
                        .foregroundStyle(NexusTheme.muted)
                }
                .nexusCard()
                .frame(maxWidth: .infinity, minHeight: 130, alignment: .topLeading)

                NexusAdaptiveGrid(minimumWidth: 190) {
                    metric("Valor simulado", money(paper?.portfolio?.currentValue), "inicio \(money(paper?.portfolio?.startingValue))")
                    metric("Resultado NEXUS", formatPct(paper?.totalReturnPct), "rendimiento acumulado")
                    metric("Comparación SPY", benchmarkLabel(paper), benchmarkHint(paper))
                    metric("Efectivo", paper?.portfolio?.cashPct.map { "\($0)%" } ?? "—", "capital sin invertir")
                }

                NexusAdaptiveGrid(minimumWidth: 210) {
                    metric("Posiciones", "\(paper?.portfolio?.holdings?.count ?? 0)", "activos en cartera")
                    metric("Mayor peso", largestHoldingLabel(paper), "concentración actual")
                    metric("Riesgo aprox.", portfolioRisk(paper), "volatilidad ponderada")
                    metric("Última actualización", shortUpdate(paper?.portfolio?.lastUpdate), "snapshot aplicado")
                }
                NexusAdaptiveGrid(minimumWidth: 210) {
                    metric("Caída máxima", formatPct(paper?.riskSummary?.maxDrawdownPct), "desde el máximo simulado")
                    metric(
                        "Exposición principal",
                        paper?.riskSummary?.largestExposure?.asset ?? "—",
                        "\(String(format: "%.0f", paper?.riskSummary?.largestExposure?.weightPct ?? 0))% del valor estimado"
                    )
                    metric("Concentración", paper?.riskSummary?.concentrationHhi.map { String(format: "%.0f/100", $0) } ?? "—", "100 = un solo activo")
                }
                if let scenarios = paper?.riskSummary?.scenarios, !scenarios.isEmpty {
                    VStack(alignment: .leading, spacing: 6) {
                        NexusSectionHeader(title: "ESCENARIOS ORIENTATIVOS", help: "Estimaciones mecánicas sobre la asignación actual; no predicciones.")
                        ForEach(scenarios) { scenario in
                            NexusKVRow(label: scenario.label ?? "Escenario", value: formatPct(scenario.portfolioPct), tone: (scenario.portfolioPct ?? 0) < 0 ? NexusTheme.bad : NexusTheme.good)
                        }
                    }
                    .nexusCard()
                }

                if let warnings = paper?.dataWarnings, !warnings.isEmpty {
                    VStack(alignment: .leading, spacing: 5) {
                        Label("Comparación limitada", systemImage: "exclamationmark.triangle.fill")
                            .font(.subheadline.weight(.bold))
                            .foregroundStyle(NexusTheme.warn)
                        ForEach(warnings, id: \.self) { warning in
                            Text(warning)
                                .font(.caption)
                                .foregroundStyle(NexusTheme.muted)
                        }
                    }
                    .nexusCard()
                }

                paperChart(paper)

                NexusAdaptiveGrid(minimumWidth: 340) {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("DECISIÓN APLICADA")
                            .font(.caption.weight(.bold))
                            .foregroundStyle(NexusTheme.accent)
                        Text(paper?.portfolio?.lastAction ?? "—")
                            .font(.title2.weight(.bold))
                            .foregroundStyle(NexusTheme.toneColor(paper?.portfolio?.lastAction))
                        Text(paper?.portfolio?.lastScore.map { "Score \($0)/100" } ?? "Score —/100")
                            .foregroundStyle(NexusTheme.muted)
                        Text(paperGuidance(paper?.portfolio?.lastAction))
                            .font(.subheadline)
                    }
                    .nexusCard()
                    .frame(maxWidth: .infinity, minHeight: 180, alignment: .topLeading)

                    VStack(alignment: .leading, spacing: 8) {
                        Text("ASIGNACIÓN ACTUAL")
                            .font(.caption.weight(.bold))
                            .foregroundStyle(NexusTheme.accent)
                        let allocation = paper?.trades?.last?.allocation ?? store.snapshot?.decision?.allocation ?? [:]
                        ForEach(allocation.sorted(by: { $0.value > $1.value }), id: \.key) { key, value in
                            HStack {
                                Text(key).frame(width: 48, alignment: .leading)
                                ProgressView(value: Double(value), total: 100)
                                    .tint(key == "CASH" ? NexusTheme.good : NexusTheme.accent)
                                Text("\(value)%").frame(width: 38, alignment: .trailing)
                            }
                            .font(.caption)
                        }
                    }
                    .nexusCard()
                    .frame(maxWidth: .infinity, minHeight: 180, alignment: .topLeading)
                }

                VStack(alignment: .leading, spacing: 8) {
                    Text("ÚLTIMOS CAMBIOS SIMULADOS")
                        .font(.caption.weight(.bold))
                        .foregroundStyle(NexusTheme.accent)
                    let changed = (paper?.trades ?? []).filter { $0.actionChanged == true }.suffix(8).reversed()
                    if changed.isEmpty {
                        Text("No hay cambios de asignación recientes.")
                            .foregroundStyle(NexusTheme.muted)
                    } else {
                        ForEach(Array(changed)) { trade in
                            HStack {
                                Text(String((trade.capturedAt ?? "—").prefix(16)).replacingOccurrences(of: "T", with: " "))
                                    .foregroundStyle(NexusTheme.muted)
                                Text(trade.action ?? "—").fontWeight(.semibold)
                                Spacer()
                                Text("Score \(trade.score ?? 0)")
                                Text(money(trade.portfolioValue))
                            }
                            .font(.caption)
                            Divider().opacity(0.10)
                        }
                    }
                }
                .nexusCard()

                if let track = store.snapshot?.trackRecord {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("VALIDACIÓN HISTÓRICA")
                            .font(.caption.weight(.bold))
                            .foregroundStyle(NexusTheme.accent)
                        if let message = track.message {
                            Text(message)
                                .font(.subheadline)
                                .foregroundStyle(NexusTheme.muted)
                        } else {
                            HStack(spacing: 24) {
                                trackMetric("Señales de compra", track.macroBuyHitRatePct, track.macroBuyCount)
                                trackMetric("Señales defensivas", track.defensiveHitRatePct, track.defensiveCount)
                                VStack(alignment: .leading, spacing: 3) {
                                    Text("Horizonte").font(.caption).foregroundStyle(NexusTheme.muted)
                                    Text("\(track.forwardDays ?? 5) días").font(.headline)
                                    Text("\(track.sampleSize ?? 0) muestras").font(.caption2).foregroundStyle(NexusTheme.muted)
                                }
                            }
                        }
                    }
                    .nexusCard()
                    .frame(maxWidth: .infinity, minHeight: 120, alignment: .topLeading)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(20)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .scrollBounceBehavior(.basedOnSize)
    }

    private func metric(_ title: String, _ value: String, _ hint: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(LocalizedStringKey(title)).font(.caption).foregroundStyle(NexusTheme.muted)
            Text(value).font(.title2.monospacedDigit().weight(.bold))
            Text(hint).font(.caption2).foregroundStyle(NexusTheme.muted)
        }
        .nexusCard()
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    @ViewBuilder
    private func paperChart(_ paper: PaperBlock?) -> some View {
        let points = equityPoints(paper)
        VStack(alignment: .leading, spacing: 8) {
            NexusSectionHeader(
                title: "Evolución de la cartera",
                detail: "base 100",
                help: "Normaliza ambas series a 100 en la primera observación visible. No incluye comisiones ni deslizamiento."
            )
            if points.filter({ $0.series == "NEXUS" }).count >= 2 {
                Chart(points) { point in
                    LineMark(
                        x: .value("Fecha", point.date),
                        y: .value("Índice", point.value)
                    )
                    .foregroundStyle(by: .value("Serie", point.series))
                    .interpolationMethod(.catmullRom)

                    if point.series == "NEXUS" {
                        AreaMark(
                            x: .value("Fecha", point.date),
                            yStart: .value("Base", 100),
                            yEnd: .value("Índice", point.value)
                        )
                        .foregroundStyle(
                            LinearGradient(
                                colors: [NexusTheme.accent.opacity(0.20), .clear],
                                startPoint: .top,
                                endPoint: .bottom
                            )
                        )
                    }
                }
                .chartForegroundStyleScale([
                    "NEXUS": NexusTheme.accent,
                    "SPY": NexusTheme.muted,
                ])
                .chartLegend(position: .top, alignment: .leading)
                .chartYAxis {
                    AxisMarks(position: .leading)
                }
                .frame(height: 240)
                if paper?.benchmarkValid == false {
                    Label("SPY se compara solo desde el primer punto visible; el alpha histórico sigue desactivado por baseline inválida.", systemImage: "exclamationmark.triangle")
                        .font(.caption)
                        .foregroundStyle(NexusTheme.warn)
                }
            } else {
                NexusEmptyState(
                    title: "Aún no hay serie suficiente",
                    detail: "Se necesitan al menos dos reevaluaciones persistidas para dibujar la evolución.",
                    symbol: "chart.xyaxis.line"
                )
            }
        }
        .nexusCard()
        .frame(maxWidth: .infinity, alignment: .topLeading)
    }

    private func equityPoints(_ paper: PaperBlock?) -> [PaperEquityPoint] {
        let trades = paper?.trades ?? []
        let dated = trades.compactMap { trade -> (Date, PaperTrade)? in
            guard let raw = trade.capturedAt,
                  let date = ISO8601DateFormatter.nexus.date(from: raw)
                    ?? ISO8601DateFormatter.nexusFractional.date(from: raw) else { return nil }
            return (date, trade)
        }
        guard let nexusBase = dated.compactMap({ $0.1.portfolioValue }).first,
              nexusBase > 0 else { return [] }

        var result = dated.compactMap { date, trade -> PaperEquityPoint? in
            guard let value = trade.portfolioValue, value > 0 else { return nil }
            return PaperEquityPoint(date: date, value: value / nexusBase * 100, series: "NEXUS")
        }

        if let benchmarkBase = dated.compactMap({ $0.1.benchmarkValue }).first,
           benchmarkBase > 0 {
            result += dated.compactMap { date, trade -> PaperEquityPoint? in
                guard let value = trade.benchmarkValue, value > 0 else { return nil }
                return PaperEquityPoint(date: date, value: value / benchmarkBase * 100, series: "SPY")
            }
        }
        return result
    }

    private func money(_ value: Double?) -> String {
        guard let value else { return "—" }
        return value.formatted(.currency(code: "USD").precision(.fractionLength(0)))
    }

    private func largestHoldingLabel(_ paper: PaperBlock?) -> String {
        guard let largest = paper?.portfolio?.holdings?.max(by: { $0.value < $1.value }) else { return "—" }
        return "\(largest.key) \(String(format: "%.0f%%", largest.value))"
    }

    private func portfolioRisk(_ paper: PaperBlock?) -> String {
        guard let holdings = paper?.portfolio?.holdings, !holdings.isEmpty else { return "—" }
        let risk = holdings.reduce(0.0) { total, item in
            total + item.value / 100 * (store.snapshot?.assets?[item.key]?.volatility20d ?? 0)
        }
        return formatPct(risk)
    }

    private func shortUpdate(_ raw: String?) -> String {
        guard let raw else { return "—" }
        return String(raw.prefix(10))
    }

    private func benchmarkLabel(_ paper: PaperBlock?) -> String {
        guard paper?.benchmarkValid != false,
              let value = paper?.benchmarkReturnPct,
              abs(value) < 200 else { return "No comparable" }
        return formatPct(value)
    }

    private func benchmarkHint(_ paper: PaperBlock?) -> String {
        guard paper?.benchmarkValid != false,
              let value = paper?.benchmarkReturnPct,
              abs(value) < 200 else {
            return "baseline histórico inválido"
        }
        return "SPY comprar y mantener"
    }

    private func paperGuidance(_ action: String?) -> String {
        let value = (action ?? "").uppercased()
        if value.contains("NO ABRIR") { return "La simulación conserva la asignación defensiva y no abre posiciones nuevas." }
        if value.contains("COMPRAR PARCIAL") { return "La simulación aumenta exposición de forma limitada." }
        if value.contains("COMPRAR") { return "La simulación aplica la asignación de riesgo recomendada." }
        return "La simulación mantiene la cartera sin cambios relevantes."
    }

    private func trackMetric(_ title: String, _ rate: Double?, _ count: Int?) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(LocalizedStringKey(title)).font(.caption).foregroundStyle(NexusTheme.muted)
            Text(rate.map { String(format: "%.1f%%", $0) } ?? "—")
                .font(.headline.monospacedDigit())
            Text("\(count ?? 0) observaciones").font(.caption2).foregroundStyle(NexusTheme.muted)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

private struct PaperEquityPoint: Identifiable {
    var id: String { "\(series)-\(date.timeIntervalSince1970)" }
    let date: Date
    let value: Double
    let series: String
}

struct ChartPlotTapOverlay: View {
    let proxy: ChartProxy
    @Binding var selectedDate: Date?

    var body: some View {
        GeometryReader { geo in
            let plotRect = proxy.plotFrame.map { geo[$0] } ?? geo.frame(in: .local)
            Color.clear
                .contentShape(Rectangle())
                .gesture(
                    SpatialTapGesture()
                        .onEnded { event in
                            guard plotRect.contains(event.location) else { return }
                            if let date: Date = proxy.value(atX: event.location.x, as: Date.self) {
                                selectedDate = date
                            }
                        }
                )
        }
    }
}
