import SwiftUI
import Charts

struct HistoryView: View {
    @EnvironmentObject private var store: NexusStore
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
                        withAnimation(.easeInOut(duration: 0.15)) {
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
    @EnvironmentObject private var store: NexusStore
    @State private var selectedHeadline: NewsItem?

    var body: some View {
        NexusPage {
            let fx = store.snapshot?.forex
            let gold = store.snapshot?.gold
            let gld = gold?.GLD
            exchangeRateStrip
            if store.snapshot?.fxAlignment?.conflict == true {
                fxAlignmentNotice
            }
            fxPlanCard
            NexusKPIStrip(items: [
                NexusKPI(title: "EUR/USD", value: fx?.EURUSD?.price.map { String(format: "%.4f", $0) } ?? "—", hint: fx?.signal?.eurTrend ?? "sin tendencia", tone: NexusTheme.toneColor(fx?.signal?.action)),
                NexusKPI(title: "GLD", value: number(gld?.price, digits: 2), hint: gold?.signal?.bias ?? "1M \(formatPct(gld?.momentum1m))", tone: NexusTheme.toneColor(gold?.signal?.tone ?? gold?.signal?.bias)),
                NexusKPI(title: "ACCIÓN FX", value: fx?.signal?.action ?? "—", hint: "confianza \(fx?.signal?.confidence ?? "—")", tone: NexusTheme.toneColor(fx?.signal?.action)),
                NexusKPI(
                    title: "SESGO ORO",
                    value: gold?.signal?.bias ?? "—",
                    hint: "confianza \(gold?.signal?.confidence ?? "—")",
                    tone: NexusTheme.toneColor(gold?.signal?.tone ?? gold?.signal?.bias),
                    help: "Combina GLD frente al dólar (UUP), tipos reales (10Y menos IPC) y VIX. No es una orden."
                ),
            ])
            sparklineStrip
            NexusResponsiveGrid(wideColumns: 2, mediumColumns: 1) {
                euroCard
                goldCard
            }
            NexusResponsiveGrid(wideColumns: 2, mediumColumns: 1) {
                dollarCard
                relativeCard
            }
            NexusResponsiveGrid(wideColumns: 2, mediumColumns: 1) {
                goldVsDollarCard
                fxHeadlinesCard
            }
            NexusResponsiveGrid(wideColumns: 2, mediumColumns: 1) {
                forexNewsCard
                forexRangeCard
            }
            fxDigestCard
            fxCalendarCard
        }
        .sheet(item: $selectedHeadline) { item in
            headlineReader(item)
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
            .onTapGesture { store.showAsset("EURUSD") }
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
            .onTapGesture { store.showAsset("EURUSD") }
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
                help: "Compara EUR/USD, GLD y el sesgo con la última evaluación persistida. No es una orden."
            )
            Text(digest?.headline ?? "Sin comparación todavía")
                .font(.title3.weight(.bold))
            Text(digest?.summary ?? "Aún no hay una evaluación anterior.")
                .font(.subheadline)
                .foregroundStyle(NexusTheme.muted)
                .fixedSize(horizontal: false, vertical: true)

            HStack(spacing: 16) {
                digestMetric("EUR/USD", digest?.eurusd?.label ?? fxPipLabel, digestTone(digest?.eurusd?.pips))
                digestMetric("GLD", digest?.gld?.label ?? formatDelta(digest?.gld?.delta), digestTone(digest?.gld?.delta))
                digestMetric("SEÑAL FX", digest?.forexAction?.label ?? digestChangeLabel(digest?.forexAction), digest?.forexAction?.changed == true ? NexusTheme.warn : NexusTheme.muted)
                digestMetric("ORO", digest?.goldBias?.label ?? digestChangeLabel(digest?.goldBias), digest?.goldBias?.changed == true ? NexusTheme.warn : NexusTheme.muted)
            }
            if digest?.hasPrior == true {
                Text("Ref. \(relativeAge(from: digest?.baselineCapturedAt))")
                    .font(.caption2)
                    .foregroundStyle(NexusTheme.muted)
            }
        }
        .nexusCard()
    }

    private var sparklineStrip: some View {
        LazyVStack(spacing: NexusLayout.spacing) {
            NexusSparklineCard(
                title: "EUR/USD",
                help: "Intervalo y rango independientes, zoom/pan, selección continua y titulares ligados al par. Ficha abre el inspector.",
                points: store.snapshot?.sparklines?["EURUSD"] ?? [],
                showRelative: false,
                minHeight: 220,
                valueDigits: 4,
                ticker: "EURUSD",
                news: newsLinked(to: "EURUSD", items: store.snapshot?.news?.items ?? []),
                onTap: { store.showAsset("EURUSD") },
                onOpenNews: { item in
                    store.selectedNewsID = item.id
                    store.selected = .news
                }
            )
            NexusSparklineCard(
                title: "GLD",
                help: "Intervalo y rango independientes, zoom/pan, selección continua y titulares ligados al metal.",
                points: store.snapshot?.sparklines?["GLD"] ?? [],
                minHeight: 220,
                valueDigits: 2,
                ticker: "GLD",
                news: newsLinked(to: "GLD", items: store.snapshot?.news?.items ?? []),
                spyPoints: store.snapshot?.sparklines?["SPY"] ?? [],
                onTap: { store.showAsset("GLD") },
                onOpenNews: { item in
                    store.selectedNewsID = item.id
                    store.selected = .news
                }
            )
        }
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
        .contentShape(Rectangle())
        .onTapGesture { store.showAsset("EURUSD") }
        .help("Abrir detalle de EUR/USD")
    }

    private var dollarCard: some View {
        let fx = store.snapshot?.forex
        let uup = store.snapshot?.assets?["UUP"]
        return VStack(alignment: .leading, spacing: 8) {
            Text("DÓLAR (UUP)")
                .font(.caption.weight(.bold))
                .foregroundStyle(NexusTheme.accent)
            metric("Spot", number(uup?.price, digits: 2))
            metric("MA20 / MA50", "\(number(uup?.ma20, digits: 2)) / \(number(uup?.ma50, digits: 2))")
            metric("Tendencia", fx?.signal?.usdTrend ?? "—")
            MetricBar(label: "Mom 1M", value: uup?.momentum1m, range: -5...5)
            MetricBar(label: "Mom 3M", value: uup?.momentum3m, range: -10...10)
            Text(fx?.dual?["usd_view"] ?? "—")
                .font(.caption)
                .foregroundStyle(NexusTheme.muted)
        }
        .nexusCard()
        .frame(maxWidth: .infinity, alignment: .topLeading)
        .contentShape(Rectangle())
        .onTapGesture { store.showAsset("UUP") }
        .help("Abrir detalle del dólar")
    }

    private var goldCard: some View {
        let gold = store.snapshot?.gold
        let gld = gold?.GLD
        let signal = gold?.signal
        return VStack(alignment: .leading, spacing: 8) {
            Text(gold?.label ?? "ORO (GLD)")
                .font(.caption.weight(.bold))
                .foregroundStyle(NexusTheme.accent)
            Text(signal?.bias ?? "—")
                .font(.title3.weight(.bold))
                .foregroundStyle(NexusTheme.toneColor(signal?.tone ?? signal?.bias))
            metric("Spot", number(gld?.price, digits: 2))
            metric("MA20 / MA50", "\(number(gld?.ma20, digits: 2)) / \(number(gld?.ma50, digits: 2))")
            MetricBar(label: "Mom 1M", value: gld?.momentum1m, range: -8...8)
            metric("Tipo real", signal?.realRate.map { String(format: "%.2f%%", $0) } ?? "—")
            metric("VIX", number(signal?.vix, digits: 1))
            Text(signal?.summary ?? "Sin lectura de oro todavía.")
                .font(.caption)
                .foregroundStyle(NexusTheme.muted)
                .fixedSize(horizontal: false, vertical: true)
        }
        .nexusCard()
        .contentShape(Rectangle())
        .onTapGesture { store.showAsset("GLD") }
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
        let uup = store.snapshot?.assets?["UUP"]
        let signal = store.snapshot?.gold?.signal
        return VStack(alignment: .leading, spacing: 8) {
            NexusSectionHeader(
                title: "GLD vs dólar · 1M",
                help: "Momentum a 1 mes de GLD y UUP, y la diferencia. El oro fuerte con dólar fuerte no se lee igual que con dólar débil."
            )
            MetricBar(label: "GLD 1M", value: gld?.momentum1m, range: -8...8)
            MetricBar(label: "Dólar (UUP) 1M", value: uup?.momentum1m, range: -8...8)
            MetricBar(label: "Relativo GLD−UUP", value: signal?.vsDollar1m, range: -8...8)
            Text(signal?.vsDollarNote ?? "Sin comparación con el dólar todavía.")
                .font(.caption)
                .foregroundStyle(NexusTheme.muted)
                .fixedSize(horizontal: false, vertical: true)
        }
        .nexusCard()
        .contentShape(Rectangle())
        .onTapGesture { store.showAsset("GLD") }
        .help("Abrir detalle del oro")
    }

    private var fxHeadlinesCard: some View {
        let items = store.snapshot?.forex?.headlines ?? []
        return VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .firstTextBaseline) {
                NexusSectionHeader(
                    title: "Titulares EUR / USD / oro",
                    help: "Coincidencia contextual con euro, dólar u oro. No implica causalidad."
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
        let events = store.snapshot?.calendar?.fxUpcoming ?? []
        return VStack(alignment: .leading, spacing: 8) {
            NexusSectionHeader(
                title: "Calendario FX y oro · 72h",
                help: "FOMC, CPI, NFP y BCE en las próximas 72 horas. Un bloqueo activo sigue mandando sobre la operativa."
            )
            if events.isEmpty {
                Text("No hay FOMC, CPI, NFP o BCE en las próximas 72 horas.")
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
            Text(title)
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
            Text(label).foregroundStyle(NexusTheme.muted)
            Spacer()
            Text(value).fontWeight(.semibold)
        }
        .font(.caption)
    }

    private func number(_ value: Double?, digits: Int) -> String {
        guard let value else { return "—" }
        return String(format: "%.\(digits)f", value)
    }
}

struct MetricBar: View {
    let label: String
    let value: Double?
    let range: ClosedRange<Double>

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(label).foregroundStyle(NexusTheme.muted)
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
            Text(title).font(.caption).foregroundStyle(NexusTheme.muted)
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
            Text(title).font(.caption).foregroundStyle(NexusTheme.muted)
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
