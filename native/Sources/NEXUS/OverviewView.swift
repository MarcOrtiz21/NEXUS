import SwiftUI

struct OverviewView: View {
    @EnvironmentObject private var store: NexusStore

    var body: some View {
        NexusPage {
            if store.snapshot == nil {
                NexusSkeleton(rows: 4)
            } else {
                sessionPlanCard
                if store.snapshot?.rotationAlignment?.conflict == true {
                    alignmentNotice
                }
                trackThesisCard
                NexusKPIStrip(items: kpiItems)
                NexusResponsiveGrid(wideColumns: 3, mediumColumns: 1) {
                    vixCard
                    calendarCard
                    newsPulseCard
                }
                NexusResponsiveGrid(wideColumns: 3, mediumColumns: 1) {
                    rankingCard
                    allocationCard
                    macroPulseCard
                }
                comparisonCard
            }
        }
    }

    private var decision: Decision? { store.snapshot?.decision }
    private var plan: SessionPlan? { store.snapshot?.sessionPlan }
    private var alignment: RotationAlignment? { store.snapshot?.rotationAlignment }

    private var sessionPlanCard: some View {
        NexusStanceCard(
            stance: plan?.stance ?? decision?.operationalAction ?? "ESPERAR",
            buy: plan?.buy ?? "Sin sesgo todavía",
            verdict: plan?.verdict ?? "Esperar a una lectura completa de la sesión.",
            doing: plan?.doing ?? "Confirmar bloqueo, asignación y sesgo de divisas antes de actuar.",
            avoiding: plan?.avoiding ?? "No tratar ESPERAR como una orden ni comprar por un titular aislado.",
            changes: plan?.changes,
            help: "Qué hacer con cada activo. El % es peso de cartera, no una orden si la acción es ESPERAR.",
            buyLabel: plan?.buyLabel ?? "AHORA",
            context: plan?.context ?? [],
            weightCaption: plan?.weightCaption,
            legs: plan?.legs ?? [],
            confidence: plan?.confidence ?? decision?.confidence,
            confidenceNote: plan?.confidenceNote ?? decision?.confidenceNote,
            score: plan?.score ?? decision?.score,
            scoreDrivers: plan?.scoreDrivers ?? []
        )
    }

    private var alignmentNotice: some View {
        NexusNoticeCard(
            title: alignment?.title ?? "La operativa no autoriza entradas",
            detail: alignment?.detail ?? "Rotación es vigilancia, no una orden de compra.",
            actionTitle: "Ver rotación"
        ) {
            store.selected = .rotation
        }
    }

    private var trackThesisCard: some View {
        let thesis = store.snapshot?.intelligence?.trackThesis
        let headline = thesis?.headline ?? "Aún no hay muestra para contrastar la tesis"
        let detail = thesis?.detail ?? "Se rellenará tras varias capturas persistidas."
        return VStack(alignment: .leading, spacing: 6) {
            NexusSectionHeader(
                title: "Tesis vs SPY",
                help: "Cuando la señal fue COMPRAR, ¿subió el S&P 500 a 5 y 20 días? No es la rentabilidad de una cartera NEXUS."
            )
            Text(headline)
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(NexusTheme.toneColor(thesis?.tone))
                .fixedSize(horizontal: false, vertical: true)
            Text(detail)
                .font(.caption)
                .foregroundStyle(NexusTheme.muted)
                .fixedSize(horizontal: false, vertical: true)
            if let count = thesis?.buyCount, let sample = thesis?.sampleSize {
                Text("Muestra: \(count) COMPRAR · \(sample) lecturas")
                    .font(.caption2)
                    .foregroundStyle(NexusTheme.muted)
            }
        }
        .nexusCard()
    }

    private var freshnessShort: String {
        let statuses = (store.snapshot?.freshness?.layers ?? []).compactMap(\.status)
        if statuses.contains(where: { $0 == "MISSING" || $0 == "ERROR" }) { return "Huecos" }
        if statuses.contains("STALE") { return "Caducado" }
        if statuses.contains("OK") { return "Al día" }
        return relativeAge(from: store.snapshot?.capturedAtUtc)
    }

    private var calendarCard: some View {
        let events = store.snapshot?.calendar?.upcoming ?? []
        return VStack(alignment: .leading, spacing: 8) {
            NexusSectionHeader(
                title: "Calendario 72h",
                help: "Eventos US de las próximas 72 horas. Si la hora es RSS o manual, es una ventana aproximada, no un FOMC datado."
            )
            if events.isEmpty {
                Text("No hay FOMC, CPI o NFP en las próximas 72 horas.")
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

    private var vixCard: some View {
        let value = market("VIX")
        return VStack(alignment: .leading, spacing: 10) {
            NexusSectionHeader(
                title: "VIX",
                help: "Termómetro de estrés. Calma favorece riesgo; estrés pide liquidez. No es una orden."
            )
            HStack(alignment: .firstTextBaseline, spacing: 10) {
                Text(value.map { String(format: "%.1f", $0) } ?? "—")
                    .font(.system(size: 34, weight: .bold, design: .rounded))
                    .foregroundStyle(vixColor(value))
                VStack(alignment: .leading, spacing: 2) {
                    Text(vixLabel(value))
                        .font(.headline.weight(.bold))
                        .foregroundStyle(vixColor(value))
                    Text("MA5 \(number(market("VIX_MA5"))) · MA20 \(number(market("VIX_MA20")))")
                        .font(.caption2)
                        .foregroundStyle(NexusTheme.muted)
                }
                Spacer(minLength: 8)
                NexusMiniSparkline(points: sparkline(for: "VIX"), width: 120, height: 44)
            }
            vixMeter(value)
            Text(macroInterpretation)
                .font(.caption)
                .foregroundStyle(NexusTheme.muted)
                .fixedSize(horizontal: false, vertical: true)
        }
        .nexusCard()
    }

    private func vixMeter(_ value: Double?) -> some View {
        let position = min(1, max(0, ((value ?? 18) - 10) / 30))
        return VStack(alignment: .leading, spacing: 4) {
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    HStack(spacing: 0) {
                        vixBand("Calma", NexusTheme.good)
                        vixBand("Normal", NexusTheme.accent)
                        vixBand("Cautela", NexusTheme.warn)
                        vixBand("Estrés", NexusTheme.bad)
                    }
                    .clipShape(RoundedRectangle(cornerRadius: 4, style: .continuous))
                    Circle()
                        .fill(NexusTheme.text)
                        .frame(width: 9, height: 9)
                        .shadow(color: .black.opacity(0.35), radius: 1, y: 1)
                        .offset(x: max(0, min(geo.size.width - 9, geo.size.width * position - 4.5)))
                }
            }
            .frame(height: 22)
            HStack {
                Text("<15")
                Spacer()
                Text("15–20")
                Spacer()
                Text("20–30")
                Spacer()
                Text(">30")
            }
            .font(.system(size: 8, weight: .semibold))
            .foregroundStyle(NexusTheme.muted)
        }
    }

    private var kpiItems: [NexusKPI] {
        let blocked = store.snapshot?.calendar?.shouldBlock == true
        let cash = decision?.allocation?["CASH"]
        return [
            NexusKPI(
                title: "SCORE",
                value: decision?.score.map { "\($0)/100" } ?? "—",
                hint: plan?.confidence ?? decision?.confidence ?? "convicción",
                tone: actionColor,
                help: "Convicción macro. La confianza baja si el dato está caducado o el calendario es estimado."
            ),
            NexusKPI(
                title: "BLOQUEO",
                value: blocked ? "Activo" : "Libre",
                hint: blocked ? "\(store.snapshot?.calendar?.blockHours ?? 0)h" : "sin filtro de calendario",
                tone: blocked ? NexusTheme.bad : NexusTheme.good
            ),
            NexusKPI(
                title: "LIQUIDEZ",
                value: cash.map { "\($0)%" } ?? "—",
                hint: "peso de cartera ahora",
                tone: NexusTheme.good,
                help: "Porcentaje de CASH en la asignación operativa actual."
            ),
            NexusKPI(
                title: "DATOS",
                value: freshnessShort,
                hint: store.snapshot?.freshness?.headline ?? store.engineStatus,
                tone: NexusTheme.toneColor(store.snapshot?.freshness?.tone),
                help: "Frescura por capa: mercado (Yahoo), macro (FRED/PER) y empresas. No es una sola hora de captura."
            ),
        ]
    }

    private var comparisonCard: some View {
        let vs = store.snapshot?.comparison?.vsYesterday ?? store.snapshot?.comparison?.vsPrevious
        return VStack(alignment: .leading, spacing: 10) {
            Text("VS AYER / ANTERIOR")
                .font(.caption.weight(.bold))
                .foregroundStyle(NexusTheme.accent)
            if let vs {
                NexusAdaptiveGrid(minimumWidth: 105, spacing: 8) {
                    metric("Score", formatDelta(vs.scoreDelta))
                    metric("SPY", formatPct(vs.spyPct))
                    metric("Oro", formatPct(vs.gldPct))
                    metric("EURUSD", formatPct(vs.eurusdPct))
                }
                if vs.actionChanged == true {
                    Text("Señal: \(vs.actionFrom ?? "—") → \(vs.actionTo ?? "—")")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(NexusTheme.warn)
                } else {
                    Text("Sin cambio de acción (\(vs.actionTo ?? "—"))")
                        .font(.caption)
                        .foregroundStyle(NexusTheme.muted)
                }
                Text("Ref: \(vs.previousCapturedAt ?? "—")")
                    .font(.caption2)
                    .foregroundStyle(NexusTheme.muted)
            } else {
                Text("Aún no hay historial suficiente para comparar.")
                    .foregroundStyle(NexusTheme.muted)
            }
        }
        .nexusCard()
    }

    private var macroPulseCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            NexusSectionHeader(
                title: "Tipos e inflación",
                help: "Condicionan valoración y duración. El VIX está en la tarjeta de arriba."
            )
            macroRow("Bono 10Y", market("US10Y"), suffix: "%")
            macroRow("Inflación", market("CPI_YoY_Pct"), suffix: "%")
            macroRow("Curva 10Y–2Y", market("Yield_Curve_Spread"), suffix: " pp")
            Text(ratesInterpretation)
                .font(.caption)
                .foregroundStyle(NexusTheme.muted)
        }
        .nexusCard()
    }

    private var rankingCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            NexusSectionHeader(
                title: "Ranking de activos",
                help: "Score técnico 0–100. La columna de la derecha es la lectura del activo, no el permiso operativo."
            )
            let ranked = (decision?.assetScores ?? [:]).sorted { ($0.value.score ?? 0) > ($1.value.score ?? 0) }
            ForEach(Array(ranked.prefix(6)), id: \.key) { ticker, asset in
                Button {
                    store.showAsset(ticker)
                } label: {
                    HStack(alignment: .center, spacing: 10) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(asset.label ?? ticker)
                                .font(.caption.weight(.semibold))
                                .lineLimit(1)
                            Text(rankingMovement(ticker))
                                .font(.system(size: 9, weight: .semibold))
                                .foregroundStyle(rankingMovementColor(ticker))
                            Text("1M \(formatPct(asset.momentum1m)) · 3M \(formatPct(asset.momentum3m))")
                                .font(.caption2)
                                .foregroundStyle(NexusTheme.muted)
                        }
                        .frame(minWidth: 108, maxWidth: 150, alignment: .leading)
                        NexusMiniSparkline(points: sparkline(for: ticker))
                        VStack(alignment: .trailing, spacing: 3) {
                            NexusScoreBar(value: asset.score.map(Double.init))
                            Text(rankingInstruction(ticker, asset.action))
                                .font(.caption2.weight(.semibold))
                                .foregroundStyle(NexusTheme.toneColor(rankingInstruction(ticker, asset.action)))
                                .lineLimit(2)
                                .multilineTextAlignment(.trailing)
                        }
                        Image(systemName: "chevron.right")
                            .font(.caption2)
                            .foregroundStyle(NexusTheme.muted)
                    }
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .help("Abrir detalle técnico de \(asset.label ?? ticker)")
            }
        }
        .nexusCard()
    }

    private var allocationCard: some View {
        let operational = (decision?.allocation ?? [:]).filter { $0.value > 0 }.sorted { $0.value > $1.value }
        let macro = decision?.macroAllocation ?? [:]
        return VStack(alignment: .leading, spacing: 10) {
            NexusSectionHeader(
                title: "Asignación de cartera",
                help: "El % es peso sobre 100 de cartera. La barra de arriba es lo que manda ahora; abajo, lo que usaría el modelo si se abriera."
            )
            if !operational.isEmpty {
                allocationStack(operational)
            }
            ForEach(operational, id: \.key) { key, value in
                HStack(spacing: 8) {
                    Text(allocationLabel(key))
                        .frame(minWidth: 88, alignment: .leading)
                    ProgressView(value: Double(value), total: 100)
                        .tint(key == "CASH" ? NexusTheme.good : NexusTheme.accent)
                    Text("\(value)%")
                        .font(.caption.monospacedDigit().weight(.semibold))
                        .frame(width: 36, alignment: .trailing)
                    Text(plan?.allowsEntry == true ? "ahora" : (key == "CASH" ? "ahora" : "bloqueo"))
                        .font(.caption2)
                        .foregroundStyle(NexusTheme.muted)
                        .frame(width: 52, alignment: .trailing)
                }
                .font(.caption)
            }
            if !macro.isEmpty, macro != decision?.allocation {
                Divider().opacity(0.12)
                Text("SI SE ABRIERA · peso de cartera")
                    .font(.caption2.weight(.bold))
                    .foregroundStyle(NexusTheme.warn)
                allocationStack(macro.filter { $0.value > 0 }.sorted { $0.value > $1.value })
                Text(allocationSummary(macro))
                    .font(.caption2)
                    .foregroundStyle(NexusTheme.muted)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .nexusCard()
    }

    private func allocationStack(_ items: [Dictionary<String, Int>.Element]) -> some View {
        GeometryReader { geo in
            HStack(spacing: 1) {
                ForEach(items, id: \.key) { key, value in
                    Rectangle()
                        .fill(allocationColor(key))
                        .frame(width: max(2, geo.size.width * CGFloat(value) / 100))
                }
            }
            .clipShape(RoundedRectangle(cornerRadius: 5, style: .continuous))
        }
        .frame(height: 12)
    }

    private func allocationColor(_ key: String) -> Color {
        switch key.uppercased() {
        case "CASH": return NexusTheme.good
        case "SPY", "QQQ": return NexusTheme.accent
        case "TLT": return NexusTheme.warn
        case "GLD": return Color.orange
        default: return NexusTheme.muted
        }
    }

    private func allocationLabel(_ key: String) -> String {
        switch key.uppercased() {
        case "SPY": return "S&P 500"
        case "QQQ": return "Nasdaq"
        case "TLT": return "Bonos"
        case "GLD": return "Oro"
        case "UUP": return "Dólar"
        case "CASH": return "Liquidez"
        case "EURUSD": return "Euro/USD"
        default: return key
        }
    }

    private var newsPulseCard: some View {
        let news = store.snapshot?.news
        let sentiment = news?.sentiment
        return VStack(alignment: .leading, spacing: 9) {
            Text("PULSO DE NOTICIAS")
                .font(.caption.weight(.bold))
                .foregroundStyle(NexusTheme.accent)
            HStack(alignment: .firstTextBaseline) {
                Text(sentiment?.dominant ?? "Neutral")
                    .font(.title3.weight(.bold))
                    .foregroundStyle(NexusTheme.toneColor(sentiment?.dominant))
                Spacer()
                Text("\(news?.count ?? 0) titulares")
                    .font(.caption.monospacedDigit().weight(.semibold))
                    .foregroundStyle(NexusTheme.muted)
            }
            if let details = sentiment?.details, !details.isEmpty {
                Text(details)
                    .font(.caption)
                    .foregroundStyle(NexusTheme.muted)
                    .lineLimit(4)
            }
            if let narratives = news?.narratives?.narratives {
                ForEach(narratives.prefix(2)) { narrative in
                    HStack(spacing: 6) {
                        Circle()
                            .fill(NexusTheme.toneColor(narrative.dominantTone))
                            .frame(width: 6, height: 6)
                        Text(narrative.topic ?? "Tema")
                            .font(.caption.weight(.semibold))
                        Spacer()
                        Text("\(narrative.headlineCount ?? 0)")
                            .font(.caption2.monospacedDigit())
                            .foregroundStyle(NexusTheme.muted)
                    }
                }
            }
        }
        .nexusCard()
        .contentShape(Rectangle())
        .onTapGesture { store.selected = .news }
        .help("Abrir noticias")
    }

    private func macroRow(_ label: String, _ value: Double?, suffix: String) -> some View {
        HStack {
            Text(label).foregroundStyle(NexusTheme.muted)
            Spacer()
            Text(value.map { String(format: "%.2f%@", $0, suffix) } ?? "—")
                .fontWeight(.semibold)
        }
        .font(.caption)
    }

    private func vixBand(_ label: String, _ color: Color) -> some View {
        Text(label)
            .font(.system(size: 8, weight: .semibold))
            .foregroundStyle(color)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 4)
            .background(color.opacity(0.12))
    }

    private func vixColor(_ value: Double?) -> Color {
        guard let value else { return NexusTheme.muted }
        if value < 15 { return NexusTheme.good }
        if value < 20 { return NexusTheme.accent }
        if value < 30 { return NexusTheme.warn }
        return NexusTheme.bad
    }

    private func vixLabel(_ value: Double?) -> String {
        guard let value else { return "Sin dato" }
        if value < 15 { return "Calma" }
        if value < 20 { return "Normal" }
        if value < 30 { return "Cautela" }
        return "Estrés"
    }

    private func rankingMovement(_ ticker: String) -> String {
        guard let delta = rankingDelta(for: ticker) else { return "sin comparación" }
        if let rankDelta = delta.rankDelta, rankDelta != 0 {
            return rankDelta > 0 ? "↑ \(rankDelta) puestos" : "↓ \(abs(rankDelta)) puestos"
        }
        if let scoreDelta = delta.scoreDelta {
            return "score \(scoreDelta >= 0 ? "+" : "")\(String(format: "%.1f", scoreDelta))"
        }
        return "sin cambio"
    }

    private func rankingInstruction(_ ticker: String, _ technical: String?) -> String {
        guard let leg = plan?.legs?.first(where: { $0.ticker == ticker }) else {
            return technical ?? "—"
        }
        if leg.now == "NO ABRIR" { return "NO ABRIR ahora" }
        if leg.now == "COMPRAR", let weight = leg.openWeight {
            return "COMPRAR \(weight)%"
        }
        if let now = leg.now, !now.isEmpty { return now }
        return technical ?? "—"
    }

    private func sparkline(for ticker: String) -> [SparklinePoint] {
        store.snapshot?.sparklines?[ticker]
            ?? store.snapshot?.sparklines?["^\(ticker)"]
            ?? []
    }

    private func number(_ value: Double?) -> String {
        value.map { String(format: "%.1f", $0) } ?? "—"
    }

    private func rankingMovementColor(_ ticker: String) -> Color {
        guard let delta = rankingDelta(for: ticker) else { return NexusTheme.muted }
        let value = Double(delta.rankDelta ?? 0) + (delta.scoreDelta ?? 0)
        return value > 0 ? NexusTheme.good : value < 0 ? NexusTheme.bad : NexusTheme.muted
    }

    private func rankingDelta(for ticker: String) -> RankingDelta? {
        store.snapshot?.rankingDelta?[ticker]
            ?? store.snapshot?.assetRanking?.first { $0.ticker == ticker }
    }

    private func market(_ key: String) -> Double? {
        store.snapshot?.market?[key]?.value
    }

    private var macroInterpretation: String {
        if let vix = market("VIX"), vix > 25 {
            return "Volatilidad alta: priorizar liquidez y reducir tamaño."
        }
        if let vix = market("VIX"), vix < 15 {
            return "Volatilidad baja: el entorno no está en estrés, pero el bloqueo sigue mandando."
        }
        return "VIX en zona normal. No sustituye al permiso operativo."
    }

    private var ratesInterpretation: String {
        if let yield = market("US10Y"), yield > 4.5 {
            return "Tipos elevados: presión para activos de larga duración."
        }
        if market("US10Y") == nil && market("CPI_YoY_Pct") == nil {
            return "Datos de tipos e inflación insuficientes."
        }
        return "Revisa tipos e inflación junto con el VIX de arriba; no son una orden."
    }

    private func metric(_ title: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title).font(.caption2).foregroundStyle(NexusTheme.muted)
            Text(value).font(.headline.monospacedDigit())
        }
    }

    private func allocationSummary(_ allocation: [String: Int]) -> String {
        allocation
            .filter { $0.value > 0 }
            .sorted { $0.value > $1.value }
            .map { "\($0.key) \($0.value)%" }
            .joined(separator: " · ")
    }

    private var actionColor: Color {
        let text = (decision?.operationalAction ?? decision?.action ?? "").uppercased()
        if text.contains("COMPRAR") { return NexusTheme.good }
        if text.contains("VENDER") || text.contains("REDUCIR") { return NexusTheme.bad }
        return NexusTheme.warn
    }
}

struct BlockBannerView: View {
    @EnvironmentObject private var store: NexusStore
    let banner: BlockBanner
    let compact: Bool
    @State private var remaining: Int
    @State private var expanded = false

    init(banner: BlockBanner, compact: Bool = false) {
        self.banner = banner
        self.compact = compact
        _remaining = State(initialValue: banner.countdownSeconds ?? 0)
    }

    var body: some View {
        Group {
            if compact && !expanded {
                compactBody
            } else {
                expandedBody
            }
        }
        .foregroundStyle(.white)
        .padding(compact && !expanded ? 10 : 14)
        .background(
            LinearGradient(
                colors: [NexusTheme.bad.opacity(0.82), Color.orange.opacity(0.66)],
                startPoint: .leading,
                endPoint: .trailing
            )
        )
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        .task(id: banner.countdownSeconds) {
            remaining = banner.countdownSeconds ?? 0
            while remaining > 0 && !Task.isCancelled {
                do {
                    try await Task.sleep(nanoseconds: 1_000_000_000)
                    remaining -= 1
                } catch {
                    return
                }
            }
        }
    }

    private var compactBody: some View {
        HStack(spacing: 10) {
            Image(systemName: banner.estimated == true ? "clock.badge.exclamationmark" : "exclamationmark.triangle.fill")
            Text(banner.title)
                .font(.subheadline.weight(.bold))
                .lineLimit(1)
            Text("· \(banner.actionHint ?? "ESPERAR")")
                .font(.caption.weight(.semibold))
                .lineLimit(1)
            Spacer()
            if remaining > 0 {
                Text(countdownLabel)
                    .font(.caption.monospacedDigit().weight(.bold))
            }
            NexusActionButton(title: "Detalle", role: .onAccent) {
                withAnimation(.easeInOut(duration: 0.18)) { expanded = true }
            }
        }
    }

    private var expandedBody: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: banner.estimated == true ? "clock.badge.exclamationmark" : "exclamationmark.triangle.fill")
                Text(banner.title)
                    .font(.headline)
                Spacer()
                if remaining > 0 {
                    Text(countdownLabel)
                        .font(.caption.monospacedDigit().weight(.bold))
                }
                if compact {
                    NexusActionButton(title: "Ocultar", systemImage: "chevron.up", role: .onAccent, helpText: "Contraer aviso") {
                        withAnimation(.easeInOut(duration: 0.18)) { expanded = false }
                    }
                }
            }
            Text(banner.guidance)
                .font(.subheadline)
            if banner.estimated == true {
                Text("La hora es una ventana aproximada (RSS o manual), no un datado FRED.")
                    .font(.caption)
                    .opacity(0.9)
            }
            if let event = banner.eventTitle {
                Text("Evento: \(event)")
                    .font(.caption)
                    .opacity(0.9)
            }
            Text("Sugerencia: \(banner.actionHint ?? "ESPERAR")")
                .font(.caption.weight(.semibold))
            HStack(spacing: 8) {
                NexusActionButton(title: "Ver histórico", systemImage: "chart.xyaxis.line", role: .onAccent) {
                    store.selected = .history
                }
                NexusActionButton(
                    title: "Reevaluar",
                    systemImage: "arrow.clockwise",
                    role: .prominent,
                    disabled: store.loading
                ) {
                    Task { await store.refresh(persist: true) }
                }
            }
        }
    }

    private var countdownLabel: String {
        let h = remaining / 3600
        let m = (remaining % 3600) / 60
        let s = remaining % 60
        if h > 0 { return String(format: "%dh %02dm", h, m) }
        return String(format: "%02d:%02d", m, s)
    }

}
