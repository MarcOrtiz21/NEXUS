import SwiftUI
import Charts

struct HistoryView: View {
    @EnvironmentObject private var store: NexusStore
    @State private var periodDays = 30
    @State private var selectedPointID: String?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: NexusLayout.spacing) {
                VStack(alignment: .leading, spacing: 5) {
                    NexusSectionHeader(
                        title: "Qué significa esta pantalla",
                        help: "El historial se guarda al reevaluar con persistencia. No representa velas de mercado continuas."
                    )
                    Text("Registra cómo ha cambiado la recomendación. “Macro” refleja los datos; “Operativa” añade bloqueos de calendario y riesgo.")
                        .font(.subheadline)
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
                                    if let delta = mover.rankDelta, delta != 0 {
                                        Text(delta > 0 ? "↑\(delta) puestos" : "↓\(abs(delta)) puestos")
                                            .foregroundStyle(delta > 0 ? NexusTheme.good : NexusTheme.bad)
                                    }
                                }
                                .font(.caption)
                            }
                        }
                        if attribution.rationale?.changed == true,
                           let rationale = attribution.rationale?.to {
                            DisclosureGroup("Racional actualizado") {
                                Text(rationale)
                                    .font(.caption)
                                    .foregroundStyle(NexusTheme.muted)
                                    .padding(.top, 4)
                            }
                            .font(.caption.weight(.semibold))
                        }
                        Text(attribution.note ?? "Atribución descriptiva entre snapshots; no implica causalidad.")
                            .font(.caption2)
                            .foregroundStyle(NexusTheme.muted)
                    }
                    .nexusCard()
                }

                Picker("Periodo", selection: $periodDays) {
                    Text("7 días").tag(7)
                    Text("30 días").tag(30)
                    Text("3 meses").tag(90)
                }
                .pickerStyle(.segmented)
                .frame(maxWidth: 420)

                NexusAdaptiveGrid(minimumWidth: 170) {
                    NexusSummaryMetricCard(title: "Muestras", value: "\(filteredTimeline.count)", hint: "evaluaciones del periodo")
                    NexusSummaryMetricCard(title: "Score medio", value: number(periodAverage), hint: "convicción promedio", help: "Media del score en el periodo seleccionado.")
                    NexusSummaryMetricCard(title: "Rango", value: periodRange, hint: "mínimo y máximo")
                    NexusSummaryMetricCard(title: "Cambios", value: "\(filteredEvents.count)", hint: "cambios operativos")
                }

                NexusAdaptiveGrid(minimumWidth: 190) {
                    historyReturnCard("SPY", help: "Variación entre el primer y último punto persistido del periodo.")
                    historyReturnCard("GLD", help: "Variación entre el primer y último punto persistido del periodo.")
                    historyReturnCard("EURUSD", help: "Variación entre el primer y último punto persistido del periodo.")
                }

                VStack(alignment: .leading, spacing: 8) {
                    NexusSectionHeader(
                        title: "Evolución del score",
                        help: "El score mide convicción, no rentabilidad. La línea une evaluaciones persistidas."
                    )
                    if filteredTimeline.count >= 2 {
                        Chart(filteredTimeline) { point in
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
                        .chartYScale(domain: 0...100)
                        .frame(height: 190)
                    } else {
                        Text("Se necesitan al menos dos evaluaciones en este periodo.")
                            .font(.caption)
                            .foregroundStyle(NexusTheme.muted)
                            .frame(maxWidth: .infinity, minHeight: 100)
                    }
                }
                .nexusCard()

                VStack(alignment: .leading, spacing: 8) {
                    NexusSectionHeader(title: "Cambios de decisión")
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
                                            Image(systemName: selectedPointID == point.id ? "chevron.up" : "chevron.down")
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
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(20)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .scrollBounceBehavior(.basedOnSize)
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

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: NexusLayout.spacing) {
                forexPlanCard
                NexusAdaptiveGrid(minimumWidth: 280) {
                    exchangeCard
                    euroCard
                    dollarCard
                }
                NexusAdaptiveGrid(minimumWidth: 340) {
                    goldCard
                    relativeCard
                }
                NexusAdaptiveGrid(minimumWidth: 240) {
                    forexMacroCard
                    forexNewsCard
                    forexRangeCard
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(20)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .scrollBounceBehavior(.basedOnSize)
    }

    private var exchangeCard: some View {
        let fx = store.snapshot?.forex
        return VStack(alignment: .leading, spacing: 8) {
            Text("TIPO DE CAMBIO")
                .font(.caption.weight(.bold))
                .foregroundStyle(NexusTheme.accent)
            Text(fx?.EURUSD?.price.map { String(format: "1 EUR = %.4f USD", $0) } ?? "—")
                .font(.system(size: 28, weight: .bold, design: .rounded))
            Text(fx?.EURUSD?.price.flatMap { $0 > 0 ? String(format: "1 USD = %.4f EUR", 1 / $0) : nil } ?? "—")
                .font(.title3.monospacedDigit().weight(.semibold))
                .foregroundStyle(NexusTheme.muted)
            Text("Acción: \(fx?.signal?.action ?? "—")")
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(NexusTheme.toneColor(fx?.signal?.action))
            Text("Confianza: \(fx?.signal?.confidence ?? "—") · score \(formatDelta(fx?.signal?.score))")
                .font(.caption)
                .foregroundStyle(NexusTheme.muted)
        }
        .nexusCard()
        .nexusSizedCard(NexusLayout.standardCardHeight)
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
        .nexusSizedCard(NexusLayout.standardCardHeight)
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
        .nexusSizedCard(NexusLayout.standardCardHeight)
        .contentShape(Rectangle())
        .onTapGesture { store.showAsset("UUP") }
        .help("Abrir detalle del dólar")
    }

    private var goldCard: some View {
        let gld = store.snapshot?.gold?.GLD
        return VStack(alignment: .leading, spacing: 8) {
            Text(store.snapshot?.gold?.label ?? "ORO (GLD)")
                .font(.caption.weight(.bold))
                .foregroundStyle(NexusTheme.accent)
            metric("Spot", number(gld?.price, digits: 2))
            metric("MA20 / MA50", "\(number(gld?.ma20, digits: 2)) / \(number(gld?.ma50, digits: 2))")
            MetricBar(label: "Mom 1M", value: gld?.momentum1m, range: -8...8)
            MetricBar(label: "Mom 3M", value: gld?.momentum3m, range: -15...15)
            metric("Vol. 20d", formatPct(gld?.volatility20d))
        }
        .nexusCard()
        .nexusSizedCard(NexusLayout.standardCardHeight)
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
        .nexusSizedCard(NexusLayout.standardCardHeight)
    }

    private var forexPlanCard: some View {
        let signal = store.snapshot?.forex?.signal
        let rel = signal?.rel1m ?? 0
        return NexusGuidanceCard(
            doing: rel > 0.5 ? "Favorecer EUR frente a USD solo con confirmación de tendencia." :
                rel < -0.5 ? "Mantener sesgo defensivo hacia USD; esperar antes de comprar EUR." :
                "Mantener exposición neutral y esperar una ruptura clara.",
            avoiding: "No operar solo por un dato de momentum ni perseguir un movimiento diario. Confirmar con MA20/50, relativo y riesgo macro.",
            changes: "Un cruce sostenido de medias y un cambio de fuerza relativa 1M/3M modificarían el sesgo."
        )
    }

    private var forexMacroCard: some View {
        VStack(alignment: .leading, spacing: 7) {
            NexusSectionHeader(title: "CATALIZADOR MACRO", help: "Próximo evento económico que puede elevar la volatilidad de divisas.")
            Text(store.snapshot?.calendar?.nextEvent?.title ?? "Sin evento próximo")
                .font(.subheadline.weight(.semibold))
            Text(store.snapshot?.calendar?.nextEvent?.hoursUntil.map { String(format: "en %.0f horas", $0) } ?? "Calendario no disponible")
                .font(.caption)
                .foregroundStyle(NexusTheme.muted)
        }
        .nexusCard()
        .nexusSizedCard(NexusLayout.compactCardHeight)
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
        .nexusSizedCard(NexusLayout.compactCardHeight)
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
        .nexusSizedCard(NexusLayout.compactCardHeight)
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

struct RotationView: View {
    @EnvironmentObject private var store: NexusStore

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: NexusLayout.spacing) {
                VStack(alignment: .leading, spacing: 8) {
                    Text("LECTURA DEL FLUJO")
                        .font(.caption.weight(.bold))
                        .foregroundStyle(NexusTheme.accent)
                    Text(rotationHeadline)
                        .font(.title2.weight(.bold))
                    Text(rotationExplanation)
                        .font(.subheadline)
                        .foregroundStyle(NexusTheme.muted)
                    HStack(spacing: 18) {
                        Label("Líderes 1M \(formatPct(rotation?.leadersAvg1m))", systemImage: "crown")
                        Label("Receptores 1M \(formatPct(rotation?.receiversAvg1m))", systemImage: "arrow.down.right.and.arrow.up.left")
                        Spacer()
                        Text("Comprar \(buyCount) · Esperar \(waitCount) · Evitar \(sellCount)")
                            .fontWeight(.semibold)
                    }
                    .font(.caption)
                }
                .nexusCard()
                .frame(maxWidth: .infinity, minHeight: 130, alignment: .topLeading)

                NexusGuidanceCard(
                    doing: rotationDoing,
                    avoiding: "No perseguir antiguos líderes cuando pierden momentum relativo ni tratar el score como una orden aislada.",
                    changes: "La lectura cambiará si los receptores dejan de superar a los líderes o si cambia el relativo frente a SPY."
                )

                NexusAdaptiveGrid(minimumWidth: 200) {
                    NexusSummaryMetricCard(title: "AMPLITUD", value: "\(buyCount)/\(max(1, themes.count))", hint: "sectores recibiendo flujo", tone: buyCount > sellCount ? NexusTheme.good : NexusTheme.warn)
                    NexusSummaryMetricCard(title: "MEJOR RELATIVO", value: bestRelativeName, hint: "frente a SPY \(formatPct(bestRelative?.relative1mVsSpy))", tone: NexusTheme.good)
                    NexusSummaryMetricCard(title: "MÁS DÉBIL", value: weakestRelativeName, hint: "frente a SPY \(formatPct(weakestRelative?.relative1mVsSpy))", tone: NexusTheme.bad)
                    NexusSummaryMetricCard(title: "MOMENTUM MEDIO", value: formatPct(rotation?.receiversAvg1m), hint: "de receptores de flujo")
                }

                NexusAdaptiveGrid(minimumWidth: 320) {
                    rotationGroupCard("RECIBIENDO FLUJO", receivingThemes, NexusTheme.good)
                    rotationGroupCard("NEUTRALES", neutralThemes, NexusTheme.warn)
                    rotationGroupCard("PERDIENDO FUERZA", losingThemes, NexusTheme.bad)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(20)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .scrollBounceBehavior(.basedOnSize)
    }

    private var rotation: Rotation? { store.snapshot?.rotation }
    private var themes: [RotationTheme] { rotation?.themes ?? [] }
    private var receivingThemes: [RotationTheme] {
        themes.filter { tradeAction($0) == "VIGILAR COMPRA" }.sorted { ($0.score ?? 0) > ($1.score ?? 0) }
    }
    private var neutralThemes: [RotationTheme] {
        themes.filter { tradeAction($0) == "ESPERAR" }.sorted { ($0.score ?? 0) > ($1.score ?? 0) }
    }
    private var losingThemes: [RotationTheme] {
        themes.filter { tradeAction($0) == "EVITAR / REDUCIR" }.sorted { ($0.score ?? 0) > ($1.score ?? 0) }
    }
    private var buyCount: Int { themes.filter { tradeAction($0) == "VIGILAR COMPRA" }.count }
    private var waitCount: Int { themes.filter { tradeAction($0) == "ESPERAR" }.count }
    private var sellCount: Int { themes.filter { tradeAction($0) == "EVITAR / REDUCIR" }.count }
    private var bestRelative: RotationTheme? { themes.max { ($0.relative1mVsSpy ?? -.infinity) < ($1.relative1mVsSpy ?? -.infinity) } }
    private var weakestRelative: RotationTheme? { themes.min { ($0.relative1mVsSpy ?? .infinity) < ($1.relative1mVsSpy ?? .infinity) } }
    private var bestRelativeName: String { bestRelative?.ticker ?? bestRelative?.theme ?? "—" }
    private var weakestRelativeName: String { weakestRelative?.ticker ?? weakestRelative?.theme ?? "—" }

    private var rotationHeadline: String {
        guard !themes.isEmpty else { return "Sin datos suficientes de rotación" }
        if buyCount > sellCount { return "El flujo busca nuevos sectores donde entrar" }
        if sellCount > buyCount { return "Los antiguos líderes pierden fuerza; prioriza defensa" }
        return "Rotación mixta: todavía no hay un liderazgo claro"
    }

    private var rotationExplanation: String {
        let original = rotation?.summary ?? ""
        return original.isEmpty
            ? "Compara momentum sectorial y rendimiento frente al S&P 500 para separar oportunidades de zonas a evitar."
            : "\(original) Los valores altos indican mejor fuerza relativa; no son una orden de compra aislada."
    }

    private var rotationDoing: String {
        if !receivingThemes.isEmpty {
            let names = receivingThemes.prefix(2).map { $0.theme ?? $0.ticker ?? "—" }.joined(separator: " y ")
            return "Vigilar \(names) como posibles receptores de flujo y confirmar tendencia antes de entrar."
        }
        return "Mantener exposición equilibrada hasta que aparezca un receptor de flujo con ventaja clara."
    }

    private func rotationGroupCard(_ title: String, _ items: [RotationTheme], _ tone: Color) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            NexusSectionHeader(
                title: title,
                detail: "\(items.count)",
                help: "Clasificación basada en señal, momentum y rendimiento relativo frente al S&P 500."
            )
            if items.isEmpty {
                Text("Sin temas en este grupo.")
                    .font(.caption)
                    .foregroundStyle(NexusTheme.muted)
                    .padding(.vertical, 12)
            } else {
                ForEach(items) { theme in
                    Button {
                        if let ticker = theme.ticker { store.showAsset(ticker) }
                    } label: {
                        VStack(alignment: .leading, spacing: 5) {
                            HStack {
                                VStack(alignment: .leading, spacing: 1) {
                                    Text(theme.theme ?? theme.ticker ?? "—")
                                        .font(.subheadline.weight(.semibold))
                                        .foregroundStyle(NexusTheme.text)
                                        .lineLimit(1)
                                    if let group = theme.group {
                                        Text("\(group) · \(theme.ticker ?? "")")
                                            .font(.caption2)
                                            .foregroundStyle(NexusTheme.muted)
                                    }
                                }
                                Spacer()
                                Text(String(format: "%.0f", theme.score ?? 0))
                                    .font(.caption.monospacedDigit().weight(.bold))
                                    .foregroundStyle(tone)
                            }
                            NexusScoreBar(value: theme.score, showValue: false)
                            HStack {
                                Text("1M \(formatPct(theme.momentum1m))")
                                Spacer()
                                Text("vs SPY \(formatPct(theme.relative1mVsSpy))")
                            }
                            .font(.caption2)
                            .foregroundStyle(NexusTheme.muted)
                            Text(readableSignal(theme))
                                .font(.caption2)
                                .foregroundStyle(actionColor(theme))
                                .lineLimit(2)
                            if let names = theme.names, !names.isEmpty {
                                Text(names.prefix(4).joined(separator: " · "))
                                    .font(.caption2)
                                    .foregroundStyle(NexusTheme.muted.opacity(0.95))
                                    .lineLimit(1)
                            }
                        }
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    Divider().opacity(0.10)
                }
            }
        }
        .nexusCard()
        .frame(maxWidth: .infinity, alignment: .topLeading)
    }

    private func tradeAction(_ theme: RotationTheme) -> String {
        let signal = (theme.signal ?? "").lowercased()
        if signal.contains("entrada") || signal.contains("mejora") { return "VIGILAR COMPRA" }
        if signal.contains("corrección") || signal.contains("descanso") { return "EVITAR / REDUCIR" }
        return "ESPERAR"
    }

    private func readableSignal(_ theme: RotationTheme) -> String {
        switch tradeAction(theme) {
        case "VIGILAR COMPRA":
            return "Está recibiendo flujo; esperar confirmación antes de entrar."
        case "EVITAR / REDUCIR":
            return "Pierde fuerza frente al mercado; no perseguir el precio."
        default:
            return "Sin ventaja clara; mantenerlo en observación."
        }
    }

    private func actionColor(_ theme: RotationTheme) -> Color {
        switch tradeAction(theme) {
        case "VIGILAR COMPRA": return NexusTheme.good
        case "EVITAR / REDUCIR": return NexusTheme.bad
        default: return NexusTheme.warn
        }
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
        .nexusSizedCard(NexusLayout.metricCardHeight, alignment: .leading)
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
